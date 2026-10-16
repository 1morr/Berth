"""Feed 的 Route 拆成劇集、電影各一欄（M4 票 105、brief §19 2026-10-16）。

`rss_feeds.route_id` 改名為 `tv_route_id`，加 `movie_route_id`。Route 分類型，一條只收一種，
所以 Feed 上兩格都要填：Mikan 的劇場版不會因為有兩條電影 Route 而停在待綁定。

**能推就推**：原本那一條寫進它那一種的那一欄（從 Media 頁訂閱的電影 Feed、票 21 選了 Movies 的
一般 Feed）；之後還是 `NULL` 的那一欄，那一種的啟用中 Route 只有一條時就填它，否則留 `NULL` 給人選
（畫面標「要選 Route」）。

**升版**：改名用原生 `RENAME COLUMN`，外鍵跟著走；加欄位同 `f4b9d2e6a157` 寫成原文（Alembic 的
`add_column` 遇到外鍵會改走 `ALTER ... ADD CONSTRAINT` 而拒絕）。**降版**：一般的 Feed 取劇集
那一欄、沒有才取電影那一欄（票 21 之前只有一格），訂閱電影的 Feed 反過來；SQLite 刪帶外鍵的
欄位只能重建表。

Revision ID: bec5947663f5
Revises: a6c3e9f2b815
Create Date: 2026-10-16 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bec5947663f5"
down_revision: str | None = "a6c3e9f2b815"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: 欄名 → Route 的 `collection_type`。
_COLUMNS = (("tv_route_id", "tvshows"), ("movie_route_id", "movies"))


def upgrade() -> None:
    op.execute("ALTER TABLE rss_feeds RENAME COLUMN route_id TO tv_route_id")
    op.execute(
        "ALTER TABLE rss_feeds ADD COLUMN movie_route_id INTEGER"
        " REFERENCES routes (id) ON DELETE SET NULL"
    )
    op.execute(
        "UPDATE rss_feeds SET movie_route_id = tv_route_id, tv_route_id = NULL"
        " WHERE tv_route_id IN (SELECT id FROM routes WHERE collection_type = 'movies')"
    )
    for column, kind in _COLUMNS:
        only = f"SELECT id FROM routes WHERE enabled = 1 AND collection_type = '{kind}'"
        op.execute(
            f"UPDATE rss_feeds SET {column} = ({only})"
            f" WHERE {column} IS NULL AND (SELECT count(*) FROM ({only})) = 1"
        )


def downgrade() -> None:
    op.execute(
        "UPDATE rss_feeds SET tv_route_id = CASE WHEN media_id LIKE 'movie:%'"
        " THEN coalesce(movie_route_id, tv_route_id) ELSE coalesce(tv_route_id, movie_route_id) END"
    )
    with op.batch_alter_table("rss_feeds", schema=None) as batch_op:
        batch_op.drop_column("movie_route_id")
        batch_op.alter_column("tv_route_id", existing_type=sa.Integer(), new_column_name="route_id")
