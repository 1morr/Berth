# 89 — 錯誤訊息說對原因（一）：問題、審核頁不再把 500 和 401 說成「API 沒回應」

**Status:** ready-for-agent

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

- [ ] issues、review 範圍內，500、401、離線三種失敗各說出對的原因；vitest 守，做變異驗證
- [ ] 範圍內不再有「解析不出來就說 API 沒回應」的寫法；收掉的 i18n key 沒有殘留
- [ ] Playwright 實跑（用 `page.route` 造 500 與 401 即可）附截圖或文字結果；**不准碰使用者的 `berth-local`**
- [ ] 全部檢查、vitest、前端 e2e 綠；CHANGELOG（Fixed）、progress.md 已更新
