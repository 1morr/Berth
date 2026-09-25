"""測試與前端演練用的 Prowlarr 替身。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from berth.adapters.prowlarr import IndexerDefinition, IndexerRejectedError, ProwlarrIndexer

#: 假的定義清單：站名與 `definitionName` 都取自真的 `indexer/schema`（`tests/fixtures/`）。
DEFAULT_DEFINITIONS: tuple[IndexerDefinition, ...] = tuple(
    IndexerDefinition(definition_name, name, privacy, language=language, description=description)
    for definition_name, name, privacy, language, description in (
        (
            "nyaasi",
            "Nyaa.si",
            "public",
            "en-US",
            "Nyaa is a Public torrent site focused on Eastern ASIAN media",
        ),
        ("dmhy", "dmhy", "public", "zh-TW", "dmhy is a TAIWANESE Public magnet tracker for ANIME"),
        (
            "Anidex",
            "Anidex",
            "public",
            "en-US",
            "Anidex is a Public torrent tracker and indexer",
        ),
        (
            "animetosho-xyz",
            "Anime Tosho",
            "semiPrivate",
            "en-US",
            "Anime Tosho is a Semi-Private Torrent Tracker for ANIME",
        ),
        (
            "acgrip",
            "ACG.RIP",
            "public",
            "zh-CN",
            "ACG.RIP is a CHINESE Public torrent tracker for the latest anime",
        ),
        (
            "mikan",
            "Mikan",
            "public",
            "zh-CN",
            "Mikan is a CHINESE Public torrent tracker for ANIME",
        ),
        (
            "1337x",
            "1337x",
            "public",
            "en-US",
            "1337x is a Public torrent site that offers verified torrent downloads",
        ),
        (
            "yts",
            "YTS",
            "public",
            "en-US",
            "YTS is a Public torrent site specialising in HD movies of small size",
        ),
        ("eztv", "EZTV", "public", "en-US", "EZTV is a Public torrent site for TV shows"),
        (
            "thepiratebay",
            "The Pirate Bay",
            "public",
            "en-US",
            "The Pirate Bay (TPB) is the galaxy’s most resilient Public BitTorrent site",
        ),
    )
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
        #: 兩個旗標都是公開的：測試要在同一個實例上演「服務掛了」再「服務回來了」，
        #: 而健康檢查的驗收正是那兩個轉換（票 10）。
        self.ping_error = ping_error
        self.indexers_error = indexers_error
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
        #: 被移除的站的 id，順序即呼叫順序。
        self.deleted: list[int] = []
        self.restarts = 0

    async def ping(self) -> None:
        if self.ping_error is not None:
            raise self.ping_error

    def present(self) -> list[ProwlarrIndexer]:
        """現在有的站，不經過 `indexers_error`（演練伺服器照它造試搜的回答）。"""
        return list(self._indexers)

    async def indexers(self) -> list[ProwlarrIndexer]:
        if self.indexers_error is not None:
            raise self.indexers_error
        return list(self._indexers)

    async def definitions(self) -> tuple[IndexerDefinition, ...]:
        return self._definitions

    async def add_indexer(self, definition: IndexerDefinition) -> ProwlarrIndexer:
        reason = self._rejects.get(definition.definition_name)
        if reason is not None:
            raise IndexerRejectedError(f"add {definition.definition_name}", messages=(reason,))
        indexer = ProwlarrIndexer(
            # 移除過的 id 不再發（真的 Prowlarr 也是遞增的）。
            id=max((row.id for row in self._indexers), default=0) + len(self.deleted) + 1,
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

    async def delete_indexer(self, indexer_id: int) -> None:
        self.deleted.append(indexer_id)
        self._indexers = [row for row in self._indexers if row.id != indexer_id]

    async def host_config(self) -> Mapping[str, Any]:
        return dict(self._host_config)

    async def set_host_config(self, values: Mapping[str, Any]) -> None:
        self._host_config.update(values)
        # 真的那一台會回 202 然後自行重啟；這裡只記下發生過。
        self.restarts += 1

    async def aclose(self) -> None:
        return None
