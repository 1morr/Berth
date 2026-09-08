"""對真的 Prowlarr 說話（brief §20.7）。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from berth.adapters.http import (
    DEFAULT_TIMEOUT_SECONDS,
    HttpSession,
    ProtocolMismatchError,
    json_body,
)
from berth.adapters.prowlarr import (
    DEFAULT_APP_PROFILE_ID,
    IndexerDefinition,
    IndexerRejectedError,
    ProwlarrIndexer,
)

#: 新增與驗證索引站要真的連上那個站，比一般 API 慢得多（實測單站 5–40 秒）。
INDEXER_TIMEOUT_SECONDS = 120.0


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
        payload = json_body(await self._session.get("/api/v1/indexer"))
        if not isinstance(payload, list):
            raise ProtocolMismatchError("/api/v1/indexer: expected a list")
        return [_indexer(row) for row in payload if isinstance(row, dict) and "id" in row]

    async def definitions(self) -> tuple[IndexerDefinition, ...]:
        payload = json_body(await self._session.get("/api/v1/indexer/schema"))
        if not isinstance(payload, list):
            raise ProtocolMismatchError("/api/v1/indexer/schema: expected a list")
        return tuple(
            IndexerDefinition(
                definition_name=str(row.get("definitionName", "")),
                name=str(row.get("name", "")),
                privacy=str(row.get("privacy", "")),
                payload=row,
            )
            for row in payload
            if isinstance(row, dict) and row.get("definitionName")
        )

    async def add_indexer(self, definition: IndexerDefinition) -> ProwlarrIndexer:
        """schema 給的定義原樣送回去，只換掉 `appProfileId`（schema 是 0，會建不起來）。"""
        body = {**definition.payload, "appProfileId": DEFAULT_APP_PROFILE_ID}
        response = await self._session.request(
            "POST",
            "/api/v1/indexer",
            json=body,
            tolerate=(400,),
            timeout=INDEXER_TIMEOUT_SECONDS,
        )
        if response.status_code == 400:
            raise IndexerRejectedError(
                f"add {definition.definition_name}", messages=_reasons(json_body(response))
            )
        payload = json_body(response)
        if not isinstance(payload, dict) or "id" not in payload:
            raise ProtocolMismatchError("/api/v1/indexer: expected the created indexer")
        return _indexer(payload)

    async def test_indexer(self, indexer: ProwlarrIndexer) -> None:
        response = await self._session.request(
            "POST",
            "/api/v1/indexer/test",
            json=dict(indexer.payload),
            tolerate=(400,),
            timeout=INDEXER_TIMEOUT_SECONDS,
        )
        if response.status_code == 400:
            raise IndexerRejectedError(
                f"test {indexer.name}", messages=_reasons(json_body(response))
            )

    async def host_config(self) -> Mapping[str, Any]:
        payload = json_body(await self._session.get("/api/v1/config/host"))
        if not isinstance(payload, dict) or "authenticationMethod" not in payload:
            raise ProtocolMismatchError("/api/v1/config/host: not a Prowlarr host config")
        return payload

    async def set_host_config(self, values: Mapping[str, Any]) -> None:
        """回 **202**，Prowlarr 隨即自行重啟——呼叫端要等它回來（brief §20.7）。"""
        await self._session.request(
            "PUT", f"/api/v1/config/host/{values.get('id', 1)}", json=dict(values)
        )

    async def aclose(self) -> None:
        await self._session.aclose()


def _indexer(row: Mapping[str, Any]) -> ProwlarrIndexer:
    return ProwlarrIndexer(
        id=int(row["id"]),
        name=str(row.get("name", "")),
        enabled=bool(row.get("enable", False)),
        definition_name=str(row.get("definitionName", "")),
        payload=row,
    )


def _reasons(payload: Any) -> tuple[str, ...]:
    """400 的 body 是一個陣列，每一列是一條理由；畫面顯示的就是 `errorMessage`。"""
    if not isinstance(payload, list):
        return ()
    return tuple(
        str(row["errorMessage"])
        for row in payload
        if isinstance(row, dict) and row.get("errorMessage")
    )
