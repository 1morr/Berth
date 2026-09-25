# 18 — 一次性 RSS 連結

**Status:** done

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

- [x] 貼 Mikan 單一 feed 的網址 → 列出整季 → 勾三集 → 三筆 Job（整合測試，用 fixture 當替身）
- [x] 合集可以勾選並送出
- [x] 不建任何 `rss_feeds` / `rss_series` 列
- [x] 網址認不出或抓不到時，說得出是哪一種失敗
- [x] playwright 實跑，1280 與 390，附結果
- [x] lint、type、test 綠燈

## 結果

- 整合測試 `tests/integration/test_rss_api.py::TestOneshot` 四條：單一 feed 12 筆 → 勾 01–03 走 `POST /jobs` → 三筆 `manual` Job，`/rss/feeds`、`/rss/series`、`/rss/items` 都是空的；合集 `release_kind = collection`、選了作品時 `S01 E01–E12`、全季，送得出去；選了作品與 Route 時第 3 集帶 `job_hash`、第 5 集帶 `known`（帳本另一個 hash 的同一個版本）；四種失敗各自的狀態碼與理由（`feed_unsupported` 422、`feed_unreachable` 502、`feed_not_rss` 502、`media_missing` / `route_missing` 422）。
- 前端 `RssPage.test.tsx` 五條（讀 → 選作品 → 勾三筆、照舊的先送，body 對得上；一筆被拒不擋下一筆；不是 RSS 時說原文；同一條網址讀不到之後再按會重讀；沒有 Feed 時也在）、`oneshotBatch.test.ts` 三條。送單順序與重讀兩條做過變異（拿掉就紅）。
- playwright `rss-oneshot` / `rss-oneshot-390`（`rss` 情境）：單一 feed 讀到 12 筆 → 選《與妳相戀到生命盡頭》、Route 選 Anime → 清單換成 `S01Exx` → 勾 01–03 → 「送出 3 筆；0 筆本來就在了；0 筆沒有送出。」→ Feed 段仍是空狀態、沒有 Feed Item 段 → `/jobs` 三筆；另一條：`example.com` 說「認不得這個網址」、讀不到的 nyaa 網址說「現在讀不到這個網址」、acg.rip 那一份 30 筆標出合集、合集勾得起來。截圖在 `web/test-results/rss-oneshot-*/`（1280 與 390 各一組）；code-review 修完之後連同 rss / rss-exclusions / rss-preview / rss-backfill 重跑 **8 passed**。

## Comments

code-review（Standards、Spec 兩軸）修了：同一條網址重按「讀取」不重讀（加測試）、換網址時讀取中勾得到上一個 feed 的項目、重讀失敗時整批清單與結果消失、oneshot 的 query key 掛在 `RSS_KEY` 底下（頁上每個動作都重打一次上游）、送出中作品與 Route 還能改、完成那一句說兩次；`wholeSeason` 改名 `freshSingles`（與後端 `whole_season` 意思不同）、`Batch` 元件改名 `Listing`（撞上 `ReleaseKind.BATCH`）。

沒處理的：

- `read_oneshot` 不檢查 Route 收不收得下這部作品、停用了沒有（`route_kind_mismatch` / `route_disabled`）：給錯 Route 時 `known` 在錯的資料夾比帳本；畫面的 `RoutePicker` 只列收得下的，送單時 `POST /jobs` 會擋。
- `OneshotSection.WorkPicker` 與 `SeriesBinder` 的搜尋區仍重複（防抖、`titleOf` / `aboutOf`、錯誤句子）；這一票只抽出 `Choices` 與 `preselect`。兩處的六個 prop（作品、詳情、Route 與各自的 setter）也可以包成一個 hook。
- `oneshot._item` 沒選作品時「單集的 `episode_end` 補成起始集」與 `search.estimate` 裡同一條規則各寫一次。
- 每一筆各打一次 `library_copy`（N+1）；feed 通常幾十筆，先不動。
- 檔名 `WorkChoices.tsx` 匯出的是 `Choices` 與 `Pickable`。
- 「勾選全部單集」鍵票面沒要求（Spec 軸記為小幅擴張）：一季十幾集逐一勾太累；它刻意不勾合集與已經有的。
