"""Tavily 搜尋 adapter 對錄製回應的契約（M5 票 17；回應是 `scripts/experiments/tavily_search.py`
2026-10-27 對 `POST https://api.tavily.com/search` 錄的）。

`tests/fixtures/http/tavily/` 的每一份是 `{status, headers, body}`。替身伺服器照原樣回它們。
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from berth.adapters.http import (
    AuthFailedError,
    ServiceError,
    ServiceUnavailableError,
)
from berth.adapters.websearch import WebPage
from berth.adapters.websearch.tavily import TAVILY_API_URL, HttpTavily
from tests.conftest import read_fixture

pytestmark = pytest.mark.asyncio

KEY = "tvly-dev-contract-test-key"
SEARCH = f"{TAVILY_API_URL}/search"
DOMAINS = ("wikipedia.org", "myanimelist.net")


def recorded(name: str) -> httpx.Response:
    record: dict[str, Any] = json.loads(read_fixture(f"http/tavily/{name}.json"))
    return httpx.Response(record["status"], json=record["body"], headers=record["headers"])


@respx.mock
async def test_a_search_returns_the_pages_and_sends_the_domains() -> None:
    route = respx.post(SEARCH).mock(return_value=recorded("search.ok"))

    pages = await HttpTavily(KEY).search("Frieren season 2", domains=DOMAINS, max_results=5)

    request = route.calls.last.request
    assert request.headers["Authorization"] == f"Bearer {KEY}"
    sent = json.loads(request.content)
    assert sent["query"] == "Frieren season 2"
    assert sent["include_domains"] == list(DOMAINS)
    assert sent["max_results"] == 5
    # 1 credit 的那一種；不要 Tavily 自己寫的答案（又一層別人的字）。
    assert sent["search_depth"] == "basic"
    assert sent["include_answer"] is False
    assert len(pages) == 5
    assert all(isinstance(page, WebPage) for page in pages)
    assert pages[0].url == "https://en.wikipedia.org/wiki/Frieren_(TV_series)"
    assert pages[0].title.startswith("Frieren")
    assert pages[0].content.startswith("Eleven short episodes")
    assert all(page.url.startswith("https://") and page.content for page in pages)


@respx.mock
async def test_a_rejected_key_says_so_with_the_services_words() -> None:
    respx.post(SEARCH).mock(return_value=recorded("search.unauthorized"))

    with pytest.raises(AuthFailedError, match="missing or invalid API key") as caught:
        await HttpTavily(KEY).search("x", domains=DOMAINS, max_results=5)

    assert KEY not in str(caught.value)


@respx.mock
async def test_a_refused_request_carries_the_reason() -> None:
    respx.post(SEARCH).mock(return_value=recorded("search.bad-request"))

    with pytest.raises(ServiceError, match="requires include_domains") as caught:
        await HttpTavily(KEY).search("x", domains=DOMAINS, max_results=5)

    # 參數錯、額度用完：再問一次也一樣，不是「等一下就好」。
    assert not isinstance(caught.value, ServiceUnavailableError | AuthFailedError)


@respx.mock
async def test_rate_limits_are_worth_retrying_later() -> None:
    # 文件的 429（https://docs.tavily.com/documentation/rate-limits），沒有錄到。
    respx.post(SEARCH).mock(
        return_value=httpx.Response(
            429,
            json={"detail": {"error": "Your request has been blocked due to excessive requests."}},
            headers={"Retry-After": "60"},
        )
    )

    with pytest.raises(ServiceUnavailableError, match="excessive requests"):
        await HttpTavily(KEY).search("x", domains=DOMAINS, max_results=5)
