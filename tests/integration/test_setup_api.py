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
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.api.deps import get_setup_probes
from berth.config import Config
from berth.main import create_app
from berth.services.setup import SetupProbes


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
    with TestClient(app) as running:
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
