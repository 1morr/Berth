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
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import fs
from berth.adapters.http import ServiceError
from berth.domain import (
    EventType,
    IssueStatus,
    IssueType,
    JellyfinRequest,
    JobState,
    LedgerStatus,
    PlanAction,
    PlanStatus,
    PlanSummary,
    ReviewReason,
)
from berth.models import (
    Issue,
    JellyfinSettings,
    Job,
    JobFile,
    LedgerEntry,
    Plan,
    PlanItem,
    Route,
)
from berth.models.types import utcnow
from berth.services.clients import ServiceClientFactory
from berth.services.deletion import Placed, remove_one
from berth.services.events import EventHub, JobSignal
from berth.services.jobs import actor_of, guarded, record_event, transition
from berth.services.plan import WRITTEN, plan_counts
from berth.services.resolve_schedule import first_resolve_at
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
    # 只拿來決定帳本要不要重寫，不拿來決定要不要鏈接（那一步交給 `link()` 自己丟的例外）。
    existed = Path(target_text).exists()
    try:
        facts = link_into(source, Path(target_text), roots=roots)
    except TargetTakenError:
        item.error = UNMANAGED_TARGET
        logger.warning("another file sits at the target", extra={"target": target_text})
        return
    except (OSError, fs.PathEscapeError) as exc:
        await _link_failed(
            session, job, item, target_text, getattr(exc, "errno", None), message(exc)
        )
        return

    entry, stale = await _ledger_rows(session, job.hash, source_row.rel_path, target_text)
    moved_from = [Path(row.target_path) for row in stale]
    if entry is not None and entry.target_path != target_text:
        moved_from.append(Path(entry.target_path))
    if (
        entry is None
        or not existed
        or not _current(entry, job.hash, source_row.rel_path, target_text)
    ):
        if entry is None:
            entry = LedgerEntry()
            session.add(entry)
        record_link(
            entry,
            job_hash=job.hash,
            source_rel_path=source_row.rel_path,
            source=source,
            target=target_text,
            facts=facts,
            item=item,
            now=now,
        )
        await record_event(
            session,
            job,
            EventType.LINKED,
            actor=actor_of(None),
            payload={"file": item.rel_path, "target": target_text},
        )
        await restate_versions(session, item, target_text, now)
    # 新長的那一列要 flush 過才有 id；它身上不會有 Issue，但一份清單比兩種情況好讀。
    await session.flush()
    healed = [entry.id, *(row.id for row in stale)]
    for row in stale:
        await session.delete(row)
    for old in moved_from:
        _take_back_old(old, source, roots)
    await _close(
        session,
        Issue.type.in_(HEALED_BY_LINKING) & Issue.ledger_id.in_(healed),
        now,
    )
    item.applied_at = now
    item.error = ""


#: 說的是帳本某一列那一條鏈接的幾種。importer 剛以來源的硬鏈接把那一列接回來（或確認它本來
#: 就是）時，三件都不再是事實：鏈接在、來源在、兩邊同一個 inode。不收的話刪了媒體庫再重新入庫
#: 之後 `/issues` 還掛著一整排按什麼都沒有結果的「鏈接遺失」。以 `ledger_id` 認而不是路徑：
#: 集名改了、那一列換到新路徑時，舊路徑上那一件說的也是同一列（M2 票 10）。
HEALED_BY_LINKING = (
    IssueType.LIBRARY_LINK_MISSING,
    IssueType.SOURCE_MISSING,
    IssueType.INODE_MISMATCH,
)


async def _close(session: AsyncSession, which: ColumnElement[bool], now: datetime) -> None:
    """條件自己解除的那幾件由系統收掉（`resolved_by = system`，同健康檢查那兩種）。"""
    for row in await session.scalars(select(Issue).where(Issue.status == IssueStatus.OPEN, which)):
        row.status = IssueStatus.RESOLVED
        row.resolved_at = now
        row.resolved_by = actor_of(None)
        logger.info("issue cleared", extra={"issue": row.type.value, "subject": row.subject})


async def _ledger_rows(
    session: AsyncSession, job_hash: str, source_rel_path: str, target: str
) -> tuple[LedgerEntry | None, list[LedgerEntry]]:
    """這一條鏈接在帳本上該是哪一列，以及同一個來源還指著別處、該收掉的舊列。

    **帳本以來源冪等**（brief §9.3）：同一個來源重新入庫一次還是同一列。只以目標路徑認的話，
    TMDB 在兩次之間改了集名就會多長一列，而舊的那條鏈接留在媒體庫裡變成同一集的第二個版本。
    目標路徑上已經有一列時仍然用它（`target_path` 是 unique，plan §3.3）——那是重新規劃看到
    自己上一輪的鏈接，或 `rebuild-ledger` 長回來、還沒掛上 Job 的那一列。
    """
    at_target = await session.scalar(select(LedgerEntry).where(LedgerEntry.target_path == target))
    elsewhere = list(
        await session.scalars(
            select(LedgerEntry)
            .where(
                LedgerEntry.job_hash == job_hash,
                LedgerEntry.source_rel_path == source_rel_path,
                LedgerEntry.target_path != target,
            )
            .order_by(LedgerEntry.id)
        )
    )
    if at_target is None and elsewhere:
        return elsewhere[0], elsewhere[1:]
    return at_target, elsewhere


def _current(entry: LedgerEntry, job_hash: str, source_rel_path: str, target: str) -> bool:
    """帳本那一列已經說的是這一條鏈接的現況。是的話（而且鏈接本來就在）什麼都不改——上一次
    反查到的 Jellyfin item 還算數，重寫一次只會讓 `jellyfin_resolver` 從頭再找一遍。

    鏈接是這一次才新建的就不算現況，即使帳本還說 `ok`：媒體庫被刪掉而對帳還沒跑過的那一刻正是
    這樣，而那個檔案在 Jellyfin 裡已經消失過一次，要重新反查、時間線也要記得它被鏈接回來。"""
    return (
        entry.status is LedgerStatus.OK
        and entry.job_hash == job_hash
        and entry.source_rel_path == source_rel_path
        and entry.target_path == target
    )


def _take_back_old(old: Path, source: Path, roots: Sequence[Path]) -> None:
    """同一個來源換了落點之後，收掉舊的那一條。**只收自己的**：與來源同一個 inode 才是 Berth
    鏈出去的那一條；別的檔案（使用者放回去的一份複製品）不碰，下一輪對帳會把它列出來。

    收不掉只留一行 log：新的那一條已經在了，這一集看得到；舊的那一條下一輪對帳是
    `unmanaged_library_file`，而那一種永遠不自動刪（brief §9.1）。
    """
    try:
        remove_one(old, roots=roots, placed=Placed.sharing(source))
    except (OSError, fs.PathEscapeError) as exc:
        logger.warning(
            "the old link was left in place", extra={"target": str(old), "error": message(exc)}
        )


class TargetTakenError(Exception):
    """目標路徑上已經有一個**別的**檔案（inode 不同，plan §3.3）。Berth 不覆寫它（brief §5.3）。"""


def link_into(
    source: Path, target: Path, *, roots: Sequence[Path]
) -> tuple[fs.PathFacts, fs.PathFacts]:
    """把一個來源鏈接到媒體庫的一條路徑，回兩邊的 `stat`（importer 與 rematch 共用，M2 票 08）。

    目標已經存在時比 inode：同一個 inode 是「上次鏈接了、帳本還沒寫」，視為已完成（plan §3.3）；
    不同就丟 `TargetTakenError`。判定交給 `link()` 自己丟的 `FileExistsError`，不先 `exists()`
    再鏈接——那樣兩步之間有一條縫，而且守衛會被繞過。其餘失敗（`OSError`、
    `fs.PathEscapeError`）原樣往上丟：原文是「哪個掛載少了」唯一的證據。
    """
    try:
        fs.link(source, target, roots=roots)
    except FileExistsError:
        if not fs.same_inode(source, target):
            raise TargetTakenError(str(target)) from None
    source_facts, target_facts = fs.stat(source), fs.stat(target)
    if source_facts != target_facts:
        raise OSError(f"{source} and {target} are not the same inode after link()")
    return source_facts, target_facts


def record_link(
    entry: LedgerEntry,
    *,
    job_hash: str | None,
    source_rel_path: str,
    source: Path,
    target: str,
    facts: tuple[fs.PathFacts, fs.PathFacts],
    item: PlanItem,
    now: datetime,
) -> None:
    """帳本那一列說出「這一條鏈接現在是什麼」（importer 寫新的一列，rematch 改寫既有的一列）。

    **Jellyfin 那幾格一起歸零**：換了來源或換了路徑，上一次反查到的 item 就不再是它——只有正片在
    Jellyfin 裡是一個自己查得到的 item，字幕是串流、特典掛在作品底下，所以只有正片排反查。
    """
    source_facts, target_facts = facts
    entry.job_hash = job_hash
    entry.source_rel_path = source_rel_path
    entry.source_abs_path = str(source)
    entry.source_inode = str(source_facts.inode)
    entry.source_dev = str(source_facts.device)
    entry.target_path = target
    entry.target_inode = str(target_facts.inode)
    entry.media_id = item.media_id
    entry.season = item.season
    entry.episode_start = item.episode_start
    entry.episode_end = item.episode_end
    entry.tags_json = item.tags_json
    entry.plan_item_id = item.id
    entry.action = item.action
    entry.audit = item.audit
    entry.status = LedgerStatus.OK
    entry.created_at = now
    entry.jellyfin_item_id = ""
    entry.jellyfin_series_id = ""
    entry.jellyfin_version_name = ""
    entry.resolve_attempts = 0
    entry.resolve_after = first_resolve_at(now) if item.action is PlanAction.IMPORT else None


async def restate_versions(
    session: AsyncSession, item: PlanItem, target: str, now: datetime
) -> None:
    """同一集的其他版本重新排一次反查（票 14b；M4 票 02 從「同一個資料夾」縮到同一集）。

    Jellyfin 12 的版本名是「去掉**各版本**檔名的共同前綴」剩下的部分，所以多一個版本會改掉
    同一集其他版本的名字：單獨一個時是整個檔名主幹，第二個進來之後兩個都縮短（2026-09-16 對
    12.1.0 實測）。帳本上先前那幾筆已經反查完、不再排程，不推它們一把就會停在舊名字，而畫面
    正是在多版本那一塊把它們並排（`services/inventory.py` 的 `_versions`）。

    **範圍是 Jellyfin 的版本分組**：同一個資料夾、同一季、集號範圍重疊；電影沒有季集，同一個
    資料夾就是同一部。以前是整個資料夾——一季每入庫一集就把前面每一集重反查一次，而且每次都
    撞在新檔案觸發的重掃上（2026-09-26 試跑）。
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
        if str(PurePosixPath(entry.target_path).parent) == folder and _same_episode(entry, item):
            entry.resolve_attempts = 0
            entry.resolve_after = first_resolve_at(now)


def _same_episode(entry: LedgerEntry, item: PlanItem) -> bool:
    """同一季、集號範圍重疊。沒有集號的（電影）只看資料夾。"""
    if item.episode_start is None or entry.episode_start is None:
        return item.episode_start is None and entry.episode_start is None
    if entry.season != item.season:
        return False
    ours = (item.episode_start, item.episode_end or item.episode_start)
    theirs = (entry.episode_start, entry.episode_end or entry.episode_start)
    return ours[0] <= theirs[1] and theirs[0] <= ours[1]


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
    # 帳本清掉之後對帳開的 `job_without_files`：這一輪長回了至少一列，它說的就不再是事實。
    # 這一輪一列都沒寫的（全是重複、全是略過）不收——那一件仍然可能是對的。
    grown = select(LedgerEntry.id).where(LedgerEntry.job_hash == job.hash).limit(1)
    if await session.scalar(grown) is not None:
        await _close(
            session,
            (Issue.type == IssueType.JOB_WITHOUT_FILES) & (Issue.subject == job.hash),
            now,
        )
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
    """通知的是這一筆 Job 在帳本裡的**每一條**目標，不只是這一輪鏈接的那幾個：重試時前一輪已經
    鏈接好的檔案，那時整筆還沒走到 `imported`，一次都沒通知過。
    """
    paths = list(
        await session.scalars(
            select(LedgerEntry.target_path)
            .where(LedgerEntry.job_hash == job.hash)
            .order_by(LedgerEntry.id)
        )
    )
    await notify_jellyfin(session, factory, job, paths)


async def notify_jellyfin(
    session: AsyncSession, factory: ServiceClientFactory, job: Job | None, paths: Sequence[str]
) -> None:
    """`POST /Library/Media/Updated`（plan §8.2）。**失敗只記事件**（plan §3.3）。

    rematch 也走它（M2 票 08），連同**拆掉的**那幾條：Jellyfin 對每一條路徑一律
    `ReportFileSystemChanged`，不看 `UpdateType`（brief §20.1），所以一條已經不在的路徑一樣會讓它
    重讀那個資料夾。沒有 Job 的時候（重新入庫的帳本）照樣通知，只是沒有時間線可寫。
    """
    if not paths:
        return
    settings = await read_settings(session, JellyfinSettings)
    client = factory.jellyfin(settings.base_url, token=settings.api_key)
    try:
        await client.notify_paths(paths)
    except ServiceError as exc:
        if job is not None:
            await record_event(
                session,
                job,
                EventType.JELLYFIN_REQUEST_FAILED,
                actor=actor_of(None),
                payload={"request": JellyfinRequest.SCAN.value, "error": message(exc)},
            )
        logger.warning("jellyfin was not told about the change", extra={"error": message(exc)})
        return
    finally:
        await client.aclose()
    if job is not None:
        await record_event(
            session,
            job,
            EventType.JELLYFIN_SCAN_REQUESTED,
            actor=actor_of(None),
            payload={"count": len(paths), "paths": list(paths)},
        )


def _publish(hub: EventHub, job: Job) -> None:
    """推播在 commit 之後（票 10 實跑抓到的那一條）。"""
    hub.publish(JobSignal(hash=job.hash, state=job.state, progress=job.progress))
