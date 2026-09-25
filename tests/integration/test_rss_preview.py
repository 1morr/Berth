"""Nyaa 與 acg.rip 的 Feed，與新 Feed 的第一輪預覽（M3 票 11、brief §15「補舊集」最後一句）。

搜尋類 feed 第一輪就帶著歷史（acg.rip 一次 30 筆、Nyaa 75 筆，跨好幾個月），所以第一輪不直接送單：
寫下 Item、長出 RSS Series、看過排除條件，然後停在預覽，等使用者選「全部下載」或「只追之後的」。
選完寫 `primed_at`。Mikan 聚合 feed 只有最近的集數，加的那一刻就算選過了。

替身是票 07 錄下來的 acg.rip 與 Nyaa 搜尋 feed。acg.rip 不報 info hash，`.torrent` 替身照網址給
一個假的 hash。
"""

from __future__ import annotations

import hashlib
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.rss.acgrip import parse_feed as parse_acgrip
from berth.adapters.rss.fake import FakeFeedFetcher
from berth.adapters.rss.nyaa import parse_feed as parse_nyaa
from berth.adapters.torrent import TorrentSource
from berth.adapters.torrent_fake import FakeTorrentFetcher
from berth.domain import (
    FeedItemStatus,
    FeedKind,
    JobState,
    JobTrigger,
    PrimeMode,
    RssRefusal,
    SkipCode,
)
from berth.models import Job, Route, RssItem, RssSeries
from berth.parser.binding import title_key
from berth.services.rss import (
    RssRejectedError,
    add_feed,
    bind_series,
    list_feeds,
    poll_feed,
    preview_feed,
    prime_feed,
)
from tests.conftest import FIXTURES
from tests.integration.arrange import arrange, factory_for
from tests.integration.factories import FakeClientFactory
from tests.integration.test_rss import FEED_URL as MIKAN_URL
from tests.integration.test_rss import NOW, anime_route, kimi

pytestmark = pytest.mark.asyncio

ACGRIP_URL = "https://acg.rip/.xml?term=Kimi+ga+Shinu+made"
KAMIINA_URL = "https://acg.rip/.xml?term=Kamiina+Botan"
NYAA_URL = "https://nyaa.si/?page=rss&q=Kamiina+Botan"
ACGRIP = (FIXTURES / "http" / "acgrip" / "rss-search.kimi-ga-shinu.xml").read_bytes()
KAMIINA = (FIXTURES / "http" / "acgrip" / "rss-search.kamiina-botan.xml").read_bytes()
NYAA = (FIXTURES / "http" / "nyaa" / "rss-search.kamiina-botan.xml").read_bytes()

#: 喵萌奶茶屋&LoliHouse《与你相恋到生命尽头》在 acg.rip 那一份裡的第 11、12 集。
LOLIHOUSE = "[喵萌奶茶屋&LoliHouse] 与你相恋到生命尽头"
LOLIHOUSE_KEY = title_key(
    f"{LOLIHOUSE} / Kimi ga Shinu made Koi wo Shitai - 12 [WebRip 1080p HEVC-10bit AAC]"
)

#: 第二輪多出來的第 13 集（真實 feed 的第三筆改集號與 id），新的在前。
EP13 = (
    "<item><title>[喵萌奶茶屋&amp;LoliHouse] 与你相恋到生命尽头 / Kimi ga Shinu made Koi wo Shitai "
    "- 13 [WebRip 1080p HEVC-10bit AAC][简繁日内封字幕]</title>"
    "<pubDate>Thu, 01 Oct 2026 01:08:02 -0700</pubDate>"
    "<link>https://acg.rip/t/364999</link><guid>https://acg.rip/t/364999</guid>"
    '<enclosure url="https://acg.rip/t/364999.torrent" type="application/x-bittorrent"/>'
    "</item>"
)


def with_ep13(feed: bytes) -> bytes:
    head, rest = feed.split(b"<item>", 1)
    return head + EP13.encode() + b"<item>" + rest


def fake_hash(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()


def acgrip_torrents(*feeds: bytes) -> FakeTorrentFetcher:
    """acg.rip 不報 hash：`.torrent` 替身照網址給一個穩定的假 hash，內容逐筆不同。"""
    urls = {item.torrent_url for feed in feeds for item in parse_acgrip(feed)}
    return FakeTorrentFetcher(
        sources={
            url: TorrentSource(info_hash=fake_hash(url), content=f"torrent:{url}".encode())
            for url in urls
        }
    )


async def harbour(
    session: AsyncSession, roots: dict[str, Path], pages: dict[str, bytes]
) -> FakeClientFactory:
    await arrange(session, roots)
    await kimi(session)
    await anime_route(session, roots)
    factory = factory_for(roots)
    factory.rss_ = FakeFeedFetcher(pages)
    factory.torrent_ = acgrip_torrents(ACGRIP, with_ep13(ACGRIP), KAMIINA)
    return factory


async def lolihouse(session: AsyncSession) -> RssSeries:
    row = await session.scalar(select(RssSeries).where(RssSeries.key == LOLIHOUSE_KEY))
    assert row is not None
    return row


async def bind_lolihouse(session: AsyncSession, factory: FakeClientFactory) -> int:
    series = await lolihouse(session)
    route = await session.scalar(select(Route.id))
    assert route is not None
    bound = await bind_series(
        session, factory, series.id, media_id="tv:262000", route_id=route, user_id=1
    )
    return bound.submitted


async def statuses(session: AsyncSession, feed_id: int) -> dict[str, FeedItemStatus]:
    rows = await session.scalars(select(RssItem).where(RssItem.feed_id == feed_id))
    return {row.title: row.status for row in rows}


def job_count(factory: FakeClientFactory) -> int:
    return len(factory.qbittorrent_.added)


class TestTheSources:
    async def test_the_hosts_are_recognised(self, session: AsyncSession) -> None:
        acgrip = await add_feed(session, url=ACGRIP_URL, name="")
        nyaa = await add_feed(session, url=NYAA_URL, name="")

        assert (acgrip.kind, nyaa.kind) == (FeedKind.ACGRIP, FeedKind.NYAA)
        assert (acgrip.name, nyaa.name) == ("acg.rip", "nyaa.si")

    async def test_an_acgrip_feed_grows_one_series_per_group(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await harbour(session, roots, {ACGRIP_URL: ACGRIP})
        feed = await add_feed(session, url=ACGRIP_URL, name="")

        polled = await poll_feed(session, factory, feed.id, now=NOW)

        assert polled.items == 30
        series = await lolihouse(session)
        rows = list(await session.scalars(select(RssItem).where(RssItem.series_id == series.id)))
        assert sorted(row.title.split(" - ")[1][:2] for row in rows) == ["11", "12"]
        # 同一部作品，喵萌奶茶屋&LoliHouse、北宇治、ANi……各是一個 Series。
        assert polled.series > 5

    async def test_a_nyaa_item_keeps_its_hash_and_its_size(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await harbour(session, roots, {NYAA_URL: NYAA})
        feed = await add_feed(session, url=NYAA_URL, name="")

        await poll_feed(session, factory, feed.id, now=NOW)

        first = parse_nyaa(NYAA)[0]
        row = await session.scalar(select(RssItem).where(RssItem.guid == first.guid))
        assert row is not None
        assert (row.info_hash, row.size, row.link) == (first.info_hash, first.size, first.link)


class TestTheFirstRound:
    async def test_a_mikan_feed_needs_no_preview(self, session: AsyncSession) -> None:
        """Mikan 聚合 feed 只有最近的集數（brief §15）：加的那一刻就算選過了。"""
        feed = await add_feed(session, url=MIKAN_URL, name="Mikan")

        assert feed.primed_at is not None

    async def test_a_search_feed_sends_nothing_in_its_first_round(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await harbour(session, roots, {ACGRIP_URL: ACGRIP})
        feed = await add_feed(session, url=ACGRIP_URL, name="")
        assert feed.primed_at is None

        await poll_feed(session, factory, feed.id, now=NOW)
        submitted = await bind_lolihouse(session, factory)

        assert submitted == 0
        assert job_count(factory) == 0
        # 綁好的兩集留在 `matched`，等使用者決定。
        waiting = await statuses(session, feed.id)
        assert [status for title, status in waiting.items() if title.startswith(LOLIHOUSE)] == [
            FeedItemStatus.MATCHED,
            FeedItemStatus.MATCHED,
        ]

    async def test_the_preview_lists_every_item_of_the_first_round(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await harbour(session, roots, {ACGRIP_URL: ACGRIP})
        feed = await add_feed(session, url=ACGRIP_URL, name="")
        await poll_feed(session, factory, feed.id, now=NOW)
        await bind_lolihouse(session, factory)

        preview = await preview_feed(session, feed.id)

        assert len(preview) == 30
        loli = [item for item in preview if item.title.startswith(LOLIHOUSE)]
        assert {item.status for item in loli} == {FeedItemStatus.MATCHED}
        assert all(item.size for item in preview)

    async def test_follow_from_now_passes_over_the_old_and_sends_the_new(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """「只追之後的」之後，第一輪的舊集不送；第二輪多出來的第 13 集送。"""
        factory = await harbour(session, roots, {ACGRIP_URL: ACGRIP})
        feed = await add_feed(session, url=ACGRIP_URL, name="")
        await poll_feed(session, factory, feed.id, now=NOW)
        await bind_lolihouse(session, factory)

        primed = await prime_feed(session, factory, feed.id, mode=PrimeMode.LATER)

        assert primed.feed.primed_at is not None
        assert primed.submitted == 0
        assert primed.passed == 30 - primed.excluded
        assert job_count(factory) == 0
        factory.rss_.pages[ACGRIP_URL] = with_ep13(ACGRIP)
        later = await poll_feed(session, factory, feed.id, now=NOW + timedelta(hours=1))
        assert later.items == 1
        assert later.submitted == 1
        after = await statuses(session, feed.id)
        loli = {
            title.split(" - ")[1][:2]: status
            for title, status in after.items()
            if title.startswith(LOLIHOUSE)
        }
        assert loli["13"] is FeedItemStatus.DOWNLOADED
        assert {loli["11"], loli["12"]} == {FeedItemStatus.PASSED}

    async def test_download_everything_sends_what_the_first_round_held(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await harbour(session, roots, {ACGRIP_URL: ACGRIP})
        feed = await add_feed(session, url=ACGRIP_URL, name="")
        await poll_feed(session, factory, feed.id, now=NOW)
        await bind_lolihouse(session, factory)

        primed = await prime_feed(session, factory, feed.id, mode=PrimeMode.ALL)

        assert primed.submitted == 2
        assert primed.passed == 0
        jobs = list(await session.scalars(select(Job)))
        assert {job.state for job in jobs} == {JobState.SUBMITTED}
        # 還沒綁的 Series 照舊待綁定：綁定之後送（不必再選一次）。
        after = await statuses(session, feed.id)
        assert FeedItemStatus.UNBOUND in after.values()
        assert FeedItemStatus.PASSED not in after.values()

    async def test_a_series_bound_after_download_everything_sends_its_old_items(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await harbour(session, roots, {ACGRIP_URL: ACGRIP})
        feed = await add_feed(session, url=ACGRIP_URL, name="")
        await poll_feed(session, factory, feed.id, now=NOW)
        await prime_feed(session, factory, feed.id, mode=PrimeMode.ALL)

        assert await bind_lolihouse(session, factory) == 2

    async def test_a_decision_made_elsewhere_while_reading_the_feed_wins(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """「只追之後的」要重讀 feed，那幾秒裡另一個分頁先選了「全部下載」：後到的這一個是 409，
        不把對方留給綁定之後送的那幾筆改成略過。"""
        factory = await harbour(session, roots, {ACGRIP_URL: ACGRIP})
        feed = await add_feed(session, url=ACGRIP_URL, name="")
        await poll_feed(session, factory, feed.id, now=NOW)
        sessions = async_sessionmaker(session.bind, expire_on_commit=False)
        fetch = factory.rss_.fetch

        async def elsewhere_first(url: str) -> bytes:
            async with sessions() as other:
                await prime_feed(other, factory, feed.id, mode=PrimeMode.ALL)
            return await fetch(url)

        factory.rss_.fetch = elsewhere_first  # type: ignore[method-assign]  # 在讀 feed 的那一刻插隊

        with pytest.raises(RssRejectedError) as refused:
            await prime_feed(session, factory, feed.id, mode=PrimeMode.LATER)

        assert refused.value.reason is RssRefusal.FEED_PRIMED
        after = await statuses(session, feed.id)
        assert FeedItemStatus.PASSED not in after.values()

    async def test_download_everything_on_a_feed_never_read_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """沒看過的東西不讓人選「全部下載」（shape §2）：畫面不給按，命令本身也不收。"""
        factory = await harbour(session, roots, {ACGRIP_URL: ACGRIP})
        feed = await add_feed(session, url=ACGRIP_URL, name="")

        with pytest.raises(RssRejectedError) as refused:
            await prime_feed(session, factory, feed.id, mode=PrimeMode.ALL)

        assert refused.value.reason is RssRefusal.FEED_UNREAD
        (row,) = await list_feeds(session)
        assert row.primed_at is None

    async def test_a_feed_is_primed_once(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await harbour(session, roots, {ACGRIP_URL: ACGRIP})
        feed = await add_feed(session, url=ACGRIP_URL, name="")
        await poll_feed(session, factory, feed.id, now=NOW)
        await prime_feed(session, factory, feed.id, mode=PrimeMode.LATER)

        with pytest.raises(RssRejectedError) as refused:
            await prime_feed(session, factory, feed.id, mode=PrimeMode.ALL)

        assert refused.value.reason is RssRefusal.FEED_PRIMED

    async def test_follow_from_now_reads_the_feed_again_and_refuses_when_it_cannot(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """「只追之後的」要知道「之前」是哪幾筆：當場再讀一次 feed。讀不到就不決定——否則下一輪
        讀到的整份歷史都會被當成新的。"""
        factory = await harbour(session, roots, {ACGRIP_URL: ACGRIP})
        feed = await add_feed(session, url=ACGRIP_URL, name="")
        factory.rss_.error = ServiceUnavailableError("acg.rip: connection refused")

        with pytest.raises(RssRejectedError) as refused:
            await prime_feed(session, factory, feed.id, mode=PrimeMode.LATER)

        assert refused.value.reason is RssRefusal.FEED_UNREACHABLE
        (row,) = await list_feeds(session)
        assert row.primed_at is None

    async def test_follow_from_now_before_the_first_round_still_passes_over_the_history(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await harbour(session, roots, {ACGRIP_URL: ACGRIP})
        feed = await add_feed(session, url=ACGRIP_URL, name="")

        primed = await prime_feed(session, factory, feed.id, mode=PrimeMode.LATER)

        assert primed.passed + primed.excluded == 30
        assert job_count(factory) == 0


class TestWhatThePreviewShows:
    async def test_collections_in_an_acgrip_search_feed_show_as_excluded(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """M3 驗收「合集被排除」：搜尋 feed 30 筆裡夾著 8 筆合集（研究檔 §6）。"""
        factory = await harbour(session, roots, {KAMIINA_URL: KAMIINA})
        feed = await add_feed(session, url=KAMIINA_URL, name="")
        await poll_feed(session, factory, feed.id, now=NOW)

        preview = await preview_feed(session, feed.id)

        excluded = [item for item in preview if item.status is FeedItemStatus.EXCLUDED]
        assert {item.skip.code for item in excluded if item.skip} == {SkipCode.NOT_SINGLE}
        titles = [item.title for item in excluded]
        assert any("01-12 合集" in title for title in titles)
        assert any("[第01-12話]" in title for title in titles)
        assert any("[01-12][1080p][繁日雙語]" in title for title in titles)
        assert all("- 12 [" not in title for title in titles)

    async def test_a_torrent_already_sent_shows_as_a_duplicate(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Nyaa 報 info hash：手動送過的那一包在預覽裡就說是重複，不必等送單。"""
        factory = await harbour(session, roots, {NYAA_URL: NYAA})
        first = parse_nyaa(NYAA)[0]
        session.add(
            Job(
                hash=first.info_hash,
                name=first.title,
                media_id="tv:262000",
                route_id=1,
                trigger=JobTrigger.MANUAL,
                state=JobState.DOWNLOADING,
            )
        )
        await session.commit()
        feed = await add_feed(session, url=NYAA_URL, name="")
        await poll_feed(session, factory, feed.id, now=NOW)

        preview = await preview_feed(session, feed.id)

        (same,) = [item for item in preview if item.title == first.title]
        assert same.status is FeedItemStatus.DUPLICATE
        assert same.skip is not None
        assert same.skip.code is SkipCode.SAME_TORRENT
        assert same.job_hash == first.info_hash
        # 預覽只是看：那一列在資料庫裡沒被改成重複。
        row = await session.scalar(select(RssItem).where(RssItem.guid == first.guid))
        assert row is not None
        assert row.status is FeedItemStatus.UNBOUND
