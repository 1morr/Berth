# 14e — 把 Route profile 整個拿掉

**Status:** ready-for-agent

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

- [ ] 上面清單逐項拿掉；`grep -rni profile berth web/src tests CONTEXT.md PRODUCT.md docs/plan.md` 只剩與 Route profile 無關的
      （`COMPOSE_PROFILES`、`appProfileId`、Sonarr 的 quality / release profile），brief 只剩 §19 與 §20.4 的紀錄；CHANGELOG 已記。
- [ ] migration 升版刪欄位、降版補回（預設 `standard`）；schema 比對的測試綠。
- [ ] 季號變體對非動漫的多季劇集也產生，單季與電影不產生，有測試。
- [ ] 精靈的 Route 步驟與「設定 → 媒體庫路徑」以 playwright 實跑，看得到沒有 profile 選擇、建立與修改照常；深淺兩主題各一張截圖。
- [ ] `uv run berth bench` 數字與 14d 結束時相同，貼輸出。
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest` 與
      `pnpm -C web format:check && pnpm -C web typecheck && pnpm -C web lint && pnpm -C web test` 全綠，貼指令輸出。

**不做：**

- 解析器的換算規則：14d。
- 量季號變體對真實索引站的效果。

## Comments
