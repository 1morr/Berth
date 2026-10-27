# M5 AI 對話 prototype（2026-10-27）

這是 [M5 方向報告](m5-ai-direction-2026-10-27.md)「Prototype 要回答的問題」的實驗紀錄。
腳本：`scripts/experiments/m5_agent_chat.py`（伺服器與 agent）、`m5_agent_chat.html`（側面板）、
`m5_agent_selftest.py`（不需要金鑰的生命週期測試）。用法見 `scripts/experiments/README.md`。

## 版本

| 套件 | 版本 |
| --- | --- |
| pydantic-ai-slim（anthropic、openai、ui） | 2.61.0（anthropic SDK 2.3.0、openai SDK 3.39.0、genai_prices 0.1.13） |
| ai / @ai-sdk/react | 7.0.138 / 4.0.141（esm.sh，`deps=zod@3.25.76`） |
| react | 19.2.8 |

## 形狀

- Berth 不動。prototype 是一個 Starlette 行程，工具透過 HTTP 打一台跑著的 Berth（真的部署，或 `scripts/fake_setup_server.py`）。
- **歷史由伺服器保管**。對話的 `ModelMessage` 序列化成 JSON 存在 SQLite（`ModelMessagesTypeAdapter`）。
  前端只送最後一則訊息：新的使用者訊息，或帶核准回應的那則助理訊息。
  `VercelAIAdapter` 的子類別把 `messages` 換成「只取最後一則使用者訊息」。
- **確認卡就是 Proposal 一列**：
  - 寫入工具先跑防護，再丟 `ApprovalRequired`。
  - 丟之前寫一列 `proposals`：參數、雜湊、預覽、是否讀過外部內容、過期時間。
  - 使用者按卡片時只記決定（`POST /api/proposals/{id}/decide`，可帶勾選的列）。
  - 恢復時伺服器從表裡組 `DeferredToolResults`，核准用 `ToolApproved(override_args=存下的參數)`。
    前端送來的參數與 approval 內容只當觸發，不採用。
- **防護**：
  - id 必須出自這段對話已存的工具結果。
  - Feed 網址必須逐字出自使用者的話。
  - 同一工具同一組參數：第 2 次警告、第 3 次擋下、第 4 次中止整輪。
  - 每輪 `UsageLimits`：10 次請求、400K input、30K output；每次呼叫 `max_tokens` 4096。
- **壓縮**：
  - 由 `ProcessHistory` 處理，每輪開頭檢查一次。上一則回應的 input token 超過門檻就壓縮。
  - 切點一定落在使用者訊息上，保留最後兩個使用者回合，之前的換成一段摘要。
  - 被切掉的 tool call 留下的孤兒 tool result 會一起拿掉。
  - `/compact` 強制壓縮。
- **觀測**：
  - 三張表：`ai_runs`、`ai_calls`、`ai_tool_calls`。
  - 側欄顯示每一輪的步數、token、快取讀寫、估計費用、停止原因和每個工具呼叫的結果。
  - `/stats` 列出全部紀錄。

## 結果：不需要金鑰的部分（問題 1、2、4、5）

`uv run --env-file .env scripts/experiments/m5_agent_chat.py --selftest` 的輸出：
假模型照腳本呼叫工具，假 Berth 用 `httpx.MockTransport`。

```
1. 下載請求 → 讀取工具自動跑、寫入工具停在確認卡
  ✓ 串流裡有 tool-approval-request
  ✓ proposals 表多了一列 pending
    卡片預覽： {"title": "Re:Zero 第一、二季", "kind": "checklist", "items": [{"label": "S01E01–E25 第一季", "media": "Re:ゼロから始める異世界生活", "source": "[LoliHouse] Re:Zero S1 01-25", "route": "Anime"}, {"label": "S01E26–E50 第二季
  ✓ 還沒有任何送單
  ✓ 重啟後卡片還在
3. 偽造：前端宣稱核准一個不存在的 tool call
  ✓ 伺服器拒絕（409 有卡片還沒決定）
  ✓ 沒有送單
4. 在卡片上只勾第二列並確認，再由前端觸發恢復（前端送來竄改過的參數）
  ✓ 決定記下了
  ✓ 只送了勾選的那一列，且用伺服器存的參數（[{'source_id': 'src-2', 'media': 'tv:65942', 'route': 3}]）
  ✓ 卡片狀態 executed
  ✓ 模型拿到結果並接著回答
5. id 防護：模型自己編了一個 source_id
  ✓ 擋下，沒有出卡片（['guard_blocked']）
6. 重複呼叫：同一個工具同一組參數一直叫
  ✓ 第 2 次警告、第 3 次擋、第 4 次中止整輪（['ok', 'loop_warned', 'loop_blocked', 'loop_abort']）
  ✓ ai_runs.stop_reason = loop（{'stop_reason': 'loop', 'error': '同一個呼叫第 4 次：berth_routes'}）
  ✓ 前端收到 error chunk
7. 沒按卡片就繼續說話 → 卡片脫離；之後再按，由伺服器直接執行
  ✓ 卡片 detached
  ✓ 直接執行
  ✓ 兩列都送了（2）
  ✓ 下一輪的 instructions 告訴模型那張卡片的結果
8. 有待確認的卡片時壓縮（/compact）→ 卡片還在、按了照常恢復
     已壓縮：34 則訊息 → 10 則。待確認的卡片不受影響（存在 proposals 表）。
  ✓ 歷史變短（34 → 10）
  ✓ 開頭是摘要
  ✓ 最後那張待確認的卡片仍在歷史結尾
  ✓ 壓縮後照常執行
9. 自動壓縮：門檻壓到很低，下一輪開頭自己壓
  ✓ 自動壓縮了（12 則 + 新的一輪 → 12 則，開頭是摘要），on_complete 存下的是壓縮後的歷史
  ✓ 壓縮本身也記一筆 run（2 筆）
10. 重新載入頁面：伺服器把歷史轉回 UI messages
    part 型別： ['text', 'tool-berth_discover_search', 'tool-berth_routes', 'tool-berth_search_torrents', 'tool-submit_downloads']
  ✓ messages、runs 都有
全部通過。
```

另以 `--demo` 起頁面，用 playwright 在瀏覽器實際走了一遍：
- 下載請求出總覽卡。
- 重新載入頁面後，對話和卡片從伺服器恢復。
- 取消一列再按確認，只送出勾選的那一列。
- 輸入 `loop` 時，側欄的工具標記依序是警告、擋下、中止，並顯示錯誤。
- `/usage` 有回應。

## 發現

1. **Vercel adapter 預設信任前端的核准與參數**（`ui/_adapter.py` 的 `run_stream_native`、`vercel_ai/_adapter.py` 的 `deferred_tool_results`）。
   - 偽造一則「已核准」的助理訊息，工具就會用偽造的參數執行。
   - 官方文件也寫了：「Tool approval responses are trusted from the request by design」。
   - 正式版要同 prototype：歷史放伺服器、從 Proposal 表組 `deferred_tool_results` 傳給 `run_stream`。selftest 第 3、4 步驗過。
2. **`sdk_version` 預設是 5**，5 沒有核准串流，要傳 6 或 7。7 的 wire 與 6 相同。
3. **所有待確認的 tool call 必須一起解決**，否則會 `UserError`。
   - 使用者沒按卡片就繼續說話時，pydantic-ai 會自己補一句 "interrupted" 當結果。
   - prototype 改成明確回 `ToolDenied`，並把卡片標成 `detached`。之後再按，由伺服器直接執行，下一輪的 instructions 帶上結果（selftest 第 7 步）。
   - 結論：**Proposal 的生命週期要獨立於 agent run**。
4. **`ApprovalRequired` 在工具裡丟**，比 `requires_approval=True` 合用：
   - 丟之前可以先跑防護、算預覽，所以預覽和執行用的是同一段程式碼。
   - 恢復時 `ctx.tool_call_approved` 為真。
5. **壓縮之後卡片還在**，原因有兩個：
   - 切點在使用者訊息上，待確認的 tool call 一定在保留的尾巴裡。
   - 卡片的事實來源本來就是 Proposal 表。
   - `ProcessHistory` 改過的歷史就是 `all_messages()` 回傳的那份，存下的就是壓縮後的版本（selftest 第 8、9 步）。
6. **run 中途被中止時，這一輪的歷史和 token 用量都會遺失**：
   - 中止的原因包括 `UsageLimitExceeded`、重複呼叫中止、模型錯誤。
   - `on_complete` 只在成功時呼叫，所以 `ai_runs` 那一列記成 0 token。
   - 正式版要在每次模型呼叫之後當場記帳（capability 的 `after_model_request` 這類 hook），並決定被中止的那一輪要不要留下使用者的訊息。
7. **重新載入頁面**：
   - `VercelAIAdapter.dump_messages(history, sdk_version=7)` 把沒有結果的 tool call 轉成 `state: approval-requested`。
   - 所以重新載入之後，`addToolApprovalResponse` 照樣能用。
   - 一則助理回應會被拆成幾則 UI 訊息，畫面上分成幾塊，不影響功能。
8. **費用**：
   - `ModelResponse.cost()` 走 genai_prices。它不認得的模型（新模型、OpenAI 相容閘道上的模型）要有自己的價目表。
   - Anthropic 的 `input_tokens` 已經包含快取讀和寫。
   - `web_search` 的次數在 `usage.details['web_search_requests']`，每次 /bin/zsh.01 要另外算。
9. **instructions 每次請求都從 agent 設定重新產生**。
   - prototype 把「最近的確認卡」放進 instructions，卡片一變，系統提示的快取就失效。
   - 這筆代價要用真的模型量（問題 3）；量出來太貴的話，改成附在使用者訊息裡。

## 還沒回答（需要金鑰，交給使用者實測）

- **問題 3**：情境 1（新番推薦）與情境 2（Re:Zero 全系列）的實際品質、步數、token、費用。這會決定防護的數字。
- **問題 6**：Anthropic 官方端點與 OpenAI 相容端點的差異，包括快取、工具呼叫格式、串流、網搜只在 Anthropic。
- `AnthropicCompaction`（伺服器端壓縮，beta）沒有實測；prototype 用的是自己的摘要。
- 實測方法：
  1. 填好 `.env`。
  2. 起 Fake 後端：`--scenario submit`（TMDB 打真的，索引站是替身），或 `search`（索引站也打真的）。
  3. `uv run --env-file .env scripts/experiments/m5_agent_chat.py`，開 http://127.0.0.1:8585。
  4. 跑完看側欄與 `/stats`。
