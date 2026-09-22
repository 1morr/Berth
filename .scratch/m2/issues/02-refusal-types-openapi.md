# 02 — 拒絕理由改由 OpenAPI 產

**Status:** ready-for-agent

**Blocked by:** 無 —— 可立即開工

**讀:** plan §6（門禁那三段、底下 OpenAPI 那兩條）、§7（資料那一段）、§11.2 的 T1.9；§11.3（票 01 那一列的後半）

## 做什麼

前端有**三組手抄的拒絕理由**與一組手抄的事件形狀，後端改了封閉集合它們不會紅：

- `web/src/api/jobs.ts` 的 `JobRefusal`
- `web/src/api/jellyfin.ts` 的 `AccessRefusal`
- `web/src/api/routes.ts` 的 `RouteRefusal`
- `web/src/api/events.ts` 的 `JobSignal`

M1 票 02 已經立了閘門（`pnpm gen:api` + CI 的 `git diff --exit-code -- src/api/schema.d.ts`），
但這四組沒走它——後端的拒絕理由不是 pydantic model，FastAPI 產的 OpenAPI 裡沒有它們，
`openapi-typescript` 自然產不出來。這一票把它們變成 model 並讓前端改用產出的型別。

M2 每一張票都會新增拒絕理由（`reconcile_running`、刪除旗標的拒絕、review 的拒絕…），先做這件
是因為之後每一張票都會再抄一次。

順手：`web/vite.config.ts` 設 `testTimeout` / `asyncUtilTimeout`——本機全量跑會固定有兩條
`findBy*` 逾時，那是預設值太緊而不是測試的問題。

## 驗收

- [ ] 四組型別都從 `src/api/schema.d.ts` 來，`web/src/` 底下沒有手寫的拒絕理由字面量聯集
      （以 grep 佐證）
- [ ] 後端改一個拒絕理由而不重跑 `pnpm gen:api` 時 CI 會紅（在票裡示範這一次變異：改一個、
      看 `git diff --exit-code` 紅、再跑產生器變綠）
- [ ] 改一次無關的格式或命名不會讓那道檢查紅（雙向變異的第二項）
- [ ] `vite.config.ts` 的兩個 timeout 有值，本機全量跑不再有 `findBy*` 逾時（貼輸出）
- [ ] lint、type、test 綠燈（前後端都貼）

## Comments
