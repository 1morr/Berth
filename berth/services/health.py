"""健康檢查的四項（plan §3.2、§9.5、brief §16.2、票 10）。

四項各自回答一個問題，合起來就是「Berth 現在還能不能做完一次入庫」：

1. **Jellyfin**：連得上、而且 Berth 那把 API key 還有效（媒體庫列得出來）。
2. **qBittorrent**：連得上、Web API 夠新，而且建議偏好沒有被改掉（漂移，brief §16.3）。
3. **索引站**：Prowlarr 或使用者自己貼的 Torznab 端點還搜得動（plan §8.4）。
4. **Route**：五條纜繩重跑一次——category、兩邊回報的路徑、跨服務可見性、真的 `link()`
   一次比 inode（plan §9.5）。與精靈第 7 步是同一組檢查、同一個欄位。

四項之後再量兩件會變成 Issue 的事（M2 票 09c）：Route 的媒體庫掛不掛 TVDB、磁碟剩的空間夠不夠
（`services/health_issues.py`）。它們不是紅燈——服務都還連得上——而是要有人決定的事。

**每一項都獨立**：一個服務掛掉只會讓它自己那一項變紅，例外在它那一格就被接住
（`_run`），另外三項照跑。Route 那一項是唯一有依賴的——它的檢查要問 qBittorrent 與
Jellyfin，所以那兩台掛掉時 Route 一起紅，那是事實不是連坐。

**檢查結果與使用者設定分開存**（`settings.health`）：迴圈每 5 分鐘寫一次的東西不該混進
`settings.services.*`，那幾組是整組覆寫的連線資訊，混在一起兩邊會互相蓋掉。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceError
from berth.adapters.jellyfin import unsupported_message
from berth.adapters.qbittorrent import MIN_WEBAPI, IpBannedError
from berth.domain import HealthStatus, IndexerKind, ServiceKind, ServiceOrigin, StepStatus
from berth.models import (
    HealthSettings,
    IndexerSettings,
    JellyfinSettings,
    PathSettings,
    PollerSettings,
    QbittorrentSettings,
    ServiceHealth,
    SetupSettings,
)
from berth.services.clients import ServiceClientFactory
from berth.services.downloads import ACTIVE_INTERVAL
from berth.services.health_issues import watch_conditions
from berth.services.indexer import probe_indexer
from berth.services.qbittorrent import drifted_keys
from berth.services.routes import RouteView, check_routes, read_route_status, routes_health
from berth.services.settings import read_settings, write_settings
from berth.services.steps import message

logger = logging.getLogger(__name__)

#: 檢查間隔（plan §3.2）。票 10 的驗收是「停掉任一服務後 5 分鐘內該項變紅」，所以它同時
#: 是那條驗收的上限——調大就違約了。
CHECK_INTERVAL = timedelta(minutes=5)

Status = Literal["ok", "degraded"]


@dataclass(frozen=True, slots=True)
class ServiceHealthView:
    """健康頁上一個服務那一列。"""

    kind: ServiceKind
    #: 套件內還是既有。修正建議分兩種：前者是「容器還在跑嗎」，後者是「位址與憑證對嗎」。
    origin: ServiceOrigin
    base_url: str
    status: HealthStatus
    #: 實測值：版本號、索引站數量。UI 直接顯示，不翻譯。
    detail: str
    #: 失敗時服務回的原文（英文）。
    error: str
    checked_at: datetime | None
    last_ok_at: datetime | None
    failures: int
    #: 有連線資訊可以檢查。索引站那一步可跳過，所以它可能是 False。
    configured: bool
    #: 被改掉的建議偏好鍵（qBittorrent 專有）。有值就顯示「還原建議設定」。
    drift: tuple[str, ...]
    #: qBittorrent 把這台的 IP 封了（brief §20.2）。畫面照它說出下一步——改帳密沒有用。
    banned: bool
    #: 這台 Jellyfin 低於 12.0（brief §16.4、§20.9）。同上：下一步是升級，而升級不可逆。
    unsupported: bool


@dataclass(frozen=True, slots=True)
class UnknownTorrentView:
    """qBittorrent 上一個掛著 Berth 記號、而 Berth 沒有 Job 的 torrent（plan §3.2、票 10）。"""

    hash: str
    name: str
    category: str
    #: qBittorrent 自己的狀態字串，原樣（The Machine String Rule）。
    state: str


@dataclass(frozen=True, slots=True)
class PollerView:
    """`qbit_poller` 上一輪的結果（plan §3.2）。

    健康頁上它與四項檢查並排，因為它回答的是同一種問題：**現在還動得了嗎**。
    一個永遠連不上 qBittorrent 的迴圈不會讓任何一項變紅（那四項各自量的是別的東西），
    但下載列表會整片停住——而那正是使用者會來健康頁問的事。
    """

    checked_at: datetime | None
    #: 連續失敗次數。0 表示上一輪成功。
    failures: int
    #: 最後一次失敗時服務回的原文（英文）。
    error: str
    #: 有活躍 job 時 5 秒、否則 30 秒（plan §3.2）。畫面用它說「多久問一次」。
    interval_seconds: int
    unknown_torrents: tuple[UnknownTorrentView, ...]


@dataclass(frozen=True, slots=True)
class HealthReport:
    """`GET /api/health/detail` 的整份形狀：三個服務、所有 Route，加上下載迴圈。"""

    degraded: bool
    checked_at: datetime | None
    services: tuple[ServiceHealthView, ...]
    routes: tuple[RouteView, ...]
    #: 第四項：所有 Route 的總結。一條都沒有是 `unknown`。
    routes_status: HealthStatus
    poller: PollerView


async def read_health(session: AsyncSession) -> HealthReport:
    """上一輪的結果。**不連任何服務**——健康頁載入時看的是紀錄，不是又打一次每個服務。"""
    health = await read_settings(session, HealthSettings)
    setup = await read_settings(session, SetupSettings)
    indexer = await read_settings(session, IndexerSettings)
    #: 畫面顯示的位址就是檢查**真的連過去**的那一條，不是第 2 步探測時記下的那條。
    urls = {
        ServiceKind.JELLYFIN: (await read_settings(session, JellyfinSettings)).base_url,
        ServiceKind.QBITTORRENT: (await read_settings(session, QbittorrentSettings)).base_url,
        ServiceKind.PROWLARR: indexer.base_url,
    }
    return HealthReport(
        degraded=_degraded(health),
        checked_at=health.checked_at,
        services=tuple(
            _view(kind, health.services.get(kind) or ServiceHealth(), setup, indexer, urls[kind])
            for kind in ServiceKind
        ),
        routes=(await read_route_status(session)).routes,
        routes_status=health.routes,
        poller=await _poller(session),
    )


async def _poller(session: AsyncSession) -> PollerView:
    """下載迴圈上一輪的結果（`settings.poller`）。**不是**這四項檢查的一部分：
    它不連任何服務，只把迴圈自己記下來的東西讀出來。"""
    poller = await read_settings(session, PollerSettings)
    return PollerView(
        checked_at=poller.checked_at,
        failures=poller.failures,
        error=poller.error,
        interval_seconds=int(ACTIVE_INTERVAL.total_seconds()),
        unknown_torrents=tuple(
            UnknownTorrentView(hash=row.hash, name=row.name, category=row.category, state=row.state)
            for row in poller.unknown_torrents
        ),
    )


async def overall_status(session: AsyncSession) -> Status:
    """匿名的 `GET /api/health` 回的那一個字（plan §6）。

    只讀 `settings.health` 那一列：compose 的健康檢查每 30 秒打一次，不該為它去連四個地方。
    **還沒檢查過不是降級**——降級的意思是有東西已知壞了。
    """
    return "degraded" if _degraded(await read_settings(session, HealthSettings)) else "ok"


async def is_due(
    session: AsyncSession, *, now: datetime | None = None, interval: timedelta = CHECK_INTERVAL
) -> bool:
    """上一輪已經過了一個間隔（或從來沒跑過）。`health_checker` 每次醒來問它一次。"""
    health = await read_settings(session, HealthSettings)
    if health.checked_at is None:
        return True
    return (now or _utcnow()) - health.checked_at >= interval


async def check_health(
    session: AsyncSession, factory: ServiceClientFactory, *, now: datetime | None = None
) -> HealthReport:
    """跑完四項並記下結果（`health_checker` 每 5 分鐘一次，畫面上也有一顆按鈕）。"""
    moment = now or _utcnow()
    for kind in ServiceKind:
        await _record(session, kind, await _run(kind, session, factory), moment)

    health = await read_settings(session, HealthSettings)
    health.routes = await _check_routes(session, factory)
    health.checked_at = moment
    await write_settings(session, health)
    await session.commit()
    await _watch_conditions(session, factory, moment)
    return await read_health(session)


async def check_service(
    session: AsyncSession,
    factory: ServiceClientFactory,
    kind: ServiceKind,
    *,
    now: datetime | None = None,
) -> HealthReport:
    """設定頁的「測試連線」：只重測這一個服務（票 10）。

    **不順便重跑 Route 的檢查**：那一組會在 qBittorrent 上建 category、在媒體庫裡寫探測檔，
    使用者按的是「測一下這台連不連得上」，不是「再跑一次第 7 步」。
    """
    await _record(session, kind, await _run(kind, session, factory), now or _utcnow())
    await session.commit()
    return await read_health(session)


# --- 紀錄 ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Outcome:
    """一項檢查這一次的結果。時間與連續失敗次數由 `_record` 接上去。"""

    status: HealthStatus
    detail: str = ""
    error: str = ""
    configured: bool = True
    drift: tuple[str, ...] = ()
    #: qBittorrent 把這台的 IP 封了。**旗標而不是一句話**：原文由 `error` 帶著（服務說的），
    #: 而畫面要照這個事實挑一句 Berth 自己的下一步（PRODUCT 原則 4）。
    banned: bool = False
    #: 這台 Jellyfin 低於 12.0（brief §16.4、§20.9）。同上：原文說「幾版對幾版」，
    #: 而升級的那幾件事（先備份、移除第三方插件、升完完整掃描、降不回去）由畫面說。
    unsupported: bool = False


async def _record(
    session: AsyncSession, kind: ServiceKind, outcome: _Outcome, moment: datetime
) -> None:
    """把這一次的結果併進上一次的紀錄，然後就地 commit。

    逐項 commit 的理由與精靈第 7 步一樣：第二項炸了，第一項的結果仍然留得下來。
    """
    health = await read_settings(session, HealthSettings)
    previous = health.services.get(kind)
    health.services = {
        **health.services,
        kind: ServiceHealth(
            status=outcome.status,
            detail=outcome.detail,
            error=outcome.error,
            checked_at=moment,
            last_ok_at=(
                moment
                if outcome.status is HealthStatus.OK
                else (previous.last_ok_at if previous else None)
            ),
            failures=(
                (previous.failures if previous else 0) + 1
                if outcome.status is HealthStatus.FAILED
                else 0
            ),
            configured=outcome.configured,
            drift=list(outcome.drift),
            banned=outcome.banned,
            unsupported=outcome.unsupported,
        ),
    }
    await write_settings(session, health)
    await session.commit()


async def _run(kind: ServiceKind, session: AsyncSession, factory: ServiceClientFactory) -> _Outcome:
    """一項檢查，例外就地接住。

    `ServiceError` 是預期中的失敗（服務自己說的話），已經在各個 `_check_*` 裡翻成紅燈；
    這裡接的是**沒預料到的**那種——一個服務的 bug 不該讓另外三項今天都不檢查了。
    """
    try:
        return await _CHECKS[kind](session, factory)
    except Exception as exc:  # 迴圈裡的一項不能把整輪拖下水
        logger.exception("health check for %s failed unexpectedly", kind.value)
        return _Outcome(HealthStatus.FAILED, error=message(exc))


async def _check_routes(session: AsyncSession, factory: ServiceClientFactory) -> HealthStatus:
    try:
        await check_routes(session, factory)
    except Exception:  # 同上：Route 那一項炸了不該弄丟前三項的結果
        logger.exception("route health checks failed unexpectedly")
        return HealthStatus.FAILED
    return await routes_health(session)


async def _watch_conditions(
    session: AsyncSession, factory: ServiceClientFactory, moment: datetime
) -> None:
    """TVDB 與磁碟空間兩種 Issue（`services/health_issues.py`，M2 票 09c）。

    排在四項之後、各自的結果都 commit 了之後：它炸了不該弄丟那四項。
    """
    try:
        await watch_conditions(session, factory, now=moment)
    except Exception:  # 同 `_check_routes`：一個沒預料到的 bug 不該讓整輪的紀錄消失
        await session.rollback()
        logger.exception("TVDB and disk space checks failed unexpectedly")


# --- 逐項檢查 -----------------------------------------------------------


async def _check_jellyfin(session: AsyncSession, factory: ServiceClientFactory) -> _Outcome:
    """版本夠新、連得上，而且 Berth 那把 API key 還列得出媒體庫。

    列媒體庫不是多做的：`public_info` 匿名就回得出來，key 被撤銷時它照樣是綠的，而 M1 入庫
    要用的每一支端點都需要那把 key。

    **版本先看**（brief §16.4、§20.9）：低於 12.0 的伺服器上，同一集的兩個版本會是兩個重複的
    條目，而 Berth 不再為它裝插件。那不是「現在連不上」而是「這台不能用」，所以是紅燈加一個
    說得出下一步的旗標，不是警告。
    """
    settings = await read_settings(session, JellyfinSettings)
    if not settings.base_url:
        return _Outcome(HealthStatus.UNKNOWN, configured=False)

    client = factory.jellyfin(settings.base_url, token=settings.api_key)
    try:
        info = await client.public_info()
        if not info.supported:
            return _Outcome(
                HealthStatus.FAILED,
                detail=info.version,
                error=unsupported_message(info.version),
                unsupported=True,
            )
        libraries = await client.libraries()
    except ServiceError as exc:
        return _Outcome(HealthStatus.FAILED, error=message(exc))
    finally:
        await client.aclose()
    return _Outcome(HealthStatus.OK, detail=f"{info.version} · {len(libraries)} libraries")


async def _check_qbittorrent(session: AsyncSession, factory: ServiceClientFactory) -> _Outcome:
    """連得上、版本夠新，而且建議偏好還是建議值（brief §16.3）。"""
    settings = await read_settings(session, QbittorrentSettings)
    paths = await read_settings(session, PathSettings)
    if not settings.base_url:
        return _Outcome(HealthStatus.UNKNOWN, configured=False)

    client = factory.qbittorrent(settings.base_url)
    try:
        if settings.username:
            await client.login(settings.username, settings.password)
        version = await client.version()
        if not version.supported:
            floor = ".".join(str(part) for part in MIN_WEBAPI)
            return _Outcome(
                HealthStatus.FAILED,
                detail=f"{version.app} · Web API {version.webapi}",
                error=f"Web API {version.webapi} is older than {floor}",
            )
        preferences = await client.preferences()
    except IpBannedError as banned:
        # 原文照舊（它自己就說了發生什麼事），另外掛一個旗標讓畫面說得出下一步——
        # 改帳密沒有用，那是這一種與「帳密不對」唯一的差別（PRODUCT 原則 4）。
        # **一定要排在 `ServiceError` 前面**：它是 `AuthFailedError` 的子類。
        return _Outcome(HealthStatus.FAILED, error=message(banned), banned=True)
    except ServiceError as exc:
        return _Outcome(HealthStatus.FAILED, error=message(exc))
    finally:
        await client.aclose()

    return _Outcome(
        HealthStatus.OK,
        detail=f"{version.app} · Web API {version.webapi}",
        drift=drifted_keys(preferences, paths),
    )


async def _check_indexer(session: AsyncSession, factory: ServiceClientFactory) -> _Outcome:
    """索引站還搜得動。第 5 步可以跳過，所以沒填位址是 `unknown` 而不是紅燈。"""
    settings = await read_settings(session, IndexerSettings)
    if not settings.base_url:
        return _Outcome(HealthStatus.UNKNOWN, configured=False)

    step = await probe_indexer(
        factory, IndexerKind(settings.kind), settings.base_url, settings.api_key
    )
    if step.status is StepStatus.FAILED:
        return _Outcome(HealthStatus.FAILED, detail=step.detail, error=step.error)
    return _Outcome(HealthStatus.OK, detail=step.detail)


_CHECKS: dict[ServiceKind, Callable[[AsyncSession, ServiceClientFactory], Awaitable[_Outcome]]] = {
    ServiceKind.JELLYFIN: _check_jellyfin,
    ServiceKind.QBITTORRENT: _check_qbittorrent,
    ServiceKind.PROWLARR: _check_indexer,
}

#: 少一項就在 import 時炸，而不是等使用者開健康頁才發現那一格是空的。
assert set(_CHECKS) == set(ServiceKind), "every service needs a health check"


# --- 攤平 ---------------------------------------------------------------


def _view(
    kind: ServiceKind,
    health: ServiceHealth,
    setup: SetupSettings,
    indexer: IndexerSettings,
    base_url: str,
) -> ServiceHealthView:
    return ServiceHealthView(
        kind=kind,
        origin=_origin(kind, setup, indexer),
        base_url=base_url,
        status=health.status,
        detail=health.detail,
        error=health.error,
        checked_at=health.checked_at,
        last_ok_at=health.last_ok_at,
        failures=health.failures,
        configured=health.configured,
        drift=tuple(health.drift),
        banned=health.banned,
        unsupported=health.unsupported,
    )


def _origin(kind: ServiceKind, setup: SetupSettings, indexer: IndexerSettings) -> ServiceOrigin:
    """套件內還是既有——沿用第 2 步的判定。

    Torznab 是使用者自己貼的端點，與 compose 裡那台 Prowlarr 無關，所以它一律是既有
    （與 `services/indexer.py` 的規則相同）。
    """
    if kind is ServiceKind.PROWLARR and indexer.kind == IndexerKind.TORZNAB.value:
        return ServiceOrigin.EXISTING
    probe = setup.services.get(kind)
    return probe.origin if probe is not None else ServiceOrigin.EXISTING


def _degraded(health: HealthSettings) -> bool:
    """任何一項**已知**壞了就是降級；`unknown` 不算（還沒檢查過、或使用者跳過了那一步）。"""
    return health.routes is HealthStatus.FAILED or any(
        row.status is HealthStatus.FAILED for row in health.services.values()
    )


def _utcnow() -> datetime:
    return datetime.now(UTC)
