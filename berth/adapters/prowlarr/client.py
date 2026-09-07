"""對真的 Prowlarr 說話（brief §20.7）。"""

from __future__ import annotations

from berth.adapters.http import (
    DEFAULT_TIMEOUT_SECONDS,
    HttpSession,
    ProtocolMismatchError,
    json_body,
)
from berth.adapters.prowlarr import ProwlarrIndexer


class HttpProwlarrClient:
    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url
        headers = {"X-Api-Key": api_key} if api_key else {}
        self._session = HttpSession(base_url, headers=headers, timeout=timeout)

    @property
    def base_url(self) -> str:
        return self._base_url

    async def ping(self) -> None:
        response = await self._session.get("/ping")
        payload = json_body(response)
        if not isinstance(payload, dict) or "status" not in payload:
            raise ProtocolMismatchError("/ping: not a Prowlarr ping payload")

    async def indexers(self) -> list[ProwlarrIndexer]:
        response = await self._session.get("/api/v1/indexer")
        payload = json_body(response)
        if not isinstance(payload, list):
            raise ProtocolMismatchError("/api/v1/indexer: expected a list")
        return [
            ProwlarrIndexer(
                id=int(row["id"]),
                name=str(row.get("name", "")),
                enabled=bool(row.get("enable", False)),
            )
            for row in payload
            if isinstance(row, dict) and "id" in row
        ]

    async def aclose(self) -> None:
        await self._session.aclose()
