# 事實：AI 助理與 Discord

查證過的外部事實。編號沿用 brief 原本的節號（`§20.x`），程式碼與文件用它引用，編號不重用。索引在 [brief §20](../design-brief.md)。

## 事實

### 20.23 Discord bot 私訊（2026-10-21 查證，M4 拆票；同日 M4 票 121 實測）

全文與來源在 [`docs/research/discord-notifications.md`](discord-notifications.md)。拆票時用到的：

- 私訊是 `POST /users/@me/channels`（`recipient_id`）再 `POST /channels/{id}/messages`，純 REST、不需要 intent；bot 與收件人要有共同伺服器（`50278`），`50007` 是「不能傳訊息給這位使用者」。「bot 要先連過一次 gateway 才能發訊息」官方文件沒寫，實測不需要（下面）。
- 互動（按鈕、slash command）只有兩條路且互斥：gateway 的 `INTERACTION_CREATE`，或公開的 Interactions Endpoint URL（要回 PING、驗 Ed25519 簽章、3 秒內回應）。家用伺服器沒有公開網址時只能 gateway——M7 的事。
- 頻道 webhook 只綁頻道、不能私訊，使用者手動建的不能帶互動按鈕。Overseerr、Jellyseerr、Sonarr 都用它（Overseerr 系另有選填的 Discord ID 用來 @mention）。
- 429 的 body 有 `retry_after`（秒、浮點）與 `global`，header 有 `Retry-After`、`X-RateLimit-*`；`content` ≤ 2000 字元、一則最多 10 個 embed、所有 embed 文字合計 ≤ 6000。


**實測**（2026-10-21，M4 票 121，API v10，`scripts/experiments/discord_dm.py`；回應錄在 `tests/fixtures/http/discord/`；逐條原文在 [研究檔〈從 brief 搬來（§20.23）〉](discord-notifications.md#從-brief-搬來2023)）。兩個新建的 bot、一個只有使用者與 bot 的測試伺服器：

- **從沒連過 gateway 的 bot 私訊得到**：開 DM channel `200`、純文字與帶 embed 的訊息都 `200`，不需要 intent。開 DM channel 什麼情況都回 `200`，擋下來的是送訊息那一步，所以「按測試」要真的送一則。
- **沒有共同伺服器、使用者在共同伺服器關了私訊、bot 被踢出，回的是同一個錯**：`403` / `50278`；`50007` 一次都沒出現。Berth 分不出是哪一種，提示要把兩個補法一起說：把 bot 加進同一個伺服器、在那個伺服器打開「私人訊息」。伺服器的「私人訊息」跟著使用者的全域設定，預設可能是關的。
- **超過長度是 `400` / `50035`**：`content` 2001 字元是 `BASE_TYPE_MAX_LENGTH`；embed 合計 6001 字元是 `MAX_EMBED_SIZE_EXCEEDED`。長度檢查在共同伺服器檢查之前。**token 錯是 `401`**，沒有 `X-RateLimit-*` header。
- **送訊息的 bucket 一次 5 則**（`X-RateLimit-Limit: 5`），**失敗的請求（`400`、`403`）也扣額度**；額度一則一則補回（約 1 秒一則），連續送第 7 則遇到 `429`。`429` 的 body 是 `{"message", "retry_after", "global"}`（**沒有 `code`**），`retry_after` 是下一個空位（浮點），header `Retry-After` 是整個 bucket 重置、無條件進位成整數。開 DM channel 是另一個 bucket（`X-RateLimit-Limit: 100`）。
- **只私訊的邀請連結**是 `https://discord.com/oauth2/authorize?client_id=<application id>&scope=bot&permissions=0`；application id 由 `GET /applications/@me` 以 bot token 取得，Berth 只讀回應的 `id` 與 `name`（M4 票 123；[Application Resource](https://discord.com/developers/docs/resources/application)，2026-10-21 經 context7 查）。這一份回應沒有錄（含擁有者帳號），契約測試只用這兩格。
- **embed 的 `url` 不收沒有點的主機名**（M4 票 124，`discord_dm.py embed-url`）：`http://berth:8000/…` 是 `400` / `50035`（`URL_TYPE_INVALID_URL`），整則送不出；網域、`*.ts.net`、`nas.local`、IP、`localhost`、`[::1]` 都 `200`。同一個網址寫成 description 裡的 Markdown 連結九種都 `200`，所以 Berth 的連結放在 description（`adapters/notify/discord._description`）。手機上 Markdown 連結是否每一種都可點沒有逐一看。

### 20.24 pydantic-ai 的確認卡與 Vercel AI SDK 串流（2026-10-27 實測，M5 prototype）

全文、selftest 輸出與用到的版本在 [`docs/research/m5-prototype-2026-10-27.md`](m5-prototype-2026-10-27.md)，腳本是 `scripts/experiments/m5_agent_chat.py`。版本：pydantic-ai-slim 2.61.0、ai 7.0.138、@ai-sdk/react 4.0.141。後續各票讀的細節（2.62.0、ai 7.0.153）在同檔末尾〈從 brief 搬來（§20.24）〉，下面各條的粗體標籤就是那裡的條目名。

- **deferred tool 可以存成一列、重啟之後接著跑**：工具丟 `ApprovalRequired`，run 以 `DeferredToolRequests` 結束（`output_type` 要含它）；歷史用 `ModelMessagesTypeAdapter` 存成 JSON；另一個請求或行程帶 `message_history` 與 `DeferredToolResults` 就能恢復，核准用 `ToolApproved(override_args=...)`，參數以伺服器存的為準（正式版改成核准就由伺服器當場執行，恢復只交結果，M5 票 13）。恢復時 `ctx.tool_call_approved` 為真，所以「丟之前跑防護、算預覽」與「核准後執行」是同一個函式。
- 待確認的呼叫**必須一次全部解決**，否則 `UserError`。所以 **Proposal 的生命週期要獨立於 agent run**：卡片脫離對話之後再按，由伺服器直接執行，下一輪告訴模型結果。
- **`VercelAIAdapter` 預設信任前端**：前端送回的核准與工具參數都照收，偽造一則「已核准」的助理訊息就會用偽造的參數執行（官方文件明說是設計）。`sdk_version` 預設 5，沒有核准串流，要傳 6 或 7（wire 相同）。Berth 的做法：歷史放伺服器，前端只送最後一則；`deferred_tool_results` 從 Proposal 表組好再傳給 `run_stream`，前端的 approval 只當觸發。`dump_messages(..., sdk_version=7)` 把沒有結果的 tool call 轉成 `approval-requested`，重新載入頁面後卡片照樣按得下去。
- **壓縮**：`ProcessHistory` 改過的歷史就是 `all_messages()` 的那份；切點落在使用者訊息上，待確認的 tool call 一定留在尾巴，被切掉的 tool call 留下的孤兒 tool result 要一起拿掉，否則 Anthropic 會拒收。`AnthropicCompaction`（伺服器端，beta）與 `OpenAICompaction`（只適用 Responses API）沒有採用。2026-10-27 讀 pydantic-ai-slim 2.62.0 原始碼（M5 票 18）：摘要放 `CompactionPart`，各家以使用者語氣送出，不當 system prompt；`RunContext.context_window_used` 沒資料時是 `None`；`RetryPromptPart` 已 deprecated；官方 `pydantic-ai-harness` 0.62.0（Alpha）的 `SummarizingCompaction` 不認一輪從哪裡開始、不拿掉孤兒 result、拿不到摘要的回應記帳，所以 Berth 自己寫（`services/compaction.py`）。
- **斷線之後接上（resumable streams）**（2026-10-28 查，M5 票 25）：Vercel AI SDK 7 的做法是伺服器在沒人看的時候照跑，`useChat` 的 `stop()` 只中止這一個請求（等於斷線），所以**停止要另一個端點**；對話記 `activeStreamId`，重連是 `GET .../{chatId}/stream`，沒有在跑的回 204；重連的串流從第一個片段重播（`ai@7.0.153`）。pydantic-ai 的 `CancellationToken` 保留串流到一半的回應，外部 `Task.cancel()` 則是 `CancelledError`，兩者同時時外部贏；Berth 的停止走後者（plan §6〈agent〉）。Starlette 的 `StreamingResponse` 在 ASGI spec 2.4 之前聽到 `http.disconnect` 就取消串流，所以一輪要跑完得放在請求之外的 task。
- **觀測的缺口**：run 中途被中止（`UsageLimitExceeded`、重複呼叫、模型錯誤）時，`on_complete` 不會被呼叫，這一輪的歷史與 token 用量都拿不到。記帳要掛在每次模型呼叫之後。
- **費用**（M5 票 21b 改寫）：價目用 genai-prices（[pydantic/genai-prices](https://github.com/pydantic/genai-prices)，pydantic-ai-slim 2.62.0 的相依，`>=0.1.13`；2026-10-28 讀 0.1.13 原始碼與實測）。
  - `calc_price(usage, model_ref, provider_id=..., provider_api_url=...)` 先用 `provider_api_url` 認服務商、再找模型，認不得是 `LookupError`；`https://api.deepseek.com/anthropic` + `deepseek-flash` 認成 `deepseek`，改傳 `provider_id=anthropic` 查不到，所以**接口種類不能當服務商**，只在網址認不得時退一步用。「網址認得、那一家沒有這個模型」Berth 當查不到。
  - 價錢帶時間：DeepSeek 尖峰（UTC 01–04、06–10）是離峰的兩倍，`genai_request_timestamp` 決定套哪一段（週末全天離峰它表達不了，那時的價是上限）；Anthropic 長 context 與 OpenAI gpt-5.5 有分級價。回應時間就是收到第一個片段那一刻的本機時鐘（2.62 原始碼，票 21c）；測試控制時段要釘時鐘。
  - **DeepSeek 官方價目**（[api-docs.deepseek.com/quick_start/pricing](https://api-docs.deepseek.com/quick_start/pricing)，2026-10-28）：`deepseek-flash` 尖峰 $0.3 / $1.2（每百萬 input / output），離峰減半 $0.15 / $0.6；尖峰是週一到週五 UTC 01:00–04:00、06:00–10:00，其餘（含週末與中國國定假日）離峰。與 genai-prices 0.1.13 一致，只差它把週末與假日也當尖峰（只會高估）。設定頁與用量頁出現的半價是**離峰價，不是過時的價**；M5 票 09 手寫表的 $0.3 / $1.2 是尖峰價。
  - `usage.input_tokens` 含快取讀寫（Anthropic 同），快取比 input 還多是 `ValueError`；沒有快取寫價的服務（DeepSeek）快取寫照輸入價算。`web_search` 次數在 `usage.details['web_search_requests']`，每次 $0.01。
  - **自動更新是 opt-in**（`UpdatePrices().start()` 才會每小時抓 `data.json`）；Berth 自己用套件內附資料建一份 `DataSnapshot(..., from_auto_update=False)`。0.1.13 已認得 M5 票 09 手寫表的全部模型，Berth 的補位表是空的。
- **provider**：`AnthropicProvider(base_url=...)` 不含 `/v1`；`OpenAIProvider(base_url=...)` 照那家文件。**anthropic SDK 2.x 把 `api_key` 放在 `Authorization: Bearer`**（讀 2.3.0 的 `_client.py`），只認 `x-api-key` 的閘道會回 401，測試連線照實說「key 被拒」。兩家 SDK 沒給 `api_key` / `base_url` 時讀環境變數，Berth 一律明給（M5 票 09）。pydantic-ai-slim 2.62.0 的 provider 吃 `httpx2.AsyncClient`；錯誤分類 `ModelAuthenticationError`、`ModelNotFoundError`、`ModelConnectionError` 都是 `ModelAPIError` 的子類。伺服器端 `web_search` 只有 Anthropic Messages 才有（含 DeepSeek 的相容端點），Chat Completions 要另接 Tavily 這類。
- **真模型實測**（DeepSeek `deepseek-flash`，Anthropic 與 OpenAI 兩種相容接口各跑六個情境；TMDB 與索引站是真的，qBittorrent 是替身）：兩種接口都跑完全部情境，沒有接口相關的錯誤；一個情境 3–16 次模型呼叫，Re:Zero 最重（約 220K input、11K output、2.5 分鐘）；快取命中 46–98%；六個情境合計約 $0.07–0.08（DeepSeek 尖峰價），換成 Claude Sonnet 5.5 價目推估約 $0.5–0.6；單輪最多 9 次模型呼叫，所以對話的往返上限 10 太緊，建議 15–20。品質逐項在研究檔〈結果：真模型〉。
- **實跑抓到、正式版要照做的**：確認後的工具結果要明說已核准、已執行；待確認的呼叫要找「最後一則模型回應裡還沒有結果的」（平行呼叫時別的工具的結果會排在後面）；卡片預覽要先跑命令的驗證（`route_required`、`route_kind_mismatch` 都是按了確認才被擋下）；總覽卡要逐列顯示結果（會部分成功；Re:Zero 全系列的總覽卡 7 列）；失敗後的重試不算重複呼叫；「讀過外部內容」的警示要縮小到「自由文字參數出自外部內容」。
- **串流時的 capability hook**（2026-10-27 M5 票 11 實測，pydantic-ai-slim 2.62.0、`VercelAIAdapter.run_stream`）：`wrap_model_request` 每次呼叫都拿得到完整 `ModelResponse`（含 `usage`），記帳掛在這裡就夠；模型串流到一半出錯時 handler 丟的是 `CancelledError`，真正的例外只到 `on_run_error`；run 出錯時串流送 `error`、`finish-step`、`finish`（`finishReason: error`），`on_complete` 不跑；`SubmitMessage` 是 `extra='allow'`，`useChat` 的 `body` 加的欄位（`language`）在 `model_extra`；`FunctionModel` 要另給 `stream_function` 才能串流。
- **確認卡的恢復**（2026-10-28 M5 票 13 讀原始碼與整合測試；pydantic-ai-slim 2.62.0、ai 7.0.153）：`ToolApproved.override_args` 只換掉傳進工具的參數，**不改歷史裡的 `ToolCallPart`**；經 `VercelAIAdapter` 時新訊息放進 `message_history`，工具結果會排在它後面；`approval.id` 就是 `tool_call_id`。**ai 7 的前端只在當前那一則助理訊息裡找工具呼叫**，對上一則訊息的呼叫送 `tool-output-*` 會丟 `UIMessageStreamError`；恢復時最後一則是助理的所以沒事，使用者沒按卡就送新訊息時會出事，Berth 改成由伺服器替那幾個呼叫補上結果再接新訊息（`tests/integration/test_agent_cards.py::TestMovingOn`）。
- **還沒測**：Claude 與 OpenAI 的官方端點（這次兩組 key 都是 DeepSeek）、`AnthropicCompaction`。DeepSeek 的 Anthropic 相容端點會忽略 `cache_control` 但自己快取，也會執行伺服器端 `web_search`。
- **網路搜尋**（2026-10-27，M5 票 17）：
  - Anthropic `web_search`：**$10 / 1,000 次**，搜尋結果另算輸入 token，出錯的那次不收費。`max_uses` 是**每個請求**的上限，超過時結果是 `max_uses_exceeded` 錯誤（HTTP 仍 200）。`allowed_domains` 與 `blocked_domains` 二選一，**自動含子網域**，組織在 Console 設了允許清單時請求的必須是它的子集否則 400。與自己的工具平行呼叫時 API 先不跑搜尋、回 `tool_use`，下一個請求才搜。（[Web search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)、[Server tools〈Domain filtering〉](https://platform.claude.com/docs/en/agents-and-tools/tool-use/server-tools)）
  - **改工具定義（名字、說明、參數）會讓整段 prompt 快取失效**（順序 tools → system → messages），所以 `max_uses` 每次請求固定，不照剩幾次調。（[Prompt caching〈What invalidates the cache〉](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)）
  - pydantic-ai-slim 2.62.0：`NativeTool` 可以給函式，每次模型呼叫前回 `WebSearchTool` 或 `None`；`usage.details['web_search_requests']` 只在大於 0 時有；`FunctionModel` 串流版的 usage 報不出網搜次數；`OpenAIChatModel` 送出歷史時略過伺服器端工具片段，同一段對話換接口不會壞。
  - Tavily `POST https://api.tavily.com/search`：`Authorization: Bearer <key>`；`basic` / `fast` / `ultra-fast` 1 credit、`advanced` 2 credit；`include_domains` 最多 300 個，**實測含子網域**；成功回 `results[]`（`title`、`url`、`content`、`score`）等，每頁 `content` 約 1,300–1,500 字；錯誤 body 是 `{"detail": {"error": "..."}}`：401 key 錯、400 參數錯、429 限流帶 `Retry-After`、432 / 433 額度；免費每月 1,000 credit。（[Search API](https://docs.tavily.com/api-reference/endpoint/search)、[Rate limits](https://docs.tavily.com/documentation/rate-limits)、[Credits](https://docs.tavily.com/documentation/api-credits)；實測錄在 `tests/fixtures/http/tavily/`，`scripts/experiments/tavily_search.py`）

### 20.26 助理的工具清單、推理與模型清單（2026-11-01 查證與實測，M5.5 規劃）

細節與時間線在 [`docs/research/assistant-feedback-2026-11-01.md`](assistant-feedback-2026-11-01.md)。

- **模型會誤報自己有什麼工具**（正式環境 `deepseek-flash`，0.4.1）：Tavily key 在該輪開始前 8 秒已存回，`open_turn` 每則訊息重讀設定、重建工具清單（臨時整合測試：填、清、再填時依序看得到、看不到、看得到），它仍連答兩輪「沒有」。送出的工具清單當時沒有記錄，所以這是推論，不是線上直接量到的。助理對工具的說法不能當事實：M5.5 票 15 起 `/status` 照設定說搜得到什麼，每次模型呼叫送出的工具名記在 `ai_calls.tools_json`、步驟頁看得到，instructions 也叫模型只看當下的工具清單。
- **DeepSeek 的 Anthropic 接口**：`thinking` 支援但忽略 `budget_tokens`；`output_config` 只支援 `effort`。（[Using the Anthropic API](https://api-docs.deepseek.com/guides/anthropic_api)）`deepseek-flash` 不送 `thinking` 時也會回推理文字（實測）。
- **DeepSeek 的推理程度**：只分 `low`、`high`、`max`，預設 `high`，思考模式預設開。`minimal`→`low`，`medium`、`xhigh`→`high`，`ultra`→`max`，所以設 `medium` 跟現在不送一樣。Anthropic 格式用 `output_config.effort`，開關是 `thinking.type`。（[Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode)）
- **pydantic-ai-slim 2.62.0 的推理**（實測 profile、讀 `models/__init__.py` 與 `models/anthropic/__init__.py`；請求本體 M5.5 票 17 錄下，見下一條）：
  - `AnthropicModel('deepseek-flash')`：`supports_thinking` 真、`anthropic_supports_effort` 假。統一的 `thinking='low'` 會變成 `budget_tokens`（DeepSeek 忽略），effort 不會送；`thinking=False` 在這個 profile 下省略 `thinking`（模型照樣思考）。所以要明寫 `anthropic_effort` 與 `anthropic_thinking`。
  - `AnthropicModel('claude-sonnet-5-5')`：`anthropic_supports_effort` 真，統一設定就夠。
  - `OpenAIChatModel` 配 `OpenAIProvider`：`deepseek-flash`、`gpt-4o-mini`、自訂名字的 `supports_thinking` 都是假，統一的 `thinking` 被靜靜拿掉，不會 400，但也沒有效果。`DeepSeekProvider` 才認 `deepseek-flash`，Berth 用的是 `OpenAIProvider`。
  - Vercel 串流與 `dump_messages` 都會帶 `reasoning` 片段。
- **Berth 送出的推理參數**（M5.5 票 17，2026-11-04；`chat_settings`，請求本體由 `tests/integration/test_ai_adapter.py::TestReasoning` 錄下並守著）：
  - Anthropic 接口、`deepseek-flash`（profile 沒有 `anthropic_supports_effort`）：低、中、高是 `output_config: {effort: low|medium|high}`、不帶 `thinking`；關是 `thinking: {type: disabled}`、不帶 `output_config`。同一個模型用統一的 `thinking` 只會送 `thinking: {type: enabled, budget_tokens: 2048|10000|16384}`，關則什麼都不送。
  - Anthropic 接口、`claude-sonnet-5-5`（有 `anthropic_supports_effort`）：統一設定，`thinking: {type: adaptive}` 加 `output_config.effort`；關是 `thinking: {type: between_tools}`（關不掉，pydantic-ai 換成最少的一種）。`claude-haiku-5-5` 關是 `disabled`。
  - OpenAI 接口：`gpt-5.5` 送 `reasoning_effort`（關是 `none`）；`deepseek-flash`、`gpt-4o-mini`、自訂名字四級都不帶參數，設定頁說這個模型的程度沒有效果（`GET /settings/ai/reasoning`）。
  - **真的 DeepSeek**（`scripts/experiments/reasoning_levels.py`，結果在 `.local/experiments/results/reasoning_levels/`）：Anthropic 接口上四級都 200；關時沒有推理文字、output 1 token，低、中、高都回推理文字。OpenAI 接口不帶參數，四級都照樣推理。題目太短，量不出低與高的差別。
  - **沒有 effort 的 Claude 不送**（code-review 追加，偏離票的字面「profile 沒有 `anthropic_supports_effort` 的明寫」）：pydantic-ai 只給 Opus 4.5 起、Sonnet 4.6 起、Haiku 5.5 這類 `anthropic_supports_effort`；`claude-sonnet-4-5`、`claude-haiku-4-5`、`claude-opus-4-1` 明寫 effort 會被官方拒，統一設定的中、高又是 `budget_tokens` 10000 / 16384，大過面板每次的 `max_tokens` 4096。所以 `claude-` 開頭又沒有 effort 的四級都不送（同加這一格之前），設定頁說沒有效果；不是 Claude 的相容端點（DeepSeek、GLM）照樣明寫（認不得的閘道「關」不送，見下一條），不收的 400 由停下的說明連到設定頁（`rejects_reasoning`：400 且 body 提到 `output_config`、`effort`、`thinking.type`、`budget_tokens`；只說 `thinking` 或 `reasoning_content` 的重播錯誤不算）。
  - **認不得的相容閘道「關」不送**（M5.5 票 17b，使用者定 2026-11-04）：Anthropic 接口上不是 Claude 的模型，只有主機是 `api.deepseek.com` 的「關」明寫 `thinking: {type: disabled}`（上面實測過）；其他主機（含轉送 DeepSeek 模型的閘道）關就什麼都不送，因為不收這兩個參數的閘道會 400，設定頁又沒有「不送」一級。低、中、高照送 `output_config.effort`，被拒時停下的說明與設定頁都說「選關就不送」。以主機認、不以模型名：收不收參數是端點的事。
  - Compaction 的摘要一律關：推理吃同一份 `SUMMARY_TOKENS`（2048）。
- **`web_search` 結果的 `encrypted_content`**：DeepSeek 的 Anthropic 接口每筆都帶，再加 `title`、`url`、`page_age`、`type`。一次 10 筆的 JSON 實測 22,628–41,654 字，幾乎都是它。Berth 在 API 層拿掉它再給瀏覽器（M5.5 票 03），存著的歷史照留給模型重播。
- **模型清單端點**（M5.5 票 02 實測 2026-11-04，`scripts/experiments/ai_models.py`，回應在 `tests/fixtures/http/ai_models/`）：
  - **DeepSeek 的 OpenAI 接口** `GET https://api.deepseek.com/models`（`Authorization: Bearer`）：200 `{object: "list", data: [...]}`，每筆 `id`、`object`、`owned_by`、`name`、`context_window`、`max_output_tokens`、`effort` 等；當時列 `deepseek-flash`、`deepseek-v4-pro`，沒有分頁。key 錯是 401 `{error: {message, type: "authentication_error", ...}}`，訊息裡的 key 已被服務遮成 `****`。（[Lists Models](https://api-docs.deepseek.com/api/list-models)）
  - **DeepSeek 的 Anthropic 接口不提供模型清單**：`{base}/v1/models` 帶對的 key，`x-api-key` 與 `Authorization: Bearer` 都是 404、空 body，不帶 `/v1` 也一樣；key 錯時先回 401。文件也沒寫這支（[Anthropic API](https://api-docs.deepseek.com/guides/anthropic_api)）。所以 Berth 沿用 `x-api-key`（同 SDK 與聊天），404、405、501 說成「這個端點不提供模型清單」、退回本機價目表（它認得 DeepSeek），401 / 403 才說 key 被拒。
  - **Anthropic 官方** `GET https://api.anthropic.com/v1/models`：**未實測**（沒有官方 key），照文件：`limit` 預設 20、最多 1,000，`has_more` 為真時帶 `after_id={last_id}` 取下一頁，回 `data`、`first_id`、`last_id`、`has_more`，新的在前；`anthropic-version` 必帶。文件把 `Authorization: Bearer` 列為主要、`x-api-key` 為仍支援的舊法。（[List Models](https://platform.claude.com/docs/en/api/models/list)）錯 key 回 401 `authentication_error` `invalid x-api-key` 是 2026-11-03 實際打到的。
  - **OpenAI 官方** `GET https://api.openai.com/v1/models`：**未實測**，照文件是 `{object: "list", data: [{id, object, created, owned_by}]}`，沒有分頁。（[List models](https://platform.openai.com/docs/api-reference/models/list)）
- **Open WebUI 的慣例**：連線填 URL 與 key，從 `/models` 自動偵測模型；服務不支援時才手動填模型 id。（[OpenAI-Compatible](https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-openai-compatible)）
