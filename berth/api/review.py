"""Review Queue 的端點（plan §6 review 群組、brief §6.5、M2 票 06）。

誰進得來由門禁決定（`api/gate.py`）：`review/*` 整組只有 `admin`（plan §6、brief §11，
2026-09-22 拍板）。`user` 送單之後碰到低信心 Plan 只能等，那一句「等管理員審核」在他看得到的
地方（Media 詳情、`/jobs`），不在這裡。

**一支端點、一份清單、一列一件事**（plan §11.3 決定 6）。每一列以 `kind` 區分形狀：共同的是
指向它的物件（`ref`）、一句封閉集合的理由（`reason`，code + 參數，前端翻譯）、這一列能按的動作
與它開始等人的時間；各類自己的欄位跟在後面。`issue` 那一類的動作打的是 `issues/*` 的那兩支，
這裡只有 audit 的兩顆；`plan` 那一類的核准與拒絕打的是 `plans/*`（`api/plans.py`）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from berth.api.deps import SessionDep
from berth.api.errors import refusal_responses
from berth.api.gate import current_user
from berth.api.issues import IssueOut, issue_out
from berth.api.plans import ItemReasonOut
from berth.domain import (
    AuditAction,
    AuditReason,
    IssueAction,
    IssueType,
    PlanDecision,
    PlanSummary,
    ReviewKind,
    ReviewReason,
    ReviewRefusal,
)
from berth.services.jobs import actor_of
from berth.services.review import (
    AuditRow,
    IssueRow,
    PlanRow,
    ReviewRejectedError,
    ReviewRow,
    confirm_audit,
    review_queue,
    undo_audit,
)

router = APIRouter(prefix="/review", tags=["review"])

#: 哪一種拒絕該回哪個狀態碼。**每一種理由都要在這裡**（`tests/unit/test_openapi_contract.py`
#: 守著）。`not_audited` 與 `unlink_failed` 是 409：請求本身沒問題，是**現在**做不了——另一個
#: 分頁先按了，或那一條掛載壞著。
_STATUS: dict[ReviewRefusal, int] = {
    ReviewRefusal.LEDGER_MISSING: status.HTTP_404_NOT_FOUND,
    ReviewRefusal.NOT_AUDITED: status.HTTP_409_CONFLICT,
    ReviewRefusal.UNLINK_FAILED: status.HTTP_409_CONFLICT,
}


class ReviewRefusalOut(BaseModel):
    """做不了的時候回的那一份。`reason` 給畫面挑句子，`detail` 是原文，不翻譯。"""

    reason: ReviewRefusal
    detail: str


def _refusals(*reasons: ReviewRefusal) -> dict[int | str, dict[str, Any]]:
    return refusal_responses(ReviewRefusalOut, {reason: _STATUS[reason] for reason in reasons})


#: 確認只改旗標，所以只有這一列本身的兩種。
CONFIRM_RESPONSES = _refusals(ReviewRefusal.LEDGER_MISSING, ReviewRefusal.NOT_AUDITED)

#: 撤銷另外要真的拆一條鏈接。
UNDO_RESPONSES = _refusals(
    ReviewRefusal.LEDGER_MISSING, ReviewRefusal.NOT_AUDITED, ReviewRefusal.UNLINK_FAILED
)


class AuditReasonOut(BaseModel):
    """`audit` 那一列的理由：封閉集合的 code 加參數，句子由前端照 code 挑（M2 票 06）。"""

    code: AuditReason
    params: dict[str, Any]


class IssueReasonOut(BaseModel):
    """`issue` 那一列的理由：code 是 Issue 的型別，參數是它逐型別不同的那幾格。"""

    code: IssueType
    params: dict[str, Any]


class PlanReasonOut(BaseModel):
    """`plan` 那一列的理由：為什麼這一份停下來（`ReviewReason`），參數是它的計數。"""

    code: ReviewReason
    params: dict[str, Any]


class PlanRowOut(BaseModel):
    """一份停在 review 的 Plan（M2 票 07）。`ref` 是 Plan 的 id，逐列的內容打 `GET /plans/{ref}`。

    逐列不跟著來：一包 39 個檔案的理由塞進佇列的每一列，佇列本身就讀不動了；畫面展開那一列時才要。
    """

    kind: Literal[ReviewKind.PLAN]
    ref: int
    reason: PlanReasonOut
    #: 核准、拒絕，順序就是畫面上的順序。
    actions: list[PlanDecision]
    #: 這一份算出來的那一刻。
    at: datetime
    media_id: str | None
    #: 作品名的兩輪（brief §7.5），畫面照 UI 語言挑。沒有作品時都是空字串。
    title: str
    title_en: str
    job_hash: str
    job_name: str
    summary: PlanSummary


class AuditRowOut(BaseModel):
    """一個 medium 自動入庫、等人看一眼的檔案（CONTEXT.md 的 Audit）。`ref` 是帳本那一列的 id。"""

    kind: Literal[ReviewKind.AUDIT]
    ref: int
    reason: AuditReasonOut
    #: 這一列按得了哪幾顆，順序就是畫面上的順序。
    actions: list[AuditAction]
    #: 它開始等人的那一刻：入庫的時間。
    at: datetime
    media_id: str | None
    #: 作品名的兩輪（brief §7.5），畫面照 UI 語言挑。沒有作品時都是空字串。
    title: str
    title_en: str
    job_hash: str
    job_name: str
    #: 媒體庫裡那個硬鏈接。
    path: str
    source_path: str
    season: int | None
    episode_start: int | None
    episode_end: int | None
    #: 解析器為什麼給 medium（那一列 Plan Item 的理由）。
    reasons: list[ItemReasonOut]


class IssueRowOut(BaseModel):
    """一件還開著的 Issue。`ref` 是 Issue 的 id，動作打 `POST /issues/{ref}/resolve`。

    **整件 `IssueOut` 跟著來**：同一件事在 `/issues` 與這裡畫的是同一個元件，而它要的每一格
    （來源路徑、按得了哪幾顆）都在那一份裡——在這裡另外攤一份，兩頁就會各說各的。
    """

    kind: Literal[ReviewKind.ISSUE]
    ref: int
    reason: IssueReasonOut
    #: 按得了哪幾顆，順序就是畫面上的順序。空的代表只剩「忽略」（同 `IssueOut.actions`）。
    actions: list[IssueAction]
    #: 它開始等人的那一刻：偵測到的時間。
    at: datetime
    issue: IssueOut


ReviewRowOut = Annotated[PlanRowOut | AuditRowOut | IssueRowOut, Field(discriminator="kind")]


class ReviewQueueOut(BaseModel):
    """整份佇列。**不分頁**（plan §6）：`rows` 最多 200 列，`total` 是全部幾件。"""

    rows: list[ReviewRowOut]
    total: int


@router.get("")
async def get_review(session: SessionDep) -> ReviewQueueOut:
    """需要人動手的排前面，同一類之內舊的在前（plan §6）。"""
    queue = await review_queue(session)
    return ReviewQueueOut(rows=[_row_out(row) for row in queue.rows], total=queue.total)


@router.post(
    "/audit/{ledger_id}/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=CONFIRM_RESPONSES,
)
async def post_confirm(session: SessionDep, request: Request, ledger_id: int) -> None:
    """「它是對的」：清掉 `ledger.audit` 與那一列 Plan Item 的旗標，寫 `audit_confirmed`。

    204 而不是回那一列：確認完它就不在佇列上了，畫面要的是重問一次佇列。
    """
    user = current_user(request)
    try:
        await confirm_audit(
            session, ledger_id, actor=actor_of(user.id if user is not None else None)
        )
    except ReviewRejectedError as refusal:
        raise review_refusal(refusal) from refusal


@router.post(
    "/audit/{ledger_id}/undo",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=UNDO_RESPONSES,
)
async def post_undo(session: SessionDep, request: Request, ledger_id: int) -> None:
    """「它是錯的」：拆掉硬鏈接、刪掉帳本那一列、Job 回 `review`（`audit_undone`）。"""
    user = current_user(request)
    try:
        await undo_audit(session, ledger_id, actor=actor_of(user.id if user is not None else None))
    except ReviewRejectedError as refusal:
        raise review_refusal(refusal) from refusal


def _row_out(row: ReviewRow) -> PlanRowOut | AuditRowOut | IssueRowOut:
    if isinstance(row, PlanRow):
        return _plan_out(row)
    if isinstance(row, IssueRow):
        view = row.issue
        return IssueRowOut(
            kind=ReviewKind.ISSUE,
            ref=view.id,
            reason=IssueReasonOut(code=view.type, params=view.detail),
            actions=list(view.actions),
            at=view.detected_at,
            issue=issue_out(view),
        )
    return _audit_out(row)


def _plan_out(row: PlanRow) -> PlanRowOut:
    summary = row.summary
    return PlanRowOut(
        kind=ReviewKind.PLAN,
        ref=row.plan_id,
        reason=PlanReasonOut(
            code=row.reason,
            params={"files": summary.files, "low": summary.low, "medium": summary.medium},
        ),
        actions=list(row.actions),
        at=row.at,
        media_id=row.media_id,
        title=row.title,
        title_en=row.title_en,
        job_hash=row.job_hash,
        job_name=row.job_name,
        summary=summary,
    )


def _audit_out(row: AuditRow) -> AuditRowOut:
    return AuditRowOut(
        kind=ReviewKind.AUDIT,
        ref=row.ledger_id,
        reason=AuditReasonOut(code=row.reason, params={}),
        actions=list(row.actions),
        at=row.at,
        media_id=row.media_id,
        title=row.title,
        title_en=row.title_en,
        job_hash=row.job_hash,
        job_name=row.job_name,
        path=row.target_path,
        source_path=row.source_path,
        season=row.season,
        episode_start=row.episode_start,
        episode_end=row.episode_end,
        reasons=[ItemReasonOut.model_validate(reason) for reason in row.reasons],
    )


def review_refusal(refusal: ReviewRejectedError) -> HTTPException:
    """`reason` 是給畫面挑句子的封閉集合，`detail` 是原文。命名照 `issue_refusal`
    （`tests/unit/test_openapi_contract.py` 的登記簿以函式名為鍵）。"""
    body = ReviewRefusalOut(reason=refusal.reason, detail=refusal.detail)
    return HTTPException(status_code=_STATUS[refusal.reason], detail=body.model_dump(mode="json"))
