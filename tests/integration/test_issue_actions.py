"""按下 Issue 上的那三顆（brief §9.1 的「預設建議動作」那一欄、M2 票 05）。

起點一律是**真的走完一輪**：入庫 → 在媒體庫裡刪掉一個檔案 → 對帳 → 拿到那一件 Issue。
票上第一條驗收要的就是這整條，所以這裡不自己 `session.add(Issue(...))` 造一筆——造出來的
那一筆不會告訴你 `ledger_id` 有沒有被對帳寫對，而三顆按鈕全都靠它找回帳本那一列。

斷言貼著磁碟（同 `test_deletion.py`）：檔案回來了沒、inode 是不是同一個、complete 裡還剩
什麼。「Issue 變成 resolved」本身不算修好——畫面說修好了而媒體庫沒變，是這一票最糟的結果。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.domain import IssueAction, IssueRefusal, IssueStatus, IssueType, LedgerStatus
from berth.models import Issue, Job, LedgerEntry
from berth.services.issues import (
    IssueRejectedError,
    ignore_issue,
    list_issues,
    resolve_issue,
)
from berth.services.reconcile import reconcile_once
from tests.integration.factories import FakeClientFactory
from tests.integration.test_deletion import LINKS, SOURCES, alive, imported, sources, targets
from tests.integration.test_importer import ledger_of, same_file
from tests.integration.test_plan import HASH, NOW
from tests.integration.test_reconcile import break_one_link, issues_of

pytestmark = pytest.mark.asyncio

ACTOR = "7"


async def broken(
    session: AsyncSession, roots: dict[str, Path]
) -> tuple[Issue, str, FakeClientFactory]:
    """一筆入庫完的 Job，媒體庫裡少了它的第一個檔案，對帳已經把它記成一件 Issue。"""
    _, _, factory = await imported(session, roots)
    target = await break_one_link(session)
    await reconcile_once(session, factory, now=NOW)
    (issue,) = await issues_of(session)
    assert issue.type is IssueType.LIBRARY_LINK_MISSING
    return issue, target, factory


async def entry_at(session: AsyncSession, target: str) -> LedgerEntry | None:
    row: LedgerEntry | None = await session.scalar(
        select(LedgerEntry).where(LedgerEntry.target_path == target)
    )
    return row


class TestRelink:
    """acceptance：按「重新鏈接」之後檔案回來、Issue 是 `resolved`、帳本那一欄回 `ok`。"""

    async def test_the_file_comes_back_as_a_hard_link_to_the_source(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        issue, target, factory = await broken(session, roots)
        entry = await entry_at(session, target)
        assert entry is not None
        source = Path(entry.source_abs_path)

        await resolve_issue(session, factory, issue.id, IssueAction.RELINK, actor=ACTOR)

        assert Path(target).exists()
        # **同一個 inode 才叫硬鏈接**（brief §4.4）：複製一份過去在畫面上長得一樣，
        # 但空間估算與刪除範圍從此都是錯的。
        assert same_file(Path(target), source)

    async def test_the_issue_is_resolved_and_says_which_button(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        issue, _, factory = await broken(session, roots)

        view = await resolve_issue(session, factory, issue.id, IssueAction.RELINK, actor=ACTOR)

        assert view.status is IssueStatus.RESOLVED
        assert view.resolved_by == ACTOR
        assert view.detail["action"] == IssueAction.RELINK.value
        assert await list_issues(session) == []

    async def test_the_ledger_row_goes_back_to_ok(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        issue, target, factory = await broken(session, roots)

        await resolve_issue(session, factory, issue.id, IssueAction.RELINK, actor=ACTOR)

        entry = await entry_at(session, target)
        assert entry is not None
        assert entry.status is LedgerStatus.OK

    async def test_the_new_inode_is_written_down(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`target_inode` 記的是「當時鏈接出來的那一個」。照抄舊值的話，票 09 的
        `inode_mismatch` 會拿一個已經不存在的 inode 去比——每一輪都報一次假的不一致。"""
        issue, target, factory = await broken(session, roots)

        await resolve_issue(session, factory, issue.id, IssueAction.RELINK, actor=ACTOR)

        entry = await entry_at(session, target)
        assert entry is not None
        assert entry.target_inode == str(Path(target).stat().st_ino)

    async def test_the_next_run_finds_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """修好了就是修好了：下一輪對帳不該再把同一件事端出來。"""
        issue, _, factory = await broken(session, roots)
        await resolve_issue(session, factory, issue.id, IssueAction.RELINK, actor=ACTOR)

        await reconcile_once(session, factory, now=NOW)

        assert await list_issues(session) == []

    async def test_it_is_refused_when_the_source_is_gone_too(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """兩邊都沒有就不是鏈接的事，而且**那一件要留著 open**：畫面說修好了而檔案還是
        不在，比一則錯誤訊息糟得多。"""
        issue, target, factory = await broken(session, roots)
        entry = await entry_at(session, target)
        assert entry is not None
        Path(entry.source_abs_path).unlink()

        with pytest.raises(IssueRejectedError) as refusal:
            await resolve_issue(session, factory, issue.id, IssueAction.RELINK, actor=ACTOR)

        assert refusal.value.reason is IssueRefusal.SOURCE_MISSING
        assert [row.id for row in await list_issues(session)] == [issue.id]


class TestForget:
    """承認刪除並清帳本：那一列本來就不該再宣稱媒體庫裡有這個檔案。"""

    async def test_the_ledger_row_goes_away(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        issue, target, factory = await broken(session, roots)

        await resolve_issue(session, factory, issue.id, IssueAction.FORGET, actor=ACTOR)

        assert await entry_at(session, target) is None
        assert len(await ledger_of(session)) == LINKS - 1

    async def test_the_source_and_the_other_links_are_left_alone(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """這一顆說的只是「媒體庫裡沒有它，這樣就對了」——來源還在的話它仍然重新入庫得回來
        （brief §9.3）。"""
        issue, _, factory = await broken(session, roots)

        await resolve_issue(session, factory, issue.id, IssueAction.FORGET, actor=ACTOR)

        assert len(alive(await sources(session))) == SOURCES
        assert len(alive(await targets(session))) == LINKS - 1

    async def test_the_next_run_finds_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """**沒有帳本那一列就沒有那個宣稱**，所以下一輪不會再問一次同一件事。"""
        issue, _, factory = await broken(session, roots)
        await resolve_issue(session, factory, issue.id, IssueAction.FORGET, actor=ACTOR)

        await reconcile_once(session, factory, now=NOW)

        assert await list_issues(session) == []


class TestDeleteComplete:
    """連 complete 一起刪：**這一筆下載整個不要了**，走 `delete_job` 的四個旗標（票 04）。"""

    async def test_the_sources_and_the_remaining_links_go(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        issue, _, factory = await broken(session, roots)
        before = await sources(session)
        remaining = await targets(session)

        await resolve_issue(session, factory, issue.id, IssueAction.DELETE_COMPLETE, actor=ACTOR)

        assert alive(before) == []
        # 其餘還在媒體庫裡的那幾個也跟著走：留著就是沒有來源的孤兒（票 09 的
        # `unmanaged_library_file`），而使用者按的是「整個不要了」。
        assert alive(remaining) == []

    async def test_the_torrent_is_removed_from_the_client(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """**排第一的那一步**（brief §9.2）：檔案被抽走而 torrent 還在做種時，
        qBittorrent 下一次重新檢查就把整包再抓一遍。"""
        issue, _, factory = await broken(session, roots)

        await resolve_issue(session, factory, issue.id, IssueAction.DELETE_COMPLETE, actor=ACTOR)

        assert factory.qbittorrent_.deleted == [(HASH, False)]

    async def test_the_job_and_its_ledger_are_purged(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        issue, _, factory = await broken(session, roots)

        await resolve_issue(session, factory, issue.id, IssueAction.DELETE_COMPLETE, actor=ACTOR)

        assert await session.get(Job, HASH) is None
        assert await ledger_of(session) == []

    async def test_the_next_run_finds_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """**這一條是這顆按鈕勾滿四個旗標的理由**。

        不 `purge` 的話帳本那幾列留著說「媒體庫裡該有這些檔案」，而它們剛剛被 `unlink` 掉
        ——下一輪對帳會照著它們再開一批 `library_link_missing`，使用者剛決定過的那一件
        會自己回來，而且還多帶四個兄弟。
        """
        issue, _, factory = await broken(session, roots)
        await resolve_issue(session, factory, issue.id, IssueAction.DELETE_COMPLETE, actor=ACTOR)

        await reconcile_once(session, factory, now=NOW)

        assert await list_issues(session) == []

    async def test_a_client_that_is_down_stops_it_before_anything_is_touched(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """移除 torrent 是唯一可能失敗的一步，所以它排第一（brief §9.2）：問不到那一台時
        整次刪除不做，而不是刪到一半才發現。"""
        issue, _, factory = await broken(session, roots)
        factory.qbittorrent_.error = ServiceUnavailableError("qbittorrent is not answering")

        with pytest.raises(IssueRejectedError) as refusal:
            await resolve_issue(
                session, factory, issue.id, IssueAction.DELETE_COMPLETE, actor=ACTOR
            )

        assert refusal.value.reason is IssueRefusal.CLIENT_UNREACHABLE
        assert len(alive(await sources(session))) == SOURCES
        assert [row.id for row in await list_issues(session)] == [issue.id]


class TestWhatCanBePressed:
    async def test_a_resolved_issue_cannot_be_pressed_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """多半是另一個分頁先按了。"""
        issue, _, factory = await broken(session, roots)
        await resolve_issue(session, factory, issue.id, IssueAction.FORGET, actor=ACTOR)

        with pytest.raises(IssueRejectedError) as refusal:
            await resolve_issue(session, factory, issue.id, IssueAction.RELINK, actor=ACTOR)

        assert refusal.value.reason is IssueRefusal.ISSUE_NOT_OPEN

    async def test_an_issue_that_is_not_there_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await imported(session, roots)

        with pytest.raises(IssueRejectedError) as refusal:
            await resolve_issue(session, factory, 404, IssueAction.RELINK, actor=ACTOR)

        assert refusal.value.reason is IssueRefusal.ISSUE_MISSING

    async def test_the_list_offers_exactly_the_three(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """**動作由後端算**，前端不重算一份：按下去會被拒絕的按鈕不該畫出來。"""
        await broken(session, roots)

        (view,) = await list_issues(session)

        assert view.actions == (
            IssueAction.RELINK,
            IssueAction.FORGET,
            IssueAction.DELETE_COMPLETE,
        )

    async def test_deleting_the_download_is_not_offered_without_one(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """帳本的 `job_hash` 是弱引用（`models/ledger.py`）：重新入庫建出來的那幾列沒有 Job，
        而「連 complete 一起刪」刪的就是那一筆 Job。"""
        issue, target, factory = await broken(session, roots)
        entry = await entry_at(session, target)
        assert entry is not None
        entry.job_hash = None
        issue.job_hash = None
        await session.commit()

        (view,) = await list_issues(session)

        assert view.actions == (IssueAction.RELINK, IssueAction.FORGET)
        with pytest.raises(IssueRejectedError) as refusal:
            await resolve_issue(
                session, factory, issue.id, IssueAction.DELETE_COMPLETE, actor=ACTOR
            )
        assert refusal.value.reason is IssueRefusal.ACTION_NOT_AVAILABLE


class TestIgnore:
    async def test_it_leaves_the_disk_and_the_ledger_alone(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        issue, target, _ = await broken(session, roots)

        await ignore_issue(session, issue.id, actor=ACTOR)

        entry = await entry_at(session, target)
        assert entry is not None
        assert entry.status is LedgerStatus.TARGET_MISSING
        assert await list_issues(session) == []

    async def test_the_next_run_asks_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """忽略的是「這一次不想處理」，不是「這件事不存在」——那個檔案仍然不在。

        真的要它安靜下來，按的是「承認刪除並清帳本」。
        """
        issue, _, factory = await broken(session, roots)
        await ignore_issue(session, issue.id, actor=ACTOR)

        await reconcile_once(session, factory, now=NOW)

        listed = await list_issues(session)
        assert [row.type for row in listed] == [IssueType.LIBRARY_LINK_MISSING]
        assert listed[0].id != issue.id
