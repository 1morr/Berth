# 02a — `setup/*` 的拒絕進文件、進畫面，並補上閘門

**Status:** ready-for-agent

**Blocked by:** 無 —— 可立即開工（票 02 已 done，這一票補它漏掉的兩支端點）

**讀:** plan §6（OpenAPI 那一條、routes 與 setup 兩個群組）、§9.5（精靈第 7 步）、§7（前端那一節）；
`.scratch/m2/issues/02-refusal-types-openapi.md` 的 `## Comments`（閘門為什麼沒做成）、
`.scratch/m2/issues/01-backend-loose-ends.md`（`route_missing` 為什麼會出現在 `POST /setup/routes`）

## 這一票為什麼存在

票 01、02、03 是並行做的。票 02 把拒絕理由收成 enum、替每個 router 補上 `responses=`，
讓前端的封閉集合改由 OpenAPI 產出；但它掃 api 模組的時候 `berth/api/setup.py` 裡還沒有任何
`route_refusal(`——`POST /setup/routes` 的那一行是票 01 在另一條分支上同時加的。合併之後留下三個缺口，
彼此是同一條拒絕的不同段落。

## 做什麼

1. **`api/setup.py` 的兩支 Route 命令宣告 `responses=`**。
   - `POST /setup/routes`：這一步順帶重跑既有 Route 的檢查，途中被刪掉的那一條是 404 `route_missing`（票 01）。
   - `DELETE /setup/routes/{route_id}`：404 `route_missing` + 409 `route_in_use`（票 14a 定的）。
   - **各自給一張小表**（`refusal_responses(RouteRefusalOut, {...})`），不要直接沿用 `api/routes.py` 的
     `REFUSAL_RESPONSES`——那支表是 `routes/*` 五支端點的聯集，套過來就是過度宣告，
     而 `refusal_responses` 的 docstring 寫明「收的是端點真的會回的那幾種」。
2. **補「會拒絕就要宣告」的閘門**。票 02 試過數原始碼裡 `raise x_refusal(` 與 `responses=` 各出現幾次，
   `PLAYED_RESPONSES` 這種先存成常數再用的寫法數不到，放寬到數得到就等於沒在守東西，所以拿掉了
   （票 02 Comments）。**這一票要做成由構造或由文件保證的版本**，例如：走訪 `create_app()` 的每一條路由，
   對照它的 handler 實際接得住哪幾個 refusal 例外（`__wrapped__` / `inspect` 取得 except 的例外 tuple，
   權限閘門那一組已經是這個形狀），handler 接得住而 OpenAPI 的 `responses` 沒列就紅。
   做不到就**在票的 Comments 寫清楚試了什麼、為什麼不成**，並把 plan §6 那一句改成沒有閘門的說法——
   不要留一條靠運氣被遵守的規則（全域 CLAUDE.md「規則要有閘門」）。
3. **精靈第 7 步畫得出拒絕**。`web/src/pages/SetupPage.tsx` 的 build mutation 現在只傳
   `requestFailed={build.isError}`，所以票 01 新加的 404 `route_missing` 到畫面上是一句通用失敗，
   沒有原因也沒有下一步（違反 PRODUCT 原則 4）。改成走 `routeRefusalOf`，與
   `RouteSettingsPage.tsx:217`、`AddRoute.tsx:103`、`RouteDelete.tsx:57` 同一個形狀。
   `route_missing` 的下一步是「那條 Route 已經被刪掉了，重新整理這一步」。

順手（同一個檔案、同一個主題，做不做都可以，不做就記進 Comments）：
`web/src/api/schemas.ts` 的 `ROUTE_CHECKS` 仍是手寫的字面聯集，而 `RouteCheck` 在
`berth/domain/enums.py` 已經是 enum——它進不了 OpenAPI 是因為 `StepOut.step` 宣告成 `str`
（`api/schemas.py`）。同一類問題、同一種解法（把 `step` 收緊成聯集型別）；票 02 沒動是因為它不是拒絕理由。

## 驗收

- [ ] `api/setup.py` 兩支端點的 OpenAPI `responses` 各自只列它真的會回的那幾種（404 / 404+409），
      不是 `routes/*` 的聯集；`pnpm gen:api` 重跑後 `git diff --exit-code -- web/src/api/schema.d.ts` 乾淨
- [ ] 有一條閘門：把任何一支的 `responses=` 拿掉會紅。**雙向變異驗證寫在測試檔內**——
      造一個違規證明它會紅，改一次無關的格式或命名證明它不會紅（全域 CLAUDE.md）
- [ ] 上一條做不到時，票的 Comments 寫明試了什麼、為什麼不成，且 plan §6 的說法同輪改掉
- [ ] 精靈第 7 步遇到 404 `route_missing` 時畫面說得出原因與下一步（vitest 斷言訊息內容，不是斷言有沒有 class）
- [ ] 既有的三個 `SetupPage.*.test.tsx` 沒有因此改壞（它們沒有把 `requestFailed` 釘成斷言，所以不該需要改）
- [ ] playwright 實跑一次精靈第 7 步的拒絕畫面，附截圖或文字結果
- [ ] plan §6 那一句的「`setup/*` 還沒宣告」註記隨這一票拿掉；票 02 Comments 的補記同輪更新
- [ ] lint、type、test 綠燈（貼指令輸出）

## Comments
