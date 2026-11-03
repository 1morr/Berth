"""單一 RSS Series 的遲到門檻（M5.5 票 11，plan §2.4）。

- `rss_series.overdue_days`：這個字幕組播出後幾天沒入庫算晚；`NULL` 用全域的
  `RssSettings.overdue_days`。一部作品多條訂閱時巡檢取最大值。

既有的列不回填：留空就是照全域（spec〈共同規則〉）。

Revision ID: e5a2c8f4b931
Revises: d7e1b3a5c926
Create Date: 2026-11-04 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5a2c8f4b931"
down_revision: str | None = "d7e1b3a5c926"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 原生 `ADD COLUMN`、不重建表（同 `d7e1b3a5c926`）。
    op.add_column("rss_series", sa.Column("overdue_days", sa.Integer(), nullable=True))


def downgrade() -> None:
    # SQLite 刪欄位只能重建表（同 `d7e1b3a5c926`）。
    with op.batch_alter_table("rss_series", schema=None) as batch_op:
        batch_op.drop_column("overdue_days")
