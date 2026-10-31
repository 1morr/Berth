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
| M5.5 | `.scratch/m5.5/issues/` | plan §11.6b；brief §13、§9.1、§20.3 | 新番時間表、追更、遲到提醒與導覽收斂（2026-10-31 加入，排在 M6 前） |
| M6 | `.scratch/m6/issues/` | plan §11.7；brief §14、§6.10 | 人工接管開關與背景 AI 任務（含 Issue）、影子模式（2026-10-27 改） |
| M7 | `.scratch/m7/issues/` | plan §11.8；brief §14、§16.2 | Discord 與 MCP（2026-09-22 加入、09-24 加 MCP、10-27 改名） |
| docs-diet | `.scratch/docs-diet/issues/` | — | 已驗收（2026-10-30），封存於 `docs/archive/docs-diet.md` |

開工：使用者在新 session 下 `/to-tickets docs/plan.md 拆 <里程碑> 的票`，那個 session 寫 `.scratch/<里程碑>/spec.md`、把 plan §11 那一節縮成連結、拆票，步驟在 `CLAUDE.md`〈Skills〉。沒開工的里程碑只在 plan §11；開工後以 spec 與票為準。

## 寫法與封存

- session 紀錄一列、偏差一條都 ≤ 200 字（整行的字元數，Python `len`）。細節放票的 `## Comments` 或 `docs/research/`，這裡只寫結論與連結。
- 每列、每條標里程碑：票欄寫 `<里程碑> <票號> <短標題>`（沒有票的工作省略票號），偏差寫 `- <日期> <里程碑> 票 <NN>：…`。
- 偏差只記跨票的決定：推翻 plan / brief、改流程、影響後續的票。票內取捨記在票的 `## Comments`。
- 大小：整檔 ≤ 20,000 字（`CLAUDE.md` ≤ 6,000 字），由 `tests/unit/test_reading_budget.py` 守。超過時，把進行中里程碑較舊的列與條也封存到 `docs/archive/<里程碑>.md`（同下面的做法），不要縮短措辭湊數。
- 只留進行中的里程碑：驗收票收尾時，把那個里程碑的列與條搬到 `docs/archive/<里程碑>.md`，用 `scripts/docs_moved_lines.py` 證明沒丟（遺失 0），里程碑表那一列改成「已驗收（日期），封存於 `docs/archive/<里程碑>.md`」。封存後 session 紀錄加一列，票欄標下一個里程碑（`<里程碑> 準備`），「下一步」寫它的開工指令，否則封存會把下一步一起搬走；沒有下一個里程碑時，紀錄留空，只在對話告訴使用者。
- 「下一步」寫新 session 要下的完整指令（反引號包住、`/` 開頭），或以 `等使用者：` 開頭；`tests/unit/test_progress_rules.py` 查最後一列。

## Session 紀錄

| 日期 | 票 | 結果 | 下一步 |
| --- | --- | --- | --- |
| 2026-10-31 | M6 流程 | 里程碑開工改成一個指令，所有 session 結尾給下一步指令；閘門 `test_scratch_specs.py`、`test_progress_rules.py` | 新 session 下 `/to-tickets docs/plan.md 拆 M6 的票` |
| 2026-10-31 | M5.5 規劃 | 新番時間表、追更與遲到提醒、導覽收斂排在 M6 前，寫進 plan §11.6b、brief §17 與 §20.3 | 新 session 下 `/to-tickets docs/plan.md 拆 M5.5 的票` |
| 2026-11-01 | M5.5 規劃 | 遲到提醒補上下載停滯與入庫失敗，已在等你處理的不重複開；通知寫作品與集數，沒接 Discord 時追更頁提示（plan §11.6b、§11.7、brief §17） | 新 session 下 `/to-tickets docs/plan.md 拆 M5.5 的票` |

## 偏差與決定

實作中推翻 plan / brief 的事，一行一條，附 commit hash 與改動的章節。

- 2026-10-31 M6 流程：M6 起 spec 由開工 session 寫到 `.scratch/<里程碑>/spec.md`，plan §11 對應節縮成一行連結、編號不變（改 plan §11 導言、`CLAUDE.md`〈Skills〉）；M0–M5 與 docs-diet 不補。
- 2026-10-31 M5.5 排程：M6 之前插入 M5.5（使用者定），M6 改在它驗收後開工；改 plan §11.6b、brief §17、`PRODUCT.md` 里程碑表、`CLAUDE.md` 的 spec 起始里程碑。
