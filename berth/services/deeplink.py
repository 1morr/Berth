"""對外的網址：Jellyfin 深連結開在哪一台主機上（brief §12、§20.1、票 13），與通知裡連回 Berth
的連結（M4 票 124，檔尾）。

播放一律交給 Jellyfin（brief §12），Berth 給的是一條連到那個項目詳細頁的網址。難的不是網址的
形狀，是**主機**：Berth 存的 `base_url` 是它自己連過去的那一條，套件內是 compose 內網的
`http://jellyfin:8096`，而瀏覽器解不到那個名字。

推導順序（使用者 2026-09-15 拍板，沿用 Seerr 的 `externalHostname`）：

1. 管理員填了對外網址就用它——反向代理、另一個網域，只有人知道。
2. 既有的 Jellyfin 用使用者自己填的 `base_url`：那是他打得出來的位址，瀏覽器多半也到得了。
3. 套件內的 Jellyfin 用**瀏覽器現在的主機名** + 它在宿主上發佈的 port（`JELLYFIN_PORT`，
   compose 傳給 Berth）：compose 把它發佈在跑 Berth 的同一台機器上。主機名只有前端知道，所以
   這一步回「用哪個 port」，由前端補完。**不從 `base_url` 取 port**——那是容器內的 8096，
   發佈成 `18096:8096` 時開過去的是同一台機器上的另一台 Jellyfin（票 06b）。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import ServiceKind, ServiceOrigin
from berth.models import JellyfinSettings, SetupSettings
from berth.services.settings import read_settings, write_settings


@dataclass(frozen=True, slots=True)
class JellyfinWeb:
    """深連結的主機。`url` 有值就用它；空的時候是「瀏覽器現在的主機名 + `port`」。"""

    #: 管理員填的那一個（可能是空的）。設定頁的欄位讀它，推導的結果在後兩格。
    public_url: str
    url: str
    port: int | None


class PublicUrlRejectedError(ValueError):
    """填進來的對外網址不是一個 http(s) 位址。原文照樣帶著，畫面貼在欄位下面。"""


def normalized_public_url(value: str) -> str:
    """管理員填的對外網址存成什麼：空白是清掉（`""`），尾巴的斜線拿掉——網址是接著路徑組的。
    不是 http(s) 的絕對網址丟 `PublicUrlRejectedError`；帶 `?` 或 `#` 的也是，接上路徑之後
    （`https://host?x=1/media/…`）開不到那一頁（M4 票 124）。"""
    text = value.strip().rstrip("/")
    if text:
        parts = urlsplit(text)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise PublicUrlRejectedError(f"{value.strip()!r} is not an http(s) address")
        if "?" in text or "#" in text:
            raise PublicUrlRejectedError(f"{value.strip()!r} has a query or fragment")
    return text


async def jellyfin_web(session: AsyncSession, *, published_port: int) -> JellyfinWeb:
    """`published_port` 是 `Config.jellyfin_port`：只有第 3 條用得到它。"""
    settings = await read_settings(session, JellyfinSettings)
    if settings.public_url:
        return JellyfinWeb(public_url=settings.public_url, url=settings.public_url, port=None)
    setup = await read_settings(session, SetupSettings)
    # 還沒選就當既有：與 `routes._jellyfin_origin`、健康頁 `health._view` 同一條規則。
    if setup.origin_of(ServiceKind.JELLYFIN) is not ServiceOrigin.BUNDLED:
        return JellyfinWeb(public_url="", url=settings.base_url.rstrip("/"), port=None)
    return JellyfinWeb(public_url="", url="", port=published_port)


async def set_public_url(session: AsyncSession, value: str, *, published_port: int) -> JellyfinWeb:
    """存下對外網址。空白就是清掉，回到推導（`normalized_public_url`）。"""
    text = normalized_public_url(value)
    settings = await read_settings(session, JellyfinSettings)
    settings.public_url = text
    await write_settings(session, settings)
    await session.commit()
    return await jellyfin_web(session, published_port=published_port)


# --- Berth 自己 -------------------------------------------------------------


class BerthPage(StrEnum):
    """後端組的網址指到前端的哪幾頁：前端路由表（`web/src/routes.tsx`）的路徑，`{…}` 是參數。

    進 OpenAPI（`main._document_pages`），前端的 `berthPages.test.ts` 拿每一條對真的路由表解析，
    前端改了路由、這裡沒跟上時那邊紅（M5 票 02）。要連回 Berth 的新頁面加在這裡，不在別處手組路徑。
    """

    #: 作品頁（M4 票 123）。
    MEDIA = "/media/{media_id}"
    #: 「有 N 件等你處理」的三份清單（M4 票 127）。只有一件時後面接那一列的錨點
    #: （`services.waiting`），頁面載入後捲到那一列、把焦點放上去。
    REVIEW = "/review"
    ISSUES = "/issues"
    RSS = "/rss"
    #: 週報頁的某一週（M4 票 131）。
    WEEKLY = "/weekly/{report_id}"


def berth_link(public_url: str, path: str) -> str | None:
    """Berth 內的一條路徑（`/media/tv:1234`）從外面怎麼開。`public_url` 是 `BerthSettings` 存的
    那一個；空的就是沒有連結——Berth 猜不出自己從外面看是什麼網址，不給一條開不了的。"""
    if not public_url:
        return None
    return f"{public_url}{path}"
