"""繼續觀看與下一集：首頁與媒體庫頁上方的兩列（M1.5 票 07、brief §13、§19）。

資料原樣來自 Jellyfin——`/UserItems/Resume` 與 `/Shows/NextUp`，參數照 jellyfin-web 首頁
（研究 library-browsing.md §7）——Berth 不疊入庫狀態，只替每一項挑一張橫圖、說出它是哪一集、看到哪。
讀 Jellyfin 一律經過權限閘門（`services/jellyfin_access.py`）：首頁那兩支不帶 `parentId`，
Jellyfin 才照這個人的媒體庫限縮；媒體庫頁的媒體庫 id 先對允許清單驗過。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta

from berth.adapters.jellyfin import ITEM_EPISODE, ITEM_MOVIE, JellyfinItem
from berth.domain import JellyfinImageType, MediaKind
from berth.models.types import utcnow
from berth.services.jellyfin_access import JellyfinAccess
from berth.services.watch import shown_progress

#: 一次取幾項：jellyfin-web 桌機首頁（`enableOverflow`）的值，繼續觀看 12、下一集 24
#: （v10.11.11 `homesections/sections/resume.ts`、`nextUp.ts`）。收起時一列最多畫 6 格，展開才全部。
RESUME_LIMIT = 12
NEXT_UP_LIMIT = 24

#: 下一集只看這麼久以內看過的劇：jellyfin-web 的 `maxDaysForNextUp` 預設 365（它送
#: `nextUpDateCutoff = 今天 − 天數`）。那是 jellyfin-web 每個人自己的顯示設定，Berth 讀不到，
#: 所以用預設。
NEXT_UP_WINDOW = timedelta(days=365)


@dataclass(frozen=True, slots=True)
class CardImage:
    """一格要代理的那一張圖。"""

    item_id: str
    image_type: JellyfinImageType
    tag: str


@dataclass(frozen=True, slots=True)
class WatchingCard:
    """一列上的一格：一集或一部電影。點下去開 Jellyfin 的 `item_id`（Jellyfin 沒有直接播放的
    網址，研究 §8）。"""

    item_id: str
    kind: MediaKind
    #: 劇名或電影名，Jellyfin 的。
    title: str
    #: 集名；電影是空字串。
    episode_name: str
    season: int | None
    episode_start: int | None
    episode_end: int | None
    #: 電影的年份；集是 `None`（卡片說的是季集）。
    year: int | None
    #: 看到幾 %（1–99），沒在看是 `None`。
    progress: int | None
    #: 沒有任何一張合用的橫圖時是 `None`。
    image: CardImage | None


@dataclass(frozen=True, slots=True)
class Watching:
    resume: tuple[WatchingCard, ...]
    next_up: tuple[WatchingCard, ...]


async def read_watching(access: JellyfinAccess, library_id: str | None) -> Watching:
    """這個人的繼續觀看與下一集。`library_id` 是 `None` 時是整個帳號（首頁），否則只含那個媒體庫的；
    不在允許清單上丟 `LibraryNotVisibleError`，兩支都不會送出去。"""
    cutoff = utcnow() - NEXT_UP_WINDOW
    resume, next_up = await asyncio.gather(
        access.resume(library_id, limit=RESUME_LIMIT),
        access.next_up(library_id, limit=NEXT_UP_LIMIT, cutoff=cutoff),
    )
    return Watching(resume=watching_cards(resume), next_up=watching_cards(next_up))


def watching_cards(items: Iterable[JellyfinItem]) -> tuple[WatchingCard, ...]:
    """只收集與電影：卡片的第一行是季集代號或 `MOVIE` 與年份，別的型別說不出自己是什麼。
    `mediaTypes=Video` 仍可能回家庭影片與音樂錄影帶（首頁不分媒體庫，混合型媒體庫裡的也會來）。"""
    return tuple(card(item) for item in items if (card := _CARDS.get(item.type)))


def _episode_card(item: JellyfinItem) -> WatchingCard:
    return WatchingCard(
        item_id=item.id,
        kind=MediaKind.TV,
        title=item.series_name,
        episode_name=item.name,
        season=item.season,
        episode_start=item.episode_start,
        episode_end=item.episode_end,
        year=None,
        progress=_progress(item),
        image=landscape(item),
    )


def _film_card(item: JellyfinItem) -> WatchingCard:
    return WatchingCard(
        item_id=item.id,
        kind=MediaKind.MOVIE,
        title=item.name,
        episode_name="",
        season=None,
        episode_start=None,
        episode_end=None,
        year=item.year,
        progress=_progress(item),
        image=landscape(item),
    )


_CARDS = {ITEM_EPISODE: _episode_card, ITEM_MOVIE: _film_card}


def _progress(item: JellyfinItem) -> int | None:
    """不走 `watch_state`：牆上那一行「已看優先」，這一列說的是看到哪（重看到一半的片照樣有 %）。"""
    return shown_progress(item.user_data.played_percentage) if item.user_data else None


def landscape(item: JellyfinItem) -> CardImage | None:
    """橫卡的圖，照 jellyfin-web（v10.11.11 `cardBuilder.getCardImageUrl`，`preferThumb`、
    `inheritThumb` 預設成立）：自己的 Thumb → 劇的 Thumb → 父層的 Thumb → 自己的 Backdrop →
    父層的 Backdrop（只有集）→ 集自己的 Primary（劇照）。

    **電影不取 Primary**：jellyfin-web 會，但那是 2:3 海報，Jellyfin 照 16:9 填滿裁切時只剩
    中間一條。
    """
    thumb, backdrop, primary = (
        JellyfinImageType.THUMB,
        JellyfinImageType.BACKDROP,
        JellyfinImageType.PRIMARY,
    )
    episode = item.type == ITEM_EPISODE
    candidates = [
        CardImage(item.id, thumb, item.thumb_tag),
        CardImage(item.series_id, thumb, item.series_thumb_tag),
    ]
    if item.parent_thumb:
        candidates.append(CardImage(item.parent_thumb.item_id, thumb, item.parent_thumb.tag))
    candidates.append(CardImage(item.id, backdrop, item.backdrop_tag))
    if episode and item.parent_backdrop:
        candidates.append(
            CardImage(item.parent_backdrop.item_id, backdrop, item.parent_backdrop.tag)
        )
    if episode:
        candidates.append(CardImage(item.id, primary, item.primary_tag))
    return next((image for image in candidates if image.item_id and image.tag), None)
