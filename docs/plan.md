# Berth 實作計劃

> 依據 `docs/design-brief.md`（以下簡稱 brief）。brief 說「做什麼、為什麼」，本文件說「怎麼做、誰先誰後」。兩者衝突以 brief 為準；本文件若改動 brief 的決定，必須同輪回寫 brief。
>
> 閱讀方式：§1–§8 是架構，開工前讀完；§9 開箱即用；§10 測試；§11 里程碑任務，M0 與 M1 拆到可直接開工的粒度，M2–M4 只列範圍與驗收；§12 風險與回寫點。
>
> 標記沿用 brief：【決定】【建議】【研究】。

---

## 0. 工程慣例

- 語言：程式碼、識別符、commit、log 一律英文；文件與註解繁體中文。例外是給使用者的 README 與 `docs/guide/`：README 英文為主、`README.zh-Hant.md` 是同內容的繁中版，guide 英文（brief §19 第四輪審計 E7、M4 票 57）。
- Commit：Conventional Commits，subject ≤ 72 字元。分支 `feat/…`、`fix/…`、`docs/…`。
- 每個里程碑結束時 `main` 可部署、CI 綠燈、README 可照著跑。
- 改動指令、環境變數、目錄結構、對外介面或資料格式時，同輪更新 README（兩份）與 `docs/guide/`（使用者）、`docs/development.md`（開發指令）、`.env.example`、CHANGELOG、專案 `CLAUDE.md`。
- 型別：後端 mypy strict（第三方缺型別時局部放寬並註明）；前端 TypeScript strict。
- 行為變更同步補測試；解析器改動必跑 benchmark（§4.6）。

---

## 1. 架構總覽

### 1.1 執行形態【決定】

- **一個容器、一個 Python 程序**：FastAPI 提供 HTTP API 與靜態前端；背景迴圈（§3.2）以 asyncio task 在同一程序內跑，於 lifespan 啟動與關閉。
- **SQLite**（WAL 模式），檔案 `/config/berth.db`；Alembic migration 在啟動時自動套用。
- **前端 React SPA**，build 產物由 FastAPI 以靜態檔案提供；開發時 Vite dev server 代理 `/api`。回應一律 gzip（Starlette `GZipMiddleware`，M3 票 06：前端一整包 760 KB 傳輸降到約 216 KB，前面不一定有代理替它壓）；SSE 與已壓縮的圖不壓（Starlette 的預設排除，`test_events_api.py` 守著 SSE 那一條）。路由拆分量過（入口 760 → 458 KB）但沒做，理由在 M3 票 06 的 Comments。
- 對外只有一個 port，預設 `8383`。
- 路徑常數：`CONFIG_ROOT`（預設 `/config`：DB、設定、log）、`DATA_ROOT`（預設 `/data`：媒體根，brief §4）、`PORT`（預設 `8383`），全部可用環境變數覆寫以便本機開發。
- 前端產物的位置是第四個變數 `WEB_ROOT`，預設 repo 佈局的 `<repo>/web/dist`；裝成 wheel 之後那個路徑不存在，所以 image 的 Dockerfile（§9.1）指到它自己的複製位置。找不到時只提供 API。

理由：單使用者到單家庭的規模，一個程序足夠；Seerr 與 AutoBangumi 都是這種形態。之後若解析或對帳變重，先把背景迴圈拆成第二個程序，不改架構。

### 1.2 後端套件結構

```
berth/
  main.py              FastAPI app 組裝；lifespan 啟動 migration 與背景迴圈
  config.py            環境變數、路徑常數、版本號
  db/                  engine、session factory
  migrations/          Alembic 環境（`env.py`）與 versions
  models/              SQLAlchemy ORM（§2 的表）
  domain/              純資料型別與狀態機，無 IO：JobState、ReleaseInfo、Tags、Candidate、PlanItem、Confidence
  parser/              純函式：classify、cjk、release、structure、mapper、subtitles、planner、confidence
  naming/              純函式：title 選擇、sanitize、tag 渲染、路徑模板
  adapters/            外部服務：qbittorrent、jellyfin、tmdb、prowlarr、rss/{mikan,nyaa,acgrip,generic}、fs、mediainfo
  services/            命令（use case）：setup、routes、discover、search、download、plan、import_、review、rematch、delete、rss、reconcile、health
  pipeline/            背景迴圈：qbit_poller、planner_runner、importer、jellyfin_resolver、reconciler、rss_poller、health_checker
  api/                 FastAPI routers：auth、setup、settings、routes、discover、media、search、jobs、plans、review、files、rss、issues、health、events
  events.py            Event 寫入與 SSE 廣播
  cli.py               `berth bench`、`berth reconcile`、`berth rebuild-ledger`
web/                   前端（§7）
tests/
  fixtures/parser/     benchmark 語料（§4.6）
  fixtures/tmdb/       TMDB 快照
  fixtures/http/       adapter 的錄製回應
  unit/ integration/ e2e/
deploy/
  docker-compose.yml   開箱即用套件（§9）；qBittorrent 的預置腳本內嵌在它的 `configs`（§9.2）
  .env.example
scripts/experiments/   brief §20.6 的實驗腳本
```

### 1.3 依賴規則【決定】

```
api ──► services ──► domain / parser / naming / adapters / models
pipeline ──► services
parser ──► naming ──► domain         （純函式；TMDB 資料以快照物件傳入，不呼叫網路）
adapters ──► domain                  （不 import services、models；回傳 domain 型別或簡單 dataclass）
```

- 所有會改變狀態的操作都是 `services` 內的命令函式，名稱即 brief §14 的命令名（`add_download`、`generate_plan`、`apply_plan`、`rematch_file`、`delete_job`…）。API 與 pipeline 只呼叫 services，兩者都不直接碰 adapters 或 models。
- **`naming` 在 `parser` 之下**（M1 票 07）：`plan` 階段要產出目標路徑（§4.1），而衝突偵測比的就是那條路徑——兩個檔案指到同一個檔名時誰都不能自動入庫。反向不成立，`naming` 只認 `domain` 的快照與 `Tags`，`import-linter` 另有一條契約守著。
- `db`（engine、session factory）在 `models` 之下、`domain` 之上；`api`、`pipeline`、`parser`、`naming`、`adapters` 都不得 import 它。Alembic 的 `env.py` 需要 `models` 的 metadata，因此放在 `migrations/`（不納入層級契約）。
- 用 `import-linter` 在 CI 強制上述方向，契約寫在 `pyproject.toml` 的 `[tool.importlinter]`。
- 每個 adapter 有一個 `Protocol` 介面與一個 `Fake` 實作（放在 `adapters/<name>/fake.py`），整合測試與 e2e 用 Fake 取代真服務。

### 1.4 主要依賴【決定】

| 層 | 選擇 | 理由 |
| --- | --- | --- |
| Web | FastAPI、uvicorn、pydantic v2 | 型別即 schema，自動產 OpenAPI，未來 MCP 直接吃 |
| DB | SQLAlchemy 2（async）+ aiosqlite、Alembic | 單檔、零維運；migration 從第一天就有 |
| HTTP client | httpx（async） | 統一逾時與重試 |
| 解析 | guessit、自維護 CJK 規則 | brief §20.4 |
| mediainfo | pymediainfo | manylinux wheel 內含 libmediainfo，不需系統套件 |
| RSS | feedparser | 成熟、容忍壞 XML |
| 排程 | 自寫 asyncio 迴圈 | 需求只是固定間隔與退避，不值得引入 APScheduler |
| 執行環境 | Python 3.13（`.python-version`）、Node 24 | 計劃內的依賴都有 cp313 wheel；`python:3.13-slim` 供 §9.1 的 image 使用 |
| CLI | argparse（stdlib） | 只有數個子指令與旗標，不值得引入 typer / click |
| 套件管理與工具 | uv、ruff、mypy、pytest、pytest-asyncio、respx、import-linter | — |
| 前端 | React 19、TypeScript、Vite、TanStack Query、TanStack Router、Tailwind v4、react-i18next | 通用、可長期維護。**不引入 shadcn/ui**（M0 票 05 起，2026-09-22 結案）：三個里程碑下來沒有一個元件需要 Radix 的行為原語，原生 `input` / `button` / `details` 的無障礙比重寫的好；要 dropdown / dialog 時再議 |
| 前端工具 | pnpm、eslint、prettier、vitest | 沒有腳本化的 playwright e2e，見 §10 |

---

## 2. 資料模型

表名與欄位。型別以 SQLite 慣例（TEXT / INTEGER / REAL / JSON 以 TEXT 存），時間一律 UTC ISO 8601。`*_json` 欄位對應一個 pydantic model，序列化集中在 `models/`。

### 2.1 使用者與設定

- `users`：`id`、`jellyfin_user_id`（unique）、`name`、`role`（`admin` / `user`）、`created_at`、`last_login_at`
- `sessions`：`id`、`user_id`、`token_hash`、`expires_at`、`created_at`。token 是 256 bit 亂數，只存 SHA-256 雜湊；壽命 30 天且**不滑動續期**，過期的列在下一次被用到時就地刪掉。
- `settings`：`key`（unique）、`value_json`、`updated_at`。key 分組：`services.jellyfin`、`services.qbittorrent`、`services.indexer`、`services.tmdb`、`paths`、`parser`、`ai`、`rss`、`setup`、`health`。每組一個 pydantic model；`services.*` 只含**連線資訊**。
  - `health`：`health_checker` 上一輪的結果——逐服務的 `status` / `detail` / `error` / `checked_at` / `last_ok_at` / `failures` / `configured` / `banned` / `unsupported` / `library_count`，加上這一輪的時間。Route 的總結**不存**，讀的時候從 `routes` 表算（`routes_health`，M4 票 59：換一台 qBittorrent 之後存著的那一份還說「已繫上」）。完成精靈時頁上測過的結論抄進來（M4 票 59）。**與 `services.*` 分開存**：那幾組是整組覆寫的使用者設定，把迴圈每 5 分鐘寫一次的狀態混進去，兩邊會互相蓋掉（票 10 改，原文是「`services.*` 含連線資訊與最後健康狀態」）。
  - `services.jellyfin` 另含 `public_url`（選填的對外網址，媒體庫深連結的主機；空的時候由 `services/deeplink.py` 推導——既有服務用 `base_url`、套件內用瀏覽器的主機名加 `base_url` 的 port，Seerr 的 `externalHostname` 慣例，票 13）、`api_key`、`metadata_fetchers`（鍵是套件內媒體庫的資料夾名，沒寫的依內容類型落回預設，票 06f；值寫進 `LibraryOptions.TypeOptions[].MetadataFetchers`；brief §10 的 TVDB【研究】定案時改這裡而不是改程式）。**沒有 MergeVersions 的任務 id**：票 14b 起只支援 Jellyfin 12，而 12.x 原生合併多版本（brief §19、§20.9）。舊資料庫裡那兩個鍵還在，`extra="ignore"` 讓它照樣讀得回來，所以沒有 migration。
  - `rss`（M3 票 10）：排除條件的全域那一層——`exclude_not_single`（預設 `true`：不是單集的不自動下載）與 `exclude`（規則清單，格式同 `rss_feeds.exclude_json`）。
  - `paths` 另含 `library_root`（套件內媒體庫的資料夾與既有媒體庫「加入 Berth 路徑」的父目錄，預設 `/data/library`）。
  - `setup.jellyfin`：Jellyfin 的七步（頁 1 的擁有者那一半與頁 3 的媒體庫）各自的 `key` / `status` / `detail` / `error`，以及 Jellyfin 回報的媒體庫與各自路徑。每一步在做**之前**就寫入 `running` 並 commit，前端才輪詢得到進度。版本號不另外存：它是 `public_info` 那一步的 `detail`（失敗的那一輪也帶著，版本閘門就是靠它顯示）。
  - `setup.choices`（M4 票 15）：鍵是 `ServiceKind`，值是 `ServiceChoice`——使用者選的 `origin`（`bundled` / `existing`）、Berth 連的 `base_url`（套件內是 compose 主機名），與最後一次測試 `test`（`state`：`ok` / `failed` / `waiting` / `timeout`；`reason` 是 `ConnectionReason`；`detail` 是版本或站數；`waiting_since` 是套件內那一台還在啟動時這一輪 2 分鐘的起點）。沒有那一列就是還沒選，寫入那個服務的命令一律拒絕。取代原本的 `setup.services`（偵測判定）與 `probe_started_at`，migration `f3c9a1d6b2e8` 把有結論的判定轉成同一個來源的選擇、其餘丟掉。
  - `setup.qbittorrent.web_ui_username` / `web_ui_password_hash`、`setup.indexer.web_ui_username` / `web_ui_password_hash`（M4 票 15）：Berth 寫進套件內那兩台的介面登入，**只記帳號與加鹽 scrypt 雜湊**（`services.steps.hash_password`），夠比對「已經是這一組」；帳號在、雜湊空的是那一台自己就設過的。套件內 qBittorrent 的 `services.qbittorrent` 帳密是空的：Berth 連它靠免密白名單；既有那一台的帳密是 Berth 的連線憑證，照舊存（brief §16.2）。

### 2.2 Route 與 Media

- `routes`：`id`、`slug`（unique）、`name`、`jellyfin_library_id`、`jellyfin_library_name`、`collection_type`（`movies` / `tvshows`）、`target_path`、`category`、`medium_auto_import`（預設 true）、`enabled`、`health_status`、`health_detail_json`、`created_at`。`health_detail_json` 是 `RouteHealth`：逐項檢查（形狀同精靈的步驟：`key` 是 `RouteCheck`、`status`、`detail`、`error`）與 `cross_device`。category 的 save path 不存欄位，它一律是 `<complete root>/<slug>`（brief §4.1）。**slug 與 `target_path` 建立之後不可改**：category 與 complete 子目錄由 slug 導出，帳本以目標路徑認 Route（`owning_route`）；要換目標就新增一條、刪掉舊的（票 14）。`enabled` 是設定頁的啟用：新建或從停用到啟用都要每一條纜繩那一輪全綠；停用的 Route 不收新的送單，也不算進健康總結與精靈第 7 步的完成條件。被 Job 或帳本引用的 Route 刪不得。
- `media`：`id`（`tv:<tmdb>` / `movie:<tmdb>`）、`tmdb_id`、`kind`、`title_en`、`title_original`、`year`、`folder_name`、`folder_frozen`、`default_route_id`、`tmdb_snapshot_json`（含**各季的 `name`**——`Hashira Training Arc` 這種篇章名是 §4.4 的季號來源——與各季各集：number、name、air_date、runtime；episode groups 的 absolute 排序若存在）、`tmdb_fetched_at`。`tmdb_snapshot_json` 的型別化版本是 `domain/media.py` 的 `MediaSnapshot`（§4.3）——它住在 `domain/` 是因為 `naming` 與 `parser` 都要它，而那兩個依契約只 import `domain`（§1.3）。
  **點進詳情頁就會寫下一列**（快照要有地方放），所以有這一列不代表 Berth 為它做過任何事。「追蹤過」是**推導**出來的（`CONTEXT.md`）：票 09 起是 `EXISTS(jobs)`，票 12 加帳本，M3 加 Rule——不存成欄位。
  `folder_name` 因此**跟著標題走**（畫面上它是「將會是」的預覽），每次刷新快照都重算；**第一次真的通向磁碟那一刻凍結**：手動送單成功時（票 09）或建 RSS Rule 時（M3），兩個都有人在場、都要一次明確確認。凍結之後 refresh 一律不動它（§5、brief §4.5、票 04b）。不拖到入庫才凍——importer 是背景迴圈，那時候沒有人看著。
  開關是 `folder_frozen`（票 09），**推導不出來**：送單失敗的 Job 也是一列 `jobs`，而那一刻磁碟上什麼都沒發生；刪掉那筆 Job 也不該讓資料夾名重新開始跟著 TMDB 跑。**送單那一步不刷新快照**（§8.3 的六小時規則留給 planning）：凍下去的必須就是使用者剛剛在確認畫面上看到的那一串字。
- `tmdb_cache`：`key`（`discover:trending` / `discover:popular` / `search:<正規化查詢>`）、`value_json`（已經合併好的卡片陣列：tmdb id、kind、顯示用標題、英文標題、年份、完整海報網址）、`fetched_at`。探索頁與搜尋結果的短期快取，一小時；Media 詳情走 `media` 表

### 2.3 Job、檔案、計劃、帳本

- `jobs`：`hash`（pk，info hash）、`name`、`source_url`、`trigger`（`manual` / `rss` / `reimport`）、`trigger_ref`（RSS Series 的 id 或 import source 路徑）、`user_id`、`media_id`、`route_id`、`state`（§3.1）、`error`、`save_path`、`content_path`、`total_size`、`progress`、`client_state`、`published_at`、`added_at`、`completed_at`、`imported_at`、`last_seen_in_client_at`。
  `source_url` 是索引站上那一條下載連結，**存著是為了重試**（§3.1 的 `submit_failed` → `requested`）：送單失敗之後畫面上那一輪搜尋早就不在了，而 Prowlarr 的代理連結每次搜尋都不一樣（brief §20.7），重新搜一次不會給出同一條（票 09）。
  `published_at`（M3 票 14）是來源說它什麼時候發佈的：索引站結果的 `publishDate`、或 Feed Item 的發佈時間，送單時存下來，規劃時比播出日（§4.4）。**住在 Job 而不是規劃時回頭讀 `rss_items`**：手動送單沒有 Feed Item，兩條路徑要同一個地方；既有的 RSS Job 由 migration 從 `rss_items` 回填（最早帶到它的那一筆）。認領與重新入庫沒有來源，是 `NULL`。
- `job_files`：`id`、`job_hash`、`rel_path`（與 hash 合併 unique）、`size`、`priority`、`kind`（§4.1）、`mediainfo_json`、`updated_at`。原本還有一欄 `release_info_json`，M1 起就沒人寫，M3 票 01 以 migration 拿掉（使用者 2026-09-24 拍板）：解析結果落在 `plan_items`，RSS 要的那一份在 `rss_items` 自己那一欄
- `plans`：`id`、`job_hash`（nullable、**unique**）、`source_path`（單列 Plan 的那個檔案）、`engine`（`rules` / `ai` / `user`）、`engine_version`、`status`（`preplan` / `auto` / `pending_review` / `approved` / `rejected` / `applied` / `failed`）、`summary_json`（各信心等級數量、原因摘要、`review_reason`）、`rss_series_id` / `season_hint` / `episode_offset`（M3 票 13：算這一份時交給解析器的 RSS Series 與它當時的季號、offset——值是規劃時讀的，同一個 Series 前後兩份計劃可能不同；不是 RSS 送的三格都是 `NULL`，既有的 Plan 不回填；`rss_series_id` 是弱引用）、`created_at`、`decided_by`、`decided_at`。
  **一個 Job 只有一份「現在的計劃」**（票 11）：`job_hash` 上是 unique index，重跑 planning 把它整份改寫而不是再長一列。兩個理由：`GET /api/plans/{id}` 不必先回答「哪一個 id 才是現在那一份」，而 `plan_items` 不會在每次重跑之後多一份重複的決定（§3.3 的重入）。上一份計劃留在時間線上（`events`）。`created_at` 因此是**算出這一份的時間**，跟著重跑換。`job_hash` 仍可為 NULL——rematch 與重複版本的決定各記一份單列 Plan（`engine = user`，以 `source_path` 說是哪個檔案），而 SQLite 的 unique 容得下多個 NULL。重新入庫自 M2 票 10 起有自己的 Job（M3 票 01 更正）。
- `plan_items`：`id`、`plan_id`、`job_file_id`（nullable）、`rel_path`、`action`（`import` / `extra` / `subtitle` / `skip` / `unmatched` / `review`）、`media_id`、`season`、`episode_start`、`episode_end`、`tags_json`、`target_path`、`confidence`（`high` / `medium` / `low`）、`reasons_json`、`audit`（medium 自動入庫為 true；RSS Series 送的另有一條——第一批確認之前 high 也是 true、確認之後 medium 也是 false，M3 票 13）、`applied_at`、`error`
- `ledger`：`id`、`job_hash`（nullable）、`source_rel_path`、`source_abs_path`、`source_inode`、`source_dev`、`target_path`（unique）、`target_inode`、`media_id`、`season`、`episode_start`、`episode_end`、`tags_json`、`plan_item_id`、`action`、`jellyfin_item_id`、`jellyfin_series_id`、`resolve_attempts`、`resolve_after`、`link_mode`（`hardlink`）、`status`（`ok` / `target_missing` / `source_missing` / `inode_mismatch` / `unlinked`）、`audit`、`created_at`、`checked_at`。
  **帳本自己站得住**（票 12）：`job_hash` 是弱引用（刪 Job 與清帳本是刪除範圍裡兩個獨立的旗標）；`action`、季集與 Tags 抄一份進來，因為 review 之後重新規劃會把 `plan_items` 整份換掉，`plan_item_id` 因此是 `SET NULL`。`resolve_attempts` / `resolve_after` 是 `jellyfin_resolver` 的排程（§3.2），要活過重啟所以落在這一列；`None` 代表沒有要反查的事（找到了、用完了，或本來就不是一個 item——字幕與特典）。**inode 與 device 存 TEXT**：Windows 的 `st_dev` 實測 `11550084160259632778`，超過 SQLite INTEGER 的有號上限，而這兩欄只比相等。`target_path` 是容器裡的 POSIX 路徑，也就是 Jellyfin 回報 `Path` 的形狀。
  `jellyfin_series_id`（票 13）是劇集正片那一集所屬的 Series item：媒體庫的深連結開的是作品而不是某一集，而反查時 `/Items` 的 Episode 自己帶 `SeriesId`，所以與 item id 一起寫下，讀頁面時不必再問 Jellyfin。
  `jellyfin_version_name`（票 14b）是同一個道理：Jellyfin 12 起劇集也原生合併多版本，而版本選單上的名字是**它算的**（去掉各版本檔名的共同前綴，12.0 與 12.1 的算法還不一樣）。反查那一刻 `MediaSources[].Name` 就在手上，抄下來就不必自己重算，也不必為了一行字再問一次（brief §7.7、§20.9）。空字串＝還沒收錄。
- `events`：`id`、`job_hash`（nullable）、`media_id`（nullable）、`type`、`actor`（user id / `system` / `rss:<series>` / `ai`）、`payload_json`、`created_at`。索引 `(job_hash, created_at)`。

### 2.4 RSS 與問題

**M3 票 08 只建了用得到的欄位**（`models/rss.py`，migration `b7e2c4d9a813`）：下面標「（票 NN）」的欄位等到用它的那一票再加。票 08 另加兩欄不在原表上的：`rss_feeds.created_at`（Feed 清單的順序）、`rss_items.error`（送單被拒的原文，`reason: detail`；送成了清空）。三張的關係是 Feed 長出 Item、Item 長出或找到 Series，**Series 不屬於任何一個 Feed**，所以刪 Feed 連它的 Item 一起刪（`CASCADE`），Series 與綁定留著（`.scratch/m3/rss-shape.md` §4）。
- `rss_feeds`：`id`、`name`、`url`（unique）、`kind`（`mikan` / `nyaa` / `acgrip`，票 11 加後兩種；`generic` 之後——由網址的主機認出來）、`interval_sec`（預設 900）、`exclude_json`（票 10：這一層的排除條件，字串清單、`parser.exclusion` 的格式；全域那一層在 `settings.rss`，不是表）、`enabled`（沒有消費者，未建）、`last_polled_at`、`last_error`、`primed_at`（第一輪預覽選過的那一刻，brief §15，票 11：`NULL` 的 Feed 一筆都不送；**Mikan 加的那一刻就寫**——聚合 feed 只有最近的集數，單一 feed 的整季由票 12 的補舊集處理；migration `c3e9a7f1b204` 把既有的 Feed 補成 `created_at`）、`media_id` / `route_id` / `user_id`（票 19，migration `f4b9d2e6a157`：從 Media 頁建的搜尋 feed 預先綁定的作品、Route 與建它的人，它長出的 RSS Series直接走 `bind_series`；綁不上時照一般的路去認作品；一般的 Feed 三欄都是 `NULL`。**票 21 起一般的 Feed 也可以只有 `route_id`**：自動綁定送進的 Route，收得下那部作品的 Route 不只一條時用它，brief §15「綁定」）、`created_at`
- `rss_series`（2026-09-24 取代 `rss_rules`，brief §15）：`id`、`key`（Mikan 是 `mikan:<番組 id>:<字幕組 id>`，其他是 `title:<骨幹>:<字幕組>`，兩段都 `normalize_title` 過、骨幹有羅馬字那一個名字就取它——同一組的简日、繁日發佈中文名常常不同（票 11，`parser.binding.title_key`）；unique）、`mikan_bangumi_id`、`mikan_subgroup_id`、`title_raw`（長出它的那一筆 Item 的標題）、`group`（未建：`title_raw` 已經帶著）、`media_id`（nullable = 待綁定）、`route_id`、`season`、`episode_offset`、`exclude_json`（票 10，同 Feed 那一欄）、`confirmed`（第一批審核確認過了沒，票 13：`false` 期間它送的集數入庫後一律掛 audit，確認之後 medium 也不掛；migration `a4f7c2e9d168` 把既有的補成 `false`——還沒有人以 Series 為單位看過它們）、`bound_by`（`system` / 使用者 id，`events.actor` 的形狀；沒綁是空字串）、`reasons_json`（票 09：自動綁定查到的 `domain.BindReason`，綁上時是依據、待綁定時是為什麼；`NULL` 是沒查過、或人拆掉了自動綁定。**重認的排程也在這裡**，不另開欄位：`lookup_deferred`（M3 票 20）與 `lookup_retry` 的 `attempt`、`at`（M4 票 14）就是 `rss._due_lookups` 讀的狀態）、`candidates_json`（票 09：給人一鍵選的作品 id）、`backfilled_at`（票 12：上一次讀 Mikan 單一 feed 補舊集或補漏的那一刻；`NULL` 是還沒補過，下一輪就補）、`mikan_bangumi_name` / `mikan_subgroup_name`（M4 票 13，migration `d5c8e2a7f391`：RSS 頁的來源說名字、不說 id；番組名來自自動綁定讀的番組頁與單一 feed 的 channel 標題（`mikan.parse_single_feed`，補舊集與每日補漏時沒有名字就補上），字幕組名來自番組頁與從 Media 頁訂閱時畫面送來的 `subgroup_name`；讀不到的那一格不蓋掉已有的；既有的是空字串）、`passed_before`（票 12 加、**M4 票 78 拿掉**（migration `d71e4b9a3c58`）：補舊集一律補，沒有取消勾選；因它略過的舊集在升級時放回 `matched` / `unbound`）、`enabled`（未建）、`created_at`。**完結不是欄位**（M4 票 13，brief §15「呈現」）：`list_series` 照現況算（`parser.series_finished`）——TMDB 快照 `ended` 而且這個 Series 的 Job 入庫過的那幾季、TMDB 上每一集都在帳本裡（這部作品的 `import` 列，誰入庫的都算），沒有 `unbound` / `matched` 或送出去而 Job 在 `/jobs`「在路上」那一組的 Item，最近一筆也發佈超過 7 天（`SETTLED_AFTER`：任何一筆新的——排除、重複、v2 都算——把它帶回清單一週，code-review 時加）；或最近一筆的發佈時間（沒寫的用 `seen_at`，一筆都沒有用 `created_at`）到現在超過 **30 天**（`QUIET_AFTER`，2026-09-27 shape 拍板：試跑 10 個 Series、146 筆，相鄰兩筆最長隔 22 天）。
- `rss_items`：`id`、`feed_id`、`guid`（與 feed 合併 unique）、`title`、`link`、`torrent_url`（來源只給 magnet 時存 magnet——Nyaa 的 `&m`，送單兩種都收）、`info_hash`、`size`（近似位元組，只供預覽顯示，票 11）、`published_at`、`seen_at`、`series_id`、`job_hash`（弱引用）、`status`（`unbound` 待綁定、`matched` 綁好還沒送成、`downloaded` 送出去了；`excluded` 排除條件擋下、`duplicate` 去重擋下，票 10；`passed` 新 Feed 第一輪選了「只追之後的」時已經在 feed 裡的，票 11；`new` 沒有建——寫下的那一刻就認出 Series、看過排除條件）、`error`、`skip_json`（票 10：`excluded` / `duplicate` 的那一條 `domain.SkipReason`，其他狀態是 NULL）。**`release_info_json` 沒有建**（票 10）：排除與帳本那一層去重要的季集與 Tags 由標題當場解析（純函式），沒有第二個讀者。
- `issues`：`id`、`type`（**十四種**，2026-09-22 定十一種、M2 票 09c 加兩種、M3 票 17 加一種：brief §9.1 對帳的七種 `library_link_missing` / `source_missing` / `inode_mismatch` / `orphan_complete` / `unknown_torrent` / `unmanaged_library_file` / `job_without_files`，管線自己發現的四種 `missing_files` / `client_error` / `client_removed` / `jellyfin_item_unresolved`——M1 `issue_detected` 事件已經在用的 `IssueType`——與 `health_checker` 量出來的兩種 `library_uses_tvdb` / `low_disk_space`，以及 Jellyfin 回驗的 `jellyfin_item_mismatch`（§11.4 ③：反查與對帳的 Jellyfin 那一方比同一份，只寫 `issues`、不寫事件）；`issues.type` 與事件共用同一個封閉集合）、`job_hash`、`ledger_id`、`path`、`detail_json`、`status`（`open` / `resolved` / `ignored`）、`detected_at`、`resolved_at`、`resolved_by`。 條件自己解除的由系統收（`resolved_by = system`）：健康檢查那兩種；importer 接回帳本某一列時掛在那一列（`ledger_id`）上的 `library_link_missing` / `source_missing` / `inode_mismatch`，與入庫長回帳本時那一筆的 `job_without_files`（M2 票 10）；管線那三種（`missing_files` / `client_error` / `client_removed`）在 Job 已經不在那個壞掉狀態時（poller 接回、別的路徑推走、被刪掉）由 poller 每一輪收（`issues.close_settled`，M3 票 02）；`jellyfin_item_mismatch` 在下一次反查或對帳**比到**一致時收，找不到 item 不算一致（M3 票 17）；**Jellyfin 還在認也不算比到**（M4 票 02）：Episode 讀不出季號或集號、或作品沒有 `ProviderIds.Tmdb`（`resolver.still_identifying`）時不開也不收，反查照還沒找到的節奏再問，**六次都還認不出才開 `jellyfin_item_mismatch`**——不是 `jellyfin_item_unresolved`，Jellyfin 列出了這個檔案，`detail_json` 並排兩邊正說得出它讀成了空的；對帳遇到還在認的與找不到同一個待遇（不動）——「還在那個狀態」與按鈕按得下去是同一份定義（`issues.STANDS_WHILE`，`client_removed` 多收一個 `submit_failed`：重新送單被拒的那一筆落在那裡）。
  **冪等鍵**是 `(type, subject)`，`subject` 依型別取：有路徑的用 `path`（`library_link_missing` / `source_missing` / `inode_mismatch` / `unmanaged_library_file` 用帳本或檔案的路徑，`orphan_complete` 用目錄路徑）、`unknown_torrent` 與 `client_*` 用 `job_hash` 或 info hash、`job_without_files` 與 `jellyfin_item_unresolved` 用 `job_hash` / `ledger_id`，`jellyfin_item_mismatch` 用 `ledger_id`（同一個 Series 被認成別的作品時每一集各一件），`library_uses_tvdb` 用那條 Route 的目標路徑（一條 Route 一件，使用者 2026-09-23 拍板），`low_disk_space` 用量的那個根目錄（同一個檔案系統只量一次，complete 先）。**`missing_files` 用 `job_hash`**（2026-09-22 票 05 實作時改判，原本列在「用路徑」那一組）：它有兩條偵測路徑，而 qBittorrent 報 `missingFiles` 的那一條手上一條路徑都沒有——多半正是因為它看不到那個掛載；而它的下一步（重新 recheck / 承認遺失）本來就是整包 torrent 的事。少了哪幾個放在 `detail_json.missing`。**`subject` 是一個存下來的欄位**（票 05）：取出來的值要落在某處，資料庫的 partial unique index 才守得住它（只蓋 `status = 'open'`，決定過的留著當歷史）——同一個 `(type, subject)` 只有一筆 `open`，再偵測到就更新 `detail_json` 與 `detected_at`。`ledger.status.target_missing` 與 Issue 的 `library_link_missing` 是同一件事的兩個角度：帳本那一欄是這一列的現況，Issue 是「要有人決定」的那一件，resolve 之後把帳本那一欄改回 `ok` 或刪掉那一列。**`source_missing` 反過來**（M2 票 09）：帳本那一欄是**按下「標記為已無來源」之後**才改，改了之後對帳就不再為它開 Issue——它是使用者決定過的現況（同刪除範圍只勾「刪 complete 檔案」的結果）；偵測時就改的話，「忽略」之後下一輪就再也不會問了。**`unlinked` 同一個先例**（M3 票 01）：刪除範圍只勾「移除鏈接」拆掉的那幾列寫 `unlinked` 而不是 `target_missing`——磁碟上兩者一樣是目標不在，差別只在有人決定過——對帳不再為它開 `library_link_missing`。

### 2.5 不做的事

- 不建 `episodes` 表：季集結構存在 `media.tmdb_snapshot_json`，查詢在 Python 做；帳本以 `(media_id, season, episode)` 引用。理由：TMDB 是唯一來源，快照整體更新比逐列同步簡單。
- 不做軟刪除：刪除範圍（brief §9.2）決定哪些列真的刪；歷史靠 `events`。

---

## 3. 狀態機與背景迴圈

### 3.1 Job 狀態轉換【決定】

| 從 | 觸發 | 到 | 副作用 |
| --- | --- | --- | --- |
| — | `add_download` | `requested` | 建 job、event `created` |
| `requested` | qBittorrent 接受 | `submitted` | event `submitted`（category、save_path） |
| `requested` | qBittorrent 拒絕 / 不可達 | `submit_failed` | event；可手動重試回 `requested`。**暫時與否分兩種**（M4 票 03）：**暫時的**是 `adapters.http.is_transient`——連不上、逾時（含 `ReadTimeout`）、解不到主機名、429、5xx，qBittorrent 與重送時抓 `.torrent` 那一站都算；event 多寫 `attempt`（第幾次）與 `retry_at`（下一次自動重送的時刻，次數用完是 `null`），由下一列自動重送。**再問也一樣的**——`.torrent` 404、qBittorrent 明確拒絕（415 等 4xx）、同名 category 指向別處、憑證被拒——不寫 `attempt`，照舊等人 |
| `submit_failed`（暫時的） | `qbit_poller` 問得到 qBittorrent 的那一輪、`retry_at` 已過（`jobs.retry_due`） | `requested` → `submitted` / `submit_failed` | event `retried`（actor `system`），之後與人按的重試同一段收尾，`attempt` 接著數。**退避 1 分鐘、10 分鐘、1 小時、6 小時**（`jobs.SUBMIT_RETRIES`，照 `jellyfin_resolver` 反查排程的先密後疏），一筆最多送 1 + 4 次，第五次失敗寫 `retry_at = null` 停下等人。**qBittorrent 停機不花次數**：poll 失敗的那一輪走不到重送，停機一整夜的那一批在服務回來的第一輪接上；放在 poll 之後，客戶端其實收下了的已由同一輪的接回（下面 `submit_failed` → `submitted` 那一列）認回、不會再送一次。前提與人按的重試同一組（Route、磁碟門檻），不成立的留在原地不花次數，磁碟不夠時整輪停下。**一輪遇到第一筆又失敗就收手**：poll 答得了不代表送得進去（M3 票 21 真站一次送近兩百個時 qBittorrent 逾時），照送下去一整批會在同一刻各燒掉一次次數；收手之後每一輪只花一筆，其餘留到下一輪。次數與 `retry_at` 在拿到 `job_lock` 之後重讀，等鎖時被人按過的重試不會被蓋掉。人按的重試（與 Issue 的重新送單）`attempt` 從 1 重新數 |
| `requested` | **程序啟動時仍停在這裡**（送單途中被打斷） | `submit_failed` | `error = interrupted: …`、event `submit_failed`（`jobs.fail_interrupted`，lifespan 在迴圈與 API 起來之前跑，M3 票 02）。**落到 `submit_failed` 而不是當場重送**：被打斷的正是等 qBittorrent 回應的那一段，它可能已經收下了——那一種由下一列認回；qBittorrent 在啟動那一刻多半還沒起來（compose 的啟動順序）。**它算暫時的**（M4 票 03，`attempt = 1`）：沒收下的由上一列在 poller 問得到 qBittorrent 之後自動重送，不再等人。只在啟動時跑：平常跑會把正在送的那一筆判成失敗 |
| `submit_failed` | poller 在客戶端看到同一個 hash | `submitted` | event `recovered(from, state, client_state)`；凍結資料夾名、記下「上次用的 Route」——它其實送成功了（brief §4.5）。之後同一輪照常往前走；它有 Job，所以不是 `unknown_torrent`（M3 票 02） |
| `submitted` | `torrents/files` 非空且 state 不是 `metaDL` | `metadata_ready` | 建 `job_files` + event `metadata_received`（票 10）；pre-plan 由 `planner_runner` 在下一輪補上（`plans.status = preplan` + event `preplan`，票 11）——poller 那一輪不算 Plan，兩件事的失敗理由不該綁在一起 |
| `metadata_ready` | 有進度 | `downloading` | event `progress`（每跨 25% 一筆） |
| `downloading` | `stalledDL` 超過 N 分鐘 | `stalled` | event；恢復進度即回 `downloading` |
| `downloading` / `stalled` | client state `missingFiles` / `error` | `missing_files` / `client_error` | issue |
| 任何活躍狀態 | torrent 從客戶端消失 | `client_removed` | issue `client_removed`；可 `reimport` 若 complete 檔案仍在 |
| `imported` / `import_failed` / `removed` / `client_removed` | `POST /jobs/{hash}/reimport`（`REIMPORTABLE`） | `completed` | complete 裡那一包讀得到才動（否則 409 `content_missing`，Job 不動）；`job_files` 照磁碟上現在的樣子重寫（不在的刪、新的補、還在的留 id 與優先序）；event `retried(state=completed, action=reimport)`——它是去重界線。之後規劃器與 importer 照常一輪，帳本以來源冪等（M2 票 10） |
| — | Issue `orphan_complete` 的「重新入庫」 | `completed` | 建一筆 `trigger = reimport` 的 Job，主鍵是那個目錄路徑的 SHA-1（`claims.adopted_hash`，同一個目錄同一筆），Route 由它在哪一條 Route 的 complete 子目錄決定，作品由管理員選；event `created`（M2 票 10） |
| — | Issue `unknown_torrent` 的「認領」 | `submitted` | 按下去重問 qBittorrent；Route 由 category 決定（只掛 `berth` tag 的不猜）、作品由管理員選；event `created` + `submitted`，之後 poller 照常（M2 票 10） |
| `missing_files` / `client_error` / `client_removed` | poller 在客戶端看到它好好的（使用者在 qBittorrent 裡自己 recheck、重新開始、把 torrent 加回去） | `metadata_ready`（沒有 `job_files` 的回 `submitted`） | event `recovered(from, state, client_state)`，它是事件去重的界線（接回之後一分鐘內又壞一次的那一筆與第一次一字不差）。「好好的」：`client_removed` 是看得到就接回（接回之後若是壞的，下一步照常轉進壞掉的狀態）；另外兩種要客戶端狀態不是壞掉、**而且它說做完了的話檔案真的在磁碟上**——Berth 自己發現的 `missing_files` 客戶端說的是 `stalledUP`，只看字串會每一輪「恢復」再壞一次。掛著的 Issue 由系統收（§2.4，M3 票 02） |
| `missing_files` / `client_error` | Issue 的「重新校驗」/「重試」 | `metadata_ready`（沒有 `job_files` 的回 `submitted`） | 先向 qBittorrent 送 `start` 再送 `recheck`（重試只送 `start`，brief §20.2；**順序不能反**：5.x 對停住的 torrent recheck 完會再停下來，校驗中送到的 start 清不掉，M3 票 03），問不到就整顆不做、Job 不動；event `retried(state, action)`。之後由 poller 照常往前推，校驗完仍缺檔就照常再開一件（M2 票 09c） |
| `client_removed` / `submit_failed` | Issue 的「重新送單」 | `requested` → `submitted` / `submit_failed` | Route 前提、下載連結（**要拿回同一個 hash**）、qBittorrent 在不在**先問完才動 Job**；之後與 `submit_failed` 的重試同一段收尾。`submit_failed` 在起點是因為上一次重新送單被拒的那一筆落在那裡，那一件 Issue 仍然開著（M2 票 09c） |
| `missing_files` / `client_removed` / `submit_failed` | Issue 的「承認遺失」/「承認移除」 | `removed` | 就是 `delete_job`、四個旗標全不勾：磁碟與 qBittorrent 都不動，event `deleted`（M2 票 09c，使用者拍板） |
| `downloading` | 完成條件（brief §5.1） | `completed` | event `completed` |
| `completed` | planner_runner 取得 | `planning` | 讀 mediainfo、更新 `job_files`（`kind` 與 `mediainfo_json`）。**進了 `planning` 就先 commit**，畫面才說得出它正在做什麼；算到一半被關掉的那一列停在這裡，下一輪掃到它會從頭再算一次（票 11） |
| `planning` | Plan 全 high/medium 且 Route 允許 | `importing` | `plans.status = auto`、event `plan_generated`；medium 的 item 掛 `audit`。**`unmatched` 不算在「全 high/medium」裡**（票 11）：它一律是 low，但那不是低信心而是一個**已經做完的決定**——「這是一個節目，但它不是 TMDB 上的任何一集」（brief §7.6），檔案留在 complete 原位由 Unmatched 清單處理。動漫批次幾乎每一包都夾著一兩個這種 SP，擋下去等於 §11.2 T1.6 的「不經人工入庫」永遠達不到；它仍然數進 `summary.low`，畫面上看得見 |
| `planning` | 否則 | `review` | `plans.status = pending_review`、event `review_required(reason)`。理由是封閉集合（`ReviewReason`）：`low_confidence` / `medium_not_allowed` / `nothing_to_import`——三種的下一步不同（票 11）；M3 票 14 加 `air_date_conflict`（播出日比對擋下的，§4.4），它排在最前面——被擋的那幾列信心仍是 high / medium，下一步是改季集而不是點頭。M3 票 15 加 `runtime_conflict`（片長驗證擋下的，§4.1），排在它之後、同一個道理——一列兩條都犯時先改季集。**不另外寫 `plan_generated`**：一個轉換一筆事件，兩筆說的是同一件事 |
| `review` | 使用者核准 | `importing` | `plans.status = approved`、event `review_decided(decision=approved, files)`。**核准＝照提案入庫**（M2 票 07，2026-09-23 使用者拍板）：待審核的列季集完整就變成 `import`，寫下的目標路徑就是 `pending_review` 時畫面上顯示的那一條（`parser.promote` + `parser.revise`，`services/plan_view.landing`）；還有沒提案的列或兩列撞同一條路徑時拒絕（`PlanRefusal.undecided` / `target_clash`）。檔案由 importer 照這一份鏈接，核准不另走一條入庫的路 |
| `review` | 使用者拒絕 | `completed` | `plans.status = rejected`、event `review_decided(decision=rejected)`；規劃器被叫醒、**整份重算**（逐列改過的不留），所以拒絕的意思是「丟掉這一份、重來」。檔案不動。`review_decided` 是事件去重的界線（同 `retried`）：重算出來的 `review_required` 與第一份一字不差，不設界線會被吞掉（票 07） |
| `importing` | 全部 item 套用完 | `imported` | event `linked` ×N（一個檔案一筆，鏈接當下寫）；**狀態落地之後**才通知 Jellyfin：`jellyfin_scan_requested`，失敗是 `jellyfin_request_failed(request=scan)` 且不擋（§3.3）。反查在 `jellyfin_resolver`（§3.2）：這一筆的正片**全部**在 Jellyfin 找到的那一輪寫 event `jellyfin_item_resolved(count)`，`count` 是這一筆的正片數，**一筆 Job 只寫一次**——M4 的「可以看了」就是它（M4 票 02）。「找到」是帳本那一列有 item、不再排反查：還在認的不算；認成別的、或六次都認不出而開了 `jellyfin_item_mismatch` 的算（它在 Jellyfin 裡打得開，錯在哪由那一件說）；有一集放棄了（`jellyfin_item_unresolved`，Jellyfin 沒列出它）就不寫 |
| `importing` | 任一 item 失敗且不可跳過 | `import_failed` | event `link_failed`（逐檔，帶 `errno` 與原文）；重試回 `importing`，已完成的 item 跳過。**「不可跳過」是正片**（`import`）：字幕與特典鏈接不成只記在那一列上、不擋整筆——那一集仍然看得了（票 12） |
| `importing` | 目標已存在且 inode 不同 | `review` | item 標 `target_unmanaged`、`plans.status = pending_review`、event `review_required(target_exists)`。其餘不衝突的檔案照樣鏈接；人決定之後重來一次它們會被跳過（§3.3，票 12） |
| `imported` | Issue `job_without_files` 的「重新規劃」 | `completed` | 帳本一列都沒有時才走得通（CAS + `job_lock`）；event `retried(state=completed)`——它是事件去重的界線，重算出來的 `plan_generated` 才不會被吞掉。之後由規劃器與 importer 照常的一輪接手，帳本以來源冪等（M2 票 09）。**不併進 `replan_job`**：那一支是 Job 頁上那一顆（`REPLANNABLE`），把 `imported` 加進去等於每一筆入庫完的 Job 都多一顆會重鏈一次的按鈕 |
| 任何狀態 | `delete_job` | `removed` | 依範圍刪除（brief §9.2 的四個旗標）；event `deleted`，payload 說的是**真的**做掉了什麼（`links` / `sources` / `torrent` / `purged` / `freed` / `unmanaged`）而不是勾了哪幾個。勾了 `purge` 的話連這一列與它的事件一起消失，所以那一次沒有時間線可看（票 04）。**轉換是鎖裡的第一件事**（M3 票 01）：CAS 的 `expected` 是請求進來時讀到的狀態（使用者按下去時看到的那一個），輸了是 409 `moved_on`、什麼都沒動——兩個分頁同時刪同一筆時，後到的那一個不會對著剛刪過的 Job 再刪一次、回報成功；先到的那一個勾了 `purge` 時後到的是 `job_missing`。之後的步驟被拒絕（qBittorrent 問不到）時連這一次轉換一起 rollback。媒體庫那一側只拆 Berth 放的那一個（brief §9.2），沒拆的列在 `unmanaged`

- **帳本以來源冪等**（M2 票 10，brief §9.3）：importer 先以目標路徑、再以「同一筆 Job 的同一個 `source_rel_path`」找那一列。後者命中而路徑換了（TMDB 改了集名）時那一列改寫、舊路徑上**與來源同 inode** 的那條鏈接收掉；帳本仍說 `ok` 而鏈接是這一次才新建的（媒體庫被刪而對帳還沒跑）也重寫那一列、重排反查、寫 `linked`。
- 轉換一律 compare-and-set：`UPDATE jobs SET state=:to WHERE hash=:h AND state=:from`，影響 0 列即放棄本次操作。
- 每個 job 在程序內另有 `asyncio.Lock`，避免 poller 與 importer 同時處理。
- **迴圈吞掉的例外寫在那一筆身上**（M3 票 02）：planner 與 importer 的一筆 Job 爆掉時（`jobs.guarded`）那一輪放棄、下一輪再試，同時寫 `Job.error`（型別加原文）與一筆 `round_failed`。**同一個錯誤只寫一次**：`Job.error` 還是那一句就是同一件事——迴圈每 60 秒重試，否則一天一千四百筆；成功的轉換清掉 `error`。
- **一輪可以走好幾步**（票 10）：已經做完種的 torrent 加進來時，同一輪裡它會走完 `submitted → metadata_ready → downloading → completed`。輪詢的間隔不該決定使用者看到幾個階段，而時間線仍然說得出它經過了哪些站。
- **多集檔與同起始集的單集送 review**（票 14b、brief §7.8）：新 Plan 的正片與同一份 Plan 的其他正片、或與同一部作品同一季的帳本 Entry，**起始集相同而結束集不同**時一律停下來等人。Jellyfin 12 的版本分組鍵只有季號與集號，`S01E03-E04` 與 `S01E03` 會被併成同一集的兩個版本，第 4 集從集列表上消失（brief §20.9 實測）。同一包裡的那一半是純函式（`parser/planner.py`，benchmark 量得到），對帳本的那一半在 `services/plan.py`。
- **壞掉優先**：`missingFiles` / `error` 的 torrent 也可能報 `progress == 1`，先問完成的話它會被當成下載好了，而磁碟上根本沒有那些檔案。
- `stalled` 的「超過 N 分鐘」量的是 qBittorrent 自己的 `last_activity`（**10 分鐘**），不是 Berth 另存一個「什麼時候變成 `stalledDL` 的」——客戶端本來就在量同一件事。

### 3.2 背景迴圈

| 迴圈 | 間隔 | 工作 |
| --- | --- | --- |
| `qbit_poller` | 有活躍 job 時 5s，否則 30s；連續失敗退避到 5 分鐘 | `sync/maindata`（帶 rid）；只看本系統 category **或 `berth` tag** 的 torrent（兩道篩子的聯集：Route 被刪掉之後它送出去的那些 torrent 仍然認得出來）；更新進度與 client state；驅動 §3.1 中由客戶端狀態觸發的轉換（含 `submit_failed` 與三種壞掉狀態的接回，M3 票 02）；**問得到 qBittorrent 的那一輪之後**把到時間的暫時送單失敗再送一次（`jobs.retry_due`，M4 票 03，§3.1）；每一輪收掉 Job 已經不在那個壞掉狀態的管線 Issue（§2.4）；發現無 job 的 torrent → issue `unknown_torrent`（**M1 先寫一筆 `issue_detected` 事件並列在健康頁的「下載迴圈」區塊**，`issues` 表在 M2，票 10） |
| `planner_runner` | 事件驅動（提示）+ 每 60s 掃 `completed` **與 `planning`** | 讀 mediainfo → 解析（§4）→ 建 Plan → 決定 auto / review；順手替下載中、還沒有 Plan 的 job 算 pre-plan |
| `importer` | 事件驅動（planner 算完、使用者按入庫重試）+ 每 60s 掃 `importing` | 逐 item：建目錄 → `link()` → 寫 ledger → event，**一個檔案 commit 一次**；完成後 `POST /Library/Media/Updated`；一次只處理一個 job（依序：同一個作品資料夾可能同時是兩筆 Job 的目標） |
| `jellyfin_resolver` | 每 15s 醒一次；每筆帳本自己的排程 30s → 2m → 10m → 1h → 1h → 1h，共 6 次（`ledger.resolve_after`） | 為到時間的 ledger 找 item（brief §20.1 的兩段查詢，也比 `MediaSources[].Path`——第二個版本不是 item 自己的 `Path`）；找到之後把那一條來源的 `Name` 抄進帳本（版本名是 Jellyfin 算的，票 14b），並**回驗**：Jellyfin 認的季號、集號（多集檔是範圍）與所屬作品的 `ProviderIds.Tmdb`（Episode 看它 `SeriesId` 那一個 Series，Movie 看自己）要與帳本一致，不一致開 `jellyfin_item_mismatch`、一致了收掉（`resolver.disagreement`，M3 票 17）。**Jellyfin 還在認的不算找到**（M4 票 02，`resolver.still_identifying`：Episode 季集 `None` 或作品沒有 Tmdb）：不抄 item、不比，照同一份排程再問但**最晚 10 分鐘**（同請它掃描之後，`SCAN_SETTLE`），也不再通知它（它已經列出這個檔案，再掃只會從頭認起）；六次都還認不出（入庫後約 43 分鐘）才照它讀成的樣子比。**間隔的依據**：2026-09-26 試跑量到的上界是入庫後約 12 分鐘（brief §20.1，那是下一次反查碰巧讀到的時間），落在第 3 次（12.5 分鐘）之內；而季集讀自檔名、作品讀自資料夾的 `[tmdbid-…]`，都不必連網，43 分鐘還認不完的就是認不出——原本的一小時間隔只會讓真服務 e2e 的 1200 秒等不到。**一筆 Job 的正片全部找到時寫一筆 `jellyfin_item_resolved(count)`，之後不再寫**（M4 的「可以看了」，§3.1）。**新版本入庫時只把同一集的其他版本排回反查**（`importer.restate_versions`：同一個資料夾、同一季、集號範圍重疊，那是 Jellyfin 12 的版本分組；電影是同一個資料夾），版本名才跟著 Jellyfin 改——以前是整個資料夾，一季每入庫一集就把前面每一集重反查一次；**沒找到的那幾條每一輪再通知一次**（入庫當下那一次可能沒送到）；**沒找到兩次以上改跑 Jellyfin 的「重新掃描媒體庫」排程任務（`RefreshLibrary`），之後最晚 10 分鐘再看**——路徑通知對從沒掃到過內容的媒體庫無效，而套件內的媒體庫一開始一定是空的（brief §20.1，票 12 實跑抓到）；耗盡寫 `issue_detected(jellyfin_item_unresolved)`（`issues` 表在 M2）。**不是事件驅動**（票 12）：第一次反查本來就排在入庫 30 秒後，importer 那一刻叫醒它也只會看到「還沒到」。**作品頁打開時提前問一次**（M4 票 51，`resolver.resolve_early`，`POST /media/{id}/resolve`）：退避中最多要等 10 分鐘，而觀看區與媒體庫頁直接問 Jellyfin，審計 S6 看到兩邊說法不同；這部作品還在排反查的帳本先問一次，**找到而且認完的走上面同一條路**（記 item、不再排程、回驗、`jellyfin_item_resolved`），**沒找到、還在認、問不到的不動**——不算一次、不改排程、不通知（打開頁面就會跑，算次數的話開幾次頁面就用完了） |
| `reconciler` | 每日 04:00（容器的 `TZ`，compose 範本預設 `Etc/UTC`）+ 手動 `POST /reconcile` | brief §9.1 全部檢查，寫 `issues`（冪等鍵見 §2.4）。**一輪是一個可觀察的工作**（2026-09-22 定）：`POST /reconcile` 回 202 並給這一輪的 id，`GET /reconcile` 回上一輪與進行中的進度（哪一方比到哪、幾筆），上一輪還在跑時再按是 409 `reconcile_running`——不排隊，因為排隊的那一輪看到的會是同一份磁碟；e2e 的「三種破壞都能偵測」靠輪詢它。四方各自走完才寫下 Issue，任一方問不到（qBittorrent 掛了、Route 目錄沒掛上）就跳過那一方並在這一輪的結果上說出來，不把「問不到」誤判成「不見了」（brief §16.2）。**每一種檢查只用它需要的那幾方，缺一方就整種不做**（M2 票 09）：`orphan_complete` 要 qBittorrent 與 complete 兩方都問到（問不到 qBittorrent 的那一刻每一個目錄看起來都沒有主），`unknown_torrent` 要 qBittorrent（與 `qbit_poller` 共用冪等鍵與內容），媒體庫那四種逐 Route，`job_without_files` 只看帳本。complete 那一方只看**每一條 Route 的 complete 子目錄**，不看整個 complete root（它可能與 Sonarr 共用，brief §16.4）。**第五方是 Jellyfin**（票 09）：把反查過的正片照 Jellyfin 現在的樣子重對一次——補上票 13 之前沒有的 `jellyfin_series_id`、換掉 Jellyfin 12 合併之後不再是主條目的 `jellyfin_item_id`（brief §20.9）；找不到的不動，問不到一樣跳過並說出來。**M3 票 17 起它也回驗**：找得到的那幾條與反查比同一份，不一致開 `jellyfin_item_mismatch`、一致了收掉，件數算進這一輪的結果。大媒體庫分不分批由 §11.3 的量測票決定：**M2 票 11 量過，1,000 部 × 12 集一輪 27–31 秒，不分批**（門檻 10 分鐘；時間在 `resolver.locate` 的逐條線性比對，下一次重量的條件見 `docs/research/large-library.md` §3） |
| `rss_poller` | 每 30 秒醒一次，到時間的 Feed（上次輪詢滿自己的 `interval_sec`，預設 15 分鐘）各輪一次；精靈跑完之前不做事 | 抓 feed → 解析 → 新的 Item（同 Feed 的 GUID 去重）讀單集頁認出 RSS Series，找到或長出一列 → 寫 Item（Series 待綁定時 `unbound`、留著不送）→ 綁好的送 `add_download`（`trigger = rss`、`trigger_ref` = Series id，時間線的 actor 是 `rss:<id>`）。**單集頁抓不到的那一筆不寫**，下一輪再試（寫了就是見過）；Feed 抓不到記在那一列的 `last_error`；一個 Feed 爆掉不拖累其他的。送單被拒的那一筆留在 `matched` 帶著原文，下一輪再送（M3 票 08）。**寫 Item 時看排除條件**（全域、Feed、Series 三層聯集，擋下的是 `excluded`），**送單前去重**（同一個 info hash 的 Job 在了、或另一筆 Item 送過；帳本已有同 Media / 季 / 集 / Tags——擋下的是 `duplicate`，M3 票 10）。**每日補漏**（M3 票 12，brief §15「補舊集」）：一個 Feed 輪完、送單之前，以它為 home（最早帶到那個 Series、還在的 Mikan Feed，綁定時補舊集寫的也是它）的**已綁定 Mikan RSS Series** 裡 `backfilled_at` 是 `NULL` 或滿一天的，各讀一次單一 feed（`/RSS/Bangumi?bangumiId=&subgroupid=`），寫成**這個 Feed 的 Item**（`(feed_id, guid)` 去重、同樣看排除條件、同一次 `_submit_waiting` 送出）。讀不到的記在 Feed 的 `last_error`、`backfilled_at` 不動，下一輪（Feed 的間隔）再試。**每一個請求都先在那一站的請求預算裡佔一格**（M3 票 20，見下）：被擋下的走同一條「讀不到」的退路 |
| `health_checker` | 每 30 秒醒來，上一輪滿 5 分鐘才真的跑；也可手動觸發（`POST /health/check`） | 四項：Jellyfin（連線 + API key 列得出媒體庫）、qBittorrent（連線 + Web API 版本；全域偏好不看，M4 票 32）、索引站（Prowlarr；M4 票 37 起不再有 Torznab 端點）、Route（§9.5 的每一條纜繩重跑一次；探針沿用上一次的結論，從沒問過的那一條 Route 是 `unknown`「要重新檢查」，不算綠，M4 票 59）。四項之後量兩件會變成 Issue 的事（M2 票 09c，`services/health_issues.py`）：每條 Route 的媒體庫掛不掛 TVDB（`library_uses_tvdb`）、incomplete / complete 剩的空間夠不夠（`low_disk_space`，門檻 `settings.disk.min_free_gb`）。條件解除時由系統收掉，問不到不算解除 |

- 每個迴圈是一個 `asyncio.Task`（`main.py` 的 lifespan 啟動，關閉時 cancel 並 await，不留 pending task；cancel 落在一輪中途時那一輪先做完再收，`pipeline/ticks.py`——async SQLAlchemy 不支援 IO 半途 cancel，M4 票 71b）；例外只記 log 不讓迴圈死掉；連續失敗次數與最後錯誤寫入**自己那一列設定**供健康頁顯示（`settings.health` / `settings.poller`）。原文寫的是「寫入 `settings.health`」，但那一列每 5 分鐘被 `health_checker` 整組覆寫一次，而 poller 每 5 秒寫一次——兩個迴圈共用一列會互相蓋掉（票 10；理由與當初把健康結果從 `settings.services.*` 分出來時一樣）。
- `qbit_poller` **醒得比問頻繁**（與 `health_checker` 同一個形狀，票 10）：每 5 秒醒一次，但只有距離上一輪滿了它該等的間隔才真的問，而那個間隔**每次醒來重算**。沿用上一輪算出來的答案的話，使用者按下送單的那一刻多半落在一個 30 秒的閒置間隔中間，他要對著那一列等最多半分鐘才看到第一個變化。
- `qbit_poller` **把 qBittorrent 的 HTTP client 握著不放**：`sync/maindata` 的 `rid` 增量掛在那條連線的 session 上（brief §20.2 實測），每輪重造一個 client 等於每輪都要一份全量。失敗那一輪才丟掉重造——重造就是重新開始，而重新開始本來就會拿到一次全量，兩邊自然對齊。
- `qbit_poller` 的**推播在 commit 之後**（票 10 實跑抓到）：反過來的話前端收到「這一筆完成了」就立刻重問一次，而那一次讀到的是還沒 commit 的舊狀態，畫面因此永遠慢一步。
- **每日補漏排在 `rss_poller` 裡、以每個 RSS Series 自己的 `backfilled_at` 滾動一天，不是固定鐘點**（M3 票 12）：它與輪詢同一個形狀（醒來看誰到時間了），重試的節奏直接用 Feed 的間隔；補漏的讀者只有綁好的 Mikan RSS Series，而它們一定掛在某個 Mikan Feed 上——Feed 刪掉就是不再訂閱，補漏跟著停。滾動而不是 `reconciler` 那種每日 04:00：一次打一個單一 feed，分散在一天裡；固定鐘點會讓 N 個 RSS Series 同一刻打 Mikan。一天一次、每個綁好的 RSS Series 一個請求，季末之後照樣讀（量隨綁過的部數線性長），所以它也吃下面那一份請求預算。
- **一個站一份請求預算**（M3 票 20，`adapters/budget.py`，研究 `docs/research/request-budget.md`）：`rss_poller`（Feed、Mikan 單集頁與番組頁）、補舊集與每日補漏（單一 feed）、索引站搜尋，加上人在 `/rss` 按的讀取（一次性連結、Mikan 代搜、從 Media 頁訂閱）打的是同一批公開站——Prowlarr 預設的 Mikan、Nyaa、ACG.RIP 就是 RSS 那三站——所以以**主機名**為鍵共用一份。**形狀照 Prowlarr 索引站的 Query Limit**：一個站在**滾動**的一段時間裡最多幾個請求（不是整點歸零），用完的那一個**被拒絕、不排隊**，放得下的時刻＝窗裡最早那一筆 + 窗長（Prowlarr 的 `IndexerLimitService` 同一個算法；它也把 RSS 與查詢算在同一份 Query Limit 裡）。數字是**每站每小時 60 個**：Prowlarr 預設不限、要使用者自己填，沒有現成的數字可抄；60 是拿用量推的——Mikan 聚合 feed 照 AutoBangumi 與 Sonarr 慣用的 15 分鐘一輪是每小時 4 個、新季開播時一輪十幾個單集頁、補漏一天每部一個，剩下的放得下十來批搜尋（一批 5 個查詢 × 索引站背後的每一站）。被擋下的照它自己的退路延後：Feed 本身與單集頁走「讀不到、下一輪再試」（`last_error` 說得出是預算）；補漏 `backfilled_at` 不動；**自動綁定讀番組頁被擋不算「查不到」**，理由寫 `lookup_deferred`、之後輪到它的 Feed 時再認（`lookup_failed` 照舊不重試；另一種會重認的是下一段的 `lookup_retry`）；搜尋**這次不問放不下的那幾站**、其他站照問，每一站都放不下才一個查詢都不問、回 `budget_exhausted` 與最早放得下的時刻；人按的讀取是 429 `budget_exhausted`。搜尋打到哪幾站由索引站回答（`IndexerSearch.sites()`：Prowlarr 是啟用中的每一站的 id、名字與 Base Url）；一批搜尋在放得下的每一站各佔「查詢數」格，查詢只帶那幾站的 `indexerIds`（每一站都放得下時不帶，照舊問全部），放不下的列在結果的 `skipped`（站、索引站名、何時放得下）。**M4 票 77 推翻票 20 的「有一站放不下就整批不問」**：使用者訂閱 MyBangumi 後 Mikan 一小時的額度被 RSS 用完，搜一部與 Mikan 無關的美劇也一站都不問；Prowlarr 自己的 Query Limit 也是「打滿的那一站那一次跳過」（brief §20.13）。**記在程序的記憶體裡、重啟歸零**：Prowlarr 從歷史表數，Berth 沒有逐請求的歷史表，為了數請求開一張表就要在背景迴圈與 API 之間多一個搶 SQLite 寫鎖的寫者（寫者等滿 `busy_timeout` 就爆 `database is locked`；票 14b 與 M4 票 01 的教訓，§3.3 的寫交易紀律）；重啟最多多送一個窗的量。健康頁的「請求預算」（`GET /health/budget`）列出每一站誰用了多少、哪一種工作被延後、何時放得下。**沒做的兩件**（研究檔的第 3、5 點）：每秒幾個的節流（Cardigann 的 `requestDelay`，只有 nyaa 設了 2 秒；Berth 的請求本來就一個接一個等回應，搜尋一批五個併發）、站台回 429 或出錯之後、以**站台**為單位的逐級退避（Sonarr 的 `EscalationBackOff`；M4 票 14 的重認是以**RSS Series**為單位的有限重試，只管自動綁定，見下一段）；`.torrent` 的下載（Prowlarr 的 Grab Limit 那一份）也不算在這裡——**M4 票 03 開工時使用者拍板維持不算**（2026-09-26）：照 Prowlarr 把 Grab 與 Query 分成兩份，補舊集一次送一百多集不會把同一站 RSS 輪詢與搜尋的額度吃光；代價是大批送單時對那一站的 `.torrent` 請求不設上限。
- **自動綁定暫時查不到時有限重認**（M4 票 14，brief §15「綁定」、§19 2026-09-26）：番組頁或 TMDB 這一次讀不到，而且是**暫時的**（`adapters.http.is_transient`：連不上、逾時、解不到主機名、429、5xx——**429 與 503 以外的 5xx 從 M4 票 14 起歸 `ServiceUnavailableError`**，以前是 `ProtocolMismatchError`，一次 502 就永遠待綁定），理由寫 `lookup_retry`（`site` 是那一站、與請求預算同一種鍵；`attempt` 第幾次；`at` 下一次的時刻；`detail` 原文），`rss._due_lookups` 在輪到帶著它的 Feed、而且過了 `at` 時再認。**退避 1、4、12 小時（`rss.LOOKUP_RETRIES`），一個 Series 最多認 1 + 3 次、分散在 17 小時裡**，用完落到 `lookup_failed`；再問也一樣的（404、回的不是那個服務、憑證被拒）當場落到 `lookup_failed`。原本「只認一次」的顧慮是壞掉的番組頁每 15 分鐘打一次——現在同一頁最多四次，而且每一次照樣在那一站的請求預算裡佔一格（`tests/integration/test_rss_auto_bind_retry.py` 數了番組頁的請求數與預算用量）。數字的理由：試跑那一次 TMDB 同日稍後就讀得到，第一次重認一小時後；最後一次在隔天，隔夜的站台維護也等得過。被預算擋下時 `lookup_retry` 那一條跟著留著，次數不歸零。TMDB 那一頭的 `unreachable`（`TmdbProblem`）也包含「回的不是 TMDB」——`services.media` 把 `ServiceError` 一概歸成它，分不開，照暫時的算，多的只是上限內的幾次重認。**一部候選讀不到不拖垮整次**：一個搜尋詞、一部作品的詳情讀不到就跳過，其餘照判；判得出來就綁，判不出來而缺的那一部是暫時讀不到的照上面重認，一部都沒讀到才是查不到。
- `health_checker` **醒得比檢查頻繁**：兩層的理由是精靈剛跑完的那一刻——迴圈在啟動時就在轉，那時候還沒有東西可檢查，如果醒來的間隔就是檢查的間隔，使用者按完「完成」會對著一個空的健康頁等五分鐘。精靈跑完之前它什麼都不做（那時候正在接的服務被打只會得到假的紅燈）。
- `health_checker` 的**磁碟空間**是一件 `low_disk_space` Issue（M2 票 09c）。門檻在設定裡（`settings.disk`，設定的 qBittorrent 那一頁可改，改了立刻重量一次），**形狀照 Sonarr 的 Minimum Free Space**（一個全域數字）而單位與預設不同：Sonarr 擋的是入庫時複製（MB、預設 100），Berth 以硬鏈接入庫不佔空間、吃空間的是下載，所以是 GB、預設 10，`0` 是不量。Route 的 `hardlink` 纜繩上的 `free=` 照舊是實測值。**同一個門檻也擋送單**（M3 票 04）：RSS 送單沒有人按確認，所以 `add_download` 與送單的重試在要 torrent **之前**量 incomplete 那一側（下載長在那裡），低於門檻是 409 `low_disk_space`、一個 Job 都不建，手動與 RSS 同一個判斷（`jobs.check_disk`）。門檻 `0` 不量；看不到那個目錄不擋——那是 `download_path` 纜繩要報的事。Issue 的「重新送單」不看（票的 Comments）。**比的是「剩餘空間 − 在途量」**（M4 票 03，`jobs._in_flight`）：在途是 `submitted` / `metadata_ready` / `downloading` / `stalled` 的 Job 還沒下完的量，`total_size × (1 − progress)`；qBittorrent 報得出之前 `total_size` 是送單時來源報的大小（搜尋結果、RSS Item 的 `size`），兩邊都不知道的不算、在 log 說有幾筆。只扣在途、不扣這一次要送的大小：門檻說的是「開新下載之前至少留多少」，與 Sonarr 的 Minimum Free Space 同一個意思。拒絕理由仍是 `low_disk_space`，`detail` 說出在途多少、幾筆。2026-09-26 試跑一次送 144 個，每一個當下都過門檻、下載途中才滿。
- `health_checker` **沒有逐服務的間隔退避**（票 10 改）：每一項各自 try/except 加上 adapter 的 5 秒逾時就足夠隔離，而 5 分鐘一次的檢查本來就打不爆任何服務；退避只會延後「服務回來之後自動變綠」。連續失敗次數仍然記錄並顯示。
- 迴圈之間用一個 in-process 的**喚醒訊號**傳「有東西動了，去看看」（`services/hints.py`，票 11）。plan 原文寫的是一條裝著「請處理 job X」的 `asyncio.Queue`，但同一段的下半句是「DB 狀態才是真相；程序重啟後由定時掃描補上」——而一旦掃描本來就找得到同一批 job，佇列裡那個 hash 就不帶任何資訊，只留下三個要回答的問題（重複的 hash 去不去重、滿了丟哪一筆、重啟之後裡面那幾筆誰來補）。訊號會自己合併：poller 一輪動了 40 筆也只是「去看看」一次。

### 3.3 冪等與重入

- `add_download`：同 hash 已存在 → 回傳既有 job，不重複送單。**那一筆是 `removed` 時拒絕**（409 `job_removed`，`detail` 是那一筆的 hash，M3 票 04）：刪除過而紀錄還在就是還沒決定要不要再下載——回傳它的話送單的人以為成功了，而 RSS 下一輪看到同一個條目會再送、再拿回同一列。重新入庫，或連紀錄一起刪掉（`purge`）之後再送，兩者都是 admin 的事；清掉紀錄之後同一個 hash 是一筆新的下載。
- importer：目標已存在且 inode 等於來源 → 視為已完成，補 ledger 若缺；目標存在但 inode 不同 → item 標 `error: target_unmanaged`（原文 `target_exists_foreign`；票 12 依 CONTEXT.md 的 Unmanaged 改名），進 review。
- ledger 的 `target_path` unique；event 寫入用 `(job_hash, type, payload hash)` 在同一分鐘內去重，避免重啟後重複「completed」事件。**使用者按下的重試是界線**：之後發生的事就算與之前一模一樣也照寫（票 12）。
- Jellyfin 通知失敗只記 event，不阻擋 `imported`；resolver 之後會再嘗試。
- **寫交易紀律**（M4 票 01，2026-09-26 試跑爆 `database is locked`）：SQLite 一次一個寫者，其他寫者最多等 `busy_timeout`（5 秒）。**先拿 `job_lock`、再開寫；網路呼叫不在寫交易裡。** 寫交易從第一個 UPDATE / INSERT（含 autoflush 送出去的那一次）開始、到 commit 或 rollback 結束；它之前的改動只要還沒 flush 就不算。
  - 鎖的順序：握著寫交易等 `job_lock` 會與「握著 `job_lock` 等寫鎖」互等（試跑：poller 一輪一個交易、逐筆拿鎖，planner 先拿鎖再寫 pre-plan）。要多把鎖的照 hash 排序一次拿齊（`jobs.job_locks`；poller 的一輪、rematch 的取代）。
  - `qbit_poller` 一輪三段：網路全部問完（`sync`、要走出 `submitted` 的那幾筆的 `torrents/files`）→ 這一輪要動的每一筆的鎖拿齊 → 一個交易寫完。**不逐筆 commit**：一輪一個交易才有「Job 接回與它的 Issue 收掉是同一刻」（`close_settled`），而下載中的每一筆每一輪都有進度要寫，逐筆 commit 是一輪上百次 fsync；鎖拿齊之後只剩資料庫操作，握不了多久。代價在拿鎖那一段：送單、重試、重新送單握著那一筆的鎖打網路，poller 等它時已經握著排序在前的那幾把，那幾筆的 planner、importer 與 API 跟著等——asyncio 的等待，不會爆 `database is locked`。
  - 要打網路的命令先打再寫，或寫完 commit 再打：`rss` 的單集頁在寫 Item 之前抓完（`_series_keys`）、綁定的補舊集在改 Series 之前讀單一 feed（`_read_season`）、刪除在向 qBittorrent 移除之後才轉 `removed`（鎖裡先比對狀態）、重試與重新送單在進 `requested` 之後 commit 再抓 `.torrent` 與送 qBittorrent（與 `add_download` 同形）。`tests/integration/test_write_discipline.py` 在這幾處與 poller 的替身上量 SQLite 寫鎖。
  - `round_failed` 寫下的 `Job.error` 由下一次成功的一輪清掉，時間線記一筆 `recovered`（`from = round_failed`）：成功的一輪不一定有狀態轉換（pre-plan 算完之後那一筆還在下載）。

---

## 4. 解析器

全部是純函式，輸入包含檔案清單、上下文與 TMDB 快照，輸出 Plan。沒有 IO，所以 benchmark 可以離線跑。

### 4.1 階段

```
files ─► classify ─► (video | subtitle | font | audio | image | archive | sample | disc | extra | other)
   │
   ├─ video / subtitle ─► normalize_cjk ─► parse_release(guessit) ─► ReleaseInfo
   │                                   └─ structure_hints(路徑) ─► SeasonHint / ExtrasFolder / SubsFolder
   ├─ video ─► map_episode(ReleaseInfo, hints, context, tmdb) ─► [Candidate]
   ├─ subtitle ─► match_subtitle(subs, videos) ─► 附掛到影片
   └─ ─► plan(items, route, media, naming) ─► Plan ─► score ─► confidence
```

| 階段 | 輸入 → 輸出 | 要點 |
| --- | --- | --- |
| `classify` | `[FileEntry]` → 加 `kind` | brief §6.2 的表；`sample` 以「檔名含 sample 且大小 < 最大影片 10%」判定——比的是**同目錄**最大的影片，同目錄只有它自己時退回整包最大的那一個——sample 幾乎都獨立放在自己的 `Sample/` 資料夾裡，只比同目錄的話這條規則永遠不成立（M1 票 05 補的推論；那一輪掃過的真實 torrent **一個 sample 都沒有**，所以規則只有單元測試守著，沒有語料）；`extra` 以關鍵字（NCOP/NCED/OP/ED 無集號、PV、CM、Menu、Preview、Trailer、Making、Interview、特典、映像特典）與資料夾（`SPs/` 內非 SP 編號，加上 Jellyfin 認得的那一串 extras 資料夾名——`Extras/`、`Bonus/`、`Featurettes/`、`Behind the Scenes/`…，brief §20.1）判定；`disc` 是**整包**的判定：任何一個檔案落在 `BDMV/` 或 `VIDEO_TS/` 底下，整個 torrent 都是 disc；mediainfo 可把時長 < 5 分鐘的「正片」降為 `extra` |
| `normalize_cjk` | 檔名 → 乾淨字串 + `CjkHints` | 從 AutoBangumi `classic.py` 與 Sonarr `Parser.cs` 移植：剝離 ★前綴、招募廣告、地區限制、【】括號正規化為 []、中文標題與英文標題並列時保留英文；抽出 `subs`（CHT/CHS/JP/EN 集合）、`hardsub`、`season_cn`（第N季/期）、`episode_cn`（第N話/集）、`collection`（合集/全集/全N話）、`special`（番外/特別篇/SP/OVA/OAD）、`movie`（劇場版/電影版）、`group_cn`。**季號要認全形羅馬數字**（`无职转生Ⅱ`、`Ⅲ`，U+2160 起）與**不以空白收邊的半形羅馬數字**（`Mushoku Tensei II]`）——實測這兩種寫法漏掉會造成整輪播出的錯置（M1 票 01） |
| `parse_release` | 乾淨字串 → `ReleaseInfo` | guessit 打底；後處理動漫模式：`- 01`、`[01]`、`01v2`、`E01` 無季、`01-12` 區間、`S01 \| 01-28+SPx11`、`第01話`；多季一包 `S01 + S02` / `S1-S2` → `season`–`season_end`（不是 S01E02，M4 票 48）；`release_kind` 由集號區間、多季與 `collection` 決定 |
| `structure_hints` | 相對路徑 → hints | 資料夾名 `Season 2` / `S2` / `第二季` / `2nd Season` / `Part 2` / `Specials` / `SPs`；`Subs/` `字幕/` 與其下的語言子資料夾 |
| `map_episode` | → `[Candidate]` | brief §6.4 的順序；絕對編號換算三法（episode group absolute、累計集數、air_date 虛擬季 offset）各自產 Candidate 並附理由；只有集號而有發佈時間時先推測那時在播的那一輪（§4.4「以發佈時間推測虛擬季」）；**篇章名 → 季號**（§4.4，比對各季 `name`）也產一個 Candidate；上下文 Media 缺時先做標題比對（正規化後與 `name` / `original_name` / alternative titles / translations 比對，年份加權） |
| `match_subtitle` | → 附掛 | brief §6.7 順序；語言由後綴（`.tc` `.cht` `.zh-Hant` `.sc` `.chs` `.jp` `.jpsc` `.jptc`，加上真實語料寫的 ISO 639-2 式 `.Cht` `.Chs` `.Jpn` `.Eng`）或資料夾決定，都缺時看 CjkHints。**不看 torrent 名**——`附官方日英简繁中字幕` 說的是這一包有四種字幕，不是這一個檔案有四種（M1 票 07 實測）。第二條規則（資料夾裡的集號）也接受**語言資料夾**（`繁體/`）：它一樣說了「這一格底下的東西是側掛字幕」 |
| `plan` | → `Plan` | 為每個影片選最佳 Candidate；產生目標路徑（§5）；衝突偵測（brief §6.4 第 5 點）；extras 與 unmatched 的處置。**brief §7.8 的「與帳本既有版本重複」不在這裡**：解析器沒有 IO，看不到既有 Entry——那個判斷在規劃那一步的 services 那一半（`services/plan._against_ledger`，M1 票 14b 起比範圍、M2 票 08 起也比 Tags），不在 importer：規劃時就知道的話，重複的那一列略過、其餘照常入庫，不必等到鏈接那一刻撞上路徑才把整筆停下來。**字幕排在影片之後**：字幕自己說不出它是第幾集，配到影片就繼承它的答案，影片沒入庫字幕就跟著 unmatched / review |
| `score` | → confidence | brief §6.5 的三級定義；批次一致性檢查在此（同模式、連續集號、數量吻合） |

**片長驗證**（M3 票 15，`parser.runtime.check_runtime`，§11.4「三道程式檢查」②）：mediainfo 量到的片長（`FileEntry.duration_s`）對 TMDB 那一集的 `runtime`（多集檔是各集相加），差超過 `max(180 秒, 15% × TMDB 片長)`（`RUNTIME_SLACK`、`RUNTIME_RATIO`）的那一列送審核（`action = review`，季集與目標路徑留著），理由 `runtime_mismatch` 帶量到的片長與 TMDB 的分鐘數，Plan 的 `review_reason` 是 `runtime_conflict`（§3.1）。抓的是分類錯誤——SP / OVA、兩集合併的檔案被當成一集正片；同一季裡算錯的集號它看不出來（每一集差不多一樣長）。**與 `classify` 的分工**（2026-09-26 使用者拍板）：短於 5 分鐘的「正片」仍由 `classify` 自動降成 extra，不送審核；片長驗證管分類器看不出來的那些。純函式、只吃 Plan Item、量到的片長與快照，所以 M5 的 AI 結果也過同一條；在 `services/plan.py` 裡與播出日比對同一個入口（`_checked`，播出日在前），排在 Route 政策之前，`_plan`、`_preplan`、`held_proposal` 都跑，`proposal`（票 13 的改正）不跑。不看來源：認領與重新入庫一樣比。缺資料不擋：TMDB 沒有那一集（或範圍裡任何一集）的片長 → 記一筆 `runtime_missing`；mediainfo 沒量到（§8.7 失敗不阻擋；pre-plan 那一輪檔案還在下載）→ 不擋也不記，否則 pre-plan 每一列都是雜訊。門檻的量測見 `scripts/experiments/runtime_gap.py`（87 集對得上的正片比例 0.94–1.03、差 −84 到 +41 秒；兩集合併檔 1.86–2.04 倍）。**已知盲點**：與正片一樣長的番外被當成正片它看不出來（量到的 One Piece 外傳就是這樣）。

### 4.2 核心型別（`domain/`）

- `FileEntry`：`rel_path`（相對於 torrent 內容根）、`size`、`kind`、`priority`、`duration_s`（mediainfo 量到的秒數，票 11）。`duration_s` **`None` 是「還沒量」不是 0**：pre-plan 那一輪檔案還在下載，一個訊號都沒有，而分類器拿它把短的正片降為 extra（§4.1、brief §6.2），片長驗證拿它比 TMDB 那一集的片長（§4.1，M3 票 15）。解析器仍然沒有 IO——量的人是 `services/plan.py`，這裡收的是它量到的結果
- `CjkHints`：`subs: frozenset[Lang]`、`hardsub: bool | None`、`subtitle_kind`、`season: int | None`、`episode: int | None`、`episode_end`、`collection`、`special: SpecialKind | None`、`movie: bool`、`group: str`、`matched: tuple[str, ...]`（認出來的原文，往上併進 `ReleaseInfo.matched_tokens`）
- `ReleaseInfo`：brief §6.3 欄位 + `raw_title`、`matched_tokens`、`part`（`Part.2` / `第二部分` 的 cour 序號，§4.4）、`air_date`（檔名寫的播出日，絕對編號換算的反證，§4.4；與 `episode_end` 一樣跟著集號走——檔名自己寫了集號時，不從 torrent 名補日期，包名上的日期說的不是這一集）。`season_hint_from_folder` **不在這裡**——資料夾提示是 `structure_hints` 的輸出，兩個階段的產物不混進同一個型別
- `Tags`：`source`、`resolution`、`subs: tuple[Lang, ...]`、`hardsub`、`group`、`version`、`edition`；`render()` 依 brief §6.8
- `StructureHints`（`parser/structure.py`）：`season`、`part`、`special`、`subtitle_folder`、`subtitle_lang`、`matched`。只讀資料夾，不讀檔名
- `Candidate`：`season`、`episode_start`、`episode_end`、`strategy`、`confidence`、`reasons: tuple[ItemReason, ...]`
- `ItemReason`（M2 票 07）：`code: ReasonCode` + `params`。**理由是封閉集合的 code 加參數，句子只在前端**（`jobs.plan.why.*`，zh-Hant / en）；參數是檔名、季集標記（`episode_label`）、日期這種不翻譯的事實。每一種 code 帶哪幾個參數寫死在 `REASON_PARAMS`，`why()` 組的那一刻核對；前端兩份語言的佔位符由 `tests/unit/test_reason_codes.py` 逐句比對。沒有叫 `count` 的參數（i18next 會把它當單複數）
- `Decision`（`parser/score.py`）：`item: PlanItem` + `strategy`。批次一致性要比的是策略，而 `PlanItem` 沒有這個欄位，所以逐檔的結果先攤成它再進 `score`
- `PlanItem`：`rel_path`、`kind`、`action`、`season`、`episode_start`、`episode_end`、`tags`、`target_path`、`confidence`、`reasons`（`ItemReason`）。`target_path` **只有真的會被寫出去的檔案有值**（`import` / `extra` / `subtitle`）——unmatched 留在 complete 原位（brief §7.4），review 還沒有決定，兩者都是空字串。`media_id` 還不在這裡：Job 一路都帶著同一個 Media，等 Plan 存進資料庫（§11.2 票 11）才有第二個來源需要它；§2.3 是它最終的樣子
- `PlanSummary`（`domain/parser.py`，票 11）：一份 Plan 的一句話（`plans.summary_json`）——會被寫進媒體庫的檔案數、逐信心的計數、逐 `PlanAction` 的計數、`review_reason`。住在 `domain/` 的理由與 `MediaSnapshot` 一樣（§2.2 的同一條偏差）：`models` 拿它當一個 `*_json` 欄位的型別、`services` 算它、`api` 直接把它送出去，而 `api` 依契約不 import `models`（§1.3）。信心只數**不是 `skip` 的那些**：字型與海報雙方都同意可以忽略，算進 high 會稀釋「這一包有多可信」
- `EDITABLE_ACTIONS`（M2 票 07）：Review Queue 上一列依分類改得成哪幾種處置——影片與特典可互換（入庫 / 特典 / 對不到 / 略過），字幕只能跟著影片或略過，光碟結構只能對不到或略過，其餘只能略過；`review` 不在任何一格裡（它是「還沒決定」）。**人改過之後重算**走 `parser.revise`（與規劃同一份 `_target_of` / `_subtitle`，已經鏈接的列路徑不動、字幕重新找影片）；核准前把待審核列升成入庫走 `parser.promote`（判準是「算得出目標路徑」）
- 封閉集合一律 `StrEnum`：`FileKind`、`Lang`、`Source`、`SubtitleKind`、`SpecialKind`（SP/OVA/OAD/Movie/NC）、`ReleaseKind`、`Confidence`、`PlanAction`、`MappingStrategy`、`PlanStatus`、`PlanEngine`、`ReviewReason`（票 11）、`ReasonCode`（M2 票 07）（explicit / folder / context / arc_name / single_season / absolute_group / absolute_cumulative / air_date_offset / cour_offset / published_run / movie）

### 4.3 上下文與 TMDB 快照

`ParseContext`：`media: MediaSnapshot | None`、`candidates: tuple[MediaSnapshot, ...]`、`season_hint`、`episode_offset`、`route_collection_type`、`published_at`（Job 的發佈時間，只有集號時推測虛擬季用，§4.4，M3 票 16）。`candidates` 是 `media` 缺席時可以比對的作品（brief §6.4 第 2 點的 RSS 與重新入庫）。**RSS 那一半沒有走這裡**（M3 票 09）：RSS Series 的作品在綁定那一刻就決定（`parser.binding.judge`，線索多了 Mikan 番組頁的名字與開播日期，而且要的是「相等 + 開播日期」而不是解析器的分數），綁好之後規劃拿到的是 `media`；`candidates` 仍然只給沒有上下文的重新入庫用——解析器沒有 IO，認得出作品的前提是呼叫端先把候選搜好遞進來；認出來時信心上限是 medium，「標題 **+ 年份**精確命中」才配得上 high（brief §6.5）。`MediaSnapshot` 是 `media.tmdb_snapshot_json` 的型別化版本，含各季集數、**各季的 `names`**（§4.4 的篇章名比對靠它）、每集 `air_date` 與 `name`、absolute 排序（若有）、標題集合。解析器不知道 TMDB API 的存在。

`SeasonSnapshot.name` 是英文季名（會進畫面），`names` 是**同一季在三輪語言下的名字**（`en-US` / `zh-TW` / `zh-CN`，去重）。要三套是因為篇章名比對的對手是真實發佈寫的那一種字：`Hashira Training Arc` / `柱訓練篇` / `柱训练篇` 指的是同一季，而簡體字幕組佔了失敗案例的多數（M1 票 06，§4.4）。多打的那一輪是 `tv/{id}` 的 `zh-CN`，只取季名，電影不打。

### 4.4 Offset 偵測與季號來源【決定】

移植 AutoBangumi `offset_detector.py` 的想法：以季內各集 `air_date` 的間隔 > 180 天切出「虛擬季」，若檔名的季/集落在某個虛擬季內，換算為 TMDB 的實際季/集，Candidate 標 `strategy = air_date_offset`、confidence 至多 medium。RSS Series 的 `episode_offset` 若有值則優先（brief §15：新 RSS Series 的第一批一律進審核，確認過之後才照信心走）。**offset 由人改正一集時算出**（M3 票 13）：人說的集號減去檔名寫的集號（`parser.written_episode`，與規劃同一個讀法——檔名說了算、torrent 名補空缺），季號就是人說的那一季；寫回 Series 之後還沒確認的集數由 `plan.proposal`（不寫、不動狀態，快照與片長用存下來的）回答該在哪一集，再走 rematch 搬過去。

**180 天這個門檻已被量測支持，不要調小**（M1 票 01，7,833 筆真實釋出）：180 天時整體換算失敗率 8.0%，改成 60 天會惡化到 9.7%。原因是一季內分割兩 cour 的間隔常常不到 180 天，門檻調小會把一季切成兩個虛擬季，季號提示就對不上了（`docs/research/anime-episode-source.md` §6.4）。

同一份量測指出，**換季集來源（TVDB aired 或 absolute）只能改善 0.4 個百分點**，brief §10 據此結案為維持 TMDB。真正的槓桿是下面兩條，兩條都不需要第二個 provider：

- **篇章名 → 季號**：九成的失敗是檔名只有篇章名沒有季號（「柱訓練篇」「最終季」「死滅迴游」「無限列車篇」）。用 `MediaSnapshot` 各季的 `names` 比對**發佈名與檔名的原文**，命中則等同季號提示，Candidate 標 `strategy = arc_name`、confidence 至多 medium。「最終季 / Final Season」對到最後一季。三條實作規則（M1 票 06）：
  - **季名要三輪語言**（§4.3）。只留英文的話，真實發佈裡最常見的簡體篇章名一個都對不到。
  - **只是季號翻譯的季名不算篇章名**（`Season 1`、`第 1 季`），**與作品標題相同的季名也不算**（Overlord 的第一季就叫 `Overlord`，每一個發佈的名字裡都有它）——兩種都不帶新資訊，卻會到處命中。
  - 多個季名同時命中時取**最長的那一個**：`Overlord II` 比 `Overlord` 說得更多。
- **`第二部分` / `Part.2` 當 cour 偏移**：唯一「檔名有季號卻還是三家一起錯」的一類（`[星空字幕组][进击的巨人 第三季 第二部分 / Shingeki no Kyojin Season 3 Part.2][01-10]`）。看到這個標記就把同一季前面幾個 cour 的長度加上去。它與字幕組的「季內連號」（第二 cour 直接從 13 接下去）是同一件事的兩種寫法，所以（M1 票 06）：
  - cour 怎麼切**與虛擬季同一條規則**（間隔 > 180 天）——它們本來就是同一件事：一季裡的兩輪播出。進擊的巨人第三季實測 12 + 10 集，中間隔 196 天。
  - 加上偏移之後超出該季時**回頭照字面讀**：那表示這一組其實是季內連號。所以「季內連號」與「每 cour 重數」兩種寫法用同一條規則就都對了。
  - 看到 cour 標記時，**照字面讀的那個候選不再產生**——不是排序問題，兩種讀法在 TMDB 裡都存在。
- **絕對編號換算**：TMDB 沒有 absolute 欄位，只能數播出序位，而 TMDB 與 TVDB 收錄的集數不一定一致（航海王 1181 vs 1177）。這條只影響 16% 的釋出、失敗率 4.4%，維持現況即可，但要標 confidence 至多 medium。**降到 low 看證據，不看 Route**（M1 票 14d，`mapping._doubts`，brief §6.4）：集號 ≤ 第一個正規季的集數（也讀得成後面某季從 01 重數），或檔名的播出日（`ReleaseInfo.air_date`；guessit 開 `date_year_first`，韓國電視台的 `150524` 才讀得成 2015-05-24）與換算出的那一集的 `air_date` 不是同一天（不容忍），兩條各自附一句理由。前一條收窄成「而且標題有認不出的多餘字」量過不成立（`docs/research/profile-effect.md` §6.1.1）。**三種換算不在同一個分支**（M1 票 06）：`absolute_group` 與 `absolute_cumulative` 是「只有集號」時的兩條路，而虛擬季換算要有一個季號才索引得到那一輪播出（`第二季` 對不到任何一季時才輪到它）。
- **以發佈時間推測虛擬季**（brief §6.4，AutoBangumi v3.2 的做法，M3 票 16，`mapping._published_run`）：字幕組每一輪播出從 01 重數，而 TMDB 把好幾輪放在同一季（或同一部作品的好幾季）時，發佈時間（`ParseContext.published_at`，即 Job 的 `published_at`，§2.3）挑得出是哪一輪，集號就照那一輪從 01 數。Candidate 標 `strategy = published_run`、confidence 至多 medium、理由 `published_in_run` 帶發佈日、全部幾輪裡的第幾輪與那一輪的第一集。它分開的是「照字面讀的那一集」與「後面某輪從 01 重數的第 N 集」——上面「集號 ≤ 第一個正規季的集數」分不開的那兩種（`docs/research/profile-effect.md` §4）。
  - **判準是「剛播」**：新的發佈發的是剛播的那一集。每一種讀法換算出的那一集（區間取最後一集）播出日落在發佈日往前 `BEHIND_LATEST`、往後 `RELEASE_TOLERANCE` 之間才算剛播，門檻與播出日比對同一組（`parser/publishing.py`）。**剛好一種讀法剛播、而它是某一輪的重數**才推測；沒有一種剛播（BD、補檔、重播、慢六週以上的字幕組）或不只一種（前一季三集就播完、第二季緊接著開播）都是分不開，照舊。只看「那一輪還在播」不夠：shincaps 在 Re:Zero 第三輪播完兩週後錄的 `- 01`（nyaa 1957100）會被讀成第三輪第 1 集，而它多半是第一季的重播。
  - **兩個入口**：沒有季號提示時（`_from_number`），候選是全部正片的季各自按 > 180 天切出的每一輪，字面讀法是「只有一季」或絕對編號換算的那幾個；第一輪的重數與字面讀法常常是同一集，剛播時一樣算數（2022 年的 `Spy x Family - 05` 因此不再被「集號 ≤ 第一季集數」送審核）。**季號來自篇章名、而那一季裡有好幾輪時**（`_restarted_within`），候選只有那一季的第二輪以後，字面讀法是「這一季第 N 集」——《死神》千年血戰篇的中文組 `千年血战篇 [08]` 對到第 2 季，TMDB 的第 2 季是四輪，照字面讀是 2022 年的 S02E08，票 16 之前以 medium 自動入錯（benchmark 語料 `bleach-tybw-kashin-tan-08-sakurato`）。只限篇章名：篇章名說的是哪一段故事，不是字幕組怎麼編號，而明說的季號（`S02E08`、`第二季`）、資料夾與 RSS Series 的季號（`context`）是照發佈或人自己的編號寫的，照字面採用（brief §6.4）；明說了分部（`Part.1` 也算）的不推測；RSS Series 的 offset 有值也不推測（人說的優先）；集號 `00` 不是任何一輪從 01 數的集數；檔名明說的播出日對不上推測出的那一集照樣降到 low（`_date_doubt`）。
  - **推測之後照樣過播出日比對，但比對幾乎擋不到它**：推測只收「剛播」的讀法，而剛播正是規則一放行的條件，所以規則一永遠不會擋；規則二（只對 RSS）只在「最近播出的一集」落在發佈後兩天內、而且比推測出的那一集晚六週以上時擋得下——一集停播六週、下一集剛好在發佈後才播的那種邊角（`tests/integration/test_air_date_check.py::TestPublishedRun` 守著「推測出的集數沒有繞過比對」）。兩者沒有互相抵銷，但也不是互相把關：推測錯了的主要防線是 medium 的 audit 旗標與 RSS Series 第一批一律審核（brief §15），不是播出日比對。
  - **已知盲點**：那一輪正在播時發的前一季舊集補檔（檔名 `- 03`、這一輪也剛播完第 3 集）會被讀成這一輪的第 3 集，驗證也看不出來；手動送單不過規則二。兩者都是 medium，入庫時帶 audit 旗標。
- **季名的寫法是一份規則**（M4 票 14，`parser.seasons`）：`第N季 / 第N期`、`Season N / Season.N / SN`、`Nth Season` 與中文數字表。解析器從發佈名撈季號（`cjk`）、讀資料夾名（`structure`，整個資料夾名就是它才算）、自動綁定把季名從搜尋詞與比對的線索裡拆掉（`binding`）都讀它——TMDB 的作品名不帶季名。**自動綁定讀季號與規劃同一個讀法**（`mapping.season_airing`）：TMDB 有那一季就是那一季，沒有時是依 > 180 天間隔切出的第 N 輪（虛擬季，同 `_virtual`）；比的是那一季**播出的期間**（任何一集前後 14 天），不只首播，因為 Mikan 把一季的第二個 cour 另開番組、寫它自己的開播日（brief §15「綁定」、§20.12）。羅馬數字（`II`、`Ⅲ`）與 `第N部分` / `Part N` 不在這份裡：前者只在解析器那一頭有用（「`Mushoku Tensei III`」與「`S3`」要對得起來），後者是 cour 不是季。
- **數量明顯不符就交給人**（brief §6.5 的 low，M1 票 06）：一季十二集卻對出二十個檔案時，是哪一個檔案讀錯了看不出來，所以整季一起進 review 而不是挑一個代罪的。
- **播出日比對**（M3 票 14，`parser.airing.check_airing`，§11.4「三道程式檢查」①）：規則層有把握卻算錯的集數，拿 Job 的 `published_at`（§2.3）對換算出的那一集的 TMDB 播出日。純函式、只吃 Plan Item、快照與一個發佈時間，所以 M5 的 AI 結果也過同一條；在 `services/plan.py` 裡排在 Route 政策之前，`_plan`、`_preplan` 都跑，`proposal`（票 13 的改正）不跑——那是人說的季集。
  - **規則一**：發佈日早於那一集（範圍取最後一集）的播出日**超過兩天**就送審核，理由 `released_before_airing` 帶兩個日期。兩天是 TMDB 的當地日期對 UTC 的發佈時間、深夜檔跨日的容忍（`RELEASE_TOLERANCE`）。手動送單與 RSS 都套。
  - **規則二**：只對 RSS Series、只對正片的季（S00 不照播出順序）。「發佈當時最近播出的一集」＝播出日不晚於發佈日加兩天的最後一集；對到的那一集比它早**超過 `BEHIND_LATEST`**、**而且**它離發佈不超過 `BEHIND_LATEST`（作品在發佈時還在連載）就送審核，理由 `behind_latest_episode` 帶兩組集與日期。第二個條件讓播完很久之後的 BD、補檔不被擋；第一個條件讓慢幾週的字幕組不被擋。門檻的量測見 `scripts/experiments/air_date_lag.py`。
  - 被擋的那一列 `action = review`，**季集與目標路徑留著**：BD 版晚幾個月才發這種對的也會落在這裡，核准就照畫面上的位置入庫（`parser.promote`）。Plan 的 `review_reason` 是 `air_date_conflict`（§3.1）。
  - 缺資料不擋、記一筆：發佈時間是 `None` → `published_missing`；TMDB 沒有那一集的播出日 → `air_date_missing`。**沒有來源的 Job 不比**（認領 `unknown_torrent`、從 complete 目錄重新入庫的那一種，`source_url` 是空的）：逐列記「來源沒給」只是雜訊。既有 Job 的 `POST /jobs/{hash}/reimport` 留著來源，所以**照樣再比一次**——與拒絕之後重算同一個取向：上一次核准過的（BD 晚發）要再核准一次，Berth 不記「這一集的日期已經有人看過」。
  - **抓不到反方向**：新一季被當成第一季時換算出的是早就播過的集數，發佈晚於它是正常的——所以它不是「只有一季 → 第一季」升 high 的前提（§11.4 ①的「待議」）。

### 4.5 AI 解析（M5 的第一種 AI 任務）

介面在 M1 就定好：`AiPlanner.propose(context, files, rules_plan) -> Plan | None`（`adapters/ai.py`），M1 的實作是 `NullAiPlanner`，**至今沒有呼叫端**。2026-09-24 起它不再是 `services/plan.py` 裡同步呼叫、結果一律進 review 的 fallback，而是 M5 的 AI 任務「規則層 low 的 Plan」的核心（brief §6.10、§11.6）：planner 判出 low 時開任務，`ai_worker` 叫 `propose`，驗證通過後依任務模式（影子 / 自動）記錄或套用。輸入壓縮（同模式檔案只送樣本 + 數量）、schema 驗證、快取鍵、預算檢查與 provider 無關，住在 services。M3 準備度評估（2026-09-24）點出的缺口開工時要補：`propose` 要能把 tokens 與費用交回給 Event 記帳；理由除了封閉的 `ReasonCode` 還要一欄自由文字；「猜作品」是另一個方法（`PlanItem` 沒有 `media_id`）。

### 4.6 Benchmark【決定】

fixture 一筆一個 JSON：

```json
{
  "id": "anime/frieren-7acg-bd-batch",
  "source_url": "https://share.dmhy.org/topics/view/...",
  "torrent_name": "[7³ACG] 葬送的芙莉莲/Sousou no Frieren S01 | 01-28+SPx11 [简繁字幕] BDrip 1080p x265 OPUS 2.0",
  "files": [{ "path": "Sousou no Frieren 2023 S01E01-[1080p][BDRIP][x265.OPUS].mkv", "size": 1234567890 }],
  "context": { "media": "tv:209867", "season_hint": null, "episode_offset": null },
  "tmdb": "tv-209867",
  "expected": [
    { "path": "Sousou no Frieren 2023 S01E01-[1080p][BDRIP][x265.OPUS].mkv",
      "kind": "video", "action": "import", "season": 1, "episode": 1,
      "tags": { "source": "BD", "resolution": "1080p", "subs": ["CHS", "CHT"], "group": "7³ACG" },
      "min_confidence": "high" }
  ]
}
```

- `torrent_name` 是**索引站上的發佈標題**（Berth 從搜尋結果拿到的那一個），`files[].path` 是**相對於 torrent 內容根**的路徑。兩者各知道一半：CJK 的字幕語言與季號幾乎只寫在前者，集號只寫在後者（M1 票 05 實測）。
- `expected` 逐檔一筆，含 `kind`（brief §6.2 的分類）——分類是第一層，錯在這裡後面每一層都白算。`tags` 缺席表示這一筆不比對 tag。`target` 是相對於 Route 目標的目標路徑（§5）：`import` / `extra` / `subtitle` 三種處置**一定要寫**，其餘一定是空的，兩種都比（M1 票 07）——季集對了但檔名錯了，Jellyfin 那一端還是入錯，而多版本的判定、繁簡的分辨與多集檔的表示法全都只寫在檔名裡。`min_confidence` **不參與比對**：信心低於期望不是做錯事，那件事由 `review` 與 high / medium 誤判率回答。
- `tests/fixtures/tmdb/<id>.json` 是 TMDB 快照，錄一次即凍結（`scripts/record_tmdb_snapshots.py`）。
- `berth bench` 輸出：整體與分類別（anime / tv / movie）的 `auto_correct`、`auto_wrong`（自動處置但錯，最嚴重）、`review`、`unmatched_correct`、`extra_correct`、`subtitle_correct`，加上 `missed`（該入庫的被丟成 unmatched / skip）與 `skipped`（雙方都同意可忽略）；**八個桶互斥且窮盡，加起來等於檔案數**——加不起來的報表會讓沒被數到的檔案看起來不存在。`subtitle_correct` 與 `extra_correct` 同一個道理（M1 票 07）：外掛字幕也是自動搬進媒體庫的檔案，混進 `auto_correct` 會讓「入對幾集」這個數字說不清楚。另列分類正確率、tag 正確率與**信心達標率**（語料寫的 `min_confidence` 有沒有達到；不達標不是做錯事，但它說得出「本來該自動入庫的少了幾個」），以及 high 與 medium 的錯誤率（brief §6.5）。
- CI 規則：`auto_wrong` 不得高於 `tests/fixtures/parser/baseline.json`，`auto_correct`、`extra_correct`、`subtitle_correct` 三格都不得低於 baseline 減 1 筆；改善時更新 baseline 並在 PR 說明。三格都要守是因為**字幕或 extras 整批掉出來時 `auto_wrong` 一格都不會動**（M1 票 07），只守兩個數字的話那種退步在 CI 上看不見。門檻與報表是同一支（`services/bench.py`），單元測試與 `berth bench` 共用，所以 CI 不另開 job。
- v0 語料：20 筆，來源 brief §20.4 的樣本清單（動漫 8、非動漫劇集 8、電影 4）；票 06 補三筆動漫（篇章名、cour 偏移、單檔多集），共 23 筆；票 14c 補五筆「只有集號、TMDB 上多季」（動漫 3、非動漫 2，§4.4 絕對編號換算那一支第一次有語料走到），共 28 筆；票 14d 補兩筆動漫（集號 ≤ 第一季集數的兩個方向），共 30 筆；票 14f 補兩筆動漫（季號剛好等於方括號集號，TMDB 一季與多季各一），共 32 筆，逐步擴到 100+。出處與涵蓋範圍逐筆記在 `tests/fixtures/parser/README.md`。

---

## 5. 命名引擎

`naming/` 是純函式，輸入 `MediaSnapshot`、`Tags`、季集、副檔名，輸出相對於 Route 目標路徑的相對路徑。模板固定在程式碼裡，第一階段不做使用者模板。

| 目標 | 模板 |
| --- | --- |
| 作品資料夾 | `{title} ({year}) [tmdbid-{id}]` |
| 季資料夾 | `Season {season:02d}` |
| 劇集檔 | `{title} ({year}) - S{s:02d}E{e:02d}[-E{e2:02d}][ - {episode_title}][ {tags}].{ext}` |
| 電影檔 | `{title} ({year}) [tmdbid-{id}][ - {tags}].{ext}`（無 tags 時檔名等於資料夾名；` - ` 之前**必須**與資料夾名一字不差，否則 Jellyfin 會當成兩部片） |
| 外掛字幕 | `{影片檔名主幹}.{SUBTOKEN}[.default].{lang}.{ext}`（旗標在語言碼**之前**：實測的是 `.CHT.default.zh.ass`，brief §20.1 的官方格式也是 `<flags>.<language>`。M1 沒有人決定得了哪一軌是預設，所以那一段不產生——等有字幕語言偏好設定的那一票再加） |
| Extras | `{作品資料夾}/extras/{原檔名}` |

- `title` 依 brief §7.5；`folder_name` 一旦寫進 `media` 就只從那裡讀。**標題自己帶著同一個年份時不再接一次**（`GTO (2026)` 不寫成 `GTO (2026) (2026)`，語料 `tv/gto-2026-magicstar`）；年份不同的兩個數字說的是兩件事（`Show (1999)` 的 2020 重製版），照樣兩個都留。
- 側掛字幕是**唯一可以超過 200 位元組**的檔名：它靠影片的完整主幹配對，截短它換來的是一個掛不上去的字幕；多出來的語言段最多 22 位元組，仍遠低於 ext4 的 255。
- `SUBTOKEN` 只在中文才出現：Jellyfin 沒有一個分得出繁簡而且 10.10 與 10.11 都認得的語言碼（§20.6），所以中文一律 `zh` 加自由文字 `CHT` / `CHS`，日文與英文直接用 `ja` / `en`。語言說不出來時整段省略，字幕仍然掛在影片旁邊。
- `episode_title` 來自快照；缺、空、或符合 `^Episode \d+$` 即省略；長度上限 80 字元。
- `sanitize`：移除 `/ \ : * ? " < > |` 與控制字元，連續空白合一，去尾端 `.` 與空白，整體 ≤ 200 bytes（UTF-8）。**逐段套用**（資料夾、季資料夾、檔名各一次），而且檔名的上限先扣掉副檔名——截到一半的 `.mk` 不是影片檔，Jellyfin 連掃都不會掃它。
- `Tags.render()`：brief §6.8 的順序與 token；缺欄位直接省略；`subs` 依 `CHS < CHT < JP < EN` 排序後以 `+` 連接。
- **模板已凍結**（2026-09-07，M0 票 04 的實驗，brief §20.6 / §20.7）。實測確認：方括號與 `+` 不會滲進 Jellyfin 的 Series 或 Episode 名稱；電影檔名含 `[tmdbid-{id}]` 才會被當成同一部片的多版本（brief §7.2 的舊範例是錯的）；`{SUBTOKEN}.{lang}` 用 `CHT.zh` / `CHS.zh` 在 10.10 與 10.11 都分得出繁簡，`zh-Hant` 只有 10.11 認得所以不用。之後要改模板只改 `naming/`，不影響其他模組。

---

## 6. API 面

REST + JSON，前綴 `/api`。門禁是 middleware（`api/gate.py`）而不是逐個 router 的相依，所以**預設拒絕**：新增端點什麼都不做就已經在門後。白名單只有三條——`auth/login`、`auth/logout`（一律成功，順便清 cookie）、`health`。未知路徑也走同一道門，匿名時回 401 而不是 404。

`setup/*` 有自己的規則（也在門禁）：精靈未完成時整組匿名開放（那時候還沒有人登入得了），完成之後只有 `role=admin` 進得來（非 admin 回 403）。**精靈跑完之後 `setup/*` 就是設定頁的寫入端點**（票 06i，shape 時拍板）：設定的 Jellyfin / qBittorrent / 索引站 / TMDB 那幾頁呼叫的是精靈的同一批命令與端點（命令冪等），不在 `settings/*` 底下另開一份——services 命令只有一份，API 也只有一份。`settings/*`、`routes/*` 與 `jellyfin/libraries` **永遠只有 admin**；M2 起 **`review/*`、`issues/*`、`files/*`、`reconcile`、`DELETE /jobs/{hash}` 與 `POST /jobs/{hash}/reimport` 也是**（2026-09-22 使用者拍板，與 brief §11、`PRODUCT.md` 一致：審核、修正、刪除都是 admin 的事；`user` 送單之後碰到低信心 Plan 只能等 admin，畫面上要說得出「等管理員審核」）。**門禁認得方法**（M2 票 04）：`ADMIN_PREFIXES` 說的是「這整塊是 admin」（`settings/*`、`routes/*`、`jellyfin/libraries`，所有方法），`ADMIN_ROUTES` 說的是「**這一個動詞**在這條路徑上是 admin，它的兄弟不是」——`(方法, 路徑樣式)`，樣式裡的 `*` 配一段，所以 `DELETE /jobs/*` 配得上而 `POST /jobs` 配不上（`user` 要送得了單）。`GET /jobs/*/deletion`（刪除估算）與刪除同一條規則：按不到刪除的人不必替他逐一 `stat` 每一個檔案。兩份都在 `api/gate.py` 一處。`routes` 在票 14 曾跟著 `setup/*` 匿名開放，票 14a 收回：停用的 Route 不算進完成條件，匿名開放等於讓精靈跑完之前的任何人把紅燈 Route 停用、再按完成。精靈第 5 步只需要刪除，它走自己的 `DELETE /setup/routes/{id}`。

`health` 匿名可讀，回 `status`（ok / degraded）、`version` 與 `setup_completed`。**最後那一個位元掛在這裡而不是 `setup/status`**：前端要在還沒有人登入時就決定該畫精靈還是登入頁，而精靈未完成時本來就整組匿名開放，所以它不多洩漏任何東西。

Session 以 httpOnly cookie（`berth_session`）承載，`SameSite=Strict`、`Path=/`；刻意不設 `Secure`，自架幾乎都是區網的純 HTTP 位址，HTTPS 交給前置代理。非 GET 請求要求 `X-Requested-With` 標頭作 CSRF 防線（跨站表單送得出 POST，送不出自訂標頭）。

| 群組 | 端點 | 對應命令 |
| --- | --- | --- |
| auth | `POST /auth/login`（Jellyfin 帳密 → 發 session；帳密錯與帳號不存在回同一個 401，Jellyfin 連不上回 503；**擁有者成立之前一律 403**、帳密不交給任何一台，M4 票 28）、`POST /auth/logout`（204，一律成功）、`GET /auth/me`（`name`、`role`） | `auth.*` |
| setup | `GET /setup/status`（頁、擁有者、每個服務的選擇與最後一次測試、套件內三台的 compose 位址 `bundled_targets`）、`GET /setup/compose`（套件內三個主機名解不解得到 `resolvable`：只查 DNS，M4 票 30）、`POST /setup/owner`（頁 1：成立擁有者並發 session；必帶畫面上測過的 `base_url` 與 `server_id`，與存下的不同是 409 `target_changed`，M4 票 28）、`POST /setup/services/{kind}`（服務頁的二選一：`origin` 加既有服務的位址與憑證，存下並測一次；換了一台就清掉那一頁的結果（`_start_over`）；擁有者成立之後改 Jellyfin 的來源是 409，M4 票 15。**頁 4 選既有 Prowlarr 也是這一支**，`choices` 只有這一條寫入路徑——原本頁 4 自己的 `POST /setup/indexers/connect` 不經過換台的清理，M4 票 39 刪了）、`POST /setup/services/{kind}/test`（用存下的選擇重測：紅燈上的「重新測試」帶 `restart`，套件內還在啟動時的輪詢不帶；還沒選是 422）、`GET /setup/services/{kind}/leftovers`（換 qBittorrent / Prowlarr 的確認框：Berth 在現在這一台擁有的物件——`berth-*` 分類與 torrent 數、Berth 加的站、Berth 設的介面登入；連不到時 `reachable: false`、列 Berth 記得的；Jellyfin 422，M4 票 47）、`DELETE /setup/services/qbittorrent/leftovers/categories`（只移除空的 `berth-*` 分類，按下時重數，回移除之後的清單，M4 票 47）、`GET /setup/jellyfin`（不連線，回上一輪的七步狀態、媒體庫，以及版本閘門的 `version` / `version_supported`；bootstrap 進行中前端輪詢它看進度）、`POST /setup/jellyfin/bootstrap`（頁 3 套件內的媒體庫；選了既有是 422）、`POST /setup/jellyfin/connect`（既有：以管理員帳密換 API key）、`POST /setup/jellyfin/libraries/paths`（**沒有 `/setup/jellyfin/plugin`**：票 14b 起只支援 Jellyfin 12，不裝任何插件）、`GET /setup/qbittorrent/diff`（現查，回逐鍵差異）、`POST /setup/qbittorrent/apply`（`login` 是頁上填的 WebUI 登入，M4 票 07；`login.reuse_owner` 是「沿用 Jellyfin 帳密」，Jellyfin 驗不過是 422 `owner_password`、連不上是 502 `jellyfin_unreachable`，都在寫任何東西之前，M4 票 15）、`PUT /setup/qbittorrent/login`（設定頁只換套件內那一台的 WebUI 登入，同一組拒絕）、`GET /setup/indexers`（只讀：Prowlarr 裡已有的站 `sites`、套件內還沒加入而 Berth 加得了的站 `candidates`（推薦清單與其他公開的 torrent 站）、上一次加入的逐站結論 `checks`、套件內 Prowlarr 在宿主上的 `web_port`，M4 票 09）、`POST /setup/indexers/test`（「測試」：`indexer/test` 測還沒加入的定義，什麼都不建立，逐站回 `checks`（理由 `SiteFailure`）；只讀但由人按，既有 422，M4 票 09）、`POST /setup/indexers/apply`（勾起來的站逐站加，套件內與既有 Prowlarr 都收；不帶介面登入，M4 票 20）、`PUT /setup/indexers/login`（精靈與設定頁的套件內 Prowlarr 介面登入，自己的一顆按鈕）、`POST /setup/indexers/skip`、`GET /setup/indexers/search?query=&indexer_id=`（試搜：逐站筆數與前三筆標題，只讀，票 06e；`indexer_id` 只問那一站，M4 票 09）、`DELETE /setup/indexers/{id}`（從套件內的 Prowlarr 移除一站：只移除 Berth 加得回去的站；既有與私站 422，票 06e、M4 票 09）、`GET /setup/tmdb`、`POST /setup/tmdb/test`（憑證使用者自備、必填，所以**沒有 skip**）、`GET /setup/routes`（媒體庫清單與已建的 Route，含上一輪逐項檢查）、`POST /setup/routes`（套件內替清單上的媒體庫導出，M4 票 24；既有用勾選，目標必須是該媒體庫回報的路徑之一；這一步順便重跑每一條既有 Route 的檢查，所以途中被另一個分頁刪掉的那一條也是 404 `route_missing`，與 `routes/*` 同一種拒絕，M2 票 01；選擇本身不成立是 422 帶理由——`library_missing`、`library_unsupported`、`target_not_in_library`，以及套件內清單上的媒體庫在 Jellyfin 上沒有資料夾的 `library_without_path`，M4 票 31）、`DELETE /setup/routes/{id}`（頁 3 每條 Route 底下的刪除：與 `DELETE /routes/{id}` 同一個命令、同一種拒絕，只是跟著 `setup/*` 的門禁；204 / 404 `route_missing` / 409 `route_in_use`，票 14a）、`POST /setup/complete`（照〈續行與跳過〉的頁序把每一頁再問一次，全部成立才寫得下 `settings.setup.completed`，否則 422 說最前面那一頁，M4 票 31） | `setup.*`（§9） |
| settings | `GET /settings/services`（三個服務的連線資訊與最後健康狀態，形狀與 `health/detail` 相同）、`POST /settings/services/{kind}/test`（只重測這一個服務）、`GET|POST /settings/jellyfin`（Jellyfin 對外網址與它沒填時推導出來的主機；不是 http(s) 的位址回 422，票 13）、`GET|POST /settings/disk`（磁碟空間門檻 `min_free_gb`，0 以上的整數，存完立刻重量一次、`/issues` 當場是新的答案；M2 票 09c）。**整組只有 `role=admin` 進得來**（規則在門禁，不在 router 的相依）。這一組只放不屬於精靈的東西；位址、憑證、索引站、TMDB key 在設定頁上改但走 `setup/*`（票 06i），所以不做 `PUT /settings/{group}` | `health.*` |
| routes | `GET /routes`（全部 Route 與引用數 `jobs`、`ledger_entries`，不連線）、`POST /routes`（`{library_id, target_path, name}`；媒體庫與路徑向 Jellyfin 現查，目標必須是它回報的路徑之一且還沒有 Route；檢查紅燈照樣建立、維持停用；同一時間的建立撞上唯一索引回 409 `route_conflict`）、`PUT /routes/{id}`（只改 `name`、`enabled`，一律重跑檢查；從停用到啟用而檢查是紅的回 409 `route_unhealthy`）、`DELETE /routes/{id}`（被 Job 或帳本引用回 409 `route_in_use`，detail 另帶 `jobs`、`ledger_entries`）、`POST /routes/{id}/check`（重跑這一條，不動啟用）、`POST /routes/check`（全部重新檢查：每一條都跑、探針也問，回整份 Route；換了一台 qBittorrent 之後設定頁自動送一次，進度靠輪詢 `GET /routes`，M4 票 59）、`GET /jellyfin/libraries`（現查，每個媒體庫的路徑是 `paths[{path, route_name}]`，已經有 Route 的帶 Route 名，沒有的是 `null`）。拒絕一律是 `{reason, detail}`，Jellyfin 連不上回 503；檢查途中 Route 被刪掉是 404 `route_missing`（票 14、14a）。「先讀再寫」的命令（刪除算引用數、建立看目標佔用）在同一把 SQLite 寫鎖裡做完，鎖內不打網路 | `routes.*` |
| discover | `GET /discover/trending`、`GET /discover/popular`、`GET /discover/search?q=`（三支回同一個形狀：`items` + `problem` + `detail`）。**拿不到 TMDB 時仍是 200**，理由寫在 `problem`（`credential_missing` / `credential_rejected` / `unreachable`）——一頁上有三個 feed，一個垮掉時另外兩個要照樣畫得出來，而畫面要說得出下一步（票 03） | `discover.*` |
| inventory | `GET /inventory`（切換列：這位使用者 `UserViews` 裡的電影與劇集媒體庫，照他在 Jellyfin 排的順序，只有 id、名稱、類型與排序選單 `sorts`（照 jellyfin-web，劇集庫與電影庫不同），以及 `has_imports`（帳本至少一列落在指向它的 Route 底下，更深的 Route 底下的歸那一條；登入後落在哪一頁讀它，M4 票 10），不問 Jellyfin 的牆）、`GET /inventory/{library_id}/filters`（類型與年份篩選的選項，Jellyfin `/Items/Filters`，同樣先驗媒體庫）、`GET /inventory/{library_id}?page=&sort=&order=&genres=&years=&q=`（一個 Jellyfin 媒體庫的一頁牆：Jellyfin 的作品 50 部一頁（M2 票 13 從 jellyfin-web 的 100 減半：100 格的牆量到 1,700 個 DOM 節點、222 個 Tab 停留點），排序鍵要在這個媒體庫的 `sorts` 上（否則 422 `sort_not_offered`），`genres` 與 `years` 重複帶、同一種之間是「或」兩種之間是「且」，`q` 是名字裡的一段（Jellyfin 的 `searchTerm`，前後空白不算、上限 200 字，M2 票 14），排序、篩選與名字只套在 Jellyfin 那一頁（M1.5 票 06）；`total`、「待審」「對不到」兩個篩選鍵的數字（**審核佇列在這個媒體庫上的 `plan` 與 `unmatched` 各幾件**，與 `GET /review?library=` 同一支查詢；M2 票 14 使用者拍板數件不數部，原本數的是 `tracked` 裡旗標成立的部數；兩個篩選只給 admin，其餘角色回 0 也不數），每一格帶 `media_id`（沒有 TMDB id 時空字串）、Jellyfin 的名稱、`poster_url`（在 Jellyfin 裡的是上面 `jellyfin` 那一支的網址，還沒進的是 TMDB 海報，票 04）、`tracking`（Berth 經手時的入庫狀態，否則 `null`）、`watch`（這位使用者看到哪了：`played` / `progress` / `unplayed_episodes`，判定照 jellyfin-web 的卡片，`services/watch.py`；只有 Jellyfin 那一頁的卡片有，M1.5 票 05）；另帶 `tracked`＝這個媒體庫上 Berth 經手的每一部，不分頁，「還沒進 Jellyfin」那一條從這裡取；加上深連結的主機）。**權限在 `services/jellyfin_access.py` 一處**（M1.5 票 03，§11.2b）：Jellyfin 的使用者 id 只從 session 來；媒體庫 id 對 `UserViews` 驗過才會變成 `parentId`；允許清單與 `Policy` 共用 60 秒快取；帳號停用或刪除（刪除認 `Users/{id}` 的 404，M2 票 11）就刪掉他的每一張 session。拒絕是 `{reason, detail}`：401 `account_disabled`（停用或刪除）、404 `library_not_visible`（沒有權限與不存在同一個回應）、422 `sort_not_offered`（排序鍵不在這種媒體庫的選單上，票 06；前端照 `sorts` 畫選單，只有手改的網址會走到）、503 `jellyfin_unreachable`。`GET /inventory/{library_id}/watching`（這個媒體庫的繼續觀看（`/UserItems/Resume?mediaTypes=Video`，12 項）與下一集（`/Shows/NextUp?enableResumable=false&nextUpDateCutoff=<一年前>`，24 項），參數照 jellyfin-web 首頁；媒體庫先驗過允許清單才變成 `parentId`，M1.5 票 07。回 `jellyfin`（深連結的主機）、`resume`、`next_up`，每一格是一集或一部電影（其餘型別丟掉）：`item_id`（深連結要開的那一集）、`kind`、Jellyfin 的作品名與集名、季集、電影的年份、`progress`（看到幾 %，看過又重看的片也有）、`image_url`（16:9，照 jellyfin-web 橫卡的順序取圖，`services/watching.landscape`；沒有合用的圖是空字串）。拒絕：401 `account_disabled`、503 `jellyfin_unreachable`）。**叫 inventory 不叫 library**：`CONTEXT.md` 裡程式碼的 `library` 一律指 Jellyfin 那一端（票 13）；判定規則全部在後端 | `inventory.*`、`jellyfin_access`、`watching` |
| jellyfin | `GET /jellyfin/items/{item_id}/images/{image_type}?size=&tag=`（M1.5 票 04）：Jellyfin 的圖由 Berth 代理，瀏覽器不必連得到 Jellyfin，HTTPS 的 Berth 配 HTTP 的 Jellyfin 也沒有 mixed content（brief §19）。路徑與 `tag` 沿用 Jellyfin 的 `/Items/{id}/Images/{type}?tag=`，尺寸是具名規格（TMDB `w342` 那種），**白名單**：`image_type` 有 `Primary`、`Thumb`、`Backdrop`，`size` 有 `poster`（2:3、`fillWidth=342&fillHeight=513`，與 TMDB `w342` 同寬）與 `wide`（16:9、342×192，繼續觀看與下一集，票 07；Media 詳情的集劇照是 `Primary` 配 `wide`，票 08），以及各自兩倍寬的 `poster_large`（684×1026）與 `wide_large`（684×384）——卡片上的網址是小的那一張，前端的 `srcset` 換 `size` 給瀏覽器挑（M2 票 13）；`item_id` 與 `tag` 都要是 32 位小寫十六進位（item id 會進 Jellyfin 的路徑）。其餘 422、不轉發。**要登入，但不逐張檢查可見性**（Jellyfin 的圖本身匿名可取）；向 Jellyfin 取圖不帶 API key。200 另帶 `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; sandbox` 與 `nosniff`：圖是 Jellyfin 那一端的內容卻從 Berth 的網域送出，直接開一張 SVG 不能帶著 Berth 的 session 跑 script。拒絕：404 `image_missing`、503 `jellyfin_unreachable`。卡片的網址由 API 那一層組（`api/jellyfin.image_url`），一定帶 DTO 的 `ImageTags`。Berth 端不另存圖（量測見研究 library-browsing.md §6.1）。`POST` / `DELETE /jellyfin/items/{item_id}/played`（M1.5 票 05）：標為已看 / 未看，寫進 session 那個人在 Jellyfin 的紀錄（`UserPlayedItems`），回寫入之後的 `WatchStateOut`，前端拿它就地改牆上那一格。動詞成對沿用 Jellyfin，使用者不在網址上；`item_id` 同樣要是 32 位十六進位。**可見性由 Jellyfin 自己查**（看不到的回 404 而且沒有寫入，研究 §5），Berth 照實轉成拒絕；停用的帳號由閘門先擋。標為未看清掉觀看次數與時間、劇集遞迴到每一集，確認在畫面上。拒絕同 inventory：401 `account_disabled`、404 `item_not_visible`、503 `jellyfin_unreachable`。`GET /jellyfin/watching`（M1.5 票 07）已於 2026-09-25 移除（M3 票 06：探索頁只放 TMDB 牆，繼續觀看與下一集只留媒體庫頁的 `GET /inventory/{library_id}/watching`，見 inventory 那一列）。`GET /jellyfin/shows/{series_id}/episodes?season_id=`（M1.5 票 08）：Media 詳情觀看區的一季，路徑照 Jellyfin 的 `/Shows/{id}/Episodes?seasonId=`；兩個 id 都要是 32 位十六進位。**劇與季的可見性由 Jellyfin 查**（帶 session 那個人的 `userId`，看不到回 404，研究 §2），回 `WatchEpisodeOut[]`：`item_id`、Jellyfin 的集名、季集、`watch`、`still_url`（集自己的 `Primary`，沒有是空字串，不借劇的圖）。拒絕：401 `account_disabled`、404 `item_not_visible`、503 `jellyfin_unreachable`。標記已看的確認規則在畫面上：標為未看、看到一半的標為已看、整部劇標為已看先確認（票 08 使用者拍板） | `jellyfin_images`、`jellyfin_access.mark_played`、`watching`、`watch_area` |
| media | `GET /media/{id}`（TMDB + 收得下它的 Route + 狀態 + 檔案 + Unmatched + 版本；票 13 起集表每一集帶 `status`：已入庫 / 卡住 / 下載中 / 缺 / 未播出，依序取；M4 票 12 起卡住與下載中的那一集另帶 `job`＝蓋到它的那一筆的 hash，兩筆蓋到時是最新送的那一筆，季表的標籤連到 `/jobs/{hash}`）、`POST /media/{id}/refresh`、`POST /media/{id}/resolve`（M4 票 51：作品頁打開時、有檔案還在等 Jellyfin 才送，回同一份詳情；`resolver.resolve_early` 替這部作品還在排反查的帳本先問一次，見 §3.2）。**沒有 track 那一支**（票 04b）：入庫到哪一條 Route 是送單時才帶上的偏好（票 14e 起搜尋不帶它），不為一個下拉的初值多一個對外介面。`GET /media/{id}/watch`（M1.5 票 08）：觀看區——作品在 Jellyfin 裡、session 那個人看得到時回 `item_id`、`kind`、`watch`、`carry_on`（這部劇接下來看哪一集：Jellyfin 的 NextUp 帶 `seriesId`，看到一半的、沒看過的第一集都算，看完了或電影是 `null`）、`seasons`（Jellyfin 的季）與深連結的主機；**不在或看不到時是 `null`**，兩者不分。找作品不帶 `parentId`（`/Items?hasTmdbId=true`，照帳本的 Series / Movie id 或 TMDB id 比），再以 `/Items/{id}?userId=` 確認看得到，**這部劇的 NextUp只在確認之後才問**（帶 `seriesId` 不套權限，研究 §2）——三件都在 `services/jellyfin_access.py`。`GET /media/{id}` 那一份永遠不帶 Jellyfin 的任何東西。拒絕：401 `account_disabled`、503 `jellyfin_unreachable` | `media.*`、`watch_area` |
| search | `GET /search?media=&q=&missing=&season=&from_season=`（索引站搜尋，結果附解析出的 Tags、預估季集與索引站報的發佈時間 `published_at`——結果表的「發佈」欄，送單時存進 Job 的是伺服器跟著 `source_id` 記下的那一份，M3 票 14；**每一列沒有下載連結，只有送單用的 `source_id`**（M4 票 79：Prowlarr 的代理連結帶著它的 API key，而 `/search` 一般使用者也打得到，連結記在伺服器上）；**每一筆帶歸到的那一類（`verdict`）與證據（`evidence`），每一類各取一份送出、`counts` 報每類每站的總數**（M4 票 83，§8.4）；**筆數加得起來**（M4 票 69、83）：`returned`（每個查詢回的筆數加總）＝`merged`（合併掉的重複）＋Σ`counts.total`，畫面照這一條說）、`GET /search/queries?media=&missing=&season=&from_season=`（按下搜尋之前先給看：會拿哪幾個名字去問。不打索引站，只讀快照與這部作品的入庫狀態；規則只能有一份實作，前端不重算。另帶 `problem`：只有 `not_configured`——不必問索引站就知道的那一種，按下去之前就說；連不上、憑證錯要按下去才知道，M2 票 13）。**兩支都不帶 Route**（票 14e）：入庫到哪一條是送單時的事，查詢只由快照與缺的季集決定。`missing=true` 是**缺集一鍵搜**（M1.5 票 10）：查詢改由季表上缺的那幾集產生（`missing_queries`，規則見 §8.4），`season=` 再收到那一季；兩支收同一組參數，所以預覽與真的送出去的那幾個永遠是同一份。缺的集是零時回空的查詢（搜尋因此是 `no_query`）——**不退回作品名**，使用者按的是「搜缺的集」。`season` 單獨帶著是 422 `season_without_missing`；搜尋只有關鍵字一種問法（M4 票 37 起 tmdbid 那條路隨 Torznab 拿掉）。M3 票 20：季記號放不下一批時**分批**，兩支都回 `batch`（`seasons`＝這一批問哪幾季、`later`＝之後還有幾批、`next_seasons`，搜尋另帶 `next_at`＝請求預算放得下下一批的時刻）。**下一批以季定位**：`from_season=<next_seasons[0]>`，照那一刻的季表從那一季起重切——以序號定位的話，問完第一批、送了幾季之後季表就變了，第二批會落到別的季（code review 抓到）；`from_season` 單獨帶著是 422 `from_season_without_missing`。**問之前先在請求預算裡佔位**（§3.2）：放不下的站這次不問，列在 `skipped`（`site`、`indexers`、`until`；M4 票 77）；每一站都放不下是 200 + `problem = budget_exhausted` 與 `retry_at`（最早有一站放得下的時刻），一個查詢都沒問 | `search_torrents`、`plan_queries`、`missing_batches` |
| jobs | `POST /jobs`（`{source_id, media, route}`；**`source_id` 是搜尋結果或一次性連結那一列的 id，不是網址**（M4 票 79）：下載連結、發佈名、info hash、發佈時間、大小記在伺服器上（`services/sources.SourceCache`，程序內、兩小時，照 Sonarr interactive search 的快取），換不回來是 404 `source_expired`（過期、Berth 重啟過、不認得都是它，下一步是再搜一次）；發佈時間存進 `jobs.published_at` 比播出日，M3 票 14）、`GET /jobs?filter=&page=&media=`（一頁 50，最新在前；`filter` 是 `JobFilter`：`active` 預設＝還沒入庫也沒被移走、`attention`＝需要人的六個狀態、`imported`、`all`，以及 `open`＝`active` 加上已入庫而計劃還有 audit 掛著的（作品頁「下載」段的預設，`/jobs` 的篩選列不畫它；它不是純狀態的一組，所以不在 `FILTER_STATES`）；`media` 收到一部作品，`counts` 也只數它的（M4 票 12）；回 `{filter, page, page_size, total, jobs, counts}`，`counts` 是五組各幾筆；超過最後一頁是空的一頁。M4 票 04，`.scratch/m4/jobs-paging-shape.md`；`JobOut.series` 是 RSS 送的那一筆的字幕組，讀不出時是 Series 的原始標題，M4 票 12）、`GET /jobs/{hash}`、`GET /jobs/{hash}/events`、`GET /jobs/{hash}/files`（`job_files` 照路徑排，每一個帶 `wanted`（優先序不是 0）與這一筆那一份計劃給它的 `action`、季集；qBittorrent 給出檔案清單之前是空陣列；沒有這一筆是 404。M4 票 12，`.scratch/m4/media-downloads-shape.md`）、`POST /jobs/{hash}/replan`（Job 停在 `review` 時只有 admin：403 `review_needs_admin`——在那裡重算會丟掉 admin 審過、撤銷過的那一份。門禁只看方法與路徑，這一條要看狀態，所以守在命令裡、與退回 `completed` 的 CAS 同一把鎖；`JobOut.replannable` 依按的人算，按鈕與命令問的是同一支 `jobs.replannable`；其他狀態照舊誰都按得了，M3 票 04）、`POST /jobs/{hash}/reimport`（admin；回退回 `completed` 的那一筆並叫醒規劃器；拒絕 404 `job_missing`、409 `not_reimportable` / `content_missing`；`JobOut.reimportable` 說按不按得了，M2 票 10）、`POST /jobs/{hash}/retry`、`GET /jobs/{hash}/deletion`（刪下去會空出多少：逐一 `stat` 每一個來源與目標，只讀；票 04）、`DELETE /jobs/{hash}?unlink=&remove_torrent=&delete_files=&purge=`（四個旗標**預設全不勾**，後端也是；回的是**真的做掉了什麼**而不是 204——勾了「移除鏈接」而那幾個檔案早就被人刪掉時畫面要說得出「0 個」。拒絕：404 `job_missing`、422 `delete_files_requires_remove_torrent`、502 `client_unreachable`。**檔案由 Berth 自己逐檔刪**，不用 `torrents/delete?deleteFiles=true`：torrent 可能早就不在客戶端了，而時間線要數得出刪了幾個、空出多少，brief §20.2） | `add_download`、`generate_plan`、`reimport`、`delete_job` |
| plans | `GET /plans/{id}`（誰都讀得到；每一列帶 `kind`、`applied` 與改得成的 `actions`，**`pending_review` 時 `target_path` 是「核准的話」會落在哪裡**）、`PUT /plans/{id}/items`（`{items: [{id, action, season, episode_start, episode_end}]}`，整批成立或整批拒絕；回改完的整份，改過那一列的新目標路徑與跟著搬的字幕都在裡面；Plan 的 `engine` 變 `user`，改過的列多一條 `set_by_user`、清掉 `error` 與 `audit`）、`POST /plans/{id}/approve`（回核准後的整份，叫醒 importer）、`POST /plans/{id}/reject`（204，叫醒規劃器）。**寫入的三支只有 admin**（門禁 `ADMIN_ROUTES`）。三支在 Job 鎖裡重讀，兩個分頁同時按時後到的是 409 `not_pending`。拒絕是 `{reason, detail}`（`PlanRefusal`）：404 `plan_missing`、409 `not_pending` / `item_applied`（已鏈接的列改它是 rematch 的事）、422 `item_missing` / `action_not_allowed`（與分類矛盾，`EDITABLE_ACTIONS`）/ `episode_required` / `episode_range_reversed` / `episode_not_allowed`（季集只屬於劇集的入庫）/ `media_missing` / `target_clash`（比的是核准後的那一份，待審核列的提案也算）/ `undecided`（核准時）。M1 只有 `GET`（票 11）；M2 票 07 實作其餘三支（§3.1 的兩條出邊）；**`series`**（M3 票 13）：算這一份時用的 RSS Series 與它當時的 `season`、`episode_offset`，不是 RSS 送的是 `null`——Job 頁說得出這一份用了什麼。**`PUT /plans/{id}/items` 的 `apply_to_series: true`**（M3 票 14b，只配一列，否則 422）：從停在審核的計劃「套用到這個 RSS Series」——由那一列算出季號與 offset（`parser.written_episode`，同 files 那一列）寫回 Series；那一列照逐列改存下來、**這一份仍是 `pending_review` 等人核准**，同一份裡沒有人碰過的列（不是 `set_by_user`、沒鏈接、不是重複版本）換成照新值重算的提案（`plan.held_proposal`，播出日比對照跑），Plan 的 `season_hint` / `episode_offset` 跟著改；同一個 Series 已入庫未確認的照 files 那一列搬，其餘停在 review、`engine ≠ user` 的重新規劃並叫醒 importer。回應是整份（`PlanEditedOut`）多 `corrected: {season, episode_offset, moved, replanned, left}`；拒絕多兩種 422：`not_from_series`、`no_episode_number`，逐列改的拒絕發生時 Series 不寫回 | `plan_review.edit_items`、`approve_plan`、`reject_plan`、`plan_view.read_plan`、`series_review.correct_series_from_plan` |
| review | `GET /review`（低信心、audit、Unmatched、重複的統一佇列。**一支端點、一份清單、一列一件事**（2026-09-22 定）：每一列帶 `kind`（`plan` / `audit` / `unmatched` / `duplicate`；**`issue` 在 M3 票 05 拿掉**，見本列最後）、指向它的物件（plan id / ledger id / item id）、一句封閉集合的理由與這一列能按的動作；排序是「需要人動手的排前面」（`plan` 與 `unmatched` 先、`audit` 與 `duplicate` 次），同類之內舊的在前；不分頁——佇列超過 200 列時回前 200 並帶 `total`，那時候該修的是上游而不是分頁。**`?library=<Jellyfin 媒體庫 id>`（M2 票 14）** 只回 Route 指向那個媒體庫的 `plan` 與 `unmatched`（媒體庫頁「待審 / 對不到」的清單），`total` 只算這兩類、`queue_total` 仍是整份佇列（清單底下「審核佇列裡還有 N 件」）；媒體庫 id 只拿來挑 Route，不問 Jellyfin）、`POST /review/audit/{ledger_id}/confirm`（清掉 `ledger.audit` 與對應 `plan_items.audit`，寫 event `audit_confirmed`）、`POST /review/audit/{ledger_id}/undo`（刪掉硬鏈接、帳本那一列刪掉、Job 回 `review` 並帶 `review_reason = audit_undone`，寫 event）。**M2 票 06 實作**：兩支都回 204；撤銷**不呼叫 `delete_job` 本人**（它的單位是整筆下載、終點是 `removed`），共用的是 `unlink` 那一步與它的 Route 守衛（`services/deletion.remove_one`），而且先拆鏈接、拆成了才改紀錄（拆不掉是 409 `unlink_failed`）；列以 `kind` 區分形狀（pydantic discriminated union）。**M2 票 07**：`plan` 那一類是「Plan 在 `pending_review` **而且** Job 在 `review`」，`ref` 是 plan id，理由 code 是 `ReviewReason`、參數是計數，動作是 `approve` / `reject`（打 `plans/*`）；逐列不跟著來，畫面展開那一列時打 `GET /plans/{ref}`。audit 列的 `notes`（英文原文）改成 `reasons`（`ItemReason`）；**撤銷時那一列 Plan Item 回到沒有提案**（`review`、季集與路徑清空），否則原樣按一次核准就把剛拆掉的鏈接鏈回同一條路徑（票 07 code-review）。**M2 票 08**：`unmatched` 那一類是 Job 那一份**定案了**的 Plan（`SETTLED_PLANS`）裡對不到的檔案，`ref` 是 `job_files` 的 id（就是 `POST /files/rematch` 的 `job_file_id`，與 Media 詳情的 Unmatched 區同一支），列上帶 `media_kind`、`file_kind`、解析器的理由與改得成的 `actions`；光碟結構不列（一包 BDMV 會把佇列塞滿，而它們只能忽略）。`duplicate` 那一類是 `plan_items.duplicate_of` 還指著帳本的那幾列（規劃時略過的），`ref` 是 Plan Item 的 id，理由是 `DuplicateReason`（`same_version` / `span_clash`），帶新舊兩份的路徑與季集；`POST /review/duplicate/{item_id}/{decision}`（`replace` / `keep_both` / `skip`）回 `{plan_id, target_path}`（跳過時 `null` 與空字串），拒絕與 rematch 同一種（`RematchRefusal`：409 `not_duplicate` 加磁碟那一步的幾種）。取代與保留兩者走 rematch 的同一步。**M3 票 05**：`/review` 不再列 Issue（brief §19 2026-09-24，Issue 只在 `/issues`），`GET /review` 多一格 `issues_open`（還開著幾件，不算進 `total` / `queue_total`），畫面原位一行「另有 N 件待處理」；`POST /review/audit/confirm`（`{ledger_ids}` → `{confirmed, skipped}`）是「全部確認」——同一個 Job 一組、audit 段整段都打它，送的是畫面上列出的 id，語意是逐列按確認（一列一個鎖、一筆 `audit_confirmed`），已經被別處確認或撤銷的列算 `skipped`、不回 409。**RSS Series 的第一批**（M3 票 13）：audit 列多帶 `action`（只有正片改得了季集）與 `series`（`id`、`name`、`confirmed`、`season`、`episode_offset`），還沒確認的 Series 那幾列的理由是 `first_batch`；畫面以 Series 分組，組上的「全部確認」打 `POST /review/series/{id}/confirm`（`{ledger_ids}`，逐列確認同 `/audit/confirm`，再把 Series 標成 `confirmed`；回 `{confirmed, skipped}`、沒有拒絕的回應） | `review.*`、`series_review.confirm_series`、`duplicates.decide_duplicate`、`issues.count_open` |
| files | `POST /files/rematch`（`{ledger_id \| job_file_id, action, season, episode_start, episode_end}`，兩個 id **恰好帶一個**，否則 422）。**內部建一份單 item 的 Plan 並立刻套用**（2026-09-22 定，brief §9.4「一律經過 Plan」）：`plans.job_hash = NULL`、`engine = user`、`status = applied`、`source_path` 是那個檔案，走 importer 的同一步（`importer.link_into` / `record_link` / `notify_jellyfin`：建新鏈接 → 拆舊鏈接 → 改帳本 → 通知掃描；**沒有一支叫 `apply_plan` 的函式**，共用的是逐檔那一步），對外仍是一支命令，回 `{plan_id, target_path}`（M3 票 13 起多 `series`；`plan_id` 只在套用到 RSS Series 而這一集自己搬不走時是 `null`）。**M2 票 08 實作**：`action` 是 `import`（指派；電影就是入庫）/ `extra` / `skip`（忽略），依檔案分類給（`REMATCH_ACTIONS`：影片與特典三種都行，字幕與光碟只能忽略）；已入庫的那一列帳本**改寫**（id 不變）而不是刪了再建，忽略就刪；**字幕跟著影片走**（同資料夾、影片主幹加一個點的那幾列帳本：改指派時改名跟過去，標記特典或忽略時一起拆）；Job 那一份 Plan 的那一列跟著改成現況（Unmatched 區與佇列讀的是它），單列 Plan 是這一次修正的紀錄；拆掉的路徑也送 `Library/Media/Updated`（Jellyfin 不看 `UpdateType`，brief §20.1）。Job 的 Plan 還沒定案（`SETTLED_PLANS` 以外：預估、等審核、被拒絕）時 409 `plan_pending`。拒絕是 `{reason, detail}`（`RematchRefusal`，16 種——M3 票 13 加 `not_from_series`、`no_episode_number`）：404 `ledger_missing` / `file_missing`、409 `not_unmatched` / `plan_pending` / `route_missing` / `target_taken` / `link_failed` / `unlink_failed`、422 `action_not_allowed` / `episode_required` / `episode_range_reversed` / `episode_not_allowed` / `media_missing`。**磁碟先、紀錄後**：鏈不起來、拆不掉都在寫任何紀錄之前拒絕，拆不掉時剛建的那一條收回。整組只有 admin（`ADMIN_PREFIXES`）。**`apply_to_series: true`**（M3 票 13，只配 `ledger_id`）：同一次 rematch 之後由那一集算出季號與 offset 寫回送出它的 RSS Series，重算它底下還沒確認的集數（已入庫的走 rematch、仍掛 audit；停在 review 的重新規劃並叫醒 importer），回應多 `series: {season, episode_offset, moved, replanned, left}`；拒絕多兩種 422：`not_from_series`、`no_episode_number`；人要的那一格被不會搬走的檔案（確認過的一集、別人的）佔著是 409 `target_taken`、什麼都不動，被同一批也要搬的那一集佔著則等它先搬（`services/series_review._carry`；這一集最後仍搬不走時 `plan_id` 是 `null`、數進 `series.left`） | `rematch.rematch_file`、`series_review.correct_series` |
| rss | **整組只有 admin**（`ADMIN_PREFIXES`：聚合 feed 的網址帶 token，綁定會替整個家送單）。M3 票 08：`GET /rss/feeds`（每個 Feed 帶它長出的 Item 數）、`POST /rss/feeds`（`{url, name, route?}`，201；網址的主機不認得是 422 `feed_unsupported`、同一個網址是 409 `feed_duplicate`；不當場輪詢。`route` 是票 21 的自動綁定 Route，不存在是 422 `route_missing`；Feed 的每一列帶 `route_id`）、`DELETE /rss/feeds/{id}`（連它的 Item 一起刪，回 `{items}`；404 `feed_missing`）、`POST /rss/feeds/{id}/poll`（立刻輪這一個，回 `{items, series, bound, submitted, failed}`；抓不到 Feed 仍是 200，失敗在那一列的 `last_error` 與回應的 `failed`（票 21）；Feed 的每一列帶 `ever_read`＝至少讀到過一次，`false` 時 `prime` 的 `all` 是 409 `feed_unread`）、`GET /rss/series`（待綁定的排前面，每一列帶 `waiting`＝還沒送出的 Item 數）、`PUT /rss/series/{id}/binding`（`{media, route}`：綁定、凍結資料夾名、送出留著的 Item，回那一列加 `submitted`；Mikan 的 RSS Series 同時讀單一 feed 補舊集（票 12，一律補——`backfill` 參數 M4 票 78 拿掉；讀不到單一 feed 不擋綁定，下一輪補）；404 `series_missing`、409 `series_bound` / `route_disabled`、422 `media_missing` / `route_missing` / `route_kind_mismatch`；**送單被拒不讓它失敗**）、`DELETE /rss/series/{id}/binding`（解除：還沒送的 Item 回到待綁定；已送的 Job 與資料夾名不動）、`GET /rss/series/{id}/items`（M4 票 13：這個 Series 的每一筆，發佈新的在前、不分頁；404 `series_missing`）。**`SeriesOut` 的呈現欄位**（M4 票 13）：`mikan_bangumi_name` / `mikan_subgroup_name`、`latest_episode`（`latest_title` 讀出的集數；`latest_*` 一直是照發佈時間的最近一筆、排除的不算）、`imported` / `active` / `excluded`（它的 Item：Job 已入庫、Job 在 `FILTER_STATES[active]`（`/jobs` 的「在路上」，需要人的也在裡面）、排除條件擋下）、`finished`（§2.4）；`ItemOut.episode` 是發佈名讀出的集數（不套 offset）。`POST /rss/subscriptions/mikan` 多選填的 `subgroup_name`（畫面挑的時候從番組頁讀過的名字；番組名由單一 feed 自己帶）、`GET /rss/items`（最近 50 筆；每一筆帶 `skip`＝`excluded` / `duplicate` 的理由 `{code, params}`，`domain.SkipCode` 六種，句子在前端 `rss.skip.*`）。M3 票 10：`GET /rss/exclusions`、`PUT /rss/exclusions`（`{not_single, rules}`，全域那一層）、`PUT /rss/feeds/{id}/exclusions`、`PUT /rss/series/{id}/exclusions`（`{rules}`，回那一列；Feed 與 Series 的清單每一列帶 `exclusions`）——整組覆寫、寫壞的那一條讓整組不存（422 `rule_invalid`，`detail` 是 `<規則>: <Python re 的原因>`）、改完之後那一層還沒送出去的 Item 照新規則再看一次（只收緊）。拒絕是 `{reason, detail}`（`RssRefusal`）。原本的 `rss/rules` 一組隨 brief §15 的 RSS Series 改寫；Feed 的編輯（`PUT /rss/feeds/{id}`）沒有消費者，沒做。M3 票 11：`GET /rss/feeds/{id}/preview`（這個 Feed 的每一筆，新的在前；還沒送的當場看一次去重、只讀，重複的回成 `duplicate` 帶理由但不寫回；404 `feed_missing`）、`POST /rss/feeds/{id}/prime`（`{mode: all | later}`，寫 `primed_at`，回 `{feed, submitted, passed, excluded}`；409 `feed_primed`；`later` 當場再讀一次 feed，讀不到是 502 `feed_unreachable`、什麼都沒改；還沒讀過的 Feed 不收 `all`，409 `feed_unread`；寫 `primed_at` 是 `WHERE primed_at IS NULL` 的條件式更新，另一個分頁先選了就是 409；命令標 `irreversible`——選完就定了，M5 的 AI 不自己選）；`GET /rss/feeds` 每一列多 `primed_at`、Item 多 `size`。M3 票 18：`POST /rss/oneshot`（`{url, media?, route?}`，**只讀**：不建 Feed、不長 RSS Series、不寫 Feed Item；回 `{kind, items}`，每一筆帶送單要的 `source_id`（M4 票 79：`.torrent` 或 magnet 的網址記在伺服器上，與搜尋結果同一份 `SourceCache`）、`published_at`，加上 `release_kind`、`tags`、季集（給了 `media` 是 `search.estimate` 照那部作品換算，沒給是發佈名寫的）、`job_hash`（同一個 hash 的 Job 已經在了）與 `known`（`media` 與 `route` 都給時比帳本，`rss.library_copy`，同 RSS 送單前那一層）；422 `feed_unsupported` / `media_missing` / `route_missing`、502 `feed_unreachable` / `feed_not_rss`（讀到的不是 RSS，多半是貼了網頁的網址））。勾好的那幾筆由前端逐筆走 `POST /jobs`（`trigger = manual`，舊的先）——不另開一支批次送單。M3 票 19（從 Media 頁訂閱）：`GET /rss/mikan/search?q=`（Mikan 搜尋頁上的番組 `{id, title}`）、`GET /rss/mikan/bangumi/{id}`（`{id, title, premiere, subgroups}`，每個字幕組帶 `updated`、`releases`、`latest` 與 `bound_to`＝它的 RSS Series 已經綁在哪一部；兩支讀不到 Mikan 都是 502 `feed_unreachable`）、`POST /rss/subscriptions/mikan`（`{media, route, bangumi, subgroup, name, subgroup_name}`，201 回 `{feed, series}`，`series.submitted` 含整季；409 `series_bound` / `feed_duplicate` / `route_disabled`、502 `feed_unreachable`（什麼都沒加）、422 `media_missing` / `route_missing` / `route_kind_mismatch`）、`POST /rss/subscriptions/search`（`{media, route, kind: nyaa | acgrip, term}`，201 回 Feed；當場讀一輪，讀不到仍是 201、原文在 `last_error`；422 `feed_unsupported`（`kind = mikan`）、409 `feed_duplicate`）；`GET /rss/series` 多 `?media=`，每一列多 `confirmed`、`source`、`group`、`latest_title`、`latest_at` | `rss.*` |
| issues | `GET /issues`、`POST /issues/{id}/resolve`（`{action, media}`，`media` 只有認領類的兩顆要（`NEEDS_MEDIA`：`adopt`、`claim_torrent`，缺了是 422 `media_required`），「認領進帳本」配不上是 409 `unclaimable`、`detail` 是 `ClaimMiss`（M2 票 10）；動作是 brief §9.1 那一欄的封閉集合；`library_link_missing` 的「連 complete 一起刪」走 `delete_job` 同一組旗標；會刪東西的那幾顆在動手之前重問一次它依據的事——孤兒目錄仍然沒有主（`services/complete.claimed`，與對帳同一份判準）、複製品仍然與來源一樣大（票 09））、`POST /issues/{id}/ignore`、`POST /reconcile`（202，回這一輪的 id；正在跑是 409 `reconcile_running`）、`GET /reconcile`（上一輪與進行中的進度，§3.2）、`GET /issues/rebuild-ledger`（`{unknown}`：Route 寫入目標底下帳本不認得、還沒被重建或認領判過的檔案數；判過 = 開著或被忽略的 `unmanaged_library_file` 寫著 `reason`）與 `POST /issues/rebuild-ledger`（與 `berth rebuild-ledger` 同一個命令，回 `RebuildReport`；對帳正在跑是 409 `reconcile_running`）——M4 票 60，精靈完成頁與 `/issues` 上的「從媒體庫重建帳本」 | `reconcile`、`issues.resolve`、`ledger_rebuild.read_ledger_gap`、`ledger_rebuild.rebuild_ledger` |
| health | `GET /health`（匿名：`status`、`version`、`setup_completed`；`status` 只讀 `settings.health` 那一列與 `routes` 表的總結，不連任何服務）、`GET /health/detail`（要登入，一般使用者也讀得到：逐服務與逐 Route 的明細、最後成功時間、檢查間隔；`tmdb_verified` 是精靈第 7 步那一次憑證測試的結果，給泊位板的 TMDB 那一格，不是第五項檢查，票 06e）、`POST /health/check`（立刻重跑四項）、`GET /health/budget`（要登入：一個站一份請求預算的現況——每站每小時上限、視窗裡每一站用了多少、照 `poll` / `backfill` / `search` / `manual` 拆開、被擋下還沒過得去的工作與放得下的時刻；記憶體裡的那一份，不連任何服務，M3 票 20） | `health.*`、`read_budget` |
| events | `GET /events/stream`（SSE：job 狀態與進度。**M1 只有 job**——健康變化每 5 分鐘一次，值不到一條長連線）。推的是**提示不是真相**：`{hash, state, progress}`，前端據此讓清單（`['jobs', 'list']`，作品頁「下載」段的那一頁也在底下，M4 票 12）與推播到的那幾筆（`['jobs', hash]`，含展開中的檔案清單）失效再問一次，所以漏掉一筆的後果是慢一點而不是畫面說謊。**一秒內到的併成一次**、進行中的請求不取消，清單還在抓時等它回來再失效（M4 票 04：poller 一輪推 N 則原本是 N 次整份 `GET /jobs`）。連上的那一刻整個 `['jobs']` 重問一次（訂閱建立之前推出去的那幾筆誰都收不到，票 10） | — |

- **`/api` 底下的每一個回應都帶 `Cache-Control: no-store`**（門禁補的，票 10）。這不是最佳化：一個 header 都不送的話瀏覽器會對 `200` 套用它自己的啟發式快取，而這裡的每一支回的都是「現在的狀態」——實跑抓到 SSE 推來的重問拿回一份幾秒前的快取，畫面因此停在錯的狀態。**唯一的例外是圖片那一支的 200**（M1.5 票 04）：`private, max-age=31536000, immutable`——網址帶著 `ImageTags`，換圖時網址就變。門禁只替沒設 `Cache-Control` 的回應補 `no-store`，所以例外由那一支自己設；它的 401 / 404 / 422 / 503 照樣是 `no-store`。
- OpenAPI 由 FastAPI 產生；前端用 `openapi-typescript` 產型別，CI 檢查型別檔是否過期。**拒絕的 `reason` 是 `domain/enums.py` 的 enum**（`JobRefusal`、`RouteRefusal`、`AccessRefusal`），由 router 的 `responses=` 帶進文件，所以前端的封閉集合也是產出的（M2 票 02；在那之前它們是裸字串，前端各抄一份，後端加一種理由時沒有東西會紅）。**會拒絕就要宣告**：`create_app()` 的每一條路由，handler 丟得出來的拒絕**形狀**要與它 `responses=` 上宣告的一模一樣，漏宣告與多宣告都紅（`tests/unit/test_openapi_contract.py` 的 `TestDeclaringWhatEachEndpointRefuses`，票 02a）。它比的是路由**物件**上的 `responses`（執行期的值）與 handler 的**語法樹**，所以 `PLAYED_RESPONSES` 這種先存成常數再用的寫法也算得到，而票 02 數字串的那一版數不到。**閘門只到形狀那一層**：每支端點只列它真的會回的哪幾個**理由**是慣例，沒有閘門——各端點各給一張小表（`api/routes.py` 的 `route_responses()`、`api/jobs.py` 的 `_refusals()`），`REFUSAL_RESPONSES` 是 `routes/*` 五支的聯集，別套到別的模組（那五支自己仍共用它，是已知的過度宣告，票 02a Comments）。精靈的兩支 Route 命令照這個慣例是 `POST /setup/routes` 404 `route_missing`、`DELETE /setup/routes/{id}` 404 + 409 `route_in_use`。理由 → 狀態碼的表要涵蓋整個 enum（`tests/unit/test_openapi_contract.py` 守著），沒有「其餘一律 422」的預設。權限閘門那一組的 `responses=` 與 `except` 吃同一個例外 tuple，文件因此不會與處理的那幾種漂開。
- 未來 MCP server 只需把 `services` 的命令包成 tool，schema 直接沿用 pydantic model。

---

## 7. 前端

- 路由：`/setup`、`/login`、`/`（探索，票 03 起是真的探索頁，不再導向 `/health`；M3 票 06 起只放 TMDB 牆）、`/health`、`/media/:id`、`/library`（導向這位使用者的第一個媒體庫）、`/library/:libraryId`（`?page=`、`?filter=review|unmatched`（只有 admin，M2 票 14）、`?sort=&order=&genres=&years=`（票 06）、`?q=`（按名字找，M2 票 14）；M1.5 票 03 取代票 13 的 `/library/:routeSlug`，舊網址不留轉址）、`/jobs`、`/jobs/:hash`、`/review`、`/rss`（只有 admin，M3 票 08：由上而下待綁定 → Feed → 綁好的 RSS Series → 最近的 Feed Item，綁定在待綁定那一列就地展開，`.scratch/m3/rss-shape.md`；**M4 票 13** 起綁好的 Series 作品一塊、字幕組一列，展開看它的 Item，Series 層排除條件在展開區的「進階」，完結的收在段尾預設收起的「已完結」；Feed Item 每一列說出 Feed 與 Series，`.scratch/m4/rss-series-shape.md`）、`/issues`、`/settings`（導向 `/settings/jellyfin`；頁首的「設定」連這裡，在每個設定頁上都是當前頁，票 14a）、`/settings/jellyfin`、`/settings/qbittorrent`、`/settings/routes`（票 14）、`/settings/indexers`、`/settings/tmdb`——**一格泊位一頁，分頁照泊位板的順序**，共用一條子分頁列（票 06i，`.scratch/m3/settings-shape.md`；對應表在 `components/berths.ts`）。每頁重用精靈那一格的元件：連線表單（`MooringLine`）、`JellyfinSignIn`、`IndexerActions`、`TmdbKey`；套件內的服務沒有位址表單。Jellyfin 頁另有對外網址，qBittorrent 頁另有建議設定的還原與磁碟空間門檻。
- 守衛：精靈未完成 → 一律導向 `/setup`（讀 `GET /health` 的 `setup_completed`，那是匿名答得出來的唯一來源）；未登入 → 導向 `/login?redirect=<原路徑>`，`?redirect=` 只收站內路徑，沒有時登入後落在 `/library`（M3 票 06：接著看的兩列在那裡；第一次開 `/` 不記下 `/`，用到一半被踢出來的才記）——**這個人看得到的媒體庫裡 Berth 一筆帳本都沒有時落在 `/`**（M4 票 10，brief §19 2026-09-26：精靈剛跑完或接上既有 Jellyfin 時第一件事是找片；讀 `GET /inventory` 的 `has_imports`，問不到時照舊落在 `/library`，由它說原因；規則在 `web/src/auth/destination.ts`）；**任何請求回 401**（讀資料或按鈕）都重跑守衛、同一條路送回登入頁，登入後回到原本那一頁（`router.ts`，M3 票 06）；`/settings/*` 只放行 `admin`；精靈完成後 `/setup` 把 `admin` 導向 `/settings`、其他人導向 `/`（**精靈只管第一次**，票 06i）。缺憑證、缺 Route、服務紅燈這類「去補上」的連結一律指設定頁的那一頁，只給 `admin`（`SettingsHint`）。頁首顯示角色、導覽（健康 / 設定）與登出，`admin` 才看得到設定入口——前端隱藏不是安全機制，後端同時回 403。健康頁是唯讀診斷，一般使用者也進得去。
- 資料：TanStack Query 管 API 快取；SSE 事件到達時使 job 相關 query 失效（合併的規則在 §6 events）。`queryFn` 把 TanStack 給的 `signal` 交給 `apiGet`，沒人要的請求真的取消。**會逐檔摸磁碟的刪除估算不掛在 `['jobs']` 底下**（`['deletion', hash]`，M4 票 04）：那個前綴被 SSE 與每一個動作失效。改入庫狀態的動作（核准、撤銷、確認 audit、修 Issue、rematch、刪除）之後也讓 `['media']` 失效：那一份 5 分鐘內不重抓（M3 票 06）。
- 送出中：動作鍵 `busy`（`aria-disabled`、按了不再送，焦點留在原地），不用 `disabled`（M3 票 06，DESIGN.md Buttons）。
- 元件：全部是專案自有元件（媒體卡片、狀態徽章、時間線、Plan 表格（逐列可改季集與動作）、檔案樹、`CollapsibleRow`），不用 shadcn/ui（§1.4）。**`/review`（M3 票 05）**：兩段（要你決定、已入庫等你看一眼），Issue 只剩一行連到 `/issues`；同一個 Job 的 audit 收成一組（`review/auditGroups.ts`，鍵留得下票 13 的 RSS Series），一組一顆「全部確認」、audit 段標題列一顆整段的（就地確認、說出件數）；收起的 audit 列與組說出主要原因（`review/leadReason.ts`，純函式）。**M1 的 Plan 畫在 `/jobs` 的就地展開區**（票 11），不是 `/jobs/:hash`：票 09 拍板不另建那一頁。**M2 另建 `/jobs/:hash`**（2026-09-22 定，M2 票 12 實作，`.scratch/m2/job-detail-shape.md`）：brief §13 的 Job 詳情頁——時間線、檔案清單與各檔決策、Plan 歷史、動作（重新解析、重試、重新入庫、刪除範圍）；刪除範圍是要二次確認的破壞性動作，塞在列表的展開區說不清楚「哪一筆正在被刪」。`/jobs` 的展開區只留狀態、最近三段時間線與到詳情頁的連結；計劃與每一顆動作只在詳情頁。**逐檔表格是唯讀的 `JobPlan`，不與 Review Queue 的 `PlanEditor` 共用**：編輯要有核准 / 拒絕流程包著，搬到詳情頁等於多一個審核入口（Plan 停在 `pending_review` 時 admin 在詳情頁看到到審核佇列的連結）。**Plan 歷史是時間線上九種與 Plan 有關的事件**（`plans.job_hash` unique、重新規劃整份換掉，所以沒有舊的那幾份可列），畫法仍是時間線元件。
- 文案：react-i18next，`zh-Hant` 與 `en` 兩個語言檔並列，預設跟隨瀏覽器；所有字串走 key，不硬編。
- 主題：深色為預設（媒體應用慣例），亮色跟隨系統。
- 版面：桌機為主，但每一頁都要有真正可用的窄版（審核、佇列、送單在手機上要做得完）。
- 無障礙：WCAG 2.2 AA 是驗收條件——純鍵盤可完成、焦點可見、對比達標、狀態不只靠顏色。
- 使用者輪廓、原則與無障礙細節見 `PRODUCT.md`；視覺系統見 `DESIGN.md`。
- 每頁的核心任務與元素見 brief §13；設定精靈的步驟見 §9.3。

---

## 8. 外部整合細節

### 8.1 qBittorrent adapter

- 連線時讀 `app/webapiVersion` 與 `app/version`，低於 2.8.4 拒絕並提示升級。
- 參數依版本：API ≥ 2.11 用 `stopped`，否則 `paused`；`contentLayout=Original`；`autoTMM=true`；`category=<route.category>`；`tags=berth`。**版本判斷是必要條件**：實測送錯的那個參數會被靜默忽略（`torrents/add` 照樣回 200），torrent 就這樣開始下載（brief §20.7）。值是 `false`（**只送版本對的那一個鍵**）——qBittorrent 有一個「加入後不自動開始」的全域偏好，而 §3.1 的狀態機假設送出去的 torrent 會自己走到 `metadata_ready`；不明講的話，開著那個偏好的使用者身上每一筆 Job 都會永遠停在 `submitted`（票 09）。`savepath` **不送**：`autoTMM=true` 時路徑由 category 決定，兩個來源會讓「存到哪裡」有兩個答案。
- **成功的形狀依版本判定**（2026-09-10 實測）：4.4.5 是 `200` + `Ok.`，5.2.3 是 `200` 加一份 JSON 摘要（`failure_count == 0` 且 `success_count > 0`）。`409` 是「不收」（已經有同一個 hash，或 category 的 save path 用不了），`415` 是那份 `.torrent` 無效，`202` 是「網址收下了、之後再去抓」而**那條路徑的失敗永遠不會回來**——所以它也不算成功（brief §20.7）。
- **送單前 Berth 自己把 torrent 抓下來**（`adapters/torrent.py`，票 09）：索引站的下載連結 → info hash + 磁力連結或 `.torrent` 位元組。兩個理由——`jobs.hash` 是主鍵而索引站不一定報 hash（實測 ACG.RIP 不報），以及交網址給 qBittorrent 是背景抓取，失敗時 §3.1 的 `submit_failed` 永遠觸發不到。
- `ensure_category(name, save_path, download_path)`：`torrents/categories` 讀取（接受 `savePath` 與 `save_path` 兩種鍵；4.4.5 與 5.2.3 實測都是 `savePath`，`save_path` 只出現在 4.4.0–4.4.1，仍在支援範圍所以兩種都收；未完成目錄讀 `download_path`，M4 票 22），不存在才建、建的時候帶 `downloadPathEnabled=true` + `downloadPath=<incomplete root>/<slug>`；存在但 save path 不同、或有自己的未完成目錄而不同 → 回報衝突不改（brief §20.2）。沒有自己未完成目錄的舊分類不算衝突。
- **全域偏好一個都不寫、也不看**（M4 票 32，brief §19 D2）：送單逐個 torrent 帶分類與 `autoTMM=true`，save path 與未完成目錄開在分類上（M4 票 22，brief §4.1），全域的 `save_path`、`temp_path`、兩個 autoTMM 開關都不影響 Berth。`app/setPreferences` 只拿來設套件內那一台的 WebUI 登入（密碼先、帳號後，M4 票 26）；`app/preferences` 只讀 `web_ui_username`（那一台自己設過登入沒，brief §20.14）。
- 完成判定依 brief §20.2。`torrents/files[].name` **相對 `save_path`**（多檔含 torrent 根目錄那一層），實測四種 `contentLayout` 組合都成立（brief §20.7）；組絕對路徑前先正規化 `save_path` 的尾斜線（4.4 有、5.x 沒有），組完仍 `stat` 驗證。`content_path` 是目錄或單檔，兩種都處理。
- **`stat` 驗證只在 Berth 解析得了那條路徑、而且真的看得到它的時候才算數**（票 10）：看不到那個 save path 時視為通過，因為那不是這一筆 torrent 的問題，而是掛載對不上——而那件事有專門的檢查在報（Route 的 `download_path` 纜繩，§9.5）。在這裡把它翻成 `missing_files` 會讓每一筆 Job 都紅著，而紅的理由指向錯的地方。「解析得了」的判定是 `Path(save_path).is_absolute()`：qBittorrent 報的一律是容器裡的 POSIX 路徑，而 Windows 上它少了磁碟機代號，`Path` 會把它當成「目前磁碟機的根目錄底下」（實跑當場踩到）。看得到卻少檔案則是 `missing_files`——客戶端說做完了而檔案不在，那正是 `missingFiles` 說的那件事。
- **IP 封鎖分得出來了**（票 10，解掉 T1.9 的第四條）：`auth/login` 上的 `403` 只有「被封了」一個意思，body 帶明說的那一句（brief §20.2 的表）。翻成 `IpBannedError`（`AuthFailedError` 的子類，因為「還連不連得上」的答案一樣），下一步不同才是分開的理由。其他端點上的 403 與「沒有登入」同形，所以這個判定只放在登入那一支。
- `preferences()` / `set_preferences(values)`：`app/preferences` 與 `app/setPreferences`。後者收的是**表單裡一個叫 `json` 的欄位**，不是 JSON body；`web_ui_password` 只寫不讀，所以「密碼設過了沒」只能比對 Berth 自己上一次寫下去的值（票 08）。
- 登入：`auth/login` 拿 SID，請求帶 `Referer` = base URL。**沒有退避**——連續登入失敗會封 IP（brief §20.2），而被封那一次回的是 `403` 加一句明說的話，票 10 起翻成 `IpBannedError`；帳密不對在兩版都不是 403，所以登入端點上的 403 只有這一個意思。**失敗判定只認 4.x 的 `200` + `Fails.`**，不認「成功等於 `Ok.`」——5.x 成功回的是 `204` 空 body，失敗才是 `401`（走共用的錯誤映射）。免密白名單上的來源在 5.x 一律回 204，那是成功：套件內的 Berth 本來就繞過驗證（brief §20.2）。
- 錯誤映射（`adapters/http.py`，四個 adapter 共用）：主機名解不到 → `ServiceNotDeployedError`（服務不在 compose 裡，精靈立刻顯示既有服務表單）；連不上或逾時 → `ServiceUnavailableError`（容器還在啟動，繼續輪詢）；401 / 403 → `AuthFailedError`；回應不是預期的服務 → `ProtocolMismatchError`；409（category 不存在）→ `CategoryMissingError`；503 → `ServiceBusyError`（服務還在載入，與「壞了」分開——Jellyfin 重啟後每一支端點都會有一段時間回 503，brief §20.7）。名稱一律以 `Error` 結尾（ruff N818）。

### 8.2 Jellyfin adapter

- 兩種憑證：使用者登入用 `Users/AuthenticateByName`（只在登入時），伺服器操作用 API key（`Auth/Keys` 建立，存 `settings.services.jellyfin`）。
- `list_libraries()`：`GET /Library/VirtualFolders` → `Name`、`ItemId`、`CollectionType`、`Locations`、`LibraryOptions.TypeOptions[].MetadataFetchers`（偵測 TVDB 插件並警告）。
- `notify_paths(paths)`：`POST /Library/Media/Updated`，每路徑 `UpdateType=Created`。**對從沒掃到過內容的媒體庫無效**（204 但什麼都不做，brief §20.1），所以 `jellyfin_resolver` 有後備（§3.2）。
- `validate_path(path, is_file)`：`POST /Environment/ValidatePath`，跨服務可見性檢查用。
- `add_library_path(library_name, path)`：`POST /Library/VirtualFolders/Paths?refreshLibrary=false`，既有媒體庫加 Berth 路徑用；對應的移除 `DELETE /Library/VirtualFolders/Paths` 只在使用者明確要求時呼叫。
- `items(library_id, item_types)`：`GET /Items?parentId=<library>&recursive=true&includeItemTypes=…&fields=Path,ProviderIds,MediaSources`。每個 `MediaSources[]` 帶 `Path` 與 `Name`（版本選單上的名字，票 14b）。**只有這一支**（票 12 推翻原本的 `find_series` / `find_episodes`）：adapter 忠實翻譯協定，兩段查詢的比對（作品資料夾是不是已經是一個 Series、集的 `Path` 或 `MediaSources[].Path` 對不對得上帳本）住在 `services/resolver.py`——那要看 Route 與帳本，adapter 不認得它們。**不要用 `parentId=<seriesId>` 或 `/Shows/{id}/Episodes`**：10.11 在第一次掃描後對已比對到 provider 的 Series 兩者都回 0，要再掃一次才正常（brief §20.1、§20.7；12.0.0 沒有重現，§20.8）。`JellyfinItem` 帶 Episode 的 `SeriesId`（票 13）：resolver 找到一集時連同它的 Series 寫進帳本，媒體庫的深連結開到作品。
- **替某一位使用者瀏覽**（M1.5 票 03）：`user_views(user_id)`（`GET /UserViews?userId=`）、`user_policy(user_id)`（`GET /Users/{id}` 的 `Policy.IsDisabled`）、`library_page(user_id, library_id, item_type, start, limit)`（jellyfin-web 牆的參數，`sortBy=SortName`）、`library_index(user_id, library_id, item_type)`（整份清單，只要 `ProviderIds` 與 Primary 圖的 tag，`UserData` 關掉；Berth 端比對 Berth 經手的作品用，篩選後的牆也從它畫海報，M1.5 票 04）。`user_id` 是必要參數；**帶 `parentId` 的兩支只由 `services/jellyfin_access.py` 呼叫**，它先對 `user_views` 驗過媒體庫 id（研究 library-browsing.md §2、§9）。契約測試用 M1.5 票 01、03 錄的 fixture 斷言每個參數伺服器真的有過濾。
- `image(item_id, image_type, tag, fill_width, fill_height, quality)`（M1.5 票 04）：`GET /Items/{id}/Images/{type}?tag=&fillWidth=&fillHeight=&quality=&format=Webp`。**匿名**，呼叫端給不帶 token 的 client；404 是 `NotFoundError`，回的不是 `image/*` 是協定不符。`format` 固定 WebP、不靠 `Accept` 協商——發請求的是 Berth 不是瀏覽器。`JellyfinItem.primary_tag` 是 DTO 的 `ImageTags.Primary`（研究 library-browsing.md §6）。
- `scheduled_tasks()` / `run_task(task_id)`：`GET /ScheduledTasks` 找內建的 `RefreshLibrary`，再 `POST /ScheduledTasks/Running/{id}` 觸發它（反查的後備，§3.2）。**介面上沒有插件那幾支**（`/Repositories`、`/Packages`、`/Plugins`、`/System/Restart`，票 14b）：只支援 Jellyfin 12，而 12.x 原生合併多版本，不需要裝任何插件——所以 Berth 也就不會重啟別人的 Jellyfin。
- `public_info()` 帶一個 `supported`：版本 ≥ 12.0 才接（brief §16.4、§20.9）。精靈的 Jellyfin 頁（頁 1）與健康檢查用同一個判斷與同一句原文。
- 初始化：§9.4。
- 絕不呼叫 `DELETE /Items/*`。

### 8.3 TMDB adapter

- 端點：`configuration`、`trending/{tv,movie}/week`、`{tv,movie}/popular`、`search/multi`、`search/{movie,tv}`（帶年份的探索搜尋：`primary_release_year` / `first_air_date_year`，M4 票 69——查詢結尾是年份時拆開問，那一年沒有東西才照原字串問 `search/multi`，brief §20.19）、`tv/{id}`（`append_to_response=alternative_titles,translations,episode_groups`）、`tv/{id}/season/{n}`、`tv/episode_group/{id}`、`movie/{id}`（`append_to_response=alternative_titles,translations`）。**兩個 append 拿掉了**（票 04）：`external_ids` 與 `release_dates` 在快照裡沒有任何欄位讀它們，而後者每部電影是一百多筆各國上映日（2026-09-09 實測 138 筆）。要用時再加回來。
- **Media 詳情打三輪 + 每季一次**：`tv/{id}` 的 `en-US` 那一輪決定結構與所有會進檔名的字串（季名、集名、英文標題），`zh-TW` 那一輪只補顯示用標題與簡介，`zh-CN` 那一輪**只取季名**（§4.3 的篇章名比對，票 06；電影不打這一輪）；季集**只取 `en-US`**——集名會進檔名（§5 的 `{episode_title}`），中文集名放進去等於讓磁碟上的檔名跟著 UI 的語言跑。一部四季的作品因此是 3 + 4 + 1 = 8 個請求，24 小時一次（票 04、06）。
- **絕對編號要從 0-based 的 `order` 推**，不是 group 裡的 `episode_number`——那一欄保留播出序的原值，所以 SPY×FAMILY 的 S02E01 在 group 裡仍然是 `episode_number: 1`，而它是絕對第 26 集（2026-09-09 對真 API 實測，brief §20.3）。一部作品可能有好幾個 episode group（實測五個），只有 `type: 2` 是絕對編號，取第一個。
- 語言 `en-US` 取英文標題，`name` 空時退回 `original_name`；另以 `zh-TW` 取一次顯示用標題與簡介給 UI（brief §7.5 的檔名仍用英文）。**顯示用標題與簡介跟著 UI 語言走**（2026-09-17 決定，brief §19；M1.5 票 02 實作）：`zh-Hant` 介面顯示 `zh-TW` 那一輪（缺翻譯落回英文），`en` 介面顯示 `en-US` 那一輪（簡介缺就不印，不借中文）。**API 兩輪都送、前端照 UI 語言挑**，後端不知道 UI 語言：`title` / `title_en`、`overview` / `overview_en`、`poster_url` / `poster_url_en`、下載列的 `media_title` / `media_title_en`。換語言時畫面當場換、不重抓，`tmdb_cache` 與 Media 快照也不必按語言分列。快照為此多兩欄 `overview_en`（票 02）與 `poster_url_en`（票 11）；寫在那之前的快照讀出來是空字串，下一次刷新（至多 24 小時）補上。**海報也分語言**（票 11 補上）：`poster_url` 是 `zh-TW` 那一輪、`poster_url_en` 是 `en-US` 那一輪，畫面與標題挑同一輪；在 Jellyfin 裡的牆卡兩輪同一張（Jellyfin 的圖不分語言，名稱也是兩格相同）。**清單本身一律以 `en-US` 那一輪為準，`zh-TW` 只是一張「這一部叫什麼、海報是哪張」的查表**：`language` 會換掉 trending 回的**成員與順序**而不只是文字（2026-09-09 實測 `trending/tv/week`，兩輪 20 筆差 3 筆），照 `zh-TW` 當清單會讓作品憑空消失（票 03）。
- 快取：探索與搜尋 1 小時（`tmdb_cache`，一個 feed 一列，存的是已經合併好的卡片而不是 TMDB 原始 payload）；Media 快照 24 小時，**planning** 前若快照超過 6 小時則刷新（新播集數會變）。**送單那一步不刷新**（票 09）：它會凍結 `folder_name`，而凍下去的必須就是使用者剛剛在確認畫面上看到的那一串字（§2.2、brief §4.5）——刷新會在他按下去與那串字落地之間把它換掉。**卡片上的本地狀態不進快取**：它是本地事實而且會當場改掉（M1 票 04b 之後卡片上沒有狀態，票 09 起以 Job 推導）。
- 順序：`trending` 與 `popular` 回的順序**就是**那個 feed 的排名，不要重排——回應裡的 `popularity` 欄位與清單順序不一致（2026-09-09 實測，兩者都是亂序的）。劇集與電影兩份清單合成一面牆時用交錯（票 03）。
- 圖片基底：`configuration` 的 `secure_base_url` 對同一把憑證是常數，精靈的 TMDB 頁（頁 5）驗憑證時就寫進 `settings.services.tmdb.image_base_url`，探索頁直接讀它。海報尺寸 `w342`。
- 速率：全域 40 req/s 令牌桶，遠低於 TMDB 的上限。
- API key：**使用者自備，唯一來源是 `settings.services.tmdb.api_key`**（brief §16.3、§20.7；Berth 不內建任何 provider 的 key）。取用它的只有 `services.tmdb.credential()`，沒有 fallback。**兩種形狀都收**：v4 的 read access token 是 JWT，走 `Authorization: Bearer`（官方建議做法，不進網址所以不落在 log 裡）；v3 的 API key 是 32 個十六進位字元，走 `?api_key=`。認的是形狀不是設定項，因為 TMDB 的帳號頁同時發兩種（2026-09-08 實測）。
- 精靈 TMDB 頁（頁 5）的「測試」打 `configuration`：那一支不需要任何參數，回得出來就證明憑證有效。空白的送出不打網路，直接是一條紅線（說的是「必填」不是「401」）。

### 8.4 索引站 adapter

- 介面 `IndexerSearch.search(query) -> [SearchResult]` 加 `sites() -> tuple[SearchSite, ...]`（一個查詢打到哪幾站，請求預算的鍵，M3 票 20：Prowlarr 讀 `GET /api/v1/indexer` 裡啟用中的每一站的 id、名字與 Base Url——沒設就是 `indexerUrls` 的第一個；M4 票 77 起帶 id，預算放不下的站靠 `SearchQuery.indexer_ids` 跳過），一個實作。M4 票 37 拿掉 `capabilities()`、`SearchCapability` 與 tmdbid 搜尋（那條路只存在於 Torznab 的 caps，Prowlarr REST 只有關鍵字搜尋）。
  **一次呼叫一個查詢**（票 08 推翻原本的 `search(queries, categories)`）：多標題展開、合併去重、逐查詢
  逾時全部要看 `MediaSnapshot` 的標題集合與季數才決定得了，而 adapter 不認得它——留在這一層
  的話兩個實作各要抄一份同樣的邏輯。那些搬進 `services/search.py`。**分類碼不送**：各站的映射自訂，
  2026-09-10 實測 dmhy 對 `cat=5000`、`cat=5070` 與不帶 `cat` 都回同樣 80 筆，它不是可靠的篩子。
  - `ProwlarrSearch`：`GET /api/v1/search?query=&categories=&type=search`，回傳 `ReleaseResource`（`title`、`size`、`seeders`、`leechers`、`downloadUrl`、`magnetUrl`、`infoHash`、`indexer`、`categories`、`publishDate`、`guid`、`infoUrl`）。Prowlarr 刻意不提供跨站聚合 Torznab，所以走 REST（brief §20.7）。
- 搜尋詞：Media 的英文標題、原文標題、**顯示用標題**，然後才是各語言 alternative titles，各發一次，
  併發，最多五個（`MAX_QUERIES`）；劇集另加 `第N季` / `Season N` 變體，佔掉排最後的別名。
  **拉丁字名字裡有 `&` 的另問一個寫成 `and` 的**（M4 票 69，brief §20.19），緊接在原樣那一個後面、仍在
  `MAX_QUERIES` 之內：The Pirate Bay 只認 `and`、Mikan 只認 `&`，所以不學 Sonarr / Radarr 只送寫開的；
  `Season N` 變體用寫開的（scene 的寫法）。比對那一邊（`parser.title`）替帶 `&` 的名字多認一種寫開的，
  `Law.and.Order` 才對得上。
  **不分動漫**（票 14e，brief §19）：票 14e 之前只給動漫 Route，效果沒有量（要打真的索引站）。
  變體只對**季數 ≥2 的最新一季**做——第一季的發佈幾乎不寫季號，而每多一個變體就是每個追蹤站
  再被問一次；要找舊季自己打字那條路一直都在。
  顯示用標題明確排第三是因為 TMDB 的 `alternative_titles` 沒有順序可言——實測它把 `Agent x Ailə`
  排到中文標題前面（票 08）。合併去重以 infohash（**正規化成小寫十六進位**：同一個發佈在 Mikan 是
  40 字十六進位、在 dmhy 是 32 字 base32）或 `guid`；**`downloadUrl` 不能當身分**，它每次請求都不一樣
  （實測 1021 筆只有 1 筆重疊）。**它也不出伺服器**（M4 票 79）：`downloadUrl` / `magnetUrl` 帶著 Prowlarr 的
  API key，`search_torrents` 把它記進 `SourceCache`，結果的每一列只帶換得回它的 id。
- **缺集一鍵搜的查詢**（M1.5 票 10，使用者 2026-09-19 拍板）：季表已經知道缺哪幾集，所以那一種搜尋是
  **標題 × 記號**，記號由缺的形狀決定——整季缺（那一季播出了的每一集都缺）是一個季記號 `S03`；缺幾集、
  缺一集是**一集一個記號**：TMDB 給了絕對編號就用它（兩位數補零，照 Sonarr 的動漫查詢），否則 `S03E05`。
  有絕對編號的作品，發佈就是照絕對編號編的（`S02E01` 在那些站上搜不到），反過來也一樣，所以一集只給
  一個記號——兩種都送會讓記號數加倍，缺三集就吃掉全部配額，中文字幕組認得的那個標題一次都問不到。
  展開成查詢時**標題優先**（第一個標題先問完它的每一個記號），缺的每一集才至少都被問過一次。
  記號放不下 `MAX_QUERIES` 時先整批收成季記號；季記號也放不下（六季以上有缺）就**分批**（M3 票 20，
  取代原本的退回 `search_titles`——那讓第六季以後的缺集一次都問不到）：每一批是一組季、最多
  `MAX_QUERIES` 個查詢，第一批先填滿，一批裡照舊標題優先。**下一批由人按**（結果要人挑，背景自己問完
  沒有人看），以季定位（`from_season`，§6），何時問得了由 §3.2 的請求預算決定：一批在索引站背後放得下的每一站各佔「查詢數」格（放不下的站這次
  不問，M4 票 77），搜尋回來時說出下一批的 `next_at`（最早有一站放得下的時刻，與 `retry_at` 同一個意思），預算還放不下時照樣按得下去——
  有站放得下就問那幾站，每一站都放不下才回 `budget_exhausted`。缺＝`EpisodeStatus.MISSING`（已經播了、沒有任何下載在處理它），判定與季表的
  「只看缺集」同一份，所以查詢跟著帳本與 Job 走，不是跟著快照走。**Specials 照同一條規則產生 `S00`**
  ——幾乎沒有發佈這樣命名（字幕組寫的是 `SP` / `OVA` / `特典`），所以那個查詢多半空手而回；不把它排除是因為
  工具列數的缺集本來就含 S00，排除等於畫面說缺 N 集、搜尋卻少問一塊。要收窄成真的找得到的字，得先有語料。
- 結果附 `parse_release` 的 Tags 與 `map_episode` 的預估（用來在結果表顯示「S01 全季」「E05」「無法判斷」）。
  **每一筆歸到一類**（M4 票 83，brief §20.20，`SearchVerdict`）：照 Sonarr 互動搜尋，對不上的也送、每一筆帶理由
  （`verdict` 與 `evidence`：觸發的那一段字），畫面預設只開「符合」。判定順序是證據硬的先：名字對不上（`parser.title.mentions`）
  → 成人分類（Newznab 6000–6999，brief §20.19）→ 不是電影（`parser.misfit`：電影搜尋讀得出季集記號或字幕組的 `- 05`、`[01-12]`）
  → 年份不符（同一支，M4 票 49、brief §20.16：電影差超過一年、劇集看整段播出期間）→ 只對上部分名字（`parser.partial_title`：
  第一個記號前面的片名包住這部作品的名字但不等於它，可能是衍生作品）→ 符合。自己打的關鍵字與沒有快照時一律 `unjudged`，不分類。
  每類各自逐站輪流取：符合與 `unjudged` 100 筆（`RESULT_LIMIT`），其餘每類 50 筆（`OTHERS_LIMIT`）；`counts` 報每一類在每一站的總數。
  **筆數的定義**（M4 票 69、83）：`returned`＝每個查詢回的筆數加總＝`merged`（`_dedupe` 合併掉的）＋Σ`counts.total`；
  畫面一行說回了幾筆與重複的，各類的數字在篩選按鈕上，標頭只說「符合」那一份（「結果表 N 筆」）。
  **解析只跑在送出去的那幾百筆上**（最多 100＋5×50）：`parse_release` 實測每筆 14 毫秒（1200 筆 17.4 秒），
  一次搜尋回一兩千筆，全部解析會把事件迴圈卡住半分鐘。粗篩用 `parser.title.mentions`（純字串）。
- 上限內**逐站輪流取**（`RESULT_LIMIT = 100`），不是取做種前 100 筆：The Pirate Bay 的 scene 發佈有
  28–86 個做種，Mikan 那一千多筆多半是個位數，純做種排序會讓一百筆全部來自同一個站（票 08 實測）。
- `ProwlarrClient`（僅 setup 與健康檢查用）：`system/status` 讀版本（要 API key，下限 1.3.2，§9.5、M4 票 17）、`indexer/schema` 取定義、`indexer` 新增、`indexer/test` 驗證（已加入的站用 `test_indexer`，還沒加入的定義用 `test_definition`——同一支、送的是 schema 原樣，什麼都不建立，M4 票 09，brief §20.7）、`config/host` 設介面登入。拒絕的原文由 `failure_of` 分成 `SiteFailure`（Cloudflare / 查無結果 / 連不上 / 其他）。**新增之前 Prowlarr 會先連一次那個站**，連不上就回 400 加一份逐條理由（`errorMessage`）而且什麼都不建立——逐站的成敗因此來自新增那一支，不是另一次 `indexer/test`；`?forceSave=true` 不會跳過這個檢查。同名的第二個站被拒（`Should be unique`），所以冪等靠先列（2026-09-08 實測，brief §20.7）。schema 給的 `appProfileId` 是 `0`，送回去之前要換成 `1`。

- 逾時：**搜尋**用 120 秒（Prowlarr 的 REST）——`GET /api/v1/search` 要現場去連
  五個追蹤站，2026-09-10 實測單次冷查詢 60–85 秒，三個查詢併發共 35 秒（所以併發是對的，短逾時不是）；
  `services` 另有 150 秒的逐查詢上限，換 adapter 也保證得了畫面
  等多久。新增與驗證索引站要真的連上那個站，用 120 秒；`indexer/schema` 用 60 秒——容器剛起來的第一次呼叫要讀進 627 份定義再組出 5.6 MB 回應，實測 9.42 秒（brief §20.7）。其餘端點用共用的 5 秒探測逾時。
### 8.5 RSS adapter

- `feedparser`（6.0.14）解析；每種來源一個小型 mapper 產 `FeedItem{guid, title, link, torrent_url, magnet, info_hash, size, published_at}`（`adapters/rss/{mikan,nyaa,acgrip}.py`，三站共用 `feed.entries`（認不出 feed 格式是協定不符）與 `approx_bytes`（`MiB` 1024 進位、`MB` 1000 進位）；抓網頁的是 `FeedFetcher`，mapper 是純函式）。欄位從哪裡取（M3 票 07 對 fixture 實跑定下，brief §20.12；逐欄理由見 `docs/research/rss-sources.md` §9，`e` 是 feedparser 的 entry）：

  | 欄位 | Mikan | Nyaa | acg.rip |
  | --- | --- | --- | --- |
  | `guid` | `e.link` 末段的 40 hex（**不用** `<guid>`：它是標題，改標題就變） | `e.id`（`https://nyaa.si/view/<id>`） | `e.id`（`https://acg.rip/t/<id>`） |
  | `link`（單集頁） | `e.link` | **`e.id`**（`e.link` 是下載連結） | `e.link` |
  | `torrent_url` | `e.enclosures[0].href` | `e.link`，不以 `magnet:` 開頭時 | `e.enclosures[0].href` |
  | `magnet` | 無 | `e.link`，以 `magnet:` 開頭時 | 無 |
  | `info_hash`（可空） | `e.link` 末段 | `e.nyaa_infohash.lower()` | `None` |
  | `size`（近似，只供顯示） | 描述後綴 `[N UNIT]` → N × 1000^k（**不用** `contentlength`：不是位元組） | `e.nyaa_size` → N × 1024^k | `int(e.torrent_contentlength)` |
  | `published_at`（aware UTC） | `fromisoformat(e.published)` 補 **UTC+8**（`published_parsed` 當 UTC 讀，差 8 小時） | `e.published_parsed`（UTC） | `e.published_parsed` |

  **自動綁定**（票 09，brief §15「綁定」）：Series 長出來的那一輪抓一次番組頁（`/Home/Bangumi/<id>`，讀中文名與「放送开始」，研究檔 §2.7；同一輪裡同一部的各字幕組共用那一次，讀不到也照同一個結果，M4 票 82），以番組名與發佈名的標題骨幹搜 TMDB（`search/multi`，每個詞取前 3 筆、年份晚於開播的劇集與差一年以上的電影不讀詳情，最多三個詞），讀回快照交給 `parser.binding.judge`。查不到（番組頁或 TMDB）不在之後每一輪重試，理由寫 `lookup_failed`。
  Mikan 的 RSS Series 鍵（番組 id, 字幕組 id）不在 feed 裡：單一 feed 的 URL 帶著；聚合 feed 的每一筆第一次出現時抓一次單集頁，讀 `a.mikan-rss` 的 `href`。Nyaa 的做種數（`nyaa_seeders` 等）不進 `FeedItem`，沒有消費者。
  **非 Mikan 的 RSS Series 鍵**（票 11）：`parser.binding.skeleton` 去掉組名（`parser.cjk` 的讀法）、播出檔期、集號與 tags——組名之後以方括號開頭的，標題就是那一格；區間的 `-` 兩側不許有空白（`Season 3 - 08` 是第三季第 8 集）——`title_key` 再接字幕組。合集照樣長在同一組的 Series 上，由排除條件擋下。這些來源沒有番組頁，自動綁定的線索只有發佈名：`judge` 列出候選、理由 `no_show_page`，一律留給人。
  **第一輪預覽**（票 11，brief §15、`.scratch/m3/preview-shape.md`）：`primed_at` 是 `NULL` 的 Feed 照樣寫 Item、長 Series、看排除條件，但 `_submit_waiting` 只送選過的 Feed——輪詢、綁定、自動綁定三條送單的路一起擋住。「全部下載」寫 `primed_at` 之後當場送綁好的；「只追之後的」**當場再讀一次 feed**，那一刻還沒送的（待綁定、綁好）都改 `passed`，之後才出現的照常送——只看已經寫下的 Item 的話，第一輪沒讀到 feed 或預覽之後才出現的那幾筆下一輪會被當成新的整批送出。
- 去重鍵：`(feed_id, guid)`；**跨 feed 以 `info_hash` 去重，做**（票 07 結論）：Mikan 與 Nyaa 在輪詢時就有 hash，比對 `rss_items.info_hash` 與 `jobs.hash`；acg.rip 不在輪詢時預抓 `.torrent`——送單時 `TorrentFetcher` 本來就要下載並算 hash，`jobs.hash` 是主鍵，算出來之後寫回 `rss_items.info_hash`，Job 已存在就標成重複。所以不多發請求。同一個發佈在兩站是不是同一個 hash 沒有證實，不同時由帳本「同 Media / 季 / 集 / Tags」那一層擋。
  **票 10 的實作**（`services/rss._held_back`，送單前）：info hash 那一層看 Job 在不在（連 `removed` 的一起算：不讓 `add_download` 每一輪回一次 `job_removed`）與另一筆 Item 送過沒有（Job 連紀錄清掉之後不從另一個 Feed 抓回來）；來源不報 hash 的由 `add_download` 回的 `created = false` 認出，算出來的 hash 寫回 `rss_items.info_hash`。**同一個 RSS Series 自己送的不算重複**（`_sent_before`：Job 的 `trigger_ref` 是它、不是 `removed`、沒有別筆 Item 認領那一筆 Job——Job commit 之後 Item 改狀態之前中斷、刪掉 Feed 再加回來），認回成 `downloaded`。帳本那一層以規劃時同一份 `parse_context` 與 `parser.planner.plan`（發佈名當 torrent 名、配一個中性的檔名）猜季集，猜不到或信心不夠自動入庫的不擋——規劃時的 `_against_ledger` 照樣會比；**Tags 比兩處**：帳本那一列的 Tags（從檔名讀）與那一列 Job 的發佈名算出的 Tags（字幕組常在檔名寫另一個組名，只比前者的話同一個發佈換 hash 重新上傳就認不出來；讀不出字幕組的標題不比這一半，空對空不是同一個版本）。解除綁定時 `in_library` 的重複回到待綁定：它是對綁上的那一部作品說的。**排除條件**（`parser.exclusion`）：規則格式照 Sonarr 的 release profile（一般字詞不分大小寫的子字串，`/…/` 正則、`/…/i` 不分大小寫），合集那一條是全域的開關、看解析器的 `release_kind`。

### 8.6 fs adapter

- `link(src, dst, roots)`、`stat`、`same_inode`、`link_test(source_dir, target_dir, roots)`（建暫存檔、鏈接、比對、清理）、`probe_file(dir, roots)`（context manager：放一個探測檔，離開就刪）、`free_space(path)`、`is_within(path, root)`（防路徑逃逸）、`ensure_directory(path)`。
- 所有寫入 library 的路徑必須在某個 Route 的 `target_path` 之下，否則拒絕；這是唯一會動 library 的模組。**凡是把檔案放進去的函式都要 `roots`**（`link`、`probe_file`、`link_test` 的目標側），不在其中就丟 `PathEscapeError`。`ensure_directory` 不在此列：它建的是 Berth 自己的根目錄（媒體庫目錄、complete 子目錄），那些是設定值不是算出來的檔名。
- `OSError` 一律往上丟（含 `errno`）：權限、掛載、`EXDEV` 的原文正是「哪個容器少了哪個掛載」唯一有用的證據。**`EXDEV` 另外說出兩邊各落在哪個掛載上**（仍是同一個 `errno` 的 `OSError`，只是訊息多一段；`mount_point()` 對還不存在的目標也答得出來），系統原文只說「跨裝置」（票 12）。
- `link()` 順手建好目標那幾層資料夾（`<作品>/Season 01/` 第一次一定不存在），**守衛在建資料夾之前**：被擋下來的那一次不在媒體庫外留下空目錄。目標已存在時丟 `FileExistsError`，由 importer 比 inode 決定是「上次做到了」還是「別人的檔案」——不先 `exists()` 再鏈接，否則守衛會被繞過（票 12）。

### 8.7 mediainfo adapter

- `probe(path) -> MediaInfoSummary{duration_s, width, height, video_codec, bit_depth, audio_langs, subtitle_tracks[{lang, title, codec, forced, default}]}`。
- 只在 planning 階段對影片檔呼叫；失敗不阻擋，Plan 只少一個訊號。量到的片長有兩個消費者：`classify` 的 5 分鐘規則與片長驗證（§4.1）。

---

## 9. 開箱即用

目標（brief §16.3）：`docker compose up` 之後只操作 Berth 就完成全部設定。事實依據見 brief §20.7。

### 9.1 套件內容（`deploy/`）

| 服務 | Image | 掛載 | 備註 |
| --- | --- | --- | --- |
| `berth` | `ghcr.io/<owner>/berth` | `${CONFIG_ROOT}/berth:/config`、`${DATA_ROOT}:/data`、`${CONFIG_ROOT}/prowlarr:/ext/prowlarr:ro` | port `${BERTH_PORT}:8383`；`PUID` / `PGID` / `TZ`，加上 `JELLYFIN_PORT`、`QBITTORRENT_WEBUI_PORT`（深連結的 port、套件內 qBittorrent 的位址，`config.py`）；唯讀掛 Prowlarr 設定以讀取其 API key |
| `qbittorrent` | `lscr.io/linuxserver/qbittorrent` | `${CONFIG_ROOT}/qbittorrent:/config`、`${DATA_ROOT}:/data`；預置腳本以頂層 `configs` 寫進 `/custom-cont-init.d/10-berth.sh`（`mode: 0555`） | port `${QBITTORRENT_WEBUI_PORT}`（WebUI）、`${QBITTORRENT_BT_PORT}`（BT，TCP 與 UDP），**兩者都是內外兩側同一個號碼**，並設成 `WEBUI_PORT` / `TORRENTING_PORT`；預置腳本見 §9.2 |
| `jellyfin` | `lscr.io/linuxserver/jellyfin:version-12.1ubu2604`（釘在 12.1 這條線，brief §19；票 14b 改的） | `${CONFIG_ROOT}/jellyfin:/config`、`${DATA_ROOT}:/data` | port `${JELLYFIN_PORT}:8096` |
| `prowlarr` | `lscr.io/linuxserver/prowlarr` | `${CONFIG_ROOT}/prowlarr:/config` | port `${PROWLARR_PORT}:9696` |

- 選 linuxserver 系列 image 的理由：四個容器都支援 `PUID` / `PGID` / `UMASK`，檔案擁有者一致；qBittorrent 官方 image 沒有這兩個變數（brief §20.7）。
- compose network `berth` 指定固定子網 `172.28.0.0/16`，`berth` 容器再固定在 `172.28.0.2`（`ipv4_address`），qBittorrent 的免密白名單就寫這一個位址的 `/32`。**白名單不能放整個網段**：Docker Desktop 把發佈 port 進來的流量的來源位址改寫成閘道 `172.28.0.1`，而閘道也在網段內，開放整段等於 LAN 上任何人都能免密打 qBittorrent 的 API（2026-09-07 實測，見 brief §20.7）。動態配發用 `ip_range: 172.28.1.0/24` 隔開，`berth` 的固定 IP 才不會被先啟動的容器領走。
- 三個外部服務在 compose 內各有 healthcheck（qBittorrent 打 WebUI 首頁、Jellyfin `/health`、Prowlarr `/ping`）；`berth` 的 healthcheck 在 image 的 `HEALTHCHECK` 裡，用 venv 的 python 打自己的 `/api/health`。
- image 是多階段 build：`node:24-slim` 產出前端靜態檔 → `python:3.13-slim` 用 uv 把 venv 建在 `/app/.venv` → runtime 只複製 venv 與 `dist`。非 root 執行：入口腳本以 root 起，用 `usermod` / `groupmod` 把內建的 `berth` 使用者對到 `PUID` / `PGID`，遞迴 chown `/config`，再 `setpriv` 降權 exec。`/data` 只在它還是空目錄時接手擁有者（Docker 替 bind mount 新建的目錄是 `root:root`），已經有內容的媒體根一律不碰。
- `.env.example`：`DATA_ROOT`、`CONFIG_ROOT`、`PUID=1000`、`PGID=1000`、`UMASK=022`、`TZ=Asia/Taipei`、五個對外 port（`BERTH_PORT=8383`、`JELLYFIN_PORT=8096`、`QBITTORRENT_WEBUI_PORT=8080`、`QBITTORRENT_BT_PORT=6881`、`PROWLARR_PORT=9696`）、`COMPOSE_PROFILES=jellyfin,qbittorrent,prowlarr`。沒有任何秘密要填。compose 裡每個 port 變數都有同值的預設，舊的 `.env` 照樣能用；`tests/unit/test_deploy_ports.py` 守著五個變數都在、都被用到、兩個傳給 `berth`、qBittorrent 內外一致。
- **`.env` 只放 Berth 在容器裡看不到的宿主端事實，也就是這五個 port**（brief §19 2026-09-24）；服務位址與憑證、下載目錄與媒體庫根、Route、對外網址、磁碟門檻都在精靈與設定頁。套件內 Jellyfin 的深連結（brief §12 推導第 3 條）用 `JELLYFIN_PORT`，不從 `base_url` 取 port——那是容器內的 8096。
- `jellyfin`、`qbittorrent`、`prowlarr` 各掛在同名 profile 下，`berth` 永遠啟動；已有某服務的人把它從 `COMPOSE_PROFILES` 拿掉，在精靈那一頁選「既有」（§9.3、§9.5）；選既有時頁面說出要拿掉哪一個，忘了拿掉也不致命。
- **容器名加 `berth-` 前綴**（brief §19 2026-09-29，M4 票 16）：`container_name` 是 `berth-jellyfin` / `berth-qbittorrent` / `berth-prowlarr`，`berth` 維持；compose 服務名（也就是 compose 網路上的 DNS 名 `jellyfin`、`qbittorrent`、`prowlarr`）不變。同一台主機上既有的容器多半就叫那三個名字，沒有前綴時撞名會讓 `docker compose up -d` 連 `berth` 在內整套都起不來；撞 port 仍可能發生，只有那一台起不來（票 16 實測，brief §20.14）。`tests/unit/test_deploy_names.py` 守著容器名、服務名、profile 與下一條的 `extra_hosts`。
- **`berth` 服務帶 `extra_hosts: ["host.docker.internal:host-gateway"]`**（M4 票 16）：Linux 上 Berth 才連得到宿主上的既有服務；Docker Desktop 本來就有這個名字（§9.5〈連線位址〉）。
- Windows：`DATA_ROOT=C:\Berth\data` 這種路徑可直接寫在 `.env`，Docker Desktop 會以 9p/drvfs 掛進容器；實測 NTFS bind mount 的硬鏈接可用（brief §20.7）。exFAT 隨身碟不支援硬鏈接，`docs/guide/requirements.md` 明說。`PUID` / `PGID` 在 Windows 掛載上沒有意義，保留預設即可。
- 只有一份 `docker-compose.yml`，Linux 與 Windows 共用；`.env.example` 內附兩種路徑寫法的註解。
- **部署只有 compose 檔加 `.env`**（M4 票 71，brief §19 E4 2026-10-09 推翻 release 附件，§20.18）：使用者把兩個檔貼進 Unraid 的 Compose Manager（檔案在隨身碟上）或放進任何資料夾，旁邊不放別的東西。所以 compose 裡的宿主路徑一律是 `${CONFIG_ROOT}` / `${DATA_ROOT}` 開頭或絕對路徑（`tests/unit/test_deploy_mounts.py` 守著），預置腳本內嵌在 compose 裡（§9.2），`.env.example` 寫明 Unraid 上兩個根要用絕對路徑。README 連到**這一版的 tag** 底下的原始檔（`raw.githubusercontent.com/1morr/Berth/v<版本>/deploy/...`），不指 `main`，compose 才不會比 `:latest` 的 image 新；`tests/unit/test_readme_docs.py` 守著連結的 tag 等於 pyproject 的版號。Release 頁只放 CHANGELOG 那一段，不附檔案；需要 Compose 2.23.1 以上（`configs.content`）。
- incomplete / complete 根目錄固定在 `/data/torrent/{incomplete,complete}`（`PathSettings` 的預設值，沒有 API 或 UI 改它，M4 票 22）；媒體庫路徑讀自 Jellyfin。要換宿主上的位置改 `DATA_ROOT` 掛到哪裡，容器路徑不變。
- 目錄骨架由 Berth 啟動時建立：`<complete root>/..`、`<incomplete root>`。套件內 Jellyfin 的媒體庫目錄（`<library_root>/<資料夾>`，預設 `movies` / `tv` / `anime`）在精靈的媒體庫與路徑頁建立媒體庫之前才建（§9.4 第 4 步）。

### 9.2 預置設定

預置的原則：**只放沒有它 Berth 就進不去的東西**，其餘一律由精靈按鈕經 API 完成、按前顯示差異、可重按。

**qBittorrent**（compose 頂層 `configs.qbittorrent-preseed` 的 `content`，Compose 建容器時寫成 `/custom-cont-init.d/10-berth.sh`、`mode: 0555`；linuxserver 的 `custom-cont-init.d` 機制，在服務啟動前執行，只跑有執行位元的檔，brief §20.18）：在 `/config/qBittorrent/qBittorrent.conf` 的 `[Preferences]` 補上這兩個鍵，**已經有值的鍵一律不動**：

```ini
WebUI\AuthSubnetWhitelistEnabled=true
WebUI\AuthSubnetWhitelist=172.28.0.2/32
```

- 為什麼非預置不可：4.6.1 起首次啟動的隨機密碼只印在容器 log，Berth 沒有 docker socket 讀不到；要使用者去 `docker logs` 抄密碼正是要避免的事。
- 為什麼是「缺鍵才補」而不是「檔案不存在才寫」：linuxserver image 自己的 `init-qbittorrent-config` 排在 `init-custom-files` 之前，已經把 `/defaults/qBittorrent.conf` 複製進 `/config`，所以「不存在」永遠不成立；整份覆蓋會掉 `LegalNotice\Accepted=true` 這類讓 qbittorrent-nox 起得來的鍵（2026-09-07 實測，brief §20.7）。缺鍵才補同時滿足冪等：重建容器不會改動任何既有內容。
- 白名單是 `/32` 不是整個網段，理由見 §9.1；`berth` 的 IP 由 compose 固定並用環境變數 `BERTH_IP` 傳給腳本，避免兩處寫死。
- `WebUI\ServerDomains` **不預置**：linuxserver image 的預設值是 `*`，Host 檢查本來就過得了；寫成 `qbittorrent` 確實讓 `http://qbittorrent:8080` 通過，但同時讓使用者從 `localhost:8080` 與 `127.0.0.1:8080` 都吃 401（2026-09-07 實測，brief §20.7）。也**不需要** `HostHeaderValidation=false`。
- **qBittorrent 的 WebUI port 內外兩側一起換**：Host 檢查除了網域還比對 port，`*` 也不放過 port 不符。發佈成 `18080:8080` 之類的偏移，使用者開 `localhost:18080` 會直接吃 401，而原因只寫在容器 log 裡（brief §20.7）。所以 compose 以 `QBITTORRENT_WEBUI_PORT` 同時設發佈的兩側與 `WEBUI_PORT`，compose 內網上那一台也跟著在這個 port；Berth 從同名環境變數組出偵測的位址（`http://qbittorrent:<port>`），判成套件內之後第 4 步與 Route 檢查連的是判定記下的那一條。**不預置 `HostHeaderValidation=false`**：它是防 DNS rebinding 的那一道，內外一致之後本來就用不到。README 的疑難排解有這一條。
- save path、autoTMM（`DisableAutoTMMByDefault` 預設 `true`，即關閉）、temp path 都**不預置、也不套用**（M4 票 22、32）：Berth 送單時逐個 torrent 帶 `autoTMM=true`，路徑與未完成目錄開在 Berth 的分類上，所以全域預設值不影響正確性。密碼不預置，由精靈 qBittorrent 頁設（§9.3）。
- 使用者在 qBittorrent 介面改任何東西都可以，Berth 不看它的全域偏好。
- **缺鍵才補的另一面：在 WebUI 關掉或改掉白名單，重啟補不回來**（M4 票 53 實跑，brief §20.7）。所以套件內 qBittorrent 回 `auth_required` 時，補法說 WebUI「選項 → WebUI → 驗證」那一格（`connection.fix.whitelist`），不給重啟指令：重啟只在兩個鍵整個不在設定檔裡時有用，照著按多半白跑。兩個鍵整個不在的那一種是 compose 沒完整複製、腳本根本沒跑（漏了 `configs` 或 `mode`，log 只有一行 `is not an executable file`）：同一句接著說重新完整複製 compose、`up -d --force-recreate qbittorrent`（M4 票 71）。

**Prowlarr**：不預置。Berth 從唯讀掛載的 `/ext/prowlarr/config.xml` 讀 `<ApiKey>`（Prowlarr 首次啟動自動產生）；讀不到時精靈退回手動貼上。也支援 `PROWLARR__AUTH__APIKEY` 環境變數的部署方式。

**Jellyfin**：不預置，全部走 API（§9.4）。

### 9.3 精靈流程

> **2026-09-29 改（brief §19「精靈改為每個服務手動選擇」）**：Jellyfin、qBittorrent、Prowlarr 各一頁，使用者手動選「套件內」或「既有」，拿掉「偵測服務」那一步，Prowlarr 與索引站併成一頁。M4 票 15 做完了選擇、服務頁與頁序，16（compose）、17（既有服務防呆）、08（媒體庫與路徑按鈕觸發）、09（Prowlarr 頁的索引站先測再加）也做完了。舊的八步全文見 `git show bd4216b:docs/plan.md` 的 §9.3。
>
> 2026-09-26 改：第 1 步改為連 Jellyfin、成為擁有者（M4 票 06）；套件內 qBittorrent / Prowlarr 的介面登入在各自的泊位（M4 票 07）。

每一頁都是冪等的 `services/setup.py` 命令；精靈跑完之後設定頁呼叫的是同一批命令（票 06i）。**來源由使用者逐服務選**（brief §16.3）：三個服務每一個不是「套件內」就是「既有」，可任意組合。選擇存在 `settings.setup.choices`（§2.1），從此「套件內 / 既有」由它決定——取代偵測判定（票 15 刪掉了判定、釘住、`POST /setup/detect` 與 `probe_targets`）。票 05 的保護（既有服務不寫帳密、不改全域偏好、不替它加站）保留，改讀選擇；**還沒選的服務，寫入它的命令一律拒絕**。

| 頁 | 泊位 | 做什麼 | 要先有 |
| --- | --- | --- | --- |
| 1 | Jellyfin（BTH 1） | 選來源 → 建立管理員或以管理員登入 → 擁有者 → Berth 建 API key；建套件內那一台的管理員時預設勾「套件內 qBittorrent 與 Prowlarr 也用這組」（M4 票 40） | 無 |
| 2 | qBittorrent（BTH 2） | 選來源 → 測試（連線、版本，再問它看不看得到 `/data`，M4 票 46）→ 套件內設 WebUI 登入（那一台自己設過就不必）；既有填位址與 WebUI 帳密，測試通過即完成 | 擁有者 |
| 3 | 媒體庫與路徑（BTH 3） | 套件內建媒體庫 / 既有加 Berth 路徑 → Route → 每一條檢查；套件內第一次來、清單沒改過時進頁自動跑（M4 票 43），其餘按鈕觸發 | Jellyfin、qBittorrent |
| 4 | Prowlarr 與索引站（BTH 4） | 選來源 → 套件內讀 key、設介面登入、挑索引站 / 既有貼 API key | 擁有者 |
| 5 | TMDB（BTH 5） | 貼 key、測試 | 擁有者 |
| 6 | 完成 | 說出跳過了什麼、之後拿什麼登入（套件內兩台的介面登入照 `web_ui_login_by_berth` 說是精靈設的、原本就有的或還沒設，M4 票 40） | 前五頁照頁序再問一次（M4 票 31） |

媒體庫與路徑維持在 qBittorrent 之後、Prowlarr 之前（票 06d：它只依賴 Jellyfin 與 qBittorrent，掛載設錯是最常卡住的地方，越早知道越好；2026-09-29 使用者再確認）。Berth 沒有自己的帳號頁（brief §11）。

**服務頁的共同形狀**（頁 1、2、4）：

- **頁首二選一**「套件內」/「既有」（Seerr 與 Sonarr / Radarr 都是手動填、按 Test，brief §20.14），**不預選**（票 15 shape 時使用者拍板：猜錯正是這一輪要消滅的；`.scratch/m4/service-pages-shape.md`）。點「套件內」就存下並測（唯讀；qBittorrent 的測試另外放一個當場收掉的探針，M4 票 46）；點「既有」只展開表單，按「測試連線」才存下並測。**送出那一刻就有回饋**（M4 票 80）：回來之前被點的那一格就是選中的、另一格停用（不送第二個），套件內第一次選先畫一條與連線列同形的「測試中」加一句「正在設定套件內 X，連線測試中…」，讀屏由同一個宣告區說；回來時同一個位置換成結果。「既有」旁說明條件：Jellyfin 與 qBittorrent 要與 Berth 在同一台主機、把 Berth 的 `DATA_ROOT` 也掛在容器路徑 `/data`（只能是 `/data`，原本的掛載不動；`DATA_ROOT` 要建得了硬鏈接；既有 Jellyfin 要先有對應類型的媒體庫，M4 票 36，brief §16.4；Prowlarr 不碰檔案，沒有這一條）；選既有時說出要從 `.env` 的 `COMPOSE_PROFILES` 拿掉哪一個（`jellyfin` / `qbittorrent` / `prowlarr`），**再給 `docker compose stop <服務>`**——只改 profile 再 `up -d` 停不掉已經在跑的那一台（M4 票 36，brief §20.14）。不叫人改 compose 檔，忘了也不致命。**「既有」說明不多說撞 port 的事**（票 16 實測，brief §20.14）：容器名改成 `berth-*` 之後撞名消失；撞 port 時只有撞到的那一台套件內容器停在 `created`，`berth` 與其他照常跑，而那個錯在終端機跑 `docker compose up -d` 時就印出來、早於精靈，起不來的正是使用者不要的那一台。疑難排解寫在 README〈部署疑難排解〉。
- **套件內**連 compose 主機名（`services.clients.bundled_targets`：`jellyfin:8096`、`qbittorrent:${QBITTORRENT_WEBUI_PORT}`、`prowlarr:9696`；compose 服務名不變，容器名是 `berth-*`，票 16）。**既有**填位址與那個服務要的憑證（brief §16.4）：Jellyfin 的管理員帳密、qBittorrent 的 WebUI 帳密、Prowlarr 的 API key。填 `localhost` / `127.0.0.0/8` / `::1` 時位址欄下就地提示改成 `host.docker.internal` 或區網 IP（票 17：前端純函式 `setup/loopback.ts` 的 `pointsAtBerth`，只提示不擋；測過的位址是它而連不上時，補法說同一句）。「既有」選項旁說出版本下限（Jellyfin 12.0 連到 12.0 發佈文的升級注意、qBittorrent 4.4、Prowlarr 1.3.2）。
- **進頁只查主機名**（M4 票 30，brief §19 2026-10-01）：服務頁進頁問 `GET /setup/compose`，Berth 解析三個套件內主機名（`services.setup.resolve_bundled` → `adapters.dns`，`getaddrinfo`、10 秒上限、逾時當作解得到），**不造任何服務的 client**——這不算「選之前發請求」。解不到的那一張「套件內」卡片寫「這套 compose 的 X 沒在跑」：停掉的容器與不在 `COMPOSE_PROFILES` 裡的服務一樣解不到、分不出來（不另外掛 Docker socket），所以還沒選時卡片下兩種補法都給——停了就 `docker compose start X`，不在就加回 `COMPOSE_PROFILES` 那一行再 `docker compose up -d`（M4 票 35）；不預選、不停用，選了照舊測（紅的是下面那一條 `not_deployed`，補法是同一組 `bringBack`）。那一頁每次選擇或重新測試完都再問一次主機名，起回來、測試轉綠之後加註跟著消失（票 35）。
- **選完就測，不偵測；既有的測過才存**（M4 票 45，審計 E-6；Home Assistant 驗過才 `create_entry`、Sonarr 存之前再測一次）：套件內的選擇與連線資訊先存進 `settings.setup` 與它們平常住的 `settings.services.*` 再測（位址是 compose 主機名，啟動中要靠存下的選擇輪詢）。**既有的先拿表單那一組測，測過才存**；測不過是 400 `connection_failed`（`setup.ConnectionFailedError`），**什麼都不存**——選擇、連線、那一頁的結果、Route 檢查都還是原本的，已經有一台測過的在用時照舊用它（原本測不過也存，設定頁打錯一個字下載就停擺）；那一次的結論帶在拒絕的 `attempt`（`ServiceOut` 同形狀），前端標在欄位上（見〈錯誤分三層〉）。改一格再按靠的是表單留著打的字。例外是擁有者之後 Jellyfin 的 `auth_required`：說的是 Berth 自己那一把 key，位址已經答出 ServerId，照樣存下（擁有者重新登入要有地方送）。套件內測不過要分開說：
  - 主機名解不到（`socket.gaierror`）＝那個服務的容器沒在跑或不在 compose 裡（停掉的容器不在 compose 的網路上，解不到的是同一件事，M4 票 25 實測 B9）→ 兩種補法並列（分不出是哪一種，M4 票 35）：停了就 `docker compose start qbittorrent`；不在的話把 `qbittorrent` 加回 `.env` 的 `COMPOSE_PROFILES` 再 `docker compose up -d`。
  - 解得到但連不上、回 503「載入中」、回的東西不像它自己（`protocol_mismatch`）＝容器還在啟動 → 照舊每 3 秒再測、到 2 分鐘上限（M3 票 06g 量到的三種樣子），逾時給重試；過了上限仍是 `protocol_mismatch` 就說那個主機名上是別的東西。
  - **位址的協定寫錯不是連不上**（M4 票 25）：`https://` 打到講 http 的 port（Jellyfin、Prowlarr 回 HTTP 400，握手讀到它而 `WRONG_VERSION_NUMBER`；qBittorrent 不回、握手逾時，鏈上是 `SSLWantReadError`，brief §20.14；`adapters.http.SchemeMismatchError`）是 `scheme_mismatch`，說「這個 port 講的是 http」；沒寫 `http://`（httpx 的 `UnsupportedProtocol`，`SchemeMissingError`）是 `scheme_missing`。兩者都不等、當場紅，纜繩的代碼同名。反方向（`http://` 打到講 https 的 port）認不出來：實測伺服器只是重設連線，與別的斷線分不開，照舊是 `unreachable`。位址欄送出前先驗（`setup/address.ts`），照 *arr 不自動補，直接說要以 `http://` 或 `https://` 開頭。
  - 既有的當場給結論。版本低於下限（Jellyfin 12.0、qBittorrent 4.4、Prowlarr 1.3.2，brief §20.14）停在這一頁，說出「至少要 X，這一台是 Y」（Jellyfin 附升級注意，brief §20.9）。**Jellyfin 的版本在測試時就擋**（`version_unsupported`，M4 票 18；原本到登入才 502），套件內那一台太舊也當場紅；登入那一段的版本閘門留著當後備。
- **表單跟著那一台的狀態走，選擇決定 Berth 之後寫什麼**（brief §16.3）：套件內但已經初始化過（重裝保留 config、精靈中途中斷）時，Jellyfin 已有管理員就給登入表單、不再建立；qBittorrent / Prowlarr 已設過介面登入就不強迫再設（「已設過」各怎麼認由票 15 查證）。選既有而那台 Jellyfin 還沒跑過初始精靈時，一樣給建立管理員的表單——它上面沒有任何人的帳號可以蓋掉。
- **點選才算數，方向鍵只是瀏覽**（M4 票 09，票 15 audit 的 P2）：radio 在兩格間移動就會選中，而選中「套件內」原本就是一次存下與測試。只有指標點下去的那一次當場送（方向鍵與空白鍵不送 pointerdown）；鍵盤選到的是草稿，另給一顆「使用套件內的 X」。草稿由頁面持有（`setup/choiceDraft.ts`），**標題與 lede 在確認之前就跟著草稿**。
- **回頭改選擇**（票 15 shape 時使用者拍板）：**Jellyfin 在擁有者成立之後鎖住來源與伺服器**——擁有者是那一台上的帳號，換一台等於換擁有者；改來源後端回 409（`ChoiceRefusal.jellyfin_owned`）。位址換得了，**但只能換到同一台**（M4 票 18）：新位址先測，`/System/Info/Public` 的 `Id`（ServerId，brief §20.15）要與擁有者成立時記下的（`settings.setup.owner.jellyfin_server_id`）相同才存，然後以 Berth 的 key 打 `/Auth/Keys` 重驗——被撤了測試紅在 `auth_required`，擁有者就地重新登入換一把（頁 1 與設定頁都有那一格）；另一台是 409 `other_server`；既有的新位址不回答是測過才存的 400 `connection_failed`、標在位址欄（M4 票 45），套件內 compose 位址換了而不回答、或原本那一台認不出（票 18 之前的擁有者）是 409 `unverified`；都什麼都不存。存下的位址後面換成另一台時，重新測試紅在 `other_server`。票 18 之前成立、沒記 ServerId 的擁有者，下一次測到的那一台就記成它。設定頁的連線區走同一支，但不畫二選一：Jellyfin 是唯讀摘要（來源、位址、版本、狀態與換不了的理由），既有的那一台多一顆「改位址」（M4 票 78，`settings/JellyfinConnection.tsx`）。**qBittorrent / Prowlarr 隨時可改**：這一頁有結果時換另一格先就地確認（`ConfirmPanel`：焦點進去、Esc 收起回到原本那一格；換成既有時後果、表單與取消在同一個確認區，按「測試連線」就是確認），說出這一頁要重做，並**列出 Berth 在原本那一台擁有的物件**（M4 票 47，brief §16.4〈換一台時〉：`berth-*` 分類與 torrent 數、Berth 加的站、Berth 設的介面登入；連不到時列 Berth 記得的，可一鍵移除空的 `berth-*` 分類；`setup/LeftoverList.tsx`）。頁 2 選過一台就先確認（原本看頁 2 的纜繩，既有的那一台自票 38 起沒有纜繩，換走時一句都不說）；換了之後那一頁的結果清掉重做（`setup._start_over`）。qBittorrent 換了，所有 Route 的檢查標成未檢查、逐條明細一起清掉（`routes.forget_route_checks`：分類建在原本那一台上；明細留著的話畫面寫「尚未檢查」卻仍是上一台的通過數與錯誤，M4 票 24），頁 3 要重新檢查才走得過去。
- **錯誤分三層**（M4 票 21，`.scratch/m4/error-layers-shape.md`，照 Home Assistant config flow 與 *arr：已知的失敗用代碼、前端翻成人話、掛在造成它的那一條上）：後端的失敗回封閉的代碼加少量參數——纜繩是 `SetupStep.failure` / `params`（`StepFailure`，`services.steps.failure_of` 照 adapter 的例外分類；Berth 自己判斷的丟 `StepFailedError` 帶代碼），連線測試是 `ConnectionReason`，讀清單與讀差異的失敗是 `failure`，對 Berth 自己的請求照狀態碼分（`requestProblem`：送不到 / 422 / 409 / 其餘；**門禁的 401 / 403 各一句**，M4 票 25：前端的 client 一律帶 CSRF 標頭，所以擁有者成立之後的 403 只會是不是管理員——讀不到精靈狀態時說「精靈只有 Jellyfin 管理員能繼續」並給登出；擁有者成立之前的 403 是門禁的「先做完頁 1」，當成與現狀衝突；401 時這一頁還以為沒有擁有者（頁 1 的擁有者表單）就是擁有者在別處搶先成立了，其餘是登入失效，兩者都給登入連結，按下先重問 `/health` 再去登入頁）。畫面一句人話（發生什麼）在上，補法照代碼與來源挑（`docker compose` 指令只給套件內那一台），**原文、HTTP 狀態、端點、`dev=` / `inode=` 收進預設收起的「技術細節」**（`TechnicalDetails`；通過的那一列在行尾，失敗的在補法之後）。認不出的例外是 `unexpected`，原文照樣在技術細節。`web/eslint.config.js` 擋精靈、設定頁與健康頁把 `.error` / `.message` 直接畫成子節點（`src/lint.test.ts` 雙向驗）。**換來源、換位址、按重新測試、改表單的一格時，那一格上一次的結果與錯誤不畫**（`SetupPage.forgetResults`、測試中不畫上一次的理由、介面登入的 `edits`）；服務頁上選著、還沒存下的那一格由 `SetupPage` 持有，泊位板跟著它。**qBittorrent 的版本也在測連線時擋**（`version_unsupported`，與 Jellyfin、Prowlarr 同一個時機；原本連線卡綠、泊位卡紅）。**連錯預警**：`SetupQbittorrent.auth_failures` 以位址為鍵，數 Berth 對那個位址連續幾次帳密不被接受（同一個位址改帳密再測接著數、成功歸零、別的位址各數各的；**跟著位址、不跟著選擇**——測不過的那一次不存，次數照樣記，M4 票 45），第 3 次起在密碼欄下說「再錯 N 次會被封」；被封了說等 60 分鐘或重啟 qBittorrent（brief §20.2）。**既有表單測不過的錯誤標在欄位上**（M4 票 45，Sonarr 與 Home Assistant 的 `errors[欄位]`；`setup/signals.connectionField`）：位址類（`unreachable`、`not_deployed`、`scheme_*`、`protocol_mismatch`，填 localhost 的那一句也在這裡）標在位址欄，憑證類（`auth_required`、`ip_banned`、`api_key_missing`）標在憑證欄——qBittorrent 帳號、密碼兩格都標、那一句寫一次、兩格的 `aria-describedby` 都指到它；Jellyfin 的表單只有位址，它的 `auth_required` 不算。其餘（版本太舊等）在表單裡、送出鍵之上。那一句與連線卡紅燈的補法同一句；下面說「這一組沒有存下」（已經有一台在用時說它照舊在用）與預設收起的技術細節。連線卡（`TestLine`）畫的是存下的那一台。
- **「已經設過介面登入」怎麼認**（票 15 查證，brief §20.14）：qBittorrent 的 `app/preferences` 讀不到密碼，只有 `web_ui_username`——全新的那一台是 `admin`，所以帳號不是 `admin` 就當設過了，還是 `admin` 的一律當沒設過；Prowlarr 的 `config/host` 全新是 `authenticationMethod: none`、帳號空白。設過的那一台，頁上說出帳號、給「更換登入」，不強迫再設。

1. **Jellyfin**（擁有者；M4 票 06、15，brief §11、§19；Seerr 的慣例：先連媒體伺服器，它的管理員就是擁有者）。
   - 選來源、測試照上面的共同形狀。沒有「先探一下 Jellyfin」：選了才測。
   - **還沒跑過初始精靈**（`StartupWizardCompleted=false`）：「建立 Jellyfin 管理員」，帳號、密碼、再輸入一次（前端比對，Jellyfin 自己的啟動精靈也是），文案說明 Berth 沒有自己的帳號、之後登入 Berth 就用這一組。**已經有管理員**：「用你的 Jellyfin 管理員登入」，密碼一次（`SetupStatus.owner_signs_in`）。
   - `POST /setup/owner` → `services.setup.claim_owner` → `jellyfin.claim_jellyfin`：建立跑 §9.4 的前六步（版本、語言、建管理員、遠端存取、完成初始精靈、登入換 API key），登入跑版本與登入換 key。**帳密一律交給 Jellyfin 驗**，即使已經有一把 key；不是管理員就拒絕（`OwnerRefusal`：`jellyfin_unresolved` 409、`invalid_credentials` 401、`not_administrator` 403、`jellyfin_failed` 502 帶原文、`target_changed` 409）；**帳密只送到畫面上測過的那一台**（M4 票 28）：body 帶 `GET /setup/status` 那一列的 `base_url` 與 `server_id`（`ServiceTest.server_id`，brief §20.15），與存下的選擇不同（或存下的那一次沒記到 ServerId）就 409、Jellyfin 一個請求都不發；比對過之後序列釘在那個位址上（`JellyfinTarget`），第一步答的 ServerId 不同就停在帳密那幾步之前，收尾時位址已被改選就不把換來的 key 寫給新位址，寫擁有者時在寫鎖內再比一次位址，也再確認還沒有擁有者（兩人同時送，後寫的 409 `owner_exists`）。前端的表單以 `base_url`＋`server_id` 為 key：畫面重讀到另一台時打好的帳密清掉；`target_changed` 的那一句旁有「重新測試」；**擁有者已經在是 409 `owner_exists`**，登入中的管理員也一樣（M4 票 18）——換 key 的重新登入是 `POST /setup/jellyfin/connect`。建立時的語言與地區、遠端存取由 body 帶（`ui_culture` / `metadata_language` / `metadata_country` / `remote_access`，§9.4 第 2、5 步）。成功時 `settings.setup.owner` 記 Jellyfin 的 user id、名字與 ServerId，並發 Berth session（與 `/auth/login` 同一種 cookie，`auth.open_session`）。Berth 自己建 API key「Berth」（§9.4 第 7 步），使用者不必貼 key。畫面照〈前端的導覽〉停在結果上（「擁有者：名字」），按了才去下一頁。
   - **帳密不存下來**：只用來建立或登入 Jellyfin、換 API key（M4 票 06 的 migration `e8a1c4d7b293` 拿掉了舊的 `SetupAdmin`）。
   - **門禁**（`api/gate.py`）：擁有者成立之前只開精靈的開場（`SETUP_OPENING_PATHS`：`GET /setup/status`、`GET /setup/compose`、`POST /setup/services/jellyfin` 與它的 `/test`、`POST /setup/owner`），其餘 `setup/*` 一律 403「先做完第 1 步」；成立之後整組要管理員的 session，與精靈跑完之後相同。**安全面**：誰先到誰建立，與 Jellyfin 自己的啟動精靈、Seerr 一樣；但成立之前 `/auth/login` 不發 session（`auth.OwnerPendingError` → 403，M4 票 28，實測 E12：頁 1 一選 Jellyfin 就存了位址，那一台上任何帳號原本都能直接拿 session），帳密也只送到畫面上那一台（見上）。匿名的 `GET /health` 帶 `owner_established`，前端守衛靠它在精靈跑完之前就把沒有 session 的人送去 `/login?redirect=/setup`。
   - 設定頁換位址或 key 仍然是登入換 key（`POST /setup/jellyfin/connect`）。套件內 Jellyfin 的媒體庫不在這一頁建，在頁 3。
2. **qBittorrent**：
   - **套件內**：設 WebUI 登入，全域偏好一個都不寫（M4 票 32，brief §19 D2）——與既有那一台只差這一格。Berth 自己靠免密白名單連它（§9.2），用不到這組登入。
     - **WebUI 登入可「沿用 Jellyfin 帳密」**（brief §16.3、§19 2026-09-29；M4 票 80 起不預設勾）：勾選時帳號是擁有者的名字，密碼請使用者**打一次**，Berth 先以 `POST /Users/AuthenticateByName` 向 Jellyfin 驗過這組帳密（不對就拒絕、不寫）再寫入；不勾就是票 07 的欄位——帳號預填擁有者的名字、密碼打兩次。擁有者的名字不合 qBittorrent 的規則時那一格停用、說原因（`interfaceLogin.reuseUnfit`）。**頁 1 勾了「也用這組」時不問**（M4 票 40，brief §19 D4）：頁 1 建套件內 Jellyfin 的管理員時那一格預設勾著，密碼由 `SetupPage` 留在 React state（不寫 storage、不送給 Berth 存；重新整理就沒了），這一頁那一台還沒有 WebUI 帳號時自動送一次 `reuse_owner`（`interfaceLogin.useCarriedLogin`），欄位與主鍵換成「設定中」，設好之後只說「已沿用 Jellyfin 帳密（擁有者）」加「改用另一組」（打開自設的三格）；「已沿用」由 `SetupPage` 記這個分頁最後一次替那一台設下的是不是帶過來的那一組（`CarriedLogin.inUse`），不看帳號。頁 1 的帳號與密碼照 qBittorrent 的規則邊打邊看（`reuseUnfit`），不合就勾不起來、帶不過來，這一頁不再看規則（M4 票 80）。Jellyfin 拒絕那一組（`owner_password`）時丟掉它、欄位打開在沿用那一格，頁 4 也不再自動送；同一個請求還在飛（走開又回來）時不重送。頁 4 套件內 Prowlarr 的介面登入同一套，送出中（Prowlarr 設完會自行重啟）「加入」與「之後再說」先停用。**必填**：不設的話使用者自己打開 WebUI 只剩容器 log 裡每次重啟都換的臨時密碼。帳密跟著「設定介面登入」送（`POST /setup/qbittorrent/apply` 的 `login`）；不帶 `login` 是「登入照舊」，設過的那一條是 `skipped`、細節是帳號，沒設過的是 `pending`，精靈停在這一頁。**那一台自己就設過的**（重裝保留它的 config）在連線測試時就讀到帳號、記成 `skipped`（`qbittorrent.note_qbittorrent_login`，M4 票 38），測試通過即完成；**「設定介面登入」只在欄位開著時出現**（還沒設、或按了「更換登入」），沒有按下去什麼都不寫的「套用這 0 項」（brief §19 D5）。
      - **照 qBittorrent 的規則先擋**（M4 票 26，brief §20.2）：帳號至少 3 字元、不能有冒號，密碼至少 6 字元；沿用時也檢查（Jellyfin 密碼太短、擁有者的名字不合就說不能沿用、請另設），設定頁的「更新登入」同一套。Berth **先送密碼、再送帳號**（5.2 帳號先寫、密碼後驗），兩個都進去了才記帳號；qBittorrent 仍回 400 時那一條是 `login_rejected`、原文進技術細節，欄位不收起來。
     - **Berth 只記帳號與密碼的加鹽雜湊**（夠比對「已經是這一組」；票 15 把票 07 存的明文換掉，附 migration）。回頭看時欄位收起來、只說帳號是誰，按「更換登入」才打開。設定頁 → qBittorrent 的「介面登入」一區是一般的改帳密表單（M4 票 78：目前的帳號、帳號預填它、新密碼兩次、「儲存」；沒有「沿用」，`reuse_owner` 只剩精靈在送），`PUT /setup/qbittorrent/login`（`qbittorrent.set_interface_login`）只換登入。設定頁的介面登入那一區讀頁 2 的 `GET /setup/qbittorrent/diff`（路徑名是票 32 之前留下的）。
   - **測試也問它看不看得到 `/data`**（M4 票 46，審計 P2-4）：連得上、版本夠之後，Berth 在共用根目錄（`routes.shared_root_of`，compose 裡的 `/data`）寫一個兩片的探測檔，請它停住校驗一次（`setup._data_sight`，頁 3 `download_visible` 那一支探針的 `unfinished=True`）。**校驗不完**：最後一片的雜湊對不上，看得到的那一台停在 50%，所以不觸發「torrent 完成時執行外部程式」（brief §20.2 對 4.4.5 與 5.2.3 實測）；5.x 的「加入時執行外部程式」照樣觸發一次，既有表單的說明寫明（套件內不提，同頁 3）。看不到是 `data_unseen`（讀不了 `data_unreadable`、一直排隊 `data_unsettled`），頁 2 紅、停在這一頁，補法與頁 3 那一條同一組片段（既有只多加一條 `${DATA_ROOT}:/data`，compose 與 `docker run` 各一，M4 票 36）。既有表單測過才存（M4 票 45），這一種也是測不過、不存。Berth 自己沒有那個目錄或寫不進去時不問，留給頁 3 Berth 那一條（`directory_missing` / `berth_cannot_write`）。探針 torrent 與探測檔當場收掉。
   - **既有**：位址 + WebUI 帳密 → 測試。一個全域鍵都不寫（M4 票 05，照 Sonarr / Radarr 對下載器只用分類的慣例）：不列偏好表（M4 票 22：它的全域偏好沒有一個影響 Berth，列套件內的建議值只會讓人以為該去改；原本的「temp path 未啟用只警告」一併撤掉），**測試通過就做完**（M4 票 38，brief §19 D5）：畫面上沒有確認鍵——原本的「確認，不改任何設定」按下去什麼都不寫，只是要人多按一次（照 Sonarr / Home Assistant「測試與儲存合一」的慣例）。沒有介面登入那一格，直接打 `apply` 帶了 `login` 回 422。
   - Berth 的路徑全靠分類（建立時帶 save path 與未完成目錄）與逐個 torrent 的 `autoTMM=true`，所以全域 `save_path` / `temp_path` / `temp_path_enabled`、`auto_tmm_enabled`、`category_changed_tmm_enabled` 動了會改掉使用者不經 Berth 加的 torrent 落在哪裡，而 Berth 自己用不到它們。**套件內那一台同一條**（M4 票 32）：票 32 之前寫過的 `save_path` 與兩個 autoTMM 開關 Berth 沒存原值，不改回去；`setup.qbittorrent.steps` 裡那三條舊紀錄讀的時候丟掉（`SetupQbittorrent` 的寬鬆讀取，不寫 migration：下一次套用整份換掉）。頁 2 的纜繩只剩 `web_ui_password` 一條。
3. **媒體庫與路徑**（票 06d 把它排在 qBittorrent 之後；票 08 改成按鈕觸發；M4 票 43 讓套件內第一次來自動跑）：
   - **套件內 Jellyfin 的媒體庫由使用者列**（票 06f，Jellyfin 啟動精靈「新增媒體庫」的慣例：內容類型 + 顯示名稱 + 資料夾）：一張可編輯的清單，預設 Movies・電影、TV・劇集、Anime・劇集三列，可以改名、改類型、改資料夾、刪列、加列，至少一列。類型只有電影與劇集（Berth 的 `SUPPORTED_TYPES`）；資料夾是 `library_root` 底下的一層（不能有 `/`、`\`、不能是 `.`、`..`，也不能有 Windows 不收的字元），名稱是 ASCII 時由它推導（照 `library_slug`），不是 ASCII 時要使用者填；名稱與資料夾各自不可重複（不分大小寫）。規則在 `services.jellyfin.check_bundled_libraries`，前端 `web/src/setup/libraryRules.ts` 用同一組在送出之前擋。清單存在 `settings.setup.jellyfin.bundled`（`PUT /setup/jellyfin/bundled`，拒絕是 `BundledLibraryRefusal` 帶列號），停手就存。**已經在 Jellyfin 建好的列鎖住**：bootstrap 以名稱認媒體庫，改了名重跑會多建一個指向同一個資料夾的——改名與刪除要去 Jellyfin，後端回 `built_changed`。媒體庫以第 1 頁存下的 API key 建（§9.4 第 1、4 步，`bootstrap_jellyfin`；沒有 key 就拒絕）。**沒有安裝插件的按鈕**（票 14b）。
   - **既有 Jellyfin**：使用者勾選媒體庫，每個媒體庫從它回報的路徑裡選寫入目標；還沒有 Berth 路徑的，寫入目標多一個「新的 Berth 路徑」選項（§9.5），**按下「建立並檢查」時才加**、再建 Route（票 08 shape 時使用者拍板把確認併進同一個動作，`.scratch/m4/route-berth-shape.md`：沒有「確認加入」那種做了一半、走得過去的狀態）。預選的是 Berth 路徑（加過的話），否則只有一條路徑時是那一條（brief §4.3，票 06h）。目標只能從那個媒體庫回報的路徑裡選，送別的路徑回 422。勾了卻還沒選目標、或一個都沒勾時，主鈕擋住並說出還差哪一步。
   - **Route**：每個選到的（套件內是清單上的，§9.5〈套件內的 Route 範圍〉）電影或劇集媒體庫各一個 Route，寫入目標取自 **Jellyfin 回報的** `locations`；slug 由媒體庫名稱算，空白換成 `-`（票 08；已經存在的 Route 與分類不改名）；**套件內改由使用者在清單上填的資料夾名算**（寫入目標的最後一段），媒體庫叫「電影」、資料夾填 films 時分類是 `berth-films`（M4 票 31）。套件內的 Route 照清單的順序建。**進這一頁不送任何寫入**（票 08：它會建媒體庫、加路徑、建分類、寫探測檔與硬鏈接測試檔，有副作用的動作由人按），**例外是套件內什麼都還沒做的那一次**（M4 票 43，brief §19 D7，`.scratch/m4/route-auto-run-shape.md`）：清單是預設（`GET /setup/jellyfin` 的 `bundled_default`）、一個都還沒建、沒有 Route、建媒體庫那一步從沒跑過、版本夠新、這一頁還沒做完時，進頁就照存下的清單送一次下面的整段（前端 `autoDock.startsOnItsOwn`；這一次不另外做進頁的重讀，整段自己先重讀），清單收起，工作面說一句為什麼沒按就開始了。跑過一次（哪怕紅了）、改過清單、既有 Jellyfin，一律等人按。**進度靠輪詢已有的 `running`**（沒有 SSE）：Route 的每一條檢查開跑前把那一列寫成 `running` 並 commit（`routes._run_checks` 的 `progress`，總結的 `health_status` 跑完才換；健康頁與 Route 設定頁的重新檢查同一條路），頁 3 在送出中、或伺服器讀到建媒體庫那一步或某條纜繩還是 `running` 時每 1.5 秒重讀（跑到一半重新整理也接得上，而且不再自動送）；跑的時候這一輪的每條 Route 在按下那一刻就畫成一列，還沒建出來、還沒輪到的「等待中」，跑著的那一列色塊是「檢查中」、摘要說「第 k / 6 條 · 纜繩名」，建媒體庫那一段在列表上方是 Jellyfin 那一條纜繩（進行中）。一顆「建立並檢查」（有新的可建）/「重新檢查 N 條 Route」，上面一份「按下之後會」列出這一輪真的會做的事（建哪幾個媒體庫、在哪個媒體庫加哪一條路徑、建或核對幾個 `berth-` 分類、在幾個寫入目標寫測試檔）。按下之後照順序做（前端 `SetupPage` 的 `dock`，各段仍是各自的命令）：套件內重讀媒體庫 → 存清單 → 存下回來的清單上有還沒建的才 `bootstrap` → `POST /setup/routes`（M4 票 24）；既有逐個加 Berth 路徑 → `POST /setup/routes`。**一段失敗就停**，後面的不送（建媒體庫或加路徑的失敗是 Jellyfin 那一份 `libraries` 那一步變紅，就地給一句人話與手動步驟，原文收進技術細節）。每個 Route 立即建立 qBittorrent category 並跑 §9.5 的每一項檢查；**每一條都綠燈**才走得到完成——紅的那個 Route 送單一定失敗（brief §4.4）。每條 Route 收成一列（`RouteRow`：健康、名稱、分類、寫入目標、「6 / 6 通過」），紅的那條自動展開、全過的收起；全過又沒有新的時，Route 列排在前、「重新檢查」降成次要排在後。健康頁與 Route 設定頁用同一個列元件。套件內的清單全部建好時收成一列（「媒體庫清單 · N 個已建立」），要加一個再展開。剖面只放 Route 列沒有的：兩個根目錄與這一輪將建立的 Route 寫到哪裡。
   - **重跑只新增、不改不刪**（票 14）：已經有 Route 的媒體庫在勾選表上鎖住、它的選擇略過，slug 與整張表比；寫入目標已經被別的 Route（或同一批前面的選擇）佔用的選擇也略過，不回 422（票 14a）。重跑的意思只剩「補上新勾的、全部重驗」。精靈跑完之前新建的 Route 直接啟用（紅著就擋完成）；跑完之後重跑新建的**先停用建立，檢查綠了才啟用**（票 14a）。重讀既有 Route、`_plan` 與插入在同一把寫鎖裡。認媒體庫用 `ItemId`（沒有 id 的舊資料才用名字）。選錯了的出路是每條 Route 底下明確的刪除（`DELETE /setup/routes/{id}`，被引用時拒絕）；精靈跑完之後在 `/settings/routes` 逐條管理。
4. **Prowlarr 與索引站**（併成一頁，brief §19 2026-09-29；票 15 併頁，票 09 做索引站那一半）：
   - **套件內**：API key 讀自唯讀掛載的 `/ext/prowlarr/config.xml`（零輸入，§9.2），選了就讀、存進 `settings.services.indexer`，M1 的搜尋從同一個地方拿憑證；**每次「重新測試」都重讀**（M4 票 27：在 Prowlarr 重新產生 key 之後，那是畫面上唯一的出口；讀不到時不動存下的——那是使用者貼的），key 被拒的補法說掛載、不說 qBittorrent 的白名單；連線卡綠而站清單讀不到時這一頁說讀不到、給「重新讀取」（＝重新測試）；讀不到時先問匿名的 `/ping` 確認它在（M4 票 25：只有 Berth 時根本沒有那個容器，該說主機名解不到，不是缺 key），在才就地給貼 key 的欄位，貼了仍是套件內。**介面登入**與 qBittorrent 同一條規則（可「沿用 Jellyfin 帳密」、只存雜湊、必填），以 `config/host` 設 Forms 登入（回 202 後它會自行重啟，要等 `/ping` 回來）；**介面登入是自己的一區與按鈕**（M4 票 20：加站不該被登入欄擋住）：精靈與設定頁都走 `PUT /setup/indexers/login`（`indexer.set_interface_login`），「加入」不帶登入、只記那一條現在的狀態（設過 `skipped`、沒設過 `pending`）；套件內 Prowlarr 要那一條有結論這一頁才算做完（`_indexer_settled`）。那一台自己就設過介面登入的（重裝保留它的 config），連線測試時就記成 `skipped`（`indexer.note_instance_login`，M4 票 27：站都在了的話沒有東西可加，原本要到「加入」才記）。**站那一半是「Prowlarr 上至少一站」，不論是不是 Berth 加的**（M4 票 27：重裝保留 Prowlarr 設定時已有的站不在候選清單、加不了）：Berth 加站成功的纜繩，或最後一次連線測試數到的站數（加站與移除之後 `_recount` 跟著改）。這一頁還沒做完時，前進鍵的位置列出還差什麼（加站、介面登入），按了把焦點送到那一區（`indexerGaps`，條件照 `_indexer_settled`）；站數前端看這一次讀到的清單、後端看上一次連線測試記的數，清單上有站而記的是 0（使用者到 Prowlarr 自己的介面加了站）時前端自動重新測試一次（與頁 2 的票 25 同一個做法）。說明寫明必填與理由：現行版本的 Prowlarr 第一次打開介面就跳出關不掉的設定視窗（brief §20.14）。
   - **套件內的主鍵**（M4 票 44，審計 E-5）：「測試推薦站，加入通過的」一次做完——`indexer.add_recommended_indexers`（`POST /setup/indexers/recommended`，只給套件內，既有回 422）測推薦清單上**還沒加入**的站（同 `verify_sites`），通過的逐站新增（同 `apply_default_indexers`），結論逐站記成纜繩：加進去 `ok`；測試就沒過 `failed`、不送新增；測過而新增被拒 `failed`。兩種沒加進去的靠 `SiteCheck.stage`（`test` / `add`，存在纜繩的 `params`）分開說——後者是 Prowlarr 加之前自己再連一次沒連上（審計實測 Internet Archive），畫面上單獨一段、不算已加入。結果照纜繩畫，重新整理還在。**Prowlarr 已經有站時不給這顆鍵**（重跑、重裝保留設定），後端也只碰還沒加入的站；新增前再讀一次清單，另一個分頁剛加的不重加。下面那一段（逐站測試與勾選、其他公開站）收進預設收起的「進階」，「加入」在那裡是次要的鍵。介面登入照舊是自己的一區（頁 1 帶過來的密碼自動送，M4 票 40），送出中主鍵停用。
   - **套件內的索引站（「進階」）**（票 09，`.scratch/m4/indexer-berth-shape.md`，使用者拍板三題：結果逐列行內、推薦在上其他公開站用搜尋叫出來、「已加入」一段在上）：「加站」一段是推薦清單 Nyaa.si、dmhy、Anime Tosho、ACG.RIP、Mikan、1337x、YTS、EZTV、The Pirate Bay（AniDex 拿掉了，brief §20.7）與「其他公開站」——`indexer/schema` 裡 privacy = public 的 torrent 站（依 `definitionName` 去重，usenet 不收），輸入名稱或選語言才列出來。**一站都不預勾，先測試通過才勾得起來**：「測試」是 `read` 命令 `indexer.verify_sites`（`POST /setup/indexers/test`，`indexer/test` 測還沒加入的定義，什麼都不建立，brief §20.7；一次最多 4 站併發），每一列一顆、推薦清單一顆「測試全部」。結果長在那一列：未測 / 測試中 / 通過 / 沒通過；沒通過是中性色塊加一句 i18n 理由（Cloudflare / 查無結果 / 連不上 / 其他，`SiteFailure`，由 Prowlarr 原文分出來），原文收進「技術細節」（M4 票 21 起與其他纜繩同一個元件）。清單上方一條摘要（`assigned` 色塊「N 站沒通過」+ 各理由的站數），**整段只有這一個 live 區**；紅色不用在這裡——一站沒通過不擋這一頁。「加入 N 個站」（套件內收在「進階」裡，是次要的鍵）只數勾著、還沒加的。加入是 `indexer` 新增（Prowlarr 加之前自己會再連一次，加不進去的回到沒通過、理由同一套，`IndexerSetupStatus.checks`）；**一站失敗不影響其他站**。私有 / 半私有站連到 Prowlarr 自己的介面去加：連結是**瀏覽器現在的主機名 + `PROWLARR_PORT`**（compose 傳給 Berth，同 Jellyfin 深連結；`setup/prowlarrWeb.ts`），給不出就不給。每一列顯示語言（BCP 47 代碼照 UI 語言換成語言名，`Intl.DisplayNames`）與定義自帶的英文說明（不翻）。
   - **「已加入」與試搜，不要的移除**（票 06e、09）：Prowlarr 只搜得到已經加入的站（`indexerIds` 只認已加入的，brief §20.7）。「已加入」列出 Prowlarr 裡的**每一站**（Berth 加的、使用者在 Prowlarr 自己加的都算，`IndexerSetupStatus.sites`），每列一顆「搜尋」、段頭一顆「搜尋全部」共用一個關鍵字欄（預設留白）。試搜是 `read` 命令 `indexer.search_indexers`（`GET /setup/indexers/search?query=&indexer_id=`，不帶 id 是全部）：逐站各發一個 `GET /api/v1/search?indexerIds=<id>`、併發，一站失敗寫在那一站上；回每站筆數與前三筆標題。移除是 `indexer.remove_indexer`（`DELETE /setup/indexers/{id}`），就地確認，只對套件內、只對 **Berth 加得回去的站**（推薦清單與公開的 torrent 站，不論是誰加的；私站回 422，列上說「要帳號的站 Berth 不移除」）；最後一站也移除時這一頁回到未完成。
   - **進頁只讀**（票 09）：精靈這一頁與設定頁的索引站分頁都只發 `GET /setup/indexers`（讀已加入的站、schema 與介面登入），不測任何一站、不送任何寫入。
   - **既有**：Prowlarr 位址 + API key（M4 票 37 起只支援 Prowlarr，不再接任一 Torznab 端點）。**表單、測試那一條與補法是頁 1、2 那一份**（`ServiceChoice` 的 `ExistingForm` 與 `TestLine`，送 `POST /setup/services/prowlarr`，M4 票 39）：key 錯時與頁 1、2 同一個錯誤版面，有「測試結果」那一列；右欄的 API key 那一格跟著最近一次連線測試，連上才寫「已取得」、key 被拒寫「不被接受」、其餘是「已存下，還沒驗證」。設定頁的 Prowlarr 分頁同樣用連線區（`ServiceConnection`）。Berth 用使用者已有的索引站；「已加入」列出它已有的站與站數（既有 Prowlarr 讀 `GET /api/v1/indexer`），沒有移除，試搜照樣可用。**既有 Prowlarr 也有「加站」**（M4 票 20，brief §19 2026-09-30）：同一套先測再勾、按一次加入，按鈕旁寫明「會加進你的 Prowlarr（主機）：哪幾站」，不讀也不寫它的 `config/host`。**一站都沒有時這一頁待處理**：連線纜繩是 `pending`（`indexer.existing_prowlarr_step`，三條入口共用），畫面說出下一步——到 Prowlarr 加站（連結是瀏覽器開得了的位址）後按「重新讀取」（就是服務頁的重新測試）、在下面加推薦站，或之後再說。加站與移除之後，連線測試記下的站數跟著清單（`_recount`），連線卡與泊位卡不再停在舊的數字。沒有介面登入那一格。
   - **可以跳過**（「之後再說」，連介面登入一起）：沒有索引站只是搜尋不到東西。完成頁的那一句照 Prowlarr 上實際的站數說（M4 票 27：有站就說搜尋用得到它們，讀不到清單就說讀不到）。
5. **TMDB**：使用者貼自己的 API key（v3 key 或 v4 token 都收），按「測試」。**這一頁是必填的閘門**：`configuration` 綠燈才走得到完成，畫面同時要說得出去哪裡申請（themoviedb.org → 設定 → API）。完成那一頁再擋一次，閘門看的是存下來的那一條綠燈。**測過才存**（M4 票 45，審計 E-6）：測不過的那一把與它的紅燈只回給畫面，已經有一把驗過的在用就照舊在用（票 06i：設定頁換 key 貼錯一把不該讓探索與入庫停擺），沒有就還是沒有；`GET /setup/tmdb` 的 `api_key_present` 因此與 `verified` 同真同假（欄位保留），「已存下，沒通過驗證」不再出現。0.1.0 測不過也存下的舊 key 不寫 migration，讀的時候當作沒有（使用者拍板），下一次測過就蓋掉。
6. **完成**：`POST /setup/complete` 寫 `settings.setup.completed`（照〈續行與跳過〉的頁序把每一頁再問一次，有一頁不再成立就回 422——另一個分頁回頭改了頁 2 或頁 4 也擋得住；前端收到 422 就重讀進度、回到那一頁，M4 票 31；問過的那些結論寫進 `settings.health`，健康頁一打開就有「上次檢查：剛才」，迴圈一個間隔之後才跑下一輪，M4 票 59），說出跳過了什麼與在哪裡補，並說出之後拿什麼登入（擁有者的 Jellyfin 帳號），然後回首頁——擁有者從第 1 頁起就登入著，直接落在探索；`/` 從那一刻起不再導向精靈，所以前端要就地把 `GET /health` 的那一個位元改掉再導航。

**續行與跳過**：精靈狀態存在 `settings.setup`，關掉瀏覽器再回來回到原本那一頁。**步驟由狀態導出，不存游標**：擁有者未成立 → 頁 1；qBittorrent 沒選、最後一次測試不是綠的，或套件內那一台的登入沒結論 → 頁 2（既有的那一台測試綠了就算做完，M4 票 38；測試要綠是 M4 票 25：設好之後它停了，重新測試紅了，頁 2 就不算做完；前端讀差異或套用時發現連不上而連線卡還是綠的，自動重新測試一次，卡片照實際的例外變紅、出現「重新測試」）；Route 沒有或沒全綠、或套件內清單有一列不在 Jellyfin 上 → 頁 3（後者看媒體庫快照而不是「建媒體庫那一步跑過沒」，與剖面的「已建立」同一條 `jellyfin.libraries_built`：保留 Jellyfin 重裝 Berth 時清單全部已建立、那一步從不執行，M4 票 24）；Prowlarr 沒結論也沒跳過 → 頁 4；TMDB 沒綠燈 → 頁 5；否則完成。**可跳過的只有頁 4**，完成頁說出跳過了什麼與在哪裡補；頁 2、3、5 不可跳。兩者不同級：沒有索引站只是搜尋不到東西，沒有 TMDB 則探索、季集快照與命名全部停擺（M1 票 02b）。

**前端的導覽**（票 06d；Material Stepper 的 linear 模式，Jellyfin 自己的啟動精靈有「上一步」）。後端的步驟仍然是導出的、前端不改它；前端只決定「畫面停在哪一頁」，進出規則全部是 `web/src/setup/navigation.ts` 的純函式：

- **畫面上那一頁就是網址的 `/setup?step=N`**（M4 票 30，實測 B3-01、B3-03、E10-06；NN/g 的精靈準則要能回上一步）：進頁沒寫就以後端那一頁補上（`replace`），點泊位板、上一個 / 前往下一個、回到目前這一步都進瀏覽器的歷史，所以瀏覽器的上一頁回到上一個看過的頁、不離開精靈，重新整理留在原頁。網址指到後端還沒到的頁（手打的、後端退回去了）就拉回後端那一頁，網址一起改。
- **做完停在結果上**：網址一直寫著畫面上那一頁，後端前進之後畫面不動，出現「前往下一個泊位」才走（原本靠按下動作那一刻釘住的覆寫，票 30 由網址取代）。
- **走過的點得回去，沒到的點不過去**：泊位板五格（Jellyfin、qBittorrent、媒體庫與路徑、Prowlarr、TMDB），走過的與目前的那幾格是按鈕，還沒到的是純文字——前進只能靠把事做完。原本板上方的前置列（擁有者、偵測）拿掉：擁有者就是 Jellyfin 那一格的結果，偵測不存在了。回頭看 Jellyfin 那一格說擁有者是誰、密碼在 Jellyfin 裡改。健康頁同一塊板，不可點。
- **每一頁有「上一個泊位」**；前往下一個一頁一頁走得回後端那一頁，所以回頭之後永遠走得回來。回頭看得比「剛做完的那一格」更前面時，板下一條帶子給「回到目前這一步」。
- **回頭看的那一頁說出能改什麼、不能改的去哪裡**：每一頁都是冪等命令，回頭照樣重跑，做過的標「已經是這樣」。
- **「重新測試」放在出問題的那一頁**：測試那一條是紅燈時才有（`POST /setup/services/{kind}/test` 帶 `restart`），取代原本的「重新偵測這個服務」。
- **頁 3 是一個畫面**（票 08 使用者拍板）：套件內的清單與 Route 在同一頁，一顆「建立並檢查」做完；原本的「開始靠泊」「前往 Route 與檢查」「媒體庫清單」三顆鈕與兩個畫面的切換拿掉。
- **手機寬度（< 640px）泊位板收成一列摘要**（M4 票 30，`.scratch/m4/wizard-navigation-shape.md`，實測 B11-08、B11-09）：五個帶泊位號的小色塊＋目前那一格＋「展開」，紅了的其他格用字說出；按了就地展開整塊 2+2+1 板，換頁就收起、不記。桌機不變，健康頁的板不收。
- **「上一個 / 前往下一個泊位」有下一個時不分寬度固定在工作面底部**（票 08：頁 3 做完是四條 Route，1280 × 720 上它被擠出畫面；DESIGN.md 記了這個例外）。
- 只管第一次設定：精靈跑完之後的修改由設定頁接手（票 06i）。跑完之後 `/setup` 導向 `/settings`，精靈沒有「從外面直接跳到某個泊位」的深連結。

### 9.4 Jellyfin 自動初始化序列

依 brief §20.7：`/Startup/*` 與 `/Library/VirtualFolders` 在精靈完成前不需憑證；插件與排程任務需要管理員 token。

**分兩半跑**（M4 票 06；2026-09-29 起第二半在媒體庫與路徑頁）：Jellyfin 頁（擁有者）跑下面的 1–3、5–7——帳密只在那一刻出現；媒體庫與路徑頁跑 1 與 4，用 Jellyfin 頁存下的 API key（`services.jellyfin` 的 `OWNER_STEPS` / `BERTH_STEPS`）。`JellyfinStep` 的宣告順序就是這個執行順序（媒體庫排最後）；畫面只列頁 3 建媒體庫那一步（M4 票 54 刪掉前端照序列七步的查表）。所以媒體庫是在 Jellyfin 的初始精靈跑完之後、以 API key 建的——第 4 步原本的「初始精靈跑完之後這一支要管理員憑證」從重按的特例變成常態。

1. `GET /System/Info/Public` → **先確認版本 ≥ 12.0**（低於就整段停在這裡，brief §16.4），再看 `StartupWizardCompleted`：`false` 給建立管理員的表單、跑 2–7；`true`（既有，或套件內但已初始化過）給登入表單、只跑 7。選套件內或既有不影響這一條（§9.3 的「表單跟著那一台的狀態走」）。
2. `POST /Startup/Configuration` `{ UICulture, MetadataCountryCode, PreferredMetadataLanguage }`，**套件內那一台另帶 `ServerName = "Berth"`**（M4 票 52，使用者 2026-10-06 拍板；`jellyfin.BUNDLED_SERVER_NAME`）：不帶的話 Jellyfin 寫成空字串，用戶端看到的是容器 ID（brief §20.9）。伺服器名稱是全域設定，既有那一台即使還沒初始化也不帶（brief §16.4）；已經初始化的整步跳過，本來就不寫。不帶等於清成空字串：既有而還沒初始化的那一台要是事先在 `system.xml` 放了名字，會被這一步清掉——票 52 之前就是這樣，要保住得先 `GET /Startup/Configuration` 讀回原值再送，目前不做。**既有那一台在擁有者表單上問**「語言與地區」（一組代碼，預設跟著 UI 語言），**套件內的不問**，帶 UI 語言（`zh-Hant` → `zh-TW` / `TW`，`en` → `en-US` / `US` / `en`）（M4 票 18，使用者 2026-09-30 拍板；`jellyfin.JellyfinStartup`）。第 4 步的媒體庫照 Jellyfin 自己的 metadata 語言與國家建（M4 票 29），也就是這一步寫進去的那一組。**寫給還沒初始化的那一台的選擇記在 `setup.jellyfin.startup`**（M4 票 29）：管理員建好之後某一步失敗，那一台的初始精靈還沒跑完，頁 1 仍是建立表單、照它重填——只有走到第 6 步（`StartupWizardCompleted`）才改成登入，否則登入表單不帶語言，重試會拿預設值蓋掉使用者選的（實測 E12）。
3. **先 `GET /Startup/User`**（它會跑 `UserManager.InitializeAsync()` 建立預設使用者），再 `POST /Startup/User` `{ Name, Password }` = 擁有者在 Jellyfin 頁填的那一組。少了 GET，POST 會回 500（brief §20.7）。**12.0 起第一個使用者已經有密碼時這一支回 403**，那是「已經設過了」而不是失敗（票 14b、brief §20.9）：第 3 步成功、後面某一步失敗、Jellyfin 沒重啟時按重試就會走到這裡，翻成錯誤的話重試永遠走不完。密碼對不對由第 7 步的登入驗證——所以管理員已經在時，同一組帳密就是登入，別的密碼過不了第 7 步。
4. **先 `GET /Library/VirtualFolders` 看有沒有同名的**：同名不會被拒，會建出 `Movies2` 指向同一個路徑（brief §20.7），所以清單上（§9.3 頁 3，`settings.setup.jellyfin.bundled`）同名已經在的標「已經是這樣」，只建其餘的。目錄由 Berth 建（`library_root` 之下那一列的資料夾，預設 `movies` / `tv` / `anime`），然後 `POST /Library/VirtualFolders?name=Movies&collectionType=movies&paths=<library_root>/movies&refreshLibrary=false`，body 是 `AddVirtualFolderDto`，也就是 **`{"LibraryOptions": { … }}`（要包一層）**：`PathInfos`、`PreferredMetadataLanguage` 與 `MetadataCountryCode`（取自 `GET /System/Configuration`：頁 1 寫進去的，或重裝保留下來的那一台原本就有的，brief §20.7）、`EnableRealtimeMonitor=false`（Berth 主動通知）、`SeasonZeroDisplayName="Specials"`、`TypeOptions[]`。直接送 `LibraryOptions` 物件一樣回 204，但整份設定會被靜默丟掉（brief §20.7）。清單上每一列各一次，預設就是 `Movies`（`movies`）、`TV`（`tvshows`）、`Anime`（`tvshows`）。
   - `TypeOptions[]` 的 **`MetadataFetchers` 是設定值**（`services.jellyfin.metadata_fetchers`，鍵是那一列的資料夾；沒寫的依內容類型落回 `DEFAULT_METADATA_FETCHERS`，目前兩種都是 TMDB，票 06f），**`ImageFetchers` 取自 `GET /Libraries/AvailableOptions?libraryContentType=`**。兩個都要給：只給 metadata 的話 image fetcher 會被存成空陣列，該類型從此不抓圖（實測，brief §20.7）。`AvailableOptions` 掛 `FirstTimeSetupOrDefault`，精靈期間匿名讀得到。
   - **初始精靈跑完之後這一支要管理員憑證**：M4 票 06 起一律用 Jellyfin 頁存下的 API key（見本節開頭的分兩半），沒有 key 就不建。
5. `POST /Startup/RemoteAccess` `{ EnableRemoteAccess }`：**預設不開**，既有那一台在擁有者表單上問、套件內的不問（M4 票 18）——Berth 從同一台主機的容器連進來，用不到它。
6. `POST /Startup/Complete`。
7. `POST /Users/AuthenticateByName` 取 token → **先 `GET /Auth/Keys` 找 `AppName == "Berth"`**，沒有才 `POST /Auth/Keys?app=Berth`，建完再列一次把 key 讀回來。那一支回 204 而且**不回傳 key**，也不檢查重複——按兩次就有兩把同名的（brief §20.7）。key 存入 `settings.services.jellyfin`，之後的請求改用它（與登入 token 同一個標頭形狀）。

**原本還有第 8、9 步**（加 danieladov 插件庫、裝 MergeVersions、重啟 Jellyfin、記下兩個合併任務的 `Id`）。票 14b 整段移除：只支援 Jellyfin 12，而 12.x 原生合併多版本，那個插件在上面是空跑（brief §19、§20.9）。少了它，這個序列不再重啟任何人的 Jellyfin，也不再依賴 GitHub 下載得動。

### 9.5 既有服務的接入（brief §16.4）

「既有」由使用者在那個服務的頁面選（§9.3，2026-09-29 起），不再由偵測判定；這一節是選了既有之後 Berth 怎麼接。

**掛載規則**：Berth、qBittorrent、Jellyfin 在**同一台主機**，把同一個宿主目錄（Berth 的 `DATA_ROOT`）掛在容器路徑 **`/data`**——只能是 `/data`：Berth 的三層路徑固定在它底下（`/data/torrent/{incomplete,complete}`、`/data/library`，`models.setting.PathSettings`，沒有設定可改；TRaSH 的單一 `/data`，brief §20.14）。**既有服務原本的掛載不動，多加這一條就好**（M4 票 36，審計 §C2）：Berth 只在 `/data` 底下讀寫，舊 torrent 照常在 `/downloads` 做種，Jellyfin 的 `/tv`、`/movies` 不能改（項目 ID 由路徑導出）。**不做 remote path mapping**（brief §18）：既有服務在另一台主機的接不上。「既有」選項旁說明這一條（容器路徑只能是 `/data`、`DATA_ROOT` 要建得了硬鏈接、既有 Jellyfin 要先有對應類型的媒體庫），媒體庫與路徑頁的檢查失敗時給那一台要多加的那一條（compose 與 `docker run` 各一種）。

NAS 範例：媒體在 `/volume1/media`、下載在 `/volume1/downloads`，Berth 的 `.env` 設 `DATA_ROOT=/volume1/berth`。使用者原本那一份只多加一條，其餘不動：

```yaml
services:
  jellyfin:
    volumes:
      - /volume1/docker/jellyfin:/config
      - /volume1/media/tv:/tv            # 原本的，留著
      - /volume1/berth:/data             # 新增
  qbittorrent:
    volumes:
      - /volume1/docker/qbittorrent:/config
      - /volume1/downloads:/downloads    # 原本的，留著（舊 torrent 繼續做種）
      - /volume1/berth:/data             # 新增
```

`docker run` 起的在原本的指令多加 `-v /volume1/berth:/data`。`/volume1/berth` 與 `/volume1/media` 不必在同一個檔案系統：硬鏈接只發生在 `/volume1/berth` 裡面（complete → library）。

**選了既有之後停掉套件內那一台**：從 `COMPOSE_PROFILES` 拿掉只讓之後的 `up -d` 不再起它，停不掉已經在跑的容器（brief §20.14 實測），所以精靈「選了既有」那一段、`docs/guide/existing-services.md` 與 `deploy/.env.example` 都另給 `docker compose stop <服務>`。

**連線位址**：Berth 在容器裡，使用者填 `localhost` / `127.0.0.1` 指的是 Berth 自己。位址欄下就地提示改成 `host.docker.internal`（Docker Desktop 內建；Linux 靠 `berth` 服務的 `extra_hosts: ["host.docker.internal:host-gateway"]`，§9.1，而且宿主上的服務要監聽 `0.0.0.0`）或區網 IP（brief §20.14，票 16、17）。

**既有 Jellyfin**

- 要的是位址 + **管理員**帳密（Berth 以它登入、自己建 API key，§9.4 第 7 步）；不是管理員就拒絕（票 06）。
- 不搬媒體庫：Jellyfin 的項目 ID 由路徑導出，改路徑等於觀看紀錄歸零。
- 「加入 Berth 路徑」按鈕：對選定媒體庫呼叫 `POST /Library/VirtualFolders/Paths?refreshLibrary=false`，body `{Name: <library>, Path: <library_root>/<slug>, PathInfo: {Path: …}}`；Route 指向這個新路徑，舊路徑只讀（辨識已存在媒體與 unmanaged 檔案）。**送出前兩件事要先擋掉**：目錄不存在會回 404（所以 Berth 先建），同一條路徑送兩次會讓媒體庫出現兩個一樣的 location（所以先看 `Locations`）。兩者都是 2026-09-07 實測（brief §20.7）。
- 使用者也可以不加路徑，直接在既有路徑中選一個當寫入目標；兩種都跑同樣的檢查。**預選的是 Berth 路徑**，只有一條既有路徑時也是（M4 票 19）。
- **加路徑之前先問 Jellyfin 看不看得到**（M4 票 19）：它對加不上的路徑只回 404 `Error processing request.`，媒體庫不存在也是同一句（brief §20.7）。Berth 建目錄、寫探測檔、`ValidatePath {IsFile: true}`；看不到就是 `BerthPathFailure.jellyfin_cannot_see`，不送那一支、收回剛建的目錄（`fs.missing_directories` / `remove_empty_directories`，只收自己建的那幾層）。一次送好幾個媒體庫（`{libraries: [...]}`），逐個試、逐個記在 `setup.jellyfin.berth_paths`；有一個沒加上，`libraries` 那一步就紅，精靈不建 Route。
- **頁 3 進頁時重讀媒體庫**（`POST /setup/routes/libraries`，另有一顆「重新讀取」，M4 票 19；**套件內也重讀**，按「建立並檢查」之前再讀一次，M4 票 24）：頁 1 之後在 Jellyfin 改的掛載、路徑與媒體庫要看得到。它只讀 Jellyfin、換 Berth 自己的快照，不寫任何服務，所以不算票 08「進頁不送寫入」的例外（真正的例外是套件內第一次來的自動建立，M4 票 43；那一次不另外重讀，整段自己先讀）。
- 絕不自動建立媒體庫、安裝插件或改既有媒體庫的 `LibraryOptions`。**adapter 的介面上根本沒有插件那幾支**（票 14b），所以「安裝插件」與「重啟」在這一層就做不到。
- 版本低於 12.0 的既有 Jellyfin 接不進來（brief §16.4）：Jellyfin 頁紅燈、健康檢查紅燈，訊息說出目前版本與升級前後要做的事。

**既有 qBittorrent**

- 要的是位址 + WebUI 帳密（5.2 起的 API key 這一輪不做，brief §16.4）。
- 不搬舊種：Berth 只用自己建立的 `berth-*` category，忽略其他分類的 torrent；舊 torrent 留在原目錄。
- 使用者原本只掛 `/downloads` 的，多加一條 `${DATA_ROOT}:/data` 即可、`/downloads` 留著；Berth 的 category save path 落在 `/data/torrent/complete` 下（M4 票 36）。
- **不改全域偏好**（M4 票 05；套件內同一條，M4 票 32）：全域 `save_path`、temp path、autoTMM 都是使用者的，Berth 一個都不寫、也不列；送單時逐個 torrent `autoTMM=true`，路徑由 Berth 的分類決定，未完成目錄也是（`downloadPath`，M4 票 22）。
- 版本低於 4.4（API 2.8.4）拒絕接入並提示升級。

**既有 Prowlarr**

- 要的是位址 + **API key**（Prowlarr 的 API 只收 API key，帳密只給瀏覽器，brief §20.14）。
- 用使用者已有的索引站；使用者按了「加入」才加勾的那幾站（M4 票 20），Berth 不移除它的站、不設它的登入（422）。**0 站不算完成**：頁 4 待處理，加站、重新讀取或之後再說才往下。
- **版本下限 1.3.2**（brief §20.14：卡住它的是匿名的 `GET /ping`，其餘端點從 0.1 就有）。版本讀 `GET /api/v1/system/status` 的 `version`（`ProwlarrStatus.supported`，形狀照 Jellyfin 的 `public_info().supported`）。`indexer.probe_indexer`（健康檢查；M4 票 39 之前頁 4 的既有表單也用它）與 `setup._test_connection`（服務頁的二選一與「重新測試」；有 key 時）**不問 `/ping`、直接問它**（M4 票 20：1.3.2 之前沒有 `/ping`，回的是介面的 HTML，先問它就說不出版本），401 是 `AUTH_REQUIRED`（補法說 API key 在「設定 → 一般」），太舊寫 `indexer.outdated_step`：細節是它的版本、原文是 `prowlarr.unsupported_message`，理由 `ConnectionReason.VERSION_UNSUPPORTED`（不等，套件內也當場紅）。

**檢查與訊息**（精靈的媒體庫與路徑頁與 `health_checker` 共用）。一個 Route 六條纜繩，前一條失敗就不跑下一條——後面的檢查測的會是錯的路徑。`RouteCheck` 是它們的封閉值集合，結果逐條存進 `routes.health_detail_json`。

1. `category`：`torrents/createCategory` 建 `berth-<slug>`（save path 為 `<complete root>/<slug>`）。已存在且路徑相同就跳過；路徑不同 → 回報衝突且**不覆寫**（改 category 路徑會搬走該分類所有 torrent，brief §20.2）。
2. `download_path`：**qBittorrent 回報的**這個 category 的兩個路徑（第 1 步的 `torrents/categories`：save path 與分類自己的未完成目錄；票 22 之前建的分類沒有後者，就不看）`stat` 得到。`stat` 的必須是服務報出來的字串——拿 Berth 自己算出來、而且剛剛才建好的目錄去 `stat` 一定會過，等於沒檢查。**全域 `save_path` 不看，兩種來源都一樣**（M4 票 05、32）：那是使用者自己的預設路徑，Berth 不寫它、送單也不落在那裡。套件內那一台原本另外現查它，使用者一改，三條 Route 全紅、送單被擋，錯誤還掛在分類路徑底下（審計 S5）。
3. `download_visible`：**反過來問**（M4 票 19）：Berth 在 qBittorrent 報的分類路徑寫探測檔，做成探針 torrent 請它校驗（`qbittorrent.probe_sight`，brief §20.2），100% 才過。第 2 條只證明 Berth 看得到那個字串，而那個目錄是 Berth 自己在第 1 條建的——既有 qBittorrent 只掛 `/downloads` 時它照樣在。讀到 `error` 是權限，逾時是它忙著校驗別的，理由各自說。**`health_checker` 不跑這一條、沿用上一次的結論**（`check_routes(probe_qbittorrent=False)`）：校驗到 100% 會觸發 qBittorrent 的「完成時執行外部程式」（brief §20.2 實測）；精靈、新增 Route、「重新檢查」照樣真的問。**真的問到的結論另存一份**（`RouteHealth.probe` 與 `probed_at`，M4 票 50）：`checks` 裡那一條會被斷在它之前的一輪洗成 `pending`，沿用的是另存的那一份；API 的 Route 多 `probed_at` 與 `probe_carried`，纜繩上說「沿用上一次的結論」與那一次的時間、要再問到 Route 設定按「重新檢查」；跑到一半（有 `running`）不說沿用，探到的結論當下就存，之後被打斷也不退回上一次的。從沒問到過的才是「尚未執行」，**那一條 Route 的總結是 `unknown`、畫面寫「要重新檢查」，不算進「已繫上」**（`routes._verdict`：有一條紅就紅，每一條都問到結論才綠；M4 票 59，審計 S4 換回套件內的 5/6）。**換一台 qBittorrent 之後**（`forget_route_checks` 作廢所有 Route 的檢查）設定 → qBittorrent 在新那台測過之後自動送一次「全部重新檢查」（`POST /routes/check`），逐條照頁 3 的進度畫；套件內那一台還在啟動的話等之後的重新測試轉綠再送。精靈裡換台（頁 2）不自動跑，頁 3 本來就是閘門。Route 設定頁另有「全部重新檢查」；健康頁的 Route 總結是「要重新檢查」時給管理員同一顆鍵。結果出來之前送單照 `jobs.check_route`：`unknown` 放行（送單自己 `ensure_category`，在空的新那一台也建得出分類，2026-10-08 實跑），`failed` 才擋。
4. `library_path`：**向 Jellyfin 現查**這個 Route 的寫入目標仍是媒體庫的路徑之一，而且 Berth `stat` 得到。不吃存下來的快照——使用者可能在那之後改了路徑或刪了媒體庫。**只驗寫入目標，不驗媒體庫的其他路徑**（M4 票 19 定案）：Berth 只在寫入目標底下讀寫（`services/reconcile.py` 走的是 Route 的目標，媒體庫的作品經 Jellyfin 的 API 讀），「舊路徑不動、加一條 Berth 路徑」時舊的 `/movies` Berth 看不到並不礙事。
5. `probe_visible`：在 Route 目標寫探測檔，`POST /Environment/ValidatePath` `{Path, IsFile: true}` 請 Jellyfin 確認看得到同一條路徑（看得到 204、看不到 404），問完就刪。
6. `hardlink`：在 `<complete root>/<slug>` 建暫存檔並 `link()` 到 Route 目標，確認同 device、同 inode，之後兩邊都清乾淨（`fs.link_test`）。
7. 任一步失敗 → 精靈與健康頁指出「哪個容器少了哪個掛載」，附**要改的那一台**的 compose `volumes:` 修正片段（`routeChecks.remedyFor`，M4 票 19）：`download_path` 與 `hardlink` 的 `EXDEV` 是 berth；`download_visible` 是 qbittorrent；`library_path` 與 `probe_visible` 是 jellyfin（Berth 早就掛著共用目錄，叫人改 berth 是白改）；不是 `EXDEV` 的硬鏈接失敗不附片段。`EXDEV` 另附「兩個目錄在 Berth 內是不同掛載」的說明。**精靈頁 3 對既有服務給那一台自己的版本**（票 08、19，`RouteCheckList` 的 `existing`）：片段是「你原本那一份」要**多加**的一條，compose 與 `docker run -v` 各一種（`routeChecks.runMount`；`${DATA_ROOT}` 換成 berth 那一份的值、容器路徑是 Berth 的 `complete_root` 與 `library_root` 的共同父目錄，也就是 `/data`），說明講原本的掛載不動、不做 remote path mapping（M4 票 36：原本叫人把下載目錄移到 `/data` 底下，照做舊 torrent 會找不到檔案）；`download_path`（既有 qBittorrent）另說同一個字串的條件，`hardlink` 的 `EXDEV`（任一既有）另說 berth 只能用一條掛載蓋住 `/data`、你的服務原本的掛載留著。Route 設定頁照 `GET /setup/status` 的選擇給同一份（票 36）；健康頁給套件內那一份。
8. **補法先看原因、再看是哪一條**（M4 票 25，實測 B5、E12）：與掛載無關的原因不給任何片段——`berth_cannot_write`（Berth 在自己的容器裡建不了目錄、寫不進探測檔，第 1、3、5 條都會撞上）說 PUID / PGID 與目錄權限；`directory_missing`（`_visible` 讀到 `FileNotFoundError` 而那條路徑在 Berth 自己的共用根目錄底下——`complete_root` 與 `library_root` 的共同父目錄，Berth 掛著它：目錄被刪或改名；不看「上面幾層在不在」，image 本來就有 `/media`、`/mnt`）說把它建回來或改回原路徑，與不在共用根目錄底下的 `path_not_visible`（沒掛進 Berth）分開；位址的協定寫錯與連不上、帳密、被封同一類。`library_path` 的掛載補法說 Route 建好之後寫入目標就鎖住了，要先刪掉這條 Route 再選新的路徑。

**套件內的 Route 範圍**（M4 票 24 定案）：套件內 Jellyfin 只替**清單上的媒體庫**建 Route（`jellyfin.is_listed`：名稱相同，或它的路徑之一是那一列的資料夾——與「已建立」同一條比對；`LibraryChoice.listed` 讓剖面照同一條列「將建立」）。使用者自己在那台 Jellyfin 加的媒體庫（重裝時保留下來的、路徑不在 `/data` 的）不自動建 Route：原本照樣建、紅著擋住頁 3，刪掉之後下一次「建立並檢查」又長回來（實測 R-04～06）。沒選另一個做法「記下使用者刪過的媒體庫」：要多存一份墓碑，而且第一次照樣先建出一條紅的。代價：清單上的媒體庫刪了 Route 會在下一次按下時再建——要它不再出現就在 Jellyfin 刪掉媒體庫、重讀之後從清單拿掉那一列；精靈跑完之後在 `/settings/routes` 逐條管理。

**不支援**：既有 qBittorrent 或 Jellyfin 與 Berth 不在同一台主機、或沒有把 Berth 的 `DATA_ROOT` 掛在容器路徑 `/data`；remote path mapping。

### 9.6 為什麼這樣做

- 借鑑 Seerr（以媒體伺服器管理員為 owner）、Servarr 生態（`custom-cont-init.d`、`APP__NAMESPACE__ITEM` 環境變數）、TRaSH（單一 `/data`、PUID/PGID/UMASK）。
- 預置只放「沒有它 Berth 就進不去」的最少內容（qBittorrent 免密白名單與路徑），其餘全部由 API 完成並可重跑，避免設定散落兩處。

---

## 10. 測試策略

| 層 | 工具 | 範圍 |
| --- | --- | --- |
| 單元 | pytest | `parser/`、`naming/`、`domain/` 狀態機、`Tags.render`、sanitize；benchmark 是單元測試的一部分 |
| adapter 契約 | pytest + respx | 每個 adapter 對錄製回應（`tests/fixtures/http/`）的解析；版本差異（qBittorrent 4.4 vs 5.x 的參數） |
| 整合 | pytest + Fake adapters + 暫存 SQLite | services 與 pipeline：送單 → 完成 → planning → importing → ledger；重入與冪等；刪除範圍；reconciler 對三種人為破壞的偵測 |
| 前端 | vitest | 元件與關鍵頁面 |
| 前端 e2e | playwright（`web/e2e/`，CI 的 `web-e2e` job，每個 push） | 對 `scripts/fake_setup_server.py` 的演練情境跑七條流程（M2 票 15 起四條，M3 票 06h 加三條）：精靈八步走完（`bundled`）、既有服務接入（`mixed`）、冷啟動不按重新探測（`starting`）、精靈跑完之後的設定頁修改（`healthy`）——這四條在 1280 與 390 各走一次、每一格留整頁截圖——以及送單到入庫（`import`，一個請求都不出網）、`/review` 確認一筆 audit（`review`）、`/issues` 修一條 `library_link_missing`（`issues`）。一條流程一台 server、不重試（替身有狀態）；失敗時截圖與 trace 上傳成 artifact。**只蓋這七條**：其餘頁面的 UI 驗證仍是每張票用 playwright MCP 對演練情境實跑並把結果貼進票與 progress.md（CLAUDE.md 的規則），新的一條流程要進閘門就在 `web/e2e/` 加一個 spec 與 `playwright.config.ts` 的一列 |
| e2e | docker compose（GitHub Actions，`tests/e2e/`；本機與 CI 同一條 `python -m tests.e2e.stack`，起、測、一定拆） | 真 qBittorrent + 真 Jellyfin + 這一份工作目錄 build 的 Berth + 真 TMDB（Prowlarr 起來讓精靈偵測，索引站那一步跳過，搜尋不在 e2e 裡）。**與同一台機器上的試跑環境並存**（M4 票 34）：專案名、容器名、網路與子網、host port、`/data` 與 `/config` 都只在 e2e 的覆寫檔與 `e2e.env` 換掉，產品 compose 不動（`tests/unit/test_e2e_stack.py`）。**一次 compose、一次精靈、一次入庫，三個模組共享**（fixture 在 `tests/e2e/conftest.py`，session scope）：<br>**M1**（`test_1_m1_pipeline.py`）用本地產生的 .torrent 與檔案（benchmark 語料的三包：美劇一季、動漫一季、電影），送單之後把位元組放進 qBittorrent 回報的下載路徑再 `recheck`，跑通 M1 驗收；驗證時間線依序走過各站、硬鏈接 inode、帳本逐檔的 Jellyfin item id（票 15 以 recheck 取代原本寫的 `seedMode`：那是 Web API 2.16 起才有、而且要由送單的 Berth 帶的參數）。<br>**M1.5**（`test_2_m15_library.py`，票 11）以 Jellyfin API 建一個只開放一個媒體庫的一般使用者，用它登入 Berth：看不到沒權限的媒體庫、直接請求也被拒；不經 Berth 放進那個媒體庫的作品照樣在牆上；某一集的 `item_id` 就是 Jellyfin 在帳本那條路徑上的 item；標為已看 / 未看之後**那個帳號自己的** `UserData` 真的變了；帳號被停用之後 Berth 的 session 結束。最後停掉 Jellyfin 容器，驗「問不到 Jellyfin」那一句（票 07 留給這一輪的）。<br>**M2**（`test_3_m2_repair.py`，票 16）三種人為破壞各造一次：以 Jellyfin 的 `DELETE /Items/{id}` 刪掉一集（`library_link_missing` → 重新鏈接）、複製品取代硬鏈接（`inode_mismatch` → 以硬鏈接取代）、手動刪 complete 裡的來源（`source_missing` → 標記為已無來源）與 complete 裡一個沒人認領的目錄（`orphan_complete` → 刪除）；每一種修完再對帳一次，那一件不再開。再把整個 Anime 媒體庫的內容刪光，`POST /jobs/{hash}/reimport` 一次回到同樣的路徑、同一個 inode、同樣的帳本列 |
| 部署腳本 | pytest + bash 替身 | `deploy/` 的 shell：preseed 的「缺鍵才補」規則（從 compose 的 `configs` 抽出腳本、`$$` 還原成 `$` 再跑）、entrypoint 的擁有者接手。真的跑腳本，把 `chown` / `setpriv` 換成會記錄參數的替身；路徑用 `BERTH_*` 的測試 seam 覆寫 |
| 實驗 | `scripts/experiments/` | brief §20.6，一次性但保留腳本，結果寫回 brief |

- CI（GitHub Actions）：lint、type、unit + integration、benchmark 門檻、前端 build、前端 e2e、image build；e2e 在 nightly、`v*` tag 與手動觸發時跑（`.github/workflows/e2e.yml`，TMDB 憑證是 repo secret）。
- 覆蓋率不設硬門檻，但 `parser/`、`naming/`、`services/` 的新程式碼必須有測試。

---

## 11. 里程碑任務

任務 ID `T<里程碑>.<序號>`，每個任務都有驗收。順序即建議開工順序，同一里程碑內標 ∥ 的可平行。本節是每個里程碑 `/to-tickets` 拆票的輸入與驗收來源；拆票後執行單位以 `.scratch/<里程碑>/issues/` 的票為準，本節不逐條維護狀態。

### 11.1 M0 骨架

| ID | 任務 | 驗收 |
| --- | --- | --- |
| T0.1 | Repo 骨架：uv 專案、ruff / mypy / pytest / import-linter、pnpm + Vite 專案、pre-commit、GitHub Actions（lint、test、build）、`.gitattributes`（LF）、LICENSE（MIT）、README 骨架、專案 `CLAUDE.md`、CHANGELOG | CI 綠燈；`uv run berth --version` 與 `pnpm build` 可跑 |
| T0.2 | 設定與 DB：`config.py`、SQLAlchemy models（§2 全部表）、Alembic 初始 migration、啟動自動 migrate、`settings` 的 pydantic 分組 | 空環境啟動後 `/config/berth.db` 建立且 schema 完整 |
| T0.3 ∥ | 實驗腳本（brief §20.6）：硬鏈接測試（Linux bind mount；Windows 已於 2026-09-07 實測通過，腳本化保留）、Jellyfin 命名實測（dummy 檔 + API 查詢結果）、qBittorrent 4.4 / 5.x 參數相容與 `ServerDomains` Host 檢查、Prowlarr host config API 設帳密 | 結果寫回 brief §20.6 與本文件 §5、§9；命名模板凍結 |
| T0.4 ∥ | adapters 第一版：jellyfin（public info、auth、api key、virtual folders、startup、repositories、packages、restart）、qbittorrent（login、version、preferences、categories）、prowlarr（indexer schema / add / test）、tmdb（configuration、search）、fs；每個附 Fake 與契約測試 | 契約測試綠燈；對真服務的手動 smoke 通過 |
| T0.5 | 認證：Jellyfin 登入 → session；角色由 Jellyfin `Policy.IsAdministrator` 決定；`auth/*` API；登入頁 | 非 admin 使用者無法進設定 |
| T0.6 | 設定精靈（§9.3）：`setup/*` API 與 UI；逐服務來源偵測；套件內服務全自動設定；既有服務表單與確認按鈕（安裝插件、加媒體庫路徑、套用偏好差異）；從媒體庫建 Route；Route 的硬鏈接與跨服務可見性檢查（§9.5） | 在乾淨的 Linux 與 Windows Docker Desktop 上，`docker compose up` 後只操作 Berth 即完成設定；「既有 Jellyfin + 套件內其餘服務」的組合也走通 |
| T0.7 ∥ | `deploy/`：Dockerfile（多階段：node build → python slim，非 root，`PUID/PGID` 入口腳本）、一份 Linux 與 Windows 共用的 compose 範本（§9.1）、preseed 檔、`.env.example`、image 發佈 workflow（GHCR） | `docker compose up` 四個服務健康；image 大小 < 400 MB |
| T0.8 | `health_checker` 迴圈與健康頁；服務設定頁（含「測試連線」「套用建議設定」按鈕） | 四項健康檢查綠燈；拔掉任一服務 5 分鐘內變紅並顯示原因 |

### 11.2 M1 手動全流程

| ID | 任務 | 驗收 |
| --- | --- | --- |
| T1.1 | TMDB：探索與搜尋 API、Media 詳情與快照、`tmdb_cache`、資料夾名（跟著標題走，凍結在 T1.3 的送單） | 探索頁可瀏覽趨勢與搜尋；Media 詳情顯示季集 |
| T1.2 ∥ | 索引站搜尋：Torznab client（M4 票 37 已移除）、多標題查詢合併、結果附 Tags 與預估季集、搜尋 API 與結果表 UI | 三種類型的作品都能搜到並正確顯示 Tags |
| T1.3 | `add_download`：qBittorrent 送單、job 建立、event；`jobs` API；下載列表頁 | 送單後 qBittorrent 出現正確 category 與 save path |
| T1.4 | `qbit_poller`：maindata 增量、狀態轉換、進度事件、SSE、未知 torrent issue | 從送單到完成的狀態在 UI 即時更新；重啟 Berth 不丟狀態 |
| T1.5 ∥ | 解析器（§4）與命名（§5）：全部階段、benchmark harness、`berth bench`、v0 語料 20 筆、baseline | benchmark 通過且 `auto_wrong = 0` |
| T1.6 | `planner_runner` + `importer` + `jellyfin_resolver`：pre-plan、planning、Plan 持久化、自動 / review 判定、硬鏈接、ledger、Jellyfin 通知與反查（~~MergeVersions 任務觸發~~ 票 14b 移除，12.x 原生合併） | 三種類型各一部不經人工入庫並在 Jellyfin 正確顯示 |
| T1.7 | UI：Media 詳情（搜尋 → 選 torrent → 選 Route → 送單；檔案與版本清單）、Job 詳情時間線、媒體庫頁（Route 分頁、卡片、狀態、深連結） | brief §17 M1 驗收 |
| T1.8 | e2e：compose 環境下的 M1 流程自動化（§10） | nightly 綠燈 |
| T1.9 | **M0 帶過來的技術債**（票 11 收尾時逐條過完，2026-09-11）：~~`openapi-typescript` 從 OpenAPI 產前端型別並在 CI 檢查是否過期~~（**票 02 做完**：`pnpm gen:api` + CI 的 `git diff --exit-code -- src/api/schema.d.ts`）、~~結構化日誌每行帶 job id~~（**票 09 做完**：`berth/logs.py` 的 `ContextVar`）、~~Route 設定頁支援「同一個媒體庫多條 Route」與明確的刪除動作~~（**票 14 做完**：`/settings/routes`，精靈第 7 步只新增不改不刪，brief §4.3）、~~qBittorrent 的 403 要分得出「帳密不對」與「IP 被封」~~（**票 10 做完**：`IpBannedError`，§8.1、brief §20.2） | 前端沒有手寫的 API 型別，型別檔過期時 CI 紅燈；Job 的每一行 log 都查得到 job id；一個媒體庫建得出第二條 Route，且沒有東西被隱式刪除 |
| T1.10 | **Jellyfin 12**（2026-09-15 插入，票 14b；brief §19、§20.9）：**只支援 Jellyfin 12 以上**：移除 MergeVersions（精靈步驟、既有服務按鈕、resolver 的合併觸發、任務 id）、低於 12 時精靈與健康檢查紅燈並說明升級；精靈第 3 步重試遇到的 403、劇集版本名改讀 Jellyfin 的 `MediaSources[].Name`、多集檔與同起始集的單集送 review、compose 釘 `version-12.1ubu2604` | 12.1 的真環境裡，同一集兩個版本入庫後在 Jellyfin 是一集兩個來源，Berth 顯示 Jellyfin 的版本名；連 10.11 的 Jellyfin 時精靈停下並說得出要升級；精靈中途失敗後重試走得完 |

### 11.2b M1.5 媒體庫瀏覽

2026-09-15 使用者在票 13 之後拍板加入（brief §12、§13、§19），排在 M1 驗收之後、M2 之前。播放仍然深連結到 Jellyfin，不做內嵌播放器。

範圍：媒體庫頁改成瀏覽**整個 Jellyfin 媒體庫**（不只 Berth 經手的），Berth 經手的作品疊上票 13 的入庫狀態，還沒進 Jellyfin 的（下載中、待審）仍在牆上；繼續觀看、下一集；卡片與各集顯示已看 / 看到一半 / 剩幾集沒看，可切換並寫回 Jellyfin 該使用者的紀錄；依類型、年份排序與篩選；Jellyfin 的圖（海報、劇照）。Media 詳情在作品已在 Jellyfin 時把**觀看區**（繼續看、選季選集、各集已看）放最上，搜尋 torrent 與檔案版本收到下面——探索與媒體庫共用 `/media/:id`，不另建媒體庫詳情頁。
前置：Jellyfin API 已查證（brief §20.8、`docs/research/library-browsing.md`）——功能都做得到，但伺服器 API key 代讀時 Jellyfin 只套用一部分媒體庫權限，所以**權限檢查集中在 services 的一處**：`userId` 一律取自 session、絕不收前端傳入；媒體庫 id 對 `GET /UserViews?userId=` 的允許清單驗證；單一作品與集走會檢查可見性的端點（`/Items/{id}?userId=`、`/Shows/{id}/Seasons|Episodes?userId=`），不用 `/Items?ids=`；`parentId` 只放驗證過的媒體庫 id（劇或季當 `parentId` 連使用者自己的 token 都擋不住）；`userId` 在 adapter 是必要參數（`Seasons` / `Episodes` 漏帶會回 200 並略過權限）。越權請求被拒寫成整合測試。research 第 2 節那張表已在一次性 Jellyfin 12.1.0 上以受限使用者逐列實測（M1.5 票 01，推論全部成立，另補四列），過濾與排序參數、由 TMDB id 找作品（不帶 `parentId` 的 `/Items?hasTmdbId=true&fields=ProviderIds`）、Series / Season 標記遞迴、停用帳號的行為也一起量了（research §3.1、§5、§10，brief §20.8）；adapter 的每個過濾參數仍要有契約測試斷言「伺服器真的有過濾」（`/Items` 靜默忽略不存在的參數）。brief §19 的四條待決已定（2026-09-15）：媒體庫頁一個 Jellyfin 媒體庫一頁（取代票 13 的一條 Route 一頁，`/library/:routeSlug` 跟著改）；首頁上方放繼續觀看與下一集，下面維持探索；瀏覽時取 `UserViews` 允許清單一併讀帳號 `Policy`（同一份短時間快取），停用就結束 session；Jellyfin 圖片由 Berth 代理，快取鍵用 `tag`。
M1 帶過來的（票 15 的 critique，2026-09-17，使用者拍板交給這一輪的 shape）：Media 詳情頁的動作沉底（1280×900 下「搜尋」在 y=984、390px 在第三屏）、全綠的搜尋纜繩佔 311px 把結果表推到下一屏、下載列展開後的計劃與「檔案與版本」逐檔列出（Frieren 那一筆展開後 9,000 px 以上）、季表收起時仍渲染整張集表（1213 集的作品開頁就多幾千個節點），而且一季展開之後只能捲回頂端收起；不能只看缺集、缺集也不能一鍵搜（搜尋仍從作品名開始，而季表已經知道缺哪幾集）。觀看區要放上最上面，這幾件跟著一起定。另外，**顯示用標題與簡介跟著 UI 語言走**（2026-09-17 決定，brief §7.5、§19）：探索牆、Media 詳情、下載列，以及媒體庫牆上還沒進 Jellyfin 的卡片都要換；媒體庫牆上已在 Jellyfin 裡的作品顯示 Jellyfin 的名稱（拆票時使用者拍板，brief §7.5、§19）。媒體庫瀏覽會大量顯示標題，所以排在這一輪。
驗收：以一般使用者（`user` 角色）登入，不開 Jellyfin Web 就能從媒體庫找到要看的那一集、看到自己的觀看進度並標記已看，按播放落在 Jellyfin 的那一集；該使用者在 Jellyfin 沒有權限的媒體庫在 Berth 也看不到；既有媒體庫裡不是 Berth 入庫的作品照樣瀏覽得到。

### 11.3 M2 修正與對帳

範圍：Review Queue（Plan 逐列編輯、批次核准、audit 確認 / 撤銷）、Unmatched 指派、`rematch_file`、`reconciler` 與 issues 頁、刪除範圍（四旗標與空間估算）、`reimport`（以目錄為 Import Source）、`berth rebuild-ledger`、`/jobs/:hash` 詳情頁。
驗收：刪掉 library 後一鍵重建；對「Jellyfin 內刪除」「complete 目錄手動刪檔」「用複製取代硬鏈接」三種破壞都能偵測並修復；medium 自動入庫的檔案可在佇列中一鍵撤銷；以 `user` 登入時看不到也按不到審核、修正與刪除。

**2026-09-22 拆票前的設計決定**（使用者拍板「照建議」；出處與理由各在指到的章節）：

1. `/jobs/:hash` 另建一頁，`/jobs` 的展開區只留摘要（§7）。
2. 大媒體庫要不要快取，拆票時不決定；量測票的驗收寫死門檻：**1,000 部的媒體庫上 `GET /inventory/{id}` p95 > 1 s，或 reconciler 走完一輪 > 10 分鐘，就做分段取；否則不做快取**（快取要解失效，M1.5 的經驗是網址帶 `tag` 才敢長快取）。**票 11 量完**：inventory p95 3.4 s 超了，原因是 `services/inventory._survey` 逐部作品篩整張帳本（二次方），改成一次分組後 0.66–0.68 s——不是 Jellyfin 回太多，所以沒有做分段取；對帳一輪 27–31 s 沒超（`docs/research/large-library.md`）。
3. Issue 型別是十一種的聯集，冪等鍵依型別，`/issues` 是獨立頁而不是健康頁的一段（§2.4；健康頁是唯讀診斷，issues 要按動作）。
4. 刪除範圍四旗標**預設全不勾**（brief §9.2）；空間估算同步 `stat`（慢而準，UI 說「正在算」）；對話框住在 `/jobs/:hash` 與 Media 詳情的版本清單，同一個元件；Issue 的「連 complete 一起刪」走同一組旗標。
5. reconciler 手動觸發回 202、`GET /reconcile` 可輪詢、正在跑是 409（§3.2）。
6. `GET /review` 一支、一列一件事、需要人動手的排前面、不分頁（§6）。
7. 審核、Issue 動作、rematch、刪除、reconcile 一律 admin（§6、brief §11）。
8. `rematch_file` 內部建單 item Plan 立刻套用（§6）。
9. `berth rebuild-ledger` 從 library 的 inode 反查 complete：配得上的重建完整一列（季集與 Tags 從目標路徑反解），**配不到的一律建 `unmanaged_library_file` Issue，不猜**。M4 票 60 起畫面上也按得到（§6 issues 群組）；對帳再記同一件時保留它寫的 `reason`，那是「判過了」的記號。

**遺留清單裡的兩個二選一也定了**：媒體庫頁上方的繼續觀看與下一集**收成一行「接著看 N 項」就地展開**（同票 07 的 watching-shape 慣例，首頁不動）；重複控制項的可存取名稱**在四個卡片元件裡用 `aria-label` 帶上作品名**（改四處而不是一百處，不走「接受並記進 DESIGN.md」）。

**建議票序**（每票一個 session，tracer bullet 先端到端；`/to-tickets` 時以此為底，使用者參與拆分）：

> 實際拆成 16 張，編號與內容以 `.scratch/m2/issues/` 為準——下表的票 01 後來拆成兩張（後端 / 拒絕理由），
> 票 02 按頁面群重切，所以表上的票號與實際票號不對應。差異記在 progress.md 2026-09-22 拆票那一條。
> 實際的票 09（下表 08「reconciler 其餘 + 重新反查」）在 2026-09-23 開工時再拆一次（使用者拍板）：管線三種的動作與 TVDB / 磁碟門檻兩種 Issue 移到新的票 09c，三顆「認領」類動作移到票 10。

| # | 票 | 內容 | 位置的理由 |
| --- | --- | --- | --- |
| 01 | 開工收尾（後端） | 兩個有 repro 的 500（同一個新使用者兩次登入同時進來撞 `users.jellyfin_user_id` unique，`services/auth.py` `_mirror_user` 沒接 `IntegrityError`；`check_routes` 途中 Route 被刪，`api/setup.py` 只接 `ValueError` 而 `StaleDataError` 裸奔）；`Season 3 / … Season 3 - 46` 被 `_LOOSE_RANGE` 讀成 `S03E03–E46`（自己的語料 fixture + 一輪 `berth bench`）；`list_jobs` 逐列查詢改批次；`QbitPoller` 補整合測試（五個迴圈裡唯一沒有的，而它扛著 §3.2 的排程規則）；前端三組手抄的拒絕理由（`web/src/api/jobs.ts` `JobRefusal`、`jellyfin.ts` `AccessRefusal`、`routes.ts` `RouteRefusal`、`events.ts` `JobSignal`）改成 pydantic model 進 OpenAPI 讓 `openapi-typescript` 產；`web/vite.config.ts` 設 `testTimeout` / `asyncUtilTimeout`（本機全量跑固定兩條 `findBy*` 逾時） | 都有 repro、都便宜、都不需要新載體 |
| 02 | 開工收尾（前端） | M1 票 15 與 M1.5 票 11 沒排進範圍的小項（下方「B」組）；`/impeccable document` 把 `.impeccable/design.json` 追上 `DESIGN.md`（M1.5 票 11 改了後者沒動前者，M1 票 11 / 13 / 14 的同一個債重現） | 純前端、互相獨立 |
| 03 | **`issues` 表 + 最小 reconciler + issues 頁** | migration；`GET /issues`、`POST /issues/{id}/resolve \| ignore`、`POST /reconcile`、`GET /reconcile`；迴圈**先只做 `library_link_missing`**；`/issues` 頁；M1 的 `issue_detected` 事件改成同時寫一列 `issues` | M0 / M1 遺留等了兩輪的載體；端到端最小版：刪一個 library 檔 → 對帳 → 一條 Issue → 按「重新鏈接」修好 |
| 04 | 刪除範圍 + `delete_job` | `DELETE /jobs/{hash}?unlink=&remove_torrent=&delete_files=&purge=`、空間估算、Job 進 `removed`、event `deleted`；對話框元件 | 票 05 的撤銷與票 07 的 rematch 都靠它 |
| 05 | Review Queue ⅓：audit 確認 / 撤銷 | `GET /review`（先只有 `audit` 一類）、`/review` 頁的清單骨架、confirm / undo | 驗收第三條本身就是 tracer bullet |
| 06 | Review Queue ⅔：低信心 Plan 逐列編輯 + 批次核准 | Plan item 的理由改封閉集合 code + 參數（前置，不然翻不了譯）、`PUT /plans/{id}/items`、`approve` / `reject`、`apply_plan`、`JobState.REVIEW` 的出邊；先 `/impeccable shape` | 最重的一張 |
| 07 | Review Queue 3/3：Unmatched 指派 + `rematch_file` + duplicate | `POST /files/rematch`；Unmatched 的指派 / 標 extra / 忽略；brief §7.8 的 `duplicate`（目前撞同一目標路徑以 `target_exists` 停下） | 票 06 之後才有清單可放 |
| 08 | reconciler 其餘 + 重新反查 | 其餘十種 Issue 的偵測；`jellyfin_series_id` 回填（票 13 之前反查完的劇集卡片一直說「還在掃描」，順手讓它會自己更新）；Jellyfin 12 合併後 `jellyfin_item_id` 可能不再是主條目；M0 兩條：媒體庫掛 TVDB 插件的警告變成 Issue、磁碟空間門檻變成 Issue | 十種檢查是同一支命令的分支 |
| 09 | `reimport` + `berth rebuild-ledger` | `POST /jobs/{hash}/reimport` 與目錄版；CLI 子命令 | 驗收第一條 |
| 10 | 【研究】大媒體庫量測 | 三件一起量：`library_index` 整份清單、不帶 `parentId` 的 `/Items?hasTmdbId=true`、`/Items` 帶整份 `MediaSources`；順便量「待審 / 對不到」篩選後的牆帶觀看狀態的代價（現在那一份 `enableUserData=false`，卡片 `watch` 是 `null`）；同一個一次性環境實測**被刪掉的 Jellyfin 帳號** `GET /Users/{id}` 回什麼（停用的驗過，刪除的沒有）。結論回寫 brief §20.8，門檻見決定 2 | reconciler 要走整個媒體庫，票 08 之後才有東西可量 |
| 11 | `/jobs/:hash` | 時間線、檔案清單與各檔決策、Plan 歷史、動作 | 決定 1 |
| 12 | 前端品質（M1.5 audit P1 / P2） | 首頁 CLS 0.3553、媒體庫 0.1605（`WatchingRows` 讀取中回 `null`，資料回來後插在上方整頁下移 440px；改成 `MediaDetailPage` `Loading()` 那種不動的佔位——**實作時改成照上一次的形狀佔位**，見 progress.md 2026-09-24 偏差）；`activeProps` 讓 `border-rule` 與 `border-rule-strong` 同時出現（`AppShell.tsx`、`InventoryPage.tsx` 兩處、`SettingsTabs.tsx`，改走 TanStack 的 `data-status="active"`）；牆 1,621 個 DOM 節點與零 memoization（`page_size` 100 → 50 先做）；兩頁清單語意相反（媒體庫牆 `<h3>` 探索牆 `<p>`、容器 `<div>` 而繼續觀看是 `<ul>`）；重複控制項的名稱（上面的二選一）；同一頁兩個 `<nav aria-label="分頁">`；`ArtSlot` 寫死 342px 無 `srcset`；`Poster.tsx` 與 `ArtSlot.tsx` 合併（`ArtSlot` 多收 `className`）；`?filter=` 抽共用型別守衛（`validateSearch` 擋不住）；`i18n/tmdbText.ts` 改名（它從票 11 起也挑圖） | WCAG 2.2 AA 是 §7 的驗收 |
| 13 | M1.5 critique 剩餘（P1 / P2） | 「待審 / 對不到」篩出來的卡片要說為什麼在這（`has_unmatched` 在 payload 裡卻沒畫）並且**做成一列一件事的清單而不是牆**（與票 05–07 的 `/review` 同一個元件）；媒體庫頁前置內容收成「接著看 N 項」；牆上按名字找（`WallQuery` 加 `q` → Jellyfin `SearchTerm`，寫進網址）；詳情頁四個集數系統至少在季表標題列說明是哪一份、集號欄用 `S01E09`；`InventoryTile` ↔ `EpisodeTile` 合併（只有這一對值得，`MediaTile` 是離群值） | 其中清單那一件是票 05 的 shape 輸入，拆票時看要不要提前 |
| 14 | 前端 e2e 閘門 | 把 playwright 對演練情境跑精靈與送單腳本化進 CI（§10）。**已做（票 15，2026-09-24）** | 可延後 |
| 15 | M2 驗收 | e2e 覆蓋三種破壞 + 一鍵重建 + `user` 越權；里程碑收尾；critique / audit / polish | — |

**遺留清單的歸屬**（M0 票 11、M1 票 15、M1.5 票 11 收尾時逐條過完的；2026-09-22 再審一次，過時的已刪、重複的已併）：

- **A. 跟著上表某張票做**：`duplicate`（07）、Plan item 理由改 code（06）、`list_jobs` 批次（01）、`/jobs/:hash`（11）、`jellyfin_series_id` 回填與「還在掃描」不自更新（08，同一件事）、合併後主條目（08）、`MediaSources` 成本（10，只列一次）、兩個 500（01）、`Season 3 - 46`（01）、M0 的 TVDB 警告與磁碟門檻（08）、大媒體庫三件與篩選後的觀看狀態與刪除帳號（10）、`?filter=` 守衛（12）、P3 九條（02：季表沒 `<caption>`；篩選連結掛 `aria-current="page"`；排序方向 `<select>` 只有 `aria-label`；`ExpandHint` 的字進可存取名稱而 `Dot` 不進；集表「片長」「播出」在 <640px 沒有替代路徑；庫存回應 53 KB `no-store` 無 `ETag`；`TilePlaceholder` 跨目錄 import 且內距差 4px；`routes.cutaway.category` 的 zh-Hant 值是英文；三處硬寫 `alt="TMDB"`）。
- **B. 開工收尾票 02 的小項**：Route 設定頁表單沒改過時「儲存」仍亮且會重跑每一條檢查卻沒說；所有路徑被佔用時「建立並檢查」仍是主動作；確認區「取消」比主動作寬；EN 文案 `Already so` → `Already there`、`Moored` → `Ready`（2026-09-22 使用者改判：`Moored` 只出現在兩個健康標籤上，`Imported` 早已是「已入庫」那一格的字）、`10 of 46 episodes in` → `10 of 46 episodes imported`（驗收是這三句）；EN 子分頁 `Library paths` 改 `Routes`；語言鍵選中態的 `assigned` 黃漆改中性（收掉 DESIGN.md 那條矛盾）；信心在同一塊展開區兩套詞（`信心 high` 與「高信心」）統一；沒接索引站時 `queries` 端點先帶 `problem`；通過 TMDB 閘門後 BTH 3 的詳情列不動；TMDB 與索引站 API key 三處一起改 `PasswordField`；`complete.failed` 缺憑證時錯怪後端；勾選表標出已被佔用的路徑；`HealthPage` / `ServiceSettingsPage` / `SetupPage` 補 `<h1>` 並統一三頁 `h1` 的大小與可見性；非 admin 開 `/settings/*` 靜默 `redirect` 改成帶一句訊息（`routes.tsx` 兩處）；`<summary>` 在無障礙樹是 `generic` 不是 `button[expanded]`（全站 `<details>` 的共同問題，查一次能不能用 `role` 補）；窄版 Route 列截掉路徑尾巴讓三條看起來一樣；健康頁全綠一千像素同一顆綠章重複八次；精靈每一步左欄剖面與右欄纜繩列是同一份清單（重構，可再延）；缺集搜之後關鍵字欄的 placeholder 仍說「留空就用這部作品的各個名字」；`?page=2` 不畫兩列但畫面沒說；電影牆 222 個 Tab 停留點；M1.5 票 01 的 `useritems-resume.restricted.json` / `shows-nextup.restricted.json` 沒有測試引用（補引用或刪）。
- **C. 延後**：缺集散在六季以上只退回作品名——分批的節奏與 M3 的輪詢預算是同一件事，**移到 §11.4**；頁首不 sticky、`/` 聚焦搜尋之類的快捷鍵、探索頁手機上兩面牆沒有跳轉、「說明散在各處沒有通往文件的出口」——票 15 就判「不排里程碑」，沒有新證據，**不進 M2**；記在這裡是為了不再逐輪重審。
- **D. M2 收尾（票 16）過完票 01–15 的 Comments 之後延後的**，都不屬 M3 / M5 AI 的範圍，**不排里程碑**，有 repro 或使用者要求再開票：`ROUTE_CHECKS` 仍是手寫字面聯集（收緊要先替 Route 檢查另開 `RouteCheckOut`，票 02 / 02a）；精靈左欄剖面與右欄纜繩列兩份實作（上面 B 組那一條，票 03 仍沒做）；對不到的**字幕**只能忽略、不能指派到某一集（票 08，rematch 的延伸）；`issues.detail_json.action` 一鍵兩義——偵測時是 `PlanAction`、resolve 時被覆寫成按了哪一顆（票 09，改鍵名要動前端）；~~qBittorrent 5.x 對停住的 torrent `recheck` → `start` 沒實測過（票 09c）~~（M3 票 03 量了：5.x 上會再停住，順序改成 start → recheck）；`AccountDisabledError` 也涵蓋「帳號被刪掉」，名實不符（票 11，對外的 `account_disabled` 不動）；`.impeccable/design.json` 沒有閘門、跟不上 `DESIGN.md` 已經第四次（票 13，一條比對測試守得住）。M3 票 06 過完 M2 票 16 的 critique / audit 遺留之後延後的三條：Job 摘要列只浮上 audit，對不到與重複待決沒有（要後端 `JobOut` 多兩個計數）；時間兩套寫法——佇列列是絕對時間、Job 頁是相對時間，`whenText` 與 `Timestamp` 各自格式化（要先定一個全站慣例再收成一份）；七處輸入框的 class 字串手寫、`rule-strong` 輸入框邊框的規則沒有閘門（下一次改輸入框外觀時收成一個常量，閘門就是「都用它」）。

### 11.4 M3 RSS

> **2026-09-26 驗收完成（票 21）**：八條驗收是真服務 e2e 的第四個模組（`tests/e2e/test_4_m3_rss.py`，公開 RSS 站由 `sites` 容器冒充）；自動綁定在同類型 Route 不只一條時用 Feed 的 Route（brief §15、§19）。

> 2026-09-24 拆成 21 張票，同日插入 06b–06f、次日插入 06g–06i，09-26 插入 14b，共 30 張；編號與內容以 `.scratch/m3/issues/` 為準：01–06i 是下方「M3 之前先做的修補」與兩個頁面決定，07 起是 RSS（tracer 是 08）。

**票 11 做完**：Nyaa、acg.rip adapter，非 Mikan 的 RSS Series 鍵，新 Feed 的第一輪預覽（§2.4、§6、§8.5）；Mikan 不走預覽（shape 拍板）。

**票 13 做完**：Plan 記下它用的季號與 offset（§2.3）；RSS Series 的第一批進 audit、在 `/review` 以 Series 分組一顆「全部確認」、確認之後 medium 不再進 audit（§2.4、§6 review 那一列）；改正一集可以「套用到這個 RSS Series」（`POST /files/rematch` 的 `apply_to_series`，§4.4、§6 files 那一列）。

**M4 票 11 做完**（第一批證據夠強時跳過，brief §15 那一段是規則本身）：純函式 `parser.vouch_first_batch`（逐條件雙向測試 `tests/unit/test_parser_first_batch.py`）；`services/first_batch.vouch` 在規劃器寫計劃之前看整批（同一個 Series 的其他 Job 都落地、掛著 audit 的每一份也擔保得了），擔保了的那一份不掛 audit，計劃落地之後 `confirm_by_batch` 確認 Series、清掉整批其他 Job 的旗標、每一筆記事件 `series_confirmed`（`series`、`name`、`episodes`）。還在等人的那一批在問什麼是 `first_batch.asks`（`FirstBatchBasis`：`literal` / `series` / `absolute` / `runs` / `arc` / `mixed`），`GET /review` 的 audit 列 `series.ask` 與 `series.group`、`GET /rss/series` 的 `ask` 帶著它；前端 `rss/firstBatchAsk.ts` 說那一句，審核頁那一組的鍵改成「確認整個 Series」。

**票 15 做完**：片長驗證（§4.1）、新理由 `runtime_conflict`（§3.1）；短於 5 分鐘的仍歸 `classify`。

**票 19 做完**：從 Media 頁訂閱（§6 rss 那一列、§2.4 `rss_feeds` 的三欄）：Mikan 代搜番組、選字幕組、建單一 feed 並綁上（`rss.subscribe_mikan`）；Nyaa / acg.rip 以標題建搜尋 feed，長出的 Series 預先綁定（`rss.subscribe_search`）；詳情頁的「RSS 訂閱」段只有 admin（`media/SubscribePanel.tsx`，`.scratch/m3/subscribe-shape.md`）。

**票 18 做完**：一次性 RSS 連結（§6 rss 那一列）：讀是 `POST /rss/oneshot`（只讀），送是逐筆的一般送單；排除條件不擋，合集標出來照樣勾得了。

**票 14 做完**：播出日比對兩條規則（§4.4）、新理由 `air_date_conflict`（§3.1）；發佈時間住在 `jobs.published_at`（§2.3），手動送單由結果表帶回來（`JobSourceIn.published_at`，§6 jobs 群組），搜尋結果表多一欄「發佈」（`SearchResultOut.published_at`）。

範圍（2026-09-24 依 brief §15 重寫）：Mikan、Nyaa、acg.rip adapter（先抓 fixture 定欄位）、feeds / series / items 資料流、`rss_poller`、RSS Series 自動綁定與待綁定清單、三層排除條件、去重、Mikan 的補舊集與每日補漏、新 Feed 的第一輪預覽、RSS Series 的季號與 offset（第一批審核、套用到整個 RSS Series 並重算）、一次性 RSS 連結、從 Media 頁訂閱；播出日比對、片長驗證與 Jellyfin 回驗（見下）；**已確認的 RSS Series 之後的 medium 入庫不再進 audit 清單**（2026-09-24 使用者拍板：第一批確認過之後改由回驗與每日檢查守著，出錯變成 Issue，不必每週打開 Berth 按確認）。
驗收：一個 Mikan 聚合 feed 加一個 Nyaa 或 acg.rip 搜尋 feed 全自動追完；中途訂閱的一部補齊舊集，之後的新集自動入庫；同一集兩個字幕組、同組 v1 與 v2 都並存；合集被排除；一部 split-cour 在審核裡改正一次之後其餘集數跟著對；一筆發佈時間與換算出的那一集播出日對不上的不自動入庫；Jellyfin 認到的季集與帳本不同時開出 Issue；已確認的 RSS Series 的新集數不出現在 audit 清單。

**入庫前後的三道程式檢查**（2026-09-24 使用者拍板，不需要 AI）：① **播出日比對**——Feed Item 的發佈時間對換算出的那一集的 TMDB 播出日：發佈早於播出日（容忍兩天）一定算錯；連載中的 RSS Series 對到的那一集比同作品最近播出的一集早很多也算可疑。這是抓 split-cour offset 算錯的主要一道：Jellyfin 認集數靠 Berth 取的檔名，Berth 算錯的集數會原樣抄進 Jellyfin，回驗看不出來。可疑的不自動入庫、送審核；BD 版晚幾個月才發會落在這裡，可以接受。手動送單也套第一條（索引站的 `publishDate`，同日試跑時加；發佈時間的實測見 brief §20.11）。**第一條只抓得到換算到還沒播的集數**，反方向——新一季被當成第一季（TMDB 還沒建新一季、字幕組沿用標題從 01 重數）——換算出的是早就播過的集數，發佈晚於它是正常的。所以「TMDB 只有一季 → 推論成第一季」維持 medium；**待議**：發佈時間離換算出的最後一集播出日很近時升成 high（剛播完的這一季，中間塞不進已經開播的新一季），遠時維持 medium——遠不能用來擋，補舊番與 BD 版都長這樣。發佈時間是條目的貼出時間、會偏晚（§20.11），門檻要拿票 14 存下的真實資料量。做的話畫面上寫日期與它為什麼影響判斷（理由 code 帶日期參數），不顯示成分數或「新鮮度」指標（brief §6.5 不用單一分數黑箱）。與 §11.4 開頭「以發佈時間推測虛擬季」用同一份資料，但驗證比推測簡單可靠。② **片長驗證**——mediainfo 的片長對 TMDB 那一集的片長，差太多不自動入庫；抓的是分類錯誤（預告、NCOP、SP / OVA、兩集合併檔被當成一集正片），抓不到同一季裡算錯的集號；TMDB 沒有那一集片長時跳過。③ **Jellyfin 回驗**——入庫後 Jellyfin 認到的季集、所屬 Series 的 `ProviderIds.Tmdb` 與帳本不同就開 Issue；抓的是 Jellyfin 那邊的意外（兩份涵蓋範圍不同的正片被合成一集、檔案沒被認成正片），是便宜的保險而不是主力——資料夾名帶 `[tmdbid-…]`、檔名格式 M0 實測過。**M3 票 17 做完**：resolver 找到 item 之後比季集與作品，對帳的 Jellyfin 那一方比同一份（§3.2）；Issue 型別 `jellyfin_item_mismatch`（§2.4），動作只有「重新反查」。

**v2 並存，不取代**（2026-09-24 使用者拍板，brief §19）：同一字幕組同一集的 v1 與 v2 tags 不同（`version`），兩份都入庫、在 Jellyfin 是同一集的兩個版本，使用者播放時自己選；不拆 v1 的鏈接。與 brief §7.7、§18「品質升級自動替換不做」一致——這一行原本寫「v2 取代」，與它們矛盾。所以 RSS 的去重鍵要把 `version` 算進去：同組同集的 v2 不是重複。

**開工前的兩題已定**（2026-09-24，brief §15、§19）：不做字幕組白名單——字幕組是使用者在 Mikan 或 feed 網址上挑的，Berth 全部接受、只提供排除；季號與 offset 放在 RSS Series 上、規劃時讀。

**M3 之前先做的修補**（2026-09-24 M2 後的全面審查，使用者拍板「先修再開 M3」；審查紀錄見 progress.md 同日）：RSS 無人值守，下面幾條會從偶發變成每週發生；批次確認是「沒有 AI 也要把人工降到最少」（brief §14）。拆票時排在 M3 的 tracer bullet 之前。

- 會刪檔的三條路刪之前比 inode：刪除範圍的「移除鏈接」（`services/deletion.py`）、audit 撤銷（`services/review.py`）、rematch 拆舊鏈接（`services/rematch.py`）。使用者把硬鏈接換成自己的檔案之後，三者都會刪掉它。**M3 票 01 做完**：三條共用 `deletion.Placed.holds`（帳本記的 inode 或來源現在的 inode，兩者都對不上就不刪），回應與時間線列出沒刪的那幾個（`unmanaged`）。
- `POST /jobs/*/replan` 在 `review` 狀態要 admin（`api/gate.py` 的 `ADMIN_ROUTES`）：`user` 重算會推翻 admin 的撤銷。**M3 票 04 做完**：守在命令裡而不是 `ADMIN_ROUTES`（門禁看不到狀態），403 `review_needs_admin`（§6 jobs 群組）。
- 卡死的 Job：`submit_failed` 在 qBittorrent 其實收下時要能被 poller 認回；`requested` 在程序中途掛掉時要有出路；`guarded` 吞掉的非預期例外要寫進 `Job.error` 與時間線。**M3 票 02 做完**：poller 認回（§3.1）、啟動時落到 `submit_failed`（§3.1，理由在那一列）、`round_failed`（§3.1 下方）。
- 刪除只勾「移除鏈接」之後，對帳不再為那幾列重開 `library_link_missing`（同 `source_missing` 的處理）。**M3 票 01 做完**：帳本寫 `unlinked`（§2.4）。
- 刪除在鎖內讀 Job 狀態，compare-and-set 輸了回報失敗而不是成功。**M3 票 01 做完**：409 `moved_on`（§3.1 最後一列）。
- 管線 Issue（`missing_files` / `client_error` / `client_removed`）在 Job 被別處修好之後由系統收掉（M2 票 09c 的延後項，失效條件票上已有）。**M3 票 02 做完**：§2.4。
- `add_download` 送單前看磁碟門檻（現在只開 `low_disk_space` Issue，不擋送單）；刪除過、沒清紀錄的 Job 不能再下載同一個 hash。**M3 票 04 做完**：409 `low_disk_space`（§3.2 `health_checker` 那一條）、409 `job_removed`（§3.3）。
- qBittorrent 5.x 停住的 torrent `recheck` → `start` 補量（§11.3 D 組第 5 條延後的前提不成立：compose 預設就是 5.x）。**M3 票 03 做完**：5.2.3 上 recheck → start 校驗完又停住（缺檔的那一包停在 `stoppedDL`，poller 永遠等不到它動），「重新校驗」改成 start → recheck（§3.1、brief §20.2）。
- 審核頁的**批次確認**：同一個 Job 或同一個 RSS Series 的 audit 一組一顆「全部確認」（2026-09-24 使用者拍板；e2e 那一包芙莉蓮的 11 個特典目前要逐一按）；audit 段另有一顆整段的「全部確認」，只確認畫面上列出的那些（同日試跑時加，一包 12 集全是 medium）。**M3 票 05 做完**（同一個 Job 那一種；RSS Series 那一種在票 13）：§6 review 那一列。
- 前端：逐列編輯有沒套用的改動時「核准並入庫」要擋；核准 / 撤銷 / 修 Issue 之後讓 `['media']` 失效；401 導回登入；動作鍵送出中不可再按。**M3 票 06 做完**：§7 的守衛、資料與送出中三條。
- 部署：五個對外 port（Berth、Jellyfin、qBittorrent WebUI 與 BT、Prowlarr）進 `.env`；Jellyfin 的 port 同時交給 Berth 做深連結推導，qBittorrent 的 WebUI port 內外兩側一起換，Berth 的套件內位址跟著走（2026-09-24 使用者拍板，brief §19；票 06b）。其餘設定仍在精靈與設定頁。
- 精靈第 1 步的「將會寫入」剖面照偵測結果說話：qBittorrent / Prowlarr 寫的是整組帳密而不是只有密碼；第 2 步偵測之前不斷定哪個服務會被寫入或建立管理員（2026-09-24 使用者重跑精靈時指出；票 06c）。
- 精靈導覽與泊位（同日重跑精靈時使用者拍板，brief §19）：每個泊位做完停在結果上、上一個 / 下一個泊位、泊位板上走過的可點、回頭看時有出口（票 06d，開工前先 `/impeccable onboard` shape）；索引站與 TMDB 拆成兩個泊位（板變 5 格）、索引站顯示語言與說明、加入後可試搜與移除、預設清單拿掉已不存在的 AniDex（票 06e）；套件內 Jellyfin 的媒體庫由使用者命名與增刪（票 06f）。
- 精靈偵測：服務還在啟動時的暫時錯誤當「探測中」——Jellyfin 啟動中回 503 時整支探測冒成 500、回應不像 Jellyfin 時被判成既有，前端又只在有 `pending` 時才輪詢，所以要人按「重新探測」（2026-09-25 重置試跑環境量到時間線；票 06g）。走過泊位 1 之後「改帳密」改不到 Jellyfin，併進 06c。
- 精靈驗收（票 06h，06b–06g 之後）：e2e 改成冷啟動——現在的 `up --wait` 等四個容器都健康才開始精靈，碰不到啟動中的那幾秒，所以 06g 沒被擋下；playwright 補既有服務與冷啟動兩條；精靈單獨跑一輪 `/impeccable critique`、`audit`、`polish`；使用者在試跑環境重置後實走一次。
- 設定頁接手精靈跑完之後的修改（票 06i，brief §19）：設定頁分五頁對應五個泊位、重用精靈那一格的元件；`/setup` 在精靈跑完之後導向設定頁，`?berth=` 回精靈的路與「改位址或憑證」刪掉；README 的「設定 → 來源」不存在，一併改正。

同一輪的兩個頁面決定（brief §19 同日）也排在 M3 之前：**探索頁不再放繼續觀看與下一集**，登入後預設落在媒體庫；**`/review` 不再列 Issue**，Issue 只在 `/issues`，`/review` 原位留一行「另有 N 件待處理」。兩條都做完（M3 票 06、05）；`GET /jellyfin/watching` 隨前者刪掉。

M1 帶過來的一條（票 15）：brief §6.4 的「以**發佈時間**推測虛擬季」票 06 刻意沒做——解析器那時拿不到發佈時間。RSS item 一定帶著它，接上之後回頭補，要有自己的語料與一輪 `berth bench`。**票 16 做完**：規則見 §4.4「以發佈時間推測虛擬季」，語料多了 `published_at` 欄位（`tests/fixtures/parser/README.md` v6）。

M1.5 帶過來的一條（票 10，2026-09-22 從 §11.3 移來）：缺集散在六季以上時只退回作品名，不分批問——一次搜尋的查詢數上限是為了不把公開站打到封 IP（§8.4）。分批的節奏與 RSS 輪詢的預算是同一個決定，在這裡一起定。**票 20 做完**：規則見 §3.2「一個站一份請求預算」與 §8.4 的缺集分批。

**M3 收尾（票 21）過完票 01–20 的 Comments 之後延後的**，不排里程碑，有 repro 或使用者要求再開票：核准被播出日比對擋下的列、以及 `held_proposal` 重算的列不再比帳本，`span_clash` 與重複版本會漏（票 14 / 14b，核准那一步再比一次）；每集短於 5 分鐘的短篇動畫被 `classify` 整包降成 extra，註解說的批次一致性救回並不存在（票 15，可以改看 TMDB 片長）；RSS 的兩個並行窗口——`_rescreen` 先讀再寫會把剛送出的 Item 改回 `excluded`、`prime_feed` 與背景 poller 同寫一批 guid 撞 unique 冒 500（票 10 / 11，條件式 `UPDATE` 與 `ON CONFLICT DO NOTHING`）；`QUEUE_LIMIT` 截斷時組上的「全部確認」只確認畫面上的列，Series 卻整個標成確認過（票 13）；精靈跑完之後改 `QBITTORRENT_WEBUI_PORT`，Berth 仍連存下來的舊位址（票 06b，README 已寫要先定）；既有 Jellyfin 帳密錯只顯示 `POST /Users/AuthenticateByName: 401`，沒有對成「帳號或密碼不對」（票 06h）；票 16 的「以發佈時間推測虛擬季」偏離票面的兩處（只推「某一輪的重數是發佈前六週內播的」、只套到篇章名；progress.md 偏差 2026-09-26）使用者還沒追認；真站一輪（票 21）一次送進近兩百個 torrent 時，qBittorrent 在 `GET /api/v2/torrents/categories` 回 `ReadTimeout`，那一筆停在 `submit_failed`——沒送到 qBittorrent，票 02 的 poller 認回接不到，只能人按重試（2026-09-26 移到 §11.5「M4 之前先做的修補」，M4 票 03）。

### 11.5 M4 巡檢與通知

2026-09-24 排到 AI 之前（使用者拍板，brief §14、§19）：Berth 平常不必打開——看片用 Jellyfin App，只在加新作品時開——前提是**有事需要人的時候它會說**。這一輪不需要 AI；M5 起 AI 只是讓要人處理的事變少。

**巡檢**：每天一次程式檢查（不花 token）：RSS Series 缺號、同一集意外多份（播出日比對與片長驗證漏掉的在這裡事後抓）、Jellyfin 回驗不一致、卡住的 Job、一直失敗的 Feed、等人處理的事放太久。每週一次週報：這週入庫了什麼、修了什麼、還有什麼等人（頁面 + 通知）。M5 起完整巡檢把標出來的交給 AI 任務。

**通知**（2026-09-22 使用者拍板加入，brief §14、§17、§19）：`events` 表上的**訂閱者**——哪些事件型別要送出去（第一批：一集或一部入庫並在 Jellyfin 反查到（「可以看了」）、RSS 命中並送單、**有 N 件等你處理**（連結直接開到那一件）、週報、Issue 新增）、送到哪一個**管道**（`adapters/notify/` 的 channel adapter 介面 + 第一個實作，Telegram 或 Discord 擇一，拆票時定）、每位使用者自己的訂閱與管道設定（`settings.notify` 或 `users` 上的欄位，拆票時定）、送出的紀錄與失敗重試、設定頁的測試按鈕。**不是**推播給瀏覽器（SSE 已經有），是人不在 Berth 頁面上時的那一條。

驗收：一個 RSS 命中 → 下載 → 入庫 → Jellyfin 可見的全程，使用者的手機收到「正在下載」與「可以看了」兩則，內容說得出作品、季集與 Route；一件進審核的事推出「等你處理」並連到那一件；週報說得出這週入庫、修了什麼、還有什麼等人；管道掛掉時 Berth 不阻塞任何管線、健康頁說得出來。

M3 收尾帶過來的兩條：巡檢的「一直失敗的 Feed」要分得出是補漏失敗還是輪詢失敗——現在拼在同一個 `rss_feeds.last_error`（M3 票 12，拆欄）；`jellyfin_item_mismatch` 被「忽略」之後，第二天對帳會重開，通知的「Issue 新增」等於每天推一次，改用健康檢查的「條件持續期間忽略有效」（`health_issues._still_ignored`，M3 票 17）。**2026-09-26 補**：`_still_ignored` 讀的 `cleared_at` 只有 `health_issues._settle` 會寫，`resolver.settle_verdicts` 不寫，要搬過去；而且它只解「忽略之後又重開」，試跑量到的主因是下面修補清單第 2 條的誤報。

**M4 之前先做的修補**（2026-09-26 M3 後的全面審查，使用者拍板「先修再拆 M4」；審查紀錄見 progress.md 同日）：試跑環境（main `82d9cd7`）一個 Mikan MyBangumi 綁定後 11 分鐘送出 144 個 torrent，下面幾條在這一輪都真的發生了，而 M4 的通知會把它們放大成推播。票已開在 `.scratch/m4/issues/01–04`，同日第二輪試跑回饋再開 05–14（清單最後一條），`/to-tickets` 拆 M4 時從 15 接著編。

- SQLite 寫鎖：poller 握著寫交易逐筆拿 `job_lock`，planner 先拿 `job_lock` 再寫，順序相反，試跑爆出 `database is locked`；另有四處握著寫交易打網路（`rss._record` 的單集頁、`bind_series` 的補舊集、刪除移除 torrent、重試送單）；`round_failed` 之後下一輪成功不清 `job.error`。交易紀律定在 §3.3（票 01）。
- Jellyfin 回驗誤報：Jellyfin 還在認剛掃進來的檔案（季集 `None`、Series 沒有 Tmdb）就被判成不一致，找到 item 當下又停止反查；`importer.restate_versions` 以整個資料夾而不是同一集重排，一季每入庫一集就把前面每一集重反查一次，`jellyfin_item_resolved` 一筆 Job 寫 5–7 次。「可以看了」的單一事件在這張票定（票 02）。
- 大批送單：磁碟門檻不扣在途量；暫時失敗的 `submit_failed`（qBittorrent `ReadTimeout`、停機）要有限重試，不留給人逐筆按（原在 §11.4 結尾）；.torrent 下載要不要進請求預算開工時問使用者（票 03）。**票 03 已做**：門檻扣在途量（§3.2 `health_checker` 的磁碟那一段）、暫時失敗由 poller 自動重送（§3.1）、`.torrent` 維持不進預算（§3.2 請求預算那一段）。
- `GET /jobs` 沒有分頁、前端每個 SSE 事件都整份重抓（2026-09-22 記「歸票 12」後沒有人接）（票 04）。**票 04 已做**：分頁與四組篩選（§6 jobs、§7）、SSE 失效合併（§6 events）、刪除估算移出 `['jobs']`。
- **試跑回饋（2026-09-26 第二輪，使用者拍板）**：既有服務被判成套件內、登入被覆寫與 qBittorrent 全域偏好被改（票 05，最先做）；精靈改為 Jellyfin 優先（票 06、07）；媒體庫路徑與索引站兩個泊位（票 08、09）；精靈完成與空媒體庫落在探索、JSX 註解外露（票 10）；第一批審核證據夠強時跳過（票 11，**已做**：§11.4 的「M4 票 11 做完」）；作品頁的下載段（票 12）；同日續談定案：RSS 頁以作品呈現 Series、完結自動收起（票 13），自動綁定的暫時失敗重試與季名（票 14）；補舊集維持一律全補（brief §19）。

**拆 M4 票時要定的**（同一輪審查，事實與行號在 progress.md 同日）：`record_event` 一定要一筆 Job，Issue、Feed 失敗、週報都成不了事件——「`events` 表上的訂閱者」要嘛放寬事件，要嘛另立通知的 outbox，擇一並改寫上面「通知」那一段；`events` 會被 purge 刪列，id 不能當游標；「連結直接開到那一件」要 Berth 自己的對外網址，現在只有 Jellyfin 有 `public_url`；RSS 送出的 Job `user_id` 是 `None`，「正在下載」送給誰要定；「正在下載」要按輪彙整（一次綁定就是上百則）；「可以看了」要照使用者的 Jellyfin `UserViews` 過濾；自動綁定一個候選讀不到 TMDB 就整次 `lookup_failed` 而且不重試、標題帶「第四季」這類季名時搜不到候選，這兩種會讓「等你處理」虛胖（已開 M4 票 14）。

### 11.6 M5 AI 核心

2026-09-24 重排（brief §6.10、§14、§19）：**AI 只替人按審核頁、待處理頁上的那些按鈕**——可撤銷的 AI 自己做，不可撤銷的與 AI 沒把握的交給人。規則層仍是主力；**沒有 AI 時 Berth 完整可用**，每一種 AI 任務都有同一個命令的人工版本，關掉 AI 或超出預算時退回 M4 的行為。

範圍：

- provider（Anthropic 實作，介面保留給其他家）、`settings.ai`（憑證、月預算、各任務型別的模式）、每次呼叫記 Event（model、tokens、費用）、快取鍵。模型與價格開工時查當時的官方資料。
- **命令登錄表**：services 命令逐一登錄 pydantic 輸入、結果與拒絕理由、副作用等級（`read` / `reversible` / `irreversible`）與反向命令。AI 的工具只從這裡來；M7 的 MCP server 包的也是它。**M3 起新增的命令先標好等級與反向命令**，表本身在這裡開頭做。登錄表開工時要處理的兩條（M3 收尾）：`confirm_audit(s)` 的反向命令標成 `review.undo_audit`，語意對不上（它拆入庫，而且拒絕確認過的列）——另立「取消確認」或改成 `inverse=None`（M3 票 05）；`services/issues` 仍在 `BEFORE_M3` 豁免表，`resolve_issue` 的各個動作要逐顆標（M3 票 17）。**2026-09-26 全面審查更正**：「M3 起新增的命令先標好」只對 M3 新建的*模組*成立（`tests/unit/test_command_marks.py` 守的是模組），豁免表裡 42 個模組都還沒標，不只 `services/issues`；M3 加進舊模組、會改狀態的命令也沒有標（`jellyfin.save_bundled_libraries`、`jobs.fail_interrupted`、`issues.close_settled`、`resolver.settle_verdicts`）。已標的也有兩條要重看：背景迴圈的入口 `rss.poll_due` 標成 `REVERSIBLE`，登錄表會把它當成 AI 工具；`rss.delete_feed` 連帶刪掉 Feed Item（CASCADE），卻標成可逆、反向是 `add_feed`。命令簽名吃 session 與 factory、拒絕是各模組自己的例外，離「pydantic 輸入」還有一段。
- **AI 任務**（`ai_tasks` 表）與 `ai_worker` 迴圈：事件觸發，一個任務一件事，帶資料包、允許的工具與預算上限，結果是「已處理」或「交給人（附理由）」——交給人的走 M4 的「等你處理」通知。
- **自主權看可逆性**：`reversible` 通過驗證後自動執行；`irreversible` 一律做成 Proposal（`proposals` 表）等人。刪 complete、移除 torrent、purge、改設定與 Route 永遠要人；「忽略 Issue」也做成 Proposal。
- **驗證**：M3 的三道程式檢查（播出日比對、片長驗證、Jellyfin 回驗）加上集在 TMDB 存在、不撞目標路徑、季集範圍，AI 的結果照樣走一遍；不通過的不套用、交給人。
- **影子模式**：每種任務型別先影子（只記錄 AI 會怎麼做，照舊由人決定，統計一致率），使用者看數字切自動，可隨時切回。
- **AI 活動**頁：做了什麼、理由、花費，逐筆撤銷。審核頁每一件附 AI 交上來的理由。
- 第一批任務型別：規則層 low 的 Plan（§4.5）；Unmatched 檔案與待綁定 RSS Series 猜作品；RSS Series 的季號與 offset 修正（寫回 RSS Series、重算未確認的集數）；audit 的確認或撤銷；三道程式檢查標出的可疑入庫。
- 修正回流：寫回 RSS Series、標題別名、排除條件；改正過的案例進 benchmark 候選語料。

驗收：第一批每種任務在影子模式跑一週真實資料、與人的決定一致率達標（門檻拆票時定）；benchmark 上 `auto_wrong` 不升、review 比例下降；AI 不能在沒人確認下執行任何 `irreversible` 命令（整合測試）；每次呼叫的 tokens 與費用在 Job 時間線與 AI 活動看得到；關掉 AI 時行為與 M4 相同。

### 11.7 M6 Issue 與側面板

範圍：Issue 的各型別變成 AI 任務（重新鏈接、recheck、rematch 這些可逆的自動；刪 complete、移除 torrent 這些不可逆的做成 Proposal）；**側面板**（每一頁都開得到的對話區，工具是同一份命令登錄表）——使用者在場時自己要求的可逆動作直接執行並給撤銷，不可逆的以 Proposal 卡確認；工具權限（哪些命令 AI 永遠不能自動、預算與速率、每一次呼叫記 Event）沿用 M5。

驗收：一件 `library_link_missing` 不經人修好；側面板裡說「把這一集標成已看」「這部作品缺的集搜一下」做得到；「把這部的 complete 刪掉」停在 Proposal，人按確認才執行（整合測試）。

### 11.8 M7 外部對話與 MCP

範圍：把 M4 的管道接上同一個核心——同一個 Telegram / Discord bot 既推通知也收訊息；訊息的身分對到 Berth 的使用者（個人 API token，brief §16.2）並帶著他的角色；Proposal 在外部管道上是一則帶按鈕的訊息，確認 / 拒絕回到同一個 `proposals` 列；每個管道自己的訊息長度與按鈕限制在 adapter 裡吸收。**命令登錄表另外包成 MCP server**（同一組個人 API token 與門禁），讓使用者用 Claude Code / Claude Desktop 直接查與操作 Berth。

驗收：在手機的聊天軟體裡收到「S02E05 正在下載」，回一句「下好了通知我並標成已看」，Berth 在入庫後推第二則並標成已看；`user` 角色在外部管道與 MCP 上碰到的是同一道門禁；Claude Code 經 MCP 查得到本週入庫。

---

## 12. 風險與回寫點

| 風險 | 影響 | 對策 / 回寫 |
| --- | --- | --- |
| Jellyfin 對方括號 tag 或 ` - ` 分隔的解析不如文件（brief §20.1） | 命名模板 | T0.3 實測後凍結 §5；只改 `naming/` |
| Windows 使用者把 `DATA_ROOT` 指到 exFAT 隨身碟，或分開掛兩個目錄 | 硬鏈接失敗 | NTFS bind mount 已實測可用；健康檢查在精靈頁 3（媒體庫與路徑）就擋下並說明原因 |
| Jellyfin 首次啟動較慢，精靈頁 1 呼叫 `/Startup/*` 時服務尚未就緒 | 精靈失敗 | 選了套件內之後每 3 秒重測至就緒（上限 2 分鐘）才給擁有者表單；每步可重試 |
| 既有 Jellyfin 使用者把媒體庫搬到新路徑而不是加路徑 | 觀看紀錄歸零 | 精靈只提供「加入路徑」，文件明說不要搬；健康檢查不會建議改既有路徑 |
| 既有服務的容器路徑各不相同（`/downloads`、`/tv`、`/movies` 分開掛） | 硬鏈接 `EXDEV`、探測檔看不到 | 檢查訊息附那一台要多加的 `${DATA_ROOT}:/data`（compose 與 `docker run`）；`docs/guide/existing-services.md` 用 NAS 範例說明「原本的掛載不動、多加一條」（M4 票 36） |
| TMDB 與字幕組的動漫季編號不一致 | medium 誤入庫 | benchmark 分開報告 medium 錯誤率；offset 偵測；M3 的 RSS Series offset 與第一批審核；後續接 anime-lists |
| Jellyfin 的大版本再跳一次（12 → 13）：版本分組、版本名算法或 `/Startup/*` 那幾支 deprecated 端點被移除 | 多版本顯示、精靈頁 1 與頁 3 | 支援下限寫在一處（`adapters/jellyfin.MIN_VERSION`）；版本名讀 Jellyfin 回的而不是自己算；`/Startup/*` 在 13.0 前要換成設定端點（brief §20.9） |
| Mikan / Nyaa feed 欄位與假設不同 | M3 | 先抓 fixture 再寫 adapter |
| qBittorrent 版本差異（`paused` / `stopped`、`save_path` 鍵名） | 送單失敗 | 契約測試涵蓋 4.4 與 5.x |
| medium 自動入庫錯誤率偏高 | 使用者信任 | 收緊 medium 定義（brief §6.5），不關自動入庫 |
| 單程序內背景迴圈互相拖慢 | 延遲 | 迴圈各自 try/except 與退避；必要時拆第二程序 |
