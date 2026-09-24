"""對帳：比四方、寫下要人決定的那幾件（brief §9.1、§16.2、plan §3.2、M2 票 05 / 09）。

**一輪對帳是一個可觀察的工作**（2026-09-22 定）：`POST /reconcile` 回 202 與這一輪的 id，
`GET /reconcile` 回上一輪與進行中的進度，上一輪還在跑時再按是 409。跑的那一段在
`pipeline/reconciling.py`；這裡是那一輪本身。

形狀只有一句話：**先把四方各自問完，再寫 Issue**。

四方是帳本、qBittorrent、complete 目錄、每一條 Route 的媒體庫目錄。分兩段的理由不是效能，
是**誠實**（brief §16.2）：任一方問不到就跳過那一方並在結果上說出來，而不是把「問不到」
當成「不見了」。qBittorrent 掛掉的那一刻，帳本上每一筆的 torrent 都「不在客戶端」；Route
目錄沒掛上的那一刻，媒體庫裡每一個檔案都「不見了」。照著「查不到就是沒有」寫的話，一輪對帳
會產出一份把整個媒體庫報成失蹤的清單——而使用者會照著它按下「承認刪除並清帳本」。

問得到的單位是**逐 Route**而不是「媒體庫這一方」：三條 Route 裡有一條沒掛上時，其餘兩條的
帳本仍然該比。跳過哪幾條寫在這一輪的結果上。

**每一種檢查只用它需要的那幾方，缺一方就整種不做**：`orphan_complete` 要 qBittorrent 與
complete 兩方都問到（問不到 qBittorrent 的那一刻，每一個目錄看起來都沒有主），
`unknown_torrent` 要 qBittorrent，媒體庫那四種逐 Route，`job_without_files` 只看帳本。

**第五方是 Jellyfin**（票 09）：它不開 Issue，只把帳本記著的 item 換成 Jellyfin 現在的樣子
（`resolver.refresh_resolved`：補上票 13 之前沒有的 Series id、換掉合併之後不再是主條目的
item id）。放進同一輪而不是另一個迴圈，是因為它與其餘四方一樣「定期比一次、問不到就說」，
而畫面上逐方說的那一行本來就是給這種事的。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.adapters import fs
from berth.adapters.http import ServiceError
from berth.adapters.qbittorrent import TorrentStatus
from berth.domain import (
    IssueAction,
    IssueRefusal,
    IssueStatus,
    IssueType,
    JobState,
    LedgerStatus,
    PlanAction,
    ReconcileSide,
)
from berth.models import (
    Issue,
    JellyfinSettings,
    Job,
    LedgerEntry,
    PathSettings,
    Plan,
    PlanItem,
    QbittorrentSettings,
    Route,
)
from berth.models.types import utcnow
from berth.services import complete
from berth.services.clients import ServiceClientFactory
from berth.services.issues import IssueRejectedError, Recorded, record_issue
from berth.services.plan import WRITTEN
from berth.services.qbittorrent import (
    managed,
    sign_in,
    unknown_torrent_detail,
    unknown_torrents,
)
from berth.services.resolver import refresh_resolved
from berth.services.settings import read_settings
from berth.services.steps import message

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SideReport:
    """一方問完之後的結果。畫面逐方說「比到哪、幾筆」（plan §3.2）。

    `unavailable` 與 `skipped` 說的是兩件不同的事：前者是**整方**問不到（qBittorrent 掛了），
    後者是問得到但其中幾處跳過了（三條 Route 裡有一條沒掛上）。兩者都要說出來，因為它們
    的下一步不同——一個是去修那台服務，一個是去看那一行 volume。
    """

    side: ReconcileSide
    #: 這一方真的比了幾筆。問不到的那一方是 0。
    counted: int
    #: 整方問不到的原文。問得到就是空字串。
    unavailable: str = ""
    #: 問得到、但跳過的那幾處（每一條一句話，含它的名字）。
    skipped: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReconcileReport:
    """一輪的全部。進行中的那一輪 `finished_at` 是 `None`，`sides` 只有已經走完的那幾方。"""

    id: int
    started_at: datetime
    finished_at: datetime | None
    sides: tuple[SideReport, ...]
    #: 這一輪新開的 Issue 數。
    opened: int
    #: 這一輪更新的（本來就開著的同一件事）。
    updated: int


@dataclass(slots=True)
class _Survey:
    """各方問完之後手上有的東西。**寫 Issue 的那一段只看它**，不再碰服務。"""

    #: 整張帳本，問帳本那一方時讀一次。其餘幾方與檢查用的都是這一份。
    ledger: list[LedgerEntry] = field(default_factory=list)
    #: 問得到的那幾條 Route 的媒體庫目錄。帳本的目標落在它們底下才比得了。
    library_roots: list[Path] = field(default_factory=list)
    #: 那幾條底下的帳本。
    library_entries: list[LedgerEntry] = field(default_factory=list)
    #: 那幾條底下走訪出來的每一個檔案（`unmanaged_library_file` 比的就是它）。
    library_files: list[Path] = field(default_factory=list)
    #: qBittorrent 現在的**全部** torrent。`None` 是問不到——與「一個都沒有」不同。
    torrents: tuple[TorrentStatus, ...] | None = None
    #: 每一條 Route 的 complete 子目錄。
    complete_folders: list[Path] = field(default_factory=list)
    #: 那幾個子目錄底下的每一項（一個 torrent 的內容根）。`None` 是 complete 讀不到。
    complete_items: list[Path] | None = None
    reports: list[SideReport] = field(default_factory=list)


@dataclass(slots=True)
class _Tally:
    """這一輪開了幾件、更新了幾件。

    **數的是 `record_issue` 真的做了什麼**，不是從帳本的舊狀態推：被忽略過的那一列帳本仍然是
    `target_missing`，而這一輪開的是新的一筆（`ignore` 的意思是「這一次不想處理」，不是「這件
    事不存在」）——推出來的答案在那一格會說謊。
    """

    opened: int = 0
    updated: int = 0

    def add(self, recorded: Recorded) -> None:
        if recorded.opened:
            self.opened += 1
        else:
            self.updated += 1


async def reconcile_once(
    session: AsyncSession,
    factory: ServiceClientFactory,
    *,
    now: datetime | None = None,
    run_id: int = 0,
    progress: Progress | None = None,
) -> ReconcileReport:
    """比一輪。**只讀各方，然後只寫 `issues` 與帳本**（`status`、`checked_at`，以及 Jellyfin
    那一方換新的 item id）。

    `progress` 讓跑在背景的那一輪把每一方的結果即時交出去（`GET /reconcile` 讀它）。
    不傳也跑得完——整份邏輯不依賴它，測試因此不必先起一個 runner。
    """
    started = now or utcnow()
    survey = _Survey()
    for side in ReconcileSide:
        report = await _ask(session, factory, side, survey)
        survey.reports.append(report)
        if progress is not None:
            progress.side_done(report)

    tally = _Tally()
    await _check_library(session, survey, started, tally)
    await _check_unmanaged(session, survey, started, tally)
    await _check_complete(session, survey, started, tally)
    await _check_unknown_torrents(session, survey, started, tally)
    await _check_jobs(session, survey, started, tally)
    await session.commit()

    finished = ReconcileReport(
        id=run_id,
        started_at=started,
        finished_at=utcnow(),
        sides=tuple(survey.reports),
        opened=tally.opened,
        updated=tally.updated,
    )
    logger.info(
        "reconcile finished",
        extra={
            "opened": tally.opened,
            "updated": tally.updated,
            "skipped": [row.side.value for row in survey.reports if row.unavailable],
        },
    )
    return finished


# --- 問各方 -------------------------------------------------------------


async def _ask(
    session: AsyncSession,
    factory: ServiceClientFactory,
    side: ReconcileSide,
    survey: _Survey,
) -> SideReport:
    if side is ReconcileSide.LEDGER:
        return await _ask_ledger(session, survey)
    if side is ReconcileSide.CLIENT:
        return await _ask_client(session, factory, survey)
    if side is ReconcileSide.COMPLETE:
        return await _ask_complete(session, survey)
    if side is ReconcileSide.LIBRARY:
        return await _ask_library(session, survey)
    return await _ask_jellyfin(session, factory, survey)


async def _ask_ledger(session: AsyncSession, survey: _Survey) -> SideReport:
    """整張帳本。**永遠問得到**——它就在同一個資料庫裡，而對帳本來就是在同一個交易裡跑的。"""
    survey.ledger = list(await session.scalars(select(LedgerEntry).order_by(LedgerEntry.id)))
    return SideReport(side=ReconcileSide.LEDGER, counted=len(survey.ledger))


async def _ask_client(
    session: AsyncSession, factory: ServiceClientFactory, survey: _Survey
) -> SideReport:
    """qBittorrent 上的**全部** torrent。

    留下全部而不只是掛著 Berth 記號的那幾筆：`orphan_complete` 問的是「qBittorrent 上**任何**
    一個 torrent 認不認得這一項」。`counted` 仍然只數 Berth 的（plan §3.2 的兩道篩子的聯集），
    那才是畫面上「比到幾筆」的意思。
    """
    settings = await read_settings(session, QbittorrentSettings)
    client = factory.qbittorrent(settings.base_url)
    try:
        await sign_in(client, settings)
        statuses = await client.sync()
    except ServiceError as exc:
        # 問不到不是「它們都不在了」。跳過這一方，說出原文。
        logger.warning("reconcile could not ask the client", extra={"error": message(exc)})
        return SideReport(
            side=ReconcileSide.CLIENT,
            counted=0,
            unavailable=f"qBittorrent did not answer: {message(exc)}",
        )
    finally:
        await client.aclose()

    survey.torrents = statuses
    ours = managed(statuses, await _categories(session))
    return SideReport(side=ReconcileSide.CLIENT, counted=len(ours))


async def _ask_complete(session: AsyncSession, survey: _Survey) -> SideReport:
    """每一條 Route 的 complete 子目錄底下有哪幾項（一個 torrent 一項，brief §4.1）。

    complete root 本身讀不到＝那個掛載沒掛上，不是「下載目錄空了」。某一條 Route 的子目錄
    還不在不是問題：qBittorrent 第一次往那個 category 下載時才會建它。
    """
    paths = await read_settings(session, PathSettings)
    root = Path(paths.complete_root)
    folders = await complete.route_folders(session)
    try:
        list(root.iterdir())
        # 子目錄讀到一半讀不到（權限、掛載中途掉）與 root 讀不到是同一件事：這一方問不到。
        # 只跳過那一條不行——`orphan_complete` 的下一步是刪除，少看一條就少認一個主。
        items = [
            item
            for folder in folders
            if folder.is_dir()
            for item in sorted(folder.iterdir())
            # Route 的硬鏈接檢查在這一層放探測檔（`fs.probe_file`），撞上的那一刻不算。
            if not item.name.startswith(fs.PROBE_PREFIX)
        ]
    except OSError as exc:
        logger.warning("reconcile could not read complete", extra={"error": message(exc)})
        return SideReport(
            side=ReconcileSide.COMPLETE,
            counted=0,
            unavailable=f"the complete folder at {root} could not be read: {message(exc)}",
        )
    survey.complete_folders = folders
    survey.complete_items = items
    return SideReport(side=ReconcileSide.COMPLETE, counted=len(items))


async def _ask_library(session: AsyncSession, survey: _Survey) -> SideReport:
    """**逐 Route 問**：那一條的媒體庫目錄在不在（brief §16.2）。

    在的那幾條留進 `survey.library_roots`，底下的帳本與檔案才比得了；不在的那幾條跳過並說出
    它的名字——使用者要知道的是「哪一條沒掛上」，而不是「有東西不見了」。

    `enabled` 不在判準裡：停用說的是「不要再往這裡入庫」，不是「裡面的東西不用管了」。
    那些檔案還在 Jellyfin 的媒體庫裡，帳本仍然要對得上。
    """
    routes = list(await session.scalars(select(Route).order_by(Route.id)))
    skipped: list[str] = []
    files: dict[str, Path] = {}
    for route in routes:
        root = Path(route.target_path)
        if not root.is_dir():
            skipped.append(
                f"{route.name} ({route.target_path}) is not there; is the volume mounted?"
            )
            logger.warning(
                "reconcile skipped a route", extra={"route": route.slug, "path": route.target_path}
            )
            continue
        try:
            walked = fs.files_under(root)
        except OSError as exc:
            # 走到一半讀不到：這一條整條跳過。只比走到的那一半的話，沒走到的檔案會被報成
            # 「不見了」，而它們的帳本列會被當成沒人認的鏈接。
            skipped.append(f"{route.name} ({route.target_path}) could not be read: {message(exc)}")
            logger.warning(
                "reconcile could not walk a route",
                extra={"route": route.slug, "error": message(exc)},
            )
            continue
        survey.library_roots.append(root)
        # 兩條 Route 的目標巢狀時（`…/tv` 與 `…/tv/anime`）同一個檔案只算一次。
        for path in walked:
            files.setdefault(fs.path_key(path), path)

    # 在 Python 裡篩而不是用 SQL 的 `LIKE`：路徑比對的規則（正規化、Windows 的大小寫、同前綴
    # 的兄弟目錄）只能有一份實作，而它在 `fs.is_within`（plan §8.6）。
    survey.library_entries = [
        entry
        for entry in survey.ledger
        if any(fs.is_within(Path(entry.target_path), root) for root in survey.library_roots)
    ]
    survey.library_files = list(files.values())
    return SideReport(
        side=ReconcileSide.LIBRARY,
        counted=len(survey.library_entries),
        # 一條都掛不上就是整方問不到：畫面該說的是「媒體庫問不到」，不是「跳過三條」。
        unavailable=(
            "no route target folder could be read; are the volumes mounted?"
            if routes and not survey.library_roots
            else ""
        ),
        skipped=tuple(skipped),
    )


async def _ask_jellyfin(
    session: AsyncSession, factory: ServiceClientFactory, survey: _Survey
) -> SideReport:
    """反查過的正片照 Jellyfin 現在的樣子重對一次（`resolver.refresh_resolved`）。

    **一條都沒反查過就一個請求都不發**：剛裝好、還沒入庫過的 Berth 不該因為 Jellyfin 還沒
    接好而在每一輪說「問不到」。
    """
    resolved = [
        entry
        for entry in survey.ledger
        if entry.action is PlanAction.IMPORT and entry.jellyfin_item_id
    ]
    if not resolved:
        return SideReport(side=ReconcileSide.JELLYFIN, counted=0)
    settings = await read_settings(session, JellyfinSettings)
    client = factory.jellyfin(settings.base_url, token=settings.api_key)
    try:
        changed = await refresh_resolved(session, client, resolved)
    except ServiceError as exc:
        logger.warning("reconcile could not ask jellyfin", extra={"error": message(exc)})
        return SideReport(
            side=ReconcileSide.JELLYFIN,
            counted=0,
            unavailable=f"Jellyfin did not answer: {message(exc)}",
        )
    finally:
        await client.aclose()
    if changed:
        logger.info("reconcile refreshed jellyfin items", extra={"count": changed})
    return SideReport(side=ReconcileSide.JELLYFIN, counted=len(resolved))


async def _categories(session: AsyncSession) -> set[str]:
    return {row for row in await session.scalars(select(Route.category)) if row}


# --- 寫 Issue -----------------------------------------------------------


async def _check_library(
    session: AsyncSession, survey: _Survey, now: datetime, tally: _Tally
) -> None:
    """帳本那一列的三種：`library_link_missing`、`source_missing`、`inode_mismatch`。

    **只比問得到的那幾條 Route 底下的帳本**。落在跳過的那一條底下的每一列連 `status` 都
    不動——那一欄說的是「比對過的現況」，而這一輪根本沒有比到它。

    三種是**同一條路上的三站**，一列只落在其中一站：目標不在就是鏈接遺失（來源在不在由
    「重新鏈接」那一顆說）；目標在、來源不在才是 `source_missing`（brief §9.1 的「library 檔
    保留」說的正是這個情況）；兩邊都在而 inode 不同才是 `inode_mismatch`。
    """
    for entry in survey.library_entries:
        entry.checked_at = now
        try:
            target = fs.stat(Path(entry.target_path))
        except OSError:
            # **`unlinked` 是使用者決定過的現況**（同下面的 `source_missing`）：刪除範圍的「移除
            # 鏈接」拆掉的那幾列留著當歷史，不再問他要不要重新鏈接（M3 票 01）。
            if entry.status is not LedgerStatus.UNLINKED:
                entry.status = LedgerStatus.TARGET_MISSING
                tally.add(await _record_entry(session, IssueType.LIBRARY_LINK_MISSING, entry, now))
            continue
        try:
            source = fs.stat(Path(entry.source_abs_path))
        except OSError:
            # **帳本上的 `source_missing` 是使用者決定過的現況**：刪除範圍只勾「刪 complete
            # 檔案」、或按過「標記為已無來源」的那一列就是這樣，不再問一次。還沒決定過的才開
            # Issue，而那一欄等按下去才改——偵測時就改的話，「忽略」之後下一輪就再也不會問了。
            if entry.status is not LedgerStatus.SOURCE_MISSING:
                tally.add(await _record_entry(session, IssueType.SOURCE_MISSING, entry, now))
            continue
        if (source.device, source.inode) != (target.device, target.inode):
            entry.status = LedgerStatus.INODE_MISMATCH
            # 「若大小一致提供以硬鏈接取代」（brief §9.1）：那一顆給不給看 `same_size`。
            sizes = {
                "same_size": source.size == target.size,
                "source_size": source.size,
                "target_size": target.size,
            }
            tally.add(
                await _record_entry(session, IssueType.INODE_MISMATCH, entry, now, extra=sizes)
            )
            continue
        # 兩邊都在、是同一份：檔案自己回來了（使用者放回去、別的地方重新鏈接過、來源被重新
        # 下載回來）。帳本那一欄回到現況。
        entry.status = LedgerStatus.OK


async def _check_unmanaged(
    session: AsyncSession, survey: _Survey, now: datetime, tally: _Tally
) -> None:
    """`unmanaged_library_file`：媒體庫裡有 Berth 不認得的檔案。**只列出，永不自動刪**。

    比的是**整張帳本**的目標，不只是問得到的那幾條 Route 底下的：巢狀的 Route 會讓同一個檔案
    落在兩條底下。比對用 `fs.path_key`——帳本記的是容器裡的 POSIX 字串，走訪拿到的是這台
    機器的 `Path`。
    """
    known = {fs.path_key(entry.target_path) for entry in survey.ledger}
    for path in survey.library_files:
        if fs.path_key(path) in known:
            continue
        tally.add(
            await record_issue(session, IssueType.UNMANAGED_LIBRARY_FILE, path=str(path), now=now)
        )


async def _check_complete(
    session: AsyncSession, survey: _Survey, now: datetime, tally: _Tally
) -> None:
    """`orphan_complete`：complete 裡一項既不屬於 qBittorrent 任何 torrent，也不在帳本上。

    **qBittorrent 與 complete 兩方都要問到**：問不到 qBittorrent 的那一刻，每一個目錄看起來
    都沒有主，而這一種的下一步是「刪除」。判準在 `services/complete.claimed`，與按下「刪除」
    那一刻的再確認是同一份。
    """
    if survey.torrents is None or survey.complete_items is None:
        return
    owned = await complete.claimed(session, survey.torrents, survey.complete_folders)
    for item in survey.complete_items:
        if fs.path_key(item) in owned:
            continue
        tally.add(
            await record_issue(
                session,
                IssueType.ORPHAN_COMPLETE,
                path=str(item),
                detail={"folder": item.is_dir()},
                now=now,
            )
        )


async def _check_unknown_torrents(
    session: AsyncSession, survey: _Survey, now: datetime, tally: _Tally
) -> None:
    """`unknown_torrent`：qBittorrent 上掛著 Berth 記號、而 Berth 沒有 Job 的那幾筆。

    `qbit_poller` 每一輪也寫它（plan §3.2），兩個生產者寫同一個 `(type, subject)`，冪等鍵把
    它們收成一筆；判準與內容都是同一份（`unknown_torrents`、`unknown_torrent_detail`）。
    """
    if survey.torrents is None:
        return
    for row in await unknown_torrents(session, survey.torrents):
        tally.add(
            await record_issue(
                session,
                IssueType.UNKNOWN_TORRENT,
                job_hash=row.hash,
                detail=unknown_torrent_detail(row),
                now=now,
            )
        )


async def _check_jobs(session: AsyncSession, survey: _Survey, now: datetime, tally: _Tally) -> None:
    """`job_without_files`：Job 已經 `imported`，帳本上卻一列都沒有。只看帳本那一方。

    兩種空帳本**不算**：

    - 那一份 Plan 本來就沒有要鏈的檔案（全是重複的那一包自動落地，票 08）——空的就是對的。
    - 使用者對它按過「承認刪除並清帳本」：帳本是他自己清的。這裡再開一件「重新規劃」的話，
      他剛決定過的事會自己回來（票 05 的 `purge` 那一條是同一個道理）。
    """
    candidates = {
        job.hash: job
        for job in await session.scalars(select(Job).where(Job.state == JobState.IMPORTED))
    }
    for entry in survey.ledger:
        candidates.pop(entry.job_hash or "", None)
    if not candidates:
        return
    linkable = set(
        await session.scalars(
            select(Plan.job_hash)
            .join(PlanItem, PlanItem.plan_id == Plan.id)
            .where(Plan.job_hash.in_(candidates), PlanItem.action.in_(WRITTEN))
        )
    )
    forgotten = {
        row.job_hash
        for row in await session.scalars(
            select(Issue).where(
                Issue.job_hash.in_(candidates), Issue.status == IssueStatus.RESOLVED
            )
        )
        if (row.detail_json or {}).get("action") == IssueAction.FORGET.value
    }
    for job_hash, job in candidates.items():
        if job_hash not in linkable or job_hash in forgotten:
            continue
        tally.add(
            await record_issue(
                session,
                IssueType.JOB_WITHOUT_FILES,
                job_hash=job_hash,
                detail={"name": job.name},
                now=now,
            )
        )


async def _record_entry(
    session: AsyncSession,
    kind: IssueType,
    entry: LedgerEntry,
    now: datetime,
    *,
    extra: dict[str, Any] | None = None,
) -> Recorded:
    """帳本那一列的一件事：來源在哪、是哪一部哪一集，加上這一種自己要說的。"""
    return await record_issue(
        session,
        kind,
        path=entry.target_path,
        job_hash=entry.job_hash,
        ledger_id=entry.id,
        detail={
            "source": entry.source_abs_path,
            "media": entry.media_id,
            "season": entry.season,
            "episode": entry.episode_start,
            "action": entry.action.value,
            **(extra or {}),
        },
        now=now,
    )


class Progress:
    """跑在背景的那一輪把每一方的結果即時交出去（`GET /reconcile` 讀它）。

    只是一個回呼的殼：`reconcile_once` 的簽名要說得出它會回報進度，而誰在讀是別人的事。
    """

    def __init__(self) -> None:
        self.sides: list[SideReport] = []

    def side_done(self, report: SideReport) -> None:
        self.sides.append(report)


@dataclass(frozen=True, slots=True)
class ReconcileStatus:
    """`GET /reconcile` 回的那一份（plan §6 issues 群組）。

    兩格都可能是 `None`，而它們的意思不一樣：`current` 是 `None` 代表現在沒有在跑，
    `last` 是 `None` 代表這個程序起來之後還沒跑過。畫面要分得出來。
    """

    current: ReconcileReport | None
    last: ReconcileReport | None


class ReconcileRunner:
    """**一次只有一輪**，加上一份「現在跑到哪」（plan §3.2，M2 票 05）。

    住在 `services` 而不是 `pipeline`，因為它有兩個呼叫端：`POST /reconcile` 開一輪、
    `GET /reconcile` 讀進度（`api`），而每日 04:00 的排程也按同一顆按鈕（`pipeline`）。
    `api` 不可以 import `pipeline`（plan §1.3，import-linter 守著），所以「一次只有一輪」
    這個判斷只能住在兩邊都到得了的這一層——而它本來就該只有一份。

    **進度活在記憶體裡**：「哪一方比到哪」是這一輪的事，重啟之後沒有人在等它；真正要留
    下來的是 `issues` 表，而那一份在資料庫裡。重啟之後 `GET /reconcile` 說「還沒跑過」，
    那是實話。
    """

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        clients: ServiceClientFactory,
        *,
        now: Callable[[], datetime] = utcnow,
    ) -> None:
        self._sessions = sessions
        self._clients = clients
        self._now = now
        self._runs = 0
        self._current: ReconcileReport | None = None
        self._progress: Progress | None = None
        self._last: ReconcileReport | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> ReconcileReport:
        """開一輪，**立刻回**這一輪的樣子（`POST /reconcile` 的 202）。

        上一輪還在跑時拒絕：**不排隊**，因為排隊的那一輪看到的會是同一份磁碟，做的是
        同樣的比對，寫的是同樣的 Issue（plan §3.2）。
        """
        if self.running:
            raise IssueRejectedError(
                IssueRefusal.RECONCILE_RUNNING,
                "a reconcile run is already going; wait for it to finish",
            )
        self._runs += 1
        self._progress = Progress()
        self._current = ReconcileReport(
            id=self._runs,
            started_at=self._now(),
            finished_at=None,
            sides=(),
            opened=0,
            updated=0,
        )
        self._task = asyncio.create_task(
            self._reconcile(self._runs), name=f"reconcile-{self._runs}"
        )
        logger.info("reconcile started", extra={"run": self._runs})
        return self._current

    def status(self) -> ReconcileStatus:
        """上一輪與進行中的那一輪（plan §3.2 的「哪一方比到哪、幾筆」）。"""
        return ReconcileStatus(current=self._snapshot(), last=self._last)

    def _snapshot(self) -> ReconcileReport | None:
        """進行中那一輪的現況：已經走完的那幾方填進去，其餘還沒有。"""
        if self._current is None or self._progress is None:
            return None
        return ReconcileReport(
            id=self._current.id,
            started_at=self._current.started_at,
            finished_at=None,
            sides=tuple(self._progress.sides),
            opened=0,
            updated=0,
        )

    async def _reconcile(self, run_id: int) -> None:
        """背景那一段。**自己開 session**：發起它的那個請求早就回完了（202）。"""
        started = self._current.started_at if self._current is not None else self._now()
        progress = self._progress
        try:
            async with self._sessions() as session:
                self._last = await reconcile_once(
                    session, self._clients, now=started, run_id=run_id, progress=progress
                )
        except Exception:
            # 這一輪垮了。下一輪（排程或手動）重新開始——對帳本來就是可以重跑的。
            logger.exception("reconcile run failed", extra={"run": run_id})
        finally:
            self._current = None
            self._progress = None

    async def wait(self) -> None:
        """等進行中的那一輪跑完。**只給測試**（同 `services/jobs.held_locks`）。

        產品裡沒有人等對帳：`POST /reconcile` 回 202 就走了，每日排程開了也不回頭看，
        而關機是 cancel（`aclose`）。測試需要它是因為「跑完之後 `last` 說得出什麼」
        只有在那一輪真的落地之後才問得出來。
        """
        if self._task is not None:
            await self._task

    async def aclose(self) -> None:
        """關機時收掉背景那一輪。跑到一半被 cancel 的不留半筆——只在最後 commit 一次。"""
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None
