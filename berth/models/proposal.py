"""確認卡（Proposal，M5 票 10，plan §11.6〈對話核心〉、CONTEXT.md 的 Proposal）。

AI 想做、但要人按的一次工具呼叫：不可逆的命令永遠是這一種（brief §14），之後的檢查也能把一次可逆
的呼叫降成它（票 11）。**它是獨立的一列，不是側面板的狀態**：M6 的背景接管與 M7 的 Discord 按鈕都
回到這一張表。

- 輸入存模型給的、驗過的那一份（`arguments_json`）；**卡上講的「會發生什麼」另存一份**
  （`preview_json`，型別名在 `preview_type`）：人按確認時同意的是他看到的那一份。
- `user_id` 是要它的那個人（只有他按得到，2026-10-24 使用者選定），`conversation_id` 與
  `call_id` 指回出自哪一則對話的哪一次呼叫；M6 的背景任務兩者都是空的。人或對話不在了，卡片
  照樣留著當紀錄（`SET NULL`）。
- 結果（`result_type` + `result_json`）是登錄表的結果型別或一份 `Refusal`，與對話裡的
  `ToolResultPart` 同形。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from berth.domain import ProposalCause, ProposalStatus
from berth.models.base import Base
from berth.models.types import JsonText, UtcDateTime, enum_column, utcnow


class Proposal(Base):
    __tablename__ = "proposals"
    # 一則對話的卡片：讀對話時一起讀。
    __table_args__ = (Index("ix_proposals_conversation_id", "conversation_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    #: 登錄表的工具名（`services/tools.py`）。
    tool: Mapped[str] = mapped_column(Text)
    arguments_json: Mapped[dict[str, Any]] = mapped_column(JsonText)
    #: 卡上那一段的型別名（`IndexerAddition`…）：前端依它畫。
    preview_type: Mapped[str] = mapped_column(Text)
    preview_json: Mapped[dict[str, Any]] = mapped_column(JsonText)
    #: AI 給的理由，原文。
    reason: Mapped[str] = mapped_column(Text, default="")
    cause: Mapped[ProposalCause] = mapped_column(enum_column(ProposalCause))
    status: Mapped[ProposalStatus] = mapped_column(enum_column(ProposalStatus))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL")
    )
    #: 模型那一次工具呼叫的 id（`ToolCallPart.id`）。
    call_id: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    result_type: Mapped[str | None] = mapped_column(Text)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JsonText)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
