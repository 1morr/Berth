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
    #: 管理員核准或拒絕了停在 review 的那一份 Plan（plan、`decision` 是 `approved` /
    #: `rejected`、核准時另帶 `files`：要寫進媒體庫的檔案數；M2 票 07）。
    REVIEW_DECIDED = "review_decided"
    #: 一個檔案硬鏈接進媒體庫了（file、target）。**一個檔案一筆**（brief §5.2、plan §3.1 的 ×N）。
    LINKED = "linked"
    #: 一個檔案沒鏈接成（file、target、errno、error）。原文不翻譯：它是「哪個掛載少了」的證據。
    LINK_FAILED = "link_failed"
    #: 入庫完成後通知了 Jellyfin（count、paths）。**請求送到了**，不代表它掃完了。
    JELLYFIN_SCAN_REQUESTED = "jellyfin_scan_requested"
    #: 反查到這一筆 Job 入庫的檔案在 Jellyfin 裡的 item（count）。
    JELLYFIN_ITEM_RESOLVED = "jellyfin_item_resolved"
    #: 刪除範圍跑完了（brief §9.2）。payload 逐旗標說出**真的**做了什麼：`links` 是移掉的
    #: 媒體庫鏈接數、`sources` 是刪掉的來源檔數、`torrent` 是有沒有從 qBittorrent 移除、
    #: `freed` 是真的空出來的位元組。「按了哪幾個勾」與「發生了什麼」不是同一件事——
    #: 帳本上早就不在的那一條勾了也沒得刪，而時間線要說得出實際發生的那一份。
    DELETED = "deleted"
    #: 對 Jellyfin 的一次請求沒成（request 是 `JellyfinRequest`、error）。**只記不擋**：
    #: 檔案已經在媒體庫裡了，Jellyfin 自己的排程掃描遲早會看到它們（plan §3.3）。
    JELLYFIN_REQUEST_FAILED = "jellyfin_request_failed"
    #: 管理員看過一個 medium 自動入庫的檔案，說它是對的（ledger、target；M2 票 06）。
    #: `ledger.audit` 與那一列 Plan Item 的旗標同時清掉。
    AUDIT_CONFIRMED = "audit_confirmed"
    #: 管理員撤銷了一個 medium 自動入庫的檔案（ledger、target、`unlinked`；M2 票 06）：
    #: 硬鏈接與帳本那一列都沒了，這一筆回到 `review`。`unlinked` 是**真的**移掉了沒有——
    #: 撤銷之前有人已經在 Jellyfin 裡刪掉它的話是 `false`。
    AUDIT_UNDONE = "audit_undone"
    #: 管理員改了一個檔案的處置（M2 票 08 的 rematch，brief §9.4）：`plan` 是記下這次修正的那一份
    #: 單列 Plan，`file` 是來源，`from` / `to` 各是 `{action, season, episode_start, episode_end,
    #: target}`——說得出從什麼改成什麼。`target` 空字串是「不在媒體庫裡」。
    REMATCHED = "rematched"
    #: 規劃時有檔案與帳本上既有的一份重複，自動模式略過它們（brief §7.8）：`files` 是這一包裡
    #: 被略過的那幾個（來源路徑）。它們各自在 Review Queue 上是一列 `duplicate`。
    DUPLICATE_SKIPPED = "duplicate_skipped"
    #: 管理員決定了一個重複版本（`decision` 是 `DuplicateDecision`、`file`、`target` 是新的那一份
    #: 落在哪裡、`replaced` 是被取代的那一條；M2 票 08）。
    DUPLICATE_DECIDED = "duplicate_decided"


class JellyfinRequest(StrEnum):
    """`jellyfin_request_failed` 事件 payload 裡的 `request`：沒成的是哪一次請求。

    **只剩一種，仍然是封閉集合**（票 14b 拿掉了 `merge`）：畫面照它說出那一種失敗的下一步，
    而自由文字翻譯不了。下一種失敗加進來時，舊事件的 payload 不必改。
    """

    #: `POST /Library/Media/Updated`（plan §8.2 的 `notify_paths`）。
    SCAN = "scan"


class IssueType(StrEnum):
    """一件「要有人決定」的事是哪一種（brief §9.1、plan §2.4）。

    **十一種的聯集，一個封閉集合**（2026-09-22 定，M2 票 05）：前五種是管線自己在路上
    發現的（M1 起寫 `issue_detected` 事件，M2 起同時寫一列 `issues`），後六種是對帳比完
    四方之後才知道的。兩邊共用同一個集合，所以加一種型別而沒替它決定 `subject` 取哪一欄、
    或沒給它動作，紅的會是 `SUBJECT_OF` 與 `ISSUE_ACTIONS` 那兩條閘門。

    `unknown_torrent` 在 brief §9.1 的表上算對帳的七種，但**今天寫它的是 `qbit_poller`**
    （plan §3.2）——票 09 讓對帳也走到它之後，兩個生產者寫的是同一個 `(type, subject)`，
    而冪等鍵會把它們收成一筆。
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
    #: 帳本有、媒體庫裡那個目標檔不在了（使用者在 Jellyfin 或檔案總管刪的，brief §9.5）。
    #: **M2 票 05 唯一做得出來的對帳檢查**，其餘六種在票 09。
    LIBRARY_LINK_MISSING = "library_link_missing"
    #: 帳本有、complete 裡那個來源檔不在了（torrent 被移除且刪檔）。
    SOURCE_MISSING = "source_missing"
    #: 目標與來源不是同一個 inode：有人用複製取代了硬鏈接，或它被轉碼覆蓋了。
    INODE_MISMATCH = "inode_mismatch"
    #: complete 底下的一個目錄既不屬於 qBittorrent 任何 torrent，也不在帳本上。
    ORPHAN_COMPLETE = "orphan_complete"
    #: 媒體庫裡有一個 Berth 不認得的檔案。**只列出，永不自動刪**（brief §9.1）。
    UNMANAGED_LIBRARY_FILE = "unmanaged_library_file"
    #: Job 已經 `imported`，帳本上卻一列都沒有。
    JOB_WITHOUT_FILES = "job_without_files"


class IssueStatus(StrEnum):
    """一件 Issue 還要不要人決定（plan §2.4）。

    只有 `open` 受冪等鍵約束：同一個 `(type, subject)` 最多一筆。決定過的那幾筆留著當
    歷史，同一件事再發生時開的是新的一筆——「上次怎麼處理的」與「現在又來了」是兩件事。
    """

    OPEN = "open"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class IssueSubject(StrEnum):
    """冪等鍵 `(type, subject)` 裡的 `subject` 取哪一欄（plan §2.4）。

    **依型別取**，因為「同一件事」的定義逐型別不同：媒體庫少一個檔案是那條路徑的事，
    torrent 報錯是那一筆下載的事。取哪一欄由 `SUBJECT_OF` 寫死，不由呼叫端各自決定。
    """

    PATH = "path"
    JOB_HASH = "job_hash"
    LEDGER_ID = "ledger_id"


#: 逐型別的冪等鍵來源（plan §2.4 那一段逐型別寫死了取哪一欄）。
#:
#: **要涵蓋整個 `IssueType`**（`tests/unit/test_issue_types.py` 守著）：加一種型別而沒在
#: 這裡決定它的 `subject`，寫進表裡的那一筆就沒有冪等鍵，於是每一輪對帳都開一筆新的。
SUBJECT_OF: dict[IssueType, IssueSubject] = {
    # 有路徑的用路徑：帳本或檔案的那一條。
    IssueType.LIBRARY_LINK_MISSING: IssueSubject.PATH,
    IssueType.SOURCE_MISSING: IssueSubject.PATH,
    IssueType.INODE_MISMATCH: IssueSubject.PATH,
    IssueType.UNMANAGED_LIBRARY_FILE: IssueSubject.PATH,
    # complete 那一側的單位是目錄，不是檔案。
    IssueType.ORPHAN_COMPLETE: IssueSubject.PATH,
    # 客戶端那幾種的單位是一筆下載（info hash 就是 `job_hash`，plan §2.3）。
    IssueType.UNKNOWN_TORRENT: IssueSubject.JOB_HASH,
    IssueType.CLIENT_ERROR: IssueSubject.JOB_HASH,
    IssueType.CLIENT_REMOVED: IssueSubject.JOB_HASH,
    IssueType.JOB_WITHOUT_FILES: IssueSubject.JOB_HASH,
    # **`missing_files` 也是一筆下載**（2026-09-22，票 05 實作時改判；plan §2.4 原本把它
    # 列在「用路徑」那一組）。它有**兩條偵測路徑**：Berth 自己比 complete 底下的檔案時
    # 知道少了哪幾個，而 qBittorrent 報 `missingFiles` 時 Berth 手上一條路徑都沒有——
    # 多半正是因為它看不到那個掛載。同一種型別的 subject 不可以看呼叫端而定，否則
    # 「同一件事」會有兩種定義。而它的下一步（重新 recheck / 承認遺失，brief §9.1）本來
    # 就是整包 torrent 的事，不是逐檔的。少了哪幾個放在 `detail_json.missing`。
    IssueType.MISSING_FILES: IssueSubject.JOB_HASH,
    # 反查用完是**那一列帳本**的事：同一筆 Job 的兩集各自反查，各自放棄。
    IssueType.JELLYFIN_ITEM_UNRESOLVED: IssueSubject.LEDGER_ID,
}


class IssueAction(StrEnum):
    """resolve 一件 Issue 時按的那一顆（brief §9.1 的「預設建議動作」那一欄）。

    **只有 `library_link_missing` 的三顆**（M2 票 05）：其餘十種的動作跟著它們的檢查一起
    在票 09 加。先立三顆是因為形狀要對——`ISSUE_ACTIONS` 那張表逐型別說得出按得了什麼，
    第二種型別進來時只是多一列。
    """

    #: 重新鏈接：來源還在 complete，照帳本那一列再硬鏈接一次。
    RELINK = "relink"
    #: 承認刪除並清帳本：那個檔案本來就該不在，把帳本那一列刪掉。
    FORGET = "forget"
    #: 連 complete 一起刪：這一筆下載整個不要了。走 `delete_job` 的四個旗標（票 04），
    #: 不是另一套刪除（plan §11.3 決定 4）。
    DELETE_COMPLETE = "delete_complete"


#: 逐型別按得了哪幾顆，**順序就是畫面上的順序**（第一顆是 brief §9.1 的預設建議動作）。
#:
#: **要涵蓋整個 `IssueType`**（`tests/unit/test_issue_types.py` 守著）。空 tuple 是誠實的
#: 答案：那一種這一票還偵測不出來，也就還沒有人替它決定按下去會發生什麼（票 09）。
ISSUE_ACTIONS: dict[IssueType, tuple[IssueAction, ...]] = {
    IssueType.LIBRARY_LINK_MISSING: (
        IssueAction.RELINK,
        IssueAction.FORGET,
        IssueAction.DELETE_COMPLETE,
    ),
    IssueType.SOURCE_MISSING: (),
    IssueType.INODE_MISMATCH: (),
    IssueType.ORPHAN_COMPLETE: (),
    IssueType.UNKNOWN_TORRENT: (),
    IssueType.UNMANAGED_LIBRARY_FILE: (),
    IssueType.JOB_WITHOUT_FILES: (),
    IssueType.MISSING_FILES: (),
    IssueType.CLIENT_ERROR: (),
    IssueType.CLIENT_REMOVED: (),
    IssueType.JELLYFIN_ITEM_UNRESOLVED: (),
}


class ReconcileSide(StrEnum):
    """對帳比的四方（brief §9.1）。

    **四方各自走完才寫下 Issue**，而任一方問不到就跳過那一方並在這一輪的結果上說出來
    ——不把「問不到」誤判成「不見了」（brief §16.2、plan §3.2）。所以這是一個封閉集合：
    畫面要逐方說「比到哪、幾筆」，而跳過的那一方要說得出為什麼。
    """

    #: Berth 自己的帳本。永遠問得到——它就在同一個資料庫裡。
    LEDGER = "ledger"
    #: qBittorrent 上掛著 Berth 記號的 torrent。
    CLIENT = "client"
    #: complete 目錄。
    COMPLETE = "complete"
    #: 每一條 Route 的媒體庫目錄。**逐 Route 各自問得到**：一條沒掛上不該讓其餘幾條停擺。
    LIBRARY = "library"


class LedgerStatus(StrEnum):
    """一筆帳本現在與磁碟對不對得起來（plan §2.3 的 `ledger.status`、brief §9.1）。

    importer 寫下的一律是 `ok`；其餘三種是 M2 的 Reconciler 比對之後寫的。
    """

    OK = "ok"
    TARGET_MISSING = "target_missing"
    SOURCE_MISSING = "source_missing"
    INODE_MISMATCH = "inode_mismatch"


class InventoryStatus(StrEnum):
    """媒體庫牆上一格的狀態（票 13、`.scratch/m1/library-shape.md` §5）。

    **宣告順序就是優先序**：一部作品常常同時是好幾件事（第一季入庫了、第二季在下載、
    有一包停在待審），而一格只說一件——需要人的那一件排前面。
    """

    #: 這條 Route 上有一筆 Job 卡在失敗（送單、客戶端、入庫）。在你動手之前不會自己好。
    FAILED = "failed"
    #: 有一份計劃停下來等人。
    REVIEW = "review"
    #: 有東西還在路上：送單到入庫之間的任何一站。
    DOWNLOADING = "downloading"
    #: 電影的正片入庫了；劇集每一集已經播出的正片都入庫了。
    COMPLETE = "complete"
    #: 有入庫，但還有已經播出的集數沒有。
    PARTIAL = "partial"
    #: 媒體庫裡一個正片都沒有（torrent 被移除了、只入庫了特典）。
    EMPTY = "empty"


class EpisodeStatus(StrEnum):
    """Media 詳情集表上一集的入庫狀態（票 13，使用者拍板五種）。

    **宣告順序就是優先序**：第二個版本在下載的那一集已經看得了，所以是已入庫。
    「卡住」與「下載中」分開、「未播出」與「缺」分開：停在待審的那一集說成下載中是騙人，
    還沒播的集說成缺也是。
    """

    #: 帳本裡有正片蓋到這一集。
    IMPORTED = "imported"
    #: 有一筆停下來的 Job（待審、入庫失敗），它的計劃蓋到這一集。
    STUCK = "stuck"
    #: 有一筆還在路上的 Job，它的計劃（含下載中的預估）蓋到這一集。
    DOWNLOADING = "downloading"
    #: 已經播出，而上面三件都不成立。
    MISSING = "missing"
    #: 還沒播，或 TMDB 還沒有播出日。
    UNAIRED = "unaired"


class JellyfinPresence(StrEnum):
    """Jellyfin 找到這部作品了沒——媒體庫卡片上那一行（票 13）。

    分四種而不是「有沒有連結」：「還在找」只要等，「找不到」要人去 Jellyfin 看它把資料夾
    認成了什麼（`IssueType.JELLYFIN_ITEM_UNRESOLVED`），兩者的下一步不同。
    """

    #: 有一個正片反查到了（劇集要連 Series 也到手）。畫得出一條深連結。
    FOUND = "found"
    #: 還排著反查，或找到了那一集卻還不知道它屬於哪個 Series。
    SEARCHING = "searching"
    #: 每一個正片的反查都用完了。
    LOST = "lost"
    #: 媒體庫裡還沒有正片，沒有東西可以找。
    NONE = "none"


class CollectionType(StrEnum):
    """Jellyfin 媒體庫的類型；沿用 Jellyfin 的字串（brief §4.3）。"""

    MOVIES = "movies"
    TVSHOWS = "tvshows"


class JellyfinImageType(StrEnum):
    """Berth 代理得了的 Jellyfin 圖片類型（M1.5 票 04）；沿用 Jellyfin 的字串。

    **是白名單**：沒有呼叫端的類型不開。劇照（票 08）用到時再加。
    """

    PRIMARY = "Primary"
    #: 繼續觀看與下一集的橫卡（票 07）：16:9 的劇照或背景圖。
    THUMB = "Thumb"
    BACKDROP = "Backdrop"


class ImageSize(StrEnum):
    """代理圖片的具名尺寸（M1.5 票 04）。實際像素在 `services/jellyfin_images.py`。

    **前端不能指定任意尺寸**：每一種尺寸都要 Jellyfin 重算一次、在它的快取裡多存一份，
    所以只收幾個名字（TMDB `w342` 那種具名尺寸的做法），名字照形狀取。
    """

    #: 2:3 的海報，牆上一格。
    POSTER = "poster"
    #: 16:9 的橫圖，繼續觀看與下一集的一格（票 07）。
    WIDE = "wide"


class LibrarySort(StrEnum):
    """媒體庫牆的排序鍵（M1.5 票 06）；沿用 Jellyfin `ItemSortBy` 的字串。

    **是 jellyfin-web 排序選單上的那幾個**，不是 `ItemSortBy` 的全部。劇集庫與電影庫各開哪幾個、
    順序與後面接什麼鍵在 `services/jellyfin_access.BROWSABLE`（研究 library-browsing.md §7）。
    """

    SORT_NAME = "SortName"
    RANDOM = "Random"
    COMMUNITY_RATING = "CommunityRating"
    CRITIC_RATING = "CriticRating"
    #: 劇集庫是作品加入的時間（Jellyfin 掃到它的那一刻），電影庫是檔案時間（研究 §3.1）。
    DATE_CREATED = "DateCreated"
    #: 劇集：最新那一集加入的時間（「新集加入」）。
    DATE_LAST_CONTENT_ADDED = "DateLastContentAdded"
    #: 劇集：這位使用者最近看過其中一集的時間。
    SERIES_DATE_PLAYED = "SeriesDatePlayed"
    #: 電影：這位使用者最近看的時間。
    DATE_PLAYED = "DatePlayed"
    #: 照分級高低，不是照字串（研究 §3.1）。
    OFFICIAL_RATING = "OfficialRating"
    PLAY_COUNT = "PlayCount"
    PREMIERE_DATE = "PremiereDate"
    RUNTIME = "Runtime"


class SortOrder(StrEnum):
    """排序方向；沿用 Jellyfin `sortOrder` 的字串。沒有值的排在升冪最前、降冪最後（研究 §3.1）。"""

    ASCENDING = "Ascending"
    DESCENDING = "Descending"


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
    """Jellyfin 自動初始化序列的七步（plan §9.4）。順序即宣告順序。

    原本有第 8、9 步（裝 MergeVersions、記下兩個合併任務的 Id）。12.x 原生合併多版本，
    插件在上面是空跑，所以整段移除了（票 14b、brief §19、§20.9）。
    """

    PUBLIC_INFO = "public_info"
    CONFIGURATION = "configuration"
    ADMIN_USER = "admin_user"
    LIBRARIES = "libraries"
    REMOTE_ACCESS = "remote_access"
    COMPLETE = "complete"
    API_KEY = "api_key"


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


#: 一份 Plan 的決定**已經定案**的那幾種狀態：自動入庫、核准過、套用完或套用失敗。其餘三種
#: （預估、等審核、被拒絕正要重算）裡的每一列都還會變——那時候改一個檔案是 Plan 編輯的事，
#: 佇列上的 `unmatched` 與 `duplicate`、Media 詳情的修正入口也只給定案了的那些（M2 票 08）。
SETTLED_PLANS: frozenset[PlanStatus] = frozenset(
    {PlanStatus.AUTO, PlanStatus.APPROVED, PlanStatus.APPLIED, PlanStatus.FAILED}
)


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
    #: 一個 medium 自動入庫的檔案被管理員從 Review Queue 撤銷了（CONTEXT.md 的 Audit）。
    #: 下一步是改那一列的季集或駁回，不是再點一次頭——這份 Plan 已經被說過一次「不對」。
    AUDIT_UNDONE = "audit_undone"


class ReviewKind(StrEnum):
    """Review Queue 上一列是哪一種事（plan §6 review 群組，2026-09-22 定）。

    **五種一開始就在**，雖然 M2 票 06 只填 `audit` 與 `issue`：佇列的排序與畫面的分組都照
    這五種定（`REVIEW_PRIORITY`），後面兩票只是把列填進去，不改形狀。
    """

    #: 低信心的 Plan，逐檔可改（票 07）。
    PLAN = "plan"
    #: medium 自動入庫、等人確認的檔案（CONTEXT.md 的 Audit）。
    AUDIT = "audit"
    #: 對不到的檔案（票 08）。
    UNMATCHED = "unmatched"
    #: Tags 完全相同的兩個版本（票 08）。
    DUPLICATE = "duplicate"
    #: 一件還開著的 Issue（brief §9.1）。
    ISSUE = "issue"


#: 佇列的排序鍵：**需要人動手的排前面**（plan §6）。`plan` 與 `unmatched` 不處理就卡著一筆
#: 下載；`audit` 與 `duplicate` 已經在媒體庫裡，只是等人看一眼；`issue` 多半是外面發生的事
#: （有人在 Jellyfin 裡刪了東西），它的一顆按鈕就是全部的工作。同一級之內舊的在前。
REVIEW_PRIORITY: dict[ReviewKind, int] = {
    ReviewKind.PLAN: 0,
    ReviewKind.UNMATCHED: 0,
    ReviewKind.AUDIT: 1,
    ReviewKind.DUPLICATE: 1,
    ReviewKind.ISSUE: 2,
}


class AuditReason(StrEnum):
    """`audit` 那一類的理由（`GET /review` 每一列的 `reason.code`）。

    **只有一種，仍然是封閉集合**（同 `JellyfinRequest`）：理由是給畫面挑句子的 code，不是後端
    拼好的一句話（M2 票 06）。解析器那幾句英文的 `reasons` 是原文，放在列上的 `notes`。
    """

    #: 信心是 medium，而這條 Route 允許 medium 自動入庫（brief §6.5）。
    MEDIUM_AUTO_IMPORTED = "medium_auto_imported"


class UnmatchedReason(StrEnum):
    """`unmatched` 那一類的理由（`GET /review` 每一列的 `reason.code`，M2 票 08）。

    **只有一種**（同 `AuditReason`）：為什麼對不到是那一列 Plan Item 的理由（`reasons`），這一格只說
    這一列在等什麼——它留在 complete 原位，等人指派、標記或忽略（brief §7.4）。
    """

    #: 對不到任何一集，沒有入庫，留在 complete 原位。
    LEFT_IN_PLACE = "left_in_place"


class DuplicateReason(StrEnum):
    """`duplicate` 那一類為什麼停下來（brief §7.8）。兩種的後果不一樣，畫面各說各的。"""

    #: 同一集、同一組 Tags：與媒體庫裡那一份是同一個版本。
    SAME_VERSION = "same_version"
    #: 同一個起始集、結束集不同（`S01E03-E04` 對 `S01E03`）。Jellyfin 12 的版本分組鍵只有季號與
    #: 集號，會把兩者併成同一集的兩個版本，後面那一集從集列表消失（brief §20.9）。
    SPAN_CLASH = "span_clash"


class DuplicateDecision(StrEnum):
    """`duplicate` 那一類按得了的三顆（brief §7.8）。"""

    #: 新的那一份進媒體庫，舊的那一條鏈接拆掉、帳本那一列改指新的來源。
    REPLACE = "replace"
    #: 兩份都留著。完全相同的那一種，新的檔名多一個序號標籤（`[2]`，2026-09-23 使用者拍板）。
    KEEP_BOTH = "keep_both"
    #: 不要新的那一份：它留在 complete 原位，這一列從佇列上消失。
    SKIP = "skip"


class AuditAction(StrEnum):
    """`audit` 那一類按得了的兩顆（brief §6.5：「一鍵撤銷或確認」）。"""

    #: 它是對的：清掉兩處旗標，檔案留在媒體庫裡。
    CONFIRM = "confirm"
    #: 它是錯的：拆掉硬鏈接、刪掉帳本那一列，這一筆回到 `review`。
    UNDO = "undo"


class PlanDecision(StrEnum):
    """`plan` 那一類按得了的兩顆（plan §3.1 `review` 的兩條出邊，M2 票 07）。"""

    #: 照提案入庫（逐列改過的照改過的）：`review → importing`。
    APPROVE = "approve"
    #: 丟掉這一份、重新規劃：`review → completed`，規劃器整份重算。
    REJECT = "reject"


# 以下三組是 `{reason, detail}` 那一格的 `reason`（plan §6）：理由翻譯、原文不翻譯。
#
# **它們是 enum 而不是字串字面值**，因為前端要照每一種說出自己的下一步（PRODUCT 原則 4），
# 而它從 OpenAPI 取這份集合（`web/src/api/schema.d.ts`）。字串的時候前端只能自己抄一份，
# 後端加一種理由不會有任何東西紅——畫面上就少一句話（M2 票 02）。


class JobRefusal(StrEnum):
    """送單、重試或重新規劃在做出任何改變之前就停下來了（`services/jobs.py`、`services/plan.py`）。

    **qBittorrent 收不下不在這裡**：那時 Job 已經建好了，狀態是 `submit_failed` 加上原文，
    列上有一顆重試（plan §3.1）。這裡的每一種都是「還沒開始就停住」。
    """

    #: `tv:<tmdb>` / `movie:<tmdb>` 在 Berth 手上沒有對應的 Media。
    MEDIA_MISSING = "media_missing"
    #: 送單指定的 Route 不在了，或這一筆 Job 記著的那一條被刪了。
    ROUTE_MISSING = "route_missing"
    #: 劇集只進得了 tvshows 媒體庫、電影只進得了 movies（`collection_type_for`）。
    ROUTE_KIND_MISMATCH = "route_kind_mismatch"
    #: Route 停用中。
    ROUTE_DISABLED = "route_disabled"
    #: Route 上一次檢查是紅的——送出去也一定進不了庫。
    ROUTE_UNHEALTHY = "route_unhealthy"
    #: 索引站給不出那一份 torrent（連結過期、站台掛了）。
    SOURCE_UNAVAILABLE = "source_unavailable"
    #: 沒有這個 hash 的 Job。
    JOB_MISSING = "job_missing"
    #: 這個狀態不能重試（plan §3.1 只給 `submit_failed` 與 `import_failed`）。
    NOT_RETRYABLE = "not_retryable"
    #: 正在照著那一份計劃動檔案，重算會讓兩邊指向不同的地方（票 12）。
    NOT_REPLANNABLE = "not_replannable"
    #: 要向 qBittorrent 動手而它問不到。刪除範圍勾了「移除 torrent」時它是**先決條件**：
    #: 檔案刪了而 torrent 還在做種的話，下一次重新檢查就把整包再抓一遍。
    CLIENT_UNREACHABLE = "client_unreachable"
    #: 刪除範圍勾了「刪除 complete 檔案」卻沒勾「從 qBittorrent 移除 torrent」（brief §9.2）。
    #: 檔案在 torrent 底下被抽走時 qBittorrent 會報 `missingFiles`，而它下一次重新檢查就把
    #: 那幾個檔案再抓一遍——刪了等於沒刪，只多繞了一圈流量。
    DELETE_FILES_REQUIRES_REMOVE_TORRENT = "delete_files_requires_remove_torrent"


class RouteRefusal(StrEnum):
    """Route 設定頁與精靈第 7 步的一個命令做不下去（`services/routes.py`、票 14、14a）。

    前五種發生在建立的路上（媒體庫與路徑向 Jellyfin 現查），後四種是對既有的那一條動手時。
    """

    #: Jellyfin 上已經沒有這個媒體庫了。
    LIBRARY_MISSING = "library_missing"
    #: Berth 只寫入電影與劇集類型的媒體庫（`SUPPORTED_TYPES`）。
    LIBRARY_UNSUPPORTED = "library_unsupported"
    #: 目標必須是這個媒體庫回報的路徑之一（brief §4.1）。
    TARGET_NOT_IN_LIBRARY = "target_not_in_library"
    #: 那條路徑已經是另一條 Route 的寫入目標。
    TARGET_TAKEN = "target_taken"
    #: 現查的那一刻問不到 Jellyfin。
    JELLYFIN_UNREACHABLE = "jellyfin_unreachable"
    #: 沒有這個 id 的 Route，或檢查途中它被刪掉了。
    ROUTE_MISSING = "route_missing"
    #: 還有 Job 或帳本指著它。拒絕另帶 `jobs`、`ledger_entries` 兩個數字。
    ROUTE_IN_USE = "route_in_use"
    #: 從停用改成啟用，而檢查是紅的。
    ROUTE_UNHEALTHY = "route_unhealthy"
    #: 同一時間的建立撞上唯一索引。選擇本身沒錯，再按一次就好。
    ROUTE_CONFLICT = "route_conflict"


class AccessRefusal(StrEnum):
    """替 session 那個人讀寫 Jellyfin 時被擋下來（`services/jellyfin_access.py`，M1.5 票 03）。

    權限的判定全部在那一處，這裡是它攤給畫面的四種答案加上一種參數錯誤。**說得出理由的拒絕
    是答案不是故障**，所以前端拿到它就不重試（`retryUnlessRefused`）。
    """

    #: 帳號在 Jellyfin 被停用；Berth 已經刪掉他的每一張 session。
    ACCOUNT_DISABLED = "account_disabled"
    #: 這位使用者看不到這個媒體庫。**沒有權限與不存在是同一個回應。**
    LIBRARY_NOT_VISIBLE = "library_not_visible"
    #: 這位使用者看不到這個 item，或根本沒有這個 item。
    ITEM_NOT_VISIBLE = "item_not_visible"
    #: 問不到 Jellyfin。
    JELLYFIN_UNREACHABLE = "jellyfin_unreachable"
    #: 排序鍵不在這一種媒體庫的選單上（票 06）。前端照 `sorts` 畫選單，所以只有手改的
    #: 網址走得到；Jellyfin 自己對打錯的參數是靜靜換一種順序，所以由 Berth 擋。
    SORT_NOT_OFFERED = "sort_not_offered"


class IssueRefusal(StrEnum):
    """對一件 Issue 動手或按下對帳時，在做出任何改變之前就停下來了（M2 票 05）。

    **修復失敗不在這裡**：`relink_failed` 是例外——硬鏈接這一步真的碰了磁碟才知道成不成，
    而它的原文（`errno` 與哪兩個掛載）正是使用者要看的那一句，包成別的字串等於丟掉它
    （plan §8.6）。其餘每一種都是「還沒開始就停住」。
    """

    #: 沒有這個 id 的 Issue。
    ISSUE_MISSING = "issue_missing"
    #: 這一件已經處理過了（`resolved` / `ignored`）。多半是另一個分頁先按了。
    ISSUE_NOT_OPEN = "issue_not_open"
    #: 這一種 Issue 沒有這一顆（`ISSUE_ACTIONS`），或這一筆現在按不了它——「連 complete
    #: 一起刪」要有一筆還在的 Job，而重新入庫建出來的帳本沒有（`ledger.job_hash` 是弱引用）。
    ACTION_NOT_AVAILABLE = "action_not_available"
    #: 要重新鏈接，而 complete 裡那個來源檔也不在了。**兩邊都沒有就不是鏈接的事**，
    #: 使用者要按的是另外兩顆。
    SOURCE_MISSING = "source_missing"
    #: 鏈接真的做了但沒成（跨掛載、權限、目標被佔）。`detail` 是系統原文。
    RELINK_FAILED = "relink_failed"
    #: 要向 qBittorrent 動手而它問不到（「連 complete 一起刪」的先決條件，brief §9.2）。
    CLIENT_UNREACHABLE = "client_unreachable"
    #: 上一輪對帳還在跑。**不排隊**：排隊的那一輪看到的會是同一份磁碟（plan §3.2）。
    RECONCILE_RUNNING = "reconcile_running"


class PlanRefusal(StrEnum):
    """逐列改 Plan、核准或拒絕時，在做出任何改變之前就停下來了（M2 票 07）。

    **改動不合法是拒絕，不是默默接受**（票面驗收）：集數範圍反了、動作與檔案分類矛盾，後端都
    說得出是哪一種，畫面照它說下一步。`detail` 是那一列的檔名或那條撞上的路徑，不翻譯。
    """

    #: 沒有這個 id 的 Plan（多半是重新規劃把它換掉了，或那筆下載被刪了）。
    PLAN_MISSING = "plan_missing"
    #: 這一份已經不在等人了：另一個分頁先核准或拒絕了，或那筆下載已經離開 `review`。
    NOT_PENDING = "not_pending"
    #: 這份 Plan 裡沒有這個 id 的列。
    ITEM_MISSING = "item_missing"
    #: 這一列已經鏈接進媒體庫了；改它要拆舊鏈接，那是重新匹配的事（票 08）。
    ITEM_APPLIED = "item_applied"
    #: 這個處置與檔案的分類矛盾（`EDITABLE_ACTIONS`）：字型不會變成一集。
    ACTION_NOT_ALLOWED = "action_not_allowed"
    #: 劇集的一列要入庫，就要有季與起始集。
    EPISODE_REQUIRED = "episode_required"
    #: 迄集比起集小。
    EPISODE_RANGE_REVERSED = "episode_range_reversed"
    #: 季集只屬於劇集的入庫：電影、特典、略過、對不到都沒有季集可填。
    EPISODE_NOT_ALLOWED = "episode_not_allowed"
    #: 這份 Plan 沒有作品快照，算不出任何目標路徑，所以沒有東西寫得進媒體庫。
    MEDIA_MISSING = "media_missing"
    #: 兩列會寫到同一條路徑（brief §6.4 第 5 點）。`detail` 是那條路徑。
    TARGET_CLASH = "target_clash"
    #: 核准時還有列沒有決定：沒有提案的待審核列（光碟、推不出季集）。`detail` 是那幾個檔名。
    UNDECIDED = "undecided"


class RematchRefusal(StrEnum):
    """改一個檔案的處置（`POST /files/rematch`）或決定一個重複版本時，在改任何東西之前停下來了
    （M2 票 08）。

    `link_failed` / `unlink_failed` 是例外，理由同 `ReviewRefusal.UNLINK_FAILED`：要真的碰了磁碟才
    知道成不成，而那時**什麼紀錄都還沒改**——先鏈接、成了才拆舊的、都成了才寫帳本。
    """

    #: 沒有這一列帳本（多半是另一個分頁先改掉或撤銷了）。
    LEDGER_MISSING = "ledger_missing"
    #: 沒有這一個 Job 檔案。
    FILE_MISSING = "file_missing"
    #: 這個檔案現在不是「對不到」（另一個分頁先指派了，或它本來就入庫了——那要帶 `ledger_id`）。
    NOT_UNMATCHED = "not_unmatched"
    #: 這一筆的 Plan 還在等審核：那時候改它是 Plan 編輯的事（`PUT /plans/{id}/items`）。
    PLAN_PENDING = "plan_pending"
    #: 沒有這一列 Plan Item，或它不是（或已經不是）一個待決定的重複版本。
    NOT_DUPLICATE = "not_duplicate"
    #: 處置與檔案分類矛盾（`REMATCH_ACTIONS`）。
    ACTION_NOT_ALLOWED = "action_not_allowed"
    #: 劇集的指派要季號與起始集。
    EPISODE_REQUIRED = "episode_required"
    #: 結束集比起始集小。
    EPISODE_RANGE_REVERSED = "episode_range_reversed"
    #: 帶了季集，而這個處置（或這部電影）沒有季集可言。
    EPISODE_NOT_ALLOWED = "episode_not_allowed"
    #: 這個檔案不屬於任何一部作品，或那一部的快照不在了——算不出目標路徑。
    MEDIA_MISSING = "media_missing"
    #: 收它的 Route 不在了。
    ROUTE_MISSING = "route_missing"
    #: 目標路徑上已經有一個別的檔案（另一個來源的鏈接，或不是 Berth 放的）。Berth 不覆寫它。
    TARGET_TAKEN = "target_taken"
    #: 來源檔案不在了，或硬鏈接建不起來。`detail` 是系統原文。
    LINK_FAILED = "link_failed"
    #: 舊的那一條鏈接拆不掉。`detail` 是系統原文；新的那一條已經收回，帳本沒改。
    UNLINK_FAILED = "unlink_failed"


class ReviewRefusal(StrEnum):
    """確認或撤銷一個 audit 時，在做出任何改變之前就停下來了（M2 票 06）。

    `unlink_failed` 是例外，理由與 `IssueRefusal.RELINK_FAILED` 相同：移除要真的碰了磁碟才
    知道成不成，而它的原文（權限、路徑逃出 Route）正是使用者要看的那一句。那一次失敗時帳本
    那一列與 Job 都沒動——先拆鏈接、成了才改紀錄。
    """

    #: 沒有這個 id 的帳本列。多半是另一個分頁先撤銷了。
    LEDGER_MISSING = "ledger_missing"
    #: 這一列沒有 `audit` 旗標（已經被確認過，或本來就是 high）。
    NOT_AUDITED = "not_audited"
    #: 硬鏈接拆不掉。`detail` 是系統原文。
    UNLINK_FAILED = "unlink_failed"
