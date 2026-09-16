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
import os
import re
import sys
import tempfile
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import uvicorn
from fastapi import FastAPI, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.routing import Route as StarletteRoute

from berth.adapters.http import AuthFailedError, ServiceNotDeployedError, ServiceUnavailableError
from berth.adapters.indexer import IndexerResult, IndexerSearch
from berth.adapters.indexer.fake import FakeIndexerSearch
from berth.adapters.indexer.prowlarr import ProwlarrSearch
from berth.adapters.jellyfin import (
    ITEM_EPISODE,
    ITEM_MOVIE,
    ITEM_SERIES,
    JellyfinClient,
    JellyfinItem,
    JellyfinLibrary,
    JellyfinSource,
    TypeOption,
)
from berth.adapters.jellyfin.fake import FakeJellyfinClient
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
from berth.adapters.tmdb import TmdbClient
from berth.adapters.tmdb.client import HttpTmdbClient
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.adapters.torrent import HttpTorrentFetcher, TorrentFetcher
from berth.adapters.torznab import TorznabClient
from berth.adapters.torznab.fake import FakeTorznabClient
from berth.api.deps import get_client_factory, get_setup_probes
from berth.config import Config, load_config
from berth.db import create_engine, create_session_factory, upgrade_to_head
from berth.domain import (
    DetectionReason,
    HealthStatus,
    IndexerKind,
    JobState,
    JobTrigger,
    ServiceKind,
    ServiceOrigin,
)
from berth.main import create_app
from berth.models import (
    IndexerSettings,
    JellyfinSettings,
    Job,
    PathSettings,
    QbittorrentSettings,
    Route,
    ServiceProbe,
    SetupAdmin,
    SetupLibrary,
    SetupSettings,
    TmdbSettings,
)
from berth.services.clients import SetupProbes
from berth.services.health import check_health
from berth.services.routes import build_routes
from berth.services.settings import read_settings, write_settings

# `poll` 情境要現生一份 `.torrent`。bencode 與 pieces 的計算已經在實驗腳本的共用工具裡，
# 而它只用標準庫——為了一個演練情境在產品程式碼裡加一個編碼器不值得。
sys.path.insert(0, str(Path(__file__).parent / "experiments"))
from lib import Torrent, make_torrent

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
        "version": "12.0.0",
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
        jellyfin=FakeJellyfinClient(),
        qbittorrent=FakeQbittorrentClient(error=ServiceUnavailableError("connection refused")),
        prowlarr=FakeProwlarrClient(),
        prowlarr_api_key="",
    )


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
#: （`tests/fixtures/http/prowlarr/search.spy-x-family.json`）；hash 是形狀對的假值。
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
    ),
    IndexerResult(
        title="SPY X FAMILY S02E01 1080p WEB H264-SKYANiME",
        indexer="The Pirate Bay",
        size=1_073_741_824,
        seeders=9,
        leechers=1,
        download_url="magnet:?xt=urn:btih:aa11bb22cc33dd44ee55ff66aa77bb88cc99dd00&dn=SKYANiME",
        info_hash="aa11bb22cc33dd44ee55ff66aa77bb88cc99dd00",
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
            download_url="http://127.0.0.1:8484/demo/torrent",
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
    scenario = discover()
    scenario.qbittorrent = PlanningQbittorrent(
        {PLAN_RELEASE: PLAN_FILES, STRAY_RELEASE: STRAY_FILES},
        version=QbittorrentVersion(app="v5.2.3", webapi="2.15.1"),
    )
    scenario.demo_releases = (PLAN_RELEASE, STRAY_RELEASE)
    scenario.indexer_results = tuple(
        IndexerResult(
            title=release,
            indexer="berth-demo",
            size=sum(size for _, size in files),
            seeders=1,
            # 送單走的是真的那條路徑：抓下來、算 info hash、把位元組交給 qBittorrent（票 09）。
            download_url=f"http://127.0.0.1:8484/demo/torrent?release={quote(release)}",
            info_hash="",
        )
        for release, files in ((PLAN_RELEASE, PLAN_FILES), (STRAY_RELEASE, STRAY_FILES))
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
    "search": search,
    "plan": plan_scenario,
    "inventory": inventory_scenario,
    "poll": poll,
    "submit": submit,
    "submit-failing": submit_failing,
    "tmdb-down": tmdb_down,
    "healthy": healthy,
    "routes": routes_scenario,
    "degraded": degraded,
    "drifted": drifted,
    "outdated": outdated,
    "signed-out": signed_out,
    "mixed": mixed,
    "starting": starting,
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
        return FakeIndexerSearch(base_url=base_url, results=self._scenario.indexer_results)

    def torrent(self) -> TorrentFetcher:
        """送單前把下載連結換成 info hash 與要交出去的那一份（票 09）。

        **走真的那一支**：演練用的結果給的是磁力連結，而磁力那條路徑連請求都不必發
        （hash 就寫在連結裡）。所以這裡跑的是產品自己的程式碼，只是沒有網路。
        """
        return HttpTorrentFetcher()


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
    if scenario.demo_releases:
        _mount_demo_torrent(app, scenario.demo_releases)

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


if __name__ == "__main__":
    raise SystemExit(main())
