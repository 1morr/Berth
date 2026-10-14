# 103 — 收尾（文案）：介面登入的叫法、頁 1 字量、COMPOSE_PROFILES 只說一次、過去式的預約時間

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** 票 68 的 Comments（critique 那幾條）；票 62 的 Comments（「下一次確認在 4 秒前」）；`PRODUCT.md`、`DESIGN.md`；`CONTEXT.md`（叫法以它為準）

## 為什麼

票 68 的 `/impeccable critique` 提了三件不在那張票範圍的事；票 62 順手看到一個時間說法的錯。使用者（2026-10-14）同意收成一張。

## 做什麼

1. **「WebUI 登入」與「介面登入」兩種叫法並存**（頁 2 標題、按鈕等）：統一成一種，以 `CONTEXT.md` 的詞為準；沒有就補進去。zh-Hant 與 en 都改。
2. **頁 1「既有」卡片字太多**：照 critique 的意見刪減，關鍵資訊（會動到什麼、不會動什麼）不能丟。
3. **`COMPOSE_PROFILES` 在頁 1、2、4 各說一次**：改成只在需要的那一頁說一次，或收在一處。完成頁那一段（閒著的套件內容器）保留。
4. **作品頁「Berth 下一次確認在 4 秒前」**：`resolve_after` 已經過了、排程那一輪還沒跑到時，說成過去時間。改成「即將確認」之類的說法，不出現過去式。
5. 改完跑一次 `/impeccable critique` 看精靈分數，結論記在票的 Comments。

## 驗收

- [ ] 每一點都有 vitest 守著（zh-Hant 與 en），i18n key 成對；舊叫法在 `web/src` 搜不到
- [ ] playwright 實跑精靈頁 1、2、4 與作品頁，390 與 1280 寬各截圖；**不准碰使用者的 `berth-local`**
- [ ] critique 前後分數記在 Comments
- [ ] 全部檢查、vitest、前端 e2e 綠；progress.md 已更新
