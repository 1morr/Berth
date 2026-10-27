"""Tavily `POST /search`（brief §20.24〈Tavily〉；回應錄在 `tests/fixtures/http/tavily/`）。

- key 走 `Authorization: Bearer`，Berth 不記標頭，所以不會經網址或錯誤訊息進日誌。
- `search_depth: basic`（1 credit；`advanced` 是 2），不要 `include_answer`：那是 Tavily 自己的
  LLM 寫的摘要，對 Berth 是又一層外部內容、還多花 token。
- 錯誤的 body 是 `{"detail": {"error": "..."}}`：401 key 錯、400 參數錯、429 限流（帶
  `Retry-After`）、432 / 433 額度用完。原文接在例外訊息後面，模型與畫面看得到是哪一種。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from berth.adapters.http import (
    AuthFailedError,
    HttpSession,
    ProtocolMismatchError,
    ServiceError,
    ServiceUnavailableError,
    json_body,
)
from berth.adapters.websearch import WebPage

TAVILY_API_URL = "https://api.tavily.com"

#: 搜尋要問出網頁、要等一下（實測約 2 秒），比探測用的 5 秒寬。
_TIMEOUT_SECONDS = 30.0

#: Tavily 用 4xx 講一件有內容的事：原樣拿回來，照狀態碼分類、帶上原文。
_ANSWERS = (400, 401, 403, 429, 432, 433)


class HttpTavily:
    def __init__(self, api_key: str, *, base_url: str = TAVILY_API_URL) -> None:
        self._api_key = api_key
        self._base_url = base_url

    async def search(
        self, query: str, *, domains: Sequence[str], max_results: int
    ) -> list[WebPage]:
        body = {
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_domains": list(domains),
            "include_answer": False,
        }
        async with HttpSession(
            self._base_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=_TIMEOUT_SECONDS,
        ) as http:
            response = await http.request("POST", "/search", json=body, tolerate=_ANSWERS)
        if response.status_code != 200:
            raise _refused(response)
        answer = json_body(response)
        results = answer.get("results") if isinstance(answer, dict) else None
        if not isinstance(results, list):
            raise ProtocolMismatchError("POST /search: no results in the answer")
        return [_page(item) for item in results if isinstance(item, dict)]


def _page(item: dict[str, Any]) -> WebPage:
    return WebPage(
        title=str(item.get("title") or ""),
        url=str(item.get("url") or ""),
        content=str(item.get("content") or ""),
    )


def _refused(response: httpx.Response) -> ServiceError:
    status = response.status_code
    label = f"POST /search: {status} {_error_text(response)}".rstrip()
    if status in (401, 403):
        return AuthFailedError(label)
    if status == 429:
        return ServiceUnavailableError(label)
    return ServiceError(label)


def _error_text(response: httpx.Response) -> str:
    """`{"detail": {"error": "..."}}` 裡的那句；形狀不對就用 body 原文（截短）。"""
    try:
        answer = response.json()
    except ValueError:
        return response.text[:200]
    detail = answer.get("detail") if isinstance(answer, dict) else None
    if isinstance(detail, dict) and isinstance(detail.get("error"), str):
        return str(detail["error"])
    return str(answer)[:200]
