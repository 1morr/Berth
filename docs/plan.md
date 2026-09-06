# Berth 實作計劃

> 依據 `docs/design-brief.md`（以下簡稱 brief）。brief 說「做什麼、為什麼」，本文件說「怎麼做、誰先誰後」。兩者衝突以 brief 為準；本文件若改動 brief 的決定，必須同輪回寫 brief。
>
> 閱讀方式：§1–§8 是架構，開工前讀完；§9 開箱即用；§10 測試；§11 里程碑任務，M0 與 M1 拆到可直接開工的粒度，M2–M4 只列範圍與驗收；§12 風險與回寫點。
>
> 標記沿用 brief：【決定】【建議】【研究】。

---

## 0. 工程慣例

- 語言：程式碼、識別符、commit、log 一律英文；文件與註解繁體中文。
- Commit：Conventional Commits，subject ≤ 72 字元。分支 `feat/…`、`fix/…`、`docs/…`。
- 每個里程碑結束時 `main` 可部署、CI 綠燈、README 可照著跑。
- 改動指令、環境變數、目錄結構、對外介面或資料格式時，同輪更新 README、`.env.example`、CHANGELOG、專案 `CLAUDE.md`。
- 型別：後端 mypy strict（第三方缺型別時局部放寬並註明）；前端 TypeScript strict。
- 行為變更同步補測試；解析器改動必跑 benchmark（§4.6）。

---

## 1. 架構總覽

### 1.1 執行形態【決定】

- **一個容器、一個 Python 程序**：FastAPI 提供 HTTP API 與靜態前端；背景迴圈（§3.2）以 asyncio task 在同一程序內跑，於 lifespan 啟動與關閉。
- **SQLite**（WAL 模式），檔案 `/config/berth.db`；Alembic migration 在啟動時自動套用。
- **前端 React SPA**，build 產物由 FastAPI 以靜態檔案提供；開發時 Vite dev server 代理 `/api`。
- 對外只有一個 port，預設 `8383`。
- 路徑常數：`/config`（DB、設定、log）、`/data`（媒體根，brief §4）。兩者可用環境變數覆寫以便本機開發。

理由：單使用者到單家庭的規模，一個程序足夠；Seerr 與 AutoBangumi 都是這種形態。之後若解析或對帳變重，先把背景迴圈拆成第二個程序，不改架構。

### 1.2 後端套件結構

```
berth/
  main.py              FastAPI app 組裝；lifespan 啟動 migration 與背景迴圈
  config.py            環境變數、路徑常數、版本號
  db/                  engine、session factory、Alembic 環境
  migrations/          Alembic versions
  models/              SQLAlchemy ORM（§2 的表）
  domain/              純資料型別與狀態機，無 IO：JobState、ReleaseInfo、Tags、Candidate、PlanItem、Confidence
  parser/              純函式：classify、cjk、release、structure、mapper、subtitles、planner、confidence
  naming/              純函式：title 選擇、sanitize、tag 渲染、路徑模板
  adapters/            外部服務：qbittorrent、jellyfin、tmdb、torznab、prowlarr、rss/{mikan,nyaa,generic}、fs、mediainfo
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
  docker-compose.yml   開箱即用套件（§9）
  .env.example
  preseed/             qBittorrent 與 Prowlarr 的預置設定檔
scripts/experiments/   brief §20.6 的實驗腳本
```

### 1.3 依賴規則【決定】

```
api ──► services ──► domain / parser / naming / adapters / models
pipeline ──► services
parser, naming ──► domain            （純函式；TMDB 資料以快照物件傳入，不呼叫網路）
adapters ──► domain                  （不 import services、models；回傳 domain 型別或簡單 dataclass）
```

- 所有會改變狀態的操作都是 `services` 內的命令函式，名稱即 brief §14 的命令名（`add_download`、`generate_plan`、`apply_plan`、`rematch_file`、`delete_job`…）。API 與 pipeline 只呼叫 services，兩者都不直接碰 adapters 或 models。
- 用 `import-linter` 在 CI 強制上述方向。
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
| 套件管理與工具 | uv、ruff、mypy、pytest、pytest-asyncio、respx | — |
| 前端 | React 18、TypeScript、Vite、TanStack Query、TanStack Router、Tailwind、shadcn/ui、react-i18next | 通用、可長期維護；shadcn 讓元件在 repo 內可改 |
| 前端工具 | pnpm、eslint、prettier、vitest、playwright | — |

---

## 2. 資料模型

表名與欄位。型別以 SQLite 慣例（TEXT / INTEGER / REAL / JSON 以 TEXT 存），時間一律 UTC ISO 8601。`*_json` 欄位對應一個 pydantic model，序列化集中在 `models/`。

### 2.1 使用者與設定

- `users`：`id`、`jellyfin_user_id`（unique）、`name`、`role`（`admin` / `user`）、`created_at`、`last_login_at`
- `sessions`：`id`、`user_id`、`token_hash`、`expires_at`、`created_at`
- `settings`：`key`（unique）、`value_json`、`updated_at`。key 分組：`services.jellyfin`、`services.qbittorrent`、`services.indexer`、`services.tmdb`、`paths`、`parser`、`ai`、`rss`、`setup`。每組一個 pydantic model，`services.*` 含連線資訊與最後健康狀態。

### 2.2 Route 與 Media

- `routes`：`id`、`slug`（unique）、`name`、`jellyfin_library_id`、`jellyfin_library_name`、`collection_type`（`movies` / `tvshows`）、`target_path`、`category`、`profile`（`standard` / `anime`）、`medium_auto_import`（預設 true）、`enabled`、`health_status`、`health_detail_json`、`created_at`
- `media`：`id`（`tv:<tmdb>` / `movie:<tmdb>`）、`tmdb_id`、`kind`、`title_en`、`title_original`、`year`、`folder_name`（凍結）、`tracked`、`default_route_id`、`tmdb_snapshot_json`（含各季各集：number、name、air_date、runtime；episode groups 的 absolute 排序若存在）、`tmdb_fetched_at`
- `tmdb_cache`：`key`、`value_json`、`fetched_at`（探索頁與搜尋結果的短期快取；Media 詳情走 `media` 表）

### 2.3 Job、檔案、計劃、帳本

- `jobs`：`hash`（pk）、`name`、`trigger`（`manual` / `rss` / `reimport`）、`trigger_ref`（rule id 或 import source 路徑）、`user_id`、`media_id`、`route_id`、`state`（§3.1）、`error`、`save_path`、`content_path`、`total_size`、`progress`、`client_state`、`added_at`、`completed_at`、`imported_at`、`last_seen_in_client_at`
- `job_files`：`id`、`job_hash`、`rel_path`（與 hash 合併 unique）、`size`、`priority`、`kind`（§4.1）、`release_info_json`、`mediainfo_json`、`updated_at`
- `plans`：`id`、`job_hash`（nullable）、`source_path`（重新入庫時的目錄）、`engine`（`rules` / `ai` / `user`）、`engine_version`、`status`（`preplan` / `auto` / `pending_review` / `approved` / `rejected` / `applied` / `failed`）、`summary_json`（各信心等級數量、原因摘要）、`created_at`、`decided_by`、`decided_at`
- `plan_items`：`id`、`plan_id`、`job_file_id`（nullable）、`rel_path`、`action`（`import` / `extra` / `subtitle` / `skip` / `unmatched` / `review`）、`media_id`、`season`、`episode_start`、`episode_end`、`tags_json`、`target_path`、`confidence`（`high` / `medium` / `low`）、`reasons_json`、`audit`（medium 自動入庫為 true）、`applied_at`、`error`
- `ledger`：`id`、`job_hash`（nullable）、`source_rel_path`、`source_abs_path`、`source_inode`、`source_dev`、`target_path`（unique）、`target_inode`、`media_id`、`season`、`episode_start`、`episode_end`、`tags_json`、`plan_item_id`、`jellyfin_item_id`、`link_mode`（`hardlink`）、`status`（`ok` / `target_missing` / `source_missing` / `inode_mismatch`）、`audit`、`created_at`、`checked_at`
- `events`：`id`、`job_hash`（nullable）、`media_id`（nullable）、`type`、`actor`（user id / `system` / `rss:<rule>` / `ai`）、`payload_json`、`created_at`。索引 `(job_hash, created_at)`。

### 2.4 RSS 與問題

- `rss_feeds`：`id`、`name`、`url`、`kind`（`mikan` / `nyaa` / `generic`）、`interval_sec`、`enabled`、`last_polled_at`、`last_error`
- `rss_rules`：`id`、`feed_id`（nullable = 所有 feed）、`media_id`、`route_id`、`include_regex`、`exclude_regex`、`groups_json`（白名單與優先序）、`resolution`、`subtitle_pref`、`season`、`episode_offset`、`policy`（`all_new` / `fill_missing`）、`enabled`、`created_at`
- `rss_items`：`id`、`feed_id`、`guid`（與 feed 合併 unique）、`title`、`link`、`torrent_url`、`info_hash`、`published_at`、`seen_at`、`release_info_json`、`matched_rule_id`、`job_hash`、`status`（`new` / `matched` / `downloaded` / `ignored` / `unmatched`）
- `issues`：`id`、`type`（brief §9.1 的七種）、`job_hash`、`ledger_id`、`path`、`detail_json`、`status`（`open` / `resolved` / `ignored`）、`detected_at`、`resolved_at`、`resolved_by`

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
| `requested` | qBittorrent 拒絕 / 不可達 | `submit_failed` | event；可手動重試回 `requested` |
| `submitted` | `torrents/files` 非空且 state 不是 `metaDL` | `metadata_ready` | 建 `job_files`、跑 pre-plan（`plans.status = preplan`）、event `metadata_received` + `preplan` |
| `metadata_ready` | 有進度 | `downloading` | event `progress`（每跨 25% 一筆） |
| `downloading` | `stalledDL` 超過 N 分鐘 | `stalled` | event；恢復進度即回 `downloading` |
| `downloading` / `stalled` | client state `missingFiles` / `error` | `missing_files` / `client_error` | issue |
| 任何活躍狀態 | torrent 從客戶端消失 | `client_removed` | issue `unknown_removed`；可 `reimport` 若 complete 檔案仍在 |
| `downloading` | 完成條件（brief §5.1） | `completed` | event `completed` |
| `completed` | planner_runner 取得 | `planning` | 讀 mediainfo、更新 `job_files` |
| `planning` | Plan 全 high/medium 且 Route 允許 | `importing` | `plans.status = auto`、event `plan_generated` |
| `planning` | 否則 | `review` | `plans.status = pending_review`、event `review_required` |
| `review` | 使用者核准 | `importing` | `plans.status = approved`、event `review_decided` |
| `review` | 使用者拒絕 | `completed` | 可重新 planning |
| `importing` | 全部 item 套用完 | `imported` | 通知 Jellyfin、event `linked` ×N、`jellyfin_scan_requested` |
| `importing` | 任一 item 失敗且不可跳過 | `import_failed` | event `link_failed`；重試回 `importing`，已完成的 item 跳過 |
| 任何狀態 | `delete_job` | `removed` | 依範圍刪除；event `deleted` |

- 轉換一律 compare-and-set：`UPDATE jobs SET state=:to WHERE hash=:h AND state=:from`，影響 0 列即放棄本次操作。
- 每個 job 在程序內另有 `asyncio.Lock`，避免 poller 與 importer 同時處理。

### 3.2 背景迴圈

| 迴圈 | 間隔 | 工作 |
| --- | --- | --- |
| `qbit_poller` | 有活躍 job 時 5s，否則 30s；連續失敗退避到 5 分鐘 | `sync/maindata`（帶 rid）；只看本系統 category 的 torrent；更新進度與 client state；驅動 §3.1 中由客戶端狀態觸發的轉換；發現無 job 的 torrent → issue `unknown_torrent` |
| `planner_runner` | 事件驅動（queue）+ 每 60s 掃 `completed` | 讀 mediainfo → 解析（§4）→ 建 Plan → 決定 auto / review |
| `importer` | 事件驅動 + 每 60s 掃 `importing` | 逐 item：建目錄 → `link()` → 寫 ledger → event；完成後 `POST /Library/Media/Updated`；一次只處理一個 job |
| `jellyfin_resolver` | 事件驅動，重試間隔 30s → 2m → 10m → 1h，共 6 次 | 為缺 `jellyfin_item_id` 的 ledger 找 item（brief §20.1 的兩段查詢）；耗盡即 issue `jellyfin_item_unresolved` |
| `reconciler` | 每日 04:00 + 手動 | brief §9.1 全部檢查，寫 `issues`（冪等：同 type + path 只有一筆 open） |
| `rss_poller` | 每個 feed 自己的 `interval_sec`，預設 15 分鐘 | 抓 feed → 解析 → 比對 rule → 去重 → `add_download` |
| `health_checker` | 每 5 分鐘 + 手動 | 服務連線、版本、Route 硬鏈接測試、磁碟空間、qBittorrent 必要設定 |

- 每個迴圈是一個 `asyncio.Task`，例外只記 log 不讓迴圈死掉；連續失敗次數與最後錯誤寫入 `settings.services.*` 供健康頁顯示。
- 迴圈之間用 in-process `asyncio.Queue` 傳「請處理 job X」的提示，DB 狀態才是真相；程序重啟後由定時掃描補上。

### 3.3 冪等與重入

- `add_download`：同 hash 已存在 → 回傳既有 job，不重複送單。
- importer：目標已存在且 inode 等於來源 → 視為已完成，補 ledger 若缺；目標存在但 inode 不同 → item 標 `error: target_exists_foreign`，進 review。
- ledger 的 `target_path` unique；event 寫入用 `(job_hash, type, payload hash)` 在同一分鐘內去重，避免重啟後重複「completed」事件。
- Jellyfin 通知失敗只記 event，不阻擋 `imported`；resolver 之後會再嘗試。

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
| `classify` | `[FileEntry]` → 加 `kind` | brief §6.2 的表；`sample` 以「檔名含 sample 且大小 < 同目錄最大影片 10%」判定；`extra` 以關鍵字（NCOP/NCED/OP/ED 無集號、PV、CM、Menu、Preview、Trailer、Making、特典、映像特典）與資料夾（`SPs/` 內非 SP 編號、`Extras/`、`Bonus/`）判定；mediainfo 可把時長 < 5 分鐘的「正片」降為 `extra` |
| `normalize_cjk` | 檔名 → 乾淨字串 + `CjkHints` | 從 AutoBangumi `classic.py` 與 Sonarr `Parser.cs` 移植：剝離 ★前綴、招募廣告、地區限制、【】括號正規化為 []、中文標題與英文標題並列時保留英文；抽出 `subs`（CHT/CHS/JP/EN 集合）、`hardsub`、`season_cn`（第N季/期）、`episode_cn`（第N話/集）、`collection`（合集/全集/全N話）、`special`（番外/特別篇/SP/OVA/OAD）、`movie`（劇場版/電影版）、`group_cn` |
| `parse_release` | 乾淨字串 → `ReleaseInfo` | guessit 打底；後處理動漫模式：`- 01`、`[01]`、`01v2`、`E01` 無季、`01-12` 區間、`S01 \| 01-28+SPx11`、`第01話`；`release_kind` 由集號區間與 `collection` 決定 |
| `structure_hints` | 相對路徑 → hints | 資料夾名 `Season 2` / `S2` / `第二季` / `2nd Season` / `Part 2` / `Specials` / `SPs`；`Subs/` `字幕/` 與其下的語言子資料夾 |
| `map_episode` | → `[Candidate]` | brief §6.4 的順序；絕對編號換算三法（episode group absolute、累計集數、air_date 虛擬季 offset）各自產 Candidate 並附理由；上下文 Media 缺時先做標題比對（正規化後與 `name` / `original_name` / alternative titles / translations 比對，年份加權） |
| `match_subtitle` | → 附掛 | brief §6.7 順序；語言由後綴（`.tc` `.cht` `.zh-Hant` `.sc` `.chs` `.jp` `.jpsc` `.jptc`）或資料夾決定，都缺時看 CjkHints |
| `plan` | → `Plan` | 為每個影片選最佳 Candidate；產生目標路徑（§5）；衝突與重複偵測（brief §6.4 第 5 點、§7.8）；extras 與 unmatched 的處置 |
| `score` | → confidence | brief §6.5 的三級定義；批次一致性檢查在此（同模式、連續集號、數量吻合） |

### 4.2 核心型別（`domain/`）

- `FileEntry`：`rel_path`、`size`、`kind`、`priority`
- `CjkHints`：`subs: set[Lang]`、`hardsub: bool | None`、`season: int | None`、`episode: int | None`、`episode_end`、`collection`、`special: str | None`、`movie: bool`、`group: str | None`
- `ReleaseInfo`：brief §6.3 欄位 + `raw_title`、`matched_tokens`
- `Tags`：`source`、`resolution`、`subs: tuple[Lang, ...]`、`hardsub`、`group`、`version`、`edition`；`render()` 依 brief §6.8
- `Candidate`：`season`、`episode_start`、`episode_end`、`strategy`、`confidence`、`reasons: list[str]`
- `PlanItem` / `Plan`：對應 §2.3

### 4.3 上下文與 TMDB 快照

`ParseContext`：`media: MediaSnapshot | None`、`profile`、`season_hint`、`episode_offset`、`route_collection_type`。`MediaSnapshot` 是 `media.tmdb_snapshot_json` 的型別化版本，含各季集數、每集 `air_date` 與 `name`、absolute 排序（若有）、標題集合。解析器不知道 TMDB API 的存在。

### 4.4 Offset 偵測

移植 AutoBangumi `offset_detector.py` 的想法：以季內各集 `air_date` 的間隔 > 180 天切出「虛擬季」，若檔名的季/集落在某個虛擬季內，換算為 TMDB 的實際季/集，Candidate 標 `strategy = air_date_offset`、confidence 至多 medium。RSS Rule 的 `episode_offset` 若有值則優先且信心可為 high。

### 4.5 AI fallback（M4）

介面在 M1 就定好：`AiPlanner.propose(context, files, rules_plan) -> Plan | None`，M1 的實作是 `NullAiPlanner`。輸入壓縮（同模式檔案只送樣本 + 數量）、schema 驗證、快取鍵、預算檢查都在 `services/plan.py`，與 provider 無關。

### 4.6 Benchmark【決定】

fixture 一筆一個 JSON：

```json
{
  "id": "anime/frieren-7acg-bd-batch",
  "source_url": "https://share.dmhy.org/topics/view/...",
  "torrent_name": "[7³ACG] 葬送的芙莉莲/Sousou no Frieren S01 | 01-28+SPx11 [简繁字幕] BDrip 1080p x265 OPUS 2.0",
  "files": [{ "path": "…/Sousou no Frieren - 01.mkv", "size": 1234567890 }],
  "context": { "media": "tv:209867", "profile": "anime", "season_hint": null, "episode_offset": null },
  "tmdb": "tv-209867",
  "expected": [
    { "path": "…/Sousou no Frieren - 01.mkv", "action": "import", "season": 1, "episode": 1,
      "tags": { "source": "BD", "resolution": "1080p", "subs": ["CHS", "CHT"], "group": "7³ACG" },
      "min_confidence": "high" }
  ]
}
```

- `tests/fixtures/tmdb/<id>.json` 是 TMDB 快照，錄一次即凍結。
- `berth bench` 輸出：整體與分類別（anime / tv / movie）的 `auto_correct`、`auto_wrong`（high 或 medium 自動入庫但錯，最嚴重）、`review`、`unmatched_correct`、`extra_correct`；分別列 high 與 medium 的錯誤率（brief §6.5）。
- CI 規則：`auto_wrong` 不得高於 `tests/fixtures/parser/baseline.json`，`auto_correct` 不得低於 baseline 減 1 筆；改善時更新 baseline 並在 PR 說明。
- v0 語料：20 筆，來源 brief §20.4 的樣本清單（動漫 8、美劇 / 韓劇 8、電影 4），逐步擴到 100+。

---

## 5. 命名引擎

`naming/` 是純函式，輸入 `MediaSnapshot`、`Tags`、季集、副檔名，輸出相對於 Route 目標路徑的相對路徑。模板固定在程式碼裡，第一階段不做使用者模板。

| 目標 | 模板 |
| --- | --- |
| 作品資料夾 | `{title} ({year}) [tmdbid-{id}]` |
| 季資料夾 | `Season {season:02d}` |
| 劇集檔 | `{title} ({year}) - S{s:02d}E{e:02d}[-E{e2:02d}][ - {episode_title}][ {tags}].{ext}` |
| 電影檔 | `{title} ({year}) [tmdbid-{id}][ - {tags}].{ext}`（無 tags 時檔名等於資料夾名） |
| 外掛字幕 | `{影片檔名主幹}.{SUBTOKEN}.{lang}[.default].{ext}` |
| Extras | `{作品資料夾}/extras/{原檔名}` |

- `title` 依 brief §7.5；`folder_name` 一旦寫進 `media` 就只從那裡讀。
- `episode_title` 來自快照；缺、空、或符合 `^Episode \d+$` 即省略；長度上限 80 字元。
- `sanitize`：移除 `/ \ : * ? " < > |` 與控制字元，連續空白合一，去尾端 `.` 與空白，整體 ≤ 200 bytes（UTF-8）。
- `Tags.render()`：brief §6.8 的順序與 token；缺欄位直接省略；`subs` 依 `CHS < CHT < JP < EN` 排序後以 `+` 連接。
- 這些模板在 M0 的實驗（brief §20.6）確認後才凍結；實驗若證明方括號有問題，只改 `naming/`，不影響其他模組。

---

## 6. API 面

REST + JSON，前綴 `/api`。所有端點需登入，除了 `auth/login`、`setup/*`（僅在 setup 未完成時開放）、`health`（可匿名，只回 ok / degraded）。Session 以 httpOnly cookie 承載，`SameSite=Strict`；非 GET 請求要求 `X-Requested-With` 標頭作 CSRF 防線。

| 群組 | 端點 | 對應命令 |
| --- | --- | --- |
| auth | `POST /auth/login`（Jellyfin 帳密）、`POST /auth/logout`、`GET /auth/me` | — |
| setup | `GET /setup/status`、`POST /setup/admin`、`POST /setup/detect`（回每個服務的來源：套件內 / 既有）、`POST /setup/jellyfin/bootstrap`、`POST /setup/jellyfin/install-mergeversions`、`POST /setup/jellyfin/add-library-path`、`GET /setup/qbittorrent/diff`、`POST /setup/qbittorrent/apply`、`POST /setup/indexer/apply`、`POST /setup/routes/from-libraries`、`POST /setup/complete` | `setup.*`（§9） |
| settings | `GET /settings/{group}`、`PUT /settings/{group}`、`POST /settings/{service}/test` | `settings.update`、`health.test_service` |
| routes | `GET/POST /routes`、`PUT/DELETE /routes/{id}`、`POST /routes/{id}/check`、`GET /jellyfin/libraries` | `routes.*` |
| discover | `GET /discover/trending`、`GET /discover/popular`、`GET /discover/search?q=` | `discover.*` |
| media | `GET /media/{id}`（TMDB + 狀態 + 檔案 + Unmatched + 版本）、`POST /media/{id}/track`、`POST /media/{id}/refresh` | `media.*` |
| search | `GET /search?media=&q=&route=`（索引站搜尋，結果附解析出的 Tags 與預估季集） | `search_torrents` |
| jobs | `POST /jobs`（`{source, media, route}`）、`GET /jobs`、`GET /jobs/{hash}`、`GET /jobs/{hash}/events`、`POST /jobs/{hash}/replan`、`POST /jobs/{hash}/reimport`、`POST /jobs/{hash}/retry`、`DELETE /jobs/{hash}?unlink=&remove_torrent=&delete_files=&purge=` | `add_download`、`generate_plan`、`reimport`、`delete_job` |
| plans | `GET /plans/{id}`、`PUT /plans/{id}/items`、`POST /plans/{id}/approve`、`POST /plans/{id}/reject` | `review.*`、`apply_plan` |
| review | `GET /review`（低信心、audit、Unmatched、重複、Issue 的統一佇列）、`POST /review/audit/{ledger_id}/confirm`、`POST /review/audit/{ledger_id}/undo` | `review.*` |
| files | `POST /files/rematch`（`{ledger_id \| job_file_id, action, season, episode_start, episode_end}`） | `rematch_file` |
| rss | `GET/POST /rss/feeds`、`PUT/DELETE /rss/feeds/{id}`、`POST /rss/feeds/{id}/poll`、`GET /rss/items`、`GET/POST /rss/rules`、`PUT/DELETE /rss/rules/{id}`、`POST /rss/rules/preview`、`POST /rss/oneshot` | `rss.*` |
| issues | `GET /issues`、`POST /issues/{id}/resolve`（`{action}`）、`POST /issues/{id}/ignore`、`POST /reconcile` | `reconcile`、`issues.resolve` |
| health | `GET /health`、`GET /health/detail` | `health.*` |
| events | `GET /events/stream`（SSE：job 狀態、進度、健康變化） | — |

- OpenAPI 由 FastAPI 產生；前端用 `openapi-typescript` 產型別，CI 檢查型別檔是否過期。
- 未來 MCP server 只需把 `services` 的命令包成 tool，schema 直接沿用 pydantic model。

---

## 7. 前端

- 路由：`/setup`、`/login`、`/`（探索）、`/media/:id`、`/library/:routeSlug`、`/jobs`、`/jobs/:hash`、`/review`、`/rss`、`/issues`、`/settings/*`。
- 資料：TanStack Query 管 API 快取；SSE 事件到達時使 job 相關 query 失效。
- 元件：shadcn/ui 為基礎；媒體卡片、狀態徽章、時間線、Plan 表格（逐列可改季集與動作）、檔案樹是專案自有元件。
- 文案：react-i18next，`zh-Hant` 為唯一語言檔；所有字串走 key，不硬編。
- 主題：深色為預設（媒體應用慣例），亮色跟隨系統。
- 每頁的核心任務與元素見 brief §13；設定精靈的步驟見 §9.3。

---

## 8. 外部整合細節

### 8.1 qBittorrent adapter

- 連線時讀 `app/webapiVersion` 與 `app/version`，低於 2.8.4 拒絕並提示升級。
- 參數依版本：API ≥ 2.11 用 `stopped`，否則 `paused`；`contentLayout=Original`；`autoTMM=true`；`category=<route.category>`；`tags=berth`。
- `ensure_category(name, save_path)`：`torrents/categories` 讀取（接受 `savePath` 與 `save_path` 兩種鍵），不存在才建，存在但 save path 不同 → 回報衝突不改（brief §20.2）。
- `diff_recommended_preferences()` / `apply_recommended_preferences()`：建議值為 `temp_path_enabled=true`、`temp_path=<incomplete root>`、`save_path=<complete root>`、`auto_tmm_enabled=true`、`category_changed_tmm_enabled=true`；先回傳與現值的差異給精靈顯示，套用時只寫不同的鍵。既有服務的 temp path 未啟用只列為警告。
- 完成判定與 `torrents/files` 路徑組合依 brief §20.2；`content_path` 是目錄或單檔，兩種都處理。
- 登入：`auth/login` 拿 SID，請求帶 `Referer` = base URL；403 記錄並退避。
- 錯誤映射：連線失敗 → `ServiceUnavailable`；403 → `AuthFailed`；409（category 不存在）→ `CategoryMissing`。

### 8.2 Jellyfin adapter

- 兩種憑證：使用者登入用 `Users/AuthenticateByName`（只在登入時），伺服器操作用 API key（`Auth/Keys` 建立，存 `settings.services.jellyfin`）。
- `list_libraries()`：`GET /Library/VirtualFolders` → `Name`、`ItemId`、`CollectionType`、`Locations`、`LibraryOptions.TypeOptions[].MetadataFetchers`（偵測 TVDB 插件並警告）。
- `notify_paths(paths)`：`POST /Library/Media/Updated`，每路徑 `UpdateType=Created`。
- `validate_path(path, is_file)`：`POST /Environment/ValidatePath`，跨服務可見性檢查用。
- `add_library_path(library_name, path)`：`POST /Library/VirtualFolders/Paths?refreshLibrary=false`，既有媒體庫加 Berth 路徑用；對應的移除 `DELETE /Library/VirtualFolders/Paths` 只在使用者明確要求時呼叫。
- `find_series(library_id, tmdb_id, folder_path)` 與 `find_episodes(series_id)`：brief §20.1 的兩段查詢，都帶 `fields=Path,ProviderIds`。
- `run_task(name)`：`GET /ScheduledTasks` 找名稱含 `Merge` 的任務 → `POST /ScheduledTasks/Running/{id}`；找不到只記 event。
- 初始化與插件安裝：§9.4。
- 絕不呼叫 `DELETE /Items/*`。

### 8.3 TMDB adapter

- 端點：`configuration`、`trending/{tv,movie}/week`、`{tv,movie}/popular`、`search/multi`、`tv/{id}`（`append_to_response=alternative_titles,translations,episode_groups,external_ids`）、`tv/{id}/season/{n}`、`tv/episode_group/{id}`、`movie/{id}`（`append_to_response=alternative_titles,translations,release_dates`）。
- 語言 `en-US` 取英文標題，`name` 空時退回 `original_name`；另以 `zh-TW` 取一次顯示用標題與簡介給 UI（brief §7.5 的檔名仍用英文）。
- 快取：探索與搜尋 1 小時；Media 快照 24 小時，Job 送單與 planning 前若快照超過 6 小時則刷新（新播集數會變）。
- 速率：全域 40 req/s 令牌桶，遠低於 TMDB 的上限。
- API key：內建專案級 key，`settings.services.tmdb.api_key` 有值則覆寫（§9 查證後定案）。

### 8.4 索引站 adapter

- 介面 `IndexerSearch.search(queries, categories) -> [SearchResult]`，兩個實作：
  - `ProwlarrSearch`：`GET /api/v1/search?query=&categories=&type=search`，回傳 `ReleaseResource`（`title`、`size`、`seeders`、`leechers`、`downloadUrl`、`magnetUrl`、`infoHash`、`indexer`、`categories`、`publishDate`、`guid`、`infoUrl`）。Prowlarr 刻意不提供跨站聚合 Torznab，所以走 REST（brief §20.7）。
  - `TorznabSearch`：任意 Torznab 端點（Jackett 的 `indexers/all/results/torznab/api` 或單站）：`?t=caps`、`?t=search&q=&cat=`、`?t=tvsearch&tmdbid=`、`?t=movie&tmdbid=`（依 caps 決定是否可用 id 搜尋）；解析 XML 的 `item` 與 `torznab:attr`（seeders、peers、size、infohash、magneturl、category）。
- 搜尋詞：Media 的英文標題、原文標題、各語言 alternative titles 各發一次，合併去重（以 infohash 或 link）；動漫 profile 另加 `第N季` / `Season N` 變體。
- 結果附 `parse_release` 的 Tags 與 `map_episode` 的預估（用來在結果表顯示「S01 全季」「E05」「無法判斷」）。
- `ProwlarrClient`（僅 setup 用）：§9.4。

### 8.5 RSS adapter

- `feedparser` 解析；每種來源一個小型 mapper 產 `FeedItem{guid, title, link, torrent_url, magnet, info_hash, size, published_at}`。
- Mikan：`enclosure` 為 `.torrent`，`link` 為集頁；Nyaa：`nyaa:` 命名空間欄位（實際欄位名以 M3 抓的 fixture 為準，brief §20.6）。
- 去重鍵：`(feed_id, guid)`；跨 feed 以 `info_hash` 去重（Mikan 的 torrent URL 可先下載解析 info hash，M3 決定是否做）。

### 8.6 fs adapter

- `link(src, dst)`、`stat`、`same_inode`、`link_test(dir_a, dir_b)`（建暫存檔、鏈接、比對、清理）、`free_space(path)`、`is_within(path, root)`（防路徑逃逸）。
- 所有寫入 library 的路徑必須在某個 Route 的 `target_path` 之下，否則拒絕；這是唯一會動 library 的模組。

### 8.7 mediainfo adapter

- `probe(path) -> MediaInfoSummary{duration_s, width, height, video_codec, bit_depth, audio_langs, subtitle_tracks[{lang, title, codec, forced, default}]}`。
- 只在 planning 階段對影片檔呼叫；失敗不阻擋，Plan 只少一個訊號。

---

## 9. 開箱即用

目標（brief §16.3）：`docker compose up` 之後只操作 Berth 就完成全部設定。事實依據見 brief §20.7。

### 9.1 套件內容（`deploy/`）

| 服務 | Image | 掛載 | 備註 |
| --- | --- | --- | --- |
| `berth` | `ghcr.io/<owner>/berth` | `${CONFIG_ROOT}/berth:/config`、`${DATA_ROOT}:/data`、`${CONFIG_ROOT}/prowlarr:/ext/prowlarr:ro` | port `8383`；`PUID` / `PGID` / `TZ`；唯讀掛 Prowlarr 設定以讀取其 API key |
| `qbittorrent` | `lscr.io/linuxserver/qbittorrent` | `${CONFIG_ROOT}/qbittorrent:/config`、`${DATA_ROOT}:/data`、`./preseed/qbittorrent:/custom-cont-init.d:ro` | port `8080`（WebUI）、`6881`（BT）；預置腳本見 §9.2 |
| `jellyfin` | `lscr.io/linuxserver/jellyfin` | `${CONFIG_ROOT}/jellyfin:/config`、`${DATA_ROOT}:/data` | port `8096` |
| `prowlarr` | `lscr.io/linuxserver/prowlarr` | `${CONFIG_ROOT}/prowlarr:/config` | port `9696` |

- 選 linuxserver 系列 image 的理由：四個容器都支援 `PUID` / `PGID` / `UMASK`，檔案擁有者一致；qBittorrent 官方 image 沒有這兩個變數（brief §20.7）。
- compose network `berth` 指定固定子網 `172.28.0.0/16`，讓 qBittorrent 的免密白名單可以寫死。
- `.env.example`：`DATA_ROOT`、`CONFIG_ROOT`、`PUID=1000`、`PGID=1000`、`UMASK=022`、`TZ=Asia/Taipei`、`COMPOSE_PROFILES=jellyfin,qbittorrent,prowlarr`。沒有任何秘密要填。
- `jellyfin`、`qbittorrent`、`prowlarr` 各掛在同名 profile 下，`berth` 永遠啟動；已有某服務的人把它從 `COMPOSE_PROFILES` 拿掉，精靈會改以既有服務表單接入（§9.3、§9.5）。
- Windows：`DATA_ROOT=C:\Berth\data` 這種路徑可直接寫在 `.env`，Docker Desktop 會以 9p/drvfs 掛進容器；實測 NTFS bind mount 的硬鏈接可用（brief §20.7）。exFAT 隨身碟不支援硬鏈接，README 明說。`PUID` / `PGID` 在 Windows 掛載上沒有意義，保留預設即可。
- 只有一份 `docker-compose.yml`，Linux 與 Windows 共用；`.env.example` 內附兩種路徑寫法的註解。
- `/data` 只是套件的預設路徑字串。Berth 不假設它：incomplete / complete 根目錄是設定值，媒體庫路徑讀自 Jellyfin；既有服務可以沿用它們原本的容器路徑（§9.5）。
- 目錄骨架由 Berth 啟動時建立：`<complete root>/..`、`<incomplete root>`、以及套件內 Jellyfin 的 `/data/library/{movies,tv,anime}`。

### 9.2 預置設定

預置的原則：**只放沒有它 Berth 就進不去的東西**，其餘一律由精靈按鈕經 API 完成、按前顯示差異、可重按。

**qBittorrent**（`preseed/qbittorrent/10-berth.sh`，linuxserver 的 `custom-cont-init.d` 機制，在服務啟動前執行）：若 `/config/qBittorrent/qBittorrent.conf` 不存在則寫入：

```ini
[Preferences]
WebUI\AuthSubnetWhitelistEnabled=true
WebUI\AuthSubnetWhitelist=172.28.0.0/16
WebUI\ServerDomains=qbittorrent
```

- 為什麼非預置不可：4.6.1 起首次啟動的隨機密碼只印在容器 log，Berth 沒有 docker socket 讀不到；要使用者去 `docker logs` 抄密碼正是要避免的事。白名單只讓 compose 內網免密，LAN 使用者開 8080 仍要密碼。
- `ServerDomains=qbittorrent` 讓 Berth 以容器名呼叫時通過 Host 檢查；T0.3 實測若仍被擋，改 `HostHeaderValidation=false` 並記錄。
- temp path、save path、autoTMM（`DisableAutoTMMByDefault` 預設 `true`，即關閉）、密碼都**不預置**，由精靈第 4 步的按鈕以 API 套用（§8.1）；Berth 送單時逐個 torrent 帶 `autoTMM=true`，所以全域預設值不影響正確性。
- 已有設定檔就不碰：使用者升級或重建容器時不會被覆寫；之後使用者在 qBittorrent 介面改任何東西都可以，健康檢查發現關鍵設定漂移時提供「還原建議設定」。

**Prowlarr**：不預置。Berth 從唯讀掛載的 `/ext/prowlarr/config.xml` 讀 `<ApiKey>`（Prowlarr 首次啟動自動產生）；讀不到時精靈退回手動貼上。也支援 `PROWLARR__AUTH__APIKEY` 環境變數的部署方式。

**Jellyfin**：不預置，全部走 API（§9.4）。

### 9.3 精靈流程

每一步都是冪等的 `services/setup.py` 命令，之後在設定頁可重跑。**來源是逐服務判斷的**（brief §16.3）：每個服務不是「套件內」就是「既有」，三個服務可任意組合。

1. **建立管理員**：帳號與密碼。套件內 Jellyfin 會以這組帳密建立管理員；既有 Jellyfin 則要求以其管理員帳密登入。勾選「同一組帳密也套用到 qBittorrent 與 Prowlarr 介面」（預設勾）則一併設定套件內的那兩者。
2. **偵測服務**：逐一探測 compose 主機名 `jellyfin:8096` `/System/Info/Public`、`qbittorrent:8080` `/api/v2/app/version`（免密）、`prowlarr:9696` `/ping`；Jellyfin 未完成初始精靈、qBittorrent 免密可進、Prowlarr 讀得到 API key 且無索引站 → 該服務標為**套件內**；探不到或已設定過 → 標為**既有**，顯示位址與憑證表單，每項有「測試連線」。服務未就緒時輪詢至多 2 分鐘。
3. **Jellyfin**：套件內 → §9.4 全自動；既有 → 登入、建立 API key、列出媒體庫與各自路徑，並提供「安裝 MergeVersions」按鈕（需確認，會重啟 Jellyfin）。
4. **qBittorrent**：顯示建議偏好與現值的差異（§8.1），按「套用」；套件內另設密碼；既有服務的 temp path 未啟用只警告。
5. **索引站**：套件內 → 勾選預設公開站清單（預設全勾）：Nyaa.si、dmhy、AniDex、Anime Tosho、ACG.RIP、Mikan、1337x、YTS、EZTV、The Pirate Bay；Berth 以 `indexer/schema` 取定義、`indexer` 新增、`indexer/test` 驗證。既有 → Prowlarr 位址 + API key，或任意 Torznab 端點 + key（Jackett）。
6. **TMDB**：內建專案 key，可覆寫；按「測試」。
7. **媒體庫與 Route**：套件內 Jellyfin → 自動由三個媒體庫建立三個 Route（`movies` / `tv` / `anime`，anime 用 `anime` profile）；既有 Jellyfin → 使用者勾選媒體庫，每個媒體庫可「加入 Berth 路徑」（§9.5）或在既有路徑中選寫入目標。每個 Route 立即建立 qBittorrent category 並跑硬鏈接與跨服務可見性測試。
8. **完成**：寫 `settings.setup.completed`，進健康頁；四項綠燈即可用。

### 9.4 Jellyfin 自動初始化序列

依 brief §20.7：`/Startup/*` 與 `/Library/VirtualFolders` 在精靈完成前不需憑證；插件與排程任務需要管理員 token。

1. `GET /System/Info/Public` → 確認 `StartupWizardCompleted == false`；否則視為既有服務（§9.5）。
2. `POST /Startup/Configuration` `{ UICulture: "zh-TW", MetadataCountryCode: "TW", PreferredMetadataLanguage: "zh-TW" }`（精靈可改）。
3. `POST /Startup/User` `{ Name, Password }` = Berth 管理員。
4. 建立目錄後 `POST /Library/VirtualFolders?name=Movies&collectionType=movies&paths=/data/library/movies&refreshLibrary=false`，body `LibraryOptions`：`PathInfos`、`PreferredMetadataLanguage`、`MetadataCountryCode`、`EnableRealtimeMonitor=false`（Berth 主動通知）、`SeasonZeroDisplayName="Specials"`。同樣建立 `TV`（`tvshows`、`/data/library/tv`）與 `Anime`（`tvshows`、`/data/library/anime`）。
5. `POST /Startup/RemoteAccess` `{ EnableRemoteAccess: true }`。
6. `POST /Startup/Complete`。
7. `POST /Users/AuthenticateByName` 取 token → `POST /Auth/Keys?app=Berth` 建 API key 存入 `settings.services.jellyfin`。
8. `GET /Repositories` 合併後 `POST /Repositories` 加入 `{ Name: "danieladov", Url: "https://raw.githubusercontent.com/danieladov/JellyfinPluginManifest/master/manifest.json", Enabled: true }` → `POST /Packages/Installed/Merge%20Versions?assemblyGuid=f21bbed8-3a97-4d8b-88b2-48aaa65427cb&repositoryUrl=…` → `POST /System/Restart` → 輪詢 `/System/Info/Public` 直到恢復。
9. `GET /ScheduledTasks` 找 `Key` 為 `MergeMoviesTask` 與 `MergeEpisodesTask` 的 `Id` 存起來，入庫後用 `POST /ScheduledTasks/Running/{Id}` 觸發。

### 9.5 既有服務的接入（brief §16.4）

**掛載規則**：Berth、qBittorrent、Jellyfin 把同一個宿主父目錄掛在相同的容器路徑，下載目錄與媒體庫目錄都在它底下。路徑字串隨使用者，例如 NAS 上三個容器都掛 `/volume1/media:/volume1/media`。Berth 的 incomplete / complete 根目錄在精靈第 4 步設為該父目錄下的子目錄。

**既有 Jellyfin**

- 不搬媒體庫：Jellyfin 的項目 ID 由路徑導出，改路徑等於觀看紀錄歸零。
- 「加入 Berth 路徑」按鈕：對選定媒體庫呼叫 `POST /Library/VirtualFolders/Paths?refreshLibrary=false`，body `{Name: <library>, Path: <parent>/library/<slug>, PathInfo: {Path: …}}`；Route 指向這個新路徑，舊路徑只讀（辨識已存在媒體與 unmanaged 檔案）。
- 使用者也可以不加路徑，直接在既有路徑中選一個當寫入目標；兩種都跑同樣的檢查。
- 「安裝 MergeVersions」按鈕：§9.4 第 8 步，需確認，因為會重啟 Jellyfin。
- 絕不自動建立媒體庫、安裝插件或改既有媒體庫的 `LibraryOptions`。

**既有 qBittorrent**

- 不搬舊種：Berth 只用自己建立的 `berth-*` category，忽略其他分類的 torrent；舊 torrent 留在原目錄。
- 使用者若原本只掛 `/downloads`，多加一個父目錄掛載即可；Berth 的 category save path 落在父目錄下。
- 全域 autoTMM 關閉無妨，送單時逐個 torrent `autoTMM=true`；temp path 未啟用只警告。
- 版本低於 4.4（API 2.8.4）拒絕接入並提示升級。

**檢查與訊息**（精靈第 7 步與 `health_checker` 共用）

1. 向 qBittorrent 讀全域 `save_path` 與每個 `berth-*` category 的路徑，逐一 `stat` 確認 Berth 看得到。
2. 向 Jellyfin 讀媒體庫路徑，逐一 `stat`。
3. 在 Route 目標寫探測檔，`POST /Environment/ValidatePath` `{Path, IsFile: true}` 請 Jellyfin 確認看得到同一路徑；再從 complete 根目錄對探測檔做 `link()`，確認同 device、同 inode。
4. 任一步失敗 → 健康頁指出「哪個容器少了哪個掛載」，附該容器的 compose `volumes:` 修正片段；`EXDEV` 另附「兩個目錄在 Berth 內是不同掛載」的說明。

**不支援**：Berth 與 qBittorrent 不在存放媒體的同一台機器；remote path mapping。

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
| 前端 | vitest、playwright | 元件與關鍵頁面；playwright 對 Fake 後端跑精靈與 M1 流程 |
| e2e | docker compose（GitHub Actions） | 真 qBittorrent + 真 Jellyfin + Berth：用本地產生的 .torrent 與檔案，以 `seedMode`（`skip_checking` 的替代）讓 torrent 立即完成，跑通 M1 驗收；驗證硬鏈接 inode 與 Jellyfin 反查 |
| 實驗 | `scripts/experiments/` | brief §20.6，一次性但保留腳本，結果寫回 brief |

- CI（GitHub Actions）：lint、type、unit + integration、benchmark 門檻、前端 build、image build；e2e 在 nightly 與 release 跑。
- 覆蓋率不設硬門檻，但 `parser/`、`naming/`、`services/` 的新程式碼必須有測試。

---

## 11. 里程碑任務

任務 ID `T<里程碑>.<序號>`，每個任務都有驗收。順序即建議開工順序，同一里程碑內標 ∥ 的可平行。

### 11.1 M0 骨架

| ID | 任務 | 驗收 |
| --- | --- | --- |
| T0.1 | Repo 骨架：uv 專案、ruff / mypy / pytest / import-linter、pnpm + Vite 專案、pre-commit、GitHub Actions（lint、test、build）、`.gitattributes`（LF）、LICENSE（MIT）、README 骨架、專案 `CLAUDE.md`、CHANGELOG | CI 綠燈；`uv run berth --version` 與 `pnpm build` 可跑 |
| T0.2 | 設定與 DB：`config.py`、SQLAlchemy models（§2 全部表）、Alembic 初始 migration、啟動自動 migrate、`settings` 的 pydantic 分組 | 空環境啟動後 `/config/berth.db` 建立且 schema 完整 |
| T0.3 ∥ | 實驗腳本（brief §20.6）：硬鏈接測試（Linux bind mount；Windows 已於 2026-09-07 實測通過，腳本化保留）、Jellyfin 命名實測（dummy 檔 + API 查詢結果）、qBittorrent 4.4 / 5.x 參數相容與 `ServerDomains` Host 檢查、Prowlarr host config API 設帳密 | 結果寫回 brief §20.6 與本文件 §5、§9；命名模板凍結 |
| T0.4 ∥ | adapters 第一版：jellyfin（public info、auth、api key、virtual folders、startup、repositories、packages、restart）、qbittorrent（login、version、preferences、categories）、prowlarr（indexer schema / add / test）、tmdb（configuration、search）、fs；每個附 Fake 與契約測試 | 契約測試綠燈；對真服務的手動 smoke 通過 |
| T0.5 | 認證：Jellyfin 登入 → session；角色由 Jellyfin `Policy.IsAdministrator` 決定；`auth/*` API；登入頁 | 非 admin 使用者無法進設定 |
| T0.6 | 設定精靈（§9.3）：`setup/*` API 與 UI；逐服務來源偵測；套件內服務全自動設定；既有服務表單與確認按鈕（安裝插件、加媒體庫路徑、套用偏好差異）；從媒體庫建 Route；Route 的硬鏈接與跨服務可見性檢查（§9.5） | 在乾淨的 Linux 與 Windows Docker Desktop 上，`docker compose up` 後只操作 Berth 即完成設定；「既有 Jellyfin + 套件內其餘服務」的組合也走通 |
| T0.7 ∥ | `deploy/`：Dockerfile（多階段：node build → python slim，非 root，`PUID/PGID` 入口腳本）、compose 範本（Linux 與 Windows 兩個 override）、preseed 檔、`.env.example`、image 發佈 workflow（GHCR） | `docker compose up` 四個服務健康；image 大小 < 400 MB |
| T0.8 | `health_checker` 迴圈與健康頁；服務設定頁（含「測試連線」「套用建議設定」按鈕） | 四項健康檢查綠燈；拔掉任一服務 5 分鐘內變紅並顯示原因 |

### 11.2 M1 手動全流程

| ID | 任務 | 驗收 |
| --- | --- | --- |
| T1.1 | TMDB：探索與搜尋 API、Media 詳情與快照、`tmdb_cache`、`media.track`、資料夾名凍結 | 探索頁可瀏覽趨勢與搜尋；Media 詳情顯示季集 |
| T1.2 ∥ | 索引站搜尋：Torznab client、多標題查詢合併、結果附 Tags 與預估季集、搜尋 API 與結果表 UI | 三種類型的作品都能搜到並正確顯示 Tags |
| T1.3 | `add_download`：qBittorrent 送單、job 建立、event；`jobs` API；下載列表頁 | 送單後 qBittorrent 出現正確 category 與 save path |
| T1.4 | `qbit_poller`：maindata 增量、狀態轉換、進度事件、SSE、未知 torrent issue | 從送單到完成的狀態在 UI 即時更新；重啟 Berth 不丟狀態 |
| T1.5 ∥ | 解析器（§4）與命名（§5）：全部階段、benchmark harness、`berth bench`、v0 語料 20 筆、baseline | benchmark 通過且 `auto_wrong = 0` |
| T1.6 | `planner_runner` + `importer` + `jellyfin_resolver`：pre-plan、planning、Plan 持久化、自動 / review 判定、硬鏈接、ledger、Jellyfin 通知與反查、MergeVersions 任務觸發 | 三種類型各一部不經人工入庫並在 Jellyfin 正確顯示 |
| T1.7 | UI：Media 詳情（搜尋 → 選 torrent → 選 Route → 送單；檔案與版本清單）、Job 詳情時間線、媒體庫頁（Route 分頁、卡片、狀態、深連結） | brief §17 M1 驗收 |
| T1.8 | e2e：compose 環境下的 M1 流程自動化（§10） | nightly 綠燈 |

### 11.3 M2 修正與對帳

範圍：Review Queue（Plan 逐列編輯、批次核准、audit 確認 / 撤銷）、Unmatched 指派、`rematch_file`、`reconciler` 與 issues 頁、刪除範圍（四旗標與空間估算）、`reimport`（以目錄為 Import Source）、`berth rebuild-ledger`。
驗收：刪掉 library 後一鍵重建；對「Jellyfin 內刪除」「complete 目錄手動刪檔」「用複製取代硬鏈接」三種破壞都能偵測並修復；medium 自動入庫的檔案可在佇列中一鍵撤銷。

### 11.4 M3 RSS

範圍：Mikan 與 Nyaa adapter（先抓 fixture 定欄位）、feeds / rules / items 資料流、`rss_poller`、去重、Rule 從 Media 頁建立並即時預覽、一次性 RSS 連結、未匹配 item 綁定 Media、offset 預填。
驗收：一個當季動漫分別以 Mikan 與 Nyaa feed 全自動追完，含 v2 取代與合集排除。

### 11.5 M4 AI fallback

範圍：`AiPlanner` 的 Anthropic 實作（provider 介面保留給其他家）、輸入壓縮、schema 驗證、快取、月預算、Event 記帳、RSS 未匹配 item 的 Media 建議、設定頁開關。
驗收：benchmark 上 low 信心案例的 review 比例下降，`auto_wrong` 不升；每次呼叫的 tokens 與費用可在 Job 時間線看到。

---

## 12. 風險與回寫點

| 風險 | 影響 | 對策 / 回寫 |
| --- | --- | --- |
| Jellyfin 對方括號 tag 或 ` - ` 分隔的解析不如文件（brief §20.1） | 命名模板 | T0.3 實測後凍結 §5；只改 `naming/` |
| Windows 使用者把 `DATA_ROOT` 指到 exFAT 隨身碟，或分開掛兩個目錄 | 硬鏈接失敗 | NTFS bind mount 已實測可用；健康檢查在精靈第 7 步就擋下並說明原因 |
| Jellyfin 首次啟動較慢，精靈第 3 步呼叫 `/Startup/*` 時服務尚未就緒 | 精靈失敗 | 精靈第 2 步輪詢至就緒（上限 2 分鐘）再前進；每步可重試 |
| 既有 Jellyfin 使用者把媒體庫搬到新路徑而不是加路徑 | 觀看紀錄歸零 | 精靈只提供「加入路徑」，文件明說不要搬；健康檢查不會建議改既有路徑 |
| 既有服務的容器路徑各不相同（`/downloads`、`/tv`、`/movies` 分開掛） | 硬鏈接 `EXDEV` | 檢查訊息附 compose 修正片段；README 用 NAS 範例說明「加一個父目錄掛載」 |
| TMDB 與字幕組的動漫季編號不一致 | medium 誤入庫 | benchmark 分開報告 medium 錯誤率；offset 偵測；M3 的 Rule offset；後續接 anime-lists |
| MergeVersions 任務名或行為變動 | 多版本顯示 | 觸發失敗只記 event；README 說明手動觸發 |
| Mikan / Nyaa feed 欄位與假設不同 | M3 | 先抓 fixture 再寫 adapter |
| qBittorrent 版本差異（`paused` / `stopped`、`save_path` 鍵名） | 送單失敗 | 契約測試涵蓋 4.4 與 5.x |
| medium 自動入庫錯誤率偏高 | 使用者信任 | 收緊 medium 定義（brief §6.5），不關自動入庫 |
| 單程序內背景迴圈互相拖慢 | 延遲 | 迴圈各自 try/except 與退避；必要時拆第二程序 |
