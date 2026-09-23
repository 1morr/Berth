"""媒體庫的端點（plan §6 inventory 群組、票 13、M1.5 票 03、`.scratch/m1.5/library-shape.md`）。

誰進得來由門禁決定（`api/gate.py`）：不在白名單上，所以未登入一律 401。看媒體庫**不是**
管理動作，一般使用者也看得了（brief §11）。**看得到哪幾個媒體庫**由權限閘門決定
（`services/jellyfin_access.py`）：Jellyfin 的使用者 id 只從 session 來，這裡沒有任何一個參數收它。

路徑叫 `inventory` 不叫 `library`：`CONTEXT.md` 裡程式碼的 `library` 一律指 Jellyfin 那一端的
媒體庫（前端的頁面網址仍是 plan §7 的 `/library/:libraryId`）。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict

from berth.api.deps import AccessCacheDep, ClientFactoryDep, SessionDep
from berth.api.jellyfin import (
    access_refusal,
    access_responses,
    image_url,
    session_user,
    watching_out,
)
from berth.api.schemas import JellyfinWebOut, WatchingOut, WatchStateOut
from berth.domain import (
    CollectionType,
    ImageSize,
    InventoryStatus,
    JellyfinImageType,
    JellyfinPresence,
    LibrarySort,
    MediaKind,
    ReviewKind,
    SortOrder,
)
from berth.services.deeplink import jellyfin_web
from berth.services.inventory import InventoryCard, read_wall
from berth.services.jellyfin_access import (
    AccountDisabledError,
    JellyfinUnreachableError,
    LibraryNotVisibleError,
    SortNotOfferedError,
    WallQuery,
    jellyfin_access,
)
from berth.services.review import library_counts
from berth.services.watching import read_watching

#: 牆上按名字找的上限（M2 票 14）。作品名沒有這麼長；再長的只是貼錯了東西，不轉給 Jellyfin。
QUERY_MAX_LENGTH = 200

router = APIRouter(prefix="/inventory", tags=["inventory"])


class InventoryLibraryOut(BaseModel):
    """這位使用者看得到、Berth 瀏覽得了的一個媒體庫。

    切換列只畫名稱（`.scratch/m1.5/library-shape.md`）；兩個篩選的數字在牆上（`InventoryOut`）。
    """

    model_config = ConfigDict(from_attributes=True)

    #: Jellyfin 的媒體庫 id，也是頁面網址的那一段。
    id: str
    name: str
    collection_type: CollectionType
    #: 排序選單，照 jellyfin-web 的順序；第一個是打開牆時的排序（票 06）。劇集庫與電影庫不同，
    #: 牆那一支只收這裡有的。
    sorts: list[LibrarySort]


class InventoryFiltersOut(BaseModel):
    """類型與年份篩選的選項：這個媒體庫裡的作品有的那些（Jellyfin `/Items/Filters`，票 06）。"""

    model_config = ConfigDict(from_attributes=True)

    genres: list[str]
    years: list[int]


class TrackingOut(BaseModel):
    """Berth 經手的作品在這個媒體庫上的入庫狀態。判定規則在 `services/inventory.py`。"""

    model_config = ConfigDict(from_attributes=True)

    #: 依序取第一個成立的：失敗 → 待審 → 下載中 → 已入庫 / 部分 / 沒有檔案。
    status: InventoryStatus
    #: 劇集：已播出的正片入庫了幾集（不含 S00）。電影：0 或 1。
    imported: int
    #: 劇集：TMDB 上已播出的正片集數。電影一律是 1。
    aired: int
    #: 電影的正片版本數；劇集是 0。
    versions: int
    #: medium 自動入庫、掛著 audit 的檔案數（跨這部作品在這個媒體庫的 Job 加總，票 15）。
    audits: int


class InventoryCardOut(BaseModel):
    """牆上的一格。在不在 Jellyfin、連到哪裡、需不需要人都由後端算好，前端只照畫。"""

    model_config = ConfigDict(from_attributes=True)

    #: `/media/:id` 要開的作品；空字串時這一格只有 Jellyfin 的深連結。
    media_id: str
    kind: MediaKind
    #: 在 Jellyfin 裡的作品兩格都是 Jellyfin 的名稱；還沒進的是 `zh-TW` 與英文兩輪，
    #: 畫面照 UI 語言挑。
    title: str
    title_en: str
    year: int | None
    #: 還沒進 Jellyfin 的是 TMDB 的海報（兩輪，畫面照 UI 語言挑；TMDB 的海報分語言，票 11）；
    #: 在 Jellyfin 裡的是 Berth 代理的 Jellyfin Primary 圖（`/api/jellyfin/items/...`，票 04），
    #: 兩格相同。沒有海報時是空字串。
    poster_url: str
    poster_url_en: str
    presence: JellyfinPresence
    #: 深連結要開的 Series / Movie。還沒進 Jellyfin 時是空字串。
    jellyfin_item_id: str
    #: Berth 沒經手的作品是 `null`。
    tracking: TrackingOut | None
    #: 這位使用者看到哪了（票 05）。只有 `titles` 的卡片有；`tracked` 一律是 `null`（整份清單不帶
    #: 觀看紀錄），還沒進 Jellyfin 的也是。
    watch: WatchStateOut | None


class InventoryOut(BaseModel):
    library: InventoryLibraryOut
    #: 深連結的主機。每一格都用同一台，所以放在牆上而不是逐格帶。
    jellyfin: JellyfinWebOut
    page: int
    page_size: int
    #: Jellyfin 說這個媒體庫一共有幾部。
    total: int
    #: Jellyfin 的這一頁。
    titles: list[InventoryCardOut]
    #: 這個媒體庫上 Berth 經手的每一部，不分頁：「還沒進 Jellyfin」那一條從這裡取。
    tracked: list[InventoryCardOut]
    #: 「待審」「對不到」兩個篩選鍵的數字：審核佇列在這個媒體庫上的 `plan` 與 `unmatched` 各幾件
    #: （M2 票 14，使用者拍板數件不數部）。清單本身是 `GET /review?library=`，同一支查詢。
    review: int
    unmatched: int


#: 切換列不碰單一媒體庫，所以只有這兩種。decorator 與底下的 `except` 吃同一份。
_LIBRARIES_REFUSALS = (AccountDisabledError, JellyfinUnreachableError)


@router.get("", responses=access_responses(*_LIBRARIES_REFUSALS))
async def get_inventories(
    session: SessionDep, factory: ClientFactoryDep, cache: AccessCacheDep, request: Request
) -> list[InventoryLibraryOut]:
    """切換列：這位使用者在 Jellyfin 看得到、Berth 瀏覽得了的媒體庫。"""
    try:
        async with jellyfin_access(session, factory, cache, session_user(request)) as access:
            libraries = access.libraries
    except _LIBRARIES_REFUSALS as refusal:
        raise access_refusal(refusal) from refusal
    return [InventoryLibraryOut.model_validate(row) for row in libraries]


#: 牆另外會遇到選單外的排序鍵（票 06）。
_WALL_REFUSALS = (
    AccountDisabledError,
    JellyfinUnreachableError,
    LibraryNotVisibleError,
    SortNotOfferedError,
)


@router.get("/{library_id}", responses=access_responses(*_WALL_REFUSALS))
async def get_inventory(
    session: SessionDep,
    factory: ClientFactoryDep,
    cache: AccessCacheDep,
    request: Request,
    library_id: str,
    page: Annotated[int, Query(ge=1)] = 1,
    sort: LibrarySort | None = None,
    order: SortOrder = SortOrder.ASCENDING,
    genres: Annotated[list[str] | None, Query()] = None,
    years: Annotated[list[int] | None, Query()] = None,
    q: Annotated[str, Query(max_length=QUERY_MAX_LENGTH)] = "",
) -> InventoryOut:
    """一頁牆。`sort` 要在這個媒體庫的 `sorts` 上（否則 422 `sort_not_offered`）；`genres` 與
    `years` 重複帶，同一種之間是「或」、兩種之間是「且」；`q` 是名字裡的一段（Jellyfin 的
    `searchTerm`，M2 票 14），前後的空白不算。排序、篩選與名字只套在 `titles`：`tracked` 與
    兩個篩選的數字是 Berth 的。"""
    query = WallQuery(
        sort=sort,
        order=order,
        genres=tuple(genres or ()),
        years=tuple(years or ()),
        search=q.strip(),
    )
    try:
        async with jellyfin_access(session, factory, cache, session_user(request)) as access:
            wall = await read_wall(session, access, library_id, page=page, query=query)
    except _WALL_REFUSALS as refusal:
        raise access_refusal(refusal) from refusal
    # 媒體庫先過了權限閘門才數：看不到它的人連它有幾件待審都不該知道。
    counts = await library_counts(session, wall.library.id)
    return InventoryOut(
        library=InventoryLibraryOut.model_validate(wall.library),
        jellyfin=JellyfinWebOut.model_validate(await jellyfin_web(session)),
        page=wall.page,
        page_size=wall.page_size,
        total=wall.total,
        titles=[_card(card) for card in wall.titles],
        tracked=[_card(card) for card in wall.tracked],
        review=counts[ReviewKind.PLAN],
        unmatched=counts[ReviewKind.UNMATCHED],
    )


#: 篩選面板與媒體庫那兩列：先驗媒體庫，但沒有排序鍵。
_LIBRARY_REFUSALS = (AccountDisabledError, JellyfinUnreachableError, LibraryNotVisibleError)


@router.get("/{library_id}/filters", responses=access_responses(*_LIBRARY_REFUSALS))
async def get_inventory_filters(
    session: SessionDep,
    factory: ClientFactoryDep,
    cache: AccessCacheDep,
    request: Request,
    library_id: str,
) -> InventoryFiltersOut:
    """篩選面板的選項。與牆分開一支：換頁、換排序都不必重問，而 jellyfin-web 也是打開面板才問。"""
    try:
        async with jellyfin_access(session, factory, cache, session_user(request)) as access:
            filters = await access.filters(library_id)
    except _LIBRARY_REFUSALS as refusal:
        raise access_refusal(refusal) from refusal
    return InventoryFiltersOut.model_validate(filters)


@router.get("/{library_id}/watching", responses=access_responses(*_LIBRARY_REFUSALS))
async def get_inventory_watching(
    session: SessionDep,
    factory: ClientFactoryDep,
    cache: AccessCacheDep,
    request: Request,
    library_id: str,
) -> WatchingOut:
    """這個媒體庫的繼續觀看與下一集（票 07）。媒體庫先對允許清單驗過才轉給 Jellyfin：帶了 `parentId`
    的 Resume 與 NextUp 不套媒體庫權限（研究 §2）。"""
    try:
        async with jellyfin_access(session, factory, cache, session_user(request)) as access:
            watching = await read_watching(access, library_id)
    except _LIBRARY_REFUSALS as refusal:
        raise access_refusal(refusal) from refusal
    return await watching_out(session, watching)


def _card(card: InventoryCard) -> InventoryCardOut:
    """在 Jellyfin 裡的作品，海報網址在這一層組：services 只知道 Jellyfin 的 tag，
    不知道 `/api` 的路由。"""
    out = InventoryCardOut.model_validate(card)
    if not card.poster_tag:
        return out
    url = image_url(
        card.jellyfin_item_id, JellyfinImageType.PRIMARY, size=ImageSize.POSTER, tag=card.poster_tag
    )
    # Jellyfin 的圖不分語言（名稱也是兩格相同），所以兩輪是同一張。
    return out.model_copy(update={"poster_url": url, "poster_url_en": url})
