"""`planner_runner`：下載完成 → Import Plan 的背景迴圈（plan §3.2、票 11）。

迴圈本身只管三件事——什麼時候該算、例外怎麼接、下一次多久之後再來。算什麼、怎麼算、
算完之後 Job 走到哪一站都是 `services/plan.py` 的事（`pipeline` 只呼叫 services，plan §1.3）。

**事件驅動 + 每 60 秒掃一次**（plan §3.2）：poller 動了任何一筆就 `nudge()`，所以下載完成
到「規劃中」之間不必等一個完整的間隔；而定時的那一輪是重啟之後的補課——提示活在記憶體裡，
Berth 重開的那一刻它們就不見了，資料庫裡那一列 `completed` 卻還在。

**例外只記 log，迴圈不死**（plan §3.2）：死掉的話每一筆下載都會停在「下載完成」，
而使用者會以為 Berth 把他的檔案忘了。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.services.clients import ServiceClientFactory
from berth.services.events import EventHub
from berth.services.hints import JobHints
from berth.services.plan import PlanOutcome, sweep_plans
from berth.services.setup import is_setup_complete

logger = logging.getLogger(__name__)

#: 沒有人叫醒它時多久自己看一次（plan §3.2）。
TICK = timedelta(seconds=60)

Waiter = Callable[[float], Awaitable[bool]]


class PlannerRunner:
    """`asyncio.Task` 的內容（plan §3.2）。停止的方式是 cancel 它。"""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        clients: ServiceClientFactory,
        hub: EventHub,
        hints: JobHints,
        *,
        tick: timedelta = TICK,
    ) -> None:
        self._sessions = sessions
        self._clients = clients
        self._hub = hub
        self._hints = hints
        self._tick = tick

    @property
    def tick_seconds(self) -> float:
        return self._tick.total_seconds()

    async def run(self) -> None:
        """**先等再算**：啟動當下精靈通常還沒跑完，而第一輪等一個提示不影響任何人。

        被叫醒與等到時間了走的是同一條路——提示只是讓同一輪早一點發生。
        """
        while True:
            await self._hints.wait(self.tick_seconds)
            try:
                await self.tick()
            except Exception:
                logger.exception("planner runner tick failed")

    async def tick(self) -> PlanOutcome | None:
        """算一輪，回傳這一輪做了什麼；精靈跑完之前回 `None`。

        精靈跑完之前不算：那時候一條 Route 都還沒有，而 Plan 的目標路徑正是 Route 給的。
        """
        async with self._sessions() as session:
            if not await is_setup_complete(session):
                return None
            outcome = await sweep_plans(session, self._clients, self._hub)
            if outcome.planned or outcome.preplanned:
                logger.debug(
                    "planner runner round",
                    extra={"planned": outcome.planned, "preplanned": outcome.preplanned},
                )
            return outcome
