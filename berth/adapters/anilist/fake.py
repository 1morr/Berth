"""AniList 的替身：回放一組條目，記下每一次收到的問題（M5 票 16）。測試與演練伺服器共用。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from berth.adapters.anilist import Airing, AnimeEntry, AnimeSeason
from berth.adapters.http import ServiceError


@dataclass
class FakeAniList:
    #: 季表：（季, 年）→ 結果。
    seasons: dict[tuple[AnimeSeason, int], list[AnimeEntry]] = field(default_factory=dict)
    #: 放送：照 `start < airs_at < end` 篩（AniList 的 `airingAt_greater` / `_lesser` 兩端都不含）。
    airings: list[Airing] = field(default_factory=list)
    #: 給了就每一次都丟它。
    error: ServiceError | None = None
    asked: list[tuple[str, object]] = field(default_factory=list)

    async def season(self, season: AnimeSeason, year: int, *, limit: int) -> list[AnimeEntry]:
        self._ask("season", (season, year))
        return list(self.seasons.get((season, year), ())[:limit])

    async def airing(self, start: datetime, end: datetime) -> list[Airing]:
        self._ask("airing", (start, end))
        return [a for a in self.airings if start < a.airs_at < end]

    def _ask(self, kind: str, what: object) -> None:
        self.asked.append((kind, what))
        if self.error is not None:
            raise self.error
