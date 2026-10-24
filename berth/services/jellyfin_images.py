"""Jellyfin 的圖由 Berth 轉給瀏覽器（M1.5 票 04、brief §19、plan §6）。

瀏覽器只連 Berth：它不必連得到 Jellyfin，HTTPS 的 Berth 配 HTTP 的 Jellyfin 也沒有 mixed content。

- **縮放由 Jellyfin 做**，而且只有幾個具名尺寸（`IMAGE_SIZES`）：每一種尺寸 Jellyfin 都要重算一次、
  在它自己的快取裡多存一份，讓前端任意指定就是讓一個網址決定 Jellyfin 做多少事。
- **不帶 API key**：Jellyfin 的圖匿名可取（研究 library-browsing.md §6）。這一支只轉圖，
  拿不到管理員憑證，就不會因為哪個參數被塞了什麼而變成一條以管理員身分打 Jellyfin 的路。
- **不逐張檢查可見性**：誰進得來由門禁決定（要登入），與 Jellyfin 本身一樣不問這張圖屬於哪個媒體庫。
  網址要帶 item id 與 `ImageTags`（兩個 32 位十六進位），牆上沒給的圖猜不到。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import NotFoundError
from berth.adapters.jellyfin import JellyfinImage
from berth.domain import ImageSize, JellyfinImageType
from berth.models import JellyfinSettings
from berth.services.clients import ServiceClientFactory
from berth.services.jellyfin_access import reachable
from berth.services.settings import read_settings

#: 具名尺寸 → Jellyfin 的 `fillWidth` × `fillHeight`（jellyfin-web 卡片的參數，研究 §7）。
#:
#: **改數字就要換名字**（`IMAGE_QUALITY` 與 adapter 的 `format` 也是）：網址只帶尺寸名與 `tag`，
#: 而圖片回應快取一年、`immutable`——名字不換，看過的瀏覽器一年內都是舊圖。
#: `test_inventory_api.py::TestImages` 對這幾個值逐一斷言。
IMAGE_SIZES: dict[ImageSize, tuple[int, int]] = {
    # 與同一面牆上還沒進 Jellyfin 的卡片用的 TMDB `w342` 同寬（`services/discover.POSTER_SIZE`）。
    ImageSize.POSTER: (342, 513),
    # 16:9、與海報同寬：繼續觀看與下一集的格子與牆共用同一份欄數（票 07）。
    ImageSize.WIDE: (342, 192),
    # 兩倍寬的那一張（M2 票 13）：前端的 `srcset` 讓瀏覽器照格子寬與螢幕密度挑，比例不變。
    ImageSize.POSTER_LARGE: (684, 1026),
    ImageSize.WIDE_LARGE: (684, 384),
}

#: Jellyfin 的 `quality`。90 是 96（jellyfin-web 的值）的一半大小（研究 §6.1）。
IMAGE_QUALITY = 90


class ImageMissingError(Exception):
    """Jellyfin 沒有這張圖（或沒有這個 item）。卡片換成佔位。"""


async def read_image(
    session: AsyncSession,
    factory: ServiceClientFactory,
    item_id: str,
    image_type: JellyfinImageType,
    *,
    size: ImageSize,
    tag: str,
) -> JellyfinImage:
    """向 Jellyfin 要一張縮好的圖。

    沒有這張圖丟 `ImageMissingError`，問不到丟 `JellyfinUnreachableError`。
    """
    settings = await read_settings(session, JellyfinSettings)
    width, height = IMAGE_SIZES[size]
    client = factory.jellyfin(settings.base_url)
    try:
        with reachable():
            try:
                return await client.image(
                    item_id,
                    image_type.value,
                    tag=tag,
                    fill_width=width,
                    fill_height=height,
                    quality=IMAGE_QUALITY,
                )
            except NotFoundError as exc:
                # 在 `reachable()` 之內先接住：404 是答案，不是「問不到」。
                raise ImageMissingError(str(exc)) from exc
    finally:
        await client.aclose()
