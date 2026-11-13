# 事實：qBittorrent、Docker 與部署

查證過的外部事實。編號沿用 brief 原本的節號（`§20.x`），程式碼與文件用它引用，編號不重用。索引在 [brief §20](../design-brief.md)。

## 事實

### 20.2 qBittorrent Web API 與硬鏈接 / Docker 限制

細節（逐字原文、實測表格、原始碼行號）在 [qbittorrent-web-api.md](qbittorrent-web-api.md)，下面只留結論與來源。來源：qBittorrent master 原始碼（`torrentscontroller.cpp`、`serialize_torrent.cpp`）、`WebAPI_Changelog.md`、qbittorrent-api、TRaSH Guides、Servarr wiki、man pages。**社群 wiki 的 API 頁面已過時**（連「5.0」頁面都還列 `paused` / `root_folder`），以原始碼為準。【決定】支援下限 qBittorrent 4.4（API 2.8.4，2022），以 5.x 為主要測試目標。

**版本對照**（留作版本行為的前提，原文在研究檔）：4.4.5 = Web API 2.8.5、5.2.3 = Web API 2.15.1；`contentLayout` 自 API 2.7 / qB 4.3.2 起，取代 `root_folder`；4.4.4 引入「方法不對回 405」，`torrents/delete` 到 4.5.0 才進 POST 白名單（4.4.5 仍可 GET）；changelog 說 API 2.15.0 起空結果回 204，`recheck` / `start` 實測沒有（仍 `200` + 空 body）。

**`torrents/add` 與改名**（[細節](qbittorrent-web-api.md#torrentsadd-參數與回應)）

- 現行參數：`urls` / `torrents`、`savepath`、`downloadPath` + `useDownloadPath`、`category`、`tags`、`rename`、`autoTMM`、`contentLayout`（API 2.7 起，取代 `root_folder`）、`stopped`（API 2.11.0 起取代 `paused`）、`stopCondition`、`seedMode`（API 2.16.0 起，同時移除 `skip_checking`）、`filePriorities`、`ratioLimit` / `seedingTimeLimit`。master 已不讀 `paused` / `root_folder`。
- adapter 必須先讀 `app/webapiVersion`，依版本送 `paused` 或 `stopped`；`torrents/pause|resume` 在 5.0 改名 `stop|start`，5.x 的 `torrents/resume` 是 404、沒有別名（實測 4.4.5 / 5.2.3，細節見 [recheck](qbittorrent-web-api.md#torrentsrecheck-與重新開始)）。
- **回應形狀兩版不同**（2026-09-10 票 09 實測，見 §20.7）：4.4.5 回 `200` + `Ok.`，5.2.3 回 `200` 加一份 JSON 摘要。只認 `Ok.` 的用戶端會把 5.x 上每一次成功的送單都判成失敗。

**分類與路徑**（[細節](qbittorrent-web-api.md#分類與路徑)）

- `createCategory` / `editCategory` 參數：`category`、`savePath`、`downloadPathEnabled`、`downloadPath`。per-category 未完成路徑自 API 2.8.4 / qB 4.4.0 即存在，WebUI 到 **5.2.0** 才有介面（[Changelog](https://raw.githubusercontent.com/qbittorrent/qBittorrent/master/Changelog)）。本系統用它取代全域 `temp_path`（M4 票 22，§4.1）。
- **分類的 `downloadPath` 實測**（M4 票 22，4.4.5 與 5.2.3 結論相同）：分類 `downloadPathEnabled=true` + `downloadPath` 時，下載中檔案在分類的 `downloadPath`，完成後搬到分類的 `savePath`；全域 `temp_path` 開或關都是**分類的贏**。分類 `downloadPathEnabled=false` 時直接寫在 `savePath`（可明說不走全域）；兩個欄位都不送時跟全域（開著就在全域 temp path，5.2.3 底下多一層分類名）。torrent 照 Berth 的送單形狀加：`category` + `autoTMM=true`、不送 `savepath`。
- 讀回 `torrents/categories` 的鍵是 **`download_path`**（不是駝峰）：設了是字串；停用兩版都是 `false`；沒設 5.2.3 是 `null`、4.4.5 **整個鍵不出現**。儲存路徑的鍵在 4.4.0–4.4.1 曾在 `savePath` / `save_path` 之間反覆，adapter 兩者都要接受（4.4.5 / 5.2.3 實測是 `savePath`）。
- `createCategory`：表單鍵 `category`、`savePath`（Berth 另帶 `downloadPathEnabled`、`downloadPath`）；名稱空字串回 **400** `Category cannot be empty`，名稱不合法或建不起來（含同名已存在）回 **409** `Unable to create category`（master 原始碼，2026-09-08）。所以冪等要靠呼叫端先 `torrents/categories` 讀一次。
- `torrents/removeCategories`：表單欄位 `categories`，多個以換行分隔，任何情況都回 200（[WebUI API 5.0](https://github.com/qbittorrent/qbittorrent/wiki/WebUI-API-(qBittorrent-5.0)#remove-categories)，context7 查核 2026-10-07）。分類裡的 torrent 會變成沒有分類，所以 Berth 只送重數過是空的 `berth-*`（M4 票 47）。
- **autoTMM 開啟時 save path 跟隨 category；`category_changed_tmm_enabled` 為真時改 category 路徑會自動搬移所有該分類 torrent。** → 建立 category 後不再改其 savePath；使用者改 Route 目標時建立新 category，舊 Job 維持原位；已存在但路徑不同回報衝突、不覆寫。
- TRaSH 明確要求 category 模式必須 `Automatic`（autoTMM），否則下載不會進分類資料夾（[Basic-Setup](https://trash-guides.info/Downloaders/qBittorrent/Basic-Setup)）。

**狀態與檔案**（[細節](qbittorrent-web-api.md#狀態與檔案)）

- `torrents/info` 欄位：`hash`、`name`、`state`、`progress`、`save_path`、`content_path`（API 2.6.1）、`download_path`（原始碼有、wiki 未列）、`completion_on`、`category`、`tags`、`added_on`。`state` 全值清單見研究檔。
- **「完成」判定**：`progress == 1` 且 `completion_on > 0` 且 state **不是** `moving` / `checking*`（temp path 搬到 save path 期間 state 為 `moving`，此時不可入庫）。`completion_on` 未完成時 4.4.5 是 `0`、5.2.3 是 `-1`：寫 `> 0` 兩版都對，寫 `!= 0` 會讓 5.x 上每個剛加入的 torrent 被當成已完成。`total_size` 在 metadata 到手前同樣是 `-1` / `0`。
- `torrents/files` 回 `index`、`name`（相對路徑）、`size`、`progress`、`priority`（0 = 不下載，要從 Plan 排除）、`availability`。`name` 相對 `save_path` 還是 `content_path` 文件未明，adapter 以 `stat` 驗證組出的絕對路徑（實測見 §20.7）。**`metaDL` 期間回 `200` + `[]`**（兩版皆然），與「torrent 不存在」同形，所以 `metadata_ready` 要 state 與清單兩個條件都成立。
- 其他端點：`setLocation`、`rename`、`renameFile` / `renameFolder`（API 2.8.0）、`delete(deleteFiles)`、`setCategory`（category 不存在回 409）、`addTags`、`recheck`。
- **`torrents/delete`**（2026-09-22 對 `release-4.1.0` 到 `release-5.2.3` 十個 tag 逐一核對原始碼，M2 票 04，[細節](qbittorrent-web-api.md#torrentsdelete-的確切形狀)）：一律 POST（4.5.0 起 GET 是 405）；`hashes`（`|` 分隔、`all`）與 `deleteFiles` **兩個都必填**，少一個回 400；`deleteFiles` **只認字面 `true` / `false`**（`1` 不是真，解析不出來退回 `false`，檔案沒刪而呼叫端以為刪了）；成功 `200` + 空 body；**不認得的 hash 靜默成功**，所以對早已不在客戶端的那一筆不必先問。Berth 因此不用 `deleteFiles=true` 刪檔，由自己刪磁碟上的東西、數刪了幾個與空出多少（§9.2、`services/deletion.py`）。
- **`torrents/recheck` 與重新開始**（2026-09-23 M2 票 09c，原始碼逐行核對加兩版容器實測，[細節](qbittorrent-web-api.md#torrentsrecheck-與重新開始)）：重新開始 4.4.5 是 `torrents/resume`、5.x 是 `torrents/start`；參數 `hashes` 必填；5.x 只收 POST，4.4.5 GET 也行；成功 `200` + 空 body；不認得的 hash 靜默成功；有錯誤先 `clear_error()`、缺檔先 `reload()`。recheck 之後停住的 torrent 校驗完會**再停下來**。資料刪掉、容器重啟後 torrent 是 `missingFiles`；資料放回去之後 recheck → start 與 start → recheck 兩版都回到做種中，資料不在則是 `stalledDL`。`client_error` 的「重試」只送 start（錯誤不是資料的問題，重新校驗幾十 GB 只是更晚回來）。
- **停住的 torrent 做 recheck：5.x 上 recheck → start 救不回來**（2026-09-24 M3 票 03，5.2.3 與對照 4.4.5，[細節](qbittorrent-web-api.md#停住的-torrent-做-recheck)）：5.2.3 的 `forceRecheck()` 對停住的 torrent 自己先 `start()` 再掛 `StopCondition::FilesChecked`，校驗中送到的 `start()` 看它沒停就什麼都不做，校驗完照樣 `stop()`，於是停在 `stoppedUP`（資料齊）或 `stoppedDL`（缺檔，progress 0.5）；`stoppedDL` 既不轉 `stalled` 也不開 Issue，畫面上看不出事。**start → recheck 順序兩版都落在做種中或 `stalledDL`。Berth 用 start 先於 recheck（`missing_files` 的「重新校驗」），順序不能反。**

**輪詢與登入**（[細節](qbittorrent-web-api.md#輪詢與-syncmaindata)）

- **沒有 webhook**；`sync/maindata` 以 `rid` 做增量輪詢。`autorun_enabled` / `autorun_program`（完成時執行外部程式，可帶 `%f` `%n`）可作「喚醒輪詢」的加速手段，非必要。
- **`rid` 的狀態掛在 session（SID cookie）上**（2026-09-10 票 10 對 4.4.5 與 5.2.3 實測）：不帶 cookie 則每次請求都是新 session，回的永遠是 `full_update: true`。所以輪詢那一側必須把 HTTP client 握著不放（Berth 的 `Downloader`）。
- **增量那一輪的 `torrents[hash]` 只帶變動的欄位**（實測有的只剩 `{"num_leechs", "time_active"}`），呼叫端一定要併回上一份完整快照再讀，否則得到沒有 category、沒有 state 的空殼。被刪掉的在 `torrents_removed`（hash 陣列）。
- 登入 `auth/login` 回 `SID` cookie，且 **`Referer` / `Origin` 必須與 `Host` 一致**（m0 實測的更準確說法見 [m0-experiments.md](m0-experiments.md)）；可設 `bypass_local_auth` 與子網白名單。
- **`auth/login` 的成敗形狀跨大版本不同**（2026-09-08 對 `lscr.io/linuxserver/qbittorrent` 的 4.4.5 與 5.2.3 實測，票 11）：4.4.5 成功 `200` + `Ok.` + `Set-Cookie: SID=…`，帳密錯 `200` + `Fails.`（**狀態碼不變**）；5.2.3 成功 `204` + 空 body + `Set-Cookie: QBT_SID_<port>=…`，帳密錯 `401` + `Unauthorized`。所以判定只能認 4.x 那個「200 卻是失敗」的 `Fails.`，不能認「成功等於 `Ok.`」。來源 IP 在 `WebUI\AuthSubnetWhitelist` 上時 5.x **一律回 204，連錯的帳密也是**——免密白名單本來就繞過驗證，這正是套件內 Berth 的處境（§16.3、§20.7）。
- **IP 封鎖與帳密不對是兩件事**（2026-09-10 票 10 對兩版各實測一輪，解掉 plan T1.9 的第四條）：帳密錯第 1–5 次是 `200` + `Fails.`（4.4.5）/ `401`（5.2.3）；**第 6 次 IP 被封回 `403` + `Your IP address has been banned after too many failed authentication attempts.`，兩版一字不差**；被封之後其他端點回 `403` + `Forbidden`。因此 **`auth/login` 上的 403 只有一個意思**（被封），其他端點上的 403 與「沒有登入」同形、分不出來。下一步不同才是分開的理由：帳密不對要改設定，被封要等過期或重啟 qBittorrent——改帳密只會再失敗五次，把封鎖時間重算一輪。
- **封鎖的偏好鍵與預設值**（2026-09-30 讀 `release-4.4.5` 與 `release-5.0.4` 原始碼，M4 票 21，兩版相同，[細節含行號](qbittorrent-web-api.md#封鎖的偏好鍵與預設值)）：門檻 `web_ui_max_auth_fail_count` 預設 **5**（連續失敗），封鎖 `web_ui_ban_duration` 預設 **3600 秒**；計數與封鎖表只在記憶體（`m_clientFailedLogins`），重啟容器就清；**登入成功才把該 IP 移除**，不隨時間衰減；**被封期間連對的帳密也被拒**；`max_auth_fail_count = 0` 不計也不封。WebUI 與 API 都沒有解除封鎖的介面。被封時 Berth 讀不到偏好，所以精靈說預設值（`components/services.BAN_DEFAULTS`），並從第 3 次連錯起預警。
- **`auth/login` 在 session 還活著時直接回成功，連密碼都不看**（帶著 SID 打八次錯的密碼全是 `200` + `Ok.`）。所以「驗一次帳密對不對」必須從沒有 cookie 的狀態發起。

**qBittorrent 看不看得到分類路徑：探針 torrent**（2026-09-30 實測 4.4.5 與 5.2.3，M4 票 19；`scripts/experiments/qbittorrent_visibility_probe.py`，[細節與表格](qbittorrent-web-api.md#探針-torrent看不看得到分類路徑)）

- Web API 沒有「這條路徑你看不看得到」（`app/getDirectoryContent` 5.0 才有，且只說目錄在不在）。反過來證明：Berth 在分類路徑寫小檔、做成單檔 torrent（`private`、不掛 tracker），`torrents/add` 明送 `savepath`、`autoTMM=false`、停住，`torrents/recheck`，看 `progress`；之後 `torrents/delete` 帶 `deleteFiles=false`，小檔由 Berth 刪。
- 結果（兩版相同，state 名 `paused*` / `stopped*` 之別）：檔在 → recheck 後 100%（約 1–1.4 秒）；檔或目錄不在 → 0%；檔在但 `chmod 000` → **`error`**（權限，與看不到分得開）；開了全域 temp path 照樣 100%。**停住加入不會自己校驗**，一定要 recheck。
- **`torrents/add` 回來時它還不一定列在 `torrents/info` 裡**，而對還不在的 hash 送 recheck 是靜默成功（校驗沒發生，停在 0% 與看不到一模一樣）。所以先等它列出、離開 `checkingResumeData`，再 recheck。
- 看不到時 qBittorrent 不替它建目錄。看不到沒有「校驗完了」的狀態可等，所以 Berth 以「不在校驗或排隊中、進度不到 100%、state 3 秒不變」判看不到，整個探針最多等 20 秒（預設一次只校驗一個 torrent）。
- **校驗到 100% 會觸發「torrent 完成時執行外部程式」**（`autorun_enabled` / `autorun_program`，兩版實測，每個看得到的探針各觸發一次）。所以探針只在精靈「建立並檢查」、新增 Route 與「重新檢查」時跑；**5 分鐘的健康迴圈不跑，`download_visible` 沿用上一次的結論**（否則每條 Route 每 5 分鐘一次，成為使用者那邊的通知洪水；M4 票 50，使用者 2026-10-06 確認）。5.x 另有「加入時執行」（`autorun_on_torrent_added_enabled`），同理，沒有另外實測。
- 探針 torrent 不掛分類、不帶 tag（`berth` tag 會讓 poller 把它當成 Berth 的下載），名字 `.berth-probe-*`，停住、幾秒內移除。

**校驗不完的探針：頁 2 問「看不看得到 `/data`」**（2026-10-07 實測 4.4.5 與 5.2.3，M4 票 46；`scripts/experiments/qbittorrent_unfinished_probe.py`，[細節與表格](qbittorrent-web-api.md#校驗不完的探針)）

- 探測檔兩片（32 KiB），第二片雜湊算在反相內容上。結果：檔在 → 停在 **`progress` 0.5**（不是 1）；檔不在 → 0；`chmod 000` → `error`；對照單片 → 1。**「完成時執行」只有對照組觸發**；5.x 的「加入時執行」四包都觸發（4.4.5 沒有這個設定）。
- 所以 Berth 判「看得到」改成 **`progress` 大於 0**（`probe_sight`），兩種探針同一條（單片本來就是 0 或 1）。頁 2 測連線用這一種（M4 票 46）：不觸發「完成時執行」；「加入時執行」擋不掉（任何加進去的 torrent 都觸發），表單照實說觸發一次。頁 3 的 Route 檢查仍是單片那一種。

**WebUI 帳密規則**（2026-10-01 讀原始碼＋實測，M4 票 26；`scripts/experiments/qbittorrent_webui_login_rules.py`，[細節](qbittorrent-web-api.md#webui-帳密規則)）

- **5.2.0 起 `app/setPreferences` 才驗**：`web_ui_username` 至少 3 字元、不能有冒號，`web_ui_password` 至少 6 字元；違反回 `400` + 一行英文原文。4.4.5 什麼都收；release-5.1.4 原始碼還沒有這段（[appcontroller.cpp @ release-5.2.0](https://github.com/qbittorrent/qBittorrent/blob/release-5.2.0/src/webui/api/appcontroller.cpp)）。字數是 QString 長度（UTF-16 code unit），與瀏覽器 `String.length` 同算法。
- **帳號先驗先寫、密碼後驗**（不看 JSON 鍵序）：帳號合規而密碼太短的那次回 `400`，帳號**已經寫進去**、密碼沒有。所以 Berth 先單獨送密碼、成功才送帳號（`qbittorrent._apply_password`），兩支都過了才記下帳號。
- 【決定】精靈與設定頁照 5.2 的規則先擋，不分版本：4.4–5.1 自己的設定頁（WebUI JS）也要求帳號 3、密碼 6 字元（只少冒號那條），套件內那一台又一定是新版。

**硬鏈接與 Docker**（[TRaSH Hardlinks](https://trash-guides.info/File-and-Folder-Structure/Hardlinks-and-Instant-Moves/)、[Servarr docker-guide](https://wiki.servarr.com/docker-guide)、[link(2)](https://man7.org/linux/man-pages/man2/link.2.html)；[細節](qbittorrent-web-api.md#硬鏈接與-docker)）

- 硬鏈接不能跨檔案系統、分割區、volume、**mount**；`link()` 即使同一個檔案系統掛兩次也會 `EXDEV`。Docker 把兩個 volume 當成兩個檔案系統，所以 `/downloads` + `/media` 分開掛一定失敗；解法是單一 `/data` 掛載。
- exFAT 不支援硬鏈接；btrfs 子卷、ZFS dataset 各自是 mount 邊界，跨越即失敗；mergerfs 在 path-preserving 建立策略下跨 branch 回 `EXDEV`，其 FAQ 同樣要求單一掛載根（[mergerfs FAQ](https://trapexit.github.io/mergerfs/latest/faq/why_isnt_it_working/)）。
- 權限：TRaSH 建議「每個 app 一個使用者 + 共用群組 + UMASK 002」（資料夾 775、檔案 664），或簡化為單一使用者 + UMASK 022。本系統與 qBittorrent 至少要同群組且對兩側目錄可寫。
- Docker Desktop（Windows）：文獻無定論，本機實測 NTFS bind mount 硬鏈接可用（§20.7）。macOS VirtioFS 未查到硬鏈接限制，也未實測。
- `stat().st_dev` 相同是必要條件但不充分（同 FS 多次掛載仍失敗），所以 §4.4 的檢查一律真的做一次 `link()`。

**Sonarr / Radarr 先例**（[sonarr/faq](https://wiki.servarr.com/sonarr/faq)、[radarr/settings](https://wiki.servarr.com/radarr/settings)、[quick-start](https://wiki.servarr.com/sonarr/quick-start-guide)；[細節](qbittorrent-web-api.md#sonarr-與-radarr-先例)）

- Completed Download Handling：只在客戶端回報完成後才入庫；要求客戶端完成後**暫停而非移除**，並保留至少 14 天歷史。「Remove Completed」只在客戶端回報做種完成且 torrent 已停止時才移除 torrent 與檔案。本系統不做自動移除（§1.2），做種上限交給 qBittorrent 分類的 share limit；移除後的善後由 Reconciler 處理。
- 入庫預設硬鏈接，失敗時 Sonarr 會**退回複製**。【決定】本系統**不退回複製**：硬鏈接失敗即 Route 不健康並拒絕送單，因為複製會讓刪除範圍與空間估算失真。
- 人工入庫的官方名稱是 **Interactive Import**（逐檔指定作品/季/集，可選 Move 或 Copy/Hardlink）；Review Queue 對應這個概念。Root Folder = 媒體庫根目錄，明文規定不可與下載目錄相同。

**其他**（[細節](qbittorrent-web-api.md#其他同一台認不出來選項頁網址sparse-檔)）

- **同一台 qBittorrent 認不出來**（M4 票 102，2026-10-14 讀 master 原始碼）：WebAPI 沒有持久的實例識別碼（`app/` 底下只有版本、build info、偏好、預設路徑、網卡清單；沒有 Jellyfin `ServerId`〔§20.15〕那種東西）。最接近的 `app/processInfo` 的 `launch_time` 2026-01 才加（4.4 下限的版本沒有）、每次重啟就變；版本加 `save_path` 也不行（兩台預設安裝一模一樣）。所以位址變了就當換台（§16.4）。
- **WebUI 沒有通往「選項」的網址**（M4 票 102，2026-10-14 對 linuxserver 5.2.4 實開）：`/#/settings` 登入後落在 torrent 清單；`client.js` 只讀 `#download=`。選項是 MochaUI 視窗，從「工具 → 選項」開，所以補法只給 WebUI 本身，文案說在哪個選單。
- **下到一半的檔是 sparse 檔**（M4 票 102，票 42 實測）：qBittorrent 預設不預先配置，表觀大小（`st_size`）已是整個檔案，實際佔用（`st_blocks` × 512）只有下載了的部分（票 42 那筆表觀 970 MB、實際約 192 MB）。刪除的「可空出空間」與 `freed` 量實際佔用（`fs.PathFacts.allocated`），以區塊取整。Windows 的 `os.stat` 沒有 `st_blocks`，Berth 只在 Linux 容器跑，開發機上退回表觀大小。

### 20.7 開箱即用所需的 API 與 Windows Docker 事實

細節（完整實測原文、fixture 位置、原始碼連結）在 [`research/setup-api-facts.md`](setup-api-facts.md)；本節只留結論、決定性的數字 / 參數 / 狀態碼與查證日期。

**Windows Docker Desktop 硬鏈接**（本機實測，2026-09-07；Windows 11、Docker Desktop 29.6.2 WSL2、NTFS；[細節](setup-api-facts.md#windows-docker-desktop-硬鏈接)）

- 同一個 Windows 目錄 bind mount 成 `/data`，容器內 `ln` 成功（`dev=70`、inode 相同、`nlink=2`，掛載型態 `9p (aname=drvfs)`，宿主端 `fsutil hardlink list` 證實是真 NTFS 硬鏈接）。`torrent/` 與 `library/` 拆成兩個 bind mount：`ln: Cross-device link`，與 Linux 相同（單一掛載根的規則不變）。named volume（WSL2 ext4）也成功。
- 結論：**Windows 用一般 bind mount**（`DATA_ROOT=D:\Berth\data`），不需要 named volume；exFAT 不支援硬鏈接（[TRaSH](https://trash-guides.info/File-and-Folder-Structure/Hardlinks-and-Instant-Moves/)）；§4.4 的「不退回複製」維持。
- 不用 named volume 的理由：WSL2 VHD 預設上限 1 TB（[Microsoft](https://learn.microsoft.com/en-us/windows/wsl/disk-space)）、搬 VHD 的設定介面多起失效（[docker/for-win#13269](https://github.com/docker/for-win/issues/13269)）。bind mount 經 9p 吞吐較低（[Docker blog](https://www.docker.com/blog/file-sharing-with-docker-desktop)），下載寫入較慢，硬鏈接是 metadata 操作不受影響。

**Jellyfin 初始化與插件 API**（[OpenAPI](https://api.jellyfin.org/openapi/jellyfin-openapi-stable.json)、[FirstTimeSetupHandler.cs](https://github.com/jellyfin/jellyfin/blob/master/Jellyfin.Api/Auth/FirstTimeSetupPolicy/FirstTimeSetupHandler.cs)；[細節](setup-api-facts.md#jellyfin-初始化與插件-api)）

- `GET /System/Info/Public` 無需憑證，回 `StartupWizardCompleted`。
- `POST /Startup/Configuration`（`ServerName`、`UICulture`、`MetadataCountryCode`、`PreferredMetadataLanguage`）、`POST /Startup/User`（`Name`、`Password`）、`POST /Startup/RemoteAccess`、`POST /Startup/Complete`，以及 **`GET/POST/DELETE /Library/VirtualFolders`**，都掛 `FirstTimeSetupOrElevated`：精靈未完成時匿名可呼叫，完成後需管理員 token。`POST /Startup/RemoteAccess` Berth 只送 `EnableRemoteAccess`（10.11.11 schema 其實也有 `EnableAutomaticPortMapping`）。
- `POST /Library/VirtualFolders?name=&collectionType=&paths=&refreshLibrary=`：`collectionType` 為 `movies` / `tvshows` / `music` / `musicvideos` / `homevideos` / `boxsets` / `books` / `mixed`；body `{LibraryOptions}` 含 `PathInfos`、`EnableRealtimeMonitor`、`PreferredMetadataLanguage`、`MetadataCountryCode`、`TypeOptions[]`、`SeasonZeroDisplayName`、`EnableAutomaticSeriesGrouping`、`EnableEmbeddedTitles`、`AutomaticRefreshIntervalDays`。
- 既有媒體庫加路徑 `POST /Library/VirtualFolders/Paths?refreshLibrary=`，body `MediaPathDto {Name, Path, PathInfo{Path}}`；移除 `DELETE /Library/VirtualFolders/Paths?name=&path=`。路徑驗證 `POST /Environment/ValidatePath`，body `{ValidateWritable, Path, IsFile}`；另有 `GET /Environment/DirectoryContents?path=`。兩組皆 `FirstTimeSetupOrElevated`（OpenAPI 直接查核，2026-09-07）。
- **`ValidatePath` 看得到回 204、看不到回 404**：`IsFile: true` 走 `File.Exists`、`false` 走 `Directory.Exists`、不給則兩者皆否才算沒有（[EnvironmentController.cs](https://github.com/jellyfin/jellyfin/blob/master/Jellyfin.Api/Controllers/EnvironmentController.cs)，2026-09-08）。**404 是答案不是失敗**，adapter 翻成 `False` 不丟例外。Berth 不送 `ValidateWritable: true`（Jellyfin 會自己建暫存檔再刪）。
- 需管理員（`RequiresElevation`）：`GET/POST /Repositories`（`{Name, Url, Enabled}`）、`POST /Packages/Installed/{name}?assemblyGuid=&version=&repositoryUrl=`、`POST /System/Restart`、`GET /ScheduledTasks`、`POST /ScheduledTasks/Running/{taskId}`。
- MergeVersions：manifest `https://raw.githubusercontent.com/danieladov/JellyfinPluginManifest/master/manifest.json`、套件名 `Merge Versions`、GUID `f21bbed8-3a97-4d8b-88b2-48aaa65427cb`；排程任務 `Key` 為 `MergeMoviesTask` / `MergeEpisodesTask`（[RefreshLibraryTask.cs](https://github.com/danieladov/jellyfin-plugin-mergeversions/blob/master/Jellyfin.Plugin.MergeVersions/ScheduledTasks/RefreshLibraryTask.cs)）。**觸發要用 `GET /ScheduledTasks` 回的 `Id`，不是 `Key`**；`Id` 不跨安裝相同（實測那台 `MergeMoviesTask=fd957c84b0cfc2380becf2893e4b76fc`、`MergeEpisodesTask=dcaf151dd1af25aefe775c58e214477e`），一律現讀。本系統只支援 12 以上、不再安裝它（[ADR-0002](../adr/0002-jellyfin-12-minimum-pinned-image.md)、§20.9）。

**Jellyfin 精靈序列實測**（2026-09-07，票 06；`jellyfin/jellyfin:10.11.11`，Berth adapter 跑完 plan §9.4 全序列，fixture 在 `tests/fixtures/http/jellyfin/`；[細節](setup-api-facts.md#jellyfin-精靈序列實測)）

- **`POST /Auth/Keys?app=` 回 204 且不回傳 key**，只能再 `GET /Auth/Keys` 從 `Items[].AppName` 找；**不檢查重複**，按兩次就有兩把 `AppName="Berth"`。所以先列再建、建完再列。
- **`POST /Library/VirtualFolders` 同名不會被拒**：第二次也回 204，建出 `Movies2` 指向同一路徑；冪等靠呼叫端先 `GET /Library/VirtualFolders`。
- **`POST /Library/VirtualFolders/Paths` 不去重**（同路徑送兩次 `Locations` 有兩個一樣的字串）；目錄不存在回 **404** `Error processing request.`，所以 Berth 先建目錄（與 Jellyfin 掛同一個容器路徑，§16.4）。
- **404 說不出原因**（2026-09-30 對 12.1 的 `bad-jellyfin-elsewhere` 再測，M4 票 19）：Jellyfin 看不到目錄與**媒體庫不存在**是同一個 `404` + `Error processing request.`（`text/plain`），`The path does not exist` 只在它自己的 log。所以 Berth 送之前先寫探測檔、以 `ValidatePath {IsFile: true}` 問。**不問目錄本身**：linuxserver 的 Jellyfin image 自帶空的 `/data`，沒掛任何東西時 `{Path: "/data", IsFile: false}` 也回 204。
- **`LibraryOptions.TypeOptions[]` 省略 `ImageFetchers` 會被存成空陣列**（送 `{Type, MetadataFetchers, MetadataFetcherOrder}` 讀回 `ImageFetchers: []`），該類型從此不抓圖。要嘛整個 `TypeOptions` 留空用預設，要嘛兩種 fetcher 都給。
- **`GET /Libraries/AvailableOptions?libraryContentType=movies|tvshows`** 回伺服器實際裝了哪些 fetcher（`{Name, Type}` 陣列），政策 `FirstTimeSetupOrDefault`，精靈期間匿名可讀。乾淨 10.11.11 的 Movie metadata 是 `TheMovieDb` / `The Open Movie Database`，image 多 `Embedded Image Extractor` / `Screen Grabber`；tvshows 分 Series / Season / Episode。裝官方 TVDB 插件後每型別多一個 `TheTVDB`，Series 另多 `Missing Episode Fetcher` —— 「image fetcher 不可寫死」的證據。
- **登入 token 與 API key 標頭同形**：`Authorization: MediaBrowser Client="…", Device="…", DeviceId="…", Version="…", Token="<token 或 key>"`，兩者都吃得下 `RequiresElevation`。
- **重啟三階段**：`POST /System/Restart` 當下連線被切（httpx `RemoteProtocolError`）→ 一段時間所有端點回 **503** → 才回 200；輪詢要把「連不上」與 503 都當繼續等。
- 九步序列對真伺服器 **69 秒**（多花在插件下載與重啟）；第二次 **0.2 秒**，除第 1 步外全 `skipped`。

**Prowlarr**（[OpenAPI](https://raw.githubusercontent.com/Prowlarr/Prowlarr/develop/src/Prowlarr.Api.V1/openapi.json)、[supported-indexers](https://wiki.servarr.com/prowlarr/supported-indexers)、[environment-variables](https://wiki.servarr.com/prowlarr/environment-variables)；[細節](setup-api-facts.md#prowlarr-api)）

- `GET /api/v1/indexer/schema`、`GET/POST /api/v1/indexer`、`DELETE /api/v1/indexer/{id}`（回 200）、`POST /api/v1/indexer/test`；`GET /api/v1/search?query=&indexerIds=&categories=&type=` 回 `ReleaseResource`（`title`、`size`、`seeders`、`leechers`、`downloadUrl`、`magnetUrl`、`infoHash`、`indexer`、`categories`、`publishDate`、`guid`、`infoUrl`、`tmdbId` …）。Prowlarr 明言**不提供跨站聚合 Torznab**（所以搜尋走 REST），單站 Torznab 為 `/{id}/api?t=search&apikey=`。
- **`indexer/schema` 第一次呼叫很慢**（2026-09-08 票 11 M0 驗收）：容器剛起來要從 `/config` 讀 **627 份** Cardigann 定義、組出 **5.6 MB** 回應，Windows Docker Desktop 9p bind mount 上 **9.42 秒**；第二次 0.34 秒。NAS 只會更久，所以這一支要有自己的逾時（現為 60 秒），不沿用探測的 5 秒。**未量測**：成因是冷讀定義而非回應大小，同時刻 `config/host` 理論上也慢，目前仍用 5 秒、沒有數據證明安全。
- API key 在 `config.xml` 的 `<ApiKey>`（首次啟動即產生，32 字元），可用 `PROWLARR__AUTH__APIKEY` 預設。
- 支援的公開索引站含：Nyaa.si、dmhy、AniDex、Anime Tosho、ACG.RIP、**Mikan**、1337x、YTS、EZTV、The Pirate Bay；TorrentGalaxy 目前不在清單。

**Prowlarr 索引站與 TMDB 憑證實測**（2026-09-08，票 08；Prowlarr 2.5.2.5491，fixture 在 `tests/fixtures/http/prowlarr/` 與 `tests/fixtures/http/tmdb/`；[細節](setup-api-facts.md#prowlarr-索引站與-tmdb-憑證實測)）

- **`POST /api/v1/indexer` 先連一次那個站再存**：成功 201 與整份資源；連不上 **400 加陣列**（每列 `{isWarning, propertyName, errorMessage, severity}`），站沒建立。「逐站成敗」因此來自新增那一支；`indexer/test` 給**已存在**的站（200 空物件）。`?forceSave=true` **不會**跳過檢查。**測試通過不保證新增成功**（新增是另一次連站，時好時壞的站兩次可能不同；2026-10-06 審計 Internet Archive：test 通過、緊接新增回「連不上」，[wizard-audit](wizard-audit-2026-10-06.md) S1 頁 4）；頁 4 主鍵因此把「測過而加不進去」與「測試就沒過」分開記（M4 票 44）。
- **同名第二個站被拒**：400 `{"propertyName": "Name", "errorMessage": "Should be unique"}`；冪等靠呼叫端先 `GET /api/v1/indexer`。
- schema 的 `appProfileId` 是 **0**，原樣送建不起來，要換成 `1`（內建同步設定檔）。
- 十個預設站的 `definitionName`：`nyaasi`、`dmhy`、**`Anidex`**（不是文件寫的 `AniDex`）、`animetosho-xyz`（唯一 `semiPrivate`）、`acgrip`、`mikan`、`1337x`、`yts`、`eztv`、`thepiratebay`。站名 Prowlarr 會改、機器名不會，清單釘 `definitionName`。
- 這一輪十站五成五敗（`nyaasi` 查得到但沒結果、`Anidex` 與 `animetosho-xyz` 連不上、`1337x` 與 `eztv` 被 CloudFlare 擋）。**幾個公開站連不上是常態**，UI 逐站顯示。容器預設憑證驗證會擋 TLS 被攔截的環境（`config/host.certificateValidation`），是使用者環境的事，Berth 不改。
- 每個定義帶 `language`（BCP 47：dmhy `zh-TW`、ACG.RIP / Mikan `zh-CN`、其餘 `en-US`）與 `description`（一句英文），皆 nullable string（2026-09-24 / 09-25，2.5.2.5491）。
- **AniDex 定義還在、站連不上**（2026-09-25，票 06e）：`Anidex` 是 C# 內建，2.5.2.5491 schema 仍有；`indexer/test` 回 `Unable to connect to indexer ... [502:BadGateway]`，anidex.info 直打也 502（09-08 也連不上）。預設清單因此拿掉它，理由是站掛了、不是定義消失。
- **空白查詢回各站最新發佈**（2026-09-25）：`GET /api/v1/search?query=&indexerIds=<id>&type=search` 對 dmhy 80 筆、YTS 96 筆，各約 1.3 秒。精靈試搜（票 06e）以它當預設；`indexerIds` 限定單站才分得出哪站失敗。
- **`indexerIds` 可帶多站（重複帶 `indexerIds=3&indexerIds=7`），空的是每一個啟用中的站**（2026-10-09，M4 票 77，原始碼 [`SearchResource.cs`](https://github.com/Prowlarr/Prowlarr/blob/develop/src/Prowlarr.Api.V1/Search/SearchResource.cs)）；帶的站全不可用回 400。M4 票 107 拿掉請求預算後搜尋不帶它（問全部），只剩精靈逐站試搜在用。
- **`indexer/test` 也測得了還沒加入的定義；搜尋只吃已加入的站**（2026-09-30，berth-lab `bundled` 的 Prowlarr 2.6.5.5623，M4 票 09）：把 schema 定義原樣送（`appProfileId` 換 1），通過 **200 `{}`**（YTS 1.9 秒、dmhy 1.1 秒），不通過 **400 加逐條理由**；都**不建立任何東西**（測完 `GET /api/v1/indexer` 仍 0 站）。`GET /api/v1/search?indexerIds=99999` 回 400「Search failed due to all selected indexers being unavailable」——`indexerIds` 只認已加入的站，所以「加入之前先搜」做不到；流程是「測試 → 勾通過的 → 加入 → 逐站 / 全部試搜 → 不要的移除」。錄下的拒絕原文在 `tests/fixtures/http/prowlarr/indexer-test.rejected.*.json`，畫面分 Cloudflare（`Unable to access 1337x.to, blocked by CloudFlare Protection.`）/ 查無結果（`Query successful, but no results were returned …`）/ 連不上（`Unable to connect to indexer. This is typically caused by DNS/SSL issues. …`）/ 其他四種。
- **schema 的公開站**：645 個定義，privacy `public` 88、`semiPrivate` 64、`private` 493。NZBIndex 是 usenet（`protocol: usenet`，Berth 只接 qBittorrent）；`Torrent RSS Feed` 的 `definitionName` 出現兩次。所以「全部公開站」只收 `protocol == torrent`、依 `definitionName` 去重。
- **TMDB 兩種憑證都打得動 v3 端點**：v4 read access token 走 `Authorization: Bearer`（官方建議、不進網址），v3 的 32 字元 API key 走 `?api_key=`；key 不對回 401。Berth 認憑證**形狀**，貼哪種都成立。

**索引站搜尋實測**（2026-09-10，票 08；Prowlarr 2.5.2.5491 + 五個公開站 acgrip / dmhy / mikan / thepiratebay / yts；Torznab fixture 已刪，M4 票 37；[細節](setup-api-facts.md#索引站搜尋實測)）

- **`GET /api/v1/search` 很慢且不吃 `limit`**：單次冷查詢 60–85 秒，`limit=20` 仍回 1200 筆；三個查詢併發共 35 秒，所以逐標題併發、逾時給 120 秒。
- **`downloadUrl` / `magnetUrl` 每次請求都不同**（`link=` 密文帶 nonce，連跑兩次 1021 筆只重疊 1 筆），`guid` 穩定（1200/1200）：身分是 infohash 或 `guid`，不是下載網址。兩者是 Prowlarr **自己的代理網址**（主機來自它的 `config/host`）；磁力站（TPB、dmhy）沒有 `downloadUrl`，只有包成代理網址的 `magnetUrl`。**兩者帶 `?apikey=<Prowlarr API key>`**（M4 票 76），能改 Prowlarr 設定，所以不出伺服器（M4 票 79）：搜尋把每列連結記在 Berth 程序，前端只拿 id，送單收 id 換回連結（慣例照 Sonarr interactive search 的 `ReleaseController.cs`：`{indexerId}_{guid}` 快取 30 分鐘、找不到回 404「try searching again」；Berth 的 id 隨機、記兩小時，理由在 `berth/services/sources.py`）。
- **info hash 兩種寫法**：同一發佈在 Mikan 是 40 字十六進位、dmhy 是 32 字 base32，解碼後位元組相同；不正規化的話 1200 筆裡 47 筆重複顯示。
- **多標題是真的多一批東西**：`Spy x Family` / `SPY×FAMILY` / `间谍过家家` 各 1200 / 908 / 1210 筆，聯集 1854，各自帶來 391 / 196 / 169 筆另兩者問不到的結果。
- **tmdbid 是私站的功能**：627 份定義裡 93 份的 `tvSearchParams` / `movieSearchParams` 含 `tmdbId`，**全是 private 或 semiPrivate**；十個預設公開站一個都沒有（YTS 只有 `imdbid`）。所以 `q=` 才是常態（Prowlarr REST 本來只收關鍵字）。
- **分類碼不是可靠篩子**：dmhy 對 `cat=5000`、`cat=5070`、不帶 `cat` 都回同樣 80 筆，且一筆帶 5070 / 100002 / 2020 而沒有 5000。Berth 不送 `categories`，分類只當顯示資料。
- **The Pirate Bay 對搜不到的關鍵字回自己的熱門清單**（搜 SPY×FAMILY 前六筆是 Spider-Man、Ted Lasso 等，做種四千到六千），純做種排序會把真結果擠出前 100 筆；Berth 先用標題粗篩再逐站輪流取。
- **公開中文站做種數是個位數**：Mikan / ACG.RIP / dmhy 多半 0–2 個，TPB scene 28–86；取「做種前 100 筆」等於把中文字幕組整批刪掉。
- **`parse_release` 每筆 14 毫秒**（1200 筆 17.4 秒，含 guessit），全解析會卡事件迴圈半分鐘，所以粗篩用純字串比對，解析只跑留下的 100 筆。

**Jackett**（[repo](https://github.com/Jackett/Jackett)；[細節](setup-api-facts.md#jackett)）

- API key 在 `ServerConfig.json` 的 `APIKey`；聚合 Torznab `/api/v2.0/indexers/all/results/torznab/api?t=search` 有文件（上限 1000 筆、站專屬分類不可用）；`GET/POST /api/v2.0/indexers/{id}/Config` 只是 UI 內部介面、無文件。有 `mikan.yml`、`dmhy.yml`、`nyaasi.yml`、`acgrip.yml`。
- ~~結論維持原決定：套件預設 Prowlarr，Jackett 以 Torznab 端點接入。~~ **已不採用**（2026-10-06 D3、M4 票 37）：只支援 Prowlarr；以上留作紀錄（[ADR-0001](../adr/0001-indexer-manager-prowlarr-only.md)）。

**compose 套件實測**（2026-09-07，Windows 11 + Docker Desktop 29.6.2，票 03；[細節](setup-api-facts.md#compose-套件實測)）

- **發佈 port 的來源位址**：Docker Desktop 把 `-p 8080:8080` 進來的流量 SNAT 成 bridge 閘道（`172.28.0.1`），閘道本身就在 compose 網段內。所以 `WebUI\AuthSubnetWhitelist=172.28.0.0/16` 等於讓宿主與 LAN 任何人免密打 qBittorrent API（實測 `curl http://localhost:8080/api/v2/app/version` 直接回 `v5.2.3`）。縮成 Berth 容器固定 IP `172.28.0.2/32` 後：berth 容器 200、宿主 403、同網段其他容器 403。§16.3「LAN 使用者開 8080 仍要密碼」只有白名單是單一位址時才成立。
- Docker 動態 IP 從網段開頭配發（`172.28.0.2` 給了先啟動的 prowlarr），固定 IP 要靠 `ip_range` 把動態池隔到別段，否則會撞。
- **linuxserver/qbittorrent 啟動順序**：`init-qbittorrent-config` 排在 `init-custom-files`（custom-cont-init.d）之前，腳本跑到時 `/config/qBittorrent/qBittorrent.conf` **一定已存在**（image 從 `/defaults/qBittorrent.conf` 複製）。所以「檔案不存在才寫」永不成立，改「缺鍵才補」。
- **缺鍵才補的另一面：在 WebUI 關掉或改掉白名單，重啟補不回來**（M4 票 53，2026-10-07，`5.2.3_v2.0.15-ls478`）：以 `app/setPreferences` 的 `bypass_auth_subnet_whitelist_enabled: false` 關掉後 `docker restart`，腳本印 `already configured`，`WebUI\AuthSubnetWhitelistEnabled=false` 不變。補法在 WebUI「選項 → WebUI → 驗證」的「讓已在白名單中的 IP 子網路略過驗證」（英文 *Bypass authentication for clients in whitelisted IP subnets*；標籤取自 qBittorrent `release-5.0.0` 的 [`preferences.html`](https://github.com/qbittorrent/qBittorrent/blob/release-5.0.0/src/webui/www/private/views/preferences.html) 與 [`webui_zh_TW.ts`](https://github.com/qbittorrent/qBittorrent/blob/release-5.0.0/src/webui/www/translations/webui_zh_TW.ts)）。
- `/defaults/qBittorrent.conf`：`LegalNotice\Accepted=true`、`WebUI\Address=*`、`WebUI\ServerDomains=*`、`Downloads\SavePath=/downloads/`、`Downloads\TempPath=/downloads/incomplete/`、`Connection\UPnP=false`、`Connection\PortRangeMin=6881`。整份覆蓋會掉 `LegalNotice\Accepted`（qbittorrent-nox 卡在法律聲明）；`ServerDomains` 預設 `*` 本來就過 Host 檢查，寫死 `qbittorrent` 反讓使用者從 `localhost:8080` 進不去。
- `init-custom-files` 只檢查 executable bit（不檢查擁有者），以 `/bin/bash <script>` 執行（[docker-baseimage-alpine](https://github.com/linuxserver/docker-baseimage-alpine/blob/master/root/etc/s6-overlay/s6-rc.d/init-custom-files/run)、[container-customization](https://docs.linuxserver.io/general/container-customization/)）。`lscr.io/linuxserver/qbittorrent:latest` 當時是 v5.2.3。
- Berth image（node:24-slim build → python:3.13-slim runtime）：281 MB 未壓縮、62.8 MB gzip，遠低於 400 MB 上限。`python:3.13-slim`（Debian 13 trixie）內建 `setpriv`、`usermod`、`groupmod`、`getent` 與 tzdata，`PUID` / `PGID` 降權不需裝 gosu；但沒有 curl。
- 空 named volume 與 Docker 替 bind mount 新建的目錄都是 `root:root`，非 root 容器寫不進去。入口腳本因此只在 `/data` 還是空目錄時接手擁有者，有內容的媒體根不碰（實測：空目錄 → `1500:1500`、`umask 002`；非空 → 維持 `root:root`）。
- compose 內 `/data` 硬鏈接再確認：`dev=70`、inode 相同、`nlink=2`（與本節開頭 Windows 實測一致）。

**TMDB 憑證由使用者自備**（2026-09-09 決定，推翻本節原本的「沿用 Seerr 的專案級 key」；[細節](setup-api-facts.md#tmdb-憑證由使用者自備)）

- Jellyseerr / Seerr 在 `server/api/themoviedb/index.ts` 寫死專案 key（[overseerr#3887](https://github.com/sct/overseerr/issues/3887)）；Jellyfin 團隊也討論過（[jellyfin#36](https://github.com/jellyfin/jellyfin/issues/36)）。TMDB 條款只區分商業與非商業，未明文規範「一 app 一 key」，那條路走得通，**本系統仍不走**：共用憑證由專案背用量與行為，TVDB ToS 明文擋的正是這件事（§20.3），兩個 provider 在「使用者自己申請」上對稱。
- 憑證唯一來源 `settings.services.tmdb.api_key`，精靈第 6 步是**必填閘門**（plan §9.3）。申請：themoviedb.org 免費帳號 → 設定 → API → 用途選 Personal / Education，即時核發；同一頁給 v3 key 與 v4 read access token，兩種形狀 Berth 都收（plan §8.3，2026-09-08）。

**qBittorrent 預置**（[sessionimpl.cpp](https://github.com/qbittorrent/qBittorrent/blob/master/src/base/bittorrent/sessionimpl.cpp)、[linuxserver/qbittorrent](https://docs.linuxserver.io/images/docker-qbittorrent)、[qbittorrent-nox](https://github.com/qbittorrent/docker-qbittorrent-nox)；[細節](setup-api-facts.md#qbittorrent-預置)）

- 4.6.1 起首次啟動用隨機臨時密碼印在 log；已知密碼要預置 `WebUI\Password_PBKDF2`（PBKDF2-HMAC-SHA512、100000 次）。官方 image 沒有密碼環境變數，也沒有 `PUID` / `PGID`；linuxserver image 有，設定檔在 `/config/qBittorrent/qBittorrent.conf`。
- `[Preferences]`：`WebUI\Port`、`WebUI\AuthSubnetWhitelistEnabled`、`WebUI\AuthSubnetWhitelist`、`WebUI\LocalHostAuth`、`WebUI\HostHeaderValidation`、`WebUI\CSRFProtection`；`[BitTorrent]`：`Session\DefaultSavePath`、`Session\TempPath`、`Session\TempPathEnabled`、`Session\DisableAutoTMMByDefault`（**預設 true，即 autoTMM 關閉**）、`Session\DisableAutoTMMTriggers\CategorySavePathChanged`、`Session\Port`。
- Web API `app/setPreferences` 對應鍵：`temp_path_enabled`、`temp_path`、`save_path`、`auto_tmm_enabled`、`category_changed_tmm_enabled`、`bypass_auth_subnet_whitelist(_enabled)`、`bypass_local_auth`、`web_ui_password`（只寫，讀回來的偏好沒有它）。

**Jellyfin 命名實測**（2026-09-07，票 04；`jellyfin/jellyfin:10.10.7` 與 `:10.11.11`，dummy 檔 + API 查驗；[完整結果](m0-experiments.md#1-jellyfin-命名10107-與-101111)、[原文](setup-api-facts.md#jellyfin-命名實測)）

- `S01E01` 一律認得，`S01E03-E04` → `IndexNumber=3` + `IndexNumberEnd=4`，`S00E01` 進 `Specials`。**方括號與 `+` 不會滲進 Series 或 Episode 名稱**（Jellyfin 不從檔名取集標題）。
- **電影多版本**：檔名在 ` - ` 之前必須與資料夾名一字不差（含 `[tmdbid-<id>]`），否則成兩部獨立電影；標籤含方括號沒問題（版本選單顯示 `[BD][2160p][CHT+JP][Sakurato]`），結尾 `p`/`i` 的標籤依解析度降冪，其餘字母序。§7.2 已據此更正。
- **劇集多版本**：未裝插件 → 同集兩檔變兩個重複 Episode；裝 MergeVersions 跑 `MergeEpisodesTask` → 合成 1 個 Episode、2 個 MediaSource，但**版本標籤是整個檔名主幹**非只有 tags，順序不保證（10.10 與 10.11 相反）。§7.7 已據此更正；12.x 不裝插件就原生合併，見 §20.9。
- **extras**：`<作品>/extras/`、`<作品>/Season 01/extras/`、`<電影>/extras/` 三者都成立，掛在 Series / Season / Movie 的 `SpecialFeatures`，不當正片。
- **外掛字幕**：`<stem>.CHT.zh.ass` 在 10.10 顯示 `CHT - Chi - ASS - 外部`、10.11 `CHT - Chinese - ASS - 外部`（繁簡分得出來）；`.default.` 兩版都生效；`zh-Hant`/`zh-Hans` **只有 10.11 認得**，10.10 顯示「未定義」→ 不採用。
- 深連結 `#!/details?id=…&serverId=…` 兩版都開得到詳細頁。
- **精靈**：`POST /Startup/User` 之前**必須先 `GET /Startup/User`**（它建立預設使用者），否則回 **500**（`Sequence contains no elements`）。`POST /Library/VirtualFolders` 的 body 是 `AddVirtualFolderDto`，`LibraryOptions` **要包一層**（`{"LibraryOptions": {...}}`），直接送一樣回 204 但整份設定被靜默丟掉。
- **MergeVersions**：`POST /Packages/Installed/Merge%20Versions?assemblyGuid=…` 不必指定版本（10.10.7 裝到 `10.10.0.5`、10.11.11 裝到 `10.11.0.1`）；下載由 Jellyfin 連 GitHub，遇過 TLS 中斷回 500，要能重試。以上是 M0 對 10.x 的紀錄；本系統只支援 12 以上、不再安裝（[ADR-0002](../adr/0002-jellyfin-12-minimum-pinned-image.md)）。排程任務 `Name` 為 `Merge All Episodes` / `Merge All Movies`，`Category` 為 `Merge Versions`。
- **重啟後不能只等 `/System/Info/Public`**：它在伺服器載入中就回 200，這時管理員 API（如 `/ScheduledTasks`）回 **503「Jellyfin 伺服器載入中」**；要輪詢真正要用的端點回 200 才算完成。
- **`find_episodes` 陷阱**：10.11 第一次掃描後，已被 provider 認出的 Series，`/Items?parentId=<seriesId>` 與 `/Shows/{id}/Episodes` **都回 0**，再掃一次才正常；10.10、12.0.0 沒有（§20.8）。改用 `parentId=<library>&recursive=true` 再照 `Path` 前綴篩選，四種情況都對。

**qBittorrent 版本矩陣**（2026-09-07，票 04；`lscr.io/linuxserver/qbittorrent:4.4.5`（API 2.8.5）與 `:5.2.3`（API 2.15.1）；[完整結果](m0-experiments.md#2-qbittorrent-445-與-523)、[原文](setup-api-facts.md#qbittorrent-版本矩陣)）

- **`torrents/add` 回應形狀兩版不同**（2026-09-10 票 09 對兩台乾淨容器實測，fixture `tests/fixtures/http/qbittorrent/torrents-add.*`）：4.4.5 成功 `200` + `Ok.`；**5.2.3 成功 `200` 加 JSON 摘要**（`{"added_torrent_ids": […], "failure_count": 0, "pending_count": 0, "success_count": 1}`），推翻原本「一律回 `Ok.`」。失敗也說得出話：同一磁力連結第二次送在 5.2.3 是 `409 Conflict`（4.4.5 照回 `Ok.`），category 的 save path 當下用不了也是 `409`；multipart 上傳非 torrent 是 `415` 加檔名與原因。
- **交 http 網址給 `torrents/add` 是背景抓取**：5.2.3 回 `202` + `pending_count: 1`，抓失敗後**永遠沒有下文**，用戶端已回過 2xx。所以 Berth 自己先抓 torrent（`adapters/torrent.py`），交出去的一律是磁力連結或位元組，「收不收」當場有答案（票 09）。
- **`paused` 與 `stopped` 各版本只認一個，送錯的靜默地開始下載**（`torrents/add` 一律 200，不認得的參數不報錯）：4.4.5 `paused=true` → `pausedDL`、`stopped=true` → `queuedDL`；5.2.3 `paused=true` → `stalledDL`、`stopped=true` → `stoppedDL`。plan §8.1 的版本判斷是必要條件，不是最佳化。
- **`torrents/files[].name` 相對 `save_path`**（多檔含 torrent 根目錄那一層），四種 `contentLayout` 組合都成立；`content_path` = save_path + 根目錄，單檔指向檔案、多檔指向目錄。單檔 + `Subfolder` 的子資料夾名是去掉副檔名的 torrent 名。**`save_path` 尾斜線兩版不同**（4.4.5 `/downloads/`、5.2.3 `/downloads`），組路徑前要正規化。
- **沒下完時 `content_path` 在分類的未完成目錄，`save_path` 已是完成後的位置**（2026-10-13 M4 票 74，5.2.4）：`berth-tv` 分類下 `stalledDL` 的一包，`save_path=/data/torrent/complete/tv`、`download_path=/data/torrent/incomplete/tv`、`content_path=/data/torrent/incomplete/tv/<根目錄>`；`torrents/files[].name` 仍相對那一層。刪下到一半的包看 `content_path`（`services/deletion._where_files_are`）。
- `torrents/files` 的鍵兩版相同：`index`、`name`、`size`、`progress`、`priority`、`is_seed`、`piece_range`、`availability`。`torrents/categories` 兩版都回駝峰 `savePath`（沒有 `save_path`）；5.2.3 另有 `download_path`、`ratio_limit`、`seeding_time_limit`、`inactive_seeding_time_limit`、`share_limit_action`。
- **Host 檢查除網域還比對 port**：`ServerDomains=*` 也擋 port 不符（`Host: localhost:18080` → **401**，容器 log `Invalid Host header, port mismatch`）。設成 `qbittorrent` 後 `localhost:8080`、`127.0.0.1:8080` 全被擋；沒有 port 的 Host 一律放行。偏好鍵 `web_ui_host_header_validation_enabled`（兩版都有）。實驗改的是 runtime 偏好 `web_ui_domain_list`（對應 `WebUI\ServerDomains`），沒另測「預置 ini 鍵」路徑。→ compose 的 qBittorrent **發佈 port 只能內外兩側一起改**（只改外側使用者開不了 WebUI）：M3 票 06b 以 `QBITTORRENT_WEBUI_PORT` 同時設兩側與 `WEBUI_PORT`（plan §9.2）。
- **CSRF**：送了 `Origin`/`Referer` 就必須與 Host 一致（不一致 → 401），完全不送則放行；兩版相同。

**Prowlarr `config/host`**（2026-09-07，票 04；Prowlarr 2.5.2.5491；[細節](setup-api-facts.md#prowlarr-host-config)）

- `GET /api/v1/config/host` 回 39 個欄位；認證相關：`authenticationMethod`（`none`/`basic`/`forms`/`external`）、`authenticationRequired`（`enabled`/`disabledForLocalAddresses`）、`username`、`password`、`passwordConfirmation`、`apiKey`。
- 設 Forms 帳密：`PUT /api/v1/config/host/1`，body 是完整 config/host 物件加上述五欄位（**少了 `passwordConfirmation` 會被拒**）→ 回 **202**，Prowlarr 隨即自行重啟，要等它回來。
- 設完後不帶 `X-Api-Key` 的 API 回 401，**`GET /ping` 仍匿名 200**（健康檢查不會因加密碼變紅，也是「回來了沒」的判準）；`password` 讀回來是雜湊。API key 從 `config.xml` 的 `<ApiKey>` 讀（與 plan §9.2 一致）。

**Jellyfin 帳號規則與伺服器的 metadata 語言**（2026-10-03，M4 票 29；原始碼 v12.1 的 [UserManager.cs](https://github.com/jellyfin/jellyfin/blob/v12.1/Jellyfin.Server.Implementations/Users/UserManager.cs)、[StartupController.cs](https://github.com/jellyfin/jellyfin/blob/v12.1/Jellyfin.Api/Controllers/StartupController.cs)、[ConfigurationController.cs](https://github.com/jellyfin/jellyfin/blob/v12.1/Jellyfin.Api/Controllers/ConfigurationController.cs)、[ServerConfiguration.cs](https://github.com/jellyfin/jellyfin/blob/v12.1/MediaBrowser.Model/Configuration/ServerConfiguration.cs)；實測 `scripts/experiments/jellyfin_username_rules.py`；[細節](setup-api-facts.md#jellyfin-帳號規則與-metadata-語言)）

- **帳號**：`ThrowIfInvalidUsername` 要求不空白、符合 `ValidUsernameRegex` = `^(?!\s)[\w\ \-'._@+]+(?<!\s)$`、不是 `.` 或 `..`；違規丟 `ArgumentException` → HTTP 400。.NET 的 `\w` 是 `[\p{L}\p{Mn}\p{Nd}\p{Pc}]`，中日文帳號照收；`< > & " / \ : #` 與空格以外的空白（tab）不收，前後不能是空白。master 與 release-12.z 同一條；建立（`CreateUserAsync`）與改名（`RenameUser`）都過它。前端照它先擋（`web/src/setup/jellyfinUsername.ts`）。
- **`POST /Startup/User` 的順序**：第一個使用者已有密碼 → **403**；密碼 `IsNullOrWhiteSpace` → **400** `Password must not be empty`；然後 `UpdateUserAsync`、**名字不同才 `RenameUser`**（帳號在這裡被拒）、最後 `ChangePassword`。帳號被拒時密碼沒設，第一個使用者仍「沒有密碼」，改名再送即可。
- **`GET /System/Configuration`** 掛 `[Authorize]`（任何登入使用者，API key 也行），回 `ServerConfiguration`：`PreferredMetadataLanguage`（預設 `en`）、`MetadataCountryCode`（預設 `US`）、`UICulture`（預設 `en-US`）——`/Startup/Configuration` 寫的就是這三格。套件內媒體庫照前兩格建（plan §9.4 第 4 步），fixture `tests/fixtures/http/jellyfin/system-configuration.json`。
- **實測**（`lscr.io/linuxserver/jellyfin:version-12.1ubu2604`，一次性容器）：精靈期間 `POST /Startup/User` 對 `a<b`、`a>b`、`a&b`、`a"b`、`a/b`、`a`、`a:b`、`a#b`、含 tab、`.`、`..` 都回 **400 `Error processing request.`**（原文不說是帳號問題，所以畫面只能說「那一段沒做完」），每次之後都能再試；只有空白的密碼回 400 `Password must not be empty`；`船長 01` 回 204。管理員之後 `POST /Users/New`：`skipper`、`o'brien`、`a.b@c+d-e_f`、`José`、`ナミ`、`..x` 收（200），`a<b`、`.`、` lead` 拒（400）。`GET /System/Configuration` 帶 token 200、讀回剛寫的 `zh-TW` / `TW`，匿名 401。

**硬鏈接腳本**（`scripts/experiments/hardlink.sh`，2026-09-07；[細節](setup-api-facts.md#硬鏈接腳本)）

- Linux ext4 單一掛載根：PASS（nlink=2、inode 相同）。Windows NTFS bind mount（9p）：PASS（dev=70）。`torrent/` 與 `library/` 分兩個 volume：`ln: Cross-device link`，退出碼 1。
- ext4 那一輪來源是 **Docker Desktop 自己的 Linux VM**（daemon 端檔案系統，與原生 Linux 宿主同一條 `link()` 路徑，但**不是另一台實體 Linux**）。腳本無相依，NAS 上 `sh hardlink.sh /volume1/<share>` 可跑。2026-10-08 在 Unraid 7.1.4 user share 上 PASS（§20.14）；其他原生 Linux 宿主與 NAS 尚未實測（§20.6）。

### 20.17 部署檔的 release 附件與「最新版」連結（2026-10-08 查證，M4 票 56）

全文與來源在 [`docs/research/deploy-and-jellyfin-identity.md`](deploy-and-jellyfin-identity.md)。

> **2026-10-09 被取代、2026-10-13 部分恢復**：M4 票 71 把部署改成只用 compose 檔加 `.env`、不附檔案（zip 拿掉，見 §20.18 與 [ADR-0009](../adr/0009-deploy-compose-and-env.md)）；M4 票 97 恢復附件，但只附那兩個純文字檔 `docker-compose.yml`、`example.env`，不附 zip（[ADR-0009](../adr/0009-deploy-compose-and-env.md)）。下面講 `latest/download` 那一條裡的 zip 已不存在，其餘事實照用。

- **開頭是 `.` 的附件名會被 GitHub 改掉**（2026-10-13 查證，M4 票 97）：REST API〈Upload a release asset〉——「GitHub renames asset filenames that have special characters, non-alphanumeric characters, and leading or trailing periods」，改成什麼沒有寫（[docs.github.com](https://docs.github.com/en/rest/releases/assets#upload-a-release-asset)）；同名附件再傳是 422，要先刪（`gh release upload --clobber`）。所以 `deploy/.env.example` 照 Immich 以 `example.env` 上傳，release workflow 先把兩個檔 `cp` 成要的名字再傳。
- **`https://github.com/<owner>/<repo>/releases/latest/download/<附件名>` 直接下載最新版本的同名附件**（[Linking to releases](https://docs.github.com/en/repositories/releasing-projects-on-github/linking-to-releases)）；每一版都要有同名附件，README 才能寫死連結。Immich 的安裝步驟就是這樣拿 compose 與 `example.env`（[docs.immich.app](https://docs.immich.app/install/docker-compose)）。
- **「最新」只算正式版本**：非 prerelease、非 draft，依 `created_at` 排（[Get the latest release](https://docs.github.com/en/rest/releases/releases#get-the-latest-release)）。所以 `-rc` 的 release 標成 prerelease 就不會動到 `latest/download`，與 GHCR 的 `:latest` 規則一致。
- **`gh release create`**：`--prerelease`、`--verify-tag`；帶附件的 `create` 先建草稿、傳完附件才發佈，失敗時刪掉草稿（`draftWhileUploading`，[create.go](https://github.com/cli/cli/blob/trunk/pkg/cmd/release/create/create.go)），所以 `latest/download/` 不會指到還沒有附件的新版。release 已存在時改用 `upload --clobber`。

### 20.18 preseed 腳本內嵌進 compose：`configs.content` 加 `mode`（2026-10-09 查證＋實測，M4 票 70）

全文、實測表與來源在 [`docs/research/deploy-and-jellyfin-identity.md`](deploy-and-jellyfin-identity.md)。部署要只剩 compose 檔加 `.env`（使用者 2026-10-09 拍板，推翻 [ADR-0009](../adr/0009-deploy-compose-and-env.md) 記的前一版決定），qBittorrent 的白名單腳本因此內嵌進 compose，不再是旁邊的 `preseed/` 目錄。

- **Docker 文件**：頂層 `configs` 的 `content` 從 Compose 2.23.1 起支援，內容會做變數展開（[configs](https://docs.docker.com/reference/compose-file/configs/)、[v2.23.1](https://github.com/docker/compose/releases/tag/v2.23.1)）；預設權限 0444，服務 `configs` 長語法的 `mode` 可覆寫（[services#configs](https://docs.docker.com/reference/compose-file/services/#configs)）。
- **`mode` 是成敗關鍵**：linuxserver 的 init 只執行 `-x` 的檔（`/etc/s6-overlay/s6-rc.d/init-custom-files/run` 對 `/custom-cont-init.d/*` 做 `[[ -x ]]`），0444 的預設一定不會跑，log 只有 `10-berth.sh: is not an executable file`，qBittorrent 照常起來但沒有白名單，Berth 進不去。漏掉 `mode` 不會報錯。
- **實測**（`scripts/experiments/inline_preseed.py`）：Docker Desktop Windows（Compose v5.3.1）、獨立二進位（v2.40.3）、rootless VM（v5.3.1）三個環境結果相同。`mode: 0555` 時內容與原檔 sha256 相同、首次啟動依序印 `executing`、`added`、`exited 0`，之後 `restart`、`--force-recreate` 都 `already configured`，且鍵各一行、`BERTH_IP` 200 而宿主 403；`COMPOSE_PROFILES=` 空時 `up -d` 回 0 無警告；不需要 `uid` / `gid`。Unraid 隨身碟（vfat）上沒有實測，推論無妨（執行期不讀 compose 目錄）。
- **坑**：`docker compose config` 的輸出會把 `$` 再轉義成 `$$`，拿它驗內容等於沒驗；抽出腳本做測試時要把 `$$` 還原成 `$`。`mode` 寫 `0555` 的前導 0，兩個版本都讀成 555。比 2.40.3 舊的 Compose 沒有量。
- **決定的寫法**：compose 頂層 `configs.qbittorrent-preseed.content` 放 `10-berth.sh` 全文（每個 `$` 寫成 `$$`），服務的 `configs` 用 `source: qbittorrent-preseed`、`target: /custom-cont-init.d/10-berth.sh`、`mode: 0555`（完整 YAML 在研究檔）。
- **閘門**（票 71）：`tests/unit/test_qbittorrent_preseed.py` 守著 `content` 沒有未轉義的 `$`、target 在 `/custom-cont-init.d/`、`mode` 帶執行位元；`tests/unit/test_deploy_mounts.py` 守著 compose 的宿主路徑沒有相對的。重量：`docs/development/experiments.md`。

### 20.25 HTTP 下的瀏覽器與發版的閘門（2026-10-30 查證與實測，0.4.1 之後）

- **Secure context**：網址是 HTTPS 或 loopback（`localhost`、`127.0.0.1`）的頁面才是 secure context；使用者用區網 IP 走 HTTP 開 Berth（`http://192.168.x.x:8383`）時不是。只在 secure context 才有的 API 這時是 `undefined`：`crypto.randomUUID`、`crypto.subtle`、`navigator.clipboard`、`navigator.serviceWorker` 等。`crypto.getRandomValues` 哪裡都有。【[MDN〈Secure contexts〉](https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Secure_Contexts)、[`Crypto.randomUUID()`](https://developer.mozilla.org/en-US/docs/Web/API/Crypto/randomUUID)】0.4.0 因此在 HTTP 下整頁 crash；實測（Edge 156、`http://192.168.50.150:8383`）`isSecureContext` 是 `false`、`crypto.randomUUID` 是 `undefined`。playwright 開 `127.0.0.1` 與 jsdom 都看不到這一類錯；`.test` 網域經 Chromium 的 `--host-resolver-rules` 指回本機時不是 secure context（`web/e2e/insecure-origin.spec.ts` 先斷言這一點）。
- **GitHub Actions 的 reusable workflow**：被呼叫的 workflow 裡 `github` context 屬於呼叫端，`github.workflow` 是呼叫端的名字，所以 concurrency group 用 `${{ github.workflow }}` 會與呼叫端或另一個被呼叫的撞在同一組；`uses: ./.github/workflows/x.yml` 用的是呼叫端同一個 commit 的檔；`secrets: inherit` 把 repo secret 傳下去。【[Reusing workflow configurations](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations)】`release.yml` 因此呼叫 `ci.yml`、`e2e.yml` 當閘門，兩邊的 group 寫死成 `ci-` / `e2e-` 開頭（`docs/development/release.md`）。
