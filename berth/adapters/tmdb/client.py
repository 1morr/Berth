"""對真的 TMDB API 說話（plan §8.3）。"""

from __future__ import annotations

from berth.adapters.http import (
    DEFAULT_TIMEOUT_SECONDS,
    HttpSession,
    ProtocolMismatchError,
    json_body,
)
from berth.adapters.tmdb import BASE_URL, TmdbConfiguration, credential_auth


class HttpTmdbClient:
    def __init__(
        self,
        credential: str,
        *,
        base_url: str = BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        headers, self._params = credential_auth(credential)
        self._session = HttpSession(base_url, headers=headers, timeout=timeout)

    async def configuration(self) -> TmdbConfiguration:
        response = await self._session.request("GET", "/configuration", params=self._params)
        payload = json_body(response)
        if not isinstance(payload, dict) or "images" not in payload:
            raise ProtocolMismatchError("/configuration: not a TMDB configuration payload")
        images = payload["images"]
        if not isinstance(images, dict):
            raise ProtocolMismatchError("/configuration: images is not an object")
        return TmdbConfiguration(image_base_url=str(images.get("secure_base_url", "")))

    async def aclose(self) -> None:
        await self._session.aclose()
