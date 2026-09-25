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
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

from berth.adapters.rss import FeedItem, approx_bytes
from berth.adapters.rss.feed import enclosure, entries

logger = logging.getLogger(__name__)

#: Mikan 本站。番組頁的網址由它與番組 id 組出來（`bangumi_url`）。
MIKAN_BASE = "https://mikanani.me/"

#: Mikan 的發佈時間所在的時區（brief §20.11）。
MIKAN_TZ = timezone(timedelta(hours=8))

_HASH = re.compile(r"^[0-9a-fA-F]{40}$")


def parse_feed(content: bytes) -> tuple[FeedItem, ...]:
    """一份 Mikan RSS 的原文 → Feed Item，照 feed 的順序（新的在前）。"""
    found: list[FeedItem] = []
    for entry in entries(content):
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
        torrent_url=enclosure(entry),
        magnet="",
        info_hash=info_hash.lower(),
        size=_size(str(entry.get("summary", ""))),
        published_at=published_at(entry.get("published")),
    )


#: 描述結尾的 `[518.65 MB]`。
_SIZE_SUFFIX = re.compile(r"\[([^\[\]]+)\]\s*$")


def _size(description: str) -> int | None:
    """描述結尾的大小，十進位。**不讀 `contentLength`**：它不是位元組數（研究檔 §2.4）。"""
    found = _SIZE_SUFFIX.search(description)
    return approx_bytes(found.group(1)) if found is not None else None


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


@dataclass(frozen=True, slots=True)
class MikanBangumi:
    """番組頁上自動綁定用得到的兩格（研究檔 §2.7、brief §15「綁定」）。"""

    #: 中文名（多半是簡體）。讀不到是空字串。
    title: str
    #: 「放送开始」。讀不到是 `None`。
    premiere: date | None


#: 「放送开始：7/7/2026」。**M/D/YYYY**：番組頁同時寫的星期只對得上這種讀法（研究檔 §2.7）。
_PREMIERE = re.compile(r"放送开始：\s*(\d{1,2})/(\d{1,2})/(\d{4})")


def bangumi_url(bangumi_id: int) -> str:
    return urljoin(MIKAN_BASE, f"/Home/Bangumi/{bangumi_id}")


def bangumi_feed_url(bangumi_id: int, subgroup_id: int) -> str:
    """番組 × 字幕組的單一 feed：整季都在（brief §20.12），補舊集與每日補漏讀它（票 12）。"""
    return urljoin(MIKAN_BASE, f"/RSS/Bangumi?bangumiId={bangumi_id}&subgroupid={subgroup_id}")


def bangumi_page(page: str) -> MikanBangumi:
    """番組頁 → 中文名與開播日期。

    中文名是第一個 `p.bangumi-title` 的文字（桌面版在前；裡面那顆 RSS 的 `<a>` 不算）。
    頁上的中文字是數字字元參照，`HTMLParser` 預設就解開（`convert_charrefs`）。
    """
    finder = _BangumiTitle()
    finder.feed(page)
    found = _PREMIERE.search(page)
    premiere = _mdy(found) if found is not None else None
    return MikanBangumi(title=" ".join("".join(finder.text).split()), premiere=premiere)


def _mdy(found: re.Match[str]) -> date | None:
    """M/D/YYYY 的三組 → 日期。不存在的日期（13/40）是 `None`。"""
    month, day, year = (int(part) for part in found.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


class _BangumiTitle(HTMLParser):
    """第一個 `class` 裡有 `bangumi-title` 的 `<p>` 的直屬文字（子元素裡的字不收）。"""

    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []
        self._depth = 0
        self._done = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._done:
            return
        if self._depth:
            self._depth += 1
        elif tag == "p" and "bangumi-title" in (dict(attrs).get("class") or "").split():
            self._depth = 1

    def handle_endtag(self, tag: str) -> None:
        if not self._depth:
            return
        self._depth -= 1
        if not self._depth:
            self._done = True

    def handle_data(self, data: str) -> None:
        if self._depth == 1:
            self.text.append(data)


# --- 從 Media 頁訂閱：搜番組、列字幕組（M3 票 19） ------------------------


@dataclass(frozen=True, slots=True)
class BangumiHit:
    """搜尋頁上的一個番組。"""

    id: int
    #: 中文名（多半是簡體），原樣。
    title: str


def search_url(term: str) -> str:
    """番組搜尋頁。英文、羅馬字、日文、繁中都搜得到（2026-09-26 實測，brief §20.12）。"""
    return urljoin(MIKAN_BASE, "/Home/Search?" + urlencode({"searchstr": term}))


_BANGUMI_HREF = re.compile(r"^/Home/Bangumi/(\d+)$")


def search_page(page: str) -> tuple[BangumiHit, ...]:
    """搜尋頁 → 番組，照頁上的順序。

    認的是結果格子：連到 `/Home/Bangumi/<id>` 的 `<a>` 裡那一個 `div.an-text`，名字取它的 `title`
    （格子裡的字會被 CSS 截斷，`title` 是全名）。頁上其他連到番組頁的連結不算。
    """
    finder = _BangumiHits()
    finder.feed(page)
    return tuple(finder.hits)


class _BangumiHits(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hits: list[BangumiHit] = []
        self._bangumi: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        found = dict(attrs)
        if tag == "a":
            href = _BANGUMI_HREF.match(found.get("href") or "")
            self._bangumi = int(href.group(1)) if href else None
        elif (
            tag == "div"
            and self._bangumi is not None
            and "an-text" in (found.get("class") or "").split()
        ):
            self.hits.append(BangumiHit(id=self._bangumi, title=(found.get("title") or "").strip()))
            self._bangumi = None

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._bangumi = None


@dataclass(frozen=True, slots=True)
class Subgroup:
    """番組頁上的一個字幕組：`subgroupid` 與畫面上讓人挑的幾格。"""

    id: int
    name: str
    #: 左欄那一格的日期（M/D/YYYY，最近一次發佈）。讀不到是 `None`。
    updated: date | None
    #: 這一組在這個番組下的發佈筆數。
    releases: int
    #: 最新的那一筆發佈名：看得出語言、解析度。沒有是空字串。
    latest: str


_SUBGROUP_CLASS = re.compile(r"^subgroup-(\d+)$")
_DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def subgroups(page: str) -> tuple[Subgroup, ...]:
    """番組頁 → 字幕組，照左欄的順序。

    左欄的 `a.subgroup-name.subgroup-<id>` 是名字、緊接的 `span.date` 是最近更新；右邊每一組是
    `div.subgroup-text#<id>` 帶一張發佈表（`a.magnet-link-wrap`，新的在前）。
    """
    finder = _Subgroups()
    finder.feed(page)
    return tuple(
        Subgroup(
            id=group,
            name=name,
            updated=finder.dates.get(group),
            releases=len(finder.releases.get(group, ())),
            latest=next(iter(finder.releases.get(group, ())), ""),
        )
        for group, name in finder.names.items()
    )


class _Subgroups(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.names: dict[int, str] = {}
        self.dates: dict[int, date] = {}
        self.releases: dict[int, list[str]] = {}
        #: 正在讀的那一格：`("name" | "date" | "release", 字幕組 id)`。
        self._reading: tuple[str, int] | None = None
        self._text: list[str] = []
        #: 左欄最後一個名字（它的日期緊接在後）、右邊目前在哪一組的發佈表裡。
        self._named: int | None = None
        self._section: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        found = dict(attrs)
        classes = (found.get("class") or "").split()
        if tag == "a" and "subgroup-name" in classes:
            for one in classes:
                matched = _SUBGROUP_CLASS.match(one)
                if matched:
                    self._named = int(matched.group(1))
                    self._start("name", self._named)
        elif tag == "span" and "date" in classes and self._named is not None:
            self._start("date", self._named)
        elif tag == "div" and "subgroup-text" in classes and (found.get("id") or "").isdigit():
            self._section = int(found["id"] or 0)
        elif tag == "a" and "magnet-link-wrap" in classes and self._section is not None:
            self._start("release", self._section)

    def _start(self, what: str, group: int) -> None:
        self._reading = (what, group)
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._reading is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._reading is None or tag not in ("a", "span"):
            return
        what, group = self._reading
        text = " ".join("".join(self._text).split())
        self._reading = None
        if what == "name":
            self.names[group] = text
        elif what == "date":
            self._named = None
            found = _DATE.search(text)
            updated = _mdy(found) if found is not None else None
            if updated is not None:
                self.dates[group] = updated
        else:
            self.releases.setdefault(group, []).append(text)
