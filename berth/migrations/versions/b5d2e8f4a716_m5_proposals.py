"""Proposal：等人確認的命令存成一列（M5 票 08，plan §2.6）。

新表，沒有既有資料要搬。`conversation_id` 還沒有外鍵：對話表在票 11。

Revision ID: b5d2e8f4a716
Revises: a8c3f6e1d254
Create Date: 2026-10-27 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b5d2e8f4a716"
down_revision: str | None = "a8c3f6e1d254"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: 抄一份而不是 import：跑過的 migration 描述的是那一刻的 schema（同 `a71c4e08b5d2`）。
_PROPOSERS = ("person", "system", "ai")
_STATUSES = (
    "pending",
    "detached",
    "approved",
    "rejected",
    "executing",
    "executed",
    "partial",
    "failed",
    "expired",
)


def upgrade() -> None:
    op.create_table(
        "proposals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("arguments_json", sa.Text(), nullable=False),
        sa.Column("arguments_hash", sa.Text(), nullable=False),
        sa.Column("preview_json", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "proposer", sa.Enum(*_PROPOSERS, name="actorkind", native_enum=False), nullable=False
        ),
        sa.Column("conversation_id", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(*_STATUSES, name="proposalstatus", native_enum=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Text(), nullable=False),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.Text(), nullable=True),
        sa.Column("selection_json", sa.Text(), nullable=True),
        sa.Column("results_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_proposals_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"],
            ["users.id"],
            name=op.f("fk_proposals_decided_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_proposals")),
    )
    with op.batch_alter_table("proposals", schema=None) as batch_op:
        batch_op.create_index(
            "ix_proposals_status_expires_at", ["status", "expires_at"], unique=False
        )
        batch_op.create_index("ix_proposals_user_id", ["user_id"], unique=False)
        batch_op.create_index("ix_proposals_conversation_id", ["conversation_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("proposals", schema=None) as batch_op:
        batch_op.drop_index("ix_proposals_conversation_id")
        batch_op.drop_index("ix_proposals_user_id")
        batch_op.drop_index("ix_proposals_status_expires_at")
    op.drop_table("proposals")
