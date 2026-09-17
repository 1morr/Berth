# 14e — 把 Route profile 整個拿掉

**Status:** done

**Blocked by:** 14d（2026-09-16 插入，排在 14d 之後、15 之前：票 15 的 UI 收尾要審的是拿掉之後的精靈與設定頁）

**讀:** `docs/research/profile-effect.md` §1、§6；brief §19（Route profile 那一列）；plan §2.2（`routes`）、§4.3（`ParseContext`）、§4.6、§6（routes 與 search 兩列）、§8.4（搜尋詞）、§9.3（第 7 步）；CONTEXT.md 的 **Library Route** 與 **Profile**

## 做什麼

使用者 2026-09-16 拍板移除 Route profile（brief §19）。14d 之後解析器已經不讀它，剩下的讀者是搜尋的季號變體與
「電影不收 anime」；這一票把欄位、API、介面、語料與文件裡的它全部拿掉。

**這是對外介面與持久化資料的破壞性變更，使用者已同意**：`routes.profile` 欄位刪除，API 上的 `profile` 欄位
與搜尋的 `route` 參數刪除。內部 API，不留相容層。

搜尋的季號變體改成**對所有劇集都做**：最新一季 ≥ 2 就多問 `<英文標題> Season N` / `<標題> 第N季`，不分動漫
（使用者拍板；沒有量，要打真的索引站才量得到）。

## 檔案清單

2026-09-16 以 `grep -rni profile` 盤點（排除 `COMPOSE_PROFILES`、Prowlarr 的 `appProfileId`、Sonarr 的 quality / release profile）：

- **資料**：`berth/models/route.py` 的 `profile` 欄位；新的 Alembic migration 刪欄位（`8b1e1dc5336b_m0_tables.py` 建的）。
- **domain**：`berth/domain/enums.py` 的 `Profile`、`domain/__init__.py` 的匯出、`domain/parser.py` 的 `ParseContext.profile`。
- **parser**：`berth/parser/mapping.py` 剩下的 import（14d 之後應該只剩它）。
- **adapters**：`berth/adapters/indexer/__init__.py` 模組 docstring 第 9 行「Route 的 profile」那一句。
- **services**：
  - `services/routes.py`：三個輸入 / 輸出 dataclass 的 `profile`、`_check_profile` 與 `profile_unsupported`、套件內 Route
    以 slug 判斷 `anime`（`bundled.slug == "anime"`）、`update_route` 改 profile 的那一行、精靈計畫與健康檢查帶出去的欄位。
  - `services/search.py`：`search_titles(snapshot, profile)` 拿掉參數、季號變體對所有劇集、`_profile`；`plan_queries` /
    `search_torrents` 的 `route_id` 只為 profile 存在，一起拿掉。
  - `services/plan.py`：組 `ParseContext` 那一行。
  - `services/bench.py`：`Fixture.profile`、`_fixture` 讀 `context.profile`。
- **API**：`api/routes.py` 的 `RouteIn`、`RouteEditIn`；`api/schemas.py` 的 `RouteOut`；`api/setup.py` 的 `LibraryChoiceOut`、
  `RouteSelectionIn`；`api/search.py` 兩支端點的 `route` 參數。之後 `pnpm -C web gen:api` 重產 `web/src/api/schema.d.ts`。
- **前端**：`components/ProfilePicker.tsx` 刪除；`settings/AddRoute.tsx`、`pages/RouteSettingsPage.tsx`、`setup/RouteStep.tsx`、
  `setup/MooringLine.tsx`、`setup/signals.ts`、`media/RoutePicker.tsx`、`media/SearchPanel.tsx`、`pages/MediaDetailPage.tsx`、
  `components/RouteDelete.tsx`、`api/routes.ts`、`api/schemas.ts`、`api/search.ts`；`i18n/resources.ts` 兩種語言的
  `picker.profile`、`profile.*`、`profile_unsupported`；`test/fixtures.ts` 與 `RouteSettingsPage.test.tsx`、
  `SetupPage.routes.test.tsx`、`SetupPage.test.tsx`。
- **後端測試**：`tests/unit/test_parser_mapping.py`、`tests/unit/test_cli.py`、`tests/integration/` 的 `test_routes.py`、
  `test_routes_api.py`、`test_setup_api.py`、`test_setup_routes.py`、`test_setup_service.py`、`test_search.py`、`test_plan.py`、
  `test_jobs.py`、`test_downloads.py`、`test_inventory.py`、`test_media.py`、`test_adapter_contracts.py`。守 `profile_unsupported`
  的測試連同規則一起刪。
- **語料**：`tests/fixtures/parser/**/*.json` 每一筆的 `context.profile`；語料 README 的範例與 v2 那一節的說法。
- **腳本**：`scripts/experiments/profile_effect.py` 刪除（它量的東西不存在了），`scripts/experiments/README.md` 那一列與
  根 README〈實驗腳本〉那一段一起拿掉；研究文件留著當紀錄，開頭註明腳本已隨 14e 刪除。
- **文件**：CHANGELOG（`### Changed` 記 API 形狀與 `routes.profile` 欄位的破壞性變更、季號變體對所有劇集，`### Removed`
  記 profile 選擇與 `profile_unsupported`）；CONTEXT.md（**Library Route** 的定義、**Profile** 整條）；brief §6.1（上下文訊號）、
  §6.9（fixture 的上下文）、§8（`routes`）、§10（「TVDB 作為 anime profile 的季集來源」那一段的措辭）；plan §2.2、§4.3、§4.6 的 JSON 範例、§6 的 routes 與 search 兩列、§8.4、§9.3 第 7 步；PRODUCT.md 第 109 行
  「TVDB 是否作為 anime profile 的季集來源仍標記【研究】」（brief §10 早已結案，一起改掉）。

## 驗收

- [x] 上面清單逐項拿掉；`grep -rni profile berth web/src tests CONTEXT.md PRODUCT.md docs/plan.md` 只剩與 Route profile 無關的
      （`COMPOSE_PROFILES`、`appProfileId`、Sonarr 的 quality / release profile），brief 只剩 §19 與 §20.4 的紀錄；CHANGELOG 已記。
- [x] migration 升版刪欄位、降版補回（預設 `standard`）；schema 比對的測試綠。
- [x] 季號變體對非動漫的多季劇集也產生，單季與電影不產生，有測試。
- [x] 精靈的 Route 步驟與「設定 → 媒體庫路徑」以 playwright 實跑，看得到沒有 profile 選擇、建立與修改照常；深淺兩主題各一張截圖。
- [x] `uv run berth bench` 數字與 14d 結束時相同，貼輸出。
- [x] `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest` 與
      `pnpm -C web format:check && pnpm -C web typecheck && pnpm -C web lint && pnpm -C web test` 全綠，貼指令輸出。

**不做：**

- 解析器的換算規則：14d。
- 量季號變體對真實索引站的效果。

## Comments

- 2026-09-17 驗收 grep 剩下的命中逐類說明（都不是 Route profile 的讀寫）：m0 migration 建的 `profile` 欄位與這一票的
  migration `9d4f1b6e2a70` 本身、`tests/integration/test_database.py` 守它的測試；指向研究文件檔名
  `docs/research/profile-effect.md` 的連結（`parser/mapping.py`、`tests/unit/test_parser_mapping.py`、語料 README、
  plan §4.4、brief §6.4）；錄下來的外部服務回應（Jellyfin 的 `"Profile": "High"`、Prowlarr 的 `Sync profile`、TMDB 的
  `profile_path`）；`COMPOSE_PROFILES`、`appProfileId`。
- **migration 升版用原生 `DROP COLUMN`、降版存下再寫回指向 Route 的兩欄**：`jobs.route_id` 與 `media.default_route_id`
  是 `ON DELETE SET NULL`，batch 重建 `routes` 會在 `DROP TABLE` 那一步把它們清空（scratchpad 實驗、再以票上的測試
  先用 batch 寫法看過紅燈 `(None, None)`、拿掉寫回那段也看過紅燈）。
- 「設定 → 媒體庫路徑」的實跑中途 playwright MCP 斷線，後半段（改名儲存、新增第二條 Route、兩張截圖）改用
  chrome-devtools；精靈泊位 4 是 playwright 跑的。截圖在 session scratchpad：`wizard-routes-{dark,light}.png`、
  `settings-routes-{dark,light}.png`。PUT body `{"name":"TV","enabled":true}`、POST body
  `{"library_id":"item-tv","target_path":"…/library-disk2/tv","name":"TV 2"}`，四條 Route 的回應都沒有 `profile`。
- 精靈用 `mixed` 情境（既有 Jellyfin）：泊位 4 勾選劇集類型的 Anime 媒體庫，展開區只有寫入目標與「加入 Berth 路徑」；
  建立照常。那條 Route 的 `library_path` 紅燈是替身 NAS 的 `/volume1/media/anime` 在這台機器上不存在，與本票無關。
- `web/src/i18n/resources.ts` 英文 `inventory…versions.pending` 那一行的換行是 prettier 改的：e02e54e 的這個檔就過不了
  `prettier --check`（票 14b 加的那一行），驗收要 `format:check` 綠燈所以留著。
- code-review 沒處理的發現：
  - `services/search._context` 把作品類型填進 `ParseContext.route_collection_type`，搜尋不帶 Route 之後名字不準
    （Standards 軸，判斷題）。那是 domain 欄位名，解析器與 plan 都用它，不在這一票改。
  - `test_a_movie_does_not_add_them` 單獨紅不起來：電影快照本來就沒有季，與單季劇集落在同一條規則（兩軸都提）。
    沒有替它在 `_season_variants` 加 `kind` 判斷——那是替不存在的資料寫的分支；docstring 照實寫它守的是什麼。
- 順帶看到、沒動：精靈泊位 4 的剖面「Route 數」數的是「這一輪要新建的」，建完之後變 0（e02e54e 就是這樣），
  票 15 的 critique 可以看一眼。
