"""測試與前端演練用的 qBittorrent 替身。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from berth.adapters.qbittorrent import QbittorrentCategory, QbittorrentVersion, TorrentAdd

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

    async def aclose(self) -> None:
        return None
