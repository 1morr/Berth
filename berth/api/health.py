"""健康端點（plan §6）。可匿名呼叫，只回總體狀態。

逐項檢查（服務連線、Route 硬鏈接）與 `/health/detail` 在票 10。
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from berth.config import VERSION

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    version: str


@router.get("/health")
async def read_health() -> Health:
    return Health(status="ok", version=VERSION)
