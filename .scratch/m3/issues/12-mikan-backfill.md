# 12 — Mikan 補舊集 + 每日補漏

**Status:** done

**Blocked by:** 08（綁定命令）、10（帳本已有的跳過）

**讀:** plan §2.4（`backfilled_at`）、§3.2（新迴圈或排程怎麼放）、§11.4；brief §15（「補舊集」）；`docs/research/rss-sources.md`（Mikan 單一 feed）

## 做什麼

聚合 feed 只有最近的集數，所以中途訂閱的作品要靠這一票補齊舊集。

- **綁定時補舊集**：Mikan 的 RSS Series 綁定當下，用它的單一 feed（`/RSS/Bangumi?bangumiId=&subgroupid=`）列出整季，**預設勾選補下載**（使用者 2026-09-24 拍板）。帳本已有、或已有 Job 的集數跳過。人工綁定時畫面讓人取消勾選；自動綁定（票 09）照預設全補。寫 `backfilled_at`。
- **每日補漏**：每天用同一個單一 feed 對每個已綁定的 Mikan RSS Series 補一次，接住 Berth 停機期間被聚合 feed 捲掉的集數。排程放哪、幾點跑照 §3.2 的形狀決定，寫進 plan。請求量先照固定節奏，預算在票 20 統一。

補下載與一般 RSS 送單走同一條路（排除、去重、`trigger = rss`），不另開一條。

## 驗收

- [x] 綁定一部中途訂閱的作品 → 單一 feed 裡帳本沒有的集數全部送單、已有的跳過（整合測試，對應 M3 驗收第二條前半）
- [x] 人工綁定時取消勾選 → 不補
- [x] 模擬停機：聚合 feed 捲掉一集 → 每日補漏一輪之後那一集有 Job（整合測試）
- [x] 補下載的 item 照樣經過排除條件（合集不因為補舊集而被送）
- [x] plan §3.2 寫明每日補漏的排程
- [x] lint、type、test 綠燈

## Comments

- 2026-09-25 實作（`/implement`）。補下來的寫成 RSS Series 的 **home Feed**（最早帶到它、還在的 Mikan Feed）的 Item：`(feed_id, guid)` 去重、三層排除、`_submit_waiting` 全部沿用，沒有第二條送單的路。每日補漏在 `rss_poller` 輪到 home Feed 時做，每個 Series 以 `backfilled_at` 滾動一天（plan §3.2 寫了為什麼不用固定鐘點）。
- 取消勾選記在 RSS Series 的 `passed_before`（綁定那一刻），不是記在那幾筆 Item 上：code-review Spec 軸抓到 Item 跟著 Feed 刪掉、同一個 Series 換到另一個 Feed 補漏時會把略過的集數送出去（紅 → 綠三條：第二個 Feed、刪掉 Feed 後綁、解綁後勾著重綁）。因此初版的「取消勾選而讀不到單一 feed 就 502」刪掉。
- migration `e8a3d6c1f59b` 把既有已綁定的 Mikan Series 的 `passed_before` 補成 `created_at`：升級那一刻不替沒被問過的送出整季（Spec 軸 (b)）；`test_database.py` 守著（變異轉紅）。
- playwright：`rss-backfill` / `rss-backfill-390` 預設全補，綁定後 `/jobs` 12 筆、全部入庫；`rss`、`rss-exclusions` 走取消勾選那一條（原本的斷言不變）。390 寬勾選框、說明與確認鍵「綁定、送出 2 集並補舊集」都在、無溢出。
- code-review Standards 軸：CONTEXT.md 補「補舊集 / 每日補漏 / 單一 feed」並擴充 `passed` 定義（硬違規，已修）；讀單一 feed 的兩份失敗處理收成 `_backfill`；`_record` 的 `passed` 旗標拿掉；Mikan 判斷補上字幕組 id；migration 日期；前端 `mikan && backfill` 收成一個值。
- 沒處理、記下：
  - **`_record` 仍有 `known=` 一個模式參數**（Standards 判斷題）：拆成兩支會重複整段寫 Item 的程式，暫留。
  - **補漏的失敗與輪詢的失敗拼在同一個 `last_error` 字串**：畫面上只顯示原文，沒有讀者要分開；要分時（M4 通知）再拆欄。
  - **綁過的 Series 季末之後仍每天讀一次單一 feed**：請求量隨綁過的部數線性長，預算在票 20 統一。
  - **使用者自己把單一 feed 加成 Feed**：那個 Feed 走一般輪詢，`passed_before` 不作用在它身上（只作用在補舊集讀到的）；同一集在兩個 Feed 下各一筆，後到的是重複。
