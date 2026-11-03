# 03 — 搜尋結果

**Status:** ready-for-agent

**Blocked by:** None (can start immediately)

**讀:** spec〈範圍〉「搜尋結果」；brief §20.26（`encrypted_content` 的量）；plan §7〈側面板〉；`docs/research/assistant-feedback-2026-11-01.md`

## 為什麼

`web_search` 每筆結果帶的 `encrypted_content` 只給服務端重播用，一次 10 筆就有兩三萬字，現在原樣印在面板上。

## 做什麼

1. 串流（`_relay`）與 `GET /agent/conversations/{id}` 兩條路都在 API 層拿掉 `encrypted_content`；`history_json` 不動，下一輪模型呼叫要用。
2. 面板的工具呼叫把 `web_search` 的結果畫成清單：標題、網址、`page_age`。其他工具照舊。
3. Fake 後端的 `agent` 情境補一段 `web_search` 回應，前端 e2e 用得到。

## 驗收

- [ ] 展開 `web_search` 看到標題、網址與日期（playwright 實跑，桌機與 390px）
- [ ] 串流和重新載入的回應裡都沒有 `encrypted_content`（測試）
- [ ] 下一輪模型呼叫的歷史仍帶 `encrypted_content`（測試）
- [ ] 全部檢查、pytest、vitest 綠；progress.md 已更新
