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
from berth.adapters.tmdb import PROJECT_CREDENTIAL
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.api.deps import get_client_factory, get_setup_probes
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.main import create_app
from berth.services import jellyfin as jellyfin_service
from berth.services.clients import SetupProbes
from berth.services.indexer import DEFAULT_INDEXERS
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
        assert by_kind["jellyfin"]["detail"] == "10.11.11"
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
    """票 09 的 `POST /setup/complete` 還沒有；直接寫 settings 造出「已完成」的狀態。"""
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
    """第 3 步的四支端點（plan §9.4、§9.5、票 06）。判定與冪等本身在 `test_setup_jellyfin.py`。"""

    @pytest.fixture(autouse=True)
    def _fast_polling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """插件與重啟的輪詢間隔在測試裡不必真的等。"""
        monkeypatch.setattr(jellyfin_service, "POLL_SECONDS", 0.0)

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
            _set_library_root(running, tmp_path / "library")
            yield running

    def test_before_anything_the_step_list_is_empty(self, client: TestClient) -> None:
        response = client.get("/api/setup/jellyfin")

        assert response.status_code == 200
        assert response.json() == {
            "origin": "existing",
            "base_url": "",
            "api_key_present": False,
            "steps": [],
            "libraries": [],
            "merge_versions_installed": False,
            "merge_movies_task_id": "",
            "merge_episodes_task_id": "",
        }

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
            "plugin",
            "tasks",
        ]
        assert {row["status"] for row in body["steps"]} == {"ok"}
        assert body["origin"] == "bundled"
        assert body["api_key_present"] is True
        assert body["merge_versions_installed"] is True
        assert [row["name"] for row in body["libraries"]] == ["Movies", "TV", "Anime"]
        assert jellyfin.admin == ("skipper", "harbour")

    def test_the_status_endpoint_replays_the_last_run(self, client: TestClient) -> None:
        client.post("/api/setup/admin", json={"username": "skipper", "password": "harbour"})
        client.post("/api/setup/detect", json={})
        client.post("/api/setup/jellyfin/bootstrap")

        body = client.get("/api/setup/jellyfin").json()

        assert {row["status"] for row in body["steps"]} == {"ok"}
        assert body["merge_movies_task_id"] == "fd957c84b0cfc2380becf2893e4b76fc"

    def test_a_failed_step_comes_back_with_its_error(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        client.post("/api/setup/admin", json={"username": "skipper", "password": "harbour"})
        client.post("/api/setup/detect", json={})
        jellyfin.install_failures = 99

        body = client.post("/api/setup/jellyfin/bootstrap").json()

        plugin = next(row for row in body["steps"] if row["step"] == "plugin")
        assert plugin["status"] == "failed"
        assert plugin["error"]
        assert next(row for row in body["steps"] if row["step"] == "tasks")["status"] == "pending"

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

    def test_the_plugin_button_only_runs_the_last_two_steps(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        jellyfin.startup_wizard_completed = True
        jellyfin.admin = ("owner", "s3cret")
        client.post("/api/setup/jellyfin/connect", json={"username": "owner", "password": "s3cret"})

        body = client.post("/api/setup/jellyfin/plugin").json()

        assert body["merge_versions_installed"] is True
        assert jellyfin.created == []
        assert jellyfin.restarts == 1

    def test_the_jellyfin_endpoints_close_after_setup(self, client: TestClient) -> None:
        _complete_setup(client)

        assert client.get("/api/setup/jellyfin").status_code == 401
        assert client.post("/api/setup/jellyfin/bootstrap").status_code == 401
        assert client.post("/api/setup/jellyfin/plugin").status_code == 401


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


def _set_library_root(client: TestClient, root: Path) -> None:
    """測試不該對真的 `/data/library` 建目錄。"""
    import asyncio

    from berth.models import PathSettings
    from berth.services.settings import read_settings, write_settings

    async def write() -> None:
        factory = client.app.state.session_factory  # type: ignore[attr-defined]
        async with factory() as session:
            paths = await read_settings(session, PathSettings)
            paths.library_root = str(root)
            await write_settings(session, paths)
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
    """第 5–6 步的端點（plan §9.3 第 5–6 步、票 08）。"""

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

    def test_the_ten_defaults_come_back_with_their_names(self, client: TestClient) -> None:
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

    def test_the_source_berth_can_be_skipped_and_unskipped(self, client: TestClient) -> None:
        """跳過是可以反悔的。步驟怎麼跟著走在 `test_setup_source.py`。"""
        assert client.post("/api/setup/indexers/skip", json={}).json()["skipped"] is True
        assert client.get("/api/setup/indexers").json()["skipped"] is True
        assert client.post("/api/setup/tmdb/skip", json={}).json()["skipped"] is True

        assert (
            client.post("/api/setup/indexers/skip", json={"skipped": False}).json()["skipped"]
            is False
        )

    def test_tmdb_answers_with_the_built_in_credential(
        self, client: TestClient, tmdb: FakeTmdbClient
    ) -> None:
        assert client.get("/api/setup/tmdb").json() == {
            "using_project_credential": True,
            "steps": [],
            "skipped": False,
        }

        body = client.post("/api/setup/tmdb/test", json={}).json()

        assert tmdb.credential == PROJECT_CREDENTIAL
        assert [(row["step"], row["status"]) for row in body["steps"]] == [("configuration", "ok")]

    def test_a_pasted_tmdb_key_is_used_instead(
        self, client: TestClient, tmdb: FakeTmdbClient
    ) -> None:
        body = client.post("/api/setup/tmdb/test", json={"api_key": "the-users-key"}).json()

        assert tmdb.credential == "the-users-key"
        assert body["using_project_credential"] is False

    def test_the_new_endpoints_close_after_setup(self, client: TestClient) -> None:
        """門禁是 middleware，所以新掛的端點什麼都不做就已經在門後（票 07）。"""
        _complete_setup(client)

        for path in ("/api/setup/qbittorrent/diff", "/api/setup/indexers", "/api/setup/tmdb"):
            assert client.get(path).status_code == 401, path
