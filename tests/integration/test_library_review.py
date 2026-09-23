"""一個媒體庫的「待審 / 對不到」（M2 票 14，`.scratch/m2/review-shape.md`「媒體庫的子集」）。

媒體庫頁的那兩個篩選是 Review Queue 的子集：`plan` 與 `unmatched` 兩類、Job 的 Route 指向那個
Jellyfin 媒體庫的。**列與 `/review` 是同一份**（同一支查詢、同一個形狀），所以起點照
`test_review.py` 走產品自己的規劃器，不手寫 Plan：手寫的那一份說不出佇列那一端會不會把它當成
一件事。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import IssueType, ReviewKind
from berth.models import Route
from berth.services.issues import record_issue
from berth.services.review import PlanRow, UnmatchedRow, library_counts, library_queue, review_queue
from tests.integration.test_plan_review import held
from tests.integration.test_rematch import OVA, imported
from tests.integration.test_review import audited

pytestmark = pytest.mark.asyncio

#: `test_plan._route` 那一條 anime Route 指向的 Jellyfin 媒體庫。
ANIME = "item-2"


async def point(session: AsyncSession, route: Route, library_id: str) -> None:
    route.jellyfin_library_id = library_id
    await session.commit()


class TestOneLibrary:
    async def test_a_held_plan_on_a_route_into_it_is_on_its_list(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, _, plan_id = await held(session, roots)

        queue = await library_queue(session, ANIME)

        (row,) = queue.rows
        assert isinstance(row, PlanRow)
        assert (row.plan_id, row.job_hash) == (plan_id, job.hash)
        assert queue.total == 1
        # 列就是佇列上那一列：同一份形狀、同一個判定。
        assert row == (await review_queue(session)).rows[0]

    async def test_an_unmatched_file_is_on_it_and_the_rest_of_the_queue_is_not(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """整份佇列上還有別類（這裡是一件 Issue）；媒體庫只收要你決定的那兩類。"""
        await imported(session, roots)
        await record_issue(session, IssueType.LIBRARY_LINK_MISSING, path="/lib/a.mkv")
        await session.commit()

        queue = await library_queue(session, ANIME)

        (row,) = queue.rows
        assert isinstance(row, UnmatchedRow)
        assert row.rel_path == OVA
        assert queue.total == 1
        assert (await review_queue(session)).total == 2

    async def test_a_route_into_another_library_keeps_its_work_off_this_one(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, route, _, _ = await held(session, roots)
        await point(session, route, "item-9")

        assert (await library_queue(session, ANIME)).rows == []
        assert (await library_queue(session, "item-9")).total == 1

    async def test_an_audit_is_not_a_decision(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await audited(session, roots)

        assert (await library_queue(session, ANIME)).total == 0

    async def test_the_counts_are_the_lists(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """篩選鍵上的數字與清單同一個定義（使用者 2026-09-24 拍板）：數的是件，不是作品。"""
        await imported(session, roots)

        counts = await library_counts(session, ANIME)

        assert counts == {ReviewKind.PLAN: 0, ReviewKind.UNMATCHED: 1}
        assert await library_counts(session, "item-9") == {
            ReviewKind.PLAN: 0,
            ReviewKind.UNMATCHED: 0,
        }

    async def test_past_the_limit_it_still_counts_everything(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await held(session, roots)

        queue = await library_queue(session, ANIME, limit=0)

        assert (queue.rows, queue.total) == ([], 1)
