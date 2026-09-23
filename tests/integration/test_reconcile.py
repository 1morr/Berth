"""對帳的一輪：比四方、跳過問不到的那一方、寫下 Issue（brief §9.1、§16.2、plan §3.2、票 05）。

這一份的重點不是「七種都找得到」（那在 `test_reconcile_checks.py`，票 09），而是**一輪的形狀**，
以 `library_link_missing` 演：

- 四方各自走完才寫 Issue，而任一方問不到就跳過那一方並**在結果上說出來**。
- 跳過的那一方不得讓任何東西被寫成「不見了」（brief §16.2）。這是整張票最容易靜靜壞掉的
  地方：Route 目錄沒掛上時，帳本上的每一條目標看起來都不在——一輪對帳會把整個媒體庫報成
  失蹤，而使用者會照著那份清單按下「承認刪除並清帳本」。
- 同一個破壞連跑兩輪只有一筆 `open`（冪等鍵在 `test_issues.py`，這裡驗它在真的一輪裡成立）。

檔案是真的寫在 `tmp_path` 底下的，破壞也是真的 `unlink`（`tests/integration/conftest.py`）。
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.db import create_session_factory
from berth.domain import IssueRefusal, IssueStatus, IssueType, LedgerStatus, ReconcileSide
from berth.models import Issue, LedgerEntry
from berth.services.issues import IssueRejectedError, ignore_issue, list_issues
from berth.services.reconcile import (
    ReconcileReport,
    ReconcileRunner,
    SideReport,
    reconcile_once,
)
from tests.integration.factories import FakeClientFactory
from tests.integration.test_deletion import imported
from tests.integration.test_importer import ledger_of
from tests.integration.test_plan import NOW

pytestmark = pytest.mark.asyncio

LATER = NOW + timedelta(days=1)


async def issues_of(session: AsyncSession) -> list[Issue]:
    return list(await session.scalars(select(Issue).order_by(Issue.id)))


def side(report: ReconcileReport, which: ReconcileSide) -> SideReport:
    found = [row for row in report.sides if row.side is which]
    assert len(found) == 1, [row.side for row in report.sides]
    return found[0]


async def break_one_link(session: AsyncSession) -> str:
    """在媒體庫裡刪掉一個入庫好的檔案——使用者在 Jellyfin 按刪除之後的樣子（brief §9.5）。

    回的是**帳本記的那一串字**而不是 `Path`：帳本的 `target_path` 是容器裡的 POSIX 路徑
    （`models/ledger.py`），而 Issue 記的要與它一模一樣——對得起來的才找得回那一列。
    """
    entries = await ledger_of(session)
    target = entries[0].target_path
    Path(target).unlink()
    return target


class TestTheLoopEndToEnd:
    """acceptance：刪掉一個 library 檔 → 對帳 → `GET /issues` 有一條 `library_link_missing`。"""

    async def test_a_deleted_library_file_becomes_an_issue(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await imported(session, roots)
        target = await break_one_link(session)

        await reconcile_once(session, FakeClientFactory(), now=NOW)

        listed = await list_issues(session)
        assert [(row.type, row.path) for row in listed] == [
            (IssueType.LIBRARY_LINK_MISSING, target)
        ]

    async def test_the_ledger_row_says_what_it_found(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`ledger.status.target_missing` 與 Issue 是同一件事的兩個角度（plan §2.4）：
        帳本那一欄是現況，Issue 是要有人決定的那一件。"""
        await imported(session, roots)
        target = await break_one_link(session)

        await reconcile_once(session, FakeClientFactory(), now=NOW)

        rows = {row.target_path: row.status for row in await ledger_of(session)}
        assert rows[target] is LedgerStatus.TARGET_MISSING
        assert set(rows.values()) == {LedgerStatus.TARGET_MISSING, LedgerStatus.OK}

    async def test_the_issue_points_back_at_the_ledger_row_and_the_job(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """三顆按鈕都要從這裡找回東西：重新鏈接要帳本那一列，連 complete 一起刪要那一筆 Job。"""
        job, _, _ = await imported(session, roots)
        await break_one_link(session)

        await reconcile_once(session, FakeClientFactory(), now=NOW)

        (issue,) = await issues_of(session)
        entry = await session.get(LedgerEntry, issue.ledger_id)
        assert entry is not None
        assert entry.target_path == issue.path
        assert issue.job_hash == job.hash

    async def test_an_intact_library_opens_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await imported(session, roots)

        report = await reconcile_once(session, FakeClientFactory(), now=NOW)

        assert await issues_of(session) == []
        assert report.opened == 0


class TestRunningItTwice:
    """acceptance：同一個破壞連跑兩輪只有一筆 `open`，第二輪更新 `detail_json` 與 `detected_at`。"""

    async def test_the_second_run_updates_the_same_row(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await imported(session, roots)
        await break_one_link(session)
        await reconcile_once(session, FakeClientFactory(), now=NOW)

        report = await reconcile_once(session, FakeClientFactory(), now=LATER)

        (issue,) = await issues_of(session)
        assert issue.status is IssueStatus.OPEN
        assert issue.detected_at == LATER
        assert (report.opened, report.updated) == (0, 1)


class TestWhenASideCannotBeAsked:
    """brief §16.2：**不把「問不到」誤判成「不見了」**。"""

    async def test_a_client_that_is_down_is_skipped_and_said(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """acceptance：qBittorrent 連不上時那一方跳過並說出來，沒有任何 Issue 被寫成「不見了」。"""
        _, _, factory = await imported(session, roots)
        factory.qbittorrent_.sync_error = ServiceUnavailableError("qbittorrent is not answering")

        report = await reconcile_once(session, factory, now=NOW)

        client = side(report, ReconcileSide.CLIENT)
        assert client.unavailable
        assert "qbittorrent" in client.unavailable.lower()
        assert await issues_of(session) == []

    async def test_the_library_side_still_runs_when_the_client_is_down(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """一方問不到不讓其餘三方停擺——那個被刪掉的檔案仍然要被發現。"""
        _, _, factory = await imported(session, roots)
        factory.qbittorrent_.sync_error = ServiceUnavailableError("qbittorrent is not answering")
        await break_one_link(session)

        report = await reconcile_once(session, factory, now=NOW)

        assert [row.type for row in await issues_of(session)] == [IssueType.LIBRARY_LINK_MISSING]
        assert not side(report, ReconcileSide.LIBRARY).unavailable

    async def test_a_route_folder_that_is_not_mounted_reports_nothing_missing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """**整張票最容易靜靜壞掉的地方**：Route 目錄不在時，帳本上每一條目標都 `stat` 不到。

        照著「檔案不在就是不見了」寫的話，一輪對帳會把整個媒體庫報成失蹤，而使用者會照著
        那份清單按下「承認刪除並清帳本」——帳本就真的沒了。所以問得到的單位是 **Route**：
        那一條的目錄不在，它底下的帳本一條都不比。
        """
        _, route, factory = await imported(session, roots)
        # 掛載掉了的樣子：整個媒體庫目錄不見（不是裡面的檔案被刪）。
        for path in sorted(Path(route.target_path).rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
        Path(route.target_path).rmdir()

        report = await reconcile_once(session, factory, now=NOW)

        assert await issues_of(session) == []
        library = side(report, ReconcileSide.LIBRARY)
        assert library.skipped
        assert route.name in library.skipped[0]

    async def test_a_ledger_row_is_not_touched_when_its_route_is_skipped(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """跳過的那幾條連 `ledger.status` 都不改：那一欄說的是「比對過的現況」。"""
        _, route, factory = await imported(session, roots)
        for path in sorted(Path(route.target_path).rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
        Path(route.target_path).rmdir()

        await reconcile_once(session, factory, now=NOW)

        assert {row.status for row in await ledger_of(session)} == {LedgerStatus.OK}


class TestWhatTheRunReports:
    """`GET /reconcile` 的「哪一方比到哪、幾筆」（plan §3.2）。"""

    async def test_every_side_is_accounted_for(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """四方都要出現在結果上，包含這一票還沒有檢查在用的那兩方。

        少報一方的話畫面說不出「它問到了嗎」——而「沒有 Issue」有兩種意思（都好好的，
        或根本沒比），使用者要分得出來。
        """
        _, _, factory = await imported(session, roots)

        report = await reconcile_once(session, factory, now=NOW)

        assert {row.side for row in report.sides} == set(ReconcileSide)

    async def test_the_library_side_counts_what_it_compared(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await imported(session, roots)

        report = await reconcile_once(session, factory, now=NOW)

        assert side(report, ReconcileSide.LIBRARY).counted == len(await ledger_of(session))

    async def test_it_finishes(self, session: AsyncSession, roots: dict[str, Path]) -> None:
        _, _, factory = await imported(session, roots)

        report = await reconcile_once(session, factory, now=NOW)

        assert report.started_at == NOW
        assert report.finished_at is not None


class TestADisabledRoute:
    async def test_its_files_are_still_compared(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """停用說的是「不要再往這裡入庫」，不是「裡面的東西不用管了」。

        那些檔案還在 Jellyfin 的媒體庫裡，使用者仍然看得到它們——所以帳本仍然要對得上。
        """
        _, route, factory = await imported(session, roots)
        route.enabled = False
        await session.commit()
        await break_one_link(session)

        await reconcile_once(session, factory, now=NOW)

        assert [row.type for row in await issues_of(session)] == [IssueType.LIBRARY_LINK_MISSING]


class TestOnlyOneRunAtATime:
    """`ReconcileRunner`：`POST /reconcile` 與每日 04:00 按的是同一顆按鈕（plan §3.2）。

    **不排隊**：排隊的那一輪看到的會是同一份磁碟，做的是同樣的比對，寫的是同樣的 Issue。

    這裡拿得到事件迴圈，所以不必跟背景 task 賽跑：`start()` 之後那個 task 還沒被排程
    （`create_task` 不會立刻跑），於是「正在跑的時候再按」是確定的，不是碰運氣。
    """

    async def test_pressing_it_again_while_one_is_going_is_refused(
        self, engine: AsyncEngine, roots: dict[str, Path]
    ) -> None:
        runner = ReconcileRunner(create_session_factory(engine), FakeClientFactory())
        await runner.start()

        with pytest.raises(IssueRejectedError) as refusal:
            await runner.start()

        assert refusal.value.reason is IssueRefusal.RECONCILE_RUNNING
        await runner.wait()

    async def test_the_run_in_flight_is_visible_before_it_finishes(
        self, engine: AsyncEngine, roots: dict[str, Path]
    ) -> None:
        """`GET /reconcile` 的 `current`：還沒有 `finished_at`，而 `last` 還是空的。"""
        runner = ReconcileRunner(create_session_factory(engine), FakeClientFactory())
        started = await runner.start()

        state = runner.status()

        assert state.current is not None
        assert state.current.id == started.id
        assert state.current.finished_at is None
        assert state.last is None
        await runner.wait()

    async def test_the_next_one_gets_in_once_the_first_has_finished(
        self, session: AsyncSession, engine: AsyncEngine, roots: dict[str, Path]
    ) -> None:
        """跑完之後 `last` 說得出這一輪比了什麼，而按鈕又按得下去了。"""
        await imported(session, roots)
        runner = ReconcileRunner(create_session_factory(engine), FakeClientFactory())
        await runner.start()
        await runner.wait()

        state = runner.status()

        assert state.current is None
        assert state.last is not None
        assert state.last.finished_at is not None
        assert {row.side for row in state.last.sides} == set(ReconcileSide)
        assert (await runner.start()).id == state.last.id + 1
        await runner.wait()


class TestWhatTheRunCounts:
    """`opened` / `updated` 說的是 `record_issue` **真的做了什麼**。

    從帳本的舊狀態去推會在「上一件被忽略過」那一格說謊：那一列帳本仍然是 `target_missing`，
    但開出來的是**新的一筆**（`ignore` 的意思是「這一次不想處理」，不是「這件事不存在」）。
    畫面上那一行摘要會說「開了 0 件」而清單多一列。
    """

    async def test_a_second_detection_of_the_same_thing_counts_as_updated(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await imported(session, roots)
        await break_one_link(session)
        await reconcile_once(session, factory, now=NOW)

        report = await reconcile_once(session, factory, now=LATER)

        assert (report.opened, report.updated) == (0, 1)

    async def test_reopening_after_an_ignore_counts_as_opened(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await imported(session, roots)
        await break_one_link(session)
        await reconcile_once(session, factory, now=NOW)
        (issue,) = await issues_of(session)
        await ignore_issue(session, issue.id, actor="7")

        report = await reconcile_once(session, factory, now=LATER)

        assert (report.opened, report.updated) == (1, 0)
        assert len(await issues_of(session)) == 2
