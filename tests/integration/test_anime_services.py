"""動漫資料來源的三組 services（M5 票 16）：AniList 的系列與季表、Fribb 的 ID 對應、Bangumi 放送表。

直接呼叫 service 函式，client 是替身；替身裡的條目有兩種：手寫的小圖（走圖規則），和錄下來的
Re:Zero 系列與 Fribb 裁出的表（`tests/fixtures/http/`）。
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date
from typing import Self

import pytest

from berth.adapters.anilist import (
    AnimeEntry,
    AnimeRelation,
    AnimeSeason,
    AnimeTitle,
    page_media,
    parse_entries,
)
from berth.adapters.anilist.fake import FakeAniList
from berth.adapters.bgm import CalendarItem
from berth.adapters.bgm.fake import FakeBgm
from berth.adapters.fribb import FribbEntry, parse_list
from berth.adapters.fribb.fake import FakeAnimeIds
from berth.services import anilist as anilist_service
from berth.services.anilist import (
    MAX_ENTRIES,
    AniListRefusal,
    AniListRefusedError,
    read_franchise,
    read_season,
    search_anime,
    season_of,
)
from berth.services.bgm import read_calendar
from berth.services.fribb import lookup_anime
from tests.conftest import read_fixture
from tests.integration.factories import FakeClientFactory

# --- 手寫的條目 -----------------------------------------------------------------------------------


def entry(
    anime_id: int,
    *relations: tuple[str, int],
    start: str | None = "2020-01-01",
    scorers: int | None = None,
    next_episode: int | None = None,
) -> AnimeEntry:
    return AnimeEntry(
        id=anime_id,
        mal_id=None,
        title=AnimeTitle(romaji=f"Anime {anime_id}", english="", native=""),
        format="TV",
        status="FINISHED",
        episodes=12,
        season=None,
        season_year=None,
        start_date=start,
        average_score=None,
        popularity=None,
        genres=(),
        relations=tuple(AnimeRelation(type=kind, id=i) for kind, i in relations),
        scorers=scorers,
        next_episode=next_episode,
    )


class _Graph(FakeAniList):
    """問太多次就停：走圖的「不重問」壞了時，要紅燈而不是無窮迴圈。"""

    async def entries(self, ids: Sequence[int]) -> list[AnimeEntry]:
        assert len(self.asked) < 100, "the walk keeps asking"
        return await super().entries(ids)


def known(*entries: AnimeEntry) -> FakeAniList:
    return _Graph(known={e.id: e for e in entries})


def batches(fake: FakeAniList) -> list[tuple[int, ...]]:
    """每一次 `entries` 問了哪些 id。"""
    return [what for kind, what in fake.asked if kind == "entries"]  # type: ignore[misc]


def ids(result: anilist_service.Franchise) -> list[int]:
    return [e.anilist_id for e in result.entries]


# --- read_franchise -------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_franchise_is_walked_one_layer_per_question() -> None:
    fake = known(
        entry(1, ("SEQUEL", 2), ("SIDE_STORY", 3)),
        entry(2, ("PREQUEL", 1), ("SEQUEL", 4)),
        entry(3, ("PARENT", 1)),
        entry(4, ("PREQUEL", 2)),
    )

    result = await read_franchise(FakeClientFactory(anilist=fake), 1)

    assert batches(fake) == [(1,), (2, 3), (4,)]
    assert sorted(ids(result)) == [1, 2, 3, 4]
    assert result.truncated is False


@pytest.mark.asyncio
async def test_an_id_is_never_asked_twice_even_when_the_relations_point_back() -> None:
    # 1 ⇄ 2 ⇄ 3 ⇄ 1：每個都指回來
    fake = known(
        entry(1, ("SEQUEL", 2), ("PREQUEL", 3)),
        entry(2, ("PREQUEL", 1), ("SEQUEL", 3)),
        entry(3, ("PREQUEL", 2), ("SEQUEL", 1)),
    )

    result = await read_franchise(FakeClientFactory(anilist=fake), 1)

    asked = [i for batch in batches(fake) for i in batch]
    assert batches(fake) == [(1,), (2, 3)]
    assert len(asked) == len(set(asked))
    assert sorted(ids(result)) == [1, 2, 3]


@pytest.mark.asyncio
async def test_an_id_that_came_back_empty_is_not_asked_again() -> None:
    # 9 是成人向 / 已刪：AniList 不回它。兩條路都指到它，後一條在 9 已經問過之後才走到
    fake = known(
        entry(1, ("SEQUEL", 2), ("SEQUEL", 3)),
        entry(2, ("SEQUEL", 9)),
        entry(3, ("SEQUEL", 4)),
        entry(4, ("SEQUEL", 9)),
    )

    result = await read_franchise(FakeClientFactory(anilist=fake), 1)

    assert batches(fake) == [(1,), (2, 3), (4, 9)]
    assert sorted(ids(result)) == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_spin_offs_are_followed_only_when_asked() -> None:
    graph = (
        entry(1, ("SEQUEL", 2), ("SPIN_OFF", 5)),
        entry(2, ("PREQUEL", 1)),
        entry(5, ("PARENT", 1)),
    )
    plain, with_spinoffs = known(*graph), known(*graph)

    without = await read_franchise(FakeClientFactory(anilist=plain), 1)
    included = await read_franchise(FakeClientFactory(anilist=with_spinoffs), 1, True)

    assert sorted(ids(without)) == [1, 2]
    assert batches(plain) == [(1,), (2,)]
    assert sorted(ids(included)) == [1, 2, 5]
    assert batches(with_spinoffs) == [(1,), (2, 5)]


@pytest.mark.asyncio
async def test_character_alternative_and_adaptation_relations_are_never_followed() -> None:
    fake = known(
        entry(
            1,
            ("CHARACTER", 6),
            ("ALTERNATIVE", 7),
            ("ADAPTATION", 8),
            ("SOURCE", 9),
            ("OTHER", 10),
            ("SUMMARY", 11),
        ),
        entry(6),
        entry(7),
        entry(11),
    )

    result = await read_franchise(FakeClientFactory(anilist=fake), 1, True)

    assert batches(fake) == [(1,), (11,)]
    assert sorted(ids(result)) == [1, 11]


@pytest.mark.asyncio
async def test_every_relation_of_an_entry_is_reported_even_the_unfollowed_ones() -> None:
    fake = known(entry(1, ("SEQUEL", 2), ("CHARACTER", 6)), entry(2))

    result = await read_franchise(FakeClientFactory(anilist=fake), 1)

    first = next(e for e in result.entries if e.anilist_id == 1)
    assert [(r.type, r.anilist_id) for r in first.relations] == [("SEQUEL", 2), ("CHARACTER", 6)]


@pytest.mark.asyncio
async def test_the_walk_stops_at_the_cap_and_says_it_was_cut() -> None:
    chain = [
        entry(i, ("SEQUEL", i + 1)) for i in range(1, MAX_ENTRIES + 6)
    ]  # 1 → 2 → … → 45 → 46（46 不存在）
    fake = known(*chain)

    result = await read_franchise(FakeClientFactory(anilist=fake), 1)

    assert len(result.entries) == MAX_ENTRIES
    assert result.truncated is True
    assert len(batches(fake)) == MAX_ENTRIES  # 一層一個


@pytest.mark.asyncio
async def test_a_franchise_of_exactly_the_cap_is_not_truncated() -> None:
    chain = [entry(i, ("SEQUEL", i + 1)) for i in range(1, MAX_ENTRIES)]
    chain.append(entry(MAX_ENTRIES))  # 最後一部沒有下一部
    fake = known(*chain)

    result = await read_franchise(FakeClientFactory(anilist=fake), 1)

    assert len(result.entries) == MAX_ENTRIES
    assert result.truncated is False


@pytest.mark.asyncio
async def test_a_wide_layer_is_cut_to_the_cap_and_says_so() -> None:
    # 起點有 49 部續集，一層放不下：沒問到的那幾部也算「被截掉」
    children = [("SEQUEL", i) for i in range(2, 51)]
    fake = known(entry(1, *children), *[entry(i) for i in range(2, 51)])

    result = await read_franchise(FakeClientFactory(anilist=fake), 1)

    assert len(result.entries) == MAX_ENTRIES
    assert batches(fake)[1] == tuple(range(2, MAX_ENTRIES + 1))
    assert result.truncated is True


@pytest.mark.asyncio
async def test_entries_are_sorted_by_start_date_with_unknown_dates_last() -> None:
    fake = known(
        entry(
            1,
            ("SEQUEL", 2),
            ("SEQUEL", 3),
            ("SEQUEL", 4),
            ("SEQUEL", 5),
            start="2018-10-06",
        ),
        entry(2, start=None),
        entry(3, start="2016-04-04"),
        entry(4, start="2018-10-06"),  # 與起點同一天：依 id
        entry(5, start="2026"),  # 只知道年
    )

    result = await read_franchise(FakeClientFactory(anilist=fake), 1)

    assert ids(result) == [3, 1, 4, 5, 2]


@pytest.mark.asyncio
async def test_an_unknown_root_is_refused_as_anime_missing() -> None:
    fake = known(entry(1))

    with pytest.raises(AniListRefusedError) as caught:
        await read_franchise(FakeClientFactory(anilist=fake), 404)

    assert caught.value.reason is AniListRefusal.ANIME_MISSING
    assert caught.value.detail == "404"
    assert batches(fake) == [(404,)]


@pytest.mark.asyncio
async def test_the_recorded_rezero_franchise_is_walked_in_the_recorded_layers() -> None:
    layers = [
        parse_entries(
            page_media(
                json.loads(read_fixture(f"http/anilist/entries.rezero.{n}.json"))["body"]["data"]
            )
        )
        for n in range(5)
    ]
    fake = known(*[e for layer in layers for e in layer])

    result = await read_franchise(FakeClientFactory(anilist=fake), 21355)

    # 與錄的時候問的五批一樣（`request.variables.ids`）
    recorded = [
        tuple(
            json.loads(read_fixture(f"http/anilist/entries.rezero.{n}.json"))["request"][
                "variables"
            ]["ids"]
        )
        for n in range(5)
    ]
    assert batches(fake) == recorded
    assert ids(result) == [21355, 100049, 108632, 119661, 163134, 189046]
    assert result.truncated is False
    assert result.entries[0].title_english == "Re:ZERO -Starting Life in Another World-"
    assert result.entries[1].format == "OVA"


@pytest.mark.asyncio
async def test_the_recorded_rezero_spin_offs_are_asked_only_on_request() -> None:
    layers = [
        parse_entries(
            page_media(
                json.loads(read_fixture(f"http/anilist/entries.rezero.{n}.json"))["body"]["data"]
            )
        )
        for n in range(5)
    ]
    fake = known(*[e for layer in layers for e in layer])

    result = await read_franchise(FakeClientFactory(anilist=fake), 21355, True)

    # 起點的外傳（21780、21891）在第二批；表裡沒有它們，所以回不來，但問過了
    assert batches(fake)[1] == (21780, 21891, 100049, 108632)
    assert ids(result) == [21355, 100049, 108632, 119661, 163134, 189046]


# --- search_anime / read_season -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_returns_the_entries_without_relations() -> None:
    fake = FakeAniList(found={"re zero": [entry(1, ("SEQUEL", 2)), entry(2)]})

    result = await search_anime(FakeClientFactory(anilist=fake), "re zero")

    assert [e.anilist_id for e in result.entries] == [1, 2]
    assert not hasattr(result.entries[0], "relations")
    assert result.external_content


class _FixedDate(date):
    today_: date = date(2026, 10, 28)

    @classmethod
    def today(cls) -> Self:
        return cls(cls.today_.year, cls.today_.month, cls.today_.day)


def fix_today(monkeypatch: pytest.MonkeyPatch, day: date) -> None:
    _FixedDate.today_ = day
    monkeypatch.setattr(anilist_service, "date", _FixedDate)


@pytest.mark.parametrize(
    ("month", "season"),
    [
        (1, AnimeSeason.WINTER),
        (2, AnimeSeason.WINTER),
        (3, AnimeSeason.WINTER),
        (4, AnimeSeason.SPRING),
        (5, AnimeSeason.SPRING),
        (6, AnimeSeason.SPRING),
        (7, AnimeSeason.SUMMER),
        (8, AnimeSeason.SUMMER),
        (9, AnimeSeason.SUMMER),
        (10, AnimeSeason.FALL),
        (11, AnimeSeason.FALL),
        (12, AnimeSeason.FALL),
    ],
)
def test_season_of_covers_the_twelve_months(month: int, season: AnimeSeason) -> None:
    assert season_of(date(2026, month, 1)) is season
    assert season_of(date(2026, month, 28)) is season


@pytest.mark.asyncio
async def test_the_season_defaults_to_the_one_we_are_in(monkeypatch: pytest.MonkeyPatch) -> None:
    fix_today(monkeypatch, date(2026, 10, 28))
    fake = FakeAniList(
        seasons={(AnimeSeason.FALL, 2026): [entry(7, scorers=19544, next_episode=5)]}
    )

    result = await read_season(FakeClientFactory(anilist=fake))

    assert (result.season, result.year) == (AnimeSeason.FALL, 2026)
    assert fake.asked == [("season", (AnimeSeason.FALL, 2026))]
    assert [(e.anilist_id, e.scorers, e.next_episode) for e in result.entries] == [(7, 19544, 5)]


@pytest.mark.asyncio
async def test_a_given_season_or_year_replaces_only_its_own_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fix_today(monkeypatch, date(2026, 1, 15))
    fake = FakeAniList()
    factory = FakeClientFactory(anilist=fake)

    await read_season(factory)
    await read_season(factory, AnimeSeason.SUMMER)
    await read_season(factory, year=2024)
    await read_season(factory, AnimeSeason.SPRING, 2019)

    assert [what for _, what in fake.asked] == [
        (AnimeSeason.WINTER, 2026),
        (AnimeSeason.SUMMER, 2026),
        (AnimeSeason.WINTER, 2024),
        (AnimeSeason.SPRING, 2019),
    ]


@pytest.mark.asyncio
async def test_the_season_limit_reaches_the_client() -> None:
    fake = FakeAniList(seasons={(AnimeSeason.FALL, 2026): [entry(i) for i in range(1, 30)]})

    result = await read_season(FakeClientFactory(anilist=fake), AnimeSeason.FALL, 2026, limit=3)

    assert [e.anilist_id for e in result.entries] == [1, 2, 3]


# --- lookup_anime ---------------------------------------------------------------------------------

EXCERPT = parse_list(json.loads(read_fixture("http/fribb/anime-list-full.excerpt.json")))


def mapped() -> FakeClientFactory:
    return FakeClientFactory(anime_ids=FakeAnimeIds(entries=dict(EXCERPT)))


@pytest.mark.asyncio
async def test_the_first_tmdb_episode_is_the_offset_plus_one() -> None:
    result = await lookup_anime(mapped(), [21355, 108632, 119661, 163134, 189046])

    by_id = {e.anilist_id: e for e in result.entries}
    assert {i: e.first_tmdb_episode for i, e in by_id.items()} == {
        21355: 1,  # 沒寫 offset：從第 1 集起
        108632: 27,
        119661: 39,
        163134: 51,
        189046: 67,
    }
    assert by_id[108632].tmdb_episode_offset == 26
    assert by_id[21355].tmdb_episode_offset is None
    assert {e.tmdb_season for e in by_id.values()} == {1}
    assert {tuple(e.media_ids) for e in by_id.values()} == {("tv:65942",)}
    assert result.unmapped == []


@pytest.mark.asyncio
async def test_specials_are_season_zero() -> None:
    result = await lookup_anime(mapped(), [100049])

    [ova] = result.entries
    assert (ova.type, ova.tmdb_season, ova.first_tmdb_episode) == ("OVA", 0, 1)
    assert ova.media_ids == ["tv:65942"]


@pytest.mark.asyncio
async def test_a_movie_maps_to_a_movie_id_and_has_no_season() -> None:
    result = await lookup_anime(mapped(), [164])

    [movie] = result.entries
    assert movie.media_ids == ["movie:128"]
    assert movie.tmdb_season is None
    assert movie.first_tmdb_episode is None
    assert movie.tmdb_episode_offset is None
    assert movie.type == "MOVIE"


@pytest.mark.asyncio
async def test_a_series_without_a_tmdb_season_has_no_first_episode() -> None:
    # Fribb 只寫了 tvdb 那一季（205909）：不猜 TMDB 的
    result = await lookup_anime(mapped(), [205909])

    [series] = result.entries
    assert series.media_ids == ["tv:320909"]
    assert series.tmdb_season is None
    assert series.first_tmdb_episode is None


@pytest.mark.asyncio
async def test_a_tv_entry_that_also_has_movies_lists_the_series_first() -> None:
    both = FribbEntry(
        anilist_id=5,
        type="TV",
        mal_id=None,
        tmdb_tv=10,
        tmdb_movies=(20, 21),
        tmdb_season=2,
        tmdb_episode_offset=12,
    )
    factory = FakeClientFactory(anime_ids=FakeAnimeIds(entries={5: both}))

    [out] = (await lookup_anime(factory, [5])).entries

    assert out.media_ids == ["tv:10", "movie:20", "movie:21"]
    assert (out.tmdb_season, out.first_tmdb_episode) == (2, 13)


@pytest.mark.asyncio
async def test_ids_without_any_tmdb_id_are_unmapped() -> None:
    # 160275 在表上（劇場版）但沒有 TMDB id；999999999 不在表上
    result = await lookup_anime(mapped(), [160275, 999999999, 21355])

    assert [e.anilist_id for e in result.entries] == [21355]
    assert result.unmapped == [160275, 999999999]


@pytest.mark.asyncio
async def test_duplicates_count_once_and_the_given_order_is_kept() -> None:
    fake = FakeAnimeIds(entries=dict(EXCERPT))

    result = await lookup_anime(
        FakeClientFactory(anime_ids=fake), [189046, 21355, 21355, 7, 164, 7, 189046]
    )

    assert [e.anilist_id for e in result.entries] == [189046, 21355, 164]
    assert result.unmapped == [7]
    assert result.external_content


# --- read_calendar --------------------------------------------------------------------------------


def cal(item_id: int, votes: int, weekday: int = 1) -> CalendarItem:
    return CalendarItem(
        id=item_id,
        name=f"n{item_id}",
        name_cn="",
        air_date="2026-10-05",
        weekday=weekday,
        score=None,
        votes=votes,
        rank=None,
    )


@pytest.mark.asyncio
async def test_the_calendar_is_sorted_by_votes_then_id_and_limited() -> None:
    fake = FakeBgm(items=[cal(5, 10), cal(2, 300), cal(9, 10), cal(1, 0), cal(4, 300)])

    result = await read_calendar(FakeClientFactory(bgm=fake), limit=4)

    assert [i.bgm_id for i in result.items] == [2, 4, 5, 9]
    assert result.total == 5
    assert fake.asked == 1


@pytest.mark.asyncio
async def test_the_calendar_default_limit_is_forty() -> None:
    fake = FakeBgm(items=[cal(i, i) for i in range(1, 61)])

    result = await read_calendar(FakeClientFactory(bgm=fake))

    assert len(result.items) == 40
    assert result.total == 60
    assert result.items[0].bgm_id == 60
