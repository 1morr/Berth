"""替某一位使用者向 Jellyfin 讀東西的閘門（M1.5 票 03、plan §11.2b、研究 library-browsing.md §9）。

伺服器 API key 在 Jellyfin 眼中是管理員：帶誰的 `userId` 就是誰，而帶 `parentId` 的查詢
**不套**媒體庫權限（12.1.0 實測）。所以權限是 Berth 的責任，而這裡的每一條都在問同一件事——
**擋下來的請求有沒有真的沒送出去**。替身 Jellyfin 刻意不替 Berth 擋（`adapters/jellyfin/fake.py`），
斷言看的是它記下的查詢。

標記已看 / 未看（M1.5 票 05）是這裡唯一的寫入。**可見性由 Jellyfin 自己查**（`UserPlayedItems`
對看不到的 item 回 404 而且沒有寫入，研究 §5、12.1.0 讀回確認），替身照做；這裡驗的是寫進去的是
session 那個人的紀錄、404 變成拒絕，以及停用的帳號在問 Jellyfin 之前就被擋下。

API 那一層（前端塞進來的 `userId`、401 之後的下一個請求）在 `test_inventory_api.py`。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.jellyfin import (
    ITEM_EPISODE,
    ITEM_MOVIE,
    ITEM_SEASON,
    ITEM_SERIES,
    JellyfinItem,
    JellyfinLibrary,
    JellyfinUserData,
)
from berth.adapters.jellyfin.fake import FakeJellyfinClient, ItemMetadata
from berth.domain import LibrarySort, MediaKind, SortOrder
from berth.models import JellyfinSettings
from berth.services.auth import AuthenticatedUser, read_session, sign_in
from berth.services.jellyfin_access import (
    ACCESS_TTL_SECONDS,
    AccessCache,
    AccountDisabledError,
    ItemNotVisibleError,
    JellyfinUnreachableError,
    LibraryNotVisibleError,
    SortNotOfferedError,
    WallQuery,
    jellyfin_access,
)
from berth.services.settings import write_settings
from berth.services.watching import read_watching
from tests.integration.factories import FakeClientFactory

pytestmark = pytest.mark.asyncio

TV = "library-tv"
MOVIES = "library-movies"
ANIME = "library-anime"
MUSIC = "library-music"


def library(item_id: str, name: str, collection_type: str) -> JellyfinLibrary:
    return JellyfinLibrary(
        name=name,
        item_id=item_id,
        collection_type=collection_type,
        locations=(f"/data/library/{name.lower()}",),
        type_options=(),
    )


class Clock:
    """`AccessCache` 的時間。測試自己往前撥，不必真的等一分鐘。"""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def jellyfin() -> FakeJellyfinClient:
    """管理員看得到全部；`deckhand` 只開放 TV 與 Movies（再加一個 Berth 瀏覽不了的音樂庫）。"""
    return FakeJellyfinClient(
        startup_wizard_completed=True,
        admin=("skipper", "harbour"),
        users={"deckhand": "rope"},
        folders={"deckhand": (MOVIES, TV, MUSIC)},
        libraries=(
            library(MOVIES, "Movies", "movies"),
            library(TV, "TV", "tvshows"),
            library(ANIME, "Anime", "tvshows"),
            library(MUSIC, "Music", "music"),
        ),
    )


#: TV 上一部兩集的劇、Movies 上一部片，與 `deckhand` 看不到的 Anime 上一部劇。
SERIES, FIRST, SECOND = "series-bear", "bear-e01", "bear-e02"
FILM = "film-oppenheimer"
HIDDEN = "series-frieren"


def watchable() -> tuple[JellyfinItem, ...]:
    def item(
        item_id: str, kind: str, path: str, series: str = "", episode: int | None = None
    ) -> JellyfinItem:
        return JellyfinItem(
            id=item_id,
            type=kind,
            name=item_id,
            path=path,
            tmdb_id="",
            series_id=series,
            season=None if episode is None else 1,
            episode_start=episode,
        )

    return (
        item(SERIES, ITEM_SERIES, "/data/library/tv/The Bear"),
        item(FIRST, ITEM_EPISODE, "/data/library/tv/The Bear/S01E01.mkv", SERIES, 1),
        item(SECOND, ITEM_EPISODE, "/data/library/tv/The Bear/S01E02.mkv", SERIES, 2),
        item(FILM, ITEM_MOVIE, "/data/library/movies/Oppenheimer/Oppenheimer.mkv"),
        item(HIDDEN, ITEM_SERIES, "/data/library/anime/Frieren"),
    )


@pytest.fixture
def factory(jellyfin: FakeJellyfinClient) -> FakeClientFactory:
    return FakeClientFactory(jellyfin=jellyfin)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def cache(clock: Clock) -> AccessCache:
    return AccessCache(clock=clock)


async def signed_in(
    session: AsyncSession, factory: FakeClientFactory, username: str, password: str
) -> tuple[AuthenticatedUser, str]:
    await write_settings(session, JellyfinSettings(base_url="http://jellyfin:8096", api_key="key"))
    signed = await sign_in(session, factory, username=username, password=password)
    user = await read_session(session, signed.token)
    assert user is not None
    return user, signed.token


class TestAllowList:
    async def test_only_the_film_and_tv_libraries_this_user_sees_are_browsable(
        self, session: AsyncSession, factory: FakeClientFactory, cache: AccessCache
    ) -> None:
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            libraries = access.libraries

        # 順序照 Jellyfin 回的（使用者自己在 Jellyfin 排的）；Anime 沒有權限、Music 瀏覽不了。
        assert [(row.id, row.name, row.collection_type.value) for row in libraries] == [
            (MOVIES, "Movies", "movies"),
            (TV, "TV", "tvshows"),
        ]

    async def test_jellyfin_is_asked_about_the_signed_in_user_and_no_one_else(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            await access.page(TV, start=0, limit=100, query=WallQuery())
            await access.index(MOVIES)
            await access.filters(TV)

        assert set(jellyfin.view_queries) == {user.jellyfin_user_id}
        assert set(jellyfin.policy_queries) == {user.jellyfin_user_id}
        assert jellyfin.browse_queries == [
            (user.jellyfin_user_id, TV),
            (user.jellyfin_user_id, MOVIES),
            (user.jellyfin_user_id, TV),
        ]

    @pytest.mark.parametrize("wanted", [ANIME, MUSIC, "no-such-library"])
    async def test_a_library_off_the_list_is_refused_without_asking_jellyfin(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
        wanted: str,
    ) -> None:
        """沒有權限、瀏覽不了、不存在的媒體庫是同一種拒絕：分得出來就是在告訴人它存在。"""
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            with pytest.raises(LibraryNotVisibleError):
                await access.page(wanted, start=0, limit=100, query=WallQuery())
            with pytest.raises(LibraryNotVisibleError):
                await access.index(wanted)
            # 類型與年份清單帶 `parentId` 時同樣不套權限，連使用者自己的 token 都照回（研究 §2）。
            with pytest.raises(LibraryNotVisibleError):
                await access.filters(wanted)

        # 替身不替 Berth 擋（真的 Jellyfin 也不擋，研究 §2），所以一筆都沒有就是 Berth 擋下的。
        assert jellyfin.browse_queries == []


class TestWallQuery:
    """排序與類型、年份篩選（M1.5 票 06）。伺服器真的照參數排、篩，是契約測試對著錄製證明的；
    這裡驗的是 Berth 問出去的那一個問題，替身照著排、照著篩。"""

    @pytest.fixture
    def shelved(self, jellyfin: FakeJellyfinClient) -> FakeJellyfinClient:
        def series(name: str, year: int) -> JellyfinItem:
            path = f"/data/library/tv/{name}"
            return JellyfinItem(
                id=name, type=ITEM_SERIES, name=name, path=path, tmdb_id="", year=year
            )

        jellyfin.items_ = [series("Alpha", 2022), series("Bravo", 2020), series("Charlie", 2023)]
        jellyfin.metadata = {
            "Alpha": ItemMetadata(genres=("Drama",), sort_values={"CommunityRating": 7.0}),
            "Bravo": ItemMetadata(genres=("Comedy",), sort_values={"CommunityRating": 9.0}),
            "Charlie": ItemMetadata(genres=("Drama", "Fantasy")),
        }
        return jellyfin

    async def test_the_wall_comes_back_in_the_order_asked_for(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        shelved: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        user, _ = await signed_in(session, factory, "deckhand", "rope")
        rating = WallQuery(sort=LibrarySort.COMMUNITY_RATING)

        async with jellyfin_access(session, factory, cache, user) as access:
            by_name = await access.page(TV, start=0, limit=100, query=WallQuery())
            ascending = await access.page(TV, start=0, limit=100, query=rating)
            descending = await access.page(
                TV, start=0, limit=100, query=replace(rating, order=SortOrder.DESCENDING)
            )

        assert [item.id for item in by_name.items] == ["Alpha", "Bravo", "Charlie"]
        # 沒有評分的排在升冪最前、降冪最後（研究 §3.1）。
        assert [item.id for item in ascending.items] == ["Charlie", "Alpha", "Bravo"]
        assert [item.id for item in descending.items] == ["Bravo", "Alpha", "Charlie"]

    async def test_genres_and_years_narrow_the_wall_and_its_total(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        shelved: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        """類型之間、年份之間是「或」，兩者之間是「且」（研究 §3.1）。"""
        user, _ = await signed_in(session, factory, "deckhand", "rope")
        query = WallQuery(genres=("Drama", "Comedy"), years=(2020, 2023))

        async with jellyfin_access(session, factory, cache, user) as access:
            page = await access.page(TV, start=0, limit=100, query=query)

        assert ([item.id for item in page.items], page.total) == (["Bravo", "Charlie"], 2)

    async def test_a_sort_this_kind_of_library_does_not_offer_is_refused_without_asking(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        shelved: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        """「最近看過」在劇集庫是 `SeriesDatePlayed`、在電影庫是 `DatePlayed`：用錯的那一個，
        Jellyfin 不會報錯，牆只會默默變成別的順序。"""
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            with pytest.raises(SortNotOfferedError):
                await access.page(
                    TV, start=0, limit=100, query=WallQuery(sort=LibrarySort.DATE_PLAYED)
                )

        assert shelved.browse_queries == []

    async def test_the_filter_lists_are_this_librarys_genres_and_years(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        shelved: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            filters = await access.filters(TV)

        assert filters.genres == ("Comedy", "Drama", "Fantasy")
        assert filters.years == (2020, 2022, 2023)
        assert shelved.browse_queries == [(user.jellyfin_user_id, TV)]


class TestAccountState:
    async def test_a_disabled_account_ends_every_session_that_account_has(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        user, phone = await signed_in(session, factory, "deckhand", "rope")
        _, laptop = await signed_in(session, factory, "deckhand", "rope")
        _, admin = await signed_in(session, factory, "skipper", "harbour")
        jellyfin.disabled.add("deckhand")

        with pytest.raises(AccountDisabledError):
            async with jellyfin_access(session, factory, cache, user):
                pytest.fail("a disabled account must not get through")

        assert await read_session(session, phone) is None
        assert await read_session(session, laptop) is None
        assert await read_session(session, admin) is not None
        assert jellyfin.browse_queries == []

    async def test_the_answer_is_kept_for_a_short_while_then_asked_again(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
        clock: Clock,
    ) -> None:
        """允許清單與 `Policy` 是同一份快取：一頁牆要打好幾支 API，每一支都去問 Jellyfin 不值得。"""
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user):
            pass
        clock.now += ACCESS_TTL_SECONDS - 1
        async with jellyfin_access(session, factory, cache, user):
            pass

        assert (len(jellyfin.view_queries), len(jellyfin.policy_queries)) == (1, 1)

        clock.now += 2
        async with jellyfin_access(session, factory, cache, user):
            pass

        assert (len(jellyfin.view_queries), len(jellyfin.policy_queries)) == (2, 2)

    async def test_a_permission_taken_away_holds_until_the_cache_runs_out(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
        clock: Clock,
    ) -> None:
        """縮權與停用最久晚 `ACCESS_TTL_SECONDS` 生效——那就是這個常數換來的代價。"""
        user, _ = await signed_in(session, factory, "deckhand", "rope")
        async with jellyfin_access(session, factory, cache, user):
            pass

        jellyfin.folders["deckhand"] = (MOVIES,)
        jellyfin.disabled.add("deckhand")
        async with jellyfin_access(session, factory, cache, user) as access:
            await access.page(TV, start=0, limit=100, query=WallQuery())

        clock.now += ACCESS_TTL_SECONDS + 1
        with pytest.raises(AccountDisabledError):
            async with jellyfin_access(session, factory, cache, user):
                pass

    async def test_each_user_has_their_own_answer(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        crew, _ = await signed_in(session, factory, "deckhand", "rope")
        admin, _ = await signed_in(session, factory, "skipper", "harbour")

        async with jellyfin_access(session, factory, cache, crew) as access:
            seen_by_crew = {row.id for row in access.libraries}
        async with jellyfin_access(session, factory, cache, admin) as access:
            seen_by_admin = {row.id for row in access.libraries}

        assert seen_by_crew == {MOVIES, TV}
        assert seen_by_admin == {MOVIES, TV, ANIME}


class TestUnreachable:
    async def test_jellyfin_not_answering_is_a_reason_with_its_own_words(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        user, _ = await signed_in(session, factory, "deckhand", "rope")
        jellyfin.error = ServiceUnavailableError("GET /UserViews: connection refused")

        with pytest.raises(JellyfinUnreachableError) as refused:
            async with jellyfin_access(session, factory, cache, user):
                pass

        assert refused.value.detail == "GET /UserViews: connection refused"

    async def test_jellyfin_going_away_between_two_questions_is_the_same_reason(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            jellyfin.error = ServiceUnavailableError("GET /Items: connection refused")
            with pytest.raises(JellyfinUnreachableError):
                await access.page(TV, start=0, limit=100, query=WallQuery())


class TestMarkPlayed:
    async def test_the_record_written_is_the_signed_in_users(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        jellyfin.items_ = list(watchable())
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            written = await access.mark_played(FILM, played=True)

        assert jellyfin.played_queries == [(user.jellyfin_user_id, FILM, True)]
        assert jellyfin.played == {"deckhand": {FILM}}
        assert written.played

    async def test_marking_unplayed_clears_the_record_it_wrote(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        jellyfin.items_ = list(watchable())
        jellyfin.played = {"deckhand": {FIRST}, "skipper": {FIRST}}
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            written = await access.mark_played(SERIES, played=False)

        assert (written.played, written.unplayed_episodes) == (False, 2)
        assert jellyfin.played == {"deckhand": set(), "skipper": {FIRST}}

    @pytest.mark.parametrize("played", [True, False])
    async def test_an_item_this_user_cannot_see_is_refused_and_nothing_is_written(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
        played: bool,
    ) -> None:
        """Jellyfin 回 404 而且沒有寫入（研究 §5）；看不到與不存在是同一種拒絕。"""
        jellyfin.items_ = list(watchable())
        jellyfin.played = {"skipper": {HIDDEN}}
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            for wanted in (HIDDEN, "no-such-item"):
                with pytest.raises(ItemNotVisibleError):
                    await access.mark_played(wanted, played=played)

        assert jellyfin.played == {"skipper": {HIDDEN}}

    async def test_a_disabled_account_writes_nothing(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        """API key 替停用的帳號照樣寫得進去（研究 §2），所以擋的是 Berth。"""
        jellyfin.items_ = list(watchable())
        user, _ = await signed_in(session, factory, "deckhand", "rope")
        jellyfin.disabled.add("deckhand")

        with pytest.raises(AccountDisabledError):
            async with jellyfin_access(session, factory, cache, user) as access:
                await access.mark_played(FILM, played=True)

        assert jellyfin.played_queries == []

    async def test_jellyfin_not_answering_is_the_same_reason_as_for_reading(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        jellyfin.items_ = list(watchable())
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            jellyfin.error = ServiceUnavailableError("POST /UserPlayedItems: connection refused")
            with pytest.raises(JellyfinUnreachableError):
                await access.mark_played(FILM, played=True)


class TestWatching:
    """繼續觀看與下一集（M1.5 票 07）。Resume 與 NextUp **不帶** `parentId` 時 Jellyfin 照這個人的
    媒體庫限縮，帶了就不限縮（研究 §2，12.1.0 實測）：首頁那兩支一定不帶，媒體庫頁先對允許清單
    驗過才帶。"""

    @pytest.fixture(autouse=True)
    def watched(self, jellyfin: FakeJellyfinClient) -> None:
        """`deckhand` 看完 The Bear 第一集、Oppenheimer 看到一半；Anime 那部他看不到的劇在 `skipper`
        帳號上看到一半——替身照 Jellyfin 的規矩，不帶 `parentId` 時不會把它交給 `deckhand`。"""
        jellyfin.items_ = list(watchable())
        jellyfin.played = {"deckhand": {FIRST}}
        jellyfin.positions = {"deckhand": {FILM: 42.0}}

    async def test_the_home_rows_are_asked_for_the_whole_account_without_a_library(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            watching = await read_watching(access, None)

        assert sorted(jellyfin.watching_queries) == [
            ("next_up", user.jellyfin_user_id, None),
            ("resume", user.jellyfin_user_id, None),
        ]
        assert jellyfin.browse_queries == []
        assert [(card.item_id, card.progress) for card in watching.resume] == [(FILM, 42)]
        assert [card.item_id for card in watching.next_up] == [SECOND]

    async def test_a_library_on_the_list_is_asked_with_its_id(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            watching = await read_watching(access, TV)

        assert sorted(jellyfin.watching_queries) == [
            ("next_up", user.jellyfin_user_id, TV),
            ("resume", user.jellyfin_user_id, TV),
        ]
        # Oppenheimer 在 Movies：TV 的繼續觀看是空的。
        assert watching.resume == ()
        assert [card.item_id for card in watching.next_up] == [SECOND]

    @pytest.mark.parametrize("wanted", [ANIME, MUSIC, "no-such-library"])
    async def test_a_library_off_the_list_is_refused_without_asking_jellyfin(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
        wanted: str,
    ) -> None:
        """帶了 `parentId` 連使用者自己的 token 都擋不住（研究 §2）：替身也不擋，一筆都沒有就是
        Berth 擋的。"""
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            with pytest.raises(LibraryNotVisibleError):
                await read_watching(access, wanted)

        assert jellyfin.watching_queries == []

    async def test_next_up_counts_only_shows_watched_within_a_year(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        """jellyfin-web 的 `maxDaysForNextUp` 預設 365（研究 §7）。"""
        user, _ = await signed_in(session, factory, "deckhand", "rope")
        before = datetime.now(UTC)

        async with jellyfin_access(session, factory, cache, user) as access:
            await read_watching(access, None)

        [cutoff] = jellyfin.next_up_cutoffs
        assert before - timedelta(days=365, seconds=5) < cutoff <= before - timedelta(days=364)

    async def test_jellyfin_going_away_is_the_same_reason_as_for_the_wall(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            jellyfin.error = ServiceUnavailableError("GET /UserItems/Resume: connection refused")
            with pytest.raises(JellyfinUnreachableError) as refused:
                await read_watching(access, None)

        assert refused.value.detail == "GET /UserItems/Resume: connection refused"


#: Media 詳情的觀看區（M1.5 票 08）：TV 上一部分季的劇、Movies 上一部片、Anime 上一部 `deckhand`
#: 看不到的劇，以及一部 Jellyfin 認錯 TMDB id 的劇（帳本記得它是哪一部）。
BEAR, BEAR_S01, BEAR_E01, BEAR_E02 = "series-bear", "bear-s01", "bear-e01", "bear-e02"
OPPENHEIMER = "film-oppenheimer"
FRIEREN, FRIEREN_S01 = "series-frieren", "frieren-s01"
MISNAMED = "series-misnamed"


def titled() -> tuple[JellyfinItem, ...]:
    tv = "/data/library/tv"
    return (
        JellyfinItem(BEAR, ITEM_SERIES, "The Bear", f"{tv}/The Bear", "136315"),
        JellyfinItem(
            BEAR_S01, ITEM_SEASON, "Season 1", f"{tv}/The Bear/S1", "", series_id=BEAR, season=1
        ),
        *(
            JellyfinItem(
                episode_id,
                ITEM_EPISODE,
                f"Episode {number}",
                f"{tv}/The Bear/S1/S01E0{number}.mkv",
                "",
                series_id=BEAR,
                season_id=BEAR_S01,
                season=1,
                episode_start=number,
            )
            for number, episode_id in ((1, BEAR_E01), (2, BEAR_E02))
        ),
        JellyfinItem(
            OPPENHEIMER, ITEM_MOVIE, "Oppenheimer", "/data/library/movies/Oppenheimer.mkv", "872585"
        ),
        JellyfinItem(FRIEREN, ITEM_SERIES, "Frieren", "/data/library/anime/Frieren", "209867"),
        JellyfinItem(
            FRIEREN_S01,
            ITEM_SEASON,
            "Season 1",
            "/data/library/anime/Frieren/S1",
            "",
            series_id=FRIEREN,
            season=1,
        ),
        JellyfinItem(MISNAMED, ITEM_SERIES, "Slow Horses", f"{tv}/Slow Horses", "1"),
    )


class TestLocate:
    """由 TMDB id 找這位使用者看得到的作品（研究 §10）。**不帶 `parentId`**，Jellyfin 才照他的
    權限限縮；找到之後向 Jellyfin 確認一次看得到（`/Items/{id}?userId=`），**這部劇的 NextUp 只在
    確認之後才問**——帶 `seriesId` 的 NextUp 不套權限（研究 §2），替身照做，所以問了就是 Berth
    放行的。"""

    @pytest.fixture(autouse=True)
    def catalogue(self, jellyfin: FakeJellyfinClient) -> None:
        jellyfin.items_ = list(titled())
        jellyfin.played = {"deckhand": {BEAR_E01}}

    async def test_a_title_is_looked_up_across_what_this_user_sees_then_confirmed(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            found = await access.locate(MediaKind.TV, 136315, links=())

        assert found is not None
        assert found.id == BEAR
        assert found.user_data is not None
        assert found.user_data.unplayed_item_count == 1
        me = user.jellyfin_user_id
        assert jellyfin.watch_area_queries == [("tmdb_index", me, ITEM_SERIES), ("item", me, BEAR)]
        # 找作品不帶 `parentId`：不走任何一個媒體庫。
        assert jellyfin.browse_queries == []

    async def test_a_film_is_looked_up_among_films(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            found = await access.locate(MediaKind.MOVIE, 872585, links=())
            # 同一個 TMDB id 在劇集那邊沒有這部片。
            series = await access.locate(MediaKind.TV, 872585, links=())

        assert found is not None
        assert found.id == OPPENHEIMER
        assert series is None

    async def test_a_title_only_in_a_library_this_user_cannot_see_is_not_there(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        """看不到與不在 Jellyfin 是同一個答案：分得出來就是在告訴人那部作品在哪裡。"""
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            found = await access.locate(MediaKind.TV, 209867, links=())

        assert found is None
        assert [query for query, *_ in jellyfin.watch_area_queries] == ["tmdb_index"]

    async def test_the_ledgers_link_wins_over_a_tmdb_id_jellyfin_got_wrong(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        """媒體庫牆的同一條規則（票 03）：Jellyfin 認錯 TMDB id 時，帳本記下的那一個才是對的。"""
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            found = await access.locate(MediaKind.TV, 95480, links=(MISNAMED,))

        assert found is not None
        assert found.id == MISNAMED

    async def test_a_link_to_a_title_this_user_cannot_see_is_not_followed(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        """帳本記的是 Berth 入庫的那一份，不是這個人看得到的那一份：連結只在找作品的結果裡比。"""
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            found = await access.locate(MediaKind.TV, 1, links=(FRIEREN,))

        assert found is not None
        assert found.id == MISNAMED
        assert ("item", user.jellyfin_user_id, FRIEREN) not in jellyfin.watch_area_queries

    async def test_next_up_of_a_show_is_asked_only_after_it_was_confirmed(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            with pytest.raises(ItemNotVisibleError):
                await access.series_next_up(BEAR)
            assert jellyfin.watch_area_queries == []

            await access.locate(MediaKind.TV, 136315, links=())
            carry_on = await access.series_next_up(BEAR)

        assert carry_on is not None
        assert carry_on.id == BEAR_E02
        assert jellyfin.watch_area_queries[-1] == ("series_next_up", user.jellyfin_user_id, BEAR)

    async def test_next_up_of_a_show_this_user_cannot_see_is_never_asked(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            assert await access.locate(MediaKind.TV, 209867, links=()) is None
            with pytest.raises(ItemNotVisibleError):
                await access.series_next_up(FRIEREN)

        assert "series_next_up" not in {query for query, *_ in jellyfin.watch_area_queries}

    async def test_seasons_and_episodes_come_from_jellyfin_for_this_user(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            seasons = await access.seasons(BEAR)
            episodes = await access.episodes(BEAR, BEAR_S01)

        assert [(season.id, season.number) for season in seasons] == [(BEAR_S01, 1)]
        assert [(episode.id, episode.user_data) for episode in episodes] == [
            (
                BEAR_E01,
                JellyfinUserData(played=True, played_percentage=0.0, unplayed_item_count=None),
            ),
            (
                BEAR_E02,
                JellyfinUserData(played=False, played_percentage=0.0, unplayed_item_count=None),
            ),
        ]

    async def test_seasons_and_episodes_of_a_show_this_user_cannot_see_are_refused(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        """這兩支 Jellyfin 自己查可見性（帶 `userId` 時無權 404，研究 §2）：404 是答案，
        翻成拒絕。"""
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            with pytest.raises(ItemNotVisibleError):
                await access.seasons(FRIEREN)
            with pytest.raises(ItemNotVisibleError):
                await access.episodes(FRIEREN, BEAR_S01)
            # 看得到的劇配上看不到的季也一樣：`seasonId` 同樣帶著這個人查（研究 §2）。
            with pytest.raises(ItemNotVisibleError):
                await access.episodes(BEAR, FRIEREN_S01)

    async def test_jellyfin_going_away_is_the_same_reason_as_for_the_wall(
        self,
        session: AsyncSession,
        factory: FakeClientFactory,
        jellyfin: FakeJellyfinClient,
        cache: AccessCache,
    ) -> None:
        user, _ = await signed_in(session, factory, "deckhand", "rope")

        async with jellyfin_access(session, factory, cache, user) as access:
            jellyfin.error = ServiceUnavailableError("GET /Items: connection refused")
            with pytest.raises(JellyfinUnreachableError):
                await access.locate(MediaKind.TV, 136315, links=())
            with pytest.raises(JellyfinUnreachableError):
                await access.episodes(BEAR, BEAR_S01)
