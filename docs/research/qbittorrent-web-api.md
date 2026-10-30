# qBittorrent Web API 與硬鏈接 / Docker 限制

從 design-brief §20.2 搬來（原文逐字，未改字；`##` / `###` 小標是搬來時加的，方便連結）。brief 只留結論與連結，細節以本檔為準。

### 20.2 qBittorrent Web API 與硬鏈接 / Docker 限制

來源：qBittorrent master 原始碼（`torrentscontroller.cpp`、`serialize_torrent.cpp`）、`WebAPI_Changelog.md`、qbittorrent-api 客戶端文件、TRaSH Guides、Servarr wiki、man pages。**社群 wiki 的 API 頁面已過時**（連「5.0」頁面都還列 `paused` / `root_folder`），以原始碼為準。

## torrents/add 參數與回應

**`torrents/add` 現行參數**（[torrentscontroller.cpp](https://raw.githubusercontent.com/qbittorrent/qBittorrent/master/src/webui/api/torrentscontroller.cpp)）

- `urls` / `torrents`、`savepath`、`downloadPath` + `useDownloadPath`、`category`、`tags`、`rename`、`autoTMM`、`contentLayout`（`Original` / `Subfolder` / `NoSubfolder`，API 2.7 / qB 4.3.2 起，取代 `root_folder`）、`stopped`（API 2.11.0 起取代 `paused`）、`stopCondition`、`seedMode`（API 2.16.0 起，同時移除 `skip_checking`）、`filePriorities`、`ratioLimit` / `seedingTimeLimit`（API 2.8.1）。
- master 已不讀 `paused` / `root_folder`。adapter 必須先讀 `app/webapiVersion`，依版本送 `paused` 或 `stopped`；`torrents/pause|resume` 在 5.0 改名 `stop|start`。
- **回應形狀兩版不同**（2026-09-10 票 09 實測，見 §20.7）：4.4.5 回 `200` + `Ok.`，5.2.3 回 `200` 加一份 JSON 摘要。只認 `Ok.` 的用戶端會把 5.x 上每一次成功的送單都判成失敗。
- 【決定】支援下限 qBittorrent 4.4（API 2.8.4，2022）；以 5.x 為主要測試目標。

## 分類與路徑

**分類與路徑**

- `createCategory` / `editCategory` 參數：`category`、`savePath`、`downloadPathEnabled`、`downloadPath`。per-category 未完成路徑自 API 2.8.4 / qB 4.4.0 即存在，但 WebUI 直到 **5.2.0** 才有介面管理（[Changelog](https://raw.githubusercontent.com/qbittorrent/qBittorrent/master/Changelog)）。本系統用它取代全域 `temp_path`（M4 票 22，§4.1）。
- **分類的 `downloadPath` 實測**（M4 票 22，`scripts/experiments/qbittorrent_category_download_path.py` 對 4.4.5 與 5.2.3 各跑一次，兩版結論相同；一台做種的 5.2.3 以 `addPeers` 直連、限速讓下載中看得到，torrent 照 Berth 的送單形狀加：`category` + `autoTMM=true`、不送 `savepath`）：

  | 情境 | 下載中檔案在 | 完成後 |
  | --- | --- | --- |
  | 分類 `downloadPathEnabled=true` + `downloadPath`，全域 `temp_path_enabled=false` | 分類的 `downloadPath`（torrent 報的 `download_path` 就是它） | 搬到分類的 `savePath` |
  | 同上，全域開著、指向另一個目錄 | 分類的 `downloadPath`：分類的贏 | 搬到 `savePath` |
  | 分類 `downloadPathEnabled=false`，全域開著 | 直接寫在 `savePath`：分類可以明說不走全域 | — |
  | 分類兩個欄位都不送，全域關著 | 直接寫在 `savePath` | — |
  | 分類兩個欄位都不送，全域開著 | 全域 temp path（5.2.3 在底下多一層分類名，4.4.5 不多） | 搬到 `savePath` |

  讀回 `torrents/categories` 的鍵是 **`download_path`**（不是駝峰）：設了是字串；停用兩版都是 `false`；沒設 5.2.3 是 `null`、4.4.5 **整個鍵不出現**。對已存在的分類再送 `createCategory` 兩版都是 409 `Unable to create category`。
- `torrents/categories` 回傳鍵在 4.4.0–4.4.1 曾在 `savePath` / `save_path` 之間反覆，adapter 兩者都要接受。
- `torrents/removeCategories`：表單欄位 `categories`，多個以 `
` 分隔，任何情況都回 200（[WebUI API（qBittorrent 5.0）](https://github.com/qbittorrent/qbittorrent/wiki/WebUI-API-(qBittorrent-5.0)#remove-categories)，4.1 起的文件同一支；context7 `/qbittorrent/qbittorrent` 查核，2026-10-07）。分類裡的 torrent 會變成沒有分類，所以 Berth 只送重數過是空的 `berth-*`（M4 票 47）。
- `createCategory` 的表單鍵是 `category`、`savePath`（Berth 另帶 `downloadPathEnabled`、`downloadPath`）；名稱空字串回 **400** `Category cannot be empty`，名稱不合法或建不起來（含同名已存在）回 **409** `Unable to create category`（查核 master 的 [torrentscontroller.cpp](https://github.com/qbittorrent/qBittorrent/blob/master/src/webui/api/torrentscontroller.cpp)，2026-09-08）。所以冪等要靠呼叫端先 `torrents/categories` 讀一次。
- autoTMM 開啟時 save path 跟隨 category；`category_changed_tmm_enabled` 為真時改 category 路徑會**自動搬移所有該分類 torrent**。→ 本系統建立 category 後不再改其 savePath；使用者改 Route 目標時建立新 category，舊 Job 維持原位。
- TRaSH 明確要求 category 模式必須 `Automatic`（autoTMM），否則下載不會進分類資料夾（[Basic-Setup](https://trash-guides.info/Downloaders/qBittorrent/Basic-Setup)）。

## 狀態與檔案

**狀態與檔案**

- `torrents/info` 欄位含 `hash`、`name`、`state`、`progress`、`save_path`、`content_path`（API 2.6.1）、`download_path`（原始碼有、wiki 未列）、`completion_on`、`category`、`tags`、`added_on`。
- `state` 值：`error`、`missingFiles`、`uploading`、`pausedUP`/`stoppedUP`、`queuedUP`、`stalledUP`、`checkingUP`、`forcedUP`、`allocating`、`downloading`、`metaDL`、`pausedDL`/`stoppedDL`、`queuedDL`、`stalledDL`、`checkingDL`、`forcedDL`、`checkingResumeData`、`moving`、`unknown`。「完成」判定：`progress == 1` 且 `completion_on > 0` 且 state **不是** `moving` / `checking*`（從 temp path 搬到 save path 期間 state 為 `moving`，此時不可入庫）。
- `torrents/files` 回傳 `index`、`name`（含相對路徑）、`size`、`progress`、`priority`（0 = 不下載）、`availability`。`name` 相對於 `save_path` 還是 `content_path` 文件未明 → adapter 以 `stat` 驗證組出的絕對路徑，兩種都試。`priority == 0` 的檔案要從 Plan 排除。
- 其他端點：`setLocation`、`rename`、`renameFile` / `renameFolder`（API 2.8.0）、`delete(deleteFiles)`、`setCategory`（category 不存在回 409）、`addTags`、`recheck`。
### torrents/delete 的確切形狀

- **`torrents/delete` 的確切形狀**（2026-09-22 對 `release-4.1.0` 到 `release-5.2.3` 共十個 tag 逐一核對原始碼，M2 票 04）：

  | 項目 | 事實 |
  | --- | --- |
  | 方法 | **一律 POST**。4.4.4 引入「方法不對回 405」的機制但 delete 不在白名單上（4.4.5 仍可 GET）；**4.5.0 起 delete 進了 POST 白名單，GET 從此是 405**（[`webapplication.h` 的 `m_allowedMethod`](https://github.com/qbittorrent/qBittorrent/blob/release-4.5.0/src/webui/webapplication.h)） |
  | 參數 | `hashes`（多個以 `\|` 分隔，特殊值 `all` 是全部）與 `deleteFiles`，**兩個都是必填**（`requireParams`），少一個回 400 |
  | `deleteFiles` 的值 | 只認字面 `true` / `false`（大小寫不敏感，`Utils::String::parseBool`）。**`1` 不是真**——解析不出來就退回 `false`，於是呼叫端以為檔案刪了而磁碟上還在。四個大版本都沒改過這一段 |
  | 回應 | 成功是 `200` + 空 body |
  | 不認得的 hash | **靜默成功**（`applyToTorrents` 找不到就跳過，整個請求仍是 200）。所以「移除 torrent」對早就不在客戶端的那一筆是成立的，不必先問一次 |

  5.0.0 的內部重構（`deleteTorrent` → `removeTorrent`）沒有改動對外的參數與回應。Berth 據此
  **不用 `deleteFiles=true` 刪檔**：那一筆 torrent 可能早就不在客戶端了（`client_removed`），
  而刪除範圍仍然要刪得掉磁碟上的東西、數得出刪了幾個、空出多少（§9.2、`services/deletion.py`）。
### torrents/recheck 與重新開始

- **`torrents/recheck` 與「重新開始」**（2026-09-23 M2 票 09c：原始碼對 `release-4.4.5` / `release-5.2.3` 逐行核對，
  再對兩版容器實測，`scripts/experiments/qbittorrent_recovery.py`，錄製在 `tests/fixtures/http/qbittorrent/`）：

  | 項目 | 4.4.5（Web API 2.8.5） | 5.2.3（Web API 2.15.1） |
  | --- | --- | --- |
  | 重新開始的端點 | `torrents/resume` | `torrents/start`；**`torrents/resume` 是 `404 Endpoint does not exist`**，沒有別名。改名在 5.0.0（Web API 2.11.x，與 `paused` → `stopped` 同一次，[discussion #21554](https://github.com/qbittorrent/qBittorrent/discussions/21554)） |
  | 參數 | `hashes`（`\|` 分隔、`all`），必填，少了是 400 | 同左 |
  | 方法 | GET 也行（4.4.5 的 POST 白名單只有 `add` 那幾支，[`webapplication.h`](https://github.com/qbittorrent/qBittorrent/blob/release-4.4.5/src/webui/webapplication.h)） | **只收 POST**，`recheck` / `start` / `stop` 都在白名單上，GET 是 405（[`webapplication.h`](https://github.com/qbittorrent/qBittorrent/blob/release-5.2.3/src/webui/webapplication.h)） |
  | 成功 | `200` + 空 body（兩支都是） | `200` + 空 body（實測；changelog 說 2.15.0 起空結果回 204，這兩支沒有） |
  | 不認得的 hash | 靜默成功（`applyToTorrents` 跳過） | 同左 |
  | recheck 之後 | state 先是 `checkingDL` / `checkingUP`；停住的 torrent 校驗完會**再停下來**（`stop_when_ready`） | 同左，機制換成 `StopCondition::FilesChecked`（[`torrentimpl.cpp`](https://github.com/qbittorrent/qBittorrent/blob/release-5.2.3/src/base/bittorrent/torrentimpl.cpp)） |
  | 重新開始對壞掉的 torrent | 有錯誤先 `clear_error()`；缺檔的先 `reload()` | 同左 |

  **資料被刪掉、容器重啟之後，那個 torrent 就是 `missingFiles`**（兩版實測）。救回來兩種順序都成立：資料放回去之後
  recheck → start 與 start → recheck 兩版都回到做種中（`stalledUP`、progress 1）；資料不在的話兩種都是 `stalledDL`、
  progress 0（在等 peer 重新下載）。`client_error` 的「重試」只送 start——錯誤不是資料的問題，重新校驗一次幾十 GB
  只是讓它晚一點回來。
### 停住的 torrent 做 recheck

- **停住的 torrent 做 recheck：5.x 上 recheck → start 救不回來**（2026-09-24 M3 票 03，
  `scripts/experiments/qbittorrent_stopped_recheck.py`；每包兩個全零稀疏檔共 8 GiB，校驗約 14–21 秒，兩支請求
  之間 < 0.1 秒。版本：`5.2.3`（`lscr.io/linuxserver/qbittorrent:5.2.3`，Web API 2.15.1），當天的 `:latest` 就是
  同一版（`5.2.3_v2.0.14-ls476`），兩次結果一致；`4.4.5`（Web API 2.8.5）作對照。上一條的四包都是重啟前在跑的
  `missingFiles`，量不到這一種）。每包先做種到完成，再照情境停住、刪掉第二個檔：

  | 前置 → 動作 | 5.2.3 的 state 序列 | 4.4.5 的 state 序列 |
  | --- | --- | --- |
  | 停住 → recheck | `stoppedUP` → `checkingUP` → `stoppedUP`（不會自己開始） | `pausedUP` → `checkingUP` → `pausedUP` |
  | 停住 → recheck → start | `stoppedUP` → `checkingUP` → **`stoppedUP`** | `pausedUP` → `checkingUP` → `stalledUP` |
  | 停住 → start → recheck | `stoppedUP` → `checkingUP` → `stalledUP` | 同左 |
  | 停住、缺一檔 → recheck | `stoppedUP` → `checkingUP` → `stoppedDL`（progress 0.5） | `pausedUP` → `checkingUP` → `pausedDL`（0.5） |
  | 停住、缺一檔 → recheck → start | `stoppedUP` → `checkingUP` → **`stoppedDL`**（0.5） | `pausedUP` → `checkingUP` → `stalledDL`（0.5） |
  | 停住、缺一檔 → start → recheck | `stoppedUP` → `checkingUP` → `stalledDL`（0.5） | 同左 |
  | 做種中、缺一檔 → recheck → start | `stalledUP` → `checkingUP` → `stalledDL`（0.5） | 同左 |
  | 做種中、缺一檔 → start → recheck | 同上 | 同左 |

  原因在原始碼：5.2.3 的 `forceRecheck()` 對停住的 torrent **自己先呼叫 `start()`**（`m_isStopped` 變假）再掛
  `StopCondition::FilesChecked`；校驗中送到的 `start()` 看它沒停就什麼都不做，條件留著，校驗完
  `handleTorrentChecked` 照樣 `stop()`（[`torrentimpl.cpp`](https://github.com/qbittorrent/qBittorrent/blob/release-5.2.3/src/base/bittorrent/torrentimpl.cpp)）。
  4.4.5 的 `forceRecheck` 只掛 `stop_when_ready`、不改 `m_isStopped`，`resume()` 看到還停著就把旗標清掉
  （[`torrentimpl.cpp`](https://github.com/qbittorrent/qBittorrent/blob/release-4.4.5/src/base/bittorrent/torrentimpl.cpp)）。
  start 若晚到校驗做完之後就又生效——所以是一個跟校驗長度賽跑的窗口，幾十 GB 的真實下載一定落在裡面。

  對 Berth 的後果：資料都回來的那一種停在 `stoppedUP`、progress 1，poller 照樣判完成並入庫，只是不做種；**缺檔的
  那一種停在 `stoppedDL`**，Job 回到 `metadata_ready` 之後進 `downloading` 就永遠不動——`stoppedDL` 不是
  `stalledDL`（不會轉 `stalled`），也不是壞掉的狀態（不會再開 Issue），畫面上看不出任何事。
  **Berth 用 start → recheck**（`missing_files` 的「重新校驗」）：先開起來，recheck 時它已經在跑，不掛條件；兩版、
  停住與否、資料回不回來都落在做種中或 `stalledDL`，poller 都接得住（上一條的 `missingFiles` 兩種順序也都成立）。
### 輪詢與 sync/maindata

- **沒有 webhook**；`sync/maindata` 以 `rid` 做增量輪詢。`autorun_enabled` / `autorun_program`（完成時執行外部程式，可帶 `%f` `%n`）可作為「喚醒輪詢」的加速手段，非必要。
- **`rid` 的狀態掛在 session（SID cookie）上**（2026-09-10 票 10 對 4.4.5 與 5.2.3 實測）：不帶 cookie 的話每一次請求都是新 session，回的永遠是 `full_update: true`。所以輪詢那一側必須把 HTTP client 握著不放（Berth 的 `Downloader`）。
- **增量那一輪的 `torrents[hash]` 只帶變動的欄位**（實測有的只剩 `{"num_leechs", "time_active"}`），所以呼叫端一定要把它併回上一份完整快照再讀——照字面讀會得到一個沒有 category、沒有 state 的空殼。被刪掉的 torrent 在 `torrents_removed`（hash 陣列）。
- **未完成時的 `completion_on` 兩版不同**：4.4.5 是 `0`、5.2.3 是 `-1`。完成判定寫 `> 0` 對兩版都成立，寫 `!= 0` 會讓 5.x 上每一個剛加入的 torrent 都被當成已完成。`total_size` 在 metadata 到手之前同樣是 `-1` / `0`。
- **`metaDL` 期間 `torrents/files` 回 `200` + `[]`**（兩版皆然），與「這個 torrent 不存在」同形——所以 `metadata_ready` 的判定要 state 與清單兩個條件都成立。
## 登入與 IP 封鎖

- 登入 `auth/login` 回 `SID` cookie，且 **`Referer` / `Origin` 必須與 `Host` 一致**；可設 `bypass_local_auth` 與子網白名單。
- **`auth/login` 的成敗形狀跨大版本不同**（2026-09-08 對 `lscr.io/linuxserver/qbittorrent` 的 4.4.5 與 5.2.3 各實測一輪，票 11）：

  | 版本 | 成功 | 帳密錯 |
  | --- | --- | --- |
  | 4.4.5 | `200` + body `Ok.` + `Set-Cookie: SID=…` | `200` + body `Fails.`（**狀態碼不變**） |
  | 5.2.3 | `204` + 空 body + `Set-Cookie: QBT_SID_<port>=…` | `401` + body `Unauthorized` |

  所以判定只能認 4.x 那個「200 卻是失敗」的 `Fails.`，不能認「成功等於 `Ok.`」。另外，來源 IP 在
  `WebUI\AuthSubnetWhitelist` 上時 5.x **一律回 204，連錯的帳密也是**——免密白名單本來就繞過驗證，
  而那正是套件內 Berth 的處境（§16.3、§20.7）。

- **IP 封鎖與帳密不對是兩件事**（2026-09-10 票 10 對兩版各實測一輪，解掉 plan T1.9 的第四條）：

  | 情況 | 4.4.5 | 5.2.3 |
  | --- | --- | --- |
  | 帳密錯（第 1–5 次） | `200` + `Fails.` | `401` + `Unauthorized` |
  | 第 6 次（IP 被封） | `403` + `Your IP address has been banned after too many failed authentication attempts.` | 同左，**一字不差** |
  | 被封之後的其他端點 | `403` + `Forbidden` | 同左 |

  也就是說：**`auth/login` 上的 403 只有一個意思**（被封），因為帳密錯在兩版都不是 403；
  而其他端點上的 403 與「沒有登入」完全同形，分不出來。門檻是連續 5 次
  （`WebUI\MaxAuthenticationFailCount`），封鎖時間預設 3600 秒（`WebUI\BanDuration`），
  兩者都存在記憶體裡，重啟容器就清掉。下一步不同是分開的理由：帳密不對要去改設定，
  被封要等過期或重啟 qBittorrent——改帳密只會再失敗五次，把封鎖時間重新算一輪。

### 封鎖的偏好鍵與預設值

  **偏好鍵與預設值**（2026-09-30 讀原始碼查證，M4 票 21；tag `release-4.4.5` 與 `release-5.0.4`，兩版相同）：
  Web API 的鍵是 `web_ui_max_auth_fail_count`（次數，預設 5，設定檔 `Preferences/WebUI/MaxAuthenticationFailCount`）
  與 `web_ui_ban_duration`（**秒**，預設 3600，`Preferences/WebUI/BanDuration`）——`src/webui/api/appcontroller.cpp`
  讀寫這兩個鍵（4.4.5 第 248–249、667–670 行；5.0.4 第 316–317、876–879 行），預設值在 `src/base/preferences.cpp`
  （4.4.5 第 662、672 行；5.0.4 第 797、810 行）。計數與封鎖表是 `src/webui/api/authcontroller.h` 的
  `m_clientFailedLogins`（記憶體裡的 `QHash`，重啟清空），**登入成功才把那個 IP 移除**（`authcontroller.cpp`
  5.0.4 第 82 行、4.4.5 第 69 行），不隨時間衰減；**被封期間連對的帳密也被拒**（`isBanned()` 在驗密碼之前，
  5.0.4 第 68–75 行）。`max_auth_fail_count = 0` 不計也不封（5.0.4 第 90–91 行）。WebUI 沒有解除封鎖的介面，
  API 也沒有：只能等期滿或重啟 qBittorrent（桌面版的「封鎖的 IP」是對 peer 的，無關）。被封時 Berth 讀不到那一台
  的偏好，所以精靈說的是預設值（`components/services.BAN_DEFAULTS`），並從第 3 次連錯起預警。原始碼：
  [appcontroller.cpp 5.0.4](https://github.com/qbittorrent/qBittorrent/blob/release-5.0.4/src/webui/api/appcontroller.cpp)、
  [authcontroller.cpp 5.0.4](https://github.com/qbittorrent/qBittorrent/blob/release-5.0.4/src/webui/api/authcontroller.cpp)、
  [preferences.cpp 4.4.5](https://github.com/qbittorrent/qBittorrent/blob/release-4.4.5/src/base/preferences.cpp)。

- **`auth/login` 在 session 還活著時直接回成功，連密碼都不看**（同一輪實測：帶著 SID 打八次錯的
  密碼全部是 `200` + `Ok.`）。所以「驗一次帳密對不對」必須從沒有 cookie 的狀態發起。

## 探針 torrent：看不看得到分類路徑

**qBittorrent 看不看得到分類路徑：探針 torrent**（2026-09-30 實測 4.4.5 與 5.2.3，M4 票 19；`scripts/experiments/qbittorrent_visibility_probe.py`，一次性容器，分類路徑是一個 volume，「Berth 寫的檔」以 `docker cp` 放進去）

Web API 沒有「這條路徑你看不看得到」：`app/getDirectoryContent` 5.0 才有，而且只說目錄在不在——qBittorrent 自己的檔案層裡剛好有同名空目錄也算。所以反過來證明：Berth 在分類路徑寫一個小檔，做成單檔 torrent（`private`、不掛 tracker），`torrents/add` 明送 `savepath`、`autoTMM=false`、停住，`torrents/recheck`，看校驗之後的 `progress`；之後 `torrents/delete` 帶 `deleteFiles=false`，小檔由 Berth 刪。

| 情境 | 4.4.5（API 2.8.5） | 5.2.3（API 2.15.1） |
| --- | --- | --- |
| 檔在、停住加入、**不** recheck | `checkingResumeData` → `pausedDL`，**0%** | `checkingResumeData` → `stoppedDL`，**0%** |
| 檔在、recheck | → `pausedUP`，100%，約 1 秒 | → `stoppedUP`，100%，約 1.4 秒 |
| 目錄與檔都不在 | 第一次讀就是 `pausedDL` 0% | → `stoppedDL` 0% |
| 目錄在（qBittorrent 自己的層）、檔不在 | `pausedDL` 0% | `stoppedDL` 0% |
| 檔在、`chmod 000` root 所有 | → `checkingDL` → **`error`** | 同左 |
| 開了全域 temp path（`download_path` 變成它） | 100%：校驗照樣找 save path 裡的檔 | 同左 |
| 同上、加入時 `useDownloadPath=false` | 100%，`download_path` 空 | 同左 |

- **停住加入不會自己校驗**，一定要 recheck。
- **`torrents/add` 回來時它還不一定列在 `torrents/info` 裡**（2026-09-30 對 5.2.3 經 Berth 實跑：第一次讀回空陣列；一次性容器的實驗剛好沒撞上），而對還不在的 hash 送 recheck 是靜默成功——校驗沒發生，停在 0% 與看不到一模一樣。所以先等它列出、離開 `checkingResumeData`，再 recheck。
- 看不到時 qBittorrent **不替它建目錄**，移除之後兩版都沒留下任何東西；`deleteFiles=false` 之後小檔還在。
- `error` 是「檔在、讀不了」（權限），與看不到分得開；Berth 把它說成權限問題而不是掛載。
- 看不到的那一面沒有一個「校驗完了」的狀態可等（4.4.5 第一次讀就已經是結論），所以 Berth 以「不在校驗或排隊中、進度不到 100%、state 3 秒不變」判看不到，整個探針最多等 20 秒（qBittorrent 預設一次只校驗一個 torrent，別的在校驗時要排隊）。
- **校驗到 100% 會觸發「torrent 完成時執行外部程式」**（`autorun_enabled` / `autorun_program`，4.4.5 與 5.2.3 同一個實驗裡實測，每個看得到的探針各觸發一次）。所以探針只在精靈「建立並檢查」、新增 Route 與「重新檢查」時跑；**5 分鐘的健康迴圈不跑，`download_visible` 沿用上一次的結論**——每條 Route 每 5 分鐘一次，會變成使用者那邊的通知洪水。「按下之後會」說出這件事；健康頁那一條說「沿用上一次的結論」與那一次的時間（M4 票 50，使用者 2026-10-06 確認）。5.x 另有「加入時執行」（`autorun_on_torrent_added_enabled`），同理只在那幾個時機觸發，沒有另外實測。
- 探針 torrent 不掛分類、不帶 tag（tag 一建就留在使用者的清單裡；`berth` 那一個會讓 poller 把它當成 Berth 的下載），名字是 `.berth-probe-*`，停住、幾秒內就移除。

### 校驗不完的探針

**校驗不完的探針：頁 2 問「看不看得到 `/data`」**（2026-10-07 實測 4.4.5 與 5.2.3，M4 票 46；`scripts/experiments/qbittorrent_unfinished_probe.py`，送的是 Berth 自己的 `probe_torrent(unfinished=True)`，報告 `.local/experiments/results/qbittorrent-unfinished-probe-*.json`）

探測檔兩片（32 KiB），torrent 的第二片雜湊算在反相的內容上。開著「完成時執行」（`autorun_program`）與「加入時執行」（`autorun_on_torrent_added_program`，各寫不同的檔），每個情境一包新的 torrent、停住加入、等它列出再 recheck：

| 情境 | 4.4.5（API 2.8.5） | 5.2.3（API 2.15.1） |
| --- | --- | --- |
| 檔在、校驗不完 | `pausedDL`，**0.5** | `stoppedDL` → `checkingDL` → `stoppedDL`，**0.5** |
| 檔不在 | `pausedDL` 0 | `stoppedDL` 0 |
| 檔在、`chmod 000` | → `checkingDL` → `error` | → `error` |
| 對照：單片（票 19 那一種）、檔在 | → `pausedUP` 1 | → `stoppedUP` 1 |
| 「完成時執行」被觸發 | 只有對照組 | 只有對照組 |
| 「加入時執行」被觸發 | （4.4.5 沒有這個設定） | 四包都觸發 |

- 看得到與看不到照樣分得開（0.5 對 0），讀不了照樣是 `error`。所以 Berth 判「看得到」改成**進度大於 0**（`probe_sight`），兩種探針同一條；單片的那一種本來就是 0 或 1。
- 頁 2 測連線時用這一種（M4 票 46）：不觸發「完成時執行」。「加入時執行」擋不掉——任何加進去的 torrent 都觸發，既有表單照實說會觸發一次。頁 3 的 Route 檢查仍是單片那一種（沒改：它的「按下之後會」照票 19 的說法）。

## WebUI 帳密規則

**WebUI 帳密規則**（2026-10-01 讀原始碼＋實測，M4 票 26；`scripts/experiments/qbittorrent_webui_login_rules.py` 對 4.4.5 與 5.2.3，報告 `.local/experiments/results/qbittorrent-webui-login-rules-*.json`）

- **5.2.0 起 `app/setPreferences` 才驗**：`web_ui_username` 至少 3 字元、不能有冒號，`web_ui_password` 至少 6 字元；違反回 `400` + 一行英文原文（`WebUI password must be at least 6 characters long`、`WebUI username must be at least 3 characters long`、`WebUI username cannot contain a colon`）。4.4.5 什麼都收（實測 2 字元帳號、含冒號、5 字元密碼都 `200`）；release-5.1.4 的原始碼還沒有這段。【[appcontroller.cpp @ release-5.2.0](https://github.com/qbittorrent/qBittorrent/blob/release-5.2.0/src/webui/api/appcontroller.cpp)、[@ release-5.1.4](https://github.com/qbittorrent/qBittorrent/blob/release-5.1.4/src/webui/api/appcontroller.cpp)】
- 字數是 QString 的長度（UTF-16 code unit），與瀏覽器的 `String.length` 同一種算法：六個中文字的密碼 5.2.3 收。
- **帳號先驗先寫、密碼後驗**，照原始碼的順序，不看 JSON 的鍵序：帳號合規而密碼太短的那一次回 `400`，帳號**已經寫進去**、密碼沒有（實測，兩種鍵序都一樣）。所以 Berth 先單獨送密碼、成功了才送帳號（`qbittorrent._apply_password`）；兩支都過了才記下帳號。
- 【決定】精靈與設定頁照 5.2 的規則先擋，不分版本：4.4–5.1 自己的設定頁（WebUI 的 JS）也要求帳號 3、密碼 6 字元（只少了冒號那一條），套件內那一台又一定是新版。【[preferences.html @ release-4.4.5](https://github.com/qbittorrent/qBittorrent/blob/release-4.4.5/src/webui/www/private/views/preferences.html)】

## 硬鏈接與 Docker

**硬鏈接與 Docker**（[TRaSH Hardlinks](https://trash-guides.info/File-and-Folder-Structure/Hardlinks-and-Instant-Moves/)、[Servarr docker-guide](https://wiki.servarr.com/docker-guide)、[link(2)](https://man7.org/linux/man-pages/man2/link.2.html)）

- 硬鏈接不能跨檔案系統、分割區、volume、**mount**；`link()` 即使同一個檔案系統掛兩次也會 `EXDEV`。Docker 把兩個 volume 當成兩個檔案系統，所以 `/downloads` + `/media` 分開掛一定失敗；解法是單一 `/data` 掛載。
- exFAT 不支援硬鏈接；btrfs 子卷、ZFS dataset 各自是 mount 邊界，跨越即失敗；mergerfs 在 path-preserving 建立策略下跨 branch 回 `EXDEV`，其 FAQ 同樣要求單一掛載根（[mergerfs FAQ](https://trapexit.github.io/mergerfs/latest/faq/why_isnt_it_working/)）。
- 權限：TRaSH 建議「每個 app 一個使用者 + 共用群組 + UMASK 002」（資料夾 775、檔案 664），或簡化為單一使用者 + UMASK 022。本系統與 qBittorrent 至少要同群組且對兩側目錄可寫。
- Docker Desktop（Windows）：文獻無定論，本機實測 NTFS bind mount 硬鏈接可用（§20.7）。macOS VirtioFS 未查到硬鏈接限制，也未實測。
- `stat().st_dev` 相同是必要條件但不充分（同 FS 多次掛載仍失敗），所以 §4.4 的檢查一律真的做一次 `link()`。

## Sonarr 與 Radarr 先例

**Sonarr / Radarr 先例**（[sonarr/faq](https://wiki.servarr.com/sonarr/faq)、[radarr/settings](https://wiki.servarr.com/radarr/settings)、[quick-start](https://wiki.servarr.com/sonarr/quick-start-guide)）

- Completed Download Handling：只在下載客戶端回報完成後才入庫；要求客戶端完成後**暫停而非移除**，並保留至少 14 天的歷史。
- 「Remove Completed」只在客戶端回報做種完成且 torrent 已停止時才移除 torrent 與檔案。本系統不做自動移除（§1.2），做種上限交給 qBittorrent 分類的 share limit；移除後的善後由 Reconciler 處理。
- 入庫預設硬鏈接，失敗時 Sonarr 會**退回複製**。【決定】本系統**不退回複製**：硬鏈接失敗即 Route 不健康並拒絕送單，因為複製會讓刪除範圍與空間估算失真。
- 人工入庫的官方名稱是 **Interactive Import**（逐檔指定作品/季/集，可選 Move 或 Copy/Hardlink）；「unmapped files」只是社群俗稱。本系統的 Review Queue 對應這個概念。
- Root Folder = 媒體庫根目錄，明文規定不可與下載目錄相同。

## 其他：同一台認不出來、選項頁網址、sparse 檔

- **同一台 qBittorrent 認不出來**（M4 票 102，2026-10-14 讀 master 原始碼）：WebAPI 沒有持久的實例識別碼——`app/` 底下只有版本、build info、偏好、預設路徑、網卡清單之類（`appcontroller.h`），沒有 Jellyfin `ServerId`（§20.15）那種東西。最接近的是 `app/processInfo` 的 `launch_time`，但它 2026-01 才加（commit `09fdbe47b`，版本下限 4.4 的那幾版沒有）、每次重啟就變，而且 IP 換了的時候舊位址多半已經連不到，沒得比。版本加 `save_path` 也不行：兩台預設安裝的一模一樣。所以位址變了就當換台（§16.4）。【[appcontroller.h](https://github.com/qbittorrent/qBittorrent/blob/master/src/webui/api/appcontroller.h)、[appcontroller.cpp `processInfoAction`](https://github.com/qbittorrent/qBittorrent/blob/master/src/webui/api/appcontroller.cpp)】
- **WebUI 沒有通往「選項」的網址**（M4 票 102，2026-10-14 對 linuxserver 5.2.4 實開）：`/#/settings` 登入後落在主畫面的 torrent 清單；`client.js` 只讀 `#download=` 這一種 hash（註冊磁力連結處理器用）。選項是 MochaUI 視窗，從「工具 → 選項」開。所以補法只給 WebUI 本身，文案說在哪個選單。【[client.js](https://github.com/qbittorrent/qBittorrent/blob/master/src/webui/www/private/scripts/client.js)】
- **下到一半的檔是 sparse 檔**（M4 票 102，票 42 實測與 Linux 上的測試）：qBittorrent 預設不預先配置，下到一半的檔表觀大小（`st_size`）已經是整個檔案，實際佔用（`st_blocks` × 512）只有下載了的部分——票 42 那一筆表觀 970 MB、實際約 192 MB。刪除的「可空出空間」與 `freed` 量的是實際佔用（`fs.PathFacts.allocated`），complete 那一側同一條規則，所以數字以區塊取整。Windows 的 `os.stat` 沒有 `st_blocks`（等價的是 `GetCompressedFileSizeW`），Berth 只在 Linux 容器裡跑，開發機上退回表觀大小。
