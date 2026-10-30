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
     已壓縮：34 則訊息 → 8 則。待確認的卡片不受影響（存在 proposals 表）。
  ✓ 歷史變短（34 → 8）
  ✓ 開頭是摘要
  ✓ 最後那張待確認的卡片仍在歷史結尾
  ✓ 壓縮後照常執行
9. 自動壓縮：門檻壓到很低，下一輪開頭自己壓
  ✓ 自動壓縮了一次（壓縮紀錄 1 → 2），存下的歷史開頭是摘要
10. 平行呼叫：卡片的呼叫不在歷史最後一則（另一個工具的結果排在後面）
  ✓ 找得到待確認的那一個，即使它不在最後一則
  ✓ 恢復並執行
11. 重新載入頁面：伺服器把歷史轉回 UI messages
    part 型別： ['text', 'tool-berth_routes', 'tool-submit_downloads']
  ✓ messages、runs 都有

全部通過。
```

第 10 步（平行呼叫）是真模型實跑抓到 bug 之後補的。另以 `--demo` 起頁面，用 playwright 在瀏覽器實際走了一遍：
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

## 結果：真模型（問題 3、6，2026-10-27）

### 環境

- **模型**：使用者的 `.env` 兩組都接 DeepSeek 的 `deepseek-flash`（DeepSeek-V4.1-Flash，1M context，預設 effort high，會思考）。
  - 「anthropic」那組走 `https://api.deepseek.com/anthropic`（Anthropic Messages 相容）。
  - 「openai」那組走 `https://api.deepseek.com`（Chat Completions 相容）。
  - 所以下面比較的是**同一個模型、兩種接口**，不是 Claude 對 GPT。
- **Berth**：`scripts/fake_setup_server.py --scenario search`。TMDB 打真的，索引站是使用者自己的 Prowlarr（真的），qBittorrent 是替身。每種接口各用一台全新的 Berth 和一個新的對話資料庫。
- **驅動**：`scripts/experiments/m5_agent_scenarios.py` 逐句送出，遇到確認卡一律按確認（勾全部）。
- **費用**：照 DeepSeek 2026-10-27 的價目（尖峰：輸入 $0.3、快取命中 $0.006、輸出 $1.2 / MTok；實測時是 UTC 07–08 點，週二尖峰）。DeepSeek `web_search` 的價格文件沒寫，不計。
- **輪次**：一共跑三輪。第一輪抓到 `berth_routes` 寫錯（`/api/routes` 回的是 `{"route": {...}}`）就中止。第二輪兩種接口共用同一台 Berth，前一個接口留下的訂閱與追蹤狀態干擾了後一個。下表是第三輪。
- **逐字稿**：每個情境的逐字稿在 [`m5-prototype-2026-10-27/`](m5-prototype-2026-10-27/)。

### 數字（第三輪）

| 接口 | 情境 | 秒 | 模型呼叫 | 工具 | input | 快取命中 | output | 費用 USD | 卡片 |
|---|---|---|---|---|---|---|---|---|---|
| anthropic | S1 新番推薦 → 訂閱 | 72 | 9 | 14 | 121,588 | 78% | 5,008 | 0.0147 | 1 |
| anthropic | S2 Re:Zero 全系列 → 壓縮 → 追問 | 146 | 16 | 24 | 218,327 | 71% | 10,110 | 0.0323 | 1 |
| anthropic | S4 為什麼沒入庫 | 14 | 3 | 5 | 70,302 | 97% | 1,994 | 0.0034 | 0 |
| anthropic | S3 冷門（宝石の国） | 51 | 8 | 11 | 52,626 | 71% | 3,510 | 0.0091 | 1 |
| anthropic | S5 使用者貼的 RSS | 13 | 4 | 5 | 13,113 | 46% | 912 | 0.0033 | 2 |
| anthropic | S6 要 AI 自己找 RSS 網址 | 29 | 5 | 6 | 25,609 | 86% | 2,001 | 0.0037 | 0 |
| openai | S1（修正恢復 bug 後重跑） | 72 | 9 | 14 | 117,423 | 77% | 5,359 | 0.0151 | 1 |
| openai | S2 | 155 | 15 | 25 | 224,712 | 46% | 11,555 | 0.0508 | 2 |
| openai | S4 | 16 | 5 | 7 | 160,946 | 98% | 1,690 | 0.0038 | 0 |
| openai | S3 | 40 | 9 | 11 | 46,089 | 89% | 2,150 | 0.0043 | 0 |
| openai | S5 | 9 | 4 | 5 | 12,828 | 45% | 1,074 | 0.0034 | 2 |
| openai | S6 | 21 | 3 | 4 | 11,773 | 76% | 1,815 | 0.0031 | 0 |
| **anthropic 合計** | | 325 | 45 | 65 | 501,565 | 76% | 23,535 | **0.066** | |
| **openai 合計** | | 313 | 45 | 66 | 573,771 | 71% | 23,643 | **0.081** | |

- **單輪最多**（一次使用者訊息或一次恢復）：9 次模型呼叫、15 次工具、161K input、5.3K output。
- **`berth_search_torrents`**：平均 6 秒，最慢 16 秒。比報告估的 35–85 秒快很多，因為使用者的 Prowlarr 站少。
- **壓縮**：`/compact` 兩種接口各一次，摘要本身約 3K input、1.2K output。
- **換成 Claude Sonnet 5.5 的價目（推估）**：同一份用量，六個情境約 $0.5–0.6，S2 一個約 $0.25–0.3。快取命中率沿用上表；Claude 的快取寫入要另付 1.25 倍。只是數量級，沒有實測。

### 品質

- **S1**：
  - 評分都附人數。
  - 兩極的作品（Cyberpunk：AniList 84 對 Bangumi 5.5）特別提醒。
  - 選中「黑色五葉草 第二季」，判斷還在播，走 Mikan 訂閱。
  - 看出字幕組沿用第一季的連續集號（171–174），而 TMDB 是 S02E01 起。
- **S2**：
  - AniList 走圖加 Fribb 對到 TMDB，明講「TMDB 把 S1–S4 併成 S01 共 85 集」。兩部劇場版各自是 movie 條目。
  - Fribb 的 offset 推出的區段有一集重疊，模型自己用總集數 85 改正成 26–38 / 39–50。
  - 總覽卡 7 列，附來源、大小、做種數與取捨。
  - 壓縮（28→16、26→12 則）之後問「剛剛送了什麼」，兩種接口都答對 7 列和各自的 TMDB 集數範圍。
- **S3**：兩種接口都一次對到同一個 TMDB / AniList 條目。anthropic 直接出卡；openai 先列四個來源（繁中但只有 1 個做種、雙語 206 個做種⋯）問要哪一個。兩種都合理。
- **S4**：只讀，查完 Job 和時間線。但結論被替身誤導，見下面第 7 點。
- **S5**：網址照抄、Route 對。但兩種接口都是第一張卡漏填電影 Route，按確認後被 Berth 拒絕（`422 route_required`），再出第二張卡，見下面第 3 點。
- **S6**：兩種接口都拒絕把搜尋到的網址直接加進去。
  - 說明網址只能由使用者貼，列出 Mikan 字幕組的 feed 讓使用者自己挑、貼回來。
  - 改建議用番組訂閱或送合集，並點出「第二季在 TMDB 是 S01E29–38」。
  - 第二輪有一次多出一張使用者沒要求的送單卡，被卡片擋住。

### 實跑才抓到的問題（prototype 已修或已記）

1. **確認後的工具結果要明說「已經按過、已經做了」**。
   - 第二輪模型拿到裸結果，說「確認卡已出，等你按下去」，或把自己剛建的訂閱說成「本來就存在」。
   - 結果改包成 `{"approved_by_user": true, "executed": true, "result": ...}` 之後，第三輪沒再出現。
2. **待確認的呼叫不一定在歷史最後一則**。
   - 模型在同一步平行叫 `fribb_lookup` 和 `subscribe_mikan`。前者先執行，它的結果排在後面，伺服器只看最後一則就找不到卡片，恢復回 400。
   - 改成「最後一則模型回應裡還沒有結果的呼叫」；selftest 第 10 步重現並守住。
3. **卡片預覽要先跑命令的驗證**。
   - `route_required`（Feed 沒給電影 Route）和 `route_kind_mismatch`（劇場版放進 Anime Route）都在使用者按了確認之後才被 Berth 拒絕，只好再出一張卡。
   - 正式版的命令登錄表要有 `validate` / 乾跑，預覽時就擋下。
4. **總覽卡會部分成功**：7 列裡 5 列送出、2 列被拒。卡片要逐列顯示結果，而不是只有一個「已執行」。
5. **連線失敗後的重試不是迴圈**。本機網路不穩時，模型重試同一個呼叫被算成重複、警告了 3 次。已改成失敗的呼叫不計數。
6. **「讀過外部內容」的警示每張卡都亮**。
   - 幾乎每段對話都搜過 torrent，警示失去意義。
   - 要縮小到「帶自由文字參數，且那段文字出自外部內容」（例如 `subscribe_search` 的 `term`）。
7. **替身 qBittorrent 收單後立刻回報「被移除」**（`client_removed`）。
   - 模型照資料推論成「qBittorrent 端拒收」，還指出存檔路徑是相對路徑。以手上的資料來說推理合理，但結論是替身造成的。
   - M5 的對話 e2e 要一個收下就留著的替身。
8. **一輪 10 次模型呼叫的上限太緊**：實測單輪最多 9 次（S2 搜六、七種關鍵字的那一輪）。建議對話調到 15–20 次；input 400K、output 30K 的上限都還很寬。

### 兩種接口的差異（問題 6，只答了一半）

- 兩種都能跑完全部情境，工具呼叫、串流、確認卡、恢復、壓縮都沒有接口相關的錯誤。
- DeepSeek 的 Anthropic 相容端點：
  - 會忽略 `cache_control`，但自己會快取，`cache_read_input_tokens` 照樣回報。兩種接口的快取命中率相近（76% 對 71%）。
  - **會執行伺服器端 `web_search`**：手打一次，回了 `server_tool_use` 與 `web_search_tool_result`，`usage.server_tool_use.web_search_requests` = 1。
  - 但第三輪模型都改用 Tavily 或根本沒搜，`web_search` 次數是 0。
- 第 2 點的平行呼叫是在 OpenAI 相容接口上抓到的，但那是模型行為，兩種接口都可能遇到。
- **沒測到**：
  - Anthropic 官方端點（Claude）與 OpenAI 官方端點，使用者的兩組 key 都是 DeepSeek。
  - `AnthropicCompaction` 伺服器端壓縮。

## 從 brief 搬來（§20.24）

以下是 brief 原有、本檔上文沒有逐字寫過的段落（原文不改字）；「真模型實測」「實跑抓到」「觀測的缺口」「還沒測」在上文〈結果：真模型〉〈發現〉〈兩種接口的差異〉已有。

- **deferred tool 可以存成一列、重啟之後接著跑**：
  - 工具丟 `ApprovalRequired` 時，run 以 `DeferredToolRequests` 結束。這需要 `output_type` 含 `DeferredToolRequests`。
  - 歷史用 `ModelMessagesTypeAdapter` 存成 JSON。
  - 另一個請求、甚至另一個行程，帶 `message_history` 與 `DeferredToolResults` 就能恢復。核准用 `ToolApproved(override_args=...)`，參數以伺服器存的為準。（Berth 的正式版改成核准就由伺服器當場執行，恢復只交結果，M5 票 13，見下方〈確認卡的恢復〉。）
  - 恢復時工具裡的 `ctx.tool_call_approved` 為真，所以「丟之前跑防護、算預覽」與「核准後執行」是同一個函式。
  - 待確認的呼叫**必須一次全部解決**，否則 `UserError`。使用者沒按就繼續說話時，pydantic-ai 會自己補一句 "interrupted"。
  - 所以 **Proposal 的生命週期要獨立於 agent run**。卡片脫離對話之後再按，由伺服器直接執行，下一輪告訴模型結果。
- **`VercelAIAdapter` 預設信任前端**：
  - 前端送回的核准與工具參數都照收。偽造一則「已核准」的助理訊息，工具就會用偽造的參數執行。官方文件明說這是設計。
  - `sdk_version` 預設 5，沒有核准串流，要傳 6 或 7（兩者 wire 相同）。
  - Berth 的做法：歷史放伺服器，前端只送最後一則；`deferred_tool_results` 從 Proposal 表組好再傳給 `run_stream`，前端的 approval 只當觸發。
  - `dump_messages(..., sdk_version=7)` 把沒有結果的 tool call 轉成 `approval-requested`，所以重新載入頁面後卡片照樣按得下去。
- **壓縮**：
  - `ProcessHistory` 改過的歷史就是 `all_messages()` 回傳的那份。
  - 切點落在使用者訊息上，待確認的 tool call 一定留在尾巴；被切掉的 tool call 留下的孤兒 tool result 要一起拿掉，否則 Anthropic 會拒收。
  - `AnthropicCompaction`（伺服器端，beta）與 `OpenAICompaction`（只適用 Responses API）沒有採用。
  - 2026-10-27 讀 pydantic-ai-slim 2.62.0 原始碼（M5 票 18）：
    - 摘要放在 `ModelRequest` 裡的 `CompactionPart(content=...)`：每一家都以使用者語氣送出、包在 `<conversation_summary>` 並說明是另一個模型寫的（`models/__init__.py` 的 `_conversation_summary_text`），不當 system prompt。`VercelAIAdapter.dump_messages` 把它轉成 `data-compaction` 片段（`data.content` 是摘要）。
    - `RunContext.context_window_used` 是上一則回應的 token 對 `model.context_window`；模型資料（genai-prices）沒有這個模型的 window、或還沒有回應時是 `None`，不是 0。
    - `ProcessHistory` 在 `before_model_request` 換掉 `ctx.messages`，所以換掉的歷史就是之後 `all_messages()` 的那一份。
    - `RetryPromptPart` 已 deprecated（v3 移除）：工具的重試改成 `ToolReturnPart(outcome='retried')`。
    - 官方的 `pydantic-ai-harness` 0.62.0（Alpha、釘死 `pydantic-ai-slim==2.62.0`）有 `SummarizingCompaction`，但切點以訊息數或 token 數算、不認一輪從哪裡開始，不拿掉孤兒 result，也拿不到摘要那一次的回應來記帳，所以 Berth 自己寫（`services/compaction.py`）。
- **斷線之後接上（resumable streams）**（2026-10-28 查，M5 票 25）：
  - Vercel AI SDK 7 的做法（context7 `/vercel/ai/ai_7.0.0` 的 `04-ai-sdk-ui/03-chatbot-resume-streams.mdx`、`09-troubleshooting/15-abort-breaks-resumable-streams.mdx`）：伺服器在沒人看的時候照跑；`useChat` 的 `stop()` 只是中止這一個請求，這種設計下等於斷線，所以**停止要另一個端點**（取消產生串流的工作、清掉對話的 active stream，只在它還指著同一條時）。對話記 `activeStreamId`，重連是 `GET .../{chatId}/stream`，沒有在跑的回 204。
  - 讀 `ai@7.0.153` 的 `dist/index.js`：`HttpChatTransport.reconnectToStream` 收到 204 回 `null`，`Chat` 回到 `ready`；`prepareReconnectToStreamRequest({ id, requestMetadata })` 可以改網址，`chat.resumeStream({ metadata })` 的 `metadata` 就是 `requestMetadata`。`DefaultChatTransport` 的 `resumeStreamIsReplay` 預設 `true`：重連的串流**從第一個片段重播**，`Chat` 在第一個 `start` 重設那一則（`resetStateOnFirstMessageStart`），不接在上一則助理訊息後面（只有最後一則助理訊息有進行中的工具片段時才接）。
  - pydantic-ai-slim 2.62 有自己的停法（`CancellationToken`、`RunCancelled`，`on_cancel`）：它保留串流到一半的回應與已完成的工具結果；task 被外部取消（`asyncio.Task.cancel()`、cancel scope）則照樣是 `CancelledError`，兩者同時發生時外部的贏（`pydantic_ai/exceptions.py` 的 `RunCancelled` docstring）。Berth 的停止走後者，停下時存的與其他停下一樣（plan §6〈agent〉）。
  - Starlette 的 `StreamingResponse` 在 ASGI spec 2.4 之前另開一個 task 聽 `http.disconnect`，收到就取消整個串流；2.4 起改成送出時的 `OSError`（`starlette/responses.py`）。所以一輪若跑在請求裡，斷線就是取消它；要跑完得放在請求之外的 task。
- **費用**：
  - ~~`ModelResponse.cost()`（genai_prices）不認得的模型要有自己的價目表~~（M5 票 21b 改寫成下面這幾條）。
  - **價目用 genai-prices**（[pydantic/genai-prices](https://github.com/pydantic/genai-prices)，pydantic-ai-slim 2.62.0 的相依，要求 `>=0.1.13`；2026-10-28 讀 0.1.13 原始碼與實測，M5 票 21b）：
    - `calc_price(usage, model_ref, provider_id=..., provider_api_url=...)` 先用 `provider_api_url` 對每家的 `api_pattern`（regex）認服務商、再找模型；認不得網址或模型是 `LookupError`。`https://api.deepseek.com/anthropic` + `deepseek-flash` 認成 `deepseek`（100 萬 input + 100 萬 output 在離峰是 $0.75）；同一組改傳 `provider_id=anthropic` 查不到，所以**接口種類不能當服務商**，只在網址認不得時退一步用。pydantic-ai 的查價順序也是網址 → provider 名（`_genai_prices.iter_provider_references`），但它遇到任何 `LookupError` 都退回，連「網址認得、那一家沒有這個模型」也是；Berth 在這種情況當查不到（M5 票 21b 的 code-review）。
    - 價錢帶時間：DeepSeek 的尖峰（UTC 01–04、06–10）是離峰的兩倍，`genai_request_timestamp` 決定套哪一段（週末全天離峰它還表達不了，那時的價是上限）；Anthropic 的長 context 與 OpenAI 的 gpt-5.5 有分級價（`+tiers`）。
    - 「回應的時間」就是收到的那一刻（pydantic-ai 2.62 原始碼 `models/anthropic/_streaming.py` 的 `AnthropicStreamedResponse`、`models/openai.py` 的 `OpenAIStreamedResponse`，票 21c 讀）：`AnthropicModel` 與 `OpenAIChatModel` 的串流回應在第一個片段到了之後才建，`timestamp` 一律是那時的本機時鐘（`_utils.now_utc()`）；服務端的 `created` 只進 `provider_details`。所以記帳照回應時間查價，等於照收到第一個片段那一刻；測試用的 `FunctionModel` 串流同樣用本機時鐘，腳本給的 `timestamp` 留不下來，控制時段要釘時鐘。
    - **DeepSeek 官方價目**（[api-docs.deepseek.com/quick_start/pricing](https://api-docs.deepseek.com/quick_start/pricing)，2026-10-28 協調者讀）：`deepseek-flash` 尖峰 $0.3 / $1.2（每百萬 input / output），離峰減半 $0.15 / $0.6；尖峰是週一到週五 UTC 01:00–04:00、06:00–10:00，其餘時間（含週末與中國國定假日）都是離峰。與 genai-prices 0.1.13 的資料一致，只差它把週末與假日的那兩段也當尖峰（只會高估）。所以設定頁與用量頁出現的半價是**離峰價，不是過時的價**；M5 票 09 手寫表的 $0.3 / $1.2 是尖峰價。
    - `usage.input_tokens` 含快取讀寫；快取比 input 還多是 `ValueError`。沒有快取寫價的服務（DeepSeek）快取寫照輸入價算。
    - **自動更新是 opt-in**：只有 `UpdatePrices().start()`（或 pydantic-ai 的 `prices.update_in_background()`）會每小時從 GitHub 抓 `data.json`，抓到的換掉全域 snapshot（`data_snapshot.get_snapshot()`）；不開就不連網。Berth 自己用套件內附的資料建一份 `DataSnapshot(providers=genai_prices.data.providers, from_auto_update=False)`，別人開了自動更新也不受影響。
    - 0.1.13 已認得 M5 票 09 手寫表上的全部模型（Claude 5.5 家族、`claude-fable-5-1`、DeepSeek V4 與 `deepseek-flash`），Berth 的補位表因此是空的。
  - Anthropic 的 `input_tokens` 已經包含快取讀與寫。
  - `web_search` 的次數在 `usage.details['web_search_requests']`，每次 $0.01。
- **provider**：
  - `AnthropicProvider(base_url=...)` 不含 `/v1`（SDK 會自己接 `/v1/messages`）；`OpenAIProvider(base_url=...)` 照那家服務的文件（OpenAI 官方含 `/v1`，DeepSeek 的 `https://api.deepseek.com` 不含也能用）。
  - **anthropic SDK 2.x 把 `api_key` 放在 `Authorization: Bearer`**，不是舊版的 `x-api-key`（2026-10-27 讀 anthropic 2.3.0 的 `_client.py` 與 M5 票 09 的 MockTransport 測試）。只認 `x-api-key` 的相容閘道會回 401，測試連線照實說「key 被拒」。
  - 兩家 SDK 在 `api_key` / `base_url` 沒給時讀環境變數（`ANTHROPIC_API_KEY`、`ANTHROPIC_BASE_URL`、`OPENAI_BASE_URL`，anthropic 另讀 `ANTHROPIC_CONFIG_DIR` 底下的 profile）；Berth 一律明給（M5 票 09）。
  - pydantic-ai-slim 2.62.0（2026-10-27 的 stable）的 provider 吃 `httpx2.AsyncClient`；`ModelSettings` 可以逐次給 `max_retries` 與 `timeout`。錯誤分類：`ModelAuthenticationError`、`ModelNotFoundError`、`ModelConnectionError`（含逾時）都是 `ModelAPIError` 的子類，帶 HTTP 狀態碼的同時是 `ModelHTTPError`（`body` 是服務回的原文）。
  - 伺服器端 `web_search` 走 Anthropic Messages 才有（Anthropic 官方，以及 DeepSeek 的相容端點）；Chat Completions 沒有，要另接 Tavily 這類工具。
- **串流時的 capability hook**（2026-10-27 M5 票 11 實測，pydantic-ai-slim 2.62.0、`VercelAIAdapter.run_stream`）：
  - `wrap_model_request` 每次呼叫都拿得到完整的 `ModelResponse`（含 `usage`），記帳掛在這裡就夠。
  - 模型串流到一半出錯時，`wrap_model_request` 的 handler 丟的是 `CancelledError`，真正的例外只到 `on_run_error`。
  - run 出錯（含 capability 自己丟的例外）時，串流送 `error`（`errorText` 是例外的字串）、`finish-step`、`finish`（`finishReason: error`），`on_complete` 不跑。
  - `SubmitMessage` 是 `extra='allow'`：`useChat` 透過 transport 的 `body` 加的欄位（Berth 的 `language`）在 `model_extra`。
  - `FunctionModel` 要另給 `stream_function` 才能串流（`adapters/ai/fake.py` 從同一則回答拆出片段）。
- **確認卡的恢復**（2026-10-28 M5 票 13 讀原始碼與整合測試；pydantic-ai-slim 2.62.0、ai 7.0.153）：
  - `ToolApproved.override_args` 只換掉傳進工具的參數，**不改歷史裡的 `ToolCallPart`**（`pydantic_ai/_tool_execution.py` 的 `_validate_approved_call` 用 `dataclasses.replace` 複製一份）。
  - `DeferredToolResults` 與新的使用者訊息可以同一輪給（`_agent_graph.py` 的 `_handle_deferred_tool_results` 直接進 `CallToolsNode`）；但經 `VercelAIAdapter` 時新訊息是放進 `message_history` 的，工具結果會排在它後面。
  - `dump_messages` 把沒有結果的呼叫轉成 `approval-requested` 時，`approval.id` 就是 `tool_call_id`（`ui/vercel_ai/_adapter.py`）。
  - **ai 7 的前端只在當前那一則助理訊息裡找工具呼叫**：串流對上一則訊息裡的呼叫送 `tool-output-*` 時丟 `UIMessageStreamError`「No tool invocation found」（`ai/src/ui/process-ui-message-stream.ts` 的 `getToolInvocation`）。恢復時最後一則是助理的，串流接在那一則上，所以沒事；使用者沒按卡就送新訊息時會出事——Berth 改成由伺服器替那幾個呼叫補上結果、再接新訊息（`tests/integration/test_agent_cards.py::TestMovingOn`）。
  - `addToolApprovalResponse` 之後 `sendMessage()`（不帶訊息）送出恢復的那一則，接在那一則助理訊息上（`ai/src/ui/chat.ts`）。
- **網路搜尋**（2026-10-27，M5 票 17）：
  - Anthropic `web_search`：**$10 / 1,000 次**，另外搜尋結果算輸入 token；出錯的那次不收費。`max_uses` 是**每個請求**的上限，超過時那一次的結果是 `max_uses_exceeded` 錯誤（HTTP 照樣 200）。`allowed_domains` 與 `blocked_domains` 二選一，**自動含子網域**（`example.com` 涵蓋 `docs.example.com`），組織在 Console 設了允許清單時，請求的 `allowed_domains` 必須是它的子集，否則 400。和自己的工具平行呼叫時 API 先不跑搜尋、回 `tool_use`，下一個請求才搜。`web_search_20260209` 以後的版本經 code execution 做動態過濾（pydantic-ai 依模型自己選版本）。（[Web search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)、[Server tools〈Domain filtering〉](https://platform.claude.com/docs/en/agents-and-tools/tool-use/server-tools)）
  - **改工具定義（名字、說明、參數）會讓整段 prompt 快取失效**（快取的順序是 tools → system → messages）。所以 `max_uses` 每次請求固定，不照這一輪剩幾次調。（[Prompt caching〈What invalidates the cache〉](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)）
  - pydantic-ai-slim 2.62.0：`NativeTool` 可以給一個函式，每次模型呼叫前回 `WebSearchTool` 或 `None`（這一步不掛）；`usage.details['web_search_requests']` 只在大於 0 時有；`FunctionModel` 接受全部 native tool，但串流版的 usage 是它自己估的，報不出網搜次數。`OpenAIChatModel` 送出歷史時略過伺服器端工具的片段，同一段對話換接口不會壞。
  - Tavily `POST https://api.tavily.com/search`：`Authorization: Bearer <key>`；`search_depth` 的 `basic` / `fast` / `ultra-fast` 1 credit、`advanced` 2 credit；`max_results` 0–20；`include_domains` 最多 300 個，**實測含子網域**（`wikipedia.org` 回 `en.wikipedia.org`、`reddit.com` 回 `www.reddit.com`）。成功回 `query`、`results[]`（`title`、`url`、`content`、`score`、`raw_content`、`id`）、`answer`、`images`、`request_id`、`response_time`（實測約 2 秒），每頁 `content` 約 1,300–1,500 字。錯誤的 body 是 `{"detail": {"error": "..."}}`：401 key 錯、400 參數錯（實測：`include_domains_mode` 不帶 `include_domains`）、429 限流帶 `Retry-After`、432 / 433 額度。免費每月 1,000 credit。（[Search API](https://docs.tavily.com/api-reference/endpoint/search)、[Rate limits](https://docs.tavily.com/documentation/rate-limits)、[Credits](https://docs.tavily.com/documentation/api-credits)；實測錄在 `tests/fixtures/http/tavily/`，`scripts/experiments/tavily_search.py`）

## 從 brief 搬來（§20.24，逐字）

全文、selftest 輸出與用到的版本在 [`docs/research/m5-prototype-2026-10-27.md`](research/m5-prototype-2026-10-27.md)，腳本是 `scripts/experiments/m5_agent_chat.py`。版本：pydantic-ai-slim 2.61.0、ai 7.0.138、@ai-sdk/react 4.0.141。
- **真模型實測**（DeepSeek `deepseek-flash`，Anthropic 與 OpenAI 兩種相容接口各跑六個情境；TMDB 與索引站是真的，qBittorrent 是替身）：
  - **完成度**：兩種接口都跑完全部情境，沒有接口相關的錯誤。
  - **品質**：
    - Re:Zero 全系列能講清楚「TMDB 把 S1–S4 併成 S01 共 85 集、劇場版是獨立 movie」，總覽卡 7 列。
    - 壓縮之後追問「剛剛送了什麼」答得出來。
    - 新番推薦的評分都附人數。
    - 要 AI 自己找 RSS 網址時，兩種接口都拒絕，改用 Mikan 番組訂閱。
  - **用量**：
    - 一個情境 3–16 次模型呼叫；Re:Zero 那個最重，約 220K input、11K output、2.5 分鐘。
    - 快取命中 46–98%。
    - 六個情境合計約 $0.07–0.08（DeepSeek 尖峰價）；換成 Claude Sonnet 5.5 的價目推估約 $0.5–0.6。
    - 單輪最多 9 次模型呼叫，所以對話的往返上限 10 太緊，建議 15–20。
- **實跑抓到、正式版要照做的**：
  - 確認後的工具結果要明說已核准、已執行，否則模型會說「卡片已出，等你按」。
  - 待確認的呼叫要找「最後一則模型回應裡還沒有結果的」：平行呼叫時，別的工具的結果會排在它後面。
  - 卡片預覽要先跑命令的驗證：`route_required`、`route_kind_mismatch` 都是按了確認才被擋下，只好再出一張卡。
  - 總覽卡要逐列顯示結果，因為會部分成功。
  - 失敗後的重試不算重複呼叫。
  - 「讀過外部內容」的警示要縮小到「自由文字參數出自外部內容」，否則每張卡都亮。
- **還沒測**：Claude 與 OpenAI 的官方端點（這次兩組 key 都是 DeepSeek）、`AnthropicCompaction`。
- DeepSeek 的 Anthropic 相容端點會忽略 `cache_control` 但自己快取，也會執行伺服器端 `web_search`（`usage.server_tool_use.web_search_requests`）。
