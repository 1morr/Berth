"""卡死的 Job 與管線 Issue 自收（plan §3.1、§3.2、§2.4、M3 票 02）。

RSS 半夜送出去的單沒有人看著。這一份測的是**沒有人按按鈕時**那幾筆 Job 自己找得到出路：

- `submit_failed` 而 qBittorrent 其實收下了（逾時、回應讀到一半斷線）：poller 認回來。
- `requested` 停在程序中途掛掉的那一刻：重啟時落到 `submit_failed`，交給上一條與重試。
- 管線那三種 Issue：Job 在別處被修好（使用者在 qBittorrent 裡自己 recheck、重新加回 torrent）
  之後由系統收掉；還壞著的時候不收。

`guarded` 吞掉的非預期例外在 `test_plan.py` 的 `TestRoundIsolation`：它要一個真的規劃器。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.qbittorrent import TorrentStatus
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.config import Config
from berth.domain import EventType, IssueStatus, IssueType, JobState
from berth.main import create_app
from berth.models import Issue, Job, JobFile, Media
from berth.services.jobs import INTERRUPTED
from tests.integration.test_downloads import (
    FILES,
    HASH,
    NOW,
    SAVE_PATH,
    events_of,
    payload,
    run,
    setup_job,
    status,
)

pytestmark = pytest.mark.asyncio

DONE = int(NOW.timestamp())


async def issues_of(session: AsyncSession, kind: IssueType) -> list[Issue]:
    rows = await session.scalars(select(Issue).where(Issue.type == kind).order_by(Issue.id))
    return list(rows)


async def state_of(session: AsyncSession, job: Job) -> JobState:
    """重讀一次。回傳值而不是讓呼叫端讀 `job.state`：mypy 會把同一個屬性前後兩次斷言的值
    收窄成互斥，第二次斷言就成了「走不到」。"""
    await session.refresh(job)
    return job.state


async def status_of(session: AsyncSession, issue: Issue) -> IssueStatus:
    await session.refresh(issue)
    return issue.status


# --- submit_failed 而 qBittorrent 其實收下了 --------------------------------


class TestSubmitFailedButAccepted:
    async def test_the_poller_takes_it_back_and_it_walks_on(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`torrents/add` 逾時而 qBittorrent 收下了：同一個 hash 出現在客戶端，一輪之後往前走。"""
        job = await setup_job(session, roots, state=JobState.SUBMIT_FAILED)
        job.error = "ReadTimeout"
        await session.commit()
        client = FakeQbittorrentClient(torrents=(status(progress=0.3),), files={HASH: FILES})

        await run(session, client)

        # 一輪可以走好幾步（plan §3.1）：認回來之後清單到手、有進度。
        assert await state_of(session, job) is JobState.DOWNLOADING
        assert job.error == ""
        assert job.save_path == SAVE_PATH

    async def test_it_is_not_an_unknown_torrent(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await setup_job(session, roots, state=JobState.SUBMIT_FAILED)
        client = FakeQbittorrentClient(torrents=(status(),), files={HASH: FILES})

        await run(session, client)

        assert await issues_of(session, IssueType.UNKNOWN_TORRENT) == []

    async def test_the_timeline_says_qbittorrent_had_it_after_all(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await setup_job(session, roots, state=JobState.SUBMIT_FAILED)
        client = FakeQbittorrentClient(torrents=(status(state="metaDL"),))

        await run(session, client)

        recovered = [
            row for row in await events_of(session) if row.type == EventType.RECOVERED.value
        ]
        assert [payload(row) for row in recovered] == [
            {
                "from": JobState.SUBMIT_FAILED.value,
                "state": JobState.SUBMITTED.value,
                "client_state": "metaDL",
            }
        ]

    async def test_the_folder_name_freezes_as_if_the_submit_had_succeeded(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """送單成功那一刻凍結資料夾名（brief §4.5）。它其實成功了，所以認回來的那一刻凍結。"""
        job = await setup_job(session, roots, state=JobState.SUBMIT_FAILED)
        client = FakeQbittorrentClient(torrents=(status(state="metaDL"),))

        await run(session, client)

        media = await session.get(Media, "tv:120089")
        assert media is not None
        await session.refresh(media)
        assert media.folder_frozen is True
        assert media.default_route_id == job.route_id

    async def test_one_qbittorrent_does_not_have_stays_where_it_is(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """不在客戶端裡的 `submit_failed` 就是沒送到：不是 `client_removed`，等人重試。"""
        job = await setup_job(session, roots, state=JobState.SUBMIT_FAILED)
        client = FakeQbittorrentClient(torrents=())

        await run(session, client)

        assert await state_of(session, job) is JobState.SUBMIT_FAILED
        assert await issues_of(session, IssueType.CLIENT_REMOVED) == []


# --- requested 在程序中途掛掉 -----------------------------------------------


class TestInterruptedRequest:
    async def test_a_restart_drops_it_into_submit_failed(
        self, session: AsyncSession, roots: dict[str, Path], config: Config
    ) -> None:
        """啟動的那一刻不可能有送單正在路上，所以停在 `requested` 的都是被打斷的那一次。"""
        job = await setup_job(session, roots, state=JobState.REQUESTED)
        app = create_app(config)

        async with app.router.lifespan_context(app):
            pass

        assert await state_of(session, job) is JobState.SUBMIT_FAILED
        assert job.error == INTERRUPTED
        failed = [row for row in await events_of(session) if row.type == "submit_failed"]
        assert [payload(row) for row in failed] == [{"error": INTERRUPTED}]

    async def test_other_states_are_left_alone(
        self, session: AsyncSession, roots: dict[str, Path], config: Config
    ) -> None:
        job = await setup_job(session, roots, state=JobState.SUBMITTED)
        app = create_app(config)

        async with app.router.lifespan_context(app):
            pass

        assert await state_of(session, job) is JobState.SUBMITTED

    async def test_if_qbittorrent_got_it_the_poller_takes_it_back(
        self, session: AsyncSession, roots: dict[str, Path], config: Config
    ) -> None:
        """兩條接在一起：重啟落到 `submit_failed`，客戶端裡有同一個 hash 就認回來。"""
        job = await setup_job(session, roots, state=JobState.REQUESTED)
        app = create_app(config)
        async with app.router.lifespan_context(app):
            pass
        # 這個 session 比那一次重啟活得久：先讀回重啟寫下的狀態（poller 每一輪開新的 session）。
        assert await state_of(session, job) is JobState.SUBMIT_FAILED
        client = FakeQbittorrentClient(torrents=(status(state="metaDL"),))

        await run(session, client)

        assert await state_of(session, job) is JobState.SUBMITTED


# --- 管線 Issue 由系統收 ---------------------------------------------------


async def broken(session: AsyncSession, roots: dict[str, Path], *, state: str) -> tuple[Job, Issue]:
    """一筆下載到一半的 Job，然後 qBittorrent 說它壞了。`state=""` 是它從客戶端消失了。"""
    job = await setup_job(session, roots, state=JobState.SUBMITTED)
    client = FakeQbittorrentClient(torrents=(status(progress=0.4),), files={HASH: FILES})
    await run(session, client)
    client.torrents = (status(state=state, progress=0.4),) if state else ()
    await run(session, client)
    (issue,) = await session.scalars(select(Issue).where(Issue.status == IssueStatus.OPEN))
    return job, issue


async def poll(session: AsyncSession, *torrents: TorrentStatus) -> None:
    client = FakeQbittorrentClient(torrents=torrents, files={HASH: FILES})
    await run(session, client)


class TestMissingFilesClosesItself:
    async def test_a_recheck_done_in_qbittorrent_closes_it(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """使用者在 qBittorrent 裡自己按了 recheck：校驗中不是壞掉，Job 回到 poller 的主幹。"""
        job, issue = await broken(session, roots, state="missingFiles")

        await poll(session, status(state="checkingDL", progress=0.0))

        assert await state_of(session, job) is JobState.METADATA_READY
        await session.refresh(issue)
        assert issue.status is IssueStatus.RESOLVED
        assert issue.resolved_by == "system"

    async def test_still_missing_stays_open(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, issue = await broken(session, roots, state="missingFiles")

        await poll(session, status(state="missingFiles", progress=0.4))

        assert await state_of(session, job) is JobState.MISSING_FILES
        await session.refresh(issue)
        assert issue.status is IssueStatus.OPEN

    async def test_files_berth_found_missing_stay_missing_until_they_are_back(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Berth 自己發現的那一種：客戶端說做完了、狀態字串不是壞掉，而檔案不在。

        只看客戶端狀態的話它每一輪都會「恢復」再壞一次，時間線與 Issue 清單一起來回翻。
        """
        visible = roots["complete"] / "anime"
        visible.mkdir(parents=True, exist_ok=True)
        done = status(state="stalledUP", progress=1.0, completion_on=DONE, save_path=str(visible))
        job = await setup_job(session, roots, state=JobState.DOWNLOADING)
        session.add_all(
            [
                JobFile(job_hash=HASH, rel_path=row.name, size=row.size, priority=row.priority)
                for row in FILES
            ]
        )
        await session.commit()
        await poll(session, done)
        assert await state_of(session, job) is JobState.MISSING_FILES
        before = len(await events_of(session))

        await poll(session, done)

        assert await state_of(session, job) is JobState.MISSING_FILES
        assert len(await events_of(session)) == before
        (issue,) = await issues_of(session, IssueType.MISSING_FILES)
        assert await status_of(session, issue) is IssueStatus.OPEN

        for row in FILES:
            target = visible / row.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"")
        await poll(session, done)

        assert await state_of(session, job) is JobState.COMPLETED
        assert await status_of(session, issue) is IssueStatus.RESOLVED
        assert issue.resolved_by == "system"


class TestClientErrorClosesItself:
    async def test_a_restart_done_in_qbittorrent_closes_it(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, issue = await broken(session, roots, state="error")

        await poll(session, status(state="downloading", progress=0.5))

        assert await state_of(session, job) is JobState.DOWNLOADING
        await session.refresh(issue)
        assert issue.status is IssueStatus.RESOLVED
        assert issue.resolved_by == "system"

    async def test_still_in_error_stays_open(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, issue = await broken(session, roots, state="error")

        await poll(session, status(state="error", progress=0.4))

        assert await state_of(session, job) is JobState.CLIENT_ERROR
        await session.refresh(issue)
        assert issue.status is IssueStatus.OPEN


class TestClientRemovedClosesItself:
    async def test_adding_the_torrent_back_closes_it(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """使用者自己把同一個 torrent 加回 qBittorrent：清單早就到手，從 `metadata_ready` 接。"""
        job, issue = await broken(session, roots, state="")

        await poll(session, status(state="downloading", progress=0.4))

        assert await state_of(session, job) is JobState.DOWNLOADING
        await session.refresh(issue)
        assert issue.status is IssueStatus.RESOLVED
        assert issue.resolved_by == "system"

    async def test_still_gone_stays_open(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, issue = await broken(session, roots, state="")

        await poll(session)

        assert await state_of(session, job) is JobState.CLIENT_REMOVED
        await session.refresh(issue)
        assert issue.status is IssueStatus.OPEN

    async def test_a_rejected_resubmission_still_counts_as_broken(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """「重新送單」被拒的那一筆落在 `submit_failed`，而那一件 Issue 刻意開著（M2 票 09c）。"""
        job, issue = await broken(session, roots, state="")
        job.state = JobState.SUBMIT_FAILED
        await session.commit()

        await poll(session)

        await session.refresh(issue)
        assert issue.status is IssueStatus.OPEN

    async def test_a_job_moved_on_by_another_path_closes_it(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """M2 票 09c 的延後項：Job 被別的路徑推走（Job 頁上重試成功）之後，這一件不再是現況。"""
        job, issue = await broken(session, roots, state="")
        job.state = JobState.SUBMITTED
        await session.commit()

        await poll(session, status(state="metaDL"))

        await session.refresh(issue)
        assert issue.status is IssueStatus.RESOLVED
        assert issue.resolved_by == "system"


class TestTimeline:
    async def test_recovering_is_one_event_that_says_from_where(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await broken(session, roots, state="error")

        await poll(session, status(state="downloading", progress=0.5))

        recovered = [
            row for row in await events_of(session) if row.type == EventType.RECOVERED.value
        ]
        assert [payload(row)["from"] for row in recovered] == [JobState.CLIENT_ERROR.value]

    async def test_breaking_again_right_after_is_written_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """恢復是事件去重的界線（plan §3.3）：一分鐘內又壞一次，那一筆與第一次一字不差也要寫。"""
        await broken(session, roots, state="error")
        await poll(session, status(state="downloading", progress=0.4))

        await poll(session, status(state="error", progress=0.4))

        detected = [row for row in await events_of(session) if row.type == "issue_detected"]
        assert len(detected) == 2
        opened = await issues_of(session, IssueType.CLIENT_ERROR)
        assert [row.status for row in opened] == [IssueStatus.RESOLVED, IssueStatus.OPEN]
