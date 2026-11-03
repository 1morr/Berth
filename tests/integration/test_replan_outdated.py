"""升級後自動重算（M5.5 票 06、plan §3.1 的 review → completed）。

規則改了之後，停在審核佇列的那幾筆要人按「重新規劃」才會用新規則。啟動時只挑**舊版本算的**
`review` 退回 `completed`，交給規劃器在背景算：每次啟動全部重算會蓋掉人改的列、重設等候時間，
而同版本的結果也一樣。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.tmdb import TmdbDetail
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.config import VERSION, Config
from berth.domain import (
    EventType,
    JobState,
    MediaKind,
    PlanEngine,
    PlanStatus,
    PlanSummary,
    ReviewReason,
)
from berth.main import create_app
from berth.models import Job, Media, Plan
from berth.services.media import PLANNING_TTL
from berth.services.plan import replan_outdated
from berth.services.setup import complete_setup
from tests.integration.arrange import factory_for
from tests.integration.test_media import SPY, credentialled, tmdb
from tests.integration.test_plan import (
    STRAY,
    STRAY_FILES,
    downloaded_job,
    events_of,
    plan_of,
    ready,
    run,
)

pytestmark = pytest.mark.asyncio

#: 上一版 Berth 算的那一份。
OLD = "0.0.1"


async def held_by_old_rules(session: AsyncSession, job: Job) -> None:
    """舊規則把它擋在審核：已算好的那一份改回舊版本、停在 review 的樣子。"""
    plan = await plan_of(session, job.hash)
    plan.engine_version = OLD
    plan.status = PlanStatus.PENDING_REVIEW
    job.state = JobState.REVIEW
    await session.commit()


def edited_by_hand(job: Job, plan: Plan) -> None:
    plan.engine = PlanEngine.USER


def undone_by_audit(job: Job, plan: Plan) -> None:
    summary = PlanSummary.model_validate(plan.summary_json or {})
    plan.summary_json = summary.model_copy(
        update={"review_reason": ReviewReason.AUDIT_UNDONE}
    ).model_dump(mode="json")


def already_imported(job: Job, plan: Plan) -> None:
    job.state = JobState.IMPORTED
    plan.status = PlanStatus.AUTO


class TestReplanOutdated:
    async def test_an_old_review_is_planned_again_with_the_new_rules(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await ready(session, roots)
        job = await downloaded_job(session, media, route, roots)
        await run(session, factory)
        await held_by_old_rules(session, job)

        assert await replan_outdated(session) == 1
        assert await state_of(session, job) is JobState.COMPLETED
        retried = [row for row in await events_of(session) if row.type == EventType.RETRIED]
        assert [(row.actor, row.payload_json) for row in retried] == [
            ("system", {"state": "completed", "engine_version": OLD})
        ]

        await run(session, factory)
        plan = await plan_of(session)
        await session.refresh(plan)
        assert await state_of(session, job) is JobState.IMPORTING
        assert plan.engine_version == VERSION

    @pytest.mark.parametrize(
        "leave", [edited_by_hand, undone_by_audit, already_imported], ids=lambda f: f.__name__
    )
    async def test_what_a_person_decided_or_what_is_in_the_library_is_left_alone(
        self,
        session: AsyncSession,
        roots: dict[str, Path],
        leave: Callable[[Job, Plan], None],
    ) -> None:
        media, route, factory = await ready(session, roots)
        job = await downloaded_job(session, media, route, roots)
        await run(session, factory)
        await held_by_old_rules(session, job)
        plan = await plan_of(session)
        leave(job, plan)
        await session.commit()
        before = (job.state, plan.created_at)

        assert await replan_outdated(session) == 0

        await session.refresh(job)
        await session.refresh(plan)
        assert (job.state, plan.created_at) == before
        assert plan.engine_version == OLD
        assert [row for row in await events_of(session) if row.type == EventType.RETRIED] == []

    async def test_a_restart_on_the_same_version_plans_nothing_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """快照放到過期：真的重算的話規劃會先問 TMDB，請求數就不是 0。"""
        media, route, _ = await ready(session, roots)
        job = await downloaded_job(session, media, route, roots)
        client = tmdb()
        factory = await credentialled(session, client)
        await run(session, factory)
        plan = await plan_of(session)
        plan.status = PlanStatus.PENDING_REVIEW
        job.state = JobState.REVIEW
        await stale(session, media)
        client.requests.clear()
        before = plan.created_at

        assert await replan_outdated(session) == 0
        await run(session, factory)

        await session.refresh(plan)
        assert client.requests == []
        assert await state_of(session, job) is JobState.REVIEW
        assert plan.created_at == before


class HeldTmdb(FakeTmdbClient):
    """讀作品詳情時停住，直到測試放行：重算還沒做完的那一段。"""

    def __init__(self) -> None:
        super().__init__(details=[SPY])
        self.asked = asyncio.Event()
        self.answer = asyncio.Event()

    async def detail(self, kind: MediaKind, tmdb_id: int, *, language: str) -> TmdbDetail:
        self.asked.set()
        await self.answer.wait()
        return await super().detail(kind, tmdb_id, language=language)


class TestStartup:
    async def test_startup_sends_old_reviews_to_the_planner_without_waiting_for_it(
        self, session: AsyncSession, roots: dict[str, Path], config: Config, tmp_path: Path
    ) -> None:
        media, route, _ = await ready(session, roots)
        job = await downloaded_job(session, media, route, roots, name=STRAY, files=STRAY_FILES)
        client = HeldTmdb()
        factory = await credentialled(session, client)
        await run(session, factory)
        await held_by_old_rules(session, job)
        await complete_setup(session)
        await stale(session, media)
        app = create_app(
            replace(config, web_root=tmp_path / "never-built"),
            clients=factory_for(roots, tmdb=client),
        )

        # 啟動等重算的話，它會卡在 TMDB 那一步、等不到這五秒。
        async with asyncio.timeout(5), app.router.lifespan_context(app):
            await client.asked.wait()
            assert await state_of(session, job) is JobState.PLANNING

            client.answer.set()
            while (await read_plan_version(session)) != VERSION:
                await asyncio.sleep(0.05)

        assert await state_of(session, job) is JobState.REVIEW


async def state_of(session: AsyncSession, job: Job) -> JobState:
    """重讀那一列的狀態（直接 `refresh` 再比，型別檢查會沿用上一次比過的值）。"""
    await session.refresh(job)
    return job.state


async def read_plan_version(session: AsyncSession) -> str:
    session.expire_all()
    return (await plan_of(session)).engine_version


async def stale(session: AsyncSession, media: Media) -> None:
    """快照超過規劃那一條期限（`media.PLANNING_TTL`）：規劃會先重抓。"""
    media.tmdb_fetched_at = datetime.now(UTC) - PLANNING_TTL - timedelta(hours=1)
    await session.commit()
