# 15 — Skill 與 `load_skill`

**Status:** ready-for-agent

**Blocked by:** 11

**讀:** plan §11.6〈Skill〉〈provider〉（prompt 的固定前段）；brief §6.10「外部文字是資料」、§18「使用者自己寫的 skill」；CONTEXT.md 的 Skill；`docs/research/` 票 07 的 Skill 格式結論

## 為什麼

使用者要的是簡化版的 claw：助理碰到某一類事會自己去讀做法說明，而不是把所有做法都塞進 system。漸進載入讓 system 保持短而固定（快取吃得到），做法說明也能隨程式碼一起改、一起測。

## 做什麼

1. **格式**照票 07 的建議（`SKILL.md` 慣例：frontmatter 的 `name`、`description` 加 Markdown 正文）。內建 skill 隨程式碼發，放在後端套件裡、跟著 image 走；載入時驗證格式，壞掉的 skill 讓啟動或測試紅，不是默默跳過。
2. **索引進固定前段**：system 只帶每個 skill 的名字與一句說明，排在工具定義旁邊、順序固定。
3. **`load_skill`**：一個 `read` 工具（經票 06 的登錄表登記），收 skill 名字、回正文；讀進來的正文是一則工具結果，不改前段。不存在的名字回拒絕並列出有哪些。
4. **skill 只是說明，不給權限**：正文裡寫了某個命令，工具清單照舊依角色過濾；`user` 讀得到管理員的 skill 也叫不到管理員的工具（skill 是否依角色隱藏，挑一個並寫理由）。
5. **第一批內建 skill**（3–4 個，用得上 M5 已有的工具）：例如「這週入庫了什麼」、「搜一部作品缺的集並下載」；票 13、14 若已完成，加「訂閱一部作品的 RSS」「加一個索引站」。正文英文（進 prompt），寫法照 `mattpocock-skills:writing-for-agents`。
6. 回覆的語言照舊是使用者的介面語言，skill 用英文寫不影響。

## 驗收

- [ ] system 只帶 skill 索引，正文要經 `load_skill` 才出現在送出的請求裡（整合測試，假 provider 錄下請求）
- [ ] 讀了 skill 之後下一次請求的固定前段與讀之前逐字相同（pytest）
- [ ] 格式壞掉的 skill 讓測試紅（雙向變異：改壞 frontmatter 紅、改正文的字不紅）
- [ ] skill 裡提到管理員命令，`user` 照樣叫不到（整合測試）
- [ ] 實跑：問一句會用到 skill 的話，畫面上看得到「讀了哪個 skill」（playwright 截圖）
- [ ] 全部檢查、pytest、vitest 綠；plan §11.6、CONTEXT.md、progress.md 已更新
