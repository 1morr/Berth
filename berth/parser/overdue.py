"""訂閱的作品有沒有按時入庫（M5.5 票 10，spec〈範圍〉「遲到判定」）。

一部作品一個結果（`watch_overdue`）：巡檢（`services.sweep`）把它寫成一件 `episodes_overdue`，追更頁
（`services.keeping_up`，M5.5 票 12）照它分段。

- **基準**：作品最後入庫的一集，不分來源（另一個字幕組、手動送的都算）；還沒入庫過時，從作品
  最早的一條訂閱開始那天（RSS Series 建立、預先綁定作品的 Feed 綁定，票 12b）之後播出的第一集
  算。基準之前的洞歸 `series_episodes_missing`。
- **晚**：基準之後播出、還沒入庫，從播出日隔天 00:00（容器時區，`now` 的時區）起算滿
  `threshold_days`。TMDB 只有日期，隔天才確定那一集已經播完。第 0 季不看。
- **例外只有兩種**：下載還在動（蓋到它的 Job 在 `UNDER_WAY_STATES`，停滯不算），或已經在等你處理
  （Job 在審核、或有 Issue 說著它現在這個狀態：`OverdueJob.waiting`，呼叫端查）。其餘不管卡在
  哪一步都算晚，卡在哪寫在 `LateEpisode.stall`。
- **換輪**（票 11）：基準那一集與下一集播出日相隔超過 `NEXT_RUN_GAP`，理由是 `next_run`、不是
  字幕組遲到；作品上有一條比基準那一集入庫更晚開始的訂閱（訂了下一輪）時回到 `late`。還沒
  入庫過就沒有基準，一律 `late`。
- **視窗**（票 11）：最後一集缺集（基準之後已播、沒入庫的最新一集，不管過門檻沒）播出滿
  `WINDOW`（從播出日算）就不再提醒。
- **不讀 `series_finished`**：RSS 頁的「已完結」安靜 30 天就成立，那時候缺的集正是要說的。
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from berth.domain import (
    UNDER_WAY_STATES,
    JobState,
    MediaSnapshot,
    OverdueReason,
    OverdueStall,
)

#: 下載還在動：送單到入庫之間的每一站，停滯不算（它不會自己好，正是要說的）。
_MOVING = UNDER_WAY_STATES - {JobState.STALLED}

#: 基準那一集與下一集播出日相隔超過這麼久是換輪（`OverdueReason.NEXT_RUN`）：多半是下一個 cour，
#: Mikan 上是另一個番組，訂了前一個收不到（brief §20.12）。兩週停播（年末、特別節目）還是同一輪。
NEXT_RUN_GAP = timedelta(days=21)

#: 最後一集缺集播出滿這麼久就不再提醒（追更頁收進「斷更很久」）。上線第一天的舊缺集也走這一條。
WINDOW = timedelta(days=60)

#: 停在哪個狀態說成哪一種。不在表上的（已入庫、已刪除）等於沒有下載蓋到它。
_STALL_OF: dict[JobState, OverdueStall] = {
    JobState.IMPORT_FAILED: OverdueStall.IMPORT_FAILED,
    JobState.STALLED: OverdueStall.STALLED,
    JobState.MISSING_FILES: OverdueStall.DOWNLOAD_FAILED,
    JobState.CLIENT_ERROR: OverdueStall.DOWNLOAD_FAILED,
    JobState.CLIENT_REMOVED: OverdueStall.DOWNLOAD_FAILED,
    JobState.SUBMIT_FAILED: OverdueStall.SUBMIT_FAILED,
}


@dataclass(frozen=True, slots=True)
class OverdueJob:
    """蓋到一集的一筆 Job（`why_not` 的那一份「誰蓋到哪一集」）。"""

    hash: str
    state: JobState
    #: 已經在等你處理：有開著或被忽略、說著它現在這個狀態的 Issue（`issues.covered_jobs`）。
    waiting: bool = False


@dataclass(frozen=True, slots=True)
class LateEpisode:
    season: int
    episode: int
    air_date: date
    stall: OverdueStall
    #: 卡在 `stall` 的那幾筆 Job（畫面連到 `/jobs/{hash}`）；沒有下載時是空的。
    jobs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Overdue:
    reason: OverdueReason
    #: 晚的集，照季集排。
    episodes: tuple[LateEpisode, ...]


@dataclass(frozen=True, slots=True)
class Watch:
    """一部作品這一刻的追更（M5.5 票 12）：遲到判定的每一段都留著，追更頁照它分段，巡檢
    從它收成一件 Issue（`overdue`）。"""

    reason: OverdueReason
    #: 過了門檻、不在兩種例外裡的集，照季集排；視窗過了也照列（`dormant` 說不提醒）。
    late: tuple[LateEpisode, ...]
    #: 基準之後已播、還沒入庫的集（過不過門檻、下載在不在動都算），照季集排。
    missing: tuple[tuple[int, int], ...]
    #: 最後一集缺集播出滿 `WINDOW`：不再提醒，追更頁收進「斷更很久」。
    dormant: bool

    @property
    def overdue(self) -> Overdue | None:
        """寫成 Issue 的那一份：有晚的集、還在視窗裡才有。"""
        if not self.late or self.dormant:
            return None
        return Overdue(reason=self.reason, episodes=self.late)


def watch_overdue(
    media: MediaSnapshot,
    *,
    imported: Mapping[tuple[int, int], datetime],
    claims: Mapping[tuple[int, int], Sequence[OverdueJob]],
    subscribed: Collection[datetime],
    now: datetime,
    threshold_days: int,
) -> Watch:
    """這部作品這一刻缺哪幾集、哪幾集晚了、過了視窗沒。

    `imported` 是帳本有正片蓋到的季集與它入庫的那一刻；`subscribed` 是作品上每一條訂閱開始的
    那一刻（RSS Series 建立、預先綁定的 Feed 綁定；不可為空）；`now`
    是容器時區的現在，日界照它的日期。
    """
    aired = sorted(
        ((season.season_number, row.episode_number), row.air_date)
        for season in media.seasons
        if season.season_number > 0
        for row in season.episodes
        if row.air_date is not None
    )
    held = [(pair, day) for pair, day in aired if pair in imported]
    reason = OverdueReason.LATE
    if held:
        baseline, baseline_aired = max(held)
        after = [(pair, day) for pair, day in aired if pair > baseline]
        if (
            after
            and after[0][1] - baseline_aired > NEXT_RUN_GAP
            and max(subscribed) <= imported[baseline]
        ):
            reason = OverdueReason.NEXT_RUN
    else:
        watched_since = min(subscribed).astimezone(now.tzinfo).date()
        after = [(pair, day) for pair, day in aired if day >= watched_since]

    found: list[LateEpisode] = []
    for pair, day in after:
        # 播出日隔天 00:00 起算滿門檻：比牆上的日期，夏令時間那一天也不差一小時。
        if pair in imported or now.date() < day + timedelta(days=1 + threshold_days):
            continue
        episode = _late(pair, day, claims.get(pair, ()))
        if episode is not None:
            found.append(episode)
    # 視窗看最後一集缺集（還沒過門檻、下載中的也算）：它播出滿 `WINDOW` 就整部不提醒，還在提醒時
    # 照實列出之前晚的每一集。
    missing = [(pair, day) for pair, day in after if pair not in imported and day <= now.date()]
    return Watch(
        reason=reason,
        late=tuple(found),
        missing=tuple(pair for pair, _ in missing),
        dormant=bool(missing) and now.date() >= max(day for _, day in missing) + WINDOW,
    )


def _late(pair: tuple[int, int], aired: date, jobs: Sequence[OverdueJob]) -> LateEpisode | None:
    """過了門檻的一集：例外是 `None`，否則說出卡在哪。"""
    if any(job.state in _MOVING or job.state is JobState.REVIEW or job.waiting for job in jobs):
        return None
    stuck = [job for job in jobs if job.state in _STALL_OF]
    order = list(OverdueStall)
    stall = min(
        (_STALL_OF[job.state] for job in stuck), key=order.index, default=OverdueStall.NOT_RELEASED
    )
    return LateEpisode(
        season=pair[0],
        episode=pair[1],
        air_date=aired,
        stall=stall,
        jobs=tuple(job.hash for job in stuck if _STALL_OF[job.state] is stall),
    )
