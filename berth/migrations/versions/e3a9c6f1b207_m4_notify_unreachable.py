"""使用者上一次收不到通知的時刻與原文（M4 票 128，plan §11.5〈通知〉的「故障」）。

原生 `ADD COLUMN`、不用 batch，理由同 `d5e8a2c7f914`：`detail` 的 `server_default` 留在欄位上，
模型也宣告同一個。既有的使用者是 `NULL` 與空字串（沒有收不到過）。

`notifications.status` 多一個值 `abandoned` 不必改表：`native_enum=False` 是沒有 CHECK 的
VARCHAR（同 `IssueType` 之後加的那幾種）。

Revision ID: e3a9c6f1b207
Revises: d5e8a2c7f914
Create Date: 2026-10-21 22:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e3a9c6f1b207"
down_revision: str | None = "d5e8a2c7f914"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("notify_unreachable_at", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("notify_unreachable_detail", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    # SQLite 刪欄位只能重建表；降版那條測試比的是欄位，不是 DDL 原文。
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("notify_unreachable_detail")
        batch_op.drop_column("notify_unreachable_at")
