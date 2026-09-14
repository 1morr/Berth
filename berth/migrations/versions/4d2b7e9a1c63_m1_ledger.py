"""M1 的帳本：ledger（plan §2.3、票 12）。

`target_path` 上是 **unique** index：一條媒體庫路徑只會有一個來源，重跑 importer 補的是
缺的那一筆而不是第二筆（plan §3.3）。`job_hash` 刻意不設外鍵——刪 Job 與清帳本是刪除範圍裡
兩個獨立的旗標（brief §9.2），與 `events` 同一個理由。

plan §2.3 的欄位表之外多三欄（`models/ledger.py`）：`action`（重新規劃會換掉 plan items，
帳本要自己記得當時鏈接的是什麼）、`resolve_attempts` / `resolve_after`（`jellyfin_resolver`
的重試要活過重啟）。inode 與 device 是 TEXT：Windows 的 `st_dev` 超過 SQLite 的有號 64 位元。

Revision ID: 4d2b7e9a1c63
Revises: ebe69db7a48b
Create Date: 2026-09-15 10:12:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4d2b7e9a1c63"
down_revision: str | None = "ebe69db7a48b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ledger",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_hash", sa.Text(), nullable=True),
        sa.Column("source_rel_path", sa.Text(), nullable=False),
        sa.Column("source_abs_path", sa.Text(), nullable=False),
        sa.Column("source_inode", sa.Text(), nullable=False),
        sa.Column("source_dev", sa.Text(), nullable=False),
        sa.Column("target_path", sa.Text(), nullable=False),
        sa.Column("target_inode", sa.Text(), nullable=False),
        sa.Column("media_id", sa.Text(), nullable=True),
        sa.Column("season", sa.Integer(), nullable=True),
        sa.Column("episode_start", sa.Integer(), nullable=True),
        sa.Column("episode_end", sa.Integer(), nullable=True),
        sa.Column("tags_json", sa.Text(), nullable=True),
        sa.Column("plan_item_id", sa.Integer(), nullable=True),
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
        sa.Column("jellyfin_item_id", sa.Text(), nullable=False),
        sa.Column("resolve_attempts", sa.Integer(), nullable=False),
        sa.Column("resolve_after", sa.Text(), nullable=True),
        sa.Column("link_mode", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "ok",
                "target_missing",
                "source_missing",
                "inode_mismatch",
                name="ledgerstatus",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("audit", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("checked_at", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["media_id"], ["media.id"], name=op.f("fk_ledger_media_id_media"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["plan_item_id"],
            ["plan_items.id"],
            name=op.f("fk_ledger_plan_item_id_plan_items"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ledger")),
    )
    with op.batch_alter_table("ledger", schema=None) as batch_op:
        batch_op.create_index("ix_ledger_target_path", ["target_path"], unique=True)
        batch_op.create_index("ix_ledger_job_hash", ["job_hash"], unique=False)
        batch_op.create_index("ix_ledger_resolve_after", ["resolve_after"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("ledger", schema=None) as batch_op:
        batch_op.drop_index("ix_ledger_resolve_after")
        batch_op.drop_index("ix_ledger_job_hash")
        batch_op.drop_index("ix_ledger_target_path")

    op.drop_table("ledger")
