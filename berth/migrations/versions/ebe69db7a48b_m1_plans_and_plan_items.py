"""M1 的兩張表：plans 與 plan_items（plan §2.3、票 11）。

`plans.job_hash` 上是一個 **unique** index：一個 Job 只有一份「現在的計劃」，重跑 planning
把它整份改寫而不是再長一列（`models/plan.py` 的理由）。`job_hash` 仍可為 NULL——M2 的重新
入庫以目錄為 Import Source，而 SQLite 的 unique 容得下多個 NULL。

`plan_items` 這一票就寫得滿，只有 `applied_at` 與 `error` 空著：那兩欄是 importer 逐檔
回填的（票 12）。

Revision ID: ebe69db7a48b
Revises: cc8a4886cfe0
Create Date: 2026-09-10 21:58:14.242827
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ebe69db7a48b"
down_revision: str | None = "cc8a4886cfe0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_hash", sa.Text(), nullable=True),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column(
            "engine",
            sa.Enum("rules", "ai", "user", name="planengine", native_enum=False),
            nullable=False,
        ),
        sa.Column("engine_version", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "preplan",
                "auto",
                "pending_review",
                "approved",
                "rejected",
                "applied",
                "failed",
                name="planstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("summary_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("decided_by", sa.Text(), nullable=False),
        sa.Column("decided_at", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["job_hash"], ["jobs.hash"], name=op.f("fk_plans_job_hash_jobs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plans")),
    )
    with op.batch_alter_table("plans", schema=None) as batch_op:
        batch_op.create_index("ix_plans_job_hash", ["job_hash"], unique=True)

    op.create_table(
        "plan_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("job_file_id", sa.Integer(), nullable=True),
        sa.Column("rel_path", sa.Text(), nullable=False),
        sa.Column(
            "action",
            sa.Enum(
                "import",
                "extra",
                "subtitle",
                "skip",
                "unmatched",
                "review",
                name="planaction",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("media_id", sa.Text(), nullable=True),
        sa.Column("season", sa.Integer(), nullable=True),
        sa.Column("episode_start", sa.Integer(), nullable=True),
        sa.Column("episode_end", sa.Integer(), nullable=True),
        sa.Column("tags_json", sa.Text(), nullable=True),
        sa.Column("target_path", sa.Text(), nullable=False),
        sa.Column(
            "confidence",
            sa.Enum("high", "medium", "low", name="confidence", native_enum=False),
            nullable=False,
        ),
        sa.Column("reasons_json", sa.Text(), nullable=True),
        sa.Column("audit", sa.Boolean(), nullable=False),
        sa.Column("applied_at", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_file_id"],
            ["job_files.id"],
            name=op.f("fk_plan_items_job_file_id_job_files"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["media_id"],
            ["media.id"],
            name=op.f("fk_plan_items_media_id_media"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["plans.id"], name=op.f("fk_plan_items_plan_id_plans"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_items")),
    )
    with op.batch_alter_table("plan_items", schema=None) as batch_op:
        batch_op.create_index("ix_plan_items_plan_id", ["plan_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("plan_items", schema=None) as batch_op:
        batch_op.drop_index("ix_plan_items_plan_id")

    op.drop_table("plan_items")
    with op.batch_alter_table("plans", schema=None) as batch_op:
        batch_op.drop_index("ix_plans_job_hash")

    op.drop_table("plans")
