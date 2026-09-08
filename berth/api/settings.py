"""服務設定的端點（plan §6 settings 群組、票 10）。

這一頁是**維運動作**，不是連線表單：位址與憑證仍然在精靈裡改（精靈跑完之後它就是設定
入口，plan §6），這裡只有兩件事——

- 「測試連線」：立刻重測一個服務，結果就是健康頁上那一列。
- 「還原建議設定」：qBittorrent 的建議偏好被改掉時把它們寫回去（brief §16.3）。

只有管理員進得來，規則在門禁（`api/gate.py`）而不是這裡的相依：新增端點什麼都不做就
已經在同一道門後面。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from berth.api.deps import ClientFactoryDep, SessionDep
from berth.api.schemas import HealthDetailOut, QbittorrentOut, health_detail
from berth.domain import ServiceKind
from berth.services.health import check_service, read_health
from berth.services.qbittorrent import apply_qbittorrent, read_qbittorrent_diff

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/services")
async def get_services(session: SessionDep) -> HealthDetailOut:
    """三個服務現在的樣子。與健康頁同一份形狀——同一件事不該有兩種說法。"""
    return health_detail(await read_health(session))


@router.post("/services/{kind}/test")
async def post_service_test(
    session: SessionDep, factory: ClientFactoryDep, kind: str
) -> HealthDetailOut:
    """「測試連線」：只重測這一個服務，其餘三項的結果留著（票 10）。"""
    try:
        service = ServiceKind(kind)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"{kind!r} is not a service Berth knows"
        ) from exc
    return health_detail(await check_service(session, factory, service))


@router.get("/qbittorrent/diff")
async def get_qbittorrent_diff(session: SessionDep, factory: ClientFactoryDep) -> QbittorrentOut:
    """現值與建議值的逐鍵差異——與精靈第 4 步問的是同一個問題。"""
    return QbittorrentOut.model_validate(await read_qbittorrent_diff(session, factory))


@router.post("/qbittorrent/apply")
async def post_qbittorrent_apply(session: SessionDep, factory: ClientFactoryDep) -> QbittorrentOut:
    """「還原建議設定」。只寫有差異的鍵，跑的是精靈第 4 步的同一支命令。"""
    return QbittorrentOut.model_validate(await apply_qbittorrent(session, factory))
