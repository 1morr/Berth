"""媒體庫：一個 Jellyfin 媒體庫的整面牆，疊上 Berth 經手作品的入庫狀態（M1.5 票 03、票 13）。

`.scratch/m1.5/library-shape.md`。四組斷言：

- **牆上有誰**：Jellyfin 那一頁的每一部作品，包括不是 Berth 入庫的；分頁照 Jellyfin。
- **Berth 經手的作品**（Tracked Media）：指向這個媒體庫的每一條 Route 上有 Job 的作品，加上帳本
  落在它們底下的。它們在 Jellyfin 裡時疊到牆上那一格，不在時列在「還沒進 Jellyfin」那一份。
  **對應不只靠帳本的 Series id**：Jellyfin 的 TMDB id 對得上也算（票 13 留下的缺口）。
- **一格說什麼**：六種狀態依序取第一個成立的、`N / M 集`、兩個篩選（票 13 的判定，沿用）。
- **還沒進 Jellyfin 的那一行**：還在找、找不到、沒有東西可以找。
- **這位使用者看到哪了**（M1.5 票 05）：只在 Jellyfin 那一頁的卡片上；推導規則在
  `tests/unit/test_watch.py`。

權限不在這裡測（`test_jellyfin_access.py`）：牆拿到的 `JellyfinAccess` 已經是驗過的那一份。
資料列是直接擺進去的：送單、規劃、入庫與反查各自有自己的測試，這裡要的是「帳本、Job 與
Jellyfin 長成這樣的時候，牆上說什麼」。
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.jellyfin import (
    ITEM_EPISODE,
    ITEM_MOVIE,
    ITEM_SERIES,
    JellyfinItem,
    JellyfinLibrary,
)
from berth.adapters.jellyfin.fake import FakeJellyfinClient, ItemMetadata
from berth.domain import (
    CollectionType,
    Confidence,
    EpisodeSnapshot,
    InventoryStatus,
    JellyfinPresence,
    JobState,
    JobTrigger,
    LibrarySort,
    MediaKind,
    MediaSnapshot,
    PlanAction,
    PlanStatus,
    ReviewKind,
    SeasonSnapshot,
    ServiceOrigin,
    SortOrder,
    Tags,
)
from berth.models import (
    JellyfinSettings,
    Job,
    JobFile,
    LedgerEntry,
    Media,
    Plan,
    PlanItem,
    Route,
)
from berth.services.deeplink import PublicUrlRejectedError, jellyfin_web, set_public_url
from berth.services.inventory import (
    PAGE_SIZE,
    InventoryCard,
    InventoryWall,
    Tracking,
    read_wall,
)
from berth.services.jellyfin_access import (
    BrowsableLibrary,
    JellyfinAccess,
    SortNotOfferedError,
    WallQuery,
)
from berth.services.review import library_counts
from berth.services.settings import read_settings, write_settings
from berth.services.watch import WatchState
from tests.integration.arrange import arrange

pytestmark = pytest.mark.asyncio

TODAY = datetime.now(UTC).date()

#: 替誰看。權限閘門不在這一層，替身也不看它（`adapters/jellyfin/fake.py`）。
VIEWER = "c7c3e8c2d6d443b38cac62383fbd5716"


def season(number: int, *, aired: int, unaired: int = 0) -> SeasonSnapshot:
    """`aired` 集已經播過、`unaired` 集還沒。播出日相對**真的今天**：判定用的是伺服器的日期。"""
    episodes = [
        EpisodeSnapshot(episode_number=index, air_date=TODAY - timedelta(days=30))
        for index in range(1, aired + 1)
    ] + [
        EpisodeSnapshot(episode_number=index, air_date=TODAY + timedelta(days=30))
        for index in range(aired + 1, aired + unaired + 1)
    ]
    return SeasonSnapshot(
        season_number=number, episode_count=len(episodes), episodes=tuple(episodes)
    )


async def title(
    session: AsyncSession,
    *,
    kind: MediaKind = MediaKind.TV,
    tmdb_id: int = 120089,
    name: str = "SPY x FAMILY",
    name_zh: str = "",
    seasons: tuple[SeasonSnapshot, ...] = (season(1, aired=4),),
) -> Media:
    row = Media(
        id=f"{kind.value}:{tmdb_id}",
        tmdb_id=tmdb_id,
        kind=kind,
        title_en=name,
        title_original=name,
        year=2022,
        folder_name=f"{name} (2022) [tmdbid-{tmdb_id}]",
        folder_frozen=True,
        tmdb_snapshot_json=MediaSnapshot(
            tmdb_id=tmdb_id,
            kind=kind,
            title=name_zh or name,
            title_en=name,
            title_original=name,
            year=2022,
            poster_url=f"https://image.tmdb.org/t/p/w342/{tmdb_id}.jpg",
            seasons=seasons if kind is MediaKind.TV else (),
        ).model_dump(mode="json"),
        tmdb_fetched_at=datetime.now(UTC),
    )
    session.add(row)
    await session.commit()
    return row


async def film(session: AsyncSession, *, tmdb_id: int = 872585) -> Media:
    return await title(session, kind=MediaKind.MOVIE, tmdb_id=tmdb_id, name="Oppenheimer")


async def route(
    session: AsyncSession,
    slug: str = "tv",
    *,
    collection_type: CollectionType = CollectionType.TVSHOWS,
    enabled: bool = True,
    library: str = "",
) -> Route:
    """`library` 是它指向的 Jellyfin 媒體庫；沒給就是自己一個（`library-<slug>`）。"""
    row = Route(
        slug=slug,
        name=slug.title(),
        jellyfin_library_id=library or f"library-{slug}",
        jellyfin_library_name=slug.title(),
        collection_type=collection_type,
        target_path=f"/data/library/{slug}",
        category=f"berth-{slug}",
        enabled=enabled,
    )
    session.add(row)
    await session.commit()
    return row


async def job(
    session: AsyncSession, media: Media, on: Route, state: JobState, *, hash: str = "a" * 40
) -> Job:
    row = Job(
        hash=hash,
        name=f"{media.title_en} release",
        trigger=JobTrigger.MANUAL,
        media_id=media.id,
        route_id=on.id,
        state=state,
    )
    session.add(row)
    await session.commit()
    return row


async def plan(
    session: AsyncSession,
    of: Job,
    *items: tuple[PlanAction, int | None, int | None],
    status: PlanStatus = PlanStatus.APPLIED,
) -> Plan:
    """`items` 是 `(處置, 季, 集)`。每一列有它自己的 `job_files` 那一列：審核佇列的 `unmatched`
    那一類以檔案為單位（`services/review._unmatched`）。"""
    # 檔名帶著這是第幾份：同一筆 Job 的第二份 Plan 不撞 `job_files` 的唯一鍵。
    earlier = await session.scalar(select(func.count(Plan.id)).where(Plan.job_hash == of.hash))
    row = Plan(job_hash=of.hash, status=status)
    session.add(row)
    files = [
        JobFile(job_hash=of.hash, rel_path=f"file-{earlier}-{index}.mkv", size=1, priority=1)
        for index in range(len(items))
    ]
    session.add_all(files)
    await session.flush()
    session.add_all(
        PlanItem(
            plan_id=row.id,
            rel_path=file.rel_path,
            job_file_id=file.id,
            action=action,
            media_id=of.media_id,
            season=number,
            episode_start=episode,
            confidence=Confidence.HIGH,
        )
        for file, (action, number, episode) in zip(files, items, strict=True)
    )
    await session.commit()
    return row


async def linked(
    session: AsyncSession,
    media: Media,
    under: Route,
    *,
    season_number: int | None = 1,
    episode: int | None = 1,
    episode_end: int | None = None,
    action: PlanAction = PlanAction.IMPORT,
    tags: Tags | None = None,
    item: str = "",
    series: str = "",
    version_name: str = "",
    resolve_after: datetime | None = None,
    attempts: int = 0,
    of: Job | None = None,
) -> LedgerEntry:
    """一筆帳本。目標路徑照命名模板的形狀擺（plan §5）：「落在哪一條 Route 底下」與
    Jellyfin 的版本標籤看的都是它。"""
    tags = tags or Tags(resolution="1080p", group="Group")
    where = (
        f"Season {season_number:02d}/{media.title_en} - "
        f"S{season_number:02d}E{episode:02d} {tags.render()}"
        if season_number is not None and episode is not None
        else f"{media.folder_name} - {tags.render()}"
    )
    suffix = ".ass" if action is PlanAction.SUBTITLE else ".mkv"
    target = f"{under.target_path}/{media.folder_name}/{where}{suffix}"
    row = LedgerEntry(
        job_hash=of.hash if of is not None else None,
        source_rel_path=f"release/{where}.mkv",
        source_abs_path=f"/data/torrent/complete/{under.slug}/release/{where}.mkv",
        source_inode="1",
        source_dev="1",
        target_path=target,
        target_inode="1",
        media_id=media.id,
        season=season_number,
        episode_start=episode,
        episode_end=episode_end,
        tags_json=tags.model_dump(mode="json"),
        action=action,
        jellyfin_item_id=item,
        jellyfin_series_id=series,
        jellyfin_version_name=version_name,
        resolve_after=resolve_after,
        resolve_attempts=attempts,
    )
    session.add(row)
    await session.commit()
    return row


def in_jellyfin(
    under: Route,
    name: str,
    *,
    id: str,
    tmdb_id: str = "",
    year: int | None = 2022,
    kind: MediaKind = MediaKind.TV,
) -> JellyfinItem:
    """Jellyfin 掃到的一部作品：資料夾在這條 Route 的目標底下（替身照路徑分媒體庫）。"""
    return JellyfinItem(
        id=id,
        type=ITEM_SERIES if kind is MediaKind.TV else ITEM_MOVIE,
        name=name,
        path=f"{under.target_path}/{name}",
        tmdb_id=tmdb_id,
        year=year,
    )


async def access_for(
    session: AsyncSession,
    items: Sequence[JellyfinItem] = (),
    *,
    jellyfin: FakeJellyfinClient | None = None,
    viewer: str = VIEWER,
) -> tuple[JellyfinAccess, FakeJellyfinClient]:
    """資料庫裡每一條 Route 指向的媒體庫都在 Jellyfin 上、而且這位使用者都看得到。"""
    routes = list(await session.scalars(select(Route).order_by(Route.id)))
    libraries: dict[str, list[Route]] = {}
    for row in routes:
        libraries.setdefault(row.jellyfin_library_id, []).append(row)
    fake = jellyfin or FakeJellyfinClient(startup_wizard_completed=True)
    fake.use_token("key")
    fake.libraries_ = [
        JellyfinLibrary(
            name=rows[0].jellyfin_library_name,
            item_id=library_id,
            collection_type=rows[0].collection_type.value,
            locations=tuple(row.target_path for row in rows),
            type_options=(),
        )
        for library_id, rows in libraries.items()
    ]
    fake.items_ = list(items)
    granted = tuple(
        BrowsableLibrary(id=library_id, name=rows[0].name, collection_type=rows[0].collection_type)
        for library_id, rows in libraries.items()
    )
    return JellyfinAccess(fake, viewer, granted), fake


async def wall(
    session: AsyncSession,
    slug: str = "tv",
    items: Sequence[JellyfinItem] = (),
    *,
    page: int = 1,
) -> InventoryWall:
    """`slug` 那條 Route 指向的媒體庫的牆。"""
    target = await session.scalar(select(Route).where(Route.slug == slug))
    assert target is not None
    access, _ = await access_for(session, items)
    return await read_wall(
        session, access, target.jellyfin_library_id, page=page, query=WallQuery()
    )


async def card(session: AsyncSession, slug: str = "tv") -> InventoryCard:
    """這個媒體庫上唯一一部 Berth 經手的作品（Jellyfin 裡沒有它）。"""
    tracked = (await wall(session, slug)).tracked
    assert len(tracked) == 1
    return tracked[0]


async def tracking(session: AsyncSession, slug: str = "tv") -> Tracking:
    found = (await card(session, slug)).tracking
    assert found is not None
    return found


class TestJellyfinWall:
    async def test_every_title_jellyfin_has_is_on_the_wall_berths_or_not(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        items = [
            in_jellyfin(tv, "Hotel Show", id="hotel", year=2021),
            in_jellyfin(tv, "Alpha Show", id="alpha", tmdb_id="1399"),
        ]

        shown = await wall(session, "tv", items)

        # 照 Jellyfin 的 `SortName`；名稱是 Jellyfin 的，兩種 UI 語言都一樣（brief §7.5）。
        assert [
            (row.jellyfin_item_id, row.title, row.title_en, row.year) for row in shown.titles
        ] == [
            ("alpha", "Alpha Show", "Alpha Show", 2022),
            ("hotel", "Hotel Show", "Hotel Show", 2021),
        ]
        assert all(row.presence is JellyfinPresence.FOUND for row in shown.titles)
        assert all(row.tracking is None for row in shown.titles)
        assert (shown.total, shown.page, shown.page_size) == (2, 1, PAGE_SIZE)
        assert shown.tracked == ()

    async def test_a_title_with_a_tmdb_id_leads_to_its_media_page_and_one_without_does_not(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        items = [
            in_jellyfin(tv, "Alpha Show", id="alpha", tmdb_id="1399"),
            in_jellyfin(tv, "Hotel Show", id="hotel"),
        ]

        shown = await wall(session, "tv", items)

        assert [(row.media_id, row.kind) for row in shown.titles] == [
            ("tv:1399", MediaKind.TV),
            ("", MediaKind.TV),
        ]

    async def test_a_film_library_holds_films(self, session: AsyncSession) -> None:
        movies = await route(session, "movies", collection_type=CollectionType.MOVIES)
        items = [
            in_jellyfin(movies, "Echo Movie", id="echo", tmdb_id="27205", kind=MediaKind.MOVIE)
        ]

        (shown,) = (await wall(session, "movies", items)).titles

        assert (shown.media_id, shown.kind) == ("movie:27205", MediaKind.MOVIE)

    async def test_a_large_library_comes_a_page_at_a_time(self, session: AsyncSession) -> None:
        tv = await route(session)
        items = [
            in_jellyfin(tv, f"Show {index:03d}", id=f"show-{index}")
            for index in range(PAGE_SIZE + 3)
        ]

        first = await wall(session, "tv", items)
        second = await wall(session, "tv", items, page=2)

        assert (len(first.titles), first.total) == (PAGE_SIZE, PAGE_SIZE + 3)
        assert [row.title for row in second.titles] == [
            f"Show {index:03d}" for index in range(PAGE_SIZE, PAGE_SIZE + 3)
        ]
        assert (second.page, second.total) == (2, PAGE_SIZE + 3)

    async def test_a_page_past_the_end_is_empty_not_an_error(self, session: AsyncSession) -> None:
        tv = await route(session)

        shown = await wall(session, "tv", [in_jellyfin(tv, "Alpha Show", id="alpha")], page=5)

        assert (shown.titles, shown.total) == ((), 1)

    async def test_jellyfin_is_not_asked_for_the_whole_library_when_berth_has_nothing_there(
        self, session: AsyncSession
    ) -> None:
        """整份清單只為了比對 Berth 經手的作品。一部都沒有時，一頁一個請求就夠。"""
        tv = await route(session)
        target = tv.jellyfin_library_id
        access, jellyfin = await access_for(session, [in_jellyfin(tv, "Alpha Show", id="alpha")])

        await read_wall(session, access, target, page=1, query=WallQuery())

        assert jellyfin.browse_queries == [(VIEWER, target)]

    async def test_the_wall_is_sorted_and_filtered_as_asked_but_berths_own_list_is_not(
        self, session: AsyncSession
    ) -> None:
        """排序與類型、年份只套在 Jellyfin 那一頁：「還沒進 Jellyfin」那一條與「待審」「Unmatched」
        是 Berth 的清單，Jellyfin 的類型套不上（票 06，使用者拍板）。"""
        tv = await route(session)
        spy = await title(session)
        await job(session, spy, tv, JobState.REVIEW, hash="a" * 40)
        items = [
            in_jellyfin(tv, "Alpha Show", id="alpha", year=2022),
            in_jellyfin(tv, "Bravo Show", id="bravo", year=2020),
            in_jellyfin(tv, "Charlie Show", id="charlie", year=2020),
        ]
        access, jellyfin = await access_for(session, items)
        jellyfin.metadata = {
            "bravo": ItemMetadata(sort_values={"CommunityRating": 6.0}),
            "charlie": ItemMetadata(sort_values={"CommunityRating": 9.0}),
        }
        query = WallQuery(
            sort=LibrarySort.COMMUNITY_RATING, order=SortOrder.DESCENDING, years=(2020,)
        )

        shown = await read_wall(session, access, tv.jellyfin_library_id, page=1, query=query)

        assert ([row.title for row in shown.titles], shown.total) == (
            ["Charlie Show", "Bravo Show"],
            2,
        )
        assert [row.media_id for row in shown.tracked] == [spy.id]

    async def test_a_sort_this_library_does_not_offer_asks_jellyfin_nothing_at_all(
        self, session: AsyncSession
    ) -> None:
        """牆與整份清單是同時問的：拒絕要在兩個請求都還沒送出去之前。"""
        tv = await route(session)
        await job(session, await title(session), tv, JobState.REVIEW)
        access, jellyfin = await access_for(session, [in_jellyfin(tv, "Alpha Show", id="alpha")])
        film_only = WallQuery(sort=LibrarySort.DATE_PLAYED)

        with pytest.raises(SortNotOfferedError):
            await read_wall(session, access, tv.jellyfin_library_id, page=1, query=film_only)

        assert jellyfin.browse_queries == []


class TestTrackedOnTheWall:
    async def test_a_berth_title_jellyfin_has_carries_its_state_under_jellyfins_name(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        spy = await title(session, name_zh="間諜家家酒", seasons=(season(1, aired=4),))
        await linked(session, spy, tv, item="episode-1", series="spy")
        items = [in_jellyfin(tv, "SPY×FAMILY", id="spy", tmdb_id="120089")]

        shown = await wall(session, "tv", items)

        (on_wall,) = shown.titles
        assert (on_wall.title, on_wall.media_id) == ("SPY×FAMILY", "tv:120089")
        assert on_wall.tracking is not None
        assert (on_wall.tracking.status, on_wall.tracking.imported, on_wall.tracking.aired) == (
            InventoryStatus.PARTIAL,
            1,
            4,
        )
        (listed,) = shown.tracked
        assert (listed.title, listed.presence, listed.jellyfin_item_id) == (
            "SPY×FAMILY",
            JellyfinPresence.FOUND,
            "spy",
        )

    async def test_a_matching_tmdb_id_is_enough_without_a_series_id_in_the_ledger(
        self, session: AsyncSession
    ) -> None:
        """票 13 留下的缺口：反查找到了集卻沒有 Series id，卡片一直說還在掃描。Jellyfin 的作品
        本來就帶著 TMDB id，所以它對得上。"""
        tv = await route(session)
        spy = await title(session)
        await linked(session, spy, tv, item="episode-1")
        items = [in_jellyfin(tv, "SPY×FAMILY", id="spy", tmdb_id="120089")]

        shown = await wall(session, "tv", items)

        assert shown.titles[0].tracking is not None
        assert shown.tracked[0].presence is JellyfinPresence.FOUND

    async def test_the_ledger_finds_a_title_jellyfin_knows_by_no_tmdb_id(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        spy = await title(session)
        await linked(session, spy, tv, item="episode-1", series="spy")
        items = [in_jellyfin(tv, "SPY x FAMILY", id="spy")]

        shown = await wall(session, "tv", items)

        assert (shown.titles[0].media_id, shown.titles[0].tracking is not None) == (
            "tv:120089",
            True,
        )
        assert shown.tracked[0].jellyfin_item_id == "spy"

    async def test_a_film_is_matched_by_its_movie(self, session: AsyncSession) -> None:
        movies = await route(session, "movies", collection_type=CollectionType.MOVIES)
        oppenheimer = await film(session)
        await linked(session, oppenheimer, movies, season_number=None, episode=None, item="opp")
        items = [in_jellyfin(movies, "Oppenheimer", id="opp", kind=MediaKind.MOVIE)]

        (shown,) = (await wall(session, "movies", items)).titles

        assert shown.tracking is not None
        assert (shown.media_id, shown.tracking.status) == ("movie:872585", InventoryStatus.COMPLETE)

    async def test_a_title_not_in_jellyfin_yet_is_listed_off_the_wall(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        spy = await title(session, name_zh="間諜家家酒")
        await job(session, spy, tv, JobState.DOWNLOADING)
        items = [in_jellyfin(tv, "Alpha Show", id="alpha", tmdb_id="1399")]

        shown = await wall(session, "tv", items)

        assert [row.tracking for row in shown.titles] == [None]
        (arriving,) = shown.tracked
        # 還沒進 Jellyfin：標題跟著 UI 語言（票 02），海報是 TMDB 的，沒有深連結。
        assert (arriving.media_id, arriving.title, arriving.title_en) == (
            "tv:120089",
            "間諜家家酒",
            "SPY x FAMILY",
        )
        assert arriving.poster_url == "https://image.tmdb.org/t/p/w342/120089.jpg"
        assert (arriving.presence, arriving.jellyfin_item_id) == (JellyfinPresence.NONE, "")
        assert arriving.tracking is not None
        assert arriving.tracking.status is InventoryStatus.DOWNLOADING

    async def test_a_title_on_every_route_into_this_library_is_listed_once(
        self, session: AsyncSession
    ) -> None:
        """一個媒體庫可以有兩條 Route（brief §4.3），同一部作品不因此出現兩次。"""
        tv = await route(session)
        second = await route(session, "tv-disk2", library=tv.jellyfin_library_id)
        spy = await title(session, seasons=(season(1, aired=2),))
        await linked(session, spy, tv, episode=1)
        await linked(session, spy, second, episode=2)

        (listed,) = (await wall(session, "tv")).tracked

        assert listed.tracking is not None
        assert (listed.tracking.imported, listed.tracking.status) == (2, InventoryStatus.COMPLETE)

    async def test_a_title_on_another_library_stays_off_this_one(
        self, session: AsyncSession
    ) -> None:
        tv, anime = await route(session, "tv"), await route(session, "anime")
        spy = await title(session)
        frieren = await title(session, tmdb_id=209867, name="Frieren")
        await job(session, spy, tv, JobState.DOWNLOADING, hash="a" * 40)
        await job(session, frieren, anime, JobState.IMPORTED, hash="b" * 40)
        items = [in_jellyfin(anime, "Frieren", id="frieren", tmdb_id="209867")]

        shown = await wall(session, "tv", items)

        assert [row.media_id for row in shown.tracked] == ["tv:120089"]
        assert shown.titles == ()

    async def test_files_under_the_route_count_without_a_job(self, session: AsyncSession) -> None:
        """帳本自己站得住（`models/ledger.py`）：Job 被刪掉了，媒體庫裡的檔案仍然在。"""
        tv = await route(session)
        spy = await title(session)
        await linked(session, spy, tv)

        assert (await card(session)).media_id == "tv:120089"

    async def test_files_count_under_a_route_whose_target_is_not_normalised(
        self, session: AsyncSession
    ) -> None:
        """Route 的目標是 Jellyfin 回報的、使用者打的字（`…//tv`），帳本卻是 importer 以
        `PurePosixPath` 組出來的正規路徑——前綴照字面比的話這個媒體庫認不出它（票 14a、15）。"""
        tv = await route(session)
        tv.target_path = "/data/library//tv/"
        await session.commit()
        spy = await title(session)
        entry = await linked(session, spy, tv)
        entry.target_path = str(PurePosixPath(entry.target_path))
        await session.commit()

        assert (await card(session)).media_id == "tv:120089"


class TestWatchState:
    async def test_each_title_on_the_wall_says_how_far_this_viewer_got(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        fake = FakeJellyfinClient(
            startup_wizard_completed=True, users={"viewer": "pw", "other": "pw"}
        )
        viewer = (await fake.authenticate("viewer", "pw")).user_id

        def episode(series: str, number: int) -> JellyfinItem:
            return JellyfinItem(
                id=f"{series}-e{number}",
                type=ITEM_EPISODE,
                name=f"{series} {number}",
                path=f"{tv.target_path}/{series}/S01E{number:02d}.mkv",
                tmdb_id="",
                series_id=series,
            )

        items = [
            in_jellyfin(tv, "alpha", id="alpha"),
            *(episode("alpha", number) for number in (1, 2, 3)),
            in_jellyfin(tv, "bravo", id="bravo"),
            *(episode("bravo", number) for number in (1, 2)),
            in_jellyfin(tv, "charlie", id="charlie"),
            episode("charlie", 1),
        ]
        # 別人看過的不算這個人的。
        fake.played = {"viewer": {"alpha-e1", "bravo-e1", "bravo-e2"}, "other": {"charlie-e1"}}
        access, _ = await access_for(session, items, jellyfin=fake, viewer=viewer)

        shown = await read_wall(session, access, tv.jellyfin_library_id, page=1, query=WallQuery())

        assert [(row.jellyfin_item_id, row.watch) for row in shown.titles] == [
            ("alpha", WatchState(played=False, progress=None, unplayed_episodes=2)),
            ("bravo", WatchState(played=True, progress=None, unplayed_episodes=None)),
            ("charlie", WatchState(played=False, progress=None, unplayed_episodes=1)),
        ]

    async def test_a_film_under_way_says_how_far(self, session: AsyncSession) -> None:
        movies = await route(session, "movies", collection_type=CollectionType.MOVIES)
        fake = FakeJellyfinClient(startup_wizard_completed=True, users={"viewer": "pw"})
        viewer = (await fake.authenticate("viewer", "pw")).user_id
        fake.positions = {"viewer": {"echo": 41.7}}
        items = [in_jellyfin(movies, "Echo Movie", id="echo", kind=MediaKind.MOVIE)]
        access, _ = await access_for(session, items, jellyfin=fake, viewer=viewer)

        (shown,) = (
            await read_wall(session, access, movies.jellyfin_library_id, page=1, query=WallQuery())
        ).titles

        assert shown.watch == WatchState(played=False, progress=42, unplayed_episodes=None)

    async def test_berths_own_list_says_nothing_about_watching(self, session: AsyncSession) -> None:
        """「還沒進 Jellyfin」那一條與兩個篩選取自整份清單（`library_index`），它不帶觀看紀錄：
        要帶就是整個媒體庫每一部都要一份，代價沒有量過，而那一份是 Berth 的工作清單（票 05）。
        Jellyfin 那一頁上的同一部照樣有。"""
        tv = await route(session)
        spy = await title(session)
        severance = await title(session, tmdb_id=95396, name="Severance")
        await linked(session, spy, tv, item="episode-1", series="spy")
        await job(session, severance, tv, JobState.DOWNLOADING)
        items = [in_jellyfin(tv, "SPY×FAMILY", id="spy", tmdb_id="120089")]

        shown = await wall(session, "tv", items)

        assert [row.watch for row in shown.tracked] == [None, None]
        assert shown.titles[0].watch == WatchState(
            played=False, progress=None, unplayed_episodes=None
        )


class TestStatus:
    async def test_every_aired_episode_in_is_imported(self, session: AsyncSession) -> None:
        tv = await route(session)
        spy = await title(session, seasons=(season(1, aired=2),))
        for episode in (1, 2):
            await linked(session, spy, tv, episode=episode)

        found = await tracking(session)

        assert (found.status, found.imported, found.aired) == (InventoryStatus.COMPLETE, 2, 2)

    async def test_an_aired_episode_still_missing_is_partial(self, session: AsyncSession) -> None:
        tv = await route(session)
        spy = await title(session, seasons=(season(1, aired=4),))
        await linked(session, spy, tv, episode=1)

        found = await tracking(session)

        assert (found.status, found.imported, found.aired) == (InventoryStatus.PARTIAL, 1, 4)

    async def test_specials_and_episodes_not_yet_aired_do_not_count(
        self, session: AsyncSession
    ) -> None:
        """TMDB 自己報的季數集數也不算 S00（票 04）；還沒播的集數缺著不是缺。"""
        tv = await route(session)
        spy = await title(session, seasons=(season(0, aired=3), season(1, aired=2, unaired=3)))
        for episode in (1, 2):
            await linked(session, spy, tv, episode=episode)

        found = await tracking(session)

        assert (found.status, found.imported, found.aired) == (InventoryStatus.COMPLETE, 2, 2)

    async def test_a_file_holding_two_episodes_counts_both(self, session: AsyncSession) -> None:
        """`S01E01-E02`（brief §6.6）。"""
        tv = await route(session)
        spy = await title(session, seasons=(season(1, aired=2),))
        await linked(session, spy, tv, episode=1, episode_end=2)

        assert (await tracking(session)).status is InventoryStatus.COMPLETE

    async def test_a_second_version_of_an_episode_is_not_a_second_episode(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        spy = await title(session, seasons=(season(1, aired=2),))
        await linked(session, spy, tv, episode=1, tags=Tags(resolution="1080p", group="A"))
        await linked(session, spy, tv, episode=1, tags=Tags(resolution="2160p", group="B"))

        assert (await tracking(session)).imported == 1

    async def test_a_job_on_its_way_is_downloading(self, session: AsyncSession) -> None:
        tv = await route(session)
        spy = await title(session)
        await linked(session, spy, tv)
        await job(session, spy, tv, JobState.DOWNLOADING)

        assert (await tracking(session)).status is InventoryStatus.DOWNLOADING

    async def test_a_plan_held_for_review_needs_you(self, session: AsyncSession) -> None:
        tv = await route(session)
        spy = await title(session)
        await job(session, spy, tv, JobState.IMPORTED, hash="a" * 40)
        await job(session, spy, tv, JobState.REVIEW, hash="b" * 40)

        assert (await tracking(session)).status is InventoryStatus.REVIEW

    async def test_a_failed_job_outranks_everything_else(self, session: AsyncSession) -> None:
        """紅色只代表阻擋：失敗那一筆在你動手之前不會自己好（The One Meaning Rule）。"""
        tv = await route(session)
        spy = await title(session)
        await job(session, spy, tv, JobState.REVIEW, hash="a" * 40)
        await job(session, spy, tv, JobState.IMPORT_FAILED, hash="b" * 40)

        assert (await tracking(session)).status is InventoryStatus.FAILED

    async def test_a_title_with_nothing_in_the_library_is_empty(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        spy = await title(session)
        await job(session, spy, tv, JobState.CLIENT_REMOVED)

        found = await tracking(session)

        assert (found.status, found.imported) == (InventoryStatus.EMPTY, 0)

    async def test_an_extra_alone_does_not_make_a_title_imported(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        spy = await title(session)
        await linked(session, spy, tv, action=PlanAction.EXTRA, season_number=None, episode=None)

        assert (await tracking(session)).status is InventoryStatus.EMPTY

    async def test_a_film_is_imported_once_its_feature_is_in(self, session: AsyncSession) -> None:
        movies = await route(session, "movies", collection_type=CollectionType.MOVIES)
        oppenheimer = await film(session)
        await linked(session, oppenheimer, movies, season_number=None, episode=None)
        await linked(
            session,
            oppenheimer,
            movies,
            season_number=None,
            episode=None,
            tags=Tags(resolution="2160p"),
        )

        found = await tracking(session, "movies")

        assert (found.status, found.versions) == (InventoryStatus.COMPLETE, 2)


async def counts(session: AsyncSession, slug: str = "tv") -> dict[ReviewKind, int]:
    """`slug` 那條 Route 指向的媒體庫上，「待審」「對不到」兩個篩選鍵的數字。"""
    target = await session.scalar(select(Route).where(Route.slug == slug))
    assert target is not None
    return await library_counts(session, target.jellyfin_library_id)


class TestFilters:
    """「待審」「對不到」兩個數字是審核佇列在這個媒體庫上的件數（M2 票 14，使用者拍板）：
    與那兩個篩選的清單同一支查詢（`services/review.library_counts`），數字與清單不會各說各的。"""

    async def test_an_unmatched_file_in_the_current_plan_is_counted(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        spy = await title(session)
        done = await job(session, spy, tv, JobState.IMPORTED)
        await plan(session, done, (PlanAction.IMPORT, 1, 1), (PlanAction.UNMATCHED, None, None))

        assert (await counts(session))[ReviewKind.UNMATCHED] == 1

    async def test_imports_waiting_for_a_look_are_counted_on_the_card(
        self, session: AsyncSession
    ) -> None:
        """medium 自動入庫的檔案（audit）在牆上要看得到，跨這部作品的每一筆 Job 加總（票 15）。"""
        tv = await route(session)
        spy = await title(session)
        for index, hash_ in enumerate(("a" * 40, "b" * 40), start=1):
            done = await job(session, spy, tv, JobState.IMPORTED, hash=hash_)
            row = await plan(
                session, done, (PlanAction.IMPORT, 1, index), (PlanAction.IMPORT, 1, 9)
            )
            first = await session.scalar(select(PlanItem).where(PlanItem.plan_id == row.id))
            assert first is not None
            first.audit = True
            await session.commit()

        assert (await tracking(session)).audits == 2

    async def test_an_estimate_made_while_downloading_counts_nothing(
        self, session: AsyncSession
    ) -> None:
        """pre-plan 沒讀過檔案本身（brief §5.1），下載完成之後會重算一份。"""
        tv = await route(session)
        spy = await title(session)
        busy = await job(session, spy, tv, JobState.DOWNLOADING)
        await plan(session, busy, (PlanAction.UNMATCHED, None, None), status=PlanStatus.PREPLAN)

        assert (await counts(session))[ReviewKind.UNMATCHED] == 0

    async def test_what_needs_you_is_counted_in_and_out_of_jellyfin(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session, "tv")
        second = await route(session, "tv-disk2", library=tv.jellyfin_library_id)
        movies = await route(session, "movies", collection_type=CollectionType.MOVIES)
        spy = await title(session)
        frieren = await title(session, tmdb_id=209867, name="Frieren")
        held = await job(session, spy, tv, JobState.REVIEW, hash="a" * 40)
        await plan(
            session, held, (PlanAction.UNMATCHED, None, None), status=PlanStatus.PENDING_REVIEW
        )
        done = await job(session, frieren, second, JobState.IMPORTED, hash="b" * 40)
        await plan(session, done, *[(PlanAction.UNMATCHED, None, None)] * 3)

        # 兩條 Route 指向同一個媒體庫：數字照樣都算進來。數的是件：Frieren 那一包三個對不到的
        # 檔案是三件；等審核的那一份裡對不到的檔案是那份 Plan 的一列，不另外算一件（`/review`
        # 同一個判定）。
        assert await counts(session) == {ReviewKind.PLAN: 1, ReviewKind.UNMATCHED: 3}
        assert (await counts(session, movies.slug))[ReviewKind.PLAN] == 0


class TestNotInJellyfinYet:
    async def test_a_file_still_scheduled_for_a_look_is_being_searched(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        spy = await title(session)
        await linked(session, spy, tv, resolve_after=datetime.now(UTC) + timedelta(minutes=2))

        found = await card(session)

        assert (found.presence, found.jellyfin_item_id) == (JellyfinPresence.SEARCHING, "")

    async def test_an_episode_found_without_its_series_is_still_being_searched(
        self, session: AsyncSession
    ) -> None:
        """Jellyfin 的牆上沒有它（TMDB id 也對不上）時，一集的 id 不是作品的連結
        （票 13 shape §7）。"""
        tv = await route(session)
        spy = await title(session)
        await linked(session, spy, tv, item="episode-1")

        found = await card(session)

        assert (found.presence, found.jellyfin_item_id) == (JellyfinPresence.SEARCHING, "")

    async def test_every_try_used_up_is_lost(self, session: AsyncSession) -> None:
        tv = await route(session)
        spy = await title(session)
        await linked(session, spy, tv, attempts=6)

        assert (await card(session)).presence is JellyfinPresence.LOST

    async def test_nothing_imported_means_nothing_to_find(self, session: AsyncSession) -> None:
        tv = await route(session)
        spy = await title(session)
        await job(session, spy, tv, JobState.DOWNLOADING)

        assert (await card(session)).presence is JellyfinPresence.NONE

    async def test_a_series_jellyfin_no_longer_lists_is_not_linked(
        self, session: AsyncSession
    ) -> None:
        """帳本記著 Series id，Jellyfin 卻不再列出它（刪掉了、改了資料夾）：
        不給一條會 404 的連結。"""
        tv = await route(session)
        spy = await title(session)
        await linked(session, spy, tv, item="episode-1", series="gone")

        found = await card(session)

        assert (found.jellyfin_item_id, found.presence) == ("", JellyfinPresence.SEARCHING)


class TestJellyfinAddress:
    """深連結的主機（使用者拍板：選填對外網址 + 自動推導，Seerr 的 `externalHostname` 慣例）。"""

    async def test_an_address_the_admin_typed_wins(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots)
        await set_public_url(session, "https://jellyfin.example.com/", published_port=8096)

        web = await jellyfin_web(session, published_port=8096)

        assert (web.url, web.port) == ("https://jellyfin.example.com", None)

    async def test_an_existing_jellyfin_is_reached_at_the_address_the_user_gave(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots, origin=ServiceOrigin.EXISTING)
        settings = await read_settings(session, JellyfinSettings)
        settings.base_url = "http://nas.local:8096"
        await write_settings(session, settings)
        await session.commit()

        web = await jellyfin_web(session, published_port=8096)

        assert (web.url, web.port) == ("http://nas.local:8096", None)

    async def test_a_bundled_jellyfin_is_reached_on_the_browsers_own_host(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`http://jellyfin:8096` 是 compose 內網的名字，瀏覽器解不到它；主機名只有前端知道。"""
        await arrange(session, roots)

        web = await jellyfin_web(session, published_port=8096)

        assert (web.url, web.port) == ("", 8096)

    async def test_a_bundled_jellyfin_is_reached_on_the_port_it_is_published_on(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`JELLYFIN_PORT=18096` 發佈成 `18096:8096`：`base_url` 裡的 8096 是容器內的 port，
        瀏覽器開那一個會開到同一台機器上另一台 Jellyfin（票 06b 的起因）。"""
        await arrange(session, roots)

        web = await jellyfin_web(session, published_port=18096)

        assert (web.url, web.port) == ("", 18096)

    async def test_clearing_the_address_goes_back_to_working_it_out(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots)
        await set_public_url(session, "https://jellyfin.example.com", published_port=8096)

        await set_public_url(session, "  ", published_port=8096)

        assert (await jellyfin_web(session, published_port=8096)).port == 8096

    async def test_an_address_that_is_not_http_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots)

        with pytest.raises(PublicUrlRejectedError):
            await set_public_url(session, "jellyfin.example.com", published_port=8096)
