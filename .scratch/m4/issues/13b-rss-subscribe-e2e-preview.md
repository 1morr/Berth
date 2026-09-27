# 13b — 前端 e2e `rss-subscribe`：acg.rip 搜尋 feed 的第一輪預覽 5 秒內沒回

**Status:** done

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

- [x] 找出原因並寫下來（票的 Comments）：預覽請求在那 5 秒裡等的是什麼，附量到的證據（log、trace 或計時）
- [x] 產品的問題：寫一條會紅的後端測試（整合層），修好轉綠；spec 的問題：說明為什麼原本的等待條件不對，改 spec
- [x] `rss-subscribe` 與 `rss-subscribe-390` 在整套前端 e2e 裡連跑三次都綠
- [x] 票 13 的「lint、type、test、前端 e2e 綠燈」補勾（附這張票的結果），progress.md 票 13 那一行補註
- [x] lint、type、test、前端 e2e 綠燈

## Comments

- **原因：產品的問題，不是鎖、也不是 spec 的等待條件**。那 5 秒裡沒有東西在等鎖，是同一個發佈名被 guessit
  反覆解析、CPU 握著事件迴圈：
  - 失敗的 trace（`rss-subscribe`，`5294f36`，單獨跑兩種寬度都紅）：`POST /rss/subscriptions/search` 花
    4375 ms，預覽 `GET /rss/feeds/2/preview` 在點下去之後 4.4 秒才發出，0.6 秒後 expect 逾時、請求被收掉
    （status -1）。同一段時間的 `GET /jobs` 也要 340–520 ms（閒著時 40 ms）：背景正在規劃 Mikan 補舊集，
    同樣是 guessit 的 CPU。
  - 對 `rss` 情境的 server 打同一串 API 計時（`scripts/experiments/rss_subscribe_timing.py`）：建搜尋 feed
    2.1 s、預覽 1.95 / 2.30 / 2.32 s；先等補舊集跑完 30 秒再做（`--settle 30`）仍是 2.2 s 與 2.5–2.7 s——
    **預覽自己就慢**，背景規劃只是把它再推過 5 秒。
  - cProfile 包住 `preview_feed`（同一支腳本的 `--profile`）：時間幾乎都在 `parse_release` → guessit。一筆
    Item 把自己的標題解析 3 次——`_item_view` 說集號、`library_copy` 裡 `decide` → `plan` 讀 torrent 名、
    `by_title` 讀字幕組——再加上 `plan` 解析中性檔名 `episode.mkv` 1 次；30 筆一次預覽 120 次 guessit
    （紅燈測試量到兩次預覽 240 次、只讀 31 個名字），每次十幾毫秒。
  - 為什麼時紅時綠：兩段加起來閒著時約 4–5 秒，恰好在 spec 的 5 秒邊上；補舊集的規劃與它搶事件迴圈時就過線。
    M4 票 11、13 多了幾處讀發佈名的地方，之後就穩定紅。
- **修法**：`parser.release.parse_release` 記住最近 2048 個名字的結果（`_parse_release` 上的 `lru_cache`；
  純函式、`ReleaseInfo` 是 frozen，同 `parser.exclusion._compiled` 的先例；讀的都是模組常數，沒有可在執行期
  改的詞典）。快取掛在私有的那一支，公開的 `parse_release(name: str)` 型別照舊（code-review Standards：
  `lru_cache` 包起來的函式收任何 `Hashable`，38 處呼叫傳錯型別 mypy 看不到）。量到：建搜尋 feed 0.36–0.83 s、
  預覽 0.14–0.16 s。紅燈測試：`test_rss_subscribe.py::TestSearchFeed::
  test_its_preview_reads_each_release_name_at_most_once`——建完 feed 先清掉快取，兩次預覽的 guessit 呼叫數
  不得超過讀到的名字數；拿掉 `lru_cache` 時紅在「240 calls for 31 names」。spec 沒改：5 秒對一個 30 筆的
  讀取本來就該夠。
- 結果：整套前端 e2e（`npx playwright test`）連跑三次都是 33 passed，`rss-subscribe` 5.7–6.3 s、
  `rss-subscribe-390` 5.4–6.5 s（修之前兩條單獨跑都紅）；code-review 的修改之後再整套跑一次，33 passed、pytest 仍是
  3192 passed。pytest 3192 passed；ruff、ruff format、mypy
  （366 files）、import-linter（6 kept）、eslint、prettier、tsc、vitest 978 綠；`berth bench` auto_wrong 0
  （high 0/84、medium 0/93）。
- code-review 處理掉的：Comments 原本寫「一筆約 5 次、一次預覽約 150 次」，照程式碼改成 3 + 1、120 次（Spec）；
  測試原本在快取熱著時量，修好之後幾乎量不到東西，改成先清快取、比名字數而不是 guessit 的輸入（兩個發佈名
  可以正規化成同一串）（Spec）；快取改掛私有函式保住型別、容量說法改成可核對的數字、實驗腳本登記進兩份
  README 並列為 import `berth` 的例外、cProfile 併進腳本（Standards）。
- **沒修、留著的**：
  - 背景規劃（與輪詢）的解析仍是跑在事件迴圈上的 CPU，一批規劃期間其他請求照樣慢幾百毫秒（上面 `GET /jobs`
    的 340–520 ms）。快取讓同一個名字不再重算，但第一次解析一批新發佈名時仍會卡住別的請求；根治要把規劃的
    CPU 移出事件迴圈（`asyncio.to_thread` 或 process pool），牽涉 plan §3.2 的背景迴圈，沒有失效的測試之前不動。
  - 快取是行程全域的（code-review Standards）：將來若有測試讓 guessit 回假值，結果會留在快取、污染後面的
    測試。現在沒有這種測試（替身都換在 `services` 那一層）；真的出現時在那個測試裡 `cache_clear`。
