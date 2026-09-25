"""改一個檔案的處置：`POST /files/rematch`（plan §6 files 群組、brief §9.4、M2 票 08）。

誰進得來由門禁決定（`api/gate.py`）：`files/*` 整組只有 `admin`（plan §6、brief §11）。

**Media 詳情與 `/review` 兩個入口打的是這同一支**（票 08 的驗收：不是兩套邏輯）：已入庫的檔案
帶 `ledger_id`，對不到、留在 complete 原位的帶 `job_file_id`。內部建一份單列 Plan 並立刻套用
（`services/rematch.py`），所以回應說的是改完之後它落在哪裡，以及記下這次修正的那一份 Plan。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator

from berth.api.deps import ClientFactoryDep, EventHubDep, ImportHintsDep, SessionDep
from berth.api.errors import refusal_responses
from berth.api.gate import current_user
from berth.api.schemas import SeriesCorrectedOut
from berth.domain import PlanAction, RematchRefusal
from berth.services.jobs import actor_of
from berth.services.rematch import (
    Assignment,
    RematchOutcome,
    RematchRejectedError,
    rematch_file,
)
from berth.services.series_review import correct_series

router = APIRouter(prefix="/files", tags=["files"])

#: 哪一種拒絕該回哪個狀態碼。**每一種理由都要在這裡**（`tests/unit/test_openapi_contract.py`
#: 守著）。404 是指向的東西不在；409 是請求本身沒錯、**現在**做不了——另一個分頁先改了、Plan
#: 還在等審核、目標被佔著、磁碟那一步不成；422 是這一次送來的改動本身說不通。
_STATUS: dict[RematchRefusal, int] = {
    RematchRefusal.LEDGER_MISSING: status.HTTP_404_NOT_FOUND,
    RematchRefusal.FILE_MISSING: status.HTTP_404_NOT_FOUND,
    RematchRefusal.NOT_UNMATCHED: status.HTTP_409_CONFLICT,
    RematchRefusal.PLAN_PENDING: status.HTTP_409_CONFLICT,
    RematchRefusal.NOT_DUPLICATE: status.HTTP_409_CONFLICT,
    RematchRefusal.ACTION_NOT_ALLOWED: status.HTTP_422_UNPROCESSABLE_CONTENT,
    RematchRefusal.EPISODE_REQUIRED: status.HTTP_422_UNPROCESSABLE_CONTENT,
    RematchRefusal.EPISODE_RANGE_REVERSED: status.HTTP_422_UNPROCESSABLE_CONTENT,
    RematchRefusal.EPISODE_NOT_ALLOWED: status.HTTP_422_UNPROCESSABLE_CONTENT,
    RematchRefusal.MEDIA_MISSING: status.HTTP_422_UNPROCESSABLE_CONTENT,
    RematchRefusal.ROUTE_MISSING: status.HTTP_409_CONFLICT,
    RematchRefusal.TARGET_TAKEN: status.HTTP_409_CONFLICT,
    RematchRefusal.LINK_FAILED: status.HTTP_409_CONFLICT,
    RematchRefusal.UNLINK_FAILED: status.HTTP_409_CONFLICT,
    RematchRefusal.NOT_FROM_SERIES: status.HTTP_422_UNPROCESSABLE_CONTENT,
    RematchRefusal.NO_EPISODE_NUMBER: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


class RematchRefusalOut(BaseModel):
    """改不下去時回的那一份。`reason` 給畫面挑句子，`detail` 是檔名、路徑或系統原文，不翻譯。"""

    reason: RematchRefusal
    detail: str


def rematch_responses(*reasons: RematchRefusal) -> dict[int | str, dict[str, Any]]:
    """一支端點真的會回的那幾種（重複版本的三顆也用它，`api/review.py`）。"""
    return refusal_responses(RematchRefusalOut, {reason: _STATUS[reason] for reason in reasons})


#: 磁碟那一步與它之前的守衛：兩支（rematch 與重複版本的決定）都走 `services.rematch.land`。
LANDING_REFUSALS = (
    RematchRefusal.MEDIA_MISSING,
    RematchRefusal.ROUTE_MISSING,
    RematchRefusal.TARGET_TAKEN,
    RematchRefusal.LINK_FAILED,
    RematchRefusal.UNLINK_FAILED,
)

REMATCH_RESPONSES = rematch_responses(
    RematchRefusal.LEDGER_MISSING,
    RematchRefusal.FILE_MISSING,
    RematchRefusal.NOT_UNMATCHED,
    RematchRefusal.PLAN_PENDING,
    RematchRefusal.ACTION_NOT_ALLOWED,
    RematchRefusal.EPISODE_REQUIRED,
    RematchRefusal.EPISODE_RANGE_REVERSED,
    RematchRefusal.EPISODE_NOT_ALLOWED,
    RematchRefusal.NOT_FROM_SERIES,
    RematchRefusal.NO_EPISODE_NUMBER,
    *LANDING_REFUSALS,
)


class RematchIn(BaseModel):
    """哪一個檔案、改成什麼。`ledger_id`（已入庫）與 `job_file_id`（對不到的）**恰好帶一個**。

    季集只屬於劇集的入庫，其餘處置三格都不帶（帶了是 `episode_not_allowed`）。
    """

    ledger_id: int | None = None
    job_file_id: int | None = None
    #: `import`（指派為某一集；電影就是入庫）、`extra`、`skip`（忽略）。
    action: PlanAction
    season: int | None = Field(default=None, ge=0)
    episode_start: int | None = Field(default=None, ge=0)
    episode_end: int | None = Field(default=None, ge=0)
    #: 「套用到這個 RSS Series」（M3 票 13）：由這一集算出季號與 offset 寫回送出它的 RSS Series，
    #: 並重算它底下還沒確認的集數。只對已入庫的指派（`ledger_id` + `import`）。
    apply_to_series: bool = False

    @model_validator(mode="after")
    def _one_file(self) -> RematchIn:
        if (self.ledger_id is None) == (self.job_file_id is None):
            raise ValueError("give exactly one of ledger_id and job_file_id")
        if self.apply_to_series and self.ledger_id is None:
            raise ValueError("apply_to_series needs a ledger_id")
        return self


class RematchOut(BaseModel):
    """改完之後。"""

    #: 記下這一次修正的單列 Plan（`GET /plans/{id}` 讀得到）。套用到 RSS Series 而這一集自己搬不走時
    #: （佔著它那一格的同一批另一集也搬不走）是 `null`：Series 照樣寫回，這一集數在 `series.left`。
    plan_id: int | None
    #: 這個檔案現在在媒體庫的哪裡；不在媒體庫裡（忽略、或上面那種沒搬成）是空字串。
    target_path: str
    #: 沒有拆的舊路徑：那裡的檔案已經不是 Berth 放的那一個（使用者換成了自己的一份，M3 票 01）。
    unmanaged: list[str]
    #: 帶了 `apply_to_series` 時才有值。
    series: SeriesCorrectedOut | None = None


@router.post("/rematch", responses=REMATCH_RESPONSES)
async def post_rematch(
    session: SessionDep,
    factory: ClientFactoryDep,
    hub: EventHubDep,
    imports: ImportHintsDep,
    request: Request,
    body: RematchIn,
) -> RematchOut:
    """建新鏈接 → 拆舊鏈接 → 改帳本 → 通知掃描，一律經過 Plan（brief §9.4）。

    帶 `apply_to_series` 時同一件事之後再寫回 RSS Series 並重算（`series_review.correct_series`）；
    重新規劃過的那幾筆叫醒 importer——它平常 60 秒才醒一次，而按下去的人要的是現在。
    """
    user = current_user(request)
    to = Assignment(
        action=body.action,
        season=body.season,
        episode_start=body.episode_start,
        episode_end=body.episode_end,
    )
    actor = actor_of(user.id if user is not None else None)
    try:
        if body.apply_to_series:
            assert body.ledger_id is not None  # `RematchIn` 擋掉了
            corrected = await correct_series(
                session, factory, hub, body.ledger_id, to=to, actor=actor
            )
            if corrected.replanned:
                imports.nudge()
            return _out(
                corrected.rematched,
                SeriesCorrectedOut(
                    season=corrected.season,
                    episode_offset=corrected.episode_offset,
                    moved=corrected.moved,
                    replanned=corrected.replanned,
                    left=corrected.left,
                ),
            )
        outcome = await rematch_file(
            session,
            factory,
            ledger_id=body.ledger_id,
            job_file_id=body.job_file_id,
            to=to,
            actor=actor,
        )
    except RematchRejectedError as refusal:
        raise rematch_refusal(refusal) from refusal
    return _out(outcome, None)


def _out(outcome: RematchOutcome | None, series: SeriesCorrectedOut | None) -> RematchOut:
    if outcome is None:
        return RematchOut(plan_id=None, target_path="", unmanaged=[], series=series)
    return RematchOut(
        plan_id=outcome.plan_id,
        target_path=outcome.target_path,
        unmanaged=list(outcome.unmanaged),
        series=series,
    )


def rematch_refusal(refusal: RematchRejectedError) -> HTTPException:
    """`reason` 是給畫面挑句子的封閉集合，`detail` 是原文。命名照 `review_refusal`
    （`tests/unit/test_openapi_contract.py` 的登記簿以函式名為鍵）。"""
    body = RematchRefusalOut(reason=refusal.reason, detail=refusal.detail)
    return HTTPException(status_code=_STATUS[refusal.reason], detail=body.model_dump(mode="json"))
