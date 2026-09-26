"""第一批的證據夠不夠強（M4 票 11、`parser.first_batch`）。

**逐條件雙向**：`TestEachCondition` 從一份會被擔保的第一批出發，每一次只拿掉一個條件，它就不再被
擔保；`TestRealReadings` 用真的解析器走一遍，守住「解析器對一般的每週發佈給的理由」沒有跑出白名單
（跑出去的話跳過會安靜地失效），以及 split-cour、虛擬季、新一季被當成第一季仍然不算。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from berth.domain import (
    CollectionType,
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
from berth.parser import BEHIND_LATEST, RELEASE_TOLERANCE, check_airing, plan, vouch_first_batch
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
        assert vouch((episode(),), at=published(3, days=-3)) is None
        assert vouch((episode(),), at=published(3, days=-RELEASE_TOLERANCE.days)) == ((1, 3, 3),)

    def test_not_just_aired(self) -> None:
        """一集播完很久之後才發的（補檔、BD、或新一季被讀成第一季）。"""
        late = published(3, days=BEHIND_LATEST.days + 1)
        assert vouch((episode(),), at=late) is None
        assert vouch((episode(),), at=published(3, days=BEHIND_LATEST.days)) == ((1, 3, 3),)


def _read(
    name: str, snapshot: MediaSnapshot, at: datetime
) -> tuple[tuple[int, int, int], ...] | None:
    """真的解析器 + 播出日比對（規劃時的那一份），再問它擔不擔保。"""
    context = ParseContext(
        media=snapshot, route_collection_type=CollectionType.TVSHOWS, published_at=at
    )
    items = plan(name, (FileEntry(rel_path=f"{name}.mkv", size=500_000_000),), context)
    checked = check_airing(items, snapshot, at, from_series=True)
    return vouch_first_batch(name, checked, snapshot, at, season_hint=None, episode_offset=None)


class TestRealReadings:
    def test_only_a_number_on_a_single_season_show(self) -> None:
        assert _read("[ANi] BLACK TORCH - 03 [1080P][Baha][WEB-DL]", media(), published(3)) == (
            (1, 3, 3),
        )

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
