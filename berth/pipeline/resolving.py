"""`jellyfin_resolver`：入庫的檔案在 Jellyfin 裡是哪一個 item（plan §3.2、票 12）。

迴圈只管什麼時候醒；問誰、怎麼比、重試排到什麼時候都在 `services/resolver.py`，而排程存在
帳本那一列上。

**沒有提示，只有一個短的 tick**（plan §3.2 寫的是「事件驅動」）：最短的重試間隔是 30 秒，
而第一次反查本來就排在入庫 30 秒之後——importer 那一刻叫醒它，它醒來看到的也只是「還沒到」。
所以它每 15 秒醒一次，問一句帶索引的「有沒有到時間的」，沒有就繼續睡。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.services.clients import ServiceClientFactory
from berth.services.resolver import ResolveOutcome, sweep_resolutions
from berth.services.setup import is_setup_complete

logger = logging.getLogger(__name__)

#: 醒來的間隔。比最短的重試間隔（30 秒）短，所以任何一次重試最多晚這麼久。
TICK = timedelta(seconds=15)


class JellyfinResolver:
    """`asyncio.Task` 的內容（plan §3.2）。停止的方式是 cancel 它。"""

    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], clients: ServiceClientFactory
    ) -> None:
        self._sessions = sessions
        self._clients = clients

    async def run(self) -> None:
        while True:
            await asyncio.sleep(TICK.total_seconds())
            try:
                await self.tick()
            except Exception:
                logger.exception("jellyfin resolver tick failed")

    async def tick(self) -> ResolveOutcome | None:
        async with self._sessions() as session:
            if not await is_setup_complete(session):
                return None
            outcome = await sweep_resolutions(session, self._clients)
            if outcome.resolved or outcome.retried or outcome.exhausted:
                logger.debug(
                    "jellyfin resolver round",
                    extra={
                        "resolved": outcome.resolved,
                        "retried": outcome.retried,
                        "exhausted": outcome.exhausted,
                    },
                )
            return outcome
