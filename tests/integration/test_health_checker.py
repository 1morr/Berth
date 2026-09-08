"""背景迴圈本身（plan §3.2、票 10）。

驗的是「迴圈不會死、不會在不該跑的時候跑、也不會在該跑的時候不跑」——檢查各項在做什麼是
`test_health_service.py` 的事。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.db import create_session_factory
from berth.domain import HealthStatus, ServiceKind
from berth.models import HealthSettings
from berth.pipeline.health import HealthChecker
from berth.services.health import CHECK_INTERVAL, check_health
from berth.services.settings import read_settings
from berth.services.setup import complete_setup
from tests.integration.arrange import NOW
from tests.integration.factories import FakeClientFactory
from tests.integration.test_health_service import ready

pytestmark = pytest.mark.asyncio


class Clock:
    """可以往前撥的時鐘。迴圈的到期判斷靠它，不靠真的等五分鐘。"""

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


async def checker(
    engine: AsyncEngine,
    factory: FakeClientFactory,
    *,
    clock: Clock,
    sleep: Sleeps | None = None,
) -> HealthChecker:
    return HealthChecker(
        create_session_factory(engine),
        factory,
        now=clock,
        sleep=sleep or Sleeps(1),
    )


class TestWhenItRuns:
    async def test_it_does_nothing_before_the_wizard_is_finished(
        self, engine: AsyncEngine, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """精靈自己就在做這些檢查，而它還沒接完的服務被打只會得到假的紅燈。"""
        factory = await ready(session, roots)
        loop = await checker(engine, factory, clock=Clock(NOW))

        assert await loop.check_once() is False
        assert (await read_settings(session, HealthSettings)).checked_at is None

    async def test_it_checks_once_the_wizard_is_finished(
        self, engine: AsyncEngine, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots)
        await complete_setup(session)
        loop = await checker(engine, factory, clock=Clock(NOW))

        assert await loop.check_once() is True

        stored = await read_settings(session, HealthSettings)
        assert stored.checked_at == NOW
        assert stored.routes is HealthStatus.OK

    async def test_it_waits_out_the_interval_before_checking_again(
        self, engine: AsyncEngine, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots)
        await complete_setup(session)
        clock = Clock(NOW)
        loop = await checker(engine, factory, clock=clock)
        await loop.check_once()

        clock.now = NOW + timedelta(minutes=1)
        assert await loop.check_once() is False

        clock.now = NOW + CHECK_INTERVAL
        assert await loop.check_once() is True

    async def test_a_service_that_went_down_turns_red_within_one_interval(
        self, engine: AsyncEngine, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """票 10 的驗收：停掉任一服務後 5 分鐘內該項變紅。"""
        factory = await ready(session, roots)
        await complete_setup(session)
        clock = Clock(NOW)
        loop = await checker(engine, factory, clock=clock)
        await loop.check_once()

        factory.prowlarr_.ping_error = ServiceUnavailableError("connection refused")
        clock.now = NOW + CHECK_INTERVAL
        await loop.check_once()

        stored = await read_settings(session, HealthSettings)
        assert stored.services[ServiceKind.PROWLARR].status is HealthStatus.FAILED


class TestTheLoop:
    async def test_it_sleeps_between_ticks(
        self, engine: AsyncEngine, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots)
        sleeps = Sleeps(stop_after=3)
        loop = await checker(engine, factory, clock=Clock(NOW), sleep=sleeps)

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
        """迴圈的例外只記 log，不讓它死掉（plan §3.2）。死掉的話健康頁會永遠停在舊值。"""
        factory = await ready(session, roots)
        await complete_setup(session)
        sleeps = Sleeps(stop_after=2)
        loop = await checker(engine, factory, clock=Clock(NOW), sleep=sleeps)

        calls = 0

        async def explode(*args: object, **kwargs: object) -> None:
            nonlocal calls
            calls += 1
            raise RuntimeError("the database went away")

        monkeypatch.setattr("berth.pipeline.health.check_health", explode)

        with pytest.raises(_StopError):
            await loop.run()

        assert calls == 1, "第一次 tick 炸掉之後迴圈還要再睡一次"

    async def test_check_health_is_what_the_loop_calls(
        self, engine: AsyncEngine, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """迴圈與畫面上那顆按鈕跑的是同一支命令。"""
        factory = await ready(session, roots)
        await complete_setup(session)
        clock = Clock(NOW)
        loop = await checker(engine, factory, clock=clock)

        await loop.check_once()
        from_loop = await read_settings(session, HealthSettings)

        clock.now = NOW + CHECK_INTERVAL
        await check_health(session, factory, now=clock.now)
        from_button = await read_settings(session, HealthSettings)

        assert set(from_loop.services) == set(from_button.services)
        assert from_loop.routes is from_button.routes
