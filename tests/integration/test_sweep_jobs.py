"""每日巡檢的「卡住的 Job」（M5 票 03，plan §2.4、§11.5 2026-10-24 已定）。

三種停住、沒有自動出路的 Job 各開一件 Issue（`subject` 是 `job_hash`），讓它進 `/issues`、
算進「等你處理」，M6 的接管開關也碰得到它：

- `submit_failed`：最後一次送單失敗**不會再自動重送**——再問也一樣的（沒有 `attempt`），或暫時的
  次數用完了（`retry_at` 是 `null`）。還有重送排著的不算，那是 `jobs.retry_due` 的事。
- `import_failed`：入庫沒有自動重試，停在這裡就是等人。
- `stalled`：做種變多就會自己恢復，所以停滯滿 `STUCK_AFTER` 才算（從最後一筆 `stalled` 事件算）。

收：Job 離開那個狀態時由 poller 每一輪的 `close_settled` 收（重試成功、被放棄、被刪）；送單失敗
又排上了自動重送的，下一輪巡檢收。

斷言只看公開的接縫：巡檢一輪（`sweep_once`）、`close_settled`、`resolve_issue` 之後的
Issue 清單（`list_issues`）與「等你處理」（`waiting_now`）。起點直接寫列，事件就是走那條路會寫的
那一筆。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import (
    EventType,
    IssueAction,
    IssueStatus,
    IssueType,
    JobState,
    JobTrigger,
)
from berth.models import Event, Issue, Job
from berth.services.issues import (
    IssueView,
    close_settled,
    ignore_issue,
    list_issues,
    record_issue,
    resolve_issue,
)
from berth.services.notify import WAIT_WINDOW, send_due
from berth.services.sweep import STUCK_AFTER, sweep_once
from berth.services.waiting import WaitingSource, waiting_now
from tests.integration.factories import FakeClientFactory
from tests.integration.test_notify import with_bot
from tests.integration.test_notify_waiting import admin, only, watch
from tests.integration.test_plan import NOW
from tests.integration.test_sweep import bound_series, stuck_job

pytestmark = pytest.mark.asyncio

#: Job 停下來的那一刻。
STOPPED = datetime(2026, 10, 20, 3, 0, tzinfo=UTC)
HASH = "c" * 40
OTHER = "d" * 40
NAME = "[SweetSub] Kusuriya no Hitorigoto - 05 [WebRip 1080p]"
REFUSED = "qBittorrent refused the torrent: 415"

#: 三種停住各自寫的那一筆事件。
STOPPED_BY = {
    JobState.SUBMIT_FAILED: EventType.SUBMIT_FAILED,
    JobState.IMPORT_FAILED: EventType.LINK_FAILED,
    JobState.STALLED: EventType.STALLED,
}

STUCK_TYPES = (IssueType.SUBMIT_FAILED, IssueType.IMPORT_FAILED, IssueType.STALLED)


async def stopped_job(
    session: AsyncSession,
    state: JobState,
    *,
    job_hash: str = HASH,
    at: datetime = STOPPED,
    payload: dict[str, Any] | None = None,
) -> Job:
    """一筆停在 `state` 的手動 Job，停下來那一刻寫了它那一種事件。送單失敗預設是再問也一樣的。"""
    job = Job(
        hash=job_hash,
        name=NAME,
        trigger=JobTrigger.MANUAL,
        state=state,
        error=REFUSED if state is JobState.SUBMIT_FAILED else "",
        added_at=at - timedelta(hours=1),
    )
    session.add(job)
    session.add(
        Event(
            job_hash=job_hash,
            type=STOPPED_BY[state].value,
            actor="system",
            payload_json=payload if payload is not None else {"error": REFUSED},
            created_at=at,
        )
    )
    await session.commit()
    return job


async def stuck(session: AsyncSession) -> list[IssueView]:
    return [view for view in await list_issues(session) if view.type in STUCK_TYPES]


class TestEachKindOpensOne:
    async def test_a_send_that_will_not_be_retried_opens_one(self, session: AsyncSession) -> None:
        """再問也一樣的拒絕（沒有 `attempt`）：沒有自動重送，下一輪巡檢就開，不必等滿門檻。"""
        await stopped_job(session, JobState.SUBMIT_FAILED)

        await sweep_once(session, now=STOPPED + timedelta(hours=1))

        (issue,) = await stuck(session)
        assert issue.type is IssueType.SUBMIT_FAILED
        assert issue.subject == HASH
        assert issue.job_hash == HASH
        assert issue.detail["name"] == NAME
        assert issue.detail["error"] == REFUSED
        assert issue.detail["since"] == STOPPED.isoformat()
        assert issue.actions == (IssueAction.RETRY, IssueAction.ABANDON)

    async def test_a_send_whose_retries_ran_out_opens_one(self, session: AsyncSession) -> None:
        """暫時的失敗，第五次之後 `retry_at` 寫 `null`（plan §3.1）。"""
        await stopped_job(
            session,
            JobState.SUBMIT_FAILED,
            payload={"error": "timed out", "attempt": 5, "retry_at": None},
        )

        await sweep_once(session, now=STOPPED + timedelta(hours=1))

        (issue,) = await stuck(session)
        assert issue.type is IssueType.SUBMIT_FAILED

    async def test_a_send_with_a_retry_still_due_is_not_stuck(self, session: AsyncSession) -> None:
        """自動重送排著：`retry_due` 在管。qBittorrent 停機時它過了時間也還排著（停機不花次數）。"""
        await stopped_job(
            session,
            JobState.SUBMIT_FAILED,
            payload={
                "error": "timed out",
                "attempt": 2,
                "retry_at": (STOPPED + timedelta(minutes=10)).isoformat(),
            },
        )

        await sweep_once(session, now=STOPPED + timedelta(days=2))

        assert await stuck(session) == []

    async def test_a_failed_import_opens_one(self, session: AsyncSession) -> None:
        await stopped_job(session, JobState.IMPORT_FAILED, payload={"errno": 18})

        await sweep_once(session, now=STOPPED + timedelta(hours=1))

        (issue,) = await stuck(session)
        assert issue.type is IssueType.IMPORT_FAILED
        assert issue.actions == (IssueAction.RETRY, IssueAction.ABANDON)

    async def test_a_download_stalled_past_the_threshold_opens_one(
        self, session: AsyncSession
    ) -> None:
        await stopped_job(session, JobState.STALLED, payload={"idle_minutes": 10})

        await sweep_once(session, now=STOPPED + STUCK_AFTER + timedelta(minutes=1))

        (issue,) = await stuck(session)
        assert issue.type is IssueType.STALLED
        assert issue.actions == (IssueAction.ABANDON,)

    async def test_a_download_stalled_for_less_than_the_threshold_is_not_stuck(
        self, session: AsyncSession
    ) -> None:
        """停滯會自己恢復（做種變多就動了）：才停一陣子的不算。"""
        await stopped_job(session, JobState.STALLED, payload={"idle_minutes": 10})

        await sweep_once(session, now=STOPPED + STUCK_AFTER - timedelta(minutes=1))

        assert await stuck(session) == []

    async def test_each_stuck_job_is_its_own_issue(self, session: AsyncSession) -> None:
        await stopped_job(session, JobState.SUBMIT_FAILED)
        await stopped_job(session, JobState.IMPORT_FAILED, job_hash=OTHER)

        await sweep_once(session, now=STOPPED + timedelta(hours=1))

        assert sorted((issue.type, issue.subject) for issue in await stuck(session)) == sorted(
            [(IssueType.SUBMIT_FAILED, HASH), (IssueType.IMPORT_FAILED, OTHER)]
        )

    async def test_it_counts_as_waiting_for_you(self, session: AsyncSession) -> None:
        """「等你處理」數的是開著的 Issue：卡住的那一筆算一件，連到它在 `/issues` 的那一列。"""
        await stopped_job(session, JobState.SUBMIT_FAILED)
        await sweep_once(session, now=STOPPED + timedelta(hours=1))
        (issue,) = await stuck(session)

        waiting = await waiting_now(session)

        assert waiting[f"issue:{issue.id}"].source is WaitingSource.ISSUE
        assert waiting[f"issue:{issue.id}"].issue_type is IssueType.SUBMIT_FAILED


class TestNotOpenedTwice:
    async def test_another_sweep_keeps_the_same_issue(self, session: AsyncSession) -> None:
        await stopped_job(session, JobState.SUBMIT_FAILED)
        await sweep_once(session, now=STOPPED + timedelta(hours=1))
        (before,) = await stuck(session)

        await sweep_once(session, now=STOPPED + timedelta(days=1, hours=1))

        (after,) = await stuck(session)
        assert after.id == before.id
        rows = await session.scalars(select(Issue).where(Issue.type == IssueType.SUBMIT_FAILED))
        assert len(list(rows)) == 1

    async def test_ignored_stays_ignored_while_it_is_still_stuck(
        self, session: AsyncSession
    ) -> None:
        """巡檢每天量一次：照「這一次不處理」的話忽略等於無效（同巡檢的其他幾種）。"""
        await stopped_job(session, JobState.IMPORT_FAILED)
        await sweep_once(session, now=STOPPED + timedelta(hours=1))
        (issue,) = await stuck(session)
        await ignore_issue(session, issue.id, actor="7")

        await sweep_once(session, now=STOPPED + timedelta(days=1, hours=1))

        assert await stuck(session) == []

    async def test_a_send_refused_after_client_removed_stays_with_that_issue(
        self, session: AsyncSession
    ) -> None:
        """`client_removed` 的「重新送單」被拒，那一筆落在 `submit_failed`，那一件仍開著在管它。"""
        await stopped_job(session, JobState.SUBMIT_FAILED)
        await record_issue(session, IssueType.CLIENT_REMOVED, job_hash=HASH, now=STOPPED)
        await session.commit()

        await sweep_once(session, now=STOPPED + timedelta(hours=1))

        assert await stuck(session) == []

    async def test_a_stuck_rss_first_batch_is_not_also_a_first_batch_issue(
        self, session: AsyncSession
    ) -> None:
        """停住的那一筆自己有一件按得了重試的 Issue：「第一批卡住」不再為同一筆開第二件。"""
        series = await bound_series(session)
        await stuck_job(session, series, job_hash=HASH, payload={"error": REFUSED})

        await sweep_once(session, now=STOPPED + timedelta(days=2))

        assert [issue.type for issue in await list_issues(session)] == [IssueType.SUBMIT_FAILED]


class TestClosedWhenItMovesOn:
    async def test_a_successful_retry_closes_it_on_the_next_poll(
        self, session: AsyncSession
    ) -> None:
        """Job 頁按了重試、qBittorrent 收下了：poller 那一輪的 `close_settled` 收掉。"""
        job = await stopped_job(session, JobState.SUBMIT_FAILED)
        await sweep_once(session, now=STOPPED + timedelta(hours=1))
        job.state = JobState.SUBMITTED
        await session.commit()

        await close_settled(session, STOPPED + timedelta(hours=2))
        await session.commit()

        assert await stuck(session) == []
        row = await session.scalar(select(Issue).where(Issue.type == IssueType.SUBMIT_FAILED))
        assert row is not None
        assert row.status is IssueStatus.RESOLVED
        assert row.resolved_by == "system"

    async def test_a_download_moving_again_closes_it(self, session: AsyncSession) -> None:
        job = await stopped_job(session, JobState.STALLED)
        await sweep_once(session, now=STOPPED + timedelta(days=2))
        job.state = JobState.DOWNLOADING
        await session.commit()

        await close_settled(session, STOPPED + timedelta(days=2, hours=1))
        await session.commit()

        assert await stuck(session) == []

    async def test_a_deleted_job_closes_it(self, session: AsyncSession) -> None:
        """Job 頁的刪除範圍（或被整列清掉）：那一件說的事不在了。"""
        job = await stopped_job(session, JobState.IMPORT_FAILED)
        await sweep_once(session, now=STOPPED + timedelta(hours=1))
        job.state = JobState.REMOVED
        await session.commit()

        await close_settled(session, STOPPED + timedelta(hours=2))
        await session.commit()

        assert await stuck(session) == []

    async def test_a_send_that_will_be_retried_again_is_closed_by_the_next_sweep(
        self, session: AsyncSession
    ) -> None:
        """人按了重試、又暫時失敗：自動重送從頭排上了，還是 `submit_failed` 但不再沒人管。"""
        await stopped_job(session, JobState.SUBMIT_FAILED)
        await sweep_once(session, now=STOPPED + timedelta(hours=1))
        session.add(
            Event(
                job_hash=HASH,
                type=EventType.SUBMIT_FAILED.value,
                actor="7",
                payload_json={
                    "error": "timed out",
                    "attempt": 1,
                    "retry_at": (STOPPED + timedelta(hours=3)).isoformat(),
                },
                created_at=STOPPED + timedelta(hours=2),
            )
        )
        await session.commit()

        await sweep_once(session, now=STOPPED + timedelta(hours=2, minutes=1))

        assert await stuck(session) == []


class TestPressingItsButtons:
    async def test_retrying_a_failed_import_puts_it_back_and_closes_it(
        self, session: AsyncSession
    ) -> None:
        """「重試」是 Job 頁的那一顆（`jobs.retry_job`）：入庫失敗回 `importing`，那一件收掉。"""
        job = await stopped_job(session, JobState.IMPORT_FAILED)
        await sweep_once(session, now=STOPPED + timedelta(hours=1))
        (issue,) = await stuck(session)

        done = await resolve_issue(
            session, FakeClientFactory(), issue.id, IssueAction.RETRY, actor="7"
        )

        assert done.status is IssueStatus.RESOLVED
        await session.refresh(job)
        assert job.state is JobState.IMPORTING

    async def test_giving_up_ends_the_download_without_touching_anything(
        self, session: AsyncSession
    ) -> None:
        """「放棄」是 Job 頁的刪除範圍四個旗標全不勾：Job 進 `removed`，磁碟與 qBittorrent
        都不動。"""
        job = await stopped_job(session, JobState.SUBMIT_FAILED)
        await sweep_once(session, now=STOPPED + timedelta(hours=1))
        (issue,) = await stuck(session)
        factory = FakeClientFactory()

        done = await resolve_issue(session, factory, issue.id, IssueAction.ABANDON, actor="7")

        assert done.status is IssueStatus.RESOLVED
        await session.refresh(job)
        assert job.state is JobState.REMOVED
        assert factory.qbittorrent_.deleted == []

    async def test_a_retry_is_not_offered_once_the_job_moved_on(
        self, session: AsyncSession
    ) -> None:
        """按鈕只在那個狀態按得了：Job 自己往前走了，按下去會把一筆好好的下載拉回去。"""
        job = await stopped_job(session, JobState.IMPORT_FAILED)
        await sweep_once(session, now=STOPPED + timedelta(hours=1))
        job.state = JobState.IMPORTED
        await session.commit()

        (issue,) = await stuck(session)

        assert issue.actions == ()


class TestTheWaitingPush:
    async def test_the_waiting_message_names_each_stuck_kind(self, session: AsyncSession) -> None:
        """「有 N 件等你處理」的推播（M4 票 127）數得到它們，訊息照型別說出是哪一種。"""
        await with_bot(session)
        await admin(session)
        await watch(session, timedelta(0))
        await stopped_job(session, JobState.SUBMIT_FAILED, at=NOW)
        await stopped_job(session, JobState.IMPORT_FAILED, job_hash=OTHER, at=NOW)
        await stopped_job(session, JobState.STALLED, job_hash="e" * 40, at=NOW - STUCK_AFTER)
        await sweep_once(session, now=NOW + timedelta(seconds=30))
        factory = FakeClientFactory()

        await watch(session, timedelta(minutes=1))
        await send_due(session, factory, now=NOW + timedelta(minutes=1) + WAIT_WINDOW)

        message = only(factory)
        assert message.title == "有 3 件等你處理"
        assert message.description == "新增 3 件：3 個 Issue（送單失敗、入庫失敗、停滯）"
