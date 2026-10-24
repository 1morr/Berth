"""助理的對話核心（M5 票 08，plan §11.6〈對話核心〉），用 `FakeChatProvider` 與真的資料庫。

從核心的介面進去：`AssistantRuns.send` 送一句、讀它的事件；存下來的從 `read_conversation`
讀回。provider 收到什麼看 `FakeChatProvider.requests`（那是 provider 的邊界，不是內部）。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from berth.adapters.ai import (
    AiProviderError,
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
from berth.db import create_session_factory
from berth.domain import (
    AiCallOrigin,
    AiFailure,
    ApiFormat,
    AssistantNotice,
    AssistantRefusal,
    Language,
    Role,
    ToolOutcome,
)
from berth.models import AiCall, AiSettings, AiToolTest, User
from berth.services.ai import set_ai
from berth.services.assistant import (
    MAX_TOOL_ROUNDS,
    AssistantEvent,
    AssistantRuns,
    Finished,
    NoticeRaised,
    ReplyText,
    Started,
    ToolFinished,
    ToolStarted,
)
from berth.services.auth import AuthenticatedUser
from berth.services.commands import Effect, command
from berth.services.conversations import (
    AssistantRefusedError,
    ModelText,
    NoticePart,
    ToolResultPart,
    UserText,
    assistant_status,
    list_conversations,
    read_conversation,
)
from berth.services.registry import Registry, Tool, ToolContext
from berth.services.settings import update_settings
from berth.services.tools import REGISTRY
from tests.integration.factories import FakeClientFactory

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)


def says(text: str, usage: Usage | None = None) -> TurnEnded:
    return TurnEnded(
        stop=StopReason.END,
        stop_raw="end_turn",
        reply=ModelTurn((TextPart(text),)),
        usage=usage or Usage(input_tokens=10, output_tokens=2),
    )


def calls(*names: str, text: str = "") -> TurnEnded:
    parts: list[TextPart | ToolCall] = [TextPart(text)] if text else []
    parts += [ToolCall(id=f"call_{i}", name=name, arguments="{}") for i, name in enumerate(names)]
    return TurnEnded(
        stop=StopReason.TOOL_CALLS,
        stop_raw="tool_use",
        reply=ModelTurn(tuple(parts)),
        usage=Usage(input_tokens=10, output_tokens=2),
    )


# --- 一個只在這裡登記的工具：它指著一般使用者也進得去的端點 -----------------------


class Nothing(BaseModel):
    pass


class Pong(BaseModel):
    said: str


@command(Effect.READ)
async def ping() -> str:
    return "pong"


async def _ping(context: ToolContext, given: Nothing) -> Pong:
    return Pong(said=await ping())


PING = Tool(
    name="ping",
    description="Answer pong.",
    input=Nothing,
    result=Pong,
    command=ping,
    route=("GET", "/health"),
    run=_ping,
)


# --- 準備 -----------------------------------------------------------------------


async def person(session: AsyncSession, name: str, role: Role) -> AuthenticatedUser:
    user = User(jellyfin_user_id=f"jf-{name}", name=name, role=role)
    session.add(user)
    await session.commit()
    return AuthenticatedUser(id=user.id, name=name, role=role, jellyfin_user_id=f"jf-{name}")


async def ai_ready(session: AsyncSession) -> None:
    await set_ai(session, format=ApiFormat.ANTHROPIC, base_url="", model="", api_key="sk-test")
    await session.commit()


def runs_for(
    engine: AsyncEngine, provider: FakeChatProvider, registry: Registry | None = None
) -> tuple[AssistantRuns, async_sessionmaker[AsyncSession]]:
    sessions = create_session_factory(engine)
    runs = AssistantRuns(
        sessions, FakeClientFactory(ai=provider), registry=registry or REGISTRY, now=lambda: NOW
    )
    return runs, sessions


async def drain(
    runs: AssistantRuns,
    user: AuthenticatedUser,
    text: str,
    conversation_id: int | None = None,
) -> list[AssistantEvent]:
    reply = await runs.send(
        user=user, text=text, language=Language.EN, conversation_id=conversation_id
    )
    return [event async for event in reply.events]


def started_id(events: list[AssistantEvent]) -> int:
    started = events[0]
    assert isinstance(started, Started)
    return started.conversation_id


# --- 一則對話送出、串流回來、存起來 ------------------------------------------------


async def test_a_message_streams_back_and_is_still_there_when_read_again(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    admin = await person(session, "skipper", Role.ADMIN)
    await ai_ready(session)
    runs, sessions = runs_for(engine, FakeChatProvider(replies=[says("Hello there.")]))

    events = await drain(runs, admin, "hi")

    started = events[0]
    assert isinstance(started, Started)
    assert events[1:] == [ReplyText("Hello there."), Finished()]
    async with sessions() as fresh:
        view = await read_conversation(
            fresh, user_id=admin.id, conversation_id=started.conversation_id
        )
    assert [message.parts for message in view.messages] == [
        [UserText(text="hi")],
        [ModelText(text="Hello there.")],
    ]
    assert view.title == "hi"


async def test_the_next_message_carries_the_conversation_so_far(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    admin = await person(session, "skipper", Role.ADMIN)
    await ai_ready(session)
    provider = FakeChatProvider(replies=[says("Hello."), says("Still here.")])
    runs, _ = runs_for(engine, provider)

    first = await drain(runs, admin, "hi")
    started = first[0]
    assert isinstance(started, Started)
    await drain(runs, admin, "again", conversation_id=started.conversation_id)

    assert provider.requests[1].turns == (
        UserTurn((TextPart("hi"),)),
        ModelTurn((TextPart("Hello."),)),
        UserTurn((TextPart("again"),)),
    )


async def test_the_reply_is_in_the_interface_language(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    admin = await person(session, "skipper", Role.ADMIN)
    await ai_ready(session)
    provider = FakeChatProvider(replies=[says("好。")])
    runs, _ = runs_for(engine, provider)

    reply = await runs.send(user=admin, text="嗨", language=Language.ZH_HANT)
    [event async for event in reply.events]

    assert "Reply in Traditional Chinese (zh-Hant)." in provider.requests[0].system
    # 使用者的話只在訊息裡，不進 system（快取吃固定的前綴）。
    assert "嗨" not in provider.requests[0].system


# --- 工具迴圈 -----------------------------------------------------------------------


async def test_a_tool_call_runs_and_its_result_goes_back_as_data_with_its_source(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    admin = await person(session, "skipper", Role.ADMIN)
    await ai_ready(session)
    provider = FakeChatProvider(replies=[calls("ping"), says("It said pong.")])
    runs, sessions = runs_for(engine, provider, Registry((PING,)))

    events = await drain(runs, admin, "ping it")

    assert events[1:] == [
        ToolStarted(call_id="call_0", name="ping"),
        ToolFinished(call_id="call_0", name="ping", outcome=ToolOutcome.DONE),
        ReplyText("It said pong."),
        Finished(),
    ]
    sent_back = provider.requests[1].turns[-1]
    assert sent_back == UserTurn(
        (
            ToolResult(
                "call_0",
                '{"result": {"said": "pong"}, "source": "berth", "status": "done", "tool": "ping"}',
            ),
        )
    )
    async with sessions() as fresh:
        view = await read_conversation(fresh, user_id=admin.id, conversation_id=started_id(events))
    assert view.messages[2].parts == [
        ToolResultPart(
            call_id="call_0",
            tool="ping",
            outcome=ToolOutcome.DONE,
            result_type="Pong",
            result={"said": "pong"},
        )
    ]


async def test_a_tool_outside_the_list_is_refused_and_the_model_hears_why(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    admin = await person(session, "skipper", Role.ADMIN)
    await ai_ready(session)
    provider = FakeChatProvider(replies=[calls("delete_everything"), says("I can't.")])
    runs, _ = runs_for(engine, provider, Registry((PING,)))

    events = await drain(runs, admin, "do it")

    assert (
        ToolFinished(call_id="call_0", name="delete_everything", outcome=ToolOutcome.REFUSED)
        in events
    )
    result = provider.requests[1].turns[-1].parts[0]
    assert isinstance(result, ToolResult)
    assert result.is_error
    assert '"reason": "unknown_tool"' in result.content


async def test_a_model_that_keeps_calling_tools_stops_at_the_round_limit_and_says_so(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    admin = await person(session, "skipper", Role.ADMIN)
    await ai_ready(session)
    provider = FakeChatProvider(replies=[calls("ping") for _ in range(MAX_TOOL_ROUNDS + 5)])
    runs, sessions = runs_for(engine, provider, Registry((PING,)))

    events = await drain(runs, admin, "loop forever")

    assert len(provider.requests) == MAX_TOOL_ROUNDS == 10
    notice = NoticePart(notice=AssistantNotice.ROUND_LIMIT)
    assert events[-2:] == [NoticeRaised(notice), Finished()]
    async with sessions() as fresh:
        view = await read_conversation(fresh, user_id=admin.id, conversation_id=started_id(events))
    assert view.messages[-1].parts == [notice]


# --- provider 沒成 ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("failure", "retry_after"),
    [
        (AiFailure.RATE_LIMITED, 30.0),
        (AiFailure.PROVIDER_DOWN, None),
        (AiFailure.AUTH_FAILED, None),
        (AiFailure.QUOTA_EXHAUSTED, None),
    ],
)
async def test_a_provider_failure_is_told_with_its_kind_and_kept(
    engine: AsyncEngine, session: AsyncSession, failure: AiFailure, retry_after: float | None
) -> None:
    admin = await person(session, "skipper", Role.ADMIN)
    await ai_ready(session)
    error = AiProviderError(failure, "429 rate_limit_error", retry_after=retry_after)
    runs, sessions = runs_for(engine, FakeChatProvider(replies=[error]))

    events = await drain(runs, admin, "hi")

    notice = NoticePart(
        notice=AssistantNotice.PROVIDER_FAILED, failure=failure, retry_after=retry_after
    )
    assert events[1:] == [NoticeRaised(notice), Finished()]
    async with sessions() as fresh:
        view = await read_conversation(fresh, user_id=admin.id, conversation_id=started_id(events))
    assert view.messages[-1].parts == [notice]


async def test_a_message_after_a_failure_still_reaches_the_model(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    """說給人聽的 notice 不送；失敗前後兩句話併成同一輪。"""
    admin = await person(session, "skipper", Role.ADMIN)
    await ai_ready(session)
    provider = FakeChatProvider(
        replies=[AiProviderError(AiFailure.PROVIDER_DOWN, "529 overloaded"), says("Back.")]
    )
    runs, _ = runs_for(engine, provider)

    first = await drain(runs, admin, "hi")
    await drain(runs, admin, "again", conversation_id=started_id(first))

    assert provider.requests[1].turns == (UserTurn((TextPart("hi"), TextPart("again"))),)


async def test_every_call_is_recorded_against_the_conversation(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    admin = await person(session, "skipper", Role.ADMIN)
    await ai_ready(session)
    provider = FakeChatProvider(
        replies=[calls("ping"), AiProviderError(AiFailure.RATE_LIMITED, "429")]
    )
    runs, sessions = runs_for(engine, provider, Registry((PING,)))

    events = await drain(runs, admin, "hi")

    async with sessions() as fresh:
        rows = list(await fresh.scalars(select(AiCall).order_by(AiCall.id)))
    assert [(row.origin, row.conversation_id, row.user_id, row.failure) for row in rows] == [
        (AiCallOrigin.CONVERSATION, started_id(events), admin.id, None),
        (AiCallOrigin.CONVERSATION, started_id(events), admin.id, AiFailure.RATE_LIMITED),
    ]


# --- 誰拿得到什麼 -------------------------------------------------------------------


async def test_a_user_gets_no_admin_tools_and_an_admin_does(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    """登錄表依角色過濾（plan §11.6）：`recent_imports` 指著只有管理員進得去的 `/weekly`。"""
    admin = await person(session, "skipper", Role.ADMIN)
    deckhand = await person(session, "deckhand", Role.USER)
    await ai_ready(session)
    provider = FakeChatProvider(replies=[says("ok"), says("ok")])
    runs, _ = runs_for(engine, provider)

    await drain(runs, admin, "what's new")
    await drain(runs, deckhand, "what's new")

    admin_tools = {tool.name for tool in provider.requests[0].tools}
    deckhand_tools = {tool.name for tool in provider.requests[1].tools}
    assert "recent_imports" in admin_tools
    assert deckhand_tools == set()
    # 沒有工具的那一份 system 也這麼說，模型才不會假裝去查。
    assert "You have no tools" in provider.requests[1].system


async def test_a_user_who_names_an_admin_tool_is_still_refused(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    """清單上沒有不夠：模型照樣叫得出名字，`invoke` 要再擋一次。"""
    deckhand = await person(session, "deckhand", Role.USER)
    await ai_ready(session)
    provider = FakeChatProvider(replies=[calls("recent_imports"), says("No.")])
    runs, _ = runs_for(engine, provider)

    events = await drain(runs, deckhand, "what's new")

    assert (
        ToolFinished(call_id="call_0", name="recent_imports", outcome=ToolOutcome.REFUSED) in events
    )


async def mark_tools(session: AsyncSession, *, supported: bool) -> None:
    def change(settings: AiSettings) -> None:
        settings.tool_test = AiToolTest(supported=supported, tested_at=NOW)

    await update_settings(session, AiSettings, change)
    await session.commit()


async def test_a_chat_only_model_gets_no_tools(engine: AsyncEngine, session: AsyncSession) -> None:
    admin = await person(session, "skipper", Role.ADMIN)
    await ai_ready(session)
    await mark_tools(session, supported=False)
    provider = FakeChatProvider(replies=[says("Sure.")])
    runs, _ = runs_for(engine, provider)

    await drain(runs, admin, "subscribe to it")

    assert provider.requests[0].tools == ()
    assert "You have no tools" in provider.requests[0].system
    assert (await assistant_status(session)).chat_only is True


async def test_a_model_that_passed_the_tool_test_gets_its_tools(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    admin = await person(session, "skipper", Role.ADMIN)
    await ai_ready(session)
    await mark_tools(session, supported=True)
    provider = FakeChatProvider(replies=[says("Sure.")])
    runs, _ = runs_for(engine, provider)

    await drain(runs, admin, "what's new")

    assert provider.requests[0].tools != ()
    assert (await assistant_status(session)).chat_only is False


# --- 每人自己的 ---------------------------------------------------------------------


async def test_someone_elses_conversation_is_not_listed_read_or_continued(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    admin = await person(session, "skipper", Role.ADMIN)
    deckhand = await person(session, "deckhand", Role.USER)
    await ai_ready(session)
    runs, sessions = runs_for(engine, FakeChatProvider(replies=[says("Hi."), says("Yo.")]))

    mine = (await drain(runs, admin, "my secret plan"))[0]
    assert isinstance(mine, Started)
    await drain(runs, deckhand, "hello")

    async with sessions() as fresh:
        listed = await list_conversations(fresh, user_id=deckhand.id)
        assert [summary.title for summary in listed] == ["hello"]
        with pytest.raises(AssistantRefusedError) as read:
            await read_conversation(
                fresh, user_id=deckhand.id, conversation_id=mine.conversation_id
            )
    assert read.value.reason is AssistantRefusal.CONVERSATION_MISSING
    with pytest.raises(AssistantRefusedError) as sent:
        await runs.send(
            user=deckhand, text="me too", language=Language.EN, conversation_id=mine.conversation_id
        )
    assert sent.value.reason is AssistantRefusal.CONVERSATION_MISSING


# --- 拒絕 -------------------------------------------------------------------------


async def test_nothing_is_sent_while_ai_is_not_set_up(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    admin = await person(session, "skipper", Role.ADMIN)
    provider = FakeChatProvider()
    runs, sessions = runs_for(engine, provider)

    with pytest.raises(AssistantRefusedError) as refused:
        await runs.send(user=admin, text="hi", language=Language.EN)

    assert refused.value.reason is AssistantRefusal.NOT_READY
    assert provider.requests == []
    async with sessions() as fresh:
        assert await list_conversations(fresh, user_id=admin.id) == []
    assert (await assistant_status(session)).ready is False


async def test_a_blank_message_is_refused(engine: AsyncEngine, session: AsyncSession) -> None:
    admin = await person(session, "skipper", Role.ADMIN)
    await ai_ready(session)
    runs, _ = runs_for(engine, FakeChatProvider())

    with pytest.raises(AssistantRefusedError) as refused:
        await runs.send(user=admin, text="  \n ", language=Language.EN)

    assert refused.value.reason is AssistantRefusal.EMPTY_MESSAGE


class HeldProvider(FakeChatProvider):
    """回覆停在送出之後，等測試放行。"""

    def __init__(self, replies: list[TurnEnded]) -> None:
        super().__init__(replies=list(replies))
        self.release = asyncio.Event()

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        await self.release.wait()
        async for event in super().stream(request):
            yield event


async def test_a_second_message_waits_for_the_reply_in_flight(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    admin = await person(session, "skipper", Role.ADMIN)
    await ai_ready(session)
    provider = HeldProvider([says("Done.")])
    runs, _ = runs_for(engine, provider)

    reply = await runs.send(user=admin, text="hi", language=Language.EN)
    with pytest.raises(AssistantRefusedError) as refused:
        await runs.send(
            user=admin, text="hurry", language=Language.EN, conversation_id=reply.conversation_id
        )
    provider.release.set()
    [event async for event in reply.events]

    assert refused.value.reason is AssistantRefusal.BUSY
    assert runs.replying(reply.conversation_id) is False


async def test_the_reply_finishes_even_when_nobody_is_reading(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    """關掉面板（SSE 斷了）不打斷回覆：它照樣跑完、存下來。"""
    admin = await person(session, "skipper", Role.ADMIN)
    await ai_ready(session)
    provider = HeldProvider([says("Saved anyway.")])
    runs, sessions = runs_for(engine, provider)

    reply = await runs.send(user=admin, text="hi", language=Language.EN)
    provider.release.set()
    while runs.replying(reply.conversation_id):
        await asyncio.sleep(0.01)

    async with sessions() as fresh:
        view = await read_conversation(
            fresh, user_id=admin.id, conversation_id=reply.conversation_id
        )
    assert view.messages[-1].parts == [ModelText(text="Saved anyway.")]
