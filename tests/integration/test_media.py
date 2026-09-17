"""Media 詳情與快照刷新的命令（plan §2.2、§5、§8.3、brief §7.5、票 04、04b）。

這裡驗的是四件事：**快照怎麼組**（英文那一輪是結構本身，`zh-TW` 只補顯示用標題與簡介）、
**24 小時的快照規則**、**`folder_name` 跟著標題走**（凍結在票 09 的送單那一刻，之後不動），
以及**拿不到 TMDB 時還剩下什麼**。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import AuthFailedError, ServiceUnavailableError
from berth.adapters.tmdb import TmdbDetail, TmdbEpisode, TmdbSeason, TmdbSeasonEntry
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.domain import CollectionType, MediaKind, TmdbProblem
from berth.models import Media, Route, TmdbSettings
from berth.services.media import SNAPSHOT_TTL, read_media, read_snapshot, refresh_media
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

    async def test_every_season_keeps_the_names_the_other_rounds_gave_it(
        self, session: AsyncSession
    ) -> None:
        """篇章名比對的對手是「柱训练篇」這種簡體寫法，而 `name` 是英文（plan §4.4）。

        所以季名要三套都留下來：英文那一輪進檔名，另外兩輪只給解析器比對用。
        """
        client = tmdb(
            season_names={
                "zh-TW": {1: "第一季", 2: "柱訓練篇"},
                "zh-CN": {1: "第一季", 2: "柱训练篇"},
            }
        )
        factory = await credentialled(session, client)

        snapshot = await read_snapshot(session, factory, SPY_ID)

        assert snapshot is not None
        assert snapshot.seasons[2].name == "Season 2"
        assert snapshot.seasons[2].names == ("Season 2", "柱訓練篇", "柱训练篇")

    async def test_a_movie_does_not_pay_for_the_third_round(self, session: AsyncSession) -> None:
        """第三輪只為了季名，而電影沒有季（plan §4.4）。"""
        client = tmdb()
        factory = await credentialled(session, client)

        await read_media(session, factory, MOANA_ID)

        rounds = [
            language for endpoint, language in client.requests if endpoint.startswith("detail/")
        ]
        assert rounds == ["en-US", "zh-TW"]

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


class TestFolderName:
    async def test_it_follows_the_title(self, session: AsyncSession) -> None:
        """**TMDB 改了標題，資料夾名就跟著改**（票 04b）。

        凍結要等到第一次真的通向磁碟的那一刻——手動送單成功時（票 09）。在那之前這一列上的
        資料夾名只是畫面上的「將會是」，沒有任何檔案依賴它，而跟著標題走的那一份比較新。
        """
        client = tmdb()
        factory = await credentialled(session, client)
        await read_media(session, factory, SPY_ID)

        client.details[(MediaKind.TV, 120089)] = replace(SPY, title="Spy Family Renamed", year=2099)
        view = await refresh_media(session, factory, SPY_ID)

        assert view.folder_name == "Spy Family Renamed (2099) [tmdbid-120089]"
        row = await session.get(Media, SPY_ID)
        assert row is not None
        assert row.folder_name == "Spy Family Renamed (2099) [tmdbid-120089]"

    async def test_a_frozen_name_survives_a_tmdb_rename(self, session: AsyncSession) -> None:
        """**凍結之後刷新一律不動它**（plan §2.2、brief §4.5、票 09）。

        凍結發生在送單成功那一刻（`services/jobs`），而那一刻起磁碟上真的有一個那樣的
        資料夾、帳本上也有指向它的路徑。TMDB 之後改標題不該讓 Berth 的檔案跟著改名——
        改名是顯式動作。拿掉 `_store` 那個 `if not row.folder_frozen:` 守衛時這一條會紅。
        """
        client = tmdb()
        factory = await credentialled(session, client)
        await read_media(session, factory, SPY_ID)
        row = await session.get(Media, SPY_ID)
        assert row is not None
        row.folder_frozen = True
        await session.commit()

        client.details[(MediaKind.TV, 120089)] = replace(SPY, title="Spy Family Renamed", year=2099)
        view = await refresh_media(session, factory, SPY_ID)

        assert view.folder_name == "SPY x FAMILY (2022) [tmdbid-120089]"
        assert view.folder_frozen is True
        # 標題本身仍然跟著 TMDB 走——凍住的只有那一串會落到磁碟上的字。
        assert view.title_en == "Spy Family Renamed"

    async def test_it_is_sanitised(self, session: AsyncSession) -> None:
        """非法字元擋在寫進資料庫之前（plan §5）。"""
        client = tmdb(details=[replace(SPY, title="Mission: Impossible"), MOANA])
        factory = await credentialled(session, client)

        view = await read_media(session, factory, SPY_ID)

        assert view.folder_name == "Mission Impossible (2022) [tmdbid-120089]"


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
