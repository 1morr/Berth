"""媒體庫：一條 Route 上 Berth 經手的作品與它們的入庫狀態（票 13、`.scratch/m1/library-shape.md`）。

四組斷言：**牆上有誰**（這條 Route 上有 Job 的作品，加上檔案落在它底下的）、**一格說什麼**
（六種狀態依序取第一個成立的、`N / M 集`）、**兩個篩選**（待審、Unmatched），以及
**Jellyfin 那一行**（找到了、還在找、找不到）。

資料列是直接擺進去的：送單、規劃、入庫與反查各自有自己的測試，這裡要的是「帳本與 Job
長成這樣的時候，牆上說什麼」，而那些組合靠真的跑一遍管線湊不齊。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import (
    CollectionType,
    Confidence,
    EpisodeSnapshot,
    InventoryStatus,
    JellyfinPresence,
    JobState,
    JobTrigger,
    MediaKind,
    MediaSnapshot,
    PlanAction,
    PlanStatus,
    SeasonSnapshot,
    ServiceOrigin,
    Tags,
)
from berth.models import JellyfinSettings, Job, LedgerEntry, Media, Plan, PlanItem, Route
from berth.services.deeplink import PublicUrlRejectedError, jellyfin_web, set_public_url
from berth.services.inventory import InventoryItem, list_inventories, read_inventory
from berth.services.settings import read_settings, write_settings
from tests.integration.arrange import arrange

pytestmark = pytest.mark.asyncio

TODAY = datetime.now(UTC).date()


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
            title=name,
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
) -> Route:
    row = Route(
        slug=slug,
        name=slug.title(),
        jellyfin_library_id=f"library-{slug}",
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
    """`items` 是 `(處置, 季, 集)`。"""
    row = Plan(job_hash=of.hash, status=status)
    session.add(row)
    await session.flush()
    session.add_all(
        PlanItem(
            plan_id=row.id,
            rel_path=f"file-{index}.mkv",
            action=action,
            media_id=of.media_id,
            season=number,
            episode_start=episode,
            confidence=Confidence.HIGH,
        )
        for index, (action, number, episode) in enumerate(items)
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


async def only(session: AsyncSession, slug: str = "tv") -> list[InventoryItem]:
    view = await read_inventory(session, slug)
    assert view is not None
    return list(view.items)


async def card(session: AsyncSession, slug: str = "tv") -> InventoryItem:
    items = await only(session, slug)
    assert len(items) == 1
    return items[0]


class TestWall:
    async def test_every_title_with_a_job_on_this_route_is_on_the_wall(
        self, session: AsyncSession
    ) -> None:
        """包含一個檔案都還沒入庫的（使用者拍板）——否則「有待審」找不到從沒入庫過的作品。"""
        tv, anime = await route(session, "tv"), await route(session, "anime")
        spy = await title(session)
        frieren = await title(session, tmdb_id=209867, name="Frieren")
        await job(session, spy, tv, JobState.DOWNLOADING, hash="a" * 40)
        await job(session, frieren, anime, JobState.IMPORTED, hash="b" * 40)

        assert [row.media_id for row in await only(session, "tv")] == ["tv:120089"]

    async def test_files_under_the_route_put_a_title_on_the_wall_without_a_job(
        self, session: AsyncSession
    ) -> None:
        """帳本自己站得住（`models/ledger.py`）：Job 被刪掉了，媒體庫裡的檔案仍然在。"""
        tv = await route(session)
        spy = await title(session)
        await linked(session, spy, tv)

        assert (await card(session)).media_id == "tv:120089"

    async def test_files_count_under_a_route_whose_target_is_not_normalised(
        self, session: AsyncSession
    ) -> None:
        """Route 的目標是 Jellyfin 回報的、使用者打的字（`…//tv`），帳本卻是 importer 以
        `PurePosixPath` 組出來的正規路徑——前綴照字面比的話，這條 Route 的牆是空的（票 14a 修掉
        同一個問題的 `_usage_of`，票 15 收掉這一處）。"""
        tv = await route(session)
        tv.target_path = "/data/library//tv/"
        await session.commit()
        spy = await title(session)
        entry = await linked(session, spy, tv)
        entry.target_path = str(PurePosixPath(entry.target_path))
        await session.commit()

        assert (await card(session)).media_id == "tv:120089"

    async def test_an_unknown_route_has_no_wall(self, session: AsyncSession) -> None:
        assert await read_inventory(session, "nowhere") is None


class TestStatus:
    async def test_every_aired_episode_in_is_imported(self, session: AsyncSession) -> None:
        tv = await route(session)
        spy = await title(session, seasons=(season(1, aired=2),))
        for episode in (1, 2):
            await linked(session, spy, tv, episode=episode)

        found = await card(session)

        assert (found.status, found.imported, found.aired) == (InventoryStatus.COMPLETE, 2, 2)

    async def test_an_aired_episode_still_missing_is_partial(self, session: AsyncSession) -> None:
        tv = await route(session)
        spy = await title(session, seasons=(season(1, aired=4),))
        await linked(session, spy, tv, episode=1)

        found = await card(session)

        assert (found.status, found.imported, found.aired) == (InventoryStatus.PARTIAL, 1, 4)

    async def test_specials_and_episodes_not_yet_aired_do_not_count(
        self, session: AsyncSession
    ) -> None:
        """TMDB 自己報的季數集數也不算 S00（票 04）；還沒播的集數缺著不是缺。"""
        tv = await route(session)
        spy = await title(session, seasons=(season(0, aired=3), season(1, aired=2, unaired=3)))
        for episode in (1, 2):
            await linked(session, spy, tv, episode=episode)

        found = await card(session)

        assert (found.status, found.imported, found.aired) == (InventoryStatus.COMPLETE, 2, 2)

    async def test_a_file_holding_two_episodes_counts_both(self, session: AsyncSession) -> None:
        """`S01E01-E02`（brief §6.6）。"""
        tv = await route(session)
        spy = await title(session, seasons=(season(1, aired=2),))
        await linked(session, spy, tv, episode=1, episode_end=2)

        assert (await card(session)).status is InventoryStatus.COMPLETE

    async def test_a_second_version_of_an_episode_is_not_a_second_episode(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        spy = await title(session, seasons=(season(1, aired=2),))
        await linked(session, spy, tv, episode=1, tags=Tags(resolution="1080p", group="A"))
        await linked(session, spy, tv, episode=1, tags=Tags(resolution="2160p", group="B"))

        assert (await card(session)).imported == 1

    async def test_a_job_on_its_way_is_downloading(self, session: AsyncSession) -> None:
        tv = await route(session)
        spy = await title(session)
        await linked(session, spy, tv)
        await job(session, spy, tv, JobState.DOWNLOADING)

        assert (await card(session)).status is InventoryStatus.DOWNLOADING

    async def test_a_plan_held_for_review_needs_you(self, session: AsyncSession) -> None:
        tv = await route(session)
        spy = await title(session)
        await job(session, spy, tv, JobState.IMPORTED, hash="a" * 40)
        await job(session, spy, tv, JobState.REVIEW, hash="b" * 40)

        found = await card(session)

        assert (found.status, found.needs_review) == (InventoryStatus.REVIEW, True)

    async def test_a_failed_job_outranks_everything_else(self, session: AsyncSession) -> None:
        """紅色只代表阻擋：失敗那一筆在你動手之前不會自己好（The One Meaning Rule）。"""
        tv = await route(session)
        spy = await title(session)
        await job(session, spy, tv, JobState.REVIEW, hash="a" * 40)
        await job(session, spy, tv, JobState.IMPORT_FAILED, hash="b" * 40)

        assert (await card(session)).status is InventoryStatus.FAILED

    async def test_a_title_with_nothing_in_the_library_is_empty(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        spy = await title(session)
        await job(session, spy, tv, JobState.CLIENT_REMOVED)

        found = await card(session)

        assert (found.status, found.imported) == (InventoryStatus.EMPTY, 0)

    async def test_an_extra_alone_does_not_make_a_title_imported(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        spy = await title(session)
        await linked(session, spy, tv, action=PlanAction.EXTRA, season_number=None, episode=None)

        assert (await card(session)).status is InventoryStatus.EMPTY

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

        found = await card(session, "movies")

        assert (found.status, found.versions) == (InventoryStatus.COMPLETE, 2)


class TestFilters:
    async def test_an_unmatched_file_in_the_current_plan_flags_the_title(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        spy = await title(session)
        done = await job(session, spy, tv, JobState.IMPORTED)
        await plan(session, done, (PlanAction.IMPORT, 1, 1), (PlanAction.UNMATCHED, None, None))

        assert (await card(session)).has_unmatched is True

    async def test_an_estimate_made_while_downloading_flags_nothing(
        self, session: AsyncSession
    ) -> None:
        """pre-plan 沒讀過檔案本身（brief §5.1），下載完成之後會重算一份。"""
        tv = await route(session)
        spy = await title(session)
        busy = await job(session, spy, tv, JobState.DOWNLOADING)
        await plan(session, busy, (PlanAction.UNMATCHED, None, None), status=PlanStatus.PREPLAN)

        assert (await card(session)).has_unmatched is False

    async def test_the_route_list_counts_titles_and_what_needs_you(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session, "tv")
        await route(session, "old", enabled=False)
        spy = await title(session)
        frieren = await title(session, tmdb_id=209867, name="Frieren")
        held = await job(session, spy, tv, JobState.REVIEW, hash="a" * 40)
        await plan(
            session, held, (PlanAction.UNMATCHED, None, None), status=PlanStatus.PENDING_REVIEW
        )
        await job(session, frieren, tv, JobState.IMPORTED, hash="b" * 40)

        rows = {row.slug: row for row in await list_inventories(session)}

        assert (rows["tv"].titles, rows["tv"].review, rows["tv"].unmatched) == (2, 1, 1)
        # 停用的 Route 仍然列出來：已經入庫的東西還在它底下。
        assert (rows["old"].enabled, rows["old"].titles) == (False, 0)


class TestJellyfin:
    async def test_a_found_series_links_to_the_series_not_the_episode(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        spy = await title(session)
        await linked(session, spy, tv, item="episode-1", series="series-1")

        found = await card(session)

        assert (found.presence, found.jellyfin_item_id) == (JellyfinPresence.FOUND, "series-1")

    async def test_a_found_film_links_to_its_movie(self, session: AsyncSession) -> None:
        movies = await route(session, "movies", collection_type=CollectionType.MOVIES)
        oppenheimer = await film(session)
        await linked(session, oppenheimer, movies, season_number=None, episode=None, item="movie-1")

        found = await card(session, "movies")

        assert (found.presence, found.jellyfin_item_id) == (JellyfinPresence.FOUND, "movie-1")

    async def test_a_file_still_scheduled_for_a_look_is_being_searched(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        spy = await title(session)
        await linked(session, spy, tv, resolve_after=datetime.now(UTC) + timedelta(minutes=2))

        found = await card(session)

        assert (found.presence, found.jellyfin_item_id) == (JellyfinPresence.SEARCHING, "")

    async def test_an_episode_found_without_its_series_gives_no_link(
        self, session: AsyncSession
    ) -> None:
        """連到某一集的連結不是「該作品」（shape brief §7）。"""
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

    async def test_one_found_file_is_enough_for_a_link(self, session: AsyncSession) -> None:
        tv = await route(session)
        spy = await title(session)
        await linked(session, spy, tv, episode=1, item="episode-1", series="series-1")
        await linked(session, spy, tv, episode=2, attempts=6)

        assert (await card(session)).presence is JellyfinPresence.FOUND

    async def test_nothing_imported_means_nothing_to_find(self, session: AsyncSession) -> None:
        tv = await route(session)
        spy = await title(session)
        await job(session, spy, tv, JobState.DOWNLOADING)

        assert (await card(session)).presence is JellyfinPresence.NONE


class TestJellyfinAddress:
    """深連結的主機（使用者拍板：選填對外網址 + 自動推導，Seerr 的 `externalHostname` 慣例）。"""

    async def test_an_address_the_admin_typed_wins(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots)
        await set_public_url(session, "https://jellyfin.example.com/")

        web = await jellyfin_web(session)

        assert (web.url, web.port) == ("https://jellyfin.example.com", None)

    async def test_an_existing_jellyfin_is_reached_at_the_address_the_user_gave(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots, origin=ServiceOrigin.EXISTING)
        settings = await read_settings(session, JellyfinSettings)
        settings.base_url = "http://nas.local:8096"
        await write_settings(session, settings)
        await session.commit()

        web = await jellyfin_web(session)

        assert (web.url, web.port) == ("http://nas.local:8096", None)

    async def test_a_bundled_jellyfin_is_reached_on_the_browsers_own_host(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`http://jellyfin:8096` 是 compose 內網的名字，瀏覽器解不到它；主機名只有前端知道。"""
        await arrange(session, roots)

        web = await jellyfin_web(session)

        assert (web.url, web.port) == ("", 8096)

    async def test_clearing_the_address_goes_back_to_working_it_out(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots)
        await set_public_url(session, "https://jellyfin.example.com")

        await set_public_url(session, "  ")

        assert (await jellyfin_web(session)).port == 8096

    async def test_an_address_that_is_not_http_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots)

        with pytest.raises(PublicUrlRejectedError):
            await set_public_url(session, "jellyfin.example.com")
