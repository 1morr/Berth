"""一個站一份請求預算：輪詢、每日補漏、搜尋共用（M3 票 20、plan §3.2、§8.4）。

三者打的是同一批公開站——Prowlarr 預設的 Mikan、Nyaa、ACG.RIP 就是 RSS 那三站（brief §20.7）。
這裡造一份很小的預算，讓三者在 `mikanani.me` 上搶同一份，並守住：加起來不超過、被擋下的
那一種工作照它自己的退路延後（輪詢下一輪、補漏不動 `backfilled_at`、自動綁定下一輪再認），
而且說得出來。

**「出去了幾個請求」數的是替身真的收到的**：`FakeFeedFetcher.requested` 與
`FakeIndexerSearch.queries`。預算擋在它們之前，所以被擋下的一個都不會出現在那裡。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.budget import RequestBudget, site_of
from berth.adapters.indexer import SearchSite
from berth.adapters.indexer.fake import FakeIndexerSearch
from berth.domain import BindReasonCode, BudgetUse, IndexerProblem
from berth.models import RssFeed, RssSeries
from berth.services.rss import add_feed, bind_series, list_series, poll_feed
from berth.services.search import SkippedSite, search_torrents
from tests.integration.factories import FakeClientFactory
from tests.integration.test_rss import FEED_URL, KIMI_KEY, NOW, harbour, series_by_key
from tests.integration.test_rss_auto_bind import moored
from tests.integration.test_rss_screen import release, serve, serve_single
from tests.integration.test_search import arrange_indexer

pytestmark = pytest.mark.asyncio

MIKAN = "mikanani.me"
NYAA = "nyaa.si"
#: 索引站背後的兩站（Prowlarr 的 indexer id 與名字）。
MIKAN_SITE = SearchSite(indexer_id=3, name="Mikan", site=MIKAN)
NYAA_SITE = SearchSite(indexer_id=7, name="Nyaa.si", site=NYAA)
#: 聚合 feed 上《与你相恋》喵萌奶茶屋&LoliHouse 的兩集：輪一輪是 Feed 1 + 單集頁 2 + 番組頁 1。
RELEASES = [release(370, "LoliHouse", "11"), release(370, "LoliHouse", "12")]


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def went_out(factory: FakeClientFactory, indexer: FakeIndexerSearch) -> int:
    """真的打到 Mikan 的請求：RSS 抓的每一條，加上每一個搜尋查詢（索引站背後就是 Mikan）。"""
    feeds = sum(site_of(url) == MIKAN for url in factory.rss_.requested)
    return feeds + len(indexer.queries)


def used(factory: FakeClientFactory, site: str = MIKAN) -> dict[BudgetUse, int]:
    (usage,) = (row for row in factory.budget.usage() if row.site == site)
    return dict(usage.by_use)


def deferred(factory: FakeClientFactory) -> set[BudgetUse]:
    return {
        deferral.use
        for row in factory.budget.usage()
        if row.site == MIKAN
        for deferral in row.deferred
    }


async def mikan_on_both_sides(
    session: AsyncSession, roots: dict[str, Path], limit: int
) -> tuple[FakeClientFactory, FakeIndexerSearch, Clock, int]:
    """Mikan 聚合 feed 與它的單一 feed 在替身上；索引站背後也是 Mikan；預算是 `limit`。

    回（替身、索引站、時鐘、anime Route 的 id）。
    """
    _, route, factory = await harbour(session, roots)
    clock = Clock(NOW)
    factory.budget = RequestBudget(limit=limit, now=clock)
    serve(factory, FEED_URL, RELEASES)
    serve_single(factory)
    indexer = FakeIndexerSearch(sites=(MIKAN_SITE,))
    factory.indexer_search_ = indexer
    await arrange_indexer(session)
    return factory, indexer, clock, route.id


async def test_the_poller_the_backfill_and_the_search_share_one_budget(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    """票 20 驗收第一條：三者在同一站上加起來不超過。

    預算 10：缺集搜尋一批 5 個、輪一輪 4 個、綁定時補舊集 1 個，正好用完；15 分鐘後的下一輪
    一個請求都沒出去，延後的是輪詢。
    """
    factory, indexer, clock, route_id = await mikan_on_both_sides(session, roots, limit=10)
    media_id = "tv:262000"
    searched = await search_torrents(session, factory, media_id=media_id, missing=True)
    feed = await add_feed(session, url=FEED_URL, name="Mikan")
    await poll_feed(session, factory, feed.id, now=clock.now)
    series = await series_by_key(session, KIMI_KEY)
    await bind_series(
        session, factory, series.id, media_id=media_id, route_id=route_id, user_id=None
    )

    clock.now = NOW + timedelta(minutes=16)
    later = await poll_feed(session, factory, feed.id, now=clock.now)

    assert searched.problem is None and len(indexer.queries) == 5
    # 每一站都放得下時不限定站：與沒有預算時問的是同一批。
    assert {query.indexer_ids for query in indexer.queries} == {()}
    assert searched.skipped == ()
    assert used(factory) == {BudgetUse.POLL: 4, BudgetUse.BACKFILL: 1, BudgetUse.SEARCH: 5}
    assert went_out(factory, indexer) == 10
    assert later.failed and MIKAN in later.failed
    assert deferred(factory) == {BudgetUse.POLL}


async def test_a_search_skips_the_site_out_of_budget_and_asks_the_rest(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    """M4 票 77：輪詢用掉 Mikan 大半，搜尋的一批在 Mikan 放不下、在 Nyaa 放得下——只問 Nyaa，
    結果說出 Mikan 這次沒問、何時放得下。Mikan 一格都不多佔。"""
    factory, indexer, clock, _ = await mikan_on_both_sides(session, roots, limit=8)
    indexer.sites_ = (MIKAN_SITE, NYAA_SITE)
    feed = await add_feed(session, url=FEED_URL, name="Mikan")
    await poll_feed(session, factory, feed.id, now=clock.now)

    clock.now = NOW + timedelta(minutes=5)
    view = await search_torrents(session, factory, media_id="tv:262000", missing=True)

    assert view.problem is None
    assert [query.indexer_ids for query in indexer.queries] == [(NYAA_SITE.indexer_id,)] * 5
    assert view.skipped == (
        SkippedSite(site=MIKAN, indexers=("Mikan",), until=NOW + timedelta(hours=1)),
    )
    assert used(factory, NYAA) == {BudgetUse.SEARCH: 5}
    assert BudgetUse.SEARCH not in used(factory)
    assert deferred(factory) == {BudgetUse.SEARCH}


async def test_a_search_that_fits_nowhere_asks_nothing_and_says_when(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    """每一站都放不下才整批等：一個查詢都不問，說得出最早何時放得下（最早空出來的那一站），
    不帶後端的原文（M4 票 77：畫面自己說）。"""
    factory, indexer, clock, _ = await mikan_on_both_sides(session, roots, limit=8)
    indexer.sites_ = (MIKAN_SITE, NYAA_SITE)
    feed = await add_feed(session, url=FEED_URL, name="Mikan")
    await poll_feed(session, factory, feed.id, now=clock.now)
    clock.now = NOW + timedelta(minutes=10)
    factory.budget.take(NYAA, 6, BudgetUse.POLL)

    clock.now = NOW + timedelta(minutes=15)
    view = await search_torrents(session, factory, media_id="tv:262000", missing=True)

    assert indexer.queries == []
    assert view.problem is IndexerProblem.BUDGET_EXHAUSTED
    assert view.retry_at == NOW + timedelta(hours=1)
    assert view.detail == ""
    assert {skipped.site: skipped.until for skipped in view.skipped} == {
        MIKAN: NOW + timedelta(hours=1),
        NYAA: NOW + timedelta(minutes=10, hours=1),
    }
    assert went_out(factory, indexer) <= 8
    assert deferred(factory) == {BudgetUse.SEARCH}


async def test_a_backfill_that_does_not_fit_waits_for_the_next_round(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    """每日補漏被擋：`backfilled_at` 不動（下一輪再試），Feed 上說得出是預算。"""
    factory, _, clock, route_id = await mikan_on_both_sides(session, roots, limit=6)
    feed = await add_feed(session, url=FEED_URL, name="Mikan")
    await poll_feed(session, factory, feed.id, now=clock.now)
    series = await series_by_key(session, KIMI_KEY)
    await bind_series(
        session,
        factory,
        series.id,
        media_id="tv:262000",
        route_id=route_id,
        user_id=None,
    )
    # 綁定時那一次補舊集讀到了；讓它像是一天前的事，這一輪就輪到每日補漏。
    row = await session.get(RssSeries, series.id)
    assert row is not None
    row.backfilled_at = None
    await session.commit()

    clock.now = NOW + timedelta(minutes=16)
    await poll_feed(session, factory, feed.id, now=clock.now)

    await session.refresh(row)
    assert row.backfilled_at is None
    polled = await session.get(RssFeed, feed.id)
    assert polled is not None and MIKAN in polled.last_error
    assert used(factory) == {BudgetUse.POLL: 5, BudgetUse.BACKFILL: 1}
    assert deferred(factory) == {BudgetUse.BACKFILL}


async def test_a_lookup_that_does_not_fit_is_tried_again_rather_than_given_up(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    """自動綁定只在 Series 長出來的那一輪認（brief §15）——被預算擋下的不算「查不到」：
    理由是延後、不是 `lookup_failed`，下一輪預算放得下時再認。"""
    route, factory = await moored(session, roots)
    clock = Clock(NOW)
    factory.budget = RequestBudget(limit=3, now=clock)
    serve(factory, FEED_URL, RELEASES)
    feed = await add_feed(session, url=FEED_URL, name="Mikan")

    await poll_feed(session, factory, feed.id, now=clock.now)

    (waiting,) = [row for row in await list_series(session) if row.key == KIMI_KEY]
    assert [reason.code for reason in waiting.reasons] == [BindReasonCode.LOOKUP_DEFERRED]
    assert waiting.media_id is None
    # 長出來的那一輪只認一次：同一輪不回頭再撞一次預算（code review 抓到）。
    (usage,) = factory.budget.usage()
    assert [(one.use, one.refused) for one in usage.deferred] == [(BudgetUse.POLL, 1)]

    clock.now = NOW + timedelta(hours=1, minutes=1)
    await poll_feed(session, factory, feed.id, now=clock.now)

    (bound,) = [row for row in await list_series(session) if row.key == KIMI_KEY]
    assert bound.media_id == "tv:262000"
    assert bound.route_id == route.id
