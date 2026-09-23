"""批次一致性與信心（plan §4.1 的 `score`、brief §6.4 第 4 點、§6.5）。

逐檔的信心由 `map_episode` 給，這一層問的是「這一包**互相**說得通嗎」：同一種模式、
集號連續、數量與 TMDB 吻合就多一句佐證；兩個檔案宣稱同一集就誰都不自動入庫。
"""

from __future__ import annotations

from berth.domain import (
    Confidence,
    FileEntry,
    FileKind,
    MappingStrategy,
    MediaKind,
    MediaSnapshot,
    ParseContext,
    PlanAction,
    PlanItem,
    ReasonCode,
    SeasonSnapshot,
    why,
)
from berth.parser import plan
from berth.parser.score import Decision, score


def context(episode_count: int = 12) -> ParseContext:
    return ParseContext(
        media=MediaSnapshot(
            tmdb_id=1,
            kind=MediaKind.TV,
            title="Show",
            title_en="Show",
            title_original="Show",
            seasons=(
                SeasonSnapshot(season_number=1, name="Season 1", episode_count=episode_count),
            ),
        )
    )


def imported(
    episode: int,
    *,
    path: str = "",
    confidence: Confidence = Confidence.HIGH,
    strategy: MappingStrategy = MappingStrategy.EXPLICIT,
    season: int = 1,
) -> Decision:
    return Decision(
        item=PlanItem(
            rel_path=path or f"Show - {episode:02d}.mkv",
            kind=FileKind.VIDEO,
            action=PlanAction.IMPORT,
            season=season,
            episode_start=episode,
            confidence=confidence,
        ),
        strategy=strategy,
    )


class TestTooManyFiles:
    """brief §6.5 的 low：影片數量與 TMDB 集數明顯不符。"""

    def test_more_files_than_the_season_has_episodes_goes_to_review(self) -> None:
        rows = [imported(number) for number in range(1, 16)]

        items = score(rows, context(episode_count=12))

        assert all(item.action is PlanAction.REVIEW for item in items)
        assert all(item.confidence is Confidence.LOW for item in items)

    def test_it_says_how_far_off_it_is(self) -> None:
        rows = [imported(number) for number in range(1, 16)]

        items = score(rows, context(episode_count=12))

        assert why(ReasonCode.TOO_MANY_FILES, files=15, season=1, episodes=12) in items[0].reasons

    def test_exactly_the_season_is_fine(self) -> None:
        rows = [imported(number) for number in range(1, 13)]

        assert all(item.action is PlanAction.IMPORT for item in score(rows, context(12)))

    def test_a_season_tmdb_says_nothing_about_is_left_alone(self) -> None:
        """TMDB 沒說那一季有幾集時，這條規則沒有分母可用。"""
        rows = [imported(number, season=9) for number in range(1, 30)]

        assert all(item.action is PlanAction.IMPORT for item in score(rows, context(12)))


class TestOddOneOut:
    def test_a_file_read_differently_from_the_rest_drops_to_medium(self) -> None:
        """十一個檔案照 `SxxEyy` 讀、一個靠絕對編號換算——那一個值得被看見（brief §6.5）。"""
        rows = [imported(number) for number in range(1, 12)]
        rows.append(
            imported(12, strategy=MappingStrategy.ABSOLUTE_CUMULATIVE, confidence=Confidence.HIGH)
        )

        items = {item.rel_path: item for item in score(rows, context())}

        assert items["Show - 12.mkv"].confidence is Confidence.MEDIUM
        assert items["Show - 01.mkv"].confidence is Confidence.HIGH

    def test_a_two_file_torrent_read_two_ways_demotes_nobody(self) -> None:
        """誰都不是「其餘的檔案」時沒有少數派可言。"""
        rows = [
            imported(1),
            imported(2, strategy=MappingStrategy.ABSOLUTE_CUMULATIVE),
        ]

        assert all(item.confidence is Confidence.HIGH for item in score(rows, context()))

    def test_one_strategy_for_everybody_changes_nothing(self) -> None:
        rows = [imported(number) for number in range(1, 13)]

        assert all(item.confidence is Confidence.HIGH for item in score(rows, context()))


class TestCompleteSeason:
    def test_covering_the_season_end_to_end_is_worth_saying(self) -> None:
        rows = [imported(number) for number in range(1, 13)]

        items = score(rows, context(episode_count=12))

        assert all(
            any(reason.code is ReasonCode.SEASON_COMPLETE for reason in item.reasons)
            for item in items
        )

    def test_a_partial_batch_says_nothing(self) -> None:
        rows = [imported(number) for number in range(1, 6)]

        items = score(rows, context(episode_count=12))

        assert not any(
            reason.code is ReasonCode.SEASON_COMPLETE for item in items for reason in item.reasons
        )

    def test_a_batch_that_does_not_add_up_says_nothing(self) -> None:
        """十二集的季收到十三個檔案——那不是「數量吻合」。"""
        rows = [imported(number) for number in range(1, 14)]

        items = score(rows, context(episode_count=12))

        assert not any(
            reason.code is ReasonCode.SEASON_COMPLETE for item in items for reason in item.reasons
        )


class TestThroughThePlanner:
    """`plan()` 走完整條路的樣子。這幾條是 benchmark 之外的最小回歸。"""

    def test_two_versions_of_the_same_episode_both_get_imported(self) -> None:
        """不同 tags 就是不同版本，並存在同一季資料夾（brief §7.7）；衝突比的是檔名。"""
        files = [
            FileEntry(rel_path="Show.S01E01.1080p.WEB.mkv", size=2_000_000_000),
            FileEntry(rel_path="Show.S01E01.720p.WEB.mkv", size=1_000_000_000),
        ]

        items = plan("Show.S01.1080p.WEB", files, context())

        assert all(item.action is PlanAction.IMPORT for item in items)
        assert len({item.target_path for item in items}) == 2
