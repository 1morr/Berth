"""`health_checker`：每 5 分鐘跑一次健康檢查的背景迴圈（plan §3.2、票 10）。

迴圈本身只管三件事——什麼時候該跑、跑的時候用哪個 session、例外怎麼接。檢查在做什麼是
`services/health.py` 的事，畫面上那顆「立即重測」按鈕呼叫的是同一支命令。

**醒得比檢查頻繁**：每 30 秒醒一次，但只有上一輪已經滿 5 分鐘才真的跑（`is_due`）。
兩層的理由是精靈剛跑完的那一刻——迴圈在 Berth 啟動時就已經在轉，那時候還沒有東西可檢查，
如果醒來的間隔就是檢查的間隔，使用者按完「完成」會對著一個空的健康頁等五分鐘。

**例外只記 log**：迴圈死掉的話健康頁會永遠停在舊值，而那正是它要回答的問題。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.services.clients import ServiceClientFactory
from berth.services.health import CHECK_INTERVAL, check_health, is_due
from berth.services.setup import is_setup_complete

logger = logging.getLogger(__name__)

#: 醒來的間隔。只是「要不要跑」的判斷頻率，不是檢查頻率。
TICK = timedelta(seconds=30)

Sleeper = Callable[[float], Awaitable[None]]
Clock = Callable[[], datetime]


class HealthChecker:
    """`asyncio.Task` 的內容（plan §3.2）。停止的方式是 cancel 它。"""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        clients: ServiceClientFactory,
        *,
        interval: timedelta = CHECK_INTERVAL,
        tick: timedelta = TICK,
        sleep: Sleeper = asyncio.sleep,
        now: Clock = lambda: datetime.now(UTC),
    ) -> None:
        self._sessions = sessions
        self._clients = clients
        self._interval = interval
        self._tick = tick
        self._sleep = sleep
        self._now = now

    @property
    def tick_seconds(self) -> float:
        return self._tick.total_seconds()

    async def run(self) -> None:
        """醒來、看看該不該檢查、再睡。**先睡再跑**：啟動當下精靈通常還沒跑完。"""
        while True:
            await self._sleep(self.tick_seconds)
            try:
                await self.check_once()
            except Exception:
                # 迴圈不能死。下一次醒來再試一次，畫面上的「上次檢查」會顯示它落後了。
                logger.exception("health checker tick failed")

    async def check_once(self) -> bool:
        """該檢查就檢查一輪，回傳這一次有沒有真的跑。

        精靈跑完之前不跑：那時候正在接的服務被打只會得到假的紅燈，而精靈自己就在做
        這些檢查（plan §9.3、§9.5）。
        """
        async with self._sessions() as session:
            if not await is_setup_complete(session):
                return False
            moment = self._now()
            if not await is_due(session, now=moment, interval=self._interval):
                return False
            await check_health(session, self._clients, now=moment)
            return True
