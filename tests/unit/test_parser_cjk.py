"""中文字幕組命名的正規化與欄位抽取（brief §6.3、§20.4、plan §4.1）。

每一條的輸入都抄自真實發佈（語料在 `tests/fixtures/parser/`，其餘標了來源）。手寫的
假檔名只會證明規則與自己的想像一致——而這一層存在的理由正是想像會出錯（M1 票 01 的
兩個羅馬數字寫法就是這樣被漏掉的）。
"""

from __future__ import annotations

import pytest

from berth.domain import Lang, SpecialKind, SubtitleKind
from berth.parser import normalize_cjk


class TestSubtitleLanguages:
    """brief §6.8 的對應表：繁體 / BIG5 / TC → CHT，简体 / GB / SC → CHS，JPTC → CHT+JP…"""

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("[Airota][Show][01][1080p AVC AAC][CHT].mp4", {Lang.CHT}),
            ("【楓葉字幕組】[寶可夢][135][繁體][1080P][MP4]", {Lang.CHT}),
            ("[FYSub][Show][135][1080P][BIG5].mp4", {Lang.CHT}),
            ("[KTXP][Dragon Ball Daima][01][GB][1080p].mp4", {Lang.CHS}),
            ("【极影字幕社】龙珠大魔 第01话 GB 1080P MP4", {Lang.CHS}),
            ("[KitaujiSub] Show [04][WebRip][CHS&CHT].mkv", {Lang.CHS, Lang.CHT}),
            ("[LoliHouse] Show - 81 [WebRip 1080p][简繁内封字幕]", {Lang.CHS, Lang.CHT}),
            ("[Group] Show - 01 [简日双语]", {Lang.CHS, Lang.JP}),
            ("[Group] Show - 01 [繁日雙語]", {Lang.CHT, Lang.JP}),
            ("[DHR][Little Busters!][04][JPN&BIG5][720P]", {Lang.CHT, Lang.JP}),
            ("[Group] Show - 01 [JPTC][1080P]", {Lang.CHT, Lang.JP}),
            ("[Group] Show - 01 [JPSC][1080P]", {Lang.CHS, Lang.JP}),
            ("[绿茶字幕组] Show [07][WebRip][1080p][简繁日内封]", {Lang.CHS, Lang.CHT, Lang.JP}),
            (
                "[MagicStar] GTO 2026 EP08 [WEBDL]【附官方日英简繁中字幕】",
                {Lang.CHS, Lang.CHT, Lang.JP, Lang.EN},
            ),
            ("Squid.Game.S02.1080p.NF.WEB-DL.x264.ESubs.MP4", {Lang.EN}),
        ],
    )
    def test_it_reads_the_language_tokens(self, name: str, expected: set[Lang]) -> None:
        assert set(normalize_cjk(name)[1].subs) == expected

    def test_a_size_is_not_a_language(self) -> None:
        """`[5.8GB]` 裡的 `GB` 不是简体——真實語料踩過（squid-game-s02-y2flix）。"""
        assert normalize_cjk("Squid.Game.S02.COMPLETE.[5.8GB].MP4.S02.FULL")[1].subs == frozenset()

    def test_a_release_without_language_tokens_says_nothing(self) -> None:
        assert normalize_cjk("The.Bear.S03E01.1080p.WEB.H264-SuccessfulCrab.mkv")[1].subs == (
            frozenset()
        )


class TestSubtitleKind:
    """內嵌 / 內封 / 外掛（brief §6.3）。只有內嵌會進檔名（§6.8 的 `Hardsub`）。"""

    def test_hardsub(self) -> None:
        hints = normalize_cjk("[三明治摆烂组] Show - 08 - [繁日内嵌][AVC 8bit 1080P]")[1]

        assert hints.hardsub is True
        assert hints.subtitle_kind is SubtitleKind.HARDSUB

    def test_softsub(self) -> None:
        hints = normalize_cjk("[LoliHouse] Show - 81 v2 [WebRip 1080p][简繁内封字幕]")[1]

        assert hints.hardsub is False
        assert hints.subtitle_kind is SubtitleKind.SOFTSUB

    def test_external(self) -> None:
        hints = normalize_cjk("[DBD-Raws][不死者之王 第二季][01-13TV全集+SP][简繁外挂]")[1]

        assert hints.hardsub is False
        assert hints.subtitle_kind is SubtitleKind.EXTERNAL

    def test_a_release_that_does_not_say_leaves_it_unknown(self) -> None:
        """不猜（brief §6.3）：`[繁體]` 只說了語言，沒說字幕怎麼放。"""
        hints = normalize_cjk("【楓葉字幕組】[寶可夢][135][繁體][1080P][MP4]")[1]

        assert hints.hardsub is None
        assert hints.subtitle_kind is SubtitleKind.UNKNOWN


class TestSeason:
    """季號。**M1 票 01 量到的兩個寫法**在這裡（`docs/research/anime-episode-source.md` §6.1）。"""

    @pytest.mark.parametrize(
        ("name", "season"),
        [
            ("[DBD-Raws][不死者之王 第二季][01][1080P]", 2),
            ("[愛戀字幕社][無職轉生 第三季][10][1080P][BIG5]", 3),
            ("[Group] 進擊的巨人 第3季 [01][1080P]", 3),
            ("[Group] 某作品 第二期 [01][1080P]", 2),
        ],
    )
    def test_chinese_season_markers(self, name: str, season: int) -> None:
        assert normalize_cjk(name)[1].season == season

    @pytest.mark.parametrize(
        ("name", "season"),
        [
            ("[爱恋字幕社&漫猫字幕社][无职转生Ⅱ ～到了异世界就拿出真本事～][03]", 2),
            ("[黒ネズミたち] 无职转生 Ⅲ ～到了异世界就拿出真本事～ - 03", 3),
            ("[DBD-Raws][不死者之王/Overlord Ⅳ][01][1080P]", 4),
        ],
    )
    def test_full_width_roman_numerals(self, name: str, season: int) -> None:
        """全形羅馬數字（U+2160 起）。漏掉這一種會把整輪播出錯置成第一季。"""
        assert normalize_cjk(name)[1].season == season

    @pytest.mark.parametrize(
        ("name", "season"),
        [
            ("[Group][Mushoku Tensei II]", 2),
            ("[愛戀字幕社][Mushoku Tensei III: Isekai Ittara Honki Dasu][10][1080P]", 3),
            ("[Group] Overlord IV - 01 [1080p]", 4),
        ],
    )
    def test_half_width_roman_numerals_do_not_need_spaces_around_them(
        self, name: str, season: int
    ) -> None:
        """`Mushoku Tensei II]` 的 `II` 右邊是 `]` 不是空白——要求空白收邊就會漏掉。"""
        assert normalize_cjk(name)[1].season == season

    def test_roman_numerals_leave_the_title_comparable(self) -> None:
        """季號從標題裡拿掉，`Mushoku Tensei III` 與 `Mushoku Tensei S3` 才對得起來。"""
        cleaned, _ = normalize_cjk("[Group][Mushoku Tensei III: Isekai Ittara Honki Dasu][10]")

        assert "III" not in cleaned

    def test_single_letter_roman_numerals_are_not_season_markers(self) -> None:
        """`I` / `V` / `X` 誤判太貴：`Vol` 與 `X` 這種字到處都是。"""
        assert normalize_cjk("[Group] Show V - 01 [1080p]")[1].season is None

    def test_a_release_without_a_season_says_nothing(self) -> None:
        assert normalize_cjk("[Airota][Show][01][1080p AVC AAC][CHT].mp4")[1].season is None


class TestPart:
    """`第二部分` 是 cour，不是季（plan §4.4）。

    這是量測裡**唯一「檔名有季號卻還是三家一起錯」**的一類
    （`docs/research/anime-episode-source.md` §6.1.1）。
    """

    @pytest.mark.parametrize(
        ("name", "part"),
        [
            ("[星空字幕组][进击的巨人 第三季 第二部分][01-10 Fin][合集]", 2),
            ("[Group] 某作品 第2部分 [01]", 2),
        ],
    )
    def test_chinese_part_markers(self, name: str, part: int) -> None:
        assert normalize_cjk(name)[1].part == part

    def test_a_season_and_a_part_are_two_different_numbers(self) -> None:
        hints = normalize_cjk("[星空字幕组][进击的巨人 第三季 第二部分][01-10 Fin]")[1]

        assert (hints.season, hints.part) == (3, 2)

    def test_a_release_without_a_part_says_nothing(self) -> None:
        assert normalize_cjk("[DBD-Raws][不死者之王 第二季][01][1080P]")[1].part is None


class TestEpisode:
    @pytest.mark.parametrize(
        ("name", "episode", "end"),
        [
            ("【极影字幕社】龙珠大魔 第01话 GB 1080P MP4", 1, None),
            ("[千夏字幕組][上伊那牡丹][第01話][1080p_AVC][繁體]", 1, None),
            ("[Group][Show][第12集][1080P]", 12, None),
            ("[千夏字幕組][上伊那牡丹][第01-12話][1080p_AVC][繁體][合集]", 1, 12),
            ("[Group][Show][第13話 END][1080P]", 13, None),
        ],
    )
    def test_chinese_episode_markers(self, name: str, episode: int, end: int | None) -> None:
        hints = normalize_cjk(name)[1]

        assert (hints.episode, hints.episode_end) == (episode, end)


class TestCollectionAndSpecial:
    @pytest.mark.parametrize(
        "name",
        [
            "[千夏字幕組][上伊那牡丹][第01-12話][繁體][合集]",
            "[DBD-Raws][不死者之王 第二季][01-13TV全集+SP][1080P]",
            "[Group][Show][全12话][1080P]",
            "[Group][Show][總集篇][1080P]",
        ],
    )
    def test_collection_markers(self, name: str) -> None:
        assert normalize_cjk(name)[1].collection is True

    @pytest.mark.parametrize(
        ("name", "kind"),
        [
            ("[DBD-Raws][不死者之王 第二季][01-13TV全集+SP][1080P]", SpecialKind.SP),
            ("[Group][Show][番外][1080P]", SpecialKind.SP),
            ("[Group][Show][特別篇][1080P]", SpecialKind.SP),
            ("[Group][Show][映像特典][1080P]", SpecialKind.SP),
            ("[Group] Show OVA 01 [1080p]", SpecialKind.OVA),
            ("[Group] Show OAD 01 [1080p]", SpecialKind.OAD),
            ("[Group] Show NCOP [1080p]", SpecialKind.NC),
        ],
    )
    def test_special_markers(self, name: str, kind: SpecialKind) -> None:
        assert normalize_cjk(name)[1].special is kind

    @pytest.mark.parametrize(
        "name",
        [
            "[7³ACG] 剧场版「进击的巨人」完结篇/Shingeki no Kyojin Movie 2024 [简繁字幕] BDrip",
            "[SweetSub][劇場版 艾斯嘉科尼][Escaflowne The Movie][BDRip][1080P]",
            "[Group][某作品 電影版][BDRip][1080P]",
        ],
    )
    def test_movie_markers(self, name: str) -> None:
        assert normalize_cjk(name)[1].movie is True

    @pytest.mark.parametrize(
        "name", ["[Group][某作品 重製版][01][1080P]", "[Group][某作品 重制][01]"]
    )
    def test_the_remaster_marker(self, name: str) -> None:
        """brief §6.3 的詞典列了 `重製`；值是 brief §6.8 的 token，不是原文。"""
        assert normalize_cjk(name)[1].edition == "Remaster"


class TestGroup:
    def test_the_leading_bracket_is_the_group(self) -> None:
        assert normalize_cjk("[Airota][Show][01][1080p][CHT].mp4")[1].group == "Airota"

    def test_a_release_schedule_prefix_is_not_the_group(self) -> None:
        """`[7月新番]` 是播出檔期。真實語料：`[愛戀字幕社][7月新番][無職轉生 第三季]…`"""
        assert normalize_cjk("[7月新番][愛戀字幕社][無職轉生][10][BIG5]")[1].group == "愛戀字幕社"

    def test_a_collection_marker_is_not_the_group(self) -> None:
        """真實語料：`【合集】女神降临True Beauty真人版韩剧01-16[韩语简体中字]`"""
        assert (
            normalize_cjk("【合集】女神降临True Beauty真人版韩剧01-16[韩语简体中字]")[1].group == ""
        )

    def test_an_episode_number_is_not_the_group(self) -> None:
        assert normalize_cjk("[01][Show][1080P]")[1].group == "Show"

    def test_a_release_without_brackets_has_no_group(self) -> None:
        assert normalize_cjk("The.Bear.S03E01.1080p.WEB.H264-SuccessfulCrab.mkv")[1].group == ""


class TestStripping:
    """剝掉只有中文讀得懂的裝飾，剩下的才交給 guessit（brief §6.3）。"""

    def test_the_star_prefix_goes(self) -> None:
        cleaned, _ = normalize_cjk(
            "【极影字幕社】★10月新番 龙珠大魔/Dragon Ball Daima 第01话 GB 1080P MP4"
        )

        assert "★" not in cleaned
        assert "新番" not in cleaned
        assert "Dragon Ball Daima" in cleaned

    def test_the_recruitment_ad_goes(self) -> None:
        cleaned, _ = normalize_cjk(
            "【极影字幕社】龙珠大魔/Dragon Ball Daima 第01话（字幕社招人内详）"
        )

        assert "招人" not in cleaned

    def test_the_region_notice_goes(self) -> None:
        cleaned, _ = normalize_cjk("[Group] Show - 01 [1080p][仅限港澳台地区]")

        assert "港澳台" not in cleaned

    def test_full_width_brackets_are_normalised(self) -> None:
        assert normalize_cjk("【楓葉字幕組】[寶可夢][135][1080P]")[1].group == "楓葉字幕組"

    def test_the_english_half_of_a_bilingual_title_survives(self) -> None:
        cleaned, _ = normalize_cjk(
            "[7³ACG] 葬送的芙莉莲/Sousou no Frieren S01 | 01-28+SPx11 [简繁字幕] BDrip 1080p x265"
        )

        assert cleaned.startswith("Sousou no Frieren S01")

    def test_a_pure_cjk_name_keeps_its_original(self) -> None:
        """剝到空字串等於把檔名丟掉，那比讓 guessit 猜錯更糟。"""
        name = "[某組] 某作品 全一話"

        assert normalize_cjk(name)[0] == name

    def test_it_records_what_it_recognised(self) -> None:
        """`matched` 是 UI 的「為什麼這樣判」（brief §6.3）。"""
        _, hints = normalize_cjk("[DBD-Raws][不死者之王 第二季][01-13TV全集+SP][简繁外挂]")

        assert "第二季" in hints.matched
        assert "简繁" in hints.matched
