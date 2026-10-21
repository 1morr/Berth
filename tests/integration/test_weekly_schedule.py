"""週報的排程（M4 票 131）：`sweeper` 每分鐘醒，跨過週一 `SWEEP_AT` 就產生在那一刻結束的一週。

一份做什麼是 `test_weekly.py` 的事；這裡只驗「什麼時候產生」。規則：

- 跨過週一 05:00 產生一份；同一週之後再醒也不多一份。
- **重啟之後補上漏掉的那一週**：週一那一刻 Berth 沒在跑的話，下一次醒來補上（`compose_weekly` 對
  同一週什麼都不寫，所以補跑不會多一筆）。
- **新裝的 Berth 不補**：還沒有任何一份時，啟動那一刻已經過去的那一週不產生——那一週 Berth 還沒在
  做事，第一份從下一個週一起。
- 精靈跑完之前不產生。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.db import create_session_factory
from berth.pipeline.sweeping import SWEEP_AT, Sweeper
from berth.services.weekly import compose_weekly, list_reports
from tests.integration.test_reconciler_schedule import Clock, ready

pytestmark = pytest.mark.asyncio

#: 2026-10-26 是週一。
MONDAY = datetime.combine(date(2026, 10, 26), SWEEP_AT, tzinfo=UTC)
SUNDAY_NIGHT = MONDAY - timedelta(hours=6)


def build(engine: AsyncEngine, clock: Clock) -> Sweeper:
    return Sweeper(create_session_factory(engine), now=clock)


async def weeks(session: AsyncSession) -> list[date]:
    return [line.first_day for line in await list_reports(session)]


class TestWhenTheWeekIsWritten:
    async def test_crossing_monday_morning_writes_the_week_once(
        self, engine: AsyncEngine, session: AsyncSession
    ) -> None:
        await ready(session)
        clock = Clock(SUNDAY_NIGHT)
        loop = build(engine, clock)
        assert await loop.report_if_due() is False

        clock.now = MONDAY + timedelta(minutes=1)
        assert await loop.report_if_due() is True
        clock.now = MONDAY + timedelta(days=1)
        assert await loop.report_if_due() is False

        assert await weeks(session) == [date(2026, 10, 19)]

    async def test_a_restart_after_a_missed_monday_catches_up(
        self, engine: AsyncEngine, session: AsyncSession
    ) -> None:
        """上一週有一份；這個週一 05:00 Berth 沒在跑，週二才起來：醒來就補上這一週，只補一次。"""
        await ready(session)
        await compose_weekly(session, ends_at=MONDAY - timedelta(days=7))
        loop = build(engine, Clock(MONDAY + timedelta(days=1)))

        assert await loop.report_if_due() is True
        assert await loop.report_if_due() is False

        assert await weeks(session) == [date(2026, 10, 19), date(2026, 10, 12)]

    async def test_a_fresh_install_waits_for_the_next_monday(
        self, engine: AsyncEngine, session: AsyncSession
    ) -> None:
        await ready(session)
        clock = Clock(MONDAY + timedelta(days=2))
        loop = build(engine, clock)

        assert await loop.report_if_due() is False
        assert await weeks(session) == []

        clock.now = MONDAY + timedelta(days=7, minutes=1)
        assert await loop.report_if_due() is True
        assert await weeks(session) == [date(2026, 10, 26)]

    async def test_nothing_before_the_wizard_is_done(
        self, engine: AsyncEngine, session: AsyncSession
    ) -> None:
        clock = Clock(SUNDAY_NIGHT)
        loop = build(engine, clock)
        clock.now = MONDAY + timedelta(minutes=1)

        assert await loop.report_if_due() is False
        assert await weeks(session) == []
