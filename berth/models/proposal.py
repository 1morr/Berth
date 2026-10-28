"""Proposal：等人確認的一個命令，存成一列（plan §2.6、M5 票 08、CONTEXT.md 的 Proposal）。

確認卡要能隔很久才按、在別的地方按、重啟之後按，所以它是一列資料，不是記憶體裡等著的呼叫；
它的生命週期也獨立於提出它的那一輪對話（brief §20.24）。

- **一張卡是同一個命令的一到多列**（`arguments_json` 是清單）：單項卡一列，總覽卡（整個系列送單）
  多列、逐列可取消勾選（`selection_json`），執行後逐列記結果（`results_json`），所以會部分成功。
- **參數存的是過了輸入模型之後的那一份**：執行時用它，不收任何外來的參數。`arguments_hash` 是它的
  雜湊，執行前重算一次比對。
- 提出者是 `user_id` 加 `proposer`（人自己，或 AI 替他）。按得到的是他本人或管理員；執行時的角色
  照他**那一刻**的角色重讀。人不在了，他的卡片也沒有意義（`ON DELETE CASCADE`）。
- `conversation_id` 是提出它的那段對話；人提出的是 `NULL`。對話表在票 11，所以這裡還沒有外鍵。
- `tool_call_id` 連回對話裡提出它的那一次工具呼叫（票 13）：恢復時靠它找回卡片。
- **Route 是唯一能在決定時給的參數**（票 23b）：作品放得進的 Route 不只一條時，提出時把那一列的
  可選清單存進預覽，人在卡片上選、`routes_json` 記下；只收清單裡的。其餘參數照舊不收。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from berth.domain import ActorKind, ProposalStatus
from berth.models.base import Base
from berth.models.types import JsonText, UtcDateTime, enum_column, utcnow


class Proposal(Base):
    __tablename__ = "proposals"
    __table_args__ = (
        # 過期清掃每分鐘問的那一句：還在等的、到期的。
        Index("ix_proposals_status_expires_at", "status", "expires_at"),
        Index("ix_proposals_user_id", "user_id"),
        Index("ix_proposals_conversation_id", "conversation_id"),
        # 恢復那一輪找卡片：同一段對話裡、那一次 tool call 的最新一張（id 不保證唯一，見下）。
        Index("ix_proposals_conversation_tool_call", "conversation_id", "tool_call_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    #: 登錄表的名字，`"<模組>.<函式>"`。
    command: Mapped[str] = mapped_column(Text)
    #: 每一列一份命令輸入（過了輸入模型、`mode="json"`）。
    arguments_json: Mapped[list[dict[str, Any]]] = mapped_column(JsonText)
    #: 命令名與 `arguments_json` 的 SHA-256（`services.proposals.arguments_hash`）。
    arguments_hash: Mapped[str] = mapped_column(Text)
    #: 提出那一刻伺服器算的預覽：命令的效果、旗標與逐列乾跑過了沒（`services.proposals`）。
    preview_json: Mapped[dict[str, Any]] = mapped_column(JsonText)
    #: 替誰提出、按得到的那個人。
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    #: 他自己（`person`）或 AI 替他（`ai`）。
    proposer: Mapped[ActorKind] = mapped_column(enum_column(ActorKind))
    conversation_id: Mapped[str | None] = mapped_column(Text, default=None)
    #: AI 提出的那一次 tool call（pydantic-ai 的 `tool_call_id`，票 13）：恢復那一輪時從它找回卡片。
    #: 人提出的是 `None`。不唯一：有的 OpenAI 相容閘道每一輪都從 `call_0` 編起。
    tool_call_id: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[ProposalStatus] = mapped_column(
        enum_column(ProposalStatus), default=ProposalStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime)
    #: 按的人；人不在了留著決定、清掉是誰。
    decided_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    decided_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    #: 脫離提出它的那一輪的時刻（使用者沒按就繼續說話）。之後每一輪的 instructions 帶上
    #: 這幾張的近況。
    detached_at: Mapped[datetime | None] = mapped_column(UtcDateTime, default=None)
    #: 核准時勾的那幾列（0 起算）；`None` 是全部。
    selection_json: Mapped[list[int] | None] = mapped_column(JsonText, default=None)
    #: 核准時逐列在卡片上選的 Route（M5 票 23b）；只有提出時可選的不只一條的列有值，其餘是 `None`。
    #: 整格 `None` 是哪一列都沒選。執行時蓋過存下參數裡的 `route_id`。
    routes_json: Mapped[list[int | None] | None] = mapped_column(JsonText, default=None)
    #: 核准時逐列在卡片上選的字幕組（M5 票 26）：選項的 `key`；只有提出時存了可選清單的列有值，
    #: 其餘是 `None`。整格 `None` 是哪一列都沒選。執行時用那個選項的參數蓋過存下的。
    subgroups_json: Mapped[list[str | None] | None] = mapped_column(JsonText, default=None)
    #: 核准時逐列選的第一輪（M5 票 26，`PrimeMode` 的值）；只有命令輸入有 `first_batch` 的列有值。
    #: 整格 `None` 是哪一列都沒選（照存下的，預設「下載這些並追之後的」）。
    first_batch_json: Mapped[list[str | None] | None] = mapped_column(JsonText, default=None)
    #: 逐列結果（`services.proposals.RowResult`），執行時每做完一列寫一次；還沒執行是 `None`。
    results_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JsonText, default=None)
