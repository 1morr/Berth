"""季集對應（plan §4.1 的 `map_episode`、§4.4，brief §6.4、§6.5）。

這一層回答的是「這個檔案是第幾季第幾集」。它**不做 IO**：TMDB 的事實由 `MediaSnapshot`
帶進來，所以每一條規則都可以在這裡逐條釘住。

真實發佈的形狀取自 `docs/research/anime-episode-source.md` §6——那份量測列出的 13 種
失敗簽章就是這一票要修的東西。
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from berth.domain import (
    Candidate,
    Confidence,
    EpisodeSnapshot,
    MappingStrategy,
    MediaKind,
    MediaSnapshot,
    ParseContext,
    ReasonCode,
    SeasonSnapshot,
    why,
)
from berth.parser import map_episode, parse_release, structure_hints


def episodes(
    count: int, *, start: date, every: int = 7, first: int = 1
) -> tuple[EpisodeSnapshot, ...]:
    return tuple(
        EpisodeSnapshot(
            episode_number=first + index, air_date=start + timedelta(days=every * index)
        )
        for index in range(count)
    )


def season(
    number: int,
    count: int,
    *,
    name: str = "",
    names: tuple[str, ...] = (),
    start: date = date(2020, 1, 5),
    every: int = 7,
    first: int = 1,
) -> SeasonSnapshot:
    return SeasonSnapshot(
        season_number=number,
        name=name or f"Season {number}",
        names=names or (name or f"Season {number}",),
        episode_count=count,
        air_date=start,
        episodes=episodes(count, start=start, every=every, first=first),
    )


def show(*seasons: SeasonSnapshot, title: str = "Show", year: int = 2020) -> MediaSnapshot:
    return MediaSnapshot(
        tmdb_id=1,
        kind=MediaKind.TV,
        title=title,
        title_en=title,
        title_original=title,
        year=year,
        titles=(title,),
        seasons=seasons,
    )


def movie(title: str = "Oppenheimer", year: int = 2023) -> MediaSnapshot:
    return MediaSnapshot(
        tmdb_id=2,
        kind=MediaKind.MOVIE,
        title=title,
        title_en=title,
        title_original=title,
        year=year,
        titles=(title,),
    )


def run(
    name: str,
    media: MediaSnapshot,
    *,
    path: str = "",
    torrent: str = "",
    season_hint: int | None = None,
    episode_offset: int | None = None,
) -> tuple[Candidate, ...]:
    context = ParseContext(media=media, season_hint=season_hint, episode_offset=episode_offset)
    return map_episode(
        parse_release(name),
        structure_hints(path or name),
        context,
        release_name=torrent,
    )


def best(candidates: tuple[Candidate, ...]) -> tuple[int | None, int | None, MappingStrategy]:
    assert candidates, "expected at least one candidate"
    first = candidates[0]
    return first.season, first.episode_start, first.strategy


class TestExplicit:
    """brief §6.4 第 3 點的第一條：顯式 `SxxEyy` 直接採用，並用 TMDB 驗證該集存在。"""

    def test_sxxeyy(self) -> None:
        bear = show(season(1, 8), season(2, 10), season(3, 10), title="The Bear")
        candidates = run("The.Bear.S03E02.1080p.WEB.mkv", bear)

        assert best(candidates) == (3, 2, MappingStrategy.EXPLICIT)
        assert candidates[0].confidence is Confidence.HIGH

    def test_a_chinese_season_marker_is_just_as_explicit(self) -> None:
        """`[DBD-Raws][不死者之王 第二季][01]`：季號明說了，只是寫成中文。"""
        candidates = run(
            "[DBD-Raws][不死者之王 第二季][01][1080P][BDRip].mkv",
            show(season(1, 13), season(2, 13)),
        )

        assert best(candidates) == (2, 1, MappingStrategy.EXPLICIT)

    def test_an_episode_tmdb_does_not_have_drops_to_low(self) -> None:
        """還沒收錄不代表解析錯，但也不能自動入庫（brief §6.5 的 low 進 review）。"""
        candidates = run("Show.S01E99.1080p.WEB.mkv", show(season(1, 10)))

        assert candidates[0].confidence is Confidence.LOW

    def test_a_multi_episode_file_keeps_both_ends(self) -> None:
        """brief §6.6 的單檔多集。"""
        candidates = run("Show.S01E01-E02.1080p.WEB.mkv", show(season(1, 12)))

        assert (candidates[0].episode_start, candidates[0].episode_end) == (1, 2)


class TestFolder:
    def test_a_season_folder_plus_an_episode_in_the_file(self) -> None:
        candidates = run(
            "Show - 05.mkv", show(season(1, 10), season(2, 10)), path="Season 2/Show - 05.mkv"
        )

        assert best(candidates) == (2, 5, MappingStrategy.FOLDER)

    def test_the_file_name_beats_the_folder(self) -> None:
        """檔名寫了 `S01E05` 而資料夾寫 `Season 2` 時，明說的贏（brief §6.4 的順序）。"""
        candidates = run(
            "Show.S01E05.mkv", show(season(1, 10), season(2, 10)), path="Season 2/Show.S01E05.mkv"
        )

        assert best(candidates) == (1, 5, MappingStrategy.EXPLICIT)


class TestContext:
    def test_the_job_season_hint_wins(self) -> None:
        candidates = run("Show - 05.mkv", show(season(1, 10), season(2, 10)), season_hint=2)

        assert best(candidates) == (2, 5, MappingStrategy.CONTEXT)

    def test_a_rule_offset_may_still_be_high(self) -> None:
        """RSS Rule 的 `episode_offset` 是人設的，所以信心可以是 high（plan §4.4）。"""
        candidates = run("Show - 05.mkv", show(season(1, 24)), season_hint=1, episode_offset=12)

        assert best(candidates) == (1, 17, MappingStrategy.CONTEXT)
        assert candidates[0].confidence is Confidence.HIGH


class TestArcName:
    """plan §4.4 的第一條槓桿：九成的換算失敗是檔名只有篇章名沒有季號。"""

    demon_slayer = show(
        season(
            1,
            26,
            name="Unwavering Resolve Arc",
            names=("Unwavering Resolve Arc", "竈門炭治郎 立志篇", "立志篇"),
        ),
        season(2, 7, name="Mugen Train Arc", names=("Mugen Train Arc", "無限列車篇", "无限列车篇")),
        season(
            5,
            8,
            name="Hashira Training Arc",
            names=("Hashira Training Arc", "柱訓練篇", "柱训练篇"),
        ),
        title="Demon Slayer: Kimetsu no Yaiba",
    )

    def test_a_simplified_arc_name_maps_to_its_season(self) -> None:
        """`[Up to 21°C] 鬼灭之刃 柱训练篇 - 08`——真實發佈，正確答案是第五季第八集。"""
        candidates = run(
            "[Up to 21°C] 鬼灭之刃 柱训练篇 - 08 [WebRip 1080p].mp4", self.demon_slayer
        )

        assert best(candidates) == (5, 8, MappingStrategy.ARC_NAME)

    def test_a_traditional_arc_name_maps_to_the_same_season(self) -> None:
        candidates = run("[Group] 鬼滅之刃 柱訓練篇 - 08 [1080p].mp4", self.demon_slayer)

        assert best(candidates) == (5, 8, MappingStrategy.ARC_NAME)

    def test_an_english_arc_name_maps_to_the_same_season(self) -> None:
        candidates = run(
            "[Group] Kimetsu no Yaiba Hashira Training Arc - 08 [1080p].mkv", self.demon_slayer
        )

        assert best(candidates) == (5, 8, MappingStrategy.ARC_NAME)

    def test_an_arc_name_is_never_more_than_medium(self) -> None:
        """它是推論出來的季號（brief §6.5）。"""
        candidates = run(
            "[Up to 21°C] 鬼灭之刃 柱训练篇 - 08 [WebRip 1080p].mp4", self.demon_slayer
        )

        assert candidates[0].confidence is Confidence.MEDIUM

    def test_the_arc_name_may_live_in_the_torrent_name_only(self) -> None:
        """篇章名常常只寫在索引站的標題上，檔名只剩羅馬字（真實語料）。"""
        candidates = run(
            "[UHA-WINGS] Kimetsu no Yaiba - Hashira Geiko-hen [07][x264 1080p][CHT].mp4",
            self.demon_slayer,
            torrent=(
                "【悠哈璃羽字幕社】[鬼灭之刃 柱训练篇 / Kimetsu no Yaiba - Hashira Geiko-hen][07]"
            ),
        )

        assert best(candidates) == (5, 7, MappingStrategy.ARC_NAME)

    def test_a_generic_season_name_is_not_an_arc(self) -> None:
        """`Season 1` 對每一個發佈都「命中」，那不是資訊。"""
        candidates = run(
            "[Group] Show Season 1 - 03 [1080p].mkv", show(season(1, 12), season(2, 12))
        )

        assert candidates[0].strategy is not MappingStrategy.ARC_NAME

    def test_a_season_name_that_is_just_the_show_title_is_not_an_arc(self) -> None:
        """Overlord 的第一季就叫 `Overlord`——每一個發佈的名字裡都有它。"""
        overlord = show(
            season(1, 13, name="Overlord"),
            season(2, 13, name="Overlord II"),
            title="Overlord",
        )
        candidates = run("[Group] Overlord - 03 [1080p].mkv", overlord)

        assert candidates[0].strategy is not MappingStrategy.ARC_NAME

    def test_final_season_maps_to_the_last_season(self) -> None:
        """`[NaN-Raws]进击的巨人_The_Final_Season[28]`——真實發佈（研究 §6.1）。"""
        titan = show(
            season(1, 25), season(2, 12), season(3, 22), season(4, 28), title="Attack on Titan"
        )
        candidates = run("[NaN-Raws]进击的巨人_The_Final_Season[28][1080P].mp4", titan)

        assert best(candidates) == (4, 28, MappingStrategy.ARC_NAME)


class TestCourOffset:
    """plan §4.4 的第三條：唯一「有季號還是錯」的一類（研究 §6.1.1）。"""

    def split_season(self) -> MediaSnapshot:
        first = episodes(12, start=date(2018, 7, 23))
        second = episodes(10, start=date(2019, 4, 29), first=13)
        return show(
            season(1, 25),
            season(2, 12),
            SeasonSnapshot(
                season_number=3,
                name="Season 3",
                names=("Season 3",),
                episode_count=22,
                air_date=date(2018, 7, 23),
                episodes=first + second,
            ),
            title="Attack on Titan",
        )

    def test_part_two_starts_after_the_first_cour(self) -> None:
        candidates = run(
            "[Erai-raws] Shingeki no Kyojin Season 3 Part 2 - 01 [1080p].mkv", self.split_season()
        )

        assert best(candidates) == (3, 13, MappingStrategy.COUR_OFFSET)

    def test_a_chinese_part_marker_says_the_same_thing(self) -> None:
        candidates = run(
            "[星空字幕组][进击的巨人 第三季 第二部分][05][1080P].mp4", self.split_season()
        )

        assert best(candidates) == (3, 17, MappingStrategy.COUR_OFFSET)

    def test_the_cour_reading_replaces_the_plain_one(self) -> None:
        """兩種讀法都「存在於 TMDB」，所以不是排序問題——看到 cour 標記就不能照字面讀。"""
        candidates = run(
            "[Erai-raws] Shingeki no Kyojin Season 3 Part 2 - 01 [1080p].mkv", self.split_season()
        )

        assert all(item.episode_start != 1 for item in candidates)

    def test_a_continuous_numbering_falls_back_to_the_plain_reading(self) -> None:
        """有的組寫「第二部分」卻直接從 13 接下去。加上偏移會超出該季，那就照字面讀。"""
        candidates = run(
            "[Group] Shingeki no Kyojin Season 3 Part 2 - 13 [1080p].mkv", self.split_season()
        )

        assert best(candidates) == (3, 13, MappingStrategy.EXPLICIT)

    def test_part_one_is_the_plain_reading(self) -> None:
        candidates = run(
            "[Erai-raws] Shingeki no Kyojin Season 3 Part 1 - 05 [1080p].mkv", self.split_season()
        )

        assert best(candidates) == (3, 5, MappingStrategy.EXPLICIT)


class TestSingleSeason:
    def test_an_episode_number_alone_lands_in_the_only_season(self) -> None:
        """韓劇的 `EP08` 與單季動漫的 `- 08`（brief §6.4）。"""
        candidates = run("True.Beauty.2020.EP08.HD1080P.mp4", show(season(1, 16)))

        assert best(candidates) == (1, 8, MappingStrategy.SINGLE_SEASON)

    def test_it_is_never_more_than_medium(self) -> None:
        candidates = run("True.Beauty.2020.EP08.HD1080P.mp4", show(season(1, 16)))

        assert candidates[0].confidence is Confidence.MEDIUM

    def test_specials_do_not_count_as_a_season(self) -> None:
        """S0 存在不代表這部作品有兩季。"""
        candidates = run("[Group] Show - 08 [1080p].mkv", show(season(0, 4), season(1, 12)))

        assert best(candidates) == (1, 8, MappingStrategy.SINGLE_SEASON)


class TestAbsoluteNumbers:
    """brief §6.4 的絕對編號三法。每一種各產一個 Candidate 並附理由（plan §4.1）。"""

    #: 三季的作品，字幕組只寫一個數字。
    long_running = show(season(1, 25), season(2, 12), season(3, 22), title="Attack on Titan")

    def test_cumulative_counting_walks_into_the_right_season(self) -> None:
        candidates = run("[Group] Shingeki no Kyojin - 30 [1080p].mkv", self.long_running)

        assert best(candidates) == (2, 5, MappingStrategy.ABSOLUTE_CUMULATIVE)

    def test_an_absolute_episode_group_is_tried_first(self) -> None:
        """TMDB 有 absolute group 時它才是官方答案，累加只是估算（brief §20.3）。"""
        grouped = show(
            SeasonSnapshot(
                season_number=1,
                name="Season 1",
                episode_count=2,
                episodes=(
                    EpisodeSnapshot(episode_number=1, absolute_number=1),
                    EpisodeSnapshot(episode_number=2, absolute_number=2),
                ),
            ),
            SeasonSnapshot(
                season_number=2,
                name="Season 2",
                episode_count=2,
                episodes=(
                    EpisodeSnapshot(episode_number=1, absolute_number=3),
                    EpisodeSnapshot(episode_number=2, absolute_number=4),
                ),
            ),
        )
        candidates = run("[Group] Show - 03 [1080p].mkv", grouped)

        assert best(candidates) == (2, 1, MappingStrategy.ABSOLUTE_GROUP)

    def test_every_conversion_leaves_its_reasoning(self) -> None:
        candidates = run("[Group] Shingeki no Kyojin - 30 [1080p].mkv", self.long_running)

        assert all(item.reasons for item in candidates)

    def test_a_number_beyond_every_season_maps_to_nothing(self) -> None:
        assert run("[Group] Shingeki no Kyojin - 999 [1080p].mkv", self.long_running) == ()

    def test_a_number_past_the_first_season_is_trusted(self) -> None:
        """超過第一季集數的數字只剩跨季連號一種讀法（SPY×FAMILY 26、MHA 139）。"""
        candidates = run("[Group] Shingeki no Kyojin - 26 [1080p].mkv", self.long_running)

        assert best(candidates) == (2, 1, MappingStrategy.ABSOLUTE_CUMULATIVE)
        assert all(item.confidence is Confidence.MEDIUM for item in candidates)

    def test_a_number_within_the_first_season_is_only_reviewed(self) -> None:
        """`- 25` 也讀得成後面某季從 01 重數的第 25 集——《死神》相剋譚的 01–14 就是。"""
        candidates = run("[Group] Shingeki no Kyojin - 25 [1080p].mkv", self.long_running)

        assert best(candidates) == (1, 25, MappingStrategy.ABSOLUTE_CUMULATIVE)
        assert all(item.confidence is Confidence.LOW for item in candidates)
        assert (
            why(ReasonCode.ABSOLUTE_WITHIN_FIRST_SEASON, number=25, episodes=25, season=1)
            in candidates[0].reasons
        )


class TestAbsoluteNumbersAgainstTheAirDate:
    """檔名帶播出日時，換算出的那一集要是那一天播的（brief §6.4「明說的贏推論的」）。

    《Home and Away》`Episode.8214.2024-02-29` 累加換成 S37E32，那一集播於 2024-02-21——
    TMDB 前幾季比官方編號多收了集數（`docs/research/profile-effect.md` §3.4）。
    """

    #: 第二季隔一年開播，兩季的播出日不重疊。
    daily = show(
        season(1, 25, start=date(2020, 1, 5)),
        season(2, 12, start=date(2021, 1, 3)),
        title="Show",
    )

    def test_the_air_date_of_the_converted_episode_confirms_it(self) -> None:
        candidates = run("Show.E026.2021-01-03.1080p.WEB.mkv", self.daily)

        assert best(candidates) == (2, 1, MappingStrategy.ABSOLUTE_CUMULATIVE)
        assert candidates[0].confidence is Confidence.MEDIUM

    def test_a_day_off_is_only_reviewed(self) -> None:
        """日播的劇差一集就是差一天，所以沒有容忍範圍。"""
        candidates = run("Show.E026.2021-01-04.1080p.WEB.mkv", self.daily)

        assert best(candidates) == (2, 1, MappingStrategy.ABSOLUTE_CUMULATIVE)
        assert candidates[0].confidence is Confidence.LOW
        assert (
            why(
                ReasonCode.AIR_DATE_MISMATCH,
                aired="2021-01-04",
                episode="S02E01",
                tmdb_aired="2021-01-03",
            )
            in candidates[0].reasons
        )

    def test_an_episode_tmdb_has_no_air_date_for_is_only_reviewed(self) -> None:
        """發佈明說了日期，而 TMDB 沒有東西證實它——這不是「對得上」。"""
        undated = show(
            season(1, 25, start=date(2020, 1, 5)),
            SeasonSnapshot(
                season_number=2,
                name="Season 2",
                episode_count=12,
                episodes=tuple(EpisodeSnapshot(episode_number=n) for n in range(1, 13)),
            ),
            title="Show",
        )

        candidates = run("Show.E026.2021-01-03.1080p.WEB.mkv", undated)

        assert best(candidates) == (2, 1, MappingStrategy.ABSOLUTE_CUMULATIVE)
        assert candidates[0].confidence is Confidence.LOW

    def test_a_korean_broadcast_date_is_read_year_first(self) -> None:
        """`150524` 是 2015-05-24（《超人回來了》E079 對到的 S03E21 就是那一天播的）。"""
        superman = show(
            season(1, 9, start=date(2013, 11, 3)),
            season(2, 49, start=date(2014, 1, 5)),
            season(3, 52, start=date(2015, 1, 4)),
            title="The Return of Superman",
        )

        candidates = run("The.Return.of.Superman.E079.150524.HDTV.H264.720p-LIMO.avi", superman)

        assert best(candidates) == (3, 21, MappingStrategy.ABSOLUTE_CUMULATIVE)
        assert candidates[0].confidence is Confidence.MEDIUM


class TestVirtualSeasons:
    """plan §4.4 的 180 天門檻。TMDB 把好幾輪播出併成一季時，季號提示對不上任何一季。"""

    #: Re:Zero 的形狀：TMDB 只有一季，裡面是 25 + 25 + 35 集三輪播出。
    def rezero(self) -> MediaSnapshot:
        first = episodes(25, start=date(2016, 4, 4))
        second = episodes(25, start=date(2020, 7, 8), first=26)
        third = episodes(35, start=date(2024, 10, 2), first=51)
        return show(
            SeasonSnapshot(
                season_number=1,
                name="Season 1",
                names=("Season 1",),
                episode_count=85,
                air_date=date(2016, 4, 4),
                episodes=first + second + third,
            ),
            title="Re:ZERO -Starting Life in Another World-",
        )

    def test_a_season_tmdb_does_not_have_becomes_a_virtual_season(self) -> None:
        candidates = run("[LoliHouse] Re Zero 第二季 - 05 [WebRip 1080p].mkv", self.rezero())

        assert best(candidates) == (1, 30, MappingStrategy.AIR_DATE_OFFSET)

    def test_it_is_never_more_than_medium(self) -> None:
        candidates = run("[LoliHouse] Re Zero 第二季 - 05 [WebRip 1080p].mkv", self.rezero())

        assert candidates[0].confidence is Confidence.MEDIUM

    def test_a_gap_under_the_threshold_does_not_split_a_season(self) -> None:
        """一季分兩 cour 只隔四個月是常態——切開的話季號提示就對不上了（研究 §6.4）。"""
        first = episodes(13, start=date(2020, 7, 8))
        second = episodes(11, start=date(2021, 1, 6), first=14)
        split = show(
            SeasonSnapshot(
                season_number=1,
                name="Season 1",
                episode_count=24,
                air_date=date(2020, 7, 8),
                episodes=first + second,
            ),
        )
        candidates = run("[Group] Show 第二季 - 05 [1080p].mkv", split)

        assert candidates == () or candidates[0].strategy is not MappingStrategy.AIR_DATE_OFFSET


class TestSpecials:
    """brief §7.6：對不到而且像正片的特典 → Unmatched，等人工指派。"""

    def test_a_release_numbered_specials_folder_maps_to_nothing(self) -> None:
        """`SP/[…][SP][01]` 的 01 是字幕組自己的特典序號，不是 TMDB 的 S00E01。"""
        candidates = run(
            "[DBD-Raws][不死者之王 第二季][SP][01][1080P].mkv",
            show(season(0, 57), season(1, 13), season(2, 13)),
            path="SP/[DBD-Raws][不死者之王 第二季][SP][01][1080P].mkv",
        )

        assert candidates == ()

    def test_an_explicit_season_zero_is_taken_at_face_value(self) -> None:
        """發佈明說 `S00E01` 就照它走（brief §6.4 的第一條）。"""
        candidates = run(
            "Sousou no Frieren 2023 S00E03-[1080p].mkv", show(season(0, 26), season(1, 28))
        )

        assert best(candidates) == (0, 3, MappingStrategy.EXPLICIT)

    def test_season_zero_is_never_more_than_medium(self) -> None:
        """字幕組的特典編號與 TMDB 的 S0 編號**不保證一致**（票 05 的語料筆記）。"""
        candidates = run(
            "Sousou no Frieren 2023 S00E03-[1080p].mkv", show(season(0, 26), season(1, 28))
        )

        assert candidates[0].confidence is Confidence.MEDIUM


class TestMovies:
    def test_a_movie_has_no_season_or_episode(self) -> None:
        candidates = run("Oppenheimer.2023.1080p.BluRay.x264.mp4", movie())

        assert best(candidates) == (None, None, MappingStrategy.MOVIE)
        assert candidates[0].confidence is Confidence.HIGH

    def test_an_episode_number_in_a_movie_release_is_ignored(self) -> None:
        """電影檔名裡的數字是年份、版本或畫質，不是集號。"""
        candidates = run(
            "Psycho.1960.Uncut.1080p.BluRay.x265.mkv",
            movie("Psycho", 1960),
        )

        assert candidates[0].episode_start is None


class TestNoMedia:
    """RSS 與重新入庫沒有上下文 Media，那時只能靠標題（brief §6.4 第 2 點）。"""

    def test_without_a_snapshot_or_candidates_there_is_nothing_to_map_against(self) -> None:
        context = ParseContext(media=None)

        assert (
            map_episode(parse_release("Show - 01.mkv"), structure_hints("Show - 01.mkv"), context)
            == ()
        )

    def test_the_title_picks_the_work_out_of_the_candidates(self) -> None:
        bear = show(season(1, 8), season(2, 10), season(3, 10), title="The Bear", year=2022)
        context = ParseContext(
            media=None,
            candidates=(show(season(1, 6), title="Fleabag", year=2016), bear),
        )
        name = "The.Bear.S03E02.1080p.WEB.mkv"

        candidates = map_episode(parse_release(name), structure_hints(name), context)

        assert best(candidates) == (3, 2, MappingStrategy.EXPLICIT)

    def test_a_title_that_matches_nobody_maps_to_nothing(self) -> None:
        context = ParseContext(
            media=None,
            candidates=(show(season(1, 6), title="Fleabag", year=2016),),
        )
        name = "The.Bear.S03E02.1080p.WEB.mkv"

        assert map_episode(parse_release(name), structure_hints(name), context) == ()

    def test_a_title_without_a_year_is_never_more_than_medium(self) -> None:
        """brief §6.5 的 high 要的是「標題 **+ 年份**精確命中」。"""
        bear = show(season(1, 8), season(2, 10), season(3, 10), title="The Bear", year=2022)
        context = ParseContext(media=None, candidates=(bear,))
        name = "The.Bear.S03E02.1080p.WEB.mkv"

        candidates = map_episode(parse_release(name), structure_hints(name), context)

        assert candidates[0].confidence is Confidence.MEDIUM

    def test_a_title_with_the_year_may_be_high(self) -> None:
        bear = show(season(1, 8), season(2, 10), season(3, 10), title="The Bear", year=2022)
        context = ParseContext(media=None, candidates=(bear,))
        name = "The.Bear.2022.S03E02.1080p.WEB.mkv"

        candidates = map_episode(parse_release(name), structure_hints(name), context)

        assert candidates[0].confidence is Confidence.HIGH


class TestWrongShow:
    def test_a_release_of_another_show_caps_the_confidence(self) -> None:
        """追蹤的是 A、torrent 是 B 時，季集算得再對也是錯的（brief §6.5 的 high 定義）。"""
        candidates = run(
            "The.Bear.S03E02.1080p.WEB.mkv",
            show(season(1, 9), season(2, 7), season(3, 6), title="Squid Game"),
        )

        assert candidates[0].confidence is not Confidence.HIGH


@pytest.mark.parametrize("name", ["Show.mkv", "[Group] Show [1080p][CHT].mkv"])
def test_a_file_without_an_episode_number_maps_to_nothing(name: str) -> None:
    assert run(name, show(season(1, 12), season(2, 12))) == ()
