# 10 — 確認卡（Proposal）：加索引站、刪 complete

**Status:** ready-for-agent

**Blocked by:** 09

**讀:** plan §11.6〈對話核心〉與驗收、§2；brief §6.10「外部文字是資料」⑤、§14「接管只放開可逆的」、§9.2（刪除範圍）；CONTEXT.md 的 Proposal；M4 加索引站與刪 complete 的現有流程

## 為什麼

`irreversible` 的命令 AI 永遠不能自己做，要停在一張確認卡上，人按了才執行。M6 的接管與 M7 的 Discord 按鈕都回到同一個 `proposals` 列，所以這張把 Proposal 做成獨立的東西，不是側面板的 UI 狀態。

## 做什麼

1. **`proposals` 表**與 migration：哪個工具、輸入、誰要的、出自哪則對話、AI 的理由、狀態（等待 / 已確認 / 已拒絕 / 失效），執行結果。
2. 工具迴圈遇到 `irreversible` 的工具：不執行，建一筆 Proposal，回給模型「已提出，等人確認」，前端畫確認卡。卡上講清楚**會發生什麼**（刪哪些檔、加哪個網址），不只是工具名。
3. **確認**：以按下的那個人執行，當下重驗角色與輸入（列已經不在、索引站已存在 → 失效並說原因）。**拒絕**也記下來。結果回到對話裡（模型與卡片都看得到）。
4. 登記兩個工具：加索引站、刪 complete（走既有命令，刪除範圍照 brief §9.2）。
5. 一個「降級成 Proposal」的入口：讓之後的檢查（票 11 的網址來源）能把一次可逆呼叫改成 Proposal，而不是各自造一套。

## 驗收

- [ ] 用假 provider：「加一個索引站」停在確認卡，沒按之前索引站沒加；按確認後加好（整合測試）
- [ ] 「把這部的 complete 刪掉」同上，拒絕後什麼都沒刪（整合測試）
- [ ] 確認時角色或輸入已不成立 → 失效並說原因（pytest）
- [ ] `user` 按不到管理員的 Proposal（pytest）
- [ ] 確認卡實跑（playwright 截圖）
- [ ] 全部檢查、pytest、vitest 綠；CONTEXT.md、progress.md 已更新
