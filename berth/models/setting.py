"""設定：一列一個分組，值是對應的 pydantic model（plan §2.1）。

分組模型是設定的唯一結構來源；DB 只存它們序列化後的 JSON，未設定時回模型的預設值。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from berth.domain import DetectionReason, HealthStatus, ServiceKind, ServiceOrigin, StepStatus
from berth.models.base import Base
from berth.models.types import JsonText, UtcDateTime, utcnow


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value_json: Mapped[dict[str, Any]] = mapped_column(JsonText)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, onupdate=utcnow)


class SettingsGroup(BaseModel):
    """一個設定分組。`KEY` 是它在 `settings` 表的鍵。"""

    #: 舊版本寫下的欄位被移除後仍要讀得回來，所以多餘的鍵忽略而不是報錯。
    model_config = ConfigDict(extra="ignore")

    KEY: ClassVar[str]


#: 套件內三個媒體庫的 slug（plan §9.4 第 4 步）。也是 `metadata_fetchers` 與媒體庫路徑的鍵。
MOVIES_SLUG = "movies"
TV_SLUG = "tv"
ANIME_SLUG = "anime"


class JellyfinSettings(SettingsGroup):
    KEY = "services.jellyfin"

    base_url: str = ""
    api_key: str = ""

    #: 建立媒體庫時寫進 `LibraryOptions.TypeOptions[].MetadataFetchers` 的名字（plan §9.4）。
    #: 鍵是媒體庫 slug，順序即優先序；名字是 Jellyfin 自己報的 fetcher 名
    #: （`GET /Libraries/AvailableOptions`）。**anime 單獨一列就是那個切換點**：brief §10 的
    #: TVDB【研究】定案時改這裡的值，不改程式。`ImageFetchers` 不在這裡——它跟著伺服器
    #: 自己的可用清單走，寫死會讓沒對到 TMDB 的作品連縮圖都沒有（實測，brief §20.7）。
    metadata_fetchers: dict[str, list[str]] = {
        MOVIES_SLUG: ["TheMovieDb"],
        TV_SLUG: ["TheMovieDb"],
        ANIME_SLUG: ["TheMovieDb"],
    }

    #: MergeVersions 兩個排程任務的 `Id`（**不是 `Key`**，觸發時要用 Id，brief §20.7）。
    #: 入庫後由 pipeline 呼叫 `POST /ScheduledTasks/Running/{Id}`（M1）。
    merge_movies_task_id: str = ""
    merge_episodes_task_id: str = ""


class QbittorrentSettings(SettingsGroup):
    KEY = "services.qbittorrent"

    base_url: str = ""
    username: str = ""
    password: str = ""


class IndexerSettings(SettingsGroup):
    KEY = "services.indexer"

    #: Prowlarr 或任意 Torznab 端點（Jackett 之類，plan §9.3 第 5 步）。
    kind: Literal["prowlarr", "torznab"] = "prowlarr"
    base_url: str = ""
    api_key: str = ""


class TmdbSettings(SettingsGroup):
    KEY = "services.tmdb"

    api_key: str = ""


class PathSettings(SettingsGroup):
    KEY = "paths"

    #: qBittorrent 的全域 temp path 與 category save path 的根（brief §4.1）。
    incomplete_root: str = "/data/torrent/incomplete"
    complete_root: str = "/data/torrent/complete"
    #: 套件內 Jellyfin 三個媒體庫的父目錄（plan §9.1）。既有 Jellyfin 的「加入 Berth 路徑」
    #: 也落在它底下。Berth 與 Jellyfin 把同一個宿主目錄掛在同一個容器路徑，所以這一個字串
    #: 對兩邊都成立（brief §16.4 的硬規則）。
    library_root: str = "/data/library"


class SetupAdmin(BaseModel):
    """精靈第 1 步建立的管理員（plan §9.3）。

    密碼是明文的：第 3 步要拿它去建 Jellyfin 管理員，第 4 步要拿它設 qBittorrent 的 WebUI 密碼，
    雜湊做不到這兩件事。Berth 自己從不驗證這組密碼——登入一律走 Jellyfin（brief §11）。
    秘密只靠檔案權限保護，與其他 `settings.services.*` 的 key 與密碼一致（brief §16.2）。
    """

    model_config = ConfigDict(extra="ignore")

    username: str = ""
    password: str = ""
    #: 「同一組帳密也套用到 qBittorrent 與 Prowlarr 介面」，預設勾。
    apply_to_services: bool = True


class ServiceProbe(BaseModel):
    """精靈第 2 步對單一服務的判定結果。"""

    model_config = ConfigDict(extra="ignore")

    origin: ServiceOrigin
    reason: DetectionReason
    #: 探測到的實測值：版本號或索引站數量。沒有就是空字串。
    detail: str = ""
    base_url: str = ""
    checked_at: datetime
    #: 這個判定來自使用者填的連線表單，不是探測 compose 主機名的結果。
    #: 重探時要跳過它——它根本不在那個主機名上。
    configured: bool = False


class SetupStep(BaseModel):
    """精靈裡一個步驟的最後結果（plan §9.4）。

    `key` 是字串而不是列舉：這個型別給每個泊位共用，而各泊位的步驟集合各不相同；
    存下來的舊值也不該因為某一步被改名就讓整份設定讀不回來。
    """

    model_config = ConfigDict(extra="ignore")

    key: str
    status: StepStatus
    #: 實測值：版本號、建了哪幾個媒體庫、任務 id。UI 直接顯示，不翻譯。
    detail: str = ""
    #: 失敗時服務回的原文（英文）。UI 貼在手動步驟旁邊。
    error: str = ""


class SetupLibrary(BaseModel):
    """Jellyfin 回報的一個媒體庫（plan §8.2）。第 7 步從這裡建 Route。"""

    model_config = ConfigDict(extra="ignore")

    name: str
    #: 這個 virtual folder 的 `ItemId`。Route 記它而不是只記名字——使用者在 Jellyfin 那邊
    #: 改名之後，靠名字認的 Route 會變成另一個 Route。舊資料沒有這個欄位，所以是選填。
    item_id: str = ""
    collection_type: str = ""
    locations: list[str] = []
    #: 攤平後的 `LibraryOptions.TypeOptions[].MetadataFetchers`，用來偵測 TVDB 插件並警告。
    metadata_fetchers: list[str] = []


class SetupJellyfin(BaseModel):
    """精靈第 3 步的狀態（plan §9.4、§9.5）。兩條路徑共用同一份形狀。"""

    model_config = ConfigDict(extra="ignore")

    steps: list[SetupStep] = []
    libraries: list[SetupLibrary] = []
    #: MergeVersions 是否已安裝。既有路徑的按鈕與套件內的第 8 步看同一個欄位。
    merge_versions_installed: bool = False


class SetupQbittorrent(BaseModel):
    """精靈第 4 步的狀態（plan §9.3 第 4 步、§8.1）。"""

    model_config = ConfigDict(extra="ignore")

    #: 逐鍵的套用結果；`key` 是 `QbittorrentStep`，也就是 `app/setPreferences` 的鍵名。
    steps: list[SetupStep] = []


class SetupIndexer(BaseModel):
    """精靈第 5 步的狀態（plan §9.3 第 5 步、§8.4）。"""

    model_config = ConfigDict(extra="ignore")

    #: 逐站結果。套件內路徑的 `key` 是 Prowlarr 的 `definitionName`；既有路徑只有一條，
    #: `key` 是 `IndexerKind`。兩條路徑共用同一份形狀，畫面也就是同一組纜繩。
    steps: list[SetupStep] = []
    #: 「之後再說」。這一步與 TMDB 可跳過，完成頁列出跳過了什麼（plan §9.3）。
    skipped: bool = False


class SetupTmdb(BaseModel):
    """精靈第 6 步的狀態（plan §9.3 第 6 步、§8.3）。"""

    model_config = ConfigDict(extra="ignore")

    #: 只有一條纜繩（`configuration`），形狀與其他泊位一致。
    steps: list[SetupStep] = []
    skipped: bool = False


class ServiceHealth(BaseModel):
    """一個服務最後一次健康檢查的結果（plan §3.2、票 10）。

    `status` 是這一次的判定，`last_ok_at` 是**最後一次成功**的時間——兩者要並存，因為
    「現在紅著，但十分鐘前還好好的」與「從來沒通過」對維運是完全不同的兩件事（brief §16.2）。
    """

    model_config = ConfigDict(extra="ignore")

    status: HealthStatus = HealthStatus.UNKNOWN
    #: 實測值：版本號、索引站數量。UI 直接顯示，不翻譯。
    detail: str = ""
    #: 失敗時服務回的原文（英文）。
    error: str = ""
    checked_at: datetime | None = None
    last_ok_at: datetime | None = None
    #: 連續失敗次數（plan §3.2）。成功就歸零。
    failures: int = 0
    #: 這個服務有連線資訊可以拿去檢查。索引站那一步可跳過，所以它可能是 False。
    configured: bool = False
    #: qBittorrent 被改掉的建議偏好鍵（brief §16.3 的「關鍵設定漂移」）。其餘服務一律是空的。
    drift: list[str] = []


class HealthSettings(SettingsGroup):
    """`health_checker` 上一輪的結果（plan §3.2）。

    **不寫進各自的 `settings.services.*`**（plan §3.2 原本的說法）：那幾組是使用者設定的
    連線資訊，整組覆寫是它們的常態（`write_settings`），把迴圈每 5 分鐘改一次的狀態混進去，
    兩邊會互相蓋掉。分成自己一列之後，迴圈只寫這一列，設定頁只寫那幾列。
    """

    KEY = "health"

    #: 逐服務的最後結果；鍵是 `ServiceKind`。
    services: dict[ServiceKind, ServiceHealth] = {}
    #: 每個 Route 都通過了它的五項檢查。逐 Route 的明細在 `routes.health_detail_json`，
    #: 這裡只留總結——匿名的 `GET /api/health` 靠它答 ok / degraded，不必查 routes 表。
    routes: HealthStatus = HealthStatus.UNKNOWN
    checked_at: datetime | None = None


class SetupSettings(SettingsGroup):
    KEY = "setup"

    completed: bool = False
    admin: SetupAdmin = SetupAdmin()
    #: 逐服務的判定；鍵是 `ServiceKind`。
    services: dict[ServiceKind, ServiceProbe] = {}
    #: 本輪輪詢的起點，用來算 2 分鐘上限。全部服務都判定完就清掉。
    probe_started_at: datetime | None = None
    jellyfin: SetupJellyfin = SetupJellyfin()
    qbittorrent: SetupQbittorrent = SetupQbittorrent()
    indexer: SetupIndexer = SetupIndexer()
    tmdb: SetupTmdb = SetupTmdb()


#: 所有分組的清單，用來確認每一組都有預設值。
SETTINGS_GROUPS: tuple[type[SettingsGroup], ...] = (
    JellyfinSettings,
    QbittorrentSettings,
    IndexerSettings,
    TmdbSettings,
    PathSettings,
    SetupSettings,
    HealthSettings,
)
