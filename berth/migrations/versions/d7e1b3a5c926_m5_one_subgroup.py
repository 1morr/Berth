"""訂閱只綁一個字幕組（M5 票 26，plan §2.4、§2.6）。

- `rss_feeds.subgroup`：關鍵字搜尋 feed 只收這個字幕組的發佈（照發佈名裡的字幕組比對）；
  空字串是每一個字幕組都收（票 26 之前的 Feed、從 Media 頁建的、一般的 Feed）。
- `proposals.subgroups_json`：核准時人在卡片上逐列選的字幕組（JSON 清單，沒得選的列是 `null`）。
  提出時把可選清單存進 `preview_json`，`decide` 只收清單裡的；執行時用選的那一個蓋過存下的參數。

既有的列不改：已經綁了好幾個字幕組的關鍵字 Feed 照舊運作（票 26 第 6 點，不做 migration）。

Revision ID: d7e1b3a5c926
Revises: c2f6a8d4e917
Create Date: 2026-10-28 22:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d7e1b3a5c926"
down_revision: str | None = "c2f6a8d4e917"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 原生 `ADD COLUMN`、不重建表（同 `c4e7a9d2b158`）。
    op.add_column("rss_feeds", sa.Column("subgroup", sa.Text(), nullable=False, server_default=""))
    op.add_column("proposals", sa.Column("subgroups_json", sa.Text(), nullable=True))


def downgrade() -> None:
    # SQLite 刪欄位只能重建表（同 `3f6c0a7d94e2`）。
    with op.batch_alter_table("proposals", schema=None) as batch_op:
        batch_op.drop_column("subgroups_json")
    with op.batch_alter_table("rss_feeds", schema=None) as batch_op:
        batch_op.drop_column("subgroup")
