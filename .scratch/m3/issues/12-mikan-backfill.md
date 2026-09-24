# 12 — Mikan 補舊集 + 每日補漏

**Status:** ready-for-agent

**Blocked by:** 08（綁定命令）、10（帳本已有的跳過）

**讀:** plan §2.4（`backfilled_at`）、§3.2（新迴圈或排程怎麼放）、§11.4；brief §15（「補舊集」）；`docs/research/rss-sources.md`（Mikan 單一 feed）

## 做什麼

聚合 feed 只有最近的集數，所以中途訂閱的作品要靠這一票補齊舊集。

- **綁定時補舊集**：Mikan 的 RSS Series 綁定當下，用它的單一 feed（`/RSS/Bangumi?bangumiId=&subgroupid=`）列出整季，**預設勾選補下載**（使用者 2026-09-24 拍板）。帳本已有、或已有 Job 的集數跳過。人工綁定時畫面讓人取消勾選；自動綁定（票 09）照預設全補。寫 `backfilled_at`。
- **每日補漏**：每天用同一個單一 feed 對每個已綁定的 Mikan RSS Series 補一次，接住 Berth 停機期間被聚合 feed 捲掉的集數。排程放哪、幾點跑照 §3.2 的形狀決定，寫進 plan。請求量先照固定節奏，預算在票 20 統一。

補下載與一般 RSS 送單走同一條路（排除、去重、`trigger = rss`），不另開一條。

## 驗收

- [ ] 綁定一部中途訂閱的作品 → 單一 feed 裡帳本沒有的集數全部送單、已有的跳過（整合測試，對應 M3 驗收第二條前半）
- [ ] 人工綁定時取消勾選 → 不補
- [ ] 模擬停機：聚合 feed 捲掉一集 → 每日補漏一輪之後那一集有 Job（整合測試）
- [ ] 補下載的 item 照樣經過排除條件（合集不因為補舊集而被送）
- [ ] plan §3.2 寫明每日補漏的排程
- [ ] lint、type、test 綠燈
