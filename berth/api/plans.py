"""Import Plan 的端點（plan §6 plans 群組、票 11、M2 票 07）。

`GET` 誰都讀得到：停在 review 的那一筆，一般使用者看得到「等管理員審核」與它為什麼停下來。
**逐列改、核准、拒絕只有 admin**（plan §6、brief §11，2026-09-22 拍板），規則在門禁
（`api/gate.py` 的 `ADMIN_ROUTES`），不在這裡。

核准只讓狀態落地（`review → importing`），檔案由 importer 去鏈接；這一層負責叫醒它，拒絕則叫醒
規劃器——兩個迴圈平常 60 秒才醒一次，而按下去的人要的是現在。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from berth.api.deps import (
    ClientFactoryDep,
    EventHubDep,
    ImportHintsDep,
    PlanHintsDep,
    SessionDep,
)
from berth.api.errors import refusal_responses
from berth.api.gate import current_user
from berth.api.schemas import SeriesCorrectedOut
from berth.domain import (
    Confidence,
    FileKind,
    MediaKind,
    PlanAction,
    PlanEngine,
    PlanRefusal,
    PlanStatus,
    PlanSummary,
    ReasonCode,
)
from berth.services.jobs import actor_of
from berth.services.plan_review import (
    ItemEdit,
    PlanRejectedError,
    approve_plan,
    edit_items,
    reject_plan,
)
from berth.services.plan_view import read_plan
from berth.services.series_review import correct_series_from_plan

router = APIRouter(prefix="/plans", tags=["plans"])

#: 哪一種拒絕該回哪個狀態碼。**每一種理由都要在這裡**（`tests/unit/test_openapi_contract.py`
#: 守著）。`not_pending` 與 `item_applied` 是 409：請求本身沒錯，是**現在**做不了——另一個分頁
#: 先決定了，或那一列已經在媒體庫裡。其餘是 422：這一次送來的改動本身說不通。
_STATUS: dict[PlanRefusal, int] = {
    PlanRefusal.PLAN_MISSING: status.HTTP_404_NOT_FOUND,
    PlanRefusal.NOT_PENDING: status.HTTP_409_CONFLICT,
    PlanRefusal.ITEM_MISSING: status.HTTP_422_UNPROCESSABLE_CONTENT,
    PlanRefusal.ITEM_APPLIED: status.HTTP_409_CONFLICT,
    PlanRefusal.ACTION_NOT_ALLOWED: status.HTTP_422_UNPROCESSABLE_CONTENT,
    PlanRefusal.EPISODE_REQUIRED: status.HTTP_422_UNPROCESSABLE_CONTENT,
    PlanRefusal.EPISODE_RANGE_REVERSED: status.HTTP_422_UNPROCESSABLE_CONTENT,
    PlanRefusal.EPISODE_NOT_ALLOWED: status.HTTP_422_UNPROCESSABLE_CONTENT,
    PlanRefusal.MEDIA_MISSING: status.HTTP_422_UNPROCESSABLE_CONTENT,
    PlanRefusal.TARGET_CLASH: status.HTTP_422_UNPROCESSABLE_CONTENT,
    PlanRefusal.UNDECIDED: status.HTTP_422_UNPROCESSABLE_CONTENT,
    PlanRefusal.NOT_FROM_SERIES: status.HTTP_422_UNPROCESSABLE_CONTENT,
    PlanRefusal.NO_EPISODE_NUMBER: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


class PlanRefusalOut(BaseModel):
    """改不下去、核准不了時回的那一份。`reason` 給畫面挑句子，`detail` 是檔名或路徑，不翻譯。"""

    reason: PlanRefusal
    detail: str


def _refusals(*reasons: PlanRefusal) -> dict[int | str, dict[str, Any]]:
    return refusal_responses(PlanRefusalOut, {reason: _STATUS[reason] for reason in reasons})


#: 三支共用的那兩種：這份 Plan 在不在、還在不在等人。
_GATE = (PlanRefusal.PLAN_MISSING, PlanRefusal.NOT_PENDING)

EDIT_RESPONSES = _refusals(
    *_GATE,
    PlanRefusal.ITEM_MISSING,
    PlanRefusal.ITEM_APPLIED,
    PlanRefusal.ACTION_NOT_ALLOWED,
    PlanRefusal.EPISODE_REQUIRED,
    PlanRefusal.EPISODE_RANGE_REVERSED,
    PlanRefusal.EPISODE_NOT_ALLOWED,
    PlanRefusal.MEDIA_MISSING,
    PlanRefusal.TARGET_CLASH,
    PlanRefusal.NOT_FROM_SERIES,
    PlanRefusal.NO_EPISODE_NUMBER,
)
APPROVE_RESPONSES = _refusals(*_GATE, PlanRefusal.UNDECIDED, PlanRefusal.TARGET_CLASH)
REJECT_RESPONSES = _refusals(*_GATE)


class ItemReasonOut(BaseModel):
    """Plan Item 的一條理由：封閉集合的 code 加參數，句子由前端照 code 挑（M2 票 07）。

    參數是檔名、季集標記、日期這種**不翻譯**的事實；`kind`、`action`、`strategy` 三個鍵的值是
    封閉集合，畫面自己翻。
    """

    model_config = ConfigDict(from_attributes=True)

    code: ReasonCode
    params: dict[str, str | int]


class PlanItemOut(BaseModel):
    """Plan 表格上的一列（brief §6.5：決定、信心與理由）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    #: 相對於 torrent 內容根的路徑。
    rel_path: str
    #: 檔案分類（brief §6.2）。它決定這一列改得成哪幾種處置（`actions`）。
    kind: FileKind
    action: PlanAction
    media_id: str | None
    season: int | None
    episode_start: int | None
    #: 單檔多集時的結尾集號（`S01E01-E02`，brief §6.6）。
    episode_end: int | None
    #: 相對於 Route 目標的位置。**`pending_review` 的 Plan 是「核准的話」它會落在哪裡**：
    #: 待審核的列照提案算（M2 票 07），核准時寫下的就是這一條。空字串＝它不會進媒體庫
    #: （略過、Unmatched 留在原位，brief §7.4），或還沒有提案。
    target_path: str
    confidence: Confidence
    #: 為什麼是這個決定，逐條（brief §6.3 最後一條）。
    reasons: list[ItemReasonOut]
    #: medium 自動入庫掛的旗標（CONTEXT.md 的 Audit）。M2 的佇列以它列出「已入庫待確認」。
    audit: bool
    #: 已經鏈接進媒體庫了；改它是重新匹配的事（票 08），這裡改不動。
    applied: bool
    #: 這一列改得成哪幾種處置（依分類）。只有 `pending_review` 而且還沒鏈接的列有；空的＝改不動。
    actions: list[PlanAction]
    #: importer 逐檔回填的失敗原文（票 12）。
    error: str


class PlanSeriesOut(BaseModel):
    """算這一份時用的 RSS Series 與它的季號、offset（M3 票 13）。兩格都是 `null` 是 Series 沒設，
    解析器自己判斷。值是規劃那一刻讀的：之後改正並套用到 Series，這一份仍說它當時用了什麼。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    season: int | None
    episode_offset: int | None


class PlanOut(BaseModel):
    """一份 Plan。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    #: 哪一個 Job。rematch 與重複版本的單列 Plan 是 `null`。
    job_hash: str | None
    status: PlanStatus
    engine: PlanEngine
    #: 算出這一份的那一版 Berth。
    engine_version: str
    #: **算出這一份的時間**。重跑會把同一列整份換掉，所以它跟著換。
    created_at: datetime
    #: 劇集或電影；沒有作品快照時是 `null`。電影的列沒有季集可填。
    media_kind: MediaKind | None
    summary: PlanSummary
    items: list[PlanItemOut]
    #: 不是 RSS 送的是 `null`。
    series: PlanSeriesOut | None


class ItemEditIn(BaseModel):
    """一列要改成什麼。季集只屬於劇集的入庫，其餘處置三格都不帶（帶了是 `episode_not_allowed`）。"""

    id: int
    action: PlanAction
    season: int | None = Field(default=None, ge=0)
    episode_start: int | None = Field(default=None, ge=0)
    episode_end: int | None = Field(default=None, ge=0)


class ItemEditsIn(BaseModel):
    """一次送幾列都行，**整批成立或整批拒絕**。畫面逐列套用，所以通常是一列。"""

    items: list[ItemEditIn] = Field(min_length=1)
    #: 「套用到這個 RSS Series」（M3 票 14b，同 `POST /files/rematch` 的那一格）：由這一列算出季號與
    #: offset 寫回送出它的 RSS Series，同一份裡沒有人碰過的列與其餘還沒確認的集數跟著重算。
    #: 只配**一列**、指派到某一集。
    apply_to_series: bool = False

    @model_validator(mode="after")
    def _each_row_once(self) -> ItemEditsIn:
        """同一列出現兩次時說不出哪一個算數——拒絕，而不是讓後者默默蓋掉前者。"""
        ids = [edit.id for edit in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("each row may appear only once")
        if self.apply_to_series and len(ids) != 1:
            # offset 由「人說的集號減檔名寫的」算出來，兩列說的可能是兩個 offset。
            raise ValueError("apply_to_series takes exactly one row")
        return self


class PlanEditedOut(PlanOut):
    """改完的整份。帶了 `apply_to_series` 時多一格 `corrected`：Series 現在的值，與其餘的集數
    怎麼了。"""

    corrected: SeriesCorrectedOut | None = None


@router.get("/{plan_id}")
async def get_plan(session: SessionDep, plan_id: int) -> PlanOut:
    view = await read_plan(session, plan_id)
    if view is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no such plan")
    return PlanOut.model_validate(view)


@router.put("/{plan_id}/items", responses=EDIT_RESPONSES)
async def put_items(
    session: SessionDep,
    factory: ClientFactoryDep,
    hub: EventHubDep,
    imports: ImportHintsDep,
    request: Request,
    plan_id: int,
    body: ItemEditsIn,
) -> PlanEditedOut:
    """逐列改處置與季集，回改完的整份：改過那一列的新目標路徑就在裡面（M2 票 07）。

    帶 `apply_to_series` 時走 `series_review.correct_series_from_plan`（票 14b）：重新規劃之後通過
    播出日比對的那幾筆直接進入庫，所以叫醒 importer——它平常 60 秒才醒一次。
    """
    edits = [ItemEdit(**edit.model_dump()) for edit in body.items]
    try:
        if not body.apply_to_series:
            view = await edit_items(session, plan_id, edits, actor=_actor(request))
            return PlanEditedOut.model_validate(view)
        corrected = await correct_series_from_plan(
            session, factory, hub, plan_id, edits[0], actor=_actor(request)
        )
    except PlanRejectedError as refusal:
        raise plan_refusal(refusal) from refusal
    if corrected.replanned:
        imports.nudge()
    out = PlanEditedOut.model_validate(corrected.plan)
    out.corrected = SeriesCorrectedOut(
        season=corrected.season,
        episode_offset=corrected.episode_offset,
        moved=corrected.moved,
        replanned=corrected.replanned,
        left=corrected.left,
    )
    return out


@router.post("/{plan_id}/approve", responses=APPROVE_RESPONSES)
async def post_approve(
    session: SessionDep,
    hub: EventHubDep,
    imports: ImportHintsDep,
    request: Request,
    plan_id: int,
) -> PlanOut:
    """核准＝照提案入庫：`review → importing`，然後叫醒 importer（plan §3.1）。"""
    try:
        view = await approve_plan(session, hub, plan_id, actor=_actor(request))
    except PlanRejectedError as refusal:
        raise plan_refusal(refusal) from refusal
    imports.nudge()
    return PlanOut.model_validate(view)


@router.post(
    "/{plan_id}/reject", status_code=status.HTTP_204_NO_CONTENT, responses=REJECT_RESPONSES
)
async def post_reject(
    session: SessionDep, hub: EventHubDep, plans: PlanHintsDep, request: Request, plan_id: int
) -> None:
    """拒絕：`review → completed`，規劃器整份重算（plan §3.1）。204：這一份馬上會被換掉。"""
    try:
        await reject_plan(session, hub, plan_id, actor=_actor(request))
    except PlanRejectedError as refusal:
        raise plan_refusal(refusal) from refusal
    plans.nudge()


def _actor(request: Request) -> str:
    user = current_user(request)
    return actor_of(user.id if user is not None else None)


def plan_refusal(refusal: PlanRejectedError) -> HTTPException:
    """`reason` 是給畫面挑句子的封閉集合，`detail` 是原文。命名照 `review_refusal`
    （`tests/unit/test_openapi_contract.py` 的登記簿以函式名為鍵）。"""
    body = PlanRefusalOut(reason=refusal.reason, detail=refusal.detail)
    return HTTPException(status_code=_STATUS[refusal.reason], detail=body.model_dump(mode="json"))
