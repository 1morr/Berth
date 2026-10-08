# 開發

給要改 Berth 程式碼的人：開發環境、指令、測試、演練伺服器與實驗腳本。**本檔是開發指令的單一來源**；新增或改動指令時同輪更新這裡。使用者的部署與操作在根目錄 [README](../README.md) 與 [`docs/guide/`](guide/)。

## 環境需求

| 工具 | 版本 | 用途 |
| --- | --- | --- |
| [uv](https://docs.astral.sh/uv/) | ≥ 0.12 | 後端套件與虛擬環境管理 |
| Python | 3.13（由 `.python-version` 指定，uv 會自動下載） | 後端執行環境 |
| Node.js | ≥ 24 | 前端建置 |
| [pnpm](https://pnpm.io/) | ≥ 11 | 前端套件管理 |

## 開發指令

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
| `JELLYFIN_PORT` | `8096` | 套件內 Jellyfin 在宿主上發佈的 port；「在 Jellyfin 開啟」沒填對外網址時開這個 port。compose 從部署套件 `.env` 的同名變數傳進來 |
| `PROWLARR_PORT` | `9696` | 套件內 Prowlarr 在宿主上發佈的 port；精靈頁 4 與設定頁「在 Prowlarr 加私站」的連結開這個 port。compose 從部署套件 `.env` 的同名變數傳進來 |
| `QBITTORRENT_WEBUI_PORT` | `8080` | 套件內 qBittorrent 的 WebUI port（容器內外同一個號碼）；精靈頁 2 選套件內時連 `http://qbittorrent:<它>`。compose 從部署套件 `.env` 的同名變數傳進來 |
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

使用者那一面（什麼時候用、畫面上的按鈕）在 [`guide/backup-and-reinstall.md`](guide/backup-and-reinstall.md)；這裡是指令與判定的細節。

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

**畫面上也按得到**（M4 票 60）：媒體庫裡有帳本不認得、還沒被重建判過的檔案時，精靈完成頁與 `/issues` 最上面
說有幾個，一顆「從媒體庫重建帳本」（`POST /api/issues/rebuild-ledger`，對帳正在跑時是 409），按完說找回幾個、
幾個變成非受管檔案。判過的不再算：配不上的那幾件寫著理由（對帳再記一次也留著），被忽略的也算判過。

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
[`tests/fixtures/parser/README.md`](../tests/fixtures/parser/README.md)。

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
pnpm -C web e2e             # playwright 對演練情境跑十七條流程（先 build，見〈前端 e2e〉）
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

### 部署套件

使用者拿到的是 release 附件 `berth-deploy-<版本>.zip` 與同內容的 `berth-deploy.zip`（compose、`.env.example`、
`preseed/`，解壓出 `berth/`）。release workflow 與本機用同一支腳本產生：

```bash
uv run python scripts/deploy_bundle.py 0.2.0     # 寫到 dist/
```

`v*` tag 上 `.github/workflows/release.yml` 先推 image 到 GHCR，再 `gh release create` 帶這兩個附件；`-rc` 標成
prerelease，不動 `releases/latest/download/`。使用者那一面（tag 的意思、升級步驟）在
[`guide/upgrading.md`](guide/upgrading.md)。

### e2e

M1 的整條路徑、M1.5 的權限與瀏覽、M2 的修正與對帳、M3 的 RSS 對**真的** qBittorrent 與 Jellyfin 跑一遍（plan §10、`tests/e2e/`）。
**一次 compose、一次精靈、一次入庫，四個模組共享**（fixture 在 `tests/e2e/conftest.py`；檔名的數字就是執行順序）：

- `test_1_m1_pipeline.py`：精靈六頁只走 Berth 的 API（三個服務都選套件內），送一部美劇一季、一部動漫一季、一部電影，等它們不經人工、
  依序走過完成 → 規劃 → 入庫，再驗硬鏈接兩端同一個 inode、帳本逐檔記下的 item id 就是 Jellyfin 在那條路徑上的 item。
- `test_2_m15_library.py`：以 Jellyfin API 建一個只開放一個媒體庫的一般使用者，用它登入 Berth——看不到沒權限的
  媒體庫、直接請求也被拒；不經 Berth 放進那個媒體庫的作品照樣在牆上；某一集的 `item_id` 就是 Jellyfin 在帳本
  那條路徑上的 item；標為已看 / 未看之後那個帳號自己的觀看紀錄真的變了；帳號被停用之後 session 結束。
  最後停掉 Jellyfin 容器，驗「問不到 Jellyfin」那一句（跑完會把它起回來）。
- `test_3_m2_repair.py`：三種人為破壞各造一次——在 Jellyfin 裡刪掉一集、用複製品取代硬鏈接、手動刪掉 complete
  裡的來源（外加 complete 裡一個沒人認領的目錄）——手動對帳偵測到，按 Issue 上的動作修好，再對帳一次確認
  那一件沒有再開；以及整個 Anime 媒體庫的內容刪光之後按一次「重新入庫」，回到同樣的路徑、同一個 inode、同樣的帳本列。
- `test_4_m3_rss.py`：plan §11.4 的八條驗收。一個 Mikan 聚合 feed（說了自動綁定送進 Anime）自動綁定並補舊集、
  從 Media 頁訂閱的 acg.rip 搜尋 feed 第一輪全部下載而合集被排除、第二輪的新集自動入庫；同一集兩個字幕組與
  同組 v1、v2 並存；確認過的 RSS Series 的新集不進 audit；一個 split-cour（Re:ZERO，TMDB 只有一季）的第一批
  被播出日比對擋在審核，改一份並套用到 RSS Series 之後其餘自動入庫；在 Jellyfin 裡改掉一集的集號，對帳開出
  `jellyfin_item_mismatch`。

Prowlarr 也會起來讓精靈選套件內、測到連上，但索引站那一頁跳過、送單直接帶 `.torrent` 網址——搜尋不在 e2e 裡。套件內的媒體庫
一開始是空的，反查要等 Berth 請 Jellyfin 掃描之後那一輪，所以一次**約 20 分鐘**，平常的 `uv run pytest` 不收它
（`-m 'not e2e'`）。

```bash
uv run --env-file .env python -m tests.e2e.stack       # 要 .env 裡的 TMDB_API_KEY：精靈 TMDB 那一頁是閘門
uv run --env-file .env python -m tests.e2e.stack -k m3 # 多給的參數原樣交給 pytest
```

`tests/e2e/stack.py` 一條指令走完：先拆掉上一輪留下的 → build → `up` → `pytest -m e2e tests/e2e`
→ 失敗時印出容器狀態與 log → **不論結果都 `down --volumes`，跑完不留容器、不留資料**。

- **試跑環境開著也能跑**（M4 票 34）：e2e 有自己的專案名（`berth-e2e`）、容器名（`berth-e2e-*`）、網路與
  子網（`10.231.0.0/16`，在 Docker 自動配發的範圍外）、host port（`28383`、`28096`、`28080`、`26881`、`29696`），`/data` 與四份
  `/config` 都是它自己的 named volume；全在 `tests/e2e/compose.yml` 與 `tests/e2e/e2e.env` 換掉，正式的
  `deploy/docker-compose.yml` 不動。`tests/unit/test_e2e_stack.py` 守著每一個名字、port 與宿主路徑都換掉了。
- **環境變數不外洩，也不被你的 shell 蓋掉**：compose 的變數只放進子程序的環境，`e2e.env` 的值優先於你
  shell 裡的同名變數（compose 自己讓 shell 優先於 `--env-file`，一個沒清掉的 `DATA_ROOT` 就會把 e2e
  掛到試跑環境的媒體庫上）。不要再 `export CONFIG_ROOT` / `DATA_ROOT`。
- **不 `pull`**：`lscr.io/linuxserver/*` 的 tag 與試跑環境共用，拉新的會讓試跑環境下一次 `up -d` 換 image。
  本機用的是已經有的那一份；要對新版跑，先在試跑環境那邊自己 `docker compose pull`。CI 的 runner 每次都是空的，
  拉到的就是最新的。
- **不加 `--wait`，`up` 完馬上跑測試**：這是冷啟動閘門（票 06h）。精靈在 Jellyfin 與 Prowlarr 還在啟動時就開始，
  三個服務頁都選套件內，各自照常每 2 秒重測到連上（頁 1 連上之後成立擁有者），都不按「重新測試」；測一輪就全部連上的話
  測試會失敗，因為那一輪沒碰到啟動中的那幾秒。所以 `up` 之前先 `build`，不要讓 `up` 之後還有東西要等（缺的 image `up` 會先拉完才啟動任何容器）。
- 精靈那一段也守著 M4 之後的行為：頁 2 先送一組 qBittorrent 不收的密碼（停在頁 2、說得出被拒），qBittorrent
  的全域預設儲存路徑被改到別處之後建 Route 與送單照常（Berth 不寫也不看全域偏好），完成前停掉 qBittorrent
  並收回頁 4 的「之後再說」——完成照頁序先送回頁 2、再送回頁 4。頁 4 先把套件內那一台當成既有接：錯的 key 是
  `auth_required`、對的 key（從 berth 唯讀掛載的 `config.xml` 讀）連上，按「之後再說」之後換回套件內，「之後再說」
  不跟過來（換台的清理，M4 票 39）。
- 沒有 peer 可以真的下載：`torrents` 容器在 `/data/e2e/staging` 造出三包發佈（檔案清單取自 benchmark
  語料、影片是 `tests/fixtures/e2e/` 的種子，標頭的片長照語料的 TMDB 快照改寫——片長驗證會擋），測試在
  送單之後把它們複製到 qBittorrent 說的下載路徑再叫它 recheck。
- 公開 RSS 站不能進 CI：`sites` 容器（`tests/e2e/sites.py`）以 network alias 冒充 `mikanani.me`、
  `acg.rip`、`nyaa.si`，照測試寫進去的輪次送出 feed、單集頁、番組頁與 `.torrent`（發佈取自票 07 的
  fixture）。它講 HTTPS，憑證由 `tests/fixtures/e2e/tls/` 的測試 CA 簽（`tests/e2e/make_tls.py` 產生）；
  `ca-bundle` 先把系統的 CA 清單接上這張 CA，Berth 以 `SSL_CERT_FILE` 信它。
- GitHub Actions 的 `.github/workflows/e2e.yml` 在 nightly、`v*` tag 與手動觸發時跑同一組指令，
  TMDB 憑證是 repo secret `TMDB_API_KEY`。

### 前端 e2e

`web/e2e/` 以 playwright 對〈UI 的 Fake 後端〉的演練情境跑十七條流程（除了送單、審核、待處理與自動綁定那四條，各有 1280 與 390 兩份，共三十個 project），一條流程一台 server、各佔一個 port
（`web/playwright.config.ts` 自己起、跑完收掉）：

| 流程 | 情境 | port（1280 / 390） |
| --- | --- | --- |
| 精靈六頁走完（三頁都選套件內、選之前不發請求；頁 1 建 Jellyfin 管理員成為擁有者、密碼只在頁 1 打兩次（頁 2、頁 4 的介面登入自動沿用）、頁 3 進頁自動建立並檢查、再展開清單加一個媒體庫、每一格停在結果上、回頭再往前、試搜與移除），之後以同一組帳密登入、是管理員 | `bundled` | 8491 / 8501 |
| 既有服務：三頁都選既有（說出同主機條件與 `COMPOSE_PROFILES` 那一行）、以既有 Jellyfin 的管理員成為擁有者（打錯密碼被拒）、填 qBittorrent 帳密（測試通過就做完、沒有確認鍵）、加 Berth 路徑並選它當寫入目標、貼 Prowlarr 的 key（先貼錯的：與頁 1、2 同一個錯誤版面、右欄不寫「已取得」） | `mixed` | 8495 / 8505 |
| 冷啟動：服務還在啟動時選套件內，Jellyfin 與 qBittorrent 各自每 3 秒重測到連上，不按重新測試 | `starting` | 8496 / 8506 |
| 精靈跑完之後：`/setup` 導向設定頁，加一個索引站並試搜、換 TMDB key | `healthy` | 8497 / 8507 |
| 從作品頁送單，一路走到已入庫 | `import` | 8492 |
| `/review` 確認一筆 audit | `review` | 8493 |
| 作品頁的「下載」段：列出還沒了結的四筆、進度自己動、展開看檔案與季集、季表標籤連到那一筆、「全部」多一筆 | `downloads` | 8517 / 8518 |
| `/issues` 修一條 `library_link_missing` | `issues` | 8494 |
| `/rss` 加 Mikan feed、輪詢、綁定待綁定的那一部，下載列表上兩集都已入庫 | `rss` | 8498 / 8508 |
| `/rss` 加 Feed 時選自動綁定送進 Anime：輪詢之後那一部自動綁定並補舊集，下載列表上已入庫 | `rss` | 8516 |
| `/rss` 排除條件：寫壞的正則存不進去、全域與 RSS Series 那一層擋下的、第二個 Feed 帶同一個 hash 的是重複 | `rss` | 8499 / 8509 |
| `/rss` 新的 acg.rip 搜尋 feed：第一輪停在預覽、合集在「排除」那一組，選「只追之後的」之後整份歷史略過 | `rss` | 8488 / 8489 |
| `/rss` 綁定 Mikan 的 RSS Series 時補舊集，之後每日補漏 | `rss` | 8486 / 8487 |
| split-cour 的第一批已入庫：在 `/review` 改一集並套用到 RSS Series，其餘 11 集跟著搬，全部確認 | `rss-split-cour` | 8484 / 8485 |
| 連載中的 split-cour 第一批整批擋在審核：改一份計劃的一列並套用到 RSS Series，其餘 11 份重新規劃、自動入庫，改的那一份核准 | `rss-split-cour-airing` | 8510 / 8511 |
| 一次性 RSS 連結：讀單一 feed 勾三集送單、acg.rip 那一份標出合集 | `rss` | 8512 / 8513 |
| 詳情頁訂閱：Mikan 搜番組、選字幕組、整季進下載列表；再以標題建 acg.rip 搜尋 feed，第一輪就地預覽 | `rss` | 8514 / 8515 |

精靈、設定頁與 RSS 那幾條在兩種寬度各走一次（`playwright.config.ts` 的 `NARROW`），每一格都留一張整頁截圖在
`web/test-results/<那一條>/`，通過的那一輪也留著。

```bash
pnpm -C web build                                          # server 發的是 web/dist
pnpm -C web exec playwright install chromium               # 第一次
pnpm -C web e2e                                            # 約 2 分鐘（三十台替身）
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
| `bundled`（預設） | 乾淨的 compose：三個服務選套件內都連得上、全部走得完。九個預設索引站裡有四個連不上（訊息取自真的 Prowlarr 那一輪），逐站成敗看得到；加完之後試搜，Mikan 演「搜尋時連不上」，其餘站各回幾筆 |
| `outdated` | qBittorrent 的 Web API 低於 2.8.4：頁 2 拒絕接入並給升級指令 |
| `mixed` | NAS 的常見組合：既有 Jellyfin（跑過自己的精靈、兩個媒體庫，其中一個掛 TVDB；管理員 `owner` / `s3cret`）、qBittorrent 已設密碼（選既有、填任何位址與帳密都測得過；選套件內是「要求帳密」）、Prowlarr 已有索引站。三頁都選既有才走得完。兩個媒體庫的舊路徑是暫存目錄底下真的存在的 `nas/movies`、`nas/anime`，Route 的第三條纜繩才看得到它們，精靈走得完 |
| `starting` | 四個容器同時起來（票 06g 量到的時間線，照測試次數演，前端每 3 秒一次）：選了套件內之後 Jellyfin 先回不像它自己的東西、再回兩次 503「還在載入」，約 9 秒後連上；qBittorrent 第一次連不上；Prowlarr 連不上五次，約 15 秒。不必按「重新測試」，之後與 `bundled` 一樣走得完 |
| `key-missing` | 同 `bundled`，但 Prowlarr 的設定目錄沒有唯讀掛進 Berth：頁 4 選套件內之後讀不到 API key，就地貼上 |
| `absent` | Jellyfin 不在 `COMPOSE_PROFILES` 裡：頁 1 進頁「套件內」卡片就說它沒在跑、給起回來的兩種補法，選了是「主機名解不到」；改選既有、填任何位址就接得上 |
| `berth-only` | 只有 Berth（`COMPOSE_PROFILES=`）：三個服務頁的「套件內」卡片進頁都說沒在跑；其餘同 `absent` |
| `old-jellyfin` | 既有 Jellyfin 還停在 10.11（其餘兩個服務照 `bundled`，擋路的只留一個）：頁 1 擁有者那一步紅燈，說出目前版本、為什麼要 12，以及升級前後要做的事；健康頁上同一台也是紅的 |
| `signed-out` | 精靈已跑完，畫面從登入頁開始。`skipper` / `harbour` 是管理員，`deckhand` / `rope` 是普通使用者（看不到設定入口） |
| `unmounted` | Jellyfin 少了媒體庫目錄的掛載：泊位 4 的第四條纜繩失敗，看「哪個容器少了哪個掛載」與 compose 修正片段 |
| `rss` | RSS 頁 `/rss`（M3 票 08）：同 `healthy`，一個請求都不出網。Mikan 是替身：加 `https://mikanani.me/RSS/MyBangumi?token=REDACTED`（任何 token 都一樣，替身只認這一條網址）、按「立即輪詢」，票 07 錄下來的聚合 feed 12 筆長出 11 個待綁定的 RSS Series（單集頁照 `tests/integration/test_rss.py` 合成）。TMDB 也是替身，搜「Kimi ga Shinu made Koi wo Shitai」或「与你相恋到生命尽头」找得到那一部；在《与你相恋到生命尽头》那一列綁到它與 Anime，兩集的 `.torrent` 換成這台自己生的，qBittorrent 收下就當場完成，幾秒後 `/jobs` 上兩筆都已入庫。票 11 起另有錄下來的 acg.rip 搜尋 feed：加 `https://acg.rip/.xml?term=Kamiina+Botan`、按「立即輪詢」，30 筆停在頁首的第一輪預覽（8 筆合集被排除）。票 19 起在《与你相恋》的詳情頁（`/media/tv:262000`）按「新增訂閱」：以任何一個名字搜 Mikan 都是番組 4009（搜尋頁是合成的），訂閱喵萌奶茶屋&LoliHouse 就是整季 12 筆；acg.rip 以任何一個名字建搜尋 feed 讀到的都是錄下來的《与你相恋》那一份。帳號同 `signed-out` |
| `rss-split-cour` | 改正並套用到 RSS Series（M3 票 13）：同 `rss`，但 TMDB 把《与你相恋》的兩個 cour 併成一季 24 集。綁定時補舊集，12 集全部落在 S01E01–E12（錯的：字幕組的第二 cour 從 01 重數），在 `/review` 是這個 RSS Series 的第一批、一組；把第 1 集改成 S01E13 並勾「套用到這個 RSS Series」，其餘 11 集跟著搬到 14–24，再按「全部確認」 |
| `rss-split-cour-airing` | 從審核裡套用到 RSS Series（M3 票 14b）：同 `rss-split-cour`，但第二 cour 正在播（2026-07-02 起）。綁定時補舊集，12 集照字面對到一月播出的 S01E01–E12，播出日比對把 12 份計劃整批擋在 `/review` 的「要你決定」、一集都沒入庫；在第 1 集那一份按「改」、起集填 13、勾著「套用到這個 RSS Series」套用，其餘 11 份重新規劃、自動入庫（第一批，等全部確認），改的那一份等你核准 |
| `rss-runtime` | 片長驗證（M3 票 15）：同 `rss`，但 mediainfo 是替身——檔名第 11 集的量到 12:05，其餘 24 分鐘（TMDB 每集 24 分鐘）。綁定《与你相恋》之後第 11 集那一份停在 `/review` 的「要你決定」，理由說出兩個片長；其餘 11 集照常入庫（第一批） |
| `budget` | 一個站一份請求預算（M3 票 20）：同 `rss`，但 Mikan 的預算只有 6 個，替身索引站背後也是 Mikan。TMDB 上《与你相恋》有七季、每季兩集都播完了：詳情頁（`/media/tv:262000`）按「搜這部作品缺的集」，預覽說分批、這一批問 S01–S05、之後還有 1 批，問完用掉 5 個；下一批也是 5 個放不下，那一行說出何時放得下，照樣按「問下一批」是「等請求預算」。之後到 `/rss` 加 Mikan 聚合 feed、按「立即輪詢」：Feed 本身用掉最後一個，12 個單集頁全被擋（那一列的原文說是預算）；健康頁的「請求預算」列出 `mikanani.me 6 / 6`、搜尋與輪詢各用了幾個、被延後的是哪兩種。帳號同 `signed-out` |
| `healthy` | 精靈已跑完、三條 Route 綠燈、四項健康檢查全綠：健康頁 `/health` 與設定頁 `/settings/*`（五個分頁：換 TMDB key、加站試搜移除都在這裡演得出來）的起點。帳號同 `signed-out` |
| `degraded` | 同上，但索引站在第一輪檢查之後掛掉：按「立即重測」就會看到那一項變紅、其餘三項不動，以及「最後成功」還留著 |
| `review` | 審核佇列 `/review`（M2 票 06）：同 `issues`，另外 SPY×FAMILY 第二季兩集（只寫絕對集號 26、27，累計換算成 S02E01、S02E02，信心 medium）真的硬鏈接進媒體庫、帳本與 Plan Item 都掛 audit。按「確認」清旗標；按「撤銷」真的把那一條鏈接拆掉，那一筆下載回到待審核——之後以 `deckhand` / `rope` 登入，`/jobs` 與 SPY×FAMILY 的詳情頁說「等管理員審核」。這兩集是同一筆下載，收成一組、收起時說出為什麼是 medium，按「全部確認」一次清掉（M3 票 05）。Issue 不在這一頁（M3 票 05），頁尾一行「另有 N 件待處理」連到 `/issues`。另有一筆 `- 05` 下載完成（M2 票 07）：只寫集號、沒超過第一季的 25 集，規劃器算成低信心、提案 S01E05，停在「要你決定」那一段——逐列改季集看目標路徑當場換掉，按「核准並入庫」真的硬鏈接進媒體庫；按「拒絕」就重新規劃。再一筆 S01E03 + OVA 下載完成（M2 票 08）：媒體庫裡已經有一份一模一樣的 S01E03（路徑與 Tags 照解析器算），所以規劃器略過它、佇列上一列「重複」（取代 / 保留兩者 / 跳過，都真的動磁碟）；OVA 2 對不到任何一集，佇列上一列「對不到」，指派到 S00E02 真的建硬鏈接。伺服器起來約 60 秒後規劃器第一輪才算出這兩列 |
| `downloads` | 作品頁的「下載」段（M4 票 12）：同 `import`，SPY×FAMILY 已經有五筆下載——`- 08` 在 qBittorrent 排隊（`queuedDL`、還沒有檔案清單）、`- 25` 下載中而且替身每一輪多 7%（5%–95% 循環，看得到進度自己動；pre-plan 提案 S01E25 待審，季表那一集是「下載中」）、`- 01` 停在待審核（季表 S01E01「卡住」）、`- 05` 已入庫一個檔案待確認、`- 04` 已入庫確認過（只在「全部」） |
| `routes` | Route 設定頁 `/settings/routes`（票 14）：同 `healthy`，另外 TV 媒體庫在 Jellyfin 上多掛一顆碟（新增第二條 Route 會全綠）、Movies 多一條沒掛進 Berth 的路徑（在那裡建 Route 會紅、維持停用），TV 那條 Route 有一筆已入庫的下載（刪除鍵換成「刪不得」與一鍵停用）；新增時選 Anime 沒有空路徑，給一條到 Jellyfin 媒體庫設定的連結 |
| `issues` | 待處理頁 `/issues` 與對帳（M2 票 05）：同 `healthy`，另外真的入庫一包三集的動漫（來源在 complete、媒體庫那一份是真的硬鏈接），並把其中第二集的媒體庫檔案刪掉——使用者在 Jellyfin 按刪除之後就是這樣。按「立刻對帳」真的比四方並寫下一件 Issue，按「重新鏈接」真的 `os.link` 把它接回來。另外三種破壞（M2 票 09）：第三集被一份一樣大的複製品取代（「以硬鏈接取代」真的換回硬鏈接）、complete 裡一個沒人認領的目錄（「刪除這個目錄」真的整棵刪掉）、媒體庫裡一個手放的檔案（只列出，沒有會刪的按鈕）。管線與健康檢查那幾種（M2 票 09c）：三筆下載到一半的 SPY×FAMILY，替身 qBittorrent 說一筆 `missingFiles`、一筆 `error`、一筆已經不在——起來之後 poller 第一輪就開出三件，「重新校驗」「重試」「重新送單」各自讓它們離開壞掉的狀態；或者 `curl -X POST 'http://127.0.0.1:8484/demo/qbittorrent/fix?hash=<hash>'` 演使用者在 qBittorrent 裡自己修好那一筆（M3 票 02），poller 下一輪（至多 30 秒）把 Job 接回、那一件由系統收掉，時間線多一筆「已接回」；Anime 媒體庫掛著 TVDB，所以一開始就有一件 TVDB（只有「忽略」，按了之後「立即重測」也不會再開）。磁碟空間那一件要到設定的 qBittorrent 那一頁把門檻調到比這台機器剩的還大，`/issues` 當場多一件，調回來當場收掉。認領類三顆（M2 票 10，替身 TMDB 搜得到 `spy`）：媒體庫裡第四集是真的硬鏈接但帳本上沒有它——「認領進帳本」長回一列，`Hand Placed` 那一件按下去說出配不上的理由；qBittorrent 上一筆 `[Sub] SPY×FAMILY - 07` 沒有 Job——「認領並建立下載」選作品，下載列表多一筆；`[Old] Forgotten Batch` 按「重新入庫」選作品，規劃器接手。`/jobs` 上入庫完的那一筆，在它的詳情頁（展開那一列 → 「下載詳情」）有「重新入庫」 |
| `discover` | 探索頁 `/`：三個外部服務仍是替身，但 TMDB 打**真的** `api.themoviedb.org`。憑證從環境變數 `TMDB_API_KEY` 讀（v3 key 或 v4 read access token 都收），沒設就變成「憑證缺失」那個畫面 |
| `tmdb-down` | 憑證有、TMDB 連不上：探索頁的每個 feed 各自顯示服務回的原文與「重試」，而不是一片空白 |
| `search` | Media 詳情頁的搜尋結果表：TMDB 與**索引站都打真的**。索引站位址從 `BERTH_INDEXER_URL` / `BERTH_INDEXER_KEY` 讀，沒設就退回替身（結果表是空的，那本身也是要驗的畫面）。一次搜尋 35–85 秒 |
| `submit` | 送單與下載列表 `/jobs`：TMDB 打真的，索引站給三筆磁力連結的替身結果（形狀取自真的那一輪）。送單、解析、Job 與時間線走的都是產品自己的程式碼，只有 qBittorrent 是替身 |
| `submit-failing` | 同上，但 qBittorrent 收不下：送單失敗那一列、服務回的原文，以及「重新送單」 |
| `import` | 送單到入庫整條走完、**一個請求都不出網**（M2 票 15 的前端 e2e 用它）：同 `plan` 那一包對得上的批次，但 TMDB 是替身（與 `issues` 同一部 SPY×FAMILY，`/media/tv:120089`）。送到 Anime 之後幾秒就是「已入庫」，詳情頁的「檔案與版本」列出五個檔案 |
| `global-path` | 同 `import`，但使用者在套件內 qBittorrent 把全域預設儲存路徑改成 `/data/my-downloads`（Berth 的容器裡沒有這個目錄，審計 S5）：健康頁三條 Route 照樣綠、送單照常——Berth 不寫也不看全域偏好（M4 票 32） |
| `plan` | 下載完成 → **Import Plan**（票 11）：索引站給兩包替身結果——一包對得上的批次（自動入庫）與一包對不到任何一集的 OST（停在待審核）。qBittorrent 是替身，但它會把那幾個檔案**真的寫進 save path** 並報成 100%，所以 poller 走完狀態機、planner 算出真的 Plan：解析、命名、mediainfo、TMDB 快照全是產品自己的程式碼 |
| `inventory` | Media 詳情的「檔案與版本」與送單到入庫的媒體庫（票 13）：同 `plan` 的兩包，加上一台會「掃到」入庫檔案的替身 Jellyfin。送單之後那一部先在媒體庫頁的「還沒進 Jellyfin」那一條，約 30 秒後 resolver 反查、替身「掃到」它，它就換到牆上；OST 那一包是「待審」篩選要找到的那一格。深連結指向瀏覽器主機名的 8096，那台 Jellyfin 不存在——Jellyfin 那一端要用真的一套驗 |
| `late-scan` | 作品頁的 Jellyfin 狀態與媒體庫頁一致（M4 票 51）：同 `import`，但替身 Jellyfin 第一次被通知滿 170 秒才「掃到」入庫的檔案——resolver 前兩次（30 秒、2 分 30 秒）都沒找到，下一次排在 10 分鐘後，正是審計 S6 的時間線。送到 Anime、等約 3 分鐘再打開 `/media/tv:120089`：「檔案與版本」先問一次就是「Jellyfin 已收錄」，不必等那 10 分鐘 |
| `reinstall-before` | 重裝之前（M4 票 60）：同 `import`，替身 Jellyfin 被通知就「掃到」。**與 `reinstall` 用同一個 `--config-root`**：在這裡送單入庫一部，停掉 server、把 `berth.db*` 搬走 |
| `reinstall` | 重裝之後重跑精靈（M4 票 60，審計 S4）：精靈從頁 1 開始，三個服務是上一次的樣子——Jellyfin 已初始化（頁 1 用 `skipper` / `harbour` 登入）、三個媒體庫還在、替身列出媒體庫目錄裡真的有的檔案，qBittorrent 掛著 complete 底下還在的那一包（一件無主 torrent），Prowlarr 有站；TMDB key 要重貼（替身收任何 key）。完成頁與 `/issues` 上有「從媒體庫重建帳本」，作品頁 `/media/tv:120089` 在重建之前說「Jellyfin 有這部，Berth 的紀錄裡沒有」 |
| `long-lists` | 長清單的收合（M1.5 票 09）：同 `inventory`，但索引站只給 benchmark 語料裡葬送的芙莉蓮 `[7³ACG]` BD 合集（39 個檔案：S01 28 集、S00 11 集）。在芙莉蓮的詳情頁（`/media/tv:209867`）送到 Anime，計劃、入庫與替身 Jellyfin 的反查約一分鐘走完，之後看「檔案與版本」與 `/jobs` 那一列的計劃；名偵探柯南（`/media/tv:30983`，TMDB 併成一季 1216 集）不必送單，打開就是那張季表。需要 `TMDB_API_KEY`。**Windows 上加 `--config-root` 指一個短路徑**（例如 `C:/Users/<你>/t9`）：預設的暫存目錄太深，S00 那 11 個檔案的目標路徑會超過 260 字元而入庫失敗 |
| `library` | 媒體庫頁 `/library` 的整庫瀏覽與權限（M1.5 票 03）：Movies / TV / Anime 三個媒體庫擺好作品（Movies 有 131 部，翻得到第二頁；有一部沒有 TMDB id），海報經 Berth 代理替身 Jellyfin 的 SVG（票 04；`Home Videos 2019` 沒有圖、`Harbour Film 007` 有 tag 但圖不見了，兩格都是「無海報」），Berth 經手的有在牆上的、還沒進 Jellyfin 的、待審與 Unmatched（M2 票 14：`skipper` 在 TV 媒體庫的「待審」是 Slow Horses 一份等審核的計劃，「對不到」是 The Bear 兩個 Extras 檔案，就地按得了；Anime 上是 Frieren 的計劃）。作品有類型與社群評分（票 06：排序、類型與年份篩選看得出差別；Shōgun 的 `War & Politics` 帶 `&`），Home Videos 2019 兩者都沒有。每部劇六集；`deckhand` 看到 The Bear 第三集、第四集看到 18%，看完 Breaking Bad，Slow Horses、Shōgun、Game of Thrones、The Office 各看了幾集，Oppenheimer 看到 42%、Harbour Film 002 看到 65%、看過 Harbour Film 001，`skipper` 看完 Slow Horses、The Bear 看過一集（票 05，標為已看 / 未看寫進替身 Jellyfin，重開伺服器就還原）。所以 `deckhand` 的媒體庫頁上方有繼續觀看與下一集（票 07：劇有 16:9 的 Thumb 或 Backdrop，Harbour Film 002 沒有橫圖是「無圖」；登入後就落在媒體庫——看得到的媒體庫裡有 Berth 入庫的東西時；一筆都沒有時落在探索，M4 票 10——探索頁只放 TMDB 牆，M3 票 06），`bosun` / `knot`（權限同 `deckhand`、什麼都沒看過）兩列都不出現。`skipper` / `harbour` 看得到三個媒體庫；`deckhand` / `rope` 只開放 Movies 與 TV，開 `/library/item-anime` 是「找不到或沒有權限」。`curl -X POST 'http://127.0.0.1:8484/demo/jellyfin/disable?user=deckhand'` 在替身 Jellyfin 停用他（`enable` 復原），至多 60 秒後他的下一個請求被送回登入頁。Media 詳情的觀看區（票 08）：`deckhand` 開 The Bear 是「繼續看 S01E04」、集有劇照；The Office 有兩季與 Specials，主按鈕是「看下一集 S01E05」；Breaking Bad 看完了；Oppenheimer 是電影；SPY×FAMILY 在他看不到的 Anime，頁面上沒有觀看區（`skipper` 開同一頁就有）；`bosun` 開 The Bear 是「從 S01E01 開始看」。有 `TMDB_API_KEY` 時詳情頁打真的 TMDB |
| `poll` | 送單到完成的狀態**自己走完**（票 10）：qBittorrent 打**真的**那一台，所以 `sync/maindata` 會真的換 state、poller 會真的驅動 §3.1 的轉換、SSE 會真的把那一列推著動。位址從 `BERTH_QBITTORRENT_URL` 讀，準備步驟見下方 |

`healthy` 沒有 TMDB 憑證，所以它同時是探索頁「還沒填憑證」的樣子——那一步是精靈的必填閘門
（見 [README〈What you need〉](../README.md#what-you-need)），畫面要指得出下一步。

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

Fake 是**有狀態**的，每個情境只有一份，所以頁 1 與頁 3 真的會把那台假 Jellyfin 一步一步改掉，
重按也真的會標成「已經是這樣」。

每次啟動都用一個新的暫存 `CONFIG_ROOT`，所以永遠是乾淨環境；`--config-root` 可指定成固定目錄
以便跨次保留進度。精靈頁 3（媒體庫路徑）會**真的**建目錄、寫探測檔並呼叫 `link()`，所以三層
路徑（`settings.paths`）由這支腳本指到該次的暫存 `DATA_ROOT` 底下，不會碰到容器裡的 `/data`。

`healthy` / `degraded` / `global-path` 這幾個情境在啟動時就真的跑過一輪 `build_routes` 與健康檢查，
所以畫面上的 inode、可用空間與版本號都是那一輪量到的值，不是寫死的假資料。

### 實驗腳本

`scripts/experiments/` 是對真實外部服務做的驗證（Jellyfin 命名、qBittorrent 版本差異、
Prowlarr 設定 API、硬鏈接），全部可重跑。每個腳本在回答什麼、有哪些坑，見
[`scripts/experiments/README.md`](../scripts/experiments/README.md)；結果寫在
[`docs/research/m0-experiments.md`](research/m0-experiments.md)。

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
[`docs/research/library-browsing.md`](research/library-browsing.md) §2、§3.1、§5、§10、§11：

```bash
python scripts/experiments/jellyfin_permissions.py            # 只量，報告寫到 .local/experiments/results/
python scripts/experiments/jellyfin_permissions.py --record   # 另外重錄 tests/fixtures/http/jellyfin/ 的權限 fixture
python scripts/experiments/jellyfin_permissions.py --record --only items.tv.series.page.json   # 只加錄這幾個，其餘不動
```

Jellyfin 的圖經 Berth 代理要不要另存一份（M1.5 票 04）：同樣自己起停一次性 Jellyfin，另外起一個 `berth serve`
量經過代理的延遲，所以要用 `uv run`。結果見 [`docs/research/library-browsing.md`](research/library-browsing.md) §6.1：

```bash
uv run python scripts/experiments/jellyfin_images.py   # 報告寫到 .local/experiments/results/jellyfin-images.json
```

RSS Series 自動綁定的規則門檻（M3 票 09）：對票 07 錄下的 Mikan 聚合 feed，真的抓 Mikan 單集頁與番組頁、真的打
TMDB，走 Berth 自己的判定、只印不綁。憑證讀環境變數，資料庫是暫時目錄裡的新的一份。結果見
[`docs/research/rss-sources.md`](research/rss-sources.md) §2.8：

```bash
uv run --env-file .env python scripts/experiments/rss_auto_bind.py   # 要 .env 裡的 TMDB_API_KEY；會連 Mikan 與 TMDB
uv run --env-file .env python scripts/experiments/air_date_lag.py    # 同上；Windows 主控台加 PYTHONIOENCODING=utf-8
```

第一批「證據夠強」的規則（M4 票 11）：語料那一段離線；`--online` 另跑 split-cour 模擬與上面那一套真的 RSS fixture
（重用 `air_date_lag.py` 認作品的那一段，所以要同一把憑證）。結果記在 `.scratch/m4/issues/11-first-batch-skip-when-sure.md`：

```bash
uv run python scripts/experiments/first_batch_rule.py                                  # 只跑語料，不連網
uv run --env-file .env python scripts/experiments/first_batch_rule.py --online          # Windows 主控台加 PYTHONIOENCODING=utf-8
```

前端 e2e `rss-subscribe` 的第一輪預覽為什麼慢（M4 票 13b）：起一台 `rss` 情境的演練 server，打那條 spec 同一串 API、
逐步計時；不連網。結果記在 `.scratch/m4/issues/13b-rss-subscribe-e2e-preview.md`：

```bash
uv run python scripts/experiments/rss_subscribe_timing.py                 # 訂閱 Mikan 之後馬上建 acg.rip 搜尋 feed
uv run python scripts/experiments/rss_subscribe_timing.py --settle 30     # 先等補舊集跑完 30 秒再建
uv run python scripts/experiments/rss_subscribe_timing.py --profile       # 同一個行程起 server，cProfile 包住預覽
```

1,000 部的媒體庫上量 Berth（M2 票 11，plan §11.3 決定 2 的門檻）：自己 build Berth 的 image（只有 backend 那一層）、
起一次性的 Jellyfin 與 qBittorrent、造 1,000 部 × 12 集的媒體樹（掃描約 6 分鐘），量完連容器、volume、network、image
一起刪。宿主只要 Python 標準庫與 docker；量測本身在 Berth 的 image 裡跑。結果見
[`docs/research/large-library.md`](research/large-library.md)：

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

qBittorrent 看不看得到 Berth 寫進分類路徑的檔：探針 torrent 在 4.4.5 與 5.2.3 上怎麼校驗（M4 票 19，brief §20.2）：
自己起停一次性的 qBittorrent（前綴 `berth-exp-visibility`，只發佈在 `127.0.0.1:18095`），一個版本不到一分鐘：

```bash
python scripts/experiments/qbittorrent_visibility_probe.py     # 5.2.3；報告寫到 .local/experiments/results/qbittorrent-visibility-<版本>.json
python scripts/experiments/qbittorrent_visibility_probe.py --image lscr.io/linuxserver/qbittorrent:4.4.5   # 支援下限
```

精靈頁 2 的探針「看得到但校驗不完」：看得到的那一台停在 50%、不觸發「完成時執行外部程式」（M4 票 46，brief §20.2）。
用的是 Berth 自己的 `probe_torrent(unfinished=True)`，沿用上一支的容器名，只發佈在 `127.0.0.1:18096`：

```bash
uv run python scripts/experiments/qbittorrent_unfinished_probe.py     # 5.2.3；報告寫到 .local/experiments/results/qbittorrent-unfinished-probe-<版本>.json
uv run python scripts/experiments/qbittorrent_unfinished_probe.py --image lscr.io/linuxserver/qbittorrent:4.4.5
```

分類自己的未完成目錄（`createCategory` 的 `downloadPath`）下載中是不是落在那裡、完成後搬到 save path，全域
temp path 開關時誰贏（M4 票 22，brief §20.2）：自己起停一台做種的 5.2.3 與一台受測版本（前綴
`berth-exp-catpath`，只發佈在 `127.0.0.1:18093`、`18094`），一個版本約兩分鐘：

```bash
python scripts/experiments/qbittorrent_category_download_path.py     # 5.2.3；報告寫到 .local/experiments/results/qbittorrent-category-download-path-<版本>.json
python scripts/experiments/qbittorrent_category_download_path.py --image lscr.io/linuxserver/qbittorrent:4.4.5   # 支援下限
```

套件容器撞名、撞 port 時 `docker compose up -d` 怎麼收場，以及 `berth` 的 `host.docker.internal` 解到哪
（M4 票 16，brief §20.14）：以 `deploy/docker-compose.yml` 改出一套隔離的 compose project（`berth-exp-collide`、
子網 `172.26.0.0/16`、容器名前綴 `bexp-`、port 4xxxx），不碰這台機器上正在跑的部署；`berth` 用本地已有的 image，
不 build。約 2 分鐘，結束時全部清掉並印出殘留。換 Docker 或 Compose 版本之後重量：

```bash
python scripts/experiments/compose_collisions.py --berth-image berth:e2e   # 報告寫到 .local/experiments/results/compose-collisions.json
```

選了既有之後，哪一個指令停得掉已經在跑的套件內容器（M4 票 36，brief §20.14）：同樣改出一套隔離的 compose project
（`berth-exp-profiles`、子網 `10.232.0.0/16`、容器名前綴 `bexp-`、port 4xxxx），image 都用本地已有的、不 pull，
依序量拿掉 profile 再 `up -d`、加 `--remove-orphans`、`stop`、再 `up -d`、不帶 profile 的 `down`。約 1 分鐘，結束時全部清掉：

```bash
python scripts/experiments/compose_profile_removal.py --berth-image berth:e2e   # 報告寫到 .local/experiments/results/compose-profile-removal.json
```

qBittorrent 的 preseed 腳本內嵌進 compose（頂層 `configs` 的 `content`，加 `mode: 0555`）之後 linuxserver 的 init
認不認、白名單對不對、重啟與重建冪不冪等、qbittorrent 的 profile 關掉時 `up -d` 會不會報錯，另跑不寫 `mode` 的
對照組（M4 票 70，brief §20.18）。內嵌的腳本是當下的
`deploy/preseed/qbittorrent/10-berth.sh`；compose project 與 network 叫 `berth-t70`、容器 `berth-t70-qbittorrent` 與 `berth-t70-idle`（子網
`10.70.0.0/16`，WebUI port 7080），用本地已有的 `qbittorrent:latest`、不 pull。三個變體約 3 分鐘，結束時 `down` 並刪掉工作目錄。
換 Compose、Docker 或 linuxserver 版本之後重量；別的 Compose 版本用官方的獨立二進位，不換掉系統的：

```bash
python scripts/experiments/inline_preseed.py --label desktop     # 報告寫到 .local/experiments/results/inline-preseed-<label>.json
python scripts/experiments/inline_preseed.py --label compose-2.40.3 --compose-bin <docker-compose 執行檔>
python scripts/experiments/inline_preseed.py --label debug --variant mode --keep   # --keep 只能配一個變體：留著容器與目錄
```

搬到 Linux 宿主上跑時保留相對位置（只用標準庫，宿主要有 `python3`）：

```bash
tar cf - scripts/experiments/inline_preseed.py scripts/experiments/lib.py deploy/preseed/qbittorrent/10-berth.sh \
  | ssh <host> 'mkdir -p ~/berth-t70 && tar xf - -C ~/berth-t70'
ssh <host> 'cd ~/berth-t70 && python3 scripts/experiments/inline_preseed.py --label vm-rootless'
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

rootless Docker 上容器的 uid 落到宿主是誰、`berth` 容器連得到宿主上的哪些位址（M4 票 42）：在宿主上、Berth 那一套
`up -d` 之後跑，第一個參數是宿主的區網 IP，其餘是要多打的 port（既有服務）；只讀，自己起的兩個暫時 http 服務會收掉：

```bash
sh scripts/experiments/rootless_host_probe.sh 192.168.50.99 18096 18080
```

入庫的那一部片 Jellyfin 認不認得、播不播得到（M4 票 55，Unraid 上 mover 前後各問一次）：在已經跑完精靈的
`berth` 容器裡跑，用 Berth 存的 Jellyfin API key（不印出），只讀。item id 在作品頁「在 Jellyfin 看」的連結裡：

```bash
ssh root@tower 'docker exec -i berth python - <jellyfin item id>' < scripts/experiments/jellyfin_stream_probe.py
```

收工：

```bash
docker compose -f scripts/experiments/compose.yml down -v
```

Windows 的 Git Bash 要在 `docker run` 前加 `MSYS_NO_PATHCONV=1`，否則 `/data` 這種容器內路徑
會被改寫成 `C:\Program Files\Git\data`。

動漫季集來源的量測（不需要任何容器，只打外部 API）。除了 `--self-test` 以外都要一把 TMDB 憑證，
從環境變數 `TMDB_API_KEY` 讀（v3 key 或 v4 token 都可以，取得步驟見 [README〈What you need〉](../README.md#what-you-need)）：

```bash
export TMDB_API_KEY=...                                              # Windows PowerShell 是 $env:TMDB_API_KEY
python scripts/experiments/anime_episode_source.py --self-test       # 換算器的手算樣例
python scripts/experiments/anime_episode_source.py                   # 完整量測（門檻 180 天，同 plan §4.4）
python scripts/experiments/anime_episode_source.py --gap-days 60     # 虛擬季門檻的敏感度比較
python scripts/experiments/anime_episode_source.py --discover        # 重新找 Mikan 的番組 id
```

第一次跑要抓好幾百個頁面（Mikan 的頁很大且常斷線），大約十來分鐘；抓過的東西會快取在
`.local/experiments/cache/`，之後重跑分析是秒級。結果見
[`docs/research/anime-episode-source.md`](research/anime-episode-source.md)。

「集號 ≤ 第一季集數就送審核」這條規則的代價（M1 票 14d）。拿上面 `anime_episode_source.py` 的快取當正解、
丟進 Berth 的解析器，所以要憑證也要 `uv run`（快取被清掉的話會先重抓，約十分鐘）：

```bash
uv run --env-file .env python scripts/experiments/absolute_rule_cost.py    # A / B、收窄規則 R 的放行與漏掉
```

結果見 [`docs/research/profile-effect.md`](research/profile-effect.md) §6.1.1。

片長驗證的門檻（M3 票 15，比對 mediainfo 量出的片長與 TMDB 該集 `runtime`）：真的 mediainfo 時長對
AnimeTosho 的公開端點查，不需要任何憑證、不連 TMDB（讀本地 `tests/fixtures/tmdb/`）、不下載任何
影片內容。第一次跑要抓不少 AnimeTosho 的頁面，會自動節流；抓過的東西快取在
`.local/experiments/cache/runtime_gap/`，之後重跑是秒級：

```bash
python scripts/experiments/runtime_gap.py                  # Windows 主控台加 PYTHONUTF8=1 PYTHONIOENCODING=utf-8
```

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
  fixtures/e2e/     e2e 用的兩支 330 秒種子影片與冒充 RSS 站的測試 CA
  fixtures/http/    對真服務錄下來的回應，adapter 契約測試的輸入
  fixtures/mediainfo/  ffmpeg 造的一份真 Matroska（2 秒、17 KB），mediainfo adapter 的輸入
  fixtures/parser/  解析基準測試的語料（真實 torrent 的檔案清單）
  fixtures/tmdb/    語料用到的 TMDB 快照，錄一次即凍結
docs/             設計綱要、實作計劃、進度、本檔
  guide/          給使用者的英文 guide（README 連過去的那幾份）
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
