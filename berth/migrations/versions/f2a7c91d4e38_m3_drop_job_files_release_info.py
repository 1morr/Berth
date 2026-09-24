"""拿掉 job_files.release_info_json（M3 票 01）。

M1 起就沒有人寫這一欄：解析結果落在 `plan_items`（處置、季集、Tags），發佈名的解析每次規劃都
重算。RSS 要的那一份在 `rss_items` 自己那一欄（plan §2.4），不借這裡（2026-09-24 使用者拍板）。

**升版用原生 `DROP COLUMN`**（理由同 `9d4f1b6e2a70`）：batch 會重建 `job_files`，而 SQLite 3.35
起原生的刪欄不重建表；這一欄沒有索引、約束或外鍵。降版的原生 `ADD COLUMN` 也成立：可為 NULL、
沒有預設值，與 M1 建的那一欄同一個形狀。

Revision ID: f2a7c91d4e38
Revises: d4f1a8c2e6b9
Create Date: 2026-09-24 20:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2a7c91d4e38"
down_revision: str | None = "d4f1a8c2e6b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("job_files", "release_info_json")


def downgrade() -> None:
    op.add_column("job_files", sa.Column("release_info_json", sa.Text(), nullable=True))
