"""對真的 AniList GraphQL 說話（brief §20.3〈動漫資料來源〉；回應錄在
`tests/fixtures/http/anilist/`）。

- **限流**：文件寫 90 次 / 分，但目前降級成 30 次 / 分，另有沒公布數字的突發限制；超過就封一分鐘，
  封鎖期間的請求都回 429 帶 `Retry-After`（秒）。所以全程序共用一個閘門：平常兩秒放一個，
  收到 429 就整個閘門停到 `Retry-After` 之後再試（各自重試只會延長封鎖）。
- **快取**：條款禁止大量收集，Berth 只按需問、問過的記 6 小時（`TtlCache`），不落地。
- 錯誤寫在 body 的 `errors`（HTTP 200 也可能有），先看它再用 `data`。
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from berth.adapters.anilist import (
    API_URL,
    PAGE_SIZE,
    SEASON_QUERY,
    AnimeEntry,
    AnimeSeason,
    page_media,
    parse_entries,
)
from berth.adapters.http import (
    HttpSession,
    ProtocolMismatchError,
    ServiceUnavailableError,
    json_body,
)
from berth.adapters.rate import TokenBucket
from berth.adapters.ttl import TtlCache

#: 目前的上限是 30 次 / 分（brief §20.3）。突發的上限沒有公布，所以桶只放一個：兩秒一個。
RATE_PER_SECOND = 30 / 60

#: 一個問題記多久。季表的人氣與打分人數一天裡變得不多。
CACHE_SECONDS = 6 * 60 * 60

#: 收到 429 之後最多再試幾次。封鎖是一分鐘：再試兩次還不行，就是這一刻問不到。
RETRIES = 2

#: 沒有 `Retry-After` 時等多久：文件說超過上限是封一分鐘。
DEFAULT_RETRY_AFTER = 60.0
#: `Retry-After` 寫得再長也只等這麼久：側面板那一輪在等這個工具。
MAX_RETRY_AFTER = 90.0

_TIMEOUT_SECONDS = 30.0


class Throttle:
    """全程序共用的閘門：令牌桶加上「被 429 擋下之後停到什麼時候」。

    與 `TokenBucket` 一樣不用鎖（理由見那裡）：算出要等多久與記下來之間沒有 `await`。
    """

    def __init__(
        self,
        *,
        rate: float = RATE_PER_SECOND,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._bucket = TokenBucket(rate=rate, capacity=1, clock=clock, sleep=sleep)
        self._clock = clock
        self._sleep = sleep
        self._blocked_until = 0.0

    async def acquire(self) -> None:
        while (delay := self._blocked_until - self._clock()) > 0:
            await self._sleep(delay)
        await self._bucket.acquire()

    def block(self, seconds: float) -> None:
        self._blocked_until = max(self._blocked_until, self._clock() + seconds)


#: **全域**一份：上限是每個 IP 的，而 services 每次呼叫都造一個新的 client（同 TMDB 的桶）。
_THROTTLE = Throttle()
_CACHE: TtlCache[Any] = TtlCache(ttl=CACHE_SECONDS, size=512)


class HttpAniList:
    def __init__(
        self,
        *,
        base_url: str = API_URL,
        throttle: Throttle = _THROTTLE,
        cache: TtlCache[Any] = _CACHE,
    ) -> None:
        self._base_url = base_url
        self._throttle = throttle
        self._cache = cache

    async def season(self, season: AnimeSeason, year: int, *, limit: int) -> list[AnimeEntry]:
        data = await self._ask(
            SEASON_QUERY, {"s": season.value, "y": year, "n": min(limit, PAGE_SIZE)}
        )
        return parse_entries(page_media(data))

    async def _ask(self, query: str, variables: dict[str, Any]) -> Any:
        key = json.dumps([query, variables], sort_keys=True)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        body = {"query": query, "variables": variables}
        async with HttpSession(self._base_url, timeout=_TIMEOUT_SECONDS) as http:
            for attempt in range(RETRIES + 1):
                await self._throttle.acquire()
                response = await http.request("POST", "/", json=body, tolerate=(400, 404, 429))
                if response.status_code != 429:
                    break
                self._throttle.block(_retry_after(response))
                if attempt == RETRIES:
                    raise ServiceUnavailableError(f"POST {self._base_url}: 429 {_errors(response)}")
        data = _data(response)
        self._cache.put(key, data)
        return data


def _data(response: httpx.Response) -> Any:
    answer = json_body(response)
    errors = answer.get("errors") if isinstance(answer, dict) else None
    if response.status_code != 200 or errors:
        raise ProtocolMismatchError(f"AniList: {response.status_code} {_errors(response)}")
    data = answer.get("data")
    if not isinstance(data, dict):
        raise ProtocolMismatchError("AniList: no data in the answer")
    return data


def _retry_after(response: httpx.Response) -> float:
    raw = response.headers.get("Retry-After", "")
    try:
        seconds = float(raw)
    except ValueError:
        seconds = DEFAULT_RETRY_AFTER
    return min(max(seconds, 1.0), MAX_RETRY_AFTER)


def _errors(response: httpx.Response) -> str:
    """`errors[].message` 接起來；不是 JSON 就用 body 原文（截短）。"""
    try:
        answer = response.json()
    except ValueError:
        return response.text[:200]
    errors = answer.get("errors") if isinstance(answer, dict) else None
    if isinstance(errors, list):
        messages = [str(e.get("message")) for e in errors if isinstance(e, dict)]
        return "; ".join(messages)[:300]
    return str(answer)[:200]
