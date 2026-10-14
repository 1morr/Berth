# 83c — 照作品名搜：三個字以下的中文名也要算「對得上名字」

**Status:** needs-triage

**Blocked by:** None — can start immediately

**讀:** 票 83b 的 Comments 與 `.scratch/m4/search-typed-filter-shape.md`〈已知的代價〉；`berth/parser/title.py` 的 `mentions`、`_MIN_CONTAINED`、
`typed_fits` / `_contains_words`；`berth/services/search.py` 的 `_judge`；brief §20.20

## 為什麼（2026-10-14 票 83b 實跑發現）

《無間道》照作品名搜（`Infernal Affairs`、`無間道` 兩個查詢）：dmhy 的 `無間道 III [国语中字.高清无水印]`、`[无间道I][国语中字…]` 這類只寫中文名的
發佈全歸「名字對不上」，預設看不到。原因是 `mentions` 的長度下限 `_MIN_CONTAINED = 4` 算的是正規化後的字數，「無間道」「无间道」只有三個字，
整個名字被略過（下限是為了拉丁字的 `Up` 出現在半數發佈名裡）。

票 83b 在自己打關鍵字那條路上已經用 `_contains_words`（有 CJK 不設下限、不到四字的拉丁字要整詞相等）解決同一件事，但票面規定照作品名搜的六類不改，
所以這裡留著。

## 做什麼（待 triage 時定）

- `mentions` 的長度下限改成與 `_contains_words` 同一個規則，或直接共用它。
- `mentions` 現在只有搜尋的 `_judge` 在用（2026-10-14 查），改的是解析器模組，照規矩跑 `berth bench`；`auto_wrong` 不得上升。
- 一兩個字的中文名（`她`、`寄生`）會不會讓熱門清單對得上，要看實際語料再定。

## 驗收

- [ ] 《無間道》照作品名搜時 `無間道 III [国语中字]` 不再是「名字對不上」；pytest
- [ ] `berth bench` 前後比較寫在 Comments，`auto_wrong` 不上升

## Comments
