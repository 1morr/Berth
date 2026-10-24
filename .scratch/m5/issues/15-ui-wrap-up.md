# 15 — M5 UI 收尾

**Status:** ready-for-agent

**Blocked by:** 10、11、12、13、14

**讀:** CLAUDE.md〈UI〉；`DESIGN.md`、`PRODUCT.md`；`.scratch/m5/` 的各份 shape

## 為什麼

CLAUDE.md：每個里程碑 UI 收尾前跑 `critique`、`audit`、`polish`。M5 新增的側面板、四種結果卡、確認卡、設定的 AI 一格、用量頁、AI 活動頁一起過一遍。

## 做什麼

1. `/impeccable critique`、`audit`（含無障礙、鍵盤操作、窄螢幕下的側面板）、`polish`。
2. 修掉發現的問題；不修的寫進 Comments 並說理由。
3. `DESIGN.md` 同步（`/impeccable document` 若有新的設計系統元件）。

## 驗收

- [ ] 三個步驟的發現都處理或記錄
- [ ] 窄螢幕與鍵盤操作實跑（playwright 截圖）
- [ ] 全部檢查、pytest、vitest 綠；DESIGN.md、progress.md 已更新
