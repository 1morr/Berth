"""精靈只寫 Berth 擁有的物件（brief §16.4、§19「精靈審計後的八項」D1，M4 票 33）。

**接管＝只建立與管理 Berth 擁有的物件**，套件內與既有同一條；兩者只差在套件內由 Berth 讓服務
有人登得進去（Jellyfin 初始設定、qBittorrent 與 Prowlarr 的介面登入）。票 05 的事故（覆寫使用者
Prowlarr 的登入）就是這條規則沒有閘門時會出的錯。

閘門：整個精靈經 API 跑完一輪——套件內一輪、既有兩輪（那台 Jellyfin 跑過自己的精靈、還沒跑過）。
三台替身上每一個會改服務狀態的方法都被記下（`WRITES`），每一筆都要對得上 `ALLOWED` 的一列。
既有那一輪的 bootstrap 只允許「那台 Jellyfin 還沒初始化」這一個例外。

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
from fastapi.testclient import TestClient

from berth.adapters.jellyfin import JellyfinClient, JellyfinLibrary
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.adapters.prowlarr import ProwlarrClient, ProwlarrIndexer
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.adapters.qbittorrent import QbittorrentClient
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.api.deps import get_bundled_services, get_client_factory
from berth.config import Config
from berth.domain import ServiceKind, ServiceOrigin
from berth.main import create_app
from berth.services.jellyfin import API_KEY_APP
from berth.services.qbittorrent import (
    WEB_UI_PASSWORD_KEY,
    WEB_UI_USERNAME_KEY,
    apply_qbittorrent,
)
from berth.services.routes import CATEGORY_PREFIX
from tests.integration.factories import FakeClientFactory
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
            "notify_paths",
            "mark_played",
        }
    ),
    QBITTORRENT: frozenset(
        {
            "set_preferences",
            "create_category",
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


@dataclass
class Made:
    """這一次精靈裡 Berth 自己建出來、白名單放行了的物件：只有它們可以再被 Berth 動。"""

    probes: set[str] = field(default_factory=set)
    sites: set[int] = field(default_factory=set)


@dataclass(frozen=True)
class Allowed:
    """白名單的一列。`bootstrap` 那幾列只給套件內；既有只有那台 Jellyfin 還沒初始化時例外。"""

    service: ServiceKind
    method: str
    holds: Callable[[Write, Premise, Made], bool]
    bootstrap: bool = False
    origins: frozenset[ServiceOrigin] = frozenset(ServiceOrigin)


def under(path: str, root: str) -> bool:
    """容器路徑一律以 `/` 相接（`services.routes`），Windows 上的 `tmp_path` 也是這樣接上去的。"""
    return path.startswith(root.rstrip("/\\") + "/")


def _always(write: Write, premise: Premise, made: Made) -> bool:
    return True


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
    # 探測 torrent：加、校驗、移除（不刪檔）。後兩者只對 Berth 加了、放行了的那幾個。
    Allowed(
        QBITTORRENT, "add_probe",
        lambda w, p, _: under(str(w.kwargs["save_path"]), p.complete_root),
    ),
    Allowed(QBITTORRENT, "recheck", lambda w, _, made: w.args[0] in made.probes),
    Allowed(
        QBITTORRENT, "delete_torrent",
        lambda w, _, made: w.args[0] in made.probes and w.kwargs["delete_files"] is False,
    ),
    # 使用者勾選、確認加入的站；套件內移除的只能是 Berth 加的。
    Allowed(PROWLARR, "add_indexer", lambda w, p, _: str(w.args[0].definition_name) in p.ticked),
    Allowed(
        PROWLARR, "delete_indexer", lambda w, _, made: w.args[0] in made.sites,
        origins=frozenset({ServiceOrigin.BUNDLED}),
    ),
    # 套件內清單上的媒體庫是 Berth 的；既有那一台只加 Berth 路徑，不建媒體庫（brief §16.4）。
    Allowed(
        JELLYFIN, "create_library", lambda w, p, _: under(str(w.args[0].path), p.library_root),
        origins=frozenset({ServiceOrigin.BUNDLED}),
    ),
    # --- bootstrap：讓那台服務有人登得進去 ---
    # Jellyfin 初始設定。
    *(
        Allowed(JELLYFIN, method, _always, bootstrap=True)
        for method in (
            "start_configuration",
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
    的帳密、替第一個媒體庫加 Berth 路徑當寫入目標、貼 Prowlarr 的 key 並加兩站。"""
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
    # 「建立並檢查」先加 Berth 路徑、再建 Route（`SetupPage` 同一個順序）。
    ok(client.post("/api/setup/jellyfin/libraries/paths", json={"libraries": [first["name"]]}))
    ok(client.post("/api/setup/routes", json={"selections": [selection]}))
    ok(_choose(client, "prowlarr", base_url=addresses[PROWLARR], api_key=THEIR_PROWLARR_KEY))
    ok(client.post("/api/setup/indexers/test", json={"indexers": list(TICKED)}))
    ok(client.post("/api/setup/indexers/apply", json={"indexers": list(TICKED)}))
    walk_tmdb_and_complete(client)


def walk_tmdb_and_complete(client: TestClient) -> None:
    ok(client.post("/api/setup/tmdb/test", json={"api_key": "the-users-key"}))
    assert ok(client.post("/api/setup/complete"))["completed"] is True


def methods(writes: list[Write]) -> set[tuple[ServiceKind, str]]:
    return {(write.service, write.method) for write in writes}


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


@pytest.mark.parametrize("initialized", [True, False], ids=["initialized", "fresh-jellyfin"])
def test_an_existing_wizard_writes_only_owned_objects(
    wizard: Callable[[ServiceOrigin, Services], Wizard], tmp_path: Path, initialized: bool
) -> None:
    run = wizard(
        ServiceOrigin.EXISTING, existing_services(tmp_path / "nas", initialized=initialized)
    )

    walk_existing(run.client)

    assert violations(run.recorder.writes, run.premise) == []
    assert {
        (JELLYFIN, "create_api_key"),
        (JELLYFIN, "add_library_path"),
        (QBITTORRENT, "create_category"),
        (QBITTORRENT, "add_probe"),
        (PROWLARR, "add_indexer"),
    } <= methods(run.recorder.writes)
    # 例外只有一個：還沒初始化的那台 Jellyfin 由擁有者跑完它的初始設定。
    assert ((JELLYFIN, "complete_startup") in methods(run.recorder.writes)) is not initialized


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


def test_the_fresh_jellyfin_exception_does_not_reach_the_other_logins() -> None:
    """違規要紅：既有 Jellyfin 還沒初始化，也不讓 Berth 設既有 Prowlarr 的登入（票 05 的事故）。"""
    before = {"authenticationMethod": "forms", "username": "theirs", "password": ""}
    write = Write(
        PROWLARR, "set_host_config", ({**before, "username": "skipper"},), {}, before=before
    )
    fresh = replace(EXISTING_INITIALIZED, jellyfin_fresh=True)

    assert violations([write], fresh) != []
    assert violations([write], replace(fresh, origin=ServiceOrigin.BUNDLED)) == []


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
