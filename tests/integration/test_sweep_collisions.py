"""每日巡檢的「同一集意外多份」（M4 票 130，plan §11.5〈巡檢〉；判準 2026-10-22 協調者確認，票的
Comments）。

**意外**是兩個不同的發佈被對到同一集：同一個 RSS Series 底下兩筆以上不同的 Job 入庫成同一集（帳本
`import`、`ok`、同作品同季同起始集），而它們的發佈名寫的集號不同——offset、絕對編號換算或季名讀錯，
播出日比對與片長驗證沒擋下的那一種。**版本並存不算**（brief §7.7、§7.8）：不同 Series（別的字幕組、
別的來源）的同一集；同一個 Series 而發佈名寫的是同一集（v2、简／繁兩版、不同解析度、保留兩者的
`[2]`）。

斷言只看公開的接縫：巡檢一輪（`sweep_once`）之後 Issue 清單（`list_issues`）上有什麼。
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import IssueStatus, IssueType, JobState, JobTrigger, LedgerStatus, PlanAction
from berth.models import Issue, Job, LedgerEntry, RssSeries
from berth.services.issues import IssueView, ignore_issue, list_issues
from berth.services.sweep import sweep_once
from tests.integration.test_sweep_gaps import MEDIA, bound_series

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 10, 22, 5, 0, tzinfo=UTC)
GROUP = "[喵萌奶茶屋&LoliHouse] 与你相恋 / Kimi ga Shinu made Koi wo Shitai"
TAIL = "[WebRip 1080p HEVC-10bit AAC][简繁日内封字幕]"


async def landed(
    session: AsyncSession,
    series: RssSeries | None,
    name: str,
    episode: int,
    *,
    status: LedgerStatus = LedgerStatus.OK,
) -> None:
    """發佈名 `name` 的一筆 Job 入庫成第 1 季第 `episode` 集。`series` 是 `None` 的是手動送的。"""
    job_hash = hashlib.sha1(name.encode()).hexdigest()
    session.add(
        Job(
            hash=job_hash,
            name=name,
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
            target_path=f"/data/library/tv/Kimi/Season 01/{job_hash}.mkv",
            target_inode="1",
            media_id=MEDIA,
            season=1,
            episode_start=episode,
            episode_end=episode,
            tags_json={},
            action=PlanAction.IMPORT,
            status=status,
            created_at=NOW - timedelta(days=3),
        )
    )
    await session.commit()


async def collisions(session: AsyncSession) -> list[IssueView]:
    return [
        view
        for view in await list_issues(session)
        if view.type is IssueType.SERIES_EPISODES_COLLIDE
    ]


class TestEpisodesCollide:
    async def test_two_releases_mapped_to_one_episode_open_one_issue(
        self, session: AsyncSession
    ) -> None:
        series = await bound_series(session)
        await landed(session, series, f"{GROUP} - 04 {TAIL}", 4)
        await landed(session, series, f"{GROUP} - 05 {TAIL}", 5)
        await landed(session, series, f"{GROUP} - 06 {TAIL}", 5)

        await sweep_once(session, now=NOW)

        (issue,) = await collisions(session)
        assert issue.subject == str(series.id)
        assert issue.detail["series"] == series.id
        assert issue.detail["media"] == MEDIA
        assert issue.detail["collisions"] == [
            {
                "season": 1,
                "episode": 5,
                "releases": [f"{GROUP} - 05 {TAIL}", f"{GROUP} - 06 {TAIL}"],
            }
        ]
        assert issue.actions == ()

    async def test_versions_of_the_same_written_episode_are_not_flagged(
        self, session: AsyncSession
    ) -> None:
        """同組的 v2、简／繁兩版、不同解析度：發佈名寫的都是同一集。"""
        series = await bound_series(session)
        await landed(session, series, f"{GROUP} - 05 {TAIL}", 5)
        await landed(session, series, f"{GROUP} - 05v2 {TAIL}", 5)
        await landed(session, series, f"{GROUP} - 05 [WebRip 720p HEVC-10bit AAC][简日内嵌]", 5)

        await sweep_once(session, now=NOW)

        assert await collisions(session) == []

    async def test_a_batch_covering_the_episode_is_a_version_too(
        self, session: AsyncSession
    ) -> None:
        """同組季末的合集（`[01-12]`）寫的是一整段，與每週的單集並存：範圍蓋到那一集就是同一集。"""
        series = await bound_series(session)
        await landed(session, series, f"{GROUP} - 05 {TAIL}", 5)
        await landed(session, series, f"{GROUP} [01-12] [BDRip 1080p HEVC-10bit FLAC]", 5)

        await sweep_once(session, now=NOW)

        assert await collisions(session) == []

    async def test_two_batches_mapped_onto_the_same_episodes_are_flagged(
        self, session: AsyncSession
    ) -> None:
        """兩段不相交的合集（offset 錯了，第二段被對到第一段的集數上）仍是兩個不同的發佈。"""
        series = await bound_series(session)
        await landed(session, series, f"{GROUP} [01-12] [BDRip 1080p HEVC-10bit FLAC]", 5)
        await landed(session, series, f"{GROUP} [13-24] [BDRip 1080p HEVC-10bit FLAC]", 5)

        await sweep_once(session, now=NOW)

        assert len(await collisions(session)) == 1

    async def test_other_series_and_manual_copies_are_not_flagged(
        self, session: AsyncSession
    ) -> None:
        """別的字幕組（別的 Series）、手動送的同一集是版本並存。"""
        series = await bound_series(session)
        other = await bound_series(session, key="mikan:3600:370")
        await landed(session, series, f"{GROUP} - 05 {TAIL}", 5)
        await landed(session, other, "[ANi] Kimi ga Shinu made Koi wo Shitai - 06 [1080P]", 5)
        await landed(session, None, "Kimi.ga.Shinu.made.Koi.wo.Shitai.S01E07.1080p.WEB", 5)

        await sweep_once(session, now=NOW)

        assert await collisions(session) == []

    async def test_a_release_whose_episode_cannot_be_read_does_not_count(
        self, session: AsyncSession
    ) -> None:
        series = await bound_series(session)
        await landed(session, series, f"{GROUP} - 05 {TAIL}", 5)
        await landed(session, series, f"{GROUP} {TAIL}", 5)

        await sweep_once(session, now=NOW)

        assert await collisions(session) == []

    async def test_a_copy_no_longer_ok_does_not_count(self, session: AsyncSession) -> None:
        """帳本不在 `ok` 的（移除了鏈接、目標不見了）有自己的 Issue 或是人決定過的。"""
        series = await bound_series(session)
        await landed(session, series, f"{GROUP} - 05 {TAIL}", 5)
        await landed(session, series, f"{GROUP} - 06 {TAIL}", 5, status=LedgerStatus.UNLINKED)

        await sweep_once(session, now=NOW)

        assert await collisions(session) == []

    async def test_fixing_it_closes_it_by_the_system(self, session: AsyncSession) -> None:
        series = await bound_series(session)
        await landed(session, series, f"{GROUP} - 05 {TAIL}", 5)
        await landed(session, series, f"{GROUP} - 06 {TAIL}", 5)
        await sweep_once(session, now=NOW)
        (issue,) = await collisions(session)

        # 放錯的那一份改正成第 6 集（作品頁的「修正」走 rematch，帳本那一列換季集）。
        entry = await _entry_of(session, f"{GROUP} - 06 {TAIL}")
        entry.episode_start = entry.episode_end = 6
        await session.commit()
        await sweep_once(session, now=NOW + timedelta(days=1))

        assert await collisions(session) == []
        closed = await session.get(Issue, issue.id)
        assert closed is not None and closed.status is IssueStatus.RESOLVED

    async def test_ignoring_holds_while_it_stays(self, session: AsyncSession) -> None:
        series = await bound_series(session)
        await landed(session, series, f"{GROUP} - 05 {TAIL}", 5)
        await landed(session, series, f"{GROUP} - 06 {TAIL}", 5)
        await sweep_once(session, now=NOW)
        (issue,) = await collisions(session)
        await ignore_issue(session, issue.id, actor="1")

        await sweep_once(session, now=NOW + timedelta(days=1))

        assert await collisions(session) == []


async def _entry_of(session: AsyncSession, name: str) -> LedgerEntry:
    (job_hash,) = await session.scalars(select(Job.hash).where(Job.name == name))
    (entry,) = await session.scalars(select(LedgerEntry).where(LedgerEntry.job_hash == job_hash))
    return entry
