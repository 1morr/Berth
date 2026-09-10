"""`qbit_poller`：驅動客戶端狀態那幾個轉換的背景迴圈（plan §3.2、票 10）。

迴圈本身只管三件事——什麼時候該問、例外怎麼接、下一次多久之後再來。問什麼、連線握多久、
轉換怎麼走都是 `services/downloads.py` 的事（`pipeline` 只呼叫 services，plan §1.3）。

**醒得比問頻繁**，與 `health_checker` 同一個形狀：每 5 秒醒一次，但只有距離上一輪滿了
它該等的間隔才真的問。兩層的理由是**送單那一刻**——使用者按下去時多半落在一個 30 秒的
閒置間隔中間，而沿用上一輪算出來的間隔會讓他對著那一列等最多半分鐘才看到第一個變化。
每次醒來重問一次「現在有沒有活躍 job」，那一列就在 5 秒內開始動。

間隔有三種（plan §3.2）：有活躍 job 時 5 秒、否則 30 秒、連續失敗時退避到 5 分鐘。
失敗次數存在 `settings.poller`，所以 Berth 重開之後不會把一台已經連續失敗一小時的
qBittorrent 當成新的來打。

**例外只記 log，迴圈不死**（plan §3.2）：死掉的話下載列表會永遠停在送單那一刻，
而那正是它要回答的問題。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.services.clients import ServiceClientFactory
from berth.services.downloads import (
    ACTIVE_INTERVAL,
    Downloader,
    backoff,
    next_interval,
    record_poll_failure,
)
from berth.services.events import EventHub
from berth.services.setup import is_setup_complete
from berth.services.steps import message

logger = logging.getLogger(__name__)

#: 醒來的間隔。只是「要不要問」的判斷頻率，不是輪詢頻率——而它等於最短的那個間隔，
#: 因為醒得比最短間隔還慢的話，那個間隔就形同虛設。
TICK = ACTIVE_INTERVAL

Sleeper = Callable[[float], Awaitable[None]]
Clock = Callable[[], datetime]


class QbitPoller:
    """`asyncio.Task` 的內容（plan §3.2）。停止的方式是 cancel 它，然後 `aclose`。"""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        clients: ServiceClientFactory,
        hub: EventHub,
        *,
        sleep: Sleeper = asyncio.sleep,
        now: Clock = lambda: datetime.now(UTC),
    ) -> None:
        self._sessions = sessions
        self._downloader = Downloader(clients, hub)
        self._sleep = sleep
        self._now = now
        self._last: datetime | None = None
        #: 連續失敗時的退避。成功就清掉，讓間隔回到 `next_interval` 的判斷。
        self._penalty: timedelta | None = None

    @property
    def tick_seconds(self) -> float:
        return TICK.total_seconds()

    async def run(self) -> None:
        """**先睡再問**：啟動當下精靈通常還沒跑完，而第一輪等一個 tick 不影響任何人。"""
        while True:
            await self._sleep(self.tick_seconds)
            try:
                await self.tick()
            except Exception:
                logger.exception("qbit poller tick failed")

    async def tick(self) -> bool:
        """醒來、看看該不該問、該就問一輪。回傳這一次有沒有真的問。

        精靈跑完之前不問：那時候 qBittorrent 的位址與憑證還沒定下來，打過去只會得到一串
        假的失敗（`health_checker` 的同一條規則）。
        """
        moment = self._now()
        async with self._sessions() as session:
            if not await is_setup_complete(session):
                return False
            wait = self._penalty or await next_interval(session)
            if self._last is not None and moment - self._last < wait:
                return False
            self._last = moment
            try:
                outcome = await self._downloader.poll(session, now=moment)
            except Exception as failure:
                await session.rollback()
                failures = await record_poll_failure(session, message(failure))
                self._penalty = backoff(failures)
                logger.warning(
                    "qbit poller round failed",
                    extra={"failures": failures, "error": message(failure)},
                )
                return True
            self._penalty = None
            logger.debug(
                "qbit poller round",
                extra={"moved": outcome.moved, "unknown": outcome.unknown},
            )
            return True

    async def aclose(self) -> None:
        """放掉握著的 qBittorrent 連線。lifespan 在 cancel 這個 task 之後呼叫它。"""
        await self._downloader.aclose()
