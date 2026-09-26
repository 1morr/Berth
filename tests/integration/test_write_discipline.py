"""寫交易紀律（plan §3.3，M4 票 01）：**先拿 `job_lock`、再開寫；網路呼叫不在寫交易裡**。

SQLite 一次只有一個寫者（WAL 讓讀不擋寫，寫仍然互斥），其他寫者最多等 `busy_timeout`（5 秒，
`berth/db/engine.py`）就爆 `database is locked`。2026-09-26 試跑一次綁定 144 個 torrent，poller
握著寫交易逐筆等 `job_lock`、planner 握著 `job_lock` 等寫鎖，pre-plan 就這樣爆了。

閘門是 `write_locked`：另開一條連線試 `BEGIN IMMEDIATE`、不等（`timeout=0`）。拿不到就是**現在有人
握著寫鎖**——看的是 SQLite 本身，不是 session 的內部狀態，所以哪一種寫法（flush、`execute(update)`、
autoflush）開的交易都逃不掉。每一處打網路的替身包一層 `watch`，被呼叫的那一刻量一次。
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Awaitable, Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.qbittorrent import TorrentFile
from berth.config import Config
from berth.db import create_session_factory
from berth.domain import EventType, JobState, JobTrigger
from berth.models import Event, Job, PollerSettings, RssSeries
from berth.services.deletion import DeleteScope, delete_job
from berth.services.downloads import poll_downloads
from berth.services.events import EventHub
from berth.services.hints import JobHints
from berth.services.jobs import (
    add_download,
    job_lock,
    record_event,
    resubmit_job,
    retry_job,
    transition,
)
from berth.services.plan import plan_id_of, sweep_plans
from berth.services.rss import add_feed, bind_series, poll_feed
from berth.services.settings import read_settings, write_settings
from tests.integration.arrange import applied_qbittorrent, arrange, factory_for
from tests.integration.test_deletion import imported
from tests.integration.test_downloads import status
from tests.integration.test_jobs import MAGNET_HASH, _media, _route, _source
from tests.integration.test_plan import HASH, NOW, downloaded_job, ready
from tests.integration.test_rss import FEED_URL, harbour
from tests.integration.test_rss_backfill import subscribed
from tests.integration.test_rss_screen import SINGLE_URL

pytestmark = pytest.mark.asyncio


def write_locked(database: Path) -> bool:
    """現在有沒有別的連線握著 SQLite 的寫鎖。"""
    probe = sqlite3.connect(database, timeout=0, isolation_level=None)
    try:
        probe.execute("BEGIN IMMEDIATE")
    except sqlite3.OperationalError as exc:
        if "locked" not in str(exc):
            raise
        return True
    else:
        probe.execute("ROLLBACK")
        return False
    finally:
        probe.close()


def watch(target: object, method: str, database: Path) -> list[bool]:
    """把 `target.method`（一次網路呼叫）換成「先量寫鎖、再照原樣做」。回每一次量到的結果。

    替身的方法是實例屬性，指派回去就是「這一輪改問這個」（`arrange.delete_once_during_checks`
    同一招）。
    """
    seen: list[bool] = []
    original: Callable[..., Awaitable[Any]] = getattr(target, method)

    async def probed(*args: Any, **kwargs: Any) -> Any:
        seen.append(write_locked(database))
        return await original(*args, **kwargs)

    setattr(target, method, probed)
    return seen


class _Wire:
    """只有一個網路呼叫的假東西：閘門自己的變異測試用。"""

    async def call(self) -> str:
        return "answer"


class TestTheProbe:
    """閘門的雙向變異：造一個違規證明它會紅，換一種無害的寫法證明它不會紅。"""

    async def test_a_flushed_write_is_caught_on_the_wire(
        self, session: AsyncSession, roots: dict[str, Path], config: Config
    ) -> None:
        await arrange(session, roots)
        wire = _Wire()
        seen = watch(wire, "call", config.database_path)
        settings = await read_settings(session, PollerSettings)
        settings.failures = 1
        await write_settings(session, settings)
        await session.flush()

        await wire.call()
        await session.rollback()
        await wire.call()

        # 握著的那一次紅，rollback 之後放掉了。
        assert seen == [True, False]

    async def test_a_cas_update_is_caught_without_any_flush(
        self, session: AsyncSession, roots: dict[str, Path], config: Config
    ) -> None:
        """`transition` 走 `execute(update(...))`，不經過 flush：寫鎖照樣在它之後就握著了。"""
        media, route, _ = await ready(session, roots)
        job = await downloaded_job(session, media, route, roots, state=JobState.DOWNLOADING)
        wire = _Wire()
        seen = watch(wire, "call", config.database_path)

        await transition(session, job, JobState.STALLED, expected=JobState.DOWNLOADING)
        await wire.call()
        await session.rollback()

        assert seen == [True]

    async def test_reads_and_unflushed_changes_are_not_a_write(
        self, session: AsyncSession, roots: dict[str, Path], config: Config
    ) -> None:
        """讀（session 的交易已經開了）與還沒 flush 的改動都不是握著寫鎖。"""
        media, route, _ = await ready(session, roots)
        job = await downloaded_job(session, media, route, roots, state=JobState.DOWNLOADING)
        wire = _Wire()
        seen = watch(wire, "call", config.database_path)

        await session.scalars(select(Job))
        job.progress = 0.5
        await wire.call()
        await session.rollback()

        assert seen == [False]


# --- poller 與 planner -------------------------------------------------

#: 兩筆 `submitted` 的 hash 都排在 `HASH`（`4bd…`）前面：poller 不論照 rowid 還是照主鍵走，都先處理
#: 它們——排在後面的話它走到那一筆的鎖之前一個字都還沒寫，測不到鎖的順序。
FIRST = "0" * 40
SLOW = "1" * 40
FILES = (TorrentFile(index=0, name="Release/E01.mkv", size=1_000, priority=1, progress=0.0),)


async def _submitted(session: AsyncSession, job_hash: str, media_id: str, route_id: int) -> None:
    session.add(
        Job(
            hash=job_hash,
            name=f"Release {job_hash[:4]}",
            source_url=f"magnet:?xt=urn:btih:{job_hash}",
            trigger=JobTrigger.MANUAL,
            media_id=media_id,
            route_id=route_id,
            state=JobState.SUBMITTED,
        )
    )
    await session.commit()


class TestPollerAndPlanner:
    async def test_a_preplan_during_a_poller_round_does_not_hit_database_is_locked(
        self,
        session: AsyncSession,
        engine: AsyncEngine,
        roots: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """2026-09-26 試跑的形狀：poller 一輪裡某一筆的 `files()` 慢，那幾秒 planner 替另一筆算
        pre-plan。兩邊拿鎖的順序相反時，planner 握著那一筆的 `job_lock` 等寫鎖、poller 握著寫鎖等
        同一把 `job_lock`，planner 等滿 `busy_timeout` 就爆（`round_failed`）。

        `busy_timeout` 縮到 1 秒只是讓紅燈那一次不必等 5 秒：連線是第一次用到時才開，所以在這裡
        改得到。順序：先到的兩筆 `submitted`（poller 照 rowid 走，第一筆轉換之後就握著寫鎖），
        最後一筆是等 pre-plan 的 `downloading`。
        """
        monkeypatch.setattr("berth.db.engine.BUSY_TIMEOUT_MS", 1_000)
        media, route, factory = await ready(session, roots)
        await _submitted(session, FIRST, media.id, route.id)
        await _submitted(session, SLOW, media.id, route.id)
        await downloaded_job(session, media, route, roots, state=JobState.DOWNLOADING)
        client = factory.qbittorrent_
        client.torrents = (
            status(info_hash=FIRST, category=route.category),
            status(info_hash=SLOW, category=route.category),
            status(info_hash=HASH, category=route.category, progress=0.5),
        )
        client.files_by_hash = {FIRST: FILES, SLOW: FILES}
        sessions = create_session_factory(engine)
        planner: asyncio.Task[None] | None = None

        async def plan_meanwhile() -> None:
            async with sessions() as other:
                await sweep_plans(other, factory, EventHub(), now=NOW)

        files = client.files

        async def slow_files(info_hash: str) -> tuple[TorrentFile, ...]:
            nonlocal planner
            if info_hash == SLOW and planner is None:
                planner = asyncio.create_task(plan_meanwhile())
                await asyncio.sleep(0.3)
            return await files(info_hash)

        # 替身的方法是實例屬性，指派回去就是「這一輪改問這個」；mypy 不讓指派方法。
        client.files = slow_files  # type: ignore[method-assign]

        await poll_downloads(session, client, EventHub(), JobHints(), now=NOW)
        assert planner is not None
        await planner

        failed = await session.scalars(
            select(Event.payload_json).where(
                Event.job_hash == HASH, Event.type == EventType.ROUND_FAILED.value
            )
        )
        assert list(failed) == []
        assert await plan_id_of(session, HASH) is not None
        states = dict((await session.execute(select(Job.hash, Job.state))).tuples().all())
        assert states[FIRST] is JobState.METADATA_READY
        assert states[SLOW] is JobState.METADATA_READY

    async def test_the_poller_takes_the_job_locks_before_it_writes(
        self,
        session: AsyncSession,
        engine: AsyncEngine,
        roots: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """鎖的順序那一半：別人握著一筆的 `job_lock` 要寫時，poller 在等那把鎖而且**還沒開寫**。

        上一條測試的 planner 在 `files()` 那幾百毫秒裡就寫完了，驗不到這一半——保留預先問清單、
        改回「握著寫交易逐筆拿鎖」的話它照樣綠。這裡鎖從 poller 開始之前就握著，一路握到 poller
        一定已經走到它面前。`FIRST` 排在前面：舊的順序下 poller 寫完它才來等這把鎖。
        """
        monkeypatch.setattr("berth.db.engine.BUSY_TIMEOUT_MS", 1_000)
        media, route, factory = await ready(session, roots)
        await _submitted(session, FIRST, media.id, route.id)
        await downloaded_job(session, media, route, roots, state=JobState.DOWNLOADING)
        client = factory.qbittorrent_
        client.torrents = (
            status(info_hash=FIRST, category=route.category),
            status(info_hash=HASH, category=route.category, progress=0.5),
        )
        client.files_by_hash = {FIRST: FILES}
        sessions = create_session_factory(engine)
        holding = asyncio.Event()

        async def hold_and_write() -> None:
            async with job_lock(HASH):
                holding.set()
                await asyncio.sleep(0.3)
                async with sessions() as other:
                    job = await other.get(Job, HASH)
                    assert job is not None
                    await record_event(
                        other, job, EventType.PROGRESS, actor="user", payload={"held": True}
                    )
                    await other.commit()

        holder = asyncio.create_task(hold_and_write())
        await holding.wait()
        await poll_downloads(session, client, EventHub(), JobHints(), now=NOW)
        await holder

        states = dict((await session.execute(select(Job.hash, Job.state))).tuples().all())
        assert states[FIRST] is JobState.METADATA_READY

    async def test_the_poller_asks_for_file_lists_outside_the_write_transaction(
        self, session: AsyncSession, roots: dict[str, Path], config: Config
    ) -> None:
        """第一筆轉換之後第二筆的 `torrents/files` 不能在寫交易裡問：qBittorrent 慢的那幾秒，
        每一個寫者（API、RSS、planner）都在等。"""
        media, route, factory = await ready(session, roots)
        await _submitted(session, FIRST, media.id, route.id)
        await _submitted(session, SLOW, media.id, route.id)
        client = factory.qbittorrent_
        client.torrents = (
            status(info_hash=FIRST, category=route.category),
            status(info_hash=SLOW, category=route.category),
        )
        client.files_by_hash = {FIRST: FILES, SLOW: FILES}
        seen = watch(client, "files", config.database_path)

        await poll_downloads(session, client, EventHub(), JobHints(), now=NOW)

        assert seen == [False, False]
        states = set(await session.scalars(select(Job.state)))
        assert states == {JobState.METADATA_READY}


# --- 其他握著寫交易打網路的地方 -----------------------------------------


class TestNetworkOutsideTheWriteTransaction:
    async def test_rss_reads_episode_pages_before_it_writes(
        self, session: AsyncSession, roots: dict[str, Path], config: Config
    ) -> None:
        """Mikan 的單集頁一筆一個請求、逾時 30 秒：寫下第一筆之後才抓第二頁的話，整輪都握著寫鎖。"""
        _, _, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        seen = watch(factory.rss_, "fetch", config.database_path)

        polled = await poll_feed(session, factory, feed.id, now=NOW)

        assert polled.items == 12
        assert len(seen) > 12
        assert not any(seen)

    async def test_binding_reads_the_single_feed_before_it_writes(
        self, session: AsyncSession, roots: dict[str, Path], config: Config
    ) -> None:
        """綁定時補舊集要讀一次單一 feed；綁定本身的改動等讀完再寫。"""
        media, route, factory, _, series_id = await subscribed(session, roots)
        seen = watch(factory.rss_, "fetch", config.database_path)

        bound = await bind_series(
            session, factory, series_id, media_id=media.id, route_id=route.id, user_id=1, now=NOW
        )

        assert bound.submitted > 0
        assert seen
        assert not any(seen)

    async def test_the_daily_backfill_reads_before_it_writes(
        self, session: AsyncSession, roots: dict[str, Path], config: Config
    ) -> None:
        """每日補漏（`_backfill_due`）讀單一 feed 與綁定時補舊集是同一個請求，同一條規矩。"""
        media, route, factory, feed_id, series_id = await subscribed(session, roots)
        await bind_series(
            session, factory, series_id, media_id=media.id, route_id=route.id, user_id=1, now=NOW
        )
        series = await session.get(RssSeries, series_id)
        assert series is not None
        series.backfilled_at = NOW - timedelta(days=2)
        await session.commit()
        seen = watch(factory.rss_, "fetch", config.database_path)
        before = len(factory.rss_.requested)

        await poll_feed(session, factory, feed_id, now=NOW)

        assert SINGLE_URL in factory.rss_.requested[before:]
        assert not any(seen)
        await session.refresh(series)
        assert series.backfilled_at == NOW

    async def test_deletion_removes_the_torrent_before_it_writes(
        self, session: AsyncSession, roots: dict[str, Path], config: Config
    ) -> None:
        job, _, factory = await imported(session, roots)
        seen = watch(factory.qbittorrent_, "delete_torrent", config.database_path)

        await delete_job(session, factory, job.hash, DeleteScope(remove_torrent=True), actor="user")

        assert seen == [False]
        assert await session.scalar(select(Job.state).where(Job.hash == job.hash)) is (
            JobState.REMOVED
        )

    async def test_a_retry_fetches_and_submits_outside_the_write_transaction(
        self, session: AsyncSession, roots: dict[str, Path], config: Config
    ) -> None:
        """重試先進 `requested` 再抓 `.torrent`、送 qBittorrent：與第一次送單一樣先 commit。"""
        await arrange(session, roots)
        media = await _media(session)
        route = await _route(session, roots)
        qbittorrent = applied_qbittorrent(roots, add_error=ServiceUnavailableError("down"))
        factory = factory_for(roots, qbittorrent=qbittorrent)
        await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )
        qbittorrent.add_error = None
        fetched = watch(factory.torrent_, "fetch", config.database_path)
        added = watch(qbittorrent, "add_torrent", config.database_path)

        job = await retry_job(session, factory, MAGNET_HASH)

        assert job.state is JobState.SUBMITTED
        assert fetched == [False]
        assert added == [False]

    async def test_a_resubmit_sends_outside_the_write_transaction(
        self, session: AsyncSession, roots: dict[str, Path], config: Config
    ) -> None:
        """Issue 的「重新送單」（`client_removed`）走同一段收尾。"""
        await arrange(session, roots)
        media = await _media(session)
        route = await _route(session, roots)
        factory = factory_for(roots)
        await add_download(
            session, factory, source=_source(), media_id=media.id, route_id=route.id, user_id=None
        )
        job = await session.get(Job, MAGNET_HASH)
        assert job is not None
        await transition(session, job, JobState.CLIENT_REMOVED, expected=JobState.SUBMITTED)
        await session.commit()
        added = watch(factory.qbittorrent_, "add_torrent", config.database_path)

        view = await resubmit_job(
            session,
            factory,
            MAGNET_HASH,
            expected=frozenset({JobState.CLIENT_REMOVED}),
            actor="user",
        )

        assert view.state is JobState.SUBMITTED
        assert added == [False]
