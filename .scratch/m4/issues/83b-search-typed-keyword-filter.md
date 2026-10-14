# 83b — 自己打關鍵字的搜尋：分出「對得上」與「對不上」，熱門清單不再壓在上面

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** 票 83 本文與 Comments、`.scratch/m4/search-filter-shape.md`（〈自己打關鍵字〉〈畫面〉）、`.scratch/m1/issues/08-indexer-search.md`（自己打關鍵字不篩的理由）；`berth/services/search.py`（`search_torrents`、`_judge`、`_take`、`_rows`、`_counts`、`_LISTED`、`SearchVerdict`）；`berth/parser/title.py` 的 `mentions`、`normalize_title`；`web/src/media/searchFilter.ts`、`SearchResults.tsx`；brief §20（The Pirate Bay 熱門清單、公開中文站做種數那兩條）、§20.20；plan §8.4

## 為什麼（2026-10-14 使用者）

作品頁《無間道》（電影）在關鍵字欄自己打「無間道」搜尋：104 筆，前 96 筆是 The Pirate Bay 的熱門清單
（Avira、Spider-Man、Slow Horses……），真的是無間道的 4 筆 dmhy 結果排在最底。使用者問「為什麼沒有篩選」。

原因是兩個刻意的決定疊在一起：

1. 自己打的關鍵字一律 `unjudged`：不分類、沒有篩選按鈕、全部列出（票 08、票 83 shape，2026-10-10 使用者確認）。
2. The Pirate Bay 遇到搜不到的字會回它自己的熱門清單（做種上千），公開中文站的做種是 0–2；表格預設照做種排序。

照作品名搜的路有「預設只開『符合』＋依類別分組」擋熱門清單；自己打字的路沒有這兩層，所以完全沒防住。
票 08 不判的理由（會打字多半是 TMDB 的名字搜不到，拿作品名判斷幾乎每一筆都會是「名字對不上」）仍然成立，
所以這張不讓 Berth 判斷「是不是這部作品」，只判斷「發佈名對不對得上使用者問的東西」。

## 做什麼

1. **後端分兩類**：自己打關鍵字時，每一筆是下面其中一類（鍵名在 shape 時定）：
   - **對得上**：正規化（`normalize_title`）之後，發佈名含打的那串字，**或**含這部作品的任何一個名字（`mentions`）。
     第二條是為了繁簡：打「無間道」時 `[心叶荐] 无间道_Infernal Affairs` 只靠 TMDB 的簡體名（`title_zh_cn`）與英文名才對得上，
     專案裡沒有繁簡轉換，不為這張引進 OpenCC。沒有快照時只看第一條。
   - **對不上**：兩條都沒有。
   - 打的字太短時（比照 `mentions` 的 `_MIN_CONTAINED`）第一條怎麼辦，在 shape 時定。
   - 照票 83：每類各自逐站輪流取；「對得上」送 `RESULT_LIMIT` 筆、「對不上」送 `OTHERS_LIMIT` 筆；`returned = merged + Σ counts.total` 仍加得起來。
2. **前端**：沿用票 83 的 `ToggleChips` 與分組，預設只開「對得上」；「對不上」那一列的那一句話說出原因
   （例如「發佈名裡沒有『無間道』，也沒有這部作品的名字」）。兩種語言。
   「對得上」是 0、「對不上」有東西時，照票 83 的 `onlyAside` 那一句指向按鈕。
3. **不改**：照作品名搜的六類與判定順序；自己打關鍵字仍不判年份、類型、成人、部分名字。
4. **UI 走 `/impeccable`**：先 `shape`（照誰的慣例：Prowlarr 的手動搜尋頁、票 83 已查的 Sonarr 互動搜尋），稿子給使用者確認後才實作；收尾 `critique` / `polish`。

## 不做

- 偵測「某一站整批都是熱門清單」然後把那一站藏掉：上面的逐筆判斷已經涵蓋，而且整站藏掉會連那一站碰巧對得上的幾筆一起藏。
- 繁簡轉換程式庫。
- 改排序的預設欄位。

遇到上面沒涵蓋的設計決定（鍵名與文案、`unjudged` 是否還留著給沒有快照的情況、API 形狀怎麼變）就停下回報，不自行拍板。

## 驗收

- [ ] shape 稿使用者確認過，路徑寫在 Comments
- [ ] 打「無間道」：The Pirate Bay 的熱門清單歸「對不上」；`無間道 III [国语中字]`（含打的字）與 `[心叶荐] 无间道_Infernal Affairs`（只含作品的簡體名／英文名）都歸「對得上」；pytest 守，兩條規則各做變異驗證（拿掉一條就紅，改無關的命名不紅）
- [ ] 沒有快照時只看打的字；pytest
- [ ] 筆數加得起來、回應有上限；pytest
- [ ] 按鈕開關、預設只開「對得上」、對不上那一句（兩種語言）、只看某個站；vitest
- [ ] 照作品名搜的六類行為不變（既有測試照舊綠）
- [ ] Playwright 實跑：《無間道》打「無間道」與照作品名各搜一次，1280 與 390 寬截圖；用隔離環境，**不准碰使用者的 `berth-local`**
- [ ] brief §20.20、plan §8.4 的「自己打的關鍵字一律 `unjudged`」改寫；progress.md「偏差與決定」記一行（推翻票 83 shape〈自己打關鍵字〉）
- [ ] 全部檢查、pytest、vitest、前端 e2e 綠；`pnpm gen:api` 有差異的話 CHANGELOG 寫明；progress.md 已更新

## Comments
