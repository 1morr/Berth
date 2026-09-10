# 08 — 索引站搜尋與結果表

**Status:** done

**Blocked by:** 04b（Media 詳情頁的版面與 Route 語意）、06（Tags 與預估季集）

**讀:** plan §6（search 群組）、§8.4、§11.2（T1.2）；brief §13（Media 詳情）

## 做什麼

在 Media 詳情頁按「搜尋」，索引站回一張結果表：大小、做種、來源、解析出的 Tags、預估季集
（`S01 全季` / `E05` / 無法判斷）。這是使用者第一次看見解析器的判斷。

兩個實作：`ProwlarrSearch`（REST `/api/v1/search`，Prowlarr 刻意不提供跨站聚合 Torznab）與
`TorznabSearch`（任意 Torznab 端點，依 `t=caps` 決定能不能用 tmdbid 搜）。搜尋詞由 Media 的多個
標題各發一次後合併去重。

## 驗收

- [x] `IndexerSearch` 介面與兩個實作各有 `Fake` 與對錄製回應的契約測試（`tests/fixtures/http/`）
- [x] `TorznabSearch` 依 `t=caps` 決定是否可用 `tmdbid` 搜尋，不支援時退回 `q=`
- [x] 搜尋詞由英文標題、原文標題與各語言 alternative titles 各發一次，合併去重（infohash 或 link）；
      anime profile 另加 `第N季` / `Season N` 變體
- [x] `GET /api/search?media=&q=&route=` 回結果清單，每筆附 Tags 與預估季集
- [x] `route` 參數是**搜尋用的偏好，不是承諾**（票 04b）：它只影響這一輪搜尋（profile 決定
      anime 的查詢變體），不寫進 `media`，也不代表之後一定送到那條 Route
- [x] 結果表顯示大小、做種、來源、Tags、預估，可依做種與大小排序
- [x] 動漫、美劇、電影三種類型都搜得到並正確顯示 Tags（plan T1.2 驗收）
- [x] 索引站未設定（第 5 步跳過）或不可達時，結果表顯示可行動的說明而不是空清單
- [x] 單站逾時不拖垮整次搜尋，逐站成敗看得見
- [x] 結果表走 `/impeccable shape`（Media 詳情頁的新區塊，沿用票 04 定下的版面）
- [x] playwright 實跑；深淺兩主題文字對比 ≥ 4.5:1；390px 窄版可用（結果表要在手機上讀得完）
- [x] zh-Hant 與 en 並列；lint / type / test 全綠並貼指令輸出

## Comments

實作與驗收字面不符的地方，以及留給後面幾票的發現。

### 與票的字面不同

- **「兩個實作各有 `Fake`」→ 一份共用的 `FakeIndexerSearch`。** 兩個實作對呼叫端是同一個介面，
  而 services 那一層要驗的（多標題展開、合併去重、逐查詢成敗）不認得協定。協定本身的差異由
  `tests/integration/test_indexer_search.py` 對錄製回應守著，兩個實作各有自己的契約測試。
  兩份 Fake 只會是同一段 stub 抄兩次。
- **「逐站成敗看得見」→ 逐查詢成敗看得見。** Prowlarr 的 `GET /api/v1/search` 聚合完就回，
  **不報逐站的成敗**（2026-09-10 查證），所以那個粒度拿不到。Berth 看得見的單位是「一個關鍵字
  一次請求」，纜繩畫的就是它；單一 Torznab 端點時兩者本來就是同一件事。
  逐站的資訊仍然在結果表的「來源」欄裡。
- **`tmdbid` 那一條分支沒有錄製回應。** 627 份 Cardigann 定義裡支援 tmdbid 的 93 份**全部是私站**，
  公開站錄不到。所以驗的是 `capability_of()` 這個純函式（輸入是 caps 的值），不偽造一份 XML
  當「錄製回應」。`supportedParams` 的解析本身有三份真的 caps 守著（`q` / `q,season,ep` / `q,imdbid`）。

### 留給後面的發現

- **`Season 3 / … Season 3 - 46` 被讀成 `S03E03–E46`**（`_LOOSE_RANGE` 把 `3 - 46` 當成集號區間）。
  已確認是票 05 就有的行為，不是這一票造成的。修法要動 `_LOOSE_RANGE` 的前後文判斷（季號詞之後的
  數字不是區間起點），需要自己的語料 fixture 與一輪 `berth bench`。**留給票 05/06 的後續**。
- **TMDB 別名的順序是隨機的，而查詢上限是五個。** 顯示用標題已經明確排到第三（票 08 修），但第四、
  第五個名額仍然由 TMDB 的 `alternative_titles` 順序決定：實跑看到 `Agent x Ailə`（亞塞拜然語）與
  `Разделяне`（保加利亞語）各佔一個名額而實搜 0 筆。要再改就得有「哪些語言值得問」的規則，
  而那需要自己的量測。
- **同名不同作品會通過粗篩。** `mentions()` 是純字串包含，所以搜劇集 Severance 時 2006 年的同名
  電影也進得了結果表。它們的預估是「判斷不出來」（`map_episode` 的年份比對擋下了），所以畫面沒有
  說錯話，但它們佔了名額。要收緊就要在粗篩之後、取一百筆之前再跑一次精確比對，而那要先解決
  `parse_release` 每筆 14 毫秒的成本。
- **窄版上五條纜繩把結果表推到第二屏。** 390px 實跑量到搜尋列 + 五條纜繩約佔 700px。全部成功時
  那五條的資訊量只有「各問到幾筆」；失敗那幾條才是要看的。全綠時收成一行是可能的改法。
