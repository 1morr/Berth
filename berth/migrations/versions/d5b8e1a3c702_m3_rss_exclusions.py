"""RSS 的排除條件與跳過理由（M3 票 10）。

`rss_feeds.exclude_json` 與 `rss_series.exclude_json` 是那一層的排除條件（字串清單，
`parser.exclusion` 的格式），既有的列是空清單；`rss_items.skip_json` 是 `excluded` /
`duplicate` 的那一條理由（`domain.SkipReason`），其他狀態是 NULL。全域那一層在 `settings`
的 `rss` 分組，不動表。
`rss_items.status` 多兩個值（`excluded`、`duplicate`）：`native_enum=False` 又沒有 CHECK，
不必改表。原生 `ADD COLUMN` / `DROP COLUMN` 就夠（理由同 `f2a7c91d4e38`）。

Revision ID: d5b8e1a3c702
Revises: a9c4e2f7b315
Create Date: 2026-09-25 22:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5b8e1a3c702"
down_revision: str | None = "a9c4e2f7b315"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "rss_feeds", sa.Column("exclude_json", sa.Text(), nullable=False, server_default="[]")
    )
    op.add_column(
        "rss_series", sa.Column("exclude_json", sa.Text(), nullable=False, server_default="[]")
    )
    op.add_column("rss_items", sa.Column("skip_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("rss_items", "skip_json")
    op.drop_column("rss_series", "exclude_json")
    op.drop_column("rss_feeds", "exclude_json")
