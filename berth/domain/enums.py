"""跨層共用的封閉值集合。純資料，不依賴任何東西（plan §1.3）。"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """使用者角色。由 Jellyfin 的 `Policy.IsAdministrator` 決定（plan §11.1 T0.5）。"""

    ADMIN = "admin"
    USER = "user"


class MediaKind(StrEnum):
    """一個作品是劇集還是電影（plan §2.2）。

    字串同時是三個東西：`media.id` 的前綴（`tv:1234`）、TMDB `search/multi` 回的
    `media_type`，以及 TMDB 那兩組端點的路徑段（`trending/tv/week`、`movie/popular`）。
    三者一致不是巧合——沿用 provider 的字串就不必維護一張對照表。
    """

    TV = "tv"
    MOVIE = "movie"


class TmdbProblem(StrEnum):
    """向 TMDB 要東西沒要到的四種樣子（票 03 的探索頁、票 04 的 Media 詳情）。

    分成四種而不是一句錯誤訊息，是因為**下一步不同**：前兩種要使用者去精靈第 6 步處理憑證，
    `unreachable` 只能等或查網路，`not_found` 則是那個 id 本身不存在——重試一百次也一樣。
    封閉集合讓 UI 說得出那一步，而不是丟一個空畫面。

    一個 enum 而不是每頁一個：兩頁問的是同一台服務，理由與下一步都一樣，
    各寫一份的話「憑證缺失要連到泊位 3」這條規則遲早會在其中一份裡走樣。
    """

    #: `settings.services.tmdb.api_key` 是空的。連線都不必發（brief §16.3）。
    CREDENTIAL_MISSING = "credential_missing"
    #: TMDB 回 401 / 403：key 有值但它不接受。
    CREDENTIAL_REJECTED = "credential_rejected"
    #: 連不上、逾時，或回的東西不是 TMDB。
    UNREACHABLE = "unreachable"
    #: TMDB 回 404：這個 id 上面沒有作品。只有詳情頁到得了這一種（票 04）。
    NOT_FOUND = "not_found"


class JobState(StrEnum):
    """一個 Job 的生命週期位置（plan §3.1、brief §5.1）。

    宣告順序就是狀態機的主幹，分支緊接在它離開的那一站之後。**這一票只走得到前三個**：
    `requested` 是 `add_download` 建出來的，qBittorrent 收下就是 `submitted`，收不下是
    `submit_failed`。其餘由票 10 起的迴圈驅動——先一次定義完是因為它們是同一個封閉集合，
    分兩批加的話畫面上的狀態字典會有兩份，而其中一份遲早會漏掉一個狀態。
    """

    #: 已經建了 job，但 qBittorrent 還沒收下。
    REQUESTED = "requested"
    #: qBittorrent 收下了。
    SUBMITTED = "submitted"
    #: qBittorrent 拒絕，或根本連不上。可手動重試回 `requested`。
    SUBMIT_FAILED = "submit_failed"
    METADATA_READY = "metadata_ready"
    DOWNLOADING = "downloading"
    STALLED = "stalled"
    MISSING_FILES = "missing_files"
    CLIENT_ERROR = "client_error"
    CLIENT_REMOVED = "client_removed"
    COMPLETED = "completed"
    PLANNING = "planning"
    REVIEW = "review"
    IMPORTING = "importing"
    IMPORTED = "imported"
    IMPORT_FAILED = "import_failed"
    REMOVED = "removed"


class JobTrigger(StrEnum):
    """這個 Job 是誰要的（`CONTEXT.md`、plan §2.3）。

    規則 id 與重新入庫的來源目錄放在 `jobs.trigger_ref`，不編進這個字串——畫面要拿它
    分組，而 `rss:12` 那種寫法會讓每一條規則各自成為一種 trigger。
    """

    MANUAL = "manual"
    RSS = "rss"
    REIMPORT = "reimport"


class EventType(StrEnum):
    """Job 時間線上一筆事件的型別（brief §5.2）。

    只列**已經有東西會寫它**的那幾種。brief §5.2 那一串是整個管線寫完之後的樣子，
    照抄進來會讓時間線的字典裡有一半是永遠不會出現的詞，而 i18n 要為每一個備一句話。
    每個轉換落地時把自己那一個加進來。
    """

    #: `add_download` 建了 job（trigger、user、media、route）。
    CREATED = "created"
    #: qBittorrent 收下了（client、category、save_path）。
    SUBMITTED = "submitted"
    #: 送單失敗，payload 帶服務回的原文。
    SUBMIT_FAILED = "submit_failed"
    #: 使用者按了重試，回到 `requested`。
    RETRIED = "retried"
    #: 檔案清單到手（file_count、total_size）。票 10 的 poller 寫。
    METADATA_RECEIVED = "metadata_received"
    #: 進度。**每跨 25% 一筆**，不是每一輪一筆（plan §3.1）。
    PROGRESS = "progress"
    #: 沒有資料在動超過一段時間（client_state、idle_minutes）。恢復時寫一筆 `progress`。
    STALLED = "stalled"
    #: 下載完成（brief §5.1 的四條判定全部成立）。
    COMPLETED = "completed"
    #: 出了一件需要人處理的事（brief §5.2 的 `issue_detected(type)`）。
    #: **`issues` 表要到 M2 才有**（plan §11.3），所以 M1 的載體就是這一筆事件；
    #: `type` 是 `IssueType`，不是自由文字。
    ISSUE_DETECTED = "issue_detected"
    #: 檔案清單一到手就先算一份預估的 Plan（brief §5.1）。**不動檔案**，也不改 Job 的狀態
    #: ——它回答的是「還來得及取消嗎」。
    PREPLAN = "preplan"
    #: 下載完成之後算出來的正式 Plan（engine、逐信心的檔案數）。
    PLAN_GENERATED = "plan_generated"
    #: 這一份 Plan 要人看過才動（`reason` 是 `ReviewReason`）。
    REVIEW_REQUIRED = "review_required"
    #: 一個檔案硬鏈接進媒體庫了（file、target）。**一個檔案一筆**（brief §5.2、plan §3.1 的 ×N）。
    LINKED = "linked"
    #: 一個檔案沒鏈接成（file、target、errno、error）。原文不翻譯：它是「哪個掛載少了」的證據。
    LINK_FAILED = "link_failed"
    #: 入庫完成後通知了 Jellyfin（count、paths）。**請求送到了**，不代表它掃完了。
    JELLYFIN_SCAN_REQUESTED = "jellyfin_scan_requested"
    #: 反查到這一筆 Job 入庫的檔案在 Jellyfin 裡的 item（count）。
    JELLYFIN_ITEM_RESOLVED = "jellyfin_item_resolved"
    #: 觸發了 MergeVersions 的排程任務（task）。
    MERGE_VERSIONS_REQUESTED = "merge_versions_requested"
    #: 對 Jellyfin 的一次請求沒成（request 是 `JellyfinRequest`、error）。**只記不擋**：
    #: 檔案已經在媒體庫裡了，Jellyfin 自己的排程掃描遲早會看到它們（plan §3.3）。
    JELLYFIN_REQUEST_FAILED = "jellyfin_request_failed"


class JellyfinRequest(StrEnum):
    """`jellyfin_request_failed` 事件 payload 裡的 `request`：沒成的是哪一次請求。

    封閉集合，因為兩種的下一步不同：通知沒送到，Jellyfin 的排程掃描遲早會補上；
    MergeVersions 沒觸發，同一集的兩個版本會一直是兩個條目，直到有人去按那個任務。
    """

    #: `POST /Library/Media/Updated`（plan §8.2 的 `notify_paths`）。
    SCAN = "scan"
    #: `POST /ScheduledTasks/Running/{id}`，或根本沒有存下任務 id（brief §7.7）。
    MERGE = "merge"


class IssueType(StrEnum):
    """`issue_detected` 事件 payload 裡的 `type`（brief §5.2、plan §3.1）。

    M2 建 `issues` 表時它就是那張表的 `type` 欄——現在先把封閉集合定下來，因為畫面已經
    要逐種說一句話，而自由文字的「理由」翻譯不了也查詢不了。
    """

    #: 客戶端說檔案不見了（`missingFiles`）。
    MISSING_FILES = "missing_files"
    #: 客戶端自己報錯（state `error`）。
    CLIENT_ERROR = "client_error"
    #: torrent 從客戶端消失了。complete 檔案可能還在，M2 的 `reimport` 撿得回來。
    CLIENT_REMOVED = "client_removed"
    #: qBittorrent 上有一個掛著 Berth category 或 tag、但 Berth 沒有 Job 的 torrent
    #: （plan §3.2 的 `unknown_torrent`）。
    UNKNOWN_TORRENT = "unknown_torrent"
    #: 入庫的檔案重試到最後仍然在 Jellyfin 裡找不到對應的 item（plan §3.2 的
    #: `jellyfin_resolver`）。多半是 Jellyfin 看不到那條路徑，或它把資料夾認成了別的作品。
    JELLYFIN_ITEM_UNRESOLVED = "jellyfin_item_unresolved"


class LedgerStatus(StrEnum):
    """一筆帳本現在與磁碟對不對得起來（plan §2.3 的 `ledger.status`、brief §9.1）。

    importer 寫下的一律是 `ok`；其餘三種是 M2 的 Reconciler 比對之後寫的。
    """

    OK = "ok"
    TARGET_MISSING = "target_missing"
    SOURCE_MISSING = "source_missing"
    INODE_MISMATCH = "inode_mismatch"


class CollectionType(StrEnum):
    """Jellyfin 媒體庫的類型；沿用 Jellyfin 的字串（brief §4.3）。"""

    MOVIES = "movies"
    TVSHOWS = "tvshows"


def collection_type_for(kind: MediaKind) -> CollectionType:
    """一部作品進得了哪一種媒體庫。

    劇集不能送進 movies 媒體庫：命名模板不同（plan §5），而 Jellyfin 會把它掃成一堆電影。
    這是規則不是巧合，所以住在 `domain/` 而不是兩個呼叫端各判一次。
    """
    return CollectionType.TVSHOWS if kind is MediaKind.TV else CollectionType.MOVIES


class IndexerProblem(StrEnum):
    """索引站那邊沒搜到東西的五種樣子（票 08 的結果表）。

    與 `TmdbProblem` 同一個道理：分成五種而不是一句錯誤訊息，是因為**下一步不同**。
    索引站是精靈裡唯一可以跳過的一步，所以 `not_configured` 不是失敗而是「還沒接」——
    畫面要把人送回泊位 5，不是叫他重試。
    """

    #: 精靈第 5 步跳過了，或連線資訊是空的。一個請求都不必發（plan §9.3 第 5 步）。
    NOT_CONFIGURED = "not_configured"
    #: 有位址，但這部作品連一個查得出去的關鍵字都沒有（快照還沒抓到，使用者也沒自己打）。
    NO_QUERY = "no_query"
    #: `t=caps` 說這個端點不提供搜尋。位址對、key 也對，但它做不了這件事。
    NO_SEARCH = "no_search"
    #: API key 被拒（401 / 403）。
    CREDENTIAL_REJECTED = "credential_rejected"
    #: 連不上、逾時，或回的東西不像索引站。
    UNREACHABLE = "unreachable"


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


class RouteCheck(StrEnum):
    """精靈第 7 步對一個 Route 跑的檢查（plan §9.5、brief §4.4）。順序即宣告順序，
    前一條斷了就不跑下一條——後面的檢查測的會是錯的路徑。

    健康頁的 Route 檢查用同一組（`health_checker`，票 10）。
    """

    #: qBittorrent 上這個 Route 的 category。已存在但 save path 不同 → 衝突，不覆寫。
    CATEGORY = "category"
    #: qBittorrent 報的全域 save path 與這個 category 的路徑，在 Berth 內 `stat` 得到。
    DOWNLOAD_PATH = "download_path"
    #: Jellyfin 報的媒體庫路徑，在 Berth 內 `stat` 得到。
    LIBRARY_PATH = "library_path"
    #: Berth 在 Route 目標寫的探測檔，Jellyfin 那台也看得到（`Environment/ValidatePath`）。
    PROBE_VISIBLE = "probe_visible"
    #: complete 目錄與 Route 目標之間真的鏈接得起來，而且是同一個 inode。
    HARDLINK = "hardlink"


class QbittorrentStep(StrEnum):
    """第 4 步逐鍵套用建議偏好（plan §9.3 第 4 步、§8.1）。

    值就是 `app/setPreferences` 的鍵名——一條纜繩對一個鍵，畫面顯示的與送出去的是同一個字串。
    """

    TEMP_PATH_ENABLED = "temp_path_enabled"
    TEMP_PATH = "temp_path"
    SAVE_PATH = "save_path"
    AUTO_TMM_ENABLED = "auto_tmm_enabled"
    CATEGORY_CHANGED_TMM_ENABLED = "category_changed_tmm_enabled"
    #: 「同一組帳密」勾了才會有這一條；`web_ui_password` 只寫不讀。
    PASSWORD = "web_ui_password"


#: 精靈第 5 步「替 Prowlarr 介面設登入」那一條纜繩的 key（plan §9.3 第 5 步）。
#: **不與 `IndexerKind.PROWLARR` 同名**：那一條與站接不接得上無關，混在一起會讓「這一步
#: 做完了沒」把一條永遠存在的憑證步驟當成「至少接上了一個站」。
PROWLARR_LOGIN_STEP = "prowlarr_login"


class IndexerKind(StrEnum):
    """第 5 步接索引站的兩種方式（plan §8.4、§9.3 第 5 步）。"""

    PROWLARR = "prowlarr"
    #: 任意 Torznab 端點（Jackett 的聚合網址或單站）。
    TORZNAB = "torznab"


class DetectionReason(StrEnum):
    """判定的理由。UI 逐服務顯示，所以是封閉集合而不是自由文字。"""

    #: Jellyfin 的 `StartupWizardCompleted=false`。
    SETUP_PENDING = "setup_pending"
    #: Jellyfin 已經跑過初始精靈。
    SETUP_COMPLETED = "setup_completed"
    #: qBittorrent 免密進得去 API。
    ANONYMOUS_OK = "anonymous_ok"
    #: 需要憑證：Prowlarr 的 API key 不被接受，或 qBittorrent 要帳密。
    AUTH_REQUIRED = "auth_required"
    #: qBittorrent 把 Berth 這台的 IP 封了（連續 5 次登入失敗，brief §20.2、票 10）。
    #: 與 `AUTH_REQUIRED` 分開的理由是**下一步不同**：帳密不對要去改設定，被封要等封鎖過期
    #: 或去 qBittorrent 的介面解除——改帳密只會再失敗五次，把封鎖時間重新算一輪。
    IP_BANNED = "ip_banned"
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


class PlanStatus(StrEnum):
    """一份 Import Plan 現在的位置（plan §2.3 的 `plans.status`）。

    **它與 Job 狀態回答的是不同的問題**：Job 說的是那個 torrent 走到哪一站，Plan 說的是
    「這一份決定被採信到什麼程度」。一筆 `review` 的 Job 一定有一份 `pending_review` 的
    Plan，但一份 `preplan` 的 Plan 底下的 Job 可能還在下載。
    """

    #: `metadata_ready` 時算的預估（brief §5.1）。沒有 mediainfo，也還沒有人採信它。
    PREPLAN = "preplan"
    #: 全部 high / medium 而且 Route 允許：不必問人（brief §6.5）。
    AUTO = "auto"
    PENDING_REVIEW = "pending_review"
    #: 使用者在 Review Queue 按了核准（M2）。
    APPROVED = "approved"
    REJECTED = "rejected"
    #: importer 已經逐檔套用完（票 12）。
    APPLIED = "applied"
    FAILED = "failed"


class PlanEngine(StrEnum):
    """這一份 Plan 是誰算的（plan §2.3 的 `plans.engine`、brief §5.2）。"""

    RULES = "rules"
    #: AI fallback（M4；介面在 plan §4.5，M1 的實作永遠沒有意見）。
    AI = "ai"
    #: 使用者在 Review Queue 逐列改過（M2）。
    USER = "user"


class ReviewReason(StrEnum):
    """為什麼這一份 Plan 停下來等人（brief §5.2 的 `review_required(reason)`）。

    封閉集合而不是一句話：畫面要照理由說出**下一步**（PRODUCT 原則 4），而三種理由的
    下一步不一樣——低信心要人指定季集，被 Route 擋下的 medium 只要人點頭，
    而「這一包沒有東西可以入庫」多半表示送錯了 torrent。
    """

    #: 有檔案落在 low：季集推不出來、有衝突，或數量與 TMDB 對不上（brief §6.5）。
    LOW_CONFIDENCE = "low_confidence"
    #: 這條 Route 關掉了 medium 自動入庫（`routes.medium_auto_import`，brief §6.5）。
    MEDIUM_NOT_ALLOWED = "medium_not_allowed"
    #: 一個會被寫進媒體庫的檔案都沒有（整包 OST、整包光碟結構、整包對不到）。
    NOTHING_TO_IMPORT = "nothing_to_import"
    #: 目標路徑上已經有一個**別的**檔案（inode 不同，plan §3.3）。Berth 不覆寫媒體庫裡
    #: 不是它鏈接的東西（brief §5.3），所以停下來等人決定。
    TARGET_EXISTS = "target_exists"
