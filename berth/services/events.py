"""程序內的事件廣播，`GET /api/events/stream` 的來源（plan §6 events 群組、票 10）。

背景迴圈改了一列 Job，畫面上那一列要**自己**跟著變——不用重新整理，也不用每秒問一次
「有沒有變」。所以迴圈把「這一筆動了」丟進這裡，SSE 端點把它送給每個正開著的分頁。

推出去的**只有身分與一眼看得到的兩格**（狀態與進度），不是整份 Job：

- 前端拿到之後做的事是讓 `['jobs']` 失效再重問一次（plan §7）。真相在資料庫，
  推播只是「該去問了」的提示——這樣一來，推播漏掉一筆的後果是慢一點，不是畫面說謊。
- 狀態與進度仍然帶著，因為它們是**去不去重問的依據**：一輪只動了進度時，沒有展開的
  那幾十列根本不必重畫。

**M5 票 08 起多一種：Proposal**（確認卡）的狀態變了。同一個規矩：只有 id 與狀態，前端讓
`['proposals']` 失效再問一次，看不看得到那一張由列表的門禁決定，不由推播決定。

**publish 是同步的**，而且滿了就丟掉最舊的那一筆：poller 不能因為某個分頁在睡覺而卡住，
而 Job 的事件是「去重問」的提示，最新的那一筆永遠比舊的有價值。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Iterator
from dataclasses import dataclass

from berth.domain import JobState, ProposalStatus

logger = logging.getLogger(__name__)

#: 每個訂閱者的緩衝上限。一個分頁落後這麼多筆時，它要的其實只是「重問一次」，
#: 而那件事最新的那一筆就說得完。
QUEUE_CAPACITY = 128

#: SSE 的 `event:` 名。前端逐種掛 listener，所以它是封閉集合的一員而不是自由文字。
JOB_EVENT = "job"
PROPOSAL_EVENT = "proposal"


@dataclass(frozen=True, slots=True)
class JobSignal:
    """「這一筆 Job 動了」。

    程序內的訊息，不是線上的形狀——送出去的那一份是 `api/events.JobSignalOut`（前端從
    OpenAPI 取它，M2 票 02）。這裡不自己組 JSON，序列化是 api 那一層的事。
    """

    hash: str
    state: JobState
    progress: float


@dataclass(frozen=True, slots=True)
class ProposalSignal:
    """「這一張 Proposal 的狀態變了」。送出去的那一份是 `api/events.ProposalSignalOut`。"""

    id: int
    status: ProposalStatus


#: hub 送的每一種。
Signal = JobSignal | ProposalSignal


class EventHub:
    """一個程序內的 fan-out。訂閱者是「一個正開著的 SSE 連線」。

    不用 `asyncio.Condition` 或第三方的 pub/sub：這裡要的就是「每個訂閱者一條有界佇列」，
    而它的兩個規則（不阻塞發送端、滿了丟最舊的）都是這個問題自己的答案。
    """

    def __init__(self, *, capacity: int = QUEUE_CAPACITY) -> None:
        self._capacity = capacity
        self._queues: set[asyncio.Queue[Signal]] = set()

    @property
    def subscribers(self) -> int:
        """現在有幾條連線開著。只給測試：確認訂閱真的收掉了。"""
        return len(self._queues)

    def publish(self, signal: Signal) -> None:
        """丟給每個訂閱者。**永不阻塞、永不丟例外**——呼叫端是背景迴圈。"""
        for queue in self._queues:
            while True:
                try:
                    queue.put_nowait(signal)
                except asyncio.QueueFull:
                    # 丟最舊的那一筆再試。丟最新的會讓落後的分頁停在一個過期的狀態上。
                    with contextlib.suppress(asyncio.QueueEmpty):
                        queue.get_nowait()
                    continue
                break

    @contextlib.contextmanager
    def subscribe(self) -> Iterator[asyncio.Queue[Signal]]:
        """開一條訂閱，離開時一定收掉——不然斷線的分頁會留下一條永遠沒人讀的佇列。"""
        queue: asyncio.Queue[Signal] = asyncio.Queue(maxsize=self._capacity)
        self._queues.add(queue)
        try:
            yield queue
        finally:
            self._queues.discard(queue)
