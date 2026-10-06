# 53 — 文件與實作不符清單收尾

**Status:** ready-for-agent

**Blocked by:** 32、33、36、37、40（它們各自改掉表上的幾列；這張收尾，避免來回改）

**讀:** `docs/research/wizard-audit-2026-10-06.md`（「文件與實作不符」整張表、改進清單 P2-10）；brief §19「精靈審計後的八項」；`PRODUCT.md`

## 為什麼

報告列了 16 處文件或文案與實作不符。大部分由前面的票在同一個 commit 修掉，這張逐列核對，處理剩下的。

## 做什麼

1. 表上每一列對一遍：已由前面的票處理的標「已由 NN 處理」。預期的對應：
   - README:27 → 32
   - CONTEXT:110-112、README:28、brief:519、brief:123 → 33
   - README:33、`choice.existing.*`、`routes.fix.existing.qbittorrentMount`、plan §9.5 → 36
   - CONTEXT:122、頁 4 lede vs 既有卡片 → 37
   - 完成頁（重裝時） → 40
   - README:29 → 44
2. 剩下的修掉，或在 Comments 寫明不改的理由：
   - `choice.existing.adds.jellyfin` 漏說頁 1 會建 API key
   - `jellyfin.fix.configuration` 寫死繁中與台灣
   - `connection.fix.whitelist` 與預置腳本的行為不符：先實跑確認預置腳本是不是只補「不存在」的鍵，再決定改文案還是改腳本
   - 票 09 票面與票 20 衝突：在票 09 的 Comments 標「已由 20 推翻」，不改它的驗收
3. brief §3、§16.3、§16.4 頂端的「待改寫」標記，確認相關的票都完成後拿掉。

## 驗收

- [ ] 表上 16 列在 Comments 都有結論（已修／已由 NN 處理／不改＋理由）
- [ ] `connection.fix.whitelist` 的結論有實跑佐證（指令與輸出）
- [ ] 改過的文案 zh-Hant 與 en 並列（vitest）
- [ ] brief 不再有 2026-10-06 的「待改寫」標記
- [ ] 全部檢查（`pre-commit run --all-files`）、test、前端 e2e 綠燈
