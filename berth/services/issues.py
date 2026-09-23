"""Issue 的載體與它的按鈕（plan §2.4、§6 issues 群組、brief §9.1、M2 票 05 / 09）。

三件事在這裡：**寫下一件**（`record_issue`，冪等）、**攤給畫面**（`list_issues`）、
**按下去**（`resolve_issue` / `ignore_issue`）。偵測本身不在這裡——對帳在
`services/reconcile.py`，管線那四種在 `services/downloads.py` 與 `services/resolver.py`，
健康檢查那兩種在 `services/health_issues.py`，它們都只呼叫 `record_issue`。

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

**按下去之前再確認一次世界**：偵測與按下去之間隔了一段時間（每日 04:00 那一輪開的，使用者
下午才看到）。會刪東西的那幾顆在動手之前重問一次它們依據的那件事——那個目錄仍然沒人認領、
那一份複製品仍然與來源一樣大——而不是照著早上的 `detail_json` 做。
"""

from __future__ import annotations

import logging
from collections.abc import Coroutine, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, assert_never

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import fs
from berth.adapters.http import ServiceError
from berth.adapters.jellyfin import scan_libraries
from berth.domain import (
    ISSUE_ACTIONS,
    NEEDS_MEDIA,
    EventType,
    IssueAction,
    IssueRefusal,
    IssueStatus,
    IssueType,
    JobRefusal,
    JobState,
    LedgerStatus,
)
from berth.models import (
    Issue,
    JellyfinSettings,
    Job,
    JobFile,
    LedgerEntry,
    QbittorrentSettings,
    Route,
    subject_of,
)
from berth.models.types import utcnow
from berth.parser import parse_release
from berth.services import claims, complete
from berth.services.clients import ServiceClientFactory
from berth.services.deletion import DeleteScope, delete_job
from berth.services.hints import JobHints
from berth.services.jobs import (
    JobRejectedError,
    job_lock,
    record_event,
    resubmit_job,
    transition,
)
from berth.services.qbittorrent import sign_in
from berth.services.settings import read_settings
from berth.services.steps import message

logger = logging.getLogger(__name__)


class IssueRejectedError(Exception):
    """按不下去，而且**還沒動任何東西**（`domain.IssueRefusal`）。

    `relink_failed` 是一個例外：鏈接要真的碰了磁碟才知道成不成。那一次失敗沒有留下
    半個檔案（`fs.link` 自己保證），所以它仍然是「這一次什麼都沒改」。

    `resubmit_failed` 是另一個（票 09c）：送了才知道 qBittorrent 收不收，而不收的那一次 Job
    照送單的規矩落在 `submit_failed`。這一件仍然開著、再按一次就是再送一次。
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
    #: 選作品的搜尋框預填的字（`NEEDS_MEDIA` 那兩顆才有，其餘是空字串）。
    query: str


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


async def list_issues(
    session: AsyncSession, *, oldest_first: bool = False, limit: int | None = None
) -> list[IssueView]:
    """還沒有人決定的那幾件，預設最近偵測到的在前面。

    **只有 `open`**：這是一份工作清單，不是歷史。決定過的留在資料庫裡（`resolved_by` 與
    `detail_json.action` 說得出當時按了哪一顆），但它們不該再佔著使用者的注意力。

    `oldest_first` 與 `limit` 是 Review Queue 的（`services/review.py`）：那一份是「等得最久
    的先看」並且有上限，`/issues` 這一頁是「剛發生的先看」、不設上限。
    """
    order = (
        (Issue.detected_at, Issue.id)
        if oldest_first
        else (Issue.detected_at.desc(), Issue.id.desc())
    )
    rows = list(
        await session.scalars(
            select(Issue).where(Issue.status == IssueStatus.OPEN).order_by(*order).limit(limit)
        )
    )
    jobs = await _live_jobs(session, rows)
    return [_view(row, jobs) for row in rows]


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
    plans: JobHints | None = None,
    media: str = "",
) -> IssueView:
    """按下那一顆（brief §9.1 的「預設建議動作」那一欄）。

    `media` 只有認領類的兩顆要（`NEEDS_MEDIA`）：管理員選的那一部作品（`tv:<tmdb>`）。

    **做得到才記成 resolved**：重新鏈接失敗時那一筆仍然是 `open`，清單上還看得到它。
    反過來的話畫面會說「修好了」，而媒體庫裡什麼都沒變。

    `plans` 是規劃器的喚醒訊號（「重新規劃」與「重新入庫」用）。沒給也修得好：規劃器每 60 秒自己
    掃一次 `completed`（plan §3.2），給了只是早一點。
    """
    row = await _open_issue(session, issue_id)
    view = await _reread(session, row)
    if action not in view.actions:
        raise IssueRejectedError(
            IssueRefusal.ACTION_NOT_AVAILABLE,
            f"{row.type.value} cannot be resolved with {action.value} right now",
        )
    if action in NEEDS_MEDIA and not media:
        raise IssueRejectedError(IssueRefusal.MEDIA_REQUIRED, "pick the work this belongs to")

    if action is IssueAction.RELINK:
        await _relink(session, row)
    elif action is IssueAction.FORGET:
        await _forget(session, row)
    elif action is IssueAction.DELETE_COMPLETE:
        await _delete_complete(session, factory, row, actor=actor)
    elif action is IssueAction.MARK_SOURCELESS:
        await _mark_sourceless(session, row)
    elif action is IssueAction.REPLACE_WITH_LINK:
        await _replace_with_link(session, row)
    elif action is IssueAction.DELETE_ORPHAN:
        await _delete_orphan(session, factory, row)
    elif action is IssueAction.REPLAN:
        await _replan(session, row, actor=actor)
    elif action is IssueAction.RELOOK:
        await _relook(session, row)
    elif action is IssueAction.RESCAN:
        await _rescan(session, factory, row)
    elif action is IssueAction.RECHECK or action is IssueAction.RETRY:
        await _restart(session, factory, row, action, actor=actor)
    elif action is IssueAction.ACCEPT_LOSS or action is IssueAction.ACCEPT_REMOVAL:
        await _accept(session, factory, row, actor=actor)
    elif action is IssueAction.RESUBMIT:
        await _resubmit(session, factory, row, actor=actor)
    elif action is IssueAction.ADOPT:
        await _claimed(claims.reimport_folder(session, factory, Path(row.path), media, actor=actor))
    elif action is IssueAction.CLAIM_TORRENT:
        await _claimed(
            claims.claim_torrent(session, factory, row.job_hash or "", media, actor=actor)
        )
    elif action is IssueAction.CLAIM_FILE:
        await _claim_file(session, factory, row, actor=actor)
    else:
        # 加一顆新的而沒有接到這裡，mypy 在這一行紅——不會靜靜跑到別顆的實作。
        assert_never(action)

    row.status = IssueStatus.RESOLVED
    row.resolved_at = utcnow()
    row.resolved_by = actor
    row.detail_json = {**(row.detail_json or {}), "action": action.value}
    await session.commit()
    if action in _WAKES_PLANNER and plans is not None:
        # commit 之後才叫醒：規劃器那一輪讀的是資料庫，早叫它只會看到還是 `imported` 的那一列。
        plans.nudge()
    logger.info(
        "issue resolved",
        extra={"issue_id": row.id, "issue": row.type.value, "action": action.value},
    )
    return await _reread(session, row)


# --- 按鈕 -------------------------------------------------------------


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


async def _mark_sourceless(session: AsyncSession, row: Issue) -> None:
    """標記為「已無來源」，library 檔保留（brief §9.1）。

    帳本那一列改成 `source_missing` 就是那個標記：對帳看到這一欄就不再為它開 Issue（同刪除
    範圍只勾「刪 complete 檔案」的結果，票 04）。媒體庫那一份一個位元組都不動——它現在是那份
    資料唯一的名字。
    """
    entry = await _entry_of(session, row)
    entry.status = LedgerStatus.SOURCE_MISSING
    await session.flush()


async def _replace_with_link(session: AsyncSession, row: Issue) -> None:
    """以硬鏈接取代：媒體庫裡那一份複製品換成來源的硬鏈接（brief §9.1）。

    **按下去那一刻重量一次大小**：偵測時一樣大、之後被轉碼覆蓋的那一份不能換掉——換掉等於
    丟掉別人的成品，而 `detail_json.same_size` 是偵測那一刻的事。換的那一步走
    `fs.replace_link`（票 08）：同一個名字一步換過去，失敗時舊的不動。
    """
    entry = await _entry_of(session, row)
    source, target = Path(entry.source_abs_path), Path(entry.target_path)
    try:
        origin = fs.stat(source)
    except OSError as exc:
        raise IssueRejectedError(IssueRefusal.SOURCE_MISSING, message(exc)) from exc
    try:
        placed = fs.stat(target)
    except OSError as exc:
        # 媒體庫那一份也不見了：這件事已經變成 `library_link_missing`，下一輪對帳會那樣開。
        raise IssueRejectedError(IssueRefusal.ACTION_NOT_AVAILABLE, message(exc)) from exc
    if (origin.device, origin.inode) != (placed.device, placed.inode):
        if origin.size != placed.size:
            raise IssueRejectedError(
                IssueRefusal.SIZE_DIFFERS,
                f"{target} is {placed.size} bytes and its source is {origin.size}",
            )
        roots = [Path(value) for value in await session.scalars(select(Route.target_path))]
        try:
            fs.replace_link(source, target, roots=roots)
        except (OSError, fs.PathEscapeError) as exc:
            raise IssueRejectedError(IssueRefusal.RELINK_FAILED, message(exc)) from exc
    entry.source_inode = str(origin.inode)
    entry.source_dev = str(origin.device)
    entry.target_inode = str(fs.stat(target).inode)
    entry.status = LedgerStatus.OK
    await session.flush()


async def _delete_orphan(session: AsyncSession, factory: ServiceClientFactory, row: Issue) -> None:
    """刪掉 complete 裡那個沒人認領的目錄（brief §9.1）。

    **動手之前重問一次它有沒有主**（`services/complete.claimed`，與對帳同一份判準）：偵測之後
    有人在 qBittorrent 上把它加回來做種的話，刪下去就是刪掉正在做種的資料。問不到
    qBittorrent 就不刪——那一刻答不出它有沒有主。
    """
    path = Path(row.path)
    folders = await complete.route_folders(session)
    settings = await read_settings(session, QbittorrentSettings)
    client = factory.qbittorrent(settings.base_url)
    try:
        await sign_in(client, settings)
        torrents = await client.sync()
    except ServiceError as exc:
        raise IssueRejectedError(IssueRefusal.CLIENT_UNREACHABLE, message(exc)) from exc
    finally:
        await client.aclose()
    if fs.path_key(path) in await complete.claimed(session, torrents, folders):
        raise IssueRejectedError(IssueRefusal.IN_USE, str(path))
    try:
        fs.remove_tree(path, roots=folders)
    except fs.PathEscapeError as exc:
        # 那一條 Route 在這中間被刪掉了：這個目錄已經不在 Berth 管得到的地方。
        raise IssueRejectedError(IssueRefusal.ACTION_NOT_AVAILABLE, message(exc)) from exc
    except OSError as exc:
        raise IssueRejectedError(IssueRefusal.DELETE_FAILED, message(exc)) from exc


async def _replan(session: AsyncSession, row: Issue, *, actor: str) -> None:
    """重新規劃：Job 從 `imported` 退回 `completed`，規劃器照現在的檔案重算一份（brief §9.1）。

    **不經 `replan_job`**：那一支是 Job 頁上那一顆，只接 `completed` / `planning` / `review`
    （`REPLANNABLE`），而把 `imported` 加進去等於讓每一筆入庫完的 Job 都多一顆會重鏈一次的按鈕。
    這裡只做退回那一步；算與鏈是規劃器與 importer 照常的一輪（plan §3.1），帳本以來源冪等。

    時間線寫一筆 `retried`：它是事件去重的界線（plan §3.3），重算出來的 `plan_generated` 與
    第一次一字不差時才不會被吞掉。
    """
    job = await session.get(Job, row.job_hash) if row.job_hash else None
    if job is None:
        raise IssueRejectedError(IssueRefusal.ACTION_NOT_AVAILABLE, "the download is gone")
    async with job_lock(job.hash):
        linked = await session.scalar(
            select(LedgerEntry.id).where(LedgerEntry.job_hash == job.hash).limit(1)
        )
        if linked is not None or not await transition(
            session, job, JobState.COMPLETED, expected=JobState.IMPORTED
        ):
            # 另一個分頁先按了，或它自己已經動了（使用者在 Job 頁上刪了它、audit 撤銷）。
            raise IssueRejectedError(IssueRefusal.ACTION_NOT_AVAILABLE, job.state.value)
        await record_event(
            session,
            job,
            EventType.RETRIED,
            actor=actor,
            payload={"state": JobState.COMPLETED.value},
        )


async def _relook(session: AsyncSession, row: Issue) -> None:
    """重新反查：那一列重新排進 `jellyfin_resolver`，六次從頭算（plan §3.2）。

    排在**現在**而不是 30 秒後：使用者按下去多半是因為他剛在 Jellyfin 那邊修好了什麼。
    """
    entry = await _entry_of(session, row)
    entry.resolve_attempts = 0
    entry.resolve_after = utcnow()
    await session.flush()


async def _rescan(session: AsyncSession, factory: ServiceClientFactory, row: Issue) -> None:
    """先請 Jellyfin 跑「重新掃描媒體庫」，再重新反查（brief §20.1：路徑通知對從沒掃到過
    內容的媒體庫無效）。

    **Jellyfin 問不到就整顆不做**，那一列不重排——畫面上它還在，旁邊說為什麼。
    """
    entry = await _entry_of(session, row)
    settings = await read_settings(session, JellyfinSettings)
    client = factory.jellyfin(settings.base_url, token=settings.api_key)
    try:
        scanned = await scan_libraries(client)
    except ServiceError as exc:
        raise IssueRejectedError(IssueRefusal.JELLYFIN_UNREACHABLE, message(exc)) from exc
    finally:
        await client.aclose()
    if not scanned:
        raise IssueRejectedError(
            IssueRefusal.JELLYFIN_UNREACHABLE, "Jellyfin has no library scan task"
        )
    entry.resolve_attempts = 0
    entry.resolve_after = utcnow()
    await session.flush()


async def _restart(
    session: AsyncSession,
    factory: ServiceClientFactory,
    row: Issue,
    action: IssueAction,
    *,
    actor: str,
) -> None:
    """重新 recheck（`missing_files`）或重試（`client_error`）：請 qBittorrent 動手，Job 回到
    poller 接得住的那一站（plan §3.1）。

    **qBittorrent 那一半**（brief §20.2，2026-09-23 對 4.4.5 與 5.2.3 實測）：recheck 是重新校驗
    磁碟上的資料，`start`（4.x 的 `resume`）讓它重新開始，而重新開始本身就會清掉客戶端的錯誤
    （原始碼 `clear_error()`）。所以重試只送 `start`——錯誤不是資料的問題，重新校驗一次幾十 GB
    只是讓它晚一點回來。recheck 之後**一定接 `start`**：原始碼裡 5.x 對停住的 torrent recheck 完
    會再停下來；實測資料回來之後兩版都是做種中，資料不在的話兩版都是 `stalledDL`。

    **Job 那一半**：檔案清單早就到手的回 `metadata_ready`，還沒有的回 `submitted`——兩站的下一步
    poller 本來就會走（完成判定、等清單），這一顆不另外判斷 qBittorrent 校驗的結果。校驗完仍然
    缺檔的話，下一輪 poller 會照常再開一件（壞掉優先，plan §3.1）。

    **先問 qBittorrent 才動 Job**：問不到的話那一列一步都不動，這一件留著 `open`。
    """
    job = await _broken_job(session, row)
    async with job_lock(job.hash):
        broken = job.state
        settings = await read_settings(session, QbittorrentSettings)
        client = factory.qbittorrent(settings.base_url)
        try:
            await sign_in(client, settings)
            if action is IssueAction.RECHECK:
                await client.recheck(job.hash)
            await client.start(job.hash)
        except ServiceError as exc:
            raise IssueRejectedError(IssueRefusal.CLIENT_UNREACHABLE, message(exc)) from exc
        finally:
            await client.aclose()

        listed = await session.scalar(
            select(JobFile.id).where(JobFile.job_hash == job.hash).limit(1)
        )
        back = JobState.METADATA_READY if listed is not None else JobState.SUBMITTED
        if not await transition(session, job, back, expected=broken):
            raise IssueRejectedError(IssueRefusal.ACTION_NOT_AVAILABLE, job.state.value)
        # `retried` 是事件去重的界線（plan §3.3）：之後又壞一次時那一筆 `issue_detected` 與
        # 第一次一字不差，沒有界線會被吞掉。`action` 讓時間線分得出是哪一顆。
        await record_event(
            session,
            job,
            EventType.RETRIED,
            actor=actor,
            payload={"state": back.value, "action": action.value},
        )


async def _accept(
    session: AsyncSession, factory: ServiceClientFactory, row: Issue, *, actor: str
) -> None:
    """承認遺失 / 承認移除：那一筆下載到此為止（2026-09-23 使用者拍板）。

    **走 `delete_job`、四個旗標全不勾**：Job 進 `removed`、時間線一筆 `deleted`，磁碟與
    qBittorrent 一個位元組都不動（`ACTION_DELETES` 是 False）。要刪東西的人去 Job 頁的刪除範圍，
    那裡四個旗標逐一說清楚；這一顆只說「別再等它了」。torrent 還在 qBittorrent 上的話它仍然有
    Job，所以不會變成 `unknown_torrent`。
    """
    job = await _broken_job(session, row)
    try:
        await delete_job(session, factory, job.hash, DeleteScope(), actor=actor)
    except JobRejectedError as refusal:
        raise IssueRejectedError(_REFUSAL_OF[refusal.reason], refusal.detail) from refusal


async def _resubmit(
    session: AsyncSession, factory: ServiceClientFactory, row: Issue, *, actor: str
) -> None:
    """重新送單：照存下來的下載連結再加一次（`services/jobs.resubmit_job`）。

    **送了而 qBittorrent 不收**（409 / 415）時 Job 落在 `submit_failed`，這一件仍然開著：
    修好之後再按一次就是再送一次（所以 `submit_failed` 也在這一顆的 `_BROKEN_BY` 裡）。
    """
    job = await _broken_job(session, row)
    try:
        view = await resubmit_job(
            session, factory, job.hash, expected=_BROKEN_BY[IssueAction.RESUBMIT], actor=actor
        )
    except JobRejectedError as refusal:
        raise IssueRejectedError(_REFUSAL_OF[refusal.reason], refusal.detail) from refusal
    if view.state is JobState.SUBMIT_FAILED:
        raise IssueRejectedError(IssueRefusal.RESUBMIT_FAILED, view.error)


async def _claimed(work: Coroutine[Any, Any, Job]) -> None:
    """重新入庫（孤兒目錄）或認領 torrent：建一筆 Job，交給管線照常的一輪（`services/claims`）。

    兩顆都是「什麼都還沒動就拒絕」，說法直接是 `IssueRefusal`，這裡只換例外的型別。
    """
    try:
        await work
    except claims.ClaimRejectedError as refusal:
        raise IssueRejectedError(refusal.reason, refusal.detail) from refusal


async def _claim_file(
    session: AsyncSession, factory: ServiceClientFactory, row: Issue, *, actor: str
) -> None:
    """認領進帳本：單一檔案的 `rebuild-ledger`。配不上的拒絕，那一件照舊開著
    （brief §9.1「只列出」）。

    **不刪任何東西**：配得上的只是多一列帳本；配不上的連帳本都不寫。
    """
    try:
        await claims.claim_file(session, factory, Path(row.path), actor=actor)
    except claims.UnclaimedError as miss:
        raise IssueRejectedError(IssueRefusal.UNCLAIMABLE, miss.reason.value) from miss


async def _broken_job(session: AsyncSession, row: Issue) -> Job:
    job = await session.get(Job, row.job_hash) if row.job_hash else None
    if job is None:
        raise IssueRejectedError(IssueRefusal.ACTION_NOT_AVAILABLE, "the download is gone")
    return job


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

#: `delete_job` 與 `resubmit_job` 丟得出來的拒絕 → Issue 這一層的說法。**只列走得到的那幾種**：
#: 漏一種是一個帶著 repro 的 `KeyError`，而不是一句說錯了下一步的話。
#:
#: 刪除的四個旗標是按鈕自己寫死的，所以勾錯組合那一種走不到；Job 在按下去之前被刪掉或動過了
#: ＝這一顆現在按不了，qBittorrent 問不到＝去修那一台，Route 用不了＝送出去也入不了庫。
_REFUSAL_OF: dict[JobRefusal, IssueRefusal] = {
    JobRefusal.JOB_MISSING: IssueRefusal.ACTION_NOT_AVAILABLE,
    JobRefusal.NOT_RETRYABLE: IssueRefusal.ACTION_NOT_AVAILABLE,
    JobRefusal.CLIENT_UNREACHABLE: IssueRefusal.CLIENT_UNREACHABLE,
    JobRefusal.DELETE_FILES_REQUIRES_REMOVE_TORRENT: IssueRefusal.ACTION_NOT_AVAILABLE,
    JobRefusal.SOURCE_UNAVAILABLE: IssueRefusal.SOURCE_UNAVAILABLE,
    JobRefusal.ROUTE_MISSING: IssueRefusal.ROUTE_UNUSABLE,
    JobRefusal.ROUTE_DISABLED: IssueRefusal.ROUTE_UNUSABLE,
    JobRefusal.ROUTE_UNHEALTHY: IssueRefusal.ROUTE_UNUSABLE,
    JobRefusal.ROUTE_KIND_MISMATCH: IssueRefusal.ROUTE_UNUSABLE,
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
    return _view(row, await _live_jobs(session, [row]))


async def _live_jobs(session: AsyncSession, rows: Sequence[Issue]) -> dict[str, JobState]:
    """這幾列指著的 Job 裡還真的在的那幾個，各自現在是什麼狀態。

    一次問完而不是逐列 `session.get`：清單上兩百列就是兩百次查詢（票 01 才剛把 `list_jobs`
    的同一個毛病改掉）。狀態是管線那三種要的：Job 已經離開那個壞掉的狀態時它們的按鈕不畫。
    """
    hashes = {row.job_hash for row in rows if row.job_hash}
    if not hashes:
        return {}
    found = await session.execute(select(Job.hash, Job.state).where(Job.hash.in_(hashes)))
    return dict(found.tuples().all())


def _view(row: Issue, jobs: dict[str, JobState]) -> IssueView:
    actions = _actions(row, jobs.get(row.job_hash or ""))
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
        actions=actions,
        query=_query(row) if not NEEDS_MEDIA.isdisjoint(actions) else "",
    )


def _query(row: Issue) -> str:
    """選作品時搜尋框預填的字：torrent 名（`unknown_torrent`）或目錄名（`orphan_complete`）裡
    解析器讀出的標題，讀不出來就是那個名字本身。Berth 不替管理員選作品，只是不讓他從頭打。"""
    name = str((row.detail_json or {}).get("name") or "") or Path(row.path).name
    return next(iter(parse_release(name).title_candidates), name)


def _actions(row: Issue, job_state: JobState | None) -> tuple[IssueAction, ...]:
    """這一列**現在**按得了哪幾顆。

    型別決定有哪幾顆（`ISSUE_ACTIONS`），這一筆的資料決定其中哪幾顆按得下去：決定過的
    一顆都沒有，指不到帳本的按不了動帳本的那幾顆，沒有 Job 的按不了動 Job 的那幾顆，
    Job 已經離開那個壞掉狀態的管線 Issue 按不了它的按鈕（`_BROKEN_BY`），大小不同的
    `inode_mismatch` 沒有「以硬鏈接取代」。

    **在後端算而不是讓畫面猜**：按下去會被拒絕的按鈕不該畫出來。
    """
    if row.status is not IssueStatus.OPEN:
        return ()
    usable: list[IssueAction] = []
    for action in ISSUE_ACTIONS[row.type]:
        if action in _ON_THE_LEDGER_ROW and row.ledger_id is None:
            continue
        if action in _ON_THE_JOB and job_state is None:
            continue
        if action in _BROKEN_BY and job_state not in _BROKEN_BY[action]:
            continue
        # 「否則列出等人決定」（brief §9.1）：大小不同時不給這一顆。
        same_size = (row.detail_json or {}).get("same_size")
        if action is IssueAction.REPLACE_WITH_LINK and not same_size:
            continue
        usable.append(action)
    return tuple(usable)


#: 按完之後叫醒規劃器：這幾顆都把一筆 Job 放在 `completed`，接下來是規劃器的事。
_WAKES_PLANNER = frozenset({IssueAction.REPLAN, IssueAction.ADOPT})

#: 這幾顆動的是帳本那一列，指不到它就按不了。
_ON_THE_LEDGER_ROW = frozenset(
    {
        IssueAction.RELINK,
        IssueAction.FORGET,
        IssueAction.MARK_SOURCELESS,
        IssueAction.REPLACE_WITH_LINK,
        IssueAction.RELOOK,
        IssueAction.RESCAN,
    }
)
#: 這幾顆動的是那一筆 Job。帳本的 `job_hash` 是弱引用，重新入庫建出來的那幾列就沒有。
_ON_THE_JOB = frozenset(
    {
        IssueAction.DELETE_COMPLETE,
        IssueAction.REPLAN,
        IssueAction.RECHECK,
        IssueAction.ACCEPT_LOSS,
        IssueAction.RETRY,
        IssueAction.RESUBMIT,
        IssueAction.ACCEPT_REMOVAL,
    }
)
#: 管線那三種的按鈕只在 Job **還在那個壞掉的狀態**時按得了（plan §3.1 的出邊）。
#:
#: Job 自己往前走了（另一個分頁按過、Job 頁上重試成功、它被刪了）的話，那一件說的事已經不是
#: 現況，按下去會把一筆好好的下載拉回去。重新送單多收一個 `submit_failed`：上一次重新送單被
#: qBittorrent 拒絕的那一筆落在那裡，這一件仍然開著，再按一次就是再送一次。
_BROKEN_BY: dict[IssueAction, frozenset[JobState]] = {
    IssueAction.RECHECK: frozenset({JobState.MISSING_FILES}),
    IssueAction.ACCEPT_LOSS: frozenset({JobState.MISSING_FILES}),
    IssueAction.RETRY: frozenset({JobState.CLIENT_ERROR}),
    IssueAction.RESUBMIT: frozenset({JobState.CLIENT_REMOVED, JobState.SUBMIT_FAILED}),
    IssueAction.ACCEPT_REMOVAL: frozenset({JobState.CLIENT_REMOVED, JobState.SUBMIT_FAILED}),
}
