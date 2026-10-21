"""每日巡檢：一天一次、不花 token 的程式檢查（M4 票 129，plan §11.5〈巡檢〉）。

一輪是幾項檢查依序跑完、一起 commit（`sweep_once`）。要人動手的寫成 Issue（進 `/issues`、算進
「等你處理」），已經有 Issue 管著的不重複開；量到條件不在了由系統收掉。排程在
`pipeline/sweeping.py`。

- **卡住的**（`_stuck_first_batches`）：還沒確認的 RSS Series 有 Job 停在 `submit_failed` /
  `client_error` 超過 `STUCK_AFTER`。第一批要整批落地才由系統確認（`services.first_batch`），
  停住的那一筆讓整批一直等人（M4 票 11 的遺留）。
- **一直失敗的 Feed**（`_failing_feeds`，M4 票 130）：輪詢或每日補漏從由好轉壞的那一輪起一直失敗
  超過 `FAILING_AFTER`（`rss_feeds.poll_failing_since` / `backfill_failing_since`，`services.rss`
  寫），兩種各一件。
- **RSS Series 缺集**（`_missing_episodes`，M4 票 130）：綁好的 Series 已入庫的集數之間，作品頁說
  「缺」的那幾集（`inventory.read_holdings`：播了、沒有下載在處理），洞之後的集數入庫滿
  `GAP_GRACE` 才算。
- **放太久**（`_remind_lingering`）：「等你處理」裡最舊的一件等了超過 `LINGER_AFTER`，給訂閱了
  「等你處理」的管理員再提醒一則（`notify.queue_lingering`）；同一件 `REMIND_EVERY` 內只提醒一次。
  一件從什麼時候開始等是送出迴圈的看守第一次看到它的那一刻（`NotifyWatchSettings.since`）：
  「新的一件」也是它說了算，兩邊對「一件」的定義才一致。
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import cast, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import Integer

from berth.domain import (
    EpisodeStatus,
    EventType,
    IssueStatus,
    IssueType,
    JobState,
    JobTrigger,
    PlanAction,
)
from berth.models import (
    Event,
    Issue,
    Job,
    LedgerEntry,
    Media,
    NotifyWatchSettings,
    RssFeed,
    RssSeries,
    SweepSettings,
)
from berth.models.types import utcnow
from berth.services.commands import Effect, command
from berth.services.inventory import episodes_of, read_holdings
from berth.services.issues import (
    STANDS_WHILE,
    clear_by_system,
    note_cleared,
    record_issue,
    still_ignored,
)
from berth.services.notify import queue_lingering
from berth.services.settings import read_settings, write_settings
from berth.services.waiting import WaitingSource, waiting_now

logger = logging.getLogger(__name__)

#: 停了多久才算卡住（票面預設 24 小時）。送單失敗的暫時性重試（`jobs.retry_due`）在這之內早就
#: 用完；過了一天還停著的，沒有人看就不會動。
STUCK_AFTER = timedelta(hours=24)

#: 讓第一批停住的那兩種狀態（M4 票 11 的 Comments）。其他停住的狀態（`review`、
#: `import_failed`）在審核佇列或 Job 頁上已經等著人。
_STUCK_STATES = (JobState.SUBMIT_FAILED, JobState.CLIENT_ERROR)

#: Job 停下來那一刻寫的事件：送單失敗寫 `submit_failed`，客戶端報錯寫 `issue_detected`。
_STOPPED_BY = (EventType.SUBMIT_FAILED.value, EventType.ISSUE_DETECTED.value)

#: 輪詢或補漏一直失敗多久開 Issue（M4 票 130 票面 24 小時）。補漏一天才讀一次，但讀不到的那一個
#: 每一輪輪詢都會再試（`backfilled_at` 不動），所以一天裡試過幾十次。
FAILING_AFTER = timedelta(hours=24)

#: 每一種失敗讀 Feed 的哪兩欄：（原文, 從什麼時候開始一直失敗）。
_FAILURES: tuple[tuple[IssueType, Callable[[RssFeed], tuple[str, datetime | None]]], ...] = (
    (IssueType.FEED_POLL_FAILING, lambda feed: (feed.poll_error, feed.poll_failing_since)),
    (
        IssueType.FEED_BACKFILL_FAILING,
        lambda feed: (feed.backfill_error, feed.backfill_failing_since),
    ),
)

#: 洞之後的集數入庫滿多久才算缺（M4 票 130 票面 7 天）：字幕組常晚幾天補發前一集。
GAP_GRACE = timedelta(days=7)

#: 「等你處理」裡的一件等了多久算放太久（票面 3 天）。
LINGER_AFTER = timedelta(days=3)

#: 同一件提醒過之後，隔多久才再提醒（票面「同一件三天內只提醒一次」）。
REMIND_EVERY = timedelta(days=3)


@dataclass(frozen=True, slots=True)
class SweepOutcome:
    """一輪做了什麼（迴圈記 log 用）。"""

    #: 這一輪開著（新開或還在）的「第一批卡住」。
    stuck: int
    #: 這一輪開著的「一直失敗的 Feed」（輪詢與補漏各算一件）。
    failing: int
    #: 這一輪開著的「RSS Series 缺集」。
    missing: int
    #: 這一輪由系統收掉的（每一種加起來）。
    cleared: int
    #: 「放太久」排了幾則提醒（每位收件人一則）。
    reminded: int


# 寫 Issue 與排通知；Issue 由下一輪收、通知送出去收不回來。
@command(Effect.IRREVERSIBLE)
async def sweep_once(session: AsyncSession, *, now: datetime | None = None) -> SweepOutcome:
    """巡檢一輪，最後 commit。"""
    moment = now or utcnow()
    stuck, cleared = await _stuck_first_batches(session, moment)
    failing, recovered = await _failing_feeds(session, moment)
    missing, filled = await _missing_episodes(session, moment)
    reminded = await _remind_lingering(session, moment)
    await session.commit()
    return SweepOutcome(
        stuck=stuck,
        failing=failing,
        missing=missing,
        cleared=cleared + recovered + filled,
        reminded=reminded,
    )


async def _stuck_first_batches(session: AsyncSession, moment: datetime) -> tuple[int, int]:
    """開（或更新）每一個卡住的 Series 一件，收掉不再卡住的。回（開著的件數，收掉的件數）。"""
    rows = list(
        (
            await session.execute(
                select(RssSeries, Job)
                .join(
                    Job,
                    (Job.trigger == JobTrigger.RSS)
                    & (cast(Job.trigger_ref, Integer) == RssSeries.id),
                )
                .where(
                    RssSeries.confirmed.is_(False),
                    RssSeries.media_id.is_not(None),
                    Job.state.in_(_STUCK_STATES),
                )
            )
        ).tuples()
    )
    covered = await _covered(session, [job for _, job in rows])
    since = await _stopped_at(session, [job for _, job in rows])
    flagged: dict[int, tuple[RssSeries, Job, datetime]] = {}
    for series, job in rows:
        stopped = since.get(job.hash, job.added_at)
        if job.hash in covered or moment - stopped < STUCK_AFTER:
            continue
        held = flagged.get(series.id)
        if held is None or stopped < held[2]:
            flagged[series.id] = (series, job, stopped)

    for series, job, stopped in flagged.values():
        recorded = await record_issue(
            session,
            IssueType.FIRST_BATCH_STUCK,
            series_id=series.id,
            job_hash=job.hash,
            detail={
                "series": series.id,
                "name": series.title_raw,
                "job": job.name,
                "state": job.state.value,
                "error": job.error,
                "since": stopped.isoformat(),
            },
            now=moment,
        )
        # 停得最久的那一筆換了（前一筆走開了）：清單上那一格連到現在這一筆。
        recorded.issue.job_hash = job.hash

    cleared = await _settle(
        session,
        (IssueType.FIRST_BATCH_STUCK,),
        {(IssueType.FIRST_BATCH_STUCK, str(series_id)) for series_id in flagged},
        moment,
    )
    return len(flagged), cleared


async def _failing_feeds(session: AsyncSession, moment: datetime) -> tuple[int, int]:
    """每一個輪詢或補漏一直失敗超過 `FAILING_AFTER` 的 Feed 開（或更新）一件，說出最後的原因；
    恢復了或 Feed 被刪了的收掉。回（開著的件數，收掉的件數）。"""
    flagged: set[tuple[IssueType, str]] = set()
    for feed in await session.scalars(select(RssFeed).order_by(RssFeed.id)):
        for kind, read in _FAILURES:
            error, since = read(feed)
            if not error or since is None or moment - since < FAILING_AFTER:
                continue
            await record_issue(
                session,
                kind,
                feed_id=feed.id,
                detail={
                    "feed": feed.id,
                    "name": feed.name,
                    "error": error,
                    "since": since.isoformat(),
                },
                now=moment,
            )
            flagged.add((kind, str(feed.id)))
    cleared = await _settle(session, [kind for kind, _ in _FAILURES], flagged, moment)
    return len(flagged), cleared


async def _missing_episodes(session: AsyncSession, moment: datetime) -> tuple[int, int]:
    """每一個有洞的綁好的 RSS Series 開（或更新）一件，列出缺哪幾集；補上了或解除綁定了的收掉。
    回（開著的件數，收掉的件數）。

    **缺不缺看作品頁那一份**（`read_holdings` 的 `missing`）：另一個字幕組或手動送的入庫了那一集
    就不缺，下載中、卡住、等審核的那一集已經有人在管。**洞在這個 Series 自己入庫過的集數之間**：
    中途訂閱的第一集之前、最新一集之後都不算。第 0 季不看：特別篇的編號本來就不連續。
    """
    found: dict[int, RssSeries] = {}
    landed: dict[int, dict[tuple[int, int], datetime]] = {}
    for series, entry in (
        await session.execute(
            select(RssSeries, LedgerEntry)
            .join(
                Job,
                (Job.trigger == JobTrigger.RSS) & (cast(Job.trigger_ref, Integer) == RssSeries.id),
            )
            .join(LedgerEntry, LedgerEntry.job_hash == Job.hash)
            .where(
                RssSeries.media_id.is_not(None),
                LedgerEntry.media_id == RssSeries.media_id,
                LedgerEntry.action == PlanAction.IMPORT,
                LedgerEntry.season > 0,
                LedgerEntry.episode_start.is_not(None),
            )
        )
    ).tuples():
        found[series.id] = series
        mine = landed.setdefault(series.id, {})
        for pair in episodes_of(entry):
            mine[pair] = min(mine.get(pair, entry.created_at), entry.created_at)

    missing_in: dict[str, set[tuple[int, int]]] = {}
    flagged: dict[int, list[tuple[int, int]]] = {}
    for series_id, mine in landed.items():
        media_id = found[series_id].media_id
        assert media_id is not None  # 上面的 where
        if media_id not in missing_in:
            missing_in[media_id] = await _missing_in(session, media_id)
        holes = _holes(mine, missing_in[media_id], moment)
        if holes:
            flagged[series_id] = holes

    for series_id, holes in flagged.items():
        series = found[series_id]
        media = await session.get(Media, series.media_id)
        await record_issue(
            session,
            IssueType.SERIES_EPISODES_MISSING,
            series_id=series_id,
            detail={
                "series": series_id,
                "name": series.title_raw,
                "media": series.media_id,
                "title": media.snapshot().title if media is not None else "",
                "missing": [{"season": season, "episode": number} for season, number in holes],
            },
            now=moment,
        )
    cleared = await _settle(
        session,
        (IssueType.SERIES_EPISODES_MISSING,),
        {(IssueType.SERIES_EPISODES_MISSING, str(series_id)) for series_id in flagged},
        moment,
    )
    return len(flagged), cleared


async def _missing_in(session: AsyncSession, media_id: str) -> set[tuple[int, int]]:
    """作品頁說「缺」的那幾集。沒有 TMDB 快照的作品說不出哪幾集播了，一集都不算。"""
    media = await session.get(Media, media_id)
    snapshot = media.stored_snapshot() if media is not None else None
    if media is None or snapshot is None:
        return set()
    holdings = await read_holdings(session, media, snapshot)
    return {
        (season.season_number, episode.episode_number)
        for season in holdings.seasons
        for episode in season.episodes
        if episode.status is EpisodeStatus.MISSING
    }


def _holes(
    landed: dict[tuple[int, int], datetime], missing: Collection[tuple[int, int]], moment: datetime
) -> list[tuple[int, int]]:
    """這個 Series 入庫過的集數之間缺的那幾集；洞之後最早入庫的一集已滿 `GAP_GRACE` 的才算。"""
    holes: list[tuple[int, int]] = []
    for season in sorted({season for season, _ in landed}):
        mine = {number: at for (this, number), at in landed.items() if this == season}
        for number in range(min(mine) + 1, max(mine)):
            if (season, number) not in missing:
                continue
            after = min(at for later, at in mine.items() if later > number)
            if moment - after >= GAP_GRACE:
                holes.append((season, number))
    return holes


async def _settle(
    session: AsyncSession,
    kinds: Collection[IssueType],
    flagged: Collection[tuple[IssueType, str]],
    moment: datetime,
) -> int:
    """`kinds` 裡這一輪沒再量到的（型別, subject）由系統收掉：開著的收成 `resolved`，被忽略的記下
    條件解除過（`note_cleared`，之後再發生是新的一件）。回收掉的件數。"""
    known = list(
        await session.scalars(
            select(Issue).where(
                Issue.type.in_(kinds),
                Issue.status.in_((IssueStatus.OPEN, IssueStatus.IGNORED)),
            )
        )
    )
    gone = [row for row in known if (row.type, row.subject) not in flagged]
    clear_by_system([row for row in gone if row.status is IssueStatus.OPEN], moment)
    note_cleared(gone, moment)
    await session.flush()
    return sum(1 for row in gone if row.status is IssueStatus.RESOLVED)


async def _remind_lingering(session: AsyncSession, moment: datetime) -> int:
    """最舊的那一件等滿 `LINGER_AFTER`、而且 `REMIND_EVERY` 內沒提醒過它，排一則提醒。回排了幾則。

    被忽略、條件一直都在而又開的 Issue 不算（`issues.still_ignored`）：人說過這一件不用管。
    """
    current = await waiting_now(session)
    since = (await read_settings(session, NotifyWatchSettings)).since
    quiet = await still_ignored(
        session, [one.ref for one in current.values() if one.source is WaitingSource.ISSUE]
    )
    ages = {
        key: since[key]
        for key, one in current.items()
        if key in since and not (one.source is WaitingSource.ISSUE and one.ref in quiet)
    }
    record = await read_settings(session, SweepSettings)
    record.reminded = {key: at for key, at in record.reminded.items() if key in current}
    queued = 0
    if ages:
        oldest = min(ages, key=lambda key: ages[key])
        last = record.reminded.get(oldest)
        if moment - ages[oldest] >= LINGER_AFTER and (
            last is None or moment - last >= REMIND_EVERY
        ):
            days = (moment - ages[oldest]).days
            queued = await queue_lingering(session, oldest, days=days, now=moment)
            if queued:
                # 沒有人收得到就不算提醒過：之後勾了的人下一輪就收得到。
                record.reminded[oldest] = moment
    await write_settings(session, record)
    return queued


async def _covered(session: AsyncSession, jobs: list[Job]) -> set[str]:
    """這幾筆裡已經有一件管線 Issue 說著它現在這個狀態的（`client_error`；重新送單被拒、落回
    `submit_failed` 的 `client_removed`），不再為同一筆開第二件：開著的那一件已經在等人；被忽略的
    那一件是人看過、說了不用管，換一個型別再問同一筆是噪音（M4 票 129 code-review）。收掉的不算：
    它說的是過去。"""
    if not jobs:
        return set()
    state = {job.hash: job.state for job in jobs}
    open_rows = await session.execute(
        select(Issue.type, Issue.job_hash).where(
            Issue.status.in_((IssueStatus.OPEN, IssueStatus.IGNORED)),
            Issue.type.in_(STANDS_WHILE),
            Issue.job_hash.in_(state),
        )
    )
    return {
        job_hash
        for kind, job_hash in open_rows.tuples()
        if job_hash is not None and state[job_hash] in STANDS_WHILE[kind]
    }


async def _stopped_at(session: AsyncSession, jobs: list[Job]) -> dict[str, datetime]:
    """每一筆最後一次停下來的時刻（`_STOPPED_BY` 那兩種事件的最後一筆）。沒有事件的不在裡面，
    呼叫端退回 `added_at`。"""
    if not jobs:
        return {}
    found: dict[str, datetime] = {}
    for job_hash, created_at in (
        await session.execute(
            select(Event.job_hash, Event.created_at).where(
                Event.job_hash.in_([job.hash for job in jobs]), Event.type.in_(_STOPPED_BY)
            )
        )
    ).tuples():
        if job_hash is not None and (job_hash not in found or created_at > found[job_hash]):
            found[job_hash] = created_at
    return found
