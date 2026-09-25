"""任意 Torznab 端點的搜尋（plan §8.4）。

Jackett 的聚合網址、Prowlarr 的單站網址，或別的什麼——只要它說 Torznab。單站的回應比
Prowlarr 的聚合 REST 快得多（2026-09-10 實測 1.2 秒對 60–85 秒），因為它只問一個站。

`t=caps` 決定用哪一種問法：端點的 `tv-search` / `movie-search` 說支援 `tmdbid` 時用 id 問，
不支援時退回 `q=`（票 08 驗收）。**實測十個預設公開站一個都不支援 tmdbid**——627 份
Cardigann 定義裡有 93 份支援，全部是 private 或 semiPrivate 的私站，所以 `q=` 是常態。
"""

from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import httpx

from berth.adapters.budget import site_of
from berth.adapters.http import ProtocolMismatchError
from berth.adapters.indexer import (
    IndexerResult,
    SearchCapability,
    SearchQuery,
    first_int,
    normalise_info_hash,
)
from berth.adapters.torznab import TorznabCaps
from berth.adapters.torznab.client import parse_caps, torznab_session
from berth.domain import MediaKind

#: 單站 Torznab 只問一個追蹤站，不像 Prowlarr 的 REST 要現場連五個。實測 1.2 秒，
#: 但被擋在 CloudFlare 前面的站可以拖很久，所以仍然給得比探測寬。
SEARCH_TIMEOUT_SECONDS = 60.0

#: `torznab:attr` 的命名空間。`ElementTree` 的 `find` 要的是這個展開形式。
_ATTR = "{http://torznab.com/schemas/2015/feed}attr"

#: 用 tmdbid 問時的 `t=`。泛用的 `t=search` 不吃 id，所以要依作品種類換一支。
_ID_FUNCTION = {MediaKind.TV: "tvsearch", MediaKind.MOVIE: "movie"}


class TorznabSearch:
    def __init__(
        self, base_url: str, api_key: str = "", *, timeout: float = SEARCH_TIMEOUT_SECONDS
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._session, self._path = torznab_session(base_url, timeout=timeout)

    @property
    def base_url(self) -> str:
        return self._base_url

    async def capabilities(self) -> SearchCapability:
        return capability_of(parse_caps((await self._get({"t": "caps"})).text))

    async def sites(self) -> frozenset[str]:
        """端點背後是哪一站 Berth 看不到（Jackett 的聚合網址、Prowlarr 的單站網址都是那台
        管理器自己的主機），所以記在端點的主機上（plan §8.4）。不發請求。"""
        return frozenset({site_of(self._base_url)})

    async def search(self, query: SearchQuery) -> tuple[IndexerResult, ...]:
        """`query.tmdb_id` 有值就用 id 問，否則用關鍵字。

        決定權在呼叫端而不是這裡：它已經看過 `capabilities()`，而每次搜尋都先問一次
        `t=caps` 等於把每個查詢變成兩次請求。
        """
        if query.tmdb_id is not None:
            params = {
                "t": _ID_FUNCTION.get(query.kind, "search"),
                "tmdbid": str(query.tmdb_id),
            }
        else:
            params = {"t": "search", "q": query.text}
        return _items((await self._get(params)).text)

    async def aclose(self) -> None:
        await self._session.aclose()

    async def _get(self, params: dict[str, str]) -> httpx.Response:
        if self._api_key:
            params = {**params, "apikey": self._api_key}
        return await self._session.request("GET", self._path, params=params)


def capability_of(caps: TorznabCaps) -> SearchCapability:
    """`t=caps` → 「這個端點搜得動什麼」。

    id 搜尋逐種類問：`tv-search` 認得 tmdbid 不代表 `movie-search` 也認得（實測 YTS 的
    `movie-search` 只有 `q,imdbid`），而作品是劇集還是電影是呼叫端已經知道的事。
    """
    return SearchCapability(
        searchable=caps.search.available,
        tmdb_id=frozenset(
            kind
            for kind, mode in ((MediaKind.TV, caps.tv), (MediaKind.MOVIE, caps.movie))
            if mode.available and "tmdbid" in mode.params
        ),
    )


def _items(text: str) -> tuple[IndexerResult, ...]:
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise ProtocolMismatchError("t=search: response is not XML") from exc
    if root.tag != "rss":
        raise ProtocolMismatchError(f"t=search: root element is <{root.tag}>, not <rss>")
    return tuple(_result(item) for item in root.findall("channel/item"))


def _result(item: ElementTree.Element) -> IndexerResult:
    attrs = _attrs(item)
    seeders = first_int(attrs.get("seeders", ()))
    enclosure = item.find("enclosure")
    length = enclosure.get("length", "") if enclosure is not None else ""
    url = enclosure.get("url", "") if enclosure is not None else ""
    return IndexerResult(
        title=_text(item, "title"),
        # Prowlarr 的單站網址逐筆掛 `<prowlarrindexer>`；別的端點沒有，那時候整批同一個站，
        # 而使用者已經在設定裡看得到它是哪一個——猜一個站名比留空糟。
        indexer=_text(item, "prowlarrindexer"),
        size=first_int((_text(item, "size"), length)) or 0,
        seeders=seeders,
        # Torznab 報的是 `peers`（做種 + 下載），下載中的人數要自己扣（plan §8.4）。
        leechers=_leechers(first_int(attrs.get("peers", ())), seeders),
        download_url=_text(item, "link") or url,
        info_url=_text(item, "comments"),
        info_hash=normalise_info_hash(next(iter(attrs.get("infohash", ())), "")),
        guid=_text(item, "guid"),
        published_at=_published(_text(item, "pubDate")),
        categories=tuple(
            value for value in (first_int((raw,)) for raw in attrs.get("category", ())) if value
        ),
    )


def _attrs(item: ElementTree.Element) -> dict[str, tuple[str, ...]]:
    """`<torznab:attr name= value=>` 收成 `{名字: (值, …)}`。

    值是一串而不是一個：`category` 逐筆重複出現（實測 dmhy 一筆帶 5070 / 100002 / 2020）。
    """
    collected: dict[str, list[str]] = {}
    for attr in item.findall(_ATTR):
        name = (attr.get("name") or "").lower()
        if name:
            collected.setdefault(name, []).append(attr.get("value") or "")
    return {name: tuple(values) for name, values in collected.items()}


def _leechers(peers: int | None, seeders: int | None) -> int | None:
    if peers is None or seeders is None:
        return peers
    return max(peers - seeders, 0)


def _text(item: ElementTree.Element, tag: str) -> str:
    element = item.find(tag)
    return (element.text or "").strip() if element is not None else ""


def _published(value: str) -> datetime | None:
    """`pubDate` 是 RFC 822（`Tue, 14 Apr 2026 14:51:24 +0000`），不是 ISO 8601。"""
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
