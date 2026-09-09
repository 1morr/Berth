"""對真的 TMDB API 說話（plan §8.3）。"""

from __future__ import annotations

from typing import Any

from berth.adapters.http import (
    DEFAULT_TIMEOUT_SECONDS,
    HttpSession,
    ProtocolMismatchError,
    json_body,
)
from berth.adapters.rate import TokenBucket
from berth.adapters.tmdb import (
    BASE_URL,
    TmdbConfiguration,
    TmdbEntry,
    credential_auth,
    parse_entries,
)
from berth.domain import MediaKind

#: TMDB 沒有公布上限，員工在論壇說約 50 req/s（brief §20.3）。留餘裕（plan §8.3）。
RATE_PER_SECOND = 40.0

#: **全域**一個桶：上限是每個 IP 的，不是每個 client 的。探索頁一次開三個 feed、
#: 每個 feed 兩種語言，各自造一個 client——各配一個桶就等於根本沒有上限。
_BUCKET = TokenBucket(rate=RATE_PER_SECOND, capacity=int(RATE_PER_SECOND))


class HttpTmdbClient:
    def __init__(
        self,
        credential: str,
        *,
        base_url: str = BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        bucket: TokenBucket = _BUCKET,
    ) -> None:
        headers, self._params = credential_auth(credential)
        self._session = HttpSession(base_url, headers=headers, timeout=timeout)
        self._bucket = bucket

    async def configuration(self) -> TmdbConfiguration:
        payload = await self._get("/configuration")
        images = payload.get("images")
        if not isinstance(images, dict):
            raise ProtocolMismatchError("/configuration: not a TMDB configuration payload")
        return TmdbConfiguration(image_base_url=str(images.get("secure_base_url", "")))

    async def trending(self, kind: MediaKind, *, language: str) -> tuple[TmdbEntry, ...]:
        payload = await self._get(f"/trending/{kind.value}/week", language=language)
        return parse_entries(payload.get("results"))

    async def popular(self, kind: MediaKind, *, language: str) -> tuple[TmdbEntry, ...]:
        payload = await self._get(f"/{kind.value}/popular", language=language)
        # 這一支的每一筆沒有 `media_type`，型別由端點決定。
        return parse_entries(payload.get("results"), kind=kind)

    async def search(self, query: str, *, language: str) -> tuple[TmdbEntry, ...]:
        payload = await self._get(
            "/search/multi", language=language, query=query, include_adult="false"
        )
        return parse_entries(payload.get("results"))

    async def aclose(self) -> None:
        await self._session.aclose()

    async def _get(self, path: str, **params: str) -> dict[str, Any]:
        """每一支端點都先過令牌桶，再要求回應是一個 JSON 物件。"""
        await self._bucket.acquire()
        response = await self._session.request("GET", path, params={**self._params, **params})
        payload = json_body(response)
        if not isinstance(payload, dict):
            raise ProtocolMismatchError(f"{path}: response is not a JSON object")
        return payload
