"""Plan Item 多一欄 duplicate_of：與帳本上哪一列重複（M2 票 08、brief §7.8）。

規劃時比帳本：同一集同一組 Tags，或同一個起始集而結束集不同。自動模式略過那一列，
Review Queue 上它是一列 `duplicate`，管理員決定之後清掉。

**升版用原生 `ADD COLUMN`**（理由同 `7c3e5a9b2d41`）：batch 會重建整張表。SQLite 接受帶
`REFERENCES` 的 `ADD COLUMN`，只要預設值是 NULL；**但 Alembic 的 `op.add_column` 遇到外鍵就丟
`NotImplementedError`**，所以是一句 SQL。約束名照 `models.base.NAMING_CONVENTION`，降版的 batch
才認得它。既有的列都是 NULL——它們規劃時沒有比過。

Revision ID: d4f1a8c2e6b9
Revises: b58e3d1f7a20
Create Date: 2026-09-23 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "d4f1a8c2e6b9"
down_revision: str | None = "b58e3d1f7a20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE plan_items ADD COLUMN duplicate_of INTEGER "
        "CONSTRAINT fk_plan_items_duplicate_of_ledger "
        "REFERENCES ledger (id) ON DELETE SET NULL"
    )


def downgrade() -> None:
    # SQLite 刪欄位只能重建表；降版那條測試比的是欄位（`PRAGMA table_info`），不是 DDL 原文。
    with op.batch_alter_table("plan_items", schema=None) as batch_op:
        batch_op.drop_column("duplicate_of")
