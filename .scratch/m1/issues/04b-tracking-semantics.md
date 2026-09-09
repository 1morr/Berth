# 04b — 追蹤語意：凍結時機移到送單

**Status:** ready-for-agent

**Blocked by:** 04

**讀:** plan §2.2、§5（`folder_name`）、§6（media 群組）、§11.2（T1.7）；
brief §4.5、§13（探索、Media 詳情）；`CONTEXT.md`（Tracked Media、Rule）；
`.scratch/m1/media-detail-shape.md` §3（版面契約）

## 做什麼

票 04 把「追蹤」做成一個使用者動作：按下去凍結 `folder_name`、綁定 Route、把 `tracked` 翻成 true。
這跟三處早就寫好的東西衝突：

- `CONTEXT.md`：「Tracked Media：Berth **曾為其**下載、訂閱或入庫過的 Media」——一個推導出的結果，
  不是一顆按鈕
- plan §11.2 T1.7：「Media 詳情（搜尋 → 選 torrent → **選 Route** → 送單）」
- 票 09：「從結果表選一筆 torrent、**選一條 Route**，送進 qBittorrent」

而且它在畫面上讀起來像訂閱（使用者回報：「似乎訂閱了這個媒體，新集出來時會自動下載」）。
M3 才有真的訂閱（Rule），到時候這一頁會同時有兩個東西宣稱自己是「追蹤」。

本票把凍結拿掉，讓它回到**第一次真正通向磁碟的那一刻**。凍結最後落在哪：

| 時機 | 誰做 | 票 |
| --- | --- | --- |
| 手動送單 | `add_download` 成功時凍 | 09 |
| 建 RSS Rule | Rule 建立時凍（若還沒凍） | M3 |

兩個都有人在場、都要一次明確確認。**不能拖到入庫才凍**：importer 是背景迴圈，那時候沒有人看著，
而這是整個系統唯一一個定了就改不掉的字串（brief §4.5）。

`tracked` 在票 09 以推導回來（`EXISTS(jobs)`，票 12 加帳本，M3 加 Rule）。本票是**刪掉**它而不是
改成推導：`jobs` / `ledger` / `rss_rules` 三張表現在都還不存在，推導不出任何東西，留著只會是一個
永遠是 false 的死欄位。

**版面不動。** 動作列原地保留、只換語意——票 08 要在這一頁 shape 搜尋結果表，它需要一個穩定的
基礎（shape brief §3 的區塊序列）。

## 驗收

- [ ] `media.tracked` 欄位與 `POST /api/media/{id}/track` 移除，含 Alembic migration；
      `media.default_route_id` 與 `media.folder_name` 兩個欄位**留著**（票 09 要寫它們）
- [ ] `folder_name` 一律跟著標題走（仍然 `sanitize`）：票 04 釘住「refresh 不改 `folder_name`」的
      那條測試反過來，改為釘住「TMDB 改標題後 refresh 會跟著改」
- [ ] Route 下拉留在原位，語意改為「入庫到哪裡」的偏好：**不落地、不新增端點**（見 Comments），
      只有一條 `collection_type` 相符的 Route 時自動選它；仍然只列相符的 Route
- [ ] 詳情頁不再出現「已追蹤」與「追蹤」按鈕；資料夾名那一列一律是「將會是」，
      並說明它會在送單時定下來
- [ ] 探索牆的卡片不再顯示「已追蹤」（`DiscoverItem.tracked` 一併移除；狀態要等票 09 有 Job
      才推導得出來）
- [ ] `TrackAction.tsx` 依實際職責改名，i18n 的 `media.tracked` / `isTracked` / `untracked` /
      `retrack` / `trackFailed` 一組清掉，zh-Hant 與 en 並列
- [ ] `openapi-typescript` 重產 `web/src/api/schema.d.ts`，CI 不紅
- [ ] plan §2.2 刪掉「**`tracked` 是一個欄位而不是有沒有這一列**」那段並改寫 `folder_name` 的規則；
      brief §13 的探索卡片狀態註明為推導；`CONTEXT.md` **不改**（它的定義本來就對）
- [ ] 票 08 的驗收補一條「`route` 參數是搜尋用的偏好，不是承諾」；票 09 補兩條「送單確認要印出
      資料夾名，成功時凍結」與「`tracked` 以 `EXISTS(jobs)` 推導」
- [ ] 票 04 的 `## Comments` 加一行說明第 2、5、7 條驗收被本票取代（不改它的勾選歷史）
- [ ] `docs/progress.md`「偏差與決定」記一行
- [ ] lint / type / test 全綠並貼指令輸出

## Comments

- **Route 的選擇不落地，也不新增端點。** 票 04 用 `POST /track` 順便存了 `default_route_id`；
  拿掉 track 之後要保住「記得上次選的」就得補一支 `PUT /media/{id}/route`——為了一個下拉的初值
  加一個對外介面不划算。改成：頁面狀態，票 08 的搜尋當查詢參數送、票 09 的送單當 body 送，
  `default_route_id` 由 `add_download` 寫成「上次用的」。多數人只有一條相符的 Route，
  自動選中之後這件事根本不存在。
- **不做 watchlist。**「想要但還不下載」在本票之後沒有地方標。定位（brief §1.1）是取得與入庫
  協調，request 管理是 Overseerr / Jellyseerr 的活；真要片單那是獨立功能，不該由 `tracked` 兼差。
- **本票之後到票 08 之前，詳情頁是唯讀的瀏覽頁。** 這是現況的誠實版本——票 04 的追蹤鍵按下去
  本來也看不到任何事發生。第一個真的動作是票 08 的搜尋。
- **`media` 列仍然在點進詳情頁時就寫下。** 快照要有地方放，這一條票 04 判斷正確，不動。
