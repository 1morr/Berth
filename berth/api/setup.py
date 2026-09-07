"""設定精靈的端點（plan §6 setup 群組、§9.3）。

`setup/*` **只在 setup 未完成時匿名開放**；完成之後要登入（plan §6）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from berth.api.deps import ClientFactoryDep, SessionDep, SetupProbesDep
from berth.domain import DetectionReason, ServiceKind, ServiceOrigin
from berth.services.setup import (
    ServiceConnection,
    SetupStatus,
    connect_service,
    create_admin,
    detect_services,
    read_status,
)


async def require_setup_open(session: SessionDep) -> None:
    """setup 未完成時整個群組匿名開放；完成之後要登入（plan §6）。

    登入本身在票 07。在它落地之前「要登入」等於「還沒有人登入得了」，所以完成後一律 401；
    票 07 只需要把這裡換成真的 session 檢查。
    """
    if (await read_status(session)).completed:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "setup is complete; sign in to change these settings",
        )


router = APIRouter(prefix="/setup", tags=["setup"], dependencies=[Depends(require_setup_open)])


class ServiceDetectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: ServiceKind
    origin: ServiceOrigin
    reason: DetectionReason
    #: 實測值（版本號、索引站數量）。UI 直接顯示，不翻譯。
    detail: str
    base_url: str
    #: 這個判定來自使用者填的連線表單，不是探測 compose 主機名的結果。
    configured: bool


class SetupStatusOut(BaseModel):
    #: 直接從 `SetupStatus` 這個 dataclass 讀，欄位增減不必兩處同步。
    model_config = ConfigDict(from_attributes=True)

    completed: bool
    current_step: int
    admin_created: bool
    admin_username: str
    apply_to_services: bool
    services: list[ServiceDetectionOut]
    waited_seconds: int
    window_seconds: int


class AdminIn(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    #: 「同一組帳密也套用到 qBittorrent 與 Prowlarr 介面」，預設勾（plan §9.3 第 1 步）。
    apply_to_services: bool = True


class ConnectIn(BaseModel):
    """既有服務的連線表單。每個服務只用得到其中幾個欄位。"""

    base_url: str = Field(min_length=1)
    #: Prowlarr / Torznab 的 key；Prowlarr 讀不到掛載時使用者手動貼在這裡。
    api_key: str = ""
    #: qBittorrent 的 WebUI 帳密。留空代表那台是免密的。
    username: str = ""
    password: str = ""


class DetectIn(BaseModel):
    #: 使用者按「重試」，重新開始 2 分鐘的輪詢窗口。
    restart: bool = False


@router.get("/status")
async def get_status(session: SessionDep) -> SetupStatusOut:
    return _out(await read_status(session))


@router.post("/admin")
async def post_admin(session: SessionDep, body: AdminIn) -> SetupStatusOut:
    try:
        result = await create_admin(
            session,
            username=body.username,
            password=body.password,
            apply_to_services=body.apply_to_services,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return _out(result)


@router.post("/detect")
async def post_detect(
    session: SessionDep, probes: SetupProbesDep, body: DetectIn | None = None
) -> SetupStatusOut:
    return _out(await detect_services(session, probes, restart=(body or DetectIn()).restart))


@router.post("/services/{kind}")
async def post_service(
    session: SessionDep,
    factory: ClientFactoryDep,
    kind: ServiceKind,
    body: ConnectIn,
) -> SetupStatusOut:
    """既有服務的「測試連線」：存下連線資訊再連一次（plan §9.3 第 2 步）。"""
    return _out(
        await connect_service(
            session,
            kind,
            ServiceConnection(
                base_url=body.base_url.rstrip("/"),
                api_key=body.api_key.strip(),
                username=body.username,
                password=body.password,
            ),
            factory,
        )
    )


def _out(result: SetupStatus) -> SetupStatusOut:
    return SetupStatusOut.model_validate(result)
