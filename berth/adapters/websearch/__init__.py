"""網路搜尋的 adapter 介面（M5 票 17、plan §11.6〈外部資料〉）。

一個問題：**這串查詢、限在這幾個網域，網路上有哪幾頁**。實作只有 Tavily（`tavily.py`，REST），
介面不認它：之後換 SearXNG 或別家，services 不動（研究 08 §4 的建議 2）。

回來的每一頁都是**外部內容**：標題與摘錄是別人寫的字，不是指令（services 與 agent 照這個處理）。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class WebPage:
    title: str
    url: str
    #: 這一頁跟查詢有關的摘錄（Tavily 的 `content`），已截短。
    content: str


class WebSearch(Protocol):
    async def search(
        self, query: str, *, domains: Sequence[str], max_results: int
    ) -> list[WebPage]:
        """搜一次。`domains` 空的是不限（Berth 永遠給一份）。

        key 被拒是 `AuthFailedError`，限流與 5xx 是 `ServiceUnavailableError`，服務拒絕這次請求
        （參數錯、額度用完）是 `ServiceError`；訊息帶服務回的原文。
        """
        ...


__all__ = ["WebPage", "WebSearch"]
