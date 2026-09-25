"""RSS 的第一輪預覽與 Feed Item 的大小（M3 票 11）。

`rss_feeds.primed_at` 是第一輪預覽選過的那一刻：`NULL` 的 Feed 一筆都不送。既有的 Feed 全是
Mikan（票 08 只認 `mikanani.me`），聚合 feed 沒有歷史要選，所以補成它的 `created_at`——與之後
加 Mikan Feed 時當場寫入是同一個規則。`rss_items.size` 是近似的位元組數，只供預覽顯示。
`rss_feeds.kind` 多兩個值（`nyaa`、`acgrip`）、`rss_items.status` 多一個（`passed`）：
`native_enum=False` 又沒有 CHECK，不必改表。原生 `ADD COLUMN` / `DROP COLUMN` 就夠（理由同
`f2a7c91d4e38`）。

Revision ID: c3e9a7f1b204
Revises: d5b8e1a3c702
Create Date: 2026-09-25 23:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3e9a7f1b204"
down_revision: str | None = "d5b8e1a3c702"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("rss_feeds", sa.Column("primed_at", sa.Text(), nullable=True))
    op.execute("UPDATE rss_feeds SET primed_at = created_at")
    op.add_column("rss_items", sa.Column("size", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("rss_items", "size")
    op.drop_column("rss_feeds", "primed_at")
