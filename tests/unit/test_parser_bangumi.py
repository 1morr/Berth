"""一部作品在 Mikan 上是哪一個番組（M5.6 票 08）。

給模型一支 `rss.subscribe`，Mikan 的「用哪些名字搜、用開播日挑哪一個」從 skill 搬進程式。這一層
沒有 IO：候選是呼叫端讀回來的番組（id、標題、番組頁的「放送开始」），介面是 `same_work` 與
`choose`。規則與 `parser.binding.judge` 的「有把握」同一套（brief §15〈綁定〉）。
"""

from __future__ import annotations

from datetime import date

import pytest

from berth.domain import MediaKind, MediaSnapshot
from berth.parser.bangumi import BangumiCandidate, choose, names, same_work


def work(
    *,
    title: str = "與妳相戀到生命盡頭",
    title_en: str = "Kimi ga Shinu made Koi wo Shitai",
    title_original: str = "君が死ぬまで恋をしたい",
    title_zh_cn: str = "",
    #: TMDB 的 `titles` 帶著各語言翻譯（plan §4.3）：番組名是簡體，繁中名對不上，這是真的那一條。
    titles: tuple[str, ...] = ("与你相恋到生命尽头",),
    first_air_date: date | None = date(2026, 7, 7),
) -> MediaSnapshot:
    return MediaSnapshot(
        tmdb_id=1,
        kind=MediaKind.TV,
        title=title,
        title_en=title_en,
        title_original=title_original,
        title_zh_cn=title_zh_cn,
        titles=titles,
        year=first_air_date.year if first_air_date else None,
        first_air_date=first_air_date,
    )


class TestNames:
    def test_every_name_is_searched_once(self) -> None:
        """中文、原名、羅馬拼音、英文名都搜（brief §20.12 實測四種寫法都回同樣的番組）。"""
        found = names(work(titles=("Kimi ga Shinu made Koi wo Shitai", "与你相恋到生命尽头")))

        assert set(found) == {
            "與妳相戀到生命盡頭",
            "君が死ぬまで恋をしたい",
            "Kimi ga Shinu made Koi wo Shitai",
            "与你相恋到生命尽头",
        }

    def test_the_simplified_name_goes_first(self) -> None:
        """Mikan 的番組名多半是簡體中文，先搜它省一次請求。"""
        found = names(work(title_zh_cn="与你相恋到生命尽头"))

        assert found[0] == "与你相恋到生命尽头"

    def test_cjk_names_are_searched_before_english_ones(self) -> None:
        """每次搜尋真的打一次 Mikan，先搜命中率高的（番組名是中文或日文）。"""
        found = names(work(titles=("Kimi ga Shinu made Koi wo Shitai", "与你相恋到生命尽头")))

        assert found.index("与你相恋到生命尽头") < found.index("Kimi ga Shinu made Koi wo Shitai")
        assert found.index("君が死ぬまで恋をしたい") < found.index(
            "Kimi ga Shinu made Koi wo Shitai"
        )

    def test_a_season_name_does_not_make_a_second_search(self) -> None:
        found = names(work(titles=("與妳相戀到生命盡頭 第二季", "與妳相戀到生命盡頭")))

        assert found.count("與妳相戀到生命盡頭") == 1

    def test_latin_names_can_go_first(self) -> None:
        """M5.6 票 09：關鍵字站退回時 nyaa 先試原文與英文（發佈名多半是那兩種寫法）。"""
        found = names(
            work(titles=("Kimi ga Shinu made Koi wo Shitai", "与你相恋到生命尽头")),
            latin_first=True,
        )

        assert found[0] == "Kimi ga Shinu made Koi wo Shitai"
        assert set(found) == set(names(work(titles=("与你相恋到生命尽头",)))) | {
            "君が死ぬまで恋をしたい",
            "Kimi ga Shinu made Koi wo Shitai",
        }


class TestSameWork:
    @pytest.mark.parametrize(
        "title",
        [
            "與妳相戀到生命盡頭",
            "与你相恋到生命尽头",
            "君が死ぬまで恋をしたい",
            "Kimi ga Shinu made Koi wo Shitai",
            # 番組名寫了季名，作品名沒有（M4 票 14）。
            "與妳相戀到生命盡頭 第二季",
            "Kimi ga Shinu made Koi wo Shitai 2nd Season",
            # 全形與大小寫不算差別。
            "ＫＩＭＩ ＧＡ ＳＨＩＮＵ ＭＡＤＥ ＫＯＩ ＷＯ ＳＨＩＴＡＩ",
        ],
    )
    def test_the_same_title_in_any_writing(self, title: str) -> None:
        assert same_work(work(), title)

    @pytest.mark.parametrize(
        "title",
        [
            "與妳相戀到生命盡頭 特別篇",  # 名字包住不算相等（續作名常常包住前作名）
            "別的動畫",
            "",
        ],
    )
    def test_a_title_that_only_looks_like_it(self, title: str) -> None:
        assert not same_work(work(), title)


class TestChoose:
    def test_one_matching_bangumi(self) -> None:
        found = choose(
            work(),
            (BangumiCandidate(id=4009, title="与你相恋到生命尽头", premiere=date(2026, 7, 7)),),
        )

        assert found is not None and found.id == 4009

    def test_the_premiere_date_picks_between_namesakes_of_different_years(self) -> None:
        """同名不同年（重拍）：兩部都叫同一個名字，開播日把它們分開。"""
        remake = (
            BangumiCandidate(id=11, title="猎人", premiere=date(1999, 10, 16)),
            BangumiCandidate(id=22, title="猎人", premiere=date(2011, 10, 2)),
        )

        found = choose(
            work(
                title="猎人",
                title_en="Hunter x Hunter",
                title_original="ハンター×ハンター",
                titles=("猎人",),
                first_air_date=date(2011, 10, 2),
            ),
            remake,
        )

        assert found is not None and found.id == 22

    def test_a_later_season_of_the_same_work_is_not_picked_for_the_first_season(self) -> None:
        """Mikan 的一季第二個 cour 另開一個番組；作品的開播日是第一季的，挑第一季那一個。"""
        frieren = (
            BangumiCandidate(id=3821, title="葬送的芙莉莲 第二季", premiere=date(2026, 1, 16)),
            BangumiCandidate(id=3141, title="葬送的芙莉莲", premiere=date(2023, 9, 29)),
        )

        found = choose(
            work(
                title="葬送的芙莉蓮",
                title_en="Frieren: Beyond Journey's End",
                title_original="葬送のフリーレン",
                titles=("葬送的芙莉莲",),
                first_air_date=date(2023, 9, 29),
            ),
            frieren,
        )

        assert found is not None and found.id == 3141

    def test_no_name_matches(self) -> None:
        found = choose(work(), (BangumiCandidate(id=1, title="別的動畫", premiere=None),))

        assert found is None

    def test_a_namesake_far_in_time_is_not_it(self) -> None:
        found = choose(
            work(), (BangumiCandidate(id=1, title="与你相恋到生命尽头", premiere=date(2016, 7, 7)),)
        )

        assert found is None

    def test_two_namesakes_in_the_window_are_ambiguous(self) -> None:
        """兩個都落在窗口裡、一樣近：不猜。"""
        same_day = (
            BangumiCandidate(id=1, title="与你相恋到生命尽头", premiere=date(2026, 7, 7)),
            BangumiCandidate(id=2, title="与你相恋到生命尽头", premiere=date(2026, 7, 7)),
        )

        assert choose(work(), same_day) is None

    def test_without_a_premiere_only_a_single_name_match_is_used(self) -> None:
        """作品沒有首播日（舊快照、TMDB 未定檔）：一個命中才用，兩個就不猜。"""
        one = (BangumiCandidate(id=1, title="与你相恋到生命尽头", premiere=None),)
        two = (*one, BangumiCandidate(id=2, title="与你相恋到生命尽头", premiere=None))

        assert choose(work(first_air_date=None), one) is not None
        assert choose(work(first_air_date=None), two) is None

    def test_a_page_without_a_premiere_is_used_when_it_is_the_only_name_match(self) -> None:
        found = choose(work(), (BangumiCandidate(id=1, title="与你相恋到生命尽头", premiere=None),))

        assert found is not None and found.id == 1
