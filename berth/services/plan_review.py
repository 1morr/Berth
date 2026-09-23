"""停在 review 的 Plan：逐列改、核准、拒絕（plan §3.1 `review` 的出邊、§6 plans 群組、M2 票 07）。

**Plan 在核准之前不碰任何檔案**（PRODUCT 原則 2），所以這裡的三支命令只改資料庫；檔案由
importer 照核准後的那一份去鏈接（`services/importer.py`）——核准不另外走一條入庫的路。

- **逐列改**（`edit_items`）：改處置與季集，然後**整份重算一次**目標路徑與字幕的附掛
  （`parser.revise`，與規劃時同一份規則）。改一列可能動到另一列：影片換了一集，它的字幕跟著搬。
  不合法的改動整批拒絕、什麼都不寫（`PlanRefusal`）。
- **核准**（`approve_plan`）＝照提案入庫（2026-09-23 使用者拍板）：待審核的列季集完整就入庫，
  寫下的路徑就是畫面上 `landing` 算出來的那一份。還有沒決定的列或兩列撞同一條路徑時拒絕。
  `review → importing`，然後叫醒 importer。**批次核准與改過之後的核准是同一支**：一份 Plan 一顆
  按鈕，改過幾列都一樣。
- **拒絕**（`reject_plan`）照 plan §3.1：`review → completed`。規劃器下一輪會把它**整份重算**，
  所以拒絕的意思是「丟掉這一份（連同改過的列），重來一次」；檔案不動。

三支都在那筆 Job 的鎖裡、在鎖裡重讀：兩個分頁同時按的時候，後到的那一個讀到先到的結果，
得到 `not_pending`，而不是兩個都成立（票 06 的 `TestTwoTabs` 同一個道理）。
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace

from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import (
    EDITABLE_ACTIONS,
    EventType,
    JobState,
    MediaKind,
    PlanAction,
    PlanEngine,
    PlanRefusal,
    PlanStatus,
    PlanSummary,
    why,
)
from berth.domain import PlanItem as PlannedFile
from berth.domain import ReasonCode as Code
from berth.logs import job_context
from berth.models import Job
from berth.models.types import utcnow
from berth.parser import revise
from berth.services.events import EventHub, JobSignal
from berth.services.jobs import job_lock, record_event, transition
from berth.services.plan import WRITTEN, summarise
from berth.services.plan_view import (
    LoadedPlan,
    PlanView,
    dump_reasons,
    landing,
    load_plan,
    read_plan,
)

logger = logging.getLogger(__name__)

#: 撞上的那一份 `detail` 最多列幾個檔名。其餘的畫面上那幾列自己看得到。
_NAMED = 3


class PlanRejectedError(Exception):
    """改不下去、核准不了，而且**還沒動任何東西**（`domain.PlanRefusal`）。"""

    def __init__(self, reason: PlanRefusal, detail: str) -> None:
        super().__init__(f"{reason.value}: {detail}")
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True, slots=True)
class ItemEdit:
    """一列要改成什麼。季集只屬於劇集的入庫，其餘處置三格都是 `None`。"""

    id: int
    action: PlanAction
    season: int | None = None
    episode_start: int | None = None
    episode_end: int | None = None


async def edit_items(
    session: AsyncSession, plan_id: int, edits: Sequence[ItemEdit], *, actor: str
) -> PlanView:
    """逐列改（`PUT /plans/{id}/items`），回改完之後的整份——畫面拿它畫新的目標路徑。"""
    async with _deciding(session, plan_id) as (loaded, _):
        by_id = {row.id: index for index, row in enumerate(loaded.rows)}
        items = list(loaded.items)
        for edit in edits:
            index = by_id.get(edit.id)
            if index is None:
                raise PlanRejectedError(PlanRefusal.ITEM_MISSING, str(edit.id))
            _check(edit, loaded, index)
            items[index] = _edited(items[index], edit)
        changed = replace(loaded, items=tuple(items))
        # 比的是**核准的話**會寫出去的那一份：待審核那一列的提案也會，等到按核准才說「撞了」，
        # 使用者要回頭找是哪一列。存下來的仍然是改過、但**還沒升級**的那一份。
        _refuse_clashes(landing(changed))
        revised = revise(changed.items, loaded.media, settled=loaded.settled)
        edited = {by_id[edit.id] for edit in edits}
        _write(loaded, revised, edited=edited)
        loaded.plan.engine = PlanEngine.USER
        await session.commit()
    logger.info("plan items edited", extra={"plan": plan_id, "count": len(edits), "actor": actor})
    view = await read_plan(session, plan_id)
    assert view is not None  # 剛在鎖裡讀過、寫過，commit 之後不會憑空消失
    return view


async def approve_plan(
    session: AsyncSession, hub: EventHub, plan_id: int, *, actor: str
) -> PlanView:
    """核准＝照提案入庫：寫下 `landing` 那一份，`review → importing`（plan §3.1）。

    呼叫端負責叫醒 importer（`api/plans.py`）：這一支只讓狀態落地，不自己鏈接任何東西。
    """
    async with _deciding(session, plan_id) as (loaded, job):
        landed = landing(loaded)
        held = [
            item.rel_path
            for item in landed
            if item.action is PlanAction.REVIEW and item.rel_path not in loaded.settled
        ]
        if held:
            raise PlanRejectedError(PlanRefusal.UNDECIDED, _names(held))
        _refuse_clashes(landed)
        _write(loaded, landed, edited=set())
        plan = loaded.plan
        plan.status = PlanStatus.APPROVED
        plan.decided_by = actor
        plan.decided_at = utcnow()
        files = sum(1 for item in landed if item.action in WRITTEN)
        if not await transition(session, job, JobState.IMPORTING, expected=JobState.REVIEW):
            raise PlanRejectedError(PlanRefusal.NOT_PENDING, job.state.value)
        await record_event(
            session,
            job,
            EventType.REVIEW_DECIDED,
            actor=actor,
            payload={"plan": plan.id, "decision": PlanStatus.APPROVED.value, "files": files},
        )
        await session.commit()
        hub.publish(JobSignal(hash=job.hash, state=job.state, progress=job.progress))
    logger.info("plan approved", extra={"plan": plan_id, "files": files})
    view = await read_plan(session, plan_id)
    assert view is not None
    return view


async def reject_plan(session: AsyncSession, hub: EventHub, plan_id: int, *, actor: str) -> None:
    """拒絕：`review → completed`（plan §3.1），規劃器下一輪整份重算。檔案不動。

    呼叫端負責叫醒規劃器；Plan 這一列先記下「被拒絕了、誰、什麼時候」，重算時它會被換掉，
    那一次決定留在時間線上（`review_decided`）。
    """
    async with _deciding(session, plan_id) as (loaded, job):
        plan = loaded.plan
        plan.status = PlanStatus.REJECTED
        plan.decided_by = actor
        plan.decided_at = utcnow()
        if not await transition(session, job, JobState.COMPLETED, expected=JobState.REVIEW):
            raise PlanRejectedError(PlanRefusal.NOT_PENDING, job.state.value)
        await record_event(
            session,
            job,
            EventType.REVIEW_DECIDED,
            actor=actor,
            payload={"plan": plan.id, "decision": PlanStatus.REJECTED.value},
        )
        await session.commit()
        hub.publish(JobSignal(hash=job.hash, state=job.state, progress=job.progress))
    logger.info("plan rejected", extra={"plan": plan_id})


@asynccontextmanager
async def _deciding(session: AsyncSession, plan_id: int) -> AsyncIterator[tuple[LoadedPlan, Job]]:
    """三支命令共用的入口：**鎖住那一筆 Job，在鎖裡重讀這份 Plan**，確認它還在等人。

    拒絕在任何寫入之前丟出來，所以例外離開時 session 裡沒有要撤回的東西；保險起見仍然 rollback
    ——`transition` 的 CAS 輸掉時，Plan 這一列已經被改過了。
    """
    loaded = await load_plan(session, plan_id)
    if loaded is None:
        raise PlanRejectedError(PlanRefusal.PLAN_MISSING, str(plan_id))
    job_hash = loaded.plan.job_hash
    if job_hash is None:
        # 重新入庫的 Plan 沒有 Job，也就沒有 `review` 可以離開（票 10 再決定它怎麼核准）。
        raise PlanRejectedError(PlanRefusal.NOT_PENDING, "no job")
    with job_context(job_hash):
        async with job_lock(job_hash):
            fresh = await load_plan(session, plan_id)
            job = await session.get(Job, job_hash, populate_existing=True)
            if fresh is None:
                raise PlanRejectedError(PlanRefusal.PLAN_MISSING, str(plan_id))
            if (
                job is None
                or job.state is not JobState.REVIEW
                or fresh.plan.status is not PlanStatus.PENDING_REVIEW
            ):
                raise PlanRejectedError(PlanRefusal.NOT_PENDING, fresh.plan.status.value)
            try:
                yield fresh, job
            except PlanRejectedError:
                await session.rollback()
                raise


def _check(edit: ItemEdit, loaded: LoadedPlan, index: int) -> None:
    """一列的改動合不合法。**矛盾的改動拒絕，不是默默修正**（票面驗收）。"""
    row, item = loaded.rows[index], loaded.items[index]
    name = item.name
    if row.applied_at is not None:
        raise PlanRejectedError(PlanRefusal.ITEM_APPLIED, name)
    if edit.action not in EDITABLE_ACTIONS[item.kind]:
        raise PlanRejectedError(PlanRefusal.ACTION_NOT_ALLOWED, name)
    if edit.action in WRITTEN and loaded.media is None:
        raise PlanRejectedError(PlanRefusal.MEDIA_MISSING, name)
    numbered = edit.action is PlanAction.IMPORT and (
        loaded.media is not None and loaded.media.kind is MediaKind.TV
    )
    given = (edit.season, edit.episode_start, edit.episode_end)
    if not numbered:
        if any(value is not None for value in given):
            raise PlanRejectedError(PlanRefusal.EPISODE_NOT_ALLOWED, name)
        return
    if edit.season is None or edit.episode_start is None:
        raise PlanRejectedError(PlanRefusal.EPISODE_REQUIRED, name)
    if edit.episode_end is not None and edit.episode_end < edit.episode_start:
        raise PlanRejectedError(PlanRefusal.EPISODE_RANGE_REVERSED, name)


def _edited(item: PlannedFile, edit: ItemEdit) -> PlannedFile:
    """人說了算：處置與季集照改，理由留著（那是解析器看到的證據）並多一條 `set_by_user`。

    結束集等於起始集時存成 `None`：單集檔就是單集檔，`S01E05-E05` 不是一種檔名。
    """
    end = None if edit.episode_end == edit.episode_start else edit.episode_end
    marked = why(Code.SET_BY_USER)
    return item.model_copy(
        update={
            "action": edit.action,
            "season": edit.season,
            "episode_start": edit.episode_start,
            "episode_end": end,
            "reasons": item.reasons if marked in item.reasons else (*item.reasons, marked),
        }
    )


def _refuse_clashes(items: Sequence[PlannedFile]) -> None:
    counted = Counter(item.target_path for item in items if item.action in WRITTEN)
    clashes = sorted(path for path, count in counted.items() if path and count > 1)
    if clashes:
        raise PlanRejectedError(PlanRefusal.TARGET_CLASH, clashes[0])


def _write(loaded: LoadedPlan, items: Sequence[PlannedFile], *, edited: set[int]) -> None:
    """解析器的形狀寫回那幾列，以及一份重算過的摘要。已經鏈接的列不動。

    改過的那幾列清掉 `error`（例如 `target_unmanaged`：人把它改成略過就是他的回答）與 `audit`
    ——人親手指定的一列沒有「medium 待確認」可言。
    """
    for index, (row, item) in enumerate(zip(loaded.rows, items, strict=True)):
        if row.applied_at is not None:
            continue
        row.action = item.action
        row.season = item.season
        row.episode_start = item.episode_start
        row.episode_end = item.episode_end
        row.target_path = item.target_path
        row.confidence = item.confidence
        row.reasons_json = dump_reasons(item.reasons)
        if index in edited:
            row.error = ""
            row.audit = False
    plan = loaded.plan
    reason = PlanSummary.model_validate(plan.summary_json or {}).review_reason
    plan.summary_json = summarise(items, reason).model_dump(mode="json")


def _names(paths: Sequence[str]) -> str:
    names = [path.rpartition("/")[2] for path in paths]
    extra = len(names) - _NAMED
    return ", ".join(names[:_NAMED]) + (f" (+{extra})" if extra > 0 else "")
