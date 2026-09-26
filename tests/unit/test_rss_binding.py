"""RSS Series 自動綁定的規則（brief §15「綁定」、§6.5、M3 票 09）。

「有把握」= 標題正規化後相等，**而且** Mikan 的開播日期落在 TMDB 某一季的首播附近，**而且**只有一部
這樣的作品。其餘留在待綁定，每一種各有自己的理由碼。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import pytest

from berth.domain import (
    BindReasonCode,
    EpisodeSnapshot,
    MediaKind,
    MediaSnapshot,
    SeasonSnapshot,
)
from berth.parser.binding import (
    PREMIERE_WINDOW,
    BindVerdict,
    SeriesClues,
    could_be,
    judge,
    search_terms,
    skeleton,
    title_key,
)
from berth.parser.release import parse_release
from tests.conftest import FIXTURES

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
            # 組名之後的方括號後面還接著字：那一格是 tag，標題是後面那一段。
            ("[Group] [Other] Title - 01 [1080p]", ("Title",)),
            # 讀不出集號時到第一個括號為止：tags 不是標題（票 11）。
            ("[Group] Some Movie [1080p]", ("Some Movie",)),
            # 集號在方括號裡（acg.rip 的真實標題）。
            (
                "[北宇治字幕组] 與妳相戀到生命盡頭 / Kimi ga Shinu made Koi wo Shitai "
                "[12][WebRip][HEVC_AAC][繁日內嵌]",
                ("與妳相戀到生命盡頭", "Kimi ga Shinu made Koi wo Shitai"),
            ),
            # 標題本身在方括號裡，組名在全形括號、前面還有播出檔期。
            (
                "【喵萌奶茶屋】★07月新番★[與妳相戀到生命盡頭 / きみが死ぬまで恋をしたい / "
                "Kimi ga Shinu made Koi wo Shitai][12][1080p][繁日雙語]",
                (
                    "與妳相戀到生命盡頭",
                    "きみが死ぬまで恋をしたい",
                    "Kimi ga Shinu made Koi wo Shitai",
                ),
            ),
            (
                "[千夏字幕組][上伊那牡丹，醉姿如百合_Kamiina Botan, Yoeru Sugata wa Yuri no Hana]"
                "[第12話][1080p_AVC][繁體]",
                ("上伊那牡丹，醉姿如百合_Kamiina Botan, Yoeru Sugata wa Yuri no Hana",),
            ),
            # Nyaa 的真實標題：組名後面接破折號、中文集號、`S01E10`、括號裡的解析度。
            (
                "[Doomdos] - Botan Kamiina Fully Blossoms When Drunk - 第12话 - "
                "[1080p BILIBILI COM WEB-DL]",
                ("Botan Kamiina Fully Blossoms When Drunk",),
            ),
            (
                "[sgt] Botan Kamiina Fully Blossoms When Drunk - S01E10 (WEB 1080p HEVC) | "
                "Kamiina Botan, Yoeru Sugata wa Yuri no Hana",
                ("Botan Kamiina Fully Blossoms When Drunk",),
            ),
            (
                "[SubsPlease] Kamiina Botan, Yoeru Sugata wa Yuri no Hana - 12 (1080p) "
                "[79C53144].mkv",
                ("Kamiina Botan, Yoeru Sugata wa Yuri no Hana",),
            ),
            # 季號是標題的一部分：第三季是另一個 RSS Series。
            (
                "[黒ネズミたち] 时光代理人 第三季 / Link Click Season 3 - 08 "
                "(CR 1920x1080 AVC AAC MKV)",
                ("时光代理人 第三季", "Link Click Season 3"),
            ),
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

    def test_the_season_name_is_not_searched(self) -> None:
        """TMDB 的作品名不帶季名：「第四季」一起搜就搜不到（M4 票 14，2026-09-26 實測）。"""
        assert search_terms(REZERO) == (
            "Re：从零开始的异世界生活 夺还篇",
            "Re：从零开始的异世界生活",
        )

    def test_a_latin_season_name_is_not_searched_either(self) -> None:
        clues = SeriesClues(
            title="时光代理人 第三季",
            premiere=None,
            release_title="[黒ネズミたち] 时光代理人 第三季 / Link Click Season 3 - 08 (CR 1080p)",
        )

        assert search_terms(clues) == ("时光代理人", "Link Click")


def fixture_feeds() -> dict[str, list[str]]:
    """Nyaa 與 acg.rip 的四份 fixture：`<站>/<檔名>` → 每一筆的標題。一份是一部作品的搜尋結果。"""
    import feedparser  # type: ignore[import-untyped]  # 沒有型別存根，同 adapters/rss/feed.py

    paths = sorted((FIXTURES / "http" / "nyaa").glob("*.xml")) + sorted(
        (FIXTURES / "http" / "acgrip").glob("*.xml")
    )
    return {
        f"{path.parent.name}/{path.name}": [
            str(entry.title) for entry in feedparser.parse(path.read_bytes()).entries
        ]
        for path in paths
    }


class TestTheTitleKey:
    """非 Mikan 的 RSS Series 鍵：標題骨幹 + 字幕組（brief §15，AutoBangumi 的做法，票 11）。"""

    def test_the_episodes_of_one_group_share_one_key(self) -> None:
        episodes = [
            f"[喵萌奶茶屋&LoliHouse] 上伊那牡丹，醉姿如百合 / Kamiina Botan, Yoeru Sugata wa Yuri "
            f"no Hana - {number:02d} [WebRip 1080p HEVC-10bit AAC]"
            for number in (9, 10, 11, 12)
        ]

        assert len({title_key(title) for title in episodes}) == 1

    def test_two_groups_on_one_work_are_two_keys(self) -> None:
        lolihouse = (
            "[喵萌奶茶屋&LoliHouse] 与你相恋到生命尽头 / Kimi ga Shinu made Koi wo Shitai - 12 "
            "[WebRip 1080p HEVC-10bit AAC][简繁日内封字幕]"
        )
        ani = "[ANi] Kimi ga Shinu made Koi wo Shitai /  與妳相戀到生命盡頭 - 12 [1080P][Baha]"

        assert title_key(lolihouse) != title_key(ani)

    def test_the_simplified_and_traditional_releases_of_one_group_share_the_latin_name(
        self,
    ) -> None:
        """北宇治的简日、繁日、简繁三種發佈中文名各不同，羅馬字那一段相同：是同一個 Series。"""
        variants = [
            "[北宇治字幕组] 與妳相戀到生命盡頭 / Kimi ga Shinu made Koi wo Shitai "
            "[12][WebRip][HEVC_AAC][繁日內嵌]",
            "[北宇治字幕组] 与你相恋到生命尽头 / Kimi ga Shinu made Koi wo Shitai "
            "[12][WebRip][HEVC_AAC][简日内嵌]",
            "[北宇治字幕组] 与你相恋到生命尽头 / 與妳相戀到生命盡頭 / "
            "Kimi ga Shinu made Koi wo Shitai [11][WebRip][HEVC_AAC][简繁日内封]",
        ]

        assert len({title_key(title) for title in variants}) == 1

    def test_a_batch_joins_the_series_of_its_group(self) -> None:
        """合集照樣長在同一個 Series 上，由排除條件擋下，而不是另長一個。"""
        batch = "[SubsPlease] Kamiina Botan, Yoeru Sugata wa Yuri no Hana (01-12) (1080p) [Batch]"
        single = (
            "[SubsPlease] Kamiina Botan, Yoeru Sugata wa Yuri no Hana - 12 (720p) [E91B4570].mkv"
        )

        assert title_key(batch) == title_key(single)

    @pytest.mark.parametrize("feed", sorted(fixture_feeds()))
    def test_every_group_in_a_real_feed_is_one_key_and_the_groups_are_apart(
        self, feed: str
    ) -> None:
        """一份真實的搜尋 feed 是一部作品：同一個組名的每一筆（各集、各解析度、合集）同一個鍵，
        不同組名的鍵不同。"""
        by_group: dict[str, set[str | None]] = {}
        for title in fixture_feeds()[feed]:
            by_group.setdefault(parse_release(title).group, set()).add(title_key(title))

        assert all(len(keys) == 1 for keys in by_group.values()), by_group
        keys = [next(iter(keys)) for keys in by_group.values()]
        assert None not in keys
        assert len(set(keys)) == len(keys)

    def test_a_title_with_nothing_left_has_no_key(self) -> None:
        assert title_key("[Group] - 12 [1080p]") is None


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
        """「包含」夠當解析器的證據，不夠當自動綁定的：續作、外傳的名字常常包住前作名。"""
        spinoff = SeriesClues(
            title="与你相恋到生命尽头 另一个结局", premiere=date(2026, 7, 7), release_title=""
        )

        assert codes(judge(spinoff, [show(262000)])) == [BindReasonCode.NO_CANDIDATE]

    def test_without_a_premiere_the_year_cannot_be_confirmed(self) -> None:
        blind = SeriesClues(title="与你相恋到生命尽头", premiere=None, release_title="")

        found = judge(blind, [show(262000)])

        assert found.media is None
        assert codes(found) == [BindReasonCode.NO_PREMIERE]
        assert [shot.tmdb_id for shot in found.candidates] == [262000]

    def test_a_source_without_a_show_page_offers_candidates_from_the_title_only(self) -> None:
        """Nyaa、acg.rip 沒有番組頁（票 11）：標題相等的列成候選，理由說的是「沒有番組頁」。"""
        titled = SeriesClues(title="", premiere=None, release_title=KIMI_RELEASE, show_page=False)

        found = judge(titled, [show(262000)])

        assert found.media is None
        assert codes(found) == [BindReasonCode.NO_SHOW_PAGE]
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


#: 2026-09-26 試跑沒綁上的那一部（M4 票 14）：真的 Mikan 聚合 feed 裡的發佈名，與 Mikan 番組頁 4052
#: 的番組名與「放送开始」（第四季的第二個 cour 另開的番組）。
REZERO = SeriesClues(
    title="Re：从零开始的异世界生活 第四季 夺还篇",
    premiere=date(2026, 8, 12),
    release_title=(
        "[ANi]  Re：从零开始的异世界生活 第四季 - 18 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]"
    ),
)


def weekly(first: date, count: int, start: int = 1) -> tuple[EpisodeSnapshot, ...]:
    return tuple(
        EpisodeSnapshot(episode_number=start + n, air_date=first + timedelta(weeks=n))
        for n in range(count)
    )


def rezero() -> MediaSnapshot:
    """TMDB 65942 的形狀（2026-09-26 查）：四輪播出全部放在第 1 季，一共 85 集；第四輪是第 67–77 集
    （4 月起）與隔 56 天之後的第 78–85 集（8 月起），間隔不到 180 天，同一輪。"""
    episodes = (
        weekly(date(2016, 4, 4), 25)
        + weekly(date(2020, 7, 8), 25, start=26)
        + weekly(date(2024, 10, 2), 16, start=51)
        + weekly(date(2026, 4, 8), 11, start=67)
        + weekly(date(2026, 8, 12), 8, start=78)
    )
    return MediaSnapshot(
        tmdb_id=65942,
        kind=MediaKind.TV,
        title="Re：從零開始的異世界生活",
        title_en="Re:ZERO -Starting Life in Another World-",
        title_original="Re:ゼロから始める異世界生活",
        year=2016,
        first_air_date=date(2016, 4, 4),
        titles=("Re:ZERO -Starting Life in Another World-", "Re：从零开始的异世界生活"),
        seasons=(
            SeasonSnapshot(
                season_number=1,
                name="Season 1",
                episode_count=len(episodes),
                air_date=date(2016, 4, 4),
                episodes=episodes,
            ),
        ),
    )


def two_seasons() -> MediaSnapshot:
    """《与你相恋》的兩季，每季 12 集照週播。"""
    shot = show(262000, seasons=(date(2026, 7, 7), date(2027, 4, 5)))
    return shot.model_copy(
        update={
            "seasons": tuple(
                row.model_copy(update={"episodes": weekly(row.air_date or date.min, 12)})
                for row in shot.seasons
            )
        }
    )


class TestSeasonNames:
    """季名從標題拆出來當線索（M4 票 14）：標題比拆掉季名的那一段，開播日比那一季播出的期間。"""

    def test_a_named_season_binds_by_that_season(self) -> None:
        clues = SeriesClues(
            title="与你相恋到生命尽头 第二季", premiere=date(2027, 4, 3), release_title=""
        )

        found = judge(clues, [two_seasons()])

        assert found.media is not None
        assert found.reasons[0].params == {
            "clue": "与你相恋到生命尽头",
            "title": "与你相恋到生命尽头",
        }
        assert codes(found)[1] is BindReasonCode.SEASON_AIRING
        assert found.reasons[1].params == {
            "premiere": "2027-04-03",
            "season": 2,
            "episode": "S02E01",
            "aired": "2027-04-05",
        }

    def test_a_second_cour_that_mikan_lists_on_its_own_binds_by_the_merged_run(self) -> None:
        """TMDB 把 Re:Zero 四輪播出都放在第 1 季：第四季是依播出日切出的第 4 輪，Mikan 的「夺还篇」
        是那一輪隔了 56 天之後的第 78 集（plan §4.4 的虛擬季）。番組名帶篇名不相等，發佈名的
        骨幹相等。"""
        found = judge(REZERO, [rezero()])

        assert found.media is not None
        assert found.media.tmdb_id == 65942
        assert codes(found) == [BindReasonCode.TITLE_EQUAL, BindReasonCode.SEASON_AIRING]
        assert found.reasons[0].params["clue"] == "Re：从零开始的异世界生活"
        assert found.reasons[1].params == {
            "premiere": "2026-08-12",
            "season": 4,
            "episode": "S01E78",
            "aired": "2026-08-12",
        }

    def test_a_premiere_in_the_break_between_cours_is_not_airing(self) -> None:
        """兩個 cour 之間停播 56 天：落在中間、離兩邊都超過窗口的開播日對不上。"""
        mid_break = replace(REZERO, premiere=date(2026, 7, 15))

        assert codes(judge(mid_break, [rezero()])) == [BindReasonCode.PREMIERE_FAR]

    def test_a_named_season_on_another_seasons_date_is_not_bound(self) -> None:
        """第二季的番組頁寫的卻是第一季的開播日：兩條線索互相矛盾，留給人（續作綁到前作的樣子）。"""
        sequel = SeriesClues(
            title="与你相恋到生命尽头 第二季", premiere=date(2026, 7, 7), release_title=""
        )

        found = judge(sequel, [two_seasons()])

        assert found.media is None
        assert codes(found) == [BindReasonCode.PREMIERE_FAR]
        assert [shot.tmdb_id for shot in found.candidates] == [262000]

    def test_a_named_season_tmdb_does_not_have_is_not_bound(self) -> None:
        sequel = SeriesClues(
            title="与你相恋到生命尽头 第三季", premiere=date(2027, 4, 3), release_title=""
        )

        assert codes(judge(sequel, [two_seasons()])) == [BindReasonCode.PREMIERE_FAR]

    def test_without_a_season_name_the_airing_does_not_count(self) -> None:
        """沒寫季名時照舊只比各季首播：多一種比法就多一種綁錯的可能，這張票只補有季名的那一種。"""
        unnamed = replace(REZERO, title="Re：从零开始的异世界生活", release_title="")

        assert codes(judge(unnamed, [rezero()])) == [BindReasonCode.PREMIERE_FAR]

    def test_a_title_that_carries_its_season_as_a_name_is_compared_as_before(self) -> None:
        """TMDB 的名字本身帶季名（續作另開一部）：原樣相等時季名是名字的一部分，比各季首播。"""
        sequel_entry = show(7, titles=("与你相恋到生命尽头 第二季",), seasons=(date(2027, 4, 5),))
        clues = SeriesClues(
            title="与你相恋到生命尽头 第二季", premiere=date(2027, 4, 3), release_title=""
        )

        found = judge(clues, [sequel_entry])

        assert found.media is not None
        assert codes(found) == [BindReasonCode.TITLE_EQUAL, BindReasonCode.PREMIERE_NEAR]
        assert found.reasons[1].params["season"] == 1
