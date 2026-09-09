"""TMDB adapter（plan §8.3）。

**憑證由使用者自備**：Berth 不內建任何 provider 的 API key（brief §16.3、§20.7），唯一的來源是
`settings.services.tmdb.api_key`，取用它的地方只有 `services.tmdb.credential()`。

這一層只做翻譯：把 TMDB 三種端點各自的欄位名收斂成一個 `TmdbEntry`。挑哪些作品、
怎麼快取、要不要合併兩種語言，都是 `services/discover.py` 的事。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from berth.domain import MediaKind

BASE_URL = "https://api.themoviedb.org/3"

#: 取英文標題與檔名用的那一輪（brief §7.5）。
BASE_LANGUAGE = "en-US"
#: 顯示用標題另外取的那一輪（plan §8.3）。
DISPLAY_LANGUAGE = "zh-TW"


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


def _text(row: dict[str, Any], key: str) -> str:
    """TMDB 用 `null` 表示「沒有」，而畫面上「沒有」就是空字串。"""
    value = row.get(key)
    return value.strip() if isinstance(value, str) else ""


def _year(date: str) -> int | None:
    """`2026-08-16` → `2026`。未定檔是空字串。"""
    head = date[:4]
    return int(head) if head.isdigit() else None


__all__ = [
    "BASE_LANGUAGE",
    "BASE_URL",
    "DISPLAY_LANGUAGE",
    "TmdbClient",
    "TmdbConfiguration",
    "TmdbEntry",
    "credential_auth",
    "parse_entries",
]
