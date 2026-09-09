"""標題比對（plan §4.1、§4.3，brief §6.4 第 2 點）。

Job 帶了 Media 時這一層只是覆核；RSS 與重新入庫時它是**唯一**認得出作品的辦法。
比的是正規化之後的字，年份加權——同名不同年的重拍太多了。
"""

from __future__ import annotations

from datetime import date

import pytest

from berth.domain import MediaKind, MediaSnapshot
from berth.parser import match_media, normalize_title, parse_release


def media(
    tmdb_id: int,
    title_en: str,
    *,
    year: int | None = None,
    titles: tuple[str, ...] = (),
    original: str = "",
) -> MediaSnapshot:
    return MediaSnapshot(
        tmdb_id=tmdb_id,
        kind=MediaKind.TV,
        title=title_en,
        title_en=title_en,
        title_original=original or title_en,
        year=year,
        first_air_date=date(year, 1, 1) if year else None,
        titles=titles or (title_en,),
    )


class TestNormalise:
    @pytest.mark.parametrize(
        ("left", "right"),
        [
            ("Sousou no Frieren", "sousou.no.frieren"),
            ("The Bear", "the-bear"),
            ("Mushoku Tensei Ⅲ", "Mushoku Tensei III"),
            ("葬送的芙莉蓮", "【葬送的芙莉蓮】"),
        ],
    )
    def test_two_spellings_of_the_same_title_normalise_to_one(self, left: str, right: str) -> None:
        assert normalize_title(left) == normalize_title(right)

    def test_different_titles_stay_different(self) -> None:
        assert normalize_title("The Bear") != normalize_title("The Boar")


class TestMatch:
    def test_an_exact_title_wins(self) -> None:
        info = parse_release("The.Bear.S03E01.1080p.WEB.H264-SuccessfulCrab.mkv")

        found = match_media(info, [media(1, "Fleabag"), media(2, "The Bear")])

        assert found is not None and found.media.tmdb_id == 2

    def test_an_alternative_title_counts(self) -> None:
        """TMDB 的別名與各語言翻譯都在 `titles` 裡（plan §4.3）。"""
        info = parse_release("[LoliHouse] Sousou no Frieren - 01 [WebRip 1080p HEVC-10bit].mkv")
        frieren = media(209867, "Frieren: Beyond Journey's End", titles=("Sousou no Frieren",))

        found = match_media(info, [media(1, "Dungeon Meshi"), frieren])

        assert found is not None and found.media.tmdb_id == 209867

    def test_a_cjk_title_inside_the_release_name_counts(self) -> None:
        """中文標題只出現在方括號堆裡，guessit 一個字都認不出來——比對比的是整行原文。"""
        info = parse_release("【楓葉字幕組】[寵物小精靈 / 寶可夢 地平線][135][繁體][1080P][MP4]")
        pokemon = media(220150, "Pokémon Horizons", titles=("Pokémon Horizons", "寶可夢 地平線"))

        found = match_media(info, [media(1, "Dungeon Meshi"), pokemon])

        assert found is not None and found.media.tmdb_id == 220150

    def test_the_year_breaks_a_tie(self) -> None:
        """同名重拍：`GTO 2026` 不是 1998 年那一部（brief §6.4 的年份加權）。"""
        info = parse_release("GTO.2026.EP08.1080p.NF.WEB-DL.AAC2.0.H.264-MagicStar.mkv")

        found = match_media(info, [media(1, "GTO", year=1998), media(2, "GTO", year=2026)])

        assert found is not None and found.media.tmdb_id == 2

    def test_a_release_of_something_else_matches_nothing(self) -> None:
        info = parse_release("The.Bear.S03E01.1080p.WEB.H264-SuccessfulCrab.mkv")

        assert match_media(info, [media(1, "Fleabag"), media(2, "Squid Game")]) is None

    def test_an_empty_pool_matches_nothing(self) -> None:
        info = parse_release("The.Bear.S03E01.1080p.WEB.H264-SuccessfulCrab.mkv")

        assert match_media(info, []) is None

    def test_a_short_word_does_not_match_by_containment(self) -> None:
        """`Up` 出現在半數的發佈名裡。太短的標題只認完全相同。"""
        info = parse_release("[Up to 21°C] 鬼灭之刃 柱训练篇 - 08 [1080p].mp4")

        assert match_media(info, [media(1, "Up", year=2009)]) is None

    def test_most_of_the_words_is_enough(self) -> None:
        """字幕組用羅馬字而 TMDB 只收官方譯名——真實語料（進擊的巨人劇場版）。"""
        info = parse_release("Shingeki no Kyojin Movie The Last Attack 2024-[1080p][BDRIP].mkv")
        titan = media(1333100, "Attack on Titan: THE LAST ATTACK", year=2024)

        found = match_media(info, [titan])

        assert found is not None
        assert any("carries most of" in reason for reason in found.reasons)

    def test_it_says_why(self) -> None:
        info = parse_release("The.Bear.S03E01.1080p.WEB.H264-SuccessfulCrab.mkv")

        found = match_media(info, [media(2, "The Bear", year=2022)])

        assert found is not None and found.reasons
