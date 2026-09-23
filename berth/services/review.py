"""Review Queue：一份清單、一列一件事（plan §6 review 群組、brief §6.5、M2 票 06）。

**這一支只回答「現在有哪幾件事在等管理員」**，不自己偵測任何東西：`audit` 來自帳本上的
旗標（importer 抄過去的），`issue` 來自 `services/issues`。票 07、08 把 `plan`、`unmatched`、
`duplicate` 三類填進來時，只多一個 `_Producer`，排序與上限不動。

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

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import fs
from berth.domain import (
    REVIEW_PRIORITY,
    AuditAction,
    AuditReason,
    EventType,
    IssueStatus,
    JobState,
    PlanStatus,
    PlanSummary,
    ReviewKind,
    ReviewReason,
    ReviewRefusal,
)
from berth.logs import job_context
from berth.models import Issue, Job, LedgerEntry, Media, Plan, PlanItem
from berth.services.deletion import remove_one, route_targets
from berth.services.issues import IssueView, list_issues
from berth.services.jobs import job_lock, record_event, transition

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
    #: 解析器為什麼給 medium（`plan_items.reasons_json`）。**英文原文，不翻譯**：它是給人判斷
    #: 對不對的證據，與 `detail` 同一個規矩。
    notes: tuple[str, ...]
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


ReviewRow = AuditRow | IssueRow


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
    """
    if entry.plan_item_id is None:
        return
    item = await session.get(PlanItem, entry.plan_item_id)
    if item is None:
        return
    item.audit = False
    if unapply:
        item.applied_at = None


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
        notes=tuple(item.reasons_json or ()) if item is not None else (),
    )


async def _count_issues(session: AsyncSession) -> int:
    return int(
        await session.scalar(select(func.count(Issue.id)).where(Issue.status == IssueStatus.OPEN))
        or 0
    )


async def _fetch_issues(session: AsyncSession, limit: int) -> list[IssueRow]:
    views = await list_issues(session, oldest_first=True, limit=limit)
    return [IssueRow(issue=view) for view in views]


_PRODUCERS: dict[ReviewKind, _Producer] = {
    ReviewKind.AUDIT: _Producer(count=_count_audits, fetch=_fetch_audits),
    ReviewKind.ISSUE: _Producer(count=_count_issues, fetch=_fetch_issues),
}
