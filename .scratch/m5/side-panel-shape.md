# 側面板 shape（M5 票 08）

`/impeccable shape`，2026-10-24。使用者選定三題：桌機並排推窄頁面、最近一則＋歷史清單、開關換頁不關且重整記得。
世界沿用 DESIGN.md「泊位調度板」，這一面是 **Operate**：人在場、下指令、看結果。

## 參考了誰

- **Vercel AI SDK 的 UI message stream**（<https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol>、
  <https://ai-sdk.dev/docs/ai-sdk-ui/chatbot-tool-usage>）：送一則訊息是 **POST，回應本身就是 SSE**，前端用 fetch
  讀串流（不是 `EventSource`）。照抄的是事件名與工具呼叫的狀態：`text-delta`、`tool-input-start`、
  `tool-output-available`、`error`、`finish`；工具在畫面上的三態 `input-available`（正在查）→ `output-available`
  （查過）/ `output-error`（沒做成）。錯誤預設不把原文外洩給前端，Berth 送封閉的分類碼，原文留在 log。
  不用 `ai` 套件本身：它要的訊息形狀與 Berth 存在資料庫裡的不同，事件名照它的、reducer 自己寫。
  解析用 `eventsource-parser`（Vercel AI SDK 自己用的那一個）。
- **Home Assistant Assist 的 exposed entities**（<https://www.home-assistant.io/voice_control/voice_remote_expose_devices/>、
  `homeassistant/helpers/llm.py`）：只有明確暴露的才給 LLM，權限在工具層再查一次——Berth 的命令登錄表（票 05）就是這一份
  暴露清單，`Registry.invoke` 再查角色。**工具迴圈上限照 HA 的 `MAX_TOOL_ITERATIONS = 10`**
  （`components/anthropic/entity.py`、`openai_conversation/entity.py`）。
- HA 的預設指示要模型回純文字（`DEFAULT_INSTRUCTIONS_PROMPT`）；Berth 票 08 也只畫純文字（保留換行），不解析 Markdown。

## 1. 工作與對象

每一頁都開得到的對話區。管理員在任何一頁想到「這週入庫了什麼」「訂閱這部」時，不必離開那一頁；`user` 用它問問題，
工具清單比管理員短（登錄表依角色過濾，介面不另外擋）。M7 的 Discord 接的是同一個對話核心，面板只是其中一個介面。

## 2. 結果與證據

- 成功 = 送出一句話，回覆一字一字串流出來；工具呼叫時看得到「正在查……」，查完那一行換成「查過……」。
- **做了什麼只以結果卡為準**（票 09 起有卡）。模型的文字永遠是中性的散文，**不塗任何信號色、不畫成成功**；
  綠色或「已完成」只會出現在工具結果的卡上。只能聊天的模型，面板上方常駐一句「這個模型只能聊天：它說的事都沒有真的做」。
- 重整之後對話還在（存在 Berth）；回覆到一半關掉面板或換頁，回覆在後端照樣跑完、存下來，回來看得到。

## 3. 方向

- **並排的一欄，不是浮起的抽屜。** 這個系統沒有陰影與 z 軸（Elevation & Depth），並排不必發明「浮起來」的語彙。
  `lg` 以上外框變成兩欄：頁面 `flex-1 min-w-0`，面板在右側 `w-[26rem]`（`xl` 28rem），`border-l-2 border-rule-strong`
  分開。面板自己內部捲動；頁面照常可操作。**實作時改**：`sticky top-0 h-dvh` 比畫面高一個頁首，焦點進輸入框時整頁被捲過頁首；改成 `lg` 以上 `fixed` 在右側全高、外框以同寬 `padding-right` 讓出那一欄（仍是並排、不疊，DESIGN.md〈助理側面板〉）。
- **窄版（`lg` 以下）面板開著時取代 `main`**：整寬、頁首保留（關閉鍵就在面板抬頭列）。不疊在頁面上。
- **對話是一份航海日誌，不是聊天泡泡**：沒有圓角泡泡、不左右對齊。每一則一塊、上方一個 `.label` 說話者（「你」/「助理」），
  使用者那一則是 `deck` 底（抬起一階），助理的是面板本身的 `well` 底；塊與塊之間 `gap-3`。

## 4. 範圍與界線

- 這張：面板外殼、開關、對話清單、文字串流、工具呼叫的狀態行、失敗與保險絲的說法、未設定好與只能聊天兩種狀態。
- **不在這張**：結果卡（票 09）、確認卡與撤銷（票 10、11）、Markdown、附件、改寫或重新生成、刪除對話、改對話名。
- 不碰任何現有頁面的版面；頁面在 `lg` 以上只是變窄（它們本來就照 `max-w-*` 置中）。

## 5. 狀態與範圍

| 狀態 | 畫面 |
| --- | --- |
| AI 沒設定好，管理員 | 面板內一塊空狀態：「AI 還沒設定好。」＋ `GHOST_LINK`「去設定」→ `/settings/ai`。沒有輸入框 |
| AI 沒設定好，`user` | 同一塊：「管理員還沒開啟 AI。」沒有連結、沒有輸入框 |
| 只能聊天（設定頁測出不支援工具） | 抬頭列下方一則 `Notice`（中性）：「這個模型只能聊天：它說的事都沒有真的做。」輸入框照常 |
| 新對話、空的 | 一句提示「跟助理說你想做什麼。」 |
| 回覆中 | 助理那一塊 `aria-busy`，字串流進來；送出鍵 `busy`（不停用） |
| 工具呼叫 | 助理那一塊裡一行 `.value text-xs`：`working` 小色塊「查詢中」＋「正在查最近入庫」；完成換成中性「查過最近入庫」，沒做成是中性「沒做成：<理由碼的說法>」。工具名走 i18n（`assistant.tools.<name>`），沒有 key 的退回「工具」 |
| provider 失敗 | 對話裡一則 `Notice`，存下來、重整還在。限流、provider 掛掉、連不上：`assigned`「等一下再試」（限流有秒數就說）；key 不對、額度用完、模型不存在、端點拒絕：`blocked`，管理員多一條「去設定」 |
| 到輪數上限 | `Notice` `assigned`：「這一輪呼叫工具到了 10 次上限，先停在這裡。」 |
| 歷史清單 | 面板內換成清單（取代對話那一塊）：每列是第一句話（散文，`break-words`）＋ `Timestamp`；最近的在上；空的是「還沒有對話」 |
| 對話很長 | 面板內捲動，打開時捲到最底；新字進來時只有本來就在最底才跟著捲 |

## 6. 互動與版面

- **入口**：頁首導覽列的最後、登出鍵之前，一顆 `NAV_BOX` 外觀的「助理」按鈕（`aria-expanded`、`aria-controls`），
  開著時 `NAV_BOX_ACTIVE`。未登入（精靈、登入頁）沒有面板。
- **開關記憶**：掛在 `AppShell`，換頁不關；開關存在 `localStorage`（讀不到就當關著），重整照原樣。
  打開的是最近一則對話（`GET /conversations` 的第一筆），沒有就是新對話。
- **抬頭列**（`deck` 底、`border-b-2 border-rule`）：`.label`「助理」＋ Ghost 小鍵「新對話」「歷史」「關閉」。
- **輸入**：`textarea`（`hull` 底 + `border-2 border-rule-strong`，散文字型），Enter 送出、Shift+Enter 換行，
  輸入法組字中（`isComposing`）的 Enter 不送出。送出鍵是 **Ghost**：頁面自己的主鍵已經是那一屏的調度黃，面板不搶。
- **焦點**：打開時焦點進輸入框；關閉（鍵或 `Esc`，焦點在面板內時）回到頁首的「助理」鍵。歷史清單點一列，焦點回輸入框。
- **無障礙**：面板是 `<aside aria-label="助理">`；對話是 `role="log"`，回覆中的那一塊 `aria-busy="true"`，串流完才被念。
  工具狀態行與 `Notice` 在同一個 log 裡。

## 7. 限制與不許自己發明的

- 文案全部走 i18n（zh-Hant、en 並列）；回覆語言由前端送出的介面語言決定（後端寫進 system 的那一行）。
- 串流的真相在資料庫：`finish` 之後前端讓那一則對話的 query 失效再讀一次，串流中的字只是先畫上去。
- 送出時後端拒絕（另一則回覆還在跑、AI 沒設定好）以就地一句話說，不開 dialog。
- 新元件：`AssistantPanel`（外殼）、`AssistantTranscript`、`AssistantComposer`、`ConversationList`，寫進 DESIGN.md 一節。
