"""週報：一週一筆的表，既有的管理員訂閱「週報」（M4 票 131，plan §11.5〈巡檢〉）。

- `weekly_reports`：產生那一刻算好的三段事實（`models/weekly.py`），`week_of` 唯一。
- 既有的管理員補上 `weekly`：新建的管理員預設就訂（`domain.default_notify_kinds`），升版之前就在的
  沒有機會選過這一種，照新的預設補上（同 `b7d1e5a3c820` 的 `waiting`）。一般使用者不動。
  `notifications.kind` 多一個值不必改表（`native_enum=False` 是沒有 CHECK 的 VARCHAR）。

降版把 `weekly` 從每個人的清單上拿掉，連同排著的那幾則（舊版認不得這個種類），再刪表。

Revision ID: a8c3f6e1d254
Revises: c5f2a8e4d917
Create Date: 2026-10-22 22:00:00.000000
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8c3f6e1d254"
down_revision: str | None = "c5f2a8e4d917"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: 寫死在這裡，不 import `domain`：migration 說的是那一刻的值，之後改名不該改寫歷史。
_WEEKLY = "weekly"
_ADMIN = "admin"


def upgrade() -> None:
    op.create_table(
        "weekly_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("week_of", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.Text(), nullable=False),
        sa.Column("ends_at", sa.Text(), nullable=False),
        sa.Column("content_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_weekly_reports")),
    )
    with op.batch_alter_table("weekly_reports", schema=None) as batch_op:
        batch_op.create_index("ix_weekly_reports_week_of", ["week_of"], unique=True)

    bind = op.get_bind()
    admins = bind.execute(
        sa.text("SELECT id, notify_kinds_json FROM users WHERE role = :admin"), {"admin": _ADMIN}
    ).all()
    for user_id, raw in admins:
        kinds = list(json.loads(raw or "[]"))
        if _WEEKLY not in kinds:
            _write(bind, user_id, [*kinds, _WEEKLY])


def downgrade() -> None:
    bind = op.get_bind()
    for user_id, raw in bind.execute(sa.text("SELECT id, notify_kinds_json FROM users")).all():
        kinds = list(json.loads(raw or "[]"))
        if _WEEKLY in kinds:
            _write(bind, user_id, [kind for kind in kinds if kind != _WEEKLY])
    bind.execute(sa.text("DELETE FROM notifications WHERE kind = :kind"), {"kind": _WEEKLY})
    with op.batch_alter_table("weekly_reports", schema=None) as batch_op:
        batch_op.drop_index("ix_weekly_reports_week_of")
    op.drop_table("weekly_reports")


def _write(bind: sa.Connection, user_id: int, kinds: list[str]) -> None:
    bind.execute(
        sa.text("UPDATE users SET notify_kinds_json = :kinds WHERE id = :id"),
        {"kinds": json.dumps(kinds), "id": user_id},
    )
