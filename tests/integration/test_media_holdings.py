"""Media 詳情的最後一塊：各集入庫狀態、檔案清單、多版本並存。

票 13、`.scratch/m1/library-shape.md` §5。

詳情頁回答的是**一部作品**的事，所以這裡跨 Route：同一部劇集可能一季進 TV、一季進 Anime。
資料列直接擺進去，理由與 `test_inventory.py` 相同；那一份的安排在這裡照用。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import (
    CollectionType,
    EpisodeStatus,
    JellyfinPresence,
    JobState,
    LedgerStatus,
    PlanAction,
    PlanStatus,
    Tags,
)
from berth.models import Media
from berth.services.media import MediaView, read_media
from tests.integration.factories import FakeClientFactory
from tests.integration.test_inventory import film, job, linked, plan, route, season, title

pytestmark = pytest.mark.asyncio


async def detail(session: AsyncSession, media: Media) -> MediaView:
    """快照是剛寫下的，所以 `read_media` 不會去問 TMDB——替身什麼都不必會。"""
    return await read_media(session, FakeClientFactory(), media.id)


def statuses(view: MediaView, season_number: int = 1) -> dict[int, EpisodeStatus]:
    found = next(row for row in view.seasons if row.season_number == season_number)
    return {episode.episode_number: episode.status for episode in found.episodes}


class TestEpisodes:
    async def test_each_episode_says_where_it_stands(self, session: AsyncSession) -> None:
        """五種：已入庫 · 下載中 · 卡住 · 缺 · 未播出（使用者拍板）。"""
        tv = await route(session)
        spy = await title(session, seasons=(season(1, aired=4, unaired=1),))
        await linked(session, spy, tv, episode=1)
        coming = await job(session, spy, tv, JobState.DOWNLOADING, hash="a" * 40)
        await plan(session, coming, (PlanAction.IMPORT, 1, 2), status=PlanStatus.PREPLAN)
        held = await job(session, spy, tv, JobState.REVIEW, hash="b" * 40)
        await plan(session, held, (PlanAction.IMPORT, 1, 3), status=PlanStatus.PENDING_REVIEW)

        assert statuses(await detail(session, spy)) == {
            1: EpisodeStatus.IMPORTED,
            2: EpisodeStatus.DOWNLOADING,
            3: EpisodeStatus.STUCK,
            4: EpisodeStatus.MISSING,
            5: EpisodeStatus.UNAIRED,
        }

    async def test_a_failed_import_holds_its_episodes_as_stuck(self, session: AsyncSession) -> None:
        tv = await route(session)
        spy = await title(session, seasons=(season(1, aired=1),))
        failed = await job(session, spy, tv, JobState.IMPORT_FAILED)
        await plan(session, failed, (PlanAction.IMPORT, 1, 1), status=PlanStatus.FAILED)

        assert statuses(await detail(session, spy)) == {1: EpisodeStatus.STUCK}

    async def test_being_in_the_library_outranks_a_job_bringing_it_again(
        self, session: AsyncSession
    ) -> None:
        """第二個版本在下載，第一個版本已經看得了——那一集就是已入庫。"""
        tv = await route(session)
        spy = await title(session, seasons=(season(1, aired=1),))
        await linked(session, spy, tv, episode=1)
        again = await job(session, spy, tv, JobState.DOWNLOADING)
        await plan(session, again, (PlanAction.IMPORT, 1, 1), status=PlanStatus.PREPLAN)

        assert statuses(await detail(session, spy)) == {1: EpisodeStatus.IMPORTED}

    async def test_a_job_without_a_file_list_yet_claims_no_episode(
        self, session: AsyncSession
    ) -> None:
        """送單了但還沒有檔案清單：還不知道那一包蓋到哪幾集，照實說缺。"""
        tv = await route(session)
        spy = await title(session, seasons=(season(1, aired=1),))
        await job(session, spy, tv, JobState.SUBMITTED)

        assert statuses(await detail(session, spy)) == {1: EpisodeStatus.MISSING}

    async def test_an_old_plan_of_a_finished_job_claims_nothing(
        self, session: AsyncSession
    ) -> None:
        """入庫完成的那一份計劃不是「在路上」——它蓋到的集數要看帳本。"""
        tv = await route(session)
        spy = await title(session, seasons=(season(1, aired=1),))
        done = await job(session, spy, tv, JobState.IMPORTED)
        await plan(session, done, (PlanAction.IMPORT, 1, 1))

        assert statuses(await detail(session, spy)) == {1: EpisodeStatus.MISSING}

    async def test_a_season_counts_what_aired_and_how_much_of_it_is_in(
        self, session: AsyncSession
    ) -> None:
        """與媒體庫卡片同一個分母：播出了的集數。還沒播卻先入庫的那一集不算進去（code-review）。"""
        tv = await route(session)
        spy = await title(session, seasons=(season(1, aired=2, unaired=1),))
        await linked(session, spy, tv, episode=1)
        await linked(session, spy, tv, episode=3)

        (found,) = (await detail(session, spy)).seasons

        assert (found.imported, found.aired) == (1, 2)


class TestAwaitingReview:
    """`user` 碰到停在 `review` 的那一筆只能等，詳情頁要說得出「等管理員審核」（M2 票 06）。"""

    async def test_it_counts_the_downloads_held_for_review(self, session: AsyncSession) -> None:
        tv = await route(session)
        spy = await title(session, seasons=(season(1, aired=2),))
        await job(session, spy, tv, JobState.REVIEW, hash="a" * 40)
        await job(session, spy, tv, JobState.IMPORT_FAILED, hash="b" * 40)
        await job(session, spy, tv, JobState.DOWNLOADING, hash="c" * 40)

        # 入庫失敗也卡著集數，但那不是「等審核」——它要的是重試，不是一個決定。
        assert (await detail(session, spy)).awaiting_review == 1

    async def test_nothing_held_is_zero(self, session: AsyncSession) -> None:
        tv = await route(session)
        spy = await title(session, seasons=(season(1, aired=1),))
        await job(session, spy, tv, JobState.IMPORTED)

        assert (await detail(session, spy)).awaiting_review == 0


class TestFiles:
    async def test_a_file_carries_its_episode_tags_target_and_ledger_state(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        spy = await title(session)
        entry = await linked(session, spy, tv, episode=2, item="episode-2", series="series-1")

        (file,) = (await detail(session, spy)).files

        assert (file.action, file.season, file.episode_start, file.episode_end) == (
            PlanAction.IMPORT,
            1,
            2,
            None,
        )
        assert file.tags == "[1080p][Group]"
        assert file.target_path == entry.target_path
        assert (file.status, file.presence) == (LedgerStatus.OK, JellyfinPresence.FOUND)

    async def test_a_file_still_waiting_on_jellyfin_says_when_it_looks_next(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        spy = await title(session)
        upcoming = datetime.now(UTC) + timedelta(minutes=2)
        await linked(session, spy, tv, resolve_after=upcoming, attempts=1)

        (file,) = (await detail(session, spy)).files

        assert (file.presence, file.resolve_after, file.resolve_attempts) == (
            JellyfinPresence.SEARCHING,
            upcoming,
            1,
        )

    async def test_a_file_jellyfin_never_showed_is_lost(self, session: AsyncSession) -> None:
        tv = await route(session)
        spy = await title(session)
        await linked(session, spy, tv, attempts=6)

        (file,) = (await detail(session, spy)).files

        assert file.presence is JellyfinPresence.LOST

    async def test_a_subtitle_is_listed_but_never_looked_up(self, session: AsyncSession) -> None:
        """字幕是串流、特典掛在作品底下：它們在 Jellyfin 裡不是自己查得到的 item（票 12）。"""
        tv = await route(session)
        spy = await title(session)
        await linked(session, spy, tv, action=PlanAction.SUBTITLE)

        (file,) = (await detail(session, spy)).files

        assert (file.action, file.presence) == (PlanAction.SUBTITLE, JellyfinPresence.NONE)

    async def test_files_are_listed_in_episode_order(self, session: AsyncSession) -> None:
        tv = await route(session)
        spy = await title(session, seasons=(season(0, aired=1), season(1, aired=3)))
        await linked(session, spy, tv, episode=3)
        await linked(session, spy, tv, season_number=0, episode=1)
        await linked(session, spy, tv, episode=1)

        files = (await detail(session, spy)).files

        assert [(file.season, file.episode_start) for file in files] == [(0, 1), (1, 1), (1, 3)]

    async def test_an_unmatched_file_is_listed_where_it_stays(self, session: AsyncSession) -> None:
        """Unmatched 不入庫也不搬走，留在 complete 原位（brief §7.4），所以它不在帳本裡。"""
        tv = await route(session)
        spy = await title(session)
        done = await job(session, spy, tv, JobState.IMPORTED)
        await plan(session, done, (PlanAction.IMPORT, 1, 1), (PlanAction.UNMATCHED, None, None))

        (stray,) = (await detail(session, spy)).unmatched

        assert (stray.rel_path, stray.job_hash) == ("file-1.mkv", done.hash)

    async def test_an_estimate_lists_no_unmatched_file(self, session: AsyncSession) -> None:
        tv = await route(session)
        spy = await title(session)
        busy = await job(session, spy, tv, JobState.DOWNLOADING)
        await plan(session, busy, (PlanAction.UNMATCHED, None, None), status=PlanStatus.PREPLAN)

        assert (await detail(session, spy)).unmatched == ()


class TestVersions:
    async def test_a_version_is_named_by_jellyfin_not_by_berth(self, session: AsyncSession) -> None:
        """版本名是 Jellyfin 算的，反查時抄進帳本（brief §7.7、§20.9、票 14b）。

        12.0 起它是「去掉各版本檔名的共同前綴」剩下的部分，算法跟標題的標點有關，12.0 與 12.1
        還不一樣——自己重算就要同時追三種算法。票 13 原本的「整個檔名主幹」是 10.x + 插件的樣子。
        """
        tv = await route(session)
        spy = await title(session)
        await linked(
            session,
            spy,
            tv,
            episode=1,
            tags=Tags(resolution="1080p", group="Lilith"),
            version_name="Winter Is Coming [1080p][Lilith]",
        )
        await linked(
            session,
            spy,
            tv,
            episode=1,
            tags=Tags(resolution="2160p", group="Sakurato"),
            version_name="Winter Is Coming [2160p][Sakurato]",
        )
        await linked(session, spy, tv, episode=2)

        (group,) = (await detail(session, spy)).versions

        assert (group.season, group.episode_start) == (1, 1)
        assert [row.name for row in group.versions] == [
            "Winter Is Coming [1080p][Lilith]",
            "Winter Is Coming [2160p][Sakurato]",
        ]

    async def test_a_version_jellyfin_has_not_indexed_yet_only_has_its_tags(
        self, session: AsyncSession
    ) -> None:
        """還沒收錄就沒有版本名。畫面照實說，不自己算一個（票 14b）。"""
        movies = await route(session, "movies", collection_type=CollectionType.MOVIES)
        oppenheimer = await film(session)
        await linked(
            session,
            oppenheimer,
            movies,
            season_number=None,
            episode=None,
            tags=Tags(resolution="1080p"),
        )
        await linked(
            session,
            oppenheimer,
            movies,
            season_number=None,
            episode=None,
            tags=Tags(resolution="2160p"),
        )

        (group,) = (await detail(session, oppenheimer)).versions

        assert [(row.name, row.tags) for row in group.versions] == [
            ("", "[1080p]"),
            ("", "[2160p]"),
        ]

    async def test_a_single_version_is_not_a_group(self, session: AsyncSession) -> None:
        tv = await route(session)
        spy = await title(session)
        await linked(session, spy, tv, episode=1)
        await linked(session, spy, tv, action=PlanAction.SUBTITLE, episode=1)

        assert (await detail(session, spy)).versions == ()

    async def test_the_same_episode_in_two_routes_is_not_two_versions(
        self, session: AsyncSession
    ) -> None:
        """兩條 Route 是兩個 Jellyfin 媒體庫、兩個條目。

        版本選單只合併同一個資料夾裡的（code-review 抓到的）。
        """
        tv, anime = await route(session, "tv"), await route(session, "anime")
        spy = await title(session)
        await linked(session, spy, tv, episode=1, tags=Tags(resolution="1080p", group="A"))
        await linked(session, spy, anime, episode=1, tags=Tags(resolution="2160p", group="B"))

        assert (await detail(session, spy)).versions == ()
