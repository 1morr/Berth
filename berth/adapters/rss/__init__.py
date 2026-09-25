"""RSS adapter（plan §8.5、brief §15、§20.12）。

每一站一個 mapper，把該站的 RSS 翻成統一的 `FeedItem`；抓網頁的是 `FeedFetcher`，兩件事分開，
所以 mapper 是純函式、對著 `tests/fixtures/http/<站>/` 的錄製回應就測得到。

`FeedItem` 只有這一票（M3 票 08）用得到的欄位。plan §8.5 的 `magnet` 與 `size` 等 Nyaa（票 11）
進來時一起加：Mikan 沒有 magnet，而大小沒有消費者。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class FeedItem:
    """Feed 裡的一筆，已經翻成跟站無關的形狀。"""

    #: 同一個 Feed 裡的去重鍵（plan §8.5 的表：Mikan 是 info hash，不是它那個等於標題的 `<guid>`）。
    guid: str
    title: str
    #: 單集頁。Mikan 的 RSS Series 鍵要從這一頁讀（`mikan.series_key`）。
    link: str
    torrent_url: str
    #: 小寫十六進位；站不報時空字串。
    info_hash: str
    #: aware UTC。站不報時 `None`。
    published_at: datetime | None


class FeedFetcher(Protocol):
    """抓一條網址的原文：Feed 本身，或 Mikan 的單集頁。"""

    async def fetch(self, url: str) -> bytes: ...

    async def aclose(self) -> None: ...
