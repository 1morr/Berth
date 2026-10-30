"""Jellyfin 的集怎麼對到 TMDB 的集（`inventory.match_episodes`，M5 票 28，使用者 2026-10-30）。

規則只看播出日，不看 Jellyfin 的季集號；寧可多下一集，不要漏一集——所以每一條拿不準的路都要落到
「對不上」（照舊算缺），而不是對到某一集。作品頁與給模型的那一份經 API 的測試在
`tests/integration/test_media_in_jellyfin.py::TestTheNumbering`。
"""

from __future__ import annotations

from datetime import date, timedelta

from berth.adapters.jellyfin import ITEM_EPISODE, JellyfinItem
from berth.domain import EpisodeSnapshot, MediaKind, MediaSnapshot, SeasonSnapshot
from berth.services.inventory import UnmatchedEpisode, match_episodes

FIRST = date(2024, 4, 13)


def snapshot(*seasons: list[tuple[int, date]]) -> MediaSnapshot:
    """`seasons[0]` 是 S00（特典），之後是 S01、S02…；每一季是（集號, 播出日）。"""
    return MediaSnapshot(
        tmdb_id=1,
        kind=MediaKind.TV,
        title="Show",
        title_en="Show",
        title_original="Show",
        seasons=tuple(
            SeasonSnapshot(
                season_number=number,
                episode_count=len(episodes),
                episodes=tuple(
                    EpisodeSnapshot(episode_number=n, air_date=day) for n, day in episodes
                ),
            )
            for number, episodes in enumerate(seasons)
        ),
    )


def weekly(count: int, first: date = FIRST) -> list[tuple[int, date]]:
    return [(n, first + timedelta(weeks=n - 1)) for n in range(1, count + 1)]


def jellyfin(
    season: int, start: int, premiere: date | None, *, end: int | None = None
) -> JellyfinItem:
    return JellyfinItem(
        f"{season}-{start}",
        ITEM_EPISODE,
        "",
        "",
        "",
        season=season,
        episode_start=start,
        episode_end=end,
        premiere_date=premiere,
    )


def test_the_air_date_decides_not_jellyfins_numbers() -> None:
    """Jellyfin 的 S02E01 是 TMDB 第 1 季最後一集那一天播的：算 TMDB 的 S01E14。"""
    tmdb = snapshot([], weekly(14))

    held, unmatched = match_episodes([jellyfin(2, 1, FIRST + timedelta(weeks=13))], tmdb)

    assert (held, unmatched) == (frozenset({(1, 14)}), ())


def test_two_tmdb_episodes_within_a_day_match_neither() -> None:
    """雙集首播（同一天兩集）：拿不準是哪一集，兩集都照舊算缺。"""
    tmdb = snapshot([], [(1, FIRST), (2, FIRST), *weekly(4, FIRST + timedelta(weeks=1))[1:]])

    held, unmatched = match_episodes([jellyfin(1, 1, FIRST)], tmdb)

    assert held == frozenset()
    assert unmatched == (UnmatchedEpisode(1, 1, None, FIRST),)


def test_a_special_never_claims_a_regular_episode() -> None:
    """Jellyfin 的特典（S00）在第 5 集的隔天播，TMDB 沒列這個特典：不能把第 5 集算成有。"""
    tmdb = snapshot([], weekly(8))
    aired = FIRST + timedelta(weeks=4, days=1)

    held, unmatched = match_episodes([jellyfin(0, 1, aired)], tmdb)

    assert held == frozenset()
    assert unmatched == (UnmatchedEpisode(0, 1, None, aired),)


def test_a_tmdb_special_on_the_same_day_does_not_blur_the_regular_one() -> None:
    """TMDB 的特典與正片同一天：正片照樣對得上（特典只與特典比）。"""
    tmdb = snapshot([(1, FIRST)], weekly(4))

    held, _ = match_episodes([jellyfin(1, 1, FIRST)], tmdb)

    assert held == frozenset({(1, 1)})


def test_one_tmdb_episode_claimed_twice_is_claimed_by_neither() -> None:
    """兩個 Jellyfin 的集對到同一集（一集重複、或兩集差一天）：拿不準，都不算。"""
    tmdb = snapshot([], weekly(4))

    held, unmatched = match_episodes(
        [jellyfin(1, 1, FIRST), jellyfin(1, 9, FIRST + timedelta(days=1))], tmdb
    )

    assert held == frozenset()
    assert len(unmatched) == 2


def test_a_double_episode_file_counts_only_the_episode_its_date_matches() -> None:
    """多集檔（E01-E02）對到第 1 集；第 2 集是下一週播的，不算進來（寧可多下一集）。同一天播的
    兩集則連起點都拿不準。"""
    weekly_tmdb = snapshot([], weekly(4))
    same_day = snapshot([], [(1, FIRST), (2, FIRST), (3, FIRST + timedelta(weeks=1))])

    assert match_episodes([jellyfin(1, 1, FIRST, end=2)], weekly_tmdb)[0] == frozenset({(1, 1)})
    assert match_episodes([jellyfin(1, 1, FIRST, end=2)], same_day)[0] == frozenset()


def test_no_air_date_is_unmatched() -> None:
    tmdb = snapshot([], weekly(4))

    held, unmatched = match_episodes([jellyfin(1, 1, None)], tmdb)

    assert held == frozenset()
    assert unmatched == (UnmatchedEpisode(1, 1, None, None),)
