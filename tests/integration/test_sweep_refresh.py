"""巡檢前刷新（M5.5 票 11，spec〈範圍〉「巡檢前刷新」）。

巡檢的交易之前、獨立 session 刷新訂閱作品的 TMDB 快照（`refresh_watched`），回刷新失敗的作品；
那幾部這一輪不開也不收（`sweep_once(unrefreshed=...)`）。跳過 6 小時內刷新過的與 TMDB 說完結且都在庫
的，一輪的 TMDB 請求數有上界。斷言看公開的接縫：TMDB 替身收到的請求、Issue 清單、排程迴圈跑完一輪。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.tmdb import TmdbDetail, TmdbEpisode, TmdbSeason, TmdbSeasonEntry
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.db import create_session_factory
from berth.domain import (
    EpisodeSnapshot,
    FeedKind,
    IssueStatus,
    JobState,
    JobTrigger,
    MediaKind,
    MediaSnapshot,
    PlanAction,
    SeasonSnapshot,
)
from berth.models import (
    Issue,
    Job,
    LedgerEntry,
    Media,
    RssFeed,
    RssItem,
    RssSeries,
    TmdbSettings,
)
from berth.pipeline.sweeping import SWEEP_AT, Sweeper
from berth.services.events import EventHub
from berth.services.settings import write_settings
from berth.services.sweep import refresh_watched, sweep_once
from tests.conftest import TMDB_API_KEY
from tests.integration.factories import FakeClientFactory
from tests.integration.test_reconciler_schedule import Clock, ready
from tests.integration.test_sweep_overdue import (
    AIRED,
    MEDIA,
    SUBSCRIBED,
    landed,
    overdue,
    subscribed,
    wall,
)

pytestmark = pytest.mark.asyncio


def aired(number: int) -> date:
    return AIRED + timedelta(weeks=number - 4)


def detail(tmdb_id: int, *, ended: bool = False) -> TmdbDetail:
    return TmdbDetail(
        tmdb_id=tmdb_id,
        kind=MediaKind.TV,
        title="Kimi to Koishitai",
        original_title="与你相恋",
        year=2026,
        first_air_date=aired(1),
        overview="",
        poster_path="",
        seasons=(
            TmdbSeasonEntry(season_number=1, name="Season 1", episode_count=12, air_date=aired(1)),
        ),
        ended=ended,
    )


def season(tmdb_id: int) -> TmdbSeason:
    return TmdbSeason(
        season_number=1,
        name="Season 1",
        air_date=aired(1),
        episodes=tuple(
            TmdbEpisode(
                season_number=1, episode_number=n, name=f"E{n}", air_date=aired(n), runtime=24
            )
            for n in range(1, 13)
        ),
    )


def tmdb(*ids: int, ended: frozenset[int] = frozenset()) -> FakeTmdbClient:
    return FakeTmdbClient(
        details=[detail(tmdb_id, ended=tmdb_id in ended) for tmdb_id in ids],
        seasons={tmdb_id: [season(tmdb_id)] for tmdb_id in ids},
    )


async def credentialled(session: AsyncSession, client: FakeTmdbClient) -> FakeClientFactory:
    await write_settings(session, TmdbSettings(api_key=TMDB_API_KEY))
    await session.commit()
    return FakeClientFactory(tmdb=client)


async def snapshot_without_episode_4(session: AsyncSession) -> None:
    """存著的快照是 7 小時前的：那時第 4 集還沒有播出日。"""
    row = await session.get(Media, MEDIA)
    assert row is not None
    shot = row.stored_snapshot()
    assert shot is not None
    episodes = tuple(
        e.model_copy(update={"air_date": None}) if e.episode_number >= 4 else e
        for e in shot.seasons[0].episodes
    )
    row.tmdb_snapshot_json = shot.model_copy(
        update={"seasons": (shot.seasons[0].model_copy(update={"episodes": episodes}),)}
    ).model_dump(mode="json")
    row.tmdb_fetched_at = datetime.now(UTC) - timedelta(hours=7)
    await session.commit()


class TestRefreshBeforeTheSweep:
    async def test_the_episode_that_just_aired_shows_up(self, session: AsyncSession) -> None:
        await subscribed(session)
        await snapshot_without_episode_4(session)
        factory = await credentialled(session, tmdb(120089))
        await sweep_once(session, now=wall(31))
        assert await overdue(session) == []

        failed = await refresh_watched(session, factory)
        await sweep_once(session, now=wall(31, 6), unrefreshed=failed)

        assert failed == frozenset()
        (issue,) = await overdue(session)
        assert [one["episode"] for one in issue.detail["episodes"]] == [4]


class TestAFailedRefresh:
    """`_load` 把錯誤吞成回傳值：看 `tmdb_fetched_at` 才知道沒刷新到。那幾部這一輪不開也不收。"""

    async def test_an_open_issue_is_not_closed(self, session: AsyncSession) -> None:
        series = await subscribed(session)
        await sweep_once(session, now=wall(31))
        (issue,) = await overdue(session)
        await landed(session, series, 4)
        await snapshot_without_episode_4(session)
        client = tmdb(120089)
        client.error = ServiceUnavailableError("GET /tv/120089: 503")
        factory = await credentialled(session, client)

        failed = await refresh_watched(session, factory)
        await sweep_once(session, now=wall(31, 6), unrefreshed=failed)

        assert failed == {MEDIA}
        kept = await session.get(Issue, issue.id)
        assert kept is not None and kept.status is IssueStatus.OPEN

    async def test_a_new_issue_is_not_opened(self, session: AsyncSession) -> None:
        await subscribed(session)
        row = await session.get(Media, MEDIA)
        assert row is not None
        row.tmdb_fetched_at = datetime.now(UTC) - timedelta(hours=7)
        await session.commit()
        client = tmdb(120089)
        client.error = ServiceUnavailableError("GET /tv/120089: 503")
        factory = await credentialled(session, client)

        failed = await refresh_watched(session, factory)
        await sweep_once(session, now=wall(31), unrefreshed=failed)

        assert failed == {MEDIA}
        assert await overdue(session) == []


class TestOneWorkBreaking:
    async def test_an_unexpected_error_only_costs_that_work(self, session: AsyncSession) -> None:
        """一部作品刷新時拋出服務錯誤以外的例外：記成那一部失敗，其他照刷新，巡檢照跑。"""
        await subscribed(session)
        await snapshot_without_episode_4(session)
        await another_work(session, 2, fetched=None)
        client = tmdb(120089, 2)
        client.detail_errors[(MediaKind.TV, 2)] = RuntimeError("boom")
        factory = await credentialled(session, client)

        failed = await refresh_watched(session, factory)
        await sweep_once(session, now=wall(31), unrefreshed=failed)

        assert failed == {"tv:2"}
        (issue,) = await overdue(session)
        assert [one["episode"] for one in issue.detail["episodes"]] == [4]


async def another_work(
    session: AsyncSession, tmdb_id: int, *, fetched: datetime | None, ended: bool = False
) -> str:
    """又一部訂著的作品（第 1 季 12 集都播完了）。"""
    media_id = f"tv:{tmdb_id}"
    session.add(
        Media(
            id=media_id,
            tmdb_id=tmdb_id,
            kind=MediaKind.TV,
            title_en=f"Work {tmdb_id}",
            title_original=f"Work {tmdb_id}",
            year=2026,
            folder_name=f"Work {tmdb_id} (2026)",
            tmdb_fetched_at=fetched,
            tmdb_snapshot_json=MediaSnapshot(
                tmdb_id=tmdb_id,
                kind=MediaKind.TV,
                title=f"Work {tmdb_id}",
                title_en=f"Work {tmdb_id}",
                title_original=f"Work {tmdb_id}",
                ended=ended,
                seasons=(
                    SeasonSnapshot(
                        season_number=1,
                        episode_count=1,
                        episodes=(EpisodeSnapshot(episode_number=1, air_date=date(2026, 7, 1)),),
                    ),
                ),
            ).model_dump(mode="json"),
        )
    )
    series = RssSeries(
        key=f"mikan:{tmdb_id}:1",
        title_raw=f"[G] Work {tmdb_id} - 01",
        reasons_json=[],
        media_id=media_id,
        created_at=SUBSCRIBED,
    )
    feed = RssFeed(name=str(tmdb_id), url=f"https://mikanani.me/{tmdb_id}", kind=FeedKind.MIKAN)
    session.add_all([series, feed])
    await session.flush()
    session.add(RssItem(feed_id=feed.id, guid=str(tmdb_id), title="x", series_id=series.id))
    await session.commit()
    return media_id


class TestHowMuchItAsks:
    async def test_fresh_and_finished_works_are_skipped(self, session: AsyncSession) -> None:
        """三部：一部 7 小時前刷新過（要刷）、一部剛刷新過、一部 TMDB 說完結而且都在庫。只問第一部，
        一部的請求數有上界；同一天再跑一次一個都不問。"""
        await subscribed(session)
        await snapshot_without_episode_4(session)
        await another_work(session, 2, fetched=datetime.now(UTC) - timedelta(hours=1))
        finished = await another_work(session, 3, fetched=None, ended=True)
        await all_in(session, finished)
        client = tmdb(120089, 2, 3, ended=frozenset({3}))
        factory = await credentialled(session, client)

        assert await refresh_watched(session, factory) == frozenset()

        # `detail/tv/{id}` 與 `season/{id}/{季}`。
        asked = {
            path.split("/")[2 if path.startswith("detail") else 1]
            for path, _ in client.requests
            if path.startswith(("detail", "season"))
        }
        assert asked == {"120089"}
        assert len(client.requests) <= 7

        before = len(client.requests)
        assert await refresh_watched(session, factory) == frozenset()
        assert len(client.requests) == before


async def all_in(session: AsyncSession, media_id: str) -> None:
    """`another_work` 那一部唯一的一集入庫了（手動送的）。"""
    job = Job(
        hash=media_id.replace("tv:", "f").ljust(40, "0"),
        name="Work - 01",
        trigger=JobTrigger.MANUAL,
        trigger_ref="",
        media_id=media_id,
        state=JobState.IMPORTED,
    )
    session.add(job)
    session.add(
        LedgerEntry(
            job_hash=job.hash,
            source_rel_path="01.mkv",
            source_abs_path="/data/complete/01.mkv",
            source_dev="1",
            target_path=f"/data/library/tv/{media_id}/Season 01/01.mkv",
            target_inode="1",
            media_id=media_id,
            season=1,
            episode_start=1,
            episode_end=1,
            tags_json={},
            action=PlanAction.IMPORT,
        )
    )
    await session.commit()


class TestTheLoop:
    async def test_a_round_refreshes_before_it_sweeps(
        self, engine: AsyncEngine, session: AsyncSession
    ) -> None:
        await ready(session)
        await subscribed(session)
        await snapshot_without_episode_4(session)
        factory = await credentialled(session, tmdb(120089))
        day = date(2026, 10, 31)
        at = datetime.combine(day, SWEEP_AT).astimezone()
        clock = Clock(at - timedelta(minutes=30))
        loop = Sweeper(create_session_factory(engine), factory, EventHub(), now=clock)
        clock.now = at + timedelta(minutes=1)

        assert await loop.run_if_due() is True

        (issue,) = await overdue(session)
        assert [one["episode"] for one in issue.detail["episodes"]] == [4]
