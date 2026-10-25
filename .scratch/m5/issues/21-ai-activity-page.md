# 21 — AI 活動頁

**Status:** ready-for-agent

**Blocked by:** 12、14

**讀:** plan §11.6〈AI 活動頁〉；brief §6.10「外部文字是資料」⑤、§14；CONTEXT.md 的 AI Activity；票 06 定下的 actor 格式；參考 `backup/m5-attempt-1-20261024` 的 `d439215`

## 為什麼

AI 做過的每一個寫入都要有地方看、能撤銷，這是可逆動作直接執行的前提。M6 的背景接管也寫到同一頁。

## 做什麼

1. 先 `/impeccable shape`，輸出 `.scratch/m5/ai-activity-shape.md`。
2. 列出 AI 執行過的每一個寫入命令與確認過的 Proposal：何時、代誰、哪個工具、輸入摘要、AI 給的理由、這一輪的 tokens、出自哪則對話（連得回去）。資料從票 06 的 actor 撈，不另寫一份日誌；撈不出來就回頭補 actor，而不是新開表。
3. 逐筆撤銷：與票 16 的 `/undo` 走同一條撤銷路；有反向命令的按得到，已經撤銷過的或沒有反向命令的說明為什麼不行。
4. 管理員看全部，`user` 只看自己對話裡的。

## 驗收

- [ ] 票 12、13、14 的寫入都出現在這頁，撤銷後狀態正確（整合測試）
- [ ] `user` 看不到別人的（pytest）
- [ ] 實跑截圖（playwright）
- [ ] 全部檢查、pytest、vitest 綠；DESIGN.md、progress.md 已更新
