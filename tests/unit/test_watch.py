"""一位使用者在 Jellyfin 看到哪了：牆上那一行由 `UserData` 怎麼推出來（M1.5 票 05）。

判定照 jellyfin-web 的卡片（v10.11.11 `components/indicators`）：劇集只有「已看」與「剩幾集沒看」，
沒開始看的劇集也有集數；「看到一半」只有影片。輸入的值取自 12.1.0 錄的 fixture
（`items.tv.series.userdata.json`、`items.movies.movie.userdata.json`、`userplayeditems.*.json`）。
"""

from __future__ import annotations

import pytest

from berth.adapters.jellyfin import JellyfinUserData
from berth.services.watch import WatchState, watch_state


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        # Alpha Show：五集看過一集。
        (JellyfinUserData(False, 20.0, 4), WatchState(False, None, 4)),
        # Frieren：一集都沒看，jellyfin-web 照樣畫集數。
        (JellyfinUserData(False, 0.0, 2), WatchState(False, None, 2)),
        # 整部標為已看之後的回應（研究 §5）。
        (JellyfinUserData(True, 100.0, 0), WatchState(True, None, None)),
        # 沒有任何一集的劇集：沒有東西可以說。
        (JellyfinUserData(False, 0.0, 0), WatchState(False, None, None)),
        # Foxtrot Movie：看到一半。
        (JellyfinUserData(False, 50.0, None), WatchState(False, 50, None)),
        # Echo Movie：看過，沒有 `PlayedPercentage`。
        (JellyfinUserData(True, 0.0, None), WatchState(True, None, None)),
        # 沒看過的片。
        (JellyfinUserData(False, 0.0, None), WatchState(False, None, None)),
    ],
)
def test_the_line_on_the_wall_follows_jellyfin_web(
    data: JellyfinUserData, expected: WatchState
) -> None:
    assert watch_state(data) == expected


@pytest.mark.parametrize(("percentage", "shown"), [(0.4, 1), (42.4, 42), (42.6, 43), (99.6, 99)])
def test_a_film_under_way_is_never_shown_at_zero_or_a_hundred(
    percentage: float, shown: int
) -> None:
    """「看到 0%」「看到 100%」卻沒看完，兩句都是假話。"""
    assert watch_state(JellyfinUserData(False, percentage, None)).progress == shown


def test_a_film_rewatched_part_way_is_still_played() -> None:
    """看過又重看到一半：牆上那一行只說一件事，已看優先（jellyfin-web 兩個標記都畫）。"""
    assert watch_state(JellyfinUserData(True, 30.0, None)) == WatchState(True, None, None)


def test_a_percentage_at_a_hundred_is_played_even_without_the_flag() -> None:
    """jellyfin-web：`PlayedPercentage >= 100 || Played` 就畫勾。"""
    assert watch_state(JellyfinUserData(False, 100.0, None)).played
