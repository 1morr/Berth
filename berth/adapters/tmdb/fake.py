"""測試與前端演練用的 TMDB 替身。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace

from berth.adapters.tmdb import BASE_LANGUAGE, TmdbConfiguration, TmdbEntry
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
        display_absent: Iterable[int] = (),
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
        self._display_absent = frozenset(display_absent)
        #: 逐支端點的呼叫次數。快取生效與否就看這裡。
        self.requests: list[tuple[str, str]] = []

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

    async def aclose(self) -> None:
        return None

    def _raise(self) -> None:
        if self.error is not None:
            raise self.error

    def _localised(self, entries: Sequence[TmdbEntry], language: str) -> tuple[TmdbEntry, ...]:
        if language == BASE_LANGUAGE:
            return tuple(entries)
        return tuple(
            replace(entry, title=self._translations.get(entry.tmdb_id, entry.title))
            for entry in entries
            if entry.tmdb_id not in self._display_absent
        )
