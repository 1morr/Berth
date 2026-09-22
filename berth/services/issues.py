"""Issue 的載體與它的三顆按鈕（plan §2.4、§6 issues 群組、brief §9.1、M2 票 05）。

三件事在這裡：**寫下一件**（`record_issue`，冪等）、**攤給畫面**（`list_issues`）、
**按下去**（`resolve_issue` / `ignore_issue`）。偵測本身不在這裡——對帳在
`services/reconcile.py`，管線那四種在 `services/downloads.py` 與 `services/resolver.py`，
它們都只呼叫 `record_issue`。

**冪等是這一支的全部重點**。`qbit_poller` 每 5 秒醒一次、對帳每天跑一輪，同一件事會被說很多
遍；清單上要是一件一列，不是一天一萬七千列。所以寫入是「同一個 `(type, subject)` 只有一筆
`open`，再偵測到就更新 `detail_json` 與 `detected_at`」，而 `subject` 依型別取（`SUBJECT_OF`）。

**先查再寫，沒有接 `IntegrityError`**：今天沒有兩個呼叫端寫同一種型別（對帳那一輪與管線各寫
各的，而對帳同時只有一輪），所以那條縫關不上也走不到。資料庫上的 partial unique index 是
backstop——真的撞上時它會是一個帶著 repro 的 500，而不是一筆悄悄重複的列。

**`ledger.status` 與 Issue 是同一件事的兩個角度**（plan §2.4）：帳本那一欄是這一列的現況，
Issue 是「要有人決定」的那一件。所以三顆按鈕都要把帳本那一欄收乾淨——修好了改回 `ok`，
承認刪除就把那一列刪掉。留著一列說 `target_missing` 的帳本，下一輪對帳會再開一筆同樣的
Issue，而使用者剛剛才決定過它。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import fs
from berth.domain import (
    ISSUE_ACTIONS,
    IssueAction,
    IssueRefusal,
    IssueStatus,
    IssueType,
    JobRefusal,
    LedgerStatus,
)
from berth.models import Issue, Job, LedgerEntry, Route, subject_of
from berth.models.types import utcnow
from berth.services.clients import ServiceClientFactory
from berth.services.deletion import DeleteScope, delete_job
from berth.services.jobs import JobRejectedError
from berth.services.steps import message

logger = logging.getLogger(__name__)


class IssueRejectedError(Exception):
    """按不下去，而且**還沒動任何東西**（`domain.IssueRefusal`）。

    `relink_failed` 是唯一的例外：鏈接要真的碰了磁碟才知道成不成。那一次失敗沒有留下
    半個檔案（`fs.link` 自己保證），所以它仍然是「這一次什麼都沒改」。
    """

    def __init__(self, reason: IssueRefusal, detail: str) -> None:
        super().__init__(f"{reason.value}: {detail}")
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True, slots=True)
class Recorded:
    """`record_issue` 做了什麼。

    **`opened` 是實際發生的事，不是推出來的**：呼叫端（對帳的那一輪）要報「這一輪開了幾件、
    更新了幾件」，而那個答案只有這裡知道。從別的狀態去猜會在「上一件被忽略過」那一格出錯
    ——那一列帳本仍然是 `target_missing`，但開出來的是**新的一筆**。
    """

    issue: Issue
    #: 這一次是新開的（`False` 代表更新了一筆本來就開著的）。
    opened: bool


@dataclass(frozen=True, slots=True)
class IssueView:
    """清單上的一列。**動作由後端算**，前端不重算一份（同 `JobOut.retryable`）。"""

    id: int
    type: IssueType
    subject: str
    job_hash: str
    ledger_id: int | None
    path: str
    detail: dict[str, Any]
    status: IssueStatus
    detected_at: datetime
    resolved_at: datetime | None
    resolved_by: str
    #: 這一列現在按得了哪幾顆，順序就是畫面上的順序。空的代表只剩「忽略」。
    actions: tuple[IssueAction, ...]


async def record_issue(
    session: AsyncSession,
    kind: IssueType,
    *,
    path: str = "",
    job_hash: str | None = None,
    ledger_id: int | None = None,
    detail: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> Recorded:
    """偵測到一件事。已經有一筆 `open` 的同一件事就更新它（plan §2.4 的冪等鍵）。

    **不 commit**：呼叫端多半在一個迴圈裡寫好幾筆，交易的邊界是它的事。
    """
    subject = subject_of(kind, path=path, job_hash=job_hash, ledger_id=ledger_id)
    if not subject:
        # 寫一筆沒有鍵的列的話，同型別的每一件事會互相覆蓋成一列。
        raise ValueError(f"{kind.value} needs the column its subject comes from")

    moment = now or utcnow()
    existing = await session.scalar(
        select(Issue).where(
            Issue.type == kind, Issue.subject == subject, Issue.status == IssueStatus.OPEN
        )
    )
    if existing is not None:
        # 「還在」與「又發生了一次」是同一件事：更新它說的內容與時間，不開第二筆。
        existing.detail_json = detail
        existing.detected_at = moment
        await session.flush()
        return Recorded(issue=existing, opened=False)

    row = Issue(
        type=kind,
        subject=subject,
        job_hash=job_hash,
        ledger_id=ledger_id,
        path=path,
        detail_json=detail,
        status=IssueStatus.OPEN,
        detected_at=moment,
    )
    session.add(row)
    await session.flush()
    logger.warning(
        "issue opened", extra={"issue": kind.value, "subject": subject, "issue_id": row.id}
    )
    return Recorded(issue=row, opened=True)


async def list_issues(session: AsyncSession) -> list[IssueView]:
    """還沒有人決定的那幾件，最近偵測到的在前面。

    **只有 `open`**：這是一份工作清單，不是歷史。決定過的留在資料庫裡（`resolved_by` 與
    `detail_json.action` 說得出當時按了哪一顆），但它們不該再佔著使用者的注意力。
    """
    rows = list(
        await session.scalars(
            select(Issue)
            .where(Issue.status == IssueStatus.OPEN)
            .order_by(Issue.detected_at.desc(), Issue.id.desc())
        )
    )
    jobs = await _live_jobs(session, rows)
    return [_view(row, has_job=row.job_hash in jobs) for row in rows]


async def ignore_issue(session: AsyncSession, issue_id: int, *, actor: str) -> IssueView:
    """「我知道了，不用管它」。不碰磁碟、不碰帳本。

    與 resolve 分開是因為它們對下一輪對帳的意思不同：ignore 之後那個檔案**仍然不在**，
    所以下一輪會再開一筆新的 Issue。這是刻意的——忽略的是「這一次不想處理」，不是
    「這件事不存在」。真的要它安靜下來，按的是「承認刪除並清帳本」。
    """
    row = await _open_issue(session, issue_id)
    row.status = IssueStatus.IGNORED
    row.resolved_at = utcnow()
    row.resolved_by = actor
    await session.commit()
    logger.info("issue ignored", extra={"issue_id": row.id, "issue": row.type.value})
    return await _reread(session, row)


async def resolve_issue(
    session: AsyncSession,
    factory: ServiceClientFactory,
    issue_id: int,
    action: IssueAction,
    *,
    actor: str,
) -> IssueView:
    """按下那一顆（brief §9.1 的「預設建議動作」那一欄）。

    **做得到才記成 resolved**：重新鏈接失敗時那一筆仍然是 `open`，清單上還看得到它。
    反過來的話畫面會說「修好了」，而媒體庫裡什麼都沒變。
    """
    row = await _open_issue(session, issue_id)
    view = await _reread(session, row)
    if action not in view.actions:
        raise IssueRejectedError(
            IssueRefusal.ACTION_NOT_AVAILABLE,
            f"{row.type.value} cannot be resolved with {action.value} right now",
        )

    if action is IssueAction.RELINK:
        await _relink(session, row)
    elif action is IssueAction.FORGET:
        await _forget(session, row)
    else:
        await _delete_complete(session, factory, row, actor=actor)

    row.status = IssueStatus.RESOLVED
    row.resolved_at = utcnow()
    row.resolved_by = actor
    row.detail_json = {**(row.detail_json or {}), "action": action.value}
    await session.commit()
    logger.info(
        "issue resolved",
        extra={"issue_id": row.id, "issue": row.type.value, "action": action.value},
    )
    return await _reread(session, row)


# --- 三顆按鈕 -----------------------------------------------------------


async def _relink(session: AsyncSession, row: Issue) -> None:
    """照帳本那一列再硬鏈接一次，帳本那一欄回 `ok`（brief §9.1）。

    走的是 `fs.link` 與 Route 的守衛——媒體庫裡的檔案只有這一條路徑放得進去（plan §8.6）。
    成了之後**重新量目標的 inode**：`target_inode` 記的是「當時鏈接出來的那一個」，新的
    鏈接是新的一次，照抄舊值會讓下一輪的 `inode_mismatch` 比到一個不存在的東西。
    """
    entry = await _entry_of(session, row)
    source = Path(entry.source_abs_path)
    try:
        facts = fs.stat(source)
    except OSError as exc:
        # 兩邊都沒有就不是鏈接的事：使用者要按的是另外兩顆。
        raise IssueRejectedError(IssueRefusal.SOURCE_MISSING, message(exc)) from exc

    target = Path(entry.target_path)
    roots = [Path(value) for value in await session.scalars(select(Route.target_path))]
    try:
        fs.link(source, target, roots=roots)
    except FileExistsError:
        # 這中間有人把它放回去了。同一個 inode 就是已經好了；不同就是別人的檔案，不覆寫。
        if not fs.same_inode(source, target):
            raise IssueRejectedError(
                IssueRefusal.RELINK_FAILED, f"another file already sits at {target}"
            ) from None
    except (OSError, fs.PathEscapeError) as exc:
        raise IssueRejectedError(IssueRefusal.RELINK_FAILED, message(exc)) from exc

    entry.source_inode = str(facts.inode)
    entry.source_dev = str(facts.device)
    entry.target_inode = str(fs.stat(target).inode)
    entry.status = LedgerStatus.OK
    await session.flush()


async def _forget(session: AsyncSession, row: Issue) -> None:
    """承認刪除並清帳本（brief §9.1）：那一列本來就不該再宣稱媒體庫裡有這個檔案。

    只刪帳本那一列，不碰 Job 也不碰 complete：來源還在的話它仍然是一份可以重新入庫的東西
    （brief §9.3），而這一顆說的只是「媒體庫裡沒有它，這樣就對了」。
    """
    entry = await session.get(LedgerEntry, row.ledger_id) if row.ledger_id is not None else None
    if entry is not None:
        await session.delete(entry)
    await session.flush()


async def _delete_complete(
    session: AsyncSession, factory: ServiceClientFactory, row: Issue, *, actor: str
) -> None:
    """連 complete 一起刪：這一筆下載整個不要了。

    **走 `delete_job` 的四個旗標**（plan §11.3 決定 4、票 04），不是另一套刪除。四個**全勾**，
    而這是整顆按鈕唯一需要解釋的地方：

    - 來源是一個 torrent，所以「刪掉 complete」本來就是整包的事——抽掉其中一個檔案只會讓
      qBittorrent 在下一次重新檢查時把它抓回來（brief §9.2）。
    - `unlink` 要勾，否則這一筆其餘還在媒體庫裡的檔案會變成沒有來源的孤兒（下一輪對帳的
      `unmanaged_library_file`）。
    - `purge` 要勾，否則帳本那幾列留著說「媒體庫裡該有這些檔案」，而下一輪對帳會照著它們
      再開一批 `library_link_missing`——使用者剛剛才決定過的那一件會自己回來。

    所以這一顆的文案要說清楚它的單位是**一筆下載**而不是一個檔案（`PRODUCT.md`、`/issues` 頁）。
    """
    if row.job_hash is None:
        raise IssueRejectedError(
            IssueRefusal.ACTION_NOT_AVAILABLE, "this entry is not attached to a download"
        )
    try:
        await delete_job(
            session,
            factory,
            row.job_hash,
            DeleteScope(unlink=True, remove_torrent=True, delete_files=True, purge=True),
            actor=actor,
        )
    except JobRejectedError as refusal:
        raise IssueRejectedError(_REFUSAL_OF[refusal.reason], refusal.detail) from refusal

    # 那一筆下載已經不在了，它底下其他等著人決定的事也不必決定了。
    await _close_siblings(session, row, actor=actor)


async def _close_siblings(session: AsyncSession, row: Issue, *, actor: str) -> None:
    """同一筆 Job 底下其餘還開著的 Issue 跟著收掉。

    沒有這一段的話它們會永遠停在 `open`：它們指著的帳本與 Job 都已經被 `purge` 刪掉了，
    按哪一顆都不會有結果，而清單上每一列都要是「按得了東西」的。
    """
    siblings = await session.scalars(
        select(Issue).where(
            Issue.job_hash == row.job_hash,
            Issue.status == IssueStatus.OPEN,
            Issue.id != row.id,
        )
    )
    for sibling in siblings:
        sibling.status = IssueStatus.RESOLVED
        sibling.resolved_at = utcnow()
        sibling.resolved_by = actor
        sibling.detail_json = {
            **(sibling.detail_json or {}),
            "action": IssueAction.DELETE_COMPLETE.value,
        }
    await session.flush()


# --- 內部 ---------------------------------------------------------------

#: `delete_job` 丟得出來的拒絕 → Issue 這一層的說法（`tests/unit/test_issue_types.py` 守著
#: 這張表涵蓋了那一顆按鈕真的走得到的每一種）。
#:
#: 四個旗標是這一顆自己寫死的，所以勾錯組合那一種走不到；其餘三種各自對得上一句話：
#: Job 在按下去之前被刪掉了＝這一顆現在按不了，qBittorrent 問不到＝去修那一台。
_REFUSAL_OF: dict[JobRefusal, IssueRefusal] = {
    JobRefusal.JOB_MISSING: IssueRefusal.ACTION_NOT_AVAILABLE,
    JobRefusal.CLIENT_UNREACHABLE: IssueRefusal.CLIENT_UNREACHABLE,
    JobRefusal.DELETE_FILES_REQUIRES_REMOVE_TORRENT: IssueRefusal.ACTION_NOT_AVAILABLE,
}


async def _entry_of(session: AsyncSession, row: Issue) -> LedgerEntry:
    entry = await session.get(LedgerEntry, row.ledger_id) if row.ledger_id is not None else None
    if entry is None:
        raise IssueRejectedError(
            IssueRefusal.ACTION_NOT_AVAILABLE, "this issue no longer points at a ledger entry"
        )
    return entry


async def _open_issue(session: AsyncSession, issue_id: int) -> Issue:
    row = await session.get(Issue, issue_id)
    if row is None:
        raise IssueRejectedError(IssueRefusal.ISSUE_MISSING, str(issue_id))
    if row.status is not IssueStatus.OPEN:
        # 多半是另一個分頁先按了。
        raise IssueRejectedError(IssueRefusal.ISSUE_NOT_OPEN, row.status.value)
    return row


async def _reread(session: AsyncSession, row: Issue) -> IssueView:
    jobs = await _live_jobs(session, [row])
    return _view(row, has_job=row.job_hash in jobs)


async def _live_jobs(session: AsyncSession, rows: Sequence[Issue]) -> set[str]:
    """這幾列指著的 Job 裡，還真的在的那幾個。

    一次問完而不是逐列 `session.get`：清單上兩百列就是兩百次查詢（票 01 才剛把 `list_jobs`
    的同一個毛病改掉）。
    """
    hashes = {row.job_hash for row in rows if row.job_hash}
    if not hashes:
        return set()
    return set(await session.scalars(select(Job.hash).where(Job.hash.in_(hashes))))


def _view(row: Issue, *, has_job: bool) -> IssueView:
    return IssueView(
        id=row.id,
        type=row.type,
        subject=row.subject,
        job_hash=row.job_hash or "",
        ledger_id=row.ledger_id,
        path=row.path,
        detail=row.detail_json or {},
        status=row.status,
        detected_at=row.detected_at,
        resolved_at=row.resolved_at,
        resolved_by=row.resolved_by,
        actions=_actions(row, has_job=has_job),
    )


def _actions(row: Issue, *, has_job: bool) -> tuple[IssueAction, ...]:
    """這一列**現在**按得了哪幾顆。

    型別決定有哪幾顆（`ISSUE_ACTIONS`），這一筆的資料決定其中哪幾顆按得下去：決定過的
    一顆都沒有，指不到帳本的按不了「重新鏈接」，沒有 Job 的按不了「連 complete 一起刪」
    （帳本的 `job_hash` 是弱引用，重新入庫建出來的那幾列就沒有）。

    **在後端算而不是讓畫面猜**：按下去會被拒絕的按鈕不該畫出來。
    """
    if row.status is not IssueStatus.OPEN:
        return ()
    offered = ISSUE_ACTIONS[row.type]
    usable: list[IssueAction] = []
    for action in offered:
        # 前兩顆都動帳本那一列，所以指不到它就都按不了。
        if action in (IssueAction.RELINK, IssueAction.FORGET) and row.ledger_id is None:
            continue
        if action is IssueAction.DELETE_COMPLETE and not has_job:
            continue
        usable.append(action)
    return tuple(usable)
