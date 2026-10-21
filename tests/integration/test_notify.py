"""「可以看了」送到管理員的 Discord（M4 票 123，plan §11.5〈通知〉）。

起點與 `test_resolver.py` 相同：importer 真的跑完的一筆 Job（SPY×FAMILY S01E01–E03，Route
`Anime`），替身 Jellyfin 掃到了它。斷言只看兩個公開的接縫：resolver 的一輪
（`sweep_resolutions`）寫下什麼，與送出的一輪（`send_due`）交給 Discord 什麼。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.notify import Delivery
from berth.domain import DeliveryFailure, JobState, JobTrigger, Language, MediaKind, Role
from berth.models import Job, Media, NotifySettings, User, media_id
from berth.services.notify import queue_ready, send_due
from berth.services.settings import write_settings
from tests.integration.factories import FakeClientFactory
from tests.integration.test_plan import NOW, ready
from tests.integration.test_resolver import FIRST, imported, resolve, scanned

pytestmark = pytest.mark.asyncio

TOKEN = "bot-token"
ADMIN_ID = "100000000000000001"
SECOND_ADMIN_ID = "100000000000000002"


async def with_bot(session: AsyncSession) -> None:
    await write_settings(
        session,
        NotifySettings(
            discord_bot_token=TOKEN, discord_application_id="42", discord_bot_name="berth"
        ),
    )


async def person(
    session: AsyncSession,
    name: str,
    *,
    role: Role = Role.ADMIN,
    discord: str = "",
    language: Language = Language.ZH_HANT,
) -> User:
    user = User(
        jellyfin_user_id=f"jf-{name}",
        name=name,
        role=role,
        discord_user_id=discord,
        notify_language=language,
    )
    session.add(user)
    await session.flush()
    return user


async def found(session: AsyncSession, roots: dict[str, Path]) -> FakeClientFactory:
    """這一筆在 Jellyfin 全部認出來的那一輪跑完、commit 了。"""
    route, factory = await imported(session, roots)
    await scanned(session, route, factory)
    await resolve(session, factory, FIRST)
    return factory


async def deliver(session: AsyncSession, factory: FakeClientFactory) -> None:
    await send_due(session, factory, now=NOW + FIRST)


class TestReady:
    async def test_every_admin_with_a_discord_id_gets_one_message(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await with_bot(session)
        await person(session, "skipper", discord=ADMIN_ID)
        await person(session, "bosun", discord=SECOND_ADMIN_ID, language=Language.EN)
        await person(session, "deckhand", role=Role.USER, discord="100000000000000003")
        await person(session, "quiet")
        factory = await found(session, roots)

        await deliver(session, factory)

        sent = dict(factory.discord_.sent)
        assert set(sent) == {ADMIN_ID, SECOND_ADMIN_ID}
        assert factory.discord_.token == TOKEN

        zh = sent[ADMIN_ID]
        assert "SPY×FAMILY 間諜家家酒" in zh.title
        assert "S01E01–E03" in zh.description
        assert ("Route", "Anime") in zh.fields

        en = sent[SECOND_ADMIN_ID]
        assert "SPY x FAMILY" in en.title
        assert "S01E01–E03" in en.description
        assert ("Route", "Anime") in en.fields

    async def test_a_sent_message_is_not_sent_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await with_bot(session)
        await person(session, "skipper", discord=ADMIN_ID)
        factory = await found(session, roots)

        await deliver(session, factory)
        await deliver(session, factory)

        assert len(factory.discord_.sent) == 1

    async def test_a_rolled_back_resolution_leaves_no_notification(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """寫通知與寫 `jellyfin_item_resolved` 是同一筆交易：觸發它的那一筆沒有落地，就沒有通知。"""
        await with_bot(session)
        await person(session, "skipper", discord=ADMIN_ID)
        route, factory = await imported(session, roots)
        await scanned(session, route, factory)
        await session.commit()

        failing = FailingCommit(session)
        with pytest.raises(RuntimeError):
            await resolve(failing, factory, FIRST)  # type: ignore[arg-type]  # 只換掉 commit
        await session.rollback()

        await deliver(session, factory)
        assert factory.discord_.sent == []


class TestMovie:
    async def test_a_movie_says_the_title_and_route_without_episodes(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """「電影只說作品」：沒有季集那一行，Route 照說。"""
        await with_bot(session)
        await person(session, "skipper", discord=ADMIN_ID)
        _, route, factory = await ready(session, roots)
        movie = Media(
            id=media_id(MediaKind.MOVIE, 27205),
            tmdb_id=27205,
            kind=MediaKind.MOVIE,
            title_en="Inception",
            title_original="Inception",
            year=2010,
            folder_name="Inception (2010)",
        )
        session.add(movie)
        await session.flush()
        job = Job(
            hash="b" * 40,
            name="Inception.2010.1080p.BluRay",
            trigger=JobTrigger.MANUAL,
            media_id=movie.id,
            route_id=route.id,
            state=JobState.IMPORTED,
        )
        session.add(job)
        await session.flush()

        await queue_ready(session, job, now=NOW)
        await session.commit()
        await deliver(session, factory)

        ((_, message),) = factory.discord_.sent
        assert message.title == "可以看了：Inception"
        assert message.description == ""
        assert message.fields == (("Route", "Anime"),)


class TestSending:
    async def test_a_discord_outage_keeps_the_message_for_the_next_round(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await with_bot(session)
        await person(session, "skipper", discord=ADMIN_ID)
        factory = await found(session, roots)
        factory.discord_.failures.append(
            Delivery(failure=DeliveryFailure.UNAVAILABLE, detail="POST /channels/2/messages: 502")
        )

        await deliver(session, factory)
        assert factory.discord_.sent == []

        await deliver(session, factory)
        assert [recipient for recipient, _ in factory.discord_.sent] == [ADMIN_ID]

    async def test_a_channel_failure_stops_the_round(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Discord 這一刻送不出任何一則時，後面的不再送：限速時失敗的請求也扣額度（brief §20.23），
        連送只會把每一則的次數灌高。收件人那一層的失敗（下一條）不算。"""
        await with_bot(session)
        await person(session, "skipper", discord=ADMIN_ID)
        await person(session, "bosun", discord=SECOND_ADMIN_ID)
        factory = await found(session, roots)
        factory.discord_.failures.append(
            Delivery(failure=DeliveryFailure.RATE_LIMITED, detail="429", retry_after=0.3)
        )

        await deliver(session, factory)
        assert factory.discord_.sent == []

        await deliver(session, factory)
        assert {recipient for recipient, _ in factory.discord_.sent} == {ADMIN_ID, SECOND_ADMIN_ID}

    async def test_an_unreachable_recipient_does_not_hold_up_the_next_one(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await with_bot(session)
        await person(session, "skipper", discord=ADMIN_ID)
        await person(session, "bosun", discord=SECOND_ADMIN_ID)
        factory = await found(session, roots)
        factory.discord_.unreachable.add(ADMIN_ID)

        await deliver(session, factory)

        assert [recipient for recipient, _ in factory.discord_.sent] == [SECOND_ADMIN_ID]

    async def test_nothing_is_sent_without_a_bot(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """沒設 token 時寫下的那幾則留著，設好之後的那一輪送出。"""
        await person(session, "skipper", discord=ADMIN_ID)
        factory = await found(session, roots)

        await deliver(session, factory)
        assert factory.discord_.sent == []

        await with_bot(session)
        await session.commit()
        await deliver(session, factory)
        assert [recipient for recipient, _ in factory.discord_.sent] == [ADMIN_ID]


class FailingCommit:
    """一個 commit 就爆的 session：其餘照轉給真的那一個。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        raise RuntimeError("disk full")

    def __getattr__(self, name: str) -> object:
        return getattr(self._session, name)
