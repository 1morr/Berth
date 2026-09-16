# Berth

自託管的媒體取得與入庫協調器：把索引站或 RSS 命中的 torrent 送到 qBittorrent，下載完成後解析、比對 TMDB，以硬鏈接入庫到 Jellyfin，並維護可修復的帳本。

**M0（骨架）已完成，但整套流程要到 M1 才跑得通**：現在裝起來能做的是把四個服務接起來並看它們的健康狀態，還不能搜尋、下載或入庫。設計與決定見 `docs/design-brief.md`，架構與里程碑見 `docs/plan.md`，名詞表見 `CONTEXT.md`。

## 部署

`deploy/` 是完整的 compose 套件：Berth 加 qBittorrent、Jellyfin、Prowlarr，四個容器掛同一個媒體根。Linux 與 Windows 共用同一份 `docker-compose.yml`。

```bash
cd deploy
cp .env.example .env        # 改 DATA_ROOT 與 CONFIG_ROOT
docker compose up -d
```

開 <http://localhost:8383>，之後所有設定都在 Berth 的精靈裡完成，不需要分別打開另外三個服務的介面。
**唯一要離開 Berth 的一步是 TMDB 的 API key**，見下面的〈先申請一把 TMDB API key〉。

精靈是八個步驟、四個泊位：

| 泊位 | 步驟 | 套件內的服務 | 你自己的服務 |
| --- | --- | --- | --- |
| — | 1–2 建立 Berth 管理員、逐服務探測 | 探到 compose 主機名就是套件內 | 探不到就填位址，就地測連線 |
| BTH 1 | 3 Jellyfin | 確認版本 ≥ 12.0、建管理員、Movies / TV / Anime 三個媒體庫、API key | 只做檢查；「加入 Berth 路徑」是一顆要確認的按鈕 |
| BTH 2 | 4 qBittorrent | 套用五個建議鍵、設 WebUI 密碼 | 先顯示逐鍵差異再問要不要套用 |
| BTH 3 | 5–6 索引站與 TMDB | 加十個預設公開站 | 填既有 Prowlarr 或任一 Torznab 網址 |
| BTH 4 | 7–8 媒體庫路徑 | 自動建三條 Route | 勾選媒體庫與寫入目標 |

索引站那一步可以按「之後再說」（沒接只是搜尋不到東西）；**TMDB 那一步不行** —— 沒有一把測得過的憑證就沒有標題、季集與封面，精靈停在第 6 步。

每條 Route 建立時都會**真的建一個硬鏈接再比對 inode**，三個容器看到的不是同一個檔案系統就當場失敗，並指出是哪個容器少了哪個掛載。全部綠燈才走得到最後一步。

設定完成後精靈關閉，之後用 Jellyfin 的帳號登入；健康頁 `/health` 每 5 分鐘重跑同一組檢查。

> **compose 範本 pin 的 `ghcr.io/1morr/berth:latest` 還是空的。** GHCR 上目前只有預發佈的 `0.1.0-rc1`（`:latest` 要等第一個正式版本 tag），所以現在要跑 compose 得先在 repo 根目錄自己 build 一份：見下面的〈自己 build image〉。

| 服務 | Port | 備註 |
| --- | --- | --- |
| Berth | 8383 | 唯一需要開的介面 |
| qBittorrent | 8080（WebUI）、6881（BT） | WebUI 要密碼，密碼在精靈裡設定 |
| Jellyfin | 8096 | |
| Prowlarr | 9696 | |

已經有其中某個服務的人，把它從 `.env` 的 `COMPOSE_PROFILES` 拿掉，精靈會改用「既有服務」的表單接入；`berth` 沒有 profile，永遠會啟動。變數清單見 `deploy/.env.example`，裡面沒有任何秘密欄位。

### 先申請一把 TMDB API key

Berth **不內建任何 provider 的 API key**，TMDB 的憑證要你自己申請 —— 專案不替所有使用者背一把
共用憑證。它是必要的：作品標題、季集結構與封面全部來自 TMDB，沒有它精靈走不完。

1. 在 <https://www.themoviedb.org/signup> 註冊一個免費帳號（要收驗證信）。
2. 開 <https://www.themoviedb.org/settings/api>，申請 API key，用途（Type of Use）選
   **Personal / Education**；應用資訊隨便填得過去即可。核發是即時的，不必等審核。
3. 那一頁同時給兩把東西：**API Key (v3 auth)** 是 32 個十六進位字元，**API Read Access Token
   (v4 auth)** 是很長的一串 JWT。**兩種 Berth 都收**，貼哪一把都成立（v4 走標頭，不會落在
   任何一行 log 裡）。
4. 精靈第 6 步貼上去按「測試 TMDB」，綠燈才走得到下一個泊位。之後要換一把就在
   「設定 → 來源」重貼。

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
  精靈第 6 步或「設定 → 來源」都改得了。

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

**不要改 qBittorrent 的發佈 port 號碼。** qBittorrent 的 Host 檢查除了網域還會比對 port，
而且 `WebUI\ServerDomains=*` 也不放過 port 不符的請求。把 compose 的 `8080:8080` 改成
`18080:8080` 之類的偏移之後，瀏覽器開 `http://localhost:18080` 只會看到 `Unauthorized`，
真正的原因（`Invalid Host header, port mismatch`）只寫在 `docker compose logs qbittorrent` 裡。
要換 port 的話，`WEBUI_PORT` 與發佈 port 兩邊要一起改成同一個號碼。

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
| `WEB_ROOT` | `<repo>/web/dist` | 前端 build 產物。找不到時只提供 API |
| `EXT_ROOT` | `/ext` | 其他服務唯讀掛進來的設定目錄。目前只讀 `${EXT_ROOT}/prowlarr/config.xml` 的 `<ApiKey>` |
| `PROWLARR__AUTH__APIKEY` | 無 | Prowlarr 的 API key。用這個環境變數部署 Prowlarr 的人把同一個值也給 Berth，就不必唯讀掛它的設定目錄；有值時蓋過 `config.xml` |

### 後端

```bash
uv run berth --version      # CLI
uv run berth serve          # 啟動程序（--reload 為開發模式）
uv run berth openapi        # 印出 OpenAPI 文件（--output 寫檔）；前端型別的上游
uv run berth bench          # 解析基準測試（見下）；離線跑，離開碼是 CI 的門檻
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
```

### API 型別

前端不手寫 API 的形狀：`web/src/api/schema.d.ts` 由後端的 OpenAPI 產生，`web/src/api/*.ts`
只把後端的類別名（`RouteOut`）換成前端在講的名字（`RouteView`）。

```bash
pnpm -C web gen:api         # berth openapi → web/openapi.json → src/api/schema.d.ts
```

- **改了任何 pydantic 的 request / response model 就重跑它**，產出的 `schema.d.ts` 與後端的
  改動放同一個 commit。CI 的 `api-types` job 跑同一個指令再比對，型別檔過期時紅燈。
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

### UI 的 Fake 後端

精靈與健康頁的 UI 不必真的有四個容器也能實跑：`scripts/fake_setup_server.py` 起一台真的 Berth
（真的 API、真的資料庫、真的前端 build），只把三個外部服務換成 `adapters/*/fake.py`。

```bash
pnpm -C web build                                          # 先有前端產物
uv run python scripts/fake_setup_server.py                 # http://127.0.0.1:8484
uv run python scripts/fake_setup_server.py --scenario mixed
```

| `--scenario` | 演的是什麼 |
| --- | --- |
| `bundled`（預設） | 乾淨的 compose：三個服務都判為套件內，泊位 1–3 全部走得完。十個預設索引站裡有五個連不上（訊息取自真的 Prowlarr 那一輪），逐站成敗看得到 |
| `outdated` | qBittorrent 的 Web API 低於 2.8.4：第 4 步拒絕接入並給升級指令 |
| `mixed` | NAS 的常見組合：既有 Jellyfin（跑過自己的精靈、兩個媒體庫，其中一個掛 TVDB）、qBittorrent 已設密碼、Prowlarr 已有索引站 |
| `starting` | 容器還在啟動：qBittorrent 連不上，Prowlarr 讀不到 API key |
| `absent` | Jellyfin 不在 `COMPOSE_PROFILES` 裡：探不到，要在第 2 步填自己那一台的位址 |
| `old-jellyfin` | 既有 Jellyfin 還停在 10.11（其餘兩個服務照 `bundled`，擋路的只留一個）：泊位 1 紅燈，說出目前版本、為什麼要 12，以及升級前後要做的事；健康頁上同一台也是紅的 |
| `signed-out` | 精靈已跑完，畫面從登入頁開始。`skipper` / `harbour` 是管理員，`deckhand` / `rope` 是普通使用者（看不到設定入口） |
| `unmounted` | Jellyfin 少了媒體庫目錄的掛載：泊位 4 的第四條纜繩失敗，看「哪個容器少了哪個掛載」與 compose 修正片段 |
| `healthy` | 精靈已跑完、三條 Route 綠燈、四項健康檢查全綠：健康頁 `/health` 與服務設定頁 `/settings/services` 的起點。帳號同 `signed-out` |
| `degraded` | 同上，但索引站在第一輪檢查之後掛掉：按「立即重測」就會看到那一項變紅、其餘三項不動，以及「最後成功」還留著 |
| `drifted` | 同上，但有人把 qBittorrent 的 `auto_tmm_enabled` 改掉了：看設定頁的逐鍵差異表與「還原建議設定」 |
| `routes` | Route 設定頁 `/settings/routes`（票 14）：同 `healthy`，另外 TV 媒體庫在 Jellyfin 上多掛一顆碟（新增第二條 Route 會全綠）、Movies 多一條沒掛進 Berth 的路徑（在那裡建 Route 會紅、維持停用），TV 那條 Route 有一筆已入庫的下載（刪除鍵換成「刪不得」與一鍵停用）；新增時選 Anime 沒有空路徑，給一條到 Jellyfin 媒體庫設定的連結 |
| `discover` | 探索頁 `/`：三個外部服務仍是替身，但 TMDB 打**真的** `api.themoviedb.org`。憑證從環境變數 `TMDB_API_KEY` 讀（v3 key 或 v4 read access token 都收），沒設就變成「憑證缺失」那個畫面 |
| `tmdb-down` | 憑證有、TMDB 連不上：探索頁的每個 feed 各自顯示服務回的原文與「重試」，而不是一片空白 |
| `search` | Media 詳情頁的搜尋結果表：TMDB 與**索引站都打真的**。索引站位址從 `BERTH_INDEXER_URL` / `BERTH_INDEXER_KEY` 讀，沒設就退回替身（結果表是空的，那本身也是要驗的畫面）。一次搜尋 35–85 秒 |
| `submit` | 送單與下載列表 `/jobs`：TMDB 打真的，索引站給三筆磁力連結的替身結果（形狀取自真的那一輪）。送單、解析、Job 與時間線走的都是產品自己的程式碼，只有 qBittorrent 是替身 |
| `submit-failing` | 同上，但 qBittorrent 收不下：送單失敗那一列、服務回的原文，以及「重新送單」 |
| `plan` | 下載完成 → **Import Plan**（票 11）：索引站給兩包替身結果——一包對得上的批次（自動入庫）與一包對不到任何一集的 OST（停在待審核）。qBittorrent 是替身，但它會把那幾個檔案**真的寫進 save path** 並報成 100%，所以 poller 走完狀態機、planner 算出真的 Plan：解析、命名、mediainfo、TMDB 快照全是產品自己的程式碼 |
| `inventory` | 媒體庫頁 `/library` 與 Media 詳情的「檔案與版本」（票 13）：同 `plan` 的兩包，加上一台會「掃到」入庫檔案的替身 Jellyfin。送單約 30 秒後 resolver 找到 Series，卡片從「Jellyfin 還在掃描」換成「在 Jellyfin 開啟」；OST 那一包是「待審」篩選要找到的那一格。深連結指向瀏覽器主機名的 8096，那台 Jellyfin 不存在——Jellyfin 那一端要用真的一套驗 |
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
以便跨次保留進度。精靈第 7 步（媒體庫路徑）會**真的**建目錄、寫探測檔並呼叫 `link()`，所以三層
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
python scripts/experiments/prowlarr_host_config.py     --base-url http://localhost:19696 --config .local/experiments/prowlarr
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

Route profile 對解析結果的作用（M1 票 14c）。不連線、不需要憑證，但 import `berth`，所以用 `uv run`：

```bash
uv run python scripts/experiments/profile_effect.py    # 語料四種 profile 組合的報表、逐檔差異、分支側錄
```

結果見 [`docs/research/profile-effect.md`](docs/research/profile-effect.md)。

## 目錄結構

```
berth/            後端套件
  cli.py          命令列進入點（berth serve、berth openapi、berth bench）
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
