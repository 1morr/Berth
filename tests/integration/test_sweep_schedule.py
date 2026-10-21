"""每日巡檢的排程迴圈本身（plan §3.2 的 `sweeper`、M4 票 129）。

一輪做什麼是 `test_sweep.py` 與 `test_sweep_reminder.py` 的事；這裡只驗「什麼時候跑」。規則同
`reconciler`：**跨過 `SWEEP_AT` 就跑一輪，一個 `SWEEP_AT` 只跑一次，重啟不立刻跑**。巡檢一輪
做了沒有，看它開了沒有那一件「第一批卡住」。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.db import create_session_factory
from berth.pipeline.sweeping import SWEEP_AT, Sweeper
from berth.services.notify import send_due
from tests.integration.factories import FakeClientFactory
from tests.integration.test_plan import NOW
from tests.integration.test_reconciler_schedule import Clock, ready
from tests.integration.test_sweep import STOPPED, bound_series, stuck_issues, stuck_job
from tests.integration.test_sweep_reminder import waiting_since_seen

pytestmark = pytest.mark.asyncio

#: 還沒跨過今天的 `SWEEP_AT`。Job 停在 `STOPPED`，到這時已經停了兩天。
DAY = (STOPPED + timedelta(days=2)).date()
BEFORE = datetime.combine(DAY, SWEEP_AT, tzinfo=UTC) - timedelta(minutes=30)
AFTER = datetime.combine(DAY, SWEEP_AT, tzinfo=UTC) + timedelta(minutes=30)


def build(engine: AsyncEngine, clock: Clock) -> Sweeper:
    return Sweeper(create_session_factory(engine), now=clock)


async def stuck(session: AsyncSession) -> None:
    await ready(session)
    await stuck_job(session, await bound_series(session))


class TestWhenItRuns:
    async def test_starting_up_does_not_run_it(
        self, engine: AsyncEngine, session: AsyncSession
    ) -> None:
        """重啟在 `SWEEP_AT` 之後：今天的那一個已經算跑過了，不是一啟動就跑一輪。"""
        await stuck(session)
        loop = build(engine, Clock(AFTER))

        assert await loop.run_if_due() is False
        assert await stuck_issues(session) == []

    async def test_it_runs_once_the_hour_is_crossed(
        self, engine: AsyncEngine, session: AsyncSession
    ) -> None:
        await stuck(session)
        clock = Clock(BEFORE)
        loop = build(engine, clock)
        assert await loop.run_if_due() is False

        clock.now = AFTER

        assert await loop.run_if_due() is True
        assert len(await stuck_issues(session)) == 1

    async def test_one_day_only_runs_once(self, engine: AsyncEngine, session: AsyncSession) -> None:
        await stuck(session)
        clock = Clock(BEFORE)
        loop = build(engine, clock)
        clock.now = AFTER
        assert await loop.run_if_due() is True

        clock.now = AFTER + timedelta(hours=12)

        assert await loop.run_if_due() is False

    async def test_the_next_day_runs_again(
        self, engine: AsyncEngine, session: AsyncSession
    ) -> None:
        await stuck(session)
        clock = Clock(BEFORE)
        loop = build(engine, clock)
        clock.now = AFTER
        await loop.run_if_due()

        clock.now = AFTER + timedelta(days=1)

        assert await loop.run_if_due() is True

    async def test_not_before_setup_is_complete(
        self, engine: AsyncEngine, session: AsyncSession
    ) -> None:
        await stuck_job(session, await bound_series(session))
        clock = Clock(BEFORE)
        loop = build(engine, clock)
        clock.now = AFTER

        assert await loop.run_if_due() is False
        assert await stuck_issues(session) == []


class TestTheRoundIsTheScheduledHour:
    async def test_three_days_later_is_three_days_whatever_minute_it_woke(
        self, engine: AsyncEngine, session: AsyncSession
    ) -> None:
        """每分鐘醒一次：跨過 05:00 的那一次落在 05:00 到 05:01 之間。門檻照醒來的那一刻算的話，
        第 0 天 05:00:42 提醒過、第 3 天 05:00:15 醒來只差 2 天 23 小時多，
        要拖到第 4 天（code-review）。"""
        await ready(session)
        factory = FakeClientFactory()
        await waiting_since_seen(session, factory)
        due = datetime.combine((NOW + timedelta(days=4)).date(), SWEEP_AT, tzinfo=UTC)
        clock = Clock(due - timedelta(hours=1))
        loop = build(engine, clock)

        clock.now = due + timedelta(seconds=42)
        assert await loop.run_if_due() is True
        await send_due(session, factory, now=clock.now + timedelta(seconds=10))
        assert len(factory.discord_.sent) == 1

        clock.now = due + timedelta(days=3, seconds=15)
        assert await loop.run_if_due() is True
        await send_due(session, factory, now=clock.now + timedelta(seconds=10))
        assert len(factory.discord_.sent) == 2
