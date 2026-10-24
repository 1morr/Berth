# AI provider：Anthropic Messages 與 OpenAI 相容格式

查證日期：2026-10-24（M5 票 06）。範圍：Berth 的對話核心（M5 側面板、M6 背景任務、M7 Discord 共用）要能接兩種 API 格式，使用者可填第三方 base URL 與 API key（plan §11.6〈provider〉）。這份回答票 06 的九題，給票 07（Anthropic adapter、設定、`ai_calls`）、07b（OpenAI 相容 adapter）與 08（對話核心）照著做。

來源規則：只用一手來源——Anthropic 與 OpenAI 的官方文件、兩家官方 Python SDK 的原始碼與 CHANGELOG、PyPI，第三方端點用各自的官方文件或原始碼（OpenRouter、vLLM、Ollama、DeepSeek、Moonshot）。查不到的標「未查到」，不以記憶補。逐條事實與來源 URL 在兩份底稿：

- [`ai-providers/anthropic.md`](ai-providers/anthropic.md)：Anthropic 這一側（下文簡稱 **A**，例如 A §3.5）
- [`ai-providers/openai-compatible.md`](ai-providers/openai-compatible.md)：OpenAI 相容與四個第三方端點（簡稱 **O**）

實測：[`scripts/experiments/ai_sdk_mocking.py`](../../scripts/experiments/ai_sdk_mocking.py)（`uv run --script`，SDK 裝在臨時環境、不進 Berth 的依賴）。2026-10-24 跑出：

```text
respx-plain : {'anthropic': 'APIConnectionError', 'openai': 'APIConnectionError'}
respx-alias : {"anthropic": "intercepted", "openai": "intercepted"}
stream-error: APIStatusError status=200
```

沒有用真的 API key 打過任何端點；要真 key 才能確認的事列在最後一節，由 07 / 07b 實測。

---

## 結論

### 1. 兩種格式都直接用 httpx 打，不用官方 SDK

| 理由 | 出處 |
| --- | --- |
| **兩家 SDK 都換成了 `httpx2`**：`anthropic` 2.3.0（2026-10-23）要 `httpx2>=2.0.0,<3`、1.0.0 起換；`openai` 3.37.0（2026-10-22）要 `httpx2>=2.12.0,<3`、3.0.0 起換，而且不再裝 `httpx`。用 SDK 等於程序裡多一套 HTTP 堆疊；`pyproject.toml` 已經為 Starlette 的 TestClient 決定過不跟著分裂 | A §1.1；O §1.1 |
| **專案的 respx 攔不到 SDK 的請求**（上面的 `respx-plain`，兩家都真的去連線）。官方給的兩條路都不好走：`httpx2.alias_httpx()` 會把整個程序的 `import httpx` 換掉、要在任何 import 之前（pytest 得用 `-p` 載一個早期 plugin），所有 adapter 跟著換；或每個 client 注入 `httpx2.MockTransport`，測試寫法與其他 adapter（plan §1.4 的 httpx + respx）不同。respx 0.23.1 仍只依賴 `httpx`，支援 httpx2 的只有 open issue | A §1.2；O §1.1、未查到第 9 條；`respx-alias` |
| **SDK 省下的不多**：兩種串流格式都小（Anthropic 是八種具名事件、其中 `ping` 略過，OpenAI 是 `data:` 行加 `[DONE]`）；工具參數只要整段拼完再解析，不需要 SDK 的 partial JSON；**內建重試要關掉**（兩家預設各重試 2 次，與 brief §6.10「provider 失敗交給人」相反，見結論 7） | A §1.3、§1.5、§3.5；O §1.2–§1.4 |
| **錯誤無論如何要自己分類**：Anthropic SDK 把串流中途的 overloaded 拋成裸 `APIStatusError`、`status_code == 200`（`stream-error`），要讀 body 才分得出；OpenAI SDK 把 503/504 都歸 `InternalServerError`。Berth 本來就有 `adapters/http.py` 的分類，自己打可以一路沿用 | A §1.4、§3.7；O §1.3 |
| **第三方的怪處在自己的解析器裡最好處理**：OpenRouter 的 usage chunk 帶非空的 `choices`、會在 200 裡回 `error`；DeepSeek 的快取欄位叫 `prompt_cache_hit_tokens`；vLLM 的快取寫入叫 `created_cache_tokens`；SSE 夾 `: keep-alive` 註解行 | O §1.4、§6.2、§7.2 |
| **SDK 變得快**：`anthropic` 10-14 到 10-23 發了 8 版，其中 2.0.0 是 breaking（新 API 版本 `2026-10-21`、預設改送 `Authorization: Bearer`、拿掉 `temperature` / `top_p` / `top_k`） | A §1.1、§1.2 |

代價：SSE 解析、兩個 adapter 的事件轉換、錯誤對照要自己寫與測。SSE 解析可以先評估 `httpx-sse`（PyPI 0.4.3，2025-10-10 發佈，`requires_dist` 空；https://pypi.org/pypi/httpx-sse/json ），07 開工時查它的維護狀態與 httpx 0.28 / respx 能不能一起用，不行就自己寫一個只認 `event:` / `data:` / 註解行 / 空行的小解析器。respx 回串流用 `httpx.Response(200, headers={"content-type": "text/event-stream"}, content=...)`。

### 2. OpenAI 相容走 Chat Completions（`POST {base}/chat/completions`）

OpenAI 官方建議新專案用 Responses、Chat Completions「remains supported」（O §2.1）。但 Berth 接的是第三方，**Chat Completions 是五家都支援、而且工具呼叫都能用的一支**（Ollama 的少了 `tool_choice`，O §3.3）；Responses 那邊缺得更多：OpenRouter 與 Ollama 只有 stateless，Ollama 的欄位同樣不含 `tool_choice`，DeepSeek 的串流沒有 `[DONE]`（O §2.2）。Berth 的對話本來就存在自己的資料庫、每次送完整歷史，用不到 Responses 的伺服器端狀態。

風險：OpenAI 官方「Starting with GPT-5.4, Chat Completions does not support tool calling with `reasoning_effort` values other than `none`」（O §2.1）。不送 `reasoning_effort` 時的預設值沒查到，07b 有 OpenAI 的 key 時實測（最後一節）。

### 3. 共同介面草案

對話核心只看下面這些型別；兩個 adapter 各自轉換。放在 `adapters/` 這一側、不 import services（票 07）。名字是草案，07 定。

```python
# 送出去的
@dataclass(frozen=True)
class ToolSpec:
    name: str  # 兩邊命名規則的交集：小寫 snake_case、短（A §3.1；OpenAI 的上限本票沒查）
    description: str
    input_schema: Mapping[str, object]  # JSON Schema object


@dataclass(frozen=True)
class TextPart:
    text: str


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # 模型給的 JSON 原文；解析與驗證交給登錄表（票 05 的統一輸入與拒絕）


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    content: str  # JSON 文字；錯誤也寫在這裡，is_error 只是附帶
    is_error: bool


@dataclass(frozen=True)
class OpaquePart:
    """provider 要求原樣帶回下一輪、Berth 不讀的東西（Anthropic 的 thinking、DeepSeek 的 reasoning_content）。"""

    format: ApiFormat  # 與 settings.ai 的「格式」同一個型別：ANTHROPIC / OPENAI_COMPATIBLE
    raw: Mapping[str, object]


@dataclass(frozen=True)
class UserTurn:
    parts: tuple[TextPart | ToolResult, ...]


@dataclass(frozen=True)
class ModelTurn:  # 模型的那一輪；不叫 Assistant，那是 CONTEXT.md 的「助理」
    parts: tuple[TextPart | ToolCall | OpaquePart, ...]


@dataclass(frozen=True)
class ChatRequest:
    model: str
    system: str  # 只放固定的字（結論 6）
    tools: tuple[ToolSpec, ...]  # 空 = 只能聊天，請求不帶 tools
    turns: tuple[UserTurn | ModelTurn, ...]
    max_output_tokens: int


# 收回來的（串流事件）
@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ToolCallStarted:  # 側面板的「正在查……」
    id: str
    name: str


@dataclass(frozen=True)
class TurnEnded:
    stop: StopReason  # END / TOOL_CALLS / MAX_TOKENS / REFUSED / OTHER
    stop_raw: str  # provider 給的原值（`end_turn`、`tool_calls`…），OTHER 時靠它說明
    reply: ModelTurn  # 這一輪完整的回覆，含拼好的 ToolCall
    usage: Usage


@dataclass(frozen=True)
class Usage:
    input_tokens: int | None  # 全部輸入，含快取寫入與讀取
    output_tokens: int | None
    cache_write_tokens: int | None  # None = 不知道，不是 0
    cache_read_tokens: int | None


class ChatProvider(Protocol):
    def stream(
        self, request: ChatRequest
    ) -> AsyncIterator[TextDelta | ToolCallStarted | TurnEnded]: ...
    async def list_models(self) -> list[str] | None: ...  # None = 端點沒有或讀不懂，退回手填
```

轉換時要守的規則（出處在對照表）：

- **一輪可以有多個 ToolCall**（兩邊預設都會平行呼叫）。核心把結果收成**一個** `UserTurn`，Anthropic adapter 轉成一則 user 訊息、`tool_result` 全部排在最前面；OpenAI adapter 轉成每個結果一則 `role: "tool"`，前一則 assistant 要原樣帶 `tool_calls`（A §3.6；O §3.1）。
- **`ToolCall.arguments` 是字串**：Anthropic 把 `input_json_delta.partial_json` 依 `index` 拼起來、空字串當 `{}`；OpenAI 把 `delta.tool_calls[].function.arguments` 依 `index` 拼起來，`id` 與 `name` 取第一次出現的值（A §3.5；O §3.1）。Ollama 一次給完整參數（O §3.3），同一個拼法照樣成立。第三方缺 `id` 時 adapter 自己補一個這一輪唯一的。
- **錯誤寫在 `content` 裡**：OpenAI 的 tool 訊息沒有 `is_error`，DeepSeek 的 Anthropic 相容端點忽略 `is_error`（A §8.2），所以失敗的原因一定寫進 `content`，`is_error` 只在 Anthropic 那邊附帶送。
- **`TurnEnded` 只在串流正常結束時發**（Anthropic 的 `message_stop`、OpenAI 的 `[DONE]` 或串流結尾）。OpenRouter 在 usage chunk 會重複一次 `finish_reason`（O §6.2），不能當成第二輪。結束前斷掉 → 拋錯誤（結論 8），錯誤上帶著斷掉之前已知的 `Usage`（結論 7），`ai_calls` 照樣記一列。
- **未知的事件與欄位一律略過**：Anthropic 的 `ping` 與將來的新事件、SSE 註解行（A §3.5；O §1.4）。

### 4. 偵測「支不支援工具呼叫」：設定頁的測試照實跑一次，能力欄位只拿來解釋

能力欄位不夠用：Anthropic 的 `/v1/models` 的 `capabilities` 沒有 tool use 這一格，OpenAI、vLLM、DeepSeek 的列模型端點也沒有；只有 Ollama（原生 `POST /api/show` 的 `capabilities` 含 `tools`）與 OpenRouter（`/api/v1/models` 的 `supported_parameters` 含 `tools`）查得到（A §4.3、§8；O §8.2）。而且就算查得到，OpenRouter 在某個模型的上游全都不支援時會**忽略** `tools`、照樣回 200（O §8.1）。所以以實測為準：

1. **第一次：不帶工具的最小請求**。驗 key、base URL、模型；失敗照結論 7 說原因，不往下走。
2. **第二次：帶一個無害的假工具**（例如 `berth_echo`，參數 `{"nonce": string}`），使用者訊息要模型用一個隨機 nonce 呼叫它。**請求的組法與對話核心完全相同**（同一個 adapter、同樣的 `tool_choice`），探針過了、真的對話才不會壞。不能強制呼叫：Anthropic 的 Opus 5.5、Sonnet 5.5、Fable 5.1 對 `tool_choice` 的 `any` / `tool` 回 400（A §3.2），Ollama 的 Chat Completions 不支援 `tool_choice`（O §3.3）。
3. **第三次：把假工具的結果送回去**，要拿到一則正常的文字回覆。這一步驗 tool result 的格式被接受（例如 DeepSeek 思考模式帶工具時要把前幾輪的 `reasoning_content` 送回去，O §3.4）。票 07 原文只寫「再試一次工具呼叫」，這一步是本研究加的建議，07 開工時一起定。

判定：

| 第二次的結果 | 判成 | 說給人聽（07 / 07b 的文案方向） |
| --- | --- | --- |
| 一個 `berth_echo` 的 ToolCall，`arguments` 解得開、`nonce` 對 | 支援（第三次也過才算） | — |
| 400，且第一次成功 | 不支援 | 原文照記；認得的給下一步：vLLM 的 `"auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set` →「啟動 vLLM 時加這兩個選項」；Ollama 的 `<model> does not support tools` →「換一個 ollama.com/search?c=tool 列的模型」（O §8.1） |
| 200，只有文字 | 不支援 | 文字裡出現 nonce 或工具名 →「模型把呼叫寫成了文字」（vLLM 沒開 parser 時的樣子，O §8.1）；沒有 →「端點忽略了工具」（OpenRouter 的樣子） |
| 呼叫了，但名字不對或 nonce 不對 | 不支援 | 「呼叫的格式不對」 |
| 限流、provider 掛掉、連不上 | 不知道，不存 | 「這次沒測成，稍後再測」 |

能力欄位查得到的（Ollama、OpenRouter）在判成「不支援」時順便查一次，讓說明更具體；不拿它代替實測。結果存在 `settings.ai`，格式、base URL、模型任一改了就要重測（票 07）。

### 5. base URL、認證、模型清單

**base URL 照兩家 SDK 的慣例**，使用者照第三方文件給的值貼上就對：OpenAI 格式的 base **含** `/v1`（`openai` 預設 `https://api.openai.com/v1`、讀 `OPENAI_BASE_URL`，O §1.1），Anthropic 格式的 base **不含** `/v1`（`ANTHROPIC_BASE_URL`，SDK 自己接 `/v1/messages`，A §1.2）。

| 端點 | Anthropic 格式的 base | OpenAI 格式的 base | 出處 |
| --- | --- | --- | --- |
| 官方 | 留空（`https://api.anthropic.com`） | 留空（`https://api.openai.com/v1`） | A §1.6；O §1.1 |
| OpenRouter | `https://openrouter.ai/api` | `https://openrouter.ai/api/v1` | A §8.2；O §2.2 |
| DeepSeek | `https://api.deepseek.com/anthropic` | `https://api.deepseek.com`（官方範例不加 `/v1`） | A §8.2；O 未查到第 8 條 |
| Moonshot | `https://api.moonshot.ai/anthropic` | `https://api.moonshot.ai/v1`（只查了列模型端點在這底下） | A §8.2 |
| Ollama | `http://<主機>:11434` | `http://<主機>:11434/v1` | A §8.2；O §4 |
| vLLM | 有 Anthropic 入口（原始碼目錄），文件沒查 | `http://<主機>:<port>/v1` | O §2.2、§4 |

**認證**：OpenAI 格式送 `Authorization: Bearer <key>`。Anthropic 官方現在要 `Authorization: Bearer`，`x-api-key` 是「Legacy fallback」，版本 header 是 `anthropic-version: 2026-10-21`（A §1.6）；第三方不一：DeepSeek 文件只列 `x-api-key`、Ollama 雲端只收 Bearer、OpenRouter 與 Moonshot 用 Bearer（A §8.2）。「兩個 header 都送」官方接不接受沒查到，07 有真 key 時實測（最後一節）。Berth 不送 `temperature` / `top_p` / `top_k`（`2026-10-21` 送了回 400，A §1.2）。**自架的 Ollama 與 vLLM 可以不要 key**（Ollama 本機不驗 key，A §8.2），所以「AI 有沒有設定」不能只看有沒有 key（最後一節）。

**模型清單**：Anthropic 格式打 `GET {base}/v1/models?limit=1000`、讀 `data[].id`（官方另有 `display_name`；有 `has_more` 分頁，A §4.3）；OpenAI 格式打 `GET {base}/models`、讀 `data[].id`——OpenAI、OpenRouter、vLLM、Ollama、DeepSeek 都是這個形狀（O §4）。讀不到或形狀不對 → `None`，設定頁退回手填。**預設模型只在官方 Anthropic 端點時給**：官方 models overview「start with Claude Opus 5.5」，id `claude-opus-5-5`（A §4.1）；現役四個 id `claude-fable-5-1`、`claude-opus-5-5`、`claude-sonnet-5-5`、`claude-haiku-5-5` 沒有另外的 alias，而且「All current models support ... tool use」。第三方端點不給預設（DeepSeek 會把 `claude-opus*` 映射到自己的模型，A §8.2），一定要選或填。

### 6. prompt caching：固定的前綴在最前、順序固定、會變的字放進訊息

兩邊的快取都要求前綴逐字相同，Anthropic 的前綴順序是 `tools` → `system` → `messages`（A §5），OpenAI 是開頭的 token 完全一致、前綴 hash 含工具定義（O §5.1）。所以：

- **工具定義依名稱排序、序列化固定**；同一個角色每次送一模一樣的清單。改工具定義會讓 Anthropic 的三段快取全部失效（A §5）。
- **system 只放固定的字**：不放時間、使用者名字、這一頁的狀態；這些放在使用者那一輪的訊息裡。介面語言如果要寫進 system，就只有兩種前綴（zh-Hant / en），照樣吃得到。
- **`tool_choice` 固定**（`auto` 或不送）：Anthropic 改 `tool_choice` 會讓 messages 段失效（A §3.2）。只能聊天的模型不送工具，是另一個前綴，本來就分開。
- **Anthropic 放兩個 breakpoint**：system 最後一個 block 上一個顯式 `cache_control: {"type": "ephemeral"}`（讓不同對話共用 tools + system），加上請求頂層的 `cache_control`（自動快取，breakpoint 隨對話往後移）；共用 4 個上限裡的 2 個（A §5）。現役模型最小可快取 512 tokens，短於它不快取也不報錯；TTL 用預設 5 分鐘（寫入 1.25 倍、讀取 0.1 倍以下；1 小時寫入是 2 倍）。第三方：OpenRouter 收兩種、Moonshot 只認頂層、DeepSeek 忽略、Ollama 不支援（A §8.2）——不支援時是忽略還是 400 沒查到，07 實測。
- **OpenAI 相容什麼都不用送**：OpenAI 自動快取、GPT-5.6 起最小 1,024 tokens（O §5.1）；DeepSeek 預設開、vLLM 預設開 prefix caching（O §5.2）。`prompt_cache_key`、OpenRouter 的 `session_id` 這類非標準欄位 M5 不送：vLLM / Ollama 碰到不認得的欄位怎麼辦沒查。

### 7. `usage` 對映與快取命中率

| Berth 的 `Usage` | Anthropic | OpenAI 相容 |
| --- | --- | --- |
| `input_tokens`（全部輸入） | `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`（官方原文的總輸入公式；`input_tokens` 只算最後一個 breakpoint 之後的）；兩個快取欄位都沒回時就是 `input_tokens` | `prompt_tokens`（DeepSeek 明寫等於 hit + miss，vLLM 是全部 prompt token；OpenAI 的 Chat Completions 沒有逐字說明，Responses 的計價式是含的） |
| `output_tokens` | `output_tokens` | `completion_tokens` |
| `cache_read_tokens` | `cache_read_input_tokens`，沒回 → `None` | `prompt_tokens_details.cached_tokens`；沒有 `prompt_tokens_details` 時看 DeepSeek 的 `prompt_cache_hit_tokens`；都沒有 → `None`（vLLM 沒開 `--enable-prompt-tokens-details`、Ollama 引擎沒回報時就是這樣） |
| `cache_write_tokens` | `cache_creation_input_tokens`，沒回 → `None` | `prompt_tokens_details.cache_write_tokens`（OpenAI、OpenRouter）、vLLM 的 `created_cache_tokens`；都沒有 → `None`（DeepSeek、Ollama 沒有這一格） |
| 串流時從哪拿 | `message_start.message.usage` 起始，`message_delta.usage` 是**累計值**、有給的欄位就覆寫（沒給的保留 `message_start` 的） | 請求帶 `stream_options: {"include_usage": true}`（OpenRouter 不用帶也會給）；取**最後一個 `usage` 非 null 的 chunk**，不管它的 `choices` 是不是空的（OpenAI 是空的、OpenRouter 不是） |
| 出處 | A §6 | O §6 |

缺欄位的原則：**沒回的是「不知道」（`None`），回了 0 才是 0**。串流中途斷掉時，斷掉之前收到的照記：Anthropic 的 `message_start` 已經給了輸入與快取欄位，所以只有 `output_tokens` 是 `None`；OpenAI 相容的 usage 只在最後一個 chunk，所以四格都是 `None`（O §6.1：「If the stream is interrupted, you may not receive the final usage chunk」）。

**快取命中率** = Σ `cache_read_tokens` ÷ Σ `input_tokens`，**只算兩格都知道的呼叫**；`cache_read_tokens` 不知道的呼叫不進分子也不進分母，用量頁另外說「N 次呼叫沒有回報快取」。`cache_write_tokens` 不知道不影響命中率（全部輸入已經含它）。

### 8. 錯誤：分成七種，M5 一律不自動重試

| 分類 | Anthropic | OpenAI 相容 | 下一步 |
| --- | --- | --- | --- |
| 限流 | 429 `rate_limit_error`，`retry-after`（秒）有時有 | 429，`error.code` 是 `rate_limit_exceeded` 一類或 `slow_down`，`Retry-After`；OpenRouter、DeepSeek 也是 429 | 說「被限流」，有 `retry-after` 就說幾秒後再試 |
| 額度用完 | 402 `billing_error`；400 的 spend limit；**沒有 `retry-after` 的 429 可能是月支出上限**（官方：「A tier spend-cap 429 has no `retry-after` header」，但也說不是每個 429 都帶它） | 429 且 `error.code` 是 `credit_balance_exhausted`、`*_spend_limit_exceeded`、`*_usage_limit_exceeded` 或 `error.type == "insufficient_quota"`；402（OpenRouter、DeepSeek） | 交給人；官方：「Retrying billing, spend, or quota errors won't restore API access」 |
| provider 掛掉 | 500 `api_error`、504 `timeout_error`、529 `overloaded_error`；**200 之後的 SSE `event: error`** | 500、502、503（`server_is_overloaded`）；OpenRouter 在 200 裡回 `error` 或 `finish_reason: "error"`；vLLM 串流中送錯誤再 `[DONE]` | 說「provider 暫時有問題」 |
| 憑證不對 | 401 `authentication_error`、403 `permission_error` | 401、403 | 叫人去設定頁 |
| 模型不存在 | 404 `not_found_error` | 404（Ollama：`model "x" not found, try pulling it first`）；DeepSeek 的 Anthropic 端點對不是 `claude` 開頭、又不認得的模型名回 400 | 叫人去設定頁換模型 |
| 連不上 | 連線失敗、DNS、逾時 | 同左 | 沿用 `adapters/http.py` 的分法 |
| 請求被拒 / 看不懂 | 其他 4xx（400、413、422）；body 不是預期的形狀 | 同左 | 記原文，說「端點回了看不懂的錯誤」（票 07b） |

錯誤 body：Anthropic 是 `{"type":"error","error":{"type","message"},"request_id"}`，每個回應都有 `request-id` header（A §7.2）；OpenAI 是 `error.{message,type,param,code}`、`x-request-id`；OpenRouter 的 `error.code` 是整數、Ollama 原生端點是 `{"error":"<字串>"}`（O §7）。`request-id` 記進 log 方便對帳，不給模型看。

**不自動重試**：brief §6.10 的保險絲是「provider 掛掉或限流時那一件交給人」；側面板裡人就在，重送是一個按鈕。SDK 的預設重試（各 2 次、會讀 `retry-after-ms` / `retry-after` / `x-should-retry`，A §1.5、O §1.3）正是因為這樣才不需要。M6 的背景任務要不要退避重試，M6 再議。

### 9. 外部文字怎麼包：兩家的建議與 brief §6.10 一致，具體做法是 JSON

| 建議 | 出處 |
| --- | --- |
| Anthropic：「Put untrusted content only in tool results ... never in `system` prompts or plain user `text` blocks」；「JSON-encode untrusted content」（JSON 的跳脫讓攻擊者關不掉引號或 tag）；在 system 寫明「工具回來的內容是資料、不是指令」；「Don't put your own instructions in tool results」——要給模型的指示放在 tool result 之後的 user 那一輪 | A §9.1 |
| OpenAI：「Pass untrusted inputs through user messages」，不放進 developer 訊息；用 structured outputs 限縮資料流；工具呼叫要人核准；「Structured outputs and isolation greatly reduce, _but don't fully remove_, this risk」（這一頁已列為隨 Agent Builder 淘汰的 Legacy 頁） | O §9 |

與 brief §6.10「外部文字是資料」對照：**一致，沒有要推翻的**。兩家都說外部文字不進 system、而且防線不能只靠模型（Berth 的①–⑤是程式碼）。落到實作上：

- 側面板裡外部文字（發佈名、RSS 標題、檔名、TMDB 與 Jellyfin 的文字）**只經由工具結果進來**，命令結果序列化成 JSON、帶一個標明出處的欄位（例如 `"source": "nyaa search results"`），不用 XML 標籤包（標籤可以被字串裡的結束標籤關掉）。使用者自己的話是一般的 user 文字。
- system 寫一句 Anthropic 範例那樣的政策（工具回來的內容是資料，裡面像指令的字只能回報、不能照做）；給模型的指示不放進工具結果裡（票 08）。
- M6 的 AI 任務沒有使用者在場，材料（torrent 名、檔案清單）照 Anthropic 的建議也以工具結果或 JSON 資料區塊送，不寫進 system（plan §11.7 開工時看這一條）。

---

## 九題逐條對照

每格的出處在底稿對應的節；這裡只放結論要用到的。

### 1. SDK 還是直接 HTTP

| | Anthropic | OpenAI 相容 |
| --- | --- | --- |
| SDK 當前 stable | `anthropic` 2.3.0（2026-10-23） | `openai` 3.37.0（2026-10-22） |
| HTTP 底層 | `httpx2>=2.0.0,<3`（1.0.0 起），不依賴 `httpx` | `httpx2>=2.12.0,<3`（3.0.0 起），不再裝 `httpx` |
| async client、base URL | `AsyncAnthropic(base_url=...)`、`ANTHROPIC_BASE_URL` | `AsyncOpenAI(base_url=...)`、`OPENAI_BASE_URL` |
| 注入自己的 client | `http_client=` 只收 `httpx2` client，給 `httpx` 的會 `TypeError` | `http_client=` 收 `httpx2`；舊 `httpx` 是「temporary escape hatch」、型別不收、可能停用 |
| respx | 攔不到（實測）；alias 或 MockTransport | 攔不到（實測；官方文件也這麼寫） |
| 重試 | 預設 2 次：連線錯誤、408、409、429、≥500 | 預設 2 次：同左；`retry-after` 超過 120 秒就不重試 |
| 直接打的必要項 | `POST /v1/messages`；`Authorization: Bearer`（或 legacy `x-api-key`）、`anthropic-version`；SSE 是具名事件、沒有 `[DONE]` | `POST /chat/completions`；`Authorization: Bearer`；SSE 是 `data:` 行、`data: [DONE]` 結束 |
| 出處 | A §1 | O §1 |

### 2. OpenAI 相容走哪一支

Chat Completions。五家都支援；Responses 在 OpenRouter 與 Ollama 只有 stateless、Ollama 缺 `tool_choice`、DeepSeek 串流沒有 `[DONE]`（O §2.2）。Anthropic 格式只有 Messages 一支。

### 3. tool use 加串流

| | Anthropic | OpenAI 相容（Chat Completions） |
| --- | --- | --- |
| 工具定義 | `{name, description, input_schema}`；`name` 合 `^[a-zA-Z0-9_-]{1,128}$` | `{"type":"function","function":{name, description, parameters, strict?}}` |
| `tool_choice` | `auto` / `any` / `tool` / `none`；**Opus 5.5、Sonnet 5.5、Fable 5.1 的 `any` / `tool` 回 400** | `auto` / `none` / `required` / 指定 function；Ollama 不支援 `tool_choice`；vLLM 的 `auto` 要啟動選項 |
| 回應裡的呼叫 | `content[]` 的 `tool_use` block：`id`、`name`、`input`（物件） | `message.tool_calls[]`：`id`、`function.name`、`function.arguments`（**JSON 字串**，官方說不一定是合法 JSON） |
| 結束原因 | `stop_reason`：`end_turn`、`tool_use`、`max_tokens`、`stop_sequence`、`pause_turn`（只與 server tools 有關）、`refusal`（200，不是錯誤）、`model_context_window_exceeded` | `finish_reason`：`stop`、`tool_calls`、`length`、`content_filter`；OpenRouter 另有 `error`、DeepSeek 另有 `insufficient_system_resource`、`aborted` |
| 串流 | `message_start` → [`content_block_start` → `content_block_delta`（`text_delta` / `input_json_delta`）→ `content_block_stop`]… → `message_delta` → `message_stop`，中間有 `ping`；工具參數依 `index` 拼 `partial_json` | `choices[].delta.content` 與 `delta.tool_calls[]`（依 `index`，第一片帶 `id` 與 `name`，之後只有 `arguments` 片段）；`[DONE]` 結束 |
| 平行呼叫 | 預設會；`tool_choice.disable_parallel_tool_use: true` 關（DeepSeek 忽略它） | 預設會；`parallel_tool_calls: false` 關（Ollama、DeepSeek 文件沒列） |
| 送回結果 | 下一則 user 訊息，`tool_result` block（`tool_use_id`、`content`、`is_error`）全部排最前，緊接在對應的 assistant 之後 | 每個結果一則 `{"role":"tool","tool_call_id","content"}`；前一則 assistant 要帶 `tool_calls`；每次請求都要再送 `tools` |
| 串流中途出錯 | `event: error`，`{"type":"error","error":{"type":"overloaded_error",...}}`；tool use 不能從一半恢復 | 官方沒有專節；SDK 把 `data` 裡含 `error` 的事件當錯誤；OpenRouter 送含 `error` 與 `finish_reason: "error"` 的 chunk 再結束 |
| 出處 | A §3 | O §3 |

### 4. 模型

| | Anthropic | OpenAI 相容 |
| --- | --- | --- |
| 模型 id | 現役 `claude-fable-5-1`、`claude-opus-5-5`、`claude-sonnet-5-5`、`claude-haiku-5-5`，沒有另外的 alias；官方「start with Claude Opus 5.5」 | 不固定，看端點；DeepSeek 現在是 `deepseek-flash`、`deepseek-v4-pro` |
| 列模型端點 | `GET /v1/models`：`data[]`（`id`、`display_name`、`capabilities`…）、`has_more`、`limit` 最多 1000 | `GET /models`：`data[].id`；OpenRouter 另有 `supported_parameters`、`pricing`；Ollama 原生 `/api/show` 有 `capabilities` |
| 出處 | A §4 | O §4 |

### 5. prompt caching

| | Anthropic | OpenAI 相容 |
| --- | --- | --- |
| 怎麼開 | 顯式：block 上的 `cache_control`（最多 4 個）；自動：請求頂層 `cache_control` | 自動，不用送（OpenAI、DeepSeek、vLLM 預設開） |
| 最小長度 | 現役四個模型 512 tokens | OpenAI GPT-5.6 起 1,024 tokens |
| TTL | 5 分鐘（命中刷新），可選 1 小時 | OpenAI GPT-5.6 起預設 30 分鐘；DeepSeek 幾小時到幾天、best-effort |
| 前綴 | `tools` → `system` → `messages`；改工具定義全失效，改 `tool_choice` 只失效 messages | 開頭 token 完全一致；前綴 hash 含工具定義 |
| 第三方 | OpenRouter 兩種都收；Moonshot 只認頂層；DeepSeek 忽略；Ollama 不支援 | OpenRouter 對 Anthropic 上游要 `cache_control`，其餘多半自動 |
| 出處 | A §5、§8.2 | O §5 |

### 6. `usage`

見結論 7 的表。第三方常缺的：快取寫入（DeepSeek、Ollama 沒有這一格；Anthropic 相容的 Ollama 只回 `input_tokens` 與 `output_tokens`）、快取讀取（vLLM 要啟動選項、Ollama 看引擎）。

### 7. 錯誤

見結論 8 的表。retry-after：Anthropic 429 有時帶 `retry-after`（秒），另有 `anthropic-ratelimit-*`；OpenAI 429 / 503 可能帶 `Retry-After`，另有 `x-ratelimit-*`；OpenRouter 429、503 可能帶；vLLM、Ollama、DeepSeek 沒查到（O §7.2）。

### 8. 支不支援工具呼叫

| 端點 | 能力欄位 | 不支援時的樣子 |
| --- | --- | --- |
| Anthropic 官方 | 沒有（`capabilities` 沒有 tool use 這一格）；現役模型都支援 | — |
| DeepSeek（兩種格式） | 沒有；文件表列兩個模型都支援 | 沒查到 |
| OpenAI 官方 | 沒有 | 沒查到 |
| OpenRouter | `supported_parameters` 含 `tools` | 上游全都不支援時**忽略 `tools`**、回 200 |
| vLLM | 沒有；看啟動選項 `--enable-auto-tool-choice` 與 `--tool-call-parser` | 送 `tool_choice: "auto"` → 400；不送 `tool_choice` → 呼叫以文字出現、不報錯 |
| Ollama | 原生 `POST /api/show` 的 `capabilities` 含 `tools` | 400 `<model> does not support tools` |

做法見結論 4。出處：A §8；O §8。

### 9. tool result 與 prompt injection

見結論 9。

---

## 留給 07 / 07b 實測的事

沒有真 key 查不到，或文件互相矛盾的；實測完寫回 brief §20 那一節。票 07（2026-10-24，沒有真 key）的處置寫在 brief §20.24「票 07 實作時定的」：第 6 條已定，第 1–3 條照研究的建議先做、等有 key 時實測。票 07b（同日，也沒有真 key 與第三方端點）的處置寫在 brief §20.24「票 07b 實作時定的」：第 4、5、7 條照那裡的做法先做，等有端點時實測。

1. **Anthropic 官方接不接受同時送 `Authorization: Bearer` 與 `x-api-key`**：接受就兩個都送（DeepSeek 只寫了 `x-api-key`、Ollama 雲端只收 Bearer），不接受就只送 Bearer。官方文件的 cURL 範例自己也新舊並存（A 未查到第 1 條）。
2. **第三方 Anthropic 相容端點碰到 `anthropic-version: 2026-10-21` 與頂層 `cache_control` 時是忽略還是 400**（Ollama 文件只說拒絕比 `2023-06-01` 舊的版本、`cache_control` 不支援）。
3. **Anthropic 現役模型在 `2026-10-21` 預設會不會回 `thinking` block**：會的話 adapter 要把它當 `OpaquePart` 原樣帶回下一輪。本票沒查 thinking 的往返規則。
4. **OpenAI 官方的 Chat Completions 不送 `reasoning_effort` 時工具呼叫能不能用**（GPT-5.4 起只有 `none` 能用工具，預設值沒查到）。
5. **Ollama 的 Chat Completions 收到 `tool_choice` 是忽略還是 400**：決定 OpenAI adapter 送不送 `tool_choice: "auto"`（送了 vLLM 會給清楚的 400，不送則 vLLM 沒開 parser 時呼叫變成文字——兩種探針都判得出不支援，差在說明能不能具體）。
6. **「AI 有沒有設定」的判斷**：brief 與票 07 寫「沒設 key 時與 M4 相同」，但自架的 Ollama / vLLM 不需要 key。07 要定「設定好」看什麼（例如格式、模型都有，且官方端點時有 key）。
7. **OpenAI 相容的 `prompt_tokens` 含不含快取讀取**：DeepSeek 與 vLLM 明寫含，OpenAI 的 Chat Completions 與 OpenRouter 沒有逐字說明（O 未查到第 2、5 條）。結論 7 的命中率假設含；不含的話會超過 100%。07b 有真端點時各看一次 `cached_tokens` 與 `prompt_tokens`，在那之前 adapter 遇到讀取大於輸入就把讀取記成「不知道」並寫 log。
