"""結果卡上的撤銷（M5 票 11；plan §11.6〈對話核心〉的「使用者要求的 `reversible` 直接執行，結果卡附
撤銷」）。

AI 做的可逆寫入（送單、訂閱）直接做，卡上附一顆撤銷。撤銷是**人按的**，走那個工具的命令標著的反向
命令（`Tool.undo`，造 `Tool` 時比對過），以按的那個人執行。這一支與介面無關：側面板、M7 的 Discord
按鈕都經過它。

- 找的是**這則對話**裡那一次工具呼叫做成了的結果，照那一份撤（存下的是 Berth 寫的）。對話要是
  按的人自己的；管理員撤得了任何人的（AI 活動頁看全部，M5 票 14，2026-10-24 使用者選定）。
- **人按了確認的確認卡**（被降級的可逆工具，例如加 Feed）也撤得了（M5 票 14）：位址是那張卡的那一份
  工具結果，照卡上存下的執行結果撤。
- 誰按得到照撤銷指著的那一支端點的門禁（AI 送單人人送得了，刪 Job 只有管理員）。
- 撤掉了在對話加一則 `decision`（`UndonePart`）：模型下一輪知道、卡片照它說已撤銷，同一次不再撤
  第二次。撤銷被拒（qBittorrent 連不上）什麼都不記，回那一份 `Refusal`，再按一次會接著做。
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import MessageKind, Role, UndoRefusal
from berth.models import Conversation, Proposal
from berth.services.auth import AuthenticatedUser
from berth.services.commands import Effect, command
from berth.services.conversations import (
    ToolResultPart,
    UndonePart,
    UndoRejectedError,
    append_message,
    messages_of,
    own_conversation,
    parts_of,
)
from berth.services.proposals import card_id_of, done_of
from berth.services.registry import Refusal, Registry, ToolContext

logger = logging.getLogger(__name__)


# 撤銷呼叫的是各工具的反向命令（刪 Job、刪 Feed 與下載下來的檔），照最壞的那一條標。
@command(Effect.IRREVERSIBLE)
async def undo(
    registry: Registry,
    *,
    conversation_id: int,
    message_id: int,
    call_id: str,
    context: ToolContext,
) -> UndonePart:
    """撤銷這則對話裡、`message_id` 那一則存著的那一次工具呼叫（同一個 call id 可能出現不只一次）。
    回撤銷的結果，或撤銷被拒時的那一份 `Refusal`（沒有存）。"""
    assert context.confirmed, "an undo runs as the person who pressed it"
    async with context.sessions() as session:
        await _conversation(session, context.user, conversation_id)
        done: ToolResultPart | None = None
        for message in await messages_of(session, conversation_id):
            for part in parts_of(message):
                if (
                    isinstance(part, ToolResultPart)
                    and message.id == message_id
                    and part.call_id == call_id
                ):
                    done = part
                elif (
                    isinstance(part, UndonePart)
                    and part.message_id == message_id
                    and part.call_id == call_id
                ):
                    raise UndoRejectedError(UndoRefusal.ALREADY_UNDONE, call_id)
        if done is None:
            raise UndoRejectedError(UndoRefusal.CALL_MISSING, call_id)
        tool = registry.get(done.tool)
        result = await _done_result(session, done)
    if (
        tool is None
        or tool.undo is None
        or result is None
        or registry.nothing_to_undo(tool, result)
    ):
        # 讀取的、不可逆的、那一次沒做成的（結果是 `Refusal`、還沒按或被拒的確認卡）、做成了卻什麼都
        # 沒改的（送單時那一筆本來就在）都沒有東西可撤。
        raise UndoRejectedError(UndoRefusal.NOT_UNDOABLE, done.tool)
    if not tool.undoable_by(context.user.role):
        raise UndoRejectedError(UndoRefusal.NOT_ALLOWED, done.tool)

    outcome = await registry.undo(tool, context, result)
    undone = UndonePart(
        message_id=message_id,
        call_id=call_id,
        tool=tool.name,
        result_type=type(outcome).__name__,
        result=outcome.model_dump(mode="json"),
    )
    if isinstance(outcome, Refusal):
        logger.info("undo refused", extra={"tool": tool.name, "reason": outcome.reason})
        return undone
    async with context.sessions() as session:
        conversation = await _conversation(session, context.user, conversation_id)
        append_message(session, conversation, MessageKind.DECISION, [undone], context.now)
        await session.commit()
    logger.info("tool call undone", extra={"tool": tool.name, "conversation": conversation_id})
    return undone


async def _conversation(
    session: AsyncSession, user: AuthenticatedUser, conversation_id: int
) -> Conversation:
    """撤銷落在哪一則對話：自己的；管理員是任何人的。其他人的與不存在的說同一句。"""
    if user.role is Role.ADMIN:
        found = await session.get(Conversation, conversation_id)
        if found is not None:
            return found
    return await own_conversation(session, user_id=user.id, conversation_id=conversation_id)


async def _done_result(session: AsyncSession, done: ToolResultPart) -> dict[str, Any] | None:
    """那一次做成了的結果：直接做的是那一份工具結果；確認卡是人按了確認、執行成了的那一份
    （`proposals.done_of`）。沒做成的是 `None`。"""
    card_id = card_id_of(done)
    if card_id is None:
        return None if done.result_type == Refusal.__name__ else done.result
    card = await session.get(Proposal, card_id)
    return done_of(card) if card is not None else None
