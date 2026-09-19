"""探索與搜尋的命令（plan §8.3、§2.2、票 03）。

這裡驗的是三件事：**兩種語言怎麼合**（英文那一輪是清單本身，`zh-TW` 那一輪只補顯示用標題）、
**快取一小時**（同一查詢第二次不打外部），以及**拿不到 TMDB 時說得出下一步**。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import AuthFailedError, ServiceUnavailableError
from berth.adapters.tmdb import TmdbConfiguration, TmdbEntry
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.domain import MediaKind, TmdbProblem
from berth.models import TmdbCache, TmdbSettings
from berth.services.discover import (
    CACHE_TTL,
    read_popular,
    read_trending,
    search_media,
)
from berth.services.settings import read_settings, write_settings
from tests.conftest import TMDB_API_KEY
from tests.integration.factories import FakeClientFactory

pytestmark = pytest.mark.asyncio


def entry(
    tmdb_id: int,
    kind: MediaKind,
    title: str,
    *,
    original: str = "",
    year: int | None = 2026,
    poster: str = "/poster.jpg",
) -> TmdbEntry:
    return TmdbEntry(
        tmdb_id=tmdb_id,
        kind=kind,
        title=title,
        original_title=original or title,
        year=year,
        poster_path=poster,
    )


LANTERNS = entry(95350, MediaKind.TV, "Lanterns")
SILO = entry(125988, MediaKind.TV, "Silo", year=2023)
MOANA = entry(1108427, MediaKind.MOVIE, "Moana")
ODYSSEY = entry(1368337, MediaKind.MOVIE, "The Odyssey")
SPY_FAMILY = entry(120089, MediaKind.TV, "SPY x FAMILY", year=2022)


def tmdb(**kwargs: object) -> FakeTmdbClient:
    """預設有兩支劇集、兩部電影，趨勢與熱門用同一份。"""
    defaults: dict[str, object] = {
        "trending": {MediaKind.TV: [LANTERNS, SILO], MediaKind.MOVIE: [MOANA, ODYSSEY]},
        "popular": {MediaKind.TV: [SILO], MediaKind.MOVIE: [MOANA]},
        "search": {"spy x family": [SPY_FAMILY]},
    }
    # `**kwargs` 是 `object`，而 FakeTmdbClient 的每個參數各有自己的型別；這裡刻意用一個
    # 寬鬆的入口讓每個測試只覆寫它在乎的那一個（`fake_jellyfin` 同一個寫法）。
    return FakeTmdbClient(**{**defaults, **kwargs})  # type: ignore[arg-type]


async def credentialled(session: AsyncSession, client: FakeTmdbClient) -> FakeClientFactory:
    """精靈第 6 步做完的樣子：憑證存下來了（票 02b 之後它是必填閘門）。"""
    await write_settings(session, TmdbSettings(api_key=TMDB_API_KEY))
    await session.commit()
    return FakeClientFactory(tmdb=client)


class TestTrending:
    async def test_it_interleaves_series_and_films(self, session: AsyncSession) -> None:
        """一面牆上兩種作品輪流站，而不是先十部劇再十部電影。

        兩份清單各自照 TMDB 給的順序（**趨勢排名不是 `popularity` 排序**，2026-09-09 實測
        `popularity` 在回應裡是亂序的），所以合併只能交錯，不能重排。
        """
        client = tmdb()
        result = await read_trending(session, await credentialled(session, client))

        assert [item.id for item in result.items] == [
            "tv:95350",
            "movie:1108427",
            "tv:125988",
            "movie:1368337",
        ]
        assert result.problem is None

    async def test_the_display_title_comes_from_the_zh_tw_round(
        self, session: AsyncSession
    ) -> None:
        """英文標題留著：檔名與比對用的是它（brief §7.5）。"""
        client = tmdb(translations={95350: "綠燈軍團"})
        result = await read_trending(session, await credentialled(session, client))

        lanterns = result.items[0]
        assert (lanterns.title, lanterns.title_en) == ("綠燈軍團", "Lanterns")

    async def test_an_untranslated_work_keeps_its_english_title(
        self, session: AsyncSession
    ) -> None:
        client = tmdb(translations={95350: "綠燈軍團"})
        result = await read_trending(session, await credentialled(session, client))

        silo = next(item for item in result.items if item.id == "tv:125988")
        assert (silo.title, silo.title_en) == ("Silo", "Silo")

    async def test_a_work_missing_from_the_zh_tw_round_still_shows_up(
        self, session: AsyncSession
    ) -> None:
        """`language` 會換掉趨勢的**成員**，不只文字（2026-09-09 實測，20 筆差 3 筆）。

        所以清單是英文那一輪，`zh-TW` 只是一張查得到就用的表——反過來做會讓作品消失。
        """
        client = tmdb(display_absent=[125988])
        result = await read_trending(session, await credentialled(session, client))

        assert "tv:125988" in [item.id for item in result.items]

    async def test_the_poster_url_is_built_from_the_configuration_base(
        self, session: AsyncSession
    ) -> None:
        client = tmdb()
        result = await read_trending(session, await credentialled(session, client))

        assert result.items[0].poster_url == "https://image.tmdb.org/t/p/w342/poster.jpg"

    async def test_the_poster_comes_from_both_rounds(self, session: AsyncSession) -> None:
        """TMDB 的海報也分語言（票 11）：兩輪都送，畫面照 UI 語言挑——中文標題配英文海報是
        兩個來源拼出來的東西，反過來也是。"""
        client = tmdb(poster_translations={95350: "/zh.jpg"})
        result = await read_trending(session, await credentialled(session, client))

        lanterns = result.items[0]
        assert lanterns.poster_url == "https://image.tmdb.org/t/p/w342/zh.jpg"
        assert lanterns.poster_url_en == "https://image.tmdb.org/t/p/w342/poster.jpg"

    async def test_a_work_with_no_translated_poster_shows_the_english_one(
        self, session: AsyncSession
    ) -> None:
        client = tmdb(poster_translations={95350: "/zh.jpg"})
        result = await read_trending(session, await credentialled(session, client))

        silo = next(item for item in result.items if item.id == "tv:125988")
        assert silo.poster_url == silo.poster_url_en != ""

    async def test_a_work_without_a_poster_gets_an_empty_url(self, session: AsyncSession) -> None:
        """卡片自己畫沒有海報的樣子；組出半條網址只會變成一個破圖。"""
        client = tmdb(trending={MediaKind.TV: [entry(1, MediaKind.TV, "No Art", poster="")]})
        result = await read_trending(session, await credentialled(session, client))

        assert (result.items[0].poster_url, result.items[0].poster_url_en) == ("", "")


class TestCache:
    async def test_the_second_call_does_not_reach_tmdb(self, session: AsyncSession) -> None:
        client = tmdb()
        factory = await credentialled(session, client)

        first = await read_trending(session, factory)
        requested = len(client.requests)
        second = await read_trending(session, factory)

        assert len(client.requests) == requested
        assert [item.id for item in second.items] == [item.id for item in first.items]

    async def test_each_feed_has_its_own_row(self, session: AsyncSession) -> None:
        client = tmdb()
        factory = await credentialled(session, client)

        await read_trending(session, factory)
        popular = await read_popular(session, factory)

        assert [item.id for item in popular.items] == ["tv:125988", "movie:1108427"]

    async def test_an_expired_row_is_refetched(self, session: AsyncSession) -> None:
        client = tmdb()
        factory = await credentialled(session, client)
        await read_trending(session, factory)
        await _age(session, CACHE_TTL + timedelta(minutes=1))
        client.requests.clear()

        await read_trending(session, factory)

        assert client.requests != []

    async def test_a_row_just_under_the_hour_still_counts(self, session: AsyncSession) -> None:
        client = tmdb()
        factory = await credentialled(session, client)
        await read_trending(session, factory)
        await _age(session, CACHE_TTL - timedelta(minutes=1))
        client.requests.clear()

        await read_trending(session, factory)

        assert client.requests == []

    async def test_the_same_search_normalises_to_one_row(self, session: AsyncSession) -> None:
        """大小寫與多餘空白不該各佔一格快取。"""
        client = tmdb()
        factory = await credentialled(session, client)

        await search_media(session, factory, "spy x family")
        requested = len(client.requests)
        result = await search_media(session, factory, "  SPY  X  Family ")

        assert len(client.requests) == requested
        assert [item.id for item in result.items] == ["tv:120089"]

    async def test_a_row_cached_before_the_language_split_still_carries_both_titles(
        self, session: AsyncSession
    ) -> None:
        """顯示用標題跟著 UI 語言走之後（M1.5 票 02），快取裡還沒過期的舊列照樣畫得出兩種語言。

        卡片從票 03 起就兩輪都帶（`title` 是 `zh-TW`、`title_en` 是 `en-US`），所以這一票不改快取的
        形狀；這一條釘住的是「不必為了換語言而丟掉快取」。
        """
        client = tmdb()
        factory = await credentialled(session, client)
        session.add(
            TmdbCache(
                key="discover:trending",
                # M1 寫下的形狀，逐鍵照抄，刻意不從 `MediaCard` 產生。
                value_json=[
                    {
                        "tmdb_id": 95350,
                        "kind": "tv",
                        "title": "綠燈軍團",
                        "title_en": "Lanterns",
                        "year": 2026,
                        "poster_url": "",
                    }
                ],
                fetched_at=datetime.now(UTC),
            )
        )
        await session.commit()

        result = await read_trending(session, factory)

        assert [(item.title, item.title_en) for item in result.items] == [("綠燈軍團", "Lanterns")]
        assert client.requests == []

    async def test_an_empty_search_asks_tmdb_nothing(self, session: AsyncSession) -> None:
        client = tmdb()
        factory = await credentialled(session, client)

        result = await search_media(session, factory, "   ")

        assert (result.items, result.problem, client.requests) == ((), None, [])


class TestSearch:
    async def test_it_returns_the_matches_in_tmdb_order(self, session: AsyncSession) -> None:
        client = tmdb(search={"spy x family": [SPY_FAMILY, MOANA]})
        result = await search_media(session, await credentialled(session, client), "spy x family")

        assert [item.id for item in result.items] == ["tv:120089", "movie:1108427"]

    async def test_the_query_reaches_tmdb_in_both_languages(self, session: AsyncSession) -> None:
        client = tmdb()
        await search_media(session, await credentialled(session, client), "spy x family")

        assert client.requests == [
            ("search/spy x family", "en-US"),
            ("search/spy x family", "zh-TW"),
        ]


class TestProblems:
    async def test_a_missing_credential_is_named_and_costs_no_request(
        self, session: AsyncSession
    ) -> None:
        """票 02b 之後憑證是使用者自備的必填項，所以「沒有 key」是最可能的失敗。"""
        client = tmdb()
        result = await read_trending(session, FakeClientFactory(tmdb=client))

        assert result.problem is TmdbProblem.CREDENTIAL_MISSING
        assert client.requests == []

    async def test_a_rejected_credential_is_told_apart_from_a_missing_one(
        self, session: AsyncSession
    ) -> None:
        client = tmdb()
        client.error = AuthFailedError("GET /trending/tv/week: 401")
        result = await read_trending(session, await credentialled(session, client))

        assert result.problem is TmdbProblem.CREDENTIAL_REJECTED
        assert result.detail == "GET /trending/tv/week: 401"

    async def test_an_unreachable_tmdb_is_its_own_problem(self, session: AsyncSession) -> None:
        """憑證沒問題、網路有問題——修法完全不同，所以不共用一句話。"""
        client = tmdb()
        client.error = ServiceUnavailableError("GET /trending/tv/week: connection refused")
        result = await read_trending(session, await credentialled(session, client))

        assert result.problem is TmdbProblem.UNREACHABLE
        assert result.items == ()

    async def test_a_failed_fetch_leaves_no_cache_row(self, session: AsyncSession) -> None:
        """失敗不該被快取一小時：使用者貼上正確的 key 之後要立刻看得到東西。"""
        client = tmdb()
        client.error = AuthFailedError("GET /trending/tv/week: 401")
        factory = await credentialled(session, client)
        await read_trending(session, factory)

        client.error = None
        result = await read_trending(session, factory)

        assert result.items != ()


class TestImageBase:
    async def test_the_configuration_base_is_stored_so_it_is_fetched_once(
        self, session: AsyncSession
    ) -> None:
        """`configuration` 對同一把憑證是常數。每次探索都問一次是白花一個請求。"""
        client = tmdb()
        factory = await credentialled(session, client)

        await read_trending(session, factory)
        await _age(session, CACHE_TTL + timedelta(minutes=1))
        await read_trending(session, factory)

        assert client.calls == 1
        assert (
            await read_settings(session, TmdbSettings)
        ).image_base_url == "https://image.tmdb.org/t/p/"

    async def test_it_is_fetched_when_the_wizard_ran_before_this_field_existed(
        self, session: AsyncSession
    ) -> None:
        """升級上來的資料庫裡沒有這個欄位的值，而精靈是不會再跑一次的。"""
        client = tmdb(configuration=TmdbConfiguration(image_base_url="https://cdn.example/t/p/"))
        result = await read_trending(session, await credentialled(session, client))

        assert result.items[0].poster_url == "https://cdn.example/t/p/w342/poster.jpg"


async def _age(session: AsyncSession, by: timedelta) -> None:
    """把每一列快取的時間往前推，模擬時間過去。"""
    for row in (await session.scalars(select(TmdbCache))).all():
        row.fetched_at = datetime.now(UTC) - by
    await session.commit()
