"""RSS Series 自動綁定的規則（brief §15「綁定」、§6.5、M3 票 09）。

「有把握」= 標題正規化後相等，**而且** Mikan 的開播日期落在 TMDB 某一季的首播附近，**而且**只有一部
這樣的作品。其餘留在待綁定，每一種各有自己的理由碼。
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from berth.domain import BindReasonCode, MediaKind, MediaSnapshot, SeasonSnapshot
from berth.parser.binding import (
    PREMIERE_WINDOW,
    BindVerdict,
    SeriesClues,
    could_be,
    judge,
    search_terms,
    skeleton,
)

KIMI_RELEASE = (
    "[喵萌奶茶屋&LoliHouse] 与你相恋到生命尽头 / Kimi ga Shinu made Koi wo Shitai - 12 "
    "[WebRip 1080p HEVC-10bit AAC][简繁日内封字幕]"
)
KIMI = SeriesClues(
    title="与你相恋到生命尽头", premiere=date(2026, 7, 7), release_title=KIMI_RELEASE
)


def show(
    tmdb_id: int,
    *,
    titles: tuple[str, ...] = ("Kimi ga Shinu made Koi wo Shitai", "与你相恋到生命尽头"),
    seasons: tuple[date, ...] = (date(2026, 7, 7),),
    kind: MediaKind = MediaKind.TV,
    released: date | None = None,
) -> MediaSnapshot:
    first = released or (seasons[0] if seasons else None)
    return MediaSnapshot(
        tmdb_id=tmdb_id,
        kind=kind,
        title="與妳相戀到生命盡頭",
        title_en="Kimishinu",
        title_original="君が死ぬまで恋をしたい",
        year=first.year if first else None,
        first_air_date=first,
        titles=titles,
        seasons=tuple(
            SeasonSnapshot(
                season_number=number,
                name=f"Season {number}",
                episode_count=12,
                air_date=aired,
            )
            for number, aired in enumerate(seasons, start=1)
        ),
    )


def codes(found: BindVerdict) -> list[BindReasonCode]:
    return [reason.code for reason in found.reasons]


class TestTheSkeleton:
    @pytest.mark.parametrize(
        ("release", "expected"),
        [
            (KIMI_RELEASE, ("与你相恋到生命尽头", "Kimi ga Shinu made Koi wo Shitai")),
            (
                "[ANi]  BLACK TORCH 暗黑灯火 - 12 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]",
                ("BLACK TORCH 暗黑灯火",),
            ),
            (
                "[ANi] Otome Kaijuu Carameliser /  少女怪兽焦糖恋心 - 12 [1080P][Baha]",
                ("Otome Kaijuu Carameliser", "少女怪兽焦糖恋心"),
            ),
            # 讀不出 ` - 集號` 時整段都是骨幹（只去掉開頭的組名）。
            ("[Group] Some Movie [1080p]", ("Some Movie [1080p]",)),
        ],
    )
    def test_the_group_and_the_episode_are_cut_and_every_name_is_kept(
        self, release: str, expected: tuple[str, ...]
    ) -> None:
        assert skeleton(release) == expected

    def test_the_search_asks_for_the_mikan_name_first_then_the_latin_one(self) -> None:
        """英文或羅馬字那一段多半與 TMDB 的英文標題相符，排在番組名之後；重複的只問一次。"""
        assert search_terms(KIMI) == ("与你相恋到生命尽头", "Kimi ga Shinu made Koi wo Shitai")

    def test_at_most_three_searches(self) -> None:
        clues = SeriesClues(title="甲", premiere=None, release_title="[G] 乙 / 丙 / 丁 / 戊 - 01")

        assert len(search_terms(clues)) == 3


class TestConfident:
    def test_equal_title_and_a_nearby_premiere_on_one_work_binds_it(self) -> None:
        found = judge(KIMI, [show(262000)])

        assert found.media is not None
        assert found.media.tmdb_id == 262000
        assert codes(found) == [BindReasonCode.TITLE_EQUAL, BindReasonCode.PREMIERE_NEAR]
        assert found.reasons[0].params == {
            "clue": "与你相恋到生命尽头",
            "title": "与你相恋到生命尽头",
        }
        assert found.reasons[1].params == {
            "premiere": "2026-07-07",
            "season": 1,
            "aired": "2026-07-07",
        }

    def test_the_latin_skeleton_counts_as_a_title_too(self) -> None:
        only_romaji = show(262000, titles=("Kimi ga Shinu made Koi wo Shitai",))

        found = judge(KIMI, [only_romaji])

        assert found.media is not None
        assert found.reasons[0].params["clue"] == "Kimi ga Shinu made Koi wo Shitai"

    def test_normalisation_ignores_punctuation_width_and_case(self) -> None:
        loud = show(262000, titles=("ＫＩＭＩ ga shinu made, koi wo shitai!",))

        assert judge(KIMI, [loud]).media is not None

    def test_a_later_season_premiering_then_counts(self) -> None:
        """第二季的番組頁寫的是第二季的開播日。"""
        clues = SeriesClues(title="与你相恋到生命尽头", premiere=date(2027, 4, 3), release_title="")
        two = show(262000, seasons=(date(2026, 7, 7), date(2027, 4, 5)))

        found = judge(clues, [two])

        assert found.media is not None
        assert found.reasons[1].params["season"] == 2

    @pytest.mark.parametrize("days", [PREMIERE_WINDOW.days, -PREMIERE_WINDOW.days])
    def test_the_window_edges_are_near(self, days: int) -> None:
        shifted = show(262000, seasons=(date(2026, 7, 7) + timedelta(days=days),))

        assert judge(KIMI, [shifted]).media is not None

    def test_a_movie_compares_its_release_date(self) -> None:
        movie = show(9, kind=MediaKind.MOVIE, seasons=(), released=date(2026, 7, 10))

        found = judge(KIMI, [movie])

        assert found.media is not None
        assert codes(found) == [BindReasonCode.TITLE_EQUAL, BindReasonCode.RELEASE_NEAR]
        assert found.reasons[1].params == {"premiere": "2026-07-07", "aired": "2026-07-10"}


class TestPending:
    def test_same_title_another_year_stays_pending(self) -> None:
        """同名不同年：標題相同，但沒有一季在 Mikan 寫的開播日附近首播。"""
        old = show(1000, seasons=(date(2006, 4, 1),))

        found = judge(KIMI, [old])

        assert found.media is None
        assert codes(found) == [BindReasonCode.PREMIERE_FAR]
        assert found.reasons[0].params == {"title": "Kimishinu", "premiere": "2026-07-07"}
        assert [shot.tmdb_id for shot in found.candidates] == [1000]

    def test_just_outside_the_window_is_far(self) -> None:
        late = show(262000, seasons=(date(2026, 7, 7) + PREMIERE_WINDOW + timedelta(days=1),))

        assert codes(judge(KIMI, [late])) == [BindReasonCode.PREMIERE_FAR]

    def test_two_works_that_both_fit_stay_pending_and_are_both_listed(self) -> None:
        found = judge(KIMI, [show(1), show(2)])

        assert found.media is None
        assert codes(found) == [BindReasonCode.SEVERAL_CANDIDATES]
        assert found.reasons[0].params == {"number": 2}
        assert [shot.tmdb_id for shot in found.candidates] == [1, 2]

    def test_nothing_with_that_title_stays_pending(self) -> None:
        stranger = show(5, titles=("Something Else",))

        found = judge(KIMI, [stranger])

        assert found.media is None
        assert codes(found) == [BindReasonCode.NO_CANDIDATE]
        assert found.candidates == ()

    def test_an_empty_search_is_no_candidate_too(self) -> None:
        assert codes(judge(KIMI, [])) == [BindReasonCode.NO_CANDIDATE]

    def test_a_contained_title_is_not_equal(self) -> None:
        """「包含」夠當解析器的證據，不夠當自動綁定的：續作名常常包住前作名。"""
        sequel = SeriesClues(
            title="与你相恋到生命尽头 第二季", premiere=date(2026, 7, 7), release_title=""
        )

        assert codes(judge(sequel, [show(262000)])) == [BindReasonCode.NO_CANDIDATE]

    def test_without_a_premiere_the_year_cannot_be_confirmed(self) -> None:
        blind = SeriesClues(title="与你相恋到生命尽头", premiere=None, release_title="")

        found = judge(blind, [show(262000)])

        assert found.media is None
        assert codes(found) == [BindReasonCode.NO_PREMIERE]
        assert [shot.tmdb_id for shot in found.candidates] == [262000]

    def test_the_reasons_are_distinct_for_the_three_cases(self) -> None:
        """驗收：同名不同年、兩個候選、沒有候選，三種理由碼不同。"""
        found = {
            codes(judge(KIMI, [show(1000, seasons=(date(2006, 4, 1),))]))[0],
            codes(judge(KIMI, [show(1), show(2)]))[0],
            codes(judge(KIMI, []))[0],
        }

        assert len(found) == 3


class TestTheYearPrefilter:
    """只憑搜尋結果的年份就排除得掉的，不去讀詳情（`services.rss._candidates`）。"""

    @pytest.mark.parametrize(
        ("kind", "year", "kept"),
        [
            # 劇集的年份是第一季的：更早開播的作品可能是它的後面某一季，留著。
            (MediaKind.TV, 2006, True),
            (MediaKind.TV, 2026, True),
            # 比 Mikan 寫的開播還晚開始的劇集不可能是它。
            (MediaKind.TV, 2027, False),
            # 電影就是那一年，前後差一年（跨年上映、各地上映日不同）。
            (MediaKind.MOVIE, 2025, True),
            (MediaKind.MOVIE, 2027, True),
            (MediaKind.MOVIE, 2024, False),
            (MediaKind.MOVIE, 2028, False),
        ],
    )
    def test_what_the_year_alone_rules_out(self, kind: MediaKind, year: int, kept: bool) -> None:
        assert could_be(kind, year, date(2026, 7, 7)) is kept

    def test_a_premiere_at_the_year_end_keeps_next_years_show(self) -> None:
        """12 月底開播、TMDB 記成隔年 1 月首播的，還在窗口裡。"""
        assert could_be(MediaKind.TV, 2027, date(2026, 12, 25))

    @pytest.mark.parametrize(("year", "premiere"), [(None, date(2026, 7, 7)), (2030, None)])
    def test_without_either_date_nothing_is_ruled_out(
        self, year: int | None, premiere: date | None
    ) -> None:
        assert could_be(MediaKind.TV, year, premiere)
