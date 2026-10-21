"""每日巡檢的「放太久」（M4 票 129，plan §11.5〈巡檢〉）。

「等你處理」裡最舊的一件超過 `LINGER_AFTER`（3 天），巡檢給訂閱了「等你處理」的管理員再提醒一則；
同一件 `REMIND_EVERY`（3 天）內只提醒一次。一件從什麼時候開始等，是送出迴圈的看守
（`watch_waiting`）第一次在清單上看到它的那一刻——「新的一件」也是它說了算（M4 票 127）。

斷言只看公開的接縫：看守一輪、巡檢一輪（`sweep_once`）、送出一輪（`send_due`）之後，Discord
收到什麼。起點同 `test_notify_waiting.py`：Issue 走 `record_issue`，待綁定是 `media_id` 為空的一列。
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import IssueType, Language, NotificationKind
from berth.models import BerthSettings, Issue, NotifyWatchSettings, User
from berth.services.issues import record_issue
from berth.services.notify import WAIT_WINDOW
from berth.services.settings import write_settings
from berth.services.sweep import LINGER_AFTER, REMIND_EVERY, sweep_once
from tests.integration.factories import FakeClientFactory
from tests.integration.test_notify import ADMIN_ID, with_bot
from tests.integration.test_notify_waiting import (
    ORPHAN,
    URL,
    admin,
    deliver,
    first_look,
    ignored,
    orphan_issue,
    unbound_series,
    watch,
)
from tests.integration.test_plan import NOW

pytestmark = pytest.mark.asyncio

#: 那一件出現在清單上、看守看到它的那一刻。
SEEN = timedelta(minutes=1)


async def waiting_since_seen(session: AsyncSession, factory: FakeClientFactory) -> int:
    """一件無主目錄在 `SEEN` 出現：看守看到、那一波的「等你處理」送掉（之後只剩提醒會送）。"""
    await first_look(session)
    issue = await orphan_issue(session)
    await watch(session, SEEN)
    await deliver(session, factory, SEEN + WAIT_WINDOW)
    factory.discord_.sent.clear()
    return issue.id


async def sweep(session: AsyncSession, factory: FakeClientFactory, at: timedelta) -> None:
    """巡檢一輪，送出迴圈接著（10 秒後）送一輪。"""
    await sweep_once(session, now=NOW + at)
    await deliver(session, factory, at + timedelta(seconds=10))


class TestTheOldestOneIsRemindedOnce:
    async def test_older_than_three_days_sends_one_reminder(self, session: AsyncSession) -> None:
        factory = FakeClientFactory()
        issue_id = await waiting_since_seen(session, factory)
        await write_settings(session, BerthSettings(public_url=URL))
        await session.commit()

        await sweep(session, factory, SEEN + LINGER_AFTER + timedelta(hours=1))

        ((to, message),) = factory.discord_.sent
        assert to == ADMIN_ID
        assert message.title == "有一件等了 3 天"
        assert message.description == "1 個 Issue（無主目錄）"
        assert message.fields == (("Issue", "1"),)
        assert [link.url for link in message.links] == [f"{URL}/issues#issue-{issue_id}"]

    async def test_not_yet_three_days_sends_nothing(self, session: AsyncSession) -> None:
        factory = FakeClientFactory()
        await waiting_since_seen(session, factory)

        await sweep(session, factory, SEEN + LINGER_AFTER - timedelta(minutes=1))

        assert factory.discord_.sent == []

    async def test_the_same_one_is_not_reminded_again_within_three_days(
        self, session: AsyncSession
    ) -> None:
        factory = FakeClientFactory()
        await waiting_since_seen(session, factory)
        reminded = SEEN + LINGER_AFTER + timedelta(hours=1)
        await sweep(session, factory, reminded)
        factory.discord_.sent.clear()

        await sweep(session, factory, reminded + timedelta(days=1))
        await sweep(session, factory, reminded + REMIND_EVERY - timedelta(minutes=1))
        assert factory.discord_.sent == []

        await sweep(session, factory, reminded + REMIND_EVERY)
        ((_, message),) = factory.discord_.sent
        assert message.title == "有一件等了 6 天"

    async def test_it_names_the_oldest_one(self, session: AsyncSession) -> None:
        factory = FakeClientFactory()
        await waiting_since_seen(session, factory)
        await unbound_series(session)
        await watch(session, timedelta(days=1))

        await sweep(session, factory, SEEN + LINGER_AFTER + timedelta(hours=1))

        ((_, message),) = factory.discord_.sent
        assert message.description == "1 個 Issue（無主目錄）"
        assert message.fields == (("Issue", "1"), ("待綁定", "1"))

    async def test_english(self, session: AsyncSession) -> None:
        await with_bot(session)
        await admin(session, language=Language.EN)
        await watch(session, timedelta(0))
        await unbound_series(session)
        await watch(session, SEEN)
        factory = FakeClientFactory()
        await deliver(session, factory, SEEN + WAIT_WINDOW)
        factory.discord_.sent.clear()

        await sweep(session, factory, SEEN + timedelta(days=4))

        ((_, message),) = factory.discord_.sent
        assert message.title == "Waiting for 4 days"
        assert message.description == "1 RSS series to bind"


class TestNotWorthAReminder:
    async def test_handled_before_it_was_sent_is_not_sent(self, session: AsyncSession) -> None:
        factory = FakeClientFactory()
        issue_id = await waiting_since_seen(session, factory)
        at = SEEN + LINGER_AFTER + timedelta(hours=1)
        await sweep_once(session, now=NOW + at)

        await ignored(session, await session.get_one(Issue, issue_id))
        await deliver(session, factory, at + timedelta(seconds=10))

        assert factory.discord_.sent == []

    async def test_an_ignored_one_that_came_back_is_not_reminded(
        self, session: AsyncSession
    ) -> None:
        """人說過這一件不用管、條件一直都在而又開的那一筆（`issues.still_ignored`）：算進總數，不提醒。"""
        factory = FakeClientFactory()
        await first_look(session)
        await ignored(session, await orphan_issue(session))
        await record_issue(session, IssueType.ORPHAN_COMPLETE, path=ORPHAN, now=NOW)
        await session.commit()
        await watch(session, SEEN)

        await sweep(session, factory, SEEN + timedelta(days=4))

        assert factory.discord_.sent == []


class TestSinceWhen:
    async def test_waiting_since_before_the_upgrade_counts_from_the_first_look_after_it(
        self, session: AsyncSession
    ) -> None:
        """升版之前看守只記了「有誰」：那幾件從升版後第一次看起算，也不當成新的一件推出去。"""
        await with_bot(session)
        await admin(session)
        issue = await orphan_issue(session)
        await write_settings(session, NotifyWatchSettings(seen=[f"issue:{issue.id}"]))
        await session.commit()
        factory = FakeClientFactory()
        await watch(session, SEEN)

        await sweep(session, factory, SEEN + LINGER_AFTER - timedelta(minutes=1))
        assert factory.discord_.sent == []

        await sweep(session, factory, SEEN + LINGER_AFTER)
        ((_, message),) = factory.discord_.sent
        assert message.title == "有一件等了 3 天"

    async def test_nobody_to_tell_does_not_count_as_reminded(self, session: AsyncSession) -> None:
        """那一刻沒有管理員收得到（沒勾、沒填 Discord ID）：之後勾了的人隔天就收得到，
        不必再等 3 天。"""
        factory = FakeClientFactory()
        await waiting_since_seen(session, factory)
        skipper = await session.scalar(select(User).where(User.discord_user_id == ADMIN_ID))
        assert skipper is not None
        kinds = skipper.notify_kinds_json
        skipper.notify_kinds_json = [NotificationKind.READY.value]
        await session.commit()
        first = SEEN + LINGER_AFTER + timedelta(hours=1)
        await sweep(session, factory, first)
        assert factory.discord_.sent == []

        skipper.notify_kinds_json = kinds
        await session.commit()
        await sweep(session, factory, first + timedelta(days=1))

        ((_, message),) = factory.discord_.sent
        assert message.title == "有一件等了 4 天"
