"""上下文壓縮的摘要也記進 `ai_runs`（M5 票 18，plan §2.6）。

- `ai_runs.kind`：`chat`（一輪對話）或 `compaction`（一次摘要）。既有的列都是 `chat`。

降版拿掉這一欄（壓縮的那幾列跟著變成看起來像對話的一輪）。

Revision ID: e6b2d9a4c731
Revises: c4e7a9d2b158
Create Date: 2026-10-27 22:40:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6b2d9a4c731"
down_revision: str | None = "c4e7a9d2b158"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 原生 `ADD COLUMN`、不重建表（同 `c4e7a9d2b158`）。
    op.add_column(
        "ai_runs",
        sa.Column(
            "kind",
            sa.Enum("chat", "compaction", name="airunkind", native_enum=False),
            nullable=False,
            server_default="chat",
        ),
    )


def downgrade() -> None:
    op.drop_column("ai_runs", "kind")
