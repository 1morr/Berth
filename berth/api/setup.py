"""設定精靈的端點（plan §6 setup 群組、§9.3）。"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field

from berth.api.auth import issue_cookie
from berth.api.deps import BundledServicesDep, ClientFactoryDep, ConfigDep, SessionDep
from berth.api.errors import refusal_responses
from berth.api.routes import route_refusal, route_responses
from berth.api.schemas import InterfaceLoginIn, QbittorrentOut, RouteOut, StepOut
from berth.config import Config
from berth.domain import (
    BerthPathFailure,
    BundledLibraryRefusal,
    ChoiceRefusal,
    CollectionType,
    ConnectionReason,
    ConnectionState,
    IndexerKind,
    InterfaceLoginRefusal,
    OwnerRefusal,
    RouteRefusal,
    ServiceKind,
    ServiceOrigin,
    SiteFailure,
    StepFailure,
    StepStatus,
)
from berth.services.clients import bundled_targets
from berth.services.indexer import (
    IndexerSetupStatus,
    apply_default_indexers,
    connect_indexer,
    read_indexer_status,
    remove_indexer,
    search_indexers,
    skip_indexers,
    verify_sites,
)
from berth.services.indexer import (
    set_interface_login as set_prowlarr_login,
)
from berth.services.jellyfin import (
    DEFAULT_STARTUP,
    BundledLibraryRejectedError,
    InterfaceLoginRejectedError,
    JellyfinStartup,
    add_berth_paths,
    bootstrap_jellyfin,
    connect_jellyfin,
    read_jellyfin_status,
    save_bundled_libraries,
)
from berth.services.qbittorrent import apply_qbittorrent, read_qbittorrent_diff
from berth.services.qbittorrent import set_interface_login as set_qbittorrent_login
from berth.services.routes import (
    RouteRejectedError,
    RouteSelection,
    build_routes,
    delete_route,
    read_route_status,
    reread_libraries,
)
from berth.services.setup import (
    ChoiceLockedError,
    OwnerRejectedError,
    ServiceConnection,
    SetupStatus,
    choose_service,
    claim_owner,
    complete_setup,
    read_status,
    retest_service,
)
from berth.services.tmdb import read_tmdb_status, verify_tmdb

#: 誰進得來這一組由門禁決定（`api/gate.py`）：擁有者成立之前只開 Jellyfin 的選擇、測試與成立擁有者，
#: 之後只有管理員（M4 票 06）。
#: 規則放在那裡而不是這裡的相依，是為了「忘記掛相依」不會變成一個沒人守的洞。
#: 精靈跑完之後設定頁呼叫的也是這一組（票 06i）：命令冪等，一份命令、一份端點。
router = APIRouter(prefix="/setup", tags=["setup"])

#: Jellyfin 的語言代碼：兩三碼的語言，可帶地區或文字（`zh-TW`、`en`、`zh-Hant`）。
_LANGUAGE = r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$"


class ServiceOut(BaseModel):
    """一個服務的來源選擇與最後一次測試（plan §9.3〈服務頁的共同形狀〉）。"""

    model_config = ConfigDict(from_attributes=True)

    kind: ServiceKind
    origin: ServiceOrigin
    #: Berth 連的那一條：套件內是 compose 主機名，既有是使用者填的。
    base_url: str
    #: 還沒測過是 `null`。
    state: ConnectionState | None
    reason: ConnectionReason | None
    #: 實測值（版本號、索引站數量）。UI 直接顯示，不翻譯。
    detail: str
    #: 沒連上時服務回的原文（英文），收進「技術細節」（M4 票 21）。
    error: str
    #: 這個位址上連續幾次帳密不被接受（qBittorrent 預設 5 次封 IP，brief §20.2）。
    auth_failures: int
    #: 套件內那一台還在啟動時，這一輪已經等了幾秒。
    waited_seconds: int


class SetupStatusOut(BaseModel):
    #: 直接從 `SetupStatus` 這個 dataclass 讀，欄位增減不必兩處同步。
    model_config = ConfigDict(from_attributes=True)

    completed: bool
    current_step: int
    #: 擁有者的 Jellyfin 名字；空字串就是還沒有（頁 1）。
    owner: str
    #: 頁 1 是登入（那一台已經有管理員）而不是建立。
    owner_signs_in: bool
    #: 選過的服務。沒選的不在裡面。
    services: list[ServiceOut]
    #: 套件內那一台還在啟動時的輪詢上限。
    window_seconds: int
    #: 選「套件內」會連的三個 compose 位址（`bundled_targets`）。服務頁照它說「套件內會連哪裡」，
    #: 不在前端寫死 port（票 06h）。
    bundled_targets: dict[ServiceKind, str]


class OwnerIn(BaseModel):
    """擁有者的 Jellyfin 帳密：套件內拿去建管理員，既有拿去登入。只交給 Jellyfin，不存下來。

    帳密不加約束，理由同 `LoginIn`：空的與錯的一律由 services 拒絕成 `invalid_credentials`。
    其餘四欄只用在還沒初始化的那一台（`jellyfin.JellyfinStartup`，M4 票 18）：既有的在畫面上問，
    套件內的由前端帶 UI 語言、不開遠端存取。
    """

    username: str = ""
    password: str = ""
    #: Jellyfin 的語言代碼（`zh-TW`、`en-US`、`ja`）：`UICulture`。
    ui_culture: str = Field(default=DEFAULT_STARTUP.ui_culture, pattern=_LANGUAGE)
    #: `PreferredMetadataLanguage`（`zh-TW`、`en`）。
    metadata_language: str = Field(default=DEFAULT_STARTUP.metadata_language, pattern=_LANGUAGE)
    #: `MetadataCountryCode`，ISO 3166 兩碼。
    metadata_country: str = Field(default=DEFAULT_STARTUP.metadata_country, pattern=r"^[A-Z]{2}$")
    remote_access: bool = DEFAULT_STARTUP.remote_access


#: 一種理由一個狀態碼（`refusal_responses` 由它導出文件）。帳密不對與登入同一個 401；不是管理員
#: 是 403；還沒找到 Jellyfin 與擁有者已經在是 409（與現在的狀態衝突）；Jellyfin 那一段失敗是 502。
_OWNER_STATUS: dict[OwnerRefusal, int] = {
    OwnerRefusal.JELLYFIN_UNRESOLVED: status.HTTP_409_CONFLICT,
    OwnerRefusal.OWNER_EXISTS: status.HTTP_409_CONFLICT,
    OwnerRefusal.INVALID_CREDENTIALS: status.HTTP_401_UNAUTHORIZED,
    OwnerRefusal.NOT_ADMINISTRATOR: status.HTTP_403_FORBIDDEN,
    OwnerRefusal.JELLYFIN_FAILED: status.HTTP_502_BAD_GATEWAY,
}


class OwnerRefusalOut(BaseModel):
    reason: OwnerRefusal
    #: Jellyfin 那一步的原文（英文）；帳密那兩種是空字串。
    detail: str


def owner_refusal(refusal: OwnerRejectedError) -> HTTPException:
    body = OwnerRefusalOut(reason=refusal.reason, detail=refusal.detail)
    return HTTPException(_OWNER_STATUS[refusal.reason], detail=body.model_dump(mode="json"))


#: 選擇不成立的三種都是擁有者之後的 Jellyfin，都是 409（與它現在的狀態衝突）：改來源、換到另一台、
#: 新位址認不出是哪一台（M4 票 18）。
_CHOICE_STATUS: dict[ChoiceRefusal, int] = dict.fromkeys(ChoiceRefusal, status.HTTP_409_CONFLICT)


class ChoiceRefusalOut(BaseModel):
    reason: ChoiceRefusal
    detail: str


def choice_refusal(refusal: ChoiceLockedError) -> HTTPException:
    body = ChoiceRefusalOut(reason=refusal.reason, detail=refusal.detail)
    return HTTPException(_CHOICE_STATUS[refusal.reason], detail=body.model_dump(mode="json"))


class ChoiceIn(BaseModel):
    """服務頁的二選一。選既有時帶那個服務要的連線資訊，每個服務只用得到其中幾個欄位。"""

    origin: ServiceOrigin
    #: 既有服務的位址。套件內的忽略它：位址是 compose 主機名。
    base_url: str = ""
    #: Prowlarr 的 API key：既有的必填；套件內的只在唯讀掛載讀不到時由使用者貼。
    api_key: str = ""
    #: 既有 qBittorrent 的 WebUI 帳密。留空代表那台是免密的。
    username: str = ""
    password: str = ""


class RetestIn(BaseModel):
    #: 使用者按「重新測試」：2 分鐘的輪詢重新算。前端的自動輪詢不帶。
    restart: bool = False


@router.get("/status")
async def get_status(session: SessionDep, config: ConfigDep) -> SetupStatusOut:
    return _out(await read_status(session), config)


@router.post("/owner", responses=refusal_responses(OwnerRefusalOut, _OWNER_STATUS))
async def post_owner(
    session: SessionDep,
    config: ConfigDep,
    factory: ClientFactoryDep,
    body: OwnerIn,
    response: Response,
) -> SetupStatusOut:
    """第 1 步：成立擁有者並發 session（plan §9.3 第 1 步、M4 票 06）。

    cookie 與 `/auth/login` 發的是同一種。擁有者已經在是 409：這一支不換擁有者（M4 票 18）。
    """
    try:
        claimed = await claim_owner(
            session,
            factory,
            username=body.username,
            password=body.password,
            startup=JellyfinStartup(
                ui_culture=body.ui_culture,
                metadata_language=body.metadata_language,
                metadata_country=body.metadata_country,
                remote_access=body.remote_access,
            ),
        )
    except OwnerRejectedError as refusal:
        raise owner_refusal(refusal) from refusal
    issue_cookie(response, claimed.signed_in.token)
    return _out(claimed.status, config)


@router.post("/services/{kind}", responses=refusal_responses(ChoiceRefusalOut, _CHOICE_STATUS))
async def post_service(
    session: SessionDep,
    config: ConfigDep,
    factory: ClientFactoryDep,
    bundled: BundledServicesDep,
    kind: ServiceKind,
    body: ChoiceIn,
) -> SetupStatusOut:
    """服務頁的二選一：存下來源與連線資訊，然後測一次（plan §9.3〈服務頁的共同形狀〉）。

    擁有者成立之後改 Jellyfin 的來源、或把位址換到另一台 Jellyfin 是 409（擁有者是那一台上的帳號，
    M4 票 18）；既有卻沒給位址是 422。
    """
    try:
        result = await choose_service(
            session,
            factory,
            bundled,
            kind,
            body.origin,
            ServiceConnection(
                base_url=body.base_url.strip().rstrip("/"),
                api_key=body.api_key.strip(),
                username=body.username,
                password=body.password,
            ),
        )
    except ChoiceLockedError as refusal:
        raise choice_refusal(refusal) from refusal
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return _out(result, config)


@router.post("/services/{kind}/test")
async def post_service_test(
    session: SessionDep,
    config: ConfigDep,
    factory: ClientFactoryDep,
    bundled: BundledServicesDep,
    kind: ServiceKind,
    body: RetestIn | None = None,
) -> SetupStatusOut:
    """用存下來的選擇再測一次：出問題那一頁的「重新測試」，與套件內那一台還在啟動時的輪詢。
    還沒選過是 422。"""
    try:
        result = await retest_service(
            session, factory, bundled, kind, restart=(body or RetestIn()).restart
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return _out(result, config)


def _out(result: SetupStatus, config: Config) -> SetupStatusOut:
    return SetupStatusOut.model_validate(
        {**asdict(result), "bundled_targets": bundled_targets(config)}
    )


#: 「沿用 Jellyfin 帳密」沒過的兩種（M4 票 15）：密碼不對是 422（這份輸入不成立），
#: Jellyfin 連不上是 502。
_LOGIN_STATUS: dict[InterfaceLoginRefusal, int] = {
    InterfaceLoginRefusal.OWNER_PASSWORD: status.HTTP_422_UNPROCESSABLE_CONTENT,
    InterfaceLoginRefusal.JELLYFIN_UNREACHABLE: status.HTTP_502_BAD_GATEWAY,
}


class InterfaceLoginRefusalOut(BaseModel):
    reason: InterfaceLoginRefusal
    #: Jellyfin 的原文（英文）；密碼不對是空字串。
    detail: str


def login_refusal(refusal: InterfaceLoginRejectedError) -> HTTPException:
    body = InterfaceLoginRefusalOut(reason=refusal.reason, detail=refusal.detail)
    return HTTPException(_LOGIN_STATUS[refusal.reason], detail=body.model_dump(mode="json"))


_LOGIN_RESPONSES = refusal_responses(InterfaceLoginRefusalOut, _LOGIN_STATUS)


# --- Jellyfin（頁 1 之後的媒體庫與設定頁，plan §9.4、§9.5）---


class LibraryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    collection_type: str
    locations: list[str]
    metadata_fetchers: list[str]
    uses_tvdb: bool
    berth_path: str
    has_berth_path: bool


class BundledLibraryOut(BaseModel):
    """套件內要建的一個媒體庫（票 06f）。"""

    model_config = ConfigDict(from_attributes=True)

    name: str
    collection_type: CollectionType
    folder: str
    #: 已經在 Jellyfin 建好了：精靈裡鎖住，改名與刪除去 Jellyfin。
    built: bool


class BerthPathOut(BaseModel):
    """一個媒體庫加 Berth 路徑的結果。`reason` 給畫面挑句子，`error` 是原文（M4 票 19）。"""

    model_config = ConfigDict(from_attributes=True)

    library: str
    #: 要加的那一條。媒體庫找不到、或一開始就問不到 Jellyfin 時是空字串。
    path: str
    status: StepStatus
    reason: BerthPathFailure | None
    error: str


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
    #: 套件內路徑要建的媒體庫（票 06f）。
    bundled: list[BundledLibraryOut]
    #: 每一列的完整路徑是 `<library_root>/<folder>`。
    library_root: str
    #: 上一次「加入 Berth 路徑」逐個媒體庫的結果（M4 票 19）。
    berth_paths: list[BerthPathOut]


class JellyfinConnectIn(BaseModel):
    """既有 Jellyfin 的管理員帳密。只用來換 API key，不存下來。"""

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class BundledLibraryIn(BaseModel):
    name: str
    #: Berth 只寫得了電影與劇集（`SUPPORTED_TYPES`）；別的類型 FastAPI 就擋在門口。
    collection_type: CollectionType
    #: `library_root` 底下的一層。規則在 `services.jellyfin.check_bundled_libraries`。
    folder: str


class BundledLibrariesIn(BaseModel):
    libraries: list[BundledLibraryIn]


#: 清單的每一種拒絕都是「這份清單本身不成立」，所以都是 422。表是 OpenAPI 宣告的來源。
_BUNDLED_STATUS: dict[BundledLibraryRefusal, int] = dict.fromkeys(
    BundledLibraryRefusal, status.HTTP_422_UNPROCESSABLE_CONTENT
)


class BundledLibraryRefusalOut(BaseModel):
    """與其他拒絕同形（`reason` 挑句子、`detail` 是原文），多一格 `row`：是清單的第幾列。"""

    reason: BundledLibraryRefusal
    detail: str
    #: 空清單與「已建好的那一列不見了」指不出是哪一列，就不送這一格。
    row: int | None = None


def bundled_refusal(refusal: BundledLibraryRejectedError) -> HTTPException:
    body = BundledLibraryRefusalOut(reason=refusal.reason, detail=refusal.detail, row=refusal.row)
    return HTTPException(
        status_code=_BUNDLED_STATUS[refusal.reason],
        detail=body.model_dump(mode="json", exclude_none=True),
    )


class LibraryPathIn(BaseModel):
    #: 要加 Berth 路徑的媒體庫名稱，逐個試、逐個回報（M4 票 19）。路徑由伺服器算，UI 在按之前
    #: 就顯示同一個值。
    libraries: list[str] = Field(min_length=1)


@router.get("/jellyfin")
async def get_jellyfin(session: SessionDep) -> JellyfinSetupOut:
    """不連線，只回存下來的狀態。bootstrap 進行中前端輪詢這一支看序列走到哪裡。"""
    return JellyfinSetupOut.model_validate(await read_jellyfin_status(session))


@router.post("/jellyfin/bootstrap")
async def post_jellyfin_bootstrap(
    session: SessionDep, factory: ClientFactoryDep
) -> JellyfinSetupOut:
    """套件內路徑：建使用者列的媒體庫（plan §9.4 第 4 步）。重按只補建還沒建的那幾個。

    選了既有（或還沒選）是 422：Berth 絕不在使用者的 Jellyfin 上建媒體庫（brief §16.4）。
    """
    try:
        result = await bootstrap_jellyfin(session, factory)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return JellyfinSetupOut.model_validate(result)


@router.put(
    "/jellyfin/bundled", responses=refusal_responses(BundledLibraryRefusalOut, _BUNDLED_STATUS)
)
async def put_jellyfin_bundled(session: SessionDep, body: BundledLibrariesIn) -> JellyfinSetupOut:
    """套件內路徑：存下要建的媒體庫（票 06f）。剖面改一次存一次，按「開始靠泊」之前也存一次。"""
    try:
        result = await save_bundled_libraries(session, body.libraries)
    except BundledLibraryRejectedError as refusal:
        raise bundled_refusal(refusal) from refusal
    return JellyfinSetupOut.model_validate(result)


@router.post("/jellyfin/connect")
async def post_jellyfin_connect(
    session: SessionDep, factory: ClientFactoryDep, body: JellyfinConnectIn
) -> JellyfinSetupOut:
    """既有路徑：登入、建立 API key、列出媒體庫（plan §9.5）。還沒選來源是 422。"""
    try:
        result = await connect_jellyfin(
            session, factory, username=body.username, password=body.password
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return JellyfinSetupOut.model_validate(result)


@router.post("/jellyfin/libraries/paths")
async def post_jellyfin_library_path(
    session: SessionDep, factory: ClientFactoryDep, body: LibraryPathIn
) -> JellyfinSetupOut:
    """既有路徑的「加入 Berth 路徑」。舊路徑原地不動（brief §16.4）。

    失敗不是 4xx/5xx，而是逐個媒體庫的 `berth_paths` 加上一條 `failed` 的 `libraries` 步驟——
    畫面靠它們逐個說原因。
    """
    try:
        result = await add_berth_paths(session, factory, library_names=body.libraries)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return JellyfinSetupOut.model_validate(result)


# --- 頁 2：qBittorrent（plan §9.3、§8.1）---


@router.get("/qbittorrent/diff")
async def get_qbittorrent_diff(
    session: SessionDep, config: ConfigDep, factory: ClientFactoryDep
) -> QbittorrentOut:
    """現值與建議值的逐鍵差異。連得到才有內容，連不到就是 `reachable=false` 加原文。"""
    return QbittorrentOut.of(await read_qbittorrent_diff(session, factory), config)


class QbittorrentApplyIn(BaseModel):
    #: 泊位上填的 WebUI 登入（M4 票 07）。不帶就是登入照舊；套件內那一台沒設過時精靈停在這一步。
    login: InterfaceLoginIn | None = None


@router.post("/qbittorrent/apply", responses=_LOGIN_RESPONSES)
async def post_qbittorrent_apply(
    session: SessionDep,
    config: ConfigDep,
    factory: ClientFactoryDep,
    body: QbittorrentApplyIn | None = None,
) -> QbittorrentOut:
    """套用建議偏好。只寫有差異的鍵；帶了登入就順便設套件內那一台的 WebUI 登入。

    既有的那一台帶登入回 422：Berth 不寫既有服務的帳密（brief §16.4）。
    """
    login = body.login.value() if body is not None and body.login is not None else None
    try:
        result = await apply_qbittorrent(session, factory, login=login)
    except InterfaceLoginRejectedError as refusal:
        raise login_refusal(refusal) from refusal
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return QbittorrentOut.of(result, config)


@router.put("/qbittorrent/login", responses=_LOGIN_RESPONSES)
async def put_qbittorrent_login(
    session: SessionDep, config: ConfigDep, factory: ClientFactoryDep, body: InterfaceLoginIn
) -> QbittorrentOut:
    """設定頁的「更新登入」（M4 票 07）：只換套件內那一台的 WebUI 登入。既有的那一台 422。"""
    try:
        result = await set_qbittorrent_login(session, factory, body.value())
    except InterfaceLoginRejectedError as refusal:
        raise login_refusal(refusal) from refusal
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return QbittorrentOut.of(result, config)


# --- 頁 4：Prowlarr 與索引站（plan §9.3、§8.4）---


class IndexerSiteOut(BaseModel):
    """Prowlarr 裡已經有的一站（M4 票 09 的「已加入」）。"""

    model_config = ConfigDict(from_attributes=True)

    indexer_id: int
    definition_name: str
    name: str
    enabled: bool
    #: BCP 47 代碼（`zh-TW`…）。畫面照 UI 語言換成語言名。
    language: str
    #: 定義自帶的英文說明，原樣顯示、不翻。
    description: str
    privacy: str
    #: 可以從 Berth 移除（套件內、而且 Berth 加得回去）。
    removable: bool


class IndexerCandidateOut(BaseModel):
    """還沒加入、Berth 加得了的一站（M4 票 09 的「加站」）。"""

    model_config = ConfigDict(from_attributes=True)

    definition_name: str
    name: str
    privacy: str
    language: str
    description: str
    #: 推薦清單上的（排最前）；其餘是 schema 裡其他公開的 torrent 站。
    recommended: bool


class SiteCheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    definition_name: str
    passed: bool
    #: 沒通過時是哪一種；通過是 `null`。
    reason: SiteFailure | None
    #: Prowlarr 的原文（英文）。
    detail: str


class IndexerSetupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    #: 使用者在頁 4 選的來源；還沒選是 `null`。
    origin: ServiceOrigin | None
    kind: IndexerKind
    base_url: str
    api_key_present: bool
    reachable: bool
    #: Prowlarr 裡已經有的站（套件內與既有 Prowlarr）。
    sites: list[IndexerSiteOut]
    #: 還沒加入、Berth 加得了的站。Prowlarr（套件內與既有）才有；Torznab 端點沒有。
    candidates: list[IndexerCandidateOut]
    #: 上一次「加入」對每一站的結論。
    checks: list[SiteCheckOut]
    steps: list[StepOut]
    skipped: bool
    #: 泊位上有介面登入那一格：只有套件內的 Prowlarr（M4 票 07）。
    web_ui_login: bool
    #: Berth 替套件內 Prowlarr 設下的介面帳號；還沒設過是空字串。
    web_ui_username: str
    #: 讀清單那一次為什麼失敗（M4 票 21）。讀到了是 `null`。
    failure: StepFailure | None
    error: str
    #: 上一次連線測試的理由；還沒測過是 `null`（M4 票 17：既有表單照它選補法）。
    reason: ConnectionReason | None
    #: 套件內 Prowlarr 在宿主上發佈的 port（`PROWLARR_PORT`）：瀏覽器開它的介面是「現在的主機名 +
    #: 這個 port」，主機名只有前端知道（同 Jellyfin 深連結）。既有與還沒選是 `null`。
    web_port: int | None

    @classmethod
    def of(cls, status: IndexerSetupStatus, config: Config) -> IndexerSetupOut:
        bundled = status.origin is ServiceOrigin.BUNDLED
        return cls.model_validate(
            {**asdict(status), "web_port": config.prowlarr_port if bundled else None}
        )


class IndexerApplyIn(BaseModel):
    #: 勾起來的站，值是 Prowlarr 的 `definitionName`。空清單代表一個都沒勾。介面登入不跟著送
    #: （M4 票 20）：套件內那一台的登入走 `PUT /indexers/login`。
    indexers: list[str] = []


class IndexerTestIn(BaseModel):
    #: 要測的站，值是 Prowlarr 的 `definitionName`。
    indexers: list[str] = Field(min_length=1)


class IndexerTestOut(BaseModel):
    checks: list[SiteCheckOut]


class IndexerConnectIn(BaseModel):
    """既有路徑：Prowlarr 位址 + key，或任意 Torznab 端點 + key。"""

    kind: IndexerKind
    base_url: str = Field(min_length=1)
    api_key: str = ""


class SiteSearchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    indexer_id: int | None
    definition_name: str
    name: str
    count: int
    #: 前三筆的發佈名，原文。
    titles: list[str]
    error: str


class IndexerSearchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    query: str
    sites: list[SiteSearchOut]
    error: str


class SkipIn(BaseModel):
    #: 第 6 步可跳過，也可以再取消跳過（plan §9.3）。第 7 步不行（票 02b）。
    skipped: bool = True


@router.get("/indexers")
async def get_indexers(
    session: SessionDep, config: ConfigDep, factory: ClientFactoryDep
) -> IndexerSetupOut:
    """只讀：進頁 4 與設定頁的索引站分頁只發這一支，不測任何一站（M4 票 09）。"""
    return IndexerSetupOut.of(await read_indexer_status(session, factory), config)


@router.post("/indexers/test")
async def post_indexers_test(
    session: SessionDep, factory: ClientFactoryDep, body: IndexerTestIn
) -> IndexerTestOut:
    """「測試」：逐站問 Prowlarr 通不通，什麼都不建立（M4 票 09；既有的那一台也測，M4 票 20）。

    只讀（`read` 命令），但它要 Prowlarr 現場去連那些站、要花幾秒，所以是由人按的 POST。
    Torznab 端點回 422：沒有站的清單可加。
    """
    try:
        checks = await verify_sites(session, factory, body.indexers)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return IndexerTestOut.model_validate({"checks": [asdict(row) for row in checks]})


@router.post("/indexers/apply")
async def post_indexers_apply(
    session: SessionDep, config: ConfigDep, factory: ClientFactoryDep, body: IndexerApplyIn
) -> IndexerSetupOut:
    """勾起來的站逐個加進 Prowlarr（套件內與既有，M4 票 20），逐站回報成敗。

    Torznab 端點與還沒選的回 422：沒有一台 Prowlarr 可加。
    """
    try:
        result = await apply_default_indexers(session, factory, body.indexers)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return IndexerSetupOut.of(result, config)


@router.put("/indexers/login", responses=_LOGIN_RESPONSES)
async def put_indexers_login(
    session: SessionDep, config: ConfigDep, factory: ClientFactoryDep, body: InterfaceLoginIn
) -> IndexerSetupOut:
    """設定頁的「更新登入」（M4 票 07）：只換套件內 Prowlarr 的介面登入，等它重啟回來。

    既有的索引站回 422：它的登入是使用者自己的（brief §16.4）。
    """
    try:
        result = await set_prowlarr_login(session, factory, body.value())
    except InterfaceLoginRejectedError as refusal:
        raise login_refusal(refusal) from refusal
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return IndexerSetupOut.of(result, config)


@router.post("/indexers/connect")
async def post_indexers_connect(
    session: SessionDep, config: ConfigDep, factory: ClientFactoryDep, body: IndexerConnectIn
) -> IndexerSetupOut:
    """既有路徑的「測試」。測不過也存，使用者才能改一個欄位再按一次。"""
    result = await connect_indexer(
        session,
        factory,
        kind=body.kind,
        base_url=body.base_url.rstrip("/"),
        api_key=body.api_key.strip(),
    )
    return IndexerSetupOut.of(result, config)


@router.get("/indexers/search")
async def get_indexers_search(
    session: SessionDep,
    factory: ClientFactoryDep,
    query: str = "",
    indexer_id: int | None = None,
) -> IndexerSearchOut:
    """加入之後的試搜（票 06e）：逐站列出搜到幾筆與前三筆標題。空白查詢回各站最新的發佈。

    `indexer_id` 是那一列的「搜尋」，只問那一站（M4 票 09）；不帶是全部。
    只讀、不寫任何東西（`read` 命令），所以是 GET。一站失敗寫在那一站上，不是整支 5xx。
    """
    return IndexerSearchOut.model_validate(
        await search_indexers(session, factory, query=query.strip(), indexer_id=indexer_id)
    )


@router.delete("/indexers/{indexer_id}")
async def delete_indexer(
    session: SessionDep, config: ConfigDep, factory: ClientFactoryDep, indexer_id: int
) -> IndexerSetupOut:
    """從套件內的 Prowlarr 移除一站（票 06e）。已經不在的站照樣回 200：結果就是它不在了。

    對既有的索引站、與 Berth 加不回去的站（私站）回 422（brief §16.4）。
    """
    try:
        result = await remove_indexer(session, factory, indexer_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return IndexerSetupOut.of(result, config)


@router.post("/indexers/skip")
async def post_indexers_skip(
    session: SessionDep, config: ConfigDep, factory: ClientFactoryDep, body: SkipIn
) -> IndexerSetupOut:
    return IndexerSetupOut.of(await skip_indexers(session, factory, skipped=body.skipped), config)


# --- 頁 5：TMDB（plan §9.3、§8.3）。憑證使用者自備、必填（票 02b）---


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

    **沒有 `/tmdb/skip`**：這一步是閘門，測不過就走不到第 8 步（票 02b）。
    """
    return TmdbSetupOut.model_validate(await verify_tmdb(session, factory, api_key=body.api_key))


# --- 頁 3、頁 6：媒體庫與路徑、完成（plan §9.3、§9.5）---


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
    #: 套件內清單上的一列：套件內只替這幾個建 Route（M4 票 24）。既有 Jellyfin 一律 `false`。
    listed: bool


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


class RoutesIn(BaseModel):
    #: 套件內 Jellyfin 忽略這個欄位：它的 Route 由它自己的媒體庫導出（plan §9.3 第 5 步）。
    selections: list[RouteSelectionIn] = []


@router.get("/routes")
async def get_routes(session: SessionDep) -> RouteSetupOut:
    """不連線，只回媒體庫清單與已經建好的 Route（含上一輪的檢查結果）。"""
    return RouteSetupOut.model_validate(await read_route_status(session))


@router.post("/routes/libraries", responses=route_responses(RouteRefusal.JELLYFIN_UNREACHABLE))
async def post_routes_libraries(session: SessionDep, factory: ClientFactoryDep) -> RouteSetupOut:
    """頁 3 進頁時（與「重新讀取」）向 Jellyfin 重讀媒體庫（M4 票 19）。問不到是 503。"""
    try:
        result = await reread_libraries(session, factory)
    except RouteRejectedError as refusal:
        raise route_refusal(refusal) from refusal
    return RouteSetupOut.model_validate(result)


#: 這一步順帶重跑**每一條**既有 Route 的檢查，途中被另一個分頁刪掉的那一條就是它
#: （M2 票 01）。其餘無效的選擇是 `ValueError` → 422，不走拒絕那條路，所以只有這一種。
_BUILD_RESPONSES = route_responses(RouteRefusal.ROUTE_MISSING)

#: 與 `DELETE /routes/{id}` 同一個命令，所以同樣是這兩種（票 14a）。
_DELETE_RESPONSES = route_responses(RouteRefusal.ROUTE_MISSING, RouteRefusal.ROUTE_IN_USE)


@router.post("/routes", responses=_BUILD_RESPONSES)
async def post_routes(
    session: SessionDep, factory: ClientFactoryDep, body: RoutesIn | None = None
) -> RouteSetupOut:
    """建立 Route，並立刻建 category 與跑三項檢查（plan §9.5）。

    檢查失敗**不是** 4xx：它是這一步的結果，逐項回在 `routes[].checks` 裡，畫面靠它顯示
    原文與該補哪個掛載。4xx 只留給「這個選擇本身無效」（不存在的媒體庫、不是它的路徑），
    以及檢查途中被另一個分頁刪掉的那一條（404 `route_missing`，與 `routes/*` 同一種拒絕）。
    """
    try:
        result = await build_routes(
            session,
            factory,
            [
                RouteSelection(library=row.library, target_path=row.target_path)
                for row in (body or RoutesIn()).selections
            ],
        )
    except RouteRejectedError as refusal:
        raise route_refusal(refusal) from refusal
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return RouteSetupOut.model_validate(result)


@router.delete(
    "/routes/{route_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_DELETE_RESPONSES,
)
async def delete_setup_route(session: SessionDep, route_id: int) -> None:
    """第 5 步每條 Route 底下的「刪除」（票 14a）。

    與 Route 設定頁同一個命令、同一種拒絕（404 `route_missing`、409 `route_in_use`），只是跟著
    `setup/*` 的門禁：精靈跑完之前還沒有人登入得了，而 `/routes/*` 永遠只有管理員。
    """
    try:
        await delete_route(session, route_id)
    except RouteRejectedError as refusal:
        raise route_refusal(refusal) from refusal


@router.post("/complete")
async def post_complete(session: SessionDep, config: ConfigDep) -> SetupStatusOut:
    """第 8 步：寫下 `settings.setup.completed`。**寫完這一支就要登入才進得來**（票 07）。"""
    try:
        return _out(await complete_setup(session), config)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
