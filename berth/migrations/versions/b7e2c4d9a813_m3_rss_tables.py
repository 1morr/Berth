"""M3 的 RSS 三張表（plan §2.4、brief §15、票 08）。

`rss_feeds`、`rss_series`、`rss_items`，只建票 08 用得到的欄位（理由在 `models/rss.py`）。
`rss_items.error` 與 `rss_feeds.created_at` 不在 plan §2.4 原本的欄位表上，同一票補進去：送單被拒
的那一筆要說得出為什麼還沒送，Feed 清單要排得出順序。

Revision ID: b7e2c4d9a813
Revises: c3d8a6f1b240
Create Date: 2026-09-25 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e2c4d9a813"
down_revision: str | None = "c3d8a6f1b240"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: `domain.FeedKind` 與 `domain.FeedItemStatus` 在這一刻的值（抄一份的理由同 `a71c4e08b5d2`）。
_KINDS = ("mikan",)
_STATUSES = ("unbound", "matched", "downloaded")


def upgrade() -> None:
    op.create_table(
        "rss_feeds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("kind", sa.Enum(*_KINDS, name="feedkind", native_enum=False), nullable=False),
        sa.Column("interval_sec", sa.Integer(), nullable=False),
        sa.Column("last_polled_at", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rss_feeds")),
        sa.UniqueConstraint("url", name=op.f("uq_rss_feeds_url")),
    )
    op.create_table(
        "rss_series",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("mikan_bangumi_id", sa.Integer(), nullable=True),
        sa.Column("mikan_subgroup_id", sa.Integer(), nullable=True),
        sa.Column("title_raw", sa.Text(), nullable=False),
        sa.Column("media_id", sa.Text(), nullable=True),
        sa.Column("route_id", sa.Integer(), nullable=True),
        sa.Column("season", sa.Integer(), nullable=True),
        sa.Column("episode_offset", sa.Integer(), nullable=True),
        sa.Column("bound_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["media_id"],
            ["media.id"],
            name=op.f("fk_rss_series_media_id_media"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["route_id"],
            ["routes.id"],
            name=op.f("fk_rss_series_route_id_routes"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rss_series")),
        sa.UniqueConstraint("key", name=op.f("uq_rss_series_key")),
    )
    op.create_table(
        "rss_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("feed_id", sa.Integer(), nullable=False),
        sa.Column("guid", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("link", sa.Text(), nullable=False),
        sa.Column("torrent_url", sa.Text(), nullable=False),
        sa.Column("info_hash", sa.Text(), nullable=False),
        sa.Column("published_at", sa.Text(), nullable=True),
        sa.Column("seen_at", sa.Text(), nullable=False),
        sa.Column("series_id", sa.Integer(), nullable=True),
        sa.Column("job_hash", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(*_STATUSES, name="feeditemstatus", native_enum=False),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["feed_id"],
            ["rss_feeds.id"],
            name=op.f("fk_rss_items_feed_id_rss_feeds"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["series_id"],
            ["rss_series.id"],
            name=op.f("fk_rss_items_series_id_rss_series"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rss_items")),
        sa.UniqueConstraint("feed_id", "guid", name="uq_rss_items_feed_id_guid"),
    )
    with op.batch_alter_table("rss_items", schema=None) as batch_op:
        batch_op.create_index("ix_rss_items_series_id", ["series_id"], unique=False)
        batch_op.create_index("ix_rss_items_seen_at", ["seen_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("rss_items", schema=None) as batch_op:
        batch_op.drop_index("ix_rss_items_seen_at")
        batch_op.drop_index("ix_rss_items_series_id")
    op.drop_table("rss_items")
    op.drop_table("rss_series")
    op.drop_table("rss_feeds")
