"""Job 時間線上的事件（plan §2.3）。

`job_hash` 與 `media_id` 是弱引用：Job 刪掉後事件仍要留著，所以不設外鍵。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from berth.models.base import Base
from berth.models.types import JsonText, UtcDateTime, utcnow


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_job_hash_created_at", "job_hash", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_hash: Mapped[str | None] = mapped_column(Text, default=None)
    media_id: Mapped[str | None] = mapped_column(Text, default=None)
    type: Mapped[str] = mapped_column(Text)
    #: user id、`system`、`rss:<rule>` 或 `ai`。
    actor: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JsonText, default=None)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
