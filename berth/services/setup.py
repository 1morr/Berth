"""設定精靈的命令（plan §9.3）。本檔是第 1–2 步；第 3–8 步在票 06、08、09。

每個命令都冪等：精靈的每一步之後都能在設定頁重跑，狀態全部在 `settings.setup` 那一列，
所以重跑只是覆寫同一份值，不會長出第二份資料。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import (
    AuthFailedError,
    ProtocolMismatchError,
    ServiceNotDeployedError,
    ServiceUnavailableError,
)
from berth.adapters.jellyfin import JellyfinClient
from berth.adapters.prowlarr import ProwlarrClient
from berth.adapters.qbittorrent import QbittorrentClient, QbittorrentVersion
from berth.domain import DetectionReason, ServiceKind, ServiceOrigin
from berth.models import (
    IndexerSettings,
    JellyfinSettings,
    QbittorrentSettings,
    ServiceProbe,
    SetupAdmin,
    SetupSettings,
)
from berth.services.settings import read_settings, write_settings

#: 服務未就緒時的輪詢上限（plan §9.3 第 2 步）。逾時後使用者可重試，不是永遠轉圈。
DETECT_WINDOW = timedelta(minutes=2)

#: 精靈的步序（plan §9.3）。第 1 步建管理員，第 2 步偵測，第 3 步起是各服務。
STEP_ADMIN = 1
STEP_DETECT = 2
STEP_JELLYFIN = 3


@dataclass(frozen=True, slots=True)
class SetupProbes:
    """第 2 步要探的三個 client，加上唯讀掛載讀到的 Prowlarr API key。"""

    jellyfin: JellyfinClient
    qbittorrent: QbittorrentClient
    prowlarr: ProwlarrClient
    prowlarr_api_key: str


@dataclass(frozen=True, slots=True)
class ServiceConnection:
    """使用者為既有服務填的連線資訊（plan §9.3 第 2 步）。"""

    base_url: str
    api_key: str = ""
    username: str = ""
    password: str = ""


class ServiceClientFactory(Protocol):
    """依使用者填的位址造 client。探測套件內服務用的是固定主機名，不走這裡。"""

    def jellyfin(self, base_url: str) -> JellyfinClient: ...

    def qbittorrent(self, base_url: str) -> QbittorrentClient: ...

    def prowlarr(self, base_url: str, api_key: str) -> ProwlarrClient: ...


@dataclass(frozen=True, slots=True)
class ServiceDetection:
    kind: ServiceKind
    origin: ServiceOrigin
    reason: DetectionReason
    #: 實測值：Jellyfin 版本、qBittorrent 版本、Prowlarr 的索引站數量。
    detail: str
    base_url: str
    #: 這個判定來自使用者填的連線表單，不是探測 compose 主機名的結果。
    configured: bool


@dataclass(frozen=True, slots=True)
class SetupStatus:
    """`GET /api/setup/status` 的整份形狀。"""

    completed: bool
    current_step: int
    admin_created: bool
    admin_username: str
    apply_to_services: bool
    services: tuple[ServiceDetection, ...]
    #: 本輪已等待的秒數與上限，UI 用來顯示等待狀態與逾時。
    waited_seconds: int
    window_seconds: int


async def read_status(session: AsyncSession) -> SetupStatus:
    """目前的步驟與上一次的逐服務判定。不做任何探測。"""
    return _status(await read_settings(session, SetupSettings), now=_utcnow())


async def create_admin(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    apply_to_services: bool,
) -> SetupStatus:
    """第 1 步。重跑就是覆寫同一組帳密。呼叫端負責 commit。"""
    if not username.strip():
        raise ValueError("username must not be blank")
    if not password:
        raise ValueError("password must not be blank")

    setup = await read_settings(session, SetupSettings)
    setup.admin = SetupAdmin(
        username=username.strip(),
        password=password,
        apply_to_services=apply_to_services,
    )
    await write_settings(session, setup)
    return _status(setup, now=_utcnow())


async def detect_services(
    session: AsyncSession,
    probes: SetupProbes,
    *,
    restart: bool = False,
    now: datetime | None = None,
) -> SetupStatus:
    """第 2 步：逐一探測三個 compose 主機名並記下判定（plan §9.3、brief §16.3）。

    `restart=True` 是使用者按「重試」，重新開始 2 分鐘的輪詢窗口。

    **已經手動接好的服務不重探**：它根本不在 compose 主機名上，再探一次只會把使用者剛填好的
    連線判回「探不到」。前端在有服務還在啟動時每 3 秒自動探一次，沒有這條保護的話，
    「Jellyfin 被拿掉 profile + qBittorrent 還在啟動」這個組合會在填完表單三秒後被清掉。
    要重測那一個服務，用它自己的「測試連線」（`connect_service`）。
    """
    moment = now or _utcnow()
    setup = await read_settings(session, SetupSettings)
    if restart or setup.probe_started_at is None:
        setup.probe_started_at = moment

    waited = moment - setup.probe_started_at
    probed: dict[ServiceKind, ServiceProbe] = {}
    for kind in ServiceKind:
        configured = setup.services.get(kind)
        if configured is not None and configured.configured:
            probed[kind] = configured
            continue
        origin, reason, detail, base_url = await _probe(kind, probes)
        probed[kind] = ServiceProbe(
            origin=_settled(origin, waited),
            reason=reason,
            detail=detail,
            base_url=base_url,
            checked_at=moment,
        )
    setup.services = probed
    if not _still_waiting(setup):
        # 全部有結論了：下一輪重試從頭開始算，不繼承這一輪已經燒掉的時間。
        setup.probe_started_at = None

    await write_settings(session, setup)
    return _status(setup, now=moment)


async def connect_service(
    session: AsyncSession,
    kind: ServiceKind,
    connection: ServiceConnection,
    factory: ServiceClientFactory,
    *,
    now: datetime | None = None,
) -> SetupStatus:
    """既有服務的「測試連線」：存下連線資訊，然後真的連一次（plan §9.3 第 2 步）。

    測不過也照樣存——使用者要能改一個欄位再按一次，而不是每次重打整份表單。

    **判定用的是同一套規則**（`_probe`），不是「他填了表單所以算既有」：使用者為一台
    讀不到 API key 的**套件內** Prowlarr 貼上 key 之後，它仍然該是套件內，否則票 08 的
    十個預設索引站對它不會跑。位址是誰填的不影響服務自己報出來的事實。
    """
    moment = now or _utcnow()
    setup = await read_settings(session, SetupSettings)
    await _remember_connection(session, kind, connection)

    origin, reason, detail, _ = await _probe_connection(kind, connection, factory)
    setup.services = {
        **setup.services,
        kind: ServiceProbe(
            origin=origin,
            reason=reason,
            detail=detail,
            base_url=connection.base_url,
            checked_at=moment,
            configured=True,
        ),
    }
    if not _still_waiting(setup):
        setup.probe_started_at = None
    await write_settings(session, setup)
    return _status(setup, now=moment)


async def _remember_connection(
    session: AsyncSession, kind: ServiceKind, connection: ServiceConnection
) -> None:
    """連線資訊寫進它平常住的 `settings.services.*`，之後的里程碑從同一個地方讀。"""
    if kind is ServiceKind.JELLYFIN:
        jellyfin = await read_settings(session, JellyfinSettings)
        jellyfin.base_url = connection.base_url
        await write_settings(session, jellyfin)
    elif kind is ServiceKind.QBITTORRENT:
        qbittorrent = await read_settings(session, QbittorrentSettings)
        qbittorrent.base_url = connection.base_url
        qbittorrent.username = connection.username
        qbittorrent.password = connection.password
        await write_settings(session, qbittorrent)
    else:
        indexer = await read_settings(session, IndexerSettings)
        indexer.kind = "prowlarr"
        indexer.base_url = connection.base_url
        indexer.api_key = connection.api_key
        await write_settings(session, indexer)


async def _probe_connection(
    kind: ServiceKind, connection: ServiceConnection, factory: ServiceClientFactory
) -> _Verdict:
    """用使用者填的位址與憑證跑一次判定，規則與探測 compose 主機名時完全相同。

    唯一的差別是「連不上」的意思：探 compose 主機名時代表容器還在啟動，該等；
    使用者自己填的位址連不上就是連不上，不該給他一個永遠不會好的倒數。
    """
    origin, reason, detail, base_url = await _connection_verdict(kind, connection, factory)
    if origin is ServiceOrigin.PENDING:
        return _existing(reason, detail, base_url)
    return (origin, reason, detail, base_url)


async def _connection_verdict(
    kind: ServiceKind, connection: ServiceConnection, factory: ServiceClientFactory
) -> _Verdict:
    if kind is ServiceKind.JELLYFIN:
        jellyfin = factory.jellyfin(connection.base_url)
        try:
            return await _verdict_jellyfin(jellyfin)
        finally:
            await jellyfin.aclose()

    if kind is ServiceKind.QBITTORRENT:
        qbittorrent = factory.qbittorrent(connection.base_url)
        try:
            return await _verdict_qbittorrent(qbittorrent, connection.username, connection.password)
        finally:
            await qbittorrent.aclose()

    prowlarr = factory.prowlarr(connection.base_url, connection.api_key)
    try:
        return await _verdict_prowlarr(prowlarr, connection.api_key)
    finally:
        await prowlarr.aclose()


#: 還沒有結論的兩種狀態：容器啟動中，或已經等超過上限。
_UNSETTLED = (ServiceOrigin.PENDING, ServiceOrigin.TIMEOUT)


def _still_waiting(setup: SetupSettings) -> bool:
    return not setup.services or any(
        probe.origin in _UNSETTLED for probe in setup.services.values()
    )


def _settled(origin: ServiceOrigin, waited: timedelta) -> ServiceOrigin:
    """還在等的服務超過輪詢上限就轉成逾時，讓 UI 給出重試而不是無限等待。"""
    if origin is ServiceOrigin.PENDING and waited > DETECT_WINDOW:
        return ServiceOrigin.TIMEOUT
    return origin


_Verdict = tuple[ServiceOrigin, DetectionReason, str, str]


async def _probe(kind: ServiceKind, probes: SetupProbes) -> _Verdict:
    """探測 compose 主機名上的那一台。"""
    if kind is ServiceKind.JELLYFIN:
        return await _verdict_jellyfin(probes.jellyfin)
    if kind is ServiceKind.QBITTORRENT:
        return await _verdict_qbittorrent(probes.qbittorrent, "", "")
    return await _verdict_prowlarr(probes.prowlarr, probes.prowlarr_api_key)


async def _verdict_jellyfin(client: JellyfinClient) -> _Verdict:
    """`StartupWizardCompleted=false` 才是套件內；跑過自己的精靈就是使用者的服務。"""

    async def probe() -> _Verdict:
        info = await client.public_info()
        if info.startup_wizard_completed:
            return _existing(DetectionReason.SETUP_COMPLETED, info.version, client.base_url)
        return (
            ServiceOrigin.BUNDLED,
            DetectionReason.SETUP_PENDING,
            info.version,
            client.base_url,
        )

    return await _classified(probe, client.base_url)


async def _verdict_qbittorrent(client: QbittorrentClient, username: str, password: str) -> _Verdict:
    """免密進得去就是套件內；要帳密就是使用者自己設過密碼的那一台（plan §9.2）。"""

    async def probe() -> _Verdict:
        if username:
            await client.login(username, password)
            settled = _existing(DetectionReason.CONNECTED, "", client.base_url)
        else:
            settled = (ServiceOrigin.BUNDLED, DetectionReason.ANONYMOUS_OK, "", client.base_url)
        version = await client.version()
        return (settled[0], settled[1], _version_detail(version), client.base_url)

    return await _classified(probe, client.base_url)


async def _verdict_prowlarr(client: ProwlarrClient, api_key: str) -> _Verdict:
    """讀得到 API key 而且一個索引站都沒有才是套件內（plan §9.3 第 2 步）。"""

    async def probe() -> _Verdict:
        await client.ping()
        if not api_key:
            # 唯讀掛載與環境變數都沒有，使用者也還沒貼：退回手動貼上（plan §9.2）。
            return _existing(DetectionReason.API_KEY_MISSING, "", client.base_url)
        indexers = await client.indexers()
        if indexers:
            return _existing(DetectionReason.HAS_INDEXERS, str(len(indexers)), client.base_url)
        return (ServiceOrigin.BUNDLED, DetectionReason.NO_INDEXERS, "", client.base_url)

    return await _classified(probe, client.base_url)


def _version_detail(version: QbittorrentVersion) -> str:
    return f"{version.app} · Web API {version.webapi}"


async def _classified(probe: Callable[[], Awaitable[_Verdict]], base_url: str) -> _Verdict:
    """把 adapter 的四種錯誤翻成判定。

    連不上與解不到必須分開：解不到代表這個服務被從 `COMPOSE_PROFILES` 拿掉了，該立刻顯示
    既有服務的表單；連不上只是容器還在啟動，該繼續等到輪詢上限。
    """
    try:
        return await probe()
    except ServiceNotDeployedError:
        return _existing(DetectionReason.NOT_DEPLOYED, "", base_url)
    except ServiceUnavailableError:
        return (ServiceOrigin.PENDING, DetectionReason.UNREACHABLE, "", base_url)
    except AuthFailedError:
        return _existing(DetectionReason.AUTH_REQUIRED, "", base_url)
    except ProtocolMismatchError:
        return _existing(DetectionReason.PROTOCOL_MISMATCH, "", base_url)


def _existing(reason: DetectionReason, detail: str, base_url: str) -> _Verdict:
    return (ServiceOrigin.EXISTING, reason, detail, base_url)


def _current_step(setup: SetupSettings) -> int:
    """步驟由狀態導出，不存游標。

    精靈可以續行也可以重跑，存「走到第幾步」的游標會在偵測結果變回等待時說謊。
    後面的步驟（票 06、08、09）依同樣的方式從自己的狀態導出。
    """
    if not setup.admin.username:
        return STEP_ADMIN
    if _still_waiting(setup):
        return STEP_DETECT
    return STEP_JELLYFIN


def _status(setup: SetupSettings, *, now: datetime) -> SetupStatus:
    waited = now - setup.probe_started_at if setup.probe_started_at else timedelta()
    return SetupStatus(
        completed=setup.completed,
        current_step=_current_step(setup),
        admin_created=bool(setup.admin.username),
        admin_username=setup.admin.username,
        apply_to_services=setup.admin.apply_to_services,
        services=tuple(
            ServiceDetection(
                kind=kind,
                origin=probe.origin,
                reason=probe.reason,
                detail=probe.detail,
                base_url=probe.base_url,
                configured=probe.configured,
            )
            for kind in ServiceKind
            if (probe := setup.services.get(kind)) is not None
        ),
        waited_seconds=max(int(waited.total_seconds()), 0),
        window_seconds=int(DETECT_WINDOW.total_seconds()),
    )


def _utcnow() -> datetime:
    return datetime.now(UTC)
