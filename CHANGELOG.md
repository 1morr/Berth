# Changelog

本專案所有重要的變更都記在這個檔案。

格式依循 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)，版本號依循 [Semantic Versioning](https://semver.org/lang/zh-TW/)。

## [Unreleased]

**M0（骨架）在 2026-09-08 通過驗收**（brief §17、`.scratch/m0/issues/11-m0-acceptance.md`）：在乾淨的
Windows Docker Desktop（NTFS bind mount）與 Linux（ext4）上各跑一次 `docker compose up` → 只操作 Berth
→ 四項健康檢查綠燈，全程沒有打開 qBittorrent / Jellyfin / Prowlarr 的介面；另以「既有 Jellyfin +
套件內 qBittorrent 與 Prowlarr」的組合走一次，既有媒體庫是**加**一條路徑而不是搬路徑，項目 ID 與
觀看紀錄都沒有變。M0 建的東西全部列在下面，M1 之後的變更接在同一份清單後面；還沒有發佈過正式版本。

### Added

- Repo 骨架：uv 後端專案與 `berth` CLI（`--version`）、pnpm + Vite + React + TypeScript 前端。
- 工具鏈：ruff、mypy（strict）、pytest、import-linter、eslint、prettier、vitest。
- `import-linter` 契約，編碼 plan §1.3 的依賴方向。
- pre-commit 設定與 GitHub Actions CI（後端 lint / type / test、前端 lint / test / build、檔案衛生）。
- LICENSE（MIT）與 README（指令的單一來源）。
- `berth serve`：FastAPI 程序，啟動時自動套用 Alembic migration 並以 WAL 開啟 `<CONFIG_ROOT>/berth.db`。
- M0 資料表：`users`、`sessions`、`settings`、`routes`、`events`（plan §2）。
- `settings` 的分組模型：`services.jellyfin`、`services.qbittorrent`、`services.indexer`、
  `services.tmdb`、`paths`、`setup`，未設定時回預設值。
- `GET /api/health`：匿名可呼叫，回總體狀態、版本與精靈是否已完成。
- 前端 shell：深色為預設、亮色跟隨系統的 Tailwind 主題，`zh-Hant` 語言檔，
  TanStack Router 與 Query，以及顯示健康狀態的佔位頁；build 產物由後端同一個程序提供。
- 環境變數 `CONFIG_ROOT`、`DATA_ROOT`、`WEB_ROOT`、`PORT` 與 `.env.example`。
- `deploy/`：多階段 Dockerfile（node build → python slim、非 root、`PUID` / `PGID` 入口腳本）、
  四個服務的 `docker-compose.yml`（profiles、固定子網、健康檢查）、qBittorrent 的
  preseed 腳本與部署用的 `.env.example`。
- GHCR 發佈 workflow（`v*` tag）與 CI 的 image build job。
- `scripts/experiments/`：對真實外部服務的可重跑驗證腳本（Jellyfin 10.10 / 10.11 命名、
  qBittorrent 4.4 / 5.x 參數矩陣、Prowlarr `config/host`、硬鏈接），只用標準庫，
  可搬到 NAS 上跑；結果寫在 `docs/research/m0-experiments.md`。
- 設定精靈的前兩步（plan §9.3）：`GET /api/setup/status`、`POST /api/setup/admin`、
  `POST /api/setup/detect`、`POST /api/setup/services/{kind}`。setup 未完成時匿名開放，
  完成後只有 `admin` 進得來。
- Jellyfin、qBittorrent、Prowlarr 三個 adapter 的第一版：各有 `Protocol` 介面、HTTP 實作與
  `Fake`，錯誤分成「服務不在 compose 裡」「還在啟動」「要憑證」「不是這個服務」四種；
  契約測試對 `tests/fixtures/http/` 的錄製回應執行。
- Prowlarr 的 API key 從唯讀掛載的 `config.xml` 或 `PROWLARR__AUTH__APIKEY` 讀取，
  兩處都沒有時精靈退回手動貼上。新增環境變數 `EXT_ROOT`。
- 設定精靈第 7–8 步（plan §9.3）：`GET/POST /api/setup/routes` 從 Jellyfin 媒體庫建立 Library Route，
  每條 Route 在 qBittorrent 建 `berth-*` category（已存在但 save path 不同時回報衝突且不覆寫）並跑
  五項跨服務檢查——qBittorrent 與 Jellyfin 回報的路徑在 Berth 內 `stat` 得到、Jellyfin 看得到 Berth
  寫的探測檔（`Environment/ValidatePath`）、complete 目錄與寫入目標之間真的 `link()` 得起來且同
  inode。`POST /api/setup/complete` 在每條 Route 都綠燈時寫下 `settings.setup.completed`，之後
  `setup/*` 需登入、`/` 不再導向精靈。
- fs adapter（plan §8.6）：`link`、`stat`、`same_inode`、`link_test`、`free_space`、`is_within`
  與探測檔；所有寫入都要帶允許的根目錄，不在其中就拒絕（防路徑逃逸）。
- 設定精靈 UI（`/setup`）：常駐的四格泊位板、第 1 步建立管理員、第 2 步逐服務探測與
  就地展開的既有服務連線表單與可複製的手動步驟。setup 未完成時其他頁面導向 `/setup`。
- 認證（plan §6、brief §11）：`POST /api/auth/login`（以 Jellyfin 帳密驗證，角色取自
  `Policy.IsAdministrator`）、`POST /api/auth/logout`、`GET /api/auth/me`。session 以
  httpOnly、`SameSite=Strict` 的 cookie 承載，壽命 30 天不續期，資料庫只存 token 的雜湊。
- `/api` 的門禁 middleware：預設拒絕，白名單只有 `auth/login`、`auth/logout`、`health`；
  非 GET 請求要求 `X-Requested-With` 標頭。精靈跑完之後 `setup/*` 只有 `admin` 進得來。
- 登入頁 `/login`，以及登入後頁首的身分區（角色、設定入口、登出）。未登入時任何頁面
  導向 `/login`，非 admin 看不到也進不了設定。
- UI 語言 `zh-Hant` 與 `en` 並列，跟隨瀏覽器並可切換，選擇存在 localStorage。
- `scripts/fake_setup_server.py`：以 Fake adapter 起一台真的 Berth，用來實跑驗證精靈。
- 設定精靈第 3 步 Jellyfin（plan §9.4、§9.5）：`GET /api/setup/jellyfin`、
  `POST /api/setup/jellyfin/bootstrap`、`/connect`、`/libraries/paths`、`/plugin`。
  套件內一鍵跑完九步（建管理員、Movies / TV / Anime 三個媒體庫、API key、安裝 MergeVersions、
  重啟並記下兩個合併任務的 `Id`），每一步冪等、失敗可單獨重試；既有服務只做檢查，
  提供「加入 Berth 路徑」與「安裝 MergeVersions」兩顆需二次確認的按鈕。
- `settings.services.jellyfin` 新增 `api_key`、`metadata_fetchers`（建立媒體庫時的 metadata
  provider，預設 TMDB，是 brief §10 的 TVDB【研究】的切換點）、`merge_movies_task_id`、
  `merge_episodes_task_id`；`settings.paths` 新增 `library_root`。
- Jellyfin adapter 補上初始精靈、媒體庫、API key、插件、排程任務；`Fake` 是有狀態的假伺服器，
  複製了實測到的行為（同名媒體庫不被拒、`Auth/Keys` 不去重、重啟後回 503）。
- `adapters/fs.py`：媒體庫目錄由 Berth 建立（plan §9.1）。
- 設定精靈第 4 步 qBittorrent（plan §9.3、§8.1）：`GET /api/setup/qbittorrent/diff` 現查逐鍵差異
  （`temp_path_enabled`、`temp_path`、`save_path`、`auto_tmm_enabled`、`category_changed_tmm_enabled`），
  `POST /api/setup/qbittorrent/apply` 只寫有差異的鍵；勾了「同一組帳密」時另設套件內的 WebUI 密碼。
  Web API 低於 2.8.4 拒絕接入並給升級指令；既有服務的 temp path 未啟用只警告。
- 設定精靈第 5–6 步來源（plan §9.3、§8.3、§8.4）：`GET /api/setup/indexers`、
  `POST /api/setup/indexers/apply`（十個預設公開站，逐站顯示成敗，重按不會重複新增）、
  `/connect`（既有 Prowlarr 或任意 Torznab 端點）、`/skip`，以及 `GET /api/setup/tmdb`、
  `POST /api/setup/tmdb/test`、`/skip`。勾了「同一組帳密」時一併設定套件內 Prowlarr 的介面登入。
- qBittorrent adapter 補上偏好讀寫與分類，版本判斷（`paused` / `stopped`、2.8.4 下限）綁在
  4.4.5 與 5.2.3 兩組錄製回應上；Prowlarr adapter 補上索引站定義、新增、驗證與 `config/host`。
- 新增 TMDB 與 Torznab 兩個 adapter（各有 `Protocol`、HTTP 實作、`Fake` 與契約測試）。
  TMDB 內建專案級憑證，`settings.services.tmdb.api_key` 可覆寫，v3 key 與 v4 token 都收。
- 套件內 Prowlarr 的 API key 在探測時就存進 `settings.services.indexer`，之後的步驟與里程碑
  從同一個地方拿憑證。
- `health_checker` 背景迴圈（plan §3.2）：由 lifespan 啟動與關閉，每 30 秒醒來、上一輪滿 5 分鐘
  才真的跑，精靈跑完之前不跑。四項檢查——Jellyfin（連線與 API key）、qBittorrent（連線、Web API
  版本、建議設定漂移）、索引站（Prowlarr 或 Torznab）、每條 Route 的五項跨服務檢查（與精靈第 7 步
  同一組、寫回同一個欄位）。每一項各自 try/except，一個服務掛掉不影響其他檢查。
- `GET /api/health/detail`（要登入）與 `POST /api/health/check`（立刻重跑）：逐服務與逐 Route 的
  明細、最後成功時間、連續失敗次數與失敗原文。`GET /api/health` 的 `status` 改成由上一輪的結果
  導出（`ok` / `degraded`），只讀一列設定，不連任何服務。
- `settings` 新增 `health` 分組：迴圈上一輪的逐服務結果與 Route 總結。與 `services.*`
  分開存——那幾組是整組覆寫的使用者設定。
- 服務設定 API（plan §6，只有 `admin`）：`GET /api/settings/services`、
  `POST /api/settings/services/{kind}/test`（只重測一個服務）、`GET /api/settings/qbittorrent/diff`、
  `POST /api/settings/qbittorrent/apply`（「還原建議設定」，brief §16.3）。
- 健康頁 `/health`（唯讀，一般使用者也看得到）與服務設定頁 `/settings/services`（只有 admin）：
  與精靈同一塊四格泊位板，紅燈就地展開服務回的原文與修正步驟（套件內給 docker 指令，既有指回
  精靈），Route 綠燈收起、紅燈展開五條纜繩；qBittorrent 設定漂移顯示逐鍵差異與還原按鈕。
  頁首長出導覽，`/` 在 M1 的探索頁之前先導向 `/health`。

- `berth openapi`：印出 OpenAPI 文件（`--output` 寫檔）。只組裝路由，不跑 lifespan、不碰資料庫。
- `pnpm -C web gen:api`：從上一條產出前端的 API 型別 `web/src/api/schema.d.ts`（openapi-typescript）。
  CI 多一個 `api-types` job，型別檔過期時紅燈。

- M1 資料表：`media`（Berth 手上的作品，資料夾名一凍結就進了檔案系統）與 `tmdb_cache`（探索與搜尋的
  一小時快取，整列丟掉不會失去任何東西）。
- TMDB adapter 補上 `trending/{tv,movie}/week`、`{tv,movie}/popular` 與 `search/multi`，以及
  **全域 40 req/s 的令牌桶**——上限是每個 IP 的，所以桶是程序層級的一個，不是每個 client 一個。
- `GET /api/discover/trending`、`/api/discover/popular`、`/api/discover/search?q=`：回作品卡片
  （tmdb id、類型、顯示用標題、英文標題、年份、完整海報網址）。**拿不到 TMDB 時仍是
  200**，理由放在 `problem`——一頁上有三個 feed，一個垮掉時另外兩個要照樣畫得出來。
- 探索頁 `/`：趨勢與熱門兩面海報牆（劇集與電影交錯）、鍵入即搜的搜尋（500 ms 防抖、2 字起跳、
  結果接管整面牆），以及 TMDB 條款要求的歸屬聲明與標誌。**卡片上還沒有狀態**——「已追蹤 /
  部分 / 完整 / 下載中」要等 Job 與帳本才推導得出來。
- `scripts/fake_setup_server.py` 新增 `discover` 與 `tmdb-down` 兩個情境；前者打**真的** TMDB
  （憑證由環境變數 `TMDB_API_KEY` 帶入，與實驗腳本同一個名字；根目錄的 `.env.example` 有欄位）。
  **Berth 本身不讀那個變數**——產品的唯一來源仍是精靈寫進資料庫的 `settings.services.tmdb.api_key`。
- TMDB adapter 再補上詳情那四支：`tv/{id}`、`movie/{id}`（各自帶它需要的 append）、
  `tv/{id}/season/{n}` 與 `tv/episode_group/{id}`。**絕對編號從 0-based 的 `order` 推**，
  不是 group 裡的 `episode_number`——後者保留播出序原值，照它讀會把第二季算成第 1 集起。
- `GET /api/media/{id}`、`POST /api/media/{id}/refresh`：TMDB 詳情與各季各集的快照
  （24 小時，過期自動重抓），以及收得下這部作品的 Route 清單。**拿不到 TMDB 時仍是 200**，
  存過的快照照樣回，只是掛一條「這是舊的」。
- Media 詳情頁 `/media/:id`：海報與三個標題（顯示用、英文、原文）、識別欄位、簡介、各季可展開的
  集表（集號、標題、絕對編號、片長、播出日），以及「入庫到哪裡」的 Route 下拉。**電影沒有季集
  區塊**，改列片長。搜尋 torrent 與送單在 M1 後段接上去之前，這一頁是唯讀的瀏覽頁。
- 探索牆的每一格現在是連到詳情頁的連結（票 03 刻意留下的那條線）。
- `domain/media.py` 的 `MediaSnapshot` / `SeasonSnapshot` / `EpisodeSnapshot`：`media.tmdb_snapshot_json`
  的型別化版本，也是 `naming` 與（M1 後段的）`parser` 的輸入。
- `naming.folder_name()`：plan §5 凍結模板的第一格——`{title} ({year}) [tmdbid-{id}]`。
- 解析器的前三層（plan §4.1、brief §6.2、§6.3、§6.8）：
  - `parser.classify`：依副檔名、關鍵字與資料夾判 `kind`。`sample` 要**同時**滿足「檔名含
    sample」與「遠小於正片」；`disc` 是整包的判定（有 `BDMV/` 或 `VIDEO_TS/` 就整包需人工）。
  - `parser.normalize_cjk`：中文字幕組命名的詞典。抽出字幕語言、內嵌 / 內封 / 外掛、季號、
    集號、合集、特典、劇場版與組名，並剝掉 `★` 前綴、招募廣告、地區限制與 CJK 標題，
    剩下的拉丁字母那一半才交給 guessit。**季號認全形羅馬數字（`无职转生Ⅲ`）與不以空白收邊的
    半形羅馬數字（`Mushoku Tensei III:`）**——M1 票 01 量到漏掉這兩種會把整輪播出錯置成第一季。
  - `parser.parse_release` / `merge_release`：guessit 打底，補上它在字幕組格式下會漏或會錯的
    幾條（多方括號裡的集號、`Season 3 [04]` 被讀成兩個季號、年份被當成季號、`HD1080P`、
    結尾 `-[Group]`、把字幕 token 當組名）。檔名說了算，torrent 名補空缺。
  - `domain.Tags.render()`：brief §6.8 的順序與 token，`subs` 依 `CHS < CHT < JP < EN` 以 `+` 連接。
- `berth bench`：解析基準測試（plan §4.6、brief §6.9）。**離線跑**——真實 torrent 的
  檔案清單（`tests/fixtures/parser/`）與凍結的 TMDB 快照（`tests/fixtures/tmdb/`）都在
  repo 裡。報表逐分類列出 `auto_correct` / `auto_wrong` / `review` / `missed` /
  `unmatched_correct` / `extra_correct` / `skipped`（七個桶加起來等於檔案數）、分類與 tag
  的正確率，以及 high / medium 誤判率；門檻在
  `tests/fixtures/parser/baseline.json`，同一支邏輯就是 `tests/unit/test_bench.py`，所以 CI
  不另開 job。
- 解析器的第四層：季集對應與信心（plan §4.1、§4.4、brief §6.4、§6.5、§6.6）。
  - `parser.structure_hints`：只讀資料夾——`Season 2` / `S2` / `第二季` / `2nd Season` /
    `Part 2` / `Specials` / `SPs`，以及 `Subs/` `字幕/` 與其下的語言子資料夾。
  - `parser.map_episode`：brief §6.4 的優先序（上下文季號 → 檔名的顯式季號 → 資料夾 → 篇章名
    → 只有集號），每一個答案都是一個帶理由的 `Candidate`。**三條規則來自 M1 票 01 的量測**：
    **篇章名 → 季號**（佔失敗的九成；比對各季在三輪語言下的名字，`最終季` 對到最後一季）、
    **`第二部分` / `Part.2` 當 cour 偏移**（唯一「有季號還是錯」的一類），以及 **180 天的虛擬季
    門檻**（TMDB 把好幾輪播出併成一季時的換算）。絕對編號三法（episode group、各季累加、
    虛擬季）各產一個 Candidate。
  - `parser.match_media`：正規化後比 `name` / `original_name` / 別名 / 翻譯，年份加權。上下文
    有 Media 時它是覆核（對不上就壓低信心）；`ParseContext.candidates` 有東西時（RSS 與
    重新入庫）它就是認作品的那條路，而「標題 + 年份精確命中」才配得上 high 信心。
  - `parser.score`：批次一致性（同模式、連續集號、數量與 TMDB 吻合）。兩個檔案宣稱同一集、
    或一季十二集卻對出二十個檔案時，**那一季都不自動入庫**——是哪一個讀錯了看不出來；
    整包用同一種模式讀而只有一個例外時，那一個降到 medium。
  - 特典的處置（brief §7.6）：發佈明說 `S00Exx` 就照它走但信心至多 medium，只寫 `[SP][01]`
    這種自己的序號則是 `unmatched`，等人工指派。
- `MediaSnapshot` 的各季多一個 `names`：同一季在 `en-US` / `zh-TW` / `zh-CN` 三輪的名字。
  篇章名比對的對手是真實發佈寫的那一種字（`柱训练篇`），只留英文季名的話那條規則不會命中。
  代價是 `tv/{id}` 多打一輪 `zh-CN`（只取季名，電影不打）。
- 語料補三筆真實發佈（動漫 11 / 劇集 8 / 電影 4，共 23 筆 333 個檔案）：篇章名（鬼滅之刃
  柱訓練篇）、cour 偏移（進擊的巨人 Season 3 Part 2）與單檔多集（`- 01-02` 的 `.ts`）。
- `berth bench` 的報表多一欄**信心達標率**：語料寫的 `min_confidence` 有沒有達到。不達標不是
  做錯事，但它說得出「本來該自動入庫的少了幾個」。
- `scripts/record_tmdb_snapshots.py`：用產品自己的路徑（暫時的資料庫 + `refresh_media`）錄
  `tests/fixtures/tmdb/`，語料加了新作品時跑。
- `import-linter` 契約「parser and naming do no IO」：`berth.parser` 與 `berth.naming` 不得
  import `os` / `pathlib` / `httpx` / `sqlalchemy` 這一類會做 IO 的模組——benchmark 能離線跑
  靠的就是這條。
- **命名引擎**（`berth/naming/`，plan §5）：作品資料夾、季資料夾、劇集檔、電影檔、外掛字幕、
  extras 六種凍結模板，輸出相對於 Route 目標的路徑。集名來自快照（缺、空、或 `Episode 5`
  這種佔位就省略，上限 80 字元）；`sanitize` 逐段套用，檔名的 200 位元組上限先扣掉副檔名。
- **外掛字幕附掛**（`berth/parser/subtitles.py`，brief §6.7）：主幹相同（去掉語言後綴）或
  字幕資料夾裡的集號 → 那個影片；語言由字幕自己的後綴、資料夾、檔名決定。檔名走
  `{影片主幹}.{CHT|CHS}.zh.{ext}`，日文與英文只用 `ja` / `en`——`zh-Hant` 只有 Jellyfin 10.11
  認得（brief §20.6 實測）。
- **Plan 產出目標路徑**：`PlanItem.target_path`，只有真的會被寫出去的檔案有值。
  兩個檔案指到同一條路徑就是衝突，兩個都進 review（brief §6.4 第 5 點）。
- `berth bench` 的比對**含目標路徑**，報表多一個 `subtitle_correct` 桶（八個桶），
  baseline 多守 `extra_correct` 與 `subtitle_correct` 兩格。
- **索引站搜尋**（`berth/adapters/indexer/`、`berth/services/search.py`，plan §6、§8.4）：
  `IndexerSearch` 介面加兩個實作——`ProwlarrSearch`（REST `/api/v1/search`，Prowlarr 刻意不提供
  跨站聚合 Torznab）與 `TorznabSearch`（任意 Torznab 端點，`t=caps` 決定能不能用 tmdbid 搜，
  不支援時退回 `q=`）。介面**一次一個查詢**；多標題展開、併發、合併去重與逐查詢逾時在 services。
- `GET /api/search?media=&q=&route=`：結果附解析出的 Tags 與預估季集。`route` 是**這一輪搜尋的
  偏好，不是承諾**（票 04b）——它只決定 anime profile 要不要加 `第N季` / `Season N` 變體。
- `GET /api/search/queries?media=&route=`：按下搜尋之前先給看會拿哪幾個名字去問（PRODUCT 原則 2）。
  不打索引站，只讀快照，所以改 Route 時可以隨手重問；規則只有一份實作，前端不重算。
- **Media 詳情頁的搜尋區塊與結果表**（`.scratch/m1/search-results-shape.md`）：待命 → 按了才搜
  （一次搜尋實測 35–85 秒），逐條纜繩顯示每個關鍵字問到幾筆，五欄結果表（發佈名 + Tags / 大小 /
  做種 / 來源 / 預估），可依做種與大小排序，390px 上塌成堆疊列。Route 下拉從身分帶搬進這一區塊
  ——它現在真的驅動一件事。
- `--scenario search`：TMDB 與索引站都打真的那一台的演練情境。
- **送單**（`berth/services/jobs.py`、`berth/api/jobs.py`，plan §3.1、§3.3、§6 jobs 群組）：
  `POST /api/jobs`（`{source, media, route}`）建一筆 Job（`requested`）→ qBittorrent 收下
  → `submitted`，兩個轉換各寫一筆 event。同 hash 重複送單回傳既有 Job，不重複送單。
  qBittorrent 拒絕或不可達 → `submit_failed` 加服務回的原文，`POST /api/jobs/{hash}/retry`
  可以退回 `requested` 再送一次。
- `jobs` 與 `job_files` 兩張表與 migration（plan §2.3）。**主鍵是 info hash**，所以
  「同一個 torrent 送兩次」在資料庫層就是同一列。`job_files` 這一票只建表。
- `GET /api/jobs`、`GET /api/jobs/{hash}`、`GET /api/jobs/{hash}/events`。
- **送單前 Berth 自己把 torrent 抓下來**（`berth/adapters/torrent.py`）：索引站的下載連結 →
  info hash（磁力連結就地解析，`.torrent` 逐位元組取 `info` 再 SHA-1）+ 要交給 qBittorrent 的
  那一份。兩個理由——`jobs.hash` 是主鍵而索引站不一定報 hash（實測 ACG.RIP 不報），以及交一條
  網址給 `torrents/add` 是**背景抓取**，抓失敗永遠沒有下文（`202` + `pending_count`），
  那樣 `submit_failed` 這個狀態永遠觸發不到。
- `torrents/add`（`berth/adapters/qbittorrent/`）：`category` + `tags=berth` +
  `contentLayout=Original` + `autoTMM=true` + 版本對的那個開始參數（API ≥ 2.11 是 `stopped`，
  否則 `paused`，值都是 `false`）。`savepath` 不送——`autoTMM` 開著時路徑由 category 決定。
- **`media.folder_frozen`**：資料夾名在**第一次送單成功那一刻**定死（plan §2.2、brief §4.5、
  票 04b）。送單確認裡印著那一串字，按下去之前就看得到；已經凍結過的第二次送單不重凍。
  `media.default_route_id` 同時寫成「上次用的」，下一次進詳情頁時下拉停在它。
- **Tracked Media 以 `EXISTS(jobs)` 推導**（`berth/services/tracking.py`、`CONTEXT.md`、票 04b）：
  詳情頁與探索牆的卡片讀同一份推導，不是欄位。票 12 的帳本與 M3 的 Rule 之後加進同一支函式。
- **下載列表頁 `/jobs`**（`.scratch/m1/jobs-shape.md`）：一份船期表，逐列狀態色塊 + 作品 +
  Route + trigger + 大小 + 進度 + 時間；點一列**就地展開**時間線、info hash 與重試，
  其他列不動、不跳頁（The Failure Expands In Place Rule）。最新的在前面。
- **結構化日誌**（`berth/logs.py`，brief §16.2、plan T1.9）：一行一筆 JSON，job 上下文裡的
  每一行都帶 job id。id 由 `ContextVar` 帶著、在 record 建立那一刻蓋上，不靠呼叫端記得傳。
- `--scenario submit` / `--scenario submit-failing`：送單與下載列表的演練情境。
- **`qbit_poller`**（`berth/pipeline/downloads.py`、`berth/services/downloads.py`、plan §3.1、§3.2、
  票 10）：`sync/maindata` 帶 `rid` 做增量，驅動 plan §3.1 中由客戶端狀態觸發的每一個轉換
  （`metadata_ready`、`downloading`、`stalled`、`missing_files`、`client_error`、`client_removed`、
  `completed`）。轉換一律 compare-and-set，每個 job 另有程序內的 `asyncio.Lock`。間隔有活躍 job 時
  5 秒、否則 30 秒、連續失敗退避到 5 分鐘，而且**每次醒來重算**——送單那一刻多半落在一個閒置間隔
  中間，沿用上一輪的答案會讓使用者等最多半分鐘才看到第一個變化。
- **`GET /api/events/stream`（SSE）**（`berth/api/events.py`、`berth/services/events.py`、plan §6）：
  推 `{hash, state, progress}`，前端據此讓 `['jobs']` 失效再問一次。下載列表因此**不用重整就自己動**
  ——沒有「即時」指示器、沒有輪詢（`.scratch/m1/live-jobs-shape.md`，使用者拍板）。
- **`job_files`**：`metadata_ready` 那一刻由 `torrents/files` 建起來，`rel_path` 是它回的 `name` 原樣
  （相對 `save_path`、含 torrent 自己的根目錄那一層，brief §20.7 再驗一次）。
- **時間線多五種事件**（brief §5.2）：`metadata_received`（檔案數與總大小）、`progress`（**每跨 25%
  一筆**，不是每一輪一筆）、`stalled`、`completed`、`issue_detected`（`IssueType` 四種）。
- **健康頁的「下載迴圈」區塊**：上次輪詢、輪詢間隔、連續失敗與服務回的原文，以及**無主 torrent**
  的清單（qBittorrent 上掛著 Berth 記號、Berth 卻沒有 Job 的那些）。`issues` 表在 M2，所以 M1 的
  載體是一筆 `issue_detected` 事件加這一份「現在還在不在」的清單。
- **`IpBannedError`**（plan §8.1、brief §20.2、解掉 plan T1.9 的第四條）：qBittorrent 連續 5 次登入
  失敗會封住來源 IP 並回 `403`，而帳密不對在 4.4.5 是 `200` + `Fails.`、5.2.3 是 `401`——所以登入
  端點上的 403 只有「被封了」一個意思。兩種都有可行動的訊息：一個要去改設定，一個要等封鎖過期。
- `--scenario poll`：qBittorrent 打**真的**那一台，送單到完成的狀態自己走完（見 README）。
- `sse-starlette` 相依。
- **`planner_runner`**（`berth/pipeline/planning.py`、`berth/services/plan.py`、plan §3.1、§3.2、
  票 11）：下載完成之後**沒有人在場**的那一段——讀 mediainfo → 解析（plan §4）→ 建 Import Plan →
  照信心決定自動入庫還是停下來問人。事件驅動（poller 動了什麼就叫醒它）加每 60 秒掃一次
  `completed` 與 `planning`；例外只記 log，迴圈不死。
- **`plans` 與 `plan_items` 兩張表**（plan §2.3）：一個 Job **一份「現在的計劃」**（`job_hash`
  unique），重跑改寫同一列而不是再長一份——不然 `GET /api/plans/{id}` 要先回答「哪一個 id 才是
  現在那一份」。上一份留在時間線上。
- **pre-plan**（brief §5.1）：檔案清單一到手就先算一份預估（`plans.status = preplan`），不碰網路、
  不碰磁碟、不動 Job 的狀態。它回答的是「這一包對不對、還來得及取消嗎」。
- **mediainfo adapter**（`berth/adapters/mediainfo.py`、plan §8.7）：`probe(path)` 回時長、寬高、
  codec、bit depth、音軌語言與逐條內封字幕軌。**失敗不阻擋**（讀不到、讀不懂、函式庫自己爆掉都回
  `None`），Plan 只少一個訊號。`pymediainfo` 相依（wheel 內含 libmediainfo，不需系統套件）。
- **時長 < 5 分鐘的「正片」降為 extra**（`berth/parser/classify.py`、brief §6.2）：檔名像第一集而
  mediainfo 說它 88 秒時，檔名輸。**沒量到不是量到 0**：pre-plan 那一輪一個訊號都沒有，
  而那時候每個檔案都還在下載。
- **`GET /api/plans/{id}`** 與 **`POST /api/jobs/{hash}/replan`**（plan §6）：一份 Plan 的逐檔決定、
  信心與理由；重跑限 `completed` / `planning` / `review`——`importing` 的那一份已經被採信，
  而 importer 正照著它動檔案（票 12）。
- **下載列表的展開區多一塊「匯入計劃」**（`web/src/jobs/JobPlan.tsx`）：一個檔案一列（包含略過的
  那些），逐列說得出處置、信心、季集、**它會被寫到哪一條路徑**與理由。停下來時說得出三種理由
  中的哪一種與下一步。M1 唯讀——逐列編輯與核准是 M2 的 Review Queue。
- **時間線多三種事件**（brief §5.2）：`preplan`、`plan_generated`、`review_required`。
- `--scenario plan`：下載完成 → Import Plan 的演練情境（見 README）。
- `pymediainfo` 相依。
- `AiPlanner` 介面與 `NullAiPlanner`（`berth/adapters/ai.py`，plan §4.5、brief §6.10）：
  `propose(context, files, rules_plan) -> Plan | None`。M4 才有實作，介面先定是因為它約束的是
  規則層——AI 只能提出規則層表達得出來的處置，碰不到檔案。
- **`importer`**（`berth/pipeline/importing.py`、`berth/services/importer.py`、plan §3.1、§3.2、§3.3、
  票 12）：Import Plan 真的落到媒體庫——逐檔建目錄 → 硬鏈接 → 寫帳本 → 事件，**一個檔案 commit
  一次**。目標已經存在時比 inode：同一個就是「上次做到了」，補上帳本；不同就是別人的檔案，整筆
  停在 review 而且不覆寫它。正片鏈接不成是 `import_failed`（重試從沒做完的接著做），字幕與特典
  鏈接不成只記在那一列上。全部落地之後才通知 Jellyfin（`POST /Library/Media/Updated`），失敗
  只記事件、不擋 `imported`。planner 算完就叫醒它，另外每 60 秒掃一次 `importing`。
- **`ledger` 表**（plan §2.3）：一條「來源檔案 → 目標硬鏈接」一列，`target_path` unique。它自己
  站得住——`job_hash` 是弱引用、處置與季集抄一份進來（重新規劃會換掉 plan items）；inode 與
  device 存 TEXT（Windows 的 `st_dev` 超過 SQLite 的有號 64 位元）。
- **`jellyfin_resolver`**（`berth/pipeline/resolving.py`、`berth/services/resolver.py`）：入庫的
  正片在 Jellyfin 裡是哪一個 item。每筆帳本自己的排程 30 秒 → 2 分 → 10 分 → 1 小時 ×3，共 6 次，
  存在帳本上所以重啟不會忘；兩段查詢都以媒體庫為 parent（brief §20.1），也比 `MediaSources` 的
  路徑（第二個版本不是 item 自己的 `Path`）。找到之後觸發 MergeVersions；耗盡寫一筆
  `issue_detected(jellyfin_item_unresolved)`。沒找到兩次以上改跑 Jellyfin 的「重新掃描媒體庫」排程
  任務——**路徑通知對從沒掃到過內容的媒體庫無效**（Jellyfin 12.0.0 實測，brief §20.1），而套件內的
  媒體庫一開始一定是空的。
- Jellyfin adapter 多三支：`notify_paths`、`items`、`run_task`（plan §8.2）。
- **時間線多六種事件**（brief §5.2）：`linked`、`link_failed`（帶 `errno` 與原文）、
  `jellyfin_scan_requested`、`jellyfin_item_resolved`、`merge_versions_requested`、
  `jellyfin_request_failed`；停下來的理由多一種 `target_exists`，需要處理的事多一種
  `jellyfin_item_unresolved`。
- 下載列表上入庫失敗的那一筆有一顆「再試一次入庫」（與「重新送單」同一個端點，回到的是另一站；
  不叫「重新入庫」——那是 M2 的 Reimport）。鏈接失敗只有擋住入庫時才是紅字。
- **媒體庫頁 `/library/:routeSlug`**（票 13、`.scratch/m1/library-shape.md`）：依 Route 分頁的卡片牆，
  牆上是這條 Route 上有 Job 的作品加上檔案落在它底下的。一格說得出狀態（失敗 → 待審 → 下載中 →
  已入庫 / 部分 / 沒有檔案，依序取第一個成立的；只有需要人的那幾格塗漆）、`N / M 集入庫`（分母是
  已播出的正片，S00 不算），以及 Jellyfin 找到了沒——找到了是一條深連結，還沒找到說原因、不給死
  連結。「待審」「Unmatched」兩個篩選在網址上。卡片本體連到 Media 詳情，Jellyfin 那一行是並排的
  另一條連結。`GET /api/inventory`、`GET /api/inventory/{slug}`；頁首多一項「媒體庫」。
- Media 詳情的第 4 塊「檔案與版本」：帳本裡每一個檔案的季集、Tags、目標路徑、帳本狀態與 Jellyfin
  反查狀態（還在掃描時說下一次什麼時候查），對不到的檔案，以及多版本並存（電影是 Tags，劇集是
  整個檔名主幹，brief §7.7）。集表多一欄「入庫」：已入庫 · 卡住 · 下載中 · 缺 · 未播出。
- **Jellyfin 對外網址**（`settings.services.jellyfin.public_url`，在服務設定頁改；
  `GET|POST /api/settings/jellyfin`）：選填，沒填時推導——既有服務用它自己的位址，套件內用瀏覽器
  的主機名加 `base_url` 的 port（Seerr 的 `externalHostname` 慣例）。深連結的形狀是
  `{對外網址}/web/#/details?id=…`，不帶 `serverId`（Jellyfin 12.0.0 實測不需要）。
- 帳本多一欄 `jellyfin_series_id`：resolver 反查到一集時連同它所屬的 Series 寫下，深連結開到作品
  而不是某一集。
- 演練情境 `inventory`（`scripts/fake_setup_server.py`）：替身 Jellyfin 會「掃到」入庫的檔案，媒體庫
  的卡片看得到從「還在掃描」換成「在 Jellyfin 開啟」。
- **Route 設定頁 `/settings/routes`**（票 14、`.scratch/m1/route-settings-shape.md`，只有 admin）：與服務設定頁
  共用一條子分頁列。每條 Route 一列，綠燈收起、紅燈或停用就地展開；展開區改名稱、profile、啟用，
  重新檢查五條纜繩，以及刪除（二次確認）。**同一個 Jellyfin 媒體庫可以建第二條 Route**（brief §4.3）：
  清單下方的「新增 Route」按下去才向 Jellyfin 現查媒體庫與路徑，已經有 Route 的路徑選不了。新建或
  重新啟用時檢查紅燈就維持停用；被下載或入庫檔案指著的 Route 不給刪除鍵，說出原因與出路（停用）。
  `GET|POST /api/routes`、`PUT|DELETE /api/routes/{id}`、`POST /api/routes/{id}/check`、
  `GET /api/jellyfin/libraries`。健康頁的 Route 區塊對 admin 多一條「到 Route 設定」。
- 演練情境 `routes`（`scripts/fake_setup_server.py`）：TV 媒體庫在 Jellyfin 上多掛一顆碟、Movies 多一條
  沒掛進來的路徑、TV 那條 Route 有一筆下載——第二條 Route、紅燈建立與「刪不得」三種樣子都看得到。
- 語料補五筆「只有集號、TMDB 上多季」的真實發佈（票 14c；動漫 14 / 劇集 10 / 電影 4，共 28 筆 368 個
  檔案）：SPY×FAMILY 第二季合集、我的英雄學院 139、航海王 1089–1104、Home and Away 第 8214 集、
  超人回來了 E079。絕對編號換算那一支第一次有語料走到；baseline 的 `auto_correct` 140 → 169，
  `auto_wrong` 仍是 0。
- `scripts/experiments/profile_effect.py`（票 14c）：Route profile 對語料有沒有作用——四種組合重算、
  逐檔比桶、側錄 `_from_number` 的分支。結論在 `docs/research/profile-effect.md`：使用者拍板移除
  profile（票 14d、14e）。
- 語料補兩筆（票 14d；動漫 16 / 劇集 10 / 電影 4，共 30 筆 383 個檔案）：Erai-raws《死神 千年血戰篇 相剋譚》
  01–14（每 cour 重數，正解 S02E27–40；改解析器之前是 `auto_wrong` 14）與 SubsPlease `Spy x Family - 05`
  （第一季的無季號發佈，正解 S01E05）。baseline 的 `auto_correct` 169 → 170，`auto_wrong` 仍是 0。
- `scripts/experiments/absolute_rule_cost.py`（票 14d）：用 M1 票 01 以發佈時間判定正解的 Mikan 發佈，量「集號
  ≤ 第一季集數就送審核」擋下的對與錯，以及「標題有認不出的多餘字」能不能分開兩者（結論：分不開，研究 §6.1.1）。
  `anime_episode_source.py` 的 `Trial` 為此多帶 Mikan 的原始標題。

### Changed

- **只支援 Jellyfin 12 以上**（票 14b、brief §19、§20.9）。12.0 起同一集的多個版本由 Jellyfin
  自己合併成一個條目，10.x 需要的 MergeVersions 插件在它上面是空跑，還會跨媒體庫誤併——所以
  **插件整段移除**：精靈第 3 步從九步變七步（沒有「裝插件」與「重啟」）、既有服務少了「安裝
  MergeVersions」按鈕與那支 `POST /api/setup/jellyfin/plugin`、resolver 不再觸發合併任務、
  adapter 的介面上不再有 `/Repositories`、`/Packages`、`/Plugins` 與 `/System/Restart`。
  設定裡的 `merge_movies_task_id` / `merge_episodes_task_id` 與 `setup.jellyfin.merge_versions_installed`
  一併拿掉；舊資料庫存的那幾個鍵照樣讀得回來（`extra="ignore"`），不需要 migration。
- **低於 Jellyfin 12.0 就紅燈**：精靈第 3 步（套件內與既有都是）與健康檢查讀 `/System/Info/Public`
  的 `Version`，不足就停下，說出目前版本、為什麼要 12，以及升級前後要做的事（先完整備份、
  移除第三方插件、升級後完整掃描、降不回去）。`GET /api/setup/jellyfin` 多 `version` 與
  `version_supported` 兩個欄位。
- **精靈第 3 步的重試在 12.x 走得完**：`POST /Startup/User` 在第一個使用者已有密碼時回 403，
  現在當成「已經設過了」繼續往下（密碼對不對由之後的登入驗證）。原本會翻成 `AuthFailedError`，
  讓「第 4 步失敗後重試」永遠卡在第 3 步。
- **劇集的版本名改讀 Jellyfin 回的 `MediaSources[].Name`**，不再自己重算（12.0 起它是「去掉各版本
  檔名的共同前綴」剩下的部分，算法連 12.0 與 12.1 都不一樣）。反查到的那一刻抄進帳本
  （`ledger.jellyfin_version_name`，migration `3f6c0a7d94e2`）；Jellyfin 還沒收錄的版本顯示檔名的
  tags 並說明那不是版本名。
- **多集檔與同起始集的單集送審核**（brief §7.8）：同一份 Plan 裡、或與同一部作品同一季的帳本
  Entry 之間，起始集相同而結束集不同的正片一律停下等人，理由說出「Jellyfin 12 只用季號與集號
  分組，會把它們併成一集、後面那一集從集列表上消失」。
- `deploy/docker-compose.yml` 的 Jellyfin 從 `:latest` 釘到 `lscr.io/linuxserver/jellyfin:version-12.1ubu2604`。
- 演練情境：`installed` 與 `failing` 換成 `old-jellyfin`（既有 Jellyfin 停在 10.11 的樣子）。
- **精靈第 7 步略過寫入目標已經被佔用的選擇**（票 14a）：佔用者可以是既有的 Route，也可以是同一批
  前面的選擇；不回 422。沒有 `ItemId` 的舊 Route 在媒體庫改名之後，重跑不再長出同一個目標的第二條。
- **精靈跑完之後重跑第 7 步新建的 Route 先停用，檢查綠了才啟用**（票 14a）。原本是先啟用、檢查紅了
  再停掉，檢查跑完之前的那幾秒裡送單選得到還沒驗過的 Route。
- `GET /api/jellyfin/libraries` 的 `locations` 與 `taken` 合成 `paths[{path, route_name}]`：已經有 Route 的
  路徑帶著 Route 名，新增 Route 的表單不再拿清單反查。`DELETE /api/routes/{id}` 的 409 `route_in_use`
  另帶 `jobs` 與 `ledger_entries`，畫面照著說數字。建立時同一時間撞上唯一索引回 409 `route_conflict`。
- Route 設定頁：被引用而且還啟用著的 Route 旁邊有一顆「停用這條 Route」（送的是存下來的名稱與
  profile），刪除、停用、重新檢查之後都有 `aria-live` 播報；新增時媒體庫沒有空路徑，給一條到 Jellyfin
  媒體庫設定的連結。頁首的「設定」連到新的 `/settings`（導向服務設定），兩個設定頁上都標成當前頁。
- **精靈第 7 步只新增、不改不刪**（票 14）：重跑不再隱式刪掉沒勾的 Route，也不再改寫已經有 Route
  的媒體庫；那些媒體庫在勾選表上鎖住，重跑的意思是「補上新勾的、全部重驗」。每條 Route 底下有
  明確的刪除（被引用時拒絕）。
- **停用的 Route 不算進健康總結與精靈第 7 步的完成條件**（票 14）：停用是「刪不得」時的出路，
  它紅著不再讓整台 Berth 顯示 degraded。
- `/api/routes` 與 `/api/jellyfin/libraries` 跟著 `/api/setup` 的門禁規則：精靈跑完之前匿名開放，之後只有 admin。
- **Route 檢查與精靈認 Jellyfin 媒體庫改用 `ItemId`**（票 14）：在 Jellyfin 改了名字或有兩個同名的媒體庫時，
  Route 不再驗到別的媒體庫。精靈跑完之後重跑第 7 步新建的 Route 紅燈就維持停用；電影媒體庫的 Route 不收
  anime profile。精靈的 `GET /api/setup/routes` 裡 `libraries[].selected` 改名 `has_route`。
- **事件一分鐘內不重複**（`record_event`、plan §3.3、票 12）：`(job_hash, type, payload)` 相同就跳過，使用者按下的重試是界線。
  迴圈的一輪可能在寫完事件之後、下一步落地之前被關掉，重啟後的第一輪會把同一件事再做一次。
- **`POST /api/jobs/{hash}/retry` 也收 `import_failed`**（回 `importing`），`retried` 事件的
  `state` 分得出是哪一種重試。
- **fs adapter 的 `link()` 會建好目標那幾層資料夾**（守衛之後才建），`EXDEV` 另外說出來源與目標
  各自落在哪一個掛載上（仍是同一個 `errno` 的 `OSError`，plan §8.6）。
- **`/api` 底下的每一個回應都帶 `Cache-Control: no-store`**（`berth/api/gate.py`、plan §6、票 10）。
  這不是最佳化：Berth 原本一個快取 header 都不送，於是瀏覽器對 `200` 套用它自己的啟發式快取——
  實跑抓到 SSE 推來「這一筆完成了」之後前端重問一次，拿回來的卻是幾秒前那份說「已送出」的快取，
  畫面因此永遠停在錯的狀態。這裡的每一支回的都是「現在的狀態」，沒有一支的答案在下一秒還算數。
- **`torrents/add` 的成功形狀依版本判定**（brief §20.2、§20.7、plan §8.1）：2026-09-10 對真的
  qBittorrent 5.2.3 與 4.4.5 各錄一輪，發現 5.2.3 成功回的是一份 JSON 摘要而不是 `Ok.`——
  brief 原本記的「一律回 200 `Ok.`」只對 4.4.x 成立，只認 `Ok.` 的話 5.x 上每一次成功的送單
  都會被判成失敗。`409` / `415` / `202` 的意義一併記進 brief §20.7 與 fixture。
- **`/` 不再導向 `/health`**，它就是探索頁（plan §7）。登入之後落到的第一個畫面因此從「看它有沒有
  壞」變成「找東西」；健康頁留在導覽列上。
- 依實測更正 TMDB 的三件事（brief §20.3、plan §8.3）：`language` 會換掉 `trending` 回的**成員與
  順序**而不只是文字（兩輪 20 筆差 3 筆），所以清單以 `en-US` 那一輪為準、`zh-TW` 只當查表；
  回應裡的 `popularity` **不是**清單的排序依據，所以兩種作品合成一面牆時用交錯而不是重排；
  `{tv,movie}/popular` 的每一筆沒有 `media_type`。
- `settings.services.tmdb` 新增 `image_base_url`，精靈第 6 步驗憑證時順手寫下——`configuration`
  對同一把憑證是常數，每次探索都問一次是白花一個請求。
- **`naming` 移到 `parser` 之下**（plan §1.3 的依賴圖與 import-linter 契約）：`plan` 階段要
  產出目標路徑，而衝突偵測比的就是那條路徑。反向不成立，另有一條契約守著。
- **「兩個檔案同一集」不再一律進 review**：同一集不同 tags 的檔案本來就該並存（brief §7.7），
  简繁分軌與 1080p / 720p 同包都是常態。衝突改比**目標路徑**——那正是「會不會蓋掉對方」的定義。
- **標題自己帶著同一個年份時不再接一次**：TMDB 上真的有 `GTO (2026)` 這種標題，照字面套模板
  會寫成 `GTO (2026) (2026)`。年份不同的兩個數字說的是兩件事，照樣兩個都留。
- **作品資料夾名在第一次送單成功那一刻凍結**（plan §5、brief §4.5）：那是它第一次真的通向磁碟，
  而且有人在場確認。在那之前它跟著 TMDB 的標題走，畫面上是「將會是」的預覽；凍結之後 TMDB
  改標題也不動它——已入庫的檔案不該因為別人改了條目就對不上。**「追蹤」不是一個按鈕**，它是
  「Berth 曾為這部作品下載、訂閱或入庫過」的推導結果（`CONTEXT.md`）。
- `DiscoverProblem` 更名為 `TmdbProblem` 並新增 `not_found`：探索頁與 Media 詳情頁問的是同一台
  服務、四種理由的下一步也一樣，各寫一份遲早會走樣。訊息塊因此收成共用的 `TmdbNotice`。
- TMDB 詳情的 `append_to_response` 拿掉 `external_ids` 與 `release_dates`：快照裡沒有欄位讀它們，
  而後者每部電影是一百多筆各國上映日（實測 138 筆）。plan §8.3 已同步。
- 依實測更正文件：brief §7.2（電影檔名必須含 `[tmdbid-<id>]` 才算多版本）、§7.7（劇集的版本
  標籤是整個檔名而非 tags）、§20.1；plan §5 的命名模板**凍結**，§8.1、§8.2、§9.2、§9.4 依
  實測修正。細節見 `docs/research/m0-experiments.md` 與 `docs/progress.md` 的「偏差與決定」。
- 視覺系統重寫成「泊位調度板」（`.impeccable/surfaces/` 的 direction contract）：四個信號色
  各只有一個意思、狀態三重編碼、無圓角無漸層。票 02 的七個佔位色彩 token 被取代。
- `settings.setup` 不再存「走到第幾步」的游標，步驟由狀態導出。
- 精靈第 2 步要**每個服務都連得上**才算做完（判定多一個 `resolved` 旗標）。原本只看「有沒有
  結論」，會讓從 `COMPOSE_PROFILES` 拿掉的服務一有結論就跳過那張唯一能填位址的表單。
- HTTP adapter 新增 `ServiceBusyError`（503）：Jellyfin 重啟後「還在載入」與「壞了」要分得開。
- `/api/settings/*` 只有 `admin` 進得來，規則與 `setup/*` 一樣放在門禁 middleware。
- 前端共用件從 `setup/` 移到 `components/`（纜繩、狀態對照、Route 檢查的文案與 compose 片段），
  跨頁共用的 API 型別移到 `api/schemas.ts`（後端對應 `api/schemas.py`）——精靈、健康頁與設定頁
  講的是同一批東西。
- 前端 eslint 開啟 `@typescript-eslint/no-floating-promises` 與 `no-misused-promises`（需要型別資訊）。
  這是票 01 把型別感知規則延後時寫下的理由——TanStack Query 進來之後忘了 `await` 才變成真風險。
  只開這兩條而不是整包 `recommendedTypeChecked`：整包在這個 repo 上抓到的 36 條全是框架慣用法
  （TanStack Router 的 `throw redirect(...)`）與測試裡的型別噪音，沒有一條是真的缺陷。
- 英文的精靈階段字串從 `Berth {{code}}` 改成 `{{code}}`——`code` 本身就是 `BTH 1`，原本讀起來是 `BERTH BTH 1`。中文維持「泊位 BTH 1」：`泊位` 與 `BTH` 不同字集，而且它替第一次看到這個代號的人解釋了它是什麼。
- `routes.tsx` 的「精靈沒跑完就去跑、跑完了就要有 session」收斂成 `requireSignedInPage`
  （票 07 留的「頁面變多時再收」）。精靈那一頁仍然自己寫——它在同一個條件下是留下來而不是導走。

- 前端不再手寫任何 API 的形狀：`web/src/api/*.ts` 只把後端的類別名（`RouteOut`）換成前端在講的
  名字（`RouteView`），欄位與可選性全部來自產出的型別。M0 票 10 記的「同一份形狀寫了四層」的第四層
  就此消失。換過來的第一天就抓到一個漂移：`ServiceDetection` 少了後端已經在回的 `configured`。

- **Berth 不再內建 TMDB 的專案級憑證，改由使用者自備**（推翻上面 M0 那一條，也削掉 brief §16
  「開箱即用」的一角）。不替所有使用者背一把共用憑證；而兩個 metadata provider 在「使用者自己
  申請一把」上本來就對稱（brief §10、§20.7）。憑證的唯一來源是 `settings.services.tmdb.api_key`，
  精靈第 6 步從「可跳過的覆寫」變成**必填的閘門**：`POST /api/setup/tmdb/skip` 移除，測不過就
  停在第 6 步，`POST /api/setup/complete` 在沒有一把綠燈憑證時回 422。v3 key 與 v4 read access
  token 兩種形狀仍然都收。取得步驟寫在 README 的〈先申請一把 TMDB API key〉。
- `scripts/experiments/anime_episode_source.py` 的 TMDB 憑證改從環境變數 `TMDB_API_KEY` 讀
  （原本是從 adapter 原始碼刮那把內建的）。
- **只有集號、TMDB 上不只一季時，絕對編號換算的信心改看證據，不再看 Route 的 profile**（票 14d，brief §6.4）：
  預設 medium（自動入庫），集號沒超過第一季的集數、或檔名的播出日與換算出的那一集在 TMDB 上的播出日不同，
  就降到 low 送審核並說出是哪一條。所以 `anime` Route 上第一季的無季號發佈（`Spy x Family - 05`）改送審核，
  `standard` Route 上的跨季連號與播出日對得上的（`The.Return.of.Superman.E079.150524`）改自動入庫。
  Route 上的 profile 欄位還在，解析器已經不讀它（票 14e 拿掉）。
- 發佈名解析多讀檔名裡的播出日（`ReleaseInfo.air_date`）；六位數的短日期年份在前，韓國電視台的 `150524`
  讀成 2015-05-24，而不是 guessit 預設的 2024-05-15。

### Fixed

- **刪除 Route 與送單的競態**（票 14a）：刪除先算引用數再刪，兩步之間另一個請求送的單會先落地，
  接著被刪除設成 `route_id = NULL`。現在算引用數與刪除在同一把 SQLite 寫鎖裡，那一筆等到刪除 commit
  之後撞上外鍵，送單回 422 `route_missing` 而不是 500（`add_download` 的 `try` 往前擴到 flush）。
- **兩個分頁同時新增 Route 回 500**（票 14a）：兩邊都看到目標沒人佔、算出同一個 slug，後到的撞上唯一
  索引。建立改在寫鎖內重讀再寫，後到的那一個回 `target_taken`；修改與重新檢查途中 Route 被刪掉回 404
  `route_missing`。
- `/api/routes/{id}` 的刪除只算那一條的引用數（帳本以前綴粗篩、`owning_route` 精判），不再整張帳本讀進來。
- 前端測試的 fetch 替身遇到 204 會自己丟 TypeError，票 14 的刪除成功測試因此從來沒走到成功分支。
- **`[01-13Fin]` 被讀成「第 1 集」**（`berth/parser/release.py`）：`Fin` / `END` 黏在集號後面是中文
  字幕組的季末寫法，而方括號的集號規則不認得它們，於是一整類季包的預估季集是錯的。`完` / `完結`
  沒事——`normalize_cjk` 已經把它們吃掉了。票 08 在真的索引站回應裡抓到，`berth bench` 的
  `auto_wrong` 仍是 0。

- **英文的「{{count}} titles」在只有一筆時說「1 titles」**（探索頁的搜尋計數）。i18next 傳 `count`
  時查的是 `_one` / `_other`，兩個都沒有就退回原鍵。其他頁面既有的同類鍵尚未處理，留給 M1 的 UI 收尾。
- **一把真的 TMDB v3 API key 被當成「同形狀的假值」寫進測試**（票 08）。它從未被推送——帶著它的
  兩個 commit 都還在本地 `main` 上——但憑證仍已換掉，字串換成 `0000…0003`。假值的號碼表寫進
  `tests/fixtures/http/README.md`，那條規則現在管的不只是 fixture 檔，也管任何寫得出憑證形狀的測試。
- **泊位板的實測值標籤對比只有 3.56:1**（WCAG 2.2 AA 的驗收條件，PRODUCT.md）。`opacity-70` 疊在
  信號色塊上，正好把 `index.css` 註釋裡「白字配中明度色只有 3.6:1，過不了 AA」那個數字加了回來。
  拿掉 opacity 之後同一批標籤實測 **9.63:1**，精靈與健康頁兩塊板都適用。
- **英文版把大小寫敏感的 API 端點大寫掉**：剖面欄的 term 走 `.label`（拉丁文 `uppercase`），
  於是左欄印 `POST /LIBRARY/VIRTUALFOLDERS`、右欄印正確的 `POST /Library/VirtualFolders`，
  同一畫面兩種大小寫而其中一種不是真的端點。中文版因為 `text-transform: none` 沒有這個問題，
  所以一直沒被看到。`CutawayRow` 新增 `code` 變體給機器字串用。
- **索引站的「之後再說」按下去畫面毫無變化**：狀態存下去了，但只有 TMDB 那一節畫得出徽章。
  兩個審查代理與驗收本人都以為按鈕壞了而重複按。徽章同時改用新的 `source.deferred`
  （「之後再說」/「Deferred」）——原本借用的 `status.skipped` 是「已經是這樣」，那是冪等步驟的字。
- **`<summary>` 落回 Chrome 預設的 0.67px 焦點環**：`:focus-visible` 的選擇器漏了它。
- **「顯示」密碼按鈕 38.6 × 15px**，間距例外也不成立（距密碼框 11.5px < 12），不符 WCAG 2.2 AA 2.5.8。
- **窄版泊位板是 carousel**，BTH 3 與 BTH 4 整個在畫面外，而「一眼看出哪一格紅了」正是這塊板的
  用途；捲動容器還會變成一個沒有名字的 Tab 停留點。改回 shape brief 寫的 2×2。
- **精靈沒有出口**：設定跑完之後它就是設定入口（plan §6），但整頁沒有任何連結回得去，而設定頁
  三張服務卡片的「改位址或憑證」又全部連到裸 `/setup`（於是不管按哪一張都落在第 3 步
  「接手這台 Jellyfin」）。精靈新增 `?berth=1..4` 深連結、返回鍵，以及一句「不會重跑一次靠泊」。

- **入口腳本從來沒有接手過媒體根的擁有者**（`deploy/entrypoint.sh`）。`take_ownership` 的參數順序
  寫反，`/data` 那一次呼叫展開成 `chown /data berth:berth berth:berth`，一律失敗。Windows 上看不
  出來（那裡 `chown` 本來就會失敗且不影響寫入），但乾淨的 Linux 宿主上 Docker 新建的 `/data` 是
  `root:root`，Berth 連 `/data/library` 都建不出來，精靈第 3 步當場死。順帶讓腳本改讀
  `CONFIG_ROOT` / `DATA_ROOT`——它本來寫死路徑，與 Berth 自己讀的變數對不上。
- **qBittorrent 5.x 的登入被判成失敗**（`berth/adapters/qbittorrent/client.py`）。`auth/login` 成功時
  4.4.5 回 `200` + `Ok.`、5.2.3 回 `204` 空 body；失敗時 4.4.5 回 `200` + `Fails.`、5.2.3 回 `401`。
  原本的判定是「不是 `Ok.` 就是失敗」，所以**每一套用預設 image 的部署，qBittorrent 那一項健康檢查
  都永遠紅著**。判定改成只認 4.x 的 `Fails.`，兩個版本的實測回應都錄成 fixture。
- **Prowlarr 冷啟動時索引站清單超過探測逾時**（`berth/adapters/prowlarr/client.py`）。容器剛起來的
  第一次 `indexer/schema` 要讀進 627 份定義再組出 5.6 MB 回應，Windows 的 9p bind mount 上實測
  9.42 秒（第二次 0.34 秒），5 秒的探測逾時讓精靈第 5 步在乾淨部署上直接失敗。這一支端點改用自己的
  逾時。

### Security

- **`/api/routes/*` 與 `/api/jellyfin/libraries` 永遠只有 admin**（票 14a，推翻票 14）。原本精靈跑完之前
  它們與 `/api/setup/*` 一樣匿名開放，而停用的 Route 不算進完成條件，所以那一刻任何人都能把紅燈 Route
  停用、再按完成。精靈第 7 步的刪除改走 `DELETE /api/setup/routes/{id}`（同一個命令、同一種拒絕）。
