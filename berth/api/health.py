"""健康端點（plan §6 health 群組、票 10）。

兩支：匿名的總體狀態，與登入後的逐項明細。**匿名那一支只回一個字**——compose 的健康檢查
與前端的路由守衛靠它，而沒登入的人不該知道內部主機名、版本與掛載長什麼樣（票 07 同一個
理由）。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from berth.api.deps import ClientFactoryDep, SessionDep
from berth.api.schemas import HealthDetailOut, health_detail
from berth.config import VERSION
from berth.domain import BudgetUse
from berth.services.health import (
    BudgetView,
    Status,
    check_health,
    overall_status,
    read_budget,
    read_health,
)
from berth.services.setup import is_setup_complete

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: Status
    version: str
    #: 精靈跑完了沒。前端的路由守衛靠它決定要畫精靈還是登入頁——那個決定必須在還沒有人
    #: 登入得了的時候就做得出來，所以它掛在這支匿名端點上，不在 `setup/status`（票 07）。
    setup_completed: bool


@router.get("/health")
async def read_root_health(session: SessionDep) -> Health:
    return Health(
        status=await overall_status(session),
        version=VERSION,
        setup_completed=await is_setup_complete(session),
    )


@router.get("/health/detail")
async def read_detail(session: SessionDep) -> HealthDetailOut:
    """上一輪的結果，逐服務與逐 Route。**不連任何服務**（`POST /health/check` 才連）。"""
    return health_detail(await read_health(session))


@router.post("/health/check")
async def post_check(session: SessionDep, factory: ClientFactoryDep) -> HealthDetailOut:
    """立刻重跑四項檢查（plan §3.2 的「+ 手動」）。迴圈跑的是同一支命令。"""
    return health_detail(await check_health(session, factory))


class UseCountOut(BaseModel):
    use: BudgetUse
    count: int


class DeferralOut(BaseModel):
    """被預算擋下、還沒過得去的一種工作。"""

    use: BudgetUse
    #: 擋下了幾個請求。
    refused: int
    #: 第一次被擋的時刻。
    since: datetime
    #: 放得下的時刻；`null` 是一次要的比整份預算還多，永遠放不下。
    until: datetime | None


class SiteBudgetOut(BaseModel):
    site: str
    #: 視窗裡的請求數。
    used: int
    by_use: list[UseCountOut]
    #: 最早那一個請求滑出視窗的時刻。
    frees_at: datetime | None
    deferred: list[DeferralOut]


class BudgetOut(BaseModel):
    """一個站一份請求預算（M3 票 20、plan §3.2）。記在程序的記憶體裡，重啟歸零。"""

    #: 每一站在一個視窗裡最多幾個請求。
    limit: int
    window_seconds: int
    #: 視窗裡問過、或有工作被擋著的站。
    sites: list[SiteBudgetOut]


@router.get("/health/budget")
async def read_request_budget(factory: ClientFactoryDep) -> BudgetOut:
    """輪詢、補漏、搜尋共用的那一份。**不連任何服務**。"""
    return _budget(read_budget(factory))


def _budget(view: BudgetView) -> BudgetOut:
    return BudgetOut(
        limit=view.limit,
        window_seconds=int(view.window.total_seconds()),
        sites=[
            SiteBudgetOut(
                site=row.site,
                used=row.used,
                by_use=[UseCountOut(use=use, count=count) for use, count in row.by_use],
                frees_at=row.frees_at,
                deferred=[
                    DeferralOut(use=one.use, refused=one.refused, since=one.since, until=one.until)
                    for one in row.deferred
                ],
            )
            for row in view.sites
        ],
    )
