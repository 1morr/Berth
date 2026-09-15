"""服務設定的端點（plan §6 settings 群組、票 10）。

這一頁是**維運動作**，不是連線表單：位址與憑證仍然在精靈裡改（精靈跑完之後它就是設定
入口，plan §6），這裡只有三件事——

- 「測試連線」：立刻重測一個服務，結果就是健康頁上那一列。
- 「還原建議設定」：qBittorrent 的建議偏好被改掉時把它們寫回去（brief §16.3）。
- Jellyfin 的**對外網址**（票 13）：瀏覽器開深連結用的那一個，不是 Berth 自己連過去的那一條。
  它不是連線資訊——精靈用不到它，填錯也不會讓任何服務斷線——所以住在這裡而不是精靈。

只有管理員進得來，規則在門禁（`api/gate.py`）而不是這裡的相依：新增端點什麼都不做就
已經在同一道門後面。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from berth.api.deps import ClientFactoryDep, SessionDep
from berth.api.schemas import HealthDetailOut, JellyfinWebOut, QbittorrentOut, health_detail
from berth.domain import ServiceKind
from berth.services.deeplink import PublicUrlRejectedError, jellyfin_web, set_public_url
from berth.services.health import check_service, read_health
from berth.services.qbittorrent import apply_qbittorrent, read_qbittorrent_diff

router = APIRouter(prefix="/settings", tags=["settings"])


class JellyfinAddressIn(BaseModel):
    #: `https://jellyfin.example.com`。空白就是清掉，回到推導（`services/deeplink.py`）。
    public_url: str = ""


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


@router.get("/jellyfin")
async def get_jellyfin(session: SessionDep) -> JellyfinWebOut:
    """對外網址，與它沒填時推導出來的樣子——欄位旁邊要說得出「空著的話會開在哪」。"""
    return JellyfinWebOut.model_validate(await jellyfin_web(session))


@router.post("/jellyfin")
async def post_jellyfin(session: SessionDep, body: JellyfinAddressIn) -> JellyfinWebOut:
    try:
        web = await set_public_url(session, body.public_url)
    except PublicUrlRejectedError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return JellyfinWebOut.model_validate(web)
