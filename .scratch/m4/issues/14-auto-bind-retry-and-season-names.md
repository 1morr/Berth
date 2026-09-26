# 14 — 自動綁定：暫時失敗有限重試、一個候選壞掉不拖垮整次、季名不進搜尋詞

**Status:** ready-for-agent

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

- [ ] 兩條 repro 修前紅、修後綠（貼輸出）
- [ ] 一個候選壞掉時其餘照判（單元 / 整合測試，雙向：全部壞掉仍是查不到）
- [ ] 暫時失敗在上限內重試成功、用完落到 `lookup_failed`、非暫時性的不重試（整合測試）；同一個番組頁的請求次數有上限（測試斷言預算用量）
- [ ] 季名規則逐寫法雙向測試；`berth bench` 輸出貼上、`auto_wrong` 不升
- [ ] brief §15、plan §3.2、§4.4 同步
- [ ] lint、type、test 綠燈

## Comments
