# 進度

工作單位是票（`.scratch/<里程碑>/issues/NN-slug.md`），狀態在票的 `Status:` 行。這裡只記各里程碑的閱讀指引、session 紀錄、偏差與決定。

M0–M5 已驗收，只留進行中的里程碑在本檔。M0–M5 的 session 紀錄與偏差在 `docs/archive/<里程碑>.md`（`m0`、`m1`、`m1.5`、`m2`、`m3`、`m4`、`m5`）；舊文件與舊票指到「progress.md 的偏差與決定」的，到那裡找。

## 里程碑與閱讀指引

| 里程碑 | 票目錄 | 拆票前讀 | 備註 |
| --- | --- | --- | --- |
| M0 | `.scratch/m0/issues/` | — | 已驗收（2026-09-08），封存於 `docs/archive/m0.md` |
| M1 | `.scratch/m1/issues/` | — | 已驗收（2026-09-17），封存於 `docs/archive/m1.md` |
| M1.5 | `.scratch/m1.5/issues/` | — | 已驗收（2026-09-19），封存於 `docs/archive/m1.5.md` |
| M2 | `.scratch/m2/issues/` | — | 已驗收（2026-09-24），封存於 `docs/archive/m2.md` |
| M3 | `.scratch/m3/issues/` | — | 已驗收（2026-09-26），封存於 `docs/archive/m3.md` |
| M4 | `.scratch/m4/issues/` | — | 已驗收（2026-10-23），封存於 `docs/archive/m4.md` |
| M5 | `.scratch/m5/issues/` | — | 已驗收（2026-10-28），封存於 `docs/archive/m5.md` |
| M6 | `.scratch/m6/issues/` | plan §11.7；brief §14、§6.10 | 人工接管開關與背景 AI 任務（含 Issue）、影子模式（2026-10-27 改） |
| M7 | `.scratch/m7/issues/` | plan §11.8；brief §14、§16.2 | Discord 與 MCP（2026-09-22 加入、09-24 加 MCP、10-27 改名） |
| docs-diet | `.scratch/docs-diet/issues/` | `.scratch/docs-diet/spec.md` | 文件瘦身，不改產品程式碼（使用者 2026-10-30）。同日拆成 16 張票：01 → 07 → 02 → 06 → 03a → 03b → 04a → 04b、04c → 05a–05e → 08 |

拆票：每個里程碑開頭跑 `/to-tickets docs/plan.md` 並指定里程碑；每張票要寫「讀：plan §x、brief §y」與驗收條件。plan §11 是拆票的輸入與驗收來源，拆票後以票為準。

## 寫法與封存

- session 紀錄一列、偏差一條都 ≤ 200 字（整行的字元數，Python `len`）。細節放票的 `## Comments` 或 `docs/research/`，這裡只寫結論與連結。
- 每列、每條標里程碑：票欄寫 `<里程碑> <票號> <短標題>`（沒有票的工作省略票號），偏差寫 `- <日期> <里程碑> 票 <NN>：…`。
- 偏差只記跨票的決定：推翻 plan / brief、改流程、影響後續的票。票內取捨記在票的 `## Comments`。
- 大小：整檔 ≤ 20,000 字（`CLAUDE.md` ≤ 6,000 字），由 `tests/unit/test_reading_budget.py` 守。超過時，把進行中里程碑較舊的列與條也封存到 `docs/archive/<里程碑>.md`（同下面的做法），不要縮短措辭湊數。
- 只留進行中的里程碑：驗收票收尾時，把那個里程碑的列與條搬到 `docs/archive/<里程碑>.md`，用 `scripts/docs_moved_lines.py` 證明沒丟（遺失 0），里程碑表那一列改成「已驗收（日期），封存於 `docs/archive/<里程碑>.md`」。

## Session 紀錄

| 日期 | 票 | 結果 | 下一步 |
| --- | --- | --- | --- |
| 2026-10-30 | docs-diet 拆票 | 重量文件後拆成 16 張票（`.scratch/docs-diet/`），規則在 spec.md；03、04、05 按章節再拆，加 08 收尾 | `/implement .scratch/docs-diet/issues/01-progress-archive.md` |
| 2026-10-30 | docs-diet 01 progress.md 封存 M0–M5 | 314 列、1,189 條搬到 `docs/archive/`（遺失 0 行）；寫法與上限由 `test_progress_rules.py` 守；CLAUDE.md 流程第 1、4、5 步改好 | `/implement` 票 07 |
| 2026-10-30 | docs-diet 02 plan §11.1–§11.6 封存 | 六節搬到 `docs/archive/`（遺失 0 行），plan 留標題加一行；遺留 11 條歸 §11.9，判不出的列在票 Comments 問使用者 | `/implement` 票 07 |
| 2026-10-30 | docs-diet 04a brief §19 改成 ADR | 54 列判定完：32 列寫成 16 篇 `docs/adr/`，20 列正文已有、2 列被取代；原文封存進 `docs/archive/`（遺失 0 行）；§19 留 ADR 索引；正文加 ADR 連結 | `/implement` 票 04b |
| 2026-10-30 | docs-diet 06 development.md 拆分 | 834 行拆成主檔 152 行加 `docs/development/` 五個子檔（遺失 0 行；工具改成忽略連結的 `../` 深度）；引用改指子檔，連結檢查涵蓋子檔 | `/implement` 票 03a |
| 2026-10-30 | docs-diet 07 閱讀預算閘門 | `test_reading_budget.py` 守 CLAUDE.md ≤ 6,000 字、progress.md ≤ 20,000 字；雙向變異（補到上限 + 1 紅、重排不紅）跑過；做法寫進〈寫法與封存〉 | `/implement` 票 03a |
| 2026-10-30 | docs-diet 03a brief §20.1–§20.7 壓縮 | 七節留結論加來源，細節搬進 `docs/research/`（三個新檔、四個補〈從 brief 搬來〉；遺失 0 行）；brief 1,875 → 1,615 行；§20.7 只縮 11% | `/implement` 票 03b |
| 2026-10-30 | docs-diet 03b brief §20.8–§20.24 壓縮 | 十七節留結論加來源，細節逐字搬進 `docs/research/`（四個新檔、十一個補段；遺失 0 行）；§20 846 → 696 行，brief 1,615 → 1,465 行；§20.10、§20.22 不動 | `/implement` 票 04b |
| 2026-10-30 | docs-diet 04b brief §0–§9 去歷史 | 歷史標記 43 → 0，455 行 54.5 KB → 549 行 52.4 KB（長段拆清單）；標題與號碼不變；對照表與 8 條舊有矛盾（Issue 14 vs 19 種等）在票 Comments 問使用者 | `/implement` 票 04c |
| 2026-10-30 | docs-diet 05a plan §0–§2 去歷史 | §0–§2 歷史標記 118 → 0；照 `berth/models/` 補通知、週報、`duplicate_of` 等缺的欄位；Spec 軸比對補回 6 項；對照表在票 Comments | `/implement` 票 05b |
| 2026-10-30 | docs-diet 05b plan §3–§5 去歷史 | §3–§5 歷史標記 79 → 1；長表格列拆成條列；`AiPlanner` 與數個識別符照程式修正；Spec 軸比對補回 5 項；對照表在票 Comments | `/implement` 票 05c |

## 偏差與決定

實作中推翻 plan / brief 的事，一行一條，附 commit hash 與改動的章節。

- 2026-10-30 docs-diet 拆票：**plan 與 brief 的章節號不改、不重排**（`berth/`、`web/` 引用數百處、這輪不改程式碼）；整節搬走留標題指向 `docs/archive/`。
