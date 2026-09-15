"""帳本多一欄 jellyfin_series_id（票 13）。

媒體庫的卡片深連結到 Jellyfin 的**作品**，而帳本上一條劇集正片記的是那一集的 item。
反查時 `/Items` 的 Episode 自己帶 `SeriesId`（2026-09-15 對 12.0.0 實測），所以與 item id
一起寫下，不必為了一條連結在讀頁面時再問 Jellyfin。

既有的列補空字串：它們不會被重新反查，卡片上照實說「還在找」而不是給一條連到某一集的連結。

**升版不用 batch**：batch 會把整張表重建一次，而 ledger 有兩個外鍵——重建時它們的順序是反射出來的，
不固定，`CREATE TABLE` 的原文於是每次不一樣（「降回去再升上來是同一份 schema」那條測試抓到的）。
SQLite 原生的 `ADD COLUMN` 不重建表；代價是 `server_default` 留在欄位上，所以模型也宣告同一個。

Revision ID: 7c3e5a9b2d41
Revises: 4d2b7e9a1c63
Create Date: 2026-09-15 14:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7c3e5a9b2d41"
down_revision: str | None = "4d2b7e9a1c63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ledger",
        sa.Column("jellyfin_series_id", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    # SQLite 刪欄位只能重建表；降版那條測試比的是欄位（`PRAGMA table_info`），不是 DDL 原文。
    with op.batch_alter_table("ledger", schema=None) as batch_op:
        batch_op.drop_column("jellyfin_series_id")
