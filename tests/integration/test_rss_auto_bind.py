"""RSS Series 自動綁定（M3 票 09、brief §15「綁定」）：第一次見到的 Series 去 TMDB 認作品。

替身：票 07 錄下來的 Mikan 聚合 feed、《与你相恋到生命尽头》的單集頁與番組頁（4009，
`放送开始：7/7/2026`）；TMDB 是替身，搜番組名或羅馬字名都回那一部。其餘十個 Series 的番組頁
不在替身裡——Mikan 連不上的樣子。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.rss.fake import FakeFeedFetcher
from berth.adapters.rss.mikan import bangumi_url
from berth.adapters.tmdb import TmdbDetail, TmdbEntry, TmdbEpisode, TmdbSeason, TmdbSeasonEntry
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.domain import (
    BindReason,
    BindReasonCode,
    CollectionType,
    EventType,
    JobTrigger,
    MediaKind,
    RssRefusal,
)
from berth.models import Event, Job, LedgerEntry, Route, RssFeed, TmdbSettings
from berth.services.rss import (
    RssRejectedError,
    add_feed,
    bind_series,
    list_series,
    poll_feed,
    unbind_series,
)
from berth.services.settings import write_settings
from tests.conftest import TMDB_API_KEY
from tests.integration.arrange import arrange, factory_for
from tests.integration.factories import FakeClientFactory
from tests.integration.test_rss import (
    FEED,
    FEED_URL,
    KIMI,
    KIMI_ID,
    KIMI_KEY,
    MIKAN,
    NOW,
    anime_route,
    count,
    episode_pages,
    run_pipeline,
    series_by_key,
    torrents,
)
from tests.integration.test_rss_preview import ACGRIP, ACGRIP_URL, LOLIHOUSE_KEY
from tests.integration.test_rss_screen import serve_single

pytestmark = pytest.mark.asyncio

KIMI_TMDB = 262000
#: TMDB 的第一季首播。Mikan 寫 7/7，TMDB 這裡 7/8：時區與先行上映差個一兩天是常態。
AIRED = date(2026, 7, 8)


def kimi_tmdb() -> FakeTmdbClient:
    entry = TmdbEntry(
        tmdb_id=KIMI_TMDB,
        kind=MediaKind.TV,
        title="Kimishinu",
        original_title="君が死ぬまで恋をしたい",
        year=2026,
        poster_path="",
    )
    return FakeTmdbClient(
        # `search_media` 先正規化（小寫、收空白）再問。
        search={"与你相恋到生命尽头": [entry], "kimi ga shinu made koi wo shitai": [entry]},
        translations={KIMI_TMDB: "與妳相戀到生命盡頭"},
        details=[
            TmdbDetail(
                tmdb_id=KIMI_TMDB,
                kind=MediaKind.TV,
                title="Kimishinu",
                original_title="君が死ぬまで恋をしたい",
                year=2026,
                first_air_date=AIRED,
                overview="",
                poster_path="",
                titles=(
                    "Kimishinu",
                    "君が死ぬまで恋をしたい",
                    "Kimi ga Shinu made Koi wo Shitai",
                    "与你相恋到生命尽头",
                ),
                seasons=(TmdbSeasonEntry(1, "Season 1", 12, AIRED),),
            )
        ],
        seasons={
            KIMI_TMDB: [
                TmdbSeason(
                    season_number=1,
                    name="Season 1",
                    air_date=AIRED,
                    episodes=tuple(
                        TmdbEpisode(1, n, f"Episode {n}", AIRED + timedelta(weeks=n - 1), 24)
                        for n in range(1, 13)
                    ),
                )
            ]
        },
    )


async def moored(
    session: AsyncSession, roots: dict[str, Path], *, tmdb: FakeTmdbClient | None = None
) -> tuple[Route, FakeClientFactory]:
    """精靈跑完（含 TMDB key）、一條 anime Route。

    **沒有**先打開過任何作品的詳情頁：自動綁定自己去讀。
    """
    await arrange(session, roots)
    await write_settings(session, TmdbSettings(api_key=TMDB_API_KEY))
    route = await anime_route(session, roots)
    factory = factory_for(roots, tmdb=tmdb or kimi_tmdb())
    factory.rss_ = FakeFeedFetcher(
        {
            FEED_URL: FEED,
            **episode_pages(),
            bangumi_url(4009): (MIKAN / "home-bangumi.4009.html").read_bytes(),
        }
    )
    factory.torrent_ = torrents()
    return route, factory


def codes(reasons: Sequence[BindReason]) -> list[BindReasonCode]:
    return [reason.code for reason in reasons]


class TestConfident:
    async def test_a_sure_series_binds_itself_sends_and_reaches_the_ledger(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """驗收第 1 條：命中唯一候選 → 自動綁定並送單，`bound_by = system`，時間線說得出依據。"""
        route, factory = await moored(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        polled = await poll_feed(session, factory, feed.id, now=NOW)

        assert (polled.bound, polled.submitted) == (1, 2)
        series = await series_by_key(session, KIMI_KEY)
        assert (series.media_id, series.route_id, series.bound_by) == (KIMI_ID, route.id, "system")

        created = list(await session.scalars(select(Event).where(Event.type == EventType.CREATED)))
        assert {row.actor for row in created} == {f"rss:{series.id}"}
        for row in created:
            assert row.payload_json is not None
            grounds = row.payload_json["grounds"]
            assert [ground["code"] for ground in grounds] == [
                "title_equal",
                "premiere_near",
                "only_route",
            ]
            assert grounds[1]["params"] == {
                "premiere": "2026-07-07",
                "season": 1,
                "aired": "2026-07-08",
            }
            assert grounds[2]["params"] == {"route": "Anime"}

        await run_pipeline(session, factory, roots)
        jobs = list(await session.scalars(select(Job)))
        assert {(job.trigger, job.hash) for job in jobs} == {
            (JobTrigger.RSS, item.info_hash) for item in KIMI
        }
        ledger = list(await session.scalars(select(LedgerEntry)))
        assert sorted((row.season, row.episode_start) for row in ledger) == [(1, 11), (1, 12)]

    async def test_the_bound_series_shows_its_grounds(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, factory = await moored(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)

        view = next(row for row in await list_series(session) if row.key == KIMI_KEY)

        assert codes(view.reasons) == [
            BindReasonCode.TITLE_EQUAL,
            BindReasonCode.PREMIERE_NEAR,
            BindReasonCode.ONLY_ROUTE,
        ]
        assert [(one.id, one.title, one.year) for one in view.candidates] == [
            (KIMI_ID, "與妳相戀到生命盡頭", 2026)
        ]

    async def test_a_series_is_looked_up_once(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """認作品只在它長出來的那一輪做：之後每 15 分鐘一輪，不再抓番組頁、不再搜 TMDB。

        綁上的那一輪也讀了單一 feed 補舊集（票 12）；不滿一天不再讀。"""
        _, factory = await moored(session, roots)
        serve_single(factory)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        factory.rss_.requested.clear()
        asked = len(factory.tmdb_.requests)

        await poll_feed(session, factory, feed.id, now=NOW + timedelta(minutes=15))

        assert factory.rss_.requested == [FEED_URL]
        assert len(factory.tmdb_.requests) == asked


class TestPending:
    async def test_two_routes_of_that_kind_keep_it_pending_with_the_work_prefilled(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """驗收：同類型有兩條 Route 時不自動綁定；作品已經認出來，一鍵選定走同一支綁定命令。"""
        route, factory = await moored(session, roots)
        await anime_route(
            session, roots, slug="tv", name="TV", jellyfin_library_id="item-1", category="berth-tv"
        )
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        polled = await poll_feed(session, factory, feed.id, now=NOW)

        assert (polled.bound, polled.submitted) == (0, 0)
        assert await count(session, Job) == 0
        view = next(row for row in await list_series(session) if row.key == KIMI_KEY)
        assert view.media_id is None
        assert codes(view.reasons)[-1] is BindReasonCode.ROUTE_AMBIGUOUS
        assert view.reasons[-1].params == {"routes": "Anime, TV"}
        assert [one.id for one in view.candidates] == [KIMI_ID]

        bound = await bind_series(
            session, factory, view.id, media_id=view.candidates[0].id, route_id=route.id, user_id=1
        )

        assert (bound.bound_by, bound.submitted) == ("1", 2)

    async def test_a_disabled_route_does_not_count(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        route, factory = await moored(session, roots)
        route.enabled = False
        await session.commit()
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        await poll_feed(session, factory, feed.id, now=NOW)

        view = next(row for row in await list_series(session) if row.key == KIMI_KEY)
        assert view.media_id is None
        assert codes(view.reasons)[-1] is BindReasonCode.NO_ROUTE

    async def test_mikan_unreachable_leaves_the_others_pending_to_retry(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """連不上是暫時的：留在待綁定、晚點再認（M4 票 14 的 `test_rss_auto_bind_retry`）。"""
        _, factory = await moored(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        await poll_feed(session, factory, feed.id, now=NOW)

        others = [row for row in await list_series(session) if row.key != KIMI_KEY]
        assert len(others) == 10
        assert {tuple(codes(row.reasons)) for row in others} == {(BindReasonCode.LOOKUP_RETRY,)}
        assert all(row.media_id is None and row.candidates == () for row in others)

    async def test_tmdb_down_leaves_it_pending_to_retry(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        tmdb = kimi_tmdb()
        tmdb.error = ServiceUnavailableError("GET api.themoviedb.org: connection refused")
        _, factory = await moored(session, roots, tmdb=tmdb)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        polled = await poll_feed(session, factory, feed.id, now=NOW)

        assert polled.items == 12
        view = next(row for row in await list_series(session) if row.key == KIMI_KEY)
        assert view.media_id is None
        assert codes(view.reasons) == [BindReasonCode.LOOKUP_RETRY]
        assert "connection refused" in str(view.reasons[0].params["detail"])

    async def test_same_title_another_year_stays_pending_with_the_candidate(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        tmdb = kimi_tmdb()
        old = date(2006, 4, 1)
        tmdb.details[(MediaKind.TV, KIMI_TMDB)] = replace(
            tmdb.details[(MediaKind.TV, KIMI_TMDB)],
            year=2006,
            first_air_date=old,
            seasons=(TmdbSeasonEntry(1, "Season 1", 12, old),),
        )
        _, factory = await moored(session, roots, tmdb=tmdb)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        await poll_feed(session, factory, feed.id, now=NOW)

        view = next(row for row in await list_series(session) if row.key == KIMI_KEY)
        assert view.media_id is None
        assert codes(view.reasons) == [BindReasonCode.PREMIERE_FAR]
        assert [one.id for one in view.candidates] == [KIMI_ID]


class TestFeedRoute:
    """Feed 帶一條 Route（M3 票 21，使用者拍板，照 Sonarr Import List 的 Root Folder）：同類型的
    Route 不只一條時，自動綁定送進 Feed 說的那一條。預設安裝就是 TV 與 Anime 兩條。"""

    async def test_two_routes_of_that_kind_bind_to_the_feeds_route(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        route, factory = await moored(session, roots)
        await anime_route(
            session, roots, slug="tv", name="TV", jellyfin_library_id="item-1", category="berth-tv"
        )
        feed = await add_feed(session, url=FEED_URL, name="Mikan", route_id=route.id)

        polled = await poll_feed(session, factory, feed.id, now=NOW)

        assert (polled.bound, polled.submitted) == (1, 2)
        view = next(row for row in await list_series(session) if row.key == KIMI_KEY)
        assert (view.media_id, view.route_id, view.bound_by) == (KIMI_ID, route.id, "system")
        assert codes(view.reasons)[-1] is BindReasonCode.FEED_ROUTE
        assert view.reasons[-1].params == {"route": "Anime"}

    async def test_a_feed_route_of_another_kind_falls_back_to_the_routes_of_that_kind(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Feed 的 Route 收電影、認出來的是劇集：照原本的規則挑（這裡只有一條 anime Route）。"""
        route, factory = await moored(session, roots)
        movies = await anime_route(
            session,
            roots,
            slug="movies",
            name="Movies",
            jellyfin_library_id="item-3",
            collection_type=CollectionType.MOVIES,
            category="berth-movies",
        )
        feed = await add_feed(session, url=FEED_URL, name="Mikan", route_id=movies.id)

        await poll_feed(session, factory, feed.id, now=NOW)

        view = next(row for row in await list_series(session) if row.key == KIMI_KEY)
        assert view.route_id == route.id
        assert codes(view.reasons)[-1] is BindReasonCode.ONLY_ROUTE

    async def test_a_disabled_feed_route_does_not_count(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        route, factory = await moored(session, roots)
        await anime_route(
            session, roots, slug="tv", name="TV", jellyfin_library_id="item-1", category="berth-tv"
        )
        feed = await add_feed(session, url=FEED_URL, name="Mikan", route_id=route.id)
        route.enabled = False
        await session.commit()

        await poll_feed(session, factory, feed.id, now=NOW)

        view = next(row for row in await list_series(session) if row.key == KIMI_KEY)
        assert view.route_id != route.id
        assert codes(view.reasons)[-1] is BindReasonCode.ONLY_ROUTE

    async def test_a_missing_route_is_refused(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await moored(session, roots)

        with pytest.raises(RssRejectedError) as refused:
            await add_feed(session, url=FEED_URL, name="Mikan", route_id=999)

        assert refused.value.reason is RssRefusal.ROUTE_MISSING
        assert await count(session, RssFeed) == 0


class TestUnbinding:
    async def test_unbinding_an_automatic_binding_does_not_rebind_it_next_round(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """人拆掉的自動綁定不會在下一輪又被綁回去：自動綁定只在 Series 長出來的那一輪做。"""
        _, factory = await moored(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        series = await series_by_key(session, KIMI_KEY)

        undone = await unbind_series(session, series.id)
        await poll_feed(session, factory, feed.id, now=NOW + timedelta(minutes=15))

        assert undone.bound_by == ""
        assert undone.reasons == ()
        assert [one.id for one in undone.candidates] == [KIMI_ID]
        await session.refresh(series)
        assert series.media_id is None


class TestWithoutAShowPage:
    """Nyaa、acg.rip 沒有番組頁（票 11）：候選只從標題來，年份無從確認，一律留給人一鍵選。"""

    async def test_an_acgrip_series_is_offered_its_candidate_and_left_to_you(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, factory = await moored(session, roots)
        factory.rss_.pages[ACGRIP_URL] = ACGRIP
        feed = await add_feed(session, url=ACGRIP_URL, name="")

        polled = await poll_feed(session, factory, feed.id, now=NOW)

        assert polled.bound == 0
        view = next(row for row in await list_series(session) if row.key == LOLIHOUSE_KEY)
        assert view.media_id is None
        assert codes(view.reasons) == [BindReasonCode.NO_SHOW_PAGE]
        assert [one.id for one in view.candidates] == [KIMI_ID]
        # 沒有番組頁可抓：除了 feed 本身，沒有別的請求。
        assert factory.rss_.requested == [ACGRIP_URL]
