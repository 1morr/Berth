"""`/api/setup/*` 的端點行為（plan §6 setup 群組、票 05 驗收）。

用 `dependency_overrides` 把三個 client 換成 Fake，所以這裡測的是 API 的形狀與門禁，
不是網路。判定規則本身在 `test_setup_service.py`。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.jellyfin import JellyfinLibrary, TypeOption
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.adapters.qbittorrent import QbittorrentVersion
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.api.deps import get_client_factory, get_setup_probes
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.main import create_app
from berth.services.clients import SetupProbes
from berth.services.indexer import DEFAULT_INDEXERS
from tests.integration.arrange import delete_once_during_checks
from tests.integration.factories import FakeClientFactory

#: 前端每個非 GET 請求都帶這個標頭（`api/client.ts`）；缺了它的行為在 `test_auth_api.py`。
BROWSER = {CSRF_HEADER: "XMLHttpRequest"}


def fake_probes(**overrides: object) -> SetupProbes:
    defaults: dict[str, object] = {
        "jellyfin": FakeJellyfinClient(),
        "qbittorrent": FakeQbittorrentClient(),
        "prowlarr": FakeProwlarrClient(),
        "prowlarr_api_key": "the-key",
    }
    defaults.update(overrides)
    return SetupProbes(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def probes() -> SetupProbes:
    return fake_probes()


@pytest.fixture
def client(config: Config, tmp_path: Path, probes: SetupProbes) -> Iterator[TestClient]:
    app = create_app(replace(config, web_root=tmp_path / "never-built"))

    async def override() -> AsyncIterator[SetupProbes]:
        yield probes

    app.dependency_overrides[get_setup_probes] = override
    with TestClient(app, headers=BROWSER) as running:
        yield running


class TestStatus:
    def test_a_clean_install_answers_anonymously_at_step_one(self, client: TestClient) -> None:
        response = client.get("/api/setup/status")

        assert response.status_code == 200
        body = response.json()
        assert body == {
            "completed": False,
            "current_step": 1,
            "admin_created": False,
            "admin_username": "",
            "interface_username": "",
            "jellyfin_owns_account": False,
            "apply_to_services": True,
            "services": [],
            "waited_seconds": 0,
            "window_seconds": 120,
        }


class TestAdmin:
    def test_creating_the_admin_advances_to_the_detection_step(self, client: TestClient) -> None:
        response = client.post(
            "/api/setup/admin",
            json={"username": "skipper", "password": "harbour", "apply_to_services": False},
        )

        assert response.status_code == 200
        assert response.json()["current_step"] == 2
        assert response.json()["admin_username"] == "skipper"
        assert response.json()["apply_to_services"] is False

    def test_the_checkbox_defaults_to_checked(self, client: TestClient) -> None:
        response = client.post(
            "/api/setup/admin", json={"username": "skipper", "password": "harbour"}
        )

        assert response.json()["apply_to_services"] is True

    def test_the_password_is_never_returned(self, client: TestClient) -> None:
        response = client.post(
            "/api/setup/admin", json={"username": "skipper", "password": "harbour"}
        )

        assert "harbour" not in response.text
        assert "password" not in response.json()

    def test_the_admin_survives_a_reload(self, client: TestClient) -> None:
        client.post("/api/setup/admin", json={"username": "skipper", "password": "harbour"})

        assert client.get("/api/setup/status").json()["admin_username"] == "skipper"

    def test_blank_credentials_are_rejected(self, client: TestClient) -> None:
        assert (
            client.post(
                "/api/setup/admin", json={"username": "", "password": "harbour"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/setup/admin", json={"username": "skipper", "password": ""}
            ).status_code
            == 422
        )

    def test_whitespace_only_username_is_rejected(self, client: TestClient) -> None:
        response = client.post("/api/setup/admin", json={"username": "   ", "password": "harbour"})

        assert response.status_code == 422


class TestDetect:
    def test_a_clean_compose_reports_three_bundled_services(self, client: TestClient) -> None:
        response = client.post("/api/setup/detect", json={})

        assert response.status_code == 200
        services = response.json()["services"]
        assert [row["kind"] for row in services] == ["jellyfin", "qbittorrent", "prowlarr"]
        assert {row["origin"] for row in services} == {"bundled"}

    def test_the_measured_values_reach_the_client(self, client: TestClient) -> None:
        services = client.post("/api/setup/detect", json={}).json()["services"]

        by_kind = {row["kind"]: row for row in services}
        assert by_kind["jellyfin"]["detail"] == "12.1.0"
        assert by_kind["jellyfin"]["base_url"] == "http://jellyfin:8096"
        assert by_kind["jellyfin"]["reason"] == "setup_pending"

    def test_detect_works_without_a_body(self, client: TestClient) -> None:
        assert client.post("/api/setup/detect").status_code == 200

    def test_results_are_readable_from_status_afterwards(self, client: TestClient) -> None:
        client.post("/api/setup/detect", json={})

        assert len(client.get("/api/setup/status").json()["services"]) == 3

    def test_rerunning_detect_does_not_duplicate_rows(self, client: TestClient) -> None:
        client.post("/api/setup/detect", json={})
        response = client.post("/api/setup/detect", json={})

        assert len(response.json()["services"]) == 3

    @pytest.mark.parametrize(
        "probes",
        [fake_probes(qbittorrent=FakeQbittorrentClient(error=ServiceUnavailableError("refused")))],
    )
    def test_a_starting_container_reports_the_waiting_window(self, client: TestClient) -> None:
        body = client.post("/api/setup/detect", json={}).json()

        qbittorrent = next(row for row in body["services"] if row["kind"] == "qbittorrent")
        assert qbittorrent["origin"] == "pending"
        assert body["window_seconds"] == 120


class TestGate:
    def test_setup_endpoints_require_login_once_setup_is_complete(self, client: TestClient) -> None:
        """setup 完成後這個群組不再匿名（plan §6）。真正的登入在票 07。"""
        _complete_setup(client)

        assert client.get("/api/setup/status").status_code == 401
        assert client.post("/api/setup/detect", json={}).status_code == 401
        assert (
            client.post(
                "/api/setup/admin", json={"username": "other", "password": "pass"}
            ).status_code
            == 401
        )

    def test_health_stays_anonymous_after_setup(self, client: TestClient) -> None:
        _complete_setup(client)

        assert client.get("/api/health").status_code == 200


def _complete_setup(client: TestClient) -> None:
    """直接寫 settings 造出「已完成」的狀態。

    只給**不關心第 5 步**的測試用：`POST /setup/complete` 要每個 Route 都綠燈才寫得下去
    （票 09），而這些測試連 Route 都還沒有。走那一支的路徑在 `TestRoutes`。
    """
    import asyncio

    from berth.models import SetupSettings
    from berth.services.settings import read_settings, write_settings

    async def mark() -> None:
        factory = client.app.state.session_factory  # type: ignore[attr-defined]
        async with factory() as session:
            setup = await read_settings(session, SetupSettings)
            setup.completed = True
            await write_settings(session, setup)
            await session.commit()

    asyncio.run(mark())


class TestJellyfin:
    """第 3 步的三支端點（plan §9.4、§9.5、票 06）。判定與冪等本身在 `test_setup_jellyfin.py`。"""

    @pytest.fixture
    def jellyfin(self) -> FakeJellyfinClient:
        return FakeJellyfinClient()

    @pytest.fixture
    def client(
        self,
        config: Config,
        tmp_path: Path,
        probes: SetupProbes,
        jellyfin: FakeJellyfinClient,
    ) -> Iterator[TestClient]:
        """媒體庫路徑指到 tmp_path：bootstrap 會真的建目錄（plan §9.1）。"""
        app = create_app(replace(config, web_root=tmp_path / "never-built"))

        async def override_probes() -> AsyncIterator[SetupProbes]:
            yield jellyfin_probes(probes, jellyfin)

        app.dependency_overrides[get_setup_probes] = override_probes
        app.dependency_overrides[get_client_factory] = lambda: OneJellyfin(jellyfin)
        with TestClient(app, headers=BROWSER) as running:
            _set_paths(running, tmp_path)
            yield running

    def test_before_anything_the_step_list_is_empty(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        response = client.get("/api/setup/jellyfin")

        assert response.status_code == 200
        assert response.json() == {
            "origin": "existing",
            "base_url": "",
            "api_key_present": False,
            "steps": [],
            "libraries": [],
            "version": "",
            # 還沒問過就不是紅燈：那一格是「尚未取得」。
            "version_supported": True,
            # 沒有人動過清單時就是預設三列（票 06f）。
            "bundled": [
                {"name": "Movies", "collection_type": "movies", "folder": "movies", "built": False},
                {"name": "TV", "collection_type": "tvshows", "folder": "tv", "built": False},
                {"name": "Anime", "collection_type": "tvshows", "folder": "anime", "built": False},
            ],
            "library_root": str(tmp_path / "library"),
        }

    def test_the_library_list_is_still_there_on_the_next_visit(self, client: TestClient) -> None:
        """票 06f 驗收：清單在按下之前存進精靈狀態，重新整理（下一個 GET）還在。"""
        libraries = [
            {"name": "電影", "collection_type": "movies", "folder": "films"},
            {"name": "電視劇（華語）", "collection_type": "tvshows", "folder": "tv-zh"},
        ]

        saved = client.put("/api/setup/jellyfin/bundled", json={"libraries": libraries})
        body = client.get("/api/setup/jellyfin").json()

        assert saved.status_code == 200
        assert body["bundled"] == [{**row, "built": False} for row in libraries]

    @pytest.mark.parametrize(
        ("libraries", "refusal"),
        [
            ([], {"reason": "empty"}),
            (
                [
                    {"name": "TV", "collection_type": "tvshows", "folder": "tv"},
                    {"name": "tv", "collection_type": "tvshows", "folder": "tv-2"},
                ],
                {"reason": "name_taken", "row": 1},
            ),
            (
                [{"name": "TV", "collection_type": "tvshows", "folder": "../tv"}],
                {"reason": "folder_outside_root", "row": 0},
            ),
        ],
    )
    def test_a_list_that_cannot_stand_is_refused_with_its_row(
        self, client: TestClient, libraries: list[dict[str, str]], refusal: dict[str, object]
    ) -> None:
        response = client.put("/api/setup/jellyfin/bundled", json={"libraries": libraries})

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert {key: detail[key] for key in ("reason", "row") if key in detail} == refusal
        # 存不下來就是沒存：下一次來看到的仍然是原本那份。
        assert [row["name"] for row in client.get("/api/setup/jellyfin").json()["bundled"]] == [
            "Movies",
            "TV",
            "Anime",
        ]

    def test_only_movies_and_shows_are_accepted(self, client: TestClient) -> None:
        """Berth 寫不了音樂或書（`SUPPORTED_TYPES`），所以這兩種以外的類型根本進不來。"""
        response = client.put(
            "/api/setup/jellyfin/bundled",
            json={"libraries": [{"name": "Music", "collection_type": "music", "folder": "music"}]},
        )

        assert response.status_code == 422

    def test_bootstrap_returns_every_step_with_its_measured_value(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        client.post("/api/setup/admin", json={"username": "skipper", "password": "harbour"})
        client.post("/api/setup/detect", json={})

        response = client.post("/api/setup/jellyfin/bootstrap")

        assert response.status_code == 200
        body = response.json()
        assert [row["step"] for row in body["steps"]] == [
            "public_info",
            "configuration",
            "admin_user",
            "libraries",
            "remote_access",
            "complete",
            "api_key",
        ]
        assert {row["status"] for row in body["steps"]} == {"ok"}
        assert body["origin"] == "bundled"
        assert body["api_key_present"] is True
        assert (body["version"], body["version_supported"]) == ("12.1.0", True)
        assert [row["name"] for row in body["libraries"]] == ["Movies", "TV", "Anime"]
        assert jellyfin.admin == ("skipper", "harbour")

    def test_the_status_endpoint_replays_the_last_run(self, client: TestClient) -> None:
        client.post("/api/setup/admin", json={"username": "skipper", "password": "harbour"})
        client.post("/api/setup/detect", json={})
        client.post("/api/setup/jellyfin/bootstrap")

        body = client.get("/api/setup/jellyfin").json()

        assert {row["status"] for row in body["steps"]} == {"ok"}
        assert body["version"] == "12.1.0"

    def test_a_failed_step_comes_back_with_its_error(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        """版本閘門就是第一步：低於 12.0 時整段停在那裡（brief §16.4、§19）。"""
        client.post("/api/setup/admin", json={"username": "skipper", "password": "harbour"})
        client.post("/api/setup/detect", json={})
        jellyfin.version = "10.11.11"

        body = client.post("/api/setup/jellyfin/bootstrap").json()

        public_info = next(row for row in body["steps"] if row["step"] == "public_info")
        assert public_info["status"] == "failed"
        assert public_info["detail"] == "10.11.11"
        assert "12.0" in public_info["error"]
        assert body["version_supported"] is False
        assert next(row for row in body["steps"] if row["step"] == "libraries")["status"] == (
            "pending"
        )

    def test_connect_needs_credentials(self, client: TestClient) -> None:
        assert client.post("/api/setup/jellyfin/connect", json={}).status_code == 422
        assert (
            client.post(
                "/api/setup/jellyfin/connect", json={"username": "", "password": "x"}
            ).status_code
            == 422
        )

    def test_connecting_to_an_existing_server_lists_its_libraries(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        jellyfin.startup_wizard_completed = True
        jellyfin.admin = ("owner", "s3cret")
        jellyfin.libraries_ = [
            JellyfinLibrary(
                name="Films",
                item_id="a1",
                collection_type="movies",
                locations=("/volume1/media/films",),
                type_options=(
                    TypeOption(
                        type="Movie",
                        metadata_fetchers=("TheTVDB",),
                        image_fetchers=("TheTVDB",),
                    ),
                ),
            )
        ]

        body = client.post(
            "/api/setup/jellyfin/connect", json={"username": "owner", "password": "s3cret"}
        ).json()

        assert body["api_key_present"] is True
        assert body["libraries"][0]["uses_tvdb"] is True
        assert body["libraries"][0]["berth_path"].endswith("/films")
        assert body["libraries"][0]["has_berth_path"] is False

    def test_a_path_that_cannot_be_added_comes_back_as_a_failed_step(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        """不是 500 也不是 422：畫面要看得到原文才給得出手動步驟。"""
        jellyfin.startup_wizard_completed = True
        jellyfin.admin = ("owner", "s3cret")
        client.post("/api/setup/jellyfin/connect", json={"username": "owner", "password": "s3cret"})

        response = client.post("/api/setup/jellyfin/libraries/paths", json={"library": "Nope"})

        assert response.status_code == 200
        libraries = next(row for row in response.json()["steps"] if row["step"] == "libraries")
        assert libraries["status"] == "failed"
        assert "Nope" in libraries["error"]

    def test_the_jellyfin_endpoints_close_after_setup(self, client: TestClient) -> None:
        _complete_setup(client)

        assert client.get("/api/setup/jellyfin").status_code == 401
        assert client.post("/api/setup/jellyfin/bootstrap").status_code == 401
        assert client.put("/api/setup/jellyfin/bundled", json={"libraries": []}).status_code == 401
        assert client.post(
            "/api/setup/jellyfin/libraries/paths", json={"library": "x"}
        ).status_code == (401)


class OneJellyfin:
    """同一台假 Jellyfin：序列跨好幾次呼叫，每次回新實例狀態就沒了。"""

    def __init__(self, jellyfin: FakeJellyfinClient) -> None:
        self._jellyfin = jellyfin

    def jellyfin(self, base_url: str, token: str = "") -> FakeJellyfinClient:
        self._jellyfin.base_url = base_url
        if token:
            self._jellyfin.use_token(token)
        return self._jellyfin

    def qbittorrent(self, base_url: str) -> FakeQbittorrentClient:
        return FakeQbittorrentClient(base_url=base_url)

    def prowlarr(self, base_url: str, api_key: str) -> FakeProwlarrClient:
        return FakeProwlarrClient(base_url=base_url)


def jellyfin_probes(probes: SetupProbes, jellyfin: FakeJellyfinClient) -> SetupProbes:
    return SetupProbes(
        jellyfin=jellyfin,
        qbittorrent=probes.qbittorrent,
        prowlarr=probes.prowlarr,
        prowlarr_api_key=probes.prowlarr_api_key,
    )


def _set_paths(client: TestClient, data_root: Path) -> None:
    """三層路徑指到 tmp_path：測試不該對真的 `/data` 建目錄、鏈接檔案（brief §4.1）。"""
    import asyncio

    from berth.models import PathSettings
    from berth.services.settings import write_settings

    async def write() -> None:
        factory = client.app.state.session_factory  # type: ignore[attr-defined]
        async with factory() as session:
            await write_settings(
                session,
                PathSettings(
                    library_root=str(data_root / "library"),
                    complete_root=str(data_root / "torrent" / "complete"),
                    incomplete_root=str(data_root / "torrent" / "incomplete"),
                ),
            )
            await session.commit()

    asyncio.run(write())


class TestQbittorrent:
    """第 4 步的兩支端點（plan §9.3 第 4 步、票 08）。

    差異的算法與冪等本身在 `test_setup_qbittorrent.py`。
    """

    @pytest.fixture
    def qbittorrent(self) -> FakeQbittorrentClient:
        return FakeQbittorrentClient()

    @pytest.fixture
    def client(
        self,
        config: Config,
        tmp_path: Path,
        probes: SetupProbes,
        qbittorrent: FakeQbittorrentClient,
    ) -> Iterator[TestClient]:
        app = create_app(replace(config, web_root=tmp_path / "never-built"))

        async def override_probes() -> AsyncIterator[SetupProbes]:
            yield probes

        app.dependency_overrides[get_setup_probes] = override_probes
        app.dependency_overrides[get_client_factory] = lambda: FakeClientFactory(
            qbittorrent=qbittorrent
        )
        with TestClient(app, headers=BROWSER) as running:
            running.post("/api/setup/admin", json={"username": "skipper", "password": "harbour"})
            running.post("/api/setup/detect")
            yield running

    def test_the_diff_lists_every_recommended_key(self, client: TestClient) -> None:
        response = client.get("/api/setup/qbittorrent/diff")

        assert response.status_code == 200
        body = response.json()
        assert [row["key"] for row in body["diffs"]] == [
            "temp_path_enabled",
            "temp_path",
            "save_path",
            "auto_tmm_enabled",
            "category_changed_tmm_enabled",
        ]
        assert body["version"] == "v5.2.3"
        assert body["webapi_version"] == "2.15.1"
        assert body["supported"] is True
        assert body["sets_password"] is True

    def test_applying_writes_the_keys_and_leaves_no_difference(
        self, client: TestClient, qbittorrent: FakeQbittorrentClient
    ) -> None:
        body = client.post("/api/setup/qbittorrent/apply").json()

        assert [row["differs"] for row in body["diffs"]] == [False] * 5
        assert [row["status"] for row in body["steps"]] == ["ok"] * 6
        assert qbittorrent.writes[0].keys() == {
            "temp_path_enabled",
            "temp_path",
            "save_path",
            "auto_tmm_enabled",
            "category_changed_tmm_enabled",
        }

    def test_an_old_web_api_is_refused_with_its_version_visible(
        self, config: Config, tmp_path: Path, probes: SetupProbes
    ) -> None:
        app = create_app(replace(config, web_root=tmp_path / "never-built"))
        old = FakeQbittorrentClient(version=QbittorrentVersion(app="v4.3.9", webapi="2.8.2"))

        async def override_probes() -> AsyncIterator[SetupProbes]:
            yield probes

        app.dependency_overrides[get_setup_probes] = override_probes
        app.dependency_overrides[get_client_factory] = lambda: FakeClientFactory(qbittorrent=old)
        with TestClient(app, headers=BROWSER) as running:
            body = running.get("/api/setup/qbittorrent/diff").json()

        assert (body["supported"], body["blocked"]) == (False, True)
        assert body["webapi_version"] == "2.8.2"
        assert body["diffs"] == []

    def test_an_unreachable_service_is_a_body_not_a_500(
        self, config: Config, tmp_path: Path, probes: SetupProbes
    ) -> None:
        app = create_app(replace(config, web_root=tmp_path / "never-built"))
        down = FakeQbittorrentClient(error=ServiceUnavailableError("connection refused"))

        async def override_probes() -> AsyncIterator[SetupProbes]:
            yield probes

        app.dependency_overrides[get_setup_probes] = override_probes
        app.dependency_overrides[get_client_factory] = lambda: FakeClientFactory(qbittorrent=down)
        with TestClient(app, headers=BROWSER) as running:
            response = running.get("/api/setup/qbittorrent/diff")

        assert response.status_code == 200
        assert response.json()["reachable"] is False
        assert response.json()["error"] == "connection refused"


class TestSource:
    """第 6–7 步的端點（plan §9.3 第 6–7 步、票 08）。"""

    @pytest.fixture
    def prowlarr(self) -> FakeProwlarrClient:
        return FakeProwlarrClient()

    @pytest.fixture
    def tmdb(self) -> FakeTmdbClient:
        return FakeTmdbClient()

    @pytest.fixture
    def client(
        self,
        config: Config,
        tmp_path: Path,
        probes: SetupProbes,
        prowlarr: FakeProwlarrClient,
        tmdb: FakeTmdbClient,
    ) -> Iterator[TestClient]:
        app = create_app(replace(config, web_root=tmp_path / "never-built"))

        async def override_probes() -> AsyncIterator[SetupProbes]:
            yield probes

        app.dependency_overrides[get_setup_probes] = override_probes
        app.dependency_overrides[get_client_factory] = lambda: FakeClientFactory(
            prowlarr=prowlarr, tmdb=tmdb
        )
        with TestClient(app, headers=BROWSER) as running:
            running.post("/api/setup/admin", json={"username": "skipper", "password": "harbour"})
            running.post("/api/setup/detect")
            yield running

    def test_the_defaults_come_back_with_their_names(self, client: TestClient) -> None:
        body = client.get("/api/setup/indexers").json()

        assert [row["definition_name"] for row in body["options"]] == list(DEFAULT_INDEXERS)
        assert body["kind"] == "prowlarr"
        assert body["origin"] == "bundled"

    def test_applying_adds_only_what_was_ticked(self, client: TestClient) -> None:
        body = client.post(
            "/api/setup/indexers/apply", json={"indexers": ["nyaasi", "mikan"]}
        ).json()

        assert [row["step"] for row in body["steps"] if row["step"] in DEFAULT_INDEXERS] == [
            "nyaasi",
            "mikan",
        ]
        assert [row["definition_name"] for row in body["options"] if row["present"]] == [
            "nyaasi",
            "mikan",
        ]

    def test_an_existing_torznab_endpoint_is_tested_and_remembered(
        self, client: TestClient
    ) -> None:
        body = client.post(
            "/api/setup/indexers/connect",
            json={
                "kind": "torznab",
                "base_url": "http://jackett:9117/api/v2.0/indexers/all/results/torznab/api/",
                "api_key": "the-key",
            },
        ).json()

        assert body["kind"] == "torznab"
        assert [(row["step"], row["status"]) for row in body["steps"]] == [("torznab", "ok")]
        # 尾斜線在存下來之前就削掉，之後組網址才不會出現兩條斜線。
        assert body["base_url"].endswith("/torznab/api")

    def test_sites_can_be_searched_and_removed_after_they_are_added(
        self, client: TestClient, prowlarr: FakeProwlarrClient
    ) -> None:
        """加入 → 試搜 → 不要的移除（票 06e）。試搜逐站回報，移除之後那一站不見。"""
        added = client.post("/api/setup/indexers/apply", json={"indexers": ["dmhy", "yts"]}).json()
        ids = {row["definition_name"]: row["indexer_id"] for row in added["options"]}
        assert added["options"][1]["language"] == "zh-TW"

        found = client.get("/api/setup/indexers/search", params={"query": " "}).json()
        assert found["query"] == ""
        assert [row["definition_name"] for row in found["sites"]] == ["dmhy", "yts"]

        after = client.delete(f"/api/setup/indexers/{ids['yts']}")
        assert after.status_code == 200
        assert [row["definition_name"] for row in after.json()["options"] if row["present"]] == [
            "dmhy"
        ]
        assert prowlarr.deleted == [ids["yts"]]

    def test_only_the_indexer_half_can_be_skipped_and_unskipped(self, client: TestClient) -> None:
        """跳過是可以反悔的。TMDB 那一半根本沒有這一支（票 02b）。"""
        assert client.post("/api/setup/indexers/skip", json={}).json()["skipped"] is True
        assert client.get("/api/setup/indexers").json()["skipped"] is True

        assert (
            client.post("/api/setup/indexers/skip", json={"skipped": False}).json()["skipped"]
            is False
        )
        # 這一支不存在了。這裡的 app 沒有掛前端所以是 404；掛了前端的正式程序由 `SpaFiles`
        # 的 mount 接手，POST 會拿到 405（它只收 GET / HEAD）——兩者都是「沒有這支端點」。
        assert client.post("/api/setup/tmdb/skip", json={}).status_code == 404

    def test_tmdb_starts_empty_and_takes_the_key_the_user_pastes(
        self, client: TestClient, tmdb: FakeTmdbClient
    ) -> None:
        assert client.get("/api/setup/tmdb").json() == {
            "api_key_present": False,
            "verified": False,
            "steps": [],
        }

        body = client.post("/api/setup/tmdb/test", json={"api_key": "the-users-key"}).json()

        assert tmdb.credential == "the-users-key"
        assert [(row["step"], row["status"]) for row in body["steps"]] == [("configuration", "ok")]
        assert (body["api_key_present"], body["verified"]) == (True, True)

    def test_the_new_endpoints_close_after_setup(self, client: TestClient) -> None:
        """門禁是 middleware，所以新掛的端點什麼都不做就已經在門後（票 07）。"""
        _complete_setup(client)

        for path in ("/api/setup/qbittorrent/diff", "/api/setup/indexers", "/api/setup/tmdb"):
            assert client.get(path).status_code == 401, path


class TestRoutes:
    """第 5 步、第 8 步的三支端點（plan §9.3 第 5 步、第 8 步、§9.5、票 09）。

    這一組是**整個精靈跑一遍**：管理員 → 偵測 → Jellyfin → qBittorrent → 跳過來源 →
    建 Route → 完成。檔案系統是真的（`tmp_path`），所以硬鏈接檢查也是真的。
    """

    @pytest.fixture
    def jellyfin(self) -> FakeJellyfinClient:
        return FakeJellyfinClient()

    @pytest.fixture
    def qbittorrent(self) -> FakeQbittorrentClient:
        return FakeQbittorrentClient()

    @pytest.fixture
    def client(
        self,
        config: Config,
        tmp_path: Path,
        jellyfin: FakeJellyfinClient,
        qbittorrent: FakeQbittorrentClient,
    ) -> Iterator[TestClient]:
        app = create_app(replace(config, web_root=tmp_path / "never-built"))
        probes = fake_probes(jellyfin=jellyfin, qbittorrent=qbittorrent)

        async def override_probes() -> AsyncIterator[SetupProbes]:
            yield probes

        app.dependency_overrides[get_setup_probes] = override_probes
        app.dependency_overrides[get_client_factory] = lambda: FakeClientFactory(
            jellyfin=jellyfin, qbittorrent=qbittorrent
        )
        with TestClient(app, headers=BROWSER) as running:
            _set_paths(running, tmp_path)
            running.post("/api/setup/admin", json={"username": "skipper", "password": "harbour"})
            running.post("/api/setup/detect")
            running.post("/api/setup/jellyfin/bootstrap")
            running.post("/api/setup/qbittorrent/apply")
            running.post("/api/setup/indexers/skip", json={})
            running.post("/api/setup/tmdb/test", json={"api_key": "the-users-key"})
            yield running

    def test_the_wizard_arrives_at_step_five_with_three_libraries_to_route(
        self, client: TestClient
    ) -> None:
        assert client.get("/api/setup/status").json()["current_step"] == 5

        body = client.get("/api/setup/routes").json()

        assert body["origin"] == "bundled"
        assert [row["name"] for row in body["libraries"]] == ["Movies", "TV", "Anime"]
        assert [row["has_route"] for row in body["libraries"]] == [False, False, False]
        assert body["routes"] == []
        assert body["ready"] is False

    def test_building_returns_three_green_routes_with_their_checks(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        response = client.post("/api/setup/routes", json={})

        assert response.status_code == 200
        body = response.json()
        assert [(row["slug"], row["health"]) for row in body["routes"]] == [
            ("movies", "ok"),
            ("tv", "ok"),
            ("anime", "ok"),
        ]
        assert [row["step"] for row in body["routes"][0]["checks"]] == [
            "category",
            "download_path",
            "library_path",
            "probe_visible",
            "hardlink",
        ]
        assert body["ready"] is True
        assert body["routes"][1]["category"] == "berth-tv"
        # 目標路徑是 **Jellyfin 回報的** 那一條，不是 Berth 再算一次的（plan §9.3 第 5 步）。
        assert body["routes"][1]["target_path"] == f"{tmp_path / 'library'}/tv"

    def test_a_target_that_is_not_a_library_path_is_refused(self, client: TestClient) -> None:
        """路徑用選的，不用打的（brief §4.1）。這是唯一會回 4xx 的情況。

        TV 還沒有 Route：已經有 Route 的媒體庫的選擇會被略過（票 14，精靈只新增）。
        """
        # 套件內會忽略 selections，所以先讓它變成既有 Jellyfin 的形狀。
        _mark_jellyfin_existing(client)

        response = client.post(
            "/api/setup/routes",
            json={"selections": [{"library": "TV", "target_path": "/mnt/elsewhere"}]},
        )

        assert response.status_code == 422
        assert "not a path of" in response.json()["detail"]

    def test_a_route_deleted_while_the_step_rechecks_is_a_404_not_a_crash(
        self, client: TestClient, qbittorrent: FakeQbittorrentClient
    ) -> None:
        """第 5 步重跑時在鎖外打網路，那幾秒裡另一個分頁把某一條刪掉了（票 01）。

        寫回時 0 列被改到，那是 `routes/*` 早就定好的 404 `route_missing`（票 14、14a），
        不是 500——`api/setup.py` 從前只接 `ValueError`，`StaleDataError` 因此裸奔。
        """
        client.post("/api/setup/routes", json={})
        doomed = client.get("/api/setup/routes").json()["routes"][0]["id"]
        # app 自己那一份 sessionmaker：刪除要從另一條連線發生，才是另一個分頁的樣子。
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        delete_once_during_checks(qbittorrent, sessions, doomed)

        refused = client.post("/api/setup/routes", json={})

        assert refused.status_code == 404
        assert refused.json()["detail"]["reason"] == "route_missing"

    def test_completing_needs_a_green_route_first(self, client: TestClient) -> None:
        refused = client.post("/api/setup/complete")

        assert refused.status_code == 422
        assert client.get("/api/health").json()["setup_completed"] is False

    def test_completing_needs_a_tmdb_credential_first(self, client: TestClient) -> None:
        """第 7 步是閘門，第 8 步也擋一次（票 02b）：完成看的是存下來的那一條綠燈。

        回頭貼一把測不過的 key 已經不會蓋掉驗過的那一把（票 06i），所以直接把狀態推到
        「沒有驗過的 key」——這一條驗的是完成的閘門，不是怎麼走到那裡。
        """
        client.post("/api/setup/routes", json={})
        _forget_tmdb(client)

        refused = client.post("/api/setup/complete")

        assert refused.status_code == 422
        assert "tmdb" in refused.json()["detail"].lower()
        assert client.get("/api/health").json()["setup_completed"] is False

    def test_completing_closes_the_wizard_and_the_api(self, client: TestClient) -> None:
        client.post("/api/setup/routes", json={})
        assert client.get("/api/setup/status").json()["current_step"] == 8

        body = client.post("/api/setup/complete").json()

        assert body["completed"] is True
        assert client.get("/api/health").json()["setup_completed"] is True
        # 精靈跑完之後這一組就是設定入口，只有登入的管理員進得來（票 07）。
        assert client.get("/api/setup/status").status_code == 401
        assert client.get("/api/setup/routes").status_code == 401
        assert client.post("/api/setup/complete").status_code == 401


def _forget_tmdb(client: TestClient) -> None:
    """把第 7 步推回「沒有驗過的 key」。"""
    import asyncio

    from berth.models import SetupSettings, TmdbSettings
    from berth.services.settings import read_settings, write_settings

    async def forget() -> None:
        # `TestClient.app` 是 Starlette 的 `ASGIApp`，型別上沒有 `state`（實際是 FastAPI）。
        factory = client.app.state.session_factory  # type: ignore[attr-defined]
        async with factory() as session:
            setup = await read_settings(session, SetupSettings)
            setup.tmdb.steps = []
            await write_settings(session, setup)
            await write_settings(session, TmdbSettings())
            await session.commit()

    asyncio.run(forget())


def _mark_jellyfin_existing(client: TestClient) -> None:
    """把 Jellyfin 的判定改成既有——套件內不看使用者的勾選，那條路徑才驗得到。"""
    import asyncio

    from berth.domain import ServiceKind, ServiceOrigin
    from berth.models import SetupSettings
    from berth.services.settings import read_settings, write_settings

    async def mark() -> None:
        factory = client.app.state.session_factory  # type: ignore[attr-defined]
        async with factory() as session:
            setup = await read_settings(session, SetupSettings)
            probe = setup.services[ServiceKind.JELLYFIN]
            setup.services = {
                **setup.services,
                ServiceKind.JELLYFIN: probe.model_copy(update={"origin": ServiceOrigin.EXISTING}),
            }
            await write_settings(session, setup)
            await session.commit()

    asyncio.run(mark())
