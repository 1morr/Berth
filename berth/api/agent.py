"""側面板對話的端點（M5 票 11、plan §6〈agent〉）。

- `POST /agent/chat`：Vercel AI SDK 的 UI message stream（`VercelAIAdapter`，`sdk_version=7`）。
  前端 `useChat` 每次送整份訊息，這裡**只取最後一則使用者訊息的字**，歷史以資料庫為準；前端送回的
  工具結果與核准一律不採用（brief §20.24：adapter 預設照收）。body 另外帶 `language`（介面語言，
  `domain.Language`），防護停下時的說明照它寫。
- `GET /agent/conversations/{id}`：存著的歷史轉回 UI 訊息（`dump_messages(..., sdk_version=7)`），
  重新載入頁面時接回來。

登入就能用（門禁的預設）；工具的範圍照這個人的角色（`services.agent_tools.visible_tools`）。
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError
from pydantic_ai import DeferredToolResults
from pydantic_ai.messages import ModelMessage, ModelRequest
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from pydantic_ai.ui.vercel_ai.request_types import SubmitMessage, TextUIPart
from pydantic_ai.ui.vercel_ai.response_types import (
    BaseChunk,
    ErrorChunk,
    TextDeltaChunk,
    TextEndChunk,
    TextStartChunk,
)

from berth.api.deps import (
    AgentRuntimeDep,
    ClientFactoryDep,
    ExecutorDep,
    SessionDep,
    SessionFactoryDep,
)
from berth.api.errors import refusal_responses
from berth.api.gate import current_user
from berth.domain import Actor, AgentRefusal, Language
from berth.services.agent import (
    AgentRefusedError,
    Turn,
    open_turn,
    read_conversation,
)

router = APIRouter(prefix="/agent", tags=["agent"])

#: Vercel AI SDK 的版本：6 起才有核准串流，7 與 6 同一份 wire（brief §20.24）。
SDK_VERSION: Literal[7] = 7

_STATUS: dict[AgentRefusal, int] = {
    AgentRefusal.AI_DISABLED: status.HTTP_409_CONFLICT,
    AgentRefusal.BUSY: status.HTTP_409_CONFLICT,
    AgentRefusal.NO_MESSAGE: status.HTTP_422_UNPROCESSABLE_CONTENT,
    AgentRefusal.CONVERSATION_MISSING: status.HTTP_404_NOT_FOUND,
}


class AgentRefusalOut(BaseModel):
    reason: AgentRefusal
    detail: str


class ConversationOut(BaseModel):
    id: str
    #: `useChat` 的 `UIMessage`（ai 7）。`Any`：JSON 的形狀由 pydantic-ai 的 `UIMessage` 決定，
    #: 不在這裡重抄一份 schema。
    messages: list[dict[str, Any]]


def agent_refusal(exc: AgentRefusedError) -> HTTPException:
    body = AgentRefusalOut(reason=exc.reason, detail=exc.detail)
    return HTTPException(status_code=_STATUS[exc.reason], detail=body.model_dump(mode="json"))


def _responses(*reasons: AgentRefusal) -> dict[int | str, dict[str, Any]]:
    return refusal_responses(AgentRefusalOut, {reason: _STATUS[reason] for reason in reasons})


@dataclass
class ServerHistoryAdapter(VercelAIAdapter[Turn, str]):
    """歷史由伺服器保管：送給 agent 的新訊息只有這一輪的使用者訊息，前端的核准不採用。"""

    prompt: ModelRequest | None = None

    @cached_property
    def messages(self) -> list[ModelMessage]:
        return [self.prompt] if self.prompt is not None else []

    @cached_property
    def deferred_tool_results(self) -> DeferredToolResults | None:
        return None


def _actor(request: Request) -> Actor:
    user = current_user(request)
    if user is None:
        # 門禁保證走得到這裡的都登入了；萬一沒有，不可以變成不受角色限制的 `system`。
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="sign in to use this API")
    return Actor.ai(user.id, user.role)


def _last_user_text(run_input: SubmitMessage) -> str:
    last = run_input.messages[-1] if run_input.messages else None
    if last is None or last.role != "user":
        return ""
    return "".join(part.text for part in last.parts if isinstance(part, TextUIPart))


def _language(run_input: SubmitMessage) -> Language:
    raw = (run_input.model_extra or {}).get("language")
    try:
        return Language(str(raw))
    except ValueError:
        return Language.ZH_HANT


@router.post(
    "/chat",
    response_class=StreamingResponse,
    responses={
        status.HTTP_200_OK: {"content": {"text/event-stream": {}}},
        **_responses(*_STATUS),
    },
)
async def chat(
    request: Request,
    executor: ExecutorDep,
    factory: ClientFactoryDep,
    runtime: AgentRuntimeDep,
    sessions: SessionFactoryDep,
) -> StreamingResponse:
    """送一則訊息，串流回模型的回覆與工具呼叫（UI message stream）。"""
    actor = _actor(request)
    try:
        run_input = ServerHistoryAdapter.build_run_input(await request.body())
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.errors(include_input=False)
        ) from exc
    if not isinstance(run_input, SubmitMessage):
        raise agent_refusal(AgentRefusedError(AgentRefusal.NO_MESSAGE, "regenerate"))
    try:
        turn = await open_turn(
            runtime=runtime,
            sessions=sessions,
            executor=executor,
            factory=factory,
            actor=actor,
            conversation_id=run_input.id,
            text=_last_user_text(run_input),
            language=_language(run_input),
        )
    except AgentRefusedError as exc:
        raise agent_refusal(exc) from exc
    adapter = ServerHistoryAdapter(
        agent=turn.agent,
        run_input=run_input,
        accept=request.headers.get("accept"),
        sdk_version=SDK_VERSION,
        prompt=turn.prompt,
    )
    return adapter.streaming_response(_relay(adapter, turn))


async def _relay(adapter: ServerHistoryAdapter, turn: Turn) -> AsyncIterator[BaseChunk]:
    """agent 的串流，把「出錯」換成停下來的說明；不論怎麼結束都收尾這一輪。"""
    try:
        turn.started()
        stream = adapter.run_stream(
            message_history=turn.history,
            deps=turn,
            run_id=turn.run_id,
            model_settings=turn.model_settings,
            on_complete=turn.completed,
        )
        async for chunk in stream:
            if isinstance(chunk, ErrorChunk):
                note = await turn.stopped(chunk.error_text)
                text_id = uuid.uuid4().hex
                yield TextStartChunk(id=text_id)
                yield TextDeltaChunk(id=text_id, delta=note)
                yield TextEndChunk(id=text_id)
                continue
            yield chunk
    finally:
        await turn.close()


@router.get(
    "/conversations/{conversation_id}",
    responses=_responses(AgentRefusal.CONVERSATION_MISSING),
)
async def get_conversation(
    request: Request, session: SessionDep, conversation_id: str
) -> ConversationOut:
    """存著的歷史，轉成 `useChat` 的訊息。沒有工具結果的工具呼叫是 `approval-requested`。"""
    actor = _actor(request)
    assert actor.user_id is not None
    try:
        history = await read_conversation(session, conversation_id, user_id=actor.user_id)
    except AgentRefusedError as exc:
        raise agent_refusal(exc) from exc
    messages = VercelAIAdapter.dump_messages(list(history), sdk_version=SDK_VERSION)
    return ConversationOut(
        id=conversation_id,
        messages=[m.model_dump(mode="json", by_alias=True, exclude_none=True) for m in messages],
    )
