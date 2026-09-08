# 05 — 解析器骨架：benchmark、檔案分類與發佈名解析

**Status:** ready-for-agent

**Blocked by:** 01（季集來源決定 fixture 的 `expected` 與快照形狀）

**讀:** plan §4.1（classify / normalize_cjk / parse_release / structure_hints）、§4.2、§4.6、§10；
brief §6.1、§6.2、§6.3、§6.8、§6.9、§20.4

## 做什麼

`berth bench` 跑得起來並輸出報表；20 筆真實 torrent 語料與凍結的 TMDB 快照就位；檔案分類、
CJK 正規化、發佈名解析與 Tags 渲染實作到位。

順序照 `docs/progress.md` 的 M1 閱讀指引：**先寫 fixture 與 harness 再逐階段實作**。
benchmark fixture 就是 TDD 的紅燈（`mattpocock-skills:tdd`）。

語料來源見 brief §20.4 的樣本清單：動漫 8、美劇 / 韓劇 8、電影 4。這一票只要求分類與 ReleaseInfo
正確，季集對應是票 06、目標路徑是票 07，所以此時 benchmark 大量落在 review / unmatched 是預期的。

## 驗收

- [ ] `tests/fixtures/parser/` 有 20 筆語料（動漫 8、美劇 / 韓劇 8、電影 4），格式同 plan §4.6，
      每筆附 `source_url`
- [ ] `tests/fixtures/tmdb/` 有對應快照，錄一次即凍結（不在測試裡打外部）
- [ ] `berth bench` 輸出整體與分類別（anime / tv / movie）的 `auto_correct`、`auto_wrong`、`review`、
      `unmatched_correct`、`extra_correct`，high 與 medium 的錯誤率分列
- [ ] `tests/fixtures/parser/baseline.json` 建立；CI 有門檻檢查（`auto_wrong` 不得高於 baseline、
      `auto_correct` 不得低於 baseline 減 1 筆）
- [ ] `classify` 對 20 筆語料的 kind 全對，含 `sample`（檔名含 sample 且 < 同目錄最大影片 10%）、
      `extra`（brief §6.2 的關鍵字與資料夾）、`disc` 的判定
- [ ] `normalize_cjk` 抽出 `CjkHints` 的每個欄位，brief §6.2 列的每一種前綴與標記各有單元測試
- [ ] `parse_release` 產出 `ReleaseInfo`；動漫六種集號模式（`- 01`、`[01]`、`01v2`、`E01` 無季、
      `01-12` 區間、`第01話`）各有測試
- [ ] `Tags.render()` 依 brief §6.8 的順序與 token，`subs` 依 `CHS < CHT < JP < EN` 排序後以 `+` 連接
- [ ] `parser/` 與 `naming/` 沒有任何 IO，import-linter 契約涵蓋
- [ ] `berth bench` 寫進 README 的指令段
- [ ] lint / type / test 全綠並貼指令輸出
