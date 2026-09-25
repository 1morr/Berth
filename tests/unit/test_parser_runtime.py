"""片長驗證（M3 票 15、plan §11.4 的「入庫前後的三道程式檢查」②）。

mediainfo 量到的片長對 TMDB 那一集的片長，差太多的那一列送審核、說出兩個片長。抓的是分類錯誤
（SP / OVA、兩集合併檔被當成一集正片），抓不到同一季裡算錯的集號。短於五分鐘的那種由分類器
自己降成 extra（`parser.classify`），走不到這裡。

容忍是「絕對秒數」與「TMDB 片長的比例」取大的那一個：短的一集比例容易大，長的一集絕對差容易大。
"""

from __future__ import annotations

from berth.domain import (
    Confidence,
    EpisodeSnapshot,
    FileEntry,
    FileKind,
    MediaKind,
    MediaSnapshot,
    PlanAction,
    PlanItem,
    ReasonCode,
    SeasonSnapshot,
    why,
)
from berth.parser import RUNTIME_RATIO, RUNTIME_SLACK, check_runtime


def media(*, minutes: int | None = 24, special: int | None = 12) -> MediaSnapshot:
    """一季 12 集、每集 `minutes` 分鐘，S00E01 是 `special` 分鐘的特典。"""
    return MediaSnapshot(
        tmdb_id=1,
        kind=MediaKind.TV,
        title="作品",
        title_en="Show",
        title_original="Show",
        seasons=(
            SeasonSnapshot(
                season_number=0,
                episode_count=1,
                episodes=(EpisodeSnapshot(episode_number=1, runtime=special),),
            ),
            SeasonSnapshot(
                season_number=1,
                episode_count=12,
                episodes=tuple(
                    EpisodeSnapshot(episode_number=number, runtime=minutes)
                    for number in range(1, 13)
                ),
            ),
        ),
    )


def item(episode: int, *, end: int | None = None, season: int = 1) -> PlanItem:
    return PlanItem(
        rel_path=f"[Group] Show - {episode:02d}.mkv",
        kind=FileKind.VIDEO,
        action=PlanAction.IMPORT,
        season=season,
        episode_start=episode,
        episode_end=end,
        confidence=Confidence.HIGH,
        target_path=f"Show/Season {season:02d}/Show S{season:02d}E{episode:02d}.mkv",
        reasons=(why(ReasonCode.SEASON_FROM_JOB, season=season),),
    )


def measured(row: PlanItem, seconds: int | None) -> FileEntry:
    return FileEntry(rel_path=row.rel_path, size=1, duration_s=seconds)


def check(row: PlanItem, seconds: int | None, snapshot: MediaSnapshot | None = None) -> PlanItem:
    [found] = check_runtime([row], [measured(row, seconds)], snapshot or media())
    return found


#: 各長度的一集容忍幾秒：5 分鐘靠絕對秒數，24 與 60 分鐘靠比例。寫死數字而不是重算公式——
#: 公式寫錯時測試不該跟著一起錯。
TOLERANCE = {5: 180, 24: 216, 60: 540}


class TestTooFarOff:
    def test_a_matching_episode_passes_untouched(self) -> None:
        assert check(item(3), 24 * 60 - 30) == item(3)

    def test_a_special_parsed_as_an_episode_is_held_with_both_runtimes(self) -> None:
        """12 分鐘的 SP 被讀成第 3 集：量到的只有一半。"""
        found = check(item(3), 12 * 60 + 5)

        assert found.action is PlanAction.REVIEW
        assert found.reasons[-1] == why(
            ReasonCode.RUNTIME_MISMATCH, episode="S01E03", measured="12:05", minutes=24
        )

    def test_two_episodes_merged_into_one_file_are_held(self) -> None:
        """合併檔被讀成單集：量到的是兩倍長。"""
        found = check(item(3), 48 * 60)

        assert found.action is PlanAction.REVIEW
        assert found.reasons[-1].params["measured"] == "48:00"

    def test_an_hour_long_file_says_its_hours(self) -> None:
        found = check(item(3), 3600 + 2 * 60 + 3)

        assert found.reasons[-1].params["measured"] == "1:02:03"

    def test_a_held_row_keeps_its_proposal(self) -> None:
        """停下來只是先問一句：核准就照這一格入庫（`parser.promote`）。"""
        found = check(item(3), 48 * 60)

        assert (found.season, found.episode_start, found.target_path, found.confidence) == (
            1,
            3,
            item(3).target_path,
            Confidence.HIGH,
        )

    def test_a_range_is_checked_against_the_episodes_it_covers(self) -> None:
        """`S01E03-E04` 的合併檔本來就該是兩集長。"""
        assert check(item(3, end=4), 48 * 60).action is PlanAction.IMPORT
        assert check(item(3, end=4), 24 * 60).action is PlanAction.REVIEW

    def test_a_special_is_checked_against_its_own_runtime(self) -> None:
        """S00 的片長各集不同；比的是 TMDB 上那一集。"""
        assert check(item(1, season=0), 12 * 60).action is PlanAction.IMPORT
        assert check(item(1, season=0), 24 * 60).action is PlanAction.REVIEW


class TestThreshold:
    """容忍 = max(`RUNTIME_SLACK`, `RUNTIME_RATIO` × TMDB 片長)，邊界上那一秒還算對。"""

    def test_exactly_the_tolerance_off_passes(self) -> None:
        for minutes in (5, 24, 60):
            snapshot = media(minutes=minutes)
            expected = minutes * 60

            assert check(item(3), expected + TOLERANCE[minutes], snapshot).action is (
                PlanAction.IMPORT
            )
            assert check(item(3), expected - TOLERANCE[minutes], snapshot).action is (
                PlanAction.IMPORT
            )

    def test_one_second_past_the_tolerance_is_held(self) -> None:
        for minutes in (5, 24, 60):
            snapshot = media(minutes=minutes)
            expected = minutes * 60

            assert check(item(3), expected + TOLERANCE[minutes] + 1, snapshot).action is (
                PlanAction.REVIEW
            )
            assert check(item(3), expected - TOLERANCE[minutes] - 1, snapshot).action is (
                PlanAction.REVIEW
            )

    def test_short_episodes_lean_on_the_slack_and_long_ones_on_the_ratio(self) -> None:
        """兩個條件都要：只看比例的話五分鐘的短篇差幾十秒就被擋，只看秒數的話一小時的劇差不出來。"""
        assert TOLERANCE[5] == RUNTIME_SLACK
        assert TOLERANCE[60] == 3600 * RUNTIME_RATIO


class TestMissingFacts:
    """TMDB 沒有片長時跳過、記一筆；mediainfo 沒量到（失敗、或 pre-plan 還在下載）不擋也不記。"""

    def test_no_runtime_on_tmdb_passes_with_a_note(self) -> None:
        found = check(item(3), 12 * 60, media(minutes=None))

        assert found.action is PlanAction.IMPORT
        assert found.reasons[-1] == why(ReasonCode.RUNTIME_MISSING, episode="S01E03")

    def test_a_range_with_one_runtime_missing_is_not_checked(self) -> None:
        snapshot = media().model_copy(
            update={
                "seasons": (
                    SeasonSnapshot(
                        season_number=1,
                        episodes=(
                            EpisodeSnapshot(episode_number=3, runtime=24),
                            EpisodeSnapshot(episode_number=4),
                        ),
                    ),
                )
            }
        )

        found = check(item(3, end=4), 24 * 60, snapshot)

        assert found.action is PlanAction.IMPORT
        assert found.reasons[-1] == why(ReasonCode.RUNTIME_MISSING, episode="S01E03-E04")

    def test_an_episode_tmdb_does_not_list_is_a_missing_runtime(self) -> None:
        found = check(item(30), 12 * 60)

        assert found.reasons[-1] == why(ReasonCode.RUNTIME_MISSING, episode="S01E30")

    def test_an_unmeasured_file_is_left_alone(self) -> None:
        """§8.7「失敗不阻擋」；pre-plan 那一輪也是 `None`，逐列記一筆只是雜訊。"""
        assert check(item(3), None) == item(3)

    def test_a_zero_measurement_is_left_alone(self) -> None:
        """`0` 是 mediainfo 讀得到檔案但說不出多長（`MediaInfoSummary`）。"""
        assert check(item(3), 0) == item(3)

    def test_without_a_snapshot_nothing_changes(self) -> None:
        assert check_runtime([item(3)], [measured(item(3), 12 * 60)], None) == (item(3),)

    def test_rows_that_are_not_episodes_are_left_alone(self) -> None:
        extra = item(3).model_copy(update={"action": PlanAction.EXTRA, "season": None})
        held = item(3).model_copy(update={"action": PlanAction.REVIEW})

        assert check_runtime([extra, held], [measured(extra, 12 * 60)], media()) == (extra, held)
