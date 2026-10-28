"""確認卡上逐列選的 Route（M5 票 23b，plan §2.6）。

- `proposals.routes_json`：核准時人在卡片上逐列選的 Route（JSON 清單，沒得選的列是 `null`）。
  作品放得進的 Route 不只一條時，提出時把可選清單存進 `preview_json`，`decide` 只收清單裡的；
  執行時用它蓋過存下參數裡的 `route_id`。

既有的列留 `NULL`：票 23b 之前提出的卡片沒有存可選清單，照原本存下的 Route 執行。

Revision ID: c2f6a8d4e917
Revises: a9c3e5f1b742
Create Date: 2026-10-28 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c2f6a8d4e917"
down_revision: str | None = "a9c3e5f1b742"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 原生 `ADD COLUMN`、不重建表（同 `c4e7a9d2b158`）。
    op.add_column("proposals", sa.Column("routes_json", sa.Text(), nullable=True))


def downgrade() -> None:
    # SQLite 刪欄位只能重建表（同 `3f6c0a7d94e2`）。
    with op.batch_alter_table("proposals", schema=None) as batch_op:
        batch_op.drop_column("routes_json")
