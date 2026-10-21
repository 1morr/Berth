"""通知的待送表，使用者的 Discord ID 與通知語言（M4 票 123，plan §11.5〈通知〉）。

`users` 兩欄用原生 `ADD COLUMN`、不用 batch：不重建表，代價是 `server_default` 留在欄位上，
模型也宣告同一個（理由同 `7c3e5a9b2d41`）。既有的使用者是空字串（不收）與 `zh-Hant`。

Revision ID: d5e8a2c7f914
Revises: c1d7e4a9b302
Create Date: 2026-10-21 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5e8a2c7f914"
down_revision: str | None = "c1d7e4a9b302"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: 抄一份而不是 import：跑過的 migration 描述的是那一刻的 schema（同 `a71c4e08b5d2`）。
_KINDS = ("ready",)
_STATUSES = ("pending", "sent")
_LANGUAGES = ("zh-Hant", "en")


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("discord_user_id", sa.Text(), nullable=False, server_default="")
    )
    op.add_column(
        "users",
        sa.Column(
            "notify_language",
            sa.Enum(*_LANGUAGES, name="language", native_enum=False),
            nullable=False,
            server_default="zh-Hant",
        ),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "kind", sa.Enum(*_KINDS, name="notificationkind", native_enum=False), nullable=False
        ),
        sa.Column("content_json", sa.Text(), nullable=False),
        sa.Column("merge_key", sa.Text(), nullable=False),
        sa.Column("not_before", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(*_STATUSES, name="notificationstatus", native_enum=False),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("retry_at", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notifications_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.create_index(
            "ix_notifications_status_not_before", ["status", "not_before"], unique=False
        )
        batch_op.create_index("ix_notifications_user_id", ["user_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.drop_index("ix_notifications_user_id")
        batch_op.drop_index("ix_notifications_status_not_before")
    op.drop_table("notifications")
    # SQLite 刪欄位只能重建表；降版那條測試比的是欄位，不是 DDL 原文。
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("notify_language")
        batch_op.drop_column("discord_user_id")
