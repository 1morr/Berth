"""M1 的兩張表：media 與 tmdb_cache（plan §2.2、票 03）。

Revision ID: e13597cc3295
Revises: 8b1e1dc5336b
Create Date: 2026-09-09 14:55:44.175617
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e13597cc3295"
down_revision: str | None = "8b1e1dc5336b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tmdb_cache",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_tmdb_cache")),
    )
    op.create_table(
        "media",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("tmdb_id", sa.Integer(), nullable=False),
        sa.Column(
            "kind", sa.Enum("tv", "movie", name="mediakind", native_enum=False), nullable=False
        ),
        sa.Column("title_en", sa.Text(), nullable=False),
        sa.Column("title_original", sa.Text(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("folder_name", sa.Text(), nullable=False),
        sa.Column("tracked", sa.Boolean(), nullable=False),
        sa.Column("default_route_id", sa.Integer(), nullable=True),
        sa.Column("tmdb_snapshot_json", sa.Text(), nullable=True),
        sa.Column("tmdb_fetched_at", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["default_route_id"],
            ["routes.id"],
            name=op.f("fk_media_default_route_id_routes"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media")),
    )


def downgrade() -> None:
    op.drop_table("media")
    op.drop_table("tmdb_cache")
