"""每日巡檢的「訂閱的作品遲到」（M5.5 票 10，spec〈範圍〉「遲到判定」「提醒」）。

有綁好的 RSS Series 的作品，最後入庫的一集之後播出滿門檻還沒入庫：一部作品一件 `episodes_overdue`，
說出晚的集與卡在哪；入庫了由系統收掉。下載還在動、等審核、Job 有 Issue 管著的不開。

斷言只看公開的接縫：巡檢一輪（`sweep_once`）之後 Issue 清單（`list_issues`）上有什麼。時刻用容器的
時區（`datetime(...).astimezone()`）：巡檢迴圈給的就是牆上的 05:00。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import (
    EpisodeSnapshot,
    FeedKind,
    IssueStatus,
    IssueType,
    JobState,
    JobTrigger,
    MediaKind,
    MediaSnapshot,
    PlanAction,
    PlanStatus,
    SeasonSnapshot,
)
from berth.models import (
    Issue,
    Job,
    LedgerEntry,
    Media,
    Plan,
    PlanItem,
    RssFeed,
    RssItem,
    RssSeries,
    RssSettings,
)
from berth.parser import series_finished
from berth.services.issues import IssueView, ignore_issue, list_issues
from berth.services.rss import delete_feed
from berth.services.settings import read_settings, write_settings
from berth.services.sweep import sweep_once

pytestmark = pytest.mark.asyncio

MEDIA = "tv:120089"
#: 第 4 集 10/28 播出，每週一集。
AIRED = date(2026, 10, 28)
SUBSCRIBED = datetime(2026, 10, 1, 3, 0, tzinfo=UTC)


def wall(day: int, hour: int = 5) -> datetime:
    """容器時區牆上的 10 月 `day` 日 `hour` 點。"""
    return datetime(2026, 10, day, hour, 0).astimezone()


async def work(session: AsyncSession, *, ended: bool = False) -> None:
    session.add(
        Media(
            id=MEDIA,
            tmdb_id=120089,
            kind=MediaKind.TV,
            title_en="Kimi to Koishitai",
            title_original="与你相恋",
            year=2026,
            folder_name="Kimi to Koishitai (2026)",
            tmdb_snapshot_json=MediaSnapshot(
                tmdb_id=120089,
                kind=MediaKind.TV,
                title="与你相恋",
                title_en="Kimi to Koishitai",
                title_original="与你相恋",
                year=2026,
                ended=ended,
                seasons=(
                    SeasonSnapshot(
                        season_number=1,
                        episode_count=12,
                        episodes=tuple(
                            EpisodeSnapshot(
                                episode_number=number,
                                air_date=AIRED + timedelta(weeks=number - 4),
                            )
                            for number in range(1, 13)
                        ),
                    ),
                ),
            ).model_dump(mode="json"),
        )
    )
    await session.commit()


async def subscribed(
    session: AsyncSession, *, key: str = "mikan:3600:583", created: datetime = SUBSCRIBED
) -> RssSeries:
    """作品有一條綁好的 Series（預設 10/1 建的），帶著它的 Feed 有它的 Item（訂閱還在）；第 1–3 集
    已經由它入庫。"""
    if await session.get(Media, MEDIA) is None:
        await work(session)
    series = RssSeries(
        key=key,
        title_raw=f"[{key}] Kimi to Koishitai - 01",
        reasons_json=[],
        media_id=MEDIA,
        created_at=created,
    )
    feed = RssFeed(name=key, url=f"https://mikanani.me/RSS/{key}", kind=FeedKind.MIKAN)
    session.add_all([series, feed])
    await session.flush()
    session.add(RssItem(feed_id=feed.id, guid=key, title=series.title_raw, series_id=series.id))
    await session.commit()
    for number in (1, 2, 3):
        await landed(session, series, number)
    return series


def hash_of(series: RssSeries | None, episode: int, tag: str = "0") -> str:
    return f"{series.id if series else 0:02d}{episode:02d}{tag}".ljust(40, "0")


async def job(
    session: AsyncSession, series: RssSeries | None, episode: int, state: JobState, tag: str = "0"
) -> Job:
    """一筆蓋到第 `episode` 集的 Job（計劃說的季集）。`series` 是 `None` 的是手動送的。"""
    row = Job(
        hash=hash_of(series, episode, tag),
        name=f"Kimi to Koishitai - {episode:02d}",
        trigger=JobTrigger.RSS if series else JobTrigger.MANUAL,
        trigger_ref=str(series.id) if series else "",
        media_id=MEDIA,
        state=state,
    )
    session.add(row)
    plan = Plan(job_hash=row.hash, status=PlanStatus.PENDING_REVIEW)
    session.add(plan)
    await session.flush()
    session.add(
        PlanItem(
            plan_id=plan.id,
            rel_path=f"{episode:02d}.mkv",
            action=PlanAction.IMPORT,
            media_id=MEDIA,
            season=1,
            episode_start=episode,
            episode_end=episode,
            confidence="high",
        )
    )
    await session.commit()
    return row


async def landed(session: AsyncSession, series: RssSeries | None, episode: int) -> None:
    """第 `episode` 集入庫了：Job 進 `imported`，帳本一列正片。"""
    row = await session.get(Job, hash_of(series, episode))
    if row is None:
        row = await job(session, series, episode, JobState.IMPORTED)
    row.state = JobState.IMPORTED
    session.add(
        LedgerEntry(
            job_hash=row.hash,
            source_rel_path=f"{row.hash}.mkv",
            source_abs_path=f"/data/complete/{row.hash}.mkv",
            source_dev="1",
            target_path=f"/data/library/tv/Kimi/Season 01/{row.hash}.mkv",
            target_inode="1",
            media_id=MEDIA,
            season=1,
            episode_start=episode,
            episode_end=episode,
            tags_json={},
            action=PlanAction.IMPORT,
        )
    )
    await session.commit()


async def overdue(session: AsyncSession) -> list[IssueView]:
    return [view for view in await list_issues(session) if view.type is IssueType.EPISODES_OVERDUE]


def late(issue: IssueView) -> list[tuple[int, str]]:
    return [(one["episode"], one["stall"]) for one in issue.detail["episodes"]]


class TestTheGroupHasNotReleasedIt:
    async def test_two_days_after_the_day_after_airing_then_closed_once_imported(
        self, session: AsyncSession
    ) -> None:
        """10/28 播出而字幕組沒發：10/30 不開，10/31 巡檢開一件，發了入庫後系統收掉。"""
        series = await subscribed(session)

        await sweep_once(session, now=wall(30))
        assert await overdue(session) == []

        await sweep_once(session, now=wall(31))
        (issue,) = await overdue(session)
        assert issue.subject == MEDIA
        assert issue.detail["reason"] == "late"
        assert issue.detail["media"] == MEDIA
        assert issue.detail["title"] == "与你相恋"
        assert issue.detail["episodes"] == [
            {
                "season": 1,
                "episode": 4,
                "air_date": "2026-10-28",
                "stall": "not_released",
                "jobs": [],
            }
        ]
        assert issue.actions == ()

        await landed(session, series, 4)
        await sweep_once(session, now=wall(31, 6))
        assert await overdue(session) == []
        closed = await session.get(Issue, issue.id)
        assert closed is not None and closed.status is IssueStatus.RESOLVED

    async def test_the_threshold_is_the_rss_setting(self, session: AsyncSession) -> None:
        await subscribed(session)
        settings = await read_settings(session, RssSettings)
        assert settings.overdue_days == 2
        settings.overdue_days = 3
        await write_settings(session, settings)
        await session.commit()

        await sweep_once(session, now=wall(31))
        assert await overdue(session) == []

    async def test_another_group_or_a_manual_download_brought_it(
        self, session: AsyncSession
    ) -> None:
        series = await subscribed(session)
        other = RssSeries(key="mikan:3600:370", title_raw="x", reasons_json=[], media_id=MEDIA)
        session.add(other)
        await session.commit()
        await landed(session, other, 4)
        await landed(session, None, 5)
        assert series.id != other.id

        await sweep_once(session, now=wall(31))
        await sweep_once(session, now=datetime(2026, 11, 7, 5, 0).astimezone())

        assert await overdue(session) == []

    async def test_series_finished_is_not_read(self, session: AsyncSession) -> None:
        """TMDB 說完結、安靜超過 30 天（RSS 頁收進「已完結」）也照開：缺的正是最近播出的。"""
        await work(session, ended=True)
        quiet_since = SUBSCRIBED - timedelta(days=7)
        await subscribed(session, created=quiet_since)
        now = wall(31)
        assert series_finished(
            latest=quiet_since, now=now, media=None, seasons=(), held=(), open_items=0
        )

        await sweep_once(session, now=now)

        assert len(await overdue(session)) == 1

    async def test_a_work_without_a_bound_series_is_not_looked_at(
        self, session: AsyncSession
    ) -> None:
        series = await subscribed(session)
        await sweep_once(session, now=wall(31))
        (issue,) = await overdue(session)

        series.media_id = None
        await session.commit()
        await sweep_once(session, now=wall(31, 6))

        assert await overdue(session) == []
        closed = await session.get(Issue, issue.id)
        assert closed is not None and closed.status is IssueStatus.RESOLVED


class TestIgnoring:
    async def test_ignoring_holds_while_late_and_reopens_after_it_cleared(
        self, session: AsyncSession
    ) -> None:
        """忽略在條件持續期間有效（`STAYS_IGNORED`）：還晚著就不重開；都入庫過一次之後再晚是新的一件。"""
        series = await subscribed(session)
        await sweep_once(session, now=wall(31))
        (issue,) = await overdue(session)
        await ignore_issue(session, issue.id, actor="1")

        await sweep_once(session, now=wall(31, 6))
        assert await overdue(session) == []

        await landed(session, series, 4)
        await sweep_once(session, now=wall(31, 7))
        await sweep_once(session, now=datetime(2026, 11, 7, 5, 0).astimezone())

        (again,) = await overdue(session)
        assert again.id != issue.id
        assert late(again) == [(5, "not_released")]


class TestWhereItIsStuck:
    @pytest.mark.parametrize(
        ("state", "stall"),
        [(JobState.STALLED, "stalled"), (JobState.IMPORT_FAILED, "import_failed")],
    )
    async def test_stuck_past_the_threshold_says_where_then_closes_once_imported(
        self, session: AsyncSession, state: JobState, stall: str
    ) -> None:
        series = await subscribed(session)
        stuck = await job(session, series, 4, state)

        await sweep_once(session, now=wall(31))
        (issue,) = await overdue(session)
        assert late(issue) == [(4, stall)]
        assert issue.detail["episodes"][0]["jobs"] == [stuck.hash]

        await landed(session, series, 4)
        await sweep_once(session, now=wall(31, 6))
        assert await overdue(session) == []


class TestAlreadyBeingHandled:
    @pytest.mark.parametrize("state", [JobState.DOWNLOADING, JobState.REVIEW])
    async def test_moving_or_awaiting_review(self, session: AsyncSession, state: JobState) -> None:
        series = await subscribed(session)
        await job(session, series, 4, state)

        await sweep_once(session, now=wall(31))

        assert await overdue(session) == []

    @pytest.mark.parametrize("ignored", [False, True])
    async def test_a_job_an_issue_speaks_for_opens_on_the_next_round_once_it_closes(
        self, session: AsyncSession, ignored: bool
    ) -> None:
        """Job 有開著或被忽略的 `client_error`：不開；那件收掉而這一集還缺，下一輪開。"""
        series = await subscribed(session)
        broken = await job(session, series, 4, JobState.CLIENT_ERROR)
        speaks = Issue(type=IssueType.CLIENT_ERROR, subject=broken.hash, job_hash=broken.hash)
        session.add(speaks)
        await session.commit()
        if ignored:
            await ignore_issue(session, speaks.id, actor="1")

        await sweep_once(session, now=wall(31))
        assert await overdue(session) == []

        speaks.status = IssueStatus.RESOLVED
        await session.commit()
        await sweep_once(session, now=wall(31, 6))

        (issue,) = await overdue(session)
        assert late(issue) == [(4, "download_failed")]


class TestUnsubscribed:
    """刪掉訂閱（`delete_feed`）只刪 Feed，RSS Series 與綁定留著（協調者追加，票 10 的缺陷）：對象與
    作品頁的訂閱清單同一套判定（`rss.subscribed_media`），退訂了就不再提醒。"""

    async def test_deleting_the_feed_stops_and_closes_the_reminder(
        self, session: AsyncSession
    ) -> None:
        series = await subscribed(session)
        await sweep_once(session, now=wall(31))
        (issue,) = await overdue(session)

        feed = await session.scalar(select(RssFeed))
        assert feed is not None
        await delete_feed(session, feed.id)
        assert (await session.get(RssSeries, series.id)) is not None

        await sweep_once(session, now=wall(31, 6))
        assert await overdue(session) == []
        closed = await session.get(Issue, issue.id)
        assert closed is not None and closed.status is IssueStatus.RESOLVED

    async def test_an_unsubscribed_work_is_never_opened(self, session: AsyncSession) -> None:
        await subscribed(session)
        feed = await session.scalar(select(RssFeed))
        assert feed is not None
        await delete_feed(session, feed.id)

        await sweep_once(session, now=wall(31))

        assert await overdue(session) == []


class TestSeriesThreshold:
    """單一 RSS Series 覆寫門檻（`rss_series.overdue_days`，留空用全域）；一部作品多條取最大值。"""

    async def test_a_series_override_beats_the_global_setting(self, session: AsyncSession) -> None:
        series = await subscribed(session)
        series.overdue_days = 3
        await session.commit()

        await sweep_once(session, now=wall(31))
        assert await overdue(session) == []

        await sweep_once(session, now=datetime(2026, 11, 1, 5, 0).astimezone())
        assert len(await overdue(session)) == 1

    async def test_several_series_take_the_largest(self, session: AsyncSession) -> None:
        """全域 2 天、一條覆寫 1 天、一條留空（等於 2 天）：取 2 天，10/30 不開、10/31 開。"""
        first = await subscribed(session)
        first.overdue_days = 1
        await session.commit()
        await subscribed(session, key="mikan:3600:370")

        await sweep_once(session, now=wall(30))
        assert await overdue(session) == []
        await sweep_once(session, now=wall(31))
        assert len(await overdue(session)) == 1

    async def test_a_larger_override_on_another_series_wins(self, session: AsyncSession) -> None:
        await subscribed(session)
        other = await subscribed(session, key="mikan:3600:370")
        other.overdue_days = 4
        await session.commit()

        await sweep_once(session, now=datetime(2026, 11, 1, 5, 0).astimezone())
        assert await overdue(session) == []
        await sweep_once(session, now=datetime(2026, 11, 2, 5, 0).astimezone())
        assert len(await overdue(session)) == 1


class TestNextRunThroughTheSweep:
    """換輪寫進 `detail_json.reason`：帳本與 Series 的 `created_at` 從資料庫讀回來比。"""

    async def weeks_apart(self, session: AsyncSession) -> None:
        """第 3 集 9/9 播出、第 4 集 10/28：隔了七週。第 1–3 集 10/2 入庫。"""
        row = await session.get(Media, MEDIA)
        assert row is not None
        shot = row.stored_snapshot()
        assert shot is not None
        episodes = tuple(
            e.model_copy(
                update={"air_date": date(2026, 9, 9) - timedelta(weeks=3 - e.episode_number)}
            )
            if e.episode_number <= 3
            else e
            for e in shot.seasons[0].episodes
        )
        row.tmdb_snapshot_json = shot.model_copy(
            update={"seasons": (shot.seasons[0].model_copy(update={"episodes": episodes}),)}
        ).model_dump(mode="json")
        for entry in await session.scalars(select(LedgerEntry)):
            entry.created_at = datetime(2026, 10, 2, 3, 0, tzinfo=UTC)
        await session.commit()

    async def test_a_long_break_opens_next_run(self, session: AsyncSession) -> None:
        await subscribed(session)
        await self.weeks_apart(session)

        await sweep_once(session, now=wall(31))

        (issue,) = await overdue(session)
        assert issue.detail["reason"] == "next_run"

    async def test_subscribing_to_the_next_run_brings_back_late(
        self, session: AsyncSession
    ) -> None:
        await subscribed(session)
        await subscribed(session, key="mikan:3700:583", created=datetime(2026, 10, 20, tzinfo=UTC))
        await self.weeks_apart(session)

        await sweep_once(session, now=wall(31))

        (issue,) = await overdue(session)
        assert issue.detail["reason"] == "late"

    async def test_a_feed_bound_to_the_next_run_brings_back_late(
        self, session: AsyncSession
    ) -> None:
        """基準之後才預先綁定作品的 Feed（字幕組還沒發）也是訂了下一輪（票 12b）。"""
        await subscribed(session)
        await prebound(session, created=datetime(2026, 10, 20, tzinfo=UTC))
        await self.weeks_apart(session)

        await sweep_once(session, now=wall(31))

        (issue,) = await overdue(session)
        assert issue.detail["reason"] == "late"


class TestSeriesOfADeletedFeed:
    """作品還訂著，但其中一條的 Feed 刪了：那一條不再算（門檻、換輪、起算日都不看它）。"""

    async def test_its_override_no_longer_raises_the_threshold(self, session: AsyncSession) -> None:
        gone = await subscribed(session)
        gone.overdue_days = 5
        await session.commit()
        await subscribed(session, key="mikan:3600:370")
        feed = await session.scalar(select(RssFeed).where(RssFeed.name == gone.key))
        assert feed is not None
        await delete_feed(session, feed.id)

        await sweep_once(session, now=wall(31))

        assert len(await overdue(session)) == 1


async def prebound(
    session: AsyncSession,
    *,
    created: datetime = datetime(2026, 10, 25, 3, 0, tzinfo=UTC),
    subgroup: str = "LoliHouse",
) -> RssFeed:
    """從作品頁訂的搜尋 Feed（`RssFeed.media_id` 預先綁到作品），字幕組一集都還沒發：沒有 Item、
    也沒有 RSS Series。綁定時刻是 Feed 建立的那一刻（預設 10/25，第 4 集 10/28 播出）。"""
    if await session.get(Media, MEDIA) is None:
        await work(session)
    feed = RssFeed(
        name=f"Nyaa · Kimi to Koishitai · {subgroup}",
        url=f"https://nyaa.si/?page=rss&q=Kimi+{subgroup}",
        kind=FeedKind.NYAA,
        media_id=MEDIA,
        subgroup=subgroup,
        created_at=created,
    )
    session.add(feed)
    await session.commit()
    return feed


class TestPreBoundFeedWithNothingYet:
    """預先綁定作品、字幕組一集都還沒發的 Feed 也算在看這部作品（M5.5 票 12b）：從綁定那天之後播出的
    第一集算起，門檻用全域的；刪掉 Feed 就不算。"""

    async def test_opens_past_the_threshold_from_the_day_it_was_bound(
        self, session: AsyncSession
    ) -> None:
        await prebound(session)

        await sweep_once(session, now=wall(30))
        assert await overdue(session) == []

        await sweep_once(session, now=wall(31))
        (issue,) = await overdue(session)
        assert issue.detail["reason"] == "late"
        assert late(issue) == [(4, "not_released")]

    async def test_deleting_the_feed_closes_it_and_it_never_reopens(
        self, session: AsyncSession
    ) -> None:
        feed = await prebound(session)
        await sweep_once(session, now=wall(31))
        (issue,) = await overdue(session)

        await delete_feed(session, feed.id)
        await sweep_once(session, now=wall(31, 6))

        assert await overdue(session) == []
        closed = await session.get(Issue, issue.id)
        assert closed is not None and closed.status is IssueStatus.RESOLVED
        await sweep_once(session, now=wall(31, 7))
        assert await overdue(session) == []

    async def test_counts_from_the_binding_even_after_the_feed_grew_a_series(
        self, session: AsyncSession
    ) -> None:
        """10/1 綁定，字幕組 10/26 才發第一筆（長出 Series、還沒入庫）：仍從 10/1 之後播出的
        第一集算，不跳到 Series 建立那天（起算取兩者較早的）。"""
        feed = await prebound(session, created=SUBSCRIBED)
        series = RssSeries(
            key="title:kimi:lolihouse",
            title_raw="[LoliHouse] Kimi to Koishitai - 04",
            reasons_json=[],
            media_id=MEDIA,
            created_at=datetime(2026, 10, 26, 3, 0, tzinfo=UTC),
        )
        session.add(series)
        await session.flush()
        session.add(
            RssItem(feed_id=feed.id, guid="04", title=series.title_raw, series_id=series.id)
        )
        await session.commit()

        await sweep_once(session, now=wall(31))

        (issue,) = await overdue(session)
        assert [episode for episode, _ in late(issue)] == [1, 2, 3, 4]

    async def test_the_threshold_is_the_global_setting(self, session: AsyncSession) -> None:
        await prebound(session)
        settings = await read_settings(session, RssSettings)
        settings.overdue_days = 3
        await write_settings(session, settings)
        await session.commit()

        await sweep_once(session, now=wall(31))
        assert await overdue(session) == []

        await sweep_once(session, now=datetime(2026, 11, 1, 5, 0).astimezone())
        assert len(await overdue(session)) == 1
