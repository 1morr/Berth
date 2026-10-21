"""既有的管理員訂閱「有 N 件等你處理」（M4 票 127，plan §11.5〈通知〉）。

新建的管理員預設就訂（`domain.default_notify_kinds`）；升版之前就在的管理員沒有機會選過這一種，
照新的預設補上——Berth 平常不必打開的前提是有事時它會說，那一則不該要人先找到勾選才收得到。
一般使用者不動：他們看不到也收不到。

只改資料：`notifications.kind` 多一個值 `waiting` 不必改表（`native_enum=False` 是沒有 CHECK 的
VARCHAR，同 `f4b8d2e6a913` 的 `downloading`）。降版把 `waiting` 從每個人的清單上拿掉，連同排著的
那幾則：舊版認不得這個種類。

Revision ID: b7d1e5a3c820
Revises: f4b8d2e6a913
Create Date: 2026-10-22 16:00:00.000000
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7d1e5a3c820"
down_revision: str | None = "f4b8d2e6a913"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: 寫死在這裡，不 import `domain`：migration 說的是那一刻的值，之後改名不該改寫歷史。
_WAITING = "waiting"
_ADMIN = "admin"


def upgrade() -> None:
    bind = op.get_bind()
    admins = bind.execute(
        sa.text("SELECT id, notify_kinds_json FROM users WHERE role = :admin"), {"admin": _ADMIN}
    ).all()
    for user_id, raw in admins:
        kinds = list(json.loads(raw or "[]"))
        if _WAITING not in kinds:
            _write(bind, user_id, [*kinds, _WAITING])


def downgrade() -> None:
    bind = op.get_bind()
    for user_id, raw in bind.execute(sa.text("SELECT id, notify_kinds_json FROM users")).all():
        kinds = list(json.loads(raw or "[]"))
        if _WAITING in kinds:
            _write(bind, user_id, [kind for kind in kinds if kind != _WAITING])
    bind.execute(sa.text("DELETE FROM notifications WHERE kind = :kind"), {"kind": _WAITING})


def _write(bind: sa.Connection, user_id: int, kinds: list[str]) -> None:
    bind.execute(
        sa.text("UPDATE users SET notify_kinds_json = :kinds WHERE id = :id"),
        {"kinds": json.dumps(kinds), "id": user_id},
    )
