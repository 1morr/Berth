"""AniList adapter（M5 票 16、plan §8.10、brief §20.3〈動漫資料來源〉）。

側面板的兩個情境要的東西 Berth 自己沒有：當季清單附評分人數（推薦新番）、一部作品的每個條目
（每一季、cour、OVA、劇場版）與它們的關係（整部系列）。AniList 的 GraphQL 一次給得出格式、集數、
開播日、狀態與型別化的關係。

這一層只做翻譯：三種問法（標題搜尋、依 id 取條目與關係、季表）收斂成一個 `AnimeEntry`。沿關係
走圖、挑哪幾種關係是 `services/anilist.py` 的事。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from berth.adapters.http import ProtocolMismatchError

API_URL = "https://graphql.anilist.co"


class AnimeSeason(StrEnum):
    """AniList 的季（`MediaSeason`）：冬是 1–3 月，依此類推。"""

    WINTER = "WINTER"
    SPRING = "SPRING"
    SUMMER = "SUMMER"
    FALL = "FALL"


@dataclass(frozen=True, slots=True)
class AnimeTitle:
    """三種寫法；AniList 沒有的是空字串（`english` 常常沒有）。"""

    romaji: str
    english: str
    native: str


@dataclass(frozen=True, slots=True)
class AnimeRelation:
    """一條關係：`type` 是 AniList 的 `MediaRelation`（`SEQUEL`、`SIDE_STORY`…），
    `id` 是對面那一部。"""

    type: str
    id: int


@dataclass(frozen=True, slots=True)
class AnimeEntry:
    id: int
    mal_id: int | None
    title: AnimeTitle
    #: `TV`、`TV_SHORT`、`MOVIE`、`SPECIAL`、`OVA`、`ONA`、`MUSIC`；沒填是 `None`。
    format: str | None
    #: `FINISHED`、`RELEASING`、`NOT_YET_RELEASED`、`CANCELLED`、`HIATUS`。
    status: str | None
    episodes: int | None
    season: str | None
    season_year: int | None
    #: `2016-04-04`；只知道年或年月時就只寫那幾段（`2026`、`2026-04`）。
    start_date: str | None
    #: 0–100；打分的人太少時 AniList 給 `null`。
    average_score: int | None
    #: 把它加進清單的人數。
    popularity: int | None
    genres: tuple[str, ...]
    #: 只有依 id 取的那一種帶（`AniList.entries`），只留指向動畫的。
    relations: tuple[AnimeRelation, ...] = ()
    #: 打過分的人數（分數分佈加總），只有季表帶：分數要連人數一起看。
    scorers: int | None = None
    #: 下一集是第幾集（還在播的），只有季表帶。
    next_episode: int | None = None


class AniList(Protocol):
    async def search(self, query: str, *, limit: int) -> list[AnimeEntry]:
        """標題搜尋（羅馬字、英文、日文都行），AniList 的相關度排序。"""
        ...

    async def entries(self, ids: Sequence[int]) -> list[AnimeEntry]:
        """這幾個 id 的條目，帶關係。一次最多 `PAGE_SIZE` 個；不存在的不在結果裡，順序不保證。"""
        ...

    async def season(self, season: AnimeSeason, year: int, *, limit: int) -> list[AnimeEntry]:
        """某一季的動畫，人氣高的在前，帶打分人數。不含成人向。"""
        ...


#: AniList 一頁最多 50 筆：要 60 筆回 50 筆、`pageInfo.perPage` 是 50（brief §20.3）。
PAGE_SIZE = 50

#: 每一種問法都要的欄位。
FIELDS = (
    "id idMal format status episodes season seasonYear startDate{year month day} "
    "title{romaji english native} averageScore popularity genres"
)

SEARCH_QUERY = (
    "query($q:String,$n:Int){Page(perPage:$n){media(search:$q,type:ANIME,isAdult:false){"
    f"{FIELDS}}}}}}}"
)

#: `relationType(version: 2)`：`SOURCE`、`COMPILATION`、`CONTAINS` 只在第二版（schema 的說明
#: 「Version 2 only」，brief §20.3）。第三版多 `SAME_UNIVERSE`，Berth 不沿它，不必升。
ENTRIES_QUERY = (
    "query($ids:[Int],$n:Int){Page(perPage:$n){media(id_in:$ids,type:ANIME){"
    f"{FIELDS} relations{{edges{{relationType(version:2) node{{id type}}}}}}}}}}}}"
)

SEASON_QUERY = (
    "query($s:MediaSeason,$y:Int,$n:Int){Page(perPage:$n){media(season:$s,seasonYear:$y,"
    "type:ANIME,sort:POPULARITY_DESC,isAdult:false){"
    f"{FIELDS} nextAiringEpisode{{episode}} stats{{scoreDistribution{{amount}}}}}}}}}}"
)


def page_media(data: Any) -> list[dict[str, Any]]:
    """`{"Page": {"media": [...]}}` 裡的那一串。形狀不對是協定不符。"""
    page = data.get("Page") if isinstance(data, dict) else None
    media = page.get("media") if isinstance(page, dict) else None
    if not isinstance(media, list):
        raise ProtocolMismatchError("AniList: no Page.media in the answer")
    return [item for item in media if isinstance(item, dict)]


def parse_entries(items: Iterable[dict[str, Any]]) -> list[AnimeEntry]:
    return [parse_entry(item) for item in items if isinstance(item.get("id"), int)]


def parse_entry(item: dict[str, Any]) -> AnimeEntry:
    title = item.get("title") or {}
    stats = item.get("stats")
    airing = item.get("nextAiringEpisode")
    return AnimeEntry(
        id=int(item["id"]),
        mal_id=_int(item.get("idMal")),
        title=AnimeTitle(
            romaji=str(title.get("romaji") or ""),
            english=str(title.get("english") or ""),
            native=str(title.get("native") or ""),
        ),
        format=_str(item.get("format")),
        status=_str(item.get("status")),
        episodes=_int(item.get("episodes")),
        season=_str(item.get("season")),
        season_year=_int(item.get("seasonYear")),
        start_date=_date(item.get("startDate")),
        average_score=_int(item.get("averageScore")),
        popularity=_int(item.get("popularity")),
        genres=tuple(str(g) for g in item.get("genres") or () if isinstance(g, str)),
        relations=_relations(item.get("relations")),
        scorers=_scorers(stats) if isinstance(stats, dict) else None,
        next_episode=_int(airing.get("episode")) if isinstance(airing, dict) else None,
    )


def _relations(relations: Any) -> tuple[AnimeRelation, ...]:
    edges = relations.get("edges") if isinstance(relations, dict) else None
    found: list[AnimeRelation] = []
    for edge in edges or ():
        node = edge.get("node") if isinstance(edge, dict) else None
        kind = edge.get("relationType") if isinstance(edge, dict) else None
        # 漫畫、小說這一頭（`ADAPTATION`、`SOURCE`）Berth 下載不到，不給。
        if isinstance(node, dict) and node.get("type") == "ANIME" and isinstance(kind, str):
            node_id = node.get("id")
            if isinstance(node_id, int):
                found.append(AnimeRelation(type=kind, id=node_id))
    return tuple(found)


def _scorers(stats: dict[str, Any]) -> int:
    """`stats.scoreDistribution` 是 10、20…100 各幾個人；加起來就是打過分的人數。"""
    total = 0
    for bucket in stats.get("scoreDistribution") or ():
        amount = bucket.get("amount") if isinstance(bucket, dict) else None
        if isinstance(amount, int):
            total += amount
    return total


def _date(value: Any) -> str | None:
    if not isinstance(value, dict) or not isinstance(value.get("year"), int):
        return None
    parts = [f"{value['year']:04d}"]
    for key in ("month", "day"):
        part = value.get(key)
        if not isinstance(part, int):
            break
        parts.append(f"{part:02d}")
    return "-".join(parts)


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


__all__ = [
    "API_URL",
    "PAGE_SIZE",
    "AniList",
    "AnimeEntry",
    "AnimeRelation",
    "AnimeSeason",
    "AnimeTitle",
]
