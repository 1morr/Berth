# 22 — M5 UI 收尾

**Status:** ready-for-agent

**Blocked by:** 09, 12, 13, 14, 16, 17, 18, 19, 20, 21

**讀:** CLAUDE.md〈UI〉；`PRODUCT.md`、`DESIGN.md`；M4 票 132（上一次收尾的做法）；票 12–21 的 Comments 裡留給收尾的 UI 項

## 為什麼

每個里程碑的 UI 收尾前，都要跑 critique、audit、polish。M5 新增的面：側面板、確認卡、設定頁的 AI 分頁、用量頁、步驟頁。

## 做什麼

1. 依序跑 `/impeccable critique` → `audit` → `polish`。範圍是上面五個面，每個面都看深淺色、1280 與 390 寬度、鍵盤操作。
2. 票 12–21 的 Comments 裡標了「收尾」的 UI 項逐條處理或歸類。
3. 決定 Media 詳情頁要不要露出票 10 的「為什麼沒入庫」：只有使用者會在那裡找答案才露出。
4. 設計系統有變就 `/impeccable document` 更新 `DESIGN.md`。
5. **票 20 搬過來的（收尾）**：側面板的兩塊 UI：斷路器開與關的狀態（讀 `GET /agent/status` 的 `paused_until`，一般使用者也看得到；管理員另有 `pause_error` 說是什麼錯）、防護停下時的「繼續」（`data-stop` 或對話的 `stop` 裡 `continuable` 是真才畫；按下去送一則按鈕上的字、body 帶 `continues: <turn_id>`；`not_continuable` 時收掉按鈕）。票 20 做的時候側面板（票 12）還沒有，後端與測試在票 20（2026-10-27 使用者決定）。

## 驗收

- [ ] critique / audit / polish 的分數與處理清單記在 Comments
- [ ] 五個面 × 深淺 × 兩種寬度沒有橫向捲動，對比達標（實跑）
- [ ] 斷路器開與關的狀態在側面板看得到；「繼續」只出現在可以續的那一則、按過一次就沒了（playwright 實跑，從票 20 搬來）
- [ ] 全部檢查、vitest 綠；DESIGN.md、progress.md 已更新

## Comments
