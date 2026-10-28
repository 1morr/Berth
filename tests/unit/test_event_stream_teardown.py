"""SSE 串流收尾不能留下孤兒 task（e2e log 的「Task was destroyed but it is pending!」）。

分頁關掉時，`EventSourceResponse` 取消正在跑 body iterator 的 task；`_signals` 那時停在
`asyncio.wait((waiting, stopping))`。`asyncio.wait` 被取消不會取消它在等的 future，所以
`waiting`（`queue.get()` 的 task）沒人收，等 GC 回收佇列時才印出那一行。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import anyio
import pytest

from berth.api.events import _signals
from berth.services.events import EventHub

pytestmark = pytest.mark.asyncio


def _others() -> set[asyncio.Task[Any]]:
    return {task for task in asyncio.all_tasks() if task is not asyncio.current_task()}


async def _drive(
    hub: EventHub, shutdown: anyio.Event
) -> tuple[AsyncGenerator[dict[str, Any]], asyncio.Task[dict[str, Any]]]:
    """像 sse-starlette 一樣在另一個 task 裡迭代，停在等佇列的那一步。"""
    stream = _signals(hub, shutdown)
    assert isinstance(stream, AsyncGenerator)  # 宣告成 AsyncIterator；要 aclose 得先收窄
    task = asyncio.ensure_future(anext(stream))
    await asyncio.sleep(0.01)
    assert hub.subscribers == 1
    return stream, task


async def test_a_closed_tab_leaves_no_pending_queue_getter() -> None:
    hub = EventHub()
    before = _others()
    stream, task = await _drive(hub, anyio.Event())

    task.cancel()  # 分頁關掉：sse-starlette 取消串流的 task group
    with pytest.raises(asyncio.CancelledError):
        await task
    await stream.aclose()
    await asyncio.sleep(0.01)

    assert hub.subscribers == 0
    assert _others() - before == set()


async def test_shutting_down_leaves_no_pending_queue_getter() -> None:
    hub = EventHub()
    before = _others()
    shutdown = anyio.Event()
    _, task = await _drive(hub, shutdown)

    shutdown.set()
    with pytest.raises(StopAsyncIteration):
        await task
    await asyncio.sleep(0.01)

    assert hub.subscribers == 0
    assert _others() - before == set()
