# 109 — 每個 Feed 可以設定輪詢間隔

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** plan §3.2（`rss_poller`）、§6 rss；`berth/models/rss.py` 的 `interval_sec`；`berth/api/rss.py` 的 `FeedIn`、`PUT /feeds/{id}/routes`（票 105）；`web/src/rss/FeedSection.tsx`

## 為什麼

使用者 2026-10-19 要在新增 Feed 時就能設間隔，之後也能改。資料庫早就是每個 Feed 一個 `interval_sec`（預設 900），`poll_due` 也照各自的間隔跑；缺的只有 API 和畫面，API 現在只回傳、不收。

## 慣例

照 FreshRSS（[Refreshing feeds](https://freshrss.github.io/FreshRSS/en/users/09_refreshing_feeds.html)）：每個 Feed 可以設自己的間隔，而且有下限（單一 Feed 15 分鐘），理由是避免把來源站打到封 IP。FreshRSS 另有一個全域預設，這裡不做。

## 使用者拍板（2026-10-19）

- 每個 Feed 各自設，不做全域預設。
- 下拉選固定檔位，不開放自由輸入：15 分、30 分、1 小時、3 小時、6 小時、12 小時、24 小時，預設 15 分。

## 做什麼

1. **後端**：檔位定義在一處（例如 `models/rss.py` 旁邊的 tuple），`FeedIn` 收選填的 `interval_sec`，預設 900；新增 `PUT /feeds/{id}/interval`，形狀照票 105 的 `PUT /feeds/{id}/routes`。不在檔位裡的值回 422，拒絕理由照現有的 `RssRefusal` 慣例加一種。改間隔是 `services` 的命令函式，要標 `@command`（CLAUDE.md 架構規則）。
2. **生效時機**：照現有 `poll_due` 的算法，下一次 = `last_polled_at` + 新間隔，不立刻輪一次。
3. **從作品頁訂閱**建出來的 Mikan 單一 Feed 用預設 15 分鐘，之後在 RSS 頁可以改；訂閱區塊不加這一格。
4. **前端**：新增 Feed 的表單多一個「輪詢間隔」下拉；Feed 列上現在顯示「每 N 分鐘」的地方可以改，和改 Route 放在同一處。i18n 的 zh-Hant、en 並列。
5. **文件**：plan §3.2、§6 rss；CHANGELOG；progress.md session 紀錄。

## 不做

- 全域預設間隔、停用輪詢（0）、自由輸入分鐘數。

## 驗收

- [ ] 新增 Feed 可以帶檔位內的間隔；不帶是 900；檔位外的回 422（pytest）
- [ ] `PUT /feeds/{id}/interval` 改了之後，`poll_due` 照新間隔判斷到期（pytest）
- [ ] 新增表單與 Feed 列都能選間隔，存完畫面顯示新值（vitest，zh-Hant 與 en）
- [ ] playwright 實跑新增與修改，附截圖（1280 與 390）
- [ ] 全部檢查、pytest、vitest 綠；plan、CHANGELOG、progress.md 已更新

## Comments
