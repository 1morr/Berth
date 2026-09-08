"""qBittorrent adapter（plan §8.1）。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

#: 支援下限（brief §16.4）。低於它的 Web API 缺少 Berth 要用的端點，精靈拒絕接入。
MIN_WEBAPI = (2, 8, 4)

#: `torrents/add` 改用 `stopped` 的那一版。實測 4.4.5（2.8.5）只認 `paused`、
#: 5.2.3（2.15.1）只認 `stopped`，送錯的那個**被靜默忽略**，torrent 就開始下載（brief §20.7）。
STOPPED_SINCE_WEBAPI = (2, 11)


@dataclass(frozen=True, slots=True)
class QbittorrentVersion:
    """`app/version` 與 `app/webapiVersion`。

    版本判斷是必要條件不是最佳化：送錯 `paused` / `stopped` 會被靜默忽略（brief §20.7）。
    """

    app: str
    webapi: str

    @property
    def supported(self) -> bool:
        return _parse(self.webapi) >= MIN_WEBAPI

    @property
    def pause_parameter(self) -> str:
        """加入 torrent 時要送的那個「先別下載」參數。"""
        return "stopped" if _parse(self.webapi) >= STOPPED_SINCE_WEBAPI else "paused"


@dataclass(frozen=True, slots=True)
class QbittorrentCategory:
    """`torrents/categories` 的一列。"""

    name: str
    save_path: str


class QbittorrentClient(Protocol):
    @property
    def base_url(self) -> str: ...

    async def login(self, username: str, password: str) -> None:
        """帳密不對時丟 `AuthFailedError`。免密的套件內服務不需要呼叫。"""
        ...

    async def version(self) -> QbittorrentVersion: ...

    async def preferences(self) -> Mapping[str, Any]:
        """`app/preferences`。精靈第 4 步拿它與建議值比對（plan §8.1）。"""
        ...

    async def set_preferences(self, values: Mapping[str, Any]) -> None:
        """`app/setPreferences`。只送要改的鍵，其餘不動。"""
        ...

    async def categories(self) -> tuple[QbittorrentCategory, ...]: ...

    async def aclose(self) -> None: ...


def _parse(version: str) -> tuple[int, ...]:
    """`2.8.5` → `(2, 8, 5)`。認不得的字串當成 0，也就是「太舊」。"""
    parts: list[int] = []
    for chunk in version.strip().split("."):
        digits = "".join(char for char in chunk if char.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


__all__ = [
    "MIN_WEBAPI",
    "STOPPED_SINCE_WEBAPI",
    "QbittorrentCategory",
    "QbittorrentClient",
    "QbittorrentVersion",
]
