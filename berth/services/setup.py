"""設定精靈的命令（plan §9.3）。本檔是第 1–2 步與步序本身；各泊位在 `services/` 的鄰居。

每個命令都冪等：精靈的每一步之後都能在設定頁重跑，狀態全部在 `settings.setup` 那一列，
所以重跑只是覆寫同一份值，不會長出第二份資料。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

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
from berth.domain import (
    PROWLARR_LOGIN_STEP,
    DetectionReason,
    IndexerKind,
    JellyfinStep,
    QbittorrentStep,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.models import (
    IndexerSettings,
    JellyfinSettings,
    QbittorrentSettings,
    ServiceProbe,
    SetupAdmin,
    SetupSettings,
)
from berth.services.clients import ServiceClientFactory, SetupProbes
from berth.services.routes import routes_ready
from berth.services.settings import read_settings, write_settings
from berth.services.tmdb import tmdb_verified

#: 服務未就緒時的輪詢上限（plan §9.3 第 2 步）。逾時後使用者可重試，不是永遠轉圈。
DETECT_WINDOW = timedelta(minutes=2)

#: 精靈的步序（plan §9.3）。第 1 步建管理員，第 2 步偵測，第 3 步起是各服務。
#: 每一步「做完了沒」由它自己的狀態導出（`_current_step`），不存游標。
STEP_ADMIN = 1
STEP_DETECT = 2
STEP_JELLYFIN = 3
STEP_QBITTORRENT = 4
STEP_INDEXER = 5
STEP_TMDB = 6
STEP_ROUTES = 7
STEP_COMPLETE = 8


@dataclass(frozen=True, slots=True)
class ServiceConnection:
    """使用者為既有服務填的連線資訊（plan §9.3 第 2 步）。"""

    base_url: str
    api_key: str = ""
    username: str = ""
    password: str = ""


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
    #: 連線問題解掉了沒。沒解掉就要使用者補位址或憑證，第 2 步也還沒做完。
    resolved: bool


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


async def is_setup_complete(session: AsyncSession) -> bool:
    """精靈跑完了沒。這一個位元是匿名可讀的（`GET /api/health`）：前端要在**還沒有人
    登入得了**的時候就決定該畫精靈還是登入頁，而精靈未完成時本來就整組匿名開放。
    """
    return (await read_settings(session, SetupSettings)).completed


async def read_status(session: AsyncSession) -> SetupStatus:
    """目前的步驟與上一次的逐服務判定。不做任何探測。"""
    return await _read(session, now=_utcnow())


async def complete_setup(session: AsyncSession) -> SetupStatus:
    """第 8 步：寫下 `settings.setup.completed`，精靈結束（plan §9.3 第 8 步）。

    **這個位元就是門禁的開關**：寫下去之後 `setup/*` 只有管理員進得來，`/` 也不再導向精靈
    （票 07）。所以在寫之前要確定不可跳的那幾步真的做完了——第 3、4、6、7 步不可跳
    （plan §9.3、票 02b）。第 6 步在這裡再擋一次，因為使用者回得去把 key 清掉。
    """
    setup = await read_settings(session, SetupSettings)
    if not tmdb_verified(setup):
        raise ValueError("finish step 6 first: TMDB needs a credential that passes its test")
    if not await routes_ready(session):
        raise ValueError("finish step 7 first: every library route has to pass its checks")
    setup.completed = True
    await write_settings(session, setup)
    await session.commit()
    return await _read(session, now=_utcnow())


async def _read(session: AsyncSession, *, now: datetime) -> SetupStatus:
    """整份狀態。步驟是導出的，而第 7 步的依據在 `routes` 表，所以要多讀一次它。"""
    setup = await read_settings(session, SetupSettings)
    return _status(setup, now=now, routes=await routes_ready(session))


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
    return await _read(session, now=_utcnow())


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

    await _remember_bundled_indexer(session, probed, probes.prowlarr_api_key)
    await write_settings(session, setup)
    return await _read(session, now=moment)


async def _remember_bundled_indexer(
    session: AsyncSession, probed: dict[ServiceKind, ServiceProbe], api_key: str
) -> None:
    """套件內 Prowlarr 的 API key 讀自唯讀掛載，探測是唯一讀得到它的地方。

    存進 `settings.services.indexer` 之後，第 5 步與 M1 的搜尋都從同一個地方拿憑證，不必再各自
    去翻那個檔案；使用者自己貼過的值優先，不會被掛載讀到的蓋掉。
    """
    probe = probed.get(ServiceKind.PROWLARR)
    if probe is None or probe.origin is not ServiceOrigin.BUNDLED or not api_key:
        return
    indexer = await read_settings(session, IndexerSettings)
    if indexer.api_key:
        return
    indexer.kind = IndexerKind.PROWLARR.value
    indexer.base_url = probe.base_url
    indexer.api_key = api_key
    await write_settings(session, indexer)


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
    return await _read(session, now=moment)


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
        indexer.kind = IndexerKind.PROWLARR.value
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

#: 這些理由代表「還要使用者補連線資訊」，其餘的都是服務自己報出來的事實（plan §9.3 第 2 步）。
UNRESOLVED_REASONS = frozenset(
    {
        DetectionReason.NOT_DEPLOYED,
        DetectionReason.UNREACHABLE,
        DetectionReason.AUTH_REQUIRED,
        DetectionReason.PROTOCOL_MISMATCH,
        DetectionReason.API_KEY_MISSING,
    }
)


def _still_waiting(setup: SetupSettings) -> bool:
    return not setup.services or any(
        probe.origin in _UNSETTLED for probe in setup.services.values()
    )


def _resolved(probe: ServiceProbe) -> bool:
    """這個服務的連線問題解掉了沒。

    「有結論」不等於「可以往下走」：從 `COMPOSE_PROFILES` 拿掉的服務立刻就有結論（既有），
    但 Berth 還不知道它在哪裡。第 2 步要到每個服務都連得上才算做完，否則精靈會跳過那張
    使用者唯一能填位址的表單。
    """
    return probe.origin not in _UNSETTLED and probe.reason not in UNRESOLVED_REASONS


def _detect_done(setup: SetupSettings) -> bool:
    return len(setup.services) == len(ServiceKind) and all(
        _resolved(probe) for probe in setup.services.values()
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


def _current_step(setup: SetupSettings, *, routes: bool) -> int:
    """步驟由狀態導出，不存游標。

    精靈可以續行也可以重跑，存「走到第幾步」的游標會在偵測結果變回等待時說謊。
    第 7 步的依據不在設定裡而在 `routes` 表（`routes_ready`），所以它由參數帶進來。
    """
    if not setup.admin.username:
        return STEP_ADMIN
    if not _detect_done(setup):
        return STEP_DETECT
    if not _jellyfin_secured(setup):
        return STEP_JELLYFIN
    if not _qbittorrent_secured(setup):
        return STEP_QBITTORRENT
    if not _indexer_settled(setup):
        return STEP_INDEXER
    if not tmdb_verified(setup):
        return STEP_TMDB
    if not routes:
        return STEP_ROUTES
    return STEP_COMPLETE


def _jellyfin_secured(setup: SetupSettings) -> bool:
    """第 3 步做完了沒（票 06）。

    套件內要 plan §9.4 的九步都有結論；既有只要拿得到 API key——建立媒體庫與安裝插件
    在既有 Jellyfin 上是使用者按不按都可以的按鈕，不是這一步的完成條件（brief §16.4）。
    """
    done = {
        row.key for row in setup.jellyfin.steps if row.status in (StepStatus.OK, StepStatus.SKIPPED)
    }
    probe = setup.services.get(ServiceKind.JELLYFIN)
    if probe is not None and probe.origin is ServiceOrigin.BUNDLED:
        return done >= {step.value for step in JellyfinStep}
    return JellyfinStep.API_KEY.value in done


def _qbittorrent_secured(setup: SetupSettings) -> bool:
    """第 4 步做完了沒（票 08）：五個建議鍵都有結論。

    密碼不算——沒勾「同一組帳密」的人永遠不會有那一條，拿它當條件會把精靈卡在第 4 步。
    """
    done = {
        row.key
        for row in setup.qbittorrent.steps
        if row.status in (StepStatus.OK, StepStatus.SKIPPED)
    }
    return done >= {step.value for step in QbittorrentStep if step is not QbittorrentStep.PASSWORD}


def _indexer_settled(setup: SetupSettings) -> bool:
    """第 5 步可跳過（plan §9.3），所以「有結論」包含「使用者說之後再說」。

    逐站失敗不擋：十個公開站裡有幾個連不上是常態，只要接上了一個就走得下去。
    **替 Prowlarr 介面設登入那一條不算**——它與站接不接得上無關，而且不勾「同一組帳密」時
    它永遠是 `skipped`，算進去等於十站全失敗也放行。
    """
    return setup.indexer.skipped or any(
        row.status in (StepStatus.OK, StepStatus.SKIPPED)
        for row in setup.indexer.steps
        if row.key != PROWLARR_LOGIN_STEP
    )


def _status(setup: SetupSettings, *, now: datetime, routes: bool) -> SetupStatus:
    waited = now - setup.probe_started_at if setup.probe_started_at else timedelta()
    return SetupStatus(
        completed=setup.completed,
        current_step=_current_step(setup, routes=routes),
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
                resolved=_resolved(probe),
            )
            for kind in ServiceKind
            if (probe := setup.services.get(kind)) is not None
        ),
        waited_seconds=max(int(waited.total_seconds()), 0),
        window_seconds=int(DETECT_WINDOW.total_seconds()),
    )


def _utcnow() -> datetime:
    return datetime.now(UTC)
