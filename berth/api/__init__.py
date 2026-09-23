"""FastAPI routers。只呼叫 `services`（plan §1.3）。

門禁是 middleware（`api/gate.py`），不是逐個 router 的相依：新增端點預設就在門後。
"""

from fastapi import APIRouter

from berth.api import (
    auth,
    discover,
    events,
    files,
    health,
    inventory,
    issues,
    jellyfin,
    jobs,
    media,
    plans,
    review,
    routes,
    search,
    settings,
    setup,
)

#: 掛在 `/api` 之下（plan §6）。
router = APIRouter()
router.include_router(auth.router)
router.include_router(discover.router)
router.include_router(events.router)
router.include_router(files.router)
router.include_router(health.router)
router.include_router(inventory.router)
router.include_router(issues.router)
router.include_router(jellyfin.router)
router.include_router(jobs.router)
router.include_router(media.router)
router.include_router(plans.router)
router.include_router(review.router)
router.include_router(routes.router)
router.include_router(search.router)
router.include_router(settings.router)
router.include_router(setup.router)

__all__ = ["router"]
