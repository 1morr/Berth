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
