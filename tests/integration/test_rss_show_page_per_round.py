"""同一輪裡同一個 Mikan 番組頁只讀一次（M4 票 82）。

同一部動畫的不同字幕組是不同的 RSS Series，自動綁定卻是讀同一頁番組頁。替身是合成的聚合 feed：
《与你相恋》（番組 4009）的 LoliHouse（370）與 ANi（583）各一集，番組頁是票 07 錄下來的那一頁，
兩組都在上面。輪一輪是 Feed 1 + 單集頁 2 + 番組頁 1。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.budget import RequestBudget
from berth.adapters.http import ServiceUnavailableError
from berth.adapters.rss.mikan import bangumi_url
from berth.domain import BindReasonCode, BudgetUse
from berth.models import RssSeries
from berth.services.rss import LOOKUP_RETRIES, add_feed, list_series, poll_feed
from tests.integration.factories import FakeClientFactory
from tests.integration.test_request_budget import Clock, used
from tests.integration.test_rss import FEED_URL, KIMI_ID, NOW
from tests.integration.test_rss_auto_bind import moored
from tests.integration.test_rss_screen import release, serve

pytestmark = pytest.mark.asyncio

SHOW_PAGE = bangumi_url(4009)
RELEASES = [release(370, "LoliHouse", "11"), release(583, "ANi", "11")]


async def two_groups(
    session: AsyncSession, roots: dict[str, Path], *, limit: int = 60
) -> tuple[FakeClientFactory, Clock, int]:
    """回（替身、時鐘、Feed 的 id）。"""
    _, factory = await moored(session, roots)
    clock = Clock(NOW)
    factory.budget = RequestBudget(limit=limit, now=clock)
    serve(factory, FEED_URL, RELEASES)
    feed = await add_feed(session, url=FEED_URL, name="Mikan")
    return factory, clock, feed.id


async def round_at(
    session: AsyncSession, factory: FakeClientFactory, feed_id: int, moment: datetime
) -> int:
    """輪一輪，回這一輪讀了幾次番組頁。"""
    factory.rss_.requested.clear()
    await poll_feed(session, factory, feed_id, now=moment)
    return factory.rss_.requested.count(SHOW_PAGE)


async def by_group(session: AsyncSession) -> dict[int | None, RssSeries]:
    session.expire_all()
    rows = await session.scalars(select(RssSeries).where(RssSeries.mikan_bangumi_id == 4009))
    return {row.mikan_subgroup_id: row for row in rows}


async def codes_by_group(session: AsyncSession) -> dict[int | None, list[BindReasonCode]]:
    views = {view.id: view for view in await list_series(session)}
    return {
        group: [reason.code for reason in views[row.id].reasons]
        for group, row in (await by_group(session)).items()
    }


async def test_two_groups_of_one_show_read_its_page_once(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    factory, clock, feed_id = await two_groups(session, roots)

    reads = await round_at(session, factory, feed_id, clock.now)

    assert reads == 1
    assert used(factory)[BudgetUse.POLL] == 4
    series = await by_group(session)
    assert set(series) == {370, 583}
    # 兩組都拿到番組頁的線索（綁得上）與各自的字幕組名。
    assert {group: row.media_id for group, row in series.items()} == {370: KIMI_ID, 583: KIMI_ID}
    assert {group: row.mikan_subgroup_name for group, row in series.items()} == {
        370: "LoliHouse",
        583: "ANi",
    }
    assert {row.mikan_bangumi_name for row in series.values()} == {"与你相恋到生命尽头"}


async def test_a_page_that_cannot_be_read_fails_both_groups_alike_with_one_ask(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    factory, clock, feed_id = await two_groups(session, roots)
    factory.rss_.page_errors[SHOW_PAGE] = ServiceUnavailableError(f"GET {SHOW_PAGE}: 503")

    reads = await round_at(session, factory, feed_id, clock.now)

    assert reads == 1
    assert await codes_by_group(session) == {
        370: [BindReasonCode.LOOKUP_RETRY],
        583: [BindReasonCode.LOOKUP_RETRY],
    }


async def test_a_page_out_of_budget_defers_both_groups_and_takes_one_refusal(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    # 3 格：Feed 與兩頁單集頁，番組頁放不下。
    factory, clock, feed_id = await two_groups(session, roots, limit=3)

    reads = await round_at(session, factory, feed_id, clock.now)

    assert reads == 0
    assert await codes_by_group(session) == {
        370: [BindReasonCode.LOOKUP_DEFERRED],
        583: [BindReasonCode.LOOKUP_DEFERRED],
    }
    (usage,) = factory.budget.usage()
    assert [(one.use, one.refused) for one in usage.deferred] == [(BudgetUse.POLL, 1)]


async def test_another_round_reads_the_page_again(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    """快取只活在那一輪：第一輪讀不到，重認的那一輪再讀一次，兩組都綁上。"""
    factory, clock, feed_id = await two_groups(session, roots)
    factory.rss_.page_errors[SHOW_PAGE] = ServiceUnavailableError(f"GET {SHOW_PAGE}: 503")
    first = await round_at(session, factory, feed_id, clock.now)
    del factory.rss_.page_errors[SHOW_PAGE]

    second = await round_at(session, factory, feed_id, clock.now + LOOKUP_RETRIES[0])

    assert (first, second) == (1, 1)
    series = await by_group(session)
    assert {group: row.media_id for group, row in series.items()} == {370: KIMI_ID, 583: KIMI_ID}


async def test_a_new_group_and_a_due_lookup_share_the_page_in_one_round(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    """同一輪裡一組剛長出來、另一組是上一輪被預算擋下的重認：兩段迴圈共用那一次。"""
    _, factory = await moored(session, roots)
    clock = Clock(NOW)
    # 2 格：Feed 與一頁單集頁，番組頁放不下，LoliHouse 那一組延後。
    factory.budget = RequestBudget(limit=2, now=clock)
    serve(factory, FEED_URL, RELEASES[:1])
    feed = await add_feed(session, url=FEED_URL, name="Mikan")
    assert await round_at(session, factory, feed.id, clock.now) == 0
    assert await codes_by_group(session) == {370: [BindReasonCode.LOOKUP_DEFERRED]}

    factory.budget = RequestBudget(now=clock)
    serve(factory, FEED_URL, RELEASES)
    reads = await round_at(session, factory, feed.id, clock.now + timedelta(minutes=16))

    assert reads == 1
    series = await by_group(session)
    assert {group: row.media_id for group, row in series.items()} == {370: KIMI_ID, 583: KIMI_ID}
