"""Jellyfin 的圖（plan §6、M1.5 票 04）。

路徑與 `tag` 沿用 Jellyfin 自己的 `/Items/{id}/Images/{type}?tag=`
（研究 library-browsing.md §6、§7），尺寸換成具名的 `size`（TMDB 圖片網址的 `w342` 那種做法），
不收 Jellyfin 的 `fillWidth` 之類的數字。

誰進得來由門禁決定（`api/gate.py`）：不在白名單上，所以要登入。`/jellyfin/libraries` 那一支是
管理員的，這一支不是（`ADMIN_PREFIXES` 只收那一支）。判定都在 `services/jellyfin_images.py`。
"""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Path, Query, status
from fastapi.responses import Response

from berth.api.deps import ClientFactoryDep, SessionDep
from berth.domain import ImageSize, JellyfinImageType
from berth.services.jellyfin_access import JellyfinUnreachableError
from berth.services.jellyfin_images import ImageMissingError, read_image

router = APIRouter(prefix="/jellyfin", tags=["jellyfin"])

#: Jellyfin 的 item id 與 `ImageTags` 都是 32 個小寫十六進位字元（研究 §6）。
#: **item id 會進 Jellyfin 的路徑**，所以別的形狀（`..`）不轉發。
HEX32 = r"^[0-9a-f]{32}$"

#: `/api` 底下唯一不是 `no-store` 的回應（門禁只替沒設 `Cache-Control` 的回應補 `no-store`）。
#:
#: 網址帶著 `ImageTags`，Jellyfin 換圖時網址就變，所以一年、`immutable`（重新整理也不重問）。
#: `private`：回應在門後，前置代理不該存一份給沒登入的人。
IMAGE_CACHE_CONTROL = "private, max-age=31536000, immutable"

#: 圖是 Jellyfin 那一端的內容（管理員上傳的、metadata 來源給的），卻從 Berth 的網域送出去。直接開
#: 這個網址時，一張 SVG 裡的 script 會帶著 Berth 的 session 跑；`<img>` 裡本來就不執行。照 GitHub 送
#: 使用者內容（`raw.githubusercontent.com`）的標頭：不載入任何東西、沙箱化，也不讓瀏覽器猜型別。
IMAGE_HEADERS = {
    "Cache-Control": IMAGE_CACHE_CONTROL,
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
    "X-Content-Type-Options": "nosniff",
}


def image_url(item_id: str, image_type: JellyfinImageType, *, size: ImageSize, tag: str) -> str:
    """卡片上的圖片網址。**`tag` 一定要是 DTO 的 `ImageTags`**：錯的 tag Jellyfin 一樣回圖，
    而這個網址被快取一年。`/api` 是 `main.API_PREFIX`（api 不 import main）。"""
    query = urlencode({"size": size.value, "tag": tag})
    return f"/api/jellyfin/items/{item_id}/images/{image_type.value}?{query}"


@router.get(
    "/items/{item_id}/images/{image_type}",
    response_class=Response,
    responses={
        200: {"content": {"image/webp": {}}, "description": "縮好的圖"},
        404: {"description": "`image_missing`：Jellyfin 沒有這張圖"},
        503: {"description": "`jellyfin_unreachable`：問不到 Jellyfin"},
    },
)
async def get_image(
    session: SessionDep,
    factory: ClientFactoryDep,
    item_id: Annotated[str, Path(pattern=HEX32)],
    image_type: JellyfinImageType,
    size: ImageSize,
    tag: Annotated[str, Query(pattern=HEX32)],
) -> Response:
    try:
        image = await read_image(session, factory, item_id, image_type, size=size, tag=tag)
    except ImageMissingError as missing:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, {"reason": "image_missing", "detail": str(missing)}
        ) from missing
    except JellyfinUnreachableError as refusal:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            {"reason": "jellyfin_unreachable", "detail": refusal.detail},
        ) from refusal
    return Response(
        image.content,
        media_type=image.content_type,
        headers=IMAGE_HEADERS,
    )
