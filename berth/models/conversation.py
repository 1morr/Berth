"""助理的對話與它的每一則（M5 票 08，plan §11.6〈對話核心〉、CONTEXT.md 的 Assistant）。

- **每人自己的**：對話掛在 `users` 的一列上（`ON DELETE CASCADE`：人不在了，他的對話沒有人讀）。
  列表與讀取一律帶著 user id 查，別人的對話在任何一支查詢裡都不存在。
- **一則一列，內容是 JSON**（`parts_json`）：使用者的字、模型的一輪（文字、工具呼叫、provider 要求
  原樣帶回的部分）、Berth 執行工具的結果、說給人聽的停止原因。形狀由 `services.conversations`
  的 pydantic 型別定義、讀出時驗過；這裡只存。重整與下一輪送給模型的歷史都從這裡讀。
- 順序是 `id`：同一則對話一次只有一個回覆在跑（`services.assistant`），寫入是依序的。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from berth.domain import MessageKind
from berth.models.base import Base
from berth.models.types import JsonText, UtcDateTime, enum_column, utcnow


class Conversation(Base):
    __tablename__ = "conversations"
    # 面板的歷史清單：一個人的、最近的在前。
    __table_args__ = (Index("ix_conversations_user_id_updated_at", "user_id", "updated_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    #: 第一句話的開頭，歷史清單上的那一行。
    title: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    #: 最後一則寫進來的時刻。
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (Index("ix_conversation_messages_conversation_id", "conversation_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    kind: Mapped[MessageKind] = mapped_column(enum_column(MessageKind))
    parts_json: Mapped[list[dict[str, Any]]] = mapped_column(JsonText)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
