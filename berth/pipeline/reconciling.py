"""`reconciler`：每日 04:00 那一輪的排程（plan §3.2、M2 票 05）。

迴圈本身只管一件事——**什麼時候該按那顆按鈕**。按下去之後發生什麼是
`services/reconcile.ReconcileRunner` 的事，而畫面上那顆「立刻對帳」按的是同一個物件：
「一次只有一輪」因此只有一份判斷（`api` 不可以 import `pipeline`，所以那份判斷本來就
只能住在 services，plan §1.3）。

**醒得比跑頻繁**（同 `health_checker`）：每分鐘醒一次，只有跨過 04:00 那一刻才真的開一輪。

**第一次的排程從啟動那一刻的前一個 04:00 起算**：不這樣的話每次重啟都會立刻跑一輪，而
一輪要走過整個媒體庫。代價是剛好在 04:00 之前重啟的那一天會跳過——那一天按得到那顆按鈕，
而量完大媒體庫的成本之後會重新看這個排程（plan §11.3 決定 2）。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.services.reconcile import ReconcileRunner
from berth.services.setup import is_setup_complete

logger = logging.getLogger(__name__)

#: 醒來的間隔。只是「要不要跑」的判斷頻率，不是對帳頻率。
TICK = timedelta(minutes=1)

#: 每日排程的時刻，**容器的 `TZ`**（compose 範本預設 `Etc/UTC`，plan §3.2）。
#: 04:00 是刻意的離峰：那時候沒有人在看媒體庫，而一輪要走過整個媒體庫。
RECONCILE_AT = time(4, 0)

Sleeper = Callable[[float], Awaitable[None]]
Clock = Callable[[], datetime]


def local_now() -> datetime:
    """容器時區的現在。**帶 tzinfo**：與 `RECONCILE_AT` 比的是牆上的時刻。"""
    return datetime.now().astimezone()


class Reconciler:
    """`asyncio.Task` 的內容（plan §3.2）。停止的方式是 cancel 它。"""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        runner: ReconcileRunner,
        *,
        tick: timedelta = TICK,
        at: time = RECONCILE_AT,
        sleep: Sleeper = asyncio.sleep,
        now: Clock = local_now,
    ) -> None:
        self._sessions = sessions
        self._runner = runner
        self._tick = tick
        self._at = at
        self._sleep = sleep
        self._now = now
        # 啟動那一刻的前一個 04:00 已經「算跑過了」，所以第一次排程是下一個 04:00。
        self._scheduled_for = previous(self._now(), self._at)

    @property
    def tick_seconds(self) -> float:
        return self._tick.total_seconds()

    async def run(self) -> None:
        """醒來、看看該不該跑、再睡。**先睡再跑**：啟動當下精靈通常還沒跑完。"""
        while True:
            await self._sleep(self.tick_seconds)
            try:
                await self.run_if_due()
            except Exception:
                # 迴圈不能死。下一次醒來再試一次。
                logger.exception("reconciler tick failed")

    async def run_if_due(self) -> bool:
        """跨過 04:00 了就開一輪，回傳這一次有沒有真的開。

        精靈跑完之前不跑：那時候還沒有 Route、也還沒有帳本，走一輪只會把「什麼都沒有」
        比一遍（同 `health_checker`）。
        """
        moment = self._now()
        due = previous(moment, self._at)
        if due <= self._scheduled_for:
            return False

        # **排程照樣往前走**，即使這一次沒真的跑：精靈跑完之後要等的是下一個 04:00，
        # 而不是把積欠的那幾天補跑一遍。
        self._scheduled_for = due
        async with self._sessions() as session:
            if not await is_setup_complete(session):
                return False
        if self._runner.running:
            # 手動按的那一輪還在跑。今天的排程就算它跑過了——同一份磁碟不必比兩次。
            return False
        await self._runner.start()
        return True


def previous(now: datetime, at: time) -> datetime:
    """`now` 之前最近的那一個 `at`（今天的，或還沒到就是昨天的）。

    比「下一次是什麼時候」好用：排程的判斷是「有沒有跨過某一個 04:00」，而跨過的定義是
    最近那一個 04:00 比上次跑的那一個新。換日光節約時間的那一天也只是多一小時或少一小時，
    不會漏跑、也不會跑兩次。
    """
    today = now.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
    return today if today <= now else today - timedelta(days=1)
