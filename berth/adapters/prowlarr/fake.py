"""測試與前端演練用的 Prowlarr 替身。"""

from __future__ import annotations

from berth.adapters.prowlarr import ProwlarrIndexer


class FakeProwlarrClient:
    def __init__(
        self,
        *,
        base_url: str = "http://prowlarr:9696",
        indexers: list[ProwlarrIndexer] | None = None,
        ping_error: Exception | None = None,
        indexers_error: Exception | None = None,
    ) -> None:
        self._base_url = base_url
        self._indexers = indexers or []
        self._ping_error = ping_error
        self._indexers_error = indexers_error

    @property
    def base_url(self) -> str:
        return self._base_url

    async def ping(self) -> None:
        if self._ping_error is not None:
            raise self._ping_error

    async def indexers(self) -> list[ProwlarrIndexer]:
        if self._indexers_error is not None:
            raise self._indexers_error
        return list(self._indexers)

    async def aclose(self) -> None:
        return None
