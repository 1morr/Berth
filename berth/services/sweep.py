"""每日巡檢：一天一次、不花 token 的程式檢查（M4 票 129，plan §11.5〈巡檢〉）。

一輪是幾項檢查依序跑完、一起 commit（`sweep_once`）。要人動手的寫成 Issue（進 `/issues`、算進
「等你處理」），已經有 Issue 管著的不重複開；量到條件不在了由系統收掉。排程在
`pipeline/sweeping.py`。

- **卡住的**（`_stuck_first_batches`）：還沒確認的 RSS Series 有 Job 停在 `submit_failed` /
  `client_error` 超過 `STUCK_AFTER`。第一批要整批落地才由系統確認（`services.first_batch`），
  停住的那一筆讓整批一直等人（M4 票 11 的遺留）。
- **放太久**（`_remind_lingering`）：「等你處理」裡最舊的一件等了超過 `LINGER_AFTER`，給訂閱了
  「等你處理」的管理員再提醒一則（`notify.queue_lingering`）；同一件 `REMIND_EVERY` 內只提醒一次。
  一件從什麼時候開始等是送出迴圈的看守第一次看到它的那一刻（`NotifyWatchSettings.since`）：
  「新的一件」也是它說了算，兩邊對「一件」的定義才一致。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import cast, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import Integer

from berth.domain import EventType, IssueStatus, IssueType, JobState, JobTrigger
from berth.models import Event, Issue, Job, NotifyWatchSettings, RssSeries, SweepSettings
from berth.models.types import utcnow
from berth.services.commands import Effect, command
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

#: 「等你處理」裡的一件等了多久算放太久（票面 3 天）。
LINGER_AFTER = timedelta(days=3)

#: 同一件提醒過之後，隔多久才再提醒（票面「同一件三天內只提醒一次」）。
REMIND_EVERY = timedelta(days=3)


@dataclass(frozen=True, slots=True)
class SweepOutcome:
    """一輪做了什麼（迴圈記 log 用）。"""

    #: 這一輪開著（新開或還在）的「第一批卡住」。
    stuck: int
    #: 這一輪由系統收掉的。
    cleared: int
    #: 「放太久」排了幾則提醒（每位收件人一則）。
    reminded: int


# 寫 Issue 與排通知；Issue 由下一輪收、通知送出去收不回來。
@command(Effect.IRREVERSIBLE)
async def sweep_once(session: AsyncSession, *, now: datetime | None = None) -> SweepOutcome:
    """巡檢一輪，最後 commit。"""
    moment = now or utcnow()
    stuck, cleared = await _stuck_first_batches(session, moment)
    reminded = await _remind_lingering(session, moment)
    await session.commit()
    return SweepOutcome(stuck=stuck, cleared=cleared, reminded=reminded)


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

    known = list(
        await session.scalars(
            select(Issue).where(
                Issue.type == IssueType.FIRST_BATCH_STUCK,
                Issue.status.in_((IssueStatus.OPEN, IssueStatus.IGNORED)),
            )
        )
    )
    gone = [row for row in known if int(row.subject) not in flagged]
    clear_by_system([row for row in gone if row.status is IssueStatus.OPEN], moment)
    note_cleared(gone, moment)
    await session.flush()
    return len(flagged), sum(1 for row in gone if row.status is IssueStatus.RESOLVED)


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
