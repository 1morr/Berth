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

import hashlib
from pathlib import Path
from typing import Any

import anyio
import pytest
from guessit import guessit
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.adapters.rss import acgrip, mikan
from berth.adapters.rss.fake import FakeFeedFetcher
from berth.adapters.torrent import TorrentSource
from berth.db.engine import create_session_factory
from berth.domain import (
    CollectionType,
    FeedItemStatus,
    FeedKind,
    MediaKind,
    PrimeMode,
    Role,
    RssRefusal,
    SkipCode,
    label_of,
)
from berth.models import Media, Route, RssFeed, RssSeries, User
from berth.parser import release
from berth.services import rss as rss_service
from berth.services.rss import (
    ExcludedCount,
    FeedView,
    RssRejectedError,
    bind_series,
    list_feeds,
    list_series,
    list_subscriptions,
    poll_feed,
    preview_feed,
    search_subgroups,
    set_feed_routes,
    subscribe_mikan,
    subscribe_search,
    subscriptions_of_feed_url,
)
from tests.conftest import FIXTURES
from tests.integration.arrange import Meeting
from tests.integration.factories import FakeClientFactory
from tests.integration.test_rss import (
    KIMI_KEY,
    NOW,
    anime_route,
    count,
    harbour,
    routed_feed,
    series_by_key,
)
from tests.integration.test_rss_backfill import SEASON, rss_jobs, subscribed
from tests.integration.test_rss_screen import SINGLE_URL, serve, serve_single
from tests.integration.test_rss_screen import release as synthetic

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
            actor=label_of(1),
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
        assert done.excluded == ()
        # 鍵從網址就知道：一頁單集頁都不必抓。
        assert factory.rss_.requested == [SINGLE_URL]

    async def test_what_the_season_left_excluded_is_counted_by_reason(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """M4 票 112：字幕組只出了合集，全域預設擋下它。回報說得出幾筆、哪一種理由。"""
        media, route, factory = await harbour(session, roots)
        group = "喵萌奶茶屋&LoliHouse"
        serve(factory, SINGLE_URL, [synthetic(370, group, "[01-12 合集]")])

        done = await subscribe_mikan(
            session,
            factory,
            bangumi_id=4009,
            subgroup_id=370,
            media_id=media.id,
            route_id=route.id,
            user_id=1,
            actor=label_of(1),
            now=NOW,
        )

        assert done.series.submitted == 0
        assert done.excluded == (ExcludedCount(code=SkipCode.NOT_SINGLE, count=1),)

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
            actor=label_of(1),
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
            actor=label_of(1),
            subgroup_name="LoliHouse",
            now=NOW,
        )

        assert [feed.id for feed in await feeds(session)] == [feed_id]
        assert (done.feed.id, done.series.id) == (feed_id, series_id)
        assert (done.series.mikan_bangumi_name, done.series.mikan_subgroup_name) == (
            "与你相恋到生命尽头",
            "LoliHouse",
        )
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
                actor=label_of(1),
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
                actor=label_of(1),
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
                actor=label_of(1),
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


class MeetingFetcher(FakeFeedFetcher):
    """兩條 Feed 都抓到了才各自往下讀（`Meeting`）：真的抓要幾百毫秒，兩輪會疊在一起。"""

    def __init__(self, pages: dict[str, bytes]) -> None:
        super().__init__(pages)
        self.meeting = Meeting()

    async def fetch(self, url: str) -> bytes:
        page = await super().fetch(url)
        await self.meeting.arrive()
        return page


class TestSearchFeed:
    async def test_its_preview_reads_each_release_name_at_most_once(
        self, session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """M4 票 13b：預覽是綁好的 Item（票 26 起只有黒ネズミたち那 5 筆），每一筆說集號、當場看去重
        （`library_copy` 以規劃的算法猜季集、再讀一次字幕組）。同一個發佈名每一步各解析一次的話，
        一次預覽呼叫 guessit 約 120 次、閒著也要 2 秒以上，而且是握著事件迴圈的 CPU：背景同時在
        規劃時，前端 e2e 5 秒內等不到它。發佈名解析是純函式，一個名字只該解析一次。

        建 feed 那一輪已經讀過這些名字，所以預覽之前先清掉記住的結果：要看的是預覽**自己**冷著讀
        的時候也不重讀，不是快取剛好熱著。"""
        media, route, factory = await harbour(session, roots)
        user_id = await skipper(session)
        factory.rss_.pages[acgrip.search_url(TERM)] = ACGRIP_FEED
        feed = await subscribe_search(
            session,
            factory,
            kind=FeedKind.ACGRIP,
            term=TERM,
            subgroup=MOUSE,
            media_id=media.id,
            route_id=route.id,
            user_id=user_id,
            now=NOW,
        )
        calls: list[str] = []

        def counting(name: str, options: dict[str, object]) -> object:
            calls.append(name)
            return guessit(name, options)

        monkeypatch.setattr(release, "guessit", counting)
        release._parse_release.cache_clear()
        preview = await preview_feed(session, feed.id)
        again = await preview_feed(session, feed.id)

        assert len(preview) == len(again) == 5
        assert calls, "the preview read no release name at all"
        # guessit 收的是正規化過的字串，兩個發佈名可以正規化成同一串：比的是讀了幾個名字——每一筆的
        # 標題，加上 `library_copy` 配的中性檔名。
        names = {row.title for row in preview} | {"episode.mkv"}
        assert len(calls) <= len(names), f"{len(calls)} calls for {len(names)} names"

    async def test_series_already_waiting_from_another_feed_are_bound_too(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """另一條搜尋 feed 先長出同一個鍵（標題骨幹 + 字幕組）、還在待綁定：這一條帶到它時也綁。"""
        media, route, factory = await harbour(session, roots)
        user_id = await skipper(session)
        other = "https://acg.rip/.xml?term=Kimi+ga+Shinu"
        factory.rss_.pages[other] = ACGRIP_FEED
        factory.rss_.pages[acgrip.search_url(TERM)] = ACGRIP_FEED
        earlier = await routed_feed(session, url=other)
        await poll_feed(session, factory, earlier.id, now=NOW)
        assert {row.media_id for row in await session.scalars(select(RssSeries))} == {None}

        await subscribe_search(
            session,
            factory,
            kind=FeedKind.ACGRIP,
            term=TERM,
            subgroup=MOUSE,
            media_id=media.id,
            route_id=route.id,
            user_id=user_id,
            now=NOW,
        )

        rows = list(await session.scalars(select(RssSeries)))
        # 只有選的那一組綁上，別組還在待綁定（票 26）。
        assert {
            (row.key.rsplit(":", 1)[1], row.media_id, row.bound_by) for row in rows if row.media_id
        } == {(MOUSE, media.id, str(user_id))}
        assert len(rows) > 1

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
                subgroup=MOUSE,
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
            "subgroup": MOUSE,
            "media_id": media.id,
            "route_id": route.id,
            "user_id": user_id,
        }
        await subscribe_search(session, factory, **arguments)  # type: ignore[arg-type]  # 同一組參數送兩次

        with pytest.raises(RssRejectedError) as refused:
            await subscribe_search(session, factory, **arguments)  # type: ignore[arg-type]  # 同上

        assert refused.value.reason is RssRefusal.FEED_DUPLICATE

    async def test_the_same_search_twice_at_once_is_one_feed_and_a_duplicate(
        self,
        engine: AsyncEngine,
        session: AsyncSession,
        roots: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """同一步並行的兩個工具呼叫（M5 票 24）：兩支都過了「已經有這條 Feed 嗎」才建。

        檢查與寫入之間沒有網路，替身插不進去，所以在中間那一步（算 Feed 的兩格 Route）碰面。
        """
        meeting = Meeting()
        routes_of = rss_service._subscribed_routes

        async def met(*args: Any, **kwargs: Any) -> Any:  # `Any`：原樣轉給被包住的那一支
            await meeting.arrive()
            return await routes_of(*args, **kwargs)

        monkeypatch.setattr(rss_service, "_subscribed_routes", met)
        media, route, factory = await harbour(session, roots)
        user_id = await skipper(session)
        factory.rss_.pages[acgrip.search_url(TERM)] = ACGRIP_FEED
        sessions = create_session_factory(engine)
        outcomes: list[object] = []

        async def subscribe() -> None:
            async with sessions() as own:
                try:
                    outcomes.append(
                        await subscribe_search(
                            own,
                            factory,
                            kind=FeedKind.ACGRIP,
                            term=TERM,
                            subgroup=MOUSE,
                            media_id=media.id,
                            route_id=route.id,
                            user_id=user_id,
                        )
                    )
                except RssRejectedError as exc:
                    outcomes.append(exc.reason)

        async with anyio.create_task_group() as both:
            both.start_soon(subscribe)
            both.start_soon(subscribe)

        assert RssRefusal.FEED_DUPLICATE in outcomes
        assert len(await feeds(session)) == 1

    async def test_two_searches_growing_the_same_series_at_once_both_succeed(
        self, engine: AsyncEngine, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """兩條不同的搜尋 feed 搜到同一批發佈（M5 票 24）：Series 的鍵是標題骨幹，跨 Feed 共用。"""
        media, route, factory = await harbour(session, roots)
        user_id = await skipper(session)
        terms = (TERM, "Kimi ga Shinu made")
        factory.rss_ = MeetingFetcher({acgrip.search_url(term): ACGRIP_FEED for term in terms})
        sessions = create_session_factory(engine)

        async def subscribe(term: str) -> None:
            async with sessions() as own:
                await subscribe_search(
                    own,
                    factory,
                    kind=FeedKind.ACGRIP,
                    term=term,
                    subgroup=MOUSE,
                    media_id=media.id,
                    route_id=route.id,
                    user_id=user_id,
                )

        async with anyio.create_task_group() as both:
            for term in terms:
                both.start_soon(subscribe, term)

        assert [feed.poll_error for feed in await feeds(session)] == ["", ""]
        grown = list(await session.scalars(select(RssSeries)))
        assert grown
        assert {series.media_id for series in grown} == {media.id}

    async def test_when_the_route_went_away_what_grows_waits_for_a_person(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """訂閱之後 Route 停用了，才長出來的 Series 照一般的路去認作品、留在待綁定（Feed 直接寫：
        票 26 起訂閱那一刻讀不到就不建）。"""
        media, route, factory = await harbour(session, roots)
        user_id = await skipper(session)
        feed = RssFeed(
            name="acg.rip · Kimi",
            url=acgrip.search_url(TERM),
            kind=FeedKind.ACGRIP,
            media_id=media.id,
            user_id=user_id,
            subgroup=MOUSE,
            tv_route_id=route.id,
            primed_at=NOW,
        )
        session.add(feed)
        await session.commit()
        row = await session.get(Route, route.id)
        assert row is not None
        row.enabled = False
        await session.commit()
        factory.rss_.pages[acgrip.search_url(TERM)] = ACGRIP_FEED

        await poll_feed(session, factory, feed.id, now=NOW)

        grown = list(await session.scalars(select(RssSeries)))
        assert grown and {row.media_id for row in grown} == {None}

    async def test_only_the_works_kind_needs_a_route(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """M4 票 105：它長出的都綁到那一部劇集，電影那一格永遠用不到——兩條電影 Route 也不要它選：
        不算進要選的、不要求、存 `None`。"""
        media, route, factory = await harbour(session, roots)
        user_id = await skipper(session)
        factory.rss_.pages[acgrip.search_url(TERM)] = ACGRIP_FEED
        for slug in ("movies", "cinema"):
            await anime_route(
                session,
                roots,
                slug=slug,
                name=slug.title(),
                jellyfin_library_id=f"item-{slug}",
                collection_type=CollectionType.MOVIES,
                category=f"berth-{slug}",
            )

        feed = await subscribe_search(
            session,
            factory,
            kind=FeedKind.ACGRIP,
            term=TERM,
            subgroup=MOUSE,
            media_id=media.id,
            route_id=route.id,
            user_id=user_id,
            now=NOW,
        )
        chosen = await set_feed_routes(
            session, factory, feed.id, tv_route_id=route.id, movie_route_id=None, now=NOW
        )

        assert (feed.route_kinds, feed.tv_route_id, feed.movie_route_id) == (
            (MediaKind.TV,),
            route.id,
            None,
        )
        assert (chosen.feed.route_kinds, chosen.feed.movie_route_id) == ((MediaKind.TV,), None)
        (listed,) = await list_feeds(session)
        assert listed.route_kinds == (MediaKind.TV,)

    async def test_a_general_feed_uses_both_kinds(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, route, _ = await harbour(session, roots)

        feed = await routed_feed(session)

        assert (feed.route_kinds, feed.tv_route_id) == ((MediaKind.TV, MediaKind.MOVIE), route.id)


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


MOUSE = "黒ネズミたち"


def mouse_torrents(factory: FakeClientFactory) -> set[str]:
    """《与你相恋》acg.rip 搜尋裡黒ネズミたち那 5 筆的 `.torrent`，各一個 hash。"""
    items = [item for item in acgrip.parse_feed(ACGRIP_FEED) if item.title.startswith(f"[{MOUSE}]")]
    hashes: set[str] = set()
    for item in items:
        assert item.torrent_url
        info_hash = hashlib.sha1(item.torrent_url.encode()).hexdigest()
        factory.torrent_.sources[item.torrent_url] = TorrentSource(
            info_hash=info_hash, content=f"torrent:{info_hash}".encode()
        )
        hashes.add(info_hash)
    return hashes


class TestOneSubgroup:
    """關鍵字訂閱只綁一個字幕組（M5 票 26）：試用機上助理把搜到的每個字幕組都綁上作品，使用者
    沒選過。指定了字幕組的那一條只收那一組的發佈；第一批由人在作品頁或確認卡上看過才建，第一輪
    也在那裡選：「下載這些並追之後的」建好就送、那個 Series 記成第一批已確認；「只追之後的」現有的
    一筆都不送。"""

    async def subscribe(
        self,
        session: AsyncSession,
        roots: dict[str, Path],
        first_batch: PrimeMode = PrimeMode.ALL,
    ) -> tuple[Media, Route, FakeClientFactory, FeedView, set[str]]:
        media, route, factory = await harbour(session, roots)
        user_id = await skipper(session)
        factory.rss_.pages[acgrip.search_url(TERM)] = ACGRIP_FEED
        hashes = mouse_torrents(factory)
        feed = await subscribe_search(
            session,
            factory,
            kind=FeedKind.ACGRIP,
            term=TERM,
            subgroup=MOUSE,
            media_id=media.id,
            route_id=route.id,
            user_id=user_id,
            first_batch=first_batch,
            now=NOW,
        )
        return media, route, factory, feed, hashes

    async def test_only_the_chosen_subgroup_is_written_and_bound(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, _, feed, _ = await self.subscribe(session, roots)

        grown = list(await session.scalars(select(RssSeries)))
        assert [row.key for row in grown] == ["title:kimigashinumadekoiwoshitai:黒ネズミたち"]
        assert {(row.media_id, row.route_id) for row in grown} == {(media.id, route.id)}
        items = await preview_feed(session, feed.id)
        assert len(items) == 5
        assert {row.title.split("]")[0] for row in items} == {f"[{MOUSE}"}

    async def test_the_first_batch_was_confirmed_on_the_card_so_it_is_sent(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, _, feed, hashes = await self.subscribe(session, roots)

        assert feed.primed_at == NOW
        assert await rss_jobs(session) == hashes
        [series] = await session.scalars(select(RssSeries))
        assert series.confirmed

    async def test_only_what_comes_next_sends_nothing_now(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """「只追之後的」（同 RSS 頁第一輪那一顆）：現有的五筆記成略過、一個都不送，第一批還沒確認
        （入庫的會是之後的集數，人沒看過）。之後這一組的新發佈照送。"""
        _, _, factory, feed, _ = await self.subscribe(session, roots, PrimeMode.LATER)

        assert feed.primed_at == NOW
        assert await rss_jobs(session) == set()
        items = await preview_feed(session, feed.id)
        assert {row.status for row in items} == {FeedItemStatus.PASSED}
        [series] = await session.scalars(select(RssSeries))
        assert not series.confirmed

        twelve = f"[{MOUSE}] 與妳相戀到生命盡頭 / Kimi ga Shinu made Koi wo Shitai - 12 (Baha"
        newer = ACGRIP_FEED.replace(
            twelve.encode(), twelve.replace(" - 12 ", " - 13 ").encode()
        ).replace(b"https://acg.rip/t/363904", b"https://acg.rip/t/999904")
        factory.rss_.pages[acgrip.search_url(TERM)] = newer
        await poll_feed(session, factory, feed.id, now=NOW)

        assert len(await rss_jobs(session)) == 1

    async def test_a_search_that_cannot_be_read_makes_no_feed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """人在場（同 Mikan 的訂閱）：讀不到就第一輪也選不了，不留下沒讀過的 Feed。"""
        media, route, factory = await harbour(session, roots)
        user_id = await skipper(session)

        with pytest.raises(RssRejectedError) as refused:
            await subscribe_search(
                session,
                factory,
                kind=FeedKind.ACGRIP,
                term=TERM,
                subgroup=MOUSE,
                media_id=media.id,
                route_id=route.id,
                user_id=user_id,
                now=NOW,
            )

        assert refused.value.reason is RssRefusal.FEED_UNREACHABLE
        assert await feeds(session) == []

    async def test_later_rounds_keep_to_the_subgroup(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """之後的輪詢帶到別的字幕組的新發佈，也不寫、不長 Series、不綁。"""
        _, _, factory, feed, _ = await self.subscribe(session, roots)
        newer = ACGRIP_FEED.replace(b"- 12 [1080P]", b"- 13 [1080P]").replace(
            b"https://acg.rip/t/363905", b"https://acg.rip/t/999999"
        )
        factory.rss_.pages[acgrip.search_url(TERM)] = newer

        await poll_feed(session, factory, feed.id, now=NOW)

        assert await count(session, RssSeries) == 1
        assert len(await preview_feed(session, feed.id)) == 5


class TestTheSubgroupsASearchFinds:
    """確認卡的選項（票 26）：這一次搜到的字幕組，各有幾筆、最近一筆、第一批會下載的發佈名。
    只讀。"""

    async def test_each_subgroup_with_its_releases_newest_first(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await harbour(session, roots)
        factory.rss_.pages[acgrip.search_url(TERM)] = ACGRIP_FEED

        found = await search_subgroups(factory, kind=FeedKind.ACGRIP, term=TERM)

        by_name = {group.name: group for group in found}
        mouse = by_name[MOUSE]
        assert mouse.releases == len(mouse.titles) == 5
        assert mouse.latest == mouse.titles[0]
        assert mouse.latest.startswith(f"[{MOUSE}]") and " - 12 " in mouse.latest
        assert mouse.updated is not None
        # 最多的在前，同數照最近更新。
        assert [group.releases for group in found] == sorted(
            (group.releases for group in found), reverse=True
        )
        assert "ANi" in by_name
        assert await count(session, RssFeed) == 0

    async def test_a_search_that_cannot_be_read_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, _, factory = await harbour(session, roots)

        with pytest.raises(RssRejectedError) as refused:
            await search_subgroups(factory, kind=FeedKind.ACGRIP, term=TERM)

        assert refused.value.reason is RssRefusal.FEED_UNREACHABLE


class TestWhatAWorkIsSubscribedTo:
    """重複訂閱（票 26）：訂閱之前說出這部作品已經有的訂閱——哪一條 Feed、哪個來源、哪個字幕組。"""

    async def test_a_keyword_feed_and_a_mikan_subscription_are_both_listed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, route, factory = await harbour(session, roots)
        user_id = await skipper(session)
        factory.rss_.pages[acgrip.search_url(TERM)] = ACGRIP_FEED
        mouse_torrents(factory)
        keyword = await subscribe_search(
            session,
            factory,
            kind=FeedKind.ACGRIP,
            term=TERM,
            subgroup=MOUSE,
            media_id=media.id,
            route_id=route.id,
            user_id=user_id,
            now=NOW,
        )
        # 票 26 之前建的關鍵字 Feed：每一個字幕組都收（`subgroup` 空的）。
        everything = RssFeed(
            name="nyaa.si · Kimi",
            url="https://nyaa.si/?page=rss&q=Kimi",
            kind=FeedKind.NYAA,
            media_id=media.id,
            user_id=user_id,
        )
        session.add(everything)
        await session.commit()
        serve_single(factory)
        mikan = await subscribe_mikan(
            session,
            factory,
            bangumi_id=4009,
            subgroup_id=370,
            media_id=media.id,
            route_id=route.id,
            user_id=user_id,
            actor=label_of(user_id),
            subgroup_name="LoliHouse",
            now=NOW,
        )

        found = await list_subscriptions(session, media.id)

        assert [(row.feed_id, row.kind, row.subgroup) for row in found] == [
            (keyword.id, FeedKind.ACGRIP, MOUSE),
            (everything.id, FeedKind.NYAA, ""),
            (mikan.feed.id, FeedKind.MIKAN, "LoliHouse"),
        ]
        assert found[0].name == keyword.name

    async def test_an_aggregate_feed_carrying_a_bound_series_is_listed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """聚合 feed 上綁到這部作品的 RSS Series 也算：刪那條 Feed 會連同別部作品一起停。"""
        media, route, factory, feed_id, series_id = await subscribed(session, roots)
        await bind_series(
            session, factory, series_id, media_id=media.id, route_id=route.id, user_id=None, now=NOW
        )

        [row] = await list_subscriptions(session, media.id)

        assert (row.feed_id, row.kind) == (feed_id, FeedKind.MIKAN)

    async def test_a_mikan_feed_url_names_the_work_its_bangumi_is_bound_to(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """加 Feed 的卡（票 26）：要加的是某個番組的單一 feed、而那個番組（任一個字幕組）已經綁在
        作品上時，說出那部作品現有的訂閱。看不出是哪一部的網址什麼都不說。"""
        media, route, factory, feed_id, series_id = await subscribed(session, roots)
        await bind_series(
            session, factory, series_id, media_id=media.id, route_id=route.id, user_id=None, now=NOW
        )

        other_group = await subscriptions_of_feed_url(session, mikan.bangumi_feed_url(4009, 583))
        other_bangumi = await subscriptions_of_feed_url(session, mikan.bangumi_feed_url(5011, 1))

        assert [row.feed_id for row in other_group] == [feed_id]
        assert other_bangumi == ()
        assert await subscriptions_of_feed_url(session, acgrip.search_url(TERM)) == ()

    async def test_nothing_for_a_work_with_no_subscription(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        media, _, _ = await harbour(session, roots)

        assert await list_subscriptions(session, media.id) == ()

    async def test_without_a_work_every_subscription_says_which_work_it_is_for(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """新番推薦一次標出已經訂閱的（票 28）：不帶 `media_id` 列每一條，各自說綁的是哪一部。
        聚合 feed 上綁到作品的 RSS Series 照作品列；什麼都還沒綁的 Feed 也列，作品是空的。"""
        media, route, factory, feed_id, series_id = await subscribed(session, roots)
        await bind_series(
            session, factory, series_id, media_id=media.id, route_id=route.id, user_id=None, now=NOW
        )
        loose = RssFeed(
            name="nyaa.si · Frieren", url="https://nyaa.si/?page=rss&q=Frieren", kind=FeedKind.NYAA
        )
        session.add(loose)
        await session.commit()

        found = await list_subscriptions(session)

        assert [(row.feed_id, row.media_id, row.title) for row in found] == [
            (feed_id, media.id, media.snapshot().title),
            (loose.id, "", ""),
        ]
        # 帶 `media_id` 的那一種照舊，一樣說得出是哪一部。
        [mine] = await list_subscriptions(session, media.id)
        assert (mine.feed_id, mine.media_id) == (feed_id, media.id)
