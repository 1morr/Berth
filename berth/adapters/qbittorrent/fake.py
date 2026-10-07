"""測試與前端演練用的 qBittorrent 替身。"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from berth.adapters.http import AuthFailedError
from berth.adapters.qbittorrent import (
    PreferencesRejectedError,
    QbittorrentCategory,
    QbittorrentVersion,
    TorrentAdd,
    TorrentFile,
    TorrentStatus,
)

#: 乾淨實例的偏好值，取自 `tests/fixtures/http/qbittorrent/app-preferences.*.json` 的同名鍵。
#: 全域路徑是 qBittorrent 自己的 `/downloads`，Berth 看不到——Berth 不寫也不看它（M4 票 32），
#: 所以每一條 Route 測試都在這一台上照樣綠。
DEFAULT_PREFERENCES: Mapping[str, Any] = {
    "save_path": "/downloads",
    "temp_path": "/downloads/incomplete",
    "temp_path_enabled": False,
    "auto_tmm_enabled": False,
    "category_changed_tmm_enabled": False,
    "web_ui_username": "admin",
}


@dataclass(frozen=True, slots=True)
class _Probe:
    """一個還在的探針 torrent：它說它是哪個檔、放在哪裡，與校驗之後的樣子。"""

    path: Path
    payload: bytes
    status: TorrentStatus
    #: 校驗不完的那一種（M4 票 46）：看得到也停在一半。
    unfinished: bool = False


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
        visible_roots: tuple[str, ...] | None = None,
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
        self._web_ui_password: str | None = None
        #: 每一次 `set_preferences` 收到的鍵值，用來斷言「只寫有差異的鍵」。
        self.writes: list[dict[str, Any]] = []
        #: 這一台上被建出來的 category，用來斷言「已經在那裡的不會再建一次」。
        self.created_categories: list[QbittorrentCategory] = []
        #: 被刪掉的 category 名字，依送出順序（M4 票 47：只刪 Berth 建的空分類）。
        self.removed_categories: list[str] = []
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
        #: 每一次 `torrents/recheck` 與 `start` 依到達順序記下 `(端點, hash)`。Issue 的按鈕斷言的是
        #: 它：「重新 recheck」與「重試」送出去的是不同的請求，而**兩支的先後**在 5.x 上決定
        #: 停住的 torrent 校驗完會不會又停下來（brief §20.2，M3 票 03）。
        self.restarts: list[tuple[str, str]] = []
        #: `sync()` 被呼叫過幾次。「一輪只問一次」由它守著。
        self.syncs = 0
        #: 這一台看得到哪些路徑（字串前綴），`None` 是全部——與 Berth 共用同一個檔案系統。
        #: 探針校驗時讀的是**真的磁碟**：檔真的在、內容對、路徑又在它看得到的範圍裡才是 100%
        #: （Jellyfin 替身的 `visible_roots` 同一個做法，M4 票 19）。
        self.visible_roots = visible_roots
        #: 加過的每一個探針的檔名；`open_probes` 是還沒移除的。探針不進 `torrents`、`deleted`、
        #: `restarts`：它不是下載，斷言那幾個欄位的測試不該看到它。
        self.probed: list[str] = []
        self.open_probes: dict[str, _Probe] = {}

    async def login(self, username: str, password: str) -> None:
        self.logins.append((username, password))
        if self._login_error is not None:
            raise self._login_error
        # 設過 WebUI 密碼之後只認那一組（M4 票 07 的「舊的失效、新的有效」）。沒設過的替身什麼都收：
        # 真的那一台此時只有容器 log 的臨時密碼，測試不模擬它。
        if self._web_ui_password is not None and (username, password) != (
            self._preferences.get("web_ui_username"),
            self._web_ui_password,
        ):
            raise AuthFailedError("auth/login: Fails.")

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
        written = dict(values)
        password = written.pop("web_ui_password", None)
        username = written.pop("web_ui_username", None)
        self._preferences.update(written)
        # 5.2.0 起照原始碼的順序：帳號先驗先寫、密碼後驗——帳號合規而密碼太短時帳號已經寫進去了
        # （brief §20.2，M4 票 26 實測）。之前的版本什麼都收。
        rules = tuple(int(part) for part in self._version.app.lstrip("v").split(".")[:2]) >= (5, 2)
        if username is not None:
            if rules and len(str(username)) < 3:
                raise PreferencesRejectedError("WebUI username must be at least 3 characters long")
            if rules and ":" in str(username):
                raise PreferencesRejectedError("WebUI username cannot contain a colon")
            self._preferences["web_ui_username"] = username
        if password is not None:
            if rules and len(str(password)) < 6:
                raise PreferencesRejectedError("WebUI password must be at least 6 characters long")
            # 密碼只寫不讀（brief §20.7）：讀回來的偏好裡沒有它，只有登入認它。
            self._web_ui_password = str(password)

    async def categories(self) -> tuple[QbittorrentCategory, ...]:
        if self.error is not None:
            raise self.error
        return tuple(self._categories)

    async def create_category(self, name: str, save_path: str, *, download_path: str) -> None:
        """有狀態：建完再讀就看得到，重跑精靈才測得出「已經在那裡了」。"""
        if self.error is not None:
            raise self.error
        category = QbittorrentCategory(name=name, save_path=save_path, download_path=download_path)
        self.created_categories.append(category)
        self._categories.append(category)

    async def remove_categories(self, names: Sequence[str]) -> None:
        if self.error is not None:
            raise self.error
        self.removed_categories.extend(names)
        self._categories = [row for row in self._categories if row.name not in names]

    async def add_probe(
        self, name: str, payload: bytes, *, save_path: str, unfinished: bool = False
    ) -> str:
        if self.error is not None:
            raise self.error
        info_hash = hashlib.sha1(f"{save_path}/{name}".encode(), usedforsecurity=False).hexdigest()
        self.probed.append(name)
        self.open_probes[info_hash] = _Probe(
            path=Path(save_path) / name,
            payload=payload,
            unfinished=unfinished,
            status=_probe_status(info_hash, name, save_path, state="stoppedDL", progress=0.0),
        )
        return info_hash

    async def torrent(self, info_hash: str) -> TorrentStatus | None:
        if self.error is not None:
            raise self.error
        if info_hash in self.open_probes:
            return self.open_probes[info_hash].status
        return next((row for row in self.torrents if row.hash == info_hash), None)

    def _sees(self, probe: _Probe) -> bool:
        if self.visible_roots is not None and not str(probe.path).startswith(self.visible_roots):
            return False
        try:
            return probe.path.read_bytes() == probe.payload
        except OSError:
            return False

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
        if self.open_probes.pop(info_hash, None) is not None:
            return
        self.deleted.append((info_hash, delete_files))
        self.torrents = tuple(row for row in self.torrents if row.hash != info_hash)

    async def recheck(self, info_hash: str) -> None:
        """有狀態：那一筆進 `checkingDL`、進度歸零，與真的那一台校驗一開始的樣子相同。

        校驗完之後是什麼樣子由測試換掉 `torrents` 決定——那是 qBittorrent 看了磁碟之後的答案，
        替身不猜。不認得的 hash 不是錯誤（brief §20.2）。
        """
        if self.error is not None:
            raise self.error
        probe = self.open_probes.get(info_hash)
        if probe is not None:
            # 校驗一下子就完。看得到：單片的是做種完成的樣子，校驗不完的兩片停在一半（M4 票 46）；
            # 看不到停在 0%（brief §20.2 實測）。
            seen = self._sees(probe)
            finished = seen and not probe.unfinished
            self.open_probes[info_hash] = replace(
                probe,
                status=replace(
                    probe.status,
                    state="stoppedUP" if finished else "stoppedDL",
                    progress=(0.5 if probe.unfinished else 1.0) if seen else 0.0,
                ),
            )
            return
        self.restarts.append(("recheck", info_hash))
        self._restate(info_hash, lambda row: replace(row, state="checkingDL", progress=0.0))

    async def start(self, info_hash: str) -> None:
        """有狀態：`error` 與停住的那幾種回到 `downloading`（重新開始會清掉錯誤）。"""
        if self.error is not None:
            raise self.error
        self.restarts.append(("start", info_hash))
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


def _probe_status(
    info_hash: str, name: str, save_path: str, *, state: str, progress: float
) -> TorrentStatus:
    return TorrentStatus(
        hash=info_hash,
        name=name,
        state=state,
        category="",
        tags=(),
        progress=progress,
        completion_on=0,
        last_activity=0,
        added_on=0,
        save_path=save_path,
        content_path=f"{save_path}/{name}",
        total_size=0,
    )
