"""AI 活動（M5 票 14，CONTEXT.md 的 AI Activity、brief §6.10 ⑤、
`.scratch/m5/ai-activity-shape.md`）。

AI 做過的每一個寫入：何時、代誰、哪個工具、輸入、AI 給的理由、這次回覆花的 tokens、出自哪則對話、
撤不撤得了。

**不另寫一份日誌，從對話本身撈**：AI 的每一次工具呼叫與結果存在 `conversation_messages`，確認卡
在 `proposals`，撤銷是對話裡的 `UndonePart`。`events.actor` 的 `ai:<user id>` 只掛在 Job 的事件上，
說不出工具、理由與對話，所以不從它撈。

- **列進來的**：工具結果是 `done`、而工具不是讀取的（AI 直接做的）；確認卡是 `confirmed`、而且
  做成了的（人按了、以他執行）。拒絕的、等人按的、被拒絕或失效的卡什麼都沒改，不列。登錄表裡
  已經沒有的工具分不出讀寫，不列。
- **誰看得到**：管理員看全部，其他人只看自己對話裡的。
- **位址**：每一列帶著結果卡同一個撤銷位址（那一則的 id 與 call id；確認卡是那張卡的那一份工具
  結果），撤銷走同一支命令（`services.undo`）。
- **tokens**：這次回覆（使用者那一句之後的每一次模型呼叫，`ai_calls.message_id`）加總，只加知道的；
  一格都不知道是 `None`。
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import (
    ActivityUndo,
    ActivityVia,
    MessageKind,
    ProposalStatus,
    Role,
    ToolOutcome,
)
from berth.models import AiCall, Conversation, ConversationMessage, Proposal, User
from berth.services.auth import AuthenticatedUser
from berth.services.commands import Effect, command
from berth.services.conversations import (
    ToolCallPart,
    ToolResultPart,
    UndonePart,
    parts_of,
)
from berth.services.proposals import card_id_of, done_of
from berth.services.registry import Registry

#: 一次列幾筆，新的在前。家用的量；更早的頁面說一句不列。
LIMIT = 200


@dataclass(frozen=True, slots=True)
class ReplyTokens:
    input: int | None
    output: int | None


@dataclass(frozen=True, slots=True)
class ActivityEntry:
    conversation_id: int
    conversation_title: str
    #: 是看的人自己的對話（連得回去）。
    own: bool
    #: 撤銷的位址：存著那一份工具結果的那一則與 call id（同結果卡）。
    message_id: int
    call_id: str
    #: AI 做的那一刻；確認卡是人按下確認的那一刻。
    at: datetime
    user_id: int
    user_name: str
    via: ActivityVia
    tool: str
    #: 模型給的輸入，拿掉理由那一格。
    arguments: dict[str, Any]
    #: AI 給的理由，原文；舊的紀錄沒有時是空字串。
    reason: str
    result_type: str
    result: dict[str, Any]
    tokens: ReplyTokens
    undo: ActivityUndo
    undone_at: datetime | None


@dataclass(frozen=True, slots=True)
class Activity:
    entries: list[ActivityEntry]
    #: 有比 `LIMIT` 更早的沒列出來。
    truncated: bool


@command(Effect.READ)
async def read_activity(
    session: AsyncSession, registry: Registry, *, viewer: AuthenticatedUser
) -> Activity:
    """`viewer` 看得到的 AI 寫入，新的在前。"""
    query = select(Conversation, User.name).join(User, User.id == Conversation.user_id)
    if viewer.role is not Role.ADMIN:
        query = query.where(Conversation.user_id == viewer.id)
    conversations = {
        row.Conversation.id: (row.Conversation, row.name) for row in await session.execute(query)
    }
    if not conversations:
        return Activity(entries=[], truncated=False)
    ids = list(conversations)
    messages = await session.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id.in_(ids))
        .order_by(ConversationMessage.conversation_id, ConversationMessage.id)
    )
    cards = {
        card.id: card
        for card in await session.scalars(
            select(Proposal).where(
                Proposal.conversation_id.in_(ids), Proposal.status == ProposalStatus.CONFIRMED
            )
        )
    }
    found = _WriteCollector(registry, viewer, cards)
    for message in messages:
        conversation, name = conversations[message.conversation_id]
        found.read(message, conversation, name)
    tokens = await _reply_tokens(session, found.replies())
    entries = sorted(
        (found.entry(row, tokens) for row in found.rows),
        key=lambda entry: (entry.at, entry.message_id),
        reverse=True,
    )
    return Activity(entries=entries[:LIMIT], truncated=len(entries) > LIMIT)


@dataclass(frozen=True, slots=True)
class _Row:
    """一筆還沒算 tokens 與撤銷狀態的寫入。"""

    conversation: Conversation
    user_name: str
    message_id: int
    call_id: str
    user_message_id: int | None
    at: datetime
    via: ActivityVia
    tool: str
    arguments: dict[str, Any]
    result_type: str
    result: dict[str, Any]


class _WriteCollector:
    """照順序讀每一則對話，收出寫入與撤銷。一則對話的訊息連續地來（照對話、照 id 排）。"""

    def __init__(
        self, registry: Registry, viewer: AuthenticatedUser, cards: dict[int, Proposal]
    ) -> None:
        self._registry = registry
        self._viewer = viewer
        self._cards = cards
        self.rows: list[_Row] = []
        #: `(那一則, call id)` → 撤銷那一則的時刻。
        self._undone: dict[tuple[int, str], datetime] = {}
        self._conversation: int | None = None
        #: 這一輪回覆在回哪一句話。
        self._user_message: int | None = None
        #: 上一則模型回合的工具呼叫：工具結果接在它後面（同一個 call id 可能每一輪都出現）。
        self._calls: dict[str, ToolCallPart] = {}

    def read(self, message: ConversationMessage, conversation: Conversation, name: str) -> None:
        if message.conversation_id != self._conversation:
            self._conversation, self._user_message, self._calls = message.conversation_id, None, {}
        parts = parts_of(message)
        if message.kind is MessageKind.USER:
            self._user_message = message.id
        elif message.kind is MessageKind.MODEL:
            self._calls = {part.id: part for part in parts if isinstance(part, ToolCallPart)}
        elif message.kind is MessageKind.DECISION:
            for part in parts:
                if isinstance(part, UndonePart):
                    self._undone[(part.message_id, part.call_id)] = message.created_at
        elif message.kind is MessageKind.TOOLS:
            for part in parts:
                if isinstance(part, ToolResultPart):
                    row = self._row(part, message, conversation, name)
                    if row is not None:
                        self.rows.append(row)

    def _row(
        self,
        part: ToolResultPart,
        message: ConversationMessage,
        conversation: Conversation,
        name: str,
    ) -> _Row | None:
        tool = self._registry.get(part.tool)
        if tool is None:
            return None

        def made(
            at: datetime,
            via: ActivityVia,
            arguments: dict[str, Any],
            result_type: str,
            result: dict[str, Any],
        ) -> _Row:
            return _Row(
                conversation=conversation,
                user_name=name,
                message_id=message.id,
                call_id=part.call_id,
                user_message_id=self._user_message,
                at=at,
                via=via,
                tool=part.tool,
                arguments=arguments,
                result_type=result_type,
                result=result,
            )

        if part.outcome is ToolOutcome.DONE and tool.effect is not Effect.READ:
            called = self._calls.get(part.call_id)
            raw = called.arguments if called is not None else ""
            return made(
                message.created_at, ActivityVia.AI, _arguments(raw), part.result_type, part.result
            )
        card_id = card_id_of(part)
        card = self._cards.get(card_id) if card_id is not None else None
        done = done_of(card) if card is not None else None
        if card is not None and done is not None and card.decided_at is not None:
            return made(
                card.decided_at,
                ActivityVia.CONFIRMED,
                {**card.arguments_json, "reason": card.reason},
                card.result_type or "",
                done,
            )
        return None

    def replies(self) -> list[int]:
        return sorted({row.user_message_id for row in self.rows if row.user_message_id is not None})

    def entry(self, row: _Row, tokens: dict[int, ReplyTokens]) -> ActivityEntry:
        arguments = dict(row.arguments)
        reason = arguments.pop("reason", "")
        undone_at = self._undone.get((row.message_id, row.call_id))
        return ActivityEntry(
            conversation_id=row.conversation.id,
            conversation_title=row.conversation.title,
            own=row.conversation.user_id == self._viewer.id,
            message_id=row.message_id,
            call_id=row.call_id,
            at=row.at,
            user_id=row.conversation.user_id,
            user_name=row.user_name,
            via=row.via,
            tool=row.tool,
            arguments=arguments,
            reason=reason if isinstance(reason, str) else "",
            result_type=row.result_type,
            result=row.result,
            tokens=tokens.get(row.user_message_id or 0, ReplyTokens(input=None, output=None)),
            undo=self._undo(row.tool, row.result, undone=undone_at is not None),
            undone_at=undone_at,
        )

    def _undo(self, name: str, result: dict[str, Any], *, undone: bool) -> ActivityUndo:
        if undone:
            return ActivityUndo.UNDONE
        tool = self._registry.get(name)
        if tool is None or tool.undo is None:
            return ActivityUndo.NO_INVERSE
        if self._registry.nothing_to_undo(tool, result):
            return ActivityUndo.NOTHING_DONE
        if not tool.undoable_by(self._viewer.role):
            return ActivityUndo.NOT_ALLOWED
        return ActivityUndo.UNDOABLE


def _arguments(raw: str) -> dict[str, Any]:
    """模型給的 JSON 原文。做成了的呼叫都驗過，讀不懂只會是舊的或壞掉的紀錄：當成沒有輸入。"""
    try:
        parsed = json.loads(raw)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


async def _reply_tokens(
    session: AsyncSession, user_messages: Sequence[int]
) -> dict[int, ReplyTokens]:
    """每一句話的回覆花了多少。有一次呼叫沒回報那一格，那一格就是 `None`：只加知道的會是一個
    看起來像總數、其實少算的數（用量頁的命中率另有自己的分母規則，這裡不是比例）。"""
    if not user_messages:
        return {}
    rows = await session.execute(
        select(
            AiCall.message_id,
            func.count(),
            func.count(AiCall.input_tokens),
            func.sum(AiCall.input_tokens),
            func.count(AiCall.output_tokens),
            func.sum(AiCall.output_tokens),
        )
        .where(AiCall.message_id.in_(user_messages))
        .group_by(AiCall.message_id)
    )
    return {
        int(message): ReplyTokens(
            input=int(spent_in or 0) if known_in == calls else None,
            output=int(spent_out or 0) if known_out == calls else None,
        )
        for message, calls, known_in, spent_in, known_out, spent_out in rows
        if message is not None
    }
