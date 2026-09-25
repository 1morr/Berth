"""Job 記下來源的發佈時間（M3 票 14：播出日比對）。

`jobs.published_at`：索引站結果的 `publishDate`、或 Feed Item 的發佈時間，送單時跟著存下來。住在 Job
而不是規劃時回頭讀 `rss_items`：手動送單沒有 Feed Item，兩條路徑要同一個地方。

**既有的 RSS Job 從 `rss_items` 回填**（最早帶到它的那一筆，`rss_items.job_hash`）：還沒入庫的那幾筆
重新規劃時才比得到。手動送單的沒有來源可以回填，留空——規劃時照「沒有發佈時間」跳過。
兩欄同型別（`UtcDateTime` 存成 ISO 文字），直接搬原文。

Revision ID: c8d2f5a1e734
Revises: a4f7c2e9d168
Create Date: 2026-09-26 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8d2f5a1e734"
down_revision: str | None = "a4f7c2e9d168"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("published_at", sa.Text(), nullable=True))
    op.execute(
        "UPDATE jobs SET published_at = ("
        " SELECT min(rss_items.published_at) FROM rss_items"
        " WHERE rss_items.job_hash = jobs.hash AND rss_items.published_at IS NOT NULL"
        ") WHERE trigger = 'rss'"
    )


def downgrade() -> None:
    op.drop_column("jobs", "published_at")
