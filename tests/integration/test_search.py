"""索引站搜尋這一支命令（票 08、plan §6 search 群組）。

驗的是**領域決策**：哪幾個關鍵字問出去、結果怎麼合併去重、一個查詢垮掉時剩下的還在不在、
每一列的 Tags 與預估季集是什麼。協定本身（Prowlarr 的 REST）由
`test_indexer_search.py` 對錄製回應守著，所以這裡一律用 `FakeIndexerSearch`。
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import AuthFailedError, ServiceUnavailableError
from berth.adapters.indexer import IndexerResult, SearchQuery
from berth.adapters.indexer.fake import FakeIndexerSearch
from berth.domain import (
    IndexerProblem,
    MappingStrategy,
    MediaKind,
    NameKind,
    SearchVerdict,
    Source,
    StepStatus,
)
from berth.models import IndexerSettings, Media, Route
from berth.models import media_id as build_media_id
from berth.services.search import (
    OTHERS_LIMIT,
    RESULT_LIMIT,
    QueryScope,
    SearchView,
    plan_queries,
    remember_names,
    search_torrents,
)
from berth.services.search_queries import MAX_QUERIES, QueryChoice
from berth.services.settings import write_settings
from berth.services.sources import SourceCache
from tests.integration.factories import FakeClientFactory
from tests.integration.test_inventory import linked, route, title
from tests.integration.test_inventory import season as season_snapshot

SPY = build_media_id(MediaKind.TV, 120089)
OPPENHEIMER = build_media_id(MediaKind.MOVIE, 872585)


def result(title: str, **kwargs: Any) -> IndexerResult:
    return IndexerResult(title=title, **kwargs)


def listed(view: SearchView, verdict: SearchVerdict = SearchVerdict.FITS) -> list[str]:
    """送出來的列裡歸到這一類的發佈名，照送出來的順序。"""
    return [row.title for row in view.rows if row.verdict is verdict]


def count(view: SearchView, verdict: SearchVerdict = SearchVerdict.FITS) -> int:
    """這一類在每一站的總筆數加起來。"""
    return sum(one.total for one in view.counts if one.verdict is verdict)


def verdicts(view: SearchView) -> set[SearchVerdict]:
    """這一次搜尋有哪幾類（`counts` 是每一類每一站一筆）。"""
    return {one.verdict for one in view.counts}


async def arrange_media(session: AsyncSession) -> None:
    """一列已經有快照的 Media。搜尋不必再打 TMDB（plan §8.3 的 24 小時還沒到）。"""
    snapshot = {
        "tmdb_id": 120089,
        "kind": "tv",
        "title": "間諜家家酒",
        "title_en": "SPY x FAMILY",
        "title_original": "SPY×FAMILY",
        "year": 2022,
        "titles": ["SPY x FAMILY", "SPY×FAMILY", "間諜家家酒", "间谍过家家"],
        "seasons": [
            {
                "season_number": 1,
                "name": "Season 1",
                "episode_count": 12,
                "air_date": "2022-04-09",
                "episodes": [{"episode_number": n, "name": f"E{n}"} for n in range(1, 13)],
            },
            {
                "season_number": 3,
                "name": "Season 3",
                "episode_count": 13,
                # 首播之後幾年的發佈名寫的是那一季的年份（M4 票 49 的年份篩看整段播出期間）。
                "air_date": "2025-10-04",
                "episodes": [{"episode_number": n, "name": f"E{n}"} for n in range(1, 14)],
            },
        ],
    }
    session.add(
        Media(
            id=SPY,
            tmdb_id=120089,
            kind=MediaKind.TV,
            title_en="SPY x FAMILY",
            title_original="SPY×FAMILY",
            year=2022,
            folder_name="SPY x FAMILY (2022) [tmdbid-120089]",
            tmdb_snapshot_json=snapshot,
            tmdb_fetched_at=datetime.now(UTC),
        )
    )
    await session.commit()


async def arrange_indexer(session: AsyncSession) -> None:
    """精靈第 6 步接好的樣子：有位址、有 key。"""
    await write_settings(session, IndexerSettings(base_url="http://prowlarr:9696", api_key="k"))
    await session.commit()


async def restyle(session: AsyncSession, **fields: Any) -> None:
    """把存下來的快照換掉幾格：同一列 Media，換成另一種作品的樣子。"""
    row = await session.get(Media, SPY)
    assert row is not None
    row.tmdb_snapshot_json = {**(row.tmdb_snapshot_json or {}), **fields}
    await session.commit()


def season_queries(indexer: FakeIndexerSearch) -> list[str]:
    """問出去的查詢裡，哪幾個是季號變體（`Season N` / `第N季`）。"""
    return [query.text for query in indexer.queries if "Season" in query.text or "季" in query.text]


def season_of(number: int, episodes: int) -> dict[str, Any]:
    return {
        "season_number": number,
        "name": f"Season {number}",
        "episode_count": episodes,
        "episodes": [{"episode_number": n, "name": f"E{n}"} for n in range(1, episodes + 1)],
    }


@pytest.mark.asyncio
async def test_every_known_title_gets_its_own_query_and_the_results_merge(
    session: AsyncSession,
) -> None:
    """開了的名字各發一次：實測三個標題的聯集比任何一個都大得多（票 08）。"""
    await arrange_media(session)
    await arrange_indexer(session)
    await restyle(session, seasons=[season_of(1, 12)])
    every = QueryChoice(names=("SPY x FAMILY", "SPY×FAMILY", "間諜家家酒", "间谍过家家"))
    indexer = FakeIndexerSearch(
        by_query={
            "SPY x FAMILY": (result("SPY x FAMILY S03E01 1080p WEB", info_hash="a" * 40),),
            "SPY×FAMILY": (result("SPY×FAMILY 03", info_hash="b" * 40),),
            "間諜家家酒": (result("間諜家家酒 03", info_hash="c" * 40),),
            "间谍过家家": (result("间谍过家家 03", info_hash="d" * 40),),
        }
    )
    factory = FakeClientFactory(indexer_search=indexer)

    view = await search_torrents(
        session, factory, SourceCache(), media_id=SPY, scope=QueryScope(choice=every)
    )

    assert sorted(query.text for query in indexer.queries) == sorted(
        ["SPY x FAMILY", "SPY×FAMILY", "間諜家家酒", "间谍过家家"]
    )
    assert count(view) == 4
    assert view.problem is None


@pytest.mark.asyncio
async def test_the_same_torrent_from_two_sites_is_one_row(session: AsyncSession) -> None:
    """去重的鑰匙是 info hash，寫法不同也算同一個（實測 dmhy 是 base32、Mikan 是十六進位）。"""
    await arrange_media(session)
    await arrange_indexer(session)
    hex_hash = "4bd0f6ef8a1a55b38b7a4d4f7b10458cfa8b8d3f"
    indexer = FakeIndexerSearch(
        results=(
            result("[LoliHouse] Spy x Family [38-50]", indexer="Mikan", info_hash=hex_hash),
            result("[LoliHouse] Spy x Family [38-50]", indexer="dmhy", info_hash=hex_hash),
            result(
                "[ANi] SPY x FAMILY - 26 [1080P]",
                indexer="ACG.RIP",
                guid="https://acg.rip/t/1.torrent",
            ),
        )
    )
    factory = FakeClientFactory(indexer_search=indexer)

    view = await search_torrents(session, factory, SourceCache(), media_id=SPY)

    assert count(view) == 2
    assert sorted(row.indexer for row in view.rows) == ["ACG.RIP", "Mikan"]


@pytest.mark.asyncio
async def test_rows_come_back_seeded_first_and_capped(session: AsyncSession) -> None:
    """一次搜尋可以回一千多筆（實測 1854）。畫面拿到的是做種最多的前 100 筆與總數。"""
    await arrange_media(session)
    await arrange_indexer(session)
    indexer = FakeIndexerSearch(
        results=tuple(
            result(f"SPY x FAMILY S03E{n:02d}", info_hash=f"{n:040x}", seeders=n)
            for n in range(1, RESULT_LIMIT + 21)
        )
    )
    factory = FakeClientFactory(indexer_search=indexer)

    view = await search_torrents(session, factory, SourceCache(), media_id=SPY)

    assert count(view) == RESULT_LIMIT + 20
    assert len(view.rows) == RESULT_LIMIT
    assert [row.seeders for row in view.rows[:3]] == [
        RESULT_LIMIT + 20,
        RESULT_LIMIT + 19,
        RESULT_LIMIT + 18,
    ]


@pytest.mark.asyncio
async def test_every_site_gets_a_seat_at_the_table(session: AsyncSession) -> None:
    """上限內逐站輪流取，不是純粹取做種前 N 筆。

    2026-09-10 實跑：The Pirate Bay 的 scene 發佈有 28–86 個做種，Mikan 那一千多筆多半是
    個位數，於是做種前 100 筆**全部**來自同一個站——中文字幕組的版本一筆都看不到。
    """
    await arrange_media(session)
    await arrange_indexer(session)
    indexer = FakeIndexerSearch(
        results=(
            *(
                result(
                    f"SPY x FAMILY S02E{n:02d} 1080p WEB",
                    indexer="The Pirate Bay",
                    info_hash=f"{n:040x}",
                    seeders=80,
                )
                for n in range(1, RESULT_LIMIT + 21)
            ),
            result(
                "[桜都字幕组] 间谍过家家 [01][1080p]",
                indexer="Mikan",
                info_hash="f" * 40,
                seeders=2,
            ),
        )
    )
    factory = FakeClientFactory(indexer_search=indexer)

    view = await search_torrents(session, factory, SourceCache(), media_id=SPY)

    assert len(view.rows) == RESULT_LIMIT
    assert sorted({row.indexer for row in view.rows}) == ["Mikan", "The Pirate Bay"]


@pytest.mark.asyncio
async def test_one_failing_query_does_not_sink_the_others(session: AsyncSession) -> None:
    """一個標題查不動時剩下的照樣回得來，而畫面說得出是哪一個垮了（票 08 驗收）。"""
    await arrange_media(session)
    await arrange_indexer(session)
    indexer = FakeIndexerSearch(
        by_query={"SPY x FAMILY": (result("SPY x FAMILY S03E01", info_hash="a" * 40),)},
        errors={"SPY×FAMILY": ServiceUnavailableError("GET /api/v1/search: ReadTimeout")},
    )
    factory = FakeClientFactory(indexer_search=indexer)

    view = await search_torrents(session, factory, SourceCache(), media_id=SPY)

    assert view.problem is None
    assert count(view) == 1
    failed = [attempt for attempt in view.attempts if attempt.status is StepStatus.FAILED]
    assert [attempt.step for attempt in failed] == ["SPY×FAMILY"]
    assert failed[0].error == "GET /api/v1/search: ReadTimeout"


@pytest.mark.asyncio
async def test_an_indexer_that_was_never_set_up_says_so(session: AsyncSession) -> None:
    """精靈第 6 步是唯一可以跳過的一步，所以「沒接」不是失敗，是還沒接（票 08 驗收）。"""
    await arrange_media(session)
    factory = FakeClientFactory(indexer_search=FakeIndexerSearch())

    view = await search_torrents(session, factory, SourceCache(), media_id=SPY)

    assert view.problem is IndexerProblem.NOT_CONFIGURED
    assert view.rows == ()


@pytest.mark.asyncio
async def test_an_unreachable_indexer_says_which_way_it_failed(session: AsyncSession) -> None:
    """憑證被拒與連不上的下一步不同，所以它們不是同一個 problem。"""
    await arrange_media(session)
    await arrange_indexer(session)
    factory = FakeClientFactory(
        indexer_search=FakeIndexerSearch(error=AuthFailedError("GET /api/v1/search: 401"))
    )

    view = await search_torrents(session, factory, SourceCache(), media_id=SPY)

    assert view.problem is IndexerProblem.CREDENTIAL_REJECTED
    assert view.detail == "GET /api/v1/search: 401"


@pytest.mark.asyncio
async def test_every_query_timing_out_is_said_on_the_cables_not_as_unreachable(
    session: AsyncSession,
) -> None:
    """M4 票 107：`sites()` 拿掉之後，「整台問不動」由每一個查詢都被索引站拒絕來判；逾時不算——
    索引站在、是它背後的站慢，畫面照舊是逐查詢的纜繩。"""
    await arrange_media(session)
    await arrange_indexer(session)

    class Slow(FakeIndexerSearch):
        async def search(self, query: SearchQuery) -> tuple[IndexerResult, ...]:
            await asyncio.sleep(1)
            return ()

    factory = FakeClientFactory(indexer_search=Slow())

    view = await search_torrents(session, factory, SourceCache(), media_id=SPY, timeout=0.01)

    assert view.problem is None
    assert view.attempts
    assert {attempt.status for attempt in view.attempts} == {StepStatus.FAILED}


@pytest.mark.asyncio
async def test_each_row_carries_the_parser_verdict(session: AsyncSession) -> None:
    """這是使用者第一次看見解析器的判斷：Tags 與預估季集（票 08）。"""
    await arrange_media(session)
    await arrange_indexer(session)
    indexer = FakeIndexerSearch(
        results=(
            result(
                "[桜都字幕组] 间谍过家家 第三季 / Spy x Family (2025) [05][1080p][简繁内封]",
                info_hash="e" * 40,
            ),
        )
    )
    factory = FakeClientFactory(indexer_search=indexer)

    view = await search_torrents(session, factory, SourceCache(), media_id=SPY)

    row = view.rows[0]
    assert row.tags.resolution == "1080p"
    assert row.tags.group == "桜都字幕组"
    assert (row.season, row.episode_start, row.episode_end) == (3, 5, 5)
    assert row.whole_season is False


@pytest.mark.asyncio
async def test_the_estimate_reads_the_publish_time_like_planning_does(
    session: AsyncSession,
) -> None:
    """M3 票 16：只有集號時，預估與送單之後的規劃一樣拿發佈時間推測是哪一輪播出。"""
    await arrange_media(session)
    await arrange_indexer(session)
    first, second = date(2022, 4, 9), date(2026, 7, 4)
    aired = [first + timedelta(weeks=n) for n in range(12)]
    aired += [second + timedelta(weeks=n) for n in range(12)]
    await restyle(
        session,
        seasons=[
            {
                "season_number": 1,
                "name": "Season 1",
                "episode_count": 24,
                "episodes": [
                    {"episode_number": n, "name": f"E{n}", "air_date": day.isoformat()}
                    for n, day in enumerate(aired, start=1)
                ],
            }
        ],
    )
    indexer = FakeIndexerSearch(
        results=(
            result(
                "[Group] Spy x Family - 05 [1080p]",
                info_hash="d" * 40,
                published_at=datetime(2026, 8, 3, 15, tzinfo=UTC),
            ),
        )
    )
    factory = FakeClientFactory(indexer_search=indexer)

    view = await search_torrents(session, factory, SourceCache(), media_id=SPY)

    row = view.rows[0]
    assert (row.season, row.episode_start, row.strategy) == (1, 17, MappingStrategy.PUBLISHED_RUN)


@pytest.mark.asyncio
async def test_a_season_pack_reads_as_the_whole_season(session: AsyncSession) -> None:
    """`S03 全季` 與 `E05` 是兩種不同的話，畫面要說得出是哪一種。"""
    await arrange_media(session)
    await arrange_indexer(session)
    indexer = FakeIndexerSearch(
        results=(
            result(
                "[桜都字幕组] 间谍过家家 第三季 / Spy x Family (2025) [01-13Fin][1080p][简繁内封]",
                info_hash="f" * 40,
            ),
        )
    )
    factory = FakeClientFactory(indexer_search=indexer)

    view = await search_torrents(session, factory, SourceCache(), media_id=SPY)

    row = view.rows[0]
    assert (row.season, row.episode_start, row.episode_end) == (3, 1, 13)
    assert row.whole_season is True


@pytest.mark.asyncio
async def test_a_release_the_parser_cannot_place_says_nothing_rather_than_guessing(
    session: AsyncSession,
) -> None:
    """判斷不出來就是判斷不出來——結果表的第三種說法（票 08）。

    名字對得上（所以它進得了結果表），但沒有一個數字說得出是第幾集：特典合輯就長這樣。
    """
    await arrange_media(session)
    await arrange_indexer(session)
    indexer = FakeIndexerSearch(
        results=(result("SPY x FAMILY 幕後花絮 2160p", info_hash="1" * 40),)
    )
    factory = FakeClientFactory(indexer_search=indexer)

    view = await search_torrents(session, factory, SourceCache(), media_id=SPY)

    row = view.rows[0]
    assert (row.season, row.episode_start) == (None, None)
    assert row.tags.resolution == "2160p"


@pytest.mark.asyncio
async def test_releases_that_are_not_this_work_are_sent_under_their_own_verdict(
    session: AsyncSession,
) -> None:
    """**索引站對搜不到的關鍵字會回它自己的熱門清單**（2026-09-10 實跑 The Pirate Bay）。

    那些東西動輒五六千個做種，依做種排序時會把真正的結果整批擠出前 100 筆。歸成「名字對不上」
    另成一類照樣送（M4 票 83）——「索引站什麼都沒回」與「回了一堆但沒有一筆是這部作品」
    的下一步不同，而使用者要看得到 Berth 略過了什麼，才判斷得了它是不是判斷錯了。
    """
    await arrange_media(session)
    await arrange_indexer(session)
    indexer = FakeIndexerSearch(
        results=(
            result("SPY x FAMILY S02E01 1080p WEB", info_hash="a" * 40, seeders=9),
            result("Spider-Man: Brand New Day 2026.1080p", info_hash="b" * 40, seeders=6055),
        )
    )
    factory = FakeClientFactory(indexer_search=indexer)

    view = await search_torrents(session, factory, SourceCache(), media_id=SPY)

    assert listed(view) == ["SPY x FAMILY S02E01 1080p WEB"]
    assert listed(view, SearchVerdict.UNRELATED) == ["Spider-Man: Brand New Day 2026.1080p"]
    assert (count(view), count(view, SearchVerdict.UNRELATED)) == (1, 1)


INFERNAL = build_media_id(MediaKind.MOVIE, 10775)
#: 2026-10-14 使用者在《無間道》自己打「無間道」：104 筆裡 96 筆是 The Pirate Bay 的熱門清單
#: （M4 票 83b）。
INFERNAL_RESULTS = (
    result("Avira Antivirus Pro 2026 Multi", info_hash="1" * 40, seeders=5210, indexer="TPB"),
    result("Spider-Man Brand New Day 2026 1080p", info_hash="2" * 40, seeders=4801, indexer="TPB"),
    result("Slow Horses S05E01 1080p WEB", info_hash="3" * 40, seeders=3120, indexer="TPB"),
    result("無間道 III [国语中字]", info_hash="4" * 40, seeders=2, indexer="dmhy"),
    result("[心叶荐] 无间道_Infernal Affairs", info_hash="5" * 40, seeders=1, indexer="dmhy"),
)


async def arrange_infernal(session: AsyncSession) -> None:
    session.add(
        Media(
            id=INFERNAL,
            tmdb_id=10775,
            kind=MediaKind.MOVIE,
            title_en="Infernal Affairs",
            title_original="無間道",
            year=2002,
            folder_name="Infernal Affairs (2002) [tmdbid-10775]",
            tmdb_snapshot_json={
                "tmdb_id": 10775,
                "kind": "movie",
                "title": "無間道",
                "title_en": "Infernal Affairs",
                "title_original": "無間道",
                "title_zh_cn": "无间道",
                "year": 2002,
                "titles": ["Infernal Affairs", "無間道", "无间道"],
            },
            tmdb_fetched_at=datetime.now(UTC),
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_a_three_character_chinese_name_fits_a_title_search(session: AsyncSession) -> None:
    """照作品名搜《無間道》：只寫中文名的 dmhy 發佈不再歸「名字對不上」（M4 票 83c）。"""
    await arrange_infernal(session)
    await arrange_indexer(session)
    factory = FakeClientFactory(indexer_search=FakeIndexerSearch(results=INFERNAL_RESULTS))

    view = await search_torrents(session, factory, SourceCache(), media_id=INFERNAL)

    assert listed(view) == ["無間道 III [国语中字]", "[心叶荐] 无间道_Infernal Affairs"]
    assert "無間道 III [国语中字]" not in listed(view, SearchVerdict.UNRELATED)


class TestTypedKeyword:
    """自己打關鍵字時分「對得上」與「對不上」（M4 票 83b）：只判發佈名對不對得上使用者問的東西，
    不判是不是這部作品（票 08）。熱門清單不再壓在那幾筆真正的結果上面。"""

    @pytest.mark.asyncio
    async def test_the_popular_list_does_not_match_the_typed_words(
        self, session: AsyncSession
    ) -> None:
        await arrange_infernal(session)
        await arrange_indexer(session)
        factory = FakeClientFactory(indexer_search=FakeIndexerSearch(results=INFERNAL_RESULTS))

        view = await search_torrents(
            session, factory, SourceCache(), media_id=INFERNAL, query="無間道"
        )

        # 第二筆只靠作品的簡體名與英文名對得上：專案沒有繁簡轉換。
        assert listed(view, SearchVerdict.TYPED_MATCH) == [
            "無間道 III [国语中字]",
            "[心叶荐] 无间道_Infernal Affairs",
        ]
        assert set(listed(view, SearchVerdict.TYPED_MISS)) == {
            "Avira Antivirus Pro 2026 Multi",
            "Spider-Man Brand New Day 2026 1080p",
            "Slow Horses S05E01 1080p WEB",
        }
        assert verdicts(view) == {SearchVerdict.TYPED_MATCH, SearchVerdict.TYPED_MISS}

    @pytest.mark.asyncio
    async def test_without_a_snapshot_only_the_typed_words_count(
        self, session: AsyncSession
    ) -> None:
        """Berth 還不知道這部作品叫什麼（TMDB 讀不到、沒存過）：只看打的字。"""
        await arrange_indexer(session)
        factory = FakeClientFactory(indexer_search=FakeIndexerSearch(results=INFERNAL_RESULTS))

        view = await search_torrents(
            session, factory, SourceCache(), media_id=INFERNAL, query="無間道"
        )

        assert listed(view, SearchVerdict.TYPED_MATCH) == ["無間道 III [国语中字]"]
        assert count(view, SearchVerdict.TYPED_MISS) == 4

    @pytest.mark.asyncio
    async def test_a_typed_keyword_judges_neither_year_nor_kind(
        self, session: AsyncSession
    ) -> None:
        """年份與類型照舊不判：重拍與真人秀的那一集只要含打的字就對得上。"""
        await arrange_night(session)
        await arrange_indexer(session)
        factory = FakeClientFactory(indexer_search=FakeIndexerSearch(results=night_results()))

        view = await search_torrents(
            session, factory, SourceCache(), media_id=NIGHT, query="Night of the Living"
        )

        assert (verdicts(view), count(view, SearchVerdict.TYPED_MATCH)) == (
            {SearchVerdict.TYPED_MATCH},
            20,
        )

    @pytest.mark.asyncio
    async def test_the_counts_add_up_and_each_kind_is_capped(self, session: AsyncSession) -> None:
        """對得上送 `RESULT_LIMIT` 筆、對不上送 `OTHERS_LIMIT` 筆；總數另外報，加得起來。"""
        await arrange_infernal(session)
        await arrange_indexer(session)
        rows = (
            *(
                result(f"無間道 {n:03d} 1080p", info_hash=f"{n:040x}", seeders=n)
                for n in range(RESULT_LIMIT + 7)
            ),
            *(
                result(f"Popular Thing {n:03d} 1080p", info_hash=f"{1000 + n:040x}", seeders=n)
                for n in range(OTHERS_LIMIT + 9)
            ),
        )
        factory = FakeClientFactory(indexer_search=FakeIndexerSearch(results=rows))

        view = await search_torrents(
            session, factory, SourceCache(), media_id=INFERNAL, query="無間道"
        )

        assert len(listed(view, SearchVerdict.TYPED_MATCH)) == RESULT_LIMIT
        assert len(listed(view, SearchVerdict.TYPED_MISS)) == OTHERS_LIMIT
        assert (count(view, SearchVerdict.TYPED_MATCH), count(view, SearchVerdict.TYPED_MISS)) == (
            RESULT_LIMIT + 7,
            OTHERS_LIMIT + 9,
        )
        assert view.returned == view.merged + sum(one.total for one in view.counts)


@pytest.mark.asyncio
async def test_a_show_past_its_first_season_opens_the_latest_season(
    session: AsyncSession,
) -> None:
    """發佈名常常只寫得出 `S03` / `Season 3`，光靠作品名搜不到那一季（plan §8.4）。

    **不分動漫**（票 14e，brief §19）：Route 上已經沒有東西說得出「這是動漫」，而美劇的
    `The Bear Season 3` 一樣是真的發佈名。預設只開英文名與原名（M4 票 84），所以中文名不問。
    """
    await arrange_media(session)
    await arrange_indexer(session)
    await restyle(
        session,
        title="熊家餐館",
        title_en="The Bear",
        title_original="The Bear",
        titles=["The Bear", "熊家餐館"],
        seasons=[season_of(0, 3), season_of(1, 8), season_of(2, 10), season_of(3, 10)],
    )
    indexer = FakeIndexerSearch()
    factory = FakeClientFactory(indexer_search=indexer)

    await search_torrents(session, factory, SourceCache(), media_id=SPY)

    assert [query.text for query in indexer.queries] == [
        "The Bear",
        "The Bear S03",
        "The Bear Season 3",
    ]


class TestRememberedNames:
    """名字的開關以種類為單位全域記住（M4 票 84，`.scratch/m4/search-choose-shape.md`）。"""

    @pytest.mark.asyncio
    async def test_a_kind_turned_on_for_one_work_is_on_for_the_next(
        self, session: AsyncSession
    ) -> None:
        """在一部作品開了中文名，另一部打開時中文名就開著；關掉也一樣。"""
        await arrange_media(session)
        await arrange_nosferatu(session)
        await arrange_indexer(session)
        factory = FakeClientFactory()

        before = await plan_queries(session, factory, media_id=NOSFERATU)
        await remember_names(session, {NameKind.CHINESE: True})
        turned_on = await plan_queries(session, factory, media_id=SPY)
        await remember_names(session, {NameKind.CHINESE: False})
        turned_off = await plan_queries(session, factory, media_id=NOSFERATU)

        assert "吸血鬼" not in before.choice.names
        assert "間諜家家酒" in turned_on.choice.names
        assert "吸血鬼" not in turned_off.choice.names

    @pytest.mark.asyncio
    async def test_the_search_uses_the_remembered_kinds_too(self, session: AsyncSession) -> None:
        """沒帶 `choice` 的搜尋與預覽同一個預設：按下去問的就是畫面上開著的。"""
        await arrange_media(session)
        await arrange_indexer(session)
        await remember_names(session, {NameKind.SIMPLIFIED: True, NameKind.ORIGINAL: False})
        await restyle(session, title_zh_cn="间谍过家家", seasons=[season_of(1, 12)])
        indexer = FakeIndexerSearch()
        factory = FakeClientFactory(indexer_search=indexer)

        preview = await plan_queries(session, factory, media_id=SPY)
        await search_torrents(session, factory, SourceCache(), media_id=SPY)

        assert preview.queries == ("SPY x FAMILY", "间谍过家家")
        assert [query.text for query in indexer.queries] == list(preview.queries)

    @pytest.mark.asyncio
    async def test_only_the_kinds_sent_change(self, session: AsyncSession) -> None:
        stored = await remember_names(session, {NameKind.CHINESE: True})

        assert stored == {
            NameKind.ENGLISH: True,
            NameKind.ORIGINAL: True,
            NameKind.CHINESE: True,
            NameKind.SIMPLIFIED: False,
        }

    @pytest.mark.asyncio
    async def test_aliases_are_not_remembered(self, session: AsyncSession) -> None:
        """別名沒有語言：記住「別名」等於下一部作品三十幾個全開。拒絕，不默默丟掉。"""
        with pytest.raises(ValueError, match="aliases"):
            await remember_names(session, {NameKind.ALIAS: True})


class TestChosenNamesAndSeasons:
    """使用者在 chip 上開了的名字與季（M4 票 84）：預覽與搜尋同一份，超過上限整次不問。"""

    @pytest.mark.asyncio
    async def test_the_preview_and_the_search_ask_the_chosen_ones(
        self, session: AsyncSession
    ) -> None:
        await arrange_media(session)
        await arrange_indexer(session)
        indexer = FakeIndexerSearch()
        factory = FakeClientFactory(indexer_search=indexer)
        choice = QueryChoice(names=("間諜家家酒", "SPY x FAMILY"), seasons=(1,), any_season=False)

        preview = await plan_queries(
            session, factory, media_id=SPY, scope=QueryScope(choice=choice)
        )
        await search_torrents(
            session, factory, SourceCache(), media_id=SPY, scope=QueryScope(choice=choice)
        )

        assert preview.queries == ("SPY x FAMILY S01", "SPY x FAMILY Season 1", "間諜家家酒 第1季")
        assert [query.text for query in indexer.queries] == list(preview.queries)
        assert preview.choice == choice

    @pytest.mark.asyncio
    async def test_the_preview_lists_every_name_and_season_to_choose_from(
        self, session: AsyncSession
    ) -> None:
        await arrange_media(session)

        plan = await plan_queries(session, FakeClientFactory(), media_id=SPY)

        assert [(name.text, name.kinds) for name in plan.names] == [
            ("SPY x FAMILY", (NameKind.ENGLISH,)),
            ("SPY×FAMILY", (NameKind.ORIGINAL,)),
            ("間諜家家酒", (NameKind.CHINESE,)),
            ("间谍过家家", (NameKind.ALIAS,)),
        ]
        assert plan.seasons == (1, 3)
        assert plan.limit == MAX_QUERIES

    @pytest.mark.asyncio
    async def test_more_queries_than_the_limit_asks_nothing(self, session: AsyncSession) -> None:
        """超過上限不砍尾巴：名字與季是使用者自己開的，默默少問幾個等於替他做了決定。"""
        await arrange_media(session)
        await arrange_indexer(session)
        indexer = FakeIndexerSearch()
        factory = FakeClientFactory(indexer_search=indexer)
        every = QueryChoice(
            names=("SPY x FAMILY", "SPY×FAMILY", "間諜家家酒", "间谍过家家"), seasons=(1, 3)
        )

        preview = await plan_queries(session, factory, media_id=SPY, scope=QueryScope(choice=every))
        view = await search_torrents(
            session, factory, SourceCache(), media_id=SPY, scope=QueryScope(choice=every)
        )

        assert len(preview.queries) > MAX_QUERIES
        assert view.problem is IndexerProblem.TOO_MANY_QUERIES
        assert indexer.queries == []

    @pytest.mark.asyncio
    async def test_the_missing_search_asks_every_chosen_name(self, session: AsyncSession) -> None:
        """搜缺的集也用開了的名字：中文名開著時，缺的那一集中文名也問到。"""
        tv = await route(session)
        spy = await title(session, name_zh="間諜家家酒", seasons=(season_snapshot(1, aired=2),))
        await linked(session, spy, tv, episode=1)
        await arrange_indexer(session)
        indexer = FakeIndexerSearch()
        factory = FakeClientFactory(indexer_search=indexer)
        choice = QueryChoice(names=("SPY x FAMILY", "間諜家家酒"))

        await search_torrents(
            session,
            factory,
            SourceCache(),
            media_id=spy.id,
            scope=QueryScope(choice=choice, missing=True),
        )

        assert [query.text for query in indexer.queries] == [
            "SPY x FAMILY S01E02",
            "間諜家家酒 S01E02",
        ]


@pytest.mark.asyncio
async def test_a_single_season_show_does_not_add_them(session: AsyncSession) -> None:
    """只有一季時沒有「哪一季」要分：第一季的發佈幾乎不寫季號，多問一次只是替每個站多添一趟。

    Specials（第 0 季）不算一季。
    """
    await arrange_media(session)
    await arrange_indexer(session)
    await restyle(session, seasons=[season_of(0, 2), season_of(1, 12)])
    indexer = FakeIndexerSearch()
    factory = FakeClientFactory(indexer_search=indexer)

    await search_torrents(session, factory, SourceCache(), media_id=SPY)

    assert season_queries(indexer) == []


@pytest.mark.asyncio
async def test_a_movie_does_not_add_them(session: AsyncSession) -> None:
    """電影的快照沒有季，所以它與單季劇集落在同一條規則上；這一條釘的是真的一部電影
    （`movie:` 的 id、`kind=movie`）照樣問得出去，而且不帶季號變體。"""
    await arrange_indexer(session)
    session.add(
        Media(
            id=OPPENHEIMER,
            tmdb_id=872585,
            kind=MediaKind.MOVIE,
            title_en="Oppenheimer",
            title_original="Oppenheimer",
            year=2023,
            folder_name="Oppenheimer (2023) [tmdbid-872585]",
            tmdb_snapshot_json={
                "tmdb_id": 872585,
                "kind": "movie",
                "title": "奧本海默",
                "title_en": "Oppenheimer",
                "title_original": "Oppenheimer",
                "year": 2023,
                "titles": ["Oppenheimer", "奧本海默"],
            },
            tmdb_fetched_at=datetime.now(UTC),
        )
    )
    await session.commit()
    indexer = FakeIndexerSearch()
    factory = FakeClientFactory(indexer_search=indexer)

    await search_torrents(session, factory, SourceCache(), media_id=OPPENHEIMER)

    assert [query.text for query in indexer.queries] == ["Oppenheimer"]
    assert season_queries(indexer) == []


@pytest.mark.asyncio
async def test_a_typed_query_replaces_the_titles(session: AsyncSession) -> None:
    """使用者自己打字時就只問那一個——他比 TMDB 更知道自己在找什麼。"""
    await arrange_media(session)
    await arrange_indexer(session)
    indexer = FakeIndexerSearch()
    factory = FakeClientFactory(indexer_search=indexer)

    await search_torrents(session, factory, SourceCache(), media_id=SPY, query="Spy Family BDRip")

    assert [query.text for query in indexer.queries] == ["Spy Family BDRip"]


@pytest.mark.asyncio
async def test_tags_render_the_way_the_file_name_will(session: AsyncSession) -> None:
    """結果表的 Tags 欄與之後檔名裡的那一串是同一份資料（brief §6.8）。"""
    await arrange_media(session)
    await arrange_indexer(session)
    indexer = FakeIndexerSearch(
        results=(
            result(
                "[ANi] SPY x FAMILY - 50 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]",
                info_hash="2" * 40,
            ),
        )
    )
    factory = FakeClientFactory(indexer_search=indexer)

    view = await search_torrents(session, factory, SourceCache(), media_id=SPY)

    assert view.rows[0].tags.source is Source.WEB
    assert view.rows[0].tags.render().startswith("[WEB][1080p]")


class TestMissingEpisodes:
    """缺集一鍵搜（M1.5 票 10）：季表已經知道缺哪幾集，搜尋就不必從作品名開始。

    記號怎麼組由 `tests/unit/test_search_missing.py` 守著（純函式）；這裡守的是**搜尋真的走
    同一份規則**，而且缺哪幾集是現在的帳本與 Job 說的，不是快照說的。
    """

    @pytest.mark.asyncio
    async def test_the_search_asks_for_the_episodes_the_library_is_missing(
        self, session: AsyncSession
    ) -> None:
        tv = await route(session)
        spy = await title(session, seasons=(season_snapshot(1, aired=3),))
        await linked(session, spy, tv, episode=1)
        await linked(session, spy, tv, episode=2)
        await arrange_indexer(session)
        indexer = FakeIndexerSearch()
        factory = FakeClientFactory(indexer_search=indexer)

        await search_torrents(
            session, factory, SourceCache(), media_id=spy.id, scope=QueryScope(missing=True)
        )

        assert [query.text for query in indexer.queries] == ["SPY x FAMILY S01E03"]

    @pytest.mark.asyncio
    async def test_one_season_only_asks_for_that_seasons_gaps(self, session: AsyncSession) -> None:
        tv = await route(session)
        spy = await title(
            session, seasons=(season_snapshot(1, aired=2), season_snapshot(2, aired=2))
        )
        await linked(session, spy, tv, episode=1)
        await arrange_indexer(session)
        indexer = FakeIndexerSearch()
        factory = FakeClientFactory(indexer_search=indexer)

        await search_torrents(
            session,
            factory,
            SourceCache(),
            media_id=spy.id,
            scope=QueryScope(missing=True, season=2),
        )

        assert [query.text for query in indexer.queries] == [
            "SPY x FAMILY S02",
            "SPY x FAMILY Season 2",
        ]

    @pytest.mark.asyncio
    async def test_the_preview_and_the_search_ask_the_same_thing(
        self, session: AsyncSession
    ) -> None:
        """`/search/queries` 的預覽就是待會兒真的送出去的那幾個——規則只有一份實作（票 10）。"""
        tv = await route(session)
        spy = await title(session, seasons=(season_snapshot(1, aired=3),))
        await linked(session, spy, tv, episode=1)
        await arrange_indexer(session)
        indexer = FakeIndexerSearch()
        factory = FakeClientFactory(indexer_search=indexer)

        preview = (
            await plan_queries(session, factory, media_id=spy.id, scope=QueryScope(missing=True))
        ).queries
        await search_torrents(
            session, factory, SourceCache(), media_id=spy.id, scope=QueryScope(missing=True)
        )

        assert list(preview) == [query.text for query in indexer.queries]
        assert preview == ("SPY x FAMILY S01E02", "SPY x FAMILY S01E03")

    @pytest.mark.asyncio
    async def test_nothing_missing_asks_nothing(self, session: AsyncSession) -> None:
        """缺的集是零就不問——**不退回作品名**，那會在使用者按「搜缺的集」時搜出整部作品。"""
        tv = await route(session)
        spy = await title(session, seasons=(season_snapshot(1, aired=1),))
        await linked(session, spy, tv, episode=1)
        await arrange_indexer(session)
        indexer = FakeIndexerSearch()
        factory = FakeClientFactory(indexer_search=indexer)

        view = await search_torrents(
            session, factory, SourceCache(), media_id=spy.id, scope=QueryScope(missing=True)
        )

        assert indexer.queries == []
        assert view.problem is IndexerProblem.NO_QUERY

    @pytest.mark.asyncio
    async def test_a_typed_keyword_still_wins(self, session: AsyncSession) -> None:
        """自己打了字就只問那一個：他比季表更知道自己在找什麼（票 08 的規矩不變）。"""
        tv = await route(session)
        spy = await title(session, seasons=(season_snapshot(1, aired=2),))
        await linked(session, spy, tv, episode=1)
        await arrange_indexer(session)
        indexer = FakeIndexerSearch()
        factory = FakeClientFactory(indexer_search=indexer)

        await search_torrents(
            session,
            factory,
            SourceCache(),
            media_id=spy.id,
            query="Spy Family BDRip",
            scope=QueryScope(missing=True),
        )

        assert [query.text for query in indexer.queries] == ["Spy Family BDRip"]

    @pytest.mark.asyncio
    async def test_gaps_in_twelve_seasons_are_asked_batch_by_batch(
        self, session: AsyncSession
    ) -> None:
        """M3 票 20 驗收第二條：十二季都有缺，季記號放不下一批——**分批問完每一季**，一次也不退回
        作品名。每一批說得出問了哪幾季、下一批是哪幾季。每一個查詢都問全部的站（M4 票 107 刪掉
        請求預算之後不再只帶部分 `indexerIds`）。"""
        long = await many_seasons(session)
        indexer = FakeIndexerSearch()
        factory = FakeClientFactory(indexer_search=indexer)

        first = await search_torrents(
            session, factory, SourceCache(), media_id=long.id, scope=QueryScope(missing=True)
        )
        assert first.batch is not None
        second = await search_torrents(
            session,
            factory,
            SourceCache(),
            media_id=long.id,
            scope=QueryScope(missing=True, from_season=first.batch.next_seasons[0]),
        )

        asked = [query.text for query in indexer.queries]
        assert asked[:10] == [
            f"SPY x FAMILY {token}"
            for number in range(1, 6)
            for token in (f"S{number:02d}", f"Season {number}")
        ]
        # 第二批只剩七季、七集缺：放得下逐集，就問那幾集（收成季記號只在放不下時才做）。
        assert asked[10:] == [f"SPY x FAMILY S{number:02d}E02" for number in range(6, 13)]
        assert "SPY x FAMILY" not in asked
        assert {query.indexer_ids for query in indexer.queries} == {()}
        assert (first.batch.seasons, first.batch.later) == ((1, 2, 3, 4, 5), 2)
        assert first.batch.next_seasons == (6, 7, 8, 9, 10)
        assert second.batch is not None
        assert (second.batch.seasons, second.batch.later, second.batch.next_seasons) == (
            tuple(range(6, 13)),
            0,
            (),
        )

    @pytest.mark.asyncio
    async def test_the_next_batch_still_asks_its_seasons_after_some_were_sent(
        self, session: AsyncSession
    ) -> None:
        """問完第一批、從結果送了幾季之後季表就變了：下一批照季定位，S06、S07 照樣問得到
        （以序號定位時 S02 補上之後第二批只剩 S07，code review 抓到）。"""
        long = await many_seasons(session)
        indexer = FakeIndexerSearch()
        factory = FakeClientFactory(indexer_search=indexer)
        first = await search_torrents(
            session, factory, SourceCache(), media_id=long.id, scope=QueryScope(missing=True)
        )
        assert first.batch is not None
        tv = await session.scalar(select(Route).where(Route.slug == "tv"))
        assert tv is not None
        await linked(session, long, tv, season_number=2, episode=2)
        indexer.queries.clear()

        await search_torrents(
            session,
            factory,
            SourceCache(),
            media_id=long.id,
            scope=QueryScope(missing=True, from_season=first.batch.next_seasons[0]),
        )

        assert [query.text for query in indexer.queries][:2] == [
            "SPY x FAMILY S06E02",
            "SPY x FAMILY S07E02",
        ]

    @pytest.mark.asyncio
    async def test_the_preview_names_the_batch_it_will_ask(self, session: AsyncSession) -> None:
        """預覽與搜尋同一份：第二批的預覽就是第二批真的問出去的那幾個。"""
        long = await many_seasons(session)
        indexer = FakeIndexerSearch()
        factory = FakeClientFactory(indexer_search=indexer)

        preview = await plan_queries(
            session, factory, media_id=long.id, scope=QueryScope(missing=True, from_season=6)
        )
        await search_torrents(
            session,
            factory,
            SourceCache(),
            media_id=long.id,
            scope=QueryScope(missing=True, from_season=6),
        )

        assert list(preview.queries) == [query.text for query in indexer.queries]
        assert preview.batch is not None
        assert (preview.batch.seasons, preview.batch.later) == (tuple(range(6, 13)), 0)


async def many_seasons(session: AsyncSession) -> Media:
    """十二季、每季播了兩集、每季只入庫第一集：十二季都缺一集，逐集放不下一批、季記號也放不下。"""
    tv = await route(session)
    long = await title(
        session, seasons=tuple(season_snapshot(number, aired=2) for number in range(1, 13))
    )
    for number in range(1, 13):
        await linked(session, long, tv, season_number=number, episode=1)
    await arrange_indexer(session)
    return long


NIGHT = build_media_id(MediaKind.MOVIE, 10331)
#: 審計 S6 搜《活死人之夜》（1968）的結果，從截圖 s6-02 抄下來的發佈名與做種（M4 票 49）。
NIGHT_RESULTS = (
    Path(__file__).parents[1] / "fixtures" / "search" / "night-of-the-living-dead-1968.json"
)


async def arrange_night(session: AsyncSession) -> None:
    session.add(
        Media(
            id=NIGHT,
            tmdb_id=10331,
            kind=MediaKind.MOVIE,
            title_en="Night of the Living Dead",
            title_original="Night of the Living Dead",
            year=1968,
            folder_name="Night of the Living Dead (1968) [tmdbid-10331]",
            tmdb_snapshot_json={
                "tmdb_id": 10331,
                "kind": "movie",
                "title": "活死人之夜",
                "title_en": "Night of the Living Dead",
                "title_original": "Night of the Living Dead",
                "year": 1968,
                "titles": [
                    "Night of the Living Dead",
                    "活死人之夜",
                    "Die Nacht der lebenden Toten",
                ],
            },
            tmdb_fetched_at=datetime.now(UTC),
        )
    )
    await session.commit()


def night_results() -> tuple[IndexerResult, ...]:
    return tuple(result(**row) for row in json.loads(NIGHT_RESULTS.read_text(encoding="utf-8")))


@pytest.mark.asyncio
async def test_a_movie_search_sets_aside_remakes_and_episodes(session: AsyncSession) -> None:
    """審計 S6：主清單混進 1990、2006 的重拍與一集真人秀。名字對上了，年份與類型對不上——
    收到另一份，數量照實說，展開看得到（M4 票 49）。"""
    await arrange_night(session)
    await arrange_indexer(session)
    factory = FakeClientFactory(indexer_search=FakeIndexerSearch(results=night_results()))

    view = await search_torrents(session, factory, SourceCache(), media_id=NIGHT)

    shown = listed(view)
    assert shown and all("1968" in title for title in shown)
    assert not any(year in title for title in shown for year in ("1990", "2006", "2022"))
    assert not any("S04E02" in title for title in shown)
    year = listed(view, SearchVerdict.YEAR)
    assert "Night of the Living Dead (1990) 1080p BRRip x264 -YTS" in year
    episode = listed(view, SearchVerdict.NOT_MOVIE)
    assert "Below Deck Down Under S04E02 Night of the Living Dead XviD-AFG" in episode
    # 片名那一段多了一個詞就是「只對上部分名字」（照 Radarr：它解析出的片名也帶著那一段）。
    assert listed(view, SearchVerdict.PARTIAL_TITLE) == [
        "Night.Of.The.Living.Dead.Remastered.Collection.1968.2009"
    ]
    assert (count(view), len(view.rows) - len(shown)) == (7, 13)
    assert count(view, SearchVerdict.UNRELATED) == 0


@pytest.mark.asyncio
async def test_a_movie_keeps_its_year_and_releases_without_one(session: AsyncSession) -> None:
    await arrange_night(session)
    await arrange_indexer(session)
    indexer = FakeIndexerSearch(
        results=(
            result("Night of the Living Dead 1968 720p", info_hash="a" * 40, seeders=3),
            result("Night of the Living Dead 1080p BluRay", info_hash="b" * 40, seeders=2),
            result("Night of the Living Dead 1990 1080p", info_hash="c" * 40, seeders=1),
        )
    )
    factory = FakeClientFactory(indexer_search=indexer)

    view = await search_torrents(session, factory, SourceCache(), media_id=NIGHT)

    assert listed(view) == [
        "Night of the Living Dead 1968 720p",
        "Night of the Living Dead 1080p BluRay",
    ]
    assert listed(view, SearchVerdict.YEAR) == ["Night of the Living Dead 1990 1080p"]


@pytest.mark.asyncio
async def test_a_show_search_keeps_its_episodes(session: AsyncSession) -> None:
    """反過來那一邊：劇集照常收季集與沒寫年份的，只擋首播之前的年份（M4 票 49）。"""
    await arrange_media(session)
    await arrange_indexer(session)
    indexer = FakeIndexerSearch(
        results=(
            result("SPY x FAMILY S02E01 1080p WEB", info_hash="a" * 40, seeders=9),
            result("SPY x FAMILY (2022) S01 1080p", info_hash="b" * 40, seeders=8),
            result("[字幕組] SPY x FAMILY - 05 [1080p]", info_hash="c" * 40, seeders=7),
            result("SPY x FAMILY 1998 VHS", info_hash="d" * 40, seeders=6),
        )
    )
    factory = FakeClientFactory(indexer_search=indexer)

    view = await search_torrents(session, factory, SourceCache(), media_id=SPY)

    assert listed(view) == [
        "SPY x FAMILY S02E01 1080p WEB",
        "SPY x FAMILY (2022) S01 1080p",
        "[字幕組] SPY x FAMILY - 05 [1080p]",
    ]
    assert listed(view, SearchVerdict.YEAR) == ["SPY x FAMILY 1998 VHS"]


NOSFERATU = build_media_id(MediaKind.MOVIE, 653)
#: 審計 S3 搜《Nosferatu》(1922)：主表混進同名動畫《Tsuki to Laika to Nosferatu》的各集與成人內容
#: （M4 票 69）。發佈名照各站的寫法造，分類照 Prowlarr 回的 `categories`（標準碼加站自己的碼）。
NOSFERATU_RESULTS = Path(__file__).parents[1] / "fixtures" / "search" / "nosferatu-1922.json"


async def arrange_nosferatu(session: AsyncSession) -> None:
    session.add(
        Media(
            id=NOSFERATU,
            tmdb_id=653,
            kind=MediaKind.MOVIE,
            title_en="Nosferatu",
            title_original="Nosferatu, eine Symphonie des Grauens",
            year=1922,
            folder_name="Nosferatu (1922) [tmdbid-653]",
            tmdb_snapshot_json={
                "tmdb_id": 653,
                "kind": "movie",
                "title": "吸血鬼",
                "title_en": "Nosferatu",
                "title_original": "Nosferatu, eine Symphonie des Grauens",
                "year": 1922,
                "titles": ["Nosferatu", "Nosferatu, eine Symphonie des Grauens", "吸血鬼"],
            },
            tmdb_fetched_at=datetime.now(UTC),
        )
    )
    await session.commit()


def nosferatu_results() -> tuple[IndexerResult, ...]:
    rows = json.loads(NOSFERATU_RESULTS.read_text(encoding="utf-8"))
    return tuple(result(**{**row, "categories": tuple(row["categories"])}) for row in rows)


class TestNosferatu:
    """審計 S3（M4 票 69）：同名動畫的各集、成人內容，與畫面上加不起來的幾個筆數。"""

    @pytest.mark.asyncio
    async def test_a_namesake_shows_episodes_are_set_aside(self, session: AsyncSession) -> None:
        await arrange_nosferatu(session)
        await arrange_indexer(session)
        factory = FakeClientFactory(indexer_search=FakeIndexerSearch(results=nosferatu_results()))

        view = await search_torrents(session, factory, SourceCache(), media_id=NOSFERATU)

        assert listed(view) == [
            "Nosferatu (1922) [720p] [BluRay] [YTS.MX]",
            "Nosferatu.1922.1080p.BluRay.x264-OFT",
            "Nosferatu - Eine Symphonie des Grauens (1922) 1080p BluRay",
            "Nosferatu 1922 RESTORED 720p BluRay x264",
        ]
        namesake = listed(view, SearchVerdict.NOT_MOVIE)
        assert "[SubsPlease] Tsuki to Laika to Nosferatu - 05 (1080p) [8A1C3B2F].mkv" in namesake
        assert "[Group] Tsuki to Laika to Nosferatu [01-12][BDRip 1080p]" in namesake

    @pytest.mark.asyncio
    async def test_releases_the_indexer_files_as_adult_are_set_aside(
        self, session: AsyncSession
    ) -> None:
        """Prowlarr 的 `categories` 帶 Newznab 標準碼，6000–6999 是 XXX（brief §20.19）。"""
        await arrange_nosferatu(session)
        await arrange_indexer(session)
        factory = FakeClientFactory(indexer_search=FakeIndexerSearch(results=nosferatu_results()))

        view = await search_torrents(session, factory, SourceCache(), media_id=NOSFERATU)

        assert not any("XXX" in title for title in listed(view))
        assert {"Nosferatu Parody XXX 720p MP4-WRB", "Nosferatu Nights XXX 1080p WEB"} <= set(
            listed(view, SearchVerdict.ADULT)
        )

    @pytest.mark.asyncio
    async def test_the_counts_add_up_to_what_the_indexer_returned(
        self, session: AsyncSession
    ) -> None:
        """回了幾筆 = 重複合併的 + 每一類的筆數（M4 票 83）。預設的兩個名字各問一次，
        替身每一次都回同樣 18 筆，所以 18 筆是重複的。"""
        await arrange_nosferatu(session)
        await arrange_indexer(session)
        indexer = FakeIndexerSearch(results=nosferatu_results())
        factory = FakeClientFactory(indexer_search=indexer)

        view = await search_torrents(session, factory, SourceCache(), media_id=NOSFERATU)

        assert len(indexer.queries) == 2
        assert (view.returned, view.merged, count(view, SearchVerdict.UNRELATED)) == (36, 18, 2)
        assert count(view) == 4
        assert view.returned == view.merged + sum(one.total for one in view.counts)

    @pytest.mark.asyncio
    async def test_a_typed_keyword_counts_the_same_way(self, session: AsyncSession) -> None:
        await arrange_nosferatu(session)
        await arrange_indexer(session)
        factory = FakeClientFactory(indexer_search=FakeIndexerSearch(results=nosferatu_results()))

        view = await search_torrents(
            session, factory, SourceCache(), media_id=NOSFERATU, query="Nosferatu"
        )

        assert (view.returned, view.merged) == (18, 0)
        assert view.returned == sum(one.total for one in view.counts)


LAW = build_media_id(MediaKind.TV, 549)


async def arrange_law(session: AsyncSession) -> None:
    session.add(
        Media(
            id=LAW,
            tmdb_id=549,
            kind=MediaKind.TV,
            title_en="Law & Order",
            title_original="Law & Order",
            year=1990,
            folder_name="Law & Order (1990) [tmdbid-549]",
            tmdb_snapshot_json={
                "tmdb_id": 549,
                "kind": "tv",
                "title": "法網遊龍",
                "title_en": "Law & Order",
                "title_original": "Law & Order",
                "year": 1990,
                "titles": ["Law & Order", "法網遊龍", "Law & Order: Original"],
                "seasons": [
                    {"season_number": 1, "name": "Season 1", "episode_count": 22},
                    {"season_number": 24, "name": "Season 24", "episode_count": 13},
                ],
            },
            tmdb_fetched_at=datetime.now(UTC),
        )
    )
    await session.commit()


class TestAmpersand:
    """《Law & Order》：The Pirate Bay 對 `Law & Order` 回 0 筆、對 `Law and Order` 回 100 筆，
    Mikan 反過來（`TIGER & BUNNY` 81 筆、`TIGER and BUNNY` 0 筆；2026-10-10 實測，M4 票 69）。
    所以兩種都問：原樣的那一個問完它的每一季，再換寫開的那一個。"""

    @pytest.mark.asyncio
    async def test_the_spelled_out_title_follows_the_original(self, session: AsyncSession) -> None:
        await arrange_law(session)
        await arrange_indexer(session)
        indexer = FakeIndexerSearch()
        factory = FakeClientFactory(indexer_search=indexer)

        await search_torrents(session, factory, SourceCache(), media_id=LAW)

        assert [query.text for query in indexer.queries] == [
            "Law & Order",
            "Law & Order S24",
            "Law & Order Season 24",
            "Law and Order",
            "Law and Order S24",
            "Law and Order Season 24",
        ]

    @pytest.mark.asyncio
    async def test_the_preview_says_the_same(self, session: AsyncSession) -> None:
        await arrange_law(session)
        await arrange_indexer(session)

        planned = await plan_queries(session, FakeClientFactory(), media_id=LAW)

        assert "Law and Order" in planned.queries

    @pytest.mark.asyncio
    async def test_releases_spelled_either_way_reach_the_table(self, session: AsyncSession) -> None:
        await arrange_law(session)
        await arrange_indexer(session)
        indexer = FakeIndexerSearch(
            results=(
                result("Law.and.Order.S24E01.1080p.WEB.h264", info_hash="a" * 40, seeders=9),
                result("Law & Order S24E02 1080p WEB", info_hash="b" * 40, seeders=8),
                result("Order of the Phoenix 2007 1080p", info_hash="c" * 40, seeders=7),
            )
        )
        factory = FakeClientFactory(indexer_search=indexer)

        view = await search_torrents(session, factory, SourceCache(), media_id=LAW)

        assert listed(view) == [
            "Law.and.Order.S24E01.1080p.WEB.h264",
            "Law & Order S24E02 1080p WEB",
        ]
        assert count(view, SearchVerdict.UNRELATED) == 1

    @pytest.mark.asyncio
    async def test_a_title_without_an_ampersand_is_asked_as_it_is(
        self, session: AsyncSession
    ) -> None:
        await arrange_media(session)
        await arrange_indexer(session)
        indexer = FakeIndexerSearch()
        factory = FakeClientFactory(indexer_search=indexer)

        await search_torrents(session, factory, SourceCache(), media_id=SPY)

        assert [query.text for query in indexer.queries][:3] == [
            "SPY x FAMILY",
            "SPY x FAMILY S03",
            "SPY x FAMILY Season 3",
        ]
        assert not [query for query in indexer.queries if " and " in query.text]


class TestVerdicts:
    """每一筆歸到一類、說得出證據，每一類都送（M4 票 83，`.scratch/m4/search-filter-shape.md`）。"""

    @pytest.mark.asyncio
    async def test_a_movie_search_sorts_every_release_into_its_verdict(
        self, session: AsyncSession
    ) -> None:
        await arrange_nosferatu(session)
        await arrange_indexer(session)
        indexer = FakeIndexerSearch(
            results=(
                result("Nosferatu.1922.1080p.BluRay.x264-OFT", info_hash="1" * 40),
                result("Nosferatu.2024.2160p.WEB-DL.DDP5.1", info_hash="2" * 40),
                result("Nosferatu S01E03 1080p WEB", info_hash="3" * 40),
                result("[SubsPlease] Tsuki to Laika to Nosferatu - 05 (1080p)", info_hash="4" * 40),
                result("Nosferatu Nights XXX 1080p WEB", info_hash="5" * 40, categories=(6040,)),
                result("Spider-Man: Brand New Day 2026.1080p", info_hash="6" * 40),
            )
        )
        factory = FakeClientFactory(indexer_search=indexer)

        view = await search_torrents(session, factory, SourceCache(), media_id=NOSFERATU)

        assert [(row.verdict, row.evidence) for row in view.rows] == [
            (SearchVerdict.FITS, ""),
            (SearchVerdict.YEAR, "2024"),
            (SearchVerdict.NOT_MOVIE, "S01E03"),
            (SearchVerdict.NOT_MOVIE, "- 05"),
            (SearchVerdict.ADULT, "6040"),
            (SearchVerdict.UNRELATED, ""),
        ]

    @pytest.mark.asyncio
    async def test_a_spinoff_is_only_part_of_the_name(self, session: AsyncSession) -> None:
        """票 69 留下的：《Law & Order》混進衍生劇《Law & Order: SVU》。照 Sonarr 比片名那一段
        （brief §20.20），不再硬放進主表，也不硬擋——歸成一類，按了看得到、照樣送得了單。"""
        await arrange_law(session)
        await arrange_indexer(session)
        indexer = FakeIndexerSearch(
            results=(
                result("Law.and.Order.S24E01.1080p.WEB.h264", info_hash="a" * 40, seeders=9),
                result("Law.and.Order.SVU.S28E01.1080p.WEB.h264", info_hash="b" * 40, seeders=8),
            )
        )
        factory = FakeClientFactory(indexer_search=indexer)

        view = await search_torrents(session, factory, SourceCache(), media_id=LAW)

        assert listed(view) == ["Law.and.Order.S24E01.1080p.WEB.h264"]
        spinoff = next(row for row in view.rows if row.verdict is SearchVerdict.PARTIAL_TITLE)
        assert (spinoff.title, spinoff.evidence) == (
            "Law.and.Order.SVU.S28E01.1080p.WEB.h264",
            "Law and Order SVU",
        )
        assert spinoff.source_id

    @pytest.mark.asyncio
    async def test_each_verdict_is_capped_on_its_own(self, session: AsyncSession) -> None:
        """回應的大小有上限：「符合」`RESULT_LIMIT` 筆、其餘每類 `OTHERS_LIMIT` 筆，各自逐站輪流取；
        總數照實報，筆數照樣加得起來。"""
        await arrange_nosferatu(session)
        await arrange_indexer(session)
        many = RESULT_LIMIT + 20
        indexer = FakeIndexerSearch(
            results=(
                *(
                    result(f"Nosferatu 1922 Cut {n}", indexer="YTS", info_hash=f"a{n:039x}")
                    for n in range(many)
                ),
                *(
                    result(
                        f"Nosferatu 2024 Cut {n}",
                        indexer="YTS" if n % 2 else "The Pirate Bay",
                        info_hash=f"b{n:039x}",
                    )
                    for n in range(many)
                ),
                *(
                    result(f"Top {n} 2026 1080p", indexer="The Pirate Bay", info_hash=f"c{n:039x}")
                    for n in range(many)
                ),
            )
        )
        factory = FakeClientFactory(indexer_search=indexer)

        view = await search_torrents(session, factory, SourceCache(), media_id=NOSFERATU)

        assert (len(listed(view)), count(view)) == (RESULT_LIMIT, many)
        assert (len(listed(view, SearchVerdict.YEAR)), count(view, SearchVerdict.YEAR)) == (
            OTHERS_LIMIT,
            many,
        )
        year = [row.indexer for row in view.rows if row.verdict is SearchVerdict.YEAR]
        assert year.count("YTS") == year.count("The Pirate Bay")
        assert len(listed(view, SearchVerdict.UNRELATED)) == OTHERS_LIMIT
        assert len(view.rows) == RESULT_LIMIT + 2 * OTHERS_LIMIT
        assert view.returned == view.merged + sum(one.total for one in view.counts)

    @pytest.mark.asyncio
    async def test_counts_are_per_site_so_the_buttons_follow_the_site_filter(
        self, session: AsyncSession
    ) -> None:
        await arrange_nosferatu(session)
        await arrange_indexer(session)
        indexer = FakeIndexerSearch(
            results=(
                result("Nosferatu 1922 720p", indexer="YTS", info_hash="a" * 40),
                result("Nosferatu.1922.1080p", indexer="The Pirate Bay", info_hash="b" * 40),
                result("Nosferatu 1922 2160p", indexer="The Pirate Bay", info_hash="c" * 40),
                result("Nosferatu 2024 1080p", indexer="YTS", info_hash="d" * 40),
            )
        )
        factory = FakeClientFactory(indexer_search=indexer)

        view = await search_torrents(session, factory, SourceCache(), media_id=NOSFERATU)

        assert [(one.verdict, one.indexer, one.total) for one in view.counts] == [
            (SearchVerdict.FITS, "YTS", 1),
            (SearchVerdict.FITS, "The Pirate Bay", 2),
            (SearchVerdict.YEAR, "YTS", 1),
        ]
