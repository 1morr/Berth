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

精靈是八個步驟、四個泊位：

| 泊位 | 步驟 | 套件內的服務 | 你自己的服務 |
| --- | --- | --- | --- |
| — | 1–2 建立 Berth 管理員、逐服務探測 | 探到 compose 主機名就是套件內 | 探不到就填位址，就地測連線 |
| BTH 1 | 3 Jellyfin | 建管理員、Movies / TV / Anime 三個媒體庫、API key、裝 MergeVersions、重啟 | 只做檢查；「加入 Berth 路徑」與「安裝 MergeVersions」各是一顆要確認的按鈕 |
| BTH 2 | 4 qBittorrent | 套用五個建議鍵、設 WebUI 密碼 | 先顯示逐鍵差異再問要不要套用 |
| BTH 3 | 5–6 索引站與 TMDB | 加十個預設公開站、內建 TMDB 憑證 | 填既有 Prowlarr 或任一 Torznab 網址；兩步都可以跳過 |
| BTH 4 | 7–8 媒體庫路徑 | 自動建三條 Route | 勾選媒體庫與寫入目標 |

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
- **Jellyfin**：同一部片的多個版本要合併需要 [MergeVersions](https://github.com/danieladov/jellyfin-plugin-mergeversions) 插件。套件內的 Jellyfin 由精靈自動安裝並重啟；既有的 Jellyfin 是一顆要確認的按鈕。
- **Prowlarr**：不預置任何東西，Berth 唯讀掛載它的設定目錄以讀取它自動產生的 API key。

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
| `failing` | 套件內 Jellyfin，但插件下載一直失敗：看第 8 步的失敗樣子與可複製的手動步驟 |
| `installed` | 既有 Jellyfin 而且 MergeVersions 已裝好：兩顆按鈕的「已完成」樣子 |
| `signed-out` | 精靈已跑完，畫面從登入頁開始。`skipper` / `harbour` 是管理員，`deckhand` / `rope` 是普通使用者（看不到設定入口） |
| `unmounted` | Jellyfin 少了媒體庫目錄的掛載：泊位 4 的第四條纜繩失敗，看「哪個容器少了哪個掛載」與 compose 修正片段 |
| `healthy` | 精靈已跑完、三條 Route 綠燈、四項健康檢查全綠：健康頁 `/health` 與服務設定頁 `/settings/services` 的起點。帳號同 `signed-out` |
| `degraded` | 同上，但索引站在第一輪檢查之後掛掉：按「立即重測」就會看到那一項變紅、其餘三項不動，以及「最後成功」還留著 |
| `drifted` | 同上，但有人把 qBittorrent 的 `auto_tmm_enabled` 改掉了：看設定頁的逐鍵差異表與「還原建議設定」 |

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

動漫季集來源的量測（不需要任何容器，只打外部 API）：

```bash
python scripts/experiments/anime_episode_source.py --self-test       # 換算器的手算樣例
python scripts/experiments/anime_episode_source.py                   # 完整量測（門檻 180 天，同 plan §4.4）
python scripts/experiments/anime_episode_source.py --gap-days 60     # 虛擬季門檻的敏感度比較
python scripts/experiments/anime_episode_source.py --discover        # 重新找 Mikan 的番組 id
```

第一次跑要抓好幾百個頁面（Mikan 的頁很大且常斷線），大約十來分鐘；抓過的東西會快取在
`.local/experiments/cache/`，之後重跑分析是秒級。結果見
[`docs/research/anime-episode-source.md`](docs/research/anime-episode-source.md)。

## 目錄結構

```
berth/            後端套件
  cli.py          命令列進入點（berth serve、berth openapi）
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
tests/            後端測試
  fixtures/http/  對真服務錄下來的回應，adapter 契約測試的輸入
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
