# AI 活動頁 shape（M5 票 14）

2026-10-24，`/impeccable shape`。使用者答了四題：頁首導覽一格（側面板抬頭也連過去）；直接做的寫入工具一律要帶 `reason`；管理員撤得了任何人的、確認過的可逆 Proposal 也撤得了；tokens 算整個回覆。

## 工作與讀者

- **誰**：叫過助理做事的人。管理員看全部（「AI 這週替大家做了什麼、有沒有做錯」），`user` 只看自己對話裡的。偶爾打開：發現多了一個訂閱或一筆下載、想知道是誰叫的、為什麼。
- **模式**：Operate。掃一眼讀得出「何時、代誰、做了什麼、為什麼」，錯的那一筆當場撤掉。
- **成功**：每一筆 AI 的寫入都在這裡；撤得了的一顆鍵就撤，撤不了的說得出為什麼；連得回那則對話看上下文。

## 採用的慣例

**GitHub 的 Security log / Audit log** 與 **Vercel 的 Activity**：一列一個動作、最新在前、主詞（誰）+ 動作 + 對象 + 時間，細節收在展開裡；**Gmail 的「復原」**：撤銷就在那一列上、撤了之後列還在、說已撤銷。不做它們的篩選器與匯出（筆數是家用的量）。

## 資料（不另寫日誌，brief §6.10 ⑤）

**來源是對話本身**：AI 的每一次工具呼叫與結果已存在 `conversation_messages`（`ToolCallPart` / `ToolResultPart`），確認卡在 `proposals`，撤銷是對話裡的 `UndonePart`。`events.actor` 的 `ai:<user id>` 只掛在 Job 的事件上、沒有工具名、理由與對話，撈不出這一頁要的東西——所以從對話撈，`actor` 照舊管 Job 時間線。缺的兩樣補在既有的記錄上，不開新表：

- **理由**：直接做的寫入工具（`submit_search_result`、`subscribe_mikan`、`subscribe_search_feed`）輸入加必填 `reason`，同確認卡的 `ProposalInput`。
- **這次回覆的 tokens**：`ai_calls.message_id`（這一次呼叫在回覆哪一則使用者的話）。時間窗對不準（對話的時鐘可注入，`call_model` 用真的時鐘），所以存連結。

**列進來的**：工具結果 `done` 而工具等級不是 `read` 的（AI 直接做的）；確認卡 `confirmed` 的（人按了確認、由他執行）。拒絕的、等人按的、被拒絕或失效的卡不列。最新在前，一次 200 筆。

## 結構（`max-w-[80rem]`，同下載列表的外框）

1. `h1`「AI 活動」+ 一句導言：「助理替人做過的每一件事。撤得了的就在這裡撤。」管理員多半句「（所有人的）」。
2. **一列一筆**（同工作清單列的外殼：`well` 底 + `border-2 border-rule` + `px-4 py-3`，列間 `gap-3`，**不塗信號色**——它們不是在等人）：
   - ① 識別行：中性色塊的動作名（「送單」「訂閱 Mikan」「加 Feed」，`.label` + `deck`）+ 對象（`.value wrap-anywhere`：送出的發佈名、Feed 名）。
   - ② 一行事實（`text-sm ink-dim`，`Dot` 分隔）：`Timestamp` · 「AI 代 {人}」或「{人} 確認的」· 出自《對話標題》（是自己的對話時連到側面板開那一則；別人的只印標題）· 這次回覆 N tokens（`.value`，不知道時「—」）。
   - ③ 「AI 的理由」：`.label` + 原文散文（`text-sm ink`）。舊資料沒有理由時這一格不出現。
   - ④ 展開（原生 `<details>`，`.label`「輸入」）：`hull` 底的 `dl`，每個輸入欄一條 `DetailLine`（欄名照原樣、值是機器字串，The Machine String Rule）；`reason` 不重複。
   - ⑤ 撤銷那一格：撤得了 → Ghost「撤銷送單 / 撤銷訂閱」，就地 `ConfirmPanel`，後果句同結果卡那一句；撤了 → 一句 `text-xs ink`「已撤銷」+ `Timestamp`；撤不了 → 一句 `text-xs ink-dim` 說為什麼（「沒有反向命令：加索引站做了就撤不回」、「只有管理員撤得了送單」）。撤銷被拒是 `blocked-ink` 的 `role="alert"`，列留著、再按一次接著做。

## 狀態

- **一筆都沒有**：`Notice`（中性）「AI 還沒替{你 / 任何人}做過事。」加一句側面板怎麼開。AI 沒設定好時導覽沒有這一格，直接進網址照樣看得到以前的。
- **讀取中**：三塊與列同高的 `deck` 色條。**讀不到**：`RequestFailed`。
- **撤銷之後**：列不消失，換成「已撤銷」；焦點留在那一列的狀態句上。

## 窄版

一欄；② 的事實行自然換行（一組一行，斷開不以中點開頭）；撤銷的確認區照 `CONFIRM_ACTIONS` 疊成一欄。

## 不做

篩選與搜尋、分頁（200 筆之外說「更早的不列」）、匯出、讀取工具的紀錄、被拒絕或失效的卡、M6 背景任務的列（M6 寫進同一頁時再加出處）。

## 契約（給實作）

`GET /api/ai-activity` 回 `{ entries: AiActivityEntry[], truncated: bool }`。`AiActivityEntry`：`conversation_id`、`conversation_title`、`own`（是看的人自己的對話）、`message_id`、`call_id`（撤銷用的位址，同結果卡）、`at`、`user_id`、`user_name`、`via`（`ai` 直接做 / `confirmed` 人確認的）、`tool`、`arguments`（去掉 `reason` 的 JSON 物件）、`reason`（可為空字串）、`result_type`、`result`、`tokens`（`input`、`output`，可為 `null`）、`undo`（`undoable` / `undone` / `no_inverse` / `not_allowed`）、`undone_at`。撤銷走既有的 `POST /conversations/{id}/messages/{m}/tools/{call}/undo`：管理員不必是對話的主人；確認卡那一筆的位址是 `ProposalCard` 那一份工具結果。
