# 90 — 錯誤訊息說對原因（二）：工作、RSS、作品頁

**Status:** ready-for-agent

**Blocked by:** 89（照它定下的寫法延伸，也避免兩張同時改 i18n 檔）

**讀:** 票 89 與它的 Comments；`docs/research/simplification-audit-2026-10-13.md` 的 S2

## 為什麼

同票 89：拒絕原因解析不出來時一律說「API 沒回應」，對 500、401 說錯。這張把 89 的做法延伸到剩下的範圍。

## 做什麼

- 照票 89 的寫法，改 jobs、rss、media（含 `api/files.ts`），以及其他還留著「解析不出來就說 API 沒回應」寫法的地方。做完時 `web/src` 不應該再有這種寫法。
- 收掉因此不再用的 i18n key（zh-Hant 與 en 成對）；斷言整句文字的測試跟著改。

## 驗收

- [ ] 範圍內 500、401、離線三種失敗各說出對的原因；vitest 守，做變異驗證
- [ ] 全 `web/src` 搜不到「API 沒回應」當作通用錯誤的退路；兩種尾巴（`Berth’s own API did not answer…`、`The Berth backend may be down…`）只留在真的是連不上的情況
- [ ] Playwright 實跑附截圖或文字結果；**不准碰使用者的 `berth-local`**
- [ ] 全部檢查、vitest、前端 e2e 綠；CHANGELOG、progress.md 已更新
