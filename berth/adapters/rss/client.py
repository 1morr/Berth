"""真的去抓 Feed 與單集頁（`FeedFetcher` 的 HTTP 實作）。"""

from __future__ import annotations

from berth.adapters.http import HttpSession

#: Mikan 的聚合 feed 與單集頁偶爾要十幾秒才回（2026-09-24 試跑），探測用的 5 秒太短。
FETCH_TIMEOUT_SECONDS = 30.0


class HttpFeedFetcher:
    """網址是 Feed 自己帶的整條，所以不綁 base URL；錯誤分類沿用 `HttpSession`。"""

    def __init__(self, *, timeout: float = FETCH_TIMEOUT_SECONDS) -> None:
        self._session = HttpSession("", timeout=timeout)

    async def fetch(self, url: str) -> bytes:
        response = await self._session.request("GET", url)
        return response.content

    async def aclose(self) -> None:
        await self._session.aclose()
