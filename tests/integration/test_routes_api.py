"""`/api/routes` 與 `/api/jellyfin/libraries`（plan §6 routes 群組、票 14）。

命令本身的規則在 `test_routes.py`；這裡驗的是形狀、每種拒絕理由對到哪個狀態碼，以及誰進得來。
誰進得來的規則在門禁（`api/gate.py`），不在 router 的相依：精靈跑完之前與 `setup/*` 一樣匿名
開放——精靈第 7 步的「刪除」打的就是這一支——跑完之後只有管理員。
"""

from __future__ import annotations

import asyncio
import errno
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from berth.api.deps import get_client_factory
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.domain import JobTrigger
from berth.main import create_app
from berth.models import Job
from berth.services.routes import build_routes
from berth.services.setup import complete_setup
from tests.integration.arrange import arrange, factory_for, fake_jellyfin, with_second_disk
from tests.integration.factories import FakeClientFactory

BROWSER = {CSRF_HEADER: "XMLHttpRequest"}
ADMIN = {"username": "skipper", "password": "harbour"}
DECKHAND = {"username": "deckhand", "password": "rope"}


@pytest.fixture
def factory(roots: dict[str, Path]) -> FakeClientFactory:
    """同一台假 Jellyfin 既報媒體庫，也是登入的身分來源（brief §11）。TV 掛了兩顆碟。"""
    libraries, _ = with_second_disk(roots)
    return factory_for(
        roots,
        jellyfin=fake_jellyfin(
            libraries,
            admin=(ADMIN["username"], ADMIN["password"]),
            users={DECKHAND["username"]: DECKHAND["password"]},
        ),
    )


@pytest.fixture
def client(
    config: Config, tmp_path: Path, roots: dict[str, Path], factory: FakeClientFactory
) -> Iterator[TestClient]:
    """精靈跑完、三條 Route 綠燈的一台 Berth。"""
    with _running(config, tmp_path, factory) as running:
        _seed(running, roots, factory, complete=True)
        yield running


@pytest.fixture
def wizard(
    config: Config, tmp_path: Path, roots: dict[str, Path], factory: FakeClientFactory
) -> Iterator[TestClient]:
    """停在第 7 步的一台：三條 Route 建好了，精靈還沒按完成。"""
    with _running(config, tmp_path, factory) as running:
        _seed(running, roots, factory, complete=False)
        yield running


@pytest.fixture
def cross_device_link(monkeypatch: pytest.MonkeyPatch) -> None:
    """`link()` 回 `EXDEV`：這一刻起新的檢查的硬鏈接那一條一定紅。"""

    def refuse(source: object, target: object) -> None:
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(os, "link", refuse)


def sign_in(client: TestClient, credentials: dict[str, str]) -> None:
    assert client.post("/api/auth/login", json=credentials).status_code == 200


def routes(client: TestClient) -> dict[str, dict[str, Any]]:
    """`GET /api/routes`，以 slug 為鍵。"""
    # Any：這是剛解析出來的 JSON，形狀由被測的端點決定，斷言本身才是型別檢查。
    rows: list[dict[str, Any]] = client.get("/api/routes").json()
    return {str(row["route"]["slug"]): row for row in rows}


def route_id(client: TestClient, slug: str) -> int:
    return int(routes(client)[slug]["route"]["id"])


def second_route(client: TestClient, disk: Path, **overrides: object) -> dict[str, object]:
    body = {
        "library_id": "item-1",
        "target_path": str(disk),
        "name": "TV 2",
        "profile": "anime",
        **overrides,
    }
    response = client.post("/api/routes", json=body)
    assert response.status_code == 200, response.text
    created: dict[str, object] = response.json()
    return created


class TestWhoGetsIn:
    def test_an_administrator_lists_every_route_with_what_refers_to_it(
        self, client: TestClient
    ) -> None:
        sign_in(client, ADMIN)

        rows = routes(client)

        assert list(rows) == ["movies", "tv", "anime"]
        assert (rows["tv"]["jobs"], rows["tv"]["ledger_entries"], rows["tv"]["in_use"]) == (
            0,
            0,
            False,
        )

    def test_an_ordinary_user_is_refused(self, client: TestClient) -> None:
        """`/settings/routes` 只有 admin（票 14 驗收）：後端同樣回 403，不靠前端藏按鈕。"""
        sign_in(client, DECKHAND)

        assert client.get("/api/routes").status_code == 403
        assert client.get("/api/jellyfin/libraries").status_code == 403
        assert client.delete("/api/routes/1").status_code == 403

    def test_signed_out_is_401(self, client: TestClient) -> None:
        assert client.get("/api/routes").status_code == 401

    def test_the_rule_holds_for_route_paths_that_no_router_claims(self, client: TestClient) -> None:
        """規則在門禁上，不在 router 的相依上——之後新掛的 routes 端點預設就在門後。"""
        sign_in(client, DECKHAND)

        assert client.get("/api/routes/not-built-yet").status_code == 403

    def test_before_setup_completes_the_wizard_reaches_them_without_a_session(
        self, wizard: TestClient
    ) -> None:
        """精靈跑完之前還沒有人登入得了；第 7 步的「刪除」打的就是這一組。"""
        assert wizard.get("/api/routes").status_code == 200
        assert wizard.get("/api/jellyfin/libraries").status_code == 200
        movies = route_id(wizard, "movies")
        assert wizard.delete(f"/api/routes/{movies}").status_code == 204

    def test_other_jellyfin_paths_do_not_inherit_the_wizard_rule(self, wizard: TestClient) -> None:
        """跟著精靈規則走的只有媒體庫清單那一支：`/jellyfin` 底下之後新掛的端點預設要登入。"""
        assert wizard.get("/api/jellyfin/not-built-yet").status_code == 401


class TestCommands:
    def test_one_library_gets_a_second_route(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        sign_in(client, ADMIN)
        _, disk = with_second_disk(roots)
        tv = next(
            row for row in client.get("/api/jellyfin/libraries").json() if row["name"] == "TV"
        )
        assert tv["taken"] == [str(roots["library"] / "tv")]

        created = second_route(client, disk)

        assert (created["slug"], created["category"], created["profile"]) == (
            "tv-2",
            "berth-tv-2",
            "anime",
        )
        assert (created["health"], created["enabled"]) == ("ok", True)
        assert list(routes(client)) == ["movies", "tv", "anime", "tv-2"]

    def test_an_invalid_choice_is_422_with_a_reason(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        sign_in(client, ADMIN)

        response = client.post(
            "/api/routes",
            json={
                "library_id": "item-1",
                "target_path": "/mnt/elsewhere",
                "name": "TV 2",
                "profile": "standard",
            },
        )

        assert response.status_code == 422
        assert response.json()["detail"]["reason"] == "target_not_in_library"

    def test_enabling_a_route_whose_checks_are_red_is_409(
        self, client: TestClient, roots: dict[str, Path], cross_device_link: None
    ) -> None:
        sign_in(client, ADMIN)
        _, disk = with_second_disk(roots)
        created = second_route(client, disk)
        assert created["enabled"] is False

        response = client.put(
            f"/api/routes/{created['id']}",
            json={"name": "TV 2", "profile": "anime", "enabled": True},
        )

        assert response.status_code == 409
        assert response.json()["detail"]["reason"] == "route_unhealthy"

    def test_a_route_in_use_is_409_and_stays(self, client: TestClient) -> None:
        sign_in(client, ADMIN)
        tv = route_id(client, "tv")
        _add_job(client, tv)

        response = client.delete(f"/api/routes/{tv}")

        assert response.status_code == 409
        assert response.json()["detail"]["reason"] == "route_in_use"
        assert (routes(client)["tv"]["jobs"], routes(client)["tv"]["in_use"]) == (1, True)

    def test_an_unused_route_is_deleted(self, client: TestClient, roots: dict[str, Path]) -> None:
        sign_in(client, ADMIN)
        _, disk = with_second_disk(roots)
        created = second_route(client, disk)

        response = client.delete(f"/api/routes/{created['id']}")

        assert response.status_code == 204
        assert "tv-2" not in routes(client)

    def test_one_route_is_rechecked(self, client: TestClient) -> None:
        sign_in(client, ADMIN)

        response = client.post(f"/api/routes/{route_id(client, 'movies')}/check")

        assert response.status_code == 200
        assert response.json()["health"] == "ok"

    def test_an_unknown_route_is_404(self, client: TestClient) -> None:
        sign_in(client, ADMIN)

        response = client.put(
            "/api/routes/999", json={"name": "x", "profile": "standard", "enabled": True}
        )

        assert response.status_code == 404
        assert response.json()["detail"]["reason"] == "route_missing"


@contextmanager
def _running(config: Config, tmp_path: Path, factory: FakeClientFactory) -> Iterator[TestClient]:
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app, headers=BROWSER) as running:
        yield running


def _seed(
    client: TestClient, roots: dict[str, Path], factory: FakeClientFactory, *, complete: bool
) -> None:
    async def run() -> None:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            libraries, _ = with_second_disk(roots)
            await arrange(session, roots, libraries=libraries)
            await build_routes(session, factory, ())
            if complete:
                await complete_setup(session)

    asyncio.run(run())


def _add_job(client: TestClient, route: int) -> None:
    """一筆送到這條 Route 的下載。送單有自己的測試，這裡只要它存在。"""

    async def run() -> None:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            session.add(
                Job(hash="a" * 40, name="release", trigger=JobTrigger.MANUAL, route_id=route)
            )
            await session.commit()

    asyncio.run(run())
