"""`notify_sender`：把待送表上到時間的通知送出去（plan §11.5〈通知〉、M4 票 123）。

迴圈只管什麼時候醒；送誰、送什麼、沒送到怎麼記都在 `services/notify.py`，排程存在待送表那一列。

**每 10 秒醒一次**，問一句帶索引的「有沒有到時間的」：「可以看了」在 Jellyfin 認出來之後最多晚
這麼久，而沒有東西要送的那幾輪一個請求都不發。沒有提示：寫入的那一刻多半在 resolver 的交易裡，
叫醒它省下的不到 10 秒。

**每一輪先看守「等你處理」**（`watch_waiting`，M4 票 127）：三份清單的身分各問一次，與上一輪一樣
就不寫任何東西。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.pipeline.ticks import whole_tick
from berth.services.clients import ServiceClientFactory
from berth.services.notify import SendOutcome, send_due, watch_waiting

logger = logging.getLogger(__name__)

TICK = timedelta(seconds=10)


class NotifySender:
    """`asyncio.Task` 的內容（plan §3.2）。停止的方式是 cancel 它。"""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        clients: ServiceClientFactory,
        *,
        tick: timedelta = TICK,
    ) -> None:
        self._sessions = sessions
        self._clients = clients
        self._tick = tick

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self._tick.total_seconds())
            try:
                await whole_tick(self.tick())
            except Exception:
                logger.exception("notify sender tick failed")

    async def tick(self) -> SendOutcome:
        async with self._sessions() as session:
            # 看守不 commit：它寫的與 `send_due` 開頭那一次 commit 一起落地，一輪只借一次連線。
            await watch_waiting(session)
            outcome = await send_due(session, self._clients)
        if outcome.sent or outcome.failed:
            logger.info(
                "notify sender round", extra={"sent": outcome.sent, "failed": outcome.failed}
            )
        return outcome
