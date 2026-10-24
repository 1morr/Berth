"""確認卡 `proposals`（M5 票 10）。

一張新表；既有的資料不動。`conversation_messages.kind` 多一個值 `decision`，那一欄是 VARCHAR
（`native_enum=False`），不必改表。

Revision ID: 9708ccd64def
Revises: 13c178a92497
Create Date: 2026-10-24 15:31:45.031201
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9708ccd64def"
down_revision: str | None = "13c178a92497"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: 抄一份而不是 import：跑過的 migration 描述的是那一刻的 schema（同 `a71c4e08b5d2`）。
_CAUSES = ("irreversible",)
_STATUSES = ("proposed", "confirmed", "rejected", "expired")


def upgrade() -> None:
    op.create_table(
        "proposals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tool", sa.Text(), nullable=False),
        sa.Column("arguments_json", sa.Text(), nullable=False),
        sa.Column("preview_type", sa.Text(), nullable=False),
        sa.Column("preview_json", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "cause", sa.Enum(*_CAUSES, name="proposalcause", native_enum=False), nullable=False
        ),
        sa.Column(
            "status", sa.Enum(*_STATUSES, name="proposalstatus", native_enum=False), nullable=False
        ),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("call_id", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.Text(), nullable=True),
        sa.Column("result_type", sa.Text(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_proposals_conversation_id_conversations"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"],
            ["users.id"],
            name=op.f("fk_proposals_decided_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_proposals_user_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_proposals")),
    )
    with op.batch_alter_table("proposals", schema=None) as batch_op:
        batch_op.create_index("ix_proposals_conversation_id", ["conversation_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("proposals", schema=None) as batch_op:
        batch_op.drop_index("ix_proposals_conversation_id")
    op.drop_table("proposals")
