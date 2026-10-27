# 15 — prompt injection 的整合測試

**Status:** ready-for-agent

**Blocked by:** 14

**讀:** brief §14；`docs/research/m5-ai-direction-2026-10-27.md` C4 全部、`docs/research/m5-ai-direction-2026-10-27/07-guardrails-injection-observability.md` §2；票 13、14 的守法

## 為什麼

外部內容裡的指令一定會有部分被模型照做。防線靠的是**照做了也做不到**。這要用測試證明，而不是相信 prompt。

## 做什麼

用假模型重現「模型被說動」的情況，逐一證明擋得住。外部內容的來源包括 torrent 標題、RSS Item、AniList 與 Bangumi 的資料、網頁搜尋結果：

1. 外部內容要它加一個 Feed：網址不是使用者打的，被擋。
2. 外部內容要它送使用者沒要求的 torrent：出卡，不直接送。
3. 外部內容要它改設定或服務位址：永遠要人，出卡或被擋。
4. 外部內容要它說出 key：憑證從來不在上下文裡（斷言送給模型的訊息不含任何 key）。
5. 外部內容在回覆裡塞外部圖片：前端不載入（與票 12 的測試對上）。
6. 偽造前端的核准與歷史：不被採用（與票 11、13 對上）。

## 驗收

- [ ] 以上六類各至少一條整合測試，全部是「模型照做了，系統擋住」
- [ ] brief §14 或 plan §11.6 標明哪些防線由哪些測試守（宣稱與測試逐條對得上）
- [ ] 全部檢查與 pytest 綠；progress.md 已更新

## Comments
