"""測試與前端演練用的 qBittorrent 替身。"""

from __future__ import annotations

from berth.adapters.qbittorrent import QbittorrentVersion


class FakeQbittorrentClient:
    def __init__(
        self,
        *,
        base_url: str = "http://qbittorrent:8080",
        version: QbittorrentVersion | None = None,
        error: Exception | None = None,
        login_error: Exception | None = None,
    ) -> None:
        self._base_url = base_url
        self._version = version or QbittorrentVersion(app="v5.2.3", webapi="2.15.1")
        self._error = error
        self._login_error = login_error
        self.calls = 0
        self.logins: list[tuple[str, str]] = []

    @property
    def base_url(self) -> str:
        return self._base_url

    async def login(self, username: str, password: str) -> None:
        self.logins.append((username, password))
        if self._login_error is not None:
            raise self._login_error

    async def version(self) -> QbittorrentVersion:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._version

    async def aclose(self) -> None:
        return None
