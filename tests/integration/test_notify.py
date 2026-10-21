"""「可以看了」送到管理員的 Discord（M4 票 123，plan §11.5〈通知〉）。

起點與 `test_resolver.py` 相同：importer 真的跑完的一筆 Job（SPY×FAMILY S01E01–E03，Route
`Anime`），替身 Jellyfin 掃到了它。斷言只看兩個公開的接縫：resolver 的一輪
（`sweep_resolutions`）寫下什麼，與送出的一輪（`send_due`）交給 Discord 什麼。
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.jellyfin.fake import account_id
from berth.adapters.notify import Delivery, Link
from berth.domain import (
    DeliveryFailure,
    JobState,
    JobTrigger,
    Language,
    MediaKind,
    NotificationKind,
    PlanAction,
    Role,
)
from berth.models import BerthSettings, Job, LedgerEntry, Media, NotifySettings, User, media_id
from berth.services.notify import MERGE_WINDOW, backoff, queue_ready, send_due
from berth.services.settings import write_settings
from tests.integration.factories import FakeClientFactory
from tests.integration.test_plan import NOW, ready
from tests.integration.test_resolver import FIRST, imported, resolve, scanned

pytestmark = pytest.mark.asyncio

TOKEN = "bot-token"
ADMIN_ID = "100000000000000001"
SECOND_ADMIN_ID = "100000000000000002"
CREW_ID = "100000000000000003"
SECOND_CREW_ID = "100000000000000004"
#: Route `Anime` 的媒體庫（`tests/integration/arrange.bundled_libraries` 的第三個），與另外兩個。
ANIME, MOVIES, TV = "item-2", "item-0", "item-1"


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
    kinds: tuple[NotificationKind, ...] = (NotificationKind.READY,),
) -> User:
    """`users` 的一列，對上替身 Jellyfin 的同名帳號（`found` 把每一位登記進去）。"""
    user = User(
        jellyfin_user_id=account_id(name),
        name=name,
        role=role,
        discord_user_id=discord,
        notify_language=language,
        notify_kinds_json=[kind.value for kind in kinds],
    )
    session.add(user)
    await session.flush()
    return user


async def found(
    session: AsyncSession,
    roots: dict[str, Path],
    *,
    folders: dict[str, tuple[str, ...]] | None = None,
) -> FakeClientFactory:
    """這一筆在 Jellyfin 全部認出來的那一輪跑完、commit 了。

    `users` 上的每一位都是替身 Jellyfin 的帳號；`folders` 是帳號 → 他看得到的媒體庫（沒列的看得到
    全部，同 Jellyfin 的「所有媒體庫」）。Route `Anime` 在媒體庫 `ANIME`。
    """
    route, factory = await imported(session, roots)
    for user in await session.scalars(select(User)):
        factory.jellyfin_.users[user.name] = "secret"
    factory.jellyfin_.folders.update(folders or {})
    await scanned(session, route, factory)
    await resolve(session, factory, FIRST)
    return factory


async def deliver(
    session: AsyncSession, factory: FakeClientFactory, *, later: timedelta = MERGE_WINDOW
) -> None:
    """送一輪。預設在這一筆的合併時間剛過的那一刻：寫入時的最早送出時間是 5 分鐘後。"""
    await send_due(session, factory, now=NOW + FIRST + later)


class TestReady:
    async def test_everyone_subscribed_with_a_discord_id_gets_one_message(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """不只管理員（M4 票 125）：一般使用者也收，各用自己的語言。"""
        await with_bot(session)
        await person(session, "skipper", discord=ADMIN_ID)
        await person(session, "bosun", discord=SECOND_ADMIN_ID, language=Language.EN)
        await person(session, "deckhand", role=Role.USER, discord=CREW_ID)
        await person(session, "quiet")
        factory = await found(session, roots)

        await deliver(session, factory)

        sent = dict(factory.discord_.sent)
        assert set(sent) == {ADMIN_ID, SECOND_ADMIN_ID, CREW_ID}
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


class TestRecipients:
    """收件人：訂閱了「可以看了」、有 Discord ID、Jellyfin `UserViews` 看得到那筆 Job 的媒體庫
    （M4 票 125，plan §11.5〈通知〉）。M1.5 的受限使用者不能從 Discord 這一側看到別的媒體庫的
    作品名。"""

    async def test_a_user_who_cannot_see_the_library_gets_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await with_bot(session)
        await person(session, "deckhand", role=Role.USER, discord=CREW_ID)
        await person(session, "lookout", role=Role.USER, discord=SECOND_CREW_ID)
        factory = await found(
            session, roots, folders={"deckhand": (MOVIES, TV), "lookout": (ANIME,)}
        )

        await deliver(session, factory)
        # 擋下的那一則不是「下一輪再送」：再一輪也沒有。
        await deliver(session, factory, later=MERGE_WINDOW * 2)

        assert [recipient for recipient, _ in factory.discord_.sent] == [SECOND_CREW_ID]

    async def test_an_admin_is_held_to_the_same_library_rule(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """角色不算數，算的是 Jellyfin 給他開了哪些媒體庫。"""
        await with_bot(session)
        await person(session, "skipper", discord=ADMIN_ID)
        factory = await found(session, roots, folders={"skipper": (MOVIES,)})

        await deliver(session, factory)

        assert factory.discord_.sent == []

    async def test_without_the_subscription_or_a_discord_id_nothing_is_sent(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await with_bot(session)
        await person(session, "skipper", discord=ADMIN_ID, kinds=())
        await person(
            session, "bosun", discord=SECOND_ADMIN_ID, kinds=(NotificationKind.DOWNLOADING,)
        )
        await person(session, "deckhand", role=Role.USER)
        await person(session, "lookout", role=Role.USER, discord=SECOND_CREW_ID)
        factory = await found(session, roots)

        await deliver(session, factory)

        assert [recipient for recipient, _ in factory.discord_.sent] == [SECOND_CREW_ID]

    async def test_unreadable_user_views_hold_the_message_until_jellyfin_answers(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Jellyfin 掛了就不知道他看不看得到：不猜（不送），也不丟（之後照送）。"""
        await with_bot(session)
        await person(session, "deckhand", role=Role.USER, discord=CREW_ID)
        factory = await found(session, roots)
        factory.jellyfin_.error = ServiceUnavailableError("GET /UserViews: connection refused")

        await deliver(session, factory)
        await deliver(session, factory, later=MERGE_WINDOW + timedelta(minutes=10))
        assert factory.discord_.sent == []

        factory.jellyfin_.error = None
        await deliver(session, factory, later=MERGE_WINDOW + timedelta(minutes=20))
        assert [recipient for recipient, _ in factory.discord_.sent] == [CREW_ID]

    async def test_a_disabled_jellyfin_account_gets_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """停用的帳號 `UserViews` 照樣讀得到（研究 library-browsing.md §2），只有 `Policy`
        說得出來。"""
        await with_bot(session)
        await person(session, "deckhand", role=Role.USER, discord=CREW_ID)
        factory = await found(session, roots)
        factory.jellyfin_.disabled.add("deckhand")

        await deliver(session, factory)

        assert factory.discord_.sent == []


class TestMerge:
    """同一個收件人、同一部作品 5 分鐘內的幾筆合成一則，季集範圍合起來（M4 票 125）。"""

    async def test_two_jobs_within_five_minutes_are_one_message(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await with_bot(session)
        await person(session, "skipper", discord=ADMIN_ID)
        await person(session, "deckhand", role=Role.USER, discord=CREW_ID)
        factory = await found(session, roots)
        await queue_ready(
            session, await next_job(session, (4, 5)), now=NOW + FIRST + timedelta(minutes=4)
        )
        await session.commit()

        await deliver(session, factory)
        await deliver(session, factory, later=MERGE_WINDOW + timedelta(minutes=4))

        sent = dict(factory.discord_.sent)
        assert len(factory.discord_.sent) == 2
        assert sent[ADMIN_ID].description == "S01E01–E05"
        assert sent[CREW_ID].description == "S01E01–E05"

    async def test_a_job_after_five_minutes_is_a_second_message(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await with_bot(session)
        await person(session, "skipper", discord=ADMIN_ID)
        factory = await found(session, roots)
        await queue_ready(session, await next_job(session, (5,)), now=NOW + FIRST + MERGE_WINDOW)
        await session.commit()

        await deliver(session, factory)
        await deliver(session, factory, later=MERGE_WINDOW * 2)

        assert [message.description for _, message in factory.discord_.sent] == [
            "S01E01–E03",
            "S01E05",
        ]

    async def test_a_message_about_to_be_sent_is_not_merged_into(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """最後 30 秒不併（`_MERGE_GUARD`）：送出迴圈讀完就放開交易去打 Discord，併進它撿走的
        那一則，新的季集會跟著舊內容一起被標成已送，哪裡都看不到。"""
        await with_bot(session)
        await person(session, "skipper", discord=ADMIN_ID)
        factory = await found(session, roots)
        await queue_ready(
            session,
            await next_job(session, (5,)),
            now=NOW + FIRST + MERGE_WINDOW - timedelta(seconds=20),
        )
        await session.commit()

        await deliver(session, factory, later=MERGE_WINDOW * 2)

        assert sorted(message.description for _, message in factory.discord_.sent) == [
            "S01E01–E03",
            "S01E05",
        ]


async def next_job(session: AsyncSession, episodes: tuple[int, ...]) -> Job:
    """同一部作品、同一條 Route 的下一筆：S01 的這幾集各一列帳本。"""
    first = await session.scalar(select(Job))
    assert first is not None
    job = Job(
        hash="c" * 40,
        name="[Sub] SPY x FAMILY - batch 2",
        trigger=JobTrigger.RSS,
        media_id=first.media_id,
        route_id=first.route_id,
        state=JobState.IMPORTED,
    )
    session.add(job)
    for episode in episodes:
        session.add(
            LedgerEntry(
                job_hash=job.hash,
                source_rel_path=f"e{episode}.mkv",
                source_abs_path=f"/downloads/e{episode}.mkv",
                source_dev="1",
                target_path=f"/library/anime/e{episode}.mkv",
                target_inode=str(1000 + episode),
                media_id=first.media_id,
                season=1,
                episode_start=episode,
                action=PlanAction.IMPORT,
            )
        )
    await session.flush()
    return job


class TestLink:
    """「可以看了」連到作品頁（M4 票 124）：Berth 的網址存了才有，沒存照送、不附。"""

    async def test_the_message_links_to_the_media_page_on_the_saved_address(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await with_bot(session)
        await person(session, "skipper", discord=ADMIN_ID)
        factory = await found(session, roots)
        # 寫進待送表之後才存：連結在送出時組，已經排著的那幾則也帶得到。
        await write_settings(session, BerthSettings(public_url="https://berth.example.com"))
        await session.commit()

        await deliver(session, factory)

        ((_, message),) = factory.discord_.sent
        assert message.links == (
            Link("在 Berth 打開", "https://berth.example.com/media/tv:120089"),
        )

    async def test_without_an_address_the_message_is_sent_without_a_link(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await with_bot(session)
        await person(session, "skipper", discord=ADMIN_ID)
        factory = await found(session, roots)

        await deliver(session, factory)

        ((_, message),) = factory.discord_.sent
        assert message.links == ()
        assert "SPY×FAMILY 間諜家家酒" in message.title


class TestMovie:
    async def test_a_movie_says_the_title_and_route_without_episodes(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """「電影只說作品」：沒有季集那一行，Route 照說。"""
        await with_bot(session)
        await person(session, "skipper", discord=ADMIN_ID)
        _, route, factory = await ready(session, roots)
        factory.jellyfin_.users["skipper"] = "secret"
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

        # 管道退避過去之後（票 128）。
        await deliver(session, factory, later=MERGE_WINDOW + backoff(1))
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

        # `retry_after` 過去之後（票 128）。
        await deliver(session, factory, later=MERGE_WINDOW + timedelta(seconds=1))
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
