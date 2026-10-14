# 83b — 自己打關鍵字的搜尋：分出「對得上」與「對不上」，熱門清單不再壓在上面

**Status:** done

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

- [x] shape 稿使用者確認過，路徑寫在 Comments
- [x] 打「無間道」：The Pirate Bay 的熱門清單歸「對不上」；`無間道 III [国语中字]`（含打的字）與 `[心叶荐] 无间道_Infernal Affairs`（只含作品的簡體名／英文名）都歸「對得上」；pytest 守，兩條規則各做變異驗證（拿掉一條就紅，改無關的命名不紅）
- [x] 沒有快照時只看打的字；pytest
- [x] 筆數加得起來、回應有上限；pytest
- [x] 按鈕開關、預設只開「對得上」、對不上那一句（兩種語言）、只看某個站；vitest
- [x] 照作品名搜的六類行為不變（既有測試照舊綠）
- [x] Playwright 實跑：《無間道》打「無間道」與照作品名各搜一次，1280 與 390 寬截圖；用隔離環境，**不准碰使用者的 `berth-local`**
- [x] brief §20.20、plan §8.4 的「自己打的關鍵字一律 `unjudged`」改寫；progress.md「偏差與決定」記一行（推翻票 83 shape〈自己打關鍵字〉）
- [x] 全部檢查、pytest、vitest、前端 e2e 綠；`pnpm gen:api` 有差異的話 CHANGELOG 寫明；progress.md 已更新

## Comments

### 決定

- **shape**：`.scratch/m4/search-typed-filter-shape.md`，2026-10-14 使用者確認。三題選定：
  短字規則「有 CJK 不設長度下限、不到四字的純拉丁字要整詞相等；第二條（作品名）在這條路上用同一個規則，`mentions` 不動」——
  照搬 `_MIN_CONTAINED` 的話票面的「無間道」（三個字）本身就判不出對得上，簡體名「无间道」也永遠不算；
  鍵名 `typed_match` / `typed_miss`、**刪 `unjudged`**（沒有快照時也照第一條判，照作品名搜沒有快照時本來就是 `NO_QUERY`）；
  文案「對得上／對不上」（Matches / No match）。
- **照誰的慣例**：Prowlarr 手動搜尋頁（打字搜、預設 `all`、只有使用者自建的 `title` 字串篩選，沒有拿發佈名比查詢的判斷，原始碼查證寫進 brief §20.20）、
  票 83 已查的 Sonarr 互動搜尋。
- **API**（`GET /api/search`，SPA 是唯一消費者，CHANGELOG 已寫）：`verdict` 多 `typed_match`、`typed_miss`，拿掉 `unjudged`；`evidence` 兩類都是空字串，
  「對不上」那一句引的是前端送出去的那串字（`search.variables.q`，不是欄位裡現在的字）。
- **拿掉 shape 稿「沒有快照時只說打的字」那個句子變體**：前端分不出這一次有沒有快照。
- **預設開著的是「這一次搜尋的第一類」**（`verdictsOf(typed)[0]`），不是一份同時含 `fits` 與 `typed_match` 的常數：後者讓「關掉符合」之後集合不是空的，
  「沒有選任何一類。」就不出來（vitest 抓到）。

### 變異驗證（手動跑過、測試裡守著）

- parser（`test_parser_title.py::TestTypedFits`）：拿掉第一條（打的字）→ 5 紅；拿掉第二條（作品名）→ 2 紅；CJK 也套 `_MIN_CONTAINED` → 3 紅；
  短拉丁字不要求整詞 → 2 紅；只改區域變數名 → 全綠。
- services（`test_search.py::TestTypedKeyword`）：`_LISTED` 不含 `typed_match`（對得上只送 50 筆）→ 1 紅；`_judge_typed` 不把快照傳下去 → 1 紅；改區域變數名 → 全綠。
- 前端（`SearchPanel.test.tsx` 票 83b 那一組）：預設全開 → 4 紅；對不上那一句引 `row.evidence` → 2 紅；按鈕數字不跟站別 → 1 紅；
  對得上是 0 時用照作品名搜那一句 → 2 紅；改區域變數名 → 全綠。

### berth bench

改動後 `overall 904 files · auto_correct 253 · auto_wrong 0 · review 86`；high 0/112、medium 0/141 wrong——與票 83 記的改動前相同（`typed_fits` 不在 bench 的路徑上）。

### 實跑（隔離環境）

compose 專案 `berth-t83b`：只有一台 Prowlarr（`berth-t83b-prowlarr`、port 19786、named volume、網路 10.86.0.0/16、`restart: "no"`），
加 The Pirate Bay、dmhy、Mikan。Berth 是這個工作樹的 `fake_setup_server.py --scenario search --port 8583`（真 TMDB、真 Prowlarr，`web/dist` 重新 build）。
跑完 `down -v`；`berth-local` 四個容器全程 Exited、沒碰。截圖在 `.playwright-mcp/t83b/`（`typed-1280`、`typed-miss-open-1280`、`typed-390`、`title-1280`、`title-390`）：

- 《無間道》打「無間道」：索引站回了 104 筆，**對得上 4 · 對不上 100**。對得上的 4 筆都是 dmhy：`[心叶荐][130603][OS] 无间道_Infernal Affairs 精选辑 AAC`（只靠簡體名／英文名）、
  `無間道 III [国语中字.高清无水印]`、`[RMVB/1.03GB]無間道 II  Infernal Affairs Trilogy`、`[无间道I][国语中字…]`。按「對不上」列出 50 筆（上限那一行在），
  Avira、Spider-Man、Obsession……每一列「發佈名裡沒有「無間道」，也沒有這部作品的名字。」
- 照作品名搜（`Infernal Affairs`、`無間道`）：符合 50 · 年份不符 1 · 只對上部分名字 30 · 名字對不上 102，加 2 筆重複 = 185，六類行為照舊。
- 390 寬兩次都沒有橫向捲動；按鈕列、站別一列、排序一列照票 83。

### critique / polish

看兩種寬度的截圖：「對得上」列不塗漆、「對不上」是中性色塊加一句 `ink-dim`、空狀態與上限那一行照票 83。沒有要改的。

### code-review（Standards、Spec 兩軸 opus）處理掉的

`_holds` 改名 `_contains_words`、`FilteredResults` 的 `kinds` 改名 `verdicts`（Standards）；DESIGN.md〈搜尋結果的篩選〉補自己打關鍵字那一段（Spec）；
Spec 推出的三個邊角寫進 shape 稿〈已知的代價〉：作品名太短時第二條也會讓熱門清單對得上（`It`、`Up`）、打好幾個詞時整串比
（`Infernal Affairs 1080p` 只靠作品名救）、打純西里爾／希臘／泰文時正規化後什麼都不剩，每一筆都對不上。

### 未處理

- `_word_run` 與既有的 `_words` 切詞方式相同、只差丟不丟短詞：要的正是短詞，沒合。
- 「預設列出的那一類」散在後端 `_LISTED`、前端 `isListed`、`verdictsOf(...)[0]`、`empty()` 四處（Repeated Switches）：與票 83 的結構相同，沒收。
- `typed` 從 `FilteredResults` 穿過 `SearchResults`、`ResultRow` 到 `VerdictNote`（Data Clumps）：放進 `evidence` 會違反「發佈名裡的那一段字」的定義，照現在的傳法。
- `onlyTypedMiss` 的句子直接寫了按鈕名「對不上」／“No match”，沒引用 `search.verdict.typed_miss`：與 `onlyOthers` 同一種寫法。
- 照作品名搜時三個字的中文名不算（`mentions` 的下限）：另開票 83c。
