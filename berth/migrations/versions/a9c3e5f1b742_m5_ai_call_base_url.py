"""一次模型呼叫記下打的是哪個端點（M5 票 21b，plan §2.6）。

- `ai_calls.base_url`：實際打的網址（官方端點也寫出來）。查價先用它認服務商（genai-prices），
  用量頁照「端點 + 模型」列價目。

既有的列留 `NULL`：不知道當時打哪裡，也不回填費用（只影響之後的呼叫）。

Revision ID: a9c3e5f1b742
Revises: e6b2d9a4c731
Create Date: 2026-10-28 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9c3e5f1b742"
down_revision: str | None = "e6b2d9a4c731"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 原生 `ADD COLUMN`、不重建表（同 `c4e7a9d2b158`）。
    op.add_column("ai_calls", sa.Column("base_url", sa.Text(), nullable=True))


def downgrade() -> None:
    # SQLite 刪欄位只能重建表（同 `3f6c0a7d94e2`）。
    with op.batch_alter_table("ai_calls", schema=None) as batch_op:
        batch_op.drop_column("base_url")
