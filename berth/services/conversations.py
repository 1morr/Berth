"""助理的對話：存下來的形狀、讀取、交給模型的歷史（M5 票 08，plan §11.6〈對話核心〉）。

送一句話、跑工具迴圈的是 `services.assistant`；這裡是兩邊與 API 都要讀的那一半，與介面無關
（M7 的 Discord 讀同一份）。

- **每人自己的**：每一支讀取都帶著 user id。別人的對話與不存在的說同一句（`conversation_missing`），
  不說出「有，但不是你的」。
- **一則的內容是一串 part**（pydantic、以 `type` 區分），整串存成
  `conversation_messages.parts_json`、讀出時驗過。模型那一輪的 `OpaqueModelPart`
  （Anthropic 的 thinking）只回給 provider，不給畫面。
- **送給模型的歷史由 `turns_of` 從存下的那幾則組出來**：說給人聽的 notice 不送；連著的使用者那一側
  （上一輪的工具結果、這一句話、有人按了確認卡）併成一輪；呼叫了卻沒有結果的工具（回覆跑到一半
  Berth 關機）補一份「沒執行」，provider 才收這份歷史。
- **有人按了確認卡**（M5 票 10）存成一則 `decision`：模型下一輪從帶出處的 JSON 讀到結果，畫面上
  由那張卡自己畫（卡片讀 `proposals` 的現況，不讀這一則）。
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.ai import ModelTurn, OpaquePart, TextPart, ToolCall, ToolResult, UserTurn
from berth.domain import (
    AiFailure,
    ApiFormat,
    AssistantNotice,
    AssistantRefusal,
    MessageKind,
    ProposalRefusal,
    ProposalStatus,
    ToolOutcome,
)
from berth.models import AiSettings, Conversation, ConversationMessage
from berth.services.ai import is_ready
from berth.services.commands import Effect, command
from berth.services.settings import read_settings

#: 歷史清單一次列幾則。
LIST_LIMIT = 50
#: 對話名取第一句話的前幾個字。
TITLE_LENGTH = 80


class AssistantRefusedError(Exception):
    def __init__(self, reason: AssistantRefusal, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason.value)
        self.reason = reason
        self.detail = detail


class ProposalRejectedError(Exception):
    """按確認卡不做的理由（`services.proposals`，M5 票 10）。定義在這裡而不在 `proposals`：登錄表
    要把它列進 `REJECTIONS`，而 `proposals` 依賴登錄表。"""

    def __init__(self, reason: ProposalRefusal, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason.value)
        self.reason = reason
        self.detail = detail


# --- 一則的 part ------------------------------------------------------------------


class _Part(BaseModel):
    model_config = ConfigDict(frozen=True)


class UserText(_Part):
    type: Literal["user_text"] = "user_text"
    text: str


class ModelText(_Part):
    type: Literal["model_text"] = "model_text"
    text: str


class ToolCallPart(_Part):
    type: Literal["tool_call"] = "tool_call"
    id: str
    name: str
    #: 模型給的 JSON 原文。
    arguments: str


class OpaqueModelPart(_Part):
    """provider 要求原樣帶回的東西。只對同一種格式送回去，畫面上不出現。"""

    type: Literal["opaque"] = "opaque"
    format: ApiFormat
    raw: dict[str, Any]


class ToolResultPart(_Part):
    type: Literal["tool_result"] = "tool_result"
    #: 對應的 `ToolCallPart.id`。
    call_id: str
    tool: str
    outcome: ToolOutcome
    #: 結果型別的名字（`RecentImports`、`Refusal`）：前端依它挑卡片（票 09）。
    result_type: str
    result: dict[str, Any]


class NoticePart(_Part):
    """Berth 說給人聽的停止原因。不送給模型。"""

    type: Literal["notice"] = "notice"
    notice: AssistantNotice
    #: `provider_failed` 時是哪一種。
    failure: AiFailure | None = None
    #: 限流時 provider 說的「幾秒後再來」。
    retry_after: float | None = None
    #: `round_limit` 時是幾次（`services.assistant.MAX_TOOL_ROUNDS`）：畫面照它說，不另抄一份數字。
    limit: int | None = None


class DecisionPart(_Part):
    """有人按了一張確認卡（M5 票 10）：確認了、結果是什麼，或拒絕了。給模型看的，畫面不另畫。"""

    type: Literal["decision"] = "decision"
    proposal_id: int
    tool: str
    status: ProposalStatus
    #: 確認之後的結果型別與結果（同 `ToolResultPart`）；拒絕時是空的。
    result_type: str | None = None
    result: dict[str, Any] | None = None


#: 一則裡的一個 part。`Part` 是同一份聯集加上讀出時用的 discriminator。
StoredPart = (
    UserText
    | ModelText
    | ToolCallPart
    | OpaqueModelPart
    | ToolResultPart
    | NoticePart
    | DecisionPart
)
Part = Annotated[StoredPart, Field(discriminator="type")]
_PARTS = TypeAdapter(list[Part])


def dump_parts(parts: Sequence[StoredPart]) -> list[dict[str, Any]]:
    return [part.model_dump(mode="json") for part in parts]


# --- 讀取 -------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AssistantStatus:
    #: AI 設定好了（`services.ai.is_ready`）；沒有時側面板說怎麼開。
    ready: bool
    #: 設定頁測出這個模型不支援工具呼叫：請求不帶工具，側面板標明只能聊天。還沒測是 `False`。
    chat_only: bool


@dataclass(frozen=True, slots=True)
class ConversationSummary:
    id: int
    title: str
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class MessageView:
    id: int
    kind: MessageKind
    created_at: datetime
    parts: list[Part]


@dataclass(frozen=True, slots=True)
class ConversationView:
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageView]


def status_of(settings: AiSettings) -> AssistantStatus:
    test = settings.tool_test
    return AssistantStatus(
        ready=is_ready(settings), chat_only=test is not None and not test.supported
    )


@command(Effect.READ)
async def assistant_status(session: AsyncSession) -> AssistantStatus:
    return status_of(await read_settings(session, AiSettings))


@command(Effect.READ)
async def list_conversations(session: AsyncSession, *, user_id: int) -> list[ConversationSummary]:
    """這個人的對話，最近有動的在前。"""
    rows = await session.scalars(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        .limit(LIST_LIMIT)
    )
    return [
        ConversationSummary(id=row.id, title=row.title, updated_at=row.updated_at) for row in rows
    ]


@command(Effect.READ)
async def read_conversation(
    session: AsyncSession, *, user_id: int, conversation_id: int
) -> ConversationView:
    """一則對話的每一則，照順序。沒有、或不是這個人的，是 `conversation_missing`。"""
    conversation = await own_conversation(session, user_id=user_id, conversation_id=conversation_id)
    return ConversationView(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[
            MessageView(id=row.id, kind=row.kind, created_at=row.created_at, parts=parts_of(row))
            for row in await messages_of(session, conversation.id)
        ],
    )


@command(Effect.READ)
async def own_conversation(
    session: AsyncSession, *, user_id: int, conversation_id: int
) -> Conversation:
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user_id:
        raise AssistantRefusedError(AssistantRefusal.CONVERSATION_MISSING, str(conversation_id))
    return conversation


@command(Effect.READ)
async def messages_of(session: AsyncSession, conversation_id: int) -> list[ConversationMessage]:
    rows = await session.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.id)
    )
    return list(rows)


def append_message(
    session: AsyncSession,
    conversation: Conversation,
    kind: MessageKind,
    parts: Sequence[StoredPart],
    now: datetime,
) -> None:
    """加一則到對話的最後（不 commit）。同一則對話一次只有一個寫者：回覆在跑時，按確認卡的那一支
    等它跑完（`services.assistant.AssistantRuns`）。"""
    session.add(
        ConversationMessage(
            conversation_id=conversation.id, kind=kind, parts_json=dump_parts(parts), created_at=now
        )
    )
    conversation.updated_at = now


def parts_of(row: ConversationMessage) -> list[Part]:
    return _PARTS.validate_python(row.parts_json)


def title_of(text: str) -> str:
    return " ".join(text.split())[:TITLE_LENGTH]


# --- 交給模型的歷史 -----------------------------------------------------------------

#: 呼叫了卻沒有結果的工具（`turns_of` 補上的那一份）。
_NOT_RUN = json.dumps({"source": "berth", "status": "not_run"})


def tool_content(part: ToolResultPart) -> str:
    """工具結果給模型的那一段：**帶出處的 JSON**（brief §6.10「外部文字是資料」、§20.24）。

    結果裡的字（發佈名、標題、檔名）是外部來的，system 說明這一段是資料不是指令；給模型的指示
    不放在這裡。`sort_keys`：同一份結果每次序列化成同一串字，歷史才吃得到快取。
    """
    return json.dumps(
        {
            "source": "berth",
            "tool": part.tool,
            "status": part.outcome.value,
            "result": part.result,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def decision_content(part: DecisionPart) -> str:
    """有人按了確認卡，給模型的那一段：帶出處的 JSON，**只有 Berth 自己的字**。

    它在使用者那一側進模型（工具呼叫早就有了結果），而外部來的文字只能經由工具結果進來
    （brief §6.10「外部文字是資料」、§20.24）：結果裡的 torrent 名、Prowlarr 回的原文都不放，只說
    做成了沒有與拒絕的理由碼。做了什麼的細節在卡上（plan §11.6：做了什麼只以結果卡為準）。
    """
    content: dict[str, Any] = {
        "source": "berth",
        "proposal": part.proposal_id,
        "tool": part.tool,
        "status": part.status.value,
    }
    if part.result_type is not None:
        refused = part.result_type == "Refusal"
        content["outcome"] = "refused" if refused else "done"
        if refused and part.result is not None:
            content["reason"] = part.result.get("reason", "")
    return json.dumps(content, ensure_ascii=False, sort_keys=True)


def tool_result_of(part: ToolResultPart) -> ToolResult:
    """存下的一個工具結果 → 送給 provider 的那一份。"""
    return ToolResult(
        part.call_id, tool_content(part), is_error=part.outcome is ToolOutcome.REFUSED
    )


def turns_of(
    rows: Sequence[ConversationMessage], format: ApiFormat
) -> tuple[UserTurn | ModelTurn, ...]:
    """存下的那幾則 → provider 的歷史（模組說明的三條）。`format` 是現在要打的那一種格式：
    別種格式的 `OpaqueModelPart` 不送。"""
    turns: list[UserTurn | ModelTurn] = []
    for row in rows:
        parts = parts_of(row)
        if row.kind is MessageKind.USER:
            _add_user(turns, tuple(TextPart(p.text) for p in parts if isinstance(p, UserText)))
        elif row.kind is MessageKind.DECISION:
            decided = tuple(
                TextPart(decision_content(p)) for p in parts if isinstance(p, DecisionPart)
            )
            _add_user(turns, decided)
        elif row.kind is MessageKind.TOOLS:
            results = tuple(tool_result_of(p) for p in parts if isinstance(p, ToolResultPart))
            # 這一份就是上一輪那幾個呼叫的結果，不補「沒執行」。
            _add_user(turns, results, closes=False)
        elif row.kind is MessageKind.MODEL:
            model = ModelTurn(tuple(_provider_parts(parts, format)))
            if model.parts:
                _close_open_calls(turns)
                turns.append(model)
    return tuple(turns)


def _provider_parts(
    parts: Sequence[Part], format: ApiFormat
) -> list[TextPart | ToolCall | OpaquePart]:
    out: list[TextPart | ToolCall | OpaquePart] = []
    for part in parts:
        if isinstance(part, ModelText) and part.text:
            out.append(TextPart(part.text))
        elif isinstance(part, ToolCallPart):
            out.append(ToolCall(id=part.id, name=part.name, arguments=part.arguments))
        elif isinstance(part, OpaqueModelPart) and part.format is format:
            out.append(OpaquePart(format=part.format, raw=part.raw))
    return out


def _add_user(
    turns: list[UserTurn | ModelTurn],
    parts: tuple[TextPart | ToolResult, ...],
    *,
    closes: bool = True,
) -> None:
    if not parts:
        return
    if closes:
        _close_open_calls(turns)
    if turns and isinstance(turns[-1], UserTurn):
        previous = turns.pop()
        assert isinstance(previous, UserTurn)
        # 工具結果在前、文字在後（Anthropic 要 tool_result 排在使用者那一輪的最前面）。
        merged = sorted(
            (*previous.parts, *parts), key=lambda part: not isinstance(part, ToolResult)
        )
        turns.append(UserTurn(tuple(merged)))
        return
    turns.append(UserTurn(parts))


def _close_open_calls(turns: list[UserTurn | ModelTurn]) -> None:
    """接下來要加一輪、而最後一輪是模型呼叫了工具卻沒有結果時，補一份「沒執行」。"""
    if not turns or not isinstance(turns[-1], ModelTurn):
        return
    open_calls = turns[-1].tool_calls
    if open_calls:
        turns.append(
            UserTurn(tuple(ToolResult(call.id, _NOT_RUN, is_error=True) for call in open_calls))
        )
