"""帳本多一欄 jellyfin_version_name（票 14b）。

Jellyfin 12 起劇集也原生合併多版本，而版本選單上的名字是 Jellyfin 自己算的（去掉各版本檔名的
共同前綴，12.0 與 12.1 的算法還不一樣）。Berth 不重算它，改在反查到的那一刻把
`MediaSources[].Name` 抄下來（brief §7.7、§20.9）。

既有的列補空字串：還排著反查的那幾筆下一輪就會填上，反查已經用完的沒有名字，畫面照實說
「Jellyfin 還沒收錄」。

**升版不用 batch**，理由同 `7c3e5a9b2d41`：batch 會把整張表重建一次，而 ledger 有兩個外鍵，
重建時它們的順序不固定，「降回去再升上來是同一份 schema」那條測試會偶發紅。

Revision ID: 3f6c0a7d94e2
Revises: 7c3e5a9b2d41
Create Date: 2026-09-16 09:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3f6c0a7d94e2"
down_revision: str | None = "7c3e5a9b2d41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ledger",
        sa.Column("jellyfin_version_name", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    # SQLite 刪欄位只能重建表；降版那條測試比的是欄位（`PRAGMA table_info`），不是 DDL 原文。
    with op.batch_alter_table("ledger", schema=None) as batch_op:
        batch_op.drop_column("jellyfin_version_name")
