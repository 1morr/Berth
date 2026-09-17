"""替某一位使用者向 Jellyfin 讀寫東西的唯一入口：權限閘門（M1.5 票 03、plan §11.2b）。

Berth 只有一把伺服器 API key，而 Jellyfin 把 API key 當管理員：帶誰的 `userId` 就是誰，帶
`parentId` 的查詢**不套**媒體庫權限，停用的帳號也照樣代讀得到（12.1.0 實測，研究
library-browsing.md §2、§9）。所以「這個人看得到什麼」由 Berth 自己擋，而且只在這裡擋：

- **`userId` 一律取自 session**。入口收的是 `AuthenticatedUser`
  （`services/auth.read_session` 的產物），沒有任何一個參數收得下前端送來的 id。
- **媒體庫 id 對 `GET /UserViews?userId=` 的允許清單驗證**，不在清單就丟 `LibraryNotVisibleError`，
  而且**在問 Jellyfin 之前**。`parentId` 只放驗過的媒體庫 id：劇或季當 `parentId` 連使用者自己的
  token 都擋不住，所以這裡根本不收它們。
- **允許清單與 `Policy` 同一份短時間快取**（`AccessCache`）。帳號被停用就結束這個人的每一張
  Berth session，而不是縮短 session 的效期（brief §19）。
- **寫入只有標記已看 / 未看**（`JellyfinAccess.mark_played`，票 05）。它不先查可見性：
  `UserPlayedItems` 自己查，看不到的回 404 而且沒有寫入（研究 §5 的原始碼；12.1.0 打完立刻讀回，
  研究 §2 的表）。

單一作品與集的讀取（`/Items/{id}?userId=`、`/Shows/{id}/Seasons|Episodes?userId=`，會檢查可見性的那幾支）
要加在這裡，跟著它們第一個呼叫端一起來（票 08）。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import NotFoundError, ServiceError
from berth.adapters.jellyfin import (
    ITEM_MOVIE,
    ITEM_SERIES,
    JellyfinClient,
    JellyfinItem,
    JellyfinPage,
    JellyfinView,
)
from berth.domain import CollectionType, MediaKind
from berth.models import JellyfinSettings
from berth.services.auth import AuthenticatedUser, end_sessions
from berth.services.clients import ServiceClientFactory
from berth.services.settings import read_settings
from berth.services.steps import message
from berth.services.watch import WatchState, watch_state

#: 允許清單與 `Policy` 記多久（秒）。
#:
#: **取捨是「縮權與停用最久晚多久生效」對「每個請求多打幾支 Jellyfin」**。一頁媒體庫牆是兩到三個
#: API 請求（切換列、牆、換頁），不快取的話每一個都多問兩次 Jellyfin
#: （`UserViews` 與 `Users/{id}`）。
#: 一分鐘讓一次瀏覽只問一輪，而管理員在 Jellyfin 停用一個帳號、或收回一個媒體庫之後，那個人最多再
#: 翻一分鐘——Berth 的 session 本來活 30 天、只在登入時驗證（plan §2.1），一分鐘是從 30 天縮下來的。
ACCESS_TTL_SECONDS = 60.0

#: Berth 瀏覽得了的媒體庫類型，與牆上那一種作品。音樂、書、`mixed` 沒有 Berth 認得的東西。
BROWSABLE: dict[CollectionType, tuple[MediaKind, str]] = {
    CollectionType.TVSHOWS: (MediaKind.TV, ITEM_SERIES),
    CollectionType.MOVIES: (MediaKind.MOVIE, ITEM_MOVIE),
}


class AccountDisabledError(Exception):
    """這個人的 Jellyfin 帳號被停用了。

    丟出之前，他在 Berth 的每一張 session 都已經刪掉並 commit。
    """


class LibraryNotVisibleError(Exception):
    """這個媒體庫不在這個人的允許清單上。**沒有權限、瀏覽不了、不存在是同一種拒絕**：
    分得出來就是在告訴人那個媒體庫存在。"""


class ItemNotVisibleError(Exception):
    """這位使用者在 Jellyfin 看不到這個 item，或沒有這個 item：與 `LibraryNotVisibleError`
    同一個道理，兩者不分。"""


class JellyfinUnreachableError(Exception):
    """問不到 Jellyfin。`detail` 是服務回的原文，畫面貼得出來（PRODUCT 原則 4）。"""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


@dataclass(frozen=True, slots=True)
class BrowsableLibrary:
    """允許清單上、Berth 瀏覽得了的一個媒體庫。"""

    id: str
    name: str
    collection_type: CollectionType

    @property
    def kind(self) -> MediaKind:
        return BROWSABLE[self.collection_type][0]

    @property
    def item_type(self) -> str:
        """牆上那一種作品在 Jellyfin 的型別名（`includeItemTypes`）。"""
        return BROWSABLE[self.collection_type][1]


class AccessCache:
    """每位使用者一份允許清單，記 `ACCESS_TTL_SECONDS`。

    一個程序一份（`create_app` 放進 `app.state`）。

    只記「沒有停用」的答案：停用的那一刻就把 session 刪了，沒有下一次要記。
    """

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._entries: dict[str, tuple[float, tuple[BrowsableLibrary, ...]]] = {}

    def get(self, jellyfin_user_id: str) -> tuple[BrowsableLibrary, ...] | None:
        entry = self._entries.get(jellyfin_user_id)
        if entry is None:
            return None
        expires, libraries = entry
        if self._clock() >= expires:
            del self._entries[jellyfin_user_id]
            return None
        return libraries

    def put(self, jellyfin_user_id: str, libraries: tuple[BrowsableLibrary, ...]) -> None:
        self._entries[jellyfin_user_id] = (self._clock() + ACCESS_TTL_SECONDS, libraries)


class JellyfinAccess:
    """一位使用者看得到的 Jellyfin。只由 `jellyfin_access` 造出來。"""

    def __init__(
        self, client: JellyfinClient, user_id: str, libraries: tuple[BrowsableLibrary, ...]
    ) -> None:
        self._client = client
        self._user_id = user_id
        self.libraries = libraries

    def library(self, library_id: str) -> BrowsableLibrary:
        found = next((row for row in self.libraries if row.id == library_id), None)
        if found is None:
            raise LibraryNotVisibleError("no such library, or not yours to see")
        return found

    async def page(self, library_id: str, *, start: int, limit: int) -> JellyfinPage:
        """這個媒體庫的一頁作品。媒體庫先對允許清單驗過，才會變成 `parentId`。"""
        library = self.library(library_id)
        with reachable():
            return await self._client.library_page(
                user_id=self._user_id,
                library_id=library.id,
                item_type=library.item_type,
                start=start,
                limit=limit,
            )

    async def index(self, library_id: str) -> tuple[JellyfinItem, ...]:
        """這個媒體庫的每一部作品（只有 id、名稱、年份、TMDB id、Primary 圖的 tag）。
        同樣先驗媒體庫。"""
        library = self.library(library_id)
        with reachable():
            return await self._client.library_index(
                user_id=self._user_id, library_id=library.id, item_type=library.item_type
            )

    async def mark_played(self, item_id: str, *, played: bool) -> WatchState:
        """把這個 item 標為已看或未看，寫進這個人在 Jellyfin 的紀錄；回寫入之後的觀看狀態。

        **對劇集會遞迴到每一集**，標為未看清掉觀看次數與最後觀看時間、復原不了（研究 §5）——
        要不要先確認是畫面的事。看不到這個 item 時丟 `ItemNotVisibleError`，Jellyfin 那一端
        沒有寫入。
        """
        with reachable():
            try:
                written = await self._client.mark_played(
                    user_id=self._user_id, item_id=item_id, played=played
                )
            except NotFoundError as exc:
                # 在 `reachable()` 之內先接住：404 是答案，不是「問不到」。
                raise ItemNotVisibleError("no such item, or not yours to see") from exc
        return watch_state(written)


@asynccontextmanager
async def jellyfin_access(
    session: AsyncSession,
    factory: ServiceClientFactory,
    cache: AccessCache,
    user: AuthenticatedUser,
) -> AsyncIterator[JellyfinAccess]:
    """打開這位使用者看得到的 Jellyfin。帳號停用時丟 `AccountDisabledError`，問不到時丟
    `JellyfinUnreachableError`；兩者都在交出任何東西之前。"""
    settings = await read_settings(session, JellyfinSettings)
    client = factory.jellyfin(settings.base_url, token=settings.api_key)
    try:
        libraries = cache.get(user.jellyfin_user_id)
        if libraries is None:
            libraries = await _grant(session, client, user)
            cache.put(user.jellyfin_user_id, libraries)
        yield JellyfinAccess(client, user.jellyfin_user_id, libraries)
    finally:
        await client.aclose()


async def _grant(
    session: AsyncSession, client: JellyfinClient, user: AuthenticatedUser
) -> tuple[BrowsableLibrary, ...]:
    with reachable():
        policy, views = await asyncio.gather(
            client.user_policy(user.jellyfin_user_id), client.user_views(user.jellyfin_user_id)
        )
    if policy.is_disabled:
        await end_sessions(session, user.id)
        raise AccountDisabledError("this Jellyfin account is disabled")
    return tuple(_browsable(view) for view in views if view.collection_type in _TYPES)


_TYPES = {kind.value for kind in BROWSABLE}


@contextmanager
def reachable() -> Iterator[None]:
    """服務層的錯誤一律翻成 `JellyfinUnreachableError`，帶著服務回的原文。"""
    try:
        yield
    except ServiceError as exc:
        raise JellyfinUnreachableError(message(exc)) from exc


def _browsable(view: JellyfinView) -> BrowsableLibrary:
    return BrowsableLibrary(
        id=view.id, name=view.name, collection_type=CollectionType(view.collection_type)
    )
