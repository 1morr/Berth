"""對帳的排程迴圈本身（plan §3.2 的 `reconciler`、M2 票 05）。

驗的是「不會在不該跑的時候跑、也不會在該跑的時候不跑」——一輪在做什麼是
`test_reconcile.py` 的事。

排程只有一條規則：**跨過 04:00 就開一輪，一個 04:00 只開一次**。它可以用三種方式壞掉，
而三種都是靜的：每次醒來都跑一輪（對帳要走過整個媒體庫）、永遠不跑（使用者以為有排程）、
精靈還沒跑完就跑（那時候什麼都還沒有）。所以三種各驗一條。

`M2 票 01` 記過五個迴圈裡 `QbitPoller` 是唯一沒有測試的那一個；這個迴圈不重複那個債。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.db import create_session_factory
from berth.models import SetupSettings
from berth.pipeline.reconciling import Reconciler
from berth.services.reconcile import ReconcileRunner
from berth.services.settings import read_settings, write_settings
from tests.integration.factories import FakeClientFactory

pytestmark = pytest.mark.asyncio

#: 03:30，也就是**還沒**跨過今天的 04:00。
BEFORE = datetime(2026, 9, 22, 3, 30, tzinfo=UTC)
AFTER = datetime(2026, 9, 22, 4, 30, tzinfo=UTC)
TOMORROW = AFTER + timedelta(days=1)


class Clock:
    """可以往前撥的時鐘。排程的到期判斷靠它，不靠真的等到凌晨四點。"""

    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now


def build(engine: AsyncEngine, clock: Clock) -> tuple[Reconciler, ReconcileRunner]:
    sessions = create_session_factory(engine)
    runner = ReconcileRunner(sessions, FakeClientFactory())
    return Reconciler(sessions, runner, now=clock), runner


async def ready(session: AsyncSession) -> None:
    """把「精靈跑完了」那一個位元打開。

    不走 `complete_setup`：它要 TMDB 綠燈與每一條 Route 綠燈（plan §9.3 第 8 步），而這一份
    問的是排程，不是精靈的完成條件。
    """
    setup = await read_settings(session, SetupSettings)
    setup.completed = True
    await write_settings(session, setup)
    await session.commit()


class TestWhenItRuns:
    async def test_it_does_not_run_before_the_hour_is_crossed(
        self, engine: AsyncEngine, session: AsyncSession
    ) -> None:
        await ready(session)
        clock = Clock(BEFORE)
        loop, runner = build(engine, clock)

        # 同一天裡醒好幾次：啟動那一刻的前一個 04:00 已經算跑過了。
        assert await loop.run_if_due() is False
        clock.now = BEFORE + timedelta(minutes=20)
        assert await loop.run_if_due() is False
        assert runner.status().last is None

    async def test_it_runs_once_the_hour_is_crossed(
        self, engine: AsyncEngine, session: AsyncSession
    ) -> None:
        await ready(session)
        clock = Clock(BEFORE)
        loop, runner = build(engine, clock)

        clock.now = AFTER

        assert await loop.run_if_due() is True
        await runner.wait()
        assert runner.status().last is not None

    async def test_one_boundary_only_opens_one_run(
        self, engine: AsyncEngine, session: AsyncSession
    ) -> None:
        """**每分鐘醒一次**，所以「跨過了」在同一天裡會成立一千多次。

        沒有這一條的話對帳會整天不停地跑——而它要走過整個媒體庫。
        """
        await ready(session)
        clock = Clock(BEFORE)
        loop, runner = build(engine, clock)
        clock.now = AFTER
        assert await loop.run_if_due() is True
        await runner.wait()

        clock.now = AFTER + timedelta(hours=3)

        assert await loop.run_if_due() is False

    async def test_the_next_day_opens_another(
        self, engine: AsyncEngine, session: AsyncSession
    ) -> None:
        await ready(session)
        clock = Clock(BEFORE)
        loop, runner = build(engine, clock)
        clock.now = AFTER
        await loop.run_if_due()
        await runner.wait()

        clock.now = TOMORROW

        assert await loop.run_if_due() is True
        await runner.wait()

    async def test_a_run_already_going_is_not_doubled(
        self, engine: AsyncEngine, session: AsyncSession
    ) -> None:
        """使用者剛按過「立刻對帳」而 04:00 到了：同一份磁碟不必比兩次。"""
        await ready(session)
        clock = Clock(BEFORE)
        loop, runner = build(engine, clock)
        await runner.start()
        clock.now = AFTER

        assert await loop.run_if_due() is False

        # 讓它自己跑完而不是 cancel：cancel 一個正卡在查詢裡的 task 會讓 aiosqlite 的
        # worker thread 拋例外，而那與這一條要驗的規則無關。
        await runner.wait()


class TestBeforeTheWizardIsDone:
    async def test_it_does_not_run(self, engine: AsyncEngine) -> None:
        """那時候還沒有 Route、也還沒有帳本，走一輪只會把「什麼都沒有」比一遍。"""
        clock = Clock(BEFORE)
        loop, runner = build(engine, clock)

        clock.now = AFTER

        assert await loop.run_if_due() is False
        assert runner.status().last is None

    async def test_the_schedule_still_moves_on(
        self, engine: AsyncEngine, session: AsyncSession
    ) -> None:
        """精靈跑完之後要等的是**下一個** 04:00，不是把積欠的那幾天補跑一遍。

        沒有這一條的話，精靈跑完的那一刻會立刻觸發一輪——而使用者正在看精靈的完成畫面。
        """
        clock = Clock(BEFORE)
        loop, runner = build(engine, clock)
        clock.now = AFTER
        await loop.run_if_due()

        await ready(session)

        assert await loop.run_if_due() is False
        assert runner.status().last is None


class TestTheLoopItself:
    async def test_a_tick_that_throws_does_not_kill_it(
        self, engine: AsyncEngine, session: AsyncSession
    ) -> None:
        """迴圈死掉的話排程會靜靜地再也不跑，而沒有任何東西會說。"""
        await ready(session)
        clock = Clock(AFTER)
        loop, _ = build(engine, clock)
        sleeps: list[float] = []

        async def sleep(seconds: float) -> None:
            sleeps.append(seconds)
            if len(sleeps) == 1:
                clock.now = _Exploding()  # type: ignore[assignment]
            elif len(sleeps) == 2:
                clock.now = TOMORROW
            else:
                raise _StopError

        loop._sleep = sleep
        with pytest.raises(_StopError):
            await loop.run()

        assert len(sleeps) == 3


class _Exploding:
    """讀它就炸。用來讓一次 tick 丟例外。"""

    def __getattr__(self, name: str) -> object:
        raise RuntimeError("the clock is broken this tick")


class _StopError(Exception):
    """測試用的收工訊號。正式的收工是 task 被 cancel。"""
