"""設定精靈的端點（plan §6 setup 群組、§9.3）。

`setup/*` **只在 setup 未完成時匿名開放**；完成之後要登入（plan §6）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from berth.api.deps import ClientFactoryDep, SessionDep, SetupProbesDep
from berth.domain import DetectionReason, ServiceKind, ServiceOrigin, StepStatus
from berth.services.jellyfin import (
    add_berth_path,
    bootstrap_jellyfin,
    connect_jellyfin,
    install_merge_versions,
    read_jellyfin_status,
)
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
    #: 連線問題解掉了沒。沒解掉就要使用者補位址或憑證。
    resolved: bool


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


# --- 第 3 步：Jellyfin（plan §9.4、§9.5）---


class StepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step: str
    status: StepStatus
    #: 實測值：版本號、建了哪幾個媒體庫、任務 id。UI 直接顯示，不翻譯。
    detail: str
    #: 失敗時 Jellyfin 回的原文（英文）。
    error: str


class LibraryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    collection_type: str
    locations: list[str]
    metadata_fetchers: list[str]
    uses_tvdb: bool
    berth_path: str
    has_berth_path: bool


class JellyfinSetupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    origin: ServiceOrigin
    base_url: str
    api_key_present: bool
    steps: list[StepOut]
    libraries: list[LibraryOut]
    merge_versions_installed: bool
    merge_movies_task_id: str
    merge_episodes_task_id: str


class JellyfinConnectIn(BaseModel):
    """既有 Jellyfin 的管理員帳密。只用來換 API key，不存下來。"""

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LibraryPathIn(BaseModel):
    #: 要加 Berth 路徑的媒體庫名稱。路徑由伺服器算，UI 在按之前就顯示同一個值。
    library: str = Field(min_length=1)


@router.get("/jellyfin")
async def get_jellyfin(session: SessionDep) -> JellyfinSetupOut:
    """不連線，只回存下來的狀態。bootstrap 進行中前端輪詢這一支看序列走到哪裡。"""
    return JellyfinSetupOut.model_validate(await read_jellyfin_status(session))


@router.post("/jellyfin/bootstrap")
async def post_jellyfin_bootstrap(
    session: SessionDep, factory: ClientFactoryDep
) -> JellyfinSetupOut:
    """套件內路徑：跑完 plan §9.4 的九步。重按只補做還沒做的那幾步。"""
    return JellyfinSetupOut.model_validate(await bootstrap_jellyfin(session, factory))


@router.post("/jellyfin/connect")
async def post_jellyfin_connect(
    session: SessionDep, factory: ClientFactoryDep, body: JellyfinConnectIn
) -> JellyfinSetupOut:
    """既有路徑：登入、建立 API key、列出媒體庫（plan §9.5）。"""
    return JellyfinSetupOut.model_validate(
        await connect_jellyfin(session, factory, username=body.username, password=body.password)
    )


@router.post("/jellyfin/libraries/paths")
async def post_jellyfin_library_path(
    session: SessionDep, factory: ClientFactoryDep, body: LibraryPathIn
) -> JellyfinSetupOut:
    """既有路徑的「加入 Berth 路徑」。舊路徑原地不動（brief §16.4）。

    失敗不是 4xx/5xx，而是回一條 `failed` 的 `libraries` 步驟——畫面靠它顯示原文與手動步驟。
    """
    return JellyfinSetupOut.model_validate(
        await add_berth_path(session, factory, library_name=body.library)
    )


@router.post("/jellyfin/plugin")
async def post_jellyfin_plugin(session: SessionDep, factory: ClientFactoryDep) -> JellyfinSetupOut:
    """既有路徑的「安裝 MergeVersions」。**會重啟 Jellyfin**，所以 UI 要二次確認。"""
    return JellyfinSetupOut.model_validate(await install_merge_versions(session, factory))
