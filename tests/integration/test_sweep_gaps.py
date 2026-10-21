"""每日巡檢的「RSS Series 缺集」（M4 票 130，plan §11.5〈巡檢〉）。

綁好的 RSS Series 已入庫的集數之間有洞：作品頁說「缺」的那幾集（播了、沒有下載在處理，
`inventory.read_holdings` 同一份判定）落在這個 Series 入庫過的最小與最大集之間。洞之後那幾集最早
入庫的一集滿 `GAP_GRACE` 才開——字幕組常晚幾天補發前一集。一個 Series 一件，列出缺哪幾集；補上了、
或 Series 解除綁定了，下一輪由系統收掉。

斷言只看公開的接縫：巡檢一輪（`sweep_once`）之後 Issue 清單（`list_issues`）上有什麼。起點直接寫列：
Series 綁好、它送的 Job、那些 Job 入庫的帳本列（入庫的時間就是那一刻）。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

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
from berth.models import Issue, Job, LedgerEntry, Media, Plan, PlanItem, RssSeries
from berth.models.types import utcnow
from berth.services.issues import IssueView, list_issues
from berth.services.sweep import GAP_GRACE, sweep_once

pytestmark = pytest.mark.asyncio

MEDIA = "tv:120089"
#: 全部播過了：缺不缺只看有沒有入庫、有沒有下載在處理。
AIRED = (utcnow() - timedelta(days=120)).date()
#: 第 4 集之後那一集入庫的時刻。
LANDED = datetime(2026, 10, 1, 3, 0, tzinfo=UTC)
LATER = LANDED + GAP_GRACE + timedelta(minutes=1)


async def bound_series(session: AsyncSession, *, key: str = "mikan:3600:583") -> RssSeries:
    if await session.get(Media, MEDIA) is None:
        session.add(
            Media(
                id=MEDIA,
                tmdb_id=120089,
                kind=MediaKind.TV,
                title_en="Kimi to Koishitai",
                title_original="与你相恋",
                year=2025,
                folder_name="Kimi to Koishitai (2025)",
                tmdb_snapshot_json=MediaSnapshot(
                    tmdb_id=120089,
                    kind=MediaKind.TV,
                    title="与你相恋",
                    title_en="Kimi to Koishitai",
                    title_original="与你相恋",
                    year=2025,
                    seasons=(
                        SeasonSnapshot(
                            season_number=0,
                            episode_count=3,
                            episodes=tuple(
                                EpisodeSnapshot(episode_number=number, air_date=AIRED)
                                for number in range(1, 4)
                            ),
                        ),
                        SeasonSnapshot(
                            season_number=1,
                            episode_count=12,
                            episodes=tuple(
                                EpisodeSnapshot(
                                    episode_number=number, air_date=AIRED + timedelta(weeks=number)
                                )
                                for number in range(1, 13)
                            ),
                        ),
                    ),
                ).model_dump(mode="json"),
            )
        )
    series = RssSeries(
        key=key, title_raw=f"[{key}] Kimi to Koishitai", reasons_json=[], media_id=MEDIA
    )
    session.add(series)
    await session.commit()
    return series


async def landed(
    session: AsyncSession,
    series: RssSeries | None,
    episode: int,
    *,
    at: datetime = LANDED,
    season: int = 1,
) -> None:
    """一筆 Job 入庫了第 `episode` 集。`series` 是 `None` 的是手動送的。"""
    job_hash = f"{series.id if series else 0:02d}{season:02d}{episode:02d}".ljust(40, "0")
    session.add(
        Job(
            hash=job_hash,
            name=f"Kimi to Koishitai - {episode:02d}",
            trigger=JobTrigger.RSS if series else JobTrigger.MANUAL,
            trigger_ref=str(series.id) if series else "",
            media_id=MEDIA,
            state=JobState.IMPORTED,
        )
    )
    session.add(
        LedgerEntry(
            job_hash=job_hash,
            source_rel_path=f"{job_hash}.mkv",
            source_abs_path=f"/data/complete/{job_hash}.mkv",
            source_dev="1",
            target_path=f"/data/library/tv/Kimi/Season {season:02d}/{job_hash}.mkv",
            target_inode="1",
            media_id=MEDIA,
            season=season,
            episode_start=episode,
            episode_end=episode,
            tags_json={},
            action=PlanAction.IMPORT,
            created_at=at,
        )
    )
    await session.commit()


async def gaps(session: AsyncSession) -> list[IssueView]:
    return [
        view
        for view in await list_issues(session)
        if view.type is IssueType.SERIES_EPISODES_MISSING
    ]


class TestEpisodesMissing:
    async def test_a_hole_older_than_the_grace_opens_one_issue_naming_the_episodes(
        self, session: AsyncSession
    ) -> None:
        series = await bound_series(session)
        for number in (1, 2):
            await landed(session, series, number, at=LANDED - timedelta(weeks=3))
        await landed(session, series, 5)
        await landed(session, series, 7, at=LANDED + timedelta(days=1))

        await sweep_once(session, now=LATER + timedelta(days=1))

        (issue,) = await gaps(session)
        assert issue.subject == str(series.id)
        assert issue.detail["series"] == series.id
        assert issue.detail["media"] == MEDIA
        assert issue.detail["title"] == "与你相恋"
        assert issue.detail["missing"] == [
            {"season": 1, "episode": 3},
            {"season": 1, "episode": 4},
            {"season": 1, "episode": 6},
        ]
        assert issue.actions == ()

    async def test_a_hole_within_the_grace_waits(self, session: AsyncSession) -> None:
        """第 3、4 集的洞在第 5 集入庫時出現，給字幕組 `GAP_GRACE` 補發。"""
        series = await bound_series(session)
        await landed(session, series, 2, at=LANDED - timedelta(weeks=3))
        await landed(session, series, 5)

        await sweep_once(session, now=LANDED + GAP_GRACE - timedelta(minutes=1))

        assert await gaps(session) == []

    async def test_only_holes_between_its_own_episodes_count(self, session: AsyncSession) -> None:
        """中途訂閱的：第一集之前、最新一集之後都不是洞。"""
        series = await bound_series(session)
        for number in (5, 6, 7):
            await landed(session, series, number)

        await sweep_once(session, now=LATER)

        assert await gaps(session) == []

    async def test_an_episode_another_group_brought_is_not_missing(
        self, session: AsyncSession
    ) -> None:
        """缺不缺看媒體庫（作品頁那一份）：另一個字幕組或手動送的入庫了那一集，就不缺。"""
        series = await bound_series(session)
        other = await bound_series(session, key="mikan:3600:370")
        await landed(session, series, 1)
        await landed(session, other, 2)
        await landed(session, None, 3)
        await landed(session, series, 4)

        await sweep_once(session, now=LATER)

        assert await gaps(session) == []

    async def test_an_episode_on_its_way_is_not_missing(self, session: AsyncSession) -> None:
        """有下載在處理那一集（下載中、卡住、等審核）不是缺：它已經有人在管。"""
        series = await bound_series(session)
        await landed(session, series, 1)
        await landed(session, series, 3)
        waiting = Job(
            hash="f" * 40,
            name="Kimi to Koishitai - 02",
            trigger=JobTrigger.RSS,
            trigger_ref=str(series.id),
            media_id=MEDIA,
            state=JobState.REVIEW,
        )
        session.add(waiting)
        plan = Plan(job_hash=waiting.hash, status=PlanStatus.PENDING_REVIEW)
        session.add(plan)
        await session.flush()
        session.add(
            PlanItem(
                plan_id=plan.id,
                rel_path="02.mkv",
                action=PlanAction.REVIEW,
                media_id=MEDIA,
                season=1,
                episode_start=2,
                episode_end=2,
                confidence="low",
            )
        )
        await session.commit()

        await sweep_once(session, now=LATER)

        assert await gaps(session) == []

    async def test_filling_the_hole_closes_it_by_the_system(self, session: AsyncSession) -> None:
        series = await bound_series(session)
        await landed(session, series, 1)
        await landed(session, series, 3)
        await sweep_once(session, now=LATER)
        (issue,) = await gaps(session)

        await landed(session, series, 2, at=LATER)
        await sweep_once(session, now=LATER + timedelta(days=1))

        assert await gaps(session) == []
        closed = await session.get(Issue, issue.id)
        assert closed is not None and closed.status is IssueStatus.RESOLVED

    async def test_an_unbound_series_is_closed_by_the_system(self, session: AsyncSession) -> None:
        series = await bound_series(session)
        await landed(session, series, 1)
        await landed(session, series, 3)
        await sweep_once(session, now=LATER)
        series.media_id = None
        await session.commit()

        await sweep_once(session, now=LATER + timedelta(days=1))

        assert await gaps(session) == []

    async def test_specials_are_not_checked(self, session: AsyncSession) -> None:
        """第 0 季的編號本來就不連續（OVA、SP 散落在各處）。"""
        series = await bound_series(session)
        await landed(session, series, 1, season=0)
        await landed(session, series, 3, season=0)

        await sweep_once(session, now=LATER)

        assert await gaps(session) == []
