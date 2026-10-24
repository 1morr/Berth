"""設定頁的測試探針的邊角（M5 票 07、研究 ai-providers.md 結論 4），用 `FakeChatProvider`。

假端點那一層（respx、真的 adapter）在 `test_ai_settings_api.py`；這裡驗只看得到回覆內容的判定。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.ai import (
    ChatRequest,
    ModelTurn,
    StopReason,
    StreamEvent,
    TextPart,
    ToolCall,
    ToolResult,
    TurnEnded,
    Usage,
    UserTurn,
)
from berth.adapters.ai.fake import FakeChatProvider
from berth.domain import ApiFormat, Role, ToolGap
from berth.models import User
from berth.services.ai import read_ai, run_ai_test, set_ai
from tests.integration.factories import FakeClientFactory

pytestmark = pytest.mark.asyncio


def says(text: str) -> TurnEnded:
    return TurnEnded(
        stop=StopReason.END, stop_raw="end_turn", reply=ModelTurn((TextPart(text),)), usage=Usage()
    )


def nonce_in(request: ChatRequest) -> str:
    turn = request.turns[-1]
    assert isinstance(turn, UserTurn)
    part = turn.parts[0]
    assert isinstance(part, TextPart)
    return part.text.split('"')[1]


def echoes(times: int) -> Callable[[ChatRequest], TurnEnded]:
    def answer(request: ChatRequest) -> TurnEnded:
        arguments = json.dumps({"nonce": nonce_in(request)})
        calls = tuple(
            ToolCall(id=f"call_{i}", name="berth_echo", arguments=arguments) for i in range(times)
        )
        return TurnEnded(
            stop=StopReason.TOOL_CALLS, stop_raw="tool_use", reply=ModelTurn(calls), usage=Usage()
        )

    return answer


async def ready(session: AsyncSession) -> int:
    user = User(jellyfin_user_id="jf-1", name="skipper", role=Role.ADMIN)
    session.add(user)
    await session.flush()
    await set_ai(session, format=ApiFormat.ANTHROPIC, base_url="", model="", api_key="sk-test")
    return user.id


async def test_two_parallel_calls_each_get_a_result_and_count_as_supported(
    session: AsyncSession,
) -> None:
    provider = FakeChatProvider(replies=[says("ok"), echoes(2), says("Got both.")])
    user_id = await ready(session)

    result = await run_ai_test(session, FakeClientFactory(ai=provider), user_id=user_id)

    assert result.tools is not None
    assert result.tools.supported is True
    last = provider.requests[-1].turns[-1]
    assert isinstance(last, UserTurn)
    assert [part.call_id for part in last.parts if isinstance(part, ToolResult)] == [
        "call_0",
        "call_1",
    ]


async def test_no_text_after_the_tool_result_is_chat_only(session: AsyncSession) -> None:
    provider = FakeChatProvider(replies=[says("ok"), echoes(1), says("")])
    user_id = await ready(session)

    result = await run_ai_test(session, FakeClientFactory(ai=provider), user_id=user_id)

    assert result.tools is not None
    assert result.tools.gap is ToolGap.NO_REPLY


async def test_calling_another_tool_after_the_result_is_still_no_reply(
    session: AsyncSession,
) -> None:
    """第三步又呼叫一次只在名字與 nonce 都對時算數（M5 票 16）；呼叫別的就是沒好好回。"""
    wrong = TurnEnded(
        stop=StopReason.TOOL_CALLS,
        stop_raw="tool_use",
        reply=ModelTurn((ToolCall(id="call_9", name="something_else", arguments="{}"),)),
        usage=Usage(),
    )
    provider = FakeChatProvider(replies=[says("ok"), echoes(1), wrong])
    user_id = await ready(session)

    result = await run_ai_test(session, FakeClientFactory(ai=provider), user_id=user_id)

    assert result.tools is not None
    assert result.tools.gap is ToolGap.NO_REPLY


@dataclass
class SwitchesModelMidTest(FakeChatProvider):
    """第二次請求送出之前，管理員在另一個分頁換了模型：探針已經讀過設定了。"""

    session: AsyncSession | None = None

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        if request.tools and self.session is not None:
            await set_ai(
                self.session,
                format=ApiFormat.ANTHROPIC,
                base_url="",
                model="claude-haiku-5-5",
                api_key=None,
            )
        async for event in super().stream(request):
            yield event


async def test_a_result_for_settings_changed_mid_test_is_not_stored(session: AsyncSession) -> None:
    """結論說的是舊的那一個模型，不存（存了就會把新模型標成測過）。"""
    user_id = await ready(session)
    provider = SwitchesModelMidTest(
        replies=[says("ok"), says("I won't call tools.")], session=session
    )

    result = await run_ai_test(session, FakeClientFactory(ai=provider), user_id=user_id)

    assert result.tools is not None
    assert result.tools.supported is False
    assert (await read_ai(session)).tool_test is None


def replies_with(template: str) -> Callable[[ChatRequest], TurnEnded]:
    return lambda request: says(template.format(nonce=nonce_in(request)))


@pytest.mark.parametrize(
    ("template", "gap"),
    [
        # 端點忽略了工具，模型只是在回話裡提到它（提示本身就有工具名與 nonce）。
        ("I can't call berth_echo here, but the nonce was {nonce}.", ToolGap.TOOLS_IGNORED),
        ("Sure, I called berth_echo.", ToolGap.TOOLS_IGNORED),
        # 端點沒有把模型輸出的呼叫解析出來：vLLM 沒開 `--tool-call-parser` 時的幾種樣子。
        (
            '<tool_call>\n{{"name": "berth_echo", "arguments": {{"nonce": "{nonce}"}}}}'
            "\n</tool_call>",
            ToolGap.WRITTEN_AS_TEXT,
        ),
        ('{{"name": "berth_echo", "parameters": {{"nonce": "{nonce}"}}}}', ToolGap.WRITTEN_AS_TEXT),
        (
            '[TOOL_CALLS] [{{"name":"berth_echo","arguments":{{"nonce":"{nonce}"}}}}]',
            ToolGap.WRITTEN_AS_TEXT,
        ),
        ('berth_echo(nonce="{nonce}")', ToolGap.WRITTEN_AS_TEXT),
    ],
)
async def test_mentioning_the_tool_is_not_the_same_as_writing_the_call(
    session: AsyncSession, template: str, gap: ToolGap
) -> None:
    provider = FakeChatProvider(replies=[says("ok"), replies_with(template)])
    user_id = await ready(session)

    result = await run_ai_test(session, FakeClientFactory(ai=provider), user_id=user_id)

    assert result.tools is not None
    assert result.tools.gap is gap
