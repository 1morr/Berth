"""側面板的其餘防護（M5 票 20，plan §2.6）。

- `ai_runs.continues`：使用者對哪一輪按了「繼續」；唯一索引讓一輪只能被繼續一次。沒有外鍵：指的是
  同一段對話裡的一輪，刪對話時一起刪。
- `ai_tool_calls.truncated`：交給模型的結果是截過的。既有的列是 `false`。

降版拿掉兩欄。

Revision ID: c4e7a9d2b158
Revises: 78a62163b817
Create Date: 2026-10-27 20:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4e7a9d2b158"
down_revision: str | None = "78a62163b817"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 原生 `ADD COLUMN`、不重建表：SQLite 重建時外鍵的順序不固定，降版再升版的 schema 會不同。
    op.add_column("ai_runs", sa.Column("continues", sa.Text(), nullable=True))
    op.create_index("ix_ai_runs_continues", "ai_runs", ["continues"], unique=True)
    op.add_column(
        "ai_tool_calls",
        sa.Column("truncated", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("ai_tool_calls", "truncated")
    op.drop_index("ix_ai_runs_continues", table_name="ai_runs")
    op.drop_column("ai_runs", "continues")
