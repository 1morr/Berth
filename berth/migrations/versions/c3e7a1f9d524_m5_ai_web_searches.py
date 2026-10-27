"""AI 的觀測多記伺服器端網搜（M5 票 17，plan §2.6）。

- `ai_calls.web_searches`、`ai_calls.web_search_cost_usd`：一次模型呼叫裡搜了幾次、花多少；
  費用 `NULL` 是價錢不知道（不是 Anthropic 官方端點），沒算進 `cost_usd`。
- `ai_runs.web_searches`：一輪的合計。

既有的列補 0：票 17 之前沒有網搜。升版不用 batch（理由同 `3f6c0a7d94e2`）。

Revision ID: c3e7a1f9d524
Revises: 78a62163b817
Create Date: 2026-10-27 22:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3e7a1f9d524"
down_revision: str | None = "78a62163b817"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_calls", sa.Column("web_searches", sa.Integer(), nullable=False, server_default="0")
    )
    # 沒有 server default（`NULL` 有意思：價錢不知道），舊列另外補 0。
    op.add_column("ai_calls", sa.Column("web_search_cost_usd", sa.Float(), nullable=True))
    op.execute("UPDATE ai_calls SET web_search_cost_usd = 0")
    op.add_column(
        "ai_runs", sa.Column("web_searches", sa.Integer(), nullable=False, server_default="0")
    )


def downgrade() -> None:
    # SQLite 刪欄位只能重建表（同 `3f6c0a7d94e2`）。
    with op.batch_alter_table("ai_runs", schema=None) as batch_op:
        batch_op.drop_column("web_searches")
    with op.batch_alter_table("ai_calls", schema=None) as batch_op:
        batch_op.drop_column("web_search_cost_usd")
        batch_op.drop_column("web_searches")
