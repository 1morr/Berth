# 11 — M6 UI 收尾

**Status:** ready-for-agent

**Blocked by:** 03、07、08、09、10

**讀:** spec〈共同規則〉；`AGENTS.md`〈UI〉；`PRODUCT.md`、`DESIGN.md`；`.scratch/m5.6/issues/10-m5.6-ui-wrap-up.md`（上一次收尾的做法）

## 為什麼

`AGENTS.md`〈UI〉：每個里程碑 UI 收尾前跑 `critique`、`audit`、`polish`。M6 動到的畫面有確認卡、Issue 頁、AI 設定頁的開關、AI 活動頁、審核頁的 AI 理由、週報。

## 做什麼

1. `/impeccable critique`、`audit`、`polish` 走過上面每個畫面，桌機與 390px。
2. 修掉的與沒修的分開記進 Comments（沒修的寫原因）；`DESIGN.md` 跟著改。
3. M5.6 側面板拖寬沒在觸控裝置驗過（M5.6 票 10b audit）：playwright 開觸控模擬（`hasTouch`）實跑拖寬與 390px 不畫把手，結果記進 Comments（2026-11-12 M5.6 回顧）。
4. 關掉 AI 時：AI 活動頁、開關、理由的空狀態說得清楚，不留壞掉的入口。

## 驗收

- [ ] critique、audit、polish 的結論與修正在 Comments
- [ ] playwright 實跑每個畫面，桌機與 390px，附截圖或文字結果
- [ ] 側面板拖寬在觸控模擬下實跑過，結果在 Comments
- [ ] 關掉 AI 的前端 e2e 綠
- [ ] 全部檢查、vitest、前端 e2e 綠

## Comments
