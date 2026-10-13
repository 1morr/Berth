# 99 — 前端收尾：三處錯誤訊息一律怪外部服務；審核頁的區塊標題

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** 票 90 的 Comments〈code-review 未處理〉(1)；票 92 的 Comments（`ReviewPage.tsx` 那一條）；`web/src/components/requestProblem.ts`、`web/src/components/SectionHeading.tsx`；`DESIGN.md`

## 為什麼

票 90、92 收尾時各留下一件，使用者（2026-10-13）同意一起做。

## 做什麼

1. **三處錯誤訊息**：
   - 設定精靈的 `indexer.remove.failed` 一律說「Prowlarr 可能正在重啟」。
   - `routes.rereadFailed` 一律說「讀不到 Jellyfin 現在的媒體庫」。

   這兩句不管錯誤是什麼都怪外部服務。另外，媒體庫的 `inventory.narrow.failed` 不說原因。

   先查後端在 Prowlarr、Jellyfin 問不到時回什麼（狀態碼與 `detail`），再分開說：外部服務的問題照後端給的理由說，Berth 自己的請求沒成時照 `requestProblem` 說。
2. **審核頁的區塊標題**（`ReviewPage.tsx` 那一份手寫版）：改用 `SectionHeading`，讓票 92 的閘門也守得到它。
   - 票 92 提過：改了之後 `h2` 的可存取名稱會變短（計數移出 `h2`）。這是 `SectionHeading` 全站一致的寫法，照它走。
   - 標題列右側的按鈕走 `extra`。

## 驗收

- [ ] 三處在 500、401、離線，以及外部服務問不到時，各說出對的原因；vitest 守，做變異驗證
- [ ] 審核頁的區塊標題是 `SectionHeading`；票 92 的閘門改成也認得它（造一份手寫的會紅）
- [ ] Playwright 實跑附截圖或文字結果；**不准碰使用者的 `berth-local`**
- [ ] i18n zh-Hant 與 en 成對；全部檢查、vitest、前端 e2e 綠；CHANGELOG、progress.md 已更新
