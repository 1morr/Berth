"""測試與前端演練用的 `FeedFetcher` 替身：一張「網址 → 原文」的查表。"""

from __future__ import annotations

from berth.adapters.http import ServiceError, ServiceUnavailableError


class FakeFeedFetcher:
    """查不到的網址當成連不上——真的 Mikan 單集頁偶爾就是那樣。"""

    def __init__(self, pages: dict[str, bytes] | None = None) -> None:
        self.pages = dict(pages or {})
        #: 要過的每一條網址，用來斷言「第二輪沒有再抓一次單集頁」。
        self.requested: list[str] = []
        #: 設了就整個垮掉（Feed 本身抓不到）。
        self.error: ServiceError | None = None
        #: `網址 → 抓它時丟的例外`：只有那一頁壞掉（404 的番組頁，M4 票 14）。
        self.page_errors: dict[str, ServiceError] = {}

    async def fetch(self, url: str) -> bytes:
        self.requested.append(url)
        if self.error is not None:
            raise self.error
        if url in self.page_errors:
            raise self.page_errors[url]
        if url not in self.pages:
            raise ServiceUnavailableError(f"GET {url}: connection refused")
        return self.pages[url]

    async def aclose(self) -> None:
        return None
