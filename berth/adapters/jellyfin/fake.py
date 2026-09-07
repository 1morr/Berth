"""測試與前端演練用的 Jellyfin 替身。"""

from __future__ import annotations

from berth.adapters.jellyfin import JellyfinPublicInfo


class FakeJellyfinClient:
    """回一份固定的公開資訊，或丟出指定的例外。"""

    def __init__(
        self,
        *,
        base_url: str = "http://jellyfin:8096",
        public_info: JellyfinPublicInfo | None = None,
        error: Exception | None = None,
    ) -> None:
        self._base_url = base_url
        self._public_info = public_info or JellyfinPublicInfo(
            server_name="jellyfin",
            version="10.11.11",
            startup_wizard_completed=False,
        )
        self._error = error
        self.calls = 0

    @property
    def base_url(self) -> str:
        return self._base_url

    async def public_info(self) -> JellyfinPublicInfo:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._public_info

    async def aclose(self) -> None:
        return None
