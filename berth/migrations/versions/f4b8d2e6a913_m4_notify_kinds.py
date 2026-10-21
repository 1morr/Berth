"""每個人要收哪幾種通知（M4 票 125，plan §11.5〈通知〉的「種類與收件人」）。

原生 `ADD COLUMN`、不用 batch，理由同 `d5e8a2c7f914`：`server_default` 留在欄位上，模型也宣告
同一個。既有的使用者是 `["ready"]`：票 123 起填了 Discord ID 的人本來就收「可以看了」，升版之後
照收；「正在下載」要自己勾（每一輪一則，比較吵）。

`notifications.kind` 多一個值 `downloading` 不必改表：`native_enum=False` 是沒有 CHECK 的
VARCHAR（同 `e3a9c6f1b207` 的 `abandoned`）。

Revision ID: f4b8d2e6a913
Revises: e3a9c6f1b207
Create Date: 2026-10-22 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f4b8d2e6a913"
down_revision: str | None = "e3a9c6f1b207"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("notify_kinds_json", sa.Text(), nullable=False, server_default='["ready"]'),
    )


def downgrade() -> None:
    # SQLite 刪欄位只能重建表；降版那條測試比的是欄位，不是 DDL 原文。
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("notify_kinds_json")
