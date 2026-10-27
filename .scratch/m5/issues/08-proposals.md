# 08 — Proposal：待人確認的動作存成一列

**Status:** done

**Blocked by:** 07

**讀:** plan §11.6〈分段〉第 3 段；brief §14〈對話裡的確認卡〉、§20.24；`docs/research/m5-prototype-2026-10-27.md`〈發現〉第 3 點、〈實跑才抓到的問題〉第 3、4 點；`docs/research/m5-ai-direction-2026-10-27.md` C2〈卡片的原則〉；prototype 的 `proposals` 表與 `_decision`（`scripts/experiments/m5_agent_chat.py`）

## 為什麼

確認卡要能隔很久才按、在別的地方按、重啟之後按。所以它必須是一筆持久化的資料，而不是記憶體裡等待中的呼叫。Proposal 本身不需要 AI，人也能提出。

## 做什麼

1. `proposals` 表（migration）：
   - 命令名、參數、參數雜湊、預覽、提出者（使用者 id 或 `ai`）、所屬對話（可空）。
   - 狀態：等待、脫離對話、已核准、已拒絕、已執行、部分成功、失敗、過期。
   - 過期時間、決定的人與時間、逐列選擇、**逐列結果**。
2. 命令：
   - **提出**：跑登錄表的 `validate`，不通過就不建，回理由。
   - **決定**：核准時可帶逐列選擇。只有提出者或管理員按得到；先搶狀態，防雙擊。
   - **執行**：經執行器，執行前重驗，參數以存下的那一份為準，逐列記結果。
   - **過期清掃**：背景迴圈入口，`INTERNAL`。
3. **脫離對話**：對話繼續之後還沒決定的卡片標成脫離，之後再按由伺服器直接執行。這一張只做狀態與執行，對話那一半在票 13。
4. API：列出某段對話或某個人的 Proposal，以及決定。狀態變更經 SSE 推播。
5. 這張不做 UI。

## 驗收

- [x] 建、決定、執行、過期、部分成功各有測試；執行用存下的參數，不收外來參數
- [x] 不是提出者也不是管理員的人按不到；連按兩次只執行一次（測試）
- [x] 重開行程之後照樣能決定與執行（測試）
- [x] `validate` 不通過的不建（測試）
- [x] plan §2 補表、§6 補 API；`pnpm gen:api`；全部檢查與 pytest 綠；progress.md 已更新

## Comments

2026-10-27 code-review（Standards、Spec 兩軸）已改：決定之後執行被別處搶走時回卡片現在的樣子而不是 409；`api/events._event` 改成窮舉的 `match`；`Any` 補原因；補了壞掉的一列、降級後的角色、重啟前已核准、SSE `event: proposal` 的測試。

未處理，留給後面的票：

- **票 13：Proposal 與 tool call 沒有連結。** prototype 用 `tool_call_id` 當 Proposal 的 id；這張表是自增 id，恢復時要從「最後一則模型回應裡還沒有結果的呼叫」找回卡片，票 13 要加一欄 `tool_call_id`（nullable、unique）的 migration。prototype 的 `tainted`（讀過外部內容）也還沒有，照 plan §11.6 由票 14 決定放哪。
- **票 13：還在對話裡、核准了而恢復失敗的卡片**會停在 `approved`：`detach` 只動 `pending`、`expire_due` 不動 `approved`。恢復那一輪失敗時要嘛重試執行、要嘛由伺服器直接執行。
- **`executing` 停住的卡片沒有地方顯示**（行程死在執行中）。票 21 / 22 的畫面要說得出來。
- **執行器在 commit 之前推播與叫醒迴圈**（`Executor._after`，票 07 的形狀，API 路由也一樣）：命令自己沒 commit 的話，被叫醒的迴圈可能讀到舊狀態，下一輪會補上。沒在這張改，因為牽動每一支經執行器的路由。
- **命令中途自己 commit 過、之後才丟例外的那一列**，結果記成 `failed`，但已 commit 的部分留著（例如送單重試先寫 `requested` 才打 qBittorrent）。`detail` 有原文；要更準得由命令回報做到哪一步。
- 逐列結果的 `reason` 是字串（各模組拒絕 enum 的值、例外型別名、`arguments_changed`），不是封閉集合；票 13 做卡片時要決定畫面怎麼挑句子。
- 雜湊只比對存下的參數與存下的雜湊（防有人改了那一列），`decide` 不收前端看到的雜湊：參數建立後不可改、id 不重用，所以沒加。M7 的 Discord 按鈕若要防舊訊息，再把雜湊放進 custom_id。
- 管理員的列表是每一張，沒有「某一個人」的篩選；`list_proposals` 進了命令登錄表（唯讀、一般使用者也可），要不要當成 AI 的工具由票 14 決定。
- 重複的形狀：`propose` 開頭查登錄表與擋 `audience` 同 `Executor.execute`；`detach` 與 `expire_due` 同形。各兩處，先不抽。
