# Berth

自託管的媒體取得與入庫協調器：把索引站或 RSS 命中的 torrent 送到 qBittorrent，下載完成後解析、比對 TMDB，以硬鏈接入庫到 Jellyfin，並維護可修復的帳本。

**M1（手動全流程）已完成**：探索 → 搜 torrent → 送單 → 下載 → 解析比對 → 硬鏈接入庫 → Jellyfin 找到它，一部美劇一季、一部動漫一季、一部電影都不經人工走完（nightly 的 e2e 對真的服務守著這一條）。**M1.5（媒體庫瀏覽）也已完成**：媒體庫是一個 Jellyfin 媒體庫一頁、瀏覽整個媒體庫（不只 Berth 經手的），繼續觀看與下一集、已看 / 未看與切換、依類型與年份排序篩選、Jellyfin 的圖由 Berth 代理，Media 詳情最上面是觀看區；權限一律由 Berth 自己對 Jellyfin 的允許清單擋，播放仍深連結到 Jellyfin。**M2（修正與對帳）也已完成**：審核佇列（低信心的計劃逐列改後核准、medium 自動入庫的一鍵確認或撤銷、對不到的檔案指派、重複版本）、修正已入庫的檔案、可組合的刪除範圍、每日與手動的對帳（Jellyfin 裡刪掉的、complete 裡少了的、被複製品取代的硬鏈接都偵測得到並一鍵修）、重新入庫與 `berth rebuild-ledger`、Job 詳情頁；審核與修正只有管理員做得了。RSS 自動追番（M3）做到第一段：`/rss` 加 Mikan 的聚合 feed、把新出現的作品 × 字幕組綁到作品與 Route，之後的新集自動送單入庫，認得出的作品自動綁定，合集與自己不要的版本用三層排除條件擋下、同一個 torrent 與媒體庫裡已有的版本不重複下載；補舊集與其他來源還沒有。設計與決定見 `docs/design-brief.md`，架構與里程碑見 `docs/plan.md`，名詞表見 `CONTEXT.md`。

## 部署

`deploy/` 是完整的 compose 套件：Berth 加 qBittorrent、Jellyfin、Prowlarr，四個容器掛同一個媒體根。Linux 與 Windows 共用同一份 `docker-compose.yml`。

```bash
cd deploy
cp .env.example .env        # 改 DATA_ROOT 與 CONFIG_ROOT；port 撞到了再改五個 *_PORT
docker compose up -d
```

開 <http://localhost:8383>，之後所有設定都在 Berth 的精靈裡完成，不需要分別打開另外三個服務的介面。
**唯一要離開 Berth 的一步是 TMDB 的 API key**，見下面的〈先申請一把 TMDB API key〉。

精靈是八個步驟、五個泊位：

| 泊位 | 步驟 | 套件內的服務 | 你自己的服務 |
| --- | --- | --- | --- |
| — | 1–2 建立 Berth 管理員、逐服務探測 | 探到 compose 主機名就是套件內；還在啟動的顯示「探測中」，自己等到起來（上限 2 分鐘），不必按重新探測 | 探不到就填位址，就地測連線 |
| BTH 1 | 3 Jellyfin | 確認版本 ≥ 12.0、建管理員、建清單上的媒體庫（預設 Movies / TV / Anime，可改名、增刪）、API key | 只做檢查；「加入 Berth 路徑」是一顆要確認的按鈕 |
| BTH 2 | 4 qBittorrent | 套用五個建議鍵、設 WebUI 密碼 | 先顯示逐鍵差異再問要不要套用 |
| BTH 3 | 5 媒體庫路徑 | 走到就替每個媒體庫自動建一條 Route、跑五條檢查 | 勾選媒體庫與寫入目標 |
| BTH 4 | 6 索引站 | 加九個預設公開站（每一站標出語言），加完試搜、不要的移除 | 填既有 Prowlarr 或任一 Torznab 網址，接上之後同樣可以試搜 |
| BTH 5 | 7 TMDB | 貼你自己的 API key 並測試 | 同左 |
| — | 8 完成 | 說出跳過了什麼、在哪裡補 | 同左 |

索引站那一步可以按「之後再說」（沒接只是搜尋不到東西）；**TMDB 那一步不行** —— 沒有一把測得過的憑證就沒有標題、季集與封面，精靈停在第 7 步。

每條 Route 建立時都會**真的建一個硬鏈接再比對 inode**，三個容器看到的不是同一個檔案系統就當場失敗，並指出是哪個容器少了哪個掛載。全部綠燈才走得到下一個泊位——所以掛載設錯在第 5 步就會知道，不必先去申請 TMDB key。

每個泊位做完都停在結果上，按「前往下一個泊位」才走；泊位板上走過的格子點得回去，每一頁都有「上一個泊位」。

設定完成後精靈關閉，之後用 Jellyfin 的帳號登入；健康頁 `/health` 每 5 分鐘重跑同一組檢查。

### 頁面

| 頁面 | 做什麼 |
| --- | --- |
| 探索 `/` | TMDB 的趨勢、熱門與搜尋。每一格連到那部作品的詳情 |
| Media 詳情 `/media/:id` | 季集表；向索引站搜 torrent，結果表附 Tags 與預估季集；選 Route 送單（送出前印出會用的資料夾名）；已入庫的檔案、版本與 Jellyfin 找到了沒 |
| 下載 `/jobs` | 送單之後的每一筆，狀態與進度即時更新；展開看時間線與匯入計劃（逐檔的處置、信心、目標路徑與理由），送單失敗、入庫失敗、待審各有自己的下一步 |
| 媒體庫 `/library/:library` | 一個 Jellyfin 媒體庫一頁，只列你在 Jellyfin 看得到的：整庫 50 部一頁（不是 Berth 入庫的也在，海報是 Jellyfin 的、經 Berth 轉給瀏覽器），Berth 經手的疊上入庫了幾集、哪一部在等人；每一格說得出你看到哪了（已看、看到幾 %、剩幾集沒看），可標為已看 / 未看（寫回你在 Jellyfin 的紀錄，標為未看先確認）；還沒進 Jellyfin 的另列一條；「在 Jellyfin 開啟」；「待審」「Unmatched」兩個篩選 |
| 健康 `/health` | 四項健康檢查與下載迴圈；一般使用者也看得到 |
| 設定 `/settings/*` | 只有管理員。精靈只管第一次，跑完之後改東西都在這裡，一格泊位一頁：**Jellyfin**（健康與重新檢查、既有那一台的位址與重新登入、對外網址）、**qBittorrent**（健康、既有那一台的位址與帳密、建議設定的差異與還原、磁碟空間門檻）、**媒體庫路徑**（Route 的新增——同一個 Jellyfin 媒體庫可以有第二條——改名、停用、重新檢查與刪除）、**索引站**（加站、試搜、移除；既有 Prowlarr / Torznab 換網址或 key）、**TMDB**（換 key 並測試）。精靈跑完之後打開 `/setup` 會被帶到這裡 |

> **compose 範本 pin 的 `ghcr.io/1morr/berth:latest` 還是空的。** GHCR 上目前只有預發佈的 `0.1.0-rc1`（`:latest` 要等第一個正式版本 tag），所以現在要跑 compose 得先在 repo 根目錄自己 build 一份：見下面的〈自己 build image〉。

| 服務 | `.env` 變數（預設） | 備註 |
| --- | --- | --- |
| Berth | `BERTH_PORT`（8383） | 唯一需要開的介面 |
| qBittorrent | `QBITTORRENT_WEBUI_PORT`（8080）、`QBITTORRENT_BT_PORT`（6881） | WebUI 要密碼，密碼在精靈裡設定。兩個 port 都是容器內外同一個號碼 |
| Jellyfin | `JELLYFIN_PORT`（8096） | 「在 Jellyfin 開啟」開的就是這個 port |
| Prowlarr | `PROWLARR_PORT`（9696） | |

port 跟這台機器上別的東西撞到時（同一台還跑著另一套 Berth、開發環境），改 `.env` 的這五個變數再
`docker compose up -d`，**不要改 compose 檔**。`.env` 只放這五個 Berth 在容器裡看不到的宿主端事實；
服務位址與憑證、下載目錄、媒體庫路徑都在精靈與設定頁裡改（brief §19）。
**`QBITTORRENT_WEBUI_PORT` 要在跑精靈之前定下來**：Berth 連套件內 qBittorrent 的位址是精靈第 2 步探到、
第 4 步存下的那一條，之後再改這個變數不會跟著走。

已經有其中某個服務的人，把它從 `.env` 的 `COMPOSE_PROFILES` 拿掉，精靈會改用「既有服務」的表單接入；`berth` 沒有 profile，永遠會啟動。變數清單見 `deploy/.env.example`，裡面沒有任何秘密欄位。

### 先申請一把 TMDB API key

Berth **不內建任何 provider 的 API key**，TMDB 的憑證要你自己申請 —— 專案不替所有使用者背一把
共用憑證。它是必要的：作品標題、季集結構與封面全部來自 TMDB，沒有它精靈走不完。
**這台機器也要連得到 `api.themoviedb.org`**：第 7 步真的打一次 TMDB 驗憑證，被防火牆擋住的話精靈同樣走不完。

1. 在 <https://www.themoviedb.org/signup> 註冊一個免費帳號（要收驗證信）。
2. 開 <https://www.themoviedb.org/settings/api>，申請 API key，用途（Type of Use）選
   **Personal / Education**；應用資訊隨便填得過去即可。核發是即時的，不必等審核。
3. 那一頁同時給兩把東西：**API Key (v3 auth)** 是 32 個十六進位字元，**API Read Access Token
   (v4 auth)** 是很長的一串 JWT。**兩種 Berth 都收**，貼哪一把都成立（v4 走標頭，不會落在
   任何一行 log 裡）。
4. 精靈第 7 步貼上去按「測試 TMDB」，綠燈才走得到下一個泊位。之後要換一把就在
   「設定 → TMDB」重貼：新的那一把測得過才換掉舊的，測不過的話舊的照舊在用。

TMDB 的條款限非商業使用；歸屬聲明見〈[授權與歸屬](#授權與歸屬)〉。

### 硬鏈接前提

入庫是硬鏈接不是複製，所以：

- **只掛一個媒體根**：下載目錄與媒體庫都要在 `DATA_ROOT` 底下。分成兩個 bind mount 會得到 `EXDEV`，建立 Route 時的檢查會直接擋下來。
- **檔案系統要支援硬鏈接**：exFAT 不行；btrfs 子卷、ZFS dataset、mergerfs branch 之間也不行，它們在核心眼中是不同的裝置。
- **同一台機器**：Berth 與 qBittorrent 要看得到同一份檔案，跨主機與 remote path mapping 不支援。

### 支援的宿主平台

- **Linux**（NAS 與伺服器）：`DATA_ROOT` 要能被 `PUID` / `PGID` 寫入，例如 `chown -R 1000:1000 /srv/berth/data`。Berth 只在媒體根還是空目錄時自動接手擁有者；已經有內容的目錄一律不碰。
- **Windows**（Docker Desktop、WSL2 後端）：用一般的 bind mount 就好（`DATA_ROOT=C:\Berth\data`），不需要 named volume，NTFS 上的硬鏈接實測可用（brief §20.7）。`PUID` / `PGID` 在這種掛載上沒有意義，維持預設即可。

實際跑過整套流程的環境（2026-09-08 的 M0 驗收）：Windows Docker Desktop 的 NTFS bind mount，以及 Docker Desktop 那個 Linux VM 上的 ext4。**原生 Linux 宿主與 NAS 還沒有人跑過**——理論上同一條路徑，但沒有實測就不當成驗過。

### 外部服務的前提

- **qBittorrent**：最低 4.4（Web API 2.8.4）。套件內的容器由 `deploy/preseed/qbittorrent/10-berth.sh` 在服務啟動前補上免密白名單，而且只放行 Berth 那一個固定 IP —— 4.6.1 起首次啟動的隨機密碼只印在容器 log，沒有這一步 Berth 進不去；WebUI 從宿主或 LAN 進來仍然要密碼。其餘偏好（temp path、save path、category 的 autoTMM）與 WebUI 密碼由精靈經 API 設定，按之前會顯示差異。腳本不覆蓋任何已經有值的設定。
- **Jellyfin**：**最低 12.0**（12.0 就是原本的 10.12 —— Jellyfin 把版號前面永遠不變的 `10` 拿掉了）。12.0 起同一集的多個版本由 Jellyfin 自己合併成一個條目，不需要任何插件；10.x 要靠第三方插件，而那個插件在 12 上是空跑、還會跨媒體庫誤併，所以 Berth 只支援 12 以上。更舊的伺服器在精靈第 3 步與健康頁都是紅燈，不會被接進來。
  - **從 10.x 升上來**：10.10.7 與任何 10.11.x 都可以直接升，不必經過中繼版本。**升級前**把 Jellyfin 的 `${CONFIG_ROOT}/jellyfin` 完整備份 —— 12 改了資料庫，降不回去，只能還原備份；再移除第三方插件，10.11 的插件在 12 載入不了。**升級後**完整掃描一次媒體庫，自動分組的版本才會回來。
  - **套件內的 Jellyfin 釘在 `version-12.1ubu2604`**：`docker compose pull` 只會拿到 12.1 這條線的重建，不會默默跨到下一個大版本。要升級時先備份上面那個目錄，再改 `deploy/docker-compose.yml` 的 tag 並 `docker compose up -d jellyfin`。
- **Prowlarr**：不預置任何東西，Berth 唯讀掛載它的設定目錄以讀取它自動產生的 API key。
- **TMDB**：要你自己申請一把 API key（上面那一節），Berth 不內建。憑證存在 Berth 自己的資料庫裡，
  精靈第 7 步或「設定 → TMDB」都改得了。

### 秘密與備份

各服務的 API key 與密碼存在 `${CONFIG_ROOT}/berth/berth.db`，靠檔案權限保護，不做應用層加密（與 Seerr 相同）。備份 Berth 就是複製 `${CONFIG_ROOT}/berth`。

### 自己 build image

```bash
docker build -f deploy/Dockerfile -t ghcr.io/1morr/berth:latest .
```

發佈由 `.github/workflows/release.yml` 在 `v*` tag 上推到 GHCR。

### 部署疑難排解

image 裡沒有 curl。要從 Berth 這一端測外部服務時：

```bash
docker compose exec berth python -c \
  "import urllib.request; print(urllib.request.urlopen('http://qbittorrent:8080/api/v2/app/version').read())"
```

（8080 換成你的 `QBITTORRENT_WEBUI_PORT`。）

**qBittorrent 的 WebUI 回 `Unauthorized`：改 `QBITTORRENT_WEBUI_PORT`，不要手改 compose 檔。**
qBittorrent 的 Host 檢查除了網域還會比對 port，而且 `WebUI\ServerDomains=*` 也不放過 port 不符的請求。
手動把 compose 的發佈 port 改成 `18080:8080` 之類的偏移之後，瀏覽器開 `http://localhost:18080` 只會看到
`Unauthorized`，真正的原因（`Invalid Host header, port mismatch`）只寫在 `docker compose logs qbittorrent`
裡。`QBITTORRENT_WEBUI_PORT` 會把容器內外兩側與 qBittorrent 自己的 `WEBUI_PORT` 一起換成同一個號碼。
**不要**用 `WebUI\HostHeaderValidation=false` 繞過：那是 qBittorrent 防 DNS rebinding 的那一道。

## 環境需求

| 工具 | 版本 | 用途 |
| --- | --- | --- |
| [uv](https://docs.astral.sh/uv/) | ≥ 0.12 | 後端套件與虛擬環境管理 |
| Python | 3.13（由 `.python-version` 指定，uv 會自動下載） | 後端執行環境 |
| Node.js | ≥ 24 | 前端建置 |
| [pnpm](https://pnpm.io/) | ≥ 11 | 前端套件管理 |

## 開發指令

本檔是所有指令的單一來源；新增或改動指令時同輪更新這裡。

### 安裝

```bash
uv sync                     # 後端依賴與虛擬環境
pnpm -C web install         # 前端依賴
uv run pre-commit install   # 啟用 git hook（選用但建議）
cp .env.example .env        # 本機的 CONFIG_ROOT / DATA_ROOT
```

### 啟動

```bash
pnpm -C web build                                   # 前端產物（後端會提供它）
uv run --env-file .env berth serve                  # http://localhost:8383
```

開發時前後端分開跑，Vite 代理 `/api` 到後端：

```bash
uv run --env-file .env berth serve --reload         # 後端，改 .py 自動重啟
pnpm -C web dev                                     # 前端，開 Vite 印出的網址
```

### 環境變數

`.env.example` 是完整清單；每一個都有預設值，本機開發只需要覆寫前兩個。

| 變數 | 預設 | 用途 |
| --- | --- | --- |
| `CONFIG_ROOT` | `/config` | `berth.db`、設定與 log。啟動時自動建立並套用 migration |
| `DATA_ROOT` | `/data` | 媒體根：incomplete、complete 與媒體庫路徑都在它底下 |
| `PORT` | `8383` | 對外的唯一 port |
| `JELLYFIN_PORT` | `8096` | 套件內 Jellyfin 在宿主上發佈的 port；「在 Jellyfin 開啟」沒填對外網址時開這個 port。compose 從 `deploy/.env` 的同名變數傳進來 |
| `QBITTORRENT_WEBUI_PORT` | `8080` | 套件內 qBittorrent 的 WebUI port（容器內外同一個號碼）；精靈第 2 步探 `http://qbittorrent:<它>`。compose 從 `deploy/.env` 的同名變數傳進來 |
| `WEB_ROOT` | `<repo>/web/dist` | 前端 build 產物。找不到時只提供 API |
| `EXT_ROOT` | `/ext` | 其他服務唯讀掛進來的設定目錄。目前只讀 `${EXT_ROOT}/prowlarr/config.xml` 的 `<ApiKey>` |
| `PROWLARR__AUTH__APIKEY` | 無 | Prowlarr 的 API key。用這個環境變數部署 Prowlarr 的人把同一個值也給 Berth，就不必唯讀掛它的設定目錄；有值時蓋過 `config.xml` |

### 後端

```bash
uv run berth --version      # CLI
uv run berth serve          # 啟動程序（--reload 為開發模式）
uv run berth openapi        # 印出 OpenAPI 文件（--output 寫檔）；前端型別的上游
uv run berth bench          # 解析基準測試（見下）；離線跑，離開碼是 CI 的門檻
uv run berth rebuild-ledger # 從媒體庫的 inode 把帳本長回來（見下）
uv run pytest               # 測試
uv run ruff check .         # lint
uv run ruff format .        # 格式化（CI 用 --check）
uv run mypy                 # 型別檢查（strict）
uv run lint-imports         # 依賴方向契約（plan §1.3）
```

資料庫 migration（Alembic）。程序啟動時會自動套用到最新版本，以下只在改 schema 時用：

```bash
uv run --env-file .env alembic current                          # 目前版本
uv run --env-file .env alembic revision --autogenerate -m "…"   # 依 models/ 產生新版本
uv run --env-file .env alembic upgrade head                     # 手動套用
```

改完 `berth/models/` 一定要產生 migration：schema 不是從 models 直接建的。

### 帳本重建（`berth rebuild-ledger`）

帳本沒了（資料庫還原到舊備份、手動清掉），但媒體庫裡的硬鏈接與 complete 裡的來源都還在時用它
（plan §11.3 決定 9）。逐條 Route 走完媒體庫，帳本不認得的每一個檔案：

- complete（每一條 Route 的子目錄）裡有一個檔案與它**同一個 inode**，而且它的路徑照命名模板
  讀得回季、集與 Tags（`naming.read_target`，讀的方法是重算一次、一字不差才算）→ 長回完整一列。
- 配不上的**一筆都不猜**：變成一件 `unmanaged_library_file`，理由寫在那一件上
  （`outside_routes` / `no_source` / `unknown_work` / `not_berth_naming`），到 `/issues` 看。

```bash
docker compose exec berth berth rebuild-ledger   # 容器裡（讀同一份 CONFIG_ROOT / DATA_ROOT）
uv run --env-file .env berth rebuild-ledger      # 開發機
```

**只加不減**：一個位元組都不刪，帳本上有、磁碟上不在的那幾列也不動（那是對帳的
`library_link_missing`）。服務開著也能跑（SQLite WAL），schema 由指令自己升到最新。印出計數；
有 Route 的目標目錄讀不到時那一條整條跳過並列出來，離開碼 1。complete 有子目錄讀不到時也是離開碼 1，
而且那一輪配不到來源的檔案**不開** `no_source`（問不到不算不見了），只數在 `not decided`。重跑是冪等的。

單一檔案的同一件事是 `/issues` 上 `unmanaged_library_file` 那一列的「認領進帳本」。

### 解析基準測試

解析器的正確率量在一組凍結的語料上（plan §4.6、brief §6.9）。**離線跑**：語料與 TMDB
快照都在 repo 裡，不打外部服務。

```bash
uv run berth bench                     # 跑一遍並印出報表；有問題時離開碼 1
uv run berth bench --update-baseline   # 改善之後更新門檻（理由寫進 commit message）
```

報表逐分類（anime / tv / movie）與整體列出八個互斥的桶——`auto_correct`、`auto_wrong`、
`review`、`missed`、`unmatched_correct`、`extra_correct`、`subtitle_correct`、`skipped`，
加起來就是檔案數——再加上分類正確率、tag 正確率、信心達標率（語料寫的 `min_confidence`
有沒有達到）與 high / medium 的誤判率。**最重要的是 `auto_wrong`**：自動處置但處置錯，
門檻是「不得高於 `tests/fixtures/parser/baseline.json`」；`auto_correct`、`extra_correct`、
`subtitle_correct` 三格則各允許比 baseline 少一筆（語料會長大）。

比對包含**目標路徑**：季集對了但檔名錯了，Jellyfin 那一端還是入錯（多版本的判定、繁簡的
分辨與多集檔的表示法全都只寫在檔名裡）。

同一支邏輯也是 `tests/unit/test_bench.py`，所以 CI 不另外開 job——`uv run pytest` 綠燈就
代表 benchmark 沒掉。語料怎麼來、怎麼加一筆，見
[`tests/fixtures/parser/README.md`](tests/fixtures/parser/README.md)。

### 前端

```bash
pnpm -C web dev             # Vite dev server
pnpm -C web build           # 產出 web/dist
pnpm -C web preview         # 預覽 build 產物
pnpm -C web test            # vitest（test:watch 為 watch 模式）
pnpm -C web lint            # eslint
pnpm -C web format          # prettier（CI 用 format:check）
pnpm -C web typecheck       # tsc（strict）；build 已含，這是單獨跑的快捷
pnpm -C web gen:api         # 重新產生 API 型別（見下）
pnpm -C web e2e             # playwright 對演練情境跑九條流程（先 build，見〈前端 e2e〉）
```

### API 型別

前端不手寫 API 的形狀：`web/src/api/schema.d.ts` 由後端的 OpenAPI 產生，`web/src/api/*.ts`
只把後端的類別名（`RouteOut`）換成前端在講的名字（`RouteView`）。

```bash
pnpm -C web gen:api         # berth openapi → web/openapi.json → src/api/schema.d.ts
```

- **改了任何 pydantic 的 request / response model 就重跑它**，產出的 `schema.d.ts` 與後端的
  改動放同一個 commit。CI 的 `api-types` job 跑同一個指令再比對，型別檔過期時紅燈；
  `tests/unit/test_openapi_contract.py` 在本機 `pytest` 就先紅，不必等 CI 跑完產生器。
- **拒絕的理由是 `berth/domain/enums.py` 的 enum**（`JobRefusal`、`RouteRefusal`、
  `AccessRefusal`），經由各 router 的 `responses=` 進 OpenAPI，前端從產出的型別取它們。
  加一種理由要做四件事，**每一件都有閘門**：enum 加一個成員、那一支 router 的 `_STATUS`
  給它一個狀態碼（`TestStatusTables`）、重跑 `pnpm gen:api`（`TestRefusalReasons` 與 CI）、
  前端的 `ReasonSet` 加一格（`tsc`，`refusal.test.ts` 的 `@ts-expect-error` 釘著那道閘門本身）。
  第五件是**畫面要說一句話**：`jobs.refusal.*` 走動態 key，所以 `t()` 的 `strictKeyChecks`
  會替它擋；`RouteRefusal` 與 `AccessRefusal` 的消費端是查表或單一理由比較，那一句沒有閘門。
- **會拒絕的端點都要在 `responses=` 裡宣告**（`TestDeclaringWhatEachEndpointRefuses`）：走訪
  `create_app()` 的每一條路由，比對路由**物件**上的 `responses` 與 handler **語法樹**丟得出來的
  拒絕，漏宣告與多宣告都紅。**守的是形狀那一層**（`RouteRefusalOut` 這幾個 model），不是理由
  那一層：把 `POST /setup/routes` 的表改成多列一種理由，這道閘門不會紅。
- 理由那一層**沒有閘門**，是慣例：各端點各給一張小表，只列它真的會回的那幾種
  （`api/routes.py` 的 `route_responses()`、`api/jobs.py` 的 `_refusals()`）。`REFUSAL_RESPONSES`
  是 `routes/*` 五支的聯集，別套到別的模組。`routes/*` 那五支自己至今仍共用它，所以
  `GET /jellyfin/libraries` 的文件上列得出它丟不出來的 `route_in_use`——已知的過度宣告，
  收它要替那五支各寫一組（M2 票 02a Comments）。
- 產出的型別檔進版控，中間產物 `web/openapi.json` 不進（`.gitignore`）。型別檔進版控，
  `pnpm install` 之後沒有 Python 環境也能 typecheck 與跑測試；`openapi.json` 則會因為
  `info.version` 每次發版都變而製造沒有意義的 diff。
- 指令裡的 `--default-non-nullable false` 讓有預設值的請求欄位維持選填，與 OpenAPI 的
  `required` 一致（回應的欄位全部是必填，不受影響）。
- 產生器不需要跑起服務：`berth openapi` 只組裝路由，沒有 lifespan、不碰資料庫。

### 全部檢查

```bash
uv run pre-commit run --all-files
```

CI（`.github/workflows/ci.yml`）在 push 到 `main` 與所有 PR 上跑同一組檢查。

### e2e

M1 的整條路徑、M1.5 的權限與瀏覽、M2 的修正與對帳對**真的** qBittorrent 與 Jellyfin 跑一遍（plan §10、`tests/e2e/`）。
**一次 compose、一次精靈、一次入庫，三個模組共享**（fixture 在 `tests/e2e/conftest.py`；檔名的數字就是執行順序）：

- `test_1_m1_pipeline.py`：精靈八步只走 Berth 的 API，送一部美劇一季、一部動漫一季、一部電影，等它們不經人工、
  依序走過完成 → 規劃 → 入庫，再驗硬鏈接兩端同一個 inode、帳本逐檔記下的 item id 就是 Jellyfin 在那條路徑上的 item。
- `test_2_m15_library.py`：以 Jellyfin API 建一個只開放一個媒體庫的一般使用者，用它登入 Berth——看不到沒權限的
  媒體庫、直接請求也被拒；不經 Berth 放進那個媒體庫的作品照樣在牆上；某一集的 `item_id` 就是 Jellyfin 在帳本
  那條路徑上的 item；標為已看 / 未看之後那個帳號自己的觀看紀錄真的變了；帳號被停用之後 session 結束。
  最後停掉 Jellyfin 容器，驗「問不到 Jellyfin」那一句（跑完會把它起回來）。
- `test_3_m2_repair.py`：三種人為破壞各造一次——在 Jellyfin 裡刪掉一集、用複製品取代硬鏈接、手動刪掉 complete
  裡的來源（外加 complete 裡一個沒人認領的目錄）——手動對帳偵測到，按 Issue 上的動作修好，再對帳一次確認
  那一件沒有再開；以及整個 Anime 媒體庫的內容刪光之後按一次「重新入庫」，回到同樣的路徑、同一個 inode、同樣的帳本列。

Prowlarr 也會起來讓精靈偵測，但第 6 步跳過索引站、送單直接帶 `.torrent` 網址——搜尋不在 e2e 裡。套件內的媒體庫
一開始是空的，反查要等 Berth 請 Jellyfin 掃描之後那一輪，所以一次**約 15 分鐘**，平常的 `uv run pytest` 不收它
（`-m 'not e2e'`）。

```bash
# CONFIG_ROOT 是宿主上的空目錄；/data 是 named volume（tests/e2e/e2e.env），
# 因為發佈名很長，Windows bind mount 的 260 字元路徑放不下。
export CONFIG_ROOT="$PWD/.local/e2e-config"          # PowerShell: $env:CONFIG_ROOT = "$PWD/.local/e2e-config"
docker compose -f deploy/docker-compose.yml -f tests/e2e/compose.yml --env-file tests/e2e/e2e.env up -d --build
uv run --env-file .env pytest -m e2e tests/e2e -rA     # 要 .env 裡的 TMDB_API_KEY：精靈第 7 步是閘門
docker compose -f deploy/docker-compose.yml -f tests/e2e/compose.yml --env-file tests/e2e/e2e.env down --volumes
```

- **不加 `--wait`，`up` 完馬上跑測試**：這是冷啟動閘門（票 06h）。精靈在 Jellyfin 與 Prowlarr 還在啟動時就開始，
  照常輪詢到三個服務都判定完成、不按重新探測；第一輪探測就全部判定完成的話測試會失敗，因為那一輪沒碰到啟動中的
  那幾秒。所以 `up` 之前先 `build`（與拉 image），不要讓 `up` 之後還有東西要等。
- **一次 `up` 只跑得了一次**：精靈走完就不能再走一遍，重跑前先 `down --volumes`。
- 容器名、網路名與 port 與正式部署相同（qBittorrent 的免密白名單認的是 berth 的固定 IP），
  所以同一台機器上正式的那一套要先停下來。
- 沒有 peer 可以真的下載：`torrents` 容器在 `/data/e2e/staging` 造出三包發佈（檔案清單取自 benchmark
  語料、影片是 `tests/fixtures/e2e/` 的種子），測試在送單之後把它們複製到 qBittorrent 說的下載路徑
  再叫它 recheck。
- GitHub Actions 的 `.github/workflows/e2e.yml` 在 nightly、`v*` tag 與手動觸發時跑同一組指令，
  TMDB 憑證是 repo secret `TMDB_API_KEY`。

### 前端 e2e

`web/e2e/` 以 playwright 對〈UI 的 Fake 後端〉的演練情境跑十三條流程（除了送單、審核與待處理那三條，各有 1280 與 390 兩份，共二十三個 project），一條流程一台 server、各佔一個 port
（`web/playwright.config.ts` 自己起、跑完收掉）：

| 流程 | 情境 | port（1280 / 390） |
| --- | --- | --- |
| 精靈八步走完（改媒體庫清單、每一格停在結果上、回頭再往前、試搜與移除），之後以同一組帳密登入 | `bundled` | 8491 / 8501 |
| 既有服務：填 qBittorrent 帳密、登入既有 Jellyfin 加 Berth 路徑並選它當寫入目標、貼 Prowlarr 的 key | `mixed` | 8495 / 8505 |
| 冷啟動：服務還在啟動時開始精靈，不按重新探測就判定完成 | `starting` | 8496 / 8506 |
| 精靈跑完之後：`/setup` 導向設定頁，加一個索引站並試搜、換 TMDB key | `healthy` | 8497 / 8507 |
| 從作品頁送單，一路走到已入庫 | `import` | 8492 |
| `/review` 確認一筆 audit | `review` | 8493 |
| `/issues` 修一條 `library_link_missing` | `issues` | 8494 |
| `/rss` 加 Mikan feed、輪詢、綁定待綁定的那一部，下載列表上兩集都已入庫 | `rss` | 8498 / 8508 |
| `/rss` 排除條件：寫壞的正則存不進去、全域與 RSS Series 那一層擋下的、第二個 Feed 帶同一個 hash 的是重複 | `rss` | 8499 / 8509 |
| `/rss` 新的 acg.rip 搜尋 feed：第一輪停在預覽、合集在「排除」那一組，選「只追之後的」之後整份歷史略過 | `rss` | 8488 / 8489 |
| `/rss` 綁定 Mikan 的 RSS Series 時補舊集，之後每日補漏 | `rss` | 8486 / 8487 |
| split-cour 的第一批已入庫：在 `/review` 改一集並套用到 RSS Series，其餘 11 集跟著搬，全部確認 | `rss-split-cour` | 8484 / 8485 |
| 連載中的 split-cour 第一批整批擋在審核：改一份計劃的一列並套用到 RSS Series，其餘 11 份重新規劃、自動入庫，改的那一份核准 | `rss-split-cour-airing` | 8510 / 8511 |

精靈、設定頁與 RSS 那幾條在兩種寬度各走一次（`playwright.config.ts` 的 `NARROW`），每一格都留一張整頁截圖在
`web/test-results/<那一條>/`，通過的那一輪也留著。

```bash
pnpm -C web build                                          # server 發的是 web/dist
pnpm -C web exec playwright install chromium               # 第一次
pnpm -C web e2e                                            # 約 1 分鐘（十三台替身）
pnpm -C web e2e --project issues                           # 只跑一條
pnpm -C web exec playwright show-trace web/test-results/<那一條>/trace.zip   # 失敗時看 trace
```

- **不重試、不接手已經在跑的 server**：替身是有狀態的，重跑一次面對的是被上一次改過的替身。表上的 port
  有東西在聽時先停掉它。
- 選擇器寫的是 zh-Hant 文案（瀏覽器語系 `zh-TW`），改文案要跟著改腳本。
- 失敗時 `web/test-results/` 留截圖與 trace、`web/playwright-report/` 是 HTML 報告；CI 的 `web-e2e` job 把兩者
  上傳成 artifact `playwright-evidence`（留 14 天）。
- 與上一節的 e2e 是兩回事：那一套對真的服務、nightly 跑；這一套全是替身、每個 push 都跑。

### UI 的 Fake 後端

精靈與健康頁的 UI 不必真的有四個容器也能實跑：`scripts/fake_setup_server.py` 起一台真的 Berth
（真的 API、真的資料庫、真的前端 build），只把三個外部服務換成 `adapters/*/fake.py`。

```bash
pnpm -C web build                                          # 先有前端產物
uv run python scripts/fake_setup_server.py                 # http://127.0.0.1:8484
uv run python scripts/fake_setup_server.py --scenario mixed
uv run python scripts/fake_setup_server.py --port 8383     # 換 port（索引站給的下載連結跟著走）
```

`--port 8383` 是後端的預設 port（`berth/config.py` 的 `DEFAULT_PORT`），也就是 `web/vite.config.ts` 代理
`/api` 的去處——想對著某個演練情境跑 `pnpm -C web dev`（改前端存檔就重載）時用它。

| `--scenario` | 演的是什麼 |
| --- | --- |
| `bundled`（預設） | 乾淨的 compose：三個服務都判為套件內，泊位 1–3 全部走得完。九個預設索引站裡有四個連不上（訊息取自真的 Prowlarr 那一輪），逐站成敗看得到；加完之後試搜，Mikan 演「搜尋時連不上」，其餘站各回幾筆 |
| `outdated` | qBittorrent 的 Web API 低於 2.8.4：第 4 步拒絕接入並給升級指令 |
| `mixed` | NAS 的常見組合：既有 Jellyfin（跑過自己的精靈、兩個媒體庫，其中一個掛 TVDB；管理員 `owner` / `s3cret`）、qBittorrent 已設密碼（任何帳密都測得過）、Prowlarr 已有索引站。兩個媒體庫的舊路徑是暫存目錄底下真的存在的 `nas/movies`、`nas/anime`，Route 的第三條纜繩才看得到它們，精靈走得完 |
| `starting` | 四個容器同時起來（票 06g 量到的時間線，照探測次數演，前端每 3 秒一次）：Jellyfin 先回不像它自己的東西、再回兩次 503「還在載入」，約 9 秒後是套件內；qBittorrent 第一次連不上；Prowlarr 連不上五次，約 15 秒。第 2 步不必按重新探測就全部判定完成，之後與 `bundled` 一樣走得完 |
| `key-missing` | 同 `bundled`，但 Prowlarr 的設定目錄沒有唯讀掛進 Berth：讀不到 API key，第 2 步要貼上 |
| `absent` | Jellyfin 不在 `COMPOSE_PROFILES` 裡：探不到，要在第 2 步填自己那一台的位址 |
| `old-jellyfin` | 既有 Jellyfin 還停在 10.11（其餘兩個服務照 `bundled`，擋路的只留一個）：泊位 1 紅燈，說出目前版本、為什麼要 12，以及升級前後要做的事；健康頁上同一台也是紅的 |
| `signed-out` | 精靈已跑完，畫面從登入頁開始。`skipper` / `harbour` 是管理員，`deckhand` / `rope` 是普通使用者（看不到設定入口） |
| `unmounted` | Jellyfin 少了媒體庫目錄的掛載：泊位 4 的第四條纜繩失敗，看「哪個容器少了哪個掛載」與 compose 修正片段 |
| `rss` | RSS 頁 `/rss`（M3 票 08）：同 `healthy`，一個請求都不出網。Mikan 是替身：加 `https://mikanani.me/RSS/MyBangumi?token=REDACTED`（任何 token 都一樣，替身只認這一條網址）、按「立即輪詢」，票 07 錄下來的聚合 feed 12 筆長出 11 個待綁定的 RSS Series（單集頁照 `tests/integration/test_rss.py` 合成）。TMDB 也是替身，搜「Kimi ga Shinu made Koi wo Shitai」或「与你相恋到生命尽头」找得到那一部；在《与你相恋到生命尽头》那一列綁到它與 Anime，兩集的 `.torrent` 換成這台自己生的，qBittorrent 收下就當場完成，幾秒後 `/jobs` 上兩筆都已入庫。票 11 起另有錄下來的 acg.rip 搜尋 feed：加 `https://acg.rip/.xml?term=Kamiina+Botan`、按「立即輪詢」，30 筆停在頁首的第一輪預覽（8 筆合集被排除）。帳號同 `signed-out` |
| `rss-split-cour` | 改正並套用到 RSS Series（M3 票 13）：同 `rss`，但 TMDB 把《与你相恋》的兩個 cour 併成一季 24 集。綁定時補舊集，12 集全部落在 S01E01–E12（錯的：字幕組的第二 cour 從 01 重數），在 `/review` 是這個 RSS Series 的第一批、一組；把第 1 集改成 S01E13 並勾「套用到這個 RSS Series」，其餘 11 集跟著搬到 14–24，再按「全部確認」 |
| `rss-split-cour-airing` | 從審核裡套用到 RSS Series（M3 票 14b）：同 `rss-split-cour`，但第二 cour 正在播（2026-07-02 起）。綁定時補舊集，12 集照字面對到一月播出的 S01E01–E12，播出日比對把 12 份計劃整批擋在 `/review` 的「要你決定」、一集都沒入庫；在第 1 集那一份按「改」、起集填 13、勾著「套用到這個 RSS Series」套用，其餘 11 份重新規劃、自動入庫（第一批，等全部確認），改的那一份等你核准 |
| `healthy` | 精靈已跑完、三條 Route 綠燈、四項健康檢查全綠：健康頁 `/health` 與設定頁 `/settings/*`（五個分頁：換 TMDB key、加站試搜移除都在這裡演得出來）的起點。帳號同 `signed-out` |
| `degraded` | 同上，但索引站在第一輪檢查之後掛掉：按「立即重測」就會看到那一項變紅、其餘三項不動，以及「最後成功」還留著 |
| `drifted` | 同上，但有人把 qBittorrent 的 `auto_tmm_enabled` 改掉了：看設定的 qBittorrent 那一頁的逐鍵差異表與「還原建議設定」 |
| `review` | 審核佇列 `/review`（M2 票 06）：同 `issues`，另外 SPY×FAMILY 第二季兩集（只寫絕對集號 26、27，累計換算成 S02E01、S02E02，信心 medium）真的硬鏈接進媒體庫、帳本與 Plan Item 都掛 audit。按「確認」清旗標；按「撤銷」真的把那一條鏈接拆掉，那一筆下載回到待審核——之後以 `deckhand` / `rope` 登入，`/jobs` 與 SPY×FAMILY 的詳情頁說「等管理員審核」。這兩集是同一筆下載，收成一組、收起時說出為什麼是 medium，按「全部確認」一次清掉（M3 票 05）。Issue 不在這一頁（M3 票 05），頁尾一行「另有 N 件待處理」連到 `/issues`。另有一筆 `- 05` 下載完成（M2 票 07）：只寫集號、沒超過第一季的 25 集，規劃器算成低信心、提案 S01E05，停在「要你決定」那一段——逐列改季集看目標路徑當場換掉，按「核准並入庫」真的硬鏈接進媒體庫；按「拒絕」就重新規劃。再一筆 S01E03 + OVA 下載完成（M2 票 08）：媒體庫裡已經有一份一模一樣的 S01E03（路徑與 Tags 照解析器算），所以規劃器略過它、佇列上一列「重複」（取代 / 保留兩者 / 跳過，都真的動磁碟）；OVA 2 對不到任何一集，佇列上一列「對不到」，指派到 S00E02 真的建硬鏈接。伺服器起來約 60 秒後規劃器第一輪才算出這兩列 |
| `routes` | Route 設定頁 `/settings/routes`（票 14）：同 `healthy`，另外 TV 媒體庫在 Jellyfin 上多掛一顆碟（新增第二條 Route 會全綠）、Movies 多一條沒掛進 Berth 的路徑（在那裡建 Route 會紅、維持停用），TV 那條 Route 有一筆已入庫的下載（刪除鍵換成「刪不得」與一鍵停用）；新增時選 Anime 沒有空路徑，給一條到 Jellyfin 媒體庫設定的連結 |
| `issues` | 待處理頁 `/issues` 與對帳（M2 票 05）：同 `healthy`，另外真的入庫一包三集的動漫（來源在 complete、媒體庫那一份是真的硬鏈接），並把其中第二集的媒體庫檔案刪掉——使用者在 Jellyfin 按刪除之後就是這樣。按「立刻對帳」真的比四方並寫下一件 Issue，按「重新鏈接」真的 `os.link` 把它接回來。另外三種破壞（M2 票 09）：第三集被一份一樣大的複製品取代（「以硬鏈接取代」真的換回硬鏈接）、complete 裡一個沒人認領的目錄（「刪除這個目錄」真的整棵刪掉）、媒體庫裡一個手放的檔案（只列出，沒有會刪的按鈕）。管線與健康檢查那幾種（M2 票 09c）：三筆下載到一半的 SPY×FAMILY，替身 qBittorrent 說一筆 `missingFiles`、一筆 `error`、一筆已經不在——起來之後 poller 第一輪就開出三件，「重新校驗」「重試」「重新送單」各自讓它們離開壞掉的狀態；或者 `curl -X POST 'http://127.0.0.1:8484/demo/qbittorrent/fix?hash=<hash>'` 演使用者在 qBittorrent 裡自己修好那一筆（M3 票 02），poller 下一輪（至多 30 秒）把 Job 接回、那一件由系統收掉，時間線多一筆「已接回」；Anime 媒體庫掛著 TVDB，所以一開始就有一件 TVDB（只有「忽略」，按了之後「立即重測」也不會再開）。磁碟空間那一件要到設定的 qBittorrent 那一頁把門檻調到比這台機器剩的還大，`/issues` 當場多一件，調回來當場收掉。認領類三顆（M2 票 10，替身 TMDB 搜得到 `spy`）：媒體庫裡第四集是真的硬鏈接但帳本上沒有它——「認領進帳本」長回一列，`Hand Placed` 那一件按下去說出配不上的理由；qBittorrent 上一筆 `[Sub] SPY×FAMILY - 07` 沒有 Job——「認領並建立下載」選作品，下載列表多一筆；`[Old] Forgotten Batch` 按「重新入庫」選作品，規劃器接手。`/jobs` 上入庫完的那一筆，在它的詳情頁（展開那一列 → 「下載詳情」）有「重新入庫」 |
| `discover` | 探索頁 `/`：三個外部服務仍是替身，但 TMDB 打**真的** `api.themoviedb.org`。憑證從環境變數 `TMDB_API_KEY` 讀（v3 key 或 v4 read access token 都收），沒設就變成「憑證缺失」那個畫面 |
| `tmdb-down` | 憑證有、TMDB 連不上：探索頁的每個 feed 各自顯示服務回的原文與「重試」，而不是一片空白 |
| `search` | Media 詳情頁的搜尋結果表：TMDB 與**索引站都打真的**。索引站位址從 `BERTH_INDEXER_URL` / `BERTH_INDEXER_KEY` 讀，沒設就退回替身（結果表是空的，那本身也是要驗的畫面）。一次搜尋 35–85 秒 |
| `submit` | 送單與下載列表 `/jobs`：TMDB 打真的，索引站給三筆磁力連結的替身結果（形狀取自真的那一輪）。送單、解析、Job 與時間線走的都是產品自己的程式碼，只有 qBittorrent 是替身 |
| `submit-failing` | 同上，但 qBittorrent 收不下：送單失敗那一列、服務回的原文，以及「重新送單」 |
| `import` | 送單到入庫整條走完、**一個請求都不出網**（M2 票 15 的前端 e2e 用它）：同 `plan` 那一包對得上的批次，但 TMDB 是替身（與 `issues` 同一部 SPY×FAMILY，`/media/tv:120089`）。送到 Anime 之後幾秒就是「已入庫」，詳情頁的「檔案與版本」列出五個檔案 |
| `plan` | 下載完成 → **Import Plan**（票 11）：索引站給兩包替身結果——一包對得上的批次（自動入庫）與一包對不到任何一集的 OST（停在待審核）。qBittorrent 是替身，但它會把那幾個檔案**真的寫進 save path** 並報成 100%，所以 poller 走完狀態機、planner 算出真的 Plan：解析、命名、mediainfo、TMDB 快照全是產品自己的程式碼 |
| `inventory` | Media 詳情的「檔案與版本」與送單到入庫的媒體庫（票 13）：同 `plan` 的兩包，加上一台會「掃到」入庫檔案的替身 Jellyfin。送單之後那一部先在媒體庫頁的「還沒進 Jellyfin」那一條，約 30 秒後 resolver 反查、替身「掃到」它，它就換到牆上；OST 那一包是「待審」篩選要找到的那一格。深連結指向瀏覽器主機名的 8096，那台 Jellyfin 不存在——Jellyfin 那一端要用真的一套驗 |
| `long-lists` | 長清單的收合（M1.5 票 09）：同 `inventory`，但索引站只給 benchmark 語料裡葬送的芙莉蓮 `[7³ACG]` BD 合集（39 個檔案：S01 28 集、S00 11 集）。在芙莉蓮的詳情頁（`/media/tv:209867`）送到 Anime，計劃、入庫與替身 Jellyfin 的反查約一分鐘走完，之後看「檔案與版本」與 `/jobs` 那一列的計劃；名偵探柯南（`/media/tv:30983`，TMDB 併成一季 1216 集）不必送單，打開就是那張季表。需要 `TMDB_API_KEY`。**Windows 上加 `--config-root` 指一個短路徑**（例如 `C:/Users/<你>/t9`）：預設的暫存目錄太深，S00 那 11 個檔案的目標路徑會超過 260 字元而入庫失敗 |
| `library` | 媒體庫頁 `/library` 的整庫瀏覽與權限（M1.5 票 03）：Movies / TV / Anime 三個媒體庫擺好作品（Movies 有 131 部，翻得到第二頁；有一部沒有 TMDB id），海報經 Berth 代理替身 Jellyfin 的 SVG（票 04；`Home Videos 2019` 沒有圖、`Harbour Film 007` 有 tag 但圖不見了，兩格都是「無海報」），Berth 經手的有在牆上的、還沒進 Jellyfin 的、待審與 Unmatched（M2 票 14：`skipper` 在 TV 媒體庫的「待審」是 Slow Horses 一份等審核的計劃，「對不到」是 The Bear 兩個 Extras 檔案，就地按得了；Anime 上是 Frieren 的計劃）。作品有類型與社群評分（票 06：排序、類型與年份篩選看得出差別；Shōgun 的 `War & Politics` 帶 `&`），Home Videos 2019 兩者都沒有。每部劇六集；`deckhand` 看到 The Bear 第三集、第四集看到 18%，看完 Breaking Bad，Slow Horses、Shōgun、Game of Thrones、The Office 各看了幾集，Oppenheimer 看到 42%、Harbour Film 002 看到 65%、看過 Harbour Film 001，`skipper` 看完 Slow Horses、The Bear 看過一集（票 05，標為已看 / 未看寫進替身 Jellyfin，重開伺服器就還原）。所以 `deckhand` 的媒體庫頁上方有繼續觀看與下一集（票 07：劇有 16:9 的 Thumb 或 Backdrop，Harbour Film 002 沒有橫圖是「無圖」；登入後就落在媒體庫，探索頁只放 TMDB 牆，M3 票 06），`bosun` / `knot`（權限同 `deckhand`、什麼都沒看過）兩列都不出現。`skipper` / `harbour` 看得到三個媒體庫；`deckhand` / `rope` 只開放 Movies 與 TV，開 `/library/item-anime` 是「找不到或沒有權限」。`curl -X POST 'http://127.0.0.1:8484/demo/jellyfin/disable?user=deckhand'` 在替身 Jellyfin 停用他（`enable` 復原），至多 60 秒後他的下一個請求被送回登入頁。Media 詳情的觀看區（票 08）：`deckhand` 開 The Bear 是「繼續看 S01E04」、集有劇照；The Office 有兩季與 Specials，主按鈕是「看下一集 S01E05」；Breaking Bad 看完了；Oppenheimer 是電影；SPY×FAMILY 在他看不到的 Anime，頁面上沒有觀看區（`skipper` 開同一頁就有）；`bosun` 開 The Bear 是「從 S01E01 開始看」。有 `TMDB_API_KEY` 時詳情頁打真的 TMDB |
| `poll` | 送單到完成的狀態**自己走完**（票 10）：qBittorrent 打**真的**那一台，所以 `sync/maindata` 會真的換 state、poller 會真的驅動 §3.1 的轉換、SSE 會真的把那一列推著動。位址從 `BERTH_QBITTORRENT_URL` 讀，準備步驟見下方 |

`healthy` 沒有 TMDB 憑證，所以它同時是探索頁「還沒填憑證」的樣子——那一步是精靈的必填閘門
（見〈先申請一把 TMDB API key〉），畫面要指得出下一步。

```bash
# 把 TMDB_API_KEY 寫進 repo 根目錄的 .env（`.env.example` 有欄位，`.gitignore` 已擋），
# 再用 uv 的 --env-file 帶進去——與 `berth serve` 同一個慣例。
uv run --env-file .env python scripts/fake_setup_server.py --scenario discover
```

搜尋結果表要看真的發佈名——中日英混排、100 字以上、每個字幕組各寫各的，那是替身演不出來的：

```bash
# $KEY 是那台 Prowlarr 的 API key（`config.xml` 的 <ApiKey>）。
BERTH_INDEXER_URL=http://127.0.0.1:19696 BERTH_INDEXER_KEY=$KEY   uv run --env-file .env python scripts/fake_setup_server.py --scenario search
```

下載列表要看它**自己動**——狀態與進度不重整就一路走到「下載完成」——那需要一台真的 qBittorrent，
因為替身收下 `torrents/add` 之後什麼都不會發生：

```bash
# 1. 一台乾淨的 qBittorrent。**發佈 port 必須是 8080**：它的 Host 檢查連 port 都比對，
#    偏移的 port 會讓每一個請求回 401（brief §20.7）。
docker run -d --name berth-poll-demo -p 8080:8080 \
  -e PUID=1000 -e PGID=1000 -e WEBUI_PORT=8080 \
  -v "$PWD/.local/experiments/poll-demo:/config" lscr.io/linuxserver/qbittorrent:5.2.3

# 2. 把那一份 torrent 的資料先放進 category 的 save path，qBittorrent 校驗完就是「完成」。
#    `demo_torrent()` 用的是 `scripts/experiments/lib.py` 的 `make_torrent`，pieces 是真的 SHA-1。
python - <<'EOF'
import subprocess, sys, tempfile
from pathlib import Path
sys.path[:0] = ["scripts", "scripts/experiments"]
from fake_setup_server import POLL_FILES, POLL_RELEASE
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / POLL_RELEASE
    for rel, size in POLL_FILES:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(bytes((i % 251) for i in range(size)))
    subprocess.run(["docker", "exec", "berth-poll-demo", "mkdir", "-p", "/downloads/complete/anime"], check=True)
    subprocess.run(["docker", "cp", str(root), "berth-poll-demo:/downloads/complete/anime/"], check=True)
EOF

# 3. 起 Berth，開 http://127.0.0.1:8484/jobs（skipper / harbour），在 Media 詳情頁
#    用關鍵字 `Berth.Poller.Demo` 搜、選 Anime、送單。那一列會自己走完。
BERTH_QBITTORRENT_URL=http://127.0.0.1:8080   uv run --env-file .env python scripts/fake_setup_server.py --scenario poll
```

這個情境的三層路徑用的是**容器裡的**那一組（`/downloads/complete`），因為真的 qBittorrent 只用得了
它自己看得到的路徑。**Windows 上的副作用**：`Path("/downloads")` 在那裡是「目前磁碟機的根目錄底下」，
所以建 Route 那一步會在 `C:\downloads` 留下幾個空目錄——跑完刪掉它，否則
`tests/integration/test_setup_routes.py` 裡「Berth 看不到那條 save path」的兩條會誤判成通過。

這些環境變數**只給開發時的演練與 `scripts/experiments/*` 用**。Berth 自己不讀它們：產品的
唯一來源是 `settings.services.tmdb.api_key` 與 `settings.services.indexer`，由精靈寫進資料庫。

Fake 是**有狀態**的，每個情境只有一份，所以第 3 步真的會把那台假 Jellyfin 一步一步改掉，
重按也真的會標成「已經是這樣」。

每次啟動都用一個新的暫存 `CONFIG_ROOT`，所以永遠是乾淨環境；`--config-root` 可指定成固定目錄
以便跨次保留進度。精靈第 5 步（媒體庫路徑）會**真的**建目錄、寫探測檔並呼叫 `link()`，所以三層
路徑（`settings.paths`）由這支腳本指到該次的暫存 `DATA_ROOT` 底下，不會碰到容器裡的 `/data`。

`healthy` / `degraded` / `drifted` 三個情境在啟動時就真的跑過一輪 `build_routes` 與健康檢查，
所以畫面上的 inode、可用空間與版本號都是那一輪量到的值，不是寫死的假資料。

### 實驗腳本

`scripts/experiments/` 是對真實外部服務做的驗證（Jellyfin 命名、qBittorrent 版本差異、
Prowlarr 設定 API、硬鏈接），全部可重跑。每個腳本在回答什麼、有哪些坑，見
[`scripts/experiments/README.md`](scripts/experiments/README.md)；結果寫在
[`docs/research/m0-experiments.md`](docs/research/m0-experiments.md)。

媒體樹與 qBittorrent 設定檔都要在容器啟動**之前**備好：

```bash
python scripts/experiments/make_media.py
python scripts/experiments/prepare_qbittorrent.py     .local/experiments/qbittorrent-44 .local/experiments/qbittorrent-52
docker compose -f scripts/experiments/compose.yml up -d      # port 與 deploy/ 錯開
```

跑實驗（各自獨立，順序無所謂）：

```bash
python scripts/experiments/jellyfin_naming.py --base-url http://localhost:18096 --label 10.10.7
python scripts/experiments/jellyfin_naming.py --base-url http://localhost:18196 --label 10.11.11
python scripts/experiments/qbittorrent_matrix.py --base-url http://localhost:18080 --label 4.4.5
python scripts/experiments/qbittorrent_matrix.py --base-url http://localhost:18081 --label 5.2.3

# 票 10 的 poller 端點（`sync/maindata` 的增量、`torrents/files`、IP 封鎖的 403）。
# 最後一項會封住來源 IP，所以錄完那一輪要重建容器才能再跑一次。
python scripts/experiments/qbittorrent_poller.py --base-url http://localhost:18080 --label 4.4.5 --container berth-exp-qbittorrent-44
python scripts/experiments/qbittorrent_poller.py --base-url http://localhost:18081 --label 5.2.3 --container berth-exp-qbittorrent-52

# M2 票 09c 的 recheck / start（`missing_files` 與 `client_error` 的按鈕）。會重啟那個容器。
python scripts/experiments/qbittorrent_recovery.py --base-url http://localhost:18080 --label 4.4.5 --container berth-exp-qbittorrent-44
python scripts/experiments/qbittorrent_recovery.py --base-url http://localhost:18081 --label 5.2.3 --container berth-exp-qbittorrent-52
python scripts/experiments/prowlarr_host_config.py     --base-url http://localhost:19696 --config .local/experiments/prowlarr
```

Jellyfin 的權限與瀏覽 API（M1.5 票 01）自己起停一台一次性的 Jellyfin（image 取 `deploy/` 釘的那一個，
不需要上面的 compose），跑完連容器與工作目錄一起刪。結果見
[`docs/research/library-browsing.md`](docs/research/library-browsing.md) §2、§3.1、§5、§10、§11：

```bash
python scripts/experiments/jellyfin_permissions.py            # 只量，報告寫到 .local/experiments/results/
python scripts/experiments/jellyfin_permissions.py --record   # 另外重錄 tests/fixtures/http/jellyfin/ 的權限 fixture
python scripts/experiments/jellyfin_permissions.py --record --only items.tv.series.page.json   # 只加錄這幾個，其餘不動
```

Jellyfin 的圖經 Berth 代理要不要另存一份（M1.5 票 04）：同樣自己起停一次性 Jellyfin，另外起一個 `berth serve`
量經過代理的延遲，所以要用 `uv run`。結果見 [`docs/research/library-browsing.md`](docs/research/library-browsing.md) §6.1：

```bash
uv run python scripts/experiments/jellyfin_images.py   # 報告寫到 .local/experiments/results/jellyfin-images.json
```

RSS Series 自動綁定的規則門檻（M3 票 09）：對票 07 錄下的 Mikan 聚合 feed，真的抓 Mikan 單集頁與番組頁、真的打
TMDB，走 Berth 自己的判定、只印不綁。憑證讀環境變數，資料庫是暫時目錄裡的新的一份。結果見
[`docs/research/rss-sources.md`](docs/research/rss-sources.md) §2.8：

```bash
uv run --env-file .env python scripts/experiments/rss_auto_bind.py   # 要 .env 裡的 TMDB_API_KEY；會連 Mikan 與 TMDB
uv run --env-file .env python scripts/experiments/air_date_lag.py    # 同上；Windows 主控台加 PYTHONIOENCODING=utf-8
```

1,000 部的媒體庫上量 Berth（M2 票 11，plan §11.3 決定 2 的門檻）：自己 build Berth 的 image（只有 backend 那一層）、
起一次性的 Jellyfin 與 qBittorrent、造 1,000 部 × 12 集的媒體樹（掃描約 6 分鐘），量完連容器、volume、network、image
一起刪。宿主只要 Python 標準庫與 docker；量測本身在 Berth 的 image 裡跑。結果見
[`docs/research/large-library.md`](docs/research/large-library.md)：

```bash
python scripts/experiments/large_library.py                  # 報告寫到 .local/experiments/results/large-library*.json
python scripts/experiments/large_library.py --series 30      # 先小規模跑通
python scripts/experiments/large_library.py --keep           # 留著環境；改了 Berth 之後用下一行只重 build 與重量
python scripts/experiments/large_library.py --reuse --keep --stages inventory   # 段落：jellyfin,inventory,reconcile
```

停住的 torrent 送 recheck 與重新開始之後狀態怎麼走（M3 票 03，brief §20.2）：自己起停一次性的 qBittorrent
（network、兩個 volume、容器，前綴 `berth-exp-recheck`，只發佈在 `127.0.0.1:18093`），資料是稀疏的全零檔，
一個版本約 5 分鐘，跑完印出 `docker ps -a` / `docker volume ls` 的過濾結果：

```bash
python scripts/experiments/qbittorrent_stopped_recheck.py      # 5.2.3；報告寫到 .local/experiments/results/qbittorrent-stopped-recheck-<版本>.json
python scripts/experiments/qbittorrent_stopped_recheck.py --image lscr.io/linuxserver/qbittorrent:latest   # compose 預設的那一個
python scripts/experiments/qbittorrent_stopped_recheck.py --image lscr.io/linuxserver/qbittorrent:4.4.5    # 對照組
python scripts/experiments/qbittorrent_stopped_recheck.py --only stopped_recheck_start --keep            # 只跑一個情境，留著容器
```

`jellyfin_naming.py` 必須從乾淨的 `/config` 跑（Jellyfin 的 DB 會留住舊掃描結果，插件裝過
就在了，量不到「未裝插件」的基準）：

```bash
docker compose -f scripts/experiments/compose.yml rm -sf jellyfin-1010 jellyfin-1011
rm -rf .local/experiments/jellyfin-1010 .local/experiments/jellyfin-1011
docker compose -f scripts/experiments/compose.yml up -d jellyfin-1010 jellyfin-1011
```

硬鏈接檢查（沒有相依，NAS 上 ssh 進去直接 `sh hardlink.sh /volume1/<share>` 也行）：

```bash
docker run --rm -v /srv/berth/data:/data -v "$PWD/scripts/experiments:/exp:ro"     alpine:3 sh /exp/hardlink.sh /data                        # 應該 PASS
docker run --rm -v /srv/a:/data/torrent -v /srv/b:/data/library     -v "$PWD/scripts/experiments:/exp:ro" alpine:3 sh /exp/hardlink.sh /data   # 應該 EXDEV 並回 1
```

收工：

```bash
docker compose -f scripts/experiments/compose.yml down -v
```

Windows 的 Git Bash 要在 `docker run` 前加 `MSYS_NO_PATHCONV=1`，否則 `/data` 這種容器內路徑
會被改寫成 `C:\Program Files\Git\data`。

動漫季集來源的量測（不需要任何容器，只打外部 API）。除了 `--self-test` 以外都要一把 TMDB 憑證，
從環境變數 `TMDB_API_KEY` 讀（v3 key 或 v4 token 都可以，取得步驟見〈先申請一把 TMDB API key〉）：

```bash
export TMDB_API_KEY=...                                              # Windows PowerShell 是 $env:TMDB_API_KEY
python scripts/experiments/anime_episode_source.py --self-test       # 換算器的手算樣例
python scripts/experiments/anime_episode_source.py                   # 完整量測（門檻 180 天，同 plan §4.4）
python scripts/experiments/anime_episode_source.py --gap-days 60     # 虛擬季門檻的敏感度比較
python scripts/experiments/anime_episode_source.py --discover        # 重新找 Mikan 的番組 id
```

第一次跑要抓好幾百個頁面（Mikan 的頁很大且常斷線），大約十來分鐘；抓過的東西會快取在
`.local/experiments/cache/`，之後重跑分析是秒級。結果見
[`docs/research/anime-episode-source.md`](docs/research/anime-episode-source.md)。

「集號 ≤ 第一季集數就送審核」這條規則的代價（M1 票 14d）。拿上面 `anime_episode_source.py` 的快取當正解、
丟進 Berth 的解析器，所以要憑證也要 `uv run`（快取被清掉的話會先重抓，約十分鐘）：

```bash
uv run --env-file .env python scripts/experiments/absolute_rule_cost.py    # A / B、收窄規則 R 的放行與漏掉
```

結果見 [`docs/research/profile-effect.md`](docs/research/profile-effect.md) §6.1.1。

## 目錄結構

```
berth/            後端套件
  cli.py          命令列進入點（berth serve、berth openapi、berth bench、berth rebuild-ledger）
  config.py       環境變數與路徑常數
  main.py         FastAPI app 組裝、lifespan
  adapters/       外部服務用戶端（qBittorrent、Jellyfin、TMDB…）
  api/            FastAPI routers
  db/             engine、session factory、migration 進入點
  domain/         純資料型別與狀態機
  migrations/     Alembic 環境與版本
  models/         SQLAlchemy ORM
  naming/         命名與路徑模板（純函式）
  parser/         解析階段（純函式）
  pipeline/       背景 asyncio 迴圈
  services/       改變狀態的命令函式
web/              前端（Vite + React + TypeScript）
deploy/           部署套件：Dockerfile、compose、preseed、.env.example
scripts/
  experiments/    對真實外部服務的驗證腳本（可重跑，結果在 docs/research/）
  fake_setup_server.py  以 Fake adapter 起一台 Berth，用來實跑驗證設定精靈
  record_tmdb_snapshots.py  錄 tests/fixtures/tmdb/ 的快照（語料加了新作品時跑）
tests/            後端測試
  e2e/              對真服務跑整條 M1 路徑（compose 覆寫檔、下載替身、pytest -m e2e）
  fixtures/e2e/     e2e 用的兩支 330 秒種子影片
  fixtures/http/    對真服務錄下來的回應，adapter 契約測試的輸入
  fixtures/mediainfo/  ffmpeg 造的一份真 Matroska（2 秒、17 KB），mediainfo adapter 的輸入
  fixtures/parser/  解析基準測試的語料（真實 torrent 的檔案清單）
  fixtures/tmdb/    語料用到的 TMDB 快照，錄一次即凍結
docs/             設計綱要、實作計劃、進度
  research/       查證與實驗的完整結果
.scratch/         各里程碑的票
```

依賴方向由 `import-linter` 強制，契約在 `pyproject.toml` 的 `[tool.importlinter]`：

- `api` 與 `pipeline` 只呼叫 `services`，不直接碰 `adapters`、`models`、`db`、`parser`、`naming`。
- `services` 可以用它下面的每一層。
- `adapters`、`models`、`parser`、`naming` 互不相依；`parser`、`naming`、`adapters` 只依賴 `domain`。
- `db` 只供 `services` 與 `models` 使用；`domain` 不依賴任何東西。

## 疑難排解

- `uv sync` 出現 `failed to hardlink ... (os error 396)`：repo 放在雲端同步目錄（OneDrive 之類）時硬鏈接不可用，改用 `UV_LINK_MODE=copy uv sync`，或在使用者層級的 `uv.toml` 設 `link-mode = "copy"`。

## 授權與歸屬

MIT，見 [LICENSE](LICENSE)。

<img src="docs/assets/tmdb.svg" alt="TMDB" height="28">

This product uses the TMDB API but is not endorsed or certified by TMDB.
（本產品使用 TMDB 的 API，但未經 TMDB 認可或認證。TMDB 的條款限非商業使用。）
