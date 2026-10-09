"""關機時背景迴圈的那一輪做完才收（M4 票 71b）。

lifespan 關機時 cancel 每一個迴圈。cancel 落在一輪的資料庫 IO 半途——SQLAlchemy 剛建好一條連線、
還在跑 `connect` handler（aiosqlite 方言的兩次 `create_function`）的那一段——pool 不會關掉那條
連線（async 下 IO 半途被 cancel 是 SQLAlchemy 不支援的，sqlalchemy#8145）。它要等 GC 才
`ResourceWarning`，`filterwarnings = error` 底下就變成全套 pytest 裡**之後隨便哪一條測試**的錯誤：
票 55、59、70 各撞到一次、單跑都過的那三條與這個機制對得上（當時沒留輸出，屬旁證）。

這裡把 cancel 釘在那一段：連線建好、`connect` handler 停住，這時候 cancel 迴圈；第二次 cancel
是 lifespan 自己被 cancel 時轉過來的那一次。放大的量測在
`scripts/experiments/loop_shutdown_leak.py`。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.util import await_only

from berth import pipeline
from berth.db import create_session_factory
from berth.pipeline import (
    HealthChecker,
    Importer,
    JellyfinResolver,
    PlannerRunner,
    QbitPoller,
    Reconciler,
    RssPoller,
    resolving,
)
from berth.services.events import EventHub
from berth.services.hints import JobHints
from berth.services.reconcile import ReconcileRunner
from tests.integration.factories import FakeClientFactory

Sessions = async_sessionmaker[AsyncSession]


class Loop(Protocol):
    async def run(self) -> None: ...


async def at_once(_seconds: float) -> None:
    """第一次等待就醒：這裡要的是一輪正在跑的時候，不是間隔。"""


def day_later() -> Callable[[], datetime]:
    """對帳排程的時鐘：建構時是今天，之後每一次都已跨過明天的 04:00，於是第一輪就到時間。"""
    start = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
    calls = iter([start])
    return lambda: next(calls, start + timedelta(days=1))


#: 每一個背景迴圈，建成「一醒來就跑一輪」。`test_every_loop_is_here` 守著這張表跟得上 `pipeline`。
LOOPS: dict[type[Loop], Callable[[Sessions], Loop]] = {
    QbitPoller: lambda s: QbitPoller(s, FakeClientFactory(), EventHub(), JobHints(), sleep=at_once),
    HealthChecker: lambda s: HealthChecker(s, FakeClientFactory(), sleep=at_once),
    PlannerRunner: lambda s: PlannerRunner(
        s, FakeClientFactory(), EventHub(), JobHints(), import_hints=JobHints(), tick=timedelta()
    ),
    Importer: lambda s: Importer(s, FakeClientFactory(), EventHub(), JobHints(), tick=timedelta()),
    JellyfinResolver: lambda s: JellyfinResolver(s, FakeClientFactory()),
    Reconciler: lambda s: Reconciler(
        s, ReconcileRunner(s, FakeClientFactory()), sleep=at_once, now=day_later()
    ),
    RssPoller: lambda s: RssPoller(s, FakeClientFactory(), sleep=at_once),
}


def test_every_loop_is_here() -> None:
    exported = {name for name in pipeline.__all__ if name != "TICK"}

    assert {loop.__name__ for loop in LOOPS} == exported


@pytest.mark.asyncio
@pytest.mark.parametrize("cancels", [1, 2])
@pytest.mark.parametrize("kind", LOOPS, ids=lambda kind: kind.__name__)
async def test_a_cancel_mid_round_still_closes_every_connection(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch, kind: type[Loop], cancels: int
) -> None:
    monkeypatch.setattr(resolving, "TICK", timedelta())
    opened: list[Any] = []
    closed: list[Any] = []
    held = asyncio.Event()
    release = asyncio.Event()
    returned = asyncio.Event()

    def hold(dbapi_connection: Any, _record: Any) -> None:
        opened.append(dbapi_connection)
        held.set()
        await_only(release.wait())

    pool = engine.sync_engine.pool
    event.listen(pool, "connect", hold, insert=True)
    event.listen(pool, "close", lambda dbapi_connection, _record: closed.append(dbapi_connection))
    event.listen(pool, "checkin", lambda _dbapi_connection, _record: returned.set())
    sessions = create_session_factory(engine)

    running = asyncio.create_task(LOOPS[kind](sessions).run())
    await held.wait()
    for _ in range(cancels):
        running.cancel()
        # 讓 cancel 先送到那一輪手上，再放行 `connect` handler。
        for _ in range(5):
            await asyncio.sleep(0)
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await running
    # 第二次 cancel 之後那一輪留在背景做完；等它把連線還回 pool 再收 engine。
    await asyncio.wait_for(returned.wait(), timeout=5)
    await engine.dispose()

    assert opened
    assert [c for c in opened if c not in closed] == []
