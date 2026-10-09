"""拿掉 `rss_series.passed_before`：補舊集不再有開關（M4 票 78、brief §15「補舊集」）。

2026-09-26 使用者拍板綁定一律補齊舊集；手動綁定與訂閱留下的「取消勾選」一起拿掉。因為它而略過的
舊集放回去（使用者同意）：補漏以 `(feed_id, guid)` 去重，那幾筆已經寫成 `passed`，只拿掉欄位的話
它們永遠停在略過。認得出是它略過的那幾筆：Mikan Feed 上的、所屬 RSS Series 的 `passed_before`
有值、發佈時間早於它。Mikan Feed 一加進來就選過第一輪，「只追之後的」的 `passed` 不會在那裡；
排除條件擋下的是 `excluded`。綁著的回到 `matched`（下一輪輪詢照常去重後送出），解綁了的回到
`unbound`。放回來的不再看一次排除條件：遷移裡沒有規則可讀，它們進來那一刻是看過的。

票 12 之前就綁好的 Series 當初被補成 `passed_before = created_at`，它們的舊集一樣放回來（使用者
接受）。

**升版用原生 `DROP COLUMN`**（理由同 `f2a7c91d4e38`）：這一欄沒有索引、約束或外鍵。**降版不還原**：
欄位加回來是 `NULL`（要整季），放回去的狀態不改回 `passed`。

Revision ID: d71e4b9a3c58
Revises: b4ca280eaeca
Create Date: 2026-10-09 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d71e4b9a3c58"
down_revision: str | None = "b4ca280eaeca"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE rss_items
        SET status = CASE
            WHEN (SELECT media_id FROM rss_series WHERE rss_series.id = rss_items.series_id)
                IS NULL THEN 'unbound'
            ELSE 'matched'
        END
        WHERE status = 'passed'
            AND feed_id IN (SELECT id FROM rss_feeds WHERE kind = 'mikan')
            AND published_at < (
                SELECT passed_before FROM rss_series
                WHERE rss_series.id = rss_items.series_id
                    AND rss_series.mikan_bangumi_id IS NOT NULL
            )
        """
    )
    op.drop_column("rss_series", "passed_before")


def downgrade() -> None:
    op.add_column("rss_series", sa.Column("passed_before", sa.Text(), nullable=True))
