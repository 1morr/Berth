"""資料夾結構提示（plan §4.1 的 `structure_hints`、brief §6.4、§6.7）。

路徑講的話與檔名講的話不一樣：`Season 2/` 裡的 `- 05` 是第二季第五集，而檔名自己
從頭到尾沒有提過季。這一層只讀**路徑**，讀不到就留空——猜是 `map_episode` 的事。
"""

from __future__ import annotations

import pytest

from berth.domain import Lang
from berth.parser import structure_hints


class TestSeasonFolders:
    """brief §6.4 第 3 點的資料夾提示。"""

    @pytest.mark.parametrize(
        ("folder", "season"),
        [
            ("Season 2", 2),
            ("Season.2", 2),
            ("season 10", 10),
            ("S2", 2),
            ("S02", 2),
            ("第二季", 2),
            ("第2季", 2),
            ("第三期", 3),
            ("2nd Season", 2),
            ("3rd Season", 3),
            ("1st Season", 1),
        ],
    )
    def test_it_reads_the_season_number(self, folder: str, season: int) -> None:
        assert structure_hints(f"{folder}/Show - 05.mkv").season == season

    def test_a_folder_that_says_nothing_says_nothing(self) -> None:
        hints = structure_hints("Show (2016)/Show - 05.mkv")

        assert (hints.season, hints.part, hints.special) == (None, None, False)

    def test_the_file_name_is_not_a_folder(self) -> None:
        """`S02` 在檔名裡是發佈名解析的事，不是結構的事——兩層各讀各的。"""
        assert structure_hints("Show.S02E05.mkv").season is None

    def test_the_deepest_folder_wins(self) -> None:
        """`Fleabag (2016)/Season 2/` —— 外層是作品，內層才是季。"""
        assert structure_hints("Fleabag (2016)/Season 2/Fleabag - S02E01.mkv").season == 2


class TestPartFolders:
    """`Part 2` 是 cour，不是季（plan §4.4）。"""

    @pytest.mark.parametrize("folder", ["Part 2", "Part.2", "第二部分"])
    def test_it_reads_the_part_number(self, folder: str) -> None:
        assert structure_hints(f"{folder}/Show - 01.mkv").part == 2

    def test_a_season_and_a_part_are_two_different_numbers(self) -> None:
        hints = structure_hints("Season 3/Part 2/Show - 01.mkv")

        assert (hints.season, hints.part) == (3, 2)


class TestSpecialFolders:
    @pytest.mark.parametrize("folder", ["Specials", "SPs", "SP", "特典", "映像特典"])
    def test_it_knows_a_specials_folder(self, folder: str) -> None:
        assert structure_hints(f"{folder}/Show SP01.mkv").special is True

    def test_a_specials_folder_is_not_a_season_number(self) -> None:
        """季 0 由 `map_episode` 決定：`Specials/` 說的是「這不是正片」，不是「這是第 0 季」。"""
        assert structure_hints("Specials/Show SP01.mkv").season is None


class TestSubtitleFolders:
    """brief §6.7 的第 2 點與第 3 點。"""

    @pytest.mark.parametrize("folder", ["Subs", "subtitles", "字幕", "外挂字幕"])
    def test_it_knows_a_subtitle_folder(self, folder: str) -> None:
        assert structure_hints(f"{folder}/Show - 01.ass").subtitle_folder is True

    @pytest.mark.parametrize(
        ("folder", "lang"),
        [
            ("繁體", Lang.CHT),
            ("简体", Lang.CHS),
            ("CHT", Lang.CHT),
            ("SC", Lang.CHS),
            ("TC", Lang.CHT),
            ("JP", Lang.JP),
        ],
    )
    def test_it_reads_the_language_subfolder(self, folder: str, lang: Lang) -> None:
        hints = structure_hints(f"Subs/{folder}/Show - 01.ass")

        assert (hints.subtitle_folder, hints.subtitle_lang) == (True, lang)

    def test_a_language_folder_outside_a_subtitle_folder_still_counts(self) -> None:
        """`繁體/` 直接放在根目錄也是同一件事——外掛字幕不一定包在 `Subs/` 裡。"""
        assert structure_hints("繁體/Show - 01.ass").subtitle_lang is Lang.CHT

    def test_two_languages_in_one_folder_name_say_nothing(self) -> None:
        """`简繁/` 分不出這一個檔案是哪一種，留空比猜對一半好。"""
        assert structure_hints("Subs/简繁/Show - 01.ass").subtitle_lang is None


class TestMatched:
    def test_it_records_what_it_recognised(self) -> None:
        """UI 要說得出「為什麼判成第二季」（brief §6.3）。"""
        assert structure_hints("Season 2/Show - 05.mkv").matched == ("Season 2",)
