"""設定精靈的命令（plan §9.3）。本檔是服務頁的「選來源、測試」、擁有者與步序本身；各頁在
`services/` 的鄰居。

每個命令都冪等：精靈的每一步之後都能在設定頁重跑，狀態全部在 `settings.setup` 那一列，
所以重跑只是覆寫同一份值，不會長出第二份資料。

**來源由使用者選，不偵測**（brief §16.3、§19 2026-09-29，M4 票 15）：Jellyfin、qBittorrent、
Prowlarr 各一頁，使用者選「套件內」或「既有」，選擇存在 `settings.setup.choices`，從此「套件內 /
既有」由它決定。選之前 Berth 不對那個服務發任何請求；選完當場測一次。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import (
    AuthFailedError,
    ProtocolMismatchError,
    SchemeMismatchError,
    SchemeMissingError,
    ServiceBusyError,
    ServiceError,
    ServiceNotDeployedError,
    ServiceUnavailableError,
)
from berth.adapters.prowlarr import ProwlarrClient
from berth.adapters.qbittorrent import IpBannedError
from berth.domain import (
    PROWLARR_LOGIN_STEP,
    ChoiceRefusal,
    ConnectionReason,
    ConnectionState,
    IndexerKind,
    JellyfinStep,
    OwnerRefusal,
    QbittorrentStep,
    ServiceKind,
    ServiceOrigin,
    StepFailure,
    StepStatus,
)
from berth.models import (
    IndexerSettings,
    JellyfinSettings,
    PathSettings,
    QbittorrentSettings,
    ServiceChoice,
    ServiceTest,
    SetupOwner,
    SetupSettings,
    SetupStep,
)
from berth.services.auth import SignedIn, open_session
from berth.services.clients import BundledServices, HostResolver, ServiceClientFactory
from berth.services.commands import Effect, command
from berth.services.indexer import (
    existing_prowlarr_step,
    instance_login,
    note_instance_login,
    outdated_step,
)
from berth.services.jellyfin import (
    DEFAULT_STARTUP,
    JellyfinStartup,
    JellyfinTarget,
    claim_jellyfin,
    libraries_built,
    remembered_startup,
)
from berth.services.routes import forget_route_checks, routes_ready
from berth.services.settings import read_settings, update_settings
from berth.services.steps import message
from berth.services.tmdb import tmdb_verified

#: 套件內那一台還在啟動時的輪詢上限（plan §9.3〈服務頁的共同形狀〉）。逾時後使用者可重測，
#: 不是永遠轉圈。
TEST_WINDOW = timedelta(minutes=2)

#: 精靈的頁序（plan §9.3）。頁 1 是 Jellyfin，它的管理員就是擁有者（M4 票 06）；每一頁「做完了沒」
#: 由它自己的狀態導出（`_current_step`），不存游標。媒體庫與路徑排在 qBittorrent 之後、Prowlarr 之前
#: （票 06d）：它只依賴前兩頁，而掛載設錯是最常卡住的地方，越早知道越好。
STEP_JELLYFIN = 1
STEP_QBITTORRENT = 2
STEP_ROUTES = 3
STEP_INDEXER = 4
STEP_TMDB = 5
STEP_COMPLETE = 6


@dataclass(frozen=True, slots=True)
class ServiceConnection:
    """選「既有」時使用者填的連線資訊。每個服務只用得到其中幾個欄位；套件內的只可能帶 Prowlarr
    的 key（唯讀掛載讀不到時使用者貼的，plan §9.2）。"""

    base_url: str = ""
    api_key: str = ""
    username: str = ""
    password: str = ""


@dataclass(frozen=True, slots=True)
class ServiceView:
    """一個服務的選擇與最後一次測試。還沒測過時 `state` 與 `reason` 是 `None`。"""

    kind: ServiceKind
    origin: ServiceOrigin
    base_url: str
    state: ConnectionState | None
    reason: ConnectionReason | None
    #: 實測值：Jellyfin 與 qBittorrent 的版本、Prowlarr 的索引站數量。
    detail: str
    #: Jellyfin 答的 ServerId（`ServiceTest.server_id`）；頁 1 的表單帶著它送出（M4 票 28）。
    server_id: str
    #: 沒連上時服務回的原文（英文）。
    error: str
    #: 這個位址上連續幾次帳密不被接受（`ServiceTest.auth_failures`）。
    auth_failures: int
    #: 套件內那一台還在啟動時，這一輪已經等了幾秒。
    waited_seconds: int


@dataclass(frozen=True, slots=True)
class SetupStatus:
    """`GET /api/setup/status` 的整份形狀。"""

    completed: bool
    current_step: int
    #: 擁有者的 Jellyfin 名字。空字串就是還沒有擁有者（頁 1）。
    owner: str
    #: 頁 1 的表單是登入而不是建立：那一台 Jellyfin 已經有管理員（跑過自己的初始精靈，或上一次
    #: Berth 已經替它建好了）。**選套件內或既有不影響這一條**（plan §9.3「表單跟著那一台的
    #: 狀態走」）。
    owner_signs_in: bool
    #: 頁 1 上一次送給還沒初始化的那一台的語言與遠端存取（M4 票 29）：初始化中途失敗時，建立表單
    #: 照它重填。還沒送過、送的時候那一台已經初始化過、或之後換了一台是 `None`。
    jellyfin_startup: JellyfinStartup | None
    #: 選過的服務，照 `ServiceKind` 的順序。沒選的不在裡面。
    services: tuple[ServiceView, ...]
    window_seconds: int


class ChoiceLockedError(Exception):
    """服務頁的選擇不成立（`ChoiceRefusal`），什麼都沒存。都是擁有者成立之後的 Jellyfin：擁有者是
    那一台上的帳號，換一台 Jellyfin 等於換擁有者（shape 時使用者拍板）。所以來源換不了；位址換得了，
    但只能換到同一台（ServerId 相同，brief §20.15、M4 票 18）。"""

    def __init__(self, reason: ChoiceRefusal, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else str(reason))
        self.reason = reason
        self.detail = detail


async def is_setup_complete(session: AsyncSession) -> bool:
    """精靈跑完了沒。這一個位元是匿名可讀的（`GET /api/health`）：前端要在**還沒有人
    登入得了**的時候就決定該畫精靈還是登入頁，而精靈未完成時本來就整組匿名開放。
    """
    return (await read_settings(session, SetupSettings)).completed


async def read_status(session: AsyncSession) -> SetupStatus:
    """目前的頁與每個服務的選擇。不做任何測試。"""
    return await _read(session, now=_utcnow())


async def complete_setup(session: AsyncSession) -> SetupStatus:
    """完成頁：寫下 `settings.setup.completed`，精靈結束（plan §9.3 頁 6）。

    寫下去之後 `/` 不再導向精靈、`setup/*` 由設定頁接手（票 06i）；門禁早在擁有者成立時就關上了
    （`owner_established`）。在寫之前要確定不可跳的那幾頁真的做完了——媒體庫與路徑、TMDB 在這裡
    再擋一次，因為使用者回得去把它們弄壞（plan §9.3、票 02b）。
    """
    setup = await read_settings(session, SetupSettings)
    # 照頁序問：兩頁都沒做完時，先把人送回前面那一頁。
    if not await routes_ready(session):
        raise ValueError("finish page 3 first: every library route has to pass its checks")
    if not tmdb_verified(setup):
        raise ValueError("finish page 5 first: TMDB needs a credential that passes its test")

    def record(latest: SetupSettings) -> None:
        latest.completed = True

    await update_settings(session, SetupSettings, record)
    return await _read(session, now=_utcnow())


async def _read(session: AsyncSession, *, now: datetime) -> SetupStatus:
    """整份狀態。頁是導出的，而頁 3 的依據在 `routes` 表與媒體庫快照，所以要多讀它們。"""
    setup = await read_settings(session, SetupSettings)
    paths = await read_settings(session, PathSettings)
    berthed = await routes_ready(session) and libraries_built(setup, paths.library_root)
    return _status(setup, now=now, berthed=berthed)


class OwnerRejectedError(Exception):
    """頁 1 沒成立（`OwnerRefusal`）。`detail` 是 Jellyfin 那一步的原文，說不出就是空字串。"""

    def __init__(self, reason: OwnerRefusal, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else str(reason))
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True, slots=True)
class ClaimedOwner:
    status: SetupStatus
    #: 擁有者的 Berth session。token 只在這裡出現一次（`auth.SignedIn`）。
    signed_in: SignedIn


async def claim_owner(
    session: AsyncSession,
    factory: ServiceClientFactory,
    *,
    target: JellyfinTarget,
    username: str,
    password: str,
    startup: JellyfinStartup = DEFAULT_STARTUP,
) -> ClaimedOwner:
    """頁 1：Jellyfin 的管理員就是 Berth 的擁有者（brief §11、§19 2026-09-26，M4 票 06）。

    照 Seerr：那一台還沒跑過初始精靈就由 Berth 以這組帳密建立管理員，已經有管理員就要它登入；
    兩者都換 Berth 的 API key（`jellyfin.claim_jellyfin`）。選套件內或既有不影響走哪一條
    （M4 票 15）。
    成立的那一刻發 Berth session，之後精靈的每一支都要登入（`api/gate.py`）。帳密只交給 Jellyfin，
    不存下來。

    **誰先到誰建立**：擁有者成立之前這一支匿名可達，與 Jellyfin 自己的啟動精靈、Seerr 相同；
    成立之後它與其他精靈端點一樣要管理員的 session（plan §9.3 頁 1），**而且不再重建擁有者**
    （`OWNER_EXISTS`，M4 票 18）：換 API key 的重新登入是另一支（`jellyfin.connect_jellyfin`）。

    `startup` 只用在還沒初始化的那一台（建立管理員那一條）：語言與地區、遠端存取（M4 票 18）。

    **帳密只送到畫面上測過的那一台**（`target`，M4 票 28）：擁有者成立之前頁 1 匿名可改，存下的
    位址或那一台的 ServerId 與 `target` 不同就是有人在填表時換了目標——`TARGET_CHANGED`，Jellyfin
    一個請求都不發。比對過之後序列仍釘在 `target` 上（`jellyfin.claim_jellyfin`），寫擁有者時再
    確認一次。
    """
    setup = await read_settings(session, SetupSettings)
    if setup.owner_established():
        raise OwnerRejectedError(OwnerRefusal.OWNER_EXISTS)
    if not username.strip() or not password:
        raise OwnerRejectedError(OwnerRefusal.INVALID_CREDENTIALS)
    choice = setup.choices.get(ServiceKind.JELLYFIN)
    if choice is None or choice.test is None or choice.test.state is not ConnectionState.OK:
        raise OwnerRejectedError(OwnerRefusal.JELLYFIN_UNRESOLVED)
    if not _aimed_at(choice, target):
        raise OwnerRejectedError(OwnerRefusal.TARGET_CHANGED)

    claim = await claim_jellyfin(
        session,
        factory,
        username=username.strip(),
        password=password,
        target=target,
        startup=startup,
    )
    if claim.auth is None:
        raise OwnerRejectedError(claim.refusal or OwnerRefusal.JELLYFIN_FAILED, claim.detail)

    auth = claim.auth

    def record(latest: SetupSettings) -> None:
        if latest.owner_established():
            # 兩個人同時送頁 1：先寫進去的那一個是擁有者，後到的不蓋掉他。
            raise OwnerRejectedError(OwnerRefusal.OWNER_EXISTS)
        chosen = latest.choices.get(ServiceKind.JELLYFIN)
        # 序列跑的那一分鐘裡目標被換了：擁有者不落在一台頁 1 已經不選的 Jellyfin 上。只比位址：
        # ServerId 剛由序列的第一步對過，而同一時間的重測沒連上會把存下的那一格清成空字串。
        if chosen is None or chosen.base_url != target.base_url:
            raise OwnerRejectedError(OwnerRefusal.TARGET_CHANGED)
        latest.owner = SetupOwner(
            jellyfin_user_id=auth.user_id, name=auth.name, jellyfin_server_id=claim.server_id
        )
        if chosen.test is not None:
            # 那一台現在有管理員了：測試那一條不該還說「還沒跑過初始精靈」。
            latest.choices = {
                **latest.choices,
                ServiceKind.JELLYFIN: chosen.model_copy(
                    update={
                        "test": chosen.test.model_copy(
                            update={"reason": ConnectionReason.SETUP_COMPLETED}
                        )
                    }
                ),
            }

    await update_settings(session, SetupSettings, record)
    # 擁有者先落地、session 後發：`open_session` 失敗的話擁有者已成立，從登入頁用同一組帳密進來。
    signed_in = await open_session(session, auth)
    return ClaimedOwner(status=await _read(session, now=_utcnow()), signed_in=signed_in)


def _aimed_at(choice: ServiceChoice, target: JellyfinTarget) -> bool:
    """頁 1 的表單送的是不是 Berth 現在要連的那一台：位址與上一次測試答的 ServerId 都一樣。

    上一次測試沒記到 ServerId（票 28 之前測的）不算：比不出是不是同一台，重新測試就有了。
    """
    tested = choice.test.server_id if choice.test is not None else ""
    return bool(tested) and (choice.base_url, tested) == (target.base_url, target.server_id)


async def is_owner_established(session: AsyncSession) -> bool:
    return (await read_settings(session, SetupSettings)).owner_established()


async def choose_service(
    session: AsyncSession,
    factory: ServiceClientFactory,
    bundled: BundledServices,
    kind: ServiceKind,
    origin: ServiceOrigin,
    connection: ServiceConnection | None = None,
    *,
    now: datetime | None = None,
) -> SetupStatus:
    """服務頁的二選一：存下選擇與連線資訊，然後測一次（plan §9.3〈服務頁的共同形狀〉）。

    **測不過也存**：使用者要能改一個欄位再按一次，而不是每次重打整份表單。

    **換了一台就重做那一頁**（shape 時使用者拍板）：來源或位址變了，那一頁的結果清掉——它們說的是
    原本那一台。Berth 寫進原本那一台的東西不撤回。qBittorrent 換了，所有 Route 的檢查一起作廢：
    分類建在原本那一台上（`routes.forget_route_checks`）。

    **擁有者成立之後的 Jellyfin**（`ChoiceLockedError`，什麼都不存）：來源換不了；位址換得了，
    但新位址要先回答它是**同一台**（`_same_jellyfin`，M4 票 18）——那一頁因此不重做。設定頁的連線區
    走的也是這一支。
    """
    moment = now or _utcnow()
    connection = connection or ServiceConnection()
    setup = await read_settings(session, SetupSettings)
    previous = setup.choices.get(kind)
    if (
        kind is ServiceKind.JELLYFIN
        and setup.owner_established()
        and previous is not None
        and previous.origin is not origin
    ):
        raise ChoiceLockedError(ChoiceRefusal.JELLYFIN_OWNED)
    if origin is ServiceOrigin.BUNDLED:
        base_url = bundled.targets[kind]
    else:
        base_url = connection.base_url
        if not base_url:
            raise ValueError("an existing service needs its address")

    moved = previous is not None and not previous.is_at(origin, base_url)
    tested: _Outcome | None = None
    if (
        moved
        and previous is not None
        and kind is ServiceKind.JELLYFIN
        and setup.owner_established()
    ):
        tested = await _same_jellyfin(session, factory, setup, previous.base_url, base_url)
    elif moved and kind is ServiceKind.QBITTORRENT:
        await forget_route_checks(session)
    await _remember_connection(session, kind, origin, base_url, connection, bundled)

    def record(latest: SetupSettings) -> None:
        current = latest.choices.get(kind)
        # 同一個位址改帳密再測：上一次的結果留著，連錯的次數才接得下去（qBittorrent 數的是
        # 這台的 IP）。
        kept = current.test if current is not None and current.is_at(origin, base_url) else None
        if moved and tested is None:
            _start_over(latest, kind)
        latest.choices = {
            **latest.choices,
            kind: ServiceChoice(origin=origin, base_url=base_url, test=kept),
        }

    await update_settings(session, SetupSettings, record)
    return await _test_and_record(session, factory, kind, restart=True, now=moment, tested=tested)


async def retest_service(
    session: AsyncSession,
    factory: ServiceClientFactory,
    bundled: BundledServices,
    kind: ServiceKind,
    *,
    restart: bool = False,
    now: datetime | None = None,
) -> SetupStatus:
    """用存下來的選擇再測一次：出問題那一頁的「重新測試」（取代「重新偵測這個服務」），以及套件內
    那一台還在啟動時前端每 3 秒的那一次。`restart=True` 是使用者按的，2 分鐘重新算。

    **套件內 Prowlarr 每次都重讀掛載的 key**（M4 票 27）：在 Prowlarr 重新產生 key 之後，存下的
    那一把就不被接受了，而重新測試是畫面上唯一的出口。掛載讀不到時不動存下的——那是使用者貼的。
    """
    setup = await read_settings(session, SetupSettings)
    choice = setup.choices.get(kind)
    if choice is None:
        raise ValueError(f"choose where {kind} comes from first")
    mounted = bundled.prowlarr_api_key
    if kind is ServiceKind.PROWLARR and choice.origin is ServiceOrigin.BUNDLED and mounted:

        def remount(indexer: IndexerSettings) -> None:
            indexer.api_key = mounted

        await update_settings(session, IndexerSettings, remount)
    return await _test_and_record(session, factory, kind, restart=restart, now=now or _utcnow())


@command(Effect.READ)
async def resolve_bundled(
    bundled: BundledServices, resolver: HostResolver
) -> dict[ServiceKind, bool]:
    """套件內三個主機名各自解不解得到（M4 票 30，brief §19 2026-10-01）。

    解不到就是那個服務不在這套 compose 裡（或停著）：服務頁的「套件內」卡片照它加註。**只查 DNS**，
    不造任何服務的 client——選之前不對服務發請求（brief §19）不變。
    """
    kinds = list(bundled.targets)
    answers = await asyncio.gather(
        *(resolver.resolves(urlsplit(bundled.targets[kind]).hostname or "") for kind in kinds)
    )
    return dict(zip(kinds, answers, strict=True))


async def _test_and_record(
    session: AsyncSession,
    factory: ServiceClientFactory,
    kind: ServiceKind,
    *,
    restart: bool,
    now: datetime,
    tested: _Outcome | None = None,
) -> SetupStatus:
    """測一次並記下結果。`tested` 是呼叫端剛對同一個位址測過的那一次，不再敲第二次。

    **記的時候重讀、只改這個服務那一段**（M4 票 23）：一次測試短則幾秒，對暫停中的容器實測要
    30 秒上下，而啟動中的輪詢每 3 秒一次，這段時間裡別的頁、別的分頁可能已經寫進同一組設定。
    測的那一台已經不是現在選的（使用者換了位址），結果說的是原本那一台，不記。
    """
    tested_choice = (await read_settings(session, SetupSettings)).choices[kind]
    outcome = tested or await _test_connection(session, factory, kind)

    def record(latest: SetupSettings) -> None:
        choice = latest.choices.get(kind)
        if choice is None or not choice.is_at(tested_choice.origin, tested_choice.base_url):
            return
        test = _settle(outcome, choice, restart=restart, now=now)
        latest.choices = {**latest.choices, kind: choice.model_copy(update={"test": test})}
        if latest.owner_established() and outcome.server_id and not latest.owner.jellyfin_server_id:
            # 票 18 之前成立的擁有者沒記 ServerId：這一次回答的那一台就是它，之後照樣擋另一台。
            latest.owner = latest.owner.model_copy(update={"jellyfin_server_id": outcome.server_id})
        if kind is ServiceKind.PROWLARR and choice.origin is ServiceOrigin.EXISTING:
            # 既有 Prowlarr 這一頁是「連得上、而且有站」（M4 票 20）：它就是這一頁的結果
            # （`_indexer_settled`）。
            latest.indexer.steps = [_existing_indexer_step(test)]
            latest.indexer.skipped = False
        elif kind is ServiceKind.PROWLARR:
            note_instance_login(latest, outcome.interface_user)

    await update_settings(session, SetupSettings, record)
    return await _read(session, now=now)


def _start_over(setup: SetupSettings, kind: ServiceKind) -> None:
    """換了一台：那一頁的結果說的是原本那一台，清掉重做。qBittorrent 的 Route 檢查由呼叫端作廢
    （`routes.forget_route_checks`）：它們在 `routes` 表，不在這一組設定裡。"""
    if kind is ServiceKind.JELLYFIN:
        setup.jellyfin.steps = []
        setup.jellyfin.libraries = []
        # 重填的是同一台的重試；另一台的建立表單不帶上一台的選擇（M4 票 29）。
        setup.jellyfin.startup = None
    elif kind is ServiceKind.QBITTORRENT:
        setup.qbittorrent.steps = []
        setup.qbittorrent.web_ui_username = ""
        setup.qbittorrent.web_ui_password_hash = ""
    else:
        setup.indexer.steps = []
        setup.indexer.skipped = False
        setup.indexer.web_ui_username = ""
        setup.indexer.web_ui_password_hash = ""


async def _remember_connection(
    session: AsyncSession,
    kind: ServiceKind,
    origin: ServiceOrigin,
    base_url: str,
    connection: ServiceConnection,
    bundled: BundledServices,
) -> None:
    """連線資訊寫進它平常住的 `settings.services.*`，其餘的命令與背景迴圈從同一個地方讀。

    套件內 qBittorrent 沒有帳密：Berth 連它靠免密白名單（plan §9.2），Berth 替它設的介面登入
    只記雜湊、不拿來連（M4 票 15）。
    """
    if kind is ServiceKind.JELLYFIN:

        def remember_jellyfin(jellyfin: JellyfinSettings) -> None:
            jellyfin.base_url = base_url

        await update_settings(session, JellyfinSettings, remember_jellyfin)
    elif kind is ServiceKind.QBITTORRENT:
        existing = origin is ServiceOrigin.EXISTING

        def remember_qbittorrent(qbittorrent: QbittorrentSettings) -> None:
            qbittorrent.base_url = base_url
            qbittorrent.username = connection.username if existing else ""
            qbittorrent.password = connection.password if existing else ""

        await update_settings(session, QbittorrentSettings, remember_qbittorrent)
    else:

        def remember_prowlarr(indexer: IndexerSettings) -> None:
            indexer.kind = IndexerKind.PROWLARR.value
            indexer.base_url = base_url
            # 套件內：使用者貼的優先，否則是掛載讀到的（plan §9.2）。
            indexer.api_key = connection.api_key or (
                bundled.prowlarr_api_key if origin is ServiceOrigin.BUNDLED else ""
            )

        await update_settings(session, IndexerSettings, remember_prowlarr)


@dataclass(frozen=True, slots=True)
class _Outcome:
    reason: ConnectionReason
    detail: str = ""
    #: 連上了。沒連上的再分「可能還在啟動」（`transient`）與當場就有結論的。
    ok: bool = False
    transient: bool = False
    #: Jellyfin 說了它是哪一台（`/System/Info/Public` 的 `Id`，brief §20.15）。沒問到、或不是
    #: Jellyfin 的是空字串。
    server_id: str = ""
    #: 沒連上時的原文（英文），收進畫面的「技術細節」。
    error: str = ""
    #: 套件內 Prowlarr 自己設過的介面帳號（M4 票 27）；沒設過、或不是那一台是空字串。
    interface_user: str = ""


async def _interface_user(prowlarr: ProwlarrClient) -> str:
    """套件內 Prowlarr 自己設過的介面帳號（M4 票 27）。只是順便讀：讀不到不讓連線測試變紅，
    登入那一條照舊等「加入」或「設定介面登入」。"""
    try:
        return instance_login(await prowlarr.host_config())
    except ServiceError:
        return ""


async def _test_connection(
    session: AsyncSession, factory: ServiceClientFactory, kind: ServiceKind
) -> _Outcome:
    """用存下來的連線資訊連一次那個服務。只讀，不寫任何東西。"""
    if kind is ServiceKind.JELLYFIN:
        jellyfin = await read_settings(session, JellyfinSettings)
        setup = await read_settings(session, SetupSettings)
        return await _test_jellyfin(factory, jellyfin.base_url, setup, api_key=jellyfin.api_key)

    if kind is ServiceKind.QBITTORRENT:
        settings = await read_settings(session, QbittorrentSettings)
        qbittorrent = factory.qbittorrent(settings.base_url)

        async def qbittorrent_test() -> _Outcome:
            if settings.username:
                await qbittorrent.login(settings.username, settings.password)
            version = await qbittorrent.version()
            if not version.supported:
                # 版本在測連線時就擋（M4 票 21，與 Jellyfin、Prowlarr 同一個時機）：原本這裡是綠燈、
                # 頁 2 的泊位卡卻是紅的「太舊」，同一個畫面兩種顏色。
                return _Outcome(reason=ConnectionReason.VERSION_UNSUPPORTED, detail=version.app)
            return _Outcome(
                reason=ConnectionReason.CONNECTED,
                detail=f"{version.app} · Web API {version.webapi}",
                ok=True,
            )

        try:
            return await _classified(qbittorrent_test)
        finally:
            await qbittorrent.aclose()

    indexer = await read_settings(session, IndexerSettings)
    bundled = (await read_settings(session, SetupSettings)).origin_of(
        ServiceKind.PROWLARR
    ) is ServiceOrigin.BUNDLED
    prowlarr = factory.prowlarr(indexer.base_url, indexer.api_key)

    async def prowlarr_test() -> _Outcome:
        if not indexer.api_key:
            # 唯讀掛載與環境變數都沒有，使用者也還沒貼：就地給貼 key 的欄位（plan §9.2）。
            # **先問它在不在**（匿名的 `/ping`，M4 票 25）：只有 Berth 時根本沒有那個容器，該說的
            # 是主機名解不到，不是 key——貼了 key 才說出真正原因等於白貼一次。
            await prowlarr.ping()
            return _Outcome(reason=ConnectionReason.API_KEY_MISSING)
        # 有 key 時不問 `/ping`：1.3.2 之前沒有它，版本就說不出來了（`indexer.probe_indexer`，
        # M4 票 20）。
        status = await prowlarr.status()
        if not status.supported:
            # 等不會好，所以不是 `transient`：套件內的那一台也當場紅（M4 票 17）。
            return _Outcome(reason=ConnectionReason.VERSION_UNSUPPORTED, detail=status.version)
        indexers = await prowlarr.indexers()
        # 套件內那一台自己就有介面登入（重裝保留它的 config）：一起讀，記下來那一條就有結論
        # （M4 票 27）。既有的那一台的 `config/host` 不讀（M4 票 20）。
        user = await _interface_user(prowlarr) if bundled else ""
        return _Outcome(
            reason=ConnectionReason.CONNECTED,
            detail=str(len(indexers)),
            ok=True,
            interface_user=user,
        )

    try:
        return await _classified(prowlarr_test)
    finally:
        await prowlarr.aclose()


async def _test_jellyfin(
    factory: ServiceClientFactory, base_url: str, setup: SetupSettings, *, api_key: str
) -> _Outcome:
    """Jellyfin 的測試：它是哪一台、版本夠不夠新（brief §16.4）；擁有者成立之後再問兩件事——是不是
    擁有者那一台（ServerId，brief §20.15）、Berth 的 key 它還收不收（M4 票 18）。

    版本在這裡就擋，不等到登入：10.x 原本在測試時是綠燈、到登入才 502，表單填完才知道白填了。
    """
    client = factory.jellyfin(base_url)
    owned = setup.owner_established()
    recorded = setup.owner.jellyfin_server_id

    async def test() -> _Outcome:
        info = await client.public_info()
        if owned and recorded and info.server_id != recorded:
            return _Outcome(
                reason=ConnectionReason.OTHER_SERVER,
                detail=info.server_name,
                server_id=info.server_id,
            )
        if not info.supported:
            # 等不會好，所以不是 `transient`：套件內的那一台也當場紅（同 Prowlarr，M4 票 17）。
            return _Outcome(
                reason=ConnectionReason.VERSION_UNSUPPORTED,
                detail=info.version,
                server_id=info.server_id,
            )
        if owned and api_key:
            client.use_token(api_key)
            try:
                # `/Auth/Keys` 要管理員憑證：答得出來，這一把就還是管理員級的 key。
                await client.api_keys()
            except AuthFailedError:
                # 同一台、key 被撤了：擁有者重新登入換一把（`jellyfin.connect_jellyfin`）。
                return _Outcome(
                    reason=ConnectionReason.AUTH_REQUIRED,
                    detail=info.version,
                    server_id=info.server_id,
                )
        reason = (
            ConnectionReason.SETUP_COMPLETED
            if info.startup_wizard_completed
            else ConnectionReason.SETUP_PENDING
        )
        return _Outcome(reason=reason, detail=info.version, ok=True, server_id=info.server_id)

    try:
        return await _classified(test)
    finally:
        await client.aclose()


async def _same_jellyfin(
    session: AsyncSession,
    factory: ServiceClientFactory,
    setup: SetupSettings,
    previous_url: str,
    base_url: str,
) -> _Outcome:
    """擁有者成立之後換位址：新位址要先回答它是同一台，不然拒絕、什麼都不存（M4 票 18）。

    **連不上也不存**：認不出是不是同一台，而存下去的話每個人的登入都會打到那個位址。回的是這一次
    測試，存下之後不必再敲第二次。

    票 18 之前成立的擁有者沒記 ServerId：先問原本那一台是誰、記在 `setup` 上，再比新的。存下來的是
    回傳的那一次測試的 ServerId（`_test_and_record`）：過得了這裡就是同一台。
    原本那一台也問不到就認不出，一樣不存——不能拿新位址自己的回答當標準。
    """
    if not setup.owner.jellyfin_server_id:
        known = await _test_jellyfin(factory, previous_url, setup, api_key="")
        if not known.server_id:
            raise ChoiceLockedError(ChoiceRefusal.UNVERIFIED, known.reason.value)
        setup.owner = setup.owner.model_copy(update={"jellyfin_server_id": known.server_id})
    api_key = (await read_settings(session, JellyfinSettings)).api_key
    outcome = await _test_jellyfin(factory, base_url, setup, api_key=api_key)
    if outcome.reason is ConnectionReason.OTHER_SERVER:
        raise ChoiceLockedError(ChoiceRefusal.OTHER_SERVER, outcome.detail)
    if not outcome.server_id:
        raise ChoiceLockedError(ChoiceRefusal.UNVERIFIED, outcome.reason.value)
    return outcome


async def _classified(test: Callable[[], Awaitable[_Outcome]]) -> _Outcome:
    """把 adapter 的錯誤翻成理由。

    解不到與連不上必須分開：套件內的主機名解不到代表那個服務不在 compose 裡，該說出怎麼把它加回
    `COMPOSE_PROFILES`；連不上只是容器還在啟動，該繼續等到輪詢上限。**協定不符也先等**（票 06g）：
    啟動途中的服務會回不像它自己的東西（實測 Jellyfin 起來後第 11 秒）。
    """
    try:
        return await test()
    except ServiceNotDeployedError as exc:
        return _Outcome(reason=ConnectionReason.NOT_DEPLOYED, error=message(exc))
    except ServiceUnavailableError as exc:
        return _Outcome(reason=ConnectionReason.UNREACHABLE, transient=True, error=message(exc))
    except ServiceBusyError as exc:
        # 連得上、是對的服務，但還在載入（Jellyfin 的 503）：與連不上一樣等到輪詢上限。
        return _Outcome(reason=ConnectionReason.STARTING, transient=True, error=message(exc))
    except IpBannedError as exc:
        # `AuthFailedError` 的子類，所以**一定要排在它前面**——被封的那一台會照樣回 403，
        # 而「要帳密」與「被封了」的下一步完全不同（票 10、plan T1.9 第四條）。
        return _Outcome(reason=ConnectionReason.IP_BANNED, error=message(exc))
    except AuthFailedError as exc:
        return _Outcome(reason=ConnectionReason.AUTH_REQUIRED, error=message(exc))
    except ProtocolMismatchError as exc:
        return _Outcome(
            reason=ConnectionReason.PROTOCOL_MISMATCH, transient=True, error=message(exc)
        )
    except SchemeMismatchError as exc:
        # 等不會好：位址本身寫錯了（M4 票 25）。
        return _Outcome(reason=ConnectionReason.SCHEME_MISMATCH, error=message(exc))
    except SchemeMissingError as exc:
        return _Outcome(reason=ConnectionReason.SCHEME_MISSING, error=message(exc))


def _settle(
    outcome: _Outcome, choice: ServiceChoice, *, restart: bool, now: datetime
) -> ServiceTest:
    """一次測試的結果。只有套件內的那一台會「等」：使用者自己填的位址當場就給結論，不該給他一個
    永遠不會好的倒數。等超過上限就逾時；協定不符例外——過了上限還是它，就是主機名上真的是別的東西。
    """
    failures = _auth_failures(outcome, choice.test)
    if outcome.ok:
        state = ConnectionState.OK
    elif not outcome.transient or choice.origin is ServiceOrigin.EXISTING:
        state = ConnectionState.FAILED
    else:
        previous = choice.test
        since = (
            previous.waiting_since
            if previous is not None and previous.waiting_since is not None and not restart
            else now
        )
        if now - since <= TEST_WINDOW:
            return ServiceTest(
                state=ConnectionState.WAITING,
                reason=outcome.reason,
                server_id=outcome.server_id,
                error=outcome.error,
                checked_at=now,
                waiting_since=since,
            )
        state = (
            ConnectionState.FAILED
            if outcome.reason is ConnectionReason.PROTOCOL_MISMATCH
            else ConnectionState.TIMEOUT
        )
    return ServiceTest(
        state=state,
        reason=outcome.reason,
        detail=outcome.detail,
        server_id=outcome.server_id,
        error=outcome.error,
        auth_failures=failures,
        checked_at=now,
    )


def _auth_failures(outcome: _Outcome, previous: ServiceTest | None) -> int:
    """這個位址上連續幾次帳密不被接受（M4 票 21）。

    qBittorrent 數的是 Berth 這台的 IP、只在登入成功時歸零（brief §20.2），Berth 照同一個規則
    數：被封了也不歸零——解封之後再錯一次就又封。換位址的話呼叫端不帶上一次（`choose_service`）。
    """
    before = previous.auth_failures if previous is not None else 0
    if outcome.reason is ConnectionReason.AUTH_REQUIRED:
        return before + 1
    if outcome.ok:
        return 0
    return before


def _existing_indexer_step(test: ServiceTest) -> SetupStep:
    """既有 Prowlarr 的那一條纜繩：連得上是站數（0 站是 `pending`，M4 票 20），與頁 4 的既有表單
    同一份（`indexer.existing_prowlarr_step`）；版本太舊也是它的那一句（M4 票 17）。"""
    if test.state is ConnectionState.OK:
        return existing_prowlarr_step(int(test.detail or 0))
    if test.reason is ConnectionReason.VERSION_UNSUPPORTED:
        return outdated_step(test.detail)
    return SetupStep(
        key=IndexerKind.PROWLARR.value,
        status=StepStatus.FAILED,
        failure=_REASON_FAILURE.get(test.reason, StepFailure.UNEXPECTED),
        error=test.error or test.reason,
    )


#: 連線測試的理由 → 纜繩的代碼：既有 Prowlarr 那一條就是測試結果本身（M4 票 21）。
_REASON_FAILURE = {
    ConnectionReason.AUTH_REQUIRED: StepFailure.AUTH_REJECTED,
    ConnectionReason.API_KEY_MISSING: StepFailure.CREDENTIAL_MISSING,
    ConnectionReason.NOT_DEPLOYED: StepFailure.NOT_DEPLOYED,
    ConnectionReason.UNREACHABLE: StepFailure.UNREACHABLE,
    ConnectionReason.STARTING: StepFailure.STARTING,
    ConnectionReason.PROTOCOL_MISMATCH: StepFailure.PROTOCOL_MISMATCH,
    ConnectionReason.SCHEME_MISMATCH: StepFailure.SCHEME_MISMATCH,
    ConnectionReason.SCHEME_MISSING: StepFailure.SCHEME_MISSING,
    ConnectionReason.IP_BANNED: StepFailure.IP_BANNED,
}


def _current_step(setup: SetupSettings, *, berthed: bool) -> int:
    """頁由狀態導出，不存游標（plan §9.3〈續行與跳過〉）。

    精靈可以續行也可以重跑，存「走到第幾頁」的游標會在使用者換了一台服務之後說謊。
    頁 3 的依據不在這一組設定裡（`routes` 表的 `routes_ready`、套件內清單對著媒體庫快照的
    `libraries_built`），所以它由參數 `berthed` 帶進來。
    """
    if not setup.owner_established():
        return STEP_JELLYFIN
    if not _qbittorrent_secured(setup):
        return STEP_QBITTORRENT
    if not berthed:
        return STEP_ROUTES
    if not _indexer_settled(setup):
        return STEP_INDEXER
    if not tmdb_verified(setup):
        return STEP_TMDB
    return STEP_COMPLETE


def _qbittorrent_secured(setup: SetupSettings) -> bool:
    """頁 2 做完了沒：選過、最後一次測試連得上、按過；套件內的那一台還要建議鍵都有結論、
    有 WebUI 登入。

    登入必填（M4 票 07 shape）：沒設過的那一台密碼那一條是 `pending`，精靈停在這裡。
    既有的那一台沒有偏好的纜繩（M4 票 22），按下「確認」只記密碼那一條 `skipped`——它就是
    「按過了」的記號。

    **連線測試要是綠的**（M4 票 25）：套用過之後 qBittorrent 停了，重新測試紅了，這一頁就還沒做完
    ——原本連線卡紅、前進鍵照樣在。它回來、重新測試綠了，套用過的纜繩照舊算數。
    """
    choice = setup.choices.get(ServiceKind.QBITTORRENT)
    if choice is None or choice.test is None or choice.test.state is not ConnectionState.OK:
        return False
    origin = choice.origin
    done = {
        row.key
        for row in setup.qbittorrent.steps
        if row.status in (StepStatus.OK, StepStatus.SKIPPED)
    }
    if origin is not ServiceOrigin.BUNDLED:
        return QbittorrentStep.PASSWORD.value in done
    return done >= {step.value for step in QbittorrentStep}


def _indexer_settled(setup: SetupSettings) -> bool:
    """頁 4 可跳過（plan §9.3），所以「有結論」包含「使用者說之後再說」。

    逐站失敗不擋：十個公開站裡有幾個連不上是常態，只要接上了一個就走得下去。
    **替 Prowlarr 介面設登入那一條不算「接上了一個」**——它與站接不接得上無關，算進去等於
    十站全失敗也放行；但套件內的那一台要**另外**有它（必填，M4 票 07 shape）。

    **套件內那一台上已經有站也算**（M4 票 27）：重裝保留 Prowlarr 設定時，站不是這一次的 Berth
    加的，不在候選清單、也加不了。站數取最後一次連線測試（`_sites_counted`）。
    """
    if setup.indexer.skipped:
        return True
    settled = {
        row.key for row in setup.indexer.steps if row.status in (StepStatus.OK, StepStatus.SKIPPED)
    }
    if setup.origin_of(ServiceKind.PROWLARR) is not ServiceOrigin.BUNDLED:
        return bool(settled - {PROWLARR_LOGIN_STEP})
    sites = bool(settled - {PROWLARR_LOGIN_STEP}) or _sites_counted(setup) > 0
    return sites and PROWLARR_LOGIN_STEP in settled


def _sites_counted(setup: SetupSettings) -> int:
    """最後一次連得上的 Prowlarr 連線測試數到幾站（`_test_connection`；加站與移除之後
    `indexer._recount` 跟著改）。沒連上、或還沒測過是 0。"""
    choice = setup.choices.get(ServiceKind.PROWLARR)
    if choice is None or choice.test is None or choice.test.state is not ConnectionState.OK:
        return 0
    return int(choice.test.detail or 0)


def _owner_signs_in(setup: SetupSettings) -> bool:
    """那一台 Jellyfin 跑完了自己的初始精靈：測試時它這麼說，或 Berth 替它走完了 `Complete`。

    **管理員建好了不算**（M4 票 29，實測 E12）：之後某一步失敗時那一台還沒初始化完，重試要照樣
    寫語言與遠端存取，登入表單不帶它們，後端只能補上預設值。
    """
    choice = setup.choices.get(ServiceKind.JELLYFIN)
    if (
        choice is not None
        and choice.test is not None
        and choice.test.reason is ConnectionReason.SETUP_COMPLETED
    ):
        return True
    return any(
        row.key == JellyfinStep.COMPLETE.value and row.status in (StepStatus.OK, StepStatus.SKIPPED)
        for row in setup.jellyfin.steps
    )


def _status(setup: SetupSettings, *, now: datetime, berthed: bool) -> SetupStatus:
    return SetupStatus(
        completed=setup.completed,
        current_step=_current_step(setup, berthed=berthed),
        owner=setup.owner.name,
        owner_signs_in=_owner_signs_in(setup),
        jellyfin_startup=remembered_startup(setup),
        services=tuple(
            _view(kind, choice, now)
            for kind in ServiceKind
            if (choice := setup.choices.get(kind)) is not None
        ),
        window_seconds=int(TEST_WINDOW.total_seconds()),
    )


def _view(kind: ServiceKind, choice: ServiceChoice, now: datetime) -> ServiceView:
    test = choice.test
    waited = now - test.waiting_since if test is not None and test.waiting_since else timedelta()
    return ServiceView(
        kind=kind,
        origin=choice.origin,
        base_url=choice.base_url,
        state=test.state if test is not None else None,
        reason=test.reason if test is not None else None,
        detail=test.detail if test is not None else "",
        server_id=test.server_id if test is not None else "",
        error=test.error if test is not None else "",
        auth_failures=test.auth_failures if test is not None else 0,
        waited_seconds=max(int(waited.total_seconds()), 0),
    )


def _utcnow() -> datetime:
    return datetime.now(UTC)
