"""撤銷一個訂閱（`subscriptions.unsubscribe`，M5 票 11）。

2026-10-24 使用者選定：停掉訂閱，並撤回這個訂閱送出、還沒下載完的 Job；已經下載完的留著。
兩條路：Berth 新建的 Feed 刪掉；就地綁上的 Mikan Series（本來就在聚合 feed 裡待綁定）解綁。
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.domain import FeedItemStatus, JobRefusal, JobState
from berth.models import Job, RssFeed, RssItem, RssSeries
from berth.models.types import utcnow
from berth.services.deletion import withdraw_job
from berth.services.jobs import JobRejectedError
from berth.services.rss import bind_series, subscribe_mikan
from berth.services.subscriptions import unsubscribe
from tests.integration.test_rss import NOW, count, harbour
from tests.integration.test_rss_backfill import SEASON, rss_jobs, subscribed
from tests.integration.test_rss_screen import serve_single

pytestmark = pytest.mark.asyncio


async def subscribe(session: AsyncSession, roots: dict[str, Path]):  # type: ignore[no-untyped-def]  # 三種替身，型別在 harbour
    media, route, factory = await harbour(session, roots)
    serve_single(factory)
    done = await subscribe_mikan(
        session,
        factory,
        bangumi_id=4009,
        subgroup_id=370,
        media_id=media.id,
        route_id=route.id,
        user_id=1,
        now=NOW,
    )
    return media, route, factory, done


class TestAFeedItMade:
    async def test_the_feed_and_its_series_go_and_only_finished_downloads_stay(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory, done = await subscribe(session, roots)
        finished = SEASON[0].info_hash
        await session.execute(
            update(Job).where(Job.hash == finished).values(state=JobState.COMPLETED)
        )
        await session.commit()

        undone = await unsubscribe(session, factory, feed_id=done.feed.id, actor="1")

        assert (undone.removed, undone.kept) == (len(SEASON) - 1, 1)
        assert await count(session, RssFeed) == 0
        # 這個訂閱帶進來的 Series 也刪掉：再訂一次不會撞上 `series_bound`。
        assert await count(session, RssSeries) == 0
        assert await rss_jobs(session) == {finished}
        assert {hash for hash, _ in factory.qbittorrent_.deleted} == {
            item.info_hash for item in SEASON
        } - {finished}

    async def test_an_unreachable_qbittorrent_stops_it_before_the_feed_is_deleted(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """撤銷沒做成：Feed 還在，再按一次會接著做。"""
        _, _, factory, done = await subscribe(session, roots)
        factory.qbittorrent_.error = ServiceUnavailableError("down")

        with pytest.raises(JobRejectedError) as refused:
            await unsubscribe(session, factory, feed_id=done.feed.id, actor="1")

        assert refused.value.reason is not JobRefusal.MOVED_ON
        assert await count(session, RssFeed) == 1


class TestASeriesItBoundWhereItWas:
    async def test_the_aggregate_feed_stays_and_the_series_waits_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory, feed_id, series_id = await subscribed(session, roots)
        done = await subscribe_mikan(
            session,
            factory,
            bangumi_id=4009,
            subgroup_id=370,
            media_id=media.id,
            route_id=route.id,
            user_id=1,
            now=NOW,
        )
        assert not done.feed_created

        undone = await unsubscribe(session, factory, series_id=series_id, actor="1")

        assert (undone.removed, undone.kept) == (len(SEASON), 0)
        assert [row.id for row in await session.scalars(select(RssFeed))] == [feed_id]
        series = await session.get(RssSeries, series_id, populate_existing=True)
        assert series is not None and series.media_id is None
        assert await rss_jobs(session) == set()
        statuses = set(
            await session.scalars(select(RssItem.status).where(RssItem.series_id == series_id))
        )
        assert statuses == {FeedItemStatus.UNBOUND}

        # 撤回的那幾筆回到待綁定：再綁一次照樣送出。
        again = await bind_series(
            session, factory, series_id, media_id=media.id, route_id=route.id, user_id=1, now=NOW
        )
        assert again.submitted == len(SEASON)


class TestRetryAndScope:
    async def test_a_retry_after_qbittorrent_dropped_midway_still_resets_what_was_taken_back(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """撤到一半連不上：前幾筆已經撤回了（Job 清掉了）。再按一次，那幾筆的 Item 照樣回到
        待綁定。"""
        media, route, factory, _, series_id = await subscribed(session, roots)
        await subscribe_mikan(
            session,
            factory,
            bangumi_id=4009,
            subgroup_id=370,
            media_id=media.id,
            route_id=route.id,
            user_id=1,
            now=NOW,
        )
        first = SEASON[0].info_hash
        await withdraw_job(session, factory, first, actor="1")

        undone = await unsubscribe(session, factory, series_id=series_id, actor="1")

        assert undone.removed == len(SEASON) - 1
        statuses = set(
            await session.scalars(select(RssItem.status).where(RssItem.series_id == series_id))
        )
        assert statuses == {FeedItemStatus.UNBOUND}

    async def test_in_place_only_takes_back_what_came_after_the_subscription(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """就地綁定之前，這個 Series 綁過、解綁過，當時送的還在下載：那不是這次訂閱送的，不撤。"""
        media, route, factory, _, series_id = await subscribed(session, roots)
        await subscribe_mikan(
            session,
            factory,
            bangumi_id=4009,
            subgroup_id=370,
            media_id=media.id,
            route_id=route.id,
            user_id=1,
            now=NOW,
        )
        # Job 的 `added_at` 是牆上時間：比它們都晚的那一刻訂閱的，一筆都不是它送的。
        later = utcnow() + timedelta(days=1)

        undone = await unsubscribe(session, factory, series_id=series_id, since=later, actor="1")

        assert (undone.removed, undone.kept) == (0, 0)
        assert await rss_jobs(session) == {item.info_hash for item in SEASON}


class TestWithdrawingOneJob:
    async def test_a_finished_download_is_not_withdrawn(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """送單的撤銷在後端自己守著「還沒下載完」：畫面上的 `undoable` 可能已經過期。"""
        _, _, factory, _ = await subscribe(session, roots)
        done = SEASON[0].info_hash
        await session.execute(update(Job).where(Job.hash == done).values(state=JobState.IMPORTED))
        await session.commit()

        with pytest.raises(JobRejectedError) as refused:
            await withdraw_job(session, factory, done, actor="1")

        assert refused.value.reason is JobRefusal.NOT_UNDOABLE
        assert done in await rss_jobs(session)
