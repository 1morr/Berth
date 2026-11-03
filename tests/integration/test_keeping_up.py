"""追更頁（`keeping_up.read_keeping_up`，M5.5 票 12，`.scratch/m5.5/tracking-shape.md`）。

一部訂閱的作品一列：字幕組、已播到、已入庫到、狀態（`WhyNot` 的結論，停滯另外說），晚的集與
「晚 N 天」（從播出日算），分成要你動手、準時、斷更很久三段。對象與判定同遲到提醒（巡檢開的
`episodes_overdue`）：材料借 `test_sweep_overdue` 的那幾支。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import (
    FeedKind,
    JobState,
    JobTrigger,
    KeepingUpSection,
    OverdueReason,
    OverdueStall,
    PlanAction,
    WhyNot,
)
from berth.models import Job, LedgerEntry, Media, RssFeed, RssItem, RssSeries
from berth.services import keeping_up
from berth.services.keeping_up import EpisodeMark, KeepingUpView, TrackedWork, read_keeping_up
from berth.services.sweep import sweep_once
from tests.integration.test_sweep_overdue import (
    AIRED,
    MEDIA,
    job,
    landed,
    overdue,
    subscribed,
    wall,
    work,
)

pytestmark = pytest.mark.asyncio


def at(moment: datetime, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(keeping_up, "local_now", lambda: moment)


async def only(session: AsyncSession) -> TrackedWork:
    view = await read_keeping_up(session)
    (work,) = view.works
    return work


class TestOneRowPerWork:
    async def test_the_row_says_groups_aired_imported_and_the_conclusion(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """10/30：第 4 集 10/28 播了、字幕組還沒發，還沒過門檻：準時，結論是沒有來源。"""
        series = await subscribed(session)
        series.mikan_subgroup_name = "LoliHouse"
        await session.commit()
        at(wall(30), monkeypatch)

        view = await read_keeping_up(session)

        assert isinstance(view, KeepingUpView)
        assert view.today == date(2026, 10, 30)
        (work,) = view.works
        assert work.media_id == MEDIA
        assert work.title == "与你相恋"
        assert work.groups == ("LoliHouse",)
        assert work.aired == EpisodeMark(1, 4, AIRED)
        assert work.imported == EpisodeMark(1, 3, AIRED - timedelta(weeks=1))
        assert work.conclusion is WhyNot.NO_SOURCE
        assert not work.stalled
        assert work.section is KeepingUpSection.ON_TIME
        assert work.late_days is None
        assert work.late == ()

    async def test_caught_up_is_imported_and_on_time(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        series = await subscribed(session)
        await landed(session, series, 4)
        at(wall(31), monkeypatch)

        work = await only(session)

        assert work.conclusion is WhyNot.IMPORTED
        assert work.section is KeepingUpSection.ON_TIME
        assert work.imported == EpisodeMark(1, 4, AIRED)

    async def test_subscribed_mid_season_with_nothing_new_since_is_caught_up(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """10/29 才訂（第 4 集 10/28 播過了），之後還沒有新的一集：沒有缺，是跟上了，不是還沒播。"""
        await work(session)
        series = RssSeries(
            key="mikan:3600:583",
            title_raw="[mikan:3600:583] Kimi to Koishitai - 01",
            reasons_json=[],
            media_id=MEDIA,
            created_at=datetime(2026, 10, 29, 3, 0).astimezone(),
        )
        feed = RssFeed(name="mikan", url="https://mikanani.me/RSS/x", kind=FeedKind.MIKAN)
        session.add_all([series, feed])
        await session.flush()
        session.add(RssItem(feed_id=feed.id, guid="x", title=series.title_raw, series_id=series.id))
        await session.commit()
        at(wall(31), monkeypatch)

        work_row = await only(session)

        assert work_row.aired == EpisodeMark(1, 4, AIRED)
        assert work_row.imported is None
        assert work_row.conclusion is WhyNot.IMPORTED
        assert work_row.section is KeepingUpSection.ON_TIME

    async def test_unsubscribed_works_are_not_listed(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        series = await subscribed(session)
        series.media_id = None
        await session.commit()
        at(wall(31), monkeypatch)

        assert (await read_keeping_up(session)).works == ()


class TestLate:
    async def test_late_days_count_from_the_air_date_and_match_the_issue(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """10/31：第 4 集 10/28 播出，過了兩天的門檻：晚 3 天，與巡檢開的那一件說同一集。"""
        await subscribed(session)
        at(wall(31), monkeypatch)

        work = await only(session)

        assert work.section is KeepingUpSection.ACTION
        assert work.reason is OverdueReason.LATE
        assert work.late_days == 3
        assert [(one.season, one.episode, one.stall) for one in work.late] == [
            (1, 4, OverdueStall.NOT_RELEASED)
        ]
        await sweep_once(session, now=wall(31))
        (issue,) = await overdue(session)
        assert [one["episode"] for one in issue.detail["episodes"]] == [4]

    async def test_a_stalled_download_says_stalled_not_downloading(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """驗收第 1 條的後端：停滯的那一集，結論仍是 `downloading`，但 `stalled` 說出來、排進
        要你動手，還沒過門檻也一樣。"""
        series = await subscribed(session)
        await job(session, series, 4, JobState.STALLED)
        at(wall(29), monkeypatch)

        work = await only(session)

        assert work.conclusion is WhyNot.DOWNLOADING
        assert work.stalled
        assert work.section is KeepingUpSection.ACTION
        assert work.late == ()

    async def test_a_moving_download_is_on_time(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        series = await subscribed(session)
        await job(session, series, 4, JobState.DOWNLOADING)
        at(wall(31), monkeypatch)

        work = await only(session)

        assert work.conclusion is WhyNot.DOWNLOADING
        assert not work.stalled
        assert work.section is KeepingUpSection.ON_TIME

    async def test_an_import_failure_needs_you_before_the_threshold(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        series = await subscribed(session)
        await job(session, series, 4, JobState.IMPORT_FAILED)
        at(wall(29), monkeypatch)

        work = await only(session)

        assert work.conclusion is WhyNot.IMPORT_FAILED
        assert work.section is KeepingUpSection.ACTION

    async def test_the_next_run_says_so(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """第 3 集之後停播 56 天才有第 4 集：可能是下一輪。"""
        await subscribed(session)
        await _shift(session, MEDIA, days=49)
        at(datetime(2026, 12, 19, 5, 0).astimezone(), monkeypatch)

        work = await only(session)

        assert work.reason is OverdueReason.NEXT_RUN
        assert work.late_days == 3


class TestDormant:
    async def test_sixty_days_after_the_last_missing_episode_it_is_put_away(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """第 12 集 12/23 播出、第 4 集起都沒入庫：最後一集缺集播出滿 60 天收進斷更很久，
        不說晚幾天。"""
        await subscribed(session)
        at(datetime(2027, 2, 21, 5, 0).astimezone(), monkeypatch)

        work = await only(session)

        assert work.section is KeepingUpSection.DORMANT
        assert work.late_days is None
        assert work.late == ()
        assert work.conclusion is WhyNot.NO_SOURCE


class TestOrder:
    async def test_needs_you_first_longest_late_first_then_on_time(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """三部：晚 4 天、停滯（也晚 3 天）、準時。晚越久越前面，準時最後。"""
        await subscribed(session)
        other = await _another_work(session, "tv:2", episodes_imported=4)
        stalled = await _another_work(session, "tv:3", episodes_imported=3)
        await _stalled_job(session, stalled, 4)
        assert other.id != stalled.id
        at(wall(31), monkeypatch)
        # 第一部的第 4 集早一天播：晚 4 天。
        await _shift(session, MEDIA, days=-1)

        works = (await read_keeping_up(session)).works

        assert [(work.media_id, work.section) for work in works] == [
            (MEDIA, KeepingUpSection.ACTION),
            ("tv:3", KeepingUpSection.ACTION),
            ("tv:2", KeepingUpSection.ON_TIME),
        ]


async def _another_work(
    session: AsyncSession, media_id: str, *, episodes_imported: int
) -> RssSeries:
    """同一份快照、另一個 id 的作品，綁一條 Series，前 `episodes_imported` 集入庫了。"""
    source = await session.get(Media, MEDIA)
    assert source is not None and source.tmdb_snapshot_json is not None
    tmdb_id = int(media_id.split(":")[1])
    session.add(
        Media(
            id=media_id,
            tmdb_id=tmdb_id,
            kind=source.kind,
            title_en=f"Work {tmdb_id}",
            title_original=f"Work {tmdb_id}",
            year=2026,
            folder_name=f"Work {tmdb_id} (2026)",
            tmdb_snapshot_json={
                **source.tmdb_snapshot_json,
                "tmdb_id": tmdb_id,
                "title": f"Work {tmdb_id}",
            },
        )
    )
    series = RssSeries(
        key=f"mikan:{tmdb_id}:1",
        title_raw=f"[G{tmdb_id}] Work - 01",
        reasons_json=[],
        media_id=media_id,
        created_at=datetime(2026, 10, 1, 3, 0).astimezone(),
    )
    feed = RssFeed(name=series.key, url=f"https://mikanani.me/RSS/{tmdb_id}", kind=FeedKind.MIKAN)
    session.add_all([series, feed])
    await session.flush()
    session.add(
        RssItem(feed_id=feed.id, guid=series.key, title=series.title_raw, series_id=series.id)
    )
    for number in range(1, episodes_imported + 1):
        session.add(
            LedgerEntry(
                job_hash=f"{tmdb_id:02d}{number:02d}".ljust(40, "a"),
                source_rel_path=f"{tmdb_id}-{number}.mkv",
                source_abs_path=f"/data/complete/{tmdb_id}-{number}.mkv",
                source_dev="1",
                target_path=f"/data/library/{tmdb_id}/{number}.mkv",
                target_inode="1",
                media_id=media_id,
                season=1,
                episode_start=number,
                episode_end=number,
                tags_json={},
                action=PlanAction.IMPORT,
            )
        )
    await session.commit()
    return series


async def _stalled_job(session: AsyncSession, series: RssSeries, episode: int) -> None:
    """`series` 的作品第 `episode` 集一筆停滯的下載（發佈名猜得出那一集）。"""
    assert series.media_id is not None
    session.add(
        Job(
            hash=f"{series.id:02d}{episode:02d}".ljust(40, "b"),
            name=f"[G] Work - {episode:02d}",
            trigger=JobTrigger.RSS,
            trigger_ref=str(series.id),
            media_id=series.media_id,
            state=JobState.STALLED,
        )
    )
    await session.commit()


async def _shift(session: AsyncSession, media_id: str, *, days: int) -> None:
    """`media_id` 第 4 集起的播出日挪 `days` 天。"""
    media = await session.get(Media, media_id)
    assert media is not None
    snapshot = media.stored_snapshot()
    assert snapshot is not None
    (season,) = snapshot.seasons
    shifted = tuple(
        row.model_copy(update={"air_date": row.air_date + timedelta(days=days)})
        if row.episode_number >= 4 and row.air_date
        else row
        for row in season.episodes
    )
    media.tmdb_snapshot_json = snapshot.model_copy(
        update={"seasons": (season.model_copy(update={"episodes": shifted}),)}
    ).model_dump(mode="json")
    await session.commit()
