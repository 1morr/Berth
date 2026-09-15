"""Jellyfin 深連結開在哪一台主機上（brief §12、§20.1、票 13）。

播放一律交給 Jellyfin（brief §12），Berth 給的是一條連到那個項目詳細頁的網址。難的不是網址的
形狀，是**主機**：Berth 存的 `base_url` 是它自己連過去的那一條，套件內是 compose 內網的
`http://jellyfin:8096`，而瀏覽器解不到那個名字。

推導順序（使用者 2026-09-15 拍板，沿用 Seerr 的 `externalHostname`）：

1. 管理員填了對外網址就用它——反向代理、另一個網域，只有人知道。
2. 既有的 Jellyfin 用使用者自己填的 `base_url`：那是他打得出來的位址，瀏覽器多半也到得了。
3. 套件內的 Jellyfin 用**瀏覽器現在的主機名** + `base_url` 的 port：compose 把 8096 發佈在
   跑 Berth 的同一台機器上。主機名只有前端知道，所以這一步回「用哪個 port」，由前端補完。
"""

from __future__ import annotations

from dataclasses import dataclass
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


async def jellyfin_web(session: AsyncSession) -> JellyfinWeb:
    settings = await read_settings(session, JellyfinSettings)
    if settings.public_url:
        return JellyfinWeb(public_url=settings.public_url, url=settings.public_url, port=None)
    setup = await read_settings(session, SetupSettings)
    probe = setup.services.get(ServiceKind.JELLYFIN)
    # 沒有判定紀錄就當既有：與健康頁的 `_origin` 同一條規則。
    if probe is None or probe.origin is not ServiceOrigin.BUNDLED:
        return JellyfinWeb(public_url="", url=settings.base_url.rstrip("/"), port=None)
    parts = urlsplit(settings.base_url)
    return JellyfinWeb(public_url="", url="", port=_port(parts.scheme, parts.netloc))


async def set_public_url(session: AsyncSession, value: str) -> JellyfinWeb:
    """存下對外網址。空白就是清掉，回到推導。尾巴的斜線拿掉——網址是接著 `/web/` 組的。"""
    text = value.strip().rstrip("/")
    if text:
        parts = urlsplit(text)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise PublicUrlRejectedError(f"{value.strip()!r} is not an http(s) address")
    settings = await read_settings(session, JellyfinSettings)
    settings.public_url = text
    await write_settings(session, settings)
    await session.commit()
    return await jellyfin_web(session)


def _port(scheme: str, netloc: str) -> int:
    try:
        explicit = urlsplit(f"{scheme}://{netloc}").port
    except ValueError:
        explicit = None
    return explicit or (443 if scheme == "https" else 80)
