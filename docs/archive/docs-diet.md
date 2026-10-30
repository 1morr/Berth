# docs-diet 封存

從 `docs/progress.md` 封存（封存前最後一版是 commit `1d0efda5`）；原文不改字，順序照原檔。

## 閱讀指引

| 里程碑 | 票目錄 | 拆票前讀 | 備註 |
| --- | --- | --- | --- |
| docs-diet | `.scratch/docs-diet/issues/` | `.scratch/docs-diet/spec.md` | 文件瘦身，不改產品程式碼（使用者 2026-10-30）。同日拆成 16 張票：01 → 07 → 02 → 06 → 03a → 03b → 04a → 04b、04c → 05a–05e → 08 |

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
| 2026-10-30 | docs-diet 04c brief §10–§18 去歷史 | 歷史標記 90 → 3（只剩研究檔名）；269 行 82 KB → 545 行 75 KB；號碼不變；Spec 軸補回 8 項；對照表與 3 條矛盾（§18 的 AI 里程碑等）在票 Comments 問使用者 | `/implement` 票 05c |
| 2026-10-30 | docs-diet 05e plan §9 去歷史 | §9 歷史標記 102 行 → 0；長段拆清單，88.6 → 83.7 KB；號碼不變；Spec 軸補回 6 處；對照表與 6 條矛盾（偵測用語、`stop` 在哪給等）在票 Comments 問使用者 | `/implement` 票 05d |
| 2026-10-30 | docs-diet 05c plan §6–§7 去歷史 | §6–§7 歷史標記 253 → 2（連結檔名）；長表格列拆成每群一節；對照 `schema.d.ts` 與程式補 `/settings/ai`、`/weekly`、`setup/*` 門禁等；Spec 軸比對補回 7 項；對照表在票 Comments | `/implement` 票 05d |
| 2026-10-30 | docs-diet 05d plan §8、§10、§11.7–§12 去歷史 | 歷史標記 107 → 3（只剩研究檔名）；長段與 e2e 表格列拆成條列；錯誤映射、前端 e2e 範圍等照程式修正；Spec 軸補回 3 項；對照表在票 Comments | `/implement` 票 05e |
| 2026-10-30 | docs-diet 08 收尾驗收 | 重量、必讀範圍、評估閘門、遺留清單貼在票 Comments；必讀範圍 14,587 字（M6 範例）讀得完；docs-diet 封存到 `docs/archive/docs-diet.md`（遺失 0 行）；順手把 brief §20 與 `berth/` 註解裡 41 處「§19 列名」舊引用改連 ADR | 等使用者決定票 Comments 的遺留清單；開 M6 拆票 `/to-tickets docs/plan.md` |

## 偏差與決定

- 2026-10-30 docs-diet 拆票：**plan 與 brief 的章節號不改、不重排**（`berth/`、`web/` 引用數百處、這輪不改程式碼）；整節搬走留標題指向 `docs/archive/`。
