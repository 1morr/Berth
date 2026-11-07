"""集數的寫法（`domain/episodes.py`）：範圍的排版與多集檔（M5.6 票 06）。

範圍只有一種寫法，給模型的媒體庫命中、作品的集表與對不上的集都用它；型式在
`agent_tools` 與 `inventory` 的測試裡驗，這裡驗純排版。
"""

from __future__ import annotations

from berth.domain import number_ranges, season_ranges


def test_consecutive_numbers_collapse_into_one_span() -> None:
    assert number_ranges([1, 2, 3, 5]) == "1-3, 5"


def test_duplicates_count_once_and_nothing_is_empty() -> None:
    assert number_ranges([3, 1, 2, 2]) == "1-3"
    assert number_ranges([]) == ""


def test_each_season_keeps_its_own_ranges_and_multipart_files_cover_every_episode() -> None:
    assert season_ranges([(1, 1, None), (1, 2, 3), (1, 7, None), (2, 1, None)]) == {
        "1": "1-3, 7",
        "2": "1",
    }


def test_an_end_before_the_start_is_ignored() -> None:
    """Jellyfin 的 `IndexNumberEnd` 不該比 `IndexNumber` 小；真的遇到時只算第一集。"""
    assert season_ranges([(1, 5, 4)]) == {"1": "5"}
