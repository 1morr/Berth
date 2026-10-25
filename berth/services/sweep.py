"""每日巡檢：一天一次、不花 token 的程式檢查（M4 票 129，plan §11.5〈巡檢〉）。

一輪是幾項檢查依序跑完、一起 commit（`sweep_once`）。要人動手的寫成 Issue（進 `/issues`、算進
「等你處理」），已經有 Issue 管著的不重複開；量到條件不在了由系統收掉。排程在
`pipeline/sweeping.py`。

- **卡住的 Job**（`_stuck_jobs`，M5 票 03）：停在 `submit_failed`（不會再自動重送）、
  `import_failed`、`stalled`（滿 `STUCK_AFTER`）的每一筆各一件，型別與狀態同名。排在第一批之前：
  它們按得了重試，有了它們「第一批卡住」就不再為同一筆開第二件（`_covered`）。
- **卡住的第一批**（`_stuck_first_batches`）：還沒確認的 RSS Series 有 Job 停在 `submit_failed` /
  `client_error` 超過 `STUCK_AFTER`。第一批要整批落地才由系統確認（`services.first_batch`），
  停住的那一筆讓整批一直等人（M4 票 11 的遺留）。
- **一直失敗的 Feed**（`_failing_feeds`，M4 票 130）：輪詢或每日補漏從由好轉壞的那一輪起一直失敗
  超過 `FAILING_AFTER`（`rss_feeds.poll_failing_since` / `backfill_failing_since`，`services.rss`
  寫），兩種各一件。
- **RSS Series 缺集**（`_missing_episodes`，M4 票 130）：綁好的 Series 已入庫的集數之間，作品頁說
  「缺」的那幾集（`inventory.read_holdings`：播了、沒有下載在處理），洞之後的集數入庫滿
  `GAP_GRACE` 才算。
- **同一集意外多份**（`_colliding_episodes`，M4 票 130）：同一個 Series 兩個發佈名寫的集號不同的 Job
  入庫成同一集。版本並存（別的字幕組、v2、简繁）不算。
- **放太久**（`_remind_lingering`）：「等你處理」裡最舊的一件等了超過 `LINGER_AFTER`，給訂閱了
  「等你處理」的管理員再提醒一則（`notify.queue_lingering`）；同一件 `REMIND_EVERY` 內只提醒一次。
  一件從什麼時候開始等是送出迴圈的看守第一次看到它的那一刻（`NotifyWatchSettings.since`）：
  「新的一件」也是它說了算，兩邊對「一件」的定義才一致。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, NamedTuple

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
    LedgerStatus,
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
from berth.parser import parse_release
from berth.services.commands import Effect, command
from berth.services.inventory import read_holdings
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
#: 用完；過了一天還停著的，沒有人看就不會動。卡住的 Job 只有停滯照它等（M5 票 03）：送單失敗不會再
#: 自動重送、入庫失敗本來就沒有自動重試，多等一天也不會自己好。
STUCK_AFTER = timedelta(hours=24)


class _StuckJob(NamedTuple):
    """卡住的 Job 的一種（M5 票 03）。"""

    kind: IssueType
    #: 停下來那一刻寫的事件。入庫失敗的那一刻沒有自己的事件，`link_failed` 是逐檔寫在它前面的
    #: 那幾筆。
    stopped_by: EventType
    #: 要停滿 `STUCK_AFTER` 才算：只有會自己恢復的停滯。
    waits: bool


#: 卡住的 Job 的三種，依 Job 的狀態。
_STUCK_JOBS: dict[JobState, _StuckJob] = {
    JobState.SUBMIT_FAILED: _StuckJob(IssueType.SUBMIT_FAILED, EventType.SUBMIT_FAILED, False),
    JobState.IMPORT_FAILED: _StuckJob(IssueType.IMPORT_FAILED, EventType.LINK_FAILED, False),
    JobState.STALLED: _StuckJob(IssueType.STALLED, EventType.STALLED, True),
}

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

    #: 這一輪開著（新開或還在）的卡住的 Job（三種加起來）。
    jobs: int
    #: 這一輪開著（新開或還在）的「第一批卡住」。
    stuck: int
    #: 這一輪開著的「一直失敗的 Feed」（輪詢與補漏各算一件）。
    failing: int
    #: 這一輪開著的「RSS Series 缺集」。
    missing: int
    #: 這一輪開著的「同一集意外多份」。
    colliding: int
    #: 這一輪由系統收掉的（每一種加起來）。
    cleared: int
    #: 「放太久」排了幾則提醒（每位收件人一則）。
    reminded: int


# 寫 Issue 與排通知；Issue 由下一輪收、通知送出去收不回來。
@command(Effect.IRREVERSIBLE)
async def sweep_once(session: AsyncSession, *, now: datetime | None = None) -> SweepOutcome:
    """巡檢一輪，最後 commit。"""
    moment = now or utcnow()
    jobs, released = await _stuck_jobs(session, moment)
    stuck, cleared = await _stuck_first_batches(session, moment)
    failing, recovered = await _failing_feeds(session, moment)
    missing, filled = await _missing_episodes(session, moment)
    colliding, untangled = await _colliding_episodes(session, moment)
    reminded = await _remind_lingering(session, moment)
    await session.commit()
    return SweepOutcome(
        jobs=jobs,
        stuck=stuck,
        failing=failing,
        missing=missing,
        colliding=colliding,
        cleared=released + cleared + recovered + filled + untangled,
        reminded=reminded,
    )


async def _stuck_jobs(session: AsyncSession, moment: datetime) -> tuple[int, int]:
    """每一筆卡住的 Job 開（或更新）一件，收掉不再卡住的。回（開著的件數，收掉的件數）。

    已經有別的 Issue 管著它現在這個狀態的不開（`_covered`：重新送單被拒、落回 `submit_failed` 的
    `client_removed`）。Job 離開那個狀態時 poller 那一輪就收掉了（`issues.close_settled`）；這裡收的
    是還在那個狀態、但不再算卡住的——送單失敗又排上了自動重送。
    """
    rows = list(await session.scalars(select(Job).where(Job.state.in_(_STUCK_JOBS))))
    kinds = [stuck.kind for stuck in _STUCK_JOBS.values()]
    covered = await _covered(session, rows, excluding=kinds)
    last = await _last_stops(session, rows)
    flagged: set[tuple[IssueType, str]] = set()
    for job in rows:
        kind, stopped_by, waits = _STUCK_JOBS[job.state]
        stopped, payload = last.get((job.hash, stopped_by.value), (None, {}))
        since = stopped or job.completed_at or job.added_at
        if (
            job.hash in covered
            or (job.state is JobState.SUBMIT_FAILED and _retry_pending(payload, moment))
            or (waits and moment - since < STUCK_AFTER)
        ):
            continue
        await record_issue(
            session,
            kind,
            job_hash=job.hash,
            detail={
                "name": job.name,
                "state": job.state.value,
                "error": job.error,
                "since": since.isoformat(),
            },
            now=moment,
        )
        flagged.add((kind, job.hash))
    cleared = await _settle(session, kinds, flagged, moment)
    return len(flagged), cleared


def _retry_pending(failure: dict[str, Any], moment: datetime) -> bool:
    """這一次送單失敗還有自動重送排著。過了時間還沒送的也算——qBittorrent 停機時 `retry_due` 不花
    次數、等它回來；但過期滿 `STUCK_AFTER` 就不算了：Route 停用或紅著時 `retry_due` 也是留在原地
    不送，那一筆沒有人在管（M5 票 03 code-review）。"""
    retry_at = failure.get("retry_at")
    return isinstance(retry_at, str) and moment - datetime.fromisoformat(retry_at) < STUCK_AFTER


async def _last_stops(
    session: AsyncSession, jobs: list[Job]
) -> dict[tuple[str, str], tuple[datetime, dict[str, Any]]]:
    """每一筆的 `_STUCK_JOBS` 那幾種事件，各自最後一筆的時刻與 payload，鍵是（hash, 事件型別）。"""
    if not jobs:
        return {}
    found: dict[tuple[str, str], tuple[datetime, dict[str, Any]]] = {}
    for job_hash, event, created_at, payload in (
        await session.execute(
            select(Event.job_hash, Event.type, Event.created_at, Event.payload_json)
            .where(
                Event.job_hash.in_([job.hash for job in jobs]),
                Event.type.in_([stuck.stopped_by.value for stuck in _STUCK_JOBS.values()]),
            )
            .order_by(Event.id)
        )
    ).tuples():
        if job_hash is not None:
            found[(job_hash, event)] = (created_at, payload or {})
    return found


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

    `read_holdings` 一部作品要幾十 ms，所以先從這個 Series 自己的集數找出過了寬限的候選，有候選的
    作品才問它（`scripts/experiments/sweep_loop_lag.py`）。
    """
    landed: dict[int, dict[tuple[int, int], datetime]] = {}
    media_of: dict[int, str] = {}
    for row in await _series_imports(session):
        if row.season == 0:
            continue
        media_of[row.series] = row.media
        mine = landed.setdefault(row.series, {})
        for number in range(row.start, row.end + 1):
            pair = (row.season, number)
            mine[pair] = min(mine.get(pair, row.at), row.at)

    missing_in: dict[str, set[tuple[int, int]]] = {}
    flagged: dict[int, list[tuple[int, int]]] = {}
    for series_id, mine in landed.items():
        candidates = _gaps(mine, moment)
        if not candidates:
            continue
        media_id = media_of[series_id]
        if media_id not in missing_in:
            missing_in[media_id] = await _missing_in(session, media_id)
        holes = [pair for pair in candidates if pair in missing_in[media_id]]
        if holes:
            flagged[series_id] = holes

    for series_id, holes in flagged.items():
        await record_issue(
            session,
            IssueType.SERIES_EPISODES_MISSING,
            series_id=series_id,
            detail={
                **await _about(session, series_id),
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


async def _colliding_episodes(session: AsyncSession, moment: datetime) -> tuple[int, int]:
    """每一個有「同一集意外多份」的 RSS Series 開（或更新）一件；改正了、刪掉了的收掉。回（開著的
    件數，收掉的件數）。

    **意外**（2026-10-22 協調者確認，票 130 的 Comments）：同一個 Series 的兩筆以上不同的 Job 入庫成
    同一集（帳本 `ok`、同季同起始集），而它們的發佈名寫的集號不同（合集看範圍：有兩個範圍不相交，
    `_apart`）——兩個不同的發佈被對到同一集（offset、絕對編號換算、季名讀錯）。發佈名讀不出集號的
    那一筆不參與比較。**版本並存不算**
    （brief §7.7、§7.8）：別的 Series 的同一集、發佈名寫同一集的 v2 / 简繁 / 不同解析度 / `[2]`。
    比 Tags 分不出這兩種：Tags 全同的第二份在規劃時就被擋成 `duplicate`，進得了帳本的 Tags 一定
    不同。
    """
    names: dict[int, dict[tuple[int, int], dict[str, str]]] = {}
    for row in await _series_imports(session):
        if row.ok:
            at = names.setdefault(row.series, {}).setdefault((row.season, row.start), {})
            at[row.job_hash] = row.release

    flagged: dict[int, list[dict[str, Any]]] = {}
    for series_id, episodes in names.items():
        hits = [
            {"season": season, "episode": start, "releases": sorted(jobs.values())}
            for (season, start), jobs in sorted(episodes.items())
            if len(jobs) > 1 and _apart(await _written_spans(jobs.values()))
        ]
        if hits:
            flagged[series_id] = hits

    for series_id, hits in flagged.items():
        await record_issue(
            session,
            IssueType.SERIES_EPISODES_COLLIDE,
            series_id=series_id,
            detail={**await _about(session, series_id), "collisions": hits},
            now=moment,
        )
    cleared = await _settle(
        session,
        (IssueType.SERIES_EPISODES_COLLIDE,),
        {(IssueType.SERIES_EPISODES_COLLIDE, str(series_id)) for series_id in flagged},
        moment,
    )
    return len(flagged), cleared


async def _written_spans(names: Iterable[str]) -> list[tuple[int, int]]:
    """這幾個發佈名各自寫的集數範圍（單集是同一集起迄）；讀不出集號的不算。

    **一個名字讓出一次迴圈**：解析一個發佈名約 15 ms（guessit），同一集有簡繁兩版的 Series 每一集
    都要解析，連著解析一整輪會佔住迴圈好幾秒（`scripts/experiments/sweep_loop_lag.py`）。
    """
    spans: list[tuple[int, int]] = []
    for name in names:
        info = parse_release(name)
        if info.episode is not None:
            spans.append((info.episode, info.episode_end or info.episode))
        await asyncio.sleep(0)
    return spans


def _apart(spans: list[tuple[int, int]]) -> bool:
    """有兩個範圍不相交：兩個寫著不同集的發佈。季末的合集 `[01-12]` 蓋到每週的那一集，是同一集的
    版本（M4 票 130 code-review）。"""
    return any(
        first[1] < second[0] or second[1] < first[0]
        for index, first in enumerate(spans)
        for second in spans[index + 1 :]
    )


@dataclass(frozen=True, slots=True)
class _Landed:
    """一個 RSS Series 送來、入庫成它那部作品正片的帳本一列（`_series_imports`）。"""

    series: int
    media: str
    season: int
    start: int
    end: int
    #: 入庫的那一刻。
    at: datetime
    #: 帳本那一列現在對得上磁碟（`LedgerStatus.OK`）。
    ok: bool
    job_hash: str
    #: 那一筆 Job 的發佈名。
    release: str


#: `_series_imports` 一次組幾列就讓出迴圈。
_PARTITION = 500


async def _series_imports(session: AsyncSession) -> list[_Landed]:
    """每一個綁好的 RSS Series 送來、入庫成它那部作品的正片（帳本 `import`、有季集）的每一列。缺集與
    意外多份都從這一份看「這個 Series 自己入庫過什麼」。

    **只選用得到的欄位、分批組列**：整份組成 ORM 物件時一次佔住迴圈近 200 ms（400 個 Series ×
    12 集，`scripts/experiments/sweep_loop_lag.py`）。
    """
    result = await session.stream(
        select(
            RssSeries.id,
            RssSeries.media_id,
            LedgerEntry.season,
            LedgerEntry.episode_start,
            LedgerEntry.episode_end,
            LedgerEntry.created_at,
            LedgerEntry.status,
            Job.hash,
            Job.name,
        )
        .join(
            Job,
            (Job.trigger == JobTrigger.RSS) & (cast(Job.trigger_ref, Integer) == RssSeries.id),
        )
        .join(LedgerEntry, LedgerEntry.job_hash == Job.hash)
        .where(
            RssSeries.media_id.is_not(None),
            LedgerEntry.media_id == RssSeries.media_id,
            LedgerEntry.action == PlanAction.IMPORT,
            LedgerEntry.season.is_not(None),
            LedgerEntry.episode_start.is_not(None),
        )
    )
    rows: list[_Landed] = []
    async for partition in result.partitions(_PARTITION):
        for series, media, season, start, end, at, status, job_hash, release in partition:
            # 上面的 where 擋掉了這三格是 NULL 的列，查詢結果的型別上看不出來。
            assert media is not None and season is not None and start is not None
            rows.append(
                _Landed(
                    series=series,
                    media=media,
                    season=season,
                    start=start,
                    end=end or start,
                    at=at,
                    ok=status is LedgerStatus.OK,
                    job_hash=job_hash,
                    release=release,
                )
            )
    return rows


async def _about(session: AsyncSession, series_id: int) -> dict[str, Any]:
    """巡檢開在 Series 上的那幾件共用的 `detail`：哪一個 Series、哪一部作品（列上連到作品頁）。

    `name`（清單上那一列的標題）是「作品 × 字幕組」，同審核頁的第一批（M4 票 11）：長出 Series 的
    那一筆發佈名寫著某一集，拿它當標題，缺第 3 集的那一件會被讀成在說第 1 集（M4 票 130 實跑）。
    """
    series = await session.get(RssSeries, series_id)
    assert series is not None  # 剛從 `_series_imports` 讀到它
    media = await session.get(Media, series.media_id) if series.media_id is not None else None
    title = media.snapshot().title if media is not None else ""
    group = series.mikan_subgroup_name or parse_release(series.title_raw).group
    return {
        "series": series.id,
        "name": " × ".join(part for part in (title, group) if part) or series.title_raw,
        "media": series.media_id,
        "title": title,
    }


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


def _gaps(landed: dict[tuple[int, int], datetime], moment: datetime) -> list[tuple[int, int]]:
    """這個 Series 入庫過的集數之間它自己沒有的那幾集；洞之後它最早入庫的一集已滿 `GAP_GRACE`
    的才算。缺不缺還要看媒體庫（`_missing_in`）：別人可能補上了。"""
    gaps: list[tuple[int, int]] = []
    for season in sorted({season for season, _ in landed}):
        mine = {number: at for (this, number), at in landed.items() if this == season}
        for number in range(min(mine) + 1, max(mine)):
            if number in mine:
                continue
            after = min(at for later, at in mine.items() if later > number)
            if moment - after >= GAP_GRACE:
                gaps.append((season, number))
    return gaps


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


async def _covered(
    session: AsyncSession, jobs: list[Job], *, excluding: Collection[IssueType] = ()
) -> set[str]:
    """這幾筆裡已經有一件 Issue 說著它現在這個狀態的（`client_error`；重新送單被拒、落回
    `submit_failed` 的 `client_removed`；卡住的 Job 那三種，M5 票 03），不再為同一筆開第二件：開著的
    那一件已經在等人；被忽略的那一件是人看過、說了不用管，換一個型別再問同一筆是噪音（M4 票 129
    code-review）。收掉的不算：它說的是過去。`excluding` 那幾種不算數：問的人自己就是那幾種。"""
    if not jobs:
        return set()
    state = {job.hash: job.state for job in jobs}
    open_rows = await session.execute(
        select(Issue.type, Issue.job_hash).where(
            Issue.status.in_((IssueStatus.OPEN, IssueStatus.IGNORED)),
            Issue.type.in_(set(STANDS_WHILE) - set(excluding)),
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
