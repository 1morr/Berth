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
- **媒體庫檢視**：像 Jellyfin 那樣瀏覽整個 Jellyfin 媒體庫（繼續觀看、下一集、已看 / 未看、依類型或年份排序、選季選集），疊上本系統的入庫狀態；同時是人工修正與未來 AI 功能的入口。播放跳到 Jellyfin（§12）。
- **可觀測性**：每個 torrent 有完整時間線（誰觸發、何時下載、怎麼解析、何時入庫、出了什麼錯）。

### 1.2 本系統不負責（交給外部服務）

| 職責 | 交給 | 說明 |
| --- | --- | --- |
| 播放、轉碼、觀看紀錄的儲存、刮削圖片與簡介 | Jellyfin | 本系統讀取 Jellyfin 的媒體庫、項目、圖片與每位使用者的觀看紀錄來呈現媒體庫（§12）；唯一寫回的是已看 / 未看標記。播放一律深連結到 Jellyfin |
| 下載協定、做種、限速、分享率、種子清理 | qBittorrent | 做種策略用 qBittorrent 的分類設定，本系統只處理「種子被移除後」的善後 |
| 索引站接入 | Prowlarr 或 Jackett（Torznab） | 只依賴 Torznab 協定。開箱即用套件預設打包 Prowlarr（§16.3），已有 Jackett 的使用者直接填 Torznab 端點 |
| Metadata | TMDB | 第一階段唯一的 provider，見 §10 |
| 同一集多版本的合併顯示 | Jellyfin（12 起原生合併；本系統只支援 12 以上） | 本系統只保證命名讓 Jellyfin 能合併；不裝 MergeVersions（§7.7、§19） |

刻意不做的事（第一階段）：品質檔案自動升級替換（Sonarr 的 quality profile upgrade）、內嵌播放器、多人審批、非影片媒體。AI 側面板與外部通知不在第一階段，排在 M5–M7（§14、§17）。見 §18。

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

名詞表在 repo 根目錄的 `CONTEXT.md`（單一來源，含每個詞的定義與應避免的同義詞）。實作、UI、文件與 API 一律使用那裡的詞。本文件後續章節出現的 Media、Library Route、Download Job、Import Plan、Ledger Entry、Review Queue、Unmatched、Extras、Issue、Event 等，定義以 `CONTEXT.md` 為準。

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
- Route 的 slug 與寫入目標建立之後不可改；刪除是明確、要二次確認的動作，被 Job 或帳本引用時拒絕，出路是停用（票 14）。

### 4.4 硬鏈接能力驗證【決定】

- 每個 Route 建立時與每次啟動時執行：在 `complete/<route-slug>` 建暫存檔 → 真的呼叫 `link()` 鏈接到目標路徑 → 比對 inode 與 device → 刪除。失敗即 Route 標記為不健康，拒絕送單。只比 `st_dev` 不夠（同一檔案系統掛兩次、btrfs 子卷、ZFS dataset、mergerfs 都會 `EXDEV`，§20.2），所以一定實際鏈接一次。
- 也檢查：目標路徑對本系統可寫、qBittorrent 回報的 save path 在本系統看得到、Jellyfin 以 `Environment/ValidatePath` 確認看得到探測檔、category 為 autoTMM 模式；temp path 未啟用只警告。
- **硬鏈接失敗不退回複製**（與 Sonarr 不同）：複製會讓刪除範圍與空間估算失真，違反「避免複製檔案」的需求。
- Docker 部署要求三個容器（qBittorrent、Jellyfin、本系統）以**相同容器路徑**掛載同一個宿主父目錄（TRaSH 的單一掛載慣例）；路徑字串可以是 `/data` 以外的任何值，套件預設 `/data`，既有服務沿用它們原本的路徑（§16.4）。第一階段不做 remote path mapping，設定精靈直接驗證「你看到的路徑 qBittorrent 與 Jellyfin 也看得到」。
- 已知限制要寫進 README：Docker Desktop（Windows/macOS）bind mount 的硬鏈接支援與 mergerfs / 跨 dataset 情境，見 §20 的查證結果。

### 4.5 檔名與目錄安全

- Media 資料夾名在**第一次真的通向磁碟那一刻**決定並寫入 DB——手動送單成功時，或建 RSS Rule 時（M1 票 04b）。兩者都有人在場、都要一次明確確認；不拖到入庫，那時是背景迴圈在跑，沒有人看著。在那之前它跟著 TMDB 的標題走，畫面上是「將會是」的預覽。凍結之後 TMDB 改名不自動改資料夾（避免 Jellyfin 重掃與帳本漂移）；提供「重新命名」的顯式動作。
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

1. **上下文**：Job 是從哪個 Media 詳情頁送出、送到哪一種媒體庫（電影 / 劇集）、RSS 規則綁定的 Media 與季 offset。這是最強的訊號，第一階段的絕大多數 Job 都有上下文。
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
| `extra` | NCOP/NCED/OP/ED（無集號）、PV、CM、Menu、Preview、Trailer、Making、Interview、`特典`、`映像特典`、`SPs/` 中非 SP 編號者，以及 §20.1 那一串 Jellyfin 認得的 extras 資料夾名（`Extras/`、`Bonus/`、`Featurettes/`、`Behind the Scenes/`、`Deleted Scenes/`、`Interviews/`、`Trailers/`…） | 進入 extras 路徑（§7.3） |
| `other` | nfo/txt/url 等 | 忽略 |

分類器要能被 mediainfo 修正：例如檔名像正片但時長 90 秒 → 降為 `extra`。

### 6.3 第二層：發佈名解析 → ReleaseInfo

對 torrent 名與每個檔名解析出結構化欄位（缺就留空，不猜）：

`title_candidates[]`、`season`（顯式）、`episode`/`episode_range`、`absolute_number`、`version`（v2/v3）、`group`、`source`（BD/WEB/DVD/HDTV/Remux）、`resolution`、`video_codec`、`bit_depth`、`audio`、`subtitle_langs[]`、`subtitle_kind`（hardsub/softsub/external/unknown）、`edition`（Remaster/Director's Cut/Uncut/…）、`year`、`air_date`（檔名寫的播出日，§6.4）、`season_hint_from_folder`、`special_kind`（SP/OVA/OAD/Movie/NC）。

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
   - 只有集號（動漫常見）→ TMDB 只有一季而且那一集存在 → 該季；否則視為 **絕對編號**，TMDB episode group（Absolute 類型）與各季累計集數兩種換算各產一個候選，換算過程寫入理由。**信心看證據，不看 Route**（2026-09-16，§19）：預設 medium，遇到任一條降到 low 送審核並附理由——(1) **集號 ≤ 第一個正規季的集數**：這個數字同時讀得成「第一季第 N 集」與「後面某季從 01 重數的第 N 集」，檔名分不出來（Erai-raws《死神》相剋譚 01–14 是後者）；§20.4 量過它擋下的多半其實是第一季，但「標題有認不出的多餘字」分不開兩者，2026-09-17 維持原形。(2) **檔名帶播出日，而換算出的那一集在 TMDB 上不是那一天播的**：日期是明說的，換算是推論的；沒有容忍範圍，因為日播的劇差一集就是差一天。以發佈時間推測「虛擬季」offset（AutoBangumi v3.2 的做法）**沒有做**：解析器拿不到發佈時間，而且它分不出上面那兩種讀法（plan §4.4、`docs/research/profile-effect.md` §4）。
   - 已知陷阱：TMDB 與 TVDB 近年都把 split-cour 動漫併成單季連續編號，而字幕組每個 cour 從 01 重數（§20.3）。RSS Rule 因此必須支援手動 offset；第二階段接入 Fribb/anime-lists 的 `season.tmdb` + `episode_offset.tmdb` 自動填 offset。
   - 韓劇常見 `E01` 無季 → 視為 Season 1（多數韓劇單季）並驗證集數。
4. **批次一致性**：同一 torrent 內所有影片以同一種模式解析成功、集號連續、數量與 TMDB 該季集數吻合 → 大幅加分；只有少數檔案解析失敗 → 那些檔案進 review，其餘照常入庫（不因為一顆 NCOP 卡住整季）。
5. **重複與衝突**：兩個檔案會被寫到**同一條目標路徑**（§7.1 / §7.2 的檔名已經含 tags）→ 標記衝突進 review，兩個都不自動入庫——誰對誰錯解析器答不出來，而蓋掉是不可逆的；與帳本既有版本同 tags → 標記 `duplicate`（§7.8）。比路徑而不是比（季, 集, tags）是因為那正是「會不會蓋掉對方」的定義，而**同一集不同 tags 的檔案本來就該並存**（§7.7）：简繁分軌、1080p 與 720p 同包都是常態（M1 票 07）。

### 6.5 信心與門檻【決定】

- 不用單一浮點數黑箱。每個 Plan item 帶 `confidence ∈ {high, medium, low}` 與 `reasons[]`。
- **high**：Media 由上下文或「標題 + 年份精確命中」決定；每個影片檔都有顯式季/集或資料夾提示；季/集都存在於 TMDB；無衝突；批次一致性通過。
- **medium**：Media 確定，但季/集靠推論（絕對編號換算、air_date offset、標題季名比對），或批次一致性只部分通過（少數檔案例外）。絕對編號換算要**沒有反證**才是 medium：集號超過第一季的集數，而且檔名若帶播出日就要與換算出的那一集相同（§6.4）。
- **low**：Media 不確定、有衝突、影片數量與 TMDB 集數明顯不符，或絕對編號換算有反證（§6.4 的兩條）。
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
2. 位於 `Subs/` `字幕/` **或語言資料夾**（`繁體/`、`简体/`）且檔名含集號 → 以集號對應影片。語言資料夾算同一種證據：它一樣說了「這一格底下的東西是側掛字幕」。**要有那個資料夾**——光有一個數字不算，一包裡任何帶數字的檔案都會對到某一集（M1 票 07）。同一集對到兩個以上的影片時不選：多版本並存時這一份字幕是誰旁邊的那一個，路徑沒有說。
3. 從檔名後綴或資料夾名判斷語言：`.tc` `.cht` `.zh-Hant` `繁體/` → zh-Hant；`.sc` `.chs` `.zh-Hans` `简体/` → zh-Hans；`.jp` `ja`；`JPSC` / `JPTC` → 雙語。真實語料另外寫 ISO 639-2 式的 `.Cht` `.Chs` `.Jpn` `.Eng`（`tv/gto-2026-magicstar`），一併認得。三者都沒說時才看檔名裡的詞典；**torrent 名不算**——`附官方日英简繁中字幕` 說的是這一包有四種字幕，不是這一個檔案有四種（M1 票 07 實測）。
4. 對不到影片的字幕 → Unmatched。影片自己沒有入庫（Unmatched / review）時字幕跟著它走，人在佇列裡看到的才是一對。

輸出：以 Jellyfin sidecar 慣例命名 `<影片檔名主幹>.<標題>.<語言碼>.ass`。Jellyfin 無法用語言碼區分繁簡（§20.1），所以語言碼一律 `zh`，繁簡放在自由文字標題欄位，用 §6.8 的 token：`….CHT.zh.ass`、`….CHS.zh.ass`、日文 `….ja.ass`、英文 `….en.ass`、預設軌加 `.default`（旗標排在語言碼**之前**：`….CHT.default.zh.ass`，§20.6 實測。M1 沒有任何東西決定得了哪一軌是預設——沒有字幕語言偏好設定——所以那一段先不產生，plan §5）。標題欄位在播放器字幕選單的顯示方式列入 §20.6 實測。字型不入庫。

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

- repo 內維護一組 fixture：每筆含 torrent 名、檔案清單（路徑、大小）、上下文（Media id，RSS 的季號提示與 offset）、期望輸出（每檔的分類、季、集、tags 或 unmatched）。
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
  <Title> (<Year>) [tmdbid-<id>] - [BD][2160p][CHT+JP][Group].mkv
  <Title> (<Year>) [tmdbid-<id>] - [WEB][1080p][CHS][Group2].mkv
```

同資料夾內以 ` - <版本標籤>` 區分多版本，這是 Jellyfin 原生支援的多版本方式，不需插件；檔名在 ` - ` 之前必須與資料夾名**完全一致，包含 `[tmdbid-<id>]`**。2026-09-07 實測（§20.6）：檔名少了 `[tmdbid-<id>]` 就不是多版本，而是兩部獨立的電影；本節原本的範例是錯的，已更正。標籤內含方括號與 `+` 沒有問題，版本選單顯示的就是 `[BD][2160p][CHT+JP][Group]`。Jellyfin 對結尾為 `p`/`i` 的標籤依解析度降冪排序、其他字母排序（§20.1，已實測）。

### 7.3 Extras【決定，取代原「unmatch 資料夾」的一部分】

NCOP/NCED、PV、CM、Menu、預告、花絮等**可辨識**的非正片內容，硬鏈接到 Jellyfin 支援的 extras 資料夾（名稱與位置依 §20 查證），讓 Jellyfin 把它們顯示為該作品的額外內容，而不是污染集列表。

### 7.4 Unmatched【決定，取代原「unmatch 資料夾」】

真正對不到 metadata 的影片與字幕**不入庫**，留在 `complete` 原位；本系統在 Media 頁與 Job 頁列出它們，提供「指派到某季某集」「標記為 extra」「忽略」三種動作。理由：

- Jellyfin 會嘗試把媒體庫內任何影片解析成集數，`unmatch/` 資料夾裡的 `[Group] Title - 25.mkv` 很可能被當成第 25 集，反而製造錯誤。
- 把不確定的東西鏈接進去再要求使用者清理，比不鏈接更難維護。
- 原需求「使用者能在媒體庫頁面重新匹配」完全保留，只是資料來源改成 complete 目錄 + 帳本。

### 7.5 標題語言【決定】

`Title` = TMDB 英文 `name`；英文缺或與 `original_name` 相同時用 `original_name`。資料夾名決定後凍結（§4.5）。

**畫面上的顯示用標題、簡介與海報跟著 UI 語言走**（2026-09-17 決定，§19；海報由 M1.5 票 11 補上——TMDB 的海報也分語言，中文標題配英文海報是兩個來源拼出來的東西）：`zh-Hant` 取 TMDB `zh-TW` 那一輪，`en` 取 `en-US` 那一輪。這一條只管畫面；檔名、資料夾名與季名比對用的字串不跟 UI 走。**媒體庫牆上已在 Jellyfin 裡的作品例外**，顯示 Jellyfin 的名稱（M1.5 拆票時決定，§19）：牆上多數作品不是 Berth 經手的，Berth 手上沒有它們的 TMDB 快照，而 Jellyfin 的名稱與使用者在 Jellyfin 裡看到的一致；還沒進 Jellyfin 的卡片照樣跟著 UI 語言。

### 7.6 Specials / OVA / OAD / SP

- 能對到 TMDB season 0 某一集 → `Season 00/… - S00Exx`。
- 對不到但可辨識為 extra（NC/PV/CM）→ extras。
- 對不到且像正片（`SP1`、`OVA 2`、`特別篇`）→ Unmatched，等人工指派；這類是 review 的大宗，UI 要讓「把這檔指派為 S00E03」只需兩次點擊。

### 7.7 多版本並存

- 同一集不同 tags 的檔案並存在同一季資料夾。**Jellyfin 12.0 起原生合併**：同一個季資料夾裡解析出同一個 `S/E` 的檔案就是同一集的版本，本系統現行命名不裝插件就合併成 1 個 Episode、多個 MediaSource（2026-09-15 對 12.0.0 / 12.1.0 實測，§20.9）。**本系統只支援 Jellyfin 12 以上，不裝 MergeVersions**（§19）：10.10 / 10.11 原生不可靠（實測會變成兩個重複的 Episode 條目，§20.6），得靠這個插件；而它在 12.x 上對本系統的樹是空跑，卻要多一次 Jellyfin 重啟、依賴 GitHub 下載，還會跨媒體庫誤併。
- 版本標籤：**電影**是 tags 字串本身（` - ` 之後的部分）。**劇集**是「去掉各版本檔名的共同前綴」剩下的部分（有集名時是 `集名 + tags`，沒有集名時是 `S01E01 + tags`；算法跟標點有關，12.0 與 12.1 也不同，§20.9）。所以 UI 不自己重算劇集的版本名，Jellyfin 收錄之後讀它回的 `MediaSources[].Name`（M1 票 14b）。tags 詞彙仍要短且可讀，但 UI 文案不能說「使用者看到的就是 tags」。版本先後依解析度降冪，再依檔名。
- 命名唯一必須保證的事：同一集所有版本的檔名在 `S01E01` 之前的部分完全相同，且互相只差 tags。

### 7.8 重複版本

新 Plan item 與帳本既有 Entry 的（Media, 季, 集, tags）完全相同 → `duplicate`。自動模式預設 **跳過並記事件**；review 提供「取代舊版」「保留兩者（加 `[v2]` 類 tag 者本來就不同）」「跳過」。**保留兩者時新的那一份檔名多一個序號標籤**（`[2]`、`[3]`…，存在 Tags 的 `edition`，2026-09-23 使用者拍板）：Tags 完全相同的兩份檔名一模一樣，不改名就放不進同一個資料夾；Jellyfin 12 把它們當同一集的兩個版本。判斷在**規劃時**（比帳本，M2 票 08），不在入庫時。

**多集檔與同起始集的單集**（2026-09-15 使用者拍板）：新 Plan item 的正片與同一季的帳本既有 Entry、或同一份 Plan 的其他正片**起始集相同、結束集不同**（`S01E03-E04` 對 `S01E03`）→ 送 review，不自動入庫，理由要說出後果。與帳本撞的那一種 M2 票 08 起走上面那一條（略過那一列、Review Queue 上一列 `duplicate`，同一包其餘照常入庫）；同一包之內互撞的照舊整份送 review。Jellyfin 12 的版本分組鍵只有季號與集號，會把它們併成同一集的兩個版本，後面那一集從集列表消失（§20.9）。規則不分 Jellyfin 版本：同一集有兩份涵蓋範圍不同的正片，本來就該由人決定留哪一份。

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
- `routes`：Jellyfin library id、目標路徑、category、啟用狀態、健康狀態。
- `media`：tmdb id、類型、標題（英文/原文）、年份、資料夾名（送單那一刻凍結，§4.5）、TMDB 快取（含季集結構、更新時間）。「追蹤過」不是欄位而是從 Job / 帳本 / Rule 推導。
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
| `missing_files` | 管線：qBittorrent 回報完成但 Berth 在 complete 找不到（或 `stat` 不到）那些檔案 | 重新 recheck / 承認遺失 |
| `client_error` | 管線：torrent 在 qBittorrent 進入 error 狀態 | 重試 / 忽略 |
| `client_removed` | 管線：Job 還沒完成，torrent 已不在 qBittorrent | 重新送單 / 承認移除 |
| `jellyfin_item_unresolved` | 管線：入庫後六次反查都沒在 Jellyfin 找到那個檔案 | 重新反查 / 重新掃描媒體庫 |
| `library_uses_tvdb` | 健康檢查：一條 Route 的 Jellyfin 媒體庫掛著 TVDB 的 metadata fetcher（§16.4 的警告） | 只列出；在 Jellyfin 拿掉之後系統自己收掉 |
| `low_disk_space` | 健康檢查：incomplete 或 complete 所在的檔案系統剩下的空間低於門檻（設定裡，預設 10 GB） | 只列出；空間回來之後系統自己收掉 |

中間四種是管線自己發現的（M1 以 `issue_detected` 事件記著，M2 起與對帳的七種共用 `issues` 表與同一個封閉集合，plan §2.4，2026-09-22 定）；最後兩種是 `health_checker` 每 5 分鐘量出來的（M2 票 09c，使用者拍板由健康檢查偵測而不是對帳），十三種共用一個集合。`ledger.status` 的 `target_missing` / `source_missing` / `inode_mismatch` 是帳本那一列的現況，Issue 是「要有人決定」的那一件——同一件事的兩個角度，resolve 之後帳本那一欄跟著改。

**認領類三顆（M2 票 10 做完）**：都走既有的入庫路線、都不刪東西。「重新入庫」與「認領」**由管理員在列上選作品**（2026-09-23 使用者拍板：沒有作品的 Job 規劃出來只會整份停在 review 而且核准不了）；孤兒目錄建一筆 `trigger = reimport` 的 Job 停在 `completed`，無主 torrent 建一筆停在 `submitted`（Route 由它的 category 決定，只掛 `berth` tag 的說不出要入庫到哪裡，拒絕）。「認領進帳本」是單一檔案的 `berth rebuild-ledger`：inode 反查 complete、路徑照命名模板反解，配不上的拒絕、那一件開著。

2026-09-23（M2 票 09 開工時使用者拍板）：「認領」類的三顆——`orphan_complete` 的重新入庫、`unknown_torrent` 的認領、`unmanaged_library_file` 的認領進帳本——在**票 10** 與 `reimport` / `rebuild-ledger` 一起做（同一組原語，先做一份會變成兩條入庫路徑）；管線那三種（`missing_files` / `client_error` / `client_removed`）的動作在**票 09c** 做完：重新校驗與重試讓 Job 回到檔案清單到手之後那一站（還沒有清單的回 `submitted`），由 poller 照常往前推；重新送單照存下來的下載連結再加一次，**先問過 Route、連結與 qBittorrent 才動 Job**；兩顆「承認」走刪除範圍四個旗標全不勾（Job 進 `removed`，磁碟與 qBittorrent 都不動，使用者 2026-09-23 拍板）。它們只在 Job 還停在那個壞掉的狀態時按得了。

健康檢查那兩種**沒有 Berth 按得了的修法**，所以條件解除時系統自己收掉（`resolved_by = system`）；問不到 Jellyfin、量不到那個目錄不算解除。它們的**「忽略」在條件持續期間有效**（2026-09-23 使用者拍板）：其餘幾種忽略之後下一次偵測就開新的一筆，對 5 分鐘量一次的東西那等於忽略無效，而故意掛 TVDB 的使用者會被一直問。條件解除過一次、之後再發生才重開。會刪東西的按鈕（連 complete 一起刪、刪除孤兒目錄、以硬鏈接取代）按下去之前再確認一次世界：偵測在早上，按下去在下午。`job_without_files` 的判定有兩個例外（票 09）：那一份 Plan 本來就沒有要鏈的檔案（全是重複的那一包自動落地，§7.8）不算；使用者對那一筆按過「承認刪除並清帳本」的不算——帳本是他自己清的，再問他要不要重新規劃等於讓剛決定過的事自己回來。

### 9.2 刪除範圍【決定】

刪除是一組可組合的旗標，UI 用勾選框呈現（沿用 Sonarr 的「同時刪除檔案」慣例，但拆得更細）：

- 移除 library 硬鏈接（Jellyfin 會在下次掃描少掉它）
- 從 qBittorrent 移除 torrent（不刪檔）
- 刪除 complete 檔案（要求先移除 torrent，否則拒絕）
- 清除帳本與 Job 紀錄（否則保留為歷史）

顯示「預估可釋放空間」：只有當來源與所有鏈接都刪掉時才真的釋放，UI 要說清楚。

實作（M2 票 04，`services/deletion.py`）：順序是**移除 torrent → 移除鏈接 → 刪來源 → 清紀錄**，移除 torrent 排第一是因為它是唯一可能失敗的一步，問不到那一台時整次刪除不做而不是刪到一半才發現；`unlink` / `delete_files` 之後帳本那幾列留著當歷史（清帳本是另一個旗標），只把 `status` 改成 `target_missing` / `source_missing`；空掉的目錄跟著收（留著 `Show/Season 01/` 兩層空目錄的話 Jellyfin 的牆上那部作品還在）；刪除與鏈接**同一道路徑守衛**（plan §8.6），帳本被改壞、指到媒體庫外面的那一條不刪而其餘照樣做完。

2026-09-22 定：四個旗標**預設全不勾**——Sonarr 的對話框預設勾「同時刪除檔案」，但這裡的刪除以 Job 為單位而不是作品，預設刪檔會誤刪還在做種的東西；空間估算**同步 `stat` 每一個來源與目標**（慢而準，畫面上說「正在算」），不用來源大小去猜；對話框住在 Job 詳情頁與 Media 詳情的版本清單，同一個元件；對帳發現的 `library_link_missing` 選「連 complete 一起刪」時走同一組旗標。

### 9.3 重新入庫

Import Source 可以是「complete 內任一資料夾」，不要求 torrent 仍存在。流程與正常入庫相同（planning → review/importing），帳本以來源相對路徑冪等，所以「刪了 library、保留 complete、再重新入庫」是一鍵動作。

實作（M2 票 10）：兩個入口——Job 頁的 `POST /jobs/{hash}/reimport`（那一筆的 complete 目錄），與 `orphan_complete` 的「重新入庫」（沒有 Job 的目錄，建一筆 `trigger = reimport` 的 Job）。**Import Source 是磁碟上那一包**：`job_files` 照資料夾裡現在的樣子重寫，少了一集就少規劃一集，而不是照 torrent 的清單在 importer 那一步失敗。帳本冪等的鍵是「Job + 來源相對路徑」，所以 TMDB 在兩次之間改了集名時，那一列換到新路徑、舊的鏈接被收掉，Jellyfin 不會多一個同一集的版本。

帳本本身沒了的時候（還原舊備份、手動清掉）是 `berth rebuild-ledger`：媒體庫裡帳本不認得的檔案，complete 裡有同一個 inode 的來源、而且路徑照命名模板讀得回季集與 Tags 才長回一列；**配不上的一律變成 `unmanaged_library_file`，不猜**（plan §11.3 決定 9）。

### 9.4 重新匹配（Rematch）

Media 頁對某個檔案（已入庫或 Unmatched）選「改指派為 SxxEyy / 標記 extra / 忽略」：建立新硬鏈接 → 刪舊鏈接 → 更新帳本 → 觸發掃描。一律經過 Plan，讓修正也有紀錄。

### 9.5 Jellyfin 端的刪除

使用者在 Jellyfin 刪媒體只會刪 library 檔案，Reconciler 會發現 `library_link_missing`。未來可接 Jellyfin Webhook 插件即時偵測，第一階段靠排程。

---

## 10. Metadata Provider 策略【決定】

**第一階段只用 TMDB**，同時負責探索與季集結構。理由：

- Jellyfin 內建的劇集 provider 預設是 TMDB，本系統的季/集編號必須與 Jellyfin 顯示一致，否則檔名 `S02E01` 在 Jellyfin 會對到別集；同源最安全。
- Seerr 長期只用 TMDB，媒體牆體驗已被驗證（近期才加入實驗性 TVDB，目的只是配合 Sonarr）。
- TVDB 在動漫 split-cour 上與 TMDB 採**同樣的合併政策**（§20.3），換 provider 不解決主要的編號錯誤來源；引入第二個 provider 的代價是每個 Media 多一層 ID 對應與衝突處理，第一階段不值得。（原本列的第三個理由「TVDB 要每位使用者付費並輸入 PIN」已於 2026-09-07 重查推翻，見 §20.3。）

**TVDB 作為動漫的季集來源已於 2026-09-09 定案：不採用【決定】。** M1 票 01 對 10 部動漫、7,833 筆真實字幕組釋出量化了三種來源的換算失敗率（[`docs/research/anime-episode-source.md`](research/anime-episode-source.md)）：TMDB 季集 **8.0%**、TVDB default(aired) **7.6%**、TVDB absolute **7.6%**。差距 0.4 個百分點，且方向兩邊都有（TVDB 在《航海王》贏 4.4 點、在《SPY×FAMILY》輸 3.9 點）。換不到的東西不值得付三個代價：**引入第二個 provider** —— 每個 Media 多一組 `tvdb_id` 與對不上時的處理、快照抓兩次快取兩份、精靈與設定頁多一把使用者自備的 key；**Jellyfin 那一端必須跟著改** —— 媒體庫要改用 TVDB 插件刮，編號才對得上，而這是 Berth 保證不了的使用者設定；**走 absolute 還要再多一步** —— Jellyfin 本體沒有絕對編號的概念，得對每一部劇寫 `Series.DisplayOrder`（§20.3）。因此 `media` 表不加 `tvdb_id` / `episode_source`，不做 TVDB adapter。

**授權不在上面那三條裡（2026-09-09 更正）。** 先前一版把它算成主要代價是錯的：§20.3 早已查證 v4 key 免費且自助申請、不帶 PIN 可讀，ToS 擋的是「內建一把 key 發給所有使用者」而不是「使用者自己申請一把填進 Berth」。後者與 TMDB 的做法對稱，兩個 provider 之間不構成差異。

已知弱點與對策（**對策已依實測改寫**）：

- **主要弱點不是編號來源，是檔名裡沒有季號。** 三種來源同時失敗的有 573 筆，佔 TMDB 全部失敗的 91%（573/627）。主要成因是「柱訓練篇」「最終季」「死滅迴游」這類**篇章名帶語意但沒有數字**，換 provider 一集都救不到；唯一「有季號還錯」的一類是「第三季 第二部分 / Season 3 Part.2」——缺的是 cour 偏移不是季號。對策：解析器用 `MediaSnapshot` 已有的各季 `name` 與 alternative titles 比對篇章名、把「最終季」對到最後一季、把「第二部分 / Part.2」當成 cour 偏移（plan §4.4、M1 票 06）。
- 絕對編號換算只影響 16% 的釋出，TMDB 在那一段錯 4.4%（TMDB 沒有 absolute 欄位，只能數播出序位）→ 維持絕對編號換算 + review，但它不是主要槓桿。
- 字幕組的編號習慣有四種且同一部作品會並存（每 cour 從 01、官方編號、正篇序位、季內連號），任何「假設編號一致」的設計都會踩到（§20.3）。
- 若使用者在 Jellyfin 該媒體庫改用 TVDB 插件 → 本系統讀取 `LibraryOptions` 偵測並警告「編號來源不一致」。
- 第二階段【研究】接入 anime-lists 類的 AniList/MAL ↔ TMDB 對應。

**什麼情況該回頭重看這個決定。** 本節寫的是「第一階段只用 TMDB」，不是永久結論。下面四條任一成立就重跑 `scripts/experiments/anime_episode_source.py` 並重新評估，其餘時候不要再開這個題目：

1. **Jellyfin 換掉預設的劇集 provider，或社群普遍改用 TVDB 插件刮。** 上面第一條理由（同源最安全）是整個決定的承重牆，它一旦反向，結論就跟著反向。
2. **M1 票 06 的「篇章名 → 季號」做完之後，benchmark 的季集失敗仍集中在 provider 結構差異上。** 現在那一塊只剩 78 筆（只有 TMDB 錯 54、只有 TVDB 錯 24），佔樣本 1%；主因（573 筆）是解析器缺口。若補完解析器後比例翻轉，代價與收益就要重算。
3. **美劇 / 韓劇出現同類問題。** 這次只量了 10 部動漫 —— 動漫是最難的形態（split-cour、字幕組四種編號習慣並存、劇場版插號），結論往簡單形態推是合理的，但**沒有量過**。M1 的 benchmark 語料含美劇 / 韓劇 8 筆（§20.4），那裡是第一個會看見的地方。
4. ~~**TVDB 的授權模式改變。**~~ **這一條 2026-09-09 撤銷** —— 免費自助 key 現在就有，使用者自備 key 本來就可行，授權從一開始就不是差異（見上面的更正）。留著這行是為了不讓它被重新加回來。

---

## 11. 帳號與權限【決定】

沿用 Seerr 做法：以 Jellyfin 帳號登入本系統。

- 初次設定：輸入 Jellyfin 位址 → 以 Jellyfin **管理員**帳號登入 → 該帳號成為本系統 admin，並產生本系統用的 Jellyfin API key。
- 其他 Jellyfin 使用者可登入，預設角色 `user`（可探索、可送單到指定 Route、可看自己的 Job）；admin 可改 Route、刪除、審核。**2026-09-22 明確**（M2 拆票前）：Review Queue、Issue 的動作、rematch、刪除範圍、手動對帳一律只有 admin（plan §6 的門禁與 `api/gate.py` 同輪補上）；`user` 送單的 Job 停在 review 時只能等，畫面上說「等管理員審核」。
- 不自建密碼系統；本系統的 `users` 表只存 Jellyfin user id 與偏好。
- 未來的審批、配額、通知都掛在這個角色模型上。
- 取捨：Jellyfin 掛掉時無法登入。可接受，Seerr 同樣如此。

---

## 12. 播放【決定】

第一階段 **深連結到 Jellyfin** 該項目的詳情頁（帳本存有 Jellyfin item id；劇集連 Series，電影連 Movie）。格式原本沿用 Seerr 來源碼的 `{externalUrl}/web/index.html#!/details?id={itemId}&serverId={serverId}`；**實作用 `{對外網址}/web/#/details?id={itemId}`**——客戶端自己的 `#/` 形式（M0 票 04 實測），不帶 `serverId`（2026-09-15 對 12.0.0 實測開到同一頁，§20.1）。主機是選填的「Jellyfin 對外網址」，沒填時推導（票 13，Seerr 的 `externalHostname` 慣例）。Jellyfin 沒有「直接開始播放」的穩定 URL。不做內嵌播放器：播放器牽涉轉碼協商、字幕（動漫的 ASS 與字型）、播放進度回報，是最大工作量且與本系統核心無關；而且多數人在電視與手機上用 Jellyfin 的 app 看，網頁播放器取代不了它們。

**瀏覽由 Berth 取代**（2026-09-15 使用者拍板，推翻原本的「媒體庫頁的價值在『狀態與修正』，不在『取代 Jellyfin 播放』」；M1.5）：媒體庫頁與 Media 詳情像 Jellyfin 那樣呈現整個 Jellyfin 媒體庫——繼續觀看、下一集、已看 / 未看（可切換，寫回 Jellyfin 該使用者的紀錄）、依類型或年份排序、Jellyfin 的圖、選季選集——並疊上本系統的入庫狀態。按下播放或某一集時才深連結到 Jellyfin 的那一項（Jellyfin 沒有直接開始播放的網址，使用者在那一集的詳細頁再按一次播放）。可行性已查（§20.8）：伺服器 API key 可以代讀代寫每位使用者的觀看資料，但 Jellyfin 這時只套用一部分媒體庫權限，**媒體庫存取權限要由 Berth 自己擋**——`userId` 一律取自 session，媒體庫對 Jellyfin 的 `UserViews` 允許清單驗證。

---

## 13. 頁面清單

| 頁面 | 目的 | 關鍵內容 |
| --- | --- | --- |
| 設定精靈 | 首次啟動 | 建立管理員 → 偵測套件內的 Jellyfin / qBittorrent / Prowlarr 並一鍵設定，或連接既有服務 → 路徑 → 建立 Route → 健康檢查（§16.3） |
| 探索（首頁 `/`） | 找東西、接著看 | 上方是這位使用者的繼續觀看與下一集（M1.5，沒有內容就不出現，點下去深連結到 Jellyfin 的那一集）；趨勢 / 熱門 / 搜尋；卡片顯示狀態（未追蹤 / 部分 / 完整 / 下載中，**四種都由 Job 與帳本推導**，所以卡片上的狀態要等 M1 票 09 才畫得出來） |
| Media 詳情 | 決策中心與觀看入口 | 探索與媒體庫點進的是**同一頁**（2026-09-15 使用者拍板，不另建媒體庫詳情頁）。作品已在 Jellyfin 裡時最上面是**觀看區**（M1.5）：繼續看 / 下一集的深連結、選季選集、各集劇照與已看標記。其下：TMDB 資訊、各季各集入庫狀態、**搜尋 torrent**（結果表：大小、做種、來源、解析出的 tags、預估匹配；作品已入庫時收合）、選 Route 送單、RSS 訂閱、檔案清單（含 Unmatched 與 rematch）、版本並存清單 |
| 媒體庫 | 瀏覽與修正 | 像 Jellyfin 那樣瀏覽**整個 Jellyfin 媒體庫**（M1.5，不只 Berth 經手的）：一個 Jellyfin 媒體庫一頁、只列這位使用者在 Jellyfin 看得到的；繼續觀看、下一集、卡片牆附已看 / 未看、依類型或年份排序；Berth 經手的作品疊上入庫狀態，還沒進 Jellyfin 的（下載中、待審）也在牆上；篩選：有 Issue / 有 Unmatched / 有待審。M1（票 13）是依 Route 分頁、只列 Berth 經手的作品＋深連結 |
| 下載與活動 | 全域狀態 | 所有 Job 列表：狀態、進度、Route、trigger；點入 Job 頁 |
| Job 詳情 | 可觀測性 | **獨立頁 `/jobs/:hash`**（M2，2026-09-22 定；M1 只有 `/jobs` 的就地展開區）：**時間線**（§5.2）、檔案清單與各檔決策、Plan 歷史、動作（重新解析、重新入庫、刪除範圍） |
| 審核佇列 | 人工介入 | 低信心 Plan（逐檔可改）、已入庫待確認（medium 自動入庫的 audit 清單，可一鍵撤銷）、Unmatched、重複版本、Issue；批次核准。**一列一件事的清單，不是牆**（2026-09-22 定，M1.5 的 critique：篩出來常常只有一兩件，卡片牆說不出「有幾件事在等你」）；只有 admin 進得來 |
| RSS | 自動化 | 訂閱清單、規則清單、最近命中與未匹配項目、一次性 RSS 連結、規則試跑 |
| 健康與問題 | 維運 | 服務連線、Route 硬鏈接檢查、Reconciler 結果、磁碟空間 |
| 設定 | 管理 | 服務、路徑、Route、命名詞彙、解析與 AI 開關與預算、使用者角色 |

---

## 14. AI 與通知【決定】

**第一階段（M0–M4）只做便宜的事**，形狀從一開始就定：

- **API-first**：UI 做得到的每個動作都是一個有名字、有 schema、冪等的服務命令（`search_torrents`、`add_download`、`generate_plan`、`apply_plan`、`rematch_file`、`delete_job`、`reconcile`、`issues.resolve`…）。未來的 AI 工具與 MCP server 只是包裝這些命令。
- **資料可讀**：Plan、Event、Issue 都是結構化 JSON，AI 不需要爬 UI。
- **M4 的 AI 是 fallback 解析器**（§6.10）：只在規則層信心 low 時被叫、只產出 Plan、一律進 review。它不是 agent。
- **M2–M4 不做**：agent 迴圈、側面板、工具權限模型。

**之後怎麼長**（2026-09-22 使用者拍板，plan §11.6–§11.8）。owner 要的四件事——(1) 開關打開後 Review Queue 交給 AI、(2) 側面板讓 AI 替使用者操作、需要人看的以卡片確認或拒絕、(3) 外部通知（某一集正在下載、在 Jellyfin 可見了）、(4) 像 OpenClaw 那樣在聊天軟體裡與 AI 對話——拆成三個里程碑，因為 (3) 不是 AI，而 (1)(2)(4) 是**同一個 agent 核心的三個介面**：

| 里程碑 | 內容 | 為什麼在這個位置 |
| --- | --- | --- |
| **M5 通知** | `events` 的訂閱者 + channel adapter（Telegram / Discord 擇一先做）+ 每人的訂閱設定 | 便宜；M7 要靠它的管道與身分；「最新一集正在下載」要有 M3 的 RSS 才有意義 |
| **M6 AI 助理** | agent 核心（對話 → 挑命令 → **提案** → 人確認 → 執行）、`proposals` 表、Review Queue 的 AI 模式、側面板、工具權限模型 | M2 的命令面是它的工具集，M4 的 provider 與預算是它的地基 |
| **M7 外部對話** | M5 的管道接上 M6 的核心：同一個 bot 既推通知也收訊息，提案卡是帶按鈕的訊息，身分用個人 API token（§16.2） | 只多一個介面，核心與提案共用 |

**提案（Proposal）是核心的形狀**：AI 永遠只能提出「叫哪個命令、帶什麼參數、為什麼」，改狀態的命令要人確認才執行（讀取類不用；使用者可在設定頁對某一類開自動）。這與 §6.10 的「AI 只能產出 Plan，不能動檔案」是同一條原則放大到所有命令。

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
- README 明列：硬鏈接前提（單一掛載、不可 exFAT、不可跨 btrfs 子卷 / ZFS dataset / mergerfs branch）、支援 Linux 宿主與 Windows Docker Desktop（NTFS）、qBittorrent 版本下限與必要設定（temp path、category autoTMM）、Jellyfin 版本下限 12.0，以及從 10.x 升級的注意事項（先完整備份、移除第三方插件、升級後完整掃描、不能降級，§20.9）、**使用者要自備 TMDB API key 與取得步驟**（§16.3）、TMDB 的歸屬聲明與 logo。

### 16.2 跨切面需求

- **外部呼叫**：統一逾時、重試與退避；服務不可達時 Job 停在當前狀態並記事件，不判定失敗；健康檢查頁顯示每個服務最後成功時間。
- **資料庫**：SQLite WAL；schema migration 從 M0 就用（Alembic）；備份就是複製 `/config`；提供「從磁碟 inode 掃描重建帳本」的災難復原指令（§7.9）。
- **秘密**：API key 存在 DB，靠檔案權限保護，不做應用層加密（與 Seerr 相同），README 註明。
- **日誌**：結構化，每行帶 job id；Event 是使用者可見層，log 是維運層，兩者不互相取代。
- **安全**：所有 API 需登入；未來 AI / MCP 用個人 API token；容器非 root；不開 CORS 萬用字元。
- **測試**：解析 benchmark（純函式，CI 必跑）；管線整合測試用假的 qBittorrent / Jellyfin / TMDB adapter；docker compose 端到端至少覆蓋 M1 驗收流程。
- **i18n**：zh-Hant 與 en 並列，字串集中管理、一律走 key；檔名 token 與 log 一律英文。2026-09-07 改：原本是「UI 繁體中文優先，不做英文版直到有需求」，因確定面向英語自架者而推翻，見 `PRODUCT.md` 的 `## Users`。
- **授權**：MIT（與 Seerr、AutoBangumi 相同）。TMDB 條款限非商業使用，README 註明。

### 16.3 開箱即用（一鍵設定）【決定】

目標：新手使用者下載 compose 範本、`docker compose up`、開瀏覽器，之後所有設定都在 Berth 的精靈裡完成，不需要分別打開 qBittorrent、Jellyfin、Prowlarr 的介面。做法是「預置設定檔 + Berth 透過各服務 API 代為設定」，兩者都冪等，可重複按。

**唯一要離開 Berth 的一步是 TMDB 憑證**【決定 2026-09-09】：使用者得先去 themoviedb.org 註冊、在「設定 → API」申請一把 key，貼進精靈第 6 步。Berth **不內建任何 provider 的 API key** —— 不替所有使用者背一把共用憑證（原本沿用 Seerr 的內建 key，§20.7）。代價是「開箱即用」缺了這一角，這是知情且接受的；相對地兩個 metadata provider（TMDB 與 §10 評估過的 TVDB）在「使用者自備 key」這件事上是對稱的。

| 服務 | 預置（compose 範本） | Berth 一鍵設定（API） | 使用者仍需自己做 |
| --- | --- | --- | --- |
| qBittorrent | **只預置「讓 Berth 進得去」**：只放行 Berth 容器固定 IP 的免密白名單（不是整個網段，理由見 §20.7）。原因是 4.6.1 起首次啟動的隨機密碼只印在容器 log，Berth 拿不到，沒有這一步按鈕就登不進去 | 套用建議偏好（temp path、save path、autoTMM）、依 Route 建立 category、設定 WebUI 密碼；按下前顯示差異 | 無 |
| Jellyfin | 無 | 偵測「尚未完成初始精靈」→ 以 Berth 管理員帳密建立 Jellyfin 管理員 → 建立 Movies / TV / Anime 三個媒體庫（對應 `/data/library/{movies,tv,anime}`）→ 自動建立三個 Route | 無 |
| Prowlarr | 無；Berth 唯讀掛載其設定目錄讀取 API key | 加入預設索引站清單（Nyaa.si、dmhy、AniDex、Anime Tosho、ACG.RIP、Mikan、1337x、YTS、EZTV、The Pirate Bay，可勾選）、以 Berth 管理員帳密設定介面登入 | 私有站的帳號 |
| TMDB | 無 —— **Berth 不內建任何 provider 的 key**【決定 2026-09-09】 | 無 | **必要**：自己申請一把 API key 貼進精靈第 6 步（§20.7） |
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
- **健康檢查會擋下的情況**：qBittorrent 回報的 save path 在 Berth 看不到；Jellyfin 的媒體庫路徑在 Berth 看不到；兩者在 Berth 內是不同掛載（`link()` 回 `EXDEV`）；qBittorrent 低於 4.4；Jellyfin 低於 12.0（說出目前版本，附升級注意：先完整備份、移除第三方插件、升級後完整掃描、不能降級，§20.9）；媒體庫掛 TVDB 插件（警告，M2 票 09c 起是一件 `library_uses_tvdb` Issue，§9.1）。每項附「哪個容器少了哪個掛載」的 compose 修正片段。
- **跨主機驗證**：Berth 在 Route 目標寫一個探測檔，再以 `POST /Environment/ValidatePath` 請 Jellyfin 確認看得到同一路徑（§20.7）；Jellyfin 在別台機器而路徑不一致會立刻現形。
- **不支援**：Jellyfin 10.x（2026-09-15 起只支援 12 以上，§19）；Berth 與 qBittorrent 不在存放媒體的同一台機器（硬鏈接做不到）；remote path mapping（第一階段不做，見 §18）。

---

## 17. 里程碑（tracer bullet）

每個里程碑結束時 repo 都可運作、可部署。

| 里程碑 | 內容 | 驗收 |
| --- | --- | --- |
| **M0 骨架** | §20.6 的實驗（結果可能改變命名決定，所以最先做）、compose 範本（profiles）與最小預置、精靈（建立管理員、逐服務判斷套件內或既有、套件內服務全自動設定、既有服務連線與確認按鈕）、Route 建立、健康檢查 | 實驗結論寫回本文件；在乾淨的 Linux 與 Windows Docker Desktop 上 `docker compose up` 後只操作 Berth 即完成設定，四項健康檢查綠燈；另以「既有 Jellyfin + 套件內其餘服務」的組合走一次 |
| **M1 手動全流程** | 探索 → 詳情 → 索引站搜尋 → 送 qBittorrent → 輪詢 → 規則 planning → 硬鏈接 → 掃描 → 媒體庫頁顯示可播放 + 深連結；Job 時間線；benchmark v0 | 一部美劇一季、一部動漫一季、一部電影，三者不經人工入庫並在 Jellyfin 正確顯示 |
| **M1.5 媒體庫瀏覽** | 媒體庫與 Media 詳情像 Jellyfin 那樣瀏覽（§12、§13）：整個 Jellyfin 媒體庫疊上 Berth 狀態、繼續觀看、下一集、已看 / 未看與切換、類型與年份排序、Jellyfin 的圖、選季選集；播放深連結到 Jellyfin | 以一般使用者登入，不開 Jellyfin Web 就能找到要看的那一集、看到自己的進度並標記已看，按播放落在 Jellyfin 的那一集；Jellyfin 不讓這位使用者看的媒體庫，在 Berth 也看不到 |
| **M2 修正與對帳** | Review Queue、Unmatched 指派、rematch、Reconciler、刪除範圍、重新入庫、`berth rebuild-ledger`（§16.2 的災難復原指令）、Job 詳情頁 | 刪掉 library 後可一鍵重建；Issue 表對三種人為破壞都能偵測；medium 自動入庫可一鍵撤銷；`user` 看不到也按不到審核與刪除 |
| **M3 RSS** | Mikan 與 Nyaa adapter、Rule、去重、一次性連結、dry-run | 一個動漫季度分別以 Mikan 與 Nyaa feed 全自動追完 |
| **M4 AI fallback** | AI Plan、驗證、快取、預算、Event 記帳（§6.10；不是 agent） | benchmark 上 review 比例下降且誤入庫率不升 |
| **M5 通知**（2026-09-22 加） | `events` 訂閱者、channel adapter（Telegram / Discord 擇一）、每人的訂閱設定（§14） | RSS 命中 → 入庫 → Jellyfin 可見的全程，手機收到「正在下載」與「可以看了」兩則 |
| **M6 AI 助理**（2026-09-22 加） | agent 核心、提案、Review Queue 的 AI 模式、側面板、工具權限模型（§14） | low 信心 Job 交給 AI 模式後佇列上有說得出理由的提案，人確認才入庫；AI 不能在沒有確認下動任何檔案 |
| **M7 外部對話**（2026-09-22 加） | M5 的管道接上 M6 的核心：聊天軟體裡對話、提案卡帶按鈕、個人 API token（§14、§16.2） | 手機上收到通知、回一句話、按確認之後那一集在 Jellyfin 是已看 |
| 之後 | anime-lists 對應、Jellyfin Webhook（§9.5，社群回報不可靠）、字型與字幕解壓、多使用者審批、非影片媒體、MCP server | — |

---

## 18. 明確延後或不做

| 項目 | 處置 | 理由 |
| --- | --- | --- |
| complete / incomplete 鏡像 library 結構 | 不做 | §4.2 |
| library 內的 `unmatch` 資料夾 | 不做，改為 UI 列表 | §7.4 |
| 內嵌播放器 | 延後（M1.5 的媒體庫瀏覽照樣跳到 Jellyfin 播放） | §12 |
| AI 解析 | M4 | 先有 benchmark 才能評估 |
| 品質升級自動替換 | 不做 | 版本並存（Jellyfin 12 原生合併）已滿足；升級邏輯是 Sonarr 最複雜的部分 |
| remote path mapping | 不做 | 強制同路徑掛載更簡單、更不易錯 |
| 多 provider（TVDB / AniList） | 延後 | §10 |
| 字型安裝、字幕解壓、OST 入音樂庫 | 延後 | 非核心流程 |
| BDMV 原盤 | 只辨識不處理 | 需要 Jellyfin 端特殊結構 |
| 多使用者審批、配額 | 延後 | 角色模型已預留 |
| 通知 | M5 | §14、§17（2026-09-22） |
| AI 助理（Review Queue 的 AI 模式、側面板、外部對話） | M6 / M7 | §14、§17（2026-09-22）；M2 的命令面與 M4 的 provider 先到 |

---

## 19. 決策紀錄與待決問題

已由 owner 拍板（2026-09-07 起，之後的決定在項目欄註明日期）：

| 項目 | 決定 | 落點 |
| --- | --- | --- |
| 產品名稱 | Berth | §1.4、§20.5 |
| 技術棧 | Python（FastAPI + worker + SQLite）+ React | §16.1 |
| 檔名 tag | 英文 token（CHT / CHS / JP / EN 等） | §6.8 |
| 第一批 RSS 來源 | Mikan、Nyaa | §15、§17 M3 |
| medium 信心 | 所有 Route 預設自動入庫，帶 audit 旗標 | §6.5、§13 |
| 集標題 | 有正式標題才進檔名，不自動改名 | §7.1 |
| UI 語言 | zh-Hant 與 en 並列，跟隨瀏覽器 | §16.2、`PRODUCT.md` |
| 授權 | MIT | §16.2 |
| 目標環境 | Linux 與 Windows 的 Docker；NAS 與一般電腦使用者；套件內含 Jellyfin / qBittorrent / Prowlarr，開箱即用 | §16.1、§16.3 |
| 索引站管理器 | 套件預設 Prowlarr（有文件化 REST API 可一鍵加索引站）；Jackett 以 Torznab 端點接入 | §3、§16.3、§20.7 |
| 媒體庫的角色（2026-09-15） | 像 Jellyfin 那樣瀏覽，播放跳 Jellyfin；牆上是整個 Jellyfin 媒體庫疊上 Berth 狀態；已看 / 未看可切換並寫回 Jellyfin；探索與媒體庫共用同一個 Media 詳情頁，作品在 Jellyfin 裡時觀看區在最上；排在 M1 驗收後、M2 之前（M1.5） | §1.1、§1.2、§12、§13、§17、plan §11.2b |
| Jellyfin 支援版本（2026-09-15） | **只支援 Jellyfin 12 以上**（同日稍早定的「兩條版本線都支援、13.0 發佈才拿掉 10.x」被使用者改掉，為了降低複雜度）。MergeVersions 的精靈步驟、既有服務按鈕、resolver 的合併觸發與任務 id 整段移除；既有 Jellyfin 低於 12 時，精靈與健康檢查紅燈，說出目前版本並附升級注意（§20.9），不往下做。代價是已知的：從 10.11 升到 12 有遷移失敗的 open issue、舊客戶端要升級、binhex（unRAID）與 QNAP 社群套件還沒有 12，那些使用者要先升級才能接本系統 | §1.2、§7.7、§16.4、§20.9、M1 票 14b |
| 套件內 Jellyfin image（2026-09-15） | 釘在 12.1 這條線（linuxserver `version-12.1ubu2604`）：跟得上 12.1 的修正與重建，但 pull 時不會默默跨到下一版；本系統實測過新版才調高，README 寫升級步驟（先備份 Jellyfin 的 `/config`、升級後完整掃描） | §16.3、§20.9、plan §9.1、M1 票 14b |
| 多集檔與同起始集的單集（2026-09-15） | 同一季已有、或同一批要入的正片裡，有同起始集而結束集不同的，送審核不自動入庫；理由要說出 Jellyfin 12 會把它們併成一集、藏掉後面的集 | §7.8、§20.9、M1 票 14b |
| Route profile（2026-09-16） | **移除**。量測（§20.4）顯示它唯一的作用是「只有集號、TMDB 多季」時絕對編號換算自動入庫（anime）還是送審核（standard），而「是不是動漫」預測不了換算對錯。改由兩條證據決定：集號 ≤ 第一季集數、或檔名的播出日與換算出的那一集對不上，就送審核，其餘 medium。季號搜尋變體改成對所有劇集都做。代價：多季作品第一季的無季號發佈送審核。**14d 量過**（M1 票 01 的真實發佈，§20.4）：規則 1 擋下的 1,095 個檔案裡 928 個其實是第一季；「標題有認不出的多餘字」分不開兩者——連 TMDB 別名一起比會讓 14 個後面季的自動入錯，只比主標題時一個不漏卻是靠 TMDB 英文標題碰巧夠長。**2026-09-17 維持規則 1 原形** | §6.4、§6.5、§20.4、`docs/research/profile-effect.md` §6.1、M1 票 14d（解析器，已完成）/ 14e（拿掉欄位、API、介面與語料，已完成） |
| M1.5 拆票前的四條（2026-09-15） | 媒體庫頁一個 Jellyfin 媒體庫一頁，只列這位使用者 `UserViews` 裡有的，Route 退成卡片上入庫狀態的來源；首頁上方放這位使用者的繼續觀看與下一集（沒有內容就不出現），下面維持探索；瀏覽時取允許清單一併讀 Jellyfin 帳號的 `Policy`（同一份短時間快取），帳號被停用就結束 Berth 的 session，不縮短 session 效期；Jellyfin 的圖片由 Berth 代理，快取鍵用 `tag` | §12、§13、§20.8、plan §11.2b |
| 顯示用標題的語言（2026-09-17） | **跟著 UI 語言走**，不另做「片庫語言」設定：`zh-Hant` 介面顯示 TMDB `zh-TW` 那一輪的標題與簡介，EN 介面顯示 `en-US` 那一輪的。檔名與資料夾名照舊只用英文（§7.5），不跟 UI 走。M1 票 15 的 critique（2026-09-17）量到 EN 介面上海報牆、詳情頁 h1 與簡介全是中文，與「英文是一等公民」（`PRODUCT.md`）衝突。**例外**（同日 M1.5 拆票時拍板）：媒體庫牆上已在 Jellyfin 裡的作品顯示 Jellyfin 的名稱，不為每一部去查 TMDB——牆上多數作品 Berth 沒有快照，大媒體庫第一次載入要打上千個請求；代價是 EN 介面從牆上點進 Media 詳情時標題可能換成另一種語言 | §7.5、plan §8.3、§11.2b（M1.5 票 02、03） |
| TMDB 連不上時的精靈（2026-09-17） | **接受**：TMDB 憑證維持精靈第 6 步的閘門（M1 票 02b），`api.themoviedb.org` 被防火牆擋住的使用者裝不起來是這個決定的代價，不另開「先完成精靈、探索與入庫停擺」的路 | §16.3、README〈先申請一把 TMDB API key〉 |
| 審核、修正與刪除的權限（2026-09-22） | **一律 admin**：Review Queue、Issue 的動作、rematch、刪除範圍、手動對帳。plan §6 與 `api/gate.py` 原本只擋 `settings/*`、`routes/*`，與本文件 §11、`PRODUCT.md` 矛盾，M2 補齊；`user` 的 Job 停在 review 時畫面說「等管理員審核」 | §11、plan §6、§11.3 |
| M2 拆票前的九題（2026-09-22） | 全部照建議：`/jobs/:hash` 獨立頁；快取門檻寫進量測票；Issue 型別十一種聯集與依型別的冪等鍵、`/issues` 獨立頁；刪除旗標預設全不勾、同步 `stat` 估算；reconciler 手動 202 + 輪詢、正在跑 409；`GET /review` 一支一列一件事不分頁；rematch 內部建單 item Plan；rebuild-ledger 配不到的建 Issue 不猜 | §9、plan §2.4、§3.2、§6、§7、§11.3 |
| AI 與通知的里程碑（2026-09-22） | M2 → M3 → M4 fallback（維持小範圍）→ **M5 通知 → M6 AI 助理 → M7 外部對話**。owner 要的四件事拆成三個里程碑：通知不是 AI；Review Queue 的 AI 模式、側面板、外部對話是同一個 agent 核心的三個介面，核心的形狀是「提案 → 人確認 → 執行」 | §14、§17、§18、plan §11.6–§11.8 |
| 精靈的兩個產品問題（2026-09-22，M0 票 11 的 critique 留下） | **維持現狀**：建管理員的密碼只有一格、靠「顯示密碼」（GitHub / Vercel 的慣例，二次確認欄防的是看不見的輸入錯誤）；套件內十個索引站預設全勾（一鍵加入就是精靈那一步的目的，不想要的取消勾） | plan §9.3、M0 票 11 |
| 前端沒有 shadcn/ui、沒有腳本化的 playwright e2e（2026-09-22 結案） | plan §1.4 / §7 原本寫 shadcn/ui 為元件基礎，M0 票 05 起沒有引入、三個里程碑沒有一個元件需要它，plan 已改；plan §10 原本寫「playwright 對 Fake 後端跑精靈與 M1 流程」但從未寫過，UI 驗證是每張票用 playwright 實跑演練情境並貼結果，plan 已改成實話，腳本化是 M2 的候選票 | plan §1.4、§7、§10、§11.3 |

M1.5 拆票前的四條待決，2026-09-15 已全數照推薦拍板（上表「M1.5 拆票前的四條」那一列），這裡留著當時的理由：

- **媒體庫頁的分頁單位**：票 13 是一條 Route 一頁，但牆上改成整個 Jellyfin 媒體庫之後，一個 Jellyfin 媒體庫可以有多條 Route（§4.3、M1 票 14），也可以有 Berth 路徑以外的舊路徑——照 Route 分頁會讓同一批作品出現在兩頁。**推薦**：一個 Jellyfin 媒體庫一頁（Jellyfin 自己的慣例），並且只列這位使用者 `UserViews` 裡有的；Route 退成卡片上入庫狀態的來源。
- **首頁 `/`**：現在是探索頁；Jellyfin 的首頁是繼續觀看與下一集。**推薦**：首頁上方放繼續觀看與下一集兩列（沒有內容就不出現），下面維持探索——找片與接著看是同一位使用者最常做的兩件事。
- **帳號狀態跟不上**：Berth 的 session 活 30 天、只在登入時向 Jellyfin 驗證，而 API key 代讀被停用的帳號照常回資料（§20.8，2026-09-17 在 12.1.0 實測）。**推薦**：瀏覽請求取 `UserViews` 允許清單時，一起讀 `GET /Users/{id}` 的 `Policy`，兩者同一份短時間快取；帳號被停用就結束 Berth 的 session。不縮短 session，因為管理類頁面（下載、設定）也會一起被迫重新登入。
- **圖片怎麼到瀏覽器**：瀏覽器直連 Jellyfin（最簡單，但瀏覽器要連得到它，HTTPS 的 Berth 配 HTTP 的 Jellyfin 是 mixed content），還是由 Berth 代理（頻寬與快取自己處理）。**推薦**：Berth 代理，快取鍵用 `tag`。瀏覽器只要連得到 Berth，不依賴深連結的主機推導、也沒有 mixed content；縮圖後一張約 45 KB（§20.8 實測），代價可接受。

---

## 20. 研究與查證結果

（本節由查證子任務填入，附來源。）

### 20.1 Jellyfin 命名、extras、字幕、多版本、API

來源：jellyfin.org 官方文件、api.jellyfin.org OpenAPI、jellyfin GitHub issues。標「未證實」者需實測。

**命名**

- 劇集資料夾 `Series Name (2018) [tmdbid-12345]`，年份與 ID 皆可選但官方建議加；可疊多個 ID。季資料夾必須是 `Season NN`（不可 `S01`），Specials 放 `Season 00`。集檔名支援 `S01E01`、`S01E01-E02`、`S02E03 Part 1`。（[identifiers](https://jellyfin.org/docs/general/server/metadata/identifiers)、[shows](https://jellyfin.org/docs/general/server/media/shows)）
- 純數字或數字開頭的劇名會讓 metadata 搜尋失敗（[#15860](https://github.com/jellyfin/jellyfin/issues/15860)）→ 用 `[tmdbid-…]` 鎖定可迴避。
- 集號後面接方括號 tag 曾造成 AniDB 插件誤判（[anidb#11](https://github.com/jellyfin/jellyfin-plugin-anidb/issues/11)）；**核心解析器沒有這個問題**：方括號與 `+` 不會滲進 Series 或 Episode 名稱，Jellyfin 根本不從檔名取集標題（2026-09-07 實測，§20.6）。
- 檔名中的 ` - ` 會觸發「多版本」regex：沒有 Season 資料夾時不同集會被誤併為版本（[#7855](https://github.com/jellyfin/jellyfin/issues/7855)）。本系統一律有 Season 資料夾，§7.1 的格式已實測無誤（§20.6）。
- Extras 子資料夾名：`extras`、`behind the scenes`、`deleted scenes`、`interviews`、`scenes`、`samples`、`shorts`、`featurettes`、`clips`、`other`、`trailers`、`theme-music`、`backdrops`；**劇集層與季層都可放**。也支援 `-trailer`、`-short`、`-extra` 等檔名後綴。（[_video-external-extras.md](https://github.com/jellyfin/jellyfin.org/blob/master/docs/general/server/media/_video-external-extras.md)）
- 空的 `.ignore` 檔會讓整個資料夾被掃描排除；10.11 起非空 `.ignore` 支援 gitignore 語法。（[excluding-directory](https://jellyfin.org/docs/general/server/media/excluding-directory)）

**外掛字幕**

- 格式 `<影片名>.{flags}.{language}.{ext}`，flags 有 `default`、`forced`、`sdh`/`cc`/`hi`，另可放自由文字標題，例如 `… S01E01 Title.commentary.ja.aac`。（[_video-external-streams.md](https://github.com/jellyfin/jellyfin.org/blob/master/docs/general/server/media/_video-external-streams.md)）
- **中文語言碼是已知痛點**：`chi`/`zh`/`zho`/`zh-hk` 只被辨識為泛「中文」，`cht`/`zh-cn`/`zh-cht` 不被辨識（[#6302](https://github.com/jellyfin/jellyfin/issues/6302)）。`zh-Hant`/`zh-Hans` **只有 10.11 認得**（顯示為 Chinese (Traditional) / (Simplified)），10.10 完全不認、退化成「未定義」（2026-09-07 實測，§20.6）。
- 沒有可靠的語言碼能區分繁簡。**已實測採用**：語言用 `zh`，繁簡放自由文字標題欄位 —— `<stem>.CHT.zh.ass` 在 10.10 顯示為 `CHT - Chi - ASS - 外部`、在 10.11 顯示為 `CHT - Chinese - ASS - 外部`，自由文字排在最前面，兩個版本都分得出繁簡（§20.6）。

**多版本**

- 電影：同資料夾內 `Movie (2021) [tmdbid-…] - 1080p.mkv`，檔名必須與資料夾名完全一致直到 ` - `；` - ` 之後為版本標籤，結尾為 `p`/`i` 的標籤會依解析度排序，否則字母排序。（[_video-multiversion.md](https://github.com/jellyfin/jellyfin.org/blob/master/docs/general/server/media/_video-multiversion.md)）標籤內含**方括號與 `+` 已實測可用**（§20.6）；**標籤內含中文仍未證實** —— 實驗用的 tag 全是 ASCII，而 §6.8 的 group token 保留字幕組原文，中文組名會落在這個未測範圍。
- **劇集原生多版本在 10.x 不可靠**（12.0 起原生支援，§20.9）：10.8 起要求每集自己一個子資料夾才會視為版本，且社群回報同一集兩個檔案通常變成重複條目而非版本選單（[discussion#7900](https://github.com/orgs/jellyfin/discussions/7900)、[discussion#16063](https://github.com/orgs/jellyfin/discussions/16063)、[#13432](https://github.com/jellyfin/jellyfin/issues/13432)）。結論（10.x）：**劇集多版本必須靠 MergeVersions 插件**，本系統命名只需保證同集檔名的 `S01E01` 部分一致。
- MergeVersions 插件持續維護到 10.11 與 12.0（12.0.0 版 `targetAbi 12.0`；12.x 上對本系統的樹是空跑、不裝，§20.9），透過排程任務或設定頁手動觸發；沒有公開 API 可由外部呼叫，本系統用 Jellyfin 的排程任務 API 觸發（任務名已實測，§20.7）。（[README](https://github.com/danieladov/jellyfin-plugin-mergeversions/blob/master/README.md)、[releases](https://github.com/danieladov/jellyfin-plugin-mergeversions/releases)）已知問題：偶發錯誤、無法停用、跨媒體庫合併。

**API**

- `GET /Library/VirtualFolders` 回傳 `Name`、`Locations[]`、`CollectionType`（movies / tvshows / music / mixed …）、`ItemId`、`LibraryOptions`（含 `TypeOptions[].MetadataFetchers`，可用來偵測 TVDB 插件）。
- 觸發掃描：`POST /Library/Media/Updated` 帶 `{Updates:[{Path, UpdateType: Created|Modified|Deleted}]}` 做路徑級通知；`POST /Library/Refresh` 是全庫掃描。沒有「掃描單一資料夾」的專用端點。**`UpdateType` 不影響行為**：`LibraryController.PostUpdatedMedia` 對每一條都呼叫 `ILibraryMonitor.ReportFileSystemChanged(path)`，不看型別（2026-09-23 讀 jellyfin master 的原始碼，<https://github.com/jellyfin/jellyfin/blob/master/Jellyfin.Api/Controllers/LibraryController.cs>）。所以 rematch 拆掉的舊路徑照樣以 `Created` 通知（M2 票 08）。【原始碼】
- **路徑通知對「從來沒掃到過內容」的媒體庫無效**（2026-09-15 對 `lscr.io/linuxserver/jellyfin:latest` = **12.0.0** 實測，並查核 master 的 [`FileRefresher.GetAffectedBaseItem`](https://github.com/jellyfin/jellyfin/blob/master/Emby.Server.Implementations/IO/FileRefresher.cs)）：等 `LibraryMonitorDelay`（預設 60 秒）之後，它從通知的路徑往上找第一個已存在的 item；初次掃描時是空的媒體庫資料夾不會成為 item（log：`Library folder "/data/library/tv" is inaccessible or empty, skipping`），於是找不到、**不做事也不寫 log**，而 `POST` 照樣回 204。套件內的媒體庫一開始一定是空的，所以**第一次入庫一定踩到**。實測三個媒體庫送了三輪通知，四分鐘後仍是 0 個 item。這條與 `EnableRealtimeMonitor` 無關——`ReportFileSystemChanged` 不看它（同日查核 [`LibraryMonitor`](https://github.com/jellyfin/jellyfin/blob/master/Emby.Server.Implementations/IO/LibraryMonitor.cs)）。
- `POST /Items/{id}/Refresh` 在 master 上**沒有 `Recursive` 參數**（[`ItemRefreshController`](https://github.com/jellyfin/jellyfin/blob/master/Jellyfin.Api/Controllers/ItemRefreshController.cs)），對媒體庫 id 呼叫只刷新那一個 item 的中繼資料、不找新的子資料夾（實測 204，兩分鐘後仍是 0 個 item）。`POST /Library/Refresh` 在請求裡**等整次掃描做完**（[`LibraryController.RefreshLibrary`](https://github.com/jellyfin/jellyfin/blob/master/Jellyfin.Api/Controllers/LibraryController.cs) `await ValidateMediaLibrary`）。要「現在掃」又不把呼叫端卡住，用內建排程任務 **`RefreshLibrary`**（「Scan Media Library」／「重新掃描媒體庫」）：`POST /ScheduledTasks/Running/{id}` 收下就回；id 從 `GET /ScheduledTasks` 以 `Key` 找（12.0.0 實測 `7738148ffcd07979c7ceb148e06b3aed`）。
- `GET /Items` **沒有 `path` 篩選**。反查方式：以 `parentId=<library>&includeItemTypes=Series&fields=ProviderIds,Path` 找 Series（比對 tmdb id 或路徑），再取集並用 `Path` 比對。（[ItemsController.cs](https://github.com/jellyfin/jellyfin/blob/master/Jellyfin.Api/Controllers/ItemsController.cs)）**注意**：取集時不要用 `parentId=<series>` —— 10.11 在第一次掃描後對「已被 provider 認出來的」Series 會回 0 筆，`/Shows/{id}/Episodes` 同樣回 0，要再掃一次才正常；改用 `parentId=<library>&recursive=true` 再照 `Path` 前綴篩選，四種情況都對（2026-09-07 實測，§20.6）。12.0.0 沒有重現（2026-09-15，§20.8）。
- **`DELETE /Items/{id}` 會刪除磁碟檔案**（`DeleteFileLocation = true`），本系統絕不呼叫它。（[LibraryController.cs](https://github.com/jellyfin/jellyfin/blob/master/Jellyfin.Api/Controllers/LibraryController.cs)）
- 登入 `POST /Users/AuthenticateByName` 回 `AccessToken`、`ServerId`、`User`；`POST /Auth/Keys` 建 API key。
- 深連結：`{server}/web/index.html#!/details?id={itemId}&serverId={serverId}` 在 10.10.7 與 10.11.11 **都能開到詳細頁**，前端會正規化成 `#/details?id=…`；客戶端自己產生的連結一律不帶 `!`（2026-09-07 playwright 實測，§20.6）。沒有「直接開始播放」的穩定 URL。
- **`serverId` 可以不帶**：12.0.0 上登入後直接開 `{server}/web/#/details?id={seriesId}`（沒有 `serverId`）照樣畫出該作品的詳細頁與季列（2026-09-15 playwright 實測，Series `大熊餐廳`）。10.10 / 10.11 沒有測過不帶的形式。Berth 產生的連結不帶它（票 13）。
- **`GET /Items` 的每一筆都帶 `ServerId`，Episode 另帶 `SeriesId` 與 `SeasonId`**，不必另外在 `fields` 要（2026-09-15 對 12.0.0 實測）。反查一集時順手就知道它屬於哪個 Series，媒體庫的深連結靠它開到作品而不是某一集（票 13）。
- Webhook 插件有 `ItemAdded` / `ItemDeleted`，但走排程批次且社群長期回報不可靠（[#252](https://github.com/jellyfin/jellyfin-plugin-webhook/issues/252)、[#367](https://github.com/jellyfin/jellyfin-plugin-webhook/issues/367)）→ 支持 §9 以排程對帳為主。

**Provider**

- 內建劇集 provider 預設 TMDb（另有 OMDb 與 .nfo）；TheTVDB、AniDB、AniList 都是插件。TVDB 與 TMDB 混用時 Specials 編號錯配有實例（[#13294](https://github.com/jellyfin/jellyfin/issues/13294)）；多 provider 同時啟用時鎖定 ID 也可能被覆寫（[#16268](https://github.com/jellyfin/jellyfin/issues/16268)）→ 支持 §10 單一 TMDB。
- AniDB / AniList 插件的編號語意沒有文件 → 不納入第一階段。

### 20.2 qBittorrent Web API 與硬鏈接 / Docker 限制

來源：qBittorrent master 原始碼（`torrentscontroller.cpp`、`serialize_torrent.cpp`）、`WebAPI_Changelog.md`、qbittorrent-api 客戶端文件、TRaSH Guides、Servarr wiki、man pages。**社群 wiki 的 API 頁面已過時**（連「5.0」頁面都還列 `paused` / `root_folder`），以原始碼為準。

**`torrents/add` 現行參數**（[torrentscontroller.cpp](https://raw.githubusercontent.com/qbittorrent/qBittorrent/master/src/webui/api/torrentscontroller.cpp)）

- `urls` / `torrents`、`savepath`、`downloadPath` + `useDownloadPath`、`category`、`tags`、`rename`、`autoTMM`、`contentLayout`（`Original` / `Subfolder` / `NoSubfolder`，API 2.7 / qB 4.3.2 起，取代 `root_folder`）、`stopped`（API 2.11.0 起取代 `paused`）、`stopCondition`、`seedMode`（API 2.16.0 起，同時移除 `skip_checking`）、`filePriorities`、`ratioLimit` / `seedingTimeLimit`（API 2.8.1）。
- master 已不讀 `paused` / `root_folder`。adapter 必須先讀 `app/webapiVersion`，依版本送 `paused` 或 `stopped`；`torrents/pause|resume` 在 5.0 改名 `stop|start`。
- **回應形狀兩版不同**（2026-09-10 票 09 實測，見 §20.7）：4.4.5 回 `200` + `Ok.`，5.2.3 回 `200` 加一份 JSON 摘要。只認 `Ok.` 的用戶端會把 5.x 上每一次成功的送單都判成失敗。
- 【決定】支援下限 qBittorrent 4.4（API 2.8.4，2022）；以 5.x 為主要測試目標。

**分類與路徑**

- `createCategory` / `editCategory` 參數：`category`、`savePath`、`downloadPathEnabled`、`downloadPath`。per-category 未完成路徑自 API 2.8.4 / qB 4.4.0 即存在，但 WebUI 直到 **5.2.0** 才有介面管理（[Changelog](https://raw.githubusercontent.com/qbittorrent/qBittorrent/master/Changelog)）。本系統不用它（§4.2），只用全域 `temp_path` / `temp_path_enabled`。
- `torrents/categories` 回傳鍵在 4.4.0–4.4.1 曾在 `savePath` / `save_path` 之間反覆，adapter 兩者都要接受。
- `createCategory` 的表單鍵是 `category` 與 `savePath`；名稱空字串回 **400** `Category cannot be empty`，名稱不合法或建不起來（含同名已存在）回 **409** `Unable to create category`（查核 master 的 [torrentscontroller.cpp](https://github.com/qbittorrent/qBittorrent/blob/master/src/webui/api/torrentscontroller.cpp)，2026-09-08）。所以冪等要靠呼叫端先 `torrents/categories` 讀一次。
- autoTMM 開啟時 save path 跟隨 category；`category_changed_tmm_enabled` 為真時改 category 路徑會**自動搬移所有該分類 torrent**。→ 本系統建立 category 後不再改其 savePath；使用者改 Route 目標時建立新 category，舊 Job 維持原位。
- TRaSH 明確要求 category 模式必須 `Automatic`（autoTMM），否則下載不會進分類資料夾（[Basic-Setup](https://trash-guides.info/Downloaders/qBittorrent/Basic-Setup)）。

**狀態與檔案**

- `torrents/info` 欄位含 `hash`、`name`、`state`、`progress`、`save_path`、`content_path`（API 2.6.1）、`download_path`（原始碼有、wiki 未列）、`completion_on`、`category`、`tags`、`added_on`。
- `state` 值：`error`、`missingFiles`、`uploading`、`pausedUP`/`stoppedUP`、`queuedUP`、`stalledUP`、`checkingUP`、`forcedUP`、`allocating`、`downloading`、`metaDL`、`pausedDL`/`stoppedDL`、`queuedDL`、`stalledDL`、`checkingDL`、`forcedDL`、`checkingResumeData`、`moving`、`unknown`。「完成」判定：`progress == 1` 且 `completion_on > 0` 且 state **不是** `moving` / `checking*`（從 temp path 搬到 save path 期間 state 為 `moving`，此時不可入庫）。
- `torrents/files` 回傳 `index`、`name`（含相對路徑）、`size`、`progress`、`priority`（0 = 不下載）、`availability`。`name` 相對於 `save_path` 還是 `content_path` 文件未明 → adapter 以 `stat` 驗證組出的絕對路徑，兩種都試。`priority == 0` 的檔案要從 Plan 排除。
- 其他端點：`setLocation`、`rename`、`renameFile` / `renameFolder`（API 2.8.0）、`delete(deleteFiles)`、`setCategory`（category 不存在回 409）、`addTags`、`recheck`。
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
  progress 0（在等 peer 重新下載）。Berth 用 **recheck → start**（`missing_files` 的「重新校驗」），`client_error` 的
  「重試」只送 start——錯誤不是資料的問題，重新校驗一次幾十 GB 只是讓它晚一點回來。
- **沒有 webhook**；`sync/maindata` 以 `rid` 做增量輪詢。`autorun_enabled` / `autorun_program`（完成時執行外部程式，可帶 `%f` `%n`）可作為「喚醒輪詢」的加速手段，非必要。
- **`rid` 的狀態掛在 session（SID cookie）上**（2026-09-10 票 10 對 4.4.5 與 5.2.3 實測）：不帶 cookie 的話每一次請求都是新 session，回的永遠是 `full_update: true`。所以輪詢那一側必須把 HTTP client 握著不放（Berth 的 `Downloader`）。
- **增量那一輪的 `torrents[hash]` 只帶變動的欄位**（實測有的只剩 `{"num_leechs", "time_active"}`），所以呼叫端一定要把它併回上一份完整快照再讀——照字面讀會得到一個沒有 category、沒有 state 的空殼。被刪掉的 torrent 在 `torrents_removed`（hash 陣列）。
- **未完成時的 `completion_on` 兩版不同**：4.4.5 是 `0`、5.2.3 是 `-1`。完成判定寫 `> 0` 對兩版都成立，寫 `!= 0` 會讓 5.x 上每一個剛加入的 torrent 都被當成已完成。`total_size` 在 metadata 到手之前同樣是 `-1` / `0`。
- **`metaDL` 期間 `torrents/files` 回 `200` + `[]`**（兩版皆然），與「這個 torrent 不存在」同形——所以 `metadata_ready` 的判定要 state 與清單兩個條件都成立。
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
  被封要等過期或去 qBittorrent 的介面解除——改帳密只會再失敗五次，把封鎖時間重新算一輪。

- **`auth/login` 在 session 還活著時直接回成功，連密碼都不看**（同一輪實測：帶著 SID 打八次錯的
  密碼全部是 `200` + `Ok.`）。所以「驗一次帳密對不對」必須從沒有 cookie 的狀態發起。

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
- **探索三支端點的形狀**（2026-09-09 對真 API 錄，fixture 在 `tests/fixtures/http/tmdb/`）：`trending/{tv,movie}/week` 與 `search/multi` 的每一筆帶 `media_type`，`{tv,movie}/popular` **不帶**（型別由端點決定）。劇集用 `name` / `original_name` / `first_air_date`，電影用 `title` / `original_title` / `release_date`。`search/multi` 也回人物——`?query=miyazaki` 那一輪 20 筆裡 16 筆是 `person`。
- **`language` 換掉的不只是文字，還有清單的成員與順序**（2026-09-09 實測）：`trending/tv/week` 的 `en-US` 與 `zh-TW` 兩輪各 20 筆，只有 17 筆相同。所以清單要以 `en-US` 那一輪為準，`zh-TW` 只當「這一部叫什麼」的查表（plan §8.3）。`{tv,movie}/popular` 與 `search/multi` 在同一輪實測裡成員一致。
- **回應裡的 `popularity` 不是清單的排序依據**（2026-09-09 實測）：`trending` 與 `popular` 兩支的 `results[]` 都不是照 `popularity` 降冪排的（`tv/popular` 首五筆是 583 / 440 / 692 / 417 / 398）。要照 TMDB 的排名就直接用陣列順序，拿 `popularity` 重排會得到第三種順序。
- **未翻譯時 `name` 回英文而不是空字串**（2026-09-09 實測 `zh-TW`）：`tv/popular` 那一輪的 `Watch What Happens Live with Andy Cohen`、`El conquistador` 都原樣回來。所以「翻譯缺」與「同名」在回應上分不出來，兩種都當成「顯示英文」即可。
- **詳情四支端點的形狀**（2026-09-09 對真 API 錄，fixture 在 `tests/fixtures/http/tmdb/`，票 04）：`tv/{id}` 的 `seasons[]` 每筆有 `season_number` / `name` / `episode_count` / `air_date`，`season_number: 0` 就是 Specials；`tv/{id}/season/{n}` 的 `episodes[]` 每筆有 `episode_number` / `name` / `air_date` / `runtime`（未播的集數 `runtime` 是 `null`）；`movie/{id}` 有 `runtime` 而完全沒有 `seasons`。不存在的 id 回 **404 加 `status_code: 34`**，與「TMDB 壞了」是兩件事。
- **Absolute episode group 的絕對編號要自己從 0-based 的 `order` 推**（2026-09-09 實測 SPY×FAMILY 的 `689a2aec017d0bc9ecc6fac8`）：group 裡的 `episode_number` **保留播出序的原值**，所以第一季二十五集之後，S02E01 在 group 裡仍然是 `episode_number: 1`，而它的絕對編號是 26（`order: 25`）。照 `episode_number` 讀會把整個第二季算成第 1–12 集。同一部作品有五個 episode group（Cours / 兩個 type 1 / Absolute / Blu-ray / Story Arcs），只有 `type: 2` 是絕對編號——這與「有的部有多個互相衝突的 Absolute group」是同一件事的兩面。
- **動漫 split-cour 正被 TMDB 與 TVDB 同步合併成單季連續編號**（例如 Dandadan S2 併入 S1），字幕組編號則多數按 cour 重新從 01 起算。（[TMDB talk](https://www.themoviedb.org/talk/697d0680d564e13094e4e270)、[TVDB KB](https://support.thetvdb.com/kb/faq.php?id=61)）**2026-09-09 實測修正兩點**：（一）TMDB 的合併比這段原記載更激進，**連獨立的連續季也在併** —— 咒術迴戰 3 季併成 1 季 59 集、Re:Zero 4 季併成 1 季 85 集、芙莉蓮 2 季併成 1 季 38 集、柯南 34 季併成 1 季 1213 集；TVDB 這幾部都維持分季。（二）**這不是主要錯誤來源** —— 量化後合併只造成 0.4 個百分點的差距，真正的主要來源是檔名沒有季號（§10、`docs/research/anime-episode-source.md`）。
- **季名逐語言翻譯，而且三套字都有人用**（2026-09-10 實測 `tv/85937`、`tv/1429`，票 06）：同一季的 `name` 在 `en-US` / `zh-TW` / `zh-CN` 分別是 `Hashira Training Arc` / `柱訓練篇` / `柱训练篇`，進擊的巨人第四季則是 `The Final Season` / `第4季` / `最终季`。**篇章名比對必須三套都留**：真實發佈裡最常見的寫法是簡體（`[Up to 21°C] 鬼灭之刃 柱训练篇 - 08`），只留英文季名的話 plan §4.4 那條規則對它一個都不會命中。代價是 `tv/{id}` 多打一輪 `zh-CN`（只取季名，電影不打，plan §4.3、§8.3）。
- **`alternative_titles` 帶篇章名但不帶季號**（2026-09-10 實測 `tv/85937`）：CN 只有 `鬼灭之刃 锻刀村篇` / `鬼灭之刃 游郭篇` 兩筆，TW 五個篇章齊全，JP 是羅馬字（`Kimetsu no Yaiba: Hashira Geiko-hen`）。它們對不出「這是第幾季」——那個對應只有 `seasons[].name` 給得出來，所以比對的主力是季名，別名只是補充。
- **split-cour 的兩個 cour 之間可以超過半年**（2026-09-10 實測 `tv/1429/season/3`）：進擊的巨人第三季 E12 播於 2018-10-15、E13 播於 2019-04-29，相隔 196 天。所以 plan §4.4 的 180 天門檻同時切得出「虛擬季」與「同一季裡的 cour」——它們本來就是同一件事。
- **字幕組的編號習慣有四種，同一部作品會並存**（2026-09-09 實測 7,833 筆）：每 cour 從 01 重新起算（68%）、官方編號（16%）、正篇序位（13%）、季內連號（分割兩 cour 的第二 cour 從 13 接下去，3%）。Dandadan 第二季同時存在 `S01 | 01-24`、`[13-24]`、`S2 - 10`、`S2 - 20`（季號 + 絕對編號）四種寫法。解析器不能假設編號一致。

**TheTVDB v4**

- 存取模型（2026-09-07 重查，**原記載過度，已更正**）：申請 v4 key **免費**，dashboard → API Keys → Create a v4 API Key；選 End-User Subscriptions 者「your key will be automatically approved and ready for use」（[KB#81](https://support.thetvdb.com/kb/faq.php?id=81)）。`/login` 的 `pin` 是**選填**，官方文檔原話「provide your API key as "apikey". If you have a user-supported key, **also** provide your subscriber PIN as "pin". Otherwise…」（[v4-api swagger](https://thetvdb.github.io/v4-api/)）；不帶 PIN 可取得 token 並讀資料（本機實測）。
- 但**授權模型未變**：所有 key 必須「either a commercial license, or have subscriptions enabled for end users」（[KB#62](https://support.thetvdb.com/kb/faq.php?id=62)）；README 明說 user-supported 模式「requires that each of your users has a $12/year TheTVDB subscription」（[v4-api](https://github.com/thetvdb/v4-api)）；KB#81 另警告開發者自用 PIN「prohibited from sharing a PIN for multiple users… Your access may be shut off at any time, and/or legal action may be pursued」。→ **個人自用沒問題；Berth 內建一把 key 給所有使用者是靠執行寬鬆，隨時可能被關。** 若採用，走「使用者自己申請免費 key」而非內建。
- Jellyfin 官方 TVDB 插件是同一個形狀：`PluginConfiguration.cs` 有唯讀的「tvdb api key **for project**」（插件內建）與選填的「tvdb api key for user, this is the **subscriber's pin**」（[jellyfin-plugin-tvdb](https://github.com/jellyfin/jellyfin-plugin-tvdb/blob/master/Jellyfin.Plugin.Tvdb/Configuration/PluginConfiguration.cs)）。→ 使用者把 Jellyfin 媒體庫切成 TVDB 刮削**不需付費**，§10 的「Jellyfin 同源」理由因此被削弱。
- 季類型：default(aired) / absolute / dvd / alternate / regional，**每部劇都有**；對比 TMDB 的 Absolute episode group 只在有人替該劇手動建立時才存在。這是 TVDB 對動漫絕對編號換算的實質優勢。Sonarr 只用 TVDB（經 Skyhook 代理），並靠 TheXEM 做 scene 編號對應（[xem-guide](https://wiki.servarr.com/sonarr/xem-guide)）。
- **`absolute` 會把 OVA 與劇場版也編進去**（2026-09-09 實測 10 部）：SPY×FAMILY 的劇場版 CODE: White 佔掉 absolute 38，正篇第 38 集的 absolute 是 39；無職轉生兩支 OVA 佔掉 17 與 25；航海王的跨作品特別篇佔掉 590。**absolute ≠ 正篇第幾集**，而字幕組「接著往下算」時數的是正篇。
- 取資料要打兩次：`/series/{id}/extended` 只回 default order，絕對編號要另外打 `/series/{id}/episodes/absolute`（`page` 必填、每頁 100 筆），且 `absoluteNumber` 只在 `EpisodeBaseRecord`、`EpisodeExtendedRecord` 沒有。「一次拿多種排序」的 [issue #98](https://github.com/thetvdb/v4-api/issues/98) 開了五年未做。（2026-09-08 查 [v4-api swagger](https://thetvdb.github.io/v4-api/) 4.7.10）
- **授權是硬牆**：ToS 第 2 節寫 key 為 "non-transferable"、"solely for the product or project for which you have been provided access"，並禁止 "transfer, assign"（[tos](https://www.thetvdb.com/tos)）。官方對「終端使用者直連」只給談約或 subscriber-supported key（每位使用者 $11.99/年）兩條路；「每人自己申請一把免費 key」官方從未表態，**未證實**。

**Jellyfin 對絕對編號的支援（2026-09-08 讀原始碼）**

- **Jellyfin 沒有「絕對編號」這個概念。** `Emby.Naming` 解析得出 `Show - 128.mkv` 的數字，但 `EpisodeInfo` 只有 `EpisodeNumber` / `SeasonNumber`；沒有季資料夾時 `EpisodeResolver` 直接把季號設成 1。
- 要走 absolute 得把**整部劇**的 `Series.DisplayOrder` 設成 `absolute`（`tvshow.nfo` 的 `<displayorder>`，或 `POST /Items/{id}` 但會觸發整劇 FullRefresh + ReplaceAllMetadata）。jellyfin-plugin-tvdb 的 `PluginConfiguration.cs` 12 個欄位裡**沒有任何排序設定**，排序只來自 `Series.DisplayOrder`。
- absolute + specials 目前是壞的：插件把 absolute 的特輯打回 `official` season 0 查詢，[issue #91](https://github.com/jellyfin/jellyfin-plugin-tvdb/issues/91) 從 2023 open 至今。

**TMDB 的 Absolute episode group 不能當備援**（2026-09-08 實測 10 部）：只有 6 部有；有的部有多個互相衝突（進擊的巨人四個 Absolute group，集數 89/97/97/97），柯南的那個叫 "China Online Version"。而且 group 內的 `episode_number` 保持 aired order 原值，絕對編號要自己從 0-based 的 `order` 推。

**Sonarr Skyhook 不能寫進產品**：`https://skyhook.sonarr.tv/v1/tvdb/shows/en/{tvdbId}` 免認證、有 `absoluteEpisodeNumber`，適合當量測替身（本專案的實驗就是這樣用的，10/10 與 thetvdb.com 網頁一致）；但它封閉源（Team Sonarr 官方論壇："It is not open source and we don't have plans to open source it."）、無文檔、無 SLA，servarr 對同類 metadata proxy 的政策是 "We do not support directly hitting any metadata service that isn't our own"。

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
- **已證實（2026-09-10，M1 票 05，抓真實 torrent metadata）**：BD 包的附屬資料夾名兩家不同，社群轉述的那一串只對了一半。
  - [VCB-Studio 魔王2099](https://share.dmhy.org/topics/view/726629_VCB-Studio_2099_Demon_Lord_2099_10-bit_1080p_HEVC_BDRip_Fin.html)（223 個檔案）：`SPs/`、`CDs/`（每張碟一個子資料夾，內含 flac 與 webp）、`CDs/…/Scans/`、`Scans/`（`BDBOX`、`Vol.1`…）。**沒有** `Fonts/` 與 `Menu/`。
  - [DBD-Raws 不死者之王 第二季](https://share.dmhy.org/topics/view/668157_DBD-Raws_Overlord_Overlord_S2_01-13TV_SP_1080P_BDRip_HEVC-10bit_FLAC_MKV.html)（106 個檔案）：`SP/`（帶 SP 編號，每個配 `.sc.ass` / `.tc.ass`）、`PV/`、`NCOP&NCED/`、`menu/`（小寫）、`Fonts/Fonts.zip`（字型是壓縮檔不是散檔）。
  - 兩份都成了 §6.9 的語料（`tests/fixtures/parser/`），分類規則因此有真實輸入可以釘。

**只有集號、TMDB 上多季的真實發佈（2026-09-16，M1 票 14c，[研究](research/profile-effect.md)）**：
§6.4「只有集號 → 絕對編號」那一支在 v1 的 23 筆語料上一次都沒走到（34 次全是 TMDB 只有一季），
補了 5 筆走得到的才量得出 Route profile 的作用。

- **動漫的跨季連號換算得對**：SubsPlease `Spy x Family - 26`–`37`（S02E01–12）、`Boku no Hero Academia - 139`
  （S07E01）、Erai-raws `One Piece - 1089 ~ 1104`。**TMDB 的航海王第 22 季沿用官方集數當 `episode_number`**
  （S22E1089–1155），所以只有 absolute group 換對，各季累加換成 S22E01 是錯的。
- **非動漫的「集號」可能是另一套數法**：《Home and Away》`Episode.8214.2024-02-29` 累加換成 S37E32，
  但 TMDB 的 S37E39 集名就是 `Episode 8214`、播於同一天——TMDB 前 36 季比官方編號多收 7 集。
  韓國電視台的 `The.Return.of.Superman.E079.150524` 累加換成 S03E21，播出日與檔名一致，是對的。
- **字幕組每 cour 重數、篇章名只寫羅馬字時會被當成絕對編號**：Erai-raws
  `Bleach - Sennen Kessen Hen - Soukoku Tan - 01 ~ 14` 換成 S01E01–14，正解 S02E27–40（TMDB 季名是
  `Thousand-Year Blood War` / `千年血戰篇`，比不到羅馬字）。
- **`guessit` 預設把韓國電視台的 `YYMMDD` 讀錯**：`150524` 讀成 2024-05-15（本機 guessit 實測），要加
  `date_year_first`——官方說明「If short date is found, consider the first digits as the year」
  （[guessit 文件](https://guessit-io.github.io/guessit)的 `-Y, --date-year-first`；設定檔裡是 `date_year_first`）。
  加上之後讀成 2015-05-24，`2024-02-29` 這種四位數年份不受影響。
- 韓劇第二季以後、檔名沒有季號的 `Show.2.E01.YYMMDD` 在 TPB、Knaben、dmhy 都沒找到，公開索引站上的
  第二季發佈全部帶 `S02E`。
- **「集號 ≤ 第一季集數就送審核」擋下的多半是對的**（2026-09-17，M1 票 14d，[研究 §6.1.1](research/profile-effect.md)，
  `scripts/experiments/absolute_rule_cost.py`）：M1 票 01 那批以發佈時間判定正解的 Mikan 發佈，取 TMDB 上 ≥ 2 季的
  5 部（SPY×FAMILY、無職轉生、鬼滅之刃、進擊的巨人、航海王），每筆當成以標題為檔名的單檔 torrent 丟進 `plan`、
  合集逐集展開。走到絕對編號換算的檔案裡，集號 ≤ 第一季集數的**正解在第一季 928 個、在後面某季 167 個**；
  超過第一季集數的 1,219 對、54 錯，錯的 54 個正解全是播出日對不上、退回序位的那種，本身存疑。
  「標題有認不出的多餘字」（guessit 的標題候選不等於作品的已知名字）分不開兩者：連 TMDB 的 `titles` 一起比，
  放行 793 個第一季、漏掉 14 個後面季的——`Kimetsu no Yaiba: Katanakaji no Sato-hen` 本身就是 TMDB 別名，
  `Mushoku Tensei S2 [02]` 的季號被 Berth 丟掉（季號等於方括號集號時；M1 票 14f 已修，這 5 個之後
  讀得出季號、不再走到絕對編號換算）；只比三個主標題，放行 328 個、一個不漏，
  但無職轉生那 5 個是因為 TMDB 英文標題 `Mushoku Tensei: Jobless Reincarnation` 比羅馬字長才擋下，同一種寫法換成
  英文標題就是 `SPY x FAMILY` 的作品就會入錯。近似的限制：Mikan 只有標題沒有檔名、樣本以中文字幕組與動漫為主。

**Jellyfin 動漫命名的社群痛點**

- One Piece / Detective Conan 這類長篇：TVDB arc 順序 vs 絕對編號長期無解（[r/jellyfin](https://www.reddit.com/r/jellyfin/comments/1sny587/one_piece_tvdb_arc_order_vs_absolute_episode)、[tvdb-plugin#91](https://github.com/jellyfin/jellyfin-plugin-tvdb/issues/91)）。本系統只承諾「與 TMDB 一致」，不承諾符合任何一種社群偏好。
- Split-cour 被 Jellyfin 併成一季的抱怨很多（[r/jellyfin](https://www.reddit.com/r/jellyfin/comments/1r5sk02/any_way_to_have_anime_seasons_shown_in_parts_like)）；本系統不對抗 provider，只做正確對應。
- Sonarr FAQ 也承認 Bleach TYBW 這類新 arc 只有在編號與 TVDB 對上時才會自動匹配；絕對編號缺失時需等 TVDB 更新。

**mediainfo（pymediainfo 7.0.1，2026-09-11 對真檔案實測）**

- `pip install pymediainfo` 的 wheel **內含 libmediainfo**，不需要系統套件（[README](https://github.com/sbraz/pymediainfo)）；在這台 Windows 上 `MediaInfo.can_parse()` 直接回 `True`。
- `MediaInfo.parse(path)` 回一份 track 清單，`track.to_data()` 是那一條的所有欄位。**同一個 `duration` 在不同 track 上型別不同**：General 上是整數毫秒（`2023`），Video 上是字串（`"2000.000000"`）——照抄任一邊的型別去讀另一邊都會拿到錯的值。
- 布林是字串 `"Yes"` / `"No"`（`forced`、`default`）；語言是兩碼（`ja` / `en` / `zh`），`other_language` 另有一組別名。繁簡分不出來，所以字幕軌的繁簡只寫在 `title` 裡（與 §20.1 的 Jellyfin 同一個限制）。
- 讀得完但不是媒體的檔案（例如一個 `.txt`）**不會丟例外**，回的是一份只有 General 的清單——所以「有沒有影像軌」才是「這是不是一個影片」的判準，而不是例外。
- 證據：`tests/fixtures/mediainfo/two-second-episode.mkv`（ffmpeg 造的 17 KB Matroska：10 bit AVC + 兩條標了語言的音軌 + 兩條標了 forced / default 的字幕軌）與 `tests/unit/test_mediainfo.py`。

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

**已完成（2026-09-07，票 04）**。完整結果與量測方式在
[`docs/research/m0-experiments.md`](research/m0-experiments.md)，腳本在 `scripts/experiments/`，
可重跑。以下只留結論與尚未完成的項目。

- ~~在 Windows Docker Desktop 的 NTFS bind mount 測硬鏈接~~、~~在 Linux 的 ext4 bind mount 跑同一腳本~~
  **都通過**（`hardlink.sh`：NTFS 9p bind mount 與 ext4 bind mount 皆 nlink=2、inode 相同；
  分成兩個 volume 則回 `Cross-device link` 並退出 1）。**但 ext4 那一輪跑的是 Docker Desktop
  自己的 Linux VM（`docker-desktop` 發行版）**，是 daemon 端的檔案系統，不是另一台實體 Linux
  宿主。**剩下：一台原生 Linux 宿主與至少一台 NAS**（Synology / QNAP / TrueNAS 其一），
  `sh hardlink.sh /volume1/<share>` 即可。
- **標籤內含中文**（中文字幕組名）未測：實驗用的 tag 全是 ASCII，見 §20.1「多版本」。
- ~~qBittorrent 4.4 與 5.x 的參數相容測試~~ **完成**，見 §20.7「qBittorrent 版本矩陣」。
- ~~Jellyfin 10.10/10.11 的命名實測~~ **完成**，見 §20.7「Jellyfin 命名實測」。§7.2 的電影範例與
  §7.7 的版本標籤說法已據此更正；plan §5 的模板凍結。
- ~~`WebUI\ServerDomains=qbittorrent` 是否足以通過 Host 檢查~~ **完成**：足夠，但代價是使用者從
  `localhost:8080` 進不了 WebUI，所以維持不預置（§20.7、plan §9.2）。
- ~~Prowlarr `config/host` 設定 Forms 帳密的欄位名~~ **完成**，見 §20.7「Prowlarr」。
- 建立 20 筆真實 torrent fixture（動漫 8、美劇/韓劇 8、電影 4）作為 benchmark v0。→ M1 解析器票。
- 抓一份 Mikan（我的訂閱、單作品 + 字幕組）與 Nyaa（搜尋）的實際 RSS，確認擴充欄位名
  （infoHash、大小、做種數、enclosure、發佈時間），寫成 adapter 的 fixture。→ M3 RSS 票。
- ~~抽 10 部動漫，量化**字幕組編號**對三種來源的換算失敗率：TMDB 季集、TVDB default(aired) season、TVDB absolute~~ **完成（2026-09-09，M1 票 01）**：7,833 筆真實釋出，TMDB 8.0% / TVDB aired 7.6% / TVDB absolute 7.6%。§10 的【研究】據此結案為**維持 TMDB**，完整結果與方法在 [`docs/research/anime-episode-source.md`](research/anime-episode-source.md)，腳本 `scripts/experiments/anime_episode_source.py` 可重跑。順帶推翻兩件事：§20.3 的合併政策比原記載更激進（TMDB 連**獨立的連續季**也在併，咒術 3 季→1 季、Re:Zero 4 季→1 季），以及 **TVDB 的 absolute 會把 OVA 與劇場版也編號**（SPY×FAMILY 的 CODE: White 佔掉 absolute 38），所以 absolute ≠ 正篇第幾集。

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
- **`POST /Environment/ValidatePath` 看得到回 204、看不到回 404**：`IsFile: true` 時走 `File.Exists`、`false` 時走 `Directory.Exists`、不給則兩者皆否才算沒有；`ValidateWritable: true` 會讓 Jellyfin 自己在那裡建一個暫存檔再刪掉，Berth 不送它——要問的只是「你看不看得到我寫的這一個」（查核 master 的 [EnvironmentController.cs](https://github.com/jellyfin/jellyfin/blob/master/Jellyfin.Api/Controllers/EnvironmentController.cs)，2026-09-08）。**404 是答案不是失敗**，adapter 因此把它翻成 `False` 而不是例外。
- `GET/POST /Repositories`（`{Name, Url, Enabled}`）、`POST /Packages/Installed/{name}?assemblyGuid=&version=&repositoryUrl=`、`POST /System/Restart`、`GET /ScheduledTasks`、`POST /ScheduledTasks/Running/{taskId}` 都需管理員（`RequiresElevation`）。
- MergeVersions：manifest `https://raw.githubusercontent.com/danieladov/JellyfinPluginManifest/master/manifest.json`，套件名 `Merge Versions`，GUID `f21bbed8-3a97-4d8b-88b2-48aaa65427cb`；排程任務 `Key` 為 `MergeMoviesTask` 與 `MergeEpisodesTask`（[RefreshLibraryTask.cs](https://github.com/danieladov/jellyfin-plugin-mergeversions/blob/master/Jellyfin.Plugin.MergeVersions/ScheduledTasks/RefreshLibraryTask.cs)），觸發時要用 `GET /ScheduledTasks` 回傳的 `Id`，不是 `Key`。

**Jellyfin 精靈序列實測**（2026-09-07，票 06；`jellyfin/jellyfin:10.11.11`，由 Berth 自己的 adapter 跑完 plan §9.4 全序列並錄下回應，fixture 在 `tests/fixtures/http/jellyfin/`）

- **`POST /Auth/Keys?app=` 回 204 而且不回傳 key**，只能再 `GET /Auth/Keys` 從 `Items[].AppName` 找回來。它**不檢查重複**：同一個 `app` 按兩次就有兩把 `AppName="Berth"` 的 key。所以要先列再建、建完再列。
- **`POST /Library/VirtualFolders` 同名不會被拒**：第二次一樣回 204，並建出名為 `Movies2` 的第二個媒體庫指向同一個路徑。冪等要靠呼叫端先 `GET /Library/VirtualFolders`。
- **`POST /Library/VirtualFolders/Paths` 不去重**：同一條路徑送兩次，該媒體庫的 `Locations` 就有兩個一樣的字串。目錄不存在時回 **404**（`Error processing request.`），所以路徑要先由 Berth 建好——Berth 與 Jellyfin 掛同一個宿主目錄在同一個容器路徑（§16.4），建完 Jellyfin 立刻看得到。
- **`LibraryOptions.TypeOptions[]` 省略 `ImageFetchers` 會被存成空陣列**（實測送 `{Type, MetadataFetchers, MetadataFetcherOrder}` 讀回來 `ImageFetchers: []`），該類型從此不抓圖。要嘛整個 `TypeOptions` 留空用 Jellyfin 的預設，要嘛兩種 fetcher 都給值。
- **`GET /Libraries/AvailableOptions?libraryContentType=movies|tvshows`** 回這台伺服器實際裝了哪些 fetcher（`{Name, Type}` 物件陣列），政策是 `FirstTimeSetupOrDefault`，精靈期間匿名讀得到。乾淨的 10.11.11：Movie 的 metadata 是 `TheMovieDb` / `The Open Movie Database`，image 多了 `Embedded Image Extractor` / `Screen Grabber`；tvshows 分 Series / Season / Episode 三個型別。裝了官方 TVDB 插件之後每個型別各多一個 `TheTVDB`，Series 還多 `Missing Episode Fetcher` —— 這正是「image fetcher 不可以寫死」的證據。
- **登入 token 與 API key 在標頭裡是同一個形狀**：`Authorization: MediaBrowser Client="…", Device="…", DeviceId="…", Version="…", Token="<token 或 key>"`，兩者都吃得下 `RequiresElevation` 的端點。
- **重啟的三個階段**：`POST /System/Restart` 當下連線直接被切（httpx 的 `RemoteProtocolError`）→ 一段時間所有端點回 **503** → 才回 200。所以「還沒好」有兩種形狀（連不上與 503），輪詢兩種都要當成繼續等。
- `StartupRemoteAccessDto` 在 10.11.11 的 schema **有** `EnableAutomaticPortMapping`（本節前面說「沒有」是過時的），但 Berth 只送 `EnableRemoteAccess`。
- MergeVersions 的排程任務 `Id` 在這台是 `MergeMoviesTask=fd957c84b0cfc2380becf2893e4b76fc`、`MergeEpisodesTask=dcaf151dd1af25aefe775c58e214477e`。**不要假設它跨安裝相同**，一律從 `GET /ScheduledTasks` 讀。
- 整段九步對真伺服器跑完 **69 秒**（大半花在插件下載與重啟）；第二次跑 **0.2 秒**，除了第 1 步之外全部是 `skipped`。

**Prowlarr**（[OpenAPI](https://raw.githubusercontent.com/Prowlarr/Prowlarr/develop/src/Prowlarr.Api.V1/openapi.json)、[supported-indexers](https://wiki.servarr.com/prowlarr/supported-indexers)、[environment-variables](https://wiki.servarr.com/prowlarr/environment-variables)）

- `GET /api/v1/indexer/schema`、`GET/POST /api/v1/indexer`、`POST /api/v1/indexer/test`；`GET /api/v1/search?query=&indexerIds=&categories=&type=` 回 `ReleaseResource`（`title`、`size`、`seeders`、`leechers`、`downloadUrl`、`magnetUrl`、`infoHash`、`indexer`、`categories`、`publishDate`、`guid`、`infoUrl`、`tmdbId` …）。Prowlarr 明言**不提供跨站聚合 Torznab**，單站 Torznab 為 `/{id}/api?t=search&apikey=`。
- **`indexer/schema` 的第一次呼叫很慢**（2026-09-08 票 11 M0 驗收實測）：容器剛起來時它要把 627 份 Cardigann 定義從 `/config` 讀進來再組出 **5.6 MB** 的回應，Windows Docker Desktop 的 9p bind mount 上量到 **9.42 秒**；同一支端點第二次 0.34 秒。慢的儲存（NAS）只會更久，所以這一支必須有自己的逾時，不能沿用探測用的 5 秒。**未量測**：成因是冷容器從 `/config` 讀那 627 份定義，不是回應大小，所以同一時刻的 `config/host` 理論上也慢；它目前仍用 5 秒，沒有數據支持那樣安全。
- API key 在 `config.xml` 的 `<ApiKey>`，可用 `PROWLARR__AUTH__APIKEY` 預設。
- 支援的公開索引站含：Nyaa.si、dmhy、AniDex、Anime Tosho、ACG.RIP、**Mikan**、1337x、YTS、EZTV、The Pirate Bay；TorrentGalaxy 目前不在清單。

**Prowlarr 索引站與 TMDB 憑證實測**（2026-09-08，票 08；Prowlarr 2.5.2.5491，fixture 在
`tests/fixtures/http/prowlarr/` 與 `tests/fixtures/http/tmdb/`）

- **`POST /api/v1/indexer` 會先連一次那個站再存**：成功回 201 與整份資源；連不上回 **400 加一個陣列**，
  每列是 `{isWarning, propertyName, errorMessage, severity}`。站沒有被建立。所以「逐站成敗」來自新增
  那一支，`indexer/test` 是給**已經存在**的站用的（回 200 空物件）。`?forceSave=true` **不會**跳過這個檢查。
- **同名的第二個站被拒**：400 `{"propertyName": "Name", "errorMessage": "Should be unique"}`。冪等只能靠
  呼叫端先 `GET /api/v1/indexer`。
- schema 的 `appProfileId` 是 **0**，原樣送回去建不起來；要換成 `1`（Prowlarr 內建的同步設定檔）。
- 十個預設站的 `definitionName` 實測為 `nyaasi`、`dmhy`、**`Anidex`**（不是文件寫的 `AniDex`）、
  `animetosho-xyz`（唯一 `semiPrivate`）、`acgrip`、`mikan`、`1337x`、`yts`、`eztv`、`thepiratebay`。
  站名 Prowlarr 自己會改，機器名不會，所以清單釘 `definitionName`。
- 本機這一輪十個站有五個加得起來、五個失敗（`nyaasi` 查得到但沒有結果、`Anidex` 與
  `animetosho-xyz` 連不上、`1337x` 與 `eztv` 被 CloudFlare 擋）。**幾個公開站連不上是常態**，UI 因此逐站顯示而不是整批成敗。
  另外：容器預設的憑證驗證會擋下 TLS 被攔截的環境（`config/host.certificateValidation`），那是使用者
  環境的事，Berth 不改它。
- **TMDB 的兩種憑證都打得動 v3 端點**：v4 的 read access token 走 `Authorization: Bearer`（官方建議、
  不進網址），v3 的 32 字元 API key 走 `?api_key=`；key 不對回 401。Berth 認憑證的**形狀**，
  所以使用者貼哪一種都成立。

**索引站搜尋實測**（2026-09-10，票 08；Prowlarr 2.5.2.5491 + 五個公開站 acgrip / dmhy / mikan /
thepiratebay / yts，fixture 在 `tests/fixtures/http/prowlarr/search.*.json` 與
`tests/fixtures/http/torznab/`）

- **`GET /api/v1/search` 很慢而且不吃 `limit`**：單次冷查詢 60–85 秒（Prowlarr 現場去連五個站），
  `limit=20` 仍然回 1200 筆。**三個查詢併發共 35 秒**，所以逐標題併發是對的，逾時要給到 120 秒。
- **`downloadUrl` / `magnetUrl` 每次請求都不一樣**：`link=` 的密文帶 nonce，同一個查詢連跑兩次
  1021 筆只有 1 筆重疊。`guid` 穩定（1200/1200）。所以身分是 infohash 或 `guid`，不是下載網址。
  兩者都是 Prowlarr **自己的代理網址**（主機來自它的 `config/host`，不是 Berth 打過去的位址），
  磁力站（TPB、dmhy）沒有 `downloadUrl`，只有被包成代理網址的 `magnetUrl`。
- **info hash 有兩種寫法**：同一個發佈在 Mikan 是 40 字十六進位、在 dmhy 是 32 字 base32，
  base32 解碼後位元組相同。不正規化的話單次查詢的 1200 筆裡有 47 筆會重複顯示。
- **多標題是真的多一批東西**：`Spy x Family` / `SPY×FAMILY` / `间谍过家家` 各搜出 1200 / 908 / 1210 筆，
  聯集 1854 筆，各自帶來 391 / 196 / 169 筆另外兩個問不到的結果。
- **tmdbid 是私站的功能**：627 份 Cardigann 定義裡 93 份的 `tvSearchParams` / `movieSearchParams`
  含 `tmdbId`，**全部是 private 或 semiPrivate**；十個預設公開站一個都沒有（YTS 只有 `imdbid`）。
  所以 `t=caps` 決定用哪一種問法時，`q=` 那條退路才是常態。
- **分類碼不是可靠的篩子**：dmhy 對 `cat=5000`、`cat=5070` 與不帶 `cat` 都回同樣 80 筆；
  它一筆帶 5070 / 100002 / 2020 而沒有 5000。Berth 因此不送 `categories`，只把分類當顯示資料。
- **The Pirate Bay 對搜不到的關鍵字會回它自己的熱門清單**：搜 SPY×FAMILY 時前六筆是 Spider-Man、
  Lanterns、Ted Lasso、Reacher，做種四千到六千。純做種排序時它們會把真正的結果整批擠出前 100 筆，
  所以 Berth 先用標題粗篩再逐站輪流取。
- **公開中文站的做種數是個位數**：Mikan / ACG.RIP / dmhy 的發佈多半 0–2 個做種，TPB 的 scene 發佈
  28–86 個。取「做種前 100 筆」等於把中文字幕組整批刪掉。
- **`parse_release` 每筆 14 毫秒**（1200 筆 17.4 秒，含 guessit）。一兩千筆全解析會把事件迴圈卡住
  半分鐘，所以粗篩要用純字串比對，解析只跑在留下來的那一百筆上。

**Jackett**（[repo](https://github.com/Jackett/Jackett)）

- API key 在 `ServerConfig.json` 的 `APIKey`；聚合 Torznab `/api/v2.0/indexers/all/results/torznab/api?t=search` 有文件（上限 1000 筆、站專屬分類不可用）；`GET/POST /api/v2.0/indexers/{id}/Config` 只是 UI 內部介面，無文件。有 `mikan.yml`、`dmhy.yml`、`nyaasi.yml`、`acgrip.yml` 定義。
- 結論維持 §19：套件預設 Prowlarr，Jackett 以 Torznab 端點接入。

**compose 套件實測（2026-09-07，Windows 11 + Docker Desktop 29.6.2，票 03）**

- **發佈 port 的來源位址**：Docker Desktop 把 `-p 8080:8080` 進來的流量 SNAT 成 bridge 閘道位址（`172.28.0.1`），而閘道本身就在 compose 網段內。所以 `WebUI\AuthSubnetWhitelist=172.28.0.0/16` 等於讓宿主與 LAN 上任何人免密打 qBittorrent 的 API —— 實測 `curl http://localhost:8080/api/v2/app/version` 直接回 `v5.2.3`。白名單縮成 Berth 容器固定 IP 的 `172.28.0.2/32` 之後：berth 容器回 200、宿主 403、同網段的其他容器 403。§16.3「LAN 使用者開 8080 仍要密碼」只有在白名單是單一位址時才成立。
- Docker 的動態 IP 從網段開頭配發（實測 `172.28.0.2` 給了先啟動的 prowlarr），固定 IP 要靠 `ip_range` 把動態池隔到別的段，否則會撞。
- **linuxserver/qbittorrent 的啟動順序**：`init-qbittorrent-config`（依賴 `init-config`）排在 `init-custom-files`（依賴 `init-mods-end`，而該鏈在 `init-config-end` → `init-qbittorrent-config` 之後）之前。custom-cont-init.d 的腳本跑到時 `/config/qBittorrent/qBittorrent.conf` **一定已經存在**，由 image 從 `/defaults/qBittorrent.conf` 複製。因此「檔案不存在才寫」的預置條件永遠不成立，改為「缺鍵才補」。
- `/defaults/qBittorrent.conf` 的內容：`LegalNotice\Accepted=true`、`WebUI\Address=*`、`WebUI\ServerDomains=*`、`Downloads\SavePath=/downloads/`、`Downloads\TempPath=/downloads/incomplete/`、`Connection\UPnP=false`、`Connection\PortRangeMin=6881`。整份覆蓋會掉 `LegalNotice\Accepted`，qbittorrent-nox 會卡在法律聲明；而 `ServerDomains` 既然預設是 `*`，Host 檢查本來就過得了，寫死成 `qbittorrent` 反而讓使用者從 `localhost:8080` 進不去。
- `init-custom-files` 只檢查 executable bit（不檢查擁有者），以 `/bin/bash <script>` 執行（[docker-baseimage-alpine](https://github.com/linuxserver/docker-baseimage-alpine/blob/master/root/etc/s6-overlay/s6-rc.d/init-custom-files/run)、[container-customization](https://docs.linuxserver.io/general/container-customization/)）。
- `lscr.io/linuxserver/qbittorrent:latest` 目前是 qBittorrent v5.2.3。
- Berth image（node:24-slim build → python:3.13-slim runtime）：281 MB 未壓縮、62.8 MB gzip，遠低於 400 MB 的上限。
- `python:3.13-slim`（Debian 13 trixie）內建 `setpriv`、`usermod`、`groupmod`、`getent` 與 tzdata，`PUID` / `PGID` 降權不需要額外裝 gosu；但沒有 curl。
- 空的 named volume 與 Docker 替 bind mount 新建的目錄都是 `root:root`，非 root 的容器寫不進去。入口腳本因此只在 `/data` 還是空目錄時接手擁有者，已經有內容的媒體根不碰（實測：空目錄 → 檔案為 `1500:1500`、`umask 002`；非空目錄 → 維持 `root:root`）。
- compose 內再次確認 `/data` 的硬鏈接：`dev=70`、inode 相同、`nlink=2`（與 §20.7 開頭的 Windows 實測一致）。

**TMDB 憑證由使用者自備**（2026-09-09 決定，推翻本節原本的「沿用 Seerr 的專案級 key」）

- Jellyseerr / Seerr 在 `server/api/themoviedb/index.ts` 寫死一把專案 key，使用者無處填自己的 key（[overseerr#3887](https://github.com/sct/overseerr/issues/3887)）；Jellyfin 團隊也曾討論專案級 key（[jellyfin#36](https://github.com/jellyfin/jellyfin/issues/36)）。TMDB 條款只區分商業與非商業，未明文規範「一 app 一 key」，所以那條路是走得通的。
- **本系統仍然不走**：一把發給所有使用者的共用憑證由專案背著它的用量與行為，而 TVDB 的 ToS 明文擋的也正是這件事（§20.3）。兩個 provider 在「使用者自己申請一把」上對稱，於是這裡也對稱處理。憑證的唯一來源是 `settings.services.tmdb.api_key`，精靈第 6 步是**必填的閘門**（plan §9.3）。
- 申請路徑：themoviedb.org 免費帳號 → 設定 → API → 用途選 Personal / Education，即時核發。同一頁同時給 v3 API key 與 v4 read access token，兩種形狀 Berth 都收（plan §8.3，2026-09-08 實測）。

**qBittorrent 預置**（[sessionimpl.cpp](https://github.com/qbittorrent/qBittorrent/blob/master/src/base/bittorrent/sessionimpl.cpp)、[linuxserver/qbittorrent](https://docs.linuxserver.io/images/docker-qbittorrent)、[qbittorrent-nox](https://github.com/qbittorrent/docker-qbittorrent-nox)）

- 4.6.1 起首次啟動用隨機臨時密碼印在 log；已知密碼要預置 `WebUI\Password_PBKDF2`（PBKDF2-HMAC-SHA512、100000 次）。官方 image 沒有密碼環境變數，也沒有 `PUID` / `PGID`；linuxserver image 有，且設定檔在 `/config/qBittorrent/qBittorrent.conf`。
- `[Preferences]`：`WebUI\Port`、`WebUI\AuthSubnetWhitelistEnabled`、`WebUI\AuthSubnetWhitelist`、`WebUI\LocalHostAuth`、`WebUI\HostHeaderValidation`、`WebUI\CSRFProtection`；`[BitTorrent]`：`Session\DefaultSavePath`、`Session\TempPath`、`Session\TempPathEnabled`、`Session\DisableAutoTMMByDefault`（**預設 true，即 autoTMM 關閉**）、`Session\DisableAutoTMMTriggers\CategorySavePathChanged`、`Session\Port`。
- Web API `app/setPreferences` 對應鍵：`temp_path_enabled`、`temp_path`、`save_path`、`auto_tmm_enabled`、`category_changed_tmm_enabled`、`bypass_auth_subnet_whitelist(_enabled)`、`bypass_local_auth`、`web_ui_password`（只寫）。

**Jellyfin 命名實測**（2026-09-07，票 04；`jellyfin/jellyfin:10.10.7` 與 `:10.11.11`，dummy 檔 + API 查驗，[完整結果](research/m0-experiments.md#1-jellyfin-命名10107-與101111)）

- **`S01E01` 一律認得**，`S01E03-E04` 解析為 `IndexNumber=3` + `IndexNumberEnd=4`，`S00E01` 進 `Specials` 季。**方括號與 `+` 不會滲進 Series 或 Episode 名稱** —— Jellyfin 根本不從檔名取集標題（TMDB 對不上的作品，帶 tag 與不帶 tag 的兩集名稱完全相同）。
- **電影多版本**：檔名在 ` - ` 之前必須與資料夾名一字不差（含 `[tmdbid-<id>]`），否則變成兩部獨立的電影。標籤含方括號沒問題，版本選單顯示的就是 `[BD][2160p][CHT+JP][Sakurato]`；結尾 `p`/`i` 的標籤依解析度降冪（`2160p` → `1080p` → `720p`），其餘字母序。§7.2 已據此更正。
- **劇集多版本**：未裝插件 → 同一集的兩個檔案變成**兩個重複的 Episode 條目**。裝 MergeVersions 跑 `MergeEpisodesTask` → 合併成 1 個 Episode、2 個 MediaSource，但**版本標籤是整個檔名主幹**而非只有 tags，且順序不保證（10.10 與 10.11 相反）。§7.7 已據此更正。12.x 不裝插件就原生合併，見 §20.9。
- **extras**：劇集層 `<作品>/extras/`、季層 `<作品>/Season 01/extras/`、電影層 `<電影>/extras/` 三者都成立，分別掛在 Series / Season / Movie 的 `SpecialFeatures`，不會被當成正片集數。
- **外掛字幕**：`<stem>.CHT.zh.ass` 在 10.10 顯示 `CHT - Chi - ASS - 外部`、10.11 顯示 `CHT - Chinese - ASS - 外部`（`Title` 欄排最前面，繁簡分得出來）。`.default.` 旗標兩版都生效。`zh-Hant`/`zh-Hans` **只有 10.11 認得**，10.10 顯示「未定義」→ 不採用。
- **深連結** `#!/details?id=…&serverId=…` 在兩個版本都開得到詳細頁（前端正規化成 `#/details?id=…`）。
- **精靈**：`POST /Startup/User` 之前**必須先 `GET /Startup/User`**，否則回 500（`Sequence contains no elements`）—— GET 會先建立預設使用者。`POST /Library/VirtualFolders` 的 body 是 `AddVirtualFolderDto`，`LibraryOptions` **要包一層**（`{"LibraryOptions": {...}}`），直接送會靜默丟掉整份設定。
- **MergeVersions**：`POST /Packages/Installed/Merge%20Versions?assemblyGuid=…` 不必指定版本，10.10.7 裝到 `10.10.0.5`、10.11.11 裝到 `10.11.0.1`；下載由 Jellyfin 連 GitHub，實測遇過 TLS 中斷回 500，要能重試。以上是 M0 時對 10.x 的紀錄；本系統只支援 12 以上、不再安裝它（§19）。排程任務 `Key` 為 `MergeEpisodesTask` / `MergeMoviesTask`，`Name` 為 `Merge All Episodes` / `Merge All Movies`，`Category` 為 `Merge Versions`。
- **重啟後不能只等 `/System/Info/Public`**：它在伺服器還在載入時就回 200，這時管理員 API（如 `/ScheduledTasks`）回 **503「Jellyfin 伺服器載入中」**。要輪詢真正要用的那個端點回 200 才算重啟完成（實測踩到過）。
- **`find_episodes` 的陷阱**：10.11 在第一次掃描後，對已被 provider 認出來的 Series，`/Items?parentId=<seriesId>` 與 `/Shows/{id}/Episodes` **都回 0**，再掃一次才正常；10.10 沒有這個問題，12.0.0 也沒有重現（§20.8）。改用 `parentId=<library>&recursive=true` 再照 `Path` 前綴篩選，四種情況都對。

**qBittorrent 版本矩陣**（2026-09-07，票 04；`lscr.io/linuxserver/qbittorrent:4.4.5`（API 2.8.5）與 `:5.2.3`（API 2.15.1），[完整結果](research/m0-experiments.md#2-qbittorrent-445-與-523)）

- **`torrents/add` 的回應形狀兩版不同**（2026-09-10 票 09 對 5.2.3 / 4.4.5 兩台乾淨容器實測，fixture 在 `tests/fixtures/http/qbittorrent/torrents-add.*`）：4.4.5 成功回 `200` + `Ok.`；**5.2.3 成功回 `200` 加一份 JSON 摘要**（`{"added_torrent_ids": […], "failure_count": 0, "pending_count": 0, "success_count": 1}`）。**這推翻本節原本記的「一律回 200 `Ok.`」**——那句話只對 4.4.x 成立。失敗也說得出話：同一個磁力連結送第二次在 5.2.3 是 `409 Conflict`（4.4.5 照樣回 `Ok.`），category 的 save path 當下用不了也是 `409`；multipart 上傳一份不是 torrent 的東西是 `415` 加檔名與原因。
- **交一條 http 網址給 `torrents/add` 是背景抓取**：5.2.3 回 `202` + `pending_count: 1`，抓失敗之後**永遠沒有下文**——torrent 不會出現，而用戶端已經回過 2xx 了。所以 Berth 自己先把 torrent 抓下來（`adapters/torrent.py`），交出去的一律是磁力連結或位元組，這樣「收不收」當場就有答案（票 09）。
- **`paused` 與 `stopped` 各版本只認一個，送錯的那個會靜默地開始下載**：4.4.5 `paused=true` → `pausedDL`、`stopped=true` → `queuedDL`（沒暫停）；5.2.3 `paused=true` → `stalledDL`（沒暫停）、`stopped=true` → `stoppedDL`。`torrents/add` 一律回 200，不認得的參數不報錯。plan §8.1 的版本判斷是必要條件，不是最佳化。
- **`torrents/files[].name` 相對 `save_path`**（多檔會含 torrent 根目錄那一層），四種 `contentLayout` 組合都成立；`content_path` = save_path + 根目錄，單檔時指向檔案、多檔時指向目錄。單檔 + `Subfolder` 的子資料夾名是去掉副檔名的 torrent 名。**`save_path` 的尾斜線兩版不同**（4.4.5 `/downloads/`、5.2.3 `/downloads`），組路徑前要正規化。
- `torrents/files` 的鍵兩版相同：`index`、`name`、`size`、`progress`、`priority`、`is_seed`、`piece_range`、`availability`。
- **`torrents/categories` 兩版都回 `savePath`**（駝峰），沒有出現 `save_path`；5.2.3 另有 `download_path`、`ratio_limit`、`seeding_time_limit`、`inactive_seeding_time_limit`、`share_limit_action`。
- **Host 檢查除了網域還比對 port**：`ServerDomains=*` 也擋 port 不符的 Host（實測 `Host: localhost:18080` → 401，容器 log 寫 `Invalid Host header, port mismatch`）。設成 `qbittorrent` 之後 `localhost:8080` 與 `127.0.0.1:8080` 全被擋。沒有 port 的 Host 一律放行。偏好鍵是 `web_ui_host_header_validation_enabled`（兩版都有）。實驗改的是 Web API 的 runtime 偏好 `web_ui_domain_list`，它對應設定檔的 `WebUI\ServerDomains`（同一個設定的兩種寫法），沒有另外測「預置 ini 鍵」那條路徑。→ compose 的 qBittorrent **不可以把發佈 port 改成別的號碼**，否則使用者開不了 WebUI。
- **CSRF**：送了 `Origin`/`Referer` 就必須與 Host 一致（不一致 → 401），完全不送則放行。兩版相同。

**Prowlarr `config/host`**（2026-09-07，票 04；Prowlarr 2.5.2.5491）

- `GET /api/v1/config/host` 回 39 個欄位；認證相關為 `authenticationMethod`（`none`/`basic`/`forms`/`external`）、`authenticationRequired`（`enabled`/`disabledForLocalAddresses`）、`username`、`password`、`passwordConfirmation`、`apiKey`。
- 設 Forms 帳密：`PUT /api/v1/config/host/1`，body 是完整的 config/host 物件加上上述五個欄位（**少了 `passwordConfirmation` 會被拒**）→ 回 **202**，Prowlarr 隨即自行重啟，要等它回來才能繼續。
- 設完之後：不帶 `X-Api-Key` 的 API 回 401，**`GET /ping` 仍然匿名 200**（所以健康檢查不會因為使用者加了密碼而變紅）。`password` 讀回來是雜湊。
- API key 從 `config.xml` 的 `<ApiKey>` 讀得到（首次啟動即產生，32 字元），與 plan §9.2 的做法一致。

**硬鏈接腳本**（`scripts/experiments/hardlink.sh`，2026-09-07）

- Linux ext4 單一掛載根：PASS（nlink=2、inode 相同）。Windows NTFS bind mount（9p）：PASS（dev=70）。`torrent/` 與 `library/` 分成兩個 volume：`ln: Cross-device link`，退出碼 1。
- ext4 那一輪的來源是 **Docker Desktop 自己的 Linux VM**（`/mnt/docker-desktop-disk/...`），daemon 端的檔案系統，與原生 Linux 宿主是同一條 `link()` 路徑，但**不是另一台實體 Linux**。
- 腳本沒有相依，NAS 上 `sh hardlink.sh /volume1/<share>` 可直接跑；原生 Linux 宿主與 NAS 都尚未實測（§20.6）。

### 20.8 媒體庫瀏覽用的 Jellyfin API（M1.5 前置）

2026-09-15 查證；全文、端點範例與原始碼連結見 [`docs/research/library-browsing.md`](research/library-browsing.md)。2026-09-15 在 **12.0.0** 上實測，2026-09-17 在一次性的 **12.1.0** 上以只開放部分媒體庫的使用者補測權限、過濾排序、TMDB 反查、標記遞迴與停用帳號（M1.5 票 01，`scripts/experiments/jellyfin_permissions.py`，研究 §0、§2、§3.1、§5、§10、§11；12.0.0 量過的行為在 12.1.0 上沒看到不同，只有圖片 CORS 標頭的條件判定不了）。原始碼對照 tag `v10.10.7`、`v10.11.11`、`v12.0`。

- **伺服器 API key 可以代讀代寫任何使用者**：API key 在驗證層一律算 Administrator，帶哪個 `userId` 就是誰（三版一致）。繼續觀看 `GET /UserItems/Resume?userId=&mediaTypes=Video`（不帶 `mediaTypes` 會混進 Season 與 Series）、下一集 `GET /Shows/NextUp?userId=`、附 `UserData` 的項目 `GET /Items?userId=`、已看 / 未看 `POST|DELETE /UserPlayedItems/{id}?userId=`。不帶 `userId` 時 Resume、NextUp、PlayedItems 回 400，`/Items` 回整台伺服器且沒有 `UserData`。舊路徑 `/Users/{userId}/...` 還能用但已不在 12.0.0 的 OpenAPI；NextUp 的 `disableFirstEpisode` 在 12.0 移除。【實測 12.0.0 + 原始碼】
- **媒體庫存取權限只有一部分會套用**（家長分級只要帶 `userId` 就套，這一條只讀原始碼）：`/UserViews?userId=`、不帶 `parentId` / `ids` 的 `/Items`、不帶 `parentId` 的 Resume / NextUp / `/Items/Latest` / `/Genres`、`/Items/{id}?userId=`、`/Shows/{id}/Seasons|Episodes?userId=`、`/UserItems/{id}/UserData?userId=`、`/UserPlayedItems` 會照使用者的權限（無權時不列或 404）；**帶 `parentId` / `ids` / `seriesId` 的查詢，以及帶 `parentId` 的 `/Genres`、`/Years`、`/Items/Filters`、`/Items/Filters2`、`/Items/Latest` 不會**。而且**使用者自己的 token 也只擋下 `/Items?parentId=<無權的媒體庫>`（401）**：劇或季當 `parentId`、`ids`，以及 Resume、NextUp、`/Genres`、`/Years`、`/Items/Filters(2)`、`/Items/Latest` 帶 `parentId`（NextUp 帶 `seriesId`）時，使用者 token 一樣照回。所以權限要由 Berth 自己擋，`parentId` 只放對 `UserViews` 驗證過的媒體庫 id（§12、plan §11.2b）。【實測 12.1.0 + 原始碼】
- **`/Items` 靜默忽略不存在的參數**：實測帶 `seriesId` 或 `ancestorIds` 都回整台伺服器的集，打錯字的 `genre=`、`year=` 回全部（12.0.0、12.1.0）。每個過濾參數都要測「伺服器真的有過濾」。
- **漏帶 `userId`**：`/Shows/{id}/Seasons|Episodes` 回 200 並**略過權限**（無聲洩漏），`/Items/{id}` 回 400，Resume、NextUp、`UserPlayedItems` 回 400。【實測 12.1.0】
- **排序與篩選**：`sortBy`（逗號、多鍵）加 `sortOrder`；`genres` 以 `|` 分隔（「或」）、`years` 以逗號（「或」），兩個參數之間是「且」。類型與年份清單用 `GET /Items/Filters?userId=&parentId=&includeItemTypes=Series|Movie`（三版形狀一致，jellyfin-web 的篩選面板用這支；**不帶 `parentId` 四份清單全空**；`Filters2` 沒有年份；`/Years` 不帶 `includeItemTypes` 會混進集的播出年）。劇集的「新集加入」排序是 `DateLastContentAdded`、「最近看過」是 `SeriesDatePlayed`；電影的「最近看過」是 `DatePlayed`。**jellyfin-web 的排序選單兩種媒體庫不同**（`tvshows.js` / `movies.js`，v10.10.7 與 v10.11.11 相同）：劇集庫 `SortName`、`Random`、`CommunityRating`、`DateCreated`、`DateLastContentAdded`、`SeriesDatePlayed`、`OfficialRating`、`PremiereDate`，每項後接 `,SortName`；電影庫 `SortName`、`Random`、`CommunityRating`、`CriticRating`、`DateCreated`、`DatePlayed`、`OfficialRating`、`PlayCount`、`PremiereDate`、`Runtime`，每項後接 `,SortName,ProductionYear`（`Random` 不接）。`sortOrder` 只送一個時套在每一個鍵上。12.1.0 逐一驗過 `parentId`、`includeItemTypes`、`genres`、`years`、`startIndex` / `limit` 真的有過濾；排序鍵除了劇集庫的 `DateCreated`（值的順序剛好等於名稱順序，證明不了）、`OfficialRating`（只驗到升降冪互為反序）與 `Random` 之外，都驗到照值排序（電影庫的 `DatePlayed` 是 M1.5 票 06 補驗的）；`sortBy`、`sortOrder`、`genres`、`years` 各有一份錄製給契約測試（票 06）。**`searchTerm` 是名字裡的任一段、不分大小寫**（`show` 與 `SHOW` 同樣 3 部、`lpha` 找得到 Alpha Show），照權限過濾，而且照樣照 `sortBy` 排、不換成相關度；參數名打錯（`search=`）被靜默忽略（2026-09-24 在 12.1.0 實測，M2 票 14，研究 §3.1 的表、錄製 `items.tv.series.search.json`）。沒有值的排在升冪最前；劇集的分級照高低（`TV-G < TV-PG < TV-14 < TV-MA`）不是照字串。`sortBy=SortName` 與不帶 `sortBy` 回的順序相同；`enableImages=false`、`enableUserData=false` 真的拿掉 `ImageTags` 與 `UserData`，而 `enableTotalRecordCount=false` 在不帶 `limit` 時照樣回 `TotalRecordCount`（M1.5 票 03 加錄的 fixture）。【實測 12.1.0】
- **選季選集**：`/Shows/{id}/Seasons?userId=` 與 `/Shows/{id}/Episodes?userId=&seasonId=`（jellyfin-web 詳細頁的查法，會套權限）。§20.1 的「10.11 第一次掃描後回 0」**在 12.0.0 沒有重現**（一次性容器：掃完當下、兩分鐘後、第二次掃描後都對）；10.11 沒有重測，那一條仍成立，後備是媒體庫遞迴查詢照 `Path` 分群（三版都驗過）。
- **圖片不需要驗證**：`GET /Items/{id}/Images/{Primary|Backdrop|Thumb}` 匿名 200，請求帶 `Origin` 時回 `Access-Control-Allow-Origin: *`；縮放用 `fillWidth` / `fillHeight` / `quality` / `format=Webp`。`tag` 只是快取鍵（錯的也回圖），URL 要帶 DTO 的 `ImageTags` 才會在換圖時失效。瀏覽器直連的前提是連得到 Jellyfin（與深連結同一個主機），HTTPS 的 Berth 配 HTTP 的 Jellyfin 是 mixed content（§19 已定由 Berth 代理）。
- **經 Berth 代理的圖**（M1.5 票 04，研究 §6.1，12.1.0 實測）：2:3 的原圖帶 `fillWidth=342&fillHeight=513` 回 342×513；**不帶 `format` 時照 `Accept` 挑格式**，Berth 的 httpx（`*/*`）拿到 JPEG、瀏覽器的 `Accept` 拿到 WebP，所以代理固定送 `format=Webp`；`quality=90` 約 23 KB，`quality=96`（jellyfin-web 的值）是它的兩倍多。**Jellyfin 自己存縮好的圖**（`/config/cache/images/resized-images`，同一張第二次從約 250 ms 掉到 25 ms），所以 Berth 端不另存。`/Items` 帶 `enableImageTypes=Primary&imageTypeLimit=1` 時連 `ImageBlurHashes` 一起回。
- **標為未看會清掉 `PlayCount` 與 `LastPlayedDate`**，復原不了原本的次數與時間。**對 Series / Season 標記會遞迴到底下每一集**：標已看把看到一半的位置歸零，標未看連之前單獨看過的集一起清掉；對季只動那一季。**遞迴的結果只有清單端點讀得到**（M1.5 票 11 的 e2e）：一集的 `UserData` 在 `/Items/{集}?userId=` 用的是 provider 導出的 `Key`、在 `/Shows/{劇}/Episodes?userId=` 與 `/Items?ids=` 用的是 item id，對整部劇標記之後前者仍回 `Played=false`（單集自己標記時兩邊都會更新）。Berth 讀集一律走 `/Shows/{id}/Episodes`，與寫入那一側一致。【實測 12.1.0】
- **由 TMDB id 找作品**：`/Items` 沒有 provider id 過濾參數（猜的參數名都被忽略），但有 `hasTmdbId`。`GET /Items?userId=&recursive=true&includeItemTypes=Series,Movie&hasTmdbId=true&fields=ProviderIds` **不帶 `parentId`** 就會套權限，在 Berth 端比 `ProviderIds.Tmdb`；同一個 TMDB id 在沒權限的媒體庫裡的那一份不會回來。已知 item id 時用 `/Items/{id}?userId=` 驗可見性（研究 §10）。【實測 12.1.0】
- **jellyfin-web 卡片上的觀看標記**（M1.5 票 05，研究 §7.1，讀 v10.11.11 原始碼）：劇集只要 `UnplayedItemCount` 非 0 就畫集數（沒開始看的也畫），否則 `Played` 或 `PlayedPercentage >= 100` 畫勾；進度條只給影片（`MediaType=Video`），劇集沒有。已看切換兩個方向都不確認，切換之後就地改那一格、不重抓。Berth 的判定照它（`services/watch.py`），但標為未看先確認（上一條：復原不了）。【原始碼】
- **繼續觀看與下一集**（M1.5 票 07，研究 §7.2）：jellyfin-web 首頁兩列（v10.11.11 `resume.ts` / `nextUp.ts`）一次取 12 / 24 項（桌機的 overflow 版），`imageTypeLimit=1`、`enableImageTypes=Primary,Backdrop,Thumb`；NextUp 另送 `enableResumable=false`（**伺服器預設是 `true`**，不送的話看到一半的集兩列都出現）與 `nextUpDateCutoff=今天 − maxDaysForNextUp`（使用者設定，預設 365；伺服器預設沒有截止日）。NextUp 只挑最後觀看日期在截止日之後的劇、每部取最後看過那一集之後還沒看的第一集，照劇的最後觀看日期新的在前；Resume 照 `DatePlayed` 新的在前（v12.0 原始碼）。`mediaTypes=Video`、`parentId`、`nextUpDateCutoff` 各有一份對照錄製證明伺服器真的過濾（12.1.0，`useritems-resume.watching*.json`、`shows-nextup.watching*.json`）；`enableResumable` 的效果只讀原始碼。**橫卡取圖**（`cardBuilder.getCardImageUrl`，`preferThumb`、`inheritThumb` 預設成立）：自己的 Thumb → `SeriesThumbImageTag` → `ParentThumbItemId` / `ParentThumbImageTag` → 自己的 `BackdropImageTags[0]` → `ParentBackdropItemId` / `ParentBackdropImageTags[0]`（只有集）→ 自己的 Primary → 劇與季的 Primary……；上層借來的那幾格只在 `enableImageTypes` 開了那一種時才回（v12.0 `DtoService`），Thumb 先找季、劇自己有就換成劇的，Backdrop 取往上找到的第一個。**12.1.0 沒有回 `SeriesThumbImageTag`**，劇的 Thumb 在 `ParentThumb*` 那一對。Berth 照這個順序取到集自己的 Primary 為止（電影不取 Primary：2:3 海報填進 16:9 只剩中間一條）。【原始碼 + 實測 12.1.0】
- **劇集詳情頁：這部劇的下一集**（M1.5 票 08，研究 §7.3）：jellyfin-web 劇集頁的 Next Up 只送 `SeriesId` 與 `UserId`，其餘吃伺服器預設。帶 `seriesId` 時**截止日不套用**，`enableResumable` 預設 `true`——候選那一集看到一半就照樣回它與它的位置；「最後看過」是已標記看過的最大季集號，取它之後第一個還沒看完的，Specials 與缺片不算；**從沒看過回 S01E01**，看完了回空。12.1.0 三種情況各錄一份（`shows-nextup.series*.json`）。jellyfin-web 的主按鈕文字只看那一項自己的 `PlaybackPositionTicks`，劇集頁因此幾乎永遠是「Play」；它的季頁把集列成清單，集沒有自己的 `Primary` 時退回劇的海報。`/Items/{id}?userId=` 沒有 `fields` 參數，不必要就帶 `ProviderIds` 與 `UserData`（v12.0 `new DtoOptions()`，12.1.0 錄製）。Berth 照 §10 找作品、以 `/Items/{id}?userId=` 確認看得到之後才問這部劇的 NextUp（帶 `seriesId` 不套權限）。【原始碼 + 實測 12.1.0】
- **沒有直接開始播放的網址**（§12 維持）：三版的 `#/video` 都不吃 item id，「播放某一集」只能深連結到那一集的 `#/details?id=`。
- **帳號狀態**：Jellyfin 停用帳號之後，**API key 代讀這位使用者的 `UserViews`、`/Items`、Resume、NextUp、Seasons 照常回資料，`UserPlayedItems` 照常寫入**；只有他自己的 token 回 401、重新登入回 403。`GET /Users/{id}` 讀得到 `Policy.IsDisabled` 與 `EnabledFolders`（與 `UserViews` 的 `Id` 同一種格式）。所以 Berth 要自己讀 `Policy`（§19 已定）。【實測 12.1.0】**刪除的帳號**（M2 票 11，[`docs/research/large-library.md`](research/large-library.md) §4）與停用不同：API key 代讀他的**每一支都是 404**——`GET /Users/{id}` 回 JSON 字串 `"User not found"`，`UserViews`、`/Items` 回 `Error processing request.`，Resume、NextUp、`/Items/{id}`、`POST /UserPlayedItems` 回 problem details（沒有寫入）；重新登入 Berth 是帳密錯。Berth 只把 `Users/{id}` 的 404 當成與停用同一種處置（`UserViews` 的 404 可能是位址設錯，仍是問不到）（刪掉他的每一張 session、401 `account_disabled`，使用者拍板）。【實測 12.1.0】
- **大媒體庫的代價**（M2 票 11，[`docs/research/large-library.md`](research/large-library.md)；1,000 部 × 12 集、全部由 Berth 經手，Docker Desktop 上的量級）：整份清單（`library_index`）1,000 部 318 KB、p95 35 ms；不帶 `parentId` 的 `hasTmdbId` 反查 303 KB、p95 39 ms；**帶整份 `MediaSources` 的集清單 12,000 列 25.9 MB、p95 5.0 s**（不帶是 8.3 MB、0.55 s），約 8 萬集會撞上 Berth 30 s 的 Jellyfin 逾時，分段取（`startIndex` + `limit`）總時間不減、只讓單一請求變短；**Series 的觀看紀錄很貴**：整份清單打開 `enableUserData` 從 31 ms 變 1.95 s（`UnplayedItemCount`），牆的一頁 100 部帶觀看紀錄 250 ms，`ids=` 只取 50 部 150 ms、200 部 450 ms、500 部回 **414 URI Too Long**。plan §11.3 決定 2 的門檻：`GET /inventory/{id}` p95 修正前 3.4 s（Berth 的分組是二次方，不是 Jellyfin）、修正後 0.66–0.68 s；對帳一輪 27–31 s（Jellyfin 那一方 25–29 s，其中 Jellyfin 的回應只占 4.5 s）。不做快取、不做分段取。【實測 12.1.0】

### 20.10 Sonarr 怎麼替一集組查詢（2026-09-19 查證）

缺集一鍵搜（M1.5 票 10）要決定「缺一集時拿什麼字去問」，採用的是 Sonarr 的慣例：

- Sonarr 的 Newznab / Torznab 請求把季集放在**結構化參數**上（`&season=<n>&ep=<n>`），標題只放 `q=`。
- **只有動漫的絕對編號是接在關鍵字後面的**：`&q={NewsnabifyTitle(queryTitle)}+{searchCriteria.AbsoluteEpisodeNumber:00}`
  ——絕對編號補零到兩位，與標題之間一個空白。
  【來源：`Sonarr/src/NzbDrone.Core/Indexers/Newznab/NewznabRequestGenerator.cs`，develop 分支，2026-09-19 讀】
- Berth 的兩個實作都只送 `q=`（Prowlarr 的 REST 與 Torznab 的 `t=search`，plan §8.4「分類碼不送」同一個理由：
  各站對結構化參數的支援與映射不一致，而 Berth 打的是公開站），所以季集一律進關鍵字：整季 `S03`、
  單集 `S03E05`、有絕對編號的 `26`。

### 20.9 Jellyfin 12（2026-09-15 查證）

全文、原始碼行號與實測紀錄見 [`docs/research/jellyfin-12.md`](research/jellyfin-12.md)。實測對象是一次性的 linuxserver `12.0ubu2604-ls48`（12.0.0）與 `12.1ubu2604-ls49`（12.1.0），跑完即刪；10.x 的對照引 §20.6 與 `m0-experiments.md`。

- **版號**：12.0 就是原本的 10.12，只拿掉永遠不變的 `10`（2026-09-08 發佈；12.1 在 2026-09-15 發佈）。【文件】
- **升級是單向的**：10.10.7 或任何 10.11.x 可直接升；資料庫改動讓降級只能靠備份還原。第三方插件要對 .NET 10 重建，10.11 的插件在 12 載入不了。升級後要完整掃描一次，自動分組的版本才會回來。item id 的算法（`MD5(型別全名 + 路徑)`）在 10.11.11 與 12.1 逐字相同，所以一般 Movie / Episode 主條目升級後 id 不變；型別被修正的條目（含自動分組的次要版本）會換 id，缺檔與孤立的條目會被刪。沒有做升級前後逐筆比對的實測。【文件 + 原始碼】
- **從 10.11 升級的阻力**（2026-09-15 補查，`jellyfin-12.md` §4）：
  - **遷移會失敗**：12.0 發佈一週內仍有 12 條遷移、啟動、媒體庫變空的 open issue，多數沒有維護者回應，其中 #17862 是 12.1 啟動不了。內建的遷移前備份只保護資料庫。
  - **舊客戶端與整合要升級才能用**：舊式驗證關閉之後，Jellyfin for Kodi 要 v2.0.0 以上、Seerr 要 v3.0.0，Sonarr / Radarr 要最近的版本。Ombi 與 Jellyfin Vue 的播放仍然壞著。暫時打開舊式驗證要手改 `system.xml` 的 `EnableLegacyAuthorization`，後台沒有開關，官方也預告下一個大版本移除。
  - **升級前後要做的事**：第三方插件要先移除；只差大小寫的兩個使用者名稱會讓遷移失敗；全域字幕設定改到各媒體庫。
  - **一鍵管道沒到齊**：binhex（unRAID）與 QNAP 社群套件還停在 10.11.11；SynoCommunity、TrueNAS 是 12.0；Debian 11 / Ubuntu 20.04 的 apt 已經沒有 12。Docker `latest`、官方 apt、Windows / macOS installer 已是 12.1。
  - **保留的資料**：帳號、API key、觀看紀錄保留；armhf 在 10.11 就沒有官方建置，12 沒有新增 CPU 架構門檻。
  - **反向推力**：Kotlin SDK 1.9.0 已把最低伺服器版本拉到 12，Android 與 Android TV 換上它之後，新版 app 可能反過來要求伺服器是 12【推論】。
  - 【文件 + 原始碼 + 官方 issue】
- **劇集原生多版本**（[PR #16828](https://github.com/jellyfin/jellyfin/pull/16828)、官方文件 [`_video-multiversion.md`](https://github.com/jellyfin/jellyfin.org/blob/187351cd69c532a833c9ed57de036297012f5e9e/docs/general/server/media/_video-multiversion.md)）：同一個季資料夾裡解析出同一個 `S/E` 的檔案，併成同一集的多個 MediaSource。
  - **分組鍵只有季號與集號，不含集名與結束集**：`S01E03-E04` 與 `S01E03` 同季時被當成同一集的兩個版本，第 4 集從集列表消失（實測；本系統的處理見 §7.8）。
  - 12.1 起季號與集號都要解析得出才分組（[PR #17890](https://github.com/jellyfin/jellyfin/pull/17890)）。
  - 本系統的命名在 12.0.0 與 12.1.0 不裝插件就合併，新版本在路徑通知後 100 秒內併入，外掛字幕掛在對的版本上。
  - 版本名是去掉各版本檔名共同前綴後剩下的部分；順序依解析度降冪，再依檔名。
  - 電影規則不變：檔名仍要以資料夾名開頭，分隔符多接受 `_`、`.`、`[`。中文組名的標籤是純 tag。
  - 【實測 + 原始碼 + 文件】
- **MergeVersions**：manifest 有 `12.0.0`（`targetAbi 12.0`），不指定版本的安裝在 12.x 會挑到它。但它在 12.x 上對本系統的樹是空跑：log 是 `Found 5 episodes and 0 duplicate episode groups`，合併前後來源數與名稱不變。原因是原生分組的次要版本帶 `PrimaryVersionId`，一般查詢會濾掉它們，插件湊不成一組。它的分組鍵不看資料夾與媒體庫，會跨媒體庫合併【原始碼推論】。【實測 + 原始碼】
- **本系統用到的 24 支端點**在 12.0 / 12.1 都在、授權政策相同，以本系統的 adapter 跑完 plan §9.4 整段。例外兩條：
  - `POST /Startup/User` 在第一個使用者已有密碼時回 **403**（[PR #17369](https://github.com/jellyfin/jellyfin/pull/17369)）。精靈第 3 步做完、後面某步失敗、Jellyfin 沒重啟時按重試，會一直卡在這裡（M1 票 14b）。【原始碼 + 部分實測：精靈未完成時匿名送的那條只讀了原始碼】
  - `POST /Startup/Configuration`、`GET /Startup/User`、`POST /Startup/RemoteAccess` 在 12.x 的 OpenAPI 標 deprecated，現在還能用。Jellyfin 的政策是至少標滿一個大版本週期才移除，所以 13.0 發佈前要換成設定端點（替代端點的欄位【未查】）。【實測 + 文件】
- **舊式驗證預設關閉**，連既有安裝也由遷移關掉：`X-Emby-Token`、`X-Emby-Authorization`、`?api_key=` 回 401。本系統用的 `Authorization: MediaBrowser …, Token="…"` 不受影響。【實測 + 原始碼】
- `GET /Items` 帶 `includeItemTypes` 而沒指定 `recursive` 時預設遞迴（2026-09-17 在 12.1.0 實測，§20.8），本系統一律明確帶 `recursive=true`。`POST /Library/Media/Updated` 背後的 `FileRefresher` 一行沒改，所以「空的媒體庫收到路徑通知無效」（§20.1）仍成立。【原始碼 + 前半句實測 12.1.0】
- **linuxserver image**：
  - tag 變成 `12.0ubu2604-ls48`、`12.1ubu2604-ls49` 這種形式。
  - `latest` 已是 12.1。
  - 舊 tag 會保留，另有跟著同一版號重建的 `version-12.1ubu2604`。所以 `m0-experiments.md` 當時寫的「只保留最新 tag，釘不了版本」不成立。
  - Dockerfile、`/config`、8096、`PUID` / `PGID` 都不變。
  - 【實測 + 原始碼】
