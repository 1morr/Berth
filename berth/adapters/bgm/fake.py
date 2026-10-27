"""Bangumi 放送表的替身（M5 票 16）。測試與演練伺服器共用。"""

from __future__ import annotations

from dataclasses import dataclass, field

from berth.adapters.bgm import CalendarItem
from berth.adapters.http import ServiceError


@dataclass
class FakeBgm:
    items: list[CalendarItem] = field(default_factory=list)
    error: ServiceError | None = None
    asked: int = 0

    async def calendar(self) -> list[CalendarItem]:
        self.asked += 1
        if self.error is not None:
            raise self.error
        return list(self.items)
