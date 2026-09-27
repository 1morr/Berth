"""RSS Series 記下 Mikan 的番組名與字幕組名（M4 票 13）。

RSS 頁以作品呈現 Series，來源那一格說的是番組 × 字幕組的**名字**，不是 id（brief §15、§19
2026-09-26）。名字取自已經抓過的頁面（自動綁定讀的番組頁、從 Media 頁訂閱時讀的番組頁），不為了顯示
多打 Mikan；既有的留空字串，畫面上沒有就不顯示。原生 `ADD COLUMN` 就夠（理由同 `f2a7c91d4e38`）。

Revision ID: d5c8e2a7f391
Revises: f4b9d2e6a157
Create Date: 2026-09-27 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5c8e2a7f391"
down_revision: str | None = "f4b9d2e6a157"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ("mikan_bangumi_name", "mikan_subgroup_name")


def upgrade() -> None:
    for name in _COLUMNS:
        op.add_column("rss_series", sa.Column(name, sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    for name in reversed(_COLUMNS):
        op.drop_column("rss_series", name)
