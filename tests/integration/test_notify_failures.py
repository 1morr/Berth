"""管道故障：重試、放棄、健康頁（M4 票 128，plan §11.5〈通知〉的「故障」）。

待送表上直接擺好要送的那幾則，斷言只看兩個公開的接縫：送出的一輪（`send_due`）之後待送表、
收件人與管道各記下什麼，以及畫面讀的兩份（`read_mine`、`read_bot`、`read_channel`）怎麼說。

429 那一組吃票 121 錄下來的回應（`tests/fixtures/http/discord/`），走真的 `HttpDiscordBot`；
其餘用替身排好每一則的結果。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.jellyfin import JellyfinLibrary
from berth.adapters.jellyfin.fake import FakeJellyfinClient, account_id
from berth.adapters.notify import Delivery, DiscordBot
from berth.adapters.notify.discord import HttpDiscordBot
from berth.config import DEFAULT_DISCORD_API_URL
from berth.domain import (
    DeliveryFailure,
    EventType,
    Language,
    NotificationKind,
    NotificationStatus,
    Role,
)
from berth.models import Notification, NotifySettings, User
from berth.services import notify
from berth.services.notify import (
    GIVE_UP_AFTER,
    backoff,
    read_bot,
    read_channel,
    read_mine,
    send_due,
    send_test,
    set_bot_token,
    set_mine,
)
from berth.services.settings import write_settings
from tests.conftest import read_fixture
from tests.integration.factories import FakeClientFactory
from tests.integration.test_plan import NOW, events_of
from tests.integration.test_resolver import FIRST, imported, resolve, scanned

pytestmark = pytest.mark.asyncio

TOKEN = "bot-token"
NEW_TOKEN = "bot-token-after-reset"
ADMIN_ID = "100000000000000001"
SECOND_ADMIN_ID = "100000000000000002"
CHANNEL = "000000000000000002"
CONTENT: dict[str, Any] = {
    "media": "tv:120089",
    "kind": "tv",
    "title": "SPY×FAMILY 間諜家家酒",
    "title_en": "SPY x FAMILY",
    "route": "Anime",
    "library": "item-2",
    "episodes": [[1, 1, 3]],
}

OUTAGE = Delivery(failure=DeliveryFailure.UNAVAILABLE, detail="POST /channels/2/messages: 502")
UNAUTHORIZED = Delivery(failure=DeliveryFailure.UNAUTHORIZED, detail="401 code=0 401: Unauthorized")


async def with_bot(session: AsyncSession, token: str = TOKEN) -> None:
    await write_settings(
        session,
        NotifySettings(
            discord_bot_token=token, discord_application_id="42", discord_bot_name="berth"
        ),
    )
    await session.commit()


async def person(session: AsyncSession, name: str, discord: str) -> User:
    user = User(
        jellyfin_user_id=account_id(name),
        name=name,
        role=Role.ADMIN,
        discord_user_id=discord,
        notify_language=Language.ZH_HANT,
    )
    session.add(user)
    await session.flush()
    return user


def crew() -> FakeJellyfinClient:
    """`person` 擺的人都是這台 Jellyfin 的帳號、看得到全部媒體庫（`CONTENT` 的 `item-2` 在裡面）：
    這一檔講的是管道，收件人的權限在 `test_notify.py`（M4 票 125）。"""
    jellyfin = FakeJellyfinClient(
        startup_wizard_completed=True,
        users={"skipper": "harbour", "bosun": "rope"},
        libraries=(
            JellyfinLibrary(
                name="Anime",
                item_id="item-2",
                collection_type="tvshows",
                locations=("/data/library/anime",),
                type_options=(),
            ),
        ),
    )
    # 送出迴圈帶 `JellyfinSettings.api_key` 問；這一檔沒寫設定，替身先拿著一把。
    jellyfin.use_token("key")
    return jellyfin


async def queued(
    session: AsyncSession,
    user: User,
    *,
    at: datetime = NOW,
    content: dict[str, Any] | None = None,
) -> Notification:
    row = Notification(
        user_id=user.id,
        kind=NotificationKind.READY,
        content_json=content if content is not None else CONTENT,
        merge_key="tv:120089",
        not_before=at,
        created_at=at,
    )
    session.add(row)
    await session.commit()
    return row


async def fresh(session: AsyncSession, row: Notification) -> Notification:
    await session.refresh(row)
    return row


def recipients(factory: FakeClientFactory) -> list[str]:
    return [recipient for recipient, _ in factory.discord_.sent]


# --- 429 --------------------------------------------------------------------


def recorded(name: str, **body: Any) -> httpx.Response:
    """票 121 錄的一份回應；`body` 改其中幾格（只用在 Discord 沒錄到的變體上，見用到的那一條）。"""
    record: dict[str, Any] = json.loads(read_fixture(f"http/discord/{name}.json"))
    transport = {"content-length", "transfer-encoding", "connection"}
    headers = {k: v for k, v in record["headers"].items() if k.lower() not in transport}
    return httpx.Response(record["status"], json={**record["body"], **body}, headers=headers)


class HttpFactory(FakeClientFactory):
    """其餘照替身，Discord 換成真的 adapter（對 respx 擺好的錄製回應）。"""

    def discord(self, token: str) -> DiscordBot:
        return HttpDiscordBot(token)


def discord_answers(*answers: httpx.Response) -> respx.Route:
    respx.post(f"{DEFAULT_DISCORD_API_URL}/users/@me/channels").mock(
        return_value=recorded("users-me-channels.created")
    )
    return respx.post(f"{DEFAULT_DISCORD_API_URL}/channels/{CHANNEL}/messages").mock(
        side_effect=list(answers)
    )


class TestRateLimit:
    @respx.mock
    async def test_a_rate_limited_message_waits_for_its_retry_after(
        self, session: AsyncSession
    ) -> None:
        """錄下來的 `429`：body 的 `retry_after` 0.3 秒，`global` 是 false——只延後那一則。"""
        await with_bot(session)
        row = await queued(session, await person(session, "skipper", ADMIN_ID))
        sent = discord_answers(
            recorded("channels-messages.rate-limited"), recorded("channels-messages.embed")
        )
        factory = HttpFactory(jellyfin=crew())

        await send_due(session, factory, now=NOW)
        row = await fresh(session, row)
        assert row.status is NotificationStatus.PENDING
        assert row.retry_at == NOW + timedelta(seconds=0.3)
        assert "429" in row.error

        # 還沒到 `retry_at` 的那一輪不送。
        await send_due(session, factory, now=NOW + timedelta(seconds=0.2))
        assert sent.call_count == 1

        await send_due(session, factory, now=NOW + timedelta(seconds=0.3))
        assert (await fresh(session, row)).status is NotificationStatus.SENT
        assert sent.call_count == 2

    @respx.mock
    async def test_a_global_rate_limit_holds_the_whole_channel(self, session: AsyncSession) -> None:
        """`global: true` 的 429（Discord 文件 Rate Limits；票 121 沒量到，從錄的那一份翻
        `global`）：整個管道等 `retry_after`，排在後面、自己沒被限速的那一則也等。"""
        await with_bot(session)
        skipper = await person(session, "skipper", ADMIN_ID)
        first = await queued(session, skipper)
        second = await queued(session, skipper)
        sent = discord_answers(
            recorded("channels-messages.rate-limited", retry_after=4.5, **{"global": True}),
            recorded("channels-messages.embed"),
            recorded("channels-messages.embed"),
        )
        factory = HttpFactory(jellyfin=crew())

        await send_due(session, factory, now=NOW)
        await send_due(session, factory, now=NOW + timedelta(seconds=4))
        assert sent.call_count == 1
        assert (await read_channel(session)).resume_at == NOW + timedelta(seconds=4.5)

        await send_due(session, factory, now=NOW + timedelta(seconds=4.5))
        assert (await fresh(session, first)).status is NotificationStatus.SENT
        assert (await fresh(session, second)).status is NotificationStatus.SENT


# --- 5xx 與連不上 --------------------------------------------------------------


class TestOutage:
    async def test_an_outage_backs_off_the_whole_channel(self, session: AsyncSession) -> None:
        await with_bot(session)
        row = await queued(session, await person(session, "skipper", ADMIN_ID))
        factory = FakeClientFactory(jellyfin=crew())
        factory.discord_.failures.extend([OUTAGE, OUTAGE])

        await send_due(session, factory, now=NOW)
        channel = await read_channel(session)
        assert channel.failures == 1
        assert channel.resume_at == NOW + backoff(1)
        assert "502" in channel.error

        # 退避中的那幾輪一個請求都不發。
        await send_due(session, factory, now=NOW + backoff(1) - timedelta(seconds=1))
        assert len(factory.discord_.failures) == 1

        await send_due(session, factory, now=NOW + backoff(1))
        assert (await read_channel(session)).resume_at == NOW + backoff(1) + backoff(2)

        await send_due(session, factory, now=NOW + backoff(1) + backoff(2))
        assert (await fresh(session, row)).status is NotificationStatus.SENT
        channel = await read_channel(session)
        assert (channel.failures, channel.error, channel.resume_at) == (0, "", None)
        assert channel.last_sent_at == NOW + backoff(1) + backoff(2)

    async def test_backoff_doubles_up_to_an_hour(self) -> None:
        assert [backoff(n) for n in (1, 2, 3)] == [
            timedelta(seconds=30),
            timedelta(minutes=1),
            timedelta(minutes=2),
        ]
        assert backoff(8) == timedelta(hours=1)
        assert backoff(40) == timedelta(hours=1)

    async def test_a_message_still_unsent_after_the_limit_is_given_up_with_its_reason(
        self, session: AsyncSession
    ) -> None:
        await with_bot(session)
        row = await queued(session, await person(session, "skipper", ADMIN_ID))
        factory = FakeClientFactory(jellyfin=crew())
        factory.discord_.failures.append(OUTAGE)

        await send_due(session, factory, now=NOW)
        await send_due(session, factory, now=NOW + GIVE_UP_AFTER)

        row = await fresh(session, row)
        assert row.status is NotificationStatus.ABANDONED
        assert "expired" in row.error
        assert "502" in row.error, "放棄時留下上一次沒送到的原因"
        assert factory.discord_.sent == []

    async def test_a_message_just_inside_the_limit_is_still_sent(
        self, session: AsyncSession
    ) -> None:
        await with_bot(session)
        row = await queued(session, await person(session, "skipper", ADMIN_ID))
        factory = FakeClientFactory(jellyfin=crew())
        factory.discord_.failures.append(OUTAGE)

        await send_due(session, factory, now=NOW)
        await send_due(session, factory, now=NOW + GIVE_UP_AFTER - timedelta(seconds=1))

        assert (await fresh(session, row)).status is NotificationStatus.SENT

    async def test_messages_queued_without_a_bot_are_given_up_after_the_limit(
        self, session: AsyncSession
    ) -> None:
        """票 123 的 code-review 留下的：沒設 token 時寫下的那幾則，隔了幾天才設好，
        不該一次全送出去。"""
        stale = await queued(session, await person(session, "skipper", ADMIN_ID))
        factory = FakeClientFactory(jellyfin=crew())
        await send_due(session, factory, now=NOW)

        await with_bot(session)
        await send_due(session, factory, now=NOW + timedelta(days=3))

        stale = await fresh(session, stale)
        assert stale.status is NotificationStatus.ABANDONED
        assert "not sent" in stale.error
        assert factory.discord_.sent == []


# --- 收件人那一層 ---------------------------------------------------------------


class TestRecipient:
    async def test_an_unreachable_recipient_gives_up_that_message_and_says_why_on_their_page(
        self, session: AsyncSession
    ) -> None:
        await with_bot(session)
        skipper = await person(session, "skipper", ADMIN_ID)
        bosun = await person(session, "bosun", SECOND_ADMIN_ID)
        lost = await queued(session, skipper)
        await queued(session, bosun)
        factory = FakeClientFactory(jellyfin=crew())
        factory.discord_.unreachable.add(ADMIN_ID)

        await send_due(session, factory, now=NOW)

        lost = await fresh(session, lost)
        assert lost.status is NotificationStatus.ABANDONED
        assert "50278" in lost.error
        assert recipients(factory) == [SECOND_ADMIN_ID]

        view = await read_mine(session, skipper.id)
        assert view.unreachable_at == NOW
        assert "50278" in view.unreachable_detail
        assert (await read_mine(session, bosun.id)).unreachable_at is None
        # 不是管道的事：其他人照送，健康頁不變。
        assert (await read_channel(session)).failures == 0

        # 下一輪不再試那一則。
        await send_due(session, factory, now=NOW + timedelta(minutes=1))
        assert recipients(factory) == [SECOND_ADMIN_ID]

    async def test_the_next_delivery_clears_the_note(self, session: AsyncSession) -> None:
        await with_bot(session)
        skipper = await person(session, "skipper", ADMIN_ID)
        await queued(session, skipper)
        factory = FakeClientFactory(jellyfin=crew())
        factory.discord_.unreachable.add(ADMIN_ID)
        await send_due(session, factory, now=NOW)

        factory.discord_.unreachable.clear()
        await queued(session, skipper, at=NOW + timedelta(hours=1))
        await send_due(session, factory, now=NOW + timedelta(hours=1))

        assert (await read_mine(session, skipper.id)).unreachable_at is None

    async def test_a_delivered_test_message_clears_the_note(self, session: AsyncSession) -> None:
        """補好之後按「測試」就是驗證：送到了，那一句就收掉。"""
        await with_bot(session)
        skipper = await person(session, "skipper", ADMIN_ID)
        await queued(session, skipper)
        factory = FakeClientFactory(jellyfin=crew())
        factory.discord_.unreachable.add(ADMIN_ID)
        await send_due(session, factory, now=NOW)

        factory.discord_.unreachable.clear()
        assert (await send_test(session, factory, skipper.id)).delivered

        assert (await read_mine(session, skipper.id)).unreachable_at is None

    async def test_an_undelivered_test_message_leaves_the_same_note(
        self, session: AsyncSession
    ) -> None:
        await with_bot(session)
        skipper = await person(session, "skipper", ADMIN_ID)
        await session.commit()
        factory = FakeClientFactory(jellyfin=crew())
        factory.discord_.unreachable.add(ADMIN_ID)

        await send_test(session, factory, skipper.id)

        assert (await read_mine(session, skipper.id)).unreachable_at is not None

    async def test_a_new_discord_id_clears_the_note(self, session: AsyncSession) -> None:
        await with_bot(session)
        skipper = await person(session, "skipper", ADMIN_ID)
        await queued(session, skipper)
        factory = FakeClientFactory(jellyfin=crew())
        factory.discord_.unreachable.add(ADMIN_ID)
        await send_due(session, factory, now=NOW)

        await set_mine(session, skipper.id, ADMIN_ID, Language.ZH_HANT, [NotificationKind.READY])
        assert (await read_mine(session, skipper.id)).unreachable_at is not None, "同一個 ID"

        await set_mine(
            session, skipper.id, SECOND_ADMIN_ID, Language.ZH_HANT, [NotificationKind.READY]
        )
        assert (await read_mine(session, skipper.id)).unreachable_at is None

    async def test_a_rejected_message_is_given_up_at_once(self, session: AsyncSession) -> None:
        """`400` / `50035`（超長）再送也一樣：當場放棄，不擋下一則。"""
        await with_bot(session)
        skipper = await person(session, "skipper", ADMIN_ID)
        rejected = await queued(session, skipper)
        await queued(session, skipper)
        factory = FakeClientFactory(jellyfin=crew())
        factory.discord_.failures.append(
            Delivery(failure=DeliveryFailure.REJECTED, detail="400 code=50035 Invalid Form Body")
        )

        await send_due(session, factory, now=NOW)

        rejected = await fresh(session, rejected)
        assert rejected.status is NotificationStatus.ABANDONED
        assert "50035" in rejected.error
        assert recipients(factory) == [ADMIN_ID]
        assert (await read_mine(session, skipper.id)).unreachable_at is None


# --- token 失效 ---------------------------------------------------------------


class TestToken:
    async def test_a_rejected_token_pauses_the_channel_until_a_new_one(
        self, session: AsyncSession
    ) -> None:
        await with_bot(session)
        skipper = await person(session, "skipper", ADMIN_ID)
        row = await queued(session, skipper)
        factory = FakeClientFactory(jellyfin=crew())
        factory.discord_.rejected_tokens.add(TOKEN)

        await send_due(session, factory, now=NOW)
        channel = await read_channel(session)
        assert channel.token_rejected
        assert "401" in channel.error
        assert (await read_bot(session)).token_rejected

        # 暫停中一個請求都不發（替身這時已經不拒了，送得出去的話就會送）。
        factory.discord_.rejected_tokens.clear()
        await send_due(session, factory, now=NOW + timedelta(hours=1))
        assert factory.discord_.sent == []

        await set_bot_token(session, factory, NEW_TOKEN)
        assert not (await read_channel(session)).token_rejected

        await send_due(session, factory, now=NOW + timedelta(hours=2))
        assert (await fresh(session, row)).status is NotificationStatus.SENT
        assert factory.discord_.token == NEW_TOKEN

    async def test_a_rejection_of_the_old_token_does_not_pause_the_new_one(
        self, session: AsyncSession
    ) -> None:
        """送的那幾秒裡管理員換了 token：舊的那一把被拒，記下的是舊的那一把，新的照送。"""
        await with_bot(session)
        skipper = await person(session, "skipper", ADMIN_ID)
        await queued(session, skipper)
        factory = FakeClientFactory(jellyfin=crew())

        class SwappedMidSend:
            async def send(self, recipient: str, message: object) -> Delivery:
                await with_bot(session, NEW_TOKEN)
                return UNAUTHORIZED

        factory.discord = lambda token: SwappedMidSend()  # type: ignore[method-assign,assignment,return-value]  # 只換這一次的 bot

        await send_due(session, factory, now=NOW)

        assert not (await read_channel(session)).token_rejected

    async def test_a_test_message_refused_for_the_token_marks_it(
        self, session: AsyncSession
    ) -> None:
        """存的那一刻 token 是好的（`set_bot_token` 先問過），之後在 Discord 被重設，
        按測試就知道了。"""
        await with_bot(session)
        skipper = await person(session, "skipper", ADMIN_ID)
        await session.commit()
        factory = FakeClientFactory(jellyfin=crew())
        factory.discord_.rejected_tokens.add(TOKEN)

        await send_test(session, factory, skipper.id)

        assert (await read_channel(session)).token_rejected


# --- 不拖累 ------------------------------------------------------------------


class TestIsolation:
    async def test_a_notification_that_cannot_be_written_does_not_fail_the_resolution(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        await with_bot(session)
        await person(session, "skipper", ADMIN_ID)
        route, factory = await imported(session, roots)
        await scanned(session, route, factory)

        async def broken(*_: object) -> dict[str, Any]:
            raise ValueError("snapshot is not what it used to be")

        monkeypatch.setattr(notify, "_ready_content", broken)
        await resolve(session, factory, FIRST)

        assert EventType.JELLYFIN_ITEM_RESOLVED in [e.type for e in await events_of(session)]
        assert list(await session.scalars(select(Notification))) == []

    async def test_a_message_that_cannot_be_put_into_words_does_not_hold_up_the_next(
        self, session: AsyncSession
    ) -> None:
        await with_bot(session)
        skipper = await person(session, "skipper", ADMIN_ID)
        broken = await queued(session, skipper, content={"kind": "tv", "library": "item-2"})
        await queued(session, skipper)
        factory = FakeClientFactory(jellyfin=crew())

        await send_due(session, factory, now=NOW)

        broken = await fresh(session, broken)
        assert broken.status is NotificationStatus.ABANDONED
        assert "KeyError" in broken.error
        assert recipients(factory) == [ADMIN_ID]

    async def test_a_channel_that_raises_does_not_hold_up_the_next(
        self, session: AsyncSession
    ) -> None:
        """`NotifyChannel.send` 說好不丟例外；真的丟了，那一則記下來留著，下一則照送。"""
        await with_bot(session)
        skipper = await person(session, "skipper", ADMIN_ID)
        first = await queued(session, skipper)
        await queued(session, skipper)
        factory = FakeClientFactory(jellyfin=crew())
        real = factory.discord_
        calls = 0

        class RaisesOnce:
            async def send(self, recipient: str, message: Any) -> Delivery:
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise RuntimeError("adapter bug")
                return await real.send(recipient, message)

        factory.discord = lambda token: RaisesOnce()  # type: ignore[method-assign,assignment,return-value]  # 只換這一次的 bot

        await send_due(session, factory, now=NOW)

        first = await fresh(session, first)
        assert first.status is NotificationStatus.PENDING
        assert "RuntimeError" in first.error
        assert recipients(factory) == [ADMIN_ID]
