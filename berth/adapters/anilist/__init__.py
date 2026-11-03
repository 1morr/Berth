"""AniList adapter（M5 票 16、plan §8.10、brief §20.3〈動漫資料來源〉）。

側面板的推薦新番要的東西 Berth 自己沒有：當季清單附評分人數。AniList 的 GraphQL 一次給得出格式、
集數、開播日、狀態與打分人數。

時間表（M5.5 票 14）另外要放送時刻：`AiringSchedule` 一段時間裡的每一集。

這一層只做翻譯：季表收斂成 `AnimeEntry`，放送收斂成 `Airing`。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
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
    #: 打過分的人數（分數分佈加總），只有季表帶：分數要連人數一起看。
    scorers: int | None = None
    #: 下一集是第幾集（還在播的），只有季表帶。
    next_episode: int | None = None


@dataclass(frozen=True, slots=True)
class Airing:
    """一集的放送時刻（`AiringSchedule`）。"""

    #: AniList 的作品 id。
    media_id: int
    #: AniList 的集號：每季從 1 數，不一定是 TMDB 的集號。
    episode: int
    #: 帶時區（UTC）。
    airs_at: datetime
    #: 原文標題（`title.native`）；沒有是空字串。
    native_title: str


class AniList(Protocol):
    async def season(self, season: AnimeSeason, year: int, *, limit: int) -> list[AnimeEntry]:
        """某一季的動畫，人氣高的在前，帶打分人數。不含成人向。"""
        ...

    async def airing(self, start: datetime, end: datetime) -> list[Airing]:
        """`start` 到 `end` 之間的放送，照時刻排、全部頁數。不含成人向。"""
        ...


#: AniList 一頁最多 50 筆：要 60 筆回 50 筆、`pageInfo.perPage` 是 50（brief §20.3）。
PAGE_SIZE = 50

#: 季表要的欄位。
FIELDS = (
    "id idMal format status episodes season seasonYear startDate{year month day} "
    "title{romaji english native} averageScore popularity genres"
)

SEASON_QUERY = (
    "query($s:MediaSeason,$y:Int,$n:Int){Page(perPage:$n){media(season:$s,seasonYear:$y,"
    "type:ANIME,sort:POPULARITY_DESC,isAdult:false){"
    f"{FIELDS} nextAiringEpisode{{episode}} stats{{scoreDistribution{{amount}}}}}}}}}}"
)

#: 一段時間裡的放送（時間表的第二層，M5.5 票 14）：照時刻排、一頁 50 筆翻到底。AniList 只保證
#: **未來的**放送存在且準確（brief §20.3），所以這只拿來顯示時刻，不拿來判斷該不該入庫。
#: `media` 帶原文標題（時間表照它對 TMDB 的 `original_name`）與 `isAdult`（成人向不列）。
AIRING_QUERY = (
    "query($p:Int,$a:Int,$b:Int){Page(page:$p,perPage:50){pageInfo{hasNextPage}"
    "airingSchedules(airingAt_greater:$a,airingAt_lesser:$b,sort:TIME){"
    "airingAt episode media{id isAdult title{native}}}}}"
)


def page_media(data: Any) -> list[dict[str, Any]]:
    """`{"Page": {"media": [...]}}` 裡的那一串。形狀不對是協定不符。"""
    page = data.get("Page") if isinstance(data, dict) else None
    media = page.get("media") if isinstance(page, dict) else None
    if not isinstance(media, list):
        raise ProtocolMismatchError("AniList: no Page.media in the answer")
    return [item for item in media if isinstance(item, dict)]


def parse_airings(data: Any) -> tuple[list[Airing], bool]:
    """一頁放送與「還有沒有下一頁」。形狀不對是協定不符。"""
    page = data.get("Page") if isinstance(data, dict) else None
    items = page.get("airingSchedules") if isinstance(page, dict) else None
    if not isinstance(items, list):
        raise ProtocolMismatchError("AniList: no Page.airingSchedules in the answer")
    info = page.get("pageInfo") if isinstance(page, dict) else None
    more = isinstance(info, dict) and info.get("hasNextPage") is True
    found: list[Airing] = []
    for item in items:
        media = item.get("media") if isinstance(item, dict) else None
        if not isinstance(media, dict) or media.get("isAdult") is True:
            continue
        media_id, at, episode = (
            _int(media.get("id")),
            _int(item.get("airingAt")),
            _int(item.get("episode")),
        )
        if media_id is None or at is None or episode is None:
            continue
        title = media.get("title")
        native = title.get("native") if isinstance(title, dict) else None
        found.append(
            Airing(
                media_id=media_id,
                episode=episode,
                airs_at=datetime.fromtimestamp(at, UTC),
                native_title=native if isinstance(native, str) else "",
            )
        )
    return found, more


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
        scorers=_scorers(stats) if isinstance(stats, dict) else None,
        next_episode=_int(airing.get("episode")) if isinstance(airing, dict) else None,
    )


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
    "AIRING_QUERY",
    "API_URL",
    "PAGE_SIZE",
    "Airing",
    "AniList",
    "AnimeEntry",
    "AnimeSeason",
    "AnimeTitle",
]
