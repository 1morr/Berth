"""助理的對話 `conversations`、`conversation_messages`，與 `ai_calls.conversation_id`（M5 票 08）。

兩張新表，`ai_calls` 多一欄可為空的出處；既有的資料不動。`ai_calls.origin` 多一個值
`conversation`，那一欄是 VARCHAR（`native_enum=False`），不必改表。

Revision ID: 13c178a92497
Revises: 2b74d84a462c
Create Date: 2026-10-24 13:49:38.644846
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "13c178a92497"
down_revision: str | None = "2b74d84a462c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: 抄一份而不是 import：跑過的 migration 描述的是那一刻的 schema（同 `a71c4e08b5d2`）。
_KINDS = ("user", "model", "tools", "notice")


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_conversations_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
    )
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.create_index(
            "ix_conversations_user_id_updated_at", ["user_id", "updated_at"], unique=False
        )

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Enum(*_KINDS, name="messagekind", native_enum=False), nullable=False),
        sa.Column("parts_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_conversation_messages_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversation_messages")),
    )
    with op.batch_alter_table("conversation_messages", schema=None) as batch_op:
        batch_op.create_index(
            "ix_conversation_messages_conversation_id", ["conversation_id"], unique=False
        )

    with op.batch_alter_table("ai_calls", schema=None) as batch_op:
        batch_op.add_column(sa.Column("conversation_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_ai_calls_conversation_id_conversations"),
            "conversations",
            ["conversation_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("ai_calls", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_ai_calls_conversation_id_conversations"), type_="foreignkey"
        )
        batch_op.drop_column("conversation_id")
    with op.batch_alter_table("conversation_messages", schema=None) as batch_op:
        batch_op.drop_index("ix_conversation_messages_conversation_id")
    op.drop_table("conversation_messages")
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.drop_index("ix_conversations_user_id_updated_at")
    op.drop_table("conversations")
