# 08 — 索引站搜尋與結果表

**Status:** ready-for-agent

**Blocked by:** 04b（Media 詳情頁的版面與 Route 語意）、06（Tags 與預估季集）

**讀:** plan §6（search 群組）、§8.4、§11.2（T1.2）；brief §13（Media 詳情）

## 做什麼

在 Media 詳情頁按「搜尋」，索引站回一張結果表：大小、做種、來源、解析出的 Tags、預估季集
（`S01 全季` / `E05` / 無法判斷）。這是使用者第一次看見解析器的判斷。

兩個實作：`ProwlarrSearch`（REST `/api/v1/search`，Prowlarr 刻意不提供跨站聚合 Torznab）與
`TorznabSearch`（任意 Torznab 端點，依 `t=caps` 決定能不能用 tmdbid 搜）。搜尋詞由 Media 的多個
標題各發一次後合併去重。

## 驗收

- [ ] `IndexerSearch` 介面與兩個實作各有 `Fake` 與對錄製回應的契約測試（`tests/fixtures/http/`）
- [ ] `TorznabSearch` 依 `t=caps` 決定是否可用 `tmdbid` 搜尋，不支援時退回 `q=`
- [ ] 搜尋詞由英文標題、原文標題與各語言 alternative titles 各發一次，合併去重（infohash 或 link）；
      anime profile 另加 `第N季` / `Season N` 變體
- [ ] `GET /api/search?media=&q=&route=` 回結果清單，每筆附 Tags 與預估季集
- [ ] 結果表顯示大小、做種、來源、Tags、預估，可依做種與大小排序
- [ ] 動漫、美劇、電影三種類型都搜得到並正確顯示 Tags（plan T1.2 驗收）
- [ ] 索引站未設定（第 5 步跳過）或不可達時，結果表顯示可行動的說明而不是空清單
- [ ] 單站逾時不拖垮整次搜尋，逐站成敗看得見
- [ ] 結果表走 `/impeccable shape`（Media 詳情頁的新區塊，沿用票 04 定下的版面）
- [ ] playwright 實跑；深淺兩主題文字對比 ≥ 4.5:1；390px 窄版可用（結果表要在手機上讀得完）
- [ ] zh-Hant 與 en 並列；lint / type / test 全綠並貼指令輸出
