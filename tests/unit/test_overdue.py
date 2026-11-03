"""遲到判定（`parser.overdue`，M5.5 票 10、spec〈範圍〉「遲到判定」）。

一部作品一個結果：基準（最後入庫的一集，沒入庫過時從訂閱那天起）之後、播出滿門檻、還沒入庫、
沒有下載還在動、也沒有已經在等人的集。時刻用容器時區：從播出日隔天 00:00 起算。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta, timezone

from berth.domain import (
    EpisodeSnapshot,
    JobState,
    MediaKind,
    MediaSnapshot,
    OverdueReason,
    OverdueStall,
    SeasonSnapshot,
)
from berth.parser.overdue import Overdue, OverdueJob, judge_overdue

#: 容器時區（台北）：牆上的時刻才是門檻的單位。
TZ = timezone(timedelta(hours=8))
AIRED = date(2026, 10, 28)
SUBSCRIBED = date(2026, 10, 1)


def at(day: int, hour: int = 5, minute: int = 0, month: int = 10) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=TZ)


def snapshot(*seasons: dict[int, date | None]) -> MediaSnapshot:
    """`seasons[i]` 是第 i 季的 {集: 播出日}；第一個是第 0 季。"""
    return MediaSnapshot(
        tmdb_id=1,
        kind=MediaKind.TV,
        title="Kimi to Koishitai",
        title_en="Kimi to Koishitai",
        title_original="Kimi to Koishitai",
        seasons=tuple(
            SeasonSnapshot(
                season_number=number,
                episode_count=len(episodes),
                episodes=tuple(
                    EpisodeSnapshot(episode_number=episode, air_date=day)
                    for episode, day in episodes.items()
                ),
            )
            for number, episodes in enumerate(seasons)
        ),
    )


#: 每週一集，第 4 集 10/28 播出。
WEEKLY = snapshot({}, {n: AIRED + timedelta(weeks=n - 4) for n in range(1, 13)})


def judge(
    *,
    now: datetime,
    media: MediaSnapshot = WEEKLY,
    imported: set[tuple[int, int]] | None = None,
    claims: Mapping[tuple[int, int], Sequence[OverdueJob]] | None = None,
    watched_since: date = SUBSCRIBED,
    threshold_days: int = 2,
) -> Overdue | None:
    return judge_overdue(
        media,
        imported={(1, 1), (1, 2), (1, 3)} if imported is None else imported,
        claims=claims or {},
        watched_since=watched_since,
        now=now,
        threshold_days=threshold_days,
    )


def late(result: Overdue | None) -> list[tuple[int, int, OverdueStall]]:
    assert result is None or result.reason is OverdueReason.LATE
    return [] if result is None else [(e.season, e.episode, e.stall) for e in result.episodes]


class TestWhenItIsLate:
    def test_two_days_after_the_day_after_it_aired(self) -> None:
        """10/28 播出：10/30 05:00 不開，10/31 05:00 才開（spec 的例子）。"""
        assert judge(now=at(30)) is None
        assert late(judge(now=at(31))) == [(1, 4, OverdueStall.NOT_RELEASED)]

    def test_the_count_starts_at_midnight_on_the_container_clock(self) -> None:
        assert judge(now=at(30, 23, 59)) is None
        assert late(judge(now=at(31, 0, 0))) == [(1, 4, OverdueStall.NOT_RELEASED)]

    def test_the_threshold_is_a_setting(self) -> None:
        assert late(judge(now=at(29, 0, 0), threshold_days=0)) == [
            (1, 4, OverdueStall.NOT_RELEASED)
        ]
        assert judge(now=at(31), threshold_days=3) is None

    def test_an_episode_without_an_air_date_or_still_to_come_is_never_late(self) -> None:
        media = snapshot({}, {1: date(2026, 9, 1), 2: None, 3: date(2026, 12, 1)})
        assert judge(media=media, imported={(1, 1)}, now=at(31)) is None


class TestWhichEpisodesCount:
    def test_an_imported_episode_is_not_late_whoever_brought_it(self) -> None:
        assert judge(imported={(1, 1), (1, 2), (1, 3), (1, 4)}, now=at(31)) is None

    def test_only_what_comes_after_the_last_imported_episode(self) -> None:
        """第 2 集的洞歸 `series_episodes_missing`：這裡只看最新一集之後。"""
        assert late(judge(imported={(1, 1), (1, 3)}, now=at(31))) == [
            (1, 4, OverdueStall.NOT_RELEASED)
        ]

    def test_every_late_episode_after_the_last_imported_one(self) -> None:
        assert late(judge(imported={(1, 1), (1, 2)}, now=at(31))) == [
            (1, 3, OverdueStall.NOT_RELEASED),
            (1, 4, OverdueStall.NOT_RELEASED),
        ]

    def test_nothing_imported_yet_counts_from_the_first_episode_after_subscribing(self) -> None:
        """10/20 訂閱：10/21 的第 3 集起算，之前播的兩集不是遲到。"""
        assert late(judge(imported=set(), watched_since=date(2026, 10, 20), now=at(31))) == [
            (1, 3, OverdueStall.NOT_RELEASED),
            (1, 4, OverdueStall.NOT_RELEASED),
        ]

    def test_an_episode_that_aired_on_the_day_of_subscribing_counts(self) -> None:
        assert late(judge(imported=set(), watched_since=AIRED, now=at(31))) == [
            (1, 4, OverdueStall.NOT_RELEASED)
        ]

    def test_specials_are_not_looked_at(self) -> None:
        media = snapshot(
            {1: date(2026, 10, 20)},
            {n: AIRED + timedelta(weeks=n - 4) for n in range(1, 13)},
        )
        assert late(judge(media=media, now=at(31))) == [(1, 4, OverdueStall.NOT_RELEASED)]

    def test_the_next_season_follows_the_last_one(self) -> None:
        media = snapshot(
            {},
            {n: date(2026, 6, 1) + timedelta(weeks=n) for n in range(1, 4)},
            {1: AIRED, 2: AIRED + timedelta(weeks=1)},
        )
        assert late(judge(media=media, imported={(1, 1), (1, 2), (1, 3)}, now=at(31))) == [
            (2, 1, OverdueStall.NOT_RELEASED)
        ]


def job(state: JobState, *, waiting: bool = False, name: str = "a") -> OverdueJob:
    return OverdueJob(hash=name * 40, state=state, waiting=waiting)


class TestWhatIsAlreadyBeingHandled:
    def test_a_download_still_moving_is_not_late(self) -> None:
        for state in (JobState.DOWNLOADING, JobState.SUBMITTED, JobState.IMPORTING):
            assert judge(claims={(1, 4): [job(state)]}, now=at(31)) is None

    def test_a_stalled_download_is_late_and_says_so(self) -> None:
        result = judge(claims={(1, 4): [job(JobState.STALLED)]}, now=at(31))
        assert late(result) == [(1, 4, OverdueStall.STALLED)]
        assert result is not None
        assert result.episodes[0].jobs == ("a" * 40,)

    def test_awaiting_review_is_already_waiting_for_you(self) -> None:
        assert judge(claims={(1, 4): [job(JobState.REVIEW)]}, now=at(31)) is None

    def test_a_job_an_issue_already_speaks_for_is_already_waiting_for_you(self) -> None:
        claims = {(1, 4): [job(JobState.CLIENT_ERROR, waiting=True)]}
        assert judge(claims=claims, now=at(31)) is None

    def test_where_it_is_stuck(self) -> None:
        cases = {
            JobState.IMPORT_FAILED: OverdueStall.IMPORT_FAILED,
            JobState.SUBMIT_FAILED: OverdueStall.SUBMIT_FAILED,
            JobState.CLIENT_ERROR: OverdueStall.DOWNLOAD_FAILED,
            # 刪掉的 Job 不在路上：等於沒有下載。
            JobState.REMOVED: OverdueStall.NOT_RELEASED,
        }
        for state, stall in cases.items():
            assert late(judge(claims={(1, 4): [job(state)]}, now=at(31))) == [(1, 4, stall)]

    def test_the_stuck_job_closest_to_the_library_speaks(self) -> None:
        claims = {
            (1, 4): [job(JobState.SUBMIT_FAILED, name="s"), job(JobState.IMPORT_FAILED, name="i")]
        }
        result = judge(claims=claims, now=at(31))
        assert late(result) == [(1, 4, OverdueStall.IMPORT_FAILED)]
        assert result is not None
        assert result.episodes[0].jobs == ("i" * 40,)

    def test_one_moving_download_is_enough(self) -> None:
        claims = {(1, 4): [job(JobState.IMPORT_FAILED, name="i"), job(JobState.DOWNLOADING)]}
        assert judge(claims=claims, now=at(31)) is None
