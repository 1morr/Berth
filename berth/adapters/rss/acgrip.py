"""acg.rip 的 RSS（plan §8.5 的 acg.rip 那一欄、brief §20.12、研究檔 `rss-sources.md` §4）。

只有搜尋 feed。**沒有 info hash**（feed 與單集頁都沒有）：送單時 `TorrentFetcher` 下載 `.torrent`
本來就會算，這裡不為了它多發請求（票 07 的結論）。
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlencode

from berth.adapters.rss import FeedItem
from berth.adapters.rss.feed import enclosure, entries, rfc822_published

logger = logging.getLogger(__name__)


def parse_feed(content: bytes) -> tuple[FeedItem, ...]:
    """一份 acg.rip RSS 的原文 → Feed Item，照 feed 的順序（新的在前）。"""
    found: list[FeedItem] = []
    for entry in entries(content):
        page = str(entry.get("id", "")) or str(entry.get("link", ""))
        if not page:
            logger.warning(
                "skipping an acg.rip item without a page", extra={"title": entry.get("title", "")}
            )
            continue
        found.append(
            FeedItem(
                guid=page,
                title=str(entry.get("title", "")),
                link=str(entry.get("link", "")) or page,
                torrent_url=enclosure(entry),
                magnet="",
                info_hash="",
                size=_size(entry),
                published_at=rfc822_published(entry),
            )
        )
    return tuple(found)


def _size(entry: Any) -> int | None:
    """`torrent:contentLength`，位元組的整數（捨到 KiB，研究檔 §4）。"""
    raw = str(entry.get("torrent_contentlength", ""))
    return int(raw) if raw.isdigit() else None


def search_url(term: str) -> str:
    """搜尋 feed，與錄 fixture 的那一條同形（M3 票 19）。"""
    return "https://acg.rip/.xml?" + urlencode({"term": term})
