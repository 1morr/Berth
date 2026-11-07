# 進度

工作單位是票（`.scratch/<里程碑>/issues/NN-slug.md`），狀態在票的 `Status:` 行。這裡只記各里程碑的閱讀指引、session 紀錄、偏差與決定。

M0–M5 已驗收，只留進行中的里程碑在本檔。M0–M5 的 session 紀錄與偏差在 `docs/archive/<里程碑>.md`（`m0`、`m1`、`m1.5`、`m2`、`m3`、`m4`、`m5`）；舊文件與舊票指到「progress.md 的偏差與決定」的，到那裡找。

M5.5（新番與導覽）也已驗收，封存於 `docs/archive/m5.5.md`。

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
| M5.5 | `.scratch/m5.5/issues/` | — | 已驗收（2026-11-04），封存於 `docs/archive/m5.5.md` |
| M5.6 | `.scratch/m5.6/issues/` | `.scratch/m5.6/spec.md`；`docs/research/agent-slimming-2026-11-06.md` | AI 對話精簡：Route 卡、skills 與工具（2026-11-06 開工，排在 M6 前） |
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
| 2026-11-04 | M6 準備 | M5.5 驗收完、封存於 `docs/archive/m5.5.md`；CHANGELOG 定為 0.5.0，tag 與 push 由協調者做。M6 照 plan §11.7 開工 | 新 session 下 `/to-tickets docs/plan.md 拆 M6 的票` |
| 2026-11-06 | M5.6 方案 | 試用機對話分析與精簡方案 `docs/research/agent-slimming-2026-11-06.md`：Route 卡一部作品問一次、skills 5→3、工具 22→18、C2 季記號 bug | 等使用者：審精簡方案，決定 M5.6 排在 M6 之前或之後 |
| 2026-11-06 | M5.6 開工 | 方案已審、排在 M6 前；spec 與 11 張票：基準先量、C3 拆兩張、UI 收尾獨立；plan 補 §11.6c、brief §17 加 M5.6 列 | 新 session 下 `/implement .scratch/m5.6/issues/01-baseline.md` |
| 2026-11-07 | M5.6 工具 | 加 `.worktreeinclude`：Orca 與 Claude Code 新建的 worktree 從主資料夾複製 `.claude/settings.local.json`（本機 router 設定） | 新 session 下 `/implement .scratch/m5.6/issues/01-baseline.md` |
| 2026-11-07 | M5.6 01 基準 | S7/S8 進腳本、summary 加種子搜尋與 skill 載入；真模型 22 列約 $0.39：S7 種子 11/22、Route 13，S8 0/6 | 新 session 下 `/implement .scratch/m5.6/issues/02-single-season-search-marks.md` |
| 2026-11-07 | M5.6 03 確認卡 Route | 卡片依 `media_id` 分組、一部作品選一次；兩部以上有交集時頂部加「全部套用」；API 不動。e2e 桌機與 390 通過 | 新 session 下 `/implement .scratch/m5.6/issues/02-single-season-search-marks.md` |
| 2026-11-07 | M5.6 02 單季季記號 | 單季作品整季缺時不接季記號（實測：Mikan／dmhy／ACG.RIP 帶記號零筆、名字本身回得來）；修在 `missing_batches`，判準是播過的季（brief §20.28） | 新 session 下 `/implement .scratch/m5.6/issues/03-card-route-per-work.md` |
| 2026-11-07 | M5.6 05 搜尋 contains | 種子搜尋加 `contains`（每個詞都要有、先篩再截斷）；帶它時模型看 20 列（token 量測在票）；人用的端點不變 | 新 session 下 `/implement .scratch/m5.6/issues/06-library-episodes.md` |
| 2026-11-07 | M5.6 合併 main | 合併 main（票 02）到 `1morr/t03`，02、03 兩列都留著；pre-commit、vitest 2440、pytest 5724 全綠 | 新 session 下 `/implement .scratch/m5.6/issues/04-server-decides-route.md` |
| 2026-11-07 | M5.6 06 find_in_library 集數 | 劇集命中加 `episodes`（Jellyfin 季集範圍、缺集斷開），電影沒有；同一部只讀一次，讀不到只那一部說原因 | 新 session 下 `/implement .scratch/m5.6/issues/04-server-decides-route.md` |
| 2026-11-07 | M5.6 04 伺服器定 Route | 模型不給 route_id：一條用它、多條 RouteAsk、零條拒絕；拿掉 route_choices 與 read_media 的 Route 欄 | 新 session 下 `/implement .scratch/m5.6/issues/07-instructions-and-skills.md` |
| 2026-11-07 | M5.6 07 系統指示與 skills | B1 四條進 `INSTRUCTIONS`；skills 5→3，三份合計 80 行；`why_not` 寫出各結論；整季 `in_jellyfin` 帶 `hint` | 新 session 下 `/implement .scratch/m5.6/issues/08-subscribe-mikan.md` |
| 2026-11-07 | M5.6 08 以作品訂閱 | `rss.subscribe`：純函式挑番組（名字相等＋開播日）、`match_bangumi` 搜四個名字、卡片照舊；舊工具留給票 09，bench 0 錯 | 新 session 下 `/implement .scratch/m5.6/issues/09-subscribe-keyword-fallback.md` |

## 偏差與決定

實作中推翻 plan / brief 的事，一行一條，附 commit hash 與改動的章節。

- 2026-10-31 M6 流程：M6 起 spec 由開工 session 寫到 `.scratch/<里程碑>/spec.md`，plan §11 對應節縮成一行連結、編號不變（改 plan §11 導言、`CLAUDE.md`〈Skills〉）；M0–M5 與 docs-diet 不補。
- 2026-11-07 M5.6 票 04：推翻 plan §7「一條的照模型給的」——模型不給 Route，提出時由伺服器定（一條用它、多條問、零條拒）；plan §6 工具清單、§7 守法與 brief §14 同輪改。
