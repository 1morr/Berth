"""側面板對話的端點（M5 票 11、plan §6〈agent〉）。

- `POST /agent/chat`：Vercel AI SDK 的 UI message stream（`VercelAIAdapter`，`sdk_version=7`）。
  前端 `useChat` 每次送整份訊息，這裡**只取最後一則使用者訊息的字**，歷史以資料庫為準；前端送回的
  工具結果與核准一律不採用（brief §20.24：adapter 預設照收）。最後一則是**助理**的，是使用者按了
  確認卡之後的恢復（票 13）：它只當觸發，按了什麼由伺服器上的 Proposal 決定。body 另外帶
  `language`（介面語言，`domain.Language`），防護停下時的說明照它寫；按「繼續」時帶 `continues`
  （停下的那一輪的 id，M5 票 20）。防護停下時的說明是一則 `data-stop`（`TurnStopOut`，含說明的字），
  不是助理的文字：側面板畫成「停下」與「繼續」（M5 票 22）。
- `GET /agent/status`：AI 開著沒有，側面板一打開就分得出「可以問」與「沒開」（票 12）；provider
  斷路器暫停到什麼時候、為什麼（票 20）。
- `GET /agent/conversations/{id}`：存著的歷史轉回 UI 訊息（`dump_messages(..., sdk_version=7)`），
  重新載入頁面時接回來。壓縮過的對話開頭是一則 `data-compaction`（摘要）；停下的說明換成與串流
  同一個 `data-stop`，只有最後一輪可能 `continuable`。
- `POST /agent/conversations/{id}/commands`：斜線指令（`services.slash`，M5 票 18）。body 同
  Slack 的 slash command 只帶打的字（`text`），由伺服器認是哪一個；回的是結構，畫面自己組字。
  以 `/` 開頭的訊息送進 `/chat` 是 `slash_command`：指令不經過模型。
- `GET /agent/runs/{id}`：一輪的步驟（M5 票 21）。一般使用者只看得到自己的。每一則助理訊息的
  `metadata.runId` 指到它那一輪：串流時在開頭的 `start`，重新載入時在每一則上。

登入就能用（門禁的預設）；工具的範圍照這個人的角色（`services.agent_tools.visible_tools`）。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from functools import cached_property
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic_ai import DeferredToolRequests, DeferredToolResults
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from pydantic_ai.ui.vercel_ai.request_types import SubmitMessage, TextUIPart, UIMessage
from pydantic_ai.ui.vercel_ai.response_types import (
    BaseChunk,
    DataChunk,
    ErrorChunk,
    StartChunk,
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
from berth.api.usage import SpendCheckOut
from berth.domain import (
    Actor,
    AgentRefusal,
    AiProvider,
    AiRunRefusal,
    AiStopReason,
    AiToolOutcome,
    Language,
    ProposalStatus,
)
from berth.services.agent import (
    NOTE_MODEL,
    AgentRefusedError,
    Turn,
    TurnStop,
    open_turn,
    read_conversation,
    read_status,
)
from berth.services.slash import (
    Compacted,
    NewConversation,
    Pending,
    Skills,
    SlashResult,
    Status,
    Usage,
    run_slash,
)
from berth.services.usage import RunRejectedError, read_run

router = APIRouter(prefix="/agent", tags=["agent"])

#: Vercel AI SDK 的版本：6 起才有核准串流，7 與 6 同一份 wire（brief §20.24）。
SDK_VERSION: Literal[7] = 7

_STATUS: dict[AgentRefusal, int] = {
    AgentRefusal.AI_DISABLED: status.HTTP_409_CONFLICT,
    AgentRefusal.AI_PAUSED: status.HTTP_409_CONFLICT,
    AgentRefusal.CARD_UNDECIDED: status.HTTP_409_CONFLICT,
    AgentRefusal.BUSY: status.HTTP_409_CONFLICT,
    AgentRefusal.NO_MESSAGE: status.HTTP_422_UNPROCESSABLE_CONTENT,
    AgentRefusal.CONVERSATION_MISSING: status.HTTP_404_NOT_FOUND,
    AgentRefusal.NOT_CONTINUABLE: status.HTTP_409_CONFLICT,
    AgentRefusal.UNKNOWN_COMMAND: status.HTTP_422_UNPROCESSABLE_CONTENT,
    AgentRefusal.SLASH_COMMAND: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


class AgentRefusalOut(BaseModel):
    reason: AgentRefusal
    detail: str


class AgentStatusOut(BaseModel):
    #: 關著時面板只說怎麼設定（管理員）或「管理員還沒設定」（一般使用者），其餘與 M4 相同。
    enabled: bool
    #: provider 斷路器暫停到什麼時候；`null` 是沒有暫停。
    paused_until: datetime | None
    #: 讓它暫停的那一次的錯誤原文（key 已遮掉）；只給管理員，其他人與沒有暫停是空字串。
    pause_error: str
    #: 今天的花費提醒與它沒算進去的呼叫數（同用量頁）；只給管理員，其他人是 `null`。只提醒，不停用。
    spend: SpendCheckOut | None


class TurnStopOut(BaseModel):
    """一輪沒有答完：哪一輪、為什麼、能不能按「繼續」，與 Berth 寫的那一句說明（哪一條、做到哪）。

    `data-stop` 的 `data`：串流裡與重新載入時同一個形狀。說明不是助理的文字，側面板畫成「停下」。
    """

    turn_id: str
    reason: AiStopReason
    continuable: bool
    note: str

    @classmethod
    def of(cls, stop: TurnStop, note: str) -> TurnStopOut:
        return cls(
            turn_id=stop.turn_id, reason=stop.reason, continuable=stop.continuable, note=note
        )


class ConversationOut(BaseModel):
    id: str
    #: `useChat` 的 `UIMessage`（ai 7）。`Any`：JSON 的形狀由 pydantic-ai 的 `UIMessage` 決定，
    #: 不在這裡重抄一份 schema。
    messages: list[dict[str, Any]]


class SlashIn(BaseModel):
    #: 打的字，整則就是 `/<名字>`。
    text: str


class NewOut(BaseModel):
    command: Literal["new"]


class CompactOut(BaseModel):
    command: Literal["compact"]
    #: 壓縮前有幾則訊息。
    before: int
    #: 壓縮後有幾則；`null` 是沒有壓（只有一輪，或摘要失敗）。
    after: int | None
    #: 摘要失敗的原文（key 已遮掉）；其他時候是空字串。
    error: str


class UsageOut(BaseModel):
    """這段對話到目前為止（含壓縮的摘要）。`null` 是有一次不知道，合計就是不知道。"""

    command: Literal["usage"]
    turns: int
    compactions: int
    requests: int
    tool_calls: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int | None
    #: 伺服器端網搜（Anthropic `web_search`）。
    web_searches: int
    #: Tavily 真的搜了的次數。
    tavily_searches: int
    cost_usd: float | None


class StatusOut(BaseModel):
    command: Literal["status"]
    provider: AiProvider
    model: str
    messages: int
    #: 上一次回應的 input + output；還沒有回應是 `null`。
    context_tokens: int | None
    context_window: int
    #: 到了這個比例，下一輪開頭自動壓縮。
    compact_at: float
    paused_until: datetime | None


class PendingCardOut(BaseModel):
    id: int
    command: str
    status: ProposalStatus
    rows: int
    expires_at: datetime
    #: 在這段對話裡。
    here: bool


class PendingOut(BaseModel):
    command: Literal["pending"]
    cards: list[PendingCardOut]


class SkillOut(BaseModel):
    name: str
    #: 寫給模型的英文描述（skill 檔的 `description`），畫面原樣顯示。
    description: str


class SkillsOut(BaseModel):
    command: Literal["skills"]
    skills: list[SkillOut]


SlashOut = Annotated[
    NewOut | CompactOut | UsageOut | StatusOut | PendingOut | SkillsOut,
    Field(discriminator="command"),
]


def slash_out(
    result: SlashResult,
) -> NewOut | CompactOut | UsageOut | StatusOut | PendingOut | SkillsOut:
    match result:
        case NewConversation():
            return NewOut(command="new")
        case Compacted():
            return CompactOut(
                command="compact", before=result.before, after=result.after, error=result.error
            )
        case Usage():
            return UsageOut.model_validate({"command": "usage", **asdict(result)})
        case Status():
            return StatusOut.model_validate({"command": "status", **asdict(result)})
        case Pending():
            return PendingOut.model_validate({"command": "pending", **asdict(result)})
        case Skills():
            return SkillsOut(
                command="skills",
                skills=[SkillOut(name=s.name, description=s.description) for s in result.skills],
            )


def agent_refusal(exc: AgentRefusedError) -> HTTPException:
    body = AgentRefusalOut(reason=exc.reason, detail=exc.detail)
    return HTTPException(status_code=_STATUS[exc.reason], detail=body.model_dump(mode="json"))


def _responses(*reasons: AgentRefusal) -> dict[int | str, dict[str, Any]]:
    return refusal_responses(AgentRefusalOut, {reason: _STATUS[reason] for reason in reasons})


@dataclass
class ServerHistoryAdapter(VercelAIAdapter[Turn, str | DeferredToolRequests]):
    """歷史由伺服器保管：送給 agent 的新訊息只有這一輪的使用者訊息，前端的核准不採用（恢復時的
    結論由 `open_turn` 從 Proposal 算好，經 `run_stream` 的 `deferred_tool_results` 給）。"""

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


def _prompt_text(run_input: SubmitMessage) -> str | None:
    """這一輪的使用者訊息的字；`None` 是**恢復**。

    恢復：最後一則是助理的，是按了確認卡之後 `useChat` 送的。

    空字串是沒有字（`open_turn` 回 `no_message`）。
    """
    last = run_input.messages[-1] if run_input.messages else None
    if last is None:
        return ""
    if last.role == "assistant":
        return None
    if last.role != "user":
        return ""
    return "".join(part.text for part in last.parts if isinstance(part, TextUIPart))


def _continues(run_input: SubmitMessage) -> str | None:
    raw = (run_input.model_extra or {}).get("continues")
    return raw if isinstance(raw, str) and raw else None


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
            text=_prompt_text(run_input),
            language=_language(run_input),
            continues=_continues(run_input),
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
            deferred_tool_results=turn.deferred,
            deps=turn,
            run_id=turn.run_id,
            model_settings=turn.model_settings,
            on_complete=turn.completed,
        )
        async for chunk in stream:
            if isinstance(chunk, StartChunk):
                chunk.message_metadata = {RUN_ID: turn.run_id}
            if isinstance(chunk, ErrorChunk):
                note, stop = await turn.stopped(chunk.error_text)
                yield _stop_chunk(TurnStopOut.of(stop, note))
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
        found = await read_conversation(session, conversation_id, user_id=actor.user_id)
    except AgentRefusedError as exc:
        raise agent_refusal(exc) from exc
    messages = VercelAIAdapter.dump_messages(_tagged(found.history), sdk_version=SDK_VERSION)
    return ConversationOut(
        id=conversation_id,
        messages=[_with_stop(message, found.stops) for message in messages],
    )


#: 每一則助理訊息的 `metadata` 裡指到它那一輪的鍵（側面板連到步驟頁）。
RUN_ID = "runId"
#: 停下的說明那一則的記號，只在這裡轉換時用：轉成 `data-stop` 之後拿掉。
_STOP_NOTE = "berthStopNote"


def _tagged(history: Sequence[ModelMessage]) -> list[ModelMessage]:
    """每一則模型回應的 metadata 帶上它那一輪的 id；停下的說明另外記一個記號。

    `dump_messages` 一則回應一則 `UIMessage`，回應的 metadata 照抄進 `UIMessage.metadata`。
    """
    return [
        replace(
            message,
            metadata={
                **(message.metadata or {}),
                RUN_ID: message.run_id,
                **({_STOP_NOTE: True} if message.model_name == NOTE_MODEL else {}),
            },
        )
        if isinstance(message, ModelResponse) and message.run_id
        else message
        for message in history
    ]


def _stop_chunk(stop: TurnStopOut) -> DataChunk:
    return DataChunk(type="data-stop", data=stop.model_dump(mode="json"))


def _with_stop(message: UIMessage, stops: Mapping[str, TurnStop]) -> dict[str, Any]:
    """停下的說明那一則換成與串流同一個 `data-stop`；其餘照原樣。"""
    dumped = message.model_dump(mode="json", by_alias=True, exclude_none=True)
    metadata = dumped.get("metadata") or {}
    if not metadata.pop(_STOP_NOTE, False):
        return dumped
    stop = stops.get(metadata.get(RUN_ID, ""))
    note = "".join(part.get("text", "") for part in dumped["parts"] if part["type"] == "text")
    if stop is None:
        # 停止原因沒有記下（不該發生）：照一般的文字畫，不憑空說能不能續。
        return dumped
    dumped["parts"] = [
        {"type": "data-stop", "data": TurnStopOut.of(stop, note).model_dump(mode="json")}
    ]
    return dumped


@router.get("/status")
async def get_status(
    request: Request, session: SessionDep, runtime: AgentRuntimeDep
) -> AgentStatusOut:
    """側面板的狀態。登入就讀得到：一般使用者讀不到 `/settings/ai`，也一樣被暫停擋著。"""
    actor = _actor(request)
    found = await read_status(session, runtime, actor.role)
    return AgentStatusOut(
        enabled=found.enabled,
        paused_until=found.paused_until,
        pause_error=found.pause_error,
        spend=SpendCheckOut.model_validate(found.spend) if found.spend is not None else None,
    )


@router.post(
    "/conversations/{conversation_id}/commands",
    responses=_responses(
        AgentRefusal.UNKNOWN_COMMAND,
        AgentRefusal.CONVERSATION_MISSING,
        AgentRefusal.AI_DISABLED,
        AgentRefusal.AI_PAUSED,
        AgentRefusal.BUSY,
    ),
)
async def post_command(
    request: Request,
    body: SlashIn,
    conversation_id: str,
    factory: ClientFactoryDep,
    runtime: AgentRuntimeDep,
    sessions: SessionFactoryDep,
) -> SlashOut:
    """斜線指令。不經過模型，只有 `/compact` 的摘要叫一次。"""
    try:
        result = await run_slash(
            runtime=runtime,
            sessions=sessions,
            factory=factory,
            actor=_actor(request),
            conversation_id=conversation_id,
            text=body.text,
        )
    except AgentRefusedError as exc:
        raise agent_refusal(exc) from exc
    return slash_out(result)


class RunRefusalOut(BaseModel):
    reason: AiRunRefusal
    detail: str


class StepCallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model: str
    input_tokens: int
    output_tokens: int
    #: `null` 是接口沒報（不當 0）。
    cache_read_tokens: int | None
    cache_write_tokens: int | None
    #: 查不到價目、或出錯沒有回應是 `null`。
    cost_usd: float | None
    web_searches: int
    #: 模型說它為什麼停（原樣）；出錯是空字串。
    finish_reason: str
    duration_ms: int
    #: 出錯的原文（key 已遮掉）；成功是空字串。
    error: str
    created_at: datetime


class StepToolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    #: 命令登錄表的名字（`why_not.explain`）。
    command: str
    #: 參數的 JSON，截在 2000 字。
    args_json: str
    outcome: AiToolOutcome
    #: 拒絕的理由、錯誤的原文；成功是空字串。
    detail: str
    truncated: bool
    duration_ms: int


class RunStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step: int
    #: 記帳之前就斷掉的那一次是 `null`（只剩它叫的工具）。
    call: StepCallOut | None
    tools: list[StepToolOut]


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_name: str
    provider: AiProvider
    model: str
    started_at: datetime
    #: 還在跑是 `null`。
    ended_at: datetime | None
    #: 還在跑是 `null`。
    stop_reason: AiStopReason | None
    #: 出錯的原文（key 已遮掉）。
    error: str
    #: 這一輪是對哪一輪按的「繼續」。
    continues: str | None
    requests: int
    tool_calls: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int | None
    cache_write_tokens: int | None
    #: 快取讀 ÷ input；快取讀不知道或沒有 input 是 `null`。
    hit_rate: float | None
    cost_usd: float | None
    web_searches: int
    tavily_searches: int
    steps: list[RunStepOut]


_RUN_STATUS: dict[AiRunRefusal, int] = {AiRunRefusal.RUN_MISSING: status.HTTP_404_NOT_FOUND}


def run_refusal(exc: RunRejectedError) -> HTTPException:
    body = RunRefusalOut(reason=exc.reason, detail=exc.detail)
    return HTTPException(status_code=_RUN_STATUS[exc.reason], detail=body.model_dump(mode="json"))


@router.get("/runs/{run_id}", responses=refusal_responses(RunRefusalOut, _RUN_STATUS))
async def get_run(request: Request, session: SessionDep, run_id: str) -> RunOut:
    """一輪的步驟：每一次模型呼叫與它叫的工具、各自的數字，以及停止原因。"""
    actor = _actor(request)
    assert actor.user_id is not None
    try:
        found = await read_run(session, run_id, user_id=actor.user_id, role=actor.role)
    except RunRejectedError as exc:
        raise run_refusal(exc) from exc
    return RunOut.model_validate(found)
