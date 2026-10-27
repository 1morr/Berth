"""AniList 的替身：回放一組條目，記下每一次收到的問題（M5 票 16）。測試與演練伺服器共用。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from berth.adapters.anilist import AnimeEntry, AnimeSeason
from berth.adapters.http import ServiceError


@dataclass
class FakeAniList:
    #: 依 id 取的那一種回的條目（帶關係）。
    known: dict[int, AnimeEntry] = field(default_factory=dict)
    #: 搜尋：查詢字串 → 結果。沒列的回空。
    found: dict[str, list[AnimeEntry]] = field(default_factory=dict)
    #: 季表：（季, 年）→ 結果。
    seasons: dict[tuple[AnimeSeason, int], list[AnimeEntry]] = field(default_factory=dict)
    #: 給了就每一次都丟它。
    error: ServiceError | None = None
    asked: list[tuple[str, object]] = field(default_factory=list)

    async def search(self, query: str, *, limit: int) -> list[AnimeEntry]:
        self._ask("search", query)
        return list(self.found.get(query, ())[:limit])

    async def entries(self, ids: Sequence[int]) -> list[AnimeEntry]:
        self._ask("entries", tuple(ids))
        return [self.known[i] for i in ids if i in self.known]

    async def season(self, season: AnimeSeason, year: int, *, limit: int) -> list[AnimeEntry]:
        self._ask("season", (season, year))
        return list(self.seasons.get((season, year), ())[:limit])

    def _ask(self, kind: str, what: object) -> None:
        self.asked.append((kind, what))
        if self.error is not None:
            raise self.error
