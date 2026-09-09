# 05 — 解析器骨架：benchmark、檔案分類與發佈名解析

**Status:** done

**Blocked by:** ~~01（季集來源決定 fixture 的 `expected` 與快照形狀）~~ 已解除

**讀:** plan §4.1（classify / normalize_cjk / parse_release / structure_hints）、§4.2、§4.6、§10；
brief §6.1、§6.2、§6.3、§6.8、§6.9、§20.4

## 做什麼

`berth bench` 跑得起來並輸出報表；20 筆真實 torrent 語料與凍結的 TMDB 快照就位；檔案分類、
CJK 正規化、發佈名解析與 Tags 渲染實作到位。

順序照 `docs/progress.md` 的 M1 閱讀指引：**先寫 fixture 與 harness 再逐階段實作**。
benchmark fixture 就是 TDD 的紅燈（`mattpocock-skills:tdd`）。

票 01 量到一個 `normalize_cjk` 必須處理的寫法：**季號的全形羅馬數字**（`无职转生Ⅱ`、`Ⅲ`，
U+2160 起）與**不以空白收邊的半形羅馬數字**（`Mushoku Tensei II]`）。漏掉這兩種會讓整輪播出
被錯置成第一季（plan §4.1、`docs/research/anime-episode-source.md` §6.1）。

語料來源見 brief §20.4 的樣本清單：動漫 8、美劇 / 韓劇 8、電影 4。這一票只要求分類與 ReleaseInfo
正確，季集對應是票 06、目標路徑是票 07，所以此時 benchmark 大量落在 review / unmatched 是預期的。

## 驗收

- [x] `tests/fixtures/parser/` 有 20 筆語料（動漫 8、美劇 / 韓劇 8、電影 4），格式同 plan §4.6，
      每筆附 `source_url`
- [x] `tests/fixtures/tmdb/` 有對應快照，錄一次即凍結（不在測試裡打外部）
- [x] `berth bench` 輸出整體與分類別（anime / tv / movie）的 `auto_correct`、`auto_wrong`、`review`、
      `unmatched_correct`、`extra_correct`，high 與 medium 的錯誤率分列
- [x] `tests/fixtures/parser/baseline.json` 建立；CI 有門檻檢查（`auto_wrong` 不得高於 baseline、
      `auto_correct` 不得低於 baseline 減 1 筆）
- [x] `classify` 對 20 筆語料的 kind 全對，含 `sample`（檔名含 sample 且 < 同目錄最大影片 10%）、
      `extra`（brief §6.2 的關鍵字與資料夾）、`disc` 的判定
- [x] `normalize_cjk` 抽出 `CjkHints` 的每個欄位，brief §6.2 列的每一種前綴與標記各有單元測試
- [x] `parse_release` 產出 `ReleaseInfo`；動漫六種集號模式（`- 01`、`[01]`、`01v2`、`E01` 無季、
      `01-12` 區間、`第01話`）各有測試
- [x] `Tags.render()` 依 brief §6.8 的順序與 token，`subs` 依 `CHS < CHT < JP < EN` 排序後以 `+` 連接
- [x] `parser/` 與 `naming/` 沒有任何 IO，import-linter 契約涵蓋
- [x] `berth bench` 寫進 README 的指令段
- [x] lint / type / test 全綠並貼指令輸出

## Comments

code-review（Standards / Spec 兩軸）留下的、**這一票沒有做**的事：

- **特典對不對得上 TMDB 的 season 0，目前只靠編號。** `frieren-7acg-bd-batch` 的 11 個特典
  在發佈裡是 `S00E01`–`S00E11`，TMDB 的 S0 卻把同一串「○○の魔法」排在 1,2,3,4,6,7,8,9,10,11,13
  （#5 與 #12 是別的特典）。brief §6.4 的規則是「顯式 `SxxEyy` → 直接採用並驗證該集存在」，
  照它走就是這個結果，檔名裡也沒有別的東西可以用。語料因此把這 11 筆記為 `medium` 而不是
  `high`，理由寫在 `tests/fixtures/parser/README.md`。**票 06 / 07 決定**要不要加一條靠集名或
  片長比對特典的規則；不加也要是個明說的決定。
- **語料缺兩種形狀**：`sample` 檔（掃過的 20 個真實 torrent 一個都沒有，現在的發佈幾乎不附）
  與多集檔（`S01E01E02`）。兩者的規則都有單元測試，但沒有語料。票 06 的驗收本來就要求
  「多集檔、合集、多季在語料裡各有涵蓋」，補在那裡。
- **`profile` 與 `min_confidence` 語料寫了但還沒有人讀**（`services/bench.py` 的 `Expected`
  刻意沒收它們）。票 06 的季集對應會用到 profile，信心下限也是那時候才有東西可比。
