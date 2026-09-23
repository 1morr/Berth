"""測試與前端演練用的 qBittorrent 替身。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any

from berth.adapters.qbittorrent import (
    QbittorrentCategory,
    QbittorrentVersion,
    TorrentAdd,
    TorrentFile,
    TorrentStatus,
)

#: 乾淨實例的偏好值，取自 `tests/fixtures/http/qbittorrent/app-preferences.*.json` 的同名鍵。
#: 五個建議鍵全部與建議值不同，所以精靈第 4 步真的有差異可套（brief §20.7）。
DEFAULT_PREFERENCES: Mapping[str, Any] = {
    "save_path": "/downloads",
    "temp_path": "/downloads/incomplete",
    "temp_path_enabled": False,
    "auto_tmm_enabled": False,
    "category_changed_tmm_enabled": False,
    "web_ui_username": "admin",
}


class FakeQbittorrentClient:
    """偏好是**有狀態**的：套用之後再讀就是新值，重按才看得出「已經是這樣」。"""

    def __init__(
        self,
        *,
        base_url: str = "http://qbittorrent:8080",
        version: QbittorrentVersion | None = None,
        preferences: Mapping[str, Any] | None = None,
        categories: tuple[QbittorrentCategory, ...] = (),
        error: Exception | None = None,
        login_error: Exception | None = None,
        set_preferences_error: Exception | None = None,
        add_error: Exception | None = None,
        torrents: tuple[TorrentStatus, ...] = (),
        files: Mapping[str, tuple[TorrentFile, ...]] | None = None,
        sync_error: Exception | None = None,
    ) -> None:
        self.base_url = base_url
        self._version = version or QbittorrentVersion(app="v5.2.3", webapi="2.15.1")
        self._preferences: dict[str, Any] = {**DEFAULT_PREFERENCES, **(preferences or {})}
        self._categories = list(categories)
        #: 探測要看得到這個旗標：情境切換時要分得出「這一台壞了」與「這一台好了」。
        self.error = error
        self._login_error = login_error
        self._set_preferences_error = set_preferences_error
        #: 與 `error` 一樣是公開的：測試要能在中途把服務修好，重試那條路徑才驗得了。
        self.add_error = add_error
        self.calls = 0
        self.logins: list[tuple[str, str]] = []
        #: 每一次 `set_preferences` 收到的鍵值，用來斷言「只寫有差異的鍵」。
        self.writes: list[dict[str, Any]] = []
        #: 這一台上被建出來的 category，用來斷言「已經在那裡的不會再建一次」。
        self.created_categories: list[QbittorrentCategory] = []
        #: 收下的每一筆 `torrents/add`。送單測試斷言的就是它——category、tag 與
        #: 交出去的到底是磁力連結還是一份 `.torrent`。
        self.added: list[TorrentAdd] = []
        #: 每一次 `torrents/delete` 收到的 `(hash, delete_files)`。刪除範圍的測試斷言的是它：
        #: 「不刪檔」與「刪檔」送出去的是不同的請求，而磁碟上的事實由 Berth 自己那一半決定。
        self.deleted: list[tuple[str, bool]] = []
        #: 客戶端當下有哪些 torrent。**是公開的可變欄位**：poller 的測試要在兩輪之間
        #: 換掉它（下載完成、torrent 被使用者刪掉），那正是狀態機的輸入。
        self.torrents: tuple[TorrentStatus, ...] = torrents
        self.files_by_hash: dict[str, tuple[TorrentFile, ...]] = dict(files or {})
        self.sync_error = sync_error
        #: 每一次 `torrents/recheck` 與 `start` 收到的 hash。Issue 的按鈕斷言的是它們：
        #: 「重新 recheck」與「重試」送出去的是不同的請求。
        self.rechecked: list[str] = []
        self.started: list[str] = []
        #: `sync()` 被呼叫過幾次。「一輪只問一次」由它守著。
        self.syncs = 0

    async def login(self, username: str, password: str) -> None:
        self.logins.append((username, password))
        if self._login_error is not None:
            raise self._login_error

    async def version(self) -> QbittorrentVersion:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self._version

    async def preferences(self) -> Mapping[str, Any]:
        if self.error is not None:
            raise self.error
        return dict(self._preferences)

    async def set_preferences(self, values: Mapping[str, Any]) -> None:
        if self._set_preferences_error is not None:
            raise self._set_preferences_error
        self.writes.append(dict(values))
        self._preferences.update(values)

    async def categories(self) -> tuple[QbittorrentCategory, ...]:
        if self.error is not None:
            raise self.error
        return tuple(self._categories)

    async def create_category(self, name: str, save_path: str) -> None:
        """有狀態：建完再讀就看得到，重跑精靈才測得出「已經在那裡了」。"""
        if self.error is not None:
            raise self.error
        category = QbittorrentCategory(name=name, save_path=save_path)
        self.created_categories.append(category)
        self._categories.append(category)

    async def add_torrent(self, request: TorrentAdd) -> None:
        """有狀態：收下的留著，測試才驗得出「重複送單沒有再送一次」。"""
        if self.add_error is not None:
            raise self.add_error
        self.added.append(request)

    async def delete_torrent(self, info_hash: str, *, delete_files: bool) -> None:
        """有狀態：那一筆真的從 `torrents` 裡消失，下一輪 poller 看到的就是「它不在了」。

        **不認得的 hash 不是錯誤**，與真的那一台同形（brief §20.2）。`delete_files=True` 時
        替身**不動磁碟**：真 qBittorrent 刪的是它自己記的那份內容，而 Berth 逐檔刪來源是
        `services/deletion.py` 自己做的事（它要數得出刪了幾個、空出多少）。
        """
        if self.error is not None:
            raise self.error
        self.deleted.append((info_hash, delete_files))
        self.torrents = tuple(row for row in self.torrents if row.hash != info_hash)

    async def recheck(self, info_hash: str) -> None:
        """有狀態：那一筆進 `checkingDL`、進度歸零，與真的那一台校驗一開始的樣子相同。

        校驗完之後是什麼樣子由測試換掉 `torrents` 決定——那是 qBittorrent 看了磁碟之後的答案，
        替身不猜。不認得的 hash 不是錯誤（brief §20.2）。
        """
        if self.error is not None:
            raise self.error
        self.rechecked.append(info_hash)
        self._restate(info_hash, lambda row: replace(row, state="checkingDL", progress=0.0))

    async def start(self, info_hash: str) -> None:
        """有狀態：`error` 與停住的那幾種回到 `downloading`（重新開始會清掉錯誤）。"""
        if self.error is not None:
            raise self.error
        self.started.append(info_hash)
        stopped = {"error", "stoppedDL", "pausedDL"}
        self._restate(
            info_hash,
            lambda row: replace(row, state="downloading") if row.state in stopped else row,
        )

    def _restate(self, info_hash: str, change: Callable[[TorrentStatus], TorrentStatus]) -> None:
        self.torrents = tuple(
            change(row) if row.hash == info_hash else row for row in self.torrents
        )

    async def sync(self) -> tuple[TorrentStatus, ...]:
        """替身直接回「現在有哪些」——合併本來就發生在真 client 的 `MaindataCursor` 裡，
        而那一段由契約測試對錄下來的兩輪回應驗（`tests/integration/test_adapter_contracts.py`）。
        """
        self.syncs += 1
        if self.sync_error is not None:
            raise self.sync_error
        return self.torrents

    async def files(self, info_hash: str) -> tuple[TorrentFile, ...]:
        if self.error is not None:
            raise self.error
        return self.files_by_hash.get(info_hash, ())

    async def aclose(self) -> None:
        return None
