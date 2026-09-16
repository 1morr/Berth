"""設定精靈的端點（plan §6 setup 群組、§9.3）。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from berth.api.deps import ClientFactoryDep, SessionDep, SetupProbesDep
from berth.api.routes import route_refusal
from berth.api.schemas import QbittorrentOut, RouteOut, StepOut
from berth.domain import (
    DetectionReason,
    IndexerKind,
    Profile,
    ServiceKind,
    ServiceOrigin,
)
from berth.services.indexer import (
    apply_default_indexers,
    connect_indexer,
    read_indexer_status,
    skip_indexers,
)
from berth.services.jellyfin import (
    add_berth_path,
    bootstrap_jellyfin,
    connect_jellyfin,
    read_jellyfin_status,
)
from berth.services.qbittorrent import apply_qbittorrent, read_qbittorrent_diff
from berth.services.routes import (
    RouteRejectedError,
    RouteSelection,
    build_routes,
    delete_route,
    read_route_status,
)
from berth.services.setup import (
    ServiceConnection,
    SetupStatus,
    complete_setup,
    connect_service,
    create_admin,
    detect_services,
    read_status,
)
from berth.services.tmdb import read_tmdb_status, verify_tmdb

#: 誰進得來這一組由門禁決定（`api/gate.py`）：精靈跑完之前匿名開放，跑完之後只有管理員。
#: 規則放在那裡而不是這裡的相依，是為了「忘記掛相依」不會變成一個沒人守的洞。
router = APIRouter(prefix="/setup", tags=["setup"])


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
    #: 這台 Jellyfin 上一次報的版本號。還沒問過就是空字串。
    version: str
    #: 版本是不是 12.0 以上（brief §16.4）。還沒問過時是 `true`。
    version_supported: bool


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
    """套件內路徑：跑完 plan §9.4 的七步。重按只補做還沒做的那幾步。"""
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


# --- 第 4 步：qBittorrent（plan §9.3 第 4 步、§8.1）---


@router.get("/qbittorrent/diff")
async def get_qbittorrent_diff(session: SessionDep, factory: ClientFactoryDep) -> QbittorrentOut:
    """現值與建議值的逐鍵差異。連得到才有內容，連不到就是 `reachable=false` 加原文。"""
    return QbittorrentOut.model_validate(await read_qbittorrent_diff(session, factory))


@router.post("/qbittorrent/apply")
async def post_qbittorrent_apply(session: SessionDep, factory: ClientFactoryDep) -> QbittorrentOut:
    """套用建議偏好。只寫有差異的鍵；勾了「同一組帳密」才順便設 WebUI 密碼。"""
    return QbittorrentOut.model_validate(await apply_qbittorrent(session, factory))


# --- 第 5 步：索引站（plan §9.3 第 5 步、§8.4）---


class IndexerOptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    definition_name: str
    name: str
    privacy: str
    present: bool


class IndexerSetupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    origin: ServiceOrigin
    kind: IndexerKind
    base_url: str
    api_key_present: bool
    reachable: bool
    options: list[IndexerOptionOut]
    steps: list[StepOut]
    skipped: bool
    sets_password: bool
    error: str


class IndexerApplyIn(BaseModel):
    #: 勾起來的站，值是 Prowlarr 的 `definitionName`。空清單代表一個都沒勾。
    indexers: list[str] = []


class IndexerConnectIn(BaseModel):
    """既有路徑：Prowlarr 位址 + key，或任意 Torznab 端點 + key。"""

    kind: IndexerKind
    base_url: str = Field(min_length=1)
    api_key: str = ""


class SkipIn(BaseModel):
    #: 第 5 步可跳過，也可以再取消跳過（plan §9.3）。第 6 步不行（票 02b）。
    skipped: bool = True


@router.get("/indexers")
async def get_indexers(session: SessionDep, factory: ClientFactoryDep) -> IndexerSetupOut:
    return IndexerSetupOut.model_validate(await read_indexer_status(session, factory))


@router.post("/indexers/apply")
async def post_indexers_apply(
    session: SessionDep, factory: ClientFactoryDep, body: IndexerApplyIn
) -> IndexerSetupOut:
    """套件內路徑：勾起來的站逐個加進 Prowlarr，逐站回報成敗。

    對既有的索引站回 422：那是使用者自己的服務，Berth 只做檢查（brief §16.4）。
    """
    try:
        result = await apply_default_indexers(session, factory, body.indexers)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return IndexerSetupOut.model_validate(result)


@router.post("/indexers/connect")
async def post_indexers_connect(
    session: SessionDep, factory: ClientFactoryDep, body: IndexerConnectIn
) -> IndexerSetupOut:
    """既有路徑的「測試」。測不過也存，使用者才能改一個欄位再按一次。"""
    return IndexerSetupOut.model_validate(
        await connect_indexer(
            session,
            factory,
            kind=body.kind,
            base_url=body.base_url.rstrip("/"),
            api_key=body.api_key.strip(),
        )
    )


@router.post("/indexers/skip")
async def post_indexers_skip(
    session: SessionDep, factory: ClientFactoryDep, body: SkipIn
) -> IndexerSetupOut:
    return IndexerSetupOut.model_validate(
        await skip_indexers(session, factory, skipped=body.skipped)
    )


# --- 第 6 步：TMDB（plan §9.3 第 6 步、§8.3）。憑證使用者自備、必填（票 02b）---


class TmdbSetupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    api_key_present: bool
    verified: bool
    steps: list[StepOut]


class TmdbTestIn(BaseModel):
    #: 使用者自己申請的 v3 API key 或 v4 read access token（票 02b）。空字串就是一條紅線。
    api_key: str


@router.get("/tmdb")
async def get_tmdb(session: SessionDep) -> TmdbSetupOut:
    return TmdbSetupOut.model_validate(await read_tmdb_status(session))


@router.post("/tmdb/test")
async def post_tmdb_test(
    session: SessionDep, factory: ClientFactoryDep, body: TmdbTestIn
) -> TmdbSetupOut:
    """先存再測。`configuration` 回得出來就證明這把憑證有效。

    **沒有 `/tmdb/skip`**：這一步是閘門，測不過就走不到第 7 步（票 02b）。
    """
    return TmdbSetupOut.model_validate(await verify_tmdb(session, factory, api_key=body.api_key))


# --- 第 7–8 步：媒體庫 → Route 與完成（plan §9.3 第 7–8 步、§9.5）---


class LibraryChoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    collection_type: str
    locations: list[str]
    berth_path: str
    has_berth_path: bool
    uses_tvdb: bool
    #: Berth 建得了 Route 的類型（movies / tvshows）。
    supported: bool
    #: 已經有 Route 了：精靈只新增，這個媒體庫在勾選表上鎖住（票 14）。
    has_route: bool
    target_path: str
    profile: Profile


class RouteSetupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    origin: ServiceOrigin
    library_root: str
    complete_root: str
    libraries: list[LibraryChoiceOut]
    routes: list[RouteOut]
    #: 至少一個 Route，而且每個都綠燈。完成鍵的前提。
    ready: bool
    completed: bool


class RouteSelectionIn(BaseModel):
    """既有 Jellyfin：勾起來的一個媒體庫與它的寫入目標。"""

    library: str = Field(min_length=1)
    #: 必須是那個媒體庫回報的路徑之一——路徑用選的，不用打的（brief §4.1）。
    target_path: str = Field(min_length=1)
    profile: Profile = Profile.STANDARD


class RoutesIn(BaseModel):
    #: 套件內 Jellyfin 忽略這個欄位：三個 Route 由它自己的三個媒體庫導出（plan §9.3 第 7 步）。
    selections: list[RouteSelectionIn] = []


@router.get("/routes")
async def get_routes(session: SessionDep) -> RouteSetupOut:
    """不連線，只回媒體庫清單與已經建好的 Route（含上一輪的檢查結果）。"""
    return RouteSetupOut.model_validate(await read_route_status(session))


@router.post("/routes")
async def post_routes(
    session: SessionDep, factory: ClientFactoryDep, body: RoutesIn | None = None
) -> RouteSetupOut:
    """建立 Route，並立刻建 category 與跑三項檢查（plan §9.5）。

    檢查失敗**不是** 4xx：它是這一步的結果，逐項回在 `routes[].checks` 裡，畫面靠它顯示
    原文與該補哪個掛載。4xx 只留給「這個選擇本身無效」（不存在的媒體庫、不是它的路徑）。
    """
    try:
        result = await build_routes(
            session,
            factory,
            [
                RouteSelection(
                    library=row.library, target_path=row.target_path, profile=row.profile
                )
                for row in (body or RoutesIn()).selections
            ],
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return RouteSetupOut.model_validate(result)


@router.delete("/routes/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_setup_route(session: SessionDep, route_id: int) -> None:
    """第 7 步每條 Route 底下的「刪除」（票 14a）。

    與 Route 設定頁同一個命令、同一種拒絕（404 `route_missing`、409 `route_in_use`），只是跟著
    `setup/*` 的門禁：精靈跑完之前還沒有人登入得了，而 `/routes/*` 永遠只有管理員。
    """
    try:
        await delete_route(session, route_id)
    except RouteRejectedError as refusal:
        raise route_refusal(refusal) from refusal


@router.post("/complete")
async def post_complete(session: SessionDep) -> SetupStatusOut:
    """第 8 步：寫下 `settings.setup.completed`。**寫完這一支就要登入才進得來**（票 07）。"""
    try:
        return _out(await complete_setup(session))
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
