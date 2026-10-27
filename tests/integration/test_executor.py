"""命令執行器（M5 票 07）：AI、確認卡、之後的 Discord 與 MCP 共用的那一條路。

原本散在 API 層的語意要在這裡：叫醒背景迴圈、推播、記下是誰（`ai` 替誰做的）、角色、
把拒絕變成同一個形狀（研究 R9、R14，brief §19「M5 的方向」⑦）。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import (
    SYSTEM_ACTOR,
    Actor,
    EventType,
    JobRefusal,
    JobState,
    JobTrigger,
    Role,
)
from berth.models import Event, Job, User
from berth.services.events import EventHub
from berth.services.executor import CommandRefusal, CommandRefusedError, Executor
from berth.services.hints import JobHints
from berth.services.jobs import JobRejectedError, JobSource
from berth.services.sources import SourceCache
from tests.integration.arrange import factory_for
from tests.integration.factories import FakeClientFactory
from tests.integration.test_command_dry_run import harbour
from tests.integration.test_deletion import imported
from tests.integration.test_jobs import MAGNET, MAGNET_HASH
from tests.integration.test_rss import KIMI_KEY, series_by_key
from tests.integration.test_rss import harbour as rss_harbour
from tests.integration.test_rss_screen import serve_single

pytestmark = pytest.mark.asyncio

ADMINS_JOB = "a" * 40
CREWS_JOB = "c" * 40


class Loops:
    """執行器手上的東西，測試看得到它們被怎麼用了。"""

    def __init__(self, factory: FakeClientFactory | None = None) -> None:
        self.hub = EventHub()
        self.plans = JobHints()
        self.imports = JobHints()
        self.executor = Executor(
            factory=factory or FakeClientFactory(),
            hub=self.hub,
            sources=SourceCache(),
            plans=self.plans,
            imports=self.imports,
        )


async def household(session: AsyncSession) -> tuple[User, User]:
    """一位管理員、一位一般使用者，各送過一筆，兩筆都入庫失敗。"""
    admin = User(jellyfin_user_id="jf-admin", name="admin", role=Role.ADMIN)
    crew = User(jellyfin_user_id="jf-crew", name="crew", role=Role.USER)
    session.add_all([admin, crew])
    await session.flush()
    for job_hash, owner in ((ADMINS_JOB, admin), (CREWS_JOB, crew)):
        session.add(
            Job(
                hash=job_hash,
                name=job_hash,
                trigger=JobTrigger.MANUAL,
                user_id=owner.id,
                state=JobState.IMPORT_FAILED,
            )
        )
    await session.commit()
    return admin, crew


def magnet() -> JobSource:
    return JobSource(url=MAGNET, title="[Sub] Kimi - 01 [1080p]")


async def woken(hints: JobHints) -> bool:
    return await hints.wait(0.01)


class TestAfterTheCommand:
    async def test_retrying_an_import_wakes_the_importer_tells_the_tabs_and_names_the_ai(
        self, session: AsyncSession
    ) -> None:
        _, crew = await household(session)
        loops = Loops()

        with loops.hub.subscribe() as tab:
            view = await loops.executor.execute(
                session, "jobs.retry_job", {"job_hash": CREWS_JOB}, Actor.ai(crew.id, crew.role)
            )
            signal = tab.get_nowait()

        assert view.state is JobState.IMPORTING
        assert (signal.hash, signal.state) == (CREWS_JOB, JobState.IMPORTING)
        assert await woken(loops.imports)
        assert not await woken(loops.plans)
        actors = await session.scalars(
            select(Event.actor).where(
                Event.job_hash == CREWS_JOB, Event.type == EventType.RETRIED.value
            )
        )
        assert list(actors) == [f"ai:{crew.id}"]

    async def test_a_job_sent_back_to_completed_wakes_the_planner(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        job, _, factory = await imported(session, roots)
        admin = User(jellyfin_user_id="jf-admin", name="admin", role=Role.ADMIN)
        session.add(admin)
        await session.commit()
        loops = Loops(factory)

        view = await loops.executor.execute(
            session,
            "reimport.reimport_job",
            {"job_hash": job.hash},
            Actor.person(admin.id, admin.role),
        )

        assert view.state is JobState.COMPLETED
        assert await woken(loops.plans)
        assert not await woken(loops.imports)

    async def test_a_series_the_ai_binds_says_the_ai_bound_it(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await rss_harbour(session, roots)
        serve_single(factory)
        admin = User(jellyfin_user_id="jf-admin", name="admin", role=Role.ADMIN)
        session.add(admin)
        await session.commit()

        await Loops(factory).executor.execute(
            session,
            "rss.subscribe_mikan",
            {"bangumi_id": 4009, "subgroup_id": 370, "media_id": media.id, "route_id": route.id},
            Actor.ai(admin.id, admin.role),
        )

        assert (await series_by_key(session, KIMI_KEY)).bound_by == f"ai:{admin.id}"

    async def test_reading_a_job_wakes_nothing_and_tells_no_one(
        self, session: AsyncSession
    ) -> None:
        admin, _ = await household(session)
        job = await session.get_one(Job, CREWS_JOB)
        job.state = JobState.COMPLETED
        await session.commit()
        loops = Loops()

        with loops.hub.subscribe() as tab:
            view = await loops.executor.execute(
                session,
                "jobs.read_job",
                {"job_hash": CREWS_JOB},
                Actor.person(admin.id, admin.role),
            )

            assert tab.empty()
        assert view.state is JobState.COMPLETED
        assert not await woken(loops.plans)


class TestWhoMayDoIt:
    async def test_the_ai_of_an_ordinary_user_cannot_retry_someone_elses_job(
        self, session: AsyncSession
    ) -> None:
        _, crew = await household(session)
        loops = Loops()

        with pytest.raises(CommandRefusedError) as refused:
            await loops.executor.execute(
                session, "jobs.retry_job", {"job_hash": ADMINS_JOB}, Actor.ai(crew.id, crew.role)
            )

        assert (refused.value.reason, refused.value.detail) == (
            JobRefusal.JOB_MISSING,
            ADMINS_JOB,
        )
        assert (await session.get_one(Job, ADMINS_JOB)).state is JobState.IMPORT_FAILED
        assert not await woken(loops.imports)

    async def test_an_admin_retries_anyones(self, session: AsyncSession) -> None:
        admin, _ = await household(session)

        view = await Loops().executor.execute(
            session, "jobs.retry_job", {"job_hash": CREWS_JOB}, Actor.person(admin.id, admin.role)
        )

        assert view.state is JobState.IMPORTING

    async def test_an_ordinary_user_cannot_run_an_admin_command(
        self, session: AsyncSession
    ) -> None:
        _, crew = await household(session)

        for actor in (Actor.person(crew.id, crew.role), Actor.ai(crew.id, crew.role)):
            with pytest.raises(CommandRefusedError) as refused:
                await Loops().executor.execute(session, "routes.list_routes", {}, actor)
            assert refused.value.reason is CommandRefusal.ADMIN_ONLY

    async def test_the_ai_of_an_admin_can(self, session: AsyncSession) -> None:
        admin, _ = await household(session)

        routes = await Loops().executor.execute(
            session, "routes.list_routes", {}, Actor.ai(admin.id, admin.role)
        )

        assert routes == ()


class TestWhatIsNotACommand:
    @pytest.mark.parametrize("name", ["jobs.no_such_thing", "jobs.record_event", "jobs.own_job"])
    async def test_an_unknown_or_internal_command_is_refused(
        self, session: AsyncSession, name: str
    ) -> None:
        with pytest.raises(CommandRefusedError) as refused:
            await Loops().executor.execute(session, name, {}, SYSTEM_ACTOR)

        assert refused.value.reason is CommandRefusal.UNKNOWN_COMMAND


class TestSubmitting:
    async def test_the_ai_submits_for_the_user_it_works_for(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, anime, _ = await harbour(session, roots)
        crew = User(jellyfin_user_id="jf-crew", name="crew", role=Role.USER)
        session.add(crew)
        await session.commit()
        loops = Loops(factory_for(roots))

        with loops.hub.subscribe() as tab:
            outcome = await loops.executor.execute(
                session,
                "downloading.add_manual_download",
                {"source": magnet(), "media_id": media.id, "route_id": anime.id},
                Actor.ai(crew.id, crew.role),
            )
            signal = tab.get_nowait()

        job = await session.get_one(Job, MAGNET_HASH)
        assert (outcome.created, job.user_id) == (True, crew.id)
        assert signal.hash == MAGNET_HASH
        created = await session.scalar(
            select(Event.actor).where(
                Event.job_hash == MAGNET_HASH, Event.type == EventType.CREATED.value
            )
        )
        assert created == f"ai:{crew.id}"

    async def test_a_refusal_keeps_the_reason_of_its_module(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, _, movies = await harbour(session, roots)

        with pytest.raises(CommandRefusedError) as refused:
            await Loops(factory_for(roots)).executor.execute(
                session,
                "downloading.add_manual_download",
                {"source": magnet(), "media_id": media.id, "route_id": movies.id},
                SYSTEM_ACTOR,
            )

        assert refused.value.command == "downloading.add_manual_download"
        assert refused.value.reason is JobRefusal.ROUTE_KIND_MISMATCH
        assert isinstance(refused.value.__cause__, JobRejectedError)

    async def test_a_command_needing_what_the_executor_lacks_says_so(
        self, session: AsyncSession
    ) -> None:
        """`watching.read_watching` 要那個人的 Jellyfin 存取（`JellyfinAccess`）：執行器還給不出，
        照實說，不帶著缺的那一格硬叫。"""
        with pytest.raises(RuntimeError, match="cannot supply access"):
            await Loops().executor.execute(
                session, "watching.read_watching", {"library_id": "x"}, SYSTEM_ACTOR
            )
