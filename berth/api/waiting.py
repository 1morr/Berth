"""頁首的件數（M5.5 票 07）：待處理、新番兩格與它們的區塊分頁上的數字。

只有管理員進得來（`api/gate.py` 的 `ADMIN_PREFIXES`）：數的是審核、Issue、RSS 那幾頁，那幾頁只有
管理員看得到。
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from berth.api.deps import SessionDep
from berth.services.waiting import waiting_counts

router = APIRouter(prefix="/waiting", tags=["waiting"])


class WaitingCountsOut(BaseModel):
    """三格加起來就是 Discord「有 N 件等你處理」的 N。"""

    model_config = ConfigDict(from_attributes=True)

    #: 審核佇列（`/review`）。
    review: int
    #: 開著的 Issue（`/issues`）。
    issue: int
    #: 待綁定的 RSS Series（`/rss` 的待綁定段）。
    rss: int


@router.get("")
async def read_waiting(session: SessionDep) -> WaitingCountsOut:
    return WaitingCountsOut.model_validate(await waiting_counts(session))
