"""qBittorrent adapter（plan §8.1）。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from berth.adapters.http import ServiceError

#: 支援下限（brief §16.4）。低於它的 Web API 缺少 Berth 要用的端點，精靈拒絕接入。
MIN_WEBAPI = (2, 8, 4)

#: `torrents/add` 改用 `stopped` 的那一版。實測 4.4.5（2.8.5）只認 `paused`、
#: 5.2.3（2.15.1）只認 `stopped`，送錯的那個**被靜默忽略**，torrent 就開始下載（brief §20.7）。
STOPPED_SINCE_WEBAPI = (2, 11)


class TorrentRejectedError(ServiceError):
    """qBittorrent 答話了，而它不收這一個 torrent。

    2026-09-10 對 5.2.3 實測到兩種：`409 Conflict`（已經有同一個 hash，或 category 的
    save path 用不了）與 `415`（那份 `.torrent` 不是有效的 torrent，body 帶檔名與原因）。

    與「連不上」分開的理由是**下一步不同**：這一個重試一百次多半還是一樣，而連不上
    只要等服務回來。畫面上兩種都是 `submit_failed`，但原文說得出是哪一種（plan §3.1）。
    """


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


#: 每一筆 Berth 送出去的 torrent 都掛這個 tag（plan §8.1）。它讓使用者在 qBittorrent 自己的
#: 介面上分得出「這是 Berth 放的」，也讓票 10 的 poller 有一個 category 之外的第二道篩子。
BERTH_TAG = "berth"

#: `Original` = 照 torrent 自己的結構存（brief §20.7 實測四種組合，`torrents/files[].name`
#: 一律相對 `save_path`）。改成別的會讓解析器看到的路徑與做種中的檔案佈局不一樣。
CONTENT_LAYOUT = "Original"


@dataclass(frozen=True, slots=True)
class TorrentAdd:
    """要加進 qBittorrent 的一份。

    `magnet` 與 `content` 剛好有一個（`adapters.torrent.TorrentSource` 的同一個分岔）：
    前者是表單值，後者是 multipart 的檔案欄位，兩邊在 `torrents/add` 上不是同一種東西。
    """

    #: `<route.category>`。save path 由它決定，因為 `autoTMM=true`（brief §4.1）。
    category: str
    magnet: str = ""
    content: bytes = b""
    filename: str = "berth.torrent"


def add_form(request: TorrentAdd, version: QbittorrentVersion) -> dict[str, str]:
    """`torrents/add` 的表單值（不含 `.torrent` 那個檔案欄位）。

    抽出來是因為**版本矩陣要測得到**：`paused` / `stopped` 選錯的那一半不會報錯，
    只會靜默地做相反的事（brief §20.7），所以那個選擇要有一個看得見、驗得了的形狀。

    `savepath` 刻意不送：`autoTMM=true` 時路徑由 category 決定，兩個來源會讓「這個 torrent
    存到哪裡」有兩個答案，而其中一個會在使用者改 category 時悄悄過期。
    """
    form = {
        "category": request.category,
        "tags": BERTH_TAG,
        "contentLayout": CONTENT_LAYOUT,
        "autoTMM": "true",
        # **明講「開始下載」**：qBittorrent 有一個「加入後不自動開始」的全域偏好，而
        # plan §3.1 的狀態機假設送出去的 torrent 會自己走到 `metadata_ready`。
        version.pause_parameter: "false",
    }
    if request.magnet:
        form["urls"] = request.magnet
    return form


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

    async def add_torrent(self, request: TorrentAdd) -> None:
        """`torrents/add`。qBittorrent 不收就丟 `ServiceError` 的子類。

        版本判斷在**實作裡**而不是呼叫端：它要讀 `app/webapiVersion`，而那是這一層的事
        （plan §8.1）。呼叫端只說「加這一個」，不必記得哪一版叫什麼。
        """
        ...

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
    "BERTH_TAG",
    "CONTENT_LAYOUT",
    "MIN_WEBAPI",
    "STOPPED_SINCE_WEBAPI",
    "CategoryOutcome",
    "QbittorrentCategory",
    "QbittorrentClient",
    "QbittorrentVersion",
    "TorrentAdd",
    "TorrentRejectedError",
    "add_form",
    "ensure_category",
]
