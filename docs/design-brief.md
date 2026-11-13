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

名詞表在 repo 根目錄的 `GLOSSARY.md`（單一來源，含每個詞的定義與應避免的同義詞）。實作、UI、文件與 API 一律使用那裡的詞。本文件後續章節出現的 Media、Library Route、Download Job、Import Plan、Ledger Entry、Review Queue、Unmatched、Extras、Issue、Event 等，定義以 `GLOSSARY.md` 為準。

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

- 每個 Route 建立時與健康檢查每一輪（每 5 分鐘；啟動後迴圈第一次醒來若已逾期就跑）執行：在 `complete/<route-slug>` 建暫存檔 → 真的呼叫 `link()` 鏈接到目標路徑 → 比對 inode 與 device → 刪除。失敗即 Route 標記為不健康，拒絕送單。只比 `st_dev` 不夠（同一檔案系統掛兩次、btrfs 子卷、ZFS dataset、mergerfs 都會 `EXDEV`，§20.2），所以一定實際鏈接一次。
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

- **三層漏斗**：規則層（解析器、比對）是主力——免費、確定、有 benchmark 守著；AI 只接規則層的例外；人只處理 AI 交上來的與不可撤銷的。AI 掛掉或碰到防護上限時退回沒有 AI 的行為，系統照樣能用。
- **規則層自己知道沒把握的**（信心 low、Unmatched、目標衝突、RSS Series 待綁定）→ 開一個 AI 任務，而不是直接進審核。
- **規則層有把握卻錯了的**（high / medium 入錯）規則層自己看不出來，靠不花 token 的程式檢查抓（plan §11.4）：
  - **播出日比對**（Feed Item 的發佈時間對換算出的那一集的播出日，抓集數與 offset 算錯——主要的一道）。
  - **片長驗證**（抓預告、SP、合併檔被當成正片這類分類錯誤）。
  - 每日檢查（RSS Series 缺號、同一集意外多份）。
  - **Jellyfin 回驗抓不到集數算錯**：Jellyfin 認集數靠 Berth 取的檔名，錯的集數會原樣抄過去；它只是抓 Jellyfin 那邊意外的保險。
  - 抓到的開 AI 任務：撤銷、rematch、必要時把 offset 寫回 RSS Series 並重算同一 RSS Series 未確認的集數。**不讓 AI 逐筆重看每一次入庫**——那是規則層該做的事，也付不起。
- 輸入（壓縮後）：torrent 名、檔案清單（每個檔案帶大小與 mediainfo 量到的片長；同模式的檔案只送樣本 + 數量，但片長偏離同組的單獨送）、規則層的部分解析與理由、TMDB 季集結構（集數、集名、首播日、片長）、程式先查好的 Bangumi / AniList / Mikan 資料、命名規則、使用者偏好。不送檔案內容與帳密。模型答「資料不夠」時才再呼叫一次並給限網域的唯讀網搜（plan §11.7）。
- 輸出：JSON schema 固定的 Plan（逐檔分類、季、集、tags、confidence、理由）。程式做**結構與約束驗證**：集必須存在、不得兩檔同目標、副檔名與分類一致、片長相符；驗證失敗即丟棄並交給人。
- **執行**：通過驗證、且這個決定點的開關在 AI → 直接套用（入庫可撤銷：硬鏈接，原檔在 complete）。AI 的結果照樣走上面的程式檢查，不通過的不套用、交給人。
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
| `episodes_overdue` | 每日巡檢：訂閱的作品最後入庫的一集之後，有集播出滿門檻（從播出日隔天 00:00 起算，預設 2 天）還沒入庫；下載還在動、等審核、Job 已有 Issue 管著的不算（M5.5 票 10） | 搜這一集或去訂閱（作品頁）/ 處理卡住的 Job（Job 頁）/ 忽略（條件持續期間有效）；都入庫了系統自己收掉 |

表上十五種與巡檢另外五種（`first_batch_stuck` 等，plan §2.4）共用 `issues` 表與同一個封閉集合，表上的來源分五組：

- 前七種：對帳。
- 中間四種（`missing_files` 到 `jellyfin_item_unresolved`）：管線自己發現，另以 `issue_detected` 事件記著。
- `library_uses_tvdb`、`low_disk_space`：`health_checker` 每 5 分鐘量出來，由健康檢查偵測而不是對帳。
- `jellyfin_item_mismatch`：Jellyfin 回驗，反查與對帳的 Jellyfin 那一方比同一份。
- `episodes_overdue`：每日巡檢，一部作品一件，說出晚的集與卡在哪（字幕組沒發、送單失敗、下載停滯、入庫失敗）。不讀 RSS 頁的「已完結」：安靜 30 天正是要說的時候。和下一集隔了三週以上的說「可能是下一輪」（換輪）；最後一集缺集播出滿 60 天不再提醒；退訂了就不看（M5.5 票 11）。從作品頁預先綁定作品、字幕組一集都還沒發的訂閱也看，從綁定那天之後播出的第一集算（M5.5 票 12b）。

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
- `jellyfin_item_mismatch`、`unknown_torrent` 與巡檢那幾種（含 `episodes_overdue`）照同一條：回驗每日對帳比一次、巡檢每天量一次，`unknown_torrent` 的 poller 每 5 秒寫一次，照「這一次」會為同一件事每天推、忽略 5 秒就重開。對帳的其餘六種仍是「這一次不處理」。

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

**只用 TMDB**，同時負責探索與季集結構。理由：

- Jellyfin 內建的劇集 provider 預設是 TMDB，本系統的季/集編號必須與 Jellyfin 顯示一致，否則檔名 `S02E01` 在 Jellyfin 會對到別集；同源最安全。
- Seerr 長期只用 TMDB，媒體牆體驗已被驗證（近期才加入實驗性 TVDB，目的只是配合 Sonarr）。
- TVDB 在動漫 split-cour 上與 TMDB 採**同樣的合併政策**（§20.3），換 provider 不解決主要的編號錯誤來源；引入第二個 provider 的代價是每個 Media 多一層 ID 對應與衝突處理，不值得。
- 授權不構成差異：TVDB v4 key 免費且自助申請、不帶 PIN 可讀（§20.3）；ToS 擋的是「內建一把 key 發給所有使用者」，不是「使用者自己申請一把填進 Berth」，與 TMDB 的做法對稱。

**TVDB 作為動漫的季集來源：不採用【決定】。** 對 10 部動漫、7,833 筆真實字幕組釋出量化了三種來源的換算失敗率（[`docs/research/anime-episode-source.md`](research/anime-episode-source.md)）：

| 來源 | 換算失敗率 |
| --- | --- |
| TMDB 季集 | **8.0%** |
| TVDB default（aired） | **7.6%** |
| TVDB absolute | **7.6%** |

差距 0.4 個百分點，且方向兩邊都有（TVDB 在《航海王》贏 4.4 點、在《SPY×FAMILY》輸 3.9 點）。換不到的東西不值得付三個代價：

- **引入第二個 provider**：每個 Media 多一組 `tvdb_id` 與對不上時的處理、快照抓兩次快取兩份、精靈與設定頁多一把使用者自備的 key。
- **Jellyfin 那一端必須跟著改**：媒體庫要改用 TVDB 插件刮，編號才對得上，而這是 Berth 保證不了的使用者設定。
- **走 absolute 還要再多一步**：Jellyfin 本體沒有絕對編號的概念，得對每一部劇寫 `Series.DisplayOrder`（§20.3）。

因此 `media` 表不加 `tvdb_id` / `episode_source`，不做 TVDB adapter。

已知弱點與對策：

- **主要弱點不是編號來源，是檔名裡沒有季號。** 三種來源同時失敗的有 573 筆，佔 TMDB 全部失敗的 91%（573/627）。主要成因是「柱訓練篇」「最終季」「死滅迴游」這類**篇章名帶語意但沒有數字**，換 provider 一集都救不到；唯一「有季號還錯」的一類是「第三季 第二部分 / Season 3 Part.2」——缺的是 cour 偏移不是季號。對策：解析器用 `MediaSnapshot` 已有的各季 `name` 與 alternative titles 比對篇章名、把「最終季」對到最後一季、把「第二部分 / Part.2」當成 cour 偏移（plan §4.4）。
- 絕對編號換算只影響 16% 的釋出，TMDB 在那一段錯 4.4%（TMDB 沒有 absolute 欄位，只能數播出序位）→ 維持絕對編號換算加 review，但它不是主要槓桿。
- 字幕組的編號習慣有四種且同一部作品會並存（每 cour 從 01、官方編號、正篇序位、季內連號），任何「假設編號一致」的設計都會踩到（§20.3）。
- 使用者在 Jellyfin 該媒體庫改用 TVDB 插件 → 本系統讀取 `LibraryOptions` 偵測並警告「編號來源不一致」。
- AniList/MAL ↔ TMDB 對應（Fribb anime-lists）不用：AI 助理拿它對應 17 部錯 4 段，網搜集數表加 TMDB 季集表錯 0 段（`docs/research/agent-sources-ab-2026-10-28.md`）。RSS 的 offset 建議用 Mikan 開播日，見 §15〈offset 建議〉。

**什麼情況該回頭重看這個決定。** 「只用 TMDB」不是永久結論。下面三條任一成立就重跑 `scripts/experiments/anime_episode_source.py` 並重新評估，其餘時候不要再開這個題目：

1. **Jellyfin 換掉預設的劇集 provider，或社群普遍改用 TVDB 插件刮。** 上面第一條理由（同源最安全）是整個決定的承重牆，它一旦反向，結論就跟著反向。
2. **解析器的「篇章名 → 季號」做完之後，benchmark 的季集失敗仍集中在 provider 結構差異上。** 量測時那一塊只剩 78 筆（只有 TMDB 錯 54、只有 TVDB 錯 24），佔樣本 1%；主因（573 筆）是解析器缺口。若補完解析器後比例翻轉，代價與收益就要重算。
3. **美劇 / 韓劇出現同類問題。** 只量了 10 部動漫——動漫是最難的形態（split-cour、字幕組四種編號習慣並存、劇場版插號），結論往簡單形態推是合理的，但**沒有量過**。benchmark 語料含美劇 / 韓劇 8 筆（§20.4），那裡是第一個會看見的地方。

---

## 11. 帳號與權限【決定】

沿用 Seerr 做法：以 Jellyfin 帳號登入本系統。

- 初次設定（[ADR-0012](adr/0012-owner-is-jellyfin-admin.md)）：輸入 Jellyfin 位址 → 以 Jellyfin **管理員**帳號登入 → 該帳號成為本系統 admin，並產生本系統用的 Jellyfin API key。
- 其他 Jellyfin 使用者可登入，預設角色 `user`：
  - 可探索、可送單到指定 Route、可看自己的 Job。送單只能送這次搜尋記下的結果，不收網址，也拿不到索引站的 API key。
  - 只有 admin 能改 Route、刪除、審核。Review Queue、Issue 的動作、rematch、刪除範圍、手動對帳一律只有 admin（plan §6 的門禁與 `api/gate.py`；[ADR-0006](adr/0006-review-and-issues-split.md)）。
  - `user` 送單的 Job 停在 review 時只能等，畫面上說「等管理員審核」。
- 不自建密碼系統；本系統的 `users` 表只存 Jellyfin user id 與偏好。
- 未來的審批、配額、通知都掛在這個角色模型上。
- 取捨：Jellyfin 掛掉時無法登入。可接受，Seerr 同樣如此。

---

## 12. 播放【決定】

**深連結到 Jellyfin** 該項目的詳情頁（帳本存有 Jellyfin item id；劇集連 Series，電影連 Movie）。

- 格式：`{對外網址}/web/#/details?id={itemId}`，客戶端自己的 `#/` 形式，不帶 `serverId`（對 12.0.0 實測開到同一頁，§20.1）。Seerr 用的是 `{externalUrl}/web/index.html#!/details?id={itemId}&serverId={serverId}`。
- 主機是選填的「Jellyfin 對外網址」，沒填時推導（Seerr 的 `externalHostname` 慣例）；套件內的 Jellyfin 用瀏覽器的主機名加 `JELLYFIN_PORT`。
- Jellyfin 沒有「直接開始播放」的穩定 URL，使用者在那一集的詳細頁再按一次播放。
- 不做內嵌播放器：播放器牽涉轉碼協商、字幕（動漫的 ASS 與字型）、播放進度回報，是最大工作量且與本系統核心無關；多數人在電視與手機上用 Jellyfin 的 app 看，網頁播放器取代不了它們。

**瀏覽由 Berth 取代**：媒體庫頁與 Media 詳情像 Jellyfin 那樣呈現整個 Jellyfin 媒體庫，並疊上本系統的入庫狀態。

- 呈現：繼續觀看、下一集、已看 / 未看（可切換，寫回 Jellyfin 該使用者的紀錄）、依類型或年份排序、Jellyfin 的圖、選季選集。
- 按下播放或某一集時才深連結到 Jellyfin 的那一項。
- 伺服器 API key 可以代讀代寫每位使用者的觀看資料（§20.8），但 Jellyfin 這時只套用一部分媒體庫權限，所以**媒體庫存取權限要由 Berth 自己擋**：`userId` 一律取自 session，媒體庫對 Jellyfin 的 `UserViews` 允許清單驗證。劇的集數（`/Shows/{id}/Episodes`）只問兩種 id：`locate` 確認過看得到的劇，或從允許清單媒體庫的整份清單（`index`）讀到的劇；NextUp（`seriesId`）仍只認前者。

---

## 13. 頁面清單

| 頁面 | 目的 | 關鍵內容 |
| --- | --- | --- |
| 設定精靈 | 首次啟動（只管第一次，跑完之後導向設定） | Jellyfin、qBittorrent、Prowlarr 各一頁，每頁由使用者選套件內或既有、選完當場測試（不偵測）。順序：Jellyfin → 以它的管理員成為擁有者（套件內或還沒初始化的那一台由擁有者建）→ qBittorrent → 媒體庫路徑與 Route（建立並跑檢查）→ Prowlarr 與索引站 → TMDB → 完成。兩種來源都只建 Berth 擁有的物件（§16.3、§16.4） |
| 探索（首頁 `/`） | 找東西 | **只放 TMDB 牆**（[ADR-0004](adr/0004-library-browsing-and-discovery.md)）：趨勢 / 熱門 / 搜尋。繼續觀看與下一集只在媒體庫頁。登入後預設落在媒體庫；媒體庫裡還沒有 Berth 入庫的東西時落在這裡。卡片顯示狀態（未追蹤 / 部分 / 完整 / 下載中），**四種都由 Job 與帳本推導** |
| Media 詳情 | 決策中心與觀看入口 | 探索與媒體庫點進的是**同一頁**。作品已在 Jellyfin 裡時最上面是**觀看區**：繼續看 / 下一集的深連結、選季選集、各集劇照與已看標記。其下依序：TMDB 資訊、各季各集入庫狀態、**搜尋 torrent**、選 Route 送單、RSS 訂閱、**這部作品的下載**、檔案清單（含 Unmatched 與 rematch）、版本並存清單。細節見下表 |
| 媒體庫 | 瀏覽與修正 | 像 Jellyfin 那樣瀏覽**整個 Jellyfin 媒體庫**（不只 Berth 經手的）：一個 Jellyfin 媒體庫一頁、只列這位使用者在 Jellyfin 看得到的；繼續觀看、下一集、卡片牆附已看 / 未看、依類型或年份排序。Berth 經手的作品疊上入庫狀態，還沒進 Jellyfin 的（下載中、待審）也在牆上。篩選：待審 / 對不到（只給 admin）。不放「有 Issue」篩選：`/issues` 是獨立頁 |
| 下載與活動 | 全域狀態 | 所有 Job 列表：狀態、進度、Route、trigger；點入 Job 頁 |
| Job 詳情 | 可觀測性 | **獨立頁 `/jobs/:hash`**：**時間線**（§5.2）、檔案清單與各檔決策、Plan 歷史、動作（重新解析、重新入庫、刪除範圍） |
| 頁首 | 到處去 | 主導覽：探索、新番（M5.5 票 09 起每個人）、媒體庫、下載、待處理（admin）；外面是助理開關與帳號選單（名字與角色、設定、健康、週報（admin）、語言、登出）。待處理與新番帶件數（只有 admin 看得到）：待處理是審核加 Issue、新番是待綁定的 RSS Series，加起來是「有 N 件等你處理」的 N。待處理區塊的分頁是審核 `/review`、Issue `/issues`（兩頁仍分開，ADR-0006），新番區塊是時間表 `/schedule`（每個人）、追更 `/schedule/tracking`（admin）與訂閱 `/rss`（admin） |
| 時間表（`/schedule`） | 找當季新番 | 這一週 TMDB 上播的動畫（brief §20.3），週一到週日分欄、今天標出，窄版一次一天；預設列全部（含長壽、兒童節目與國產動畫，篩不篩等用過再定），可切「只看已訂閱」。一集一張卡：小海報、顯示用標題、季集、放送時刻（AniList，只有未來的）、狀態（已入庫 / 已訂閱，未訂閱不畫）、Bangumi 評分；時刻與評分只在原文名對得上時顯示（§20.3），來源失敗只少這兩格；點進 Media 詳情走現有的訂閱流程；那一集晚了時是「晚 N 天」（中性色塊，票 12）。一般使用者看得到狀態類別，看不到字幕組與 Feed（`.scratch/m5.5/schedule-shape.md`） |
| 追更（`/schedule/tracking`） | 訂閱的作品有沒有按時入庫（admin） | 一部作品一列：字幕組、已播到、已入庫到、狀態（「為什麼沒入庫」的結論，下載停滯另外說；晚的寫「晚 N 天」，從播出日算，換輪的說「可能是下一輪」）。分要你動手、準時、斷更很久（最後一集缺集播出滿 60 天，預設收起）三段，桌機是表格、窄版一部一塊。對象與判定同遲到提醒。沒接 Discord 的管理員頁首看得到「遲到只會顯示在這裡」，連到通知設定（不另做其他通知管道，ADR-0015；`.scratch/m5.5/tracking-shape.md`） |
| 審核佇列 | 人工介入 | 低信心 Plan（逐檔可改）、已入庫待確認（medium 自動入庫的 audit 清單，可一鍵撤銷；同一個 Job 一組一顆「全部確認」、整段一顆，收起時說出為什麼是 medium）、Unmatched、重複版本；批次核准。**Issue 不在這裡**：只在 `/issues`，這一頁原位一行「另有 N 件待處理」連過去。**一列一件事的清單，不是牆**：篩出來常常只有一兩件，卡片牆說不出「有幾件事在等你」。只有 admin 進得來 |
| 訂閱（RSS，`/rss`） | 自動化 | Feed 清單、RSS Series 清單（待綁定排最前、就地綁定作品與 Route）、最近的 Feed Item、一次性 RSS 連結、新 Feed 的第一輪預覽（§15） |
| 健康與問題 | 維運 | 服務連線、Route 硬鏈接檢查、Reconciler 結果、磁碟空間 |
| 設定 | 管理 | 一格泊位一頁（Jellyfin、qBittorrent、媒體庫路徑、索引站、TMDB），與精靈共用元件與命令：服務位址與憑證、索引站、TMDB key、Route；之後加命名詞彙、解析與 AI 開關、使用者角色 |

Media 詳情各塊的規則：

- **搜尋 torrent**：按搜尋前用 chip 選要問的名字與季、說出會發幾個查詢。結果表列大小、做種、來源、解析出的 tags、預估匹配。作品已入庫時收合。
- **這部作品的下載**：排在 RSS 訂閱之後、季集之前。
  - 每一筆 Job 列狀態、進度、大小、來源與字幕組、Route、時間；展開看它的檔案、大小與計劃對到的季集，連到 Job 詳情。
  - 預設只列還沒了結的：在路上的，加上已入庫而還有檔案待確認的；其餘在「全部」。
  - 從沒送過下載的作品整段不畫。
  - 季表的「下載中 / 卡住」連到蓋到那一集的那一筆。

---

## 14. AI 與通知【決定】

**形狀從一開始就定**：

- **API-first**：UI 做得到的每個動作都是一個有名字、有 schema、冪等的服務命令（`search_torrents`、`add_download`、`generate_plan`、`apply_plan`、`rematch_file`、`delete_job`、`reconcile`、`issues.relink`——Issue 的按鈕一顆一個命令…）。AI 的工具與 MCP server 只是包裝這些命令。
- **資料可讀**：Plan、Event、Issue 都是結構化 JSON，AI 不需要爬 UI。

**AI native**：目標是綁不到 TMDB、解析不出集數、offset 錯、解析錯這類問題**幾乎不需要人工處理**，外加定期巡檢。原則：

- **沒有 AI 也完整可用**：AI 只是替使用者按審核頁、待處理頁上的那些按鈕，讓人專心看片——平常用 Jellyfin App 看，只在要加新作品時打開 Berth。
  - 每一種 AI 任務都有同一個命令的人工版本。
  - 不需要 AI 的檢查（Jellyfin 回驗、片長驗證、每日程式檢查）與通知是核心功能，不綁在 AI 上。
  - 沒有 AI 時要靠規則、批次動作與通知把人工降到最少。
- **三層漏斗**（[ADR-0008](adr/0008-ai-autonomy-and-optional-ai.md)）：規則層 → AI → 人（§6.10）。沒有 AI 時是兩層：播出日比對、片長驗證與 Jellyfin 回驗（M3），加上每日檢查與通知（M4），都不靠 AI。
- **自主權看可不可以撤銷**：每個命令在**命令登錄表**裡標明副作用等級（讀取 / 可逆 / 不可逆）與反向命令。
  - 可逆的（綁定作品、改季號與 offset、核准或改寫計劃、rematch、確認 audit、重試、recheck、重新反查、在 torrent 數與磁碟門檻內補下載）通過驗證後 AI 自己做。
  - 不可逆的（刪 complete 檔案、移除 torrent、purge）與改設定、Route **永遠要人**，做成 Proposal。判斷是 `services/commands.py` 的 `needs_person`：標記是 `irreversible`，或帶「連到新位址」「對外發訊息」「改設定」任一個旗標。
  - 「忽略 Issue」會把問題藏起來，也做成 Proposal。
  - 新增的命令都要先標好等級、反向命令與旗標。
- **AI 說了不算，要經過驗證**：AI 的結果與規則層的結果走同一組程式檢查（播出日、片長、TMDB 集存在、不撞目標路徑），不通過的不套用。
- **信任靠評估，不靠人陪跑**：使用者不在頁面上逐件處理，所以不做影子模式（2026-11-10 改）。每種任務型別先對凍在 repo、附標準答案的案例集跑 **AI 評估**，套用的錯 0 件才開放（只動可撤銷東西的至少 20 件，會送下載的至少 60 件）；之後靠程式驗證、可撤銷與 AI 活動頁兜底。背景任務一次送出的 torrent 超過 13 個或磁碟不夠就改成 Proposal（2026-11-11），送錯的下載收不回，靠數量上限而不是靠評估擋。開關以決定點為單位，人 / AI 兩段，可隨時切回。
- **可追溯、可撤銷**：「AI 活動」頁列出 AI 做了什麼、理由、花費，逐筆撤銷；審核頁只剩 AI 交上來的，每一件附 AI 的理由。
- **記憶是結構化資料**：改正寫回 RSS Series、別名、排除條件，並進 benchmark 候選語料（§6.10）。
- **巡檢**：每天一次只跑程式檢查（不花 token），每週一次完整巡檢（程式檢查標出的項目交給 AI、可逆的修、其餘交給人），產出週報送到通知管道。

| 里程碑 | 內容 | 為什麼在這個位置 |
| --- | --- | --- |
| **M4 巡檢與通知** | 每日程式檢查加每週週報；`events` 的訂閱者加 channel adapter（第一個是 Discord，[ADR-0015](adr/0015-notifications-discord-dm.md)）加每人的訂閱設定；「可以看了」「有 N 件等你處理」 | 不需要 AI；平常不打開 Berth 的前提是有事時它會說，所以排在 AI 之前 |
| **M5 AI 地基與對話 agent** | 命令登錄表與執行器、Proposal（兩者不需要 AI 也成立）；provider（Anthropic 與 OpenAI 相容，各自可設 base URL 與 key）、防護與記帳、觀測頁；每一頁都叫得出的側面板對話：工具、確認卡、外部資料（AniList 當季清單、Bangumi 放送表、網搜）、skills、上下文壓縮、斜線指令 | 有人在場的對話最適合讓核心第一次碰到真實模型；確認卡就是 Proposal 的第一個介面 |
| **M6 人工接管開關** | 以決定點為單位的人 / AI 開關；背景 AI 任務（規則層 low 的 Plan、Unmatched 與待綁定猜作品、offset 修正、audit 確認或撤銷、可疑入庫）；AI 評估；AI 活動頁與撤銷 | 要等核心在 M5 穩了，AI 才有可靠的規則層與執行器可接 |
| **M6.5 Issue 與巡檢交給 AI** | Issue 的各型別（可逆的自動、刪檔與放棄追蹤做成 Proposal，含 `episodes_overdue`）、重複版本、每週巡檢交給 AI、修正回流 | 沿用 M6 的開關與 AI 評估；從 M6 拆出（2026-11-10），讓 M6 早點收尾 |
| **M7 Discord 與 MCP** | M4 的 Discord bot 接上同一個核心：同樣的對話體驗，確認卡是帶按鈕的訊息，身分用個人 API token（§16.2）；命令登錄表另外包成 MCP server | 只多兩個入口，核心與 Proposal 共用 |

**Proposal 只用在不可逆的動作與 AI 沒把握的事**：命令名、參數、理由，人確認才執行。這與「AI 不動原檔」是同一條界線。

**對話裡的確認卡**：

- 這幾類一律出確認卡，其餘可逆動作直接做並給撤銷：
  - 不可逆的。
  - 送出 torrent。
  - 讓 Berth 連到新位址（Feed 網址、改設定）。
  - 對外發訊息。
  - 讀過外部內容之後帶自由文字參數的寫入。
- 卡片的參數由伺服器存，按確認時用存下的那一份，不信前端回傳的。id 必須出自這段對話已存的工具結果，網址必須逐字出自使用者打的字。
- **Route 由伺服器定，要人選時由人在卡片上選**（M5.6）：模型不給 Route，提出時伺服器照作品查——零條就拒絕、一條就用它（卡片只印名字）、不只一條才由人選（預選這部作品上次用的那一條，沒用過就不預選），只收提出時存下的那份清單裡的。**同一部作品只問一次**：卡片上的列依 `media_id` 分組，一組一個選擇，套到那組勾著的每一列；兩部以上作品、可選的 Route 有交集時，頂部另有一個「全部套用」，選了填進每一組、之後仍可逐組改。沒勾的列不必選；送出時 `routes` 照舊逐列展開，API 不變。作品頁的手動送單照舊自己帶 Route。
- **訂閱的字幕組由人選**：可選的不只一個時卡上必選，助理建議的只當預選，伺服器只收提出時讀番組頁或那一次搜尋存下的清單裡的。以作品訂閱時伺服器先找 Mikan 的番組；Mikan 沒有番組、或番組上沒有助理說的那個字幕組時，自己再問 nyaa 與 acg.rip 的關鍵字搜尋，卡片列出兩條路找到的字幕組與各自的來源、由人選一個（M5.6 票 09）。訂閱因此一律出卡（第一批在卡上確認）。
- **送單卡逐列標出作品已經有的集**（帳本或這個人的 Jellyfin，「含已有的第 N 集」）：伺服器提出時算，不靠助理說。
- 整個系列一次送單時先出一張總覽卡，逐列可取消勾選（§20.24）。

**skills 只寫決策順序**（M5.6）：跨任務的共同規則（搜尋與字幕語言、只在使用者要下載或問有什麼時才搜種子且先認出作品再搜、已有的不重抓、確認卡的說法）寫一次在系統指示；skill 只寫這類任務的決策順序，不重述工具說明、不點名特定作品。三份：`download`（電影、一季、缺的集、整部系列）、`subscribe`（連載中的作品）、`recommend`（新番與趨勢），三份合計 ≤ 80 行、`subscribe` ≤ 20 行（`tests/unit/test_skills.py` 的閘門）。診斷沒入庫的原因不是 skill：各結論的意思寫在 `why_not.explain` 的工具說明；「從媒體庫重建帳本」的指引只由 `media.read_media` 的輸出帶出（整季以上都在 Jellyfin、帳本沒有時）。

**provider**：Anthropic Messages API 與 OpenAI 相容的 Chat Completions 都做，使用者自己設 base URL 與 key（自架閘道、OpenRouter、本機模型走後者）。網路搜尋在 Anthropic 用伺服器端 `web_search`，另可設 Tavily key（兩種 provider 都能用）。

---

## 15. RSS 設計要點

以 RSS Series 為單位（[ADR-0007](adr/0007-rss-series-model.md)）。使用者在 Mikan 上選好作品與字幕組，聚合 feed 裡出現的就是要的（Mikan 的 `MyBangumi` 實測：同一部作品訂兩個字幕組是常態）。Berth 的工作是**認出每一筆是哪部作品**，不再挑一次字幕組。

### Feed 與 RSS Series

- **Feed**：URL、輪詢間隔、來源類型、排除條件。【決定】支援 **Mikan**（`/RSS/MyBangumi?token=` 聚合 feed、`/RSS/Bangumi?bangumiId=&subgroupid=` 單一 feed）、**Nyaa**（搜尋 feed、使用者 feed）與 **acg.rip**（搜尋 feed）；之後加 dmhy 與 generic。每種來源一個 adapter，負責解析該站的 RSS 擴充欄位並輸出統一的 Feed Item；各站的欄位與取法見 §20.12。
- **RSS Series**：一部作品 × 一個來源，由 Feed Item **自動長出**。帶著 Media、Route、季號、集號 offset、排除條件、是否已確認。鍵：
  - Mikan 用（番組 id, 字幕組 id）。item 的 `link` 是單集頁，單集頁上有 `/RSS/Bangumi?bangumiId=…&subgroupid=…`。
  - 其他來源用標題骨幹（去掉字幕組、集號、tags）加字幕組（AutoBangumi 的做法）。骨幹有羅馬字那一個名字就取它——同一組的简日、繁日發佈中文名常常不同，是同一個 Series。
  - 標題中間的括號註記後面還接著 ` / ` 與下一個名字時（`尼古喵喵 (邪竜解放版) / ヤニねこ / Yani Neko / Chainsmoker Cat`），搜尋與比對用的骨幹丟掉那一格註記、後面的名字照讀；**鍵不跟著改**，仍讀到第一個括號為止——鍵存在資料庫裡，改了它既有的 Series 下一輪會另長一個。
  - 這些來源沒有番組頁，自動綁定的候選只從標題來，一律留給人。

### 排除與處理

- **全部接受，只排除**：Feed 裡的項目預設全部下載，Berth 不再問字幕組。同一集多個字幕組、同組的 v2 都入庫並存（§7.7）。
- **排除條件**是關鍵字或正則、比對整個標題，分全域、Feed、RSS Series 三層。
  - 預設只排除合集（`release_kind != single`；搜尋 feed 常夾著「01-13 合集」）。合集那一條是全域的開關（看解析器的 `release_kind`，合集、區間、季包的寫法一條關鍵字寫不完），不在 Feed 與 Series 那兩層。
  - 720p、简体等做成一鍵加入的建議項，不預設勾。
  - **合集不是不能解析，只是不自動下載**，使用者仍可從一次性 RSS 或搜尋手動送單。
- **規則格式照 Sonarr 的 release profile**（§20.12）：一般字詞不分大小寫、比對整個標題，`/…/` 包起來是正則（`/…/i` 不分大小寫）；寫壞的存不進去、當場說出原因。
- **只往前看**：規則收緊時還沒送出去的 Item 照新規則再看一次，放寬時不把之前擋下的放回來——拿掉一條規則不該讓幾個月前被它擋下的一次全部下載。
- **逐筆放行**（照 Sonarr 互動搜尋的「照樣下載」）：被排除的那一筆在 Feed Item 清單上按「仍然下載」，當場走同一條送單的路（去重照常，同一個 torrent 已送過是重複）。
  - 只收 RSS Series 已綁定、Feed 已選過第一輪的；送不出就留在排除、帶著原文。
  - 它是人按的、一次一筆，與「只往前看」防的批次放回不衝突；不做整批或依規則放行，也不記「人放行過」。
- **處理流程**：item → RSS Series → 排除條件 → 去重 → 建 Job（trigger = rss、帶 RSS Series id）。
  - 去重：Feed 內的 GUID；跨 Feed 的 info hash；帳本已有同 Media/季/集/Tags。v2 版本號不同，不是重複。
  - 排除與去重擋下的都不是錯誤，Feed Item 清單說出是哪一層的哪一條、或重複了哪一筆。
  - 帳本那一層比不準的（季集猜不到、字幕組在檔名寫另一個組名）放行，由規劃時的重複版本判斷（§7.8）接住——漏擋只是多下載一次，擋錯卻是少一集。

### 綁定

第一次見到的 RSS Series 去 TMDB 找作品（Mikan 的番組頁有中文標題、開播日期、bgm.tv 連結）；有把握就自動綁定，沒把握的進「待綁定」清單，它的項目留著，綁定之後再送。bgm.tv 連結沒有用上：TMDB 不收它的 id。

- **有把握**是 §6.5「標題 + 年份精確命中」在這裡的樣子：
  - 番組名或發佈名的標題骨幹與 TMDB 的某個名字正規化後**相等**。
  - 番組頁的開播日期落在那部作品某一季首播前後 14 天內。
  - 這樣的作品只有一部。
- **Route** 是長出它的 Feed 那一種的那一條：加 Feed 時選（照 Sonarr Import List 的「Root Folder」），劇集、電影各一條，那一種有 Route 就必填（預設安裝的 TV 與 Anime 都收劇集，沒有這一格一部都綁不上）。那一格是空的（較早建的 Feed）或停用了，才照「收得下它的啟用中 Route 只有一條」的規則。
- 自動綁定以 `system` 身分走人工綁定同一支命令，Job 的時間線說出依據。
- 沒綁上的每一種各有理由碼，認得出的作品列成候選讓人一鍵選（選定之後照樣要按一次確認：資料夾名在那一刻定下來，§4.5）。
- **只在 Series 長出來的那一輪認**，不在之後每一輪重認——壞掉的番組頁會每 15 分鐘打一次，人拆掉的自動綁定也會被綁回去。
- **暫時查不到的例外**：連不上、逾時、限流、5xx，理由寫 `lookup_retry`、說出下一次在什麼時候，退避、有上限地重認（1、4、12 小時後，一個 Series 最多認四次，plan §3.2）。用完、或再問也一樣的（404、回的不是那個服務）才落到 `lookup_failed` 等人。
- **一部候選讀不到不拖垮整次**：其餘的照判，判得出來就綁；判不出來而缺的那一部是暫時讀不到的，照暫時的失敗晚點再認；一部都沒讀到才是查不到。
- **季名不進搜尋詞**：TMDB 的作品名不帶季名，`第N季 / 第N期`、`Season N / Nth Season / SN` 從搜尋詞與比對的線索裡拆掉（規則與解析器讀資料夾名同一份，`parser.seasons`）。
  - 拆出來的季號改當開播日那一條的線索——**只比那一季播出的期間**（它任何一集的前後 14 天內；TMDB 把幾季併成一季時是依播出日切出的那一輪，plan §4.4），不是只比首播。Mikan 會把一季的第二個 cour 另開一個番組、寫它自己的開播日（Re:Zero 第四季「夺还篇」，TMDB 65942 第 1 季第 78 集，§20.12）。
  - 第二季的番組頁寫的是第一季的開播日時兩條線索矛盾，留給人。
- 實測見 [`docs/research/rss-sources.md`](research/rss-sources.md) §2.8（11 部認得 10 部、錯 0 部）。

### 補舊集與第一輪

聚合 feed 只有最近的集數。

- **Mikan 的補舊集**：RSS Series 綁定時以它的單一 feed 列出整季，**一律補下載，沒有開關**。
  - 帳本已有、已有 Job 的跳過，排除條件照樣看。
  - 讀不到單一 feed 不擋綁定，下一輪再補。
  - 手動綁定與訂閱沒有「同時補下載舊集」的勾選。
- **每日補漏**：每天用同一個單一 feed 補漏一次，接住 Berth 停機期間聚合 feed 捲掉的集數。RSS Series 完結之後再補最後一次就停（接住停機跨過完結判斷時被捲掉的最後幾集）、新的一筆出現時恢復，不設開關。畫面上看得到上次補漏的時間（排程見 plan §3.2）。
- **搜尋類 feed 第一輪就帶著歷史**：新 Feed 的第一輪不直接下載，列成預覽讓使用者選「全部下載」或「只追之後的」。
  - 預覽依結果分成會送出、綁定之後送、排除、重複四組，排除與重複各說理由。
  - 「只追之後的」當場再讀一次 feed、讀不到就不決定，選的那一刻已經在 feed 裡的都略過。
- **Mikan 不走預覽**：聚合 feed 只有最近的集數，單一 feed 的整季由補舊集處理。

### 季號、offset 與第一批確認

季號與 offset 放在 RSS Series 上，**規劃時讀**，每份計劃記下它用到的值。大部分時候不必設——解析器的季名、篇章名、cour 標記與絕對編號換算先處理（§6.4、plan §4.4）。

- **第一批進審核**：新 RSS Series 的第一批進審核（已入庫、等你看一眼），確認過一次之後照一般信心走，而且之後的 medium 入庫不再進 audit 清單（由播出日比對、片長驗證與每日檢查守著）。
  - 確認之前 high 也掛 audit（Series 帶了季號時解析器給的正是 high）。
- **算錯時**在審核裡改正並「套用到這個 RSS Series」：寫回季號與 offset，並重算它底下還沒確認的集數（補舊集一次十幾集，第一集錯就全錯，改一次要全修好）。
  - offset 是人說的集號減去檔名寫的集號。
  - 已入庫的未確認集數走 rematch 搬過去、**仍留在第一批裡**等「全部確認」（還沒有人看過它們）；人親手改的那一集算確認過。
  - 停在 review 的走重新規劃；已確認的集數不動。
  - 停在審核的計劃列也能「套用到這個 RSS Series」：連載中的 split-cour 第一批會被播出日比對整批擋在審核、一集都沒入庫。人改的那一列照人說的、那一份仍等人核准；同一份裡沒人碰過的列與其餘停在審核的計劃照新的值重算，播出日比對照跑——offset 對了就放行、自動入庫（仍在第一批裡）。管理員逐列改過的其他計劃不動。
- **證據夠強的第一批不掛 audit**：系統確認那個 Series（Job 的時間線記 `series_confirmed` 與擔保的集數）。**證據夠強**逐列看，一列不符合整批就不算：
  - Series 沒有設季號與 offset。
  - 要入庫的列只有正片與跟著它的字幕。
  - **季集照字面**：對到的集號就是檔名寫的（沒有 offset、絕對編號換算、重數推測），季號是寫明的、或只寫集號而對到第一季。
  - **或是寫明季號的累計編號**（M5.5 票 05）：理由是 `absolute_cumulative`、季號是發佈名或資料夾寫明的、檔名集號正好等於前面各季集數加對到的集號（夜櫻家 40 → 前面 27 集 + S02E13）。季號與累加換算互相印證，讀法是確定的。只寫集號的絕對編號、`absolute_group`、重數推測仍等人。量過才收（下面〈量測〉）。
  - 理由只限白名單：標題、年份、季號的字面來源、只有一季、發佈時間落在第一輪、地上波先行（播出日比對放行時記的）、TMDB 沒有片長；累計編號那一種另一份，多 `absolute_cumulative`、少地上波先行與兩條單季的。新加的理由預設不在。季集照字面與白名單和播出日比對共用一個定義（`parser/literal.py`，M5.5 票 04）。
  - 發佈時間與 TMDB 的播出日都拿得到，而且過了播出日比對。
  - **那一集剛播**：發佈前六週到發佈後九天，上緣與播出日比對放行照字面的列相同（兩天加地上波先行一週，§20.27；M5.5 票 04 前是兩天，先行的第一批因此擔保不了）。累計編號與推測虛擬季仍用兩天的窗口。
  - **累計編號的下一集還沒播**（M5.5 票 05b）：整份最後一集的下一集，TMDB 播出日晚於發佈日加兩天（與「剛播」的上緣同一個寬限）；TMDB 沒有下一集或它沒有播出日算還沒播。照字面的列不看這一條：套上去會讓慢發的字幕組多等人（真 RSS 115 筆擋 22 筆）。
  - 片長驗證擋下的列本來就不是入庫。
  - 白名單加「剛播」而不是只看「信心 high」，因為只寫集號的單季作品解析器給的是 medium，那個 medium 防的是「TMDB 還沒建新的一季、照字面讀成第一季」；新一季的第 N 集發佈時舊的第 N 集早就不是剛播。
- **第一批是整個 Series 到確認為止送來的每一筆**：
  - 同一個 Series 的其他 Job 都落地了（入庫中或已入庫；還在下載、停在審核、失敗的都算還沒到齊），還掛著 audit 的每一份也都擔保得了，才整批確認、一起清掉旗標。補舊集的前幾筆先掛著，最後一筆**自動**落地時整批一起看。
  - 有一筆停在審核就是那一批有一列不符合，由人按「確認整個 Series」。
  - **已入庫的舊列不另外掃**：下一集自動落地時整批照同一套條件看（M5.5 票 05 收累計編號時定）；已經完結、不會再有下一集的，留給人按「確認整個 Series」。
  - 仍要人看的那一組（掛著 audit 的正片，與停在審核的計劃），審核頁與作品頁的「第一批待確認」說一句在問什麼（「確認 BLACK TORCH × ANi 的季集對應：S01 E01–E04 由集號直接對應」），組的鍵是「確認整個 Series」。
- **量測**（`scripts/experiments/first_batch_rule.py`）：
  - 語料 36 份擔保 12 份、擔保錯 0（M5.5 票 05 收累計編號後；多的兩份是 SPY×FAMILY 第三季 ANi 與 DYNAMIS 的累計編號，收之前是 10 份；沒有發佈時間的模擬成期望那一集播出後一天，照定義是剛播，所以這一輪量的是照字面與白名單）。
  - 對抗的一輪把發佈時間改成 Berth 自己讀成的那一集播出後一天：30 份擔保 11 份（收之前 9 份）、擔保錯仍是 0。累計編號的讀法不看發佈時間，這一輪對它只多驗「剛播」。
  - 芙莉蓮與藥師少女的 split-cour 第二輪從 01 重數 0 份被擔保、第一輪剛播的都擔保（M5.5 票 05 重跑相同）。
  - 真的 RSS fixture 150 筆擔保 135 筆（M4 票 11）；M5.5 票 05 重跑時 128 筆擔保 113 筆，**沒有一筆是累計編號**，所以累計編號的證據只有語料那兩筆。沒擔保的是虛擬季換算、慢發的補檔與一次補齊的舊集。
  - M5.5 票 05b 加「下一集還沒播」後四段重跑，數字與上面完全相同（SPY×FAMILY 兩筆仍擔保）。
- **已知盲點**：前一季只有幾集、緊接著開播 TMDB 還沒建的新一季時，新一季的第 1 集照字面讀成的舊第 1 集也可能在六週內播過。
- **累計編號與 TMDB 前幾季集數差一集**（原本的已知盲點，M5.5 票 05b 由守衛擋下）：「檔名集號等於前面各季集數加對到的集號」對累計編號的讀法本來就成立，不是另一道檢查；錯的來源是 TMDB 前幾季的集數。
  - TMDB **少記**一集：換算晚一集，比發佈晚一週播，播出日比對擋下（有換算的只容忍兩天）。
  - TMDB **多記**一集（總集篇只有它算）：換算早一集，那一集仍在「剛播」的六週內；擋下它的是「下一集還沒播」——那「下一集」就是真的那一集，一定播過（`test_tmdb_counting_one_episode_more_before`）。回到等人確認，人在審核改 offset。

### offset 建議（候選，未排程）

不改 RSS 的規劃，只在 RSS Series **綁定之後給一個建議值**，顯示在第一批確認與審核的畫面上，由人一鍵套用；不自動寫進 RSS Series。

- **做法**：
  1. 取 Mikan 番組頁的開播日。
  2. 在綁定的 TMDB 作品正篇裡找同一天（±1 天：深夜檔在 TMDB 常記成前後一天）播出的那一集，它就是這一輪的起始集，**offset = 那一集 − 1**。
     - 那一天播的是 Specials 裡的一集（第 0 集）時，取開播日之後正篇的第一集、建議旁註明（同一份研究算無職轉生第二季正解的做法）。
     - 正篇找不到或對到不只一集就不給。
  3. 先用 benchmark 量：建議能少掉多少需要人改的第一批、誤報幾成。
- 這就是 `docs/research/fribb-vs-chaining-2026-10-28.md` 算正解的方法，17 部 49 段沒錯過。
- **只有 Mikan 來源有開播日**；其他來源沒有建議，照現在由第一批確認擋。
- 不用 Fribb anime-lists：它與 AniList 集數串接在同一批 17 部裡分別錯 4 段、3 段，Berth 也不接它（`docs/research/agent-sources-ab-2026-10-28.md`）。
- **它補的是 RSS 現在的盲點**（`fribb-vs-chaining` 研究〈走 RSS 現在的路擋不擋得住〉）：
  - 同一季兩個 cour 間隔不到 180 天又從 01 重數（Re:Zero 第二季後半，98 天）。
  - TMDB 不放在正篇的 TV 條目找不到同一天的那一集、不給建議，照舊由第一批擋。
  - 其餘錯法 RSS 照 TMDB 播出日切季本來就擋得住。
- **什麼時候做**：M5 驗收之後看實際紀錄——RSS Series 第一批被人改季號或 offset（「套用到這個 RSS Series」）夠頻繁，就排進 M6 當一張票；很少發生就維持現狀，由第一批確認擋。

### 從 Media 頁訂閱（次要入口）

選一個來源建單一 feed，並預先綁定這部作品。

- **Mikan 由 Berth 代搜番組**（`/Home/Search`，§20.12）：選字幕組之後建它的單一 feed、當場長出那一個 RSS Series 以綁定的同一支命令綁上，整季照補舊集的規矩（一律全補）。
  - 人在場，所以讀不到單一 feed 就當場拒絕、什麼都不加（綁定時的補舊集是讀不到不擋、下一輪再補）。
  - 那個 Series 已經在待綁定時就地綁它、不多開 Feed。
- **助理訂閱走同一條路**（M5.6 票 08）：助理只給作品與推薦的字幕組，不用先自己找出番組 id。
  Berth 用作品的中文（含簡體）、原名、羅馬拼音與英文名搜 Mikan，挑番組的規則與〈綁定〉的「有把握」同一套：名字拆掉季名後相等，而且番組頁的開播日落在作品首播前後 14 天內；同名不同年由開播日分開，兩個一樣近就不挑。番組頁上的字幕組列在卡片上由人選。找不到番組、或番組上沒有助理說的那個字幕組時，改問 nyaa 與 acg.rip 的關鍵字搜尋（各站先用最可能命中的前兩個名字），兩條路的字幕組一起列在卡片上、各帶來源由人選；訂關鍵字那一條時第一批照卡上列出的送（M5.6 票 09）。讀不到 Mikan 不自己換來源（分不出「站上沒有」與「暫時讀不到」）；三個站都沒有字幕組才拒絕（`subgroups_not_found`）。
- **Nyaa / acg.rip 以作品的標題建搜尋 feed**，Feed 記下作品與 Route。
- **關鍵字訂閱只綁一個字幕組，而且由人選**：先搜一次，列出搜到的字幕組（筆數、最近更新、最新一筆，同 Mikan 的字幕組清單），選一組才建。
  - Feed 只收那一組的發佈（`rss_feeds.subgroup`，照發佈名裡的字幕組比對，別組的不寫、不長 Series），那一組長出的 RSS Series 以建它的人的身分綁上。
  - 字幕組必填，沒有「每一組都綁」的路。`subgroup` 空的 Feed（較早建的、綁了好幾個字幕組的）照舊運作，不做 migration；第一輪預覽只留給它們與手動加的搜尋 feed。
  - 第一批（那一組這一次搜到的發佈名）就在作品頁或確認卡上列出，第一輪也在同一處選：「下載這些並追之後的」（預設，那個 Series 記成第一批已確認）或「只追之後的」（現有的記成略過、一筆都不送）。與 RSS 頁第一輪那兩顆同義、走同一支命令（`rss.prime_feed`），不再到 RSS 頁選；按下去那一刻才出現的也算在這一批。
  - 作品頁不另加數量上限（清單攤在眼前、人自己按），側面板的卡一張最多 13 個 torrent。
  - 讀不到搜尋就不建（人在場，第一輪選不了的 Feed 不留下）。
  - 搜到別部作品的風險由人看過的第一批與 Series 的播出日比對接住。
- **重複訂閱說出來**：訂閱或加 Mikan 單一 feed 之前查這部作品現有的訂閱（`rss.list_subscriptions`），卡上與給助理的結果都列出來源與字幕組，由人決定。助理能刪訂閱（`rss.delete_feed`，不可逆、出卡，已下載的檔案與綁定留著）。
- 詳情頁列出已綁在這部作品上的 RSS Series（來源、字幕組、第一批確認了沒、最近一集），整段只有 admin。
- **只下載現有的**：已完結、字幕組只出了合集的作品，訂閱建的 Feed 那一筆合集馬上被全域預設擋下、之後也不會再有新的——要的是「把現在有的下下來」。
  - 選好字幕組之後「訂閱」旁邊有「只下載現有的」：就地走一次性 RSS 連結（不建 Feed、逐筆手動送單、排除條件不擋），網址是後端給的那一組單一 feed、作品與 Route 帶好。
  - 訂閱之後讀到的若有被排除的，回報說出幾筆、理由，並指向它。
  - Nyaa / acg.rip 走搜尋頁、不做這一條；不在訂閱前預讀單一 feed 判斷「只有合集」（多一次請求，回報那一句已經接住）。

### 一次性 RSS 連結

貼上 URL → 解析全部 item → 勾選 → 送單，不建立 Feed。

- 選一部作品與一條 Route（同一批共用）之後，季集照那部作品換算、標出帳本已有與已經有下載的。
- 送單逐筆走一般的手動送單（`trigger = manual`），不是 RSS 的路。
- 排除條件只作用在自動下載，這裡只標出合集、不擋。

### RSS 頁的呈現

綁好的 Series **作品一塊、字幕組一列**。

- 來源說 Mikan 的番組名與字幕組名、不說數字 id；名字取自已經抓過的番組頁（自動綁定讀的、從 Media 頁訂閱時讀的），**不為了顯示多打 Mikan**，沒有就不顯示。番組名另一個來源是單一 feed 的 channel 標題（`Mikan Project - <番組名>`；補舊集與每日補漏本來就讀它）。
- 列上說已入庫 / 下載中 / 排除各幾筆與最近**發佈**的那一集（不是長出它的那一筆），展開看它的每一筆 Item。
- Series 層的排除條件收進「進階」，Feed 層的在明處。
- **已完結**的收進段尾預設收起的「已完結」。條件（任一）：
  - TMDB 說完結（`status` 是 `Ended` / `Canceled`，§20.3）、這個 Series 入庫過的那幾季每一集都在帳本裡、沒有在等或在路上的、最近一筆也發佈滿一週了。
  - 最近一筆發佈之後 30 天沒有新的（試跑最長間隔 22 天）。
- 已完結**不是存下來的狀態**，每次照現況算（`parser.finished`）：紀錄不刪（去重與重新出現時的綁定要它），新的一筆出現時——不論送了沒，排除、重複、v2 都算——條件自己不成立，它就回到清單。

RSS 依賴解析器與管線，因此排在 M3 而非 M1（§17）。

---

## 16. 部署與跨切面需求

### 16.1 部署

- 技術棧【決定】：後端 Python（FastAPI + 同一程序內的背景 worker + SQLite），前端 React（Vite），單一容器發佈。`/config` 存資料庫與設定，`/data` 掛媒體根。
- **目標環境【決定】**：Linux（NAS 與伺服器）與 Windows（Docker Desktop，WSL2 後端）。兩種使用者：NAS 使用者已有目錄規劃、可能已有 Jellyfin；一般電腦使用者什麼都沒有，要能「下載一份 compose、跑起來、開瀏覽器」就完成。
- 範例 `docker-compose.yml` 含 `berth`、qBittorrent、Jellyfin、Prowlarr，前三者掛同一個 `/data`（Prowlarr 不碰檔案）；權限採 TRaSH 的「單一使用者 + UMASK 022」簡化方案（§20.2），四個容器同 `PUID/PGID`。
- `/data` 一律用宿主目錄 bind mount（`DATA_ROOT`），Linux 與 Windows 相同：Windows Docker Desktop 的 NTFS bind mount 硬鏈接已實測可用（§20.7）。不支援 exFAT；健康檢查在建立 Route 時即驗證。
- 使用者文件明列（README 只留必讀，其餘在 `docs/guide/`）：
  - 硬鏈接前提：單一掛載、不可 exFAT、不可跨 btrfs 子卷 / ZFS dataset / mergerfs branch。
  - 支援 Linux 宿主與 Windows Docker Desktop（NTFS）。
  - qBittorrent 版本下限與必要設定（category autoTMM）。
  - Jellyfin 版本下限 12.0，以及從 10.x 升級的注意事項：先完整備份、移除第三方插件、升級後完整掃描、不能降級（§20.9）。
  - **使用者要自備 TMDB API key 與取得步驟**（§16.3）。
  - TMDB 的歸屬聲明與 logo。

### 16.2 跨切面需求

- **外部呼叫**：統一逾時、重試與退避；服務不可達時 Job 停在當前狀態並記事件，不判定失敗；健康檢查頁顯示每個服務最後成功時間。
- **資料庫**：SQLite WAL；schema migration 用 Alembic；備份就是複製 `/config`；提供「從磁碟 inode 掃描重建帳本」的災難復原指令（§7.9）。
- **秘密**：API key 存在 DB，靠檔案權限保護，不做應用層加密（與 Seerr 相同），`docs/guide/backup-and-reinstall.md` 註明。
- **日誌**：結構化，每行帶 job id；Event 是使用者可見層，log 是維運層，兩者不互相取代。
  - 網址的 query 值在 log（含 uvicorn 自己印的兩個 logger）與 `ServiceError` 的訊息（含 Prowlarr 的逐條理由）裡遮成 `***`，不認參數名（httpx 的 INFO log 印過 Mikan 的個人 token）。守它的是 `tests/unit/test_logs.py` 與 `test_redact.py`。
  - 不是 `ServiceError` 的例外原文（Job、Feed 整輪失敗時寫的 `型別: 原文`）不遮：httpx 的例外都在 adapter 裡翻成 `ServiceError`，目前沒有帶網址的例外走到那裡。
- **安全**：所有 API 需登入；未來 AI / MCP 用個人 API token；容器非 root；不開 CORS 萬用字元。
- **測試**：解析 benchmark（純函式，CI 必跑）；管線整合測試用假的 qBittorrent / Jellyfin / TMDB adapter；docker compose 端到端至少覆蓋 M1 驗收流程。
- **i18n**：zh-Hant 與 en 並列，字串集中管理、一律走 key；檔名 token 與 log 一律英文。面向英語自架者，見 `PRODUCT.md` 的 `## Users`。
- **授權**：MIT（與 Seerr、AutoBangumi 相同）。TMDB 條款限非商業使用，README 註明。

### 16.3 開箱即用（一鍵設定）【決定】

目標：新手使用者下載 compose 範本、`docker compose up`、開瀏覽器，之後所有設定都在 Berth 的精靈裡完成，不需要分別打開 qBittorrent、Jellyfin、Prowlarr 的介面。做法是「預置設定檔 + Berth 透過各服務 API 代為設定」，兩者都冪等，可重複按。

**唯一要離開 Berth 的一步是 TMDB 憑證**【決定，閘門見 [ADR-0011](adr/0011-wizard-accepted-frictions.md)】：使用者得先去 themoviedb.org 註冊、在「設定 → API」申請一把 key，貼進精靈的 TMDB 泊位。Berth **不內建任何 provider 的 API key**——不替所有使用者背一把共用憑證（Seerr 內建了一把，§20.7）。代價是「開箱即用」缺了這一角，這是知情且接受的；TMDB 與 §10 評估過的 TVDB 在「使用者自備 key」上是對稱的。

| 服務 | 預置（compose 範本） | Berth 一鍵設定（API） | 使用者仍需自己做 |
| --- | --- | --- | --- |
| qBittorrent | **只預置「讓 Berth 進得去」**：只放行 Berth 容器固定 IP 的免密白名單（不是整個網段，理由見 §20.7）。原因是 4.6.1 起首次啟動的隨機密碼只印在容器 log，Berth 拿不到，沒有這一步按鈕就登不進去 | 套件內：設定介面登入（必填；可「沿用 Jellyfin 帳密」，見下文；不設的話它的介面只剩容器 log 裡每次重啟都換的臨時密碼）。**全域偏好一個都不寫**：送單逐個 torrent 帶 Berth 的分類與 `autoTMM=true`，save path 與未完成目錄開在分類上，全域的 save path、autoTMM 都不影響 Berth。既有：填位址與 WebUI 帳密，同樣一個全域偏好都不寫（§16.4），**連線測試通過就做完**，沒有不寫入的確認鍵。兩種都依 Route 建立 category | 無 |
| Jellyfin | 無 | 精靈第一頁選套件內或既有 → 那一台還沒跑過初始精靈就以擁有者填的帳密建立 Jellyfin 管理員、跑完它的初始設定；已經有管理員就用管理員登入 → Berth 自己建 API key「Berth」（帳密不存下來）→ 媒體庫與路徑泊位：套件內建立使用者在精靈列的媒體庫（內容類型 + 名稱 + 資料夾，預設 Movies / TV / Anime 對應 `/data/library/{movies,tv,anime}`，可改名、增刪），既有只「加入 Berth 路徑」→ 每個媒體庫一個 Route。**套件內第一次來、清單沒改過時進頁就建立並檢查**，逐條 Route 顯示跑到第幾條檢查；改過清單、跑過一次之後與既有，照舊按「建立並檢查」 | 無 |
| Prowlarr | 無；Berth 唯讀掛載其設定目錄讀取 API key（套件內零輸入） | 套件內：見表後〈Prowlarr 的站〉。設定介面登入（與 qBittorrent 同一條「沿用 Jellyfin 帳密」規則，各自一組；自己的一顆按鈕，不跟著「加入」）。既有：貼 API key，用使用者已有的索引站；一站都沒有時這一頁待處理，也可以測試推薦的公開站、按一次加進它；Berth 不移除它的站、不設它的登入 | 私有站的帳號 |
| TMDB | 無——**Berth 不內建任何 provider 的 key**【決定】 | 無 | **必要**：自己申請一把 API key 貼進精靈的 TMDB 泊位（§20.7） |
| 索引站 / RSS | 無 | Mikan、Nyaa feed 由使用者貼 URL | 貼自己的 Mikan 訂閱 URL |

**Prowlarr 的站**（套件內）：

- 推薦清單：Nyaa.si、dmhy、Anime Tosho、ACG.RIP、Mikan、1337x、YTS、EZTV、The Pirate Bay（AniDex 不在清單，§20.7）。
- **一顆主鍵「測試推薦站，加入通過的」**：測還沒加入的推薦站、通過的加進去，結果逐站列出。測過而新增被拒的（Prowlarr 加之前自己再連一次，§20.7）單獨說、不算已加入。Prowlarr 已經有站時不給這顆鍵。
- 逐站測試與勾選、schema 裡其他公開的 torrent 站收在「進階」：預設不勾、先測試通過才勾得起來再加入（`indexer/test` 測還沒加入的定義，§20.7）。
- **可以不用**：精靈頁 4 的「之後再說」與設定 → Prowlarr 的「不用 Prowlarr」是同一個狀態，可逆。不用時健康不檢查它、BTH 4 是「沒有使用」不算阻擋，作品頁的搜尋說沒有接索引站、可以接 Prowlarr 或用 RSS 訂閱，Berth 不動它的站與容器。

規則：

- **每個服務由使用者選來源，不偵測**（[ADR-0010](adr/0010-wizard-manual-service-selection.md)）：Jellyfin、qBittorrent、Prowlarr 各一頁，頁首二選一「套件內」/「既有」。
  - Seerr 連 Jellyfin、加 Sonarr / Radarr，Sonarr / Radarr 加下載器，全都是手動填位址與憑證、按 Test，沒有自動偵測（§20.14）。
  - 選擇存下來，從此「套件內 / 既有」由它決定：套件內的連 compose 主機名，既有的填位址與憑證。
  - NAS 使用者常見的組合是既有 Jellyfin + 套件內 qBittorrent 與 Prowlarr。
  - 不偵測的理由：偵測說不出服務是誰的，只能靠「免密可進」「無索引站」這類跡象猜，猜錯就會寫使用者的服務。
- **不偵測、不判定，但選完要測試**：選了套件內而 compose 沒起那個服務（`COMPOSE_PROFILES` 拿掉了）時，測試失敗要說出怎麼補：「把 `qbittorrent` 加回 `.env` 的 `COMPOSE_PROFILES` 再 `docker compose up -d`」。容器還在啟動的輪詢規則見 plan §9.3。
- **只存驗過的憑證、錯誤標在欄位上**（Home Assistant 驗過才 `create_entry`、`errors[欄位]`；Sonarr 存之前再測一次、錯誤綁欄位）：
  - 既有服務的位址與憑證、TMDB 的 key 都測過才存；測不過什麼都不換，已經有一組驗過的在用就照舊用它。
  - 錯誤分兩類標在各自的欄位旁：位址類（連不上、解不到、協定寫錯、回的不是這個服務、填了 localhost）標位址，憑證類（帳密或 key 被拒、被封、key 沒填）標憑證；其餘留在表單層級。
  - 人話、手動步驟、技術細節分層呈現。
- **兩種來源接下來做的事一樣，只差誰讓服務登得進去**：Berth 只建立與管理自己擁有的物件——Jellyfin 的 API key「Berth」、Berth 路徑（既有）或清單上的媒體庫（套件內）、`berth-*` 分類、勾選加入的站——不碰全域偏好與帳密（清單與能不能撤回見 §16.4）。套件內多出來的只有 bootstrap：Jellyfin 的管理員與初始設定、qBittorrent 與 Prowlarr 的介面登入、免密白名單（預置）、掛載的 Prowlarr API key；既有由使用者給憑證。
- **表單跟著那一台的狀態走**：
  - 套件內但已經初始化過（重裝保留了 config、精靈中途中斷）時，Jellyfin 已有管理員就改成「用管理員登入」、不再建立；qBittorrent / Prowlarr 已設過介面登入同理，不強迫再設。連線測試時就讀到它設過的帳號，頁 2 測試通過即完成，不必再按一次「套用」（Prowlarr 那一頁的站另算）。
  - 選既有而那台 Jellyfin 還沒跑過初始精靈時，一樣由擁有者建管理員、跑完它的初始設定（語言與地區、遠端存取在畫面上問）——它上面沒有任何人的帳號可以蓋掉。這是既有服務唯一的 bootstrap。
- compose 用 profiles（[ADR-0009](adr/0009-deploy-compose-and-env.md)）：`.env` 的 `COMPOSE_PROFILES=jellyfin,qbittorrent,prowlarr` 預設全起。
  - 選「既有」時精靈說出要從 `COMPOSE_PROFILES` 拿掉哪幾個（不叫人改 compose 檔）。那一行與停掉的指令照整份選擇在完成頁給一次；忘了拿掉也不致命。
  - 套件的容器名是 `berth-jellyfin` / `berth-qbittorrent` / `berth-prowlarr`（`berth` 維持；compose 服務名與 DNS 名不變）。同一台主機上既有的容器多半就叫 `jellyfin` / `qbittorrent` / `prowlarr`、用 8096 / 8080 / 9696 / 6881，沒有前綴時撞名會讓**整套**起不來（連 `berth`），所以加了前綴。撞 port 仍可能發生，只有撞到的那一個套件內容器起不來（實測見 §20.14）。
- 預置只補設定檔裡沒有的鍵（缺鍵才補，§20.7），已經有值的不動，之後使用者在各服務介面改什麼都行——包括關掉白名單，那時重啟補不回來，補法在 qBittorrent 的 WebUI。沒有「建議設定」可漂移：Berth 不寫也不看 qBittorrent 的全域偏好。精靈的 qBittorrent 頁會列出「已預置的項目」。
- 每顆按鈕都顯示「將會做什麼」與執行結果，失敗給出可複製的手動步驟。
- 各服務 API 的可行性與細節見 §20.7；手動選擇的慣例與既有服務的條件見 §20.14。

**「沿用 Jellyfin 帳密」**是精靈裡套件內 qBittorrent / Prowlarr 的介面登入上的一個勾選。

- **勾選**：
  - **不預設勾**：頁 1 帶了一組過來時那兩頁自動送、不出現欄位；沒帶時預設勾就等於再問一次 Jellyfin 密碼。
  - **只在精靈**：設定頁是一般的改帳密表單（目前的帳號、帳號、新密碼兩次、儲存）——頁 1 沒打過密碼，「沿用」在那裡讀起來像沿用上次的設定。
  - 勾選時帳號帶入擁有者的名字，Berth 先向 Jellyfin 驗證這組帳密正確再寫入；不勾就自設一組、密碼打兩次。
  - 擁有者的名字不合 qBittorrent 的規則時，頁 2 的勾選停用並說原因（不是勾了才紅）。
- **密碼只問一次**：
  - 頁 1 建套件內 Jellyfin 的管理員時預設勾「套件內 qBittorrent 與 Prowlarr 的介面也用這組」，密碼只留在精靈那一個瀏覽器分頁的記憶體裡（不寫 storage、不送給 Berth 存）。
  - 頁 2、頁 4 那一台還沒有介面登入時自動以沿用送出，不出現密碼欄；設好之後只說「已沿用 Jellyfin 帳密（擁有者）」與「改用另一組」。
  - 重新整理、沒勾、頁 1 是登入既有的管理員（沒有「設一組」）、或 Jellyfin 不再收那一組時，那兩頁照舊問介面登入：沒帶的是自設的三格，勾起「沿用」就只打一次 Jellyfin 密碼；Jellyfin 不再收那一組時欄位打開在「沿用」，打的是新的 Jellyfin 密碼。
- **「已沿用」照後端記的 `web_ui_login_reuses_owner`**，不看帳號（「改用另一組」只換密碼時帳號一樣），也不看這個分頁最後一次設下的是不是帶過來的那一組（重新整理之後同一個狀態會變成「帳號：擁有者」＋「更換登入」）。手動勾「沿用」設的也說已沿用。
- **頁 1 的帳號與密碼不合 qBittorrent 的規則時頁 1 就擋**：「也用這組」邊打邊停用並說原因，帶不過去，不等到頁 2 才說不能沿用（同一件事在頁 2 又被表單的預設勾選說一次）。只有 qBittorrent 不合時也整格停用，不拆成只給 Prowlarr——那一格答應的是「兩台都用這組」，頁 4 照樣勾得起「沿用」。
- **完成頁**照 `web_ui_login_by_berth`（Berth 記著那一組的密碼雜湊）說登入是精靈設的、那一台原本就有的（重裝保留 config，並說忘了去「設定 → 該服務」的「介面登入」換一組），或還沒設。精靈設的那一組是沿用 Jellyfin 帳密時（`web_ui_login_reuses_owner`，寫進去的那一刻記下）直接說「與 Jellyfin 同一組」。不看登入那一條纜繩——Prowlarr 的「加入」每次以不帶登入重算它，Berth 設好的也記成 `skipped`。
- **Berth 不存這兩組介面密碼的明文**，只記帳號與加鹽雜湊，夠比對「已經是這一組」。勾了沿用時那就是 Jellyfin 的密碼，存明文會讓資料庫裡留下擁有者的明文密碼，而 Berth 不存；Berth 連套件內 qBittorrent 靠免密白名單，本來就用不到它。

### 16.4 既有服務的接入規則【決定】

「既有」由使用者在該服務那一頁選（§16.3）；本節的條件在「既有」選項旁說明。

允許接入既有服務；NAS 使用者是主要客群，Seerr 與 Sonarr 也都支援。問題只有一類：路徑與檔案系統邊界。

**接管＝只建立與管理 Berth 擁有的物件**（[ADR-0013](adr/0013-berth-manages-only-its-own-objects.md)）。套件內與既有是同一條，差在套件內由 Berth 讓服務有人登得進去（§16.3）。理由是兩件實際發生過的事：使用者自己的 Prowlarr 被覆寫登入、既有 qBittorrent 的全域 `save_path` 被改成 Berth 的目錄；Sonarr / Radarr 對下載器同樣只用自己的分類、不碰全域。Berth 擁有的物件都是獨立的一件，刪掉它不動使用者原有的任何東西：

| 物件 | 套件內 | 既有 | 在 Berth 能撤回嗎 | 撤不回時怎麼辦 |
| --- | --- | --- | --- | --- |
| Jellyfin 管理員帳號 | 那一台還沒初始化時建 | 只在那一台還沒初始化時建（唯一的例外） | 不能 | Jellyfin 的使用者管理 |
| Jellyfin 語言、地區、遠端存取 | 還沒初始化時設（跟 UI，不開遠端） | 還沒初始化時設（畫面上問） | 不能 | Jellyfin 控制台 |
| Jellyfin 伺服器名稱 | 還沒初始化時設成「Berth」 | 不設（初始設定照跑、不帶名稱：Jellyfin 清成空字串、報 hostname，§20.9） | 不能 | Jellyfin 控制台「一般」 |
| Jellyfin API key「Berth」 | 建 | 建 | 不能（Berth 不刪）；在 Jellyfin 刪掉之後 Berth 偵測得到，請你重新登入換一把 | Jellyfin「API 金鑰」頁 |
| Jellyfin 媒體庫 | 建精靈清單上的 | 只建頁 3 勾了「新建一個媒體庫」的那一個：`<library root>/<slug>`，與套件內同一條路徑，同名的已經在就不再建；伺服器上所有使用者都看得到，所以預設不勾。名稱只差大小寫、或資料夾已經是別的媒體庫的路徑時擋下 | 不能；套件內已建的在 Berth 裡鎖住，既有那一台建好之後就是清單上的一個媒體庫 | Jellyfin 刪 |
| 媒體庫上的 Berth 路徑 | — | 頁 3「建立並檢查」時加；類型對得上的媒體庫（電影、劇集）預設勾選、預設寫入目標是這一條。**同一個資料夾不給第二個媒體庫**：兩個名字算出同一個 slug 時（`TV Shows` 與 `TV-Shows`），後加的那個失敗（`path_taken`），slug 規則不改 | 不能；頁 3 的檢查失敗也留著 | Jellyfin 媒體庫設定移除 |
| 請 Jellyfin 去看 Berth 寫的路徑 | 同右 | 入庫後通知那幾條路徑（`POST /Library/Media/Updated`）；反查還沒找到時只刷新那條 Route 的媒體庫；**Berth 的路徑 Jellyfin 還沒列出過任何東西時（空的媒體庫第一次入庫、剛加上 Berth 路徑的媒體庫），跑整台的「掃描媒體庫」排程任務，你其他的媒體庫也會一起被掃**——只有它建得出那個路徑（§20.1）；路徑還沒被列出之前，反查每一次沒找到都會再請一次（它還在跑時再請是空操作）。Issue 的「重新掃描媒體庫」照同一條 | 不留下東西 | — |
| qBittorrent 免密白名單 | 預置（容器啟動前，只放 Berth 的 IP） | 不碰 | —；換走套件內那一台時換台框列出它與關法 | `qBittorrent.conf`，或它的 WebUI「選項 → WebUI → 驗證」取消勾選（重啟不會再打開：預置腳本只補沒有的鍵） |
| qBittorrent 全域偏好 | 不寫 | 不寫 | — | — |
| qBittorrent 介面登入 | 設 | 不碰 | 只能再設一組蓋過 | qBittorrent 偏好 |
| `berth-*` 分類與它的 complete / incomplete 目錄 | 建 | 建；**送單與 Route 檢查都先 `ensure_category`，你在 qBittorrent 刪掉的會照 Route 的路徑重建**（路徑開在分類上，沒有它 torrent 就落到全域的儲存路徑） | 刪 Route 不刪分類；換一台時換台框可勾選一併移除舊那台上**空的**，確認換台才移除，目錄不刪 | 先刪 Route（之後不再重建），再在 qBittorrent 刪分類 |
| Berth 送出的 torrent，帶 tag `berth` | 送單時加 | 同左 | 刪 Job 時勾「從 qBittorrent 移除」：只移除 torrent，**不刪檔**（§9.2） | qBittorrent 刪 torrent；tag 讓你在它的介面上篩出 Berth 放的 |
| 探測 torrent、探測檔 | 暫時，自清 | 同左 | 自清（Berth 中途崩潰、或答完之後移除那一下 qBittorrent 斷線時可能殘留：停住、沒有分類） | 手動刪 |
| Prowlarr 站 | 加勾選的 | 加勾選的 | 套件內可單站移除 **Berth 加的**（`SetupIndexer.added_sites`；沒有紀錄的照實說、不給移除；使用者自己加的公開站也不給）；既有不移除 | Prowlarr 刪 |
| Prowlarr 介面登入 | 設 | 不碰 | 只能再設一組蓋過 | Prowlarr 設定 |
| Jellyfin 的裝置「Berth」（DeviceId `berth-server`） | 登入過 Berth 的每一位 Jellyfin 使用者一筆：Berth 沒有自己的密碼，登入是交給 Jellyfin 驗，Jellyfin 為每次登入發權杖、記一筆裝置；同一位再登入是換掉自己那一筆（§20.22） | 同左 | 不能 | Jellyfin 控制台「裝置」刪 |
| TMDB | 不寫 | 不寫 | — | — |

探測檔的位置：

- 頁 2：在 `/data`，校驗不完的探測 torrent。
- 頁 3：在分類路徑。
- 頁 1 給既有 Jellyfin 的 `ValidatePath` 看的探測檔：在 `/data`，沒有 torrent。

「不用 Berth 了」要手動清的寫在 `docs/guide/uninstalling.md`。

**換一台 qBittorrent / Prowlarr 時**：

- **確認框**列出 Berth 在原本那一台擁有的物件：
  - `berth-*` 分類各有幾個 torrent。
  - Berth 加進去的站（Berth 加站時記下 `definitionName` 與站名，`SetupIndexer.added_sites`；沒記到的列不出）。
  - Berth 設的介面登入（只有 Berth 記著雜湊的那一組）。
  - 使用者自己的分類與站不列。原本那一台是套件內 qBittorrent 時多列預置的免密白名單，說它在 `qBittorrent.conf`、在 WebUI 怎麼關。
  - 連不到那一台時列 Berth 記得的（分類取自 Route、站取自那份紀錄），照實說確認不了現況。
- **分類裡的 torrent 留在原本那一台**（做種的照樣做種、下載中的照樣下載），Berth 換台之後不再追蹤它們、已入庫的檔案不受影響，那一台關掉做種就停——換台框照數目說（連不到時不說數目）。換台之後，送進原本那一台、已入庫的 Job 詳情說「做種的 torrent 在原本那一台」：讀最後一次 `submitted` 事件記下的 `client`，與現在那一台不同才說；不知道的不說。
- **還沒下完的 Job 例外**：poller 在新那一台上找不到它們的 torrent，照 plan §3.1 各開一件 `client_removed`。換台框照實說並列出名字（`in_flight`：poller 每一輪到 qBittorrent 裡找的那幾種狀態，讀 Berth 自己的 Job，連不到原本那一台也列得出），那件 Issue 的「重新送單」送到的就是新那一台。換台本身不改它們的狀態。
- **設定頁「改位址」從一台既有換到另一台既有也是換台**（存下的位址不同就是，`ServiceChoice.is_at`；存之前去掉頭尾空白與結尾的 `/`）：同一份說明與清單就地加在表單裡，「測試連線」就是確認。同一台 qBittorrent 只是 IP 換了，Berth 一樣當成換台——qBittorrent 沒有認得出同一台的方法（§20.2〈同一台 qBittorrent 認不出來〉）。
- **能移除的只有空的 `berth-*` 分類**；站與登入只列出——站可能有人在用、登入拿掉就沒人登得進去。
- **移除是換台框裡的勾選（預設不勾），跟著確認換台一起做**（`POST /setup/services/qbittorrent` 的 `remove_empty_categories`）：
  - 在新那一台測過之後、存下之前移除，確認時重數。
  - 取消就什麼都不動；換成既有時新那一台測不過也不動（套件內照舊先存再測，選了就換過去）。
  - 勾了而原本那一台沒答上來，整個換台不做（502 `categories_not_removed`），取消勾選再換一次就只換台。
- **換成功之後 Route 自動重查**：所有 Route 的檢查作廢，健康頁的媒體庫路徑那一格是「要重新檢查」而不是「已繫上」。
  - 設定 → qBittorrent 在新那台測過之後自動跑一次「全部重新檢查」（分類建在新那台、探針重問），說「正在重新檢查 N 條 Route」、逐條進度、跑完說幾條過了。
  - 結果出來之前送單照舊：還沒檢查完的放行（送單自己建分類），紅了的才擋。探針從沒問過的 Route 同樣不算「已繫上」。

**閘門**是 `tests/integration/test_setup_owned_writes.py`：整個精靈經 API 跑套件內一輪、既有兩輪（Jellyfin 初始化過與還沒），三台替身收到的每一個寫入都要對得上「Berth 擁有的物件 + 套件內的 bootstrap」那張白名單。

- 既有那一輪的 bootstrap 只放行那台 Jellyfin 還沒初始化；建媒體庫只放行勾了的、在 library root 底下的（沒勾也建、建在 root 外各有變異測試）。
- **執行期另一輪**經 services 走送單、缺檔按「重新校驗」、下載完成、入庫、反查（全庫掃描與只刷新媒體庫兩條）、六次用完按「重新掃描媒體庫」、刪 Job，同一張白名單：
  - 送單只能是 `berth-*` 分類、表單上的 tag 只有 `berth`、路徑交給分類。
  - 重新開始、校驗、移除只能對 Berth 送的（或探測的）torrent，移除不刪檔。
  - 通知的路徑在 library root 底下、只刷新 Route 的媒體庫、排程任務只能是「掃描媒體庫」。
  - 每一條都有紅綠雙向的變異測試，tag 與刪檔另各有一條走完整流程的。
  - 套件內 Prowlarr 的移除只放行這一輪 Berth 加的站，不寬於程式（`added_sites`）。
- **不在範圍**（閘門只看得到 Berth 經三個服務的 adapter 送出的寫入）：預置的免密白名單、掛載的 key、探測檔的自清與 Berth 對 `/data` 的磁碟操作；Jellyfin 的裝置紀錄（登入是讀）；標已看（使用者自己按、寫他自己的觀看紀錄）；換台時移除空分類那一顆（白名單列只用合成的寫入驗，行為由 `test_setup_leftovers.py` 守）。
- 頁 1、頁 3 問 Jellyfin 的 `ValidatePath` 是讀（POST 但不留東西），白名單不放行任何東西；閘門另外斷言既有那一輪頁 1 真的問了 `/data`。

**條件與規則**：

- **唯一的硬規則**：Berth、qBittorrent、Jellyfin 三個容器在**同一台主機**、把同一個宿主父目錄掛在**相同的容器路徑**，且下載目錄與媒體庫目錄都在它底下（TRaSH 的單一 `/data` 掛載，§20.14）。
  - Berth 的 incomplete / complete 根目錄固定在 `/data/torrent/{incomplete,complete}`（沒有設定項），所以 Berth 與 qBittorrent 的共用掛載要掛在 `/data`；媒體庫路徑讀自 Jellyfin。
  - **這是既有 qBittorrent 與 Jellyfin 最關鍵的條件**：在另一台 NAS 上的接不上；只掛了 `/downloads`、`/tv` 的，**多加一條 `${DATA_ROOT}:/data` 就好，原本的掛載不動**——Berth 只在 `/data` 底下讀寫，叫人把下載目錄搬過去反而讓舊 torrent 找不到檔案。
  - 「既有」選項旁說明這個條件：容器路徑只能是 `/data`、`DATA_ROOT` 要建得了硬鏈接；缺某類型的媒體庫時頁 3 勾了才建。
  - 媒體庫與路徑泊位的探測檔 / 硬鏈接檢查失敗時，給那一台要多加的那一條（compose、`docker run` 與 Unraid 模板「Add another Path」三種寫法）。**宿主那一側是 Berth 的 `DATA_ROOT` 真正的值**：compose 把 `.env` 的原字串傳成 `HOST_DATA_ROOT`，Windows 的反斜線換成 `/`，相對路徑（`./data`）說它相對於 Berth 的 docker-compose.yml、要換成絕對路徑。
  - **少了 `/data` 提早說**：qBittorrent 在頁 2 測連線時；既有 Jellyfin 在頁 1 成為擁有者、Berth 拿到 key 之後（與頁 3 同一種探測檔加 `ValidatePath`；不擋頁 2）。之後每次重新測試、設定頁換位址也問，看不到就不存新位址——與「測過才存」同一條。
- **既有服務要給的東西各不相同**（§20.14）：
  - Jellyfin：位址 + **管理員**帳密（不是管理員就拒絕）；Berth 以它登入、自己建 API key。版本下限 12.0，**測連線時就擋**。擁有者成立之後只能換到**同一台**的另一個位址（ServerId，§20.15）。還沒初始化的那一台由擁有者表單建立管理員，語言與地區、遠端存取在畫面上問（預設 UI 語言、不開遠端存取）。
  - qBittorrent：位址 + WebUI 帳密。版本下限 4.4（Web API 2.8.4）。5.2 起它有 API key（`Authorization: Bearer`），之後可當第二種接法，目前不做。
  - Prowlarr：位址 + **API key**（Prowlarr 的「設定 → 一般 → 安全性」）；它的 API 只收 API key，帳密只給瀏覽器登入。Berth 用使用者已有的索引站。
    - **一站都沒有不算完成**：可以在 Prowlarr 加站後重新讀取、在精靈測試推薦的公開站並按一次加進它（與套件內同一顆「測試推薦站，加入通過的」，畫面列出站名與它的位址），或之後再說。
    - Berth 不移除它的站、不設它的登入。
    - 版本下限 1.3.2（卡住它的是匿名的 `/ping`，§20.14）；版本從 `system/status` 讀，比 1.3.2 舊、沒有 `/ping` 的那一台也說得出版本；key 錯說「API key 不對」而不是連不上。
  - 三個服務的下限都寫在「既有」選項旁，版本太舊時精靈與健康檢查說出目前版本與下限。
- **容器裡的 `localhost`**：使用者填 `localhost` / `127.0.0.0/8` / `::1` 時，位址欄下就地提示（只提示、不擋：`network_mode: host` 的部署填 `localhost` 是對的；測試不過時的補法也是同一句，那時位址欄下的提示收起來、不說兩遍）。
  - Berth 在容器裡，那指的是 Berth 自己；要填宿主的區網 IP 或 `host.docker.internal`（Docker Desktop 內建；Linux 由 compose 的 `extra_hosts: ["host.docker.internal:host-gateway"]` 提供），服務要監聽 `0.0.0.0` 而不是 `127.0.0.1`（§20.14）。
  - rootless Docker 上 `host.docker.internal` 連不到宿主，只有區網 IP 會通，提示照說（§20.14）。
- **既有 Jellyfin 不搬媒體庫**：Jellyfin 的項目 ID 由路徑算出，改路徑等於全部變成新項目、觀看紀錄歸零。
  - 做法是用 Jellyfin 的「一個媒體庫多個路徑」：Berth 按鈕以 `POST /Library/VirtualFolders/Paths` 為既有媒體庫**加**一個 Berth 用的路徑（§20.7），Route 指向新路徑；舊媒體原地不動，在 Berth 只是 unmanaged 檔案。
  - 缺某類型的媒體庫時，頁 3 勾了「新建一個媒體庫」Berth 才建一個新的（`POST /Library/VirtualFolders`，與套件內同一條路徑），舊的一個都不動。
  - 送出前先寫探測檔問 Jellyfin 看不看得到：它對加不上的路徑只回 404，說不出原因；看不到就說「Jellyfin 看不到 <路徑>：它沒掛 <共用目錄>」、收回剛建的目錄。
  - 多個媒體庫逐個試、逐個回報；畫面上「看不到」合併成一則、列出受影響的媒體庫——那是整台沒掛 `/data`，補法只給一次。
- **既有 qBittorrent 不搬舊種、不改全域偏好**（套件內那一台的全域偏好同樣不寫）：使用者多加一個掛載，Berth 用自己的 `berth-*` category 與新的 save path；舊 torrent 留在原目錄，Berth 忽略非自己分類的 torrent。
  - 全域的 save path、temp path、autoTMM 一個都不寫、也不列在精靈上（Sonarr / Radarr 對下載器同樣只用分類）——改了它們，使用者不經 Berth 加的 torrent 就會落進 Berth 的目錄，而它們沒有一個影響 Berth。
  - 全域 autoTMM 關閉無妨，Berth 送單時逐個 torrent 指定 `autoTMM=true`。
  - 全域未完成目錄沒開無妨，Berth 的分類各自帶 `downloadPath`；temp path 未啟用不警告，因為完成看的是 qBittorrent 回報的 progress / completion_on / state，不靠它。
  - 沒有自己未完成目錄的 Berth 分類（較早建的）照舊跟著全域設定下載、不算衝突；有而且不同才照衝突規則處理、不覆寫。
- **健康檢查會擋下的情況**：
  - qBittorrent 回報的**分類**路徑（save path 與分類自己的未完成目錄）在 Berth 看不到——全域的預設 save path 不看，兩種來源都一樣。
  - qBittorrent 讀不到 Berth 寫進分類路徑的探測檔。
  - Route 的寫入目標在 Berth 看不到（媒體庫的其他路徑不驗：Berth 只在寫入目標底下讀寫，舊的 `/movies` 看不到不礙事）。
  - 兩者在 Berth 內是不同掛載（`link()` 回 `EXDEV`）。
  - qBittorrent 低於 4.4；Prowlarr 低於 1.3.2。
  - Jellyfin 低於 12.0（說出目前版本，附升級注意：先完整備份、移除第三方插件、升級後完整掃描、不能降級，§20.9）。
  - 媒體庫掛 TVDB 插件（警告，一件 `library_uses_tvdb` Issue，§9.1）。
  - 每項附「哪個容器少了哪個掛載」的 compose 修正片段，**片段對著要改的那一台**：寫入目標看不到、Jellyfin 看不到探測檔是 jellyfin；qBittorrent 讀不到探測檔是 qbittorrent；Berth 看不到 qBittorrent 報的路徑與 `EXDEV` 才是 berth。既有服務的片段是「你原本那一份」要多加的一條 `/data`（compose、`docker run -v` 與 Unraid 模板，帶著 `DATA_ROOT` 的值），原本的掛載不動。
- **跨主機驗證**：Berth 在 Route 目標寫一個探測檔，再以 `POST /Environment/ValidatePath` 請 Jellyfin 確認看得到同一路徑（§20.7）；Jellyfin 在別台機器而路徑不一致會立刻現形。
- **不支援**：Jellyfin 10.x（只支援 12 以上，[ADR-0002](adr/0002-jellyfin-12-minimum-pinned-image.md)）；既有 qBittorrent 或 Jellyfin 與 Berth 不在同一台主機、或沒有把 Berth 的 `DATA_ROOT` 掛在容器路徑 `/data`（硬鏈接做不到）；remote path mapping（不做，§18）。

---

## 17. 里程碑（tracer bullet）

每個里程碑結束時 repo 都可運作、可部署。已驗收的里程碑封存在 `docs/archive/<里程碑>.md`；M6、M6.5、M7 尚未驗收。

| 里程碑 | 內容 | 驗收 |
| --- | --- | --- |
| **M0 骨架**（已驗收，[`docs/archive/m0.md`](archive/m0.md)） | §20.6 的實驗、compose 範本（profiles）與最小預置、精靈、Route 建立、健康檢查 | 在乾淨的 Linux 與 Windows Docker Desktop 上 `docker compose up` 後只操作 Berth 即完成設定，四項健康檢查綠燈；另以「既有 Jellyfin + 套件內其餘服務」走一次；實驗結論寫回本文件 |
| **M1 手動全流程**（已驗收，[`docs/archive/m1.md`](archive/m1.md)） | 探索 → 詳情 → 索引站搜尋 → 送 qBittorrent → 輪詢 → 規則 planning → 硬鏈接 → 掃描 → 可播放 + 深連結；Job 時間線；benchmark | 一部美劇一季、一部動漫一季、一部電影，不經人工入庫並在 Jellyfin 正確顯示 |
| **M1.5 媒體庫瀏覽**（已驗收，[`docs/archive/m1.5.md`](archive/m1.5.md)） | 媒體庫與 Media 詳情像 Jellyfin 那樣瀏覽（§12、§13） | 不開 Jellyfin Web 就能找到要看的那一集、看到進度並標記已看；Jellyfin 不讓這位使用者看的媒體庫，在 Berth 也看不到 |
| **M2 修正與對帳**（已驗收，[`docs/archive/m2.md`](archive/m2.md)） | Review Queue、Unmatched 指派、rematch、Reconciler、刪除範圍、重新入庫、`berth rebuild-ledger`（§16.2）、Job 詳情頁 | 刪掉 library 後可一鍵重建；Issue 表對三種人為破壞都能偵測；medium 自動入庫可一鍵撤銷；`user` 看不到也按不到審核與刪除 |
| **M3 RSS**（已驗收，[`docs/archive/m3.md`](archive/m3.md)） | Mikan、Nyaa、acg.rip adapter、RSS Series 自動綁定、排除條件、去重、補舊集、一次性連結（§15） | 聚合 feed 加一個搜尋 feed 全自動追完，中途訂閱的補齊舊集 |
| **M4 巡檢與通知**（已驗收，[`docs/archive/m4.md`](archive/m4.md)） | 每日程式檢查、每週週報；`events` 訂閱者、channel adapter（Discord）、每人的訂閱設定（§14） | RSS 命中 → 入庫 → Jellyfin 可見的全程，手機收到「正在下載」與「可以看了」；週報說得出這週入庫與修正了什麼 |
| **M5 AI 地基與對話 agent**（已驗收，[`docs/archive/m5.md`](archive/m5.md)） | 命令登錄表與執行器、Proposal、provider、防護與記帳、側面板對話（工具、確認卡、外部資料、skills、壓縮、斜線指令）、觀測頁（§6.10、§14） | 側面板說「下載 Re:Zero 全系列」得到逐列可勾的總覽卡，按確認後送單；「為什麼這集沒入庫」答得出卡在哪；AI 不能在沒人確認下執行不可逆的命令；重啟之後舊卡片按得下去；關掉 AI 時與 M4 相同 |
| **M5.5 新番與導覽**（已驗收，[`docs/archive/m5.5.md`](archive/m5.5.md)） | 頁首收斂成五項加帳號選單、新番時間表、追更頁、訂閱作品遲到的提醒；助理的模型清單、搜尋結果、推理、對話清單；審核佇列減量（細節在 plan §11.6b） | 找得到當季新番並一鍵走到訂閱；地上波先行的集數自動入庫、不進審核，升級後不必手動重新規劃；訂閱的作品播出滿兩天沒入庫會收到一件 Issue，說得出卡在哪（字幕組沒發、下載停滯、入庫失敗都算，已在等你處理的不重複開）；接了 Discord 的管理員收到寫明作品與集數的私訊，沒接的在追更頁看得到提示；字幕組沒遲到（下一個 cour 沒訂）不誤報；關掉 AI 也完整可用；設定頁存檔前選得到該端點的模型，換瀏覽器接得回對話，看得到推理並設得了程度 |
| **M5.6 AI 對話精簡**（已驗收，[`docs/archive/m5.6.md`](archive/m5.6.md)） | 確認卡同一部作品只選一次 Route、Route 由伺服器定；種子搜尋的 `contains`、媒體庫給集數、`rss.subscribe` 一支包辦訂閱；共同規則進系統指示，skills 5 → 3、工具 22 → 18；只有一季的作品整季缺時問得到動畫站（細節在 plan §11.6c） | 「下載想吃掉我的非人少女、要喵萌奶茶屋繁中單集」種子搜尋 6 次以內（和改動前的基準比），卡片 Route 只選一次；只說「找」時不搜種子；其他情境的品質不比改動前差 |
| **M6 人工接管開關** | 決定點的人 / AI 開關、第一批背景 AI 任務、卡住的 Job 開 Issue、AI 評估、AI 活動與撤銷；先修 M5.6 遺留（§6.10、§14，細節在 plan §11.7） | 每種任務的 AI 評估套用的錯 0 件、交回人的比例 ≤ 5%；benchmark `auto_wrong` 不升、review 比例下降；以作品訂閱挑得到要的那一季；關掉 AI 時與 M4 相同 |
| **M6.5 Issue 與巡檢交給 AI** | Issue 的各型別、每週巡檢交給 AI、修正回流寫回 RSS Series、別名與排除條件（§14，細節在 plan §11.7b） | 一件 `library_link_missing` 不經人修好；刪 complete 的請求停在 Proposal；週報說得出 AI 修了什麼 |
| **M7 Discord 與 MCP** | M4 的 Discord bot 接上同一個核心、確認卡帶按鈕、個人 API token、MCP server（§14、§16.2） | 手機上收到通知、回一句話、按確認之後完成；Claude Code 經 MCP 查得到本週入庫 |
| 之後 | RSS 的 offset 建議（§15〈offset 建議〉，看第一批改正的頻率決定）、Jellyfin Webhook（§9.5，社群回報不可靠）、字型與字幕解壓、多使用者審批、非影片媒體 | — |

---

## 18. 明確延後或不做

| 項目 | 處置 | 理由 |
| --- | --- | --- |
| complete / incomplete 鏡像 library 結構 | 不做 | §4.2 |
| library 內的 `unmatch` 資料夾 | 不做，改為 UI 列表 | §7.4 |
| 內嵌播放器 | 延後（媒體庫瀏覽照樣跳到 Jellyfin 播放） | §12 |
| AI 解析 | M5 起；背景任務在 M6 | 先有 benchmark 才能評估 |
| 品質升級自動替換 | 不做 | 版本並存（Jellyfin 12 原生合併）已滿足；升級邏輯是 Sonarr 最複雜的部分 |
| remote path mapping | 不做 | 強制同路徑掛載更簡單、更不易錯；既有服務的條件在精靈講清楚（§16.4） |
| 多 provider（TVDB / AniList） | 延後 | §10 |
| 字型安裝、字幕解壓、OST 入音樂庫 | 延後 | 非核心流程 |
| BDMV 原盤 | 只辨識不處理 | 需要 Jellyfin 端特殊結構 |
| 多使用者審批、配額 | 延後 | 角色模型已預留 |
| 通知 | M4 | §14、§17 |
| AI 助理（側面板、外部對話、MCP） | M6 / M7 | §14、§17；M5 的 AI 核心先到 |

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

外部事實搬到 `docs/research/facts-*.md`，節號不變；程式碼與文件裡的「brief §20.x」照下表找。

| 節 | 檔案 | 主題 |
| --- | --- | --- |
| §20.1 | [`docs/research/facts-jellyfin.md`](research/facts-jellyfin.md) | Jellyfin 命名、extras、字幕、多版本、API |
| §20.2 | [`docs/research/facts-qbittorrent-docker.md`](research/facts-qbittorrent-docker.md) | qBittorrent Web API 與硬鏈接 / Docker 限制 |
| §20.3 | [`docs/research/facts-metadata-parsing.md`](research/facts-metadata-parsing.md) | Metadata provider 與動漫 ID 對應 |
| §20.4 | [`docs/research/facts-metadata-parsing.md`](research/facts-metadata-parsing.md) | 解析先例與真實 torrent 內容 |
| §20.5 | [`docs/research/facts-metadata-parsing.md`](research/facts-metadata-parsing.md) | 名稱衝突檢查 |
| §20.6 | [`docs/research/facts-metadata-parsing.md`](research/facts-metadata-parsing.md) | 實作前必做的實驗【研究】 |
| §20.7 | [`docs/research/facts-qbittorrent-docker.md`](research/facts-qbittorrent-docker.md) | 開箱即用所需的 API 與 Windows Docker 事實 |
| §20.8 | [`docs/research/facts-jellyfin.md`](research/facts-jellyfin.md) | 媒體庫瀏覽用的 Jellyfin API（M1.5 前置） |
| §20.9 | [`docs/research/facts-jellyfin.md`](research/facts-jellyfin.md) | Jellyfin 12（2026-09-15 查證） |
| §20.10 | [`docs/research/facts-search-rss.md`](research/facts-search-rss.md) | Sonarr 怎麼替一集組查詢（2026-09-19 查證） |
| §20.11 | [`docs/research/facts-search-rss.md`](research/facts-search-rss.md) | 發佈時間：索引站與 RSS（2026-09-24 查證） |
| §20.12 | [`docs/research/facts-search-rss.md`](research/facts-search-rss.md) | RSS 來源的欄位（2026-09-25 查證，M3 票 07） |
| §20.13 | [`docs/research/facts-search-rss.md`](research/facts-search-rss.md) | 公開站的請求限制：Prowlarr、Sonarr、AutoBangumi 的慣例（2026-09-26 查證，M3 票 20） |
| §20.14 | [`docs/research/facts-wizard.md`](research/facts-wizard.md) | 精靈手動選擇的慣例與既有服務的條件（2026-09-29 查證） |
| §20.15 | [`docs/research/facts-jellyfin.md`](research/facts-jellyfin.md) | 「同一台 Jellyfin」怎麼認：ServerId（2026-09-30 查證＋實測，M4 票 18） |
| §20.16 | [`docs/research/facts-search-rss.md`](research/facts-search-rss.md) | 搜尋結果怎麼用年份與類型篩：Radarr 與 Sonarr（2026-10-07 查證，M4 票 49） |
| §20.17 | [`docs/research/facts-qbittorrent-docker.md`](research/facts-qbittorrent-docker.md) | 部署檔的 release 附件與「最新版」連結（2026-10-08 查證，M4 票 56） |
| §20.18 | [`docs/research/facts-qbittorrent-docker.md`](research/facts-qbittorrent-docker.md) | preseed 腳本內嵌進 compose：`configs.content` 加 `mode`（2026-10-09 查證＋實測，M4 票 70） |
| §20.19 | [`docs/research/facts-search-rss.md`](research/facts-search-rss.md) | 搜尋的年份、片名裡的 `&` 與成人分類（2026-10-10 查證，M4 票 69） |
| §20.20 | [`docs/research/facts-search-rss.md`](research/facts-search-rss.md) | 搜尋結果怎麼說出「為什麼不像這部作品」：Sonarr 的互動搜尋（2026-10-10 查證，M4 票 83） |
| §20.21 | [`docs/research/facts-search-rss.md`](research/facts-search-rss.md) | 季的搜尋記號：`Season N` 與 `SNN` 實跑比較（2026-10-13 實測，M4 票 84） |
| §20.22 | [`docs/research/facts-jellyfin.md`](research/facts-jellyfin.md) | Berth 登入 Jellyfin 留下的裝置（2026-10-14 查證，M4 票 66） |
| §20.23 | [`docs/research/facts-ai-discord.md`](research/facts-ai-discord.md) | Discord bot 私訊（2026-10-21 查證，M4 拆票；同日 M4 票 121 實測） |
| §20.24 | [`docs/research/facts-ai-discord.md`](research/facts-ai-discord.md) | pydantic-ai 的確認卡與 Vercel AI SDK 串流（2026-10-27 實測，M5 prototype） |
| §20.25 | [`docs/research/facts-qbittorrent-docker.md`](research/facts-qbittorrent-docker.md) | HTTP 下的瀏覽器與發版的閘門（2026-10-30 查證與實測，0.4.1 之後） |
| §20.26 | [`docs/research/facts-ai-discord.md`](research/facts-ai-discord.md) | 助理的工具清單、推理與模型清單（2026-11-01 查證與實測，M5.5 規劃） |
| §20.27 | [`docs/research/facts-metadata-parsing.md`](research/facts-metadata-parsing.md) | 地上波先行配信與 TMDB 的播出日（2026-11-01 查證，審核佇列調查） |
| §20.28 | [`docs/research/facts-metadata-parsing.md`](research/facts-metadata-parsing.md) | 只有一季的作品：整季缺時不接季記號（2026-11-07 實測，M5.6 票 02） |
| §20.29 | [`docs/research/facts-metadata-parsing.md`](research/facts-metadata-parsing.md) | 以作品訂閱時選不出「第幾季」（2026-11-07 實測，M5.6 票 11） |
