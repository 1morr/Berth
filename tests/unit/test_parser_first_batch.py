"""第一批的證據夠不夠強（M4 票 11、`parser.first_batch`）。

**逐條件雙向**：`TestEachCondition` 從一份會被擔保的第一批出發，每一次只拿掉一個條件，它就不再被
擔保；`TestRealReadings` 用真的解析器走一遍，守住「解析器對一般的每週發佈給的理由」沒有跑出白名單
（跑出去的話跳過會安靜地失效），以及 split-cour、虛擬季、新一季被當成第一季仍然不算。
`TestCumulativeConditions`、`TestCumulativeReadings` 對寫明季號的累計編號（M5.5 票 05）
做同樣兩件事。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from berth.domain import (
    Confidence,
    EpisodeSnapshot,
    FileEntry,
    FileKind,
    ItemReason,
    MediaKind,
    MediaSnapshot,
    ParseContext,
    PlanAction,
    PlanItem,
    SeasonSnapshot,
    why,
)
from berth.domain import ReasonCode as Code
from berth.parser import (
    BEHIND_LATEST,
    RELEASE_TOLERANCE,
    SIMULCAST_LEAD,
    check_airing,
    plan,
    vouch_first_batch,
)
from berth.parser.planner import hold

#: 第一季第 1 集播出的那一天；每週一集。
FIRST = date(2026, 7, 5)
TORRENT = "[ANi] BLACK TORCH - 03 [1080P][Baha][WEB-DL][AAC AVC][CHT]"
VIDEO = f"{TORRENT}.mp4"


def _aired(number: int, *, gap: int = 0) -> date:
    return FIRST + timedelta(weeks=number - 1 + (gap if number > 12 else 0))


def media(*, episodes: int = 12, gap: int = 0, seasons: int = 1) -> MediaSnapshot:
    """單季、每週一集。`episodes = 24, gap = 13` 是 TMDB 把 split-cour 併成一季的形狀。"""
    blocks = [
        SeasonSnapshot(
            season_number=1,
            episode_count=episodes,
            episodes=tuple(
                EpisodeSnapshot(episode_number=n, air_date=_aired(n, gap=gap))
                for n in range(1, episodes + 1)
            ),
        )
    ]
    if seasons == 2:
        start = _aired(episodes, gap=gap) + timedelta(weeks=30)
        blocks.append(
            SeasonSnapshot(
                season_number=2,
                episode_count=12,
                episodes=tuple(
                    EpisodeSnapshot(episode_number=n, air_date=start + timedelta(weeks=n - 1))
                    for n in range(1, 13)
                ),
            )
        )
    return MediaSnapshot(
        tmdb_id=1,
        kind=MediaKind.TV,
        title="BLACK TORCH",
        title_en="BLACK TORCH",
        title_original="BLACK TORCH",
        seasons=tuple(blocks),
    )


def published(number: int, *, gap: int = 0, days: int = 1) -> datetime:
    """第 `number` 集播出之後 `days` 天發佈。"""
    return datetime.combine(
        _aired(number, gap=gap) + timedelta(days=days), datetime.min.time(), UTC
    )


def episode(**update: object) -> PlanItem:
    """一列會被擔保的正片：只寫集號、單季、標題完全相同、發佈時間落在第一輪。"""
    row = PlanItem(
        rel_path=VIDEO,
        kind=FileKind.VIDEO,
        action=PlanAction.IMPORT,
        season=1,
        episode_start=3,
        episode_end=3,
        confidence=Confidence.MEDIUM,
        target_path="BLACK TORCH/Season 01/BLACK TORCH - S01E03.mp4",
        reasons=(
            why(Code.PUBLISHED_IN_RUN, published="2026-07-20", run=1, runs=1, episode="S01E01"),
            why(Code.TITLE_EXACT, title="BLACK TORCH"),
        ),
    )
    return row.model_copy(update=update)


def subtitle() -> PlanItem:
    return PlanItem(
        rel_path=f"{TORRENT}.cht.ass",
        kind=FileKind.SUBTITLE,
        action=PlanAction.SUBTITLE,
        season=1,
        episode_start=3,
        episode_end=3,
        confidence=Confidence.MEDIUM,
        reasons=(why(Code.SUBTITLE_FOLLOWS, video=VIDEO),),
    )


def vouch(
    items: tuple[PlanItem, ...],
    *,
    snapshot: MediaSnapshot | None = None,
    at: datetime | None = None,
    season_hint: int | None = None,
    episode_offset: int | None = None,
    torrent: str = TORRENT,
) -> tuple[tuple[int, int, int], ...] | None:
    return vouch_first_batch(
        torrent,
        items,
        snapshot if snapshot is not None else media(),
        at if at is not None else published(3),
        season_hint=season_hint,
        episode_offset=episode_offset,
    )


class TestEachCondition:
    def test_the_baseline_is_vouched_for(self) -> None:
        assert vouch((episode(), subtitle())) == ((1, 3, 3),)

    def test_a_season_set_on_the_series(self) -> None:
        assert vouch((episode(),), season_hint=1) is None

    def test_an_offset_set_on_the_series(self) -> None:
        assert vouch((episode(),), episode_offset=0) is None

    def test_no_media(self) -> None:
        assert (
            vouch_first_batch(
                TORRENT, (episode(),), None, published(3), season_hint=None, episode_offset=None
            )
            is None
        )

    @pytest.mark.parametrize("action", [PlanAction.EXTRA, PlanAction.UNMATCHED, PlanAction.REVIEW])
    def test_a_row_it_cannot_vouch_for(self, action: PlanAction) -> None:
        other = episode(rel_path="NCOP.mkv", action=action, season=None, episode_start=None)
        assert vouch((episode(), other)) is None

    def test_skipped_files_do_not_count(self) -> None:
        """字型、海報這種略過的檔案不進媒體庫，不必擔保。"""
        font = episode(
            rel_path="Fonts/a.ttf", kind=FileKind.FONT, action=PlanAction.SKIP, season=None
        )
        assert vouch((episode(), font)) == ((1, 3, 3),)

    def test_nothing_but_subtitles(self) -> None:
        assert vouch((subtitle(),)) is None

    def test_held_by_the_runtime_check(self) -> None:
        held = hold(
            episode(), why(Code.RUNTIME_MISMATCH, episode="S01E03", measured="3:02", minutes=24)
        )
        assert vouch((held,)) is None

    def test_runtime_not_on_tmdb_is_fine(self) -> None:
        missing = episode(reasons=(*episode().reasons, why(Code.RUNTIME_MISSING, episode="S01E03")))
        assert vouch((missing,)) == ((1, 3, 3),)

    def test_low_confidence(self) -> None:
        assert vouch((episode(confidence=Confidence.LOW),)) is None

    @pytest.mark.parametrize(
        "reason",
        [
            why(Code.SEASON_FROM_JOB, season=1),
            why(Code.SEASON_FROM_ARC, arc="篇", season=1),
            why(Code.ABSOLUTE_CUMULATIVE, number="3", episode="S01E03"),
            why(Code.AIR_DATE_RUN, season=1, runs=2, episode="S01E01"),
            why(Code.SERIES_CORRECTED, season=1, offset="+0"),
            why(Code.SET_BY_USER),
            why(Code.TITLE_MISMATCH, release_title="X", title="BLACK TORCH"),
        ],
        ids=lambda reason: reason.code.value,
    )
    def test_a_reason_outside_the_list(self, reason: ItemReason) -> None:
        tainted = episode(reasons=(*episode().reasons, reason))
        assert vouch((tainted,)) is None

    def test_the_file_wrote_another_number(self) -> None:
        """集號被換算過（offset、絕對編號、重數推測）：對到的不是檔名寫的那一集。第 15 集在
        TMDB 上、發佈時剛播，只差在檔名寫的是 03。"""
        long = media(episodes=24)
        moved = episode(episode_start=15, episode_end=15)
        assert vouch((moved,), snapshot=long, at=published(15)) is None
        assert vouch((episode(),), snapshot=long) == ((1, 3, 3),)

    def test_an_unwritten_season_that_is_not_the_first(self) -> None:
        second = media(seasons=2)
        row = episode(season=2)
        aired = second.episode(2, 3)
        assert aired is not None and aired.air_date is not None
        at = datetime.combine(aired.air_date + timedelta(days=1), datetime.min.time(), UTC)
        assert vouch((row,), snapshot=second, at=at) is None
        written = episode(season=2, reasons=(why(Code.SEASON_FROM_RELEASE, season=2),))
        assert vouch((written,), snapshot=second, at=at) == ((2, 3, 3),)

    def test_no_published_time(self) -> None:
        assert (
            vouch_first_batch(
                TORRENT, (episode(),), media(), None, season_hint=None, episode_offset=None
            )
            is None
        )

    def test_no_air_date_on_tmdb(self) -> None:
        blank = media().model_copy(
            update={
                "seasons": (
                    SeasonSnapshot(
                        season_number=1,
                        episode_count=12,
                        episodes=tuple(EpisodeSnapshot(episode_number=n) for n in range(1, 13)),
                    ),
                )
            }
        )
        assert vouch((episode(),), snapshot=blank) is None

    def test_released_before_it_aired(self) -> None:
        """上緣是播出日比對放行照字面的那一個：容忍加上地上波先行（M5.5 票 04）。"""
        edge = (RELEASE_TOLERANCE + SIMULCAST_LEAD).days
        assert vouch((episode(),), at=published(3, days=-edge - 1)) is None
        assert vouch((episode(),), at=published(3, days=-edge)) == ((1, 3, 3),)

    def test_a_simulcast_lead_noted_by_the_air_date_check(self) -> None:
        ahead = why(
            Code.RELEASED_AHEAD_OF_AIRING,
            published="2026-07-12",
            episode="S01E03",
            aired="2026-07-19",
        )
        row = episode(reasons=(*episode().reasons, ahead))
        assert vouch((row,), at=published(3, days=-7)) == ((1, 3, 3),)

    def test_not_just_aired(self) -> None:
        """一集播完很久之後才發的（補檔、BD、或新一季被讀成第一季）。"""
        late = published(3, days=BEHIND_LATEST.days + 1)
        assert vouch((episode(),), at=late) is None
        assert vouch((episode(),), at=published(3, days=BEHIND_LATEST.days)) == ((1, 3, 3),)


def _read(
    name: str, snapshot: MediaSnapshot, at: datetime
) -> tuple[tuple[int, int, int], ...] | None:
    """真的解析器 + 播出日比對（規劃時的那一份），再問它擔不擔保。"""
    context = ParseContext(media=snapshot, published_at=at)
    items = plan(name, (FileEntry(rel_path=f"{name}.mkv", size=500_000_000),), context)
    checked = check_airing(name, items, snapshot, at, from_series=True)
    return vouch_first_batch(name, checked, snapshot, at, season_hint=None, episode_offset=None)


class TestRealReadings:
    def test_only_a_number_on_a_single_season_show(self) -> None:
        assert _read("[ANi] BLACK TORCH - 03 [1080P][Baha][WEB-DL]", media(), published(3)) == (
            (1, 3, 3),
        )

    def test_a_simulcast_lead_of_eight_days(self) -> None:
        """平台先播一週、TMDB 的深夜檔日期再晚一天：比對放行，第一批也認（brief §20.27）。"""
        name = "[LoliHouse] BLACK TORCH - 03 [WebRip 1080p HEVC-10bit AAC]"
        assert _read(name, media(), published(3, days=-8)) == ((1, 3, 3),)

    def test_a_written_season(self) -> None:
        name = "[Nekomoe kissaten&LoliHouse] BLACK TORCH S01E03 [WebRip 1080p HEVC-10bit AAC]"
        assert _read(name, media(), published(3)) == ((1, 3, 3),)

    def test_split_cour_restarting_from_one(self) -> None:
        """TMDB 一季 24 集、中間停 13 週，字幕組第二個 cour 從 01 重數：照字面是第 1 集，播出日比對
        擋在審核（M3 e2e 的 Re:ZERO 就是這一種）。"""
        split = media(episodes=24, gap=13)
        name = "[LoliHouse] BLACK TORCH - 01 [WebRip 1080p]"
        assert _read(name, split, published(13, gap=13)) is None

    def test_a_virtual_season_restarting_from_one(self) -> None:
        """中間停超過 180 天（虛擬季）：解析器以發佈時間推測成第 13 集（`published_run`），播出日
        也對得上——擋下它的是「對到的不是檔名寫的集號」。"""
        split = media(episodes=24, gap=30)
        name = "[LoliHouse] BLACK TORCH - 01 [WebRip 1080p]"
        assert _read(name, split, published(13, gap=30)) is None

    def test_a_new_season_tmdb_has_not_added_yet(self) -> None:
        """第一季早就播完、新一季還不在 TMDB 上：照字面讀成第一季第 3 集，但那一集不是剛播。"""
        later = published(12) + timedelta(weeks=40)
        assert _read("[ANi] BLACK TORCH - 03 [1080P][Baha][WEB-DL]", media(), later) is None

    def test_a_number_on_a_show_with_two_seasons(self) -> None:
        """只寫集號、TMDB 有兩季、發佈在第二季播出時：季號是推出來的，不是字面。"""
        second = media(seasons=2)
        aired = second.episode(2, 3)
        assert aired is not None and aired.air_date is not None
        at = datetime.combine(aired.air_date + timedelta(days=1), datetime.min.time(), UTC)
        assert _read("[ANi] BLACK TORCH - 03 [1080P][Baha][WEB-DL]", second, at) is None


# --- 累計編號（M5.5 票 05） -------------------------------------------------------------

#: 夜櫻家的大作戰：TMDB 第一季 27 集，第二季每週一集；LoliHouse 的集號從第一季一路數下來，
#: 40 是 S02E13（研究 `review-queue-2026-11-01.md` §2）。
YOZAKURA_S2 = date(2026, 7, 4)
YOZAKURA = "[LoliHouse] 夜樱家的大作战 第二季 / Yozakura-san Chi no Daisakusen Season 2 - {number} [WebRip 1080p HEVC-10bit AAC][简繁内封字幕]"  # noqa: E501  # 真的發佈名，不拆


def yozakura() -> MediaSnapshot:
    def block(number: int, count: int, start: date, aired: int) -> SeasonSnapshot:
        return SeasonSnapshot(
            season_number=number,
            episode_count=count,
            episodes=tuple(
                EpisodeSnapshot(episode_number=n, air_date=start + timedelta(weeks=n - 1))
                for n in range(1, aired + 1)
            ),
        )

    return MediaSnapshot(
        tmdb_id=2,
        kind=MediaKind.TV,
        title="夜櫻家的大作戰",
        title_en="Mission: Yozakura Family",
        title_original="夜桜さんちの大作戦",
        titles=("Yozakura-san Chi no Daisakusen", "夜樱家的大作战"),
        seasons=(
            block(1, 27, date(2024, 4, 6), 27),
            block(2, 24, YOZAKURA_S2, 15),
        ),
    )


def yozakura_aired(episode: int, *, days: int = 1) -> datetime:
    """第二季第 `episode` 集播出之後 `days` 天發佈。"""
    aired = YOZAKURA_S2 + timedelta(weeks=episode - 1, days=days)
    return datetime.combine(aired, datetime.min.time(), UTC)


class TestCumulativeReadings:
    """真的解析器：季號寫明、集號從第一季數下來的，第一批擔保；其他絕對編號仍等人。"""

    def test_a_written_season_counted_from_the_first(self) -> None:
        name = YOZAKURA.format(number=40)
        assert _read(name, yozakura(), yozakura_aired(13)) == ((2, 13, 13),)

    def test_a_cumulative_number_without_a_written_season(self) -> None:
        """只寫集號的絕對編號：季號是換算推出來的，仍等人。"""
        name = "[LoliHouse] Yozakura-san Chi no Daisakusen - 40 [WebRip 1080p HEVC-10bit AAC]"
        assert _read(name, yozakura(), yozakura_aired(13)) is None

    def test_a_cumulative_number_long_after_it_aired(self) -> None:
        name = YOZAKURA.format(number=40)
        late = yozakura_aired(13, days=BEHIND_LATEST.days + 1)
        assert _read(name, yozakura(), late) is None


def cumulative(**update: object) -> PlanItem:
    """一列會被擔保的累計編號：季號寫明、40 換算成 S02E13。"""
    name = YOZAKURA.format(number=40)
    row = PlanItem(
        rel_path=f"{name}.mkv",
        kind=FileKind.VIDEO,
        action=PlanAction.IMPORT,
        season=2,
        episode_start=13,
        episode_end=13,
        confidence=Confidence.MEDIUM,
        reasons=(
            why(Code.SEASON_FROM_RELEASE, season=2),
            why(Code.ABSOLUTE_CUMULATIVE, number=40, episode="S02E13"),
            why(Code.TITLE_EXACT, title="Yozakura-san Chi no Daisakusen"),
        ),
    )
    return row.model_copy(update=update)


def vouch_cumulative(
    row: PlanItem, *, at: datetime | None = None, number: int = 40
) -> tuple[tuple[int, int, int], ...] | None:
    return vouch(
        (row,),
        snapshot=yozakura(),
        at=at if at is not None else yozakura_aired(13),
        torrent=YOZAKURA.format(number=number),
    )


class TestCumulativeConditions:
    """從一列會被擔保的累計編號出發，每次只拿掉一個條件。"""

    def test_the_baseline_is_vouched_for(self) -> None:
        assert vouch_cumulative(cumulative()) == ((2, 13, 13),)

    def test_a_season_set_on_the_series(self) -> None:
        name = YOZAKURA.format(number=40)
        assert (
            vouch(
                (cumulative(),),
                snapshot=yozakura(),
                at=yozakura_aired(13),
                torrent=name,
                season_hint=2,
            )
            is None
        )

    def test_the_file_number_is_not_the_count_so_far(self) -> None:
        """檔名寫 41、對到 S02E13：前面 27 集加 13 是 40，對不上。"""
        row = cumulative(rel_path=f"{YOZAKURA.format(number=41)}.mkv")
        assert vouch_cumulative(row, number=41) is None

    @pytest.mark.parametrize(
        "reason",
        [
            why(Code.ABSOLUTE_GROUP, number=40, episode="S02E13"),
            why(Code.ABSOLUTE_WITHIN_FIRST_SEASON, number=40, episodes=27, season=1),
            why(Code.AIR_DATE_RUN, season=2, runs=2, episode="S02E01"),
            why(Code.PUBLISHED_IN_RUN, published="2026-09-27", run=2, runs=2, episode="S02E01"),
            why(
                Code.RELEASED_AHEAD_OF_AIRING,
                published="2026-09-20",
                episode="S02E13",
                aired="2026-09-26",
            ),
            why(Code.SEASON_FROM_JOB, season=2),
        ],
        ids=lambda reason: reason.code.value,
    )
    def test_a_reason_outside_the_list(self, reason: ItemReason) -> None:
        tainted = cumulative(reasons=(*cumulative().reasons, reason))
        assert vouch_cumulative(tainted) is None

    def test_a_season_written_on_the_folder(self) -> None:
        folder = cumulative(
            reasons=(why(Code.SEASON_FROM_FOLDER, season=2), *cumulative().reasons[1:])
        )
        assert vouch_cumulative(folder) == ((2, 13, 13),)

    def test_the_written_season_is_another(self) -> None:
        """發佈名寫第三季、換算落在第二季：兩者沒有互相印證。"""
        other = cumulative(
            reasons=(why(Code.SEASON_FROM_RELEASE, season=3), *cumulative().reasons[1:])
        )
        assert vouch_cumulative(other) is None

    def test_no_written_season(self) -> None:
        bare = cumulative(reasons=cumulative().reasons[1:])
        assert vouch_cumulative(bare) is None

    def test_low_confidence(self) -> None:
        assert vouch_cumulative(cumulative(confidence=Confidence.LOW)) is None

    def test_released_before_it_aired(self) -> None:
        """上緣維持兩天：地上波先行的寬限只給照字面的列。"""
        edge = RELEASE_TOLERANCE.days
        assert vouch_cumulative(cumulative(), at=yozakura_aired(13, days=-edge - 1)) is None
        assert vouch_cumulative(cumulative(), at=yozakura_aired(13, days=-edge)) == ((2, 13, 13),)
