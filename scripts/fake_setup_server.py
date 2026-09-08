"""用 Fake adapter 起一台 Berth，讓精靈的 UI 不必真的有四個容器也能實跑驗證。

真的 API、真的資料庫、真的前端 build——只有三個外部服務換成 `adapters/*/fake.py`。
Fake 是**有狀態**的，而且每個情境只有一份，所以精靈的第 3 步（plan §9.4 的九步）真的會把
那台假 Jellyfin 一步一步改掉，重按也真的會標成「已經是這樣」。

指令與情境見根目錄 README 的〈設定精靈的 Fake 後端〉。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

import uvicorn

from berth.adapters.http import AuthFailedError, ServiceNotDeployedError, ServiceUnavailableError
from berth.adapters.jellyfin import (
    JellyfinClient,
    JellyfinLibrary,
    JellyfinPlugin,
    JellyfinTask,
    TypeOption,
)
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.adapters.prowlarr import ProwlarrClient, ProwlarrIndexer
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.adapters.qbittorrent import QbittorrentClient, QbittorrentVersion
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.adapters.tmdb import TmdbClient
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.adapters.torznab import TorznabClient
from berth.adapters.torznab.fake import FakeTorznabClient
from berth.api.deps import get_client_factory, get_setup_probes
from berth.config import Config, load_config
from berth.db import create_engine, create_session_factory, upgrade_to_head
from berth.main import create_app
from berth.models import JellyfinSettings, SetupSettings
from berth.services.clients import SetupProbes
from berth.services.jellyfin import MERGE_VERSIONS_GUID
from berth.services.settings import read_settings, write_settings

#: 這台假 Prowlarr 連不上的站。訊息是 2026-09-08 對真的 Prowlarr 錄到的原文（brief §20.7）——
#: 十個公開站裡有幾個連不上是常態，畫面必須撐得住這個組合。
BLOCKED_SITES = {
    "nyaasi": (
        "Query successful, but no results were returned from your indexer. "
        "This may be an issue with the indexer, your indexer category settings, "
        "or other indexer settings such as search freeleech only etc."
    ),
    "1337x": "Unable to access 1337x.to, blocked by CloudFlare Protection.",
    "eztv": "Unable to access eztvx.to, blocked by CloudFlare Protection.",
    "Anidex": "Unable to connect to indexer, indexer's server is unavailable.",
    "animetosho-xyz": "Unable to connect to indexer, check the log above the ValidationFailure.",
}

#: 使用者自己那台 Jellyfin 的媒體庫。Anime 那個掛了 TVDB，用來看警告長什麼樣。
NAS_LIBRARIES = (
    JellyfinLibrary(
        name="電影",
        item_id="a1",
        collection_type="movies",
        locations=("/volume1/media/movies",),
        type_options=(
            TypeOption(
                type="Movie", metadata_fetchers=("TheMovieDb",), image_fetchers=("TheMovieDb",)
            ),
        ),
    ),
    JellyfinLibrary(
        name="Anime",
        item_id="a2",
        collection_type="tvshows",
        locations=("/volume1/media/anime",),
        type_options=(
            TypeOption(
                type="Series",
                metadata_fetchers=("TheTVDB", "TheMovieDb"),
                image_fetchers=("TheTVDB",),
            ),
        ),
    ),
)


def nas_jellyfin(**overrides: object) -> FakeJellyfinClient:
    defaults: dict[str, object] = {
        "base_url": "http://nas:8096",
        "server_name": "nas",
        "version": "10.10.7",
        "startup_wizard_completed": True,
        "admin": ("owner", "s3cret"),
        "libraries": NAS_LIBRARIES,
    }
    return FakeJellyfinClient(**{**defaults, **overrides})  # type: ignore[arg-type]


@dataclass
class Scenario:
    """一個情境的三台假服務。探測與「代為設定」用的是同一份實例，狀態才留得住。"""

    jellyfin: FakeJellyfinClient
    qbittorrent: FakeQbittorrentClient
    prowlarr: FakeProwlarrClient
    prowlarr_api_key: str
    #: 「測試連線」時 Prowlarr 要回報的索引站（貼上 key 之後判套件內還是既有）。
    connect_indexers: list[ProwlarrIndexer] = field(default_factory=list)
    #: 精靈已經跑完：整個 API 進門禁，畫面從登入頁開始（票 07）。
    setup_completed: bool = False
    #: TMDB 只有一台，位址寫死，所以情境裡就一份。
    tmdb: FakeTmdbClient = field(default_factory=FakeTmdbClient)

    def probes(self) -> SetupProbes:
        return SetupProbes(
            jellyfin=self.jellyfin,
            qbittorrent=self.qbittorrent,
            prowlarr=self.prowlarr,
            prowlarr_api_key=self.prowlarr_api_key,
        )


def bundled() -> Scenario:
    """乾淨的 compose：三個服務都還沒被設定過。"""
    return Scenario(
        jellyfin=FakeJellyfinClient(),
        qbittorrent=FakeQbittorrentClient(),
        prowlarr=FakeProwlarrClient(rejects=BLOCKED_SITES),
        prowlarr_api_key="00000000000000000000000000000001",
    )


def outdated() -> Scenario:
    """qBittorrent 太舊：Web API 低於 2.8.4，第 4 步拒絕接入並要求升級（brief §16.4）。"""
    scenario = bundled()
    scenario.qbittorrent = FakeQbittorrentClient(
        version=QbittorrentVersion(app="v4.3.9", webapi="2.8.2")
    )
    return scenario


def mixed() -> Scenario:
    """NAS 的常見組合：既有 Jellyfin（跑過自己的精靈、兩個媒體庫）、qBittorrent 已設密碼。"""
    return Scenario(
        jellyfin=nas_jellyfin(),
        qbittorrent=FakeQbittorrentClient(error=AuthFailedError("403")),
        prowlarr=FakeProwlarrClient(indexers=[ProwlarrIndexer(id=1, name="Nyaa.si", enabled=True)]),
        prowlarr_api_key="00000000000000000000000000000001",
        connect_indexers=[ProwlarrIndexer(id=1, name="Nyaa.si", enabled=True)],
    )


def starting() -> Scenario:
    """容器還在啟動：qBittorrent 連不上，其餘兩個已就緒。"""
    return Scenario(
        jellyfin=FakeJellyfinClient(version="10.10.7"),
        qbittorrent=FakeQbittorrentClient(error=ServiceUnavailableError("connection refused")),
        prowlarr=FakeProwlarrClient(),
        prowlarr_api_key="",
    )


def absent() -> Scenario:
    """Jellyfin 從 COMPOSE_PROFILES 拿掉了：探不到，要使用者填自己那一台的位址。"""
    scenario = mixed()
    scenario.jellyfin = FakeJellyfinClient(error=ServiceNotDeployedError("no such host"))
    return scenario


def installed() -> Scenario:
    """既有 Jellyfin，而且 MergeVersions 已經裝好了——兩顆按鈕的「已完成」樣子。"""
    scenario = mixed()
    scenario.jellyfin = nas_jellyfin(
        version="10.11.11",
        plugins=(
            JellyfinPlugin(
                id=MERGE_VERSIONS_GUID.replace("-", ""), name="Merge Versions", version="10.11.0.1"
            ),
        ),
        tasks=(
            JellyfinTask(id="m1", key="MergeMoviesTask", name="Merge All Movies"),
            JellyfinTask(id="e1", key="MergeEpisodesTask", name="Merge All Episodes"),
        ),
    )
    return scenario


def signed_out() -> Scenario:
    """精靈已經跑完，剩下登入（票 07）。

    `skipper` / `harbour` 是管理員，`deckhand` / `rope` 是普通使用者——後者登入後
    看不到設定入口，直接打 `/api/setup/*` 也會被回 403。
    """
    scenario = mixed()
    scenario.jellyfin = nas_jellyfin(admin=("skipper", "harbour"), users={"deckhand": "rope"})
    scenario.setup_completed = True
    return scenario


def failing() -> Scenario:
    """套件內 Jellyfin，但插件下載一直失敗——第 8 步的失敗樣子與可複製的手動步驟。"""
    scenario = bundled()
    scenario.jellyfin = FakeJellyfinClient(install_failures=99)
    return scenario


SCENARIOS = {
    "bundled": bundled,
    "outdated": outdated,
    "signed-out": signed_out,
    "failing": failing,
    "mixed": mixed,
    "starting": starting,
    "absent": absent,
    "installed": installed,
}


class FakeClientFactory:
    """回情境裡那**同一份**實例。每次造新的，第 3 步的九步就永遠從零開始。

    既有服務的「測試連線」永遠連得上，用來走通表單那條路徑。
    """

    def __init__(self, scenario: Scenario) -> None:
        self._scenario = scenario

    def jellyfin(self, base_url: str, token: str = "") -> JellyfinClient:
        if self._scenario.jellyfin.error is not None:
            # 探不到的那一台，使用者填了位址之後就該連得上。
            self._scenario.jellyfin = nas_jellyfin(base_url=base_url)
        client = self._scenario.jellyfin
        client.base_url = base_url
        if token:
            client.use_token(token)
        return client

    def qbittorrent(self, base_url: str) -> QbittorrentClient:
        if self._scenario.qbittorrent.error is not None:
            # 要帳密的那一台，使用者填了之後就該連得上。
            self._scenario.qbittorrent = FakeQbittorrentClient(base_url=base_url)
        client = self._scenario.qbittorrent
        client.base_url = base_url
        return client

    def prowlarr(self, base_url: str, api_key: str) -> ProwlarrClient:
        if base_url == self._scenario.prowlarr.base_url:
            # 套件內的那一台要回同一份實例：索引站加進去之後再讀要看得到。
            return self._scenario.prowlarr
        return FakeProwlarrClient(base_url=base_url, indexers=list(self._scenario.connect_indexers))

    def tmdb(self, credential: str) -> TmdbClient:
        return self._scenario.tmdb

    def torznab(self, base_url: str, api_key: str) -> TorznabClient:
        return FakeTorznabClient(base_url=base_url)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="bundled")
    parser.add_argument("--port", type=int, default=8484)
    parser.add_argument(
        "--config-root",
        type=Path,
        default=None,
        help="預設是一個新的暫存目錄，所以每次啟動都是乾淨環境。",
    )
    args = parser.parse_args(argv)

    config_root = args.config_root or Path(tempfile.mkdtemp(prefix="berth-fake-"))
    config = load_config({"CONFIG_ROOT": str(config_root), "DATA_ROOT": str(config_root / "data")})
    app = create_app(config)

    scenario = SCENARIOS[args.scenario]()
    if scenario.setup_completed:
        asyncio.run(_complete_setup(config))
    probes = scenario.probes()

    async def override_probes() -> AsyncIterator[SetupProbes]:
        yield probes

    factory = FakeClientFactory(scenario)
    app.dependency_overrides[get_setup_probes] = override_probes
    app.dependency_overrides[get_client_factory] = lambda: factory

    print(f"scenario={args.scenario} config_root={config_root}", file=sys.stderr)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


async def _complete_setup(config: Config) -> None:
    """把資料庫推到「精靈跑完」的狀態。票 09 的 `POST /setup/complete` 還沒有。"""
    config.config_root.mkdir(parents=True, exist_ok=True)
    engine = create_engine(config)
    try:
        await upgrade_to_head(engine)
        async with create_session_factory(engine)() as session:
            setup = await read_settings(session, SetupSettings)
            setup.completed = True
            await write_settings(session, setup)
            await write_settings(
                session, JellyfinSettings(base_url="http://jellyfin:8096", api_key="fake-key")
            )
            await session.commit()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
