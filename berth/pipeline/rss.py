"""`rss_poller`：每個 Feed 照自己的間隔輪詢的背景迴圈（plan §3.2、M3 票 08）。

與 `health_checker` 同一個形狀：**醒得比輪詢頻繁**（每 30 秒醒一次，哪幾個 Feed 到時間了由
`services/rss.poll_due` 看各自的 `interval_sec`），精靈跑完之前不做事，例外只記 log。
一輪在做什麼是 `services/rss.py` 的事，畫面上那一顆「立即輪詢」呼叫的是同一支 `poll_feed`。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.services.clients import ServiceClientFactory
from berth.services.rss import poll_due
from berth.services.setup import is_setup_complete

logger = logging.getLogger(__name__)

#: 醒來的間隔。只是「有沒有 Feed 到時間」的判斷頻率，不是輪詢頻率。
TICK = timedelta(seconds=30)

Sleeper = Callable[[float], Awaitable[None]]
Clock = Callable[[], datetime]


class RssPoller:
    """`asyncio.Task` 的內容（plan §3.2）。停止的方式是 cancel 它。"""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        clients: ServiceClientFactory,
        *,
        tick: timedelta = TICK,
        sleep: Sleeper = asyncio.sleep,
        now: Clock = lambda: datetime.now(UTC),
    ) -> None:
        self._sessions = sessions
        self._clients = clients
        self._tick = tick
        self._sleep = sleep
        self._now = now

    async def run(self) -> None:
        """醒來、輪到時間的、再睡。**先睡再跑**：啟動當下不必搶著打外面的站。"""
        while True:
            await self._sleep(self._tick.total_seconds())
            try:
                await self.poll_once()
            except Exception:
                # 迴圈不能死；一個 Feed 的失敗在 `poll_due` 裡就接住了，走到這裡的是資料庫那一層。
                logger.exception("rss poller tick failed")

    async def poll_once(self) -> int:
        """到時間的 Feed 各輪一次，回輪了幾個。精靈跑完之前不輪：那時候還沒有 Route 可送。"""
        async with self._sessions() as session:
            if not await is_setup_complete(session):
                return 0
            return await poll_due(session, self._clients, now=self._now())
