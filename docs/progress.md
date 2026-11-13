# 進度

工作單位是票（`.scratch/<里程碑>/issues/NN-slug.md`），狀態在票的 `Status:` 行。這裡只記進行中里程碑的 session 紀錄；里程碑的順序、狀態與閱讀指引在 `docs/roadmap.md`，決定在 `docs/decisions.md`。

已驗收的里程碑，session 紀錄與當時的偏差在 `docs/archive/<里程碑>.md`；舊文件與舊票指到「progress.md 的偏差與決定」的，到那裡找。

## 寫法與封存

- 做票的分支不改本檔與 `docs/decisions.md`：票的 Comments 留 `Session 紀錄：` 與 `決定：` 行，合併的人在 main 抄成這裡的一列與 decisions.md 的一條（`CLAUDE.md`〈每個 session 的流程〉第 5 步）；驗收票例外。
- 一列 ≤ 200 字（整行的字元數，Python `len`）。細節放票的 `## Comments` 或 `docs/research/`，這裡只寫結論與連結。
- 票欄標里程碑：`<里程碑> <票號> <短標題>`（沒有票的工作省略票號）。
- 大小：整檔 ≤ 20,000 字（`CLAUDE.md` ≤ 8,000 字），由 `tests/unit/test_reading_budget.py` 守。超過時，把進行中里程碑較舊的列也封存到 `docs/archive/<里程碑>.md`（同下面的做法），不要縮短措辭湊數。
- 只留進行中的里程碑：驗收票收尾時，把那個里程碑的列搬到 `docs/archive/<里程碑>.md` 的 `## Session 紀錄`、`docs/decisions.md` 裡它的決定搬到同一個檔的 `## 決定`，用 `scripts/docs_moved_lines.py` 證明沒丟（遺失 0），`docs/roadmap.md` 里程碑表那一列的狀態改成「已驗收（日期），封存於 `docs/archive/<里程碑>.md`」。封存後 session 紀錄加一列，票欄標下一個里程碑（`<里程碑> 準備`），「下一步」寫 `/1morr:checkpoint <封存的里程碑>`（它結束時再寫下一個里程碑的開工指令），否則封存會把下一步一起搬走；沒有下一個里程碑時，紀錄留空，只在對話告訴使用者。
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
| 2026-11-12 | M6 回顧 M5.6 | 回顧 M5.6，確認的 8 項寫回 spec 與票 01–03、05、06、08、11（見偏差）；補記兩條 M5.6 偏差、plan §11.9 加兩項 | 新 session 下 `/implement .scratch/m6/issues/01-subscribe-picks-season.md` |
| 2026-11-12 | M6 流程 | 拿掉 `docs/overview/`，改用 `/1morr:explain` 出臨時解說頁；brief、plan、ADR 0011、CONTEXT、程式註解對齊程式碼 | 新 session 下 `/implement .scratch/m6/issues/01-subscribe-picks-season.md` |
| 2026-11-13 | M6 流程 | 對齊 project-init：票留 Session 紀錄由合併的人寫本檔、驗收票加使用者試、提問寫法；章節號引用與票號只減不增；路線圖與瘦身排在 M6 之後（plan §11.9） | 新 session 下 `/implement .scratch/m6/issues/01-subscribe-picks-season.md` |
| 2026-11-13 | M6 流程 | 路線圖、決定、brief §20 的事實搬出 plan、progress、brief（見 `CLAUDE.md`〈文件〉）；瘦身的票在 `.scratch/docs-diet-2/` | 新 session 下 `/implement .scratch/m6/issues/01-subscribe-picks-season.md` |
| 2026-11-13 | M6 流程 | 決定改成跟著里程碑封存，`docs/decisions.md` 只留進行中的（改該檔〈寫法〉、本檔〈寫法與封存〉、票 12） | 新 session 下 `/implement .scratch/m6/issues/01-subscribe-picks-season.md` |
