# S2 實跑筆記（全部接既有服務，先錯後對）

Berth：main 107708c 的 image `berth:audit-107708c`，容器 `berth-s2`，http://localhost:8384。
截圖在 `docs/research/usability-audit-2026-10-07/s2-NN-*.jpeg`（共 28 張）。

## 環境偏差
- 兩套不能並存的觀察：官方 compose 寫死 `name: berth`、`container_name: berth`、網路名 `berth`、子網 172.28.0.0/16。改副本 `C:\Users\Roxy\berth-audit3\docker-compose.yml`（原檔存為 docker-compose.orig.yml）：
  `name: berth-s2`、`container_name: berth-s2`、網路 `name: berth-s2`、子網 172.31.0.0/16、ip_range 172.31.1.0/24、berth IP 172.31.0.2、image 改 `berth:audit-107708c`。
  - 任務指定 172.29 被別人的 `fx-net` 佔了（`cannot create network ... overlapping IPv4`），改 172.31。
  - qbittorrent 服務的 BERTH_IP 錨點也跟著改（未啟用，COMPOSE_PROFILES 為空）。
- `.env`：COMPOSE_PROFILES=（空）、DATA_ROOT=./data、CONFIG_ROOT=./config、BERTH_PORT=8384。
- 既有組 `mine3`：`C:\Users\Roxy\berth-audit3-existing`，jellyfin 47096、qbittorrent 47080、prowlarr 47696；一開始都沒掛 /data。設好 Jellyfin 管理員 + 非管理員 + 兩個媒體庫（電影 /movies、節目 /tv，CollectionType movies / tvshows），qBittorrent 改自己帳密 + save_path /downloads，Prowlarr 表單登入 + YTS。帳密在該目錄 CREDENTIALS.md。
- 修 mine3-qbittorrent / mine3-jellyfin 時我在 `mine3` compose 加的行（Windows，使用者典型寫法）：`- C:/Users/Roxy/berth-audit3/data:/data`。第一次用反斜線寫進 YAML，是我 sed 把反斜線吃掉造成 `too many colons`，不是 Berth 的問題；改正斜線後可用。
- 安全事項：playwright 的 `browser_run_code_unsafe` 把整段程式碼（含 TMDB key）回顯在工具輸出裡，這次的工具輸出已含 key 明文（.env 本來就有）；腳本已刪，key 沒寫進本筆記與截圖（欄位是 password 遮罩）。主對話請留意 transcript 裡有一份。
- 另：舊的 `.playwright-mcp` 是 gitignored。

## 逐頁動作計數（成功路徑，不含故意的錯誤）
| 頁 | 打字欄位 | 必按按鈕 | 畫面上可見按鈕（約） | 備註 |
|---|---|---|---|---|
| 1 Jellyfin | 3（位址、帳號、密碼） | 4（選「既有」radio、測試連線、登入、前往下一個泊位） | 約 8（含 2 個複製、顯示、改位址…） | 測試連線通過後才長出登入表單；登入成功即自動存、自動建 API key |
| 2 qBittorrent | 3（位址、帳號、密碼） | 3（選既有、測試連線、前往下一個泊位） | 約 7 | 沒掛 /data 時在此紅（見下）；補完只需再按一次「測試連線」，欄位內容保留 |
| 3 媒體庫路徑 | 0 | 3（勾 2 個媒體庫 = 2、建立並檢查、前往下一個泊位） | 約 6 | 預設寫入目標就是「新的 Berth 路徑」，不用選 |
| 4 Prowlarr | 2（位址、API key） | 3（選既有、測試連線、前往下一個泊位）；加推薦站另按 測試全部、勾、加入 | 約 18 | 不加站可「之後再說」 |
| 5 TMDB | 1 | 2（測試 TMDB、前往下一個泊位） | 4 | |
| 6 完成 | 0 | 1（完成設定） | 5（3 個外連 + 完成 + 上一個） | |
| 合計 | 9 次打字 | 約 16 次按鍵（不含加推薦站 3 次） | | 一次到底 + 兩次離開 Berth 修掛載 |

修錯誤時離開 Berth 做的事：
- 頁 2：開 mine3 compose → 加一行 `- <絕對路徑>:/data` → `docker compose up -d qbittorrent`（重建）→ 回畫面再按測試。約 4 步，一次修好。
- 頁 3：同上對 jellyfin；Jellyfin 重建後到可用約 30 秒；回畫面按「建立並檢查」。約 4 步，一次修好。
- 為了把 `${DATA_ROOT}` 換成實值，要自己查 berth 的 `.env`：`DATA_ROOT=./data` 是相對路徑，必須自己換算成絕對路徑（Windows 還要處理 `C:\` 與 `:` 的 YAML 問題）。

## 逐錯誤表
標在哪：以 aria-invalid 與畫面位置判斷。原文逐字。

### 頁 1 Jellyfin
| 錯誤 | 畫面原文 | 標在哪 | 補法 | 只靠畫面修得好嗎 | 實際結果 | 截圖 |
|---|---|---|---|---|---|---|
| a. 位址 `http://localhost:47096` | 位址欄下紅字：「Berth 在容器裡，這個位址指的是 Berth 自己，不是你的主機。改填 host.docker.internal（Docker Desktop 內建；Linux 由 compose 的 extra_hosts 提供，服務要監聽 0.0.0.0）或它的區網 IP。用 network_mode: host 部署的話，照填沒關係。」下方「這一組沒有存下：測得過才存。改好再按一次「測試連線」。」技術細節（收合）：`localhost:47096/System/Info/Public` / `GET /System/Info/Public: connection refused` | 位址欄（aria-invalid=true）；說明訊息在 DOM 裡出現兩份（innerText 重複，可能是 sr-only 重複，需肉眼看截圖確認） | 改填 host.docker.internal 或區網 IP | 可。不是可複製片段，但已經講出該填什麼；沒有「一鍵代入 host.docker.internal」 | 照填 `http://host.docker.internal:47096` 通過 | s2-02 |
| b. 10.10.7 | 「失敗／至少要 Jellyfin 12.0，這一台是 10.10.7；等也不會好。升級之後再測一次。」+ 同樣「這一組沒有存下」 | 位址下方（aria-invalid 未標） | 升級（單向）；選卡片裡有「Jellyfin 12.0 升級注意」連結 | 可（理解到「要升級」，不給具體升級指令） | 不修，換回正確那台 | s2-03 |
| c. 非管理員 | 「失敗／這個帳號登得進 Jellyfin，但不是管理員。擁有者要改得動設定——用這台 Jellyfin 的管理員登入。」 | 登入表單下 | 換管理員 | 可 | 換管理員成功 | s2-06 |
| d. 管理員密碼錯 | 「失敗／Jellyfin 不認這組帳號或密碼。」 | 登入表單下，aria-invalid 未標任一欄 | 重打 | 可 | 重打通過 | s2-05 |
| e. 正確 | 通過後：「連上了／Jellyfin／host.docker.internal:47096 … 已經有管理員／版本 12.1.0」→ 登入表單 → 成功後 Berth 板上「已完成」、右側「擁有者 mine3admin」，來源鎖住說明「擁有者是這一台 Jellyfin 上的帳號，換一台等於換擁有者，所以來源鎖住了。同一台換了位址可以改，另一台伺服器會被擋下。」 | | | | 前往下一個泊位 | s2-04、s2-07 |

頁 1 其他可見：選了「既有」會出現「選了既有，套件內那一台用不到了：把 .env 的 COMPOSE_PROFILES 換成第一行（jellyfin 不在裡面），再用第二行停掉已經在跑的那一台…」+ 兩個可複製片段 `COMPOSE_PROFILES=qbittorrent,prowlarr` 與 `docker compose stop jellyfin`。我的 .env 本來就是空，這段對我無關但無害（片段會依其他頁的選擇而變，頁 4 那一頁顯示 `COMPOSE_PROFILES=prowlarr`）。

### 頁 2 qBittorrent
| 錯誤 | 畫面原文 | 標在哪 | 補法 | 只靠畫面修得好嗎 | 實際結果 | 截圖 |
|---|---|---|---|---|---|---|
| a. localhost | 位址欄 aria-invalid；同頁 1（a）那段「Berth 在容器裡…」；技術細節 `POST /api/v2/auth/login: connection refused` | 位址欄 | 改 host.docker.internal | 可 | 改填通過 | s2-08 |
| b. 4.3.9 | 「失敗／至少要 qBittorrent 4.4，這一台是 v4.3.9；等也不會好。升級之後再測一次。」 | 位址／帳密欄之下 | 升級 | 可（無具體指令） | 不修 | s2-09 |
| c. 密碼錯（只錯一次） | 「帳號或密碼不對。改好上面的欄位再測一次。」；技術細節 `POST /api/v2/auth/login: 401` | 帳號與密碼兩欄都標 aria-invalid | 重打 | 可 | 重打通過 | s2-10 |
| d. 帳密對、沒掛 /data | 「失敗／你的 qBittorrent 看不到 /data：Berth 在那裡寫了一個檔，它校驗之後說一點都沒有——它多半沒掛 /data（例如只掛了 /downloads），下載會寫進 Berth 拿不到的地方。在你原本那一份 compose（或 docker run 指令）的 qBittorrent 上多加一條掛載：berth 那一份 .env 的 DATA_ROOT 掛在 /data（${DATA_ROOT} 換成那個值；容器路徑只能是 /data）。原本的掛載不用動：/downloads 留著，舊 torrent 照常做種，Berth 只在 /data 底下讀寫。Berth 不做 remote path mapping。重建它（docker compose up -d，或刪掉容器再照新的指令 docker run）之後重新測試：」＋ 片段 ```qbittorrent:\n  volumes:\n    - ${DATA_ROOT}:/data``` ＋ 第二個可複製 `-v ${DATA_ROOT}:/data`。技術細節：`qBittorrent cannot see /data: it checked the file Berth had just written there and found none of it (0% after a recheck)` | 表單下方紅區，沒有標欄位（合理，非欄位問題） | 多加一條 /data 掛載、重建 | **大部分可**：找得到原因、補法與可複製片段、不用動既有掛載。缺口：片段仍是 `${DATA_ROOT}` 佔位，使用者得自己去 Berth 的 .env 找值；預設值 `./data` 是相對路徑，貼進另一個 compose 檔會解析成另一個目錄（我沒驗證這會不會被偵測，但技術上會再紅一次）；Windows 路徑（`C:\Berth\data`）放進 compose 的寫法沒說 | 加 `- C:/Users/Roxy/berth-audit3/data:/data`、`docker compose up -d qbittorrent`，回畫面再按一次「測試連線」→ 通過：「http://host.docker.internal:47080 / 版本 v5.2.3 / Web API 2.15.1 / WebUI 登入 不改（這台是你自己的）」 | s2-11、s2-12 |

驗證：d 失敗後（snap-mid-p2fail）qBittorrent 無殘留 torrent、無新分類、偏好沒變；`/data` 也沒留任何東西（探測檔刪乾淨，Berth 沒建目錄樹）。Jellyfin 的 API key「Berth」在頁 1 就已建立（見 diff）。

### 頁 3 媒體庫路徑
- 進頁面說明：「勾選要交給 Berth 寫入的媒體庫，每個選一條寫入目標。Berth 只往你選的那一條寫，同一個媒體庫的其他路徑維持唯讀；不想讓它寫進你既有的資料夾，選「新的 Berth 路徑」，按「建立並檢查」時才加到 Jellyfin。進這一頁不會動任何東西。」
- 媒體庫列：「節目 / 劇集」「電影 / 電影」，勾選後出現「寫入目標」radio：既有路徑（/tv）與「/data/library/節目 · 新的 Berth 路徑：按「建立並檢查」時加到這個媒體庫，原本的路徑不動」，預設選新的 Berth 路徑。
- 「按下之後會」清單：在 Jellyfin 的「節目」加入路徑 /data/library/節目（原本的路徑不動、不重新掃描）；在 qBittorrent 建或核對 N 個 berth- 分類（已經有的不改路徑）；在 N 條 Route 的分類路徑與寫入目標各寫一個探測檔（…你的 qBittorrent 設了「torrent 完成時執行外部程式」的話，每條會觸發一次），做一次硬鏈接，檢查完就刪掉。
- 右欄「將建立」表：媒體庫 → 寫入目標。

| 錯誤 | 畫面原文 | 標在哪 | 補法 | 只靠畫面 | 結果 | 截圖 |
|---|---|---|---|---|---|---|
| Jellyfin 沒掛 /data | 每個媒體庫一則：「「節目」沒加上 Berth 路徑／Jellyfin 看不到 /data/library/節目：它沒掛 /data。Berth 建好了目錄、在裡面寫了一個檔，Jellyfin 說它看不到；這一次建的目錄已經收回（原本就在的不動）。在你原本那一份 compose（或 docker run 指令）的 Jellyfin 上多加一條掛載：berth 那一份 .env 的 DATA_ROOT 掛在 /data（${DATA_ROOT} 換成那個值）。原本的掛載不用動。重建它之後再按一次：」＋ 片段 `jellyfin:\n  volumes:\n    - ${DATA_ROOT}:/data` ＋ `-v ${DATA_ROOT}:/data`。技術細節：`Jellyfin cannot see /data/library/節目: POST /Environment/ValidatePath answered 404 for a file Berth had just written there` | 每個媒體庫的卡片（不是欄位） | 多加 /data、重建 | 同頁 2：大部分可，同樣有 `${DATA_ROOT}` 佔位、相對路徑的缺口。兩個媒體庫各重複同一段長文與兩份片段（共 4 個複製鈕），視覺很重 | 加 `- C:/Users/Roxy/berth-audit3/data:/data`、`docker compose up -d jellyfin`（約 30 秒起來）、回畫面按「建立並檢查」→ 兩條都 6/6 通過 | s2-15、s2-16 |
- 失敗後狀態（snap-mid-p3fail）：Jellyfin 媒體庫沒被加路徑、qBittorrent 沒建分類、/data 底下沒殘留（Berth 說「建好了目錄……已經收回」，實測 /data 是空的）。
- 修好後的畫面：每個媒體庫變「已繫上 節目 / berth-節目 / /data/library/節目 / 6 / 6 通過」，可展開 6 項檢查（建 qBittorrent 分類、qBittorrent 的路徑 Berth 看得到、qBittorrent 讀得到 Berth 寫的檔案、Jellyfin 的媒體庫路徑 Berth 看得到、Jellyfin 看得到 Berth 寫的檔案、硬鏈接與 inode 比對，附 dev / inode / free=489.1 GB）。上方「已經有 Route 了：精靈只新增，不改也不刪它。選錯了就用下面那一條的刪除；精靈跑完之後在「設定 → 媒體庫路徑」管理。」按鈕「刪除這條 Route」「重新檢查 2 條 Route」。

### 頁 4 Prowlarr
| 錯誤 | 畫面原文 | 標在哪 | 結果 | 截圖 |
|---|---|---|---|---|
| a. 1.0.1 | 「失敗／至少要 Prowlarr 1.3.2，這一台是 1.0.1.2220；等也不會好。升級之後再測一次。」 | 表單下 | 可懂 | s2-17 |
| b. API key 錯 | 「API key 不對：在 Prowlarr 的「設定 → 一般」複製 API key（不是介面登入的密碼），貼上再測一次。」；技術細節 `GET /api/v1/system/status: 401` | API key 欄（aria-invalid，password 型） | 可修（說明指向對的位置；頁面開頭另有「在 Prowlarr 的「設定 → 一般 → 安全性」找得到 API key」） | s2-18 |
| c. 正確 | 「連上了／Prowlarr／host.docker.internal:47696 … 連線測試通過／索引站 1」；列出「你那一台上已經有的站。Berth 用它們搜尋，不移除——要移除請到它自己的介面。」顯示 YTS（可「搜尋」單站、「搜尋全部」）；「加站」區：推薦的站（Nyaa.si、dmhy、Anime Tosho、ACG.RIP、Mikan、1337x、EZTV、The Pirate Bay）有「測試全部」「測試」；「其他公開站 78」搜尋名稱 + 語言；底下「要帳號的站（私站、半私站）在 Prowlarr 自己的介面加…」 | | | s2-19 |
- 推薦站測試：測試全部約 40 秒內回完，結果 Nyaa.si 沒通過（「連不上：DNS、TLS 或站本身掛了。換個時間再測，或檢查 Prowlarr 那台對外的網路。」）、1337x 與 EZTV 沒通過（「被 Cloudflare 擋住：這個站擋掉自動化的請求，要在 Prowlarr 設 FlareSolverr 才過得去。」），dmhy、Anime Tosho、ACG.RIP、Mikan、The Pirate Bay 通過；沒通過的勾不起來，通過的才可勾。我勾了 The Pirate Bay，按鈕變「加入 1 個站」，加入後「已加入 2 站」，推薦清單變「3 站沒通過／Cloudflare 擋住 2 · 連不上 1 · 4 站通過」。不動原有的 YTS（id 與設定都沒變，見 diff）。截圖 s2-20（測完勾選）、s2-21（加入後）。
- 加推薦站不是必要的，可以按「之後再說」。

### 頁 5 TMDB
- 進頁面：「TMDB／必填／Berth 不內建任何一把 API key……去哪裡拿：在 themoviedb.org 註冊一個免費帳號，開「設定 → API」申請…」連結與可複製網址；欄位「你的 TMDB API key」（v3 32 位 hex 或 v4 token 都可）；「測試 TMDB」。填真 key 後「已完成／驗證憑證」，板上「已驗證」，右欄「憑證 已取得」。s2-22、s2-23。

### 頁 6 完成
- 「完成設定／五個泊位都走過了。按下完成之後精靈就關閉，之後的修改在設定頁。」列兩條 Route（節目 → berth-節目 → 寫入目標 /data/library/節目、complete 目錄 /data/torrent/complete/節目；電影同）；「各服務自己的介面／平常用不到它們：Berth 替你接好了。要看下載細節、管理 Jellyfin 的使用者、在 Prowlarr 加要帳號的站時才開。」三個外連：Jellyfin http://localhost:47096「用擁有者 mine3admin 登入，與 Berth 同一組。」qBittorrent http://localhost:47080「用你原本的登入。」Prowlarr http://localhost:47696「用你原本的登入。」「完成後直接進 Berth。之後登入一律用 Jellyfin 帳號：你是 mine3admin，其他人用自己的 Jellyfin 帳號，是那台的管理員才進得來設定。」右欄「這一輪的結果」：媒體庫根目錄 /data/library、complete 根目錄 /data/torrent/complete、Route 數 2、跳過 沒有。s2-24。
- 完成後落在探索首頁（TMDB 趨勢）；右上顯示「管理員 mine3admin」。s2-25。

## before / after diff（snap-before.json vs snap-after.json，mine3 三台）
Jellyfin（12.1.0）：
- 新增 API key：AppName=`Berth`（AppVersion、DeviceName 空）。頁 1 登入後就建了，不是頁 3。
- 兩個媒體庫各多一條路徑，原路徑保留：節目 `['/tv']` → `['/data/library/節目','/tv']`、電影 `['/movies']` → `['/data/library/電影','/movies']`；`LibraryOptions.PathInfos` 同步各加一筆。其他 LibraryOptions 沒變。
- 使用者：沒變（管理員、非管理員都在，沒新增 Berth 自己的帳號）。`/System/Configuration` 全文 hash 沒變。
- `System/Info/Public.ServerName` 變了（89bce0f23b9c → b8ebef46a5ae），這是我重建容器的副作用（ServerName 預設 = 容器 hostname），與 Berth 無關。
- 沒觸發重新掃描（說明也這樣寫）；未驗證 Jellyfin 之後是否排程掃描。
qBittorrent（v5.2.3）：
- 新增分類（2）：`berth-節目`（savePath `/data/torrent/complete/節目`、download_path `/data/torrent/incomplete/節目`）、`berth-電影`（`/data/torrent/complete/電影`、`/data/torrent/incomplete/電影`）。
- `app/preferences` 逐鍵沒變（含 save_path=/downloads、temp_path、auto_tmm、web_ui_username=我自己的帳號、密碼）。tags 沒變（空）。torrents 清單空（探針 torrent 清乾淨）。
Prowlarr：
- 多 1 個站（The Pirate Bay，id 2，enable、appProfile 1，我在畫面上勾的），YTS 沒動。
- `config/host`：authenticationMethod 仍是 forms、使用者名沒變；沒新增 application、tag。
Berth 在 `/data`（宿主 `berth-audit3\data`）：
```
data/library/節目  data/library/電影
data/torrent/complete/節目  data/torrent/complete/電影
data/torrent/incomplete/節目  data/torrent/incomplete/電影
```
（全是空目錄，沒殘留探測檔；中文資料夾名是由 Jellyfin 媒體庫名稱而來，非英文識別符，qBittorrent 分類也是 `berth-節目`。）
Berth config 目錄：`/config` 底下只有 `berth.db`（+ -shm/-wal）；宿主 `config/prowlarr` 目錄由 compose 的 `/ext/prowlarr` 唯讀掛載自動建出一個空目錄（預期，因為 prowlarr 是既有的、這個目錄沒用）。

## 冒煙
- 探索頁搜「Night of the Living Dead」→ 20 部作品，第一筆 MOVIE · 1968 活死人之夜；進作品頁（movie:10331）→ 按「搜尋」約一分鐘內回 36 筆（另有 100 筆名字對不上已略過），來源有 YTS 與 The Pirate Bay（Berth 加的），5 個關鍵字都有回應。沒送單。s2-26、s2-27。
- 作品頁的「入庫到」下拉顯示「尚未指定 / 電影」，沒有預選；未驗證不選就送單會怎樣。
- 健康頁：Jellyfin 版本 12.1.0 · 2 個媒體庫；qBittorrent v5.2.3 · Web API 2.15.1；2 條 Route 皆 6/6 通過；Prowlarr 索引站 2；TMDB 已驗證。s2-28。

## 問題清單
1. 補法的 `${DATA_ROOT}` 佔位需要使用者自己換成實值（頁 2、頁 3；s2-11、s2-15）。`.env.example` 預設 `./data` 是相對路徑，貼進另一個 compose 會指到別的目錄。Windows 的 `C:\...` 路徑在 YAML 裡怎麼寫也沒提。影響：第一次接既有服務最容易卡在這。（畫面不知道宿主絕對路徑是合理的；但至少可說「若是相對路徑要換成絕對路徑」。）
2. 頁 3 同一段長補法對每個沒掛 /data 的媒體庫重複一份（兩個庫 = 兩段 + 4 個複製鈕），而且不是「Jellyfin 沒掛 /data」的一則總訊息。Jellyfin 是容器層級問題，不是媒體庫層級（s2-15）。
3. qBittorrent 與 Jellyfin 沒掛 /data 要到「頁 2 的測試連線」與「頁 3 的建立並檢查」才各自發現；Jellyfin 沒掛的事到頁 3 才會知道，頁 1 只講版本與登入。使用者在頁 1 的卡片說明已經看到條件，但畫面沒有在頁 1 提醒要先掛。（票 46 的做法讓 qBittorrent 提前到頁 2，Jellyfin 沒對稱。）
4. 頁 1、頁 2 位址填 localhost 時，同一段「Berth 在容器裡，這個位址指的是 Berth 自己…」在畫面上出現兩次（一次是黃線提示、一次是紅字錯誤，內容逐字相同；s2-02 已確認，s2-08 同）。影響：視覺重複，使用者會以為是兩個問題。
5. 頁 1「選了既有，套件內那一台用不到了」的 `COMPOSE_PROFILES=qbittorrent,prowlarr` 與 `docker compose stop jellyfin`：對本情境（`.env` 已是空）不適用，但畫面沒辦法知道，不是錯。小問題：頁 4 選既有仍顯示 `docker compose stop prowlarr`。
6. 頁 1 aria-invalid 只有位址有標，登入失敗（密碼錯、非管理員）沒標欄位；頁 2 密碼錯標了兩欄；不一致，小。
7. `docker compose` 重建 mine3-jellyfin 後 Jellyfin 的 ServerName 預設值（容器 id）變了；Berth 的擁有者鎖是看伺服器 id（未動）所以沒擋。未驗證若使用者換掉 Jellyfin 資料目錄的情況。
8. 技術細節裡的位址少了 scheme（`host.docker.internal:47096/System/Info/Public`），複製不能直接貼；小。
9. 同一主機不能並存兩套 Berth：官方 compose 寫死 `name: berth`、`container_name: berth`、網路名與子網（172.28.0.0/16）。對本審計是額外工作；對使用者是「第二次試跑撞名」。（brief §20.14 與 compose 註解有提容器名撞名，但沒提這個。）
10. 分類與資料夾用媒體庫名稱：`berth-節目`、`/data/library/節目`。中文媒體庫名直接成為檔案系統與分類名；若使用者的庫名有特殊字元／同名，可能有問題，未驗證。

## 做得好的地方
- 所有錯誤都有人話原因與下一步，且都標「這一組沒有存下：測得過才存」；錯誤的設定沒有被存下（Jellyfin 的 API key 除外，那是登入成功時才建）。
- qBittorrent 版本、Prowlarr 版本、Jellyfin 版本的錯誤訊息一致（「至少要 X，這一台是 Y；等也不會好。升級之後再測一次。」）。
- 頁 2 在畫面上就先寫了「檢查時暫時加一個停住的探測 torrent、隨即移除」「測試時 Berth 會在 /data 寫一個探測檔…」，事先講清楚會做什麼；失敗後實測沒有殘留。
- 失敗時不留東西（頁 3 失敗後 /data 是空的、qBittorrent 沒建分類）。
- 對既有 Prowlarr 的站「不移除」並寫明；推薦站先測再勾，Cloudflare 擋住與連不上有分開的原因文案。
- 修完後重測是原地按一次，不必重填；補法有可複製的 compose 與 docker run 兩種格式；明講「原本的掛載不用動」、「Berth 不做 remote path mapping」。
- 完成頁的外連是 localhost（瀏覽器看得到的位址），不是 host.docker.internal；寫了每台要用什麼登入。
- diff 顯示 Berth 在既有服務上的改動很小，且全都有在畫面事先交代（Jellyfin 的 API key、路徑加一條、qBittorrent 分類）。

## 沒跑到／未驗證
- 沒測：連錯 5 次被封 IP 的畫面（故意只錯一次）；qBittorrent「免密」；Jellyfin 還沒跑過初始精靈的情境；Berth 的 EN 介面；窄螢幕。
- 沒送單、沒驗證入庫與硬鏈接實際入庫（只有 Route 的 6 項檢查）。
- 頁 3 「寫入目標」選既有路徑（/tv）的分支沒走。
- 沒驗證 Linux 路徑（這台是 Windows + Docker Desktop）。
- 沒量實際的按鍵時間；計數是我的腳本步驟換算，真人手動會多幾次捲動與複製。
