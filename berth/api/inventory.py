"""媒體庫的端點（plan §6 inventory 群組、票 13、M1.5 票 03、`.scratch/m1.5/library-shape.md`）。

誰進得來由門禁決定（`api/gate.py`）：不在白名單上，所以未登入一律 401。看媒體庫**不是**
管理動作，一般使用者也看得了（brief §11）。**看得到哪幾個媒體庫**由權限閘門決定
（`services/jellyfin_access.py`）：Jellyfin 的使用者 id 只從 session 來，這裡沒有任何一個參數收它。

路徑叫 `inventory` 不叫 `library`：`CONTEXT.md` 裡程式碼的 `library` 一律指 Jellyfin 那一端的
媒體庫（前端的頁面網址仍是 plan §7 的 `/library/:libraryId`）。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict

from berth.api.deps import AccessCacheDep, ClientFactoryDep, SessionDep
from berth.api.gate import current_user
from berth.api.jellyfin import image_url
from berth.api.schemas import JellyfinWebOut
from berth.domain import (
    CollectionType,
    ImageSize,
    InventoryStatus,
    JellyfinImageType,
    JellyfinPresence,
    MediaKind,
)
from berth.services.auth import AuthenticatedUser
from berth.services.deeplink import jellyfin_web
from berth.services.inventory import InventoryCard, read_wall
from berth.services.jellyfin_access import (
    AccountDisabledError,
    JellyfinUnreachableError,
    LibraryNotVisibleError,
    jellyfin_access,
)

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
    needs_review: bool
    has_unmatched: bool
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
    #: 還沒進 Jellyfin 的是 TMDB 的海報；在 Jellyfin 裡的是 Berth 代理的 Jellyfin Primary 圖
    #: （`/api/jellyfin/items/...`，票 04）。沒有海報時是空字串。
    poster_url: str
    presence: JellyfinPresence
    #: 深連結要開的 Series / Movie。還沒進 Jellyfin 時是空字串。
    jellyfin_item_id: str
    #: Berth 沒經手的作品是 `null`。
    tracking: TrackingOut | None


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
    #: 這個媒體庫上 Berth 經手的每一部，不分頁：「還沒進 Jellyfin」那一條與兩個篩選從這裡取。
    tracked: list[InventoryCardOut]
    #: `tracked` 裡有計劃停下來等人的部數（Jellyfin 內外都算）。
    review: int
    #: `tracked` 裡現在那一份計劃有對不到的檔案的部數。
    unmatched: int


@router.get("")
async def get_inventories(
    session: SessionDep, factory: ClientFactoryDep, cache: AccessCacheDep, request: Request
) -> list[InventoryLibraryOut]:
    """切換列：這位使用者在 Jellyfin 看得到、Berth 瀏覽得了的媒體庫。"""
    try:
        async with jellyfin_access(session, factory, cache, _user(request)) as access:
            libraries = access.libraries
    except (AccountDisabledError, JellyfinUnreachableError) as refusal:
        raise _refusal(refusal) from refusal
    return [InventoryLibraryOut.model_validate(row) for row in libraries]


@router.get("/{library_id}")
async def get_inventory(
    session: SessionDep,
    factory: ClientFactoryDep,
    cache: AccessCacheDep,
    request: Request,
    library_id: str,
    page: Annotated[int, Query(ge=1)] = 1,
) -> InventoryOut:
    try:
        async with jellyfin_access(session, factory, cache, _user(request)) as access:
            wall = await read_wall(session, access, library_id, page=page)
    except (AccountDisabledError, JellyfinUnreachableError, LibraryNotVisibleError) as refusal:
        raise _refusal(refusal) from refusal
    return InventoryOut(
        library=InventoryLibraryOut.model_validate(wall.library),
        jellyfin=JellyfinWebOut.model_validate(await jellyfin_web(session)),
        page=wall.page,
        page_size=wall.page_size,
        total=wall.total,
        titles=[_card(card) for card in wall.titles],
        tracked=[_card(card) for card in wall.tracked],
        review=wall.review,
        unmatched=wall.unmatched,
    )


def _card(card: InventoryCard) -> InventoryCardOut:
    """在 Jellyfin 裡的作品，海報網址在這一層組：services 只知道 Jellyfin 的 tag，
    不知道 `/api` 的路由。"""
    out = InventoryCardOut.model_validate(card)
    if not card.poster_tag:
        return out
    url = image_url(
        card.jellyfin_item_id, JellyfinImageType.PRIMARY, size=ImageSize.POSTER, tag=card.poster_tag
    )
    return out.model_copy(update={"poster_url": url})


def _user(request: Request) -> AuthenticatedUser:
    user = current_user(request)
    if user is None:  # pragma: no cover - 門禁保證不會發生
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sign in to use this API")
    return user


#: 閘門的三種拒絕 → 狀態碼與 `reason`。
#:
#: - `account_disabled`（401）：session 已經結束，前端照「登入失效」處理。
#: - `library_not_visible`（404）：沒有權限與不存在是同一個回應。
#: - `jellyfin_unreachable`（503）：`detail` 是服務回的原文。
_REFUSALS: dict[type[Exception], tuple[int, str]] = {
    AccountDisabledError: (status.HTTP_401_UNAUTHORIZED, "account_disabled"),
    LibraryNotVisibleError: (status.HTTP_404_NOT_FOUND, "library_not_visible"),
    JellyfinUnreachableError: (status.HTTP_503_SERVICE_UNAVAILABLE, "jellyfin_unreachable"),
}


def _refusal(refusal: Exception) -> HTTPException:
    """`{reason, detail}`，與 Route 設定頁的拒絕同形（`api/routes.py`）。"""
    code, reason = _REFUSALS[type(refusal)]
    return HTTPException(code, {"reason": reason, "detail": str(refusal)})
