"""每日巡檢的「一直失敗的 Feed」（M4 票 130，plan §11.5〈巡檢〉）。

輪詢與每日補漏各記自己的錯誤與「從什麼時候開始一直失敗」（`rss_feeds.poll_*` / `backfill_*`，
同票拆欄）。巡檢看到其中一種失敗超過 `FAILING_AFTER`，開一件說出是哪一種、最後的原因；恢復（那一欄
清空）或 Feed 被刪了，下一輪由系統收掉。

斷言只看公開的接縫：巡檢一輪（`sweep_once`）之後 Issue 清單（`list_issues`）上有什麼。起點直接寫
Feed 那一列：輪詢與補漏怎麼寫這幾欄由 `test_rss.py`、`test_rss_backfill.py` 守著。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import FeedKind, IssueStatus, IssueType
from berth.models import Issue, RssFeed
from berth.services.issues import IssueView, ignore_issue, list_issues
from berth.services.sweep import FAILING_AFTER, sweep_once

pytestmark = pytest.mark.asyncio

#: 由好轉壞的那一輪。
BROKE = datetime(2026, 10, 20, 3, 0, tzinfo=UTC)
LATER = BROKE + FAILING_AFTER + timedelta(minutes=1)
POLL_ERROR = "GET https://mikanani.me/RSS/MyBangumi?token=***: connection refused"
BACKFILL_ERROR = "backfill mikan:3600:583: GET https://mikanani.me/RSS/Bangumi: 404"
FAILING = (IssueType.FEED_POLL_FAILING, IssueType.FEED_BACKFILL_FAILING)


async def feed(
    session: AsyncSession,
    *,
    poll: str = "",
    backfill: str = "",
    since: datetime = BROKE,
) -> RssFeed:
    row = RssFeed(
        name="Mikan",
        url="https://mikanani.me/RSS/MyBangumi?token=t",
        kind=FeedKind.MIKAN,
        poll_error=poll,
        poll_failing_since=since if poll else None,
        backfill_error=backfill,
        backfill_failing_since=since if backfill else None,
    )
    session.add(row)
    await session.commit()
    return row


async def failing(session: AsyncSession) -> list[IssueView]:
    return [view for view in await list_issues(session) if view.type in FAILING]


class TestFailingFeed:
    async def test_polling_failing_past_the_threshold_opens_one_issue_that_says_so(
        self, session: AsyncSession
    ) -> None:
        row = await feed(session, poll=POLL_ERROR)

        await sweep_once(session, now=LATER)

        (issue,) = await failing(session)
        assert issue.type is IssueType.FEED_POLL_FAILING
        assert issue.subject == str(row.id)
        assert issue.detail["feed"] == row.id
        assert issue.detail["name"] == "Mikan"
        assert issue.detail["error"] == POLL_ERROR
        assert issue.detail["since"] == BROKE.isoformat()
        assert issue.actions == ()

    async def test_backfill_failing_is_its_own_kind(self, session: AsyncSession) -> None:
        row = await feed(session, backfill=BACKFILL_ERROR)

        await sweep_once(session, now=LATER)

        (issue,) = await failing(session)
        assert issue.type is IssueType.FEED_BACKFILL_FAILING
        assert issue.subject == str(row.id)
        assert issue.detail["error"] == BACKFILL_ERROR

    async def test_both_failing_are_two_issues(self, session: AsyncSession) -> None:
        await feed(session, poll=POLL_ERROR, backfill=BACKFILL_ERROR)

        await sweep_once(session, now=LATER)

        assert {issue.type for issue in await failing(session)} == set(FAILING)

    async def test_not_yet_past_the_threshold_opens_nothing(self, session: AsyncSession) -> None:
        await feed(session, poll=POLL_ERROR, backfill=BACKFILL_ERROR)

        await sweep_once(session, now=BROKE + FAILING_AFTER - timedelta(minutes=1))

        assert await failing(session) == []

    async def test_the_latest_reason_replaces_the_old_one(self, session: AsyncSession) -> None:
        row = await feed(session, poll=POLL_ERROR)
        await sweep_once(session, now=LATER)
        row.poll_error = "GET https://mikanani.me/RSS/MyBangumi?token=***: 503"
        await session.commit()

        await sweep_once(session, now=LATER + timedelta(days=1))

        (issue,) = await failing(session)
        assert issue.detail["error"] == row.poll_error

    async def test_a_feed_that_recovers_is_closed_by_the_system(
        self, session: AsyncSession
    ) -> None:
        row = await feed(session, poll=POLL_ERROR, backfill=BACKFILL_ERROR)
        await sweep_once(session, now=LATER)
        row.poll_error, row.poll_failing_since = "", None
        await session.commit()

        await sweep_once(session, now=LATER + timedelta(days=1))

        (left,) = await failing(session)
        assert left.type is IssueType.FEED_BACKFILL_FAILING
        closed = await session.get(Issue, (await _ids(session))[IssueType.FEED_POLL_FAILING])
        assert closed is not None and closed.status is IssueStatus.RESOLVED

    async def test_a_deleted_feed_is_closed_by_the_system(self, session: AsyncSession) -> None:
        row = await feed(session, poll=POLL_ERROR)
        await sweep_once(session, now=LATER)
        await session.delete(row)
        await session.commit()

        await sweep_once(session, now=LATER + timedelta(days=1))

        assert await failing(session) == []

    async def test_ignoring_holds_while_it_keeps_failing(self, session: AsyncSession) -> None:
        """每天量一次的那幾種：忽略在條件持續期間有效（`STAYS_IGNORED`，同
        `first_batch_stuck`）。"""
        row = await feed(session, poll=POLL_ERROR)
        await sweep_once(session, now=LATER)
        (issue,) = await failing(session)
        await ignore_issue(session, issue.id, actor="1")

        await sweep_once(session, now=LATER + timedelta(days=1))
        assert await failing(session) == []

        # 恢復過一次之後再壞，是新的一件。
        row.poll_error, row.poll_failing_since = "", None
        await session.commit()
        await sweep_once(session, now=LATER + timedelta(days=2))
        row.poll_error, row.poll_failing_since = POLL_ERROR, LATER + timedelta(days=2)
        await session.commit()
        await sweep_once(session, now=LATER + timedelta(days=4))

        (again,) = await failing(session)
        assert again.id != issue.id


async def _ids(session: AsyncSession) -> dict[IssueType, int]:
    rows = await session.execute(select(Issue.type, Issue.id).where(Issue.type.in_(FAILING)))
    return dict(rows.tuples().all())
