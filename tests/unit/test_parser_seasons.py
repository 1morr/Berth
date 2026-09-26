"""季名的寫法：一份規則，`structure` 讀資料夾名、`binding` 拆搜尋詞（M4 票 14）。

每一種寫法雙向：寫在名字裡要拆得出季號，長得像卻不是季名的不能動。
"""

from __future__ import annotations

import pytest

from berth.parser.seasons import split_season


class TestEachWritingIsSplit:
    @pytest.mark.parametrize(
        ("name", "rest", "season"),
        [
            ("Re：从零开始的异世界生活 第四季", "Re：从零开始的异世界生活", 4),
            ("某某 第2季", "某某", 2),
            ("某某 第 十一 季", "某某", 11),
            ("某某 第三期", "某某", 3),
            (
                "Re:Zero kara Hajimeru Isekai Seikatsu 4th Season",
                "Re:Zero kara Hajimeru Isekai Seikatsu",
                4,
            ),
            ("Shingeki no Kyojin 3rd Season", "Shingeki no Kyojin", 3),
            ("Kaguya-sama 2nd season", "Kaguya-sama", 2),
            ("Spy x Family Season 2", "Spy x Family", 2),
            ("Spy x Family Season.2", "Spy x Family", 2),
            ("Mushoku Tensei S2", "Mushoku Tensei", 2),
            ("Mushoku Tensei s02", "Mushoku Tensei", 2),
        ],
    )
    def test_the_season_leaves_the_name(self, name: str, rest: str, season: int) -> None:
        assert split_season(name) == (rest, season)

    def test_the_season_in_the_middle_leaves_one_space(self) -> None:
        assert split_season("Re：从零开始的异世界生活 第四季 夺还篇") == (
            "Re：从零开始的异世界生活 夺还篇",
            4,
        )


class TestLookalikesStay:
    @pytest.mark.parametrize(
        "name",
        [
            "与你相恋到生命尽头",
            "Spy x Family",
            "Seasons of Love",
            "Mob Psycho 100",
            "Kaiju No. 8",
            "The 2nd Life",
            "SS2 Club",
            "Kimetsu no Yaiba S",
            "某某 第12话",
            "某某 第二部分",
        ],
    )
    def test_a_name_without_a_season_is_left_alone(self, name: str) -> None:
        assert split_season(name) == (name, None)
