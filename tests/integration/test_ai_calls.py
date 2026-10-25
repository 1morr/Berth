"""`call_model` 的用量記錄（M5 票 08、plan §11.6〈用量記錄〉）：成與不成都一列。

假端點用 respx、adapter 用真的 `AnthropicProvider`：串流斷在哪裡、已經知道哪幾格 tokens，要從
真的事件順序看。
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.ai import ChatRequest, Endpoint, TextPart, UserTurn
from berth.adapters.ai.anthropic import AnthropicProvider
from berth.domain import AiCallOrigin, AiFailure, ApiFormat
from berth.models import AiCall
from berth.services.ai_calls import call_model

pytestmark = pytest.mark.asyncio

OFFICIAL = "https://api.anthropic.com/v1/messages"
HELLO = ChatRequest(
    model="claude-opus-5-5",
    system="",
    tools=(),
    turns=(UserTurn((TextPart("Say ok"),)),),
    max_output_tokens=64,
)


def _event(name: str, data: dict[str, object]) -> bytes:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n".encode()


class _HangsAfterStart(httpx.AsyncByteStream):
    """送完 `message_start` 就停住：模型還在想，使用者這時候關掉了。"""

    def __init__(self, started: asyncio.Event) -> None:
        self._started = started

    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield _event(
            "message_start",
            {
                "type": "message_start",
                "message": {
                    "id": "msg_1",
                    "role": "assistant",
                    "content": [],
                    "usage": {
                        "input_tokens": 40,
                        "output_tokens": 1,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 900,
                    },
                },
            },
        )
        self._started.set()
        await asyncio.Event().wait()


@respx.mock
async def test_a_stream_cancelled_halfway_still_logs_the_input_it_spent(
    session: AsyncSession,
) -> None:
    started = asyncio.Event()
    respx.post(OFFICIAL).mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=_HangsAfterStart(started),
        )
    )
    provider = AnthropicProvider(Endpoint(format=ApiFormat.ANTHROPIC, api_key="sk-test"))
    call = asyncio.create_task(
        call_model(
            session,
            provider,
            HELLO,
            format=ApiFormat.ANTHROPIC,
            origin=AiCallOrigin.TEST,
            user_id=None,
        )
    )
    await asyncio.wait_for(started.wait(), timeout=5)
    await asyncio.sleep(0)

    call.cancel()
    with pytest.raises(asyncio.CancelledError):
        await call

    row = (await session.scalars(select(AiCall))).one()
    assert row.failure is AiFailure.CANCELLED
    assert (row.input_tokens, row.cache_read_tokens, row.cache_write_tokens) == (940, 900, 0)
    # 輸出還沒講完：不知道，不是 1。
    assert row.output_tokens is None
    assert row.host == "api.anthropic.com"


async def test_a_call_cancelled_before_anything_came_back_is_still_a_row(
    session: AsyncSession,
) -> None:
    class Silent:
        host = "ai.invalid"

        async def stream(self, request: ChatRequest) -> AsyncIterator[object]:
            await asyncio.Event().wait()
            yield None  # pragma: no cover

        async def list_models(self) -> None:  # pragma: no cover
            return None

    call = asyncio.create_task(
        call_model(
            session,
            Silent(),  # type: ignore[arg-type]  # 只用到 host 與 stream
            HELLO,
            format=ApiFormat.ANTHROPIC,
            origin=AiCallOrigin.TEST,
            user_id=None,
        )
    )
    await asyncio.sleep(0.01)
    call.cancel()
    with pytest.raises(asyncio.CancelledError):
        await call

    row = (await session.scalars(select(AiCall))).one()
    assert row.failure is AiFailure.CANCELLED
    assert (row.input_tokens, row.output_tokens) == (None, None)
