"""媒體庫與 Jellyfin 對外網址的端點（plan §6、票 13）。

判定規則在 `test_inventory.py`；這裡驗的是形狀與誰進得來。媒體庫**不是**管理動作——一般使用者
也看得了（brief §11）；對外網址是設定，只有 admin 改得了，規則在門禁（`/api/settings/*`）。
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

from berth.api.deps import get_client_factory
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.main import create_app
from berth.models import Route
from berth.services.routes import build_routes
from berth.services.setup import complete_setup
from tests.integration.arrange import arrange, bundled_libraries, factory_for, fake_jellyfin
from tests.integration.factories import FakeClientFactory
from tests.integration.test_inventory import linked, title

BROWSER = {CSRF_HEADER: "XMLHttpRequest"}
ADMIN = {"username": "skipper", "password": "harbour"}
CREW = {"username": "deckhand", "password": "rope"}


@pytest.fixture
def factory(roots: dict[str, Path]) -> FakeClientFactory:
    return factory_for(
        roots,
        jellyfin=fake_jellyfin(
            bundled_libraries(roots["library"]),
            admin=(ADMIN["username"], ADMIN["password"]),
            users={CREW["username"]: CREW["password"]},
        ),
    )


@pytest.fixture
def client(
    config: Config, tmp_path: Path, roots: dict[str, Path], factory: FakeClientFactory
) -> Iterator[TestClient]:
    """精靈跑完、三條 Route 都在的一台 Berth。套件內的 Jellyfin，所以深連結開在瀏覽器的主機上。"""
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app) as running:

        async def seed() -> None:
            # `TestClient.app` 是 Starlette 的 `ASGIApp`，型別上沒有 `state`（實際是 FastAPI）。
            sessions = running.app.state.session_factory  # type: ignore[attr-defined]
            async with sessions() as session:
                await arrange(session, roots)
                await build_routes(session, factory, ())
                await complete_setup(session)

        asyncio.run(seed())
        yield running


def sign_in(client: TestClient, who: dict[str, str] = ADMIN) -> httpx.Response:
    response: httpx.Response = client.post("/api/auth/login", json=who, headers=BROWSER)
    return response


def put_on_the_wall(client: TestClient) -> None:
    """TV 那一條 Route 上一部入庫了一集、Jellyfin 找到了的劇集。"""

    async def run() -> None:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]  # 同 `client` 那一條
        async with sessions() as session:
            tv = await session.scalar(select(Route).where(Route.slug == "tv"))
            assert tv is not None
            spy = await title(session)
            await linked(session, spy, tv, item="episode-1", series="series-1")

    asyncio.run(run())


class TestGate:
    def test_the_wall_needs_a_session(self, client: TestClient) -> None:
        assert client.get("/api/inventory").status_code == 401
        assert client.get("/api/inventory/tv").status_code == 401

    def test_an_ordinary_user_may_look_at_the_wall(self, client: TestClient) -> None:
        sign_in(client, CREW)

        assert client.get("/api/inventory").status_code == 200
        assert client.get("/api/inventory/tv").status_code == 200

    def test_only_an_admin_may_set_the_jellyfin_address(self, client: TestClient) -> None:
        sign_in(client, CREW)

        response = client.post(
            "/api/settings/jellyfin", json={"public_url": "https://jf.example.com"}, headers=BROWSER
        )

        assert response.status_code == 403


class TestInventory:
    def test_the_route_list_carries_what_the_switcher_needs(self, client: TestClient) -> None:
        sign_in(client)
        put_on_the_wall(client)

        rows = {row["slug"]: row for row in client.get("/api/inventory").json()}

        assert set(rows) == {"movies", "tv", "anime"}
        assert rows["tv"] == {
            "slug": "tv",
            "name": "TV",
            "collection_type": "tvshows",
            "enabled": True,
            "titles": 1,
            "review": 0,
            "unmatched": 0,
        }

    def test_a_wall_carries_its_cards_and_where_jellyfin_lives(self, client: TestClient) -> None:
        sign_in(client)
        put_on_the_wall(client)

        body = client.get("/api/inventory/tv").json()

        assert body["route"]["slug"] == "tv"
        assert body["jellyfin"] == {"public_url": "", "url": "", "port": 8096}
        assert body["items"] == [
            {
                "media_id": "tv:120089",
                "kind": "tv",
                "title": "SPY x FAMILY",
                "title_en": "SPY x FAMILY",
                "year": 2022,
                "poster_url": "https://image.tmdb.org/t/p/w342/120089.jpg",
                "status": "partial",
                "imported": 1,
                "aired": 4,
                "versions": 0,
                "needs_review": False,
                "has_unmatched": False,
                "audits": 0,
                "presence": "found",
                "jellyfin_item_id": "series-1",
            }
        ]

    def test_a_route_that_does_not_exist_is_a_404(self, client: TestClient) -> None:
        sign_in(client)

        assert client.get("/api/inventory/nowhere").status_code == 404


class TestJellyfinAddress:
    def test_a_bundled_jellyfin_is_worked_out_on_the_browsers_host(
        self, client: TestClient
    ) -> None:
        sign_in(client)

        body = client.get("/api/settings/jellyfin").json()

        assert body == {"public_url": "", "url": "", "port": 8096}

    def test_what_the_admin_typed_is_what_comes_back(self, client: TestClient) -> None:
        sign_in(client)

        posted = client.post(
            "/api/settings/jellyfin",
            json={"public_url": "https://jf.example.com/"},
            headers=BROWSER,
        )

        expected = {
            "public_url": "https://jf.example.com",
            "url": "https://jf.example.com",
            "port": None,
        }
        assert posted.json() == expected
        assert client.get("/api/settings/jellyfin").json() == expected

    def test_an_address_that_is_not_http_is_refused_with_the_reason(
        self, client: TestClient
    ) -> None:
        sign_in(client)

        response = client.post(
            "/api/settings/jellyfin", json={"public_url": "jf.example.com"}, headers=BROWSER
        )

        assert response.status_code == 422
        assert "http" in response.json()["detail"]
