"""FastAPI routers。只呼叫 `services`（plan §1.3）。"""

from fastapi import APIRouter

from berth.api import health

#: 掛在 `/api` 之下（plan §6）。
router = APIRouter()
router.include_router(health.router)

__all__ = ["router"]
