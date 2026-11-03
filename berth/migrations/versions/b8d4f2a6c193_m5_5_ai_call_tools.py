"""每次模型呼叫記下送出的工具名（M5.5 票 15，plan §2.6）。

- `ai_calls.tools_json`：這次呼叫送出的工具名（JSON 陣列）。模型說自己沒有某個工具時，從這裡
  查當時到底送了什麼（brief §20.26）。

既有的列不回填：當時送了什麼沒有記下，`NULL` 就是「未記錄」。

Revision ID: b8d4f2a6c193
Revises: e5a2c8f4b931
Create Date: 2026-11-04 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8d4f2a6c193"
down_revision: str | None = "e5a2c8f4b931"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 原生 `ADD COLUMN`、不重建表（同 `e5a2c8f4b931`）。
    op.add_column("ai_calls", sa.Column("tools_json", sa.Text(), nullable=True))


def downgrade() -> None:
    # SQLite 刪欄位只能重建表（同 `e5a2c8f4b931`）。
    with op.batch_alter_table("ai_calls", schema=None) as batch_op:
        batch_op.drop_column("tools_json")
