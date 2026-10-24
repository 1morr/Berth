"""格式 → adapter 與官方端點的預設模型（plan §11.6〈provider〉）。加一種格式只改這張表與
`ApiFormat`；`tests/unit/test_ai_formats.py` 守著每一種格式都在表上。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from berth.adapters.ai import ChatProvider, Endpoint, anthropic, openai
from berth.domain import ApiFormat


@dataclass(frozen=True, slots=True)
class Format:
    provider: Callable[[Endpoint], ChatProvider]
    #: base URL 留空（官方端點）、模型也留空時用的那一個。`None` 是一定要選或填：第三方會把
    #: 別家的模型名映射成自己的模型（研究結論 5），OpenAI 官方沒有一個「先用這個」的建議。
    official_model: str | None


FORMATS: Mapping[ApiFormat, Format] = {
    ApiFormat.ANTHROPIC: Format(anthropic.AnthropicProvider, anthropic.DEFAULT_MODEL),
    ApiFormat.OPENAI: Format(openai.OpenAiProvider, None),
}


def provider_for(endpoint: Endpoint) -> ChatProvider:
    return FORMATS[endpoint.format].provider(endpoint)


def official_model(format: ApiFormat) -> str | None:
    return FORMATS[format].official_model


def official_models() -> dict[ApiFormat, str | None]:
    """每一種格式各自的那一個（設定頁照草稿裡的格式說「留空用哪一個」）。"""
    return {format: spec.official_model for format, spec in FORMATS.items()}
