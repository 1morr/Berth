"""精靈頁 2：qBittorrent（plan §9.3、§8.1、§9.5）。

**Berth 不寫任何全域偏好**（M4 票 32，brief §19 D2）：送單逐個 torrent 帶 Berth 的分類與
`autoTMM=true`，分類建立時帶自己的 save path 與未完成目錄（M4 票 22），全域的哪一個鍵都不影響
Berth——與 Sonarr / Radarr 對下載器的做法相同。套件內與既有因此只差一件事：

- **WebUI 登入只給套件內的那一台**：頁上填的那一組跟著「套用」送進來（M4 票 07），設定頁改它走
  `set_interface_login`。既有 qBittorrent 是他自己的服務，Berth 不改它的密碼（brief §16.4），帶了
  登入就拒絕。**Berth 只記帳號與雜湊**，自己連它靠免密白名單（M4 票 15）。
- **還沒選來源就什麼都不寫**（M4 票 15）：寫入的命令一律拒絕。
- **Web API 低於 2.8.4 拒絕接入**，因為 Berth 要用的端點在那之前不存在（brief §16.4）。

票 32 之前套件內那一台被寫過 `save_path` 與兩個 autoTMM 開關；Berth 沒有存原值，所以不改回去。
"""

from __future__ import annotations

from collections.abc import Container, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceError
from berth.adapters.qbittorrent import (
    BERTH_TAG,
    PreferencesRejectedError,
    QbittorrentClient,
    QbittorrentVersion,
    TorrentStatus,
)
from berth.domain import (
    IssueType,
    QbittorrentStep,
    ServiceKind,
    ServiceOrigin,
    StepFailure,
    StepStatus,
)
from berth.models import (
    Job,
    QbittorrentSettings,
    Route,
    ServiceChoice,
    SetupQbittorrent,
    SetupSettings,
    SetupStep,
)
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, command
from berth.services.jellyfin import resolve_interface_login
from berth.services.settings import read_settings, update_settings
from berth.services.steps import (
    InterfaceLogin,
    StepFailedError,
    StepView,
    failed_step,
    failure_of,
    hash_password,
    message,
    password_matches,
    step_views,
)

#: WebUI 帳號的偏好鍵。`web_ui_password` 只寫不讀，讀回來的偏好裡根本沒有它（brief §20.7）。
WEB_UI_USERNAME_KEY = "web_ui_username"
WEB_UI_PASSWORD_KEY = "web_ui_password"

#: 全新 qBittorrent 的 WebUI 帳號（brief §20.14）。它讀得回來、密碼讀不回來，所以「套件內那一台
#: 自己就設過登入了」只認得出帳號不是它的那一種；還是 `admin` 的一律當沒設過（寧可多問一次）。
DEFAULT_WEB_UI_USERNAME = "admin"


def managed(statuses: Iterable[TorrentStatus], categories: Container[str]) -> list[TorrentStatus]:
    """客戶端上掛著 Berth 記號的那幾筆（plan §3.2 的**兩道篩子的聯集**）。

    category 是 Berth 某一條 Route 的，**或** tag 是 `berth`。只認 category 的話，Route 被刪掉
    之後它送出去的那些 torrent 就再也沒有人認領；只認 tag 的話，使用者自己丟進 Berth category
    的 torrent 看不見——而那一筆之後會被 importer 撿走。

    **只有一份實作**：poller（無主 torrent）與對帳（客戶端那一方）問的是同一個問題，各寫一份
    的話加第三道篩子時會漏改一邊。
    """
    return [row for row in statuses if row.category in categories or BERTH_TAG in row.tags]


async def unknown_torrents(
    session: AsyncSession, statuses: Iterable[TorrentStatus]
) -> list[TorrentStatus]:
    """掛著 Berth 記號、而 Berth 沒有 Job 的那幾筆（plan §3.2 的 `unknown_torrent`）。

    **兩個生產者問同一題**：`qbit_poller` 每一輪、對帳每一天（M2 票 09）。它們寫的是同一個
    冪等鍵，判準若各寫一份，漂移的那一天兩邊會對同一個 hash 一個開、一個不開。
    """
    categories = {row for row in await session.scalars(select(Route.category)) if row}
    ours = managed(statuses, categories)
    if not ours:
        return []
    known = set(
        await session.scalars(select(Job.hash).where(Job.hash.in_([row.hash for row in ours])))
    )
    return [row for row in ours if row.hash not in known]


def unknown_torrent_detail(status: TorrentStatus) -> dict[str, Any]:
    """`unknown_torrent` 那一件說的內容。**兩個生產者寫同一份**：`qbit_poller` 每一輪、對帳
    每一天（M2 票 09），而冪等鍵把它們收成一筆——兩邊寫的形狀不同的話，清單上那一列說的話會
    跟著最後寫的是誰變。"""
    return {
        "type": IssueType.UNKNOWN_TORRENT.value,
        "name": status.name,
        "category": status.category,
        "client_state": status.state,
    }


async def sign_in(client: QbittorrentClient, settings: QbittorrentSettings) -> None:
    """既有服務要先登入；套件內的那一台在免密白名單上（plan §9.2）。

    住在這裡而不是 `services/routes`：它問的是 qBittorrent 的事，而 Route 檢查（票 09 起
    還有送單）只是兩個呼叫端。

    **登入失敗不在這裡爆掉**：帳密不對要變成每個 Route 的 `category` 那一條紅燈（接下來的
    呼叫會丟同一個 `AuthFailedError`，原文就落在那一行），而不是一個把整頁換成 500、
    連哪個 Route 卡住都看不出來的例外。
    """
    await try_sign_in(client, settings)


async def try_sign_in(
    client: QbittorrentClient, settings: QbittorrentSettings
) -> ServiceError | None:
    """`sign_in`，但把失敗交回來。Route 檢查要把它說成第一條的紅燈（M4 票 21）：帳密錯時
    接下來的 403 與「沒登入」同形（brief §20.2），原因只有這一次登入說得出來。"""
    if not settings.username:
        return None
    try:
        await client.login(settings.username, settings.password)
    except ServiceError as exc:
        return exc
    return None


@dataclass(frozen=True, slots=True)
class QbittorrentSetupStatus:
    """`GET /api/setup/qbittorrent/diff` 與 `POST .../apply` 的整份形狀。"""

    #: 使用者在頁 2 選的來源；還沒選是 `None`。
    origin: ServiceOrigin | None
    base_url: str
    #: `app/version` 與 `app/webapiVersion`，探到什麼就顯示什麼。
    version: str
    webapi_version: str
    #: Web API 夠新（≥ 2.8.4）。
    supported: bool
    #: 這一步做不下去：版本太舊或根本連不上。
    blocked: bool
    reachable: bool
    steps: tuple[StepView, ...]
    #: 泊位上有 WebUI 登入那一格：只有套件內的那一台（M4 票 07）。
    web_ui_login: bool
    #: 套件內那一台的 WebUI 帳號：Berth 設下的，或那一台自己就設過的（不是 `admin`）。還沒設過、
    #: 或是既有的那一台是空字串。
    web_ui_username: str
    #: 連線本身為什麼失敗（M4 票 21）：UI 照它說人話。連上了是 `None`。
    failure: StepFailure | None
    #: 連線本身的失敗原文（英文）。UI 收進「技術細節」。
    error: str


async def read_qbittorrent(
    session: AsyncSession, factory: ServiceClientFactory
) -> QbittorrentSetupStatus:
    """連一次那台 qBittorrent：版本、介面登入設過沒。不寫任何東西。"""
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, QbittorrentSettings)
    origin, base_url = qbittorrent_target(setup, settings)
    if origin is None:
        # 選之前不連（M4 票 15）：不知道那一台是誰的，連「讀」也不去敲。
        return _unreachable(
            setup, settings, origin, base_url, ValueError("choose where it comes from first")
        )

    client = factory.qbittorrent(base_url)
    try:
        version, preferences = await _connect(client, settings)
    except ServiceError as exc:
        return _unreachable(setup, settings, origin, base_url, exc)
    finally:
        await client.aclose()

    return _status(
        setup,
        settings,
        origin=origin,
        base_url=base_url,
        version=version,
        preferences=preferences,
    )


async def apply_qbittorrent(
    session: AsyncSession,
    factory: ServiceClientFactory,
    *,
    login: InterfaceLogin | None = None,
) -> QbittorrentSetupStatus:
    """頁 2 的「套用」：套件內那一台設 WebUI 登入，全域偏好一個都不寫（M4 票 32）。

    `login` 是泊位上填的 WebUI 登入（M4 票 07）。不帶就是「登入照舊」：回頭重按時不帶，已經設過的
    那一組不重寫。

    既有的那一台什麼都不寫：這一步對它的意思只剩「連得上、版本夠新」，按下去只記密碼那一條
    `skipped`（`setup._qbittorrent_secured` 認它）。帶了登入就拒絕（`ValueError`）。
    """
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, QbittorrentSettings)
    chosen = setup.choices.get(ServiceKind.QBITTORRENT)
    before = setup.qbittorrent.model_copy()
    origin, base_url = qbittorrent_target(setup, settings)
    if origin is None:
        raise ValueError("choose where qBittorrent comes from first")
    if login is not None:
        _refuse_existing(origin)
        # 沿用 Jellyfin 帳密要先過 Jellyfin 那一關：在寫任何東西之前（M4 票 15）。
        login = await resolve_interface_login(session, factory, login)

    client = factory.qbittorrent(base_url)
    try:
        version, preferences = await _connect(client, settings)
        if not version.supported:
            # 版本太舊：什麼都不寫，畫面顯示升級提示（brief §16.4）。
            return _status(
                setup,
                settings,
                origin=origin,
                base_url=base_url,
                version=version,
                preferences=preferences,
            )

        steps = [await _apply_password(client, setup, origin, login, preferences)]
        preferences = dict(await client.preferences())
    except ServiceError as exc:
        return _unreachable(setup, settings, origin, base_url, exc)
    finally:
        await client.aclose()

    after = setup.qbittorrent

    def record(latest: SetupSettings) -> None:
        if _still_chosen(latest, chosen):
            latest.qbittorrent.steps = steps
            _keep_login(latest, before, after)

    def remember_address(latest: QbittorrentSettings) -> None:
        latest.base_url = base_url

    # 套用要好幾個來回，這段時間裡別的頁、啟動中的輪詢可能已經寫進同一組設定（M4 票 23）。
    setup = await update_settings(session, SetupSettings, record)
    if _still_chosen(setup, chosen):
        settings = await update_settings(session, QbittorrentSettings, remember_address)

    return _status(
        setup,
        settings,
        origin=origin,
        base_url=base_url,
        version=version,
        preferences=preferences,
    )


@command(Effect.REVERSIBLE)
async def set_interface_login(
    session: AsyncSession, factory: ServiceClientFactory, login: InterfaceLogin
) -> QbittorrentSetupStatus:
    """設定頁的「更新登入」（M4 票 07）：只換套件內那一台的 WebUI 登入。

    與頁 2 的密碼那一條是同一段（`_apply_password`），結果換掉那一條纜繩。可逆的方式就是
    再設一組。既有的那一台拒絕（`ValueError`）。
    """
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, QbittorrentSettings)
    chosen = setup.choices.get(ServiceKind.QBITTORRENT)
    before = setup.qbittorrent.model_copy()
    origin, base_url = qbittorrent_target(setup, settings)
    _refuse_existing(origin)
    login = await resolve_interface_login(session, factory, login)

    client = factory.qbittorrent(base_url)
    try:
        version, preferences = await _connect(client, settings)
        step = await _apply_password(client, setup, origin, login, preferences)
    except ServiceError as exc:
        return _unreachable(setup, settings, origin, base_url, exc)
    finally:
        await client.aclose()

    after = setup.qbittorrent

    def record(latest: SetupSettings) -> None:
        if not _still_chosen(latest, chosen):
            return
        latest.qbittorrent.steps = [
            *(row for row in latest.qbittorrent.steps if row.key != step.key),
            step,
        ]
        _keep_login(latest, before, after)

    setup = await update_settings(session, SetupSettings, record)
    return _status(
        setup,
        settings,
        origin=origin,
        base_url=base_url,
        version=version,
        preferences=preferences,
    )


def _refuse_existing(origin: ServiceOrigin | None) -> None:
    if origin is not ServiceOrigin.BUNDLED:
        # 泊位上根本沒有那一格；走到這裡的只有直接打 API 的人（brief §16.4 的紅線）。
        raise ValueError("this qBittorrent is an existing service; Berth does not set its login")


async def _apply_password(
    client: QbittorrentClient,
    setup: SetupSettings,
    origin: ServiceOrigin | None,
    login: InterfaceLogin | None,
    preferences: Mapping[str, Any],
) -> SetupStep:
    """套件內的那一台另設 WebUI 登入（M4 票 07）。

    設完的那一組只記帳號與加鹽雜湊（`setup.qbittorrent.web_ui_*`，M4 票 15）：Berth 連它靠免密
    白名單，用不到密碼；雜湊只拿來比出「已經是這一組了」——密碼是這一步唯一讀不回來比對的鍵。

    不帶登入時：設過的照舊（`skipped`、細節是帳號）；**那一台自己就設過的也不強迫再設**（重裝保留
    config，M4 票 15）——帳號不是 `admin` 就是設過了（brief §20.14），記下帳號、雜湊留空；其餘是
    `pending`：必填，精靈停在頁 2（`setup._qbittorrent_secured`）。
    """
    key = QbittorrentStep.PASSWORD.value
    if origin is not ServiceOrigin.BUNDLED:
        return SetupStep(key=key, status=StepStatus.SKIPPED)
    record = setup.qbittorrent
    if login is None:
        instance = _instance_username(preferences)
        if not record.web_ui_username and instance:
            record.web_ui_username = instance
            record.web_ui_password_hash = ""
        if not record.web_ui_username:
            return SetupStep(key=key, status=StepStatus.PENDING)
        return SetupStep(key=key, status=StepStatus.SKIPPED, detail=record.web_ui_username)
    if login.username == record.web_ui_username and password_matches(
        login.password, record.web_ui_password_hash
    ):
        return SetupStep(key=key, status=StepStatus.SKIPPED, detail=login.username)

    try:
        # 密碼先送、帳號後送（M4 票 26）：5.2 起 qBittorrent 帳號先驗先寫、密碼後驗，一次送兩個鍵
        # 時密碼被拒、帳號已經換掉，下一次讀就被當成「它自己設過了」（brief §20.2）。分兩次送，
        # 密碼被拒時那一台一個鍵都沒動。帳號被拒（前端照同一套規則先擋，只剩直接打 API）或兩次
        # 之間斷線時，密碼已經換了、帳號還是原本那一個：Berth 不記，這一條照舊是沒設好，重送一組
        # 就蓋過去。
        await client.set_preferences({WEB_UI_PASSWORD_KEY: login.password})
        await client.set_preferences({WEB_UI_USERNAME_KEY: login.username})
    except PreferencesRejectedError as exc:
        return failed_step(
            key, StepFailedError(StepFailure.LOGIN_REJECTED, exc.reason), detail=login.username
        )
    except ServiceError as exc:
        return failed_step(key, exc)
    # 兩個鍵都進去了才記（M4 票 26）。
    record.web_ui_username = login.username
    record.web_ui_password_hash = hash_password(login.password)
    return SetupStep(key=key, status=StepStatus.OK, detail=login.username)


def _still_chosen(latest: SetupSettings, chosen: ServiceChoice | None) -> bool:
    """剛才連的那一台還是頁 2 現在選的。使用者在這段時間裡換了一台（另一個分頁），結果說的是原本
    那一台，不記（M4 票 23，`setup._test_and_record` 同一條）。"""
    current = latest.choices.get(ServiceKind.QBITTORRENT)
    return (
        chosen is not None and current is not None and current.is_at(chosen.origin, chosen.base_url)
    )


def _keep_login(latest: SetupSettings, before: SetupQbittorrent, after: SetupQbittorrent) -> None:
    """`_apply_password` 這一次改了介面登入的紀錄才搬到重讀的那一份上（M4 票 23）。沒改的話不寫：
    開頭讀到的那一組可能已經被別的命令換掉了。"""
    if (after.web_ui_username, after.web_ui_password_hash) == (
        before.web_ui_username,
        before.web_ui_password_hash,
    ):
        return
    latest.qbittorrent.web_ui_username = after.web_ui_username
    latest.qbittorrent.web_ui_password_hash = after.web_ui_password_hash


def _instance_username(preferences: Mapping[str, Any]) -> str:
    """那一台自己的 WebUI 帳號，還是預設的 `admin` 時是空字串（`DEFAULT_WEB_UI_USERNAME`）。"""
    name = str(preferences.get(WEB_UI_USERNAME_KEY) or "")
    return "" if name == DEFAULT_WEB_UI_USERNAME else name


async def _connect(
    client: QbittorrentClient, settings: QbittorrentSettings
) -> tuple[QbittorrentVersion, dict[str, Any]]:
    """既有服務要先登入；套件內的那一台在免密白名單上（plan §9.2）。"""
    if settings.username:
        await client.login(settings.username, settings.password)
    version = await client.version()
    if not version.supported:
        return (version, {})
    return (version, dict(await client.preferences()))


def qbittorrent_target(
    setup: SetupSettings, settings: QbittorrentSettings
) -> tuple[ServiceOrigin | None, str]:
    """要連哪一台、它是誰的：使用者在頁 2 選的（M4 票 15），位址是選的時候存下的那一條
    （套件內是 compose 主機名，`clients.bundled_targets`）。還沒選是 `None`，寫入的命令一律拒絕。
    """
    choice = setup.choices.get(ServiceKind.QBITTORRENT)
    if choice is None:
        return (None, settings.base_url)
    return (choice.origin, settings.base_url or choice.base_url)


def _web_ui_username(
    setup: SetupSettings, origin: ServiceOrigin | None, preferences: Mapping[str, Any]
) -> str:
    """套件內那一台的 WebUI 帳號：Berth 記下的，或那一台自己就設過的。既有的那一台是空字串——
    Berth 連它用的帳密是使用者給的，不是 Berth 設的登入。"""
    if origin is not ServiceOrigin.BUNDLED:
        return ""
    return setup.qbittorrent.web_ui_username or _instance_username(preferences)


def _status(
    setup: SetupSettings,
    settings: QbittorrentSettings,
    *,
    origin: ServiceOrigin | None,
    base_url: str,
    version: QbittorrentVersion,
    preferences: dict[str, Any],
) -> QbittorrentSetupStatus:
    supported = version.supported
    return QbittorrentSetupStatus(
        origin=origin,
        base_url=base_url,
        version=version.app,
        webapi_version=version.webapi,
        supported=supported,
        blocked=not supported,
        reachable=True,
        steps=step_views(setup.qbittorrent.steps),
        web_ui_login=origin is ServiceOrigin.BUNDLED,
        web_ui_username=_web_ui_username(setup, origin, preferences),
        failure=None,
        error="",
    )


def _unreachable(
    setup: SetupSettings,
    settings: QbittorrentSettings,
    origin: ServiceOrigin | None,
    base_url: str,
    exc: Exception,
) -> QbittorrentSetupStatus:
    failure, _ = failure_of(exc)
    return QbittorrentSetupStatus(
        origin=origin,
        base_url=base_url,
        version="",
        webapi_version="",
        supported=False,
        blocked=True,
        reachable=False,
        steps=step_views(setup.qbittorrent.steps),
        web_ui_login=origin is ServiceOrigin.BUNDLED,
        web_ui_username=_web_ui_username(setup, origin, {}),
        failure=failure,
        error=message(exc),
    )
