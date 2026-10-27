"""對真的 Bangumi API 說話（回應錄在 `tests/fixtures/http/bgm/`）。

`/calendar` 回 `cache-control: max-age=3600`，所以 Berth 照它記一小時（全程序一份）。沒有公布的
速率上限；一個 Turn 最多問一次，快取之後一小時裡都不再問。
"""

from __future__ import annotations

from berth.adapters.bgm import API_URL, USER_AGENT, CalendarItem, parse_calendar
from berth.adapters.http import HttpSession, json_body
from berth.adapters.ttl import TtlCache

CACHE_SECONDS = 60 * 60

_TIMEOUT_SECONDS = 30.0

_CACHE: TtlCache[list[CalendarItem]] = TtlCache(ttl=CACHE_SECONDS, size=4)


class HttpBgm:
    def __init__(
        self, *, base_url: str = API_URL, cache: TtlCache[list[CalendarItem]] = _CACHE
    ) -> None:
        self._base_url = base_url
        self._cache = cache

    async def calendar(self) -> list[CalendarItem]:
        items = self._cache.get("calendar")
        if items is None:
            async with HttpSession(
                self._base_url, headers={"User-Agent": USER_AGENT}, timeout=_TIMEOUT_SECONDS
            ) as http:
                items = parse_calendar(json_body(await http.get("/calendar")))
            self._cache.put("calendar", items)
        return list(items)
