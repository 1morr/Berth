# Berth 設計綱要（Design Brief）

> 本文件取代原始需求 prompt，作為後續設計、實作與 AI 協作的唯一輸入。
> 它描述「要做什麼、邊界在哪、已定與未定」，不描述實作細節。
> 文中「本系統」即 Berth。
>
> 標記：
> - 【決定】已採納的預設方案；除非出現新事實，不重開討論。
> - 【建議】本文件作者的推薦，等 owner 拍板後改為【決定】。
> - 【待決】需要 owner 選擇，文中附推薦。
> - 【研究】實作前必須先做的調查或實驗，附驗收方式。

---

## 0. 一句話

一個自託管的「媒體取得與入庫協調器」：把索引站（Torznab）搜尋或 RSS 命中的 torrent 送到 qBittorrent，下載完成後解析內容、比對 TMDB metadata、以硬鏈接入庫到 Jellyfin 媒體庫，並維護一份可追溯、可修復的入庫帳本。

第一階段目標：**探索 → 下載 → 入庫 → 在 Jellyfin 可播放** 的全流程跑通，同時支援動漫、美劇、韓劇與電影。

---

## 1. 產品定位

### 1.1 本系統負責

- **探索與決策**：TMDB 媒體牆與詳情頁、索引站 torrent 搜尋與挑選、RSS 訂閱與規則。
- **取得**：把 torrent 送進 qBittorrent、追蹤下載狀態。
- **入庫**：解析 torrent 內容 → 比對 metadata → 產生入庫計劃 → 硬鏈接 → 觸發 Jellyfin 掃描。
- **帳本與修復**：記錄每個入庫檔案的來源，偵測孤兒與斷鏈，支援重新入庫、重新匹配與分範圍刪除。
- **媒體庫檢視**：以 Jellyfin 資料加上本系統狀態呈現，作為人工修正與未來 AI 功能的入口。
- **可觀測性**：每個 torrent 有完整時間線（誰觸發、何時下載、怎麼解析、何時入庫、出了什麼錯）。

### 1.2 本系統不負責（交給外部服務）

| 職責 | 交給 | 說明 |
| --- | --- | --- |
| 播放、轉碼、觀看紀錄、刮削圖片與簡介 | Jellyfin | 本系統只讀取 Jellyfin 的媒體庫與項目狀態 |
| 下載協定、做種、限速、分享率、種子清理 | qBittorrent | 做種策略用 qBittorrent 的分類設定，本系統只處理「種子被移除後」的善後 |
| 索引站接入 | Prowlarr 或 Jackett（Torznab） | 只依賴 Torznab 協定。開箱即用套件預設打包 Prowlarr（§16.3），已有 Jackett 的使用者直接填 Torznab 端點 |
| Metadata | TMDB | 第一階段唯一的 provider，見 §10 |
| 同一集多版本的合併顯示 | Jellyfin + MergeVersions 插件 | 本系統只保證命名讓插件能合併 |

刻意不做的事（第一階段）：品質檔案自動升級替換（Sonarr 的 quality profile upgrade）、內嵌播放器、多人審批、非影片媒體、AI 側面板。見 §18。

### 1.3 參考的成熟產品與採用的慣例

| 面向 | 借鑑 | 採用的慣例 |
| --- | --- | --- |
| 目錄與硬鏈接 | TRaSH Guides、Sonarr/Radarr | 單一掛載根 `/data`；「qBittorrent category = 一個目標媒體庫」 |
| 探索頁與帳號 | Seerr（2026 年起 Jellyseerr 與 Overseerr 的合併專案） | TMDB 媒體牆；用 Jellyfin 帳號登入，Jellyfin 管理員即本系統管理員；深連結格式 |
| 入庫管線 | Sonarr/Radarr | Completed Download Handling、Interactive Import（人工入庫）、Root Folder、健康檢查 |
| RSS | AutoBangumi | 訂閱 + 規則 + 解析 + 重命名；一次性 RSS 連結 |
| 檔案命名 | Jellyfin 官方命名文件 | `[tmdbid-…]` 鎖定 ID、`Season 00` 放 Specials、extras 資料夾 |
| 帳本 | Sonarr 的 EpisodeFile 表 | 每個入庫檔案一筆紀錄，含來源與品質資訊 |

### 1.4 名稱【決定】

**Berth**（船席）：torrent 靠岸、卸貨、入倉。五個字母，直接用作 Docker service 名、CLI 名與 qBittorrent category 前綴。衝突檢查見 §20.5：自託管媒體領域無同名專案；PyPI 與 npm 上有同名的舊套件，但本系統以 Docker image 發佈，不佔用這兩個註冊名。

---

## 2. 名詞表（Ubiquitous Language）

實作、UI、文件與 API 一律使用這些詞，不另造同義詞。

| 名詞 | 定義 |
| --- | --- |
| **Media** | TMDB 上的一部電影或一部劇集。主鍵 `tmdb:movie:<id>` / `tmdb:tv:<id>`。劇集底下有 Season 與 Episode（TMDB 的編號）。 |
| **Tracked Media** | 本系統曾為其下載、訂閱或入庫過的 Media。媒體庫頁與 RSS 規則只針對 Tracked Media。 |
| **Library Route**（UI 顯示「媒體庫」） | 一個入庫目的地：Jellyfin 媒體庫 + 一個寫入目標路徑 + 一個 qBittorrent category + 一個命名 profile（`standard` / `anime`）。 |
| **Download Job** | 一個 torrent 在本系統中的生命週期紀錄，以 info hash 為鍵。 |
| **Trigger** | Job 的來源：`manual`（使用者在詳情頁選擇）、`rss:<rule>`、`reimport`、未來 `ai`。 |
| **Import Source** | 待入庫的檔案集合：通常是 Job 的內容目錄，也可以是 complete 目錄下的任意資料夾（重新入庫時）。 |
| **Import Plan** | 對一個 Import Source 的每個檔案，決定「分類、對應 Media/季/集、目標路徑、tags、信心與理由」的可審核計劃。Plan 在被套用前不動任何檔案。 |
| **Ledger Entry** | 一條「來源檔案 → 目標硬鏈接」的紀錄：torrent hash、來源相對路徑、目標路徑、inode、Media/季/集、tags、plan id、時間。 |
| **Review Queue** | 低信心 Plan、未匹配檔案、重複版本、孤兒等待人工處理的清單。 |
| **Unmatched** | 解析後無法對應到 TMDB 任何一集/一部的影片或字幕檔。 |
| **Extras** | 可辨識但不屬於正片的內容：NCOP/NCED、PV、CM、Menu、預告、花絮、特典映像。 |
| **Orphan / Issue** | 帳本、qBittorrent、complete 目錄、library 目錄四方不一致的項目，見 §9。 |
| **Event** | Job 時間線上的一筆事件，含類型、時間、觸發者、細節 JSON。 |

---

## 3. 外部服務與整合邊界

| 服務 | 用途 | 整合方式 | 備註 |
| --- | --- | --- | --- |
| Prowlarr / Jackett | torrent 搜尋 | Torznab API（`caps`、`search`、分類碼）；Prowlarr 另有 REST API 可由 Berth 自動加入索引站（§16.3） | 搜尋結果短暫快取 |
| qBittorrent | 下載 | Web API v2：新增、分類、輪詢 `sync/maindata`、檔案清單、刪除、搬移 | 無 webhook，用輪詢；活躍時短間隔、閒置時退避。支援下限 4.4（API 2.8.4），adapter 依 `webapiVersion` 切換 `paused`/`stopped` 等改名參數（§20.2） |
| Jellyfin | 媒體庫與播放 | 伺服器 API key 做媒體庫操作；使用者以 Jellyfin 帳號登入本系統 | 讀 VirtualFolders 得到媒體庫與路徑；針對路徑觸發掃描；用路徑反查 item id |
| TMDB | metadata | REST v3，本地快取 | 探索、搜尋、季集結構、別名與翻譯、episode groups |

所有外部呼叫都經由一層 adapter，adapter 的介面以本系統的名詞（§2）表達，不外洩第三方資料結構到核心邏輯。這也是未來替換 Prowlarr、Emby 或其他 provider 的邊界。

---

## 4. 路徑模型

### 4.1 三層路徑【決定】

```
/data/torrent/incomplete/<torrent 內容>                 qBittorrent 全域 temp path
/data/torrent/complete/<route-slug>/<torrent 內容>       qBittorrent category save path
/data/library/<Jellyfin 媒體庫路徑>/<Media 資料夾>/...     由 Jellyfin 推導，不讓使用者重填
```

- `incomplete` 與 `complete` 的根目錄在 WebUI 設定，預設如上。
- `complete/<route-slug>` 對應一個 qBittorrent category；category 名稱預設 `berth-<route-slug>`，可改。
- library 路徑一律從 Jellyfin `VirtualFolders` 讀取，使用者只做「選擇」，不做「輸入」。

### 4.2 為什麼 incomplete / complete **不**鏡像 library 結構【決定】

原始想法：`complete/<library>/<media title>/<torrent name>`，讓人在檔案系統就能看出哪個 torrent 屬於哪部作品。不採用，理由：

1. 送單時對「這是哪部作品」的判斷可能是錯的（RSS 誤判、選錯季），之後修正就得搬 torrent 資料，做種中搬移是最容易出事的操作。
2. 目錄名會鎖死在送單當下的標題，TMDB 改名、使用者改匹配都會讓目錄說謊。
3. Sonarr/Radarr 這類成熟產品都用「category 一層、扁平」，整個生態（TRaSH Guides、qBittorrent 分類）都以此為前提。
4. 「這個 torrent 是哪部作品」由本系統的 Job 頁與帳本回答；檔案系統層面用 `find -samefile` 也能反查。
5. incomplete 是暫態，qBittorrent 完成時自行從 temp path 搬到 save path；鏡像它沒有任何收益。

保留的替代：Job 頁提供「開啟 complete 目錄」與「顯示所有硬鏈接目標」，滿足「我想知道這堆檔案是什麼」的需求。

### 4.3 一個 Jellyfin 媒體庫有多個路徑【決定】

- Library Route = （Jellyfin 媒體庫, **一個**寫入目標路徑）。
- 媒體庫只有一個路徑時自動選定；多個路徑時建立 Route 時選一個作為寫入目標。
- 該媒體庫的其他路徑視為唯讀：用來辨識「已存在的媒體」與偵測孤兒，不寫入。
- 同一個 Jellyfin 媒體庫可以建立多個 Route（例如兩顆碟各一個 Route），但每個 Route 有自己的 category 與 complete 子目錄，硬鏈接檢查各自獨立。

### 4.4 硬鏈接能力驗證【決定】

- 每個 Route 建立時與每次啟動時執行：在 `complete/<route-slug>` 建暫存檔 → 真的呼叫 `link()` 鏈接到目標路徑 → 比對 inode 與 device → 刪除。失敗即 Route 標記為不健康，拒絕送單。只比 `st_dev` 不夠（同一檔案系統掛兩次、btrfs 子卷、ZFS dataset、mergerfs 都會 `EXDEV`，§20.2），所以一定實際鏈接一次。
- 也檢查：目標路徑對本系統可寫、qBittorrent 回報的 save path 在本系統看得到、Jellyfin 以 `Environment/ValidatePath` 確認看得到探測檔、category 為 autoTMM 模式；temp path 未啟用只警告。
- **硬鏈接失敗不退回複製**（與 Sonarr 不同）：複製會讓刪除範圍與空間估算失真，違反「避免複製檔案」的需求。
- Docker 部署要求三個容器（qBittorrent、Jellyfin、本系統）以**相同容器路徑**掛載同一個宿主父目錄（TRaSH 的單一掛載慣例）；路徑字串可以是 `/data` 以外的任何值，套件預設 `/data`，既有服務沿用它們原本的路徑（§16.4）。第一階段不做 remote path mapping，設定精靈直接驗證「你看到的路徑 qBittorrent 與 Jellyfin 也看得到」。
- 已知限制要寫進 README：Docker Desktop（Windows/macOS）bind mount 的硬鏈接支援與 mergerfs / 跨 dataset 情境，見 §20 的查證結果。

### 4.5 檔名與目錄安全

- Media 資料夾名在 Media 第一次被 track 時決定並寫入 DB，之後 TMDB 改名不自動改資料夾（避免 Jellyfin 重掃與帳本漂移）；提供「重新命名」的顯式動作。
- 去除 `/ \ : * ? " < > |` 與控制字元，尾端不留 `.` 與空白（相容 SMB/Windows 掛載）；長度上限 200 bytes。

---

## 5. 下載與入庫管線

### 5.1 狀態機【決定】

```
requested ─► submitted ─► metadata_ready ─► downloading ─► completed ─► planning ─┬─► importing ─► imported
                │                                                                  └─► review ────┘
                └─► submit_failed
downloading ─► stalled / missing_files / client_removed（可恢復或需人工）
importing  ─► import_failed（可重試）
任何狀態 ─► removed（使用者刪除，帳本保留或清除依刪除範圍）
```

- **metadata_ready 做預先計劃（pre-plan）**：一拿到檔案清單就用規則跑一次 Plan，不動檔案。目的：在下載完成前就發現「這個 torrent 根本不是那一季」或「全部是 OST」，讓使用者可以立刻取消。這一步是原流程沒有的，成本極低。
- **completed 的判定**：qBittorrent `progress == 1` 且 `completion_on > 0` 且 state 不是 `moving` / `checking*`（temp path 搬到 save path 期間會是 `moving`，§20.2）；再以 `stat` 確認每個檔案存在於 save path 下。`priority == 0`（不下載）的檔案不進 Plan。
- **completed 觸發正式 planning**：此時可讀 mediainfo（時長、音軌、內封字幕語言），信心明顯高於只看檔名。
- **planning 的產出是 Plan，不是副作用**。高信心 Plan 自動進 importing；否則進 review。
- **importing 逐檔寫帳本**：每成功鏈接一個檔案就寫一筆 Ledger Entry。中途失敗可重跑，已完成的檔案跳過（以目標 inode 判定）。
- 入庫完成後：以 `POST /Library/Media/Updated` 通知變更路徑 → 延遲反查 Jellyfin item id 寫回帳本 → 媒體庫頁可顯示「可播放」。反查沒有路徑篩選 API（§20.1），做法是：在該媒體庫列出 Series 並以 `ProviderIds.Tmdb` 或路徑比對，再列該 Series 的 Episode 以 `Path` 比對；找不到就排程重試，多次失敗記為 Issue。

### 5.2 事件（Timeline）

每個 Job 的所有轉換都寫 Event，至少包含：

`created(trigger, user, media, route)`、`submitted(client, category, save_path)`、`metadata_received(file_count, total_size)`、`preplan(result, confidence)`、`progress(每 25% 一筆)`、`completed`、`plan_generated(engine=rules|ai, confidence, model, tokens, cost)`、`review_required(reason)`、`review_decided(user, changes)`、`linked(file, target)`、`link_failed(file, error)`、`jellyfin_scan_requested(paths)`、`jellyfin_item_resolved(item_id)`、`issue_detected(type)`、`deleted(scope, user)`。

Event 是 Job 頁時間線的資料來源，也是未來 AI 理解「發生了什麼」的介面。

### 5.3 不變量

- 永不移動、重新命名或修改 `complete` 下的檔案（做種依賴它們）。
- 永不在 torrent 仍在 qBittorrent 內時刪除 complete 檔案。
- library 內只寫「本系統建立的硬鏈接」；使用者原本就在 library 內的檔案（unmanaged）永不刪除、永不改名。
- 同一時間一個 Job 只有一個 worker 在處理（job lock）。
- 所有步驟可重入：重跑不會造成重複鏈接或重複事件（以 hash + 相對路徑 + 目標路徑做冪等鍵）。

---

## 6. 解析與比對策略

### 6.1 輸入

1. **上下文**：Job 是從哪個 Media 詳情頁送出、Route 的 profile、RSS 規則綁定的 Media 與季 offset。這是最強的訊號，第一階段的絕大多數 Job 都有上下文。
2. **torrent 名稱**與**檔案清單**（相對路徑、大小）。
3. 下載完成後的 **mediainfo**：時長、影音軌、內封字幕語言。
4. **TMDB**：該 Media 的季/集數、集標題、首播日、別名與各語言標題、episode groups。

### 6.2 第一層：檔案分類【決定】

以副檔名、大小、檔名關鍵字、所在資料夾名決定：

| 類別 | 判定訊號 | 第一階段處理 |
| --- | --- | --- |
| `video` | mkv/mp4/avi/ts/m2ts/wmv/flv/webm | 進入比對 |
| `subtitle` | ass/ssa/srt/sup/sub+idx/vtt | 進入字幕匹配 |
| `font` | ttf/otf/ttc；或位於 `Fonts/` | 忽略（未來：安裝到 Jellyfin 字型目錄） |
| `audio` | flac/mp3/m4a/aac/ogg/wav；或位於 `CDs/` `OST/` `Scans/` 附近 | 忽略（未來：入音樂庫） |
| `image` | jpg/png/webp/bmp；`Scans/` | 忽略 |
| `archive` | zip/rar/7z | 忽略但記錄；常見內容是字幕或字型（未來：解壓字幕） |
| `sample` | 檔名含 `sample` 且大小遠小於同目錄影片 | 忽略 |
| `disc` | `BDMV/`、`VIDEO_TS/` 結構 | 整體標記為需人工 |
| `extra` | NCOP/NCED/OP/ED（無集號）、PV、CM、Menu、Preview、Trailer、Making、Interview、`特典`、`映像特典`、`SPs/` 中非 SP 編號者 | 進入 extras 路徑（§7.3） |
| `other` | nfo/txt/url 等 | 忽略 |

分類器要能被 mediainfo 修正：例如檔名像正片但時長 90 秒 → 降為 `extra`。

### 6.3 第二層：發佈名解析 → ReleaseInfo

對 torrent 名與每個檔名解析出結構化欄位（缺就留空，不猜）：

`title_candidates[]`、`season`（顯式）、`episode`/`episode_range`、`absolute_number`、`version`（v2/v3）、`group`、`source`（BD/WEB/DVD/HDTV/Remux）、`resolution`、`video_codec`、`bit_depth`、`audio`、`subtitle_langs[]`、`subtitle_kind`（hardsub/softsub/external/unknown）、`edition`（Remaster/Director's Cut/Uncut/…）、`year`、`season_hint_from_folder`、`special_kind`（SP/OVA/OAD/Movie/NC）。

- 沒有現成庫能處理中文字幕組命名（§20.4）。【決定】解析分兩段：先用本系統維護的 **CJK 字幕組詞典**（簡繁/繁日/簡日/BIG5/GB/CHT/CHS/內嵌/內封/外掛/第 N 話/第 N 集/全集/合集/第 N 季/劇場版/番外/重製/★前綴/招募廣告/地區限制…，起點是 AutoBangumi `classic.py` 與 Sonarr `Parser.cs` 的規則）做正規化與 CJK 欄位抽取，再把剩餘字串交給成熟的西方命名解析庫（Python 用 guessit，TS 用 @ctrl/video-filename-parser）。
- 欄位定義對齊 AutoBangumi 的 `ParsedRelease`（含 `media_type` 與 `release_kind = single | range | batch | collection`），讓 benchmark 可以互相比較。
- 解析結果保留 `raw_title` 與 `matched_tokens[]`，讓 UI 能顯示「為什麼這樣判」。

### 6.4 第三層：對應到 Media / 季 / 集

依序嘗試，每一步產出候選與理由：

1. **上下文**：Job 帶 Media → Media 確定，只需決定季/集。
2. **標題比對**（無上下文時，主要是 RSS 與重新入庫）：以 TMDB `name` / `original_name` / alternative titles / translations 做正規化後比對，年份與類型（Animation + 日本）加權。
3. **季/集決定**，優先序：
   - 顯式 `SxxEyy` → 直接採用（並用 TMDB 驗證該集存在）。
   - 資料夾提示（`Season 2` / `S2` / `第二季` / `2nd Season` / `Part 2`）+ 檔內集號。
   - 標題含季名（`Title 2nd Season`、`Title Part 2`、`Title: Subtitle`）→ 用 TMDB 該劇各季的 `name` 與首播年比對決定季。
   - 只有集號（動漫常見）→ 若集號 ≤ 該季集數且上下文指定季 → 該季；否則視為 **絕對編號**，依序嘗試：TMDB episode group（Absolute 類型）、各季累計集數換算、以 TMDB 各集 `air_date` 與發佈時間推測「虛擬季」offset（AutoBangumi v3.2 的做法）。換算過程寫入理由。
   - 已知陷阱：TMDB 與 TVDB 近年都把 split-cour 動漫併成單季連續編號，而字幕組每個 cour 從 01 重數（§20.3）。RSS Rule 因此必須支援手動 offset；第二階段接入 Fribb/anime-lists 的 `season.tmdb` + `episode_offset.tmdb` 自動填 offset。
   - 韓劇常見 `E01` 無季 → 視為 Season 1（多數韓劇單季）並驗證集數。
4. **批次一致性**：同一 torrent 內所有影片以同一種模式解析成功、集號連續、數量與 TMDB 該季集數吻合 → 大幅加分；只有少數檔案解析失敗 → 那些檔案進 review，其餘照常入庫（不因為一顆 NCOP 卡住整季）。
5. **重複與衝突**：兩個檔案對應到同一（季, 集, tags）→ 標記衝突進 review；與帳本既有版本同 tags → 標記 `duplicate`（§7.8）。

### 6.5 信心與門檻【決定】

- 不用單一浮點數黑箱。每個 Plan item 帶 `confidence ∈ {high, medium, low}` 與 `reasons[]`。
- **high**：Media 由上下文或「標題 + 年份精確命中」決定；每個影片檔都有顯式季/集或資料夾提示；季/集都存在於 TMDB；無衝突；批次一致性通過。
- **medium**：Media 確定，但季/集靠推論（絕對編號換算、air_date offset、標題季名比對），或批次一致性只部分通過（少數檔案例外）。
- **low**：Media 不確定、有衝突、或影片數量與 TMDB 集數明顯不符。
- **high 與 medium 都自動入庫**（owner 決定，所有 Route 預設開啟；可在 Route 上關閉 medium）。medium 入庫的檔案帶 `audit` 旗標，在審核佇列以「已入庫待確認」列出，一鍵撤銷（拆鏈接、清帳本）或確認。硬鏈接讓撤銷幾乎零成本，這是敢於自動入庫 medium 的前提。
- low 進 review，並在啟用 AI 時觸發 §6.10。
- 取捨：medium 自動入庫會提高誤入庫率。§6.9 的 benchmark 必須分開報告 high 與 medium 的誤判率，若 medium 誤判率明顯高於 high，回頭收緊 medium 的定義而不是關掉自動入庫。

### 6.6 多集檔、合集、多季

- 單檔多集（`S01E01-E02`、`01-02`）→ 目標檔名用 Jellyfin 支援的 `S01E01-E02` 形式，帳本一筆對多集。
- 一個 torrent 多季（子資料夾分季或絕對編號連續）→ Plan 逐檔決定季，允許一個 Job 寫入同一 Media 的多季。
- 一個 torrent 多部作品（系列合集）→ 第一階段不自動處理：所有影片對不到上下文 Media 的檔案進 review，使用者在 review 時可把檔案指派給其他 Media。
- 分割光碟 `CD1/CD2` 電影 → 第一階段進 review。

### 6.7 外掛字幕與字型

匹配順序：

1. 檔名主幹與某影片完全相同（去掉語言後綴後）→ 該影片。
2. 位於 `Subs/` `字幕/` 等資料夾且檔名含集號 → 以集號對應影片。
3. 從檔名後綴或資料夾名判斷語言：`.tc` `.cht` `.zh-Hant` `繁體/` → zh-Hant；`.sc` `.chs` `.zh-Hans` `简体/` → zh-Hans；`.jp` `ja`；`JPSC` / `JPTC` → 雙語。
4. 對不到影片的字幕 → Unmatched。

輸出：以 Jellyfin sidecar 慣例命名 `<影片檔名主幹>.<標題>.<語言碼>.ass`。Jellyfin 無法用語言碼區分繁簡（§20.1），所以語言碼一律 `zh`，繁簡放在自由文字標題欄位，用 §6.8 的 token：`….CHT.zh.ass`、`….CHS.zh.ass`、日文 `….ja.ass`、英文 `….en.ass`、預設軌加 `.default`。標題欄位在播放器字幕選單的顯示方式列入 §20.6 實測。字型不入庫。

### 6.8 Tag 的保留方式【決定】

- 所有 tag 以**結構化欄位**存在 Ledger Entry 與 Plan item（§6.3 的欄位），檔名只是這些欄位的一種呈現。
- 檔名用固定順序與固定詞彙渲染，缺的片段直接省略【決定，owner 選英文 token】：

```
[<source>][<resolution>][<subtitle>][Hardsub]?[<group>][<version>][<edition>]
例：[BD][1080p][CHT+JP][Sakurato][v2]
例：[WEB][1080p][CHS][Hardsub][Lilith-Raws]
```

| 欄位 | token 集合 | 說明 |
| --- | --- | --- |
| source | `BD` `WEB` `DVD` `HDTV` `REMUX` | BDRip / BluRay → `BD`；WEB-DL / WebRip → `WEB`；BD 原盤 remux → `REMUX` |
| resolution | `2160p` `1080p` `720p` `480p` | 由解析或 mediainfo 取得，mediainfo 優先 |
| subtitle | `CHT` `CHS` `JP` `EN` 以 `+` 依此固定順序連接 | 只有繁中 → `CHT`；繁日雙語 → `CHT+JP`；簡繁分軌 → `CHS+CHT`；三語 → `CHS+CHT+JP`。字幕組常見寫法對應：繁體/BIG5/TC → `CHT`，简体/GB/SC → `CHS`，JPTC → `CHT+JP`，JPSC → `CHS+JP`，简繁 → `CHS+CHT` |
| hardsub | `Hardsub` | 內嵌字幕時才出現；內封 / 外掛不加 token |
| group | 字幕組名原文 | 去掉括號，保留大小寫與連字號 |
| version | `v2` `v3` … | 一般集數不加 |
| edition | `Remaster` `Director's Cut` `Extended` `Uncut` `Unrated` | 沿用 guessit 的 edition 詞彙 |

- token 是給 Jellyfin 版本選單與檔名看的；UI 顯示可另做在地化（`CHT+JP` 顯示為「繁日」）。
- 詞彙表集中在一個渲染表，改詞不改邏輯。

### 6.9 解析基準測試（Benchmark）【決定】

- repo 內維護一組 fixture：每筆含 torrent 名、檔案清單（路徑、大小）、上下文（Media id、profile）、期望輸出（每檔的分類、季、集、tags 或 unmatched）。
- 來源：真實 torrent 的檔案清單（Nyaa、dmhy、Mikan、公開 tracker），去除個資後入庫；每修一個解析 bug 就加一筆。
- CI 跑基準並輸出：整體與分類別（anime / tv / movie）的正確率、誤判率（錯誤自動入庫最嚴重，要單獨列）、需 review 比例。
- 目標：**誤自動入庫率趨近 0**，其次才是提高自動入庫率。先有 benchmark 才允許調整門檻或引入 AI。

### 6.10 AI 的角色【決定】

- AI 是 **fallback 解析器與助理，不是執行者**：只能產出 Plan，不能動檔案。
- 觸發條件：規則層信心為 low，且使用者開啟 AI 解析。high 與 medium 已自動入庫（§6.5），不呼叫 AI。
- 輸入（壓縮後）：torrent 名、檔案清單（同模式的檔案只送樣本 + 數量）、規則層的部分解析、TMDB 季集結構（集數、集名、首播日）、命名規則、使用者偏好。
- 輸出：JSON schema 固定的 Plan（逐檔分類、季、集、tags、confidence、reason）。程式做**結構與約束驗證**：集必須存在、不得兩檔同目標、副檔名與分類一致；驗證失敗即丟棄並回退 review。
- AI 產出的 Plan 一律進 review，除非使用者明確開啟「AI high 自動入庫」。
- 快取鍵：`torrent hash + 解析器版本 + prompt 版本`；同一 torrent 不重複付費。
- 每次呼叫記錄 model、tokens、費用到 Event；設定頁有月預算上限，超過即停用並提示。
- 第二個用途：RSS 未匹配項目與 Unmatched 檔案的「猜 Media」建議（同樣只建議不執行）。
- 引入時機：§17 的 M4，在 benchmark 存在之後，才能量化 AI 帶來的增益與誤判。

---

## 7. 命名與入庫結構

### 7.1 劇集（含動漫）【決定】

```
/data/library/<lib>/<Title> (<Year>) [tmdbid-<id>]/
  Season 01/<Title> (<Year>) - S01E01 - <Episode Title> [BD][1080p][CHT+JP][Group].mkv
  Season 01/<Title> (<Year>) - S01E01 - <Episode Title> [BD][1080p][CHT+JP][Group].CHT.zh.ass
  Season 00/<Title> (<Year>) - S00E01 - <Special Title> [...].mkv
  extras/<原檔名>.mkv
```

與原提案的差異與理由：

- 資料夾加 `(<Year>) [tmdbid-<id>]`：Jellyfin 以 ID 鎖定辨識，杜絕同名作品與翻譯差異造成的誤刮削。這是「動漫、電影、劇集互不污染」最重要的一招。
- 集標題只在 TMDB 已有正式標題時加入；缺或為佔位（`Episode 5`）時省略。不因 TMDB 後來補了標題而自動改名，提供顯式「依最新 metadata 重新命名」動作。
- 使用 `Season 01`（兩位數）；Specials 放 `Season 00`，集號沿用 TMDB season 0 的編號。
- Tag 渲染規則見 §6.8。

### 7.2 電影【決定】

```
/data/library/<lib>/<Title> (<Year>) [tmdbid-<id>]/
  <Title> (<Year>) - [BD][2160p][CHT+JP][Group].mkv
  <Title> (<Year>) - [WEB][1080p][CHS][Group2].mkv
```

同資料夾內以 ` - <版本標籤>` 區分多版本，這是 Jellyfin 原生支援的多版本方式，不需插件；檔名在 ` - ` 之前必須與資料夾名完全一致。Jellyfin 對結尾為 `p`/`i` 的標籤依解析度排序、其他字母排序（§20.1），標籤內可否含方括號列入 §20.6 實測；若不行，電影改用空白分隔、解析度置尾的標籤（`… - BD CHT+JP Group 2160p.mkv`）。

### 7.3 Extras【決定，取代原「unmatch 資料夾」的一部分】

NCOP/NCED、PV、CM、Menu、預告、花絮等**可辨識**的非正片內容，硬鏈接到 Jellyfin 支援的 extras 資料夾（名稱與位置依 §20 查證），讓 Jellyfin 把它們顯示為該作品的額外內容，而不是污染集列表。

### 7.4 Unmatched【決定，取代原「unmatch 資料夾」】

真正對不到 metadata 的影片與字幕**不入庫**，留在 `complete` 原位；本系統在 Media 頁與 Job 頁列出它們，提供「指派到某季某集」「標記為 extra」「忽略」三種動作。理由：

- Jellyfin 會嘗試把媒體庫內任何影片解析成集數，`unmatch/` 資料夾裡的 `[Group] Title - 25.mkv` 很可能被當成第 25 集，反而製造錯誤。
- 把不確定的東西鏈接進去再要求使用者清理，比不鏈接更難維護。
- 原需求「使用者能在媒體庫頁面重新匹配」完全保留，只是資料來源改成 complete 目錄 + 帳本。

### 7.5 標題語言【決定】

`Title` = TMDB 英文 `name`；英文缺或與 `original_name` 相同時用 `original_name`。資料夾名決定後凍結（§4.5）。

### 7.6 Specials / OVA / OAD / SP

- 能對到 TMDB season 0 某一集 → `Season 00/… - S00Exx`。
- 對不到但可辨識為 extra（NC/PV/CM）→ extras。
- 對不到且像正片（`SP1`、`OVA 2`、`特別篇`）→ Unmatched，等人工指派；這類是 review 的大宗，UI 要讓「把這檔指派為 S00E03」只需兩次點擊。

### 7.7 多版本並存

- 同一集不同 tags 的檔案並存在同一季資料夾。Jellyfin 原生的劇集多版本不可靠（會變成重複條目，§20.1），所以 **MergeVersions 插件是必要前提**，README 與設定精靈的健康檢查都要提示；本系統入庫後透過 Jellyfin 排程任務 API 觸發插件的合併任務（任務名需實測）。
- 版本標籤即 tags 字串，使用者在 Jellyfin 版本選單看到的就是它，所以 tags 詞彙要短且可讀。
- 命名唯一必須保證的事：同一集所有版本的檔名在 `S01E01` 之前的部分完全相同，且互相只差 tags。

### 7.8 重複版本

新 Plan item 與帳本既有 Entry 的（Media, 季, 集, tags）完全相同 → `duplicate`。自動模式預設 **跳過並記事件**；review 提供「取代舊版」「保留兩者（加 `[v2]` 類 tag 者本來就不同）」「跳過」。

### 7.9 是否必須在資料庫記錄檔案？

**是**。帳本是本系統的核心資產：

- 沒有帳本就無法回答「這個 library 檔案來自哪個 torrent」「這個 torrent 入庫到哪」「哪些鏈接斷了」。
- 帳本讓刪除可以分範圍、讓重新入庫可以跳過已完成的檔案、讓 review 的修正可追溯。
- inode 掃描可以在災難時重建大部分帳本（同 device 下找相同 inode），這是備援不是主路徑。

---

## 8. 最小資料模型

只列實體與關鍵欄位，型別與索引由實作決定。

- `users`：Jellyfin user id、顯示名、角色（admin / user）、偏好。
- `services`：qBittorrent / Jellyfin / 索引站 / TMDB 的連線設定與最後健康狀態。
- `routes`：Jellyfin library id、目標路徑、category、profile、啟用狀態、健康狀態。
- `media`：tmdb id、類型、標題（英文/原文）、年份、凍結的資料夾名、tracked、TMDB 快取（含季集結構、更新時間）。
- `jobs`：hash、名稱、trigger、user、media、route、狀態、qBittorrent 的 save/content path、時間戳。
- `job_files`：hash + 相對路徑、大小、分類、ReleaseInfo、mediainfo 摘要。
- `plans` / `plan_items`：job 或 import source、引擎（rules/ai/user）、版本、每檔決策、confidence、reasons、審核狀態與審核者。
- `ledger`：來源（hash、相對路徑、inode、device）、目標路徑、目標 inode、media/季/集、tags、plan item、Jellyfin item id、狀態（ok / target_missing / source_missing / inode_mismatch）。
- `events`：job、類型、時間、actor、payload。
- `rss_feeds` / `rss_rules` / `rss_items`：見 §15。
- `issues`：孤兒與斷鏈清單，見 §9。

---

## 9. 刪除、孤兒、修復

這組功能**合理且必要**：硬鏈接讓「刪了一邊另一邊還在」成為常態，沒有對帳就會累積垃圾，也無法安全刪除。

### 9.1 對帳（Reconciler）

排程與手動觸發，比對四方：帳本、qBittorrent（本系統 category 下的 torrent）、complete 目錄、library 目錄。

| Issue 類型 | 判定 | 預設建議動作 |
| --- | --- | --- |
| `library_link_missing` | 帳本有、目標檔不存在（使用者在 Jellyfin 或檔案系統刪了） | 重新鏈接 / 承認刪除並清帳本 / 連 complete 一起刪 |
| `source_missing` | 帳本有、來源檔不存在（torrent 被移除且刪檔） | 標記為「已無來源」，library 檔保留 |
| `inode_mismatch` | 目標與來源 inode 不同（有人用複製取代、或被轉碼覆蓋） | 若大小一致提供「以硬鏈接取代」；否則列出等人決定 |
| `orphan_complete` | complete 內的目錄不屬於 qBittorrent 任何 torrent 也不在帳本 | 刪除 / 重新入庫（adopt） |
| `unknown_torrent` | qBittorrent 本系統 category 下有 torrent 但無 Job | 認領（建 Job 並解析）/ 忽略 |
| `unmanaged_library_file` | library 內有本系統不知道的檔案 | **只列出，永不自動刪**；可「認領」進帳本 |
| `job_without_files` | Job 已 imported 但帳本為空 | 重新 planning |

### 9.2 刪除範圍【決定】

刪除是一組可組合的旗標，UI 用勾選框呈現（沿用 Sonarr 的「同時刪除檔案」慣例，但拆得更細）：

- 移除 library 硬鏈接（Jellyfin 會在下次掃描少掉它）
- 從 qBittorrent 移除 torrent（不刪檔）
- 刪除 complete 檔案（要求先移除 torrent，否則拒絕）
- 清除帳本與 Job 紀錄（否則保留為歷史）

顯示「預估可釋放空間」：只有當來源與所有鏈接都刪掉時才真的釋放，UI 要說清楚。

### 9.3 重新入庫

Import Source 可以是「complete 內任一資料夾」，不要求 torrent 仍存在。流程與正常入庫相同（planning → review/importing），帳本以來源相對路徑冪等，所以「刪了 library、保留 complete、再重新入庫」是一鍵動作。

### 9.4 重新匹配（Rematch）

Media 頁對某個檔案（已入庫或 Unmatched）選「改指派為 SxxEyy / 標記 extra / 忽略」：建立新硬鏈接 → 刪舊鏈接 → 更新帳本 → 觸發掃描。一律經過 Plan，讓修正也有紀錄。

### 9.5 Jellyfin 端的刪除

使用者在 Jellyfin 刪媒體只會刪 library 檔案，Reconciler 會發現 `library_link_missing`。未來可接 Jellyfin Webhook 插件即時偵測，第一階段靠排程。

---

## 10. Metadata Provider 策略【決定】

**第一階段只用 TMDB**，同時負責探索與季集結構。理由：

- Jellyfin 內建的劇集 provider 預設是 TMDB，本系統的季/集編號必須與 Jellyfin 顯示一致，否則檔名 `S02E01` 在 Jellyfin 會對到別集；同源最安全。
- Seerr 長期只用 TMDB，媒體牆體驗已被驗證（近期才加入實驗性 TVDB，目的只是配合 Sonarr）。
- TVDB v4 的「user-supported」金鑰要求**每位使用者自付訂閱並輸入 PIN**（§20.3），對自託管產品不可行；且 TVDB 在動漫 split-cour 上與 TMDB 採同樣的合併政策，換 provider 解決不了編號問題。引入第二個 provider 的代價是每個 Media 多一層 ID 對應與衝突處理，第一階段不值得。

已知弱點與對策：

- 動漫的季切分（split cour、長篇）TMDB 與字幕組編號常不一致 → 靠絕對編號換算 + review；第二階段【研究】接入 anime-lists 類的 AniList/MAL ↔ TMDB 對應。
- 若使用者在 Jellyfin 該媒體庫改用 TVDB 插件 → 本系統讀取 `LibraryOptions` 偵測並警告「編號來源不一致」。

---

## 11. 帳號與權限【決定】

沿用 Seerr 做法：以 Jellyfin 帳號登入本系統。

- 初次設定：輸入 Jellyfin 位址 → 以 Jellyfin **管理員**帳號登入 → 該帳號成為本系統 admin，並產生本系統用的 Jellyfin API key。
- 其他 Jellyfin 使用者可登入，預設角色 `user`（可探索、可送單到指定 Route、可看自己的 Job）；admin 可改 Route、刪除、審核。
- 不自建密碼系統；本系統的 `users` 表只存 Jellyfin user id 與偏好。
- 未來的審批、配額、通知都掛在這個角色模型上。
- 取捨：Jellyfin 掛掉時無法登入。可接受，Seerr 同樣如此。

---

## 12. 播放【決定】

第一階段 **深連結到 Jellyfin** 該項目的詳情頁（帳本存有 Jellyfin item id），格式沿用 Seerr 來源碼：`{externalUrl}/web/index.html#!/details?id={itemId}&serverId={serverId}`，10.9+ 是否需改為 `#/details` 列入實測。Jellyfin 沒有「直接開始播放」的穩定 URL。不做內嵌播放器：播放器牽涉轉碼協商、字幕、播放進度回報，是最大工作量且與本系統核心無關。媒體庫頁的價值在「狀態與修正」，不在「取代 Jellyfin 播放」。

---

## 13. 頁面清單

| 頁面 | 目的 | 關鍵內容 |
| --- | --- | --- |
| 設定精靈 | 首次啟動 | 建立管理員 → 偵測套件內的 Jellyfin / qBittorrent / Prowlarr 並一鍵設定，或連接既有服務 → 路徑 → 建立 Route → 健康檢查（§16.3） |
| 探索 | 找東西 | 趨勢 / 熱門 / 搜尋；卡片顯示狀態（未追蹤 / 部分 / 完整 / 下載中） |
| Media 詳情 | 決策中心 | TMDB 資訊、各季各集狀態、**搜尋 torrent**（結果表：大小、做種、來源、解析出的 tags、預估匹配）、選 Route 送單、RSS 訂閱、檔案清單（含 Unmatched 與 rematch）、版本並存清單 |
| 媒體庫 | 瀏覽與修正 | 依 Route 分頁；卡片牆；篩選：有 Issue / 有 Unmatched / 有待審 |
| 下載與活動 | 全域狀態 | 所有 Job 列表：狀態、進度、Route、trigger；點入 Job 頁 |
| Job 詳情 | 可觀測性 | **時間線**（§5.2）、檔案清單與各檔決策、Plan 歷史、動作（重新解析、重新入庫、刪除範圍） |
| 審核佇列 | 人工介入 | 低信心 Plan（逐檔可改）、已入庫待確認（medium 自動入庫的 audit 清單，可一鍵撤銷）、Unmatched、重複版本、Issue；批次核准 |
| RSS | 自動化 | 訂閱清單、規則清單、最近命中與未匹配項目、一次性 RSS 連結、規則試跑 |
| 健康與問題 | 維運 | 服務連線、Route 硬鏈接檢查、Reconciler 結果、磁碟空間 |
| 設定 | 管理 | 服務、路徑、Route、命名詞彙、解析與 AI 開關與預算、使用者角色 |

---

## 14. AI 接口預留【決定】

要預留，但只做便宜的事：

- **API-first**：UI 做得到的每個動作都是一個有名字、有 schema、冪等的服務命令（`search_torrents`、`add_download`、`generate_plan`、`apply_plan`、`rematch_file`、`delete_job`…）。未來的 AI 工具與 MCP server 只是包裝這些命令。
- **資料可讀**：Plan、Event、Issue 都是結構化 JSON，AI 不需要爬 UI。
- **不現在做**：agent 迴圈、側面板、工具權限模型。

---

## 15. RSS 設計要點

- **Feed**：URL、輪詢間隔、來源類型。【決定】第一批支援 **Mikan**（我的訂閱聚合 feed、單作品 feed、單作品 + 字幕組 feed）與 **Nyaa**（搜尋 feed、使用者 feed）；之後加 dmhy 與索引站（Prowlarr / Jackett）feed。每種來源一個 adapter，負責解析該站的 RSS 擴充欄位（Nyaa 的 infoHash / 大小 / 做種數、Mikan 的 torrent enclosure 與發佈時間）並輸出統一的 FeedItem；欄位名在實作時對照實際 feed 確認（§20.6）。
- **Rule**：綁定 Media + Route；條件：包含 / 排除關鍵字或 regex、字幕組白名單與優先序、解析度與字幕語言偏好；季對應與集號 offset（AutoBangumi 慣例，並可由 §6.4 的 offset 偵測預填）；策略：所有新集 / 只補缺集。預設條件沿用 AutoBangumi 的經驗：排除合集（`release_kind != single`）、一部作品一個字幕組；但**合集不是不能解析，只是不自動下載**，使用者仍可從一次性 RSS 或搜尋手動送單。
- **處理**：item 標題 → ReleaseInfo → 對 Rule 比對（標題相似度 + 條件）→ 去重（GUID/link；以及帳本已有同 Media/季/集/字幕組/版本）→ 建 Job（trigger = rss:<rule>）。
- **從 Media 頁建立訂閱**：選 Feed → 即時預覽該 Feed 中會命中的項目（dry-run）→ 確認。
- **一次性 RSS 連結**：貼上 URL → 解析全部 item → 勾選 → 送單，不建立訂閱。
- **未匹配 item**：RSS 頁列出，使用者可一鍵綁定到 Media（順便建立 Rule）；這是未來 AI 建議的位置。
- **排序**：RSS 依賴解析器與管線，因此在 M3 而非 M1（§17）。

---

## 16. 部署與跨切面需求

### 16.1 部署

- 技術棧【決定】：後端 Python（FastAPI + 同一程序內的背景 worker + SQLite），前端 React（Vite），單一容器發佈。`/config` 存資料庫與設定，`/data` 掛媒體根。
- **目標環境【決定】**：Linux（NAS 與伺服器）與 Windows（Docker Desktop，WSL2 後端）。兩種使用者：NAS 使用者已有目錄規劃、可能已有 Jellyfin；一般電腦使用者什麼都沒有，要能「下載一份 compose、跑起來、開瀏覽器」就完成。
- 範例 `docker-compose.yml` 含 `berth`、qBittorrent、Jellyfin、Prowlarr，四者掛同一個 `/data`；權限採 TRaSH 的「單一使用者 + UMASK 022」簡化方案（§20.2），四個容器同 `PUID/PGID`。
- `/data` 一律用宿主目錄 bind mount（`DATA_ROOT`），Linux 與 Windows 相同：Windows Docker Desktop 的 NTFS bind mount 硬鏈接已實測可用（§20.7）。不支援 exFAT；健康檢查在建立 Route 時即驗證。
- README 明列：硬鏈接前提（單一掛載、不可 exFAT、不可跨 btrfs 子卷 / ZFS dataset / mergerfs branch）、支援 Linux 宿主與 Windows Docker Desktop（NTFS）、qBittorrent 版本下限與必要設定（temp path、category autoTMM）、Jellyfin 側需安裝 MergeVersions 插件（套件模式自動安裝）、TMDB 的歸屬聲明與 logo。

### 16.2 跨切面需求

- **外部呼叫**：統一逾時、重試與退避；服務不可達時 Job 停在當前狀態並記事件，不判定失敗；健康檢查頁顯示每個服務最後成功時間。
- **資料庫**：SQLite WAL；schema migration 從 M0 就用（Alembic）；備份就是複製 `/config`；提供「從磁碟 inode 掃描重建帳本」的災難復原指令（§7.9）。
- **秘密**：API key 存在 DB，靠檔案權限保護，不做應用層加密（與 Seerr 相同），README 註明。
- **日誌**：結構化，每行帶 job id；Event 是使用者可見層，log 是維運層，兩者不互相取代。
- **安全**：所有 API 需登入；未來 AI / MCP 用個人 API token；容器非 root；不開 CORS 萬用字元。
- **測試**：解析 benchmark（純函式，CI 必跑）；管線整合測試用假的 qBittorrent / Jellyfin / TMDB adapter；docker compose 端到端至少覆蓋 M1 驗收流程。
- **i18n**：UI 繁體中文優先，字串集中管理，不做英文版直到有需求；檔名 token 與 log 一律英文。
- **授權**：MIT（與 Seerr、AutoBangumi 相同）。TMDB 條款限非商業使用，README 註明。

### 16.3 開箱即用（一鍵設定）【決定】

目標：新手使用者下載 compose 範本、`docker compose up`、開瀏覽器，之後所有設定都在 Berth 的精靈裡完成，不需要分別打開 qBittorrent、Jellyfin、Prowlarr 的介面。做法是「預置設定檔 + Berth 透過各服務 API 代為設定」，兩者都冪等，可重複按。

| 服務 | 預置（compose 範本） | Berth 一鍵設定（API） | 使用者仍需自己做 |
| --- | --- | --- | --- |
| qBittorrent | **只預置「讓 Berth 進得去」**：compose 內網免密白名單與 Host 檢查網域名。原因是 4.6.1 起首次啟動的隨機密碼只印在容器 log，Berth 拿不到，沒有這一步按鈕就登不進去 | 套用建議偏好（temp path、save path、autoTMM）、依 Route 建立 category、設定 WebUI 密碼；按下前顯示差異 | 無 |
| Jellyfin | 無 | 偵測「尚未完成初始精靈」→ 以 Berth 管理員帳密建立 Jellyfin 管理員 → 建立 Movies / TV / Anime 三個媒體庫（對應 `/data/library/{movies,tv,anime}`）→ 加入插件庫並安裝 MergeVersions → 重啟 → 自動建立三個 Route | 無 |
| Prowlarr | 無；Berth 唯讀掛載其設定目錄讀取 API key | 加入預設索引站清單（Nyaa.si、dmhy、AniDex、Anime Tosho、ACG.RIP、Mikan、1337x、YTS、EZTV、The Pirate Bay，可勾選）、以 Berth 管理員帳密設定介面登入 | 私有站的帳號 |
| TMDB | Berth 內建專案級 API key（Seerr 的做法，§20.7） | 無 | 可選：填自己的 key |
| 索引站 / RSS | 無 | Mikan、Nyaa feed 由使用者貼 URL | 貼自己的 Mikan 訂閱 URL |

- **每個服務各自判斷來源，沒有全局模式**。精靈逐一探測 compose 主機名（`jellyfin`、`qbittorrent`、`prowlarr`）：探得到且尚未設定過（Jellyfin 的 `StartupWizardCompleted=false`、qBittorrent 免密可進、Prowlarr 無索引站）→ 視為**套件內服務**，全自動；否則顯示連線表單 → **既有服務**，只做檢查，「套用建議設定」「加入媒體庫路徑」「安裝插件」各是一顆需確認的按鈕。NAS 使用者常見的組合是既有 Jellyfin + 套件內 qBittorrent 與 Prowlarr。
- compose 用 profiles：`.env` 的 `COMPOSE_PROFILES=jellyfin,qbittorrent,prowlarr` 預設全起；已有某服務的人把它從清單拿掉即可。
- 預置只在設定檔不存在時寫入一次，之後使用者在各服務介面改什麼都行；健康檢查發現關鍵設定漂移時提供「還原建議設定」按鈕。精靈的 qBittorrent 步驟會列出「已預置的項目」。
- 每顆按鈕都顯示「將會做什麼」與執行結果，失敗給出可複製的手動步驟。
- 各服務 API 的可行性與細節見 §20.7。

### 16.4 既有服務的接入規則【決定】

允許接入既有服務；NAS 使用者是主要客群，Seerr 與 Sonarr 也都支援。問題只有一類：路徑與檔案系統邊界。

- **唯一的硬規則**：Berth、qBittorrent、Jellyfin 三個容器把同一個宿主父目錄掛在**相同的容器路徑**，且下載目錄與媒體庫目錄都在它底下。路徑字串不必是 `/data`（`/volume1/media` 掛成 `/volume1/media` 也可以）；Berth 的 incomplete / complete 根目錄可設定，媒體庫路徑讀自 Jellyfin。
- **既有 Jellyfin 不搬媒體庫**：Jellyfin 的項目 ID 由路徑算出，改路徑等於全部變成新項目、觀看紀錄歸零。做法是用 Jellyfin 的「一個媒體庫多個路徑」：Berth 按鈕以 `POST /Library/VirtualFolders/Paths` 為既有媒體庫**加**一個 Berth 用的路徑（§20.7），Route 指向新路徑；舊媒體原地不動，在 Berth 只是 unmanaged 檔案。
- **既有 qBittorrent 不搬舊種**：使用者多加一個掛載，Berth 用自己的 `berth-*` category 與新的 save path；舊 torrent 留在原目錄，Berth 忽略非自己分類的 torrent。全域 autoTMM 關閉也無妨，Berth 送單時逐個 torrent 指定 `autoTMM=true`。temp path 未啟用只給警告，不阻擋。
- **健康檢查會擋下的情況**：qBittorrent 回報的 save path 在 Berth 看不到；Jellyfin 的媒體庫路徑在 Berth 看不到；兩者在 Berth 內是不同掛載（`link()` 回 `EXDEV`）；qBittorrent 低於 4.4；媒體庫掛 TVDB 插件（警告）。每項附「哪個容器少了哪個掛載」的 compose 修正片段。
- **跨主機驗證**：Berth 在 Route 目標寫一個探測檔，再以 `POST /Environment/ValidatePath` 請 Jellyfin 確認看得到同一路徑（§20.7）；Jellyfin 在別台機器而路徑不一致會立刻現形。
- **不支援**：Berth 與 qBittorrent 不在存放媒體的同一台機器（硬鏈接做不到）；remote path mapping（第一階段不做，見 §18）。

---

## 17. 里程碑（tracer bullet）

每個里程碑結束時 repo 都可運作、可部署。

| 里程碑 | 內容 | 驗收 |
| --- | --- | --- |
| **M0 骨架** | §20.6 的實驗（結果可能改變命名決定，所以最先做）、compose 範本（profiles）與最小預置、精靈（建立管理員、逐服務判斷套件內或既有、套件內服務全自動設定、既有服務連線與確認按鈕）、Route 建立、健康檢查 | 實驗結論寫回本文件；在乾淨的 Linux 與 Windows Docker Desktop 上 `docker compose up` 後只操作 Berth 即完成設定，四項健康檢查綠燈；另以「既有 Jellyfin + 套件內其餘服務」的組合走一次 |
| **M1 手動全流程** | 探索 → 詳情 → 索引站搜尋 → 送 qBittorrent → 輪詢 → 規則 planning → 硬鏈接 → 掃描 → 媒體庫頁顯示可播放 + 深連結；Job 時間線；benchmark v0 | 一部美劇一季、一部動漫一季、一部電影，三者不經人工入庫並在 Jellyfin 正確顯示 |
| **M2 修正與對帳** | Review Queue、Unmatched 指派、rematch、Reconciler、刪除範圍、重新入庫 | 刪掉 library 後可一鍵重建；Issue 表對三種人為破壞都能偵測 |
| **M3 RSS** | Mikan 與 Nyaa adapter、Rule、去重、一次性連結、dry-run | 一個動漫季度分別以 Mikan 與 Nyaa feed 全自動追完 |
| **M4 AI fallback** | AI Plan、驗證、快取、預算、Event 記帳 | benchmark 上 review 比例下降且誤入庫率不升 |
| 之後 | anime-lists 對應、Webhook、字型與字幕解壓、通知、多使用者審批、非影片媒體、AI 側面板 | — |

---

## 18. 明確延後或不做

| 項目 | 處置 | 理由 |
| --- | --- | --- |
| complete / incomplete 鏡像 library 結構 | 不做 | §4.2 |
| library 內的 `unmatch` 資料夾 | 不做，改為 UI 列表 | §7.4 |
| 內嵌播放器 | 延後 | §12 |
| AI 解析 | M4 | 先有 benchmark 才能評估 |
| 品質升級自動替換 | 不做 | 版本並存 + MergeVersions 已滿足；升級邏輯是 Sonarr 最複雜的部分 |
| remote path mapping | 不做 | 強制同路徑掛載更簡單、更不易錯 |
| 多 provider（TVDB / AniList） | 延後 | §10 |
| 字型安裝、字幕解壓、OST 入音樂庫 | 延後 | 非核心流程 |
| BDMV 原盤 | 只辨識不處理 | 需要 Jellyfin 端特殊結構 |
| 多使用者審批、配額、通知 | 延後 | 角色模型已預留 |

---

## 19. 決策紀錄與待決問題

已由 owner 拍板（2026-09-07）：

| 項目 | 決定 | 落點 |
| --- | --- | --- |
| 產品名稱 | Berth | §1.4、§20.5 |
| 技術棧 | Python（FastAPI + worker + SQLite）+ React | §16.1 |
| 檔名 tag | 英文 token（CHT / CHS / JP / EN 等） | §6.8 |
| 第一批 RSS 來源 | Mikan、Nyaa | §15、§17 M3 |
| medium 信心 | 所有 Route 預設自動入庫，帶 audit 旗標 | §6.5、§13 |
| 集標題 | 有正式標題才進檔名，不自動改名 | §7.1 |
| UI 語言 | 繁體中文優先，預留 i18n | §16.2 |
| 授權 | MIT | §16.2 |
| 目標環境 | Linux 與 Windows 的 Docker；NAS 與一般電腦使用者；套件內含 Jellyfin / qBittorrent / Prowlarr，開箱即用 | §16.1、§16.3 |
| 索引站管理器 | 套件預設 Prowlarr（有文件化 REST API 可一鍵加索引站）；Jackett 以 Torznab 端點接入 | §3、§16.3、§20.7 |

目前沒有待決事項。

---

## 20. 研究與查證結果

（本節由查證子任務填入，附來源。）

### 20.1 Jellyfin 命名、extras、字幕、多版本、API

來源：jellyfin.org 官方文件、api.jellyfin.org OpenAPI、jellyfin GitHub issues。標「未證實」者需實測。

**命名**

- 劇集資料夾 `Series Name (2018) [tmdbid-12345]`，年份與 ID 皆可選但官方建議加；可疊多個 ID。季資料夾必須是 `Season NN`（不可 `S01`），Specials 放 `Season 00`。集檔名支援 `S01E01`、`S01E01-E02`、`S02E03 Part 1`。（[identifiers](https://jellyfin.org/docs/general/server/metadata/identifiers)、[shows](https://jellyfin.org/docs/general/server/media/shows)）
- 純數字或數字開頭的劇名會讓 metadata 搜尋失敗（[#15860](https://github.com/jellyfin/jellyfin/issues/15860)）→ 用 `[tmdbid-…]` 鎖定可迴避。
- 集號後面接方括號 tag 曾造成 AniDB 插件誤判（[anidb#11](https://github.com/jellyfin/jellyfin-plugin-anidb/issues/11)）；核心解析器行為未證實 → §20.6 實測。
- 檔名中的 ` - ` 會觸發「多版本」regex：沒有 Season 資料夾時不同集會被誤併為版本（[#7855](https://github.com/jellyfin/jellyfin/issues/7855)）。本系統一律有 Season 資料夾，但仍需實測 §7.1 的格式。
- Extras 子資料夾名：`extras`、`behind the scenes`、`deleted scenes`、`interviews`、`scenes`、`samples`、`shorts`、`featurettes`、`clips`、`other`、`trailers`、`theme-music`、`backdrops`；**劇集層與季層都可放**。也支援 `-trailer`、`-short`、`-extra` 等檔名後綴。（[_video-external-extras.md](https://github.com/jellyfin/jellyfin.org/blob/master/docs/general/server/media/_video-external-extras.md)）
- 空的 `.ignore` 檔會讓整個資料夾被掃描排除；10.11 起非空 `.ignore` 支援 gitignore 語法。（[excluding-directory](https://jellyfin.org/docs/general/server/media/excluding-directory)）

**外掛字幕**

- 格式 `<影片名>.{flags}.{language}.{ext}`，flags 有 `default`、`forced`、`sdh`/`cc`/`hi`，另可放自由文字標題，例如 `… S01E01 Title.commentary.ja.aac`。（[_video-external-streams.md](https://github.com/jellyfin/jellyfin.org/blob/master/docs/general/server/media/_video-external-streams.md)）
- **中文語言碼是已知痛點**：`chi`/`zh`/`zho`/`zh-hk` 只被辨識為泛「中文」，`cht`/`zh-cn`/`zh-cht` 不被辨識（[#6302](https://github.com/jellyfin/jellyfin/issues/6302)）；`zh-Hant`/`zh-Hans` 是否可用未證實。
- 沒有可靠的語言碼能區分繁簡。可行做法：語言用 `zh`，繁簡放在自由文字標題欄位，例如 `<stem>.CHT.zh.ass`、`<stem>.CHS.zh.ass` → §20.6 實測標題欄位的顯示方式。

**多版本**

- 電影：同資料夾內 `Movie (2021) [tmdbid-…] - 1080p.mkv`，檔名必須與資料夾名完全一致直到 ` - `；` - ` 之後為版本標籤，結尾為 `p`/`i` 的標籤會依解析度排序，否則字母排序。（[_video-multiversion.md](https://github.com/jellyfin/jellyfin.org/blob/master/docs/general/server/media/_video-multiversion.md)）標籤內能否含方括號與中文未證實。
- **劇集原生多版本不可靠**：10.8 起要求每集自己一個子資料夾才會視為版本，且社群回報同一集兩個檔案通常變成重複條目而非版本選單（[discussion#7900](https://github.com/orgs/jellyfin/discussions/7900)、[discussion#16063](https://github.com/orgs/jellyfin/discussions/16063)、[#13432](https://github.com/jellyfin/jellyfin/issues/13432)）。結論：**劇集多版本必須靠 MergeVersions 插件**，本系統命名只需保證同集檔名的 `S01E01` 部分一致。
- MergeVersions 插件持續維護到 10.11 與 12.0，透過排程任務或設定頁手動觸發；沒有公開 API 可由外部呼叫，本系統可用 Jellyfin 的排程任務 API 觸發該任務（需實測任務名）。（[README](https://github.com/danieladov/jellyfin-plugin-mergeversions/blob/master/README.md)、[releases](https://github.com/danieladov/jellyfin-plugin-mergeversions/releases)）已知問題：偶發錯誤、無法停用、跨媒體庫合併。

**API**

- `GET /Library/VirtualFolders` 回傳 `Name`、`Locations[]`、`CollectionType`（movies / tvshows / music / mixed …）、`ItemId`、`LibraryOptions`（含 `TypeOptions[].MetadataFetchers`，可用來偵測 TVDB 插件）。
- 觸發掃描：`POST /Library/Media/Updated` 帶 `{Updates:[{Path, UpdateType: Created|Modified|Deleted}]}` 做路徑級通知；`POST /Library/Refresh` 是全庫掃描。沒有「掃描單一資料夾」的專用端點。
- `GET /Items` **沒有 `path` 篩選**。反查方式：以 `parentId=<library>&includeItemTypes=Series&fields=ProviderIds,Path` 找 Series（比對 tmdb id 或路徑），再以 `parentId=<series>&recursive=true&includeItemTypes=Episode&fields=Path` 取集並用 `Path` 比對。（[ItemsController.cs](https://github.com/jellyfin/jellyfin/blob/master/Jellyfin.Api/Controllers/ItemsController.cs)）
- **`DELETE /Items/{id}` 會刪除磁碟檔案**（`DeleteFileLocation = true`），本系統絕不呼叫它。（[LibraryController.cs](https://github.com/jellyfin/jellyfin/blob/master/Jellyfin.Api/Controllers/LibraryController.cs)）
- 登入 `POST /Users/AuthenticateByName` 回 `AccessToken`、`ServerId`、`User`；`POST /Auth/Keys` 建 API key。
- 深連結：`{server}/web/index.html#!/details?id={itemId}&serverId={serverId}` 仍被官方 webhook 範本使用；10.9+ 是否改為 `#/details` 未證實 → 實測。沒有「直接開始播放」的穩定 URL。
- Webhook 插件有 `ItemAdded` / `ItemDeleted`，但走排程批次且社群長期回報不可靠（[#252](https://github.com/jellyfin/jellyfin-plugin-webhook/issues/252)、[#367](https://github.com/jellyfin/jellyfin-plugin-webhook/issues/367)）→ 支持 §9 以排程對帳為主。

**Provider**

- 內建劇集 provider 預設 TMDb（另有 OMDb 與 .nfo）；TheTVDB、AniDB、AniList 都是插件。TVDB 與 TMDB 混用時 Specials 編號錯配有實例（[#13294](https://github.com/jellyfin/jellyfin/issues/13294)）；多 provider 同時啟用時鎖定 ID 也可能被覆寫（[#16268](https://github.com/jellyfin/jellyfin/issues/16268)）→ 支持 §10 單一 TMDB。
- AniDB / AniList 插件的編號語意沒有文件 → 不納入第一階段。

### 20.2 qBittorrent Web API 與硬鏈接 / Docker 限制

來源：qBittorrent master 原始碼（`torrentscontroller.cpp`、`serialize_torrent.cpp`）、`WebAPI_Changelog.md`、qbittorrent-api 客戶端文件、TRaSH Guides、Servarr wiki、man pages。**社群 wiki 的 API 頁面已過時**（連「5.0」頁面都還列 `paused` / `root_folder`），以原始碼為準。

**`torrents/add` 現行參數**（[torrentscontroller.cpp](https://raw.githubusercontent.com/qbittorrent/qBittorrent/master/src/webui/api/torrentscontroller.cpp)）

- `urls` / `torrents`、`savepath`、`downloadPath` + `useDownloadPath`、`category`、`tags`、`rename`、`autoTMM`、`contentLayout`（`Original` / `Subfolder` / `NoSubfolder`，API 2.7 / qB 4.3.2 起，取代 `root_folder`）、`stopped`（API 2.11.0 起取代 `paused`）、`stopCondition`、`seedMode`（API 2.16.0 起，同時移除 `skip_checking`）、`filePriorities`、`ratioLimit` / `seedingTimeLimit`（API 2.8.1）。
- master 已不讀 `paused` / `root_folder`。adapter 必須先讀 `app/webapiVersion`，依版本送 `paused` 或 `stopped`；`torrents/pause|resume` 在 5.0 改名 `stop|start`。
- 【決定】支援下限 qBittorrent 4.4（API 2.8.4，2022）；以 5.x 為主要測試目標。

**分類與路徑**

- `createCategory` / `editCategory` 參數：`category`、`savePath`、`downloadPathEnabled`、`downloadPath`。per-category 未完成路徑自 API 2.8.4 / qB 4.4.0 即存在，但 WebUI 直到 **5.2.0** 才有介面管理（[Changelog](https://raw.githubusercontent.com/qbittorrent/qBittorrent/master/Changelog)）。本系統不用它（§4.2），只用全域 `temp_path` / `temp_path_enabled`。
- `torrents/categories` 回傳鍵在 4.4.0–4.4.1 曾在 `savePath` / `save_path` 之間反覆，adapter 兩者都要接受。
- autoTMM 開啟時 save path 跟隨 category；`category_changed_tmm_enabled` 為真時改 category 路徑會**自動搬移所有該分類 torrent**。→ 本系統建立 category 後不再改其 savePath；使用者改 Route 目標時建立新 category，舊 Job 維持原位。
- TRaSH 明確要求 category 模式必須 `Automatic`（autoTMM），否則下載不會進分類資料夾（[Basic-Setup](https://trash-guides.info/Downloaders/qBittorrent/Basic-Setup)）。

**狀態與檔案**

- `torrents/info` 欄位含 `hash`、`name`、`state`、`progress`、`save_path`、`content_path`（API 2.6.1）、`download_path`（原始碼有、wiki 未列）、`completion_on`、`category`、`tags`、`added_on`。
- `state` 值：`error`、`missingFiles`、`uploading`、`pausedUP`/`stoppedUP`、`queuedUP`、`stalledUP`、`checkingUP`、`forcedUP`、`allocating`、`downloading`、`metaDL`、`pausedDL`/`stoppedDL`、`queuedDL`、`stalledDL`、`checkingDL`、`forcedDL`、`checkingResumeData`、`moving`、`unknown`。「完成」判定：`progress == 1` 且 `completion_on > 0` 且 state **不是** `moving` / `checking*`（從 temp path 搬到 save path 期間 state 為 `moving`，此時不可入庫）。
- `torrents/files` 回傳 `index`、`name`（含相對路徑）、`size`、`progress`、`priority`（0 = 不下載）、`availability`。`name` 相對於 `save_path` 還是 `content_path` 文件未明 → adapter 以 `stat` 驗證組出的絕對路徑，兩種都試。`priority == 0` 的檔案要從 Plan 排除。
- 其他端點：`setLocation`、`rename`、`renameFile` / `renameFolder`（API 2.8.0）、`delete(deleteFiles)`、`setCategory`（category 不存在回 409）、`addTags`、`recheck`。
- **沒有 webhook**；`sync/maindata` 以 `rid` 做增量輪詢。`autorun_enabled` / `autorun_program`（完成時執行外部程式，可帶 `%f` `%n`）可作為「喚醒輪詢」的加速手段，非必要。
- 登入 `auth/login` 回 `SID` cookie，且 **`Referer` / `Origin` 必須與 `Host` 一致**；可設 `bypass_local_auth` 與子網白名單。

**硬鏈接與 Docker**（[TRaSH Hardlinks](https://trash-guides.info/File-and-Folder-Structure/Hardlinks-and-Instant-Moves/)、[Servarr docker-guide](https://wiki.servarr.com/docker-guide)、[link(2)](https://man7.org/linux/man-pages/man2/link.2.html)）

- 硬鏈接不能跨檔案系統、分割區、volume、**mount**；`link()` 即使同一個檔案系統掛兩次也會 `EXDEV`。Docker 把兩個 volume 當成兩個檔案系統，所以 `/downloads` + `/media` 分開掛一定失敗；解法是單一 `/data` 掛載。
- exFAT 不支援硬鏈接；btrfs 子卷、ZFS dataset 各自是 mount 邊界，跨越即失敗；mergerfs 在 path-preserving 建立策略下跨 branch 回 `EXDEV`，其 FAQ 同樣要求單一掛載根（[mergerfs FAQ](https://trapexit.github.io/mergerfs/latest/faq/why_isnt_it_working/)）。
- 權限：TRaSH 建議「每個 app 一個使用者 + 共用群組 + UMASK 002」（資料夾 775、檔案 664），或簡化為單一使用者 + UMASK 022。本系統與 qBittorrent 至少要同群組且對兩側目錄可寫。
- Docker Desktop（Windows）：文獻無定論，本機實測 NTFS bind mount 硬鏈接可用（§20.7）。macOS VirtioFS 未查到硬鏈接限制，也未實測。
- `stat().st_dev` 相同是必要條件但不充分（同 FS 多次掛載仍失敗），所以 §4.4 的檢查一律真的做一次 `link()`。

**Sonarr / Radarr 先例**（[sonarr/faq](https://wiki.servarr.com/sonarr/faq)、[radarr/settings](https://wiki.servarr.com/radarr/settings)、[quick-start](https://wiki.servarr.com/sonarr/quick-start-guide)）

- Completed Download Handling：只在下載客戶端回報完成後才入庫；要求客戶端完成後**暫停而非移除**，並保留至少 14 天的歷史。
- 「Remove Completed」只在客戶端回報做種完成且 torrent 已停止時才移除 torrent 與檔案。本系統不做自動移除（§1.2），做種上限交給 qBittorrent 分類的 share limit；移除後的善後由 Reconciler 處理。
- 入庫預設硬鏈接，失敗時 Sonarr 會**退回複製**。【決定】本系統**不退回複製**：硬鏈接失敗即 Route 不健康並拒絕送單，因為複製會讓刪除範圍與空間估算失真。
- 人工入庫的官方名稱是 **Interactive Import**（逐檔指定作品/季/集，可選 Move 或 Copy/Hardlink）；「unmapped files」只是社群俗稱。本系統的 Review Queue 對應這個概念。
- Root Folder = 媒體庫根目錄，明文規定不可與下載目錄相同。

### 20.3 Metadata provider 與動漫 ID 對應

**TMDB**

- 季/集 schema：`season_number: 0` 為 Specials；每集有 `episode_number`、`name`、`air_date`、`episode_type`、`runtime`。（[tv-season-details](https://developer.themoviedb.org/reference/tv-season-details)）
- Episode Groups 類型：Original air date / **Absolute** / DVD / Digital / Story arc / Production / TV。Absolute 只在有人替該劇建立 group 時存在，不是每部都有。（[episode-group-details](https://developer.themoviedb.org/reference/tv-episode-group-details)）
- 標題：`name` 依 `language`（預設 `en-US`）回傳，翻譯缺時可能是空字串，**要自己 fallback 到 `original_name`**；`alternative_titles` 是各國別名，與 translations 無關，兩者都應納入標題比對。（[translations](https://developer.themoviedb.org/reference/tv-series-translations)、[alternative-titles](https://developer.themoviedb.org/reference/tv-series-alternative-titles)）
- `find/{external_id}` 支援 `imdb_id`、`tvdb_id` 等反查。（[find-by-id](https://developer.themoviedb.org/reference/find-by-id)）
- 速率：官方文件未列；TMDB 員工在論壇稱約 50 req/s、20 併發/IP。條款：非商業免費、需顯示 TMDB logo 與聲明「This product uses the TMDB API but is not endorsed or certified by TMDB.」（[faq](https://developer.themoviedb.org/docs/faq)）
- **動漫 split-cour 正被 TMDB 與 TVDB 同步合併成單季連續編號**（例如 Dandadan S2 併入 S1），字幕組編號則多數按 cour 重新從 01 起算 → 這是動漫季/集對應的主要錯誤來源。（[TMDB talk](https://www.themoviedb.org/talk/697d0680d564e13094e4e270)、[TVDB KB](https://support.thetvdb.com/kb/faq.php?id=61)）

**TheTVDB v4**

- 存取模型：商業協議，或「user-supported」金鑰但**每位終端使用者需自付約 $12/年訂閱並輸入 PIN**。（[v4-api](https://github.com/thetvdb/v4-api)、[KB#62](https://support.thetvdb.com/kb/faq.php?id=62)）→ 對自託管產品極不友善，支持 §10 不採用。
- 季類型：default(aired) / absolute / dvd / alternate / regional。Sonarr 只用 TVDB（經 Skyhook 代理），並靠 TheXEM 做 scene 編號對應（[xem-guide](https://wiki.servarr.com/sonarr/xem-guide)）。

**Sonarr 作為先例**

- Series Type：Standard / Daily / Anime（絕對編號）。預設動漫命名：`{Series TitleYear} - S{season:00}E{episode:00} - {absolute:000} - {Episode CleanTitle} [{Custom Formats}{Quality Full}]…{-Release Group}`。（[settings](https://wiki.servarr.com/sonarr/settings)）
- v4 以 Custom Formats 取代 Preferred Words；Release Profiles 保留 must / must-not contain。
- EpisodeFile（帳本先例）欄位：`relativePath`、`path`、`size`、`dateAdded`、`sceneName`、`releaseGroup`、`language`、`quality`、`mediaInfo`、`qualityVersion`（1 一般、2 proper、3+ 可用於動漫 v3）。（[starr sonarr](https://pkg.go.dev/golift.io/starr/sonarr)）§8 的 `ledger` 至少要涵蓋這些。

**動漫 ID 對應**

- **Fribb/anime-lists** `anime-list-full.json`（由 anime-offline-database + Anime-Lists 自動產生）：每筆含 `anidb_id`、`anilist_id`、`mal_id`、`kitsu_id`、`imdb_id`、`themoviedb_id`、`tvdb_id`，並有 `season {tvdb, tmdb}` 與 `episode_offset {tvdb, tmdb}`。**這就是「AniList/MAL 條目 → TMDB 季 + 集 offset」的直接資料**。（[Fribb/anime-lists](https://github.com/Fribb/anime-lists)）更新頻率未證實。
- Anime-Lists 的 `anime-list.xml` 只有 AniDB→TVDB（`defaulttvdbseason`、`episodeoffset`、`mapping-list`），無 TMDB。新專案 [anibridge-mappings](https://github.com/anibridge/anibridge-mappings) 目標是 AniDB/AniList/MAL/TMDB/TVDB 集級對應，可觀察。
- AutoBangumi v3.2 加入「Episode Offset Auto-Detection」：用 TMDB 各集 `air_date` 偵測「虛擬季」並建議 offset。（[autobangumi bangumi](https://www.autobangumi.org/en/feature/bangumi.html)）本系統 §6.4 的絕對編號換算應同時用「累計集數」與「air_date 區間」兩種訊號。
- Shoko + Shokofin 以 AniDB ED2K hash 辨識檔案，是動漫 metadata 的「黃金標準」但整套獨立生態，與 TMDB 路線不相容，不納入。

**Seerr（前 Jellyseerr / Overseerr）**

- 2026 年 3 月起 Jellyseerr 與 Overseerr 合併為 **Seerr**（[seerr-release](https://docs.seerr.dev/blog/seerr-release)）；本文件所有「Seerr」指它。
- 登入：以 Jellyfin / Emby / Plex 帳號登入，可選本地帳號；第一個以媒體伺服器**管理員**身分登入者成為 owner；權限為細粒度旗標（Manage Users、Manage Requests、Auto-Request…）。（[users](https://docs.seerr.dev/using-seerr/settings/users)）
- 可用性判定（來源碼 `server/lib/scanners/jellyfin/index.ts`）：讀 Jellyfin item 的 `ProviderIds.Tmdb`，缺則 `Imdb` → TMDB find，再缺則 `AniDB` → 內建 anime-list 對應。本系統 §9 認領 unmanaged 檔案時可沿用這條鏈。
- 深連結（來源碼 `server/entity/Media.ts`）：`{externalUrl}/web/index.html#!/details?id={itemId}&context=home&serverId={serverId}`。§12 採用此格式。

### 20.4 解析先例與真實 torrent 內容

**解析庫現況（2026-09）**

| 庫 | 語言 | 狀態 | 欄位 | CJK / 字幕組 |
| --- | --- | --- | --- | --- |
| [guessit](https://github.com/guessit-io/guessit) | Python | 活躍，v4.4.0（2026-07） | title / season / episode / absolute_episode / version / release_group / source / screen_size / video_codec / subtitle_language / edition / other 等極完整 | 弱：[#929](https://github.com/guessit-io/guessit/issues/929) 仍開著，fansub 括號格式常錯 |
| [anitopy](https://github.com/igorcmoura/anitopy) | Python | 停滯（2022） | anime_title / episode_number / release_group / release_version / video_resolution 等 | 無專門處理 |
| [anitomy](https://github.com/erengy/anitomy) | C++ | develop 分支重寫中（C++23） | 同上 | 無專門處理 |
| [anitomyscript](https://github.com/skiptirengu/anitomyscript) | JS/WASM | 2019 版本，落後上游 | 同上 | 無 |
| [@ctrl/video-filename-parser](https://github.com/scttcper/video-filename-parser) | TS | 活躍，v5.11（2026-07），Radarr 風格 | title / year / resolution / sources / videoCodec / revision / group / edition / languages；TV 模式 seasons / episodeNumbers | 無 |
| [parse-torrent-title](https://github.com/clement-escolano/parse-torrent-title) | JS | 活躍 | title / season / episode / resolution / codec / source / group，可擴充 handler | 無 |
| [dreulavelle/PTT](https://github.com/dreulavelle/PTT)（pip `parsett`） | Python | 活躍 | 西方 scene 命名 | 無 |
| torrent-name-parser | Rust | 停滯（2023） | 基本欄位 | 無 |

**結論**：沒有現成庫能處理中文字幕組命名，CJK 詞典一定要自己維護；西方命名交給 guessit（Python）或 @ctrl/video-filename-parser（TS）。可直接借鑑的 CJK regex 有兩處：

- **AutoBangumi `tokenizer/classic.py`**（[repo](https://github.com/EstrellaXD/Auto_Bangumi)，`backend/src/module/parser/analyser/tokenizer/classic.py`）：`_CJK_SUBTITLE_TAG`（简/繁/日/双语/内嵌/内封/外挂/多国）、`_SUBTITLE`（CHS/CHT/GB/Big5/JPSC/JPTC/Multi-Subs/PGS）、`_CHINESE_SEASON`（第N季/期，含中文數字）、`_CHINESE_EPISODE`（第N话/集）、`_FULL_COLLECTION` / `_COLLECTION`（全N话/合集/全集/总集篇/特典）、`_SPECIAL_CJK`（番外/特別篇）、`_MOVIE_CJK`（劇場版/電影版）、`_PREFIX`（★1月新番★）、`_RECRUIT`（招募廣告）、`_REGION`（僅限港澳台）、`_SOURCE`（Baha/B-Global/Bilibili/CR/AT-X/Abema/AMZN/NF/…）、`_CODEC`、`_AUDIO`。
- **Sonarr `Parser.cs`**（[raw](https://raw.githubusercontent.com/Sonarr/Sonarr/develop/src/NzbDrone.Core/Parser/Parser.cs)）：約 8 條中文動漫 pre-substitution（以 `[一-鿌]` 剝離中文標題、LoliHouse / Lilith-Raws / Skymoon-Raws 無括號格式、GM-Team 多括號格式、`第?(\d+)(话|集)?( END|完| Fin)?`），以及韓劇 `\.E(\d{2,4})\.\d{6}\.(.*-NEXT)$ → S01E$1` 規則。

**AutoBangumi 現況（main，2026-08）**

- 解析輸出 `ParsedRelease`：`title_en / title_zh / title_jp / group / season / episode / episode_end / media_type(EPISODE|MOVIE|OVA|OAD|SPECIAL|PV|OPENING|ENDING) / release_kind(SINGLE|RANGE|BATCH|COLLECTION) / resolution / source / subtitle / codecs / audio / version / tags / evidence`。§6.3 的欄位設計與此對齊。
- LLM 解析支援 OpenAI / Anthropic / Gemini，兩種模式：`primary`（LLM 為主但仍合併規則層的結構提示）與 `fallback`（只在規則層失敗或只得到弱標題時呼叫）；有記憶體快取、斷路器、併發上限。§6.10 的設計與其 `fallback` 模式一致，並多加了 schema 驗證與預算。
- `offset_detector.py`：以 TMDB 各集 `air_date`、播出間隔 > 6 個月切「虛擬季」，算出 season_offset 與 episode_offset。
- 明確限制：**不支援合集/批次**（FAQ：「AB 目前不支持解析合集」）、OVA 與電影 RSS 不支援、路徑必須是 `Title/Season X/`。這三點正是本系統 §6.6 要超越的地方。
- RSS 預設過濾 regex `720|\d+-\d+`（排除 720p 與區間合集）；建議一部作品只訂一個字幕組；繁簡二選一靠 Mikan 訂閱時選或 filter。§15 的 Rule 預設沿用「排除合集、字幕組白名單」。

**真實內容樣本（都取自現場列表，作為 benchmark v0 的種子）**

- 單集：`[Erai-raws] Yani Neko - 07 [1080p NF WEB-DL AVC AAC][MultiSub][A5D38B89]`；`[三明治摆烂组] … - 08 - [繁日内嵌][AVC 8bit 1080P]` 與同集的 `[简日内嵌]`、`[简繁日内封]` 三個 torrent（內嵌 vs 內封的實例）；`【楓葉字幕組】[寵物小精靈/ 寶可夢地平線烈空坐飛升][089][繁體][1080P][MP4]`；`【悠哈璃羽字幕社】[碧蓝航线 微速前进 S2_Azur Lane - Bisoku Zenshin! S2][x264 1080p][CHT]`；`[DHR Fansub][Little Busters!_リトルバスターズ!][04][JPN&BIG5][720P][AVC_Hi10P_AAC][MKV]`；`[LoliHouse] Re:Zero … - 81 v2 WebRip 1080p HEVC-10bit AAC`。
- 合集 / BD：`[7³ACG] 葬送的芙莉莲/Sousou no Frieren S01 | 01-28+SPx11 [简繁字幕] BDrip 1080p x265 OPUS 2.0`（28 集 + 11 個 SP）；`[7³ACG] 日常/Nichijou S01 | 01-26+SPx1 …`；`…★百姓贵族★29~40(完)★1920x1080★…★繁体中文`（`★` 分隔、`完` 標記）；`jibaketa TVB Honzuki no Gekokujou - S1 S2 S3 BD 1920x1080 x264 AACx2 SRT TVB CHT`（多季合一）；`Solo Leveling S01 + S02 BDRIP …`。
- 外掛字幕：`sub/スレイヤーズTRY第01話(DVD 640x480).gb.ass` / `.big5.ass`；`[11番小队][十二国记]…tc.ass`；Mikan 的「生肉/不明字幕」標記。
- 西方劇集：RARBG 季包 `Show/Subs/Episode 1/2_English.srt, 3_English.srt, 2_French.srt`（[renamer README](https://github.com/img02/Rarbg-Subtitle-Renamer)）；Sonarr Daily 型 `Some.Daily.Show.2021.03.04.1080p.HDTV.x264-GROUP`；`S01E01E02` 多集檔。
- 電影：`Oppenheimer (2023) [1080p] [BluRay] [5.1] [YTS.MX]/Oppenheimer.2023.1080p.BluRay.x264.AAC5.1-[YTS.MX].mp4` + `www.YTS.MX.jpg` + `YTSProxies.com.txt`；Jellyfin 官方多片段 `Movie Name-cd1.mkv`（parttype：cd/dvd/part/pt/disc/disk）。
- 韓劇：`Show.E01.YYMMDD.1080p…-NEXT` 無季編號（Sonarr 特別處理），`E01-16 COMPLETE (HDTV NEXT)` 全季字幕包。
- 未證實：VCB-Studio 類 BD 包內 `SPs/ CDs/ Scans/ Fonts/ Menu/` 的精確資料夾名只有社群轉述（[r/jellyfin](https://www.reddit.com/r/jellyfin/comments/pkrz4h/extra_folders_for_anime)），需抓一份真實檔案清單確認。

**Jellyfin 動漫命名的社群痛點**

- One Piece / Detective Conan 這類長篇：TVDB arc 順序 vs 絕對編號長期無解（[r/jellyfin](https://www.reddit.com/r/jellyfin/comments/1sny587/one_piece_tvdb_arc_order_vs_absolute_episode)、[tvdb-plugin#91](https://github.com/jellyfin/jellyfin-plugin-tvdb/issues/91)）。本系統只承諾「與 TMDB 一致」，不承諾符合任何一種社群偏好。
- Split-cour 被 Jellyfin 併成一季的抱怨很多（[r/jellyfin](https://www.reddit.com/r/jellyfin/comments/1r5sk02/any_way_to_have_anime_seasons_shown_in_parts_like)）；本系統不對抗 provider，只做正確對應。
- Sonarr FAQ 也承認 Bleach TYBW 這類新 arc 只有在編號與 TVDB 對上時才會自動匹配；絕對編號缺失時需等 TVDB 更新。

### 20.5 名稱衝突檢查

以 tavily basic 搜尋 GitHub / npm / PyPI / Docker Hub / App Store，非窮盡商標檢索。

| 名稱 | 評級 | 證據 |
| --- | --- | --- |
| Berth | 可用（已定案） | 精確比對（2026-09-07）：GitHub 無同領域專案，最接近的是 macOS SSH 客戶端 xinghelee/Berth（31★）；PyPI `berth` 是 2017 年停更的打包工具；npm `berth` 已標記 deprecated；Docker Hub 有 `berth/` 組織（舊 OpenStack 容器化專案，已停）。本系統以 `ghcr.io/<owner>/berth` 發佈，不需要這三個註冊名。 |
| Lading | 可用 | 未找到同名軟體專案 |
| Cleat | 可用 | 未找到同名軟體專案 |
| Longshore | 可用 | 僅人名 |
| Mooring | 可用 | 未找到同名軟體專案 |
| Keelhaul | 可用 | 僅文化典故 |
| Wharf | 輕微 | 數個小型不活躍專案（iver-wharf 等） |
| Gangway | 輕微 | VMware 已封存的 k8s OIDC 工具 |
| Drayage | 輕微 | 小型 Docker volume 遷移工具 |
| Dockhand | **衝突** | 現役自託管 Docker 管理工具，5.8k★，同為 homelab 領域（[Finsys/dockhand](https://github.com/Finsys/dockhand)） |
| Stow | **衝突** | GNU Stow |
| Quay | **衝突** | Red Hat Quay |
| Tally | **衝突** | TallyPrime 會計軟體與同名自託管記帳 App |
| Stevedore | **衝突** | OpenStack stevedore（PyPI plugin 載入套件） |

### 20.6 實作前必做的實驗【研究】

- ~~在 Windows Docker Desktop 的 NTFS bind mount 測硬鏈接~~ **已完成（2026-09-07，§20.7）**：可用。剩下：在 Linux 宿主與至少一台 NAS（Synology / QNAP / TrueNAS 其一）跑同一腳本，腳本保留在 `scripts/experiments/`。
- 對 qBittorrent 4.4 與 5.x 各跑一次 adapter 的參數相容測試（`paused`/`stopped`、`contentLayout`、`torrents/files.name` 的相對基準）。
- 建立 20 筆真實 torrent fixture（動漫 8、美劇/韓劇 8、電影 4）作為 benchmark v0。
- 用 dummy 檔案在 Jellyfin 10.10/10.11 實測 §7 的命名，逐項確認：
  - `<Title> (<Year>) - S01E01 - <Episode Title> [BD][1080p][CHT+JP][Group].mkv` 是否被正確辨識為 S01E01，方括號與 `+` 不會滲入劇名（對照 §20.1 的 anidb#11 與 #7855）。
  - 同一集兩個版本放同一季資料夾 → 未裝插件時的表現、裝 MergeVersions 後排程任務的名稱與合併結果、版本選單顯示的標籤。
  - 電影 ` - [BD][2160p][CHT+JP][Group]` 標籤是否被接受、版本排序如何。
  - `Season 00` 與 `extras/`（劇集層與季層）是否如文件所述。
  - 字幕 `….CHT.zh.ass` / `….CHS.zh.ass` 在播放器字幕選單的顯示文字。
- 抓一份 Mikan（我的訂閱、單作品 + 字幕組）與 Nyaa（搜尋）的實際 RSS，確認擴充欄位名（infoHash、大小、做種數、enclosure、發佈時間），寫成 adapter 的 fixture。
- qBittorrent 預置 `WebUI\ServerDomains=qbittorrent` 是否足以讓容器名呼叫通過 Host 檢查；Prowlarr `config/host` API 設定 Forms 帳密的欄位名。

### 20.7 開箱即用所需的 API 與 Windows Docker 事實

**Windows Docker Desktop 硬鏈接（本機實測，2026-09-07）**

- 環境：Windows 11、Docker Desktop 29.6.2（WSL2 後端）、NTFS 系統碟。把同一個 Windows 目錄 bind mount 為 `/data`，容器內對 `/data/torrent/complete/a.bin` 做 `ln` 到 `/data/library/b.bin`：**成功**，兩者 `dev=70`、inode 相同、`nlink=2`；掛載型態為 `9p (aname=drvfs)`。宿主端 `fsutil hardlink list` 列出兩個路徑，證明是真正的 NTFS 硬鏈接。
- 把 `torrent/` 與 `library/` 分開掛成兩個 bind mount：`ln: Cross-device link`，與 Linux 行為一致（單一掛載根的規則不變）。
- Docker named volume（WSL2 內 ext4）：成功。
- 結論：**Windows 使用者可以用一般的 bind mount**（`DATA_ROOT=D:\Berth\data`），不需要 named volume；exFAT 隨身碟不支援硬鏈接（[TRaSH](https://trash-guides.info/File-and-Folder-Structure/Hardlinks-and-Instant-Moves/)）。§4.4 的「不退回複製」維持。
- 其他查證：named volume 可從 `\\wsl.localhost\docker-desktop\mnt\docker-desktop-disk\data\docker\volumes\` 瀏覽；WSL2 VHD 預設上限 1 TB（[Microsoft](https://learn.microsoft.com/en-us/windows/wsl/disk-space)）；搬移 VHD 的設定介面有多起失效回報（[docker/for-win#13269](https://github.com/docker/for-win/issues/13269)）→ 這些都是不用 named volume 的理由。bind mount 經 9p 的吞吐比 volume 低（[Docker blog](https://www.docker.com/blog/file-sharing-with-docker-desktop)），下載寫入會慢一些，硬鏈接本身是 metadata 操作不受影響。

**Jellyfin 初始化與插件 API**（[OpenAPI](https://api.jellyfin.org/openapi/jellyfin-openapi-stable.json)、[FirstTimeSetupHandler.cs](https://github.com/jellyfin/jellyfin/blob/master/Jellyfin.Api/Auth/FirstTimeSetupPolicy/FirstTimeSetupHandler.cs)）

- `GET /System/Info/Public` 無需憑證，回 `StartupWizardCompleted`。
- `POST /Startup/Configuration`（`ServerName`、`UICulture`、`MetadataCountryCode`、`PreferredMetadataLanguage`）、`POST /Startup/User`（`Name`、`Password`）、`POST /Startup/RemoteAccess`（只有 `EnableRemoteAccess`，沒有 `EnableAutomaticPortMapping`）、`POST /Startup/Complete`，以及 **`GET/POST/DELETE /Library/VirtualFolders`**，都掛 `FirstTimeSetupOrElevated` 政策：精靈未完成時匿名可呼叫，完成後需管理員 token。
- `POST /Library/VirtualFolders?name=&collectionType=&paths=&refreshLibrary=`，`collectionType` 可為 `movies` / `tvshows` / `music` / `musicvideos` / `homevideos` / `boxsets` / `books` / `mixed`；body `{LibraryOptions}` 含 `PathInfos`、`EnableRealtimeMonitor`、`PreferredMetadataLanguage`、`MetadataCountryCode`、`TypeOptions[]`、`SeasonZeroDisplayName`、`EnableAutomaticSeriesGrouping`、`EnableEmbeddedTitles`、`AutomaticRefreshIntervalDays`。
- 為既有媒體庫加路徑：`POST /Library/VirtualFolders/Paths?refreshLibrary=`，body `MediaPathDto {Name, Path, PathInfo{Path}}`；移除為 `DELETE /Library/VirtualFolders/Paths?name=&path=`。路徑驗證：`POST /Environment/ValidatePath`，body `{ValidateWritable, Path, IsFile}`；另有 `GET /Environment/DirectoryContents?path=`。兩組都是 `FirstTimeSetupOrElevated`（本機對 OpenAPI 直接查核，2026-09-07）。
- `GET/POST /Repositories`（`{Name, Url, Enabled}`）、`POST /Packages/Installed/{name}?assemblyGuid=&version=&repositoryUrl=`、`POST /System/Restart`、`GET /ScheduledTasks`、`POST /ScheduledTasks/Running/{taskId}` 都需管理員（`RequiresElevation`）。
- MergeVersions：manifest `https://raw.githubusercontent.com/danieladov/JellyfinPluginManifest/master/manifest.json`，套件名 `Merge Versions`，GUID `f21bbed8-3a97-4d8b-88b2-48aaa65427cb`；排程任務 `Key` 為 `MergeMoviesTask` 與 `MergeEpisodesTask`（[RefreshLibraryTask.cs](https://github.com/danieladov/jellyfin-plugin-mergeversions/blob/master/Jellyfin.Plugin.MergeVersions/ScheduledTasks/RefreshLibraryTask.cs)），觸發時要用 `GET /ScheduledTasks` 回傳的 `Id`，不是 `Key`。

**Prowlarr**（[OpenAPI](https://raw.githubusercontent.com/Prowlarr/Prowlarr/develop/src/Prowlarr.Api.V1/openapi.json)、[supported-indexers](https://wiki.servarr.com/prowlarr/supported-indexers)、[environment-variables](https://wiki.servarr.com/prowlarr/environment-variables)）

- `GET /api/v1/indexer/schema`、`GET/POST /api/v1/indexer`、`POST /api/v1/indexer/test`；`GET /api/v1/search?query=&indexerIds=&categories=&type=` 回 `ReleaseResource`（`title`、`size`、`seeders`、`leechers`、`downloadUrl`、`magnetUrl`、`infoHash`、`indexer`、`categories`、`publishDate`、`guid`、`infoUrl`、`tmdbId` …）。Prowlarr 明言**不提供跨站聚合 Torznab**，單站 Torznab 為 `/{id}/api?t=search&apikey=`。
- API key 在 `config.xml` 的 `<ApiKey>`，可用 `PROWLARR__AUTH__APIKEY` 預設。
- 支援的公開索引站含：Nyaa.si、dmhy、AniDex、Anime Tosho、ACG.RIP、**Mikan**、1337x、YTS、EZTV、The Pirate Bay；TorrentGalaxy 目前不在清單。

**Jackett**（[repo](https://github.com/Jackett/Jackett)）

- API key 在 `ServerConfig.json` 的 `APIKey`；聚合 Torznab `/api/v2.0/indexers/all/results/torznab/api?t=search` 有文件（上限 1000 筆、站專屬分類不可用）；`GET/POST /api/v2.0/indexers/{id}/Config` 只是 UI 內部介面，無文件。有 `mikan.yml`、`dmhy.yml`、`nyaasi.yml`、`acgrip.yml` 定義。
- 結論維持 §19：套件預設 Prowlarr，Jackett 以 Torznab 端點接入。

**TMDB 專案級 key**

- Jellyseerr / Seerr 在 `server/api/themoviedb/index.ts` 寫死一把專案 key，使用者無處填自己的 key（[overseerr#3887](https://github.com/sct/overseerr/issues/3887)）；Jellyfin 團隊也曾討論專案級 key（[jellyfin#36](https://github.com/jellyfin/jellyfin/issues/36)）。TMDB 條款只區分商業與非商業，未明文規範「一 app 一 key」；本系統沿用此慣例並允許覆寫。

**qBittorrent 預置**（[sessionimpl.cpp](https://github.com/qbittorrent/qBittorrent/blob/master/src/base/bittorrent/sessionimpl.cpp)、[linuxserver/qbittorrent](https://docs.linuxserver.io/images/docker-qbittorrent)、[qbittorrent-nox](https://github.com/qbittorrent/docker-qbittorrent-nox)）

- 4.6.1 起首次啟動用隨機臨時密碼印在 log；已知密碼要預置 `WebUI\Password_PBKDF2`（PBKDF2-HMAC-SHA512、100000 次）。官方 image 沒有密碼環境變數，也沒有 `PUID` / `PGID`；linuxserver image 有，且設定檔在 `/config/qBittorrent/qBittorrent.conf`。
- `[Preferences]`：`WebUI\Port`、`WebUI\AuthSubnetWhitelistEnabled`、`WebUI\AuthSubnetWhitelist`、`WebUI\LocalHostAuth`、`WebUI\HostHeaderValidation`、`WebUI\CSRFProtection`；`[BitTorrent]`：`Session\DefaultSavePath`、`Session\TempPath`、`Session\TempPathEnabled`、`Session\DisableAutoTMMByDefault`（**預設 true，即 autoTMM 關閉**）、`Session\DisableAutoTMMTriggers\CategorySavePathChanged`、`Session\Port`。
- Web API `app/setPreferences` 對應鍵：`temp_path_enabled`、`temp_path`、`save_path`、`auto_tmm_enabled`、`category_changed_tmm_enabled`、`bypass_auth_subnet_whitelist(_enabled)`、`bypass_local_auth`、`web_ui_password`（只寫）。
  - 深連結 `#!/details?id=` 在 10.9+ 是否仍可用。
- 抽 10 部動漫比對 TMDB 季結構與字幕組編號，量化絕對編號換算的失敗率。
