"""測試與前端演練用的 TMDB 替身。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace

from berth.adapters.http import NotFoundError
from berth.adapters.tmdb import (
    BASE_LANGUAGE,
    TmdbConfiguration,
    TmdbDetail,
    TmdbEntry,
    TmdbSeason,
    TmdbSeasonEntry,
)
from berth.domain import MediaKind


class FakeTmdbClient:
    """一份固定的目錄，加上「另一種語言長什麼樣」。

    翻譯不是逐筆換一個字串就算了：真的 TMDB 在 `language=zh-TW` 下**回的成員與順序都可能不同**
    （2026-09-09 實測 `trending/tv/week`，20 筆裡有 3 筆只在 `en-US` 那一輪出現）。
    `display_absent` 就是這件事，讓「顯示用標題那一輪少了幾筆」在測試裡演得出來。
    """

    def __init__(
        self,
        *,
        configuration: TmdbConfiguration | None = None,
        error: Exception | None = None,
        trending: Mapping[MediaKind, Sequence[TmdbEntry]] | None = None,
        popular: Mapping[MediaKind, Sequence[TmdbEntry]] | None = None,
        search: Mapping[str, Sequence[TmdbEntry]] | None = None,
        translations: Mapping[int, str] | None = None,
        season_names: Mapping[str, Mapping[int, str]] | None = None,
        display_absent: Iterable[int] = (),
        details: Sequence[TmdbDetail] = (),
        seasons: Mapping[int, Sequence[TmdbSeason]] | None = None,
        ordering: Mapping[str, Mapping[tuple[int, int], int]] | None = None,
    ) -> None:
        self._configuration = configuration or TmdbConfiguration(
            image_base_url="https://image.tmdb.org/t/p/"
        )
        self.error = error
        #: 最後一次拿到的憑證，用來斷言「用的是存下來的那一把」。
        self.credential = ""
        self.calls = 0
        self._trending = dict(trending or {})
        self._popular = dict(popular or {})
        self._search = dict(search or {})
        self._translations = dict(translations or {})
        #: `語言 → {季號: 季名}`。真的 TMDB 每一輪回的季名都是那個語言的
        #: （`Hashira Training Arc` / `柱訓練篇` / `柱训练篇`），篇章名比對靠這件事。
        self._season_names = {
            language: dict(rows) for language, rows in (season_names or {}).items()
        }
        self._display_absent = frozenset(display_absent)
        #: 逐支端點的呼叫次數。快取生效與否就看這裡。
        self.requests: list[tuple[str, str]] = []
        #: `(kind, id) → 詳情`。公開的，測試要演「TMDB 改了標題」就改這裡。
        self.details = {(row.kind, row.tmdb_id): row for row in details}
        self._seasons = {
            (tmdb_id, season.season_number): season
            for tmdb_id, rows in (seasons or {}).items()
            for season in rows
        }
        self._ordering = {key: dict(value) for key, value in (ordering or {}).items()}

    async def configuration(self) -> TmdbConfiguration:
        self.calls += 1
        self._raise()
        return self._configuration

    async def trending(self, kind: MediaKind, *, language: str) -> tuple[TmdbEntry, ...]:
        self.requests.append((f"trending/{kind.value}", language))
        self._raise()
        return self._localised(self._trending.get(kind, ()), language)

    async def popular(self, kind: MediaKind, *, language: str) -> tuple[TmdbEntry, ...]:
        self.requests.append((f"popular/{kind.value}", language))
        self._raise()
        return self._localised(self._popular.get(kind, ()), language)

    async def search(self, query: str, *, language: str) -> tuple[TmdbEntry, ...]:
        self.requests.append((f"search/{query}", language))
        self._raise()
        return self._localised(self._search.get(query, ()), language)

    async def detail(self, kind: MediaKind, tmdb_id: int, *, language: str) -> TmdbDetail:
        self.requests.append((f"detail/{kind.value}/{tmdb_id}", language))
        self._raise()
        found = self.details.get((kind, tmdb_id))
        if found is None:
            raise NotFoundError(f"{kind.value}/{tmdb_id}: no such title on TMDB")
        if language == BASE_LANGUAGE:
            return found
        return replace(
            found,
            title=self._translations.get(tmdb_id, found.title),
            seasons=self._localised_seasons(found.seasons, language),
        )

    async def season(self, tmdb_id: int, season_number: int, *, language: str) -> TmdbSeason:
        self.requests.append((f"season/{tmdb_id}/{season_number}", language))
        self._raise()
        found = self._seasons.get((tmdb_id, season_number))
        if found is None:
            raise NotFoundError(f"tv/{tmdb_id}/season/{season_number}: no such season")
        return found

    async def absolute_ordering(self, group_id: str) -> dict[tuple[int, int], int]:
        self.requests.append((f"episode_group/{group_id}", ""))
        self._raise()
        return dict(self._ordering.get(group_id, {}))

    async def aclose(self) -> None:
        return None

    def _raise(self) -> None:
        if self.error is not None:
            raise self.error

    def _localised_seasons(
        self, seasons: Sequence[TmdbSeasonEntry], language: str
    ) -> tuple[TmdbSeasonEntry, ...]:
        names = self._season_names.get(language, {})
        return tuple(
            replace(entry, name=names.get(entry.season_number, entry.name)) for entry in seasons
        )

    def _localised(self, entries: Sequence[TmdbEntry], language: str) -> tuple[TmdbEntry, ...]:
        if language == BASE_LANGUAGE:
            return tuple(entries)
        return tuple(
            replace(entry, title=self._translations.get(entry.tmdb_id, entry.title))
            for entry in entries
            if entry.tmdb_id not in self._display_absent
        )
