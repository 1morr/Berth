"""`GET /events/stream`：把背景迴圈的動靜推給正開著的分頁（plan §6 events 群組、票 10）。

送單之後畫面上那一列要自己走完 `submitted → … → completed`。做法有三種，這裡選了第三種：

- 每 N 秒重問一次整份清單。閒著的分頁會替後端加上一份永遠不停的負擔，而使用者多數時間
  根本沒開著這一頁。
- WebSocket。雙向的協定用來做單向的事，還要自己處理重連。
- **SSE**。單向、走一般的 HTTP、瀏覽器內建自動重連，而 Berth 要送的正好是「有東西動了」。

門禁不必為它開洞：`/api/events` 不在白名單上，所以未登入一律 401；`EventSource` 送不了
自訂標頭，但它是 GET，而 CSRF 標頭只要求非 GET（`api/gate.py`）。

推出去的是**提示不是真相**：前端收到之後讓 `['jobs']` 失效再問一次（plan §7）。漏掉一筆
的後果因此是慢一點，不是畫面說謊——而 `ping` 讓中間的反向代理不會把閒著的連線掐掉。
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import anyio
from fastapi import APIRouter
from sse_starlette import EventSourceResponse

from berth.api.deps import EventHubDep
from berth.services.events import JOB_EVENT, EventHub

router = APIRouter(prefix="/events", tags=["events"])

#: 沒有事件時多久送一次註解 ping。反向代理常見的閒置逾時是 60 秒。
PING_SECONDS = 20

#: 關機時留給串流說再見的時間。必須小於 uvicorn 的 graceful shutdown 逾時，
#: 否則收工要等一個完整的逾時（sse-starlette 的建議）。
SHUTDOWN_GRACE_SECONDS = 2.0


@router.get("/stream")
async def stream(hub: EventHubDep) -> EventSourceResponse:
    """一條 SSE 連線。斷線或關機時一定收掉訂閱。"""
    shutdown = anyio.Event()
    return EventSourceResponse(
        _signals(hub, shutdown),
        ping=PING_SECONDS,
        shutdown_event=shutdown,
        shutdown_grace_period=SHUTDOWN_GRACE_SECONDS,
        headers={"Cache-Control": "no-store"},
    )


async def _signals(hub: EventHub, shutdown: anyio.Event) -> AsyncIterator[dict[str, Any]]:
    """訂閱、把每一筆丟出去，直到 Berth 收工或分頁關掉。

    **等待是「佇列或關機，誰先來」，不是每秒醒一次看看。** 逾時版本每秒都會取消一次
    `queue.get()`，而取消一個正在被喚醒的 getter 是 `asyncio.Queue` 最細的那一段語意——
    一條開著幾小時的連線會做上萬次那個動作。這裡的 getter 只在真的收工時才被取消一次。

    **斷線不在這裡查。** `EventSourceResponse` 自己有一個 task 在讀 ASGI 的 `receive`；
    在這裡再呼叫一次 `request.is_disconnected()` 就是同一條 receive 通道上的第二個讀者，
    兩邊會互相把訊息搶走。訂閱的收尾交給 `with`：連線結束時產生器被關掉，`with` 一定跑完。
    """
    with hub.subscribe() as queue:
        stopping = asyncio.ensure_future(shutdown.wait())
        try:
            while not shutdown.is_set():
                waiting = asyncio.ensure_future(queue.get())
                done, _ = await asyncio.wait(
                    (waiting, stopping), return_when=asyncio.FIRST_COMPLETED
                )
                if waiting not in done:
                    waiting.cancel()
                    return
                yield {"event": JOB_EVENT, "data": json.dumps(waiting.result().payload())}
        finally:
            stopping.cancel()
