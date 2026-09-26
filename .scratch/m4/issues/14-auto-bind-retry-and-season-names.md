# 14 — 自動綁定：暫時失敗有限重試、一個候選壞掉不拖垮整次、季名不進搜尋詞

**Status:** done

**Blocked by:** None — can start immediately（與 01 碰同一個模組 `services/rss.py`，兩張不要同時開）

**讀:** brief §15「綁定」、§19 2026-09-26「自動綁定的兩種失敗」那一列；plan §2.4、§3.2（rss_poller、請求預算）、§4.4；`.scratch/m3/issues/09-rss-auto-bind.md`、`20-request-budget.md`；`berth/services/rss.py:1226-1340`、`berth/parser/binding.py:131`、`berth/parser/cjk.py:49`

## 為什麼（2026-09-26 試跑，Mikan MyBangumi 綁定 10 個 Series，2 個沒綁上）

- **尼古喵喵**：`lookup_failed: tmdb detail: tv:312949 could not be read`。同日稍後同一支 TMDB 詳情回 200。
  `_candidates`（`rss.py:1318-1340`）任一個候選讀不到快照就拋 `_LookupError`，整次綁定作廢；而 `_auto_bind` 的設計是
  「只在長出來的那一輪做」、查不到就不再重試（docstring：避免壞掉的番組頁每 15 分鐘打一次）——一次暫時失敗就永久待綁定。
  `adapters/http.py:136-137` 把 503 以外的所有 4xx / 5xx（含 429、500、502）都歸成 `ProtocolMismatchError`，
  暫時性與「接錯服務」分不出來，同樣一次定終身。分類要不要在 adapter 層多一種（例如 `RateLimitedError`、5xx 歸
  `ServiceUnavailableError`）是這張票的設計題——它影響每一個 adapter 的呼叫端，先盤點誰在接 `ProtocolMismatchError`。
- **Re:Zero**：發佈名「Re：从零开始的异世界生活 第四季」，`search_terms`（`binding.py:131`）把骨幹原樣拿去搜 TMDB，
  「第四季」讓它 `no_candidate`；拿掉之後同一個搜尋回 Re:Zero（TMDB 65942，2026-09-26 實測）。parser 已經有 `SEASON_CN`
  （`cjk.py:49`）認 `第N季 / 第N期`，搜尋詞沒用它。英文的 `Season 4`、`4th Season`、`S4` 同理。

## 做什麼

1. **先 repro**：兩條整合測試（Fake TMDB 第一次詳情 5xx / 429 之後正常；發佈名帶 `第四季`），修前紅。
2. 一個候選的快照讀不到：跳過那一個、其餘照判；全部都讀不到才算查不到。
3. **暫時失敗有限重試**：逾時、連不上、5xx、429 記成可重試（理由與現在的 `lookup_deferred` 一族，說得出下一次什麼時候），
   退避、次數有上限（寫進 plan §3.2，沿用請求預算的站台鍵）；用完才落到 `lookup_failed` 等人。非暫時性的（404、解析失敗）照舊不重試。
   保留原本的顧慮：壞掉的番組頁不會每 15 分鐘被打一次。
4. **季名**：搜尋詞去掉季名（中文 `第N季 / 第N期`、英文 `Season N / Nth Season / SN` 等，規則放 parser 並與 `structure` 共用同一份），
   去掉的季號交給 `judge` 當線索——它已經拿各季播出日比對（`binding.py:~228`），有季號時優先比那一季。
   改動 parser 要跑 `berth bench`，`auto_wrong` 不升；綁定的語料補這兩個案例。
5. 試跑環境那兩個待綁定的 Series：修完後不會自己重綁（它們已經是 `lookup_failed` / `no_candidate`）——人按一次「重新認」
   或這張票給一個一次性的重試入口，擇一並寫理由。

## 驗收

- [x] 兩條 repro 修前紅、修後綠（貼輸出）
- [x] 一個候選壞掉時其餘照判（單元 / 整合測試，雙向：全部壞掉仍是查不到）
- [x] 暫時失敗在上限內重試成功、用完落到 `lookup_failed`、非暫時性的不重試（整合測試）；同一個番組頁的請求次數有上限（測試斷言預算用量）
- [x] 季名規則逐寫法雙向測試；`berth bench` 輸出貼上、`auto_wrong` 不升
- [x] brief §15、plan §3.2、§4.4 同步
- [x] lint、type、test 綠燈

## Comments

**2026-09-26 實作（session 紀錄在 `docs/progress.md`）**

- **修前紅**：修之前的程式（`fe5a5cd` 的 worktree，只換上新測試與替身的錯誤鉤子）跑兩條 repro：

  ```
  FAILED test_rss_auto_bind_retry.py::TestTransientFailureIsRetried::test_a_detail_that_failed_once_binds_on_the_retry[502]
    AssertionError: assert 0 == 1   (PollOutcome(...).bound)
  FAILED ...::test_a_detail_that_failed_once_binds_on_the_retry[429]
    AssertionError: assert 0 == 1
  FAILED ...::TestSeasonName::test_a_release_named_with_its_season_binds_to_the_merged_work
    AssertionError: assert (None, '') == ('tv:65942', 'system')
  3 failed in 14.40s
  ```

  修後 `tests/integration/test_rss_auto_bind_retry.py` 12 passed。
- **`berth bench`**（修前、修後相同，`auto_wrong` 0 = baseline）：
  `overall 391 391/391 194/194 171/171 177 0 80 0 42 41 37 14`，high 0/84、medium 0/93 錯。
  bench 不涵蓋綁定；**「綁定的語料」是 `scripts/experiments/rss_auto_bind.py` 對真的 Mikan 與 TMDB 重量**：
  11 部認得 11 部、錯 0 部（2026-09-25 是 10 部），結果記在 `docs/research/rss-sources.md` §2.8。單元測試另補
  Re:Zero 的真實形狀（`test_rss_binding.py::TestSeasonNames`）。
- **第 4 點推翻了票面「優先比那一季」**：名字寫了季號時**只比那一季**，而且比那一季**播出的期間**（任何一集
  前後 14 天），不只首播。重量時發現 Mikan 的番組 4052 是 Re:Zero 第四季的第二個 cour「夺还篇」（放送开始
  2026-08-12），TMDB 65942 把四季全部放在第 1 季、這一天是第 78 集；只比首播會是 `premiere_far`。「優先」的
  退路（對不上就比別季）會讓第二季的番組頁綁到只有第一季對得上日期的作品——續作綁到前作。新理由碼
  `season_airing`（說出是 TMDB 的哪一集），取代實作中途的 `run_near`。
- **第 5 點選了兩個選項以外的第三條：人在待綁定那一列按「綁定 → 搜尋 TMDB」**。產品裡沒有「重新認」這顆鍵，
  做一顆是新的 UI 功能；一次性重試入口（migration 把那兩列排進重認）是替兩列資料留下的永久程式碼，而且
  `lookup_retry` 的句子（「這一次讀不到」）套在 `no_candidate` 的那一列上是假話。票之後新發生的暫時失敗會自己
  重認，用完與再問也一樣的正是人手綁定要接的。**代價**：綁定框預填的搜尋詞（`web/src/rss/searchTerm.ts`）
  不拆季名，Re:Zero 那一列預填「Re：从零开始的异世界生活 第四季」會搜不到，要人自己刪掉「第四季」。
- **分類改動的波及面**（票面要求先盤點）：接 `ProtocolMismatchError` 的只有 `services/setup.py`（精靈偵測）與
  `services/oneshot.py`（一次性 RSS 連結）；429 / 5xx 現在分別落到「連不上」（使用者自己填的位址當場給結論，
  compose 主機名過了視窗是逾時而不是既有）與 `feed_unreachable`，兩處都補了雙向測試。`.torrent` 下載
  （`adapters/torrent.py`）也改走同一支 `raise_for_status`：429 / 5xx 是 `ServiceUnavailableError`、503 是
  `ServiceBusyError`；下游只接 `ServiceError`，送單被拒的原文換一種，行為不變。
- **已知取捨**：
  - 一部候選讀不到時其餘照判（票面第 2 點），所以自動綁定第 3 條「這樣的作品只有一部」在缺一部時驗不全：
    讀不到的那一部如果也對得上，本該是 `several_candidates` 卻會綁上讀得到的那一部。要同名、開播日也在 14 天內
    的兩部作品才碰得到。
  - TMDB 的 `unreachable`（`TmdbProblem`）也包含「回的不是 TMDB」，分不開，照暫時的算，多的只是上限內的三次重認。
  - 重認用完、而讀得到的幾部判不出來時，理由是判定的那一條加 `lookup_failed`（code-review 抓到只寫判定的理由會
    誤導人，已修）。
- **code-review 沒處理的發現**：
  - `_equal_title` 與 `_candidates` 回位置 tuple（Data Clumps），各只有一個呼叫端，沒有抽成具名型別。
  - `services/media.read_snapshot` 現在只是轉呼叫 `read_snapshot_checked(...).snapshot`；它在 `services/search.py`
    還有兩個呼叫端，留著。
  - 綁定框的預填（`searchTerm.ts`）是 `parser.binding.skeleton` 在前端的一份手抄，不拆季名。修法是後端在
    `SeriesView` 送出拆好的搜尋詞、刪掉前端那一份；沒開票。
