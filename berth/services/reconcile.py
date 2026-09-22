"""對帳：比四方、寫下要人決定的那幾件（brief §9.1、§16.2、plan §3.2、M2 票 05）。

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

**這一輪只做 `library_link_missing`**（票 05）：其餘六種檢查在票 09。客戶端與 complete 那兩方
仍然要問——沒有檢查在用它們，但「這一方問到了嗎」本身就是結果的一部分，而下一張票只是多幾個
比對，不是重做這一輪的形狀。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.adapters import fs
from berth.adapters.http import ServiceError
from berth.domain import IssueRefusal, IssueType, LedgerStatus, ReconcileSide
from berth.models import LedgerEntry, PathSettings, QbittorrentSettings, Route
from berth.models.types import utcnow
from berth.services.clients import ServiceClientFactory
from berth.services.issues import IssueRejectedError, record_issue
from berth.services.qbittorrent import managed, sign_in
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
    """四方問完之後手上有的東西。**寫 Issue 的那一段只看它**，不再碰磁碟或服務。"""

    #: 問得到的那幾條 Route 的媒體庫目錄。帳本的目標落在它們底下才比得了。
    library_roots: list[Path] = field(default_factory=list)
    #: 那幾條底下的帳本。**問那一方的時候就讀出來**：檢查要用的是同一份，整張 `ledger`
    #: 一輪讀一次就夠（讀兩次還得把 `fs.is_within` 也算兩遍）。
    library_entries: list[LedgerEntry] = field(default_factory=list)
    reports: list[SideReport] = field(default_factory=list)


async def reconcile_once(
    session: AsyncSession,
    factory: ServiceClientFactory,
    *,
    now: datetime | None = None,
    run_id: int = 0,
    progress: Progress | None = None,
) -> ReconcileReport:
    """比一輪。**只讀四方，然後只寫 `issues` 與 `ledger.status`。**

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

    opened, updated = await _check_library_links(session, survey, started)
    await session.commit()

    finished = ReconcileReport(
        id=run_id,
        started_at=started,
        finished_at=utcnow(),
        sides=tuple(survey.reports),
        opened=opened,
        updated=updated,
    )
    logger.info(
        "reconcile finished",
        extra={
            "opened": opened,
            "updated": updated,
            "skipped": [row.side.value for row in survey.reports if row.unavailable],
        },
    )
    return finished


# --- 問四方 -------------------------------------------------------------


async def _ask(
    session: AsyncSession,
    factory: ServiceClientFactory,
    side: ReconcileSide,
    survey: _Survey,
) -> SideReport:
    if side is ReconcileSide.LEDGER:
        return await _ask_ledger(session)
    if side is ReconcileSide.CLIENT:
        return await _ask_client(session, factory)
    if side is ReconcileSide.COMPLETE:
        return await _ask_complete(session)
    return await _ask_library(session, survey)


async def _ask_ledger(session: AsyncSession) -> SideReport:
    """帳本有幾列。**永遠問得到**——它就在同一個資料庫裡，而對帳本來就是在同一個交易裡跑的。"""
    rows = await session.scalars(select(LedgerEntry.id))
    return SideReport(side=ReconcileSide.LEDGER, counted=len(list(rows)))


async def _ask_client(session: AsyncSession, factory: ServiceClientFactory) -> SideReport:
    """qBittorrent 上掛著 Berth 記號的那幾筆（plan §3.2 的兩道篩子的聯集）。

    **這一票沒有檢查在用這一份**（`unknown_torrent` 與 `orphan_complete` 在票 09），但仍然要
    問：結果上少一方的話，「沒有 Issue」會有兩種意思——都好好的，或根本沒比。票上那一條
    驗收要的正是「問不到時說出來」。
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

    categories = {row for row in await session.scalars(select(Route.category)) if row}
    return SideReport(side=ReconcileSide.CLIENT, counted=len(managed(statuses, categories)))


async def _ask_complete(session: AsyncSession) -> SideReport:
    """complete 底下有幾個第一層目錄（一個 torrent 一個，brief §4.2）。

    同樣是「問到了沒」而不是一個檢查（`orphan_complete` 在票 09）。目錄不在＝那個掛載
    沒掛上，不是「下載目錄空了」。
    """
    paths = await read_settings(session, PathSettings)
    root = Path(paths.complete_root)
    try:
        entries = list(root.iterdir())
    except OSError as exc:
        logger.warning("reconcile could not read complete", extra={"error": message(exc)})
        return SideReport(
            side=ReconcileSide.COMPLETE,
            counted=0,
            unavailable=f"the complete folder at {root} could not be read: {message(exc)}",
        )
    return SideReport(side=ReconcileSide.COMPLETE, counted=len(entries))


async def _ask_library(session: AsyncSession, survey: _Survey) -> SideReport:
    """**逐 Route 問**：那一條的媒體庫目錄在不在（brief §16.2）。

    在的那幾條留進 `survey.library_roots`，底下的帳本才比得了；不在的那幾條跳過並說出它的
    名字——使用者要知道的是「哪一條沒掛上」，而不是「有東西不見了」。

    `enabled` 不在判準裡：停用說的是「不要再往這裡入庫」，不是「裡面的東西不用管了」。
    那些檔案還在 Jellyfin 的媒體庫裡，帳本仍然要對得上。
    """
    routes = list(await session.scalars(select(Route).order_by(Route.id)))
    skipped: list[str] = []
    for route in routes:
        root = Path(route.target_path)
        if root.is_dir():
            survey.library_roots.append(root)
            continue
        skipped.append(f"{route.name} ({route.target_path}) is not there; is the volume mounted?")
        logger.warning(
            "reconcile skipped a route", extra={"route": route.slug, "path": route.target_path}
        )

    survey.library_entries = await _entries_under(session, survey.library_roots)
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


# --- 寫 Issue -----------------------------------------------------------


async def _check_library_links(
    session: AsyncSession, survey: _Survey, now: datetime
) -> tuple[int, int]:
    """`library_link_missing`：帳本有、媒體庫裡那個目標檔不在了（brief §9.1）。

    **只比問得到的那幾條 Route 底下的帳本**。落在跳過的那一條底下的每一列連 `status` 都
    不動——那一欄說的是「比對過的現況」，而這一輪根本沒有比到它。
    """
    opened = updated = 0
    for entry in survey.library_entries:
        try:
            fs.stat(Path(entry.target_path))
        except OSError:
            entry.status = LedgerStatus.TARGET_MISSING
            entry.checked_at = now
            recorded = await record_issue(
                session,
                IssueType.LIBRARY_LINK_MISSING,
                path=entry.target_path,
                job_hash=entry.job_hash,
                ledger_id=entry.id,
                detail={
                    "source": entry.source_abs_path,
                    "media": entry.media_id,
                    "season": entry.season,
                    "episode": entry.episode_start,
                    "action": entry.action.value,
                },
                now=now,
            )
            # **數的是 `record_issue` 真的做了什麼**，不是從帳本的舊狀態推。被忽略過的
            # 那一列帳本仍然是 `target_missing`，而這一輪開的是新的一筆（`ignore` 的意思是
            # 「這一次不想處理」，不是「這件事不存在」）——推出來的答案在那一格會說謊。
            opened, updated = (opened + 1, updated) if recorded.opened else (opened, updated + 1)
            continue
        entry.checked_at = now
        if entry.status is LedgerStatus.TARGET_MISSING:
            # 檔案自己回來了（使用者手動放回去、或別的地方重新鏈接過）。
            entry.status = LedgerStatus.OK
    return opened, updated


async def _entries_under(session: AsyncSession, roots: list[Path]) -> list[LedgerEntry]:
    """帳本裡目標落在這幾個根底下的那幾列。

    在 Python 裡篩而不是用 SQL 的 `LIKE`：路徑比對的規則（正規化、Windows 的大小寫、
    同前綴的兄弟目錄）只能有一份實作，而它在 `fs.is_within`（plan §8.6）。
    """
    if not roots:
        return []
    return [
        entry
        for entry in await session.scalars(select(LedgerEntry).order_by(LedgerEntry.id))
        if any(fs.is_within(Path(entry.target_path), root) for root in roots)
    ]


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
