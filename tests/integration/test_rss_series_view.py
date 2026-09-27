"""RSS 頁以作品呈現 Series（M4 票 13、brief §15、plan §2.4）。

`list_series` 的每一列說得出：最近一筆**發佈**的是哪一集（不是長出它的那一筆）、已入庫 / 下載中 /
排除各幾筆、完結了沒（`parser.finished` 的兩條路，照現況算——新的一筆出現就回到清單）；
`list_series_items` 列出它的每一筆。Mikan 的番組名與字幕組名取自已經抓過的番組頁。
"""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.rss.fake import FakeFeedFetcher
from berth.domain import FeedItemStatus, PlanAction, RssRefusal
from berth.models import LedgerEntry, Media
from berth.parser import QUIET_AFTER, SETTLED_AFTER
from berth.services.rss import (
    RssRejectedError,
    SeriesView,
    add_feed,
    bind_series,
    list_series,
    list_series_items,
    poll_feed,
    set_series_exclusions,
)
from tests.integration.test_rss import (
    FEED,
    FEED_URL,
    KIMI,
    KIMI_KEY,
    MIKAN,
    NOW,
    episode_pages,
    harbour,
    kimi_snapshot,
    run_pipeline,
    series_by_key,
)
from tests.integration.test_rss_auto_bind import moored
from tests.integration.test_rss_screen import serve_single

pytestmark = pytest.mark.asyncio

#: 12 那一集：聚合 feed 裡最新的一筆。
TWELVE = KIMI[0]
ELEVEN = KIMI[1]
_ITEM = re.compile(rb"<item>.*?</item>", re.DOTALL)


def items_of(feed: bytes) -> list[bytes]:
    return _ITEM.findall(feed)


def with_items(blocks: list[bytes]) -> bytes:
    """同一份 channel、換成 `blocks` 這幾筆。"""
    head = FEED[: FEED.index(b"<item>")]
    return head + b"".join(blocks) + b"</channel></rss>"


def kimi_blocks() -> list[bytes]:
    return [block for block in items_of(FEED) if TWELVE.info_hash.encode() in block] + [
        block for block in items_of(FEED) if ELEVEN.info_hash.encode() in block
    ]


def thirteen() -> tuple[bytes, str]:
    """12 那一筆照抄成 13：新的 info hash、晚一週發佈。回（`<item>` 原文, 單集頁網址）。"""
    block = kimi_blocks()[0]
    fresh = "13" * 20
    block = block.replace(TWELVE.info_hash.encode(), fresh.encode())
    block = block.replace(b" - 12 [", b" - 13 [").replace(b"2026-09-24T16:08", b"2026-10-01T16:08")
    return block, f"https://mikanani.me/Home/Episode/{fresh}"


async def the_row(session: AsyncSession, **kwargs: object) -> SeriesView:
    return next(
        row
        for row in await list_series(session, **kwargs)  # type: ignore[arg-type]  # 只轉交 now
        if row.key == KIMI_KEY
    )


class TestLatest:
    async def test_latest_is_the_newest_published_not_the_one_it_grew_from(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """驗收：Item 發佈順序與長出順序不同時，「最近」是發佈最新的那一筆。"""
        _, _, factory = await harbour(session, roots)
        # 一輪裡舊的先寫（`_unseen`）：這個 Series 由 11 長出來，12 才是最近發佈的。
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)

        row = await the_row(session)

        assert row.title_raw == ELEVEN.title
        assert (row.latest_title, row.latest_at, row.latest_episode) == (
            TWELVE.title,
            TWELVE.published_at,
            12,
        )


class TestCounts:
    async def test_imported_active_and_excluded(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)
        await set_series_exclusions(session, series.id, [" - 11 "])

        await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )
        sent = await the_row(session)
        assert (sent.imported, sent.active, sent.excluded) == (0, 1, 1)

        await run_pipeline(session, factory, roots)
        done = await the_row(session)
        assert (done.imported, done.active, done.excluded) == (1, 0, 1)


class TestFinished:
    async def test_quiet_for_a_month_is_finished_and_a_new_item_brings_it_back(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """驗收：有新 Item 時回到清單。紀錄不刪，完結只是照現況算出來的。"""
        media, route, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)
        await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )
        assert TWELVE.published_at is not None
        later = TWELVE.published_at + QUIET_AFTER + timedelta(days=1)

        assert not (await the_row(session, now=TWELVE.published_at + QUIET_AFTER)).finished
        assert (await the_row(session, now=later)).finished

        block, link = thirteen()
        factory.rss_.pages[FEED_URL] = with_items([block, *kimi_blocks()])
        factory.rss_.pages[link] = (MIKAN / "home-episode.85c93c23.html").read_bytes()
        await poll_feed(session, factory, feed.id, now=later)

        back = await the_row(session, now=later)
        assert not back.finished
        assert back.latest_episode == 13

    async def test_ended_on_tmdb_and_all_in_the_library_is_finished(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await harbour(session, roots)
        media.tmdb_snapshot_json = (
            kimi_snapshot().model_copy(update={"ended": True}).model_dump(mode="json")
        )
        await session.commit()
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)
        await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )
        await earlier_episodes(session, media, 10)
        assert TWELVE.published_at is not None
        settled = TWELVE.published_at + SETTLED_AFTER + timedelta(hours=1)
        # 在路上的兩集還沒入庫。
        assert not (await the_row(session, now=settled)).finished

        await run_pipeline(session, factory, roots)

        assert (await the_row(session, now=settled)).finished
        # 最後一集才發佈沒多久：新的一筆（不論送了沒）還看得到，一週之後才收起來。
        assert not (await the_row(session, now=NOW)).finished

    async def test_ended_but_an_episode_missing_is_not(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await harbour(session, roots)
        media.tmdb_snapshot_json = (
            kimi_snapshot().model_copy(update={"ended": True}).model_dump(mode="json")
        )
        await session.commit()
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)
        await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )
        await earlier_episodes(session, media, 9)
        await run_pipeline(session, factory, roots)

        assert TWELVE.published_at is not None
        later = TWELVE.published_at + SETTLED_AFTER + timedelta(hours=1)
        assert not (await the_row(session, now=later)).finished


async def earlier_episodes(session: AsyncSession, media: Media, through: int) -> None:
    """第 1 到 `through` 集已經在庫（之前手動入庫的），帳本各一列。"""
    for episode in range(1, through + 1):
        name = f"Kimishinu - S01E{episode:02d}.mkv"
        session.add(
            LedgerEntry(
                job_hash=None,
                source_rel_path=name,
                source_abs_path=f"/data/torrent/complete/anime/{name}",
                source_inode=str(episode),
                source_dev="1",
                target_path=f"/data/library/anime/{media.folder_name}/Season 01/{name}",
                target_inode=str(episode),
                media_id=media.id,
                season=1,
                episode_start=episode,
                action=PlanAction.IMPORT,
            )
        )
    await session.commit()


class TestItemsOfASeries:
    async def test_every_item_newest_published_first_with_its_episode_and_job(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)
        await set_series_exclusions(session, series.id, [" - 11 "])
        await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )

        rows = await list_series_items(session, series.id)

        assert [(row.episode, row.status, row.job_hash) for row in rows] == [
            (12, FeedItemStatus.DOWNLOADED, TWELVE.info_hash),
            (11, FeedItemStatus.EXCLUDED, ""),
        ]

    async def test_a_missing_series_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await harbour(session, roots)
        with pytest.raises(RssRejectedError) as refused:
            await list_series_items(session, 404)
        assert refused.value.reason is RssRefusal.SERIES_MISSING


class TestMikanNames:
    async def test_the_show_page_read_for_binding_leaves_its_names(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """自動綁定讀過番組頁：番組名與這個字幕組的名字記下來，不為了顯示多打 Mikan。"""
        _, factory = await moored(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)

        row = await the_row(session)

        assert (row.mikan_bangumi_name, row.mikan_subgroup_name) == (
            "与你相恋到生命尽头",
            "LoliHouse",
        )

    async def test_without_a_show_page_there_are_no_names(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await harbour(session, roots)
        factory.rss_ = FakeFeedFetcher({FEED_URL: FEED, **episode_pages()})
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)

        row = await the_row(session)

        assert (row.mikan_bangumi_name, row.mikan_subgroup_name) == ("", "")
        assert row.group == "喵萌奶茶屋&LoliHouse"

    async def test_the_single_feed_read_for_backfill_names_the_bangumi(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """feed 本身帶的：單一 feed 的 channel 標題是「Mikan Project - 番組名」，補舊集讀它時
        記下。"""
        media, route, factory = await harbour(session, roots)
        factory.rss_ = FakeFeedFetcher({FEED_URL: FEED, **episode_pages()})
        serve_single(factory)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)
        assert (await the_row(session)).mikan_bangumi_name == ""

        await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )

        assert (await the_row(session)).mikan_bangumi_name == "与你相恋到生命尽头"
