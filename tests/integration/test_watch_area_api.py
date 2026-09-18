"""Media 詳情的觀看區（`GET /api/media/{id}/watch`、`GET /api/jellyfin/shows/{id}/episodes`，
M1.5 票 08）。

閘門本身（找作品不帶 `parentId`、確認之前不問這部劇的 NextUp）在 `test_jellyfin_access.py`；
這裡驗的是**從 HTTP 那一端看起來的樣子**：看得到的作品有觀看區、主按鈕那一集、季與集的劇照；
**看不到的作品回應裡沒有任何 Jellyfin 的東西**——沒有 item id、沒有圖、沒有觀看狀態——而且這部
作品的 NextUp 從頭到尾沒被問過。替身 Jellyfin 照真的那一台的規矩：帶 `seriesId` 的 NextUp 不看權限
（研究 §2），所以沒被問就是 Berth 擋的。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from berth.adapters.http import NotFoundError, ServiceUnavailableError
from berth.adapters.jellyfin import (
    ITEM_EPISODE,
    ITEM_MOVIE,
    ITEM_SEASON,
    ITEM_SERIES,
    JellyfinItem,
    JellyfinSeason,
)
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.api.deps import get_client_factory
from berth.config import Config
from berth.main import create_app
from berth.services.routes import build_routes
from berth.services.setup import complete_setup
from tests.integration.arrange import arrange, bundled_libraries, factory_for, fake_jellyfin
from tests.integration.factories import FakeClientFactory
from tests.integration.test_inventory_api import ADMIN, CREW, jellyfin_id, sign_in

#: The Bear（TV）：一季三集，第一集看過、第二集有劇照。Jellyfin 的 id 都是 32 個十六進位字元。
BEAR = "0b1a2c3d4e5f60718293a4b5c6d7e8f9"
BEAR_S01 = "1c2b3a4d5e6f708192a3b4c5d6e7f8a9"
BEAR_EPISODES = (
    "2d3c4b5a6f7e8091a2b3c4d5e6f7a8b9",
    "3e4d5c6b7a8f9001b2c3d4e5f6a7b8c9",
    "4f5e6d7c8b9a0011c2d3e4f5a6b7c8d9",
)
STILL = "5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d"
#: Oppenheimer（Movies），`deckhand` 看到 42%。
OPPENHEIMER = "6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e"
#: Frieren 在 Anime：`deckhand` 看不到，`skipper` 看得到。
FRIEREN = "7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f"
FRIEREN_S01 = "8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a"
FRIEREN_E01 = "9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b"


@pytest.fixture
def jellyfin(roots: dict[str, Path]) -> FakeJellyfinClient:
    fake = fake_jellyfin(
        bundled_libraries(roots["library"]),
        admin=(ADMIN["username"], ADMIN["password"]),
        users={CREW["username"]: CREW["password"]},
        folders={CREW["username"]: ("item-0", "item-1")},
    )
    movies, tv, anime = (library.locations[0] for library in fake.libraries_)
    bear = f"{tv}/The Bear (2022) [tmdbid-136315]"
    frieren = f"{anime}/Frieren (2023) [tmdbid-209867]"
    fake.items_ = [
        JellyfinItem(BEAR, ITEM_SERIES, "The Bear", bear, "136315"),
        JellyfinItem(
            BEAR_S01, ITEM_SEASON, "Season 1", f"{bear}/Season 01", "", series_id=BEAR, season=1
        ),
        *(
            JellyfinItem(
                episode,
                ITEM_EPISODE,
                f"Episode {number}",
                f"{bear}/Season 01/S01E0{number}.mkv",
                "",
                series_id=BEAR,
                season_id=BEAR_S01,
                season=1,
                episode_start=number,
                primary_tag=STILL if number == 2 else "",
            )
            for number, episode in enumerate(BEAR_EPISODES, start=1)
        ),
        JellyfinItem(
            OPPENHEIMER, ITEM_MOVIE, "Oppenheimer", f"{movies}/Oppenheimer (2023).mkv", "872585"
        ),
        JellyfinItem(FRIEREN, ITEM_SERIES, "Frieren", frieren, "209867"),
        JellyfinItem(
            FRIEREN_S01, ITEM_SEASON, "Season 1", f"{frieren}/S1", "", series_id=FRIEREN, season=1
        ),
        JellyfinItem(
            FRIEREN_E01,
            ITEM_EPISODE,
            "Episode 1",
            f"{frieren}/S1/S01E01.mkv",
            "",
            series_id=FRIEREN,
            season_id=FRIEREN_S01,
            season=1,
            episode_start=1,
        ),
    ]
    fake.played = {CREW["username"]: {BEAR_EPISODES[0]}}
    fake.positions = {CREW["username"]: {OPPENHEIMER: 42.0}}
    return fake


@pytest.fixture
def factory(roots: dict[str, Path], jellyfin: FakeJellyfinClient) -> FakeClientFactory:
    return factory_for(roots, jellyfin=jellyfin)


@pytest.fixture
def client(
    config: Config, tmp_path: Path, roots: dict[str, Path], factory: FakeClientFactory
) -> Iterator[TestClient]:
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app) as running:

        async def seed() -> None:
            sessions = running.app.state.session_factory  # type: ignore[attr-defined]  # Starlette 的型別
            async with sessions() as session:
                await arrange(session, roots)
                await build_routes(session, factory, ())
                await complete_setup(session)

        asyncio.run(seed())
        yield running


def episodes_of(series: str, season: str) -> str:
    return f"/api/jellyfin/shows/{series}/episodes?season_id={season}"


class TestWatchArea:
    def test_a_show_this_user_sees_carries_on_where_they_left_off(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        sign_in(client, CREW)

        response = client.get("/api/media/tv:136315/watch")

        assert response.status_code == 200
        area = response.json()
        assert (area["item_id"], area["kind"]) == (BEAR, "tv")
        assert area["watch"] == {"played": False, "progress": None, "unplayed_episodes": 2}
        assert area["seasons"] == [{"id": BEAR_S01, "name": "Season 1", "number": 1}]
        carry_on = area["carry_on"]
        assert (carry_on["item_id"], carry_on["season"], carry_on["episode_start"]) == (
            BEAR_EPISODES[1],
            1,
            2,
        )
        assert carry_on["still_url"] == (
            f"/api/jellyfin/items/{BEAR_EPISODES[1]}/images/Primary?size=wide&tag={STILL}"
        )
        # 套件內的 Jellyfin：深連結開在瀏覽器的主機名 + 8096。
        assert area["jellyfin"] == {"public_url": "", "url": "", "port": 8096}
        me = jellyfin_id(client, CREW)
        assert jellyfin.watch_area_queries[:2] == [
            ("tmdb_index", me, ITEM_SERIES),
            ("item", me, BEAR),
        ]
        assert sorted(jellyfin.watch_area_queries[2:]) == [
            ("seasons", me, BEAR),
            ("series_next_up", me, BEAR),
        ]

    def test_a_film_says_how_far_in_and_has_no_seasons(self, client: TestClient) -> None:
        sign_in(client, CREW)

        area = client.get("/api/media/movie:872585/watch").json()

        assert (area["item_id"], area["kind"]) == (OPPENHEIMER, "movie")
        assert area["watch"] == {"played": False, "progress": 42, "unplayed_episodes": None}
        assert (area["carry_on"], area["seasons"]) == (None, [])

    def test_a_title_that_is_not_in_jellyfin_has_no_watch_area(self, client: TestClient) -> None:
        sign_in(client, CREW)

        response = client.get("/api/media/tv:95396/watch")

        assert response.status_code == 200
        assert response.json() is None

    def test_a_title_only_in_a_library_this_user_cannot_see_leaks_nothing(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        """看不到與不在 Jellyfin 是同一個答案（`null`）：沒有 item id、沒有圖、沒有觀看狀態，
        詳情頁的那一份也沒有。這部劇從沒被確認過，所以它的 NextUp 一次都沒問——替身不替 Berth
        擋那一支。"""
        sign_in(client, CREW)

        watch = client.get("/api/media/tv:209867/watch")
        media = client.get("/api/media/tv:209867")

        assert watch.status_code == 200
        assert watch.json() is None
        for body in (watch.text, media.text):
            for jellyfin_owned in (FRIEREN, FRIEREN_S01, FRIEREN_E01, "/api/jellyfin/"):
                assert jellyfin_owned not in body
        asked = {(query, target) for query, _, target in jellyfin.watch_area_queries}
        assert ("series_next_up", FRIEREN) not in asked
        assert ("item", FRIEREN) not in asked
        assert ("seasons", FRIEREN) not in asked

    def test_the_same_title_has_a_watch_area_for_someone_who_can_see_it(
        self, client: TestClient
    ) -> None:
        sign_in(client, ADMIN)

        area = client.get("/api/media/tv:209867/watch").json()

        assert area["item_id"] == FRIEREN
        assert area["carry_on"]["item_id"] == FRIEREN_E01

    def test_a_malformed_media_id_has_no_watch_area(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        sign_in(client, CREW)

        assert client.get("/api/media/nonsense/watch").json() is None
        assert jellyfin.watch_area_queries == []

    def test_a_title_taken_away_between_two_questions_is_not_there(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        """找作品、確認之後，問季的那一下 Jellyfin 回 404（權限剛好被收回、劇被刪了）：與一開始
        就看不到是同一個答案，不是 500。"""
        sign_in(client, CREW)

        async def gone(*, user_id: str, series_id: str) -> tuple[JellyfinSeason, ...]:
            raise NotFoundError(f"GET /Shows/{series_id}/Seasons: 404")

        # 只替換這一支，其餘照替身的規矩。
        jellyfin.seasons = gone  # type: ignore[method-assign]  # 測試替身上的單點換掉

        response = client.get("/api/media/tv:136315/watch")

        assert response.status_code == 200
        assert response.json() is None

    def test_signed_out_is_refused_before_jellyfin_is_asked(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        assert client.get("/api/media/tv:136315/watch").status_code == 401
        assert client.get(episodes_of(BEAR, BEAR_S01)).status_code == 401
        assert jellyfin.watch_area_queries == []

    def test_a_disabled_account_is_signed_out(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        sign_in(client, CREW)
        jellyfin.disabled.add(CREW["username"])

        ended = client.get("/api/media/tv:136315/watch")

        assert ended.status_code == 401
        assert ended.json()["detail"]["reason"] == "account_disabled"
        assert jellyfin.watch_area_queries == []

    def test_jellyfin_not_answering_says_so_with_its_own_words(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        sign_in(client, CREW)
        jellyfin.error = ServiceUnavailableError("GET /UserViews: connection refused")

        for path in ("/api/media/tv:136315/watch", episodes_of(BEAR, BEAR_S01)):
            response = client.get(path)
            assert response.status_code == 503
            assert response.json()["detail"] == {
                "reason": "jellyfin_unreachable",
                "detail": "GET /UserViews: connection refused",
            }


class TestEpisodes:
    def test_a_season_has_its_episodes_with_stills_and_this_users_record(
        self, client: TestClient
    ) -> None:
        sign_in(client, CREW)

        response = client.get(episodes_of(BEAR, BEAR_S01))

        assert response.status_code == 200
        rows = response.json()
        assert [(row["item_id"], row["episode_start"]) for row in rows] == [
            (episode, number) for number, episode in enumerate(BEAR_EPISODES, start=1)
        ]
        assert [row["watch"]["played"] for row in rows] == [True, False, False]
        # 只有第二集有自己的劇照；其餘不借劇的圖（shape §5）。
        assert [bool(row["still_url"]) for row in rows] == [False, True, False]

    def test_a_show_this_user_cannot_see_is_refused(self, client: TestClient) -> None:
        sign_in(client, CREW)

        response = client.get(episodes_of(FRIEREN, FRIEREN_S01))

        assert response.status_code == 404
        assert response.json()["detail"]["reason"] == "item_not_visible"
        assert FRIEREN_E01 not in response.text

    def test_ids_that_are_not_jellyfin_ids_are_not_forwarded(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        sign_in(client, CREW)

        assert client.get(episodes_of("..", BEAR_S01)).status_code in (404, 422)
        assert client.get(episodes_of(BEAR, "not-a-season")).status_code == 422
        assert ("episodes", jellyfin_id(client, CREW), "not-a-season") not in {
            (query, who, target) for query, who, target in jellyfin.watch_area_queries
        }
