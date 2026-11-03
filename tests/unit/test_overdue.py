"""遲到判定（`parser.overdue`，M5.5 票 10、spec〈範圍〉「遲到判定」）。

一部作品一個結果：基準（最後入庫的一集，沒入庫過時從訂閱那天起）之後、播出滿門檻、還沒入庫、
沒有下載還在動、也沒有已經在等人的集。時刻用容器時區：從播出日隔天 00:00 起算。
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from datetime import date, datetime, time, timedelta, timezone

from berth.domain import (
    EpisodeSnapshot,
    JobState,
    MediaKind,
    MediaSnapshot,
    OverdueReason,
    OverdueStall,
    SeasonSnapshot,
)
from berth.parser.overdue import Overdue, OverdueJob, Watch, judge_overdue, watch_overdue

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


#: 帳本那一列寫下的時刻；換輪要比「比基準那一集入庫更晚建立的 RSS Series」時才看得到它。
LANDED = datetime(2026, 10, 2, 12, 0, tzinfo=TZ)


def noon(day: date) -> datetime:
    return datetime.combine(day, time(12), TZ)


def judge(
    *,
    now: datetime,
    media: MediaSnapshot = WEEKLY,
    imported: Collection[tuple[int, int]] | Mapping[tuple[int, int], datetime] | None = None,
    claims: Mapping[tuple[int, int], Sequence[OverdueJob]] | None = None,
    watched_since: date = SUBSCRIBED,
    subscribed: Sequence[datetime] = (),
    threshold_days: int = 2,
) -> Overdue | None:
    held = {(1, 1), (1, 2), (1, 3)} if imported is None else imported
    return judge_overdue(
        media,
        imported=held if isinstance(held, Mapping) else dict.fromkeys(held, LANDED),
        claims=claims or {},
        subscribed=subscribed or (noon(watched_since),),
        now=now,
        threshold_days=threshold_days,
    )


def late(
    result: Overdue | None, reason: OverdueReason = OverdueReason.LATE
) -> list[tuple[int, int, OverdueStall]]:
    assert result is None or result.reason is reason
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
            {n: AIRED - timedelta(weeks=4 - n) for n in range(1, 4)},
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


def weekly(first: date, count: int, start: int = 1) -> dict[int, date | None]:
    return {start + n: first + timedelta(weeks=n) for n in range(count)}


#: Re:Zero（TMDB 65942）第四季的形狀：第 67–77 集 4 月起每週一集，停播 56 天之後第 78–85 集 8/12 起
#: （brief §20.12）。Mikan 上第二個 cour 是另一個番組，訂了前一個不會收到這一個。
REZERO_BREAK = date(2026, 8, 12) - date(2026, 6, 17)


def rezero(gap: timedelta = REZERO_BREAK) -> MediaSnapshot:
    first = weekly(date(2026, 4, 8), 11, start=67)
    return snapshot({}, {**first, **weekly(date(2026, 6, 17) + gap, 8, start=78)})


#: 第 67–77 集都入庫了，第 77 集 6/18 入庫；訂閱是 4/1 建的。
REZERO_HELD = {(1, n): datetime(2026, 6, 18, 9, 0, tzinfo=TZ) for n in range(67, 78)}
REZERO_SUBSCRIBED = (datetime(2026, 4, 1, 12, 0, tzinfo=TZ),)


class TestNextRun:
    """換輪：基準那一集與下一集播出日相隔超過 21 天，可能是下一個 cour（Mikan 是另一個番組），
    不是字幕組遲到。"""

    def test_rezero_after_the_56_day_break_is_the_next_run(self) -> None:
        assert timedelta(days=56) == REZERO_BREAK
        result = judge(
            media=rezero(),
            imported=REZERO_HELD,
            subscribed=REZERO_SUBSCRIBED,
            now=at(20, month=8),
        )
        assert late(result, OverdueReason.NEXT_RUN) == [(1, 78, OverdueStall.NOT_RELEASED)]

    def test_a_14_day_break_in_the_same_run_is_still_late(self) -> None:
        media = rezero(timedelta(days=14))
        aired = date(2026, 7, 1)
        result = judge(
            media=media,
            imported=REZERO_HELD,
            subscribed=REZERO_SUBSCRIBED,
            now=datetime.combine(aired + timedelta(days=3), time(5), TZ),
        )
        assert late(result) == [(1, 78, OverdueStall.NOT_RELEASED)]

    def test_21_days_is_the_same_run_and_22_is_not(self) -> None:
        def reason(gap: int) -> OverdueReason:
            result = judge(
                media=rezero(timedelta(days=gap)),
                imported=REZERO_HELD,
                subscribed=REZERO_SUBSCRIBED,
                now=at(20, month=8),
            )
            assert result is not None
            return result.reason

        assert reason(21) is OverdueReason.LATE
        assert reason(22) is OverdueReason.NEXT_RUN

    def test_a_series_created_after_the_baseline_landed_brings_back_late(self) -> None:
        """訂了第二個 cour 的番組：那一條比第 77 集入庫更晚建立，晚了就是晚了。"""
        resubscribed = (*REZERO_SUBSCRIBED, datetime(2026, 8, 10, 20, 0, tzinfo=TZ))
        result = judge(
            media=rezero(), imported=REZERO_HELD, subscribed=resubscribed, now=at(20, month=8)
        )
        assert late(result) == [(1, 78, OverdueStall.NOT_RELEASED)]

    def test_the_next_season_after_a_long_break_is_the_next_run(self) -> None:
        media = snapshot(
            {},
            {n: date(2026, 6, 1) + timedelta(weeks=n) for n in range(1, 4)},
            {1: AIRED, 2: AIRED + timedelta(weeks=1)},
        )
        result = judge(media=media, imported={(1, 1), (1, 2), (1, 3)}, now=at(31))
        assert late(result, OverdueReason.NEXT_RUN) == [(2, 1, OverdueStall.NOT_RELEASED)]

    def test_nothing_imported_yet_has_no_baseline_to_break_from(self) -> None:
        result = judge(
            media=rezero(), imported=set(), watched_since=date(2026, 8, 1), now=at(20, month=8)
        )
        assert late(result) == [(1, 78, OverdueStall.NOT_RELEASED)]


#: 只到第 4 集的一季：第 4 集 10/28 播出之後沒有下一集。
SHORT = snapshot({}, {n: AIRED + timedelta(weeks=n - 4) for n in range(1, 5)})


class TestWindow:
    """最後一集缺集播出滿 60 天後不再提醒（追更頁的「斷更很久」）；上線第一天的舊缺集也走這一條。"""

    def test_sixty_days_after_the_last_late_episode_aired_it_stops(self) -> None:
        assert late(judge(media=SHORT, now=at(26, month=12))) == [(1, 4, OverdueStall.NOT_RELEASED)]
        assert judge(media=SHORT, now=at(27, month=12)) is None

    def test_old_gaps_from_before_berth_are_not_reminded(self) -> None:
        old = snapshot({}, weekly(date(2024, 1, 3), 12))
        assert judge(media=old, imported={(1, 1), (1, 2)}, now=at(31)) is None

    def test_an_old_late_episode_still_shows_while_a_recent_one_is_late(self) -> None:
        """視窗看最後一集缺集：還在提醒的一件照實列出它之前晚的每一集。"""
        assert late(judge(imported={(1, 1)}, now=at(31))) == [
            (1, 2, OverdueStall.NOT_RELEASED),
            (1, 3, OverdueStall.NOT_RELEASED),
            (1, 4, OverdueStall.NOT_RELEASED),
        ]
        stale = snapshot({}, {1: date(2026, 8, 1), 2: date(2026, 8, 8), 3: AIRED})
        assert [
            episode for _, episode, _ in late(judge(media=stale, imported={(1, 1)}, now=at(31)))
        ] == [2, 3]


class TestWindowAnchor:
    def test_the_window_follows_the_last_missing_episode_not_the_last_late_one(self) -> None:
        """第 4 集昨天才播（還沒過門檻）：最後一集缺集是它，70 天前的第 3 集照樣提醒。"""
        today = date(2026, 10, 31)
        media = snapshot(
            {},
            {
                1: today - timedelta(days=84),
                2: today - timedelta(days=77),
                3: today - timedelta(days=70),
                4: today - timedelta(days=1),
            },
        )
        assert late(judge(media=media, imported={(1, 1), (1, 2)}, now=at(31))) == [
            (1, 3, OverdueStall.NOT_RELEASED)
        ]


def watch(
    *,
    now: datetime,
    media: MediaSnapshot = WEEKLY,
    imported: Collection[tuple[int, int]] = ((1, 1), (1, 2), (1, 3)),
    claims: Mapping[tuple[int, int], Sequence[OverdueJob]] | None = None,
) -> Watch:
    return watch_overdue(
        media,
        imported=dict.fromkeys(imported, LANDED),
        claims=claims or {},
        subscribed=(noon(SUBSCRIBED),),
        now=now,
        threshold_days=2,
    )


class TestWatch:
    """追更頁讀的那一份（M5.5 票 12）：缺的集、晚的集與視窗，不收成 Issue。"""

    def test_missing_counts_what_aired_after_the_baseline_before_the_threshold(self) -> None:
        """10/30：第 4 集播了、還沒過門檻：缺它，但還不晚。"""
        seen = watch(now=at(30))
        assert seen.missing == ((1, 4),)
        assert seen.late == ()
        assert not seen.dormant
        assert seen.overdue is None

    def test_late_once_past_the_threshold_matches_the_judgement(self) -> None:
        seen = watch(now=at(31))
        assert [(one.season, one.episode) for one in seen.late] == [(1, 4)]
        assert seen.overdue == judge(now=at(31))

    def test_caught_up_has_nothing_missing(self) -> None:
        seen = watch(now=at(27), imported=((1, 1), (1, 2), (1, 3)))
        assert seen.missing == ()
        assert seen.late == ()

    def test_past_the_window_is_dormant_and_still_says_what_is_missing(self) -> None:
        seen = watch(media=SHORT, now=at(27, month=12))
        assert seen.dormant
        assert seen.missing == ((1, 4),)
        assert seen.overdue is None

    def test_a_moving_download_is_missing_but_not_late(self) -> None:
        moving = {(1, 4): [OverdueJob(hash="a", state=JobState.DOWNLOADING)]}
        seen = watch(now=at(31), claims=moving)
        assert seen.missing == ((1, 4),)
        assert seen.late == ()
