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

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.jellyfin import (
    ITEM_EPISODE,
    ITEM_MOVIE,
    ITEM_SERIES,
    JellyfinItem,
    JellyfinLibrary,
)
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.models import JellyfinSettings
from berth.services.auth import AuthenticatedUser, read_session, sign_in
from berth.services.jellyfin_access import (
    ACCESS_TTL_SECONDS,
    AccessCache,
    AccountDisabledError,
    ItemNotVisibleError,
    JellyfinUnreachableError,
    LibraryNotVisibleError,
    jellyfin_access,
)
from berth.services.settings import write_settings
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
    def item(item_id: str, kind: str, path: str, series: str = "") -> JellyfinItem:
        return JellyfinItem(
            id=item_id, type=kind, name=item_id, path=path, tmdb_id="", series_id=series
        )

    return (
        item(SERIES, ITEM_SERIES, "/data/library/tv/The Bear"),
        item(FIRST, ITEM_EPISODE, "/data/library/tv/The Bear/S01E01.mkv", SERIES),
        item(SECOND, ITEM_EPISODE, "/data/library/tv/The Bear/S01E02.mkv", SERIES),
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
            await access.page(TV, start=0, limit=100)
            await access.index(MOVIES)

        assert set(jellyfin.view_queries) == {user.jellyfin_user_id}
        assert set(jellyfin.policy_queries) == {user.jellyfin_user_id}
        assert jellyfin.browse_queries == [
            (user.jellyfin_user_id, TV),
            (user.jellyfin_user_id, MOVIES),
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
                await access.page(wanted, start=0, limit=100)
            with pytest.raises(LibraryNotVisibleError):
                await access.index(wanted)

        # 替身不替 Berth 擋（真的 Jellyfin 也不擋，研究 §2），所以一筆都沒有就是 Berth 擋下的。
        assert jellyfin.browse_queries == []


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
            await access.page(TV, start=0, limit=100)

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
                await access.page(TV, start=0, limit=100)


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
