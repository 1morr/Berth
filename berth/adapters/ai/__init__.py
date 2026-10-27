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
from dataclasses import dataclass

import httpx2
from pydantic_ai import ModelRequest
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
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from berth.domain import AiProbeFailure, AiProvider

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
    """組一個模型要的四樣東西。`base_url` 空的是官方端點。"""

    provider: AiProvider
    base_url: str
    api_key: str
    model: str


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


def build_model(endpoint: AiEndpoint, *, http_client: httpx2.AsyncClient | None = None) -> Model:
    """照設定組出模型物件。`http_client` 給測試換 transport；正式環境用 SDK 自己的。"""
    base_url = (
        normalize_base_url(endpoint.provider, endpoint.base_url)
        or (OFFICIAL_BASE_URL[endpoint.provider])
    )
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


def chat_settings(provider: AiProvider, max_tokens: int) -> ModelSettings:
    """側面板每一次模型呼叫的設定（M5 票 11）：輸出上限，與 Anthropic 的快取標記。

    Anthropic 明寫 `cache_control`（instructions、工具定義、最後一則訊息各一個）：自架閘道不一定吃
    頂層的自動快取；prototype 實測命中 46–98%（brief §20.24）。Chat Completions 的快取由服務自己做。
    """
    if provider is AiProvider.ANTHROPIC:
        anthropic: AnthropicModelSettings = {
            "max_tokens": max_tokens,
            "anthropic_cache_instructions": "5m",
            "anthropic_cache_tool_definitions": "5m",
            "anthropic_cache_messages": "5m",
        }
        return anthropic
    return {"max_tokens": max_tokens}
