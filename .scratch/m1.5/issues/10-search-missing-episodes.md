# 10 — 缺集一鍵搜

**Status:** done

**Blocked by:** 08

**讀:** plan §6（search 群組）、§8.4（索引站 adapter 與查詢名）、§11.2b（M1 帶過來的 critique 那一段）；brief §6.9
（benchmark）；`.scratch/m1/search-results-shape.md`；`.scratch/m1.5/media-detail-shape.md`

## 做什麼

季表已經知道缺哪幾集，搜尋卻仍從作品名開始（plan §11.2b）。從季表的缺集直接開始搜尋：

- **查詢由後端產生**，前端不重算——`GET /search/queries` 先給看會拿哪幾個名字去問，這條規則只能有一份實作
  （plan §6）。缺整季、缺幾集、缺一集時要問什麼（季包、單集、動漫的絕對編號），用測試先寫出來再實作。
- 結果表照舊：送單、預估季集、Tags 都不變。

按鈕放在哪、一次搜一季還是勾選幾集，照票 08 的 shape。

## 驗收

- [x] 季表上有缺集時可以直接開始搜尋；沒有缺集時不出現這個入口
- [x] 查詢由後端依缺的季集產生，`/search/queries` 的預覽照實顯示；單元測試涵蓋整季、數集、單集與有絕對編號的作品
- [x] 搜尋結果照舊可以送單（playwright 走一次：缺集 → 搜尋 → 送單確認）
- [x] 改到解析器時跑 `berth bench`，`auto_wrong` 不升並貼輸出
- [x] plan §6 的 search 群組同步改
- [x] 390px 與深淺兩主題；鍵盤可完成；zh-Hant 與 en 並列
- [x] lint / type / test 全綠並貼指令輸出

## 記號規則（使用者 2026-09-19 拍板）

查詢是**標題 × 記號**，上限仍是 `MAX_QUERIES = 5`，展開時**標題優先**（第一個標題先問完它的每一個記號，
缺的每一集才至少都被問過一次）：

| 缺的形狀 | 記號 | 例 |
| --- | --- | --- |
| 整季缺（那一季播出了的每一集都缺） | `S03` | `Frieren: Beyond Journey's End S01` |
| 缺幾集 / 缺一集，該集有絕對編號 | 兩位數絕對編號 | `SPY x FAMILY 26` |
| 缺幾集 / 缺一集，沒有絕對編號 | `S03E05` | `The Bear S03E05` |
| 記號超過 5 個 | 整批收成季記號 | `The Bear S03` |
| 季記號也超過 5 個（六季以上有缺） | 退回作品名（`search_titles`） | `Long Show`、`Long Show Season 6` |

**一集只有一個記號**：兩種寫法都送的話記號數加倍，缺三集就吃掉全部配額，中文字幕組認得的那個標題一次都
問不到。絕對編號補零到兩位是照 Sonarr 的動漫查詢（`{title}+{absoluteEpisodeNumber:00}`，
`NewznabRequestGenerator.cs`）。**缺的集是零時回空的查詢**，不退回作品名——使用者按的是「搜缺的集」。

## 驗證

- `uv run pytest -q` → **1568 passed, 4 deselected**（新增：`tests/unit/test_search_missing.py` 8 條、
  `test_search.py` 的 `TestMissingEpisodes` 6 條、`test_search_api.py` 的 `TestMissingEpisodes` 4 條）。
- `uv run ruff check berth tests` → `All checks passed!`；`uv run mypy` → `Success: no issues found in 218 source files`；
  `uv run lint-imports` → `Contracts: 6 kept, 0 broken.`
- `pnpm -C web test --run` → **430 passed**（含 code-review 之後補的那一條）；`pnpm -C web typecheck` / `lint` /
  `format:check` 皆通過（`All matched files use Prettier code style!`）。
- `uv run berth bench` → `auto_wrong` **0**（不變）、`auto_correct` 172、`high: 0/84 wrong`、`medium: 0/88 wrong`。
  解析器這一輪沒有改，跑它是為了證明沒有旁及。
- **playwright 實跑**（`--scenario long-lists`，真 TMDB）：葬送的芙莉蓮 `/media/tv:209867`
  - 工具列「搜這部作品缺的集」→ 預覽與五條纜繩都是 `… S00` / `… S01`（兩季都整季缺），焦點落在 `h2`「搜尋 torrent」。
  - S01 展開區第一行「搜 S01 缺的集」→ 只問 S01 的五個關鍵字，纜繩與預覽一字不差。
  - 結果列送單：選 Anime → 確認送單（印出資料夾名）→「已送出 · 看下載列表」。入庫之後 S01 的缺集由 38 掉到 10
    （`imported: 28`），預覽跟著重算——缺哪幾集跟著帳本走，不是跟著快照走。
  - 鍵盤：從「只看缺集」Tab 一次到「搜這部作品缺的集」，Enter 就搜，焦點到 `h2`。
  - 對比：亮色 314 個文字節點最差 **5.71:1**、深色 314 個最差 **6.53:1**（皆 ≥ 4.5）。
  - 390px：`scrollWidth == clientWidth == 375`（無頁面層級橫向捲動），三顆新按鈕都在畫面內、高 24px。
  - EN 介面：`Search for the missing episodes` / `Search for what S01 is missing` / `Search by title instead` /
    `Berth will ask for the episodes this title is missing:`。

## code-review（兩軸，基準 637152c）

**Spec 軸抓到一個真缺陷並修掉**：`SearchPanel` 的 mutation 從 render 的 closure 讀 `keyword`，而季表那兩顆按鈕
在同一個 tick 裡 `setKeyword('')` 之後就 `mutate()`——先打字再按缺集時，送出去的可能是上一個關鍵字，而 `q` 有值時
後端只問那一個（票 08），畫面上的預覽就成了謊話。**實測目前那條路徑沒有真的送錯**（react-query 在替身環境下取到的是
清空後的那一份），但它靠的是 render 時序不是結構：改成把 `q` 與範圍都當 mutation 的參數傳，並補一條測試
（「先打了關鍵字再按缺集」）釘住。

其餘處理：

- **Standards 硬違規**：`web/src/i18n/resources.ts` 的 en 區塊縮排壞掉，`pnpm format:check` 紅（CI 有這道閘門）。
  已 `pnpm format` 修好，並把 `format:check` 加進上面的驗證清單——這一輪原本漏跑它。
- `_title_order()`：`search_titles` 與 `missing_queries` 各寫一次標題優先序，抽成一份。
- `berth/api/search.py` 的 `_check` → `_refuse_bare_season`（本 repo 拒絕用 `_refuse*`，見 `api/jobs.py`）。
- `SearchPanel` 的 `ref` 由選配改成必填：ref 沒接上時 `search.current?.searchMissing()` 會靜默什麼都不做。
- **brief §20.10**（新）：Sonarr 怎麼替一集組查詢，附 `NewznabRequestGenerator.cs` 來源——票的記號規則引用了它，
  而「brief 沒寫的先查再用，查到的補進 §20」是規矩。
- **plan §8.4**：補一句 Specials——`S00` 幾乎沒有發佈這樣命名，但不排除它，因為工具列數的缺集本來就含 S00。
- **shape 同輪補**：`.scratch/m1.5/media-detail-shape.md` §5 的「搜尋區塊（改的只有兩處）」加上第三處（缺集模式的
  引言與「改回作品名搜尋」），Spec 軸指出加了東西就該同輪改 shape。
- **保留、不改**：`missing` + `season` 在後端是兩個參數而前端是一個 `MissingScope`（API 上是兩個查詢參數，
  非法組合由 422 擋）；`season_without_missing` 與「缺集搜尋不走 tmdbid」雖然票沒寫，但前者是不默默給錯答案、
  後者是驗收第 2 條（預覽照實顯示）的前提。

## Comments

- **shape 沒寫、這一輪加的一件**：搜尋區塊在缺集模式下多一顆「改回作品名搜尋」（`search.missingOff`）。
  shape §4 只說「關鍵字預覽換成後端給的那幾個」，沒有說怎麼回去——沒有出口的話，按進來之後只剩重整一招。
  已記進 progress.md 的「偏差與決定」。
- **`season` 單獨帶著是 422 `season_without_missing`**：它是「缺集搜尋收到那一季」的參數，默默當成整部作品搜
  會讓手改網址的人拿到他沒有要的那一份，而畫面上沒有任何地方說得出差別。
- **缺集搜尋不走 tmdbid**：端點認得 tmdbid 時整批換成一個 id 查詢（票 08），但 id 找的是整部作品，收窄就沒了，
  而預覽已經說了要問那幾集。實測十個預設公開站一個都不支援，所以這條路平常走不到。
- **沒有做、留給後面的**：
  - 缺的集散在六季以上時只退回作品名，不分批問。要做的話得讓一次搜尋發超過 5 個查詢，而上限是為了不要替
    使用者把那些公開站打到封 IP（plan §8.4）。
  - 勾選幾集再搜（票寫的「一次搜一季還是勾選幾集」的另一半）：入口照 shape 走「整部 / 一季」兩顆，沒有逐集勾選。
  - 缺集模式不寫進網址，與「只看缺集」同一個理由（票 09）。
