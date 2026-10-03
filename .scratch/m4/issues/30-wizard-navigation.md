# 30 — 精靈導覽：上一頁回到上一步、重新整理留在原頁、手機首屏、套件內卡片先查主機名

**Status:** done

**Blocked by:** None — can start immediately

**讀:** `docs/research/wizard-qa-2026-10-01.md`（第 23、24 條與「兩條決定」第二條）；brief §19（每個服務手動選擇）；
plan §9.3〈前端的導覽〉；`web/src/setup/navigation.ts`；`PRODUCT.md`、`DESIGN.md`；先跑 `/impeccable shape`

## 為什麼（2026-10-01 精靈實測）

- **瀏覽器「上一頁」直接離開精靈（兩邊，實測證實）。** 精靈步驟不進 history（`web/src/pages/SetupPage.tsx:108-131`）。
  NN/g 的精靈準則要求可以回上一步。截圖 B3-03、E10-06。
- **回頭看某一頁時重新整理，被帶回目前這一步；已完成的頁重新整理被推到下一頁（實測證實）。** 截圖 B3-01。
- **手機寬度的首屏被泊位板和底部固定列佔掉（全新，實測證實）。** 390 寬沒有橫向溢出，但一進頁幾乎只看到泊位板
  （`web/src/setup/BerthBoard.tsx`）。截圖 B11-08、B11-09。
- **只有 Berth 時「套件內」照常列出（使用者 2026-10-01 決定）。** 選了才說主機名解不到。決定：進頁只做主機名解析
  （`jellyfin`、`qbittorrent`、`prowlarr`），不對服務發請求；解不到的卡片直接寫「這套 compose 沒有起 X」並附加回
  `COMPOSE_PROFILES` 的指令；**不預選、不停用**。brief §19「每個服務手動選擇、選之前不發請求」不變。截圖 E9-01、E9-02。

## 做什麼

1. 目前看的步驟放進 URL（例如 `/setup?step=3`），上一頁／下一頁在「≤ 後端頁」的範圍內移動；超出時回到後端頁。重新整理
   留在 URL 指的那一頁。
2. 手機寬度的泊位板收成一列摘要（可展開），首屏先看到這一頁要做的事。依 `/impeccable shape` 的結果定。
3. 新增一支唯讀 API（或併進 `GET /setup/status`）回三個套件內主機名能不能解析；服務頁的套件內卡片據此加註與補法。
4. progress.md「偏差與決定」記第 3 點（只查 DNS 不算「選之前發請求」）。

## 驗收

- [x] vitest：URL 的 step 與畫面一致；瀏覽器上一頁回到上一步、不離開精靈；超過後端頁的 step 被拉回
- [x] 整合測試：主機名解不到的服務標為不在 compose；解得到的不標（雙向）；過程沒有對服務發 HTTP 請求
- [x] vitest：套件內卡片的加註與補法；卡片仍可選
- [x] playwright：390 寬首屏截圖、上一頁、重新整理；只有 Berth 時頁 1 的卡片加註。附截圖
- [x] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈

## Comments

**2026-10-03 實作紀錄**

- 導覽：`/setup?step=N`（`navigation.stepOf` / `shownStep` / `go`，路由的 `validateSearch`）。原本的 `pinned` 與 `hold` 刪掉——網址一直
  寫著畫面上那一頁。SetupPage 的 vitest 改掛在 `test/render.renderInRoute` 的路由上；泊位板的查詢收到 `test/board.boardCells()`
  （摘要列的名字裡也有目前那一格的泊位碼）。
- 窄版泊位板：shape 三題照建議（`.scratch/m4/wizard-navigation-shape.md`），`components/BerthBoard` 的 `summary`；DESIGN.md 記板與
  三重編碼的例外。
- `GET /setup/compose`：`services.setup.resolve_bundled` → `adapters.dns`。卡片加註在 `ServiceChoice`（`composeHosts`），還沒選時卡片
  下給 `signals.bringBack` 的兩行，與 `not_deployed` 的補法同一組。
- 演練伺服器：`ScenarioHosts`（照情境回答，真的解析器在宿主上要等好幾秒）、新情境 `berth-only`、`absent` 標 Jellyfin 沒起；e2e
  多 `compose-absent`／`compose-absent-390`，wizard 加 390 首屏、重新整理、上一頁／下一頁。

**實測（工作樹 build 的 image `berth:qa-t30`，`berth-qa/bundled` 以 override 換 image；用完 down、清 config、刪 image；沒碰
berth-trial、berth-existing）**

1. `COMPOSE_PROFILES=`（只有 `qa-berth`）：`GET /api/setup/compose` 200、約 2.6 秒、三個都 `false`；容器裡三個名字都是
   `gaierror -5`、各約 1.27 秒（brief §20.14）。390 寬首屏是一列摘要＋二選一，「套件內」卡片寫「這套 compose 沒有起 Jellyfin。」，
   卡片下兩行補法；展開是整塊 2+2+1（`.playwright-mcp/t30-01-berth-only-390.png`、`t30-02-board-expanded-390.png`，不進版控）。
2. 起完整套件：同一支 8 毫秒、三個都 `true`，重新整理後卡片不加註。選套件內 Jellyfin、建擁有者、前往頁 2（`?step=2`）→
   瀏覽器上一頁回到「擁有者：qat30owner」（`?step=1`）→ 重新整理仍在頁 1（原本被推到頁 2）→ 下一頁回頁 2 → 手打 `?step=5`
   拉回 `?step=2`（`t30-03`～`t30-05`）。
3. e2e 截圖：`web/test-results/wizard-…-wizard-390/1-first-viewport.png`、`compose-absent-…/1-absent-viewport.png`（桌機與 390）。

**code-review 未處理的發現**

- Standards：`SetupPage` 對 `useSearch({ strict: false }).step` 再跑一次 `stepOf`，與路由的 `validateSearch` 重複（Duplicated Code）。
  留著：測試的 `renderInRoute` 路由沒有 `validateSearch`，頁面自己驗才不靠掛法。
- Standards：`get_host_resolver` → `clients.host_resolver` → `SystemHostResolver` 一路轉手、`HostResolver` 在 `services.clients` 再匯出
  （Middle Man）：`api` 不能 import `adapters`，與 `get_bundled_services` → `bundled_services` 同一個形狀。
- Standards：同一件事有 `resolvable`（API）、`composeHosts`（前端）、`absent`（卡片）、`undeployed`（演練伺服器）幾個名字，既有的理由碼是
  `not_deployed`（Mysterious Name，判斷題）。
- Spec：「過程沒有對服務發 HTTP 請求」由「沒有造任何 client」證明；`SystemHostResolver` 本身只對 `localhost`、含空白的名字與逾時測過。
