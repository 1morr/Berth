"""探索端點（plan §6 discover 群組、票 03 驗收）。

命令本身在 `test_discover.py`；這裡驗的是形狀與「誰進得來」——`/api/discover/*` 沒有
在門禁的白名單上，所以匿名一律 401，前端據此導向 `/login`。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.tmdb import TmdbEntry
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.api.deps import get_client_factory
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.domain import MediaKind
from berth.main import create_app
from berth.models import TmdbSettings
from berth.services.routes import build_routes
from berth.services.settings import write_settings
from berth.services.setup import complete_setup
from tests.integration.arrange import arrange, bundled_libraries, factory_for, fake_jellyfin
from tests.integration.factories import FakeClientFactory

BROWSER = {CSRF_HEADER: "XMLHttpRequest"}
ADMIN = {"username": "skipper", "password": "harbour"}
CREDENTIAL = "00000000000000000000000000000003"

LANTERNS = TmdbEntry(
    tmdb_id=95350,
    kind=MediaKind.TV,
    title="Lanterns",
    original_title="Lanterns",
    year=2026,
    poster_path="/gpC7h43xPMEV3goYMQShfJbTtLq.jpg",
)
MOANA = TmdbEntry(
    tmdb_id=1108427,
    kind=MediaKind.MOVIE,
    title="Moana",
    original_title="Moana",
    year=2026,
    poster_path="/gaet1xQ2nxrG0V1Ep9T20ZMNEIC.jpg",
)


@pytest.fixture
def tmdb() -> FakeTmdbClient:
    return FakeTmdbClient(
        trending={MediaKind.TV: [LANTERNS], MediaKind.MOVIE: [MOANA]},
        popular={MediaKind.TV: [LANTERNS]},
        search={"lanterns": [LANTERNS]},
        translations={95350: "綠燈軍團"},
    )


@pytest.fixture
def factory(roots: dict[str, Path], tmdb: FakeTmdbClient) -> FakeClientFactory:
    return factory_for(
        roots,
        jellyfin=fake_jellyfin(
            bundled_libraries(roots["library"]), admin=(ADMIN["username"], ADMIN["password"])
        ),
        tmdb=tmdb,
    )


@pytest.fixture
def client(
    config: Config, tmp_path: Path, roots: dict[str, Path], factory: FakeClientFactory
) -> Iterator[TestClient]:
    """精靈跑完、憑證存好的一台 Berth。"""
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app) as running:
        _seed(running, roots, factory)
        yield running


def sign_in(client: TestClient) -> httpx.Response:
    response: httpx.Response = client.post("/api/auth/login", json=ADMIN, headers=BROWSER)
    return response


class TestGate:
    def test_discover_needs_a_session(self, client: TestClient) -> None:
        """探索頁在門後：未登入時前端據此導向 `/login`（plan §6、票 07）。"""
        assert client.get("/api/discover/trending").status_code == 401
        assert client.get("/api/discover/popular").status_code == 401
        assert client.get("/api/discover/search", params={"q": "x"}).status_code == 401

    def test_an_ordinary_user_may_browse(self, client: TestClient) -> None:
        """探索不是管理動作。"""
        sign_in(client)

        assert client.get("/api/discover/trending").status_code == 200


class TestTrending:
    def test_it_returns_the_wall(self, client: TestClient) -> None:
        sign_in(client)

        body = client.get("/api/discover/trending").json()

        assert body["items"] == [
            {
                "id": "tv:95350",
                "tmdb_id": 95350,
                "kind": "tv",
                "title": "綠燈軍團",
                "title_en": "Lanterns",
                "year": 2026,
                "poster_url": ("https://image.tmdb.org/t/p/w342/gpC7h43xPMEV3goYMQShfJbTtLq.jpg"),
                "tracked": False,
            },
            {
                "id": "movie:1108427",
                "tmdb_id": 1108427,
                "kind": "movie",
                "title": "Moana",
                "title_en": "Moana",
                "year": 2026,
                "poster_url": ("https://image.tmdb.org/t/p/w342/gaet1xQ2nxrG0V1Ep9T20ZMNEIC.jpg"),
                "tracked": False,
            },
        ]
        assert body["problem"] is None

    def test_popular_answers_the_same_shape(self, client: TestClient) -> None:
        sign_in(client)

        body = client.get("/api/discover/popular").json()

        assert [item["id"] for item in body["items"]] == ["tv:95350"]


class TestSearch:
    def test_it_searches(self, client: TestClient) -> None:
        sign_in(client)

        body = client.get("/api/discover/search", params={"q": "Lanterns"}).json()

        assert [item["id"] for item in body["items"]] == ["tv:95350"]

    def test_a_blank_query_is_an_empty_wall_not_an_error(self, client: TestClient) -> None:
        """搜尋框清空是使用者每天都會做的事，不是 422。"""
        sign_in(client)

        response = client.get("/api/discover/search", params={"q": "  "})

        assert (response.status_code, response.json()["items"]) == (200, [])

    def test_the_query_is_required(self, client: TestClient) -> None:
        sign_in(client)

        assert client.get("/api/discover/search").status_code == 422


class TestProblems:
    def test_a_missing_credential_is_named(self, client: TestClient) -> None:
        """憑證缺失時畫面要指得出下一步（票 03 驗收），所以理由是封閉集合而不是空清單。"""
        sign_in(client)
        _forget_credential(client)

        body = client.get("/api/discover/trending").json()

        assert (body["problem"], body["items"]) == ("credential_missing", [])

    def test_an_unreachable_tmdb_says_so(self, client: TestClient, tmdb: FakeTmdbClient) -> None:
        sign_in(client)
        tmdb.error = ServiceUnavailableError("GET /trending/tv/week: connection refused")

        body = client.get("/api/discover/trending").json()

        assert body["problem"] == "unreachable"
        assert body["detail"] == "GET /trending/tv/week: connection refused"


def _seed(client: TestClient, roots: dict[str, Path], factory: FakeClientFactory) -> None:
    """精靈跑完（含第 6 步的憑證）、三條 Route 都在。"""

    async def run() -> None:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            await arrange(session, roots)
            await write_settings(
                session,
                TmdbSettings(api_key=CREDENTIAL, image_base_url="https://image.tmdb.org/t/p/"),
            )
            await session.commit()
            await build_routes(session, factory, ())
            await complete_setup(session)

    asyncio.run(run())


def _forget_credential(client: TestClient) -> None:
    """使用者回精靈把 key 清掉了。第 6 步是閘門，但清空之後探索頁得說得出話。"""

    async def run() -> None:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            await write_settings(session, TmdbSettings())
            await session.commit()

    asyncio.run(run())
