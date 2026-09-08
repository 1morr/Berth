"""健康端點（plan §6）。可匿名呼叫，只回總體狀態。

逐項檢查（服務連線、Route 硬鏈接）與 `/health/detail` 在票 10。
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from berth.api.deps import SessionDep
from berth.config import VERSION
from berth.services.setup import is_setup_complete

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    #: 精靈跑完了沒。前端的路由守衛靠它決定要畫精靈還是登入頁——那個決定必須在還沒有人
    #: 登入得了的時候就做得出來，所以它掛在這支匿名端點上，不在 `setup/status`（票 07）。
    setup_completed: bool


@router.get("/health")
async def read_health(session: SessionDep) -> Health:
    return Health(status="ok", version=VERSION, setup_completed=await is_setup_complete(session))
