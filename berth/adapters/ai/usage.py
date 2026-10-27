"""一次模型呼叫用了多少 token，照兩種接口各自報得出的那幾格（M5 票 11、研究 C5）。

pydantic-ai 的 `RequestUsage` 把沒報的格子填 0，分不出「0」與「不知道」；這裡照接口的規格決定哪一格
是不知道（`None`），記帳與用量頁照它顯示，不把不知道當 0（研究 C5）。

`input` 一律**含**快取讀寫：pydantic-ai 把 Anthropic 的三格加總成 `input_tokens`（brief §20.24），
Chat Completions 的 `prompt_tokens` 本來就含快取命中的部分。
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_ai.messages import ModelResponse, NativeToolCallPart
from pydantic_ai.usage import RequestUsage

from berth.domain import AiProvider


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input: int
    output: int
    #: 命中快取讀進來的 input；`None` 是接口沒報。
    cache_read: int | None
    #: 寫進快取的 input；`None` 是接口沒報。
    cache_write: int | None


def usage_of(provider: AiProvider, usage: RequestUsage) -> TokenUsage:
    """Anthropic Messages 每次都報快取讀與寫；Chat Completions 只有讀
    （`prompt_tokens_details.cached_tokens`），沒有寫這一格。

    已知的缺口：Chat Completions 的服務不報快取讀時，pydantic-ai 填的 0 分不出來，照 0 記。
    """
    if provider is AiProvider.ANTHROPIC:
        return TokenUsage(
            usage.input_tokens,
            usage.output_tokens,
            usage.cache_read_tokens,
            usage.cache_write_tokens,
        )
    return TokenUsage(usage.input_tokens, usage.output_tokens, usage.cache_read_tokens, None)


#: 伺服器端網搜的工具名（Anthropic Messages；DeepSeek 的相容端點同名）。
WEB_SEARCH = "web_search"


def web_searches_of(response: ModelResponse) -> int:
    """這一次模型呼叫裡伺服器端搜了幾次（M5 票 17）。

    服務報的 `usage.server_tool_use.web_search_requests`（pydantic-ai 放在
    `details['web_search_requests']`，0 次時不放）是計費的那個數，有就照它；沒報的照回應裡
    `web_search` 的呼叫數（自架閘道不一定報，替身的串流也報不出來）。
    """
    reported = response.usage.details.get("web_search_requests", 0)
    if reported:
        return reported
    return sum(
        1
        for part in response.parts
        if isinstance(part, NativeToolCallPart) and part.tool_name == WEB_SEARCH
    )
