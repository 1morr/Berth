"""一輪做到底：關機時的 cancel 只落在迴圈等待的時候（M4 票 71b）。

lifespan 關機時 cancel 每一個迴圈。落在等待（sleep、等提示）時什麼都沒握著；落在一輪的資料庫 IO
半途就不一樣——async 下 IO 半途被 cancel 是 SQLAlchemy 不支援的（sqlalchemy#8145）。`db/engine.py`
的 `_connect` 把建連線與 pragma 包在 shield 裡，但連線交回 pool 之後 SQLAlchemy 還要跑方言的
`connect` handler（兩次 `create_function`）；cancel 落在那裡，那條 aiosqlite 連線沒有人關，要等 GC
才 `ResourceWarning`（`tests/integration/test_loop_shutdown.py`）。

代價是關機要等正在跑的那一輪做完，沒有總上限：每一次外部呼叫有逾時，一輪裡可能有好幾次（RSS
依序輪每個到時間的 Feed）。超過 `docker stop` 的寬限就被 SIGKILL，與這之前被打斷一樣——SQLite 的
交易是整筆的。迴圈幾乎所有時間都在等待，所以多半不必等。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable

logger = logging.getLogger(__name__)


async def whole_tick[T](tick: Awaitable[T]) -> T:
    """跑一輪；跑到一半被 cancel 時先讓它做完，再把 cancel 往上傳。

    等它做完的那一段再被 cancel 也不打斷它（`asyncio.wait` 不 cancel 它等的 task）：cancel 照樣
    往上走，那一輪留在背景做完。
    """
    running = asyncio.ensure_future(tick)
    try:
        return await asyncio.shield(running)
    except asyncio.CancelledError:
        await asyncio.wait({running})
        if not running.cancelled() and (failure := running.exception()) is not None:
            # 迴圈的 `except Exception` 接不到了（往上走的是 cancel），在這裡記下。
            task = asyncio.current_task()
            logger.error(
                "tick failed while shutting down",
                extra={"loop": task.get_name() if task else None},
                exc_info=failure,
            )
        raise
