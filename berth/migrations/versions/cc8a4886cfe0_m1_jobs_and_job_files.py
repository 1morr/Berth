"""M1 的兩張表：jobs 與 job_files（plan §2.3、票 09）。

`jobs.hash` 是 info hash 本身，不是流水號——「同一個 torrent 送兩次」因此在資料庫層就是
同一列（plan §3.3）。`job_files` 這一票只建表，它的第一批列由票 10 的 `metadata_ready` 寫。

順帶替 `media` 加上 `folder_frozen`：資料夾名在送單成功那一刻定死（plan §2.2、brief §4.5），
而那件事發生在這一票，所以開關與 `jobs` 同一條 migration。

Revision ID: cc8a4886cfe0
Revises: 5225422c03ef
Create Date: 2026-09-10 16:20:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cc8a4886cfe0"
down_revision: str | None = "5225422c03ef"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_STATE = sa.Enum(
    "requested",
    "submitted",
    "submit_failed",
    "metadata_ready",
    "downloading",
    "stalled",
    "missing_files",
    "client_error",
    "client_removed",
    "completed",
    "planning",
    "review",
    "importing",
    "imported",
    "import_failed",
    "removed",
    name="jobstate",
    native_enum=False,
)

FILE_KIND = sa.Enum(
    "video",
    "subtitle",
    "font",
    "audio",
    "image",
    "archive",
    "sample",
    "disc",
    "extra",
    "other",
    name="filekind",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("hash", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column(
            "trigger",
            sa.Enum("manual", "rss", "reimport", name="jobtrigger", native_enum=False),
            nullable=False,
        ),
        sa.Column("trigger_ref", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("media_id", sa.Text(), nullable=True),
        sa.Column("route_id", sa.Integer(), nullable=True),
        sa.Column("state", JOB_STATE, nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("save_path", sa.Text(), nullable=False),
        sa.Column("content_path", sa.Text(), nullable=False),
        sa.Column("total_size", sa.Integer(), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("client_state", sa.Text(), nullable=False),
        sa.Column("added_at", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.Text(), nullable=True),
        sa.Column("imported_at", sa.Text(), nullable=True),
        sa.Column("last_seen_in_client_at", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["media_id"],
            ["media.id"],
            name=op.f("fk_jobs_media_id_media"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["route_id"],
            ["routes.id"],
            name=op.f("fk_jobs_route_id_routes"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_jobs_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("hash", name=op.f("pk_jobs")),
    )
    op.create_table(
        "job_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_hash", sa.Text(), nullable=False),
        sa.Column("rel_path", sa.Text(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("kind", FILE_KIND, nullable=True),
        sa.Column("release_info_json", sa.Text(), nullable=True),
        sa.Column("mediainfo_json", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_hash"],
            ["jobs.hash"],
            name=op.f("fk_job_files_job_hash_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_files")),
        sa.UniqueConstraint("job_hash", "rel_path", name="uq_job_files_job_hash_rel_path"),
    )
    op.create_index("ix_job_files_job_hash", "job_files", ["job_hash"], unique=False)

    # `media.folder_name` 從「跟著 TMDB 的標題走」變成「定死了」的那個開關（plan §2.2）。
    # 既有的列一律是 false：這一票之前沒有任何東西送過單，也就沒有任何一個資料夾名落過地。
    with op.batch_alter_table("media", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("folder_frozen", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    with op.batch_alter_table("media", schema=None) as batch_op:
        batch_op.alter_column("folder_frozen", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("media", schema=None) as batch_op:
        batch_op.drop_column("folder_frozen")
    op.drop_index("ix_job_files_job_hash", table_name="job_files")
    op.drop_table("job_files")
    op.drop_table("jobs")
