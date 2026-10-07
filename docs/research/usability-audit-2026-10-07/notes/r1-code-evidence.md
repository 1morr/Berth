# Berth 程式碼蒐證（main `107708c`，2026-10-07）

更新對象：`docs/research/wizard-audit-2026-10-06.md`（`5f3717f`）的 §A1、§B3、§C1、§3.2、§3.3、「文件與實作不符」、改進清單。
方法：只讀碼與讀票，沒有開瀏覽器、沒有跑測試。**讀碼確認**的不加註；**推論**的明寫「推論」。縮寫：`A/` = `berth/adapters/`、`S/` = `berth/services/`、`AJ`/`AQ`/`AP` = `A/jellyfin/client.py`、`A/qbittorrent/client.py`、`A/prowlarr/client.py`。

**先講一件和審計對象有關的事實**：GHCR 的 `:latest` / `:0.1.0` 是 tag `v0.1.0` = `6bc4c1d`（我用匿名 `tags/list` 再確認：`0.1.0-rc1`、`0.1.0`、`0.1`、`latest`）。之後 `git log v0.1.0..HEAD` 有 **15 個 commit**，票 43–54 全在其後。所以**現在拉 `:latest` 的人拿不到**：頁 3 套件內自動跑（43）、頁 4 一鍵加站（44）、只存驗過的憑證與欄位錯誤（45）、頁 2 的 `/data` 探針（46）、換台列遺留物（47）、多季一包解析（48）、搜尋年份類型篩（49）、健康頁沿用結論（50）、作品頁先問 Jellyfin（51）、套件內 Jellyfin 名稱「Berth」（52）、文案修正（53、54）。而 main 上的 README / brief 描述的是含這些的行為（`CHANGELOG.md:7` `[Unreleased]` 還沒收版）。

---

## 1. 接管表

### 1.0 讀法

- 「來源」：套件內（compose 起的 `berth-*`）/ 既有（使用者自己的）。
- 「撤回（Berth 裡）」= Berth 有沒有任何程式路徑可以把它還原；「撤回（服務裡）」= 使用者自己在該服務做的方法。
- Berth 對 Jellyfin / qBittorrent / Prowlarr 的 HTTP 寫入**全部**經 `A/jellyfin/client.py`、`A/qbittorrent/client.py`、`A/prowlarr/client.py` 三個檔（我逐一 grep `request("POST"|"PUT"|"DELETE")`）；TMDB 只有 `GET`（`A/tmdb/client.py:107`，`"GET"` 寫死）。

### 1.1 Jellyfin

| # | 東西 | 來源 | 實際請求（程式位置） | 為什麼 | 觸發 | 撤回（Berth 裡） | 撤回（服務裡） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| J1 | 伺服器語言 / 地區 / metadata 語言；套件內另加 **ServerName = `Berth`** | 套件內（那台沒初始化）、既有（只在那台沒初始化；**不送 ServerName**，Jellyfin 會把它清成空字串） | `POST /Startup/Configuration`（`AJ:92-107`；`ServerName` 只在非 None 時帶：`AJ:105-106`）；呼叫 `S/jellyfin.py:861-872`；名稱常數 `BUNDLED_SERVER_NAME` | Jellyfin 初始精靈第 1 步；名稱避免用戶端顯示容器 ID（票 52） | 頁 1 的 `bootstrap`，且 `self.fresh` | 不能 | Jellyfin 控制台「一般」 |
| J2 | 預設使用者（`GET /Startup/User` 會把它建出來）、管理員帳號 | 同上 | `GET /Startup/User`（`AJ:109-111`，有寫入副作用）、`POST /Startup/User`（`AJ:113-119`，403 當「已設過」）；`S/jellyfin.py:874-888` | 擁有者 = Jellyfin 管理員（brief §11） | 同上 | 不能 | Jellyfin 使用者管理 |
| J3 | 遠端存取（預設關） | 同上 | `POST /Startup/RemoteAccess`（`AJ:121-124`）；`S/jellyfin.py:920-924` | 初始精靈步驟 | 同上 | 不能 | Jellyfin 控制台 |
| J4 | 初始精靈標記完成 | 同上 | `POST /Startup/Complete`（`AJ:126-127`）；`S/jellyfin.py:926-930` | 同上 | 同上 | 不能 | — |
| J5 | **API key「Berth」** | 兩種 | `POST /Auth/Keys?app=Berth`（`AJ:169-170`）；先 `GET /Auth/Keys` 找，找到就不建（`S/jellyfin.py:932-` `_api_key`、`_find_api_key` 982） | Berth 之後所有 Jellyfin 呼叫都用這把 | 頁 1 登入；key 被撤後重新登入會再建一把 | **不能**（整個 repo 沒有刪 key 的呼叫） | Jellyfin「API 金鑰」頁刪（Berth 偵測到會請你重新登入換一把） |
| J6 | 媒體庫（Movies / TV / Anime 等清單上的） | **只有套件內** | `POST /Library/VirtualFolders?name&collectionType&paths&refreshLibrary=false`，body 的 `LibraryOptions`：`Enabled`、`PathInfos`、metadata 語言與國家、**`EnableRealtimeMonitor: false`**、`SeasonZeroDisplayName: "Specials"`、`TypeOptions`（metadata fetcher 預設 `TheMovieDb`，image fetcher 取自該台可用清單）（`AJ:196-209`、`AJ:627-646`；`S/jellyfin.py:124-127`、`:890-918`）。同時 `ensure_directory(/data/library/<folder>)`（`S/jellyfin.py:908`） | 套件內沒有媒體庫 | 頁 3 | 不能（Berth 沒有刪媒體庫；建好的在 Berth 裡鎖住） | Jellyfin 刪 |
| J7 | 既有媒體庫上**加一條 Berth 路徑** `/data/library/<slug>` | 既有（程式不擋套件內，但 UI 只給既有；`add_berth_paths` 只 `_require_choice`，`S/jellyfin.py:495-,1042-1045`） | `POST /Library/VirtualFolders/Paths?refreshLibrary=false`（`AJ:211-217`）；呼叫 `S/jellyfin.py:603`（`_add_berth_path` 566-）。**先** `ensure_directory`（594）→ 寫探測檔 → `POST /Environment/ValidatePath`（`AJ:219-231`）→ **看得到才加**；看不到就收回剛建的空目錄、不加 | 舊路徑不動、不換項目 ID（觀看紀錄不歸零） | 頁 3 `POST /setup/jellyfin/libraries/paths`（`api/setup.py:608`） | **不能**（無移除路徑的呼叫）。注意：只要 Jellyfin 看得到就加，**之後的 qBittorrent / 硬鏈接檢查失敗也照樣留著** | Jellyfin 媒體庫設定移除路徑 |
| J8 | 登入（`AuthenticateByName`），每次 Berth 使用者登入與精靈第 1 步 | 兩種 | `POST /Users/AuthenticateByName`，標頭 `Client=Berth, Device=Berth, DeviceId=berth-server`（`AJ:40-45`、`AJ:142-157`、`AJ:497-510`）；`S/auth.py:161-181` | Berth 沒有自己的密碼，帳密交給 Jellyfin 驗 | 每次登入 | 不存 token；整個 repo **沒有** `Sessions/Logout`（grep 無） | **推論**：Jellyfin 會替這個 DeviceId 留一筆裝置 / 存取 token（Jellyfin 的慣例，我沒在它的原始碼確認）；使用者在 Jellyfin「裝置」頁可見 |
| J9 | **通知路徑已變更** | 兩種 | `POST /Library/Media/Updated`，每路徑 `UpdateType=Created`（`AJ:250-255`）；呼叫 `S/importer.py:573`（入庫、rematch，連**已拆掉的**路徑也送）、`S/resolver.py:546`（反查沒找到就再通知） | 讓 Jellyfin 認到新檔 | 每次入庫；resolver 退避 | 不適用（無狀態） | — |
| J10 | **觸發整個 Jellyfin 的「掃描媒體庫」排程任務** | 兩種 | `GET /ScheduledTasks` → `POST /ScheduledTasks/Running/{id}`（`AJ:233-246`；`A/jellyfin/__init__.py:599-616` `scan_libraries`）。呼叫者：`S/resolver.py:547-549`（同一批反查沒找到 ≥ 2 次，`SCAN_AFTER_MISSES = 2`，`resolver.py:71`）與 `S/issues.py:563`（Issue「重新掃描媒體庫」鍵） | 對從沒掃到過內容的媒體庫，路徑通知無效（brief §20.1） | 自動（resolver）與人按 | 不適用 | — **全域動作，會掃使用者在既有 Jellyfin 的所有媒體庫**；見 1.8 #1 |
| J11 | 標已看 / 未看（寫進**該使用者**在 Jellyfin 的紀錄） | 兩種 | `POST` / `DELETE /UserPlayedItems/{id}?userId=`（`AJ:368-379`）；`S/jellyfin_access.py:378`、`api/jellyfin.py:291` | 媒體庫頁的標記鍵 | 使用者按（標未看前端先確認） | 再標一次；對劇集會**遞迴**每一集、未看會清觀看次數（`S/jellyfin_access.py` docstring） | Jellyfin 自己 |
| J12 | 其餘 | — | 全是 `GET`（`public_info`、`libraries`、`items`、`user_views`、`image` 等） | — | — | — | — |

### 1.2 qBittorrent

| # | 東西 | 來源 | 實際請求 / 檔案（程式位置） | 為什麼 | 觸發 | 撤回（Berth 裡） | 撤回（服務裡） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Q1 | 免密白名單（只放 Berth 的 IP `/32`） | 套件內，容器啟動前 | `deploy/preseed/qbittorrent/10-berth.sh:25-27`（`WebUI\AuthSubnetWhitelistEnabled=true`、`WebUI\AuthSubnetWhitelist=${BERTH_IP}/32`），**鍵不存在才補**（`has_key` 40、寫入 68）；`BERTH_IP` 由 compose 傳（`docker-compose.yml` `x-berth-ip` 172.28.0.2） | 4.6.1 起首次密碼只印 log，Berth 進不去 | 容器每次啟動 | 不適用 | 改 `qBittorrent.conf` 或 WebUI「驗證」勾選（鍵一旦存在、值被改，重啟**不會**補回，票 53 實跑確認） |
| Q2 | WebUI 帳號與密碼 | **只有套件內**（`_refuse_existing`，`S/qbittorrent.py:332-336`；既有走 `_apply_password` 的 `origin is not BUNDLED` → `SKIPPED`，不寫，`:338-` ） | `POST /api/v2/app/setPreferences`，表單 `json`；**密碼先、帳號後，各一次**（`S/qbittorrent.py:378-379`；`AQ:105-115`）。鍵只有 `web_ui_password`、`web_ui_username`（`S/qbittorrent.py:67-68`） | 沒設的話 WebUI 只剩 log 裡每次重啟都換的臨時密碼 | 頁 2「設定介面登入」/ 自動沿用 | 只能再設一組蓋過；兩次之間斷線會留「舊帳號＋新密碼」（票 26、54 不修） | WebUI 偏好 |
| Q3 | **全域偏好**（save path、autoTMM…） | — | **不寫**。`setPreferences` 的呼叫端只有上面那兩行（grep `set_preferences` 在 `berth/` 非 adapters 只有 `S/qbittorrent.py:378-379`）。閘門：`tests/integration/test_qbittorrent_login_only.py`（票 32） | 不影響 Berth | — | — | — |
| Q4 | **分類 `berth-<slug>`**（save path = `/data/torrent/complete/<slug>`、`downloadPathEnabled=true`、`downloadPath` = `/data/torrent/incomplete/<slug>`） | 兩種 | `POST /api/v2/torrents/createCategory`（`AQ:134-146`）；經 `ensure_category`（`A/qbittorrent/__init__.py:419-451`）：**先讀、不存在才建、同名不同路徑回報衝突、不覆寫**。**程式裡沒有 `editCategory`**（grep `editCategory` 全 repo 無）。呼叫者 `S/routes.py:1059`（Route 檢查）與 **`S/jobs.py:1102`（每次送單）** | 路徑開在分類上、`autoTMM=true` | 頁 3 建 Route；**每次送單若分類被刪就悄悄重建** | 見 Q5 | qBittorrent 刪分類 |
| Q5 | 移除分類 | 兩種 | `POST /api/v2/torrents/removeCategories`（`AQ:148-151`）；`S/leftovers.py:73-92` `remove_empty_categories`（`@command(IRREVERSIBLE)`） | 換台時一鍵清 | 使用者在換台確認框按 | **只刪「現在那台上 `berth-` 開頭、而且 0 個 torrent」的分類**，判準是**名字前綴**不是 Berth 記得建過的（`S/leftovers.py:77-92`、白名單 `ALLOWED` 同樣只比前綴）；目錄不刪 | — |
| Q6 | **送單：torrent** | 兩種 | `POST /api/v2/torrents/add`：`category=berth-<slug>`、**`tags=berth`**、`contentLayout=Original`、`autoTMM=true`、`paused/stopped=false`，不送 `savepath`（`A/qbittorrent/__init__.py:122-142`、`AQ:154-185`）。呼叫 `S/jobs.py:1112` | Berth 的下載 | 使用者送單 / RSS | 刪 Job：`torrents/delete`，**`deleteFiles=false`**（`AQ:224-241`、`S/deletion.py:248`） | qBittorrent 刪 |
| Q7 | **探針 torrent**（頁 2：放 `/data` 本身、校驗不完；頁 3：放 `complete/<slug>`） | 兩種 | `torrents/add`（`AQ:187-215`：`savepath` 明送、`autoTMM=false`、**不掛分類、不帶 tag**、停住、名字 `.berth-probe-*.torrent`）→ `torrents/recheck`（`AQ:243-246`）→ `finally: torrents/delete deleteFiles=false`（`A/qbittorrent/__init__.py:513-542`）。呼叫：頁 2 `S/setup.py:764-785`、頁 3 `S/routes.py:1096-1116` | qBittorrent 沒有「這條路徑你看不看得到」的 API | 頁 2 連線測試、頁 3 每次建立並檢查、設定頁「重新檢查」；**健康迴圈刻意不跑**（會觸發「完成時執行外部程式」） | 自清；`finally` 的 delete 失敗會殘留（票 54 不修，使用者決定要不要補刪） | 手動刪（停住、無分類、無 tag） |
| Q8 | 重新校驗 / 開始 | 兩種 | `torrents/recheck`、`torrents/start|resume`（`AQ:243-254`）；`S/issues.py:608-610`（`missing_files` / `client_error` 的 Issue 按鈕，先 `start` 再 `recheck`） | 修復 Berth 自己的 Job | 使用者按 | — | — |
| Q9 | 登入 session | 兩種 | `POST /api/v2/auth/login`（`AQ:65-`）；套件內靠白名單免密 | — | 每次連 | — | — |

### 1.3 Prowlarr

| # | 東西 | 來源 | 實際請求（程式位置） | 為什麼 | 觸發 | 撤回（Berth 裡） | 撤回（服務裡） |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | **讀** API key | 套件內 | Berth 容器**唯讀**掛 `${CONFIG_ROOT}/prowlarr:/ext/prowlarr:ro`（`deploy/docker-compose.yml:63`），讀 `<ApiKey>`（`A/prowlarr/config_file.py:20-48`；路徑 `berth/config.py:56-59`）。環境變數 `PROWLARR__AUTH__APIKEY` 優先 | 零輸入 | 每次進頁 4 | 不適用（唯讀） | — |
| P2 | **站**（加） | 兩種 | `POST /api/v1/indexer`：schema 的定義原樣送回，只換 `appProfileId` 與 `enable=true`（`AP:85-103`）；`S/indexer.py:553-585`（`_ensure_indexer`，加在 574；已存在的只做 `POST /indexer/test`，不重加）。可加的限 `_offered`：推薦清單、或「公開 + torrent」（`S/indexer.py:845-852`） | 搜尋要站 | 使用者勾選加入 / 套件內一鍵（`add_recommended_indexers`，票 44） | 套件內可單站移除（P3）；既有不移除 | Prowlarr 刪站 |
| P3 | **站**（刪） | **只有套件內**（`S/indexer.py:507` 對既有 `raise ValueError`） | `DELETE /api/v1/indexer/{id}`（`AP:133-134`）；`S/indexer.py:494-530`（`remove_indexer`）。**只擋 `not _offered(gone)`（514）**；UI 的 `removable = bundled and _offered(row)`（`S/indexer.py:936`） | 加錯 / 不要的站 | 使用者按 | **能刪任何「公開 torrent 站」或推薦站，不論是誰加的**（docstring 自己寫「不論是誰加的」）；與 brief「Berth 加的站」措辭不同，見 1.8 #5 | — |
| P4 | **介面登入（forms）** | **只有套件內**（`S/indexer.py:659` 對既有 `raise ValueError`） | `GET /api/v1/config/host` → **整份物件原樣 + 5 個欄位**（`authenticationMethod=forms`、`authenticationRequired=enabled`、`username`、`password`、`passwordConfirmation`）`PUT /api/v1/config/host/{id}`（`AP:142-146`；`S/indexer.py:757`）；Prowlarr 隨即**自行重啟**，Berth 輪詢 `/ping` 等回來（`:770-` `_wait_for_restart`） | 沒設的話 Prowlarr 第一次開會強迫設 | 頁 4 / 設定頁 | 只能再設一組 | Prowlarr 設定 |
| P5 | 測試站 | 兩種 | `POST /api/v1/indexer/test`（`AP:105-131`）。Prowlarr 會**對外連該站**；不留物件 | 先測再加（票 09） | 頁 4「測試」 | — | — |
| P6 | 搜尋 | 兩種 | `GET /api/v1/search`、`GET /api/v1/indexer`（`A/indexer/prowlarr.py:46-66`）。是讀，但會讓 Prowlarr 對外打每一站 | 作品頁搜 torrent | 使用者 | — | — |

### 1.4 TMDB / 自己的 DB

| 東西 | 內容（程式位置） |
| --- | --- |
| TMDB | 只 `GET`（`A/tmdb/client.py:107`）。key 由使用者貼，**測過才存**（票 45：`api_key_present` 與 `verified` 同真同假）。`.env` 的 `TMDB_API_KEY` **Berth 不讀**（`.env.example:34-36` 自己說） |
| Berth 對自己 DB 寫的秘密 | 全部在 `${CONFIG_ROOT}/berth/berth.db`（`berth/config.py:51-53`），**沒有應用層加密**（README〈秘密與備份〉、brief §16.2） |

Berth 自己 DB 裡的秘密（`settings` 表一列一分組，值是 JSON，`berth/models/setting.py`）：

| 秘密 | 形式 | 位置 |
| --- | --- | --- |
| Jellyfin API key | **明文** | `JellyfinSettings.api_key`（`setting.py:48-52`） |
| 既有 qBittorrent 的帳號與密碼 | **明文**（套件內留空，靠白名單） | `QbittorrentSettings`（`:79-85`） |
| Prowlarr API key | **明文** | `IndexerSettings.api_key`（`:87-92`） |
| TMDB key | **明文** | `TmdbSettings.api_key`（`:95-100`） |
| Berth 替套件內 qBittorrent 設的介面帳號 + 密碼 | 帳號明文、密碼**加鹽 scrypt 雜湊**（`n=2^14,r=8,p=1`，`S/steps.py:62-72`） | `SetupQbittorrent.web_ui_username/_password_hash`（`setting.py:308-309`） |
| 同上，Prowlarr | 同上 | `SetupIndexer`（`:338-339`） |
| 擁有者的 Jellyfin 密碼 | 不存**明文**；但勾「沿用 Jellyfin 帳密」時上面兩個雜湊**就是擁有者密碼的雜湊**（`steps.py:62-72` docstring 自己這樣說）。README 寫「密碼只交給 Jellyfin，Berth 不存」 | — |
| RSS Feed 網址 | **明文**，Mikan 聚合 feed 的 token 就在網址裡（`models/rss.py:36-38`） | `rss_feeds.url` |
| Berth session cookie | 只存 `sha256` 雜湊（`S/auth.py:152` `token_digest`；`models/auth.py:36`） | `sessions.token_hash` |
| Jellyfin 使用者 token | **不存**（登入時換 session 就丟；整個 repo 沒有存 `AccessToken`） | — |

### 1.5 Berth 對**磁碟**（`/data` = `DATA_ROOT`）做的事

這些不是 HTTP 寫入，白名單測試看不到（見 1.9），brief §16.4 物件表也只列了一部分。

| 動作 | 程式位置 | 說明 |
| --- | --- | --- |
| 建 `/data/library/<folder>`（套件內媒體庫） | `S/jellyfin.py:908` → `A/fs.py:53` | 不存在才建 |
| 建 Route 的 `complete/<slug>` 與 `incomplete/<slug>` | `S/routes.py:1054-1055` | Route 檢查第一條就建 |
| 建既有媒體庫的 Berth 路徑目錄 `/data/library/<slug>` | `S/jellyfin.py:594` | Jellyfin 看不到就收回剛建的空殼（`:599-` 之後、`remove_empty_directories`） |
| 探測檔 `.berth-probe-<8hex>`（點開頭，Jellyfin 不當媒體） | `A/fs.py:231-247`（`PROBE_PREFIX` 在 `:35`）。**四處**：頁 2 在 `/data` 根（`S/setup.py:777`，內容兩片）、頁 3 在 `complete/<slug>`（`S/routes.py:1105`）、頁 3 在 Route 目標（`:1150`）、加 Berth 路徑時在新路徑（`S/jellyfin.py:599`） | 離開區塊就刪；崩潰才可能殘留（推論：程序被殺時 `finally` 不跑；沒有啟動時掃除） |
| 硬鏈接測試（暫時檔 → `os.link` → 比 inode → 兩邊都刪） | `A/fs.py:271-288`；`S/routes.py:1161-1175` | `complete/<slug>` → Route 目標 |
| **入庫的硬鏈接** | `A/fs.py:158-193`（`os.link`，**失敗不退回複製**，EXDEV 時說兩邊在哪個掛載）；`S/importer.py:332-350` | 每次入庫 |
| **刪檔** | `A/fs.py:94-115`（`remove`，單檔、守衛在 `roots`）、`:118-`（`remove_tree`，只給 `orphan_complete` Issue 的「刪除孤兒」） | 都是使用者在 Issue / 刪除範圍按了才做；不在 Route 根底下一律 `PathEscapeError` |
| 容器入口 `chown` | `deploy/entrypoint.sh:42`（`/config` 遞迴）、`:46-49`（**`/data` 只在是空目錄時**才 chown，非遞迴） | 其餘不碰 |

### 1.6 暫時物件與殘留條件（彙整）

| 物件 | 在哪 | 什麼時候會殘留 | 現在有沒有處理 |
| --- | --- | --- | --- |
| 探針 torrent（停住、無分類、無 tag） | 使用者的 qBittorrent | `finally` 內 `delete_torrent` 丟例外（答完之後那一下斷線） | **不修**（票 54 第 1 條；失效條件寫得出、兩條補救代價大於效益，「要不要補刪由使用者決定」） |
| `.berth-probe-*` 檔 | `/data` 根、`complete/<slug>`、Route 目標 | 程序被殺（推論） | 沒有啟動時清除 |
| 5.x qBittorrent 的「加入時執行外部程式」 | 使用者在 qBittorrent 設的 hook | 頁 2、頁 3 探針各觸發一次（實測，brief §20.2；校驗不完的探針不觸發「完成時執行」） | 畫面上有說（票 46） |
| 空的 `berth-*` 分類、目錄 | qBittorrent、磁碟 | 刪 Route 不刪分類；換台只有確認框的鍵能刪空分類 | 部分（票 47）；目錄永不刪 |
| 加進舊媒體庫的 Berth 路徑 | Jellyfin | 一律留 | 不處理 |
| 「原帳號＋新密碼」 | 套件內 qBittorrent | `setPreferences` 兩次之間斷線 / 帳號被拒 | 不修（票 54 第 2 條） |
| 換台時 Berth 在舊 qBittorrent / Prowlarr 留的東西 | 舊那一台 | 一律 | 列出（票 47）；只能刪空分類 |

### 1.7 容器掛載（接管面）

`deploy/docker-compose.yml`：berth 掛 `${CONFIG_ROOT}/berth:/config`、`${DATA_ROOT}:/data`、`${CONFIG_ROOT}/prowlarr:/ext/prowlarr:ro`（60-63）；qbittorrent 掛 `config`、`/data`、`./preseed/qbittorrent:/custom-cont-init.d:ro`（87-89）；jellyfin 掛 `config`、`/data`（110-111）；**prowlarr 只掛 `/config`（125），沒有 `/data`**。

### 1.8 文件與程式不一致（逐條）

| # | 文件寫的（位置） | 程式實際 | 嚴重度 |
| --- | --- | --- | --- |
| 1 | brief §16.4 物件表、`CONTEXT.md:105-115` 的「Berth 擁有的物件」清單沒有：**Jellyfin 全域「掃描媒體庫」任務**（J10）、**`/Library/Media/Updated`**（J9）、**qBittorrent 的 `berth` tag**（Q6）、**每次送單的 `ensure_category`**（Q4：分類被刪會悄悄重建）、**Jellyfin 的登入裝置**（J8，推論） | 全部真的會送 | **出乎意料的寫入**；其中 J10 動到使用者在既有 Jellyfin 的所有媒體庫 |
| 2 | brief §16.4、README 等多處：「Berth 只**建立與管理 Berth 擁有的物件**，不動使用者原有的……站」 | 套件內 Prowlarr 的 `remove_indexer` / `removable` 以「公開 torrent 站或推薦站」為準（`S/indexer.py:514,936`），**不看是不是 Berth 加的**。使用者自己在 Prowlarr 加的公開站，在 Berth 設定頁也按得到移除 | 與「接管＝只管 Berth 擁有的」矛盾；`added_sites`（票 47）只用在「列出」 |
| 3 | `tests/integration/test_setup_owned_writes.py` 的 `ALLOWED`（`delete_indexer` 的 `holds = w.args[0] in made.sites`）+ brief §16.4 閘門段 | 只是**測試走的那一條路**（刪 Berth 剛加的）才成立；程式本身沒有這個限制（同 #2） | 閘門比程式嚴；閘門沒守住實際行為 |
| 4 | `CONTEXT.md:115`（Existing service）列「檢查用的暫時探測 torrent 與探測檔」 | 屬實，但探針 torrent 頁 2 放在 **`/data` 根目錄本身**（不是分類目錄），是 `.berth-probe-*` 直接落在使用者 `DATA_ROOT` 最上層（`S/setup.py:777`）；README / brief 沒說 | 低 |
| 5 | README:9「Berth 加 qBittorrent、Jellyfin、Prowlarr，**四個容器掛同一個媒體根**」；`deploy/.env.example:4`「四個容器都掛這一個目錄」；brief §16.1「四者掛同一個 `/data`」 | compose 只有 **berth、qbittorrent、jellyfin 三個**掛 `/data`；prowlarr 沒有（`docker-compose.yml:118-130`） | 低但三處都錯；對「既有」使用者其實沒差，只是說法不實 |
| 6 | README〈部署〉：「**密碼只交給 Jellyfin，Berth 不存**」 | 勾「沿用 Jellyfin 帳密」時 DB 存的是擁有者密碼的 scrypt 雜湊（`S/steps.py:62-72`、`setting.py:308-309,338-339`）。不是明文，但不是「不存」 | 措辭 |
| 7 | brief §16.4 物件表「探測 torrent 自清（Berth 中途崩潰、或答完之後移除那一下斷線時可能殘留）」 | 屬實（票 54 補進去） | 一致 |
| 8 | brief §16.4「媒體庫上的 Berth 路徑：頁 3 的檢查失敗也留著」 | **半對**：Jellyfin 看不到時**不加**、收回空目錄（`S/jellyfin.py:598-` 之後）；只有加進去**之後**才失敗的檢查（qBittorrent 看不到、EXDEV）才留著 | 低；說法應限定 |
| 9 | brief §16.4 開頭「全域偏好不寫」、README〈外部服務的前提〉 | **一致**（`set_preferences` 只剩兩個登入鍵） | 一致 |
| 10 | brief §16.3「預置只補設定檔裡沒有的鍵」 | 一致（`10-berth.sh:40-50`） | 一致 |
| 11 | README:159 / brief §16.1「原生 Linux 宿主與 NAS 還沒有人跑過」 | 仍是事實（票 42 `needs-info`） | 一致 |
| 12 | 先前審計 §A1 BTH 2 列「寫三個全域鍵…（`S/qbittorrent.py:72-76,408-409`）」 | **已過時**：票 32 後只剩登入兩鍵；**§A1 BTH 2 整列、§B3「qBittorrent 三個全域鍵」列、§C1「同一台主機…」之外的所有 `save_path` 敘述都要改** | 更新審計時處理 |
| 13 | 先前審計 §A1 BTH 4 列：既有「只讀 `system/status`、indexer 清單…不碰登入、不移除站」 | 仍成立；套件內多了一鍵加站（`add_recommended_indexers`） | 更新 |
| 14 | `S/jellyfin.py` 的 `add_berth_paths` 沒有「只限既有」的程式守衛（只 `_require_choice`），白名單 `ALLOWED` 也對兩種來源都放行（`test_setup_owned_writes.py:226`）；文件說「既有只加路徑、套件內建媒體庫」 | UI 不會對套件內送，但 API 打得動 | 低（推論：沒 repro） |

### 1.9 `tests/integration/test_setup_owned_writes.py` 的白名單對照

**宣稱**（檔頭 1-15、brief §16.4 閘門段）：整個精靈經 API 跑一輪套件內、兩輪既有（Jellyfin 初始化過 / 還沒），三台**替身**收到的每個寫入都要對上 `ALLOWED`；既有那輪 bootstrap 只放行「那台 Jellyfin 還沒初始化」；範圍外：預置白名單、掛載的 key、探測檔自清。

**實際守的**（讀碼確認）：

- `WRITES`（`:52-84`）= adapter 介面上會改狀態的方法；`READS` 列其餘；`test_every_adapter_method_is_either_a_read_or_a_write`（`:773` 附近）逼新增的方法要分類。
- `ALLOWED`（`:243-300`）的條件：`create_api_key` 只能 `app=="Berth"`；`add_library_path` 在 `library_root` 底下；`create_category` 名稱 `berth-` 前綴、save path 在 `complete_root`、download path 在 `incomplete_root`；`remove_categories` 全 `berth-` 前綴；`add_probe` 在 `complete_root` 底下，或剛好是 `shared_root` 且 `unfinished`；`recheck` / `delete_torrent` 只能對 `made.probes` 且 `delete_files is False`；`add_indexer` 的定義在使用者勾的清單；`delete_indexer` 只能 `made.sites`（僅套件內）；`create_library` 在 `library_root` 底下（僅套件內）；bootstrap：`start_configuration`（`server_name` 只准「新的套件內那台」）、Jellyfin 四個初始精靈方法、`set_preferences` 只准兩個登入鍵、`set_host_config` 只准 5 個登入欄位。
- 變異驗證都在檔內（`test_an_extra_global_preference…`、`test_naming_a_jellyfin…`、`test_the_fresh_jellyfin_exception…`、`test_a_probe_on_the_shared_root…`、`test_removing_a_category_that_is_not_berths…`、`test_unrelated_names_and_address_formatting_stay_green`）。

**漏洞 / 範圍落差**（讀碼確認，除註明）：

| # | 落差 | 影響 |
| --- | --- | --- |
| G1 | **只走精靈的 API**（`walk_bundled` `:501`、`walk_existing` `:533`）。執行期寫入 `add_torrent`、`notify_paths`、`run_task`（J10）、`start`、`mark_played`、非探針的 `recheck` / `delete_torrent` 雖然在 `WRITES` 分類裡，但**沒有 ALLOWED 列、也沒有任何一輪走到它們**；所以「Berth 只管自己擁有的物件」只對**設定流程**有閘門，執行期（送單、入庫、反查、Issue 修復）沒有 | 出乎意料寫入 J9、J10、Q6 的 tag、Q4 的重建都不在閘門裡 |
| G2 | **替身不是真服務**：記的是 `Fake*Client` 的方法呼叫，看不到真實的 HTTP 路徑與參數；`add_torrent` 的 `tags=berth`、`setPreferences` 之外的表單欄位都不會被檢查 | `AQ:122-142` 的 `tags` 沒閘門 |
| G3 | **`READS` 裡有帶副作用的**：`authenticate`（J8，Jellyfin 會留裝置，推論）、`login`（qB session）、`test_indexer` / `test_definition`（Prowlarr 對外連站）、`validate_path` | 這些被當讀 |
| G4 | `delete_indexer` 的 `ALLOWED` 條件比程式嚴（1.8 #3） | 閘門可能給出「已守住」的錯覺 |
| G5 | `remove_categories` 的真實呼叫（`S/leftovers.py:91`）**沒有一輪走到**（`walk_*` 不打 `DELETE /setup/services/qbittorrent/leftovers/categories`；`grep leftovers` 在該檔只出現在白名單列與合成 `Write`，`:72,258,735`）；另有 `tests/integration/test_setup_leftovers.py` 守它的行為（我沒讀內容） | 白名單列靠合成輸入驗，不是靠真實路徑 |
| G6 | **完全不在範圍**：磁碟（1.5 全表）、預置腳本（Q1）、Prowlarr config.xml 讀取（P1）、Berth 自己 DB | 與檔頭 / brief 的聲明一致（brief 有寫），但 1.5 的磁碟面沒有任何測試守 |
| G7 | 套件內與既有共用 `ALLOWED`，`add_library_path` 對套件內也放行（1.8 #14） | 低 |
| G8 | `Allowed(PROWLARR, "add_indexer", … in p.ticked)` 只比 `definition_name` 在勾選清單，不驗 `_offered` | 低 |

結論：**閘門名實大致相符於它自己的聲明（精靈流程、三個 adapter 的狀態改變、不含磁碟與預置）**；但「接管＝只管 Berth 擁有的物件」這句話，**閘門只保證設定流程**。

---

## 2. 目錄樹

### 2.0 規則（程式位置）

- 容器內路徑固定，沒有設定可改：`PathSettings`（`berth/models/setting.py:104-114`）：`incomplete_root=/data/torrent/incomplete`、`complete_root=/data/torrent/complete`、`library_root=/data/library`。宿主側只由 `.env` 的 `DATA_ROOT`、`CONFIG_ROOT`（`deploy/.env.example`；預設 `./data`、`./config`，相對於 `deploy/`）。
- **slug**：`library_slug(name)`（`S/jellyfin.py:1070-1079`）：把 `<>:"/\|?*` 與控制字元換 `-`，空白（連同貼著它的 `-`）換 `-`，去頭尾 ` .-`，**轉小寫**，中日文照留，空了回 `berth`。
  - 套件內：Route 的 slug 取自**清單上的資料夾名**（目標路徑最後一段，`S/routes.py:892-894`，票 31）；預設 `movies` / `tv` / `anime`。
  - 既有：取自**媒體庫名稱**（`S/routes.py:894` 的 `library.name`）；Berth 路徑 = `<library_root>/<slug>`（`berth_path`，`S/jellyfin.py:1091-1104`；已經以舊 slug 加過的不改名）。
  - 撞名接 `-2`（`_unique_slug`，`S/routes.py:941-949`）。
- 分類 `berth-<slug>`；save path = `complete/<slug>`（`save_path_of`，`:1320`），未完成 = `incomplete/<slug>`（`incomplete_path_of`，`:1326`）。
- 作品資料夾：`{title} ({year}) [tmdbid-{id}]`；沒年份 `{title} [tmdbid-{id}]`（`berth/naming/__init__.py:19-21`）。標題 `sanitize` 且整個名字上限 200 位元組（`:61`）。
  - 電影檔名：`<作品資料夾名> - <tags>.<ext>`（`:111-124`；**檔名開頭必須與資料夾名一字不差含 `[tmdbid-…]`**，否則 Jellyfin 當成兩部）。
  - 劇集檔名：`{title} ({year}) - S01E01[-E02][ - {集名}][ {tags}].{ext}`，在 `Season 01/` 底下（`:83-108`；季資料夾 `Season NN`，Specials 是 `Season 00`；**劇集檔名沒有 `[tmdbid-]`**）。集名取 TMDB 快照，缺或 `Episode 5` 這種佔位就省略（`:176-197`）。
  - tags：`[<來源>][<解析度>][<字幕語言>][Hardsub]?[<組>][<v2>][<edition>]`，缺的省略（`berth/domain/parser.py:474-506`；來源 `BD|WEB|DVD|HDTV|REMUX`，語言 `CHS|CHT|JP|EN`）。
  - 動畫：**與劇集同一套模板**（沒有任何動畫專屬命名；它只是 `Anime` 媒體庫、`tvshows` 類型）。
  - 特典：`<作品資料夾>/extras/<原檔名>`；字幕：`<影片主幹>.<token>.<lang>.<ext>`（`:127-155`、`:157-164`）。
- 硬鏈接：**來源** = qBittorrent 完成後在 `complete/<slug>/<torrent 內容根>/...`（`contentLayout=Original`，`A/qbittorrent/__init__.py:104`）→ **目標** = Route 的 `target_path` + 上面的相對路徑；`os.link`，失敗**不退回複製**（`A/fs.py:158-193`）。**兩邊都在 `/data` 底下 = 同一個 bind mount、同一個檔案系統**。

### 2.1 套件內（三個服務都選套件內，預設清單）

```
宿主 DATA_ROOT（預設 deploy/data；Windows 例 C:\Berth\data）        容器內
├── .berth-probe-xxxxxxxx                       ← 頁 2 探針檔，用完即刪（S/setup.py:777）      /data/.berth-probe-…
├── torrent/
│   ├── incomplete/                             ← 分類的 downloadPath（下載中），qBittorrent 寫
│   │   ├── movies/        ← 分類 berth-movies 的未完成目錄（Berth 先建：S/routes.py:1055）
│   │   ├── tv/            ← berth-tv
│   │   └── anime/         ← berth-anime
│   └── complete/                               ← 分類的 savePath（完成後 qBittorrent 搬到這），硬鏈接來源
│       ├── movies/  Night.of.the.Living.Dead.1968.720p…/（torrent 內容根，Original）
│       ├── tv/      Some.Show.S01.1080p…/ E01.mkv, E02.mkv …
│       └── anime/   [LoliHouse] Anime - 05 [WebRip 1080p].mkv（單檔就直接是檔案）
└── library/                                    ← Jellyfin 媒體庫的父目錄（library_root）
    ├── movies/                                 ← Jellyfin 媒體庫「Movies」（movies 類型）
    │   └── Night of the Living Dead (1968) [tmdbid-10331]/
    │       └── Night of the Living Dead (1968) [tmdbid-10331] - [BD][720p][YTS.AM].mp4   ← 與 complete 裡那個檔同 inode
    ├── tv/                                     ← 「TV」（tvshows）
    │   └── Some Show (2020) [tmdbid-1234]/
    │       ├── Season 01/
    │       │   └── Some Show (2020) - S01E01 - Pilot [WEB][1080p][CHT][Group].mkv
    │       └── extras/ …
    └── anime/                                  ← 「Anime」（tvshows）
        └── 葬送的芙莉蓮 (2023) [tmdbid-209867]/
            └── Season 01/
                └── 葬送的芙莉蓮 (2023) - S01E05 [WEB][1080p][CHT][LoliHouse].mkv

宿主 CONFIG_ROOT（預設 deploy/config）
├── berth/          ← berth:/config          berth.db（+WAL）。entrypoint 對它 chown -R（entrypoint.sh:42）
├── qbittorrent/    ← berth-qbittorrent:/config   qBittorrent/qBittorrent.conf（預置腳本 10-berth.sh 只補兩個白名單鍵）
├── jellyfin/       ← berth-jellyfin:/config      Jellyfin 的資料庫與設定（推論：linuxserver 的標準 /config 內容）
└── prowlarr/       ← berth-prowlarr:/config      config.xml（內含 <ApiKey>）；同一個目錄**唯讀**掛進 berth:/ext/prowlarr
```

（注：`complete/` 與 `incomplete/` 的實際子目錄在第一次「建立並檢查」時才出現；`library/*` 在頁 3 建媒體庫時出現。`movies` 一例的檔名 tags 取自審計 S6 實跑的 `Night of the Living Dead (1968) [tmdbid-10331] - [BD][720p][YTS.AM].mp4`。）

### 2.2 既有 Jellyfin / qBittorrent（使用者原本的 `/tv`、`/downloads`，只多掛一條 `/data`）

使用者的宿主（舉例，沿用 README〈選「既有」的條件〉）：

```
/volume1/media/tv/            ← 使用者原有的電視庫（Jellyfin 容器內 /tv；Berth 不掛、不讀、不寫）
/volume1/downloads/           ← 使用者原有的下載（qBittorrent 容器內 /downloads；Berth 不用；舊 torrent 照常做種）
/volume1/berth/               ← DATA_ROOT，三個容器都**多掛**成 /data（berth、qbittorrent、jellyfin 同一個宿主目錄、同一個容器路徑）
├── torrent/
│   ├── incomplete/shows/                ← 例：既有 Jellyfin 的媒體庫叫「Shows」→ slug `shows` → 分類 berth-shows
│   └── complete/shows/<torrent 內容根>/
└── library/
    └── shows/                           ← Berth 路徑：被「加」到既有媒體庫「Shows」的第二條路徑（舊的 /tv 原地不動）
        └── Some Show (2020) [tmdbid-1234]/Season 01/Some Show (2020) - S01E01 [WEB][1080p][Group].mkv
```

既有 Jellyfin 的媒體庫 `Shows` 之後在 Jellyfin 裡的 `locations` 是 `['/data/library/shows', '/tv']`（票 36 實跑確認：`['/data/library/shows', '/tv']`）。Route 的目標預設是新的 Berth 路徑；**既有項目與 Berth 路徑同在一個 Jellyfin 媒體庫**，所以 Jellyfin 會把新舊並成同一個庫。Berth 對 `/tv` 與 `/downloads` 一個位元組都不寫（Route 檢查只驗寫入目標 `S/routes.py:1118-1143`）。

**既有 qBittorrent**：`berth-shows` 分類存 `savePath=/data/torrent/complete/shows`、`downloadPath=/data/torrent/incomplete/shows`（票 36 實跑：`berth-shows`）；全域 `save_path=/downloads`、`autoTMM` 不動。

### 2.3 每個掛載點：做什麼、誰看得到

| 宿主 | 容器路徑 | 誰看得到 | 做什麼 |
| --- | --- | --- | --- |
| `${DATA_ROOT}` | `/data` | **berth、berth-qbittorrent、berth-jellyfin**（prowlarr 沒有，`docker-compose.yml`） | `torrent/{incomplete,complete}/<slug>`（qBittorrent 寫、Berth 讀與刪孤兒）+ `library/<folder>`（Berth 硬鏈接寫、Jellyfin 讀）。硬鏈接兩端必須在這**同一個**掛載 |
| `${CONFIG_ROOT}/berth` | berth:`/config` | 只有 berth | `berth.db`（設定、秘密、帳本、Job） |
| `${CONFIG_ROOT}/qbittorrent` | berth-qbittorrent:`/config` | 只有 qbittorrent | `qBittorrent.conf`；Berth 看不到 |
| `${CONFIG_ROOT}/jellyfin` | berth-jellyfin:`/config` | 只有 jellyfin | Jellyfin 資料（備份重點，README〈版本與升級〉） |
| `${CONFIG_ROOT}/prowlarr` | berth-prowlarr:`/config` **與** berth:`/ext/prowlarr:ro` | prowlarr 讀寫；berth 唯讀 | `config.xml` 的 `<ApiKey>` |
| `deploy/preseed/qbittorrent` | berth-qbittorrent:`/custom-cont-init.d:ro` | 只有 qbittorrent | `10-berth.sh`，容器啟動前補白名單鍵 |

（`DATA_ROOT` 預設是**相對於 compose 檔的 `./data`**，所以預設值在 `deploy/data`；README 要使用者 `cd deploy` 才對。）

---

## 3. 功能現況

**分級**：**真**＝有真服務 e2e（`tests/e2e/`，真的 Jellyfin 12.1 / qBittorrent / Prowlarr 容器）或有人在真服務上實跑過的紀錄；**Fake**＝只有單元 / 整合（`FakeJellyfinClient` 等）或前端 e2e（`web/e2e/`，Fake 後端 `scripts/fake_setup_server.py`）；**無**＝沒做。

### 3.1 `tests/e2e/`（真服務）實際涵蓋

進入點 `uv run --env-file .env python -m tests.e2e.stack`（`tests/e2e/stack.py`），專案 `berth-e2e`、port 28xxx、子網 `10.231.0.0/16`，與使用者的試跑環境並存（票 34）；nightly `.github/workflows/e2e.yml`（cron `23 18 * * *` + `workflow_dispatch`）。**24 條測試**（票 52 實跑 `24 passed`）。

| 檔 | 測什麼（真服務上） |
| --- | --- |
| `conftest.py`（共用，不是測試但就是精靈的真服務走查） | 冷啟動：三個套件內服務選完照常每 2 秒重測到連上；頁 1 建管理員（拿 session、`/auth/me` 是 admin）；頁 2：5 字元密碼被拒（`login_rejected`、停在頁 2）、合規密碼過、換成既有再換回套件內只靠連線測試就到頁 3；全域 `save_path` 被改到別處後照常；頁 4：**既有 Prowlarr 錯 key = 400 `connection_failed`/`auth_required`、對的 key 從 `/ext/prowlarr/config.xml` 讀**；頁 5 TMDB 用真 key；頁 3 建 Route 6/6；**完成照頁序再驗**（停掉 qBittorrent → 422 指頁 2；收回頁 4 跳過 → 422 指頁 4）；最後以同組帳密登入 Berth |
| `test_1_m1_pipeline.py`（6 條） | 三筆送單（美劇一季、動漫一季、電影，`.torrent` 由 Berth 自己去抓）→ 不經人工走到 `imported`；全域 save path 不影響（票 32）；套件內 Jellyfin 名稱是 `Berth`（票 52）；帳本與語料對得上；入庫是硬鏈接（容器內 `stat` inode）；Jellyfin 的 item id 與帳本一致 |
| `test_2_m15_library.py`（6 條） | 一般使用者只看得到有權限的媒體庫（直接打網址也被拒）；不是 Berth 入庫的也在牆上；播放連結指向 Jellyfin 那一集；標已看寫進該使用者的 `UserData`；帳號停用 → session 結束；Jellyfin 停掉時牆說得出問不到 |
| `test_3_m2_repair.py`（5 條） | 在 Jellyfin 刪檔 → `library_link_missing` → 重新鏈接；複製品取代 → `inode_mismatch`；complete 來源被刪 → `source_missing`；沒人認領的目錄 → `orphan_complete` 刪除；整個 Anime 庫刪光 → `reimport` 回到同樣路徑與 inode |
| `test_4_m3_rss.py`（7 條） | Mikan 聚合 feed 自動綁定＋補舊集；acg.rip 搜尋訂閱第一輪（合集被排除）；split-cour 播出日對不上被擋；一次修正、其餘跟著；新集自動入庫＋同集多版本並存；已確認的 RSS Series 不進 audit 清單；Jellyfin 讀成不同季集 → Issue |

**e2e 的邊界（讀碼確認）**：
1. **下載是假的**：沒有 peer。位元組由測試從 staging **複製**到 qBittorrent 說的路徑再叫它 `recheck`（`tests/e2e/payload.py:1-21`、`test_1` 檔頭）。真 qBittorrent 的收尾、分類搬移、`contentLayout` 是真的；BitTorrent 傳輸不是。
2. **公開站是替身**：`tests/e2e/sites.py` 冒充 `mikanani.me` / `acg.rip` / `nyaa.si`（compose network alias + 測試 CA）。真站只在審計 S6 與票 44 手動碰過。
3. **Prowlarr 在 e2e 裡不加站、不搜**：`conftest.py:135-136` 把頁 4 `skip`；`test_1` docstring 寫「Prowlarr 在跑但沒被測到，索引站搜尋有自己的契約測試」。**所以頁 4 套件內「一鍵加站」「Prowlarr 介面登入」沒有 e2e**，只有票 44 的**手動**實跑（`berth-e2e-*` 上加了 dmhy、Anime Tosho、YTS、The Pirate Bay）。
4. **沒有既有 Jellyfin / 既有 qBittorrent 的 e2e**（`conftest.py` 的「既有」只是把套件內 qBittorrent 的位址當既有填一次、既有 Prowlarr 同理）；混用靠票 36 / 46 的**手動**實跑（`berth-qa-t36`、`t46`，已拆掉）。
5. **沒有頁 2 `/data` 探針、換台列遺留物、頁 3 自動跑的 e2e 斷言**（票 43、46、47 的證據是手動實跑與整合測試）。
6. `test_1_m1_pipeline.py:21-23` 的 docstring「精靈偵測得到它…按之後再說」是舊話（票 15 起不偵測），不影響行為。

### 3.2 `web/e2e/`（前端，Fake 後端）

`web/playwright.config.ts` 的情境：`bundled`、`mixed`、`starting`、`berth-only`、`healthy` 等，每條對 `scripts/fake_setup_server.py`。19 個 spec：`wizard`（精靈六頁走完＋同組帳密登入，含 390 寬）、`existing`（三頁選既有＋選寫入目標，含 390 寬）、`cold-start`、`compose-absent`、`settings`（精靈後 `/setup` 導向設定頁、加站試搜、改兩個介面登入、換 TMDB key）、`submit`（作品頁送單到已入庫）、`media-downloads`、`review`、`issues`（2）、`series-offset`、`series-offset-held`、`rss`、`rss-auto-bind`、`rss-backfill`、`rss-exclusions`、`rss-oneshot`（2）、`rss-preview`、`rss-subscribe`。票 53 記 `pnpm -C web e2e` 35 passed。**這些不碰任何真服務。**

### 3.3 功能表

| 功能 | 邏輯（一兩句） | 狀態 | 證據 |
| --- | --- | --- | --- |
| 精靈：全套件內 | 六頁：選來源→測連線→bootstrap；套件內建 Jellyfin 管理員、設 qBittorrent / Prowlarr 登入、建媒體庫與 Route、測並加站、TMDB、完成時照頁序再驗（`S/setup.py`） | **真** | `tests/e2e/conftest.py`（頁 1–3、5、6 + 頁 4 以既有走過、不加站）；票 40、41、43、44 的手動 S1；審計 S1。**頁 4 加站 + Prowlarr 登入無 e2e** |
| 精靈：混用既有 | 既有只做連線測試與 Berth 擁有的寫入（key、分類、Berth 路徑、勾的站）；掛載由頁 2/3 探針驗 | **真（手動）＋ Fake** | 票 36、46 手動實跑；審計 S2；`web/e2e/existing.spec.ts`；`test_setup_owned_writes.py`（Fake） |
| 精靈錯誤說明 / 欄位錯誤 | 錯誤分類成 reason；位址類標位址、憑證類標憑證；補法照原因（票 21、25、45） | Fake（＋審計 S3 手動 11 種） | `web/src/**` vitest、`web/e2e/existing*.spec.ts`；審計 S3 |
| 探索 | TMDB 趨勢 / 熱門 / 搜尋，一格連到作品頁（`S/discover.py`） | **真（手動）** | 審計 S6；e2e 用真 TMDB key 走頁 5（只驗連通） |
| 作品頁搜尋 | 作品的多個名字各問 Prowlarr 一次、按名字比對過濾；電影擋掉有季集與年份差>1 的，劇集收在播出期；被收起來的說筆數可展開（票 49，`parser.fits`） | 真（手動，修之前）＋Fake | 審計 S6（修前：111 筆 109 筆對不上、混進 1990/2006）；票 49 單元；**無 e2e（e2e 不加站）** |
| 送單 | 送前檢查 Route 狀態與磁碟（扣在途量）；`ensure_category` → `torrents/add`（分類、tag、`autoTMM`）；暫時失敗自動重送（`S/jobs.py`） | **真** | `tests/e2e/test_1`（三筆）；審計 S6（真 YTS 電影）；`test_submit_guards.py` |
| 下載追蹤 | `QbitPoller` 讀 `sync/maindata` 增量、狀態→Job、SSE 推前端（`pipeline/downloads.py`） | **真（傳輸除外）** | `test_1`（位元組由測試複製）；審計 S6（真下載 6 分鐘） |
| RSS：自動綁定 | Mikan 聚合 feed 的 作品×字幕組 認得出且證據夠強就綁；其餘留給人（`pipeline/rss.py`、`parser.vouch_first_batch`） | **真（替身站）**＋Fake | `test_4_m3_rss.py`（站是 `sites.py`）；`web/e2e/rss-auto-bind.spec.ts` |
| RSS：補舊集 | 綁定時預設補單一字幕組 feed 的舊集 | 真（替身站）＋Fake | `test_4`；`web/e2e/rss-backfill.spec.ts` |
| RSS：一次性連結 | 貼 feed 連結列出整季、勾幾集送單，不建 Feed | **真站（手動）**＋Fake | 審計 S6（真 acg.rip，30 筆）；`web/e2e/rss-oneshot.spec.ts`；票 48 修多季一包 |
| RSS：排除條件 | 三層（全域、Feed、Series）取聯集；預設只排合集（`release_kind != single`） | Fake＋替身站 | `test_4`（合集被排除）；`web/e2e/rss-exclusions.spec.ts`、`rss-preview.spec.ts` |
| 解析 | 純函式：分類→發佈名→季集/播出日/片長→逐檔處置與信心；`berth bench` 守 `auto_wrong` | Fake（純函式＋真語料） | `tests/unit/test_bench.py`；e2e 用同一批語料驗結果；票 48 加多季一包 |
| 計劃（Import Plan） | 逐檔：處置、信心、目標路徑與理由；低信心 / 播出日或片長不符進審核 | Fake＋**真** | `test_4`（split-cour 被擋）；`web/e2e/review.spec.ts` |
| 入庫 | 硬鏈接（不退回複製），帳本記 inode；通知 Jellyfin（J9） | **真** | `test_1`（容器內 `stat` inode）、審計 S6 |
| 帳本 | 每個鏈接一列（來源、目標、inode、Jellyfin item id）；災難復原 `berth rebuild-ledger` | **真**（帳本）＋Fake（rebuild） | `test_1`；`test_3`（reimport 回同一 inode）；`rebuild-ledger` 只有整合測試 |
| Jellyfin 回驗 | 排程退避反查 item；季集不一致開 Issue；找不到兩次後觸發整庫掃描（J10）；作品頁打開先問一次（票 51） | **真**（回驗與 Issue）；票 51 的早問是 Fake + 演練 | `test_1`（item id）、`test_4`（mismatch Issue）；票 51 用 `late-scan` 演練，**沒有真 Jellyfin 的早問實跑** |
| 審核佇列 | 低信心逐列改後核准；medium 自動入庫可一鍵確認或撤銷；指派 Unmatched | **真**（部分）＋Fake | `test_4`（修正一次其餘跟著）；`web/e2e/review.spec.ts`、`series-offset*.spec.ts` |
| 對帳與修復 | 每日 04:00 / 手動，比 Jellyfin、complete、媒體庫、帳本；一鍵修 | **真** | `test_3_m2_repair.py`（5 種人為破壞）；`web/e2e/issues.spec.ts` |
| 媒體庫瀏覽 | 一個 Jellyfin 媒體庫一頁、整庫、繼續觀看、標已看；權限由 Berth 對 Jellyfin 允許清單擋 | **真** | `test_2_m15_library.py`（6 條） |
| 多使用者權限 | 角色 = Jellyfin `IsAdministrator`；`user` 對審核 / 設定都是 403；`ADMIN_ROUTES` 逐段比對 | **真（媒體庫那一半）**＋Fake | `test_2`（viewer 看不到沒權限的庫、停用即斷）；管理員端點 403 只有整合測試 |
| 健康 | 每 5 分鐘四項服務＋Route 纜繩（探針沿用上次結論，票 50）＋下載迴圈 | Fake＋真（Route 6/6） | `conftest` 的 Route 6/6；票 50 `healthy` 演練；**真服務上沒驗「沿用」** |
| 設定頁 | 精靈跑完後 `/setup` 導向；設定頁呼叫的是精靈同一批命令（`api/gate.py` 註解） | Fake（`web/e2e/settings.spec.ts`）＋e2e 的完成流程 | — |
| i18n zh-Hant / en | 字串走 key；`resources.test.ts` 守成對與**未引用鍵**（票 54） | Fake（vitest） | 審計 S6 切 EN 抽查 |
| 巡檢（缺號、卡住、Feed 失敗、週報） | **無** | **無** | `berth/pipeline/` 只有 downloads、health、importing、planning、reconciling、resolving、rss；`.scratch/m4/issues/` 全是修補與精靈票，沒有巡檢票 |
| 通知（Telegram / Discord） | **無** | **無** | `berth/adapters/` 沒有 notify / channel；grep `telegram|discord` 在 `berth/`、`tests/` 無命中 |
| AI | 只有 `AiPlanner` Protocol 與預留（`A/ai.py`），沒有 provider、預算、命令登錄表 | **無** | `A/ai.py:1-30`；M5 票目錄尚未存在 |
| 可拉的 image | `ghcr.io/1morr/berth:latest` = 0.1.0（**不含票 43–54**） | **有，但落後 15 commit** | 匿名 `tags/list` 我今天查：`0.1.0-rc1`、`0.1.0`、`0.1`、`latest`；`git log v0.1.0..HEAD` = 15 |

---

## 4. 上一輪「還不能交給一般使用者」阻擋項現況

### 4.1 §3.3 四條阻擋項

| 阻擋項 | 處理的票 | 現況 | 證據 |
| --- | --- | --- | --- |
| 1 沒有可拉的 image | 41（done） | **已解（有但舊）**：`:latest`、`:0.1.0`、`:0.1` 都是 digest `sha256:8b93…6425`；匿名 `docker pull` 與乾淨環境 S1 走過。**但**那顆 image 不含 43–54（見最前面） | 票 41 Comments；我今天再查 GHCR `tags/list`；`git tag`：`v0.1.0`、`v0.1.0-rc1` |
| 2 P0-1 套件內全域 `save_path` 擋送單 | 32（done） | **已解**：套件內與既有都只寫登入兩鍵、只看分類路徑；真服務 e2e `test_the_global_save_path_steers_nothing`（全域 `save_path` 改到別處照常入庫）；閘門 `test_qbittorrent_login_only.py` | 票 32、34 Comments；`tests/e2e/test_1_m1_pipeline.py:87` |
| 3 原生 Linux / NAS 沒驗 | 42（**needs-info**） | **未解**：被擋在「使用者要提供一台原生 Linux」。README 仍寫「原生 Linux 宿主與 NAS 還沒有人跑過」 | 票 42 `Status: needs-info`；`README.md:159`。`host-gateway` 與 PUID/PGID 只在 Windows Docker Desktop + 其 Linux VM 驗過（票 36 另在 Docker 29.6.2 / Compose v5.3.1 實測了 compose 停不停） |
| 4 README 混用指示不完整 | 36（done，另 33、53 修文案） | **已解（文件面）**：README〈選「既有」的條件〉明寫只能 `/data`、原本掛載不動、要 `docker compose stop <服務>`（Compose 實測確認 profile 拿掉停不掉）；補法改成「多加一條 `/data`」；票 36 手動實跑 6/6 | README:7-100；票 36 Comments（實測 1、2） |

### 4.2 加分項

| 項目 | 現況 | 證據 / 票 |
| --- | --- | --- |
| 通知 | **沒做**（M4 的「巡檢與通知」主體沒拆票） | 3.3 表 |
| 巡檢 | **沒做** | 同上 |
| 精靈收斂（E-1…E-7） | **全部做完**：E-1 → 32；E-2 → 38、39；E-3 → 40；E-4 → 43；E-5 → 44；E-6 → 45；E-7 → 47 | 各票 `Status: done` |
| 搜尋年份 / 類型篩 | 做完（票 49）。**未真服務實跑**（e2e 不加站） | 票 49 |
| RSS「S01 + S02」誤讀 | 做完（票 48）：`ReleaseInfo.season_end`，確認綁定不受影響 | 票 48 Comments |
| 健康頁 5/6 | 做完（票 50）。**真服務上沒驗**「沿用」顯示 | 票 50 |

### 4.3 改進清單 P0-1…P2-11 對應

| 項 | 票 | `Status` | 備註 |
| --- | --- | --- | --- |
| P0-1 全域偏好不影響 Route | 32 | done | |
| P0-2 發 image | 41 | done | image 落後 15 commit |
| P0-3 原生 Linux 實跑 | 42 | **needs-info** | **唯一沒做** |
| P1-1 接管模型定義與 CONTEXT | 33 | done | 加了白名單閘門 |
| P1-2 每頁同形狀、拿掉不寫入確認鍵 | 38（頁 2）、39（頁 4） | done | |
| P1-3 套件內卡片提示 | 35 | done | |
| P1-4 頁 4 錯誤版面與右欄 | 39 | done | |
| P1-5 密碼只問一次 | 40 | done | 重整後才再問 |
| P1-6 既有條件與補法改 `/data` | 36 | done | |
| P1-7 README 補停掉套件內容器 | 36 | done | |
| P1-8 真服務 e2e 恢復 | 34 | done | 24 條，nightly |
| P1-9 只支援 Prowlarr | 37 | done | migration `b4ca280eaeca` |
| P2-1 頁 3 自動跑 | 43 | done | 實跑 12.7 秒 |
| P2-2 頁 4 一鍵加站 | 44 | done | |
| P2-3 只存驗過的憑證 | 45 | done | TMDB key 被拒仍不標到 key 欄（未處理，見 4.4） |
| P2-4 頁 2 驗 `/data` | 46 | done | |
| P2-5 換台列遺留物 | 47 | done | |
| P2-6 S01+S02 | 48 | done | |
| P2-7 搜尋篩 | 49 | done | |
| P2-8 健康頁 5/6 | 50 | done | |
| P2-9 作品頁 Jellyfin 狀態 | 51 | done | |
| P2-10 文件與實作不符 | 53 | done | 17 列逐列結論在票 |
| P2-11 Jellyfin 伺服器名稱 | 52 | done | e2e 守 |
| §A3 code-review 遺留與過期 i18n | 54 | done | 4 修 2 不修 |

### 4.4 各票 `## Comments` 裡 code-review「**沒處理**」的發現（票 32–54）

| 票 | 沒處理的發現（一句話） |
| --- | --- |
| 32 | HTTP 路徑 `GET /setup/qbittorrent/diff` 與 handler `get_qbittorrent_diff` 名字沒改（對外路徑）；i18n `qbittorrent.apply` 的 `{{keys}}` 參數名沒改 |
| 33 | README〈選「既有」的條件〉「例如三個都是 `/data`」（後由 36 修）；README 表 BTH 4 既有那欄舊說法（後由 44、53 修）；測試 helper 名偏短、跨檔 import 私有 helper（判斷題） |
| 34 | 密碼規則只驗「密碼 < 6」，帳號 < 3 與含冒號沒進 e2e；不 `pull` 之後本機 e2e 用本地已有的 image（README 有寫） |
| 35 | `35042a0` subject 76 字元超過 72（已提交）；`bringBack` 函式與元件 `BringBack` 同檔只差大小寫 |
| 36 | Route 設定頁與 `SetupPage` 各組一份 `ExistingServices`（root 一個用常數一個用 `commonRoot`）；實驗腳本函式與 `compose_collisions.py` 重複；NAS compose 範例在 README 與 plan 各一份；健康頁仍給套件內那份補法（票面只點名頁 3 與設定頁） |
| 37 | `IndexerMode` 剩 `'bundled'｜'prowlarr'`（其實是既有）、`'prowlarr'` 步驟鍵寫死；`test_prowlarr_only.py` 的 helper 與 `test_database.py` 重複 |
| 38 | `apply` 對既有那台的分支沒有前端呼叫端卻留著（改 422 是公開 API 破壞性）；`note_qbittorrent_login` 與 Prowlarr 對應函式形狀相近；`LoginSequence` 的 `onApply` 等命名仍是「偏好」時代；「讀得到帳號、後端沒記」時按下去記 `skipped` 不寫（文案沒另分） |
| 39 | `indexer.probe_indexer`（健康）與 `setup._test_connection`（精靈）各自問 `system/status` 判版本（兩份實作）；`IndexerActions` 只剩設定頁用卻住在 `setup/IndexerStep.tsx`；`jellyfin.cutaway.*` 三個鍵疑似沒引用（後由 54 清 41 個鍵） |
| 40 | 頁 4 自動登入時 Prowlarr 重啟期間「測試」仍按得下去（暫時連不上）；帳號與密碼都不合 qBittorrent 規則時只說帳號；前端 e2e 對「頁 2 打錯密碼」「頁 4 自設登入」只剩 vitest 守；`bodiesOf` 兩份 |
| 41 | README 新增〈版本與升級〉超出票面；`v0.1.0` tag 上的 CHANGELOG 是修正前的版本（不重打 tag） |
| 42 | （無 Comments；`needs-info`） |
| 43 | 健康頁與 Route 設定頁的「立即檢查」不輪詢；容器在檢查中途被殺時 `running` 留到下一次有人按「重新檢查」 |
| 44 | 兩個分頁幾乎同時按主鍵可能撞同名（`Should be unique`）被記成「測過、加不進去」（沒有 repro 不修）；Prowlarr 沒有某推薦站定義時主鍵不測也不列它 |
| 45 | TMDB key 被拒仍在 `StepLine`、不標到 key 欄；0.1.0 存下的紅燈纜繩留著；`setup.py` 照服務分三支的讀寫有四處沒收 |
| 46 | autouse fixture 改寫私有 `setup._data_root`；`_test_connection` 多一個只有 qBittorrent 用的 `data_root` 參數；`_data_sight` 先 `os.access` 再寫（沒 repro）；`ProbeSight` 三份平行對照、`unfinished` 旗標穿五個簽章 |
| 47 | **移除與送單之間沒有鎖**（剛 `ensure_category` 還沒 `add` 時分類被刪，qBittorrent 可能自建預設路徑的同名分類，沒查證）；Prowlarr 以 `definitionName` 比對會把使用者自己刪掉又加回的站列成 Berth 的；連不到 qBittorrent 時列的是全部 Route 的分類；`choice.switchAway.prowlarr` 與 `switchWarning.prowlarr` 同一句 |
| 48 | `[S1] Movie 2019` 等把 `S1` 當片源記號會被收起來；只寫修復年份的發佈會被收起來；收起來的也跑 `parse_release`（≤100 筆約 1.4 秒）；`set_aside*` 與 `rows/total` 同形不收；展開後照樣能送單；**全套 pytest 時 `test_rss.py::TestTwoRoundsAtOnce::test_only_one_round_runs_and_neither_fails` 失敗過一次（單獨跑 3/3 綠，與本票無關，沒 repro 不修）** |
| 49 | （與 48 同一段「未處理」；見上，其中收起來的相關三條屬票 49 範圍） |
| 50 | `probe` / `probed_at` 沒收成一個型別；`probe_carried` 靠兩個時間相等認出；測試中字面值與 `.value` 並用 |
| 51 | （Comments 只記已修；無未處理條目） |
| 52 | 測試斷言寫字面 `"Berth"`（刻意）；**既有而還沒初始化的 Jellyfin，`system.xml` 事先放的名字仍會被第 2 步清空**（要保住得先讀 `GET /Startup/Configuration`，記在 plan §9.4） |
| 53 | 「重啟補不回來」的理由寫在六處（刻意，brief §20.7 為單一來源） |
| 54 | 設定頁「重新讀取」與連線區「重新測試」是同一支的兩個 mutation；`inventory/jellyfinLink` 與 `setup/serviceWeb` 互相 import；radio 說明 `<span>` 裡有 `<div>`；套件內 Prowlarr 掛掉時設定頁不再給 `docker compose ps/logs`。**另 2 條「不修」（探針刪不掉殘留、「原帳號＋新密碼」）在 4.5** |

### 4.5 判斷為「不修」、但對一般使用者有影響的（建議上報）

1. 探針在 `finally` 刪除時斷線 → 探針殘留在使用者 qBittorrent（票 54 #1，「要不要補刪由使用者決定」）。
2. qBittorrent 兩次 `setPreferences` 之間斷線 → 「舊帳號＋新密碼」（票 54 #2）。
3. 移除空分類與送單之間無鎖（票 47）。
4. `berth` tag 與每次送單的 `ensure_category` 重建、Jellyfin 全域掃描任務：**這輪審計新看到，沒有任何票或文件提到**（1.8 #1）。
5. 套件內 Prowlarr 的「移除」能刪使用者自己加的公開站（1.8 #2）。
6. 發佈的 image 落後 15 commit（最前面）。
