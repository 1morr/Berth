"""Review Queue：一份清單、一列一件事（plan §6 review 群組、brief §6.5、M2 票 06）。

**這一支只回答「現在有哪幾件事在等管理員」**，不自己偵測任何東西：`plan` 是停在 review 的
那幾份 Plan（票 07），`audit` 來自帳本上的旗標（importer 抄過去的），`issue` 來自
`services/issues`；票 08 填進 `unmatched`（Job 那一份定案了的 Plan 裡對不到的檔案）與
`duplicate`（規劃時與帳本重複而被略過的那幾列，`plan_items.duplicate_of`）。各自一個
`_Producer`，排序與上限不動。Plan 的三支命令（逐列改、核准、拒絕）在
`services/plan_review.py`，rematch 在 `services/rematch.py`，重複版本的三顆在
`services/duplicates.py`。

排序是 plan §6 定的：**需要人動手的排前面**（`REVIEW_PRIORITY`），同一級之內舊的在前——
等得最久的那一件最該先看。**不分頁**：超過 `QUEUE_LIMIT` 列時回前面那幾列並帶 `total`，
那時候該修的是上游（一次掛載掉了、一條 Route 的 medium 規則太鬆），不是加一個分頁器。

audit 的兩顆按鈕也在這裡（CONTEXT.md 的 Audit）：

- **確認**只改旗標——`ledger.audit` 與那一列 Plan Item 的一起清，檔案不動。
- **撤銷**先拆那一條硬鏈接（與刪除範圍的 `unlink` 同一步，`deletion.remove_one`），**拆成了**
  才刪帳本那一列、把 Job 送回 `review`。反過來的話拆不掉的那一次會留下一個沒有帳本的
  媒體庫檔案——下一輪對帳的 `unmanaged_library_file`，而使用者以為已經撤銷了。

**撤銷不走 `delete_job` 本人**（票面寫「走 `delete_job` 的 `unlink` 旗標」）：`delete_job`
的單位是整筆下載、終點是 `removed`，而撤銷的單位是一個檔案、終點是 `review`。兩者共用的是
「拆一條鏈接」那一步與它的守衛（`remove_one`、`route_targets`），所以共用的就是那一步。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import fs
from berth.domain import (
    REMATCH_ACTIONS,
    REVIEW_PRIORITY,
    SETTLED_PLANS,
    AuditAction,
    AuditReason,
    DuplicateDecision,
    DuplicateReason,
    EventType,
    FileKind,
    IssueStatus,
    ItemReason,
    JobState,
    MediaKind,
    PlanAction,
    PlanDecision,
    PlanStatus,
    PlanSummary,
    ReviewKind,
    ReviewReason,
    ReviewRefusal,
    UnmatchedReason,
)
from berth.domain import ReasonCode as Code
from berth.logs import job_context
from berth.models import Issue, Job, JobFile, LedgerEntry, Media, Plan, PlanItem
from berth.services.deletion import remove_one, route_targets
from berth.services.issues import IssueView, list_issues
from berth.services.jobs import job_lock, record_event, transition
from berth.services.plan_view import reasons_of

logger = logging.getLogger(__name__)

#: 佇列最多回幾列（plan §6）。超過就回前面這幾列並帶 `total`。
QUEUE_LIMIT = 200

#: 撤銷之後 Job 可以回 `review` 的那幾種狀態。其餘（`removed`，或下載還在跑的那幾種）
#: 不動它的狀態：`removed` 的那一筆已經被人決定過了，而還沒下載完的那一筆不會有 audit。
_RETURNS_TO_REVIEW = frozenset({JobState.IMPORTED, JobState.IMPORT_FAILED, JobState.REVIEW})


class ReviewRejectedError(Exception):
    """按不下去，而且**還沒動任何東西**（`domain.ReviewRefusal`）。"""

    def __init__(self, reason: ReviewRefusal, detail: str) -> None:
        super().__init__(f"{reason.value}: {detail}")
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True, slots=True)
class AuditRow:
    """一個 medium 自動入庫、等人看一眼的檔案。指向它的是帳本那一列。"""

    ledger_id: int
    #: 入庫的那一刻——它從那時起就在等人看。
    at: datetime
    media_id: str | None
    #: 作品名的兩輪（brief §7.5），沒有作品時都是空字串。
    title: str
    title_en: str
    job_hash: str
    job_name: str
    target_path: str
    source_path: str
    season: int | None
    episode_start: int | None
    episode_end: int | None
    #: 解析器為什麼給 medium（那一列 Plan Item 的理由，code + 參數，畫面翻譯）。
    reasons: tuple[ItemReason, ...]
    reason: AuditReason = AuditReason.MEDIUM_AUTO_IMPORTED
    actions: tuple[AuditAction, ...] = (AuditAction.CONFIRM, AuditAction.UNDO)

    @property
    def kind(self) -> ReviewKind:
        return ReviewKind.AUDIT


@dataclass(frozen=True, slots=True)
class IssueRow:
    """一件還開著的 Issue。**就是 `/issues` 的那一列**，按鈕由 `services/issues` 算。"""

    issue: IssueView

    @property
    def kind(self) -> ReviewKind:
        return ReviewKind.ISSUE


@dataclass(frozen=True, slots=True)
class PlanRow:
    """一份停在 review 的 Plan（M2 票 07）。逐列的內容由 `GET /plans/{id}` 另外給——一包 39 個
    檔案的逐列理由塞進佇列的每一列，佇列本身就讀不動了。"""

    plan_id: int
    #: 這一份算出來的那一刻。重新規劃會換掉它，所以它說的是「這一份」等了多久。
    at: datetime
    media_id: str | None
    title: str
    title_en: str
    job_hash: str
    job_name: str
    reason: ReviewReason
    summary: PlanSummary
    actions: tuple[PlanDecision, ...] = (PlanDecision.APPROVE, PlanDecision.REJECT)

    @property
    def kind(self) -> ReviewKind:
        return ReviewKind.PLAN


@dataclass(frozen=True, slots=True)
class UnmatchedRow:
    """一個對不到、留在 complete 原位的檔案（brief §7.4）。指向它的是 `job_files` 那一列——
    `POST /files/rematch` 的 `job_file_id`，與 Media 詳情的 Unmatched 區打同一支。"""

    job_file_id: int
    #: 它開始等人的那一刻：那一份 Plan 算出來的時間。
    at: datetime
    media_id: str | None
    #: 劇集或電影：劇集的指派要季集，電影的「指派」就是入庫。沒有作品時是 `None`。
    media_kind: MediaKind | None
    title: str
    title_en: str
    job_hash: str
    job_name: str
    #: 相對 `jobs.save_path`（與 `job_files.rel_path` 同形）。
    rel_path: str
    #: complete 裡的完整路徑。
    source_path: str
    file_kind: FileKind
    #: 解析器為什麼對不到（那一列 Plan Item 的理由）。
    reasons: tuple[ItemReason, ...]
    #: 改得成哪幾種（`REMATCH_ACTIONS`，依分類）：影片是指派 / 標記 extra / 忽略，字幕只能忽略。
    actions: tuple[PlanAction, ...]
    reason: UnmatchedReason = UnmatchedReason.LEFT_IN_PLACE

    @property
    def kind(self) -> ReviewKind:
        return ReviewKind.UNMATCHED


@dataclass(frozen=True, slots=True)
class DuplicateRow:
    """規劃時與帳本重複而被略過的一個檔案（brief §7.8）。指向它的是 Job 那一份 Plan 的那一列。"""

    item_id: int
    at: datetime
    media_id: str | None
    title: str
    title_en: str
    job_hash: str
    job_name: str
    #: 新的那一份：來源與它蓋到的集。
    rel_path: str
    source_path: str
    season: int | None
    episode_start: int | None
    episode_end: int | None
    reason: DuplicateReason
    #: 媒體庫裡已經有的那一份（帳本那一列）。
    known_path: str
    known_season: int | None
    known_episode_start: int | None
    known_episode_end: int | None
    actions: tuple[DuplicateDecision, ...] = (
        DuplicateDecision.REPLACE,
        DuplicateDecision.KEEP_BOTH,
        DuplicateDecision.SKIP,
    )

    @property
    def kind(self) -> ReviewKind:
        return ReviewKind.DUPLICATE


ReviewRow = PlanRow | AuditRow | UnmatchedRow | DuplicateRow | IssueRow


@dataclass(frozen=True, slots=True)
class ReviewQueue:
    """佇列本身。`total` 是全部幾件，`rows` 最多 `QUEUE_LIMIT` 列。"""

    rows: list[ReviewRow]
    total: int


@dataclass(frozen=True, slots=True)
class _Producer:
    """一類的列：數得出有幾件，也拿得出最舊的前 N 件。"""

    count: Callable[[AsyncSession], Awaitable[int]]
    fetch: Callable[[AsyncSession, int], Awaitable[Sequence[ReviewRow]]]


async def review_queue(session: AsyncSession, *, limit: int = QUEUE_LIMIT) -> ReviewQueue:
    """整份佇列，排好、截好（plan §6）。

    **逐類問，不是全部拿回來再排**：一次掛載掉了會讓整個媒體庫變成 Issue，而截掉的那幾千列
    不該先整份讀進記憶體。所以每一類先數、再照「還剩幾格」拿最舊的那幾列——類與類之間的
    順序本來就是固定的（`REVIEW_PRIORITY`），只有類內要排。
    """
    rows: list[ReviewRow] = []
    total = 0
    for kind in sorted(_PRODUCERS, key=lambda kind: REVIEW_PRIORITY[kind]):
        producer = _PRODUCERS[kind]
        total += await producer.count(session)
        room = limit - len(rows)
        if room > 0:
            rows.extend(await producer.fetch(session, room))
    return ReviewQueue(rows=rows, total=total)


async def confirm_audit(session: AsyncSession, ledger_id: int, *, actor: str) -> None:
    """「它是對的」：兩處旗標一起清，時間線寫一筆 `audit_confirmed`。檔案不動。"""
    async with _deciding(session, ledger_id) as (entry, job):
        entry.audit = False
        await _clear_item(session, entry, unapply=False)
        if job is not None:
            await record_event(
                session,
                job,
                EventType.AUDIT_CONFIRMED,
                actor=actor,
                payload={"ledger": entry.id, "target": entry.target_path},
            )
        await session.commit()
    logger.info("audit confirmed", extra={"ledger": ledger_id})


async def undo_audit(session: AsyncSession, ledger_id: int, *, actor: str) -> None:
    """「它是錯的」：拆鏈接 → 刪帳本那一列 → Job 回 `review`（CONTEXT.md 的 Audit）。"""
    async with _deciding(session, ledger_id) as (entry, job):
        await _undo(session, entry, job, actor=actor)


@asynccontextmanager
async def _deciding(
    session: AsyncSession, ledger_id: int
) -> AsyncIterator[tuple[LedgerEntry, Job | None]]:
    """確認與撤銷共用的入口：**鎖住那一筆 Job，在鎖裡讀那一列**。

    兩個分頁同時按同一列（一個確認、一個撤銷，或兩個都確認）時，後到的那一個要讀到先到的
    結果，得到 `ledger_missing` / `not_audited`——不是 500，也不是兩個都成立、時間線上寫出
    兩筆互相矛盾的事件（code-review 抓到，`TestTwoTabs`）。importer 的重試也寫這一列帳本
    與這一份 Plan，所以鎖的是 Job。鎖外那一次讀只為了知道是哪一筆 Job；鎖裡那一次
    （`populate_existing`）才是算數的。
    """
    job_hash = (await _audited(session, ledger_id)).job_hash
    if job_hash is None:
        # 重新入庫建出來的帳本沒有 Job（`models/ledger.py`），沒有鎖可拿，也沒有時間線可寫。
        yield await _audited(session, ledger_id), None
        return
    with job_context(job_hash):
        async with job_lock(job_hash):
            entry = await _audited(session, ledger_id)
            yield entry, await session.get(Job, job_hash)


async def _undo(session: AsyncSession, entry: LedgerEntry, job: Job | None, *, actor: str) -> None:
    target = Path(entry.target_path)
    try:
        unlinked = remove_one(target, roots=await route_targets(session))
    except (OSError, fs.PathEscapeError) as exc:
        # **拆不掉就什麼都不改**：帳本那一列還在，佇列上它也還在，旁邊多一句為什麼。
        raise ReviewRejectedError(ReviewRefusal.UNLINK_FAILED, str(exc)) from exc

    await _clear_item(session, entry, unapply=True)
    await session.delete(entry)
    if job is not None:
        await _back_to_review(session, job)
        await record_event(
            session,
            job,
            EventType.AUDIT_UNDONE,
            actor=actor,
            payload={"ledger": entry.id, "target": entry.target_path, "unlinked": unlinked},
        )
    await session.commit()
    logger.info("audit undone", extra={"ledger": entry.id, "unlinked": unlinked})


async def _back_to_review(session: AsyncSession, job: Job) -> None:
    """Job 回 `review`，它的 Plan 回 `pending_review` 並說出為什麼（`audit_undone`）。

    CAS 的 `expected` 是讀進來的那個狀態，理由同 `deletion._record`：鏈接已經拆了，輸掉的那
    一次只記一行 log。`review` → `review` 是刻意的——同一筆撤銷第二個檔案時，理由要換成
    這一次的。
    """
    if job.state not in _RETURNS_TO_REVIEW:
        return
    if not await transition(session, job, JobState.REVIEW, expected=job.state):
        logger.warning("job moved on before it could go back to review")
        return
    plan = await session.scalar(select(Plan).where(Plan.job_hash == job.hash))
    if plan is None:
        return
    summary = PlanSummary.model_validate(plan.summary_json or {})
    plan.status = PlanStatus.PENDING_REVIEW
    plan.summary_json = summary.model_copy(
        update={"review_reason": ReviewReason.AUDIT_UNDONE}
    ).model_dump(mode="json")


async def _clear_item(session: AsyncSession, entry: LedgerEntry, *, unapply: bool) -> None:
    """那一列 Plan Item 的 `audit` 跟著清（兩處旗標是同一件事，CONTEXT.md）。

    撤銷時連 `applied_at` 一起清：那個檔案已經不在媒體庫裡了，Plan 上不該再說它套用過——
    下載列表那一列的「N 個待確認」數的也是這一格。

    **那一列同時回到「沒有提案」**（`review`、季集與路徑清空，M2 票 07 code-review）：撤銷說的是
    「這一集不對」，而核准是照提案入庫——提案留著的話，原樣按一次核准就把剛拆掉的鏈接鏈回同一條
    路徑（`ReviewReason.AUDIT_UNDONE`：下一步是改季集或駁回，不是再點一次頭）。解析器當時的理由
    留著，那是它為什麼這樣猜的證據。
    """
    if entry.plan_item_id is None:
        return
    item = await session.get(PlanItem, entry.plan_item_id)
    if item is None:
        return
    item.audit = False
    if unapply:
        item.applied_at = None
        item.action = PlanAction.REVIEW
        item.season = item.episode_start = item.episode_end = None
        item.target_path = ""


async def _audited(session: AsyncSession, ledger_id: int) -> LedgerEntry:
    entry = await session.get(LedgerEntry, ledger_id, populate_existing=True)
    if entry is None:
        raise ReviewRejectedError(ReviewRefusal.LEDGER_MISSING, str(ledger_id))
    if not entry.audit:
        raise ReviewRejectedError(ReviewRefusal.NOT_AUDITED, str(ledger_id))
    return entry


# --- 各類的列 -------------------------------------------------------------


async def _count_audits(session: AsyncSession) -> int:
    return int(
        await session.scalar(select(func.count(LedgerEntry.id)).where(LedgerEntry.audit)) or 0
    )


async def _fetch_audits(session: AsyncSession, limit: int) -> list[AuditRow]:
    """最舊的 `limit` 個 audit，連同作品、Job 與那一列 Plan Item 一次問完。"""
    found = (
        await session.execute(
            select(LedgerEntry, Media, Job, PlanItem)
            .outerjoin(Media, Media.id == LedgerEntry.media_id)
            .outerjoin(Job, Job.hash == LedgerEntry.job_hash)
            .outerjoin(PlanItem, PlanItem.id == LedgerEntry.plan_item_id)
            .where(LedgerEntry.audit)
            .order_by(LedgerEntry.created_at, LedgerEntry.id)
            .limit(limit)
        )
    ).tuples()
    return [_audit_row(*row) for row in found]


def _audit_row(
    entry: LedgerEntry, media: Media | None, job: Job | None, item: PlanItem | None
) -> AuditRow:
    """外連接的三格都可能是 `None`：作品被刪、Job 被清掉、Plan 重新規劃過（`SET NULL`）。"""
    return AuditRow(
        ledger_id=entry.id,
        at=entry.created_at,
        media_id=entry.media_id,
        title=media.snapshot().title if media is not None else "",
        title_en=media.title_en if media is not None else "",
        job_hash=entry.job_hash or "",
        job_name=job.name if job is not None else "",
        target_path=entry.target_path,
        source_path=entry.source_abs_path,
        season=entry.season,
        episode_start=entry.episode_start,
        episode_end=entry.episode_end,
        reasons=reasons_of(item) if item is not None else (),
    )


def _held_plans() -> Select[tuple[Plan, Job, Media]]:
    """停在 review 的 Plan：Plan 在等人、**那筆 Job 也還在 `review`**。

    Media 是外連接，可能是 `None`（型別照 SQLAlchemy 的推導寫，讀的那一端當可空處理）。

    兩件事都要成立：`importing` 途中停下來的那一刻 Plan 先變 `pending_review`，Job 的轉換在
    同一個交易裡，但只看其中一邊的話，一份被重新規劃換掉之前的舊狀態也會被算進來。
    """
    return (
        select(Plan, Job, Media)
        .join(Job, Job.hash == Plan.job_hash)
        .outerjoin(Media, Media.id == Job.media_id)
        .where(Plan.status == PlanStatus.PENDING_REVIEW, Job.state == JobState.REVIEW)
    )


async def _count_plans(session: AsyncSession) -> int:
    counted = select(func.count()).select_from(_held_plans().subquery())
    return int(await session.scalar(counted) or 0)


async def _fetch_plans(session: AsyncSession, limit: int) -> list[PlanRow]:
    found = await session.execute(_held_plans().order_by(Plan.created_at, Plan.id).limit(limit))
    return [_plan_row(*row) for row in found.tuples()]


def _plan_row(plan: Plan, job: Job, media: Media | None) -> PlanRow:
    summary = PlanSummary.model_validate(plan.summary_json or {})
    return PlanRow(
        plan_id=plan.id,
        at=plan.created_at,
        media_id=job.media_id,
        title=media.snapshot().title if media is not None else "",
        title_en=media.title_en if media is not None else "",
        job_hash=job.hash,
        job_name=job.name,
        # 停在 review 的 Plan 一定帶著理由；舊資料沒有時退回最常見的那一種。
        reason=summary.review_reason or ReviewReason.LOW_CONFIDENCE,
        summary=summary,
    )


async def _count_issues(session: AsyncSession) -> int:
    return int(
        await session.scalar(select(func.count(Issue.id)).where(Issue.status == IssueStatus.OPEN))
        or 0
    )


async def _fetch_issues(session: AsyncSession, limit: int) -> list[IssueRow]:
    views = await list_issues(session, oldest_first=True, limit=limit)
    return [IssueRow(issue=view) for view in views]


def _unmatched() -> Select[tuple[PlanItem, Plan, Job, JobFile, Media]]:
    """Job 那一份**定案了**的 Plan 裡對不到的檔案（`SETTLED_PLANS`：預估與等審核的那幾份裡，它們是
    Plan 編輯的一列）。下載被刪掉（`removed`）的那幾筆不算：檔案多半已經不在了。

    **光碟結構不列**：整包光碟的每一個檔案都是 `disc`（brief §6.2），一包 BDMV 會把佇列塞滿幾百列
    而它們只能忽略——第一階段不拆光碟。它們仍在 Media 詳情的 Unmatched 區。
    """
    return (
        select(PlanItem, Plan, Job, JobFile, Media)
        .join(Plan, Plan.id == PlanItem.plan_id)
        .join(Job, Job.hash == Plan.job_hash)
        .join(JobFile, JobFile.id == PlanItem.job_file_id)
        .outerjoin(Media, Media.id == Job.media_id)
        .where(
            PlanItem.action == PlanAction.UNMATCHED,
            Plan.status.in_(SETTLED_PLANS),
            Job.state != JobState.REMOVED,
            or_(JobFile.kind.is_(None), JobFile.kind != FileKind.DISC),
        )
    )


async def _count_unmatched(session: AsyncSession) -> int:
    counted = select(func.count()).select_from(_unmatched().subquery())
    return int(await session.scalar(counted) or 0)


async def _fetch_unmatched(session: AsyncSession, limit: int) -> list[UnmatchedRow]:
    found = await session.execute(_unmatched().order_by(Plan.created_at, PlanItem.id).limit(limit))
    return [_unmatched_row(*row) for row in found.tuples()]


def _unmatched_row(
    item: PlanItem, plan: Plan, job: Job, row: JobFile, media: Media | None
) -> UnmatchedRow:
    kind = row.kind or FileKind.OTHER
    return UnmatchedRow(
        job_file_id=row.id,
        at=plan.created_at,
        media_id=job.media_id,
        media_kind=media.kind if media is not None else None,
        title=media.snapshot().title if media is not None else "",
        title_en=media.title_en if media is not None else "",
        job_hash=job.hash,
        job_name=job.name,
        rel_path=row.rel_path,
        source_path=str(fs.under(job.save_path, row.rel_path)),
        file_kind=kind,
        reasons=reasons_of(item),
        actions=REMATCH_ACTIONS[kind],
    )


def _duplicates() -> Select[tuple[PlanItem, Plan, Job, LedgerEntry, Media]]:
    """規劃時被略過、還沒有人決定的重複版本（`plan_items.duplicate_of`）。範圍同 `_unmatched`。"""
    return (
        select(PlanItem, Plan, Job, LedgerEntry, Media)
        .join(Plan, Plan.id == PlanItem.plan_id)
        .join(Job, Job.hash == Plan.job_hash)
        .join(LedgerEntry, LedgerEntry.id == PlanItem.duplicate_of)
        .outerjoin(Media, Media.id == Job.media_id)
        .where(
            PlanItem.action == PlanAction.SKIP,
            Plan.status.in_(SETTLED_PLANS),
            Job.state != JobState.REMOVED,
        )
    )


async def _count_duplicates(session: AsyncSession) -> int:
    counted = select(func.count()).select_from(_duplicates().subquery())
    return int(await session.scalar(counted) or 0)


async def _fetch_duplicates(session: AsyncSession, limit: int) -> list[DuplicateRow]:
    found = await session.execute(_duplicates().order_by(Plan.created_at, PlanItem.id).limit(limit))
    rows = list(found.tuples())
    files = {
        file.id: file
        for file in await session.scalars(
            select(JobFile).where(
                JobFile.id.in_([item.job_file_id for item, *_ in rows if item.job_file_id])
            )
        )
    }
    return [_duplicate_row(*row, files) for row in rows]


def _duplicate_row(
    item: PlanItem,
    plan: Plan,
    job: Job,
    known: LedgerEntry,
    media: Media | None,
    files: dict[int, JobFile],
) -> DuplicateRow:
    source = files.get(item.job_file_id) if item.job_file_id is not None else None
    rel = source.rel_path if source is not None else item.rel_path
    clash = any(reason.code is Code.LIBRARY_SPAN_CLASH for reason in reasons_of(item))
    return DuplicateRow(
        item_id=item.id,
        at=plan.created_at,
        media_id=job.media_id,
        title=media.snapshot().title if media is not None else "",
        title_en=media.title_en if media is not None else "",
        job_hash=job.hash,
        job_name=job.name,
        rel_path=rel,
        source_path=str(fs.under(job.save_path, rel)),
        season=item.season,
        episode_start=item.episode_start,
        episode_end=item.episode_end,
        reason=DuplicateReason.SPAN_CLASH if clash else DuplicateReason.SAME_VERSION,
        known_path=known.target_path,
        known_season=known.season,
        known_episode_start=known.episode_start,
        known_episode_end=known.episode_end,
    )


_PRODUCERS: dict[ReviewKind, _Producer] = {
    ReviewKind.PLAN: _Producer(count=_count_plans, fetch=_fetch_plans),
    ReviewKind.UNMATCHED: _Producer(count=_count_unmatched, fetch=_fetch_unmatched),
    ReviewKind.AUDIT: _Producer(count=_count_audits, fetch=_fetch_audits),
    ReviewKind.DUPLICATE: _Producer(count=_count_duplicates, fetch=_fetch_duplicates),
    ReviewKind.ISSUE: _Producer(count=_count_issues, fetch=_fetch_issues),
}
