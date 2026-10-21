# 130 — RSS 的巡檢：缺集、同一集多份、一直失敗的 Feed

**Status:** ready-for-agent

**Blocked by:** 129

**讀:** plan §11.5〈巡檢〉與〈M3 收尾帶過來的兩條〉；brief §7.7（多版本並存）、§7.8（重複版本）、§15；M3 票 12 的 Comments（`last_error` 拆欄）；`berth/models/rss.py`；`berth/services/rss.py` 寫 `last_error` 的幾處（輪詢約 :916、:928，補漏約 :1208）；`/rss` 頁 Feed 列顯示錯誤的元件

## 為什麼

播出日比對與片長驗證漏掉的、Feed 默默壞掉的，都要有人在事後抓到。「一直失敗的 Feed」要分得出是輪詢還是補漏壞了，但兩者現在擠在同一個 `last_error`（M3 票 12）。

## 做什麼

1. **拆欄**：`rss_feeds` 的錯誤拆成輪詢與補漏兩欄（migration 把舊值搬到輪詢那欄），API 與 `/rss` 的 Feed 列分開說。
2. **一直失敗的 Feed**：輪詢或補漏連續失敗超過 24 小時，開一件 Issue，說出是哪一種、最後的原因；恢復後由系統收掉。
3. **RSS Series 缺集**：已入庫的集數之間有洞，而且洞比最新一集早超過 7 天（給字幕組晚發的時間），開一件 Issue 列出缺哪幾集，動作是到作品頁搜那幾集。
4. **同一集意外多份**：定義照 brief §7.7、§7.8——版本並存是允許的，**開工前把「意外」的判準寫進 Comments 給協調者確認再實作**。
5. 都接上票 129 的迴圈；新的 Issue 會經票 127 算進「等你處理」。

## 驗收

- [ ] 拆欄 migration：舊的錯誤搬到輪詢那欄；輪詢與補漏失敗分開寫、分開顯示（pytest＋vitest）
- [ ] 連續失敗超過 24 小時開 Issue、恢復後收掉；未滿 24 小時不開（pytest）
- [ ] 缺集：洞比最新一集早 7 天以上才開，列出集數（pytest）
- [ ] 同一集多份：照協調者確認的判準，版本並存不誤報（pytest）
- [ ] 全部檢查、pytest、vitest 綠；plan §11.5 那一條標做完；CHANGELOG（含 migration 說明）、progress.md 已更新
