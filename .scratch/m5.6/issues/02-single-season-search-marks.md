# 02 — 只有一季的作品，整季缺時問得到動畫站

**Status:** done

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

- [x] 會紅的測試先 commit 或寫在 Comments，修完轉綠
- [x] 實測腳本在 `scripts/experiments/`，brief §20 有結果與來源，plan §8.4 的查詢規則跟上
- [x] 多季作品與缺幾集的查詢不變（既有測試綠，必要時補）
- [x] 動 `parser/` 時 `berth bench` 的 `auto_wrong` 不升（貼數字）——沒動 `parser/`，不適用
- [x] 全部檢查、pytest 綠；progress.md 已更新

## Comments

- **紅的證據**（修法之前，`c0de5757` 的 `missing_batches`）：
  - `missing_batches(("私を喰べたい、ひとでなし",), 整季缺的 S01)` → `('私を喰べたい、ひとでなし 第1季',)`
  - `missing_batches(("Death Note",), …)` → `('Death Note S01', 'Death Note Season 1')`
  - 測試先寫、先紅：`tests/unit/test_search_missing.py` 加參數後在舊碼上 11 failed／4 passed（`TypeError: unexpected keyword argument`），修完 16 passed。實測那兩句查詢在 Mikan、dmhy、ACG.RIP 都是 0 筆（brief §20.28）。
- **選了「作品只有一季時不加記號」**，不是「第 1 季另送不帶記號的名字」：2026-11-07 實測（`scripts/experiments/single_season_marks.py`）只有一季的作品帶記號在 Mikan／dmhy／ACG.RIP 零筆，名字本身整季都回得來；多季作品的第 1 季記號在 dmhy 仍有 18 筆，另送不帶記號的名字會把其他季撈進來、也多吃 `MAX_QUERIES`。Nyaa 這台機器連不上（DNS／SSL），如實記錄。
- **修在 `missing_batches`，不是 `season_tokens`**：按搜尋的季是使用者自己開的（「不指定季」預設開著），要問哪一季由他決定；`season_tokens` 照舊是共用的記號產生器。docstring 已寫。
- **「只有一季」看播過的季**（`has_one_aired_season`）：特別篇 `S00` 不算一季，TMDB 已公告但一集都還沒播的下一季也不算——否則只有一季的番只要 TMDB 建了下一季那一列就回到舊行為。分批之後只看得到後面的季，所以由呼叫端看整份季表。
- `MAX_QUERIES` 與分批規則沒動；多季作品與缺幾集的查詢照舊（既有測試綠，另加對照測試）。
- 沒動 `parser/`，所以不用跑 `berth bench`。
- 驗證：`uv run pre-commit run --all-files` 全過；`uv run pytest -n auto` 5724 passed, 1 skipped（85.65s）。
- 一併把兩支實驗腳本重複的 `norm`／`name_hit`／`search` 收進 `scripts/experiments/lib.py`（`norm_title`、`name_hit`、`prowlarr_search`）。

### Code review

- **Spec**：整合測試改用票上的 CJK 作品並加特別篇（守服務層的季數判斷）；判準從「季表有幾列」改成「播過的季」；brief §20.28 拿掉 Mikan「`Season N` 有效」的過度解讀、補多季 CJK 在 Mikan 的殘留與量測限制；plan §8.4 措辭跟上；README 與 `docs/development/experiments.md` 的查詢次數 13 → 12。
- **Standards**：`single_season` 與 CONTEXT.md 的 Mapping Strategy 同名不同義，改 `one_season_work`；「不接記號」不再用空字串哨兵，`_mark_queries` 直接回查詢；重複的三個輔助函式收進 `lib.py`。
