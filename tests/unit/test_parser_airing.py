"""播出日比對（M3 票 14、plan §11.4 的「入庫前後的三道程式檢查」①）。

規則層有把握卻算錯的集數，靠發佈時間抓：

- **規則一**：發佈早於換算出的那一集的播出日、超過兩天容忍，就一定是算錯（換算過頭）。
- **規則二**：連載中的 RSS Series 對到的那一集，比同一部作品在發佈時最近播出的一集早很多
  （split-cour 從 01 重數而 offset 沒設）。

兩條都只把那一列送審核、說出兩個日期；對得上的原樣放行，缺資料的不擋、記一筆。
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from berth.domain import (
    Confidence,
    EpisodeSnapshot,
    FileKind,
    MediaKind,
    MediaSnapshot,
    PlanAction,
    PlanItem,
    ReasonCode,
    SeasonSnapshot,
    why,
)
from berth.parser import BEHIND_LATEST, check_airing

#: 發佈名。`item()` 的季號是 Series 給的（`season_from_job`），不算照字面，容忍兩天；
#: `literal()` 的列照字面，容忍九天（`TestSimulcastLead`）。
TORRENT = "[Group] Show - 05"

#: 一季 24 集、每週一集，兩個 cour 中間停 13 週（TMDB 把 split-cour 併成單季的那種形狀）。
FIRST = date(2026, 1, 3)


def _aired(number: int) -> date:
    gap = 0 if number <= 12 else 13
    return FIRST + timedelta(weeks=number - 1 + gap)


def media(*, missing: frozenset[int] = frozenset()) -> MediaSnapshot:
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
                episodes=(EpisodeSnapshot(episode_number=1, air_date=date(2025, 12, 1)),),
            ),
            SeasonSnapshot(
                season_number=1,
                episode_count=24,
                episodes=tuple(
                    EpisodeSnapshot(
                        episode_number=number,
                        air_date=None if number in missing else _aired(number),
                    )
                    for number in range(1, 25)
                ),
            ),
        ),
    )


def two_episodes(gap: timedelta) -> MediaSnapshot:
    """第 1 集在 `FIRST`、第 2 集在 `gap` 之後：規則二的門檻邊界用。"""
    return media().model_copy(
        update={
            "seasons": (
                SeasonSnapshot(
                    season_number=1,
                    episode_count=2,
                    episodes=(
                        EpisodeSnapshot(episode_number=1, air_date=FIRST),
                        EpisodeSnapshot(episode_number=2, air_date=FIRST + gap),
                    ),
                ),
            )
        }
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


def at(day: date, hour: int = 12) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=UTC)


def codes(found: PlanItem) -> list[ReasonCode]:
    return [reason.code for reason in found.reasons]


class TestReleasedBeforeAiring:
    """規則一：發佈早於播出日（容忍兩天）一定算錯。"""

    def test_a_release_on_the_air_date_passes(self) -> None:
        [found] = check_airing(TORRENT, [item(5)], media(), at(_aired(5)), from_series=False)

        assert found == item(5)

    def test_two_days_early_is_still_tolerated(self) -> None:
        """日本深夜檔跨日、UTC 對當地日期，兩天之內都是同一次播出。"""
        [found] = check_airing(
            TORRENT, [item(5)], media(), at(_aired(5) - timedelta(days=2)), from_series=False
        )

        assert found.action is PlanAction.IMPORT

    def test_three_days_early_is_held_with_both_dates(self) -> None:
        published = at(_aired(5) - timedelta(days=3))

        [found] = check_airing(TORRENT, [item(5)], media(), published, from_series=False)

        assert found.action is PlanAction.REVIEW
        assert found.reasons[-1] == why(
            ReasonCode.RELEASED_BEFORE_AIRING,
            published=published.date().isoformat(),
            episode="S01E05",
            aired=_aired(5).isoformat(),
        )

    def test_a_held_row_keeps_its_proposal(self) -> None:
        """停下來只是先問一句：核准就照這一格入庫（`parser.promote`），所以季集與路徑都留著。"""
        [found] = check_airing(TORRENT, [item(13)], media(), at(_aired(5)), from_series=False)

        assert (found.season, found.episode_start, found.target_path, found.confidence) == (
            1,
            13,
            item(13).target_path,
            Confidence.HIGH,
        )

    def test_a_range_is_checked_by_its_last_episode(self) -> None:
        """合集換算過頭時，最後一集還沒播。"""
        [found] = check_airing(
            TORRENT, [item(1, end=13)], media(), at(_aired(12)), from_series=False
        )

        assert found.action is PlanAction.REVIEW
        assert found.reasons[-1].params["episode"] == "S01E01-E13"

    def test_it_applies_to_a_manual_download_too(self) -> None:
        """手動送單的整季合集一樣會換算過頭；規則一不看是不是 RSS。"""
        [found] = check_airing(TORRENT, [item(24)], media(), at(_aired(12)), from_series=False)

        assert found.action is PlanAction.REVIEW


def literal(episode: int, **update: object) -> PlanItem:
    """照字面的一列：只寫集號、單季作品、對到的就是檔名寫的那一集。"""
    row = PlanItem(
        rel_path=f"[Group] Show - {episode:02d} [1080p].mkv",
        kind=FileKind.VIDEO,
        action=PlanAction.IMPORT,
        season=1,
        episode_start=episode,
        episode_end=episode,
        confidence=Confidence.MEDIUM,
        target_path=f"Show/Season 01/Show S01E{episode:02d}.mkv",
        reasons=(why(ReasonCode.SINGLE_SEASON), why(ReasonCode.TITLE_EXACT, title="Show")),
    )
    return row.model_copy(update=update)


def ahead(days: int) -> datetime:
    """第 5 集的 TMDB 播出日往前 `days` 天發佈。"""
    return at(_aired(5) - timedelta(days=days))


class TestSimulcastLead:
    """地上波先行（brief §20.27）：照字面的列多容忍 `SIMULCAST_LEAD`，有換算的列維持兩天。"""

    def test_a_literal_row_eight_days_ahead_passes_with_both_dates(self) -> None:
        [found] = check_airing(TORRENT, [literal(5)], media(), ahead(8), from_series=True)

        assert found.action is PlanAction.IMPORT
        assert found.reasons[-1] == why(
            ReasonCode.RELEASED_AHEAD_OF_AIRING,
            published=ahead(8).date().isoformat(),
            episode="S01E05",
            aired=_aired(5).isoformat(),
        )

    def test_nine_days_is_the_edge(self) -> None:
        [nine] = check_airing(TORRENT, [literal(5)], media(), ahead(9), from_series=True)
        [ten] = check_airing(TORRENT, [literal(5)], media(), ahead(10), from_series=True)

        assert nine.action is PlanAction.IMPORT
        assert ten.action is PlanAction.REVIEW
        assert ten.reasons[-1].code is ReasonCode.RELEASED_BEFORE_AIRING

    def test_within_two_days_says_nothing(self) -> None:
        """跨日的那兩天本來就是同一次播出，不是先行。"""
        [found] = check_airing(TORRENT, [literal(5)], media(), ahead(2), from_series=True)

        assert found == literal(5)

    def test_a_worked_out_row_seven_days_ahead_is_still_held(self) -> None:
        """換算差一集也剛好早一週：只看日期分不開先行與算錯。"""
        cumulative = literal(
            5,
            rel_path="[Group] Show - 29 [1080p].mkv",
            reasons=(why(ReasonCode.ABSOLUTE_CUMULATIVE, number=29, episode="S01E05"),),
        )

        [found] = check_airing(TORRENT, [cumulative], media(), ahead(7), from_series=True)

        assert found.action is PlanAction.REVIEW
        assert found.reasons[-1].code is ReasonCode.RELEASED_BEFORE_AIRING

    def test_an_offset_from_the_series_is_not_literal(self) -> None:
        """檔名寫 04、Series 的 offset 加一變成 05：對到的不是檔名寫的那一集。"""
        shifted = literal(5, rel_path="[Group] Show - 04 [1080p].mkv")

        [found] = check_airing(TORRENT, [shifted], media(), ahead(7), from_series=True)

        assert found.action is PlanAction.REVIEW

    def test_a_season_from_the_series_is_not_literal(self) -> None:
        [found] = check_airing(TORRENT, [item(5)], media(), ahead(7), from_series=True)

        assert found.action is PlanAction.REVIEW

    def test_a_bare_number_mapped_past_the_first_season_is_not_literal(self) -> None:
        """只寫集號、季號沒寫明，卻對到第一季以外：那個季號是推出來的。"""
        two = media().model_copy(
            update={
                "seasons": (
                    *media().seasons,
                    media().seasons[1].model_copy(update={"season_number": 2}),
                )
            }
        )
        second = literal(5, season=2)

        [found] = check_airing(TORRENT, [second], two, ahead(7), from_series=True)

        assert found.action is PlanAction.REVIEW


class TestBehindTheLatestEpisode:
    """規則二：連載中的 RSS Series 對到的那一集比最近播出的一集早很多。"""

    def test_a_split_cour_restart_is_held(self) -> None:
        """第二個 cour 的 01 在第 13 集播出那天發佈，而 offset 沒設：對到的是半年前的第 1 集。"""
        published = at(_aired(13))

        [found] = check_airing(TORRENT, [item(1)], media(), published, from_series=True)

        assert found.action is PlanAction.REVIEW
        assert found.reasons[-1] == why(
            ReasonCode.BEHIND_LATEST_EPISODE,
            episode="S01E01",
            aired=_aired(1).isoformat(),
            latest="S01E13",
            latest_aired=_aired(13).isoformat(),
        )

    def test_exactly_the_threshold_behind_passes(self) -> None:
        """字幕組慢幾週是常態；門檻那一天本身還算慢，不算錯。"""
        published = at(FIRST + BEHIND_LATEST)

        [found] = check_airing(
            TORRENT, [item(1)], two_episodes(BEHIND_LATEST), published, from_series=True
        )

        assert found.action is PlanAction.IMPORT

    def test_a_day_past_the_threshold_is_held(self) -> None:
        gap = BEHIND_LATEST + timedelta(days=1)

        [found] = check_airing(
            TORRENT, [item(1)], two_episodes(gap), at(FIRST + gap), from_series=True
        )

        assert found.action is PlanAction.REVIEW

    def test_the_latest_episode_counts_what_aired_up_to_two_days_after_publishing(self) -> None:
        """發佈比 TMDB 的日期早一天（跨日）時，那一集就是最近播出的那一集，與規則一同一個容忍。"""
        published = at(_aired(13) - timedelta(days=1))

        [found] = check_airing(TORRENT, [item(1)], media(), published, from_series=True)

        assert found.reasons[-1].params["latest"] == "S01E13"

    def test_a_finished_work_is_not_serial(self) -> None:
        """播完很久之後才發的（BD、補檔）：作品不在連載中，最近播出的那一集不是它該對的東西。"""
        published = at(_aired(24) + timedelta(days=200))

        [found] = check_airing(TORRENT, [item(1)], media(), published, from_series=True)

        assert found.action is PlanAction.IMPORT

    def test_a_manual_download_is_not_checked_against_the_latest_episode(self) -> None:
        [found] = check_airing(TORRENT, [item(1)], media(), at(_aired(13)), from_series=False)

        assert found.action is PlanAction.IMPORT

    def test_specials_are_not_checked_against_the_latest_episode(self) -> None:
        """S00 不照播出順序：第 0 季的特典本來就可能比正在播的一集早很多。"""
        [found] = check_airing(
            TORRENT, [item(1, season=0)], media(), at(_aired(20)), from_series=True
        )

        assert found.action is PlanAction.IMPORT


class TestMissingFacts:
    """缺資料時不擋，記一筆：沒有日期就沒有證據說它錯。"""

    def test_no_air_date_on_tmdb_passes_with_a_note(self) -> None:
        [found] = check_airing(
            TORRENT, [item(5)], media(missing=frozenset({5})), at(_aired(1)), from_series=True
        )

        assert found.action is PlanAction.IMPORT
        assert found.reasons[-1] == why(ReasonCode.AIR_DATE_MISSING, episode="S01E05")

    def test_no_publish_date_passes_with_a_note(self) -> None:
        [found] = check_airing(TORRENT, [item(5)], media(), None, from_series=True)

        assert found.action is PlanAction.IMPORT
        assert found.reasons[-1] == why(ReasonCode.PUBLISHED_MISSING)

    def test_without_a_snapshot_nothing_changes(self) -> None:
        assert check_airing(TORRENT, [item(5)], None, at(_aired(1)), from_series=True) == (item(5),)

    def test_rows_that_are_not_episodes_are_left_alone(self) -> None:
        extra = item(5).model_copy(update={"action": PlanAction.EXTRA, "season": None})
        held = item(5).model_copy(update={"action": PlanAction.REVIEW})

        assert check_airing(TORRENT, [extra, held], media(), None, from_series=True) == (
            extra,
            held,
        )
