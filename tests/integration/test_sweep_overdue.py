"""每日巡檢的「訂閱的作品遲到」（M5.5 票 10，spec〈範圍〉「遲到判定」「提醒」）。

有綁好的 RSS Series 的作品，最後入庫的一集之後播出滿門檻還沒入庫：一部作品一件 `episodes_overdue`，
說出晚的集與卡在哪；入庫了由系統收掉。下載還在動、等審核、Job 有 Issue 管著的不開。

斷言只看公開的接縫：巡檢一輪（`sweep_once`）之後 Issue 清單（`list_issues`）上有什麼。時刻用容器的
時區（`datetime(...).astimezone()`）：巡檢迴圈給的就是牆上的 05:00。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import (
    EpisodeSnapshot,
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
from berth.models import Issue, Job, LedgerEntry, Media, Plan, PlanItem, RssSeries, RssSettings
from berth.parser import series_finished
from berth.services.issues import IssueView, ignore_issue, list_issues
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
    """作品有一條綁好的 Series（預設 10/1 建的）；第 1–3 集已經由它入庫。"""
    if await session.get(Media, MEDIA) is None:
        await work(session)
    series = RssSeries(
        key=key,
        title_raw=f"[{key}] Kimi to Koishitai - 01",
        reasons_json=[],
        media_id=MEDIA,
        created_at=created,
    )
    session.add(series)
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
