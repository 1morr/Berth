"""索引站搜尋這一支命令（票 08、plan §6 search 群組）。

驗的是**領域決策**：哪幾個關鍵字問出去、結果怎麼合併去重、一個查詢垮掉時剩下的還在不在、
每一列的 Tags 與預估季集是什麼。協定本身（Prowlarr 的 REST 與 Torznab 的 XML）由
`test_indexer_search.py` 對錄製回應守著，所以這裡一律用 `FakeIndexerSearch`。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.budget import RequestBudget
from berth.adapters.http import AuthFailedError, ServiceUnavailableError
from berth.adapters.indexer import IndexerResult, SearchCapability
from berth.adapters.indexer.fake import FakeIndexerSearch
from berth.domain import (
    IndexerProblem,
    MappingStrategy,
    MediaKind,
    Source,
    StepStatus,
)
from berth.models import IndexerSettings, Media, Route
from berth.models import media_id as build_media_id
from berth.services.search import RESULT_LIMIT, plan_queries, search_torrents
from berth.services.settings import write_settings
from tests.integration.factories import FakeClientFactory
from tests.integration.test_inventory import linked, route, title
from tests.integration.test_inventory import season as season_snapshot

SPY = build_media_id(MediaKind.TV, 120089)
OPPENHEIMER = build_media_id(MediaKind.MOVIE, 872585)


def result(title: str, **kwargs: Any) -> IndexerResult:
    return IndexerResult(title=title, **kwargs)


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
                "episodes": [{"episode_number": n, "name": f"E{n}"} for n in range(1, 13)],
            },
            {
                "season_number": 3,
                "name": "Season 3",
                "episode_count": 13,
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
    await write_settings(
        session, IndexerSettings(kind="prowlarr", base_url="http://prowlarr:9696", api_key="k")
    )
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
    """英文、原文與各語言別名各發一次：實測三個標題的聯集比任何一個都大得多（票 08）。

    只有一季，所以沒有季號變體佔掉排最後的別名。
    """
    await arrange_media(session)
    await arrange_indexer(session)
    await restyle(session, seasons=[season_of(1, 12)])
    indexer = FakeIndexerSearch(
        by_query={
            "SPY x FAMILY": (result("SPY x FAMILY S03E01 1080p WEB", info_hash="a" * 40),),
            "SPY×FAMILY": (result("SPY×FAMILY 03", info_hash="b" * 40),),
            "間諜家家酒": (result("間諜家家酒 03", info_hash="c" * 40),),
            "间谍过家家": (result("间谍过家家 03", info_hash="d" * 40),),
        }
    )
    factory = FakeClientFactory(indexer_search=indexer)

    view = await search_torrents(session, factory, media_id=SPY)

    assert sorted(query.text for query in indexer.queries) == sorted(
        ["SPY x FAMILY", "SPY×FAMILY", "間諜家家酒", "间谍过家家"]
    )
    assert view.total == 4
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

    view = await search_torrents(session, factory, media_id=SPY)

    assert view.total == 2
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

    view = await search_torrents(session, factory, media_id=SPY)

    assert view.total == RESULT_LIMIT + 20
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

    view = await search_torrents(session, factory, media_id=SPY)

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

    view = await search_torrents(session, factory, media_id=SPY)

    assert view.problem is None
    assert view.total == 1
    failed = [attempt for attempt in view.attempts if attempt.status is StepStatus.FAILED]
    assert [attempt.step for attempt in failed] == ["SPY×FAMILY"]
    assert failed[0].error == "GET /api/v1/search: ReadTimeout"


@pytest.mark.asyncio
async def test_an_indexer_that_was_never_set_up_says_so(session: AsyncSession) -> None:
    """精靈第 6 步是唯一可以跳過的一步，所以「沒接」不是失敗，是還沒接（票 08 驗收）。"""
    await arrange_media(session)
    factory = FakeClientFactory(indexer_search=FakeIndexerSearch())

    view = await search_torrents(session, factory, media_id=SPY)

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

    view = await search_torrents(session, factory, media_id=SPY)

    assert view.problem is IndexerProblem.CREDENTIAL_REJECTED
    assert view.detail == "GET /api/v1/search: 401"


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

    view = await search_torrents(session, factory, media_id=SPY)

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

    view = await search_torrents(session, factory, media_id=SPY)

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

    view = await search_torrents(session, factory, media_id=SPY)

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

    view = await search_torrents(session, factory, media_id=SPY)

    row = view.rows[0]
    assert (row.season, row.episode_start) == (None, None)
    assert row.tags.resolution == "2160p"


@pytest.mark.asyncio
async def test_releases_that_are_not_this_work_do_not_reach_the_table(
    session: AsyncSession,
) -> None:
    """**索引站對搜不到的關鍵字會回它自己的熱門清單**（2026-09-10 實跑 The Pirate Bay）。

    那些東西動輒五六千個做種，依做種排序時會把真正的結果整批擠出前 100 筆。丟掉，
    但把丟掉幾筆說出來——「索引站什麼都沒回」與「回了一堆但沒有一筆是這部作品」
    的下一步不同。
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

    view = await search_torrents(session, factory, media_id=SPY)

    assert [row.title for row in view.rows] == ["SPY x FAMILY S02E01 1080p WEB"]
    assert (view.total, view.discarded) == (1, 1)


@pytest.mark.asyncio
async def test_a_typed_keyword_turns_the_filter_off(session: AsyncSession) -> None:
    """自己打字時他要的就是那一串字，不是這部作品——那時 Berth 沒有資格篩。"""
    await arrange_media(session)
    await arrange_indexer(session)
    indexer = FakeIndexerSearch(
        results=(result("Spider-Man: Brand New Day 2026.1080p", info_hash="b" * 40),)
    )
    factory = FakeClientFactory(indexer_search=indexer)

    view = await search_torrents(session, factory, media_id=SPY, query="Spider-Man")

    assert len(view.rows) == 1
    assert view.discarded == 0


@pytest.mark.asyncio
async def test_a_show_past_its_first_season_adds_the_season_variants(
    session: AsyncSession,
) -> None:
    """發佈名常常只寫得出 `第3季` / `Season 3`，光靠作品名搜不到那一季（plan §8.4）。

    **不分動漫**（票 14e，brief §19）：Route 上已經沒有東西說得出「這是動漫」，而美劇的
    `The Bear Season 3` 一樣是真的發佈名。
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

    await search_torrents(session, factory, media_id=SPY)

    texts = [query.text for query in indexer.queries]
    assert "The Bear Season 3" in texts
    assert "熊家餐館 第3季" in texts


@pytest.mark.asyncio
async def test_the_display_title_beats_a_random_alias(session: AsyncSession) -> None:
    """TMDB 的別名沒有順序可言，所以顯示用標題明確排第三——不然由 TMDB 決定誰進前五名。

    實跑抓到的樣子：`Agent x Ailə`（亞塞拜然語）排在中文標題前面，而使用者的索引站上
    是中文字幕組（票 08）。
    """
    await arrange_media(session)
    await arrange_indexer(session)
    row = await session.get(Media, SPY)
    assert row is not None
    row.tmdb_snapshot_json = {
        **(row.tmdb_snapshot_json or {}),
        "titles": ["SPY x FAMILY", "Agent x Ailə", "Spy Familie", "間諜家家酒", "间谍过家家"],
    }
    await session.commit()
    indexer = FakeIndexerSearch()
    factory = FakeClientFactory(indexer_search=indexer)

    await search_torrents(session, factory, media_id=SPY)

    texts = [query.text for query in indexer.queries]
    assert texts[:3] == ["SPY x FAMILY", "SPY×FAMILY", "間諜家家酒"]


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

    await search_torrents(session, factory, media_id=SPY)

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

    await search_torrents(session, factory, media_id=OPPENHEIMER)

    assert [query.text for query in indexer.queries] == ["Oppenheimer", "奧本海默"]
    assert season_queries(indexer) == []


@pytest.mark.asyncio
async def test_a_typed_query_replaces_the_titles(session: AsyncSession) -> None:
    """使用者自己打字時就只問那一個——他比 TMDB 更知道自己在找什麼。"""
    await arrange_media(session)
    await arrange_indexer(session)
    indexer = FakeIndexerSearch()
    factory = FakeClientFactory(indexer_search=indexer)

    await search_torrents(session, factory, media_id=SPY, query="Spy Family BDRip")

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

    view = await search_torrents(session, factory, media_id=SPY)

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

        await search_torrents(session, factory, media_id=spy.id, missing=True)

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

        await search_torrents(session, factory, media_id=spy.id, missing=True, season=2)

        assert [query.text for query in indexer.queries] == ["SPY x FAMILY S02"]

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

        preview = (await plan_queries(session, factory, media_id=spy.id, missing=True)).queries
        await search_torrents(session, factory, media_id=spy.id, missing=True)

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

        view = await search_torrents(session, factory, media_id=spy.id, missing=True)

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
            session, factory, media_id=spy.id, query="Spy Family BDRip", missing=True
        )

        assert [query.text for query in indexer.queries] == ["Spy Family BDRip"]

    @pytest.mark.asyncio
    async def test_an_id_search_does_not_swallow_the_narrowing(self, session: AsyncSession) -> None:
        """端點認得 tmdbid 時整批換成一個 id 查詢（票 08）——但 id 找的是**整部作品**，
        收窄到缺的那幾集就沒了，而預覽已經說了要問那幾集。缺集搜尋因此不走 id 那條路。"""
        tv = await route(session)
        spy = await title(session, seasons=(season_snapshot(1, aired=2),))
        await linked(session, spy, tv, episode=1)
        await arrange_indexer(session)
        indexer = FakeIndexerSearch(capability=SearchCapability(tmdb_id=frozenset({MediaKind.TV})))
        factory = FakeClientFactory(indexer_search=indexer)

        await search_torrents(session, factory, media_id=spy.id, missing=True)

        assert [query.text for query in indexer.queries] == ["SPY x FAMILY S01E02"]
        assert [query.tmdb_id for query in indexer.queries] == [None]

    @pytest.mark.asyncio
    async def test_gaps_in_seven_seasons_are_asked_batch_by_batch(
        self, session: AsyncSession
    ) -> None:
        """M3 票 20 驗收第二條：七季都有缺，季記號放不下一批——**分批問完每一季**，一次也不退回
        作品名。每一批說得出問了哪幾季、下一批是哪幾季、預算何時放得下它。"""
        long = await seven_seasons(session)
        indexer = FakeIndexerSearch(sites=frozenset({"mikanani.me"}))
        clock = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
        factory = FakeClientFactory(
            indexer_search=indexer, budget=RequestBudget(limit=60, now=lambda: clock)
        )

        first = await search_torrents(session, factory, media_id=long.id, missing=True)
        assert first.batch is not None
        second = await search_torrents(
            session,
            factory,
            media_id=long.id,
            missing=True,
            from_season=first.batch.next_seasons[0],
        )

        asked = [query.text for query in indexer.queries]
        assert asked[:5] == [f"SPY x FAMILY S{number:02d}" for number in range(1, 6)]
        # 第二批只剩兩季、兩集缺：記號放得下逐集，就問那兩集（收成季記號只在放不下時才做）。
        assert asked[5:7] == ["SPY x FAMILY S06E02", "SPY x FAMILY S07E02"]
        assert "SPY x FAMILY" not in asked
        assert (first.batch.seasons, first.batch.later) == ((1, 2, 3, 4, 5), 1)
        assert first.batch.next_seasons == (6, 7)
        # 預算還寬：下一批現在就問得（這一批用掉 5 格，60 格還剩很多）。
        assert first.batch.next_at == clock
        assert second.batch is not None
        assert (second.batch.seasons, second.batch.later, second.batch.next_seasons) == (
            (6, 7),
            0,
            (),
        )
        assert second.batch.next_at is None

    @pytest.mark.asyncio
    async def test_the_next_batch_still_asks_its_seasons_after_some_were_sent(
        self, session: AsyncSession
    ) -> None:
        """問完第一批、從結果送了幾季之後季表就變了：下一批照季定位，S06、S07 照樣問得到
        （以序號定位時 S02 補上之後第二批只剩 S07，code review 抓到）。"""
        long = await seven_seasons(session)
        indexer = FakeIndexerSearch()
        factory = FakeClientFactory(indexer_search=indexer)
        first = await search_torrents(session, factory, media_id=long.id, missing=True)
        assert first.batch is not None
        tv = await session.scalar(select(Route).where(Route.slug == "tv"))
        assert tv is not None
        await linked(session, long, tv, season_number=2, episode=2)
        indexer.queries.clear()

        await search_torrents(
            session,
            factory,
            media_id=long.id,
            missing=True,
            from_season=first.batch.next_seasons[0],
        )

        assert [query.text for query in indexer.queries][:2] == [
            "SPY x FAMILY S06E02",
            "SPY x FAMILY S07E02",
        ]

    @pytest.mark.asyncio
    async def test_the_preview_names_the_batch_it_will_ask(self, session: AsyncSession) -> None:
        """預覽與搜尋同一份：第二批的預覽就是第二批真的問出去的那幾個。"""
        long = await seven_seasons(session)
        indexer = FakeIndexerSearch()
        factory = FakeClientFactory(indexer_search=indexer)

        preview = await plan_queries(
            session, factory, media_id=long.id, missing=True, from_season=6
        )
        await search_torrents(session, factory, media_id=long.id, missing=True, from_season=6)

        assert list(preview.queries) == [query.text for query in indexer.queries]
        assert preview.batch is not None
        assert (preview.batch.seasons, preview.batch.later) == ((6, 7), 0)


async def seven_seasons(session: AsyncSession) -> Media:
    """七季、每季播了兩集、每季只入庫第一集：七個季都缺一集，季記號放不下一批。"""
    tv = await route(session)
    long = await title(
        session, seasons=tuple(season_snapshot(number, aired=2) for number in range(1, 8))
    )
    for number in range(1, 8):
        await linked(session, long, tv, season_number=number, episode=1)
    await arrange_indexer(session)
    return long
