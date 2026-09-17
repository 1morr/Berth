"""Library Route：一個入庫目的地（CONTEXT.md、plan §2.2）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from berth.domain import CollectionType, HealthStatus
from berth.models.base import Base
from berth.models.setting import SetupStep
from berth.models.types import JsonText, UtcDateTime, enum_column, utcnow


class RouteHealth(BaseModel):
    """`routes.health_detail_json`：上一次檢查逐項的結果（plan §9.5、brief §4.4）。

    形狀與精靈其他泊位的纜繩完全一樣（`SetupStep`），所以畫面是同一個元件；`key` 是
    `RouteCheck`。健康頁（票 10）重跑同一組檢查，寫回同一個欄位。
    """

    model_config = ConfigDict(extra="ignore")

    checks: list[SetupStep] = []
    #: 硬鏈接回 `EXDEV`：兩個目錄在 Berth 內是不同掛載，訊息要另外說（brief §4.4）。
    cross_device: bool = False
    checked_at: datetime | None = None
    #: 最後一次五條纜繩全綠的時間。與服務那一列同一個道理——「現在紅著，但十分鐘前還好好的」
    #: 與「從來沒通過」對維運是兩件事（brief §16.2、票 10）。
    last_ok_at: datetime | None = None


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
    #: medium 信心是否自動入庫；false 時一律進 Review Queue（brief §6.5）。
    medium_auto_import: Mapped[bool] = mapped_column(default=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    health_status: Mapped[HealthStatus] = mapped_column(
        enum_column(HealthStatus), default=HealthStatus.UNKNOWN
    )
    health_detail_json: Mapped[dict[str, Any] | None] = mapped_column(JsonText, default=None)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
