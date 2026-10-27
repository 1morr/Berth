"""Fribb 表的替身（M5 票 16）。測試與演練伺服器共用。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from berth.adapters.fribb import FribbEntry
from berth.adapters.http import ServiceError


@dataclass
class FakeAnimeIds:
    entries: dict[int, FribbEntry] = field(default_factory=dict)
    error: ServiceError | None = None
    asked: list[tuple[int, ...]] = field(default_factory=list)

    async def lookup(self, anilist_ids: Sequence[int]) -> dict[int, FribbEntry]:
        self.asked.append(tuple(anilist_ids))
        if self.error is not None:
            raise self.error
        return {i: self.entries[i] for i in anilist_ids if i in self.entries}
