"""側面板的對話與 AI 的觀測（plan §2.6、§11.6〈觀測〉，M5 票 11）。

- **`ai_conversations`**：一段對話屬於一個人。歷史是 pydantic-ai 的 `ModelMessage` 序列，以
  `ModelMessagesTypeAdapter` 存成 JSON，**只有伺服器寫**：前端每次只送最後一則使用者訊息
  （brief §20.24：`VercelAIAdapter` 預設照收前端送回的歷史與核准）。`id` 是前端 `useChat` 的
  chat id，第一次送訊息時建立。
- **`ai_runs`**：一則回覆一列，數字**每次模型呼叫之後當場加上去**——被防護中止、出錯、被關掉的
  那一輪也有（brief §20.24：`on_complete` 不會被呼叫）。`stop_reason` 是 `NULL` 就是還在跑。
- **`ai_calls`**：每次模型呼叫一列，成敗都記。快取讀寫**照原樣存，`NULL` 是不知道**，不當 0
  （研究 C5）；費用認不得模型也是 `NULL`。
- **`ai_tool_calls`**：每次工具呼叫一列：命令名、參數、結果的分類（`AiToolOutcome`）。

刪人連他的對話一起刪（`CASCADE`），刪對話連它的 run 一起刪。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from berth.domain import AiProvider, AiStopReason, AiToolOutcome
from berth.models.base import Base
from berth.models.types import UtcDateTime, enum_column, utcnow


class AiConversation(Base):
    __tablename__ = "ai_conversations"
    __table_args__ = (Index("ix_ai_conversations_user_id", "user_id"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    #: `ModelMessagesTypeAdapter` 的 JSON。
    history_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class AiRun(Base):
    __tablename__ = "ai_runs"
    __table_args__ = (
        Index("ix_ai_runs_conversation_id", "conversation_id"),
        # 用量頁（票 21）以日為單位數。
        Index("ix_ai_runs_started_at", "started_at"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE")
    )
    #: 替誰跑的（`ai:<user id>` 的那個人）。
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[AiProvider] = mapped_column(enum_column(AiProvider))
    #: 設定裡的模型名（服務自己報的名字在 `ai_calls.model`）。
    model: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    #: `NULL` 是還在跑。
    stop_reason: Mapped[AiStopReason | None] = mapped_column(
        enum_column(AiStopReason), default=None
    )
    #: 出錯時的原文（key 已遮掉）。
    error: Mapped[str] = mapped_column(Text, default="")
    requests: Mapped[int] = mapped_column(default=0)
    tool_calls: Mapped[int] = mapped_column(default=0)
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    #: 各次呼叫的合計；有一次是不知道，合計就是不知道。
    cache_read_tokens: Mapped[int | None] = mapped_column(default=0)
    cache_write_tokens: Mapped[int | None] = mapped_column(default=0)
    #: 估計費用（美元）；有一次算不出來，合計就是 `NULL`。
    cost_usd: Mapped[float | None] = mapped_column(Float, default=0.0)


class AiCall(Base):
    __tablename__ = "ai_calls"
    __table_args__ = (Index("ix_ai_calls_run_id", "run_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("ai_runs.id", ondelete="CASCADE"))
    #: 這一輪的第幾次模型呼叫，從 1 起。
    step: Mapped[int]
    #: 服務報的模型名；出錯沒有回應時是設定裡的名字。
    model: Mapped[str] = mapped_column(Text)
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    cache_read_tokens: Mapped[int | None] = mapped_column(default=None)
    cache_write_tokens: Mapped[int | None] = mapped_column(default=None)
    cost_usd: Mapped[float | None] = mapped_column(Float, default=None)
    #: 模型說它為什麼停（`stop`、`length`、`tool_call`…）；出錯是空字串。
    finish_reason: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[int] = mapped_column(default=0)
    #: 呼叫失敗的原文（key 已遮掉）；成功是空字串。
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class AiToolCall(Base):
    __tablename__ = "ai_tool_calls"
    __table_args__ = (Index("ix_ai_tool_calls_run_id", "run_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("ai_runs.id", ondelete="CASCADE"))
    #: 發出這個呼叫的是第幾次模型呼叫（`ai_calls.step`）。
    step: Mapped[int]
    #: 命令登錄表的名字（`why_not.explain`），不是給模型的工具名。
    command: Mapped[str] = mapped_column(Text)
    #: 參數的 JSON，截在 2000 字。
    args_json: Mapped[str] = mapped_column(Text, default="{}")
    outcome: Mapped[AiToolOutcome] = mapped_column(enum_column(AiToolOutcome))
    #: 拒絕的理由、錯誤的原文；成功是空字串。
    detail: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
