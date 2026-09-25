"""排除條件的規則與比對（brief §15「全部接受，只排除」、M3 票 10）。

規則格式照 Sonarr 的 release profile：一般字詞是**不分大小寫的子字串**；`/…/` 包起來是正則，
預設分大小寫、`/…/i` 不分。比對整個標題。
"""

from __future__ import annotations

import pytest

from berth.domain import SkipCode, skipped
from berth.parser.exclusion import RuleError, matches, normalize_rules, screen

SINGLE = (
    "[喵萌奶茶屋&LoliHouse] 与你相恋到生命尽头 / Kimi ga Shinu made Koi wo Shitai - 12 "
    "[WebRip 1080p HEVC-10bit AAC][简繁日内封字幕]"
)
COLLECTION = (
    "[喵萌奶茶屋&LoliHouse] 上伊那牡丹，醉姿如百合 / Kamiina Botan, Yoeru Sugata wa Yuri no Hana"
    " - [01-12 合集][WebRip 1080p HEVC-10bit AAC][简繁日内封字幕][Fin]"
)
RANGE = (
    "【喵萌奶茶屋】★04月新番★[上伊那牡丹，醉姿如百合 / Kamiina Botan, Yoeru Sugata wa Yuri no Hana]"
    "[01-12][1080p][繁日雙語]"
)


class TestAKeyword:
    def test_matches_anywhere_in_the_title(self) -> None:
        assert matches("HEVC", SINGLE)

    def test_ignores_case(self) -> None:
        assert matches("webrip 1080P", SINGLE)

    def test_does_not_match_what_is_not_there(self) -> None:
        assert not matches("720p", SINGLE)

    def test_a_lone_slash_is_a_keyword(self) -> None:
        assert matches("/", SINGLE)


class TestARegex:
    def test_slashes_make_a_regex(self) -> None:
        assert matches(r"/- \d{2} \[/", SINGLE)

    def test_a_regex_minds_case_by_default(self) -> None:
        assert not matches("/webrip/", SINGLE)

    def test_the_i_flag_ignores_case(self) -> None:
        assert matches("/webrip/i", SINGLE)

    def test_it_searches_rather_than_anchoring(self) -> None:
        assert matches("/Kimi ga/", SINGLE)


class TestNormalizing:
    def test_rules_are_trimmed_and_blank_duplicates_dropped(self) -> None:
        assert normalize_rules([" 720p ", "720p", "/x/i"]) == ("720p", "/x/i")

    def test_order_is_kept(self) -> None:
        assert normalize_rules(["b", "a"]) == ("b", "a")

    def test_an_empty_rule_is_refused(self) -> None:
        with pytest.raises(RuleError) as caught:
            normalize_rules(["720p", "  "])
        assert caught.value.rule == ""

    def test_a_broken_regex_is_refused_with_the_reason(self) -> None:
        with pytest.raises(RuleError) as caught:
            normalize_rules(["/[简繁/"])
        assert caught.value.rule == "/[简繁/"
        assert "unterminated character set" in caught.value.why

    def test_an_unknown_flag_is_refused(self) -> None:
        with pytest.raises(RuleError) as caught:
            normalize_rules(["/x/g"])
        assert "g" in caught.value.why

    def test_an_empty_regex_is_refused(self) -> None:
        """`//` 會對上每一個標題：等於把整個 Feed 關掉，不會是想要的。"""
        with pytest.raises(RuleError):
            normalize_rules(["//"])


class TestScreening:
    def test_a_single_episode_with_no_rules_passes(self) -> None:
        assert screen(SINGLE, not_single=True, layers=()) is None

    @pytest.mark.parametrize("title", [COLLECTION, RANGE])
    def test_anything_but_a_single_episode_is_excluded_by_default(self, title: str) -> None:
        assert screen(title, not_single=True, layers=()) == skipped(SkipCode.NOT_SINGLE)

    def test_with_the_default_off_a_collection_passes(self) -> None:
        assert screen(COLLECTION, not_single=False, layers=()) is None

    @pytest.mark.parametrize(
        "code", [SkipCode.GLOBAL_RULE, SkipCode.FEED_RULE, SkipCode.SERIES_RULE]
    )
    def test_the_same_rule_works_on_every_layer(self, code: SkipCode) -> None:
        """三層取聯集：放在哪一層都擋，理由說出是哪一層。"""
        layers = [(one, ("720p",) if one is code else ()) for one in SkipCode if "rule" in one]

        found = screen(SINGLE.replace("1080p", "720p"), not_single=True, layers=layers)

        assert found == skipped(code, rule="720p")

    def test_the_first_layer_that_matches_is_the_one_named(self) -> None:
        layers = [(SkipCode.GLOBAL_RULE, ("HEVC",)), (SkipCode.SERIES_RULE, ("1080p",))]

        assert screen(SINGLE, not_single=False, layers=layers) == skipped(
            SkipCode.GLOBAL_RULE, rule="HEVC"
        )

    def test_the_default_is_named_before_the_rules(self) -> None:
        layers = [(SkipCode.GLOBAL_RULE, ("合集",))]

        assert screen(COLLECTION, not_single=True, layers=layers) == skipped(SkipCode.NOT_SINGLE)
