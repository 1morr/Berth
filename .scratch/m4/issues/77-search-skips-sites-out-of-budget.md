# 77 — 一個站的請求預算用完時，搜尋照樣問其他站

**Status:** done

**Blocked by:** 76（同一批對外請求與錯誤訊息的程式，先讓 76 改完 log）

**讀:** `berth/adapters/budget.py` 開頭的說明；M3 票 20、plan §3.2、§8.4；`docs/research/request-budget.md`；`berth/services/search.py` 的預算段；前端搜尋卡片的「等請求預算」說明與 i18n

## 為什麼（2026-10-09 使用者本機實測）

- 使用者訂閱 Mikan 的 MyBangumi，Berth 在一小時內對 mikanani.me 發了 87 個請求：`.torrent` 32、單集頁 21、作品頁 17、各作品 RSS 15、MyBangumi 2。Mikan 那一小時的 60 格就用完了。
- 之後搜《Law & Order》，跟 Mikan 無關的影集：
  - 因為 Prowlarr 底下也有 Mikan，現行規則是「有一站放不下就一個都不問」，Nyaa 等還有額度的站也沒被問；
  - 畫面只說等 43 分鐘。
- 畫面最後一行是後端的英文原始訊息 `request budget for mikanani.me is used up; it fits again at 2026-10-09T01:13:14.847316+00:00`：沒走 i18n，時間是 UTC 的 ISO 字串。

## 做什麼

1. **搜尋改成跳過放不下的站**：
   - 有額度的站照常問、照常佔格；放不下的站這次不問，結果裡列出「哪幾個站這次沒問、何時放得下」。
   - 所有站都放不下時，才維持現在的「整批等待」畫面。
   - 改變的是 plan §8.4 / 票 20 的規則：同一 commit 改 plan 與 brief，progress.md「偏差與決定」記一行。
   - 先查 Prowlarr 的搜尋 API 能不能只問指定的 indexer（context7 或 OpenAPI，查到補進 brief §20）。不能指定的話，寫出替代做法再實作，理由寫在 Comments。
2. **畫面**：
   - 「這次沒問的站」與「全部都等」兩種狀態都走 i18n key，zh-Hant 與 en 並列；
   - 時間用使用者時區與既有的相對時間格式，例如「43 分鐘後」；
   - 不再顯示後端原始英文訊息。
3. **查一件事、記下來，不在這張改**：MyBangumi 一次訂閱就吃掉 87 格，其中 `.torrent` 下載與單集頁有沒有算進預算、該不該算。結論寫在 Comments；需要改就另開票。
4. 測試：
   - 整合測試（雙向）：Mikan 額度用完、Nyaa 有額度時，搜尋有問 Nyaa、結果標出 Mikan 沒問；全部用完時維持等待；
   - vitest：兩種狀態的文案（兩種語言）與時間格式；不顯示原始訊息。
5. 實跑：隔離環境（專案名 `berth-t77`、另一組 port），把 Mikan 的預算用完再搜一部非動畫影集，附截圖。**不准碰使用者的 `berth-local`。**

## 驗收

- [x] 放不下的站被跳過、其他站照問；全部放不下才整批等待；雙向整合測試
- [x] 畫面兩種狀態走 i18n、當地時區、相對時間；不再出現後端原始訊息；vitest
- [x] Prowlarr 能否指定 indexer 的查證補進 brief §20；plan 與 brief 的規則同步，progress.md 偏差已記
- [x] MyBangumi 的請求量與預算計法結論寫在 Comments（需要就另開票）
- [x] 隔離環境實跑截圖；全部檢查、pytest、vitest、前端 e2e 綠

## Comments

### 做法

- **Prowlarr 能指定 indexer**（brief §20.7 新增一條，`SearchResource.cs` 經 context7）：`indexerIds` 是 `List<int>`、可重複帶，空的是全部啟用中的站。所以不需要替代做法：`IndexerSearch.sites()` 改回 `SearchSite`（id、名字、主機名），`RequestBudget.take_each` 放得下的站各佔格、放不下的記成延後；有站被跳過時查詢只帶其他站的 id，每一站都放得下時不帶（照舊問全部）。Prowlarr 自己的 Query Limit 也是「打滿的那一站那一次跳過」（brief §20.13）。
- `RequestBudget.take` 改成收一個站（多站整批的語義已沒有呼叫端，那條單元測試換成 `take_each` 的兩條）。
- **`retry_at` 與 `next_at` 都是「最早有一站放得下」**：code-review 兩軸都指出 `next_at` 原本還是「每一站都放得下」，跳過規則之下會把下一批說得比實際晚，已改（`ready_at`，單元測試多一條）。
- **畫面**：新元件 `media/SkippedSites.tsx`（「這次沒問」，`neutral`），逐站列索引站名、主機名與 `Timestamp`（相對時間、`title` 是當地時區的絕對時間）；只在沒有 `problem` 時出現，整批等時只有「等請求預算」那一張、不再逐站列一次。等預算時後端不再帶 `detail`（英文原文、UTC ISO）。**驗收「不再出現後端原始訊息；vitest」的偏差**：一開始在 `IndexerNotice` 加了「等預算時不畫 detail」的前端判斷並用 vitest 守；code-review（Standards）指出後端已經不送，那是替舊後端留的相容層（全域規則：不留相容層、閘門對著還有人呼叫的東西），所以刪掉，改由整合測試 `view.detail == ""` 守。vitest 守的是兩種狀態的文案（兩種語言）與相對時間。
- 實跑抓到：中文的 i18next 複數只有 other，「這 1 個站……沒問它們」，改成不帶代名詞的同一句，並把整句放進 vitest。

### MyBangumi 的請求量與預算計法（第 3 項，只查不改）

讀程式碼的結論（子代理逐條附行號，主對話核過其中幾處）：

| 那一小時的請求 | 進預算？ | 用途 | 出處 |
| --- | --- | --- | --- |
| MyBangumi 聚合 feed 2 | 是 | poll | `services/rss.py` 的 `poll_feed` 用 `feed_fetcher(factory, BudgetUse.POLL)` |
| 單集頁 21 | 是 | poll | `_series_key`，同一個 poll fetcher |
| 作品頁（番組頁）17 | 是 | poll | `_clues`（自動綁定） |
| 各作品 RSS 15 | 是 | backfill | `_read_season`（綁定時補舊集、每日補漏） |
| `.torrent` 32 | **否** | — | `jobs._resolve` → `HttpTorrentFetcher`（自己的 httpx client，不經 `BudgetedFetcher`）；Berth 自己抓是為了先算 info hash（plan §8.1） |

- 算進 60 的是 55 個。剩下的格子推測是同一小時裡的搜尋（一批在每一站各佔查詢數格）；預算在記憶體裡、窗是滾動的，沒有 `GET /health/budget` 當時的 `by_use` 就無法對帳到個位數。
- **`.torrent` 不算**是 M4 票 03 開工時使用者的決定（照 Prowlarr 把 Grab 與 Query 分兩份，plan §3.2 記著代價「大批送單時對那一站的 `.torrent` 請求不設上限」）。這次 32 個就是那個代價。要改是使用者的決定，這張不開票；選項是照 Prowlarr 另立一份 Grab 預算，或至少在健康頁另列一欄。
- **單集頁不是浪費**：每一筆新 Item 都要讀它才知道屬於哪個 RSS Series（`bangumi_id`、`subgroup_id`），讀之前分不出兩筆是不是同一個。
- **番組頁有可省的**：`_clues` 以 Series 為單位讀 `bangumi_url(mikan_bangumi_id)`，同一部作品的不同字幕組是不同的 Series，同一輪會各讀一次同一頁（沒有以 `bangumi_id` 快取）。17 個裡有多少是這種沒有資料。被預算擋下的 `lookup_deferred` 下一輪再讀一次，額度用完之後會放大。
- 結論：計法照既有決定，**不另開票**；番組頁以 `bangumi_id` 去重、`.torrent` 另立 Grab 預算兩項列給使用者決定要不要開。

### 實跑（隔離環境）

image `berth:t77`（這個分支），repo 外的 compose（`name: berth-t77`、容器 `berth-t77` / `berth-t77-prowlarr`、port 18483 / 19697、資料在 session scratchpad）。Prowlarr 2.6.5.5623 加 Mikan、The Pirate Bay（nyaasi 在這台機器 SSL 失敗，同 brief §20.7）。容器裡直接寫設定（精靈跑完、索引站、開發用的 TMDB key）與一張管理員 session。**用完 Mikan 的預算不打 Mikan**：Berth 容器的 `extra_hosts` 把 `mikanani.me` 指到 127.0.0.1（Prowlarr 不受影響），打 60 次 `GET /api/rss/mikan/search`（manual，預算在送出之前佔格，請求自己連不上）；第 61 次回 429，`/api/health/budget` 是 `mikanani.me 60 / manual 60`。

- 搜《法網遊龍》（`tv:549`）：「這次沒問：Mikan mikanani.me 放得下：60 分鐘後」，5 個關鍵字都只問 TPB（`.playwright-mcp/t77-skipped-1280.png`、`t77-skipped-390.png`，390 寬沒有橫向捲動）。
- 在這台 Prowlarr 停用 TPB、只剩 Mikan：「等請求預算 / 索引站背後的每一個站……都放不下 / 最早有一站放得下：58 分鐘後」，沒有英文原文（`t77-all-wait-1280.png`；英文 `t77-all-wait-en.png`：Waiting for the budget / The first site fits again: in 56 minutes）。
- code-review 修正後重 build（`90d52dd`）：全部等時 API `detail` 是空的；重新啟用 TPB 後搜 `Law and Order`：`skipped` 是 Mikan、TPB 100 筆全對上、預算 `thepiratebay.org` search 1。
- 跑完 `docker compose down --volumes`、刪目錄與 image；`berth-local` 四個容器沒動。

### 順帶看到、不在這張改

- **《Law & Order》搜不到東西不是預算的事**：TPB 對 `Law & Order` 回 0 筆、`Law and Order` 回 100 筆；那次的 202 筆是 TPB 對其他名字（`法網遊龍`…）回的熱門清單，全被略過。標題帶 `&` 時要不要多一個 `and` 的查詢變體，要開票由使用者決定。
- code-review（Spec）：跳過一部分站之後，剩下的站若剛好都被 Prowlarr 自己停用（失敗退避），帶 `indexerIds` 的查詢會回 400「all selected indexers being unavailable」，畫面是那幾條纜繩紅著、帶 Prowlarr 的原文；不帶 id 時 Prowlarr 也問不到東西，差別只在說法。沒有改、沒有測試。
- code-review（Standards）：`SearchSite.site` 用空字串表示「說不出網址、不記帳」（搜尋端 `if target.site`），判斷題，沒改。
