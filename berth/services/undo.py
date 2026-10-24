"""結果卡上的撤銷（M5 票 11；plan §11.6〈對話核心〉的「使用者要求的 `reversible` 直接執行，結果卡附
撤銷」）。

AI 做的可逆寫入（送單、訂閱）直接做，卡上附一顆撤銷。撤銷是**人按的**，走那個工具的命令標著的反向
命令（`Tool.undo`，造 `Tool` 時比對過），以按的那個人執行。這一支與介面無關：側面板、M7 的 Discord
按鈕都經過它。

- 找的是**這個人的這則對話**裡那一次工具呼叫做成了的結果，照那一份撤（存下的是 Berth 寫的）。
- 誰按得到照撤銷指著的那一支端點的門禁（AI 送單人人送得了，刪 Job 只有管理員）。
- 撤掉了在對話加一則 `decision`（`UndonePart`）：模型下一輪知道、卡片照它說已撤銷，同一次不再撤
  第二次。撤銷被拒（qBittorrent 連不上）什麼都不記，回那一份 `Refusal`，再按一次會接著做。
"""

from __future__ import annotations

import logging

from berth.domain import MessageKind, UndoRefusal
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
        await own_conversation(session, user_id=context.user.id, conversation_id=conversation_id)
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
    if tool is None or tool.undo is None or done.result_type != tool.result.__name__:
        # 讀取的、要人按的、那一次沒做成的（結果是 `Refusal` 或確認卡）都沒有東西可撤。
        raise UndoRejectedError(UndoRefusal.NOT_UNDOABLE, done.tool)
    if not tool.undoable_by(context.user.role):
        raise UndoRejectedError(UndoRefusal.NOT_ALLOWED, done.tool)

    outcome = await registry.undo(tool, context, done.result)
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
        conversation = await own_conversation(
            session, user_id=context.user.id, conversation_id=conversation_id
        )
        append_message(session, conversation, MessageKind.DECISION, [undone], context.now)
        await session.commit()
    logger.info("tool call undone", extra={"tool": tool.name, "conversation": conversation_id})
    return undone
