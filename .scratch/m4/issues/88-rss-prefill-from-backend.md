# 88 — 簡化：RSS 綁定的搜尋預填改由後端給，刪掉前端手抄的那一份

**Status:** done

**Blocked by:** None — can start immediately

**讀:** `docs/research/simplification-audit-2026-10-13.md` 的 S4；`berth/parser/binding.py`（`skeleton`、`search_terms`）；`web/src/rss/searchTerm.ts`；progress.md 搜 `searchTerm.ts`

## 為什麼

綁定框的預填字是前端 `searchTerm.ts` 用 regex 挑的，它抄自後端 `skeleton`，兩邊已經不一致：Re:Zero 預填會帶著「第四季」要人手刪；`[千夏字幕組][中文名_Romaji][第12話]` 前端退回整串原文，後端讀得出 `中文名`、`Romaji`。使用者（2026-10-13）同意改。

## 做什麼

- 後端在 `SeriesOut` 與 oneshot 的 `OneshotItemOut` 各多一格預填字串。取 `search_terms` 的第一個還是 `skeleton`，開工時用上面兩個例子加幾筆真實發佈名比較後決定，寫進票的 Comments。
- 前端 `SeriesBinder`、`OneshotSection` 改讀這一格；刪 `searchTerm.ts` 與它的測試；重跑 `gen:api`。

## 驗收

- [x] Re:Zero 的季名不再出現在預填裡；千夏那一例預填是作品名而不是整串原文；pytest 守，做變異驗證
- [x] `searchTerm.ts` 已刪，沒有殘留的呼叫端
- [x] Playwright 實跑 RSS 綁定框看預填（用演練伺服器或隔離環境，**不准碰使用者的 `berth-local`**），附截圖或文字結果
- [x] plan 的 API 段、CHANGELOG 同步；全部檢查、pytest、vitest 綠；progress.md 已更新

## Comments

- **決定：預填取「只看發佈名」的 `search_terms` 第一個**（`binding.search_term(release_title)`；讀不出作品名時給原文）。
  比較了 `tests/fixtures/http/*/*.xml` 約 30 筆真實發佈名與兩個票面例子：
  - 用 `skeleton` 不拆季名，Re:Zero 仍是「…第四季」；`search_terms` 拆季名、英文或羅馬字那一段在前。
  - **不帶 Mikan 番組名**：番組名常帶分段名（`Re：从零开始的异世界生活 第四季 夺还篇`），拿掉季名之後仍是
    `…夺还篇`，TMDB 搜不到；發佈名那一份是 `Re：从零开始的异世界生活`。
- **千夏那一例**：票面〈為什麼〉說後端讀得出 `中文名`、`Romaji`，實際上 `skeleton` 只用 ` / ` 切、不切底線，
  預填是整格 `上伊那牡丹，醉姿如百合_Kamiina Botan, Yoeru Sugata wa Yuri no Hana`——是那一格作品名，
  不是整串原文（驗收字面成立），但拿去搜 TMDB 多半要人刪掉一半。不在這張票切底線：`skeleton` 也算非 Mikan
  Series 的持久化鍵 `title_key`，改它會讓既有 Series 分裂；只在 `search_term` 另加一條切法是新規則，要另外拍板。
- **退步一例**：`[LoliHouse] 尼古喵喵 (邪竜解放版) / ヤニねこ / Yani Neko / Chainsmoker Cat - 11` 現在預填
  `尼古喵喵`（舊前端是 `Chainsmoker Cat`）：`_TITLE_END` 把 `(` 當標題結尾。這是 `skeleton` 本來就有的問題，
  自動綁定搜的字也一樣；修要動 `skeleton`、`title_key` 與 bench，另開解析器票。
- **變異驗證**（`tests/unit/test_rss_binding.py::TestTheSearchTerm`）：實作換成 `skeleton` 最後一段（不拆季名）→
  Re:Zero、Link Click 兩例紅；換成回原文 → 四例紅；改回 → 綠。
- **Playwright 實跑**：`scripts/fake_setup_server.py --scenario rss --port 8619`（暫存 config root，沒碰
  `berth-local`），`skipper` 登入、加 Mikan 聚合 feed、立即輪詢。綁定框預填：Re:Zero →
  `Re：从零开始的异世界生活`（截圖確認沒有「第四季」）、Kimi → `Kimi ga Shinu made Koi wo Shitai`、
  てんびん那一列 → `てんびん`、Yani Neko 那一列 → `尼古喵喵`。一次性連結讀單一番組 feed：預填
  `Kimi ga Shinu made Koi wo Shitai`。
- **code-review 未處理**：Standards 指出 `search_term` 造一個只填 `release_title` 的 `SeriesClues` 去呼叫
  `search_terms`，靠「空標題正規化後跳過」成立（判斷題，輕微）；留著——`SeriesClues.title` 的註解寫明讀不到是
  空字串，抽一支私有函式只為這一處不划算。其餘兩條（測試註解指向已刪程式碼、plan 欄位順序）已改。
