"""每日巡檢的「卡住的」（M4 票 129，plan §11.5〈巡檢〉）。

一個 RSS Series 的第一批要整批落地才由系統確認（`services.first_batch`，M4 票 11）；同一個 Series
有一筆 Job 停在 `submit_failed` / `client_error`，那一批就一直等人。巡檢一天看一次，停了超過
`STUCK_AFTER` 而且沒有別的 Issue 管著的，開一件 `first_batch_stuck`；條件不在了由系統收掉。

斷言只看公開的接縫：巡檢一輪（`sweep_once`）之後 Issue 清單（`list_issues`）上有什麼。起點直接
寫列：Series 綁好、還沒確認，Job 停在那個狀態，停下來的那一刻是它最後一筆 `submit_failed` 事件
（送單失敗走的那一條路就是寫這一筆）。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import EventType, IssueStatus, IssueType, JobState, JobTrigger, MediaKind
from berth.models import Event, Issue, Job, Media, RssSeries
from berth.services.issues import IssueView, ignore_issue, list_issues, record_issue
from berth.services.sweep import STUCK_AFTER, sweep_once

pytestmark = pytest.mark.asyncio

#: Job 停下來的那一刻。
STOPPED = datetime(2026, 10, 20, 3, 0, tzinfo=UTC)
TITLE = "[LoliHouse] Kimi to Koishitai - 11 [WebRip 1080p HEVC-10bit AAC]"
HASH = "a" * 40
OTHER = "b" * 40


async def bound_series(session: AsyncSession, *, confirmed: bool = False) -> RssSeries:
    session.add(
        Media(
            id="tv:120089",
            tmdb_id=120089,
            kind=MediaKind.TV,
            title_en="Kimi to Koishitai",
            title_original="与你相恋",
            year=2025,
            folder_name="Kimi to Koishitai (2025)",
        )
    )
    series = RssSeries(
        key="mikan:3600:583",
        title_raw=TITLE,
        reasons_json=[],
        media_id="tv:120089",
        confirmed=confirmed,
    )
    session.add(series)
    await session.commit()
    return series


async def stuck_job(
    session: AsyncSession,
    series: RssSeries,
    *,
    job_hash: str = HASH,
    state: JobState = JobState.SUBMIT_FAILED,
    at: datetime = STOPPED,
    payload: dict[str, Any] | None = None,
) -> Job:
    """停在 `state` 的一筆。送單失敗預設是**還排著自動重送**的那一種（`pending`）：再問也一樣、
    次數用完、或重送過期滿一天的那一筆自己就是一件 `submit_failed`（M5 票 03），不再是第一批卡住
    的事。"""
    job = Job(
        hash=job_hash,
        name=TITLE,
        trigger=JobTrigger.RSS,
        trigger_ref=str(series.id),
        state=state,
        error="qBittorrent refused the torrent",
        added_at=at - timedelta(minutes=5),
    )
    session.add(job)
    session.add(
        Event(
            job_hash=job_hash,
            type=EventType.SUBMIT_FAILED.value,
            actor=f"rss:{series.id}",
            payload_json=payload if payload is not None else pending(at),
            created_at=at,
        )
    )
    await session.commit()
    return job


def pending(at: datetime) -> dict[str, Any]:
    """暫時的送單失敗，自動重送還排著（`jobs.retry_due` 在管）。排在一週後：這一檔的巡檢最晚跑在
    停下來之後第五天，重送過期滿一天的話它會變成一件 `submit_failed`（`sweep._retry_pending`）。"""
    return {
        "error": "qBittorrent timed out",
        "attempt": 2,
        "retry_at": (at + timedelta(days=7)).isoformat(),
    }


async def stuck_issues(session: AsyncSession) -> list[IssueView]:
    return [view for view in await list_issues(session) if view.type is IssueType.FIRST_BATCH_STUCK]


class TestStuckFirstBatch:
    async def test_a_job_stuck_past_the_threshold_opens_one_issue_for_the_series(
        self, session: AsyncSession
    ) -> None:
        series = await bound_series(session)
        await stuck_job(session, series)

        await sweep_once(session, now=STOPPED + STUCK_AFTER + timedelta(minutes=1))

        (issue,) = await stuck_issues(session)
        assert issue.subject == str(series.id)
        assert issue.job_hash == HASH
        assert issue.detail["series"] == series.id
        assert issue.detail["name"] == TITLE
        assert issue.detail["state"] == JobState.SUBMIT_FAILED.value
        assert issue.actions == ()

    async def test_not_yet_past_the_threshold_opens_nothing(self, session: AsyncSession) -> None:
        series = await bound_series(session)
        await stuck_job(session, series)

        await sweep_once(session, now=STOPPED + STUCK_AFTER - timedelta(minutes=1))

        assert await stuck_issues(session) == []

    async def test_the_threshold_counts_from_the_last_time_it_stopped(
        self, session: AsyncSession
    ) -> None:
        """重試過、又失敗了一次：從最後那一次算，不從第一次。"""
        series = await bound_series(session)
        await stuck_job(session, series)
        session.add(
            Event(
                job_hash=HASH,
                type=EventType.SUBMIT_FAILED.value,
                actor="7",
                payload_json=pending(STOPPED + timedelta(hours=12)),
                created_at=STOPPED + timedelta(hours=12),
            )
        )
        await session.commit()

        await sweep_once(session, now=STOPPED + STUCK_AFTER + timedelta(minutes=1))

        assert await stuck_issues(session) == []

    async def test_several_stuck_jobs_are_one_issue_pointing_at_the_oldest(
        self, session: AsyncSession
    ) -> None:
        series = await bound_series(session)
        await stuck_job(session, series, job_hash=OTHER, at=STOPPED + timedelta(hours=1))
        await stuck_job(session, series)

        await sweep_once(session, now=STOPPED + timedelta(days=2))

        (issue,) = await stuck_issues(session)
        assert issue.job_hash == HASH

    async def test_a_confirmed_series_is_not_waiting_for_anyone(
        self, session: AsyncSession
    ) -> None:
        """確認過的 Series 不再有第一批：停住的那一筆是 Job 頁的事。"""
        series = await bound_series(session, confirmed=True)
        await stuck_job(session, series)

        await sweep_once(session, now=STOPPED + timedelta(days=2))

        assert await stuck_issues(session) == []


class TestSystemClears:
    async def test_the_job_moving_on_clears_the_issue(self, session: AsyncSession) -> None:
        series = await bound_series(session)
        job = await stuck_job(session, series)
        await sweep_once(session, now=STOPPED + timedelta(days=2))
        assert len(await stuck_issues(session)) == 1

        job.state = JobState.DOWNLOADING
        await session.commit()
        await sweep_once(session, now=STOPPED + timedelta(days=3))

        assert await stuck_issues(session) == []
        row = await session.scalar(select(Issue).where(Issue.type == IssueType.FIRST_BATCH_STUCK))
        assert row is not None
        assert row.status is IssueStatus.RESOLVED
        assert row.resolved_by == "system"

    async def test_confirming_the_series_clears_the_issue(self, session: AsyncSession) -> None:
        series = await bound_series(session)
        await stuck_job(session, series)
        await sweep_once(session, now=STOPPED + timedelta(days=2))

        series.confirmed = True
        await session.commit()
        await sweep_once(session, now=STOPPED + timedelta(days=3))

        assert await stuck_issues(session) == []

    async def test_still_stuck_keeps_the_same_issue_open(self, session: AsyncSession) -> None:
        series = await bound_series(session)
        await stuck_job(session, series)
        await sweep_once(session, now=STOPPED + timedelta(days=2))
        (before,) = await stuck_issues(session)

        await sweep_once(session, now=STOPPED + timedelta(days=3))

        (after,) = await stuck_issues(session)
        assert after.id == before.id
        assert after.detected_at == STOPPED + timedelta(days=3)

    async def test_ignored_stays_ignored_while_it_is_still_stuck(
        self, session: AsyncSession
    ) -> None:
        """巡檢每天量一次：照「這一次不處理」的話忽略等於無效，明天又是一件新的（同票 122）。"""
        series = await bound_series(session)
        await stuck_job(session, series)
        await sweep_once(session, now=STOPPED + timedelta(days=2))
        (issue,) = await stuck_issues(session)
        await ignore_issue(session, issue.id, actor="7")
        await session.commit()

        await sweep_once(session, now=STOPPED + timedelta(days=3))

        assert await stuck_issues(session) == []


class TestAlreadyCovered:
    async def test_a_client_error_with_its_own_open_issue_is_not_opened_twice(
        self, session: AsyncSession
    ) -> None:
        """`client_error` 自己就有一件 Issue（poller 開的）在等人：不再為同一筆開第二件。"""
        series = await bound_series(session)
        await stuck_job(session, series, state=JobState.CLIENT_ERROR)
        await record_issue(session, IssueType.CLIENT_ERROR, job_hash=HASH, now=STOPPED)
        await session.commit()

        await sweep_once(session, now=STOPPED + timedelta(days=2))

        assert await stuck_issues(session) == []

    async def test_a_client_error_the_admin_ignored_is_not_asked_again(
        self, session: AsyncSession
    ) -> None:
        """人看過那一件、按了忽略：換一個型別再問同一筆是噪音（M4 票 129 code-review）。"""
        series = await bound_series(session)
        await stuck_job(session, series, state=JobState.CLIENT_ERROR)
        recorded = await record_issue(session, IssueType.CLIENT_ERROR, job_hash=HASH, now=STOPPED)
        await ignore_issue(session, recorded.issue.id, actor="7")
        await session.commit()

        await sweep_once(session, now=STOPPED + timedelta(days=2))

        assert await stuck_issues(session) == []

    async def test_a_client_error_issue_that_was_resolved_does_not_cover_it(
        self, session: AsyncSession
    ) -> None:
        """收掉的那一件說的是過去：Job 現在又停在這裡，沒有人在管。"""
        series = await bound_series(session)
        await stuck_job(session, series, state=JobState.CLIENT_ERROR)
        recorded = await record_issue(session, IssueType.CLIENT_ERROR, job_hash=HASH, now=STOPPED)
        recorded.issue.status = IssueStatus.RESOLVED
        await session.commit()

        await sweep_once(session, now=STOPPED + timedelta(days=2))

        assert len(await stuck_issues(session)) == 1

    async def test_a_resubmit_refused_after_client_removed_is_covered(
        self, session: AsyncSession
    ) -> None:
        """`client_removed` 按「重新送單」被拒的那一筆落在 `submit_failed`，那一件仍開著。"""
        series = await bound_series(session)
        await stuck_job(session, series)
        await record_issue(session, IssueType.CLIENT_REMOVED, job_hash=HASH, now=STOPPED)
        await session.commit()

        await sweep_once(session, now=STOPPED + timedelta(days=2))

        assert await stuck_issues(session) == []

    async def test_another_series_issue_does_not_cover_this_job(
        self, session: AsyncSession
    ) -> None:
        series = await bound_series(session)
        await stuck_job(session, series)
        await record_issue(session, IssueType.CLIENT_ERROR, job_hash=OTHER, now=STOPPED)
        await session.commit()

        await sweep_once(session, now=STOPPED + timedelta(days=2))

        assert len(await stuck_issues(session)) == 1

    async def test_stuck_again_after_it_cleared_is_a_new_issue(self, session: AsyncSession) -> None:
        series = await bound_series(session)
        job = await stuck_job(session, series)
        await sweep_once(session, now=STOPPED + timedelta(days=2))
        (issue,) = await stuck_issues(session)
        await ignore_issue(session, issue.id, actor="7")
        job.state = JobState.DOWNLOADING
        await session.commit()
        await sweep_once(session, now=STOPPED + timedelta(days=3))

        job.state = JobState.CLIENT_ERROR
        session.add(
            Event(
                job_hash=HASH,
                type=EventType.ISSUE_DETECTED.value,
                actor="system",
                payload_json={"type": IssueType.CLIENT_ERROR.value},
                created_at=STOPPED + timedelta(days=3, hours=1),
            )
        )
        await session.commit()
        await sweep_once(session, now=STOPPED + timedelta(days=5))

        (again,) = await stuck_issues(session)
        assert again.id != issue.id
        assert again.detail["state"] == JobState.CLIENT_ERROR.value
