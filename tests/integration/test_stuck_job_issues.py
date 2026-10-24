"""卡住的 Job 開成 Issue（M5 票 01，plan §2.4、brief §19 2026-10-24 第④條）。

三種卡住各一種型別：重試用完或永久失敗的 `submit_failed`、`import_failed`、`stalled`。開與收都是
`qbit_poller` 的一輪（`issues.flag_stuck_jobs` 與 `close_settled`）：起點是真的走一輪 poller。
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.domain import EventType, IssueAction, IssueStatus, IssueType, JobState
from berth.models import Issue, Job
from berth.services.downloads import STALL_AFTER
from berth.services.issues import ignore_issue, list_issues, record_issue, resolve_issue
from berth.services.jobs import record_event
from tests.integration.factories import FakeClientFactory
from tests.integration.test_downloads import NOW, run, setup_job, status
from tests.integration.test_notify_waiting import first_look, only, watch, wave

pytestmark = pytest.mark.asyncio

IDLE_SINCE = int((NOW - STALL_AFTER - timedelta(minutes=1)).timestamp())


def stalled_client() -> FakeQbittorrentClient:
    return FakeQbittorrentClient(
        torrents=(status(state="stalledDL", progress=0.4, last_activity=IDLE_SINCE),)
    )


async def issues_of(session: AsyncSession, kind: IssueType) -> list[Issue]:
    return list(await session.scalars(select(Issue).where(Issue.type == kind).order_by(Issue.id)))


async def failed_submit(
    session: AsyncSession, roots: dict[str, Path], *, retry_at: str | None, attempt: int | None
) -> Job:
    """一筆送單失敗的 Job，最後一次失敗的事件照 `jobs._fail` 的形狀寫。"""
    job = await setup_job(session, roots, state=JobState.SUBMIT_FAILED)
    job.error = "unavailable: qBittorrent did not answer"
    payload: dict[str, object] = {"error": job.error}
    if attempt is not None:
        payload |= {"attempt": attempt, "retry_at": retry_at}
    await record_event(session, job, EventType.SUBMIT_FAILED, actor="system", payload=payload)
    await session.commit()
    return job


def empty_client() -> FakeQbittorrentClient:
    return FakeQbittorrentClient(torrents=())


class TestStalled:
    async def test_a_stalled_download_opens_one_issue(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job = await setup_job(session, roots, state=JobState.DOWNLOADING)
        client = stalled_client()

        await run(session, client)
        await run(session, client, now=NOW + timedelta(seconds=5))

        (issue,) = await issues_of(session, IssueType.STALLED)
        assert issue.status is IssueStatus.OPEN
        assert issue.job_hash == job.hash
        assert issue.subject == job.hash
        assert (issue.detail_json or {})["name"] == job.name

    async def test_it_closes_when_data_moves_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await setup_job(session, roots, state=JobState.DOWNLOADING)
        client = stalled_client()
        await run(session, client)

        client.torrents = (status(state="downloading", progress=0.5),)
        await run(session, client, now=NOW + timedelta(seconds=5))

        (issue,) = await issues_of(session, IssueType.STALLED)
        assert issue.status is IssueStatus.RESOLVED
        assert issue.resolved_by == "system"

    async def test_ignoring_it_holds_while_it_stays_stalled_and_a_new_stall_reopens(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """poller 每一輪都量：照「這一次不處理」的話，忽略 5 秒後就重開（`STAYS_IGNORED`）。"""
        await setup_job(session, roots, state=JobState.DOWNLOADING)
        client = stalled_client()
        await run(session, client)
        (issue,) = await issues_of(session, IssueType.STALLED)
        await ignore_issue(session, issue.id, actor="7")

        await run(session, client, now=NOW + timedelta(seconds=5))
        assert [row.status for row in await issues_of(session, IssueType.STALLED)] == [
            IssueStatus.IGNORED
        ]

        client.torrents = (status(state="downloading", progress=0.5),)
        await run(session, client, now=NOW + timedelta(seconds=10))
        client.torrents = stalled_client().torrents
        await run(session, client, now=NOW + timedelta(seconds=15))

        assert [row.status for row in await issues_of(session, IssueType.STALLED)] == [
            IssueStatus.IGNORED,
            IssueStatus.OPEN,
        ]


class TestSubmitFailed:
    async def test_retries_spent_opens_one(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job = await failed_submit(session, roots, retry_at=None, attempt=5)

        await run(session, empty_client())
        await run(session, empty_client(), now=NOW + timedelta(seconds=5))

        (issue,) = await issues_of(session, IssueType.SUBMIT_FAILED)
        assert issue.status is IssueStatus.OPEN
        assert issue.job_hash == job.hash
        assert (issue.detail_json or {})["error"] == job.error

    async def test_a_failure_that_will_not_change_opens_one(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`.torrent` 404、qBittorrent 拒絕：沒有 `attempt`，從來沒排過自動重送。"""
        await failed_submit(session, roots, retry_at=None, attempt=None)

        await run(session, empty_client())

        assert len(await issues_of(session, IssueType.SUBMIT_FAILED)) == 1

    async def test_one_still_waiting_for_an_automatic_retry_is_not_stuck(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """排著 `retry_at` 的還在路上，即使時間已過（前提不成立時 `retry_due` 留著它不花次數）。"""
        await failed_submit(
            session, roots, retry_at=(NOW - timedelta(hours=1)).isoformat(), attempt=2
        )

        await run(session, empty_client())

        assert await issues_of(session, IssueType.SUBMIT_FAILED) == []

    async def test_a_rejected_resubmit_stays_under_its_client_removed_issue(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """重新送單被拒、落回 `submit_failed` 的那一筆，`client_removed` 那一件仍然說著它
        （`STANDS_WHILE`）：同一筆不開第二件，「等你處理」也不重複算。"""
        job = await failed_submit(session, roots, retry_at=None, attempt=None)
        await record_issue(session, IssueType.CLIENT_REMOVED, job_hash=job.hash, now=NOW)
        await session.commit()

        await run(session, empty_client())

        assert await issues_of(session, IssueType.SUBMIT_FAILED) == []

    async def test_it_closes_once_the_job_moves_on(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Job 頁上按了重試、qBittorrent 收下了：下一輪 poller 收掉。"""
        job = await failed_submit(session, roots, retry_at=None, attempt=5)
        await run(session, empty_client())

        job.state = JobState.SUBMITTED
        await session.commit()
        await run(session, empty_client(), now=NOW + timedelta(seconds=5))

        (issue,) = await issues_of(session, IssueType.SUBMIT_FAILED)
        assert issue.status is IssueStatus.RESOLVED

    async def test_it_closes_once_an_automatic_retry_is_scheduled_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Job 頁上按了重試、又暫時失敗：狀態沒變，但重新排了自動重送，它又在路上了。那一件說的
        「不會再自動重送」已經不是現況（code-review）。"""
        job = await failed_submit(session, roots, retry_at=None, attempt=5)
        await run(session, empty_client())

        await record_event(
            session,
            job,
            EventType.SUBMIT_FAILED,
            actor="7",
            payload={"error": job.error, "attempt": 1, "retry_at": NOW.isoformat()},
        )
        await session.commit()
        await run(session, empty_client(), now=NOW + timedelta(seconds=5))

        assert [row.status for row in await issues_of(session, IssueType.SUBMIT_FAILED)] == [
            IssueStatus.RESOLVED
        ]


class TestImportFailed:
    async def test_it_opens_one_and_closes_once_the_job_moves_on(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job = await setup_job(session, roots, state=JobState.IMPORT_FAILED)
        job.error = "link_failed: EXDEV"
        await session.commit()

        await run(session, empty_client())
        (issue,) = await issues_of(session, IssueType.IMPORT_FAILED)
        assert issue.status is IssueStatus.OPEN
        assert (issue.detail_json or {})["error"] == "link_failed: EXDEV"

        job.state = JobState.IMPORTING
        await session.commit()
        await run(session, empty_client(), now=NOW + timedelta(seconds=5))

        assert [row.status for row in await issues_of(session, IssueType.IMPORT_FAILED)] == [
            IssueStatus.RESOLVED
        ]


class TestButtons:
    """沿用 Job 頁的那幾顆（票面第 2 點）：按下去之後 Job 離開那個狀態、那一件收掉。"""

    async def offered(self, session: AsyncSession, kind: IssueType) -> tuple[IssueAction, ...]:
        (view,) = [row for row in await list_issues(session) if row.type is kind]
        return view.actions

    async def test_giving_up_on_a_stalled_download_touches_nothing_on_disk(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """放棄＝刪除範圍四個旗標全不勾（同兩顆「承認」）：Job 進 `removed`，qBittorrent 不動。"""
        job = await setup_job(session, roots, state=JobState.DOWNLOADING)
        client = stalled_client()
        await run(session, client)
        assert await self.offered(session, IssueType.STALLED) == (IssueAction.ABANDON,)
        (issue,) = await issues_of(session, IssueType.STALLED)

        await resolve_issue(
            session, FakeClientFactory(qbittorrent=client), issue.id, IssueAction.ABANDON, actor="7"
        )

        await session.refresh(job)
        assert job.state is JobState.REMOVED
        assert client.deleted == []
        await run(session, client, now=NOW + timedelta(seconds=5))
        assert [row.status for row in await issues_of(session, IssueType.STALLED)] == [
            IssueStatus.RESOLVED
        ]

    async def test_retrying_an_import_puts_the_job_back_to_importing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job = await setup_job(session, roots, state=JobState.IMPORT_FAILED)
        await run(session, empty_client())
        assert await self.offered(session, IssueType.IMPORT_FAILED) == (
            IssueAction.RETRY_IMPORT,
            IssueAction.ABANDON,
        )
        (issue,) = await issues_of(session, IssueType.IMPORT_FAILED)

        await resolve_issue(
            session, FakeClientFactory(), issue.id, IssueAction.RETRY_IMPORT, actor="7"
        )

        await session.refresh(job)
        assert job.state is JobState.IMPORTING
        await session.refresh(issue)
        assert issue.status is IssueStatus.RESOLVED

    async def test_resubmitting_sends_the_saved_link_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job = await failed_submit(session, roots, retry_at=None, attempt=5)
        client = empty_client()
        await run(session, client)
        assert await self.offered(session, IssueType.SUBMIT_FAILED) == (
            IssueAction.RESUBMIT,
            IssueAction.ABANDON,
        )
        (issue,) = await issues_of(session, IssueType.SUBMIT_FAILED)

        await resolve_issue(
            session,
            FakeClientFactory(qbittorrent=client),
            issue.id,
            IssueAction.RESUBMIT,
            actor="7",
        )

        assert [row.magnet for row in client.added] == [job.source_url]
        await session.refresh(job)
        assert job.state is JobState.SUBMITTED

    async def test_the_buttons_go_once_the_job_has_moved_on(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Job 頁上先按了重試：這一列在 poller 收掉它之前只剩「忽略」，按下去不會把它拉回去。"""
        job = await setup_job(session, roots, state=JobState.IMPORT_FAILED)
        await run(session, empty_client())
        job.state = JobState.IMPORTING
        await session.commit()

        assert await self.offered(session, IssueType.IMPORT_FAILED) == ()


class TestWaitingForYou:
    """算進「有 N 件等你處理」與它的推播（票面第 4 點）：看守只看開著的 Issue，所以這一條守的是
    卡住的 Job 真的成了一件 Issue，而推播說得出是哪一種。"""

    async def test_a_stalled_download_is_pushed_as_one_waiting_issue(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await setup_job(session, roots, state=JobState.DOWNLOADING)
        await first_look(session)
        await run(session, stalled_client())
        factory = FakeClientFactory()

        await wave(session, factory)

        message = only(factory)
        assert message.title == "有 1 件等你處理"
        assert message.description == "新增 1 件：1 個 Issue（停滯）"

    async def test_a_stall_that_clears_before_the_push_is_not_pushed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """送出前重算：資料在合併窗內又動起來，那一件已經收掉，這一則不送。"""
        await setup_job(session, roots, state=JobState.DOWNLOADING)
        await first_look(session)
        client = stalled_client()
        await run(session, client)
        factory = FakeClientFactory()
        await watch(session, timedelta(seconds=30))
        client.torrents = (status(state="downloading", progress=0.5),)
        await run(session, client, now=NOW + timedelta(seconds=5))

        await wave(session, factory)

        assert factory.discord_.sent == []
