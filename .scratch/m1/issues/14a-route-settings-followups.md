# 14a — Route 設定頁的後續：門禁收緊、並行安全、精靈重跑與 UX

**Status:** ready-for-agent

**Blocked by:** 14（done）。2026-09-15 插入，排在 14 之後、14b 之前。

**讀:** plan §6（門禁段、setup 列、routes 列）、§7（路由與守衛）、§9.3（第 7 步）、§9.5；票 14 全文與
`.scratch/m1/route-settings-shape.md`；參考實作 `git show 4f05b9d:<path>`（票 14 的另一份實作，main-2）

## 做什麼

票 14 有兩份獨立實作：main（e34fe18）與 main-2（4f05b9d）。比較之後以 main 為準，理由是 main 的精靈第 7 步
「只新增、不改不刪」符合使用者拍板，main-2 重跑精靈會隱式停用、重新啟用 Route，還會覆寫 profile。

這張票做兩件事：

- 把 main-2 做得比較好的幾處搬進來。
- 修 main 自己的風險，其中並行問題兩份都有。

另外解掉票 14 留下的「待使用者確認」：精靈跑完之前 `/api/routes` 匿名開放，所以匿名呼叫者可以先停用紅燈的
Route，再按完成。

## 使用者拍板（2026-09-15）

- 以 main 為底，main-2 不合併。
- 額外範圍全收：
  - 精靈補目標佔用檢查。
  - 新 Route 先檢查再啟用。
  - 刪除的競態。
  - 並行建立不回 500。
- 停用的 Route，健康迴圈**照樣檢查**（main 現狀，`check_routes` 不過濾 enabled），不搬 main-2 的略過。
- 精靈勾選的寫入目標已經被別的 Route 佔用時**略過**，不回 422。這跟「已有 Route 的媒體庫略過」是同一條只新增規則；
  回 422 的話，套件內模式三個媒體庫自動全勾，一旦 key 對不上，重跑就永遠卡住。

## 後端（照 TDD 順序，每一步結束 repo 都能跑）

skills：services 修 bug 用 `mattpocock-skills:tdd`；鎖 helper 與 `RouteDelete` 的介面用 `codebase-design`；收尾用 `code-review`。

- **B1 釘住啟用語意。** 在 `tests/integration/test_routes.py` 的 `TestUpdate` 加兩條：「已啟用的 Route 存檔時變紅仍維持啟用」、
  「停用永遠允許」。來源是 main-2 的 `tests/integration/test_route_settings.py:391-419`。`update_route` 本來就是這樣做的，
  所以這兩條會直接綠，記一條 TDD 偏差。
- **B2 單條 Route 的引用數改用前綴篩。** 在 `berth/services/routes.py` 新增 `_usage_of(session, route, routes)`：
  - jobs：`count where route_id`。
  - ledger：先用 `LedgerEntry.target_path.startswith(prefix, autoescape=True)` 粗篩，再用既有的 `owning_route` 精判
    （參考 main-2 `routes.py:456-469`）。
  - `delete_route` 改用它。`list_routes` 的 `_usages` 聚合不動，因為清單要算每一條，整張表本來就要讀。
  - 測試：巢狀 Route（`…/tv` 與 `…/tv/anime`）時，單條與清單算出的數字一致。
- **B3 409 改成結構化。** 新增 `RouteInUseError(RouteRejectedError)`，帶 `usage: RouteUsage`。`berth/api/routes.py` 的 `_refuse`
  改成公開的 `route_refusal()`，把 `jobs`、`ledger_entries` 併進 detail（沿用 main 的用詞）。
- **B4 已佔用的路徑帶 Route 名。** `LibraryOption` / `LibraryOptionOut` 的 `locations` 與 `taken` 合成
  `paths: [{path, route_name: str | None}]`，再跑 `pnpm -C web gen:api`。前端 `web/src/settings/AddRoute.tsx` 拿掉
  `routes.find(target_path)` 的反查與 `takenUnnamed`，`web/src/test/fixtures.ts` 跟著改。這是內部 API，不留相容層。
- **B5 送單撞上剛刪掉的 Route。** `berth/services/jobs.py` 的 `add_download`：
  - `try` 往前擴，包住 `session.add`、`record_event` 的 flush 與 commit。外鍵違反在 flush 當下就會丟，等不到 commit。
  - `IntegrityError` 之後：rollback → 查 duplicate → Route 不在就回 `JobRejectedError("route_missing")`（422），不再是 500。
- **B6 刪除的競態。** 在 `routes.py` 加私有的 `_write_lock(session)`：
  - 做法：先 `commit()`，再執行一句 0 列的 `UPDATE routes SET id = id WHERE id = -1`。這讓驅動在 legacy 交易模式下發 BEGIN
    並取得寫鎖（SQLAlchemy sqlite 方言文件：legacy 模式不為 SELECT 發 BEGIN）。
  - 規矩：取鎖之後一律重讀，鎖內不打網路。
  - `delete_route` 的順序：取鎖 → `_find_route` → `_usage_of` → delete → commit。
  - 並行測試照 `tests/integration/test_downloads.py:688-714` 的寫法（兩個 session factory + `asyncio.gather`）：
    計數之後，另一個 session 插入一筆引用這條 Route 的 Job。斷言三件事：持鎖時插入被擋住、刪除之後插入拿到外鍵的
    IntegrityError、沒有 `route_id IS NULL` 的孤兒。
  - **「0 列的 UPDATE 也拿得到寫鎖」必須由這條測試實證**；不成立就改成對目標那一列做 no-op UPDATE。
- **B7 並行建立。**
  - `create_route` 的順序：
    1. `_live_library`（網路，鎖外）
    2. 取鎖
    3. 重讀既有 Route
    4. 檢查 `target_taken`
    5. 算 slug、insert、commit
    6. 鎖外跑檢查
  - `IntegrityError` 兜底：rollback 之後重讀。目標被佔就回 `target_taken`，否則回新理由 `route_conflict`（409）。
  - `update_route` / `check_route` 與刪除並行時的 `StaleDataError`，轉成 `route_missing`。
- **B8 精靈的目標佔用。** `_plan` 維護一個 `targets` 集合（既有 Route 加上這一批）。目標已被佔用的選擇略過，docstring
  寫明理由。測試放 `tests/integration/test_setup_routes.py`：
  - 舊 Route 沒有 ItemId、媒體庫又改了名時，重跑不會長出同目標的第二條。
  - 同一批裡兩個選擇指到同一個目標，只建一條。
- **B9 精靈跑完之後重跑時的啟用窗口。**
  - `build_routes`：新 Route 以 `enabled=not setup.completed` 建立。insert 在鎖內，而且是重讀既有 Route、跑完 `_plan` 之後才做。
  - 檢查跑完之後，若精靈已經完成，才把綠的 Route 設成啟用。
  - 測試：檢查途中（包住 fake qBittorrent 的 `ensure_category`）用另一個 session 讀新 Route，`enabled is False`；
    跑完之後綠的已啟用、紅的維持停用。
- **B10 門禁收緊。**
  - `berth/api/setup.py` 新增 `DELETE /setup/routes/{route_id}`：成功回 204，Route 不在回 404 `route_missing`，
    被引用回 409 `route_in_use`。呼叫同一個 `delete_route`，錯誤走 `route_refusal()`。
  - `berth/api/gate.py` 拿掉 `OPEN_UNTIL_SETUP_PREFIXES`，改成 `ADMIN_PREFIXES = ("/settings", "/routes", "/jellyfin/libraries")`。
  - 改寫 `tests/integration/test_routes_api.py` 裡釘住「精靈跑完之前匿名」的兩條：
    - 精靈跑完之前：`GET /api/routes` 與 `/api/jellyfin/libraries` 回 401，`DELETE /api/setup/routes/{id}` 回 204。
    - 精靈跑完之後：非 admin 回 403，admin 回 204。

## 前端

- **F1 刪除之後有回饋。**
  - 先修 `web/src/test/fetch.ts`：204 時 body 給 null（參考 main-2 `web/src/test/fetch.ts:29-33`；現在的寫法會丟 TypeError，
    把刪除成功的測試都遮住了）。
  - `RouteDelete.tsx` 改成注入 `onDelete: () => Promise<void>`（必填）：設定頁傳 `deleteRoute`，精靈的 `RouteStep.tsx`
    傳新的 `deleteSetupRoute`（`web/src/api/setup.ts`）。
  - 頁面層（`RouteSettingsPage`、`RouteStep`）放一個常駐的 aria-live 區塊，播「已刪除「X」。」。
  - `RouteSettingsPage.test.tsx` 與 `SetupPage.routes.test.tsx` 的刪除測試補三個斷言：列消失、有播報、
    精靈打的是 `/api/setup/routes/{id}`。
- **F2 一鍵停用。**
  - `RouteDelete` 加 `onDisable?`。Route 被引用、而且還是啟用時，給一顆「停用這條 Route」。
  - `RouteRow` 用**已存下的** name / profile 送 PUT `enabled:false`，不順帶送出沒儲存的編輯；成功之後播報。
  - `RouteEditor` 在 `route.enabled` 變了時重設勾選框。
  - 改寫 `routeSettings.delete.inUse` 的文案（zh-Hant / en）。
  - 精靈不給停用鈕。
- **F3 拒絕帶數字。**
  - `web/src/api/routes.ts` 的 `routeRefusalOf` 解析選填的 `jobs`、`ledger_entries`，`delete.refused` 的文案帶上數字。
  - `route_conflict` 加進拒絕理由的聯集、`CREATE_REFUSAL` 與 i18n。
- **F4 重新檢查的播報。** 按「重新檢查」之後，aria-live 播「檢查跑完了。」（參考 main-2 `RouteSettingsPage.test.tsx:167-175`）。
- **F5 `/settings` 轉址。** `web/src/routes.tsx` 加 `/settings` 轉到 `/settings/services`；`web/src/AppShell.tsx` 頁首的
  NavLink 改成 `to="/settings"`，兩個設定頁上「設定」都會亮。`SettingsTabs.tsx` 不改名。
- **F6 沒有空路徑時給 Jellyfin 連結。**
  - `web/src/inventory/jellyfinLink.ts` 抽出 `jellyfinBase(web, here)`（參考 main-2），補單元測試。
  - `AddRoute.tsx` 在沒有空路徑時，用既有的 `jellyfinAddressQueryOptions`（`web/src/api/settings.ts`）給
    `${base}/web/#/dashboard/libraries`；base 為 null 時只留文字。

## 文件（跟實作同一個 commit）

- `docs/plan.md`：
  - §6：
    - 改寫門禁段：`routes` / `jellyfin/libraries` 永遠只有 admin，精靈的刪除走 `DELETE /setup/routes/{id}`。
    - setup 列加上那支 DELETE。
    - routes 列改成 `paths[{path, route_name}]`，並寫明 409 帶 `jobs` / `ledger_entries`、新理由 `route_conflict`。
  - §7：加 `/settings`（轉址）。
  - §9.3 第 7 步：補「目標已被佔用就略過」與「精靈跑完之後新建的先停用，綠了才啟用」。
- `CHANGELOG.md`：Changed / Fixed / Security。
- `README.md` fake 情境表的 `routes` 列補兩句：「Anime 沒有空路徑 → Jellyfin 連結」、「TV 被引用 → 一鍵停用」。情境本身不用改。
- `docs/progress.md`：加 session 紀錄；偏差與決定寫這幾條：門禁推翻票 14、精靈略過已佔用的目標、先停用再啟用、寫鎖的做法、API 形狀。
  票 14 的待確認標為已解。

## 驗收

- [ ] B1–B10、F1–F6 每一項都有測試釘住（B1 是既有行為的回歸測試）。
- [ ] 刪除與建立的並行測試（B6、B7）在修正前是紅的、修正後是綠的，證明寫鎖真的擋得住另一條連線。
- [ ] 精靈跑完之前，匿名打不到 `/api/routes/*` 與 `/api/jellyfin/libraries`；精靈的刪除照常可用。
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest` 全綠，貼指令輸出。
- [ ] 跑過 `pnpm -C web gen:api`，`schema.d.ts` 已提交；`pnpm -C web format:check && pnpm -C web typecheck && pnpm -C web lint && pnpm -C web test`
      全綠，貼指令輸出。
- [ ] 用 `uv run python scripts/fake_setup_server.py --scenario routes` 實跑，工具用 playwright；被佔用時改 chrome-devtools
      或 claude-in-chrome，並記在 Comments。要看的畫面：
  - [ ] `/settings` 轉址，頁首「設定」在兩個設定頁都亮。
  - [ ] TV 一鍵停用：出現停用色塊、有播報、按鈕消失。
  - [ ] 新增時選 Anime，出現 Jellyfin 連結，核對 href。
  - [ ] TV 已佔用的路徑，顯示後端給的 Route 名。
  - [ ] 建 TV 2 再刪掉：列消失、有播報。
  - [ ] 重新檢查有播報。
  - [ ] `/setup?berth=4` 的刪除打的是 `/api/setup/routes/{id}`。
  - [ ] 切 EN。
  - [ ] 深淺兩主題 × 1280 / 390：對比 ≥ 4.5:1，沒有橫向捲動。
- [ ] 文件已更新、已 commit。

**不做：**

- `routes.target_path` 的 unique index：兩個建立點都在鎖內檢查過；字串唯一也擋不住結尾斜線、大小寫這類語意上的重複；
  不做就不用 migration。
- 精靈勾選表上標出已被佔用的路徑：記債。
- 刪除時清掉 qBittorrent 的分類：票 14 已記。

## Comments

- main-2 的 worktree（`C:\Users\Roxy\orca\workspaces\MediaServer\main-2`，分支 `1morr/main-2`）這張票完成之前先不動；
  完成之後再問使用者要不要清理（先問要不要備份）。
