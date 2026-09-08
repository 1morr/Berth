"""測試與前端演練用的 Torznab 替身。"""

from __future__ import annotations

from berth.adapters.torznab import TorznabCaps


class FakeTorznabClient:
    def __init__(
        self,
        *,
        base_url: str = "http://jackett:9117/api/v2.0/indexers/all/results/torznab/api",
        caps: TorznabCaps | None = None,
        error: Exception | None = None,
    ) -> None:
        self.base_url = base_url
        self._caps = caps or TorznabCaps(
            server_title="Jackett", search_available=True, categories=("TV", "Movies")
        )
        self.error = error

    async def caps(self) -> TorznabCaps:
        if self.error is not None:
            raise self.error
        return self._caps

    async def aclose(self) -> None:
        return None
