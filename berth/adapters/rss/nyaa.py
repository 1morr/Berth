"""Nyaa 的 RSS（plan §8.5 的 Nyaa 那一欄、brief §20.12、研究檔 `rss-sources.md` §3）。

搜尋 feed（`?page=rss&q=…`）與使用者 feed（`&u=…`）是同一種格式。兩處與直覺相反：

- **`<link>` 是下載連結，單集頁是 `<guid>`**（`https://nyaa.si/view/<id>`，資料庫主鍵，改標題也不變）。
- **magnet 模式（`&m`）或那一筆沒有 torrent 檔時 `<link>` 是 magnet**，沒有 `.torrent` 可抓。
"""

from __future__ import annotations

import logging
import re
from typing import Any

from berth.adapters.rss import FeedItem, approx_bytes
from berth.adapters.rss.feed import entries, rfc822_published

logger = logging.getLogger(__name__)

_HASH = re.compile(r"^[0-9a-fA-F]{40}$")


def parse_feed(content: bytes) -> tuple[FeedItem, ...]:
    """一份 Nyaa RSS 的原文 → Feed Item，照 feed 的順序（新的在前）。"""
    found: list[FeedItem] = []
    for entry in entries(content):
        item = _item(entry)
        if item is None:
            logger.warning(
                "skipping a Nyaa item without a view page",
                extra={"title": entry.get("title", "")},
            )
            continue
        found.append(item)
    return tuple(found)


def _item(entry: Any) -> FeedItem | None:
    page = str(entry.get("id", ""))
    if not page:
        return None
    link = str(entry.get("link", ""))
    magnet = link if link.startswith("magnet:") else ""
    info_hash = str(entry.get("nyaa_infohash", ""))
    return FeedItem(
        guid=page,
        title=str(entry.get("title", "")),
        link=page,
        torrent_url="" if magnet else link,
        magnet=magnet,
        info_hash=info_hash.lower() if _HASH.match(info_hash) else "",
        size=approx_bytes(str(entry.get("nyaa_size", ""))),
        published_at=rfc822_published(entry),
    )
