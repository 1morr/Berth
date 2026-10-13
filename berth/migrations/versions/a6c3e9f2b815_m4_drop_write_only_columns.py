"""拿掉四個只寫不讀的欄位（M4 票 95、票 86 審計 S33）。

- `jobs.last_seen_in_client_at`：註解說的消費者（torrent 從客戶端消失時說「最後一次是何時」）
  不存在。
- `job_files.updated_at`：只有兩條路徑寫，其他改 `job_files` 的路徑都不寫，說不清它代表什麼。
- `ledger.link_mode`：值永遠是 `hardlink`（硬鏈接失敗不退回複製，brief §4.4）。
- `ledger.source_inode`：判 inode 不符與刪除檢查讀的是 `source_dev` 加 `target_inode`；硬鏈接的
  兩端本來就是同一個 inode。

**升版用原生 `DROP COLUMN`**（理由同 `7c3e5a9b2d41`、`f2a7c91d4e38`）：batch 會重建表，ledger 兩個
外鍵的順序是反射出來的、不固定，「降回去再升上來是同一份 schema」那條測試會紅。這四欄沒有索引、
約束或外鍵。

**降版**：可為 NULL 的那一欄原生 `ADD COLUMN`；三個 NOT NULL 欄位當初沒有預設值，原生加不回去
（SQLite 要一個非 NULL 的預設），所以先加成可為 NULL、補值，再以 batch 改回 NOT NULL。補的值：
來源 inode 取目標 inode（硬鏈接成立時兩者相等）、鏈接方式 `hardlink`、檔案的更新時間取 Job 加入
的時間。batch 重建時 `DROP TABLE` 在外鍵開著時會觸發 `plan_items` 上的 `ON DELETE SET NULL`
（`job_file_id` 指 `job_files`、`duplicate_of` 指 `ledger`），遷移跑在交易裡關不掉外鍵，所以先把
那兩欄抄出來、重建完寫回去。

Revision ID: a6c3e9f2b815
Revises: d71e4b9a3c58
Create Date: 2026-10-13 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a6c3e9f2b815"
down_revision: str | None = "d71e4b9a3c58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("jobs", "last_seen_in_client_at")
    op.drop_column("job_files", "updated_at")
    op.drop_column("ledger", "source_inode")
    op.drop_column("ledger", "link_mode")


def downgrade() -> None:
    op.add_column("jobs", sa.Column("last_seen_in_client_at", sa.Text(), nullable=True))
    op.add_column("job_files", sa.Column("updated_at", sa.Text(), nullable=True))
    op.add_column("ledger", sa.Column("source_inode", sa.Text(), nullable=True))
    op.add_column("ledger", sa.Column("link_mode", sa.Text(), nullable=True))
    op.execute(
        "UPDATE job_files SET updated_at ="
        " (SELECT added_at FROM jobs WHERE jobs.hash = job_files.job_hash)"
    )
    op.execute("UPDATE ledger SET source_inode = target_inode, link_mode = 'hardlink'")

    op.execute(
        "CREATE TEMP TABLE _plan_item_links AS"
        " SELECT id, job_file_id, duplicate_of FROM plan_items"
        " WHERE job_file_id IS NOT NULL OR duplicate_of IS NOT NULL"
    )
    with op.batch_alter_table("job_files", schema=None) as batch_op:
        batch_op.alter_column("updated_at", existing_type=sa.Text(), nullable=False)
    with op.batch_alter_table("ledger", schema=None) as batch_op:
        batch_op.alter_column("source_inode", existing_type=sa.Text(), nullable=False)
        batch_op.alter_column("link_mode", existing_type=sa.Text(), nullable=False)
    op.execute(
        "UPDATE plan_items SET"
        " job_file_id = (SELECT job_file_id FROM _plan_item_links l WHERE l.id = plan_items.id),"
        " duplicate_of = (SELECT duplicate_of FROM _plan_item_links l WHERE l.id = plan_items.id)"
        " WHERE id IN (SELECT id FROM _plan_item_links)"
    )
    op.execute("DROP TABLE _plan_item_links")
