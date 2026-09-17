"""媒體庫與 Jellyfin 對外網址的端點（plan §6、票 13、M1.5 票 03）。

判定規則在 `test_inventory.py`，閘門本身在 `test_jellyfin_access.py`；這裡驗的是形狀、誰進得來，
以及**權限從 HTTP 那一端看起來的樣子**：前端塞進來的 `userId` 不起作用、不在允許清單的媒體庫被拒而且
沒有轉發給 Jellyfin、帳號被停用之後 session 結束而下一個請求是 401。對外網址是設定，只有 admin
改得了，規則在門禁（`/api/settings/*`）。
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

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.jellyfin import ITEM_SERIES, JellyfinItem
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.api.deps import get_client_factory
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.main import create_app
from berth.models import Route, User
from berth.services.jellyfin_access import ACCESS_TTL_SECONDS, AccessCache
from berth.services.routes import build_routes
from berth.services.setup import complete_setup
from tests.integration.arrange import arrange, bundled_libraries, factory_for, fake_jellyfin
from tests.integration.factories import FakeClientFactory
from tests.integration.test_inventory import linked, title

BROWSER = {CSRF_HEADER: "XMLHttpRequest"}
ADMIN = {"username": "skipper", "password": "harbour"}
CREW = {"username": "deckhand", "password": "rope"}

#: 套件內的三個媒體庫（`arrange.bundled_libraries`）。`deckhand` 看不到 Anime。
MOVIES, TV, ANIME = "item-0", "item-1", "item-2"


@pytest.fixture
def jellyfin(roots: dict[str, Path]) -> FakeJellyfinClient:
    fake = fake_jellyfin(
        bundled_libraries(roots["library"]),
        admin=(ADMIN["username"], ADMIN["password"]),
        users={CREW["username"]: CREW["password"]},
        folders={CREW["username"]: (MOVIES, TV)},
    )
    tv = fake.libraries_[1].locations[0]
    anime = fake.libraries_[2].locations[0]
    fake.items_ = [
        JellyfinItem(
            id="spy",
            type=ITEM_SERIES,
            name="SPY×FAMILY",
            path=f"{tv}/SPY x FAMILY (2022) [tmdbid-120089]",
            tmdb_id="120089",
            year=2022,
        ),
        JellyfinItem(
            id="hotel", type=ITEM_SERIES, name="Hotel Show", path=f"{tv}/Hotel Show", tmdb_id=""
        ),
        JellyfinItem(
            id="frieren",
            type=ITEM_SERIES,
            name="Frieren",
            path=f"{anime}/Frieren (2023) [tmdbid-209867]",
            tmdb_id="209867",
        ),
    ]
    return fake


@pytest.fixture
def factory(roots: dict[str, Path], jellyfin: FakeJellyfinClient) -> FakeClientFactory:
    return factory_for(roots, jellyfin=jellyfin)


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


def jellyfin_id(client: TestClient, who: dict[str, str]) -> str:
    async def run() -> str:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]  # 同 `client` 那一條
        async with sessions() as session:
            user = await session.scalar(select(User).where(User.name == who["username"]))
            assert user is not None
            return str(user.jellyfin_user_id)

    return asyncio.run(run())


def put_on_the_wall(client: TestClient) -> None:
    """TV 那一條 Route 上一部入庫了一集的劇集；Jellyfin 已經掃到它（TMDB id 對得上）。"""

    async def run() -> None:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]  # 同 `client` 那一條
        async with sessions() as session:
            tv = await session.scalar(select(Route).where(Route.slug == "tv"))
            assert tv is not None
            spy = await title(session)
            await linked(session, spy, tv, item="episode-1")

    asyncio.run(run())


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class TestGate:
    def test_the_wall_needs_a_session(self, client: TestClient) -> None:
        assert client.get("/api/inventory").status_code == 401
        assert client.get(f"/api/inventory/{TV}").status_code == 401

    def test_an_ordinary_user_may_look_at_the_wall(self, client: TestClient) -> None:
        sign_in(client, CREW)

        assert client.get("/api/inventory").status_code == 200
        assert client.get(f"/api/inventory/{TV}").status_code == 200

    def test_only_an_admin_may_set_the_jellyfin_address(self, client: TestClient) -> None:
        sign_in(client, CREW)

        response = client.post(
            "/api/settings/jellyfin", json={"public_url": "https://jf.example.com"}, headers=BROWSER
        )

        assert response.status_code == 403


class TestPermissions:
    def test_the_switcher_lists_only_the_libraries_this_user_sees_in_jellyfin(
        self, client: TestClient
    ) -> None:
        sign_in(client, CREW)

        rows = client.get("/api/inventory").json()

        assert [row["id"] for row in rows] == [MOVIES, TV]

    @pytest.mark.parametrize("library", [ANIME, "no-such-library"])
    def test_a_library_off_the_list_is_refused_and_never_forwarded(
        self, client: TestClient, jellyfin: FakeJellyfinClient, library: str
    ) -> None:
        sign_in(client, CREW)

        response = client.get(f"/api/inventory/{library}")

        # 沒有權限與不存在是同一個回應：分得出來就是在告訴人那個媒體庫存在。
        assert response.status_code == 404
        assert response.json()["detail"]["reason"] == "library_not_visible"
        assert library not in {queried for _, queried in jellyfin.browse_queries}

    def test_a_user_id_slipped_into_the_request_changes_nothing(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        """API key 帶誰的 id 就是誰（研究 §2）：id 只從 session 來，前端送什麼都不收。"""
        sign_in(client, ADMIN)
        # 管理員登入過才有 `users` 那一列可以查 id；接著換成一般使用者的 cookie。
        sign_in(client, CREW)
        crew, admin = jellyfin_id(client, CREW), jellyfin_id(client, ADMIN)
        smuggled = {"userId": admin, "user_id": admin, "UserId": admin}

        listed = client.get("/api/inventory", params=smuggled)
        walled = client.get(f"/api/inventory/{TV}", params=smuggled)
        refused = client.get(f"/api/inventory/{ANIME}", params=smuggled)

        assert [row["id"] for row in listed.json()] == [MOVIES, TV]
        assert walled.status_code == 200
        assert refused.status_code == 404
        assert set(jellyfin.view_queries) == set(jellyfin.policy_queries) == {crew}
        assert {user for user, _ in jellyfin.browse_queries} == {crew}

    def test_a_disabled_account_is_signed_out_and_stays_out(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        sign_in(client, CREW)
        jellyfin.disabled.add(CREW["username"])

        ended = client.get("/api/inventory")

        assert ended.status_code == 401
        assert ended.json()["detail"]["reason"] == "account_disabled"
        assert client.get("/api/auth/me").status_code == 401
        assert client.get("/api/jobs").status_code == 401

    def test_disabling_catches_up_once_the_short_cache_runs_out(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        clock = Clock()
        client.app.state.jellyfin_access = AccessCache(clock=clock)  # type: ignore[attr-defined]  # 同 `client` 那一條
        sign_in(client, CREW)
        assert client.get("/api/inventory").status_code == 200

        jellyfin.disabled.add(CREW["username"])
        assert client.get(f"/api/inventory/{TV}").status_code == 200

        clock.now += ACCESS_TTL_SECONDS + 1
        assert client.get(f"/api/inventory/{TV}").status_code == 401
        assert client.get("/api/auth/me").status_code == 401

    def test_jellyfin_not_answering_says_so_with_its_own_words(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        sign_in(client, CREW)
        jellyfin.error = ServiceUnavailableError("GET /UserViews: connection refused")

        for path in ("/api/inventory", f"/api/inventory/{TV}"):
            response = client.get(path)

            assert response.status_code == 503
            assert response.json()["detail"] == {
                "reason": "jellyfin_unreachable",
                "detail": "GET /UserViews: connection refused",
            }


class TestInventory:
    def test_the_switcher_is_the_libraries_by_name_without_browsing_them(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        sign_in(client)
        put_on_the_wall(client)

        rows = client.get("/api/inventory").json()

        assert rows == [
            {"id": MOVIES, "name": "Movies", "collection_type": "movies"},
            {"id": TV, "name": "TV", "collection_type": "tvshows"},
            {"id": ANIME, "name": "Anime", "collection_type": "tvshows"},
        ]
        assert jellyfin.browse_queries == []

    def test_a_wall_carries_jellyfins_page_berths_titles_and_where_jellyfin_lives(
        self, client: TestClient
    ) -> None:
        sign_in(client)
        put_on_the_wall(client)

        body = client.get(f"/api/inventory/{TV}").json()

        assert body["library"] == {"id": TV, "name": "TV", "collection_type": "tvshows"}
        assert body["jellyfin"] == {"public_url": "", "url": "", "port": 8096}
        assert (body["page"], body["page_size"], body["total"]) == (1, 100, 2)
        assert (body["review"], body["unmatched"]) == (0, 0)
        tracking = {
            "status": "partial",
            "imported": 1,
            "aired": 4,
            "versions": 0,
            "needs_review": False,
            "has_unmatched": False,
            "audits": 0,
        }
        spy = {
            "media_id": "tv:120089",
            "kind": "tv",
            "title": "SPY×FAMILY",
            "title_en": "SPY×FAMILY",
            "year": 2022,
            "poster_url": "",
            "presence": "found",
            "jellyfin_item_id": "spy",
            "tracking": tracking,
        }
        assert body["titles"] == [
            {
                "media_id": "",
                "kind": "tv",
                "title": "Hotel Show",
                "title_en": "Hotel Show",
                "year": None,
                "poster_url": "",
                "presence": "found",
                "jellyfin_item_id": "hotel",
                "tracking": None,
            },
            spy,
        ]
        assert body["tracked"] == [spy]

    def test_a_page_number_below_one_is_refused(self, client: TestClient) -> None:
        sign_in(client)

        assert client.get(f"/api/inventory/{TV}", params={"page": 0}).status_code == 422


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
