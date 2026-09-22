"""`qbit_poller` 這個背景迴圈本身（plan §3.2、票 10 實跑換來的三條規則）。

轉換表與一輪裡發生的事在 `test_downloads.py`；這裡只驗迴圈扛著的那三條——它們每一條都是
實跑抓到之後才寫進 plan 的，所以每一條都要有自己的閘門（票 01）：

1. **醒得比問頻繁，而且間隔每次醒來重算**：送單那一刻多半落在一個 30 秒的閒置間隔中間。
2. **HTTP client 握著不放**：`sync/maindata` 的 `rid` 增量掛在那條連線的 session 上。
3. **推播在 commit 之後**：反過來的話前端收到提示就重問，而那一次讀到的是舊狀態。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.adapters.qbittorrent import QbittorrentClient, TorrentFile, TorrentStatus
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.config import Config
from berth.db import create_session_factory
from berth.domain import JobState
from berth.pipeline.downloads import QbitPoller
from berth.services.downloads import ACTIVE_INTERVAL, IDLE_INTERVAL
from berth.services.events import EventHub, JobSignal
from berth.services.hints import JobHints
from berth.services.setup import complete_setup
from tests.integration.factories import FakeClientFactory
from tests.integration.test_downloads import FILES, HASH, NOW, setup_job, status

pytestmark = pytest.mark.asyncio


class Clock:
    """可以往前撥的時鐘。迴圈的到期判斷靠它，不靠真的等三十秒。"""

    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now


class Sleeps:
    """記下每次 `sleep` 的秒數；到了次數上限就讓迴圈收工。"""

    def __init__(self, stop_after: int) -> None:
        self.seconds: list[float] = []
        self._stop_after = stop_after

    async def __call__(self, seconds: float) -> None:
        self.seconds.append(seconds)
        if len(self.seconds) >= self._stop_after:
            raise _StopError


class _StopError(Exception):
    """測試用的收工訊號。正式的收工是 task 被 cancel。"""


class OneClientPerCall(FakeClientFactory):
    """每次要 qBittorrent client 都造一個新的，並且記下造了幾個。

    共用的 `FakeClientFactory` 永遠回同一顆，所以「握著不放」在它身上看不出差別——
    重造一個也還是同一顆。
    """

    def __init__(
        self,
        *torrents: TorrentStatus,
        files: dict[str, tuple[TorrentFile, ...]] | None = None,
    ) -> None:
        super().__init__()
        self.made: list[FakeQbittorrentClient] = []
        self._torrents = torrents
        self._files = files or {}

    def qbittorrent(self, base_url: str) -> QbittorrentClient:
        client = FakeQbittorrentClient(torrents=self._torrents, files=dict(self._files))
        client.base_url = base_url
        self.made.append(client)
        return client


class ReadsTheDatabase(EventHub):
    """推播來的那一刻，另一條連線看得到那一筆的哪一個狀態。

    用 `sqlite3` 直接讀：它只讀得到已經 commit 的東西，所以「推播在 commit 之後」
    在這裡就是一個看得見的差別。
    """

    def __init__(self, database: Path) -> None:
        super().__init__()
        self._database = database
        self.states: list[str] = []

    def publish(self, signal: JobSignal) -> None:
        reader = sqlite3.connect(self._database)
        try:
            row = reader.execute("SELECT state FROM jobs WHERE hash = ?", (signal.hash,)).fetchone()
        finally:
            reader.close()
        self.states.append(row[0] if row is not None else "")


def poller(
    engine: AsyncEngine,
    factory: FakeClientFactory,
    *,
    clock: Clock,
    sleep: Sleeps | None = None,
    hub: EventHub | None = None,
) -> QbitPoller:
    return QbitPoller(
        create_session_factory(engine),
        factory,
        hub or EventHub(),
        JobHints(),
        sleep=sleep or Sleeps(1),
        now=clock,
    )


class TestWhenItAsks:
    async def test_it_does_nothing_before_the_wizard_is_finished(
        self, engine: AsyncEngine, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """精靈跑完之前 qBittorrent 的位址與憑證還沒定下來，打過去只會拿到假的失敗。"""
        await setup_job(session, roots, state=JobState.DOWNLOADING)
        factory = OneClientPerCall(status(progress=0.2))

        assert await poller(engine, factory, clock=Clock(NOW)).tick() is False
        assert factory.made == []

    async def test_it_wakes_more_often_than_the_idle_interval(
        self, engine: AsyncEngine, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """醒來的間隔等於最短的那個間隔：醒得比它還慢的話，那個間隔就形同虛設。"""
        await setup_job(session, roots, state=JobState.DOWNLOADING)
        loop = poller(engine, OneClientPerCall(), clock=Clock(NOW))

        assert loop.tick_seconds == ACTIVE_INTERVAL.total_seconds()
        assert loop.tick_seconds < IDLE_INTERVAL.total_seconds()

    async def test_the_interval_is_recomputed_on_every_wake(
        self, engine: AsyncEngine, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """閒置時問完一輪之後有人送單：下一次醒來就該問，不是等滿上一輪算出來的 30 秒。

        沿用上一輪的間隔的話，使用者按下送單的那一刻多半落在一個閒置間隔中間，他要對著
        那一列等最多半分鐘才看到第一個變化（plan §3.2，票 10 實跑）。
        """
        job = await setup_job(session, roots, state=JobState.IMPORTED)
        await complete_setup(session)
        clock = Clock(NOW)
        loop = poller(engine, OneClientPerCall(), clock=clock)
        # 閒置的一輪：這一輪算出來的間隔是 30 秒。
        assert await loop.tick() is True

        job.state = JobState.DOWNLOADING
        await session.commit()
        clock.now = NOW + ACTIVE_INTERVAL

        assert await loop.tick() is True

    async def test_it_stays_quiet_until_the_interval_it_just_computed_is_up(
        self, engine: AsyncEngine, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """另一個方向：沒有東西變的話，5 秒醒一次不等於 5 秒問一次。"""
        await setup_job(session, roots, state=JobState.IMPORTED)
        await complete_setup(session)
        clock = Clock(NOW)
        loop = poller(engine, OneClientPerCall(), clock=clock)
        await loop.tick()

        clock.now = NOW + ACTIVE_INTERVAL
        assert await loop.tick() is False

        clock.now = NOW + IDLE_INTERVAL
        assert await loop.tick() is True


class TestTheConnection:
    async def test_the_same_client_carries_every_round(
        self, engine: AsyncEngine, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`sync/maindata` 的 `rid` 增量掛在那條連線的 session 上（brief §20.2 實測）。

        每輪重造一個 client 等於每輪都要一份全量，而那正是 `rid` 要避免的事。
        """
        await setup_job(session, roots, state=JobState.DOWNLOADING)
        await complete_setup(session)
        clock = Clock(NOW)
        factory = OneClientPerCall(status(progress=0.2))
        loop = poller(engine, factory, clock=clock)

        await loop.tick()
        clock.now = NOW + ACTIVE_INTERVAL
        await loop.tick()
        await loop.aclose()

        assert len(factory.made) == 1
        assert factory.made[0].syncs == 2

    async def test_a_failed_round_drops_it_so_the_next_one_starts_over(
        self, engine: AsyncEngine, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """重造就是重新開始，而重新開始本來就會拿到一次全量——兩邊因此自然對齊。"""
        await setup_job(session, roots, state=JobState.DOWNLOADING)
        await complete_setup(session)
        clock = Clock(NOW)
        factory = OneClientPerCall(status(progress=0.2))
        loop = poller(engine, factory, clock=clock)
        await loop.tick()
        factory.made[0].sync_error = RuntimeError("connection reset")

        clock.now = NOW + ACTIVE_INTERVAL
        assert await loop.tick() is True
        clock.now = NOW + timedelta(minutes=10)
        assert await loop.tick() is True
        await loop.aclose()

        assert len(factory.made) == 2


class TestThePush:
    async def test_the_signal_goes_out_after_the_round_is_committed(
        self,
        engine: AsyncEngine,
        session: AsyncSession,
        roots: dict[str, Path],
        config: Config,
    ) -> None:
        """推播是「該去問了」的提示，而那件事只有在真相已經寫下去之後才成立。

        反過來的話前端收到「這一筆完成了」就立刻重問，讀到的卻是還沒 commit 的舊狀態，
        畫面因此永遠慢一步（票 10 實跑抓到：每一筆事件都把畫面推到**上一個**狀態）。
        """
        job = await setup_job(session, roots, state=JobState.SUBMITTED)
        await complete_setup(session)
        hub = ReadsTheDatabase(config.database_path)
        # 檔案清單到手，這一輪真的把它搬離 `submitted`——狀態沒變的話兩種順序看起來一樣。
        factory = OneClientPerCall(status(progress=0.2), files={HASH: FILES})
        loop = poller(engine, factory, clock=Clock(NOW), hub=hub)

        await loop.tick()
        await loop.aclose()

        await session.refresh(job)
        assert job.state is not JobState.SUBMITTED
        # 推播當下另一條連線看到的就是這一輪的新狀態，不是上一個。
        assert hub.states == [job.state.value]


class TestTheLoop:
    async def test_it_sleeps_between_ticks(
        self, engine: AsyncEngine, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await setup_job(session, roots, state=JobState.DOWNLOADING)
        sleeps = Sleeps(stop_after=3)
        loop = poller(engine, OneClientPerCall(), clock=Clock(NOW), sleep=sleeps)

        with pytest.raises(_StopError):
            await loop.run()

        assert sleeps.seconds == [loop.tick_seconds] * 3

    async def test_one_failed_tick_does_not_kill_the_loop(
        self,
        engine: AsyncEngine,
        session: AsyncSession,
        roots: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """死掉的話下載列表會永遠停在送單那一刻，而那正是它要回答的問題（plan §3.2）。"""
        await setup_job(session, roots, state=JobState.DOWNLOADING)
        await complete_setup(session)
        sleeps = Sleeps(stop_after=2)
        loop = poller(engine, OneClientPerCall(), clock=Clock(NOW), sleep=sleeps)
        calls = 0

        async def explode(*args: object, **kwargs: object) -> bool:
            nonlocal calls
            calls += 1
            raise RuntimeError("the database went away")

        monkeypatch.setattr(loop, "tick", explode)

        with pytest.raises(_StopError):
            await loop.run()

        assert calls == 1, "第一次 tick 炸掉之後迴圈還要再睡一次"
