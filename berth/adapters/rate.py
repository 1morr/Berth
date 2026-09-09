"""送出去的請求速率上限（plan §8.3）。

給的是「一秒最多幾個、可以先攢多少個」。TMDB 沒有公布上限，員工在論壇說的是約 50 req/s
（brief §20.3），所以 Berth 用 40——留餘裕比貼著跑重要，被擋一次的代價遠大於慢那 20%。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable


class TokenBucket:
    """令牌桶。滿桶時整串突發直接過，之後每個請求各等一格。

    實作記的是**下一個令牌可用的時間**而不是「現在有幾個令牌」，兩者等價
    （令牌數 = 落後現在多少格），但這一種不需要鎖：算出等多久與佔掉那一格之間沒有
    `await`，在 asyncio 裡就是不可分割的，所以並行的呼叫方按抵達順序排隊、不會插隊，
    也不必為了共用一把 `asyncio.Lock` 而綁死在某一個 event loop 上。
    """

    def __init__(
        self,
        *,
        rate: float,
        capacity: int,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._interval = 1.0 / rate
        #: 桶滿時能一次放行幾個。`- 1` 是因為下面存的是「第一個要等的時間」。
        self._burst = (capacity - 1) * self._interval
        self._clock = clock
        self._sleep = sleep
        #: 起點是「桶已經滿了」，不是「剛用掉一個」——第一次呼叫不該等。
        self._next = clock() - self._burst

    async def acquire(self) -> None:
        """輪到自己才回來。要等就在這裡等掉。"""
        now = self._clock()
        # 閒置再久也只攢得到 capacity 個：不 clamp 的話停一天就能一次送三千個出去。
        earliest = max(now - self._burst, self._next)
        self._next = earliest + self._interval
        delay = earliest - now
        if delay > 0:
            await self._sleep(delay)
