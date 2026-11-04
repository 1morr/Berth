"""「等你處理」寫出遲到的作品名與集數（M5.5 票 13，spec〈範圍〉「通知」）。

遲到不加通知種類：走現有的「等你處理」與「放太久」。只知道「1 個 Issue（遲到）」還得點進去，所以
這一波有 `episodes_overdue` 時，內文多列作品名與晚的集。斷言只看兩個公開的接縫：看守一輪
（`watch_waiting`）與送出一輪（`send_due`）交給 Discord 的訊息。

Issue 走 `record_issue`（巡檢寫 Issue 的唯一入口），`detail_json` 的形狀照巡檢寫的那一份
（`sweep._overdue_detail`）；有一條從真的巡檢一路走到送出，守那個形狀沒漂掉。
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import IssueType, Language
from berth.services.issues import record_issue
from berth.services.notify import WAIT_WINDOW, queue_lingering, send_due
from berth.services.sweep import sweep_once
from tests.integration.factories import FakeClientFactory
from tests.integration.test_notify import ADMIN_ID, person, with_bot
from tests.integration.test_notify_waiting import (
    BOTH,
    admin,
    deliver,
    first_look,
    only,
    orphan_issue,
    watch,
    wave,
)
from tests.integration.test_plan import NOW
from tests.integration.test_sweep_overdue import overdue, subscribed, wall

pytestmark = pytest.mark.asyncio


def detail(
    title: str,
    episodes: list[tuple[int, int]],
    *,
    reason: str = "late",
    title_en: str | None = None,
) -> dict[str, Any]:
    """`episodes_overdue` 的 `detail_json`，形狀同巡檢寫的那一份。"""
    found: dict[str, Any] = {
        "reason": reason,
        "media": f"tv:{abs(hash(title)) % 100000}",
        "title": title,
        "name": title,
        "episodes": [
            {
                "season": season,
                "episode": episode,
                "air_date": "2026-10-28",
                "stall": "not_released",
                "jobs": [],
            }
            for season, episode in episodes
        ],
    }
    if title_en is not None:
        found["title_en"] = title_en
    return found


async def late_work(
    session: AsyncSession,
    media_id: str,
    title: str,
    episodes: list[tuple[int, int]],
    **more: Any,
) -> int:
    """開一件遲到，回它的 Issue id。"""
    recorded = await record_issue(
        session,
        IssueType.EPISODES_OVERDUE,
        media_id=media_id,
        detail=detail(title, episodes, **more),
        now=NOW,
    )
    await session.commit()
    return recorded.issue.id


class TestTheWaveNamesTheWorks:
    async def test_one_late_work_names_its_title_and_episodes(self, session: AsyncSession) -> None:
        """驗收第 1 條（zh-Hant）：作品名與晚的集，集數照「可以看了」的寫法合成範圍。"""
        await first_look(session)
        await late_work(session, "tv:1", "葬送的芙莉蓮", [(2, 5), (2, 6)])
        factory = FakeClientFactory()

        await wave(session, factory)

        message = only(factory)
        assert message.title == "有 1 件等你處理"
        assert message.description == "新增 1 件：1 個 Issue（遲到）\n葬送的芙莉蓮 S02E05–E06"

    async def test_english_from_a_real_sweep_uses_the_english_title(
        self, session: AsyncSession
    ) -> None:
        """驗收第 1 條（en）：真的巡檢開的件（`sweep._overdue_detail` 的形狀），英文收件人看到英文
        片名。巡檢 10/31 05:00 開，看守在那之後看到、合併時間到了送出。"""
        await with_bot(session)
        await admin(session, language=Language.EN)
        await watch(session, timedelta(0))
        await subscribed(session)
        await sweep_once(session, now=wall(31))
        factory = FakeClientFactory()
        seen = wall(31) - NOW + timedelta(minutes=1)

        await watch(session, seen)
        await deliver(session, factory, seen + WAIT_WINDOW)

        message = only(factory)
        assert message.description == "1 new: 1 issue (overdue)\nKimi to Koishitai S01E04"

    async def test_past_five_works_the_rest_is_a_count(self, session: AsyncSession) -> None:
        """驗收第 2 條：七部遲到，列前五部（照開的順序），其餘一行「等 2 部」。"""
        await first_look(session)
        for number in range(1, 8):
            await late_work(session, f"tv:{number}", f"作品{number}", [(1, number)])
        factory = FakeClientFactory()

        await wave(session, factory)

        assert only(factory).description.split("\n") == [
            "新增 7 件：7 個 Issue（遲到 ×7）",
            "作品1 S01E01",
            "作品2 S01E02",
            "作品3 S01E03",
            "作品4 S01E04",
            "作品5 S01E05",
            "等 2 部",
        ]

    async def test_english_rest_and_next_run(self, session: AsyncSession) -> None:
        """英文的「等 N 部」；換輪的件說「可能是下一輪」、不說成晚了；沒有 `title_en` 的舊件退回
        `title`。"""
        await with_bot(session)
        await admin(session, language=Language.EN)
        await watch(session, timedelta(0))
        await late_work(
            session, "tv:1", "间谍过家家", [(3, 1)], reason="next_run", title_en="SPY×FAMILY"
        )
        for number in range(2, 7):
            await late_work(session, f"tv:{number}", f"Work {number}", [(1, number)])
        factory = FakeClientFactory()

        await wave(session, factory)

        assert only(factory).description.split("\n") == [
            "6 new: 6 issues (overdue ×6)",
            "SPY×FAMILY S03E01 (possibly the next run)",
            "Work 2 S01E02",
            "Work 3 S01E03",
            "Work 4 S01E04",
            "Work 5 S01E05",
            "and 1 more",
        ]

    async def test_next_run_in_chinese(self, session: AsyncSession) -> None:
        await first_look(session)
        await late_work(session, "tv:1", "间谍过家家", [(3, 1)], reason="next_run")
        factory = FakeClientFactory()

        await wave(session, factory)

        assert only(factory).description == (
            "新增 1 件：1 個 Issue（遲到）\n间谍过家家 S03E01（可能是下一輪）"
        )


class TestOtherKindsAreUnchanged:
    async def test_a_wave_without_overdue_reads_as_before(self, session: AsyncSession) -> None:
        """驗收第 3 條：沒有遲到的一波，內文就是原來那一行；遲到早就開著、不在這一波的也不列。"""
        await first_look(session)
        await late_work(session, "tv:1", "葬送的芙莉蓮", [(2, 5)])
        await wave(session, FakeClientFactory())
        await orphan_issue(session)
        factory = FakeClientFactory()

        await watch(session, timedelta(minutes=20))
        await deliver(session, factory, timedelta(minutes=20) + WAIT_WINDOW)

        message = only(factory)
        assert message.description == "新增 1 件：1 個 Issue（無主目錄）"
        assert message.fields == (("Issue", "2"),)


class TestLingering:
    async def test_the_lingering_reminder_names_the_work_too(self, session: AsyncSession) -> None:
        """「放太久」也走「等你處理」：那一件是遲到時同樣寫出作品與集。"""
        await with_bot(session)
        await admin(session)
        issue = await late_work(session, "tv:1", "葬送的芙莉蓮", [(2, 5)])
        await watch(session, timedelta(0))
        factory = FakeClientFactory()

        await queue_lingering(session, f"issue:{issue}", days=3, now=NOW + timedelta(days=3))
        await session.commit()
        await send_due(session, factory, now=NOW + timedelta(days=3))

        message = only(factory)
        assert message.title == "有一件等了 3 天"
        assert message.description == "1 個 Issue（遲到）\n葬送的芙莉蓮 S02E05"


class TestWithoutDiscord:
    @pytest.mark.parametrize("bot", [False, True], ids=["no_bot", "no_discord_id"])
    async def test_the_issue_still_opens_and_nothing_is_sent(
        self, session: AsyncSession, bot: bool
    ) -> None:
        """spec〈驗收〉「沒接 Discord 時 Issue 照開」：沒有 bot，或有 bot 而管理員沒填 Discord ID，
        巡檢照樣開遲到；看守與送出各一輪，什麼都沒送（追更頁頁首的提示由前端測試守）。"""
        if bot:
            await with_bot(session)
        await person(session, "skipper", discord="" if bot else ADMIN_ID, kinds=BOTH)
        await watch(session, timedelta(0))
        await subscribed(session)
        await sweep_once(session, now=wall(31))
        factory = FakeClientFactory()
        seen = wall(31) - NOW + timedelta(minutes=1)

        await watch(session, seen)
        await deliver(session, factory, seen + WAIT_WINDOW)

        (issue,) = await overdue(session)
        assert issue.detail["reason"] == "late"
        assert factory.discord_.sent == []
