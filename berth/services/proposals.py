"""確認卡（Proposal，M5 票 10；plan §11.6〈對話核心〉、brief §6.10 ⑤、§14、CONTEXT.md）。

AI 叫一個工具時走哪一條、要人按的那一條怎麼存、人按了之後怎麼做，都在這裡；機制（預覽、執行、
拒絕的形狀）在 `services.registry`。對話核心（`services.assistant`）、M6 的背景接管與 M7 的
Discord 按鈕都經過這一支，所以它與介面無關。

- **`dispatch`**：工具的 `cause`（不可逆的永遠是、之後的檢查能把一次可逆的呼叫降級）說要人按時
  **不執行**，算出「會發生什麼」（`Registry.preview`）存成一列，回一張卡片給模型——模型讀到的是
  「已提出，等人確認」，不是做好了。做不成的在預覽就拒絕，不出卡片。
- **`confirm`**：只有要它的那個人按得到（2026-10-24 使用者選定），別人的與不存在的說同一句。
  先把狀態搶成 `confirmed`（兩個分頁同時按只有一個做），再**以按的那個人**重驗：角色還拿得到
  這個工具、輸入照樣驗得過、預覽重算照樣成立**而且與卡上那一份一樣**；任何一條不成立、或執行
  被拒，都是 `expired` 並帶著那一份 `Refusal`（什麼都沒改）。成了的照**人看到的那一份預覽**做
  （`Registry.apply`）。
- **`reject`**：記下來，什麼都不做。
- 出自一則對話的卡片，按了之後在那則對話加一則 `decision`：模型下一輪看得到結果，畫面上卡片讀
  `proposals` 的現況。**按了不叫模型**（2026-10-24 使用者選定）：不多花 tokens，模型等下一句話
  再說。
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import MessageKind, ProposalCause, ProposalRefusal, ProposalStatus
from berth.models import Conversation, Proposal
from berth.services.access import admits
from berth.services.commands import Effect, command
from berth.services.conversations import (
    DecisionPart,
    ProposalRejectedError,
    append_message,
    own_conversation,
)
from berth.services.registry import (
    NextStep,
    Refusal,
    Registry,
    ToolContext,
    ToolRefusal,
    cause_of,
)

logger = logging.getLogger(__name__)


class ProposalCard(BaseModel):
    """一張確認卡：工具迴圈回給模型與畫面的那一份（`ToolResultPart` 的 `ProposalCard`），也是讀
    對話時每一張卡的現況。同一個形狀，前端一種卡（`main._document_components` 進 OpenAPI）。"""

    model_config = ConfigDict(frozen=True)

    id: int
    tool: str
    cause: ProposalCause
    #: AI 給的理由，原文。
    reason: str
    #: 卡上「會發生什麼」的型別名（`IndexerAddition`…）與內容：人按確認時同意的就是這一份。
    preview_type: str
    preview: dict[str, Any]
    status: ProposalStatus
    #: 確認之後的結果型別與結果，或 `expired` 時的那一份 `Refusal`；等待中、拒絕的是空的。
    # 沒有預設值：同一個型別也是兩支端點的回應，FastAPI 把有預設值的欄位在回應裡算成必填，兩份
    # schema 就對不起來（`main._document_components` 會紅）。
    result_type: str | None
    result: dict[str, Any] | None
    created_at: datetime
    decided_at: datetime | None


# 派發到直接做的那幾條（可逆的寫入也從這裡做），照最壞的標；不可逆的在這裡只會變成一張卡。
@command(Effect.REVERSIBLE)
async def dispatch(
    registry: Registry,
    name: str,
    arguments: Mapping[str, object],
    context: ToolContext,
    *,
    conversation_id: int | None,
    call_id: str | None,
) -> BaseModel:
    """AI 的一次工具呼叫：結果型別、`Refusal`，或一張等人按的 `ProposalCard`。"""
    call = registry.resolve(name, arguments, context.user)
    if isinstance(call, Refusal):
        return call
    cause = await cause_of(call.tool, context, call.given)
    if cause is None:
        return await registry.run(call, context)
    shown = await registry.preview(call, context)
    if isinstance(shown, Refusal):
        return shown
    assert call.tool.preview_type is not None  # 有 preview 才走得到這裡（`Tool.__post_init__`）
    async with context.sessions() as session:
        row = Proposal(
            tool=call.tool.name,
            arguments_json=call.given.model_dump(mode="json"),
            preview_type=call.tool.preview_type.__name__,
            preview_json=shown.model_dump(mode="json"),
            reason=str(getattr(call.given, "reason", "")),
            cause=cause,
            status=ProposalStatus.PROPOSED,
            user_id=context.user.id,
            conversation_id=conversation_id,
            call_id=call_id,
            created_at=context.now,
        )
        session.add(row)
        await session.commit()
        logger.info("proposal made", extra={"proposal": row.id, "tool": row.tool})
        return card_of(row)


@command(Effect.READ)
async def conversation_of(session: AsyncSession, *, proposal_id: int, user_id: int) -> int | None:
    """這張卡出自哪一則對話（M6 的背景任務沒有）。不是這個人的、不存在的是 `proposal_missing`。"""
    return (await _own(session, proposal_id, user_id)).conversation_id


@command(Effect.READ)
async def of_conversation(
    session: AsyncSession, *, user_id: int, conversation_id: int
) -> list[ProposalCard]:
    """一則對話裡每一張卡的現況，照提出的順序。不是這個人的對話是 `conversation_missing`。"""
    await own_conversation(session, user_id=user_id, conversation_id=conversation_id)
    rows = await session.scalars(
        select(Proposal).where(Proposal.conversation_id == conversation_id).order_by(Proposal.id)
    )
    return [card_of(row) for row in rows]


# 執行的是不可逆的工具（`Registry.apply`）。
@command(Effect.IRREVERSIBLE)
async def confirm(registry: Registry, proposal_id: int, context: ToolContext) -> ProposalCard:
    """以按的那個人（`context.user`）執行這張卡。`context.confirmed` 必須是真的：寫進時間線的是他
    本人，不是 AI。"""
    assert context.confirmed, "a confirmed proposal runs as the person who pressed it"
    async with context.sessions() as session:
        row = await _claim(session, proposal_id, context, ProposalStatus.CONFIRMED)
        tool_name, arguments = row.tool, dict(row.arguments_json)
        preview_type, preview = row.preview_type, dict(row.preview_json)
        await session.commit()

    try:
        outcome = await _execute(registry, tool_name, arguments, preview_type, preview, context)
        status = (
            ProposalStatus.EXPIRED if isinstance(outcome, Refusal) else ProposalStatus.CONFIRMED
        )
    except Exception:
        # bug：可能做了一半，所以不是 `expired`（那是「什麼都沒改」）。原因在 log。
        logger.exception("proposal failed", extra={"proposal": proposal_id, "tool": tool_name})
        outcome = Refusal(
            tool=tool_name, reason="internal_error", detail="", next=NextStep.HAND_OVER
        )
        status = ProposalStatus.CONFIRMED

    async with context.sessions() as session:
        row = await _get(session, proposal_id)
        row.status = status
        row.result_type = type(outcome).__name__
        row.result_json = outcome.model_dump(mode="json")
        await _tell_conversation(session, row, context.now)
        await session.commit()
        logger.info("proposal decided", extra={"proposal": row.id, "status": status})
        return card_of(row)


# 只改這張卡的狀態，但改了就回不去（按過的卡不能再按）。
@command(Effect.IRREVERSIBLE)
async def reject(proposal_id: int, context: ToolContext) -> ProposalCard:
    """記下拒絕，什麼都不做。"""
    async with context.sessions() as session:
        row = await _claim(session, proposal_id, context, ProposalStatus.REJECTED)
        await _tell_conversation(session, row, context.now)
        await session.commit()
        logger.info("proposal decided", extra={"proposal": row.id, "status": row.status})
        return card_of(row)


def result_models(registry: Registry) -> tuple[type[BaseModel], ...]:
    """`ToolResultPart.result_type` 的全部可能：每一個工具的結果型別、`Refusal`，與變成確認卡時的
    `ProposalCard`（`main._document_components` 照它產 `ToolResultType`）。"""
    return (*registry.frontend_models(), ProposalCard)


def card_of(row: Proposal) -> ProposalCard:
    return ProposalCard(
        id=row.id,
        tool=row.tool,
        cause=row.cause,
        reason=row.reason,
        preview_type=row.preview_type,
        preview=row.preview_json,
        status=row.status,
        result_type=row.result_type,
        result=row.result_json,
        created_at=row.created_at,
        decided_at=row.decided_at,
    )


async def _execute(
    registry: Registry,
    tool_name: str,
    arguments: dict[str, Any],
    preview_type: str,
    preview: dict[str, Any],
    context: ToolContext,
) -> BaseModel:
    """按下去的當下重驗，成立的照人看到的那一份做。"""
    tool = registry.get(tool_name)
    if tool is not None and not admits(tool.access, context.user.role):
        return Refusal(
            tool=tool_name, reason=ToolRefusal.NOT_ALLOWED, detail="", next=NextStep.GIVE_UP
        )
    call = registry.resolve(tool_name, arguments, context.user)
    if isinstance(call, Refusal):
        # 這一版沒有這個工具了，或它的輸入改了形狀。
        return call
    fresh = await registry.preview(call, context)
    if isinstance(fresh, Refusal):
        return fresh
    shown = _shown(call.tool.preview_type, preview_type, preview)
    if shown is None or shown != fresh:
        # 讀不回存下的那一份（這一版改了預覽的型別或形狀），或重算的與它不一樣：都還沒動任何東西。
        return Refusal(tool=tool_name, reason=ToolRefusal.CHANGED, detail="", next=NextStep.GIVE_UP)
    return await registry.apply(call, context, shown)


def _shown(
    model: type[BaseModel] | None, stored_type: str, stored: dict[str, Any]
) -> BaseModel | None:
    """存下的那一份預覽，照這一版的型別讀回來；讀不回來是 `None`。"""
    if model is None or model.__name__ != stored_type:
        return None
    try:
        return model.model_validate(stored)
    except ValidationError:
        return None


async def _claim(
    session: AsyncSession, proposal_id: int, context: ToolContext, status: ProposalStatus
) -> Proposal:
    """這個人的、還在等的卡，搶成 `status`。兩個分頁同時按，只有一個搶得到。"""
    row = await _own(session, proposal_id, context.user.id)
    claimed = await session.execute(
        update(Proposal)
        .where(Proposal.id == proposal_id, Proposal.status == ProposalStatus.PROPOSED)
        .values(status=status, decided_by=context.user.id, decided_at=context.now)
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount == 0:  # type: ignore[attr-defined]  # UPDATE 的結果是 CursorResult
        raise ProposalRejectedError(ProposalRefusal.ALREADY_DECIDED, str(proposal_id))
    await session.refresh(row)
    return row


async def _own(session: AsyncSession, proposal_id: int, user_id: int) -> Proposal:
    row = await session.get(Proposal, proposal_id)
    if row is None or row.user_id != user_id:
        raise ProposalRejectedError(ProposalRefusal.PROPOSAL_MISSING, str(proposal_id))
    return row


async def _get(session: AsyncSession, proposal_id: int) -> Proposal:
    row = await session.get(Proposal, proposal_id)
    assert row is not None  # 搶到之後不會被刪（沒有刪卡的路）
    return row


async def _tell_conversation(session: AsyncSession, row: Proposal, now: datetime) -> None:
    """出自一則對話的卡，在那則對話加一則 `decision`（模型下一輪看得到）。"""
    if row.conversation_id is None:
        return
    conversation = await session.get(Conversation, row.conversation_id)
    if conversation is None:
        return
    part = DecisionPart(
        proposal_id=row.id,
        tool=row.tool,
        status=row.status,
        result_type=row.result_type,
        result=row.result_json,
    )
    append_message(session, conversation, MessageKind.DECISION, [part], now)
