# 89 — 錯誤訊息說對原因（一）：問題、審核頁不再把 500 和 401 說成「API 沒回應」

**Status:** done

**Blocked by:** None — can start immediately

**讀:** `docs/research/simplification-audit-2026-10-13.md` 的 S2；M4 票 21（`requestProblem`、`RequestFailed` 的由來）；`web/src/components/requestProblem.ts`、`web/src/api/refusal.ts`；`PRODUCT.md`

## 為什麼

`requestProblem` / `RequestFailed` 已經會依狀態碼說：連不上、登入失效、後端出錯看 log、衝突等等。但另有約 40 處，只要拒絕原因解析不出來，就一律說「Berth 的 API 沒回應」。結果 `POST /issues/{id}/resolve` 回 500 或 401 時，畫面說的是錯的。使用者（2026-10-13）同意改文案。

審計建議分兩張做，這張先做 issues 與 review。

## 做什麼

- issues、review（含 plan、audit、rematch）裡，拒絕原因解析不出來的地方，都交給 `requestProblem` / `RequestFailed lead=…`：`lead` 說什麼事沒做成，後半句交給 `PROBLEM_TEXT`。
- 收掉因此不再用的 i18n key，包括 `issues.failed`、`review.plan.failed`、`review.audit.failed`、`rematch.failed` 這類整句相同的；zh-Hant 與 en 成對。
- 斷言整句文字的測試跟著改。

## 驗收

- [x] issues、review 範圍內，500、401、離線三種失敗各說出對的原因；vitest 守，做變異驗證
- [x] 範圍內不再有「解析不出來就說 API 沒回應」的寫法；收掉的 i18n key 沒有殘留
- [x] Playwright 實跑（用 `page.route` 造 500 與 401 即可）附截圖或文字結果；**不准碰使用者的 `berth-local`**
- [x] 全部檢查、vitest、前端 e2e 綠；CHANGELOG（Fixed）、progress.md 已更新

## Comments

- 2026-10-13 寫法（票 90 照用）：能畫元件的地方（頁級清單讀不到、`LedgerGapNotice`、`ReconcileBanner`、`PlanRow` 讀不到計劃、`WorkPicker` 搜尋）用 `RequestFailed lead=…`；只收字串的地方（`QueueRow.refusal`、`planRefusalText`、`rematchRefusalText`、`useConfirmAudits`）用新的 `problemText(t, error, lead)`（`components/requestProblem.ts`）。四個整句相同的 key 收成一個前半句 `request.notDone`；`issues.off`、`review.off`、`review.plan.off` 改名 `readFailed` 並只留前半句；`reconcile.failed`、`ledgerGap.failed` 只留前半句。測試共用 `test/fetch.ts` 的 `REQUEST_FAILURES`（500、401、離線）與 `StubRoutes`。
- 2026-10-13 變異驗證：(1) `problemText` 改成不看錯誤、一律說離線 → 範圍內 22 條紅（每個呼叫端的 500 與 401，加單元測試兩條）；(2) `IssueRow` 改回寫死的「沒有成功。＋離線那句」 → `處理一件` 的 500、401 紅，離線照綠（符合預期）。都已還原。
- 2026-10-13 Playwright 實跑（`fake_setup_server.py` 的 issues、review 情境，8590 / 8591，沒碰 `berth-local`）：`page.route` 造 500 / 401 / 斷線。忽略一件 500 →「沒有成功。 Berth 的後端出錯了。再試一次；還是不行的話看 berth 容器的 log。」，401 →「沒有成功。 登入已失效：重新登入 Berth，再試一次。」；立刻對帳 500 →「對帳沒有開始。 Berth 的後端出錯了…」；審核核准 500 / 401 同上；審核佇列 500 →「讀不到審核佇列。 Berth 的後端出錯了…」，斷線 →「讀不到審核佇列。 Berth 的後端沒有回應：它可能沒在跑，或網路斷了…」。
- 2026-10-13 code-review 已處理：四個測試檔各抄一份 `render` 路由型別 → `StubRoutes`；Spec 軸指出 `WorkPicker` 搜尋失敗什麼都不說、`PlanRow` 讀不到計劃不說原因 → 兩處改用 `RequestFailed`（附 500 / 401 / 離線測試）；CHANGELOG 說「作品頁還是舊說法」不準（`RematchForm` 是共用的）→ 改寫。
- 2026-10-13 code-review 未處理：(1) 只收字串的那幾處 401 時只有文字、沒有 `RequestFailed` 的「前往登入」與技術細節：401 本來就會讓路由守衛重跑（`router.ts`），session 真的失效時直接被送去登入頁，按鈕多半用不到；要畫按鈕得把 `QueueRow.refusal` 改成 ReactNode，超出本票。(2) `problemText(t, error, t('request.notDone'))` 出現五次、`planRefusalText` 與 `rematchRefusalText` 形狀幾乎相同、`LedgerGapNotice` 與 `ReconcileBanner` 的「拒絕或 `RequestFailed`」分支相同：判斷題，現在各自短而清楚，不抽。(3) `RequestFailed` 先分類一次判斷要不要給登入鍵，`problemText` 裡又分類一次：成本可忽略。(4) web 端「`api/` 不 import `components/`」沒有 lint 守著（`rematchRefusalText` 因此搬家）：是現況慣例，加閘門另議。
