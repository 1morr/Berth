# 83c — 照作品名搜：三個字以下的中文名也要算「對得上名字」

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** 票 83b 的 Comments 與 `.scratch/m4/search-typed-filter-shape.md`〈已知的代價〉；`berth/parser/title.py` 的 `mentions`、`_MIN_CONTAINED`、
`typed_fits` / `_contains_words`；`berth/services/search.py` 的 `_judge`；brief §20.20

## 為什麼（2026-10-14 票 83b 實跑發現）

《無間道》照作品名搜（`Infernal Affairs`、`無間道` 兩個查詢）：dmhy 的 `無間道 III [国语中字.高清无水印]`、`[无间道I][国语中字…]` 這類只寫中文名的
發佈全歸「名字對不上」，預設看不到。原因是 `mentions` 的長度下限 `_MIN_CONTAINED = 4` 算的是正規化後的字數，「無間道」「无间道」只有三個字，
整個名字被略過（下限是為了拉丁字的 `Up` 出現在半數發佈名裡）。

票 83b 在自己打關鍵字那條路上已經用 `_contains_words`（有 CJK 不設下限、不到四字的拉丁字要整詞相等）解決同一件事，但票面規定照作品名搜的六類不改，
所以這裡留著。

## 使用者拍板（2026-10-19）

**含 CJK 的名字至少 2 個字才拿來比（包含即可）**；1 個字的照舊略過。拉丁字維持現狀（不到
`_MIN_CONTAINED` 不比）。理由：一個字的中文名（`她`）幾乎什麼發佈名都含，會把無關的發佈判成對得上；
兩個字以上已涵蓋《無間道》《寄生》這類。一字名的作品照作品名搜仍看不到，要改用自己打關鍵字（83b 那條路）。

## 做什麼

1. **`mentions`**（`mattpocock-skills:tdd`）：CJK 名字的下限從 `_MIN_CONTAINED`（4）改成 2；拉丁字照舊。
   不改 `_contains_words`（自己打關鍵字那條路，83b 定的「CJK 不設下限」維持）。
2. **`partial_title`**（衍生劇判斷，`title.py` 找「包住某個名字」的 `wider` 那一段）：CJK 用同一個下限 2。
   不跟著改的話，`無間道前傳` 這類會被 `mentions` 判成對得上、卻不被 `partial_title` 標成衍生劇，直接混進正片。
3. **不動** `_compare`（`matches()` 的計分，RSS 與入庫用的那一支）：那是自動決策路徑，這張票只改搜尋的粗篩。
4. 改的是解析器模組：照規矩跑 `berth bench`，`auto_wrong` 不得上升；前後數字寫進 Comments。
5. 用實際語料抽查：至少《無間道》與一部兩字中文名的作品照作品名搜，看「對得上」裡有沒有明顯無關的發佈。
   兩字名誤判明顯偏多時，停下回報（附例子），不要自行改門檻。

## 驗收

- [ ] 《無間道》照作品名搜時 `無間道 III [国语中字]` 不再是「名字對不上」；pytest
- [ ] 一個字的中文名照舊不算對得上，兩個字的算；pytest 各一條
- [ ] 名字只對上一部分的兩、三字中文名（例如 `無間道前傳` 之於《無間道》）被 `partial_title` 標成衍生劇；pytest
- [ ] `berth bench` 前後比較寫在 Comments，`auto_wrong` 不上升

## Comments
