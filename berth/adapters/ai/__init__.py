"""AI provider 的共同介面（plan §11.6〈provider〉、brief §20.24、研究 ai-providers.md 結論 3）。

對話核心（M5 側面板、M6 背景任務、M7 Discord）只看這裡的型別：訊息、工具、串流事件、`Usage`、
`AiProviderError`。每一種 API 格式一個 adapter 負責轉換（`anthropic.py`；OpenAI 相容在票 09）。

轉換時要守的幾條（研究結論 3）：

- 一輪可以有好幾個 `ToolCall`；結果收成**一個** `UserTurn`。
- `ToolCall.arguments` 是模型給的 JSON 原文，解析與驗證交給呼叫端。
- 工具失敗的原因一定寫進 `ToolResult.content`：有的格式沒有 `is_error`。
- `TurnEnded` 只在串流正常結束時發；沒結束就斷掉是 `AiProviderError`，帶著斷掉前已知的 `Usage`。
- 不認得的事件與欄位一律略過。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from berth.adapters.http import ServiceError
from berth.domain import AiFailure, ApiFormat


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """一個工具的定義。名字用兩種格式命名規則的交集：小寫 snake_case、短。"""

    name: str
    description: str
    #: JSON Schema，`type: object`。
    input_schema: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class TextPart:
    text: str


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    #: 模型給的 JSON 原文（沒給參數是空字串）。
    arguments: str


@dataclass(frozen=True, slots=True)
class ToolResult:
    call_id: str
    #: JSON 文字。錯誤也寫在這裡，`is_error` 只是附帶。
    content: str
    is_error: bool = False


@dataclass(frozen=True, slots=True)
class OpaquePart:
    """provider 要求原樣帶回下一輪、Berth 不讀的東西（Anthropic 的 thinking block）。"""

    format: ApiFormat
    raw: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class UserTurn:
    parts: tuple[TextPart | ToolResult, ...]


@dataclass(frozen=True, slots=True)
class ModelTurn:
    """模型的那一輪。不叫 Assistant：那是 CONTEXT.md 的「助理」。"""

    parts: tuple[TextPart | ToolCall | OpaquePart, ...]

    @property
    def text(self) -> str:
        return "".join(part.text for part in self.parts if isinstance(part, TextPart))

    @property
    def tool_calls(self) -> tuple[ToolCall, ...]:
        return tuple(part for part in self.parts if isinstance(part, ToolCall))


@dataclass(frozen=True, slots=True)
class ChatRequest:
    model: str
    #: 只放固定的字（研究結論 6：快取吃前綴）。空字串是不送。
    system: str
    #: 空的是只能聊天：請求不帶 `tools`。
    tools: tuple[ToolSpec, ...]
    turns: tuple[UserTurn | ModelTurn, ...]
    max_output_tokens: int


@dataclass(frozen=True, slots=True)
class TextDelta:
    text: str


@dataclass(frozen=True, slots=True)
class ToolCallStarted:
    """模型開始呼叫一個工具（側面板的「正在查……」）。"""

    id: str
    name: str


class StopReason(StrEnum):
    END = "end"
    TOOL_CALLS = "tool_calls"
    MAX_TOKENS = "max_tokens"
    #: 輸入加輸出超過模型的 context window。
    CONTEXT_FULL = "context_full"
    REFUSED = "refused"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class Usage:
    """一次呼叫的 tokens。**`None` 是不知道，不是 0**：provider 沒回那一格。"""

    #: 全部輸入，含快取寫入與讀取。
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_write_tokens: int | None = None
    cache_read_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class TurnEnded:
    stop: StopReason
    #: provider 給的原值（`end_turn`、`tool_use`…），`OTHER` 時靠它說明。
    stop_raw: str
    #: 這一輪完整的回覆，含拼好的 `ToolCall`。
    reply: ModelTurn
    usage: Usage


@dataclass(frozen=True, slots=True)
class UsageReported:
    """串流途中已經知道的 tokens（Anthropic 的 `message_start` 就給了輸入）。

    串流沒講完就被取消時，呼叫端靠最後一個記用量：已經送出的輸入照樣花掉了。沒講完的輸出是
    `None`。最後的數字在 `TurnEnded.usage`。
    """

    usage: Usage


StreamEvent = TextDelta | ToolCallStarted | UsageReported | TurnEnded


class AiProviderError(ServiceError):
    """對 provider 的一次請求沒成。`failure` 決定下一步，`detail` 是原文（給技術細節與 log）。"""

    def __init__(
        self,
        failure: AiFailure,
        detail: str,
        *,
        retry_after: float | None = None,
        usage: Usage | None = None,
    ) -> None:
        super().__init__(detail)
        self.failure = failure
        self.detail = str(self)
        #: 限流時 provider 說的「幾秒後再來」。
        self.retry_after = retry_after
        #: 斷掉之前已經知道的 tokens（串流中途斷掉時 `ai_calls` 照樣記）。
        self.usage = usage or Usage()


@dataclass(frozen=True, slots=True)
class ModelInfo:
    id: str
    #: 模型吃得下的輸入 tokens。`None` 是端點沒說（壓縮時用設定或保守預設，plan §11.6）。
    context_window: int | None = None


@dataclass(frozen=True, slots=True)
class Endpoint:
    """要打的那一台：格式、base URL（空的是官方）、key（自架的可以沒有）。"""

    format: ApiFormat
    base_url: str = ""
    api_key: str = field(default="", repr=False)


class ChatProvider(Protocol):
    @property
    def host(self) -> str:
        """實際打到的主機（`ai_calls.host`）：base URL 的 `host[:port]`，空的是官方那一台。"""
        ...

    def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        """送一輪、串流回來。最後一個事件一定是 `TurnEnded`；沒成是 `AiProviderError`。"""
        ...

    async def list_models(self) -> list[ModelInfo] | None:
        """端點列得出的模型。`None` 是端點沒有這一支或讀不懂，設定頁退回手填。

        憑證不對、連不上這類有下一步的失敗照樣是 `AiProviderError`。
        """
        ...


__all__ = [
    "AiProviderError",
    "ChatProvider",
    "ChatRequest",
    "Endpoint",
    "ModelInfo",
    "ModelTurn",
    "OpaquePart",
    "StopReason",
    "StreamEvent",
    "TextDelta",
    "TextPart",
    "ToolCall",
    "ToolCallStarted",
    "ToolResult",
    "ToolSpec",
    "TurnEnded",
    "Usage",
    "UsageReported",
    "UserTurn",
]
