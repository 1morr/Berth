"""Import Plan 的讀取端（plan §6 plans 群組、票 11）。

M1 **只有讀**：逐列編輯、批次核准與拒絕是 Review Queue 的事（plan §11.3 的 M2），而這一支
現在回答的是「那一包下載完之後，Berth 打算把每一個檔案放到哪裡、憑什麼」。停在 review 的
Job 在 M1 就是停在那裡，所以這一份唯讀的答案是使用者唯一看得到的理由（票 11）。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from berth.api.deps import SessionDep
from berth.domain import Confidence, PlanAction, PlanEngine, PlanStatus, PlanSummary
from berth.services.plan import read_plan

router = APIRouter(prefix="/plans", tags=["plans"])


class PlanItemOut(BaseModel):
    """Plan 表格上的一列（brief §6.5：決定、信心與理由）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    #: 相對於 torrent 內容根的路徑。
    rel_path: str
    action: PlanAction
    media_id: str | None
    season: int | None
    episode_start: int | None
    #: 單檔多集時的結尾集號（`S01E01-E02`，brief §6.6）。
    episode_end: int | None
    #: 相對於 Route 目標的位置。`unmatched` 與多數 `review` 是空字串——前者留在原位
    #: （brief §7.4），後者還沒有決定。
    target_path: str
    confidence: Confidence
    #: 為什麼是這個決定，逐條（brief §6.3 最後一條）。
    reasons: list[str]
    #: medium 自動入庫掛的旗標（CONTEXT.md 的 Audit）。M2 的佇列以它列出「已入庫待確認」。
    audit: bool
    #: importer 逐檔回填的失敗原文（票 12）。
    error: str


class PlanOut(BaseModel):
    """一份 Plan。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    #: 哪一個 Job。重新入庫（M2）沒有 Job，那時是 `null`。
    job_hash: str | None
    status: PlanStatus
    engine: PlanEngine
    #: 算出這一份的那一版 Berth。
    engine_version: str
    #: **算出這一份的時間**。重跑會把同一列整份換掉，所以它跟著換。
    created_at: datetime
    summary: PlanSummary
    items: list[PlanItemOut]


@router.get("/{plan_id}")
async def get_plan(session: SessionDep, plan_id: int) -> PlanOut:
    view = await read_plan(session, plan_id)
    if view is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="no such plan")
    return PlanOut.model_validate(view)
