"""設定精靈的端點（plan §6 setup 群組、§9.3）。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from berth.api.deps import ClientFactoryDep, SessionDep, SetupProbesDep
from berth.domain import (
    DetectionReason,
    IndexerKind,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
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
    install_merge_versions,
    read_jellyfin_status,
)
from berth.services.qbittorrent import apply_qbittorrent, read_qbittorrent_diff
from berth.services.setup import (
    ServiceConnection,
    SetupStatus,
    connect_service,
    create_admin,
    detect_services,
    read_status,
)
from berth.services.tmdb import read_tmdb_status, skip_tmdb, verify_tmdb

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


# --- 第 4 步：qBittorrent（plan §9.3 第 4 步、§8.1）---


class PreferenceDiffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    #: `app/setPreferences` 的鍵名。畫面顯示的與送出去的是同一個字串。
    key: str
    current: str
    recommended: str
    differs: bool


class QbittorrentSetupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    origin: ServiceOrigin
    base_url: str
    version: str
    webapi_version: str
    supported: bool
    blocked: bool
    reachable: bool
    diffs: list[PreferenceDiffOut]
    steps: list[StepOut]
    temp_path_warning: bool
    sets_password: bool
    error: str


@router.get("/qbittorrent/diff")
async def get_qbittorrent_diff(
    session: SessionDep, factory: ClientFactoryDep
) -> QbittorrentSetupOut:
    """現值與建議值的逐鍵差異。連得到才有內容，連不到就是 `reachable=false` 加原文。"""
    return QbittorrentSetupOut.model_validate(await read_qbittorrent_diff(session, factory))


@router.post("/qbittorrent/apply")
async def post_qbittorrent_apply(
    session: SessionDep, factory: ClientFactoryDep
) -> QbittorrentSetupOut:
    """套用建議偏好。只寫有差異的鍵；勾了「同一組帳密」才順便設 WebUI 密碼。"""
    return QbittorrentSetupOut.model_validate(await apply_qbittorrent(session, factory))


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
    #: 第 5、6 步可跳過，也可以再取消跳過（plan §9.3）。
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


# --- 第 6 步：TMDB（plan §9.3 第 6 步、§8.3）---


class TmdbSetupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    using_project_credential: bool
    steps: list[StepOut]
    skipped: bool


class TmdbTestIn(BaseModel):
    #: 空字串代表用回內建的專案級憑證。
    api_key: str = ""


@router.get("/tmdb")
async def get_tmdb(session: SessionDep) -> TmdbSetupOut:
    return TmdbSetupOut.model_validate(await read_tmdb_status(session))


@router.post("/tmdb/test")
async def post_tmdb_test(
    session: SessionDep, factory: ClientFactoryDep, body: TmdbTestIn
) -> TmdbSetupOut:
    """先存再測。`configuration` 回得出來就證明這把憑證有效。"""
    return TmdbSetupOut.model_validate(await verify_tmdb(session, factory, api_key=body.api_key))


@router.post("/tmdb/skip")
async def post_tmdb_skip(session: SessionDep, body: SkipIn) -> TmdbSetupOut:
    return TmdbSetupOut.model_validate(await skip_tmdb(session, skipped=body.skipped))
