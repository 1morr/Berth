# 14 — 播出日比對

**Status:** done

**Blocked by:** 08（`rss_items.published_at` 接到 Job）

**讀:** plan §3.1（`planning` → `review` 與 `ReviewReason`）、§4.4、§11.4（「入庫前後的三道程式檢查」①）；brief §6.4、§6.10、§14、§19（「沒有 AI 時把人工降到最少」與 2026-09-24 更正）

## 做什麼

三道程式檢查裡**抓 split-cour offset 算錯的主要一道**（使用者 2026-09-24 拍板）。Jellyfin 認集數靠 Berth 取的檔名，所以 Berth 算錯的集數會原樣抄進 Jellyfin，回驗看不出來。

- **規則一**：Feed Item 的發佈時間早於換算出的那一集的 TMDB 播出日，而且超過兩天容忍，就一定是算錯。
- **規則二**：連載中的 RSS Series，對到的那一集比同一部作品最近播出的一集早很多，也算可疑。「很多」的門檻先寫成常數，再用票 07 的 fixture 與真實作品量一次。
- 可疑的**不自動入庫、送審核**，理由是新的 `ReviewReason`（封閉集合，進 OpenAPI 與 i18n）。BD 版晚幾個月才發也會落在這裡，可以接受。
- 發佈時間要從 Feed Item 帶到規劃：這一票決定它住在 Job 還是只從 `rss_items` 讀，寫進 plan。
- **手動送單也要涵蓋**（使用者 2026-09-24 試跑時拍板）：索引站結果的 `publishDate` 在送單時跟著 Job 存下來，規則一照樣套用；規則二只對 RSS Series。手動送的整季合集一樣會把絕對編號換算過頭、換到還沒播的集數，這一道同樣抓得到。索引站沒給 `publishDate` 的，跳過並在理由裡記一筆（同「沒有播出日」）。Prowlarr 的預設公開站實測每一筆都有（brief §20.11）；RSS 那一端的時區由票 08 的 adapter 處理。
  - **規則一抓不到反方向的錯**：新一季被當成第一季（TMDB 還沒建新一季、字幕組沿用標題從 01 重數）時，換算出的是早就播過的集數，發佈時間晚於它是正常的。所以這一票**不是**「只有一季 → 第一季」升成 high 的前提；那要另一個條件（plan §11.4 ①「待議」）。存下來的發佈時間是它要用的資料。
- **搜尋結果表加一欄「發佈」**（使用者 2026-09-24 拍板）：相對時間（「3 週前」），滑過去是完整日期；沿用 Sonarr / Radarr 手動搜尋的 Age 欄。資料與送單存下的是同一個欄位，`SearchResultOut` 帶上它；索引站沒給時顯示 `—`。
- TMDB 那一集沒有播出日時跳過這條檢查，並在理由裡記一筆。

檢查是純函式，放在規則層可以測的位置；AI 在 M5 的結果也要過同一條（brief §14「AI 說了不算」），所以不要寫死在 RSS 的路徑裡。

## 驗收

- [x] 規則一、規則二各有純函式單元測試，含兩天容忍的邊界
- [x] 一筆發佈時間與換算出的那一集播出日對不上的 RSS 集數不自動入庫、出現在 `/review`，理由說得出兩個日期（整合測試，對應 M3 驗收第六條）
- [x] 手動送單：索引站 `publishDate` 早於換算出的那一集播出日（超過容忍）的不自動入庫、進 `/review`；對得上的照常入庫；沒有 `publishDate` 的不擋（整合測試）
- [x] 搜尋結果表有「發佈」欄（相對時間、完整日期在 `title`、沒有時 `—`），zh-Hant 與 en（前端測試）
- [x] 對得上的照常自動入庫（雙向）
- [x] 沒有播出日時不擋
- [x] 新理由的 zh-Hant 與 en 文案
- [x] plan §3.1、§4.4 同步
- [x] lint、type、test 綠燈

## Comments

2026-09-26 收尾。

- **發佈時間住在 `jobs.published_at`**（票面要這一票決定）：手動送單沒有 Feed Item；既有 RSS Job 由 migration `c8d2f5a1e734` 從 `rss_items` 回填。寫進 plan §2.3。
- **規則**在 `berth/parser/airing.py`（`check_airing`，純函式，吃 Plan Item、快照、發佈時間與 `from_series`）；`services/plan._decided` 讓正式 Plan 與 pre-plan 同一條路，排在 Route 政策之前；`plan.proposal`（票 13 的改正）不跑。被擋的列留著季集、路徑、信心，`_verdict` 先判 `air_date_conflict`。
- **規則二的「連載中」**＝發佈當時最近播出的一集（播出日 ≤ 發佈日 + 2 天，正片的季）離發佈不超過 `BEHIND_LATEST`。**門檻 6 週的量測**（`scripts/experiments/air_date_lag.py`，2026-09-26 實跑，Mikan 兩份 + acg.rip + Nyaa fixture、真 TMDB）：198 筆、對到單集 149 筆；`lag_days`（發佈 − 播出日）最小 −1、中位 2、p95 108（上伊那牡丹整季補檔），**沒有一筆早於播出日超過兩天**；直接呼叫 `check_airing` 時 28 / 35 / 42 / 56 天四個門檻都只擋下同一筆——NanakoRaws《上伊那牡丹》`- 03`（06-30 發佈，最近播出 E12 06-27，落後 63 天），判斷是慢發補檔、核准即可。真 split-cour（芙莉蓮 tv:209867，第二季併進 S01）模擬第二輪 01：落後 840 天。
- **使用者拍板另開 14b**：連載中的 split-cour 第一批現在整批停在審核，而「套用到這個 RSS Series」只能從已入庫的發動。票 13 的測試（`test_series_review.split_cour`）與演練情境 `rss-split-cour` 改成 2025 播出（規則二不看已播完的），繼續測已入庫那一條；這段期間 M3 驗收第五條在「連載中」的情境要等 14b。
- **順手**：`Timestamp` 的相對時間多了月與年（抽成 `components/relativeTime.ts`，50–52 週說「去年」）；演練情境 `submit` 的兩筆結果帶發佈時間（dmhy 那一筆沒有，顯示 `—`）。
- **實跑**：`pnpm -C web e2e` rss / rss-390 / series-offset / series-offset-390 / rss-backfill / rss-preview / rss-exclusions / submit / review **9 passed**。playwright 另外手走兩處，截圖在 `.local/screens/m3-14/`：`submit` 情境的結果表（1280、390，「發佈」欄 3 週前 / 12 個月前 / `—`，`title` 是完整日期，390 沒有橫向捲動）；把 `rss-split-cour` 臨時改回 2026 播出的替身（scratchpad 的一次性腳本，不入庫）綁定補舊集之後 12 份計劃都停在 `/review`，列上寫「S01E01 在 2026-01-08 播出，而發佈當時這部作品最近播出的是 S01E14（2026-07-09）：季號或 offset 多半錯了」，Job 頁說出下一步。

code-review 已處理：`published_at` 不帶時區時 500 → `AwareDatetime` 422（紅 → 綠）；`serial` 改名 `from_series`；「擋下的理由」集合搬進 `parser.airing`（`HELD_BY_AIRING`）；`_plan` / `_preplan` 重複抽成 `_decided`；實驗腳本登記進 `scripts/experiments/README.md` 與 README；兩處「沒報就不送」的註解改正；多餘的 `?? null`；CONTEXT.md 加 **Air-date check**；既有 Job 的 `POST /jobs/{hash}/reimport` 會再比一次，寫進 plan §4.4（與拒絕後重算同一個取向）；UI 文案拿掉「可以套用到整個 RSS Series」（那在 14b）。

沒處理、記在這裡：
- **網路先行配信**（ABEMA、Netflix 比電視早一週，TMDB 記電視日）會被規則一擋；量測裡沒有這種樣本（`lag_days` 最小 −1），沒有 repro 不改。真的出現時的解法是 TMDB 那一集的日期，或 Series 上的容忍，屆時再定。
- **核准被擋的列時不再比帳本**：`_duplicate_of` 只比 `import` 的列，`promote` 之後直接入庫，`span_clash` 會漏。Route 政策擋下的 medium 早就是同一個形狀，這一票擴大到 high；要修的話是核准那一步再比一次帳本，另開票。
- **字幕跟著被擋的影片時仍是 `subtitle`**：整份停在 `pending_review`、核准時 `revise` 會重算，不會寫錯，只是畫面上那一對狀態不一致；同 `_apply_policy` 的既有行為。
- split-cour 的播出日產生器有三份（兩個測試檔、`fake_setup_server`）：一份是演練伺服器、兩份是不同年份的測試情境，合併要跨 `scripts/` 與 `tests/`，不值得。
- `_latest` 回傳 `tuple[tuple[int, int], date]`、`_airing` 用 `source_url` 判斷有沒有來源：判斷題，維持。
