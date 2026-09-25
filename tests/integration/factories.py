"""測試共用的 client factory（`services.clients.ServiceClientFactory` 的替身）。

每個 kind 都回**同一個實例**：精靈的一步橫跨好幾次呼叫，每次造新的就等於狀態歸零。
"""

from __future__ import annotations

from berth.adapters.indexer import IndexerSearch
from berth.adapters.indexer.fake import FakeIndexerSearch
from berth.adapters.jellyfin import JellyfinClient
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.adapters.prowlarr import ProwlarrClient
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.adapters.qbittorrent import QbittorrentClient
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.adapters.rss import FeedFetcher
from berth.adapters.rss.fake import FakeFeedFetcher
from berth.adapters.tmdb import TmdbClient
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.adapters.torrent import TorrentFetcher
from berth.adapters.torrent_fake import FakeTorrentFetcher
from berth.adapters.torznab import TorznabClient
from berth.adapters.torznab.fake import FakeTorznabClient
from berth.domain import IndexerKind


class FakeClientFactory:
    def __init__(
        self,
        *,
        jellyfin: FakeJellyfinClient | None = None,
        qbittorrent: FakeQbittorrentClient | None = None,
        prowlarr: FakeProwlarrClient | None = None,
        tmdb: FakeTmdbClient | None = None,
        torznab: FakeTorznabClient | None = None,
        indexer_search: FakeIndexerSearch | None = None,
        torrent: FakeTorrentFetcher | None = None,
        rss: FakeFeedFetcher | None = None,
    ) -> None:
        self.jellyfin_ = jellyfin or FakeJellyfinClient()
        self.qbittorrent_ = qbittorrent or FakeQbittorrentClient()
        self.prowlarr_ = prowlarr or FakeProwlarrClient()
        self.tmdb_ = tmdb or FakeTmdbClient()
        self.torznab_ = torznab or FakeTorznabClient()
        self.indexer_search_ = indexer_search or FakeIndexerSearch()
        self.torrent_ = torrent or FakeTorrentFetcher()
        self.rss_ = rss or FakeFeedFetcher()
        #: 每次拿 client 時收到的憑證，用來斷言「用的是存下來的那一把」。
        self.tokens: list[str] = []
        self.api_keys: list[str] = []
        self.indexer_kinds: list[IndexerKind] = []

    def jellyfin(self, base_url: str, token: str = "") -> JellyfinClient:
        self.tokens.append(token)
        self.jellyfin_.base_url = base_url
        if token:
            self.jellyfin_.use_token(token)
        return self.jellyfin_

    def qbittorrent(self, base_url: str) -> QbittorrentClient:
        self.qbittorrent_.base_url = base_url
        return self.qbittorrent_

    def prowlarr(self, base_url: str, api_key: str) -> ProwlarrClient:
        self.api_keys.append(api_key)
        self.prowlarr_.base_url = base_url
        return self.prowlarr_

    def tmdb(self, credential: str) -> TmdbClient:
        self.tmdb_.credential = credential
        return self.tmdb_

    def torznab(self, base_url: str, api_key: str) -> TorznabClient:
        self.api_keys.append(api_key)
        self.torznab_.base_url = base_url
        return self.torznab_

    def torrent(self) -> TorrentFetcher:
        return self.torrent_

    def rss(self) -> FeedFetcher:
        return self.rss_

    def indexer_search(self, kind: IndexerKind, base_url: str, api_key: str) -> IndexerSearch:
        self.api_keys.append(api_key)
        self.indexer_search_.base_url = base_url
        # 挑到的是哪一種實作。`kind` 存在資料庫裡，斷言它才驗得出「照存下來的那一種挑」。
        self.indexer_kinds.append(kind)
        return self.indexer_search_
