"""Jellyfin adapter（plan §8.2、§9.4）。介面與資料型別在這裡，實作在 `client.py` / `fake.py`。

覆蓋的是精靈第 3 步需要的兩條路徑：套件內的全自動初始化序列（plan §9.4），與既有服務的
接入（plan §9.5）。**既有 Jellyfin 的紅線在介面上就看得出來**：沒有刪除媒體庫、沒有改既有
`LibraryOptions`、沒有 `DELETE /Items/*` 的方法，所以那些事在這一層就做不到。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import takewhile
from typing import Protocol

from berth.domain import CollectionType

#: 支援下限（brief §16.4、§20.9）。**12.0 就是原本的 10.12**——Jellyfin 只是把版號前面
#: 永遠不變的 `10` 拿掉了，所以比的是 `12.0` 而不是 `10.12`。10.x 上同一集的兩個版本是兩個
#: 重複的條目，要靠 MergeVersions 插件；12.0 起原生合併，Berth 只支援這一邊（brief §19）。
MIN_VERSION = (12, 0)


@dataclass(frozen=True, slots=True)
class JellyfinPublicInfo:
    """`GET /System/Info/Public` 的回應。免憑證，精靈第 2 步靠它判定來源。"""

    server_name: str
    version: str
    startup_wizard_completed: bool

    @property
    def supported(self) -> bool:
        """這台 Jellyfin 夠新嗎（brief §16.4）。**版號讀不出來時當成不支援**：
        Berth 在它上面做的第一件事就是入庫，而 10.x 的多版本會變成兩個重複的條目。
        """
        return version_supported(self.version)


def version_supported(version: str) -> bool:
    """版號字串 ≥ `MIN_VERSION`。空字串（還沒問過）不在這裡判，呼叫端自己決定。"""
    return _parse(version) >= MIN_VERSION


def unsupported_message(version: str) -> str:
    """版本太舊時的原文（英文）。健康檢查與精靈第 3 步共用同一句，因為那是同一個事實。

    升級注意事項（先完整備份、移除第三方插件、升級後完整掃描、不能降級）**不在這裡**：
    那是 Berth 自己的建議而不是服務說的話，所以它走 i18n，與使用者的語言一致。
    """
    floor = ".".join(str(part) for part in MIN_VERSION)
    return f"Jellyfin {version or 'with no version string'} is older than {floor}"


def _parse(version: str) -> tuple[int, ...]:
    """`12.1.0` → `(12, 1, 0)`。認不得的片段當 0，整串認不得就是 `(0,)`。"""
    parts = []
    for chunk in version.split("."):
        digits = "".join(takewhile(str.isdigit, chunk))
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


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
class JellyfinTask:
    """`GET /ScheduledTasks` 的一項。觸發時要用 `id`，不是 `key`（brief §20.7）。"""

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
class JellyfinSource:
    """`MediaSources[]` 的一項：一個版本的檔案，與它在版本選單上的名字。

    **名字由 Jellyfin 算**（12.0 起是「去掉各版本檔名的共同前綴」剩下的部分，算法與標題的
    標點有關，12.0 與 12.1 還不一樣），所以 Berth 讀它回的值而不是自己重算（brief §7.7、§20.9）。
    """

    path: str
    name: str


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
    #: `MediaSources[]`：這個 item 底下的每一個版本。同一集或同一部電影的第二個版本**不是**
    #: item 自己的 `Path`，只出現在這裡——12.0 起劇集也原生合併（brief §7.7、§20.9）。
    sources: tuple[JellyfinSource, ...] = ()
    #: Episode 的 `SeriesId`：它屬於哪一部作品（2026-09-15 對 12.0.0 實測，每一集都帶）。
    #: 媒體庫的卡片連到作品而不是某一集（票 13）。其餘型別是空字串。
    series_id: str = ""

    @property
    def source_paths(self) -> tuple[str, ...]:
        return tuple(source.path for source in self.sources)

    def version_name(self, path: str) -> str:
        """這一條路徑在 Jellyfin 的版本選單上叫什麼。不是這個 item 的檔案就回空字串。"""
        wanted = path.rstrip("/")
        return next(
            (source.name for source in self.sources if source.path.rstrip("/") == wanted), ""
        )


class JellyfinClient(Protocol):
    """一台 Jellyfin。憑證是可變狀態：初始精靈期間匿名，之後帶 token 或 API key。

    **沒有插件那幾支**（`/Repositories`、`/Packages`、`/Plugins`、`/System/Restart`）：Berth 只支援
    Jellyfin 12，而 12.x 原生合併多版本，不需要裝任何插件（brief §19、§20.9）。介面上沒有它們，
    所以 Berth 也就不會重啟別人的 Jellyfin。
    """

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

    async def create_startup_user(self, name: str, password: str) -> bool:
        """`POST /Startup/User`。回「這一次真的設了密碼嗎」。

        12.0 起第一個使用者已經有密碼時它回 **403**（[PR #17369](https://github.com/jellyfin/jellyfin/pull/17369)），
        而那是「已經設過了」不是失敗：第 3 步成功、之後某一步失敗、Jellyfin 沒重啟時按重試
        就會走到這裡，翻成錯誤的話重試永遠走不完（brief §20.9、票 14b）。密碼對不對由之後的
        登入驗證。
        """
        ...

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

    # --- 排程任務 ---

    async def scheduled_tasks(self) -> tuple[JellyfinTask, ...]:
        """`GET /ScheduledTasks`。Berth 只用內建的 `RefreshLibrary`（反查的後備，brief §20.1）。"""
        ...

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
    "MIN_VERSION",
    "JellyfinApiKey",
    "JellyfinAuth",
    "JellyfinClient",
    "JellyfinItem",
    "JellyfinLibrary",
    "JellyfinPublicInfo",
    "JellyfinSource",
    "JellyfinTask",
    "NewLibrary",
    "TypeOption",
    "unsupported_message",
    "version_supported",
]
