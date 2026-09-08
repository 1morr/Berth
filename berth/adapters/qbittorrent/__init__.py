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


@dataclass(frozen=True, slots=True)
class CategoryOutcome:
    """`ensure_category` 的結果。`save_path` 一律是**那台 qBittorrent 現在的值**。"""

    name: str
    save_path: str
    #: 這一次建的。已經在那裡的話是 False，重跑精靈時大部分是這樣。
    created: bool
    #: 同名的 category 已存在，但指向別的 save path。Berth 不覆寫它。
    conflict: bool


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

    async def create_category(self, name: str, save_path: str) -> None:
        """`torrents/createCategory`。同名的已經存在時回 409（實測原始碼的
        `Unable to create category`），所以呼叫端要先讀再建——`ensure_category` 做這件事。
        """
        ...

    async def aclose(self) -> None: ...


async def ensure_category(client: QbittorrentClient, name: str, save_path: str) -> CategoryOutcome:
    """一個 Route 的 category：不存在才建，存在但 save path 不同就回報衝突（plan §8.1）。

    **衝突不覆寫**：autoTMM 開著時改 category 的 savePath 會自動搬走該分類的所有 torrent
    （brief §20.2），那是使用者自己的資料。畫面把兩個路徑並排，讓他自己決定。

    比對前正規化尾斜線：4.4 把設進去的 `/data/x` 讀回來寫成 `/data/x/`（brief §20.7），
    照字面比會讓每次重跑都判成衝突。
    """
    existing = next((row for row in await client.categories() if row.name == name), None)
    if existing is None:
        await client.create_category(name, save_path)
        return CategoryOutcome(name=name, save_path=save_path, created=True, conflict=False)
    return CategoryOutcome(
        name=name,
        save_path=existing.save_path,
        created=False,
        conflict=_normalise(existing.save_path) != _normalise(save_path),
    )


def _normalise(path: str) -> str:
    return path.rstrip("/") or "/"


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
    "CategoryOutcome",
    "QbittorrentCategory",
    "QbittorrentClient",
    "QbittorrentVersion",
    "ensure_category",
]
