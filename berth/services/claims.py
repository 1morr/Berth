"""認領：Berth 不認得、但磁碟或 qBittorrent 上確實存在的東西，收回 Berth 管得到的地方（M2 票 10）。

對帳開出來的三種「沒有主」各有一顆認領（brief §9.1），**三顆都走既有的入庫路線**，不另開一條：

- `orphan_complete` 的「重新入庫」：complete 裡那個沒人認領的目錄建成一筆 `reimport` Job，停在
  `completed`，由規劃器與 importer 照常的一輪接手——與 `POST /jobs/{hash}/reimport` 同一個入口
  （`services/reimport.contents_on_disk`）。
- `unknown_torrent` 的「認領」：替 qBittorrent 上那一筆建 Job，停在 `submitted`（送單成功之後
  那一站），由 poller 照常往前推。
- `unmanaged_library_file` 的「認領進帳本」：單一檔案的 `rebuild-ledger`（`claim_file`）。

**前兩顆要帶作品**（2026-09-23 使用者拍板：管理員按下去時選）：沒有作品的 Job 進規劃器只會整份停在
review（`no_media`），而 Review Queue 核准不了它。第三顆不必——作品資料夾名自己說得出是哪一部，
說不出就是配不上。

**`claim_file` 從 library 的 inode 反查 complete**（plan §11.3 決定 9）：媒體庫裡一個帳本不認得的
檔案，如果 complete 裡有一個檔案與它同一個 inode，它就是硬鏈接過去的。然後照命名模板**反解**
它的路徑（`naming.read_target`）：季、集、Tags 都從那一條路徑讀回來，讀的方法是「重算一次、
一字不差才算」，所以長回來的那一列就是 importer 當時會寫下的那一列。**配不到的一筆都不猜**
（`ClaimMiss`）：猜錯的代價是帳本說某個檔案是第 3 集，而 Review Queue、重複判斷、刪除範圍都信它。

**三顆都不刪任何東西**（`ACTION_DELETES`）。**都不 commit**：呼叫端（`resolve_issue`、
`rebuild_ledger`）決定交易的邊界。
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import fs
from berth.adapters.http import ServiceError
from berth.domain import (
    ClaimMiss,
    EventType,
    IssueRefusal,
    IssueStatus,
    IssueType,
    JobState,
    JobTrigger,
    LedgerStatus,
    MediaKind,
    PlanAction,
    collection_type_for,
)
from berth.logs import job_context
from berth.models import (
    Issue,
    Job,
    JobFile,
    LedgerEntry,
    Media,
    PathSettings,
    QbittorrentSettings,
    Route,
)
from berth.models import media_id as build_media_id
from berth.models.ledger import HARDLINK
from berth.models.types import utcnow
from berth.naming import read_target
from berth.parser import kind_by_extension
from berth.services import complete
from berth.services.clients import ServiceClientFactory
from berth.services.jobs import JobRejectedError, check_route, freeze, record_event
from berth.services.media import read_media
from berth.services.qbittorrent import sign_in, unknown_torrents
from berth.services.reimport import contents_on_disk
from berth.services.resolve_schedule import first_resolve_at
from berth.services.routes import save_path_of
from berth.services.settings import read_settings
from berth.services.steps import message

logger = logging.getLogger(__name__)

#: 作品資料夾名結尾的 TMDB id（`naming.FOLDER_TEMPLATE`）。
_TMDB_ID = re.compile(r"\[tmdbid-(\d+)\]$")


class ClaimRejectedError(Exception):
    """按不下去，而且**還沒動任何東西**。理由直接用 Issue 那一層的說法（`IssueRefusal`）：三顆都只
    從 Issue 按得到，而 `services/issues` 反過來 import 這一支，換一套說法再換回去只是多一張對照表。
    """

    def __init__(self, reason: IssueRefusal, detail: str) -> None:
        super().__init__(f"{reason.value}: {detail}")
        self.reason = reason
        self.detail = detail


class UnclaimedError(Exception):
    """這一個檔案配不上帳本（`ClaimMiss`）。什麼都還沒寫。"""

    def __init__(self, reason: ClaimMiss, path: Path) -> None:
        super().__init__(f"{reason.value}: {path}")
        self.reason = reason
        self.path = path


# --- 重新入庫（adopt） ---------------------------------------------------


def reimport_hash(path: Path) -> str:
    """complete 裡一個目錄重新入庫時那一筆 Job 的主鍵。

    `jobs.hash` 是 info hash（plan §2.3），而一個沒人認領的目錄沒有 torrent。**不另開一條沒有
    Job 的入庫路**（規劃器與 importer 都以 Job 為單位），所以給它一個與 info hash 同形的鍵：
    路徑的 SHA-1，帶一段前綴讓它不會與真的 info hash 同一個輸入。
    同一個目錄按兩次是同一個鍵（冪等）。
    """
    return hashlib.sha1(f"berth-reimport:{fs.path_key(path)}".encode()).hexdigest()


async def reimport_folder(
    session: AsyncSession, factory: ServiceClientFactory, path: Path, media_id: str, *, actor: str
) -> Job:
    """complete 裡一個沒人認領的目錄 → 一筆停在 `completed` 的 `reimport` Job（brief §9.3）。

    Route 由它落在哪一條 Route 的 complete 子目錄底下決定（brief §4.1：一條 Route 一個子目錄），
    作品由管理員選。**先把會失敗的都問完才建 Job**：那一包讀不到、作品不在、Route 收不下，都是
    什麼都沒動就停下來。
    """
    route, folder = await _route_by_folder(session, path)
    media = await ensure_media(session, factory, media_id)
    _usable(route, media)
    files = contents_on_disk(str(folder), str(path))
    if not files:
        raise ClaimRejectedError(IssueRefusal.SOURCE_MISSING, str(path))
    job_hash = reimport_hash(path)
    existing = await session.get(Job, job_hash)
    if existing is not None:
        return existing
    with job_context(job_hash):
        job = Job(
            hash=job_hash,
            name=path.name,
            trigger=JobTrigger.REIMPORT,
            trigger_ref=str(path),
            user_id=_user_id(actor),
            media_id=media.id,
            route_id=route.id,
            state=JobState.COMPLETED,
            save_path=str(folder),
            content_path=str(path),
            total_size=sum(size for _, size in files),
            progress=1.0,
            completed_at=utcnow(),
        )
        session.add(job)
        session.add_all(
            JobFile(job_hash=job_hash, rel_path=rel_path, size=size, priority=1)
            for rel_path, size in files
        )
        await record_event(
            session,
            job,
            EventType.CREATED,
            actor=actor,
            payload={
                "trigger": JobTrigger.REIMPORT.value,
                "media": media.id,
                "route": route.slug,
                "name": job.name,
                "source": str(path),
            },
        )
        # 與送單成功那一刻同一件事（`jobs.freeze`）：接下來真的要寫磁碟，資料夾名從這一刻起定死。
        freeze(media, route)
        await session.flush()
        logger.info("a complete folder was adopted", extra={"state": job.state.value})
    return job


# --- 認領 qBittorrent 上的一筆 --------------------------------------------


async def claim_torrent(
    session: AsyncSession,
    factory: ServiceClientFactory,
    job_hash: str,
    media_id: str,
    *,
    actor: str,
) -> Job:
    """qBittorrent 上掛著 Berth 記號、Berth 卻沒有 Job 的那一筆 → 一筆停在 `submitted` 的 Job。

    **按下去那一刻重問一次 qBittorrent**：偵測之後它可能被移除了，或已經有了 Job（判準與偵測同一份，
    `services/qbittorrent.unknown_torrents`）。Route 由它的 category 決定——只掛著 `berth` tag、
    category 不是任何一條 Route 的那一種說不出要入庫到哪裡，不猜。之後的每一步都是 poller 照常的
    一輪：`submitted` 正是送單成功之後那一站（plan §3.1）。
    """
    settings = await read_settings(session, QbittorrentSettings)
    client = factory.qbittorrent(settings.base_url)
    try:
        await sign_in(client, settings)
        statuses = await client.sync()
    except ServiceError as exc:
        raise ClaimRejectedError(IssueRefusal.CLIENT_UNREACHABLE, message(exc)) from exc
    finally:
        await client.aclose()
    unknown = await unknown_torrents(session, statuses)
    found = next((row for row in unknown if row.hash == job_hash), None)
    if found is None:
        raise ClaimRejectedError(
            IssueRefusal.ACTION_NOT_AVAILABLE, f"{job_hash} is no longer an unknown torrent"
        )
    route = await session.scalar(select(Route).where(Route.category == found.category))
    if route is None:
        raise ClaimRejectedError(
            IssueRefusal.ROUTE_UNUSABLE, f"category {found.category!r} belongs to no route"
        )
    media = await ensure_media(session, factory, media_id)
    _usable(route, media)
    with job_context(job_hash):
        job = Job(
            hash=found.hash,
            name=found.name,
            trigger=JobTrigger.MANUAL,
            user_id=_user_id(actor),
            media_id=media.id,
            route_id=route.id,
            state=JobState.SUBMITTED,
            save_path=found.save_path,
            content_path=found.content_path,
            total_size=found.total_size,
            progress=found.progress,
            client_state=found.state,
            last_seen_in_client_at=utcnow(),
        )
        session.add(job)
        await record_event(
            session,
            job,
            EventType.CREATED,
            actor=actor,
            payload={
                "trigger": JobTrigger.MANUAL.value,
                "media": media.id,
                "route": route.slug,
                "name": found.name,
                "claimed": True,
            },
        )
        await record_event(
            session,
            job,
            EventType.SUBMITTED,
            actor=actor,
            payload={
                "client": settings.base_url,
                "category": route.category,
                "save_path": found.save_path,
            },
        )
        freeze(media, route)
        await session.flush()
        logger.info("an unknown torrent was claimed", extra={"state": job.state.value})
    return job


async def ensure_media(
    session: AsyncSession, factory: ServiceClientFactory, media_id: str
) -> Media:
    """管理員選的那一部。Berth 還沒見過就先向 TMDB 要一份快照（`read_media`，與詳情頁同一支）；
    要不到（沒這部、TMDB 問不到）就按不下去——沒有快照的 Job 算不出任何一條目標路徑。"""
    if not media_id:
        raise ClaimRejectedError(IssueRefusal.MEDIA_REQUIRED, "pick the work this belongs to")
    await read_media(session, factory, media_id)
    row = await session.get(Media, media_id)
    if row is None or row.stored_snapshot() is None:
        raise ClaimRejectedError(IssueRefusal.MEDIA_REQUIRED, media_id)
    return row


def _usable(route: Route, media: Media) -> None:
    """與送單同一組前提（`jobs.check_route`）：停用、紅燈、種類不對的 Route 入不了庫。"""
    try:
        check_route(route, media)
    except JobRejectedError as refusal:
        raise ClaimRejectedError(IssueRefusal.ROUTE_UNUSABLE, refusal.detail) from refusal


async def _route_by_folder(session: AsyncSession, path: Path) -> tuple[Route, Path]:
    """complete 裡的一項落在哪一條 Route 的子目錄底下，以及那個子目錄。**只收第一層**：
    `orphan_complete` 說的就是那一層（`services/complete`），更深的一層是某一包裡的一部分。"""
    paths = await read_settings(session, PathSettings)
    for route in await session.scalars(select(Route).order_by(Route.id)):
        folder = Path(save_path_of(paths.complete_root, route.slug))
        if fs.top_level_under(path, [folder]) == path:
            return route, folder
    raise ClaimRejectedError(IssueRefusal.ACTION_NOT_AVAILABLE, f"{path} is under no route folder")


def _user_id(actor: str) -> int | None:
    """`events.actor` 是 user id 的字串（`jobs.actor_of`），Job 要的是那個數字。"""
    return int(actor) if actor.isdigit() else None


# --- 認領進帳本 -----------------------------------------------------------


async def claim_file(
    session: AsyncSession,
    factory: ServiceClientFactory,
    path: Path,
    *,
    index: SourceIndex | None = None,
    now: datetime | None = None,
    actor: str = "system",
) -> LedgerEntry:
    """媒體庫裡的一個檔案 → 帳本上完整的一列。配不上丟 `UnclaimedError`，什麼都不寫。

    本來就在帳本上的回那一列（冪等）。**不 commit**：CLI 一次走完再 commit，按鈕由
    `resolve_issue` commit。
    """
    route = await _route_of(session, path)
    relative = Path(path).relative_to(Path(route.target_path)).as_posix()
    target = str(PurePosixPath(route.target_path) / relative)
    existing = await session.scalar(select(LedgerEntry).where(LedgerEntry.target_path == target))
    if existing is not None:
        return existing

    try:
        placed = fs.stat(path)
    except OSError:
        raise UnclaimedError(ClaimMiss.NO_SOURCE, path) from None
    lookup = index if index is not None else await source_index(session)
    source = lookup.by_inode.get((placed.device, placed.inode))
    if source is None:
        raise UnclaimedError(ClaimMiss.NO_SOURCE, path)

    media = await _media_of(session, factory, route, relative)
    snapshot = media.stored_snapshot() if media is not None else None
    if media is None or snapshot is None:
        raise UnclaimedError(ClaimMiss.UNKNOWN_WORK, path)
    siblings = [
        f"{relative.rsplit('/', 1)[0]}/{other.name}"
        for other in Path(path).parent.iterdir()
        if other.is_file()
    ]
    reading = read_target(
        snapshot, relative, kind=kind_by_extension(Path(path).name), siblings=siblings
    )
    if reading is None:
        raise UnclaimedError(ClaimMiss.NOT_BERTH_NAMING, path)

    job_hash, source_rel_path = await _origin_of(session, source)
    moment = now or utcnow()
    entry = LedgerEntry(
        job_hash=job_hash,
        source_rel_path=source_rel_path,
        source_abs_path=str(source),
        source_inode=str(placed.inode),
        source_dev=str(placed.device),
        target_path=target,
        target_inode=str(placed.inode),
        media_id=media.id,
        season=reading.season,
        episode_start=reading.episode_start,
        episode_end=reading.episode_end,
        tags_json=reading.tags.model_dump(mode="json"),
        plan_item_id=None,
        action=reading.action,
        link_mode=HARDLINK,
        status=LedgerStatus.OK,
        audit=False,
        created_at=moment,
        # 只有正片是 Jellyfin 裡查得到的 item（同 `importer.record_link`）。
        resolve_after=first_resolve_at(moment) if reading.action is PlanAction.IMPORT else None,
    )
    session.add(entry)
    await settle(session, str(path), job_hash, actor=actor, now=moment)
    await session.flush()
    logger.info("a library file was claimed into the ledger", extra={"target": target})
    return entry


@dataclass(slots=True)
class SourceIndex:
    """complete 裡的來源，以 `(device, inode)` 為鍵，加上這一次沒讀到的那幾條子目錄。"""

    by_inode: dict[tuple[int, int], Path] = field(default_factory=dict)
    #: 讀不到的 complete 子目錄（原文）。不是空的時候，配不到來源說的就不是「它沒有來源」，
    #: 而是「問不到」——brief §16.2 的「問不到不算不見了」。
    unread: list[str] = field(default_factory=list)


async def source_index(session: AsyncSession) -> SourceIndex:
    """complete 裡每一條 Route 子目錄底下的每一個檔案，以 `(device, inode)` 為鍵。

    只看 Route 的子目錄，與對帳的 `orphan_complete` 同一個範圍（`services/complete`）：complete
    root 可能與 Sonarr 共用，別人 category 底下的檔案不是 Berth 的來源。讀不到的子目錄記在
    `unread`：在它底下的來源配不到，呼叫端要分得出那是問不到而不是沒有。
    """
    index = SourceIndex()
    for folder in await complete.route_folders(session):
        try:
            files = fs.files_under(folder) if folder.is_dir() else []
        except OSError as exc:
            logger.warning("a complete folder could not be read", extra={"path": str(folder)})
            index.unread.append(f"{folder}: {exc}")
            continue
        for path in files:
            try:
                facts = fs.stat(path)
            except OSError:
                # 走訪之後、量之前不見了（qBittorrent 正在搬、有人在刪）：這一個配不到，其餘照樣算。
                continue
            index.by_inode.setdefault((facts.device, facts.inode), path)
    return index


async def settle(
    session: AsyncSession, path: str, job_hash: str | None, *, actor: str, now: datetime
) -> None:
    """這個檔案長回帳本了：它那一件 `unmanaged_library_file` 跟著收掉；它屬於的那一筆 Job 若掛著
    `job_without_files`（帳本整個清掉之後對帳開的），那一件說的也不再是事實。"""
    rows = await session.scalars(
        select(Issue).where(
            Issue.status == IssueStatus.OPEN,
            ((Issue.type == IssueType.UNMANAGED_LIBRARY_FILE) & (Issue.subject == path))
            | ((Issue.type == IssueType.JOB_WITHOUT_FILES) & (Issue.subject == (job_hash or ""))),
        )
    )
    for row in rows:
        row.status = IssueStatus.RESOLVED
        row.resolved_at = now
        row.resolved_by = actor


# --- 內部 ---------------------------------------------------------------


async def _route_of(session: AsyncSession, path: Path) -> Route:
    """這個檔案在哪一條 Route 底下。巢狀的兩條（`…/tv` 與 `…/tv/anime`）取最深的那一條：
    作品資料夾是那一條的第一層。"""
    routes = [
        route
        for route in await session.scalars(select(Route))
        if fs.is_within(Path(path), Path(route.target_path))
    ]
    if not routes:
        raise UnclaimedError(ClaimMiss.OUTSIDE_ROUTES, path)
    return max(routes, key=lambda route: len(Path(route.target_path).parts))


async def _media_of(
    session: AsyncSession, factory: ServiceClientFactory, route: Route, relative: str
) -> Media | None:
    """作品資料夾名說的是哪一部。種類由 Route 的媒體庫類型決定（劇集只進得了 tvshows）。

    Berth 還沒有它的快照就先向 TMDB 要一份（`read_media`，與詳情頁同一支）；拿不到就是不知道。
    """
    found = _TMDB_ID.search(relative.split("/", 1)[0])
    if found is None:
        return None
    kind = next(
        (kind for kind in MediaKind if collection_type_for(kind) is route.collection_type), None
    )
    if kind is None:
        return None
    media_id = build_media_id(kind, int(found.group(1)))
    known = await session.get(Media, media_id)
    # 有那一列但沒有快照（送單時 TMDB 沒接上）與沒有那一列是同一件事：反解要的是季集。
    if known is None or known.stored_snapshot() is None:
        await read_media(session, factory, media_id)
    return await session.get(Media, media_id)


async def _origin_of(session: AsyncSession, source: Path) -> tuple[str | None, str]:
    """來源屬於哪一筆 Job，以及它相對那一筆 save path 的路徑（`ledger.source_rel_path`）。

    沒有 Job 指著它（torrent 與 Job 都清掉了）的話 `job_hash` 是 `None`，相對路徑就相對它所在的
    那一條 Route 的 complete 子目錄——那正是 qBittorrent 當時的 save path（brief §4.1）。
    """
    jobs = await session.scalars(select(Job).where(Job.content_path != "", Job.save_path != ""))
    for job in jobs:
        if fs.is_within(source, Path(job.content_path)):
            return job.hash, source.relative_to(Path(job.save_path)).as_posix()
    folders = await complete.route_folders(session)
    root = fs.root_of(source, folders)
    return None, source.relative_to(root).as_posix()
