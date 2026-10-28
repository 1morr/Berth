"""確認卡上選字幕組（M5 票 26）：訂閱的字幕組由使用者選，伺服器擋模型代選。

試用機上（2026-10-28）助理在 Mikan 自己挑了 ANi，卡上只能按確認。使用者決定：可選的字幕組不只一個
時卡上必選，模型帶來的只當預選；伺服器只收提出時存下的那份清單裡的（照票 23b 的 Route）。選項由提出
的一方算（`services.agent`：Mikan 讀番組頁、關鍵字讀那一次搜尋），這裡測的是存、收、套用。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import Actor, FeedKind, ProposalRefusal, ProposalStatus, Role
from berth.models import Media, Proposal, Route, RssFeed, User
from berth.services import proposals
from berth.services.agent import card_outcome
from berth.services.proposals import (
    ProposalRejectedError,
    ProposalView,
    SubgroupAsk,
    SubgroupOption,
)
from berth.services.rss import SubscriptionRef
from tests.integration.arrange import factory_for
from tests.integration.test_command_dry_run import harbour
from tests.integration.test_executor import Loops

pytestmark = pytest.mark.asyncio

SEARCH = "rss.subscribe_search"


def option(name: str, *titles: str) -> SubgroupOption:
    return SubgroupOption(
        key=name,
        name=name,
        releases=len(titles),
        updated=None,
        latest=titles[0] if titles else "",
        titles=titles,
        arguments={"subgroup": name},
    )


ANI = option("ANi", "[ANi] Kimi - 02 [1080P]", "[ANi] Kimi - 01 [1080P]")
MOUSE = option("黒ネズミたち", "[黒ネズミたち] Kimi - 02 (CR 1920x1080)")


def keyword_row(media: Media, route: Route, *, subgroup: str = "ANi") -> dict[str, object]:
    return {
        "kind": FeedKind.ACGRIP.value,
        "term": "Kimi ga Shinu made Koi wo Shitai",
        "subgroup": subgroup,
        "media_id": media.id,
        "route_id": route.id,
    }


async def admin(session: AsyncSession) -> User:
    user = User(jellyfin_user_id="jf-admin", name="admin", role=Role.ADMIN)
    session.add(user)
    await session.commit()
    return user


async def propose(
    session: AsyncSession,
    loops: Loops,
    user: User,
    row: dict[str, object],
    ask: SubgroupAsk | None,
    existing: tuple[SubscriptionRef, ...] = (),
) -> ProposalView:
    return await proposals.propose(
        session,
        loops.hub,
        SEARCH,
        [row],
        actor=Actor.ai(user.id, user.role),
        subgroups=[ask],
        existing=[existing],
    )


async def decide(
    session: AsyncSession,
    loops: Loops,
    card: ProposalView,
    user: User,
    subgroups: list[str | None] | None,
) -> ProposalView:
    return await proposals.decide(
        session,
        loops.executor,
        card.id,
        approve=True,
        subgroups=subgroups,
        user_id=user.id,
        role=user.role,
    )


async def status_of(session: AsyncSession, proposal_id: int) -> ProposalStatus:
    found = await session.get(Proposal, proposal_id, populate_existing=True)
    assert found is not None
    return found.status


async def feed_subgroup(session: AsyncSession) -> str:
    (feed,) = await session.scalars(select(RssFeed))
    return feed.subgroup


class TestMoreThanOneSubgroup:
    async def test_the_card_stores_the_choices_and_the_models_pick_only_as_preselected(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, anime, _ = await harbour(session, roots)
        user = await admin(session)
        loops = Loops(factory_for(roots))
        ask = SubgroupAsk(options=(ANI, MOUSE), preselected="ANi", required=True)

        card = await propose(session, loops, user, keyword_row(media, anime), ask)
        again = (await proposals.list_proposals(session, user_id=user.id, role=user.role))[0]

        assert card.preview.subgroups == (ask,)
        # 存進資料庫再讀回來是同一份（JSON 來回）。
        assert again.preview.subgroups == (ask,)

    async def test_without_a_pick_it_is_refused_and_still_waits(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """模型帶來的那一個不算人選的：沒選就是 `subgroup_required`，即使有預選。"""
        media, anime, _ = await harbour(session, roots)
        user = await admin(session)
        loops = Loops(factory_for(roots))
        ask = SubgroupAsk(options=(ANI, MOUSE), preselected="ANi", required=True)
        card = await propose(session, loops, user, keyword_row(media, anime), ask)

        nothing: list[list[str | None] | None] = [None, [None]]
        for given in nothing:
            with pytest.raises(ProposalRejectedError) as refused:
                await decide(session, loops, card, user, given)
            assert refused.value.reason is ProposalRefusal.SUBGROUP_REQUIRED

        assert await status_of(session, card.id) is ProposalStatus.PENDING
        assert await session.scalar(select(RssFeed.id)) is None

    async def test_a_subgroup_outside_the_list_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, anime, _ = await harbour(session, roots)
        user = await admin(session)
        loops = Loops(factory_for(roots))
        ask = SubgroupAsk(options=(ANI, MOUSE), preselected="ANi", required=True)
        card = await propose(session, loops, user, keyword_row(media, anime), ask)

        with pytest.raises(ProposalRejectedError) as refused:
            await decide(session, loops, card, user, ["ToonsHub"])

        assert refused.value.reason is ProposalRefusal.SUBGROUP_NOT_OFFERED
        assert await status_of(session, card.id) is ProposalStatus.PENDING

    async def test_the_picked_one_overrides_what_the_model_gave(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, anime, _ = await harbour(session, roots)
        user = await admin(session)
        loops = Loops(factory_for(roots))
        ask = SubgroupAsk(options=(ANI, MOUSE), preselected="ANi", required=True)
        card = await propose(session, loops, user, keyword_row(media, anime), ask)

        view = await decide(session, loops, card, user, ["黒ネズミたち"])

        assert view.status is ProposalStatus.EXECUTED, view.results
        assert view.subgroups == ["黒ネズミたち"]
        assert await feed_subgroup(session) == "黒ネズミたち"
        # 存下的參數不動（雜湊照舊對得上），模型拿到的是人選的那一個。
        assert view.arguments[0]["subgroup"] == "ANi"
        rows = card_outcome(view)["rows"]
        assert isinstance(rows, list)
        [row] = rows
        assert row["subgroup_chosen_on_card"] == "黒ネズミたち"


class TestOneSubgroup:
    async def test_the_only_subgroup_the_model_also_gave_needs_no_pick(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """只搜到一個、就是模型給的：卡上只列出來（第一批照樣看得到），按下去就用它。"""
        media, anime, _ = await harbour(session, roots)
        user = await admin(session)
        loops = Loops(factory_for(roots))
        ask = SubgroupAsk(options=(ANI,), preselected="ANi", required=False)
        card = await propose(session, loops, user, keyword_row(media, anime), ask)

        view = await decide(session, loops, card, user, None)

        assert view.status is ProposalStatus.EXECUTED, view.results
        assert await feed_subgroup(session) == "ANi"

    async def test_one_subgroup_that_is_not_the_models_must_be_picked(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, anime, _ = await harbour(session, roots)
        user = await admin(session)
        loops = Loops(factory_for(roots))
        ask = SubgroupAsk(options=(MOUSE,), preselected=None, required=True)
        card = await propose(session, loops, user, keyword_row(media, anime), ask)

        with pytest.raises(ProposalRejectedError) as refused:
            await decide(session, loops, card, user, None)

        assert refused.value.reason is ProposalRefusal.SUBGROUP_REQUIRED

    async def test_a_row_without_choices_takes_no_subgroup(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """其餘參數照舊不收：沒得選的列不能藉 `subgroups` 換字幕組。"""
        media, anime, _ = await harbour(session, roots)
        user = await admin(session)
        loops = Loops(factory_for(roots))
        card = await propose(session, loops, user, keyword_row(media, anime), None)

        with pytest.raises(ProposalRejectedError) as refused:
            await decide(session, loops, card, user, ["黒ネズミたち"])

        assert refused.value.reason is ProposalRefusal.SUBGROUP_NOT_OFFERED


class TestExistingSubscriptions:
    async def test_the_card_and_the_model_are_told_what_the_work_already_has(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, anime, _ = await harbour(session, roots)
        user = await admin(session)
        loops = Loops(factory_for(roots))
        ask = SubgroupAsk(options=(ANI,), preselected="ANi", required=False)
        before = SubscriptionRef(
            feed_id=7, name="acg.rip · Kimi", kind=FeedKind.ACGRIP, subgroup=""
        )
        card = await propose(session, loops, user, keyword_row(media, anime), ask, (before,))

        view = await decide(session, loops, card, user, None)

        assert card.preview.existing == ((before,),)
        rows = card_outcome(view)["rows"]
        assert isinstance(rows, list)
        [row] = rows
        assert row["existing_subscriptions"] == [
            {"feed_id": 7, "name": "acg.rip · Kimi", "kind": "acgrip", "subgroup": ""}
        ]
