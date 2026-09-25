"""RSS 的 tracer：Mikan 聚合 feed → 待綁定 → 手動綁定 → 入庫（M3 票 08、brief §15、plan §2.4）。

替身是票 07 錄下來的 Mikan 聚合 feed（`tests/fixtures/http/mikan/rss-mybangumi.xml`）。
它的 12 筆裡《与你相恋到生命尽头》喵萌奶茶屋&LoliHouse 有兩集（11、12），單集頁 fixture 是
12 那一集的；其餘各筆的單集頁照同一個形狀合成（`a.mikan-rss` 那一顆），每一筆各算一個 RSS Series。

斷言分四組：整條走得完（帳本有那兩集）、同一個 feed 輪兩次不多東西、綁定那一刻才通向磁碟、
RSS Series 的季號與 offset 規劃時讀得到。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path, PurePosixPath

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.qbittorrent import TorrentFile, TorrentStatus
from berth.adapters.rss.fake import FakeFeedFetcher
from berth.adapters.rss.mikan import parse_feed
from berth.adapters.torrent import TorrentSource
from berth.adapters.torrent_fake import FakeTorrentFetcher
from berth.db import create_session_factory
from berth.domain import (
    CollectionType,
    EpisodeSnapshot,
    EventType,
    FeedItemStatus,
    HealthStatus,
    JobState,
    JobTrigger,
    MediaKind,
    MediaSnapshot,
    RssRefusal,
    SeasonSnapshot,
)
from berth.models import (
    Event,
    Job,
    LedgerEntry,
    Media,
    PlanItem,
    Route,
    RssFeed,
    RssItem,
    RssSeries,
)
from berth.naming import folder_name
from berth.pipeline import RssPoller
from berth.services.downloads import poll_downloads
from berth.services.events import EventHub
from berth.services.hints import JobHints
from berth.services.importer import sweep_imports
from berth.services.plan import sweep_plans
from berth.services.rss import (
    RssRejectedError,
    add_feed,
    bind_series,
    delete_feed,
    list_items,
    list_series,
    poll_due,
    poll_feed,
    unbind_series,
)
from tests.conftest import FIXTURES
from tests.integration.arrange import arrange, factory_for
from tests.integration.factories import FakeClientFactory
from tests.integration.test_reconciler_schedule import ready

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
FEED_URL = "https://mikanani.me/RSS/MyBangumi?token=REDACTED"
MIKAN = FIXTURES / "http" / "mikan"
FEED = (MIKAN / "rss-mybangumi.xml").read_bytes()
ITEMS = parse_feed(FEED)

#: 喵萌奶茶屋&LoliHouse《与你相恋到生命尽头》那兩集：番組 4009 × 字幕組 370。
KIMI_TITLE = "[喵萌奶茶屋&LoliHouse] 与你相恋到生命尽头"
KIMI = tuple(item for item in ITEMS if item.title.startswith(KIMI_TITLE))
KIMI_KEY = "mikan:4009:370"
KIMI_ID = "tv:262000"


def episode_pages() -> dict[str, bytes]:
    """每一筆的單集頁。12 那一集是錄下來的原文，其餘照同一個形狀合成。"""
    pages: dict[str, bytes] = {}
    for index, item in enumerate(ITEMS):
        if item.title.startswith(KIMI_TITLE):
            pages[item.link] = (MIKAN / "home-episode.85c93c23.html").read_bytes()
            continue
        pages[item.link] = (
            f'<p class="bangumi-title"><a href="/RSS/Bangumi?bangumiId={5000 + index}'
            f'&subgroupid=1" class="mikan-rss">RSS</a></p>'
        ).encode()
    return pages


def torrents() -> FakeTorrentFetcher:
    """每一筆的 `.torrent`。內容逐筆不同，qBittorrent 替身靠它認出是哪一包。"""
    return FakeTorrentFetcher(
        sources={
            item.torrent_url: TorrentSource(
                info_hash=item.info_hash, content=f"torrent:{item.info_hash}".encode()
            )
            for item in ITEMS
        }
    )


def kimi_snapshot() -> MediaSnapshot:
    first = date(2026, 7, 2)
    return MediaSnapshot(
        tmdb_id=262000,
        kind=MediaKind.TV,
        title="與妳相戀到生命盡頭",
        # 資料夾名與檔名都從它來。刻意取短的那個叫法：Windows 的 `tmp_path` 很深，完整的英文名
        # 寫兩次（資料夾與檔名）會讓媒體庫那一頭的路徑超過 260 字元（README〈UI 的 Fake 後端〉）。
        title_en="Kimishinu",
        title_original="君が死ぬまで恋をしたい",
        year=2026,
        first_air_date=first,
        titles=("Kimi ga Shinu made Koi wo Shitai", "与你相恋到生命尽头", "與妳相戀到生命盡頭"),
        seasons=(
            SeasonSnapshot(
                season_number=1,
                name="Season 1",
                names=("Season 1",),
                episode_count=12,
                air_date=first,
                episodes=tuple(
                    EpisodeSnapshot(
                        episode_number=number,
                        name=f"Episode {number}",
                        air_date=first + timedelta(days=7 * (number - 1)),
                    )
                    for number in range(1, 13)
                ),
            ),
        ),
    )


async def kimi(session: AsyncSession, *, snapshot: MediaSnapshot | None = None) -> Media:
    """詳情頁打開過的那一列：快照在、資料夾名還跟著標題走（還沒凍結）。"""
    shot = snapshot or kimi_snapshot()
    row = Media(
        id=KIMI_ID,
        tmdb_id=shot.tmdb_id,
        kind=MediaKind.TV,
        title_en=shot.title_en,
        title_original=shot.title_original,
        year=shot.year,
        folder_name=folder_name(shot),
        folder_frozen=False,
        tmdb_snapshot_json=shot.model_dump(mode="json"),
        tmdb_fetched_at=datetime.now(UTC),
    )
    session.add(row)
    await session.commit()
    return row


async def anime_route(session: AsyncSession, roots: dict[str, Path], **overrides: object) -> Route:
    row = Route(
        slug="anime",
        name="Anime",
        jellyfin_library_id="item-2",
        jellyfin_library_name="Anime",
        collection_type=CollectionType.TVSHOWS,
        target_path=str(roots["library"] / "anime"),
        category="berth-anime",
        health_status=HealthStatus.OK,
    )
    for name, value in overrides.items():
        setattr(row, name, value)
    session.add(row)
    await session.commit()
    return row


async def harbour(
    session: AsyncSession, roots: dict[str, Path]
) -> tuple[Media, Route, FakeClientFactory]:
    """精靈跑完、《与你相恋》詳情頁打開過、一條 anime Route；Mikan 與 `.torrent` 都是替身。"""
    await arrange(session, roots)
    media = await kimi(session)
    route = await anime_route(session, roots)
    factory = factory_for(roots)
    factory.rss_ = FakeFeedFetcher({FEED_URL: FEED, **episode_pages()})
    factory.torrent_ = torrents()
    return media, route, factory


async def series_by_key(session: AsyncSession, key: str) -> RssSeries:
    row = await session.scalar(select(RssSeries).where(RssSeries.key == key))
    assert row is not None
    return row


async def count(session: AsyncSession, model: type[object]) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


def release_file(item_title: str) -> str:
    """torrent 裡那一個檔案。發佈名裡有 ` / `，檔名不會有——字幕組上傳的檔名是英文那一半。"""
    episode = item_title.split(" - ")[1].split(" ")[0]
    return f"[LoliHouse] Kimi ga Shinu made Koi wo Shitai - {episode} [1080p].mkv"


def finish_downloads(factory: FakeClientFactory, roots: dict[str, Path]) -> None:
    """qBittorrent 替身把收下的每一包「下載完」：檔案真的寫到 save path，並報成 100%。"""
    client = factory.qbittorrent_
    save_path = str(roots["complete"] / "anime")
    by_content = {f"torrent:{item.info_hash}".encode(): item for item in ITEMS}
    statuses: list[TorrentStatus] = []
    for request in client.added:
        item = by_content[request.content]
        name = release_file(item.title)
        (Path(save_path) / name).parent.mkdir(parents=True, exist_ok=True)
        (Path(save_path) / name).write_bytes(item.info_hash.encode())
        stamp = int(NOW.timestamp())
        statuses.append(
            TorrentStatus(
                hash=item.info_hash,
                name=name,
                state="stalledUP",
                category=request.category,
                tags=("berth",),
                progress=1.0,
                completion_on=stamp,
                last_activity=stamp,
                added_on=stamp,
                save_path=save_path,
                content_path=str(PurePosixPath(save_path) / name),
                total_size=1_400_000_000,
            )
        )
        client.files_by_hash[item.info_hash] = (
            TorrentFile(index=0, name=name, size=1_400_000_000, priority=1, progress=1.0),
        )
    client.torrents = tuple(statuses)


async def run_pipeline(
    session: AsyncSession, factory: FakeClientFactory, roots: dict[str, Path]
) -> None:
    """下載完 → poller → 規劃 → 入庫，各走一輪。"""
    finish_downloads(factory, roots)
    hub = EventHub()
    await poll_downloads(session, factory.qbittorrent_, hub, JobHints(), now=NOW)
    await sweep_plans(session, factory, hub, now=NOW)
    await sweep_imports(session, factory, hub, now=NOW)


class TestTheTracer:
    async def test_a_mikan_feed_reaches_the_ledger(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """加 feed → 輪詢一輪 → 長出待綁定的 RSS Series → 綁定 → 送單 → 下載完 → 規劃 → 入庫。"""
        media, route, factory = await harbour(session, roots)

        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        polled = await poll_feed(session, factory, feed.id, now=NOW)

        assert polled.items == 12
        pending = [row for row in await list_series(session) if row.media_id is None]
        assert KIMI_KEY in {row.key for row in pending}

        kimi_series = await series_by_key(session, KIMI_KEY)
        bound = await bind_series(
            session, factory, kimi_series.id, media_id=media.id, route_id=route.id, user_id=1
        )
        assert bound.media_id == KIMI_ID
        assert bound.submitted == 2

        await run_pipeline(session, factory, roots)

        jobs = list(await session.scalars(select(Job)))
        assert {job.hash for job in jobs} == {item.info_hash for item in KIMI}
        assert {(job.state, job.error) for job in jobs} == {(JobState.IMPORTED, "")}
        assert {(job.trigger, job.trigger_ref) for job in jobs} == {
            (JobTrigger.RSS, str(kimi_series.id))
        }
        ledger = list(await session.scalars(select(LedgerEntry)))
        assert sorted((row.season, row.episode_start) for row in ledger) == [(1, 11), (1, 12)]
        assert all(Path(row.target_path).exists() for row in ledger)

    async def test_the_job_says_which_series_sent_it(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """時間線的 actor 是 `rss:<series>`（plan §2.3）：沒有人按，是那個 RSS Series 送的。"""
        media, route, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)

        await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )

        created = await session.scalars(select(Event).where(Event.type == EventType.CREATED))
        assert {row.actor for row in created} == {f"rss:{series.id}"}


class TestGuidDedup:
    async def test_polling_the_same_feed_twice_adds_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)
        await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )
        items, jobs, added = (
            await count(session, RssItem),
            await count(session, Job),
            len(factory.qbittorrent_.added),
        )

        again = await poll_feed(session, factory, feed.id, now=NOW + timedelta(minutes=15))

        assert again.items == 0
        assert await count(session, RssItem) == items == 12
        assert await count(session, Job) == jobs == 2
        assert len(factory.qbittorrent_.added) == added

    async def test_the_second_round_does_not_fetch_episode_pages_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """單集頁一筆只抓一次（plan §8.5）：聚合 feed 每 15 分鐘一輪，抓 12 頁是 12 個請求。"""
        _, _, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        fetcher = factory.rss_
        fetcher.requested.clear()

        await poll_feed(session, factory, feed.id, now=NOW + timedelta(minutes=15))

        assert fetcher.requested == [FEED_URL]

    async def test_an_item_whose_episode_page_fails_is_tried_again_next_round(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """認不出是哪個 RSS Series 的那一筆不存：存了就再也不會去抓它的單集頁。"""
        _, _, factory = await harbour(session, roots)
        missing = KIMI[0].link
        page = factory.rss_.pages.pop(missing)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        first = await poll_feed(session, factory, feed.id, now=NOW)
        factory.rss_.pages[missing] = page
        second = await poll_feed(session, factory, feed.id, now=NOW + timedelta(minutes=15))

        assert (first.items, second.items) == (11, 1)
        row = await session.get(RssFeed, feed.id)
        assert row is not None
        assert row.last_error == ""


class TestBinding:
    async def test_new_series_wait_unbound_and_nothing_is_sent(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        await poll_feed(session, factory, feed.id, now=NOW)

        assert all(row.media_id is None for row in await list_series(session))
        assert {row.status for row in await list_items(session)} == {FeedItemStatus.UNBOUND}
        assert await count(session, Job) == 0
        assert factory.qbittorrent_.added == []
        assert factory.torrent_.requested == []

    async def test_binding_freezes_the_folder_name(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """第一次通向磁碟的那一刻（plan §2.2）。凍下去的是綁定當下的那一串，之後改標題不動它。"""
        media, route, factory = await harbour(session, roots)
        before = media.folder_name
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)
        frozen_before = media.folder_frozen

        await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )

        await session.refresh(media)
        assert (frozen_before, media.folder_frozen) == (False, True)
        assert media.folder_name == before
        assert media.default_route_id == route.id

    async def test_items_of_other_series_stay_unbound(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)

        await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )

        statuses = [(row.series_id == series.id, row.status) for row in await list_items(session)]
        assert statuses.count((True, FeedItemStatus.DOWNLOADED)) == 2
        assert statuses.count((False, FeedItemStatus.UNBOUND)) == 10

    async def test_a_refused_submission_keeps_the_binding_and_retries_next_round(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """綁定本身成立；送單被拒的那幾筆留在 `matched` 帶著原文，下一輪再送（shape §3）。"""
        media, route, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)
        factory.torrent_.error = ServiceUnavailableError("GET mikanani.me: connection refused")

        bound = await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )

        assert bound.media_id == KIMI_ID
        assert bound.submitted == 0
        held = [row for row in await list_items(session) if row.series_id == series.id]
        assert {row.status for row in held} == {FeedItemStatus.MATCHED}
        assert all("source_unavailable" in row.error for row in held)

        factory.torrent_.error = None
        await poll_feed(session, factory, feed.id, now=NOW + timedelta(minutes=15))

        sent = [row for row in await list_items(session) if row.series_id == series.id]
        assert {row.status for row in sent} == {FeedItemStatus.DOWNLOADED}
        assert {row.error for row in sent} == {""}
        assert await count(session, Job) == 2

    @pytest.mark.parametrize(
        ("change", "reason"),
        [
            ({"enabled": False}, RssRefusal.ROUTE_DISABLED),
            ({"collection_type": CollectionType.MOVIES}, RssRefusal.ROUTE_KIND_MISMATCH),
        ],
    )
    async def test_a_route_that_cannot_hold_it_is_refused_before_anything_changes(
        self,
        session: AsyncSession,
        roots: dict[str, Path],
        change: dict[str, object],
        reason: RssRefusal,
    ) -> None:
        media, route, factory = await harbour(session, roots)
        for name, value in change.items():
            setattr(route, name, value)
        await session.commit()
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)

        with pytest.raises(RssRejectedError) as refused:
            await bind_series(
                session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
            )

        assert refused.value.reason is reason
        await session.refresh(series)
        await session.refresh(media)
        assert series.media_id is None
        assert media.folder_frozen is False

    async def test_a_media_nobody_opened_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, route, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)

        with pytest.raises(RssRejectedError) as refused:
            await bind_series(
                session, factory, series.id, media_id="tv:1", route_id=route.id, user_id=1
            )

        assert refused.value.reason is RssRefusal.MEDIA_MISSING

    async def test_a_bound_series_is_not_bound_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)
        await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )

        with pytest.raises(RssRejectedError) as refused:
            await bind_series(
                session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
            )

        assert refused.value.reason is RssRefusal.SERIES_BOUND

    async def test_unbinding_puts_what_was_not_sent_back_to_waiting(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)
        factory.torrent_.error = ServiceUnavailableError("down")
        await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )

        view = await unbind_series(session, series.id)

        assert view.media_id is None
        held = [row for row in await list_items(session) if row.series_id == series.id]
        assert {(row.status, row.error) for row in held} == {(FeedItemStatus.UNBOUND, "")}


class TestFeeds:
    async def test_a_url_from_elsewhere_is_refused(self, session: AsyncSession) -> None:
        with pytest.raises(RssRejectedError) as refused:
            await add_feed(session, url="https://example.com/rss.xml", name="")

        assert refused.value.reason is RssRefusal.FEED_UNSUPPORTED

    async def test_the_same_url_twice_is_refused(self, session: AsyncSession) -> None:
        await add_feed(session, url=FEED_URL, name="Mikan")

        with pytest.raises(RssRejectedError) as refused:
            await add_feed(session, url=FEED_URL, name="again")

        assert refused.value.reason is RssRefusal.FEED_DUPLICATE

    async def test_deleting_a_feed_takes_its_items_and_leaves_the_series(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Series 是「作品 × 字幕組」，不屬於某個 Feed（shape §4）。"""
        _, _, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await count(session, RssSeries)

        deleted = await delete_feed(session, feed.id)

        assert deleted == 12
        assert await count(session, RssItem) == 0
        assert await count(session, RssSeries) == series == 11

    async def test_re_adding_a_deleted_feed_does_not_send_twice(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`delete_feed` 標 reversible 的根據：加回來之後以 info hash 認回同一筆 Job。"""
        media, route, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)
        await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )
        await delete_feed(session, feed.id)

        again = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, again.id, now=NOW + timedelta(hours=1))

        assert await count(session, Job) == 2
        assert len(factory.qbittorrent_.added) == 2
        kimi_items = [row for row in await list_items(session) if row.series_id == series.id]
        assert {row.status for row in kimi_items} == {FeedItemStatus.DOWNLOADED}

    async def test_a_feed_that_cannot_be_fetched_says_why_on_its_own_row(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await harbour(session, roots)
        factory.rss_.error = ServiceUnavailableError(f"GET {FEED_URL}: connection refused")
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        polled = await poll_feed(session, factory, feed.id, now=NOW)

        assert polled.items == 0
        row = await session.get(RssFeed, feed.id)
        assert row is not None
        assert "connection refused" in row.last_error
        assert row.last_polled_at == NOW


class TestSchedule:
    async def test_only_feeds_whose_interval_is_up_are_polled(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await harbour(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        assert await poll_due(session, factory, now=NOW) == 1
        assert await poll_due(session, factory, now=NOW + timedelta(minutes=14)) == 0
        assert await poll_due(session, factory, now=NOW + timedelta(minutes=15)) == 1
        row = await session.get(RssFeed, feed.id)
        assert row is not None
        assert row.last_polled_at == NOW + timedelta(minutes=15)

    async def test_nothing_is_polled_before_the_wizard_is_done(
        self, engine: AsyncEngine, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """`arrange` 停在精靈的第 5 步：那時候連 Route 都還沒定，送出去的東西沒有地方去。"""
        _, _, factory = await harbour(session, roots)
        await add_feed(session, url=FEED_URL, name="Mikan")
        poller = RssPoller(create_session_factory(engine), factory, now=lambda: NOW)

        assert await poller.poll_once() == 0
        await ready(session)
        assert await poller.poll_once() == 1


class TestSeasonAndOffset:
    """RSS Series 帶季號與 offset 時，規劃讀的是它（brief §15、plan §4.3；改正與重算在票 13）。"""

    async def _planned(
        self,
        session: AsyncSession,
        roots: dict[str, Path],
        *,
        season: int | None,
        offset: int | None,
    ) -> list[tuple[int | None, int | None]]:
        two_seasons = kimi_snapshot().model_copy(
            update={
                "seasons": (
                    *kimi_snapshot().seasons,
                    kimi_snapshot()
                    .seasons[0]
                    .model_copy(
                        update={"season_number": 2, "name": "Season 2", "names": ("Season 2",)}
                    ),
                )
            }
        )
        await arrange(session, roots)
        media = await kimi(session, snapshot=two_seasons)
        route = await anime_route(session, roots)
        factory = factory_for(roots)
        factory.rss_ = FakeFeedFetcher({FEED_URL: FEED, **episode_pages()})
        factory.torrent_ = torrents()
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)
        series.season = season
        series.episode_offset = offset
        await session.commit()
        await bind_series(
            session, factory, series.id, media_id=media.id, route_id=route.id, user_id=1
        )

        finish_downloads(factory, roots)
        hub = EventHub()
        await poll_downloads(session, factory.qbittorrent_, hub, JobHints(), now=NOW)
        await sweep_plans(session, factory, hub, now=NOW)
        rows = await session.scalars(select(PlanItem).where(PlanItem.episode_start.is_not(None)))
        return sorted((row.season, row.episode_start) for row in rows)

    async def test_the_series_season_and_offset_are_used(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        planned = await self._planned(session, roots, season=2, offset=-10)

        assert planned == [(2, 1), (2, 2)]

    async def test_without_them_the_parser_decides_on_its_own(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """同一包、同一部兩季的作品，Series 上沒有值：檔名的 11、12 照字面，落在第一季。"""
        planned = await self._planned(session, roots, season=None, offset=None)

        assert planned == [(1, 11), (1, 12)]
