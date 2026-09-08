"""測試與前端演練用的 Prowlarr 替身。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from berth.adapters.prowlarr import IndexerDefinition, IndexerRejectedError, ProwlarrIndexer

#: 假的定義清單：站名與 `definitionName` 都取自真的 `indexer/schema`（`tests/fixtures/`）。
DEFAULT_DEFINITIONS: tuple[IndexerDefinition, ...] = (
    IndexerDefinition("nyaasi", "Nyaa.si", "public"),
    IndexerDefinition("dmhy", "dmhy", "public"),
    IndexerDefinition("Anidex", "Anidex", "public"),
    IndexerDefinition("animetosho-xyz", "Anime Tosho", "semiPrivate"),
    IndexerDefinition("acgrip", "ACG.RIP", "public"),
    IndexerDefinition("mikan", "Mikan", "public"),
    IndexerDefinition("1337x", "1337x", "public"),
    IndexerDefinition("yts", "YTS", "public"),
    IndexerDefinition("eztv", "EZTV", "public"),
    IndexerDefinition("thepiratebay", "The Pirate Bay", "public"),
)


class FakeProwlarrClient:
    """索引站是**有狀態**的：加過的站再加一次就是「已經在了」，重按才看得出冪等。"""

    def __init__(
        self,
        *,
        base_url: str = "http://prowlarr:9696",
        indexers: list[ProwlarrIndexer] | None = None,
        definitions: tuple[IndexerDefinition, ...] = DEFAULT_DEFINITIONS,
        ping_error: Exception | None = None,
        indexers_error: Exception | None = None,
        #: 這些站加不進來（連不上、被 CloudFlare 擋），值就是 Prowlarr 回的理由。
        rejects: Mapping[str, str] | None = None,
        host_config: Mapping[str, Any] | None = None,
    ) -> None:
        self.base_url = base_url
        self._indexers = indexers or []
        self._definitions = definitions
        self._ping_error = ping_error
        self._indexers_error = indexers_error
        self._rejects = dict(rejects or {})
        self._host_config: dict[str, Any] = dict(
            host_config
            or {
                "id": 1,
                "authenticationMethod": "none",
                "authenticationRequired": "enabled",
                "username": "",
                "password": "",
                "passwordConfirmation": "",
                "apiKey": "0" * 31 + "1",
            }
        )
        self.tested: list[str] = []
        self.restarts = 0

    async def ping(self) -> None:
        if self._ping_error is not None:
            raise self._ping_error

    async def indexers(self) -> list[ProwlarrIndexer]:
        if self._indexers_error is not None:
            raise self._indexers_error
        return list(self._indexers)

    async def definitions(self) -> tuple[IndexerDefinition, ...]:
        return self._definitions

    async def add_indexer(self, definition: IndexerDefinition) -> ProwlarrIndexer:
        reason = self._rejects.get(definition.definition_name)
        if reason is not None:
            raise IndexerRejectedError(f"add {definition.definition_name}", messages=(reason,))
        indexer = ProwlarrIndexer(
            id=len(self._indexers) + 1,
            name=definition.name,
            enabled=True,
            definition_name=definition.definition_name,
        )
        self._indexers.append(indexer)
        return indexer

    async def test_indexer(self, indexer: ProwlarrIndexer) -> None:
        self.tested.append(indexer.definition_name or indexer.name)
        reason = self._rejects.get(indexer.definition_name)
        if reason is not None:
            raise IndexerRejectedError(f"test {indexer.name}", messages=(reason,))

    async def host_config(self) -> Mapping[str, Any]:
        return dict(self._host_config)

    async def set_host_config(self, values: Mapping[str, Any]) -> None:
        self._host_config.update(values)
        # 真的那一台會回 202 然後自行重啟；這裡只記下發生過。
        self.restarts += 1

    async def aclose(self) -> None:
        return None
