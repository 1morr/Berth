"""`importer`：Import Plan → 媒體庫（plan §3.1、§3.2、§3.3、brief §4.4、§5.3、票 12）。

**這是整個產品唯一會在媒體庫裡放東西的地方**，而且沒有人在場：planner 決定了，這一支照做。
所以它的形狀主要是關於**做到一半的時候**：

- **一個檔案一個工作單元**：建目錄 → `link()` → 寫帳本 → 事件，然後 commit（plan §3.2）。
  中途被關掉的話，磁碟上的鏈接與帳本最多差最後那一個檔案，而那一個由下一條規則補回來。
- **目標已經存在時比 inode**（plan §3.3）：與來源同一個 inode 是「上次鏈接了、帳本還沒寫」，
  補上帳本就好；不同就是媒體庫裡本來就有別人的檔案，Berth 不覆寫它（brief §5.3），整筆停在
  review。判定交給 `link()` 自己丟的 `FileExistsError`，不先 `exists()` 再鏈接——那樣兩步之間
  有一條縫，而且守衛會被繞過：先查存在的話，媒體庫外面的檔案也會被「認領」進帳本。
- **失敗分兩種**：正片鏈接不成是 `import_failed`，重試從沒做完的接著做；一條字幕或一個特典
  鏈接不成只記在那一列上——那一集仍然看得了，整季擋下來換不到任何東西。
- **通知 Jellyfin 在狀態落地之後**，失敗只記事件（plan §3.3）：檔案已經在媒體庫裡了，
  Jellyfin 自己的排程掃描遲早看得到它們。反查 item 是 `services/resolver.py` 的事。
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import fs
from berth.adapters.http import ServiceError
from berth.domain import (
    EventType,
    JellyfinRequest,
    JobState,
    PlanAction,
    PlanStatus,
    PlanSummary,
    ReviewReason,
)
from berth.models import JellyfinSettings, Job, JobFile, LedgerEntry, Plan, PlanItem, Route
from berth.models.types import utcnow
from berth.services.clients import ServiceClientFactory
from berth.services.events import EventHub, JobSignal
from berth.services.jobs import actor_of, guarded, record_event, transition
from berth.services.plan import WRITTEN, plan_counts
from berth.services.resolver import first_resolve_at
from berth.services.settings import read_settings
from berth.services.steps import message

logger = logging.getLogger(__name__)

#: 目標路徑上已經有一個不是 Berth 鏈接的檔案（CONTEXT.md 的 Unmanaged、plan §3.3）。
#: 存在那一列 `plan_items.error` 上。
UNMANAGED_TARGET = "target_unmanaged"

#: 鏈接不成也不擋整筆入庫的處置。正片不在裡面：少了它，那一集就是不在。
SKIPPABLE: frozenset[PlanAction] = frozenset({PlanAction.EXTRA, PlanAction.SUBTITLE})


@dataclass(frozen=True, slots=True)
class ImportOutcome:
    """一輪的結果。log 與測試看它。"""

    imported: int
    failed: int
    #: 停在 review 的（目標上有別人的檔案）。
    held: int


async def sweep_imports(
    session: AsyncSession,
    factory: ServiceClientFactory,
    hub: EventHub,
    *,
    now: datetime | None = None,
) -> ImportOutcome:
    """一輪：把 `importing` 的 Job 一筆一筆做完（plan §3.2 的 `importer`）。

    **一次一筆，依序不併發**：同一個作品資料夾可能同時是兩筆 Job 的目標（同一季的兩個版本），
    併發時「目標已經存在」的判定會讀到對方做到一半的樣子。
    """
    moment = now or utcnow()
    landed: Counter[JobState] = Counter()
    for job_hash in await _importable(session):
        state = await guarded(
            session, job_hash, _import(session, factory, hub, job_hash, moment), fallback=None
        )
        if state is not None:
            landed[state] += 1
    return ImportOutcome(
        imported=landed[JobState.IMPORTED],
        failed=landed[JobState.IMPORT_FAILED],
        held=landed[JobState.REVIEW],
    )


async def _importable(session: AsyncSession) -> list[str]:
    rows = await session.scalars(
        select(Job.hash).where(Job.state == JobState.IMPORTING).order_by(Job.added_at, Job.hash)
    )
    return list(rows)


async def _import(
    session: AsyncSession,
    factory: ServiceClientFactory,
    hub: EventHub,
    job_hash: str,
    now: datetime,
) -> JobState | None:
    """一筆 Job：逐檔放進去，再照結果落地（plan §3.1）。"""
    job = await session.get(Job, job_hash)
    if job is None or job.state is not JobState.IMPORTING:
        return None
    plan = await session.scalar(select(Plan).where(Plan.job_hash == job.hash))
    route = await session.get(Route, job.route_id) if job.route_id is not None else None
    if plan is None or route is None:
        # 走得到 `importing` 的 Job 一定有這兩樣；少了就是有人在中間刪掉了 Route。
        return await _fail(session, hub, job, plan, "this job has no import plan or route any more")

    # 守衛的根是**每一條** Route 的目標（plan §8.6）：寫進媒體庫的東西一定在某個 Route 底下。
    roots = [Path(row.target_path) for row in await session.scalars(select(Route))]
    sources = {
        row.id: row
        for row in await session.scalars(select(JobFile).where(JobFile.job_hash == job.hash))
    }
    pending = list(
        await session.scalars(
            select(PlanItem)
            .where(
                PlanItem.plan_id == plan.id,
                PlanItem.action.in_(WRITTEN),
                PlanItem.applied_at.is_(None),
            )
            .order_by(PlanItem.id)
        )
    )
    for item in pending:
        source = sources.get(item.job_file_id) if item.job_file_id is not None else None
        await _place(session, job, route, item, source, roots, now)
        # 一個檔案一個工作單元：磁碟上已經多了一個鏈接，帳本要立刻跟上（brief §5.1）。
        await session.commit()

    fatal = next(
        (
            item.error
            for item in pending
            if item.error and item.error != UNMANAGED_TARGET and item.action not in SKIPPABLE
        ),
        "",
    )
    if fatal:
        return await _fail(session, hub, job, plan, fatal)
    if any(item.error == UNMANAGED_TARGET for item in pending):
        return await _hold(session, hub, job, plan)
    return await _finish(session, factory, hub, job, plan, now)


async def _place(
    session: AsyncSession,
    job: Job,
    route: Route,
    item: PlanItem,
    source_row: JobFile | None,
    roots: list[Path],
    now: datetime,
) -> None:
    """一個檔案：建目錄 → `link()` → 寫帳本 → 事件（plan §3.2）。結果寫在那一列 Plan Item 上。

    目標的字串以 POSIX 相接：它是容器裡的路徑，也就是 Jellyfin 回報 `Path` 的那個形狀，
    反查比的就是這一串字（`models/ledger.py`）。
    """
    target_text = str(PurePosixPath(route.target_path) / item.target_path)
    if source_row is None:
        await _link_failed(session, job, item, target_text, None, "no file of this job backs it")
        return
    source = fs.under(job.save_path, source_row.rel_path)
    target = Path(target_text)
    try:
        try:
            fs.link(source, target, roots=roots)
        except FileExistsError:
            if not fs.same_inode(source, target):
                item.error = UNMANAGED_TARGET
                logger.warning("another file sits at the target", extra={"target": target_text})
                return
            # 上一次鏈接了、帳本還沒寫就被關掉：視為已完成，下面補上帳本（plan §3.3）。
        source_facts, target_facts = fs.stat(source), fs.stat(target)
        if source_facts != target_facts:
            raise OSError(f"{source} and {target} are not the same inode after link()")
    except (OSError, fs.PathEscapeError) as exc:
        await _link_failed(
            session, job, item, target_text, getattr(exc, "errno", None), message(exc)
        )
        return

    known = await session.scalar(
        select(LedgerEntry.id).where(LedgerEntry.target_path == target_text)
    )
    if known is None:
        session.add(
            LedgerEntry(
                job_hash=job.hash,
                source_rel_path=source_row.rel_path,
                source_abs_path=str(source),
                source_inode=str(source_facts.inode),
                source_dev=str(source_facts.device),
                target_path=target_text,
                target_inode=str(target_facts.inode),
                media_id=item.media_id,
                season=item.season,
                episode_start=item.episode_start,
                episode_end=item.episode_end,
                tags_json=item.tags_json,
                plan_item_id=item.id,
                action=item.action,
                audit=item.audit,
                created_at=now,
                # 只有正片在 Jellyfin 裡是一個自己查得到的 item；字幕是串流、特典掛在作品底下。
                resolve_after=first_resolve_at(now) if item.action is PlanAction.IMPORT else None,
            )
        )
        await record_event(
            session,
            job,
            EventType.LINKED,
            actor=actor_of(None),
            payload={"file": item.rel_path, "target": target_text},
        )
        await _restate_versions(session, item, target_text, now)
    item.applied_at = now
    item.error = ""


async def _restate_versions(
    session: AsyncSession, item: PlanItem, target: str, now: datetime
) -> None:
    """同一個資料夾裡其他正片重新排一次反查（票 14b）。

    Jellyfin 12 的版本名是「去掉**各版本**檔名的共同前綴」剩下的部分，所以多一個版本會改掉
    同一集其他版本的名字：單獨一個時是整個檔名主幹，第二個進來之後兩個都縮短（2026-09-16 對
    12.1.0 實測）。帳本上先前那幾筆已經反查完、不再排程，不推它們一把就會停在舊名字，而畫面
    正是在多版本那一塊把它們並排（`services/inventory.py` 的 `_versions`）。
    """
    if item.action is not PlanAction.IMPORT or item.media_id is None:
        return
    folder = str(PurePosixPath(target).parent)
    siblings = await session.scalars(
        select(LedgerEntry).where(
            LedgerEntry.media_id == item.media_id,
            LedgerEntry.action == PlanAction.IMPORT,
            LedgerEntry.target_path != target,
            LedgerEntry.resolve_after.is_(None),
        )
    )
    for entry in siblings:
        if str(PurePosixPath(entry.target_path).parent) == folder:
            entry.resolve_attempts = 0
            entry.resolve_after = first_resolve_at(now)


async def _link_failed(
    session: AsyncSession,
    job: Job,
    item: PlanItem,
    target: str,
    code: int | None,
    detail: str,
) -> None:
    """原文不翻譯、`errno` 另外存：它們是「哪個容器少了哪個掛載」唯一的證據（plan §8.6）。"""
    item.error = detail
    await record_event(
        session,
        job,
        EventType.LINK_FAILED,
        actor=actor_of(None),
        payload={
            "file": item.rel_path,
            "target": target,
            "errno": code,
            "error": detail,
            # 擋不擋入庫在這裡判定：畫面照它決定要不要塗紅（DESIGN.md 的 The One Meaning Rule）。
            "blocking": item.action not in SKIPPABLE,
        },
    )
    logger.warning("link failed", extra={"target": target, "errno": code, "error": detail})


# --- 落地 ---------------------------------------------------------------


async def _finish(
    session: AsyncSession,
    factory: ServiceClientFactory,
    hub: EventHub,
    job: Job,
    plan: Plan,
    now: datetime,
) -> JobState | None:
    """`importing` → `imported`，然後才通知 Jellyfin（plan §3.1、§3.3）。"""
    if not await transition(session, job, JobState.IMPORTED, expected=JobState.IMPORTING):
        logger.warning("job moved on before it could be marked imported")
        await session.rollback()
        return None
    job.imported_at = now
    plan.status = PlanStatus.APPLIED
    await session.commit()
    # 推播在狀態落地之後、通知之前：畫面不必多等 Jellyfin 回應的那一段時間。
    _publish(hub, job)
    logger.info("job imported", extra={"state": job.state.value, "plan": plan.id})
    await _notify(session, factory, job)
    await session.commit()
    return job.state


async def _fail(
    session: AsyncSession, hub: EventHub, job: Job, plan: Plan | None, detail: str
) -> JobState | None:
    """`importing` → `import_failed`（plan §3.1）。逐檔的 `link_failed` 已經寫在時間線上了。"""
    if not await transition(
        session, job, JobState.IMPORT_FAILED, expected=JobState.IMPORTING, error=detail
    ):
        logger.warning("job moved on before it could be marked import_failed")
        await session.rollback()
        return None
    if plan is not None:
        plan.status = PlanStatus.FAILED
    await session.commit()
    _publish(hub, job)
    logger.warning("job import failed", extra={"state": job.state.value, "error": detail})
    return job.state


async def _hold(session: AsyncSession, hub: EventHub, job: Job, plan: Plan) -> JobState | None:
    """`importing` → `review`：目標上有別人的檔案（plan §3.3）。

    這一條轉換不在 plan §3.1 的表上，所以理由要說清楚：`review` 是「等人決定」唯一的站，
    而其餘不衝突的檔案已經鏈接進去了——人決定完之後重來一次，它們會被跳過。
    """
    if not await transition(session, job, JobState.REVIEW, expected=JobState.IMPORTING):
        logger.warning("job moved on before it could be held for review")
        await session.rollback()
        return None
    summary = PlanSummary.model_validate(plan.summary_json or {})
    plan.status = PlanStatus.PENDING_REVIEW
    plan.summary_json = summary.model_copy(
        update={"review_reason": ReviewReason.TARGET_EXISTS}
    ).model_dump(mode="json")
    await record_event(
        session,
        job,
        EventType.REVIEW_REQUIRED,
        actor=actor_of(None),
        payload=plan_counts(plan) | {"plan": plan.id, "reason": ReviewReason.TARGET_EXISTS.value},
    )
    await session.commit()
    _publish(hub, job)
    logger.warning("job held: a target is taken", extra={"state": job.state.value})
    return job.state


async def _notify(session: AsyncSession, factory: ServiceClientFactory, job: Job) -> None:
    """`POST /Library/Media/Updated`（plan §8.2）。**失敗只記事件**（plan §3.3）。

    通知的是這一筆 Job 在帳本裡的**每一條**目標，不只是這一輪鏈接的那幾個：重試時前一輪已經
    鏈接好的檔案，那時整筆還沒走到 `imported`，一次都沒通知過。
    """
    paths = list(
        await session.scalars(
            select(LedgerEntry.target_path)
            .where(LedgerEntry.job_hash == job.hash)
            .order_by(LedgerEntry.id)
        )
    )
    if not paths:
        return
    settings = await read_settings(session, JellyfinSettings)
    client = factory.jellyfin(settings.base_url, token=settings.api_key)
    try:
        await client.notify_paths(paths)
    except ServiceError as exc:
        await record_event(
            session,
            job,
            EventType.JELLYFIN_REQUEST_FAILED,
            actor=actor_of(None),
            payload={"request": JellyfinRequest.SCAN.value, "error": message(exc)},
        )
        logger.warning("jellyfin was not told about the import", extra={"error": message(exc)})
        return
    finally:
        await client.aclose()
    await record_event(
        session,
        job,
        EventType.JELLYFIN_SCAN_REQUESTED,
        actor=actor_of(None),
        payload={"count": len(paths), "paths": paths},
    )


def _publish(hub: EventHub, job: Job) -> None:
    """推播在 commit 之後（票 10 實跑抓到的那一條）。"""
    hub.publish(JobSignal(hash=job.hash, state=job.state, progress=job.progress))
