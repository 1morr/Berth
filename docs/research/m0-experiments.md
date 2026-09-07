# M0 實驗結果（票 04 / brief §20.6）

2026-09-07。腳本在 [`scripts/experiments/`](../../scripts/experiments/README.md)，全部可重跑；
原始 JSON 落在 `.local/experiments/results/`（不進版控）。結論摘要在 brief §20.6 / §20.7，
影響到的決定改在 plan §5、§8.1、§8.2、§9.2、§9.4。

## 0. 環境

| 項目 | 版本 |
| --- | --- |
| 宿主 | Windows 11 Pro for Workstations 26200、Docker Desktop 29.6.2（WSL2） |
| Jellyfin | `jellyfin/jellyfin:10.10.7` 與 `jellyfin/jellyfin:10.11.11`（官方 image：linuxserver 只保留最新 tag，釘不了版本） |
| qBittorrent | `lscr.io/linuxserver/qbittorrent:4.4.5`（Web API 2.8.5）與 `:5.2.3`（Web API 2.15.1） |
| Prowlarr | `lscr.io/linuxserver/prowlarr:latest` → 2.5.2.5491 |

brief §20.2 訂的支援下限是 qBittorrent **4.4**（Web API 2.8.4）；4.4.5 是 linuxserver 還留著 tag 的最舊 4.4，所以拿它代表下限。兩個 Jellyfin 共用同一份 dummy 媒體樹（21 個影片、5 個字幕），
媒體庫用 Jellyfin 的預設 fetcher（TMDB），也就是實際部署的樣子。

## 1. Jellyfin 命名（10.10.7 與 10.11.11）

媒體樹裡有兩組劇集與五部電影。`Berth Test Show (2020) [tmdbid-1399]` 會被 TMDB 認出來
（變成《冰與火之歌：權力遊戲》），`Qwxzyv Berth Probe (2099)` 故意讓 TMDB 對不上，
名稱完全由 Jellyfin 自己的檔名解析器決定 —— 方括號有沒有滲進去只有在後者看得出來。

### 1.1 劇集：`S01E01` 認得出來，tag 不會滲進劇名或集名

| 檔名 | 解析結果（10.10.7 與 10.11.11 相同） |
| --- | --- |
| `… - S01E01 - Winter Is Coming [BD][1080p][CHT+JP][Sakurato].mkv` | `ParentIndexNumber=1`、`IndexNumber=1` |
| `… - S01E03-E04 - Lord Snow [BD][1080p][CHT][Sakurato].mkv` | `IndexNumber=3`、`IndexNumberEnd=4` |
| `… - S00E01 - Special One [BD][1080p][CHT][Sakurato].mkv` | `ParentIndexNumber=0`、`IndexNumber=1`，季名為 `Specials` |

TMDB 對不上的那一組（`Qwxzyv Berth Probe (2099)`）：

- Series 名稱 = 資料夾名 `Qwxzyv Berth Probe (2099)`，`ProviderIds` 為空。
- **兩個 Episode 的 `Name` 都是 `'Qwxzyv Berth Probe'`** —— 帶 tag 的 S01E01 與完全沒有 tag 的
  S01E02 一模一樣。也就是說 Jellyfin **根本不從檔名取集標題**，它取的是作品名；
  `- <Episode Title>` 那一段只是給人看的，集標題來自 provider。
- 因此 **方括號與 `+` 不會出現在 Series 或 Episode 的名稱裡**，anidb#11 的問題在核心解析器上不存在。
  票的第一條驗收成立。

順帶：plan §5 模板裡的 `episode_title` 對 Jellyfin 沒有作用，它的價值是讓檔名在檔案總管裡可讀、
以及讓同一集的不同版本檔名只差 tags（brief §7.7 的唯一硬要求）。

### 1.2 電影多版本：檔名必須與資料夾名一字不差，`[tmdbid-…]` 也算

| 資料夾 / 檔名 | 結果 |
| --- | --- |
| `Berth Movie Plan (2019) [tmdbid-27205]/`<br>`Berth Movie Plan (2019) [tmdbid-27205] - [BD][2160p][CHT+JP][Sakurato].mkv`（plan §5 模板） | **1 個 Movie、2 個版本**，標籤 `[BD][2160p][CHT+JP][Sakurato]`、`[WEB][1080p][CHS][Lilith-Raws]` |
| `Berth Movie Brief (2019) [tmdbid-157336]/`<br>`Berth Movie Brief (2019) - [BD][2160p]….mkv`（brief §7.2 範例，檔名少了 `[tmdbid-…]`） | **2 個獨立的 Movie 條目**，標籤退化成整個檔名主幹 |
| `Berth Movie Res (2019)/… - 2160p.mkv` / `- 1080p.mkv` / `- 720p.mkv`（對照組） | 1 個 Movie、3 個版本，順序 **2160p → 1080p → 720p**（解析度降冪） |
| `Qwxzyv Berth Probe (2099) Movie/… - [BD][2160p]….mkv`（TMDB 對不上） | 1 個 Movie、2 個版本，標籤同樣是純 tag |

結論：

- **方括號可以當版本標籤**，`+` 也沒問題。票的第三條驗收成立。
- **plan §5 的電影模板是對的，brief §7.2 的範例是錯的**：`- ` 之前必須與資料夾名完全一致，
  資料夾名含 `[tmdbid-…]` 時檔名也必須含。否則不是多版本，是兩部片。
- 版本順序：結尾為 `p`/`i` 的標籤依解析度降冪（`2160p` 在前），其餘依字母序
  （`[BD]…` 在 `[WEB]…` 前）。與官方文件一致，兩個版本一致。
- 瀏覽器實測（playwright，10.10.7 與 10.11.11 皆同）：詳細頁的「版本」下拉選單顯示的就是
  `[BD][2160p][CHT+JP][Sakurato]` 與 `[WEB][1080p][CHS][Lilith-Raws]`。

### 1.3 劇集多版本：沒有插件會變成兩個重複條目

同一季資料夾放同一集的兩個版本，**未裝 MergeVersions**（兩個版本皆同）：

- `S01E01` 出現 **兩個獨立的 Episode 條目**，各自 1 個 MediaSource，名稱都是 `凜冬將至`。
  不是版本選單，是重複 —— brief §20.1 引的社群回報屬實。

裝上 MergeVersions 並跑 `MergeEpisodesTask` 之後：

- 合併成 **1 個 Episode、2 個 MediaSource**。
- **版本標籤是整個檔名主幹**，不是 tags：
  `Berth Test Show (2020) - S01E01 - Winter Is Coming [WEB][1080p][CHS][Hardsub][Lilith-Raws]`。
  瀏覽器實測確認選單裡就是這一長串。
- 版本順序不保證：10.10.7 是 `[BD]` 在前，10.11.11 是 `[WEB]` 在前，同一份檔案、同一個任務。

**brief §7.7「版本標籤即 tags 字串」只對電影成立**，劇集看到的是完整檔名。這不影響正確性
（同一集的版本仍然合而為一），但 UI 文案不能說「使用者會看到 tags」。

### 1.4 extras：三層都成立

| 放置位置 | 結果 |
| --- | --- |
| `<作品>/extras/Series Level Interview.mkv` | Series 的 `SpecialFeatures`（`GET /Items/{seriesId}/SpecialFeatures`） |
| `<作品>/Season 01/extras/Season Level NCOP.mkv` | **該季**的 `SpecialFeatures`，不是劇集層 |
| `<電影>/extras/Movie Level Behind The Scenes.mkv` | Movie 的 `SpecialFeatures` |

全部沒有被誤認成正片集數，與 brief §20.1 相符。plan §5 的
`Extras → {作品資料夾}/extras/{原檔名}` 可以照寫；季層 extras 也是有效的落點。

### 1.5 外掛字幕：`.CHT.zh.ass` 可行，但 `zh-Hant` 兩個版本行為不同

`MediaStream` 實測（`DisplayTitle` 就是播放器字幕選單顯示的字串）：

| 檔名後綴 | 10.10.7 | 10.11.11 |
| --- | --- | --- |
| `.CHT.zh.ass` | `Language='chi'`、`Title='CHT'`、`DisplayTitle='CHT - Chi - ASS - 外部'` | `Language='zho'`、`Title='CHT'`、`DisplayTitle='CHT - Chinese - ASS - 外部'` |
| `.CHS.zh.ass` | `DisplayTitle='CHS - Chi - ASS - 外部'` | `DisplayTitle='CHS - Chinese - ASS - 外部'` |
| `.zh-Hant.ass` | `Language=None`、`Title='zh-Hant'`、`DisplayTitle='zh-Hant - 未定義 - ASS - 外部'` | `Language='zh-hant'`、`Title=None`、`DisplayTitle='Chinese (Traditional) - ASS - 外部'` |
| `.zh-Hans.ass` | `DisplayTitle='zh-Hans - 未定義 - ASS - 外部'` | `DisplayTitle='Chinese (Simplified) - ASS - 外部'` |
| `.CHT.default.zh.ass` | `IsDefault=True`、`DisplayTitle='CHT - Chi - 預設 - ASS - 外部'` | 同左（`Chinese`） |

結論：

- **`<stem>.{CHT|CHS}.zh.ass` 是唯一在兩個版本都正確的寫法**，繁簡靠自由文字標題區分，
  而且標題排在 `DisplayTitle` 最前面，選單一眼看得出來。plan §5 的字幕模板凍結不動。
- **`zh-Hant` / `zh-Hans` 在 10.11 才被認得**（顯示為 Chinese (Traditional) / (Simplified)），
  10.10 完全不認、退化成「未定義」。brief §20.1 標「未證實」的那一條有答案了：不能用，
  因為 Berth 同時支援 10.10。
- `zh` 的正規化碼兩版不同（`chi` vs `zho`），都顯示為中文，Berth 不依賴這個值。
- `.default.` 旗標在兩版都生效。

### 1.6 精靈與 API：plan §9.4 有兩處要改

1. **`POST /Startup/User` 之前必須先 `GET /Startup/User`**。兩個版本都一樣：直接 POST 會回
   **500**，容器 log 是 `System.InvalidOperationException: Sequence contains no elements
   at StartupController.UpdateStartupUser`。GET 那一支會先跑 `UserManager.InitializeAsync()`
   建立預設使用者，POST 只是改名字與密碼。
2. **`POST /Library/VirtualFolders` 的 body 是 `AddVirtualFolderDto`，`LibraryOptions` 要包一層**：
   `{"LibraryOptions": {...}}`。直接送 `LibraryOptions` 物件不會報錯（一樣回 204），
   但整份設定會被靜默丟掉 —— `EnableRealtimeMonitor`、`SeasonZeroDisplayName`、`TypeOptions`
   全部變成預設值。包好之後兩個版本都正確存下來。

其餘與 brief §20.7 相符：`/Startup/Configuration`、`/Startup/User`、`/Startup/RemoteAccess`、
`/Startup/Complete`、`/Library/VirtualFolders` 在精靈完成前全部**匿名**可呼叫。

MergeVersions：

- `POST /Packages/Installed/Merge%20Versions?assemblyGuid=…` **不必指定版本**，Jellyfin 會挑
  相容的：10.10.7 裝到 `10.10.0.5`，10.11.11 裝到 `10.11.0.1`。安裝後 `Status` 為 `Restart`。
- 下載是 Jellyfin 自己連 GitHub，實測遇過一次 TLS 中斷回 500（`The SSL connection could not be
  established`）。精靈要能重試，不能把一次失敗當成「插件裝不起來」。
- **重啟後不能只等 `/System/Info/Public`**：它在伺服器還在載入時就回 200，這時
  `GET /ScheduledTasks` 回 **503「Jellyfin 伺服器載入中，請稍後再試。」**。實驗腳本原本在
  `/System/Info/Public` 之後只 `sleep(5)`，重跑時就踩到了；改成輪詢 `/ScheduledTasks` 回 200。
  plan §9.4 第 8 步同樣要這樣等。
- 排程任務：`Key` 為 `MergeEpisodesTask` / `MergeMoviesTask`，`Name` 為
  `Merge All Episodes` / `Merge All Movies`，`Category` 為 `Merge Versions`。
  `Id` 在兩個版本、多次全新安裝都是同一組（`dcaf151dd1af25aefe775c58e214477e` /
  `fd957c84b0cfc2380becf2893e4b76fc`），看起來是從 Key 推導的；plan §9.4 仍然照 `Key` 查 `Id`，
  不寫死。

### 1.7 掃描一次不夠：10.11 的 `find_episodes` 會回 0

量測方式：同一批 Episode，三種查法各數一次。

| 查法 | 10.10.7 第一次掃描後 | 10.11.11 第一次掃描後 | 10.11.11 第二次掃描後 |
| --- | --- | --- | --- |
| `/Items?parentId=<媒體庫>&recursive=true` 後照路徑分群 | 6 | 6 | 6 |
| `/Items?parentId=<seriesId>&recursive=true`（plan §8.2 的做法） | 6 | **0** | 6 |
| `/Shows/{seriesId}/Episodes` | 6 | **0** | 6 |

只有**被 provider 認出來的**那個 Series 有這個問題；TMDB 對不上的 `Qwxzyv Berth Probe`
在任何時候都是 2/2/2。推測是 provider 比對成功後 Series 條目被重建，祖先索引還沒補回去。

對 plan §8.2 的影響：`find_episodes(series_id)` 不能只查一次就相信 0 這個答案。入庫後
`notify_paths` → 查集數的流程要嘛重試、要嘛改用「以媒體庫為 parent + recursive，再照 `Path`
前綴篩」，後者在四種情況下都對。

### 1.8 深連結：`#!/details?id=` 兩個版本都可用

`#!/details?id=` 是前端路由，伺服器端測不到，所以這一項是**手動**的：
`jellyfin_naming.py` 把兩種候選網址、`serverId` 與可用的 item id 寫進報告的
`deep_link_candidates`，人開瀏覽器登入後貼上去。playwright 實跑（先登入，再直接開網址）：

- `http://<server>/web/index.html#!/details?id=<itemId>&serverId=<serverId>` 在 **10.10.7 與
  10.11.11 都正確開到該項目的詳細頁**，網址列被前端正規化成 `#/details?id=…`。
- 佐證（10.10.7，`id=adee9a29…` = 《全面啟動》）：頁面渲染出 `heading "全面啟動"`，且
  版本下拉選單為 `combobox "版本"` 帶 `option "[BD][2160p][CHT+JP][Sakurato]" [selected]`
  與 `option "[WEB][1080p][CHS][Lilith-Raws]"`。10.11.11 同一個 id 得到同樣的結果。
- 佐證（10.11.11，合併後的 S01E01，`id=06008587…`）：`combobox "版本"` 的兩個 option 是
  `Berth Test Show (2020) - S01E01 - Winter Is Coming [WEB][1080p][CHS][Hardsub][Lilith-Raws]`
  與 `… [BD][1080p][CHT+JP][Sakurato]` —— §1.3 的「劇集版本標籤是整個檔名」在 UI 上成立。
- 客戶端自己產生的連結一律是 `#/`（不帶 `!`）。10.10.7 的其他路由帶 `.html`
  （`#/home.html`、`#/login.html`），10.11.11 沒有（`#/home`、`#/login`），但 `details`
  兩版都是 `#/details?id=`。

結論：Berth 產生深連結時用 `#/details?id=…&serverId=…`（客戶端自己的形式），
`#!` 版本也還能用，所以 brief §20.1 引的官方 webhook 範本沒有壞。

## 2. qBittorrent 4.4.5 與 5.2.3

### 2.1 `paused` 與 `stopped`：兩個版本各認一個，送錯的那個會**靜默地開始下載**

同一個 `torrents/add`，只差參數：

| 送出的參數 | 4.4.5（API 2.8.5）的 state | 5.2.3（API 2.15.1）的 state |
| --- | --- | --- |
| `paused=true` | `pausedDL` | `stalledDL`（**沒有暫停**） |
| `stopped=true` | `queuedDL`（**沒有暫停**） | `stoppedDL` |
| 兩個都不送 | `queuedDL` | `stalledDL` |
| `paused=true` + `stopped=true` | `pausedDL` | `stoppedDL` |

`torrents/add` 一律回 200 `Ok.`，不認得的參數不會報錯。所以 plan §8.1 的「API ≥ 2.11 用
`stopped`，否則 `paused`」不是最佳化而是**必要條件**：判斷錯了就是在使用者沒同意的情況下開始下載。

兩個都送也是安全的（各版本只認得自己那個），但 adapter 仍照版本送單一參數，理由是「靜默忽略」
表示未來再改名時同樣不會報錯，只有明確的版本判斷擋得住。

### 2.2 `contentLayout` 與 `torrents/files` 的 `name`

`name` **相對 `save_path`**，多檔 torrent 會含 torrent 根目錄那一層；`content_path` 則是
「save_path + 根目錄」。兩個版本一致：

| 案例 | `content_path` | `torrents/files[].name` |
| --- | --- | --- |
| 多檔 + `Original` | `/downloads/Berth.Test.Pack.A` | `Berth.Test.Pack.A/E01.mkv`、`Berth.Test.Pack.A/Subs/E01.CHT.ass` |
| 多檔 + `NoSubfolder` | `/downloads`（= save_path） | `E01.mkv`、`Subs/E01.CHT.ass` |
| 單檔 + `Original` | `/downloads/Berth.Test.Single.E.mkv` | `Berth.Test.Single.E.mkv` |
| 單檔 + `Subfolder` | `/downloads/Berth.Test.Single.F/Berth.Test.Single.F.mkv` | `Berth.Test.Single.F/Berth.Test.Single.F.mkv` |

- 「絕對路徑 = `save_path` + `/` + `name`」在**四種案例都成立**，包含單檔。plan §8.1 原本寫
  「兩種都試」可以簡化成「用 save_path 組，再 stat 驗證」。
- 單檔 + `Subfolder` 的子資料夾名是**去掉副檔名**的 torrent 名（`Berth.Test.Single.F`）。
- `content_path` 在單檔時指向**檔案**、多檔時指向**目錄**，plan §8.1 的「兩種都處理」成立。
- `torrents/files` 的鍵在兩個版本完全相同：`index`、`name`、`size`、`progress`、`priority`、
  `is_seed`、`piece_range`、`availability`。`index` 在 4.4.5 就有。
- **`save_path` 的尾斜線兩版不同**：4.4.5 回 `/downloads/`，5.2.3 回 `/downloads`。組路徑前要正規化。

### 2.3 `torrents/categories` 的鍵名

兩個版本都是 **`savePath`**（駝峰），沒有出現 `save_path`：

- 4.4.5：`{"name": "berth-exp", "savePath": "/downloads/berth-exp"}`
- 5.2.3：`{"name", "savePath", "download_path", "ratio_limit", "seeding_time_limit",
  "inactive_seeding_time_limit", "share_limit_action"}`

brief §20.2 說 4.4.0–4.4.1 曾在兩者間反覆；4.4.5 已經是 `savePath`。plan §8.1 的「兩種都接受」
維持不變（成本是一行，而 4.4.0/4.4.1 仍在支援範圍內），但實測到的只有 `savePath`。

### 2.4 Host 檢查：`ServerDomains` 不是重點，**port** 才是

同一個 TCP 目標（宿主的 `localhost:18080` → 容器的 `:8080`），只改 Host 標頭：

| Host 標頭 | `domain_list=*` | `domain_list=qbittorrent` | `HostHeaderValidation=false` |
| --- | --- | --- | --- |
| `qbittorrent:8080` | 200 | 200 | 200 |
| `qbittorrent`（無 port） | 200 | 200 | 200 |
| `localhost:8080` | 200 | **401** | 200 |
| `localhost:18080`（發佈 port） | **401** | 401 | 200 |
| `127.0.0.1:8080` | 200 | **401** | 200 |
| `evil.example:8080` | 200 | 401 | 200 |

4.4.5 與 5.2.3 的結果一字不差（表格的「發佈 port」列，4.4.5 是 `localhost:18080`、5.2.3 是 `localhost:18081`，兩者都 401）。qBittorrent 自己的 log 說得很清楚（以下這行來自 5.2.3 那一輪）：

```
WebUI: Invalid Host header, port mismatch. Request source IP: '::ffff:172.29.0.1'.
Server port: '8080'. Received Host header: 'localhost:18081'
```

結論：

1. **`WebUI\ServerDomains=qbittorrent` 足以讓 `http://qbittorrent:8080` 通過**，但代價是
   `localhost:8080` 與 `127.0.0.1:8080` 全部被擋 —— 使用者從瀏覽器進不了 WebUI。
   票 03 已經決定不預置 `ServerDomains`（image 預設 `*` 本來就過得了），本實驗確認那個決定正確，
   而且**不需要**改用 `HostHeaderValidation=false`。
2. **`*` 不會放過 port 不符**。domain list 只管網域那一半，port 一定要等於 WebUI 監聽的 port。
   所以 compose 把 qBittorrent 發佈成 `8080:8080` 是必要的：改成 `18080:8080` 之類的偏移，
   使用者用瀏覽器開 `localhost:18080` 會直接吃 401，而且錯誤訊息在容器 log 裡，介面上只看得到
   「Unauthorized」。這條要寫進 README 的疑難排解。
3. 沒有 port 的 Host 標頭一律放行（跳過 port 檢查）。
4. 偏好鍵叫 **`web_ui_host_header_validation_enabled`**（不是 `web_ui_host_header_validation`），
   4.4.5 與 5.2.3 都有，可經 `app/setPreferences` 開關。
5. 本節改的都是 Web API 的 runtime 偏好 `web_ui_domain_list`；它對應設定檔的
   `WebUI\ServerDomains`（同一個設定的兩種寫法）。「把 ini 鍵預置成 `qbittorrent` 再啟動」
   那條路徑沒有另外測 —— 不需要，因為結論是**不預置**。

### 2.5 CSRF

| 情境 | 4.4.5 | 5.2.3 |
| --- | --- | --- |
| `Referer` / `Origin` 與 Host 一致 | 200 | 200 |
| 完全不送 `Referer` / `Origin` | 200 | 200 |
| `Origin` / `Referer` 指向別的網域 | 401 | 401 |

brief §20.2 寫的是「`Referer` / `Origin` **必須**與 `Host` 一致」，準確的說法是
**送了就必須一致，不送則放行**。adapter 照樣一律帶 `Referer`（成本為零，且不依賴這個放行行為）。

### 2.6 其他確認到的偏好值

`app/preferences` 在 4.4.5 有 157 個鍵、5.2.3 有 223 個；plan §8.1 會讀寫的鍵兩版都存在：
`save_path`、`temp_path`、`temp_path_enabled`、`auto_tmm_enabled`、
`category_changed_tmm_enabled`、`bypass_auth_subnet_whitelist(_enabled)`、`bypass_local_auth`。
新裝的實例 `temp_path_enabled=false`、`auto_tmm_enabled=false`，與 brief §20.7 說的
`DisableAutoTMMByDefault` 預設 true 一致 —— 精靈第 4 步要套用的差異確實存在。

## 3. Prowlarr `config/host`

Prowlarr 2.5.2.5491。`GET /api/v1/config/host` 回 39 個欄位，認證相關的五個都在：

| 欄位 | 新裝的值 | 說明 |
| --- | --- | --- |
| `authenticationMethod` | `"none"` | `none` / `basic` / `forms` / `external` |
| `authenticationRequired` | `"enabled"` | `enabled` / `disabledForLocalAddresses` |
| `username` | `""` | |
| `password` | `""` | 寫入用明文；讀回來是雜湊 |
| `passwordConfirmation` | `""` | 少了它 PUT 會被拒 |
| `apiKey` | 32 字元 | 與 `config.xml` 的 `<ApiKey>` 相同 |

設定流程與實測結果：

1. API key 從唯讀掛載的 `/ext/prowlarr/config.xml` 的 `<ApiKey>` 讀得到（plan §9.2 的做法成立），
   首次啟動後就有，長度 32。
2. `PUT /api/v1/config/host/{id}`（id 為 1），body 是**完整的 config/host 物件**加上
   `authenticationMethod: "forms"`、`authenticationRequired: "enabled"`、`username`、`password`、
   `passwordConfirmation` → **202 Accepted**，Prowlarr 隨即自行重啟。
3. 重啟後：帶 `X-Api-Key` 的 API 回 200，不帶的回 **401**，`GET /ping` **仍然匿名 200**。
   `password` 讀回來是 base64 雜湊而非明文。

對 plan 的影響：

- §9.3 第 2 步用 `/ping` 偵測 Prowlarr 是對的 —— 它在設了 Forms 帳密之後仍然匿名可用，
  所以健康檢查不會因為使用者加了密碼就變紅。
- §9.3 第 1 步「同一組帳密也套用到 Prowlarr 介面」的實作就是上面的 PUT，要記得
  `passwordConfirmation`，並且要等重啟完成才能繼續下一步。

## 4. 硬鏈接（brief §4.4、§20.6）

`scripts/experiments/hardlink.sh`，三種情境：

| 情境 | 掛載型態 | 結果 |
| --- | --- | --- |
| Linux ext4 單一掛載根（見下方說明） | `ext4 rw,relatime` | **PASS**，dev=2096、inode 相同、nlink=2 |
| `torrent/` 與 `library/` 分開掛兩個 volume | overlay + 兩個 bind | **FAIL**，`ln: Cross-device link`，退出碼 1 |
| Windows NTFS bind mount | `9p aname=drvfs` | **PASS**，dev=70、inode 相同、nlink=2 |

**ext4 那一列不是一台實體 Linux 宿主**：用的是 Docker Desktop 自己的 Linux VM
（`docker-desktop` 發行版）上的 ext4 路徑 `/mnt/docker-desktop-disk/berth-exp-data`。
它是 daemon 端的檔案系統，`link()` 走的是與原生 Linux 宿主相同的路徑，但硬體、核心版本與
檔案系統選項都不是使用者機器上的那些。原生 Linux 宿主與 NAS（Synology / QNAP / TrueNAS）
都仍未測 —— 手上沒有機器，brief §20.6 兩條都保留。

負面對照是重點：腳本真的會失敗、真的回非零，所以 plan §9.5 拿它當 Route 健康檢查是有效的，
不是只看 `st_dev`（brief §20.2 說同一個檔案系統掛兩次仍會 `EXDEV`，上表第二列就是那個情況）。

## 5. 改了哪些決定

| 文件 | 原本 | 改成 | 依據 |
| --- | --- | --- | --- |
| brief §7.2 | 電影檔名範例 `<Title> (<Year>) - [BD]…` | 加上 `[tmdbid-<id>]`，與資料夾名一致 | §1.2 |
| brief §7.7 | 「版本標籤即 tags 字串」 | 只對電影成立；劇集的版本選單顯示整個檔名 | §1.3 |
| brief §20.1 | `zh-Hant`/`zh-Hans` 是否可用未證實 | 10.11 認得、10.10 不認得 → 不用 | §1.5 |
| brief §20.1 | 深連結 10.9+ 是否改為 `#/details` 未證實 | `#!` 與 `#` 兩種在 10.10 / 10.11 都能開 | §1.8 |
| plan §5 | 模板「實驗確認後才凍結」 | **凍結**，一個字沒改 | §1.1、§1.2、§1.5 |
| plan §8.1 | `torrents/files.name` 相對基準「兩種都試」 | 相對 `save_path`；正規化尾斜線後組路徑再 `stat` 驗證 | §2.2 |
| plan §8.2 | `find_episodes` 用 `parentId=<series>` | 改用媒體庫 recursive + `Path` 前綴，或重試 | §1.7 |
| plan §9.2 | 「不預置 `ServerDomains`」 | 維持，並補上 port 檢查與發佈 port 不可偏移 | §2.4 |
| plan §9.4 | `POST /Startup/User` | 前面要先 `GET /Startup/User` | §1.6 |
| plan §9.4 | `POST /Library/VirtualFolders` body | body 要包成 `{"LibraryOptions": {...}}` | §1.6 |
| plan §9.4 | 重啟後輪詢 `/System/Info/Public` | 改輪詢要用的管理員端點回 200（載入中會回 503） | §1.6 |

## 6. 還沒做的

- **原生 Linux 宿主與 NAS 上的硬鏈接**：§4 的 ext4 那一輪跑的是 Docker Desktop 自己的
  Linux VM（daemon 端的 ext4），不是另一台實體機器。`hardlink.sh` 沒有相依，ssh 進去
  `sh hardlink.sh /volume1/<share>` 就能跑，brief §20.6 保留這一條。
- **版本標籤含中文**：實驗用的 tag 全是 ASCII（`[BD][2160p][CHT+JP][Sakurato]`），
  但 brief §6.8 的 group token 保留字幕組原文，中文組名沒被測到。brief §20.1 已標未證實。
- **benchmark v0 的 20 筆真實 torrent fixture** 與 **Mikan / Nyaa 的 RSS fixture**：
  不屬於本票（分別在 M1 的解析器票與 M3 的 RSS 票），brief §20.6 保留。
- **絕對編號換算的失敗率量化**：同上，M1 的解析器票。
