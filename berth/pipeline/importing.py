"""`importer`：Import Plan → 媒體庫的背景迴圈（plan §3.2、票 12）。

迴圈本身只管三件事——什麼時候該做、例外怎麼接、下一次多久之後再來。怎麼鏈接、帳本怎麼寫、
Job 走到哪一站都是 `services/importer.py` 的事（`pipeline` 只呼叫 services，plan §1.3）。

**事件驅動 + 每 60 秒掃一次**（plan §3.2）：planner 算完一份就叫醒它，使用者按下入庫重試也會；
定時的那一輪是重啟之後的補課——提示活在記憶體裡，資料庫裡那一列 `importing` 卻還在。
"""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.services.clients import ServiceClientFactory
from berth.services.events import EventHub
from berth.services.hints import JobHints
from berth.services.importer import ImportOutcome, sweep_imports
from berth.services.setup import is_setup_complete

logger = logging.getLogger(__name__)

#: 沒有人叫醒它時多久自己看一次（plan §3.2）。
TICK = timedelta(seconds=60)


class Importer:
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
        """**先等再做**，與 `planner_runner` 同一個形狀。例外只記 log，迴圈不死（plan §3.2）。"""
        while True:
            await self._hints.wait(self.tick_seconds)
            try:
                await self.tick()
            except Exception:
                logger.exception("importer tick failed")

    async def tick(self) -> ImportOutcome | None:
        """做一輪；精靈跑完之前回 `None`——那時候一條 Route 都還沒有，沒有地方可以放。"""
        async with self._sessions() as session:
            if not await is_setup_complete(session):
                return None
            outcome = await sweep_imports(session, self._clients, self._hub)
            if outcome.imported or outcome.failed or outcome.held:
                logger.debug(
                    "importer round",
                    extra={
                        "imported": outcome.imported,
                        "failed": outcome.failed,
                        "held": outcome.held,
                    },
                )
            return outcome
