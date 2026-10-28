"""一輪在伺服器上跑時送出去的片段：誰來看都從頭重播、再跟著（M5 票 25，plan §11.6〈串流〉）。

照 Vercel AI SDK 的 resumable streams：串流記在伺服器，連線只是來看的；重連的那一條從第一個片段重播
（`DefaultChatTransport` 的 `resumeStreamIsReplay` 預設就是重播）。AI SDK 的範例把它放 Redis
（`resumable-stream`），Berth 一個程序一份就夠：`AgentRuntime` 本來就在程序裡。

不知道片段是什麼（`api/agent.py` 放的是 UI message stream 的 chunk），只管排隊與叫醒。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator


class LiveTurn[T]:
    """一輪送出的片段，依序。`end` 之後不再長；之前來看的等著下一個。"""

    def __init__(self) -> None:
        self._items: list[T] = []
        self._changed = asyncio.Event()
        self.ended = False

    def push(self, item: T) -> None:
        self._items.append(item)
        self._wake()

    def end(self) -> None:
        self.ended = True
        self._wake()

    def _wake(self) -> None:
        # 一個 Event 叫醒所有在等的，再換一個新的給下一次等。
        self._changed.set()
        self._changed = asyncio.Event()

    async def follow(self) -> AsyncIterator[T]:
        """從第一個片段起，一直到 `end`。來看的走了（取消）不影響這一輪。"""
        index = 0
        while True:
            while index < len(self._items):
                yield self._items[index]
                index += 1
            if self.ended:
                return
            await self._changed.wait()
