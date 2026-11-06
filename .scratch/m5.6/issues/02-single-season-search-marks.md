# 02 — 只有一季的作品，整季缺時問得到動畫站

**Status:** ready-for-agent

**Blocked by:** 01

**讀:** spec〈範圍〉C2；研究文檔 §1 第 2 點、§4 C2；plan §8.4〈缺集一鍵搜的查詢〉；brief §20.10、§20.21

## 為什麼

整季缺時查詢是「名字 × 季記號」，CJK 名字的季記號是 `第1季`（`season_tokens`）。只有一季的番，發佈名不寫「第1季」，所以動畫站零筆；「非人少女」那次回來的 216 列全是 TPB / YTS 的無關結果。作品頁「搜缺的集」和 AI 的 `scope` 搜尋走的是同一段（`search_queries.missing_batches`）。

## 做什麼

1. **先紅**：只有一季、第 1 季整季缺、名字有 CJK 字的作品，`missing_batches` 的查詢裡至少要有一個動畫站會回結果的寫法。拉丁名字（`S01` / `Season 1`）有沒有同樣的問題，一起查。
2. 候選修法：
   - 第 1 季另送不帶記號的名字；
   - 或作品只有一季時不加記號。
   哪一種要先實測索引站（Mikan、dmhy、nyaa、acg.rip，加一部有多季的作品當對照），實驗腳本放 `scripts/experiments/`，結果寫進 brief §20 新的一節並附日期。
3. 照實測結果修，`MAX_QUERIES` 與分批規則不變；多季作品的查詢不能變差。`season_tokens` 是「按搜尋」和「搜缺的集」共用的，修在哪一層要說明，並寫進 docstring。
4. 動到 `parser/` 的話跑 `berth bench`。

不修：TPB / YTS 對查不到的查詢回一整頁無關結果（spec〈範圍〉不做）。

## 驗收

- [ ] 會紅的測試先 commit 或寫在 Comments，修完轉綠
- [ ] 實測腳本在 `scripts/experiments/`，brief §20 有結果與來源，plan §8.4 的查詢規則跟上
- [ ] 多季作品與缺幾集的查詢不變（既有測試綠，必要時補）
- [ ] 動 `parser/` 時 `berth bench` 的 `auto_wrong` 不升（貼數字）
- [ ] 全部檢查、pytest 綠；progress.md 已更新

## Comments
