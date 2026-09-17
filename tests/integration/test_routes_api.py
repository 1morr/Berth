"""`/api/routes` 與 `/api/jellyfin/libraries`（plan §6 routes 群組、票 14）。

命令本身的規則在 `test_routes.py`；這裡驗的是形狀、每種拒絕理由對到哪個狀態碼，以及誰進得來。
誰進得來的規則在門禁（`api/gate.py`），不在 router 的相依：與 `settings/*` 一樣永遠只有管理員
（票 14a）。精靈第 7 步的刪除走自己的 `DELETE /setup/routes/{id}`，跟著 `setup/*` 的規則。
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


def setup_route_id(client: TestClient, slug: str) -> int:
    """精靈那一邊認得的 id（`GET /api/setup/routes`）。精靈跑完之前 `GET /api/routes` 要登入。"""
    # Any：剛解析出來的 JSON，形狀由被測的端點決定。
    rows: list[dict[str, Any]] = client.get("/api/setup/routes").json()["routes"]
    return int(next(row for row in rows if row["slug"] == slug)["id"])


def second_route(client: TestClient, disk: Path, **overrides: object) -> dict[str, object]:
    body = {
        "library_id": "item-1",
        "target_path": str(disk),
        "name": "TV 2",
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

    def test_before_setup_completes_they_still_need_an_administrator(
        self, wizard: TestClient
    ) -> None:
        """票 14a 推翻票 14 的「跟著 `setup/*` 匿名開放」：那樣的話精靈跑完之前，匿名的人可以把
        紅燈 Route 停用、再按完成。精靈要的只有刪除，它有自己的一支。"""
        assert wizard.get("/api/routes").status_code == 401
        assert wizard.get("/api/jellyfin/libraries").status_code == 401
        movies = setup_route_id(wizard, "movies")
        assert (
            wizard.put(
                f"/api/routes/{movies}",
                json={"name": "Movies", "enabled": False},
            ).status_code
            == 401
        )
        assert wizard.delete(f"/api/routes/{movies}").status_code == 401

    def test_before_setup_completes_the_wizard_deletes_through_its_own_endpoint(
        self, wizard: TestClient
    ) -> None:
        """精靈第 7 步的刪除走 `DELETE /setup/routes/{id}`，跟著 `setup/*` 的規則。"""
        movies = setup_route_id(wizard, "movies")

        assert wizard.delete(f"/api/setup/routes/{movies}").status_code == 204
        slugs = [row["slug"] for row in wizard.get("/api/setup/routes").json()["routes"]]
        assert slugs == ["tv", "anime"]

    def test_the_wizard_delete_refuses_the_same_way_as_the_settings_page(
        self, wizard: TestClient
    ) -> None:
        tv = setup_route_id(wizard, "tv")
        _add_job(wizard, tv)

        in_use = wizard.delete(f"/api/setup/routes/{tv}")
        missing = wizard.delete("/api/setup/routes/999")

        assert in_use.status_code == 409
        detail = in_use.json()["detail"]
        assert (detail["reason"], detail["jobs"], detail["ledger_entries"]) == (
            "route_in_use",
            1,
            0,
        )
        assert (missing.status_code, missing.json()["detail"]["reason"]) == (404, "route_missing")

    def test_after_setup_the_wizard_delete_is_for_administrators(self, client: TestClient) -> None:
        sign_in(client, ADMIN)
        movies = route_id(client, "movies")
        sign_in(client, DECKHAND)

        assert client.delete(f"/api/setup/routes/{movies}").status_code == 403
        sign_in(client, ADMIN)
        assert client.delete(f"/api/setup/routes/{movies}").status_code == 204


class TestCommands:
    def test_one_library_gets_a_second_route(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        sign_in(client, ADMIN)
        _, disk = with_second_disk(roots)
        tv = next(
            row for row in client.get("/api/jellyfin/libraries").json() if row["name"] == "TV"
        )
        assert tv["paths"] == [
            {"path": str(roots["library"] / "tv"), "route_name": "TV"},
            {"path": str(disk), "route_name": None},
        ]

        created = second_route(client, disk)

        assert (created["slug"], created["category"]) == ("tv-2", "berth-tv-2")
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
            json={"name": "TV 2", "enabled": True},
        )

        assert response.status_code == 409
        assert response.json()["detail"]["reason"] == "route_unhealthy"

    def test_a_route_in_use_is_409_and_stays(self, client: TestClient) -> None:
        sign_in(client, ADMIN)
        tv = route_id(client, "tv")
        _add_job(client, tv)

        response = client.delete(f"/api/routes/{tv}")

        assert response.status_code == 409
        detail = response.json()["detail"]
        # 數字是結構化的欄位，畫面照它說「1 筆下載、0 個入庫檔案」，不必解析原文（票 14a）。
        assert (detail["reason"], detail["jobs"], detail["ledger_entries"]) == (
            "route_in_use",
            1,
            0,
        )
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

        response = client.put("/api/routes/999", json={"name": "x", "enabled": True})

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
