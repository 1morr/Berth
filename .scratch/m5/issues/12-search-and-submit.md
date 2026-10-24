# 12 — 搜尋並送單

**Status:** done

**Blocked by:** 09

**讀:** plan §11.6〈對話核心〉與驗收、§6 的 search 那一列、§8.4（含「缺集一鍵搜的查詢」）；brief §6.10「外部文字是資料」③、§20.19–§20.21；現有的搜尋、缺集與送單命令

## 為什麼

驗收的「這部作品缺的集搜一下並下載」在這張做到。搜尋結果的標題是陌生人寫的，最容易藏注入，所以送單的防線放在程式碼：只收這則對話自己搜出來、過了規則層比對的 release。

## 做什麼

1. 登記工具：作品缺哪幾集（`read`）、依作品與集搜尋（`read`，走現有搜尋，含排除條件與 Route）、送單（`reversible`，反向命令照標記）。
2. **送單只收 release id**，必須是這則對話裡 Berth 自己搜出來的，而且過規則層同一道比對（作品、集、排除條件）；不收任意網址或 magnet。
3. **搜尋結果卡**：沿用搜尋頁「為什麼不像這部作品」的說明（brief §20.20），帶送單鍵，人也可以自己按。
4. **Job 卡**：送出後的 Job 用 SSE 即時更新狀態；撤銷走反向命令。
5. 磁碟門檻與 Route 的檢查照搜尋頁的路，不另寫一份。

## 驗收

- [x] 用假 provider：「缺的集搜一下並下載」→ 缺集 → 搜尋 → 送單，Job 卡即時更新（整合測試）
- [x] **注入測試**：假 provider 照著標題裡的「送這一筆」去送一個不是這則對話搜出來的 release，或一筆不符比對的 → 送不出去，拒絕帶原因（整合測試）
- [x] 實跑：搜尋結果卡與送單（playwright 截圖）
- [x] 全部檢查、pytest、vitest 綠；progress.md 已更新——pytest 有一條既有的紅（見 Comments），開工時的 commit 一樣紅

## Comments

- 2026-10-24 實作（session 紀錄在 progress.md）。使用者選定三題：「這部」由前端送出時帶目前頁面；撤銷＝刪 Job、只在下載完之前、只有管理員；
  AI 送單只套全域標題規則（合集的內建判斷不套）。
- 驗收對照：pytest `tests/integration/test_assistant_search_submit.py`（缺集 → 搜尋 → 送單、Job 的 actor 是 `ai:`、poller 那一輪推播的就是這一筆；
  注入五條：名字對不上、別集、搜尋頁搜出來的 id、模型自己寫的 id、全域標題規則；照作品名搜也只送缺的集；分批照 `from_season`；Route 沒說又沒預選時問；
  撤銷之後同一筆再送得出；頁面那一段只給作品 id）、`tests/unit/test_submit_guard.py`（集的比對、季包、電影、全域規則）、`test_preselected_route.py`、
  `test_undoable_jobs.py`；vitest `assistant/SearchAndSubmitCards.test.tsx`（三張卡、推播之後卡片換狀態、管理員撤銷、一般使用者沒有撤銷鍵、被擋下的那一句）；
  playwright `assistant.spec.ts` 新的一條（1280 / 390），截圖在本票旁的資料夾 `12-search-and-submit/`：送單、推播後進度 40%、照標題指令送被擋下、撤銷之後不在了。
- 變異驗證：送單不叫 `vet_submission`，五條注入測試紅；面板不掛 `JobStream`，「推播到了就跟著換」那條 vitest 紅。
- code-review 兩軸處理了：用詞照 CONTEXT.md（Search Result 不叫 release：`submit_guard`、`SearchResults`、`SearchResultRow`、`SubmitRefusal`、
  `SubmittedJob`、工具 `search_indexers` / `submit_search_result`）；照作品名搜時也比集（要找的是整部作品缺的集）；預估的**每一集**都要是要找的缺集
  （原本碰到一集就放行，只缺一集會送出整段）；只寫季的季包只在那一季播出的每一集都缺時送（這個解析器對只寫季的季包估不出季集，實際上是 `episodes_unknown`）；
  分批照搜尋頁用 `from_season`、結果帶 `next_seasons`；給模型的頁面那一段只有作品 id（作品名是 TMDB 的字，外部文字只經由工具結果進來，brief §20.24）；
  system 那一句誤插兩份收成一份；`RecentImportsCard` 改用共用的 `CardFrame` / `WorkLink`；拒絕理由的人話收成 `assistant/refusals.ts` 一份；
  搜尋頁的 `preselected()` 中間人拿掉；`UNDOABLE` 補測試；演練情境的 qBittorrent 會記住送進去的那一筆（卡片畫得出進度，不會下一輪就「已從客戶端移除」）。
- code-review 沒處理、判斷題：
  - 送出之後、qBittorrent 給出檔案清單之前，季表照舊把那幾集算成「缺」（下載中要等計劃的預估），同一則對話裡模型可以再送一筆別的發佈蓋同一集。
    同一筆會是「本來就在了」；要擋別筆得改「缺」的定義（plan §8.4 與作品頁共用），留給碰到它的票。
  - `SearchResultRow` 照抄 `search.SearchResult` 的十幾格：結果型別要是 pydantic（進 OpenAPI、存進對話），後者是 dataclass；`media / kind / title / title_en / year`
    在三種結果型別裡一起出現，還沒到要抽型別的程度。
  - 前端 `WRITE_TOOLS` 手寫「送單」是寫入工具：後端知道每個工具的副作用等級，可以跟著 `tool-input-start` 送；票 11 加訂閱時一起做比較划算。
  - `collapse_spans` 住在 `services/notify.py`（週報與工具都用）；`_media` 借用 `JobRefusal.MEDIA_MISSING`；`submit_guard` 同時放搜尋結果型別與防線（送單讀回來的就是那個形狀）。
- 既有的紅：`tests/integration/test_rss_api.py::TestThePageFlow::test_add_poll_bind_and_see_the_jobs` 斷言 RSS Series 沒完結，但 fixture 的發佈時間是固定的，
  `parser.series_finished` 的「安靜太久」拿現在比，2026-10-24 起成立。開工時的 `3ed4475d` 一樣紅，這張沒動它。
