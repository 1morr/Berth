"""從 Media 頁訂閱（M3 票 19、brief §15「從 Media 頁訂閱」）。

次要入口：在詳情頁選一個來源建一條單一 feed，並**預先綁定這部作品**。

- **Mikan**：番組 × 字幕組的單一 feed（`/RSS/Bangumi?bangumiId=&subgroupid=`）。它只有一個
  RSS Series，鍵從網址就知道，所以訂閱當場長出那個 Series、走票 08 的 `bind_series` 綁上，再把讀到的
  整季寫成這個 Feed 的 Item——補舊集照票 12 的規矩（預設全補，取消勾選時綁定之前發佈的記成
  `passed`）。
- **Nyaa / acg.rip**：以作品的標題組搜尋 feed。Feed 記下作品與 Route，它長出的每一個 RSS Series
  （一個字幕組一個）都直接綁上；第一輪照樣停在預覽（票 11），使用者選了才送。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.rss import acgrip
from berth.domain import FeedItemStatus, FeedKind, JobTrigger, Role, RssRefusal
from berth.models import Job, Route, RssFeed, RssItem, RssSeries, User
from berth.services.rss import (
    RssRejectedError,
    add_feed,
    bind_series,
    list_series,
    poll_feed,
    preview_feed,
    subscribe_mikan,
    subscribe_search,
)
from tests.conftest import FIXTURES
from tests.integration.test_rss import KIMI_KEY, NOW, count, harbour, series_by_key
from tests.integration.test_rss_backfill import SEASON, rss_jobs, subscribed
from tests.integration.test_rss_screen import SINGLE_URL, serve_single

pytestmark = pytest.mark.asyncio

TERM = "Kimi ga Shinu made Koi wo Shitai"
ACGRIP_FEED = (FIXTURES / "http" / "acgrip" / "rss-search.kimi-ga-shinu.xml").read_bytes()


async def skipper(session: AsyncSession) -> int:
    """建搜尋 feed 的那個人：Feed 記下他（外鍵），長出的 Series 以他的身分綁。"""
    user = User(jellyfin_user_id="jf-1", name="skipper", role=Role.ADMIN)
    session.add(user)
    await session.commit()
    return user.id


async def feeds(session: AsyncSession) -> list[RssFeed]:
    return list(await session.scalars(select(RssFeed).order_by(RssFeed.id)))


class TestMikan:
    async def test_subscribing_binds_the_series_and_sends_the_whole_season(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """驗收第一條：Feed、RSS Series 已綁定、舊集已送單。"""
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
            name="与你相恋到生命尽头 · LoliHouse",
            now=NOW,
        )

        (feed,) = await feeds(session)
        assert (feed.url, feed.kind, feed.name) == (
            SINGLE_URL,
            FeedKind.MIKAN,
            "与你相恋到生命尽头 · LoliHouse",
        )
        assert feed.primed_at is not None and feed.last_polled_at == NOW
        series = await series_by_key(session, KIMI_KEY)
        assert (series.media_id, series.route_id, series.bound_by) == (media.id, route.id, "1")
        assert series.title_raw == SEASON[-1].title
        assert await rss_jobs(session) == {item.info_hash for item in SEASON}
        assert (done.feed.id, done.series.id, done.series.submitted) == (feed.id, series.id, 12)
        # 鍵從網址就知道：一頁單集頁都不必抓。
        assert factory.rss_.requested == [SINGLE_URL]

    async def test_unchecking_backfill_passes_what_was_out_before(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
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
            backfill=False,
            now=NOW,
        )

        assert done.series.submitted == 0
        assert await rss_jobs(session) == set()
        statuses = set(await session.scalars(select(RssItem.status)))
        assert statuses == {FeedItemStatus.PASSED}

    async def test_the_next_round_of_the_single_feed_lands_in_the_same_series(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """之後的輪詢照一般的路走：新的一集長不出第二個 Series，送出去。"""
        media, route, factory = await harbour(session, roots)
        serve_single(factory)
        factory.rss_.pages[SINGLE_URL] = _feed_without_newest()
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
        assert done.series.submitted == 11

        serve_single(factory)
        await poll_feed(session, factory, done.feed.id, now=NOW)

        assert await count(session, RssSeries) == 1
        assert await rss_jobs(session) == {item.info_hash for item in SEASON}

    async def test_a_series_already_waiting_is_bound_where_it_is(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """聚合 feed 已經帶到它、還在待綁定：綁那一個，不多開一條 Feed（補舊集寫進聚合 Feed）。"""
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

        assert [feed.id for feed in await feeds(session)] == [feed_id]
        assert (done.feed.id, done.series.id) == (feed_id, series_id)
        assert await rss_jobs(session) == {item.info_hash for item in SEASON}

    async def test_a_series_bound_elsewhere_is_refused_and_nothing_is_added(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory, _, series_id = await subscribed(session, roots)
        await bind_series(
            session, factory, series_id, media_id=media.id, route_id=route.id, user_id=1, now=NOW
        )

        with pytest.raises(RssRejectedError) as refused:
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

        assert refused.value.reason is RssRefusal.SERIES_BOUND
        assert len(await feeds(session)) == 1

    async def test_an_unreachable_feed_adds_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """人在場：讀不到就當場說，不留下一條沒讀過的 Feed 與沒有名字的 Series。"""
        media, route, factory = await harbour(session, roots)

        with pytest.raises(RssRejectedError) as refused:
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

        assert refused.value.reason is RssRefusal.FEED_UNREACHABLE
        assert await feeds(session) == []
        assert await count(session, RssSeries) == 0

    async def test_a_disabled_route_adds_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await harbour(session, roots)
        serve_single(factory)
        row = await session.get(Route, route.id)
        assert row is not None
        row.enabled = False
        await session.commit()

        with pytest.raises(RssRejectedError) as refused:
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

        assert refused.value.reason is RssRefusal.ROUTE_DISABLED
        assert await feeds(session) == []
        assert factory.rss_.requested == []


def _feed_without_newest() -> bytes:
    """單一 feed 少了最新那一集（第 12 集）：訂閱之後才出來的那一集。"""
    raw = (FIXTURES / "http" / "mikan" / "rss-bangumi.4009-370.xml").read_text(encoding="utf-8")
    first = raw.index("<item>")
    return (raw[:first] + raw[raw.index("</item>", first) + len("</item>") :]).encode()


class TestSearchFeed:
    async def test_it_is_read_at_once_and_what_it_grows_is_bound_but_waits_for_the_first_round(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """驗收第二條：建 acg.rip 搜尋 feed → 第一輪預覽。長出的 Series 都已經綁在這部作品上，
        所以預覽裡是「會送出」而不是「綁定之後送」；選之前一筆都不送。"""
        media, route, factory = await harbour(session, roots)
        user_id = await skipper(session)
        factory.rss_.pages[acgrip.search_url(TERM)] = ACGRIP_FEED

        feed = await subscribe_search(
            session,
            factory,
            kind=FeedKind.ACGRIP,
            term=TERM,
            media_id=media.id,
            route_id=route.id,
            user_id=user_id,
            now=NOW,
        )

        assert (feed.url, feed.kind, feed.primed_at) == (
            acgrip.search_url(TERM),
            FeedKind.ACGRIP,
            None,
        )
        assert feed.last_polled_at == NOW and feed.items > 0
        grown = list(await session.scalars(select(RssSeries)))
        assert grown
        assert {(row.media_id, row.route_id, row.bound_by) for row in grown} == {
            (media.id, route.id, str(user_id))
        }
        preview = await preview_feed(session, feed.id)
        assert FeedItemStatus.UNBOUND not in {row.status for row in preview}
        assert FeedItemStatus.MATCHED in {row.status for row in preview}
        assert await session.scalar(select(Job.hash).where(Job.trigger == JobTrigger.RSS)) is None

    async def test_series_already_waiting_from_another_feed_are_bound_too(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """另一條搜尋 feed 先長出同一個鍵（標題骨幹 + 字幕組）、還在待綁定：這一條帶到它時也綁。"""
        media, route, factory = await harbour(session, roots)
        user_id = await skipper(session)
        other = "https://acg.rip/.xml?term=Kimi+ga+Shinu"
        factory.rss_.pages[other] = ACGRIP_FEED
        factory.rss_.pages[acgrip.search_url(TERM)] = ACGRIP_FEED
        earlier = await add_feed(session, url=other)
        await poll_feed(session, factory, earlier.id, now=NOW)
        assert {row.media_id for row in await session.scalars(select(RssSeries))} == {None}

        await subscribe_search(
            session,
            factory,
            kind=FeedKind.ACGRIP,
            term=TERM,
            media_id=media.id,
            route_id=route.id,
            user_id=user_id,
            now=NOW,
        )

        rows = list(await session.scalars(select(RssSeries)))
        assert {(row.media_id, row.bound_by) for row in rows} == {(media.id, str(user_id))}

    async def test_a_mikan_address_is_not_a_search_feed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await harbour(session, roots)
        user_id = await skipper(session)

        with pytest.raises(RssRejectedError) as refused:
            await subscribe_search(
                session,
                factory,
                kind=FeedKind.MIKAN,
                term=TERM,
                media_id=media.id,
                route_id=route.id,
                user_id=user_id,
            )

        assert refused.value.reason is RssRefusal.FEED_UNSUPPORTED

    async def test_the_same_search_twice_is_a_duplicate(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await harbour(session, roots)
        user_id = await skipper(session)
        factory.rss_.pages[acgrip.search_url(TERM)] = ACGRIP_FEED
        arguments = {
            "kind": FeedKind.ACGRIP,
            "term": TERM,
            "media_id": media.id,
            "route_id": route.id,
            "user_id": user_id,
        }
        await subscribe_search(session, factory, **arguments)  # type: ignore[arg-type]  # 同一組參數送兩次

        with pytest.raises(RssRejectedError) as refused:
            await subscribe_search(session, factory, **arguments)  # type: ignore[arg-type]  # 同上

        assert refused.value.reason is RssRefusal.FEED_DUPLICATE

    async def test_when_the_route_went_away_what_grows_waits_for_a_person(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """訂閱那一刻讀不到，之後 Route 停用了：長出來的 Series 照一般的路去認作品、留在待綁定。"""
        media, route, factory = await harbour(session, roots)
        user_id = await skipper(session)
        feed = await subscribe_search(
            session,
            factory,
            kind=FeedKind.ACGRIP,
            term=TERM,
            media_id=media.id,
            route_id=route.id,
            user_id=user_id,
            now=NOW,
        )
        assert feed.last_error and feed.items == 0
        row = await session.get(Route, route.id)
        assert row is not None
        row.enabled = False
        await session.commit()
        factory.rss_.pages[acgrip.search_url(TERM)] = ACGRIP_FEED

        await poll_feed(session, factory, feed.id, now=NOW)

        grown = list(await session.scalars(select(RssSeries)))
        assert grown and {row.media_id for row in grown} == {None}


class TestSeriesOfAWork:
    async def test_the_detail_page_lists_the_series_bound_to_that_work(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """驗收第三條：詳情頁列出已綁在這部作品上的 RSS Series——來源、字幕組、是否確認、
        最近一集。"""
        media, route, factory, _, series_id = await subscribed(session, roots)
        await bind_series(
            session, factory, series_id, media_id=media.id, route_id=route.id, user_id=1, now=NOW
        )

        listed = await list_series(session, media_id=media.id)

        assert [row.id for row in listed] == [series_id]
        (row,) = listed
        assert row.source is FeedKind.MIKAN
        assert row.group == "喵萌奶茶屋&LoliHouse"
        assert row.confirmed is False
        newest = max(SEASON, key=lambda item: item.published_at or NOW)
        assert (row.latest_title, row.latest_at) == (newest.title, newest.published_at)
        assert await list_series(session, media_id="tv:1") == ()
