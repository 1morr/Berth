"""`ChatProvider` 的替身（plan §1.3：每個 adapter 一個 Fake）。

每一次 `stream` 照順序取下一個回覆：一個 `TurnEnded`（文字先拆成一個 `TextDelta` 送出）、一個
`AiProviderError`（拋出去），或一個收請求、回這兩者之一的函式（要看請求才答得出的，例如照抄
nonce）。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field

from berth.adapters.ai import (
    AiProviderError,
    ChatRequest,
    StreamEvent,
    TextDelta,
    ToolCallStarted,
    TurnEnded,
)

Reply = TurnEnded | AiProviderError | Callable[[ChatRequest], TurnEnded | AiProviderError]


@dataclass
class FakeChatProvider:
    replies: list[Reply] = field(default_factory=list)
    models: list[str] | None = None
    #: 收到的每一個請求，照順序。
    requests: list[ChatRequest] = field(default_factory=list)
    host: str = "ai.invalid"

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        self.requests.append(request)
        if not self.replies:
            raise AssertionError(f"no scripted reply for request {len(self.requests)}")
        reply = self.replies.pop(0)
        answer = reply(request) if callable(reply) else reply
        if isinstance(answer, AiProviderError):
            raise answer
        if answer.reply.text:
            yield TextDelta(answer.reply.text)
        for call in answer.reply.tool_calls:
            yield ToolCallStarted(id=call.id, name=call.name)
        yield answer

    async def list_models(self) -> list[str] | None:
        return self.models
