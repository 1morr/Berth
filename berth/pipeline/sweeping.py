"""`sweeper`：每日巡檢的排程（plan §3.2、M4 票 129）。

迴圈只管什麼時候跑；一輪做什麼在 `services/sweep.py`。形狀照 `reconciler`：**醒得比跑頻繁**
（每分鐘醒一次，跨過 `SWEEP_AT` 那一刻才真的跑），**第一次的排程從啟動那一刻的前一個
`SWEEP_AT` 起算**（重啟不立刻跑一輪），精靈跑完之前不跑。錯過的那幾天不補跑：巡檢看的是現況。

時刻與 04:00 的對帳錯開：對帳要走過整個媒體庫，一小時後它多半已經跑完（M2 票 11 量過，1,000 部
× 12 集一輪約 30 秒），巡檢看到的是對帳寫完的 Issue。

**週報也在這裡**（M4 票 131，`services/weekly.py`）：每一次醒來看「最新一份該有的週報」（在最近的
週一 `SWEEP_AT` 結束的那一週）有沒有，沒有就產生。同一個 tick 裡排在巡檢之後，週一那一份看到的是
當天巡檢開完的 Issue。與巡檢不同，**重啟之後補上漏掉的那一週**：一週才一份，週一早上剛好在重啟就
少一份是看得出來的缺口；同一週再產生什麼都不寫，所以補跑不會多一筆。只有新裝、還一份都沒有時不補：
啟動那一刻已經過去的那一週 Berth 還沒在做事。

**過期的確認卡也在這裡收**（M5 票 08，`services/proposals.expire_due`）：每一次醒來都收，不等
`SWEEP_AT`——卡片的期限以分鐘計，畫面上還開著的那一張要跟著變成「已過期」，所以要 hub。
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
from berth.services.events import EventHub
from berth.services.proposals import expire_due
from berth.services.setup import is_setup_complete
from berth.services.sweep import sweep_once
from berth.services.weekly import compose_weekly, has_reports, week_ending

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
        hub: EventHub,
        *,
        tick: timedelta = TICK,
        at: clock_time = SWEEP_AT,
        sleep: Sleeper = asyncio.sleep,
        now: Clock = local_now,
    ) -> None:
        self._sessions = sessions
        self._hub = hub
        self._tick = tick
        self._at = at
        self._sleep = sleep
        self._now = now
        # 啟動那一刻的前一個 `SWEEP_AT` 已經「算跑過了」。
        self._scheduled_for: datetime = previous(self._now(), self._at)
        # 週報確定有了的最後一週（它結束的那一刻）。`None` 是這個行程還沒看過。
        self._reported_through: datetime | None = None

    async def run(self) -> None:
        """先睡再跑：啟動當下精靈通常還沒跑完。"""
        while True:
            await self._sleep(self._tick.total_seconds())
            try:
                await whole_tick(self.expire_proposals())
            except Exception:
                logger.exception("proposal expiry tick failed")
            try:
                await whole_tick(self.run_if_due())
            except Exception:
                logger.exception("sweeper tick failed")
            # 巡檢那一輪壞了不擋週報：週報的「還有什麼等人」讀的是清單，不是巡檢的結果。
            try:
                await whole_tick(self.report_if_due())
            except Exception:
                logger.exception("weekly report tick failed")

    async def expire_proposals(self) -> list[int]:
        """過了期限還沒人按的確認卡標成過期，回傳是哪幾張。"""
        async with self._sessions() as session:
            return await expire_due(session, self._hub, now=self._now())

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
                "colliding": outcome.colliding,
                "cleared": outcome.cleared,
                "reminded": outcome.reminded,
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
            },
        )
        return True

    async def report_if_due(self) -> bool:
        """最新一份該有的週報還沒有就產生，回傳這一次有沒有真的寫了一份。"""
        ends_at = week_ending(self._now(), self._at)
        if self._reported_through is not None and ends_at <= self._reported_through:
            return False
        async with self._sessions() as session:
            if not await is_setup_complete(session):
                return False
            if self._reported_through is None and not await has_reports(session):
                # 新裝的：已經過去的那一週不補，第一份從下一個週一起。
                self._reported_through = ends_at
                return False
            # 排程照樣往前走，即使這一次寫壞了（同巡檢）：每分鐘重試一個壞掉的會每分鐘記一次例外。
            # 漏掉的那一週由下一次啟動補上。
            self._reported_through = ends_at
            made = await compose_weekly(session, ends_at=ends_at, now=self._now())
        return made is not None
