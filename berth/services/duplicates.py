"""重複版本的三顆：取代舊版、保留兩者、跳過（brief §7.8、M2 票 08）。

規劃時比帳本（`services/plan._against_ledger`）：新的一列與帳本上既有的一列重複時，自動模式略過它、
記下撞上的是哪一列（`plan_items.duplicate_of`）。這裡是人決定之後的那一步，**走 rematch 的同一條
路**（`services/rematch.land`：建新鏈接 → 拆舊鏈接 → 改帳本 → 通知掃描，一律經過 Plan）：

- **取代舊版**：新的那一份鏈到它該在的路徑，舊的那一條拆掉，**帳本那一列改指新的來源**。同一條
  路徑上的（同一集同一組 Tags）一步換過去（`fs.replace_link`），中間沒有一刻那一集不存在。舊版本
  的字幕一起拆，新版本的字幕跟著新影片進來。
- **保留兩者**：新的那一份也鏈進去。同一組 Tags 的檔名一模一樣，所以新的多一個序號標籤
  （`[2]`、`[3]`…，存在 `Tags.edition`，2026-09-23 使用者拍板）；Jellyfin 12 把它們當成同一集的
  兩個版本。起始集相同而結束集不同的那一種路徑本來就不同，照原樣鏈——畫面在按之前說清楚後果。
- **跳過**：什麼都不動，只是這一列不再等人。新的那一份留在 complete 原位。
"""

from __future__ import annotations

import logging
from pathlib import Path, PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import fs
from berth.domain import (
    SETTLED_PLANS,
    DuplicateDecision,
    EventType,
    FileKind,
    MediaSnapshot,
    PlanAction,
    RematchRefusal,
    Tags,
    why,
)
from berth.domain import PlanItem as PlannedFile
from berth.domain import ReasonCode as Code
from berth.models import Job, JobFile, LedgerEntry, Media, Plan, PlanItem, Route
from berth.parser import revise
from berth.services.clients import ServiceClientFactory
from berth.services.jobs import record_event
from berth.services.plan import follows
from berth.services.plan_view import dump_reasons, load_plan, reasons_of
from berth.services.rematch import (
    Landing,
    Move,
    RematchOutcome,
    RematchRejectedError,
    announce,
    claimant,
    full_path,
    land,
    locked,
    sidecars_of,
)

logger = logging.getLogger(__name__)

#: 「保留兩者」的序號最多試到幾號。到這裡還撞，就是有別的東西在佔那一排名字。
_MAX_SERIAL = 99


async def decide_duplicate(
    session: AsyncSession,
    factory: ServiceClientFactory,
    item_id: int,
    decision: DuplicateDecision,
    *,
    actor: str,
) -> RematchOutcome | None:
    """`POST /review/duplicate/{item_id}/{decision}`。跳過回 `None`，其餘回改完的樣子。"""
    item = await session.get(PlanItem, item_id)
    if item is None:
        raise RematchRejectedError(RematchRefusal.NOT_DUPLICATE, str(item_id))
    plan = await session.get(Plan, item.plan_id)
    known = (
        await session.get(LedgerEntry, item.duplicate_of) if item.duplicate_of is not None else None
    )
    # 兩把鎖：新的那一筆，與媒體庫裡那一份所屬的舊的那一筆（取代會改它的鏈接與帳本）。
    held = (plan.job_hash if plan is not None else None, known.job_hash if known else None)
    async with locked(*held):
        item, plan, job, known = await _waiting(session, item_id, held)
        if decision is DuplicateDecision.SKIP:
            await _skip(session, item, job, actor=actor)
            return None
        landing = await _landing(session, item, job, known, decision)
        outcome_plan = await land(session, landing, actor=actor)
        main = landing.moves[0]
        target = full_path(landing.root, main.planned)
        await record_event(
            session,
            job,
            EventType.DUPLICATE_DECIDED,
            actor=actor,
            payload={
                "decision": decision.value,
                "plan": outcome_plan.id,
                "file": main.source_rel,
                "target": target,
                "replaced": known.target_path if decision is DuplicateDecision.REPLACE else "",
            },
        )
        await session.commit()
    await announce(session, factory, landing)
    logger.info("duplicate decided", extra={"item": item_id, "decision": decision.value})
    return RematchOutcome(plan_id=outcome_plan.id, target_path=target)


async def _waiting(
    session: AsyncSession, item_id: int, held: tuple[str | None, ...]
) -> tuple[PlanItem, Plan, Job, LedgerEntry]:
    """在鎖裡重讀：這一列還是一個等人決定的重複版本嗎。另一個分頁先按了就是 `not_duplicate`。

    媒體庫那一份在拿鎖之前換了主人（另一個分頁剛取代過它）時也是：手上的鎖不是它那一筆的。
    """
    item = await session.get(PlanItem, item_id, populate_existing=True)
    plan = await session.get(Plan, item.plan_id, populate_existing=True) if item else None
    job = await session.get(Job, plan.job_hash) if plan and plan.job_hash else None
    known = (
        await session.get(LedgerEntry, item.duplicate_of, populate_existing=True)
        if item is not None and item.duplicate_of is not None
        else None
    )
    if (
        item is None
        or plan is None
        or job is None
        or known is None
        or item.action is not PlanAction.SKIP
        or plan.status not in SETTLED_PLANS
        or known.job_hash not in held
    ):
        raise RematchRejectedError(RematchRefusal.NOT_DUPLICATE, str(item_id))
    return item, plan, job, known


async def _skip(session: AsyncSession, item: PlanItem, job: Job, *, actor: str) -> None:
    """不要新的那一份：旗標清掉，理由多一條「人決定的」。檔案都不動。"""
    item.duplicate_of = None
    marked = why(Code.SET_BY_USER)
    reasons = reasons_of(item)
    item.reasons_json = dump_reasons(reasons if marked in reasons else (*reasons, marked))
    await record_event(
        session,
        job,
        EventType.DUPLICATE_DECIDED,
        actor=actor,
        payload={
            "decision": DuplicateDecision.SKIP.value,
            "file": item.rel_path,
            "target": "",
            "replaced": "",
        },
    )
    await session.commit()


async def _landing(
    session: AsyncSession,
    item: PlanItem,
    job: Job,
    known: LedgerEntry,
    decision: DuplicateDecision,
) -> Landing:
    """新的那一份（加上跟著它的字幕）要鏈到哪裡；取代時舊版本的字幕一起拆。"""
    media = await session.get(Media, job.media_id) if job.media_id is not None else None
    snapshot = media.stored_snapshot() if media is not None else None
    route = await session.get(Route, job.route_id) if job.route_id is not None else None
    if snapshot is None:
        raise RematchRejectedError(RematchRefusal.MEDIA_MISSING, item.rel_path)
    if route is None:
        raise RematchRejectedError(RematchRefusal.ROUTE_MISSING, item.rel_path)
    loaded = await load_plan(session, item.plan_id)
    assert loaded is not None  # 剛在鎖裡讀過這一列的 Plan
    index = next(i for i, row in enumerate(loaded.rows) if row.id == item.id)
    video = loaded.items[index].model_copy(
        update={
            "action": PlanAction.IMPORT,
            "reasons": (*loaded.items[index].reasons, why(Code.SET_BY_USER)),
        }
    )
    if decision is DuplicateDecision.KEEP_BOTH:
        video = await _beside(session, video, snapshot, route.target_path)
    # 跟著這個影片的字幕先改回「要掛」，再讓 `revise` 照新影片的路徑重算（與 Plan 編輯同一份規則）。
    items = [
        video
        if i == index
        else row.model_copy(update={"action": PlanAction.SUBTITLE})
        if row.kind is FileKind.SUBTITLE and follows(row) == video.rel_path
        else row
        for i, row in enumerate(loaded.items)
    ]
    revised = revise(items, snapshot, settled=loaded.settled)
    landing = Landing(job=job, media=snapshot, media_id=job.media_id, root=route.target_path)
    files = {
        row.id: row
        for row in await session.scalars(select(JobFile).where(JobFile.job_hash == job.hash))
    }
    replacing = decision is DuplicateDecision.REPLACE
    landing.moves.append(
        await _move(
            session, job, files, loaded.rows[index], revised[index], known if replacing else None
        )
    )
    olds = await sidecars_of(session, known) if replacing else []
    for i, row in enumerate(loaded.rows):
        follower = revised[i]
        if i == index or follower.kind is not FileKind.SUBTITLE:
            continue
        if follows(follower) != video.rel_path or follower.action is not PlanAction.SUBTITLE:
            continue
        full = str(PurePosixPath(route.target_path) / follower.target_path)
        # 同一條路徑上舊版本的字幕：一步換過去，而不是先拆再撞。
        old = next((entry for entry in olds if entry.target_path == full), None)
        if old is not None:
            olds.remove(old)
        landing.moves.append(await _move(session, job, files, row, follower, old))
    for entry in olds:
        landing.moves.append(await _dropped(session, entry, video))
    return landing


async def _move(
    session: AsyncSession,
    job: Job,
    files: dict[int, JobFile],
    row: PlanItem,
    planned_file: PlannedFile,
    old: LedgerEntry | None,
) -> Move:
    """新的那一份的一個檔案。它取代的是另一筆 Job 的鏈接時，那一筆的那一列要改成沒有落點。"""
    source = files.get(row.job_file_id) if row.job_file_id is not None else None
    rel = source.rel_path if source is not None else row.rel_path
    return Move(
        source=fs.under(job.save_path, rel),
        source_rel=rel,
        job_hash=job.hash,
        job_file_id=row.job_file_id,
        planned=planned_file.model_copy(update={"rel_path": rel}),
        old=old,
        mirror=row,
        displaced=(
            await claimant(session, old) if old is not None and old.job_hash != job.hash else None
        ),
    )


async def _dropped(session: AsyncSession, entry: LedgerEntry, video: PlannedFile) -> Move:
    """舊版本旁邊的一條字幕，拆掉。它屬於被取代的那一份，新影片旁邊掛的是新版本自己的字幕。"""
    return Move(
        source=Path(entry.source_abs_path),
        source_rel=entry.source_rel_path,
        job_hash=entry.job_hash,
        job_file_id=None,
        planned=PlannedFile(
            rel_path=entry.source_rel_path,
            kind=FileKind.SUBTITLE,
            action=PlanAction.SKIP,
            tags=Tags.model_validate(entry.tags_json or {}),
            confidence=video.confidence,
            reasons=(why(Code.SET_BY_USER),),
        ),
        old=entry,
        # 它那一筆 Job 的那一列跟著改成略過：那一條字幕已經不在媒體庫裡了。
        mirror=await claimant(session, entry),
    )


async def _beside(
    session: AsyncSession, video: PlannedFile, media: MediaSnapshot, root: str
) -> PlannedFile:
    """「保留兩者」：路徑被佔著的話，Tags 多一個序號（`[2]`、`[3]`…）直到空出來為止。

    起始集相同而結束集不同的那一種路徑本來就不同，第一輪就空著，不加序號。
    """
    base = video.tags
    candidate = video
    for serial in range(2, _MAX_SERIAL + 1):
        (landed,) = revise((candidate,), media)
        full = str(PurePosixPath(root) / landed.target_path)
        taken = await session.scalar(select(LedgerEntry.id).where(LedgerEntry.target_path == full))
        if taken is None and not Path(full).exists():
            return candidate
        edition = f"{base.edition} {serial}".strip()
        candidate = video.model_copy(update={"tags": base.model_copy(update={"edition": edition})})
    raise RematchRejectedError(RematchRefusal.TARGET_TAKEN, video.name)
