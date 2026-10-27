"""側面板的對話與 AI 的觀測：四張新表（M5 票 11，plan §2.6）。

- `ai_conversations`：一段對話屬於一個人，歷史是伺服器寫的 JSON。
- `ai_runs`：一則回覆一列，每次模型呼叫之後當場加總；`stop_reason` 是 `NULL` 就是還在跑。
- `ai_calls`、`ai_tool_calls`：每次模型呼叫、每次工具呼叫一列。快取讀寫與費用 `NULL` 是不知道。

既有的表不動。降版整四張刪掉。

Revision ID: 78a62163b817
Revises: b5d2e8f4a716
Create Date: 2026-10-27 19:25:02.470318
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "78a62163b817"
down_revision: str | None = "b5d2e8f4a716"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("history_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_ai_conversations_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_conversations")),
    )
    with op.batch_alter_table("ai_conversations", schema=None) as batch_op:
        batch_op.create_index("ix_ai_conversations_user_id", ["user_id"], unique=False)

    op.create_table(
        "ai_runs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("conversation_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "provider",
            sa.Enum("anthropic", "openai", name="aiprovider", native_enum=False),
            nullable=False,
        ),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Text(), nullable=False),
        sa.Column("ended_at", sa.Text(), nullable=True),
        sa.Column(
            "stop_reason",
            sa.Enum(
                "completed",
                "request_limit",
                "token_limit",
                "repeated_call",
                "error",
                "cancelled",
                name="aistopreason",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False),
        sa.Column("tool_calls", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["ai_conversations.id"],
            name=op.f("fk_ai_runs_conversation_id_ai_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_ai_runs_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_runs")),
    )
    with op.batch_alter_table("ai_runs", schema=None) as batch_op:
        batch_op.create_index("ix_ai_runs_conversation_id", ["conversation_id"], unique=False)
        batch_op.create_index("ix_ai_runs_started_at", ["started_at"], unique=False)

    op.create_table(
        "ai_calls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("finish_reason", sa.Text(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["ai_runs.id"], name=op.f("fk_ai_calls_run_id_ai_runs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_calls")),
    )
    with op.batch_alter_table("ai_calls", schema=None) as batch_op:
        batch_op.create_index("ix_ai_calls_run_id", ["run_id"], unique=False)

    op.create_table(
        "ai_tool_calls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("args_json", sa.Text(), nullable=False),
        sa.Column(
            "outcome",
            sa.Enum(
                "ok",
                "warned",
                "blocked",
                "aborted",
                "refused",
                "failed",
                name="aitooloutcome",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["ai_runs.id"],
            name=op.f("fk_ai_tool_calls_run_id_ai_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_tool_calls")),
    )
    with op.batch_alter_table("ai_tool_calls", schema=None) as batch_op:
        batch_op.create_index("ix_ai_tool_calls_run_id", ["run_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("ai_tool_calls", schema=None) as batch_op:
        batch_op.drop_index("ix_ai_tool_calls_run_id")

    op.drop_table("ai_tool_calls")
    with op.batch_alter_table("ai_calls", schema=None) as batch_op:
        batch_op.drop_index("ix_ai_calls_run_id")

    op.drop_table("ai_calls")
    with op.batch_alter_table("ai_runs", schema=None) as batch_op:
        batch_op.drop_index("ix_ai_runs_started_at")
        batch_op.drop_index("ix_ai_runs_conversation_id")

    op.drop_table("ai_runs")
    with op.batch_alter_table("ai_conversations", schema=None) as batch_op:
        batch_op.drop_index("ix_ai_conversations_user_id")

    op.drop_table("ai_conversations")
