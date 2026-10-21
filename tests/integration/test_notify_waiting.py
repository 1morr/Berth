"""「有 N 件等你處理」（M4 票 127，plan §11.5〈通知〉）。

三個要人動手的地方：審核佇列、開著的 Issue、待綁定的 RSS Series。斷言只看兩個公開的接縫：
看守的一輪（`watch_waiting`，送出迴圈每一輪先跑它）排下什麼，與送出的一輪（`send_due`）交給
Discord 什麼。

起點各用最短的真路徑：審核的那一件是真的 medium 自動入庫（`test_review.audited`），Issue 走
`record_issue`（對帳與管線寫 Issue 的唯一入口），待綁定的 RSS Series 是 `media_id` 為空的一列
（RSS 頁的待綁定段就是這一條）。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.notify import Message
from berth.domain import IssueType, Language, NotificationKind, Role
from berth.models import BerthSettings, Issue, RssSeries, User
from berth.services.issues import ignore_issue, note_cleared, record_issue
from berth.services.notify import WAIT_WINDOW, send_due, set_mine, watch_waiting
from berth.services.settings import write_settings
from tests.integration.factories import FakeClientFactory
from tests.integration.test_notify import ADMIN_ID, CREW_ID, SECOND_ADMIN_ID, person, with_bot
from tests.integration.test_plan import NOW
from tests.integration.test_review import audited

pytestmark = pytest.mark.asyncio

BOTH = (NotificationKind.READY, NotificationKind.WAITING)
URL = "https://berth.example.org"
ORPHAN = "/data/torrent/complete/anime/[Nobody] Orphan"
UNKNOWN = "f" * 40
ACTOR = "7"


async def admin(session: AsyncSession, *, language: Language = Language.ZH_HANT) -> User:
    return await person(session, "skipper", discord=ADMIN_ID, kinds=BOTH, language=language)


async def orphan_issue(session: AsyncSession, *, path: str = ORPHAN, now: datetime = NOW) -> Issue:
    recorded = await record_issue(session, IssueType.ORPHAN_COMPLETE, path=path, now=now)
    await session.commit()
    return recorded.issue


async def unbound_series(session: AsyncSession, key: str = "mikan:1:2") -> RssSeries:
    series = RssSeries(key=key, title_raw="[ANi] 葬送的芙莉蓮 - 29 [1080P]", reasons_json=[])
    session.add(series)
    await session.commit()
    return series


async def ignored(session: AsyncSession, issue: Issue) -> None:
    await ignore_issue(session, issue.id, actor=ACTOR)
    await session.commit()


async def watch(session: AsyncSession, at: timedelta) -> None:
    """看守一輪。它不 commit（送出迴圈裡由接著的 `send_due` 落地），這裡自己收。"""
    await watch_waiting(session, now=NOW + at)
    await session.commit()


async def deliver(session: AsyncSession, factory: FakeClientFactory, at: timedelta) -> None:
    await send_due(session, factory, now=NOW + at)


async def first_look(session: AsyncSession) -> None:
    """有 bot、有一位訂閱了的管理員，看守跑過第一次：在這之後出現的才是新的一件。"""
    await with_bot(session)
    await admin(session)
    await watch(session, timedelta(0))


async def wave(session: AsyncSession, factory: FakeClientFactory) -> None:
    """一分鐘時看到、合併時間到了送出。"""
    await watch(session, timedelta(minutes=1))
    await deliver(session, factory, timedelta(minutes=1) + WAIT_WINDOW)


def only(factory: FakeClientFactory, recipient: str = ADMIN_ID) -> Message:
    (message,) = [message for to, message in factory.discord_.sent if to == recipient]
    return message


class TestOneMessagePerWave:
    async def test_three_new_things_within_ten_minutes_are_one_message(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """驗收第 1 條：三件（各一種）→ 一則，說出這一波新增了什麼、各幾件與現在的總數。"""
        await first_look(session)
        await audited(session, roots)
        factory = FakeClientFactory()
        await watch(session, timedelta(minutes=1))
        await orphan_issue(session)
        await watch(session, timedelta(minutes=4))
        await unbound_series(session)
        await watch(session, timedelta(minutes=8))

        await deliver(session, factory, timedelta(minutes=1) + WAIT_WINDOW - timedelta(seconds=1))
        assert factory.discord_.sent == []

        await deliver(session, factory, timedelta(minutes=1) + WAIT_WINDOW)

        message = only(factory)
        assert message.title == "有 3 件等你處理"
        assert message.description == (
            "新增 3 件：1 件待審核、1 個 Issue（無主目錄）、1 個 RSS Series 待綁定"
        )
        assert message.fields == (("待審核", "1"), ("Issue", "1"), ("待綁定", "1"))
        # 沒存 Berth 的網址：照送、不附連結。
        assert message.links == ()
        # 一則就是一則：之後再跑也不重送。
        await watch(session, timedelta(minutes=12))
        await deliver(session, factory, timedelta(minutes=30))
        assert len(factory.discord_.sent) == 1

    async def test_english_names_each_issue_type_and_counts_repeats(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await with_bot(session)
        await admin(session, language=Language.EN)
        await watch(session, timedelta(0))
        await orphan_issue(session)
        await orphan_issue(session, path=f"{ORPHAN} 2")
        await record_issue(session, IssueType.UNKNOWN_TORRENT, job_hash=UNKNOWN, now=NOW)
        await session.commit()
        await unbound_series(session)
        factory = FakeClientFactory()

        await wave(session, factory)

        message = only(factory)
        assert message.title == "4 waiting for you"
        assert message.description == (
            "4 new: 3 issues (orphan folder ×2, unknown torrent), 1 RSS series to bind"
        )
        assert message.fields == (("Issues", "3"), ("To bind", "1"))

    async def test_the_first_look_takes_what_is_already_waiting_as_the_baseline(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """升級那一刻已經在等的不是「新的一件」：第一次看只記下來。"""
        await with_bot(session)
        await admin(session)
        await orphan_issue(session)
        factory = FakeClientFactory()

        await watch(session, timedelta(0))
        await deliver(session, factory, WAIT_WINDOW * 2)

        assert factory.discord_.sent == []


class TestLinks:
    """驗收第 2 條：這一波只有一件時連到那一件（清單頁加那一列的錨點），多件時連到各自的清單。"""

    async def with_url(self, session: AsyncSession) -> None:
        await write_settings(session, BerthSettings(public_url=URL))
        await first_look(session)

    async def test_one_thing_to_review_links_to_its_row(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await self.with_url(session)
        _, entry = await audited(session, roots)
        factory = FakeClientFactory()

        await wave(session, factory)

        message = only(factory)
        assert message.description == "新增 1 件：1 件待審核"
        assert [(link.label, link.url) for link in message.links] == [
            ("在 Berth 打開", f"{URL}/review#audit-{entry.id}")
        ]

    async def test_one_issue_links_to_its_row(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await self.with_url(session)
        issue = await orphan_issue(session)
        factory = FakeClientFactory()

        await wave(session, factory)

        assert [link.url for link in only(factory).links] == [f"{URL}/issues#issue-{issue.id}"]

    async def test_one_series_to_bind_links_to_its_row(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await self.with_url(session)
        series = await unbound_series(session)
        factory = FakeClientFactory()

        await wave(session, factory)

        assert [link.url for link in only(factory).links] == [f"{URL}/rss#series-{series.id}"]

    async def test_several_link_to_each_list_they_are_on(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await self.with_url(session)
        await orphan_issue(session)
        await unbound_series(session)
        await unbound_series(session, "mikan:1:3")
        factory = FakeClientFactory()

        await wave(session, factory)

        assert [(link.label, link.url) for link in only(factory).links] == [
            ("打開 Issue", f"{URL}/issues"),
            ("打開 RSS", f"{URL}/rss"),
        ]


class TestHandledBeforeSending:
    async def test_nothing_is_sent_when_everything_was_handled(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """驗收第 3 條：送出前已處理掉、總數 0 → 不送，之後也不送。"""
        await first_look(session)
        issue = await orphan_issue(session)
        await watch(session, timedelta(minutes=1))
        await ignored(session, issue)
        await watch(session, timedelta(minutes=2))
        factory = FakeClientFactory()

        await deliver(session, factory, timedelta(minutes=1) + WAIT_WINDOW)
        await deliver(session, factory, WAIT_WINDOW * 3)

        assert factory.discord_.sent == []

    async def test_only_what_is_still_waiting_is_counted_as_new(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """這一波的兩件處理掉一件：說新增 1 件，總數照送出那一刻算。"""
        await first_look(session)
        issue = await orphan_issue(session)
        await unbound_series(session)
        await watch(session, timedelta(minutes=1))
        await ignored(session, issue)
        factory = FakeClientFactory()

        await deliver(session, factory, timedelta(minutes=1) + WAIT_WINDOW)

        message = only(factory)
        assert message.title == "有 1 件等你處理"
        assert message.description == "新增 1 件：1 個 RSS Series 待綁定"
        assert message.fields == (("待綁定", "1"),)


class TestIgnoredIssues:
    """驗收第 4 條：被忽略、條件仍在的 Issue 隔天對帳不觸發（票 122）。"""

    async def test_an_issue_held_ignored_by_ticket_122_does_not_come_back(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`unknown_torrent` 的忽略在條件持續期間有效（`STAYS_IGNORED`）：隔天再偵測什麼都不寫。"""
        await first_look(session)
        recorded = await record_issue(session, IssueType.UNKNOWN_TORRENT, job_hash=UNKNOWN, now=NOW)
        await session.commit()
        factory = FakeClientFactory()
        await wave(session, factory)
        assert len(factory.discord_.sent) == 1
        await ignored(session, recorded.issue)

        next_day = timedelta(days=1)
        await record_issue(session, IssueType.UNKNOWN_TORRENT, job_hash=UNKNOWN, now=NOW + next_day)
        await session.commit()
        await watch(session, next_day)
        await deliver(session, factory, next_day + WAIT_WINDOW)

        assert len(factory.discord_.sent) == 1

    async def test_an_ignored_issue_whose_condition_cleared_and_came_back_is_new(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """條件解除過（`cleared_at`）之後再發生是新的一件（票 122 的重開），不是「條件仍在」。"""
        await first_look(session)
        recorded = await record_issue(session, IssueType.UNKNOWN_TORRENT, job_hash=UNKNOWN, now=NOW)
        await session.commit()
        factory = FakeClientFactory()
        await wave(session, factory)
        await ignored(session, recorded.issue)
        note_cleared([recorded.issue], NOW + timedelta(hours=1))
        await session.commit()

        next_day = timedelta(days=1)
        await record_issue(session, IssueType.UNKNOWN_TORRENT, job_hash=UNKNOWN, now=NOW + next_day)
        await session.commit()
        await watch(session, next_day)
        await deliver(session, factory, next_day + WAIT_WINDOW)

        assert len(factory.discord_.sent) == 2

    async def test_an_issue_reopened_after_being_ignored_is_counted_but_not_new(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """其餘幾種忽略之後隔天對帳會再開一筆（brief §9.1）：它在清單上、算進總數，但不推。"""
        await first_look(session)
        issue = await orphan_issue(session)
        factory = FakeClientFactory()
        await wave(session, factory)
        await ignored(session, issue)

        next_day = timedelta(days=1)
        await orphan_issue(session, now=NOW + next_day)
        await watch(session, next_day)
        await deliver(session, factory, next_day + WAIT_WINDOW)
        assert len(factory.discord_.sent) == 1

        await unbound_series(session)
        later = next_day + timedelta(minutes=1)
        await watch(session, later)
        await deliver(session, factory, later + WAIT_WINDOW)
        (_, latest) = factory.discord_.sent[-1]
        assert latest.title == "有 2 件等你處理"
        assert latest.description == "新增 1 件：1 個 RSS Series 待綁定"


class TestRecipients:
    async def test_a_user_does_not_get_it_only_admins_do(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """驗收第 5 條：`user` 角色不收，存著的訂閱裡有它也一樣；沒訂閱的管理員也不收。"""
        await with_bot(session)
        await admin(session)
        await person(session, "bosun", discord=SECOND_ADMIN_ID, kinds=(NotificationKind.READY,))
        await person(session, "deckhand", role=Role.USER, discord=CREW_ID, kinds=BOTH)
        await watch(session, timedelta(0))
        await orphan_issue(session)
        factory = FakeClientFactory()

        await wave(session, factory)

        assert [to for to, _ in factory.discord_.sent] == [ADMIN_ID]

    async def test_an_admin_who_lost_the_role_before_sending_gets_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """角色每次登入照 Jellyfin 重寫：送出那一刻不是管理員就不送。"""
        await first_look(session)
        await orphan_issue(session)
        await watch(session, timedelta(minutes=1))
        skipper = await session.scalar(select(User).where(User.name == "skipper"))
        assert skipper is not None
        skipper.role = Role.USER
        await session.commit()
        factory = FakeClientFactory()

        await deliver(session, factory, timedelta(minutes=1) + WAIT_WINDOW)

        assert factory.discord_.sent == []

    async def test_a_user_cannot_subscribe_to_it(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        crew = await person(session, "deckhand", role=Role.USER)
        await session.commit()

        mine = await set_mine(session, crew.id, CREW_ID, Language.ZH_HANT, BOTH)

        assert mine.kinds == (NotificationKind.READY,)
