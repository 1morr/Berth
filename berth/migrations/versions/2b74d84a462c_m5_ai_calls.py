"""用量記錄 `ai_calls`（M5 票 07，plan §11.6〈用量記錄〉）。

一張新表，既有的資料不動。`settings.ai` 是 `settings` 的一列，不必改表。

Revision ID: 2b74d84a462c
Revises: a8c3f6e1d254
Create Date: 2026-10-24 12:05:54.014074
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2b74d84a462c"
down_revision: str | None = "a8c3f6e1d254"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: 抄一份而不是 import：跑過的 migration 描述的是那一刻的 schema（同 `a71c4e08b5d2`）。
_FORMATS = ("anthropic",)
_ORIGINS = ("test",)
_FAILURES = (
    "rate_limited",
    "quota_exhausted",
    "provider_down",
    "auth_failed",
    "model_not_found",
    "unreachable",
    "rejected",
)


def upgrade() -> None:
    op.create_table(
        "ai_calls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column(
            "format", sa.Enum(*_FORMATS, name="apiformat", native_enum=False), nullable=False
        ),
        sa.Column("host", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "origin", sa.Enum(*_ORIGINS, name="aicallorigin", native_enum=False), nullable=False
        ),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column(
            "failure", sa.Enum(*_FAILURES, name="aifailure", native_enum=False), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_ai_calls_user_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_calls")),
    )
    with op.batch_alter_table("ai_calls", schema=None) as batch_op:
        batch_op.create_index("ix_ai_calls_created_at", ["created_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("ai_calls", schema=None) as batch_op:
        batch_op.drop_index("ix_ai_calls_created_at")
    op.drop_table("ai_calls")
