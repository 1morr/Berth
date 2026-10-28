"""確認卡上選 Route（M5 票 23b）：這部作品放得進的 Route 不只一條時，那一列要人在卡片上選。

票 23 的真模型實跑裡，Anthropic 接口在兩條電視 Route、作品沒有 `default_route_id` 時沒問就挑了一條。
使用者決定「多條可用就永遠問」，由程式強制：提出時把那一列可選的 Route 存進 Proposal，`decide` 只收
那份清單裡的 Route。這放寬了票 08「參數存下後不可改」，只放寬到 Route，而且只能從存下的清單挑。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import Actor, ProposalRefusal, ProposalRowOutcome, ProposalStatus, Role
from berth.models import Job, Media, Proposal, Route, User
from berth.services import proposals
from berth.services.agent import card_outcome
from berth.services.proposals import ProposalRejectedError, ProposalView, RouteAsk, RouteOption
from tests.integration.arrange import factory_for
from tests.integration.test_command_dry_run import harbour
from tests.integration.test_executor import Loops
from tests.integration.test_jobs import MAGNET, MAGNET_HASH
from tests.integration.test_rss import anime_route

pytestmark = pytest.mark.asyncio

SUBMIT = "downloading.add_manual_download"
#: 第二列用的另一個 magnet（hash 不同，兩列各送一個 torrent）。
OTHER_HASH = "e" * 40
OTHER_MAGNET = f"magnet:?xt=urn:btih:{OTHER_HASH}&dn=Kimi-02"


async def crew_member(session: AsyncSession) -> User:
    crew = User(jellyfin_user_id="jf-crew", name="crew", role=Role.USER)
    session.add(crew)
    await session.commit()
    return crew


async def second_tv_route(session: AsyncSession, roots: dict[str, Path]) -> Route:
    return await anime_route(
        session,
        roots,
        slug="tv",
        name="TV",
        jellyfin_library_id="item-4",
        jellyfin_library_name="TV",
        target_path=str(roots["library"] / "tv"),
        category="berth-tv",
    )


def submit_row(media: Media, route: Route, *, url: str = MAGNET) -> dict[str, object]:
    return {
        "source": {"url": url, "title": "[Sub] Kimi - 01 [1080p]"},
        "media_id": media.id,
        "route_id": route.id,
    }


async def propose(
    session: AsyncSession, loops: Loops, crew: User, *rows: dict[str, object]
) -> ProposalView:
    return await proposals.propose(
        session, loops.hub, SUBMIT, list(rows), actor=Actor.ai(crew.id, crew.role)
    )


async def decide(
    session: AsyncSession,
    loops: Loops,
    card: ProposalView,
    crew: User,
    *,
    routes: list[int | None] | None = None,
    selection: list[int] | None = None,
) -> ProposalView:
    return await proposals.decide(
        session,
        loops.executor,
        card.id,
        approve=True,
        selection=selection,
        routes=routes,
        user_id=crew.id,
        role=crew.role,
    )


async def status_of(session: AsyncSession, proposal_id: int) -> ProposalStatus:
    found = await session.get(Proposal, proposal_id, populate_existing=True)
    assert found is not None
    return found.status


async def job_route(session: AsyncSession, job_hash: str) -> int | None:
    job = await session.get(Job, job_hash, populate_existing=True)
    assert job is not None
    return job.route_id


class TestOneRouteFits:
    async def test_the_row_asks_nothing_and_runs_with_the_route_it_was_given(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, anime, _ = await harbour(session, roots)
        crew = await crew_member(session)
        loops = Loops(factory_for(roots))

        card = await propose(session, loops, crew, submit_row(media, anime))
        view = await decide(session, loops, card, crew)

        assert card.preview.routes == (None,)
        assert view.status is ProposalStatus.EXECUTED, view.results
        assert await job_route(session, MAGNET_HASH) == anime.id

    async def test_a_route_for_a_row_that_asks_none_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """其餘參數照舊不收：只有一條可用的那一列不能藉 `routes` 改成別條。"""
        media, anime, movies = await harbour(session, roots)
        crew = await crew_member(session)
        loops = Loops(factory_for(roots))
        card = await propose(session, loops, crew, submit_row(media, anime))

        with pytest.raises(ProposalRejectedError) as refused:
            await decide(session, loops, card, crew, routes=[movies.id])

        assert refused.value.reason is ProposalRefusal.ROUTE_NOT_OFFERED
        assert await status_of(session, card.id) is ProposalStatus.PENDING


class TestManyRoutesFit:
    async def test_the_card_stores_each_rows_choices_and_preselects_none_without_a_default(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, anime, _ = await harbour(session, roots)
        tv = await second_tv_route(session, roots)
        crew = await crew_member(session)

        card = await propose(session, Loops(), crew, submit_row(media, anime))

        assert card.preview.routes == (
            RouteAsk(
                options=(RouteOption(id=anime.id, name="Anime"), RouteOption(id=tv.id, name="TV")),
                preselected=None,
            ),
        )

    async def test_the_route_this_work_used_last_is_preselected(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, anime, _ = await harbour(session, roots)
        tv = await second_tv_route(session, roots)
        media.default_route_id = tv.id
        await session.commit()
        crew = await crew_member(session)

        # 模型給的是 Anime；預選的仍是這部作品上次用的那一條，不是模型挑的。
        card = await propose(session, Loops(), crew, submit_row(media, anime))

        [ask] = card.preview.routes
        assert ask is not None
        assert ask.preselected == tv.id

    async def test_approving_without_a_route_is_refused_and_runs_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, anime, _ = await harbour(session, roots)
        await second_tv_route(session, roots)
        crew = await crew_member(session)
        loops = Loops(factory_for(roots))
        card = await propose(session, loops, crew, submit_row(media, anime))

        with pytest.raises(ProposalRejectedError) as refused:
            await decide(session, loops, card, crew)

        assert refused.value.reason is ProposalRefusal.ROUTE_REQUIRED
        assert refused.value.detail == "0"
        assert await status_of(session, card.id) is ProposalStatus.PENDING
        assert await session.scalar(select(Job.hash)) is None

    async def test_a_route_outside_the_stored_choices_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, anime, movies = await harbour(session, roots)
        await second_tv_route(session, roots)
        crew = await crew_member(session)
        loops = Loops(factory_for(roots))
        card = await propose(session, loops, crew, submit_row(media, anime))

        with pytest.raises(ProposalRejectedError) as refused:
            await decide(session, loops, card, crew, routes=[movies.id])

        assert refused.value.reason is ProposalRefusal.ROUTE_NOT_OFFERED
        assert await status_of(session, card.id) is ProposalStatus.PENDING

    async def test_the_route_chosen_on_the_card_is_the_one_sent(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, anime, _ = await harbour(session, roots)
        tv = await second_tv_route(session, roots)
        crew = await crew_member(session)
        loops = Loops(factory_for(roots))
        card = await propose(session, loops, crew, submit_row(media, anime))

        view = await decide(session, loops, card, crew, routes=[tv.id])

        assert view.status is ProposalStatus.EXECUTED, view.results
        assert view.routes == [tv.id]
        # 存下的參數沒變；送出用的是卡片上選的那一條。
        assert view.arguments[0]["route_id"] == anime.id
        assert await job_route(session, MAGNET_HASH) == tv.id
        refreshed = await session.get(Media, media.id, populate_existing=True)
        assert refreshed is not None
        assert refreshed.default_route_id == tv.id
        # 模型拿到的結果說出人選了哪一條（它給的是 Anime）。
        assert card_outcome(view)["rows"] == [
            {
                "row": 0,
                "outcome": "done",
                "reason": "",
                "detail": "",
                "result": view.results[0].result,  # type: ignore[index]  # 上面斷言過已執行
                "route_chosen_on_card": tv.id,
            }
        ]

    async def test_a_row_left_unticked_needs_no_route(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, anime, _ = await harbour(session, roots)
        tv = await second_tv_route(session, roots)
        crew = await crew_member(session)
        loops = Loops(factory_for(roots))
        card = await propose(
            session,
            loops,
            crew,
            submit_row(media, anime),
            submit_row(media, anime, url=OTHER_MAGNET),
        )

        view = await decide(session, loops, card, crew, routes=[None, tv.id], selection=[1])

        assert view.results is not None
        assert [row.outcome for row in view.results] == [
            ProposalRowOutcome.SKIPPED,
            ProposalRowOutcome.DONE,
        ]
        assert await job_route(session, OTHER_HASH) == tv.id

    async def test_routes_that_do_not_cover_every_row_are_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, anime, _ = await harbour(session, roots)
        tv = await second_tv_route(session, roots)
        crew = await crew_member(session)
        loops = Loops(factory_for(roots))
        card = await propose(
            session,
            loops,
            crew,
            submit_row(media, anime),
            submit_row(media, anime, url=OTHER_MAGNET),
        )

        with pytest.raises(ProposalRejectedError) as refused:
            await decide(session, loops, card, crew, routes=[tv.id])

        assert refused.value.reason is ProposalRefusal.ROUTE_NOT_OFFERED

    async def test_rejecting_needs_no_route(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, anime, _ = await harbour(session, roots)
        await second_tv_route(session, roots)
        crew = await crew_member(session)
        loops = Loops(factory_for(roots))
        card = await propose(session, loops, crew, submit_row(media, anime))

        view = await proposals.decide(
            session, loops.executor, card.id, approve=False, user_id=crew.id, role=crew.role
        )

        assert view.status is ProposalStatus.REJECTED
