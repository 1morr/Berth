"""Jellyfin adapter（plan §8.2、§9.4）。介面與資料型別在這裡，實作在 `client.py` / `fake.py`。

覆蓋的是精靈第 3 步需要的兩條路徑：套件內的全自動初始化序列（plan §9.4），與既有服務的
接入（plan §9.5）。**既有 Jellyfin 的紅線在介面上就看得出來**：沒有刪除媒體庫、沒有改既有
`LibraryOptions`、沒有 `DELETE /Items/*` 的方法，所以那些事在這一層就做不到。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from itertools import takewhile
from typing import Protocol

from berth.domain import CollectionType, SortOrder

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
#: 季（`/Shows/{id}/Seasons` 回的那一種）。只有替身會把它當成一個 item 存（M1.5 票 08）。
ITEM_SEASON = "Season"

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
class JellyfinUserData:
    """`UserData`（`UserItemDataDto`）裡 Berth 讀的那幾格：一位使用者對一個 item 的觀看紀錄
    （M1.5 票 05）。

    **欄位不是每筆都有**（研究 library-browsing.md §1.2）：`PlayedPercentage` 只在看到一半的影片或
    資料夾（Series / Season）出現，`UnplayedItemCount` 只在資料夾。缺的百分比是 0、缺的集數是
    `None`。
    """

    played: bool
    #: 影片：看到幾 %（沒在看是 0）。資料夾：底下看過的集佔幾 %。
    played_percentage: float
    #: 資料夾底下還有幾集沒看；**只有資料夾有這一格**，影片與集是 `None`。
    unplayed_item_count: int | None


@dataclass(frozen=True, slots=True)
class ParentImage:
    """上層 item 的一張圖：`ParentThumbItemId` + `ParentThumbImageTag` 這種成對的欄位。

    集沒有自己的橫圖時，jellyfin-web 借季或劇的（研究 library-browsing.md §7）。**是哪一層由
    Jellyfin 決定**（v12.0 `DtoService.AddInheritedImages`）：Thumb 先找季、劇自己有就換成劇的；
    Backdrop 取往上找到的第一個。
    """

    item_id: str
    tag: str


@dataclass(frozen=True, slots=True)
class JellyfinItem:
    """`GET /Items` 的一項（入庫之後的反查，brief §20.1、plan §8.2），也是繼續觀看與下一集的一項
    （`/UserItems/Resume`、`/Shows/NextUp` 回同一種 DTO，M1.5 票 07）。"""

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
    #: Episode 的 `SeasonId`：它屬於哪一季（Media 詳情的選季選集，M1.5 票 08）。其餘型別是空字串。
    season_id: str = ""
    #: `ProductionYear`。媒體庫牆上那一格的年份（M1.5 票 03）；Jellyfin 不知道時是 `None`。
    year: int | None = None
    #: `ImageTags.Primary`：代理圖片的網址要帶它，Jellyfin 換圖時網址才會變（M1.5 票 04、研究 §6）。
    #: 沒有 Primary 圖，或查詢關掉了圖（`enableImages=false`）時是空字串。
    primary_tag: str = ""
    #: 帶著 `userId` 查、而且沒有關掉 `enableUserData` 時才有（M1.5 票 05）。
    user_data: JellyfinUserData | None = None
    # --- 集的身分與橫卡的圖（M1.5 票 07）---
    #: `SeriesName`：集屬於哪一部劇，Jellyfin 的名稱。其餘型別是空字串。
    series_name: str = ""
    #: `ParentIndexNumber` / `IndexNumber` / `IndexNumberEnd`：季號、集號、多集檔的最後一集
    #: （名字照帳本與計劃的 `episode_start` / `episode_end`）。Jellyfin 認不出編號時沒有這幾格
    #: （`None`）；S00 是 0。
    season: int | None = None
    episode_start: int | None = None
    episode_end: int | None = None
    #: `ImageTags.Thumb` 與 `BackdropImageTags[0]`：這個 item 自己的橫圖。查詢沒開這兩種圖
    #: （`enableImageTypes`）時一律是空字串（v12.0 `DtoService` 照 `GetImageLimit` 收錄）。
    thumb_tag: str = ""
    backdrop_tag: str = ""
    #: `SeriesThumbImageTag`：集所屬的劇的 Thumb（item id 是 `series_id`）。**12.1.0 錄的 NextUp
    #: 沒有回它**，劇的 Thumb 從 `parent_thumb` 來；jellyfin-web 兩格都看，Berth 也都讀。
    series_thumb_tag: str = ""
    #: `ParentThumbItemId` + `ParentThumbImageTag`，
    #: `ParentBackdropItemId` + `ParentBackdropImageTags[0]`。
    parent_thumb: ParentImage | None = None
    parent_backdrop: ParentImage | None = None

    @property
    def source_paths(self) -> tuple[str, ...]:
        return tuple(source.path for source in self.sources)

    def version_name(self, path: str) -> str:
        """這一條路徑在 Jellyfin 的版本選單上叫什麼。不是這個 item 的檔案就回空字串。"""
        wanted = path.rstrip("/")
        return next(
            (source.name for source in self.sources if source.path.rstrip("/") == wanted), ""
        )


@dataclass(frozen=True, slots=True)
class JellyfinSeason:
    """`GET /Shows/{id}/Seasons` 的一季（M1.5 票 08）。"""

    id: str
    #: Jellyfin 的季名，跟伺服器的 metadata 語言（`第 1 季`、`Specials`、篇章名）。
    #: 不是 Berth 的文案，畫面原樣顯示。
    name: str
    #: `IndexNumber`：季號，Specials 是 0；Jellyfin 認不出來時是 `None`。
    number: int | None
    user_data: JellyfinUserData | None


@dataclass(frozen=True, slots=True)
class JellyfinView:
    """`GET /UserViews?userId=` 的一項：這位使用者在 Jellyfin 首頁看得到的一個媒體庫。

    **這一份是權限的權威清單**（研究 library-browsing.md §2、§9）：API key 代讀時，帶 `parentId`
    的查詢 Jellyfin 不套媒體庫權限，所以 Berth 只拿這裡有的 id 去當 `parentId`。`id` 與
    `/Library/VirtualFolders` 的 `ItemId` 同一種格式（12.1.0 實測）。
    """

    id: str
    name: str
    #: `CollectionType`：`tvshows`、`movies`、`music`……沒有類型的混合媒體庫是空字串。
    collection_type: str


@dataclass(frozen=True, slots=True)
class JellyfinPolicy:
    """`GET /Users/{id}` 的 `Policy` 裡 Berth 讀的那一格。

    停用的帳號 API key 照樣代讀得到資料（12.1.0 實測，brief §20.8），「停用」只讀得出這裡。
    """

    is_disabled: bool


@dataclass(frozen=True, slots=True)
class JellyfinPage:
    """一頁 `/Items`。"""

    items: tuple[JellyfinItem, ...]
    #: `TotalRecordCount`：整個查詢的筆數，不是這一頁的。
    total: int


@dataclass(frozen=True, slots=True)
class JellyfinFilters:
    """`GET /Items/Filters` 裡 Berth 讀的兩份清單：一個媒體庫的作品有哪些類型與年份
    （jellyfin-web 篩選面板那一支，研究 library-browsing.md §3.2）。"""

    genres: tuple[str, ...]
    years: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class JellyfinImage:
    """`GET /Items/{id}/Images/{type}` 的一張圖，已由 Jellyfin 縮好。"""

    content: bytes
    #: Jellyfin 回的 `Content-Type`，一定是 `image/*`。
    content_type: str


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

    # --- 替某一位使用者瀏覽（M1.5 票 03，研究 library-browsing.md §2、§9）---
    #
    # **`user_id` 在這幾支是必要參數**（plan §11.2b）：API key 在 Jellyfin 眼中是管理員，帶誰的 id
    # 就是誰；漏帶的查詢不是報錯，而是回整台伺服器（`/Items`）或略過權限（`/Shows/{id}/Seasons`），
    # 所以用型別擋。**`library_id` 必須先對 `user_views` 驗過**：帶 `parentId` 時 Jellyfin 不套
    # 媒體庫權限。這條由 `services/jellyfin_access.py` 守著，adapter 只忠實翻譯協定。

    async def user_views(self, user_id: str) -> tuple[JellyfinView, ...]:
        """`GET /UserViews?userId=`：這位使用者看得到的媒體庫，照他在 Jellyfin 排的順序。"""
        ...

    async def user_policy(self, user_id: str) -> JellyfinPolicy:
        """`GET /Users/{id}`。"""
        ...

    async def library_page(
        self,
        *,
        user_id: str,
        library_id: str,
        item_type: str,
        start: int,
        limit: int,
        sort_by: Sequence[str],
        sort_order: SortOrder,
        genres: Sequence[str],
        years: Sequence[int],
        search: str = "",
    ) -> JellyfinPage:
        """一個媒體庫的一頁作品。參數照 jellyfin-web 的劇集庫與電影庫（研究 §7）。

        `sort_by` 是 `sortBy` 的每一個鍵，`sort_order` 套在每一個鍵上（jellyfin-web 只送一個）。
        `genres` 之間、`years` 之間是「或」，兩者之間是「且」；空的就是不篩
        （研究 §3.1，12.1.0 實測）。`search` 是 `searchTerm`：名字裡的一段、不分大小寫，
        照樣照 `sortBy` 排（M2 票 14，12.1.0 實測）；空的就是不搜。
        """
        ...

    async def library_filters(
        self, *, user_id: str, library_id: str, item_type: str
    ) -> JellyfinFilters:
        """`GET /Items/Filters?userId=&parentId=&includeItemTypes=`：這個媒體庫裡這一種作品的
        類型與年份。

        **不帶 `parentId` 四份清單全空**（研究 §2，12.1.0 實測），而帶了就不套媒體庫權限——同一條
        「`library_id` 必須先驗過」的規矩。
        """
        ...

    async def library_index(
        self, *, user_id: str, library_id: str, item_type: str
    ) -> tuple[JellyfinItem, ...]:
        """一個媒體庫的**每一部**作品，只帶 id、名稱、年份、TMDB id 與 Primary 圖的 tag——不分頁，
        不要觀看紀錄。

        Berth 端比對「哪一部是 Berth 經手的」用（票 03）：`/Items` 沒有 provider id 的過濾參數
        （研究 §10），只能整份拿回來自己比。
        """
        ...

    async def mark_played(self, *, user_id: str, item_id: str, played: bool) -> JellyfinUserData:
        """`POST`（已看）/ `DELETE`（未看）`/UserPlayedItems/{id}?userId=`，回寫入之後的紀錄。

        **可見性由 Jellyfin 自己查**：這位使用者看不到（或沒有）這個 item 時回 404 而且沒有寫入
        （研究 §5 的原始碼；12.1.0 打完立刻讀回，研究 §2 的表），翻成 `NotFoundError`。
        對 Series / Season 會遞迴到底下每一集；標為未看清掉 `PlayCount` 與 `LastPlayedDate`，
        復原不了。
        """
        ...

    async def resume(
        self, *, user_id: str, library_id: str, limit: int
    ) -> tuple[JellyfinItem, ...]:
        """`GET /UserItems/Resume`：看到一半的集與電影，最近看的在前。帶 `mediaTypes=Video`
        （研究 §1.2：不帶會混進 Season 與 Series）。

        一律帶 `parentId`：帶了 Jellyfin 就不套這個人的媒體庫權限（研究 §2），`library_id` 必須
        先驗過允許清單才會傳進來。
        """
        ...

    async def next_up(
        self, *, user_id: str, library_id: str, limit: int, cutoff: datetime
    ) -> tuple[JellyfinItem, ...]:
        """`GET /Shows/NextUp`：每部看過的劇的下一集，劇最後看過的日期新的在前。只算 `cutoff`
        之後看過的劇；看到一半的集不算（`enableResumable=false`，它們在 `resume`）。
        `library_id` 同 `resume`。
        """
        ...

    # --- Media 詳情的觀看區（M1.5 票 08，研究 §2、§4.1、§10）---

    async def tmdb_index(self, *, user_id: str, item_type: str) -> tuple[JellyfinItem, ...]:
        """這位使用者看得到、有 TMDB id 的每一部作品，只帶 id、名稱與 TMDB id。

        **不帶 `parentId`**：Jellyfin 才照這個人的 `UserViews` 限縮（研究 §10）。`/Items` 沒有
        provider id 的過濾參數，由 TMDB id 比對是呼叫端的事。
        """
        ...

    async def item(self, *, user_id: str, item_id: str) -> JellyfinItem:
        """`GET /Items/{id}?userId=`，帶這個人的觀看紀錄。**可見性由 Jellyfin 查**：看不到（或沒有）
        時 404，翻成 `NotFoundError`。"""
        ...

    async def seasons(self, *, user_id: str, series_id: str) -> tuple[JellyfinSeason, ...]:
        """`GET /Shows/{id}/Seasons?userId=`。看不到這部劇時 404（`NotFoundError`）；**漏帶 `userId`
        會回 200 並略過權限**（研究 §2），所以它是必要參數。"""
        ...

    async def episodes(
        self, *, user_id: str, series_id: str, season_id: str
    ) -> tuple[JellyfinItem, ...]:
        """`GET /Shows/{id}/Episodes?userId=&seasonId=`：那一季的集。看不到這部劇或這一季時 404
        （`NotFoundError`）。"""
        ...

    async def series_next_up(self, *, user_id: str, series_id: str) -> JellyfinItem | None:
        """`GET /Shows/NextUp?userId=&seriesId=`：這部劇接下來看哪一集，全部看完是 `None`。

        參數照 jellyfin-web 劇集頁，其餘吃伺服器預設：看到一半的那一集照樣回（`enableResumable`
        預設 `true`），一集都沒看過回 S01E01，截止日不套用（v12.0 原始碼、12.1.0 錄製）。
        **帶 `seriesId` 就不套權限**（研究 §2）：呼叫端要先確認這位使用者看得到這部劇。
        """
        ...

    # --- 圖片（M1.5 票 04）---

    async def image(
        self,
        item_id: str,
        image_type: str,
        *,
        tag: str,
        fill_width: int,
        fill_height: int,
        quality: int,
    ) -> JellyfinImage:
        """`GET /Items/{id}/Images/{type}`：縮放由 Jellyfin 做。沒有這張圖是 `NotFoundError`。

        **不需要憑證**（研究 §6，三版都沒有 `[Authorize]`），所以呼叫端給一個不帶 token 的 client。
        `tag` 只是快取鍵，錯的也回圖；帶著它 Jellyfin 才回一年的 `immutable`。
        """
        ...

    async def aclose(self) -> None: ...


async def scan_libraries(client: JellyfinClient) -> bool:
    """跑 Jellyfin 的「重新掃描媒體庫」排程任務。回傳「真的請它掃了沒」（沒有那個任務時 False）。

    **不用 `POST /Library/Refresh`**：它在請求裡等整次掃描做完（`LibraryController.RefreshLibrary`，
    2026-09-15 查核 master），大的媒體庫會讓呼叫端卡上好幾分鐘；排程任務收下就回。
    **也不用 `POST /Items/{id}/Refresh`**：master 上它沒有 `Recursive`，只刷新那一個 item 的中繼
    資料，不會去找新的子資料夾（同日查核，對 12.0.0 實測兩分鐘後仍是 0 個 item）。

    任務 id 每一台不同，以 `Key` 找（brief §20.1）——那是協定的事，所以住在 adapter（同
    qBittorrent 的 `ensure_category`）。兩個呼叫端：`jellyfin_resolver` 沒找到兩次之後、
    Issue 的「重新掃描媒體庫」那一顆（M2 票 09）。
    """
    tasks = await client.scheduled_tasks()
    task = next((task for task in tasks if task.key == LIBRARY_SCAN_TASK_KEY), None)
    if task is None:
        return False
    await client.run_task(task.id)
    return True


__all__ = [
    "ITEM_EPISODE",
    "ITEM_MOVIE",
    "ITEM_SEASON",
    "ITEM_SERIES",
    "LIBRARY_SCAN_TASK_KEY",
    "MIN_VERSION",
    "JellyfinApiKey",
    "JellyfinAuth",
    "JellyfinClient",
    "JellyfinFilters",
    "JellyfinImage",
    "JellyfinItem",
    "JellyfinLibrary",
    "JellyfinPage",
    "JellyfinPolicy",
    "JellyfinPublicInfo",
    "JellyfinSeason",
    "JellyfinSource",
    "JellyfinTask",
    "JellyfinUserData",
    "JellyfinView",
    "NewLibrary",
    "ParentImage",
    "TypeOption",
    "scan_libraries",
    "unsupported_message",
    "version_supported",
]
