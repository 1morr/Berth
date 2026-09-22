"""M2 的 issues 表（plan §2.4、brief §9.1、票 05）。

十一種型別的封閉集合（`domain.IssueType`）——對帳的七種加上管線已經在用的四種。管線從這一票
起兩邊都寫：時間線一筆 `issue_detected` 事件，清單一列 `issues`。

**唯一索引是 partial 的**：`(type, subject)` 只在 `status = 'open'` 上唯一。決定過的那幾筆留著
當歷史，同一條路徑再出問題時開的是新的一筆；蓋住全部的話一條路徑一輩子只能出一次問題。
SQLite 3.8.0 起支援 partial index，而 Berth 的下限遠高於它（`db/__init__.py`）。

`subject` 是一個**存下來的**欄位，plan §2.4 的欄位表上沒有它：那一段說「`subject` 依型別取」，
而取出來的值要落在某處唯一索引才守得住（理由寫在 `models/issue.py`）。

Revision ID: a71c4e08b5d2
Revises: 9d4f1b6e2a70
Create Date: 2026-09-22 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a71c4e08b5d2"
down_revision: str | None = "9d4f1b6e2a70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: `domain.IssueType` 的十一個 value。migration 抄一份而不是 import：跑過的 migration 描述的是
#: **那一刻**的 schema，enum 之後增刪不該改寫已經套用過的 DDL（`native_enum=False`，所以它只是
#: 一個 VARCHAR 加 CHECK）。
_TYPES = (
    "missing_files",
    "client_error",
    "client_removed",
    "unknown_torrent",
    "jellyfin_item_unresolved",
    "library_link_missing",
    "source_missing",
    "inode_mismatch",
    "orphan_complete",
    "unmanaged_library_file",
    "job_without_files",
)

_STATUSES = ("open", "resolved", "ignored")


def upgrade() -> None:
    op.create_table(
        "issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.Enum(*_TYPES, name="issuetype", native_enum=False), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("job_hash", sa.Text(), nullable=True),
        sa.Column("ledger_id", sa.Integer(), nullable=True),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("detail_json", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.Enum(*_STATUSES, name="issuestatus", native_enum=False), nullable=False
        ),
        sa.Column("detected_at", sa.Text(), nullable=False),
        sa.Column("resolved_at", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_issues")),
    )
    with op.batch_alter_table("issues", schema=None) as batch_op:
        batch_op.create_index(
            "ix_issues_open_subject",
            ["type", "subject"],
            unique=True,
            sqlite_where=sa.text("status = 'open'"),
        )
        batch_op.create_index(
            "ix_issues_status_detected_at", ["status", "detected_at"], unique=False
        )
        batch_op.create_index("ix_issues_job_hash", ["job_hash"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("issues", schema=None) as batch_op:
        batch_op.drop_index("ix_issues_job_hash")
        batch_op.drop_index("ix_issues_status_detected_at")
        batch_op.drop_index("ix_issues_open_subject")

    op.drop_table("issues")
