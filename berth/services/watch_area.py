"""Media 詳情的觀看區（M1.5 票 08、brief §12、§13、`.scratch/m1.5/media-detail-shape.md`）。

作品在 Jellyfin 裡、而且這位使用者看得到時，詳情頁最上面是這一區：主按鈕（這部劇接下來看哪一集，
電影就是這一部）、Jellyfin 的季，與某一季的集。資料原樣來自 Jellyfin，Berth 不疊入庫狀態——那是
下面「季集與入庫」的事。

讀 Jellyfin 一律經過權限閘門（`services/jellyfin_access.py`）：找作品不帶 `parentId`、確認看得到之後
才問這部劇的下一集（帶 `seriesId` 的 NextUp 不套權限，研究 §2）。**看不到與不在 Jellyfin 是同一個
答案**（`None`），回應裡沒有任何 Jellyfin 的東西。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.jellyfin import JellyfinItem, JellyfinSeason
from berth.domain import JellyfinImageType, MediaKind, PlanAction
from berth.models import LedgerEntry, parse_media_id
from berth.models import media_id as build_media_id
from berth.services.inventory import jellyfin_link
from berth.services.jellyfin_access import ItemNotVisibleError, JellyfinAccess
from berth.services.watch import WatchState, watch_state
from berth.services.watching import CardImage

#: 一筆觀看紀錄都沒有時的樣子（Jellyfin 沒帶 `UserData`）。
UNWATCHED = WatchState(played=False, progress=None, unplayed_episodes=None)


@dataclass(frozen=True, slots=True)
class WatchEpisode:
    """選季選集的一集，也是主按鈕那一集（Carry On）。名稱是 Jellyfin 的。"""

    item_id: str
    name: str
    season: int | None
    episode_start: int | None
    episode_end: int | None
    watch: WatchState
    #: **集自己的 `Primary`**（劇照），沒有就是 `None`。不借劇的橫圖：整季一模一樣的圖沒辦法用來挑集
    #: （shape §5；jellyfin-web 的集清單退回劇的 2:3 海報，這裡是 16:9，不照做）。
    still: CardImage | None


@dataclass(frozen=True, slots=True)
class WatchSeason:
    id: str
    #: Jellyfin 的季名（跟伺服器的 metadata 語言）。
    name: str
    #: 季號；Specials 是 0，Jellyfin 認不出來是 `None`。
    number: int | None


@dataclass(frozen=True, slots=True)
class WatchArea:
    """這部作品在 Jellyfin 裡、這位使用者看得到的那一份。"""

    #: 劇或電影的 item id：深連結與「標為已看」都用它。
    item_id: str
    kind: MediaKind
    #: 劇集：剩幾集沒看或已看；電影：看到幾 % 或已看。
    watch: WatchState
    #: 劇集接下來看哪一集（看到一半的、沒看過的第一集都算）；看完了或電影是 `None`。
    carry_on: WatchEpisode | None
    #: 電影是空的。
    seasons: tuple[WatchSeason, ...]


async def read_watch_area(
    session: AsyncSession, access: JellyfinAccess, media_id: str
) -> WatchArea | None:
    """這部作品的觀看區；不在 Jellyfin 或這位使用者看不到時是 `None`，`media_id` 認不得
    也是。"""
    parsed = parse_media_id(media_id)
    if parsed is None:
        return None
    kind, tmdb_id = parsed
    links = await _links(session, build_media_id(kind, tmdb_id), kind)
    found = await access.locate(kind, tmdb_id, links=links)
    if found is None:
        return None
    watch = _watch(found)
    if kind is MediaKind.MOVIE:
        return WatchArea(item_id=found.id, kind=kind, watch=watch, carry_on=None, seasons=())
    # 兩支都在 `locate` 確認看得到之後才問：NextUp 帶 `seriesId` 不套權限（閘門擋著沒確認過的）。
    try:
        seasons, carry_on = await asyncio.gather(
            access.seasons(found.id), access.series_next_up(found.id)
        )
    except ItemNotVisibleError:
        # 確認與問季之間權限被收回（或劇被刪了）：與一開始就看不到同一個答案。
        return None
    return WatchArea(
        item_id=found.id,
        kind=kind,
        watch=watch,
        carry_on=None if carry_on is None else watch_episode(carry_on),
        seasons=tuple(_season(row) for row in seasons),
    )


async def read_episodes(
    access: JellyfinAccess, series_id: str, season_id: str
) -> tuple[WatchEpisode, ...]:
    """某一季的集。看不到這部劇或這一季時丟 `ItemNotVisibleError`（Jellyfin 自己查）。"""
    return tuple(watch_episode(row) for row in await access.episodes(series_id, season_id))


def watch_episode(item: JellyfinItem) -> WatchEpisode:
    return WatchEpisode(
        item_id=item.id,
        name=item.name,
        season=item.season,
        episode_start=item.episode_start,
        episode_end=item.episode_end,
        watch=_watch(item),
        still=CardImage(item.id, JellyfinImageType.PRIMARY, item.primary_tag)
        if item.primary_tag
        else None,
    )


def _watch(item: JellyfinItem) -> WatchState:
    """Jellyfin 沒帶 `UserData` 時是還沒看過。"""
    return watch_state(item.user_data) if item.user_data else UNWATCHED


def _season(row: JellyfinSeason) -> WatchSeason:
    return WatchSeason(id=row.id, name=row.name, number=row.number)


async def _links(session: AsyncSession, media_id: str, kind: MediaKind) -> frozenset[str]:
    """帳本記下的這部作品在 Jellyfin 的 id（劇集是 Series、電影是 Movie）。媒體庫牆的同一條規則：
    Jellyfin 認錯 TMDB id 時，Berth 自己寫下的那一個才是對的（票 03）。"""
    entries = await session.scalars(
        select(LedgerEntry).where(
            LedgerEntry.media_id == media_id, LedgerEntry.action == PlanAction.IMPORT
        )
    )
    return frozenset(link for entry in entries if (link := jellyfin_link(entry, kind)))
