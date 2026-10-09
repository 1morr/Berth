"""標題比對（plan §4.1、§4.3，brief §6.4 第 2 點）。

Job 帶了 Media 時這一層只是覆核；RSS 與重新入庫時它是**唯一**認得出作品的辦法。
比的是正規化之後的字，年份加權——同名不同年的重拍太多了。
"""

from __future__ import annotations

from datetime import date

import pytest

from berth.domain import MediaKind, MediaSnapshot, ReasonCode, SeasonSnapshot, why
from berth.parser import (
    fits,
    match_media,
    mentions,
    normalize_title,
    parse_release,
    spell_ampersand,
)


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
        assert (
            why(ReasonCode.TITLE_PARTIAL, title="Attack on Titan: THE LAST ATTACK") in found.reasons
        )

    def test_it_says_why(self) -> None:
        info = parse_release("The.Bear.S03E01.1080p.WEB.H264-SuccessfulCrab.mkv")

        found = match_media(info, [media(2, "The Bear", year=2022)])

        assert found is not None and found.reasons


def movie(title_en: str, year: int | None) -> MediaSnapshot:
    return MediaSnapshot(
        tmdb_id=10331,
        kind=MediaKind.MOVIE,
        title=title_en,
        title_en=title_en,
        title_original=title_en,
        year=year,
        titles=(title_en,),
    )


def show(title_en: str, year: int, *season_years: int) -> MediaSnapshot:
    return MediaSnapshot(
        tmdb_id=57243,
        kind=MediaKind.TV,
        title=title_en,
        title_en=title_en,
        title_original=title_en,
        year=year,
        titles=(title_en,),
        seasons=tuple(
            SeasonSnapshot(season_number=number, air_date=date(aired, 3, 1))
            for number, aired in enumerate(season_years, start=1)
        ),
    )


class TestFits:
    """名字對上之後的第二道粗篩：年份與「這是電影」（M4 票 49，審計 S6）。"""

    NIGHT = movie("Night of the Living Dead", 1968)

    @pytest.mark.parametrize(
        "name",
        [
            "Night of the Living Dead (1968) [BluRay] [720p] [YTS.AM]",
            "Night.of.the.Living.Dead.1969.1080p.BluRay",  # 差一年：影展與上映跨年
            "Night of the Living Dead 1080p BluRay x264",  # 沒寫年份照收（Radarr 同）
            "Night of the Living Dead 1968 4K Restoration 2018 2160p",  # 有一個對上就算
        ],
    )
    def test_a_movie_keeps_its_own_year_and_releases_without_one(self, name: str) -> None:
        assert fits(name, self.NIGHT)

    @pytest.mark.parametrize(
        "name",
        [
            "Night of the Living Dead 1990 1080p BluRay x264",
            "Night.of.the.Living.Dead.3D.2006.720p",
        ],
    )
    def test_a_remake_years_away_does_not_fit(self, name: str) -> None:
        assert not fits(name, self.NIGHT)

    @pytest.mark.parametrize(
        "name",
        [
            "Below Deck Down Under S04E02 Night of the Living Dead 1080p",
            "Night of the Living Dead S01 1080p WEB",
            "Night of the Living Dead Season 2 720p",
            "[字幕組] Night of the Living Dead 第2季 [1080p]",
            "[字幕組] Night of the Living Dead 第05話 [1080p]",
            "Night.of.the.Living.Dead.S01E01E02.1080p",  # 一個檔兩集
            "Night.of.the.Living.Dead.S01E05v2.1080p",  # 修正版
            "Night of the Living Dead 2nd Season 720p",
            "Night of the Living Dead 1x05 HDTV",
            "[Group] Night of the Living Dead EP05 [1080p]",
        ],
    )
    def test_a_movie_drops_releases_that_read_as_episodes(self, name: str) -> None:
        assert not fits(name, self.NIGHT)

    @pytest.mark.parametrize(
        "name",
        [
            "[SubsPlease] Tsuki to Laika to Nosferatu - 05 (1080p) [8A1C3B2F].mkv",
            "[ASW] Tsuki to Laika to Nosferatu - 07v2 [1080p HEVC x265 10Bit][AAC]",
            "[Erai-raws] Tsuki to Laika to Nosferatu - 01 ~ 12 [1080p][Multiple Subtitle]",
            "[Group] Tsuki to Laika to Nosferatu [01-12][BDRip 1080p]",
            "【喵萌奶茶屋】★10月新番★[月與萊卡與吸血公主 / Tsuki to Laika to Nosferatu][03][1080p]",
            "[Group] Tsuki to Laika to Nosferatu 【12】[1080p]",
            # 2026-10-10 實跑（The Pirate Bay + Mikan）時還留在主表的寫法（中文片名截掉）：
            "[千夏字幕组][月亮与莱卡与吸血公主_Tsuki to Laika to Nosferatu][第01-12话][BDRip]",
            "【幻樱字幕组】【合集】【Tsuki to Laika to Nosferatu】【01-12 END】【GB_MP4】",
            "【幻樱字幕组】【10月新番】【Tsuki to Laika to Nosferatu】【12 END】【GB_MP4】",
            "[动漫国字幕组&LoliHouse] Tsuki to Laika to Nosferatu [01-12合集][WebRip 1080p]",
        ],
    )
    def test_a_movie_drops_a_namesake_shows_episodes(self, name: str) -> None:
        """審計 S3：搜《Nosferatu》(1922) 時同名動畫的各集進了主表——字幕組的集號寫成
        `- 05`、`[05]`、`[01-12]`，不是 `S01E05`（M4 票 69）。"""
        assert not fits(name, movie("Nosferatu", 1922))

    @pytest.mark.parametrize(
        "name",
        [
            "Nosferatu (1922) [720p] [BluRay] [YTS.MX]",
            "Nosferatu - Eine Symphonie des Grauens (1922) 1080p BluRay",
            "Nosferatu - 1922 - 4K Restoration 2160p",  # 年份不是集號
            "[Group] Nosferatu [1922][BDRip 1080p]",
            "Nosferatu 1922 - 4K Restoration [1080p] [5.1]",
            "Nosferatu 1922 1080p BluRay AAC - 2.0 x264",  # 聲道不是集號
            "Nosferatu (1922) - 2 Disc Set 1080p",  # 一位數不是字幕組的集號（code-review）
            "Nosferatu 1922 [BluRay] [3] 1080p",
        ],
    )
    def test_dashes_and_brackets_around_a_year_still_fit_the_movie(self, name: str) -> None:
        assert fits(name, movie("Nosferatu", 1922))

    def test_a_show_keeps_the_fansub_episode_numbers(self) -> None:
        laika = show("Tsuki to Laika to Nosferatu", 2021, 2021)

        assert fits("[SubsPlease] Tsuki to Laika to Nosferatu - 05 (1080p)", laika)
        assert fits("[Group] Tsuki to Laika to Nosferatu [01-12][BDRip 1080p]", laika)

    def test_a_year_that_is_part_of_the_title_is_not_a_release_year(self) -> None:
        """`Blade Runner 2049`（2017）：片名裡的 2049 不是年份。"""
        blade = movie("Blade Runner 2049", 2017)

        assert fits("Blade.Runner.2049.2017.2160p.UHD.BluRay", blade)
        assert fits("Blade Runner 2049 1080p WEB", blade)

    @pytest.mark.parametrize(
        "name",
        [
            "Night of the Living Dead 1968 1920x1080 x264",  # 解析度不是 `NxNN`
            "Night of the Living Dead 1968 Subs EPUB",  # `S` / `EP` 後面要接數字
            "Night of the Living Dead 1968 DDP5.1 Atmos",
        ],
    )
    def test_codec_and_resolution_tokens_do_not_read_as_episodes(self, name: str) -> None:
        assert fits(name, self.NIGHT)

    def test_resolutions_are_not_years(self) -> None:
        assert fits("Night of the Living Dead 1920x1080 2160p", self.NIGHT)

    def test_a_movie_without_a_year_on_tmdb_keeps_everything_but_episodes(self) -> None:
        unknown = movie("Night of the Living Dead", None)

        assert fits("Night of the Living Dead 1990 1080p", unknown)
        assert not fits("Night of the Living Dead S01E01", unknown)

    def test_a_show_keeps_episodes_and_the_years_it_aired(self) -> None:
        """劇集照常收季集；年份看整段播出期間，不只首播年（Sonarr 不以年份拒絕）。"""
        bear = show("The Bear", 2022, 2022, 2023, 2024)

        assert fits("The.Bear.S03E01.1080p.WEB", bear)
        assert fits("The Bear 2024 S03 1080p", bear)
        assert fits("The Bear 2025 S04 1080p", bear)  # 新的一季還沒進快照
        assert fits("The Bear Movie 1080p", bear)  # 沒有季集也照收：`Movie` 可能是 S00

    def test_a_show_drops_a_namesake_from_another_era(self) -> None:
        """《Doctor Who》1963 與 2005 是兩部作品，搜 2005 那一部時 1963 的不收。"""
        who = show("Doctor Who", 2005, 2005, 2006)

        assert not fits("Doctor Who 1963 S01E01 DVDRip", who)


class TestAmpersand:
    """片名裡的 `&` 與 `and` 是同一個字（M4 票 69）：Sonarr / Radarr 送查詢前把 `&` 換成 `and`
    （`GetCleanSceneTitle`），比對時兩者都清掉（`CleanSeriesTitle`）。發佈名照 scene 的寫法是
    `Law.and.Order`，TMDB 的名字是 `Law & Order`。"""

    LAW = movie("Law & Order", None)

    @pytest.mark.parametrize(
        ("title", "spelled"),
        [
            ("Law & Order", "Law and Order"),
            ("Law&Order", "Law and Order"),
            ("Law & Order: Special Victims Unit", "Law and Order: Special Victims Unit"),
            ("SPY x FAMILY", "SPY x FAMILY"),
            ("法網遊龍 & 特案組", "法網遊龍 & 特案組"),  # 中文名不換
        ],
    )
    def test_the_ampersand_is_spelled_out_in_latin_titles(self, title: str, spelled: str) -> None:
        assert spell_ampersand(title) == spelled

    @pytest.mark.parametrize(
        "name",
        ["Law.and.Order.S20E01.1080p.WEB", "Law & Order S20E01 1080p", "Law.Order.S20E01"],
    )
    def test_either_spelling_names_the_work(self, name: str) -> None:
        assert mentions(name, self.LAW)

    def test_the_spelled_out_release_is_an_exact_match(self) -> None:
        found = match_media(parse_release("Law.and.Order.S20E01.1080p.WEB"), [self.LAW])

        assert found is not None and found.score >= 1.0

    def test_and_is_not_dropped_from_titles_without_an_ampersand(self) -> None:
        """只把 `&` 寫開，不學 Sonarr 把每個 `and` 都刪掉：`Pride and Prejudice` 的發佈名
        照舊要寫出 `and`。"""
        pride = movie("Pride and Prejudice", 2005)

        assert not mentions("Pride.Prejudice.2005.1080p", pride)
