"""週報：一週一筆，產生那一刻算好存下來（plan §11.5〈巡檢〉、M4 票 131、CONTEXT.md 的週報）。

**存結果，不存查詢**：purge 會連帳本與事件一起刪（`deletion._purge`），之後回頭看的舊週報要是
每次重算，就會跟著少掉那幾行。所以 `content_json` 是產生那一刻的三段事實（作品、季集、數量），
畫面與通知照它組字。

**一週的身分是它開始那一天**（`week_of`，容器時區的週一日期）：唯一索引守著「同一週只有一筆」，
重啟、補跑撞上同一週時什麼都不寫。不用起訖時刻當鍵：換日光節約時間的那一週，同一個週一 05:00
換算成 UTC 會差一小時。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from berth.models.base import Base
from berth.models.types import JsonText, UtcDateTime, utcnow


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"
    __table_args__ = (Index("ix_weekly_reports_week_of", "week_of", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    #: 這一週的第一天（容器時區的週一），ISO 日期。
    week_of: Mapped[str] = mapped_column(Text)
    #: 涵蓋的那一段：週一 05:00 起、下一個週一 05:00 止（不含）。
    starts_at: Mapped[datetime] = mapped_column(UtcDateTime)
    ends_at: Mapped[datetime] = mapped_column(UtcDateTime)
    #: 三段事實（`services.weekly`）。
    content_json: Mapped[dict[str, Any]] = mapped_column(JsonText)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
