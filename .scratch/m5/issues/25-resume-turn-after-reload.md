# 25 — 重新整理頁面後，那一輪在伺服器繼續跑、回來接上

**Status:** done

**Blocked by:** 23d

**讀:** plan §2.6（AI 對話）、§11.6 票 11 / 12 / 20 / 22 的段落；brief §14〈對話裡的確認卡〉與 §20.24（pydantic-ai 與 Vercel AI SDK 串流的實測）；`berth/services/agent.py`（一輪怎麼開、怎麼停、`data-stop`）、`berth/api/agent.py`、`web/src/agent/`（側面板、`useChat`）；票 11、12、20、22 的 Comments

## 為什麼

使用者 2026-10-28 在試用機按下 Mikan 訂閱確認卡後，助理開始下一步；4 秒後使用者重新整理了頁面（log：整頁重新載入 `/rss`），連線一斷，那一輪就停在「連線被關掉」，最後那段總結沒了。現在的設計（票 11）是瀏覽器斷線就停。

使用者決定照 ChatGPT、Claude.ai 的做法：**重新整理、換頁、關掉分頁再回來，那一輪都在伺服器繼續跑完；回到對話時接上正在跑的串流或看到跑完的結果。**只有按「停止」才停。

## 做什麼

1. 先查成熟做法並在票 Comments 說明採用了誰的慣例：Vercel AI SDK 的 resumable streams（`useChat` 的 resume、伺服器端的串流暫存）、ChatGPT / Claude.ai 重連的行為。版本相關的 API 用 context7 查，不憑記憶。
2. 伺服器：一輪不再綁在那一條 HTTP 連線上；連線斷了照跑到完（防護、上限、暫停照舊）。「停止」仍是明確的命令，一按就停。想清楚這幾件事並寫進 plan：
   - 同一個對話同時只有一輪在跑（重連不會開第二輪）；
   - 重連時接上還在跑的那一輪，跑完的直接從歷史讀；
   - 伺服器重啟時正在跑的那一輪怎麼收尾（記成停下並寫明原因，不留半截）；
   - 多個分頁同時開著同一個對話時的行為。
3. 前端：重新整理或回到對話時，正在跑的那一輪接著顯示；跑完的照常顯示；按「停止」照舊。
4. 「連線被關掉」這種停下原因只留給真的停掉的情況（例如伺服器重啟）；文案與 i18n（zh-Hant、en）同步。
5. 推翻票 11「斷線就停」：同一個 commit 改 plan / brief，progress.md「偏差與決定」記一行。

## 驗收

- [x] 整合測試：一輪跑到一半斷線，伺服器照跑完，歷史裡有完整結果；重連拿得到後續的串流（改回斷線就停會紅）
- [x] 「停止」照樣立刻停（測試）；同一對話不會因重連開出第二輪（測試）
- [x] 伺服器重啟時正在跑的那一輪有明確收尾（測試）
- [x] playwright 實跑：送出一句會跑幾步的話 → 重新整理 → 看到那一輪繼續並完成（1280 與 390 各一，附截圖或文字結果）
- [x] plan / brief 已改、progress.md 已記；全部檢查、pytest、vitest、前端 e2e 綠；`gen:api` 無 diff
- [x] 不發版、不 push

## Comments

### 2026-10-28 採用的慣例與設計（開工前）

**照 Vercel AI SDK 的 resumable streams**（context7 `/vercel/ai/ai_7.0.0`：`04-ai-sdk-ui/03-chatbot-resume-streams.mdx`、`09-troubleshooting/15-abort-breaks-resumable-streams.mdx`；讀 `ai@7.0.153` 的 `dist/index.js`）：
- 伺服器照跑，瀏覽器斷線只是斷線；`useChat` 的 `stop()` 在這種設計下只是斷線，所以**另設停止端點**：取消產生串流的工作、清掉對話的 active stream（只在它還指著同一條時）。
- 重連是 `GET .../{chatId}/stream`，沒有在跑的回 **204**（`HttpChatTransport.reconnectToStream` 收到 204 回 `null`，`Chat` 回到 `ready`）；`prepareReconnectToStreamRequest` 可以改網址，`resumeStream({ metadata })` 的 `metadata` 交給它。
- `DefaultChatTransport` 的 `resumeStreamIsReplay` 預設 `true`：重連的串流**從頭重播**，`Chat` 在第一個 `start` 重設那一則（`resetStateOnFirstMessageStart`），不接在上一則助理訊息後面。
- 對話記 `activeStreamId`，重連與停止都看它。

ChatGPT、Claude.ai 的行為（使用者在票上的描述）：重新整理、換頁、關分頁再回來，正在產生的那一則接著出現；只有停止鍵會停。

**與 AI SDK 範例不同的地方**：
- 串流暫存放程序內記憶體，不用 `resumable-stream` + Redis：Berth 是單一程序，`AgentRuntime` 本來就一個程序一份。
- 不另存 `activeStreamId`：`ai_runs.stop_reason IS NULL` 就是在跑的那一輪。歷史與停止原因同一個 commit 寫，讀對話時同一個 session 讀到的是一致的快照。
- 停止不用 pydantic-ai 2.62 的 `CancellationToken` / `RunCancelled`（它保留串流到一半的回應）：沿用取消 task 那條已經測過的路，停下時存的與其他停下一樣，到最後一次模型呼叫之前。

**決定**（寫進 plan §11.6〈串流〉與 §6〈agent〉）：
1. 一輪是 `AgentRuntime` 名下的 asyncio task。`POST /agent/chat` 開輪、起 task，回一條跟著看的串流；連線斷了只斷那一條。
2. 同一個人同時只有一輪（原本的佔位子，現在佔到 task 收尾），所以同一段對話也只有一輪；重連是 GET，不開輪。task 一定會收尾，所以「串流沒開始的位子 60 秒後回來」拿掉。
3. 開輪時歷史先存「之前的歷史 + 這一則使用者訊息」。`GET /agent/conversations/{id}` 多 `running`（在跑那一輪的 id）：在跑時讀到的是那一輪開始之前的樣子，重連從頭重播剛好接上；跑完的直接從歷史讀。重連 `GET /agent/conversations/{id}/stream?turn=<id>`：那一輪還在（或跑完 60 秒內）就從頭重播並跟著，否則 204。
4. 停止：`POST /agent/conversations/{id}/stop`（`agent.stop_turn`）取消那一輪、等它收尾，回 204；每一條跟著看的串流最後都收到同一個 `data-stop`。沒有在跑的回 409 `not_running`。
5. 伺服器重啟：正常關機時（lifespan）還在跑的那一輪記成 `interrupted`，存到最後一次模型呼叫之前、接一則說明。崩潰時（沒走到關機那一段）由啟動時的 `agent.close_interrupted` 把 `stop_reason IS NULL` 的都記成 `interrupted`、補一則說明，語言照那個人的 `notify_language`。
6. 多個分頁：每個分頁都能各自重連、跟著同一輪；任一個按停止，全部收到停下。在跑時另一個分頁送出是 409 `busy`，面板接回伺服器的對話並跟上那一輪。閒著的分頁不會自己發現別的分頁開了一輪，下一次送出或重新整理才接上。
7. `cancelled` 只指使用者按了停止（「你按了停止」）；新增 `interrupted`（Berth 重新啟動）。「連線被關掉」這句拿掉。

### 2026-10-28 code-review（兩軸）

**已修**：
- 開輪之後到起 task 之間出錯會讓這個人一直 `busy`、`ai_runs` 一直像在跑。現在模型與 agent 在佔位子之前組好，串流在 task 裡才組（`AgentRuntime.start` 收的是 `Chunks`），組到一半出錯照樣記成 `error` 收尾（測試 `TestATurnThatBreaks`）。
- `_drive` 收尾時 `aclose` 出錯會跳過 `Turn.close`：改成 try/finally。
- 按停止剛好落在 `Turn._finish` 的 commit 上：`_finish` 的寫入擋住取消。
- 起 task 改成 services 的命令 `agent.start_turn`（CLAUDE.md：改狀態的都是 services 的命令）。`start_turn`、`stop_turn`、`close_interrupted` 的標記與理由寫進 `test_command_marks.NAMED`。
- `LiveTurn` 不再抄 `Turn` 的識別資料，誰的、哪一輪看 `_Running.turn`；兩個 `cut` 改名為 `ending`（收尾的片段）與 `cancelled_as`（停止原因）。
- 兩句「關掉連線」的舊註解（`CONTINUABLE`、`agent_guards`）改掉。
- 關機那條測試寫明它怎麼跟啟動時補記分開：語言不同，而且歷史裡有工具結果。

**沒有處理**（判斷題）：
- `stop_turn`、`start_turn` 只是轉給 `AgentRuntime`（Middle Man）。留著，因為規則要求改狀態的入口是 services 命令。
- `AgentRuntime` 管的事變多了（防護數字、斷路器、位子、task 與重播）。它本來就是「一個程序一份」的那個物件，暫時不拆。
- `stop_text` 收 `runtime` 只為了讀 `limits` 與 `breaker`。
- 前端 transport 的 `fetch` 從網址剝掉 `/api` 前綴，只用來組錯誤訊息裡的路徑。
- 停止與自然答完撞在一起時照它自己的結果收、回 204；沒有測試。
- 關機時 uvicorn 先等開著的連線收掉，所以有人在看的那一輪多半自己跑完；被強制結束的走啟動時的補記。已寫進 plan，沒有實測 Docker 的 SIGTERM → SIGKILL。

### 2026-10-28 協調者追加：被「每人同時一輪」擋下時說是哪一段

- 伺服器的 `busy` 回應，detail 帶在跑的那一段對話的 id（`AgentRuntime.claim(user_id, conversation_id)`）。位子以人為單位，所以只會是本人的。`/compact` 佔位子時也記那一段。
- 面板（`BusyElsewhere`）：在跑的是自己的另一段對話時，說是哪一段（對話沒有標題，用它的第一句使用者的話，截 40 字）。可以「到那一段對話」（`switchTo`，接過去後重連它的串流），或「停止那一輪」（打那一段的 `POST .../stop`；回 `not_running` 也當作停了）。停掉之後字還在輸入欄，按送出就是重送。在跑的是同一段對話時，照舊接上那一輪。
- 測試：
  - 後端 `TestBusySaysWhichConversation`：busy 帶本人的 id，停掉之後重送成功；別人在跑不擋我，回應裡也沒有那段對話。
  - vitest 3 條：說出是哪一段、停止並重送；點過去接上；同一段時不提別段。三種變異各紅過。
  - e2e：舊對話「慢慢查」→ 新對話 → 送出 → 看到提示 → 停止 → 重送成功，1280 與 390 各一。
- e2e 用頁首的「新對話」鍵，不打 `/new`：這一頁還在跟著舊的那一輪時，輸入欄不收指令（送出與斜線指令都要等它答完）。兩者做的是同一件事（`startNew`）。
