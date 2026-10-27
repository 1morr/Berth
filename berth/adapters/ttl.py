"""程序內的回應快取：記多久、最多幾筆（M5 票 16）。

給公開的資料站用（AniList、Bangumi）：同一段對話常把同一個問題問好幾次（走系列圖時每一層都碰到
已經問過的條目），而 AniList 的條款禁止大量收集（brief §20.3〈動漫資料來源〉），所以只記按需問過的、
過期就丟，不落地。
"""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable


class TtlCache[V]:
    """鍵 → 值，每一筆記 `ttl` 秒；滿了丟最舊的那一筆。

    TTL 只有一種，所以插入順序就是過期順序：清的時候從頭清到第一個沒過期的就停（同
    `services.sources.SourceCache`）。
    """

    def __init__(
        self, *, ttl: float, size: int, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._ttl = ttl
        self._size = size
        self._clock = clock
        self._entries: OrderedDict[str, tuple[float, V]] = OrderedDict()

    def __len__(self) -> int:
        return len(self._entries)

    def get(self, key: str) -> V | None:
        entry = self._entries.get(key)
        if entry is None or self._clock() >= entry[0]:
            return None
        return entry[1]

    def put(self, key: str, value: V) -> None:
        now = self._clock()
        # 先拿掉同名的那一筆：覆寫不增加筆數，滿了也不該為它丟別人。
        self._entries.pop(key, None)
        while self._entries:
            oldest = next(iter(self._entries.values()))
            if oldest[0] > now and len(self._entries) < self._size:
                break
            self._entries.popitem(last=False)
        self._entries[key] = (now + self._ttl, value)
