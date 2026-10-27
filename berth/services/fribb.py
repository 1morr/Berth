"""AniList 條目 → TMDB 的作品、季與起始集（M5 票 16、plan §11.6〈外部資料〉、研究 08 §2.4）。

資料是 Fribb/anime-lists 的表（`adapters/fribb`）。只覆蓋約兩成的條目：近年有名的 TV 多半有，OVA、
劇場版、冷門作多半沒有——劇場版在 TMDB 是獨立的電影，對不到時由模型用標題搜尋（`series-mapping`）。

**`episode_offset` 可能差一集**（Re:Zero 第 2 季寫 26，照「offset + 1 是第一集」讀會從 E27 起、
與下一個 cour 重疊）。改正要 AniList 每個條目的集數與 TMDB 那一季的總集數，三個工具的結果才湊得齊，
所以交給 skill（`series-mapping`：同一季的範圍首尾相接、對不上用集數串、對總集數、表上註明）；
這裡只把 `first_tmdb_episode` 算好，免得模型讀錯 offset 的意思（票 16 第 4 點的決定，progress.md）。
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from berth.adapters.fribb import FribbEntry
from berth.domain import MediaKind, Role
from berth.models.media import media_id
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, command

EXTERNAL_CONTENT = (
    "This mapping (Fribb/anime-lists) is community data and its episode offsets are "
    "sometimes off by one: check that ranges in one TMDB season follow each other."
)


class AnimeIdsOut(BaseModel):
    anilist_id: int
    type: str | None
    #: Berth 的作品 id（`tv:<tmdb id>`、`movie:<tmdb id>`），`media_read_media` 收的那種。
    media_ids: list[str]
    #: 劇集那一部的第幾季；0 是 Specials。
    tmdb_season: int | None
    tmdb_episode_offset: int | None
    #: 這個條目在那一季裡的第一集（offset + 1）；不是劇集是 `None`。
    first_tmdb_episode: int | None


class AnimeIdsResult(BaseModel):
    external_content: str = EXTERNAL_CONTENT
    entries: list[AnimeIdsOut]
    #: 表上沒有、或有但沒有 TMDB id 的 AniList id：用標題搜尋 TMDB。
    unmapped: list[int]


@command(
    Effect.READ,
    audience=Role.USER,
    about=(
        "Map AniList ids to TMDB (Fribb/anime-lists): each entry's media_ids, TMDB season and "
        "first episode in that season (TMDB often folds several cours into one season). "
        "Unmapped ids, often movies and OVAs, need a title search."
    ),
)
async def lookup_anime(
    factory: ServiceClientFactory,
    anilist_ids: Annotated[list[int], Field(min_length=1, max_length=50)],
) -> AnimeIdsResult:
    """對得到 TMDB 的進 `entries`，其餘進 `unmapped`；順序照給的。"""
    table = await factory.anime_ids().lookup(anilist_ids)
    entries: list[AnimeIdsOut] = []
    unmapped: list[int] = []
    for anilist_id in dict.fromkeys(anilist_ids):
        entry = table.get(anilist_id)
        ids = _media_ids(entry) if entry is not None else []
        if entry is None or not ids:
            unmapped.append(anilist_id)
            continue
        entries.append(
            AnimeIdsOut(
                anilist_id=anilist_id,
                type=entry.type,
                media_ids=ids,
                tmdb_season=entry.tmdb_season if entry.tmdb_tv is not None else None,
                tmdb_episode_offset=entry.tmdb_episode_offset,
                first_tmdb_episode=(entry.tmdb_episode_offset or 0) + 1
                if entry.tmdb_tv is not None and entry.tmdb_season is not None
                else None,
            )
        )
    return AnimeIdsResult(entries=entries, unmapped=unmapped)


def _media_ids(entry: FribbEntry) -> list[str]:
    ids = [media_id(MediaKind.TV, entry.tmdb_tv)] if entry.tmdb_tv is not None else []
    return ids + [media_id(MediaKind.MOVIE, movie) for movie in entry.tmdb_movies]
