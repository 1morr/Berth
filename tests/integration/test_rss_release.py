"""逐筆放行被排除的 Feed Item（brief §15「全部接受，只排除」、M4 票 111）。

情境是票面那一條：Mikan 單一 feed 只有一筆 `[01-12 合集]`，被全域的「不自動下載合集」擋成
`excluded`。放行**當場送出**，走與 `_submit_waiting` 同一支 `_submit`，所以送單時的去重照常；
送不出就留在 `excluded` 帶著原文。拒絕各是一種 `RssRefusal`，Item 不變。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.domain import FeedItemStatus, JobTrigger, RssRefusal, SkipCode, skipped
from berth.models import Job, Media, Route, RssFeed, RssItem, RssSeries
from berth.services.rss import (
    RssRejectedError,
    bind_series,
    list_items,
    poll_feed,
    release_item,
)
from tests.integration.factories import FakeClientFactory
from tests.integration.test_rss import FEED_URL, KIMI_KEY, NOW, harbour, routed_feed, series_by_key
from tests.integration.test_rss_screen import items_titled, reason, release, serve

pytestmark = pytest.mark.asyncio

URL = FEED_URL + "&x=1"
COLLECTION = release(370, "喵萌奶茶屋&LoliHouse", "[01-12 合集]")
EPISODE = release(370, "喵萌奶茶屋&LoliHouse", "12")


async def held(
    session: AsyncSession, roots: dict[str, Path], *, bind: bool = True
) -> tuple[RssItem, RssSeries, FakeClientFactory, Media, Route]:
    """合集與第 12 集來自同一個字幕組；合集被全域預設擋下。`bind` 時 RSS Series 綁好了。"""
    media, route, factory = await harbour(session, roots)
    serve(factory, URL, [COLLECTION, EPISODE])
    feed = await routed_feed(session, url=URL, name="Mikan")
    await poll_feed(session, factory, feed.id, now=NOW)
    series = await series_by_key(session, KIMI_KEY)
    if bind:
        await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )
    (row,) = await items_titled(session, COLLECTION.title)
    assert row.status is FeedItemStatus.EXCLUDED
    return row, series, factory, media, route


async def snapshot(session: AsyncSession, item_id: int) -> tuple[object, ...]:
    row = await session.get(RssItem, item_id, populate_existing=True)
    assert row is not None
    return (row.status, row.skip_json, row.job_hash, row.error)


class TestReleased:
    async def test_it_is_sent_as_an_rss_job_of_its_series(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        row, series, factory, media, route = await held(session, roots)
        assert await blocked(session, row.id) is None

        view = await release_item(session, factory, row.id)

        assert (view.status, view.job_hash, view.skip, view.error) == (
            FeedItemStatus.DOWNLOADED,
            COLLECTION.hash,
            None,
            "",
        )
        job = await session.get(Job, COLLECTION.hash)
        assert job is not None
        assert (job.trigger, job.trigger_ref, job.media_id, job.route_id) == (
            JobTrigger.RSS,
            str(series.id),
            media.id,
            route.id,
        )
        assert await snapshot(session, row.id) == (
            FeedItemStatus.DOWNLOADED,
            None,
            COLLECTION.hash,
            "",
        )

    async def test_the_same_torrent_sent_before_is_a_duplicate_and_not_sent_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        row, _, factory, media, route = await held(session, roots)
        session.add(
            Job(
                hash=COLLECTION.hash,
                name=COLLECTION.title,
                source_url="",
                media_id=media.id,
                route_id=route.id,
                trigger=JobTrigger.MANUAL,
            )
        )
        await session.commit()
        sent = len(factory.qbittorrent_.added)

        view = await release_item(session, factory, row.id)

        assert (view.status, view.skip, view.job_hash) == (
            FeedItemStatus.DUPLICATE,
            skipped(SkipCode.SAME_TORRENT),
            COLLECTION.hash,
        )
        assert len(factory.qbittorrent_.added) == sent

    async def test_a_refused_submission_leaves_it_excluded_with_the_reason(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """不放回 `matched` 等下一輪：留在 `excluded`，理由照舊，帶著送單那一頭的原文。"""
        row, _, factory, _, _ = await held(session, roots)
        factory.torrent_.error = ServiceUnavailableError("GET mikanani.me: connection refused")

        view = await release_item(session, factory, row.id)

        assert view.status is FeedItemStatus.EXCLUDED
        assert view.skip == skipped(SkipCode.NOT_SINGLE)
        assert view.error.startswith("source_unavailable")
        refreshed = await session.get(RssItem, row.id, populate_existing=True)
        assert refreshed is not None
        assert refreshed.status is FeedItemStatus.EXCLUDED
        assert reason(refreshed) == skipped(SkipCode.NOT_SINGLE)
        assert await session.get(Job, COLLECTION.hash) is None


async def blocked(session: AsyncSession, item_id: int) -> RssRefusal | None:
    """清單上那一列帶的 `release_blocked`：按鈕停用時說的就是它。"""
    (view,) = [one for one in await list_items(session) if one.id == item_id]
    return view.release_blocked


class TestRefused:
    """每一種拒絕都在改任何東西之前：Item 不變、沒有 Job。"""

    async def test_an_item_not_excluded(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory, _, _ = await held(session, roots)
        (sent,) = await items_titled(session, EPISODE.title)
        assert sent.status is FeedItemStatus.DOWNLOADED
        before = await snapshot(session, sent.id)

        with pytest.raises(RssRejectedError) as refused:
            await release_item(session, factory, sent.id)

        assert refused.value.reason is RssRefusal.ITEM_NOT_EXCLUDED
        assert await blocked(session, sent.id) is RssRefusal.ITEM_NOT_EXCLUDED
        assert await snapshot(session, sent.id) == before

    async def test_a_series_not_bound_yet(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        row, _, factory, _, _ = await held(session, roots, bind=False)
        before = await snapshot(session, row.id)

        with pytest.raises(RssRejectedError) as refused:
            await release_item(session, factory, row.id)

        assert refused.value.reason is RssRefusal.SERIES_UNBOUND
        assert await blocked(session, row.id) is RssRefusal.SERIES_UNBOUND
        assert await snapshot(session, row.id) == before
        assert factory.qbittorrent_.added == []

    async def test_a_feed_still_in_its_preview(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """搜尋類 feed 第一輪還沒選。Mikan 一加就算選過，這裡清掉 `primed_at` 造出那個狀態。"""
        row, _, factory, _, _ = await held(session, roots)
        await session.execute(update(RssFeed).values(primed_at=None))
        await session.commit()
        sent = len(factory.qbittorrent_.added)
        before = await snapshot(session, row.id)

        with pytest.raises(RssRejectedError) as refused:
            await release_item(session, factory, row.id)

        assert refused.value.reason is RssRefusal.FEED_UNPRIMED
        assert await blocked(session, row.id) is RssRefusal.FEED_UNPRIMED
        assert await snapshot(session, row.id) == before
        assert len(factory.qbittorrent_.added) == sent

    async def test_a_missing_item(self, session: AsyncSession, roots: dict[str, Path]) -> None:
        _, _, factory = await harbour(session, roots)

        with pytest.raises(RssRejectedError) as refused:
            await release_item(session, factory, 404)

        assert refused.value.reason is RssRefusal.ITEM_MISSING
