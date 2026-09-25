"""RSS Series 的第一批確認，與 Plan 記下它用到的季號與 offset（M3 票 13）。

`rss_series.confirmed`：第一批審核確認過了沒（brief §15）。**既有的一律是 `false`**：它們送進來的
那幾集還沒有人以 RSS Series 為單位看過一眼，升級之後的下一批照第一批處理——多問一次的代價是按一顆
「全部確認」，少問一次的代價是一整季入錯而沒有人看。

`plans.rss_series_id` / `season_hint` / `episode_offset`：算這一份時交給解析器的 RSS Series 與它的
值。既有的 Plan 不回填：當時用了什麼沒有記下來，猜一個寫進去比空著更糟。原生 `ADD COLUMN` 就夠
（理由同 `f2a7c91d4e38`）。

Revision ID: a4f7c2e9d168
Revises: e8a3d6c1f59b
Create Date: 2026-09-26 00:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4f7c2e9d168"
down_revision: str | None = "e8a3d6c1f59b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "rss_series",
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("plans", sa.Column("rss_series_id", sa.Integer(), nullable=True))
    op.add_column("plans", sa.Column("season_hint", sa.Integer(), nullable=True))
    op.add_column("plans", sa.Column("episode_offset", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("plans", "episode_offset")
    op.drop_column("plans", "season_hint")
    op.drop_column("plans", "rss_series_id")
    op.drop_column("rss_series", "confirmed")
