"""Feed 預先綁定的作品與 Route（M3 票 19）。

從 Media 頁建的 Nyaa / acg.rip 搜尋 feed 記下作品、Route 與建它的人：它長出的每一個 RSS Series 直接
綁上（brief §15「從 Media 頁訂閱」）。既有的 Feed 三欄都是 `NULL`，照舊去認作品。

原生 `ADD COLUMN` 就夠（理由同 `7c3e5a9b2d41`）：欄位預設 `NULL`，SQLite 允許帶 `REFERENCES`。
Alembic 的 `add_column` 遇到外鍵會改走 `ALTER ... ADD CONSTRAINT` 而拒絕，所以寫成原文。

Revision ID: f4b9d2e6a157
Revises: c8d2f5a1e734
Create Date: 2026-09-26 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "f4b9d2e6a157"
down_revision: str | None = "c8d2f5a1e734"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: 欄名、型別、指向的表。
_COLUMNS = (
    ("media_id", "TEXT", "media"),
    ("route_id", "INTEGER", "routes"),
    ("user_id", "INTEGER", "users"),
)


def upgrade() -> None:
    for name, kind, target in _COLUMNS:
        op.execute(
            f"ALTER TABLE rss_feeds ADD COLUMN {name} {kind}"
            f" REFERENCES {target} (id) ON DELETE SET NULL"
        )


def downgrade() -> None:
    # SQLite 刪欄位只能重建表；降版那條測試比的是欄位（`PRAGMA table_info`），不是 DDL 原文。
    with op.batch_alter_table("rss_feeds", schema=None) as batch_op:
        for name, _, _ in reversed(_COLUMNS):
            batch_op.drop_column(name)
