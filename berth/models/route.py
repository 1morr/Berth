"""Library Route：一個入庫目的地（CONTEXT.md、plan §2.2）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from berth.domain import CollectionType, HealthStatus, Profile
from berth.models.base import Base
from berth.models.types import JsonText, UtcDateTime, enum_column, utcnow


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    jellyfin_library_id: Mapped[str] = mapped_column(Text)
    jellyfin_library_name: Mapped[str] = mapped_column(Text)
    collection_type: Mapped[CollectionType] = mapped_column(enum_column(CollectionType))
    #: 該媒體庫的其中一個路徑，Route 只寫這一個（brief §4.3）。
    target_path: Mapped[str] = mapped_column(Text)
    #: qBittorrent category，預設 `berth-<slug>`（brief §4.1）。
    category: Mapped[str] = mapped_column(Text)
    profile: Mapped[Profile] = mapped_column(enum_column(Profile))
    #: medium 信心是否自動入庫；false 時一律進 Review Queue（brief §6.5）。
    medium_auto_import: Mapped[bool] = mapped_column(default=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    health_status: Mapped[HealthStatus] = mapped_column(
        enum_column(HealthStatus), default=HealthStatus.UNKNOWN
    )
    health_detail_json: Mapped[dict[str, Any] | None] = mapped_column(JsonText, default=None)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
