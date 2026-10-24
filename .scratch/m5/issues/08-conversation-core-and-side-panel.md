# 08 — 對話核心與側面板（tracer 前半）

**Status:** done

**Blocked by:** 05、07

**讀:** plan §11.6〈對話核心〉〈側面板〉〈provider〉、§6、§7；brief §6.10「外部文字是資料」「用量，不設預算」、§14；CONTEXT.md 的 Assistant；`DESIGN.md`、`PRODUCT.md`；SSE 的現有用法（`api/events.py`）

## 為什麼

側面板是 M5 的主角，M7 的 Discord 接的也是同一個對話核心。這張先讓「在任何一頁打開側面板、跟 AI 說話、串流看到回覆」端到端跑通，工具迴圈也接上；第一張結果卡在票 09。

## 做什麼

1. **先 shape**：照 CLAUDE.md `/impeccable shape`，輸出 `.scratch/m5/side-panel-shape.md`。設計前查成熟產品的對話工具 UI 與工具暴露方式（Vercel AI SDK 的 tool UI、Home Assistant Assist 的 exposed entities），寫明採用了誰的慣例。
2. **對話核心**（services，與介面無關）：對話與訊息存在 Berth，每人自己的，重整不丟。工具迴圈的工具＝票 05 的登錄表依角色過濾。固定的 prompt 前綴（system、工具定義）放最前、順序固定，讓快取吃得到；外部文字包在標明出處的資料區塊裡（brief §6.10）。回覆用使用者的介面語言。
3. **保險絲**：一則對話的工具呼叫輪數上限（數字寫進 plan §11.6）；provider 掛掉或限流時把原因說給人聽，不默默失敗。每次呼叫寫 `ai_calls`，出處是這則對話。
4. **串流**：用現有的 SSE。**別人的串流收不到我的對話**：現有 hub 若是全體廣播，對話要有自己的通道。
5. **側面板**：每一頁都開得到；文字訊息串流顯示；工具呼叫顯示「正在查……」這一類狀態（卡片在票 09）。文案走 i18n。
6. **做了什麼只以卡片為準**：寫入只有經過工具呼叫、出了結果卡才算做了。system 要求模型不得聲稱做了沒有工具結果的事；側面板上，模型的文字說「已訂閱」卻沒有卡片時，不顯示成成功。設定頁測出「不支援工具呼叫」的模型（票 07），側面板開著但標明「只能聊天」，不送工具定義。
7. **沒設 AI key**（「設定好了」的判斷由票 07 定，自架端點可以沒有 key，見 07 的「票 06 的補充」）：管理員看到「去設定」，`user` 看到「管理員還沒開啟 AI」。其餘頁面與 M4 相同。

## 驗收

- [x] 用假 provider：一則對話送出、串流回來、存進 DB、重整後還在（pytest＋vitest）
- [x] 假 provider 一直呼叫工具時，到輪數上限就停、說出原因（pytest）
- [x] 限流與 provider 失敗回出可讀的原因（pytest）
- [x] A 的對話不出現在 B 的串流與列表裡（pytest）
- [x] `user` 的工具清單沒有管理員命令（整合測試）
- [x] 模型被標成不支援工具呼叫時，側面板標明只能聊天、請求不帶工具（pytest＋vitest）
- [x] 每頁開得到側面板，串流顯示（playwright 實跑，附截圖）
- [x] 全部檢查、pytest、vitest 綠；plan §11.6、DESIGN.md（若有新元件）、progress.md 已更新

## Comments

- 2026-10-24 實作（session 紀錄在 progress.md）。shape：`.scratch/m5/side-panel-shape.md`（使用者選定：桌機並排、最近一則加歷史清單、開關記在瀏覽器；參考 Vercel AI SDK 的 UI message stream 與 tool part 三態、Home Assistant 的 exposed entities 與 `MAX_TOOL_ITERATIONS = 10`）。
- 驗收對照：pytest `tests/integration/test_assistant.py`（核心 23 條：串流與存、重讀、輪數上限、四種 provider 失敗、串流中途斷掉保留已送出的字、`ai_calls` 出處、依角色的工具與 `invoke` 再擋、只能聊天不帶工具、別人的對話、未設定、空白、busy、沒人讀也跑完）與 `tests/integration/test_conversations_api.py`（7 條：POST 回 SSE、重讀、404、409、401）；vitest `web/src/assistant/AssistantPanel.test.tsx`（13 條）；playwright `web/e2e/assistant.spec.ts`（`assistant` 情境，1280 與 390 各 2 條：九頁都開得到、串流到一半、工具狀態行、限流、重整之後還在）。截圖在本票旁的資料夾 `08-conversation-core-and-side-panel/`（串流中 1280、工具與限流 1280、390 深色、英文深色的歷史清單）。
- 變異驗證：輪數上限多一輪、工具不依角色過濾、只能聊天照樣帶工具，各紅一條 pytest。
- 實跑抓到並改掉：面板原本 `sticky`，焦點進輸入框時整頁被捲過頁首 → `lg` 以上改成 `fixed` 右欄、外框讓出同寬（shape 第 3 節已註記）；英文「Back to the conversation」把抬頭列擠成兩行 → `Back`。
- 順手修：票 13 與 07b 合併後 `tsc` 紅（用量頁缺 `format.openai` 文案），補上；用量頁的出處多 `conversation`。
- code-review（Standards、Spec 兩軸）處理了：README 兩份還說「沒有別的功能用 AI」、指南說設定好才有助理鍵、`Any` 沒註解、中點改用 `Dot`、`min-w-0`、ToolResult 組法重複（`tool_result_of`）、兩個同名 `_model_parts`、工具名改對照表、log 與 aside 同名、`.value` 用在散文、文字連結改 `TEXT_LINK`、SSE 的文件類別共用 `api/events.EventStream` 並拿掉沒用到的關機事件、拒絕理由碼翻成人話（登錄表自己的兩種）、輪數上限的文案帶數字（`NoticePart.limit`）、串流中途斷掉時保留已送出的字。
- code-review 沒處理、判斷題：
  - `AssistantRuns` 內部 `(cid, user, language, settings, emit)` 一起傳了三層（Data Clumps）：都是私有方法、一個呼叫鏈，包成型別多一層間接；之後 M7 的 Discord 若要不同的 emit 再收。
  - 各模組的拒絕理由碼（`source_missing`、`feed_unreachable`…）在狀態行照原樣印成機器字串：說法跟著各自的結果卡（票 09 起）。
  - 「AI 請求沒成」的文案有三份（設定頁的測試、用量頁的失敗類型、面板的 notice）：三處說的下一步不同（再測、只是統計、再送），沒有合併。
  - `conversations.own_conversation`、`messages_of` 回 ORM 列、掛著 `@command(READ)`：命令只有在 `services/tools.py` 登記才是工具（票 05 逐條登記），不會被 AI 拿到。
- 留給之後：票 09 的結果卡從 `ToolResultPart.result_type` 與 `result` 畫；Markdown、刪除與改名對話不在 M5 範圍。沒有真 key，面板沒對真 provider 跑過（票 09 驗收有一條「真 key 實跑一次」）。
