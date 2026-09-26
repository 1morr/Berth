"""其餘幾種 Issue 的按鈕（brief §9.1 的「預設建議動作」那一欄、M2 票 09）。

`test_issue_actions.py` 釘 `library_link_missing` 的三顆（票 05）；這一份是票 09 加的六顆，
外加 `unmanaged_library_file` 的那一條：**它沒有任何一顆會刪東西**。

起點照舊是**真的走完一輪**：入庫 → 造出破壞 → 對帳 → 拿到那一件 Issue → 按下去 → 再對帳一輪
什麼都沒有。斷言貼著磁碟：「Issue 變成 resolved」本身不算修好。

認領類的三顆（`orphan_complete` 的重新入庫、`unknown_torrent` 的認領、`unmanaged_library_file`
的認領進帳本）在 `test_claims.py`（票 10）；管線那三種的按鈕在票 09c。
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.jellyfin.fake import LIBRARY_SCAN_TASK
from berth.domain import (
    ACTION_DELETES,
    ISSUE_ACTIONS,
    IssueAction,
    IssueRefusal,
    IssueStatus,
    IssueType,
    JobState,
    LedgerStatus,
)
from berth.models import Issue, Job, LedgerEntry, Route
from berth.models.types import utcnow
from berth.services.events import EventHub
from berth.services.hints import JobHints
from berth.services.importer import sweep_imports
from berth.services.issues import IssueRejectedError, list_issues, record_issue, resolve_issue
from berth.services.plan import sweep_plans
from berth.services.reconcile import reconcile_once
from berth.services.resolver import sweep_resolutions
from tests.integration.factories import FakeClientFactory
from tests.integration.test_deletion import LINKS, imported
from tests.integration.test_importer import ledger_of, same_file
from tests.integration.test_plan import NOW
from tests.integration.test_reconcile import issues_of
from tests.integration.test_reconcile_checks import (
    SPY,
    features,
    open_of,
    scanned,
    stray_folder,
    torrent,
)

pytestmark = pytest.mark.asyncio

ACTOR = "7"
LATER = NOW + timedelta(days=1)


async def the_one(session: AsyncSession, kind: IssueType) -> Issue:
    (issue,) = await open_of(session, kind)
    return issue


async def press(
    session: AsyncSession,
    factory: FakeClientFactory,
    issue: Issue,
    action: IssueAction,
    *,
    plans: JobHints | None = None,
) -> None:
    await resolve_issue(session, factory, issue.id, action, actor=ACTOR, plans=plans)


async def refused(
    session: AsyncSession, factory: FakeClientFactory, issue: Issue, action: IssueAction
) -> IssueRefusal:
    with pytest.raises(IssueRejectedError) as refusal:
        await press(session, factory, issue, action)
    await session.refresh(issue)
    assert issue.status is IssueStatus.OPEN
    return refusal.value.reason


async def nothing_left(session: AsyncSession, factory: FakeClientFactory) -> None:
    """按完之後再對帳一輪：什麼都沒有（修好了，而不是被記成 resolved 而已）。"""
    await reconcile_once(session, factory, now=LATER)
    assert [row.type for row in await issues_of(session) if row.status is IssueStatus.OPEN] == []


async def offered(session: AsyncSession, kind: IssueType) -> tuple[IssueAction, ...]:
    (view,) = [row for row in await list_issues(session) if row.type is kind]
    return view.actions


# --- source_missing ----------------------------------------------------


async def sourceless(
    session: AsyncSession, roots: dict[str, Path]
) -> tuple[Issue, LedgerEntry, FakeClientFactory]:
    _, _, factory = await imported(session, roots)
    entry = (await ledger_of(session))[0]
    Path(entry.source_abs_path).unlink()
    await reconcile_once(session, factory, now=NOW)
    return await the_one(session, IssueType.SOURCE_MISSING), entry, factory


class TestMarkSourceless:
    """標記為「已無來源」，library 檔保留（brief §9.1）。"""

    async def test_it_is_the_one_button_offered(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await sourceless(session, roots)

        assert await offered(session, IssueType.SOURCE_MISSING) == (IssueAction.MARK_SOURCELESS,)

    async def test_the_library_file_stays_and_the_ledger_says_sourceless(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        issue, entry, factory = await sourceless(session, roots)

        await press(session, factory, issue, IssueAction.MARK_SOURCELESS)

        await session.refresh(entry)
        assert entry.status is LedgerStatus.SOURCE_MISSING
        assert Path(entry.target_path).exists()
        await session.refresh(issue)
        assert issue.status is IssueStatus.RESOLVED
        await nothing_left(session, factory)


# --- inode_mismatch ----------------------------------------------------


async def copied(
    session: AsyncSession, roots: dict[str, Path], *, content: bytes | None = None
) -> tuple[Issue, LedgerEntry, FakeClientFactory]:
    """媒體庫裡那一份被換成複製品（`content` 給了就是被改寫成別的東西）。"""
    _, _, factory = await imported(session, roots)
    entry = (await features(session))[0]
    target = Path(entry.target_path)
    data = target.read_bytes() if content is None else content
    target.unlink()
    target.write_bytes(data)
    await reconcile_once(session, factory, now=NOW)
    return await the_one(session, IssueType.INODE_MISMATCH), entry, factory


class TestReplaceWithLink:
    """若大小一致提供「以硬鏈接取代」；否則列出等人決定（brief §9.1）。"""

    async def test_the_copy_becomes_a_hard_link_of_the_source(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        issue, entry, factory = await copied(session, roots)

        await press(session, factory, issue, IssueAction.REPLACE_WITH_LINK)

        assert same_file(Path(entry.source_abs_path), Path(entry.target_path))
        await session.refresh(entry)
        assert entry.status is LedgerStatus.OK
        assert entry.target_inode == str(Path(entry.target_path).stat().st_ino)
        await nothing_left(session, factory)

    async def test_a_different_size_is_listed_without_the_button(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        issue, _, factory = await copied(session, roots, content=b"transcoded")

        assert await offered(session, IssueType.INODE_MISMATCH) == ()
        assert await refused(session, factory, issue, IssueAction.REPLACE_WITH_LINK) is (
            IssueRefusal.ACTION_NOT_AVAILABLE
        )

    async def test_a_size_that_changed_since_the_run_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """偵測的時候一樣大、按下去之前被轉碼覆蓋了：那一份不能換掉。"""
        issue, entry, factory = await copied(session, roots)
        Path(entry.target_path).write_bytes(b"re-encoded since")

        assert await refused(session, factory, issue, IssueAction.REPLACE_WITH_LINK) is (
            IssueRefusal.SIZE_DIFFERS
        )
        assert Path(entry.target_path).read_bytes() == b"re-encoded since"


# --- orphan_complete ---------------------------------------------------


async def orphaned(
    session: AsyncSession, roots: dict[str, Path]
) -> tuple[Issue, Path, Route, FakeClientFactory]:
    _, route, factory = await imported(session, roots)
    folder = stray_folder(roots, route)
    await reconcile_once(session, factory, now=NOW)
    return await the_one(session, IssueType.ORPHAN_COMPLETE), folder, route, factory


class TestDeleteOrphan:
    async def test_the_whole_folder_goes(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        issue, folder, _, factory = await orphaned(session, roots)

        await press(session, factory, issue, IssueAction.DELETE_ORPHAN)

        assert not folder.exists()
        await nothing_left(session, factory)

    async def test_the_route_folder_and_the_other_downloads_stay(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        issue, folder, _, factory = await orphaned(session, roots)

        await press(session, factory, issue, IssueAction.DELETE_ORPHAN)

        assert folder.parent.is_dir()
        assert all(Path(entry.source_abs_path).exists() for entry in await ledger_of(session))

    async def test_a_folder_a_torrent_took_since_the_run_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """偵測與按下去之間，有人在 qBittorrent 上把它加回來做種了。"""
        issue, folder, route, factory = await orphaned(session, roots)
        factory.qbittorrent_.torrents = (torrent(route, roots, folder.name),)

        assert await refused(session, factory, issue, IssueAction.DELETE_ORPHAN) is (
            IssueRefusal.IN_USE
        )
        assert folder.exists()

    async def test_a_client_that_is_down_stops_it(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """問不到 qBittorrent 就不知道它現在有沒有主——不刪。"""
        issue, folder, _, factory = await orphaned(session, roots)
        factory.qbittorrent_.sync_error = ServiceUnavailableError("connection refused")

        assert await refused(session, factory, issue, IssueAction.DELETE_ORPHAN) is (
            IssueRefusal.CLIENT_UNREACHABLE
        )
        assert folder.exists()


# --- job_without_files -------------------------------------------------


async def emptied(
    session: AsyncSession, roots: dict[str, Path]
) -> tuple[Issue, Job, FakeClientFactory]:
    """帳本被清空了，而媒體庫也空了（例如資料庫從舊備份還原之後，使用者整理過媒體庫）。"""
    job, _, factory = await imported(session, roots)
    for entry in await ledger_of(session):
        Path(entry.target_path).unlink()
    await session.execute(delete(LedgerEntry))
    await session.commit()
    await reconcile_once(session, factory, now=NOW)
    return await the_one(session, IssueType.JOB_WITHOUT_FILES), job, factory


class TestReplan:
    """重新 planning（brief §9.1）：Job 退回 `completed`，規劃器與 importer 照常走完。"""

    async def test_the_job_goes_back_to_be_planned_and_the_planner_is_woken(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        issue, job, factory = await emptied(session, roots)
        plans = JobHints()

        await press(session, factory, issue, IssueAction.REPLAN, plans=plans)

        await session.refresh(job)
        assert job.state is JobState.COMPLETED
        assert await plans.wait(0.1)

    async def test_the_files_come_back_into_the_ledger_and_the_library(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        issue, job, factory = await emptied(session, roots)

        await press(session, factory, issue, IssueAction.REPLAN)
        await sweep_plans(session, factory, EventHub(), now=LATER)
        await sweep_imports(session, factory, EventHub(), now=LATER)

        entries = await ledger_of(session)
        assert len(entries) == LINKS
        assert all(same_file(Path(row.source_abs_path), Path(row.target_path)) for row in entries)
        await session.refresh(job)
        assert job.state is JobState.IMPORTED
        await nothing_left(session, factory)

    async def test_a_job_that_moved_on_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        issue, job, factory = await emptied(session, roots)
        job.state = JobState.REVIEW
        await session.commit()

        assert await refused(session, factory, issue, IssueAction.REPLAN) is (
            IssueRefusal.ACTION_NOT_AVAILABLE
        )

    async def test_a_ledger_the_user_forgot_does_not_come_back(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """每一個檔案都按過「承認刪除並清帳本」：帳本是使用者自己清的，不再問他要不要重新規劃。"""
        _, _, factory = await imported(session, roots)
        for entry in await ledger_of(session):
            Path(entry.target_path).unlink()
        await reconcile_once(session, factory, now=NOW)
        for issue in await open_of(session, IssueType.LIBRARY_LINK_MISSING):
            await press(session, factory, issue, IssueAction.FORGET)

        await reconcile_once(session, factory, now=LATER)

        assert await open_of(session, IssueType.JOB_WITHOUT_FILES) == []


# --- jellyfin_item_unresolved -----------------------------------------


async def unresolved(
    session: AsyncSession, roots: dict[str, Path]
) -> tuple[Issue, LedgerEntry, Route, FakeClientFactory]:
    """六次反查都用完了（resolver 自己寫下的那一件，同 `resolver._announce`）。"""
    _, route, factory = await imported(session, roots)
    entry = (await features(session))[0]
    entry.resolve_attempts = 6
    entry.resolve_after = None
    recorded = await record_issue(
        session,
        IssueType.JELLYFIN_ITEM_UNRESOLVED,
        path=entry.target_path,
        job_hash=entry.job_hash,
        ledger_id=entry.id,
        detail={"attempts": 6},
    )
    await session.commit()
    return recorded.issue, entry, route, factory


class TestRelook:
    """重新反查：那一列重新排進 `jellyfin_resolver`，六次從頭算。"""

    async def test_both_buttons_are_offered(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await unresolved(session, roots)

        assert await offered(session, IssueType.JELLYFIN_ITEM_UNRESOLVED) == (
            IssueAction.RELOOK,
            IssueAction.RESCAN,
        )

    async def test_the_next_sweep_finds_it(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        issue, entry, route, factory = await unresolved(session, roots)

        await press(session, factory, issue, IssueAction.RELOOK)
        await session.refresh(entry)
        assert entry.resolve_attempts == 0
        assert entry.resolve_after is not None
        factory.jellyfin_.items_ = scanned(route, await features(session), tmdb_id=SPY)

        await sweep_resolutions(session, factory, now=utcnow() + timedelta(seconds=1))

        await session.refresh(entry)
        assert entry.jellyfin_item_id == f"episode-{entry.episode_start}"


class TestRescan:
    async def test_jellyfin_is_asked_to_scan_and_the_row_is_looked_up_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        issue, entry, route, factory = await unresolved(session, roots)
        factory.jellyfin_.tasks_ = [LIBRARY_SCAN_TASK]

        await press(session, factory, issue, IssueAction.RESCAN)

        assert factory.jellyfin_.tasks_run == [LIBRARY_SCAN_TASK.id]
        factory.jellyfin_.items_ = scanned(route, await features(session), tmdb_id=SPY)
        await sweep_resolutions(session, factory, now=utcnow() + timedelta(hours=1))
        await session.refresh(entry)
        assert entry.jellyfin_item_id == f"episode-{entry.episode_start}"

    async def test_a_jellyfin_that_is_down_leaves_it_open(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        issue, entry, _, factory = await unresolved(session, roots)
        factory.jellyfin_.error = ServiceUnavailableError("connection refused")

        assert await refused(session, factory, issue, IssueAction.RESCAN) is (
            IssueRefusal.JELLYFIN_UNREACHABLE
        )
        await session.refresh(entry)
        assert entry.resolve_after is None


# --- unmanaged_library_file：永不刪 -----------------------------------


class TestUnmanagedIsNeverDeleted:
    """**只列出，永不自動刪**（brief §9.1）。票 10 的「認領進帳本」配不上時也是拒絕、不動檔案。"""

    async def test_no_button_it_offers_deletes_anything(self) -> None:
        offered = ISSUE_ACTIONS[IssueType.UNMANAGED_LIBRARY_FILE]

        assert not any(ACTION_DELETES[action] for action in offered)

    async def test_every_button_is_refused_and_the_file_stays(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """不只是畫面上不畫：直接打 API 按任何一顆都被擋，檔案一個位元組都沒動。"""
        _, route, factory = await imported(session, roots)
        stranger = Path(route.target_path) / "stray.mkv"
        stranger.write_bytes(b"put here by hand")
        await reconcile_once(session, factory, now=NOW)
        issue = await the_one(session, IssueType.UNMANAGED_LIBRARY_FILE)

        for action in IssueAction:
            with pytest.raises(IssueRejectedError):
                await press(session, factory, issue, action)

        assert stranger.read_bytes() == b"put here by hand"
        assert (await session.scalar(select(Issue.status).where(Issue.id == issue.id))) is (
            IssueStatus.OPEN
        )
