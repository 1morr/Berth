"""拿掉 media.tracked（票 04b）。

「追蹤」不是一個使用者動作，而是一個推導出來的結果（`CONTEXT.md`）：Berth 曾為這部作品
下載、訂閱或入庫過。推導的來源（`jobs`、`ledger`、`rss_rules`）現在一張都還不存在，
所以這個欄位留著只會永遠是 false。票 09 起以 `EXISTS(jobs)` 推導回來。

Revision ID: 5225422c03ef
Revises: e13597cc3295
Create Date: 2026-09-09 20:51:10.346423
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5225422c03ef"
down_revision: str | None = "e13597cc3295"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("media", schema=None) as batch_op:
        batch_op.drop_column("tracked")


def downgrade() -> None:
    with op.batch_alter_table("media", schema=None) as batch_op:
        # 既有的列要有值才補得回一個 NOT NULL 欄位；回到票 04 的語意就是「都還沒追蹤」。
        batch_op.add_column(
            sa.Column("tracked", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    # 但 `e13597cc3295` 建的那一欄**沒有** server_default，所以填完值就要把它拿掉——
    # 否則降版之後的 schema 與當初升上來的那一份不是同一個。
    with op.batch_alter_table("media", schema=None) as batch_op:
        batch_op.alter_column("tracked", server_default=None)
