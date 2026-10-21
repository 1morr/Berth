"""Feed 的錯誤拆成輪詢與每日補漏兩欄，各記從什麼時候開始一直失敗（M4 票 130，plan §11.5〈巡檢〉）。

M3 票 12 起兩種失敗擠在同一個 `rss_feeds.last_error`：輪詢成功就清空、補漏讀不到再接上去，所以看不出
是哪一種在壞，也說不出壞了多久。巡檢的「一直失敗的 Feed」要兩樣都知道。

- `last_error` 改名 `poll_error`，**舊值整串搬過去**（票面）：裡面可能接著補漏的那一段，下一輪輪詢
  成功時就會換成只有輪詢的。
- `poll_failing_since`：舊值不是空的就從 `last_polled_at` 起算——升版之前已經壞了多久不知道，取看得到
  的最晚那一刻，巡檢至少再等一整天才開 Issue。
- `backfill_error`、`backfill_failing_since` 從空的開始。

降版把兩欄照舊的格式（輪詢在前、`; ` 接補漏）併回 `last_error`。

Revision ID: c5f2a8e4d917
Revises: b7d1e5a3c820
Create Date: 2026-10-22 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c5f2a8e4d917"
down_revision: str | None = "b7d1e5a3c820"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # SQLite 3.25 起原生支援改欄位名，不必 batch 重建整張表。
    op.execute("ALTER TABLE rss_feeds RENAME COLUMN last_error TO poll_error")
    op.add_column("rss_feeds", sa.Column("poll_failing_since", sa.Text(), nullable=True))
    op.add_column(
        "rss_feeds", sa.Column("backfill_error", sa.Text(), nullable=False, server_default="")
    )
    op.add_column("rss_feeds", sa.Column("backfill_failing_since", sa.Text(), nullable=True))
    op.execute(
        "UPDATE rss_feeds SET poll_failing_since = last_polled_at"
        " WHERE poll_error != '' AND last_polled_at IS NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE rss_feeds SET poll_error = poll_error"
        " || CASE WHEN poll_error != '' AND backfill_error != '' THEN '; ' ELSE '' END"
        " || backfill_error"
    )
    op.drop_column("rss_feeds", "backfill_failing_since")
    op.drop_column("rss_feeds", "backfill_error")
    op.drop_column("rss_feeds", "poll_failing_since")
    op.execute("ALTER TABLE rss_feeds RENAME COLUMN poll_error TO last_error")
