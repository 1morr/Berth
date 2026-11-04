"""AI provider：依設定組出 pydantic-ai 的模型物件，與「測試連線」的那一次最小呼叫（M5 票 09）。

兩種接口（brief §14〈provider〉、§20.24）：

- **Anthropic Messages**：base URL **不含 `/v1`**，SDK 自己接 `/v1/messages`；使用者貼了帶 `/v1`
  的網址就拿掉（`normalize_base_url`），否則會打到 `/v1/v1/messages`。
- **OpenAI 相容 Chat Completions**：base URL 照那家服務的文件原樣用（OpenAI 官方含 `/v1`，
  DeepSeek 的 `https://api.deepseek.com` 不含）。

**產品不讀環境變數**（設定在資料庫）：兩家 SDK 在 `api_key` / `base_url` 沒給時會去讀
`ANTHROPIC_API_KEY`、`OPENAI_BASE_URL` 這類變數，所以這裡永遠明給，留空的 base URL 換成官方端點。
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlsplit

import httpx2
from pydantic_ai import ModelRequest, RunContext
from pydantic_ai.capabilities import AbstractCapability, NativeTool
from pydantic_ai.direct import model_request
from pydantic_ai.exceptions import (
    ModelAPIError,
    ModelAuthenticationError,
    ModelConnectionError,
    ModelHTTPError,
    ModelNotFoundError,
    UnexpectedModelBehavior,
)
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.native_tools import WebSearchTool
from pydantic_ai.profiles import ModelProfile
from pydantic_ai.profiles.anthropic import AnthropicEffort
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings, ThinkingLevel

from berth.domain import AiProbeFailure, AiProvider, AiReasoning

#: base URL 留空時打的官方端點（SDK 的預設值，明寫是為了不讓它去讀環境變數）。
OFFICIAL_BASE_URL: dict[AiProvider, str] = {
    AiProvider.ANTHROPIC: "https://api.anthropic.com",
    AiProvider.OPENAI: "https://api.openai.com/v1",
}

#: 測試連線：只試一次（SDK 預設重試兩次，按鈕會多轉十幾秒），30 秒沒回就算連不上。
#: `max_tokens` 夠模型回一個字就好。
_PROBE_SETTINGS: ModelSettings = {"max_tokens": 16, "max_retries": 0, "timeout": 30}
_PROBE_PROMPT = "Reply with the single word OK."


@dataclass(frozen=True, slots=True)
class AiEndpoint:
    """組一個模型要的四樣東西，與每次呼叫帶的推理程度。`base_url` 空的是官方端點。"""

    provider: AiProvider
    base_url: str
    api_key: str
    model: str
    reasoning: AiReasoning = AiReasoning.MEDIUM


@dataclass(frozen=True, slots=True)
class Probe:
    """一次最小呼叫的結果。"""

    #: 成功是 `None`。
    failure: AiProbeFailure | None
    #: 服務回的 HTTP 狀態碼；沒有回應（連不上）或成功是 `None`。
    status: int | None
    #: 服務回的原文（錯誤的 body、連線錯誤的訊息）；成功是空字串。
    detail: str
    #: 回話的模型名稱（服務自己報的，可能與設定的不同，例如帶日期的版本）；失敗是空字串。
    model: str


def normalize_base_url(provider: AiProvider, base_url: str) -> str:
    """去掉空白與結尾的 `/`；Anthropic 另外去掉結尾的 `/v1`（SDK 自己會接）。"""
    url = base_url.strip().rstrip("/")
    if provider is AiProvider.ANTHROPIC and url.endswith("/v1"):
        url = url.removesuffix("/v1")
    return url


def effective_base_url(provider: AiProvider, base_url: str) -> str:
    """實際打的網址：留空是那一家的官方端點。查價（`prices`）與記帳（`ai_calls.base_url`）用它。"""
    return normalize_base_url(provider, base_url) or normalize_base_url(
        provider, OFFICIAL_BASE_URL[provider]
    )


def is_official(endpoint: AiEndpoint) -> bool:
    """打的是那一家自己的端點（base URL 留空或填的就是官方那一個）。網搜的價只在這裡確定。"""
    official = normalize_base_url(endpoint.provider, OFFICIAL_BASE_URL[endpoint.provider])
    return effective_base_url(endpoint.provider, endpoint.base_url) == official


def has_native_web_search(provider: AiProvider) -> bool:
    """這種接口有沒有伺服器端的 `web_search`：只有 Anthropic Messages 有（brief §20.24）。"""
    return provider is AiProvider.ANTHROPIC


def native_web_search[D](
    provider: AiProvider, domains: Sequence[str], max_uses: int, available: Callable[[D], bool]
) -> list[AbstractCapability[D]]:
    """伺服器端的 `web_search`（M5 票 17）：只有 Anthropic Messages 有（官方與 DeepSeek 的相容端點，
    brief §20.24），Chat Completions 沒有、回空的。只搜 `domains`（含子網域）。

    每次模型呼叫之前問一次 `available(deps)`：這一輪的額度用完了，這一次起就不掛（pydantic-ai 的
    動態 native tool，回 `None` 是這一步沒有它）。**`max_uses` 每次都一樣**：它是工具定義的一部分，
    而改工具定義會讓整段 prompt 快取失效（brief §20.24）；照剩幾次調它，每搜一次下一次就整段重寫。
    代價是最後一次呼叫可能多搜幾次（最多 `max_uses - 1`），比重寫快取便宜得多。
    """
    if not has_native_web_search(provider):
        return []
    tool = WebSearchTool(max_uses=max_uses, allowed_domains=list(domains))

    def prepare(ctx: RunContext[D]) -> WebSearchTool | None:
        return tool if available(ctx.deps) else None

    return [NativeTool(prepare)]


def build_model(endpoint: AiEndpoint, *, http_client: httpx2.AsyncClient | None = None) -> Model:
    """照設定組出模型物件。`http_client` 給測試換 transport；正式環境用 SDK 自己的。"""
    base_url = effective_base_url(endpoint.provider, endpoint.base_url)
    if endpoint.provider is AiProvider.ANTHROPIC:
        return AnthropicModel(
            endpoint.model,
            provider=AnthropicProvider(
                api_key=endpoint.api_key, base_url=base_url, http_client=http_client
            ),
        )
    return OpenAIChatModel(
        endpoint.model,
        provider=OpenAIProvider(
            api_key=endpoint.api_key, base_url=base_url, http_client=http_client
        ),
    )


async def probe(model: Model) -> Probe:
    """打一次最小呼叫：成功說哪個模型回的，失敗說是哪一種與服務的原文。"""
    try:
        response = await model_request(
            model, [ModelRequest.user_text_prompt(_PROBE_PROMPT)], model_settings=_PROBE_SETTINGS
        )
    except ModelHTTPError as exc:
        return Probe(_http_failure(exc), exc.status_code, _body_text(exc.body), "")
    except ModelConnectionError as exc:
        return Probe(AiProbeFailure.UNREACHABLE, None, _message(exc), "")
    except (UnexpectedModelBehavior, ModelAPIError) as exc:
        return Probe(AiProbeFailure.BAD_RESPONSE, None, _message(exc), "")
    return Probe(None, None, "", response.model_name or "")


#: 400 的內文提到這些參數，就當成服務拒絕了推理參數：`output_config.effort`、`reasoning_effort`、
#: `thinking.type`、`thinking.budget_tokens`。只說 `thinking` 或 `reasoning` 的不算：重播推理內容的
#: 400（簽章不符、DeepSeek 要回傳 `reasoning_content`）改程度沒有用。
_REASONING_PARAMS = re.compile(r"output_config|effort|thinking\.type|budget_tokens", re.IGNORECASE)


def rejects_reasoning(error: str) -> bool:
    """模型呼叫的錯誤原文（`str(ModelHTTPError)`：`status_code: 400, model_name: …, body: …`）是
    不是服務拒絕了推理參數（M5.5 票 17）。只看 400 的 body：模型名本身可能帶 `reasoner`。"""
    head, _, body = error.partition(", body: ")
    return head.startswith("status_code: 400,") and bool(_REASONING_PARAMS.search(body))


def _http_failure(exc: ModelHTTPError) -> AiProbeFailure:
    if isinstance(exc, ModelAuthenticationError) or exc.status_code in (401, 403):
        return AiProbeFailure.KEY_REJECTED
    if isinstance(exc, ModelNotFoundError) or exc.status_code == 404:
        return AiProbeFailure.NOT_FOUND
    return AiProbeFailure.SERVICE_ERROR


def _body_text(body: object) -> str:
    if body is None:
        return ""
    if isinstance(body, str):
        return body
    return json.dumps(body, ensure_ascii=False)


def _message(exc: BaseException) -> str:
    """例外的訊息，連同它包住的那一個（SDK 的連線錯誤原因在 `__cause__`）。"""
    parts = [str(exc)]
    if exc.__cause__ is not None and str(exc.__cause__) not in parts[0]:
        parts.append(str(exc.__cause__))
    return ": ".join(part for part in parts if part)


#: 統一設定（`thinking`）的程度；`off` 是 `False`。
_THINKING: dict[AiReasoning, ThinkingLevel] = {
    AiReasoning.OFF: False,
    AiReasoning.LOW: "low",
    AiReasoning.MEDIUM: "medium",
    AiReasoning.HIGH: "high",
}
#: Anthropic 接口明寫的 effort（`off` 另外明寫關，見 `_reasoning`）。
_EFFORT: dict[AiReasoning, AnthropicEffort] = {
    AiReasoning.LOW: "low",
    AiReasoning.MEDIUM: "medium",
    AiReasoning.HIGH: "high",
}


class _Send(Enum):
    """推理程度怎麼送（`_how_to_send`）。"""

    #: 統一的 `thinking`，pydantic-ai 照 profile 換成那一家的參數。
    UNIFIED = "unified"
    #: Anthropic 接口明寫 `anthropic_effort` / `anthropic_thinking`。
    EXPLICIT = "explicit"
    #: 同 `EXPLICIT`，但「關」什麼都不送：認不得的相容閘道。
    EFFORT_ONLY = "effort_only"
    #: 不送：這個模型的程度沒有效果。
    NOTHING = "nothing"


#: Anthropic 相容端點裡已知兩個參數都收的（`output_config.effort` 與 `thinking.type: disabled`）：
#: 文件寫了、也實測過（brief §20.26）。以主機認，不以模型名：收不收參數是端點的事，轉送 DeepSeek
#: 模型的閘道照樣可能認不得。
_TAKES_THINKING_OFF = frozenset({"api.deepseek.com"})


def _how_to_send(endpoint: AiEndpoint, profile: ModelProfile) -> _Send:
    """推理程度怎麼變成請求參數（M5.5 票 17、17b，brief §20.26，以錄下的請求為準）。

    - Anthropic 接口、profile 有 `anthropic_supports_effort`（Claude Opus 4.5 起、Sonnet 4.6 起）：
      統一設定，pydantic-ai 換成 `thinking.type=adaptive` 與 `output_config.effort`。
    - Anthropic 接口、其餘的 Claude（Sonnet 4.5、Haiku 4.5 這類）：不送。官方不收
      `output_config.effort`；統一設定的中、高是 `budget_tokens` 10000 / 16384，大過每次的
      `max_tokens`。不送就與加這一格之前一樣（code-review 追加，偏離票的字面）。
    - Anthropic 接口、不是 Claude：統一設定會變成 DeepSeek 忽略的 `budget_tokens`、關則省略（模型
      照樣思考），所以明寫 effort。「關」只對 DeepSeek（`_TAKES_THINKING_OFF`）明寫
      `thinking: disabled`；認不得的閘道關就不送，送了不收的會 400，而設定頁沒有「不送」一級。
      低、中、高不收的也會 400，停下的說明指到設定頁、說選關就不送。
    - OpenAI 接口：profile 認得會推理（`supports_thinking`）才送統一設定（`reasoning_effort`）。
      Berth 用的是 `OpenAIProvider`，`deepseek-flash`、`gpt-4o-mini`、自訂名字都認不得。
    """
    if endpoint.provider is AiProvider.ANTHROPIC:
        if profile.get("anthropic_supports_effort", False):
            return _Send.UNIFIED
        if endpoint.model.startswith("claude-"):
            return _Send.NOTHING
        host = urlsplit(effective_base_url(endpoint.provider, endpoint.base_url)).hostname
        return _Send.EXPLICIT if host in _TAKES_THINKING_OFF else _Send.EFFORT_ONLY
    return _Send.UNIFIED if profile.get("supports_thinking", False) else _Send.NOTHING


@dataclass(frozen=True, slots=True)
class ReasoningSupport:
    """設定頁與停下的說明要知道的：這個端點上的這個模型，推理程度怎麼送（M5.5 票 17、17b）。"""

    #: 至少有一級會送。假的是四級都不送，設定頁說這個模型的程度沒有效果。
    applies: bool
    #: 低、中、高照送，「關」什麼都不送（認不得的 Anthropic 相容閘道）。
    off_sends_nothing: bool


def reasoning_support(provider: AiProvider, base_url: str, model: str) -> ReasoningSupport:
    """只看 profile 與網址：不連外，key 是佔位的。"""
    endpoint = AiEndpoint(provider, base_url, "unused", model)
    how = _how_to_send(endpoint, build_model(endpoint).profile)
    return ReasoningSupport(how is not _Send.NOTHING, how is _Send.EFFORT_ONLY)


def _reasoning(endpoint: AiEndpoint, model: Model) -> ModelSettings:
    """推理程度變成這次請求的參數（怎麼送見 `_how_to_send`）。"""
    level = endpoint.reasoning
    how = _how_to_send(endpoint, model.profile)
    if how is _Send.UNIFIED:
        return {"thinking": _THINKING[level]}
    if how is _Send.NOTHING or (how is _Send.EFFORT_ONLY and level is AiReasoning.OFF):
        return {}
    if level is AiReasoning.OFF:
        off: AnthropicModelSettings = {"anthropic_thinking": {"type": "disabled"}}
        return off
    effort: AnthropicModelSettings = {"anthropic_effort": _EFFORT[level]}
    return effort


def chat_settings(endpoint: AiEndpoint, model: Model, max_tokens: int) -> ModelSettings:
    """側面板（與壓縮）每一次模型呼叫的設定：輸出上限、推理程度（`_reasoning`），與 Anthropic 的
    快取標記（M5 票 11）。`model` 是照 `endpoint` 組的那一個，推理參數看它的 profile。

    Anthropic 明寫 `cache_control`（instructions、工具定義、最後一則訊息各一個）：自架閘道不一定吃
    頂層的自動快取；prototype 實測命中 46–98%（brief §20.24）。Chat Completions 的快取由服務自己做。
    """
    settings: ModelSettings = {"max_tokens": max_tokens}
    settings.update(_reasoning(endpoint, model))
    if endpoint.provider is AiProvider.ANTHROPIC:
        cache: AnthropicModelSettings = {
            "anthropic_cache_instructions": "5m",
            "anthropic_cache_tool_definitions": "5m",
            "anthropic_cache_messages": "5m",
        }
        settings.update(cache)
    return settings
