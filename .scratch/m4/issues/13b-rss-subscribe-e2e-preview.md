# 13b — 前端 e2e `rss-subscribe`：acg.rip 搜尋 feed 的第一輪預覽 5 秒內沒回

**Status:** ready-for-agent

**Blocked by:** None — can start immediately（排在 13 之後、10 之前：10、05–09 都有 UI，這條紅著它們的「前端 e2e 綠燈」勾不起來）

**讀:** 票 04、11、13 的 `## Comments`（`rss-subscribe` 那幾條）；plan §3.2（背景迴圈）、§3.3（寫交易紀律，M4 票 01）、§6 rss；
progress.md 2026-09-27 的 session 紀錄與「偏差與決定」

## 為什麼

`web/e2e` 的 `rss-subscribe`（1280 與 390）從 M4 票 11 起時紅時綠，到票 13 收尾時兩種寬度都穩定紅，把 13 的
「前端 e2e 綠燈」卡住（13 的其餘驗收都已勾）。紅在同一步：作品頁建好 acg.rip 搜尋 feed 之後，第一輪預覽
`GET /rss/feeds/{id}/preview` 5 秒內沒回（trace 裡 status -1），「只追之後的」沒出現。

各票記下的線索（都還沒 repro 成測試）：

- 票 04：那時後端正在規劃 Mikan 補舊集的 12 筆（每筆約 0.5 秒，一個接一個），懷疑預覽的讀取被規劃器餓死；
  乾淨的 `3522046` 上一綠一紅。
- 票 11：`ef805ea` 上一紅一綠，不是 11 造成。
- 票 12：`rss-subscribe` 綠、`rss-preview-390` 紅（單獨重跑綠），同一類整套跑時的時序問題。
- 票 13：把 13 的改動 stash 掉，在 `23ad00e` 上重跑兩種寬度都紅在同一步。

要先分清楚是**產品的問題**（預覽被背景規劃或寫鎖擋住，使用者真的會等超過 5 秒）還是**spec 的問題**（等待條件或
測試資料的時序不對）。前者修產品，後者修 spec；不接受只把逾時拉長而說不出為什麼。

## 驗收條件

- [ ] 找出原因並寫下來（票的 Comments）：預覽請求在那 5 秒裡等的是什麼，附量到的證據（log、trace 或計時）
- [ ] 產品的問題：寫一條會紅的後端測試（整合層），修好轉綠；spec 的問題：說明為什麼原本的等待條件不對，改 spec
- [ ] `rss-subscribe` 與 `rss-subscribe-390` 在整套前端 e2e 裡連跑三次都綠
- [ ] 票 13 的「lint、type、test、前端 e2e 綠燈」補勾（附這張票的結果），progress.md 票 13 那一行補註
- [ ] lint、type、test、前端 e2e 綠燈
