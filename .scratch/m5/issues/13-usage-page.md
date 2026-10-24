# 13 — 用量頁

**Status:** ready-for-agent

**Blocked by:** 07

**讀:** plan §11.6〈用量記錄〉；brief §6.10「用量，不設預算」、§13；CONTEXT.md 的 AI Call；`DESIGN.md`；`dataviz` 的作圖規則

## 為什麼

使用者不設預算，但要看得到 token 消耗與快取命中率（brief §19 2026-10-24）。這一頁只讀 `ai_calls`。

## 做什麼

1. 先 `/impeccable shape`，輸出 `.scratch/m5/usage-page-shape.md`。
2. API：依日期與出處（對話、測試，M6 起加 AI 任務）彙總 `ai_calls`：輸入、輸出、快取寫入、快取讀取 tokens，呼叫數，快取命中率（讀取 ÷ 全部輸入，輸入含快取寫入與讀取）。
3. 頁面：期間切換、依日期的趨勢、依出處的明細、命中率。只給管理員看（看得到每個人的用量）。
4. 沒有任何呼叫時的空狀態講清楚怎麼開始。

## 驗收

- [ ] 彙總與命中率算對，含零除（pytest）
- [ ] `user` 拿不到這支 API（pytest）
- [ ] 頁面實跑，有資料與空狀態各一張截圖（playwright）
- [ ] 全部檢查、pytest、vitest 綠；DESIGN.md、progress.md 已更新
