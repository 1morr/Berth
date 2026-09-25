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

    分成四種而不是一句錯誤訊息，是因為**下一步不同**：前兩種要使用者去精靈第 7 步處理憑證，
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
    #: poller 在客戶端看到這一筆好好的，把它從一個壞掉或失敗的狀態接回主幹（M3 票 02）：
    #: `from` 是原本的狀態（`submit_failed` / `missing_files` / `client_error` /
    #: `client_removed`），`state` 是接回的那一站，`client_state` 是 qBittorrent 當下怎麼說。
    #: 沒有人按按鈕——使用者在 qBittorrent 裡自己修好，或 `torrents/add` 逾時而其實收下了。
    RECOVERED = "recovered"
    #: 背景迴圈處理這一筆時撞到非預期的例外（`error` 是型別加原文；M3 票 02）。那一輪放棄、
    #: 下一輪再試；同一個錯誤不重寫——`Job.error` 還是它的話就是同一件事。
    ROUND_FAILED = "round_failed"


class JellyfinRequest(StrEnum):
    """`jellyfin_request_failed` 事件 payload 裡的 `request`：沒成的是哪一次請求。

    **只剩一種，仍然是封閉集合**（票 14b 拿掉了 `merge`）：畫面照它說出那一種失敗的下一步，
    而自由文字翻譯不了。下一種失敗加進來時，舊事件的 payload 不必改。
    """

    #: `POST /Library/Media/Updated`（plan §8.2 的 `notify_paths`）。
    SCAN = "scan"


class IssueType(StrEnum):
    """一件「要有人決定」的事是哪一種（brief §9.1、plan §2.4）。

    **十三種的聯集，一個封閉集合**（2026-09-22 定，M2 票 05；票 09c 加上最後兩種）：前五種
    是管線自己在路上發現的（M1 起寫 `issue_detected` 事件，M2 起同時寫一列 `issues`），中間
    六種是對帳比完四方之後才知道的，最後兩種是 `health_checker` 每 5 分鐘量出來的。三邊共用
    同一個集合，所以加一種型別而沒替它決定 `subject` 取哪一欄、或沒給它動作，紅的會是
    `SUBJECT_OF` 與 `ISSUE_ACTIONS` 那兩條閘門。

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
    #: 一條 Route 的 Jellyfin 媒體庫掛著 TVDB 的 metadata fetcher（brief §16.4 的警告）。
    #: Berth 照 TMDB 命名，TVDB 的季集編排可能與它不同（brief §10）。**`health_checker` 偵測**，
    #: 修法在 Jellyfin 的媒體庫設定裡，拿掉之後下一輪自己收掉。
    LIBRARY_USES_TVDB = "library_uses_tvdb"
    #: incomplete 或 complete 根目錄所在的檔案系統剩下的空間低於 `DiskSettings.min_free_gb`。
    #: 硬鏈接入庫不佔空間，會把磁碟吃滿的是下載。同上，空出來之後下一輪自己收掉。
    LOW_DISK_SPACE = "low_disk_space"


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
    # **一條 Route 一件**（2026-09-23 使用者拍板）：用它的目標路徑。一個媒體庫掛兩條 Route 時
    # 會有兩件，但 Route 才是 Berth 管的東西，畫面也說得出是哪一條。
    IssueType.LIBRARY_USES_TVDB: IssueSubject.PATH,
    # 量的那個根目錄（incomplete 或 complete）。兩者在同一個檔案系統上時只量一次，只有一件。
    IssueType.LOW_DISK_SPACE: IssueSubject.PATH,
}


class IssueAction(StrEnum):
    """resolve 一件 Issue 時按的那一顆（brief §9.1 的「預設建議動作」那一欄）。

    **「忽略」不在這裡**：它對每一種型別都按得了，而且不碰磁碟也不碰帳本（`ignore_issue`）。

    「認領」類的三顆（`adopt` / `claim_torrent` / `claim_file`）是票 10 加的：它們用的正是那一張
    票的原語（目錄版 `reimport` 與 `rebuild-ledger` 的反查），不另開入庫的路。管線那三種
    （`missing_files` / `client_error` / `client_removed`）的動作是票 09c 加的。
    """

    #: 重新鏈接：來源還在 complete，照帳本那一列再硬鏈接一次。
    RELINK = "relink"
    #: 承認刪除並清帳本：那個檔案本來就該不在，把帳本那一列刪掉。
    FORGET = "forget"
    #: 連 complete 一起刪：這一筆下載整個不要了。走 `delete_job` 的四個旗標（票 04），
    #: 不是另一套刪除（plan §11.3 決定 4）。
    DELETE_COMPLETE = "delete_complete"
    #: 標記為「已無來源」：媒體庫那一份保留，帳本那一列改成 `source_missing`——對帳之後就
    #: 不再為它開 Issue（那是使用者的決定，同刪除範圍只勾「刪 complete 檔案」的結果）。
    MARK_SOURCELESS = "mark_sourceless"
    #: 以硬鏈接取代：媒體庫裡那一份（複製品）換成來源的硬鏈接。**只在大小一致時給**
    #: （brief §9.1）：大小不同多半是被轉碼過，換掉等於丟掉別人的成品。
    REPLACE_WITH_LINK = "replace_with_link"
    #: 刪掉 complete 裡那個沒人認領的目錄（整棵）。按下去那一刻再確認一次它仍然沒人認領。
    DELETE_ORPHAN = "delete_orphan"
    #: 重新規劃：Job 退回 `completed`，規劃器照現在的檔案重算一份並入庫（brief §9.1 的
    #: 「重新 planning」）。
    REPLAN = "replan"
    #: 重新反查：那一列帳本重新排進 `jellyfin_resolver`，六次從頭算。
    RELOOK = "relook"
    #: 重新掃描媒體庫：先請 Jellyfin 跑「重新掃描媒體庫」，再重新反查（brief §20.1：路徑通知
    #: 對從沒掃到過內容的媒體庫無效）。
    RESCAN = "rescan"
    #: 重新 recheck：請 qBittorrent 重新開始並重新校驗那一包（`start` 在前、`recheck` 在後，
    #: brief §20.2），Job 回到 metadata 到手之後那一站，由 poller 照常往前推（plan §3.1）。
    RECHECK = "recheck"
    #: 承認遺失：那一包的檔案就是沒了。Job 走刪除範圍四個旗標**全不勾**進 `removed`
    #: （2026-09-23 使用者拍板）——磁碟與 qBittorrent 都不動，時間線一筆 `deleted`。
    ACCEPT_LOSS = "accept_loss"
    #: 重試：請 qBittorrent 重新開始那一包（`torrents/start`，4.x 叫 `resume`），它會清掉錯誤
    #: 狀態。Job 同 `recheck` 回到 metadata 到手之後那一站。
    RETRY = "retry"
    #: 重新送單：照存下來的下載連結再加一次（同 `submit_failed` 的重試，plan §3.1）。
    RESUBMIT = "resubmit"
    #: 承認移除：torrent 是使用者自己在 qBittorrent 上拿掉的。與 `accept_loss` 同一個做法。
    ACCEPT_REMOVAL = "accept_removal"
    #: 重新入庫（adopt）：complete 裡那個沒人認領的目錄當成一筆重新入庫的 Job，走目錄版
    #: `reimport`。**要帶作品**（管理員按下去時選，2026-09-23 拍板）：沒有作品的 Plan 只會停在
    #: review 而且核准不了。
    ADOPT = "adopt"
    #: 認領（建 Job 並解析）：替 qBittorrent 上那一筆建 Job，交給 poller 與規劃器。同樣要帶作品。
    CLAIM_TORRENT = "claim_torrent"
    #: 認領進帳本：單一檔案的 `rebuild-ledger`——配得上的長回一列，配不到的拒絕、那一件照舊開著。
    CLAIM_FILE = "claim_file"


#: 逐型別按得了哪幾顆，**順序就是畫面上的順序**（第一顆是 brief §9.1 的預設建議動作）。
#:
#: **要涵蓋整個 `IssueType`**（`tests/unit/test_issue_types.py` 守著）。空 tuple 是誠實的
#: 答案：那一種只按得了「忽略」——健康檢查那兩種永遠是空的，它們的修法不在 Berth 裡，條件解除時
#: 由系統收掉（票 09c）。
ISSUE_ACTIONS: dict[IssueType, tuple[IssueAction, ...]] = {
    IssueType.LIBRARY_LINK_MISSING: (
        IssueAction.RELINK,
        IssueAction.FORGET,
        IssueAction.DELETE_COMPLETE,
    ),
    IssueType.SOURCE_MISSING: (IssueAction.MARK_SOURCELESS,),
    # 「否則列出等人決定」（brief §9.1）：大小不同時這一顆不給，由 `_actions` 看 `same_size`。
    IssueType.INODE_MISMATCH: (IssueAction.REPLACE_WITH_LINK,),
    # 重新入庫排第二：brief §9.1 那一欄的順序是「刪除 / 重新入庫」。
    IssueType.ORPHAN_COMPLETE: (IssueAction.DELETE_ORPHAN, IssueAction.ADOPT),
    IssueType.UNKNOWN_TORRENT: (IssueAction.CLAIM_TORRENT,),
    # **永不刪**（brief §9.1）。`ACTION_DELETES` 與 `test_issue_types.py` 守著這一格裡沒有
    # 任何一顆會刪東西。
    IssueType.UNMANAGED_LIBRARY_FILE: (IssueAction.CLAIM_FILE,),
    IssueType.JOB_WITHOUT_FILES: (IssueAction.REPLAN,),
    IssueType.MISSING_FILES: (IssueAction.RECHECK, IssueAction.ACCEPT_LOSS),
    IssueType.CLIENT_ERROR: (IssueAction.RETRY,),
    IssueType.CLIENT_REMOVED: (IssueAction.RESUBMIT, IssueAction.ACCEPT_REMOVAL),
    IssueType.JELLYFIN_ITEM_UNRESOLVED: (IssueAction.RELOOK, IssueAction.RESCAN),
    IssueType.LIBRARY_USES_TVDB: (),
    IssueType.LOW_DISK_SPACE: (),
}

#: 按下去會不會刪掉磁碟上的東西。**要涵蓋整個 `IssueAction`**（`test_issue_types.py` 守著）：
#: 加一顆新的而沒回答這一題，`unmanaged_library_file`「永不刪」那一條就守不住了。
#:
#: 「以硬鏈接取代」算刪：被換掉的那一份複製品就沒了，只是大小一樣。
ACTION_DELETES: dict[IssueAction, bool] = {
    IssueAction.RELINK: False,
    IssueAction.FORGET: False,
    IssueAction.DELETE_COMPLETE: True,
    IssueAction.MARK_SOURCELESS: False,
    IssueAction.REPLACE_WITH_LINK: True,
    IssueAction.DELETE_ORPHAN: True,
    IssueAction.REPLAN: False,
    IssueAction.RELOOK: False,
    IssueAction.RESCAN: False,
    IssueAction.RECHECK: False,
    # 兩顆「承認」讓那一筆下載結束，但刪除範圍的四個旗標全不勾：一個位元組都不動。
    IssueAction.ACCEPT_LOSS: False,
    IssueAction.RETRY: False,
    IssueAction.RESUBMIT: False,
    IssueAction.ACCEPT_REMOVAL: False,
    # 認領類三顆只加東西：新的 Job、新的鏈接、新的帳本列。
    IssueAction.ADOPT: False,
    IssueAction.CLAIM_TORRENT: False,
    IssueAction.CLAIM_FILE: False,
}

#: 這幾顆要管理員選一部作品才按得下去（`POST /issues/{id}/resolve` 的 `media`，票 10）。
#: 沒有作品的 Job 進規劃器只會整份停在 review（`no_media`），而 Review Queue 核准不了它。
NEEDS_MEDIA: frozenset[IssueAction] = frozenset({IssueAction.ADOPT, IssueAction.CLAIM_TORRENT})


class ClaimMiss(StrEnum):
    """媒體庫裡的一個檔案**配不上**帳本的理由（`rebuild-ledger` 與「認領進帳本」，M2 票 10）。

    配不上的一律不猜（plan §11.3 決定 9）：變成一件 `unmanaged_library_file`，理由寫在
    `detail_json.reason`，畫面照它說下一步。宣告順序就是檢查的順序。
    """

    #: 不在任何一條 Route 的目標底下——Berth 沒有資格說它是誰的。
    OUTSIDE_ROUTES = "outside_routes"
    #: complete 裡沒有一個檔案與它同一個 inode：它是一份複製品，或來源早就刪了。
    NO_SOURCE = "no_source"
    #: 作品資料夾名說不出是 TMDB 上的哪一部（沒有 `[tmdbid-…]`，或 TMDB 問不到）。
    UNKNOWN_WORK = "unknown_work"
    #: 路徑照命名模板讀不回來（`naming.read_target`）：不是 Berth 寫的名字，或那一集的名字改過了。
    NOT_BERTH_NAMING = "not_berth_naming"


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
    #: Jellyfin 裡反查過的那幾條（M2 票 09 加的第五方）。它不開 Issue，只把帳本記著的 item
    #: 換成 Jellyfin 現在的樣子：票 13 之前反查完的劇集補上 Series id，Jellyfin 12 合併版本
    #: 之後換掉不再是主條目的 item id（brief §20.9）。問不到一樣跳過並說出來。
    JELLYFIN = "jellyfin"


class LedgerStatus(StrEnum):
    """一筆帳本現在與磁碟對不對得起來（plan §2.3 的 `ledger.status`、brief §9.1）。

    importer 寫下的一律是 `ok`。`target_missing` 與 `inode_mismatch` 是 Reconciler 比對之後寫的；
    `source_missing` 與 `unlinked` 是**使用者決定過的現況**（刪除範圍、「標記為已無來源」），
    對帳看到它們就不再為那一列開 Issue——偵測時寫的話，「忽略」之後下一輪就再也不會問了。
    """

    OK = "ok"
    TARGET_MISSING = "target_missing"
    SOURCE_MISSING = "source_missing"
    INODE_MISMATCH = "inode_mismatch"
    #: 刪除範圍的「移除鏈接」拆掉的（M3 票 01）。磁碟上與 `target_missing` 一樣是目標不在，
    #: 差別只在有人決定過：對帳不再為它開 `library_link_missing`。
    UNLINKED = "unlinked"


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
    #: 同一張海報、兩倍寬：`srcset` 的第二個寬度，給高密度螢幕與手機兩欄的格子（M2 票 13）。
    POSTER_LARGE = "poster_large"
    #: 16:9 的橫圖，繼續觀看與下一集的一格（票 07）。
    WIDE = "wide"
    #: 同一張橫圖、兩倍寬（M2 票 13）。
    WIDE_LARGE = "wide_large"


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
    畫面要把人送回精靈第 6 步（「來源」那一格），不是叫他重試。
    """

    #: 精靈第 6 步跳過了，或連線資訊是空的。一個請求都不必發（plan §9.3 第 6 步）。
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
    """精靈第 5 步對一個 Route 跑的檢查（plan §9.5、brief §4.4）。順序即宣告順序，
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


#: 精靈第 6 步「替 Prowlarr 介面設登入」那一條纜繩的 key（plan §9.3 第 6 步）。
#: **不與 `IndexerKind.PROWLARR` 同名**：那一條與站接不接得上無關，混在一起會讓「這一步
#: 做完了沒」把一條永遠存在的憑證步驟當成「至少接上了一個站」。
PROWLARR_LOGIN_STEP = "prowlarr_login"


class IndexerKind(StrEnum):
    """第 6 步接索引站的兩種方式（plan §8.4、§9.3 第 6 步）。"""

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
    #: 連得上、是對的服務，但它說自己還在載入（Jellyfin 啟動中的 503，票 06g）。
    STARTING = "starting"
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
    #: 發佈時間與換算出的那一集的播出日對不上（M3 票 14，`parser.airing`）：季號、offset 或絕對編號
    #: 多半算錯了。下一步是改季集（從這裡套用到整個 RSS Series 在票 14b）；BD 版晚發這種對的也會
    #: 落在這裡，那時核准就好。
    AIR_DATE_CONFLICT = "air_date_conflict"
    #: mediainfo 量到的片長與 TMDB 那一集的片長差太多（M3 票 15，`parser.runtime`）：多半是 SP、
    #: OVA 或兩集合併的檔案被當成了一集正片。下一步是改那一列的處置或季集；片長其實沒錯的核准就好。
    RUNTIME_CONFLICT = "runtime_conflict"


class ReviewKind(StrEnum):
    """Review Queue 上一列是哪一種事（plan §6 review 群組，2026-09-22 定）。

    M2 開頭定了五種，雖然票 06 只填 `audit` 與 `issue`：佇列的排序與畫面的分組都照這幾種定
    （`REVIEW_PRIORITY`），後面兩票只是把列填進去，不改形狀。**`issue` 在 M3 票 05 拿掉**（brief
    §19 2026-09-24）：Issue 只在 `/issues`，這一頁是「入庫要人決定」的那幾種。
    """

    #: 低信心的 Plan，逐檔可改（票 07）。
    PLAN = "plan"
    #: medium 自動入庫、等人確認的檔案（CONTEXT.md 的 Audit）。
    AUDIT = "audit"
    #: 對不到的檔案（票 08）。
    UNMATCHED = "unmatched"
    #: Tags 完全相同的兩個版本（票 08）。
    DUPLICATE = "duplicate"


#: 佇列的排序鍵：**需要人動手的排前面**（plan §6）。`plan` 與 `unmatched` 不處理就卡著一筆
#: 下載；`audit` 與 `duplicate` 已經在媒體庫裡，只是等人看一眼。同一級之內舊的在前。
REVIEW_PRIORITY: dict[ReviewKind, int] = {
    ReviewKind.PLAN: 0,
    ReviewKind.UNMATCHED: 0,
    ReviewKind.AUDIT: 1,
    ReviewKind.DUPLICATE: 1,
}


class AuditReason(StrEnum):
    """`audit` 那一類的理由（`GET /review` 每一列的 `reason.code`）。

    **封閉集合**（同 `JellyfinRequest`）：理由是給畫面挑句子的 code，不是後端
    拼好的一句話（M2 票 06）。解析器那幾句英文的 `reasons` 是原文，放在列上的 `notes`。
    """

    #: 信心是 medium，而這條 Route 允許 medium 自動入庫（brief §6.5）。
    MEDIUM_AUTO_IMPORTED = "medium_auto_imported"
    #: RSS Series 的第一批：信心不論高低都等人看一眼季號與集數（brief §15，M3 票 13）。
    FIRST_BATCH = "first_batch"


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
    #: 這一筆不能重新入庫（`services/jobs.reimportable`）：還在下載、還在規劃或入庫中的那一份不能
    #: 從頭再來，送單都還沒成的那一筆 complete 裡什麼都沒有，沒下載完就被移除的那一筆 complete 裡
    #: 只有殘件（M2 票 10）。
    NOT_REIMPORTABLE = "not_reimportable"
    #: 重新入庫的 Import Source（complete 裡那一包）不在了，或裡面一個檔案都沒有。
    #: 什麼都還沒動：沒有檔案可以規劃，退回 `completed` 只會得到一份空的 Plan（M2 票 10）。
    CONTENT_MISSING = "content_missing"
    #: 按下去之後這一筆被別處改過了（另一個分頁剛刪掉它、背景迴圈剛推進它）：它按下去時看到的
    #: 狀態已經不是現在的狀態，compare-and-set 輸了。什麼都還沒動，重新看一次再決定（M3 票 01）。
    MOVED_ON = "moved_on"
    #: incomplete 根目錄所在的檔案系統剩下的空間低於 `DiskSettings.min_free_gb`（M3 票 04）。
    #: RSS 送單沒有人按確認，所以這個門檻不只開 `low_disk_space` Issue，也擋送單；`0` 是不量。
    LOW_DISK_SPACE = "low_disk_space"
    #: 這個 hash 有一筆刪除過、紀錄還在的 Job（`removed`，M3 票 04）。`detail` 是那一筆的 hash。
    #: 紀錄還在就是還沒決定要不要再下載：重新入庫或連紀錄一起刪掉之後再送，都要管理員。
    JOB_REMOVED = "job_removed"
    #: 這一筆停在審核，而按的人不是管理員（M3 票 04）。在 `review` 重算會丟掉管理員逐列改過、
    #: 撤銷過的那一份，而審核本來就是管理員的事（plan §6）。其他狀態的重算照舊誰都按得了。
    REVIEW_NEEDS_ADMIN = "review_needs_admin"


class RouteRefusal(StrEnum):
    """Route 設定頁與精靈第 5 步的一個命令做不下去（`services/routes.py`、票 14、14a）。

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


class BundledLibraryRefusal(StrEnum):
    """套件內 Jellyfin 的媒體庫清單存不下來（`services/jellyfin.py`、M3 票 06f）。

    精靈的剖面在送出之前就用同一組規則擋（`web/src/setup/libraryRules.ts`），這裡是後端
    那一份。每一種都指得出是哪一列（`row`），清單本身是空的那一種除外。
    """

    #: 一列都沒有：精靈要建至少一個媒體庫，第 5 步才有 Route 可建。
    EMPTY = "empty"
    NAME_MISSING = "name_missing"
    #: 名稱重複（不分大小寫）。Jellyfin 不拒絕同名，會長出 `Movies2`（brief §20.7）。
    NAME_TAKEN = "name_taken"
    FOLDER_MISSING = "folder_missing"
    #: 資料夾重複（不分大小寫：Windows 與 macOS 的檔案系統不分）。兩個媒體庫會掃同一個目錄。
    FOLDER_TAKEN = "folder_taken"
    #: 資料夾是 `library_root` 底下的一層：有 `/`、`\`、或是 `.`、`..` 就跳出去或往下鑽了。
    FOLDER_OUTSIDE_ROOT = "folder_outside_root"
    #: 資料夾裡有 Windows 不收的字元（`<>:"|?*`、控制字元，brief §4.5）。
    FOLDER_CHARACTERS = "folder_characters"
    #: 已經在 Jellyfin 建好的那一列被改了或刪了。那一列要去 Jellyfin 改（票 06f）。
    BUILT_CHANGED = "built_changed"


class AccessRefusal(StrEnum):
    """替 session 那個人讀寫 Jellyfin 時被擋下來（`services/jellyfin_access.py`，M1.5 票 03）。

    權限的判定全部在那一處，這裡是它攤給畫面的四種答案加上一種參數錯誤。**說得出理由的拒絕
    是答案不是故障**，所以前端拿到它就不重試（`retryUnlessRefused`）。
    """

    #: 帳號在 Jellyfin 被停用或刪除（M2 票 11）；Berth 已經刪掉他的每一張 session。
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
    #: 要刪的那個 complete 目錄現在有主了（qBittorrent 上某個 torrent、Berth 的某一筆 Job 或
    #: 帳本上的一列指著它）。偵測與按下去之間隔了一段時間，而刪錯的代價是別人正在做種的資料。
    IN_USE = "in_use"
    #: 要以硬鏈接取代，而媒體庫那一份與來源現在大小不一樣了（多半是被轉碼覆蓋）。
    SIZE_DIFFERS = "size_differs"
    #: 要請 Jellyfin 掃描媒體庫而它問不到（或它沒有那個排程任務）。
    JELLYFIN_UNREACHABLE = "jellyfin_unreachable"
    #: 刪除真的做了但沒成（權限、唯讀掛載）。同 `relink_failed`，`detail` 是系統原文。
    DELETE_FAILED = "delete_failed"
    #: 重新送單時，存下來的下載連結拿不回同一個 torrent（索引站的代理連結過期了、或它現在
    #: 給的是另一個 hash）。什麼都還沒動。
    SOURCE_UNAVAILABLE = "source_unavailable"
    #: 重新送單真的送了，qBittorrent 不收（409 / 415）。同 `relink_failed`，`detail` 是原文；
    #: 那一筆現在是 `submit_failed`，這一件仍然開著、再按一次就是再送一次。
    RESUBMIT_FAILED = "resubmit_failed"
    #: 重新送單時那一筆的 Route 用不了（被刪了、停用了、紅著、改收別種作品）：送出去也入不了庫。
    #: 與第一次送單同一組前提（`services/jobs.check_route`）。
    ROUTE_UNUSABLE = "route_unusable"
    #: 認領類的兩顆要帶一部作品，而這一次沒帶、或 Berth 在 TMDB 上找不到它（票 10）。
    MEDIA_REQUIRED = "media_required"
    #: 「認領進帳本」配不上（`ClaimMiss`，`detail` 是那一種的值）。那一件照舊開著（票 10）。
    UNCLAIMABLE = "unclaimable"


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
    #: 「套用到這個 RSS Series」而這一份不是 RSS Series 送的（或那個 Series 已經刪了，M3 票 14b）。
    NOT_FROM_SERIES = "not_from_series"
    #: 「套用到這個 RSS Series」而檔名讀不出集號：算不出 offset（同 `RematchRefusal` 的那一種）。
    NO_EPISODE_NUMBER = "no_episode_number"


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
    #: 要「套用到這個 RSS Series」，而這個檔案不是 RSS Series 送的（或那個 Series 不在了）。
    #: M3 票 13。
    NOT_FROM_SERIES = "not_from_series"
    #: 要套用到 RSS Series，而檔名讀不出集號：沒有原本的集號就算不出 offset。`detail` 是檔名。
    NO_EPISODE_NUMBER = "no_episode_number"


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


class FeedKind(StrEnum):
    """Feed 是哪一站的 RSS（plan §2.4、§8.5）。每一種一個 adapter（`adapters/rss/`）。

    只列**已經有 adapter** 的那幾種（generic 之後）。加 Feed 時由網址的主機認出來
    （`services/rss.kind_of`），認不出來的是 `feed_unsupported`。
    """

    MIKAN = "mikan"
    #: 搜尋 feed 與使用者 feed（M3 票 11）。
    NYAA = "nyaa"
    #: 搜尋 feed（M3 票 11）。
    ACGRIP = "acgrip"


class FeedItemStatus(StrEnum):
    """一筆 Feed Item 走到哪了（`CONTEXT.md`、plan §2.4）。

    `new`（還沒比對）沒有建：一筆 Item 寫下的那一刻就已經認出 RSS Series、看過排除條件，
    沒有「還沒比對」這一段（M3 票 10）。
    """

    #: 它的 RSS Series 還沒綁到作品：留著不送，綁定之後才送（brief §15）。
    UNBOUND = "unbound"
    #: Series 綁好了，還沒送成（上一次送單被拒時 `error` 是原文，下一輪再送）。
    MATCHED = "matched"
    #: 送出去了，`job_hash` 是那一筆。
    DOWNLOADED = "downloaded"
    #: 排除條件擋下了（`skip_json` 說哪一層的哪一條）。寫下的那一刻看，或規則收緊時看還沒送的
    #: 那幾筆；放寬規則不把它放回來（brief §15）。
    EXCLUDED = "excluded"
    #: 去重擋下了：同一個 torrent 已經送過、或帳本已有同一個版本（`skip_json` 說是哪一種）。
    DUPLICATE = "duplicate"
    #: 新 Feed 的第一輪選了「只追之後的」：選的那一刻已經在 feed 裡的，不送（brief §15、M3 票 11）。
    PASSED = "passed"


class PrimeMode(StrEnum):
    """新 Feed 的第一輪預覽選了哪一個（brief §15「補舊集」最後一句、M3 票 11）。"""

    #: 全部下載：第一輪留著的照一般規則送（綁好的當場送，待綁定的綁定之後送）。
    ALL = "all"
    #: 只追之後的：選的那一刻已經在 feed 裡的都不送，之後才出現的照一般規則送。
    LATER = "later"


class RssRefusal(StrEnum):
    """`/rss` 的一個命令在做出任何改變之前就停下來了（`services/rss.py`、M3 票 08）。

    綁定之後的送單被拒**不在這裡**：綁定本身成立，那幾筆 Feed Item 留在 `matched` 帶著原文，
    下一輪輪詢再送（`.scratch/m3/rss-shape.md` §3）。
    """

    #: 沒有這個 id 的 Feed。多半是另一個分頁先刪了。
    FEED_MISSING = "feed_missing"
    #: 網址不是認得的來源（`mikanani.me`、`nyaa.si`、`acg.rip`），或根本不是 http(s) 網址。
    FEED_UNSUPPORTED = "feed_unsupported"
    #: 同一個網址已經是一個 Feed 了。
    FEED_DUPLICATE = "feed_duplicate"
    #: 沒有這個 id 的 RSS Series。
    SERIES_MISSING = "series_missing"
    #: 這個 RSS Series 已經綁在一部作品上。要換作品先解除綁定。
    SERIES_BOUND = "series_bound"
    #: `tv:<tmdb>` / `movie:<tmdb>` 在 Berth 手上沒有對應的 Media（畫面先打 `GET /media/{id}`
    #: 讓它長出來，資料夾名才有得預覽）。
    MEDIA_MISSING = "media_missing"
    #: 指定的 Route 不在了。
    ROUTE_MISSING = "route_missing"
    #: Route 停用中。
    ROUTE_DISABLED = "route_disabled"
    #: 劇集只進得了 tvshows 媒體庫、電影只進得了 movies（`collection_type_for`）。
    ROUTE_KIND_MISMATCH = "route_kind_mismatch"
    #: 一條排除條件寫壞了（空白、正則編譯不過、不認得的旗標）。`detail` 是 `<規則>: <原因>`，
    #: 原因是 Python `re` 的原文。儲存時就擋，不等到輪詢時才炸（M3 票 10）。
    RULE_INVALID = "rule_invalid"
    #: 這個 Feed 的第一輪已經選過了（另一個分頁先選了）。
    FEED_PRIMED = "feed_primed"
    #: 「只追之後的」當場讀不到 feed：不知道「之前」是哪幾筆，就不決定。`detail` 是原文。
    FEED_UNREACHABLE = "feed_unreachable"
    #: 這個 Feed 還沒讀過，不收「全部下載」：沒看過的東西不讓人選（M3 票 11）。
    FEED_UNREAD = "feed_unread"
