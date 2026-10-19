"""健康端點（plan §6 health 群組、票 10）。

兩支：匿名的總體狀態，與登入後的逐項明細。**匿名那一支只回總體判定、版本與精靈的兩個旗標**
——compose 的健康檢查與前端的路由守衛靠它，而沒登入的人不該知道內部主機名與掛載長什麼樣
（票 07 同一個理由）。版本不算內部細節：設定頁底部照這一支印出來（票 106）。
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from berth.api.deps import ClientFactoryDep, SessionDep
from berth.api.schemas import HealthDetailOut, health_detail
from berth.config import VERSION
from berth.services.health import (
    Status,
    check_health,
    overall_status,
    read_health,
)
from berth.services.setup import is_owner_established, is_setup_complete

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: Status
    version: str
    #: 精靈跑完了沒。前端的路由守衛靠它決定要畫精靈還是登入頁——那個決定必須在還沒有人
    #: 登入得了的時候就做得出來，所以它掛在這支匿名端點上，不在 `setup/status`（票 07）。
    setup_completed: bool
    #: 精靈第 1 步的擁有者成立了沒（M4 票 06）。成立之後精靈要登入，前端守衛靠它在精靈跑完之前
    #: 就把沒有 session 的人送去登入頁，而不是讓精靈的每一支都回 401。
    owner_established: bool


@router.get("/health")
async def read_root_health(session: SessionDep) -> Health:
    return Health(
        status=await overall_status(session),
        version=VERSION,
        setup_completed=await is_setup_complete(session),
        owner_established=await is_owner_established(session),
    )


@router.get("/health/detail")
async def read_detail(session: SessionDep) -> HealthDetailOut:
    """上一輪的結果，逐服務與逐 Route。**不連任何服務**（`POST /health/check` 才連）。"""
    return health_detail(await read_health(session))


@router.post("/health/check")
async def post_check(session: SessionDep, factory: ClientFactoryDep) -> HealthDetailOut:
    """立刻重跑四項檢查（plan §3.2 的「+ 手動」）。迴圈跑的是同一支命令。"""
    return health_detail(await check_health(session, factory))
