# 07 — AI 活動頁、審核頁附理由、週報

**Status:** ready-for-agent

**Blocked by:** 05

**讀:** spec〈範圍〉〈AI 活動頁與理由〉、〈共同規則〉；brief §14〈可追溯、可撤銷〉；plan §6、§7〈路由〉〈元件〉；`CONTEXT.md`〈AI Activity〉〈Weekly Report〉；`services/commands.py`（inverse 的三種寫法）；`PRODUCT.md`、`DESIGN.md`

## 為什麼

使用者不逐件看 AI 做的事，所以出錯時要找得到、撤得回來。可撤銷是 AI 自己動手的前提（ADR 0008）。

## 做什麼

1. 走 `/impeccable`：新頁先 `shape`。
2. **AI 活動頁**（admin）：AI 做了什麼（命令、對象）、理由、花費、結論（已套用／交給人／沒通過驗證），逐筆撤銷——照登錄表的反向命令經執行器做，沒有反向命令的不給按鈕。讀取端點與撤銷命令都標 `@command`。
3. **審核頁**：AI 交回人的每一件附 AI 的理由（`ReasonCode` 的文案加自由文字）。
4. **週報**：多列 AI 這週做了幾件、交回人幾件（存下來的週報，舊的不變）。
5. 導覽入口放哪照 `DESIGN.md`〈Navigation〉定，寫進 Comments。
6. 文件：plan §6（新端點）、§7（新路由）、`CONTEXT.md`。

## 驗收

- [ ] 第 05 張的任務套用之後，活動頁列得出來、撤銷得回來（Plan 回審核）（整合測試與 e2e）
- [ ] 審核頁看得到 AI 的理由（vitest）
- [ ] 週報有 AI 這週的兩個數（整合測試）
- [ ] playwright 實跑，桌機與 390px，附截圖
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠

## Comments
