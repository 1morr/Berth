"""TMDB adapter（plan §8.3）。

**憑證由使用者自備**：Berth 不內建任何 provider 的 API key（brief §16.3、§20.7），唯一的來源是
`settings.services.tmdb.api_key`，取用它的地方只有 `services.tmdb.credential()`。

這一層只做翻譯：把 TMDB 三種端點各自的欄位名收斂成一個 `TmdbEntry`。挑哪些作品、
怎麼快取、要不要合併兩種語言，都是 `services/discover.py` 的事。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from berth.adapters.http import ProtocolMismatchError
from berth.domain import MediaKind

BASE_URL = "https://api.themoviedb.org/3"

#: 取英文標題與檔名用的那一輪（brief §7.5）。
BASE_LANGUAGE = "en-US"
#: 顯示用標題另外取的那一輪（plan §8.3）。
DISPLAY_LANGUAGE = "zh-TW"
#: 只為了**季名**多取的那一輪（plan §4.4）。簡體字幕組寫的是「柱训练篇」，
#: 而 `zh-TW` 給的是「柱訓練篇」——同一個篇章名，兩套字，比對時一個字都不重疊。
SIMPLIFIED_LANGUAGE = "zh-CN"


@dataclass(frozen=True, slots=True)
class TmdbConfiguration:
    """`GET /3/configuration` 回的東西。精靈用它證明憑證有效，探索頁用它組海報網址。"""

    image_base_url: str


@dataclass(frozen=True, slots=True)
class TmdbEntry:
    """探索與搜尋清單裡的一筆。

    劇集與電影在 TMDB 是**兩組欄位名**（`name` / `first_air_date` 對 `title` / `release_date`），
    而三支端點回的是同一種卡片。差異收在這裡，上面就只有一種形狀。
    """

    tmdb_id: int
    kind: MediaKind
    #: 這次請求的 `language` 下的標題。翻譯缺時 TMDB 回英文或空字串，兩種都退回原文標題。
    title: str
    original_title: str
    #: 首播 / 上映年。TMDB 未定檔時日期是空字串，那時這裡是 `None`。
    year: int | None
    #: TMDB 的相對路徑（`/abc.jpg`）。完整網址由 `configuration` 的 base 組出來。
    poster_path: str


@dataclass(frozen=True, slots=True)
class TmdbSeasonEntry:
    """詳情頁面回的季清單裡的一筆。集數是 TMDB 自己報的，不是 `episodes` 的長度。"""

    season_number: int
    name: str
    episode_count: int
    air_date: date | None


@dataclass(frozen=True, slots=True)
class TmdbEpisode:
    """一集。`tv/{id}/season/{n}` 的 `episodes[]`。"""

    season_number: int
    episode_number: int
    name: str
    air_date: date | None
    runtime: int | None


@dataclass(frozen=True, slots=True)
class TmdbSeason:
    """`tv/{id}/season/{n}`。`season_number: 0` 是 Specials（brief §20.3）。"""

    season_number: int
    name: str
    air_date: date | None
    episodes: tuple[TmdbEpisode, ...]


@dataclass(frozen=True, slots=True)
class TmdbDetail:
    """一部作品的詳情。劇集與電影的兩組欄位名在這裡合併掉（`tv/{id}` 與 `movie/{id}`）。"""

    tmdb_id: int
    kind: MediaKind
    #: 這次請求的 `language` 下的標題。
    title: str
    original_title: str
    year: int | None
    first_air_date: date | None
    overview: str
    poster_path: str
    #: 電影片長（分鐘）。劇集是 `None`——它的片長在每一集上。
    runtime: int | None = None
    #: 比對用的標題集合：標題、原文、各國別名、各語言翻譯，去重（plan §4.3）。
    titles: tuple[str, ...] = ()
    seasons: tuple[TmdbSeasonEntry, ...] = ()
    #: Absolute episode group 的 id，沒有那種 group 時是空字串（brief §20.3）。
    absolute_group_id: str = ""


#: `episode_groups` 的 `type`：1 播出序、**2 絕對編號**、3 DVD、4 數位、5 故事線、6 製作、7 電視
#: （brief §20.3）。只有 2 是 Berth 要的那一種。
ABSOLUTE_GROUP_TYPE = 2

#: 詳情要的 append。兩種作品都要標題集合，只有劇集有 episode groups。
#: **不要 `external_ids` 與 `release_dates`**：快照裡沒有任何欄位讀它們，而後者每部電影就是
#: 一百多筆各國上映日（2026-09-09 實測 138 筆）。要用時再加回來（plan §8.3 已同步）。
DETAIL_APPENDS = {
    MediaKind.TV: "alternative_titles,translations,episode_groups",
    MediaKind.MOVIE: "alternative_titles,translations",
}


class TmdbClient(Protocol):
    async def configuration(self) -> TmdbConfiguration:
        """憑證不對時丟 `AuthFailedError`（TMDB 回 401）。"""
        ...

    async def trending(self, kind: MediaKind, *, language: str) -> tuple[TmdbEntry, ...]:
        """`trending/{tv,movie}/week`。**順序就是 TMDB 的趨勢排名**，不要重排。"""
        ...

    async def popular(self, kind: MediaKind, *, language: str) -> tuple[TmdbEntry, ...]:
        """`{tv,movie}/popular`。順序同樣照 TMDB 給的。"""
        ...

    async def search(self, query: str, *, language: str) -> tuple[TmdbEntry, ...]:
        """`search/multi`，只留劇集與電影（它也回人物）。"""
        ...

    async def detail(self, kind: MediaKind, tmdb_id: int, *, language: str) -> TmdbDetail:
        """`tv/{id}` 或 `movie/{id}`。id 不存在時丟 `NotFoundError`。"""
        ...

    async def season(self, tmdb_id: int, season_number: int, *, language: str) -> TmdbSeason:
        """`tv/{id}/season/{n}`。"""
        ...

    async def absolute_ordering(self, group_id: str) -> Mapping[tuple[int, int], int]:
        """`tv/episode_group/{id}` → `(季, 集) → 絕對編號`。"""
        ...

    async def aclose(self) -> None: ...


def credential_auth(credential: str) -> tuple[dict[str, str], dict[str, str]]:
    """憑證的兩種形狀 → 標頭與查詢參數。

    TMDB 的帳號頁同時發兩種東西，兩種都打得動 v3 端點（2026-09-08 對真 API 實測）：
    v4 的 read access token 是 JWT，走 `Authorization: Bearer`；v3 的 API key 是 32 個十六進位
    字元，走 `?api_key=`。使用者貼哪一種都該成立，所以認的是形狀而不是一個設定項。
    """
    value = credential.strip()
    if not value:
        return ({}, {})
    if value.count(".") == 2:
        return ({"Authorization": f"Bearer {value}"}, {})
    return ({}, {"api_key": value})


def parse_entries(results: Any, *, kind: MediaKind | None = None) -> tuple[TmdbEntry, ...]:
    """`results[]` → 卡片。

    `kind` 是 `None` 時（trending 與 search）依每一筆的 `media_type` 決定，人物與認不得的
    型別直接丟掉；`{tv,movie}/popular` 的每一筆**沒有** `media_type`，所以由呼叫端指定。
    """
    if not isinstance(results, list):
        return ()
    entries = []
    for row in results:
        if not isinstance(row, dict):
            continue
        entry = _entry(row, kind if kind is not None else _kind_of(row))
        if entry is not None:
            entries.append(entry)
    return tuple(entries)


def _kind_of(row: dict[str, Any]) -> MediaKind | None:
    try:
        return MediaKind(_text(row, "media_type"))
    except ValueError:
        # `person`，或 TMDB 之後多出來的型別。探索頁只認作品。
        return None


def _entry(row: dict[str, Any], kind: MediaKind | None) -> TmdbEntry | None:
    if kind is None:
        return None
    tmdb_id = row.get("id")
    if not isinstance(tmdb_id, int):
        return None
    original = _text(row, "original_name" if kind is MediaKind.TV else "original_title")
    return TmdbEntry(
        tmdb_id=tmdb_id,
        kind=kind,
        # 翻譯缺時 TMDB 可能回空字串（brief §20.3），那時原文標題才是能顯示的東西。
        title=_text(row, "name" if kind is MediaKind.TV else "title") or original,
        original_title=original,
        year=_year(_text(row, "first_air_date" if kind is MediaKind.TV else "release_date")),
        poster_path=_text(row, "poster_path"),
    )


def parse_detail(payload: Any, kind: MediaKind) -> TmdbDetail:
    """`tv/{id}` / `movie/{id}` 的回應 → `TmdbDetail`。

    兩種作品的欄位名不同（`name` / `first_air_date` 對 `title` / `release_date`），
    差異收在這裡；季清單、標題集合與 Absolute group 的挑選也是。
    """
    if not isinstance(payload, dict):
        raise ProtocolMismatchError("detail: response is not a JSON object")
    tmdb_id = payload.get("id")
    if not isinstance(tmdb_id, int):
        raise ProtocolMismatchError("detail: payload carries no id")

    series = kind is MediaKind.TV
    original = _text(payload, "original_name" if series else "original_title")
    title = _text(payload, "name" if series else "title") or original
    aired = _date(_text(payload, "first_air_date" if series else "release_date"))
    return TmdbDetail(
        tmdb_id=tmdb_id,
        kind=kind,
        title=title,
        original_title=original,
        year=aired.year if aired is not None else None,
        first_air_date=aired,
        overview=_text(payload, "overview"),
        poster_path=_text(payload, "poster_path"),
        # 劇集的 `episode_run_time` 是一份各集片長的清單，不是作品片長；片長在每一集上。
        runtime=None if series else _int(payload.get("runtime")),
        titles=_titles(title, original, payload),
        seasons=_seasons(payload.get("seasons")) if series else (),
        absolute_group_id=_absolute_group_id(payload.get("episode_groups")),
    )


def parse_season(payload: Any) -> TmdbSeason:
    """`tv/{id}/season/{n}` 的回應 → `TmdbSeason`。"""
    if not isinstance(payload, dict):
        raise ProtocolMismatchError("season: response is not a JSON object")
    rows = payload.get("episodes")
    episodes = tuple(
        TmdbEpisode(
            season_number=_int(row.get("season_number")) or 0,
            episode_number=_int(row.get("episode_number")) or 0,
            name=_text(row, "name"),
            air_date=_date(_text(row, "air_date")),
            runtime=_int(row.get("runtime")),
        )
        for row in (rows if isinstance(rows, list) else [])
        if isinstance(row, dict)
    )
    return TmdbSeason(
        season_number=_int(payload.get("season_number")) or 0,
        name=_text(payload, "name"),
        air_date=_date(_text(payload, "air_date")),
        episodes=episodes,
    )


def parse_absolute_ordering(payload: Any) -> dict[tuple[int, int], int]:
    """`tv/episode_group/{id}` 的回應 → `(季, 集) → 絕對編號`。

    **絕對編號不是 group 裡的 `episode_number`**：那一欄保留播出序的原值，所以第二季第一集
    在 group 裡仍然是 `episode_number: 1`。絕對編號是 **0-based 的 `order` 加一**
    （brief §20.3，2026-09-08 實測 10 部）。

    用 `order` 而不是「這一筆排第幾」：兩者在一份連續的 group 上一樣，但 group 缺號時
    位置會自己編出一個 TMDB 沒說過的號碼。`order` 是 TMDB 給的答案，位置是我們的猜測。
    """
    if not isinstance(payload, dict):
        raise ProtocolMismatchError("episode_group: response is not a JSON object")
    groups = payload.get("groups")
    ordering: dict[tuple[int, int], int] = {}
    for group in groups if isinstance(groups, list) else []:
        if not isinstance(group, dict):
            continue
        rows = group.get("episodes")
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            season = _int(row.get("season_number"))
            episode = _int(row.get("episode_number"))
            order = _int(row.get("order"))
            if season is None or episode is None or order is None:
                continue
            ordering[(season, episode)] = order + 1
    return ordering


def _seasons(rows: Any) -> tuple[TmdbSeasonEntry, ...]:
    return tuple(
        TmdbSeasonEntry(
            season_number=_int(row.get("season_number")) or 0,
            name=_text(row, "name"),
            episode_count=_int(row.get("episode_count")) or 0,
            air_date=_date(_text(row, "air_date")),
        )
        for row in (rows if isinstance(rows, list) else [])
        if isinstance(row, dict) and isinstance(row.get("season_number"), int)
    )


def _absolute_group_id(payload: Any) -> str:
    """挑出 `type == 2` 的那一個 group。

    一部作品可能有好幾個 Absolute group 而且互相衝突（進擊的巨人有四個，集數 89/97/97/97
    ——brief §20.3）。這裡取第一個，並且**不拿它當唯一真相**：它只是快照上的一欄，
    比對的信心由解析器決定（plan §4.4）。
    """
    if not isinstance(payload, dict):
        return ""
    rows = payload.get("results")
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict) and row.get("type") == ABSOLUTE_GROUP_TYPE:
            group_id = row.get("id")
            if isinstance(group_id, str) and group_id:
                return group_id
    return ""


def _titles(title: str, original: str, payload: dict[str, Any]) -> tuple[str, ...]:
    """比對用的標題集合。順序有意義：標題與原文在前，別名與翻譯跟在後面。

    `alternative_titles` 是各國別名、`translations` 是各語言翻譯，兩者無關而且都要
    （brief §20.3）。空字串丟掉——TMDB 用它表示「這個語言沒有翻譯」。
    """
    found = [title, original]
    alternatives = payload.get("alternative_titles")
    if isinstance(alternatives, dict):
        found += [
            _text(row, "title") for row in alternatives.get("results", []) if isinstance(row, dict)
        ]
    translations = payload.get("translations")
    if isinstance(translations, dict):
        for row in translations.get("translations", []):
            data = row.get("data") if isinstance(row, dict) else None
            if isinstance(data, dict):
                found += [_text(data, "name"), _text(data, "title")]
    return unique_titles(found)


def unique_titles(values: Iterable[str]) -> tuple[str, ...]:
    """保序去重，順手丟掉空字串。

    順序有意義（標題與原文在前），所以不能用 `set`；空字串是 TMDB 說「這個語言沒有翻譯」
    的方式。`services/media.py` 合併兩輪詳情時用的是同一支——去重寫兩份是遲早要分岔的。
    """
    seen: dict[str, None] = {}
    for value in values:
        if value:
            seen.setdefault(value, None)
    return tuple(seen)


def _int(value: Any) -> int | None:
    """TMDB 用 `null` 表示「還不知道」（未播集數的 `runtime` 就是）。"""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _date(value: str) -> date | None:
    """`2022-04-09` → `date`。未定檔是空字串。"""
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _text(row: dict[str, Any], key: str) -> str:
    """TMDB 用 `null` 表示「沒有」，而畫面上「沒有」就是空字串。"""
    value = row.get(key)
    return value.strip() if isinstance(value, str) else ""


def _year(value: str) -> int | None:
    """`2026-08-16` → `2026`。未定檔是空字串。"""
    head = value[:4]
    return int(head) if head.isdigit() else None


__all__ = [
    "ABSOLUTE_GROUP_TYPE",
    "BASE_LANGUAGE",
    "BASE_URL",
    "DETAIL_APPENDS",
    "DISPLAY_LANGUAGE",
    "SIMPLIFIED_LANGUAGE",
    "TmdbClient",
    "TmdbConfiguration",
    "TmdbDetail",
    "TmdbEntry",
    "TmdbEpisode",
    "TmdbSeason",
    "TmdbSeasonEntry",
    "credential_auth",
    "parse_absolute_ordering",
    "parse_detail",
    "parse_entries",
    "parse_season",
    "unique_titles",
]
