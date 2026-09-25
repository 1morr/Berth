"""RSS adapter（plan §8.5、brief §15、§20.12）。

每一站一個 mapper，把該站的 RSS 翻成統一的 `FeedItem`；抓網頁的是 `FeedFetcher`，兩件事分開，
所以 mapper 是純函式、對著 `tests/fixtures/http/<站>/` 的錄製回應就測得到。

三站各缺不同的東西（研究檔 `rss-sources.md` §9）：Mikan 沒有 magnet、acg.rip 沒有 info hash、
Nyaa 在 magnet 模式下沒有 `.torrent`。缺的那一格是空字串或 `None`，不猜。
"""

from __future__ import annotations

import re
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
    #: `.torrent` 的網址；站只給 magnet 時空字串。
    torrent_url: str
    #: Nyaa 的 magnet 模式（`&m`）或那一筆沒有 torrent 檔時才有；其他是空字串。
    magnet: str
    #: 小寫十六進位；站不報時空字串（acg.rip，送單時由 `TorrentFetcher` 算）。
    info_hash: str
    #: 近似的位元組數，只供顯示（三站都不準，研究檔 §2.4）。站不報時 `None`。
    size: int | None
    #: aware UTC。站不報時 `None`。
    published_at: datetime | None


#: `240.5 MiB`、`518.65 MB`、`812 Bytes`。
_SIZE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*(Bytes?|[KMGT]i?B)\s*$", re.IGNORECASE)
_POWER = {"k": 1, "m": 2, "g": 3, "t": 4}


def approx_bytes(text: str) -> int | None:
    """人類可讀的大小 → 位元組。讀不懂是 `None`。

    `KiB` / `MiB` 是 1024 進位（Nyaa），`KB` / `MB` 是 1000 進位（Mikan 的描述，研究檔 §2.4）。
    """
    found = _SIZE.match(text)
    if found is None:
        return None
    number, unit = float(found.group(1)), found.group(2).lower()
    if unit.startswith("byte"):
        return int(number)
    base = 1024 if unit[1] == "i" else 1000
    return int(number * base ** _POWER[unit[0]])


class FeedFetcher(Protocol):
    """抓一條網址的原文：Feed 本身，或 Mikan 的單集頁。"""

    async def fetch(self, url: str) -> bytes: ...

    async def aclose(self) -> None: ...
