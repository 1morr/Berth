"""RSS Series 記下自動綁定的理由與候選（M3 票 09）。

`reasons_json` 是 `domain.BindReason` 的清單：自動綁上時是依據，留在待綁定時是為什麼；
`candidates_json` 是給人一鍵選的那幾部作品的 id（`tv:<tmdb>`）。兩欄都可為 NULL——票 09 之前
長出來的 Series 沒有查過，畫面照舊只給搜尋。原生 `ADD COLUMN` / `DROP COLUMN` 就夠（理由同
`f2a7c91d4e38`）：沒有索引、約束或外鍵。

Revision ID: a9c4e2f7b315
Revises: b7e2c4d9a813
Create Date: 2026-09-25 20:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9c4e2f7b315"
down_revision: str | None = "b7e2c4d9a813"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("rss_series", sa.Column("reasons_json", sa.Text(), nullable=True))
    op.add_column("rss_series", sa.Column("candidates_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("rss_series", "candidates_json")
    op.drop_column("rss_series", "reasons_json")
