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

一個自託管的「媒體取得與入庫協調器」：把 Prowlarr 搜尋或 RSS 命中的 torrent 送到 qBittorrent，下載完成後解析內容、比對 TMDB metadata、以硬鏈接入庫到 Jellyfin 媒體庫，並維護一份可追溯、可修復的入庫帳本。

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
| 索引站接入 | 只支援 Prowlarr（套件內或既有；為什麼見 [ADR-0001](adr/0001-indexer-manager-prowlarr-only.md)） | 搜尋走 Prowlarr REST（`GET /api/v1/search`），加站、移除、測站也走它的 REST。開箱即用套件預設打包 Prowlarr（§16.3）。Jackett 與單站 Torznab 網址沒有路徑，要先裝 Prowlarr |
| Metadata | TMDB | 第一階段唯一的 provider，見 §10 |
| 同一集多版本的合併顯示 | Jellyfin（12 起原生合併；本系統只支援 12 以上） | 本系統只保證命名讓 Jellyfin 能合併；不裝 MergeVersions（§7.7、[ADR-0002](adr/0002-jellyfin-12-minimum-pinned-image.md)） |

刻意不做的事（第一階段）：品質檔案自動升級替換（Sonarr 的 quality profile upgrade）、內嵌播放器、多人審批、非影片媒體。巡檢與通知、AI 核心、側面板與外部對話排在 M4–M7（§14、§17）。見 §18。

### 1.3 參考的成熟產品與採用的慣例

| 面向 | 借鑑 | 採用的慣例 |
| --- | --- | --- |
| 目錄與硬鏈接 | TRaSH Guides、Sonarr/Radarr | 單一掛載根 `/data`；「qBittorrent category = 一個目標媒體庫」 |
| 探索頁與帳號 | Seerr（Jellyseerr 與 Overseerr 的合併專案） | TMDB 媒體牆；用 Jellyfin 帳號登入，Jellyfin 管理員即本系統管理員；深連結格式 |
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
| Prowlarr | torrent 搜尋 | REST API（`/api/v1/search`、`/api/v1/indexer*`、`/api/v1/system/status`）；搜尋與由 Berth 自動加入索引站（§16.3）都走它，沒有 Torznab 端點 | 搜尋結果短暫快取 |
| qBittorrent | 下載 | Web API v2：新增、分類、輪詢 `sync/maindata`、檔案清單、刪除、搬移 | 無 webhook，用輪詢；活躍時短間隔、閒置時退避。支援下限 4.4（API 2.8.4），adapter 依 `webapiVersion` 切換 `paused`/`stopped` 等改名參數（§20.2） |
| Jellyfin | 媒體庫與播放 | 伺服器 API key 做媒體庫操作；使用者以 Jellyfin 帳號登入本系統 | 讀 VirtualFolders 得到媒體庫與路徑；針對路徑觸發掃描；用路徑反查 item id |
| TMDB | metadata | REST v3，本地快取 | 探索、搜尋、季集結構、別名與翻譯、episode groups |

所有外部呼叫都經由一層 adapter，adapter 的介面以本系統的名詞（§2）表達，不外洩第三方資料結構到核心邏輯。這也是未來替換 Prowlarr、Emby 或其他 provider 的邊界。

---

## 4. 路徑模型

### 4.1 三層路徑【決定】

```
/data/torrent/incomplete/<route-slug>/<torrent 內容>     qBittorrent category 的未完成目錄（downloadPath）
/data/torrent/complete/<route-slug>/<torrent 內容>       qBittorrent category save path
/data/library/<Jellyfin 媒體庫路徑>/<Media 資料夾>/...     由 Jellyfin 推導，不讓使用者重填
```

- `incomplete` 與 `complete` 的根目錄固定在 `/data/torrent/{incomplete,complete}`，沒有 API、UI 或環境變數改它；要換宿主位置，改 `DATA_ROOT` 掛到哪裡。
- 未完成目錄開在 Berth 的每個 category 上（`downloadPath`），不寫 qBittorrent 的全域 `temp_path`：既有 qBittorrent 不必改全域設定，下載中的檔也不會落在 complete 那一側。全域關著也生效、開著時分類的贏（§20.2）。
- `complete/<route-slug>` 對應一個 qBittorrent category；category 名稱預設 `berth-<route-slug>`，可改。
- `route-slug` 由媒體庫名稱算：換掉路徑不收的字元、空白換成 `-`、小寫，中日文照留（「TV Shows」→ `tv-shows`）。依舊算法建的 Route，slug 可能帶空白；它保留自己的 slug 與分類，不改名——改分類路徑會搬走 torrent（§20.2）。
- library 路徑一律從 Jellyfin `VirtualFolders` 讀取，使用者只做「選擇」，不做「輸入」。

### 4.2 為什麼 incomplete / complete **不**鏡像 library 結構【決定】

不採用 `complete/<library>/<media title>/<torrent name>`（讓人在檔案系統就能看出哪個 torrent 屬於哪部作品），理由：

1. 送單時對「這是哪部作品」的判斷可能是錯的（RSS 誤判、選錯季），之後修正就得搬 torrent 資料，做種中搬移是最容易出事的操作。
2. 目錄名會鎖死在送單當下的標題，TMDB 改名、使用者改匹配都會讓目錄說謊。
3. Sonarr/Radarr 這類成熟產品都用「category 一層、扁平」，整個生態（TRaSH Guides、qBittorrent 分類）都以此為前提。
4. 「這個 torrent 是哪部作品」由本系統的 Job 頁與帳本回答；檔案系統層面用 `find -samefile` 也能反查。
5. incomplete 是暫態，qBittorrent 完成時自行從分類的未完成目錄搬到 save path；鏡像它沒有任何收益。

替代：Job 頁提供「開啟 complete 目錄」與「顯示所有硬鏈接目標」，滿足「我想知道這堆檔案是什麼」的需求。

### 4.3 一個 Jellyfin 媒體庫有多個路徑【決定】

- Library Route = （Jellyfin 媒體庫, **一個**寫入目標路徑）。
- 建立 Route 時從媒體庫的路徑選一個作為寫入目標。
  - 既有 Jellyfin **預選 Berth 路徑**（「加入 Berth 路徑」加的那一條，還沒加的也是——按下「建立並檢查」時才加）：那一條本來就是為 Berth 加的，其餘路徑是使用者自己的。
  - **只有一個路徑時也不自動選它**：旁邊的說明叫人別讓 Berth 寫進既有的資料夾，預設選它方向相反；要寫進去，使用者自己選。
  - 套件內的 Route 由 Berth 建的媒體庫導出，不用選。
- 該媒體庫的其他路徑視為唯讀：用來辨識「已存在的媒體」與偵測孤兒，不寫入。
- 同一個 Jellyfin 媒體庫可以建立多個 Route（例如兩顆碟各一個 Route），但每個 Route 有自己的 category 與 complete 子目錄，硬鏈接檢查各自獨立。
- Route 的 slug 與寫入目標建立之後不可改；刪除是明確、要二次確認的動作，被 Job 或帳本引用時拒絕，出路是停用。

### 4.4 硬鏈接能力驗證【決定】

- 每個 Route 建立時與每次啟動時執行：在 `complete/<route-slug>` 建暫存檔 → 真的呼叫 `link()` 鏈接到目標路徑 → 比對 inode 與 device → 刪除。失敗即 Route 標記為不健康，拒絕送單。只比 `st_dev` 不夠（同一檔案系統掛兩次、btrfs 子卷、ZFS dataset、mergerfs 都會 `EXDEV`，§20.2），所以一定實際鏈接一次。
- 也檢查：
  - 目標路徑對本系統可寫、qBittorrent 回報的 save path 在本系統看得到。
  - **反過來 qBittorrent 讀得到本系統寫進分類路徑的探測檔**（探針 torrent 校驗到 100%，§20.2）。
  - Jellyfin 以 `Environment/ValidatePath` 確認看得到探測檔。
  - category 為 autoTMM 模式，且帶自己的未完成目錄。
- **硬鏈接失敗不退回複製**（與 Sonarr 不同）：複製會讓刪除範圍與空間估算失真，違反「避免複製檔案」的需求。
- Docker 部署要求三個容器（qBittorrent、Jellyfin、本系統）以**相同容器路徑**掛載同一個宿主父目錄（TRaSH 的單一掛載慣例）；容器路徑固定是 `/data`：Berth 的 incomplete / complete 根目錄在 `/data/torrent/…`、媒體庫根目錄在 `/data/library`，都沒有設定可改，所以既有服務也要把共用父目錄掛在 `/data`（§16.4）。第一階段不做 remote path mapping，設定精靈直接驗證「你看到的路徑 qBittorrent 與 Jellyfin 也看得到」。
- 已知限制要寫進使用者文件（README 與 `docs/guide/requirements.md`）：Docker Desktop（Windows/macOS）bind mount 的硬鏈接支援與 mergerfs / 跨 dataset 情境，見 §20 的查證結果。

### 4.5 檔名與目錄安全

- Media 資料夾名在**第一次真的通向磁碟那一刻**決定並寫入 DB：
  - 手動送單成功時：有人在場，要一次明確確認。
  - RSS Series 綁定到作品時：RSS 自動綁定（§15），那一刻不一定有人在場，靠審核與「重新命名」補。
- 不拖到入庫，那時是背景迴圈在跑，沒有人看著。在那之前它跟著 TMDB 的標題走，畫面上是「將會是」的預覽。凍結之後 TMDB 改名不自動改資料夾（避免 Jellyfin 重掃與帳本漂移）；提供「重新命名」的顯式動作。
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

- **metadata_ready 做預先計劃（pre-plan）**：一拿到檔案清單就用規則跑一次 Plan，不動檔案。目的：在下載完成前就發現「這個 torrent 根本不是那一季」或「全部是 OST」，讓使用者可以立刻取消。成本極低。
- **completed 的判定**：qBittorrent `progress == 1` 且 `completion_on > 0` 且 state 不是 `moving` / `checking*`（temp path 搬到 save path 期間會是 `moving`，§20.2）；再以 `stat` 確認每個檔案存在於 save path 下。`priority == 0`（不下載）的檔案不進 Plan。
- **completed 觸發正式 planning**：此時可讀 mediainfo（時長、音軌、內封字幕語言），信心明顯高於只看檔名。
- **planning 的產出是 Plan，不是副作用**。高信心 Plan 自動進 importing；否則進 review。
- **importing 逐檔寫帳本**：每成功鏈接一個檔案就寫一筆 Ledger Entry。中途失敗可重跑，已完成的檔案跳過（以目標 inode 判定）。
- 入庫完成後：以 `POST /Library/Media/Updated` 通知變更路徑 → 延遲反查 Jellyfin item id 寫回帳本 → 媒體庫頁可顯示「可播放」。反查沒有路徑篩選 API（§20.1），做法是：在該媒體庫列出 Series 並以 `ProviderIds.Tmdb` 或路徑比對，再列該 Series 的 Episode 以 `Path` 比對；找不到就排程重試，多次失敗記為 Issue。

### 5.2 事件（Timeline）

每個 Job 的所有轉換都寫 Event，至少包含：

`created(trigger, user, media, route)`、`submitted(client, category, save_path)`、`metadata_received(file_count, total_size)`、`preplan(result, confidence)`、`progress(每 25% 一筆)`、`completed`、`plan_generated(engine=rules|ai, confidence, model, tokens, cost)`、`review_required(reason)`、`review_decided(user, changes)`、`linked(file, target)`、`link_failed(file, error)`、`jellyfin_scan_requested(paths)`、`jellyfin_item_resolved(count)`、`issue_detected(type)`、`deleted(links, sources, torrent, purged, freed, unmanaged)`。

- `jellyfin_item_resolved` 是**一筆 Job 一行、說找到了幾個**（`count`），不是逐檔帶 item id：一季 24 集的時間線不該被 24 行「找到了」淹沒，item id 已經寫在帳本那幾列上（`services/resolver.py`）。
- 它的意思是「這一筆的正片全部在 Jellyfin 認出來了」，一筆 Job 只寫一次：`count` 是整筆的正片數；之後的重新反查找到的不再寫，有一集放棄了就不寫。M4 通知的「可以看了」讀的就是它。
- `deleted` 說的是真的做掉了什麼而不是勾了哪幾格（§9.2），誰按的在事件的 `actor`。

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

`title_candidates[]`、`season`（顯式）/`season_end`（多季一包 `S01 + S02` 的最後一季）、`episode`/`episode_range`、`absolute_number`、`version`（v2/v3）、`group`、`source`（BD/WEB/DVD/HDTV/Remux）、`resolution`、`subtitle_langs[]`、`subtitle_kind`（hardsub/softsub/external/unknown）、`edition`（Remaster/Director's Cut/Uncut/…）、`year`、`air_date`（檔名寫的播出日，§6.4）、`season_hint_from_folder`、`special_kind`（SP/OVA/OAD/Movie/NC）。

編碼、位深、音軌不從名字解析：沒有消費者，留著容易被誤認成「已支援依編碼挑版本」。檔案本身的這些屬性由 mediainfo 量（plan §8.7）。

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
   - 只有集號（動漫常見）→ TMDB 只有一季而且那一集存在 → 該季；否則視為 **絕對編號**，TMDB episode group（Absolute 類型）與各季累計集數兩種換算各產一個候選，換算過程寫入理由。
   - 韓劇常見 `E01` 無季 → 視為 Season 1（多數韓劇單季）並驗證集數。

   **絕對編號的信心看證據，不看 Route**：預設 medium，遇到任一條降到 low 送審核並附理由。
   1. **集號 ≤ 第一個正規季的集數**：這個數字同時讀得成「第一季第 N 集」與「後面某季從 01 重數的第 N 集」，檔名分不出來（Erai-raws《死神》相剋譚 01–14 是後者）。§20.4 量過這條擋下的多半其實是第一季，但「標題有認不出的多餘字」分不開兩者，所以仍降 low。
   2. **檔名帶播出日，而換算出的那一集在 TMDB 上不是那一天播的**：日期是明說的，換算是推論的；沒有容忍範圍，因為日播的劇差一集就是差一天。

   **以發佈時間推測「虛擬季」**（AutoBangumi v3.2 的做法）：各讀法換算出的那一集裡，只有「某一輪從 01 重數」那一個是發佈前六週內播的，就照那一輪數，至多 medium。
   - 它分得開上面第 1 條分不開的兩種讀法；季號來自篇章名、而 TMDB 把那一季的好幾輪放在一起時也適用（明說的季號照字面）。
   - 沒有一種讀法剛播（BD、補檔、重播）或不只一種都是分不開，照舊。
   - 推測出的集數照樣過播出日比對，但那一道幾乎擋不到它——推測錯了靠 medium 的 audit 與第一批審核（plan §4.4、`docs/research/profile-effect.md` §4）。

   已知陷阱：TMDB 與 TVDB 近年都把 split-cour 動漫併成單季連續編號，而字幕組每個 cour 從 01 重數（§20.3）。RSS Series 因此必須帶得了季號與 offset（§15）；用 Mikan 番組的開播日對 TMDB 播出日給 offset 建議值是候選、未排程，做法與觸發條件見 §15〈offset 建議〉。
4. **批次一致性**：同一 torrent 內所有影片以同一種模式解析成功、集號連續、數量與 TMDB 該季集數吻合 → 大幅加分；只有少數檔案解析失敗 → 那些檔案進 review，其餘照常入庫（不因為一顆 NCOP 卡住整季）。
5. **重複與衝突**：
   - 兩個檔案會被寫到**同一條目標路徑**（§7.1 / §7.2 的檔名已經含 tags）→ 標記衝突進 review，兩個都不自動入庫——誰對誰錯解析器答不出來，而蓋掉是不可逆的。
   - 與帳本既有版本同 tags → 標記 `duplicate`（§7.8）。
   - 比路徑而不是比（季, 集, tags），因為那正是「會不會蓋掉對方」的定義；而**同一集不同 tags 的檔案本來就該並存**（§7.7）：简繁分軌、1080p 與 720p 同包都是常態。

### 6.5 信心與門檻【決定】

- 不用單一浮點數黑箱。每個 Plan item 帶 `confidence ∈ {high, medium, low}` 與 `reasons[]`。
- **high**：Media 由上下文或「標題 + 年份精確命中」決定；每個影片檔都有顯式季/集或資料夾提示；季/集都存在於 TMDB；無衝突；批次一致性通過。
- **medium**：Media 確定，但季/集靠推論（絕對編號換算、air_date offset、標題季名比對），或批次一致性只部分通過（少數檔案例外）。絕對編號換算要**沒有反證**才是 medium（[ADR-0003](adr/0003-remove-route-profile.md)）：集號超過第一季的集數，而且檔名若帶播出日就要與換算出的那一集相同（§6.4）。
- **low**：Media 不確定、有衝突、影片數量與 TMDB 集數明顯不符，或絕對編號換算有反證（§6.4 的兩條）。
- **high 與 medium 都自動入庫**（所有 Route 預設開啟；可在 Route 上關閉 medium）。medium 入庫的檔案帶 `audit` 旗標，在審核佇列以「已入庫待確認」列出，一鍵撤銷（拆鏈接、清帳本）或確認。硬鏈接讓撤銷幾乎零成本，這是敢於自動入庫 medium 的前提。
- low 進 review，並在啟用 AI 時觸發 §6.10。
- 取捨：medium 自動入庫會提高誤入庫率。§6.9 的 benchmark 必須分開報告 high 與 medium 的誤判率，若 medium 誤判率明顯高於 high，回頭收緊 medium 的定義而不是關掉自動入庫。

### 6.6 多集檔、合集、多季

- 單檔多集（`S01E01-E02`、`01-02`）→ 目標檔名用 Jellyfin 支援的 `S01E01-E02` 形式，帳本一筆對多集。
- 一個 torrent 多季（子資料夾分季或絕對編號連續）→ Plan 逐檔決定季，允許一個 Job 寫入同一 Media 的多季。
  - 發佈名寫兩個季號（`S01 + S02`、`S1-S2`、`Season 1 + Season 2`，兩邊都要有季的前綴）讀成多季一包：`season`–`season_end`、`release_kind = batch`，所以 RSS 的「合集預設排除」擋得到。
  - 它說不出其中一個檔案是哪一季，檔名沒寫季號時不從發佈名補。
- 一個 torrent 多部作品（系列合集）→ 第一階段不自動處理：所有影片對不到上下文 Media 的檔案進 review，使用者在 review 時可把檔案指派給其他 Media。
- 分割光碟 `CD1/CD2` 電影 → 第一階段進 review。

### 6.7 外掛字幕與字型

匹配順序：

1. 檔名主幹與某影片完全相同（去掉語言後綴後）→ 該影片。
2. 位於 `Subs/` `字幕/` **或語言資料夾**（`繁體/`、`简体/`）且檔名含集號 → 以集號對應影片。
   - 語言資料夾算同一種證據：它一樣說了「這一格底下的東西是側掛字幕」。
   - **要有那個資料夾**——光有一個數字不算，一包裡任何帶數字的檔案都會對到某一集。
   - 同一集對到兩個以上的影片時不選：多版本並存時這一份字幕是誰旁邊的那一個，路徑沒有說。
3. 從檔名後綴或資料夾名判斷語言：`.tc` `.cht` `.zh-Hant` `繁體/` → zh-Hant；`.sc` `.chs` `.zh-Hans` `简体/` → zh-Hans；`.jp` `ja`；`JPSC` / `JPTC` → 雙語。ISO 639-2 式的 `.Cht` `.Chs` `.Jpn` `.Eng` 也認得（真實語料 `tv/gto-2026-magicstar`）。三者都沒說時才看檔名裡的詞典；**torrent 名不算**——`附官方日英简繁中字幕` 說的是這一包有四種字幕，不是這一個檔案有四種。
4. 對不到影片的字幕 → Unmatched。影片自己沒有入庫（Unmatched / review）時字幕跟著它走，人在佇列裡看到的才是一對。

輸出：以 Jellyfin sidecar 慣例命名 `<影片檔名主幹>.<標題>.<語言碼>.ass`。Jellyfin 無法用語言碼區分繁簡（§20.1），所以語言碼一律 `zh`，繁簡放在自由文字標題欄位，用 §6.8 的 token：`….CHT.zh.ass`、`….CHS.zh.ass`、日文 `….ja.ass`、英文 `….en.ass`、預設軌加 `.default`（旗標排在語言碼**之前**：`….CHT.default.zh.ass`，§20.6 實測）。目前沒有字幕語言偏好設定，決定不了哪一軌是預設，所以不產生 `.default`（plan §5）。標題欄位在播放器字幕選單的顯示方式列入 §20.6 實測。字型不入庫。

### 6.8 Tag 的保留方式【決定】

- 所有 tag 以**結構化欄位**存在 Ledger Entry 與 Plan item（§6.3 的欄位），檔名只是這些欄位的一種呈現。
- 檔名用固定順序與固定詞彙渲染（英文 token），缺的片段直接省略：

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

目標是「AI native，出錯幾乎不需要人工處理」（§14、[ADR-0008](adr/0008-ai-autonomy-and-optional-ai.md)）。AI 解析是 M5 的第一種 AI 任務。

- **三層漏斗**：規則層（解析器、比對）是主力——免費、確定、有 benchmark 守著；AI 只接規則層的例外；人只處理 AI 交上來的與不可撤銷的。AI 掛掉或超出預算時退回沒有 AI 的行為，系統照樣能用。
- **規則層自己知道沒把握的**（信心 low、Unmatched、目標衝突、RSS Series 待綁定）→ 開一個 AI 任務，而不是直接進審核。
- **規則層有把握卻錯了的**（high / medium 入錯）規則層自己看不出來，靠不花 token 的程式檢查抓（plan §11.4）：
  - **播出日比對**（Feed Item 的發佈時間對換算出的那一集的播出日，抓集數與 offset 算錯——主要的一道）。
  - **片長驗證**（抓預告、SP、合併檔被當成正片這類分類錯誤）。
  - 每日檢查（RSS Series 缺號、同一集意外多份）。
  - **Jellyfin 回驗抓不到集數算錯**：Jellyfin 認集數靠 Berth 取的檔名，錯的集數會原樣抄過去；它只是抓 Jellyfin 那邊意外的保險。
  - 抓到的開 AI 任務：撤銷、rematch、必要時把 offset 寫回 RSS Series 並重算同一 RSS Series 未確認的集數。**不讓 AI 逐筆重看每一次入庫**——那是規則層該做的事，也付不起。
- 輸入（壓縮後）：torrent 名、檔案清單（同模式的檔案只送樣本 + 數量）、規則層的部分解析與理由、TMDB 季集結構（集數、集名、首播日、片長）、命名規則、使用者偏好。不送檔案內容與帳密。
- 輸出：JSON schema 固定的 Plan（逐檔分類、季、集、tags、confidence、理由）。程式做**結構與約束驗證**：集必須存在、不得兩檔同目標、副檔名與分類一致、片長相符；驗證失敗即丟棄並交給人。
- **執行**：通過驗證、且這種任務在自動模式 → 直接套用（入庫可撤銷：硬鏈接，原檔在 complete）；影子模式只記錄 AI 會怎麼做。AI 的結果照樣走上面的程式檢查，不通過的不套用、交給人。
- **修正回流**：人或 AI 的改正寫回結構化的地方（RSS Series 的季號與 offset、標題別名、排除條件），規則層下一次就用得到；改正過的案例進 benchmark 的候選語料，讓例外慢慢變成規則層的常態。
- 快取鍵：`torrent hash + 解析器版本 + prompt 版本`；同一 torrent 不重複付費。
- 每次呼叫記錄 model、tokens、快取命中與估計費用（`ai_runs` / `ai_calls` / `ai_tool_calls`）。不以總花費切斷 AI，沒有月預算上限（[ADR-0016](adr/0016-ai-agent-architecture.md)）；改用防護：每次呼叫的 `max_tokens`、每個任務的往返與 token 上限、同一呼叫重複偵測、背景任務的並發與冷卻、provider 斷路器。花費只做可見與提醒（§14）。
- 花費提醒有兩種（`domain/spend.py`）：
  - 今天的估計費用到了管理員設的每日提醒值。
  - 今天是近 14 天（不含今天）**有用量那幾天**的日中位數 5 倍以上；那樣的日子少於 3 天不比。家用幾天才問一次，沒用的日子算 0 的話中位數常是 0。
  - 費用只用知道的那部分，**所以費用未知的呼叫（有回應、有 token，但查不到價目）提醒看不見**；出錯、沒有回應的呼叫沒有花費可算，不算未知。今天或前 14 天有這種呼叫時，用量頁與側面板明說有幾次沒算進去（未知不當 0）。
  - 提醒出現在用量頁與側面板（只給管理員），不推 Discord。
- 引入時機：§17 的 M5，排在巡檢與通知之後；要在 benchmark 存在之後，才能量化 AI 帶來的增益與誤判。

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

同資料夾內以 ` - <版本標籤>` 區分多版本，這是 Jellyfin 原生支援的多版本方式，不需插件。

- 檔名在 ` - ` 之前必須與資料夾名**完全一致，包含 `[tmdbid-<id>]`**。實測（§20.6）：檔名少了 `[tmdbid-<id>]` 就不是多版本，而是兩部獨立的電影。
- 標籤內含方括號與 `+` 沒有問題，版本選單顯示的就是 `[BD][2160p][CHT+JP][Group]`。
- Jellyfin 對結尾為 `p`/`i` 的標籤依解析度降冪排序、其他字母排序（§20.1，已實測）。

### 7.3 Extras【決定】

NCOP/NCED、PV、CM、Menu、預告、花絮等**可辨識**的非正片內容，硬鏈接到 Jellyfin 支援的 extras 資料夾（名稱與位置依 §20 查證），讓 Jellyfin 把它們顯示為該作品的額外內容，而不是污染集列表。

### 7.4 Unmatched【決定】

真正對不到 metadata 的影片與字幕**不入庫**，留在 `complete` 原位；本系統在 Media 頁與 Job 頁列出它們，提供「指派到某季某集」「標記為 extra」「忽略」三種動作。使用者能在媒體庫頁面重新匹配，資料來源是 complete 目錄 + 帳本。不放進 `unmatch/` 資料夾，理由：

- Jellyfin 會嘗試把媒體庫內任何影片解析成集數，`unmatch/` 資料夾裡的 `[Group] Title - 25.mkv` 很可能被當成第 25 集，反而製造錯誤。
- 把不確定的東西鏈接進去再要求使用者清理，比不鏈接更難維護。

### 7.5 標題語言【決定】

`Title` = TMDB 英文 `name`；英文缺或與 `original_name` 相同時用 `original_name`。資料夾名決定後凍結（§4.5）。

**畫面上的顯示用標題、簡介與海報跟著 UI 語言走**（[ADR-0005](adr/0005-display-title-follows-ui-language.md)）：`zh-Hant` 取 TMDB `zh-TW` 那一輪，`en` 取 `en-US` 那一輪。海報也分語言，中文標題配英文海報是兩個來源拼出來的東西，所以一起跟。

- 這一條只管畫面；檔名、資料夾名與季名比對用的字串不跟 UI 走。
- **媒體庫牆上已在 Jellyfin 裡的作品例外**，顯示 Jellyfin 的名稱：牆上多數作品不是 Berth 經手的，Berth 手上沒有它們的 TMDB 快照，而 Jellyfin 的名稱與使用者在 Jellyfin 裡看到的一致。還沒進 Jellyfin 的卡片照樣跟著 UI 語言。

### 7.6 Specials / OVA / OAD / SP

- 能對到 TMDB season 0 某一集 → `Season 00/… - S00Exx`。
- 對不到但可辨識為 extra（NC/PV/CM）→ extras。
- 對不到且像正片（`SP1`、`OVA 2`、`特別篇`）→ Unmatched，等人工指派；這類是 review 的大宗，UI 要讓「把這檔指派為 S00E03」只需兩次點擊。

### 7.7 多版本並存

- 同一集不同 tags 的檔案並存在同一季資料夾。**Jellyfin 12.0 起原生合併**：同一個季資料夾裡解析出同一個 `S/E` 的檔案就是同一集的版本，本系統的命名不裝插件就合併成 1 個 Episode、多個 MediaSource（對 12.0.0 / 12.1.0 實測，§20.9）。
- **本系統只支援 Jellyfin 12 以上，不裝 MergeVersions**（[ADR-0002](adr/0002-jellyfin-12-minimum-pinned-image.md)）：10.10 / 10.11 原生不可靠（實測會變成兩個重複的 Episode 條目，§20.6），得靠這個插件；而它在 12.x 上對本系統的樹是空跑，卻要多一次 Jellyfin 重啟、依賴 GitHub 下載，還會跨媒體庫誤併。
- 版本標籤：
  - **電影**是 tags 字串本身（` - ` 之後的部分）。
  - **劇集**是「去掉各版本檔名的共同前綴」剩下的部分（有集名時是 `集名 + tags`，沒有集名時是 `S01E01 + tags`；算法跟標點有關，12.0 與 12.1 也不同，§20.9）。所以 UI 不自己重算劇集的版本名，Jellyfin 收錄之後讀它回的 `MediaSources[].Name`。
  - tags 詞彙仍要短且可讀，但 UI 文案不能說「使用者看到的就是 tags」。
  - 版本先後依解析度降冪，再依檔名。
- 命名唯一必須保證的事：同一集所有版本的檔名在 `S01E01` 之前的部分完全相同，且互相只差 tags。

### 7.8 重複版本

新 Plan item 與帳本既有 Entry 的（Media, 季, 集, tags）完全相同 → `duplicate`。自動模式預設 **跳過並記事件**；review 提供「取代舊版」「保留兩者」「跳過」。Tags 不同的（例如加 `[v2]` 類 tag）本來就不是 `duplicate`。

- **保留兩者時新的那一份檔名多一個序號標籤**（`[2]`、`[3]`…，存在 Tags 的 `edition`）：Tags 完全相同的兩份檔名一模一樣，不改名就放不進同一個資料夾；Jellyfin 12 把它們當同一集的兩個版本。
- 判斷在**規劃時**（比帳本），不在入庫時。

**多集檔與同起始集的單集**：新 Plan item 的正片與同一季的帳本既有 Entry、或同一份 Plan 的其他正片**起始集相同、結束集不同**（`S01E03-E04` 對 `S01E03`）→ 送 review，不自動入庫，理由要說出後果。

- 與帳本撞的那一種：照上面的 `duplicate` 處理——略過那一列、Review Queue 上一列 `duplicate`，同一包其餘照常入庫。
- 同一包之內互撞的：整份送 review。
- 原因：Jellyfin 12 的版本分組鍵只有季號與集號，會把它們併成同一集的兩個版本，後面那一集從集列表消失（§20.9）。規則不分 Jellyfin 版本：同一集有兩份涵蓋範圍不同的正片，本來就該由人決定留哪一份。

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
- `ledger`：來源（hash、相對路徑、device）、目標路徑、目標 inode（硬鏈接兩端同一個 inode，來源不另存）、media/季/集、tags、plan item、Jellyfin item id、狀態（ok / target_missing / source_missing / inode_mismatch）。
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
| `jellyfin_item_mismatch` | Jellyfin 回驗：反查或對帳找到的 item，Jellyfin 認的季號、集號（多集檔是範圍）或所屬作品的 TMDB id 與帳本不同 | 重新反查（在 Jellyfin 修好之後）；下一次比到一致時系統自己收掉 |

十四種共用 `issues` 表與同一個封閉集合（plan §2.4），來源分四組：

- 前七種：對帳。
- 中間四種（`missing_files` 到 `jellyfin_item_unresolved`）：管線自己發現，另以 `issue_detected` 事件記著。
- `library_uses_tvdb`、`low_disk_space`：`health_checker` 每 5 分鐘量出來，由健康檢查偵測而不是對帳。
- `jellyfin_item_mismatch`：Jellyfin 回驗，反查與對帳的 Jellyfin 那一方比同一份。

`ledger.status` 的 `target_missing` / `source_missing` / `inode_mismatch` 是帳本那一列的現況，Issue 是「要有人決定」的那一件——同一件事的兩個角度，resolve 之後帳本那一欄跟著改。`source_missing` 與 `unlinked`（刪除範圍拆掉的鏈接）是**使用者決定過的**現況，對帳看到就不再開 Issue。

**認領類三顆**（`orphan_complete` 的重新入庫、`unknown_torrent` 的認領、`unmanaged_library_file` 的認領進帳本）：與 `reimport` / `rebuild-ledger` 同一組原語，都走既有的入庫路線、都不刪東西。

- 「重新入庫」與「認領」**由管理員在列上選作品**：沒有作品的 Job 規劃出來只會整份停在 review 而且核准不了。
- 孤兒目錄建一筆 `trigger = reimport` 的 Job 停在 `completed`；無主 torrent 建一筆停在 `submitted`（Route 由它的 category 決定，只掛 `berth` tag 的說不出要入庫到哪裡，拒絕）。
- 「認領進帳本」是單一檔案的 `berth rebuild-ledger`：inode 反查 complete、路徑照命名模板反解，配不上的拒絕、那一件開著。

**管線三種的動作**（`missing_files` / `client_error` / `client_removed`）只在 Job 還停在那個壞掉的狀態時按得了：

- 重新校驗與重試讓 Job 回到檔案清單到手之後那一站（還沒有清單的回 `submitted`），由 poller 照常往前推。
- 重新送單照存下來的下載連結再加一次，**先問過 Route、連結與 qBittorrent 才動 Job**。
- 兩顆「承認」走刪除範圍四個旗標全不勾（Job 進 `removed`，磁碟與 qBittorrent 都不動）。

**「忽略」的有效期**：

- 預設是「這一次不處理」：忽略之後下一次偵測就開新的一筆。
- 健康檢查那兩種**沒有 Berth 按得了的修法**，所以條件解除時系統自己收掉（`resolved_by = system`）；問不到 Jellyfin、量不到那個目錄不算解除。它們的「忽略」在條件持續期間有效：5 分鐘量一次的東西，照「這一次」的話忽略等於無效，故意掛 TVDB 的使用者會被一直問。條件解除過一次、之後再發生才重開。
- `jellyfin_item_mismatch` 與 `unknown_torrent` 照同一條：前者每日對帳比一次，後者 poller 每 5 秒寫一次，照「這一次」會為同一件事每天推、忽略 5 秒就重開。對帳的其餘六種仍是「這一次不處理」。

**按鈕與判定的細節**：

- 會刪東西的按鈕（連 complete 一起刪、刪除孤兒目錄、以硬鏈接取代）按下去之前再確認一次世界：偵測在早上，按下去在下午。
- `job_without_files` 有兩個例外：那一份 Plan 本來就沒有要鏈的檔案（全是重複的那一包自動落地，§7.8）不算；使用者對那一筆按過「承認刪除並清帳本」的不算——帳本是他自己清的，再問他要不要重新規劃等於讓剛決定過的事自己回來。

### 9.2 刪除範圍【決定】

刪除是一組可組合的旗標，UI 用勾選框呈現（沿用 Sonarr 的「同時刪除檔案」慣例，但拆得更細）：

- 移除 library 硬鏈接（Jellyfin 會在下次掃描少掉它）
- 從 qBittorrent 移除 torrent（不刪檔）
- 刪除下載目錄裡的檔案（要求先移除 torrent，否則拒絕）：下完的在 complete；還沒下完的在 Route 自己的 incomplete 目錄，只刪 qBittorrent 報的內容路徑（`content_path`）底下屬於這個 torrent 的檔案，沒報過內容路徑的不照 slug 猜
- 清除帳本與 Job 紀錄（否則保留為歷史）

四個旗標**預設全不勾**：Sonarr 的對話框預設勾「同時刪除檔案」，但這裡的刪除以 Job 為單位而不是作品，預設刪檔會誤刪還在做種的東西。

空間估算：顯示「預估可釋放空間」，只有當來源與所有鏈接都刪掉時才真的釋放，UI 要說清楚。**同步 `stat` 每一個來源與目標**（慢而準，畫面上說「正在算」），不用來源大小去猜。

對話框住在 Job 詳情頁與 Media 詳情的版本清單，同一個元件；對帳發現的 `library_link_missing` 選「連 complete 一起刪」時走同一組旗標。

實作（`services/deletion.py`）：

- 順序是**移除 torrent → 移除鏈接 → 刪來源 → 清紀錄**。移除 torrent 排第一是因為它是唯一可能失敗的一步，問不到那一台時整次刪除不做，而不是刪到一半才發現。
- `unlink` / `delete_files` 之後帳本那幾列留著當歷史（清帳本是另一個旗標），只把 `status` 改成 `unlinked` / `source_missing`。`unlinked` 是使用者決定過的現況，同 `source_missing`（§9.1），對帳不再為它開 `library_link_missing`。
- 空掉的目錄跟著收：留著 `Show/Season 01/` 兩層空目錄的話，Jellyfin 的牆上那部作品還在。
- 刪除與鏈接**同一道路徑守衛**（plan §8.6）：帳本被改壞、指到媒體庫外面的那一條不刪，其餘照樣做完。

**媒體庫裡只拆 Berth 放下去的那一個**：使用者把硬鏈接換成自己的檔案之後（一份複製品、一個重新壓制的版本），那條路徑上的是 Unmanaged，§5.3 的不變量說它永不刪。「移除鏈接」、audit 撤銷、rematch 拆舊鏈接三條路共用一個判斷（`deletion.Placed.holds`）：

- 目標的 inode 等於帳本記的、或等於來源現在的，才是 Berth 放的；都不等就不刪。
- 回應與時間線列出沒刪的那幾個（`unmanaged`），帳本那一列的現況交給下一輪對帳（`inode_mismatch`）。
- 撤銷與 rematch 其餘照做（帳本那一列照樣移走、Job 照樣回 review），那個檔案下一輪對帳是 `unmanaged_library_file`——它本來就是。

兩個分頁同時刪同一筆時，後到的那一個是 409 `moved_on`，不是回報成功（plan §3.1）。

**沒勾「清除帳本與 Job 紀錄」的那一筆，同一個 torrent 再送單會被拒**（`job_removed`，手動與 RSS 都是），而不是回傳那一筆當成「本來就在了」：紀錄還在就是還沒決定要不要再下載，RSS 下一輪會一直拿回同一列。要再下載：complete 裡還有檔案就重新入庫（§9.3），否則連紀錄一起刪掉之後再送。

### 9.3 重新入庫

Import Source 可以是「complete 內任一資料夾」，不要求 torrent 仍存在。流程與正常入庫相同（planning → review/importing），帳本以來源相對路徑冪等，所以「刪了 library、保留 complete、再重新入庫」是一鍵動作。

兩個入口：Job 頁的 `POST /jobs/{hash}/reimport`（那一筆的 complete 目錄），與 `orphan_complete` 的「重新入庫」（沒有 Job 的目錄，建一筆 `trigger = reimport` 的 Job）。

- **Import Source 是磁碟上那一包**：`job_files` 照資料夾裡現在的樣子重寫，少了一集就少規劃一集，而不是照 torrent 的清單在 importer 那一步失敗。
- 帳本冪等的鍵是「Job + 來源相對路徑」，所以 TMDB 在兩次之間改了集名時，那一列換到新路徑、舊的鏈接被收掉，Jellyfin 不會多一個同一集的版本。

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
- AniList/MAL ↔ TMDB 對應（Fribb anime-lists）：M5 票 16 給 AI 助理用，**票 23d 拿掉**（17 部錯 4 段，網搜集數表加 TMDB 季集表錯 0 段，`docs/research/agent-sources-ab-2026-10-28.md`）；RSS 的 offset 建議改用 Mikan 開播日，見 §15〈offset 建議〉。

**什麼情況該回頭重看這個決定。** 本節寫的是「第一階段只用 TMDB」，不是永久結論。下面四條任一成立就重跑 `scripts/experiments/anime_episode_source.py` 並重新評估，其餘時候不要再開這個題目：

1. **Jellyfin 換掉預設的劇集 provider，或社群普遍改用 TVDB 插件刮。** 上面第一條理由（同源最安全）是整個決定的承重牆，它一旦反向，結論就跟著反向。
2. **M1 票 06 的「篇章名 → 季號」做完之後，benchmark 的季集失敗仍集中在 provider 結構差異上。** 現在那一塊只剩 78 筆（只有 TMDB 錯 54、只有 TVDB 錯 24），佔樣本 1%；主因（573 筆）是解析器缺口。若補完解析器後比例翻轉，代價與收益就要重算。
3. **美劇 / 韓劇出現同類問題。** 這次只量了 10 部動漫 —— 動漫是最難的形態（split-cour、字幕組四種編號習慣並存、劇場版插號），結論往簡單形態推是合理的，但**沒有量過**。M1 的 benchmark 語料含美劇 / 韓劇 8 筆（§20.4），那裡是第一個會看見的地方。
4. ~~**TVDB 的授權模式改變。**~~ **這一條 2026-09-09 撤銷** —— 免費自助 key 現在就有，使用者自備 key 本來就可行，授權從一開始就不是差異（見上面的更正）。留著這行是為了不讓它被重新加回來。

---

## 11. 帳號與權限【決定】

沿用 Seerr 做法：以 Jellyfin 帳號登入本系統。

- 初次設定（[ADR-0012](adr/0012-owner-is-jellyfin-admin.md)）：輸入 Jellyfin 位址 → 以 Jellyfin **管理員**帳號登入 → 該帳號成為本系統 admin，並產生本系統用的 Jellyfin API key。
- 其他 Jellyfin 使用者可登入，預設角色 `user`（可探索、可送單到指定 Route、可看自己的 Job；送單只能送這次搜尋記下的結果，不收網址，也拿不到索引站的 API key，M4 票 79）；admin 可改 Route、刪除、審核。**2026-09-22 明確**（M2 拆票前；[ADR-0006](adr/0006-review-and-issues-split.md)）：Review Queue、Issue 的動作、rematch、刪除範圍、手動對帳一律只有 admin（plan §6 的門禁與 `api/gate.py` 同輪補上）；`user` 送單的 Job 停在 review 時只能等，畫面上說「等管理員審核」。
- 不自建密碼系統；本系統的 `users` 表只存 Jellyfin user id 與偏好。
- 未來的審批、配額、通知都掛在這個角色模型上。
- 取捨：Jellyfin 掛掉時無法登入。可接受，Seerr 同樣如此。

---

## 12. 播放【決定】

第一階段 **深連結到 Jellyfin** 該項目的詳情頁（帳本存有 Jellyfin item id；劇集連 Series，電影連 Movie）。格式原本沿用 Seerr 來源碼的 `{externalUrl}/web/index.html#!/details?id={itemId}&serverId={serverId}`；**實作用 `{對外網址}/web/#/details?id={itemId}`**——客戶端自己的 `#/` 形式（M0 票 04 實測），不帶 `serverId`（2026-09-15 對 12.0.0 實測開到同一頁，§20.1）。主機是選填的「Jellyfin 對外網址」，沒填時推導（票 13，Seerr 的 `externalHostname` 慣例；套件內的 Jellyfin 用瀏覽器的主機名 + `JELLYFIN_PORT`，M3 票 06b）。Jellyfin 沒有「直接開始播放」的穩定 URL。不做內嵌播放器：播放器牽涉轉碼協商、字幕（動漫的 ASS 與字型）、播放進度回報，是最大工作量且與本系統核心無關；而且多數人在電視與手機上用 Jellyfin 的 app 看，網頁播放器取代不了它們。

**瀏覽由 Berth 取代**（2026-09-15 使用者拍板，推翻原本的「媒體庫頁的價值在『狀態與修正』，不在『取代 Jellyfin 播放』」；M1.5）：媒體庫頁與 Media 詳情像 Jellyfin 那樣呈現整個 Jellyfin 媒體庫——繼續觀看、下一集、已看 / 未看（可切換，寫回 Jellyfin 該使用者的紀錄）、依類型或年份排序、Jellyfin 的圖、選季選集——並疊上本系統的入庫狀態。按下播放或某一集時才深連結到 Jellyfin 的那一項（Jellyfin 沒有直接開始播放的網址，使用者在那一集的詳細頁再按一次播放）。可行性已查（§20.8）：伺服器 API key 可以代讀代寫每位使用者的觀看資料，但 Jellyfin 這時只套用一部分媒體庫權限，**媒體庫存取權限要由 Berth 自己擋**——`userId` 一律取自 session，媒體庫對 Jellyfin 的 `UserViews` 允許清單驗證。

---

## 13. 頁面清單

| 頁面 | 目的 | 關鍵內容 |
| --- | --- | --- |
| 設定精靈 | 首次啟動（只管第一次，跑完之後導向設定，2026-09-25） | Jellyfin、qBittorrent、Prowlarr 各一頁，每頁由使用者選套件內或既有、選完當場測試（不偵測，2026-09-29）：Jellyfin → 以它的管理員成為擁有者（套件內或還沒初始化的那一台由擁有者建，2026-09-26）→ qBittorrent → 媒體庫路徑與 Route（建立並跑檢查）→ Prowlarr 與索引站 → TMDB → 完成。兩種來源都只建 Berth 擁有的物件（§16.3、§16.4） |
| 探索（首頁 `/`） | 找東西 | **只放 TMDB 牆**（[ADR-0004](adr/0004-library-browsing-and-discovery.md)；2026-09-24 拍板、M3 票 06 實作）：趨勢 / 熱門 / 搜尋；繼續觀看與下一集只在媒體庫頁，登入後預設落在媒體庫、媒體庫裡還沒有 Berth 入庫的東西時落在這裡（2026-09-26，M4 票 10；M1.5 票 07 原本把那兩列放在這裡上方）；卡片顯示狀態（未追蹤 / 部分 / 完整 / 下載中，**四種都由 Job 與帳本推導**，所以卡片上的狀態要等 M1 票 09 才畫得出來） |
| Media 詳情 | 決策中心與觀看入口 | 探索與媒體庫點進的是**同一頁**（2026-09-15 使用者拍板，不另建媒體庫詳情頁）。作品已在 Jellyfin 裡時最上面是**觀看區**（M1.5）：繼續看 / 下一集的深連結、選季選集、各集劇照與已看標記。其下：TMDB 資訊、各季各集入庫狀態、**搜尋 torrent**（按搜尋前用 chip 選要問的名字與季、說出會發幾個查詢，M4 票 84；結果表：大小、做種、來源、解析出的 tags、預估匹配；作品已入庫時收合）、選 Route 送單、RSS 訂閱、**這部作品的下載**（M4 票 12，排在 RSS 訂閱之後、季集之前：每一筆 Job 的狀態、進度、大小、來源與字幕組、Route、時間，展開看它的檔案、大小與計劃對到的季集，連到 Job 詳情；預設只列還沒了結的——在路上的加上已入庫而還有檔案待確認的，其餘在「全部」；從沒送過下載的作品整段不畫；季表的「下載中 / 卡住」連到蓋到那一集的那一筆）、檔案清單（含 Unmatched 與 rematch）、版本並存清單 |
| 媒體庫 | 瀏覽與修正 | 像 Jellyfin 那樣瀏覽**整個 Jellyfin 媒體庫**（M1.5，不只 Berth 經手的）：一個 Jellyfin 媒體庫一頁、只列這位使用者在 Jellyfin 看得到的；繼續觀看、下一集、卡片牆附已看 / 未看、依類型或年份排序；Berth 經手的作品疊上入庫狀態，還沒進 Jellyfin 的（下載中、待審）也在牆上；篩選：待審 / 對不到（只給 admin，M2 票 14）。原本還有一個「有 Issue」，2026-09-24 使用者拍板拿掉：`/issues` 已經是獨立頁（M3 票 01）。M1（票 13）是依 Route 分頁、只列 Berth 經手的作品＋深連結 |
| 下載與活動 | 全域狀態 | 所有 Job 列表：狀態、進度、Route、trigger；點入 Job 頁 |
| Job 詳情 | 可觀測性 | **獨立頁 `/jobs/:hash`**（M2，2026-09-22 定；M1 只有 `/jobs` 的就地展開區）：**時間線**（§5.2）、檔案清單與各檔決策、Plan 歷史、動作（重新解析、重新入庫、刪除範圍） |
| 審核佇列 | 人工介入 | 低信心 Plan（逐檔可改）、已入庫待確認（medium 自動入庫的 audit 清單，可一鍵撤銷；同一個 Job 一組一顆「全部確認」、整段一顆，收起時說出為什麼是 medium）、Unmatched、重複版本；批次核准。**Issue 不在這裡**（2026-09-24 拍板，M3 票 05）：只在 `/issues`，這一頁原位一行「另有 N 件待處理」連過去。**一列一件事的清單，不是牆**（2026-09-22 定，M1.5 的 critique：篩出來常常只有一兩件，卡片牆說不出「有幾件事在等你」）；只有 admin 進得來 |
| RSS | 自動化 | Feed 清單、RSS Series 清單（待綁定排最前、就地綁定作品與 Route）、最近的 Feed Item、一次性 RSS 連結、新 Feed 的第一輪預覽（2026-09-24 以 RSS Series 取代規則，§15；M3 票 08 做前三塊） |
| 健康與問題 | 維運 | 服務連線、Route 硬鏈接檢查、Reconciler 結果、磁碟空間 |
| 設定 | 管理 | 一格泊位一頁（Jellyfin、qBittorrent、媒體庫路徑、索引站、TMDB），與精靈共用元件與命令：服務位址與憑證、索引站、TMDB key、Route；之後加命名詞彙、解析與 AI 開關與預算、使用者角色 |

---

## 14. AI 與通知【決定】

**形狀從一開始就定**（M0 起）：

- **API-first**：UI 做得到的每個動作都是一個有名字、有 schema、冪等的服務命令（`search_torrents`、`add_download`、`generate_plan`、`apply_plan`、`rematch_file`、`delete_job`、`reconcile`、`issues.relink`（Issue 的按鈕一顆一個命令，M5 票 04）…）。AI 的工具與 MCP server 只是包裝這些命令。
- **資料可讀**：Plan、Event、Issue 都是結構化 JSON，AI 不需要爬 UI。

**AI native**（2026-09-24 使用者拍板，推翻 2026-09-22 的「改狀態的命令一律先提案」）：目標是綁不到 TMDB、解析不出集數、offset 錯、解析錯這類問題**幾乎不需要人工處理**，外加定期巡檢。原則：

- **沒有 AI 也完整可用**（2026-09-24 使用者補充）：AI 只是替使用者按審核頁、待處理頁上的那些按鈕，讓人專心看片——平常用 Jellyfin App 看，只在要加新作品時打開 Berth。所以每一種 AI 任務都有同一個命令的人工版本；不需要 AI 的檢查（Jellyfin 回驗、片長驗證、每日程式檢查）與通知是核心功能，不綁在 AI 上；沒有 AI 時要靠規則、批次動作與通知把人工降到最少。
- **三層漏斗**（[ADR-0008](adr/0008-ai-autonomy-and-optional-ai.md)）：規則層 → AI → 人（§6.10）。沒有 AI 時是兩層：播出日比對、片長驗證與 Jellyfin 回驗在 M3，每日檢查與通知在 M4，都不靠 AI。
- **自主權看可不可以撤銷**：每個命令在**命令登錄表**裡標明副作用等級（讀取 / 可逆 / 不可逆）與反向命令。可逆的（綁定作品、改季號與 offset、核准或改寫計劃、rematch、確認 audit、重試、recheck、重新反查、在預算與磁碟門檻內補下載）通過驗證後 AI 自己做；不可逆的（刪 complete 檔案、移除 torrent、purge）與改設定、Route **永遠要人**，做成 Proposal——標記上是 `irreversible`，或帶「連到新位址」「對外發訊息」「改設定」任一個旗標（M5 票 02，`services/commands.py` 的 `needs_person`）；「忽略 Issue」會把問題藏起來，也做成 Proposal。M3 起新增的命令都要先標好等級、反向命令與旗標。
- **AI 說了不算，要經過驗證**：AI 的結果與規則層的結果走同一組程式檢查（播出日、片長、TMDB 集存在、不撞目標路徑），不通過的不套用。
- **信任逐步放開**：每種任務先**影子模式**（只記錄 AI 會怎麼做、統計與人的決定一致率），使用者看數字後切自動，可隨時切回。
- **可追溯、可撤銷**：「AI 活動」頁列出 AI 做了什麼、理由、花費，逐筆撤銷；審核頁只剩 AI 交上來的，每一件附 AI 的理由。
- **記憶是結構化資料**：改正寫回 RSS Series、別名、排除條件，並進 benchmark 候選語料（§6.10）。
- **巡檢**：每天一次只跑程式檢查（不花 token），每週一次完整巡檢（程式檢查標出的項目交給 AI、可逆的修、其餘交給人），產出週報送到通知管道。

| 里程碑 | 內容 | 為什麼在這個位置 |
| --- | --- | --- |
| **M4 巡檢與通知** | 每日程式檢查 + 每週週報；`events` 的訂閱者 + channel adapter（第一個是 Discord，2026-10-21，[ADR-0015](adr/0015-notifications-discord-dm.md)）+ 每人的訂閱設定；「可以看了」「有 N 件等你處理」 | 不需要 AI；平常不打開 Berth 的前提是有事時它會說（2026-09-24 排到 AI 之前） |
| **M5 AI 地基與對話 agent**（2026-10-27 改） | 命令登錄表與執行器、Proposal（兩者不需要 AI 也成立）；provider（Anthropic 與 OpenAI 相容，各自可設 base URL 與 key）、防護與記帳、觀測頁；每一頁都叫得出的側面板對話：工具、確認卡、外部資料（AniList 當季清單、Bangumi 放送表、網搜；Fribb 與 AniList 的系列走圖在票 23d 拿掉）、skills、上下文壓縮、斜線指令 | 有人在場的對話最適合讓核心第一次碰到真實模型；確認卡就是 Proposal 的第一個介面 |
| **M6 人工接管開關**（2026-10-27 改） | 以決定點為單位的人 / 影子 / AI 三段開關；背景 AI 任務（規則層 low 的 Plan、Unmatched 與待綁定猜作品、offset 修正、audit 確認或撤銷、可疑入庫、Issue）；影子一致率；AI 活動頁與撤銷 | 影子模式要等核心在 M5 穩了才開始累積真實資料 |
| **M7 Discord 與 MCP**（2026-10-27 改） | M4 的 Discord bot 接上同一個核心：同樣的對話體驗，確認卡是帶按鈕的訊息，身分用個人 API token（§16.2）；命令登錄表另外包成 MCP server | 只多兩個入口，核心與 Proposal 共用 |

**Proposal 只用在不可逆的動作與 AI 沒把握的事**：命令名、參數、理由，人確認才執行。這與「AI 不動原檔」是同一條界線。

**對話裡的確認卡**（2026-10-27）：不可逆的、送出 torrent、讓 Berth 連到新位址（Feed 網址、改設定）、對外發訊息、以及讀過外部內容之後帶自由文字參數的寫入，一律出確認卡；其餘可逆動作直接做並給撤銷。卡片的參數由伺服器存，按確認時用存下的那一份，不信前端回傳的；唯一的例外是 Route：作品放得進的不只一條時，那一列的 Route 一律由人在卡片上選（預選這部作品上次用的那一條，沒用過就不預選），只收提出時存下的那份清單裡的（2026-10-28 使用者決定，M5 票 23b）；**訂閱的字幕組也由人在卡片上選**：可選的不只一個時卡上必選，助理建議的只當預選，伺服器只收提出時讀番組頁或那一次搜尋存下的清單裡的（2026-10-28 使用者決定，M5 票 26）；**送單卡逐列標出作品已經有的集**（帳本或這個人的 Jellyfin，「含已有的第 N 集」）：伺服器提出時算，不靠助理說（2026-10-30 使用者決定，M5 票 28）；關鍵字訂閱因此一律出卡（第一批在卡上確認）；id 必須出自這段對話已存的工具結果，網址必須逐字出自使用者打的字。整個系列一次送單時先出一張總覽卡，逐列可取消勾選（§20.24）。

**provider**（2026-10-27）：Anthropic Messages API 與 OpenAI 相容的 Chat Completions 都做，使用者自己設 base URL 與 key（自架閘道、OpenRouter、本機模型走後者）。網路搜尋在 Anthropic 用伺服器端 `web_search`，另可設 Tavily key（兩種 provider 都能用）。

---

## 15. RSS 設計要點

**2026-09-24 重寫**（[ADR-0007](adr/0007-rss-series-model.md)）：原本以「Rule 先綁一部作品，再挑字幕組白名單與優先序」為中心，與實際用法不合——使用者在 Mikan 上選好作品與字幕組，聚合 feed 裡出現的就是要的（Mikan 的 `MyBangumi` 實測：同一部作品訂兩個字幕組是常態）。Berth 的工作因此是**認出每一筆是哪部作品**，而不是再挑一次。

- **Feed**：URL、輪詢間隔、來源類型、排除條件。【決定】第一批支援 **Mikan**（`/RSS/MyBangumi?token=` 聚合 feed、`/RSS/Bangumi?bangumiId=&subgroupid=` 單一 feed）、**Nyaa**（搜尋 feed、使用者 feed）與 **acg.rip**（搜尋 feed）；之後加 dmhy 與 generic。每種來源一個 adapter，負責解析該站的 RSS 擴充欄位並輸出統一的 Feed Item；各站的欄位與取法見 §20.12。
- **RSS Series**（取代原本的 Rule）：一部作品 × 一個來源，由 Feed Item **自動長出**。鍵：Mikan 用（番組 id, 字幕組 id）——item 的 `link` 是單集頁，單集頁上有 `/RSS/Bangumi?bangumiId=…&subgroupid=…`；其他來源用標題骨幹（去掉字幕組、集號、tags）+ 字幕組（AutoBangumi 的做法）；骨幹有羅馬字那一個名字就取它——同一組的简日、繁日發佈中文名常常不同，是同一個 Series（M3 票 11）。標題中間的括號註記後面還接著 ` / ` 與下一個名字時（`尼古喵喵 (邪竜解放版) / ヤニねこ / Yani Neko / Chainsmoker Cat`），搜尋與比對用的骨幹丟掉那一格註記、後面的名字照讀；**鍵不跟著改**，仍讀到第一個括號為止——鍵存在資料庫裡，改了它既有的 Series 下一輪會另長一個（M4 票 98）。這些來源沒有番組頁，自動綁定的候選只從標題來，一律留給人。帶著 Media、Route、季號、集號 offset、排除條件、是否已確認。
- **全部接受，只排除**：Feed 裡的項目預設全部下載，Berth 不再問字幕組。排除條件是關鍵字或正則、比對整個標題，分全域、Feed、RSS Series 三層；預設只排除合集（`release_kind != single`；搜尋 feed 常夾著「01-13 合集」），720p、简体等做成一鍵加入的建議項、不預設勾。**合集不是不能解析，只是不自動下載**，使用者仍可從一次性 RSS 或搜尋手動送單。同一集多個字幕組、同組的 v2 都入庫並存（§7.7，2026-09-24 使用者拍板）。**規則格式照 Sonarr 的 release profile**（M3 票 10，§20.12）：一般字詞不分大小寫、比對整個標題，`/…/` 包起來是正則（`/…/i` 不分大小寫）；寫壞的存不進去、當場說出原因。**只往前看**：規則收緊時還沒送出去的 Item 照新規則再看一次，放寬時不把之前擋下的放回來——拿掉一條規則不該讓幾個月前被它擋下的一次全部下載。**逐筆放行**（M4 票 111，照 Sonarr 互動搜尋的「照樣下載」）：被排除的那一筆在 Feed Item 清單上按「仍然下載」，當場走同一條送單的路（去重照常，同一個 torrent 已送過是重複）；只收 RSS Series 已綁定、Feed 已選過第一輪的，送不出就留在排除、帶著原文。它是人按的、一次一筆，與「只往前看」防的批次放回不衝突；不做整批或依規則放行，也不記「人放行過」。合集那一條是全域的開關（看解析器的 `release_kind`，合集、區間、季包的寫法一條關鍵字寫不完），不在 Feed 與 Series 那兩層。
- **綁定**：第一次見到的 RSS Series 去 TMDB 找作品（Mikan 的番組頁有中文標題、開播日期、bgm.tv 連結）；有把握就自動綁定（2026-09-24 使用者拍板），沒把握的進「待綁定」清單，它的項目留著，綁定之後再送。**有把握**（M3 票 09）是 §6.5「標題 + 年份精確命中」在這裡的樣子：番組名或發佈名的標題骨幹與 TMDB 的某個名字正規化後**相等**、番組頁的開播日期落在那部作品某一季首播前後 14 天內、這樣的作品只有一部；Route 是**長出它的 Feed 那一種的那一條**（2026-09-26 使用者拍板，M3 票 21：照 Sonarr Import List 的「Root Folder」，加 Feed 時選；2026-10-16 起劇集、電影各一條、那一種有 Route 就必填，M4 票 105，§19；預設安裝的 TV 與 Anime 都收劇集，沒有這一格一部都綁不上），那一格是空的（票 105 之前的 Feed）或停用了才照「收得下它的啟用中 Route 只有一條」的規則；自動綁定以 `system` 身分走人工綁定同一支命令，Job 的時間線說出依據。沒綁上的每一種各有理由碼，認得出的作品列成候選讓人一鍵選（選定之後照樣要按一次確認：資料夾名在那一刻定下來，§4.5）。**只在 Series 長出來的那一輪認**，不在之後每一輪重認——壞掉的番組頁會每 15 分鐘打一次，人拆掉的自動綁定也會被綁回去。**例外是暫時查不到的**（M3 票 20 曾另有被請求預算擋下的 `lookup_deferred`，M4 票 107 隨預算拿掉）：連不上、逾時、限流、5xx 的（M4 票 14，§19 2026-09-26），理由寫 `lookup_retry`、說出下一次在什麼時候，退避、有上限地重認（1、4、12 小時後，一個 Series 最多認四次，plan §3.2），用完、或再問也一樣的（404、回的不是那個服務）才落到 `lookup_failed` 等人。**一部候選讀不到不拖垮整次**：其餘的照判，判得出來就綁；判不出來而缺的那一部是暫時讀不到的，照暫時的失敗晚點再認；一部都沒讀到才是查不到。**季名不進搜尋詞**（M4 票 14）：TMDB 的作品名不帶季名，`第N季 / 第N期`、`Season N / Nth Season / SN` 從搜尋詞與比對的線索裡拆掉（規則與解析器讀資料夾名同一份，`parser.seasons`），拆出來的季號改當開播日那一條的線索——**只比那一季播出的期間**（它任何一集的前後 14 天內；TMDB 把幾季併成一季時是依播出日切出的那一輪，plan §4.4），不是只比首播：Mikan 會把一季的第二個 cour 另開一個番組、寫它自己的開播日（Re:Zero 第四季「夺还篇」，TMDB 65942 第 1 季第 78 集，§20.12）。第二季的番組頁寫的是第一季的開播日時兩條線索矛盾，留給人。bgm.tv 連結沒有用上：TMDB 不收它的 id。實測見 [`docs/research/rss-sources.md`](research/rss-sources.md) §2.8（11 部認得 10 部、錯 0 部）。
- **處理**：item → RSS Series → 排除條件 → 去重（Feed 內的 GUID；跨 Feed 的 info hash；帳本已有同 Media/季/集/Tags）→ 建 Job（trigger = rss、帶 RSS Series id）。v2 版本號不同，不是重複。排除與去重擋下的都不是錯誤，Feed Item 清單說出是哪一層的哪一條、或重複了哪一筆（M3 票 10）；帳本那一層比不準的（季集猜不到、字幕組在檔名寫另一個組名）放行，由規劃時的重複版本判斷（§7.8）接住——漏擋只是多下載一次，擋錯卻是少一集。
- **補舊集**：聚合 feed 只有最近的集數。Mikan 的 RSS Series 綁定時以它的單一 feed 列出整季，**一律補下載，沒有開關**（2026-09-24 使用者拍板、09-26 重申；M4 票 78 拿掉手動綁定與訂閱留下的「同時補下載舊集」勾選與 `passed_before`，當初因它略過的舊集由 migration 放回去；帳本已有、已有 Job 的跳過，排除條件照樣看）；讀不到單一 feed 不擋綁定，下一輪再補。每天用同一個單一 feed 補漏一次，接住 Berth 停機期間聚合 feed 捲掉的集數；RSS Series 完結之後再補最後一次就停（停機跨過完結判斷時被捲掉的最後幾集靠這一次接住，M4 票 116）、新的一筆出現時恢復，不設開關，畫面上看得到上次補漏的時間（M4 票 108，2026-10-19 使用者拍板；排程見 plan §3.2）。搜尋類 feed 第一輪就帶著歷史：新 Feed 的第一輪不直接下載，列成預覽讓使用者選「全部下載」或「只追之後的」（M3 票 11）。預覽依結果分成會送出、綁定之後送、排除、重複四組，排除與重複各說理由；「只追之後的」當場再讀一次 feed、讀不到就不決定，選的那一刻已經在 feed 裡的都略過。**Mikan 不走預覽**（2026-09-25 shape 拍板）：聚合 feed 只有最近的集數，單一 feed 的整季由上面的補舊集處理。
- **季號與 offset**：放在 RSS Series 上，**規劃時讀**，每份計劃記下它用到的值（2026-09-24 使用者拍板）。大部分時候不必設——解析器的季名、篇章名、cour 標記與絕對編號換算先處理（§6.4、plan §4.4）。新 RSS Series 的第一批進審核（已入庫、等你看一眼），確認過一次之後照一般信心走，而且之後的 medium 入庫不再進 audit 清單（2026-09-24，由播出日比對、片長驗證與每日檢查守著）；算錯時在審核裡改正並「套用到這個 RSS Series」：寫回季號與 offset，並重算它底下還沒確認的集數（補舊集一次十幾集，第一集錯就全錯，改一次要全修好）。**M3 票 13 的做法**：第一批確認之前 high 也掛 audit（Series 帶了季號時解析器給的正是 high）；offset 是人說的集號減去檔名寫的集號；已入庫的未確認集數走 rematch 搬過去、**仍留在第一批裡**等「全部確認」（還沒有人看過它們），人親手改的那一集算確認過；停在 review 的走重新規劃；已確認的集數不動。**M3 票 14b**：連載中的 split-cour 第一批會被播出日比對整批擋在審核、一集都沒入庫，所以停在審核的計劃列也能「套用到這個 RSS Series」：人改的那一列照人說的、那一份仍等人核准，同一份裡沒人碰過的列與其餘停在審核的計劃照新的值重算，播出日比對照跑——offset 對了就放行、自動入庫（仍在第一批裡）；管理員逐列改過的其他計劃不動。**M4 票 11（2026-09-27，§19 2026-09-26「第一批審核證據夠強時跳過」）**：證據夠強的第一批不掛 audit，系統確認那個 Series（Job 的時間線記 `series_confirmed` 與擔保的集數）。**證據夠強**逐列看、一列不符合整批就不算：Series 沒有設季號與 offset；要入庫的列只有正片與跟著它的字幕；**季集照字面**——對到的集號就是檔名寫的（沒有 offset、絕對編號換算、重數推測），季號是寫明的、或只寫集號而對到第一季；理由只限白名單（標題、年份、季號的字面來源、只有一季、發佈時間落在第一輪、TMDB 沒有片長；新加的理由預設不在）；發佈時間與 TMDB 的播出日都拿得到而且過了播出日比對；**那一集剛播**（發佈前六週到發佈後兩天，與推測虛擬季同一個窗口）；片長驗證擋下的列本來就不是入庫。票面的起點是「信心 high」，改成白名單加「剛播」：只寫集號的單季作品（試跑的 BLACK TORCH）解析器給的是 medium，那個 medium 防的是「TMDB 還沒建新的一季、照字面讀成第一季」，而新一季的第 N 集發佈時舊的第 N 集早就不是剛播。**第一批是整個 Series 到確認為止送來的每一筆**：同一個 Series 的其他 Job 都落地了（入庫中或已入庫；還在下載、停在審核、失敗的都算還沒到齊）、還掛著 audit 的每一份也都擔保得了，才整批確認、一起清掉旗標——補舊集的前幾筆先掛著，最後一筆**自動**落地時整批一起看；有一筆停在審核就是那一批有一列不符合，由人按「確認整個 Series」。仍要人看的那一組（掛著 audit 的正片，與停在審核的計劃），審核頁與作品頁的「第一批待確認」說一句在問什麼（「確認 BLACK TORCH × ANi 的季集對應：S01 E01–E04 由集號直接對應」），組的鍵是「確認整個 Series」。量測（`scripts/experiments/first_batch_rule.py`）：語料 34 份擔保 10 份、擔保錯 0（沒有發佈時間的模擬成期望那一集播出後一天，照定義是剛播，所以這一輪量的是照字面與白名單）；對抗的一輪把發佈時間改成 Berth 自己讀成的那一集播出後一天，26 份擔保 9 份、擔保錯仍是 0；芙莉蓮與藥師少女的 split-cour 第二輪從 01 重數 0 份被擔保、第一輪剛播的都擔保；真的 RSS fixture 150 筆擔保 135 筆，沒擔保的是虛擬季換算、慢發的補檔與一次補齊的舊集。**已知盲點**：前一季只有幾集、緊接著開播 TMDB 還沒建的新一季時，新一季的第 1 集照字面讀成的舊第 1 集也可能在六週內播過。
- **offset 建議（候選，2026-10-28 使用者同意寫入、同日票 23d 改設計，未排程）**：取代初版「第二階段接入 Fribb 自動填 offset」那一句。不改 RSS 的規劃，只在 RSS Series **綁定之後給一個建議值**，顯示在第一批確認與審核的畫面上，由人一鍵套用；不自動寫進 RSS Series。**做法**：① 取 Mikan 番組頁的開播日；② 在綁定的 TMDB 作品正篇裡找同一天（±1 天：深夜檔在 TMDB 常記成前後一天）播出的那一集，它就是這一輪的起始集，**offset = 那一集 − 1**；那一天播的是 Specials 裡的一集（第 0 集）時取開播日之後正篇的第一集、建議旁註明（同一份研究算無職轉生第二季正解的做法）；正篇找不到或對到不只一集就不給。這就是 `docs/research/fribb-vs-chaining-2026-10-28.md` 算正解的方法，17 部 49 段沒錯過；③ 先用 benchmark 量：建議能少掉多少需要人改的第一批、誤報幾成。**只有 Mikan 來源有開播日**；其他來源沒有建議，照現在由第一批確認擋。原本「Fribb 的 offset 與 AniList 集數串接互相核對」拿掉：兩者在同一批 17 部裡分別錯 4 段、3 段，Fribb 也已從 Berth 拿掉（M5 票 23d，`docs/research/agent-sources-ab-2026-10-28.md`）。**它補的是 RSS 現在的盲點**（`fribb-vs-chaining` 研究〈走 RSS 現在的路擋不擋得住〉）：同一季兩個 cour 間隔不到 180 天又從 01 重數（Re:Zero 第二季後半，98 天）；TMDB 不放在正篇的 TV 條目找不到同一天的那一集、不給建議，照舊由第一批擋。其餘錯法 RSS 照 TMDB 播出日切季本來就擋得住。**什麼時候做**：M5 驗收之後看實際紀錄——RSS Series 第一批被人改季號或 offset（「套用到這個 RSS Series」）夠頻繁，就排進 M6 當一張票；很少發生就維持現狀，由第一批確認擋。
- **從 Media 頁訂閱**（次要入口）：選一個來源建單一 feed，並預先綁定這部作品。**M3 票 19**（2026-09-26 使用者拍板兩題）：**Mikan 由 Berth 代搜番組**（`/Home/Search`，§20.12），選字幕組之後建它的單一 feed、當場長出那一個 RSS Series 以綁定的同一支命令綁上，整季照補舊集的規矩（一律全補）；人在場，所以讀不到單一 feed 就當場拒絕、什麼都不加（綁定時的補舊集是讀不到不擋、下一輪再補）；那個 Series 已經在待綁定時就地綁它、不多開 Feed。**Nyaa / acg.rip 以作品的標題建搜尋 feed，Feed 記下作品與 Route**。**關鍵字訂閱只綁一個字幕組，而且由人選**（M5 票 26，使用者 2026-10-28：試用機上助理把搜到的每個字幕組都綁上、使用者沒選過；「搜索建立的訂閱應該先搜、列出字幕組、讓用戶選」，不分側面板或作品頁）：先搜一次，列出搜到的字幕組（筆數、最近更新、最新一筆，同 Mikan 的字幕組清單），選一組才建；Feed 只收那一組的發佈（`rss_feeds.subgroup`，照發佈名裡的字幕組比對，別組的不寫、不長 Series），那一組長出的 RSS Series 以建它的人的身分綁上。第一批（那一組這一次搜到的發佈名）就在作品頁或確認卡上列出，第一輪也在同一處選（協調者 2026-10-28）：「下載這些並追之後的」（預設，那個 Series 記成第一批已確認）或「只追之後的」（現有的記成略過、一筆都不送），與 RSS 頁第一輪那兩顆同義、走同一支命令（`rss.prime_feed`），不再到 RSS 頁選；按下去那一刻才出現的也算在這一批。作品頁不另加數量上限（清單攤在眼前、人自己按），側面板的卡照舊一張最多 13 個 torrent。讀不到搜尋就不建（人在場，第一輪選不了的 Feed 不留下）。字幕組必填，沒有「每一組都綁」的路；已經綁了好幾個字幕組的舊 Feed 照舊運作（`subgroup` 空的），不做 migration，第一輪預覽只留給它們與手動加的搜尋 feed。搜到別部作品的風險由人看過的第一批與 Series 的播出日比對接住。**重複訂閱說出來**：訂閱或加 Mikan 單一 feed 之前查這部作品現有的訂閱（`rss.list_subscriptions`），卡上與給助理的結果都列出來源與字幕組，由人決定；助理能刪訂閱（`rss.delete_feed`，不可逆、出卡，已下載的檔案與綁定留著）。詳情頁列出已綁在這部作品上的 RSS Series（來源、字幕組、第一批確認了沒、最近一集），整段只有 admin。**只下載現有的**（M4 票 112，使用者 2026-10-19）：已完結、字幕組只出了合集的作品，訂閱建的 Feed 那一筆合集馬上被全域預設擋下、之後也不會再有新的——要的是「把現在有的下下來」。選好字幕組之後「訂閱」旁邊多一個「只下載現有的」：就地走一次性 RSS 連結（不建 Feed、逐筆手動送單、排除條件不擋），網址是後端給的那一組單一 feed、作品與 Route 帶好。訂閱之後讀到的若有被排除的，回報說出幾筆、理由，並指向它。Nyaa / acg.rip 走搜尋頁、不做這一條；不在訂閱前預讀單一 feed 判斷「只有合集」（多一次請求，回報那一句已經接住）。
- **一次性 RSS 連結**：貼上 URL → 解析全部 item → 勾選 → 送單，不建立 Feed。**M3 票 18**：選一部作品與一條 Route（同一批共用）之後季集照那部作品換算、標出帳本已有與已經有下載的；送單逐筆走一般的手動送單（`trigger = manual`），不是 RSS 的路；排除條件只作用在自動下載，這裡只標出合集、不擋。
- **呈現**（M4 票 13，§19 2026-09-26「RSS Series 保留、以作品呈現」，`.scratch/m4/rss-series-shape.md`）：RSS 頁綁好的
  Series **作品一塊、字幕組一列**。來源說 Mikan 的番組名與字幕組名、不說數字 id；名字取自已經抓過的番組頁（自動綁定讀的、
  從 Media 頁訂閱時讀的），**不為了顯示多打 Mikan**，沒有就不顯示。列上說已入庫 / 下載中 / 排除各幾筆與最近**發佈**的
  那一集（不是長出它的那一筆），展開看它的每一筆 Item；Series 層的排除條件收進「進階」，Feed 層的在明處。**已完結**的
  收進段尾預設收起的「已完結」：TMDB 說完結（`status` 是 `Ended` / `Canceled`，§20.3）而且這個 Series 入庫過的那幾季
  每一集都在帳本裡、沒有在等或在路上的、最近一筆也發佈滿一週了，或最近一筆發佈之後 30 天沒有新的（試跑最長間隔
  22 天）。**不是存下來的狀態**，每次照現況算（`parser.finished`）：紀錄不刪（去重與重新出現時的綁定要它），新的一筆
  出現時——不論送了沒，排除、重複、v2 都算——條件自己不成立，它就回到清單。番組名另一個來源是單一 feed 的 channel
  標題（`Mikan Project - <番組名>`；補舊集與每日補漏本來就讀它）。
- **排序**：RSS 依賴解析器與管線，因此在 M3 而非 M1（§17）。

---

## 16. 部署與跨切面需求

### 16.1 部署

- 技術棧【決定】：後端 Python（FastAPI + 同一程序內的背景 worker + SQLite），前端 React（Vite），單一容器發佈。`/config` 存資料庫與設定，`/data` 掛媒體根。
- **目標環境【決定】**：Linux（NAS 與伺服器）與 Windows（Docker Desktop，WSL2 後端）。兩種使用者：NAS 使用者已有目錄規劃、可能已有 Jellyfin；一般電腦使用者什麼都沒有，要能「下載一份 compose、跑起來、開瀏覽器」就完成。
- 範例 `docker-compose.yml` 含 `berth`、qBittorrent、Jellyfin、Prowlarr，前三者掛同一個 `/data`（Prowlarr 不碰檔案）；權限採 TRaSH 的「單一使用者 + UMASK 022」簡化方案（§20.2），四個容器同 `PUID/PGID`。
- `/data` 一律用宿主目錄 bind mount（`DATA_ROOT`），Linux 與 Windows 相同：Windows Docker Desktop 的 NTFS bind mount 硬鏈接已實測可用（§20.7）。不支援 exFAT；健康檢查在建立 Route 時即驗證。
- 使用者文件明列（README 只留必讀，其餘在 `docs/guide/`，§19 第四輪審計 E7、M4 票 57）：硬鏈接前提（單一掛載、不可 exFAT、不可跨 btrfs 子卷 / ZFS dataset / mergerfs branch）、支援 Linux 宿主與 Windows Docker Desktop（NTFS）、qBittorrent 版本下限與必要設定（category autoTMM）、Jellyfin 版本下限 12.0，以及從 10.x 升級的注意事項（先完整備份、移除第三方插件、升級後完整掃描、不能降級，§20.9）、**使用者要自備 TMDB API key 與取得步驟**（§16.3）、TMDB 的歸屬聲明與 logo。

### 16.2 跨切面需求

- **外部呼叫**：統一逾時、重試與退避；服務不可達時 Job 停在當前狀態並記事件，不判定失敗；健康檢查頁顯示每個服務最後成功時間。
- **資料庫**：SQLite WAL；schema migration 從 M0 就用（Alembic）；備份就是複製 `/config`；提供「從磁碟 inode 掃描重建帳本」的災難復原指令（§7.9）。
- **秘密**：API key 存在 DB，靠檔案權限保護，不做應用層加密（與 Seerr 相同），`docs/guide/backup-and-reinstall.md` 註明。
- **日誌**：結構化，每行帶 job id；Event 是使用者可見層，log 是維運層，兩者不互相取代。網址的 query 值在 log（含 uvicorn 自己印的兩個 logger）與 `ServiceError` 的訊息（含 Prowlarr 的逐條理由）裡遮成 `***`，不認參數名（M4 票 76：httpx 的 INFO log 印過 Mikan 的個人 token）；守它的是 `tests/unit/test_logs.py` 與 `test_redact.py`。不是 `ServiceError` 的例外原文（Job、Feed 整輪失敗時寫的 `型別: 原文`）不遮：httpx 的例外都在 adapter 裡翻成 `ServiceError`，目前沒有帶網址的例外走到那裡。
- **安全**：所有 API 需登入；未來 AI / MCP 用個人 API token；容器非 root；不開 CORS 萬用字元。
- **測試**：解析 benchmark（純函式，CI 必跑）；管線整合測試用假的 qBittorrent / Jellyfin / TMDB adapter；docker compose 端到端至少覆蓋 M1 驗收流程。
- **i18n**：zh-Hant 與 en 並列，字串集中管理、一律走 key；檔名 token 與 log 一律英文。2026-09-07 改：原本是「UI 繁體中文優先，不做英文版直到有需求」，因確定面向英語自架者而推翻，見 `PRODUCT.md` 的 `## Users`。
- **授權**：MIT（與 Seerr、AutoBangumi 相同）。TMDB 條款限非商業使用，README 註明。

### 16.3 開箱即用（一鍵設定）【決定】

> **2026-10-06 改（§19「精靈審計後的八項」）**：介面密碼沿用頁 1 那一次（D4）、不寫入的確認鍵拿掉（D5）、頁 3 套件內自動跑（D7）、BTH 4 只接 Prowlarr（D3）。D5 的頁 2 已寫進下表與條列（M4 票 38），D4 已寫進「沿用 Jellyfin 帳密」那一條（M4 票 40），D7 已寫進下表的 Jellyfin 那一列（M4 票 43），D3 已寫進下表的 Prowlarr 那一列（M4 票 37、44）。

> **2026-09-29 改（§19「精靈改為每個服務手動選擇」）**：不再偵測服務是不是套件內。Jellyfin、qBittorrent、Prowlarr 各一頁，使用者自己選「套件內」或「既有」，選擇存下來、選完要測試。取代 2026-09-26「只有 compose 主機名上探到的才可能是套件內」的判定規則（M4 票 05 的判定那一半）；票 05 的「既有服務不寫帳密、不改全域偏好」保留，改讀使用者的選擇。選擇、服務頁與頁序在 M4 票 15 做完；compose 容器名（票 16）與既有服務防呆（票 17）另外做。
>
> 2026-09-26 改（§19 兩列）：「Berth 管理員」由「Jellyfin 擁有者」取代（M4 票 06），qBittorrent 與 Prowlarr 的介面帳密移到各自的泊位（M4 票 07）。

目標：新手使用者下載 compose 範本、`docker compose up`、開瀏覽器，之後所有設定都在 Berth 的精靈裡完成，不需要分別打開 qBittorrent、Jellyfin、Prowlarr 的介面。做法是「預置設定檔 + Berth 透過各服務 API 代為設定」，兩者都冪等，可重複按。

**唯一要離開 Berth 的一步是 TMDB 憑證**【決定 2026-09-09，閘門見 [ADR-0011](adr/0011-wizard-accepted-frictions.md)】：使用者得先去 themoviedb.org 註冊、在「設定 → API」申請一把 key，貼進精靈的 TMDB 泊位。Berth **不內建任何 provider 的 API key** —— 不替所有使用者背一把共用憑證（原本沿用 Seerr 的內建 key，§20.7）。代價是「開箱即用」缺了這一角，這是知情且接受的；相對地兩個 metadata provider（TMDB 與 §10 評估過的 TVDB）在「使用者自備 key」這件事上是對稱的。

| 服務 | 預置（compose 範本） | Berth 一鍵設定（API） | 使用者仍需自己做 |
| --- | --- | --- | --- |
| qBittorrent | **只預置「讓 Berth 進得去」**：只放行 Berth 容器固定 IP 的免密白名單（不是整個網段，理由見 §20.7）。原因是 4.6.1 起首次啟動的隨機密碼只印在容器 log，Berth 拿不到，沒有這一步按鈕就登不進去 | 套件內：設定介面登入（必填；可「沿用 Jellyfin 帳密」，見下文；不設的話它的介面只剩容器 log 裡每次重啟都換的臨時密碼，M4 票 07）。**全域偏好一個都不寫**（D2，M4 票 32）：送單逐個 torrent 帶 Berth 的分類與 `autoTMM=true`，save path 與未完成目錄開在分類上（M4 票 22），全域的 save path、autoTMM 都不影響 Berth。既有：填位址與 WebUI 帳密，同樣一個全域偏好都不寫（§16.4），**連線測試通過就做完**，沒有不寫入的確認鍵（D5，M4 票 38）。兩種都依 Route 建立 category | 無 |
| Jellyfin | 無 | 精靈第一頁選套件內或既有 → 那一台還沒跑過初始精靈就以擁有者填的帳密建立 Jellyfin 管理員、跑完它的初始設定；已經有管理員就用管理員登入 → Berth 自己建 API key「Berth」（帳密不存下來，M4 票 06）→ 媒體庫與路徑泊位：套件內建立使用者在精靈列的媒體庫（內容類型 + 名稱 + 資料夾，預設 Movies / TV / Anime 對應 `/data/library/{movies,tv,anime}`，可改名、增刪，M3 票 06f），既有只「加入 Berth 路徑」→ 每個媒體庫一個 Route。**套件內第一次來、清單沒改過時進頁就建立並檢查**，逐條 Route 顯示跑到第幾條檢查（D7，M4 票 43）；改過清單、跑過一次之後與既有，照舊按「建立並檢查」 | 無 |
| Prowlarr | 無；Berth 唯讀掛載其設定目錄讀取 API key（套件內零輸入） | 套件內：推薦清單（Nyaa.si、dmhy、Anime Tosho、ACG.RIP、Mikan、1337x、YTS、EZTV、The Pirate Bay；AniDex 於 2026-09-25 拿掉，§20.7）**一顆主鍵「測試推薦站，加入通過的」**：測還沒加入的推薦站、通過的加進去，結果逐站列出，測過而新增被拒的（Prowlarr 加之前自己再連一次，§20.7）單獨說、不算已加入；Prowlarr 已經有站時不給這顆鍵（M4 票 44）。逐站測試與勾選、schema 裡其他公開的 torrent 站收在「進階」：預設不勾、先測試通過才勾得起來再加入（M4 票 09，`indexer/test` 測還沒加入的定義，§20.7）；設定介面登入（與 qBittorrent 同一條「沿用 Jellyfin 帳密」規則，各自一組；自己的一顆按鈕，不跟著「加入」，M4 票 20）。既有：貼 API key，用使用者已有的索引站；一站都沒有時這一頁待處理，也可以測試推薦的公開站、按一次加進它（M4 票 20）；Berth 不移除它的站、不設它的登入。**可以不用**（審計 E3，M4 票 61）：精靈頁 4 的「之後再說」與設定 → Prowlarr 的「不用 Prowlarr」是同一個狀態，可逆；不用時健康不檢查它、BTH 4 是「沒有使用」不算阻擋，作品頁的搜尋說沒有接索引站、可以接 Prowlarr 或用 RSS 訂閱，Berth 不動它的站與容器 | 私有站的帳號 |
| TMDB | 無 —— **Berth 不內建任何 provider 的 key**【決定 2026-09-09】 | 無 | **必要**：自己申請一把 API key 貼進精靈的 TMDB 泊位（§20.7） |
| 索引站 / RSS | 無 | Mikan、Nyaa feed 由使用者貼 URL | 貼自己的 Mikan 訂閱 URL |

- **每個服務由使用者選來源，不偵測**（[ADR-0010](adr/0010-wizard-manual-service-selection.md)）：Jellyfin、qBittorrent、Prowlarr 各一頁，頁首二選一「套件內」/「既有」。Seerr 連 Jellyfin、加 Sonarr / Radarr，Sonarr / Radarr 加下載器，全都是手動填位址與憑證、按 Test，沒有自動偵測（§20.14）。選擇存下來，從此「套件內 / 既有」由它決定：套件內的連 compose 主機名，既有的填位址與憑證。NAS 使用者常見的組合是既有 Jellyfin + 套件內 qBittorrent 與 Prowlarr。原本的偵測（2026-09-26 起「只有 compose 主機名上探到的才可能是套件內」）說不出服務是誰的，只能靠「免密可進」「無索引站」這類跡象猜，猜錯就會寫使用者的服務（M4 票 05 的 bug）。
- **不偵測、不判定，但選完要測試**：選了套件內而 compose 沒起那個服務（`COMPOSE_PROFILES` 拿掉了）時，測試失敗要說出怎麼補：「把 `qbittorrent` 加回 `.env` 的 `COMPOSE_PROFILES` 再 `docker compose up -d`」。容器還在啟動的輪詢規則照舊（plan §9.3）。
- **只存驗過的憑證、錯誤標在欄位上**（M4 票 45，審計 E-6；§E 共同慣例 2、5：Home Assistant 驗過才 `create_entry`、`errors[欄位]`，Sonarr 存之前再測一次、錯誤綁欄位）：既有服務的位址與憑證、TMDB 的 key 都測過才存；測不過什麼都不換，已經有一組驗過的在用就照舊用它。錯誤分兩類標在各自的欄位旁——位址類（連不上、解不到、協定寫錯、回的不是這個服務、填了 localhost）標位址，憑證類（帳密或 key 被拒、被封、key 沒填）標憑證——其餘留在表單層級；人話、手動步驟、技術細節的分層照舊（M4 票 21、25）。
- **兩種來源接下來做的事一樣，只差誰讓服務登得進去**（§19 D1，M4 票 33）：Berth 只建立與管理自己擁有的物件——Jellyfin 的 API key「Berth」、Berth 路徑（既有）或清單上的媒體庫（套件內）、`berth-*` 分類、勾選加入的站——不碰全域偏好與帳密（清單與能不能撤回見 §16.4）。套件內多出來的只有 bootstrap：Jellyfin 的管理員與初始設定、qBittorrent 與 Prowlarr 的介面登入、免密白名單（預置）、掛載的 Prowlarr API key；既有由使用者給憑證。
- **表單跟著那一台的狀態走**：套件內但已經初始化過（重裝保留了 config、精靈中途中斷）時，Jellyfin 已有管理員就改成「用管理員登入」、不再建立；qBittorrent / Prowlarr 已設過介面登入同理，不強迫再設——連線測試時就讀到它設過的帳號，頁 2 測試通過即完成，不必再按一次「套用」（D5，M4 票 38；Prowlarr 那一頁的站另算）。選既有而那台 Jellyfin 還沒跑過初始精靈時，一樣由擁有者建管理員、跑完它的初始設定（語言與地區、遠端存取在畫面上問）——它上面沒有任何人的帳號可以蓋掉（2026-09-26 的「Jellyfin 例外」，理由不變）；這是既有服務唯一的 bootstrap。
- **「沿用 Jellyfin 帳密」**：精靈裡套件內 qBittorrent / Prowlarr 的介面登入上的一個勾選，**不預設勾**（M4 票 80：頁 1 帶了一組過來時那兩頁自動送、不出現欄位，沒帶時預設勾就等於再問一次 Jellyfin 密碼；**只在精靈**：設定頁是一般的改帳密表單——目前的帳號、帳號、新密碼兩次、儲存——頁 1 沒打過密碼，「沿用」在那裡讀起來像沿用上次的設定，M4 票 78）。勾選時帳號帶入擁有者的名字，Berth 先向 Jellyfin 驗證這組帳密正確再寫入；不勾就自設一組、密碼打兩次（M4 票 07 的欄位）。擁有者的名字不合 qBittorrent 的規則時頁 2 的勾選停用並說原因（不是勾了才紅）。**密碼只問一次**（§19 D4，M4 票 40）：頁 1 建套件內 Jellyfin 的管理員時預設勾「套件內 qBittorrent 與 Prowlarr 的介面也用這組」，密碼只留在精靈那一個瀏覽器分頁的記憶體裡（不寫 storage、不送給 Berth 存），頁 2、頁 4 那一台還沒有介面登入時自動以沿用送出，不出現密碼欄，設好之後只說「已沿用 Jellyfin 帳密（擁有者）」與「改用另一組」（M4 票 80）；重新整理、沒勾、頁 1 是登入既有的管理員（沒有「設一組」）、或 Jellyfin 不再收那一組時，那兩頁照舊問介面登入：沒帶的是自設的三格，勾起「沿用」就只打一次 Jellyfin 密碼；Jellyfin 不再收那一組時欄位打開在「沿用」，打的是新的 Jellyfin 密碼。「已沿用」照後端記的 `web_ui_login_reuses_owner`（M4 票 104，推翻票 80 的「看這個分頁最後一次設下的是不是帶過來的那一組」：重新整理之後同一個狀態說成「帳號：擁有者」＋「更換登入」），不看帳號（「改用另一組」只換密碼時帳號一樣）；手動勾「沿用」設的也說已沿用。頁 1 的帳號與密碼不合 qBittorrent 的規則（M4 票 26）時頁 1 就擋：「也用這組」邊打邊停用並說原因，帶不過去（M4 票 80，推翻票 40 的「到頁 2 才說不能沿用」——同一件事在頁 2 又被表單的預設勾選說一次）；只有 qBittorrent 不合時也整格停用，不拆成只給 Prowlarr——那一格答應的是「兩台都用這組」，頁 4 照樣勾得起「沿用」。完成頁照 `web_ui_login_by_berth`（Berth 記著那一組的密碼雜湊）說登入是精靈設的、那一台原本就有的（重裝保留 config，並說忘了去「設定 → 該服務」的「介面登入」換一組），或還沒設；精靈設的那一組是沿用 Jellyfin 帳密時（`web_ui_login_reuses_owner`，寫進去的那一刻記下，M4 票 68）直接說「與 Jellyfin 同一組」；不看登入那一條纜繩——Prowlarr 的「加入」每次以不帶登入重算它，Berth 設好的也記成 `skipped`。**Berth 不存這兩組介面密碼的明文**，只記帳號與加鹽雜湊，夠比對「已經是這一組」（§19 2026-09-29：勾了沿用時那就是 Jellyfin 的密碼，存明文會推翻 M4 票 06「資料庫裡沒有擁有者的明文密碼」；Berth 連套件內 qBittorrent 靠免密白名單，本來就用不到它）。
- compose 用 profiles（[ADR-0009](adr/0009-deploy-compose-and-env.md)）：`.env` 的 `COMPOSE_PROFILES=jellyfin,qbittorrent,prowlarr` 預設全起。選「既有」時精靈說出要從 `COMPOSE_PROFILES` 拿掉哪幾個（不叫人改 compose 檔）：那一頁只說套件內那一台用不到了，那一行與停掉的指令照整份選擇在完成頁給一次（M4 票 103；原本頁 1、2、4 各給一次，一頁比一頁短）；忘了拿掉也不致命。套件的容器名是 `berth-jellyfin` / `berth-qbittorrent` / `berth-prowlarr`（`berth` 維持；compose 服務名與 DNS 名不變）：同一台主機上既有的容器多半就叫 `jellyfin` / `qbittorrent` / `prowlarr`、用 8096 / 8080 / 9696 / 6881。沒有前綴時撞名會讓**整套**起不來（連 `berth`），所以加了前綴；撞 port 仍可能發生，只有撞到的那一個套件內容器起不來（M4 票 16 實測，§20.14）。
- 預置只補設定檔裡沒有的鍵（缺鍵才補，§20.7），已經有值的不動，之後使用者在各服務介面改什麼都行——包括關掉白名單，那時重啟補不回來，補法在 qBittorrent 的 WebUI（M4 票 53）。沒有「建議設定」可漂移：Berth 不寫也不看 qBittorrent 的全域偏好（D2，M4 票 32；原本的漂移檢查與「還原建議設定」一起拿掉）。精靈的 qBittorrent 頁會列出「已預置的項目」。
- 每顆按鈕都顯示「將會做什麼」與執行結果，失敗給出可複製的手動步驟。
- 各服務 API 的可行性與細節見 §20.7；手動選擇的慣例與既有服務的條件見 §20.14。

### 16.4 既有服務的接入規則【決定】

> **2026-10-14 補（審計 P1-10、P1-11，M4 票 66）**：物件表補上送出的 torrent 與它的 tag `berth`、送單時重建被刪的 `berth-*` 分類、Jellyfin 的裝置紀錄；套件內 Prowlarr 的「移除」只給 Berth 加的站（原本是「Berth 加得回去的」，使用者自己加的公開站也移除得掉）；閘門加一輪執行期。「不用 Berth 了」要手動清的寫在 `docs/guide/uninstalling.md`。已寫進下文。

> **2026-10-14 改（§19「第四輪可用性審計的八項」E1，M4 票 64）**：既有 Jellyfin 也建媒體庫——只建使用者在頁 3 勾了「新建一個媒體庫」的那一個，算 Berth 擁有的物件（推翻下表原本的「既有：不建」）；類型對得上的既有媒體庫預設勾選（審計 C2）。已寫進下文。

> **2026-10-06 改（§19「精靈審計後的八項」D3、D6）**：Prowlarr 不再接受 Torznab 端點（D3，已在 M4 票 37 改寫進下文）；換台時列出舊那台的遺留物（D6，M4 票 47 改寫進下文，表後〈換一台時〉）。（D1 已寫進下文「接管＝只建立與管理 Berth 擁有的物件」那一段，M4 票 33。）

> **2026-09-29 改**：「既有」由使用者在該服務那一頁選（§16.3），不再由偵測判定；本節的條件在「既有」選項旁說明（M4 票 15、17）。

允許接入既有服務；NAS 使用者是主要客群，Seerr 與 Sonarr 也都支援。問題只有一類：路徑與檔案系統邊界。

**接管＝只建立與管理 Berth 擁有的物件**（[ADR-0013](adr/0013-berth-manages-only-its-own-objects.md)，§19 D1，2026-10-06 使用者拍板，M4 票 33）。套件內與既有是同一條，差在套件內由 Berth 讓服務有人登得進去（§16.3）。理由是 2026-09-26 `berth-lab` 的兩件事（§19）：使用者自己的 Prowlarr 被覆寫登入、既有 qBittorrent 的全域 `save_path` 被改成 Berth 的目錄；Sonarr / Radarr 對下載器同樣只用自己的分類、不碰全域。Berth 擁有的物件都是獨立的一件，刪掉它不動使用者原有的任何東西：

| 物件 | 套件內 | 既有 | 在 Berth 能撤回嗎 | 撤不回時怎麼辦 |
| --- | --- | --- | --- | --- |
| Jellyfin 管理員帳號 | 那一台還沒初始化時建 | 只在那一台還沒初始化時建（唯一的例外） | 不能 | Jellyfin 的使用者管理 |
| Jellyfin 語言、地區、遠端存取 | 還沒初始化時設（跟 UI，不開遠端） | 還沒初始化時設（畫面上問） | 不能 | Jellyfin 控制台 |
| Jellyfin 伺服器名稱 | 還沒初始化時設成「Berth」（M4 票 52） | 不設（初始設定照跑、不帶名稱：Jellyfin 清成空字串、報 hostname，§20.9） | 不能 | Jellyfin 控制台「一般」 |
| Jellyfin API key「Berth」 | 建 | 建 | 不能（Berth 不刪）；在 Jellyfin 刪掉之後 Berth 偵測得到，請你重新登入換一把 | Jellyfin「API 金鑰」頁 |
| Jellyfin 媒體庫 | 建精靈清單上的 | 只建頁 3 勾了「新建一個媒體庫」的那一個（M4 票 64）：`<library root>/<slug>`，與套件內同一條路徑，同名的已經在就不再建；伺服器上所有使用者都看得到，所以預設不勾。名稱只差大小寫、或資料夾已經是別的媒體庫的路徑時擋下 | 不能；套件內已建的在 Berth 裡鎖住，既有那一台建好之後就是清單上的一個媒體庫 | Jellyfin 刪 |
| 媒體庫上的 Berth 路徑 | — | 頁 3「建立並檢查」時加；類型對得上的媒體庫（電影、劇集）預設勾選、預設寫入目標是這一條（審計 C2，M4 票 64）。**同一個資料夾不給第二個媒體庫**：兩個名字算出同一個 slug 時（`TV Shows` 與 `TV-Shows`），後加的那個失敗（`path_taken`），slug 規則不改（M4 票 64） | 不能；頁 3 的檢查失敗也留著 | Jellyfin 媒體庫設定移除 |
| 請 Jellyfin 去看 Berth 寫的路徑（M4 票 62） | 同右 | 入庫後通知那幾條路徑（`POST /Library/Media/Updated`）；反查還沒找到時只刷新那條 Route 的媒體庫；**Berth 的路徑 Jellyfin 還沒列出過任何東西時（空的媒體庫第一次入庫、剛加上 Berth 路徑的媒體庫），跑整台的「掃描媒體庫」排程任務，你其他的媒體庫也會一起被掃**——只有它建得出那個路徑（§20.1）；路徑還沒被列出之前，反查每一次沒找到都會再請一次（它還在跑時再請是空操作）。Issue 的「重新掃描媒體庫」照同一條 | 不留下東西 | — |
| qBittorrent 免密白名單 | 預置（容器啟動前，只放 Berth 的 IP） | 不碰 | — ；換走套件內那一台時換台框列出它與關法（M4 票 65） | `qBittorrent.conf`，或它的 WebUI「選項 → WebUI → 驗證」取消勾選（重啟不會再打開：預置腳本只補沒有的鍵，M4 票 53） |
| qBittorrent 全域偏好 | 不寫（D2，M4 票 32） | 不寫 | — | — |
| qBittorrent 介面登入 | 設 | 不碰 | 只能再設一組蓋過 | qBittorrent 偏好 |
| `berth-*` 分類與它的 complete / incomplete 目錄 | 建 | 建；**送單與 Route 檢查都先 `ensure_category`，你在 qBittorrent 刪掉的會照 Route 的路徑重建**（路徑開在分類上，沒有它 torrent 就落到全域的儲存路徑，M4 票 66） | 刪 Route 不刪分類；換一台時換台框可勾選一併移除舊那台上**空的**，確認換台才移除（M4 票 47、65），目錄不刪 | 先刪 Route（之後不再重建），再在 qBittorrent 刪分類 |
| Berth 送出的 torrent，帶 tag `berth`（M4 票 66） | 送單時加 | 同左 | 刪 Job 時勾「從 qBittorrent 移除」：只移除 torrent，**不刪檔**（§9.2） | qBittorrent 刪 torrent；tag 讓你在它的介面上篩出 Berth 放的 |
| 探測 torrent、探測檔（頁 2 在 `/data`、校驗不完，M4 票 46；頁 3 在分類路徑；頁 1 給既有 Jellyfin 的 `ValidatePath` 看的探測檔在 `/data`，沒有 torrent，M4 票 63） | 暫時，自清 | 同左 | 自清（Berth 中途崩潰、或答完之後移除那一下 qBittorrent 斷線時可能殘留：停住、沒有分類，M4 票 54） | 手動刪 |
| Prowlarr 站 | 加勾選的 | 加勾選的 | 套件內可單站移除 **Berth 加的**（`SetupIndexer.added_sites`；票 47 之前加的沒有紀錄，照實說、不給移除；使用者自己加的公開站也不給，M4 票 66）；既有不移除 | Prowlarr 刪 |
| Prowlarr 介面登入 | 設 | 不碰 | 只能再設一組蓋過 | Prowlarr 設定 |
| Jellyfin 的裝置「Berth」（DeviceId `berth-server`，M4 票 66） | 登入過 Berth 的每一位 Jellyfin 使用者一筆：Berth 沒有自己的密碼，登入是交給 Jellyfin 驗，Jellyfin 為每次登入發權杖、記一筆裝置；同一位再登入是換掉自己那一筆（§20.22） | 同左 | 不能 | Jellyfin 控制台「裝置」刪 |
| TMDB | 不寫 | 不寫 | — | — |

**換一台 qBittorrent / Prowlarr 時**（§19 D6，M4 票 47）：確認框列出 Berth 在原本那一台擁有的物件——`berth-*` 分類各有幾個 torrent、Berth 加進去的站（Berth 加站時記下 `definitionName` 與站名，`SetupIndexer.added_sites`；票 47 之前加的沒記到）、Berth 設的介面登入（只有 Berth 記著雜湊的那一組）。使用者自己的分類與站不列；原本那一台是套件內 qBittorrent 時多列預置的免密白名單，說它在 `qBittorrent.conf`、在 WebUI 怎麼關（M4 票 65）。連不到那一台時列 Berth 記得的（分類取自 Route、站取自那份紀錄），照實說確認不了現況。**分類裡的 torrent 留在原本那一台**（做種的照樣做種、下載中的照樣下載），Berth 換台之後不再追蹤它們、已入庫的檔案不受影響，那一台關掉做種就停——換台框照數目說（連不到時不說數目）；換台之後，送進原本那一台、已入庫的 Job 詳情說「做種的 torrent 在原本那一台」（讀最後一次 `submitted` 事件記下的 `client`，與現在那一台不同才說；不知道的不說，M4 票 65，審計 P1-4）。**還沒下完的 Job 例外**（M4 票 102）：poller 在新那一台上找不到它們的 torrent，照 plan §3.1 各開一件 `client_removed`；換台框照實說並列出名字（`in_flight`：poller 每一輪到 qBittorrent 裡找的那幾種狀態，讀 Berth 自己的 Job，連不到原本那一台也列得出），那件 Issue 的「重新送單」送到的就是新那一台。換台本身不改它們的狀態。**設定頁「改位址」從一台既有換到另一台既有也是換台**（存下的位址不同就是，`ServiceChoice.is_at`；存之前去掉頭尾空白與結尾的 `/`）：同一份說明與清單就地加在表單裡，「測試連線」就是確認（M4 票 102）。同一台 qBittorrent 只是 IP 換了，Berth 一樣當成換台——qBittorrent 沒有認得出同一台的方法（§20.2〈同一台 qBittorrent 認不出來〉）。**能移除的只有空的 `berth-*` 分類**；站與登入只列出——站可能有人在用、登入拿掉就沒人登得進去。**移除是換台框裡的勾選（預設不勾），跟著確認換台一起做**（`POST /setup/services/qbittorrent` 的 `remove_empty_categories`，M4 票 65，審計 P2-9；推翻票 47 的「移除在確認框裡就做」）：在新那一台測過之後、存下之前移除，確認時重數；取消就什麼都不動，換成既有時新那一台測不過也不動（套件內照舊先存再測，選了就換過去）；勾了而原本那一台沒答上來，整個換台不做（502 `categories_not_removed`），取消勾選再換一次就只換台。**換成功之後 Route 自動重查**（M4 票 59，審計 P1-3）：所有 Route 的檢查作廢，健康頁的媒體庫路徑那一格是「要重新檢查」而不是「已繫上」；設定 → qBittorrent 在新那台測過之後自動跑一次「全部重新檢查」（分類建在新那台、探針重問），說「正在重新檢查 N 條 Route」、逐條進度、跑完說幾條過了。結果出來之前送單照舊——還沒檢查完的放行（送單自己建分類），紅了的才擋。探針從沒問過的 Route 同樣不算「已繫上」。

閘門是 `tests/integration/test_setup_owned_writes.py`：整個精靈經 API 跑套件內一輪、既有兩輪（Jellyfin 初始化過與還沒），三台替身收到的每一個寫入都要對得上「Berth 擁有的物件 + 套件內的 bootstrap」那張白名單；既有那一輪的 bootstrap 只放行那台 Jellyfin 還沒初始化，建媒體庫只放行勾了的、在 library root 底下的（M4 票 64，沒勾也建、建在 root 外各有變異測試）。**執行期另一輪**（M4 票 66）經 services 走送單、缺檔按「重新校驗」、下載完成、入庫、反查（全庫掃描與只刷新媒體庫兩條）、六次用完按「重新掃描媒體庫」、刪 Job，同一張白名單：送單只能是 `berth-*` 分類、表單上的 tag 只有 `berth`、路徑交給分類；重新開始、校驗、移除只能對 Berth 送的（或探測的）torrent，移除不刪檔；通知的路徑在 library root 底下、只刷新 Route 的媒體庫、排程任務只能是「掃描媒體庫」；每一條都有紅綠雙向的變異測試，tag 與刪檔另各有一條走完整流程的。套件內 Prowlarr 的移除只放行這一輪 Berth 加的站，不寬於程式（`added_sites`）。它只看得到 Berth 經三個服務的 adapter 送出的寫入，**不在範圍**的：預置的免密白名單、掛載的 key、探測檔的自清與 Berth 對 `/data` 的磁碟操作；Jellyfin 的裝置紀錄（登入是讀）；標已看（使用者自己按、寫他自己的觀看紀錄）；換台時移除空分類那一顆（白名單列只用合成的寫入驗，行為由 `test_setup_leftovers.py` 守）。頁 1、頁 3 問 Jellyfin 的 `ValidatePath` 是讀（POST 但不留東西），白名單不放行任何東西；閘門另外斷言既有那一輪頁 1 真的問了 `/data`（M4 票 63）。

- **唯一的硬規則**：Berth、qBittorrent、Jellyfin 三個容器在**同一台主機**、把同一個宿主父目錄掛在**相同的容器路徑**，且下載目錄與媒體庫目錄都在它底下（TRaSH 的單一 `/data` 掛載，§20.14）。Berth 的 incomplete / complete 根目錄固定在 `/data/torrent/{incomplete,complete}`，所以 Berth 與 qBittorrent 的共用掛載要掛在 `/data`（M4 票 22：原本寫「根目錄可設定」，程式從來沒有那個設定）；媒體庫路徑讀自 Jellyfin。**這是既有 qBittorrent 與 Jellyfin 最關鍵的條件**：在另一台 NAS 上的接不上；只掛了 `/downloads`、`/tv` 的，**多加一條 `${DATA_ROOT}:/data` 就好，原本的掛載不動**（M4 票 36，審計 §C2：Berth 只在 `/data` 底下讀寫，叫人把下載目錄搬過去反而讓舊 torrent 找不到檔案）。「既有」選項旁說明這個條件（容器路徑只能是 `/data`、`DATA_ROOT` 要建得了硬鏈接；缺某類型的媒體庫時頁 3 勾了才建，M4 票 64）；媒體庫與路徑泊位的探測檔 / 硬鏈接檢查失敗時，給那一台要多加的那一條（compose、`docker run` 與 Unraid 模板「Add another Path」三種寫法，M4 票 08、36、63），**宿主那一側是 Berth 的 `DATA_ROOT` 真正的值**：compose 把 `.env` 的原字串傳成 `HOST_DATA_ROOT`，Windows 的反斜線換成 `/`，相對路徑（`./data`）說它相對於 Berth 的 docker-compose.yml、要換成絕對路徑（M4 票 63，審計 P1-6：原本是 `${DATA_ROOT}`，要人自己去 `.env` 找）。**少了 `/data` 提早說**：qBittorrent 在頁 2 測連線時（M4 票 46），既有 Jellyfin 在頁 1 成為擁有者、Berth 拿到 key 之後（M4 票 63，與頁 3 同一種探測檔加 `ValidatePath`；不擋頁 2），之後每次重新測試、設定頁換位址也問，看不到就不存新位址——與 qBittorrent 的測過才存同一條（M4 票 45）。
- **既有服務要給的東西各不相同**（§20.14）：
  - Jellyfin：位址 + **管理員**帳密（不是管理員就拒絕，M4 票 06）；Berth 以它登入、自己建 API key。版本下限 12.0（§19 2026-09-15，2026-09-29 使用者再確認），**測連線時就擋**（M4 票 18）。擁有者成立之後只能換到**同一台**的另一個位址（ServerId，§20.15）。還沒初始化的那一台由擁有者表單建立管理員，語言與地區、遠端存取在畫面上問（預設 UI 語言、不開遠端存取）。
  - qBittorrent：位址 + WebUI 帳密。版本下限 4.4（Web API 2.8.4）。5.2 起它有 API key（`Authorization: Bearer`），之後可當第二種接法，這一輪不做。
  - Prowlarr：位址 + **API key**（Prowlarr 的「設定 → 一般 → 安全性」）；它的 API 只收 API key，帳密只給瀏覽器登入。Berth 用使用者已有的索引站；**一站都沒有不算完成**，可以在 Prowlarr 加站後重新讀取、在精靈測試推薦的公開站並按一次加進它（M4 票 67 起與套件內同一顆「測試推薦站，加入通過的」，畫面列出站名與它的位址），或之後再說（§19 2026-09-30，M4 票 20）。Berth 不移除它的站、不設它的登入。版本下限 1.3.2（卡住它的是匿名的 `/ping`，§20.14，M4 票 17）；版本從 `system/status` 讀，比 1.3.2 舊、沒有 `/ping` 的那一台也說得出版本（M4 票 20）；key 錯說「API key 不對」而不是連不上。
  - 三個服務的下限都寫在「既有」選項旁（M4 票 17），版本太舊時精靈與健康檢查說出目前版本與下限。
- **容器裡的 `localhost`**：使用者填 `localhost` / `127.0.0.0/8` / `::1` 時，位址欄下就地提示（只提示、不擋：`network_mode: host` 的部署填 `localhost` 是對的；測試不過時的補法也是同一句，那時位址欄下的提示收起來、不說兩遍，M4 票 17、63）：Berth 在容器裡，那指的是 Berth 自己；要填宿主的區網 IP 或 `host.docker.internal`（Docker Desktop 內建；Linux 由 compose 的 `extra_hosts: ["host.docker.internal:host-gateway"]` 提供），服務要監聽 `0.0.0.0` 而不是 `127.0.0.1`（§20.14，M4 票 16、17）；rootless Docker 上 `host.docker.internal` 連不到宿主，只有區網 IP 會通，提示照說（§20.14，M4 票 42、72）。
- **既有 Jellyfin 不搬媒體庫**：Jellyfin 的項目 ID 由路徑算出，改路徑等於全部變成新項目、觀看紀錄歸零。做法是用 Jellyfin 的「一個媒體庫多個路徑」：Berth 按鈕以 `POST /Library/VirtualFolders/Paths` 為既有媒體庫**加**一個 Berth 用的路徑（§20.7），Route 指向新路徑；舊媒體原地不動，在 Berth 只是 unmanaged 檔案。缺某類型的媒體庫時，頁 3 勾了「新建一個媒體庫」Berth 才建一個新的（`POST /Library/VirtualFolders`，與套件內同一條路徑），舊的一個都不動（M4 票 64）。送出前先寫探測檔問 Jellyfin 看不看得到：它對加不上的路徑只回 404，說不出原因；看不到就說「Jellyfin 看不到 <路徑>：它沒掛 <共用目錄>」、收回剛建的目錄。多個媒體庫逐個試、逐個回報（M4 票 19）；畫面上「看不到」合併成一則、列出受影響的媒體庫——那是整台沒掛 `/data`，補法只給一次（M4 票 63，審計 C5）。
- **既有 qBittorrent 不搬舊種、不改全域偏好**（套件內那一台的全域偏好同樣不寫，D2，M4 票 32）：使用者多加一個掛載，Berth 用自己的 `berth-*` category 與新的 save path；舊 torrent 留在原目錄，Berth 忽略非自己分類的 torrent。全域的 save path、temp path、autoTMM 一個都不寫、也不列在精靈上（M4 票 05、22；Sonarr / Radarr 對下載器同樣只用分類）——改了它們，使用者不經 Berth 加的 torrent 就會落進 Berth 的目錄，而它們沒有一個影響 Berth。全域 autoTMM 關閉也無妨，Berth 送單時逐個 torrent 指定 `autoTMM=true`；全域未完成目錄沒開也無妨，Berth 的分類各自帶 `downloadPath`（原本的「temp path 未啟用只警告」撤掉：警告的理由「Berth 比較難分辨下載完」不成立，完成看的是 qBittorrent 回報的 progress / completion_on / state）。票 22 之前建的 Berth 分類沒有自己的未完成目錄，照舊跟著全域設定下載、不算衝突；有而且不同才照衝突規則處理、不覆寫。
- **健康檢查會擋下的情況**：qBittorrent 回報的**分類**路徑（save path 與分類自己的未完成目錄）在 Berth 看不到——全域的預設 save path 不看，兩種來源都一樣（M4 票 32）；qBittorrent 讀不到 Berth 寫進分類路徑的探測檔（M4 票 19）；Route 的寫入目標在 Berth 看不到（媒體庫的其他路徑不驗：Berth 只在寫入目標底下讀寫，舊的 `/movies` 看不到不礙事，M4 票 19）；兩者在 Berth 內是不同掛載（`link()` 回 `EXDEV`）；qBittorrent 低於 4.4；Prowlarr 低於 1.3.2；Jellyfin 低於 12.0（說出目前版本，附升級注意：先完整備份、移除第三方插件、升級後完整掃描、不能降級，§20.9）；媒體庫掛 TVDB 插件（警告，M2 票 09c 起是一件 `library_uses_tvdb` Issue，§9.1）。每項附「哪個容器少了哪個掛載」的 compose 修正片段，**片段對著要改的那一台**（M4 票 19）：寫入目標看不到、Jellyfin 看不到探測檔是 jellyfin；qBittorrent 讀不到探測檔是 qbittorrent；Berth 看不到 qBittorrent 報的路徑與 `EXDEV` 才是 berth。既有服務的片段是「你原本那一份」要多加的一條 `/data`（compose、`docker run -v` 與 Unraid 模板，帶著 `DATA_ROOT` 的值，M4 票 36、63），原本的掛載不動（M4 票 36）。
- **跨主機驗證**：Berth 在 Route 目標寫一個探測檔，再以 `POST /Environment/ValidatePath` 請 Jellyfin 確認看得到同一路徑（§20.7）；Jellyfin 在別台機器而路徑不一致會立刻現形。
- **不支援**：Jellyfin 10.x（2026-09-15 起只支援 12 以上，§19）；既有 qBittorrent 或 Jellyfin 與 Berth 不在同一台主機、或沒有把 Berth 的 `DATA_ROOT` 掛在容器路徑 `/data`（硬鏈接做不到）；remote path mapping（不做，§18；2026-09-29 使用者再確認）。

---

## 17. 里程碑（tracer bullet）

每個里程碑結束時 repo 都可運作、可部署。

| 里程碑 | 內容 | 驗收 |
| --- | --- | --- |
| **M0 骨架** | §20.6 的實驗（結果可能改變命名決定，所以最先做）、compose 範本（profiles）與最小預置、精靈（建立管理員、逐服務判斷套件內或既有、套件內服務全自動設定、既有服務連線與確認按鈕）、Route 建立、健康檢查 | 實驗結論寫回本文件；在乾淨的 Linux 與 Windows Docker Desktop 上 `docker compose up` 後只操作 Berth 即完成設定，四項健康檢查綠燈；另以「既有 Jellyfin + 套件內其餘服務」的組合走一次 |
| **M1 手動全流程** | 探索 → 詳情 → 索引站搜尋 → 送 qBittorrent → 輪詢 → 規則 planning → 硬鏈接 → 掃描 → 媒體庫頁顯示可播放 + 深連結；Job 時間線；benchmark v0 | 一部美劇一季、一部動漫一季、一部電影，三者不經人工入庫並在 Jellyfin 正確顯示 |
| **M1.5 媒體庫瀏覽** | 媒體庫與 Media 詳情像 Jellyfin 那樣瀏覽（§12、§13）：整個 Jellyfin 媒體庫疊上 Berth 狀態、繼續觀看、下一集、已看 / 未看與切換、類型與年份排序、Jellyfin 的圖、選季選集；播放深連結到 Jellyfin | 以一般使用者登入，不開 Jellyfin Web 就能找到要看的那一集、看到自己的進度並標記已看，按播放落在 Jellyfin 的那一集；Jellyfin 不讓這位使用者看的媒體庫，在 Berth 也看不到 |
| **M2 修正與對帳** | Review Queue、Unmatched 指派、rematch、Reconciler、刪除範圍、重新入庫、`berth rebuild-ledger`（§16.2 的災難復原指令）、Job 詳情頁 | 刪掉 library 後可一鍵重建；Issue 表對三種人為破壞都能偵測；medium 自動入庫可一鍵撤銷；`user` 看不到也按不到審核與刪除 |
| **M3 RSS** | Mikan、Nyaa、acg.rip adapter、RSS Series 自動綁定、排除條件、去重、補舊集、一次性連結 | 聚合 feed 加一個搜尋 feed 全自動追完，中途訂閱的補齊舊集（§15） |
| **M4 巡檢與通知**（2026-09-22 加、09-24 改並排到 AI 之前） | 每日程式檢查、每週週報；`events` 訂閱者、channel adapter（Discord）、每人的訂閱設定（§14） | RSS 命中 → 入庫 → Jellyfin 可見的全程，手機收到「正在下載」與「可以看了」；進審核的事推出「等你處理」；週報說得出這週入庫與修正了什麼 |
| **M5 AI 地基與對話 agent**（2026-09-24 改、10-27 再改） | 命令登錄表與執行器、Proposal、provider、防護與記帳、側面板對話（工具、確認卡、外部資料、skills、壓縮、斜線指令）、觀測頁（§6.10、§14） | 側面板說「下載 Re:Zero 全系列」得到逐列可勾的總覽卡，按確認後送單；「為什麼這集沒入庫」答得出卡在哪；AI 不能在沒人確認下執行不可逆的命令；重啟之後舊卡片按得下去；關掉 AI 時與 M4 相同 |
| **M6 人工接管開關**（2026-09-22 加、10-27 改） | 決定點的人 / 影子 / AI 開關、背景 AI 任務（含 Issue）、影子一致率、AI 活動與撤銷（§6.10、§14） | 影子模式一週與人一致率達標；benchmark `auto_wrong` 不升、review 比例下降；一件 `library_link_missing` 不經人修好；刪 complete 的請求停在 Proposal |
| **M7 Discord 與 MCP**（2026-09-22 加、10-27 改） | M4 的 Discord bot 接上同一個核心、確認卡帶按鈕、個人 API token、MCP server（§14、§16.2） | 手機上收到通知、回一句話、按確認之後完成；Claude Code 經 MCP 查得到本週入庫 |
| 之後 | RSS 的 offset 建議（Mikan 開播日對 TMDB 播出日，§15〈offset 建議〉，看第一批改正的頻率決定）、Jellyfin Webhook（§9.5，社群回報不可靠）、字型與字幕解壓、多使用者審批、非影片媒體、MCP server | — |

---

## 18. 明確延後或不做

| 項目 | 處置 | 理由 |
| --- | --- | --- |
| complete / incomplete 鏡像 library 結構 | 不做 | §4.2 |
| library 內的 `unmatch` 資料夾 | 不做，改為 UI 列表 | §7.4 |
| 內嵌播放器 | 延後（M1.5 的媒體庫瀏覽照樣跳到 Jellyfin 播放） | §12 |
| AI 解析 | M5 | 先有 benchmark 才能評估 |
| 品質升級自動替換 | 不做 | 版本並存（Jellyfin 12 原生合併）已滿足；升級邏輯是 Sonarr 最複雜的部分 |
| remote path mapping | 不做（2026-09-29 使用者再確認） | 強制同路徑掛載更簡單、更不易錯；既有服務的條件在精靈講清楚（§16.4） |
| 多 provider（TVDB / AniList） | 延後 | §10 |
| 字型安裝、字幕解壓、OST 入音樂庫 | 延後 | 非核心流程 |
| BDMV 原盤 | 只辨識不處理 | 需要 Jellyfin 端特殊結構 |
| 多使用者審批、配額 | 延後 | 角色模型已預留 |
| 通知 | M4 | §14、§17（2026-09-22；09-24 排到 AI 之前） |
| AI 助理（側面板、外部對話、MCP） | M6 / M7 | §14、§17（2026-09-24 重排）；M5 的 AI 核心先到 |

---

## 19. 決策紀錄與待決問題

決定的「為什麼」在 `docs/adr/`（下表）；正文只寫現況。2026-09-07 起的 54 列決策紀錄原文封存在 `docs/archive/<里程碑>.md` 的 `## brief §19` 段，里程碑照列的日期。

### ADR 索引

| 編號 | 決定 |
| --- | --- |
| [0001](adr/0001-indexer-manager-prowlarr-only.md) | 索引站只接 Prowlarr，不支援 Jackett 與通用 Torznab |
| [0002](adr/0002-jellyfin-12-minimum-pinned-image.md) | 只支援 Jellyfin 12 以上，套件內 image 釘在 12.1 線 |
| [0003](adr/0003-remove-route-profile.md) | 移除 Route profile，改由兩條證據決定絕對編號換算是否自動入庫 |
| [0004](adr/0004-library-browsing-and-discovery.md) | 媒體庫像 Jellyfin 那樣瀏覽：一庫一頁、Berth 代理圖片、探索頁只放 TMDB 牆 |
| [0005](adr/0005-display-title-follows-ui-language.md) | 顯示用標題跟著 UI 語言走，檔名只用英文 |
| [0006](adr/0006-review-and-issues-split.md) | `/review` 只列入庫決定，Issue 只在 `/issues` |
| [0007](adr/0007-rss-series-model.md) | RSS 以 RSS Series 為單位：全部接受只排除、補齊舊集、Feed 必選 Route |
| [0008](adr/0008-ai-autonomy-and-optional-ai.md) | AI 對可撤銷的命令自己執行；沒有 AI 也完整可用 |
| [0009](adr/0009-deploy-compose-and-env.md) | 部署只用 compose 檔加 `.env`，`.env` 只放主機端事實 |
| [0010](adr/0010-wizard-manual-service-selection.md) | 精靈每個服務手動選「套件內」或「既有」；精靈只管第一次 |
| [0011](adr/0011-wizard-accepted-frictions.md) | 精靈刻意保留的兩個摩擦：TMDB 閘門、建管理員的密碼只有一格 |
| [0012](adr/0012-owner-is-jellyfin-admin.md) | 擁有者就是 Jellyfin 管理員，鎖在同一台 Jellyfin |
| [0013](adr/0013-berth-manages-only-its-own-objects.md) | 接管只建立與管理 Berth 擁有的物件 |
| [0014](adr/0014-no-site-request-budget.md) | 不做站點請求預算 |
| [0015](adr/0015-notifications-discord-dm.md) | 通知走 Discord bot 私訊，用收件人自己的語言寫 |
| [0016](adr/0016-ai-agent-architecture.md) | AI agent 架構：內建 agent 加匯出的 MCP、pydantic-ai、無月預算上限 |

### 待決問題

目前沒有。

---

## 20. 研究與查證結果

細節在 `docs/research/`，本章只留結論與來源。

### 20.1 Jellyfin 命名、extras、字幕、多版本、API

來源：jellyfin.org 官方文件、api.jellyfin.org OpenAPI、jellyfin GitHub issues、原始碼。標「未證實」者需實測。每條的完整原文（含 issue / 原始碼連結與實測細節）在 [`docs/research/jellyfin-12.md`](research/jellyfin-12.md#從-brief-搬來201)，下稱〈研究檔〉。

**命名**

- 劇集資料夾 `Series Name (2018) [tmdbid-12345]`（年份與 ID 可選但建議加，可疊多個 ID）；季資料夾必須是 `Season NN`（不可 `S01`），Specials 放 `Season 00`；集檔名支援 `S01E01`、`S01E01-E02`、`S02E03 Part 1`。（[identifiers](https://jellyfin.org/docs/general/server/metadata/identifiers)、[shows](https://jellyfin.org/docs/general/server/media/shows)）
- 純數字或數字開頭的劇名會讓 metadata 搜尋失敗（[#15860](https://github.com/jellyfin/jellyfin/issues/15860)）→ 用 `[tmdbid-…]` 鎖定可迴避。
- 集號後接方括號 tag 曾讓 AniDB 插件誤判；**核心解析器沒有這個問題**：方括號與 `+` 不滲進 Series / Episode 名稱，Jellyfin 不從檔名取集標題（2026-09-07 實測，§20.6）。
- 檔名中的 ` - ` 會觸發多版本 regex，沒有 Season 資料夾時不同集會被誤併（[#7855](https://github.com/jellyfin/jellyfin/issues/7855)）。本系統一律有 Season 資料夾，§7.1 的格式已實測無誤（§20.6）。
- Extras 子資料夾名：`extras`、`behind the scenes`、`deleted scenes`、`interviews`、`scenes`、`samples`、`shorts`、`featurettes`、`clips`、`other`、`trailers`、`theme-music`、`backdrops`；劇集層與季層都可放；也支援 `-trailer`、`-short`、`-extra` 檔名後綴。（[官方文件原文](https://github.com/jellyfin/jellyfin.org/blob/master/docs/general/server/media/_video-external-extras.md)）
- 空的 `.ignore` 檔讓整個資料夾被掃描排除；10.11 起非空 `.ignore` 支援 gitignore 語法。（[excluding-directory](https://jellyfin.org/docs/general/server/media/excluding-directory)）

**外掛字幕**

- 格式 `<影片名>.{flags}.{language}.{ext}`，flags 有 `default`、`forced`、`sdh`/`cc`/`hi`，另可放自由文字標題（旗標在語言碼**之前**）。（[官方文件原文](https://github.com/jellyfin/jellyfin.org/blob/master/docs/general/server/media/_video-external-streams.md)）
- 中文語言碼是已知痛點：`chi`/`zh`/`zho`/`zh-hk` 只被辨識為泛「中文」，`cht`/`zh-cn`/`zh-cht` 不被辨識（[#6302](https://github.com/jellyfin/jellyfin/issues/6302)）；`zh-Hant`/`zh-Hans` **只有 10.11 認得**，10.10 退化成「未定義」（2026-09-07 實測，§20.6）。
- 沒有可靠的語言碼能區分繁簡。**已實測採用**：語言用 `zh`，繁簡放自由文字標題，如 `<stem>.CHT.zh.ass`；10.10 顯示 `CHT - Chi - ASS - 外部`、10.11 顯示 `CHT - Chinese - ASS - 外部`，自由文字排最前，兩版都分得出繁簡（§20.6）。

**多版本**

- 電影：同資料夾內 `Movie (2021) [tmdbid-…] - 1080p.mkv`，檔名必須與資料夾名完全一致直到 ` - `；` - ` 之後為版本標籤，結尾為 `p`/`i` 的標籤依解析度排序，否則字母排序。（[官方文件原文](https://github.com/jellyfin/jellyfin.org/blob/master/docs/general/server/media/_video-multiversion.md)）標籤內含方括號與 `+` 已實測可用（§20.6）；標籤內含中文在 12.x 已實測是純 tag（中文組名 `喵萌奶茶屋`，[jellyfin-12.md](research/jellyfin-12.md)；10.10 / 10.11 未測，本系統只支援 12 以上）。
- 劇集原生多版本在 10.x 不可靠（12.0 起原生支援，§20.9）：10.8 起要求每集自己一個子資料夾才視為版本，社群回報同一集兩檔通常變成重複條目（[discussion#7900](https://github.com/orgs/jellyfin/discussions/7900)、[#13432](https://github.com/jellyfin/jellyfin/issues/13432)）。結論（10.x）：**劇集多版本必須靠 MergeVersions 插件**，本系統命名只需保證同集檔名的 `S01E01` 部分一致。
- MergeVersions 插件維護到 10.11 與 12.0（12.0.0 版 `targetAbi 12.0`；12.x 上對本系統的樹是空跑、不裝，§20.9）。靠排程任務或設定頁手動觸發，沒有公開 API；本系統用 Jellyfin 排程任務 API 觸發（任務名已實測，§20.7）。已知問題：偶發錯誤、無法停用、跨媒體庫合併。（[README](https://github.com/danieladov/jellyfin-plugin-mergeversions/blob/master/README.md)）

**API**

- `GET /Library/VirtualFolders` 回 `Name`、`Locations[]`、`CollectionType`、`ItemId`、`LibraryOptions`（含 `TypeOptions[].MetadataFetchers`，可偵測 TVDB 插件）。
- 路徑通知：`POST /Library/Media/Updated` 帶 `{Updates:[{Path, UpdateType: Created|Modified|Deleted}]}`；`POST /Library/Refresh` 是全庫掃描；沒有「掃描單一資料夾」的端點。**`UpdateType` 不影響行為**（`LibraryController.PostUpdatedMedia` 對每條都呼叫 `ReportFileSystemChanged(path)`，2026-09-23 讀 master 原始碼），所以 rematch 拆掉的舊路徑照樣以 `Created` 通知（M2 票 08）。【原始碼】
- **路徑通知對「從來沒掃到過內容」的媒體庫無效**（2026-09-15 對 12.0.0 實測 + master `FileRefresher.GetAffectedBaseItem` 原始碼）：等 `LibraryMonitorDelay`（預設 60 秒）後從路徑往上找第一個已存在的 item，初次掃描時空的媒體庫資料夾不成為 item（log `Library folder … is inaccessible or empty, skipping`），於是**不做事也不寫 log**，`POST` 照回 204。套件內媒體庫一開始必空，**第一次入庫一定踩到**（三個媒體庫送三輪，四分鐘後仍 0 item）。與 `EnableRealtimeMonitor` 無關。
- **只刷新一個媒體庫：`POST /Items/{媒體庫 ItemId}/Refresh?metadataRefreshMode=Default&imageRefreshMode=Default`**（2026-10-13 對 12.1.0 實測 + v12.1 原始碼，M4 票 62，`scripts/experiments/jellyfin_scan_scope.py`）。OpenAPI 上與刷新、掃描有關的只有它、`/Library/Media/Updated`、`/Library/Refresh` 三支；它沒有 `Recursive` 參數，但 `ProviderManager.RefreshItem` 對 `CollectionFolder` 會對每個**實體資料夾**遞迴 `ValidateChildren`。網頁控制台「掃描媒體庫」送的就是這一支加兩個 `Default`（它另帶的 `Recursive: true` 伺服器不收），Berth 照它的慣例。收下即回 204（0.08 秒）排進刷新佇列，新集與新劇約 2 秒出現，**同時放進另一個媒體庫的檔案沒被掃到**。
- **它只認得 Jellyfin 已經有的實體資料夾**：實體資料夾由全庫掃描驗證根目錄時建立，而空資料夾當時被略過（`Folder.IsLibraryFolderAccessible`）。所以**第一次掃描時是空的路徑，之後放了檔案，單一刷新與路徑通知都看不到它**（空的電影媒體庫刷新後 90 秒、再送路徑通知後 90 秒都是 0 item）；**只有全庫掃描建得出它**（`ValidateTopLibraryFolders` 只由全庫掃描與新增、移除媒體庫呼叫），建好之後同路徑再放檔，單一刷新 2 秒就看到。**Berth 怎麼判斷**：Jellyfin 已在 Route 的寫入目標底下列出過東西（Series 或 Movie 的 `Path`）就只刷新那個媒體庫，否則跑全庫掃描——空的媒體庫第一次入庫、既有 Jellyfin 的媒體庫剛加上 Berth 路徑時都是後者。（2026-09-15 那次「只刷新那一個 item」量的是空媒體庫，結論範圍寫錯，已更正。）
- `POST /Library/Refresh` 在請求裡**等整次掃描做完**且**掃整台伺服器所有媒體庫**。要「現在掃」又不卡住呼叫端，用內建排程任務 **`RefreshLibrary`**：`POST /ScheduledTasks/Running/{id}` 收下就回；id 從 `GET /ScheduledTasks` 以 `Key` 找（12.0.0 實測 `7738148ffcd07979c7ceb148e06b3aed`）。它同樣掃整台（12.1.0 實測另一媒體庫的新檔一起被掃，四個小媒體庫 4 秒）。**還在跑時再送是空操作**：一樣回 204，`ScheduledTaskWorker.ExecuteInternal` 對執行中任務丟例外而不排隊（v12.1 原始碼）。
- `GET /Items` **沒有 `path` 篩選**。反查：`parentId=<library>&includeItemTypes=Series&fields=ProviderIds,Path` 找 Series（比對 tmdb id 或路徑），再取集並用 `Path` 比對。取集**不要用 `parentId=<series>`**：10.11 第一次掃描後對已被 provider 認出的 Series 回 0 筆（`/Shows/{id}/Episodes` 同），要再掃一次才正常；改用 `parentId=<library>&recursive=true` 再照 `Path` 前綴篩選，四種情況都對（2026-09-07 實測，§20.6）。12.0.0 沒有重現（2026-09-15，§20.8）。
- **`DELETE /Items/{id}` 會刪除磁碟檔案**（`DeleteFileLocation = true`），本系統絕不呼叫它。【原始碼】
- 登入 `POST /Users/AuthenticateByName` 回 `AccessToken`、`ServerId`、`User`；`POST /Auth/Keys` 建 API key。
- 深連結：`{server}/web/index.html#!/details?id={itemId}&serverId={serverId}` 在 10.10.7 與 10.11.11 都能開到詳細頁，前端正規化成 `#/details?id=…`；客戶端自己產生的連結一律不帶 `!`（2026-09-07 playwright 實測，§20.6）。沒有「直接開始播放」的穩定 URL。
- **`serverId` 可以不帶**：12.0.0 登入後直接開 `{server}/web/#/details?id={seriesId}` 照樣畫出詳細頁與季列（2026-09-15 playwright 實測）；10.10 / 10.11 沒測過不帶的形式。Berth 產生的連結不帶它（票 13）。
- **`GET /Items` 每筆都帶 `ServerId`，Episode 另帶 `SeriesId` 與 `SeasonId`**，不必在 `fields` 要（2026-09-15 對 12.0.0 實測）；反查一集時順手知道所屬 Series，媒體庫深連結靠它開到作品而非某一集（票 13）。
- **剛掃進來的 item 有一段時間還沒認完**（2026-09-26 試跑環境 12.1，BLACK TORCH 一季 12 集，記錄在 `docs/archive/m3.md`「M3 後的全面審查」）：`GET /Items` 已列出該 Episode、`Path` 對得上，但 `Name` 是作品名、`ParentIndexNumber` / `IndexNumber` 為空、所屬 Series 沒有 `ProviderIds.Tmdb`；之後同一 item 讀回 `Episode S01E10`、Series 帶 Tmdb。上界約入庫後 12 分鐘（下一次反查碰巧讀到的時間，不是 Jellyfin 真正花的時間）。反查因此先問「認完了沒」再比（`resolver.still_identifying`，M4 票 02）。
- Webhook 插件有 `ItemAdded` / `ItemDeleted`，但走排程批次且社群長期回報不可靠（[#252](https://github.com/jellyfin/jellyfin-plugin-webhook/issues/252)、[#367](https://github.com/jellyfin/jellyfin-plugin-webhook/issues/367)）→ 支持 §9 以排程對帳為主。

**Provider**

- 內建劇集 provider 預設 TMDb（另有 OMDb 與 .nfo）；TheTVDB、AniDB、AniList 都是插件。TVDB 與 TMDB 混用時 Specials 編號錯配有實例（[#13294](https://github.com/jellyfin/jellyfin/issues/13294)）；多 provider 同時啟用時鎖定 ID 也可能被覆寫（[#16268](https://github.com/jellyfin/jellyfin/issues/16268)）→ 支持 §10 單一 TMDB。
- AniDB / AniList 插件的編號語意沒有文件 → 不納入第一階段。

### 20.2 qBittorrent Web API 與硬鏈接 / Docker 限制

細節（逐字原文、實測表格、原始碼行號）在 [qbittorrent-web-api.md](research/qbittorrent-web-api.md)，下面只留結論與來源。來源：qBittorrent master 原始碼（`torrentscontroller.cpp`、`serialize_torrent.cpp`）、`WebAPI_Changelog.md`、qbittorrent-api、TRaSH Guides、Servarr wiki、man pages。**社群 wiki 的 API 頁面已過時**（連「5.0」頁面都還列 `paused` / `root_folder`），以原始碼為準。【決定】支援下限 qBittorrent 4.4（API 2.8.4，2022），以 5.x 為主要測試目標。

**版本對照**（留作版本行為的前提，原文在研究檔）：4.4.5 = Web API 2.8.5、5.2.3 = Web API 2.15.1；`contentLayout` 自 API 2.7 / qB 4.3.2 起，取代 `root_folder`；4.4.4 引入「方法不對回 405」，`torrents/delete` 到 4.5.0 才進 POST 白名單（4.4.5 仍可 GET）；changelog 說 API 2.15.0 起空結果回 204，`recheck` / `start` 實測沒有（仍 `200` + 空 body）。

**`torrents/add` 與改名**（[細節](research/qbittorrent-web-api.md#torrentsadd-參數與回應)）

- 現行參數：`urls` / `torrents`、`savepath`、`downloadPath` + `useDownloadPath`、`category`、`tags`、`rename`、`autoTMM`、`contentLayout`（API 2.7 起，取代 `root_folder`）、`stopped`（API 2.11.0 起取代 `paused`）、`stopCondition`、`seedMode`（API 2.16.0 起，同時移除 `skip_checking`）、`filePriorities`、`ratioLimit` / `seedingTimeLimit`。master 已不讀 `paused` / `root_folder`。
- adapter 必須先讀 `app/webapiVersion`，依版本送 `paused` 或 `stopped`；`torrents/pause|resume` 在 5.0 改名 `stop|start`，5.x 的 `torrents/resume` 是 404、沒有別名（實測 4.4.5 / 5.2.3，細節見 [recheck](research/qbittorrent-web-api.md#torrentsrecheck-與重新開始)）。
- **回應形狀兩版不同**（2026-09-10 票 09 實測，見 §20.7）：4.4.5 回 `200` + `Ok.`，5.2.3 回 `200` 加一份 JSON 摘要。只認 `Ok.` 的用戶端會把 5.x 上每一次成功的送單都判成失敗。

**分類與路徑**（[細節](research/qbittorrent-web-api.md#分類與路徑)）

- `createCategory` / `editCategory` 參數：`category`、`savePath`、`downloadPathEnabled`、`downloadPath`。per-category 未完成路徑自 API 2.8.4 / qB 4.4.0 即存在，WebUI 到 **5.2.0** 才有介面（[Changelog](https://raw.githubusercontent.com/qbittorrent/qBittorrent/master/Changelog)）。本系統用它取代全域 `temp_path`（M4 票 22，§4.1）。
- **分類的 `downloadPath` 實測**（M4 票 22，4.4.5 與 5.2.3 結論相同）：分類 `downloadPathEnabled=true` + `downloadPath` 時，下載中檔案在分類的 `downloadPath`，完成後搬到分類的 `savePath`；全域 `temp_path` 開或關都是**分類的贏**。分類 `downloadPathEnabled=false` 時直接寫在 `savePath`（可明說不走全域）；兩個欄位都不送時跟全域（開著就在全域 temp path，5.2.3 底下多一層分類名）。torrent 照 Berth 的送單形狀加：`category` + `autoTMM=true`、不送 `savepath`。
- 讀回 `torrents/categories` 的鍵是 **`download_path`**（不是駝峰）：設了是字串；停用兩版都是 `false`；沒設 5.2.3 是 `null`、4.4.5 **整個鍵不出現**。儲存路徑的鍵在 4.4.0–4.4.1 曾在 `savePath` / `save_path` 之間反覆，adapter 兩者都要接受（4.4.5 / 5.2.3 實測是 `savePath`）。
- `createCategory`：表單鍵 `category`、`savePath`（Berth 另帶 `downloadPathEnabled`、`downloadPath`）；名稱空字串回 **400** `Category cannot be empty`，名稱不合法或建不起來（含同名已存在）回 **409** `Unable to create category`（master 原始碼，2026-09-08）。所以冪等要靠呼叫端先 `torrents/categories` 讀一次。
- `torrents/removeCategories`：表單欄位 `categories`，多個以換行分隔，任何情況都回 200（[WebUI API 5.0](https://github.com/qbittorrent/qbittorrent/wiki/WebUI-API-(qBittorrent-5.0)#remove-categories)，context7 查核 2026-10-07）。分類裡的 torrent 會變成沒有分類，所以 Berth 只送重數過是空的 `berth-*`（M4 票 47）。
- **autoTMM 開啟時 save path 跟隨 category；`category_changed_tmm_enabled` 為真時改 category 路徑會自動搬移所有該分類 torrent。** → 建立 category 後不再改其 savePath；使用者改 Route 目標時建立新 category，舊 Job 維持原位；已存在但路徑不同回報衝突、不覆寫。
- TRaSH 明確要求 category 模式必須 `Automatic`（autoTMM），否則下載不會進分類資料夾（[Basic-Setup](https://trash-guides.info/Downloaders/qBittorrent/Basic-Setup)）。

**狀態與檔案**（[細節](research/qbittorrent-web-api.md#狀態與檔案)）

- `torrents/info` 欄位：`hash`、`name`、`state`、`progress`、`save_path`、`content_path`（API 2.6.1）、`download_path`（原始碼有、wiki 未列）、`completion_on`、`category`、`tags`、`added_on`。`state` 全值清單見研究檔。
- **「完成」判定**：`progress == 1` 且 `completion_on > 0` 且 state **不是** `moving` / `checking*`（temp path 搬到 save path 期間 state 為 `moving`，此時不可入庫）。`completion_on` 未完成時 4.4.5 是 `0`、5.2.3 是 `-1`：寫 `> 0` 兩版都對，寫 `!= 0` 會讓 5.x 上每個剛加入的 torrent 被當成已完成。`total_size` 在 metadata 到手前同樣是 `-1` / `0`。
- `torrents/files` 回 `index`、`name`（相對路徑）、`size`、`progress`、`priority`（0 = 不下載，要從 Plan 排除）、`availability`。`name` 相對 `save_path` 還是 `content_path` 文件未明，adapter 以 `stat` 驗證組出的絕對路徑（實測見 §20.7）。**`metaDL` 期間回 `200` + `[]`**（兩版皆然），與「torrent 不存在」同形，所以 `metadata_ready` 要 state 與清單兩個條件都成立。
- 其他端點：`setLocation`、`rename`、`renameFile` / `renameFolder`（API 2.8.0）、`delete(deleteFiles)`、`setCategory`（category 不存在回 409）、`addTags`、`recheck`。
- **`torrents/delete`**（2026-09-22 對 `release-4.1.0` 到 `release-5.2.3` 十個 tag 逐一核對原始碼，M2 票 04，[細節](research/qbittorrent-web-api.md#torrentsdelete-的確切形狀)）：一律 POST（4.5.0 起 GET 是 405）；`hashes`（`|` 分隔、`all`）與 `deleteFiles` **兩個都必填**，少一個回 400；`deleteFiles` **只認字面 `true` / `false`**（`1` 不是真，解析不出來退回 `false`，檔案沒刪而呼叫端以為刪了）；成功 `200` + 空 body；**不認得的 hash 靜默成功**，所以對早已不在客戶端的那一筆不必先問。Berth 因此不用 `deleteFiles=true` 刪檔，由自己刪磁碟上的東西、數刪了幾個與空出多少（§9.2、`services/deletion.py`）。
- **`torrents/recheck` 與重新開始**（2026-09-23 M2 票 09c，原始碼逐行核對加兩版容器實測，[細節](research/qbittorrent-web-api.md#torrentsrecheck-與重新開始)）：重新開始 4.4.5 是 `torrents/resume`、5.x 是 `torrents/start`；參數 `hashes` 必填；5.x 只收 POST，4.4.5 GET 也行；成功 `200` + 空 body；不認得的 hash 靜默成功；有錯誤先 `clear_error()`、缺檔先 `reload()`。recheck 之後停住的 torrent 校驗完會**再停下來**。資料刪掉、容器重啟後 torrent 是 `missingFiles`；資料放回去之後 recheck → start 與 start → recheck 兩版都回到做種中，資料不在則是 `stalledDL`。`client_error` 的「重試」只送 start（錯誤不是資料的問題，重新校驗幾十 GB 只是更晚回來）。
- **停住的 torrent 做 recheck：5.x 上 recheck → start 救不回來**（2026-09-24 M3 票 03，5.2.3 與對照 4.4.5，[細節](research/qbittorrent-web-api.md#停住的-torrent-做-recheck)）：5.2.3 的 `forceRecheck()` 對停住的 torrent 自己先 `start()` 再掛 `StopCondition::FilesChecked`，校驗中送到的 `start()` 看它沒停就什麼都不做，校驗完照樣 `stop()`，於是停在 `stoppedUP`（資料齊）或 `stoppedDL`（缺檔，progress 0.5）；`stoppedDL` 既不轉 `stalled` 也不開 Issue，畫面上看不出事。**start → recheck 順序兩版都落在做種中或 `stalledDL`。Berth 用 start 先於 recheck（`missing_files` 的「重新校驗」），順序不能反。**

**輪詢與登入**（[細節](research/qbittorrent-web-api.md#輪詢與-syncmaindata)）

- **沒有 webhook**；`sync/maindata` 以 `rid` 做增量輪詢。`autorun_enabled` / `autorun_program`（完成時執行外部程式，可帶 `%f` `%n`）可作「喚醒輪詢」的加速手段，非必要。
- **`rid` 的狀態掛在 session（SID cookie）上**（2026-09-10 票 10 對 4.4.5 與 5.2.3 實測）：不帶 cookie 則每次請求都是新 session，回的永遠是 `full_update: true`。所以輪詢那一側必須把 HTTP client 握著不放（Berth 的 `Downloader`）。
- **增量那一輪的 `torrents[hash]` 只帶變動的欄位**（實測有的只剩 `{"num_leechs", "time_active"}`），呼叫端一定要併回上一份完整快照再讀，否則得到沒有 category、沒有 state 的空殼。被刪掉的在 `torrents_removed`（hash 陣列）。
- 登入 `auth/login` 回 `SID` cookie，且 **`Referer` / `Origin` 必須與 `Host` 一致**（m0 實測的更準確說法見 [m0-experiments.md](research/m0-experiments.md)）；可設 `bypass_local_auth` 與子網白名單。
- **`auth/login` 的成敗形狀跨大版本不同**（2026-09-08 對 `lscr.io/linuxserver/qbittorrent` 的 4.4.5 與 5.2.3 實測，票 11）：4.4.5 成功 `200` + `Ok.` + `Set-Cookie: SID=…`，帳密錯 `200` + `Fails.`（**狀態碼不變**）；5.2.3 成功 `204` + 空 body + `Set-Cookie: QBT_SID_<port>=…`，帳密錯 `401` + `Unauthorized`。所以判定只能認 4.x 那個「200 卻是失敗」的 `Fails.`，不能認「成功等於 `Ok.`」。來源 IP 在 `WebUI\AuthSubnetWhitelist` 上時 5.x **一律回 204，連錯的帳密也是**——免密白名單本來就繞過驗證，這正是套件內 Berth 的處境（§16.3、§20.7）。
- **IP 封鎖與帳密不對是兩件事**（2026-09-10 票 10 對兩版各實測一輪，解掉 plan T1.9 的第四條）：帳密錯第 1–5 次是 `200` + `Fails.`（4.4.5）/ `401`（5.2.3）；**第 6 次 IP 被封回 `403` + `Your IP address has been banned after too many failed authentication attempts.`，兩版一字不差**；被封之後其他端點回 `403` + `Forbidden`。因此 **`auth/login` 上的 403 只有一個意思**（被封），其他端點上的 403 與「沒有登入」同形、分不出來。下一步不同才是分開的理由：帳密不對要改設定，被封要等過期或重啟 qBittorrent——改帳密只會再失敗五次，把封鎖時間重算一輪。
- **封鎖的偏好鍵與預設值**（2026-09-30 讀 `release-4.4.5` 與 `release-5.0.4` 原始碼，M4 票 21，兩版相同，[細節含行號](research/qbittorrent-web-api.md#封鎖的偏好鍵與預設值)）：門檻 `web_ui_max_auth_fail_count` 預設 **5**（連續失敗），封鎖 `web_ui_ban_duration` 預設 **3600 秒**；計數與封鎖表只在記憶體（`m_clientFailedLogins`），重啟容器就清；**登入成功才把該 IP 移除**，不隨時間衰減；**被封期間連對的帳密也被拒**；`max_auth_fail_count = 0` 不計也不封。WebUI 與 API 都沒有解除封鎖的介面。被封時 Berth 讀不到偏好，所以精靈說預設值（`components/services.BAN_DEFAULTS`），並從第 3 次連錯起預警。
- **`auth/login` 在 session 還活著時直接回成功，連密碼都不看**（帶著 SID 打八次錯的密碼全是 `200` + `Ok.`）。所以「驗一次帳密對不對」必須從沒有 cookie 的狀態發起。

**qBittorrent 看不看得到分類路徑：探針 torrent**（2026-09-30 實測 4.4.5 與 5.2.3，M4 票 19；`scripts/experiments/qbittorrent_visibility_probe.py`，[細節與表格](research/qbittorrent-web-api.md#探針-torrent看不看得到分類路徑)）

- Web API 沒有「這條路徑你看不看得到」（`app/getDirectoryContent` 5.0 才有，且只說目錄在不在）。反過來證明：Berth 在分類路徑寫小檔、做成單檔 torrent（`private`、不掛 tracker），`torrents/add` 明送 `savepath`、`autoTMM=false`、停住，`torrents/recheck`，看 `progress`；之後 `torrents/delete` 帶 `deleteFiles=false`，小檔由 Berth 刪。
- 結果（兩版相同，state 名 `paused*` / `stopped*` 之別）：檔在 → recheck 後 100%（約 1–1.4 秒）；檔或目錄不在 → 0%；檔在但 `chmod 000` → **`error`**（權限，與看不到分得開）；開了全域 temp path 照樣 100%。**停住加入不會自己校驗**，一定要 recheck。
- **`torrents/add` 回來時它還不一定列在 `torrents/info` 裡**，而對還不在的 hash 送 recheck 是靜默成功（校驗沒發生，停在 0% 與看不到一模一樣）。所以先等它列出、離開 `checkingResumeData`，再 recheck。
- 看不到時 qBittorrent 不替它建目錄。看不到沒有「校驗完了」的狀態可等，所以 Berth 以「不在校驗或排隊中、進度不到 100%、state 3 秒不變」判看不到，整個探針最多等 20 秒（預設一次只校驗一個 torrent）。
- **校驗到 100% 會觸發「torrent 完成時執行外部程式」**（`autorun_enabled` / `autorun_program`，兩版實測，每個看得到的探針各觸發一次）。所以探針只在精靈「建立並檢查」、新增 Route 與「重新檢查」時跑；**5 分鐘的健康迴圈不跑，`download_visible` 沿用上一次的結論**（否則每條 Route 每 5 分鐘一次，成為使用者那邊的通知洪水；M4 票 50，使用者 2026-10-06 確認）。5.x 另有「加入時執行」（`autorun_on_torrent_added_enabled`），同理，沒有另外實測。
- 探針 torrent 不掛分類、不帶 tag（`berth` tag 會讓 poller 把它當成 Berth 的下載），名字 `.berth-probe-*`，停住、幾秒內移除。

**校驗不完的探針：頁 2 問「看不看得到 `/data`」**（2026-10-07 實測 4.4.5 與 5.2.3，M4 票 46；`scripts/experiments/qbittorrent_unfinished_probe.py`，[細節與表格](research/qbittorrent-web-api.md#校驗不完的探針)）

- 探測檔兩片（32 KiB），第二片雜湊算在反相內容上。結果：檔在 → 停在 **`progress` 0.5**（不是 1）；檔不在 → 0；`chmod 000` → `error`；對照單片 → 1。**「完成時執行」只有對照組觸發**；5.x 的「加入時執行」四包都觸發（4.4.5 沒有這個設定）。
- 所以 Berth 判「看得到」改成 **`progress` 大於 0**（`probe_sight`），兩種探針同一條（單片本來就是 0 或 1）。頁 2 測連線用這一種（M4 票 46）：不觸發「完成時執行」；「加入時執行」擋不掉（任何加進去的 torrent 都觸發），表單照實說觸發一次。頁 3 的 Route 檢查仍是單片那一種。

**WebUI 帳密規則**（2026-10-01 讀原始碼＋實測，M4 票 26；`scripts/experiments/qbittorrent_webui_login_rules.py`，[細節](research/qbittorrent-web-api.md#webui-帳密規則)）

- **5.2.0 起 `app/setPreferences` 才驗**：`web_ui_username` 至少 3 字元、不能有冒號，`web_ui_password` 至少 6 字元；違反回 `400` + 一行英文原文。4.4.5 什麼都收；release-5.1.4 原始碼還沒有這段（[appcontroller.cpp @ release-5.2.0](https://github.com/qbittorrent/qBittorrent/blob/release-5.2.0/src/webui/api/appcontroller.cpp)）。字數是 QString 長度（UTF-16 code unit），與瀏覽器 `String.length` 同算法。
- **帳號先驗先寫、密碼後驗**（不看 JSON 鍵序）：帳號合規而密碼太短的那次回 `400`，帳號**已經寫進去**、密碼沒有。所以 Berth 先單獨送密碼、成功才送帳號（`qbittorrent._apply_password`），兩支都過了才記下帳號。
- 【決定】精靈與設定頁照 5.2 的規則先擋，不分版本：4.4–5.1 自己的設定頁（WebUI JS）也要求帳號 3、密碼 6 字元（只少冒號那條），套件內那一台又一定是新版。

**硬鏈接與 Docker**（[TRaSH Hardlinks](https://trash-guides.info/File-and-Folder-Structure/Hardlinks-and-Instant-Moves/)、[Servarr docker-guide](https://wiki.servarr.com/docker-guide)、[link(2)](https://man7.org/linux/man-pages/man2/link.2.html)；[細節](research/qbittorrent-web-api.md#硬鏈接與-docker)）

- 硬鏈接不能跨檔案系統、分割區、volume、**mount**；`link()` 即使同一個檔案系統掛兩次也會 `EXDEV`。Docker 把兩個 volume 當成兩個檔案系統，所以 `/downloads` + `/media` 分開掛一定失敗；解法是單一 `/data` 掛載。
- exFAT 不支援硬鏈接；btrfs 子卷、ZFS dataset 各自是 mount 邊界，跨越即失敗；mergerfs 在 path-preserving 建立策略下跨 branch 回 `EXDEV`，其 FAQ 同樣要求單一掛載根（[mergerfs FAQ](https://trapexit.github.io/mergerfs/latest/faq/why_isnt_it_working/)）。
- 權限：TRaSH 建議「每個 app 一個使用者 + 共用群組 + UMASK 002」（資料夾 775、檔案 664），或簡化為單一使用者 + UMASK 022。本系統與 qBittorrent 至少要同群組且對兩側目錄可寫。
- Docker Desktop（Windows）：文獻無定論，本機實測 NTFS bind mount 硬鏈接可用（§20.7）。macOS VirtioFS 未查到硬鏈接限制，也未實測。
- `stat().st_dev` 相同是必要條件但不充分（同 FS 多次掛載仍失敗），所以 §4.4 的檢查一律真的做一次 `link()`。

**Sonarr / Radarr 先例**（[sonarr/faq](https://wiki.servarr.com/sonarr/faq)、[radarr/settings](https://wiki.servarr.com/radarr/settings)、[quick-start](https://wiki.servarr.com/sonarr/quick-start-guide)；[細節](research/qbittorrent-web-api.md#sonarr-與-radarr-先例)）

- Completed Download Handling：只在客戶端回報完成後才入庫；要求客戶端完成後**暫停而非移除**，並保留至少 14 天歷史。「Remove Completed」只在客戶端回報做種完成且 torrent 已停止時才移除 torrent 與檔案。本系統不做自動移除（§1.2），做種上限交給 qBittorrent 分類的 share limit；移除後的善後由 Reconciler 處理。
- 入庫預設硬鏈接，失敗時 Sonarr 會**退回複製**。【決定】本系統**不退回複製**：硬鏈接失敗即 Route 不健康並拒絕送單，因為複製會讓刪除範圍與空間估算失真。
- 人工入庫的官方名稱是 **Interactive Import**（逐檔指定作品/季/集，可選 Move 或 Copy/Hardlink）；Review Queue 對應這個概念。Root Folder = 媒體庫根目錄，明文規定不可與下載目錄相同。

**其他**（[細節](research/qbittorrent-web-api.md#其他同一台認不出來選項頁網址sparse-檔)）

- **同一台 qBittorrent 認不出來**（M4 票 102，2026-10-14 讀 master 原始碼）：WebAPI 沒有持久的實例識別碼（`app/` 底下只有版本、build info、偏好、預設路徑、網卡清單；沒有 Jellyfin `ServerId`〔§20.15〕那種東西）。最接近的 `app/processInfo` 的 `launch_time` 2026-01 才加（4.4 下限的版本沒有）、每次重啟就變；版本加 `save_path` 也不行（兩台預設安裝一模一樣）。所以位址變了就當換台（§16.4）。
- **WebUI 沒有通往「選項」的網址**（M4 票 102，2026-10-14 對 linuxserver 5.2.4 實開）：`/#/settings` 登入後落在 torrent 清單；`client.js` 只讀 `#download=`。選項是 MochaUI 視窗，從「工具 → 選項」開，所以補法只給 WebUI 本身，文案說在哪個選單。
- **下到一半的檔是 sparse 檔**（M4 票 102，票 42 實測）：qBittorrent 預設不預先配置，表觀大小（`st_size`）已是整個檔案，實際佔用（`st_blocks` × 512）只有下載了的部分（票 42 那筆表觀 970 MB、實際約 192 MB）。刪除的「可空出空間」與 `freed` 量實際佔用（`fs.PathFacts.allocated`），以區塊取整。Windows 的 `os.stat` 沒有 `st_blocks`，Berth 只在 Linux 容器跑，開發機上退回表觀大小。

### 20.3 Metadata provider 與動漫 ID 對應

細節（逐筆實測、數字、原文引用）在 [`docs/research/anime-episode-source.md`](research/anime-episode-source.md#從-brief-搬來203)；下面只留結論與來源。

**TMDB**（細節：[研究](research/anime-episode-source.md#203-tmdb)）

- 季/集 schema：`season_number: 0` 為 Specials；每集有 `episode_number`、`name`、`air_date`、`episode_type`、`runtime`（未播的集 `runtime` 是 `null`）。（[tv-season-details](https://developer.themoviedb.org/reference/tv-season-details)；2026-09-09 實測）
- Episode Groups 類型：Original air date / **Absolute** / DVD / Digital / Story arc / Production / TV。Absolute 只在有人替該劇建立 group 時存在（實測 10 部只有 6 部）。（[episode-group-details](https://developer.themoviedb.org/reference/tv-episode-group-details)）
- **Absolute group 不能當備援，絕對編號要自己從 0-based 的 `order` 推**（2026-09-08 / 09-09 實測）：group 內 `episode_number` 保留播出序原值（SPY×FAMILY S02E01 仍是 `episode_number: 1`，絕對編號 26、`order: 25`）；有的部有多個互相衝突的 Absolute group（進擊的巨人四個，集數 89/97/97/97），柯南那個叫 "China Online Version"；同一部作品有五個 group，只有 `type: 2` 是絕對編號。
- 標題：`name` 依 `language`（預設 `en-US`）回傳，翻譯缺時可能是空字串，**要自己 fallback 到 `original_name`**；2026-09-09 實測 `zh-TW` 未翻譯時回英文，兩種都當「顯示英文」。`alternative_titles` 是各國別名、與 translations 無關，兩者都應納入標題比對。（[translations](https://developer.themoviedb.org/reference/tv-series-translations)、[alternative-titles](https://developer.themoviedb.org/reference/tv-series-alternative-titles)）
- `find/{external_id}` 支援 `imdb_id`、`tvdb_id` 等反查。（[find-by-id](https://developer.themoviedb.org/reference/find-by-id)）
- 速率：官方未列；員工在論壇稱約 50 req/s、20 併發/IP。條款：**非商業免費，需顯示 TMDB logo 與聲明「This product uses the TMDB API but is not endorsed or certified by TMDB.」**（[faq](https://developer.themoviedb.org/docs/faq)）
- 探索三支端點（2026-09-09 實測，fixture `tests/fixtures/http/tmdb/`）：`trending/{tv,movie}/week` 與 `search/multi` 的每筆帶 `media_type`，`{tv,movie}/popular` 不帶；劇集用 `name` / `original_name` / `first_air_date`，電影用 `title` / `original_title` / `release_date`；`search/multi` 也回 `person`（`?query=miyazaki` 20 筆中 16 筆）。
- `language` 換掉的不只文字，還有清單成員與順序（2026-09-09 實測：`trending/tv/week` 的 `en-US` 與 `zh-TW` 各 20 筆只有 17 筆相同）→ 清單以 `en-US` 為準，`zh-TW` 只當「這一部叫什麼」的查表（plan §8.3）。`popularity` **不是**清單排序依據（`tv/popular` 首五筆 583 / 440 / 692 / 417 / 398），要照 TMDB 排名就用陣列順序。
- 詳情四支端點（2026-09-09 實測，票 04）：`tv/{id}` 的 `seasons[]` 有 `season_number` / `name` / `episode_count` / `air_date`；`movie/{id}` 有 `runtime` 無 `seasons`；不存在的 id 回 **404 加 `status_code: 34`**，與「TMDB 壞了」是兩件事。
- 劇集 `status`（2026-09-27 查證，M4 票 13；官方未列，維護者在[論壇](https://www.themoviedb.org/talk/6685c10585e1cbe90c4a5fe0)確認）：`Returning Series`、`Planned`、`In Production`、`Ended`、`Canceled`、`Pilot`。Berth 把 `Ended` 與 `Canceled` 讀成「不會再播了」（`MediaSnapshot.ended`，RSS Series 完結看它，§15「呈現」）。
- 動漫 split-cour 正被 TMDB 與 TVDB 同步合併成單季連續編號（[TMDB talk](https://www.themoviedb.org/talk/697d0680d564e13094e4e270)、[TVDB KB](https://support.thetvdb.com/kb/faq.php?id=61)），字幕組多數按 cour 從 01 重算。2026-09-09 實測：TMDB 連獨立的連續季也併（咒術迴戰 3 季→1 季 59 集、Re:Zero 4→1 共 85 集、芙莉蓮 2→1 共 38 集、柯南 34→1 共 1213 集），TVDB 這幾部維持分季；但合併只造成 0.4 個百分點差距，**主要錯誤來源是檔名沒有季號**（§10、[研究](research/anime-episode-source.md#0-結論)）。
- **季名逐語言翻譯，三套字都有人用**（2026-09-10 實測 `tv/85937`、`tv/1429`，票 06）：同一季 `name` 在 `en-US` / `zh-TW` / `zh-CN` 分別是 `Hashira Training Arc` / `柱訓練篇` / `柱训练篇`；進擊的巨人第四季為 `The Final Season` / `第4季` / `最终季`。**篇章名比對必須三套都留**（真實發佈最常見是簡體，只留英文則 plan §4.4 規則一個都不會命中）；代價是 `tv/{id}` 多打一輪 `zh-CN`（只取季名，電影不打，plan §4.3、§8.3）。
- `alternative_titles` 帶篇章名但不帶季號（2026-09-10 實測）：CN 只有兩筆、TW 五個篇章齊全、JP 是羅馬字；「第幾季」只有 `seasons[].name` 給得出來，比對主力是季名，別名只補充。
- split-cour 兩個 cour 之間可超過半年（2026-09-10 實測：進擊的巨人 S3 E12 播於 2018-10-15、E13 播於 2019-04-29，相隔 196 天）→ plan §4.4 的 180 天門檻同時切得出「虛擬季」與「同一季裡的 cour」。
- **字幕組編號習慣有四種且同一部並存**（2026-09-09 實測 7,833 筆）：每 cour 從 01 重算 68%、官方編號 16%、正篇序位 13%、季內連號 3%（第二 cour 從 13 接下去）。Dandadan 第二季同時有 `S01 | 01-24`、`[13-24]`、`S2 - 10`、`S2 - 20` 四種寫法。解析器不能假設編號一致。

**TheTVDB v4**（細節：[研究](research/anime-episode-source.md#203-thetvdb-v4)）

- 存取（2026-09-07 重查，原記載過度已更正）：v4 key **免費**自助申請（[KB#81](https://support.thetvdb.com/kb/faq.php?id=81)）；`/login` 的 `pin` **選填**，不帶可取 token 並讀資料（本機實測；[v4-api swagger](https://thetvdb.github.io/v4-api/)）。
- **授權是硬牆，模型未變**：key 須「commercial license 或 subscriptions enabled for end users」（[KB#62](https://support.thetvdb.com/kb/faq.php?id=62)）；user-supported 模式每位使用者 $12/年（[v4-api](https://github.com/thetvdb/v4-api)）；ToS 第 2 節 key "non-transferable"、"solely for the product or project…"（[tos](https://www.thetvdb.com/tos)）。→ 個人自用沒問題；**Berth 內建一把 key 給所有使用者靠執行寬鬆、隨時可能被關**；若採用走「使用者自己申請免費 key」。「每人自己申請一把免費 key」官方從未表態，**未證實**。
- Jellyfin 官方 TVDB 插件同形狀：內建 project key 加選填 subscriber's pin（[PluginConfiguration.cs](https://github.com/jellyfin/jellyfin-plugin-tvdb/blob/master/Jellyfin.Plugin.Tvdb/Configuration/PluginConfiguration.cs)）→ Jellyfin 媒體庫切 TVDB 刮削不需付費，§10「Jellyfin 同源」理由被削弱。
- 季類型 default(aired) / absolute / dvd / alternate / regional，**每部都有**（TMDB 的 Absolute group 要有人手動建）；Sonarr 只用 TVDB（經 Skyhook），靠 TheXEM 做 scene 編號（[xem-guide](https://wiki.servarr.com/sonarr/xem-guide)）。
- **`absolute` 把 OVA 與劇場版也編進去**（2026-09-09 實測 10 部）：SPY×FAMILY 劇場版佔掉 absolute 38，正篇第 38 集是 39；absolute ≠ 正篇第幾集，而字幕組「接著往下算」數的是正篇。
- 取資料要打兩次：`/series/{id}/extended` 只回 default order，絕對編號另打 `/series/{id}/episodes/absolute`（`page` 必填、每頁 100 筆），`absoluteNumber` 只在 `EpisodeBaseRecord`；[issue #98](https://github.com/thetvdb/v4-api/issues/98) 開了五年未做。（2026-09-08，swagger 4.7.10）

**Jellyfin 對絕對編號的支援**（2026-09-08 讀原始碼；細節：[研究](research/anime-episode-source.md#203-jellyfin-絕對編號skyhook-與-sonarr)）

- **Jellyfin 沒有「絕對編號」概念**：`EpisodeInfo` 只有 `EpisodeNumber` / `SeasonNumber`，沒有季資料夾時 `EpisodeResolver` 把季號設成 1。走 absolute 得把**整部劇**的 `Series.DisplayOrder` 設成 `absolute`（`tvshow.nfo` 的 `<displayorder>`，或 `POST /Items/{id}` 但會觸發整劇 FullRefresh + ReplaceAllMetadata）；jellyfin-plugin-tvdb 沒有任何排序設定。absolute + specials 目前壞的（[issue #91](https://github.com/jellyfin/jellyfin-plugin-tvdb/issues/91)，2023 起 open）。

**Sonarr Skyhook 不能寫進產品**：`https://skyhook.sonarr.tv/v1/tvdb/shows/en/{tvdbId}` 免認證、有 `absoluteEpisodeNumber`，只適合當量測替身（10/10 與 thetvdb.com 一致）；封閉源、無文檔、無 SLA，servarr 政策 "We do not support directly hitting any metadata service that isn't our own"。

**Sonarr 作為先例**

- Series Type：Standard / Daily / Anime（絕對編號）；預設動漫命名含 `S{season:00}E{episode:00} - {absolute:000}`。（[settings](https://wiki.servarr.com/sonarr/settings)）v4 以 Custom Formats 取代 Preferred Words，Release Profiles 保留 must / must-not contain。
- EpisodeFile（帳本先例）欄位：`relativePath`、`path`、`size`、`dateAdded`、`sceneName`、`releaseGroup`、`language`、`quality`、`mediaInfo`、`qualityVersion`。（[starr sonarr](https://pkg.go.dev/golift.io/starr/sonarr)）**§8 的 `ledger` 至少要涵蓋這些。**

**動漫 ID 對應**（細節：[研究](research/anime-episode-source.md#203-動漫-id-對應)）

- **Fribb/anime-lists** `anime-list-full.json`：每筆含 `anidb_id` / `anilist_id` / `mal_id` / `kitsu_id` / `imdb_id` / `themoviedb_id` / `tvdb_id`，另有 `season` 與 `episode_offset`（`{tvdb, tmdb}`）。（[Fribb/anime-lists](https://github.com/Fribb/anime-lists)）**M5 票 23d 拿掉**：實測錯在季與 offset，見 [fribb-vs-chaining](research/fribb-vs-chaining-2026-10-28.md)、[agent-sources-ab](research/agent-sources-ab-2026-10-28.md)。
- Anime-Lists `anime-list.xml` 只有 AniDB→TVDB，無 TMDB；[anibridge-mappings](https://github.com/anibridge/anibridge-mappings) 目標是集級對應，可觀察。
- AutoBangumi v3.2 的 Episode Offset Auto-Detection 用 TMDB 各集 `air_date` 偵測虛擬季並建議 offset。（[autobangumi](https://www.autobangumi.org/en/feature/bangumi.html)）**§6.4 的絕對編號換算應同時用「累計集數」與「air_date 區間」兩種訊號。**
- Shoko + Shokofin（AniDB ED2K hash）自成生態、與 TMDB 路線不相容，不納入。

**動漫資料來源：AniList、Bangumi、Fribb**（2026-10-28 查證＋實測，M5 票 16；細節：[研究](research/anime-episode-source.md#203-動漫資料來源-anilist-bangumi-fribb)、[m5-anime-sources](research/m5-anime-sources-2026-10-28.md)）

**M5 票 23d 拿掉 Fribb 與 AniList 的標題搜尋、系列走圖**（[agent-sources-ab](research/agent-sources-ab-2026-10-28.md)）：Berth 只用 AniList 的季表與 Bangumi 放送表；fixture 只剩 `tests/fixtures/http/{anilist,bgm}/`，`scripts/experiments/anime_sources.py` 錄的。

- **AniList**（`POST https://graphql.anilist.co`，免 key、不要求 User-Agent）：文件寫 90 次 / 分，頁首警告**目前降級成 30 次 / 分**（[Rate Limiting](https://docs.anilist.co/guide/rate-limiting)；實測 `X-RateLimit-Limit: 30`）；超過就**封一分鐘**，期間全回 429 帶 `Retry-After` 與 `X-RateLimit-Reset`，所以重試要全程序一起停。錯誤寫在 `errors`（錯參數回 400），`Page.media(id_in)` 問不存在的 id 回 200 加空清單；`Page` 一頁最多 50 筆（要 60 回 50）。條款（[Terms of Use](https://docs.anilist.co/guide/terms-of-use)）：月營收 < $150 免費；**禁止當備份 / 儲存服務、禁止 hoarding**，所以 Berth 只按需問、程序內快取 6 小時、不落地。`relations` 用 `relationType(version: 2)`。打分人數是 `stats.scoreDistribution[].amount` 加總。
- **Bangumi**（`GET https://api.bgm.tv/calendar`，免 key）：**非瀏覽器要帶 User-Agent（開發者 ID 與應用名，分發的帶版本、開源的帶主頁）**，預設的可能被擋（[user agent.md](https://github.com/bangumi/api/blob/master/docs-raw/user%20agent.md)）；Berth 送 `1morr/berth/<版本> (https://github.com/1morr/Berth)`。`/calendar` 在 `open-api/api.yml`（不在 `v0.yaml`），欄位全非必填（112 部裡 57 部有 `rank`、93 部有 `rating.score`）；回 `cache-control: max-age=3600`，Berth 記一小時；無公布速率上限。
- **Fribb**（`raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-full.json`，7.5 MB、39,579 筆）：**倉庫無授權檔**，上游 anime-offline-database 為 **ODbL 1.0**；判讀（非法律意見）嚴格說保留所有權利，Berth 的結論是執行時下載到使用者自己的 `CONFIG_ROOT`、只自己查詢，**不打包進 repo 或 image**（那才是再散布），不加 ODbL 署名（無公開使用，§4.3）。每週二約 16:04 UTC 更新，下載會斷（要先解得開才換舊檔）；僅約兩成條目有 TMDB id；`episode_offset.tmdb` 差一集（Re:Zero 第 2 季寫 26，實際 E26–E38）。17 部實測見 [fribb-vs-chaining](research/fribb-vs-chaining-2026-10-28.md)：Fribb 錯在季與 offset，只靠集數串接錯在 Specials 與 TMDB 拆條目，所以 `series-mapping` 兩種都算、不一致整季交給人。

**Seerr（前 Jellyseerr / Overseerr）**（細節：[研究](research/anime-episode-source.md#203-seerr)）

- 2026 年 3 月起 Jellyseerr 與 Overseerr 合併為 **Seerr**（[seerr-release](https://docs.seerr.dev/blog/seerr-release)）；本文件所有「Seerr」指它。以 Jellyfin / Emby / Plex 帳號登入，第一個以媒體伺服器管理員登入者成為 owner，權限為細粒度旗標（[users](https://docs.seerr.dev/using-seerr/settings/users)）。
- 可用性判定（來源碼 `server/lib/scanners/jellyfin/index.ts`）：`ProviderIds.Tmdb`，缺則 `Imdb` → TMDB find，再缺則 `AniDB` → 內建 anime-list。§9 認領 unmanaged 檔案可沿用這條鏈。
- 深連結（`server/entity/Media.ts`）：`{externalUrl}/web/index.html#!/details?id={itemId}&context=home&serverId={serverId}`。§12 採用此格式。

### 20.4 解析先例與真實 torrent 內容

細節與逐字原文在 [research/profile-effect.md](research/profile-effect.md#從-brief-搬來204)（本檔 §6.4 絕對編號量測見同檔 [§0](research/profile-effect.md#0-結論)、[§6.1.1](research/profile-effect.md#611-規則-1-的代價m1-票-14d-第-1-步2026-09-17)）。

**解析庫現況（2026-09）**：guessit（Python，v4.4.0，2026-07）欄位最完整但 CJK 弱（[#929](https://github.com/guessit-io/guessit/issues/929) 仍開著，fansub 括號格式常錯）；anitopy（2022 停滯）、anitomy（C++，重寫中）、anitomyscript（2019，落後）無 CJK 專門處理；[@ctrl/video-filename-parser](https://github.com/scttcper/video-filename-parser)（TS，v5.11，Radarr 風格）、parse-torrent-title（JS）、[PTT](https://github.com/dreulavelle/PTT)（pip `parsett`）、torrent-name-parser（Rust，2023 停滯）都只管西方 scene 命名。

**結論**：沒有現成庫能處理中文字幕組命名，CJK 詞典一定要自己維護；西方命名交給 guessit（Python）或 @ctrl/video-filename-parser（TS）。可直接借鑑的 CJK regex 有兩處：

- **AutoBangumi `backend/src/module/parser/analyser/tokenizer/classic.py`**（[repo](https://github.com/EstrellaXD/Auto_Bangumi)）：字幕標記、季 / 集（含中文數字）、合集 / 特典、番外、劇場版、★前綴、招募廣告、僅限港澳台、來源（Baha / B-Global / Bilibili / CR / AT-X / Abema / AMZN / NF…）、codec、audio 的 regex（`_CJK_SUBTITLE_TAG`、`_SUBTITLE`、`_CHINESE_SEASON`、`_CHINESE_EPISODE`、`_FULL_COLLECTION` / `_COLLECTION`、`_SPECIAL_CJK`、`_MOVIE_CJK`、`_PREFIX`、`_RECRUIT`、`_REGION`、`_SOURCE`、`_CODEC`、`_AUDIO`）。
- **Sonarr `Parser.cs`**（[raw](https://raw.githubusercontent.com/Sonarr/Sonarr/develop/src/NzbDrone.Core/Parser/Parser.cs)）：約 8 條中文動漫 pre-substitution（LoliHouse / Lilith-Raws / Skymoon-Raws 無括號、GM-Team 多括號、`第?(\d+)(话|集)?( END|完| Fin)?`），以及韓劇 `\.E(\d{2,4})\.\d{6}\.(.*-NEXT)$ → S01E$1`。

**AutoBangumi 現況（main，2026-08）**：

- 解析輸出 `ParsedRelease`（title_en / zh / jp、group、season、episode、episode_end、media_type、release_kind(SINGLE|RANGE|BATCH|COLLECTION)、resolution、source、subtitle、codecs、audio、version、tags、evidence）；§6.3 的欄位設計與此對齊。
- LLM 解析支援 OpenAI / Anthropic / Gemini，`primary` 與 `fallback` 兩種模式（記憶體快取、斷路器、併發上限）；§6.10 與其 `fallback` 一致，並多加 schema 驗證與預算。
- `offset_detector.py`：以 TMDB 各集 `air_date`、播出間隔 > 6 個月切「虛擬季」算 season_offset / episode_offset。
- 明確限制：**不支援合集 / 批次**、OVA 與電影 RSS 不支援、路徑必須是 `Title/Season X/`——正是 §6.6 要超越的地方。
- RSS 預設過濾 regex `720|\d+-\d+`；建議一部作品只訂一個字幕組；§15 的 Rule 預設沿用「排除合集、字幕組白名單」。

**真實內容樣本**（現場列表，benchmark v0 的種子；v0 語料 20 筆 = 動漫 8、非動漫劇集 8、電影 4，清單與逐字原文在 [研究檔](research/profile-effect.md#從-brief-搬來204)「真實內容樣本」，逐筆出處在 `tests/fixtures/parser/README.md`）：

- 單集：Erai-raws `- 07 [1080p NF WEB-DL AVC AAC][MultiSub][A5D38B89]`；三明治摆烂组同集三個 torrent（`[繁日内嵌]`、`[简日内嵌]`、`[简繁日内封]`，內嵌 vs 內封）；楓葉字幕組 `[089][繁體][1080P][MP4]`；悠哈璃羽字幕社 `S2_…[x264 1080p][CHT]`；DHR Fansub `[04][JPN&BIG5][720P][AVC_Hi10P_AAC][MKV]`；LoliHouse `- 81 v2 WebRip 1080p HEVC-10bit AAC`。
- 合集 / BD：7³ACG `S01 | 01-28+SPx11`、`S01 | 01-26+SPx1`；`★百姓贵族★29~40(完)★1920x1080★`（`★` 分隔、`完` 標記）；`jibaketa TVB … S1 S2 S3 BD`（多季合一）；`Solo Leveling S01 + S02 BDRIP`。
- 外掛字幕：`sub/…第01話(DVD 640x480).gb.ass` / `.big5.ass`；`[十二国记]…tc.ass`；Mikan 的「生肉 / 不明字幕」標記。
- 西方劇集：RARBG 季包 `Show/Subs/Episode 1/2_English.srt`（[renamer README](https://github.com/img02/Rarbg-Subtitle-Renamer)）；Sonarr Daily 型 `Some.Daily.Show.2021.03.04.1080p.HDTV.x264-GROUP`；`S01E01E02` 多集檔。
- 電影：`Oppenheimer (2023) [1080p] [BluRay] [5.1] [YTS.MX]/…mp4` + `www.YTS.MX.jpg` + `YTSProxies.com.txt`；Jellyfin 多片段 `Movie Name-cd1.mkv`（parttype：cd/dvd/part/pt/disc/disk）。
- 韓劇：`Show.E01.YYMMDD.1080p…-NEXT` 無季編號（Sonarr 特別處理），`E01-16 COMPLETE (HDTV NEXT)` 全季字幕包。
- **已證實（2026-09-10，M1 票 05，抓真實 torrent metadata）**：BD 包附屬資料夾名兩家不同，成了 §6.9 的語料（`tests/fixtures/parser/`）。
  - [VCB-Studio 魔王2099](https://share.dmhy.org/topics/view/726629_VCB-Studio_2099_Demon_Lord_2099_10-bit_1080p_HEVC_BDRip_Fin.html)（223 檔）：`SPs/`、`CDs/`（每碟一子資料夾，flac + webp）、`CDs/…/Scans/`、`Scans/`；**沒有** `Fonts/` 與 `Menu/`。
  - [DBD-Raws 不死者之王 第二季](https://share.dmhy.org/topics/view/668157_DBD-Raws_Overlord_Overlord_S2_01-13TV_SP_1080P_BDRip_HEVC-10bit_FLAC_MKV.html)（106 檔）：`SP/`（帶編號，各配 `.sc.ass` / `.tc.ass`）、`PV/`、`NCOP&NCED/`、`menu/`（小寫）、`Fonts/Fonts.zip`（壓縮檔不是散檔）。

**只有集號、TMDB 上多季的真實發佈（2026-09-16，M1 票 14c，[研究](research/profile-effect.md#0-結論)）**：§6.4「只有集號 → 絕對編號」在 v1 的 23 筆語料上一次都沒走到（34 次全是 TMDB 只有一季），補 5 筆走得到的才量得出 Route profile 的作用。

- **動漫跨季連號換算得對**：SubsPlease `Spy x Family - 26`–`37`、`Boku no Hero Academia - 139`、Erai-raws `One Piece - 1089 ~ 1104`；TMDB 航海王第 22 季沿用官方集數當 `episode_number`（S22E1089–1155），所以只有 absolute group 換對，各季累加換成 S22E01 是錯的。
- **非動漫的「集號」可能是另一套數法**：《Home and Away》`Episode.8214.2024-02-29` 累加換成 S37E32，TMDB 的 S37E39 才是 `Episode 8214`（TMDB 前 36 季比官方多收 7 集）；`The.Return.of.Superman.E079.150524` 換成 S03E21 是對的。**「是不是動漫」預測不了換算對錯**（ADR 0003 移除 Route profile 的依據，見研究檔 §0）。
- **字幕組每 cour 重數、篇章名只寫羅馬字會被當絕對編號**：Erai-raws `Bleach - Sennen Kessen Hen - Soukoku Tan - 01 ~ 14` 換成 S01E01–14，正解 S02E27–40。
- **`guessit` 預設把韓國電視台 `YYMMDD` 讀錯**：`150524` 讀成 2024-05-15（本機實測），要加 `date_year_first`（[guessit 文件](https://guessit-io.github.io/guessit) `-Y, --date-year-first`）；加上後讀成 2015-05-24，四位數年份不受影響。
- 韓劇第二季以後、檔名沒有季號的 `Show.2.E01.YYMMDD` 在 TPB、Knaben、dmhy 都沒找到，第二季發佈全部帶 `S02E`。
- **「集號 ≤ 第一季集數就送審核」擋下的多半是對的**（2026-09-17，M1 票 14d，[研究 §6.1.1](research/profile-effect.md#611-規則-1-的代價m1-票-14d-第-1-步2026-09-17)，`scripts/experiments/absolute_rule_cost.py`）：5 部 ≥ 2 季的 Mikan 發佈走到絕對編號換算的檔案裡，集號 ≤ 第一季集數的**正解在第一季 928 個、在後面某季 167 個**；超過的 1,219 對、54 錯（錯的全是播出日對不上、退回序位，本身存疑）。「標題有認不出的多餘字」分不開兩者（連 TMDB `titles` 比放行 793 個第一季、漏 14 個後面季；只比三個主標題放行 328 個不漏，但英文標題同寫法的作品會入錯），故維持原形。限制：Mikan 只有標題沒有檔名、樣本以中文字幕組與動漫為主。

**Jellyfin 動漫命名的社群痛點**：

- One Piece / Detective Conan 這類長篇的 TVDB arc 順序 vs 絕對編號長期無解（[r/jellyfin](https://www.reddit.com/r/jellyfin/comments/1sny587/one_piece_tvdb_arc_order_vs_absolute_episode)、[tvdb-plugin#91](https://github.com/jellyfin/jellyfin-plugin-tvdb/issues/91)）；本系統只承諾「與 TMDB 一致」，不承諾符合任何社群偏好。
- Split-cour 被 Jellyfin 併成一季的抱怨很多（[r/jellyfin](https://www.reddit.com/r/jellyfin/comments/1r5sk02/any_way_to_have_anime_seasons_shown_in_parts_like)）；本系統不對抗 provider，只做正確對應。
- Sonarr FAQ 承認 Bleach TYBW 這類新 arc 只有編號與 TVDB 對上才自動匹配。

**mediainfo（pymediainfo 7.0.1，2026-09-11 對真檔案實測）**：

- `pip install pymediainfo` 的 wheel **內含 libmediainfo**，不需系統套件（[README](https://github.com/sbraz/pymediainfo)）。
- `MediaInfo.parse(path)` 回 track 清單，`track.to_data()` 是該條所有欄位。**同一個 `duration` 型別不同**：General 是整數毫秒（`2023`），Video 是字串（`"2000.000000"`）。
- 布林是字串 `"Yes"` / `"No"`（`forced`、`default`）；語言兩碼（`ja` / `en` / `zh`），`other_language` 另有別名；繁簡分不出來，字幕軌繁簡只寫在 `title`（與 §20.1 的 Jellyfin 同一限制）。
- 讀得完但不是媒體的檔案（如 `.txt`）**不丟例外**，回只有 General 的清單——所以「有沒有影像軌」才是「是不是影片」的判準。
- 證據：`tests/fixtures/mediainfo/two-second-episode.mkv`、`tests/unit/test_mediainfo.py`。

### 20.5 名稱衝突檢查

以 tavily basic 搜尋 GitHub / npm / PyPI / Docker Hub / App Store，非窮盡商標檢索。完整比對表在 [`docs/research/name-conflict-check.md`](research/name-conflict-check.md#205-名稱衝突檢查)。

- **Berth：可用（已定案）**。精確比對（2026-09-07）：GitHub 無同領域專案，最接近的是 macOS SSH 客戶端 xinghelee/Berth（31★）；PyPI `berth` 是 2017 年停更的打包工具；npm `berth` 已標記 deprecated；Docker Hub 有 `berth/` 組織（舊 OpenStack 容器化專案，已停）。本系統以 `ghcr.io/<owner>/berth` 發佈，不需要這三個註冊名。
- 備選名稱：Lading、Cleat、Longshore、Mooring、Keelhaul 可用；Wharf、Gangway、Drayage 輕微衝突；Dockhand（5.8k★ 自託管 Docker 管理工具）、Stow、Quay、Tally、Stevedore **衝突**。

### 20.6 實作前必做的實驗【研究】

**已完成（2026-09-07，票 04）**。完整結果與量測方式在 [`docs/research/m0-experiments.md`](research/m0-experiments.md)，腳本在 `scripts/experiments/`，可重跑；brief 原記載的逐條清單在同檔 [〈從 brief 搬來（§20.6）〉](research/m0-experiments.md#從-brief-搬來206)。結論與尚未完成的項目：

- **硬鏈接通過**（`hardlink.sh`）：NTFS 9p bind mount 與 ext4 bind mount 皆 nlink=2、inode 相同；分成兩個 volume 回 `Cross-device link` 並退出 1。但 ext4 那一輪跑的是 Docker Desktop 自己的 Linux VM（`docker-desktop` 發行版），不是另一台實體 Linux 宿主。原生 Linux 已在 2026-10-09 跑過（M4 票 42，§20.14）；Unraid 7.1.4 user share 已在 2026-10-08 跑過（M4 票 55，§20.14）。**剩下：至少一台 NAS**（Synology / QNAP / TrueNAS 其一），`sh hardlink.sh /volume1/<share>` 即可。
- 標籤含中文：12.x 已實測是純 tag（`docs/research/jellyfin-12.md`），見 §20.1「多版本」。
- qBittorrent 4.4 與 5.x 參數相容：完成，見 §20.7「qBittorrent 版本矩陣」。`WebUI\ServerDomains=qbittorrent` 足以通過 Host 檢查，但使用者從 `localhost:8080` 進不了 WebUI，所以維持不預置（§20.7、plan §9.2）。Prowlarr `config/host` Forms 帳密欄位名：完成，見 §20.7「Prowlarr」。
- Jellyfin 10.10/10.11 命名實測：完成，見 §20.7「Jellyfin 命名實測」。§7.2 電影範例與 §7.7 版本標籤說法已據此更正；plan §5 的模板凍結。
- Mikan / Nyaa 實際 RSS 擴充欄位（infoHash、大小、做種數、enclosure、發佈時間）：完成（2026-09-25，M3 票 07，含 acg.rip），見 §20.12。
- **未完成**：建立 20 筆真實 torrent fixture（動漫 8、美劇/韓劇 8、電影 4）作為 benchmark v0 → M1 解析器票。
- 字幕組編號換算失敗率：完成（2026-09-09，M1 票 01）。7,833 筆真實釋出，TMDB 8.0% / TVDB aired 7.6% / TVDB absolute 7.6%；§10 的【研究】據此結案為**維持 TMDB**。方法與結果在 [`docs/research/anime-episode-source.md`](research/anime-episode-source.md)，腳本 `scripts/experiments/anime_episode_source.py`。順帶推翻兩件事：§20.3 合併政策比原記載更激進（TMDB 連獨立的連續季也併，咒術 3 季→1 季、Re:Zero 4 季→1 季）；**TVDB absolute 會把 OVA 與劇場版也編號**（SPY×FAMILY 的 CODE: White 佔掉 absolute 38），所以 absolute ≠ 正篇第幾集。

### 20.7 開箱即用所需的 API 與 Windows Docker 事實

細節（完整實測原文、fixture 位置、原始碼連結）在 [`research/setup-api-facts.md`](research/setup-api-facts.md)；本節只留結論、決定性的數字 / 參數 / 狀態碼與查證日期。

**Windows Docker Desktop 硬鏈接**（本機實測，2026-09-07；Windows 11、Docker Desktop 29.6.2 WSL2、NTFS；[細節](research/setup-api-facts.md#windows-docker-desktop-硬鏈接)）

- 同一個 Windows 目錄 bind mount 成 `/data`，容器內 `ln` 成功（`dev=70`、inode 相同、`nlink=2`，掛載型態 `9p (aname=drvfs)`，宿主端 `fsutil hardlink list` 證實是真 NTFS 硬鏈接）。`torrent/` 與 `library/` 拆成兩個 bind mount：`ln: Cross-device link`，與 Linux 相同（單一掛載根的規則不變）。named volume（WSL2 ext4）也成功。
- 結論：**Windows 用一般 bind mount**（`DATA_ROOT=D:\Berth\data`），不需要 named volume；exFAT 不支援硬鏈接（[TRaSH](https://trash-guides.info/File-and-Folder-Structure/Hardlinks-and-Instant-Moves/)）；§4.4 的「不退回複製」維持。
- 不用 named volume 的理由：WSL2 VHD 預設上限 1 TB（[Microsoft](https://learn.microsoft.com/en-us/windows/wsl/disk-space)）、搬 VHD 的設定介面多起失效（[docker/for-win#13269](https://github.com/docker/for-win/issues/13269)）。bind mount 經 9p 吞吐較低（[Docker blog](https://www.docker.com/blog/file-sharing-with-docker-desktop)），下載寫入較慢，硬鏈接是 metadata 操作不受影響。

**Jellyfin 初始化與插件 API**（[OpenAPI](https://api.jellyfin.org/openapi/jellyfin-openapi-stable.json)、[FirstTimeSetupHandler.cs](https://github.com/jellyfin/jellyfin/blob/master/Jellyfin.Api/Auth/FirstTimeSetupPolicy/FirstTimeSetupHandler.cs)；[細節](research/setup-api-facts.md#jellyfin-初始化與插件-api)）

- `GET /System/Info/Public` 無需憑證，回 `StartupWizardCompleted`。
- `POST /Startup/Configuration`（`ServerName`、`UICulture`、`MetadataCountryCode`、`PreferredMetadataLanguage`）、`POST /Startup/User`（`Name`、`Password`）、`POST /Startup/RemoteAccess`、`POST /Startup/Complete`，以及 **`GET/POST/DELETE /Library/VirtualFolders`**，都掛 `FirstTimeSetupOrElevated`：精靈未完成時匿名可呼叫，完成後需管理員 token。`POST /Startup/RemoteAccess` Berth 只送 `EnableRemoteAccess`（10.11.11 schema 其實也有 `EnableAutomaticPortMapping`）。
- `POST /Library/VirtualFolders?name=&collectionType=&paths=&refreshLibrary=`：`collectionType` 為 `movies` / `tvshows` / `music` / `musicvideos` / `homevideos` / `boxsets` / `books` / `mixed`；body `{LibraryOptions}` 含 `PathInfos`、`EnableRealtimeMonitor`、`PreferredMetadataLanguage`、`MetadataCountryCode`、`TypeOptions[]`、`SeasonZeroDisplayName`、`EnableAutomaticSeriesGrouping`、`EnableEmbeddedTitles`、`AutomaticRefreshIntervalDays`。
- 既有媒體庫加路徑 `POST /Library/VirtualFolders/Paths?refreshLibrary=`，body `MediaPathDto {Name, Path, PathInfo{Path}}`；移除 `DELETE /Library/VirtualFolders/Paths?name=&path=`。路徑驗證 `POST /Environment/ValidatePath`，body `{ValidateWritable, Path, IsFile}`；另有 `GET /Environment/DirectoryContents?path=`。兩組皆 `FirstTimeSetupOrElevated`（OpenAPI 直接查核，2026-09-07）。
- **`ValidatePath` 看得到回 204、看不到回 404**：`IsFile: true` 走 `File.Exists`、`false` 走 `Directory.Exists`、不給則兩者皆否才算沒有（[EnvironmentController.cs](https://github.com/jellyfin/jellyfin/blob/master/Jellyfin.Api/Controllers/EnvironmentController.cs)，2026-09-08）。**404 是答案不是失敗**，adapter 翻成 `False` 不丟例外。Berth 不送 `ValidateWritable: true`（Jellyfin 會自己建暫存檔再刪）。
- 需管理員（`RequiresElevation`）：`GET/POST /Repositories`（`{Name, Url, Enabled}`）、`POST /Packages/Installed/{name}?assemblyGuid=&version=&repositoryUrl=`、`POST /System/Restart`、`GET /ScheduledTasks`、`POST /ScheduledTasks/Running/{taskId}`。
- MergeVersions：manifest `https://raw.githubusercontent.com/danieladov/JellyfinPluginManifest/master/manifest.json`、套件名 `Merge Versions`、GUID `f21bbed8-3a97-4d8b-88b2-48aaa65427cb`；排程任務 `Key` 為 `MergeMoviesTask` / `MergeEpisodesTask`（[RefreshLibraryTask.cs](https://github.com/danieladov/jellyfin-plugin-mergeversions/blob/master/Jellyfin.Plugin.MergeVersions/ScheduledTasks/RefreshLibraryTask.cs)）。**觸發要用 `GET /ScheduledTasks` 回的 `Id`，不是 `Key`**；`Id` 不跨安裝相同（實測那台 `MergeMoviesTask=fd957c84b0cfc2380becf2893e4b76fc`、`MergeEpisodesTask=dcaf151dd1af25aefe775c58e214477e`），一律現讀。本系統只支援 12 以上、不再安裝它（§19、§20.9）。

**Jellyfin 精靈序列實測**（2026-09-07，票 06；`jellyfin/jellyfin:10.11.11`，Berth adapter 跑完 plan §9.4 全序列，fixture 在 `tests/fixtures/http/jellyfin/`；[細節](research/setup-api-facts.md#jellyfin-精靈序列實測)）

- **`POST /Auth/Keys?app=` 回 204 且不回傳 key**，只能再 `GET /Auth/Keys` 從 `Items[].AppName` 找；**不檢查重複**，按兩次就有兩把 `AppName="Berth"`。所以先列再建、建完再列。
- **`POST /Library/VirtualFolders` 同名不會被拒**：第二次也回 204，建出 `Movies2` 指向同一路徑；冪等靠呼叫端先 `GET /Library/VirtualFolders`。
- **`POST /Library/VirtualFolders/Paths` 不去重**（同路徑送兩次 `Locations` 有兩個一樣的字串）；目錄不存在回 **404** `Error processing request.`，所以 Berth 先建目錄（與 Jellyfin 掛同一個容器路徑，§16.4）。
- **404 說不出原因**（2026-09-30 對 12.1 的 `bad-jellyfin-elsewhere` 再測，M4 票 19）：Jellyfin 看不到目錄與**媒體庫不存在**是同一個 `404` + `Error processing request.`（`text/plain`），`The path does not exist` 只在它自己的 log。所以 Berth 送之前先寫探測檔、以 `ValidatePath {IsFile: true}` 問。**不問目錄本身**：linuxserver 的 Jellyfin image 自帶空的 `/data`，沒掛任何東西時 `{Path: "/data", IsFile: false}` 也回 204。
- **`LibraryOptions.TypeOptions[]` 省略 `ImageFetchers` 會被存成空陣列**（送 `{Type, MetadataFetchers, MetadataFetcherOrder}` 讀回 `ImageFetchers: []`），該類型從此不抓圖。要嘛整個 `TypeOptions` 留空用預設，要嘛兩種 fetcher 都給。
- **`GET /Libraries/AvailableOptions?libraryContentType=movies|tvshows`** 回伺服器實際裝了哪些 fetcher（`{Name, Type}` 陣列），政策 `FirstTimeSetupOrDefault`，精靈期間匿名可讀。乾淨 10.11.11 的 Movie metadata 是 `TheMovieDb` / `The Open Movie Database`，image 多 `Embedded Image Extractor` / `Screen Grabber`；tvshows 分 Series / Season / Episode。裝官方 TVDB 插件後每型別多一個 `TheTVDB`，Series 另多 `Missing Episode Fetcher` —— 「image fetcher 不可寫死」的證據。
- **登入 token 與 API key 標頭同形**：`Authorization: MediaBrowser Client="…", Device="…", DeviceId="…", Version="…", Token="<token 或 key>"`，兩者都吃得下 `RequiresElevation`。
- **重啟三階段**：`POST /System/Restart` 當下連線被切（httpx `RemoteProtocolError`）→ 一段時間所有端點回 **503** → 才回 200；輪詢要把「連不上」與 503 都當繼續等。
- 九步序列對真伺服器 **69 秒**（多花在插件下載與重啟）；第二次 **0.2 秒**，除第 1 步外全 `skipped`。

**Prowlarr**（[OpenAPI](https://raw.githubusercontent.com/Prowlarr/Prowlarr/develop/src/Prowlarr.Api.V1/openapi.json)、[supported-indexers](https://wiki.servarr.com/prowlarr/supported-indexers)、[environment-variables](https://wiki.servarr.com/prowlarr/environment-variables)；[細節](research/setup-api-facts.md#prowlarr-api)）

- `GET /api/v1/indexer/schema`、`GET/POST /api/v1/indexer`、`DELETE /api/v1/indexer/{id}`（回 200）、`POST /api/v1/indexer/test`；`GET /api/v1/search?query=&indexerIds=&categories=&type=` 回 `ReleaseResource`（`title`、`size`、`seeders`、`leechers`、`downloadUrl`、`magnetUrl`、`infoHash`、`indexer`、`categories`、`publishDate`、`guid`、`infoUrl`、`tmdbId` …）。Prowlarr 明言**不提供跨站聚合 Torznab**（所以搜尋走 REST），單站 Torznab 為 `/{id}/api?t=search&apikey=`。
- **`indexer/schema` 第一次呼叫很慢**（2026-09-08 票 11 M0 驗收）：容器剛起來要從 `/config` 讀 **627 份** Cardigann 定義、組出 **5.6 MB** 回應，Windows Docker Desktop 9p bind mount 上 **9.42 秒**；第二次 0.34 秒。NAS 只會更久，所以這一支要有自己的逾時（現為 60 秒），不沿用探測的 5 秒。**未量測**：成因是冷讀定義而非回應大小，同時刻 `config/host` 理論上也慢，目前仍用 5 秒、沒有數據證明安全。
- API key 在 `config.xml` 的 `<ApiKey>`（首次啟動即產生，32 字元），可用 `PROWLARR__AUTH__APIKEY` 預設。
- 支援的公開索引站含：Nyaa.si、dmhy、AniDex、Anime Tosho、ACG.RIP、**Mikan**、1337x、YTS、EZTV、The Pirate Bay；TorrentGalaxy 目前不在清單。

**Prowlarr 索引站與 TMDB 憑證實測**（2026-09-08，票 08；Prowlarr 2.5.2.5491，fixture 在 `tests/fixtures/http/prowlarr/` 與 `tests/fixtures/http/tmdb/`；[細節](research/setup-api-facts.md#prowlarr-索引站與-tmdb-憑證實測)）

- **`POST /api/v1/indexer` 先連一次那個站再存**：成功 201 與整份資源；連不上 **400 加陣列**（每列 `{isWarning, propertyName, errorMessage, severity}`），站沒建立。「逐站成敗」因此來自新增那一支；`indexer/test` 給**已存在**的站（200 空物件）。`?forceSave=true` **不會**跳過檢查。**測試通過不保證新增成功**（新增是另一次連站，時好時壞的站兩次可能不同；2026-10-06 審計 Internet Archive：test 通過、緊接新增回「連不上」，[wizard-audit](research/wizard-audit-2026-10-06.md) S1 頁 4）；頁 4 主鍵因此把「測過而加不進去」與「測試就沒過」分開記（M4 票 44）。
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

**索引站搜尋實測**（2026-09-10，票 08；Prowlarr 2.5.2.5491 + 五個公開站 acgrip / dmhy / mikan / thepiratebay / yts；Torznab fixture 已刪，M4 票 37；[細節](research/setup-api-facts.md#索引站搜尋實測)）

- **`GET /api/v1/search` 很慢且不吃 `limit`**：單次冷查詢 60–85 秒，`limit=20` 仍回 1200 筆；三個查詢併發共 35 秒，所以逐標題併發、逾時給 120 秒。
- **`downloadUrl` / `magnetUrl` 每次請求都不同**（`link=` 密文帶 nonce，連跑兩次 1021 筆只重疊 1 筆），`guid` 穩定（1200/1200）：身分是 infohash 或 `guid`，不是下載網址。兩者是 Prowlarr **自己的代理網址**（主機來自它的 `config/host`）；磁力站（TPB、dmhy）沒有 `downloadUrl`，只有包成代理網址的 `magnetUrl`。**兩者帶 `?apikey=<Prowlarr API key>`**（M4 票 76），能改 Prowlarr 設定，所以不出伺服器（M4 票 79）：搜尋把每列連結記在 Berth 程序，前端只拿 id，送單收 id 換回連結（慣例照 Sonarr interactive search 的 `ReleaseController.cs`：`{indexerId}_{guid}` 快取 30 分鐘、找不到回 404「try searching again」；Berth 的 id 隨機、記兩小時，理由在 `berth/services/sources.py`）。
- **info hash 兩種寫法**：同一發佈在 Mikan 是 40 字十六進位、dmhy 是 32 字 base32，解碼後位元組相同；不正規化的話 1200 筆裡 47 筆重複顯示。
- **多標題是真的多一批東西**：`Spy x Family` / `SPY×FAMILY` / `间谍过家家` 各 1200 / 908 / 1210 筆，聯集 1854，各自帶來 391 / 196 / 169 筆另兩者問不到的結果。
- **tmdbid 是私站的功能**：627 份定義裡 93 份的 `tvSearchParams` / `movieSearchParams` 含 `tmdbId`，**全是 private 或 semiPrivate**；十個預設公開站一個都沒有（YTS 只有 `imdbid`）。所以 `q=` 才是常態（Prowlarr REST 本來只收關鍵字）。
- **分類碼不是可靠篩子**：dmhy 對 `cat=5000`、`cat=5070`、不帶 `cat` 都回同樣 80 筆，且一筆帶 5070 / 100002 / 2020 而沒有 5000。Berth 不送 `categories`，分類只當顯示資料。
- **The Pirate Bay 對搜不到的關鍵字回自己的熱門清單**（搜 SPY×FAMILY 前六筆是 Spider-Man、Ted Lasso 等，做種四千到六千），純做種排序會把真結果擠出前 100 筆；Berth 先用標題粗篩再逐站輪流取。
- **公開中文站做種數是個位數**：Mikan / ACG.RIP / dmhy 多半 0–2 個，TPB scene 28–86；取「做種前 100 筆」等於把中文字幕組整批刪掉。
- **`parse_release` 每筆 14 毫秒**（1200 筆 17.4 秒，含 guessit），全解析會卡事件迴圈半分鐘，所以粗篩用純字串比對，解析只跑留下的 100 筆。

**Jackett**（[repo](https://github.com/Jackett/Jackett)；[細節](research/setup-api-facts.md#jackett)）

- API key 在 `ServerConfig.json` 的 `APIKey`；聚合 Torznab `/api/v2.0/indexers/all/results/torznab/api?t=search` 有文件（上限 1000 筆、站專屬分類不可用）；`GET/POST /api/v2.0/indexers/{id}/Config` 只是 UI 內部介面、無文件。有 `mikan.yml`、`dmhy.yml`、`nyaasi.yml`、`acgrip.yml`。
- ~~結論維持 §19：套件預設 Prowlarr，Jackett 以 Torznab 端點接入。~~ **已不採用**（2026-10-06 D3、M4 票 37）：只支援 Prowlarr；以上留作紀錄（[ADR-0001](adr/0001-indexer-manager-prowlarr-only.md)）。

**compose 套件實測**（2026-09-07，Windows 11 + Docker Desktop 29.6.2，票 03；[細節](research/setup-api-facts.md#compose-套件實測)）

- **發佈 port 的來源位址**：Docker Desktop 把 `-p 8080:8080` 進來的流量 SNAT 成 bridge 閘道（`172.28.0.1`），閘道本身就在 compose 網段內。所以 `WebUI\AuthSubnetWhitelist=172.28.0.0/16` 等於讓宿主與 LAN 任何人免密打 qBittorrent API（實測 `curl http://localhost:8080/api/v2/app/version` 直接回 `v5.2.3`）。縮成 Berth 容器固定 IP `172.28.0.2/32` 後：berth 容器 200、宿主 403、同網段其他容器 403。§16.3「LAN 使用者開 8080 仍要密碼」只有白名單是單一位址時才成立。
- Docker 動態 IP 從網段開頭配發（`172.28.0.2` 給了先啟動的 prowlarr），固定 IP 要靠 `ip_range` 把動態池隔到別段，否則會撞。
- **linuxserver/qbittorrent 啟動順序**：`init-qbittorrent-config` 排在 `init-custom-files`（custom-cont-init.d）之前，腳本跑到時 `/config/qBittorrent/qBittorrent.conf` **一定已存在**（image 從 `/defaults/qBittorrent.conf` 複製）。所以「檔案不存在才寫」永不成立，改「缺鍵才補」。
- **缺鍵才補的另一面：在 WebUI 關掉或改掉白名單，重啟補不回來**（M4 票 53，2026-10-07，`5.2.3_v2.0.15-ls478`）：以 `app/setPreferences` 的 `bypass_auth_subnet_whitelist_enabled: false` 關掉後 `docker restart`，腳本印 `already configured`，`WebUI\AuthSubnetWhitelistEnabled=false` 不變。補法在 WebUI「選項 → WebUI → 驗證」的「讓已在白名單中的 IP 子網路略過驗證」（英文 *Bypass authentication for clients in whitelisted IP subnets*；標籤取自 qBittorrent `release-5.0.0` 的 [`preferences.html`](https://github.com/qbittorrent/qBittorrent/blob/release-5.0.0/src/webui/www/private/views/preferences.html) 與 [`webui_zh_TW.ts`](https://github.com/qbittorrent/qBittorrent/blob/release-5.0.0/src/webui/www/translations/webui_zh_TW.ts)）。
- `/defaults/qBittorrent.conf`：`LegalNotice\Accepted=true`、`WebUI\Address=*`、`WebUI\ServerDomains=*`、`Downloads\SavePath=/downloads/`、`Downloads\TempPath=/downloads/incomplete/`、`Connection\UPnP=false`、`Connection\PortRangeMin=6881`。整份覆蓋會掉 `LegalNotice\Accepted`（qbittorrent-nox 卡在法律聲明）；`ServerDomains` 預設 `*` 本來就過 Host 檢查，寫死 `qbittorrent` 反讓使用者從 `localhost:8080` 進不去。
- `init-custom-files` 只檢查 executable bit（不檢查擁有者），以 `/bin/bash <script>` 執行（[docker-baseimage-alpine](https://github.com/linuxserver/docker-baseimage-alpine/blob/master/root/etc/s6-overlay/s6-rc.d/init-custom-files/run)、[container-customization](https://docs.linuxserver.io/general/container-customization/)）。`lscr.io/linuxserver/qbittorrent:latest` 當時是 v5.2.3。
- Berth image（node:24-slim build → python:3.13-slim runtime）：281 MB 未壓縮、62.8 MB gzip，遠低於 400 MB 上限。`python:3.13-slim`（Debian 13 trixie）內建 `setpriv`、`usermod`、`groupmod`、`getent` 與 tzdata，`PUID` / `PGID` 降權不需裝 gosu；但沒有 curl。
- 空 named volume 與 Docker 替 bind mount 新建的目錄都是 `root:root`，非 root 容器寫不進去。入口腳本因此只在 `/data` 還是空目錄時接手擁有者，有內容的媒體根不碰（實測：空目錄 → `1500:1500`、`umask 002`；非空 → 維持 `root:root`）。
- compose 內 `/data` 硬鏈接再確認：`dev=70`、inode 相同、`nlink=2`（與本節開頭 Windows 實測一致）。

**TMDB 憑證由使用者自備**（2026-09-09 決定，推翻本節原本的「沿用 Seerr 的專案級 key」；[細節](research/setup-api-facts.md#tmdb-憑證由使用者自備)）

- Jellyseerr / Seerr 在 `server/api/themoviedb/index.ts` 寫死專案 key（[overseerr#3887](https://github.com/sct/overseerr/issues/3887)）；Jellyfin 團隊也討論過（[jellyfin#36](https://github.com/jellyfin/jellyfin/issues/36)）。TMDB 條款只區分商業與非商業，未明文規範「一 app 一 key」，那條路走得通，**本系統仍不走**：共用憑證由專案背用量與行為，TVDB ToS 明文擋的正是這件事（§20.3），兩個 provider 在「使用者自己申請」上對稱。
- 憑證唯一來源 `settings.services.tmdb.api_key`，精靈第 6 步是**必填閘門**（plan §9.3）。申請：themoviedb.org 免費帳號 → 設定 → API → 用途選 Personal / Education，即時核發；同一頁給 v3 key 與 v4 read access token，兩種形狀 Berth 都收（plan §8.3，2026-09-08）。

**qBittorrent 預置**（[sessionimpl.cpp](https://github.com/qbittorrent/qBittorrent/blob/master/src/base/bittorrent/sessionimpl.cpp)、[linuxserver/qbittorrent](https://docs.linuxserver.io/images/docker-qbittorrent)、[qbittorrent-nox](https://github.com/qbittorrent/docker-qbittorrent-nox)；[細節](research/setup-api-facts.md#qbittorrent-預置)）

- 4.6.1 起首次啟動用隨機臨時密碼印在 log；已知密碼要預置 `WebUI\Password_PBKDF2`（PBKDF2-HMAC-SHA512、100000 次）。官方 image 沒有密碼環境變數，也沒有 `PUID` / `PGID`；linuxserver image 有，設定檔在 `/config/qBittorrent/qBittorrent.conf`。
- `[Preferences]`：`WebUI\Port`、`WebUI\AuthSubnetWhitelistEnabled`、`WebUI\AuthSubnetWhitelist`、`WebUI\LocalHostAuth`、`WebUI\HostHeaderValidation`、`WebUI\CSRFProtection`；`[BitTorrent]`：`Session\DefaultSavePath`、`Session\TempPath`、`Session\TempPathEnabled`、`Session\DisableAutoTMMByDefault`（**預設 true，即 autoTMM 關閉**）、`Session\DisableAutoTMMTriggers\CategorySavePathChanged`、`Session\Port`。
- Web API `app/setPreferences` 對應鍵：`temp_path_enabled`、`temp_path`、`save_path`、`auto_tmm_enabled`、`category_changed_tmm_enabled`、`bypass_auth_subnet_whitelist(_enabled)`、`bypass_local_auth`、`web_ui_password`（只寫，讀回來的偏好沒有它）。

**Jellyfin 命名實測**（2026-09-07，票 04；`jellyfin/jellyfin:10.10.7` 與 `:10.11.11`，dummy 檔 + API 查驗；[完整結果](research/m0-experiments.md#1-jellyfin-命名10107-與-101111)、[原文](research/setup-api-facts.md#jellyfin-命名實測)）

- `S01E01` 一律認得，`S01E03-E04` → `IndexNumber=3` + `IndexNumberEnd=4`，`S00E01` 進 `Specials`。**方括號與 `+` 不會滲進 Series 或 Episode 名稱**（Jellyfin 不從檔名取集標題）。
- **電影多版本**：檔名在 ` - ` 之前必須與資料夾名一字不差（含 `[tmdbid-<id>]`），否則成兩部獨立電影；標籤含方括號沒問題（版本選單顯示 `[BD][2160p][CHT+JP][Sakurato]`），結尾 `p`/`i` 的標籤依解析度降冪，其餘字母序。§7.2 已據此更正。
- **劇集多版本**：未裝插件 → 同集兩檔變兩個重複 Episode；裝 MergeVersions 跑 `MergeEpisodesTask` → 合成 1 個 Episode、2 個 MediaSource，但**版本標籤是整個檔名主幹**非只有 tags，順序不保證（10.10 與 10.11 相反）。§7.7 已據此更正；12.x 不裝插件就原生合併，見 §20.9。
- **extras**：`<作品>/extras/`、`<作品>/Season 01/extras/`、`<電影>/extras/` 三者都成立，掛在 Series / Season / Movie 的 `SpecialFeatures`，不當正片。
- **外掛字幕**：`<stem>.CHT.zh.ass` 在 10.10 顯示 `CHT - Chi - ASS - 外部`、10.11 `CHT - Chinese - ASS - 外部`（繁簡分得出來）；`.default.` 兩版都生效；`zh-Hant`/`zh-Hans` **只有 10.11 認得**，10.10 顯示「未定義」→ 不採用。
- 深連結 `#!/details?id=…&serverId=…` 兩版都開得到詳細頁。
- **精靈**：`POST /Startup/User` 之前**必須先 `GET /Startup/User`**（它建立預設使用者），否則回 **500**（`Sequence contains no elements`）。`POST /Library/VirtualFolders` 的 body 是 `AddVirtualFolderDto`，`LibraryOptions` **要包一層**（`{"LibraryOptions": {...}}`），直接送一樣回 204 但整份設定被靜默丟掉。
- **MergeVersions**：`POST /Packages/Installed/Merge%20Versions?assemblyGuid=…` 不必指定版本（10.10.7 裝到 `10.10.0.5`、10.11.11 裝到 `10.11.0.1`）；下載由 Jellyfin 連 GitHub，遇過 TLS 中斷回 500，要能重試。以上是 M0 對 10.x 的紀錄；本系統只支援 12 以上、不再安裝（§19）。排程任務 `Name` 為 `Merge All Episodes` / `Merge All Movies`，`Category` 為 `Merge Versions`。
- **重啟後不能只等 `/System/Info/Public`**：它在伺服器載入中就回 200，這時管理員 API（如 `/ScheduledTasks`）回 **503「Jellyfin 伺服器載入中」**；要輪詢真正要用的端點回 200 才算完成。
- **`find_episodes` 陷阱**：10.11 第一次掃描後，已被 provider 認出的 Series，`/Items?parentId=<seriesId>` 與 `/Shows/{id}/Episodes` **都回 0**，再掃一次才正常；10.10、12.0.0 沒有（§20.8）。改用 `parentId=<library>&recursive=true` 再照 `Path` 前綴篩選，四種情況都對。

**qBittorrent 版本矩陣**（2026-09-07，票 04；`lscr.io/linuxserver/qbittorrent:4.4.5`（API 2.8.5）與 `:5.2.3`（API 2.15.1）；[完整結果](research/m0-experiments.md#2-qbittorrent-445-與-523)、[原文](research/setup-api-facts.md#qbittorrent-版本矩陣)）

- **`torrents/add` 回應形狀兩版不同**（2026-09-10 票 09 對兩台乾淨容器實測，fixture `tests/fixtures/http/qbittorrent/torrents-add.*`）：4.4.5 成功 `200` + `Ok.`；**5.2.3 成功 `200` 加 JSON 摘要**（`{"added_torrent_ids": […], "failure_count": 0, "pending_count": 0, "success_count": 1}`），推翻原本「一律回 `Ok.`」。失敗也說得出話：同一磁力連結第二次送在 5.2.3 是 `409 Conflict`（4.4.5 照回 `Ok.`），category 的 save path 當下用不了也是 `409`；multipart 上傳非 torrent 是 `415` 加檔名與原因。
- **交 http 網址給 `torrents/add` 是背景抓取**：5.2.3 回 `202` + `pending_count: 1`，抓失敗後**永遠沒有下文**，用戶端已回過 2xx。所以 Berth 自己先抓 torrent（`adapters/torrent.py`），交出去的一律是磁力連結或位元組，「收不收」當場有答案（票 09）。
- **`paused` 與 `stopped` 各版本只認一個，送錯的靜默地開始下載**（`torrents/add` 一律 200，不認得的參數不報錯）：4.4.5 `paused=true` → `pausedDL`、`stopped=true` → `queuedDL`；5.2.3 `paused=true` → `stalledDL`、`stopped=true` → `stoppedDL`。plan §8.1 的版本判斷是必要條件，不是最佳化。
- **`torrents/files[].name` 相對 `save_path`**（多檔含 torrent 根目錄那一層），四種 `contentLayout` 組合都成立；`content_path` = save_path + 根目錄，單檔指向檔案、多檔指向目錄。單檔 + `Subfolder` 的子資料夾名是去掉副檔名的 torrent 名。**`save_path` 尾斜線兩版不同**（4.4.5 `/downloads/`、5.2.3 `/downloads`），組路徑前要正規化。
- **沒下完時 `content_path` 在分類的未完成目錄，`save_path` 已是完成後的位置**（2026-10-13 M4 票 74，5.2.4）：`berth-tv` 分類下 `stalledDL` 的一包，`save_path=/data/torrent/complete/tv`、`download_path=/data/torrent/incomplete/tv`、`content_path=/data/torrent/incomplete/tv/<根目錄>`；`torrents/files[].name` 仍相對那一層。刪下到一半的包看 `content_path`（`services/deletion._where_files_are`）。
- `torrents/files` 的鍵兩版相同：`index`、`name`、`size`、`progress`、`priority`、`is_seed`、`piece_range`、`availability`。`torrents/categories` 兩版都回駝峰 `savePath`（沒有 `save_path`）；5.2.3 另有 `download_path`、`ratio_limit`、`seeding_time_limit`、`inactive_seeding_time_limit`、`share_limit_action`。
- **Host 檢查除網域還比對 port**：`ServerDomains=*` 也擋 port 不符（`Host: localhost:18080` → **401**，容器 log `Invalid Host header, port mismatch`）。設成 `qbittorrent` 後 `localhost:8080`、`127.0.0.1:8080` 全被擋；沒有 port 的 Host 一律放行。偏好鍵 `web_ui_host_header_validation_enabled`（兩版都有）。實驗改的是 runtime 偏好 `web_ui_domain_list`（對應 `WebUI\ServerDomains`），沒另測「預置 ini 鍵」路徑。→ compose 的 qBittorrent **發佈 port 只能內外兩側一起改**（只改外側使用者開不了 WebUI）：M3 票 06b 以 `QBITTORRENT_WEBUI_PORT` 同時設兩側與 `WEBUI_PORT`（plan §9.2）。
- **CSRF**：送了 `Origin`/`Referer` 就必須與 Host 一致（不一致 → 401），完全不送則放行；兩版相同。

**Prowlarr `config/host`**（2026-09-07，票 04；Prowlarr 2.5.2.5491；[細節](research/setup-api-facts.md#prowlarr-host-config)）

- `GET /api/v1/config/host` 回 39 個欄位；認證相關：`authenticationMethod`（`none`/`basic`/`forms`/`external`）、`authenticationRequired`（`enabled`/`disabledForLocalAddresses`）、`username`、`password`、`passwordConfirmation`、`apiKey`。
- 設 Forms 帳密：`PUT /api/v1/config/host/1`，body 是完整 config/host 物件加上述五欄位（**少了 `passwordConfirmation` 會被拒**）→ 回 **202**，Prowlarr 隨即自行重啟，要等它回來。
- 設完後不帶 `X-Api-Key` 的 API 回 401，**`GET /ping` 仍匿名 200**（健康檢查不會因加密碼變紅，也是「回來了沒」的判準）；`password` 讀回來是雜湊。API key 從 `config.xml` 的 `<ApiKey>` 讀（與 plan §9.2 一致）。

**Jellyfin 帳號規則與伺服器的 metadata 語言**（2026-10-03，M4 票 29；原始碼 v12.1 的 [UserManager.cs](https://github.com/jellyfin/jellyfin/blob/v12.1/Jellyfin.Server.Implementations/Users/UserManager.cs)、[StartupController.cs](https://github.com/jellyfin/jellyfin/blob/v12.1/Jellyfin.Api/Controllers/StartupController.cs)、[ConfigurationController.cs](https://github.com/jellyfin/jellyfin/blob/v12.1/Jellyfin.Api/Controllers/ConfigurationController.cs)、[ServerConfiguration.cs](https://github.com/jellyfin/jellyfin/blob/v12.1/MediaBrowser.Model/Configuration/ServerConfiguration.cs)；實測 `scripts/experiments/jellyfin_username_rules.py`；[細節](research/setup-api-facts.md#jellyfin-帳號規則與-metadata-語言)）

- **帳號**：`ThrowIfInvalidUsername` 要求不空白、符合 `ValidUsernameRegex` = `^(?!\s)[\w\ \-'._@+]+(?<!\s)$`、不是 `.` 或 `..`；違規丟 `ArgumentException` → HTTP 400。.NET 的 `\w` 是 `[\p{L}\p{Mn}\p{Nd}\p{Pc}]`，中日文帳號照收；`< > & " / \ : #` 與空格以外的空白（tab）不收，前後不能是空白。master 與 release-12.z 同一條；建立（`CreateUserAsync`）與改名（`RenameUser`）都過它。前端照它先擋（`web/src/setup/jellyfinUsername.ts`）。
- **`POST /Startup/User` 的順序**：第一個使用者已有密碼 → **403**；密碼 `IsNullOrWhiteSpace` → **400** `Password must not be empty`；然後 `UpdateUserAsync`、**名字不同才 `RenameUser`**（帳號在這裡被拒）、最後 `ChangePassword`。帳號被拒時密碼沒設，第一個使用者仍「沒有密碼」，改名再送即可。
- **`GET /System/Configuration`** 掛 `[Authorize]`（任何登入使用者，API key 也行），回 `ServerConfiguration`：`PreferredMetadataLanguage`（預設 `en`）、`MetadataCountryCode`（預設 `US`）、`UICulture`（預設 `en-US`）——`/Startup/Configuration` 寫的就是這三格。套件內媒體庫照前兩格建（plan §9.4 第 4 步），fixture `tests/fixtures/http/jellyfin/system-configuration.json`。
- **實測**（`lscr.io/linuxserver/jellyfin:version-12.1ubu2604`，一次性容器）：精靈期間 `POST /Startup/User` 對 `a<b`、`a>b`、`a&b`、`a"b`、`a/b`、`a`、`a:b`、`a#b`、含 tab、`.`、`..` 都回 **400 `Error processing request.`**（原文不說是帳號問題，所以畫面只能說「那一段沒做完」），每次之後都能再試；只有空白的密碼回 400 `Password must not be empty`；`船長 01` 回 204。管理員之後 `POST /Users/New`：`skipper`、`o'brien`、`a.b@c+d-e_f`、`José`、`ナミ`、`..x` 收（200），`a<b`、`.`、` lead` 拒（400）。`GET /System/Configuration` 帶 token 200、讀回剛寫的 `zh-TW` / `TW`，匿名 401。

**硬鏈接腳本**（`scripts/experiments/hardlink.sh`，2026-09-07；[細節](research/setup-api-facts.md#硬鏈接腳本)）

- Linux ext4 單一掛載根：PASS（nlink=2、inode 相同）。Windows NTFS bind mount（9p）：PASS（dev=70）。`torrent/` 與 `library/` 分兩個 volume：`ln: Cross-device link`，退出碼 1。
- ext4 那一輪來源是 **Docker Desktop 自己的 Linux VM**（daemon 端檔案系統，與原生 Linux 宿主同一條 `link()` 路徑，但**不是另一台實體 Linux**）。腳本無相依，NAS 上 `sh hardlink.sh /volume1/<share>` 可跑。2026-10-08 在 Unraid 7.1.4 user share 上 PASS（§20.14）；其他原生 Linux 宿主與 NAS 尚未實測（§20.6）。

### 20.8 媒體庫瀏覽用的 Jellyfin API（M1.5 前置）

2026-09-15 查證；全文、端點範例與原始碼連結見 [`docs/research/library-browsing.md`](research/library-browsing.md)。2026-09-15 在 **12.0.0** 上實測，2026-09-17 在一次性的 **12.1.0** 上以只開放部分媒體庫的使用者補測權限、過濾排序、TMDB 反查、標記遞迴與停用帳號（M1.5 票 01，`scripts/experiments/jellyfin_permissions.py`，研究 §0、§2、§3.1、§5、§10、§11；12.0.0 量過的行為在 12.1.0 上沒看到不同，只有圖片 CORS 標頭的條件判定不了）。原始碼對照 tag `v10.10.7`、`v10.11.11`、`v12.0`。

下面每條只留結論、數值與來源；被壓縮的那幾條逐字原文在 [`library-browsing.md`](research/library-browsing.md#從-brief-搬來208)（大媒體庫那條在 [`large-library.md`](research/large-library.md#從-brief-搬來208)）。

- **伺服器 API key 可以代讀代寫任何使用者**：API key 在驗證層一律算 Administrator，帶哪個 `userId` 就是誰（三版一致）。用到的端點：繼續觀看 `GET /UserItems/Resume?userId=&mediaTypes=Video`（不帶 `mediaTypes` 會混進 Season 與 Series）、下一集 `GET /Shows/NextUp?userId=`、附 `UserData` 的 `GET /Items?userId=`、已看 / 未看 `POST|DELETE /UserPlayedItems/{id}?userId=`。不帶 `userId` 時 Resume、NextUp、PlayedItems 回 400，`/Items` 回整台伺服器且沒有 `UserData`。NextUp 的 `disableFirstEpisode` 在 12.0 移除。【實測 12.0.0 + 原始碼；研究 §1】
- **媒體庫存取權限只有一部分會套用**（家長分級只要帶 `userId` 就套，這一條只讀原始碼）：`/UserViews?userId=`、不帶 `parentId` / `ids` 的 `/Items`、`/Items/{id}?userId=`、`/Shows/{id}/Seasons|Episodes?userId=`、`/UserPlayedItems` 等會照使用者的權限；**帶 `parentId` / `ids` / `seriesId` 的查詢，以及帶 `parentId` 的 `/Genres`、`/Years`、`/Items/Filters(2)`、`/Items/Latest` 不會**。而且**使用者自己的 token 也只擋下 `/Items?parentId=<無權的媒體庫>`（401）**，其餘一樣照回。所以權限要由 Berth 自己擋，`parentId` 只放對 `UserViews` 驗證過的媒體庫 id（§12、plan §11.2b）。完整端點表見研究 §2。【實測 12.1.0 + 原始碼】
- **`/Items` 靜默忽略不存在的參數**：實測帶 `seriesId` 或 `ancestorIds` 都回整台伺服器的集，打錯字的 `genre=`、`year=` 回全部（12.0.0、12.1.0）。每個過濾參數都要測「伺服器真的有過濾」。
- **漏帶 `userId`**：`/Shows/{id}/Seasons|Episodes` 回 200 並**略過權限**（無聲洩漏），`/Items/{id}` 回 400，Resume、NextUp、`UserPlayedItems` 回 400。【實測 12.1.0】
- **排序與篩選**（研究 §3）：`sortBy`（逗號、多鍵）加 `sortOrder`；`genres` 以 `|` 分隔（「或」）、`years` 以逗號（「或」），兩個參數之間是「且」。類型與年份清單用 `GET /Items/Filters?userId=&parentId=&includeItemTypes=Series|Movie`（**不帶 `parentId` 四份清單全空**；`Filters2` 沒有年份；`/Years` 不帶 `includeItemTypes` 會混進集的播出年）。劇集的「新集加入」排序是 `DateLastContentAdded`、「最近看過」是 `SeriesDatePlayed`；電影的「最近看過」是 `DatePlayed`。jellyfin-web 的排序選單兩種媒體庫不同（`tvshows.js` / `movies.js`，v10.10.7 與 v10.11.11 相同，清單見研究 §3.1）；`sortOrder` 只送一個時套在每一個鍵上。12.1.0 逐一驗過 `parentId`、`includeItemTypes`、`genres`、`years`、`startIndex` / `limit` 真的有過濾；排序鍵除了劇集庫的 `DateCreated`、`OfficialRating`（只驗到升降冪互為反序）與 `Random` 之外，都驗到照值排序；`sortBy`、`sortOrder`、`genres`、`years` 各有一份錄製給契約測試（票 06）。**`searchTerm` 是名字裡的任一段、不分大小寫**，照權限過濾，照 `sortBy` 排、不換成相關度；參數名打錯（`search=`）被靜默忽略（2026-09-24 在 12.1.0 實測，M2 票 14）。沒有值的排在升冪最前；劇集的分級照高低（`TV-G < TV-PG < TV-14 < TV-MA`）不是照字串。`enableImages=false`、`enableUserData=false` 真的拿掉 `ImageTags` 與 `UserData`，而 `enableTotalRecordCount=false` 在不帶 `limit` 時照樣回 `TotalRecordCount`。【實測 12.1.0】
- **選季選集**：`/Shows/{id}/Seasons?userId=` 與 `/Shows/{id}/Episodes?userId=&seasonId=`（jellyfin-web 詳細頁的查法，會套權限）。§20.1 的「10.11 第一次掃描後回 0」**在 12.0.0 沒有重現**（一次性容器：掃完當下、兩分鐘後、第二次掃描後都對）；10.11 沒有重測，那一條仍成立，後備是媒體庫遞迴查詢照 `Path` 分群（三版都驗過）。
- **一部劇的每一集**（M5 票 28，作品頁與助理分得出「Jellyfin 已有、帳本沒有」）：`/Shows/{id}/Episodes?userId=&isMissing=false` **不帶 `seasonId`** 一次回整部劇每一季的集（含 S00；多集檔帶 `IndexNumberEnd`；都是 `LocationType: FileSystem`），筆數等於逐季加總；**權限照套**：無權的劇一樣 404 `"Series not found"`。不帶 `fields` 也有 `ParentIndexNumber` / `IndexNumber` / `IndexNumberEnd`。`isMissing` 伺服器認得（`true` 回 0 筆，不是被忽略），但 `false` 真的會濾掉 metadata 補出來的虛擬缺集**沒有量到**：一次性的樹關了網路 metadata，造不出虛擬集。Berth 仍只問 `locate` 確認過的劇（同 NextUp 的規矩）。【實測 12.1.0，`scripts/experiments/jellyfin_permissions.py` 第 7 節，fixture `shows-episodes.series*.json`】
- **集對 TMDB 的鍵**（M5 票 28，2026-10-30；網路 metadata 開著、TMDB 對上的 SPY×FAMILY 四集）：**集的 `ProviderIds` 沒有 `Tmdb`**，只有 `Tvdb` 與 `Imdb`（值等於 TMDB 那一集的 `external_ids`；`Tmdb` 只在 Series 上），而且要帶 `fields=ProviderIds` 才回。**`PremiereDate` 不帶 `fields` 也有**，形狀是 `YYYY-MM-DDT00:00:00.0000000Z`（那一天的 00:00 UTC），四集都等於 TMDB 的 `air_date`（只量了 `MetadataCountryCode=TW`、`zh-TW`，別的地區有沒有差一天沒量）。metadata 對不上的集 `ProviderIds` 是 `{}`、沒有 `PremiereDate`。所以 Berth 照播出日對（差一天內、TMDB 只有一集的那一集；使用者 2026-10-30 定的「先照 TMDB 的集 id」做不了；照 Tvdb / Imdb 對要 TMDB 逐集的 `external_ids`，一集一個請求，不做），Jellyfin 的季集號不算數（可能照 TVDB 編），只分特典與正片（特典只與特典比）；同一天兩集、兩個 Jellyfin 的集對到同一集、對不上的都不算有，寧可多下一集。「差一天」是使用者定的寬度，沒有量過時區造成的差。【實測 12.1.0，`scripts/experiments/jellyfin_episode_providers.py`，fixture `shows-episodes.series.providers.json`】
- **圖片不需要驗證**：`GET /Items/{id}/Images/{Primary|Backdrop|Thumb}` 匿名 200，請求帶 `Origin` 時回 `Access-Control-Allow-Origin: *`；縮放用 `fillWidth` / `fillHeight` / `quality` / `format=Webp`。`tag` 只是快取鍵（錯的也回圖），URL 要帶 DTO 的 `ImageTags` 才會在換圖時失效。瀏覽器直連的前提是連得到 Jellyfin（與深連結同一個主機），HTTPS 的 Berth 配 HTTP 的 Jellyfin 是 mixed content（§19 已定由 Berth 代理）。
- **經 Berth 代理的圖**（M1.5 票 04，研究 §6.1，12.1.0 實測）：2:3 的原圖帶 `fillWidth=342&fillHeight=513`；**不帶 `format` 時照 `Accept` 挑格式**，所以代理固定送 `format=Webp`；`quality=90` 約 23 KB，jellyfin-web 的 `quality=96` 是它的兩倍多。**Jellyfin 自己存縮好的圖**，所以 Berth 端不另存。`/Items` 帶 `enableImageTypes=Primary&imageTypeLimit=1` 時連 `ImageBlurHashes` 一起回。
- **標為未看會清掉 `PlayCount` 與 `LastPlayedDate`**，復原不了。**對 Series / Season 標記會遞迴到底下每一集**：標已看把看到一半的位置歸零，標未看連之前單獨看過的集一起清掉；對季只動那一季。**遞迴的結果只有清單端點讀得到**（M1.5 票 11 的 e2e）：對整部劇標記之後，`/Items/{集}?userId=` 仍回 `Played=false`，`/Shows/{劇}/Episodes?userId=` 與 `/Items?ids=` 才對（單集自己標記時兩邊都更新）。Berth 讀集一律走 `/Shows/{id}/Episodes`。【實測 12.1.0】
- **由 TMDB id 找作品**：`/Items` 沒有 provider id 過濾參數（猜的參數名都被忽略），但有 `hasTmdbId`。`GET /Items?userId=&recursive=true&includeItemTypes=Series,Movie&hasTmdbId=true&fields=ProviderIds` **不帶 `parentId`** 就會套權限，在 Berth 端比 `ProviderIds.Tmdb`；沒權限的媒體庫裡的那一份不會回來。已知 item id 時用 `/Items/{id}?userId=` 驗可見性（研究 §10）。【實測 12.1.0】
- **jellyfin-web 卡片上的觀看標記**（M1.5 票 05，研究 §7.1，v10.11.11 原始碼）：劇集 `UnplayedItemCount` 非 0 就畫集數，否則 `Played` 或 `PlayedPercentage >= 100` 畫勾；進度條只給影片（`MediaType=Video`）。已看切換不確認、就地改那一格。Berth 的判定照它（`services/watch.py`），但標為未看先確認（上一條：復原不了）。【原始碼】
- **繼續觀看與下一集**（M1.5 票 07，研究 §7.2）：jellyfin-web 首頁兩列一次取 12 / 24 項；NextUp 另送 `enableResumable=false`（**伺服器預設是 `true`**，不送的話看到一半的集兩列都出現）與 `nextUpDateCutoff=今天 − maxDaysForNextUp`（使用者設定，預設 365；伺服器預設沒有截止日）。`mediaTypes=Video`、`parentId`、`nextUpDateCutoff` 各有對照錄製證明伺服器真的過濾（12.1.0）；`enableResumable` 的效果只讀原始碼。**橫卡取圖**順序（自己的 Thumb → 上層的 Thumb → Backdrop → 自己的 Primary → 劇與季的 Primary）與條件見研究 §7.2；**12.1.0 沒有回 `SeriesThumbImageTag`**，劇的 Thumb 在 `ParentThumb*` 那一對。Berth 照這個順序取到集自己的 Primary 為止（電影不取 Primary：2:3 海報填進 16:9 只剩中間一條）。【原始碼 + 實測 12.1.0】
- **劇集詳情頁：這部劇的下一集**（M1.5 票 08，研究 §7.3）：jellyfin-web 只送 `SeriesId` 與 `UserId`。帶 `seriesId` 時**截止日不套用**，`enableResumable` 預設 `true`；「最後看過」是已標記看過的最大季集號，取它之後第一個還沒看完的，Specials 與缺片不算；**從沒看過回 S01E01**，看完了回空（三種情況各錄一份）。`/Items/{id}?userId=` 沒有 `fields` 參數，不必要就帶 `ProviderIds` 與 `UserData`。Berth 照 §10 找作品、以 `/Items/{id}?userId=` 確認看得到之後才問這部劇的 NextUp（帶 `seriesId` 不套權限）。【原始碼 + 實測 12.1.0】
- **沒有直接開始播放的網址**（§12 維持）：三版的 `#/video` 都不吃 item id，「播放某一集」只能深連結到那一集的 `#/details?id=`。
- **帳號狀態**：Jellyfin 停用帳號之後，**API key 代讀這位使用者的 `UserViews`、`/Items`、Resume、NextUp、Seasons 照常回資料，`UserPlayedItems` 照常寫入**；只有他自己的 token 回 401、重新登入回 403。`GET /Users/{id}` 讀得到 `Policy.IsDisabled` 與 `EnabledFolders`（與 `UserViews` 的 `Id` 同一種格式）。所以 Berth 要自己讀 `Policy`（§19 已定）。【實測 12.1.0】**刪除的帳號**（M2 票 11，[`docs/research/large-library.md`](research/large-library.md) §4）與停用不同：API key 代讀他的**每一支都是 404**（沒有寫入），重新登入 Berth 是帳密錯。Berth 只把 `Users/{id}` 的 404 當成與停用同一種處置（`UserViews` 的 404 可能是位址設錯，仍是問不到）（刪掉他的每一張 session、401 `account_disabled`，使用者拍板）。【實測 12.1.0】
- **大媒體庫的代價**（M2 票 11，[`docs/research/large-library.md`](research/large-library.md)；1,000 部 × 12 集、全部由 Berth 經手，Docker Desktop 上的量級）：整份清單（`library_index`）1,000 部 318 KB、p95 35 ms；不帶 `parentId` 的 `hasTmdbId` 反查 303 KB、p95 39 ms；**帶整份 `MediaSources` 的集清單 12,000 列 25.9 MB、p95 5.0 s**（不帶是 8.3 MB、0.55 s），約 8 萬集會撞上 Berth 30 s 的 Jellyfin 逾時，分段取總時間不減；**Series 的觀看紀錄很貴**：整份清單打開 `enableUserData` 從 31 ms 變 1.95 s，`ids=` 500 部回 **414 URI Too Long**。plan §11.3 決定 2 的門檻：`GET /inventory/{id}` p95 修正前 3.4 s（Berth 的分組是二次方，不是 Jellyfin）、修正後 0.66–0.68 s；對帳一輪 27–31 s（Jellyfin 那一方 25–29 s）。不做快取、不做分段取。【實測 12.1.0】

### 20.10 Sonarr 怎麼替一集組查詢（2026-09-19 查證）

缺集一鍵搜（M1.5 票 10）要決定「缺一集時拿什麼字去問」，採用的是 Sonarr 的慣例：

- Sonarr 的 Newznab / Torznab 請求把季集放在**結構化參數**上（`&season=<n>&ep=<n>`），標題只放 `q=`。
- **只有動漫的絕對編號是接在關鍵字後面的**：`&q={NewsnabifyTitle(queryTitle)}+{searchCriteria.AbsoluteEpisodeNumber:00}`
  ——絕對編號補零到兩位，與標題之間一個空白。
  【來源：`Sonarr/src/NzbDrone.Core/Indexers/Newznab/NewznabRequestGenerator.cs`，develop 分支，2026-09-19 讀】
- Berth 的搜尋 adapter（Prowlarr 的 REST；M4 票 37 前另有 Torznab 的 `t=search`）只送 `q=`，plan §8.4「分類碼不送」同一個理由：
  各站對結構化參數的支援與映射不一致，而 Berth 打的是公開站），所以季集一律進關鍵字：整季 `S03`、
  單集 `S03E05`、有絕對編號的 `26`。

### 20.9 Jellyfin 12（2026-09-15 查證）

全文、原始碼行號與實測紀錄見 [`docs/research/jellyfin-12.md`](research/jellyfin-12.md)。實測對象是一次性的 linuxserver `12.0ubu2604-ls48`（12.0.0）與 `12.1ubu2604-ls49`（12.1.0），跑完即刪；10.x 的對照引 §20.6 與 `m0-experiments.md`。

下面「從 10.11 升級的阻力」逐條原文在 [`jellyfin-12.md`](research/jellyfin-12.md#從-brief-搬來209)（研究 §4）；其餘各條維持原文。

- **版號**：12.0 就是原本的 10.12，只拿掉永遠不變的 `10`（2026-09-08 發佈；12.1 在 2026-09-15 發佈）。【文件】
- **升級注意的出處**：官方發佈文 [Jellyfin 12.0](https://jellyfin.org/posts/jellyfin-release-12.0/) 的 TL;DR 段（`#tl-dr`：先停機完整備份、移除第三方插件、升級後完整掃描、不能降級）；精靈「既有」選項旁的版本下限連到它（M4 票 17）。【文件】
- **升級是單向的**：10.10.7 或任何 10.11.x 可直接升；資料庫改動讓降級只能靠備份還原。第三方插件要對 .NET 10 重建，10.11 的插件在 12 載入不了。升級後要完整掃描一次，自動分組的版本才會回來。item id 的算法（`MD5(型別全名 + 路徑)`）在 10.11.11 與 12.1 逐字相同，所以一般 Movie / Episode 主條目升級後 id 不變；型別被修正的條目（含自動分組的次要版本）會換 id，缺檔與孤立的條目會被刪。沒有做升級前後逐筆比對的實測。【文件 + 原始碼】
- **從 10.11 升級的阻力**（2026-09-15 補查，`jellyfin-12.md` §4）：**遷移會失敗**（12.0 發佈一週內仍有 12 條遷移、啟動、媒體庫變空的 open issue，其中 #17862 是 12.1 啟動不了；內建的遷移前備份只保護資料庫）；**舊客戶端與整合要升級才能用**（舊式驗證關閉後 Kodi 要 v2.0.0 以上、Seerr v3.0.0、Sonarr / Radarr 要最近的版本；Ombi 與 Jellyfin Vue 的播放仍壞；暫時打開舊式驗證要手改 `system.xml` 的 `EnableLegacyAuthorization`，官方預告下一個大版本移除）；**升級前後**要先移除第三方插件、只差大小寫的兩個使用者名稱會讓遷移失敗、全域字幕設定改到各媒體庫；**一鍵管道沒到齊**（binhex、QNAP 停在 10.11.11；SynoCommunity、TrueNAS 是 12.0；Debian 11 / Ubuntu 20.04 的 apt 已沒有 12；Docker `latest`、官方 apt、Windows / macOS installer 已是 12.1）；帳號、API key、觀看紀錄保留，12 沒有新增 CPU 架構門檻；Kotlin SDK 1.9.0 已把最低伺服器版本拉到 12，新版 Android app 可能反過來要求伺服器是 12【推論】。【文件 + 原始碼 + 官方 issue】
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
- **伺服器名稱**（2026-10-07 查證，M4 票 52）：`POST /Startup/Configuration` 的 body 是 `StartupConfigurationDto`，`ServerName` 與另外三格同一層、都可為 null。它**整格覆寫**：`ServerName = dto.ServerName ?? string.Empty`，沒送就是空字串。名稱是空字串時 `/System/Info/Public` 的 `ServerName` 報 `Environment.MachineName`，在容器裡就是容器 ID——所以沒設過的那一台重建容器就換名字（§20.15 的實測）。12.1 與 12.2 這兩段逐字相同。來源：[OpenAPI](https://api.jellyfin.org/openapi/jellyfin-openapi-stable.json)（12.2.0；`StartupConfigurationDto` 四格都是 nullable string，端點標 deprecated）、[`StartupController.cs`](https://github.com/jellyfin/jellyfin/blob/v12.1/Jellyfin.Api/Controllers/StartupController.cs)（`UpdateInitialConfiguration`）、[`StartupConfigurationDto.cs`](https://github.com/jellyfin/jellyfin/blob/v12.1/Jellyfin.Api/Models/StartupDtos/StartupConfigurationDto.cs)、[`ApplicationHost.cs`](https://github.com/jellyfin/jellyfin/blob/v12.1/Emby.Server.Implementations/ApplicationHost.cs)（`FriendlyName`）。【文件 + 原始碼】
- **舊式驗證預設關閉**，連既有安裝也由遷移關掉：`X-Emby-Token`、`X-Emby-Authorization`、`?api_key=` 回 401。本系統用的 `Authorization: MediaBrowser …, Token="…"` 不受影響。【實測 + 原始碼】
- `GET /Items` 帶 `includeItemTypes` 而沒指定 `recursive` 時預設遞迴（2026-09-17 在 12.1.0 實測，§20.8），本系統一律明確帶 `recursive=true`。`POST /Library/Media/Updated` 背後的 `FileRefresher` 一行沒改，所以「空的媒體庫收到路徑通知無效」（§20.1）仍成立。【原始碼 + 前半句實測 12.1.0】
- **linuxserver image**：
  - tag 變成 `12.0ubu2604-ls48`、`12.1ubu2604-ls49` 這種形式。
  - `latest` 已是 12.1。
  - 舊 tag 會保留，另有跟著同一版號重建的 `version-12.1ubu2604`。所以 `m0-experiments.md` 當時寫的「只保留最新 tag，釘不了版本」不成立。
  - Dockerfile、`/config`、8096、`PUID` / `PGID` 都不變。
  - 【實測 + 原始碼】

### 20.11 發佈時間：索引站與 RSS（2026-09-24 查證）

播出日比對（M3 票 14）與之後可能的「發佈離播出多近」都要一個發佈時間。試跑環境（Prowlarr 預設公開站）實測：

- **Prowlarr 搜尋結果每一筆都有 `publishDate`**（ISO 8601、UTC），缺值 0（搜「Kamiina Botan」534 筆，五個站的筆數見研究檔）。Berth 的 adapter 解析成 `published_at`（`adapters/indexer/prowlarr.py`；M4 票 37 前另有 `torznab.py`，Torznab 的 `pubDate` 是 RFC 822）。**M3 票 14 起接上**：搜尋結果帶 `published_at`、送單存進 `jobs.published_at`，規劃時做播出日比對（plan §4.4）。【實測；原文在 [`publish-time-indexers-and-rss.md`](research/publish-time-indexers-and-rss.md)】
- **ACG.RIP 的 RSS** 是標準的 `<item><pubDate>`，RFC 822 帶時區（`Thu, 24 Sep 2026 06:01:00 -0700`）。【實測 `https://acg.rip/.xml`】
- **Mikan 的 RSS 沒有標準的 `<item><pubDate>`**：日期在 `https://mikanani.me/0.1/` 命名空間的 `<torrent><pubDate>`，ISO 8601 **不帶時區**（`2026-09-24T21:01:00.760219`）。同一個發佈在 ACG.RIP 是 13:01 UTC，所以 Mikan 的值是 **UTC+8**；當成 UTC 讀會差 8 小時。【實測 `https://mikanani.me/RSS/Classic`，與 ACG.RIP 同一筆對照】
- Nyaa 的 RSS 從試跑機器連不上（連線失敗），沒有量到。**2026-09-25 補量**（§20.12）：`<pubDate>` 是 RFC 822 的 `-0000`，即 UTC。
- **發佈時間是「這一筆條目」貼出的時間，不是這一集的首發**：重新上傳、合集、聚合站晚收錄都會讓它偏晚。它只保證「那一集在它之前已經播出」，所以適合當下限（規則一：早於播出日就一定算錯），不適合量「多新」（SubsPlease《上伊那牡丹》01–12 合集在 Anime Tosho 是 2026-08-15，TMDB 第一季末集 2026-06-27）。【實測】

### 20.12 RSS 來源的欄位（2026-09-25 查證，M3 票 07）

完整的欄位表、範例原文與逐條來源在 [`docs/research/rss-sources.md`](research/rss-sources.md)；
fixture 在 `tests/fixtures/http/{mikan,nyaa,acgrip}/`（來源網址與去掉 token 的方式見同目錄 README）。以下只留結論。

**2026-09-24 試跑時的五條實測**（2026-09-25 的 fixture 都重現了，[§10](research/rss-sources.md)）：

- **Mikan 聚合 feed（`/RSS/MyBangumi?token=`）只有最近的集數**：12 筆、跨 6.6 天，同一部作品 × 字幕組只剩最近兩集。
- **單集頁反查得到番組 id 與字幕組 id**：`/Home/Episode/<hash>` 頁上的 `a.mikan-rss` 就是 `/RSS/Bangumi?bangumiId=…&subgroupid=…`；feed 本身不帶，所以聚合 feed 的每一筆第一次出現都要多抓一次單集頁（[§2.7](research/rss-sources.md)）。
- **單一 feed（`/RSS/Bangumi?bangumiId=&subgroupid=`）有整季**：4009 × 370 的 01–12 都在。
- **三站都沒有標示合集的欄位**，只能看標題；acg.rip 搜尋 feed 30 筆裡 8 筆是合集，Nyaa 75 筆裡 14 筆（[§6](research/rss-sources.md)）。
- **Nyaa 從開發機連不上**（TLS 握手失敗；Mikan、acg.rip 同時 200），瀏覽器連得上；部署環境連不連得上取決於使用者的網路（[§3.5](research/rss-sources.md)）。

**三站的欄位**（逐欄對照在研究檔 §9）：

- **guid**：Mikan 的 `<guid isPermaLink="false">` **就是標題**，改標題會跟著變，不能拿來去重；Nyaa 是 `https://nyaa.si/view/<id>`，acg.rip 是 `https://acg.rip/t/<id>`。
- **info hash**：Mikan 的 `link`（`/Home/Episode/<40 hex>`）與 enclosure 檔名末段就是（124/124 筆一致，§2.3）；Nyaa 有 `nyaa:infoHash`；acg.rip **沒有**，只能下載 `.torrent` 算。
- **torrent / magnet**：Mikan、acg.rip 是 `<enclosure type="application/x-bittorrent">`、都沒有 magnet；Nyaa 沒有 enclosure，`<link>` 是 `.torrent`（`&m` 時換成 magnet）。
- **大小**：Mikan 的 `contentLength` 與 enclosure `length` **不是位元組**（多出約 5%），描述後綴 `[518.65 MB]` 比較準；Nyaa 是人類可讀字串（`240.5 MiB`）；acg.rip 的 `torrent:contentLength` 是位元組。三站都只當顯示用的近似值（§2.4）。
- **發佈時間**：Mikan 的 `https://mikanani.me/0.1/` 命名空間 `<torrent><pubDate>` 是 ISO 8601 **不帶時區、實際是 UTC+8**（同一筆在 acg.rip 對照差 +7:59:59），小數秒 0、3、6 位都有；Nyaa 是 RFC 822 `-0000`（UTC）；acg.rip 是 RFC 822 `-0700`（§5）。
- **做種數**：只有 Nyaa 有（`nyaa:seeders` / `leechers` / `downloads`）。

**feedparser 6.0.14**（2026-07-30，PyPI 最新）三站都讀得動、不丟欄位，但 Mikan 有兩處會安靜地讀錯：`published_parsed` 把不帶時區的 `<torrent><pubDate>` 當 UTC（差 8 小時，要讀 `published` 字串自己補 UTC+8）；`<torrent>` 的命名空間被抹掉（`pubDate` → `published`、`link` 變成第二個 `links`），哪天 Mikan 加上標準的 `<item><pubDate>` 會撞名（[§7](research/rss-sources.md)）。【實測 fixture；context7 `/kurtmckee/feedparser`】

**Mikan 的番組搜尋**（2026-09-26 查證，M3 票 19）：`/Home/Search?searchstr=<詞>` 回整頁 HTML（1–4 MB、約 1.5 秒），結果在 `ul.an-ul` 連到 `/Home/Bangumi/<id>` 的 `<a>`。**英文、羅馬字、日文、繁中都搜得到**：`Frieren`、`Sousou no Frieren`、`葬送のフリーレン`、`葬送的芙莉蓮` 四種寫法都回同樣兩個番組（3141、3821）。番組頁左欄 `a.subgroup-name.subgroup-<字幕組 id>` 是字幕組名、緊接的 `span.date` 是最近一次發佈（M/D/YYYY）。【[原文](research/rss-sources.md#從-brief-搬來2012)；fixture `home-search.frieren.html`、`home-bangumi.4009.html`】

**Mikan 的番組頁**（`/Home/Bangumi/<id>`）有中文標題、「放送开始」（`M/D/YYYY`）與 bgm.tv 連結，選擇器在研究檔 §2.7。字幕組 id（`subgroupid=370`）與單集頁上的發佈組 id 不是同一套編號。

**Mikan 的番組是 cour，TMDB 的季可能是好幾輪播出併成的**（2026-09-26 查證，M4 票 14）：Re:Zero 第四季的第二個 cour 在 Mikan 是另一個番組（4052，放送开始 8/12/2026），而 TMDB 65942 把四季 85 集全放第 1 季（第四季是第 67–77 集與停播 56 天後的第 78–85 集）；發佈名只寫「第四季」、不寫篇名。所以自動綁定的季號線索要比那一季**播出的期間**，不能只比首播（§15「綁定」）。【[原文與量測](research/rss-sources.md#從-brief-搬來2012)、§2.8】

**跨 feed 以 info hash 去重：做，不多發請求**（plan §8.5）。Mikan 與 Nyaa 在輪詢時就有 hash；acg.rip 不預抓 `.torrent`，送單時 `TorrentFetcher` 本來就要下載並算 hash，`jobs.hash` 是主鍵。**未證實**：同一個發佈在 Mikan 與 acg.rip 是不是同一個 info hash；不同的話由帳本「同 Media / 季 / 集 / Tags」那一層擋。

**排除條件的格式照 Sonarr 的 release profile**（2026-09-25 查證，M3 票 10）：每一條是字詞、不分大小寫；要正則寫成 `/regex/`（預設分大小寫，`/regex/i` 不分）。【[Servarr Wiki：Sonarr Settings › Release Profiles](https://wiki.servarr.com/sonarr/settings)】Berth 照搬（`parser.exclusion`），比對整個標題。

### 20.13 公開站的請求限制：Prowlarr、Sonarr、AutoBangumi 的慣例（2026-09-26 查證，M3 票 20）

研究檔 [`docs/research/request-budget.md`](research/request-budget.md)，逐條附原始碼或文件連結。M3 票 20 照這幾條定了一個站一份的請求預算（已拿掉，[ADR-0014](adr/0014-no-site-request-budget.md)）；**M4 票 107 整個拿掉**（§19 2026-10-19、plan §3.2），最後一條是拿掉的主要理由：

- **Prowlarr 的 Query Limit 是滾動窗**（[§1](research/request-budget.md)）：數「過去 N 小時」的歷史（`Limits Unit` 只有 `Hour` 與預設的 `Day`），**RSS 與查詢算在同一份**，打滿時那一站那一次跳過；Grab Limit 是另一份。預設不限，要使用者自己填。
- **Cardigann 定義的請求間隔**（[§2](research/request-budget.md)）：只有 `nyaasi.yml` 有 `requestDelay: 2`；`mikan.yml`、`dmhy.yml`、`acgrip.yml` 都沒有。
- **輪詢間隔**（[§3、§4](research/request-budget.md)）：Sonarr 的 RSS Sync Interval 10–120 分鐘（預設值查不到，社群慣用 15 分鐘）；AutoBangumi 的 `rss_time` 預設 900 秒，輪 Mikan 聚合 feed。FreshRSS 每個 Feed 各自設間隔、下限 15 分鐘（[Refreshing feeds](https://freshrss.github.io/FreshRSS/en/users/09_refreshing_feeds.html)）；Berth 照它每個 Feed 各自設、只收固定檔位（M4 票 109）。
- **出錯退避是另一回事**：Sonarr 的 `EscalationBackOff` 0 秒 → 1 分 → … → 24 小時逐級加重，與配額分開計時。
- **Berth 的搜尋曾照「那一站那一次跳過」**（M4 票 77）；票 107 之後搜尋問全部的站，各站的配額交給 Prowlarr 自己的 Query Limit（使用者看得到、調得了）。
- **三站都沒有公開的限速或封鎖事故紀錄**（[§5](research/request-budget.md)；Nyaa 只有 2 秒間隔的間接證據）。票 20 的「每站每小時 60 個」因此不是量出來的，是照 Berth 的用量推的；實際擋到人的只有 Berth 自己的計數（票 77），所以票 107 拿掉。

### 20.14 精靈手動選擇的慣例與既有服務的條件（2026-09-29 查證）

§19「精靈改為每個服務手動選擇」那一列的依據，查證紀錄在 `.scratch/m4/wizard-manual-choice-decision.md`。慣例與各項實測的完整原文在 [`docs/research/wizard-existing-services.md`](research/wizard-existing-services.md)；三次實跑／查證另有自己的研究檔，下面只留結論。

- **Seerr 連媒體伺服器與加 Sonarr / Radarr 全程手動**：填位址與金鑰 → Test → Save，沒有自動偵測。【[Seerr：Media Server](https://docs.seerr.dev/using-seerr/settings/mediaserver)、[Seerr：Services](https://docs.seerr.dev/using-seerr/settings/services)】
- **Sonarr / Radarr 的 Download Client 也是手動**：Host、Port、Username、Password、Category，按 Test。【[Servarr Wiki：Sonarr System](https://wiki.servarr.com/sonarr/system)】
- **硬鏈接的前提是單一 `/data` 掛載**；分開掛或下載器在別台主機就要 Remote Path Mapping，而且硬鏈接失效。【[TRaSH Guides：Docker 目錄結構](https://trash-guides.info/File-and-Folder-Structure/How-to-set-up/Docker)、[TRaSH Guides：Sonarr Remote Path Mapping](https://trash-guides.info/Sonarr/Tips/Sonarr-remote-path-mapping)】Berth 不做 Remote Path Mapping（§18），所以既有服務必須與 Berth 同主機、同容器路徑（§16.4）。
- **qBittorrent 5.2 起有 API key**（`Authorization: Bearer <key>`）；Berth 這一輪只做 WebUI 帳密（版本下限 4.4 不變）。【[qbittorrent-api：Behavior & Configuration](https://qbittorrent-api.readthedocs.io/en/latest/behavior%26configuration.html)】
- **Prowlarr 的 API 只收 API key**（Settings → General → Security），帳密只給瀏覽器；既有 Prowlarr 要的是位址 + API key。【[Servarr Wiki：Prowlarr Settings](https://wiki.servarr.com/prowlarr/settings)】
- **容器裡的 `localhost` 是容器自己**：Docker Desktop 內建 `host.docker.internal`；Linux 要在 compose 加 `extra_hosts: ["host.docker.internal:host-gateway"]`，宿主上的服務要監聽 `0.0.0.0`（只聽 `127.0.0.1` 的連不到）。【[Nick Janetakis](https://nickjanetakis.com/blog/connect-to-a-service-running-on-your-docker-host-from-a-container)】
- **套件內那一台「已經設過介面登入」怎麼認**（M4 票 15，2026-09-29 查證＋實測）：
  - qBittorrent：`app/preferences` 讀得到 `web_ui_username`、**讀不到密碼**（`web_ui_password` 自 Web API 2.3.0 起 write-only）。全新的 linuxserver 那一台帳號是預設的 `admin`。所以**帳號不是 `admin` 就當設過了**；還是 `admin` 的一律當沒設過、要使用者設一組（寧可多問一次）。【[qBittorrent Wiki：WebUI API (4.1)](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1))】
  - Prowlarr：`GET /api/v1/config/host` 全新是 `authenticationMethod: "none"`、`username: ""`（2.6.5 實測）；設過是 `forms`（或 `basic`）加帳號。**方法不是 `none` 就當設過了**。
- **撞名撞 port 時 `docker compose up -d` 的行為**（M4 票 16 實測，2026-09-29；Docker Engine 29.6.2、Compose v5.3.1、Docker Desktop on WSL2；`scripts/experiments/compose_collisions.py`）：社群的說法「撞到的那一台起不來、其他照常起」**只對撞 port 成立**。
  - **撞名**：`up -d` 結束碼 1（`Conflict. The container name … is already in use`），**其他容器（連 `berth` 在內）都只建立、停在 `created`**。容器名改成 `berth-*` 之後同一個情境四個都起來。
  - **撞 port**：結束碼 1（`port is already allocated`），**只有那一台停在 `created`**，其餘照常 `running`。
  - `COMPOSE_PROFILES=`（空字串，三個都接既有）只起 `berth`。
- **從 `COMPOSE_PROFILES` 拿掉服務再 `up -d`，停不掉已經在跑的那一台**（M4 票 36，2026-10-06 實測；同上版本；`scripts/experiments/compose_profile_removal.py`）：Compose 不動不在啟用 profile 裡的服務（`--remove-orphans` 也一樣）；`docker compose stop <服務>` 才停得掉，之後再 `up -d` 留在 `exited`；不帶 `--profile '*'` 的 `down` 不收它們。所以「選了既有」的指示是兩步：改 `COMPOSE_PROFILES` ＋ `docker compose stop <服務>`。
- **`extra_hosts: host.docker.internal:host-gateway` 在 Docker Desktop 上不蓋掉內建的解析**（同一次實測）：容器照樣連得到宿主發佈的 port（回 200）；原生 Linux 的結果見下面 Unraid 那一條。
- **Unraid 實跑**（M4 票 55，2026-10-08；Unraid 7.1.4、Docker 27.5.1、Compose v2.40.3；全文在 [`docs/research/unraid-trial-2026-10-08.md`](research/unraid-trial-2026-10-08.md)）：官方 compose 原樣、只改 `.env`，S1 三個套件內走完並入庫一部；實跑的那一套 2026-10-09 已全部退回（研究檔 §8）。
  - **user share（shfs）上的硬鏈接成立**，前提是全域「Tunable (support Hard Links)」＝ Yes（`fuse_useino="yes"`）；入庫的兩個名字同 inode、links 2。**shfs 回報的 inode 是合成的**（高位是底下那顆碟的 `st_dev`），帳本記的 `(dev, inode)` 是這個合成值。
  - **cache → array 的 mover 保住硬鏈接**（links 2、同一個 inode；Jellyfin 照樣 stream、qBittorrent 照常做種、Berth 對帳 0 件）。**shfs 的 inode 跟著換碟而變**，帳本記的那一個從此過期：只有刪除時的「是不是 Berth 放的」在「來源已被使用者刪掉＋搬過碟」時認不出、把媒體庫那一份留著（研究檔 §6 U4）。mover 不搬正被開著的檔，做種中被讀的那一次留在 cache。【[TRaSH Guides：Unraid](https://trash-guides.info/File-and-Folder-Structure/How-to-set-up/Unraid)】
  - **`PUID=99`、`PGID=100` 照 `.env` 生效**（建出來的全是 `nobody:users`）。
  - **`host-gateway` 在原生 Linux 上成立**：`host.docker.internal` 解成 `172.17.0.1`（docker0），打得到宿主上既有的 qBittorrent 與 Emby。
  - **Compose Manager 的 stack 預設存在隨身碟**（`/boot/config/plugins/compose.manager/projects/<名字>/`）；它的 Indirect Path 讓 stack 指到別的目錄（讀外掛 2025.11.01 原始碼，沒有在 UI 上實按）。所以 README 叫人把部署目錄放 appdata、stack 名填 `berth`。
- **既有服務已經把別的資料夾掛在 `/data` 底下時再多掛一條 `DATA_ROOT:/data`**（M4 票 63，2026-10-14 實測；Docker Desktop 29.6.2 on Windows；`scripts/experiments/nested_data_mount.sh`；**沒有在 Unraid 上跑**，票 55 的 U6）：
  - 兩條並存，`-v` 的先後不影響：`/data` 是 `DATA_ROOT`，`/data/tvshows` 是原本那個資料夾，裡面的東西照舊看得到。
  - Docker 在 `DATA_ROOT` 裡建出同名的空資料夾當掛載點，跑完留著；`DATA_ROOT` 裡原本就有同名資料夾時被子掛載蓋住（宿主上不動）。Berth 只用 `/data/torrent` 與 `/data/library`，所以只有子掛載叫這兩個名字時才會蓋住 Berth 的目錄。
- **原生 Linux、rootless Docker 實跑**（M4 票 42，2026-10-09；Ubuntu 26.04 LTS、Docker 29.7.1 rootless、Compose v5.3.1；VM；全文在 [`docs/research/linux-trial-2026-10-09.md`](research/linux-trial-2026-10-09.md)）：v0.2.0 的 zip 照英文 README 部署，S1 精靈頁 1–6 走完、送單成功；S2 頁 3 兩條各 6/6。**沒有入庫**（下載 40 分鐘只到 19.8%，原因沒查清）；入庫的端到端由 Unraid（票 55）與 Docker Desktop（票 58）實證。
  - **rootless 的 `PUID` / `PGID` 要填 `0` / `0`**：填 `id -u` 時整套照常，但 `DATA_ROOT` 與 `CONFIG_ROOT/*` 在宿主上全是 subuid（100999），宿主帳號寫不進、刪不掉。linuxserver 官方不支援 rootless（[論壇回覆](https://discourse.linuxserver.io/t/setting-puid-and-pgid-to-root/3726)），`0` / `0` 在 jellyfin 12.1、qbittorrent 5.2.4、prowlarr 2.6.5 上實測可用。
  - **PUID / PGID 與 `DATA_ROOT` 擁有者不一致時**：頁 3 三條 Route 都停在第一項 `category` 的 `berth_cannot_write`（`Permission denied: '/data/torrent'`），文案點名 `.env` 的 PUID / PGID；票 72 起多說一句 rootless 不要 chown、改填 `PUID=0`、`PGID=0`。
  - **rootless 上 `host.docker.internal` 連不到宿主**：`host-gateway` 解成 `172.17.0.1`，但那是 RootlessKit 網路命名空間裡的 docker0；宿主的區網 IP 都通（只聽 `127.0.0.1` 的除外）。rootless 上既有服務填區網 IP（M4 票 72）。
  - **qBittorrent 的免密白名單在 rootless 上仍安全**：白名單只有 Berth 的 `172.28.0.2/32`；從宿主與區網不登入打 API 都是 403。【[Docker：Rootless mode › Troubleshooting](https://docs.docker.com/engine/security/rootless/troubleshoot/)】
  - Prowlarr 拿不到 `indexers.prowlarr.com` 的站定義時只剩磁碟上的 5 個，推薦清單上的站一個都不在，頁 4 的主鍵跟著消失（M4 票 73 起說出原因與下一步）。**網路通了之後不必重啟 Prowlarr**（2026-10-14 讀 Prowlarr develop 原始碼，未實跑）：每次讀 `indexer/schema` 都先向 `https://indexers.prowlarr.com/master/12` 拿清單、失敗才讀磁碟，所以 Berth 的「重新讀取」就拿得到。Prowlarr 的介面是 BrowserRouter、不走 `#/`。**2026-10-14 對 linuxserver 2.6.5 實開**（M4 票 102）：`/#/settings/general` 與 `/#/indexers` 都落在首頁，`/settings/general` 是「General Settings - Prowlarr」，`/indexers` 是找不到頁；索引站清單就是首頁 `/`。前端連到 Prowlarr 的那幾頁收在 `web/src/setup/serviceWeb.ts` 的 `PROWLARR_PAGE`。【[原文](research/linux-trial-2026-10-09.md#從-brief-搬來2014)；[AppRoutes.tsx](https://github.com/Prowlarr/Prowlarr/blob/develop/frontend/src/App/AppRoutes.tsx)】
- **Prowlarr 的版本下限是 1.3.2**（M4 票 17，2026-09-29 查證；全表與來源在 [`docs/research/prowlarr-version-floor.md`](research/prowlarr-version-floor.md)，讀各 tag 原始碼，沒有對 1.3.x 實跑）：
  - 卡住下限的只有匿名的 `GET /ping`（[`5abb5ad`](https://github.com/Prowlarr/Prowlarr/commit/5abb5ada4991142e871dcfa94c32c8e4cb0ea247)），第一個 stable 是 **1.3.2.3006**（2023-04-07）；其餘端點與欄位從第一個 tag 0.1.0.361（2021-06）就有。`passwordConfirmation` 要到 1.10.5.4116 才有，但不推高下限（舊版 JSON 設定不拒收多的欄位，未實跑）。
  - 版本從 **`GET /api/v1/system/status` 的 `version`** 讀，四段（`2.6.5.5623`）；它**要 API key**（不帶是 401），所以順便驗了 key。
  - **比下限舊的那一台也讀得到版本**（M4 票 20，2026-09-30 對 1.0.1.2220 實測）：`GET /ping` 回 **200 `text/html`**（所以先問它只會得到「不是 JSON」），`system/status` 帶 `X-Api-Key` 回 200、不帶或錯的 key 是 **401**。Berth 的連線測試因此從 `system/status` 問起、不問 `/ping`。
  - **介面登入在現行版本是必填**（M4 票 20，讀 v2.6.5.5623 原始碼）：第一次打開介面就是一個關不掉、要人設登入的視窗（`AuthenticationRequiredModal`）。精靈因此把套件內那一台的介面登入寫成必填。【[原文](research/prowlarr-version-floor.md#從-brief-搬來2014)】
  - 目前最新 stable 是 2.6.5.5623（2026-09-16）。2.6.3 起多了 Allowed Hosts：使用者自己設了清單時，Berth 用別的主機名連可能被擋，回什麼沒查。
- **位址的協定寫錯時三個服務的樣子**（M4 票 25，2026-10-01 實測；berth image 的 Python 3.13 + OpenSSL 3.5.7、httpx 0.28.1）：
  - **Jellyfin 12.1、Prowlarr 2.6.5** 對 TLS 的 ClientHello 回 HTTP 400：`ssl.SSLError` 理由 `WRONG_VERSION_NUMBER`（httpx 包成 `ConnectError`）。**qBittorrent 5.2.3** 不回、等 HTTP 請求：握手一直等到連線逾時（`ConnectTimeout`，鏈上是 `ssl.SSLWantReadError`）。
  - 反方向（`http://` 打到講 https 的 port）只做了本機的 Python `ssl` 伺服器：它重設連線（`ReadError` / `ConnectionResetError`），與別的斷線分不開，Berth 不認它。
  - **位址沒寫協定**（`nas:8080`、`localhost:8096`…）：httpx 連都不連就丟 `UnsupportedProtocol`（`nas:8080` 被讀成協定 `nas`）。
- **停掉的 compose 容器，主機名解不到**（同一天實測）：Docker 的內建 DNS 只解析在跑的容器，連線測試是 `socket.gaierror`。所以套件內「主機名解不到」的補法要同時說容器停了與不在 compose 裡。
- **解不到要多久**（M4 票 30，2026-10-03 實測，Docker Desktop 29.6.2，從 `berth` 容器裡 `socket.getaddrinfo`）：三個名字都是 `gaierror -5`（`EAI_NODATA`），各約 1.27 秒，三個並行問的 `GET /setup/compose` 約 2.6 秒；都起來之後 8 毫秒內回。宿主上的行為不同、不能拿來推（Windows 開發機要 7 秒，代理工具的 fake-IP DNS 連 `.invalid` 都答一個 198.18.x）。`adapters.dns` 因此以 10 秒為上限、逾時當作解得到（說不出結論就不說「沒在跑」）。

### 20.15 「同一台 Jellyfin」怎麼認：ServerId（2026-09-30 查證＋實測，M4 票 18）

全文與來源在 [`docs/research/deploy-and-jellyfin-identity.md`](research/deploy-and-jellyfin-identity.md)。

- **`GET /System/Info/Public` 的 `Id` 就是伺服器的 `SystemId`**，匿名讀得到；它是第一次啟動時寫進 `<DataPath>/device.txt` 的 GUID（[DeviceId.cs @ v12.1](https://github.com/jellyfin/jellyfin/blob/v12.1/Emby.Server.Implementations/Devices/DeviceId.cs)、[ApplicationHost.cs @ v12.1](https://github.com/jellyfin/jellyfin/blob/v12.1/Emby.Server.Implementations/ApplicationHost.cs)）。
- **實測**（linuxserver 12.1.0 與 10.10.7；`scripts/experiments/jellyfin_server_id.py`）：同一台換位址連（`localhost`、`127.0.0.1`、`host.docker.internal`）、`docker restart`、`--force-recreate`（`/config` 還在），`Id` 都不變；三台不同的 Jellyfin 各自不同。
- **`ServerName` 不能拿來認**：沒設過時是容器的 hostname，重建容器就變。
- 所以 Berth 以 `Id` 判「同一台」：擁有者成立時記下，之後換位址只接受 `Id` 相同的（[ADR-0012](adr/0012-owner-is-jellyfin-admin.md)、plan §9.3）。擁有者成立**之前**也用它：頁 1 的表單帶回測過的位址與 `Id`，與存下的不同就不送帳密（M4 票 28；未初始化的那一台也有 `Id`）。清掉 `/config`（或複製別人的 `/config`）的那一台會換 `Id`（或撞 `Id`）——前者等於一台新的伺服器，擁有者帳號也不在了；後者不防。

### 20.16 搜尋結果怎麼用年份與類型篩：Radarr 與 Sonarr（2026-10-07 查證，M4 票 49）

來源：[Radarr develop](https://github.com/Radarr/Radarr/tree/develop/src/NzbDrone.Core)、[Sonarr develop](https://github.com/Sonarr/Sonarr/tree/develop/src/NzbDrone.Core)（`Movies/QueryExtensions.cs`、`Parser/ParsingService.cs`）；原文在 [`docs/research/search-results.md`](research/search-results.md)。

- **Radarr 年份要完全相同，但認 `Year` 與 `SecondaryYear` 兩個**；發佈名沒有年份照收（`Year < 1800` 放行，只比標題）。
- **Radarr 沒有「這是劇集的一集」那一道**：`Show.S01E02` 被拒是因為標題對不上。Berth 的粗篩只看 `mentions`，所以電影要另外擋季集記號。
- **Sonarr 不以年份拒絕**（只在純標題找不到時用年份分同名劇），也沒有「這是電影」那一道。
- **Berth 的做法**（`parser.title.fits`）：年份容許差一年，代替沒有的「第二年份」；劇集年份範圍是首播年到最後一季首播年（各放寬一年）；片名自帶的數字（`Blade Runner 2049`）不算年份。劇集**不**擋沒有季集記號的（`Title - 05`、`[01-12]` 是動漫常態，`Movie` 又可能是 S00，§6.3 `special_kind`）。篩掉的收著不丟，畫面說數量、可展開。

### 20.17 部署檔的 release 附件與「最新版」連結（2026-10-08 查證，M4 票 56）

全文與來源在 [`docs/research/deploy-and-jellyfin-identity.md`](research/deploy-and-jellyfin-identity.md)。

> **2026-10-09 被取代、2026-10-13 部分恢復**：M4 票 71 把部署改成只用 compose 檔加 `.env`、不附檔案（zip 拿掉，見 §20.18 與 §19 E4）；M4 票 97 恢復附件，但只附那兩個純文字檔 `docker-compose.yml`、`example.env`，不附 zip（§19 2026-10-13 那一列）。下面講 `latest/download` 那一條裡的 zip 已不存在，其餘事實照用。

- **開頭是 `.` 的附件名會被 GitHub 改掉**（2026-10-13 查證，M4 票 97）：REST API〈Upload a release asset〉——「GitHub renames asset filenames that have special characters, non-alphanumeric characters, and leading or trailing periods」，改成什麼沒有寫（[docs.github.com](https://docs.github.com/en/rest/releases/assets#upload-a-release-asset)）；同名附件再傳是 422，要先刪（`gh release upload --clobber`）。所以 `deploy/.env.example` 照 Immich 以 `example.env` 上傳，release workflow 先把兩個檔 `cp` 成要的名字再傳。
- **`https://github.com/<owner>/<repo>/releases/latest/download/<附件名>` 直接下載最新版本的同名附件**（[Linking to releases](https://docs.github.com/en/repositories/releasing-projects-on-github/linking-to-releases)）；每一版都要有同名附件，README 才能寫死連結。Immich 的安裝步驟就是這樣拿 compose 與 `example.env`（[docs.immich.app](https://docs.immich.app/install/docker-compose)）。
- **「最新」只算正式版本**：非 prerelease、非 draft，依 `created_at` 排（[Get the latest release](https://docs.github.com/en/rest/releases/releases#get-the-latest-release)）。所以 `-rc` 的 release 標成 prerelease 就不會動到 `latest/download`，與 GHCR 的 `:latest` 規則一致。
- **`gh release create`**：`--prerelease`、`--verify-tag`；帶附件的 `create` 先建草稿、傳完附件才發佈，失敗時刪掉草稿（`draftWhileUploading`，[create.go](https://github.com/cli/cli/blob/trunk/pkg/cmd/release/create/create.go)），所以 `latest/download/` 不會指到還沒有附件的新版。release 已存在時改用 `upload --clobber`。

### 20.18 preseed 腳本內嵌進 compose：`configs.content` 加 `mode`（2026-10-09 查證＋實測，M4 票 70）

全文、實測表與來源在 [`docs/research/deploy-and-jellyfin-identity.md`](research/deploy-and-jellyfin-identity.md)。部署要只剩 compose 檔加 `.env`（使用者 2026-10-09 拍板，推翻 §19 E4），qBittorrent 的白名單腳本因此內嵌進 compose，不再是旁邊的 `preseed/` 目錄。

- **Docker 文件**：頂層 `configs` 的 `content` 從 Compose 2.23.1 起支援，內容會做變數展開（[configs](https://docs.docker.com/reference/compose-file/configs/)、[v2.23.1](https://github.com/docker/compose/releases/tag/v2.23.1)）；預設權限 0444，服務 `configs` 長語法的 `mode` 可覆寫（[services#configs](https://docs.docker.com/reference/compose-file/services/#configs)）。
- **`mode` 是成敗關鍵**：linuxserver 的 init 只執行 `-x` 的檔（`/etc/s6-overlay/s6-rc.d/init-custom-files/run` 對 `/custom-cont-init.d/*` 做 `[[ -x ]]`），0444 的預設一定不會跑，log 只有 `10-berth.sh: is not an executable file`，qBittorrent 照常起來但沒有白名單，Berth 進不去。漏掉 `mode` 不會報錯。
- **實測**（`scripts/experiments/inline_preseed.py`）：Docker Desktop Windows（Compose v5.3.1）、獨立二進位（v2.40.3）、rootless VM（v5.3.1）三個環境結果相同。`mode: 0555` 時內容與原檔 sha256 相同、首次啟動依序印 `executing`、`added`、`exited 0`，之後 `restart`、`--force-recreate` 都 `already configured`，且鍵各一行、`BERTH_IP` 200 而宿主 403；`COMPOSE_PROFILES=` 空時 `up -d` 回 0 無警告；不需要 `uid` / `gid`。Unraid 隨身碟（vfat）上沒有實測，推論無妨（執行期不讀 compose 目錄）。
- **坑**：`docker compose config` 的輸出會把 `$` 再轉義成 `$$`，拿它驗內容等於沒驗；抽出腳本做測試時要把 `$$` 還原成 `$`。`mode` 寫 `0555` 的前導 0，兩個版本都讀成 555。比 2.40.3 舊的 Compose 沒有量。
- **決定的寫法**：compose 頂層 `configs.qbittorrent-preseed.content` 放 `10-berth.sh` 全文（每個 `$` 寫成 `$$`），服務的 `configs` 用 `source: qbittorrent-preseed`、`target: /custom-cont-init.d/10-berth.sh`、`mode: 0555`（完整 YAML 在研究檔）。
- **閘門**（票 71）：`tests/unit/test_qbittorrent_preseed.py` 守著 `content` 沒有未轉義的 `$`、target 在 `/custom-cont-init.d/`、`mode` 帶執行位元；`tests/unit/test_deploy_mounts.py` 守著 compose 的宿主路徑沒有相對的。重量：`docs/development/experiments.md`。

### 20.19 搜尋的年份、片名裡的 `&` 與成人分類（2026-10-10 查證，M4 票 69）

來源與完整原文：[`docs/research/search-results.md`](research/search-results.md)。外部：[TMDB search-multi](https://developer.themoviedb.org/reference/search-multi)、[search-movie](https://developer.themoviedb.org/reference/search-movie)、[search-tv](https://developer.themoviedb.org/reference/search-tv)；[Sonarr develop](https://github.com/Sonarr/Sonarr/tree/develop/src/NzbDrone.Core) `SearchCriteriaBase.GetCleanSceneTitle`；[Prowlarr develop](https://github.com/Prowlarr/Prowlarr/tree/develop/src/NzbDrone.Core/Indexers)。

- **TMDB `search/multi` 沒有年份參數**：「Nosferatu 1922」整串當片名比，0 筆（2026-10-10 實測兩次，M4 票 69、85）。帶年份的是 `search/movie`（`year`、`primary_release_year`）與 `search/tv`（`year`、`first_air_date_year`）。Jellyseerr 的一般搜尋也不拆年份，直接 `searchMulti`。
- **Berth 的做法：不用帶年份的那兩支**（M4 票 85，使用者拍板，推翻票 69 的年份拆分）。打的字整串原樣問 `search/multi`，結尾數字不拆成年份。理由：使用者搜尋不加年份，同名作品看卡片年份認；拆開問會擠掉片名以數字結尾的作品（「Space 1999」拆成 1999 年後回 24 部別的 Space 片、沒有它，兩種都問合併也只排第 25 筆，2026-10-10 實測）。代價是「Nosferatu 1922」0 筆；搜「Nosferatu」列得出各年份。要做年份篩選時從這裡起。
- **Sonarr / Radarr 送查詢前把 `&` 換成 `and`**（取代，不多問一組；兩邊逐行相同）：`Law & Order` 送出 `Law+and+Order`。比對用的 clean title 把 `and` 等與非字元刪掉，`Law & Order` 與 `Law and Order` 同為 `laworder`（2026-10-10 讀）。
- **兩種站各認一種寫法**（2026-10-10 實測）：The Pirate Bay（經 Prowlarr）`Law & Order` 0 筆、`Law and Order` 100 筆；Mikan RSS `TIGER & BUNNY` 81 筆、`TIGER and BUNNY` 0 筆。字幕組照官方拉丁字片名寫 `&`，scene 寫 `and`。
- **Berth 的做法**（`parser.title.spell_ampersand`、`services/search_queries.py` 的 `_spellings`）：**不照 Sonarr 只送寫開的**；有 `&` 的名字原樣問一次、再問寫成 `and` 的一次，各配開了的季（列在預覽裡，算進上限 `MAX_QUERIES`）。有 CJK 字的名字不換。比對不學 Sonarr 刪每個 `and`（`Pride and Prejudice` 照舊要寫 `and`）。
- **Newznab 成人分類是 6000–6090**（`XXX = 6000`，子分類 `XXX/DVD` 6010 到 `XXX/WEB-DL` 6090）；結果的 `categories` 帶標準碼加 `100000 + 站碼` 的自訂碼，不自動補父分類。The Pirate Bay 把 Porn 各類映射到 `XXX*`（`definitions/v11/thepiratebay.yml`）。2026-10-10 讀；回應形狀沒實呼叫驗證，錄製的 `search.*.json` 沒有成人類。
- **Berth 的做法**（`services/search.py` 的 `ADULT_CATEGORIES`）：分類碼落在 6000–6999 歸成「成人分類」（M4 票 83 起是 Search Verdict 的一類），不丟。分類碼不拿來查（plan §8.4：各站映射自訂），只拿來歸類（歸錯了按一下就看得到，畫面預設只列「符合」，其他類照樣送）；沒映射成人類的站（多數動漫站）擋不到，只剩發佈名。

### 20.20 搜尋結果怎麼說出「為什麼不像這部作品」：Sonarr 的互動搜尋（2026-10-10 查證，M4 票 83）

來源：[Sonarr v4.0.20.3014](https://github.com/Sonarr/Sonarr/tree/v4.0.20.3014)（`ReleaseController.cs`、`InteractiveSearchRow.tsx`、`releaseActions.js`、`ParsingService.cs`、`SeriesSpecification.cs`）、[Radarr develop](https://github.com/Radarr/Radarr/tree/develop/src/NzbDrone.Core)、[Prowlarr releaseActions.js](https://github.com/Prowlarr/Prowlarr/blob/develop/frontend/src/Store/Actions/releaseActions.js)；原文在 [`docs/research/search-results.md`](research/search-results.md)。

- **被拒的發佈照樣列出**：每個 decision 都回傳，被拒的一列紅圖示、Popover 逐條列 `rejections`；後端與畫面**沒有筆數上限**（只有 Newznab 分頁 `PageSize = 100`）。預設篩選是「全部」（`all`、`season-pack`、`not-season-pack`）。
- **片名比對是「季集記號前面那一段」清過之後完全相等**（不是包含）：`searchCriteria.Series.CleanTitle == SeriesTitle.CleanSeriesTitle()`，再退到 tvdbId / imdbId。找到別部是 `Wrong series`，整庫都找不到是 `Unknown Series`；`Law.and.Order.SVU.S28E01` 清成 `laworder svu`，與 `laworder` 不等而被拒（讀程式推得，沒實跑）。Radarr 對應 `Wrong movie` 與 `Unknown Movie. …`，年份不符沒有獨立拒絕字串。
- **Berth 的做法**（`services/search.py` 的 `_judge`、`parser.title.misfit` / `partial_title`，`.scratch/m4/search-filter-shape.md`）：照 Sonarr 每一筆都送、都說得出理由；不同的是**一筆一類、一句話**（粗篩先後：名字對不上 → 成人分類 → 不是電影 → 年份不符 → 只對上部分名字 → 符合），**畫面預設只開「符合」**（The Pirate Bay 對查不到的字回熱門清單），每類各有上限（符合 100、其餘 50，逐站輪流取）。「只對上部分名字」取第一個記號（季集、字幕組集號、年份）前面那一段，但先照 `/`、`|`、括號與文字系統（CJK／非 CJK）切成一個個名字再比；有一個名字相等就算這一部，沒有相等但有一個包住這部作品的名字才算「部分」；讀不出記號時不判。
- **自己打關鍵字的搜尋**（2026-10-14 補查，M4 票 83b）：Prowlarr 手動搜尋頁預設篩選只有 `all`，自訂篩選欄位有 `title`、`indexerId`、`seeders` 等，**沒有拿發佈名比對查詢的判斷**（The Pirate Bay 熱門清單照樣全列）。Berth 推翻票 83 的「自己打的關鍵字一律 `unjudged`」：只分**對得上**（`typed_match`：正規化後發佈名含打的字串，或含這部作品的某個名字，後者補繁簡）與**對不上**（`typed_miss`），預設只開對得上；仍不判是不是這部作品（票 08 的理由）。有 CJK 的字串不設長度下限，不到四個字的拉丁字要整詞相等（`parser.typed_fits`，`.scratch/m4/search-typed-filter-shape.md`）。`unjudged` 拿掉。

### 20.21 季的搜尋記號：`Season N` 與 `SNN` 實跑比較（2026-10-13 實測，M4 票 84）

腳本 `scripts/experiments/season_token_compare.py`，隔離的 Prowlarr（The Pirate Bay、Mikan、dmhy；Nyaa 與 YTS 當天連不上）；逐站數「總筆數 / 發佈名含作品名字的筆數」。完整比較表在 [`docs/research/search-results.md`](research/search-results.md)。

- **美劇 `SNN` 比較準**：`The Bear Season 3` 在 The Pirate Bay 名字對得上的 11 筆裡只有 3 筆寫 `S03`；`The Bear S03` 的 6 筆全是第三季。
- **動畫站的 `SNN` 少一個數量級**：Mikan、dmhy 對 `Season 2` 是寬鬆比對；`SPY x FAMILY Season 2` 在 Mikan 對得上的 162 筆裡 90 筆真寫 `Season 2`（1 筆寫 `S02`），`S02` 只回 2 筆。字幕組寫 `Season 2`、`第2季`，不是 `S02`。
- **Berth 的做法**（`parser.title.season_tokens`）：`SNN` 比較少就兩種都留——**拉丁字名字一季問 `S03` 與 `Season 3` 兩個**，有 CJK 字的名字問 `第3季`；按搜尋與搜缺的集共用這一個函式。一次搜尋上限因此從 5 改成 10（使用者 2026-10-13 拍板）：動畫的英文名、原名配「不指定季」與最新一季是 6 個，再開兩種中文名是 10 個。CJK 那一對兩邊都只有 0–1 筆，樣本太小，只當參考。

### 20.22 Berth 登入 Jellyfin 留下的裝置（2026-10-14 查證，M4 票 66）

- Berth 以 `Authorization: MediaBrowser Client="Berth", Device="Berth", DeviceId="berth-server"` 呼叫 `AuthenticateByName`（`adapters/jellyfin/client.py`）。Jellyfin 的 `SessionManager.GetAuthorizationToken` 先找同一個 `DeviceId` **且同一個使用者**的裝置、逐一登出（刪掉那一列），再建一筆新的、發新的權杖。所以**登入過 Berth 的每一位使用者在 Jellyfin「裝置」頁各一筆 Berth**，同一位再登入是換掉自己那一筆，不會越積越多；別的使用者的那一筆不刪，但同一個 `DeviceId` 的進行中工作階段會被結束。【[SessionManager.cs @ v12.1](https://github.com/jellyfin/jellyfin/blob/v12.1/Emby.Server.Implementations/Session/SessionManager.cs)（`AuthenticateNewSessionInternal`、`GetAuthorizationToken`、`Logout(Device)`）】
- 審計 S3 實跑看到的「`/Devices` 多一筆 Berth」就是這一筆（`docs/research/usability-audit-2026-10-07.md` 附錄 C.1）。

### 20.23 Discord bot 私訊（2026-10-21 查證，M4 拆票；同日 M4 票 121 實測）

全文與來源在 [`docs/research/discord-notifications.md`](research/discord-notifications.md)。拆票時用到的：

- 私訊是 `POST /users/@me/channels`（`recipient_id`）再 `POST /channels/{id}/messages`，純 REST、不需要 intent；bot 與收件人要有共同伺服器（`50278`），`50007` 是「不能傳訊息給這位使用者」。「bot 要先連過一次 gateway 才能發訊息」官方文件沒寫，實測不需要（下面）。
- 互動（按鈕、slash command）只有兩條路且互斥：gateway 的 `INTERACTION_CREATE`，或公開的 Interactions Endpoint URL（要回 PING、驗 Ed25519 簽章、3 秒內回應）。家用伺服器沒有公開網址時只能 gateway——M7 的事。
- 頻道 webhook 只綁頻道、不能私訊，使用者手動建的不能帶互動按鈕。Overseerr、Jellyseerr、Sonarr 都用它（Overseerr 系另有選填的 Discord ID 用來 @mention）。
- 429 的 body 有 `retry_after`（秒、浮點）與 `global`，header 有 `Retry-After`、`X-RateLimit-*`；`content` ≤ 2000 字元、一則最多 10 個 embed、所有 embed 文字合計 ≤ 6000。


**實測**（2026-10-21，M4 票 121，API v10，`scripts/experiments/discord_dm.py`；回應錄在 `tests/fixtures/http/discord/`；逐條原文在 [研究檔〈從 brief 搬來（§20.23）〉](research/discord-notifications.md#從-brief-搬來2023)）。兩個新建的 bot、一個只有使用者與 bot 的測試伺服器：

- **從沒連過 gateway 的 bot 私訊得到**：開 DM channel `200`、純文字與帶 embed 的訊息都 `200`，不需要 intent。開 DM channel 什麼情況都回 `200`，擋下來的是送訊息那一步，所以「按測試」要真的送一則。
- **沒有共同伺服器、使用者在共同伺服器關了私訊、bot 被踢出，回的是同一個錯**：`403` / `50278`；`50007` 一次都沒出現。Berth 分不出是哪一種，提示要把兩個補法一起說：把 bot 加進同一個伺服器、在那個伺服器打開「私人訊息」。伺服器的「私人訊息」跟著使用者的全域設定，預設可能是關的。
- **超過長度是 `400` / `50035`**：`content` 2001 字元是 `BASE_TYPE_MAX_LENGTH`；embed 合計 6001 字元是 `MAX_EMBED_SIZE_EXCEEDED`。長度檢查在共同伺服器檢查之前。**token 錯是 `401`**，沒有 `X-RateLimit-*` header。
- **送訊息的 bucket 一次 5 則**（`X-RateLimit-Limit: 5`），**失敗的請求（`400`、`403`）也扣額度**；額度一則一則補回（約 1 秒一則），連續送第 7 則遇到 `429`。`429` 的 body 是 `{"message", "retry_after", "global"}`（**沒有 `code`**），`retry_after` 是下一個空位（浮點），header `Retry-After` 是整個 bucket 重置、無條件進位成整數。開 DM channel 是另一個 bucket（`X-RateLimit-Limit: 100`）。
- **只私訊的邀請連結**是 `https://discord.com/oauth2/authorize?client_id=<application id>&scope=bot&permissions=0`；application id 由 `GET /applications/@me` 以 bot token 取得，Berth 只讀回應的 `id` 與 `name`（M4 票 123；[Application Resource](https://discord.com/developers/docs/resources/application)，2026-10-21 經 context7 查）。這一份回應沒有錄（含擁有者帳號），契約測試只用這兩格。
- **embed 的 `url` 不收沒有點的主機名**（M4 票 124，`discord_dm.py embed-url`）：`http://berth:8000/…` 是 `400` / `50035`（`URL_TYPE_INVALID_URL`），整則送不出；網域、`*.ts.net`、`nas.local`、IP、`localhost`、`[::1]` 都 `200`。同一個網址寫成 description 裡的 Markdown 連結九種都 `200`，所以 Berth 的連結放在 description（`adapters/notify/discord._description`）。手機上 Markdown 連結是否每一種都可點沒有逐一看。

### 20.24 pydantic-ai 的確認卡與 Vercel AI SDK 串流（2026-10-27 實測，M5 prototype）

全文、selftest 輸出與用到的版本在 [`docs/research/m5-prototype-2026-10-27.md`](research/m5-prototype-2026-10-27.md)，腳本是 `scripts/experiments/m5_agent_chat.py`。版本：pydantic-ai-slim 2.61.0、ai 7.0.138、@ai-sdk/react 4.0.141。後續各票讀的細節（2.62.0、ai 7.0.153）在同檔末尾〈從 brief 搬來（§20.24）〉，下面各條的粗體標籤就是那裡的條目名。

- **deferred tool 可以存成一列、重啟之後接著跑**：工具丟 `ApprovalRequired`，run 以 `DeferredToolRequests` 結束（`output_type` 要含它）；歷史用 `ModelMessagesTypeAdapter` 存成 JSON；另一個請求或行程帶 `message_history` 與 `DeferredToolResults` 就能恢復，核准用 `ToolApproved(override_args=...)`，參數以伺服器存的為準（正式版改成核准就由伺服器當場執行，恢復只交結果，M5 票 13）。恢復時 `ctx.tool_call_approved` 為真，所以「丟之前跑防護、算預覽」與「核准後執行」是同一個函式。
- 待確認的呼叫**必須一次全部解決**，否則 `UserError`。所以 **Proposal 的生命週期要獨立於 agent run**：卡片脫離對話之後再按，由伺服器直接執行，下一輪告訴模型結果。
- **`VercelAIAdapter` 預設信任前端**：前端送回的核准與工具參數都照收，偽造一則「已核准」的助理訊息就會用偽造的參數執行（官方文件明說是設計）。`sdk_version` 預設 5，沒有核准串流，要傳 6 或 7（wire 相同）。Berth 的做法：歷史放伺服器，前端只送最後一則；`deferred_tool_results` 從 Proposal 表組好再傳給 `run_stream`，前端的 approval 只當觸發。`dump_messages(..., sdk_version=7)` 把沒有結果的 tool call 轉成 `approval-requested`，重新載入頁面後卡片照樣按得下去。
- **壓縮**：`ProcessHistory` 改過的歷史就是 `all_messages()` 的那份；切點落在使用者訊息上，待確認的 tool call 一定留在尾巴，被切掉的 tool call 留下的孤兒 tool result 要一起拿掉，否則 Anthropic 會拒收。`AnthropicCompaction`（伺服器端，beta）與 `OpenAICompaction`（只適用 Responses API）沒有採用。2026-10-27 讀 pydantic-ai-slim 2.62.0 原始碼（M5 票 18）：摘要放 `CompactionPart`，各家以使用者語氣送出，不當 system prompt；`RunContext.context_window_used` 沒資料時是 `None`；`RetryPromptPart` 已 deprecated；官方 `pydantic-ai-harness` 0.62.0（Alpha）的 `SummarizingCompaction` 不認一輪從哪裡開始、不拿掉孤兒 result、拿不到摘要的回應記帳，所以 Berth 自己寫（`services/compaction.py`）。
- **斷線之後接上（resumable streams）**（2026-10-28 查，M5 票 25）：Vercel AI SDK 7 的做法是伺服器在沒人看的時候照跑，`useChat` 的 `stop()` 只中止這一個請求（等於斷線），所以**停止要另一個端點**；對話記 `activeStreamId`，重連是 `GET .../{chatId}/stream`，沒有在跑的回 204；重連的串流從第一個片段重播（`ai@7.0.153`）。pydantic-ai 的 `CancellationToken` 保留串流到一半的回應，外部 `Task.cancel()` 則是 `CancelledError`，兩者同時時外部贏；Berth 的停止走後者（plan §6〈agent〉）。Starlette 的 `StreamingResponse` 在 ASGI spec 2.4 之前聽到 `http.disconnect` 就取消串流，所以一輪要跑完得放在請求之外的 task。
- **觀測的缺口**：run 中途被中止（`UsageLimitExceeded`、重複呼叫、模型錯誤）時，`on_complete` 不會被呼叫，這一輪的歷史與 token 用量都拿不到。記帳要掛在每次模型呼叫之後。
- **費用**（M5 票 21b 改寫）：價目用 genai-prices（[pydantic/genai-prices](https://github.com/pydantic/genai-prices)，pydantic-ai-slim 2.62.0 的相依，`>=0.1.13`；2026-10-28 讀 0.1.13 原始碼與實測）。
  - `calc_price(usage, model_ref, provider_id=..., provider_api_url=...)` 先用 `provider_api_url` 認服務商、再找模型，認不得是 `LookupError`；`https://api.deepseek.com/anthropic` + `deepseek-flash` 認成 `deepseek`，改傳 `provider_id=anthropic` 查不到，所以**接口種類不能當服務商**，只在網址認不得時退一步用。「網址認得、那一家沒有這個模型」Berth 當查不到。
  - 價錢帶時間：DeepSeek 尖峰（UTC 01–04、06–10）是離峰的兩倍，`genai_request_timestamp` 決定套哪一段（週末全天離峰它表達不了，那時的價是上限）；Anthropic 長 context 與 OpenAI gpt-5.5 有分級價。回應時間就是收到第一個片段那一刻的本機時鐘（2.62 原始碼，票 21c）；測試控制時段要釘時鐘。
  - **DeepSeek 官方價目**（[api-docs.deepseek.com/quick_start/pricing](https://api-docs.deepseek.com/quick_start/pricing)，2026-10-28）：`deepseek-flash` 尖峰 $0.3 / $1.2（每百萬 input / output），離峰減半 $0.15 / $0.6；尖峰是週一到週五 UTC 01:00–04:00、06:00–10:00，其餘（含週末與中國國定假日）離峰。與 genai-prices 0.1.13 一致，只差它把週末與假日也當尖峰（只會高估）。設定頁與用量頁出現的半價是**離峰價，不是過時的價**；M5 票 09 手寫表的 $0.3 / $1.2 是尖峰價。
  - `usage.input_tokens` 含快取讀寫（Anthropic 同），快取比 input 還多是 `ValueError`；沒有快取寫價的服務（DeepSeek）快取寫照輸入價算。`web_search` 次數在 `usage.details['web_search_requests']`，每次 $0.01。
  - **自動更新是 opt-in**（`UpdatePrices().start()` 才會每小時抓 `data.json`）；Berth 自己用套件內附資料建一份 `DataSnapshot(..., from_auto_update=False)`。0.1.13 已認得 M5 票 09 手寫表的全部模型，Berth 的補位表是空的。
- **provider**：`AnthropicProvider(base_url=...)` 不含 `/v1`；`OpenAIProvider(base_url=...)` 照那家文件。**anthropic SDK 2.x 把 `api_key` 放在 `Authorization: Bearer`**（讀 2.3.0 的 `_client.py`），只認 `x-api-key` 的閘道會回 401，測試連線照實說「key 被拒」。兩家 SDK 沒給 `api_key` / `base_url` 時讀環境變數，Berth 一律明給（M5 票 09）。pydantic-ai-slim 2.62.0 的 provider 吃 `httpx2.AsyncClient`；錯誤分類 `ModelAuthenticationError`、`ModelNotFoundError`、`ModelConnectionError` 都是 `ModelAPIError` 的子類。伺服器端 `web_search` 只有 Anthropic Messages 才有（含 DeepSeek 的相容端點），Chat Completions 要另接 Tavily 這類。
- **真模型實測**（DeepSeek `deepseek-flash`，Anthropic 與 OpenAI 兩種相容接口各跑六個情境；TMDB 與索引站是真的，qBittorrent 是替身）：兩種接口都跑完全部情境，沒有接口相關的錯誤；一個情境 3–16 次模型呼叫，Re:Zero 最重（約 220K input、11K output、2.5 分鐘）；快取命中 46–98%；六個情境合計約 $0.07–0.08（DeepSeek 尖峰價），換成 Claude Sonnet 5.5 價目推估約 $0.5–0.6；單輪最多 9 次模型呼叫，所以對話的往返上限 10 太緊，建議 15–20。品質逐項在研究檔〈結果：真模型〉。
- **實跑抓到、正式版要照做的**：確認後的工具結果要明說已核准、已執行；待確認的呼叫要找「最後一則模型回應裡還沒有結果的」（平行呼叫時別的工具的結果會排在後面）；卡片預覽要先跑命令的驗證（`route_required`、`route_kind_mismatch` 都是按了確認才被擋下）；總覽卡要逐列顯示結果（會部分成功；Re:Zero 全系列的總覽卡 7 列）；失敗後的重試不算重複呼叫；「讀過外部內容」的警示要縮小到「自由文字參數出自外部內容」。
- **串流時的 capability hook**（2026-10-27 M5 票 11 實測，pydantic-ai-slim 2.62.0、`VercelAIAdapter.run_stream`）：`wrap_model_request` 每次呼叫都拿得到完整 `ModelResponse`（含 `usage`），記帳掛在這裡就夠；模型串流到一半出錯時 handler 丟的是 `CancelledError`，真正的例外只到 `on_run_error`；run 出錯時串流送 `error`、`finish-step`、`finish`（`finishReason: error`），`on_complete` 不跑；`SubmitMessage` 是 `extra='allow'`，`useChat` 的 `body` 加的欄位（`language`）在 `model_extra`；`FunctionModel` 要另給 `stream_function` 才能串流。
- **確認卡的恢復**（2026-10-28 M5 票 13 讀原始碼與整合測試；pydantic-ai-slim 2.62.0、ai 7.0.153）：`ToolApproved.override_args` 只換掉傳進工具的參數，**不改歷史裡的 `ToolCallPart`**；經 `VercelAIAdapter` 時新訊息放進 `message_history`，工具結果會排在它後面；`approval.id` 就是 `tool_call_id`。**ai 7 的前端只在當前那一則助理訊息裡找工具呼叫**，對上一則訊息的呼叫送 `tool-output-*` 會丟 `UIMessageStreamError`；恢復時最後一則是助理的所以沒事，使用者沒按卡就送新訊息時會出事，Berth 改成由伺服器替那幾個呼叫補上結果再接新訊息（`tests/integration/test_agent_cards.py::TestMovingOn`）。
- **還沒測**：Claude 與 OpenAI 的官方端點（這次兩組 key 都是 DeepSeek）、`AnthropicCompaction`。DeepSeek 的 Anthropic 相容端點會忽略 `cache_control` 但自己快取，也會執行伺服器端 `web_search`。
- **網路搜尋**（2026-10-27，M5 票 17）：
  - Anthropic `web_search`：**$10 / 1,000 次**，搜尋結果另算輸入 token，出錯的那次不收費。`max_uses` 是**每個請求**的上限，超過時結果是 `max_uses_exceeded` 錯誤（HTTP 仍 200）。`allowed_domains` 與 `blocked_domains` 二選一，**自動含子網域**，組織在 Console 設了允許清單時請求的必須是它的子集否則 400。與自己的工具平行呼叫時 API 先不跑搜尋、回 `tool_use`，下一個請求才搜。（[Web search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)、[Server tools〈Domain filtering〉](https://platform.claude.com/docs/en/agents-and-tools/tool-use/server-tools)）
  - **改工具定義（名字、說明、參數）會讓整段 prompt 快取失效**（順序 tools → system → messages），所以 `max_uses` 每次請求固定，不照剩幾次調。（[Prompt caching〈What invalidates the cache〉](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)）
  - pydantic-ai-slim 2.62.0：`NativeTool` 可以給函式，每次模型呼叫前回 `WebSearchTool` 或 `None`；`usage.details['web_search_requests']` 只在大於 0 時有；`FunctionModel` 串流版的 usage 報不出網搜次數；`OpenAIChatModel` 送出歷史時略過伺服器端工具片段，同一段對話換接口不會壞。
  - Tavily `POST https://api.tavily.com/search`：`Authorization: Bearer <key>`；`basic` / `fast` / `ultra-fast` 1 credit、`advanced` 2 credit；`include_domains` 最多 300 個，**實測含子網域**；成功回 `results[]`（`title`、`url`、`content`、`score`）等，每頁 `content` 約 1,300–1,500 字；錯誤 body 是 `{"detail": {"error": "..."}}`：401 key 錯、400 參數錯、429 限流帶 `Retry-After`、432 / 433 額度；免費每月 1,000 credit。（[Search API](https://docs.tavily.com/api-reference/endpoint/search)、[Rate limits](https://docs.tavily.com/documentation/rate-limits)、[Credits](https://docs.tavily.com/documentation/api-credits)；實測錄在 `tests/fixtures/http/tavily/`，`scripts/experiments/tavily_search.py`）
