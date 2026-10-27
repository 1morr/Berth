"""Proposal：等人確認的命令存成一列（M5 票 08，plan §2.6、§11.6〈分段〉第 3 段）。

確認卡要能隔很久才按、在別的地方按、重啟之後按，所以它是一筆資料而不是等著的呼叫；執行用存下的
那一份參數、執行前重驗、逐列記結果（總覽卡會部分成功）；只有提出者或管理員按得到，連按兩次只執行
一次（brief §14〈對話裡的確認卡〉、§20.24）。不需要 AI：人也能提出。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.config import Config
from berth.db import create_engine, create_session_factory
from berth.domain import (
    Actor,
    ActorKind,
    EventType,
    JobRefusal,
    JobState,
    JobTrigger,
    ProposalRefusal,
    ProposalRowOutcome,
    ProposalStatus,
    Role,
    RssRefusal,
)
from berth.models import Event, Job, Proposal, RssFeed, User
from berth.services import proposals, registry
from berth.services.events import ProposalSignal
from berth.services.executor import CommandRefusal, CommandRefusedError
from berth.services.proposals import (
    PROPOSAL_TTL,
    InvalidProposalError,
    ProposalRejectedError,
    ProposalView,
)
from berth.services.registry import commands
from tests.integration.test_command_dry_run import harbour
from tests.integration.test_executor import ADMINS_JOB, CREWS_JOB, Loops, household
from tests.integration.test_rss import FEED_URL

pytestmark = pytest.mark.asyncio

#: 一般使用者自己送的第二筆，也停在入庫失敗。
CREWS_OTHER = "d" * 40
NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)


async def crews_other_job(session: AsyncSession, crew: User) -> None:
    session.add(
        Job(
            hash=CREWS_OTHER,
            name=CREWS_OTHER,
            trigger=JobTrigger.MANUAL,
            user_id=crew.id,
            state=JobState.IMPORT_FAILED,
        )
    )
    await session.commit()


async def retries(session: AsyncSession, job_hash: str) -> int:
    found = await session.scalar(
        select(func.count())
        .select_from(Event)
        .where(Event.job_hash == job_hash, Event.type == EventType.RETRIED.value)
    )
    return int(found or 0)


async def state_of(session: AsyncSession, job_hash: str) -> JobState:
    job = await session.get(Job, job_hash, populate_existing=True)
    assert job is not None
    return job.state


async def propose_retry(
    session: AsyncSession,
    loops: Loops,
    crew: User,
    *hashes: str,
    conversation_id: str | None = None,
    by_ai: bool = False,
) -> ProposalView:
    actor = Actor.ai(crew.id, crew.role) if by_ai else Actor.person(crew.id, crew.role)
    return await proposals.propose(
        session,
        loops.hub,
        "jobs.retry_job",
        [{"job_hash": job_hash} for job_hash in hashes],
        actor=actor,
        conversation_id=conversation_id,
        now=NOW,
    )


async def decide(
    session: AsyncSession,
    loops: Loops,
    proposal: ProposalView,
    by: User,
    *,
    approve: bool = True,
    selection: list[int] | None = None,
    now: datetime = NOW,
) -> ProposalView:
    return await proposals.decide(
        session,
        loops.executor,
        proposal.id,
        approve=approve,
        selection=selection,
        user_id=by.id,
        role=by.role,
        now=now,
    )


class TestPropose:
    async def test_a_proposal_is_a_waiting_row_with_the_checked_arguments(
        self, session: AsyncSession
    ) -> None:
        _, crew = await household(session)
        loops = Loops()

        with loops.hub.subscribe() as tab:
            view = await propose_retry(session, loops, crew, CREWS_JOB, conversation_id="c-1")
            signal = tab.get_nowait()

        assert view.status is ProposalStatus.PENDING
        assert view.command == "jobs.retry_job"
        assert view.arguments == [{"job_hash": CREWS_JOB}]
        assert len(view.arguments_hash) == 64
        assert (view.user_id, view.proposer, view.conversation_id) == (
            crew.id,
            ActorKind.PERSON,
            "c-1",
        )
        assert view.expires_at == NOW + PROPOSAL_TTL
        assert view.results is None
        # 預覽是伺服器照命令算的：效果、旗標、逐列有沒有乾跑過（`retry_job` 沒有驗證函式）。
        spec = commands()["jobs.retry_job"]
        assert view.preview.effect is spec.effect
        assert set(view.preview.flags) == set(spec.flags)
        assert view.preview.checked == (False,)
        assert signal == ProposalSignal(id=view.id, status=ProposalStatus.PENDING)
        # 提出不是執行。
        assert await state_of(session, CREWS_JOB) is JobState.IMPORT_FAILED

    async def test_one_that_fails_its_validation_is_not_built_and_says_why(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """prototype 實測的 `route_required`：加 Feed 時有收電影的 Route 卻沒選（brief §20.24）。"""
        _, anime, _ = await harbour(session, roots)
        admin = User(jellyfin_user_id="jf-admin", name="admin", role=Role.ADMIN)
        session.add(admin)
        await session.commit()
        loops = Loops()

        with pytest.raises(InvalidProposalError) as refused:
            await proposals.propose(
                session,
                loops.hub,
                "rss.add_feed",
                [{"url": FEED_URL, "tv_route_id": anime.id}],
                actor=Actor.ai(admin.id, admin.role),
                now=NOW,
            )

        assert (refused.value.row, refused.value.reason) == (0, RssRefusal.ROUTE_REQUIRED)
        assert await session.scalar(select(func.count()).select_from(Proposal)) == 0
        assert await session.scalar(select(func.count()).select_from(RssFeed)) == 0

    async def test_a_person_cannot_propose_what_only_an_admin_may_do(
        self, session: AsyncSession
    ) -> None:
        _, crew = await household(session)

        with pytest.raises(CommandRefusedError) as refused:
            await proposals.propose(
                session,
                Loops().hub,
                "rss.add_feed",
                [{"url": FEED_URL}],
                actor=Actor.person(crew.id, crew.role),
                now=NOW,
            )

        assert refused.value.reason is CommandRefusal.ADMIN_ONLY
        assert await session.scalar(select(func.count()).select_from(Proposal)) == 0


class TestDecide:
    async def test_approving_one_outside_a_conversation_runs_it_with_the_stored_arguments(
        self, session: AsyncSession
    ) -> None:
        _, crew = await household(session)
        loops = Loops()
        proposal = await propose_retry(session, loops, crew, CREWS_JOB, by_ai=True)

        view = await decide(session, loops, proposal, crew)

        assert view.status is ProposalStatus.EXECUTED
        assert (view.decided_by, view.decided_at) == (crew.id, NOW)
        assert view.results is not None
        [row] = view.results
        assert row.outcome is ProposalRowOutcome.DONE
        assert row.result["state"] == JobState.IMPORTING.value
        assert await state_of(session, CREWS_JOB) is JobState.IMPORTING
        # AI 提出、人按下去：做的那一筆記成 AI 替他做的。
        actors = await session.scalars(
            select(Event.actor).where(
                Event.job_hash == CREWS_JOB, Event.type == EventType.RETRIED.value
            )
        )
        assert list(actors) == [f"ai:{crew.id}"]
        assert await woken_importer(loops)

    async def test_rejecting_runs_nothing(self, session: AsyncSession) -> None:
        _, crew = await household(session)
        loops = Loops()
        proposal = await propose_retry(session, loops, crew, CREWS_JOB)

        view = await decide(session, loops, proposal, crew, approve=False)

        assert view.status is ProposalStatus.REJECTED
        assert view.results is None
        assert await state_of(session, CREWS_JOB) is JobState.IMPORT_FAILED

    async def test_someone_else_cannot_see_it_but_an_admin_can_decide_it(
        self, session: AsyncSession
    ) -> None:
        admin, crew = await household(session)
        other = User(jellyfin_user_id="jf-other", name="other", role=Role.USER)
        session.add(other)
        await session.commit()
        loops = Loops()
        proposal = await propose_retry(session, loops, crew, CREWS_JOB)

        with pytest.raises(ProposalRejectedError) as refused:
            await decide(session, loops, proposal, other)
        assert refused.value.reason is ProposalRefusal.PROPOSAL_MISSING
        assert await state_of(session, CREWS_JOB) is JobState.IMPORT_FAILED

        view = await decide(session, loops, proposal, admin)
        assert view.status is ProposalStatus.EXECUTED
        assert view.decided_by == admin.id

    async def test_pressing_twice_runs_it_once(self, session: AsyncSession) -> None:
        _, crew = await household(session)
        loops = Loops()
        proposal = await propose_retry(session, loops, crew, CREWS_JOB)
        await decide(session, loops, proposal, crew)

        with pytest.raises(ProposalRejectedError) as refused:
            await decide(session, loops, proposal, crew)

        assert refused.value.reason is ProposalRefusal.PROPOSAL_DECIDED
        assert refused.value.detail == ProposalStatus.EXECUTED.value
        assert await retries(session, CREWS_JOB) == 1

    async def test_two_tabs_pressing_at_once_run_it_once(
        self, session: AsyncSession, engine: AsyncEngine
    ) -> None:
        _, crew = await household(session)
        loops = Loops()
        proposal = await propose_retry(session, loops, crew, CREWS_JOB)
        sessions = create_session_factory(engine)

        async def press() -> ProposalView | ProposalRejectedError:
            async with sessions() as tab:
                try:
                    return await decide(tab, loops, proposal, crew)
                except ProposalRejectedError as refused:
                    return refused

        outcomes = await asyncio.gather(press(), press())

        refusals = [o for o in outcomes if isinstance(o, ProposalRejectedError)]
        assert [r.reason for r in refusals] == [ProposalRefusal.PROPOSAL_DECIDED]
        assert await retries(session, CREWS_JOB) == 1

    async def test_approving_one_still_in_its_conversation_runs_it_at_once(
        self, session: AsyncSession
    ) -> None:
        """票 13：核准就當場執行，對話恢復那一輪只拿結果。不會有「核准了、恢復沒成就沒做」的卡。"""
        _, crew = await household(session)
        loops = Loops()
        proposal = await propose_retry(session, loops, crew, CREWS_JOB, conversation_id="c-1")

        view = await decide(session, loops, proposal, crew)

        assert view.status is ProposalStatus.EXECUTED
        assert await state_of(session, CREWS_JOB) is JobState.IMPORTING

    async def test_a_detached_one_runs_as_soon_as_it_is_approved(
        self, session: AsyncSession
    ) -> None:
        _, crew = await household(session)
        loops = Loops()
        kept = await propose_retry(session, loops, crew, CREWS_JOB, conversation_id="c-1")
        elsewhere = await propose_retry(session, loops, crew, ADMINS_JOB, conversation_id="c-2")

        with loops.hub.subscribe() as tab:
            detached = await proposals.detach(session, loops.hub, "c-1")
            signal = tab.get_nowait()

        assert detached == [kept.id]
        assert signal == ProposalSignal(id=kept.id, status=ProposalStatus.DETACHED)
        assert (await view_of(session, elsewhere.id)).status is ProposalStatus.PENDING

        view = await decide(session, loops, kept, crew)

        assert view.status is ProposalStatus.EXECUTED
        assert await state_of(session, CREWS_JOB) is JobState.IMPORTING

    async def test_one_pressed_after_its_deadline_is_expired_and_runs_nothing(
        self, session: AsyncSession
    ) -> None:
        _, crew = await household(session)
        loops = Loops()
        proposal = await propose_retry(session, loops, crew, CREWS_JOB)

        with pytest.raises(ProposalRejectedError) as refused:
            await decide(session, loops, proposal, crew, now=NOW + PROPOSAL_TTL)

        assert refused.value.reason is ProposalRefusal.PROPOSAL_EXPIRED
        assert (await view_of(session, proposal.id)).status is ProposalStatus.EXPIRED
        assert await state_of(session, CREWS_JOB) is JobState.IMPORT_FAILED

    @pytest.mark.parametrize("selection", [[], [0, 0], [2], [-1]])
    async def test_a_selection_that_does_not_fit_the_rows_is_refused(
        self, session: AsyncSession, selection: list[int]
    ) -> None:
        _, crew = await household(session)
        await crews_other_job(session, crew)
        loops = Loops()
        proposal = await propose_retry(session, loops, crew, CREWS_JOB, CREWS_OTHER)

        with pytest.raises(ProposalRejectedError) as refused:
            await decide(session, loops, proposal, crew, selection=selection)

        assert refused.value.reason is ProposalRefusal.SELECTION_INVALID
        assert (await view_of(session, proposal.id)).status is ProposalStatus.PENDING


class TestExecute:
    async def test_an_overview_card_records_each_row_and_can_partly_succeed(
        self, session: AsyncSession
    ) -> None:
        """prototype 的總覽卡：7 列裡 5 列送出、2 列被拒（brief §20.24）。這裡第二列是別人的。"""
        _, crew = await household(session)
        loops = Loops()
        proposal = await propose_retry(session, loops, crew, CREWS_JOB, ADMINS_JOB)

        view = await decide(session, loops, proposal, crew)

        assert view.status is ProposalStatus.PARTIAL
        assert view.results is not None
        done, refused = view.results
        assert done.outcome is ProposalRowOutcome.DONE
        assert (refused.outcome, refused.reason, refused.detail) == (
            ProposalRowOutcome.REFUSED,
            JobRefusal.JOB_MISSING.value,
            ADMINS_JOB,
        )
        assert await state_of(session, CREWS_JOB) is JobState.IMPORTING
        assert await state_of(session, ADMINS_JOB) is JobState.IMPORT_FAILED

    async def test_only_the_selected_rows_run(self, session: AsyncSession) -> None:
        _, crew = await household(session)
        await crews_other_job(session, crew)
        loops = Loops()
        proposal = await propose_retry(session, loops, crew, CREWS_JOB, CREWS_OTHER)

        view = await decide(session, loops, proposal, crew, selection=[1])

        assert view.status is ProposalStatus.EXECUTED
        assert view.selection == [1]
        assert view.results is not None
        assert [row.outcome for row in view.results] == [
            ProposalRowOutcome.SKIPPED,
            ProposalRowOutcome.DONE,
        ]
        assert await state_of(session, CREWS_JOB) is JobState.IMPORT_FAILED
        assert await state_of(session, CREWS_OTHER) is JobState.IMPORTING

    async def test_when_no_row_succeeds_it_failed(self, session: AsyncSession) -> None:
        _, crew = await household(session)
        loops = Loops()
        proposal = await propose_retry(session, loops, crew, ADMINS_JOB)

        view = await decide(session, loops, proposal, crew)

        assert view.status is ProposalStatus.FAILED
        assert view.results is not None
        assert [row.outcome for row in view.results] == [ProposalRowOutcome.REFUSED]

    async def test_arguments_changed_after_the_card_was_shown_do_not_run(
        self, session: AsyncSession
    ) -> None:
        """執行用存下的那一份，而且要是卡片上那一份：雜湊對不上就一列都不做。"""
        _, crew = await household(session)
        await crews_other_job(session, crew)
        loops = Loops()
        proposal = await propose_retry(session, loops, crew, CREWS_JOB)
        await session.execute(
            update(Proposal)
            .where(Proposal.id == proposal.id)
            .values(arguments_json=[{"job_hash": CREWS_OTHER}])
        )
        await session.commit()

        view = await decide(session, loops, proposal, crew)

        assert view.status is ProposalStatus.FAILED
        assert view.results is not None
        [row] = view.results
        assert (row.outcome, row.reason) == (ProposalRowOutcome.FAILED, "arguments_changed")
        assert await state_of(session, CREWS_JOB) is JobState.IMPORT_FAILED
        assert await state_of(session, CREWS_OTHER) is JobState.IMPORT_FAILED

    async def test_a_row_that_breaks_is_recorded_and_the_others_still_run(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """沒宣告的例外只算那一列：記型別名與原文，rollback 它自己的改動，下一列照做。"""
        _, crew = await household(session)
        await crews_other_job(session, crew)
        loops = Loops()
        proposal = await propose_retry(session, loops, crew, CREWS_JOB, CREWS_OTHER)
        real = registry.dry_run

        async def flaky(spec: Any, session: AsyncSession, arguments: Any) -> Any:
            if arguments == {"job_hash": CREWS_JOB}:
                raise RuntimeError("index went away")
            return await real(spec, session, arguments)

        monkeypatch.setattr(proposals, "dry_run", flaky)

        view = await decide(session, loops, proposal, crew)

        assert view.status is ProposalStatus.PARTIAL
        assert view.results is not None
        broken, done = view.results
        assert (broken.outcome, broken.reason, broken.detail) == (
            ProposalRowOutcome.FAILED,
            "RuntimeError",
            "index went away",
        )
        assert done.outcome is ProposalRowOutcome.DONE
        assert await state_of(session, CREWS_JOB) is JobState.IMPORT_FAILED
        assert await state_of(session, CREWS_OTHER) is JobState.IMPORTING

    async def test_it_runs_with_the_proposers_role_as_it_is_now(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """管理員提出、之後被降成一般使用者：只有管理員做得了的那一列照他現在的角色被擋。"""
        _, anime, movies = await harbour(session, roots)
        admin = User(jellyfin_user_id="jf-admin", name="admin", role=Role.ADMIN)
        session.add(admin)
        await session.commit()
        loops = Loops()
        proposal = await proposals.propose(
            session,
            loops.hub,
            "rss.add_feed",
            [{"url": FEED_URL, "tv_route_id": anime.id, "movie_route_id": movies.id}],
            actor=Actor.ai(admin.id, admin.role),
            now=NOW,
        )
        admin.role = Role.USER
        await session.commit()

        view = await decide(session, loops, proposal, admin)

        assert view.status is ProposalStatus.FAILED
        assert view.results is not None
        [row] = view.results
        assert (row.outcome, row.reason) == (
            ProposalRowOutcome.REFUSED,
            CommandRefusal.ADMIN_ONLY.value,
        )
        assert await session.scalar(select(func.count()).select_from(RssFeed)) == 0

    async def test_losing_the_run_to_someone_else_still_answers_with_the_card(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """核准已經記下，執行被別處先搶走：按的人拿到卡片現在的樣子，不是 409。"""
        _, crew = await household(session)
        loops = Loops()
        proposal = await propose_retry(session, loops, crew, CREWS_JOB)

        async def taken(*_: object) -> ProposalView:
            raise ProposalRejectedError(ProposalRefusal.PROPOSAL_DECIDED, "executing")

        monkeypatch.setattr(proposals, "execute", taken)

        view = await decide(session, loops, proposal, crew)

        assert view.status is ProposalStatus.APPROVED

    async def test_only_an_approved_one_runs(self, session: AsyncSession) -> None:
        _, crew = await household(session)
        loops = Loops()
        proposal = await propose_retry(session, loops, crew, CREWS_JOB, conversation_id="c-1")

        with pytest.raises(ProposalRejectedError) as refused:
            await proposals.execute(session, loops.executor, proposal.id)

        assert refused.value.reason is ProposalRefusal.PROPOSAL_DECIDED
        assert await state_of(session, CREWS_JOB) is JobState.IMPORT_FAILED


class TestExpiry:
    async def test_the_sweep_expires_the_waiting_ones_past_their_deadline(
        self, session: AsyncSession
    ) -> None:
        _, crew = await household(session)
        loops = Loops()
        stale = await propose_retry(session, loops, crew, CREWS_JOB, conversation_id="c-1")
        detached = await propose_retry(session, loops, crew, CREWS_JOB, conversation_id="c-2")
        await proposals.detach(session, loops.hub, "c-2")
        approved = await propose_retry(session, loops, crew, CREWS_JOB, conversation_id="c-3")
        await approved_without_running(session, approved)
        fresh = await proposals.propose(
            session,
            loops.hub,
            "jobs.retry_job",
            [{"job_hash": CREWS_JOB}],
            actor=Actor.person(crew.id, crew.role),
            now=NOW + timedelta(hours=1),
        )

        with loops.hub.subscribe() as tab:
            expired = await proposals.expire_due(session, loops.hub, now=NOW + PROPOSAL_TTL)
            signals = [tab.get_nowait(), tab.get_nowait()]

        assert sorted(expired) == sorted([stale.id, detached.id])
        assert {s.id for s in signals if isinstance(s, ProposalSignal)} == set(expired)
        statuses = {
            p.id: (await view_of(session, p.id)).status for p in (stale, detached, approved, fresh)
        }
        assert statuses == {
            stale.id: ProposalStatus.EXPIRED,
            detached.id: ProposalStatus.EXPIRED,
            approved.id: ProposalStatus.APPROVED,
            fresh.id: ProposalStatus.PENDING,
        }


class TestRestart:
    async def test_a_card_from_before_a_restart_can_still_be_decided_and_run(
        self, config: Config, engine: AsyncEngine
    ) -> None:
        async with create_session_factory(engine)() as before:
            _, crew = await household(before)
            proposal = await propose_retry(before, Loops(), crew, CREWS_JOB, conversation_id="c-1")
        await engine.dispose()

        # 新的行程：新的 engine、新的 hub 與執行器，手上只有資料庫。
        reopened = create_engine(config)
        try:
            async with create_session_factory(reopened)() as after:
                loops = Loops()
                await proposals.detach(after, loops.hub, "c-1")
                user = await after.get(User, crew.id)
                assert user is not None
                view = await decide(after, loops, proposal, user)

                assert view.status is ProposalStatus.EXECUTED
                assert await state_of(after, CREWS_JOB) is JobState.IMPORTING
        finally:
            await reopened.dispose()

    async def test_a_card_approved_before_a_restart_runs_after_it(
        self, config: Config, engine: AsyncEngine
    ) -> None:
        """核准記下了、執行還沒開始就重啟：之後照樣執行得了（對話恢復那一輪會補，`services.agent`）。"""
        async with create_session_factory(engine)() as before:
            _, crew = await household(before)
            loops = Loops()
            proposal = await propose_retry(before, loops, crew, CREWS_JOB, conversation_id="c-1")
            await approved_without_running(before, proposal)
        await engine.dispose()

        reopened = create_engine(config)
        try:
            async with create_session_factory(reopened)() as after:
                view = await proposals.execute(after, Loops().executor, proposal.id)

                assert view.status is ProposalStatus.EXECUTED
                assert await state_of(after, CREWS_JOB) is JobState.IMPORTING
        finally:
            await reopened.dispose()


class TestList:
    async def test_a_person_lists_their_own_and_an_admin_lists_everyones(
        self, session: AsyncSession
    ) -> None:
        admin, crew = await household(session)
        loops = Loops()
        crews = await propose_retry(session, loops, crew, CREWS_JOB, conversation_id="c-1")
        other_chat = await propose_retry(session, loops, crew, CREWS_JOB, conversation_id="c-2")
        admins = await proposals.propose(
            session,
            loops.hub,
            "jobs.retry_job",
            [{"job_hash": ADMINS_JOB}],
            actor=Actor.person(admin.id, admin.role),
            now=NOW,
        )

        mine = await proposals.list_proposals(session, user_id=crew.id, role=crew.role)
        in_chat = await proposals.list_proposals(
            session, conversation_id="c-1", user_id=crew.id, role=crew.role
        )
        everyone = await proposals.list_proposals(session, user_id=admin.id, role=admin.role)

        assert [p.id for p in mine] == [crews.id, other_chat.id]
        assert [p.id for p in in_chat] == [crews.id]
        assert [p.id for p in everyone] == [crews.id, other_chat.id, admins.id]


class TestToolCalls:
    """票 13：AI 提出的卡片連回提出它的那一次 tool call，脫離過的記得時刻。"""

    async def test_a_card_is_found_by_the_call_that_proposed_it(
        self, session: AsyncSession
    ) -> None:
        """同一段對話裡那一次 tool call 的最新一張：有的閘道每一輪都從 `call_0` 編起。"""
        _, crew = await household(session)
        loops = Loops()

        async def propose(conversation: str) -> ProposalView:
            return await proposals.propose(
                session,
                loops.hub,
                "jobs.retry_job",
                [{"job_hash": CREWS_JOB}],
                actor=Actor.ai(crew.id, crew.role),
                conversation_id=conversation,
                tool_call_id="call_0",
                now=NOW,
            )

        earlier = await propose("c-1")
        later = await propose("c-1")
        elsewhere = await propose("c-2")

        found = await proposals.card_of_call(session, "c-1", "call_0")

        assert found is not None
        assert found.id == later.id != earlier.id
        assert found.tool_call_id == "call_0"
        assert (await proposals.card_of_call(session, "c-2", "call_0")).id == elsewhere.id  # type: ignore[union-attr]  # 上一行剛建的，一定有
        assert await proposals.card_of_call(session, "c-1", "call_1") is None

    async def test_detaching_remembers_when_and_lists_those_cards(
        self, session: AsyncSession
    ) -> None:
        _, crew = await household(session)
        loops = Loops()
        moved_on = await propose_retry(session, loops, crew, CREWS_JOB, conversation_id="c-1")
        await proposals.detach(session, loops.hub, "c-1", now=NOW)
        still_in_turn = await propose_retry(session, loops, crew, CREWS_JOB, conversation_id="c-1")

        cards = await proposals.detached_cards(session, "c-1")

        assert [card.id for card in cards] == [moved_on.id]
        assert cards[0].detached_at == NOW
        assert (await view_of(session, still_in_turn.id)).detached_at is None


async def approved_without_running(session: AsyncSession, proposal: ProposalView) -> None:
    """核准記下了、執行還沒開始（行程死在兩者之間）。按鈕的路一定接著執行，所以直接改狀態。"""
    await session.execute(
        update(Proposal).where(Proposal.id == proposal.id).values(status=ProposalStatus.APPROVED)
    )
    await session.commit()


async def view_of(session: AsyncSession, proposal_id: int) -> ProposalView:
    [found] = [
        p
        for p in await proposals.list_proposals(session, user_id=None, role=Role.ADMIN)
        if p.id == proposal_id
    ]
    return found


async def woken_importer(loops: Loops) -> bool:
    return await loops.imports.wait(0.01)
