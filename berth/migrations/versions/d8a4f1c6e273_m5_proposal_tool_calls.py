"""確認卡連回對話裡的那一次工具呼叫（M5 票 13，plan §2.6）。

- `proposals.tool_call_id`：AI 提出的卡片是哪一次 tool call 提的（pydantic-ai 的 `tool_call_id`）。
  恢復那一輪時從「最後一則模型回應裡還沒有結果的呼叫」找回卡片；人提出的是 `NULL`。**不唯一**：
  有的 OpenAI 相容閘道每一輪都從 `call_0` 編起，同一段對話裡找最新的那一張。
- `proposals.detached_at`：使用者沒按就繼續說話、卡片脫離那一輪的時刻。之後的每一輪，模型從
  instructions 知道這幾張卡現在怎麼了（`services.agent`）。

Revision ID: d8a4f1c6e273
Revises: c4e7a9d2b158
Create Date: 2026-10-28 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8a4f1c6e273"
down_revision: str | None = "c4e7a9d2b158"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("proposals", sa.Column("tool_call_id", sa.Text(), nullable=True))
    op.add_column("proposals", sa.Column("detached_at", sa.Text(), nullable=True))
    op.create_index(
        "ix_proposals_conversation_tool_call",
        "proposals",
        ["conversation_id", "tool_call_id"],
        unique=False,
    )


def downgrade() -> None:
    # SQLite 刪欄位只能重建表（同 `3f6c0a7d94e2`）。
    with op.batch_alter_table("proposals", schema=None) as batch_op:
        batch_op.drop_index("ix_proposals_conversation_tool_call")
        batch_op.drop_column("detached_at")
        batch_op.drop_column("tool_call_id")
