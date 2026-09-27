"""RSS Series 完結了沒（M4 票 13、`parser.finished`）。

**逐條件雙向**：兩條路各從一個會被判完結的 Series 出發，每一次只改一個條件，它就回到清單；
無關的改動（別季的集數、完結之外的 TMDB 狀態）不改結果。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from berth.domain import EpisodeSnapshot, MediaKind, MediaSnapshot, SeasonSnapshot
from berth.parser import QUIET_AFTER, SETTLED_AFTER, series_finished

NOW = datetime(2026, 9, 27, 12, tzinfo=UTC)
#: 最後一集十天前發佈：過了一週，也還沒到安靜太久。
LAST = NOW - timedelta(days=10)


def media(*, ended: bool = True, episodes: int = 12) -> MediaSnapshot:
    return MediaSnapshot(
        tmdb_id=1,
        kind=MediaKind.TV,
        title="與你相戀到生命盡頭",
        title_en="Kimi ga Shinu made Koi wo Shitai",
        title_original="",
        ended=ended,
        seasons=(
            SeasonSnapshot(
                season_number=1,
                episode_count=episodes,
                episodes=tuple(EpisodeSnapshot(episode_number=n) for n in range(1, episodes + 1)),
            ),
            SeasonSnapshot(
                season_number=2,
                episode_count=3,
                episodes=tuple(EpisodeSnapshot(episode_number=n) for n in range(1, 4)),
            ),
        ),
    )


ALL_OF_S1 = frozenset((1, n) for n in range(1, 13))


def finished(**changes: object) -> bool:
    """TMDB 說完結、第一季全在庫、沒有在路上的、最後一筆十天前的 Series；`changes` 改一格。"""
    given: dict[str, object] = {
        "latest": LAST,
        "now": NOW,
        "media": media(),
        "seasons": frozenset({1}),
        "held": ALL_OF_S1,
        "open_items": 0,
    }
    given.update(changes)
    return series_finished(**given)  # type: ignore[arg-type]  # 測試以 dict 逐格覆寫參數


class TestEndedAndComplete:
    def test_ended_complete_and_settled_is_finished(self) -> None:
        assert finished()

    def test_tmdb_still_airing_is_not(self) -> None:
        assert not finished(media=media(ended=False))

    def test_one_episode_missing_is_not(self) -> None:
        assert not finished(held=ALL_OF_S1 - {(1, 7)})

    def test_any_new_item_within_a_week_is_not(self) -> None:
        # 新的一筆不論送了沒（排除、重複、v2 都算）都把它帶回清單，一週之後再收起來。
        assert not finished(latest=NOW - timedelta(days=2))
        assert not finished(latest=NOW - SETTLED_AFTER)
        assert finished(latest=NOW - SETTLED_AFTER - timedelta(minutes=1))

    def test_an_item_waiting_or_on_its_way_is_not(self) -> None:
        # 新的一筆出現時條件自己不成立：它回到清單，入庫之後再收起來。
        assert not finished(open_items=1)

    def test_nothing_imported_yet_is_not(self) -> None:
        # 沒有入庫過任何一季就說不出「對得到的集數」是哪些。
        assert not finished(seasons=frozenset(), held=frozenset())

    def test_no_work_is_not(self) -> None:
        assert not finished(media=None)

    def test_only_the_seasons_it_imported_into_count(self) -> None:
        # 第二季一集都沒有，但這個 Series 只送過第一季。
        assert finished(held=ALL_OF_S1 | {(2, 1)})
        assert not finished(seasons=frozenset({1, 2}))

    def test_extra_episodes_in_the_library_do_not_matter(self) -> None:
        assert finished(held=ALL_OF_S1 | {(1, 13), (0, 1)})


class TestQuiet:
    def test_quiet_past_the_threshold_is_finished_even_if_airing(self) -> None:
        stale = NOW - QUIET_AFTER - timedelta(minutes=1)
        assert finished(latest=stale, media=media(ended=False), held=frozenset(), open_items=2)

    def test_quiet_exactly_at_the_threshold_is_not(self) -> None:
        assert not finished(latest=NOW - QUIET_AFTER, media=media(ended=False))

    def test_a_new_item_brings_it_back(self) -> None:
        assert not finished(latest=NOW - timedelta(hours=1), media=None)

    @pytest.mark.parametrize("days", [7, 14, 22])
    def test_the_gaps_measured_in_the_trial_stay_on_the_list(self, days: int) -> None:
        # 試跑 10 個 Series 相鄰兩筆最長隔 22 天（M4 票 13 的 shape）。
        assert not finished(latest=NOW - timedelta(days=days), media=media(ended=False))
