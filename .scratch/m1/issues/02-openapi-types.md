# 02 — OpenAPI 型別產生器與 CI 過期檢查

**Status:** ready-for-agent

**Blocked by:** 無 —— 可立即開工

**讀:** plan §6（OpenAPI 段）、§11.2（T1.9 第一條）；`.scratch/m0/issues/10-health.md` 的 Comments
（「同一份形狀寫了四層」）

## 做什麼

前端不再手寫 API 的回應型別。加一個從 FastAPI 的 OpenAPI schema 產 TypeScript 型別的步驟，
把 `web/src/api/` 現有手寫的回應型別全部換成產出的型別；後端改了 response model 而沒有重新產生
型別時 CI 紅燈。

這是 **prefactor**：M1 會長出 discover / media / search / jobs / plans / events 六組端點，先接上
生成器，那批頁面才不會把「同一份形狀寫四層」再乘一次。「make the change easy, then make the
easy change.」

改動範圍橫跨現有的每一個前端 API 模組，但是機械性的，一次做完仍然綠燈。

## 驗收

- [ ] 一個指令能產出型別檔（從離線產生的 `openapi.json`，不需要跑起服務），指令寫進 README
- [ ] `web/src/api/schemas.ts` 與各 `api/*.ts` 裡手寫的回應型別全數移除，改用產出型別
- [ ] `pnpm typecheck`、`pnpm lint`、前端測試全綠，測試沒有為了配合型別來源而放寬
- [ ] 產出的型別檔是否進版控有明確決定，理由寫在票上
- [ ] CI 有一個 job 在型別檔過期時紅燈；用一次真的後端 response model 改動證明它會紅
- [ ] 後端 response model 的欄位名或可選性改變時，前端在編譯期就抓得到（附一個實例）
- [ ] `docs/progress.md` 記一行
