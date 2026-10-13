# 88 — 簡化：RSS 綁定的搜尋預填改由後端給，刪掉前端手抄的那一份

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** `docs/research/simplification-audit-2026-10-13.md` 的 S4；`berth/parser/binding.py`（`skeleton`、`search_terms`）；`web/src/rss/searchTerm.ts`；progress.md 搜 `searchTerm.ts`

## 為什麼

綁定框的預填字是前端 `searchTerm.ts` 用 regex 挑的，它抄自後端 `skeleton`，兩邊已經不一致：Re:Zero 預填會帶著「第四季」要人手刪；`[千夏字幕組][中文名_Romaji][第12話]` 前端退回整串原文，後端讀得出 `中文名`、`Romaji`。使用者（2026-10-13）同意改。

## 做什麼

- 後端在 `SeriesOut` 與 oneshot 的 `OneshotItemOut` 各多一格預填字串。取 `search_terms` 的第一個還是 `skeleton`，開工時用上面兩個例子加幾筆真實發佈名比較後決定，寫進票的 Comments。
- 前端 `SeriesBinder`、`OneshotSection` 改讀這一格；刪 `searchTerm.ts` 與它的測試；重跑 `gen:api`。

## 驗收

- [ ] Re:Zero 的季名不再出現在預填裡；千夏那一例預填是作品名而不是整串原文；pytest 守，做變異驗證
- [ ] `searchTerm.ts` 已刪，沒有殘留的呼叫端
- [ ] Playwright 實跑 RSS 綁定框看預填（用演練伺服器或隔離環境，**不准碰使用者的 `berth-local`**），附截圖或文字結果
- [ ] plan 的 API 段、CHANGELOG 同步；全部檢查、pytest、vitest 綠；progress.md 已更新
