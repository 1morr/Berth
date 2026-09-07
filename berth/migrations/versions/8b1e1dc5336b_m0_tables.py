"""M0 的五張表：users、sessions、settings、routes、events。

其餘 plan §2 的表在需要它們的里程碑增量加（progress.md 偏差與決定）。

Revision ID: 8b1e1dc5336b
Revises:
Create Date: 2026-09-07 10:40:10.819500
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8b1e1dc5336b"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_hash", sa.Text(), nullable=True),
        sa.Column("media_id", sa.Text(), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
    )
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.create_index(
            "ix_events_job_hash_created_at", ["job_hash", "created_at"], unique=False
        )

    op.create_table(
        "routes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("jellyfin_library_id", sa.Text(), nullable=False),
        sa.Column("jellyfin_library_name", sa.Text(), nullable=False),
        sa.Column(
            "collection_type",
            sa.Enum("movies", "tvshows", name="collectiontype", native_enum=False),
            nullable=False,
        ),
        sa.Column("target_path", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column(
            "profile",
            sa.Enum("standard", "anime", name="profile", native_enum=False),
            nullable=False,
        ),
        sa.Column("medium_auto_import", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "health_status",
            sa.Enum("unknown", "ok", "failed", name="healthstatus", native_enum=False),
            nullable=False,
        ),
        sa.Column("health_detail_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_routes")),
        sa.UniqueConstraint("slug", name=op.f("uq_routes_slug")),
    )
    op.create_table(
        "settings",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_settings")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("jellyfin_user_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("role", sa.Enum("admin", "user", name="role", native_enum=False), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("last_login_at", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("jellyfin_user_id", name=op.f("uq_users_jellyfin_user_id")),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sessions_token_hash")),
    )
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_sessions_user_id"), ["user_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_sessions_user_id"))

    op.drop_table("sessions")
    op.drop_table("users")
    op.drop_table("settings")
    op.drop_table("routes")
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.drop_index("ix_events_job_hash_created_at")

    op.drop_table("events")
