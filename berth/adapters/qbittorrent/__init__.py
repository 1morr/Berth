"""qBittorrent adapter（plan §8.1）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class QbittorrentVersion:
    """`app/version` 與 `app/webapiVersion`。

    版本判斷是必要條件不是最佳化：送錯 `paused` / `stopped` 會被靜默忽略（brief §20.7）。
    """

    app: str
    webapi: str


class QbittorrentClient(Protocol):
    """票 08 起會擴充（偏好差異、category）。"""

    @property
    def base_url(self) -> str: ...

    async def login(self, username: str, password: str) -> None:
        """帳密不對時丟 `AuthFailedError`。免密的套件內服務不需要呼叫。"""
        ...

    async def version(self) -> QbittorrentVersion: ...

    async def aclose(self) -> None: ...


__all__ = ["QbittorrentClient", "QbittorrentVersion"]
