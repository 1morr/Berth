# 01 — progress.md 封存 M0–M5，立下寫法與上限

**Status:** ready-for-agent

**Blocked by:** None — can start immediately

**讀:** `.scratch/docs-diet/spec.md`；`docs/progress.md` 只讀前 20 行與三個 `##` 標題（全文 893 KB，用腳本處理，不要整份讀）；`tests/unit/test_progress_merge.py`；`.gitattributes`；`tests/unit/test_readme_docs.py`（連結檢查）；`CLAUDE.md`〈每個 session 的流程〉

## 為什麼

`progress.md` 有 893 KB，CLAUDE.md 第 1 步要每個 session 讀它，實際讀不完。裡面 314 列 session 紀錄、1,189 條偏差全屬已驗收的 M0–M5；多數一列幾百字，偏差有一大半是票內的取捨。

## 做什麼

1. **搬移比對腳本** `scripts/docs_moved_lines.py <base-ref> <來源檔> -- <目的檔...>`：列出 `git diff <base-ref>` 裡從來源檔刪掉的每一行（去頭尾空白、略過空行與表格分隔列），檢查每行都出現在某個目的檔；印「刪 N 行、找到 N 行、遺失 N 行」並列出遺失的行，有遺失就 exit 1。後面的 02、03、06 和每個里程碑收尾的封存都用它。寫一個單元測試（找到 / 遺失兩種都測）。
2. **分類**：每列 / 每條歸到一個里程碑。
   - 明寫 `M0`…`M5`（含 `M1.5`）的照寫的。
   - 沒寫的（目前 36 列、393 條）照提到的票號對 `.scratch/<里程碑>/issues/` 的檔名；再判不出的照日期對里程碑區間（里程碑表的拆票日與驗收日）。
   - 還是判不出的，歸到日期最近的已驗收里程碑，逐條列在 Comments。
3. **搬到** `docs/archive/m0.md`…`m5.md`（共 7 檔，含 `m1.5.md`）。每檔：開頭一行說出處（從 `docs/progress.md` 封存，commit 之後填）；`## 閱讀指引`（里程碑表那一列原文）；`## Session 紀錄`（表頭 + 該里程碑的列）；`## 偏差與決定`。原文不改字，順序照原檔。
4. **progress.md 留下的**：
   - 開頭加一句「M0–M5 的 session 紀錄與偏差在 `docs/archive/<里程碑>.md`」，讓舊指標（`docs/research/`、舊票）一跳找到。
   - 里程碑表 M0–M5 每列縮成「已驗收（日期），封存於 `docs/archive/mX.md`」；原列已在第 3 步搬走。M6、M7 列不動。
   - 新增 `## 寫法與封存`（放在里程碑表之後），內容：
     - session 紀錄一列、偏差一條都 ≤ 200 字（整行的字元數，Python `len`）。細節放票的 Comments 或 `docs/research/`，這裡只寫結論與連結。
     - 每列 / 每條標里程碑：票欄寫 `<里程碑> <票號> <短標題>`，偏差寫 `- <日期> <里程碑> 票 <NN>：…`。
     - 偏差只記跨票的決定：推翻 plan / brief、改流程、影響後續的票。票內取捨記在票的 `## Comments`。
     - 只留進行中的里程碑：驗收票收尾時，把那個里程碑的列與條搬到 `docs/archive/<里程碑>.md`，用 `scripts/docs_moved_lines.py` 證明，里程碑表那一列改成「已驗收，封存於…」。
5. **擴充 `tests/unit/test_progress_merge.py`**（或另開 `test_progress_rules.py`，模組 docstring 說清楚分工）守三條：每列 / 每條 ≤ 200 字；每列 / 每條帶里程碑標記；標的里程碑在里程碑表裡不是「已驗收」。`problems()` 的 `SECTIONS` 跟著改成四段。
   - 雙向變異：造一列 201 字、一列沒標里程碑、一列標 `M4` → 各自紅；把空行加倍、改表格分隔列寫法、換兩列順序 → 不紅。怎麼變的記在 Comments。
6. **CLAUDE.md** 用 `mattpocock-skills:writing-for-agents` 改流程第 1、4、5 步：1 讀 progress.md（現在讀得完）；4 推翻 plan / brief 的同 commit 改文件並在 progress.md 偏差記一條（≤ 200 字），票內取捨記票的 Comments；5 session 紀錄一列 ≤ 200 字，驗收票多一步「封存這個里程碑」。「由測試強制」的宣稱逐條對得上第 5 步的測試。
7. **改引用**（全部改指 `docs/archive/m0.md` 或對應檔）：
   - `tests/unit/test_models.py:91`、`tests/integration/test_database.py:3`
   - `CHANGELOG.md:1820`
   - `berth/models/__init__.py:3`、`berth/migrations/versions/8b1e1dc5336b_m0_tables.py:3`：只改那一行說明文字（spec 第 5 條的例外）
   - `docs/design-brief.md`、`docs/plan.md` 裡 `grep -n 'progress\.md'` 指到已搬走內容的（例：brief 約 852 行的「M3 後的全面審查」）
   - 不改：`docs/research/`、`.scratch/` 舊票（開頭那句接住）
8. **連結檢查**：`tests/unit/test_readme_docs.py` 的檢查清單加上 `docs/progress.md` 與 `docs/archive/*.md`。
9. `.gitattributes` 的 `merge=union` 只留給 `progress.md`，archive 不加。

## 驗收

- [ ] `docs/archive/m0.md`…`m5.md` 共 7 檔存在；`progress.md` 不含 M0–M5 的 session 列與偏差條
- [ ] `scripts/docs_moved_lines.py` 有單元測試；對 `progress.md` → `docs/archive/*.md` 跑出「遺失 0」，輸出貼 Comments
- [ ] 分類判不出、按日期歸的列與條列在 Comments
- [ ] `## 寫法與封存` 寫好；測試守三條規則，雙向變異紅 / 不紅都跑過，記在 Comments
- [ ] CLAUDE.md 第 1、4、5 步改好，測試宣稱逐條對得上
- [ ] 第 7 步列的引用都改了；`grep -rn '偏差與決定' tests berth CHANGELOG.md docs/plan.md docs/design-brief.md` 沒有指到 progress.md 已搬走內容的
- [ ] 全部檢查與 test 綠；progress.md 記一列 session；commit；不 push

## Comments
