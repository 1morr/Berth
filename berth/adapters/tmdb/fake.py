"""測試與前端演練用的 TMDB 替身。"""

from __future__ import annotations

from berth.adapters.tmdb import TmdbConfiguration


class FakeTmdbClient:
    def __init__(
        self,
        *,
        configuration: TmdbConfiguration | None = None,
        error: Exception | None = None,
    ) -> None:
        self._configuration = configuration or TmdbConfiguration(
            image_base_url="https://image.tmdb.org/t/p/"
        )
        self.error = error
        #: 最後一次拿到的憑證，用來斷言「用的是內建的還是使用者填的」。
        self.credential = ""
        self.calls = 0

    async def configuration(self) -> TmdbConfiguration:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self._configuration

    async def aclose(self) -> None:
        return None
