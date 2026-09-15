"""Jellyfin adapter（plan §8.2、§9.4）。介面與資料型別在這裡，實作在 `client.py` / `fake.py`。

覆蓋的是精靈第 3 步需要的兩條路徑：套件內的全自動初始化序列（plan §9.4），與既有服務的
接入（plan §9.5）。**既有 Jellyfin 的紅線在介面上就看得出來**：沒有刪除媒體庫、沒有改既有
`LibraryOptions`、沒有 `DELETE /Items/*` 的方法，所以那些事在這一層就做不到。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from berth.domain import CollectionType


@dataclass(frozen=True, slots=True)
class JellyfinPublicInfo:
    """`GET /System/Info/Public` 的回應。免憑證，精靈第 2 步靠它判定來源。"""

    server_name: str
    version: str
    startup_wizard_completed: bool


@dataclass(frozen=True, slots=True)
class JellyfinAuth:
    """`POST /Users/AuthenticateByName` 的回應（brief §20.7）。"""

    token: str
    user_id: str
    #: `User.Name`。Jellyfin 才知道正規的大小寫，顯示名一律照它回的（票 07）。
    name: str
    server_id: str
    #: `User.Policy.IsAdministrator`。票 07 的角色判定用同一個欄位（plan §11.1 T0.5）。
    is_administrator: bool


@dataclass(frozen=True, slots=True)
class TypeOption:
    """`LibraryOptions.TypeOptions[]` 的一項。

    兩種用途：`available_type_options()` 回報伺服器**有哪些** fetcher，`NewLibrary` 帶著
    要**寫進去**的那幾個。省略 `ImageFetchers` 會被存成空陣列（該類型從此不抓圖），
    所以兩個欄位都得給值（2026-09-07 對 10.11.11 實測，brief §20.7）。
    """

    type: str
    metadata_fetchers: tuple[str, ...]
    image_fetchers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NewLibrary:
    """`POST /Library/VirtualFolders` 的一次建立（plan §9.4 第 4 步）。"""

    name: str
    collection_type: CollectionType
    path: str
    type_options: tuple[TypeOption, ...]
    preferred_metadata_language: str
    metadata_country_code: str


@dataclass(frozen=True, slots=True)
class JellyfinLibrary:
    """`GET /Library/VirtualFolders` 的一項。"""

    name: str
    item_id: str
    collection_type: str
    #: 這個媒體庫的所有路徑。Jellyfin 支援一庫多路徑，Berth 就是靠它接入既有媒體庫。
    locations: tuple[str, ...]
    type_options: tuple[TypeOption, ...]


@dataclass(frozen=True, slots=True)
class JellyfinApiKey:
    """`GET /Auth/Keys` 的一項。"""

    app_name: str
    access_token: str


@dataclass(frozen=True, slots=True)
class JellyfinRepository:
    """`GET /Repositories` 的一項（`{Name, Url, Enabled}`）。"""

    name: str
    url: str
    enabled: bool


@dataclass(frozen=True, slots=True)
class JellyfinPlugin:
    """`GET /Plugins` 的一項。`id` 是去掉連字號的 GUID。"""

    id: str
    name: str
    version: str


@dataclass(frozen=True, slots=True)
class JellyfinTask:
    """`GET /ScheduledTasks` 的一項。

    觸發時要用 `id`，不是 `key`（brief §20.7）。MergeVersions 的 key 是
    `MergeMoviesTask` 與 `MergeEpisodesTask`。
    """

    id: str
    key: str
    name: str


#: `GET /Items` 的 `includeItemTypes`：Jellyfin 自己的型別名。入庫之後的反查只問這三種。
ITEM_SERIES = "Series"
ITEM_EPISODE = "Episode"
ITEM_MOVIE = "Movie"

#: 內建「重新掃描媒體庫」排程任務的 `Key`（`GET /ScheduledTasks`，2026-09-15 對 12.0.0 實測）。
#: 路徑通知對從沒掃到過內容的媒體庫無效時，反查靠它（brief §20.1）。
LIBRARY_SCAN_TASK_KEY = "RefreshLibrary"


@dataclass(frozen=True, slots=True)
class JellyfinItem:
    """`GET /Items` 的一項（入庫之後的反查，brief §20.1、plan §8.2）。"""

    id: str
    #: Jellyfin 自己的型別名：`Series`、`Episode`、`Movie`。
    type: str
    name: str
    #: Jellyfin 看到的路徑。Series 是作品資料夾，Episode 與 Movie 是檔案。
    path: str
    #: `ProviderIds.Tmdb`，沒有就是空字串。
    tmdb_id: str
    #: `MediaSources[].Path`：這個 item 底下每一個版本的檔案。電影的多版本與 MergeVersions
    #: 合併過的劇集，第二個版本的檔案**不是** item 自己的 `Path`，只出現在這裡（brief §7.7）。
    source_paths: tuple[str, ...]
    #: Episode 的 `SeriesId`：它屬於哪一部作品（2026-09-15 對 12.0.0 實測，每一集都帶）。
    #: 媒體庫的卡片連到作品而不是某一集（票 13）。其餘型別是空字串。
    series_id: str = ""


class JellyfinClient(Protocol):
    """一台 Jellyfin。憑證是可變狀態：初始精靈期間匿名，之後帶 token 或 API key。"""

    @property
    def base_url(self) -> str: ...

    def use_token(self, token: str) -> None:
        """之後的請求都帶這個 token。登入 token 與 API key 同一個標頭形狀。"""
        ...

    async def public_info(self) -> JellyfinPublicInfo: ...

    # --- 初始精靈（plan §9.4 第 2、3、5、6 步）---

    async def start_configuration(
        self, *, ui_culture: str, metadata_country_code: str, preferred_metadata_language: str
    ) -> None: ...

    async def ensure_default_user(self) -> str:
        """`GET /Startup/User`，回預設使用者的名字。

        **不是多餘的一次讀取**：它會跑 `UserManager.InitializeAsync()` 建立預設使用者，
        少了它接下來的 POST 會回 500（brief §20.7）。
        """
        ...

    async def create_startup_user(self, name: str, password: str) -> None: ...

    async def set_remote_access(self, *, enabled: bool) -> None: ...

    async def complete_startup(self) -> None: ...

    # --- 憑證 ---

    async def authenticate(self, username: str, password: str) -> JellyfinAuth: ...

    async def api_keys(self) -> tuple[JellyfinApiKey, ...]: ...

    async def create_api_key(self, app: str) -> None:
        """`POST /Auth/Keys?app=` 回 204 而且**不回傳 key**，也不檢查重複。

        呼叫端要自己先看 `api_keys()`，否則同一個 `AppName` 會長出第二把
        （2026-09-07 對 10.11.11 實測，brief §20.7）。
        """
        ...

    # --- 媒體庫 ---

    async def libraries(self) -> tuple[JellyfinLibrary, ...]: ...

    async def available_type_options(
        self, collection_type: CollectionType
    ) -> tuple[TypeOption, ...]:
        """`GET /Libraries/AvailableOptions`：這台伺服器裝了哪些 fetcher。"""
        ...

    async def create_library(self, library: NewLibrary) -> None:
        """`POST /Library/VirtualFolders`。**同名不會被拒**：重按會長出 `Movies2`
        指向同一個路徑，所以呼叫端要先看 `libraries()`（實測，brief §20.7）。
        """
        ...

    async def add_library_path(self, library_name: str, path: str) -> None:
        """`POST /Library/VirtualFolders/Paths?refreshLibrary=false`（plan §9.5）。

        既有媒體庫**加**一條路徑，舊路徑原地不動。目錄不存在會回 404，同一條路徑
        送兩次會出現重複的 location，兩者都由呼叫端先擋（實測，brief §20.7）。
        """
        ...

    async def validate_path(self, path: str, *, is_file: bool = True) -> bool:
        """`POST /Environment/ValidatePath`：這台 Jellyfin 看得到這條路徑嗎（plan §9.5）。

        跨主機驗證靠它：Berth 在 Route 目標寫一個探測檔，再問 Jellyfin 看不看得到同一條
        路徑；Jellyfin 在別台機器或少了掛載就會立刻現形（brief §16.4）。看得到回 204、
        看不到回 404，所以「看不到」是答案而不是失敗
        （`EnvironmentController.ValidatePath`，2026-09-08 查核原始碼）。
        """
        ...

    # --- 插件與排程任務（plan §9.4 第 8、9 步）---

    async def repositories(self) -> tuple[JellyfinRepository, ...]: ...

    async def set_repositories(self, repositories: tuple[JellyfinRepository, ...]) -> None:
        """`POST /Repositories` 是整份覆寫，所以呼叫端要先讀再合併。"""
        ...

    async def package_versions(self, name: str) -> tuple[str, ...]:
        """`GET /Packages` 裡某個套件的可用版本。加完 repository 後要輪詢它出現。"""
        ...

    async def install_package(self, name: str, *, assembly_guid: str) -> None: ...

    async def plugins(self) -> tuple[JellyfinPlugin, ...]: ...

    async def restart(self) -> None:
        """`POST /System/Restart`。連線會被切斷，重啟完成要靠輪詢管理員端點確認。"""
        ...

    async def scheduled_tasks(self) -> tuple[JellyfinTask, ...]: ...

    async def run_task(self, task_id: str) -> None:
        """`POST /ScheduledTasks/Running/{id}`。用 `Id` 不是 `Key`（brief §20.7）。"""
        ...

    # --- 入庫之後（plan §8.2、票 12）---

    async def notify_paths(self, paths: Sequence[str]) -> None:
        """`POST /Library/Media/Updated`，每條路徑 `UpdateType=Created`（brief §20.1）。

        路徑級的通知，不是全庫掃描：Jellyfin 收下之後自己排程去掃，所以回來了不代表掃完了。
        """
        ...

    async def items(self, library_id: str, item_types: Sequence[str]) -> tuple[JellyfinItem, ...]:
        """一個媒體庫底下某幾種型別的 item（`parentId=<library>&recursive=true`）。

        **只以媒體庫為 parent**：10.11 在第一次掃描後對已被 provider 認出來的 Series，
        `parentId=<seriesId>` 與 `/Shows/{id}/Episodes` 都回 0（brief §20.1、plan §8.2）。
        `GET /Items` 沒有路徑篩選，所以對路徑是呼叫端的事。
        """
        ...

    async def aclose(self) -> None: ...


__all__ = [
    "ITEM_EPISODE",
    "ITEM_MOVIE",
    "ITEM_SERIES",
    "LIBRARY_SCAN_TASK_KEY",
    "JellyfinApiKey",
    "JellyfinAuth",
    "JellyfinClient",
    "JellyfinItem",
    "JellyfinLibrary",
    "JellyfinPlugin",
    "JellyfinPublicInfo",
    "JellyfinRepository",
    "JellyfinTask",
    "NewLibrary",
    "TypeOption",
]
