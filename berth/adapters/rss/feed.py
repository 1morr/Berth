"""三站共用的兩件事：把原文交給 feedparser、讀 RFC 822 的發佈時間。"""

from __future__ import annotations

import calendar
from datetime import UTC, datetime
from typing import Any

# feedparser 沒有型別存根（不在 typeshed，也沒隨附 py.typed）；這裡只讀它回的 dict。
import feedparser  # type: ignore[import-untyped]

from berth.adapters.http import ProtocolMismatchError

_TORRENT_TYPE = "application/x-bittorrent"


def entries(content: bytes) -> list[Any]:
    """一份 RSS 的原文 → feedparser 的 entry，照 feed 的順序。

    連到的不是 feed（登入頁、Cloudflare 的錯誤頁）時 feedparser 回一份空的 `entries`，那一刻說不出
    「這週沒更新」與「網址錯了」的差別，所以認不出 feed 格式（`version` 是空的）就當成協定不符。
    """
    parsed: Any = feedparser.parse(content)
    if not parsed.get("version"):
        raise ProtocolMismatchError("the response is not an RSS feed")
    return list(parsed.entries)


def enclosure(entry: Any) -> str:
    """`application/x-bittorrent` 那一個 `<enclosure>` 的網址（Mikan 與 acg.rip）。沒有是空字串。"""
    for found in entry.get("enclosures", ()):
        if found.get("type") == _TORRENT_TYPE and found.get("href"):
            return str(found["href"])
    return ""


def rfc822_published(entry: Any) -> datetime | None:
    """`<pubDate>`（RFC 822，帶時區）→ aware UTC。feedparser 已經換成 UTC 的 `struct_time`。

    Nyaa 寫 `-0000`、acg.rip 寫 `-0700`（研究檔 §3.3、§4），兩者 feedparser 都換對了。
    """
    moment = entry.get("published_parsed")
    if moment is None:
        return None
    return datetime.fromtimestamp(calendar.timegm(moment), tz=UTC)
