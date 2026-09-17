"""發佈名解析與 tag 渲染（brief §6.3、§6.8、plan §4.1、§4.2）。

輸入抄自真實發佈。`parse_release` 的職責是**把名字裡有的東西讀出來**，不是猜——
所以「沒說就留空」的那幾條與讀對的那幾條一樣重要。
"""

from __future__ import annotations

from datetime import date

import pytest

from berth.domain import Lang, ReleaseKind, Source, SpecialKind, SubtitleKind, Tags
from berth.parser import merge_release, parse_release, tags_of


class TestAnimeEpisodePatterns:
    """plan §4.1 點名的六種動漫集號寫法。"""

    def test_dash_number(self) -> None:
        info = parse_release("[LoliHouse] Vampire Dormitory - 07 [WebRip 1080p HEVC-10bit AAC].mkv")

        assert (info.season, info.episode) == (None, 7)

    def test_bracketed_number(self) -> None:
        info = parse_release("[Airota][Kamiina Botan][03][1080p AVC AAC][CHT].mp4")

        assert (info.season, info.episode) == (None, 3)

    def test_bracketed_number_next_to_a_season(self) -> None:
        """guessit 把 `Season 3 [04]` 讀成 `season: [3, 4]`——第二個其實是集號。"""
        info = parse_release("[KitaujiSub] Mushoku Tensei Season 3 [04][WebRip][CHS&CHT].mkv")

        assert (info.season, info.episode) == (3, 4)

    def test_version_suffix(self) -> None:
        info = parse_release(
            "[hyakuhuyu&LoliHouse] Re Zero kara Hajimeru Isekai Seikatsu - 81 v2 "
            "[WebRip 1080p HEVC-10bit AAC ASSx2].mkv"
        )

        assert (info.episode, info.version) == (81, 2)

    def test_bracketed_version_suffix(self) -> None:
        """`[01v2]`：版本號黏在集號後面，兩個都要讀出來。"""
        info = parse_release("[Group][Show][01v2][1080P][CHT].mkv")

        assert (info.episode, info.version) == (1, 2)

    def test_episode_without_a_season(self) -> None:
        """`EP01` / `E01`：韓劇與日劇常見，多數是單季（brief §6.4）。"""
        info = parse_release("True.Beauty.2020.EP07.HD1080P.X264.AAC.Korean.CHS.mp4")

        assert (info.season, info.episode) == (None, 7)

    @pytest.mark.parametrize(
        ("name", "episode"),
        [
            ("[NaN-Raws]进击的巨人_The_Final_Season[28][1080P].mp4", 28),
            ("[ANi]进击的巨人 The Final Season[28][1080P][Baha][WEB-DL][AAC AVC]", 28),
            (
                "[桜都字幕组] 进击的巨人 The Final Season / Shingeki no Kyojin The Final Season "
                "[75][1080p][简日内嵌]",
                75,
            ),
        ],
    )
    def test_a_bracket_right_after_the_word_season_is_an_episode(
        self, name: str, episode: int
    ) -> None:
        """`The_Final_Season[28]`：guessit 把那個 28 讀成季號，但它是集號（研究 §6.1）。

        `Season` 與方括號之間隔一格空白（`Season [75]`）也一樣誤讀；`Season 3 [04]` 中間
        有自己的季號，guessit 才分得開。
        """
        info = parse_release(name)

        assert (info.season, info.episode) == (None, episode)

    @pytest.mark.parametrize(
        ("name", "season", "episode"),
        [
            (
                "[桜都字幕组] 无职转生～到了异世界就拿出真本事～ S2 / Mushoku Tensei S2 "
                "[02][1080p][简繁内封]",
                2,
                2,
            ),
            (
                "[诸神字幕组][进击的巨人][Attack on Titan S2][02][简繁日双语字幕][1080P][HEVC MKV]",
                2,
                2,
            ),
            (
                "[织梦字幕组] 鬼灭之刃 柱训练篇 Kimetsu no Yaiba S05 [05] "
                "[HEVC-10bit 1080P] [繁日双语]",
                5,
                5,
            ),
            (
                "[爱恋&漫猫字幕组][7月新番][Re:从零开始的异世界生活 S2]"
                "[Re:Zero kara Hajimeru Isekai Seikatsu S2][02][1080p][AVC][繁中]",
                2,
                2,
            ),
        ],
    )
    def test_a_season_that_happens_to_equal_the_bracketed_episode_stays(
        self, name: str, season: int, episode: int
    ) -> None:
        """`S2 [02]`：兩個數字剛好相等，但 `S2` 是自己一格的季號，不是被 guessit 讀歪的集號。

        票 01 的 Mikan 標題裡這種寫法有 21 個（M1 票 14f），TMDB 併成一季的 Re:Zero 會因此自動入錯。
        """
        info = parse_release(name)

        assert (info.season, info.episode) == (season, episode)

    def test_a_cour_marker_is_read_next_to_the_season(self) -> None:
        """`Season 3 Part 2 - 01`：季號 3、cour 2、集號 1，三個數字互不覆蓋（plan §4.4）。"""
        info = parse_release(
            "[Erai-raws] Shingeki no Kyojin Season 3 Part 2 - 01 [1080p][Multiple Subtitle].mkv"
        )

        assert (info.season, info.part, info.episode) == (3, 2, 1)

    def test_a_chinese_cour_marker_says_the_same_thing(self) -> None:
        info = parse_release("[星空字幕组][进击的巨人 第三季 第二部分][01-10 Fin][合集]")

        assert (info.season, info.part, info.episode, info.episode_end) == (3, 2, 1, 10)

    def test_a_release_without_a_cour_marker_says_nothing(self) -> None:
        assert parse_release("The.Bear.S03E01.1080p.WEB.H264-SuccessfulCrab.mkv").part is None

    def test_a_year_is_not_a_season(self) -> None:
        """guessit 對 `GTO.2026.EP08` 同時回 year 與 season 2026。"""
        info = parse_release("GTO.2026.EP08.1080p.NF.WEB-DL.AAC2.0.H.264-MagicStar.mkv")

        assert (info.season, info.episode, info.year) == (None, 8, 2026)

    def test_a_range(self) -> None:
        info = parse_release("【楓葉字幕組】[寶可夢 地平線][135-136][繁體][1080P][MP4]")

        assert (info.episode, info.episode_end) == (135, 136)
        assert info.release_kind is ReleaseKind.RANGE

    def test_a_chinese_episode_marker(self) -> None:
        info = parse_release(
            "【极影字幕社】★10月新番 龙珠大魔/Dragon Ball Daima 第01话 GB 1080P MP4"
        )

        assert (info.season, info.episode) == (None, 1)

    def test_explicit_season_and_episode(self) -> None:
        info = parse_release("Sousou no Frieren 2023 S01E05-[1080p][BDRIP][x265.OPUS].mkv")

        assert (info.season, info.episode) == (1, 5)

    def test_a_specials_season(self) -> None:
        info = parse_release("Sousou no Frieren 2023 S00E03-[1080p][BDRIP][x265.OPUS].mkv")

        assert (info.season, info.episode) == (0, 3)


class TestReleaseKind:
    def test_a_single_episode(self) -> None:
        assert (
            parse_release("[Airota][Show][03][1080p][CHT].mp4").release_kind is ReleaseKind.SINGLE
        )

    def test_a_collection_marker_wins_over_a_range(self) -> None:
        info = parse_release("[千夏字幕組][上伊那牡丹][第01-12話][1080p_AVC][繁體][合集]")

        assert info.release_kind is ReleaseKind.COLLECTION


class TestFields:
    @pytest.mark.parametrize(
        ("name", "source"),
        [
            ("Sousou no Frieren 2023 S01E05-[1080p][BDRIP][x265.OPUS].mkv", Source.BD),
            ("Fleabag (2016) - S01E03 - Episode 3 (1080p BluRay x265 RZeroX).mkv", Source.BD),
            ("The.Bear.S03E04.1080p.WEB.H264-SuccessfulCrab.mkv", Source.WEB),
            (
                "The.Lord.of.the.Rings.The.Two.Towers.2002.EXTENDED.1080p.BluRay.REMUX.AVC.mkv",
                Source.REMUX,
            ),
            ("Show.S01E01.1080p.HDTV.x264-GROUP.mkv", Source.HDTV),
            ("Show.S01E01.DVDRip.XviD-GROUP.avi", Source.DVD),
        ],
    )
    def test_source_tokens(self, name: str, source: Source) -> None:
        assert parse_release(name).source is source

    def test_a_release_without_a_source_says_nothing(self) -> None:
        assert parse_release("The.Librarians.S02E05.1080p.x265-ELiTE.mkv").source is None

    def test_a_resolution_guessit_does_not_know(self) -> None:
        """韓劇常見的 `HD1080P`。"""
        assert parse_release("True.Beauty.2020.EP07.HD1080P.X264.mp4").resolution == "1080p"

    def test_a_pixel_resolution(self) -> None:
        info = parse_release("[jibaketa]Kamen Rider Zeztz - 50 END (WEB 1920x1080 AVC).mkv")

        assert info.resolution == "1080p"

    def test_the_edition(self) -> None:
        info = parse_release("Psycho (1960) Uncut Turbine Medien (1080p BluRay x265 afm72).mkv")

        assert info.edition == "Uncut"

    def test_a_chinese_edition_marker(self) -> None:
        """`重製` 在 brief §6.3 的詞典裡，但 guessit 只認得英文的 `Remastered`。"""
        info = parse_release("[Group][某作品 重製版][01][1080P][繁體].mkv")

        assert info.edition == "Remaster"

    def test_a_trailing_bracketed_group_is_copied_verbatim(self) -> None:
        """guessit 把 `-[y2flix.cc]` 切成 `y2flix` 並把 `cc` 讀成 Criterion Collection。"""
        info = parse_release("Squid.Game.S02E05.ENG.1080p.NF.x264-[y2flix.cc].mp4")

        assert info.group == "y2flix.cc"
        assert info.edition == ""

    def test_a_subtitle_token_is_not_a_group(self) -> None:
        """真實語料：`…AAC.Korean.CHS.mp4` 被 guessit 讀成 release_group `CHS`。"""
        info = parse_release("True.Beauty.2020.EP07.HD1080P.X264.AAC.Korean.CHS.mp4")

        assert info.group == ""
        assert info.subtitle_langs == (Lang.CHS,)

    def test_the_cjk_group_wins(self) -> None:
        info = parse_release("[Airota][Kamiina Botan][03][1080p AVC AAC][CHT].mp4")

        assert info.group == "Airota"

    def test_it_keeps_the_raw_title(self) -> None:
        name = "[Airota][Kamiina Botan][03][1080p AVC AAC][CHT].mp4"

        assert parse_release(name).raw_title == name


class TestAirDate:
    """檔名裡的播出日。只有集號時它是換算對不對的證據（brief §6.4、M1 票 14d）。"""

    def test_a_korean_broadcast_date_puts_the_year_first(self) -> None:
        """韓國電視台的 `YYMMDD`：guessit 預設把 `150524` 讀成 2024-05-15（M1 票 14c 實測）。"""
        info = parse_release("The.Return.of.Superman.E079.150524.HDTV.H264.720p-LIMO.avi")

        assert info.air_date == date(2015, 5, 24)

    def test_a_four_digit_year_reads_as_written(self) -> None:
        info = parse_release("Home.and.Away.Episode.8214.2024-02-29.Thu.720p.WEB-DL.H.264-bill.mkv")

        assert info.air_date == date(2024, 2, 29)

    def test_a_release_without_a_date_says_nothing(self) -> None:
        info = parse_release("[SubsPlease] Spy x Family - 05 (1080p) [547FDE9F].mkv")

        assert info.air_date is None


class TestMerge:
    """檔名說了算，torrent 名補空缺。"""

    def test_the_torrent_name_fills_the_gaps(self) -> None:
        """真實語料：字幕語言只寫在 torrent 名上（`简繁外挂`），集號只寫在檔名上。"""
        torrent = parse_release(
            "[DBD-Raws][不死者之王 第二季/Overlord Ⅱ][01-13TV全集+SP]"
            "[1080P][BDRip][简繁外挂][FLAC][MKV]"
        )
        file = parse_release(
            "[DBD-Raws][不死者之王 第二季][01][1080P][BDRip][HEVC-10bit][FLAC].mkv"
        )

        merged = merge_release(file, torrent)

        assert merged.episode == 1
        assert merged.subtitle_langs == (Lang.CHS, Lang.CHT)
        assert merged.subtitle_kind is SubtitleKind.EXTERNAL

    def test_the_file_wins_where_both_speak(self) -> None:
        torrent = parse_release(
            "[7³ACG] Sousou no Frieren S01 | 01-28+SPx11 [简繁字幕] BDrip 1080p"
        )
        file = parse_release("Sousou no Frieren 2023 S01E05-[1080p][BDRIP][x265.OPUS].mkv")

        merged = merge_release(file, torrent)

        assert (merged.season, merged.episode, merged.episode_end) == (1, 5, None)

    def test_a_pack_date_does_not_become_the_air_date_of_a_numbered_file(self) -> None:
        """播出日是某一集的，跟著集號走（與 `episode_end` 同一個道理）。"""
        torrent = parse_release("Home.and.Away.Week.Pack.2024-02-26.720p.WEB-DL.H.264-bill")
        file = parse_release("Home.and.Away.Episode.8215.720p.WEB-DL.H.264-bill.mkv")

        assert merge_release(file, torrent).air_date is None

    def test_the_torrent_date_comes_along_with_the_torrent_episode(self) -> None:
        """檔名什麼都沒說時，集號與播出日一起從 torrent 名來。"""
        torrent = parse_release("Home.and.Away.Episode.8214.2024-02-29.Thu.720p.WEB-DL.H")
        file = parse_release("bill-haa-720p.mkv")

        merged = merge_release(file, torrent)

        assert (merged.episode, merged.air_date) == (8214, date(2024, 2, 29))

    def test_a_pack_that_contains_specials_does_not_make_every_file_one(self) -> None:
        """`[01-13TV全集+SP]` 說的是這一包裡有特典，不是這個檔案是特典（真實語料）。"""
        torrent = parse_release(
            "[DBD-Raws][不死者之王 第二季/Overlord Ⅱ][01-13TV全集+SP][1080P][BDRip][简繁外挂]"
        )
        file = parse_release("[DBD-Raws][不死者之王 第二季][01][1080P][BDRip][FLAC].mkv")

        assert torrent.special_kind is SpecialKind.SP
        assert merge_release(file, torrent).special_kind is None

    def test_it_keeps_the_file_as_the_raw_title(self) -> None:
        torrent = parse_release("[7³ACG] Sousou no Frieren S01 | 01-28 [简繁字幕] BDrip 1080p")
        file = parse_release("Sousou no Frieren 2023 S01E05-[1080p][BDRIP].mkv")

        assert merge_release(file, torrent).raw_title.startswith("Sousou no Frieren 2023 S01E05")


class TestTagsRender:
    """brief §6.8 的順序與 token。"""

    def test_the_full_order(self) -> None:
        tags = Tags(
            source=Source.BD,
            resolution="1080p",
            subs=(Lang.CHT, Lang.JP),
            group="Sakurato",
            version="v2",
        )

        assert tags.render() == "[BD][1080p][CHT+JP][Sakurato][v2]"

    def test_hardsub_sits_after_the_languages(self) -> None:
        tags = Tags(
            source=Source.WEB,
            resolution="1080p",
            subs=(Lang.CHS,),
            hardsub=True,
            group="Lilith-Raws",
        )

        assert tags.render() == "[WEB][1080p][CHS][Hardsub][Lilith-Raws]"

    def test_missing_fields_are_dropped(self) -> None:
        assert Tags(resolution="1080p", group="ELiTE").render() == "[1080p][ELiTE]"

    def test_an_empty_tag_set_renders_to_nothing(self) -> None:
        assert Tags().render() == ""

    def test_the_edition_comes_last(self) -> None:
        tags = Tags(source=Source.BD, resolution="1080p", group="afm72", edition="Uncut")

        assert tags.render() == "[BD][1080p][afm72][Uncut]"

    @pytest.mark.parametrize(
        ("subs", "rendered"),
        [
            ((Lang.CHT,), "CHT"),
            ((Lang.JP, Lang.CHT), "CHT+JP"),
            ((Lang.CHT, Lang.CHS), "CHS+CHT"),
            ((Lang.JP, Lang.CHT, Lang.CHS), "CHS+CHT+JP"),
            ((Lang.EN, Lang.JP, Lang.CHT, Lang.CHS), "CHS+CHT+JP+EN"),
        ],
    )
    def test_languages_are_sorted_and_joined_with_plus(
        self, subs: tuple[Lang, ...], rendered: str
    ) -> None:
        """`CHS < CHT < JP < EN`，以 `+` 連接（brief §6.8）。"""
        assert Tags(subs=subs).render() == f"[{rendered}]"


class TestTagsOf:
    def test_it_takes_the_fields_that_go_into_the_filename(self) -> None:
        info = parse_release(
            "[hyakuhuyu&LoliHouse] Re Zero - 81 v2 [WebRip 1080p HEVC-10bit AAC][简繁内封字幕].mkv"
        )

        assert tags_of(info) == Tags(
            source=Source.WEB,
            resolution="1080p",
            subs=(Lang.CHS, Lang.CHT),
            group="hyakuhuyu&LoliHouse",
            version="v2",
        )

    def test_a_first_version_carries_no_version_token(self) -> None:
        """`v1` 不是一個版本，是「沒有重製過」（brief §6.8）。"""
        info = parse_release("[Group] Show - 01 v1 [WebRip 1080p].mkv")

        assert tags_of(info).version == ""

    def test_hardsub_is_the_only_subtitle_kind_that_shows(self) -> None:
        hard = parse_release("[Group] Show - 08 - [繁日内嵌][AVC 8bit 1080P].mkv")
        soft = parse_release("[Group] Show - 08 - [繁日内封][AVC 8bit 1080P].mkv")

        assert tags_of(hard).hardsub is True
        assert tags_of(soft).hardsub is False
