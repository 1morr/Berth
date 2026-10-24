"""`ai_calls.message_id`：這一次呼叫在回覆哪一則使用者的話（M5 票 14）。

AI 活動頁的「這次回覆花了多少 tokens」照它加總。舊的列是 `NULL`（說不出是哪一次回覆）。

Revision ID: 5e1a7c3d9b20
Revises: 9708ccd64def
Create Date: 2026-10-24 18:20:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "5e1a7c3d9b20"
down_revision: str | None = "9708ccd64def"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 不用 `batch_alter_table`：它重建整張表，而 `ai_calls` 已經有兩條外鍵，重建時的外鍵順序取自
    # 一個 set（同一個程序裡跑過什麼會改變它），降回去再升上來的 schema 字面就對不上
    # （`test_database` 的降回 base 再升上來那一條，在整套一起跑時紅過）。
    # SQLite 的 ADD COLUMN 收得下預設 NULL 的外鍵欄，不必重建。
    op.execute(
        "ALTER TABLE ai_calls ADD COLUMN message_id INTEGER "
        "CONSTRAINT fk_ai_calls_message_id_conversation_messages "
        "REFERENCES conversation_messages (id) ON DELETE SET NULL"
    )


def downgrade() -> None:
    # 同一個理由不重建；DROP COLUMN 從 SQLite 3.35 起有。
    op.execute("ALTER TABLE ai_calls DROP COLUMN message_id")
