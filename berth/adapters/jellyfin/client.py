"""對真的 Jellyfin 說話（brief §20.7）。"""

from __future__ import annotations

from berth.adapters.http import (
    DEFAULT_TIMEOUT_SECONDS,
    HttpSession,
    ProtocolMismatchError,
    json_body,
)
from berth.adapters.jellyfin import JellyfinPublicInfo


class HttpJellyfinClient:
    def __init__(self, base_url: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._base_url = base_url
        self._session = HttpSession(base_url, timeout=timeout)

    @property
    def base_url(self) -> str:
        return self._base_url

    async def public_info(self) -> JellyfinPublicInfo:
        response = await self._session.get("/System/Info/Public")
        payload = json_body(response)
        if not isinstance(payload, dict) or "StartupWizardCompleted" not in payload:
            raise ProtocolMismatchError("/System/Info/Public: not a Jellyfin public info payload")
        return JellyfinPublicInfo(
            server_name=str(payload.get("ServerName", "")),
            version=str(payload.get("Version", "")),
            startup_wizard_completed=bool(payload["StartupWizardCompleted"]),
        )

    async def aclose(self) -> None:
        await self._session.aclose()
