"""Mikan 的補舊集與每日補漏（M3 票 12、brief §15「補舊集」、plan §3.2 `rss_poller`）。

聚合 feed 只有最近的集數：錄下來的那一份裡《与你相恋》喵萌奶茶屋&LoliHouse 只剩 11、12，同一時間的
單一 feed（`/RSS/Bangumi?bangumiId=4009&subgroupid=370`）是 01–12。中途訂閱的作品在綁定那一刻讀
單一 feed 補齊，之後每天再讀一次，接住 Berth 停機期間被聚合 feed 捲掉的那幾集。

補下載與一般送單同一條路：寫成那個聚合 Feed 的 Item（`(feed_id, guid)` 去重、同樣看排除條件），
由 `_submit_waiting` 送出（`trigger = rss`）。
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.rss.mikan import parse_feed
from berth.domain import (
    FeedItemStatus,
    JobState,
    JobTrigger,
    PlanAction,
    SkipCode,
    SkipReason,
    Tags,
)
from berth.models import Job, LedgerEntry, Media, Route, RssFeed, RssItem, RssSeries
from berth.services.rss import add_feed, bind_series, delete_feed, poll_feed, unbind_series
from tests.integration.factories import FakeClientFactory
from tests.integration.test_rss import FEED_URL, KIMI, KIMI_KEY, NOW, harbour, series_by_key
from tests.integration.test_rss_auto_bind import moored
from tests.integration.test_rss_screen import (
    SINGLE,
    SINGLE_URL,
    Release,
    release,
    serve,
    serve_single,
)

pytestmark = pytest.mark.asyncio

#: 單一 feed 的 01–12，舊的在前。
SEASON = tuple(reversed(parse_feed(SINGLE)))
#: 聚合 feed 沒帶到的那十集。
OLDER = SEASON[:10]


def episode(number: int) -> str:
    return SEASON[number - 1].info_hash


async def rss_jobs(session: AsyncSession) -> set[str]:
    return set(await session.scalars(select(Job.hash).where(Job.trigger == JobTrigger.RSS)))


async def item_of(session: AsyncSession, info_hash: str) -> RssItem:
    (row,) = await session.scalars(select(RssItem).where(RssItem.info_hash == info_hash))
    return row


def skip_of(row: RssItem) -> SkipCode | None:
    return SkipReason.model_validate(row.skip_json).code if row.skip_json else None


async def subscribed(
    session: AsyncSession, roots: dict[str, Path]
) -> tuple[Media, Route, FakeClientFactory, int, int]:
    """聚合 feed 輪過一輪：《与你相恋》11、12 待綁定；單一 feed 的 01–12 在替身上。

    回（作品、Route、替身、Feed id、RSS Series id）。
    """
    media, route, factory = await harbour(session, roots)
    serve_single(factory)
    feed = await add_feed(session, url=FEED_URL, name="Mikan")
    await poll_feed(session, factory, feed.id, now=NOW)
    series = await series_by_key(session, KIMI_KEY)
    return media, route, factory, feed.id, series.id


class TestBackfillOnBinding:
    async def test_binding_sends_every_episode_the_library_lacks(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """M3 驗收第二條前半：中途訂閱的一部補齊舊集。已經有 Job 的（第 3 集，手動送過）與
        帳本已有的（第 5 集，另一個 hash 的同一個發佈）跳過，其餘九集與聚合 feed 的兩集都送。"""
        media, route, factory, feed_id, series_id = await subscribed(session, roots)
        session.add(
            Job(
                hash=episode(3),
                name=SEASON[2].title,
                source_url="",
                media_id=media.id,
                route_id=route.id,
                state=JobState.IMPORTED,
                trigger=JobTrigger.MANUAL,
            )
        )
        reupload = "e" * 40
        session.add(
            Job(
                hash=reupload,
                name=SEASON[4].title,
                source_url="",
                media_id=media.id,
                route_id=route.id,
                state=JobState.IMPORTED,
                trigger=JobTrigger.MANUAL,
            )
        )
        name = "Kimishinu - S01E05 [LoliHouse][1080p].mkv"
        session.add(
            LedgerEntry(
                job_hash=reupload,
                source_rel_path=name,
                source_abs_path=f"/data/torrent/complete/anime/{name}",
                source_inode="1",
                source_dev="1",
                target_path=f"{route.target_path}/{media.folder_name}/Season 01/{name}",
                target_inode="1",
                media_id=media.id,
                season=1,
                episode_start=5,
                tags_json=Tags(resolution="1080p", group="LoliHouse").model_dump(mode="json"),
                action=PlanAction.IMPORT,
            )
        )
        await session.commit()

        bound = await bind_series(
            session, factory, series_id, media_id=media.id, route_id=route.id, user_id=1, now=NOW
        )

        sent = {item.info_hash for item in SEASON} - {episode(3), episode(5)}
        assert await rss_jobs(session) == sent
        assert bound.submitted == 10
        assert skip_of(await item_of(session, episode(3))) is SkipCode.SAME_TORRENT
        assert skip_of(await item_of(session, episode(5))) is SkipCode.IN_LIBRARY
        # 補下來的寫成那個聚合 Feed 的 Item：之後聚合 feed 帶到同一個 hash 時認得出見過。
        rows = list(await session.scalars(select(RssItem).where(RssItem.series_id == series_id)))
        assert {row.feed_id for row in rows} == {feed_id}
        assert len(rows) == 12
        series = await session.get(RssSeries, series_id)
        assert series is not None and series.backfilled_at == NOW

    async def test_unchecking_sends_only_what_the_feed_carried(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """人工綁定時取消勾選：只送聚合 feed 帶到的那兩集，單一 feed 裡更舊的記成略過——
        之後的每日補漏才不會把它們當成新的送出去。"""
        media, route, factory, _, series_id = await subscribed(session, roots)

        bound = await bind_series(
            session,
            factory,
            series_id,
            media_id=media.id,
            route_id=route.id,
            user_id=1,
            backfill=False,
            now=NOW,
        )

        assert bound.submitted == 2
        assert await rss_jobs(session) == {item.info_hash for item in KIMI}
        for item in OLDER:
            assert (await item_of(session, item.info_hash)).status is FeedItemStatus.PASSED

        # 隔天的補漏也不送它們。
        await poll_feed(
            session,
            factory,
            (await item_of(session, episode(1))).feed_id,
            now=NOW + timedelta(days=1),
        )
        assert await rss_jobs(session) == {item.info_hash for item in KIMI}

    async def test_unchecking_holds_even_when_the_single_feed_cannot_be_read(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """取消勾選是記在 RSS Series 上的決定（`passed_before`），不是那一刻讀到的那幾筆：讀不到
        單一 feed 照樣綁，下一輪讀到的舊集記成略過。"""
        media, route, factory, feed_id, series_id = await subscribed(session, roots)
        page = factory.rss_.pages.pop(SINGLE_URL)

        bound = await bind_series(
            session,
            factory,
            series_id,
            media_id=media.id,
            route_id=route.id,
            user_id=1,
            backfill=False,
            now=NOW,
        )
        factory.rss_.pages[SINGLE_URL] = page
        await poll_feed(session, factory, feed_id, now=NOW + timedelta(minutes=15))

        assert bound.submitted == 2
        assert await rss_jobs(session) == {item.info_hash for item in KIMI}
        for item in OLDER:
            assert (await item_of(session, item.info_hash)).status is FeedItemStatus.PASSED

    async def test_what_was_passed_stays_passed_in_another_feed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """同一個 RSS Series 也在第二個 Mikan Feed 裡，而當初補舊集的那個 Feed 刪掉了（連它的 Item
        一起）：之後在第二個 Feed 補漏，取消勾選的那幾集照樣不送。"""
        media, route, factory, feed_id, series_id = await subscribed(session, roots)
        await bind_series(
            session,
            factory,
            series_id,
            media_id=media.id,
            route_id=route.id,
            user_id=1,
            backfill=False,
            now=NOW,
        )
        second_url = FEED_URL + "&second=1"
        factory.rss_.pages[second_url] = factory.rss_.pages[FEED_URL]
        second = await add_feed(session, url=second_url, name="Mikan 2")
        await poll_feed(session, factory, second.id, now=NOW)
        await delete_feed(session, feed_id)

        await poll_feed(session, factory, second.id, now=NOW + timedelta(days=1))

        assert await rss_jobs(session) == {item.info_hash for item in KIMI}
        rows = list(await session.scalars(select(RssItem).where(RssItem.feed_id == second.id)))
        older = {item.info_hash for item in OLDER}
        assert {row.status for row in rows if row.info_hash in older} == {FeedItemStatus.PASSED}

    async def test_unchecking_without_a_feed_is_remembered_for_later(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Feed 刪掉了、只剩待綁定的 RSS Series 時取消勾選綁定：之後重新加回 Feed，
        補漏照那個決定走。"""
        media, route, factory, feed_id, series_id = await subscribed(session, roots)
        await delete_feed(session, feed_id)
        await bind_series(
            session,
            factory,
            series_id,
            media_id=media.id,
            route_id=route.id,
            user_id=1,
            backfill=False,
            now=NOW,
        )

        again = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, again.id, now=NOW + timedelta(hours=1))

        assert await rss_jobs(session) == {item.info_hash for item in KIMI}
        for item in OLDER:
            assert (await item_of(session, item.info_hash)).status is FeedItemStatus.PASSED

    async def test_binding_again_with_backfill_sends_what_was_passed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """取消勾選綁過、解除，再勾著綁一次：這一次要的是整季，當初略過的那幾集送出去。"""
        media, route, factory, _, series_id = await subscribed(session, roots)
        await bind_series(
            session,
            factory,
            series_id,
            media_id=media.id,
            route_id=route.id,
            user_id=1,
            backfill=False,
            now=NOW,
        )
        await unbind_series(session, series_id)

        again = await bind_series(
            session, factory, series_id, media_id=media.id, route_id=route.id, user_id=1, now=NOW
        )

        assert again.submitted == 10
        assert await rss_jobs(session) == {item.info_hash for item in SEASON}
        series = await session.get(RssSeries, series_id)
        assert series is not None and series.passed_before is None

    async def test_a_backfill_that_cannot_read_is_tried_next_round(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """勾選時讀不到單一 feed 不擋綁定（聚合 feed 的兩集照送），下一輪輪詢再補。"""
        media, route, factory, feed_id, series_id = await subscribed(session, roots)
        page = factory.rss_.pages.pop(SINGLE_URL)

        bound = await bind_series(
            session, factory, series_id, media_id=media.id, route_id=route.id, user_id=1, now=NOW
        )
        assert bound.submitted == 2
        series = await session.get(RssSeries, series_id)
        assert series is not None and series.backfilled_at is None

        factory.rss_.pages[SINGLE_URL] = page
        later = NOW + timedelta(minutes=15)
        polled = await poll_feed(session, factory, feed_id, now=later)

        assert polled.submitted == 10
        assert await rss_jobs(session) == {item.info_hash for item in SEASON}
        series = await session.get(RssSeries, series_id, populate_existing=True)
        assert series is not None and series.backfilled_at == later

    async def test_backfilled_items_pass_the_exclusions(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """補舊集不繞過排除條件：單一 feed 裡的合集照樣被全域那一層擋下（brief §15）。"""
        media, route, factory, _, series_id = await subscribed(session, roots)
        batch = Release(
            370,
            "[喵萌奶茶屋&LoliHouse] 与你相恋到生命尽头 / Kimi ga Shinu made Koi wo Shitai "
            "[01-12 合集][WebRip 1080p HEVC-10bit AAC]",
        )
        ten = release(370, "喵萌奶茶屋&LoliHouse", "10")
        serve(factory, SINGLE_URL, [batch, ten])

        await bind_series(
            session, factory, series_id, media_id=media.id, route_id=route.id, user_id=1
        )

        row = await item_of(session, batch.hash)
        assert (row.status, skip_of(row)) == (FeedItemStatus.EXCLUDED, SkipCode.NOT_SINGLE)
        assert batch.hash not in await rss_jobs(session)
        assert ten.hash in await rss_jobs(session)

    async def test_an_automatic_binding_backfills_too(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """自動綁定（票 09）照預設全補：長出來的那一輪綁上、同一輪補齊。"""
        _, factory = await moored(session, roots)
        serve_single(factory)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        polled = await poll_feed(session, factory, feed.id, now=NOW)

        assert polled.bound == 1
        assert await rss_jobs(session) == {item.info_hash for item in SEASON}
        series = await series_by_key(session, KIMI_KEY)
        assert series.backfilled_at == NOW


def feeds_read(factory: FakeClientFactory) -> list[str]:
    """讀過的 feed，番組頁不算：其餘十部的番組頁連不上，照重認的節奏再讀（M4 票 14），
    不是補漏的事。"""
    return [url for url in factory.rss_.requested if "/Home/Bangumi/" not in url]


class TestDailyBackfill:
    async def test_an_episode_the_feed_rolled_past_is_caught_next_day(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """模擬停機：第 13 集在 Berth 停機時出現在聚合 feed、又被捲掉。重新起來之後聚合 feed 裡
        沒有它，單一 feed 有——每日補漏那一輪之後它有 Job。"""
        media, route, factory, feed_id, series_id = await subscribed(session, roots)
        await bind_series(
            session, factory, series_id, media_id=media.id, route_id=route.id, user_id=1, now=NOW
        )
        thirteen = release(370, "喵萌奶茶屋&LoliHouse", "13")
        serve(factory, SINGLE_URL, [thirteen])
        factory.rss_.requested.clear()

        # 不滿一天的那幾輪只讀聚合 feed。其餘十部的番組頁連不上，照重認的節奏再讀（M4 票 14），
        # 不是補漏的事。
        await poll_feed(session, factory, feed_id, now=NOW + timedelta(hours=6))
        assert feeds_read(factory) == [FEED_URL]
        assert thirteen.hash not in await rss_jobs(session)

        factory.rss_.requested.clear()
        polled = await poll_feed(session, factory, feed_id, now=NOW + timedelta(days=1))

        assert polled.submitted == 1
        assert thirteen.hash in await rss_jobs(session)
        # 只讀綁好的那一個 RSS Series 的單一 feed：其餘十個待綁定，不補。
        assert feeds_read(factory) == [FEED_URL, SINGLE_URL]
        row = await session.get(RssFeed, feed_id)
        assert row is not None and row.last_error == ""

    async def test_a_single_feed_that_fails_is_reported_on_the_feed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """每日補漏讀不到單一 feed：記在那個聚合 Feed 的 `last_error`（`/rss` 看得到），
        下一輪再試。"""
        media, route, factory, feed_id, series_id = await subscribed(session, roots)
        await bind_series(
            session, factory, series_id, media_id=media.id, route_id=route.id, user_id=1, now=NOW
        )
        del factory.rss_.pages[SINGLE_URL]

        await poll_feed(session, factory, feed_id, now=NOW + timedelta(days=1))

        row = await session.get(RssFeed, feed_id)
        assert row is not None and "connection refused" in row.last_error
        assert KIMI_KEY in row.last_error
        series = await session.get(RssSeries, series_id)
        assert series is not None and series.backfilled_at == NOW
