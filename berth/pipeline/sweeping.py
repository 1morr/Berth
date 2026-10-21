"""`sweeper`：每日巡檢的排程（plan §3.2、M4 票 129）。

迴圈只管什麼時候跑；一輪做什麼在 `services/sweep.py`。形狀照 `reconciler`：**醒得比跑頻繁**
（每分鐘醒一次，跨過 `SWEEP_AT` 那一刻才真的跑），**第一次的排程從啟動那一刻的前一個
`SWEEP_AT` 起算**（重啟不立刻跑一輪），精靈跑完之前不跑。錯過的那幾天不補跑：巡檢看的是現況。

時刻與 04:00 的對帳錯開：對帳要走過整個媒體庫，一小時後它多半已經跑完（M2 票 11 量過，1,000 部
× 12 集一輪約 30 秒），巡檢看到的是對帳寫完的 Issue。
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta
from datetime import time as clock_time

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.pipeline.reconciling import local_now, previous
from berth.pipeline.ticks import Clock, Sleeper, whole_tick
from berth.services.setup import is_setup_complete
from berth.services.sweep import sweep_once

logger = logging.getLogger(__name__)

#: 醒來的間隔。只是「要不要跑」的判斷頻率。
TICK = timedelta(minutes=1)

#: 每日巡檢的時刻，容器的 `TZ`（同 `RECONCILE_AT`）。
SWEEP_AT = clock_time(5, 0)


class Sweeper:
    """`asyncio.Task` 的內容（plan §3.2）。停止的方式是 cancel 它。"""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        tick: timedelta = TICK,
        at: clock_time = SWEEP_AT,
        sleep: Sleeper = asyncio.sleep,
        now: Clock = local_now,
    ) -> None:
        self._sessions = sessions
        self._tick = tick
        self._at = at
        self._sleep = sleep
        self._now = now
        # 啟動那一刻的前一個 `SWEEP_AT` 已經「算跑過了」。
        self._scheduled_for: datetime = previous(self._now(), self._at)

    async def run(self) -> None:
        """先睡再跑：啟動當下精靈通常還沒跑完。"""
        while True:
            await self._sleep(self._tick.total_seconds())
            try:
                await whole_tick(self.run_if_due())
            except Exception:
                logger.exception("sweeper tick failed")

    async def run_if_due(self) -> bool:
        """跨過 `SWEEP_AT` 了就跑一輪，回傳這一次有沒有真的跑。"""
        moment = self._now()
        due = previous(moment, self._at)
        if due <= self._scheduled_for:
            return False
        # 排程照樣往前走，即使這一次沒真的跑（同 `reconciler`）。
        self._scheduled_for = due
        async with self._sessions() as session:
            if not await is_setup_complete(session):
                return False
            started = time.perf_counter()
            # 門檻照排定的那一刻算，不照醒來的那一刻：每分鐘醒一次，跨過 05:00 的那一次落在哪一秒
            # 不一定，照醒來算的話「3 天」有時是 4 天（code-review）。
            outcome = await sweep_once(session, now=due)
        logger.info(
            "sweep round",
            extra={
                "stuck": outcome.stuck,
                "failing": outcome.failing,
                "missing": outcome.missing,
                "cleared": outcome.cleared,
                "reminded": outcome.reminded,
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
            },
        )
        return True
