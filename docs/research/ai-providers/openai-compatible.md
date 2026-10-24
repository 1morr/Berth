# OpenAI 相容 API 與第三方端點事實查證

結論與兩種格式的對照在 [`../ai-providers.md`](../ai-providers.md)；這份是 OpenAI 相容這一側的逐條事實。respx 攔不到 `openai` SDK 的實測在 [`scripts/experiments/ai_sdk_mocking.py`](../../../scripts/experiments/ai_sdk_mocking.py)。

查證日期：2026-10-24。只記事實，不含建議或設計。

## 來源基準

| 簡稱 | 基準 URL | 取得方式 |
|---|---|---|
| PyPI-openai | https://pypi.org/pypi/openai/json 、 https://pypi.org/pypi/openai/3.37.0/json | 直接取 JSON；下載 wheel `openai-3.37.0-py3-none-any.whl`（https://files.pythonhosted.org/packages/56/73/c605f0cee1882e453a4b7fc2f17f4a42a7d4c1ed2304aff4b163ffade819/openai-3.37.0-py3-none-any.whl）解壓後讀原始碼 |
| SDK-src | 上述 wheel 內 `openai/*.py`（下稱 `openai/<檔>`） | 讀原始碼 |
| SDK-CHANGELOG | https://github.com/openai/openai-python/blob/main/CHANGELOG.md | raw 取得 |
| SDK-httpx2.md | https://github.com/openai/openai-python/blob/main/httpx2.md | raw 取得 |
| OAI-docs | https://developers.openai.com/api/docs/guides/<頁>（加 `.md` 取 Markdown） | curl |
| OR | https://openrouter.ai/docs/...（加 `.md`） | curl |
| vLLM-docs / vLLM-src | https://github.com/vllm-project/vllm （main 分支，PyPI 最新 0.32.0，2026-10-18，https://pypi.org/pypi/vllm/json） | raw 取得 |
| Ollama-docs / Ollama-src | https://github.com/ollama/ollama （main 分支；latest release v0.40.10，2026-10-23，`gh api repos/ollama/ollama/releases/latest`） | raw 取得 |
| DS | https://api-docs.deepseek.com/... | curl HTML 轉文字 |

vLLM 與 Ollama 的原始碼是 main 分支，不等於使用者實際部署的版本；查證時下載的原始碼與 wheel 不納入專案。

---

## 1. SDK 還是直接 HTTP

### 1.1 `openai` Python SDK

| 事實 | 來源 |
|---|---|
| 當前 stable 版本 `3.37.0`，發佈 2026-10-22T20:04:37（UTC）。前一版 3.36.1 為 2026-10-22。 | PyPI-openai |
| `Requires-Python >=3.10`；`Requires-Dist`：`anyio<5,>=4.10.0`、`httpx2<3,>=2.12.0`、`jiter<1,>=0.16.0`、`pydantic`（`>=1.10.13`，排除 2.0–2.3）、`sniffio`、`typing-extensions>=4.14`。 | PyPI-openai |
| **底層 HTTP 庫是 `httpx2`（pydantic 維護的 httpx 分支），不是 `httpx`。** 3.0.0（2026-08-12）的 BREAKING CHANGES：「HTTPX2 is now the default HTTP client, and `httpx` is no longer installed automatically. Applications using custom HTTPX clients, transports, or configuration objects must migrate to their HTTPX2 equivalents or use the temporary, runtime-only legacy HTTPX escape hatch.」 | SDK-CHANGELOG（3.0.0 一節） |
| `pip install openai` 不再帶入 `httpx`，也不再帶入 `certifi`；HTTPX2 預設用作業系統 trust store（`SSL_CERT_FILE` / `SSL_CERT_DIR` 在 `trust_env=True` 時生效）。 | SDK-httpx2.md「TLS certificates and trust stores」 |
| `AsyncOpenAI(base_url=..., api_key=...)`；未傳 `base_url` 時讀環境變數 `OPENAI_BASE_URL`，再退回 `https://api.openai.com/v1`。 | SDK-src `openai/_client.py`（約 L326–333） |
| `AsyncOpenAI(http_client=...)` 接受：`httpx2.AsyncClient` 實例，或（runtime 層面）已載入的舊 `httpx.AsyncClient` 實例；其他型別拋錯 "Invalid `http_client` argument; Expected an instance of `httpx.AsyncClient` or `httpx2.AsyncClient`"。 | SDK-src `openai/_base_client.py`（約 L1634–1672）；`openai/_httpx2.py` |
| 舊 `httpx` client 為「temporary escape hatch」：僅 runtime 支援、型別標註不接受（需 `cast(Any, httpx.AsyncClient())`）、「may be discontinued」；使用者需自行 `pip install httpx`。使用舊 client 時 request/response/exception 都是 `httpx.*` 家族。 | SDK-httpx2.md「Temporary escape hatch」 |
| SDK 提供 `DefaultHttpx2Client` / `DefaultAsyncHttpx2Client`（保留 SDK 預設 timeout、連線池、redirect）；舊名 `DefaultHttpxClient` / `DefaultAsyncHttpxClient` 仍存在但現在建出 httpx2 client。 | SDK-httpx2.md |
| 預設 client 設定：`DEFAULT_TIMEOUT = httpx2.Timeout(timeout=600, connect=5.0)`；`DEFAULT_CONNECTION_LIMITS = Limits(max_connections=1000, max_keepalive_connections=100)`；`follow_redirects=True`。 | SDK-src `openai/_constants.py`、`openai/_base_client.py` |
| 測試 mock 的官方說法：「Mocks must intercept HTTPX2 requests and return HTTPX2 responses」（範例用 `httpx2.MockTransport`）；「If your test suite uses RESPX, update to an HTTPX2-compatible RESPX version or fork. A RESPX version that patches only legacy HTTPX cannot intercept the SDK's default HTTPX2 client.」使用舊 httpx client 注入可讓既有 RESPX 設定繼續運作。 | SDK-httpx2.md「Request mocking and tests」 |
| RESPX 現況：PyPI 最新 `0.23.1`（2026-04-08），`Requires-Dist: httpx>=0.25.0`（未見 httpx2）。respx repo 有 open issue #316「User question: respx and the httpx forks」、#324「Allow fork response types (e.g. httpx2.Response) in return_value / side_effect」。第三方 `lundberg/pytest-httpx2`（描述「A pytest plugin for mocking out httpx2 using respx」）存在於 GitHub。 | https://pypi.org/pypi/respx/json ；https://github.com/lundberg/respx/issues/316 ；https://github.com/lundberg/respx/issues/324 |
| httpx2 PyPI 最新 `2.16.0`（2026-10-21）；`httpx` PyPI 最新仍是 `0.28.1`（2024-12-06）。httpx2 依賴 `httpcore2`、`anyio`、`truststore`。 | https://pypi.org/pypi/httpx2/json ；https://pypi.org/pypi/httpx/json |

### 1.2 串流 helper

| 事實 | 來源 |
|---|---|
| `client.chat.completions.stream(...)`（`AsyncCompletions.stream`）回傳 `AsyncChatCompletionStreamManager`，進入後得 `AsyncChatCompletionStream`；可 `async for` 取事件、`await stream.get_final_completion()` 取累積完成物件、`stream.current_completion_snapshot` 取快照。 | SDK-src `openai/lib/streaming/chat/_completions.py` |
| 事件包含 `tool_calls.function.arguments.delta`、`tool_calls.function.arguments.done`（帶 `index`）等；helper 以 `delta.tool_calls[].index` 累積到 snapshot 的 `message.tool_calls`。 | 同上（`_accumulate_chunk`、`_build_events`） |
| `ChatCompletionStreamState`（可獨立使用）：`handle_chunk(chunk)` 逐個餵 `ChatCompletionChunk`，`get_final_completion()` 取結果；即不需透過 SDK 的 HTTP 層也能用累積邏輯。 | 同上；`openai/lib/streaming/chat/__init__.py` 匯出 |
| `stream()` helper 將 `stream_options` 原樣傳入；原始碼中該 helper 與 `lib/streaming/chat/` 內未出現自動加 `include_usage`。 | SDK-src `openai/resources/chat/completions/completions.py`（`stream` 方法）；grep `include_usage` 在此二處無命中 |
| helper 的「自動解析 tool 參數」只對 `strict: true` 的 function tool 生效（`is_strict_chat_completion_tool_param`；非 strict 時拋錯 "`<name>` is not strict. Only `strict` function tools can be auto-parsed"，指 `chat.completions.parse` 路徑）。 | SDK-src `openai/lib/_parsing/_completions.py` |
| 串流原始事件 SDK 層：`Stream`/`AsyncStream` 遇 `data: [DONE]` 結束；若 SSE `data` JSON 為物件且含 `error` 欄位，拋 `openai.APIError(message=error.message 或 "An error occurred during streaming", body=data["error"])`。 | SDK-src `openai/_streaming.py`（約 L71、L95–106、L186、L215–226） |

### 1.3 例外階層與重試

| 事實 | 來源 |
|---|---|
| 階層：`OpenAIError` → `APIError`（`message`、`request`、`body`、`code`、`param`、`type`）→ `APIStatusError`（`response`、`status_code`、`request_id` 取自 `x-request-id`）→ `BadRequestError`(400) / `AuthenticationError`(401) / `PermissionDeniedError`(403) / `NotFoundError`(404) / `ConflictError`(409) / `UnprocessableEntityError`(422) / `RateLimitError`(429) / `InternalServerError`(>=500)；其他 4xx/5xx 為裸 `APIStatusError`。`APIConnectionError(APIError)` → `APITimeoutError`。另有 `APIResponseValidationError`、`LengthFinishReasonError`、`ContentFilterFinishReasonError`。 | SDK-src `openai/_exceptions.py`、`openai/_client.py`（`_make_status_error`） |
| `APIError` 的 `code/param/type` 取自 body 字典（SDK 先取 `body.get("error", body)`）。 | `openai/_exceptions.py`、`openai/_client.py` |
| 內建重試：`DEFAULT_MAX_RETRIES = 2`；`max_retries` 不可為 `None`、需為非負整數；`0` 表示停用。 | `openai/_constants.py`、`openai/_base_client.py`（`_validate_max_retries`） |
| 重試條件：連線錯誤／timeout（`continue` 重試後仍失敗拋 `APIConnectionError`／`APITimeoutError`）；狀態碼 408、409、429、>=500；`x-should-retry: true/false` 標頭優先於狀態碼判斷。 | `openai/_base_client.py`（`_should_retry`、`_request` 迴圈） |
| 等待時間：先讀 `retry-after-ms`（毫秒），再讀 `retry-after`（秒，或 HTTP date）；值需 `0 < x <= MAX_RETRY_AFTER_DELAY`（`2 * 60` = 120 秒）才採用；若 `retry-after` 超過 120 秒，`_should_retry` 直接回 False（不重試）。無有效標頭時用指數退避：`min(0.5 * 2^n, 8.0)` 秒再乘 `1 - 0.25*random()` 的 jitter。 | `openai/_base_client.py`（`_parse_retry_after_header`、`_calculate_retry_timeout`、`_should_retry`）；`openai/_constants.py`（`INITIAL_RETRY_DELAY=0.5`、`MAX_RETRY_DELAY=8.0`、`MAX_RETRY_AFTER_DELAY=120`） |
| SDK 官方說明：各官方 SDK 自動重試符合條件的 429 與 503，「Handling of `Retry-After`, especially long delays, varies by SDK」。 | OAI-docs `rate-limits.md` |

### 1.4 直接用 HTTP（SSE 格式）

| 事實 | 來源 |
|---|---|
| Chat Completions 串流為 `text/event-stream`，每個事件 `data: <JSON>\n\n`，結束事件 `data: [DONE]`；開啟 `include_usage` 時，`[DONE]` 前多一個 usage chunk。 | SDK-src `openai/types/chat/chat_completion_stream_options_param.py`（docstring：「an additional chunk will be streamed before the `data: [DONE]` message」）；SDK `_streaming.py` |
| `stream_options.include_obfuscation`：預設會在 delta 事件加 `obfuscation` 隨機字元欄位（側信道緩解），可設 `false` 省頻寬。 | 同 `chat_completion_stream_options_param.py` |
| 第三方會在 SSE 夾 comment 行：OpenRouter 會送 `: OPENROUTER PROCESSING`；DeepSeek 串流在排隊時持續送 `: keep-alive`（非串流則持續回傳空行）。 | OR `api_reference/streaming.md`；DS https://api-docs.deepseek.com/quick_start/rate_limit |
| DeepSeek Responses 串流：「there is no `data: [DONE]` message」，以 `response.completed / response.incomplete / response.failed` 事件結束。 | DS https://api-docs.deepseek.com/guides/responses_api |

---

## 2. Chat Completions 還是 Responses

### 2.1 OpenAI 官方定位

| 事實 | 來源 |
|---|---|
| 「The Responses API is our new API primitive, an evolution of Chat Completions…」；「**While Chat Completions remains supported, Responses is recommended for all new projects.**」 | OAI-docs `migrate-to-responses.md` |
| Responses 優勢（官方稱）：reasoning 模型表現較好（內部 eval SWE-bench +3%）、快取利用提升 40%–80%（內部測試）。 | 同上 |
| 「Starting with GPT-5.4, Chat Completions does not support tool calling with `reasoning_effort` values other than `none`.」 | 同上 |
| Chat Completions 的 function 定義為 externally tagged（`{"type":"function","function":{...}}`），Responses 為 internally tagged；Chat Completions 的 function 預設非 strict，Responses 省略 `strict` 時嘗試 strict 並在無法時退回非 strict。 | 同上；OAI-docs `function-calling.md` |
| Chat Completions 能力表與 Responses 對照（Function calling、Structured Outputs、Streaming 等）兩者皆有；Audio 在 Responses 標「Coming soon」。 | 同上 |
| Chat Completions 預設儲存（新帳號），Responses 預設儲存；皆可 `store: false` 停用。 | 同上 |

### 2.2 各端點支援（欄位 × 端點）

| 項目 | OpenAI | OpenRouter | vLLM | Ollama | DeepSeek |
|---|---|---|---|---|---|
| `/v1/chat/completions` | 支援（官方稱 remains supported） | 支援；主要端點 `https://openrouter.ai/api/v1/chat/completions`，回應 schema 「normalizes … to comply with the OpenAI Chat API」 | 支援（需模型有 chat template） | 支援；`tools` 勾選、`tool_choice` 未勾選 | 支援（base_url `https://api.deepseek.com`） |
| `/v1/responses` | 官方建議 | 支援，**stateless only**：`store: true` 或非 null `previous_response_id` 回 400；文件未標 beta | 支援（`/v1/responses` 及 get/cancel）；僅文字生成模型 | 支援，v0.13.3 加入；**只支援 non-stateful**（無 `previous_response_id`、`conversation`）；Tools 勾選；文件列出的欄位不含 `tool_choice` | 支援（Models & Pricing 表 Responses API ✓；guide 標明「To meet the demand for Codex」） |
| 其他格式 | — | 另有 Anthropic Messages 格式 | Anthropic、Cohere 入口（原始碼目錄 `vllm/entrypoints/anthropic`、`cohere`） | 原生 `/api/chat` | Anthropic 格式（`https://api.deepseek.com/anthropic`） |
| 來源 | OAI-docs `migrate-to-responses.md` | OR `api_reference/overview.md`、`api_reference/responses/overview.md` | vLLM-docs https://github.com/vllm-project/vllm/blob/main/docs/serving/online_serving/openai_compatible_server.md | Ollama-docs https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx | DS https://api-docs.deepseek.com/quick_start/pricing 、 https://api-docs.deepseek.com/guides/responses_api |

補充：
- DeepSeek 工具呼叫指南明寫：Chat Completion API 不支援「在對話中途插入非模型產生的 tool call」；Anthropic API 與 Responses API 支援。（DS https://api-docs.deepseek.com/guides/tool_calls）
- Ollama 雲端直連 API：「does not support stateful Responses, built-in web search through `/v1/responses`, or custom/freeform tool-call replay」。（Ollama-docs `openai-compatibility.mdx`）
- vLLM 文件對 Responses API 未標 beta/experimental；對 Chat Completions 的備註含 `user` 參數被忽略。

---

## 3. tool calling 與串流（以 Chat Completions 為主）

### 3.1 OpenAI 規格

| 項目 | 事實 | 來源 |
|---|---|---|
| `tools` | `[{"type":"function","function":{"name","description","parameters"(JSON Schema),"strict"}}]`；SDK 型別 `ChatCompletionToolUnionParam` 亦含 custom tools。 | SDK-src `openai/types/chat/completion_create_params.py`、`openai/types/shared_params/function_definition.py` |
| `strict` | 「Whether to enable strict schema adherence … Only a subset of JSON Schema is supported when `strict` is `true`」。Strict 要求每個物件 `additionalProperties: false`、`properties` 全列入 `required`（可選欄位用 `null` 型別）；`strict:true` 而 schema 不合時請求被拒。Chat Completions 省略 `strict` 時為非 strict。 | 同上；OAI-docs `function-calling.md` |
| `tool_choice` | `none` / `auto` / `required`，或 `{"type":"function","function":{"name":"..."}}`（強制指定）；另有 allowed-tools 與 custom 變體。無 tools 時預設 `none`，有 tools 時預設 `auto`。 | SDK-src `completion_create_params.py`、`chat_completion_tool_choice_option_param.py` |
| `parallel_tool_calls` | bool；官方：「The model may choose to call multiple functions in a single turn. You can prevent this by setting `parallel_tool_calls` to `false`, which ensures exactly zero or one tool is called.」 | SDK-src；OAI-docs `function-calling.md` |
| 非串流回應 | `choices[].message.tool_calls[]`：`id`(str)、`type: "function"`、`function.name`、`function.arguments`（**JSON 字串**）。`arguments` docstring：「the model does not always generate valid JSON, and may hallucinate parameters not defined by your function schema. Validate the arguments in your code…」 | SDK-src `openai/types/chat/chat_completion_message_function_tool_call.py` |
| `finish_reason` | 非串流：`stop`、`length`、`tool_calls`、`content_filter`、`function_call`（deprecated）；串流 chunk 的 `finish_reason` 為 Optional（中途 null）。意義：`stop` 自然結束或遇 stop 序列；`length` 達 `max_tokens`；`content_filter` 內容被過濾；`tool_calls` 模型呼叫工具。 | SDK-src `chat_completion.py`、`chat_completion_chunk.py` |
| 串流 delta | `choices[].delta.tool_calls[]`：`ChoiceDeltaToolCall{index:int, id?:str, type?:"function", function?:{name?:str, arguments?:str}}`；`index` 為必填，`id`/`type`/`function.name` 為 Optional。 | SDK-src `chat_completion_chunk.py`（L76–97） |
| 串流拼接（SDK 行為） | 以 `index` 對應 `tool_calls` 陣列位置；`arguments` 片段逐段字串串接；`function.name`/`id` 取首次出現值。 | SDK-src `lib/streaming/chat/_completions.py`（`_accumulate_chunk`） |
| 送回 tool result | 新增訊息 `{"role":"tool","tool_call_id":"<id>","content": <str 或 [text parts]>}`（`tool_call_id`、`content`、`role` 皆 Required）；前一則 assistant 訊息需含 `tool_calls`（`ChatCompletionAssistantMessageParam.tool_calls`）。每次請求都要再送 `tools`（OpenRouter 文件亦強調此點）。 | SDK-src `chat_completion_tool_message_param.py`、`chat_completion_assistant_message_param.py`；OR `guides/features/tool-calling.md` |

### 3.2 Responses 差異（簡述）

| 項目 | 事實 | 來源 |
|---|---|---|
| 項目型別 | 輸出為 typed items：`function_call`（含 `call_id`、`name`、`arguments`）；結果以 `function_call_output` item 送回。 | OAI-docs `migrate-to-responses.md`、`function-calling.md` |
| 串流事件 | `response.output_item.added`（含 `output_index`、`item`）、`response.function_call_arguments.delta`（`item_id`、`output_index`、`delta`）、`response.function_call_arguments.done`、`response.output_item.done`。以 `output_index` 分組。 | OAI-docs `function-calling.md`（Streaming 一節） |
| `parallel_tool_calls` | 同 Chat：設 `false` 保證 0 或 1 個工具。 | 同上 |

### 3.3 第三方差異

| 項目 | OpenRouter | vLLM | Ollama | DeepSeek |
|---|---|---|---|---|
| `tools` 格式 | 同 OpenAI（`type: function`）；每次請求都要帶 `tools` | 同 OpenAI | 同 OpenAI；原生 `/api/chat` 的 tool 訊息用 `tool_name`，OpenAI 端點訊息型別含 `tool_call_id`、`name` | 同 OpenAI；僅支援 function |
| `strict` | 文件未逐項查；Auto Exacto 說明以 JSON Schema Draft 7 驗證 `tools[].function.parameters` | `strict: true` 時（或 server `--tool-strict-level`）依 parser 附 structural tag 約束；`VLLM_ENFORCE_STRICT_TOOL_CALLING` 預設 `true` | 文件未列 `strict` | Beta：base_url 需 `https://api.deepseek.com/beta`，且 tools 內所有 function 設 `strict: true`；不合 schema 回錯誤 |
| `tool_choice` | 文件列 `auto`、`none`、指定 function（第 3 項 `required` 在 tool-calling 頁未列） | `auto`、`none`、`required`（>= 0.8.3）、指定 function（走 structured outputs 後端，首次有數秒延遲） | **未支援**（Ollama-docs `/v1/chat/completions` 欄位表 `[ ] tool_choice`） | `none`、`auto`、`required`、指定 function |
| `parallel_tool_calls` | 「default is true for most models」；`false` 時一次只請求一個 | 支援；`true`（預設）允許多個，`false` 保證 0 或 1 個；備註：不保證一定產生多個 | 欄位表未列；文件有「Parallel tool calling」一節（原生 API） | DeepSeek chat completion 參考頁全文搜尋 `parallel` 無命中（未列） |
| 一次給完整 arguments | 未查到文件明述 | 未查到文件明述（視 parser） | **是（依原始碼）**：`ToToolCalls` 將已解析的 arguments 物件整個 `json.Marshal` 成字串放進單一 `tool_calls` chunk，無分片 | 未查到文件明述 |
| `id` | 未查到 | `ToolParser` 以 `_make_tool_call_id(name)` 產生（`vllm/parser/abstract_parser.py`） | 原始碼 `toolCallId()` 產生 `"call_" + 小寫隨機字串`（`server/routes.go` 約 L2858、L3370、L3399）；`index` 取 `Function.Index` | 未查到 |
| 其他 | `finish_reason` 正規化為 `tool_calls / stop / length / content_filter / error`，原值在 `native_finish_reason` | 工具呼叫需 server 端開 `--enable-auto-tool-choice` 與 `--tool-call-parser`（見第 8 節） | 串流需累積 `thinking`/`content`/`tool_calls` 並完整帶回下一輪（官方文件） | 思考模式 + tools：前幾輪的 `reasoning_content` 需回傳（見 3.4） |

### 3.4 DeepSeek 思考模式與工具

| 事實 | 來源 |
|---|---|
| 「From DeepSeek-V3.2, the API supports tool use in the thinking mode.」 | DS https://api-docs.deepseek.com/guides/tool_calls |
| 思考模式的 CoT 以 `reasoning_content` 回傳（與 `content` 同層）；「If the request carries the `tools` parameter: the `reasoning_content` of all previous turns should be passed back to the API and will be concatenated into the context.」無 tools 時回傳會被忽略。 | DS https://api-docs.deepseek.com/guides/thinking_mode |
| 以 `extra_body={"thinking":{"type":"disabled"}}` 關閉思考；`reasoning_effort`、`thinking.type: enabled` 控制思考。 | DS tool_calls / thinking_mode 範例 |
| DeepSeek `finish_reason` 值：`stop`、`length`、`content_filter`、`tool_calls`、`insufficient_system_resource`、`aborted`。 | DS https://api-docs.deepseek.com/api/create-chat-completion |

---

## 4. 列模型端點

| 端點 | 路徑 | 回應形狀 | 來源 |
|---|---|---|---|
| OpenAI | `GET /v1/models` | `{"object":"list","data":[{id, created(int), object:"model", owned_by, shutdown_date?}]}`；**無能力欄位**。 | SDK-src `openai/types/model.py` |
| OpenRouter | `GET https://openrouter.ai/api/v1/models` | `data[]` 每項 required 欄位：`id`、`canonical_slug`、`name`、`created`、`pricing`、`context_length`(int/null)、`architecture`、`top_provider`、`per_request_limits`、`supported_parameters`、`default_parameters`、`supported_voices`、`links`。`pricing`（PublicPricing）含 `prompt`、`completion`、`request`、`image`、`input_cache_read`、`input_cache_write`、`internal_reasoning`、`web_search` 等（USD per token，字串）。`supported_parameters` 的 enum 含 `tools`、`tool_choice`、`parallel_tool_calls`、`response_format`、`structured_outputs`、`reasoning`、`max_tokens` 等。查詢參數 `output_modalities`（預設只回文字輸出模型；`all` 含全部）、`supported_parameters` 篩選。另有 `/api/v1/models/{author}/{slug}` 取單一模型。 | OR `docs/api/api-reference/models/list-all-models-and-their-properties.md`、`guides/overview/models.md` |
| vLLM | `GET /v1/models` | `{"object":"list","data":[{id, object:"model", created, owned_by:"vllm", root, parent, max_model_len, permission[]}]}`；無工具能力欄位。 | vLLM-src `vllm/entrypoints/serve/engine/protocol.py`（`ModelCard`、`ModelList`） |
| Ollama（OpenAI 相容） | `GET /v1/models`、`GET /v1/models/{model}` | 同 OpenAI 形狀；`created` 對應「last modified」，`owned_by` 對應 ollama 使用者名（預設 `"library"`）。 | Ollama-docs `openai-compatibility.mdx` |
| Ollama（原生） | `GET /api/tags` | `{"models":[{name, model, remote_model?, remote_host?, modified_at, size, digest, details{format, family, families, parameter_size, quantization_level}}]}`；**無 capabilities**。 | Ollama-docs `docs/openapi.yaml`（`ListResponse`、`ModelSummary`） |
| Ollama（原生） | `POST /api/show` | 回應含 `capabilities: string[]`（例 `["completion","thinking","vision"]`）、`model_info`、`parameters`、`template` 等。原始碼 capability 常數：`completion`、`tools`、`insert`、`vision`、`embedding`、`thinking`、`image`、`audio`、`decision`、`speech`。 | Ollama-docs `docs/openapi.yaml`（`/api/show`）；Ollama-src `types/model/capability.go` |
| DeepSeek | `GET https://api.deepseek.com/models` | `{"object":"list","data":[{id, object:"model", owned_by, name?, context_window?, max_output_tokens?, input_modalities?, output_modalities?, effort{supported_levels, default_level?}, api_capabilities{anthropic_messages{system_prompt_update}}}]}`；欄位表中**無 tools / function calling 能力欄位**。 | DS https://api-docs.deepseek.com/api/list-models |

---

## 5. prompt caching

### 5.1 OpenAI

| 事實 | 來源 |
|---|---|
| 預設對支援的模型自動啟用；前提是請求共享相同 **prefix**（開頭 token 完全一致才能命中）。 | OAI-docs `prompt-caching.md` |
| 最小可快取長度：GPT-5.6 及之後 **1,024 visible input tokens**（hidden 系統內容不計）；較早模型「Varies by request settings」（受 tools、images、output schema、reasoning effort、verbosity 影響）。 | 同上（Summary of model differences） |
| 較早模型的 `cached_tokens` 回報「excludes hidden tokens and rounds down to a multiple of 128」；GPT-5.6 及之後回報精確的可快取邊界。 | 同上 |
| 快取放置：GPT-5.6+ 於最新符合條件訊息末端放 implicit breakpoint（可加 explicit `prompt_cache_breakpoint`，每請求最多寫 4 個）；GPT-5.5 以固定 2,048-token 間隔；其他較早模型為模型相關間隔。 | 同上；SDK-src `completion_create_params.py` |
| 路由：依機器負載、前綴 hash（含 tool 定義）、`prompt_cache_key`；每機器約 15 req/min 以上可能溢出路由。`prompt_cache_key`：GPT-5.6 前用於優化命中率；GPT-5.6+ 僅用於分開快取計帳／防 cache probing。SDK 型別：`prompt_cache_key: Optional[str]`，「Replaces the `user` field」。 | 同上；SDK-src |
| 保留時間：GPT-5.6+ 用 `prompt_cache_options.ttl`（`"30m"` 預設，Responses 另有 `"12h"`；Chat Completions SDK docstring：`ttl` 目前僅 `30m`）；較早模型用 `prompt_cache_retention`（`in_memory` 約 5–10 分鐘不活動、最長一小時；`24h` 最長 24 小時；SDK 標示 `prompt_cache_retention` 為 Deprecated）。預設：未啟用 ZDR 的組織 `24h`，ZDR 組織 `in_memory`（對支援兩者的模型）。GPT-5.5 與之後僅支援 `24h`。 | 同上；SDK-src `completion_create_params.py` |
| 計價：GPT-5.6+ 快取讀取 0.1× 未快取輸入；快取寫入 `30m` 為 1.25×（Responses `12h` 為 2.5×）；GPT-5.5 及較早「No additional cache-write charge」。 | OAI-docs `prompt-caching.md` |
| 無法手動清除快取。 | 同上 FAQ |
| 快取不跨組織、不跨區域處理邊界。 | 同上 |

### 5.2 第三方

| 端點 | 事實 | 來源 |
|---|---|---|
| OpenRouter | 「Most providers automatically enable prompt caching」，Alibaba 與 Anthropic 需 per-message `cache_control`。Provider sticky routing：快取請求後同模型後續請求黏到同一 provider（僅在快取讀取價較低時啟用；閒置 10 分鐘過期；指定 `provider.order` 時不啟用）；可用 `session_id`（body 或 `x-session-id` 標頭，<=256 字元）當黏著鍵，缺時回退到 OpenAI 式 `prompt_cache_key`。 | OR `guides/best-practices/prompt-caching.md` |
| OpenRouter（OpenAI 上游） | 自動；最小 1024 tokens；GPT-5.6+ 寫入 1.25×；支援 `prompt_cache_breakpoint`／`prompt_cache_options`（僅 GPT-5.6+）；可逐請求關閉快取。 | 同上 |
| OpenRouter（Anthropic 上游） | 兩種：頂層 `cache_control`（自動快取，Anthropic/Vertex/Azure/Bedrock provider）或 content block 上的 `cache_control: {"type":"ephemeral"}`（最多 4 個 explicit breakpoint）；預設 TTL 5 分鐘，`"ttl":"1h"` 為 1 小時；各模型有最小可快取長度。 | 同上 |
| OpenRouter（其他） | Gemini 2.5+ implicit caching，另可用 `cache_control`（只採最後一個 breakpoint）；DeepSeek「automated and does not require any additional configuration」；Grok、Moonshot、Groq、Z.AI 各有小節。 | 同上 |
| vLLM | Automatic Prefix Caching（APC）；設定 `CacheConfig.enable_prefix_caching` 預設 `True`；hash 演算法預設 `sha256`。快取 token 數僅在 server 加旗標 `--enable-prompt-tokens-details` 時才回報於 `usage.prompt_tokens_details`。 | vLLM-docs `docs/features/automatic_prefix_caching.md`；vLLM-src `vllm/config/cache.py`、`vllm/entrypoints/common/cli_args.py` |
| Ollama | OpenAI 相容端點的 usage 在引擎提供 `PromptEvalCachedCount` 時才附 `prompt_tokens_details.cached_tokens`（指標為可選指標）；文件未見 prompt caching 專章。 | Ollama-src `openai/openai.go`（`ToUsage`） |
| DeepSeek | 「Context Caching on Disk … enabled by default for all users」；無需改程式；命中須完整匹配已持久化的 prefix unit（請求輸入末端、模型輸出末端、偵測到的共同前綴、固定 token 間隔皆會產生 unit）；「best-effort」，不保證 100% 命中；建構需數秒；未使用後通常幾小時到幾天清除。`user_id` 參數可隔離 KVCache。 | DS https://api-docs.deepseek.com/guides/kv_cache ；https://api-docs.deepseek.com/quick_start/rate_limit |

---

## 6. `usage` 欄位

### 6.1 OpenAI Chat Completions

| 欄位 | 事實 | 來源 |
|---|---|---|
| `prompt_tokens`、`completion_tokens`、`total_tokens` | int，皆 required。 | SDK-src `openai/types/completion_usage.py` |
| `prompt_tokens_details` | Optional：`cached_tokens`、`cache_write_tokens`（docstring：「The unadjusted number of prompt tokens written to cache」）、`audio_tokens`、`image_tokens`、`text_tokens`。 | 同上 |
| `completion_tokens_details` | Optional：`reasoning_tokens`、`accepted_prediction_tokens`、`rejected_prediction_tokens`、`audio_tokens`、`text_tokens`。 | 同上 |
| 快取寫入欄位 | **有**：`prompt_tokens_details.cache_write_tokens`（SDK 3.37.0 型別）。Responses 對應 `input_tokens_details.cache_write_tokens`，並有 `cache_write_tokens_details.ttl_30m_tokens / ttl_12h_tokens`。caching guide：GPT-5.5 及較早沒有額外寫入收費。 | 同上；OAI-docs `prompt-caching.md` |
| `prompt_tokens` 是否含 cached | caching guide 對 Responses 的計價式為 `ordinary_input_tokens = input_tokens - cached_tokens - cache_write_tokens`，即 input 總數包含 cached 與 write 部分，且 `cached_tokens` 「excludes tokens charged as writes」。guide 未對 Chat Completions 的 `prompt_tokens` 另作逐字說明。 | OAI-docs `prompt-caching.md` |
| 串流取 usage | 請求設 `stream_options: {"include_usage": true}`：在 `data: [DONE]` 前多一個 chunk，其 `usage` 為整體統計、`choices` 永遠是空陣列；其餘 chunk 也帶 `usage` 但為 `null`；「If the stream is interrupted, you may not receive the final usage chunk」。chunk 的 `choices` docstring：「Can also be empty for the last chunk if you set `stream_options: {"include_usage": true}`」。 | SDK-src `chat_completion_stream_options_param.py`、`chat_completion_chunk.py` |

### 6.2 第三方（欄位 × 端點）

| 欄位／行為 | OpenAI | OpenRouter | vLLM | Ollama | DeepSeek |
|---|---|---|---|---|---|
| 輸入 tokens | `prompt_tokens` | `prompt_tokens`（「Including images, input audio, and tools if any」） | `prompt_tokens`（原始碼 = `len(prompt_token_ids)`，即全部 prompt tokens） | `prompt_tokens`（= `PromptEvalCount`） | `prompt_tokens`，文件：「It equals `prompt_cache_hit_tokens` + `prompt_cache_miss_tokens`」 |
| 輸出 tokens | `completion_tokens` | `completion_tokens` | `completion_tokens` | `completion_tokens`（= `EvalCount`） | `completion_tokens` |
| 總計 | `total_tokens` | `total_tokens`（兩者之和） | `total_tokens` | `total_tokens`（兩者之和） | `total_tokens` |
| 快取讀取 | `prompt_tokens_details.cached_tokens` | `prompt_tokens_details.cached_tokens`（「Tokens cached by the endpoint」） | `prompt_tokens_details.cached_tokens`；**僅 server 開 `--enable-prompt-tokens-details` 才有** | `prompt_tokens_details.cached_tokens`，僅在引擎回報 `PromptEvalCachedCount` 時才有 | `prompt_cache_hit_tokens`（頂層 usage 欄位）；另有 `prompt_tokens_details.cached_tokens`，「Same as `prompt_cache_hit_tokens`」 |
| 快取未命中 | 無專屬欄位 | 無專屬欄位 | 無專屬欄位 | 無 | `prompt_cache_miss_tokens` |
| 快取寫入 | `prompt_tokens_details.cache_write_tokens` | `prompt_tokens_details.cache_write_tokens`（「only returned for models with explicit caching and cache write pricing」） | `prompt_tokens_details.created_cache_tokens`（原始碼 `PromptTokenUsageInfo`；需同旗標） | 未見 | 未見 |
| 推理 tokens | `completion_tokens_details.reasoning_tokens` | `completion_tokens_details.reasoning_tokens` | `completion_tokens_details`（原始碼有 `_make_completion_tokens_details(reasoning_tokens…)`） | 未見 | `completion_tokens_details.reasoning_tokens` |
| 花費 | 無 | `usage.cost`、`usage.cost_details.upstream_inference_cost`、`is_byok` | 無 | 無 | 無 |
| 串流是否要 `include_usage` | 要 | **不用**：文件稱 `usage: {include:true}` 與 `stream_options.include_usage` 「are deprecated and have no effect. Full usage details are now always included」；usage 在 `[DONE]` 前最後一個 chunk，**該 chunk 的 `choices` 非空**（一個 content 為空、重複 `finish_reason` 的 choice，「Unlike OpenAI's spec」） | 要：`stream_options.include_usage`（`should_include_usage`）；另有 `continuous_usage_stats`、server 旗標 `enable_force_include_usage` 強制附帶 | 要：`stream_options.include_usage`；開啟時結束 chunk 帶 `usage`，該 chunk `choices` 為空陣列；非串流回應固定含 usage | 要：`stream_options.include_usage`，「all chunks in the stream will include a `usage` field, whose value is `null` on every chunk except the last one」；`stream_options` 未搭配 `stream:true` 回 400 |
| 來源 | SDK-src `completion_usage.py` | OR `cookbook/administration/usage-accounting.md`、`api_reference/overview.md`、`api_reference/streaming.md` | vLLM-src `chat_completion/serving.py`、`engine/protocol.py`、`api_utils.py`、`cli_args.py` | Ollama-src `openai/openai.go`、`middleware/openai.go`；Ollama-docs `openai-compatibility.mdx`（`stream_options.include_usage` 勾選） | DS https://api-docs.deepseek.com/api/create-chat-completion |

---

## 7. 錯誤

### 7.1 OpenAI

| 項目 | 事實 | 來源 |
|---|---|---|
| 錯誤碼表（官方「Error codes」） | 400 Invalid `service_tier`；401 Invalid Authentication／Incorrect API key／必須是組織成員／IP not authorized；403 Country, region, or territory not supported；429（多種，見下）；500 server error；503 Model temporarily overloaded。官方表**未單列 404**；SDK 對 404 映射為 `NotFoundError`。 | OAI-docs `error-codes.md`；SDK-src `_client.py` |
| 429 子類（以 `error.code` 區分） | `credit_balance_exhausted`（預付額度用盡）、`rate_limit_error` 類 `Rate limit reached for requests`、`rate_limit_error` + `slow_down`（速率爬升過快，即使未超 RPM/TPM 也可能發生）、`organization_spend_limit_exceeded`、`project_spend_limit_exceeded`、`organization_usage_limit_exceeded`。官方：「For billing-related errors, inspect `error.code` … The broader `error.type` can still be `insufficient_quota`.」「Retrying billing, spend, or quota errors won't restore API access.」 | OAI-docs `error-codes.md` |
| 503 | `type: service_unavailable_error`、`code: server_is_overloaded`；遵循 `Retry-After`。 | 同上 |
| 錯誤 body | SDK 讀取 body（或 body.error）的 `message`、`type`、`param`、`code`；`APIStatusError.request_id` 取自 `x-request-id` 標頭。 | SDK-src `_exceptions.py` |
| 標頭 | `Retry-After`（秒，429 暫時性 rate limit 與 503 暫時過載時可能出現；不代表 quota/billing 已恢復）；`x-ratelimit-limit-requests`、`x-ratelimit-limit-tokens`、`x-ratelimit-remaining-requests`、`x-ratelimit-remaining-tokens`、`x-ratelimit-reset-requests`（例 `1s`）、`x-ratelimit-reset-tokens`（例 `6m0s`）；專案層另有 `x-ratelimit-{limit,remaining,reset}-project-tokens`。缺 `Retry-After` 時官方建議指數退避加 jitter。 | OAI-docs `rate-limits.md` |
| 串流中途出錯 | 官方文件未見 Chat Completions 串流中途錯誤格式的專節；SDK 將 SSE `data` JSON 含 `error` 欄位的事件轉為 `APIError`（見 1.2）。 | SDK-src `_streaming.py` |

### 7.2 第三方

| 項目 | OpenRouter | vLLM | Ollama | DeepSeek |
|---|---|---|---|---|
| body 形狀 | `{"error":{"code":<int>,"message":str,"metadata"?:{...}}}`；HTTP 狀態與 `error.code` 相同。Provider 錯誤另帶 `metadata.error_type`（例 `rate_limit_exceeded`）與 `metadata.provider_code`；500 時訊息被遮蔽為通用字串。 | `{"error":{"message":str,"type":str,"param":str|null,"code":<int>}}`（`ErrorInfo`；`type` 預設 `"BadRequestError"`，`code` 為整數 HTTP 狀態） | OpenAI 相容端點：`{"error":{"message","type","param","code"}}`；`type`：400 → `invalid_request_error`、404 → `not_found_error`、其他 → `api_error`；`param`/`code` 為 null。原生端點為 `{"error": "<字串>"}` | 未查到 body 形狀（錯誤碼頁僅列碼與原因） |
| 狀態碼 | 400 Bad Request；401 憑證無效；**402 額度不足**；403（權限、guardrail 擋下、moderation、預算上限）；**408** timeout；429；**502** 模型離線或收到無效回應；**503** 無符合路由要求的 provider。 | 400（含 tool_choice 驗證錯誤）；其他見原始碼 | 400（含「does not support ...」）、404（`model "x" not found, try pulling it first`）、499（`request canceled`）、503（`ErrMaxQueue`）、500（其餘） | 400 Invalid Format；401 Authentication Fails；**402 Insufficient Balance**；**422 Invalid Parameters**；429 Rate Limit Reached（速度過快或超過並行／QPS 上限）；500；503 Server Overloaded |
| `Retry-After` | 429、503，及 402 且 `metadata.limit_source = openrouter_in_flight_budget` 時可能附；各官方 SDK 自動退避，但不重試 402 | 未查到 | 未查到 | 未查到 |
| 串流中途錯誤 | 先送 HTTP 200；之後的失敗以 SSE `data:` 事件送出，形狀為含頂層 `error`、`choices:[{index:0, delta:{content:""}, finish_reason:"error"}]` 的 `chat.completion.chunk`（含 `provider`、`error.metadata.error_type`）；送出後串流終止；非串流同理，可能是 200 加只有 `error` 的 JSON。pre-stream 錯誤（key 無效、參數錯）為一般 JSON 與 4xx/5xx。 | 串流生成器例外時 `data: <create_streaming_error_response>`，最後仍送 `data: [DONE]` | 未查到 | 未查到；僅知排隊時串流送 `: keep-alive`，10 分鐘未開始推論則伺服器關閉連線 |
| 其他 | 零 token 回應可能是 200（`finish_reason:"length"`、reasoning 用盡 `max_tokens`）；「Check the body for an `error` field even on a `200`」 | `tools: []` 空陣列回 400「`tools` must not be an empty array」 | — | `finish_reason` 可為 `insufficient_system_resource`、`aborted` |
| 來源 | OR `api_reference/errors-and-debugging.md` | vLLM-src `serve/engine/protocol.py`、`renderers/online_renderer.py`、`chat_completion/serving.py`、`chat_completion/protocol.py` | Ollama-src `openai/openai.go`（`NewError`）、`server/routes.go`（`scheduleError`） | DS https://api-docs.deepseek.com/quick_start/error_codes |

---

## 8. 怎麼知道端點與模型支不支援工具呼叫

### 8.1 逐家事實

| 端點 | 能力欄位 | 不支援時的行為 | 來源 |
|---|---|---|---|
| OpenAI | `GET /v1/models` 無能力欄位（`id/created/object/owned_by/shutdown_date`）。 | 本次未查到官方「不支援 tools 時」的錯誤字串。 | SDK-src `types/model.py` |
| OpenRouter | `GET /api/v1/models` 每個模型有 `supported_parameters`，值域含 `tools`、`tool_choice`、`parallel_tool_calls`、`response_format`、`structured_outputs`。網頁篩選：`https://openrouter.ai/models?supported_parameters=tools`。路由：`provider.require_parameters: true` 時，不支援請求中所有參數的 provider 不會被路由；預設（`false`）時不支援的 provider 仍可能收到請求並「ignore unknown parameters」；但 `tools`、`response_format`、`verbosity` 三者是軟偏好——若該模型有些 provider 支援有些不支援，只路由到支援者；若全都不支援，仍路由並**忽略該參數**。Auto Exacto 對含 tools 的請求自動依吞吐、工具呼叫成功率（以 JSON Schema Draft 7 驗證 `arguments`）與基準分數重排 provider。 | OR `docs/api/api-reference/models/list-all-models-and-their-properties.md`、`guides/features/tool-calling.md`、`guides/routing/provider-selection.md`、`guides/routing/auto-exacto.md` |
| vLLM | `/v1/models` 無工具能力欄位。能力由**啟動旗標**決定：`--enable-auto-tool-choice`（「mandatory」）與 `--tool-call-parser <名稱>`（必選 parser；可用 `--tool-parser-plugin` 註冊自訂）；可選 `--chat-template`。 | `tool_choice: "auto"` 且 server 無 tool parser 且未啟用 auto tools：**HTTP 400**，`BadRequestError`，訊息 `"auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set`；`required` 或指定 function 而無 parser：400，訊息 `tool_choice="required" requires --tool-call-parser to be set`（指定時為 `tool_choice=function "<name>" requires --tool-call-parser to be set`）。`tools: []` 回 400。`required`／指定 function 在 vLLM 走 structured outputs（0.8.3+，預設啟用，「will work with any supported model」）；`auto` 才依賴 parser。若請求不帶 `tool_choice`（None）而 server 未啟用 auto tools，`tool_parser` 為 None，解析函式直接回傳原 content（工具呼叫以文字出現，不報錯）。 | vLLM-docs `docs/features/tool_calling.md`；vLLM-src `vllm/renderers/online_renderer.py`（L260–282）、`vllm/parser/abstract_parser.py`（L395–420）、`vllm/parser/parser_manager.py`、`vllm/entrypoints/openai/chat_completion/protocol.py`（L970–1010） |
| Ollama | 原生 `POST /api/show` 回 `capabilities`，含 `tools` 表示模型有工具能力；`/api/tags`、`/v1/models` 無此欄位。文件亦指向 `https://ollama.com/search?c=tool` 列支援工具的模型。 | 帶 `tools` 的請求，伺服器要求 `completion` + `tools` 能力；模型缺 `tools` 能力時 `CheckCapabilities` 回錯，訊息為 `"<模型名> does not support tools"`（`fmt.Errorf("%s %w", m.Name, err)`，`errCapabilities = "does not support"`），`scheduleError` 映射為 **HTTP 400**；OpenAI 端點包成 `{"error":{"message":"…does not support tools","type":"invalid_request_error","param":null,"code":null}}`。`/v1/chat/completions` 欄位表未支援 `tool_choice`。 | Ollama-src `server/routes.go`（L3183–3185、L3215、L3616）、`server/images.go`（`CheckCapabilities`）、`types/model/capability.go`；Ollama-docs `openai-compatibility.mdx`、`api.md`（L523） |
| DeepSeek | `GET /models` 欄位表無工具能力欄位。Models & Pricing 表（2026-10-24 取得）：`deepseek-flash`（顯示名 DeepSeek-V4.1-Flash-1017）與 `deepseek-v4-pro`（DeepSeek-V4-Pro-0813），兩者 Tool Calls ✓、Json Output ✓、Responses API ✓、Anthropic API ✓；兩者皆支援非思考與思考模式；舊名 `deepseek-v4-flash` 等仍接受但由 flash 服務。思考模式下可用 tool（V3.2 起）。表中未列獨立 reasoner 模型。 | DS https://api-docs.deepseek.com/quick_start/pricing 、 https://api-docs.deepseek.com/guides/tool_calls 、 https://api-docs.deepseek.com/api/list-models |

### 8.2 歸納

- 有能力欄位可查：**Ollama**（`POST /api/show` 的 `capabilities` 含 `tools`；原生端點，非 `/v1`）、**OpenRouter**（`/api/v1/models` 的 `supported_parameters` 含 `tools`）。
- 沒有能力欄位、只能靠文件或實測：**OpenAI**（`/v1/models` 無）、**vLLM**（`/v1/models` 無；能力取決於 server 旗標與 parser，沒開時對 `auto`／`required`／指定 function 回 400，錯誤字串見上）、**DeepSeek**（`/models` 無；文件表列出兩個模型皆支援）。
- 不支援時的外觀（依本次原始碼）：vLLM 明確 400；Ollama 明確 400（`does not support tools`）；OpenRouter 預設可能**忽略** `tools`（若該模型全部 provider 皆不支援）；vLLM 未帶 `tool_choice` 且未啟用 auto tools 時無錯誤、無 `tool_calls`。「把呼叫寫成文字」型行為：vLLM 在 auto tools 關閉路徑下回傳原始 content。OpenAI／DeepSeek 對不支援模型的行為本次未查到。

---

## 9. OpenAI 官方對 prompt injection 與 tool 輸出的建議

來源：「Safety in building agents」 https://developers.openai.com/api/docs/guides/agent-builder-safety （`.md`：https://developers.openai.com/api/docs/guides/agent-builder-safety.md）。該頁現在列在文件側欄「Legacy APIs → Agent Builder」下；頁內聲明：「OpenAI is deprecating Agent Builder … the product is scheduled to shut down on November 30, 2026.」另有「Safety best practices」 https://developers.openai.com/api/docs/guides/safety-best-practices （通用）。

逐字引句（Safety in building agents）：

1. 定義：「A prompt injection happens when untrusted text or data enters an AI system, and malicious contents in that text or data attempt to override instructions to the AI. The end goals of prompt injections vary but can include exfiltrating private data via downstream tool calls, taking misaligned actions, or otherwise changing model behavior in an unintended way.」
2. 不受信任資料放哪裡：「Because developer messages take precedence over user and assistant messages, injecting untrusted input directly into developer messages gives attackers the highest degree of control. Pass untrusted inputs through user messages to limit their influence.」
3. Structured outputs 限制資料流：「By defining structured outputs between nodes (e.g., enums, fixed schemas, required field names), you eliminate freeform channels that attackers can exploit to smuggle instructions or data.」
4. 人工核准：「When using MCP tools, always enable tool approvals so end users can review and confirm every operation, including reads and writes.」
5. 綜合：「Design workflows so untrusted data never directly drives agent behavior. Extract only specific structured fields (e.g., enums or validated JSON) from external inputs to limit injection risk from flowing between nodes. Use guardrails, tool confirmations, and variables passed via user messages to validate inputs.」
6. 風險與限制：「Risk rises when agents process arbitrary text that influences tool calls. Structured outputs and isolation greatly reduce, _but don't fully remove_, this risk.」；「even with these mitigations, agents won't be perfect and can still make mistakes or be tricked」。
7. 模型選擇：「Use GPT-5 or GPT-5-mini … These models are more disciplined about following developer instructions and exhibit stronger robustness against jailbreaks and indirect prompt injections.」
8. 其他小節標題：Steer the agent with clear guidance and examples；Use guardrails for user inputs；Run trace graders and evals。

Safety best practices 頁相關句：「Can someone easily redirect the feature via prompt injections, e.g. 'ignore the previous instructions and do this instead'?」（red-teaming 一節）；「Limiting the amount of text a user can input into the prompt helps avoid prompt injection. Limiting the number of output tokens helps reduce the chance of misuse.」

附帶：OpenRouter 也有一份「Armor」外掛說明為「A safety classifier for tool calls, between the model and your application」，及 guardrail 可在 403 回應中標示 prompt injection 規則命中（`Request blocked: prompt injection patterns detected`）。（OR `llms.txt`、`api_reference/errors-and-debugging.md`）

---

## 未查到 / 有疑義

1. **OpenAI Chat Completions 串流中途錯誤的官方格式**：官方 guide 未見專節；僅知 SDK 把含 `error` 欄位的 SSE 事件轉成 `APIError`。
2. **OpenAI `prompt_tokens` 是否含 cached**：caching guide 只對 Responses 給出 `input_tokens - cached_tokens - cache_write_tokens` 的計價式；Chat Completions 沒有逐字等價說明。
3. **OpenAI 對不支援 tools 的模型傳 `tools` 的錯誤字串**：未查到。
4. **OpenAI 官方 tool 串流在 Chat Completions 的文字說明**：function-calling guide 的串流累積說明以 Responses 事件為主；Chat Completions 的 `delta.tool_calls[].index` 行為依據 SDK 型別與 helper 原始碼，而非獨立官方 prose。
5. **OpenRouter**：`tool_choice: "required"` 在 tool-calling 頁未列；各上游是否一次給完整 arguments、id 缺漏／重複，未見文件。OpenRouter 的 `prompt_tokens` 是否含 cached 未見明文。
6. **vLLM**：tool call `id` 的具體格式與是否可能重複、各 parser 在串流下是否分片，未逐 parser 查證；`vllm/entrypoints/openai/chat_completion/serving.py` 的串流工具呼叫細節未讀完。vLLM 的速率限制／`Retry-After`／mid-stream error 型別未查到。
7. **Ollama**：`/v1/chat/completions` 的 `parallel_tool_calls` 欄位未列於文件；串流時 arguments 是否可能分片，僅依 `ToToolCalls` 判斷為整物件；錯誤字串依 main 分支原始碼，實際版本可能不同；未見 Ollama 專屬 prompt caching 文件，僅見 usage 的 `cached_tokens` 可選欄位。
8. **DeepSeek**：錯誤 body 形狀、串流中途錯誤格式、`Retry-After` 標頭、tool call `id` 行為、是否支援 `parallel_tool_calls`，文件均未見；`/v1` 前綴（官方 base_url 為 `https://api.deepseek.com`，OpenAI SDK 範例不加 `/v1`）。Rate limit 頁只描述並行上限與 HTTP 429。
9. **respx 與 httpx2**：respx 0.23.1 的 `Requires-Dist` 為 `httpx>=0.25.0`；是否已有支援 httpx2 的正式發行版未查到，只見 open issue（#316、#324）與第三方 `pytest-httpx2`。本專案現有依賴為 `httpx>=0.28.1` 與 `respx>=0.23.1`；`openai` 3.37.0 另需 `httpx2`，兩套 HTTP 庫會並存於同一環境（事實，非建議）。
10. **vLLM／Ollama 版本**：文件取自 main 分支，與實際部署版本可能不同；vLLM PyPI 最新 0.32.0，Ollama 最新 v0.40.10。
11. **Safety 頁來源狀態**：OpenAI「Safety in building agents」已被標為隨 Agent Builder 淘汰的 Legacy 頁，是否有取代的 Agents/Responses 版本安全頁，本次未找到。
