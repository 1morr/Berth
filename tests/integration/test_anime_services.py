"""動漫資料來源的兩組 services（M5 票 16）：AniList 的季表、Bangumi 放送表。

直接呼叫 service 函式，client 是替身，替身裡的條目是手寫的。
"""

from __future__ import annotations

from datetime import date
from typing import Self

import pytest

from berth.adapters.anilist import (
    AnimeEntry,
    AnimeSeason,
    AnimeTitle,
)
from berth.adapters.anilist.fake import FakeAniList
from berth.adapters.bgm import CalendarItem
from berth.adapters.bgm.fake import FakeBgm
from berth.services import anilist as anilist_service
from berth.services.anilist import (
    read_season,
    season_of,
)
from berth.services.bgm import read_calendar
from tests.integration.factories import FakeClientFactory

# --- 手寫的條目 -----------------------------------------------------------------------------------


def entry(
    anime_id: int,
    *,
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
        scorers=scorers,
        next_episode=next_episode,
    )


# --- read_season ----------------------------------------------------------------------------------


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
