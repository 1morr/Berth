"""健康與服務設定的端點（plan §6 health / settings 群組、票 10 驗收）。

門禁的規則在 `test_auth_api.py`，檢查本身在 `test_health_service.py`。這裡驗的是形狀與
「誰進得來」：`/health` 匿名、`/health/detail` 要登入、`/settings/*` 只有管理員。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from berth.adapters.budget import BudgetExhaustedError, RequestBudget
from berth.adapters.http import ServiceUnavailableError
from berth.api.deps import get_client_factory
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.domain import BudgetUse
from berth.main import create_app
from berth.models import Route, Setting
from berth.services.health import CHECK_INTERVAL, check_health
from berth.services.routes import build_routes
from berth.services.setup import complete_setup
from tests.integration.arrange import NOW, arrange, bundled_libraries, factory_for, fake_jellyfin
from tests.integration.factories import FakeClientFactory

BROWSER = {CSRF_HEADER: "XMLHttpRequest"}
ADMIN = {"username": "skipper", "password": "harbour"}
DECKHAND = {"username": "deckhand", "password": "rope"}


@pytest.fixture
def factory(roots: dict[str, Path]) -> FakeClientFactory:
    """同一台假 Jellyfin 既是健康檢查的對象，也是登入的身分來源（brief §11）。"""
    return factory_for(
        roots,
        jellyfin=fake_jellyfin(
            bundled_libraries(roots["library"]),
            admin=(ADMIN["username"], ADMIN["password"]),
            users={DECKHAND["username"]: DECKHAND["password"]},
        ),
    )


@pytest.fixture
def client(
    config: Config, tmp_path: Path, roots: dict[str, Path], factory: FakeClientFactory
) -> Iterator[TestClient]:
    """精靈跑完、三條 Route 綠燈、健康檢查跑過一輪的一台 Berth。"""
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app) as running:
        _seed(running, roots, factory)
        yield running


def post(client: TestClient, path: str, body: object = None) -> httpx.Response:
    response: httpx.Response = client.post(path, json=body, headers=BROWSER)
    return response


def sign_in(client: TestClient, credentials: dict[str, str]) -> httpx.Response:
    return post(client, "/api/auth/login", credentials)


def services(body: dict[str, object]) -> dict[str, dict[str, object]]:
    rows: list[dict[str, object]] = body["services"]  # type: ignore[assignment]
    return {str(row["kind"]): row for row in rows}


class TestAnonymousHealth:
    def test_it_answers_without_a_session(self, client: TestClient) -> None:
        """compose 的健康檢查與前端的路由守衛都打這一支（plan §6）。"""
        response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_it_turns_degraded_when_a_check_fails(
        self, client: TestClient, roots: dict[str, Path], factory: FakeClientFactory
    ) -> None:
        factory.prowlarr_.ping_error = ServiceUnavailableError("connection refused")
        _check(client, factory)

        assert client.get("/api/health").json()["status"] == "degraded"

    def test_it_does_not_leak_the_detail(self, client: TestClient) -> None:
        """匿名的人只該知道「好」或「不好」，不該知道內部主機名與版本（票 07 同一個理由）。"""
        assert set(client.get("/api/health").json()) == {
            "status",
            "version",
            "setup_completed",
            "owner_established",
        }


class TestDetail:
    def test_it_needs_a_session(self, client: TestClient) -> None:
        assert client.get("/api/health/detail").status_code == 401

    def test_a_plain_user_can_read_it(self, client: TestClient) -> None:
        """健康頁是唯讀的維運資訊，不是設定（brief §11）。"""
        sign_in(client, DECKHAND)

        assert client.get("/api/health/detail").status_code == 200

    def test_it_reports_all_four_checks(self, client: TestClient) -> None:
        sign_in(client, ADMIN)

        body = client.get("/api/health/detail").json()

        assert set(services(body)) == {"jellyfin", "qbittorrent", "prowlarr"}
        assert body["routes_status"] == "ok"
        assert len(body["routes"]) == 3

    def test_each_service_carries_its_last_success(self, client: TestClient) -> None:
        sign_in(client, ADMIN)

        row = services(client.get("/api/health/detail").json())["jellyfin"]

        assert row["status"] == "ok"
        assert row["last_ok_at"] is not None
        assert row["checked_at"] is not None
        assert row["origin"] == "bundled"

    def test_a_failure_carries_the_reason(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        factory.prowlarr_.ping_error = ServiceUnavailableError("GET /ping: connection refused")
        _check(client, factory)
        sign_in(client, ADMIN)

        row = services(client.get("/api/health/detail").json())["prowlarr"]

        assert row["status"] == "failed"
        assert "connection refused" in str(row["error"])
        assert row["failures"] == 1

    def test_the_route_checks_come_through_cable_by_cable(self, client: TestClient) -> None:
        sign_in(client, ADMIN)

        route = client.get("/api/health/detail").json()["routes"][0]

        assert [row["step"] for row in route["checks"]] == [
            "category",
            "download_path",
            "download_visible",
            "library_path",
            "probe_visible",
            "hardlink",
        ]

    def test_it_says_when_the_last_round_ran(self, client: TestClient) -> None:
        """「上次檢查」是這一頁的可信度：五分鐘前的綠燈與現在的綠燈不是同一件事。"""
        sign_in(client, ADMIN)

        body = client.get("/api/health/detail").json()

        assert body["checked_at"] is not None
        assert body["interval_seconds"] == int(CHECK_INTERVAL.total_seconds())


class TestManualCheck:
    def test_it_needs_a_session(self, client: TestClient) -> None:
        assert post(client, "/api/health/check").status_code == 401

    def test_it_runs_the_four_checks_now(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        """不必等五分鐘（票 10 的 playwright 驗證也靠它）。"""
        sign_in(client, ADMIN)
        factory.prowlarr_.ping_error = ServiceUnavailableError("connection refused")

        body = post(client, "/api/health/check").json()

        assert services(body)["prowlarr"]["status"] == "failed"

    def test_it_refuses_without_the_csrf_header(self, client: TestClient) -> None:
        sign_in(client, ADMIN)

        assert client.post("/api/health/check").status_code == 403


class TestServiceSettings:
    def test_only_administrators_get_in(self, client: TestClient) -> None:
        sign_in(client, DECKHAND)

        assert client.get("/api/settings/services").status_code == 403

    def test_it_needs_a_session(self, client: TestClient) -> None:
        assert client.get("/api/settings/services").status_code == 401

    def test_it_lists_the_three_services_with_their_addresses(self, client: TestClient) -> None:
        sign_in(client, ADMIN)

        body = client.get("/api/settings/services").json()

        assert services(body)["jellyfin"]["base_url"] == "http://jellyfin:8096"
        assert services(body)["prowlarr"]["base_url"] == "http://prowlarr:9696"

    def test_testing_one_service_answers_with_the_fresh_result(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        sign_in(client, ADMIN)
        factory.qbittorrent_.error = ServiceUnavailableError("connection refused")

        body = post(client, "/api/settings/services/qbittorrent/test").json()

        assert services(body)["qbittorrent"]["status"] == "failed"
        assert services(body)["jellyfin"]["status"] == "ok"

    def test_testing_an_unknown_service_is_422(self, client: TestClient) -> None:
        sign_in(client, ADMIN)

        assert post(client, "/api/settings/services/plex/test").status_code == 422


class TestRecordsFromBeforeTicket32:
    """票 32 之前存下的三個全域鍵紀錄：精靈頁 2、設定頁與健康頁照樣打得開。

    舊資料有三種：`setup.qbittorrent.steps` 裡三個鍵的步驟、健康那一列的 `drift`、Route 檢查裡
    已經拿掉的失敗代碼 `save_path_missing`。採寬鬆讀取（不另寫 migration）：讀的時候丟掉、
    下一次寫入就消失。
    """

    def test_pages_two_settings_and_health_still_open(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        _write_old_records(client)
        sign_in(client, ADMIN)

        qbittorrent = client.get("/api/setup/qbittorrent/diff")
        assert qbittorrent.status_code == 200
        assert [row["step"] for row in qbittorrent.json()["steps"]] == ["web_ui_password"]
        assert client.get("/api/setup/status").status_code == 200
        health = client.get("/api/settings/services")
        assert health.status_code == 200
        assert "drift" not in services(health.json())["qbittorrent"]
        routes = client.get("/api/routes")
        assert routes.status_code == 200
        failures = {
            check["step"]: check["failure"]
            for check in routes.json()[0]["route"]["checks"]
            if check["status"] == "failed"
        }
        assert failures == {"download_path": "unexpected"}


def _write_old_records(client: TestClient) -> None:
    """照票 32 之前的形狀直接改資料庫裡的 JSON，不經過現在的模型。"""

    async def run() -> None:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]  # Starlette 的 app 型別是 ASGIApp
        async with sessions() as session:
            setup = await session.get(Setting, "setup")
            steps = [
                {"key": key, "status": "ok", "detail": "/data/torrent/complete"}
                for key in ("save_path", "auto_tmm_enabled", "category_changed_tmm_enabled")
            ]
            setup.value_json = {
                **setup.value_json,
                "qbittorrent": {
                    **setup.value_json["qbittorrent"],
                    "steps": [*steps, {"key": "web_ui_password", "status": "ok"}],
                },
            }
            health = await session.get(Setting, "health")
            rows = health.value_json["services"]
            rows["qbittorrent"] = {**rows["qbittorrent"], "drift": ["auto_tmm_enabled"]}
            health.value_json = {**health.value_json, "services": rows}
            route = (await session.scalars(select(Route).order_by(Route.id))).first()
            assert route is not None and route.health_detail_json is not None
            route.health_detail_json = {
                **route.health_detail_json,
                "checks": [
                    {
                        **check,
                        "status": "failed",
                        "failure": "save_path_missing",
                        "error": "qBittorrent did not report a global save_path",
                    }
                    if check["key"] == "download_path"
                    else check
                    for check in route.health_detail_json["checks"]
                ],
            }
            await session.commit()

    asyncio.run(run())


def _seed(client: TestClient, roots: dict[str, Path], factory: FakeClientFactory) -> None:
    """把 DB 推到「精靈跑完、健康檢查跑過一輪」。"""

    async def run() -> None:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            await arrange(session, roots)
            await build_routes(session, factory, ())
            await complete_setup(session)
            await check_health(session, factory, now=NOW)

    asyncio.run(run())


def _check(client: TestClient, factory: FakeClientFactory) -> None:
    """再跑一輪健康檢查（不經過 API，測的東西才不會是端點自己）。"""

    async def run() -> None:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            await check_health(session, factory, now=NOW + CHECK_INTERVAL)

    asyncio.run(run())


class TestRequestBudget:
    """一個站一份請求預算（M3 票 20）：健康頁說得出這一小時誰用了多少、哪一種工作被延後。"""

    def test_it_needs_a_session(self, client: TestClient) -> None:
        assert client.get("/api/health/budget").status_code == 401

    def test_it_lists_what_each_site_used_and_what_waits(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        factory.budget = RequestBudget(limit=2)
        factory.budget.take(("mikanani.me",), 1, BudgetUse.POLL)
        factory.budget.take(("mikanani.me",), 1, BudgetUse.BACKFILL)
        with pytest.raises(BudgetExhaustedError):
            factory.budget.take(("mikanani.me",), 5, BudgetUse.SEARCH)
        sign_in(client, DECKHAND)

        body = client.get("/api/health/budget").json()

        assert body["limit"] == 2
        assert body["window_seconds"] == 3600
        (site,) = body["sites"]
        assert site["site"] == "mikanani.me"
        assert site["used"] == 2
        assert site["by_use"] == [
            {"use": "poll", "count": 1},
            {"use": "backfill", "count": 1},
        ]
        (waiting,) = site["deferred"]
        assert waiting["use"] == "search"
        assert waiting["refused"] == 5
        # 五個比整份預算（2）還多：永遠放不下，不說一個到不了的時間。
        assert waiting["until"] is None
