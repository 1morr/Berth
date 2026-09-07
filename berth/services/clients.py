"""從設定組出 adapter client（plan §1.3）。

`api` 不可以 import `adapters`，所以「要連哪裡、用什麼 key」這件事屬於 services。
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from berth.adapters.jellyfin import JellyfinClient
from berth.adapters.jellyfin.client import HttpJellyfinClient
from berth.adapters.prowlarr import ProwlarrClient
from berth.adapters.prowlarr.client import HttpProwlarrClient
from berth.adapters.prowlarr.config_file import read_api_key
from berth.adapters.qbittorrent import QbittorrentClient
from berth.adapters.qbittorrent.client import HttpQbittorrentClient
from berth.config import Config
from berth.services.setup import SetupProbes

#: 套件內服務的位址就是 compose 的服務名（plan §9.1）。
#: qBittorrent 的發佈 port 不可以改號碼——Host 檢查連 port 都比對（brief §20.7）。
BUNDLED_JELLYFIN_URL = "http://jellyfin:8096"
BUNDLED_QBITTORRENT_URL = "http://qbittorrent:8080"
BUNDLED_PROWLARR_URL = "http://prowlarr:9696"


def build_setup_probes(config: Config, environ: Mapping[str, str] | None = None) -> SetupProbes:
    """精靈第 2 步用的三個 client。探測的是 compose 主機名，不是使用者填的位址。"""
    env = os.environ if environ is None else environ
    api_key = read_api_key(config.prowlarr_config_path, env)
    return SetupProbes(
        jellyfin=HttpJellyfinClient(BUNDLED_JELLYFIN_URL),
        qbittorrent=HttpQbittorrentClient(BUNDLED_QBITTORRENT_URL),
        prowlarr=HttpProwlarrClient(BUNDLED_PROWLARR_URL, api_key),
        prowlarr_api_key=api_key,
    )


async def close_setup_probes(probes: SetupProbes) -> None:
    await probes.jellyfin.aclose()
    await probes.qbittorrent.aclose()
    await probes.prowlarr.aclose()


class HttpServiceClientFactory:
    """既有服務用：位址由使用者填，不是 compose 主機名。"""

    def jellyfin(self, base_url: str, token: str = "") -> JellyfinClient:
        return HttpJellyfinClient(base_url, token=token)

    def qbittorrent(self, base_url: str) -> QbittorrentClient:
        return HttpQbittorrentClient(base_url)

    def prowlarr(self, base_url: str, api_key: str) -> ProwlarrClient:
        return HttpProwlarrClient(base_url, api_key)
