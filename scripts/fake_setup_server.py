"""用 Fake adapter 起一台 Berth，讓精靈的 UI 不必真的有四個容器也能實跑驗證。

真的 API、真的資料庫、真的前端 build——只有三個外部服務換成 `adapters/*/fake.py`。
Fake 是**有狀態**的，而且每個情境只有一份，所以精靈的第 3 步（plan §9.4 的七步）真的會把
那台假 Jellyfin 一步一步改掉，重按也真的會標成「已經是這樣」。

指令與情境見根目錄 README 的〈設定精靈的 Fake 後端〉。
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import tempfile
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from html import escape
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import uvicorn
from fastapi import FastAPI, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.routing import Route as StarletteRoute

from berth.adapters.http import (
    AuthFailedError,
    ProtocolMismatchError,
    ServiceBusyError,
    ServiceNotDeployedError,
    ServiceUnavailableError,
)
from berth.adapters.indexer import IndexerResult, IndexerSearch
from berth.adapters.indexer.fake import FakeIndexerSearch
from berth.adapters.indexer.prowlarr import ProwlarrSearch
from berth.adapters.jellyfin import (
    ITEM_EPISODE,
    ITEM_MOVIE,
    ITEM_SEASON,
    ITEM_SERIES,
    JellyfinClient,
    JellyfinImage,
    JellyfinItem,
    JellyfinLibrary,
    JellyfinPublicInfo,
    JellyfinSource,
    ParentImage,
    TypeOption,
)
from berth.adapters.jellyfin.fake import FakeJellyfinClient, ItemMetadata
from berth.adapters.prowlarr import ProwlarrClient, ProwlarrIndexer
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.adapters.qbittorrent import (
    QbittorrentClient,
    QbittorrentVersion,
    TorrentAdd,
    TorrentFile,
    TorrentStatus,
)
from berth.adapters.qbittorrent.client import HttpQbittorrentClient
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.adapters.rss import FeedFetcher
from berth.adapters.rss.client import HttpFeedFetcher
from berth.adapters.rss.fake import FakeFeedFetcher
from berth.adapters.rss.mikan import bangumi_url, parse_feed
from berth.adapters.tmdb import (
    TmdbClient,
    TmdbDetail,
    TmdbEntry,
    TmdbEpisode,
    TmdbSeason,
    TmdbSeasonEntry,
)
from berth.adapters.tmdb.client import HttpTmdbClient
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.adapters.torrent import (
    HttpTorrentFetcher,
    TorrentFetcher,
    TorrentSource,
    magnet_info_hash,
)
from berth.adapters.torrent_fake import FakeTorrentFetcher
from berth.adapters.torznab import TorznabClient
from berth.adapters.torznab.fake import FakeTorznabClient
from berth.api.deps import get_client_factory, get_setup_probes
from berth.config import Config, load_config
from berth.db import create_engine, create_session_factory, upgrade_to_head
from berth.domain import (
    Confidence,
    DetectionReason,
    EpisodeSnapshot,
    FileEntry,
    HealthStatus,
    IndexerKind,
    JobState,
    JobTrigger,
    MediaKind,
    MediaSnapshot,
    ParseContext,
    PlanAction,
    PlanStatus,
    PlanSummary,
    ReasonCode,
    SeasonSnapshot,
    ServiceKind,
    ServiceOrigin,
    Source,
    Tags,
    episode_label,
    why,
)
from berth.main import create_app
from berth.models import (
    IndexerSettings,
    JellyfinSettings,
    Job,
    JobFile,
    LedgerEntry,
    Media,
    PathSettings,
    Plan,
    PlanItem,
    QbittorrentSettings,
    Route,
    ServiceProbe,
    SetupAdmin,
    SetupLibrary,
    SetupSettings,
    TmdbSettings,
    media_id,
)
from berth.parser import plan as decide
from berth.services.clients import SetupProbes
from berth.services.health import check_health
from berth.services.health_issues import watch_conditions
from berth.services.routes import build_routes
from berth.services.settings import read_settings, write_settings

# `poll` 情境要現生一份 `.torrent`。bencode 與 pieces 的計算已經在實驗腳本的共用工具裡，
# 而它只用標準庫——為了一個演練情境在產品程式碼裡加一個編碼器不值得。
sys.path.insert(0, str(Path(__file__).parent / "experiments"))
from lib import Torrent, make_torrent

# `long-lists` 情境把 benchmark 語料的發佈名當成資料夾名寫出來，而「換掉檔案系統不收的字元」
# 這條規則 e2e 已經有一份（它只用標準庫）。repo 根目錄進 `sys.path` 才 import 得到 `tests.`。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.e2e.payload import info_name

# 替身 TMDB 的 SPY×FAMILY（詳情、季、絕對編號）與整合測試同一份：`issues` 情境的認領與反解
# 要的正是測試裡那一部，另抄一份的話兩邊的季集遲早對不上（M2 票 10）。
from tests.integration.test_media import tmdb as demo_tmdb
from tests.integration.test_rss import FEED as RSS_FEED
from tests.integration.test_rss import FEED_URL as RSS_FEED_URL
from tests.integration.test_rss import KIMI_ID as RSS_KIMI_ID
from tests.integration.test_rss import MIKAN as RSS_MIKAN
from tests.integration.test_rss import episode_pages as rss_episode_pages
from tests.integration.test_rss_preview import KAMIINA as RSS_KAMIINA
from tests.integration.test_rss_preview import KAMIINA_URL as RSS_KAMIINA_URL
from tests.integration.test_rss_screen import SINGLE as RSS_SINGLE
from tests.integration.test_rss_screen import SINGLE_URL as RSS_SINGLE_URL

#: 這台 demo server 自己聽在哪個 port。索引站給的下載連結指回它自己（送單時 Berth 真的會去抓），
#: 所以 `--port` 一改這一份要跟著改——寫死的話換 port 就只會拿到 `source_unavailable`。
#: `main()` 在建情境之前設定它。
DEMO_PORT = 8484


def demo_url(path: str) -> str:
    """指回這台 demo server 自己的網址（`--port` 生效）。"""
    return f"http://127.0.0.1:{DEMO_PORT}{path}"


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
    "animetosho-xyz": "Unable to connect to indexer, check the log above the ValidationFailure.",
}

#: 使用者那台 NAS 上既有媒體庫的根目錄。`main()` 換成暫存目錄底下真的存在的一層：Route 的
#: 第三條纜繩會 `stat()` 媒體庫的每一條路徑，寫死 `/volume1` 的話 `mixed` 的第 5 步在這台
#: 機器上永遠紅，既有服務那條路就走不完（票 06h）。
NAS_ROOT = "/volume1/media"


def nas_libraries() -> tuple[JellyfinLibrary, ...]:
    """使用者自己那台 Jellyfin 的媒體庫。Anime 那個掛了 TVDB，用來看警告長什麼樣。"""
    return (
        JellyfinLibrary(
            name="電影",
            item_id="a1",
            collection_type="movies",
            locations=(f"{NAS_ROOT}/movies",),
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
            locations=(f"{NAS_ROOT}/anime",),
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
        "version": "12.0.0",
        "startup_wizard_completed": True,
        "admin": ("owner", "s3cret"),
        "libraries": nas_libraries(),
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
    #: 連三條 Route 與第一輪健康檢查都跑過：健康頁與設定頁的起點（票 10、06i）。
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
    #: 打**真的**索引站。空字串時搜尋走替身（一筆結果都沒有）。與 TMDB 同一個道理：
    #: 結果表的驗收要看真的發佈名——中日英混排、100 字以上、字幕組各寫各的（票 08）。
    indexer_url: str = ""
    indexer_key: str = ""
    #: 替身索引站要回的那幾筆。真的那一台沒接上時走這裡（票 09 的送單演練）。
    indexer_results: tuple[IndexerResult, ...] = ()
    #: 打**真的** qBittorrent（票 10 的 poller 演練）。空字串時走替身。
    #: 狀態機的驗收是「送單到完成的狀態自己走完」，而替身不會下載、不會做種、
    #: 也不會在 `sync/maindata` 上換 state——那正是這一票要驗的東西。
    qbittorrent_url: str = ""
    #: 三層路徑改用**容器裡的**那一組（`/downloads/...`）。真的 qBittorrent 只用得了它
    #: 自己看得到的路徑，而 category 的 save path 是送單當下算出來的。
    container_paths: bool = False
    #: 直接把 Route 標成綠燈，不跑第 7 步那五條纜繩。
    #: **只有 `poll` 用它**：Berth 在 Windows 上看不到容器的 `/downloads`，所以
    #: `download_path` 與 `hardlink` 兩條一定紅——而紅的 Route 會擋下送單（brief §4.4），
    #: 於是這一票要驗的東西一步都跑不到。那兩條纜繩本來就有自己的驗收（票 10 的健康頁）。
    assume_routes_healthy: bool = False
    #: 這個情境要送的那幾份 torrent 的發佈名。demo server 自己生 `.torrent` 掛在
    #: `/demo/torrent?release=<發佈名>`（沒帶查詢字串就是第一份），索引站的那幾筆指向它。
    demo_releases: tuple[str, ...] = ()
    #: Route 設定頁的三種樣子（票 14）：一庫多條、紅燈建立、刪不得。見 `_seed_route_settings`。
    route_settings_demo: bool = False
    #: 媒體庫頁的整庫瀏覽與受限使用者（M1.5 票 03）。見 `_seed_library`。
    library_demo: bool = False
    #: 待處理頁與對帳（M2 票 05）。見 `_seed_issues`：真的入庫一包、真的刪掉其中一個
    #: 媒體庫檔案，所以按下「立刻對帳」真的會偵測到，按下「重新鏈接」真的會把它接回來。
    issues_demo: bool = False
    #: 審核佇列（M2 票 06）。見 `_seed_review`：兩個 medium 自動入庫的檔案真的硬鏈接在媒體庫裡，
    #: 帳本與 Plan Item 都掛著 audit——按「確認」清旗標，按「撤銷」真的把鏈接拆掉。
    review_demo: bool = False
    #: RSS 演練（M3 票 08）：`FeedFetcher` 替身查的「網址 → 原文」。空的話走真的那一支。
    feed_pages: dict[str, bytes] = field(default_factory=dict)
    #: 送單時「下載連結 → torrent」的查表。RSS 的 `.torrent` 網址是 Mikan 的，演練不出網，
    #: 所以換成這台自己生的那幾份。空的話走真的那一支。
    torrent_sources: dict[str, TorrentSource] = field(default_factory=dict)

    def probes(self) -> SetupProbes:
        return SetupProbes(
            jellyfin=self.jellyfin,
            qbittorrent=self.qbittorrent,
            prowlarr=self.prowlarr,
            prowlarr_api_key=self.prowlarr_api_key,
        )


#: 精靈試搜（票 06e）的演練：加進來的站逐站回幾筆假的最新發佈，這一站演「搜尋時連不上」——
#: 加得進來不等於每次都搜得到，畫面要撐得住一站紅、其餘照常。
TRIAL_FAILING_SITE = "mikan"


def trial_search(prowlarr: FakeProwlarrClient, base_url: str) -> FakeIndexerSearch:
    """照這台假 Prowlarr 現在有的站，逐站造出試搜的回答。"""
    by_indexer: dict[int, tuple[IndexerResult, ...]] = {}
    errors: dict[int, Exception] = {}
    for site in prowlarr.present():
        if site.definition_name == TRIAL_FAILING_SITE:
            errors[site.id] = ServiceUnavailableError(
                "GET /api/v1/search: 502 Bad Gateway (Mikan did not answer)"
            )
            continue
        by_indexer[site.id] = tuple(
            IndexerResult(title=f"[{site.name}] Sousou no Frieren - {episode:02d} [1080p]")
            for episode in range(28, 28 - (site.id * 7) % 23, -1)
        )
    return FakeIndexerSearch(base_url=base_url, by_indexer=by_indexer, indexer_errors=errors)


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


class StartingJellyfin(FakeJellyfinClient):
    """還在啟動的 Jellyfin：前幾次 `public_info` 丟 `startup` 裡的錯，之後照常回答。"""

    def __init__(self, *startup: Exception) -> None:
        super().__init__()
        self.startup = list(startup)

    async def public_info(self) -> JellyfinPublicInfo:
        if self.startup:
            raise self.startup.pop(0)
        return await super().public_info()


class StartingQbittorrent(FakeQbittorrentClient):
    """還在啟動的 qBittorrent：前幾次 `version` 丟 `startup` 裡的錯。"""

    def __init__(self, *startup: Exception) -> None:
        super().__init__()
        self.startup = list(startup)

    async def version(self) -> QbittorrentVersion:
        if self.startup:
            raise self.startup.pop(0)
        return await super().version()


class StartingProwlarr(FakeProwlarrClient):
    """還在啟動的 Prowlarr：前幾次 `ping` 丟 `startup` 裡的錯。"""

    def __init__(self, *startup: Exception, rejects: dict[str, str]) -> None:
        super().__init__(rejects=rejects)
        self.startup = list(startup)

    async def ping(self) -> None:
        if self.startup:
            raise self.startup.pop(0)
        await super().ping()


def starting() -> Scenario:
    """四個容器同時起來（票 06g 量到的時間線，票 06h 的冷啟動演練）。

    照探測的次數演，不照秒數：前端每 3 秒探一次，所以 Jellyfin 約 9 秒、Prowlarr 約 15 秒
    才起來。Jellyfin 先回不像它自己的東西、再回兩次 503「還在載入」；qBittorrent 第一次連不上；
    Prowlarr 連不上五次。之後三個都是乾淨的套件內，與 `bundled` 一樣走得完——不必按重新探測。
    """
    refused = ServiceUnavailableError("connection refused")
    loading = ServiceBusyError("GET /System/Info/Public: 503 still loading")
    return Scenario(
        jellyfin=StartingJellyfin(
            ProtocolMismatchError("/System/Info/Public: not a Jellyfin public info payload"),
            loading,
            loading,
        ),
        qbittorrent=StartingQbittorrent(refused),
        prowlarr=StartingProwlarr(*[refused] * 5, rejects=BLOCKED_SITES),
        prowlarr_api_key="00000000000000000000000000000001",
    )


def key_missing() -> Scenario:
    """Prowlarr 的設定目錄沒有唯讀掛進 Berth：讀不到 API key，第 2 步要使用者貼上。"""
    scenario = bundled()
    scenario.prowlarr_api_key = ""
    return scenario


def absent() -> Scenario:
    """Jellyfin 從 COMPOSE_PROFILES 拿掉了：探不到，要使用者填自己那一台的位址。"""
    scenario = mixed()
    scenario.jellyfin = FakeJellyfinClient(error=ServiceNotDeployedError("no such host"))
    return scenario


def old_jellyfin() -> Scenario:
    """既有 Jellyfin 還停在 10.11：泊位 1 紅燈，說得出目前版本與升級注意（brief §16.4、§20.9）。

    這是「只支援 Jellyfin 12 以上」唯一看得到的畫面（票 14b）。健康頁上同一台也是紅的。

    **其餘兩個服務照 `bundled`**，不是 `mixed`：那一份的 qBittorrent 永遠回 403，第 2 步過不去，
    而這個情境要看的是泊位 1。擋路的東西只留一個。
    """
    scenario = bundled()
    scenario.jellyfin = nas_jellyfin(version="10.11.11")
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
    但看不到設定的入口，直接打 `/api/settings/*` 也會被回 403。
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


def issues_scenario() -> Scenario:
    """待處理頁 `/issues` 與對帳（M2 票 05）。

    同 `healthy`，加上 `_seed_issues`：一包真的入庫完的檔案，其中一個媒體庫檔案被刪掉了
    ——使用者在 Jellyfin 按刪除之後就是這個樣子（brief §9.5）。按下「立刻對帳」會真的比
    四方、真的寫下一件 Issue；按下「重新鏈接」會真的 `os.link` 把它接回來。
    """
    scenario = healthy()
    scenario.qbittorrent = RecoveringQbittorrent()
    scenario.issues_demo = True
    # 認領類的兩顆要選作品、「認領進帳本」要 SPY×FAMILY 的季集（M2 票 10）：替身 TMDB 答得出
    # 搜尋與詳情，憑證是一串不打外面的假值。
    scenario.tmdb_credential = "00000000000000000000000000000010"
    scenario.tmdb = demo_tmdb(search={"spy": [SPY_ENTRY], "SPY": [SPY_ENTRY]})
    return scenario


class RecoveringQbittorrent(FakeQbittorrentClient):
    """`issues` 情境的 qBittorrent（M2 票 09c）：按下管線那三顆之後，它照真的那一台回應。

    - 重新送單的那一筆**真的回到清單上**（磁力連結的 hash 就是 Job 的 hash），否則下一輪 poller
      又會把它判成被移除。
    - 重新開始之後是 `downloading`：資料不在的那一包在真的那一台上是 `stalledDL`
      （2026-09-23 實測），演練裡讓它往前走，畫面上看得到它離開了壞掉的狀態。
    """

    async def add_torrent(self, request: TorrentAdd) -> None:
        await super().add_torrent(request)
        info_hash = magnet_info_hash(request.magnet)
        if info_hash:
            self.torrents = (*self.torrents, _pipeline_torrent(info_hash, "downloading"))

    async def start(self, info_hash: str) -> None:
        await super().start(info_hash)
        self.torrents = tuple(
            replace(row, state="downloading") if row.hash == info_hash else row
            for row in self.torrents
        )


def review_scenario() -> Scenario:
    """審核佇列 `/review`（M2 票 06）。

    同 `issues`（一件 `library_link_missing` 要先按「立刻對帳」才出現），加上 `_seed_review`：
    SPY×FAMILY 第二季的兩集只寫了絕對集號，累計換算成 S02E01、S02E02，信心 medium，
    所以自動入庫並掛 audit。兩個鏈接都是真的，撤銷真的會把它從媒體庫拿掉。另外一筆 `- 05`
    下載完成、由規劃器算成低信心而停在 review（`_seed_held_plan`，票 07）：逐列改、核准、拒絕。
    再一筆 S01E03 + OVA（`_seed_twin`，票 08）：S01E03 與媒體庫裡已有的一份一模一樣（重複），
    OVA 對不到任何一集——規劃器略過前者、後者留在原位，兩個都在佇列上等人。
    """
    scenario = issues_scenario()
    scenario.review_demo = True
    return scenario


def routes_scenario() -> Scenario:
    """Route 設定頁 `/settings/routes`（票 14）。

    同 `healthy`，加上 `_seed_route_settings` 的三種樣子：一庫多條、紅燈建立、刪不得。
    """
    scenario = healthy()
    scenario.route_settings_demo = True
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
    """有人把 qBittorrent 的建議設定改掉了：設定的 qBittorrent 那一頁的差異表與「還原建議設定」。

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


def search() -> Scenario:
    """Media 詳情頁的搜尋區塊：真的 TMDB + 真的索引站（票 08）。

    索引站位址從 `BERTH_INDEXER_URL` / `BERTH_INDEXER_KEY` 讀。沒設就退回替身，那時結果表
    是空的——那本身也是要驗的畫面之一。

    **這不是產品拿連線資訊的方式**：Berth 自己只從 `settings.services.indexer` 讀，
    由精靈第 5 步寫入。這兩個環境變數只是替演練情境省下手動跑一次精靈。
    """
    scenario = discover()
    scenario.indexer_url = os.environ.get("BERTH_INDEXER_URL", "")
    scenario.indexer_key = os.environ.get("BERTH_INDEXER_KEY", "")
    return scenario


#: 送單演練用的三筆結果。發佈名與磁力連結的形狀取自 2026-09-10 對真索引站錄下來的回應
#: （`tests/fixtures/http/prowlarr/search.spy-x-family.json`）；hash 是形狀對的假值。dmhy 那一筆
#: 沒有發佈時間，結果表的「發佈」欄顯示 `—`（M3 票 14）。
#:
#: **download_url 是磁力連結**，因為公開中文站（dmhy、TPB）給的就是它（brief §20.7）。
#: 那條路徑在 `adapters/torrent.py` 裡連請求都不必發——hash 就寫在連結裡——所以這個情境
#: 走的是真的產品程式碼，只是沒有網路。
SUBMIT_RESULTS = (
    IndexerResult(
        title="[ANi] SPY×FAMILY 間諜家家酒 - 26 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]",
        indexer="ACG.RIP",
        size=524_288_000,
        seeders=42,
        leechers=3,
        info_url="https://acg.rip/t/344604",
        download_url="magnet:?xt=urn:btih:4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b&dn=ANi.SPY",
        info_hash="4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b",
        published_at=datetime(2026, 9, 4, 13, 1, tzinfo=UTC),
    ),
    IndexerResult(
        title="SPY X FAMILY S02E01 1080p WEB H264-SKYANiME",
        indexer="The Pirate Bay",
        size=1_073_741_824,
        seeders=9,
        leechers=1,
        download_url="magnet:?xt=urn:btih:aa11bb22cc33dd44ee55ff66aa77bb88cc99dd00&dn=SKYANiME",
        info_hash="aa11bb22cc33dd44ee55ff66aa77bb88cc99dd00",
        published_at=datetime(2025, 10, 11, 2, 30, tzinfo=UTC),
    ),
    IndexerResult(
        title="[Lilith-Raws] SPY x FAMILY - 25 [Baha][WEB-DL][1080p][AVC AAC][CHT][MKV]",
        indexer="dmhy",
        size=612_368_384,
        seeders=None,
        download_url="magnet:?xt=urn:btih:JPIPN3Y5HMPDZOY6DNVWYKU4PWHF6CQ4&dn=Lilith",
        info_hash="JPIPN3Y5HMPDZOY6DNVWYKU4PWHF6CQ4",
    ),
)


def submit() -> Scenario:
    """送單與下載列表（票 09）：真的 TMDB + 一組替身的搜尋結果。

    索引站走替身而不是真的那一台，是因為這個情境要驗的是**送單之後**的事，而真的搜尋
    要 35–85 秒、每次回來的發佈也不一樣——那會讓「按這一列」變成一個不可重現的步驟。
    結果本身仍然是真的形狀（見 `SUBMIT_RESULTS`），而解析、送單、Job 與時間線全部是產品
    自己的程式碼。

    qBittorrent 是替身：它會照實收下 `torrents/add` 並記住 category 與 tag。
    真的那一台由 `scripts/experiments/` 那條路驗（M0 票 04 的參數矩陣）。
    """
    scenario = discover()
    scenario.indexer_results = SUBMIT_RESULTS
    return scenario


def submit_failing() -> Scenario:
    """qBittorrent 收不下：送單失敗那一列與它的重試（plan §3.1）。"""
    scenario = submit()
    scenario.qbittorrent.add_error = ServiceUnavailableError(
        "POST /api/v2/torrents/add: connection refused"
    )
    return scenario


#: `poll` 情境送的那一包。檔名照真實發佈的樣子，因為 `job_files.rel_path` 存的就是這一串。
POLL_RELEASE = "Berth.Poller.Demo.S01.1080p.WEB-DL"
POLL_FILES: tuple[tuple[str, int], ...] = (
    (f"{POLL_RELEASE}.E01.mkv", 40000),
    (f"Subs/{POLL_RELEASE}.E01.zh-Hant.srt", 120),
)

#: `發佈名 → 檔案清單`。`demo_torrent()` 與 `PlanningQbittorrent` 讀同一張表——那份
#: `.torrent` 裡寫的檔案與「下載完成之後磁碟上有什麼」必須是同一件事。
DEMO_PACKS: dict[str, tuple[tuple[str, int], ...]] = {}

#: 容器裡的三層路徑（brief §4.1）。真的 qBittorrent 只用得了它自己看得到的路徑。
POLL_COMPLETE_ROOT = "/downloads/complete"
POLL_INCOMPLETE_ROOT = "/downloads/incomplete"


DEMO_PACKS[POLL_RELEASE] = POLL_FILES


def poll() -> Scenario:
    """**真的** qBittorrent + 真的 poller：送單到完成的狀態自己走完（票 10）。

    與 `submit` 的差別只有一個，而那個差別就是這一票：qBittorrent 不是替身。替身收下
    `torrents/add` 之後什麼都不會發生，而這裡那一份 torrent 的資料已經先放進容器的
    save path，所以 qBittorrent 校驗完就是完成——`sync/maindata` 會真的換 state，
    poller 會真的走完 `submitted → metadata_ready → downloading → completed`。

    位址從 `BERTH_QBITTORRENT_URL` 讀。準備步驟（起容器、把資料放進去）見 README。
    """
    scenario = discover()
    scenario.qbittorrent_url = os.environ.get("BERTH_QBITTORRENT_URL", "http://127.0.0.1:18081")
    scenario.container_paths = True
    scenario.assume_routes_healthy = True
    scenario.demo_releases = (POLL_RELEASE,)
    scenario.indexer_results = (
        IndexerResult(
            title=POLL_RELEASE,
            indexer="berth-demo",
            size=sum(size for _, size in POLL_FILES),
            seeders=1,
            # demo server 自己掛的那一支。送單走的是真的 `adapters/torrent.py`：
            # 它抓下來、算 info hash、把位元組交給 qBittorrent（票 09）。
            download_url=demo_url("/demo/torrent"),
            info_hash="",
        ),
    )
    return scenario


#: `plan` 情境送的那一包：三集正片 + 一個 NCOP + 一條外掛字幕 + 一個沒人要的 readme。
#: 形狀取自真實的字幕組批次發佈（`tests/fixtures/parser/anime/`），因為 Plan 的每一列
#: 說的就是「這個檔名被讀成什麼」。
PLAN_RELEASE = "[Berth-Demo] SPY×FAMILY S01 [01-03][1080p][CHT]"
PLAN_FILES: tuple[tuple[str, int], ...] = (
    (f"{PLAN_RELEASE}/[Berth-Demo] SPY×FAMILY S01E01 [1080p][CHT].mkv", 40000),
    (f"{PLAN_RELEASE}/[Berth-Demo] SPY×FAMILY S01E02 [1080p][CHT].mkv", 40000),
    (f"{PLAN_RELEASE}/[Berth-Demo] SPY×FAMILY S01E03 [1080p][CHT].mkv", 40000),
    (f"{PLAN_RELEASE}/[Berth-Demo] SPY×FAMILY NCOP [1080p].mkv", 8000),
    (f"{PLAN_RELEASE}/Subs/[Berth-Demo] SPY×FAMILY S01E01 [1080p].cht.ass", 400),
    (f"{PLAN_RELEASE}/readme.txt", 120),
)

#: 停在 review 的那一包：對不到任何一集，所以整份 Plan 等人（brief §6.5 的 low）。
STRAY_RELEASE = "SPY×FAMILY OST Collection [FLAC]"
STRAY_FILES: tuple[tuple[str, int], ...] = (
    (f"{STRAY_RELEASE}/Disc 1/theme.mkv", 20000),
    (f"{STRAY_RELEASE}/cover.jpg", 300),
)


DEMO_PACKS.update({PLAN_RELEASE: PLAN_FILES, STRAY_RELEASE: STRAY_FILES})


class PlanningQbittorrent(FakeQbittorrentClient):
    """收下的 torrent **當場就是完成的**（`plan` 情境，票 11）。

    這一票要驗的是完成之後那一段，而替身不會下載、不會做種。所以它做兩件真的事：把那幾個
    檔案照 category 的 save path 寫出來（完成判定的第四條要 `stat` 得到它們，brief §5.1），
    再把自己報成一筆 100% 的 torrent。poller 因此在同一輪裡走完
    `submitted → metadata_ready → downloading → completed`（plan §3.1 的「一輪可以走好幾步」），
    `planner_runner` 接著算出一份真的 Plan——解析器、命名、mediainfo 全是產品自己的程式碼。
    """

    def __init__(
        self,
        packs: dict[str, tuple[tuple[str, int], ...]],
        *,
        version: QbittorrentVersion | None = None,
    ) -> None:
        super().__init__(version=version)
        #: **以那一份 torrent 的位元組認包**，不猜檔名：送單交給 `torrents/add` 的就是
        #: `adapters/torrent.py` 剛剛抓下來的那一份原文（票 09），而檔名是 HTTP 那一層
        #: 的產物，不同來源寫法不同。
        self._packs = {
            demo_torrent(release).raw: (release, files) for release, files in packs.items()
        }

    async def add_torrent(self, request: TorrentAdd) -> None:
        await super().add_torrent(request)
        found = self._packs.get(request.content)
        if found is None:
            return
        release, files = found
        info_hash = demo_torrent(release).info_hash
        save_path = next(
            (row.save_path for row in await self.categories() if row.name == request.category), ""
        )
        _write_pack(Path(save_path), files)
        now = int(datetime.now(UTC).timestamp())
        self.torrents = (
            *self.torrents,
            TorrentStatus(
                hash=info_hash,
                name=release,
                state="stalledUP",
                category=request.category,
                tags=("berth",),
                progress=1.0,
                completion_on=now,
                last_activity=now,
                added_on=now,
                save_path=save_path,
                content_path=f"{save_path}/{release}",
                total_size=sum(size for _, size in files),
            ),
        )
        self.files_by_hash[info_hash] = tuple(
            TorrentFile(index=index, name=path, size=size, priority=1, progress=1.0)
            for index, (path, size) in enumerate(files)
        )


def _write_pack(save_path: Path, files: tuple[tuple[str, int], ...]) -> None:
    """把那幾個檔案真的寫出來。內容是確定的位元組（與 `make_torrent` 算 pieces 的同一份）。

    **真的寫**而不是假裝：完成判定的第四條會逐個 `stat`（brief §5.1），而 planning 會逐個
    問 mediainfo——兩件事都要那條路徑上真的有東西。這幾個檔案不是影片，所以 mediainfo 會
    誠實地回「沒有答案」，Plan 只少一個訊號（plan §8.7）。
    """
    for path, size in files:
        target = save_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(bytes((i % 251) for i in range(size)))


def plan_scenario() -> Scenario:
    """下載完成 → Import Plan（票 11）：qBittorrent 是替身，其餘全是真的。

    索引站給兩筆：一包對得上的批次（自動入庫），與一包對不到任何一集的 OST（停在待審核）。
    兩條路徑都要看得到——M1 沒有審核佇列，所以「為什麼停在這裡」只有 Plan 那一塊說得出口。
    """
    return _planning(discover(), {PLAN_RELEASE: PLAN_FILES, STRAY_RELEASE: STRAY_FILES})


def import_scenario() -> Scenario:
    """送單到入庫整條走完、**一個請求都不出網**（M2 票 15 的前端 e2e）。

    同 `plan` 那一包對得上的批次，但 TMDB 是替身（與 `issues` 同一部 SPY×FAMILY）：CI 上沒有
    憑證、也不該去打真的 TMDB。索引站與 qBittorrent 本來就是替身，下載連結指回這台 server。
    """
    scenario = _planning(healthy(), {PLAN_RELEASE: PLAN_FILES})
    scenario.tmdb_credential = "00000000000000000000000000000010"
    scenario.tmdb = demo_tmdb()
    return scenario


def _planning(scenario: Scenario, packs: dict[str, tuple[tuple[str, int], ...]]) -> Scenario:
    """索引站給這幾包、qBittorrent 收下就當場完成（`PlanningQbittorrent`）。"""
    scenario.qbittorrent = PlanningQbittorrent(
        packs, version=QbittorrentVersion(app="v5.2.3", webapi="2.15.1")
    )
    scenario.demo_releases = tuple(packs)
    scenario.indexer_results = tuple(
        IndexerResult(
            title=release,
            indexer="berth-demo",
            size=sum(size for _, size in files),
            seeders=1,
            # 送單走的是真的那條路徑：抓下來、算 info hash、把位元組交給 qBittorrent（票 09）。
            download_url=demo_url(f"/demo/torrent?release={quote(release)}"),
            info_hash="",
        )
        for release, files in packs.items()
    )
    return scenario


#: 替身 Jellyfin 認得的影片副檔名。字幕與其他檔案不會自己成為一個 item（brief §20.1）。
VIDEO_SUFFIXES = frozenset({".mkv", ".mp4"})

#: 作品資料夾名裡的 TMDB id（plan §5 的命名模板）。Jellyfin 靠它把 Series 認成那一部作品。
TMDB_TAG = re.compile(r"\[tmdbid-(\d+)\]")


class ScanningJellyfin(FakeJellyfinClient):
    """被通知過的路徑，下一次 `items()` 就「掃到了」（`inventory` 情境，票 13）。

    一般的替身什麼都不會掃，於是反查永遠找不到東西、媒體庫的卡片永遠是「Jellyfin 還在掃描」。
    這一台照 Jellyfin 真的回的形狀長出 item（2026-09-15 對 12.0.0 實測）：劇集媒體庫裡作品資料夾
    是一個 Series、每個影片檔一個帶 `SeriesId` 的 Episode；電影媒體庫裡每個影片檔一個 Movie。
    resolver 跑的是產品自己的兩段查詢與比對，所以 Series id 是一路真的寫進帳本的。
    """

    async def items(self, library_id: str, item_types: Sequence[str]) -> tuple[JellyfinItem, ...]:
        self.items_ = [item for library in self.libraries_ for item in self._scanned(library)]
        return await super().items(library_id, item_types)

    def _scanned(self, library: JellyfinLibrary) -> list[JellyfinItem]:
        grown: dict[str, JellyfinItem] = {}
        for path in dict.fromkeys(self.notified):
            if PurePosixPath(path).suffix not in VIDEO_SUFFIXES:
                continue
            location = next((row for row in library.locations if path.startswith(f"{row}/")), None)
            if location is None:
                continue
            folder = f"{location}/{PurePosixPath(path).relative_to(location).parts[0]}"
            found = TMDB_TAG.search(folder)
            tmdb_id = found.group(1) if found else ""
            name = PurePosixPath(path).stem
            if library.collection_type == "movies":
                grown[path] = JellyfinItem(
                    id=_scanned_id(path),
                    type=ITEM_MOVIE,
                    name=name,
                    path=path,
                    tmdb_id=tmdb_id,
                    sources=(JellyfinSource(path=path, name=name),),
                )
                continue
            grown[folder] = JellyfinItem(
                id=_scanned_id(folder),
                type=ITEM_SERIES,
                name=PurePosixPath(folder).name,
                path=folder,
                tmdb_id=tmdb_id,
            )
            grown[path] = JellyfinItem(
                id=_scanned_id(path),
                type=ITEM_EPISODE,
                name=name,
                path=path,
                tmdb_id="",
                # 單一版本時 Jellyfin 的版本名就是整個檔名主幹（12.0.0 / 12.1.0 實測）。
                sources=(JellyfinSource(path=path, name=name),),
                series_id=_scanned_id(folder),
            )
        return list(grown.values())


def _scanned_id(path: str) -> str:
    """Jellyfin 的 item id 是 32 個十六進位字元。由路徑導出，重掃時同一個檔案拿到同一個 id。"""
    return hashlib.md5(path.encode(), usedforsecurity=False).hexdigest()


def inventory_scenario() -> Scenario:
    """媒體庫頁 `/library` 與 Media 詳情的檔案、版本（票 13）。

    與 `plan` 同樣兩包，只多一台會「掃到」入庫檔案的 Jellyfin：送單之後約 30 秒，resolver 第一次
    反查就找得到那一包的 Series，卡片從「Jellyfin 還在掃描」換成「在 Jellyfin 開啟」；OST 那一包
    停在待審，是「待審」篩選要找得到的那一格。

    深連結開在瀏覽器的主機名 + 8096（套件內的 Jellyfin），而那台 Jellyfin 不存在——這個情境驗的
    是 Berth 這一頁，Jellyfin 那一端由真的那一套驗（票 12 的驗收環境）。
    """
    scenario = plan_scenario()
    scenario.jellyfin = ScanningJellyfin(
        startup_wizard_completed=True,
        admin=("skipper", "harbour"),
        users={"deckhand": "rope"},
    )
    return scenario


def _corpus_pack(fixture: str) -> tuple[str, tuple[tuple[str, int], ...]]:
    """benchmark 語料的一筆（`tests/fixtures/parser/`）→ 一包演練用的發佈。

    發佈名換掉檔案系統不收的字元（`/`、`|`）**走 e2e 的 `info_name`**：替身會把它當成 save path
    底下的資料夾真的寫出來，而那一支就是為了「兩邊不各算一份」而存在的（`tests/e2e/payload.py`）。
    影片是 4 KB 的確定位元組，其他檔案 120 B。
    """
    spec = json.loads((CORPUS_ROOT / fixture).read_text(encoding="utf-8"))
    release = info_name(spec["torrent_name"])
    files = tuple(
        (
            f"{release}/{row['path']}",
            4000 if PurePosixPath(row["path"]).suffix in VIDEO_SUFFIXES else 120,
        )
        for row in spec["files"]
    )
    return release, files


#: benchmark 語料的位置。`long-lists` 情境送的是語料裡真的那一包檔案清單。
CORPUS_ROOT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "parser"

#: 葬送的芙莉蓮 `[7³ACG]` BD 合集：39 個檔案（S01 28 集 + S00 11 集），票 15 critique 量到
#: 計劃展開 9,000 px 以上的就是這一包（M1.5 票 09）。
FRIEREN_RELEASE, FRIEREN_FILES = _corpus_pack("anime/frieren-7acg-bd-batch.json")
DEMO_PACKS[FRIEREN_RELEASE] = FRIEREN_FILES


def long_lists_scenario() -> Scenario:
    """長清單（M1.5 票 09）：季表、檔案與版本、下載列的計劃撐得住真實的長度。

    同 `inventory`（會「掃到」入庫檔案的替身 Jellyfin、真的 TMDB），索引站只給芙莉蓮那一包。
    送到 Anime 那條 Route 之後，planner 算出 39 列的計劃、importer 入庫 39 個檔案、resolver
    讓替身「掃到」它們。名偵探柯南（`/media/tv:30983`）不必送單：TMDB 把它併成一季 1213 集，
    打開詳情頁就是那張季表。
    """
    scenario = inventory_scenario()
    return _planning(scenario, {FRIEREN_RELEASE: FRIEREN_FILES})


def library_scenario() -> Scenario:
    """媒體庫頁 `/library`（M1.5 票 03）：一個 Jellyfin 媒體庫一頁，整庫瀏覽加上權限。

    同 `discover`（有 `TMDB_API_KEY` 時詳情頁打真的 TMDB），Jellyfin 上另外擺好三個媒體庫的作品，
    資料庫裡擺好 Berth 經手的那幾部（`_seed_library`）。`deckhand` / `rope` 只開放 Movies 與 TV——
    Anime 在他的切換列上不存在，直接開 `/library/item-anime` 是「找不到或沒有權限」。
    `POST /demo/jellyfin/disable?user=deckhand` 在 Jellyfin 停用他（`enable` 復原），允許清單的快取
    過了之後（至多 60 秒）他的 session 結束。`bosun` / `knot` 與 `deckhand` 同樣的權限，但什麼都
    沒看過：首頁與媒體庫頁上方沒有繼續觀看與下一集（票 07）。
    """
    scenario = discover()
    scenario.jellyfin = FakeJellyfinClient(
        startup_wizard_completed=True,
        admin=("skipper", "harbour"),
        users={"deckhand": "rope", "bosun": "knot"},
        folders={"deckhand": ("item-movies", "item-tv"), "bosun": ("item-movies", "item-tv")},
    )
    scenario.library_demo = True
    return scenario


def tmdb_down() -> Scenario:
    """憑證有、TMDB 連不上：探索頁要給原文與重試，而不是一片空白。"""
    scenario = healthy()
    scenario.tmdb_credential = "00000000000000000000000000000003"
    scenario.tmdb = FakeTmdbClient(
        error=ServiceUnavailableError("GET /trending/tv/week: connection refused")
    )
    return scenario


#: `issues` 情境那一包的 info hash。是一串合法的十六進位，不是真的 torrent。
ISSUES_HASH = "5c1f0a7b2d3e4f60718293a4b5c6d7e8f9a0b1c2"

#: `review` 情境那兩集 medium 自動入庫的下載。
REVIEW_HASH = "6d2e1b8c3e4f5061728394b5c6d7e8f9a0b1c2d3"

#: `review` 情境那一筆停在 review 的低信心下載（M2 票 07）。
HELD_HASH = "7e3f2c9d4f5061728394a5b6c7d8e9f0a1b2c3d4"

#: `review` 情境那一筆帶著一個重複版本與一個對不到的 OVA 的下載（M2 票 08）。
TWIN_HASH = "8f403d0e5061728394a5b6c7d8e9f0a1b2c3d4e5"

#: `rss` 情境的那一部：喵萌奶茶屋&LoliHouse 的《与你相恋到生命尽头》，聚合 feed 裡有它的 11、12 集。
KIMI_DETAIL = TmdbDetail(
    tmdb_id=int(RSS_KIMI_ID.removeprefix("tv:")),
    kind=MediaKind.TV,
    title="Kimi ga Shinu made Koi wo Shitai",
    original_title="君が死ぬまで恋をしたい",
    year=2026,
    first_air_date=date(2026, 7, 2),
    overview="A girl who trains assassins falls for one of them.",
    poster_path="",
    titles=("Kimi ga Shinu made Koi wo Shitai", "与你相恋到生命尽头", "與妳相戀到生命盡頭"),
    seasons=(
        TmdbSeasonEntry(
            season_number=1, name="Season 1", episode_count=12, air_date=date(2026, 7, 2)
        ),
    ),
)

KIMI_SEASON = TmdbSeason(
    season_number=1,
    name="Season 1",
    air_date=date(2026, 7, 2),
    episodes=tuple(
        TmdbEpisode(
            season_number=1,
            episode_number=number,
            name=f"Episode {number}",
            air_date=date(2026, 7, 2) + timedelta(days=7 * (number - 1)),
            runtime=24,
        )
        for number in range(1, 13)
    ),
)


def _rss_pack(title: str) -> tuple[str, tuple[tuple[str, int], ...]]:
    """聚合 feed 的一筆 → 一包演練用的發佈：一個資料夾、一集影片。發佈名是檔名那一種英文寫法。"""
    episode = title.split(" - ")[1].split(" ")[0]
    release = f"[LoliHouse] Kimi ga Shinu made Koi wo Shitai - {episode} [1080p]"
    return release, ((f"{release}/{release}.mkv", 4000),)


#: 單一 feed 的 01–12（11、12 與聚合 feed 同一個 hash、同一個 `.torrent` 網址）：票 12 綁定時
#: 補舊集，每一集都要送得出去、收得下。
RSS_SEASON = parse_feed(RSS_SINGLE)
RSS_PACKS = dict(_rss_pack(item.title) for item in RSS_SEASON)
DEMO_PACKS.update(RSS_PACKS)


def rss_scenario(detail: TmdbDetail = KIMI_DETAIL, season: TmdbSeason = KIMI_SEASON) -> Scenario:
    """`/rss`（M3 票 08）：Mikan 聚合 feed → 待綁定 → 綁定 → 送單 → 入庫，**一個請求都不出網**。

    同 `healthy`（三條 Route 綠燈），加上：Mikan 是替身（票 07 錄下來的聚合 feed，單集頁照
    `tests/integration/test_rss.py` 合成，12 筆長出 11 個 RSS Series）；TMDB 是替身，搜
    「Kimi ga Shinu made Koi wo Shitai」或「与你相恋到生命尽头」找得到那一部；那兩集的 `.torrent`
    換成這台自己生的，qBittorrent 收下就當場完成（`PlanningQbittorrent`），所以綁定之後幾秒
    `/jobs` 上就有兩筆、接著規劃與入庫。

    票 09 起輪詢會自動綁定：這一部的番組頁在、TMDB 認得出它，但 TV 與 Anime 兩條 Route 都收劇集，
    所以留在待綁定、作品預填成候選——畫面走的是「一鍵選定」那一條。

    票 10 起多一份錄下來的單一 feed（喵萌奶茶屋&LoliHouse 的《与你相恋》1–12 集，11、12 與聚合 feed
    同一個 hash）：排除條件那一條流程加它，看得到重複與 RSS Series 那一層擋下的。它的單集頁都指向
    同一個 RSS Series（4009 × 370）；那一條流程綁定時取消補舊集，再用規則擋下 1–10 集。

    票 12 起綁定《与你相恋》會讀這一份單一 feed 補舊集：12 集都有這台自己生的 `.torrent`，預設全補時
    `/jobs` 上是 12 筆。

    票 11 起多一份錄下來的 acg.rip 搜尋 feed（《上伊那牡丹》30 筆，夾著 8 筆合集）：第一輪預覽那一條
    流程加它，看得到合集被排除、選「只追之後的」之後整份歷史略過。
    """
    scenario = _planning(healthy(), RSS_PACKS)
    scenario.indexer_results = ()
    scenario.tmdb_credential = "00000000000000000000000000000010"
    scenario.tmdb = FakeTmdbClient(
        details=[detail],
        seasons={detail.tmdb_id: [season]},
        search={
            query: (
                TmdbEntry(
                    tmdb_id=KIMI_DETAIL.tmdb_id,
                    kind=MediaKind.TV,
                    title=KIMI_DETAIL.title,
                    original_title=KIMI_DETAIL.original_title,
                    year=2026,
                    poster_path="",
                ),
            )
            for query in ("kimi ga shinu made koi wo shitai", "与你相恋到生命尽头")
        },
        translations={KIMI_DETAIL.tmdb_id: "與妳相戀到生命盡頭"},
    )
    scenario.feed_pages = {
        RSS_FEED_URL: RSS_FEED,
        **rss_episode_pages(),
        # 番組頁（票 09 的自動綁定讀它）：只有這一部的在，其餘十個查不到、留在待綁定。
        bangumi_url(4009): (RSS_MIKAN / "home-bangumi.4009.html").read_bytes(),
        RSS_SINGLE_URL: RSS_SINGLE,
        RSS_KAMIINA_URL: RSS_KAMIINA,
    }
    for item in parse_feed(RSS_SINGLE):
        scenario.feed_pages.setdefault(
            item.link, b'<a href="/RSS/Bangumi?bangumiId=4009&subgroupid=370" class="mikan-rss">'
        )
    scenario.torrent_sources = {
        item.torrent_url: TorrentSource(
            info_hash=demo_torrent(release).info_hash, content=demo_torrent(release).raw
        )
        for item, release in zip(RSS_SEASON, RSS_PACKS, strict=True)
    }
    return scenario


#: split-cour（M3 票 13）：TMDB 把兩個 cour 併成一季 24 集——第一 cour 一月起、第二 cour 七月起。
#: 字幕組的第二 cour 從 01 重數，所以 feed 上的 01–12 其實是 S01E13–E24。
#:
#: **播完一年之後 feed 才帶到它**（feed 的發佈時間是 2026 年）：連載中的話，播出日比對的規則二會把
#: 整批擋在審核裡（M3 票 14）——那是 `rss-split-cour-airing`（票 14b）。這一份演的是票 13 的
#: 「已入庫、改一集整季跟著搬」。
def _split_cour(first: date, second: date) -> TmdbSeason:
    return TmdbSeason(
        season_number=1,
        name="Season 1",
        air_date=first,
        episodes=tuple(
            TmdbEpisode(
                season_number=1,
                episode_number=number,
                name=f"Episode {number}",
                air_date=(
                    first + timedelta(days=7 * (number - 1))
                    if number <= 12
                    else second + timedelta(days=7 * (number - 13))
                ),
                runtime=24,
            )
            for number in range(1, 25)
        ),
    )


KIMI_SPLIT_COUR = _split_cour(date(2025, 1, 9), date(2025, 7, 3))
#: 連載中的那一份（M3 票 14b）：第二 cour 2026-07-02 開播，正是 feed 發佈的那幾週。
KIMI_SPLIT_COUR_AIRING = _split_cour(date(2026, 1, 8), date(2026, 7, 2))


def rss_split_cour_scenario() -> Scenario:
    """改正並套用到 RSS Series（M3 票 13）：同 `rss`，但 TMDB 把《与你相恋》的兩個 cour 併成一季。

    綁定時補舊集，12 集全部以「只有集號、TMDB 一季」落在 S01E01–E12（medium，錯的——字幕組的第二
    cour 從 01 重數，正解是 S01E13–E24）。它們是這個 RSS Series 的第一批，在 `/review` 是一組；在
    審核裡把第 1 集改成 S01E13 並「套用到這個 RSS Series」，其餘 11 集跟著搬到 14–24。
    """
    return _split_cour_scenario(KIMI_SPLIT_COUR)


def rss_split_cour_airing_scenario() -> Scenario:
    """從審核裡套用到 RSS Series（M3 票 14b）：同 `rss-split-cour`，但第二 cour 正在播。

    綁定時補舊集，12 集照字面對到一月播出的 S01E01–E12，而發佈當時這部作品在播的是七月之後的
    那幾集——播出日比對的規則二把 12 份計劃**整批擋在審核**、一集都沒入庫。在其中一份把第 1 集
    改成 S01E13 並「套用到這個 RSS Series」，其餘 11 份重新規劃、通過比對、自動入庫（第一批）；
    改的那一份等人核准。
    """
    return _split_cour_scenario(KIMI_SPLIT_COUR_AIRING)


def _split_cour_scenario(season: TmdbSeason) -> Scenario:
    assert season.air_date is not None
    detail = replace(
        KIMI_DETAIL,
        first_air_date=season.air_date,
        seasons=(
            TmdbSeasonEntry(
                season_number=1, name="Season 1", episode_count=24, air_date=season.air_date
            ),
        ),
    )
    return rss_scenario(detail=detail, season=season)


SCENARIOS = {
    "bundled": bundled,
    "discover": discover,
    "search": search,
    "plan": plan_scenario,
    "import": import_scenario,
    "inventory": inventory_scenario,
    "long-lists": long_lists_scenario,
    "library": library_scenario,
    "poll": poll,
    "submit": submit,
    "submit-failing": submit_failing,
    "tmdb-down": tmdb_down,
    "healthy": healthy,
    "rss": rss_scenario,
    "rss-split-cour": rss_split_cour_scenario,
    "rss-split-cour-airing": rss_split_cour_airing_scenario,
    "issues": issues_scenario,
    "review": review_scenario,
    "routes": routes_scenario,
    "degraded": degraded,
    "drifted": drifted,
    "outdated": outdated,
    "signed-out": signed_out,
    "mixed": mixed,
    "starting": starting,
    "key-missing": key_missing,
    "absent": absent,
    "old-jellyfin": old_jellyfin,
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
        if self._scenario.qbittorrent_url:
            # **每次造一個新的**：`sync/maindata` 的 rid 掛在那條連線的 session 上，而
            # `Downloader` 自己會把它握著（票 10）。共用一份反而會讓兩個呼叫端搶同一個 rid。
            return HttpQbittorrentClient(self._scenario.qbittorrent_url)
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

    def indexer_search(self, kind: IndexerKind, base_url: str, api_key: str) -> IndexerSearch:
        if self._scenario.indexer_url:
            return ProwlarrSearch(self._scenario.indexer_url, self._scenario.indexer_key)
        if not self._scenario.indexer_results and kind is IndexerKind.PROWLARR:
            return trial_search(self._scenario.prowlarr, base_url)
        return FakeIndexerSearch(base_url=base_url, results=self._scenario.indexer_results)

    def torrent(self) -> TorrentFetcher:
        """送單前把下載連結換成 info hash 與要交出去的那一份（票 09）。

        **走真的那一支**：演練用的結果給的是磁力連結，而磁力那條路徑連請求都不必發
        （hash 就寫在連結裡）。所以這裡跑的是產品自己的程式碼，只是沒有網路。
        """
        if self._scenario.torrent_sources:
            return FakeTorrentFetcher(sources=self._scenario.torrent_sources)
        return HttpTorrentFetcher()

    def rss(self) -> FeedFetcher:
        """RSS 演練讀錄下來的 Mikan feed 與合成的單集頁（`rss` 情境）；其餘情境打真的。"""
        if self._scenario.feed_pages:
            return FakeFeedFetcher(self._scenario.feed_pages)
        return HttpFeedFetcher()


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

    # 情境裡的下載連結指回這台 server 自己，所以 port 要在建情境之前就定下來。
    global DEMO_PORT, NAS_ROOT
    DEMO_PORT = args.port
    # 既有 Jellyfin 的媒體庫路徑也是：要真的存在，Route 的檢查才看得到它。
    NAS_ROOT = (config_root / "nas").as_posix()
    for folder in ("movies", "anime"):
        (config_root / "nas" / folder).mkdir(parents=True, exist_ok=True)

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
    if scenario.demo_releases:
        _mount_demo_torrent(app, scenario.demo_releases)
    if scenario.library_demo:
        _mount_demo_accounts(app, scenario.jellyfin)
    _mount_demo_qbittorrent(app, scenario.qbittorrent)

    print(f"scenario={args.scenario} config_root={config_root}", file=sys.stderr)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


def _mount_demo_torrent(app: FastAPI, releases: tuple[str, ...]) -> None:
    """把這個情境要送的那幾份 `.torrent` 掛出來（`poll` 與 `plan` 用）。

    送單走的是真的那條路徑（`adapters/torrent.py` 抓下來、算 hash、交位元組給
    qBittorrent），所以它需要一條真的 URL。**磁力連結不行**：那條路徑要 qBittorrent
    自己去 DHT 要 metadata，而演練環境裡沒有任何一個 peer。

    `?release=` 挑哪一份；沒帶就是第一份（`poll` 的那一條網址沒有查詢字串）。
    """
    payloads = {release: demo_torrent(release).raw for release in releases}

    async def endpoint(request: Request) -> Response:
        wanted = request.query_params.get("release", releases[0])
        payload = payloads.get(wanted)
        if payload is None:
            return Response(status_code=404)
        return Response(payload, media_type="application/x-bittorrent")

    # **插在最前面**：`create_app` 已經把 SPA 掛在 `/` 上，而那個 mount 會接住所有
    # 沒被更早的路由比對到的路徑——照順序 `app.get(...)` 加進去的話，這一支永遠拿到
    # `index.html`（實測：`adapters/torrent.py` 收到一頁 HTML 並正確地說「這不是 torrent」）。
    app.router.routes.insert(0, StarletteRoute("/demo/torrent", endpoint, methods=["GET"]))


def _mount_demo_accounts(app: FastAPI, jellyfin: FakeJellyfinClient) -> None:
    """`POST /demo/jellyfin/{disable,enable}?user=`：在替身 Jellyfin 上停用 / 復原一個帳號。

    演「帳號在 Jellyfin 被停用之後，Berth 的 session 結束」（M1.5 票 03）。插在最前面的理由同
    `_mount_demo_torrent`。
    """

    async def endpoint(request: Request) -> Response:
        user = request.query_params.get("user", "")
        if user not in jellyfin.users:
            return Response(status_code=404)
        if request.path_params["action"] == "disable":
            jellyfin.disabled.add(user)
        else:
            jellyfin.disabled.discard(user)
        return Response(status_code=204)

    app.router.routes.insert(
        0, StarletteRoute("/demo/jellyfin/{action:str}", endpoint, methods=["POST"])
    )


def _mount_demo_qbittorrent(app: FastAPI, qbittorrent: FakeQbittorrentClient) -> None:
    """`POST /demo/qbittorrent/fix?hash=`：使用者在 qBittorrent 裡自己把那一筆修好（M3 票 02）。

    替身上的那一筆回到 `downloading`；不在替身上的（`issues` 情境裡 `client_removed` 那一筆）
    照原樣加回去。之後的事全是產品自己的：poller 下一輪把 Job 接回主幹、系統收掉那一件 Issue。
    插在最前面的理由同 `_mount_demo_torrent`。
    """

    async def endpoint(request: Request) -> Response:
        info_hash = request.query_params.get("hash", "")
        known = {row.hash for row in qbittorrent.torrents}
        if info_hash in known:
            qbittorrent.torrents = tuple(
                replace(row, state="downloading") if row.hash == info_hash else row
                for row in qbittorrent.torrents
            )
        elif info_hash in PIPELINE_BROKEN:
            qbittorrent.torrents = (
                *qbittorrent.torrents,
                _pipeline_torrent(info_hash, "downloading"),
            )
        else:
            return Response(status_code=404)
        return Response(status_code=204)

    app.router.routes.insert(0, StarletteRoute("/demo/qbittorrent/fix", endpoint, methods=["POST"]))


def demo_torrent(release: str) -> Torrent:
    """一份情境用的 torrent。pieces 是對確定的位元組算的真 SHA-1，所以只要把同一份位元組
    放進 save path，qBittorrent 校驗完就是完成。

    檔案清單照發佈名挑：`plan` 的兩包各有自己的結構，而 `job_files.rel_path` 存的就是
    這一份裡寫的那些路徑。
    """
    files = DEMO_PACKS[release]
    # torrent 裡的路徑相對**內容根**，而 `PLAN_FILES` 寫的是 qBittorrent 報回來的樣子
    # （含根目錄那一層，brief §20.7）。多帶一層的話這一份 torrent 自己就說了謊。
    return make_torrent(release, [(path.removeprefix(f"{release}/"), size) for path, size in files])


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
        # `poll` 用容器裡的那一組：真的 qBittorrent 只用得了它自己看得到的路徑，而
        # category 的 save path 是送單當下由 `complete_root` 算出來的。library 仍然落在
        # 這一輪的暫存目錄——那一半是 Berth 自己寫的。
        incomplete_root=(
            POLL_INCOMPLETE_ROOT if scenario.container_paths else f"{data}/torrent/incomplete"
        ),
        complete_root=(
            POLL_COMPLETE_ROOT if scenario.container_paths else f"{data}/torrent/complete"
        ),
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
    if scenario.qbittorrent_url:
        # 真的那一台：偏好由使用者的容器自己決定，演練不去改它。
        pass
    else:
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
    setup.admin = SetupAdmin(
        username="skipper",
        password="harbour",
        interface_username="skipper",
        interface_password="harbour",
    )
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
        IndexerSettings(
            kind="prowlarr",
            base_url=scenario.indexer_url or "http://prowlarr:9696",
            api_key=scenario.indexer_key or "fake-key",
        ),
    )
    await write_settings(
        session,
        QbittorrentSettings(base_url=scenario.qbittorrent_url or "http://qbittorrent:8080"),
    )
    await session.commit()

    await build_routes(session, factory, ())
    if scenario.assume_routes_healthy:
        # 理由見 `Scenario.assume_routes_healthy`：Windows 上的 Berth 看不到容器的
        # `/downloads`，而紅的 Route 會擋下送單。
        for route in await session.scalars(select(Route)):
            route.health_status = HealthStatus.OK
        await session.commit()
    if scenario.preference_drift:
        # 檢查之前就改掉，第一輪就看得到漂移。
        await scenario.qbittorrent.set_preferences({"auto_tmm_enabled": False})
    await check_health(session, factory)
    if scenario.indexer_down:
        # 第一輪之後才掛掉，畫面上「最後成功」才有值——「剛剛還好好的」與「從來沒通過」
        # 是兩件不同的事（brief §16.2）。
        scenario.prowlarr.ping_error = ServiceUnavailableError("GET /ping: connection refused")
    if scenario.route_settings_demo:
        await _seed_route_settings(session, scenario, paths)
    if scenario.library_demo:
        await _seed_library(session, scenario, paths)
    if scenario.issues_demo:
        await _seed_issues(session, paths)
        await _seed_pipeline_issues(session, scenario, factory)
        await _seed_claims(session, scenario, paths)
    if scenario.review_demo:
        await _seed_review(session, paths)


async def _seed_issues(session: AsyncSession, paths: PathSettings) -> None:
    """一包真的入庫完的檔案，其中一個媒體庫檔案被刪掉了（M2 票 05）。

    **每一個檔案都是真的**：來源真的寫在 complete 底下，媒體庫那一份真的是 `os.link` 出來的
    硬鏈接，帳本記的 inode 是真的量到的。所以「立刻對帳」真的比得出差異，而「重新鏈接」真的
    把檔案接回來——畫面上那幾個數字沒有一個是寫死的。

    刪掉的是第二集：留著前後兩集才看得出對帳只挑出那一個，而不是把整包都報成失蹤。
    """
    route = await session.scalar(select(Route).where(Route.slug == "anime"))
    assert route is not None
    show = "SPY x FAMILY (2022) [tmdbid-120089]"
    source_dir = Path(f"{paths.complete_root}/anime/{show}")
    target_dir = Path(f"{route.target_path}/{show}/Season 01")
    source_dir.mkdir(parents=True, exist_ok=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    session.add(
        Media(
            id=media_id(MediaKind.TV, 120089),
            tmdb_id=120089,
            kind=MediaKind.TV,
            title_en="SPY x FAMILY",
            title_original="SPY×FAMILY",
            folder_name=show,
        )
    )
    # 先落地：`jobs.media_id` 是外鍵，同一個 flush 裡的順序不保證。
    await session.flush()
    session.add(
        Job(
            hash=ISSUES_HASH,
            name="[ANi] SPY×FAMILY - 01~03 [1080P][WEB-DL][AAC AVC][CHT]",
            source_url="",
            trigger=JobTrigger.MANUAL,
            media_id=media_id(MediaKind.TV, 120089),
            route_id=route.id,
            state=JobState.IMPORTED,
            save_path=str(source_dir.parent).replace("\\", "/"),
            content_path=str(source_dir).replace("\\", "/"),
            # 入庫過的一包一定下載完成過（poller 在那一站寫下它）；重新入庫問的就是這一格。
            completed_at=datetime.now(UTC),
            imported_at=datetime.now(UTC),
        )
    )
    await session.flush()

    for episode in (1, 2, 3):
        name = f"SPY x FAMILY (2022) - S01E{episode:02d} [1080p][CHT][ANi].mkv"
        source = source_dir / f"[ANi] SPY×FAMILY - {episode:02d}.mkv"
        target = target_dir / name
        source.write_bytes(f"episode {episode}".encode())
        target.unlink(missing_ok=True)
        os.link(source, target)
        facts = target.stat()
        session.add(
            LedgerEntry(
                job_hash=ISSUES_HASH,
                source_rel_path=f"{show}/{source.name}",
                source_abs_path=str(source).replace("\\", "/"),
                source_inode=str(facts.st_ino),
                source_dev=str(facts.st_dev),
                target_path=str(target).replace("\\", "/"),
                target_inode=str(facts.st_ino),
                media_id=media_id(MediaKind.TV, 120089),
                season=1,
                episode_start=episode,
                action=PlanAction.IMPORT,
            )
        )
    await session.commit()

    # **在 Jellyfin 裡刪掉第二集**（brief §9.5）：帳本上還有它，磁碟上沒有了。
    (target_dir / "SPY x FAMILY (2022) - S01E02 [1080p][CHT][ANi].mkv").unlink()

    # 票 09 的另外三種破壞，都在同一包旁邊，好讓一輪對帳在一頁上攤出每一種按鈕：
    # - 第三集被「複製品」取代了（大小一樣）：`inode_mismatch`，按「以硬鏈接取代」。
    third = target_dir / "SPY x FAMILY (2022) - S01E03 [1080p][CHT][ANi].mkv"
    data = third.read_bytes()
    third.unlink()
    third.write_bytes(data)
    # - qBittorrent 刪了 torrent、檔案留在 complete：`orphan_complete`，按「刪除這個目錄」。
    orphan = Path(f"{paths.complete_root}/anime/[Old] Forgotten Batch")
    orphan.mkdir(parents=True, exist_ok=True)
    (orphan / "Forgotten - 01.mkv").write_bytes(b"left behind")
    # - 有人手動放進媒體庫的檔案：`unmanaged_library_file`，只列出、沒有會刪的按鈕。
    stray = Path(f"{route.target_path}/Hand Placed (2020)/Hand Placed (2020).mkv")
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_bytes(b"put here by hand")


#: `issues` 情境裡壞掉的三筆下載（M2 票 09c）：hash → (名字, qBittorrent 報的 state)。
#: state 是空字串的那一筆不在 qBittorrent 上（`client_removed`）。
PIPELINE_BROKEN = {
    "9a514e1f6172839405b6c7d8e9f0a1b2c3d4e5f6": ("[ANi] SPY×FAMILY - 04 [1080P]", "missingFiles"),
    "ab625f207283940516c7d8e9f0a1b2c3d4e5f607": ("[ANi] SPY×FAMILY - 05 [1080P]", "error"),
    "bc73602183940516a7d8e9f0a1b2c3d4e5f60718": ("[ANi] SPY×FAMILY - 06 [1080P]", ""),
}


def _pipeline_torrent(info_hash: str, state: str) -> TorrentStatus:
    name = PIPELINE_BROKEN[info_hash][0]
    now = int(datetime.now(UTC).timestamp())
    return TorrentStatus(
        hash=info_hash,
        name=name,
        state=state,
        category="berth-anime",
        tags=("berth",),
        progress=0.4,
        completion_on=-1,
        last_activity=now,
        added_on=now,
        save_path="/data/torrent/complete/anime",
        content_path=f"/data/torrent/complete/anime/{name}",
        total_size=1_400_000_000,
    )


async def _seed_pipeline_issues(
    session: AsyncSession, scenario: Scenario, factory: FakeClientFactory
) -> None:
    """管線那三種與健康檢查那兩種之一（M2 票 09c），都由產品自己的迴圈偵測：

    - 三筆下載到一半的 Job，qBittorrent 替身說一筆 `missingFiles`、一筆 `error`、一筆已經不在。
      啟動之後 `qbit_poller` 的第一輪就把它們寫成三件 Issue，按鈕照 Job 的狀態給。
    - Anime 媒體庫掛上 TVDB 的 metadata fetcher，然後照 `health_checker` 那一步量一次。

    磁碟空間那一種不預先造：這台機器剩多少不是演練決定的。到設定的 qBittorrent 那一頁
    把門檻調到比它大，`/issues` 當場就多一件（改了立刻重量）。
    """
    route = await session.scalar(select(Route).where(Route.slug == "anime"))
    assert route is not None
    for info_hash, (name, state) in PIPELINE_BROKEN.items():
        session.add(
            Job(
                hash=info_hash,
                name=name,
                source_url=f"magnet:?xt=urn:btih:{info_hash}",
                trigger=JobTrigger.MANUAL,
                media_id=media_id(MediaKind.TV, 120089),
                route_id=route.id,
                state=JobState.DOWNLOADING,
            )
        )
        await session.flush()
        session.add(JobFile(job_hash=info_hash, rel_path=f"{name}/{name}.mkv", size=1_400_000_000))
        if state:
            scenario.qbittorrent.torrents = (
                *scenario.qbittorrent.torrents,
                _pipeline_torrent(info_hash, state),
            )
    await session.commit()

    scenario.jellyfin.libraries_ = [
        replace(
            row,
            type_options=(
                TypeOption(
                    type="Series",
                    metadata_fetchers=("TheMovieDb", "TheTVDB"),
                    image_fetchers=("TheMovieDb",),
                ),
            ),
        )
        if row.name == "Anime"
        else row
        for row in scenario.jellyfin.libraries_
    ]
    await watch_conditions(session, factory)


#: `issues` 情境裡那一筆無主 torrent（M2 票 10）：掛著 Anime 的 category，Berth 沒有它的 Job。
STRAY_HASH = "cd84713294051627b8e9f0a1b2c3d4e5f6071829"

#: 替身 TMDB 搜尋 SPY×FAMILY 時回的那一筆。
SPY_ENTRY = TmdbEntry(
    tmdb_id=120089,
    kind=MediaKind.TV,
    title="SPY x FAMILY",
    original_title="SPY×FAMILY",
    year=2022,
    poster_path="",
)


async def _seed_claims(session: AsyncSession, scenario: Scenario, paths: PathSettings) -> None:
    """認領類三顆的材料（M2 票 10）。與 `_seed_issues` 同一包、同一個作品。

    - 第四集：來源在 complete、媒體庫那一份是真的硬鏈接、名字照命名模板寫的，**帳本上沒有它**
      ——`unmanaged_library_file`，按「認領進帳本」真的長回一列（`Hand Placed` 那一件配不上，
      按下去說出為什麼）。
    - qBittorrent 上一筆掛著 Anime category、沒有 Job 的 torrent：`unknown_torrent`，按「認領並
      建立下載」選 SPY×FAMILY，下載列表多一筆。
    - complete 裡那個 `[Old] Forgotten Batch`（`_seed_issues` 造的）按「重新入庫」選作品，
      下載列表多一筆 `重新入庫` 的 Job，規劃器接手。
    """
    route = await session.scalar(select(Route).where(Route.slug == "anime"))
    assert route is not None
    show = "SPY x FAMILY (2022) [tmdbid-120089]"
    source = Path(f"{paths.complete_root}/anime/{show}/[ANi] SPY×FAMILY - 04.mkv")
    source.write_bytes(b"episode 4")
    target = Path(
        f"{route.target_path}/{show}/Season 01/SPY x FAMILY (2022) - S01E04 [1080p][CHT][ANi].mkv"
    )
    target.unlink(missing_ok=True)
    os.link(source, target)
    now = int(datetime.now(UTC).timestamp())
    scenario.qbittorrent.torrents = (
        *scenario.qbittorrent.torrents,
        TorrentStatus(
            hash=STRAY_HASH,
            name="[Sub] SPY×FAMILY - 07 [1080P]",
            state="stalledUP",
            category=route.category,
            tags=("berth",),
            progress=1.0,
            completion_on=now,
            last_activity=now,
            added_on=now,
            save_path=f"{paths.complete_root}/anime",
            content_path=f"{paths.complete_root}/anime/[Sub] SPY×FAMILY - 07 [1080P]",
            total_size=1_400_000_000,
        ),
    )


async def _seed_review(session: AsyncSession, paths: PathSettings) -> None:
    """兩個 medium 自動入庫、等人確認的檔案（M2 票 06）。接在 `_seed_issues` 後面，作品是同一部。

    **每一個檔案都是真的**，與 `_seed_issues` 同一個理由：撤銷要真的把媒體庫裡那個硬鏈接拆掉，
    畫面上說「撤銷了」而磁碟上還在，是這一票最糟的結果。Plan 也是真的一份（`applied`、兩列
    medium 掛 audit），撤銷之後它回 `pending_review`、Job 回 `review`，下載列表看得到。
    """
    route = await session.scalar(select(Route).where(Route.slug == "anime"))
    assert route is not None
    show = "SPY x FAMILY (2022) [tmdbid-120089]"
    release = "[ANi] SPY×FAMILY - 26-27 [1080P][WEB-DL][AAC AVC][CHT]"
    source_dir = Path(f"{paths.complete_root}/anime/{release}")
    target_dir = Path(f"{route.target_path}/{show}/Season 02")
    source_dir.mkdir(parents=True, exist_ok=True)
    target_dir.mkdir(parents=True, exist_ok=True)
    tv = media_id(MediaKind.TV, 120089)
    # 給作品一份快照：沒有它的話 Media 詳情整頁只剩「沒有 TMDB 憑證」，看不到 `user` 那一句
    # 「等管理員審核」（這個情境沒有 TMDB 憑證，而新鮮的快照不會去問 TMDB）。
    spy = await session.get(Media, tv)
    assert spy is not None
    aired = datetime(2022, 4, 9, tzinfo=UTC).date()
    spy.year = 2022
    spy.tmdb_snapshot_json = MediaSnapshot(
        tmdb_id=120089,
        kind=MediaKind.TV,
        title="SPY×FAMILY 間諜家家酒",
        title_en="SPY x FAMILY",
        title_original="SPY×FAMILY",
        year=2022,
        seasons=tuple(
            SeasonSnapshot(
                season_number=number,
                name=f"Season {number}",
                episode_count=count,
                air_date=aired,
                episodes=tuple(
                    EpisodeSnapshot(episode_number=episode, air_date=aired)
                    for episode in range(1, count + 1)
                ),
            )
            for number, count in ((1, 25), (2, 12))
        ),
    ).model_dump(mode="json")
    spy.tmdb_fetched_at = datetime.now(UTC)

    session.add(
        Job(
            hash=REVIEW_HASH,
            name=release,
            source_url="",
            trigger=JobTrigger.MANUAL,
            media_id=tv,
            route_id=route.id,
            state=JobState.IMPORTED,
            save_path=str(source_dir.parent).replace("\\", "/"),
            content_path=str(source_dir).replace("\\", "/"),
            # 入庫過的一包一定下載完成過（poller 在那一站寫下它）；重新入庫問的就是這一格。
            completed_at=datetime.now(UTC),
            imported_at=datetime.now(UTC),
        )
    )
    await session.flush()
    plan = Plan(
        job_hash=REVIEW_HASH,
        status=PlanStatus.APPLIED,
        summary_json=PlanSummary(files=2, medium=2, actions={"import": 2}).model_dump(mode="json"),
    )
    session.add(plan)
    await session.flush()

    for absolute, episode in ((26, 1), (27, 2)):
        source = source_dir / f"[ANi] SPY×FAMILY - {absolute}.mkv"
        target = target_dir / f"SPY x FAMILY (2022) - S02E{episode:02d} [1080p][CHT][ANi].mkv"
        source.write_bytes(f"absolute {absolute}".encode())
        target.unlink(missing_ok=True)
        os.link(source, target)
        facts = target.stat()
        item = PlanItem(
            plan_id=plan.id,
            rel_path=f"{release}/{source.name}",
            action=PlanAction.IMPORT,
            media_id=tv,
            season=2,
            episode_start=episode,
            target_path=f"{show}/Season 02/{target.name}",
            confidence=Confidence.MEDIUM,
            reasons_json=[
                why(
                    ReasonCode.ABSOLUTE_CUMULATIVE,
                    number=absolute,
                    episode=episode_label(2, episode),
                ).model_dump(mode="json")
            ],
            audit=True,
            applied_at=datetime.now(UTC),
        )
        session.add(item)
        await session.flush()
        session.add(
            LedgerEntry(
                job_hash=REVIEW_HASH,
                source_rel_path=f"{release}/{source.name}",
                source_abs_path=str(source).replace("\\", "/"),
                source_inode=str(facts.st_ino),
                source_dev=str(facts.st_dev),
                target_path=str(target).replace("\\", "/"),
                target_inode=str(facts.st_ino),
                media_id=tv,
                season=2,
                episode_start=episode,
                plan_item_id=item.id,
                action=PlanAction.IMPORT,
                audit=True,
            )
        )
    await session.commit()
    await _seed_held_plan(session, route, source_dir.parent)
    await _seed_twin(session, route, source_dir.parent)


async def _seed_held_plan(session: AsyncSession, route: Route, save_path: Path) -> None:
    """一筆下載完成、還沒規劃的 SPY×FAMILY `- 05`（M2 票 07）。

    **只放檔案與 `completed`，Plan 由產品自己的規劃器算**：伺服器起來之後 `planner_runner` 第一輪
    就掃到它。`- 05` 只寫了集號、沒超過第一季的 25 集，讀得成 S01E05，也讀得成後面某季重新從
    01 數的第 5 集——所以是 low，整份停在 review，提案 S01E05。同名的外掛字幕跟著影片走，字型略過。
    在 `/review` 改那一列的季集、看路徑當場換掉，再核准，檔案真的硬鏈接進媒體庫。
    """
    release = "[ANi] SPY×FAMILY - 05 [1080P][WEB-DL][AAC AVC][CHT]"
    folder = save_path / release
    (folder / "fonts").mkdir(parents=True, exist_ok=True)
    files = (f"{release}.mkv", f"{release}.cht.ass", "fonts/SourceHanSans.ttf")
    for name in files:
        (folder / name).write_bytes(name.encode())
    session.add(
        Job(
            hash=HELD_HASH,
            name=release,
            source_url="",
            trigger=JobTrigger.MANUAL,
            media_id=media_id(MediaKind.TV, 120089),
            route_id=route.id,
            state=JobState.COMPLETED,
            save_path=str(save_path).replace("\\", "/"),
            content_path=str(folder).replace("\\", "/"),
            progress=1.0,
            completed_at=datetime.now(UTC),
        )
    )
    session.add_all(
        [
            JobFile(job_hash=HELD_HASH, rel_path=f"{release}/{name}", size=len(name), priority=1)
            for name in files
        ]
    )
    await session.commit()


async def _seed_twin(session: AsyncSession, route: Route, save_path: Path) -> None:
    """一筆下載完成、還沒規劃的 S01E03 + OVA（M2 票 08）。**Plan 由產品自己的規劃器算**。

    媒體庫裡先放一份 S01E03：路徑與 Tags 用**解析器自己算的那一份**（對這個發佈名跑一次
    `berth.parser.plan`），來源是另一個資料夾裡的另一個檔案——所以規劃器比帳本時它是同一集、
    同一組 Tags 的重複，自動模式略過，佇列上一列 `duplicate`（取代 / 保留兩者 / 跳過）。
    OVA 2 是字幕組自己編號的特典，對不到任何一集，留在原位，佇列上一列 `unmatched`。
    兩個鏈接與來源都是真的：取代真的換掉媒體庫裡那個名字，指派真的建一條硬鏈接。
    """
    release = "[Group] SPY×FAMILY S01E03 + OVA [1080p][CHT]"
    names = ("[Group] SPY×FAMILY S01E03 [1080p][CHT].mkv", "[Group] SPY×FAMILY OVA 2 [1080p].mkv")
    folder = save_path / release
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).write_bytes(f"new {name}".encode())

    tv = media_id(MediaKind.TV, 120089)
    spy = await session.get(Media, tv)
    assert spy is not None
    snapshot = spy.stored_snapshot()
    assert snapshot is not None
    entries = tuple(FileEntry(rel_path=name, size=1_000_000_000) for name in names)
    context = ParseContext(media=snapshot, route_collection_type=route.collection_type)
    third = next(item for item in decide(release, entries, context) if item.episode_start == 3)
    old = save_path / "[Old] SPY×FAMILY S01E03" / names[0]
    old.parent.mkdir(parents=True, exist_ok=True)
    old.write_bytes(b"old copy of S01E03")
    target = Path(route.target_path) / third.target_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    os.link(old, target)
    facts = target.stat()
    session.add(
        LedgerEntry(
            job_hash=None,
            source_rel_path=f"{old.parent.name}/{old.name}",
            source_abs_path=str(old).replace("\\", "/"),
            source_inode=str(facts.st_ino),
            source_dev=str(facts.st_dev),
            target_path=str(target).replace("\\", "/"),
            target_inode=str(facts.st_ino),
            media_id=tv,
            season=1,
            episode_start=3,
            tags_json=third.tags.model_dump(mode="json"),
            action=PlanAction.IMPORT,
        )
    )
    session.add(
        Job(
            hash=TWIN_HASH,
            name=release,
            source_url="",
            trigger=JobTrigger.MANUAL,
            media_id=tv,
            route_id=route.id,
            state=JobState.COMPLETED,
            save_path=str(save_path).replace("\\", "/"),
            content_path=str(folder).replace("\\", "/"),
            progress=1.0,
            completed_at=datetime.now(UTC),
        )
    )
    session.add_all(
        [
            JobFile(job_hash=TWIN_HASH, rel_path=f"{release}/{name}", size=len(name), priority=1)
            for name in names
        ]
    )
    await session.commit()


async def _seed_route_settings(
    session: AsyncSession, scenario: Scenario, paths: PathSettings
) -> None:
    """Route 設定頁的三種樣子（票 14）。第一輪健康檢查之後才改，精靈那三條 Route 維持綠燈。

    - TV 在 Jellyfin 上多掛一顆碟，目錄真的在、與 library 同一個檔案系統：新增第二條 Route 會全綠。
    - Movies 多一條沒掛進 Berth 的路徑（目錄不存在）：在那裡建 Route，`library_path` 會紅、
      維持停用。Movies 那條既有 Route 下一次重新檢查也會紅——那是事實：Jellyfin 回報的路徑
      Berth 看不到。
    - TV 那條 Route 有一筆已經入庫的下載：刪除鍵換成「刪不得」與出路。
    """
    disk = f"{paths.library_root}-disk2/tv"
    Path(disk).mkdir(parents=True, exist_ok=True)
    unmounted = f"{paths.library_root}-unmounted/movies"
    extra = {"TV": disk, "Movies": unmounted}
    scenario.jellyfin.libraries_ = [
        replace(library, locations=(*library.locations, extra[library.name]))
        if library.name in extra
        else library
        for library in scenario.jellyfin.libraries_
    ]
    tv = await session.scalar(select(Route).where(Route.slug == "tv"))
    if tv is None:
        raise RuntimeError("the moored scenario should have built a tv route")
    # 已經入庫：poller 不會去碰一筆終態的 Job，畫面上只剩「有東西指著這條 Route」這件事。
    session.add(
        Job(
            hash="5" * 40,
            name="The.Bear.S03.1080p.WEB-DL",
            trigger=JobTrigger.MANUAL,
            route_id=tv.id,
            state=JobState.IMPORTED,
        )
    )
    await session.commit()


#: `library` 情境擺在 Jellyfin 上的作品：`(媒體庫 slug, 名稱, 年份, TMDB id)`。TMDB id 是 0 的沒有
#: provider id——牆上照樣有它，只是連不到 Berth 的詳情頁。
LIBRARY_TITLES: tuple[tuple[str, str, int, int], ...] = (
    ("tv", "The Bear", 2022, 136315),
    ("tv", "Slow Horses", 2022, 95480),
    ("tv", "Breaking Bad", 2008, 1396),
    ("tv", "Game of Thrones", 2011, 1399),
    ("tv", "Shōgun", 2024, 126308),
    ("tv", "The Office", 2005, 2316),
    ("tv", "Home Videos 2019", 2019, 0),
    ("movies", "Oppenheimer", 2023, 872585),
    ("anime", "SPY×FAMILY", 2022, 120089),
)

#: 電影媒體庫多擺這麼多部沒有 TMDB id 的片，牆才翻得到第二頁（一頁 100 部）。
FILLER_FILMS = 130

#: 類型與排序用的值（M1.5 票 06）：換排序、篩類型或年份看得出差別。`War & Politics` 帶 `&`，
#: 網址編碼走一遍。沒列的（Home Videos 2019）沒有類型、沒有評分，排序時落在升冪最前。
DEMO_METADATA: dict[str, ItemMetadata] = {
    "The Bear": ItemMetadata(("Comedy", "Drama"), {"CommunityRating": 8.2}),
    "Slow Horses": ItemMetadata(("Drama", "Thriller"), {"CommunityRating": 8.1}),
    "Breaking Bad": ItemMetadata(("Crime", "Drama"), {"CommunityRating": 8.9}),
    "Game of Thrones": ItemMetadata(("Drama", "Fantasy"), {"CommunityRating": 8.5}),
    "Shōgun": ItemMetadata(("Drama", "War & Politics"), {"CommunityRating": 8.6}),
    "The Office": ItemMetadata(("Comedy",), {"CommunityRating": 8.6}),
    "Oppenheimer": ItemMetadata(
        ("Drama", "History"), {"CommunityRating": 8.1, "CriticRating": 93, "Runtime": 180}
    ),
    "SPY×FAMILY": ItemMetadata(("Animation", "Comedy"), {"CommunityRating": 8.6}),
}


def filler_metadata(index: int) -> ItemMetadata:
    """填充片輪流是 Drama 與 Documentary，評分與片長照編號變，排序之後不是名稱順序。"""
    return ItemMetadata(
        ("Documentary",) if index % 3 == 0 else ("Drama",),
        {"CommunityRating": 5 + (index * 7 % 40) / 10, "Runtime": 80 + index * 13 % 50},
    )


#: 替身 Jellyfin 上沒有 Primary 圖的作品：牆上印「無海報」（M1.5 票 04）。
NO_POSTER = frozenset({"Home Videos 2019"})
#: DTO 帶著 tag、圖卻不見了（掃描之後被刪）：代理回 404，卡片在瀏覽器裡換成佔位。
LOST_POSTER = frozenset({"Harbour Film 007"})

#: 每部劇在替身 Jellyfin 上擺幾集（M1.5 票 05）：劇集的「剩幾集沒看」由它們算出來。
DEMO_EPISODES = 6

#: 不只一季的劇（M1.5 票 08，Media 詳情的季切換）：季號 → 集數，其餘的劇只有第 1 季六集。The Office
#: 多一季與 Specials（S00 排在最後、不算進「看過前幾集」）。
DEMO_SEASONS: dict[str, dict[int, int]] = {"The Office": {1: DEMO_EPISODES, 2: 4, 0: 1}}

#: 集有自己劇照（`Primary`）的劇（M1.5 票 08）：選季選集的橫卡畫得出劇照；其餘的劇印「無圖」。
DEMO_STILLS = frozenset({"The Bear"})

#: 誰看過什麼（M1.5 票 05），四張表各是一種紀錄。這一張是劇集看過的集數（從第一集起）；
#: 下面三張是看過的電影、看到一半的電影與看到一半的集。
#: - `deckhand`：The Bear 看到第三集、第四集看到 18%；Breaking Bad 看完；Slow Horses、Shōgun 各看
#:   一集；Game of Thrones 兩集；The Office 四集；Oppenheimer 看到 42%；Harbour Film 002 看到 65%；
#:   Harbour Film 001 看過。
#: - `skipper`：Slow Horses 看完、The Bear 看過第一集。`bosun` 什麼都沒看過。
#: 繼續觀看與下一集（票 07）由它們算出來：`deckhand` 的下一集是四部劇：The Bear 不在（第四集看到
#: 一半，只在繼續觀看）、Breaking Bad 看完了。窄版收起時看得到「全部 4 項」。
DEMO_WATCHED: dict[str, dict[str, int]] = {
    "deckhand": {
        "The Bear": 3,
        "Breaking Bad": DEMO_EPISODES,
        "Slow Horses": 1,
        "Game of Thrones": 2,
        "Shōgun": 1,
        "The Office": 4,
    },
    "skipper": {"Slow Horses": DEMO_EPISODES, "The Bear": 1},
}
DEMO_FILMS_WATCHED: dict[str, set[str]] = {"deckhand": {"Harbour Film 001"}}
DEMO_UNDER_WAY: dict[str, dict[str, float]] = {
    "deckhand": {"Harbour Film 002": 65.0, "Oppenheimer": 42.0}
}
DEMO_EPISODES_UNDER_WAY: dict[str, dict[tuple[str, int], float]] = {
    "deckhand": {("The Bear", 4): 18.0}
}
#: 橫卡的圖（票 07）：劇有 Backdrop、其中幾部另有 Thumb，集借劇的；Oppenheimer 有自己的 Thumb。
#: 沒列的（Home Videos 2019、填充片）沒有橫圖，卡片印「無圖」。
DEMO_THUMBS = frozenset({"The Bear", "Shōgun", "Oppenheimer"})
DEMO_BACKDROPS = frozenset(
    {"The Bear", "Slow Horses", "Breaking Bad", "Game of Thrones", "Shōgun", "The Office"}
)


def _demo_tag(item_id: str, image_type: str) -> str:
    """替身的 `ImageTags`：32 個十六進位字元，換圖時才會變（這裡永遠不換）。"""
    return hashlib.md5(f"{item_id}/{image_type}".encode(), usedforsecurity=False).hexdigest()


def demo_wide(name: str, image_type: str) -> JellyfinImage:
    """一張 16:9 的 SVG：與同名海報同一個色相，Thumb 亮、Backdrop 暗，看得出取的是哪一種。"""
    digest = hashlib.md5(name.encode(), usedforsecurity=False).digest()
    hue = digest[0] * 360 // 256
    light = 42 if image_type == "Thumb" else 24
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="342" height="192" viewBox="0 0 342 192">'
        f'<rect width="342" height="192" fill="hsl({hue} 45% {light}%)"/>'
        f'<rect y="140" width="342" height="8" fill="hsl({hue} 60% 62%)"/>'
        '<text x="20" y="176" font-family="ui-monospace, monospace" font-size="18" '
        f'font-weight="700" fill="#f4f1e8">{escape(name)} · {image_type}</text></svg>'
    )
    return JellyfinImage(content=svg.encode(), content_type="image/svg+xml")


def demo_still(series: str, code: str) -> JellyfinImage:
    """一張 16:9 的集劇照：與劇同一個色相、每一集換亮度，看得出每一格是自己的圖。"""
    digest = hashlib.md5(series.encode(), usedforsecurity=False).digest()
    hue = digest[0] * 360 // 256
    light = 28 + int(hashlib.md5(code.encode(), usedforsecurity=False).digest()[0]) % 24
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="342" height="192" viewBox="0 0 342 192">'
        f'<rect width="342" height="192" fill="hsl({hue} 35% {light}%)"/>'
        f'<circle cx="270" cy="70" r="44" fill="hsl({hue} 55% {light + 20}%)"/>'
        '<text x="20" y="176" font-family="ui-monospace, monospace" font-size="18" '
        f'font-weight="700" fill="#f4f1e8">{escape(series)} {escape(code)}</text></svg>'
    )
    return JellyfinImage(content=svg.encode(), content_type="image/svg+xml")


def demo_poster(name: str) -> JellyfinImage:
    """一張 2:3 的 SVG 海報：底色由名稱導出，名稱一個詞一行。

    真的 Jellyfin 回的是 WebP（研究 §6）；替身只要瀏覽器畫得出來。
    """
    digest = hashlib.md5(name.encode(), usedforsecurity=False).digest()
    hue = digest[0] * 360 // 256
    words = name.split() or [name]
    lines = "".join(
        f'<tspan x="24" dy="{0 if index == 0 else 40}">{escape(word)}</tspan>'
        for index, word in enumerate(words)
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="342" height="513" viewBox="0 0 342 513">'
        f'<rect width="342" height="513" fill="hsl({hue} 45% 32%)"/>'
        f'<rect y="360" width="342" height="12" fill="hsl({hue} 60% 62%)"/>'
        '<text y="400" font-family="ui-monospace, monospace" font-size="32" font-weight="700" '
        f'fill="#f4f1e8">{lines}</text></svg>'
    )
    return JellyfinImage(content=svg.encode(), content_type="image/svg+xml")


async def _seed_library(session: AsyncSession, scenario: Scenario, paths: PathSettings) -> None:
    """媒體庫頁的樣子（M1.5 票 03）。Jellyfin 那一端與 Berth 那一端各擺一份，彼此對得上：

    - **TV**：七部 Jellyfin 作品。The Bear 是 Berth 入庫的（S01 八集，計劃裡另有一個對不到的檔案）；
      Slow Horses 在 Jellyfin 裡、Berth 又送了一包停在待審；Severance 還在下載，Jellyfin 裡沒有它。
    - **Movies**：Oppenheimer 兩個版本；Moana 2 入庫失敗、Jellyfin 裡沒有；另有 130 部填充片
      撐出第二頁。
    - **Anime**（`deckhand` 看不到）：SPY×FAMILY 入庫了一集；葬送的芙莉蓮停在待審、Jellyfin 裡沒有。
    - **觀看狀態**（M1.5 票 05）：每部劇 `DEMO_EPISODES` 集，誰看過什麼見 `DEMO_WATCHED`。
    - **類型與評分**（M1.5 票 06）：`DEMO_METADATA` 與 `filler_metadata`。
    - **季與劇照**（M1.5 票 08）：The Office 有兩季與 Specials（`DEMO_SEASONS`），The Bear 的集有
      劇照（`DEMO_STILLS`）。
    """
    routes = {row.slug: row for row in await session.scalars(select(Route))}
    root = paths.library_root
    items: list[JellyfinItem] = []
    for slug, name, year, tmdb_id in LIBRARY_TITLES:
        folder = f"{root}/{slug}/{name} ({year})" + (f" [tmdbid-{tmdb_id}]" if tmdb_id else "")
        items.append(
            JellyfinItem(
                id=_scanned_id(folder),
                type=ITEM_MOVIE if slug == "movies" else ITEM_SERIES,
                name=name,
                path=folder,
                tmdb_id=str(tmdb_id) if tmdb_id else "",
                year=year,
            )
        )
    for index in range(1, FILLER_FILMS + 1):
        folder = f"{root}/movies/Harbour Film {index:03d} (2020)"
        items.append(
            JellyfinItem(
                id=_scanned_id(folder),
                type=ITEM_MOVIE,
                name=f"Harbour Film {index:03d}",
                path=folder,
                tmdb_id="",
                year=2020,
            )
        )
        scenario.jellyfin.metadata[items[-1].id] = filler_metadata(index)
    for item in items:
        if item.name in DEMO_METADATA:
            scenario.jellyfin.metadata[item.id] = DEMO_METADATA[item.name]
    for index, item in enumerate(items):
        thumb = _demo_tag(item.id, "Thumb") if item.name in DEMO_THUMBS else ""
        backdrop = _demo_tag(item.id, "Backdrop") if item.name in DEMO_BACKDROPS else ""
        items[index] = item = replace(item, thumb_tag=thumb, backdrop_tag=backdrop)
        for image_type, wide_tag in (("Thumb", thumb), ("Backdrop", backdrop)):
            if wide_tag:
                scenario.jellyfin.images[(item.id, image_type)] = demo_wide(item.name, image_type)
        if item.name in NO_POSTER:
            continue
        items[index] = replace(item, primary_tag=_demo_tag(item.id, "Primary"))
        if item.name not in LOST_POSTER:
            scenario.jellyfin.images[(item.id, "Primary")] = demo_poster(item.name)
    seasons: list[JellyfinItem] = []
    episodes: dict[str, list[JellyfinItem]] = {}
    for item in items:
        if item.type != ITEM_SERIES:
            continue
        episodes[item.name] = []
        for number, count in DEMO_SEASONS.get(item.name, {1: DEMO_EPISODES}).items():
            folder = f"{item.path}/" + ("Specials" if number == 0 else f"Season {number:02d}")
            season = JellyfinItem(
                id=_scanned_id(folder),
                type=ITEM_SEASON,
                name="Specials" if number == 0 else f"Season {number}",
                path=folder,
                tmdb_id="",
                series_id=item.id,
                season=number,
            )
            seasons.append(season)
            for episode in range(1, count + 1):
                code = f"S{number:02d}E{episode:02d}"
                row = JellyfinItem(
                    id=_scanned_id(file := f"{folder}/{item.name} - {code}.mkv"),
                    type=ITEM_EPISODE,
                    name=f"Episode {episode}",
                    path=file,
                    tmdb_id="",
                    series_id=item.id,
                    season_id=season.id,
                    series_name=item.name,
                    season=number,
                    episode_start=episode,
                    # 集沒有自己的橫圖：借劇的（jellyfin-web 的順序，
                    # `services/watching.landscape`）。
                    parent_thumb=ParentImage(item.id, item.thumb_tag) if item.thumb_tag else None,
                    parent_backdrop=(
                        ParentImage(item.id, item.backdrop_tag) if item.backdrop_tag else None
                    ),
                )
                if item.name in DEMO_STILLS:
                    row = replace(row, primary_tag=_demo_tag(row.id, "Primary"))
                    scenario.jellyfin.images[(row.id, "Primary")] = demo_still(item.name, code)
                episodes[item.name].append(row)
        # 「看過前幾集」照播出順序算：正片在前，Specials 排最後。
        episodes[item.name].sort(
            key=lambda row: (row.season == 0, row.season or 0, row.episode_start or 0)
        )
    found = {item.name: item for item in items}
    for user, watched in DEMO_WATCHED.items():
        scenario.jellyfin.played[user] = {
            episode.id for name, count in watched.items() for episode in episodes[name][:count]
        } | {found[name].id for name in DEMO_FILMS_WATCHED.get(user, set())}
    for user, under_way in DEMO_UNDER_WAY.items():
        scenario.jellyfin.positions[user] = {
            found[name].id: percentage for name, percentage in under_way.items()
        } | {
            episodes[name][number - 1].id: percentage
            for (name, number), percentage in DEMO_EPISODES_UNDER_WAY.get(user, {}).items()
        }
    scenario.jellyfin.items_ = [
        *items,
        *seasons,
        *(row for rows in episodes.values() for row in rows),
    ]

    bear = _demo_media(session, MediaKind.TV, 136315, "The Bear", "大熊餐廳", 2022, seasons=3)
    slow = _demo_media(session, MediaKind.TV, 95480, "Slow Horses", "流人", 2022, seasons=4)
    severance = _demo_media(
        session, MediaKind.TV, 95396, "Severance", "人生切割術", 2022, seasons=2
    )
    oppenheimer = _demo_media(session, MediaKind.MOVIE, 872585, "Oppenheimer", "奧本海默", 2023)
    moana = _demo_media(session, MediaKind.MOVIE, 1241982, "Moana 2", "海洋奇緣2", 2024)
    spy = _demo_media(
        session, MediaKind.TV, 120089, "SPY x FAMILY", "SPY×FAMILY 間諜家家酒", 2022, seasons=2
    )
    frieren = _demo_media(
        session,
        MediaKind.TV,
        209867,
        "Frieren: Beyond Journey's End",
        "葬送的芙莉蓮",
        2023,
        seasons=1,
    )
    await session.flush()

    bear_job = _demo_job(session, bear, routes["tv"], JobState.IMPORTED, "1")
    slow_job = _demo_job(session, slow, routes["tv"], JobState.REVIEW, "2")
    severance_job = _demo_job(session, severance, routes["tv"], JobState.DOWNLOADING, "3")
    _demo_job(session, oppenheimer, routes["movies"], JobState.IMPORTED, "4")
    _demo_job(session, moana, routes["movies"], JobState.IMPORT_FAILED, "5")
    _demo_job(session, spy, routes["anime"], JobState.IMPORTED, "6")
    frieren_job = _demo_job(session, frieren, routes["anime"], JobState.REVIEW, "7")
    await session.flush()

    unmatched = Plan(job_hash=bear_job.hash, status=PlanStatus.APPLIED)
    held = Plan(job_hash=frieren_job.hash, status=PlanStatus.PENDING_REVIEW)
    # 媒體庫頁的「待審」「對不到」是審核佇列的子集（M2 票 14）：TV 媒體庫上一份等審核的計劃、兩個
    # 對不到的檔案。對不到那一類以 `job_files` 為單位，所以檔案要真的有一列。
    slow_held = Plan(job_hash=slow_job.hash, status=PlanStatus.PENDING_REVIEW)
    extras = [
        JobFile(job_hash=bear_job.hash, rel_path=f"The.Bear.S01.1080p/Extras/{name}.mkv", size=1)
        for name in ("behind the scenes", "cast interview")
    ]
    session.add_all([unmatched, held, slow_held, *extras])
    await session.flush()
    session.add_all(
        [
            *(
                PlanItem(
                    plan_id=unmatched.id,
                    rel_path=extra.rel_path,
                    job_file_id=extra.id,
                    action=PlanAction.UNMATCHED,
                    media_id=bear.id,
                    confidence=Confidence.LOW,
                )
                for extra in extras
            ),
            PlanItem(
                plan_id=slow_held.id,
                rel_path="Slow.Horses.S01.1080p.WEB-DL/Slow.Horses.05.mkv",
                action=PlanAction.REVIEW,
                media_id=slow.id,
                season=1,
                episode_start=5,
                confidence=Confidence.LOW,
            ),
            PlanItem(
                plan_id=held.id,
                rel_path="[Demo] Frieren - 01-28 [1080p]/Frieren 01.mkv",
                action=PlanAction.REVIEW,
                media_id=frieren.id,
                season=1,
                episode_start=1,
                confidence=Confidence.LOW,
            ),
        ]
    )

    for episode in range(1, 9):
        _demo_link(session, bear, routes["tv"], found["The Bear"].id, season=1, episode=episode)
    for resolution in ("1080p", "2160p"):
        _demo_link(
            session, oppenheimer, routes["movies"], found["Oppenheimer"].id, resolution=resolution
        )
    _demo_link(session, spy, routes["anime"], found["SPY×FAMILY"].id, season=1, episode=1)

    # 下載中的那一筆要真的在替身 qBittorrent 裡，poller 才不會把它當成被移除（plan §3.1）。
    now = int(datetime.now(UTC).timestamp())
    save_path = f"{paths.complete_root}/tv"
    scenario.qbittorrent.torrents = (
        *scenario.qbittorrent.torrents,
        TorrentStatus(
            hash=severance_job.hash,
            name=severance_job.name,
            state="downloading",
            category="berth-tv",
            tags=("berth",),
            progress=0.42,
            completion_on=-1,
            last_activity=now,
            added_on=now,
            save_path=save_path,
            content_path=f"{save_path}/{severance_job.name}",
            total_size=24_000_000_000,
        ),
    )
    await session.commit()


def _demo_media(
    session: AsyncSession,
    kind: MediaKind,
    tmdb_id: int,
    title_en: str,
    title: str,
    year: int,
    *,
    seasons: int = 0,
) -> Media:
    """一部快照擺好的作品：每季十集、全都播過（牆上的「N / M 集」有分母可算）。"""
    aired = datetime(year, 6, 1, tzinfo=UTC).date()
    snapshot = MediaSnapshot(
        tmdb_id=tmdb_id,
        kind=kind,
        title=title,
        title_en=title_en,
        title_original=title_en,
        year=year,
        seasons=tuple(
            SeasonSnapshot(
                season_number=number,
                name=f"Season {number}",
                episode_count=10,
                air_date=aired,
                episodes=tuple(
                    EpisodeSnapshot(episode_number=episode, air_date=aired)
                    for episode in range(1, 11)
                ),
            )
            for number in range(1, seasons + 1)
        ),
    )
    row = Media(
        id=media_id(kind, tmdb_id),
        tmdb_id=tmdb_id,
        kind=kind,
        title_en=title_en,
        title_original=title_en,
        year=year,
        folder_name=f"{title_en} ({year}) [tmdbid-{tmdb_id}]",
        folder_frozen=True,
        tmdb_snapshot_json=snapshot.model_dump(mode="json"),
        tmdb_fetched_at=datetime.now(UTC),
    )
    session.add(row)
    return row


def _demo_job(
    session: AsyncSession, media: Media, route: Route, state: JobState, digit: str
) -> Job:
    row = Job(
        hash=digit * 40,
        name=f"{media.title_en.replace(' ', '.')}.1080p.WEB-DL",
        trigger=JobTrigger.MANUAL,
        media_id=media.id,
        route_id=route.id,
        state=state,
    )
    session.add(row)
    return row


def _demo_link(
    session: AsyncSession,
    media: Media,
    route: Route,
    jellyfin_id: str,
    *,
    season: int | None = None,
    episode: int | None = None,
    resolution: str = "1080p",
) -> None:
    """一筆已經反查到的帳本。劇集記下 Series id、電影記下 Movie id（`services/resolver.py`）。"""
    tags = Tags(source=Source.WEB, resolution=resolution)
    where = (
        f"Season {season:02d}/{media.title_en} - S{season:02d}E{episode:02d} {tags.render()}"
        if season is not None and episode is not None
        else f"{media.folder_name} - {tags.render()}"
    )
    session.add(
        LedgerEntry(
            source_rel_path=f"release/{where}.mkv",
            source_abs_path=f"/data/torrent/complete/{route.slug}/release/{where}.mkv",
            source_inode="1",
            source_dev="1",
            target_path=f"{route.target_path}/{media.folder_name}/{where}.mkv",
            target_inode="1",
            media_id=media.id,
            season=season,
            episode_start=episode,
            tags_json=tags.model_dump(mode="json"),
            action=PlanAction.IMPORT,
            jellyfin_item_id=f"{jellyfin_id}-{season}-{episode}" if season else jellyfin_id,
            jellyfin_series_id=jellyfin_id if season else "",
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
