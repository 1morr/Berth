# 14 — Route 設定頁：一個媒體庫多條 Route 與明確刪除

**Status:** done

**Blocked by:** 09（Job 開始引用 `route_id`）

**讀:** plan §6（routes 群組）、§9.3（第 7 步）、§9.5、§11.2（T1.9 第三條）；brief §4.3、§16.4；
`.scratch/m0/issues/09-wizard-routes.md` 的決定

## 做什麼

M0 票 09 記下的那條債：精靈第 7 步是以媒體庫名建索引、**重跑會刪掉沒勾的 Route**，而那時候
「M0 沒有任何東西引用 route_id」。票 09 之後 Job 引用了它，所以這條必須改成軟處理，並且要有一個
真正的 Route 管理入口。

brief §4.3 本來就允許一個 Jellyfin 媒體庫掛多條路徑，所以「一個媒體庫多條 Route」是既有需求，
不是新功能。

## 驗收

- [x] `GET/POST /api/routes`、`PUT/DELETE /routes/{id}`、`POST /routes/{id}/check`（外加 plan §6 的
      `GET /api/jellyfin/libraries`，新增 Route 時向 Jellyfin 現查）
- [x] 同一個 Jellyfin 媒體庫建得出第二條 Route（不同 slug 與 target_path，劇集可挑不同 profile）——slug 由
      媒體庫名導出（`tv-2`），名稱另填；電影媒體庫的 Route 不收 anime profile
- [x] 刪除是明確動作並要二次確認；被 Job 或 ledger 引用的 Route 不能直接刪，說明原因並給出路（停用）
- [x] **重跑精靈第 7 步不再隱式刪掉沒勾的 Route**（有測試釘住；使用者拍板：精靈只新增、不改不刪）
- [x] 新建或修改的 Route 跑一次 plan §9.5 的五條纜繩檢查，紅的不給啟用——新建紅燈維持停用、從停用到
      啟用紅燈回 409；精靈跑完之前由第 7 步建的仍直接啟用（紅著就擋完成）
- [x] `/settings/routes` 只有 admin 進得來，規則在門禁 middleware 而不是 router 的相依——`/api/routes` 與
      `/api/jellyfin/libraries` 跟著 `setup/*` 那條規則（精靈跑完之前匿名開放，精靈第 7 步的刪除要用）
- [x] 設定頁走 `/impeccable shape`（`.scratch/m1/route-settings-shape.md`）；實跑並附結果——playwright 的
      瀏覽器被另一個程序佔用，改用 chrome-devtools 實跑（見 Comments）
- [x] 對比 ≥ 4.5:1；390px 窄版可用；zh-Hant 與 en 並列
- [x] lint / type / test 全綠並貼指令輸出

## 驗證

```
$ uv run ruff format berth tests scripts && uv run ruff check berth tests scripts
202 files left unchanged
All checks passed!

$ uv run mypy
Success: no issues found in 198 source files

$ uv run lint-imports
Contracts: 6 kept, 0 broken.

$ uv run pytest -q
1306 passed in 267.82s (0:04:27)

$ pnpm -C web format:check && pnpm -C web typecheck && pnpm -C web lint && pnpm -C web test
All matched files use Prettier code style!
 Test Files  19 passed (19)
      Tests  278 passed (278)
```

（在 Git Bash 裡跑，`deploy/` 的 shell 腳本測試包含在 1306 裡。`pnpm -C web gen:api` 已重產 `schema.d.ts`。）

## Comments

### 實跑（`--scenario routes`，chrome-devtools）

playwright MCP 的瀏覽器被另一個程序佔著（`Browser is already in use`），本機也沒有 playwright 套件，所以
改用 chrome-devtools MCP 開一個隔離的 context 實跑同一個前端 build。沒有去關別人的瀏覽器。

- 登入 `skipper` 之後直接到 `/settings/routes`：子分頁列「服務 | 媒體庫路徑」、三條綠燈 Route 收起；
  TV 那一列（演練情境塞了一筆已入庫的下載）展開後沒有刪除鍵，寫著「1 筆下載、0 個入庫檔案指著這條
  Route，所以它刪不得。停用它……」。
- **一庫多條**：「新增 Route」按下去才向 Jellyfin 問；選 TV 之後 `/data/library/tv` 選不了、旁邊寫
  「已是「TV」」，第二顆碟自動選定；名稱改「TV 2」、選動漫、建立並檢查 → 清單多一列
  `TV 2 · berth-tv-2`，五條纜繩全綠、已啟用。
- **紅燈建立**：Movies 那條沒掛進 Berth 的路徑 → `Movies · berth-movies-2` 建立但停用、就地展開，
  `library_path` 紅燈附服務原文與 berth 的 compose 片段；勾啟用再儲存 → 「五條纜繩沒有全綠，這條 Route
  維持停用」，勾選框退回未勾。
- **刪除**：那一條沒有東西指著它 → 「刪除這條 Route」→ 就地展開後果說明 →「確定刪除」→ 列消失。
- **精靈泊位 4**（`/setup?berth=4`）：按鈕是「重新檢查 5 條 Route」，每條 Route 底下有同一個刪除元件。
- **健康頁**：Route 區塊有「到 Route 設定」。
- code-review 修完之後重 build、重起情境再走一次：TV 的「刪不得」由後端的 `in_use` 決定，刪除警告不再
  插入 category；切到 EN，子分頁、`1 download / 0 downloads`、刪不得的說明與警告都是英文。
- 對比與窄版（逐一計算每個有文字的元素對它實際底色的對比）：淺色 1280 最低 **5.71:1**、深色 1280 最低
  **5.22:1**、深色 390（新增區塊展開）最低 **6.53:1**、淺色 390（新增區塊展開）最低 **5.71:1**；四輪頁面
  層級橫向捲動都是 0。截圖在 session scratchpad（`t14-*.png`）。
- 定時的健康檢查在實跑途中把 Movies 那條既有 Route 驗成紅燈（情境刻意多掛了一條看不到的路徑）：它維持
  啟用，沒有被默默停掉——與「已啟用的 Route 變紅不會被停用」的決定一致。

### 與票面字面不同、或這一票沒做的

每一條都記在 `docs/progress.md` 的「偏差與決定」：

- 精靈只新增不改不刪、紅燈建立但停用、PUT 只改名稱 / profile / 啟用——使用者拍板。
- 停用的 Route 不算進健康總結、精靈的完成條件與泊位板的信號（票面沒寫，是停用成為出路之後的後果）。
- **待使用者確認**：上一條加上 `/api/routes` 在精靈跑完之前匿名開放，代表那一刻匿名呼叫者可以把紅燈 Route
  停用再按完成（spec 軸 code-review 指出）。畫面沒有這個入口，暴露面與同一時期整組匿名的 `setup/*`
  相同；記下來而沒有再加一條規則。
- 刪除不清掉 qBittorrent 的分類與 complete 子目錄。
- 精靈泊位 4 的剖面「將建立」在全部建好之後仍列出三條（套件內）；「只新增」之後它說的其實是「會涵蓋的」，
  沒有改文案。
- **TDD 的偏差**：「紅燈建立但停用」那一條在實作 `create_route` 時一起寫進去，測試寫的時候已經是綠的；
  健康頁「到 Route 設定」與「停用」色塊的測試也是直接綠（實作與測試同一輪寫）。其餘接縫（精靈重跑、
  建立 / 修改 / 刪除 / 重新檢查 / 清單、API 與門禁、設定頁各切片、精靈的鎖與刪除、code-review 的五條
  spec 修正）都先看過紅燈。
- 後端全套件第一輪為了少一點輸出加了 `-p no:logging`，那個旗標拿掉了 `caplog`，`TestJobLogging` 因此
  報 1 error；拿掉旗標重跑是綠的，最後貼的是不帶旗標的輸出。

### code-review（兩軸，基準 `b570172`）

**處理了的**：
- 精靈跑完之後重跑新建的紅燈 Route 改成停用。
- 檢查與精靈認媒體庫改用 `ItemId`。
- 電影不收 anime。
- 補「啟用被拒時名稱與 profile 照樣存下」與精靈跑完之前匿名 `DELETE` / `GET /jellyfin/libraries` 的測試。
- 門禁前綴只開到 `/jellyfin/libraries`，常數改名 `OPEN_UNTIL_SETUP_PREFIXES`。
- `selected` 改名 `has_route`；`in_use` 由後端給。
- `RouteIdentity` 共用；兩處 collection type 從 `.label` 改 `.value`；刪除警告不插 category。
- `SettingsTabs` 改清單、`freePaths`、`_find_route`；演練情境的旗標與函式改名。

**沒處理、留著的**：
- `create_route` 與精靈 `_plan` 的驗證沒合併：兩邊的媒體庫型別（Jellyfin 現查 vs 第 3 步快照）與錯誤型別
  （`RouteRejectedError` vs 精靈的 `ValueError` → 422 字串）都不同，硬合要先統一精靈的錯誤形狀。
- `api/routes.py` 五個端點各一段 `try/except RouteRejectedError`：與 `api/jobs.py` 同一個寫法，改成全域
  exception handler 要兩個 router 一起動。
- `routeRefusalOf` 與 `jobs.ts` 的 `refusalOf` 只差型別，沒泛型化。
- 「已是哪一條 Route」的名字在前端以 `target_path` 反查，沒有讓後端的 `taken` 帶 Route 名。
- 拒絕理由在 Python 端是字串、TS 端是字面聯集（與 `JobRejectedError` 同一個既有模式）。
- 英文分頁叫 `Library paths`，與 CONTEXT.md「library path 是單一媒體庫的路徑」的 _Avoid_ 有落差——精靈第
  7 步的英文標題本來就是這個字，沿用；頁內連結叫「Route 設定」。
- impeccable hook 回報 `.impeccable/design.json` 比 `DESIGN.md` 舊（沒有照 skill 規則自動修），與票 13
  相同，留給票 15 的 `/impeccable document`。
