# 18 — 一次性 RSS 連結

**Status:** ready-for-agent

**Blocked by:** 11（三種來源的 adapter 都在）

**讀:** plan §6（`rss/oneshot`）、§11.4；brief §15（「一次性 RSS 連結」、合集那一句）

## 做什麼

貼上一條 RSS 網址 → 解析全部 item → 勾選 → 送單，**不建立 Feed**、不長 RSS Series（brief §15）。

- 來源類型從網址認（Mikan / Nyaa / acg.rip），認不出的回清楚的錯誤；generic 不在這一票。
- 每一筆顯示解析結果（季集、tags、`release_kind`）與「帳本已經有了」。
- **合集在這裡可以手動送**：排除條件的預設只作用在自動下載，這裡只標示、不擋。
- 送單時要選作品與 Route，一次勾選的同一批共用。走一般的 `add_download`（`trigger = manual`、帶作品上下文），不是 RSS 的路。
- 放在 `/rss` 頁上的一個區塊，不另開頁。

## 驗收

- [ ] 貼 Mikan 單一 feed 的網址 → 列出整季 → 勾三集 → 三筆 Job（整合測試，用 fixture 當替身）
- [ ] 合集可以勾選並送出
- [ ] 不建任何 `rss_feeds` / `rss_series` 列
- [ ] 網址認不出或抓不到時，說得出是哪一種失敗
- [ ] playwright 實跑，1280 與 390，附結果
- [ ] lint、type、test 綠燈
