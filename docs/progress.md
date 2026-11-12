# 進度

工作單位是票（`.scratch/<里程碑>/issues/NN-slug.md`），狀態在票的 `Status:` 行。這裡只記各里程碑的閱讀指引、session 紀錄、偏差與決定。

M0–M5 已驗收，只留進行中的里程碑在本檔。M0–M5 的 session 紀錄與偏差在 `docs/archive/<里程碑>.md`（`m0`、`m1`、`m1.5`、`m2`、`m3`、`m4`、`m5`）；舊文件與舊票指到「progress.md 的偏差與決定」的，到那裡找。

M5.5（新番與導覽）也已驗收，封存於 `docs/archive/m5.5.md`。
M5.6（AI 對話精簡）也已驗收，封存於 `docs/archive/m5.6.md`。

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
| M5.6 | `.scratch/m5.6/issues/` | — | 已驗收（2026-11-08），封存於 `docs/archive/m5.6.md` |
| M6 | `.scratch/m6/issues/` | plan §11.7；brief §14、§6.10、§20.29 | 人工接管開關、第一批背景 AI 任務、AI 評估；先修 M5.6 遺留並發 0.5.2（2026-11-10 拆出 M6.5） |
| M6.5 | `.scratch/m6.5/issues/` | plan §11.7b；brief §14 | Issue 與每週巡檢交給 AI、修正回流（2026-11-10 從 M6 拆出） |
| M7 | `.scratch/m7/issues/` | plan §11.8；brief §14、§16.2 | Discord 與 MCP（2026-09-22 加入、09-24 加 MCP、10-27 改名） |
| docs-diet | `.scratch/docs-diet/issues/` | — | 已驗收（2026-10-30），封存於 `docs/archive/docs-diet.md` |

開工：使用者在新 session 下 `/to-tickets docs/plan.md 拆 <里程碑> 的票`，那個 session 寫 `.scratch/<里程碑>/spec.md`、把 plan §11 那一節縮成連結、拆票，步驟在 `CLAUDE.md`〈Skills〉。沒開工的里程碑只在 plan §11；開工後以 spec 與票為準。

## 寫法與封存

- session 紀錄一列、偏差一條都 ≤ 200 字（整行的字元數，Python `len`）。細節放票的 `## Comments` 或 `docs/research/`，這裡只寫結論與連結。
- 每列、每條標里程碑：票欄寫 `<里程碑> <票號> <短標題>`（沒有票的工作省略票號），偏差寫 `- <日期> <里程碑> 票 <NN>：…`。
- 偏差只記跨票的決定：推翻 plan / brief、改流程、影響後續的票。票內取捨記在票的 `## Comments`。
- 偏差標決定者（2026-11-12 起）：`（使用者定）` 使用者自己定的、`（使用者同意）` agent 提議而使用者同意的、`（Agent 定）` 使用者沒看過的；`/1morr:checkpoint` 會把 `（Agent 定）` 拿給使用者看。
- 大小：整檔 ≤ 20,000 字（`CLAUDE.md` ≤ 6,000 字），由 `tests/unit/test_reading_budget.py` 守。超過時，把進行中里程碑較舊的列與條也封存到 `docs/archive/<里程碑>.md`（同下面的做法），不要縮短措辭湊數。
- 只留進行中的里程碑：驗收票收尾時，把那個里程碑的列與條搬到 `docs/archive/<里程碑>.md`，用 `scripts/docs_moved_lines.py` 證明沒丟（遺失 0），里程碑表那一列改成「已驗收（日期），封存於 `docs/archive/<里程碑>.md`」。封存後 session 紀錄加一列，票欄標下一個里程碑（`<里程碑> 準備`），「下一步」寫 `/1morr:checkpoint <封存的里程碑>`（它結束時再寫下一個里程碑的開工指令），否則封存會把下一步一起搬走；沒有下一個里程碑時，紀錄留空，只在對話告訴使用者。
- 「下一步」寫新 session 要下的完整指令（反引號包住、`/` 開頭），或以 `等使用者：` 開頭；`tests/unit/test_progress_rules.py` 查最後一列。

## Session 紀錄

| 日期 | 票 | 結果 | 下一步 |
| --- | --- | --- | --- |
| 2026-10-31 | M6 流程 | 里程碑開工改成一個指令，所有 session 結尾給下一步指令；閘門 `test_scratch_specs.py`、`test_progress_rules.py` | 新 session 下 `/to-tickets docs/plan.md 拆 M6 的票` |
| 2026-11-04 | M6 準備 | M5.5 驗收完、封存於 `docs/archive/m5.5.md`；CHANGELOG 定為 0.5.0，tag 與 push 由協調者做。M6 照 plan §11.7 開工 | 新 session 下 `/to-tickets docs/plan.md 拆 M6 的票` |
| 2026-11-08 | M6 準備 | M5.6 驗收完、封存於 `docs/archive/m5.6.md`：11b 修好「可以看了」的比對後，真服務 e2e 28 綠；M6 照 plan §11.7 開工 | 新 session 下 `/to-tickets docs/plan.md 拆 M6 的票` |
| 2026-11-08 | M6 準備 | 發 0.5.1：CHANGELOG 收成 0.5.1、pyproject 與 uv.lock 同步；沒有 migration 與部署檔變動；全部檢查、pytest 5814、vitest 2460 綠；tag 與 push 已推上 origin | 新 session 下 `/to-tickets docs/plan.md 拆 M6 的票` |
| 2026-11-10 | M6 準備 | 盤點 M5 系列：全部檢查、pytest 5814、vitest 2460、bench 綠；M6 拆出 M6.5，一致率門檻 ≥ 90% 且至少 20 件，訂閱挑季修完先發 0.5.2（plan §11.7、§11.7b） | 新 session 下 `/to-tickets docs/plan.md 拆 M6 的票` |
| 2026-11-10 | M6 準備 | 使用者不逐件處理：拿掉影子模式，改對凍在 repo 的案例做 AI 評估（套用錯 0 件）；背景任務資料不夠時第二段唯讀網搜（plan §11.7、brief §14） | 新 session 下 `/to-tickets docs/plan.md 拆 M6 的票` |
| 2026-11-11 | M6 開工 | plan §11.7 細化成 `.scratch/m6/spec.md`、§11.7 縮成連結；拆 12 張票（第一批五種併成四型、評估與網搜同一張），票序在 spec | 新 session 下 `/implement .scratch/m6/issues/01-subscribe-picks-season.md` |

## 偏差與決定

實作中推翻 plan / brief 的事，一行一條，附 commit hash 與改動的章節。

- 2026-10-31 M6 流程：M6 起 spec 由開工 session 寫到 `.scratch/<里程碑>/spec.md`，plan §11 對應節縮成一行連結、編號不變（改 plan §11 導言、`CLAUDE.md`〈Skills〉）；M0–M5 與 docs-diet 不補。
- 2026-11-10 M6 範圍：Issue 各型別、每週巡檢交給 AI、修正回流移到新的 M6.5（使用者定）；影子一致率門檻 ≥ 90%、至少 20 件；訂閱挑季修完先發 0.5.2。改 plan §11.7、§11.7b、brief §14、§17、`PRODUCT.md`。
- 2026-11-10 M6 AI 評估：使用者不在頁面上逐件處理，影子模式量不出一致率，拿掉；開關改人 / AI 兩段，驗收改成凍在 repo 的案例集上套用錯 0 件、交回人的比例下降（推翻同日的 ≥ 90% 門檻）。背景任務答「資料不夠」才給限網域的唯讀網搜。改 plan §4.5、§11.7、§11.7b、brief §6.10、§14、ADR 0008、`CONTEXT.md`。
- 2026-11-10 M6.5 範圍：補進 M6 第一批漏列的重複版本（保留兩者、跳過自動，取代做 Proposal）與 C1 表沒有的 `episodes_overdue`（使用者定）；M6 的第一批確認寫明「證據夠就確認整批」。改 plan §11.7、§11.7b、brief §14。
- 2026-11-11 M6 送下載的閘：背景任務叫帶 `Flag.DOWNLOADS` 的命令時，一次超過 13 個 torrent 或磁碟不夠改 Proposal；AI 評估件數分級，會送下載的至少 60 件、其餘 20 件（使用者定）。改 plan §11.7、§11.7b、brief §14。
- 2026-11-11 M6 片長進資料包：背景任務的檔案清單帶 mediainfo 量到的片長與大小、TMDB 每集帶 `runtime`，片長偏離同組的檔案單獨送，不壓進樣本。改 plan §4.5、brief §6.10。
- 2026-11-11 M6 拆票：第一批五種任務併成四型——程式檢查擋在入庫前的兩種併進「審核中的 Plan」，Jellyfin 回驗的不符併進「audit 與第一批」；評估與第二段網搜同一張；開關預設人，評估達標才放上設定頁。改 spec〈範圍〉。
- 2026-11-12 M6 評估門檻：案例本來全部要人處理，「交回人的比例比規則層低」等於處理掉 1 件就過；改成交回人 < 5%（AI 處理 95% 以上），太難再改（使用者定）。改 spec〈AI 評估〉〈驗收〉、票 06、08–10、brief §17、plan §11.7b。
