# 開發指令：後端、前端與 API 型別

日常開發指令：後端、帳本重建、解析基準測試、前端、API 型別。安裝、啟動、環境變數與〈全部檢查〉在[主檔](../development.md)。

### 後端

```bash
uv run berth --version      # CLI
uv run berth serve          # 啟動程序（--reload 為開發模式）
uv run berth openapi        # 印出 OpenAPI 文件（--output 寫檔）；前端型別的上游
uv run berth bench          # 解析基準測試（見下）；離線跑，離開碼是 CI 的門檻
uv run berth rebuild-ledger # 從媒體庫的 inode 把帳本長回來（見下）
uv run pytest -n auto       # 測試，一個 CPU 一個 worker（pytest-xdist）；單檔或 -k 不必加
uv run ruff check .         # lint
uv run ruff format .        # 格式化（CI 用 --check）
uv run mypy                 # 型別檢查（strict）
uv run lint-imports         # 依賴方向契約（plan §1.3）
```

測試裡的「現在」：services 的命令多半收 `now=`，直接傳；走 HTTP 那一層傳不進去的，用 time-machine 的
`time_machine` fixture 把時鐘固定在錄下來的資料的日期附近（`time_machine.move_to(...)`，例見
`tests/integration/test_rss_api.py::TestThePageFlow`）。錄下來的日期是寫死的，拿牆上時間跟它比的
斷言總有一天會翻面（M5 票 01）。演練伺服器同理：用錄下的資料的情境設 `Scenario.clock`（見
〈UI 的 Fake 後端〉的 `rss`）。

資料庫 migration（Alembic）。程序啟動時會自動套用到最新版本，以下只在改 schema 時用：

```bash
uv run --env-file .env alembic current                          # 目前版本
uv run --env-file .env alembic revision --autogenerate -m "…"   # 依 models/ 產生新版本
uv run --env-file .env alembic upgrade head                     # 手動套用
```

改完 `berth/models/` 一定要產生 migration：schema 不是從 models 直接建的。

### 帳本重建（`berth rebuild-ledger`）

使用者那一面（什麼時候用、畫面上的按鈕）在 [`guide/backup-and-reinstall.md`](../guide/backup-and-reinstall.md)；這裡是指令與判定的細節。

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
[`tests/fixtures/parser/README.md`](../../tests/fixtures/parser/README.md)。

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
pnpm -C web e2e             # playwright 對演練情境跑二十條流程（先 build，見〈前端 e2e〉）
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
