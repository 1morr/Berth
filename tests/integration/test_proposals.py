"""確認卡（Proposal，M5 票 10，plan §11.6〈對話核心〉、CONTEXT.md 的 Proposal）。

不可逆的工具 AI 永遠不能自己做：工具迴圈遇到它不執行，建一筆 Proposal、回給模型「已提出，等人
確認」；人按了確認才以按的那個人執行，按的當下重驗角色與輸入。從核心的介面進去
（`AssistantRuns.send` / `confirm` / `reject`），外部服務用替身、磁碟用暫存目錄。
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.adapters.ai import (
    ModelTurn,
    StopReason,
    TextPart,
    ToolCall,
    TurnEnded,
    Usage,
    UserTurn,
)
from berth.adapters.ai.fake import FakeChatProvider
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.db import create_session_factory
from berth.domain import (
    ProposalRefusal,
    ProposalStatus,
    Role,
    ServiceKind,
    ServiceOrigin,
    ToolOutcome,
)
from berth.models import SetupSettings
from berth.services.assistant import AssistantRuns, ToolFinished
from berth.services.auth import AuthenticatedUser
from berth.services.conversations import ProposalRejectedError
from berth.services.deletion import DeleteScope, DeletionRefusal, delete_job
from berth.services.indexer import SiteRefusal, apply_default_indexers
from berth.services.proposals import ProposalCard, of_conversation
from berth.services.registry import ToolRefusal
from berth.services.settings import read_settings, write_settings
from tests.integration.arrange import chosen, own
from tests.integration.factories import FakeClientFactory
from tests.integration.test_assistant import NOW, ai_ready, drain, person, says, started_id
from tests.integration.test_deletion import LINKS, SOURCES, alive, imported, sources, targets

pytestmark = pytest.mark.asyncio


def asks(name: str, **arguments: object) -> TurnEnded:
    """模型叫一個工具，帶著這些參數。"""
    return TurnEnded(
        stop=StopReason.TOOL_CALLS,
        stop_raw="tool_use",
        reply=ModelTurn((ToolCall(id="call_0", name=name, arguments=json.dumps(arguments)),)),
        usage=Usage(input_tokens=10, output_tokens=2),
    )


async def bundled_prowlarr(session: AsyncSession) -> None:
    await own(session)
    setup = await read_settings(session, SetupSettings)
    setup.choices = {
        ServiceKind.PROWLARR: chosen(ServiceOrigin.BUNDLED, "http://prowlarr:9696"),
    }
    await write_settings(session, setup)
    await session.commit()


def card_id(card: dict[str, object]) -> int:
    found = card["id"]
    assert isinstance(found, int)
    return found


def proposed_card(events: Sequence[object]) -> dict[str, object]:
    [finished] = [event for event in events if isinstance(event, ToolFinished)]
    assert finished.result.outcome is ToolOutcome.PROPOSED
    assert finished.result.result_type == "ProposalCard"
    return finished.result.result


# --- 加索引站 ---------------------------------------------------------------------


async def test_adding_an_indexer_stops_on_a_card_and_happens_only_when_confirmed(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    admin = await person(session, "skipper", Role.ADMIN)
    await ai_ready(session)
    await bundled_prowlarr(session)
    prowlarr = FakeProwlarrClient()
    provider = FakeChatProvider(
        replies=[
            asks("add_indexer", site="Nyaa.si", reason="You asked for an anime tracker."),
            says("I proposed adding Nyaa.si; press confirm on the card."),
        ]
    )
    sessions = create_session_factory(engine)
    runs = AssistantRuns(
        sessions, FakeClientFactory(ai=provider, prowlarr=prowlarr), now=lambda: NOW
    )

    events = await drain(runs, admin, "add an indexer for anime")

    card = proposed_card(events)
    assert card["status"] == ProposalStatus.PROPOSED
    assert card["reason"] == "You asked for an anime tracker."
    # 卡上講清楚會發生什麼：加哪一站、它在哪個網址、加到哪一台。
    assert card["preview_type"] == "IndexerAddition"
    preview = card["preview"]
    assert isinstance(preview, dict)
    assert preview["site"] == "nyaasi"
    assert preview["url"] == "https://nyaa.si/"
    assert preview["prowlarr"] == "http://prowlarr:9696"
    # 模型拿到的是「已提出，等人確認」，不是做好了。
    model_saw = provider.requests[1].turns[-1]
    assert isinstance(model_saw, UserTurn)
    assert '"status": "proposed"' in model_saw.parts[0].content  # type: ignore[union-attr]  # 這一輪只有工具結果
    # 沒按之前什麼都沒加。
    assert prowlarr.add_attempts == []

    decided = await runs.confirm(card_id(card), user=admin)

    assert decided.status is ProposalStatus.CONFIRMED
    assert decided.result_type == "IndexerAdded"
    assert prowlarr.add_attempts == ["nyaasi"]
    # 結果回到對話裡：卡片讀得到，下一句話時模型也看得到。
    async with sessions() as fresh:
        cards = await of_conversation(fresh, user_id=admin.id, conversation_id=started_id(events))
    assert [card.status for card in cards] == [ProposalStatus.CONFIRMED]
    provider.replies.append(says("Done."))
    await drain(runs, admin, "thanks", conversation_id=started_id(events))
    last = provider.requests[-1].turns[-1]
    assert isinstance(last, UserTurn)
    decision = last.parts[0]
    assert isinstance(decision, TextPart)
    assert '"proposal": ' in decision.text
    assert '"status": "confirmed"' in decision.text


# --- 刪 complete ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeletionAsked:
    runs: AssistantRuns
    admin: AuthenticatedUser
    media: str
    card: dict[str, object]


async def deletion_asked(
    engine: AsyncEngine, session: AsyncSession, roots: dict[str, Path]
) -> DeletionAsked:
    """一部入庫完的作品，管理員叫 AI 刪掉它的 complete。"""
    job, _, factory = await imported(session, roots)
    admin = await person(session, "skipper", Role.ADMIN)
    await ai_ready(session)
    assert job.media_id is not None
    factory.ai_ = FakeChatProvider(
        replies=[
            asks("delete_downloads", media=job.media_id, reason="You asked to stop seeding it."),
            says("Press confirm on the card to delete them."),
        ]
    )
    runs = AssistantRuns(create_session_factory(engine), factory, now=lambda: NOW)
    events = await drain(runs, admin, "delete this one's complete")
    return DeletionAsked(runs, admin, job.media_id, proposed_card(events))


async def test_deleting_downloads_stops_on_a_card_listing_the_files_and_rejecting_keeps_them(
    engine: AsyncEngine, session: AsyncSession, roots: dict[str, Path]
) -> None:
    asked = await deletion_asked(engine, session, roots)

    assert asked.card["preview_type"] == "DownloadsDeletion"
    preview = asked.card["preview"]
    assert isinstance(preview, dict)
    assert preview["media"] == asked.media
    [job] = preview["jobs"]
    # 卡上列出會刪的每一個檔案：complete 裡這一包的六個，包含沒入庫的 readme。
    assert sorted(job["files"]) == sorted(str(path) for path in await sources(session))
    # 沒按之前什麼都沒刪。
    assert len(alive(await sources(session))) == SOURCES

    rejected = await asked.runs.reject(card_id(asked.card), user=asked.admin)

    assert rejected.status is ProposalStatus.REJECTED
    assert len(alive(await sources(session))) == SOURCES
    assert len(alive(await targets(session))) == LINKS


async def test_confirming_the_deletion_removes_the_downloads_and_keeps_the_library(
    engine: AsyncEngine, session: AsyncSession, roots: dict[str, Path]
) -> None:
    asked = await deletion_asked(engine, session, roots)

    decided = await asked.runs.confirm(card_id(asked.card), user=asked.admin)

    assert decided.status is ProposalStatus.CONFIRMED
    assert decided.result_type == "DownloadsDeleted"
    assert alive(await sources(session)) == []
    # 「刪 complete」不拆媒體庫：Jellyfin 照樣看得到。
    assert len(alive(await targets(session))) == LINKS


# --- 按下去的當下重驗 ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IndexerAsked:
    runs: AssistantRuns
    admin: AuthenticatedUser
    prowlarr: FakeProwlarrClient
    conversation: int
    card: dict[str, object]


async def indexer_asked(engine: AsyncEngine, session: AsyncSession) -> IndexerAsked:
    admin = await person(session, "skipper", Role.ADMIN)
    await ai_ready(session)
    await bundled_prowlarr(session)
    prowlarr = FakeProwlarrClient()
    provider = FakeChatProvider(
        replies=[asks("add_indexer", site="nyaasi", reason="For anime."), says("Proposed.")]
    )
    runs = AssistantRuns(
        create_session_factory(engine),
        FakeClientFactory(ai=provider, prowlarr=prowlarr),
        now=lambda: NOW,
    )
    events = await drain(runs, admin, "add nyaa")
    return IndexerAsked(runs, admin, prowlarr, started_id(events), proposed_card(events))


def refusal_of(card: ProposalCard) -> tuple[str, str]:
    assert card.status is ProposalStatus.EXPIRED
    assert card.result_type == "Refusal"
    assert card.result is not None
    return card.result["reason"], card.result["detail"]


async def test_a_card_whose_site_was_added_meanwhile_expires_and_says_why(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    asked = await indexer_asked(engine, session)
    # 卡片等著的時候，有人在設定頁把這一站加了。
    await apply_default_indexers(session, FakeClientFactory(prowlarr=asked.prowlarr), ["nyaasi"])
    attempts = list(asked.prowlarr.add_attempts)

    decided = await asked.runs.confirm(card_id(asked.card), user=asked.admin)

    assert refusal_of(decided) == (SiteRefusal.SITE_PRESENT, "Nyaa.si")
    assert asked.prowlarr.add_attempts == attempts


async def test_a_card_whose_proposer_lost_the_role_expires(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    asked = await indexer_asked(engine, session)
    demoted = replace(asked.admin, role=Role.USER)

    decided = await asked.runs.confirm(card_id(asked.card), user=demoted)

    assert refusal_of(decided)[0] == ToolRefusal.NOT_ALLOWED
    assert asked.prowlarr.add_attempts == []


async def test_a_card_whose_downloads_were_deleted_meanwhile_expires(
    engine: AsyncEngine, session: AsyncSession, roots: dict[str, Path]
) -> None:
    asked = await deletion_asked(engine, session, roots)
    preview = asked.card["preview"]
    assert isinstance(preview, dict)
    [job] = preview["jobs"]
    # 有人在 Job 頁按了刪除（只收成 removed，什麼檔案都不動）。
    await delete_job(session, FakeClientFactory(), job["hash"], DeleteScope(), actor="7")

    decided = await asked.runs.confirm(card_id(asked.card), user=asked.admin)

    assert refusal_of(decided)[0] == DeletionRefusal.NOTHING_TO_DELETE
    assert len(alive(await sources(session))) == SOURCES


async def test_a_card_is_pressed_once(engine: AsyncEngine, session: AsyncSession) -> None:
    asked = await indexer_asked(engine, session)
    await asked.runs.confirm(card_id(asked.card), user=asked.admin)

    with pytest.raises(ProposalRejectedError) as again:
        await asked.runs.reject(card_id(asked.card), user=asked.admin)

    assert again.value.reason is ProposalRefusal.ALREADY_DECIDED
    assert asked.prowlarr.add_attempts == ["nyaasi"]


# --- 誰按得到 ---------------------------------------------------------------------------


async def test_someone_else_cannot_press_the_card(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    """只有要它的那個人按得到（2026-10-24 使用者選定）；別人的與不存在的說同一句。"""
    asked = await indexer_asked(engine, session)
    deckhand = await person(session, "deckhand", Role.USER)

    for decide in (asked.runs.confirm, asked.runs.reject):
        with pytest.raises(ProposalRejectedError) as refused:
            await decide(card_id(asked.card), user=deckhand)
        assert refused.value.reason is ProposalRefusal.PROPOSAL_MISSING

    assert asked.prowlarr.add_attempts == []
    async with create_session_factory(engine)() as fresh:
        [card] = await of_conversation(
            fresh, user_id=asked.admin.id, conversation_id=asked.conversation
        )
    assert card.status is ProposalStatus.PROPOSED


async def test_a_user_is_never_offered_the_administrator_tools(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    """`user` 連卡片都提不出來：兩個工具指著管理員的端點，清單上沒有它們。"""
    deckhand = await person(session, "deckhand", Role.USER)
    await ai_ready(session)
    provider = FakeChatProvider(
        replies=[asks("add_indexer", site="nyaasi", reason="For anime."), says("No.")]
    )
    runs = AssistantRuns(
        create_session_factory(engine), FakeClientFactory(ai=provider), now=lambda: NOW
    )

    events = await drain(runs, deckhand, "add nyaa")

    assert [spec.name for spec in provider.requests[0].tools] == []
    [finished] = [event for event in events if isinstance(event, ToolFinished)]
    assert finished.result.outcome is ToolOutcome.REFUSED
    assert finished.result.result["reason"] == ToolRefusal.UNKNOWN_TOOL
