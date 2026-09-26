"""自動綁定的兩種失敗（M4 票 14，brief §19 2026-09-26）：暫時查不到有退避、有上限地重認；一個候選
讀不到不拖垮整次；季名不進搜尋詞、改當判斷的線索。

替身沿用 `test_rss_auto_bind`：票 07 錄下來的 Mikan 聚合 feed，《与你相恋到生命尽头》有番組頁
（4009），其餘十個 Series 的番組頁不在替身裡（連不上）。Re:Zero 的番組頁照 Mikan 的形狀合成。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.budget import RequestBudget, site_of
from berth.adapters.rss.mikan import bangumi_url
from berth.adapters.tmdb import TmdbDetail, TmdbEntry, TmdbEpisode, TmdbSeason, TmdbSeasonEntry
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.domain import BindReasonCode, MediaKind
from berth.models import RssItem, RssSeries
from berth.services.rss import LOOKUP_RETRIES, SeriesView, add_feed, list_series, poll_feed
from tests.integration.factories import answered
from tests.integration.test_rss import FEED_URL, ITEMS, KIMI_ID, KIMI_KEY, NOW
from tests.integration.test_rss_auto_bind import KIMI_TMDB, codes, kimi_tmdb, moored

pytestmark = pytest.mark.asyncio


#: TMDB 詳情那一支請求（`answered` 的原文照它寫）。
TMDB_DETAIL = f"GET /3/tv/{KIMI_TMDB}"


async def view_of(session: AsyncSession, key: str) -> SeriesView:
    return next(row for row in await list_series(session) if row.key == key)


class TestTransientFailureIsRetried:
    """尼古喵喵：`tmdb detail: tv:312949 could not be read`，同日稍後同一支詳情回 200。"""

    @pytest.mark.parametrize("status", [502, 429])
    async def test_a_detail_that_failed_once_binds_on_the_retry(
        self, session: AsyncSession, roots: dict[str, Path], status: int
    ) -> None:
        tmdb = kimi_tmdb()
        tmdb.detail_errors[(MediaKind.TV, KIMI_TMDB)] = answered(status, TMDB_DETAIL)
        _, factory = await moored(session, roots, tmdb=tmdb)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        await poll_feed(session, factory, feed.id, now=NOW)
        assert (await view_of(session, KIMI_KEY)).media_id is None

        del tmdb.detail_errors[(MediaKind.TV, KIMI_TMDB)]
        polled = await poll_feed(session, factory, feed.id, now=NOW + LOOKUP_RETRIES[0])

        assert polled.bound == 1
        bound = await view_of(session, KIMI_KEY)
        assert (bound.media_id, bound.bound_by) == (KIMI_ID, "system")

    async def test_the_waiting_series_says_when_it_is_looked_up_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        tmdb = kimi_tmdb()
        tmdb.detail_errors[(MediaKind.TV, KIMI_TMDB)] = answered(502, TMDB_DETAIL)
        _, factory = await moored(session, roots, tmdb=tmdb)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        await poll_feed(session, factory, feed.id, now=NOW)

        waiting = await view_of(session, KIMI_KEY)
        assert codes(waiting.reasons) == [BindReasonCode.LOOKUP_RETRY]
        assert waiting.reasons[0].params == {
            "site": "api.themoviedb.org",
            "attempt": 1,
            "at": (NOW + LOOKUP_RETRIES[0]).isoformat(),
            "detail": f"tmdb detail: tv:{KIMI_TMDB}: GET /3/tv/{KIMI_TMDB}: 502",
        }

    async def test_the_retry_waits_for_its_time(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """壞掉的番組頁不會每 15 分鐘被打一次：退避的時間沒到，輪詢不重認。"""
        tmdb = kimi_tmdb()
        tmdb.detail_errors[(MediaKind.TV, KIMI_TMDB)] = answered(502, TMDB_DETAIL)
        _, factory = await moored(session, roots, tmdb=tmdb)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        await poll_feed(session, factory, feed.id, now=NOW)
        del tmdb.detail_errors[(MediaKind.TV, KIMI_TMDB)]
        factory.rss_.requested.clear()

        await poll_feed(session, factory, feed.id, now=NOW + timedelta(minutes=15))

        assert bangumi_url(4009) not in factory.rss_.requested
        assert (await view_of(session, KIMI_KEY)).media_id is None

    async def test_retries_run_out_into_lookup_failed_after_a_bounded_number_of_asks(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """番組頁一直連不上：照退避重認，用完落到 `lookup_failed` 等人。一天半、每 15 分鐘一輪，
        那一頁只被問 1 + 重試次數那麼多次，每一次都在 Mikan 的請求預算裡佔一格。"""
        _, factory = await moored(session, roots)
        factory.budget = RequestBudget(limit=100_000, window=timedelta(days=30))
        del factory.rss_.pages[bangumi_url(4009)]
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        for quarter in range(4 * 36):
            await poll_feed(session, factory, feed.id, now=NOW + timedelta(minutes=15 * quarter))

        page = bangumi_url(4009)
        assert factory.rss_.requested.count(page) == 1 + len(LOOKUP_RETRIES)
        mikan = [url for url in factory.rss_.requested if site_of(url) == "mikanani.me"]
        (usage,) = [row for row in factory.budget.usage() if row.site == "mikanani.me"]
        assert usage.used == len(mikan)
        view = await view_of(session, KIMI_KEY)
        assert codes(view.reasons) == [BindReasonCode.LOOKUP_FAILED]
        assert "connection refused" in str(view.reasons[0].params["detail"])

    async def test_a_page_that_is_not_there_is_not_retried(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """404 再問幾次都一樣：當場落到 `lookup_failed`。"""
        _, factory = await moored(session, roots)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")
        page = bangumi_url(4009)
        factory.rss_.page_errors[page] = answered(404, f"GET {page}")

        await poll_feed(session, factory, feed.id, now=NOW)
        await poll_feed(session, factory, feed.id, now=NOW + LOOKUP_RETRIES[0])

        assert factory.rss_.requested.count(page) == 1
        assert codes((await view_of(session, KIMI_KEY)).reasons) == [BindReasonCode.LOOKUP_FAILED]


class TestOneBrokenCandidate:
    """搜到兩部、其中一部的詳情讀不到：其餘的照判，全部讀不到才算查不到。"""

    @staticmethod
    def with_a_stranger(tmdb: FakeTmdbClient) -> FakeTmdbClient:
        """搜尋多回一部 999，它的詳情讀不到（502）。"""
        stranger = TmdbEntry(
            tmdb_id=999, kind=MediaKind.TV, title="Kimishinu", original_title="", year=2026,
            poster_path="",
        )  # fmt: skip
        for query in ("与你相恋到生命尽头", "kimi ga shinu made koi wo shitai"):
            tmdb.search_results[query] = [*tmdb.search_results[query], stranger]
        tmdb.detail_errors[(MediaKind.TV, 999)] = answered(502, TMDB_DETAIL)
        return tmdb

    @staticmethod
    def readable_stranger(tmdb: FakeTmdbClient) -> FakeTmdbClient:
        """999 讀得到，但它是另一部作品（名字不同）。"""
        del tmdb.detail_errors[(MediaKind.TV, 999)]
        kimi = tmdb.details[(MediaKind.TV, KIMI_TMDB)]
        tmdb.details[(MediaKind.TV, 999)] = replace(
            kimi, tmdb_id=999, title="Someone Else", original_title="", titles=("Someone Else",)
        )
        tmdb.season_rows[(999, 1)] = tmdb.season_rows[(KIMI_TMDB, 1)]
        return tmdb

    async def test_the_readable_one_still_binds(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, factory = await moored(session, roots, tmdb=self.with_a_stranger(kimi_tmdb()))
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        polled = await poll_feed(session, factory, feed.id, now=NOW)

        assert polled.bound == 1
        assert (await view_of(session, KIMI_KEY)).media_id == KIMI_ID

    async def test_every_one_broken_is_still_a_failed_lookup(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        tmdb = self.with_a_stranger(kimi_tmdb())
        tmdb.detail_errors[(MediaKind.TV, KIMI_TMDB)] = answered(502, TMDB_DETAIL)
        _, factory = await moored(session, roots, tmdb=tmdb)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        await poll_feed(session, factory, feed.id, now=NOW)

        view = await view_of(session, KIMI_KEY)
        assert view.media_id is None
        assert codes(view.reasons) == [BindReasonCode.LOOKUP_RETRY]

    async def test_every_one_gone_for_good_fails_without_a_retry(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        # TMDB 的詳情 404 在 adapter 是 `NotFoundError`（替身讀不到那一部時就丟它）。
        tmdb = self.with_a_stranger(kimi_tmdb())
        del tmdb.detail_errors[(MediaKind.TV, 999)]
        del tmdb.details[(MediaKind.TV, KIMI_TMDB)]
        _, factory = await moored(session, roots, tmdb=tmdb)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        await poll_feed(session, factory, feed.id, now=NOW)

        assert codes((await view_of(session, KIMI_KEY)).reasons) == [BindReasonCode.LOOKUP_FAILED]

    async def test_when_the_rest_is_not_enough_a_transient_miss_is_retried(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """讀得到的那一部不是它、讀不到的那一部可能就是：這一次判不出來，照暫時的失敗晚點再認。"""
        tmdb = self.readable_stranger(self.with_a_stranger(kimi_tmdb()))
        tmdb.detail_errors[(MediaKind.TV, KIMI_TMDB)] = answered(502, TMDB_DETAIL)
        _, factory = await moored(session, roots, tmdb=tmdb)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        await poll_feed(session, factory, feed.id, now=NOW)

        assert codes((await view_of(session, KIMI_KEY)).reasons) == [BindReasonCode.LOOKUP_RETRY]

    async def test_when_the_retries_run_out_both_the_verdict_and_the_miss_are_said(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """重認用完、讀得到的那一部仍然不是它：判定的理由與「那一部讀不到」都留著，不只說
        `no_candidate`。"""
        tmdb = self.readable_stranger(self.with_a_stranger(kimi_tmdb()))
        tmdb.detail_errors[(MediaKind.TV, KIMI_TMDB)] = answered(502, TMDB_DETAIL)
        _, factory = await moored(session, roots, tmdb=tmdb)
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        moment = NOW
        await poll_feed(session, factory, feed.id, now=moment)
        for wait in LOOKUP_RETRIES:
            moment += wait
            await poll_feed(session, factory, feed.id, now=moment)

        assert codes((await view_of(session, KIMI_KEY)).reasons) == [
            BindReasonCode.NO_CANDIDATE,
            BindReasonCode.LOOKUP_FAILED,
        ]


# --- 季名 ---------------------------------------------------------------------------------

REZERO_TITLE = "[ANi]  Re：从零开始的异世界生活 第四季"
REZERO_TMDB = 65942
REZERO_ID = f"tv:{REZERO_TMDB}"
#: Mikan 番組頁 4052（第四季的第二個 cour「夺还篇」）的「放送开始」，也是 TMDB 第 1 季第 78 集的
#: 播出日，2026-09-26 查。
REZERO_PREMIERE = date(2026, 8, 12)


def rezero_show_page() -> bytes:
    """Mikan 番組頁的形狀：第一個 `p.bangumi-title` 的直屬文字與「放送开始」。"""
    return (
        '<p class="bangumi-title">Re：从零开始的异世界生活 第四季 夺还篇 '
        '<a href="/RSS/Bangumi?bangumiId=4052" class="mikan-rss">RSS</a></p>'
        f"<p>放送开始：{REZERO_PREMIERE.month}/{REZERO_PREMIERE.day}/{REZERO_PREMIERE.year}</p>"
    ).encode()


def rezero_tmdb() -> FakeTmdbClient:
    """TMDB 65942：四輪播出全部放在第 1 季，一共 85 集；第四輪的兩個 cour 隔 56 天
    （2026-09-26 查）。"""
    tmdb = kimi_tmdb()
    entry = TmdbEntry(
        tmdb_id=REZERO_TMDB,
        kind=MediaKind.TV,
        title="Re:ZERO -Starting Life in Another World-",
        original_title="Re:ゼロから始める異世界生活",
        year=2016,
        poster_path="",
    )
    # 只有拿掉季名與篇名的那一個查詢搜得到（`search_media` 先正規化成小寫再問）。
    tmdb.search_results["re：从零开始的异世界生活"] = [entry]
    #: （這一輪第一集的播出日, 第一集的集號, 集數）
    runs = (
        (date(2016, 4, 4), 1, 25),
        (date(2020, 7, 8), 26, 25),
        (date(2024, 10, 2), 51, 16),
        (date(2026, 4, 8), 67, 11),
        (REZERO_PREMIERE, 78, 8),
    )
    episodes = tuple(
        TmdbEpisode(1, first + n, f"Episode {first + n}", aired + timedelta(weeks=n), 25)
        for aired, first, count in runs
        for n in range(count)
    )
    tmdb.details[(MediaKind.TV, REZERO_TMDB)] = TmdbDetail(
        tmdb_id=REZERO_TMDB,
        kind=MediaKind.TV,
        title="Re:ZERO -Starting Life in Another World-",
        original_title="Re:ゼロから始める異世界生活",
        year=2016,
        first_air_date=date(2016, 4, 4),
        overview="",
        poster_path="",
        titles=("Re:ZERO -Starting Life in Another World-", "Re：从零开始的异世界生活"),
        seasons=(TmdbSeasonEntry(1, "Season 1", len(episodes), date(2016, 4, 4)),),
    )
    tmdb.season_rows[(REZERO_TMDB, 1)] = TmdbSeason(
        season_number=1, name="Season 1", air_date=date(2016, 4, 4), episodes=episodes
    )
    return tmdb


class TestSeasonName:
    async def test_a_release_named_with_its_season_binds_to_the_merged_work(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Re:Zero：「第四季」一起搜是 `no_candidate`；拿掉之後搜到 65942，Mikan 寫的開播日落在
        TMDB 第四輪播出的期間。"""
        _, factory = await moored(session, roots, tmdb=rezero_tmdb())
        index = next(i for i, item in enumerate(ITEMS) if item.title.startswith(REZERO_TITLE))
        # `episode_pages()` 把第 i 筆的番組 id 合成成 5000 + i。
        factory.rss_.pages[bangumi_url(5000 + index)] = rezero_show_page()
        feed = await add_feed(session, url=FEED_URL, name="Mikan")

        await poll_feed(session, factory, feed.id, now=NOW)

        series = await session.scalar(
            select(RssSeries).where(
                RssSeries.id.in_(
                    select(RssItem.series_id).where(RssItem.title.startswith(REZERO_TITLE))
                )
            )
        )
        assert series is not None
        assert (series.media_id, series.bound_by) == (REZERO_ID, "system")
        view = await view_of(session, series.key)
        assert codes(view.reasons)[:2] == [
            BindReasonCode.TITLE_EQUAL,
            BindReasonCode.SEASON_AIRING,
        ]
        assert view.reasons[0].params["clue"] == "Re：从零开始的异世界生活"
        assert view.reasons[1].params == {
            "premiere": "2026-08-12",
            "season": 4,
            "episode": "S01E78",
            "aired": "2026-08-12",
        }
