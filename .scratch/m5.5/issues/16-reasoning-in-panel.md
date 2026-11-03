# 16 — 面板畫推理

**Status:** ready-for-agent

**Blocked by:** None (can start immediately)

**讀:** spec〈範圍〉「推理」的第一條；brief §20.26（Vercel 串流與 `dump_messages` 都帶 `reasoning`）；plan §7〈側面板〉；`.scratch/m5/side-panel-shape.md`

## 為什麼

模型會回推理文字（`deepseek-flash` 不送 `thinking` 也會），串流裡有 `reasoning` 片段，但面板沒畫也沒接。

## 做什麼

1. 面板把 `reasoning` 片段畫成預設收起的區塊，串流時也一樣（不在串流途中自動展開）。
2. 重新載入後仍在：`GET /agent/conversations/{id}` 要帶出推理片段。
3. Fake 後端的 `agent` 情境補一段帶推理的回應，前端 e2e 用得到。

## 驗收

- [ ] 模型回推理文字時，面板收在預設收起的區塊，展開看得到全文（e2e，桌機與 390px）
- [ ] 重新載入後還在（e2e）
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠；progress.md 已更新
