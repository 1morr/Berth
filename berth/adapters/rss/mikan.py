"""Mikan Project 的 RSS（plan §8.5 的 Mikan 那一欄、brief §20.12、研究檔 `rss-sources.md` §2）。

三種 feed（聚合的 `MyBangumi`、單一的 `Bangumi`、`Classic`）是同一種格式。兩處不照 feedparser
的預設讀，否則會安靜地讀錯：

- **去重鍵是 `link` 末段的 info hash，不是 `<guid>`**：Mikan 的 `<guid>` 就是標題，
  字幕組改標題就變。
- **發佈時間讀 `<torrent><pubDate>` 的字串自己補 UTC+8**：它不帶時區、實際是北京時間
  （同一筆對 acg.rip 差 +7:59:59），而 feedparser 的 `published_parsed` 把它當 UTC 讀。
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urljoin, urlsplit

# feedparser 沒有型別存根（不在 typeshed，也沒隨附 py.typed）；這裡只讀它回的 dict。
import feedparser  # type: ignore[import-untyped]

from berth.adapters.http import ProtocolMismatchError
from berth.adapters.rss import FeedItem

logger = logging.getLogger(__name__)

#: Mikan 的發佈時間所在的時區（brief §20.11）。
MIKAN_TZ = timezone(timedelta(hours=8))

_HASH = re.compile(r"^[0-9a-fA-F]{40}$")
_TORRENT_TYPE = "application/x-bittorrent"


def parse_feed(content: bytes) -> tuple[FeedItem, ...]:
    """一份 Mikan RSS 的原文 → Feed Item，照 feed 的順序（新的在前）。

    連到的不是 feed（登入頁、錯誤頁）時 feedparser 回一份空的 `entries`，那一刻說不出「這個
    番組這週沒更新」與「網址錯了」的差別，所以認不出 feed 格式（`version` 是空的）就當成協定不符。
    """
    parsed: Any = feedparser.parse(content)
    if not parsed.get("version"):
        raise ProtocolMismatchError("the response is not an RSS feed")
    found: list[FeedItem] = []
    for entry in parsed.entries:
        item = _item(entry)
        if item is None:
            logger.warning(
                "skipping a Mikan item without an info hash",
                extra={"title": entry.get("title", "")},
            )
            continue
        found.append(item)
    return tuple(found)


def _item(entry: Any) -> FeedItem | None:
    link = str(entry.get("link", ""))
    info_hash = link.rstrip("/").rsplit("/", 1)[-1]
    if not _HASH.match(info_hash):
        return None
    return FeedItem(
        guid=info_hash.lower(),
        title=str(entry.get("title", "")),
        link=link,
        torrent_url=_enclosure(entry),
        info_hash=info_hash.lower(),
        published_at=published_at(entry.get("published")),
    )


def _enclosure(entry: Any) -> str:
    for enclosure in entry.get("enclosures", ()):
        if enclosure.get("type") == _TORRENT_TYPE and enclosure.get("href"):
            return str(enclosure["href"])
    return ""


def published_at(raw: object) -> datetime | None:
    """`<torrent><pubDate>` 的字串 → aware UTC。不帶時區的當 UTC+8；讀不懂的是 `None`。

    小數秒 0、3、6 位都有（brief §20.12），`fromisoformat` 三種都收。
    """
    if not isinstance(raw, str) or not raw:
        return None
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=MIKAN_TZ)
    return moment.astimezone(UTC)


def series_key(page: str, base_url: str = "https://mikanani.me/") -> tuple[int, int] | None:
    """單集頁 → （番組 id, 字幕組 id），也就是 RSS Series 的鍵（brief §15、§20.12）。

    讀頁上 `a.mikan-rss` 的 `href`（`/RSS/Bangumi?bangumiId=…&subgroupid=…`）。找不到是 `None`：
    那一頁改版了，或連到的不是單集頁。
    """
    finder = _RssLink()
    finder.feed(page)
    for href in finder.hrefs:
        query = parse_qs(urlsplit(urljoin(base_url, href)).query)
        bangumi = query.get("bangumiId", [""])[0]
        subgroup = query.get("subgroupid", [""])[0]
        if bangumi.isdigit() and subgroup.isdigit():
            return int(bangumi), int(subgroup)
    return None


class _RssLink(HTMLParser):
    """收集 `class` 裡有 `mikan-rss` 的 `<a>` 的 `href`。"""

    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        found = dict(attrs)
        if "mikan-rss" in (found.get("class") or "").split() and found.get("href"):
            self.hrefs.append(str(found["href"]))
