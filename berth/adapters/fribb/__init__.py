"""Fribb/anime-lists adapter（M5 票 16、plan §8.10、brief §20.3〈動漫 ID 對應〉）。

一個問題：**這個 AniList 條目在 TMDB 是哪一部、第幾季、從第幾集起**。TMDB 常把好幾輪併成一季
（Re:Zero 第 2–4 季都在 TMDB 第 1 季），字幕組卻照輪次編號；Fribb 的 `season.tmdb` 與
`episode_offset.tmdb` 就是這個換算。

表是一個 7.5 MB 的 JSON（`anime-list-full.json`），**執行時**下載到 `CONFIG_ROOT`、每週換一次，
不打包進 repo 或 image：倉庫沒有授權檔，資料出自 ODbL 的 anime-offline-database（brief §20.3）。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

LIST_URL = "https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-full.json"


@dataclass(frozen=True, slots=True)
class FribbEntry:
    anilist_id: int
    #: `TV`、`MOVIE`、`OVA`、`ONA`、`SPECIAL`；沒填是 `None`。
    type: str | None
    mal_id: int | None
    #: TMDB 的劇集 id（`themoviedb_id.tv`）。
    tmdb_tv: int | None
    #: TMDB 的電影 id（`themoviedb_id.movie`，可以不只一部）。
    tmdb_movies: tuple[int, ...]
    #: 在 TMDB 那部劇集的第幾季；0 是 Specials。
    tmdb_season: int | None
    #: 這個條目（一季或一個 cour）在那一季裡的起點前一集：第一集是 `offset + 1`。沒寫是從第 1 集起。
    tmdb_episode_offset: int | None


class AnimeIds(Protocol):
    async def lookup(self, anilist_ids: Sequence[int]) -> dict[int, FribbEntry]:
        """對得到的那幾個；對不到的不在結果裡。

        表還沒下載過而這一刻也下載不到是 `ServiceUnavailableError`；下載到的不是那張表是
        `ProtocolMismatchError`。下載過、只是這一刻更新不了就用舊的那一份。
        """
        ...


def parse_list(answer: Any) -> dict[int, FribbEntry]:
    """整張表 → AniList id 索引。沒有 AniList id 的條目（約一半）不收。"""
    index: dict[int, FribbEntry] = {}
    for item in answer:
        if not isinstance(item, dict):
            continue
        anilist_id = _int(item.get("anilist_id"))
        if anilist_id is None or anilist_id in index:
            continue
        index[anilist_id] = parse_entry(anilist_id, item)
    return index


def parse_entry(anilist_id: int, item: dict[str, Any]) -> FribbEntry:
    tmdb = _dict(item.get("themoviedb_id"))
    season = _dict(item.get("season"))
    offset = _dict(item.get("episode_offset"))
    movies = tmdb.get("movie")
    return FribbEntry(
        anilist_id=anilist_id,
        type=item.get("type") if isinstance(item.get("type"), str) else None,
        mal_id=_int(item.get("mal_id")),
        tmdb_tv=_int(tmdb.get("tv")),
        tmdb_movies=tuple(m for m in movies if _int(m) is not None)
        if isinstance(movies, list)
        else (),
        tmdb_season=_int(season.get("tmdb")),
        tmdb_episode_offset=_int(offset.get("tmdb")),
    )


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


__all__ = ["LIST_URL", "AnimeIds", "FribbEntry", "parse_list"]
