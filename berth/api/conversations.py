"""助理的對話（M5 票 08，plan §11.6〈對話核心〉、`.scratch/m5/side-panel-shape.md`）。

登入就進得來：工具依角色過濾在對話核心（`services.assistant`），不在門禁。每一支都只看得到
自己的對話——別人的與不存在的同樣是 404。

**送一句話是 POST，回應本身就是 SSE**（照 Vercel AI SDK 的 UI message stream：一行 `data:` 一個
帶 `type` 的 JSON，`start` → `text-delta` / `tool-input-start` / `tool-output-available` /
`notice` → `finish`）。這條串流只屬於送出它的那一個請求，別人的連線收不到——不經過
`/events/stream` 那個全體廣播的 hub。前端用 fetch 讀它（`EventSource` 送不了 POST）。

串流是先畫上去的字，**真相在資料庫**：`finish` 之後前端重讀這則對話。連線斷了（關掉面板、換頁）
回覆照樣在後端跑完、存下來；`replying` 說它還在跑。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, RootModel
from sse_starlette import EventSourceResponse

from berth.api.deps import SessionDep
from berth.api.errors import refusal_responses
from berth.api.events import PING_SECONDS, EventStream
from berth.api.gate import current_user
from berth.domain import AssistantRefusal, Language, MessageKind, ProposalRefusal, ToolOutcome
from berth.services.assistant import (
    AssistantEvent,
    AssistantRuns,
    Finished,
    NoticeRaised,
    Reply,
    ReplyText,
    Started,
    ToolFinished,
    ToolStarted,
)
from berth.services.auth import AuthenticatedUser
from berth.services.conversations import (
    AssistantRefusedError,
    DecisionPart,
    ModelText,
    NoticePart,
    OpaqueModelPart,
    ProposalRejectedError,
    ToolCallPart,
    ToolResultPart,
    UserText,
    assistant_status,
    list_conversations,
    read_conversation,
)
from berth.services.proposals import ProposalCard, of_conversation

router = APIRouter(tags=["assistant"])

_STATUS: dict[AssistantRefusal, int] = {
    #: 前提還沒齊：管理員去設定頁。
    AssistantRefusal.NOT_READY: status.HTTP_409_CONFLICT,
    AssistantRefusal.CONVERSATION_MISSING: status.HTTP_404_NOT_FOUND,
    #: 上一個回覆跑完再送。
    AssistantRefusal.BUSY: status.HTTP_409_CONFLICT,
    AssistantRefusal.EMPTY_MESSAGE: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


class AssistantRefusalOut(BaseModel):
    """與其他群組的拒絕同形：`reason` 挑句子，`detail` 是原文。"""

    reason: AssistantRefusal
    detail: str


# Any：FastAPI 的 `responses` 參數本身就是這個型別（同 `api/notify.py`）。
def _responses(*reasons: AssistantRefusal) -> dict[int | str, dict[str, Any]]:
    return refusal_responses(AssistantRefusalOut, {reason: _STATUS[reason] for reason in reasons})


def assistant_refusal(refusal: AssistantRefusedError) -> HTTPException:
    body = AssistantRefusalOut(reason=refusal.reason, detail=refusal.detail)
    return HTTPException(status_code=_STATUS[refusal.reason], detail=body.model_dump(mode="json"))


def _user(request: Request) -> AuthenticatedUser:
    user = current_user(request)
    # 在要登入的門後面，門禁跑過之後一定有人。
    assert user is not None
    return user


def get_assistant(request: Request) -> AssistantRuns:
    """正在跑的回覆（`main.py` 的 lifespan 放進 `app.state`）：一則對話一次一個回覆，
    只有這一份判斷得出來。"""
    runs: AssistantRuns = request.app.state.assistant
    return runs


AssistantDep = Annotated[AssistantRuns, Depends(get_assistant)]


# --- 讀取 -------------------------------------------------------------------------


class AssistantStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    #: AI 設定好了；`false` 時側面板說怎麼開（管理員去設定、一般使用者等管理員）。
    ready: bool
    #: 設定頁測出這個模型不支援工具呼叫：請求不帶工具，側面板標明只能聊天。
    chat_only: bool


class ConversationSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    #: 第一句話的開頭。
    title: str
    updated_at: datetime


#: 畫面看得到的 part（`_HIDDEN` 那幾種不出去）。
VisiblePart = Annotated[
    UserText | ModelText | ToolCallPart | ToolResultPart | NoticePart,
    Field(discriminator="type"),
]


class MessageOut(BaseModel):
    id: int
    kind: MessageKind
    created_at: datetime
    parts: list[VisiblePart]


class ConversationOut(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    #: 回覆還在後端跑（送出的那個請求斷了也照樣跑完）。
    replying: bool
    messages: list[MessageOut]
    #: 這則對話裡每一張確認卡的現況（M5 票 10）。卡片依 `ToolResultPart` 裡的 id 讀這一份：存下的
    #: 那一份是提出時的樣子，按過之後的狀態與結果在這裡。
    proposals: list[ProposalCard]


@router.get("/assistant")
async def get_status(session: SessionDep) -> AssistantStatusOut:
    return AssistantStatusOut.model_validate(await assistant_status(session))


@router.get("/conversations")
async def get_conversations(session: SessionDep, request: Request) -> list[ConversationSummaryOut]:
    """這個人的對話，最近有動的在前。"""
    found = await list_conversations(session, user_id=_user(request).id)
    return [ConversationSummaryOut.model_validate(summary) for summary in found]


@router.get(
    "/conversations/{conversation_id}",
    responses=_responses(AssistantRefusal.CONVERSATION_MISSING),
)
async def get_conversation(
    conversation_id: int, session: SessionDep, request: Request, runs: AssistantDep
) -> ConversationOut:
    user = _user(request)
    try:
        view = await read_conversation(session, user_id=user.id, conversation_id=conversation_id)
        cards = await of_conversation(session, user_id=user.id, conversation_id=conversation_id)
    except AssistantRefusedError as exc:
        raise assistant_refusal(exc) from exc
    return ConversationOut(
        id=view.id,
        title=view.title,
        created_at=view.created_at,
        updated_at=view.updated_at,
        replying=runs.replying(view.id),
        messages=[
            MessageOut(
                id=message.id,
                kind=message.kind,
                created_at=message.created_at,
                parts=[part for part in message.parts if not isinstance(part, _HIDDEN)],
            )
            for message in view.messages
        ],
        proposals=cards,
    )


#: 不給畫面的 part：provider 要原樣帶回的 thinking；按確認卡的那一則由卡片自己畫（讀 `proposals`）。
_HIDDEN = (OpaqueModelPart, DecisionPart)


# --- 送一句話 ---------------------------------------------------------------------


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    #: 介面語言：回覆用它。
    language: Language


class StreamStart(BaseModel):
    type: Literal["start"] = "start"
    #: 新對話的 id 從這裡知道。
    conversation_id: int


class StreamTextDelta(BaseModel):
    type: Literal["text-delta"] = "text-delta"
    delta: str


class StreamToolStart(BaseModel):
    """模型開始呼叫一個工具（Vercel AI SDK 的 `tool-input-start`）。"""

    type: Literal["tool-input-start"] = "tool-input-start"
    tool_call_id: str
    tool_name: str


class StreamToolOutput(BaseModel):
    """工具跑完了（`tool-output-available`）。結果與存下的 `ToolResultPart` 同形：串流時就畫得出
    結果卡（票 09），`finish` 之後重讀的那一份是同一個。"""

    type: Literal["tool-output-available"] = "tool-output-available"
    tool_call_id: str
    tool_name: str
    outcome: ToolOutcome
    #: 結果型別的名字（`ToolResultType` 的一個）：前端依它挑卡片。
    result_type: str
    # `Any`：形狀由 `result_type` 那一個型別說（OpenAPI 的 components），前端照它對回去。
    result: dict[str, Any]


class StreamNotice(BaseModel):
    """回覆停下來的原因（也已經存成一則 notice）。"""

    type: Literal["notice"] = "notice"
    notice: NoticePart


class StreamFinish(BaseModel):
    type: Literal["finish"] = "finish"


Chunk = Annotated[
    StreamStart
    | StreamTextDelta
    | StreamToolStart
    | StreamToolOutput
    | StreamNotice
    | StreamFinish,
    Field(discriminator="type"),
]


class AssistantChunk(RootModel[Chunk]):
    """SSE 一行 `data:` 的形狀。"""


# Any：同 `_responses`。
_STREAM_DOC: dict[int | str, dict[str, Any]] = {
    200: {"model": AssistantChunk, "description": "一行 `data:` 一個 chunk，到 `finish` 為止"}
}


@router.post(
    "/conversations",
    response_class=EventStream,
    responses=_STREAM_DOC | _responses(AssistantRefusal.NOT_READY, AssistantRefusal.EMPTY_MESSAGE),
)
async def post_conversation(
    body: MessageIn, request: Request, runs: AssistantDep
) -> EventSourceResponse:
    """開一則新對話，第一句是 `text`。"""
    return await _send(runs, request, body, conversation_id=None)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_class=EventStream,
    responses=_STREAM_DOC
    | _responses(
        AssistantRefusal.NOT_READY,
        AssistantRefusal.CONVERSATION_MISSING,
        AssistantRefusal.BUSY,
        AssistantRefusal.EMPTY_MESSAGE,
    ),
)
async def post_message(
    conversation_id: int, body: MessageIn, request: Request, runs: AssistantDep
) -> EventSourceResponse:
    return await _send(runs, request, body, conversation_id=conversation_id)


async def _send(
    runs: AssistantRuns, request: Request, body: MessageIn, *, conversation_id: int | None
) -> EventSourceResponse:
    try:
        reply = await runs.send(
            user=_user(request),
            text=body.text,
            language=body.language,
            conversation_id=conversation_id,
        )
    except AssistantRefusedError as exc:
        raise assistant_refusal(exc) from exc
    # 不必等關機訊號：串流讀到 `finish` 就結束，關機時 `AssistantRuns.aclose` 收掉回覆、
    # 照樣送出 `finish`。
    return EventSourceResponse(
        _chunks(reply), ping=PING_SECONDS, headers={"Cache-Control": "no-store"}
    )


async def _chunks(reply: Reply) -> AsyncIterator[dict[str, str]]:
    """讀到 `finish` 為止。連線先斷了的話這個產生器被關掉，回覆本身不受影響。"""
    async for event in reply.events:
        yield {"data": AssistantChunk(_chunk(event)).model_dump_json()}


def _chunk(event: AssistantEvent) -> Chunk:
    match event:
        case Started(conversation_id=cid):
            return StreamStart(conversation_id=cid)
        case ReplyText(text=text):
            return StreamTextDelta(delta=text)
        case ToolStarted(call_id=call_id, name=name):
            return StreamToolStart(tool_call_id=call_id, tool_name=name)
        case ToolFinished(result=part):
            return StreamToolOutput(
                tool_call_id=part.call_id,
                tool_name=part.tool,
                outcome=part.outcome,
                result_type=part.result_type,
                result=part.result,
            )
        case NoticeRaised(notice=notice):
            return StreamNotice(notice=notice)
        case Finished():
            return StreamFinish()


# --- 確認卡（M5 票 10）------------------------------------------------------------

_PROPOSAL_STATUS: dict[ProposalRefusal, int] = {
    ProposalRefusal.PROPOSAL_MISSING: status.HTTP_404_NOT_FOUND,
    #: 另一個分頁或管道先按了：重讀對話就看得到結果。
    ProposalRefusal.ALREADY_DECIDED: status.HTTP_409_CONFLICT,
}


class ProposalRefusalOut(BaseModel):
    reason: ProposalRefusal
    detail: str


# Any：同 `_responses`。
_PROPOSAL_RESPONSES: dict[int | str, dict[str, Any]] = refusal_responses(
    ProposalRefusalOut, _PROPOSAL_STATUS
) | _responses(AssistantRefusal.BUSY)


@router.post("/proposals/{proposal_id}/confirm", responses=_PROPOSAL_RESPONSES)
async def post_confirm(proposal_id: int, request: Request, runs: AssistantDep) -> ProposalCard:
    """按確認：以按的這個人執行，當下重驗角色與輸入。不成立的回 200、狀態是 `expired`，理由在
    `result`——那是卡片的結局，不是請求的錯。"""
    return await _decide(runs.confirm, proposal_id, request)


@router.post("/proposals/{proposal_id}/reject", responses=_PROPOSAL_RESPONSES)
async def post_reject(proposal_id: int, request: Request, runs: AssistantDep) -> ProposalCard:
    """按拒絕：記下來，什麼都不做。"""
    return await _decide(runs.reject, proposal_id, request)


async def _decide(
    decide: Callable[..., Awaitable[ProposalCard]], proposal_id: int, request: Request
) -> ProposalCard:
    try:
        return await decide(proposal_id, user=_user(request))
    except ProposalRejectedError as exc:
        raise proposal_refusal(exc) from exc
    except AssistantRefusedError as exc:
        raise assistant_refusal(exc) from exc


def proposal_refusal(refusal: ProposalRejectedError) -> HTTPException:
    body = ProposalRefusalOut(reason=refusal.reason, detail=refusal.detail)
    return HTTPException(
        status_code=_PROPOSAL_STATUS[refusal.reason], detail=body.model_dump(mode="json")
    )
