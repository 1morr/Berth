# 108 — 完結的 RSS Series 停止每日補漏；補漏在畫面上看得見

**Status:** done

**Blocked by:** None — can start immediately

**讀:** plan §3.2（`rss_poller` 的每日補漏、「每日補漏排在 `rss_poller` 裡」那一段）；brief §15「補舊集」；`berth/services/rss.py` 的 `_backfill_due`、`_finished`；`berth/parser/finished.py`；`web/src/i18n/resources.ts` 裡「之後每天再補一次漏掉的」那兩句

## 為什麼

使用者 2026-10-19 提出兩件事：

1. **完結了還在補**：`_backfill_due` 只看「已綁定、是 Mikan、距上次補過滿一天」，不看完結與否。plan §3.2 寫明「季末之後照樣讀（量隨綁過的部數線性長）」。每一部綁過的作品都會每天讀一次 Mikan，永遠不停。
2. **使用者不知道有補漏**：畫面上只有訂閱 / 綁定確認區塊裡一句「之後每天再補一次漏掉的」，沒說誰漏、漏了什麼；Series 列上也看不出它補過沒有。

## 使用者拍板（2026-10-19）

- 不加開關，只讓它看得見。理由：問題是看不見，不是需要關掉；關掉的代價是停機期間被聚合 feed 擠掉的集數補不回來，而且使用者察覺不到。

## 做什麼

1. **完結就不補**（`mattpocock-skills:tdd`）：`_backfill_due` 跳過 `series_finished` 成立的 Series，判斷沿用 `_finished` 那一份現況，不另寫一套規則。完結不是存下來的狀態，新的一筆出現時條件自己不成立，補漏也就恢復。
2. **API**：`SeriesOut` 帶 `backfilled_at`（已經有 `finished`）。
3. **Series 列**：Mikan 且已綁定的 Series，在現有那一行（已入庫 · 在路上 · 排除 · 最近 · 綁定方式）加一項「上次補漏：〈相對時間〉」；還沒補過的顯示「尚未補漏」；完結的顯示「已完結，不再補漏」。非 Mikan 的 Series 不顯示這一項，因為它們沒有補漏。
4. **說明**：「RSS Series」標題下加一行，例如「綁定的 Mikan 番組每天會再讀一次整季清單，補上輪詢沒接到的集數（例如 Berth 停機期間）；完結後停止。」
5. **文案**：`resources.ts` 3127、3260 附近那兩句「之後每天再補一次漏掉的」改成說得出補什麼、為什麼補，與第 4 點的說法一致。zh-Hant、en 並列。
6. **文件**：plan §3.2「季末之後照樣讀」改成完結即停，並說明理由（停機少於 `QUIET_AFTER` 時，重啟後一天內就補到了）；CHANGELOG；progress.md「偏差與決定」記一行。

## 不做

- 補漏開關（全域或單一 Series）。

## 驗收

- [x] 完結的 Series 輪到它的 Feed 時不讀單一 feed；有新的一筆之後恢復補漏；未完結的照舊（pytest，做變異驗證）
- [x] Series 列看得到上次補漏時間、尚未補漏、已完結不再補漏三種；非 Mikan 的不顯示（vitest，zh-Hant 與 en）
- [x] RSS Series 標題下的說明與訂閱 / 綁定確認的文案說法一致（vitest）
- [x] playwright 實跑 RSS 頁與作品頁的訂閱區塊，附截圖（1280 與 390）
- [x] 全部檢查、pytest、vitest 綠；plan、CHANGELOG、progress.md 已更新

## Comments

- 截圖：`108-backfill-stops-when-finished-and-shows/` 的 `rss-bound-{1280,390}.png`（/rss 綁好之後，RSS Series 段落說明與「上次補漏」）、`subscribe-confirm-{1280,390}.png`（作品頁訂閱確認的同一句）。
- code-review 已改：英文文案不用 catch-up（CONTEXT.md 列為避免）；確認句不在元件裡拼字串，改 `$t()` 巢狀；`Backfill` 的 `<time>` 加 `.value`；DESIGN.md 補列；補英文的文案一致斷言。
- code-review 未改：
  - `Backfill` 沒用 `Timestamp`：時間要嵌進翻好的句子（`{{when}}`），照 `Timestamp past` 的做法自己畫 `<time>`；要共用得改用 `<Trans>`，專案還沒用過它。
  - 「尚未補漏」與 DESIGN.md §時間的「沒有紀錄」說法不同：這裡說的是狀態（還沒補過），不是時間點沒有值。
  - 測試裡 `BACKFILL_LEDE` 字面寫了兩份（RssPage、MediaDetailPage）：寫死字面才抓得到 zh-Hant 文案本身的變動；測試檔互相 import 會把另一檔的測試也跑一遍。
  - pytest 只走了 `QUIET_AFTER` 那條完結路；TMDB 說完結那條與畫面共用同一支 `_finished`，已由既有的完結測試守著。
  - 說明在 RSS Series 段落無條件顯示，整段沒有 Mikan Series 時也在；票沒有規定，維持。
