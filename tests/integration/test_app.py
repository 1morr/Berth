"""程序層面的行為：啟動套 migration、健康端點、前端由同一個程序提供（票 02 驗收）。"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from berth.config import Config
from berth.main import create_app


@pytest.fixture
def web_root(tmp_path: Path) -> Path:
    """假的 `pnpm -C web build` 產出。"""
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html><title>Berth</title>", encoding="utf-8")
    (root / "assets" / "index.js").write_text("export {}", encoding="utf-8")
    return root


@pytest.fixture
def client(config: Config, web_root: Path) -> TestClient:
    return TestClient(create_app(replace(config, web_root=web_root)))


class TestStartup:
    def test_starting_on_an_empty_config_root_creates_the_database(
        self, config: Config, client: TestClient
    ) -> None:
        assert not config.database_path.exists()

        with client:
            assert config.database_path.exists()

    def test_starting_twice_over_the_same_config_root_succeeds(
        self, config: Config, client: TestClient
    ) -> None:
        with client:
            pass
        with client:
            assert client.get("/api/health").status_code == 200


class TestHealth:
    def test_health_answers_anonymously(self, client: TestClient) -> None:
        with client:
            response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_health_reports_the_running_version(self, client: TestClient) -> None:
        from berth.config import VERSION

        with client:
            assert client.get("/api/health").json()["version"] == VERSION


class TestFrontend:
    def test_the_root_serves_the_built_index(self, client: TestClient) -> None:
        with client:
            response = client.get("/")

        assert response.status_code == 200
        assert "<title>Berth</title>" in response.text

    def test_assets_are_served(self, client: TestClient) -> None:
        with client:
            assert client.get("/assets/index.js").status_code == 200

    def test_client_side_routes_fall_back_to_the_index(self, client: TestClient) -> None:
        """`/setup` 這類路徑只有前端 router 認得，後端要回 index.html。"""
        with client:
            response = client.get("/setup")

        assert response.status_code == 200
        assert "<title>Berth</title>" in response.text

    def test_a_client_route_merely_starting_with_api_still_gets_the_index(
        self, client: TestClient
    ) -> None:
        with client:
            response = client.get("/apiary")

        assert response.status_code == 200
        assert "<title>Berth</title>" in response.text

    def test_unknown_api_paths_stay_json_404(self, client: TestClient) -> None:
        """否則前端 fetch 會拿到 HTML 再在 JSON.parse 炸開，錯誤訊息毫無意義。"""
        with client:
            response = client.get("/api/nope")

        assert response.status_code == 404
        assert json.loads(response.text)["detail"]


class TestFrontendNotBuilt:
    def test_the_api_still_runs_without_a_frontend_build(self, config: Config) -> None:
        missing = replace(config, web_root=config.config_root / "never-built")

        with TestClient(create_app(missing)) as client:
            assert client.get("/api/health").status_code == 200
            assert client.get("/").status_code == 404
