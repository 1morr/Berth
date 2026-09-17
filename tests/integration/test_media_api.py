"""Media 端點（plan §6 media 群組、票 04 與 04b 驗收）。

命令本身在 `test_media.py`；這裡驗的是形狀與「誰進得來」——`/api/media/*` 沒有在門禁的
白名單上，所以匿名一律 401，而詳情**不是**管理動作，一般使用者也看得了（brief §11）。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

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
from tests.conftest import TMDB_API_KEY
from tests.integration.arrange import arrange, bundled_libraries, factory_for, fake_jellyfin
from tests.integration.factories import FakeClientFactory
from tests.integration.test_media import MOANA as MOANA_DETAIL
from tests.integration.test_media import MOANA_ID, ORDERING, SEASONS, SPY, SPY_ID

BROWSER = {CSRF_HEADER: "XMLHttpRequest"}
ADMIN = {"username": "skipper", "password": "harbour"}
CREW = {"username": "deckhand", "password": "rope"}

#: 探索牆上的同一部作品：搜尋回它，卡片上的 `id` 就是詳情頁那一頁的網址（票 04）。
SPY_ON_THE_WALL = TmdbEntry(
    tmdb_id=SPY.tmdb_id,
    kind=SPY.kind,
    title=SPY.title,
    original_title=SPY.original_title,
    year=SPY.year,
    poster_path=SPY.poster_path,
)


@pytest.fixture
def factory(roots: dict[str, Path]) -> FakeClientFactory:
    return factory_for(
        roots,
        jellyfin=fake_jellyfin(
            bundled_libraries(roots["library"]),
            admin=(ADMIN["username"], ADMIN["password"]),
            users={CREW["username"]: CREW["password"]},
        ),
        tmdb=FakeTmdbClient(
            details=[SPY, MOANA_DETAIL],
            seasons=SEASONS,
            ordering=ORDERING,
            search={"spy x family": [SPY_ON_THE_WALL]},
            translations={120089: "SPY×FAMILY 間諜家家酒"},
            overview_translations={120089: "互相隱藏了真實身份的新家庭。"},
        ),
    )


@pytest.fixture
def client(
    config: Config, tmp_path: Path, roots: dict[str, Path], factory: FakeClientFactory
) -> Iterator[TestClient]:
    """精靈跑完、憑證存好、三條 Route 都在的一台 Berth。"""
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app) as running:
        _seed(running, roots, factory)
        yield running


def _seed(client: TestClient, roots: dict[str, Path], factory: FakeClientFactory) -> None:
    """精靈跑完（含第 6 步的憑證）、三條 Route 都在。"""

    async def run() -> None:
        # `TestClient.app` 是 Starlette 的 `ASGIApp`，型別上沒有 `state`（實際是 FastAPI）。
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            await arrange(session, roots)
            await write_settings(
                session,
                TmdbSettings(api_key=TMDB_API_KEY, image_base_url="https://image.tmdb.org/t/p/"),
            )
            await session.commit()
            await build_routes(session, factory, ())
            await complete_setup(session)

    asyncio.run(run())


def sign_in(client: TestClient, who: dict[str, str] = ADMIN) -> httpx.Response:
    response: httpx.Response = client.post("/api/auth/login", json=who, headers=BROWSER)
    return response


class TestGate:
    def test_media_needs_a_session(self, client: TestClient) -> None:
        assert client.get(f"/api/media/{SPY_ID}").status_code == 401
        assert client.post(f"/api/media/{SPY_ID}/refresh", headers=BROWSER).status_code == 401

    def test_an_ordinary_user_may_browse_a_title(self, client: TestClient) -> None:
        """送單是一般使用者的動作（brief §11），瀏覽詳情是它的前一步。"""
        sign_in(client, CREW)

        assert client.get(f"/api/media/{SPY_ID}").status_code == 200

    def test_there_is_no_track_endpoint(self, client: TestClient) -> None:
        """「追蹤」不是一個動作（票 04b）：`tracked` 是推導出來的（票 09 起以 Job 推）。"""
        sign_in(client)

        assert client.post(f"/api/media/{SPY_ID}/track", json={}, headers=BROWSER).status_code == (
            404
        )


class TestDetail:
    def test_it_returns_the_seasons_and_the_episodes(self, client: TestClient) -> None:
        sign_in(client)

        body = client.get(f"/api/media/{SPY_ID}").json()

        assert (body["id"], body["kind"], body["tmdb_id"]) == (SPY_ID, "tv", 120089)
        assert (body["title"], body["title_en"]) == ("SPY×FAMILY 間諜家家酒", "SPY x FAMILY")
        # 兩種語言都送：UI 換語言時當場換掉，不必重抓（brief §7.5）。
        assert (body["overview"], body["overview_en"]) == (
            "互相隱藏了真實身份的新家庭。",
            SPY.overview,
        )
        assert body["folder_name"] == "SPY x FAMILY (2022) [tmdbid-120089]"
        assert body["problem"] is None
        assert [row["season_number"] for row in body["seasons"]] == [0, 1, 2]
        assert body["seasons"][1]["episodes"][0] == {
            "episode_number": 1,
            "name": "OPERATION STRIX",
            "air_date": "2022-04-09",
            "runtime": 25,
            "absolute_number": 1,
            # 播出了，媒體庫裡沒有，也沒有任何一筆 Job 衝著它來（票 13）。
            "status": "missing",
        }
        assert (body["files"], body["unmatched"], body["versions"]) == ([], [], [])

    def test_a_film_carries_a_runtime_and_no_seasons(self, client: TestClient) -> None:
        sign_in(client)

        body = client.get(f"/api/media/{MOANA_ID}").json()

        assert (body["kind"], body["runtime"], body["seasons"]) == ("movie", 100, [])

    def test_it_only_offers_routes_that_fit(self, client: TestClient) -> None:
        """套件內的三條 Route 裡，劇集只配得上 TV 與 Anime 那兩條。"""
        sign_in(client)

        body = client.get(f"/api/media/{SPY_ID}").json()

        assert [row["collection_type"] for row in body["routes"]] == ["tvshows", "tvshows"]
        assert [row["slug"] for row in client.get(f"/api/media/{MOANA_ID}").json()["routes"]] == (
            ["movies"]
        )

    def test_an_unknown_id_is_a_problem_not_a_crash(self, client: TestClient) -> None:
        """`/media/nonsense` 是網址打錯，回的是可行動的理由而不是 500。"""
        sign_in(client)

        body = client.get("/api/media/nonsense").json()

        assert body["problem"] == "not_found"


class TestRefresh:
    def test_the_folder_name_follows_the_title(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        """TMDB 改了標題，「將會是」的那一串字就跟著改（票 04b 驗收）。

        凍結在第一次送單成功那一刻（票 09），不在這裡。
        """
        sign_in(client)
        client.get(f"/api/media/{SPY_ID}")
        factory.tmdb_.details[(MediaKind.TV, 120089)] = replace(SPY, title="Renamed On TMDB")

        body = client.post(f"/api/media/{SPY_ID}/refresh", headers=BROWSER).json()

        assert body["title_en"] == "Renamed On TMDB"
        assert body["folder_name"] == "Renamed On TMDB (2022) [tmdbid-120089]"
