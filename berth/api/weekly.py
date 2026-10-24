"""週報的端點（M4 票 131，plan §11.5〈巡檢〉）。只有管理員進得來（`services/access.py` 的
`ADMIN_PREFIXES`）。

只有讀：週報由 `sweeper` 每週一產生（`services.weekly`），這裡沒有「現在產生一份」的端點。
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from berth.api.deps import SessionDep
from berth.domain import IssueType, MediaKind
from berth.services.weekly import ReportMissingError, list_reports, read_report

router = APIRouter(prefix="/weekly", tags=["weekly"])


class WeeklyLineOut(BaseModel):
    """歷史清單的一列。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    #: 這一週的第一天與最後一天（容器時區的週一到週日）。
    first_day: date
    last_day: date
    #: 入庫了幾部作品、合計幾集。
    works: int
    episodes: int
    #: 修了幾件（核准、rematch、解決與收掉的 Issue 加起來）。
    fixed: int
    #: 產生那一刻還等著幾件。
    waiting: int


class ImportedWorkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    #: 作品被刪了是 `null`（不連到作品頁）。
    media: str | None
    kind: MediaKind | None
    title: str
    title_en: str
    #: `[季, 起, 迄]`，接得上的已經併成一段。電影是空的。
    episodes: list[tuple[int, int, int]]


class FixedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    approved: int
    rematched: int
    #: 人按下去解決的 Issue，照型別數。
    resolved: dict[IssueType, int]
    #: 條件不在了、系統收掉的 Issue，照型別數。
    cleared: dict[IssueType, int]


class StillWaitingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    review: int
    issues: dict[IssueType, int]
    rss: int
    #: `issues` 裡每日巡檢開的那幾種；已經算在 `issues` 裡。
    swept: dict[IssueType, int]


class WeeklyReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_day: date
    last_day: date
    created_at: datetime
    imported: list[ImportedWorkOut]
    fixed: FixedOut
    waiting: StillWaitingOut


@router.get("")
async def get_reports(session: SessionDep) -> list[WeeklyLineOut]:
    """每一份一列，最新的一週在前。"""
    return [WeeklyLineOut.model_validate(line) for line in await list_reports(session)]


@router.get("/{report_id}")
async def get_report(session: SessionDep, report_id: int) -> WeeklyReportOut:
    try:
        view = await read_report(session, report_id)
    except ReportMissingError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no such weekly report") from None
    return WeeklyReportOut.model_validate(view)
