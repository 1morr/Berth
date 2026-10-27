"""週報：每週一份，產生那一刻算好存下來（M4 票 131，plan §11.5〈巡檢〉、CONTEXT.md 的週報）。

回答三件事：這週入庫了什麼（依作品，季集範圍）、修了什麼（核准、rematch、Issue 被人解決或被系統
收掉）、還有什麼等人（產生那一刻「等你處理」的三份清單，巡檢開的 Issue 另外點出來）。

- **存結果**（`models/weekly.py`）：purge 會連帳本與事件一起刪，舊週報要是每次重算就會跟著變。
- **一週**是週一 `at`（巡檢的時刻，容器時區）起到下一個週一 `at`，由排程照那一刻的牆上時間算
  （`week_ending`）；身分是開始那一天（`week_of`），同一週再產生什麼都不寫。
- **摘要**：產生的同一筆交易裡給訂閱了「週報」、有 Discord ID 的管理員各排一則（`recipients`），
  內容是三個數與那一份的 id，送出時組字、連到週報頁那一週（`notify._render_weekly`）。
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import (
    SWEPT_ISSUE_TYPES,
    SYSTEM,
    EventType,
    IssueStatus,
    IssueType,
    MediaKind,
    NotificationKind,
    PlanAction,
    PlanStatus,
)
from berth.models import Event, Issue, Job, LedgerEntry, Media, Notification, WeeklyReport
from berth.models.types import utcnow
from berth.services.commands import Effect, Flag, command
from berth.services.notify import episode_spans
from berth.services.recipients import subscribers
from berth.services.waiting import WaitingSource, waiting_now

logger = logging.getLogger(__name__)

#: 一週的長度。換日光節約時間的那一週牆上時間差一小時，照樣是七天（同 `reconciler`）。
WEEK = timedelta(days=7)


@dataclass(frozen=True, slots=True)
class ImportedWork:
    """這一週入庫的一部作品。作品被刪了（帳本的 `media_id` 是 `SET NULL`）時 `media` 與 `kind`
    是 `None`，標題是那一筆 Job 的發佈名。"""

    media: str | None
    kind: MediaKind | None
    title: str
    title_en: str
    #: `(季, 起, 迄)`，接得上的已經併成一段。電影是空的。
    episodes: tuple[tuple[int, int, int], ...]


@dataclass(frozen=True, slots=True)
class Fixed:
    """這一週修了什麼。"""

    #: 核准的計劃（`review_decided` 的 `approved`）。
    approved: int
    #: rematch 的檔案（`rematched`）。
    rematched: int
    #: 人按下去解決的 Issue，照型別數。
    resolved: dict[IssueType, int]
    #: 條件不在了、系統收掉的 Issue，照型別數。
    cleared: dict[IssueType, int]

    @property
    def total(self) -> int:
        return (
            self.approved
            + self.rematched
            + sum(self.resolved.values())
            + sum(self.cleared.values())
        )


@dataclass(frozen=True, slots=True)
class StillWaiting:
    """產生那一刻還等著的（`waiting.waiting_now`，「有 N 件等你處理」同一份）。"""

    review: int
    #: 開著的 Issue，照型別數。
    issues: dict[IssueType, int]
    #: 待綁定的 RSS Series。
    rss: int
    #: `issues` 裡巡檢開的那幾種（`SWEPT_ISSUE_TYPES`）。不另算進總數。
    swept: dict[IssueType, int]

    @property
    def total(self) -> int:
        return self.review + sum(self.issues.values()) + self.rss


@dataclass(frozen=True, slots=True)
class WeeklyView:
    id: int
    first_day: date
    last_day: date
    created_at: datetime
    imported: tuple[ImportedWork, ...]
    fixed: Fixed
    waiting: StillWaiting


@dataclass(frozen=True, slots=True)
class WeeklyLine:
    """歷史清單的一列：哪一週與三段各幾件。"""

    id: int
    first_day: date
    last_day: date
    #: 入庫了幾部作品、合計幾集。
    works: int
    episodes: int
    fixed: int
    waiting: int


class ReportMissingError(LookupError):
    """沒有這一份週報。"""


def week_ending(moment: datetime, at: time) -> datetime:
    """`moment` 之前（含）最近的那一個週一 `at`：最新一份該有的週報在那一刻結束。
    時區照 `moment`。"""
    monday = moment.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0) - timedelta(
        days=moment.weekday()
    )
    return monday if monday <= moment else monday - WEEK


# 寫一份週報並排摘要；摘要送出去就收不回來。
@command(Effect.IRREVERSIBLE, flags={Flag.INTERNAL, Flag.SENDS_OUT})
async def compose_weekly(
    session: AsyncSession, *, ends_at: datetime, now: datetime | None = None
) -> WeeklyView | None:
    """產生在 `ends_at` 結束的那一週並 commit；那一週已經有了就什麼都不寫、回 `None`。

    `ends_at` 帶容器時區（`week_ending` 算的）：那一週的身分是它往前七天那一天的牆上日期。
    `now` 是產生的時刻（摘要立刻送：一週一則，沒有要合併的）。
    """
    moment = now or utcnow()
    starts_at = ends_at - WEEK
    week_of = starts_at.date().isoformat()
    if await session.scalar(select(WeeklyReport.id).where(WeeklyReport.week_of == week_of)):
        return None
    content = {
        "imported": await _imported(session, starts_at, ends_at),
        "fixed": await _fixed(session, starts_at, ends_at),
        "waiting": await _waiting(session),
    }
    report = WeeklyReport(
        week_of=week_of,
        starts_at=starts_at,
        ends_at=ends_at,
        content_json=content,
        created_at=moment,
    )
    session.add(report)
    await session.flush()
    line = _line(report)
    for user in await subscribers(session, NotificationKind.WEEKLY):
        session.add(
            Notification(
                user_id=user.id,
                kind=NotificationKind.WEEKLY,
                content_json={
                    "report": report.id,
                    "week_of": week_of,
                    "works": line.works,
                    "episodes": line.episodes,
                    "fixed": line.fixed,
                    "waiting": line.waiting,
                },
                merge_key=f"{NotificationKind.WEEKLY.value}:{week_of}",
                not_before=moment,
                created_at=moment,
            )
        )
    await session.commit()
    logger.info("weekly report composed", extra={"week_of": week_of, "report": report.id})
    return _view(report)


@command(Effect.READ)
async def read_report(session: AsyncSession, report_id: int) -> WeeklyView:
    report = await session.get(WeeklyReport, report_id)
    if report is None:
        raise ReportMissingError(report_id)
    return _view(report)


@command(Effect.READ)
async def has_reports(session: AsyncSession) -> bool:
    """有沒有任何一份。"""
    return await session.scalar(select(WeeklyReport.id).limit(1)) is not None


@command(Effect.READ)
async def list_reports(session: AsyncSession) -> list[WeeklyLine]:
    """每一份一列，最新的一週在前。一年 52 列，不分頁。"""
    return [
        _line(report)
        for report in await session.scalars(
            select(WeeklyReport).order_by(WeeklyReport.week_of.desc())
        )
    ]


# --- 產生 -----------------------------------------------------------------


async def _imported(session: AsyncSession, starts_at: datetime, ends_at: datetime) -> list[Any]:
    """這一週入庫的正片，依作品收成季集範圍。只算屬於某一筆 Job 的帳本列：`rebuild-ledger` 與
    認領長回來的列（`job_hash` 是 `None`）是補記帳，不是這一週入庫的。"""
    entries = list(
        await session.scalars(
            select(LedgerEntry).where(
                LedgerEntry.action == PlanAction.IMPORT,
                LedgerEntry.job_hash.is_not(None),
                LedgerEntry.created_at >= starts_at,
                LedgerEntry.created_at < ends_at,
            )
        )
    )
    by_work: dict[str, list[LedgerEntry]] = {}
    for entry in entries:
        by_work.setdefault(entry.media_id or f"job:{entry.job_hash}", []).append(entry)
    works: list[dict[str, Any]] = []
    for key, rows in by_work.items():
        work = await _work(session, key, rows)
        if work is not None:
            works.append(work)
    # 照英文標題排：中文標題的碼位順序對人沒有意義，英文字母序至少是一個查得到的順序。
    return sorted(works, key=lambda work: (work["title_en"].casefold(), work["media"] or ""))


async def _work(session: AsyncSession, key: str, rows: list[LedgerEntry]) -> dict[str, Any] | None:
    media = await session.get(Media, rows[0].media_id) if rows[0].media_id else None
    if media is not None:
        snapshot = media.snapshot()
        kind: MediaKind | None = snapshot.kind
        title, title_en = snapshot.title, snapshot.title_en
    else:
        # 作品被刪了：用那一筆 Job 的發佈名；Job 也不在就沒有名字可說。
        job = await session.get(Job, rows[0].job_hash)
        if job is None:
            return None
        kind, title, title_en = None, job.name, job.name
    movie = kind is MediaKind.MOVIE
    return {
        "media": media.id if media else None,
        "kind": kind.value if kind else None,
        "title": title,
        "title_en": title_en,
        "episodes": [] if movie else [list(span) for span in episode_spans(rows)],
    }


async def _fixed(session: AsyncSession, starts_at: datetime, ends_at: datetime) -> dict[str, Any]:
    approved = rematched = 0
    for kind, payload in await session.execute(
        select(Event.type, Event.payload_json).where(
            Event.type.in_([EventType.REVIEW_DECIDED.value, EventType.REMATCHED.value]),
            Event.created_at >= starts_at,
            Event.created_at < ends_at,
        )
    ):
        if kind == EventType.REMATCHED.value:
            rematched += 1
        elif (payload or {}).get("decision") == PlanStatus.APPROVED.value:
            approved += 1
    resolved: dict[str, int] = {}
    cleared: dict[str, int] = {}
    for issue_type, by in await session.execute(
        select(Issue.type, Issue.resolved_by).where(
            Issue.status == IssueStatus.RESOLVED,
            Issue.resolved_at >= starts_at,
            Issue.resolved_at < ends_at,
        )
    ):
        tally = cleared if by == SYSTEM else resolved
        tally[issue_type.value] = tally.get(issue_type.value, 0) + 1
    return {"approved": approved, "rematched": rematched, "resolved": resolved, "cleared": cleared}


async def _waiting(session: AsyncSession) -> dict[str, Any]:
    current = (await waiting_now(session)).values()
    issues: dict[str, int] = {}
    for one in current:
        if one.source is WaitingSource.ISSUE and one.issue_type is not None:
            issues[one.issue_type.value] = issues.get(one.issue_type.value, 0) + 1
    return {
        "review": sum(1 for one in current if one.source is WaitingSource.REVIEW),
        "issues": issues,
        "rss": sum(1 for one in current if one.source is WaitingSource.RSS),
        "swept": {
            kind: count for kind, count in issues.items() if IssueType(kind) in SWEPT_ISSUE_TYPES
        },
    }


# --- 讀 -------------------------------------------------------------------


def _view(report: WeeklyReport) -> WeeklyView:
    content = report.content_json
    fixed = content["fixed"]
    waiting = content["waiting"]
    first_day = date.fromisoformat(report.week_of)
    return WeeklyView(
        id=report.id,
        first_day=first_day,
        last_day=first_day + WEEK - timedelta(days=1),
        created_at=report.created_at,
        imported=tuple(
            ImportedWork(
                media=work["media"],
                kind=MediaKind(work["kind"]) if work["kind"] else None,
                title=work["title"],
                title_en=work["title_en"],
                episodes=tuple((s, a, b) for s, a, b in work["episodes"]),
            )
            for work in content["imported"]
        ),
        fixed=Fixed(
            approved=fixed["approved"],
            rematched=fixed["rematched"],
            resolved=_types(fixed["resolved"]),
            cleared=_types(fixed["cleared"]),
        ),
        waiting=StillWaiting(
            review=waiting["review"],
            issues=_types(waiting["issues"]),
            rss=waiting["rss"],
            swept=_types(waiting["swept"]),
        ),
    )


def _types(tally: dict[str, int]) -> dict[IssueType, int]:
    """存下的型別照 `IssueType` 讀回；之後拿掉的型別略過（存的是那一刻的值）。"""
    known = {kind.value for kind in IssueType}
    return {IssueType(kind): count for kind, count in tally.items() if kind in known}


def _line(report: WeeklyReport) -> WeeklyLine:
    view = _view(report)
    return WeeklyLine(
        id=view.id,
        first_day=view.first_day,
        last_day=view.last_day,
        works=len(view.imported),
        episodes=_episodes(view.imported),
        fixed=view.fixed.total,
        waiting=view.waiting.total,
    )


def _episodes(works: Iterable[ImportedWork]) -> int:
    return sum(end - start + 1 for work in works for _, start, end in work.episodes)
