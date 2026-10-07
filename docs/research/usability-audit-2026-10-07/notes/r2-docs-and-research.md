# Berth 可用性審計：文件走查與成熟產品對照

查證日 2026-10-07，repo main 107708c。外部原始碼行號取自各專案 develop / master 當日內容，之後會漂移。
上一輪審計的 §E 對照與來源（`docs/research/wizard-audit-2026-10-06.md:366-457`、`:601-611`）不重做，這裡只補它沒有的。
標「查不到」的是我沒有找到出處，沒有用記憶補。

---

# 第一節　任務一：照 README 部署（紙上走查）

視角：會用 docker compose、第一次接觸 Berth 的自架使用者。範圍 `README.md:1-232`、`deploy/.env.example`、`deploy/docker-compose.yml`、`CHANGELOG.md` 0.1.0 段（`:71-100`）。

## 1.1 量測

| 項目 | 數字 | 方法 |
| --- | --- | --- |
| README 1–232 行的中文字 | 約 4,650 | 7–231 行 4,165 字；3–5 行簡介 490 字（腳本計中文字元，不含英文與程式碼） |
| 第 5 行一整段「M1 / M1.5 / M2 / M3 已完成」 | 約 420–480 字，單一段落 | 里程碑編號對使用者沒有意義；名詞表（`CONTEXT.md`）只在這段最後一句帶過 |
| 部署段（7–231）各塊字數 | 概觀＋精靈表 678；既有服務條件與範例 344；停掉套件內那一台 401；精靈其餘說明（91–101，含密碼段）536；頁面表 424；port 表 255；TMDB 272；硬鏈接 110；平台 135；外部服務前提 486；秘密 37；升級＋自己 build 201；疑難排解 286 | 逐段計中文字 |
| 部署段出現的專有 / 技術名詞（去重） | 約 35 個；Berth 自創的約 6 個（泊位、BTH n、Route、Berth 路徑、套件內 / 既有、擁有者） | 見 1.3 |
| `brief §` 引用 | 部署段內 6 處（`README:35, :70, :123, :157, :167, :222`）；`.env.example` 與 compose 內另有 plan § / brief § | 只下載 `deploy/` 的人沒有這些檔 |
| 第一部片入庫的「必讀」估計 | 約 1,000–1,400 字（見 1.5） | 約為現在的 22–30% |

## 1.2 卡住的地方

| # | 位置 | 卡在哪 | 會發生什麼 | 建議 |
| --- | --- | --- | --- | --- |
| S1 | `README:11-14` | `cd deploy` 之前沒有「怎麼拿到 `deploy/`」。沒有 `git clone`、沒有 repo URL（`https://github.com/1morr/Berth`，repo 公開，我用 `gh repo view` 確認）、沒有 release 附件。`deploy/` 也不能只抓 compose 一個檔：`docker-compose.yml:90` 掛 `./preseed/qbittorrent`，缺目錄時 Docker 會建空目錄，qBittorrent 沒有免密白名單，Berth 進不去（`deploy/preseed/qbittorrent/10-berth.sh:4-7` 自己說沒這一步 Berth 進不去） | 沒裝 git 的 Windows 使用者不知道從哪開始；照 Immich 做法只 `wget` compose 會得到壞掉的套件。升級步驟（`README:184`「把那一版的 `deploy/docker-compose.yml` 蓋過」）同樣沒說怎麼拿 | 見 1.5 的 A、B 兩案 |
| S2 | `README:13`、`docker-compose.yml:3` vs `.env.example:9` | README 與 compose 檔頭說「改 DATA_ROOT 與 CONFIG_ROOT」，`.env.example:9` 說「第一次試跑不用改任何東西」。三處都沒講預設值是什麼（`./data`、`./config`，相對於 compose 檔，實際落在 clone 出來的 `deploy/data`、`deploy/config`）、也沒講不改的後果 | 使用者不知道該不該改。預設值下資料庫（`config/berth/berth.db`）與整個媒體庫都在 repo 資料夾裡：刪掉 clone 就丟資料庫；NAS 使用者的媒體會寫進系統碟。`.gitignore:27-28` 只保護開發者 | README 直接寫「DATA_ROOT 放你的媒體磁碟；試跑可不改」，並說明預設落在哪 |
| S3 | `README:11-15` 的指令塊 | 預設 `COMPOSE_PROFILES=jellyfin,qbittorrent,prowlarr`（`.env.example:51`）。已經有 Jellyfin（8096）、qBittorrent（8080 / 6881）的人照這 3 行 `up -d`，**在看到精靈之前**就撞 `port is already allocated`（`README:218`）。「選既有 → 拿掉 profile」要到精靈之後才說（`:127`、`:69-80`），順序相反 | 指令塊裡沒有「已經有服務的人先改 COMPOSE_PROFILES」；那一段在 `:127` 與疑難排解 `:218`，離安裝步驟 100–200 行 | 把這句放進安裝步驟本身：一個判斷「你已經在跑 Jellyfin / qBittorrent / Prowlarr 嗎？是 → `up -d` 之前先編輯 `.env` 的 COMPOSE_PROFILES」 |
| S4 | 全文 | 沒寫前置需求：Docker Engine / Docker Desktop、Compose v2（compose 用頂層 `name:`、`x-` 錨點、`${VAR:?}`）、要連 ghcr.io 與 lscr.io 拉四個 image、磁碟與記憶體 | 舊 Compose（v1 `docker-compose`）會報錯；Immich 文件特地為此寫了一段（`'name' does not match any of the regexes: '^x-'`） | 一行前置需求。版本下限我沒有驗證，需維護者用最舊可跑的版本測 |
| S5 | `README:17` | 「開 http://localhost:8383」之後沒有「打不開怎麼辦 / 怎麼知道好了」。疑難排解只有 3 個特定症狀（`:211, :218, :224`），沒有 `docker compose ps` / `logs berth` | 第一次拉 image 要等，使用者看到的是連線被拒 | 一行：「`docker compose ps` 看到 berth healthy 再開」 |
| S6 | `.env.example:27` | `TZ=Asia/Taipei` 預設，compose 的 fallback 是 `Etc/UTC`（`docker-compose.yml:25`）。README 完全沒提 TZ | 台灣以外的使用者 `cp` 之後，log 與排程（每日對帳）用台北時間而不自知 | README 把 TZ 列進「要確認的值」 |
| S7 | `README:156-159`、`.env.example:18-20` | PUID / PGID：Linux 說用 `id -u` 查、`chown -R 1000:1000`；NAS 使用者的 uid 多半不是 1000。`README:159` 與 CHANGELOG `:75-76` 自己承認原生 Linux 與 NAS 沒人實跑過 | 在 NAS 上第一個遇到權限問題的會是真使用者 | 把「Linux / NAS 還沒驗過」放到安裝步驟旁，而不是平台段末（第 159 行） |
| S8 | `README:17-18`、`:129-144` | TMDB key 在精靈第 5 頁才要，是整套唯一需要「離開 Berth」的步驟，但安裝步驟前沒有提示先申請；還要收驗證信 | 走到第 5 頁才停下去註冊；頁 3 檢查一過就要等 | 安裝步驟第 0 步「先申請 TMDB key（約 5 分鐘，見下）」 |
| S9 | `README:103-127` | `### 頁面`（`:103`）底下接著 port / `.env` 變數表（`:114`）與 port 衝突說明，沒有自己的標題 | 要找 port 的人在「頁面」節下找不到 | port 表單獨標題，或搬走 |

## 1.3 看不懂的地方：術語分級

「必須」＝沒懂就會做錯或卡住；「可以不懂」＝出現在文字裡，但照預設走不影響。

### 安裝到第一部片入庫之前必須理解（8 個）

| 名詞 | README 首見 | README 有沒有先定義 | 備註 |
| --- | --- | --- | --- |
| compose / `.env` / `docker compose up -d` | `:11-14` | 不需要（使用者已會） | |
| `DATA_ROOT`（媒體根：下載與媒體庫在同一個目錄底下） | `:13`、`.env.example:4-10` | 部分：`:150` 才說為什麼只能一個根 | Berth 最重要的一個設定，理由到第 150 行才出現 |
| 精靈六頁在做什麼 | `:20-31` | 有，但是一張密集表 | 使用者只需要「每頁一句話」 |
| 套件內 / 既有（只在已經有服務時才必須） | `:20` | 有，但夾在表前一段 | 沒有既有服務的人可完全略過 |
| 擁有者（你第一次建的 Jellyfin 管理員，也是登入 Berth 的帳號） | `:97` | 第 97 行才解釋，頁 1 表格 `:26` 已在用 | 必須知道「頁 1 的密碼就是日後登入 Berth 的密碼」 |
| TMDB API key | `:18`、`:129-144` | 有 | 必須 |
| 硬鏈接前提（一個檔案系統、別放 exFAT / 網路磁碟） | `:45`、`:146-152` | 有 | 使用者只需「DATA_ROOT 放在本機一般磁碟」一句 |
| Route（一個媒體庫對應的一條下載到入庫的路） | `:28` | **沒有**。`CONTEXT.md` 才有定義，README 不連結 | 精靈頁 3 會用；使用者要知道「Route 就是 Movies / TV / Anime 各一條」 |

### 出現但可以不懂（約 27 個）

| 類別 | 名詞（行號） | 為什麼可以不懂 |
| --- | --- | --- |
| Berth 自創 | 泊位（`:20, :23`）、BTH 1–5（`:25-31`）、Berth 路徑（`:28, :35, :44`）、泊位板（`:95`）；「纜繩」README 沒出現，UI 有 | UI 的隱喻；使用者只看見頁碼。README 把隱喻當術語講，多一層翻譯 |
| 檔案系統 | EXDEV、inode（`:93, :150`）、mergerfs / btrfs 子卷 / ZFS dataset / exFAT（`:45, :151`）、硬鏈接 | 檢查失敗時精靈會指出；使用者只需知道「同一個磁碟」 |
| Docker 網路 | `host.docker.internal`、`extra_hosts`（`:224-231`）、免密白名單、固定 IP / 子網（compose `:14-17`） | 只在「接既有服務」時用到；套件內全自動 |
| qBittorrent 內部 | autoTMM、`downloadPath`、`berth-*` 分類、全域偏好（`:163`） | 是「Berth 不做什麼」的說明，使用者不需要先知道 |
| 環境與升級 | PUID / PGID / UMASK（只有 NAS 需要）、`COMPOSE_PROFILES`（只有既有服務需要）、`--remove-orphans`（`:70`）、named volume / WSL2（`:157`）、migration（`:186`）、JWT / v3 / v4（`:138-140`） | |
| 內部文件引用 | `brief §` 6 處、「M0 驗收」（`:159`）、Seerr（`:173`）、`/health` 每 5 分鐘（`:101`） | 對使用者沒有資訊 |
| 帳密機制 | 免密白名單、加鹽雜湊、「介面登入」vs「Jellyfin 擁有者」（`:97-99`）：一段約 330 字講三組密碼的關係 | 使用者的實際動作是「頁 1 設一組帳密，之後自動帶入」；機制可進 docs |

README 內沒出現：Torznab、纜繩（已拿掉或只在 UI）。

數量結論：部署段約 35 個專有 / 技術名詞，**8 個**是第一次入庫前必須懂的，其餘約 27 個可延後；其中 Berth 自創、必須在 README 內先定義卻沒定義的是 **Route** 與「擁有者」。

## 1.4 跟實際對不上

比對對象：`deploy/docker-compose.yml`、`deploy/.env.example`、`deploy/preseed/qbittorrent/10-berth.sh`、`deploy/entrypoint.sh`、`berth/services/setup.py`、`berth/services/indexer.py`、`berth/models/setting.py`、`web/src/pages/SetupPage.tsx`、`web/src/i18n/resources.ts`（只抽查 README 有具體宣稱處）。

### 不一致（4 項）

| # | README 行 | 宣稱 | 實際 | 嚴重度 |
| --- | --- | --- | --- | --- |
| D1 | `:9` | 「Berth 加 qBittorrent、Jellyfin、Prowlarr，**四個容器掛同一個媒體根**」；`.env.example:4`「四個容器都掛這一個目錄」 | compose 裡只有 berth（`:61`）、qbittorrent（`:88`）、jellyfin（`:111`）掛 `${DATA_ROOT}:/data`；prowlarr（`:124-125`）只掛 config。是**三個**。`.env.example:12` 的「四個服務的設定目錄」才是對的 | 低，但是 README 第一個技術宣稱 |
| D2 | `:13` vs `.env.example:9` | 見 S2 | 兩處互相矛盾 | 中 |
| D3 | `:17-18` | 「所有設定都在精靈裡完成，不需要分別打開另外三個服務的介面。唯一要離開 Berth 的一步是 TMDB」 | 私站要去 Prowlarr 介面加（`docker-compose.yml:57-58`、`.env.example:33`：「在 Prowlarr 加私站」連結由 `PROWLARR_PORT` 組成）；接既有服務且掛載缺少時要去改自己的 compose（`README:49-67`）。只對「公開站＋套件內服務」成立 | 低 |
| D4 | `:103` 起 | `### 頁面` 下夾著 port 表 | 見 S9 | 低 |

### 抽查後一致（不需處理）

| README 行 | 宣稱 | 證據 |
| --- | --- | --- |
| `:25` | 套件內 Jellyfin 還在啟動時每 3 秒重測、上限 2 分鐘 | `web/src/pages/SetupPage.tsx:93`（`POLL_INTERVAL_MS = 3000`）、`berth/services/setup.py:94`（`TEST_WINDOW = timedelta(minutes=2)`） |
| `:28` | 預設清單 Movies / TV / Anime | `berth/models/setting.py:255-259` |
| `:29` | 「九個推薦的公開站」 | `berth/services/indexer.py:72-82`（9 項） |
| `:156` | 「只在媒體根還是空目錄時自動接手擁有者」 | `deploy/entrypoint.sh:56-58`（空目錄才 `take_ownership`） |
| `:163` | 只放行 Berth 固定 IP；不覆蓋已有值的設定 | `deploy/preseed/qbittorrent/10-berth.sh`（`BERTH_IP/32`、`has_key` 缺鍵才補） |
| `:177-179` | `:latest`、`:0.1.0`、`:0.1` 三個 tag | 我以匿名 token 查 `ghcr.io/v2/1morr/berth/tags/list`，回 `["0.1.0-rc1","0.1.0","0.1","latest"]`，image 公開 |
| `:224-227` | `extra_hosts: host.docker.internal:host-gateway` | `docker-compose.yml:68-69` |
| `:69-85` 停掉套件內那一台 | 指令與說明 | `web/src/i18n/resources.ts:232`、`web/src/setup/ServiceChoice.tsx:350` 同樣說法 |

README 中「不預選、不偵測」等 UI 行為我沒有重跑 UI 驗證（本任務不用 playwright）。

## 1.5 新使用者要讀多少、怎麼精簡

### 現況

從打開 README 到第一部片入庫，使用者實際必須經過：第 3–5 行（簡介，其中約 420 字是里程碑清單）→ 7–18（安裝）→ 20–35（精靈表與模型）→ 129–144（TMDB）→ 146–159（硬鏈接與平台）。約 **2,000 字**；再加上若有既有服務，`:37-89`（約 745 字）。真正跳不過的內容（安裝指令、TMDB 申請 4 步、DATA_ROOT 一句話）合計不到 600 字，其餘是夾在它們前後的說明。

### 逐段處置

| 段落（行） | 字數 | 處置 | 去哪 / 怎麼改 |
| --- | --- | --- | --- |
| 簡介 `:3` | 約 70 | 留 | |
| 里程碑長段 `:5` | 約 420 | 搬 | `CHANGELOG.md`（已有）；README 只留「目前版本 0.1.0」與連結 |
| 安裝 `:7-18` | 約 250 | 留，改寫 | 加入「怎麼拿到檔案」「已經有服務先改 COMPOSE_PROFILES」「先申請 TMDB key」「要改 DATA_ROOT / TZ」「怎麼知道好了」 |
| 精靈表 `:20-31`＋模型說明 `:33-35` | 約 680 | 拆 | README 只留每頁一句（約 150 字）；9 欄位的表搬 `docs/setup-wizard.md` |
| 既有服務條件、範例、停掉套件內那一台 `:37-89` | 約 745 | 搬 | `docs/existing-services.md`；README 留一句＋連結 |
| 換一台、TMDB 不可略過、Route 檢查、上一頁 `:87-95` | 約 340 | 搬 | `docs/setup-wizard.md`（多半是精靈自己會講的） |
| 帳號與介面登入 `:97-101` | 約 330 | 改寫成 2 句，其餘搬 | README：「頁 1 的 Jellyfin 管理員帳密就是日後登入 Berth 的帳密」；機制（加鹽雜湊、免密白名單、不存密碼）搬 `docs/setup-wizard.md` |
| 頁面表 `:103-112` | 424 | 刪或搬 | `docs/usage.md`；UI 自己的導覽比 README 的表準 |
| port 表與衝突說明 `:114-127` | 255 | 縮成 `.env.example` 旁幾行 | 其餘搬 `docs/troubleshooting.md` |
| TMDB `:129-144` | 272 | 留，略縮 | 整套唯一必做、且要離開 Berth 的步驟 |
| 硬鏈接前提、平台 `:146-159` | 245 | 縮成 2 句放進安裝步驟 | 「DATA_ROOT 放在本機一般磁碟（不是 exFAT / 網路磁碟），其餘由精靈第 3 頁檢查」；細節搬 `docs/requirements.md` |
| 外部服務前提 `:161-169` | 486 | 搬 | `docs/requirements.md`（只與接既有服務、升級 Jellyfin 的人相關） |
| 秘密與備份 `:171-173` | 37 | 留（1 行） | |
| 版本與升級 `:175-198` | 201 | 搬 | `docs/upgrading.md`；README 一句連結 |
| 疑難排解 `:200-231` | 286 | 搬 | `docs/troubleshooting.md`；README 留最常見 3 個症狀標題 |

### 精簡後必讀長度

簡介 70 ＋ 安裝步驟（含取得檔案、改 DATA_ROOT / TZ、既有服務判斷）約 300 ＋ 精靈每頁一句 150 ＋ TMDB 約 220 ＋ DATA_ROOT 與硬鏈接 80 ＋ 備份 40 ＋ 連結 50 ≈ **910 字**；留餘裕估 **1,000–1,400 字**，約現在的 22–30%。

### 取得檔案：兩個具體方案

| 方案 | 做法 | 優缺點 |
| --- | --- | --- |
| A：release 附件 | `.github/workflows/release.yml`（現在只推 image）多附 `berth-deploy-<版本>.zip`（`docker-compose.yml`、`.env.example`、`preseed/`），README：下載、解壓、`cp .env.example .env`。Immich 的做法是把 `docker-compose.yml` 與 `example.env` 當 release 附件，`wget -O docker-compose.yml https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml`，檔案與版本對得上 | 與升級流程（`README:184`）一致；要改 workflow |
| B：preseed 內嵌 | compose 頂層 `configs: <name>: content: \|` 內嵌 `10-berth.sh`，再掛到 `/custom-cont-init.d/`。`content` 屬性自 Compose 2.23.1 起（`docker/docs` `content/reference/compose-file/configs.md:19-23`，網頁 `https://docs.docker.com/reference/compose-file/configs/`）。這樣只需 `wget` compose 與 `.env.example`，與 Immich / Jellyfin / Seerr 的使用者習慣一致 | 只剩一個 compose 檔；代價是 Compose 版本下限變 2.23.1，腳本內嵌在 YAML 較難測。屬設計取捨，需維護者決定，本審計不推薦哪一案 |

## 1.6 成熟產品「從零到能用」的必讀篇幅與結構

| 產品 | 怎麼拿到 compose / 檔案 | 必讀內容 | 篇幅 | 來源 |
| --- | --- | --- | --- | --- |
| Immich（多容器，最像 Berth） | 建資料夾 → `wget -O docker-compose.yml https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml`、`wget -O .env .../example.env`（兩個 release 附件；也可從瀏覽器下載再把 `example.env` 改名 `.env`） | Step 1 下載、Step 2 改 `.env`（列 4 項：`UPLOAD_LOCATION`、`DB_PASSWORD`、`TZ`、必要時 DB 資訊）、Step 3 `docker compose up -d`；之後「Next Steps」連到 post-install 與升級。前置版本問題寫成幾行告警（`docker compose` 而非 `docker-compose`；Docker Engine 25） | 共用安裝步驟 249 英文字＋ 安裝頁本身 231 字（我自己下載計數） | `https://docs.immich.app/install/docker-compose`；`https://raw.githubusercontent.com/immich-app/immich/main/docs/docs/partials/_docker-compose-install-steps.mdx` |
| Jellyfin（單容器） | 文件頁直接給 `docker-compose.yml` 範例，自己 copy 存檔；變數為文中的 `/path/to/config`、`/path/to/media` | 範例檔＋「在同一資料夾執行 `docker compose up`」；`-d` 為補充句 | 一個範例＋ 2 句；之後 `post-install/setup-wizard` 另一頁（6 個畫面） | `https://jellyfin.org/docs/general/installation/container/`、`https://jellyfin.org/docs/general/post-install/setup-wizard/` |
| Seerr（前身 Jellyseerr / Overseerr） | 文件頁給 compose 範例（`ghcr.io/seerr-team/seerr:latest`），自己 copy；先 `mkdir` 設定夾並 `chown 1000:1000`（容器以 `node` 使用者跑） | 範例＋ 建夾 / chown ＋ `docker compose up -d`；Windows 有獨立小節（用 named volume，需 WSL2 避免資料庫損毀） | 整頁約 1,270 英文字，含 `docker run`、升級、Windows 多條路徑；compose 路徑本身一屏 | `https://docs.seerr.dev/getting-started/docker`；原始檔 `https://raw.githubusercontent.com/seerr-team/seerr/develop/docs/getting-started/docker.mdx` |
| Home Assistant（Docker） | 文件頁給 `docker run` 與 `compose.yaml` 範例，自己 copy；前置寫明 Docker Engine 23.0.0 以上、「Docker Desktop will not work; you must use Docker Engine」 | 調整 `/PATH_TO_YOUR_CONFIG` 與時區後執行；onboarding 5 步在另一頁 | 安裝一屏；onboarding 原始檔約 4,300 字元（含截圖說明） | `https://www.home-assistant.io/installation/linux/`、`https://www.home-assistant.io/getting-started/onboarding/` |

觀察：

1. 四個產品的安裝頁都是「一個檔案或範例＋ 一行 `up -d`＋ 指向 onboarding 另一頁」；沒有一個把里程碑、元件術語或疑難排解塞在安裝頁（我讀到的段落範圍內）。
2. 三個直接給 compose 範例的產品，使用者拿到的是**單一檔案**；Immich 靠 release 附件把檔案與版本綁在一起。Berth 因為 `preseed/` 目錄是例外（見 S1）。
3. Immich 與 Seerr 的步驟只要求改 2–4 個值，並在步驟裡直接列出是哪幾個。
4. 前置版本需求都放在安裝頁本身（HA：Engine 23+；Immich：Compose v2 / Engine 25 警告）。

---

# 第二節　任務二：成熟產品的精靈與「接入既有服務」

背景：使用者理想流程是「套件內不用動手、既有服務填位址帳密 → 檢測 → 說清楚或自動完成需要的設定」；Berth 的 D1（`docs/design-brief.md` §19、§16.4）是只管 Berth 擁有的物件、不改全域偏好與帳密。2.1–2.5 只列證據，2.7 才歸納。

## 2.1 Jellyfin 首次啟動精靈

| 項目 | 內容 |
| --- | --- |
| 頁數 | 6 個畫面：語言 → 管理員帳號 → 加入媒體庫 → 偏好的 metadata 語言 → 網路（遠端存取、自動 port 對應）→ 完成 |
| 每頁輸入 | 語言（選單）；管理員帳號與密碼；媒體庫（內容類型、顯示名稱、資料夾）；metadata 語言與國家；遠端存取與 UPnP 勾選 |
| 可略過 | 媒體庫頁：「click on 'Next' without adding anything to skip this step」，之後可補 |
| 它改外部什麼 | 沒有外部服務，只設自己 |
| 備註 | 官方建議關閉 automatic port mapping，因為依賴 UPnP |
| 來源 | `https://jellyfin.org/docs/general/post-install/setup-wizard/`（上一輪已引用，這次補逐頁欄位；網路頁欄位名稱依文件摘要，未開 UI 驗證） |

## 2.2 Sonarr / Radarr 加 qBittorrent download client

來源均為 Sonarr develop：`https://raw.githubusercontent.com/Sonarr/Sonarr/develop/src/NzbDrone.Core/Download/Clients/QBittorrent/QBittorrent.cs`（下稱 `QBittorrent.cs`）、同目錄 `QBittorrentProxyV2.cs`（下稱 `Proxy.cs`）、`src/NzbDrone.Core/Localization/Core/en.json`、`src/NzbDrone.Core/HealthCheck/Checks/RemotePathMappingCheck.cs`。

### 表單與 Test

| 項目 | 內容 | 證據 |
| --- | --- | --- |
| 我有核對到的欄位 | Host（錯誤綁在 Host）、TvCategory、TvImportedCategory、RecentTvPriority、OlderTvPriority | `QBittorrent.cs:490, 521-545, 553-568` |
| 其餘欄位（port、帳密、SSL 等） | 沒有逐一開設定類別核對，不在此列 | |
| Test 的流程 | `TestConnection()`，有錯就停；再 `TestCategory()`、`TestPrioritySupport()`、`TestGetTorrents()` | `QBittorrent.cs:417-429` |
| Test 對 qBittorrent 寫了什麼 | **只有一件**：分類不存在時 `AddLabel`（`/api/v2/torrents/createCategory`）；建完再讀一次，沒建成回報「Configuration of category failed」（綁 TvCategory 欄位） | `QBittorrent.cs:523-545`；`Proxy.cs:215` |
| 全域偏好 | **沒有任何寫入**。`QBittorrentProxyV2.cs` 呼叫的端點只有 `webapiVersion`、`version`、`app/preferences`、`torrents/info`、`properties`、`files`、`add`、`delete`、`setCategory`、`createCategory`、`categories`、`setShareLimits`、`topPrio`、`setForceStart`、`auth/login`；其中 `app/preferences` 是讀（`GetConfig`），**沒有 `app/setPreferences`**；`setShareLimits` 是逐 torrent | `Proxy.cs` 中每個 `.Resource("…")`：`:31, 74, 82, 91, 99, 112, 130, 139, 148, 170, 192, 206, 215, 223, 288, 312, 334, 452` |
| 讀偏好用來幹嘛 | 只用來發警告：優先權設了但 qBittorrent 沒開佇列 → 驗證失敗；做種比例 / 時間設定會刪完成的 torrent → `RemovesCompletedDownloads` | `QBittorrent.cs:412-415, 549-568`；`en.json:506` |
| Save | Save 時自動再測，失敗不建立；警告可 Save Anyway（上一輪已有） | 上一輪 §E，`ProviderControllerBase.cs` |

### 設定不對時怎麼告訴使用者

| 情況 | 訊息 | 位置與證據 |
| --- | --- | --- |
| 連不上（WebUI 沒開、位址 / port 錯） | 欄位錯誤「Unable to connect to qBittorrent」＋說明「Please verify the hostname and port.」 | 綁 Host 欄。`QBittorrent.cs:487-492`；`en.json:565-566` |
| 佇列沒開卻用了優先權 | 欄位錯誤綁在優先權欄；說明「Torrent Queueing is not enabled in your qBittorrent settings. Enable it in qBittorrent or select 'Last' as priority.」 | **只告訴使用者去 qBittorrent 改，或改選 Sonarr 這邊的設定**，不代為開啟。`en.json:506` |
| 容器內看不到下載路徑 | Health 頁錯誤：「You are using docker; download client {name} places downloads in {path} but this directory does not appear to exist inside the container. Review your remote path mappings and container volume settings.」；路徑在容器內不是合法路徑則另一則 BadDocker 訊息 | `RemotePathMappingCheck.cs`；`en.json:1685-1686`。檢查在匯入失敗事件後、download client / Remote Path Mapping 異動時重跑（`:21-24` `CheckOn`），不是 Test 時就抓 |
| 路徑等於 qBittorrent 的根下載夾 | 匯入失敗訊息提示 Keep top-level folder / Torrent Content Layout | `QBittorrent.cs:323`；`en.json:496` |

結論：Sonarr 對 qBittorrent 的立場是 **只建一個分類、其他全域設定唯讀，不對就說「請你去 qBittorrent 改」**；路徑問題另有 Remote Path Mapping 機制（由使用者建立）。Berth 建 Route 時就檢查容器掛載並給補法，比 Sonarr 的 Health 檢查（匯入失敗後才檢）更早。

## 2.3 Seerr（Overseerr 與 Jellyseerr 合併後）

原始檔：`https://raw.githubusercontent.com/seerr-team/seerr/develop/` 下的 `src/components/Setup/index.tsx`、`server/routes/auth.ts`、`server/api/jellyfin.ts`、`server/api/servarr/sonarr.ts`、`server/entity/MediaRequest.ts`、`src/components/Settings/SonarrModal/index.tsx`、`docs/using-seerr/settings/{mediaserver.mdx,services.md}`、`src/i18n/locale/en.json`。

| 項目 | 內容 | 證據 |
| --- | --- | --- |
| 精靈步數 | **4 步**：選媒體伺服器類型 → 登入 → 設定媒體伺服器（挑媒體庫）→ 設定服務（Radarr / Sonarr，可不加）→ 「Finish Setup」 | `Setup/index.tsx:27-39, 141-166, 266-283`；`en.json:1333-1347` |
| 連 Jellyfin 要什麼 | 位址（新版 Internal URL，舊版 hostname + port + SSL）、**管理員**帳密（文件：「make sure you log in using an account with administrative privileges」）、一個電郵（只用於通知與本地登入，**不綁** Jellyfin 帳號） | `docs/using-seerr/settings/mediaserver.mdx`（Jellyfin tab） |
| 對 Jellyfin 寫了什麼 | 首次管理員登入時，用管理員身分 `POST /Auth/Keys?App=Seerr` 建一把 API key，再讀出來存進 Seerr 自己的設定，之後都用它（與 Berth 建 API key「Berth」同一做法） | `auth.ts:419-431`；`jellyfin.ts:586-589`（`createApiToken(appName)`） |
| 不寫什麼 | `jellyfin.ts` 中 `post(` 只有這一處；媒體庫只是勾選要掃描哪些，不改 Jellyfin 的媒體庫 | `jellyfin.ts` 全檔搜尋 |
| 連 Sonarr / Radarr 要什麼 | hostname 或 IP、port、API key、（選用）URL base、品質 profile、root folder、最低可用性；文件：「all of these options are required, and that requests will fail if any of these are not configured」。測試成功後才列 profile 與 root folder（上一輪已有） | `docs/using-seerr/settings/services.md` |
| 對 Sonarr 寫了什麼 | (1) 建立請求時 `addSeries`；**該劇若已在 Sonarr 裡，直接更新既有 series**：改 `monitored`、把 tag 合併進既有 tags、重算 seasons（`PUT /series`）。(2) 只有勾了 **Tag Requests** 才在 Sonarr 建 tag（請求者 ID 與顯示名稱），`createTag` 在建立請求時才呼叫；預設 `false` | `sonarr.ts:210-224`；`MediaRequest.ts:668-692`；`SonarrModal/index.tsx:263`；`en.json:1159-1160`：「Automatically add an additional tag with the requester's user ID & display name」 |
| 怎麼告訴使用者 | tag 行為寫在勾選框的說明文字；其餘靠文件。Test 失敗的訊息文字我未逐條核對 | |

## 2.4 Home Assistant onboarding 與 integration config flow

### Onboarding

| 項目 | 內容 | 來源 |
| --- | --- | --- |
| 步數 | 5 步：(1) 開啟位址（Container 為 `http://<host>:8123`；首次要「Preparing Home Assistant」，下載約 700 MB）(2) 建立擁有者帳號（名稱、帳號、密碼；或從備份還原）(3) 家的位置（設時區、單位、幣別、建 home zone）(4) 選擇分享的匿名資料（預設關）(5) 完成，進入預設 dashboard | `https://www.home-assistant.io/getting-started/onboarding/`（原始檔 `home-assistant.io` repo `source/getting-started/onboarding.markdown`） |
| 備註 | 擁有者帳號「There is no way to recover the owner credentials」。目前的 onboarding 文件沒有「發現到的裝置」這一步；發現的整合在之後的 Settings → Devices & services 出現，這句我沒有找到官方 onboarding 頁面佐證：查不到 | 同上 |

### Config flow：發現 → 確認 → 驗證 → 建立

| 階段 | 機制 | 來源 |
| --- | --- | --- |
| 觸發 | flow 的 source：`user`（使用者手動）、`zeroconf` / `ssdp` / `usb` 等（發現）、`reauth`（憑證失效時由整合觸發）、`reconfigure`（使用者重新設定） | `https://developers.home-assistant.io/docs/config_entries_config_flow_handler/`（source 表） |
| 確認 | 被發現的裝置先顯示確認表單才建立（`discovery_confirm`）：這次沒有逐條引用該頁的確認段落，只確認 source 表 | 同上 |
| 驗證 | 品質規則 test-before-configure：建立前先連線測；`test-before-setup`：載入時暫時連不上用 `ConfigEntryNotReady` 稍後重試，憑證錯用 `ConfigEntryAuthFailed` 觸發 reauth（提示使用者重新驗證，不是重跑設定） | 上一輪 §E（test-before-configure）；`https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/test-before-setup/` |
| 建立 | 驗過才 `create_entry` | 上一輪 §E |

### integration 會不會反過來改裝置設定：兩個實例

| 例子 | 寫什麼 | 條件 | 怎麼告知使用者 | 證據 |
| --- | --- | --- | --- | --- |
| **Shelly Gen2+**（電池供電裝置） | 在裝置上啟用 outbound WebSocket 並把 server 指向 HA（`update_outbound_websocket(ws_url)`） | 只在裝置的 ws `server` 為空，或未啟用時才寫；已啟用並指向別處的不覆蓋，文件要求使用者手動處理 | 文件：「may need manual outbound WebSocket configuration if Home Assistant cannot correctly determine your instance's internal URL, or if the outbound WebSocket was previously configured for a different Home Assistant instance」。程式端的自動寫入我沒找到 UI 提示 | `home-assistant/core` `homeassistant/components/shelly/coordinator.py:763-774`；`home-assistant.io` `source/_integrations/shelly.markdown:105-111` |
| **Shelly Gen1** | **不寫**。使用者要在裝置網頁勾 Enable CoIoT、填 CoIoT peer（HA 位址:5683）、手動重啟裝置 | | 整合開 repair issue（推播收不到時）；文件：「Home Assistant will display a repair issue for the Shelly device if push updates … do not reach」，並說可忽略該 issue | `shelly.markdown:88-103` |
| **Reolink** | 登入後若裝置的 RTSP / ONVIF / RTMP 沒開，「trying to enable it」，呼叫 `set_net_port` 打開（裝置的全域網路服務開關）；另註冊 ONVIF webhook 訂閱事件 | 需要管理員等級帳號：不是 admin 時 config flow 報 `not_admin`「User needs to be admin」 | 開啟失敗只記 log；**webhook 打不到 HA** 時開 repair issue `webhook_url`「Reolink webhook URL unreachable」，內容教使用者去 Settings → System → Network 設 Home Assistant URL；並自動降級成輪詢（文件：TCP push → ONVIF push → ONVIF long polling → fast polling，用偵測到可行的最快者）。官方文件有沒有明說「會自動開啟 RTSP / ONVIF」：查不到 | `reolink/host.py:236-270`；`reolink/strings.json:7-15, 1015-1018`；`reolink.markdown:131-132` |
| Synology DSM、UniFi | 本輪沒有查：查不到 | | | |

## 2.5 「自動在別人的服務裡建東西」與宣告式工具

### Prowlarr Apps → Sonarr（上一輪已有三級同步，補原始碼與文案）

| 項目 | 內容 | 證據 |
| --- | --- | --- |
| 同步等級文案 | `SyncLevelAddRemove`：「When indexers are added or removed from {appName}, it will update this remote app.」；`SyncLevelFull`：「Will keep this app's indexers fully in sync. … Any change made to indexers remotely within this app will be overridden by {appName} on the next sync.」（Disabled 的說明字串我沒在 `en.json` 找到：查不到） | Prowlarr `src/NzbDrone.Core/Localization/Core/en.json:715-717` |
| 對使用者原有標籤 | 同步時保留非 Prowlarr 的使用者 tag（程式註解「Retain user tags not-affiliated with Prowlarr」） | Prowlarr `src/NzbDrone.Core/Applications/Sonarr/Sonarr.cs:199-200` |
| 存檔時的驗證 | 位址 / URL base 錯在欄位上說明：「Sonarr URL is invalid, Prowlarr cannot connect to Sonarr - are you missing a URL base?」 | `Sonarr.cs:63-69` |
| 長期失敗 | Health：「Applications unavailable due to failures for more than 6 hours: {0}」 | `en.json:55-56` |

### Buildarr（宣告式，寫入外部服務）

| 項目 | 內容 | 來源 |
| --- | --- | --- |
| 預設保守 | 每種資源都有 `delete_unmanaged`，預設 `false`；沒有定義就不動既有項目。文件原文：「Buildarr will not modify existing release profiles, but if `delete_unmanaged` is `True`, Buildarr will delete all existing profiles. Be careful when using `delete_unmanaged`.」 | `https://buildarr.github.io/plugins/sonarr/configuration/profiles/release` |
| 警告方式 | 欄位說明裡的 Be careful；Prowlarr 通知頁另有「Take care when using this option, as it can remove connections automatically managed by other applications.」 | `https://buildarr.github.io/plugins/prowlarr/configuration/settings/notifications` |
| 撤回 | 設定檔是來源，改設定檔再跑。沒有「反向還原」的說明：查不到 | |

### Recyclarr（把 TRaSH 指南同步進 Sonarr / Radarr）

| 項目 | 內容 | 來源 |
| --- | --- | --- |
| 預覽 | `-p` / `--preview`：「won't update your actual instance configuration」，API 只用來讀取 | `https://recyclarr.dev/wiki/cli/sync/` |
| 刪除 | `delete_old_custom_formats` 預設關；只刪 Recyclarr 自己同步過的 custom format（以 Sync State 追蹤），手動建的「will not be deleted」 | `https://recyclarr.dev/wiki/yaml/config-reference/custom-formats/` |
| 接管同名物件 | 設定中的 custom format 若與服務裡已有的同名，「Recyclarr automatically adopts and updates it」，即手動調過的同名項目會被覆寫；要保留手動控制就別把它的 trash ID 放進設定 | 同上 |
| 其他 | 該頁沒有寫確認提示；預覽是唯一安全網 | 同上 |

Unpackerr、Bazarr 本輪未查：查不到。

## 2.6 光譜

依「寫」的對象侵入程度分級；每列附本輪或上一輪的實例。

| 級 | 定義 | 實例 | 怎麼告知使用者 | 怎麼撤回 |
| --- | --- | --- | --- | --- |
| L0 | 只讀；不對就說「請你去改」 | Sonarr 對 qBittorrent 的全域偏好：佇列沒開 → 欄位錯誤「Enable it in qBittorrent or select 'Last' as priority」；Remote Path Mapping 的 Health 訊息 | 欄位錯誤＋ Health 頁 | 不需要，沒有寫 |
| L1 | 在對方服務裡**只建自己用的新物件** | Sonarr 建 qBittorrent 分類（Test 時）；Seerr 建 Jellyfin API key「Seerr」；Prowlarr（Add and Remove Only）在 Sonarr 建它的 indexer；Seerr 在 Sonarr 建 tag（Tag Requests 勾選時） | 多半不特別告知；Seerr 的 tag 有勾選框說明文字 | 各產品怎麼清理這些物件（刪 download client 後分類是否保留、刪 Seerr 後 key 是否保留）：**查不到** |
| L2 | 改**使用者既有的物件**或覆寫 | Seerr `addSeries` 對 Sonarr 裡已有的劇合併 tag、改 monitored、重算 seasons；Prowlarr Full Sync「Any change made … remotely … will be overridden」；Recyclarr 接管同名 custom format | Prowlarr：同步等級由使用者選，文案明講覆寫；Seerr：無，行為在請求時才發生；Recyclarr：文件寫「adopts and updates」 | Prowlarr：把同步等級改回 Add and Remove（Disabled 的說明查不到）；其餘查不到 |
| L3 | 改**對方的全域 / 裝置設定** | HA Shelly Gen2 電池裝置：在裝置寫 outbound WebSocket（只在未設時）；HA Reolink：開 RTSP / ONVIF / RTMP、註冊 ONVIF webhook | Shelly：文件提到；Reolink：失敗時 repair issue，成功時無提示。兩者的寫入都是整合運作的通道（沒有它資料進不來），且有降級路徑（輪詢）或「不覆蓋已設定的」條件 | 查不到（移除 integration 時是否還原裝置設定，本輪沒查） |
| L4 | 宣告式管理整個服務 | Buildarr、Recyclarr | 使用者自己寫設定檔就是明示授權；Recyclarr `--preview`；Buildarr `delete_unmanaged` 預設 false 與 Be careful 文案 | 改設定檔再跑；Recyclarr 靠 Sync State 只刪自己建的 |

同一產品常跨級：Seerr 對 Jellyfin 是 L1，對 Sonarr 是 L1＋ L2；HA 同時有 L0（Shelly Gen1：只開 repair 讓你手動改）與 L3（Gen2）。

## 2.7 與 D1 的關係（我的歸納，不是決定）

1. **最接近 Berth 情境的先例（Sonarr 與 qBittorrent、Seerr 與 Jellyfin）都在 L0–L1。** Sonarr 對 qBittorrent 的全域偏好只讀，錯了教使用者去改；Seerr 對 Jellyfin 只建一把 API key。Berth 現行 D1（API key「Berth」、`berth-*` 分類、使用者勾選的站）與這兩者同級。
2. **這些產品裡「自動完成需要的設定」實際上是 L1：建自己的物件。** 使用者感覺「自動」來自「測試通過 = 完成」「錯誤綁欄位」「錯了給一句教你怎麼改」，不是因為寫了對方的全域設定。這與使用者的理想流程（填位址帳密 → 檢測 → 說清楚或自動完成）不衝突；衝突只在「能接入就自動改全域設定」這半句。
3. **有寫全域 / 裝置設定的先例（L3：Shelly、Reolink）的共同點**：該設定是整合運作的唯一通道、條件寫入（只在未設時，不覆蓋別人設好的）、有降級或 repair issue 告知。Berth 目前沒有「沒有這項全域設定就不能運作」的情況（brief §16.4：送單逐個 torrent 帶 `autoTMM` 與分類；上一輪 E-1 已記錄這三個全域鍵不影響 Berth），所以 L3 的前提不成立。
4. **Berth 有一項比上述 L1 先例更侵入的寫入：在既有 Jellyfin 的使用者媒體庫上加一條 Berth 路徑**（brief §16.4）。本輪找不到成熟產品對「使用者既有的媒體庫」做同類寫入（Seerr 只讀媒體庫；Sonarr / Prowlarr 的對象是 client / indexer，不是使用者的資料目錄）：查不到先例。D1 對這項的保護是「舊路徑不動、使用者勾選才加」。
5. **成熟產品在「怎麼撤回」上普遍是弱項**：Seerr 的 key、Sonarr 的分類、Prowlarr 的 indexer 在對方服務裡怎麼清理，本輪都沒找到官方文件；做得最明確的是宣告式工具（Recyclarr 預覽＋只刪自己同步過的、Buildarr 的 `delete_unmanaged`）。上一輪 E-7（換台時列出遺留物）在這個光譜上比多數產品更進一步。
6. **對精靈步數的啟示**：Jellyfin 精靈 6 頁、HA onboarding 5 步、Seerr 4 步；Seerr 的 Radarr / Sonarr 可不加、HA 的整合在 onboarding 之後才加。Berth 精靈 6 頁，三個服務頁都必選，TMDB 不可略過，結構上比 Seerr / HA「必要的少、其餘後補」更重；是否調整是產品決定。

---

## 來源總表

- Jellyfin：`https://jellyfin.org/docs/general/installation/container/`、`https://jellyfin.org/docs/general/post-install/setup-wizard/`
- Immich：`https://docs.immich.app/install/docker-compose`、`https://raw.githubusercontent.com/immich-app/immich/main/docs/docs/partials/_docker-compose-install-steps.mdx`
- Seerr：`https://docs.seerr.dev/getting-started/docker`、`https://docs.seerr.dev/using-seerr/settings/mediaserver`、`https://docs.seerr.dev/using-seerr/settings/services`；原始碼 `https://github.com/seerr-team/seerr`（develop：`src/components/Setup/index.tsx`、`server/routes/auth.ts`、`server/api/jellyfin.ts`、`server/api/servarr/sonarr.ts`、`server/entity/MediaRequest.ts`、`src/components/Settings/SonarrModal/index.tsx`、`src/i18n/locale/en.json`）
- Home Assistant：`https://www.home-assistant.io/installation/linux/`、`https://www.home-assistant.io/getting-started/onboarding/`、`https://developers.home-assistant.io/docs/config_entries_config_flow_handler/`、`https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/test-before-setup/`、`https://www.home-assistant.io/integrations/shelly/`、`https://www.home-assistant.io/integrations/reolink/`；原始碼 `https://github.com/home-assistant/core`（`homeassistant/components/shelly/coordinator.py`、`homeassistant/components/reolink/host.py`、`homeassistant/components/reolink/strings.json`）
- Sonarr：`https://github.com/Sonarr/Sonarr`（develop：`src/NzbDrone.Core/Download/Clients/QBittorrent/QBittorrent.cs`、`QBittorrentProxyV2.cs`、`src/NzbDrone.Core/Localization/Core/en.json`、`src/NzbDrone.Core/HealthCheck/Checks/RemotePathMappingCheck.cs`）
- Prowlarr：`https://github.com/Prowlarr/Prowlarr`（develop：`src/NzbDrone.Core/Localization/Core/en.json`、`src/NzbDrone.Core/Applications/Sonarr/Sonarr.cs`）
- Buildarr：`https://buildarr.github.io/plugins/sonarr/configuration/profiles/release`、`https://buildarr.github.io/plugins/prowlarr/configuration/settings/notifications`
- Recyclarr：`https://recyclarr.dev/wiki/cli/sync/`、`https://recyclarr.dev/wiki/yaml/config-reference/custom-formats/`
- Docker Compose `configs.content`：`https://docs.docker.com/reference/compose-file/configs/`（讀的是 `docker/docs` 原始檔 `content/reference/compose-file/configs.md`）
- 上一輪 §E 來源：`docs/research/wizard-audit-2026-10-06.md:601-611`
