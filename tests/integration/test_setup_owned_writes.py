"""精靈與執行期只寫 Berth 擁有的物件（brief §16.4、§19「精靈審計後的八項」D1，M4 票 33、66）。

**接管＝只建立與管理 Berth 擁有的物件**，套件內與既有同一條；兩者只差在套件內由 Berth 讓服務
有人登得進去（Jellyfin 初始設定、qBittorrent 與 Prowlarr 的介面登入）。票 05 的事故（覆寫使用者
Prowlarr 的登入）就是這條規則沒有閘門時會出的錯。

閘門：整個精靈經 API 跑完一輪——套件內一輪、既有兩輪（那台 Jellyfin 跑過自己的精靈、還沒跑過）。
三台替身上每一個會改服務狀態的方法都被記下（`WRITES`），每一筆都要對得上 `ALLOWED` 的一列。
既有那一輪的 bootstrap 只允許「那台 Jellyfin 還沒初始化」這一個例外。

執行期另一輪（M4 票 66，審計 R1 §1.9 G1）：精靈之後的送單、壞掉按「重新校驗」、下載完成、入庫、
反查（全庫掃描與只刷新媒體庫兩條）、六次用完那一件按「重新掃描媒體庫」、刪 Job，經 services 跑一遍，
同一張白名單。標已看（`mark_played`）不在這一輪：那是使用者自己按的、寫的是他自己的觀看紀錄。

為什麼不沿用前端 `web/e2e/existing.spec.ts` 的寫入清單：它記的是瀏覽器對 Berth 的 `/api/setup/*`，
看不到 Berth 對服務送了什麼。
"""

from __future__ import annotations

import typing
from collections.abc import Awaitable, Callable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Protocol

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import qbittorrent as qbittorrent_adapter
from berth.adapters.jellyfin import JellyfinClient, JellyfinItem, JellyfinLibrary, NewLibrary
from berth.adapters.jellyfin.fake import LIBRARY_SCAN_TASK, FakeJellyfinClient
from berth.adapters.prowlarr import ProwlarrClient, ProwlarrIndexer
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.adapters.qbittorrent import (
    BERTH_TAG,
    QbittorrentClient,
    QbittorrentVersion,
    TorrentAdd,
    TorrentFile,
)
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.adapters.torrent import info_hash_of, magnet_info_hash
from berth.api.deps import get_bundled_services, get_client_factory
from berth.config import Config
from berth.domain import (
    CollectionType,
    IssueAction,
    IssueStatus,
    IssueType,
    JobState,
    ServiceKind,
    ServiceOrigin,
)
from berth.main import create_app
from berth.models import Issue, Job, LedgerEntry, Media, Route
from berth.services.deletion import DeleteScope, delete_job
from berth.services.downloads import poll_downloads
from berth.services.events import EventHub
from berth.services.hints import JobHints
from berth.services.importer import sweep_imports
from berth.services.issues import resolve_issue
from berth.services.jellyfin import API_KEY_APP, BUNDLED_SERVER_NAME
from berth.services.jobs import JobSource, add_download
from berth.services.plan import sweep_plans
from berth.services.qbittorrent import (
    WEB_UI_PASSWORD_KEY,
    WEB_UI_USERNAME_KEY,
    apply_qbittorrent,
)
from berth.services.resolve_schedule import RESOLVE_DELAYS
from berth.services.resolver import sweep_resolutions
from berth.services.routes import CATEGORY_PREFIX
from tests.integration.factories import FakeClientFactory
from tests.integration.test_downloads import status
from tests.integration.test_plan import BATCH, BATCH_FILES, HASH, NOW, ready
from tests.integration.test_setup_api import BROWSER, BUNDLED, _choose, _seen, _set_paths

JELLYFIN = ServiceKind.JELLYFIN
QBITTORRENT = ServiceKind.QBITTORRENT
PROWLARR = ServiceKind.PROWLARR

#: 每個 adapter 介面上**會改那台服務狀態**的方法。`GET /Startup/User` 也在這裡：它會建出預設
#: 使用者（brief §20.7）。
WRITES: dict[ServiceKind, frozenset[str]] = {
    JELLYFIN: frozenset(
        {
            "start_configuration",
            "ensure_default_user",
            "create_startup_user",
            "set_remote_access",
            "complete_startup",
            "create_api_key",
            "create_library",
            "add_library_path",
            "run_task",
            "refresh_library",
            "notify_paths",
            "mark_played",
        }
    ),
    QBITTORRENT: frozenset(
        {
            "set_preferences",
            "create_category",
            "remove_categories",
            "add_probe",
            "recheck",
            "delete_torrent",
            "add_torrent",
            "start",
        }
    ),
    PROWLARR: frozenset({"add_indexer", "delete_indexer", "set_host_config"}),
}

#: 其餘都是讀。送 POST 而不留下東西的也算：`authenticate`、`login`、`validate_path`、
#: `test_indexer`、`test_definition`。
READS: dict[ServiceKind, frozenset[str]] = {
    JELLYFIN: frozenset(
        {
            "base_url",
            "use_token",
            "public_info",
            "metadata_defaults",
            "authenticate",
            "api_keys",
            "libraries",
            "available_type_options",
            "validate_path",
            "scheduled_tasks",
            "items",
            "user_views",
            "user_policy",
            "library_page",
            "library_filters",
            "library_index",
            "resume",
            "next_up",
            "tmdb_index",
            "item",
            "seasons",
            "episodes",
            "series_next_up",
            "image",
            "aclose",
        }
    ),
    QBITTORRENT: frozenset(
        {
            "base_url",
            "login",
            "version",
            "preferences",
            "categories",
            "torrent",
            "sync",
            "files",
            "aclose",
        }
    ),
    PROWLARR: frozenset(
        {
            "base_url",
            "ping",
            "status",
            "indexers",
            "definitions",
            "test_indexer",
            "test_definition",
            "host_config",
            "aclose",
        }
    ),
}

PROTOCOLS: dict[ServiceKind, type] = {
    JELLYFIN: JellyfinClient,
    QBITTORRENT: QbittorrentClient,
    PROWLARR: ProwlarrClient,
}

#: 介面登入會動到的 `config/host` 欄位（`services.indexer` 設登入那一段）。其餘欄位原樣送回。
PROWLARR_LOGIN_FIELDS = frozenset(
    {
        "authenticationMethod",
        "authenticationRequired",
        "username",
        "password",
        "passwordConfirmation",
    }
)


@dataclass(frozen=True)
class Write:
    """替身收到的一個寫入。`before` 只有 `set_host_config` 有：它整份送回，要比得出改了哪幾欄。

    參數、回傳值與 `before` 都是 `Any`：記的是三種介面上任一方法的呼叫，形狀各不相同。
    `raised` 是那一次丟了例外——服務收到了，寫沒寫成不知道，照樣要對白名單。
    """

    service: ServiceKind
    method: str
    args: tuple[Any, ...]
    kwargs: Mapping[str, Any]
    result: Any = None
    before: Mapping[str, Any] = field(default_factory=dict)
    raised: bool = False


@dataclass(frozen=True)
class Premise:
    """走一次精靈的前提：三個服務選了什麼、那台 Jellyfin 跑過自己的精靈沒、使用者勾了哪幾站。"""

    origin: ServiceOrigin
    jellyfin_fresh: bool
    library_root: str
    complete_root: str
    incomplete_root: str
    ticked: frozenset[str]
    #: 三層路徑的共同父目錄（compose 裡的 `/data`）：頁 2 的探針放在這裡（M4 票 46）。
    shared_root: str = ""
    #: 既有 Jellyfin 頁 3 勾了要新建的媒體庫名（M4 票 64）。
    new_libraries: frozenset[str] = frozenset()
    #: 執行期那一輪：Route 所在的媒體庫（只刷新它）與 Jellyfin「掃描媒體庫」排程任務的 id
    #: （M4 票 66）。精靈那幾輪是空的：精靈不掃描。
    route_libraries: frozenset[str] = frozenset()
    scan_task: str = ""


@dataclass
class Made:
    """這一次精靈裡 Berth 自己建出來、白名單放行了的物件：只有它們可以再被 Berth 動。"""

    probes: set[str] = field(default_factory=set)
    sites: set[int] = field(default_factory=set)
    #: Berth 送出去的 torrent 的 hash（M4 票 66）。
    torrents: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class Allowed:
    """白名單的一列。`bootstrap` 那幾列只給套件內；既有只有那台 Jellyfin 還沒初始化時例外。"""

    service: ServiceKind
    method: str
    holds: Callable[[Write, Premise, Made], bool]
    bootstrap: bool = False
    origins: frozenset[ServiceOrigin] = frozenset(ServiceOrigin)


def under(path: str, root: str) -> bool:
    """容器路徑一律以 `/` 相接（`services.routes`）；Windows 上的 `tmp_path` 本身是反斜線分隔的，
    Route 的寫入目標從它開始，所以兩種都算。"""
    base = root.rstrip("/\\")
    return path.startswith(base) and path[len(base) : len(base) + 1] in ("/", "\\")


def same_path(path: str, root: str) -> bool:
    """同一條路徑：結尾斜線不算差別（同 `under`）。"""
    return bool(root) and path.rstrip("/\\") == root.rstrip("/\\")


def _always(write: Write, premise: Premise, made: Made) -> bool:
    return True


def _named_only_when_fresh_and_bundled(write: Write, premise: Premise, made: Made) -> bool:
    """伺服器名稱是全域設定：只有 Berth 替還沒初始化的套件內那一台跑初始精靈時給它名字
    （M4 票 52）。"""
    name = write.kwargs.get("server_name")
    return name is None or (
        premise.origin is ServiceOrigin.BUNDLED
        and premise.jellyfin_fresh
        and name == BUNDLED_SERVER_NAME
    )


def _berths_torrent(write: Write, premise: Premise, made: Made) -> bool:
    """送單：`berth-*` 分類，表單上的 tag 只有 `berth`、路徑交給分類（`autoTMM`、不帶 `savepath`）。

    看的是真的會送出去的表單（`add_form`）：替身收的是 `TorrentAdd`，tag 不在它上面（R1 §1.9 G2）。
    """
    request: TorrentAdd = write.args[0]
    # 版本只決定暫停參數叫 `paused` 還是 `stopped`，與這幾個條件無關；取部署釘的 5.x 那一條。
    form = qbittorrent_adapter.add_form(request, QbittorrentVersion(app="v5.1.4", webapi="2.11.4"))
    return (
        request.category.startswith(CATEGORY_PREFIX)
        and form["tags"] == BERTH_TAG
        and form["autoTMM"] == "true"
        and "savepath" not in form
    )


def _sent_hash(request: TorrentAdd) -> str:
    return magnet_info_hash(request.magnet) if request.magnet else info_hash_of(request.content)


def _login_fields_only(write: Write, premise: Premise, made: Made) -> bool:
    values: Mapping[str, Any] = write.args[0]
    changed = {key for key, value in values.items() if write.before.get(key) != value}
    return changed <= PROWLARR_LOGIN_FIELDS


#: 白名單。`# fmt: skip`：讓一列維持「服務、方法、條件」擠在一起讀，ruff 會拆成一個參數一行。
ALLOWED: tuple[Allowed, ...] = (
    # --- Berth 擁有的物件：兩種來源都一樣 ---
    # Jellyfin 的 API key「Berth」。
    Allowed(JELLYFIN, "create_api_key", lambda w, p, _: w.args == (API_KEY_APP,)),
    # 媒體庫上的 Berth 路徑。
    Allowed(JELLYFIN, "add_library_path", lambda w, p, _: under(str(w.args[1]), p.library_root)),
    # `berth-*` 分類與它在 Berth 根目錄底下的兩個目錄。
    Allowed(
        QBITTORRENT, "create_category",
        lambda w, p, _: str(w.args[0]).startswith(CATEGORY_PREFIX)
        and under(str(w.args[1]), p.complete_root)
        and under(str(w.kwargs["download_path"]), p.incomplete_root),
    ),
    # 換台時一鍵移除的只有 `berth-*`（M4 票 47；空不空由命令重數，這裡只守名字）。
    Allowed(
        QBITTORRENT, "remove_categories",
        lambda w, p, _: all(str(name).startswith(CATEGORY_PREFIX) for name in w.args[0]),
    ),
    # 探測 torrent：加、校驗、移除（不刪檔）。後兩者只對 Berth 加了、放行了的那幾個——探測的與送單的
    # 都算（M4 票 66）。頁 3 的在分類路徑底下；頁 2 的在共用根目錄本身，而且校驗不完（M4 票 46）。
    Allowed(
        QBITTORRENT, "add_probe",
        lambda w, p, _: under(str(w.kwargs["save_path"]), p.complete_root)
        or (same_path(str(w.kwargs["save_path"]), p.shared_root) and w.kwargs["unfinished"]),
    ),
    Allowed(QBITTORRENT, "recheck", lambda w, _, made: w.args[0] in made.probes | made.torrents),
    Allowed(
        QBITTORRENT, "delete_torrent",
        lambda w, _, made: w.args[0] in made.probes | made.torrents
        and w.kwargs["delete_files"] is False,
    ),
    # --- 執行期（M4 票 66）---
    # 送單，以及 Issue「重新校驗」「重試」讓 Berth 自己的那一個重新開始。
    Allowed(QBITTORRENT, "add_torrent", _berths_torrent),
    Allowed(QBITTORRENT, "start", lambda w, _, made: w.args[0] in made.torrents),
    # 請 Jellyfin 去看 Berth 寫的路徑：通知、只刷新 Route 的媒體庫、整台的「掃描媒體庫」排程任務。
    Allowed(
        JELLYFIN, "notify_paths",
        lambda w, p, _: all(under(str(path), p.library_root) for path in w.args[0]),
    ),
    Allowed(JELLYFIN, "refresh_library", lambda w, p, _: w.args[0] in p.route_libraries),
    Allowed(JELLYFIN, "run_task", lambda w, p, _: bool(p.scan_task) and w.args[0] == p.scan_task),
    # 使用者勾選、確認加入的站；套件內移除的只能是 Berth 加的。
    Allowed(PROWLARR, "add_indexer", lambda w, p, _: str(w.args[0].definition_name) in p.ticked),
    Allowed(
        PROWLARR, "delete_indexer", lambda w, _, made: w.args[0] in made.sites,
        origins=frozenset({ServiceOrigin.BUNDLED}),
    ),
    # 套件內清單上的媒體庫是 Berth 的。
    Allowed(
        JELLYFIN, "create_library", lambda w, p, _: under(str(w.args[0].path), p.library_root),
        origins=frozenset({ServiceOrigin.BUNDLED}),
    ),
    # 既有那一台只建使用者在頁 3 勾了的新媒體庫，而且在 library root 底下（M4 票 64）。
    Allowed(
        JELLYFIN, "create_library",
        lambda w, p, _: w.args[0].name in p.new_libraries
        and under(str(w.args[0].path), p.library_root),
        origins=frozenset({ServiceOrigin.EXISTING}),
    ),
    # --- bootstrap：讓那台服務有人登得進去 ---
    # Jellyfin 初始設定。
    Allowed(JELLYFIN, "start_configuration", _named_only_when_fresh_and_bundled, bootstrap=True),
    *(
        Allowed(JELLYFIN, method, _always, bootstrap=True)
        for method in (
            "ensure_default_user",
            "create_startup_user",
            "set_remote_access",
            "complete_startup",
        )
    ),
    # qBittorrent 的 WebUI 登入。
    Allowed(
        QBITTORRENT, "set_preferences",
        lambda w, _p, _m: set(w.args[0]) <= {WEB_UI_USERNAME_KEY, WEB_UI_PASSWORD_KEY},
        bootstrap=True,
    ),
    # Prowlarr 的介面登入。
    Allowed(PROWLARR, "set_host_config", _login_fields_only, bootstrap=True),
)  # fmt: skip


def violations(writes: list[Write], premise: Premise) -> list[str]:
    """對不上白名單的那幾筆，照收到的順序。放行了而且成功的探測 torrent 與站才記進 `Made`。"""
    made = Made()
    refused = []
    for write in writes:
        rows = [
            row
            for row in ALLOWED
            if (row.service, row.method) == (write.service, write.method)
            and premise.origin in row.origins
            and _bootstrap_allowed(row, write, premise)
        ]
        if not any(row.holds(write, premise, made) for row in rows):
            refused.append(f"{write.service.value}.{write.method}{write.args}{dict(write.kwargs)}")
        elif write.method == "add_probe" and not write.raised:
            made.probes.add(str(write.result))
        elif write.method == "add_indexer" and not write.raised:
            made.sites.add(write.result.id)
        elif write.method == "add_torrent" and not write.raised:
            made.torrents.add(_sent_hash(write.args[0]))
    return refused


def _bootstrap_allowed(row: Allowed, write: Write, premise: Premise) -> bool:
    if not row.bootstrap or premise.origin is ServiceOrigin.BUNDLED:
        return True
    return write.service is JELLYFIN and premise.jellyfin_fresh


class Recorder:
    """替身上 `WRITES` 列的方法換成先記一筆再照做的版本。"""

    def __init__(self) -> None:
        self.writes: list[Write] = []

    def watch(self, service: ServiceKind, fake: object) -> None:
        for name in WRITES[service]:
            setattr(fake, name, self._recording(service, fake, name, getattr(fake, name)))

    def _recording(
        self, service: ServiceKind, fake: object, name: str, original: Callable[..., Awaitable[Any]]
    ) -> Callable[..., Awaitable[Any]]:
        async def recorded(*args: Any, **kwargs: Any) -> Any:  # `Any`：包的是三種介面的任一方法
            before: Mapping[str, Any] = {}
            if name == "set_host_config":
                before = dict(await typing.cast(FakeProwlarrClient, fake).host_config())
            try:
                result = await original(*args, **kwargs)
            except Exception:
                self.writes.append(Write(service, name, args, kwargs, None, before, raised=True))
                raise
            self.writes.append(Write(service, name, args, kwargs, result, before))
            return result

        return recorded


def unclassified(service: ServiceKind, protocol: type) -> set[str]:
    """介面上沒被歸到讀或寫的方法。新加一個方法就要決定它是哪一種，否則寫入會被當成讀放過去。"""
    members = set(typing.get_protocol_members(protocol))
    return members ^ (READS[service] | WRITES[service]) | (READS[service] & WRITES[service])


# --- 三台替身 ---

OWNER = ("owner", "s3cret")
ADDRESSES = {
    JELLYFIN: "http://nas:8096",
    QBITTORRENT: "http://nas:8080",
    PROWLARR: "http://nas:9696",
}
#: 使用者那台 Prowlarr 的 API key。
THEIR_PROWLARR_KEY = "0" * 31 + "2"
#: 使用者那台 Prowlarr 原本就有的站。
THEIR_SITE = ProwlarrIndexer(
    1, "Nyaa.si", True, "nyaasi", privacy="public", language="en-US", protocol="torrent"
)
#: 頁 4 測試並勾起來的站：使用者還沒有的兩個公開站。
TICKED = ("yts", "eztv")
#: 既有 Jellyfin 的頁 3 勾了新建的媒體庫（M4 票 64）：那台還沒有的類型。
NEW_LIBRARY = "紀錄片"


@dataclass
class Services:
    jellyfin: FakeJellyfinClient
    qbittorrent: FakeQbittorrentClient
    prowlarr: FakeProwlarrClient


def bundled_services() -> Services:
    return Services(FakeJellyfinClient(), FakeQbittorrentClient(), FakeProwlarrClient())


def existing_services(
    nas: Path,
    *,
    initialized: bool,
    names: tuple[str, str] = ("電影", "Anime"),
    owner: tuple[str, str] = OWNER,
) -> Services:
    """使用者自己的三台：兩個媒體庫、qBittorrent 有自己的全域偏好、Prowlarr 已有一站。"""
    libraries = []
    for index, name in enumerate(names):
        location = nas / f"library-{index}"
        location.mkdir(parents=True)
        libraries.append(
            JellyfinLibrary(
                name=name,
                item_id=f"nas-{index}",
                collection_type="movies" if index == 0 else "tvshows",
                locations=(str(location),),
                type_options=(),
            )
        )
    return Services(
        FakeJellyfinClient(
            base_url=ADDRESSES[JELLYFIN],
            startup_wizard_completed=initialized,
            admin=owner if initialized else None,
            libraries=tuple(libraries),
        ),
        FakeQbittorrentClient(
            base_url=ADDRESSES[QBITTORRENT],
            preferences={"save_path": "/downloads", "auto_tmm_enabled": False},
        ),
        FakeProwlarrClient(
            base_url=ADDRESSES[PROWLARR],
            indexers=[THEIR_SITE],
            host_config={
                "id": 1,
                "authenticationMethod": "forms",
                "authenticationRequired": "enabled",
                "username": "theirs",
                "password": "",
                "passwordConfirmation": "",
                "apiKey": THEIR_PROWLARR_KEY,
            },
        ),
    )


@dataclass
class Wizard:
    client: TestClient
    recorder: Recorder
    premise: Premise


@pytest.fixture
def wizard(config: Config, tmp_path: Path) -> Iterator[Callable[[ServiceOrigin, Services], Wizard]]:
    """起一台 Berth、把三台替身接上去並開始記錄。精靈本身由各個 `walk_*` 走。"""
    running: list[TestClient] = []

    def start(origin: ServiceOrigin, services: Services) -> Wizard:
        app = create_app(replace(config, web_root=tmp_path / "never-built"))
        factory = FakeClientFactory(
            jellyfin=services.jellyfin,
            qbittorrent=services.qbittorrent,
            prowlarr=services.prowlarr,
        )
        recorder = Recorder()
        recorder.watch(JELLYFIN, services.jellyfin)
        recorder.watch(QBITTORRENT, services.qbittorrent)
        recorder.watch(PROWLARR, services.prowlarr)
        app.dependency_overrides[get_bundled_services] = lambda: BUNDLED
        app.dependency_overrides[get_client_factory] = lambda: factory
        client = TestClient(app, headers=BROWSER)
        client.__enter__()
        running.append(client)
        data = tmp_path / "data"
        # 正式環境的 `/data` 是 compose 掛進來的，一開始就在：頁 2 的探針放在它底下（M4 票 46）。
        data.mkdir(exist_ok=True)
        _set_paths(client, data)
        return Wizard(
            client,
            recorder,
            Premise(
                origin=origin,
                jellyfin_fresh=not services.jellyfin.startup_wizard_completed,
                library_root=str(data / "library"),
                complete_root=str(data / "torrent" / "complete"),
                incomplete_root=str(data / "torrent" / "incomplete"),
                ticked=frozenset(TICKED),
                shared_root=str(data),
                new_libraries=frozenset({NEW_LIBRARY}),
            ),
        )

    yield start
    for client in running:
        client.__exit__(None, None, None)


def ok(response: Any) -> Any:  # `Any`：httpx 的 Response 與它的 JSON
    assert response.status_code < 300, response.text
    return response.json() if response.content else None


def walk_bundled(client: TestClient) -> None:
    """頁 1–6 全選套件內：建管理員、兩個介面登入、清單上的媒體庫、加兩站再移除一站。"""
    ok(_choose(client, "jellyfin"))
    ok(
        client.post(
            "/api/setup/owner", json={**_seen(client), "username": "skipper", "password": "harbour"}
        )
    )
    ok(client.post("/api/setup/jellyfin/bootstrap"))
    ok(_choose(client, "qbittorrent"))
    ok(
        client.post(
            "/api/setup/qbittorrent/apply",
            json={"login": {"reuse_owner": True, "password": "harbour"}},
        )
    )
    ok(client.post("/api/setup/routes/libraries"))
    ok(client.post("/api/setup/routes", json={}))
    ok(_choose(client, "prowlarr"))
    ok(client.post("/api/setup/indexers/test", json={"indexers": list(TICKED)}))
    added = ok(client.post("/api/setup/indexers/apply", json={"indexers": list(TICKED)}))
    ok(client.delete(f"/api/setup/indexers/{added['sites'][0]['indexer_id']}"))
    ok(client.put("/api/setup/indexers/login", json={"reuse_owner": True, "password": "harbour"}))
    walk_tmdb_and_complete(client)
    # 擁有者那一組之外再設一組，確定第二次寫登入也照樣只動登入那幾欄。
    ok(
        client.put(
            "/api/setup/indexers/login", json={"username": "deckhand", "password": "rope-and-knots"}
        )
    )


def walk_existing(
    client: TestClient,
    owner: tuple[str, str] = OWNER,
    addresses: Mapping[ServiceKind, str] = ADDRESSES,
) -> None:
    """頁 1–6 全選既有：以那台 Jellyfin 的管理員成為擁有者（沒初始化就由擁有者建）、填 qBittorrent
    的帳密、新建一個媒體庫、替第一個媒體庫加 Berth 路徑當寫入目標、貼 Prowlarr 的 key 並加兩站。"""
    ok(_choose(client, "jellyfin", base_url=addresses[JELLYFIN]))
    user, password = owner
    ok(
        client.post(
            "/api/setup/owner", json={**_seen(client), "username": user, "password": password}
        )
    )
    ok(
        _choose(
            client,
            "qbittorrent",
            base_url=addresses[QBITTORRENT],
            username="admin",
            password="adminadmin",
        )
    )
    ok(client.post("/api/setup/qbittorrent/apply"))
    page = ok(client.post("/api/setup/routes/libraries"))
    first = page["libraries"][0]
    selection = {"library": first["name"], "target_path": first["berth_path"]}
    # 「建立並檢查」先建勾了的新媒體庫、再加 Berth 路徑、再建 Route（`SetupPage` 同一個順序）。
    made = ok(
        client.post(
            "/api/setup/jellyfin/libraries",
            json={"libraries": [{"name": NEW_LIBRARY, "collection_type": "tvshows"}]},
        )
    )
    built = {"library": NEW_LIBRARY, "target_path": f"{made['library_root']}/{NEW_LIBRARY}"}
    ok(client.post("/api/setup/jellyfin/libraries/paths", json={"libraries": [first["name"]]}))
    ok(client.post("/api/setup/routes", json={"selections": [selection, built]}))
    ok(_choose(client, "prowlarr", base_url=addresses[PROWLARR], api_key=THEIR_PROWLARR_KEY))
    ok(client.post("/api/setup/indexers/test", json={"indexers": list(TICKED)}))
    ok(client.post("/api/setup/indexers/apply", json={"indexers": list(TICKED)}))
    walk_tmdb_and_complete(client)


def walk_tmdb_and_complete(client: TestClient) -> None:
    ok(client.post("/api/setup/tmdb/test", json={"api_key": "the-users-key"}))
    ok(client.post("/api/setup/complete"))
    assert client.get("/api/health").json()["setup_completed"] is True


def methods(writes: list[Write]) -> set[tuple[ServiceKind, str]]:
    return {(write.service, write.method) for write in writes}


def probed_shared_root(run: Wizard) -> bool:
    """頁 2 的探針真的跑了（M4 票 46）：放在共用根目錄的那一個。"""
    return any(
        write.method == "add_probe" and write.kwargs["save_path"] == run.premise.shared_root
        for write in run.recorder.writes
    )


def asked_jellyfin_about_shared_root(run: Wizard, jellyfin: FakeJellyfinClient) -> bool:
    """頁 1 真的問了既有 Jellyfin 看不看得到共用根目錄（M4 票 63）。`validate_path` 是讀
    （`READS`）：探測檔是 Berth 在自己的 `/data` 寫的，Jellyfin 那一台什麼都沒多，所以白名單不必
    放行任何東西。"""
    shared = Path(run.premise.shared_root)
    return any(Path(path).parent == shared for path in jellyfin.paths_validated)


# --- 執行期那一輪（M4 票 66）---

#: Issue 的按鈕由誰按：事件上記的 actor。
ACTOR = "7"


@dataclass
class Runtime:
    services: Services
    recorder: Recorder
    premise: Premise
    route: Route
    media: Media
    roots: dict[str, Path]


@pytest_asyncio.fixture
async def runtime(session: AsyncSession, roots: dict[str, Path]) -> Runtime:
    """精靈跑完、有一部作品與一條 anime Route（`test_plan.ready`），三台替身開始記錄。"""
    media, route, factory = await ready(session, roots)
    services = Services(factory.jellyfin_, factory.qbittorrent_, factory.prowlarr_)
    services.jellyfin.tasks_ = [LIBRARY_SCAN_TASK]
    recorder = Recorder()
    recorder.watch(JELLYFIN, services.jellyfin)
    recorder.watch(QBITTORRENT, services.qbittorrent)
    recorder.watch(PROWLARR, services.prowlarr)
    premise = Premise(
        origin=ServiceOrigin.BUNDLED,
        jellyfin_fresh=False,
        library_root=str(roots["library"]),
        complete_root=str(roots["complete"]),
        incomplete_root=str(roots["incomplete"]),
        ticked=frozenset(),
        shared_root=str(roots["library"].parent),
        route_libraries=frozenset({route.jellyfin_library_id}),
        scan_task=LIBRARY_SCAN_TASK.id,
    )
    return Runtime(services, recorder, premise, route, media, roots)


async def walk_runtime(session: AsyncSession, run: Runtime) -> None:
    """送單 → 下載到一半說缺檔、按「重新校驗」→ 下載完成 → 規劃、入庫 → 反查 → 六次用完那一件按
    「重新掃描媒體庫」→ 刪 Job，移除 torrent（不刪檔）。

    反查兩條都走到：第一次沒找到時 Berth 的路徑還沒列出過任何東西（全庫掃描），之後媒體庫裡有了
    別的作品（只刷新那個媒體庫）。
    """
    qbittorrent, jellyfin = run.services.qbittorrent, run.services.jellyfin
    factory = FakeClientFactory(jellyfin=jellyfin, qbittorrent=qbittorrent)
    hub = EventHub()
    route = run.route
    save_path = run.roots["complete"] / route.slug

    await add_download(
        session,
        factory,
        source=JobSource(url=f"magnet:?xt=urn:btih:{HASH}&dn=batch", title=BATCH),
        media_id=run.media.id,
        route_id=route.id,
        user_id=None,
    )
    files = tuple(
        TorrentFile(index=index, name=name, size=size, priority=1, progress=0.4)
        for index, (name, size) in enumerate(BATCH_FILES)
    )
    qbittorrent.files_by_hash[HASH] = files

    def reports(state: str, progress: float) -> None:
        qbittorrent.torrents = (
            status(
                state=state,
                progress=progress,
                category=route.category,
                save_path=str(save_path),
                completion_on=int(NOW.timestamp()) if progress == 1.0 else 0,
            ),
        )

    reports("downloading", 0.4)
    await poll_downloads(session, qbittorrent, hub, JobHints(), now=NOW)
    reports("missingFiles", 0.4)
    await poll_downloads(session, qbittorrent, hub, JobHints(), now=NOW)
    await press(session, factory, IssueType.MISSING_FILES, IssueAction.RECHECK)

    for name, _size in BATCH_FILES:
        (save_path / name).parent.mkdir(parents=True, exist_ok=True)
        (save_path / name).write_bytes(name.encode())
    qbittorrent.files_by_hash[HASH] = tuple(replace(row, progress=1.0) for row in files)
    reports("stalledUP", 1.0)
    await poll_downloads(session, qbittorrent, hub, JobHints(), now=NOW)
    await sweep_plans(session, factory, hub, now=NOW)
    await sweep_imports(session, factory, hub, now=NOW)

    await sweep_resolutions(session, factory, now=NOW + RESOLVE_DELAYS[0])
    jellyfin.items_ = [
        JellyfinItem(
            id="other-series",
            type="Series",
            name="Other",
            path=f"{route.target_path}/Other (2020)",
            tmdb_id="1",
        )
    ]
    while (due := await session.scalar(select(func.min(LedgerEntry.resolve_after)))) is not None:
        await sweep_resolutions(session, factory, now=due)
    await press(session, factory, IssueType.JELLYFIN_ITEM_UNRESOLVED, IssueAction.RESCAN)

    await delete_job(session, factory, HASH, DeleteScope(remove_torrent=True), actor=ACTOR)


async def press(
    session: AsyncSession, factory: FakeClientFactory, kind: IssueType, action: IssueAction
) -> None:
    """按下那一種 Issue 的第一件（反查用完的每一列各一件，按一件就夠）。"""
    issue = await session.scalar(
        select(Issue).where(Issue.type == kind, Issue.status == IssueStatus.OPEN).order_by(Issue.id)
    )
    assert issue is not None, kind
    await resolve_issue(session, factory, issue.id, action, actor=ACTOR)


# --- 閘門 ---


def test_a_bundled_wizard_writes_only_owned_objects_and_the_bootstrap(
    wizard: Callable[[ServiceOrigin, Services], Wizard],
) -> None:
    run = wizard(ServiceOrigin.BUNDLED, bundled_services())

    walk_bundled(run.client)

    assert violations(run.recorder.writes, run.premise) == []
    # 不是空轉：每一種擁有的物件與 bootstrap 都真的寫了。
    assert {
        (JELLYFIN, "complete_startup"),
        (JELLYFIN, "create_api_key"),
        (JELLYFIN, "create_library"),
        (QBITTORRENT, "set_preferences"),
        (QBITTORRENT, "create_category"),
        (QBITTORRENT, "add_probe"),
        (PROWLARR, "add_indexer"),
        (PROWLARR, "delete_indexer"),
        (PROWLARR, "set_host_config"),
    } <= methods(run.recorder.writes)
    assert probed_shared_root(run)
    assert any(
        write.method == "start_configuration"
        and write.kwargs.get("server_name") == BUNDLED_SERVER_NAME
        for write in run.recorder.writes
    )


@pytest.mark.parametrize("initialized", [True, False], ids=["initialized", "fresh-jellyfin"])
def test_an_existing_wizard_writes_only_owned_objects(
    wizard: Callable[[ServiceOrigin, Services], Wizard], tmp_path: Path, initialized: bool
) -> None:
    services = existing_services(tmp_path / "nas", initialized=initialized)
    run = wizard(ServiceOrigin.EXISTING, services)

    walk_existing(run.client)

    assert violations(run.recorder.writes, run.premise) == []
    assert {
        (JELLYFIN, "create_api_key"),
        (JELLYFIN, "add_library_path"),
        (JELLYFIN, "create_library"),
        (QBITTORRENT, "create_category"),
        (QBITTORRENT, "add_probe"),
        (PROWLARR, "add_indexer"),
    } <= methods(run.recorder.writes)
    assert probed_shared_root(run)
    assert asked_jellyfin_about_shared_root(run, services.jellyfin)
    # 例外只有一個：還沒初始化的那台 Jellyfin 由擁有者跑完它的初始設定。
    assert ((JELLYFIN, "complete_startup") in methods(run.recorder.writes)) is not initialized


@pytest.mark.asyncio
async def test_the_runtime_writes_only_owned_objects(
    session: AsyncSession, runtime: Runtime
) -> None:
    await walk_runtime(session, runtime)

    assert violations(runtime.recorder.writes, runtime.premise) == []
    # 不是空轉：執行期的每一種寫入都真的送了。
    assert {
        (QBITTORRENT, "create_category"),
        (QBITTORRENT, "add_torrent"),
        (QBITTORRENT, "start"),
        (QBITTORRENT, "recheck"),
        (QBITTORRENT, "delete_torrent"),
        (JELLYFIN, "notify_paths"),
        (JELLYFIN, "run_task"),
        (JELLYFIN, "refresh_library"),
    } <= methods(runtime.recorder.writes)
    job = await session.get(Job, HASH)
    assert job is not None and job.state is JobState.REMOVED


# --- 閘門自己的變異驗證 ---


def test_an_extra_global_preference_on_the_existing_round_is_refused(
    wizard: Callable[[ServiceOrigin, Services], Wizard],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """違規要紅：既有那一輪，頁 2 的套用順手改了 qBittorrent 的全域預設儲存路徑。"""
    run = wizard(ServiceOrigin.EXISTING, existing_services(tmp_path / "nas", initialized=True))

    async def also_moves_their_downloads(session: Any, factory: Any, **kwargs: Any) -> Any:
        await factory.qbittorrent(ADDRESSES[QBITTORRENT]).set_preferences({"save_path": "/data"})
        return await apply_qbittorrent(session, factory, **kwargs)

    monkeypatch.setattr("berth.api.setup.apply_qbittorrent", also_moves_their_downloads)

    walk_existing(run.client)

    assert violations(run.recorder.writes, run.premise) == [
        "qbittorrent.set_preferences({'save_path': '/data'},){}"
    ]


#: 既有、那台 Jellyfin 已經初始化：直接拿單筆寫入對白名單的變異測試用。
EXISTING_INITIALIZED = Premise(
    ServiceOrigin.EXISTING, False, "/data/library", "/c", "/i", frozenset()
)


def test_the_bootstrap_on_an_initialized_existing_jellyfin_is_refused() -> None:
    """違規要紅：已經初始化的既有 Jellyfin 收到初始設定。同一筆在還沒初始化的那台與套件內放行。"""
    write = Write(JELLYFIN, "set_remote_access", (), {"enabled": True})

    assert violations([write], EXISTING_INITIALIZED) != []
    assert violations([write], replace(EXISTING_INITIALIZED, jellyfin_fresh=True)) == []
    assert violations([write], replace(EXISTING_INITIALIZED, origin=ServiceOrigin.BUNDLED)) == []


def test_naming_a_jellyfin_other_than_a_fresh_bundled_one_is_refused() -> None:
    """違規要紅：既有 Jellyfin 還沒初始化時初始設定放行，但不替它取名；套件內但已經初始化過的
    也不取名（M4 票 52）。還沒初始化的套件內那一台放行，換一組語言照樣放行。"""
    fresh = replace(EXISTING_INITIALIZED, jellyfin_fresh=True)

    def configure(name: str | None, *, culture: str = "zh-TW") -> Write:
        values = {"ui_culture": culture, "metadata_country_code": "TW", "server_name": name}
        return Write(JELLYFIN, "start_configuration", (), values)

    named = configure(BUNDLED_SERVER_NAME)
    assert violations([named], fresh) != []
    assert violations([configure(None)], fresh) == []
    bundled = replace(fresh, origin=ServiceOrigin.BUNDLED)
    assert violations([named], replace(bundled, jellyfin_fresh=False)) != []
    assert violations([configure("their-nas")], bundled) != []
    assert violations([named], bundled) == []
    assert violations([configure(BUNDLED_SERVER_NAME, culture="en-US")], bundled) == []


def test_the_fresh_jellyfin_exception_does_not_reach_the_other_logins() -> None:
    """違規要紅：既有 Jellyfin 還沒初始化，也不讓 Berth 設既有 Prowlarr 的登入（票 05 的事故）。"""
    before = {"authenticationMethod": "forms", "username": "theirs", "password": ""}
    write = Write(
        PROWLARR, "set_host_config", ({**before, "username": "skipper"},), {}, before=before
    )
    fresh = replace(EXISTING_INITIALIZED, jellyfin_fresh=True)

    assert violations([write], fresh) != []
    assert violations([write], replace(fresh, origin=ServiceOrigin.BUNDLED)) == []


def test_a_probe_on_the_shared_root_has_to_be_one_that_never_finishes() -> None:
    """違規要紅：頁 2 的探針放在共用根目錄本身，校驗得完的那一種會觸發使用者的「完成時執行外部程式」
    （M4 票 46）；放在共用根目錄底下別處（不是分類路徑）也不行。校驗不完的那一種放行。"""
    premise = replace(EXISTING_INITIALIZED, shared_root="/data")

    def probe(save_path: str, *, unfinished: bool) -> Write:
        return Write(
            QBITTORRENT,
            "add_probe",
            (".berth-probe-1", b"berth"),
            {"save_path": save_path, "unfinished": unfinished},
        )

    assert violations([probe("/data", unfinished=False)], premise) != []
    assert violations([probe("/data/elsewhere", unfinished=True)], premise) != []
    assert violations([probe("/data", unfinished=True)], premise) == []
    # 無關的寫法不紅：結尾多一個斜線還是同一條。
    assert violations([probe("/data/", unfinished=True)], premise) == []


def test_a_library_on_an_existing_jellyfin_has_to_be_ticked_and_under_the_root() -> None:
    """違規要紅：既有 Jellyfin 上沒勾也建、勾了但建在 library root 外（M4 票 64）。

    勾了、在 root 底下的放行；root 多一個結尾斜線、換一個勾了的名字都不紅。
    """

    def create(name: str, path: str) -> Write:
        library = NewLibrary(name, CollectionType.MOVIES, path, (), "zh", "TW")
        return Write(JELLYFIN, "create_library", (library,), {})

    ticked = replace(EXISTING_INITIALIZED, new_libraries=frozenset({"電影"}))

    assert violations([create("電影", "/data/library/電影")], EXISTING_INITIALIZED) != []
    assert violations([create("電影", "/volume1/電影")], ticked) != []
    assert violations([create("Films", "/data/library/films")], ticked) != []
    assert violations([create("電影", "/data/library/電影")], ticked) == []
    assert (
        violations(
            [create("電影", "/data/library/電影")], replace(ticked, library_root="/data/library/")
        )
        == []
    )
    assert (
        violations(
            [create("Films", "/data/library/films")],
            replace(ticked, new_libraries=frozenset({"Films"})),
        )
        == []
    )


# --- 執行期那一輪的變異驗證（M4 票 66）---


@pytest.mark.asyncio
async def test_a_runtime_round_that_tags_torrents_otherwise_is_refused(
    session: AsyncSession, runtime: Runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    """違規要紅：送單的表單多掛一個 tag。看的是 adapter 真的會送出去的表單，不是替身收到的參數。"""
    monkeypatch.setattr("berth.adapters.qbittorrent.BERTH_TAG", "berth,keep")

    await walk_runtime(session, runtime)

    refused = violations(runtime.recorder.writes, runtime.premise)
    # 被拒的那一個不記成 Berth 送的，之後碰它的也一起紅。
    assert [line.split("(")[0] for line in refused] == [
        "qbittorrent.add_torrent",
        "qbittorrent.start",
        "qbittorrent.recheck",
        "qbittorrent.delete_torrent",
    ]


@pytest.mark.asyncio
async def test_a_runtime_round_that_deletes_the_downloaded_files_is_refused(
    session: AsyncSession, runtime: Runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    """違規要紅：刪 Job 時請 qBittorrent 連檔一起刪（brief §9.2：Berth 只移除 torrent）。"""

    # `Any`：換掉的是 services 的私有函式，factory 是測試的替身工廠。
    async def deletes_the_files_too(session: AsyncSession, factory: Any, job: Job) -> None:
        await factory.qbittorrent("").delete_torrent(job.hash, delete_files=True)

    monkeypatch.setattr("berth.services.deletion._remove_torrent", deletes_the_files_too)

    await walk_runtime(session, runtime)

    assert violations(runtime.recorder.writes, runtime.premise) == [
        f"qbittorrent.delete_torrent('{HASH}',){{'delete_files': True}}"
    ]


#: 執行期：Route 在媒體庫 `item-2`，掃描任務是 Jellyfin 內建那一個。
RUNTIME = replace(
    EXISTING_INITIALIZED, route_libraries=frozenset({"item-2"}), scan_task=LIBRARY_SCAN_TASK.id
)
MAGNET = f"magnet:?xt=urn:btih:{HASH}"


def send(category: str = "berth-anime", magnet: str = MAGNET) -> Write:
    return Write(QBITTORRENT, "add_torrent", (TorrentAdd(category=category, magnet=magnet),), {})


def test_a_torrent_outside_berths_categories_is_refused() -> None:
    """違規要紅：送單落在不是 `berth-` 的分類（使用者自己的、Sonarr 的）。換一個 `berth-*`、磁力多帶
    幾個參數都不紅。"""
    assert violations([send("tv-sonarr")], RUNTIME) != []
    assert violations([send("berth-films")], RUNTIME) == []
    assert violations([send(magnet=f"{MAGNET}&dn=batch&tr=udp%3A%2F%2Ftracker")], RUNTIME) == []


def test_a_torrent_whose_path_is_not_left_to_the_category_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """違規要紅：送單表單自己帶 `savepath`，或關掉 autoTMM——下載就不再落在 `berth-*` 分類的路徑。
    表單上無關的欄位換一個值不紅。"""
    real = qbittorrent_adapter.add_form

    def form_with(**extra: str) -> Callable[..., dict[str, str]]:
        def form(request: TorrentAdd, version: QbittorrentVersion) -> dict[str, str]:
            return {**real(request, version), **extra}

        return form

    monkeypatch.setattr(qbittorrent_adapter, "add_form", form_with(savepath="/downloads"))
    assert violations([send()], RUNTIME) != []
    monkeypatch.setattr(qbittorrent_adapter, "add_form", form_with(autoTMM="false"))
    assert violations([send()], RUNTIME) != []
    monkeypatch.setattr(qbittorrent_adapter, "add_form", form_with(contentLayout="Subfolder"))
    assert violations([send()], RUNTIME) == []


def test_touching_a_torrent_berth_did_not_send_is_refused() -> None:
    """違規要紅：重新開始、校驗、移除不是 Berth 送的 torrent；移除 Berth 的時連檔一起刪。

    Berth 送過的那一個放行；磁力裡的 hash 寫成大寫也是同一個。
    """
    theirs = "f" * 40

    def remove(info_hash: str, *, files: bool) -> Write:
        return Write(QBITTORRENT, "delete_torrent", (info_hash,), {"delete_files": files})

    for method in ("start", "recheck"):
        assert violations([send(), Write(QBITTORRENT, method, (theirs,), {})], RUNTIME) != []
        assert violations([send(), Write(QBITTORRENT, method, (HASH,), {})], RUNTIME) == []
    assert violations([send(), remove(theirs, files=False)], RUNTIME) != []
    assert violations([send(), remove(HASH, files=True)], RUNTIME) != []
    assert violations([send(), remove(HASH, files=False)], RUNTIME) == []
    upper = send(magnet=f"magnet:?xt=urn:btih:{HASH.upper()}")
    assert violations([upper, remove(HASH, files=False)], RUNTIME) == []


def test_asking_jellyfin_about_anything_but_berths_paths_is_refused() -> None:
    """違規要紅：通知 library root 以外的路徑（名字只是開頭相同的也算外面）、刷新不是 Route 的
    媒體庫、跑掃描以外的排程任務；精靈那幾輪連掃描都不放行。

    root 多一個結尾斜線、Windows 的反斜線不紅。
    """

    def notify(*paths: str) -> Write:
        return Write(JELLYFIN, "notify_paths", (list(paths),), {})

    inside = "/data/library/anime/SPY x FAMILY (2022)/Season 01/E01.mkv"
    assert violations([notify(inside, "/volume1/tv/E01.mkv")], RUNTIME) != []
    assert violations([notify("/data/library-old/E01.mkv")], RUNTIME) != []
    assert violations([notify(inside)], RUNTIME) == []
    assert violations([notify(inside)], replace(RUNTIME, library_root="/data/library/")) == []
    windows = replace(RUNTIME, library_root=r"C:\data\library")
    assert violations([notify(r"C:\data\library\anime/SPY/E01.mkv")], windows) == []

    def refresh(library_id: str) -> Write:
        return Write(JELLYFIN, "refresh_library", (library_id,), {})

    assert violations([refresh("their-library")], RUNTIME) != []
    assert violations([refresh("item-2")], RUNTIME) == []

    scan = Write(JELLYFIN, "run_task", (LIBRARY_SCAN_TASK.id,), {})
    assert violations([Write(JELLYFIN, "run_task", ("optimize-database",), {})], RUNTIME) != []
    assert violations([scan], EXISTING_INITIALIZED) != []
    assert violations([scan], RUNTIME) == []


def test_removing_a_category_that_is_not_berths_is_refused() -> None:
    """違規要紅：換台時一鍵移除夾帶一個不是 `berth-` 的分類（M4 票 47）。只有 `berth-*` 的放行，
    名字換一個、順序換一下都不紅。"""

    def remove(*names: str) -> Write:
        return Write(QBITTORRENT, "remove_categories", (list(names),), {})

    assert violations([remove("berth-shows", "movies")], EXISTING_INITIALIZED) != []
    assert violations([remove("berth-shows")], EXISTING_INITIALIZED) == []
    assert violations([remove("berth-films", "berth-anime")], EXISTING_INITIALIZED) == []


def test_unrelated_names_and_address_formatting_stay_green(
    wizard: Callable[[ServiceOrigin, Services], Wizard],
    tmp_path: Path,
) -> None:
    """無關的改動不紅：媒體庫與擁有者換名字、位址多打一個結尾斜線。白名單看的是物件是不是
    Berth 的，不是它叫什麼、使用者怎麼打位址。"""
    captain = ("captain", "harbour-master")
    services = existing_services(
        tmp_path / "nas", initialized=True, names=("Films", "Cartoons"), owner=captain
    )
    run = wizard(ServiceOrigin.EXISTING, services)

    walk_existing(run.client, captain, {kind: f"{url}/" for kind, url in ADDRESSES.items()})

    assert violations(run.recorder.writes, run.premise) == []
    assert (JELLYFIN, "add_library_path") in methods(run.recorder.writes)


class _WithAnUnclassifiedWrite(QbittorrentClient, Protocol):
    async def set_global_speed_limit(self, limit: int) -> None: ...


class _Redeclared(QbittorrentClient, Protocol):
    async def set_preferences(  # 同一個方法換個排版、補一句說明：不是新的方法。
        self,
        values: Mapping[str, Any],
    ) -> None:
        """改它的全域偏好。"""
        ...


def test_every_adapter_method_is_either_a_read_or_a_write() -> None:
    for service, protocol in PROTOCOLS.items():
        assert unclassified(service, protocol) == set(), service

    # 變異：介面多一個沒分類的方法要紅；同一個方法改排版不紅。
    assert unclassified(QBITTORRENT, _WithAnUnclassifiedWrite) == {"set_global_speed_limit"}
    assert unclassified(QBITTORRENT, _Redeclared) == set()
