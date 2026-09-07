"""跨層共用的封閉值集合。純資料，不依賴任何東西（plan §1.3）。"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """使用者角色。由 Jellyfin 的 `Policy.IsAdministrator` 決定（plan §11.1 T0.5）。"""

    ADMIN = "admin"
    USER = "user"


class CollectionType(StrEnum):
    """Jellyfin 媒體庫的類型；沿用 Jellyfin 的字串（brief §4.3）。"""

    MOVIES = "movies"
    TVSHOWS = "tvshows"


class Profile(StrEnum):
    """Route 的命名與解析偏好（CONTEXT.md）。"""

    STANDARD = "standard"
    ANIME = "anime"


class HealthStatus(StrEnum):
    """Route 或服務的最後檢查結果；`UNKNOWN` 表示尚未檢查過。"""

    UNKNOWN = "unknown"
    OK = "ok"
    FAILED = "failed"


class ServiceKind(StrEnum):
    """精靈與健康檢查認得的三個外部服務。字串同時是 compose 的服務名。"""

    JELLYFIN = "jellyfin"
    QBITTORRENT = "qbittorrent"
    PROWLARR = "prowlarr"


class ServiceOrigin(StrEnum):
    """精靈第 2 步對單一服務的判定（plan §9.3）。逐服務判斷，沒有全局模式。"""

    #: 套件內：探得到而且還沒被設定過，Berth 可以全自動接手。
    BUNDLED = "bundled"
    #: 既有：使用者自己的服務（或不在 compose 內），顯示連線表單。
    EXISTING = "existing"
    #: 容器還在啟動；輪詢期間的暫時狀態。
    PENDING = "pending"
    #: 超過輪詢上限仍未就緒，使用者可重試。
    TIMEOUT = "timeout"


class StepStatus(StrEnum):
    """精靈裡一個步驟的結果。逐條纜繩顯示，所以是封閉集合。"""

    #: 這一次真的做了它。
    OK = "ok"
    #: 已經是想要的樣子，這一次沒動它。重按精靈時大部分步驟都會是這個。
    SKIPPED = "skipped"
    FAILED = "failed"
    #: 正在做。每一步開始前就寫進設定，UI 靠輪詢看得到序列走到哪裡。
    RUNNING = "running"
    #: 前面的步驟失敗或還沒輪到，這一步沒跑到。
    PENDING = "pending"


class JellyfinStep(StrEnum):
    """Jellyfin 自動初始化序列的九步（plan §9.4）。順序即宣告順序。"""

    PUBLIC_INFO = "public_info"
    CONFIGURATION = "configuration"
    ADMIN_USER = "admin_user"
    LIBRARIES = "libraries"
    REMOTE_ACCESS = "remote_access"
    COMPLETE = "complete"
    API_KEY = "api_key"
    PLUGIN = "plugin"
    TASKS = "tasks"


class DetectionReason(StrEnum):
    """判定的理由。UI 逐服務顯示，所以是封閉集合而不是自由文字。"""

    #: Jellyfin 的 `StartupWizardCompleted=false`。
    SETUP_PENDING = "setup_pending"
    #: Jellyfin 已經跑過初始精靈。
    SETUP_COMPLETED = "setup_completed"
    #: qBittorrent 免密進得去 API。
    ANONYMOUS_OK = "anonymous_ok"
    #: 需要憑證：qBittorrent 回 403，或 Prowlarr 的 API key 不被接受。
    AUTH_REQUIRED = "auth_required"
    #: Prowlarr 讀得到 API key 而且一個索引站都沒有。
    NO_INDEXERS = "no_indexers"
    #: Prowlarr 已經有索引站，視為使用者自己在用的那一套。
    HAS_INDEXERS = "has_indexers"
    #: 唯讀掛載的 `config.xml` 與環境變數都沒有 API key，退回手動貼上。
    API_KEY_MISSING = "api_key_missing"
    #: compose 主機名解不到 —— 這個服務不在套件裡（從 `COMPOSE_PROFILES` 拿掉了）。
    NOT_DEPLOYED = "not_deployed"
    #: 主機名解得到但連不上，通常是容器還在啟動。
    UNREACHABLE = "unreachable"
    #: 連得上但回的東西不是預期的服務。
    PROTOCOL_MISMATCH = "protocol_mismatch"
    #: 使用者填的既有服務連線資訊測試通過。
    CONNECTED = "connected"
