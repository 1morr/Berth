# 45 — 只存驗過的憑證、錯誤標在欄位上

**Status:** ready-for-agent

**Blocked by:** 39（頁 4 用上共用表單之後，欄位錯誤一次改三頁）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（S1 頁 5「錯的 key 也被存下」、§E 共同慣例 2 與 5、「Berth 精靈哪裡不統一」第 6、7 條、簡化方案 E-6、改進清單 P2-3）；票 21、25、31；brief §16.3；plan §9.3

## 為什麼（2026-10-06 審計）

- 錯的 TMDB key 照樣存下，右欄寫「已存下，沒通過驗證」。Home Assistant 是驗過才 `create_entry`。
- 錯誤都是頁面層級的橫幅加手動步驟，不標在欄位上（只有頁 1 的帳號規則例外）。Sonarr 與 Home Assistant 都會把錯誤標到欄位：位址錯標位址，帳密錯標帳密。

## 做什麼

1. TMDB 與既有服務的憑證改成測過才存。`GET /setup/tmdb` 的回應語意會變，欄位可以保留，但「已存下，沒通過驗證」這個狀態要消失。記進 CHANGELOG。
2. 連線錯誤分兩類，標在各自的欄位旁：
   - 位址類：`unreachable`、`scheme_*`、`protocol_mismatch`、localhost
   - 憑證類：`auth_required`、`ip_banned`、API key 錯

   其餘的留在頁面層級。人話、手動步驟、技術細節的分層照票 21 / 25 保留。

## 驗收

- [ ] 整合測試（雙向）：錯的 TMDB key 不存、對的才存；既有服務的憑證同一條
- [ ] vitest：位址錯時錯誤標在位址欄、帳密錯時標在帳密欄（頁 1、2、4 三頁同一個元件）；`aria-describedby` 指到錯誤
- [ ] playwright 實跑三種錯誤，附截圖
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈
