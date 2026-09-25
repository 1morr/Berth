"""RSS Series 的補舊集（M3 票 12）。

`rss_series.backfilled_at` 是上一次讀它的 Mikan 單一 feed 補舊集或補漏的那一刻；`NULL` 是還沒補過，
下一輪輪詢就補（brief §15「補舊集」、plan §3.2）。`passed_before` 是取消勾選補舊集的那一刻：單一
feed 裡在這之前發佈的記成略過。

既有的已綁定 Mikan RSS Series 從沒被問過要不要補舊集，升級那一刻不替它們一次送出整季：
`passed_before` 補成它的 `created_at`——在那之前的舊集略過，那之後被聚合 feed 捲掉的照樣補回來
（與票 11 把既有 Feed 當成選過同一個取向）。原生 `ADD COLUMN` 就夠（理由同 `f2a7c91d4e38`）。

Revision ID: e8a3d6c1f59b
Revises: c3e9a7f1b204
Create Date: 2026-09-25 23:59:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8a3d6c1f59b"
down_revision: str | None = "c3e9a7f1b204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("rss_series", sa.Column("backfilled_at", sa.Text(), nullable=True))
    op.add_column("rss_series", sa.Column("passed_before", sa.Text(), nullable=True))
    op.execute(
        "UPDATE rss_series SET passed_before = created_at"
        " WHERE media_id IS NOT NULL AND mikan_bangumi_id IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("rss_series", "passed_before")
    op.drop_column("rss_series", "backfilled_at")
