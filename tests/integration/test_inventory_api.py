"""媒體庫與 Jellyfin 對外網址的端點（plan §6、票 13、M1.5 票 03）。

判定規則在 `test_inventory.py`，閘門本身在 `test_jellyfin_access.py`；這裡驗的是形狀、誰進得來，
以及**權限從 HTTP 那一端看起來的樣子**：前端塞進來的 `userId` 不起作用、不在允許清單的媒體庫被拒而且
沒有轉發給 Jellyfin、帳號被停用之後 session 結束而下一個請求是 401。對外網址是設定，只有 admin
改得了，規則在門禁（`/api/settings/*`）。

牆上的海報由 Berth 代理 Jellyfin 的圖（`/api/jellyfin/items/{id}/images/{type}`，M1.5 票 04）：
卡片帶的網址真的打得回那一張圖、它是 `/api` 底下唯一可以長期快取的回應、白名單以外的類型
與尺寸不轉發。

標記已看 / 未看（`POST` / `DELETE /api/jellyfin/items/{id}/played`，M1.5 票 05）是 M1.5 第一條寫進
Jellyfin 使用者資料的路：寫的是 session 那個人、前端塞的 id 不起作用、看不到的 item 被拒而且
Jellyfin 那一端沒有寫入。
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
from berth.adapters.jellyfin import ITEM_EPISODE, ITEM_SERIES, JellyfinImage, JellyfinItem
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

#: TV 上的 SPY×FAMILY 與它的 Primary 圖。Jellyfin 的 item id 與 `ImageTags` 都是 32 個十六進位字元。
SPY = "5d2c1a0b9e8f7d6c5b4a39281706f5e4"
SPY_POSTER = "f99664090dfd3223c18e80663440deac"
#: SPY×FAMILY 的兩集，與 `deckhand` 看不到的 Anime 上那部劇。
SPY_EPISODES = ("0e3a2f5b1c9d4e7f8a6b5c4d3e2f1a0b", "1f4b3a6c2d0e5f8a9b7c6d5e4f3a2b1c")
FRIEREN = "8836e6e2b1400442080287739a22c85d"
POSTER = JellyfinImage(content=b"RIFF\x00\x00\x00\x00WEBPVP8 ", content_type="image/webp")


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
            id=SPY,
            type=ITEM_SERIES,
            name="SPY×FAMILY",
            path=f"{tv}/SPY x FAMILY (2022) [tmdbid-120089]",
            tmdb_id="120089",
            year=2022,
            primary_tag=SPY_POSTER,
        ),
        JellyfinItem(
            id="hotel", type=ITEM_SERIES, name="Hotel Show", path=f"{tv}/Hotel Show", tmdb_id=""
        ),
        *(
            JellyfinItem(
                id=episode,
                type=ITEM_EPISODE,
                name=f"Episode {number}",
                path=f"{tv}/SPY x FAMILY (2022) [tmdbid-120089]/Season 01/S01E0{number}.mkv",
                tmdb_id="",
                series_id=SPY,
            )
            for number, episode in enumerate(SPY_EPISODES, start=1)
        ),
        JellyfinItem(
            id=FRIEREN,
            type=ITEM_SERIES,
            name="Frieren",
            path=f"{anime}/Frieren (2023) [tmdbid-209867]",
            tmdb_id="209867",
        ),
    ]
    fake.images = {(SPY, "Primary"): POSTER}
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
            "poster_url": f"/api/jellyfin/items/{SPY}/images/Primary?size=poster&tag={SPY_POSTER}",
            "presence": "found",
            "jellyfin_item_id": SPY,
            "tracking": tracking,
        }
        # 管理員一集都沒看過；Berth 那一份清單不帶觀看紀錄（`test_inventory.py`）。
        unwatched = {"played": False, "progress": None, "unplayed_episodes": 2}
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
                "watch": {"played": False, "progress": None, "unplayed_episodes": None},
            },
            {**spy, "watch": unwatched},
        ]
        assert body["tracked"] == [{**spy, "watch": None}]

    def test_a_page_number_below_one_is_refused(self, client: TestClient) -> None:
        sign_in(client)

        assert client.get(f"/api/inventory/{TV}", params={"page": 0}).status_code == 422


PLAYED = f"/api/jellyfin/items/{SPY}/played"


class TestWatchState:
    def test_marking_a_series_played_writes_this_users_record_of_every_episode(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        sign_in(client, CREW)

        response = client.post(PLAYED, headers=BROWSER)

        assert response.status_code == 200
        assert response.json() == {"played": True, "progress": None, "unplayed_episodes": None}
        assert jellyfin.played_queries == [(jellyfin_id(client, CREW), SPY, True)]
        assert jellyfin.played == {CREW["username"]: set(SPY_EPISODES)}

    def test_marking_unplayed_clears_it_and_the_wall_says_so(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        jellyfin.played = {
            CREW["username"]: set(SPY_EPISODES),
            ADMIN["username"]: {SPY_EPISODES[0]},
        }
        sign_in(client, CREW)

        response = client.delete(PLAYED, headers=BROWSER)
        [card] = [
            card
            for card in client.get(f"/api/inventory/{TV}").json()["titles"]
            if card["jellyfin_item_id"] == SPY
        ]

        expected = {"played": False, "progress": None, "unplayed_episodes": 2}
        assert (response.status_code, response.json()) == (200, expected)
        assert card["watch"] == expected
        assert jellyfin.played == {CREW["username"]: set(), ADMIN["username"]: {SPY_EPISODES[0]}}

    def test_a_user_id_slipped_into_the_request_changes_nothing(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        sign_in(client, ADMIN)
        sign_in(client, CREW)
        crew, admin = jellyfin_id(client, CREW), jellyfin_id(client, ADMIN)
        smuggled = {"userId": admin, "user_id": admin, "UserId": admin}

        response = client.post(PLAYED, params=smuggled, json=smuggled, headers=BROWSER)

        assert response.status_code == 200
        assert jellyfin.played_queries == [(crew, SPY, True)]
        assert ADMIN["username"] not in jellyfin.played

    @pytest.mark.parametrize("method", ["POST", "DELETE"])
    def test_an_item_this_user_cannot_see_is_refused_and_nothing_is_written(
        self, client: TestClient, jellyfin: FakeJellyfinClient, method: str
    ) -> None:
        jellyfin.played = {ADMIN["username"]: {FRIEREN}}
        sign_in(client, CREW)

        response = client.request(method, f"/api/jellyfin/items/{FRIEREN}/played", headers=BROWSER)

        # 看不到與沒有這個 item 是同一個回應。
        assert response.status_code == 404
        assert response.json()["detail"]["reason"] == "item_not_visible"
        assert jellyfin.played == {ADMIN["username"]: {FRIEREN}}

    def test_signed_out_or_without_the_csrf_header_is_refused_before_jellyfin_is_asked(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        assert client.post(PLAYED, headers=BROWSER).status_code == 401
        sign_in(client, CREW)
        assert client.post(PLAYED).status_code == 403
        assert client.delete(PLAYED).status_code == 403

        assert jellyfin.played_queries == []

    @pytest.mark.parametrize(
        "path",
        [
            pytest.param("/api/jellyfin/items/spy/played", id="item-shape"),
            pytest.param("/api/jellyfin/items/%2E%2E/played", id="item-dot-dot"),
        ],
    )
    def test_only_jellyfin_shaped_ids_are_forwarded(
        self, client: TestClient, jellyfin: FakeJellyfinClient, path: str
    ) -> None:
        sign_in(client, CREW)

        assert client.post(path, headers=BROWSER).status_code == 422
        assert jellyfin.played_queries == []

    def test_a_disabled_account_is_signed_out_and_nothing_is_written(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        sign_in(client, CREW)
        jellyfin.disabled.add(CREW["username"])

        response = client.post(PLAYED, headers=BROWSER)

        assert response.status_code == 401
        assert response.json()["detail"]["reason"] == "account_disabled"
        assert jellyfin.played_queries == []
        assert client.get("/api/auth/me").status_code == 401

    def test_jellyfin_not_answering_says_so_with_its_own_words(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        sign_in(client, CREW)
        jellyfin.error = ServiceUnavailableError("GET /UserViews: connection refused")

        response = client.delete(PLAYED, headers=BROWSER)

        assert response.status_code == 503
        assert response.json()["detail"] == {
            "reason": "jellyfin_unreachable",
            "detail": "GET /UserViews: connection refused",
        }


IMAGE = f"/api/jellyfin/items/{SPY}/images/Primary"
POSTER_QUERY = {"size": "poster", "tag": SPY_POSTER}


class TestImages:
    def test_the_poster_on_a_wall_card_is_served_through_berth(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        sign_in(client, CREW)
        put_on_the_wall(client)
        body = client.get(f"/api/inventory/{TV}").json()
        [url] = [card["poster_url"] for card in body["titles"] if card["jellyfin_item_id"] == SPY]

        response = client.get(url)

        assert response.status_code == 200
        assert response.content == POSTER.content
        assert response.headers["content-type"] == "image/webp"
        # `poster` 翻成 Jellyfin 的 2:3、342 寬：與同一面牆上 TMDB 的 `w342` 海報同寬。
        # **這幾個數字（與 adapter 的 `format=Webp`）不在網址裡**，而瀏覽器把網址快取一年、
        # `immutable`：改了它們就要換 `ImageSize` 的值，看過的瀏覽器才會拿到新圖。
        assert jellyfin.image_queries == [(SPY, "Primary", SPY_POSTER, 342, 513, 90)]

    def test_a_poster_is_cached_for_good_and_everything_else_is_not(
        self, client: TestClient
    ) -> None:
        """網址帶著 `ImageTags`，換圖時網址就變，所以圖可以長期快取；
        其餘 `/api` 仍是 `no-store`。"""
        sign_in(client)

        image = client.get(IMAGE, params=POSTER_QUERY)
        wall = client.get(f"/api/inventory/{TV}")

        assert image.headers["cache-control"] == "private, max-age=31536000, immutable"
        assert wall.headers["cache-control"] == "no-store"

    def test_an_svg_from_jellyfin_cannot_run_script_on_berths_origin(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        """圖是 Jellyfin 那一端的內容（管理員上傳的、metadata 來源給的），卻從 Berth 的網域送出去：
        直接開這個網址時，SVG 裡的 script 會帶著 Berth 的 session 跑。`<img>` 裡本來就不執行。"""
        sign_in(client)
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        jellyfin.images[(SPY, "Primary")] = JellyfinImage(content=svg, content_type="image/svg+xml")

        response = client.get(IMAGE, params=POSTER_QUERY)

        assert response.headers["content-security-policy"] == (
            "default-src 'none'; style-src 'unsafe-inline'; sandbox"
        )
        assert response.headers["x-content-type-options"] == "nosniff"

    def test_jellyfin_is_asked_without_a_key_and_nobody_checks_each_image(
        self, client: TestClient, factory: FakeClientFactory, jellyfin: FakeJellyfinClient
    ) -> None:
        """Jellyfin 的圖匿名可取（研究 §6）：Berth 不為它帶 API key，也不逐張問這個人看不看得到。"""
        sign_in(client, CREW)

        assert client.get(IMAGE, params=POSTER_QUERY).status_code == 200
        assert factory.tokens[-1] == ""
        assert jellyfin.view_queries == jellyfin.policy_queries == []

    def test_signed_out_is_refused_before_jellyfin_is_asked(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        response = client.get(IMAGE, params=POSTER_QUERY)

        assert response.status_code == 401
        assert response.headers["cache-control"] == "no-store"
        assert jellyfin.image_queries == []

    @pytest.mark.parametrize(
        ("path", "params"),
        [
            pytest.param(f"/api/jellyfin/items/{SPY}/images/Backdrop", POSTER_QUERY, id="type"),
            pytest.param(IMAGE, {**POSTER_QUERY, "size": "original"}, id="size"),
            pytest.param(IMAGE, {"tag": SPY_POSTER}, id="no-size"),
            pytest.param(IMAGE, {"size": "poster"}, id="no-tag"),
            pytest.param(IMAGE, {**POSTER_QUERY, "tag": "latest"}, id="tag-shape"),
            pytest.param("/api/jellyfin/items/spy/images/Primary", POSTER_QUERY, id="item-shape"),
            pytest.param(
                "/api/jellyfin/items/%2E%2E/images/Primary", POSTER_QUERY, id="item-dot-dot"
            ),
        ],
    )
    def test_only_listed_types_sizes_and_jellyfin_shaped_ids_are_forwarded(
        self,
        client: TestClient,
        jellyfin: FakeJellyfinClient,
        path: str,
        params: dict[str, str],
    ) -> None:
        """尺寸讓前端任意指定，一個網址就能讓 Jellyfin 重算任意大小的圖；
        item id 會進 Jellyfin 的路徑。"""
        sign_in(client)

        response = client.get(path, params=params)

        assert response.status_code == 422
        assert response.headers["cache-control"] == "no-store"
        assert jellyfin.image_queries == []

    def test_an_image_jellyfin_does_not_have_is_a_404(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        sign_in(client)
        jellyfin.images.clear()

        response = client.get(IMAGE, params=POSTER_QUERY)

        assert response.status_code == 404
        assert response.json()["detail"]["reason"] == "image_missing"
        assert response.headers["cache-control"] == "no-store"

    def test_jellyfin_not_answering_is_a_503_that_is_not_cached(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        sign_in(client)
        jellyfin.error = ServiceUnavailableError(f"GET /Items/{SPY}/Images/Primary: timed out")

        response = client.get(IMAGE, params=POSTER_QUERY)

        assert response.status_code == 503
        assert response.json()["detail"] == {
            "reason": "jellyfin_unreachable",
            "detail": f"GET /Items/{SPY}/Images/Primary: timed out",
        }
        assert response.headers["cache-control"] == "no-store"


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
