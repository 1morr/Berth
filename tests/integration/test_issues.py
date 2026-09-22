"""`issues` 表的寫入與冪等鍵（plan §2.4、brief §9.1、M2 票 05）。

這一份只驗**載體**：偵測到一件事會留下什麼、同一件事再偵測到會發生什麼、決定過之後還算不算
同一件事。對帳怎麼發現它們在 `test_reconcile.py`，按下去怎麼修在 `test_issue_actions.py`。

分開的理由是冪等鍵有它自己的失效方式：`subject` 取錯欄位、唯一索引蓋到 `resolved`、
`detected_at` 沒更新——三種都不會讓對帳那一層看起來有問題，但清單上會多出重複的列，或者
同一條路徑第二次出問題時**永遠不再出現**。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import IssueStatus, IssueType
from berth.models import Issue
from berth.services.issues import ignore_issue, list_issues, record_issue

pytestmark = pytest.mark.asyncio

FIRST = datetime(2026, 9, 22, 4, 0, tzinfo=UTC)
LATER = FIRST + timedelta(days=1)

TARGET = "/data/library/tv/Show (2020)/Season 01/Show - S01E01.mkv"
OTHER = "/data/library/tv/Show (2020)/Season 01/Show - S01E02.mkv"


async def count(session: AsyncSession) -> int:
    total = await session.scalar(select(func.count()).select_from(Issue))
    return total or 0


async def only(session: AsyncSession) -> Issue:
    rows = list(await session.scalars(select(Issue)))
    assert len(rows) == 1, [(row.type, row.subject, row.status) for row in rows]
    return rows[0]


class TestWritingOneDown:
    async def test_a_detection_leaves_an_open_row(self, session: AsyncSession) -> None:
        await record_issue(
            session, IssueType.LIBRARY_LINK_MISSING, path=TARGET, ledger_id=7, now=FIRST
        )

        row = await only(session)
        assert row.type is IssueType.LIBRARY_LINK_MISSING
        assert row.status is IssueStatus.OPEN
        assert row.path == TARGET
        assert row.ledger_id == 7
        assert row.detected_at == FIRST

    async def test_the_subject_is_taken_per_type(self, session: AsyncSession) -> None:
        """`library_link_missing` 的冪等鍵是路徑，`client_error` 的是那一筆下載（plan §2.4）。

        兩種一起驗：只驗一種的話「`subject` 永遠抄 `path`」也會通過。
        """
        await record_issue(
            session, IssueType.LIBRARY_LINK_MISSING, path=TARGET, job_hash="abc", now=FIRST
        )
        await record_issue(session, IssueType.CLIENT_ERROR, path=TARGET, job_hash="abc", now=FIRST)

        subjects = {row.type: row.subject for row in await session.scalars(select(Issue))}
        assert subjects[IssueType.LIBRARY_LINK_MISSING] == TARGET
        assert subjects[IssueType.CLIENT_ERROR] == "abc"

    async def test_a_detection_without_the_column_its_subject_needs_is_refused(
        self, session: AsyncSession
    ) -> None:
        """型別說 subject 取 `job_hash` 而呼叫端沒給：**不寫**，而不是寫一筆沒有鍵的列。

        沒有這一條的話那幾筆會共用 `subject = ''`，於是「同一件事」的定義塌成「同一種型別」
        ——第二筆 `client_error` 會去更新第一筆，清單上永遠只有一筆。
        """
        with pytest.raises(ValueError):
            await record_issue(session, IssueType.CLIENT_ERROR, path=TARGET, now=FIRST)

        assert await count(session) == 0


class TestDetectingTheSameThingAgain:
    """acceptance：同一個破壞連跑兩輪只有一筆 `open`，第二輪更新 `detail_json` 與 `detected_at`。"""

    async def test_the_second_detection_updates_instead_of_inserting(
        self, session: AsyncSession
    ) -> None:
        await record_issue(
            session,
            IssueType.LIBRARY_LINK_MISSING,
            path=TARGET,
            detail={"season": 1, "run": 1},
            now=FIRST,
        )

        await record_issue(
            session,
            IssueType.LIBRARY_LINK_MISSING,
            path=TARGET,
            detail={"season": 1, "run": 2},
            now=LATER,
        )

        row = await only(session)
        assert row.detected_at == LATER
        assert row.detail_json == {"season": 1, "run": 2}

    async def test_a_different_path_is_a_different_thing(self, session: AsyncSession) -> None:
        await record_issue(session, IssueType.LIBRARY_LINK_MISSING, path=TARGET, now=FIRST)

        await record_issue(session, IssueType.LIBRARY_LINK_MISSING, path=OTHER, now=FIRST)

        assert await count(session) == 2

    async def test_the_same_path_under_another_type_is_a_different_thing(
        self, session: AsyncSession
    ) -> None:
        await record_issue(session, IssueType.LIBRARY_LINK_MISSING, path=TARGET, now=FIRST)

        await record_issue(session, IssueType.INODE_MISMATCH, path=TARGET, now=FIRST)

        assert await count(session) == 2


class TestAfterSomebodyHasDecided:
    async def test_the_same_thing_happening_again_opens_a_new_row(
        self, session: AsyncSession
    ) -> None:
        """決定過的那一筆是歷史。同一條路徑第二次出問題要再問一次人。

        唯一索引因此只蓋 `open`（`models/issue.py`）：蓋住全部的話這一筆會撞上去，而使用者
        再也不會知道那個檔案又不見了。
        """
        first = await record_issue(session, IssueType.LIBRARY_LINK_MISSING, path=TARGET, now=FIRST)
        await ignore_issue(session, first.issue.id, actor="7")
        await session.commit()

        await record_issue(session, IssueType.LIBRARY_LINK_MISSING, path=TARGET, now=LATER)

        rows = sorted(await session.scalars(select(Issue)), key=lambda row: row.id)
        assert [row.status for row in rows] == [IssueStatus.IGNORED, IssueStatus.OPEN]

    async def test_only_the_open_one_is_listed(self, session: AsyncSession) -> None:
        first = await record_issue(session, IssueType.LIBRARY_LINK_MISSING, path=TARGET, now=FIRST)
        await record_issue(session, IssueType.LIBRARY_LINK_MISSING, path=OTHER, now=FIRST)
        await ignore_issue(session, first.issue.id, actor="7")
        await session.commit()

        listed = await list_issues(session)

        assert [row.path for row in listed] == [OTHER]


class TestTheOrderOfTheList:
    async def test_the_newest_detection_is_first(self, session: AsyncSession) -> None:
        """清單上是「最近偵測到的在前」：對帳跑完之後使用者要看的是這一輪發現了什麼。"""
        await record_issue(session, IssueType.LIBRARY_LINK_MISSING, path=TARGET, now=FIRST)
        await record_issue(session, IssueType.LIBRARY_LINK_MISSING, path=OTHER, now=LATER)

        listed = await list_issues(session)

        assert [row.path for row in listed] == [OTHER, TARGET]
