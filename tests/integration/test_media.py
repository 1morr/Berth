"""Media 詳情、追蹤與快照刷新的命令（plan §2.2、§5、§8.3、brief §7.5、票 04）。

這裡驗的是四件事：**快照怎麼組**（英文那一輪是結構本身，`zh-TW` 只補顯示用標題與簡介）、
**24 小時的快照規則**、**`folder_name` 什麼時候凍結**，以及**拿不到 TMDB 時還剩下什麼**。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import AuthFailedError, ServiceUnavailableError
from berth.adapters.tmdb import TmdbDetail, TmdbEpisode, TmdbSeason, TmdbSeasonEntry
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.domain import CollectionType, MediaKind, Profile, TmdbProblem
from berth.models import Media, Route, TmdbSettings
from berth.services.media import SNAPSHOT_TTL, read_media, refresh_media, track_media
from berth.services.settings import write_settings
from tests.conftest import TMDB_API_KEY
from tests.integration.factories import FakeClientFactory

pytestmark = pytest.mark.asyncio

SPY_ID = "tv:120089"
MOANA_ID = "movie:1241982"

SPY = TmdbDetail(
    tmdb_id=120089,
    kind=MediaKind.TV,
    title="SPY x FAMILY",
    original_title="SPY×FAMILY",
    year=2022,
    first_air_date=date(2022, 4, 9),
    overview="A spy, an assassin and a telepath keep house.",
    poster_path="/3zQ6cM3o6NleaR5NrDvHzeaBmM6.jpg",
    titles=("SPY x FAMILY", "SPY×FAMILY", "间谍过家家"),
    seasons=(
        TmdbSeasonEntry(
            season_number=0, name="Specials", episode_count=3, air_date=date(2023, 7, 28)
        ),
        TmdbSeasonEntry(
            season_number=1, name="Season 1", episode_count=25, air_date=date(2022, 4, 9)
        ),
        TmdbSeasonEntry(
            season_number=2, name="Season 2", episode_count=12, air_date=date(2023, 10, 7)
        ),
    ),
    absolute_group_id="689a2aec017d0bc9ecc6fac8",
)

MOANA = TmdbDetail(
    tmdb_id=1241982,
    kind=MediaKind.MOVIE,
    title="Moana 2",
    original_title="Moana 2",
    year=2024,
    first_air_date=date(2024, 11, 21),
    overview="Moana sails again.",
    poster_path="/aLVkiINlIeCkcZIzb7XHzPYgO6L.jpg",
    runtime=100,
    titles=("Moana 2", "海洋奇緣2"),
)


def episode(season: int, number: int, name: str, day: date, runtime: int = 24) -> TmdbEpisode:
    return TmdbEpisode(
        season_number=season,
        episode_number=number,
        name=name,
        air_date=day,
        runtime=runtime,
    )


SEASONS = {
    120089: [
        TmdbSeason(
            season_number=0,
            name="Specials",
            air_date=date(2023, 7, 28),
            episodes=(episode(0, 1, "MISSION EXTRA", date(2023, 7, 28)),),
        ),
        TmdbSeason(
            season_number=1,
            name="Season 1",
            air_date=date(2022, 4, 9),
            episodes=(
                episode(1, 1, "OPERATION STRIX", date(2022, 4, 9), 25),
                episode(1, 25, "FIRST CONTACT", date(2022, 12, 24)),
            ),
        ),
        TmdbSeason(
            season_number=2,
            name="Season 2",
            air_date=date(2023, 10, 7),
            episodes=(episode(2, 1, "FOLLOW MAMA AND PAPA", date(2023, 10, 7)),),
        ),
    ]
}

#: `tv/episode_group/689a…` 攤平之後的樣子（`(季, 集) → 絕對編號`）。
ORDERING = {"689a2aec017d0bc9ecc6fac8": {(1, 1): 1, (1, 25): 25, (2, 1): 26}}


def tmdb(**kwargs: object) -> FakeTmdbClient:
    defaults: dict[str, object] = {
        "details": [SPY, MOANA],
        "seasons": SEASONS,
        "ordering": ORDERING,
        "translations": {120089: "SPY×FAMILY 間諜家家酒", 1241982: "海洋奇緣2"},
    }
    return FakeTmdbClient(**{**defaults, **kwargs})  # type: ignore[arg-type]


async def credentialled(session: AsyncSession, client: FakeTmdbClient) -> FakeClientFactory:
    """精靈第 6 步做完的樣子：憑證存下來了（票 02b 之後它是必填閘門）。"""
    await write_settings(session, TmdbSettings(api_key=TMDB_API_KEY))
    await session.commit()
    return FakeClientFactory(tmdb=client)


async def add_route(
    session: AsyncSession,
    *,
    slug: str = "tv",
    name: str = "TV",
    collection_type: CollectionType = CollectionType.TVSHOWS,
) -> Route:
    route = Route(
        slug=slug,
        name=name,
        jellyfin_library_id=f"item-{slug}",
        jellyfin_library_name=name,
        collection_type=collection_type,
        target_path=f"/data/library/{slug}",
        category=f"berth-{slug}",
        profile=Profile.STANDARD,
    )
    session.add(route)
    await session.commit()
    return route


class TestSnapshot:
    async def test_it_reads_every_season_and_episode(self, session: AsyncSession) -> None:
        """快照要帶各季各集的 number / name / air_date / runtime（票 04 驗收）。"""
        factory = await credentialled(session, tmdb())

        view = await read_media(session, factory, SPY_ID)

        assert view.problem is None
        assert [(row.season_number, row.name, row.episode_count) for row in view.seasons] == [
            (0, "Specials", 3),
            (1, "Season 1", 25),
            (2, "Season 2", 12),
        ]
        first = view.seasons[1].episodes[0]
        assert (first.episode_number, first.name) == (1, "OPERATION STRIX")
        assert (first.air_date, first.runtime) == (date(2022, 4, 9), 25)

    async def test_the_display_title_comes_from_the_second_round(
        self, session: AsyncSession
    ) -> None:
        """`zh-TW` 那一輪只補顯示用標題與簡介；英文標題留著，因為檔名用的是它（brief §7.5）。"""
        factory = await credentialled(session, tmdb())

        view = await read_media(session, factory, SPY_ID)

        assert view.title == "SPY×FAMILY 間諜家家酒"
        assert view.title_en == "SPY x FAMILY"
        assert view.title_original == "SPY×FAMILY"

    async def test_absolute_numbers_land_on_the_episodes(self, session: AsyncSession) -> None:
        """有 Absolute group 的作品，每一集帶得出絕對編號（票 04 驗收）。"""
        factory = await credentialled(session, tmdb())

        view = await read_media(session, factory, SPY_ID)

        numbers = {
            (row.season_number, episode.episode_number): episode.absolute_number
            for row in view.seasons
            for episode in row.episodes
        }
        assert numbers[(1, 25)] == 25
        # 第二季第一集是絕對第 26 集，不是第 1 集。
        assert numbers[(2, 1)] == 26
        # 沒有排進 group 的特輯就是沒有絕對編號，不是 0。
        assert numbers[(0, 1)] is None

    async def test_a_show_without_an_absolute_group_asks_for_none(
        self, session: AsyncSession
    ) -> None:
        """六成的動漫才有那種 group（brief §20.3），沒有時不該多打一次 TMDB。"""
        client = tmdb(details=[replace(SPY, absolute_group_id="")])
        factory = await credentialled(session, client)

        await read_media(session, factory, SPY_ID)

        assert not [row for row in client.requests if row[0].startswith("episode_group/")]

    async def test_a_film_has_no_seasons(self, session: AsyncSession) -> None:
        """電影沒有季集區塊，片長在作品上（票 04 驗收：兩種 kind 都走得通）。"""
        factory = await credentialled(session, tmdb())

        view = await read_media(session, factory, MOANA_ID)

        assert view.kind is MediaKind.MOVIE
        assert view.seasons == ()
        assert view.runtime == 100
        assert view.title == "海洋奇緣2"


class TestCache:
    async def test_a_fresh_snapshot_does_not_touch_tmdb(self, session: AsyncSession) -> None:
        """快照 24 小時內有效（plan §8.3）。第二次讀只讀資料庫。"""
        client = tmdb()
        factory = await credentialled(session, client)

        await read_media(session, factory, SPY_ID)
        client.requests.clear()
        again = await read_media(session, factory, SPY_ID)

        assert client.requests == []
        assert again.seasons[1].episodes[0].name == "OPERATION STRIX"

    async def test_a_snapshot_older_than_a_day_refreshes_itself(
        self, session: AsyncSession
    ) -> None:
        """超過 24 小時自動刷新（票 04 驗收）。使用者不必按任何東西。"""
        client = tmdb()
        factory = await credentialled(session, client)
        await read_media(session, factory, SPY_ID)
        row = await session.get(Media, SPY_ID)
        assert row is not None
        row.tmdb_fetched_at = datetime.now(UTC) - SNAPSHOT_TTL - timedelta(minutes=1)
        await session.commit()
        client.requests.clear()

        await read_media(session, factory, SPY_ID)

        assert [name for name, _ in client.requests if name.startswith("detail/")]


class TestTrack:
    async def test_it_freezes_the_folder_name(self, session: AsyncSession) -> None:
        """追蹤那一刻把 plan §5 的模板算出來寫進去，之後只從那裡讀。"""
        factory = await credentialled(session, tmdb())
        route = await add_route(session)

        view = await track_media(session, factory, SPY_ID, route_id=route.id)

        assert view.tracked is True
        assert view.default_route_id == route.id
        assert view.folder_name == "SPY x FAMILY (2022) [tmdbid-120089]"
        row = await session.get(Media, SPY_ID)
        assert row is not None
        assert (row.tracked, row.folder_name) == (True, "SPY x FAMILY (2022) [tmdbid-120089]")

    async def test_refreshing_a_tracked_media_leaves_the_folder_name_alone(
        self, session: AsyncSession
    ) -> None:
        """**TMDB 改了標題也不動已經凍結的資料夾名**（plan §5、brief §4.5、票 04 驗收）。

        改名是顯式動作；靜默改掉的話已入庫的檔案就對不上它的作品資料夾了。
        """
        client = tmdb()
        factory = await credentialled(session, client)
        route = await add_route(session)
        await track_media(session, factory, SPY_ID, route_id=route.id)

        client.details[(MediaKind.TV, 120089)] = replace(SPY, title="Spy Family Renamed", year=2099)
        view = await refresh_media(session, factory, SPY_ID)

        assert view.title_en == "Spy Family Renamed"
        assert view.folder_name == "SPY x FAMILY (2022) [tmdbid-120089]"

    async def test_an_untracked_media_still_previews_the_current_name(
        self, session: AsyncSession
    ) -> None:
        """還沒追蹤的那一列上，資料夾名是**預覽**：TMDB 改了標題就跟著改。

        凍結發生在追蹤那一刻，不是第一次點進詳情頁那一刻——詳情頁只是看看。
        """
        client = tmdb()
        factory = await credentialled(session, client)
        await read_media(session, factory, SPY_ID)

        client.details[(MediaKind.TV, 120089)] = replace(SPY, title="Spy Family Renamed")
        view = await refresh_media(session, factory, SPY_ID)

        assert view.folder_name == "Spy Family Renamed (2022) [tmdbid-120089]"

    async def test_tracking_again_moves_the_route_without_thawing_the_name(
        self, session: AsyncSession
    ) -> None:
        """改預設 Route 走同一支命令。Route 不是凍結的東西——媒體庫會搬，資料夾名不會。"""
        factory = await credentialled(session, tmdb())
        first = await add_route(session)
        second = await add_route(session, slug="anime", name="Anime")

        await track_media(session, factory, SPY_ID, route_id=first.id)
        view = await track_media(session, factory, SPY_ID, route_id=second.id)

        assert view.default_route_id == second.id
        assert view.folder_name == "SPY x FAMILY (2022) [tmdbid-120089]"

    async def test_a_film_cannot_be_routed_to_a_series_library(self, session: AsyncSession) -> None:
        """Route 的 `collection_type` 要與作品相符，否則命名與 Jellyfin 都會錯（brief §4.3）。"""
        factory = await credentialled(session, tmdb())
        series = await add_route(session)

        with pytest.raises(ValueError, match="collection type"):
            await track_media(session, factory, MOANA_ID, route_id=series.id)

    async def test_tracking_without_a_route_is_allowed(self, session: AsyncSession) -> None:
        """一條相符的 Route 都還沒有的人也追蹤得了；送單時再回來補（票 09）。"""
        factory = await credentialled(session, tmdb())

        view = await track_media(session, factory, SPY_ID, route_id=None)

        assert (view.tracked, view.default_route_id) == (True, None)


class TestRouteChoices:
    async def test_only_matching_routes_are_offered(self, session: AsyncSession) -> None:
        """詳情頁的下拉只列得出相符的那幾條（票 04 驗收）。"""
        factory = await credentialled(session, tmdb())
        series = await add_route(session)
        await add_route(session, slug="films", name="Films", collection_type=CollectionType.MOVIES)

        view = await read_media(session, factory, SPY_ID)

        assert [(row.id, row.name) for row in view.routes] == [(series.id, "TV")]

    async def test_a_disabled_route_is_not_a_choice(self, session: AsyncSession) -> None:
        """停用的 Route 不該出現在下拉裡——選了它送單也不會發生任何事。"""
        factory = await credentialled(session, tmdb())
        route = await add_route(session)
        route.enabled = False
        await session.commit()

        view = await read_media(session, factory, SPY_ID)

        assert view.routes == ()


class TestProblems:
    async def test_it_says_when_the_credential_is_missing(self, session: AsyncSession) -> None:
        """憑證是精靈第 6 步的必填閘門（票 02b），所以「沒有 key」有一句自己的話。"""
        factory = FakeClientFactory(tmdb=tmdb())

        view = await read_media(session, factory, SPY_ID)

        assert view.problem is TmdbProblem.CREDENTIAL_MISSING
        assert view.seasons == ()

    async def test_it_says_when_tmdb_rejects_the_credential(self, session: AsyncSession) -> None:
        factory = await credentialled(session, tmdb(error=AuthFailedError("GET /tv/120089: 401")))

        view = await read_media(session, factory, SPY_ID)

        assert view.problem is TmdbProblem.CREDENTIAL_REJECTED
        assert "401" in view.detail

    async def test_it_says_when_the_title_does_not_exist(self, session: AsyncSession) -> None:
        """404 與「TMDB 壞了」的下一步完全不同（票 04 的 `TmdbNotice`）。"""
        factory = await credentialled(session, tmdb())

        view = await read_media(session, factory, "tv:99999999")

        assert view.problem is TmdbProblem.NOT_FOUND

    async def test_a_malformed_id_is_not_found_either(self, session: AsyncSession) -> None:
        """`/media/nonsense` 是網址打錯，不該變成 500。"""
        factory = await credentialled(session, tmdb())

        view = await read_media(session, factory, "nonsense")

        assert view.problem is TmdbProblem.NOT_FOUND

    async def test_a_stale_snapshot_still_draws_the_page(self, session: AsyncSession) -> None:
        """**快照過期而 TMDB 連不上時，畫面仍然畫得出來**（shape brief §5）。

        存下來的季集加一句「這是舊的」，比一片空白有用得多。
        """
        client = tmdb()
        factory = await credentialled(session, client)
        await read_media(session, factory, SPY_ID)
        row = await session.get(Media, SPY_ID)
        assert row is not None
        row.tmdb_fetched_at = datetime.now(UTC) - SNAPSHOT_TTL - timedelta(minutes=1)
        await session.commit()
        client.error = ServiceUnavailableError("GET /tv/120089: connection refused")

        view = await read_media(session, factory, SPY_ID)

        assert view.problem is TmdbProblem.UNREACHABLE
        assert view.seasons[1].episodes[0].name == "OPERATION STRIX"
        assert view.fetched_at is not None
