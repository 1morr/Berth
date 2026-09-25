"""要連哪一台服務、用什麼憑證（plan §1.3）。

`api` 不可以 import `adapters`，所以「造一個 client」這件事屬於 services。介面（誰造）
與實作（怎麼造）都在這裡，需要 client 的命令模組只 import 這一支。
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from berth.adapters.indexer import IndexerSearch
from berth.adapters.indexer.prowlarr import ProwlarrSearch
from berth.adapters.indexer.torznab import TorznabSearch
from berth.adapters.jellyfin import JellyfinClient
from berth.adapters.jellyfin.client import HttpJellyfinClient
from berth.adapters.prowlarr import ProwlarrClient
from berth.adapters.prowlarr.client import HttpProwlarrClient
from berth.adapters.prowlarr.config_file import read_api_key
from berth.adapters.qbittorrent import QbittorrentClient
from berth.adapters.qbittorrent.client import HttpQbittorrentClient
from berth.adapters.tmdb import TmdbClient
from berth.adapters.tmdb.client import HttpTmdbClient
from berth.adapters.torrent import HttpTorrentFetcher, TorrentFetcher
from berth.adapters.torznab import TorznabClient
from berth.adapters.torznab.client import HttpTorznabClient
from berth.config import Config
from berth.domain import IndexerKind


class ServiceClientFactory(Protocol):
    """依位址造 client。探測套件內服務用的是固定主機名，不走這裡。"""

    def jellyfin(self, base_url: str, token: str = "") -> JellyfinClient: ...

    def qbittorrent(self, base_url: str) -> QbittorrentClient: ...

    def prowlarr(self, base_url: str, api_key: str) -> ProwlarrClient: ...

    def tmdb(self, credential: str) -> TmdbClient:
        """TMDB 只有一台，位址是寫死的；可變的是憑證（使用者自備，票 02b）。"""
        ...

    def torznab(self, base_url: str, api_key: str) -> TorznabClient:
        """位址是使用者貼的**整條** Torznab 網址，不是一個服務根。"""
        ...

    def torrent(self) -> TorrentFetcher:
        """送單前把索引站的下載連結換成「一個 info hash + 一份交得出去的東西」（票 09）。

        沒有位址參數：那條網址是搜尋結果自己帶的，而且**每次請求都不一樣**
        （Prowlarr 的代理連結帶 nonce，brief §20.7），所以它是呼叫時才有的東西。
        """
        ...

    def indexer_search(self, kind: IndexerKind, base_url: str, api_key: str) -> IndexerSearch:
        """搜尋用的索引站 client（票 08）。

        與上面兩支的分工是**問題不同**：`prowlarr()` 與 `torznab()` 回答「這個端點還通不通」
        （精靈與健康檢查），這一支回答「這部作品有哪些發佈」。挑哪一種實作由 `kind` 決定，
        而 `kind` 是精靈第 6 步存下來的——呼叫端不必認得兩個類別。
        """
        ...


@dataclass(frozen=True, slots=True)
class SetupProbes:
    """精靈第 2 步要探的三個 client，加上唯讀掛載讀到的 Prowlarr API key。"""

    jellyfin: JellyfinClient
    qbittorrent: QbittorrentClient
    prowlarr: ProwlarrClient
    prowlarr_api_key: str


#: 套件內服務的位址就是 compose 的服務名（plan §9.1）。qBittorrent 不在這裡：它的 WebUI port
#: 內外兩側一起換（Host 檢查連 port 都比對，brief §20.7），號碼是設定值（`build_setup_probes`）。
BUNDLED_JELLYFIN_URL = "http://jellyfin:8096"
BUNDLED_PROWLARR_URL = "http://prowlarr:9696"


def build_setup_probes(config: Config, environ: Mapping[str, str] | None = None) -> SetupProbes:
    """精靈第 2 步用的三個 client。探測的是 compose 主機名，不是使用者填的位址。

    判成套件內時，這裡的位址會記進判定（`ServiceProbe.base_url`）；之後的步驟連的是那一條，
    不再自己組一次。
    """
    env = os.environ if environ is None else environ
    api_key = read_api_key(config.prowlarr_config_path, env)
    return SetupProbes(
        jellyfin=HttpJellyfinClient(BUNDLED_JELLYFIN_URL),
        qbittorrent=HttpQbittorrentClient(f"http://qbittorrent:{config.qbittorrent_webui_port}"),
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

    def tmdb(self, credential: str) -> TmdbClient:
        return HttpTmdbClient(credential)

    def torznab(self, base_url: str, api_key: str) -> TorznabClient:
        return HttpTorznabClient(base_url, api_key)

    def torrent(self) -> TorrentFetcher:
        return HttpTorrentFetcher()

    def indexer_search(self, kind: IndexerKind, base_url: str, api_key: str) -> IndexerSearch:
        if kind is IndexerKind.TORZNAB:
            return TorznabSearch(base_url, api_key)
        return ProwlarrSearch(base_url, api_key)
