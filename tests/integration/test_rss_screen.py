"""排除條件三層與去重（brief §15「全部接受，只排除」「處理」、plan §8.5、M3 票 10）。

Feed 除了票 07 錄下來的那兩份（聚合 feed、《与你相恋》喵萌奶茶屋&LoliHouse 的單一 feed），其餘是這裡
照 Mikan 的形狀合成的（`mikan_feed`）：合集、同一集兩個字幕組、同組的 v2 都不在錄下來的那幾份裡。

斷言分五組：三層排除各一條而且同一條件放在哪一層都擋、合集預設與關掉它、規則寫壞時存不進去、
同一個 info hash 從兩個 Feed 來只有一筆 Job、帳本已有同一個版本的不送；最後一組是 M3 驗收第三條：
同一集兩個字幕組、同組 v1 與 v2，四份都入庫並存。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path, PurePosixPath
from xml.sax.saxutils import escape

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.qbittorrent import TorrentFile, TorrentStatus
from berth.adapters.rss.mikan import parse_feed
from berth.adapters.torrent import TorrentSource
from berth.domain import (
    FeedItemStatus,
    JobState,
    JobTrigger,
    RssRefusal,
    SkipCode,
    SkipReason,
    Tags,
    skipped,
)
from berth.models import Job, LedgerEntry, RssFeed, RssItem, RssSeries
from berth.services.downloads import poll_downloads
from berth.services.events import EventHub
from berth.services.hints import JobHints
from berth.services.importer import sweep_imports
from berth.services.plan import sweep_plans
from berth.services.rss import (
    RssRejectedError,
    add_feed,
    bind_series,
    list_items,
    poll_feed,
    read_exclusions,
    set_exclusions,
    set_feed_exclusions,
    set_series_exclusions,
    unbind_series,
)
from tests.conftest import FIXTURES
from tests.integration.factories import FakeClientFactory
from tests.integration.test_rss import (
    FEED_URL,
    ITEMS,
    KIMI,
    KIMI_KEY,
    NOW,
    count,
    harbour,
    run_pipeline,
    series_by_key,
)

pytestmark = pytest.mark.asyncio

KIMI_NAME = "与你相恋到生命尽头 / Kimi ga Shinu made Koi wo Shitai"
#: 錄下來的那一份單一 feed：喵萌奶茶屋&LoliHouse 的《与你相恋》1–12 集，
#: 11、12 與聚合 feed 同一個 hash。
SINGLE_URL = "https://mikanani.me/RSS/Bangumi?bangumiId=4009&subgroupid=370"
SINGLE = (FIXTURES / "http" / "mikan" / "rss-bangumi.4009-370.xml").read_bytes()
#: ANi 那一筆（聚合 feed 裡另一部作品）：三層排除共用的那一條規則擋的就是它。
ANI = next(item for item in ITEMS if item.title.startswith("[ANi]"))


@dataclass(frozen=True, slots=True)
class Release:
    """合成 feed 的一筆：字幕組（Mikan 的字幕組 id）與標題。hash 由標題算。"""

    subgroup: int
    title: str

    @property
    def hash(self) -> str:
        return hashlib.sha1(self.title.encode()).hexdigest()

    @property
    def file(self) -> str:
        """torrent 裡那一個檔案：標題去掉 ` / `（檔名不會有斜線）加副檔名。"""
        return self.title.replace(" / ", " ") + ".mkv"


def release(subgroup: int, group: str, episode: str) -> Release:
    return Release(subgroup, f"[{group}] {KIMI_NAME} - {episode} [WebRip 1080p HEVC-10bit AAC]")


def mikan_feed(releases: list[Release]) -> bytes:
    """照 Mikan 聚合 feed 的形狀：`link` 是單集頁、末段是 info hash，enclosure 是 `.torrent`。"""
    items = "".join(
        f'<item><guid isPermaLink="false">{escape(one.title)}</guid>'
        f"<link>https://mikanani.me/Home/Episode/{one.hash}</link>"
        f"<title>{escape(one.title)}</title>"
        '<torrent xmlns="https://mikanani.me/0.1/">'
        "<pubDate>2026-09-24T16:08:01</pubDate></torrent>"
        f'<enclosure type="application/x-bittorrent" length="1" '
        f'url="https://mikanani.me/Download/20260924/{one.hash}.torrent" /></item>'
        for one in releases
    )
    head = '<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel>'
    return f"{head}{items}</channel></rss>".encode()


def serve(factory: FakeClientFactory, url: str, releases: list[Release]) -> None:
    """把合成的 feed、它每一筆的單集頁（番組 4009 × 那一個字幕組）與 `.torrent` 交給替身。"""
    factory.rss_.pages[url] = mikan_feed(releases)
    for one in releases:
        factory.rss_.pages[f"https://mikanani.me/Home/Episode/{one.hash}"] = (
            f'<a href="/RSS/Bangumi?bangumiId=4009&subgroupid={one.subgroup}" class="mikan-rss">'
        ).encode()
        factory.torrent_.sources[f"https://mikanani.me/Download/20260924/{one.hash}.torrent"] = (
            TorrentSource(info_hash=one.hash, content=f"torrent:{one.hash}".encode())
        )


def serve_single(factory: FakeClientFactory) -> None:
    """錄下來的單一 feed：它的每一筆單集頁都指向同一個 RSS Series（4009 × 370）。"""
    factory.rss_.pages[SINGLE_URL] = SINGLE
    for item in parse_feed(SINGLE):
        factory.rss_.pages.setdefault(
            item.link, b'<a href="/RSS/Bangumi?bangumiId=4009&subgroupid=370" class="mikan-rss">'
        )
        factory.torrent_.sources.setdefault(
            item.torrent_url,
            TorrentSource(info_hash=item.info_hash, content=f"torrent:{item.info_hash}".encode()),
        )


def finish(factory: FakeClientFactory, roots: dict[str, Path], releases: list[Release]) -> None:
    """qBittorrent 替身把收下的合成那幾包「下載完」（`test_rss.finish_downloads` 的合成版）。"""
    client = factory.qbittorrent_
    save_path = Path(roots["complete"]) / "anime"
    by_content = {f"torrent:{one.hash}".encode(): one for one in releases}
    statuses = list(client.torrents)
    known = {status.hash for status in statuses}
    for request in client.added:
        one = by_content.get(request.content)
        if one is None or one.hash in known:
            continue
        (save_path / one.file).parent.mkdir(parents=True, exist_ok=True)
        (save_path / one.file).write_bytes(one.hash.encode())
        stamp = int(NOW.timestamp())
        statuses.append(
            TorrentStatus(
                hash=one.hash,
                name=one.file,
                state="stalledUP",
                category=request.category,
                tags=("berth",),
                progress=1.0,
                completion_on=stamp,
                last_activity=stamp,
                added_on=stamp,
                save_path=str(save_path),
                content_path=str(PurePosixPath(save_path.as_posix()) / one.file),
                total_size=1_400_000_000,
            )
        )
        client.files_by_hash[one.hash] = (
            TorrentFile(index=0, name=one.file, size=1_400_000_000, priority=1, progress=1.0),
        )
    client.torrents = tuple(statuses)


async def pipeline(session: AsyncSession, factory: FakeClientFactory) -> None:
    hub = EventHub()
    await poll_downloads(session, factory.qbittorrent_, hub, JobHints(), now=NOW)
    await sweep_plans(session, factory, hub, now=NOW)
    await sweep_imports(session, factory, hub, now=NOW)


async def items_titled(session: AsyncSession, prefix: str) -> list[RssItem]:
    return list(await session.scalars(select(RssItem).where(RssItem.title.startswith(prefix))))


def reason(row: RssItem) -> SkipReason | None:
    return SkipReason.model_validate(row.skip_json) if row.skip_json is not None else None


class TestThreeLayers:
    """同一條規則（`Baha`：ANi 的片源）放在哪一層都擋，理由說出是哪一層的哪一條。"""

    async def test_a_global_rule(self, session: AsyncSession, roots: dict[str, Path]) -> None:
        _, _, factory = await harbour(session, roots)
        await set_exclusions(session, not_single=True, rules=["Baha"])
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        await poll_feed(session, factory, feed.id, now=NOW)

        (row,) = await items_titled(session, ANI.title)
        assert row.status is FeedItemStatus.EXCLUDED
        assert reason(row) == skipped(SkipCode.GLOBAL_RULE, rule="Baha")

    async def test_a_feed_rule(self, session: AsyncSession, roots: dict[str, Path]) -> None:
        _, _, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await set_feed_exclusions(session, feed.id, ["Baha"])

        await poll_feed(session, factory, feed.id, now=NOW)

        (row,) = await items_titled(session, ANI.title)
        assert row.status is FeedItemStatus.EXCLUDED
        assert reason(row) == skipped(SkipCode.FEED_RULE, rule="Baha")

    async def test_a_series_rule(self, session: AsyncSession, roots: dict[str, Path]) -> None:
        """RSS Series 在第一輪才長出來：規則加上去的那一刻，它還沒送的那幾筆就照新規則看。"""
        _, _, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        (row,) = await items_titled(session, ANI.title)
        assert row.series_id is not None

        await set_series_exclusions(session, row.series_id, ["Baha"])

        await session.refresh(row)
        assert row.status is FeedItemStatus.EXCLUDED
        assert reason(row) == skipped(SkipCode.SERIES_RULE, rule="Baha")

    async def test_other_items_are_untouched(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await harbour(session, roots)
        await set_exclusions(session, not_single=True, rules=["Baha"])
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        await poll_feed(session, factory, feed.id, now=NOW)

        rows = list(await session.scalars(select(RssItem)))
        baha = [row for row in rows if "Baha" in row.title]
        assert {row.status for row in baha} == {FeedItemStatus.EXCLUDED}
        assert {row.status for row in rows if row not in baha} == {FeedItemStatus.UNBOUND}
        assert all(row.skip_json is None for row in rows if row not in baha)

    async def test_an_excluded_item_is_not_sent_when_its_series_is_bound(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)
        await set_series_exclusions(session, series.id, ["- 11 "])

        bound = await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )

        assert bound.submitted == 1
        assert {job.hash for job in await session.scalars(select(Job))} == {KIMI[0].info_hash}

    async def test_loosening_a_rule_does_not_bring_items_back(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """只往前看（brief §15）：拿掉一條規則，之前被它擋下的不會突然全部下載。"""
        _, _, factory = await harbour(session, roots)
        await set_exclusions(session, not_single=True, rules=["Baha"])
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)

        await set_exclusions(session, not_single=True, rules=[])

        (row,) = await items_titled(session, ANI.title)
        await session.refresh(row)
        assert row.status is FeedItemStatus.EXCLUDED

    async def test_the_items_list_says_why(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await set_feed_exclusions(session, feed.id, ["Baha"])
        await poll_feed(session, factory, feed.id, now=NOW)

        (view,) = [row for row in await list_items(session) if row.title == ANI.title]

        assert view.status is FeedItemStatus.EXCLUDED
        assert view.skip == skipped(SkipCode.FEED_RULE, rule="Baha")


class TestNotSingle:
    COLLECTION = release(370, "喵萌奶茶屋&LoliHouse", "[01-12 合集]")
    EPISODE = release(370, "喵萌奶茶屋&LoliHouse", "12")

    async def test_a_collection_is_excluded_by_default(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await harbour(session, roots)
        serve(factory, FEED_URL + "&x=1", [self.COLLECTION, self.EPISODE])
        feed = await add_feed(session, url=FEED_URL + "&x=1", name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)

        bound = await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )

        (row,) = await items_titled(session, self.COLLECTION.title)
        assert (row.status, reason(row)) == (
            FeedItemStatus.EXCLUDED,
            skipped(SkipCode.NOT_SINGLE),
        )
        assert bound.submitted == 1

    async def test_with_the_default_off_a_collection_is_sent(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await harbour(session, roots)
        await set_exclusions(session, not_single=False, rules=[])
        serve(factory, FEED_URL + "&x=1", [self.COLLECTION])
        feed = await add_feed(session, url=FEED_URL + "&x=1", name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)

        bound = await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )

        assert bound.submitted == 1
        assert await session.get(Job, self.COLLECTION.hash) is not None

    async def test_the_default_is_on_until_someone_turns_it_off(
        self, session: AsyncSession
    ) -> None:
        assert (await read_exclusions(session)).not_single is True


class TestBrokenRules:
    """寫壞的規則存不進去，說出原因；不等到輪詢時才炸。"""

    async def test_a_broken_regex_is_refused_with_the_reason(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        with pytest.raises(RssRejectedError) as caught:
            await set_feed_exclusions(session, feed.id, ["720p", "/[简繁/"])

        assert caught.value.reason is RssRefusal.RULE_INVALID
        assert caught.value.detail.startswith("/[简繁/: ")
        assert "unterminated character set" in caught.value.detail
        row = await session.get(RssFeed, feed.id)
        assert row is not None
        assert row.exclude_json == []

    @pytest.mark.parametrize("layer", ["global", "series"])
    async def test_every_layer_refuses_it(
        self, session: AsyncSession, roots: dict[str, Path], layer: str
    ) -> None:
        _, _, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)

        with pytest.raises(RssRejectedError) as caught:
            if layer == "global":
                await set_exclusions(session, not_single=True, rules=["/x/g"])
            else:
                await set_series_exclusions(session, series.id, ["  "])

        assert caught.value.reason is RssRefusal.RULE_INVALID
        assert (await read_exclusions(session)).rules == ()
        await session.refresh(series)
        assert series.exclude_json == []

    async def test_rules_are_stored_trimmed_and_once(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        view = await set_feed_exclusions(session, feed.id, [" 720p", "720p ", "/简体/i"])

        assert view.exclusions == ("720p", "/简体/i")

    async def test_a_missing_feed_or_series_is_named(self, session: AsyncSession) -> None:
        with pytest.raises(RssRejectedError) as feed:
            await set_feed_exclusions(session, 404, [])
        with pytest.raises(RssRejectedError) as series:
            await set_series_exclusions(session, 404, [])

        assert (feed.value.reason, series.value.reason) == (
            RssRefusal.FEED_MISSING,
            RssRefusal.SERIES_MISSING,
        )


class TestSameTorrent:
    """同一個 info hash 從兩個 Feed 來：只有一筆 Job，另一筆是重複、連到那一筆。"""

    async def test_a_later_feed_carrying_the_same_hash_adds_no_job(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await harbour(session, roots)
        serve_single(factory)
        aggregate = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, aggregate.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)
        await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )
        single = await add_feed(session, url=SINGLE_URL, name="Kimi")

        await poll_feed(session, factory, single.id, now=NOW + timedelta(minutes=1))

        assert await count(session, Job) == 12
        sent = [request.content for request in factory.qbittorrent_.added]
        assert len(sent) == len(set(sent)) == 12
        for item in KIMI:
            row = await session.scalar(
                select(RssItem).where(RssItem.feed_id == single.id, RssItem.guid == item.guid)
            )
            assert row is not None
            assert (row.status, row.job_hash) == (FeedItemStatus.DUPLICATE, item.info_hash)
            assert reason(row) == skipped(SkipCode.SAME_TORRENT)

    async def test_two_feeds_seen_before_binding_send_it_once(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """綁定那一刻兩份都還留著：先送的那一份建 Job，另一份是重複。

        票 12 起綁定也補舊集：單一 feed 的 01–10 同時寫進聚合 Feed，所以 12 集每一集都是兩份。"""
        media, route, factory = await harbour(session, roots)
        serve_single(factory)
        for url in (FEED_URL, SINGLE_URL):
            feed = await add_feed(session, url=url, name=url)
            await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)

        bound = await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )

        assert bound.submitted == 12
        assert await count(session, Job) == 12
        duplicates = list(
            await session.scalars(select(RssItem).where(RssItem.status == FeedItemStatus.DUPLICATE))
        )
        assert sorted(row.job_hash for row in duplicates) == sorted(
            item.info_hash for item in parse_feed(SINGLE)
        )

    async def test_a_job_cleared_with_its_records_is_not_fetched_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """使用者連紀錄一起刪掉的那一包，不該從另一個 Feed 被抓回來：另一筆 Item 送過就算。"""
        media, route, factory = await harbour(session, roots)
        serve_single(factory)
        aggregate = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, aggregate.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)
        await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )
        cleared = await session.get(Job, KIMI[0].info_hash)
        assert cleared is not None
        await session.delete(cleared)
        await session.commit()
        single = await add_feed(session, url=SINGLE_URL, name="Kimi")

        await poll_feed(session, factory, single.id, now=NOW + timedelta(minutes=1))

        assert await session.get(Job, KIMI[0].info_hash) is None
        row = await session.scalar(
            select(RssItem).where(RssItem.feed_id == single.id, RssItem.guid == KIMI[0].guid)
        )
        assert row is not None
        assert (row.status, row.job_hash) == (FeedItemStatus.DUPLICATE, "")

    async def test_an_item_is_not_a_duplicate_of_the_job_it_sent_itself(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Job commit 之後、Item 改狀態之前中斷（或綁定與輪詢同時送）：下一次送那一筆時
        Job 已經在了，而它就是這個 RSS Series 送的——認回成已送單，不是重複。"""
        media, route, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)
        await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )
        (row,) = await items_titled(session, KIMI[0].title)
        row.status = FeedItemStatus.MATCHED
        row.job_hash = ""
        await session.commit()

        await poll_feed(session, factory, feed.id, now=NOW + timedelta(minutes=15))

        await session.refresh(row)
        assert (row.status, row.job_hash, row.skip_json) == (
            FeedItemStatus.DOWNLOADED,
            KIMI[0].info_hash,
            None,
        )

    async def test_a_hash_worked_out_on_sending_is_written_back(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """來源不報 hash（acg.rip）的那一筆，送單時算出來的 hash 寫回 Item（plan §8.5）：之後別的
        Feed 帶同一個 hash 來時才比得到它。"""
        media, route, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)
        for row in await items_titled(session, "[喵萌奶茶屋&LoliHouse] 与你相恋"):
            row.info_hash = ""
        await session.commit()

        await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )

        rows = await items_titled(session, "[喵萌奶茶屋&LoliHouse] 与你相恋")
        assert sorted(row.info_hash for row in rows) == sorted(item.info_hash for item in KIMI)

    async def test_a_hash_sent_by_hand_counts_too(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Job 已經在了（手動送單、或刪掉過）：RSS 不再送，也不每一輪撞一次 `job_removed`。"""
        media, route, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)
        session.add(
            Job(
                hash=KIMI[0].info_hash,
                name=KIMI[0].title,
                source_url="",
                media_id=media.id,
                route_id=route.id,
                state=JobState.REMOVED,
                trigger=JobTrigger.MANUAL,
            )
        )
        await session.commit()

        bound = await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )

        assert bound.submitted == 1
        (row,) = await items_titled(session, KIMI[0].title)
        assert (row.status, row.error) == (FeedItemStatus.DUPLICATE, "")


class TestInLibrary:
    """帳本已有同 Media / 季 / 集 / Tags 的不再送（同一個發佈換了 hash 重新上傳，就是這一種）。"""

    async def imported(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> tuple[FakeClientFactory, int]:
        """走完 tracer：《与你相恋》11、12 已經在帳本。回替身與 RSS Series 的 id。"""
        media, route, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)
        await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )
        await run_pipeline(session, factory, roots)
        assert await count(session, LedgerEntry) == 2
        return factory, series.id

    async def test_the_same_release_under_another_hash_is_not_sent(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """帳本那一列的 Tags 是從**檔名**讀的（`[LoliHouse]`），發佈名寫的是
        `[喵萌奶茶屋&LoliHouse]`：所以也比那一筆 Job 的發佈名——標題對標題才比得準。"""
        factory, _ = await self.imported(session, roots)
        again = Release(370, KIMI[0].title)
        assert again.hash != KIMI[0].info_hash
        serve(factory, FEED_URL + "&again=1", [again])
        feed = await add_feed(session, url=FEED_URL + "&again=1", name="Again")
        jobs = await count(session, Job)

        await poll_feed(session, factory, feed.id, now=NOW + timedelta(hours=1))

        (row,) = list(await session.scalars(select(RssItem).where(RssItem.feed_id == feed.id)))
        assert row.status is FeedItemStatus.DUPLICATE
        skip = reason(row)
        assert skip is not None and skip.code is SkipCode.IN_LIBRARY
        assert "S01E12" in str(skip.params["known"])
        assert await count(session, Job) == jobs

    async def test_the_same_tags_on_the_ledger_count_too(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """沒有 Job 的那一列（`rebuild-ledger` 長回來的）只有 Tags 可比。"""
        factory, _ = await self.imported(session, roots)
        entry = await session.scalar(select(LedgerEntry).where(LedgerEntry.episode_start == 12))
        assert entry is not None
        entry.job_hash = None
        entry.tags_json = Tags(resolution="1080p", group="LoliHouse").model_dump(mode="json")
        await session.commit()
        tagged = Release(370, "[LoliHouse] Kimi ga Shinu made Koi wo Shitai - 12 [1080p]")
        serve(factory, FEED_URL + "&again=1", [tagged])
        feed = await add_feed(session, url=FEED_URL + "&again=1", name="Again")

        await poll_feed(session, factory, feed.id, now=NOW + timedelta(hours=1))

        (row,) = list(await session.scalars(select(RssItem).where(RssItem.feed_id == feed.id)))
        assert row.status is FeedItemStatus.DUPLICATE

    async def test_titles_without_a_group_are_not_compared(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """兩個標題都讀不出字幕組時 Tags 可能兩邊都是空的：空對空不算同一個版本。漏擋只是多下載
        一次，擋錯卻是少一集（brief §15）。"""
        factory, _ = await self.imported(session, roots)
        entry = await session.scalar(select(LedgerEntry).where(LedgerEntry.episode_start == 12))
        assert entry is not None and entry.job_hash is not None
        job = await session.get(Job, entry.job_hash)
        assert job is not None
        job.name = "Kimi ga Shinu made Koi wo Shitai - 12"
        await session.commit()
        bare = Release(370, "Kimi ga Shinu made Koi wo Shitai - 12")
        serve(factory, FEED_URL + "&bare=1", [bare])
        feed = await add_feed(session, url=FEED_URL + "&bare=1", name="Bare")

        await poll_feed(session, factory, feed.id, now=NOW + timedelta(hours=1))

        (row,) = list(await session.scalars(select(RssItem).where(RssItem.feed_id == feed.id)))
        assert row.status is FeedItemStatus.DOWNLOADED

    async def test_unbinding_lets_the_in_library_ones_be_judged_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """「媒體庫裡已經有」是對那一部作品說的：綁錯作品時擋下的，改綁之後要重新判斷。"""
        factory, series_id = await self.imported(session, roots)
        again = Release(370, KIMI[0].title)
        serve(factory, FEED_URL + "&again=1", [again])
        feed = await add_feed(session, url=FEED_URL + "&again=1", name="Again")
        await poll_feed(session, factory, feed.id, now=NOW + timedelta(hours=1))

        await unbind_series(session, series_id)

        (row,) = list(await session.scalars(select(RssItem).where(RssItem.feed_id == feed.id)))
        await session.refresh(row)
        assert (row.status, row.skip_json) == (FeedItemStatus.UNBOUND, None)

    async def test_a_v2_is_not_a_duplicate(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory, _ = await self.imported(session, roots)
        v2 = Release(370, KIMI[0].title.replace(" - 12 ", " - 12v2 "))
        serve(factory, FEED_URL + "&v2=1", [v2])
        feed = await add_feed(session, url=FEED_URL + "&v2=1", name="v2")

        await poll_feed(session, factory, feed.id, now=NOW + timedelta(hours=1))

        (row,) = list(await session.scalars(select(RssItem).where(RssItem.feed_id == feed.id)))
        assert (row.status, row.job_hash) == (FeedItemStatus.DOWNLOADED, v2.hash)


class TestVersionsLiveSideBySide:
    """M3 驗收第三條：同一集兩個字幕組、同組 v1 與 v2，四份都入庫並存（brief §7.7、§19）。"""

    async def test_two_groups_and_their_v2s_are_all_imported(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await harbour(session, roots)
        first = [release(370, "LoliHouse", "12"), release(583, "ANi", "12")]
        later = [release(370, "LoliHouse", "12v2"), release(583, "ANi", "12v2")]
        url = FEED_URL + "&versions=1"
        serve(factory, url, first)
        feed = await add_feed(session, url=url, name="Versions")
        await poll_feed(session, factory, feed.id, now=NOW)
        for key in ("mikan:4009:370", "mikan:4009:583"):
            series = await series_by_key(session, key)
            await bind_series(
                session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
            )
        finish(factory, roots, first)
        await pipeline(session, factory)

        # v2 晚一週才出，那時 v1 已經在帳本上。
        serve(factory, url, first + later)
        await poll_feed(session, factory, feed.id, now=NOW + timedelta(days=7))
        finish(factory, roots, first + later)
        await pipeline(session, factory)

        items = list(await session.scalars(select(RssItem).where(RssItem.feed_id == feed.id)))
        assert {row.status for row in items} == {FeedItemStatus.DOWNLOADED}
        ledger = list(await session.scalars(select(LedgerEntry)))
        assert len(ledger) == 4
        assert {(row.season, row.episode_start) for row in ledger} == {(1, 12)}
        folders = {str(PurePosixPath(Path(row.target_path).as_posix()).parent) for row in ledger}
        assert len(folders) == 1
        names = {Path(row.target_path).name for row in ledger}
        assert len(names) == 4
        assert all(Path(row.target_path).exists() for row in ledger)
        series_count = await session.scalar(select(func.count()).select_from(RssSeries))
        assert series_count == 2
