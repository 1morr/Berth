"""管線那三種 Issue 的按鈕（brief §9.1、plan §3.1、M2 票 09c）。

起點是**真的走一輪 poller**：qBittorrent 替身說壞了 → Job 進壞掉的狀態、開出一件 Issue → 按下去
→ 替身照真的那一台的樣子回應 → 再走一輪 poller，Job 一路走到 `completed`、清單上什麼都沒有。
「Issue 變成 resolved」本身不算修好。

qBittorrent 問不到的那幾條：按鈕說得出為什麼，Issue 留著 `open`，Job 一步都沒動。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.qbittorrent import TorrentRejectedError
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.adapters.torrent import TorrentSource
from berth.adapters.torrent_fake import FakeTorrentFetcher
from berth.domain import EventType, IssueAction, IssueRefusal, IssueStatus, IssueType, JobState
from berth.models import Issue, Job
from berth.services.issues import IssueRejectedError, list_issues, resolve_issue
from tests.integration.factories import FakeClientFactory
from tests.integration.test_downloads import FILES, HASH, NOW, events_of, run, setup_job, status

pytestmark = pytest.mark.asyncio

ACTOR = "7"
DONE = int(NOW.timestamp())


async def broken(
    session: AsyncSession, roots: dict[str, Path], *, state: str
) -> tuple[Job, FakeClientFactory]:
    """一筆下載到一半的 Job，然後 qBittorrent 說它壞了（`state` 是客戶端的字串）。

    `state=""` 代表那一筆從客戶端消失了。
    """
    job = await setup_job(session, roots, state=JobState.SUBMITTED)
    client = FakeQbittorrentClient(torrents=(status(progress=0.4),), files={HASH: FILES})
    await run(session, client)
    client.torrents = (status(state=state, progress=0.4),) if state else ()
    await run(session, client)
    await session.refresh(job)
    return job, FakeClientFactory(qbittorrent=client)


async def the_issue(session: AsyncSession, kind: IssueType) -> Issue:
    (issue,) = await session.scalars(
        select(Issue).where(Issue.type == kind, Issue.status == IssueStatus.OPEN)
    )
    return issue


async def press(
    session: AsyncSession, factory: FakeClientFactory, issue: Issue, action: IssueAction
) -> None:
    await resolve_issue(session, factory, issue.id, action, actor=ACTOR)


async def refused(
    session: AsyncSession, factory: FakeClientFactory, issue: Issue, action: IssueAction
) -> IssueRefusal:
    with pytest.raises(IssueRejectedError) as refusal:
        await press(session, factory, issue, action)
    await session.refresh(issue)
    assert issue.status is IssueStatus.OPEN
    return refusal.value.reason


async def offered(session: AsyncSession, kind: IssueType) -> tuple[IssueAction, ...]:
    (view,) = [row for row in await list_issues(session) if row.type is kind]
    return view.actions


async def finishes(session: AsyncSession, job: Job, client: FakeQbittorrentClient) -> None:
    """qBittorrent 說它做完了：再走一輪 poller，Job 到 `completed`、沒有新的 Issue。"""
    client.torrents = (status(state="stalledUP", progress=1.0, completion_on=DONE),)
    await run(session, client)
    await session.refresh(job)
    assert job.state is JobState.COMPLETED
    assert [row.type for row in await list_issues(session)] == []


async def state_of(session: AsyncSession, job: Job) -> JobState:
    """重讀一次。回傳值而不是讓呼叫端讀 `job.state`：mypy 會把同一個屬性前後兩次斷言的值
    收窄成互斥，第二次斷言就成了「走不到」。"""
    await session.refresh(job)
    return job.state


def client_of(factory: FakeClientFactory) -> FakeQbittorrentClient:
    return factory.qbittorrent_


# --- missing_files -----------------------------------------------------


class TestRecheck:
    async def test_the_row_is_named_after_the_download(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """清單上那一列沒有路徑：只剩 hash 的話分不出是哪一筆（2026-09-23 實跑抓到）。"""
        job, _ = await broken(session, roots, state="missingFiles")

        (view,) = await list_issues(session)

        assert view.detail["name"] == job.name

    async def test_it_is_offered_first_then_accepting_the_loss(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _ = await broken(session, roots, state="missingFiles")

        assert job.state is JobState.MISSING_FILES
        assert await offered(session, IssueType.MISSING_FILES) == (
            IssueAction.RECHECK,
            IssueAction.ACCEPT_LOSS,
        )

    async def test_it_rechecks_restarts_and_the_poller_takes_it_from_there(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """recheck → start（2026-09-23 對 4.4.5 與 5.2.3 實測：資料回來了就是做種中）。

        Job 回到 `metadata_ready`：檔案清單早就到手了，從這一站起完成判定照常走。
        """
        job, factory = await broken(session, roots, state="missingFiles")
        issue = await the_issue(session, IssueType.MISSING_FILES)

        await press(session, factory, issue, IssueAction.RECHECK)

        client = client_of(factory)
        assert client.rechecked == [HASH]
        assert client.started == [HASH]
        await session.refresh(job)
        assert job.state is JobState.METADATA_READY
        await session.refresh(issue)
        assert issue.status is IssueStatus.RESOLVED
        retried = [row for row in await events_of(session) if row.type == EventType.RETRIED.value]
        assert retried[-1].payload_json == {"state": "metadata_ready", "action": "recheck"}
        # 校驗中的那一輪不是壞掉，也還沒做完。
        await run(session, client)
        await session.refresh(job)
        assert job.state is JobState.METADATA_READY
        await finishes(session, job, client)

    async def test_a_job_without_a_file_list_goes_back_to_waiting_for_one(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """metadata 還沒到就壞掉的那一筆：回 `submitted`，poller 照常先等清單。"""
        job = await setup_job(session, roots, state=JobState.SUBMITTED)
        client = FakeQbittorrentClient(torrents=(status(state="missingFiles"),))
        await run(session, client)
        factory = FakeClientFactory(qbittorrent=client)

        await press(
            session, factory, await the_issue(session, IssueType.MISSING_FILES), IssueAction.RECHECK
        )

        await session.refresh(job)
        assert job.state is JobState.SUBMITTED

    async def test_an_unreachable_client_changes_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, factory = await broken(session, roots, state="missingFiles")
        issue = await the_issue(session, IssueType.MISSING_FILES)
        client_of(factory).error = ServiceUnavailableError("connection refused")

        assert await refused(session, factory, issue, IssueAction.RECHECK) is (
            IssueRefusal.CLIENT_UNREACHABLE
        )
        await session.refresh(job)
        assert job.state is JobState.MISSING_FILES

    async def test_a_job_that_moved_on_offers_nothing_but_ignore(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Job 已經不在那個壞掉的狀態（另一個分頁按過、或它被刪了）：按鈕不畫，直接打是拒絕。"""
        job, factory = await broken(session, roots, state="missingFiles")
        issue = await the_issue(session, IssueType.MISSING_FILES)
        job.state = JobState.REMOVED
        await session.commit()

        assert await offered(session, IssueType.MISSING_FILES) == ()
        assert await refused(session, factory, issue, IssueAction.RECHECK) is (
            IssueRefusal.ACTION_NOT_AVAILABLE
        )
        assert client_of(factory).rechecked == []


class TestAcceptTheLoss:
    async def test_the_download_ends_and_nothing_is_touched(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """刪除範圍四個旗標全不勾（2026-09-23 使用者拍板）：Job 進 `removed`，qBittorrent 一個
        請求都沒收到，時間線一筆 `deleted`。"""
        job, factory = await broken(session, roots, state="missingFiles")

        await press(
            session,
            factory,
            await the_issue(session, IssueType.MISSING_FILES),
            IssueAction.ACCEPT_LOSS,
        )

        await session.refresh(job)
        assert job.state is JobState.REMOVED
        client = client_of(factory)
        assert (client.deleted, client.rechecked, client.started) == ([], [], [])
        deleted = [row for row in await events_of(session) if row.type == EventType.DELETED.value]
        assert deleted[-1].payload_json == {
            "links": 0,
            "sources": 0,
            "torrent": False,
            "purged": False,
            "freed": 0,
            "unmanaged": [],
        }
        # 那個 torrent 還在 qBittorrent 上，但它有 Job：不是無主的，下一輪什麼都不開。
        await run(session, client)
        assert [row.type for row in await list_issues(session)] == []


# --- client_error ------------------------------------------------------


class TestRetry:
    async def test_it_restarts_the_torrent_and_the_poller_takes_it_from_there(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """重新開始會清掉客戶端的錯誤（原始碼 `clear_error()`，brief §20.2）。不 recheck：
        錯誤不是資料的問題。"""
        job, factory = await broken(session, roots, state="error")
        issue = await the_issue(session, IssueType.CLIENT_ERROR)
        assert await offered(session, IssueType.CLIENT_ERROR) == (IssueAction.RETRY,)

        await press(session, factory, issue, IssueAction.RETRY)

        client = client_of(factory)
        assert (client.started, client.rechecked) == ([HASH], [])
        await session.refresh(job)
        assert job.state is JobState.METADATA_READY
        await session.refresh(issue)
        assert issue.status is IssueStatus.RESOLVED
        await finishes(session, job, client)

    async def test_an_unreachable_client_changes_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, factory = await broken(session, roots, state="error")
        client_of(factory).error = ServiceUnavailableError("connection refused")

        reason = await refused(
            session, factory, await the_issue(session, IssueType.CLIENT_ERROR), IssueAction.RETRY
        )

        assert reason is IssueRefusal.CLIENT_UNREACHABLE
        await session.refresh(job)
        assert job.state is JobState.CLIENT_ERROR


# --- client_removed ----------------------------------------------------


class TestResubmit:
    async def test_it_is_offered_first_then_accepting_the_removal(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _ = await broken(session, roots, state="")

        assert job.state is JobState.CLIENT_REMOVED
        assert await offered(session, IssueType.CLIENT_REMOVED) == (
            IssueAction.RESUBMIT,
            IssueAction.ACCEPT_REMOVAL,
        )

    async def test_it_adds_the_same_torrent_again_and_the_poller_takes_it_from_there(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """照存下來的下載連結再送一次（同 `submit_failed` 的重試）。同一個 hash，所以
        `job_files` 不重建，poller 從 `submitted` 照常往前走。"""
        job, factory = await broken(session, roots, state="")
        issue = await the_issue(session, IssueType.CLIENT_REMOVED)

        await press(session, factory, issue, IssueAction.RESUBMIT)

        client = client_of(factory)
        assert [row.magnet for row in client.added] == [job.source_url]
        await session.refresh(job)
        assert job.state is JobState.SUBMITTED
        await session.refresh(issue)
        assert issue.status is IssueStatus.RESOLVED
        client.torrents = (status(progress=0.1),)
        await run(session, client)
        await finishes(session, job, client)

    async def test_an_unreachable_client_changes_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """先問 qBittorrent 在不在才動那一列：問不到就不讓它變成 `submit_failed`。"""
        job, factory = await broken(session, roots, state="")
        client_of(factory).error = ServiceUnavailableError("connection refused")
        before = len(await events_of(session))

        reason = await refused(
            session,
            factory,
            await the_issue(session, IssueType.CLIENT_REMOVED),
            IssueAction.RESUBMIT,
        )

        assert reason is IssueRefusal.CLIENT_UNREACHABLE
        await session.refresh(job)
        assert job.state is JobState.CLIENT_REMOVED
        assert len(await events_of(session)) == before

    async def test_a_link_that_now_gives_another_torrent_is_not_sent(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Job 的主鍵就是 info hash：送出去的會是另一筆沒有 Job 的 torrent。"""
        job, factory = await broken(session, roots, state="")
        factory.torrent_ = FakeTorrentFetcher(
            sources={job.source_url: TorrentSource(info_hash="f" * 40, magnet=job.source_url)}
        )

        reason = await refused(
            session,
            factory,
            await the_issue(session, IssueType.CLIENT_REMOVED),
            IssueAction.RESUBMIT,
        )

        assert reason is IssueRefusal.SOURCE_UNAVAILABLE
        assert client_of(factory).added == []
        await session.refresh(job)
        assert job.state is JobState.CLIENT_REMOVED

    async def test_a_rejected_resubmission_leaves_the_issue_open_to_press_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """qBittorrent 答話了但不收：Job 照舊落在 `submit_failed`，這一件仍然開著，
        修好之後再按一次就是再送一次。"""
        job, factory = await broken(session, roots, state="")
        issue = await the_issue(session, IssueType.CLIENT_REMOVED)
        client = client_of(factory)
        client.add_error = TorrentRejectedError("torrents/add: 409 Conflict")

        assert await refused(session, factory, issue, IssueAction.RESUBMIT) is (
            IssueRefusal.RESUBMIT_FAILED
        )
        assert await state_of(session, job) is JobState.SUBMIT_FAILED
        assert await offered(session, IssueType.CLIENT_REMOVED) == (
            IssueAction.RESUBMIT,
            IssueAction.ACCEPT_REMOVAL,
        )

        client.add_error = None
        await press(session, factory, issue, IssueAction.RESUBMIT)

        assert await state_of(session, job) is JobState.SUBMITTED
        await session.refresh(issue)
        assert issue.status is IssueStatus.RESOLVED


class TestAcceptTheRemoval:
    async def test_the_download_ends_and_nothing_is_touched(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, factory = await broken(session, roots, state="")

        await press(
            session,
            factory,
            await the_issue(session, IssueType.CLIENT_REMOVED),
            IssueAction.ACCEPT_REMOVAL,
        )

        await session.refresh(job)
        assert job.state is JobState.REMOVED
        client = client_of(factory)
        assert (client.deleted, client.added) == ([], [])
        await run(session, client)
        assert [row.type for row in await list_issues(session)] == []
