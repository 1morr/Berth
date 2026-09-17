"""拿掉 routes.profile（票 14e）。

Route profile（`standard` / `anime`）已經沒有讀者：解析器改看證據（票 14d），搜尋的季號變體
對所有劇集都做（brief §19）。

**升版不用 batch**。`jobs.route_id` 與 `media.default_route_id` 都是 `ON DELETE SET NULL`，而
migration 跑的時候外鍵開著：batch 重建 `routes` 會在 `DROP TABLE` 那一步把它們全部清成 NULL
（2026-09-17 實測）。SQLite 3.35 起原生的 `DROP COLUMN` 不重建表，這一欄沒有索引、約束或外鍵，
刪得掉。

**降版躲不開重建**：原生 `ADD COLUMN` 加 NOT NULL 一定要帶預設值，而 m0 建的那一欄沒有，
拿掉預設值只能重建表。所以先記下指向 Route 的那兩欄，重建完再寫回去。外鍵在交易裡關不掉
（`PRAGMA foreign_keys` 在交易中是 no-op）。

Revision ID: 9d4f1b6e2a70
Revises: 3f6c0a7d94e2
Create Date: 2026-09-17 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9d4f1b6e2a70"
down_revision: str | None = "3f6c0a7d94e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: 這一版的 schema 裡指向 `routes` 的外鍵：(表, 主鍵, 欄位)。
_POINTERS = (("jobs", "hash", "route_id"), ("media", "id", "default_route_id"))


def upgrade() -> None:
    op.drop_column("routes", "profile")


def downgrade() -> None:
    # 既有的列要有值才補得回 NOT NULL 欄位；拿掉之前的預設就是 `standard`。
    op.add_column(
        "routes",
        sa.Column(
            "profile",
            sa.Enum("standard", "anime", name="profile", native_enum=False),
            nullable=False,
            server_default="standard",
        ),
    )
    bind = op.get_bind()
    saved = {
        table: bind.execute(
            sa.text(f"SELECT {key}, {column} FROM {table} WHERE {column} IS NOT NULL")
        ).all()
        for table, key, column in _POINTERS
    }
    # m0 建的那一欄沒有 server_default：留著的話降版之後的 schema 不是原本那一份。
    with op.batch_alter_table("routes", schema=None) as batch_op:
        batch_op.alter_column("profile", server_default=None)
    for table, key, column in _POINTERS:
        for row_key, route_id in saved[table]:
            bind.execute(
                sa.text(f"UPDATE {table} SET {column} = :route_id WHERE {key} = :key"),
                {"route_id": route_id, "key": row_key},
            )
