"""用 Fake adapter 起一台 Berth，讓精靈的 UI 不必真的有四個容器也能實跑驗證。

真的 API、真的資料庫、真的前端 build——只有三個外部服務換成 `adapters/*/fake.py`。
Fake 是**有狀態**的，而且每個情境只有一份，所以精靈的第 3 步（plan §9.4 的九步）真的會把
那台假 Jellyfin 一步一步改掉，重按也真的會標成「已經是這樣」。

指令與情境見根目錄 README 的〈設定精靈的 Fake 後端〉。
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import tempfile
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import uvicorn
from sqlalchemy.ext.asyncio import AsyncSession

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
from berth.adapters.tmdb.client import HttpTmdbClient
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.adapters.torznab import TorznabClient
from berth.adapters.torznab.fake import FakeTorznabClient
from berth.api.deps import get_client_factory, get_setup_probes
from berth.config import Config, load_config
from berth.db import create_engine, create_session_factory, upgrade_to_head
from berth.domain import DetectionReason, ServiceKind, ServiceOrigin
from berth.main import create_app
from berth.models import (
    IndexerSettings,
    JellyfinSettings,
    PathSettings,
    QbittorrentSettings,
    ServiceProbe,
    SetupAdmin,
    SetupLibrary,
    SetupSettings,
    TmdbSettings,
)
from berth.services.clients import SetupProbes
from berth.services.health import check_health
from berth.services.jellyfin import MERGE_VERSIONS_GUID
from berth.services.routes import build_routes
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
    #: 連三條 Route 與第一輪健康檢查都跑過：健康頁與服務設定頁的起點（票 10）。
    moored: bool = False
    #: 第一輪檢查跑完之後才把索引站弄掉。這樣畫面上「最後成功」有值，看得出「剛剛還好好的」。
    indexer_down: bool = False
    #: 有人把 qBittorrent 的一個建議鍵改掉了（brief §16.3 的「關鍵設定漂移」）。
    preference_drift: bool = False
    #: TMDB 只有一台，位址寫死，所以情境裡就一份。
    tmdb: FakeTmdbClient = field(default_factory=FakeTmdbClient)
    #: 存進 `settings.services.tmdb` 的憑證。空的話探索頁走「憑證缺失」那條路。
    tmdb_credential: str = ""
    #: 打**真的** `api.themoviedb.org`。探索頁的驗收要看真的海報與真的 zh-TW 標題，
    #: 而那是替身演不出來的東西——它沒有 20 部作品的封面。
    real_tmdb: bool = False

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


def unmounted() -> Scenario:
    """Jellyfin 少了媒體庫目錄的掛載：泊位 4 的檢查三失敗（brief §16.4）。

    這是「哪個容器少了哪個掛載」那條訊息唯一看得到的地方——`visible_roots` 指到一條
    Berth 不會寫的路徑，所以 `Environment/ValidatePath` 對探測檔一律回看不到。
    """
    scenario = bundled()
    scenario.jellyfin = FakeJellyfinClient(visible_roots=("/somewhere-else",))
    return scenario


def healthy() -> Scenario:
    """精靈跑完、三條 Route 綠燈、四項健康檢查全綠（票 10）。

    `skipper` / `harbour` 是管理員，`deckhand` / `rope` 是普通使用者——後者看得到健康頁，
    但看不到服務設定的入口，直接打 `/api/settings/*` 也會被回 403。
    """
    scenario = bundled()
    scenario.jellyfin = FakeJellyfinClient(
        startup_wizard_completed=True,
        admin=("skipper", "harbour"),
        users={"deckhand": "rope"},
    )
    scenario.prowlarr = FakeProwlarrClient(
        indexers=[ProwlarrIndexer(id=1, name="Nyaa.si", enabled=True, definition_name="nyaasi")]
    )
    scenario.setup_completed = True
    scenario.moored = True
    return scenario


def degraded() -> Scenario:
    """索引站掛了：那一項紅、另外三項綠（票 10 驗收的第二種狀態）。

    紅的是索引站而不是 Jellyfin 或 qBittorrent，因為 Route 的檢查要問那兩台——它們掛掉時
    Route 一起紅是事實。索引站沒有人依賴它，所以它是「一項紅、其餘不受影響」最乾淨的樣子。
    """
    scenario = healthy()
    scenario.indexer_down = True
    return scenario


def drifted() -> Scenario:
    """有人把 qBittorrent 的建議設定改掉了：服務設定頁的差異表與「還原建議設定」。

    這**不是紅燈**——那台服務好好的（brief §16.3）。
    """
    scenario = healthy()
    scenario.preference_drift = True
    return scenario


def discover() -> Scenario:
    """探索頁的正常樣子：打**真的** TMDB。

    憑證從環境變數 `TMDB_API_KEY` 讀（v3 key 或 v4 read access token 都行），與實驗腳本
    同一個名字——它們要的是同一把 key。沒設就退回「憑證缺失」那條路徑，那本身也是要驗的
    畫面之一，所以不必特別處理。

    **這不是產品拿憑證的方式**：Berth 自己只從 `settings.services.tmdb.api_key` 讀，
    由精靈第 6 步寫入（票 02b）。這個環境變數只是替演練情境省下手動跑一次精靈。
    """
    scenario = healthy()
    scenario.tmdb_credential = os.environ.get("TMDB_API_KEY", "")
    scenario.real_tmdb = bool(scenario.tmdb_credential)
    return scenario


def tmdb_down() -> Scenario:
    """憑證有、TMDB 連不上：探索頁要給原文與重試，而不是一片空白。"""
    scenario = healthy()
    scenario.tmdb_credential = "00000000000000000000000000000003"
    scenario.tmdb = FakeTmdbClient(
        error=ServiceUnavailableError("GET /trending/tv/week: connection refused")
    )
    return scenario


SCENARIOS = {
    "bundled": bundled,
    "discover": discover,
    "tmdb-down": tmdb_down,
    "healthy": healthy,
    "degraded": degraded,
    "drifted": drifted,
    "outdated": outdated,
    "signed-out": signed_out,
    "failing": failing,
    "mixed": mixed,
    "starting": starting,
    "absent": absent,
    "installed": installed,
    "unmounted": unmounted,
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
        if self._scenario.real_tmdb:
            return HttpTmdbClient(credential)
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

    scenario = SCENARIOS[args.scenario]()
    factory = FakeClientFactory(scenario)
    # 背景迴圈不經過 FastAPI 的相依，所以它要用的 client 從 `create_app` 換掉（票 10）。
    app = create_app(config, clients=factory)
    asyncio.run(_seed(config, scenario, factory))
    probes = scenario.probes()

    async def override_probes() -> AsyncIterator[SetupProbes]:
        yield probes

    app.dependency_overrides[get_setup_probes] = override_probes
    app.dependency_overrides[get_client_factory] = lambda: factory

    print(f"scenario={args.scenario} config_root={config_root}", file=sys.stderr)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


async def _seed(config: Config, scenario: Scenario, factory: FakeClientFactory) -> None:
    """精靈第 7 步會**真的**建目錄、寫探測檔、呼叫 `link()`，所以三層路徑要落在這一輪的
    暫存 `DATA_ROOT` 底下，而不是容器裡的 `/data`（brief §4.1）。

    `completed=True` 的情境（`signed-out`）另外把精靈標成跑完：那條路徑要的是登入頁，
    不是再走一次八步，所以不經過 `POST /setup/complete`（它要每個 Route 都綠燈）。

    `moored=True` 的情境（`healthy` / `degraded`）再往前推一步：把精靈跑完後的設定寫進去、
    真的建三條 Route、真的跑一輪健康檢查。跑的是與正式環境同一組 services 命令，所以畫面上
    的 inode、可用空間、版本號全都是這一輪量到的，不是寫死的假資料。
    """
    config.config_root.mkdir(parents=True, exist_ok=True)
    # 容器裡的路徑一律是 POSIX 形狀，畫面上顯示的也就是那個形狀。Windows 上開發時把
    # 反斜線換掉，看到的才與正式部署一致（`os` 兩種分隔符都吃）。
    data = str(config.data_root).replace("\\", "/").rstrip("/")
    paths = PathSettings(
        incomplete_root=f"{data}/torrent/incomplete",
        complete_root=f"{data}/torrent/complete",
        library_root=f"{data}/library",
    )
    engine = create_engine(config)
    try:
        await upgrade_to_head(engine)
        async with create_session_factory(engine)() as session:
            await write_settings(session, paths)
            if scenario.setup_completed:
                setup = await read_settings(session, SetupSettings)
                setup.completed = True
                await write_settings(session, setup)
                await write_settings(
                    session, JellyfinSettings(base_url="http://jellyfin:8096", api_key="fake-key")
                )
            if scenario.tmdb_credential:
                await write_settings(session, TmdbSettings(api_key=scenario.tmdb_credential))
            await session.commit()
            if scenario.moored:
                await _moor(session, scenario, factory, paths)
    finally:
        await engine.dispose()


async def _moor(
    session: AsyncSession,
    scenario: Scenario,
    factory: FakeClientFactory,
    paths: PathSettings,
) -> None:
    """把資料庫推到「精靈跑完的隔天」：三條 Route 都在，健康檢查跑過一輪。"""
    for slug in ("movies", "tv", "anime"):
        Path(f"{paths.library_root}/{slug}").mkdir(parents=True, exist_ok=True)
    scenario.jellyfin.libraries_ = [
        JellyfinLibrary(
            name=name,
            item_id=f"item-{slug}",
            collection_type=collection_type,
            locations=(f"{paths.library_root}/{slug}",),
            type_options=(),
        )
        for slug, name, collection_type in (
            ("movies", "Movies", "movies"),
            ("tv", "TV", "tvshows"),
            ("anime", "Anime", "tvshows"),
        )
    ]
    await scenario.qbittorrent.set_preferences(
        {
            "save_path": paths.complete_root,
            "temp_path": paths.incomplete_root,
            "temp_path_enabled": True,
            "auto_tmm_enabled": True,
            "category_changed_tmm_enabled": True,
        }
    )

    setup = await read_settings(session, SetupSettings)
    setup.admin = SetupAdmin(username="skipper", password="harbour")
    setup.services = {
        kind: ServiceProbe(
            origin=ServiceOrigin.BUNDLED,
            reason=reason,
            base_url=base_url,
            checked_at=datetime.now(UTC),
        )
        for kind, reason, base_url in (
            (ServiceKind.JELLYFIN, DetectionReason.SETUP_PENDING, "http://jellyfin:8096"),
            (ServiceKind.QBITTORRENT, DetectionReason.ANONYMOUS_OK, "http://qbittorrent:8080"),
            (ServiceKind.PROWLARR, DetectionReason.NO_INDEXERS, "http://prowlarr:9696"),
        )
    }
    setup.jellyfin.libraries = [
        SetupLibrary(
            name=library.name,
            item_id=library.item_id,
            collection_type=library.collection_type,
            locations=list(library.locations),
        )
        for library in scenario.jellyfin.libraries_
    ]
    await write_settings(session, setup)
    await write_settings(
        session,
        IndexerSettings(kind="prowlarr", base_url="http://prowlarr:9696", api_key="fake-key"),
    )
    await write_settings(session, QbittorrentSettings(base_url="http://qbittorrent:8080"))
    await session.commit()

    await build_routes(session, factory, ())
    if scenario.preference_drift:
        # 檢查之前就改掉，第一輪就看得到漂移。
        await scenario.qbittorrent.set_preferences({"auto_tmm_enabled": False})
    await check_health(session, factory)
    if scenario.indexer_down:
        # 第一輪之後才掛掉，畫面上「最後成功」才有值——「剛剛還好好的」與「從來沒通過」
        # 是兩件不同的事（brief §16.2）。
        scenario.prowlarr.ping_error = ServiceUnavailableError("GET /ping: connection refused")


if __name__ == "__main__":
    raise SystemExit(main())
