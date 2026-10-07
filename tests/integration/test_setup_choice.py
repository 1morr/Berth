"""服務頁的二選一：選來源、存下、測試（plan §9.3〈服務頁的共同形狀〉、brief §16.3，M4 票 15）。

不偵測：選之前 Berth 不對那個服務發任何請求；選了「套件內」連 compose 主機名，選了「既有」連使用者
填的位址。選擇存在 `settings.setup.choices`，從此「套件內 / 既有」由它決定。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import (
    AuthFailedError,
    ProtocolMismatchError,
    ServiceBusyError,
    ServiceNotDeployedError,
    ServiceUnavailableError,
)
from berth.adapters.jellyfin import JellyfinApiKey
from berth.adapters.jellyfin.fake import SERVER_ID, FakeJellyfinClient
from berth.adapters.prowlarr import ProwlarrIndexer
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.adapters.qbittorrent import IpBannedError, QbittorrentVersion
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.domain import (
    ChoiceRefusal,
    ConnectionReason,
    ConnectionState,
    HealthStatus,
    QbittorrentStep,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.models import (
    IndexerSettings,
    JellyfinSettings,
    QbittorrentSettings,
    SetupSettings,
    SetupStep,
)
from berth.services.clients import BundledServices
from berth.services.jellyfin import add_berth_paths, connect_jellyfin
from berth.services.qbittorrent import read_qbittorrent
from berth.services.routes import build_routes, read_route_status, routes_ready
from berth.services.settings import read_settings, write_settings
from berth.services.setup import (
    STEP_JELLYFIN,
    STEP_QBITTORRENT,
    STEP_ROUTES,
    TEST_WINDOW,
    ChoiceLockedError,
    ConnectionFailedError,
    ServiceConnection,
    ServiceView,
    SetupStatus,
    choose_service,
    read_status,
    retest_service,
)
from tests.integration.arrange import arrange, factory_for, own
from tests.integration.factories import COMPOSE, FakeClientFactory

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
BUNDLED = BundledServices(targets=COMPOSE, prowlarr_api_key="mounted-key")


def view(status: SetupStatus, kind: ServiceKind) -> ServiceView:
    return next(row for row in status.services if row.kind is kind)


async def choose(
    session: AsyncSession,
    factory: FakeClientFactory,
    kind: ServiceKind,
    origin: ServiceOrigin,
    connection: ServiceConnection | None = None,
    *,
    now: datetime = NOW,
    bundled: BundledServices = BUNDLED,
) -> SetupStatus:
    return await choose_service(session, factory, bundled, kind, origin, connection, now=now)


# --- 選之前 ---


@pytest.mark.asyncio
async def test_nothing_is_chosen_or_probed_on_a_clean_install(session: AsyncSession) -> None:
    status = await read_status(session)

    assert status.services == ()
    assert status.current_step == STEP_JELLYFIN


@pytest.mark.asyncio
async def test_retesting_before_choosing_is_refused(session: AsyncSession) -> None:
    factory = FakeClientFactory()

    with pytest.raises(ValueError, match="choose"):
        await retest_service(session, factory, BUNDLED, ServiceKind.QBITTORRENT)

    assert factory.qbittorrent_.calls == 0


@pytest.mark.asyncio
async def test_existing_needs_an_address(session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="address"):
        await choose(session, FakeClientFactory(), ServiceKind.JELLYFIN, ServiceOrigin.EXISTING)


@pytest.mark.asyncio
async def test_the_qbittorrent_diff_does_not_knock_before_a_choice(session: AsyncSession) -> None:
    """選之前連「讀」也不去敲：不知道那一台是誰的（M4 票 15）。"""
    await own(session)
    await write_settings(session, QbittorrentSettings(base_url=COMPOSE[ServiceKind.QBITTORRENT]))
    factory = FakeClientFactory()

    status = await read_qbittorrent(session, factory)

    assert (status.origin, status.reachable) == (None, False)
    assert factory.qbittorrent_.calls == 0


@pytest.mark.asyncio
async def test_routes_are_not_built_before_both_choices(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    """還沒選的服務，寫入它的命令一律拒絕：不建分類、不寫探測檔。"""
    await arrange(session, roots)
    setup = await read_settings(session, SetupSettings)
    setup.choices = {k: v for k, v in setup.choices.items() if k is not ServiceKind.QBITTORRENT}
    await write_settings(session, setup)
    factory = factory_for(roots)

    with pytest.raises(ValueError, match="choose"):
        await build_routes(session, factory, ())

    assert factory.qbittorrent_.created_categories == []


@pytest.mark.asyncio
async def test_no_berth_path_is_added_before_jellyfin_is_chosen(session: AsyncSession) -> None:
    await own(session)
    jellyfin = FakeJellyfinClient()
    factory = FakeClientFactory(jellyfin=jellyfin)

    with pytest.raises(ValueError, match="choose"):
        await add_berth_paths(session, factory, library_names=["TV"])
    with pytest.raises(ValueError, match="choose"):
        await connect_jellyfin(session, factory, username="captain", password="x")

    assert factory.tokens == []


# --- 套件內 ---


@pytest.mark.asyncio
async def test_bundled_connects_to_the_compose_hostname(session: AsyncSession) -> None:
    factory = FakeClientFactory(jellyfin=FakeJellyfinClient(startup_wizard_completed=False))

    status = await choose(session, factory, ServiceKind.JELLYFIN, ServiceOrigin.BUNDLED)

    row = view(status, ServiceKind.JELLYFIN)
    assert (row.origin, row.base_url, row.state, row.reason) == (
        ServiceOrigin.BUNDLED,
        COMPOSE[ServiceKind.JELLYFIN],
        ConnectionState.OK,
        ConnectionReason.SETUP_PENDING,
    )
    assert factory.jellyfin_.base_url == COMPOSE[ServiceKind.JELLYFIN]
    assert status.owner_signs_in is False


@pytest.mark.asyncio
async def test_a_bundled_jellyfin_kept_from_a_reinstall_asks_for_a_sign_in(
    session: AsyncSession,
) -> None:
    """重裝保留 config：套件內那一台已經有管理員，頁 1 是登入表單（brief §16.3）。"""
    factory = FakeClientFactory(jellyfin=FakeJellyfinClient(startup_wizard_completed=True))

    status = await choose(session, factory, ServiceKind.JELLYFIN, ServiceOrigin.BUNDLED)

    assert view(status, ServiceKind.JELLYFIN).reason is ConnectionReason.SETUP_COMPLETED
    assert status.owner_signs_in is True


@pytest.mark.asyncio
async def test_an_existing_jellyfin_that_never_ran_its_wizard_asks_to_create(
    session: AsyncSession,
) -> None:
    """選既有而那一台還沒初始化：一樣由擁有者建管理員——它上面沒有任何人的帳號可以蓋掉。"""
    factory = FakeClientFactory(jellyfin=FakeJellyfinClient(startup_wizard_completed=False))

    status = await choose(
        session,
        factory,
        ServiceKind.JELLYFIN,
        ServiceOrigin.EXISTING,
        ServiceConnection(base_url="http://nas:8096"),
    )

    row = view(status, ServiceKind.JELLYFIN)
    assert (row.origin, row.base_url, row.state) == (
        ServiceOrigin.EXISTING,
        "http://nas:8096",
        ConnectionState.OK,
    )
    assert status.owner_signs_in is False


@pytest.mark.asyncio
async def test_bundled_qbittorrent_is_reached_without_a_login(session: AsyncSession) -> None:
    """套件內那一台在免密白名單上（plan §9.2）：Berth 不拿任何帳密登入它。"""
    await own(session)
    factory = FakeClientFactory()

    status = await choose(session, factory, ServiceKind.QBITTORRENT, ServiceOrigin.BUNDLED)

    row = view(status, ServiceKind.QBITTORRENT)
    assert (row.state, row.reason, row.detail) == (
        ConnectionState.OK,
        ConnectionReason.CONNECTED,
        "v5.2.3 · Web API 2.15.1",
    )
    assert factory.qbittorrent_.logins == []
    assert await read_settings(session, QbittorrentSettings) == QbittorrentSettings(
        base_url=COMPOSE[ServiceKind.QBITTORRENT]
    )


@pytest.mark.asyncio
async def test_bundled_prowlarr_uses_the_mounted_key(session: AsyncSession) -> None:
    await own(session)
    factory = FakeClientFactory(
        prowlarr=FakeProwlarrClient(indexers=[ProwlarrIndexer(1, "Nyaa.si", True, "nyaasi")])
    )

    status = await choose(session, factory, ServiceKind.PROWLARR, ServiceOrigin.BUNDLED)

    assert view(status, ServiceKind.PROWLARR).detail == "1"
    assert factory.api_keys == ["mounted-key"]
    indexer = await read_settings(session, IndexerSettings)
    assert (indexer.base_url, indexer.api_key) == (
        COMPOSE[ServiceKind.PROWLARR],
        "mounted-key",
    )


@pytest.mark.asyncio
async def test_bundled_prowlarr_without_a_readable_key_asks_for_one(
    session: AsyncSession,
) -> None:
    await own(session)
    factory = FakeClientFactory()
    unmounted = BundledServices(targets=COMPOSE, prowlarr_api_key="")

    status = await choose(
        session, factory, ServiceKind.PROWLARR, ServiceOrigin.BUNDLED, bundled=unmounted
    )

    row = view(status, ServiceKind.PROWLARR)
    assert (row.origin, row.state, row.reason) == (
        ServiceOrigin.BUNDLED,
        ConnectionState.FAILED,
        ConnectionReason.API_KEY_MISSING,
    )
    # 沒有 key 只敲匿名的 `/ping`：先確定它在，才說缺的是 key（M4 票 25）。
    assert factory.api_keys == [""]

    # 貼了 key 仍是套件內（plan §9.2）。
    status = await choose(
        session,
        factory,
        ServiceKind.PROWLARR,
        ServiceOrigin.BUNDLED,
        ServiceConnection(api_key="pasted-key"),
        bundled=unmounted,
    )
    row = view(status, ServiceKind.PROWLARR)
    assert (row.origin, row.state) == (ServiceOrigin.BUNDLED, ConnectionState.OK)
    assert (await read_settings(session, IndexerSettings)).api_key == "pasted-key"


@pytest.mark.asyncio
async def test_retesting_a_bundled_prowlarr_reads_the_mounted_key_again(
    session: AsyncSession,
) -> None:
    """在 Prowlarr 重新產生 API key 之後按「重新測試」：用掛載上現在那一把（實測 L-P2-3，
    M4 票 27）。

    原本只有「選」那一刻讀掛載，重新測試拿存下的舊 key，連線卡紅成 401、補法卻是 qBittorrent 的
    白名單，照做沒用。
    """
    await own(session)
    factory = FakeClientFactory()
    await choose(session, factory, ServiceKind.PROWLARR, ServiceOrigin.BUNDLED)
    regenerated = BundledServices(targets=COMPOSE, prowlarr_api_key="regenerated-key")

    status = await retest_service(
        session, factory, regenerated, ServiceKind.PROWLARR, restart=True, now=NOW
    )

    assert view(status, ServiceKind.PROWLARR).state is ConnectionState.OK
    assert factory.api_keys[-1] == "regenerated-key"
    assert (await read_settings(session, IndexerSettings)).api_key == "regenerated-key"


@pytest.mark.asyncio
async def test_retesting_without_a_mounted_key_keeps_what_was_pasted_or_still_asks(
    session: AsyncSession,
) -> None:
    """掛載讀不到 key 時重新測試不換掉什麼：沒貼過的仍是 `api_key_missing`，貼過的仍用貼的
    那一把。"""
    await own(session)
    factory = FakeClientFactory()
    unmounted = BundledServices(targets=COMPOSE, prowlarr_api_key="")
    await choose(session, factory, ServiceKind.PROWLARR, ServiceOrigin.BUNDLED, bundled=unmounted)

    status = await retest_service(session, factory, unmounted, ServiceKind.PROWLARR, now=NOW)

    assert view(status, ServiceKind.PROWLARR).reason is ConnectionReason.API_KEY_MISSING
    assert factory.api_keys[-1] == ""

    await choose(
        session,
        factory,
        ServiceKind.PROWLARR,
        ServiceOrigin.BUNDLED,
        ServiceConnection(api_key="pasted-key"),
        bundled=unmounted,
    )
    status = await retest_service(session, factory, unmounted, ServiceKind.PROWLARR, now=NOW)

    assert view(status, ServiceKind.PROWLARR).state is ConnectionState.OK
    assert factory.api_keys[-1] == "pasted-key"


@pytest.mark.asyncio
async def test_a_bundled_prowlarr_left_out_of_compose_is_not_a_missing_key(
    session: AsyncSession,
) -> None:
    """只有 Berth 時選套件內 Prowlarr：沒有那個容器，所以也沒有掛載的 key。

    原本先查 key、說「讀不到 API key」，貼了 key 才說主機名解不到（實測 E9-07～09，M4 票 25）。
    先連線，照 Jellyfin、qBittorrent 說。
    """
    await own(session)
    factory = FakeClientFactory(
        prowlarr=FakeProwlarrClient(ping_error=ServiceNotDeployedError("no such host"))
    )
    unmounted = BundledServices(targets=COMPOSE, prowlarr_api_key="")

    status = await choose(
        session, factory, ServiceKind.PROWLARR, ServiceOrigin.BUNDLED, bundled=unmounted
    )

    row = view(status, ServiceKind.PROWLARR)
    assert (row.state, row.reason) == (ConnectionState.FAILED, ConnectionReason.NOT_DEPLOYED)


@pytest.mark.asyncio
async def test_a_bundled_service_left_out_of_compose_says_so(session: AsyncSession) -> None:
    """主機名解不到＝它不在 compose 裡：當場紅燈，不等（畫面說出 `COMPOSE_PROFILES` 的補法）。"""
    await own(session)
    factory = FakeClientFactory(
        qbittorrent=FakeQbittorrentClient(error=ServiceNotDeployedError("no such host"))
    )

    status = await choose(session, factory, ServiceKind.QBITTORRENT, ServiceOrigin.BUNDLED)

    row = view(status, ServiceKind.QBITTORRENT)
    assert (row.origin, row.state, row.reason) == (
        ServiceOrigin.BUNDLED,
        ConnectionState.FAILED,
        ConnectionReason.NOT_DEPLOYED,
    )
    assert status.current_step == STEP_QBITTORRENT


# --- 還在啟動（M3 票 06g）---


STILL_STARTING = [
    (ServiceUnavailableError("connection refused"), ConnectionReason.UNREACHABLE),
    (ServiceBusyError("503 still loading"), ConnectionReason.STARTING),
    (ProtocolMismatchError("not the expected service"), ConnectionReason.PROTOCOL_MISMATCH),
]


@pytest.mark.parametrize(("error", "reason"), STILL_STARTING)
@pytest.mark.asyncio
async def test_a_bundled_container_still_starting_is_waited_for(
    session: AsyncSession, error: Exception, reason: ConnectionReason
) -> None:
    factory = FakeClientFactory(jellyfin=FakeJellyfinClient(error=error))

    await choose(session, factory, ServiceKind.JELLYFIN, ServiceOrigin.BUNDLED, now=NOW)
    status = await retest_service(
        session, factory, BUNDLED, ServiceKind.JELLYFIN, now=NOW + TEST_WINDOW
    )

    row = view(status, ServiceKind.JELLYFIN)
    assert (row.state, row.reason) == (ConnectionState.WAITING, reason)
    assert row.waited_seconds == int(TEST_WINDOW.total_seconds())
    assert status.window_seconds == int(TEST_WINDOW.total_seconds())


@pytest.mark.parametrize(
    ("error", "reason", "state"),
    [
        (ServiceUnavailableError("refused"), ConnectionReason.UNREACHABLE, ConnectionState.TIMEOUT),
        (ServiceBusyError("503"), ConnectionReason.STARTING, ConnectionState.TIMEOUT),
        # 過了上限還是別的東西：那個主機名上真的不是它（不是逾時）。
        (ProtocolMismatchError("?"), ConnectionReason.PROTOCOL_MISMATCH, ConnectionState.FAILED),
    ],
)
@pytest.mark.asyncio
async def test_past_the_window_the_wait_ends(
    session: AsyncSession, error: Exception, reason: ConnectionReason, state: ConnectionState
) -> None:
    factory = FakeClientFactory(jellyfin=FakeJellyfinClient(error=error))
    later = NOW + TEST_WINDOW + timedelta(seconds=1)

    await choose(session, factory, ServiceKind.JELLYFIN, ServiceOrigin.BUNDLED, now=NOW)
    status = await retest_service(session, factory, BUNDLED, ServiceKind.JELLYFIN, now=later)

    assert (
        view(status, ServiceKind.JELLYFIN).state,
        view(status, ServiceKind.JELLYFIN).reason,
    ) == (
        state,
        reason,
    )


@pytest.mark.asyncio
async def test_retesting_by_hand_restarts_the_window(session: AsyncSession) -> None:
    factory = FakeClientFactory(jellyfin=FakeJellyfinClient(error=ServiceUnavailableError("x")))
    later = NOW + TEST_WINDOW + timedelta(seconds=1)

    await choose(session, factory, ServiceKind.JELLYFIN, ServiceOrigin.BUNDLED, now=NOW)
    status = await retest_service(
        session, factory, BUNDLED, ServiceKind.JELLYFIN, restart=True, now=later
    )

    row = view(status, ServiceKind.JELLYFIN)
    assert (row.state, row.waited_seconds) == (ConnectionState.WAITING, 0)


@pytest.mark.asyncio
async def test_a_container_that_came_up_turns_green(session: AsyncSession) -> None:
    jellyfin = FakeJellyfinClient(error=ServiceUnavailableError("refused"))
    factory = FakeClientFactory(jellyfin=jellyfin)

    await choose(session, factory, ServiceKind.JELLYFIN, ServiceOrigin.BUNDLED, now=NOW)
    jellyfin.error = None
    status = await retest_service(session, factory, BUNDLED, ServiceKind.JELLYFIN, now=NOW)

    row = view(status, ServiceKind.JELLYFIN)
    assert (row.state, row.waited_seconds) == (ConnectionState.OK, 0)


# --- 既有 ---


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (ServiceUnavailableError("refused"), ConnectionReason.UNREACHABLE),
        (ServiceNotDeployedError("no such host"), ConnectionReason.NOT_DEPLOYED),
        (AuthFailedError("401"), ConnectionReason.AUTH_REQUIRED),
        (IpBannedError("403"), ConnectionReason.IP_BANNED),
    ],
)
@pytest.mark.asyncio
async def test_an_existing_address_gets_its_answer_on_the_spot(
    session: AsyncSession, error: Exception, reason: ConnectionReason
) -> None:
    """使用者自己填的位址不給倒數：一個永遠不會好的倒數比紅燈更糟（票 06g）。測不過不存
    （M4 票 45），那一次的結論跟著拒絕回去，畫面標在欄位上。"""
    await own(session)
    factory = FakeClientFactory(qbittorrent=FakeQbittorrentClient(login_error=error))

    with pytest.raises(ConnectionFailedError) as refused:
        await choose(
            session,
            factory,
            ServiceKind.QBITTORRENT,
            ServiceOrigin.EXISTING,
            ServiceConnection(base_url="http://nas:8080", username="home", password="wrong"),
        )

    row = refused.value.attempt
    assert (row.kind, row.origin, row.base_url) == (
        ServiceKind.QBITTORRENT,
        ServiceOrigin.EXISTING,
        "http://nas:8080",
    )
    assert (row.state, row.reason) == (ConnectionState.FAILED, reason)
    # 原文照錄，畫面收進技術細節（M4 票 21）。
    assert row.error == str(error)


@pytest.mark.parametrize(
    ("version", "passes"),
    [
        (QbittorrentVersion(app="v4.3.9", webapi="2.8.2"), False),
        (QbittorrentVersion(app="v4.4.5", webapi="2.8.5"), True),
    ],
    ids=["4.3.9", "4.4.5"],
)
@pytest.mark.asyncio
async def test_qbittorrent_below_the_floor_is_red_at_the_connection_test(
    session: AsyncSession, version: QbittorrentVersion, passes: bool
) -> None:
    """版本在測連線時就擋（M4 票 21）：原本 4.3.9 在這裡是綠的「連上了」，頁 2 的泊位卡卻是紅的
    「太舊」——同一個畫面兩種顏色。下限 Web API 2.8.4 的兩邊各一台。"""
    await own(session)
    factory = FakeClientFactory(qbittorrent=FakeQbittorrentClient(version=version))
    nas = ServiceConnection(base_url="http://nas:8080")

    if passes:
        status = await choose(
            session, factory, ServiceKind.QBITTORRENT, ServiceOrigin.EXISTING, nas
        )
        row = view(status, ServiceKind.QBITTORRENT)
        assert (row.state, row.reason) == (ConnectionState.OK, ConnectionReason.CONNECTED)
    else:
        with pytest.raises(ConnectionFailedError) as refused:
            await choose(session, factory, ServiceKind.QBITTORRENT, ServiceOrigin.EXISTING, nas)
        row = refused.value.attempt
        assert (row.state, row.reason, row.detail) == (
            ConnectionState.FAILED,
            ConnectionReason.VERSION_UNSUPPORTED,
            "v4.3.9",
        )


@pytest.mark.asyncio
async def test_failed_logins_are_counted_until_one_succeeds(session: AsyncSession) -> None:
    """連錯的次數（M4 票 21）：qBittorrent 預設連錯 5 次封 IP，只在登入成功時歸零（brief §20.2）。

    **次數跟著位址、不跟著選擇**（M4 票 45）：測不過的那一次不存，次數照樣要記——qBittorrent 數的
    是 Berth 這台的 IP。同一個位址改帳密再測接著數；另一個位址是另一台，各數各的；存下的那一組被
    拒（重新測試）也算在它的位址上；成功歸零。
    """
    await own(session)
    wrong = FakeClientFactory(qbittorrent=FakeQbittorrentClient(login_error=AuthFailedError("401")))

    async def attempt(base_url: str, password: str) -> int:
        connection = ServiceConnection(base_url=base_url, username="home", password=password)
        with pytest.raises(ConnectionFailedError) as refused:
            await choose(
                session, wrong, ServiceKind.QBITTORRENT, ServiceOrigin.EXISTING, connection
            )
        return refused.value.attempt.auth_failures

    counts = [await attempt("http://nas:8080", pw) for pw in ("wrong", "still-wrong", "nope")]
    assert counts == [1, 2, 3]
    assert await attempt("http://other:8080", "x") == 1

    right = ServiceConnection(base_url="http://other:8080", username="home", password="x")
    fixed = await choose(
        session, FakeClientFactory(), ServiceKind.QBITTORRENT, ServiceOrigin.EXISTING, right
    )
    assert view(fixed, ServiceKind.QBITTORRENT).auth_failures == 0

    retested = await retest_service(
        session, wrong, BUNDLED, ServiceKind.QBITTORRENT, restart=True, now=NOW
    )
    assert view(retested, ServiceKind.QBITTORRENT).auth_failures == 1
    assert await attempt("http://nas:8080", "again") == 4


@pytest.mark.asyncio
async def test_existing_qbittorrent_credentials_are_verified_and_kept(
    session: AsyncSession,
) -> None:
    """既有那一台的帳密是 Berth 的連線憑證（brief §16.2）：測過才存、拿它登入（M4 票 45）。"""
    await own(session)
    factory = FakeClientFactory()

    status = await choose(
        session,
        factory,
        ServiceKind.QBITTORRENT,
        ServiceOrigin.EXISTING,
        ServiceConnection(base_url="http://nas:8080", username="home", password="Home-1"),
    )

    assert view(status, ServiceKind.QBITTORRENT).state is ConnectionState.OK
    assert factory.qbittorrent_.logins == [("home", "Home-1")]
    assert await read_settings(session, QbittorrentSettings) == QbittorrentSettings(
        base_url="http://nas:8080", username="home", password="Home-1"
    )


@pytest.mark.asyncio
async def test_an_existing_prowlarr_is_the_whole_page(session: AsyncSession) -> None:
    """既有 Prowlarr 這一頁只有「連得上」：連上就做完了（不加站，票 05）。"""
    await own(session)
    factory = FakeClientFactory(
        prowlarr=FakeProwlarrClient(indexers=[ProwlarrIndexer(4, "Mine", True, "mine")])
    )

    await choose(
        session,
        factory,
        ServiceKind.PROWLARR,
        ServiceOrigin.EXISTING,
        ServiceConnection(base_url="http://nas:9696", api_key="theirs"),
    )

    setup = await read_settings(session, SetupSettings)
    assert setup.indexer.steps == [SetupStep(key="prowlarr", status=StepStatus.OK, detail="1")]
    assert factory.api_keys == ["theirs"]


#: 既有那一台的錯憑證與對的那一組（M4 票 45）：qBittorrent 的帳密、Prowlarr 的 key。
WRONG_CREDENTIALS = [
    pytest.param(
        ServiceKind.QBITTORRENT,
        ServiceConnection(base_url="http://nas:8080", username="home", password="wrong"),
        ServiceConnection(base_url="http://nas:8080", username="home", password="Home-1"),
        FakeClientFactory(qbittorrent=FakeQbittorrentClient(login_error=AuthFailedError("401"))),
        id="qbittorrent",
    ),
    pytest.param(
        ServiceKind.PROWLARR,
        ServiceConnection(base_url="http://nas:9696", api_key="wrong"),
        ServiceConnection(base_url="http://nas:9696", api_key="theirs"),
        FakeClientFactory(prowlarr=FakeProwlarrClient(ping_error=AuthFailedError("401"))),
        id="prowlarr",
    ),
]


@pytest.mark.parametrize(("kind", "wrong", "right", "rejecting"), WRONG_CREDENTIALS)
@pytest.mark.asyncio
async def test_only_existing_credentials_that_pass_are_saved(
    session: AsyncSession,
    kind: ServiceKind,
    wrong: ServiceConnection,
    right: ServiceConnection,
    rejecting: FakeClientFactory,
) -> None:
    """測過才存（M4 票 45，審計 E-6）：錯的那一組不進 `settings.services.*`、也不留選擇；對的才存。
    原本測不過也存，「改一格再按」靠的是表單留著使用者打的字，不必存下來。"""
    await own(session)
    group = QbittorrentSettings if kind is ServiceKind.QBITTORRENT else IndexerSettings

    with pytest.raises(ConnectionFailedError) as refused:
        await choose(session, rejecting, kind, ServiceOrigin.EXISTING, wrong)

    assert refused.value.attempt.reason is ConnectionReason.AUTH_REQUIRED
    assert await read_settings(session, group) == group()
    assert kind not in (await read_settings(session, SetupSettings)).choices

    status = await choose(session, FakeClientFactory(), kind, ServiceOrigin.EXISTING, right)

    assert view(status, kind).state is ConnectionState.OK
    stored = (await read_settings(session, group)).model_dump()
    assert stored["base_url"] == right.base_url
    assert (right.password or right.api_key) in stored.values()


@pytest.mark.asyncio
async def test_a_failing_change_leaves_the_connection_in_use_alone(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    """已經有一台測過的在用（設定頁改位址或帳密）：新的測不過就什麼都不換——連線、選擇、Route 的
    檢查都還是原本那一台的（M4 票 45；原本打錯一個字下載就停擺）。"""
    await arrange(session, roots)
    factory = factory_for(roots)
    in_use = ServiceConnection(base_url="http://nas:8080", username="home", password="Home-1")
    await choose(session, factory, ServiceKind.QBITTORRENT, ServiceOrigin.EXISTING, in_use)
    await build_routes(session, factory, ())
    assert await routes_ready(session)
    before = await read_settings(session, SetupSettings)
    rejecting = FakeClientFactory(
        qbittorrent=FakeQbittorrentClient(error=ServiceUnavailableError("refused"))
    )

    with pytest.raises(ConnectionFailedError) as refused:
        await choose(
            session,
            rejecting,
            ServiceKind.QBITTORRENT,
            ServiceOrigin.EXISTING,
            ServiceConnection(base_url="http://typo:8080", username="home", password="Home-1"),
        )

    assert refused.value.attempt.reason is ConnectionReason.UNREACHABLE
    assert await read_settings(session, QbittorrentSettings) == QbittorrentSettings(
        base_url="http://nas:8080", username="home", password="Home-1"
    )
    assert (await read_settings(session, SetupSettings)).choices == before.choices
    assert await routes_ready(session)


@pytest.mark.asyncio
async def test_an_existing_jellyfin_that_does_not_answer_is_not_chosen(
    session: AsyncSession,
) -> None:
    """頁 1 的既有 Jellyfin 只有位址一格：連不上同樣不存，頁 1 停在還沒選（M4 票 45）。"""
    factory = FakeClientFactory(
        jellyfin=FakeJellyfinClient(error=ServiceUnavailableError("refused"))
    )

    with pytest.raises(ConnectionFailedError) as refused:
        await choose(
            session,
            factory,
            ServiceKind.JELLYFIN,
            ServiceOrigin.EXISTING,
            ServiceConnection(base_url="http://nas:8096"),
        )

    assert refused.value.attempt.reason is ConnectionReason.UNREACHABLE
    assert (await read_status(session)).services == ()
    assert (await read_settings(session, JellyfinSettings)).base_url == ""


@pytest.mark.asyncio
async def test_choosing_one_service_leaves_the_others_alone(session: AsyncSession) -> None:
    await own(session)
    factory = FakeClientFactory()
    await choose(session, factory, ServiceKind.QBITTORRENT, ServiceOrigin.BUNDLED)

    status = await choose(session, factory, ServiceKind.PROWLARR, ServiceOrigin.BUNDLED)

    assert [row.kind for row in status.services] == [ServiceKind.QBITTORRENT, ServiceKind.PROWLARR]


# --- 換一台（shape：Jellyfin 鎖、另兩個可改）---


@pytest.mark.asyncio
async def test_switching_qbittorrent_starts_its_page_over_and_voids_the_route_checks(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    """分類建在原本那一台上：Route 的綠燈說的是它，媒體庫與路徑頁要重新檢查（shape 時拍板）。"""
    await arrange(session, roots)
    factory = factory_for(roots)
    await build_routes(session, factory, ())
    assert await routes_ready(session)
    setup = await read_settings(session, SetupSettings)
    setup.qbittorrent.web_ui_username = "skipper"
    await write_settings(session, setup)

    status = await choose(
        session,
        factory,
        ServiceKind.QBITTORRENT,
        ServiceOrigin.EXISTING,
        ServiceConnection(base_url="http://nas:8080"),
    )

    setup = await read_settings(session, SetupSettings)
    assert setup.qbittorrent.steps == []
    assert setup.qbittorrent.web_ui_username == ""
    assert not await routes_ready(session)
    routes = (await read_route_status(session)).routes
    assert all(route.health is HealthStatus.UNKNOWN for route in routes)
    # 逐條明細也清掉（M4 票 24）：留著的話畫面寫「尚未檢查」卻仍是上一台的 6 / 6 與它的錯誤。
    assert [(route.checks, route.checked_at, route.last_ok_at) for route in routes] == [
        ((), None, None)
    ] * len(routes)
    # 既有那一台測試通過就做完頁 2（M4 票 38）；作廢的 Route 檢查把精靈拉回頁 3。
    assert status.current_step == STEP_ROUTES


@pytest.mark.asyncio
async def test_choosing_the_same_one_again_keeps_the_page(session: AsyncSession) -> None:
    await own(session)
    factory = FakeClientFactory()
    await choose(session, factory, ServiceKind.QBITTORRENT, ServiceOrigin.BUNDLED)
    setup = await read_settings(session, SetupSettings)
    setup.qbittorrent.steps = [
        SetupStep(key=step.value, status=StepStatus.OK) for step in QbittorrentStep
    ]
    await write_settings(session, setup)

    await choose(session, factory, ServiceKind.QBITTORRENT, ServiceOrigin.BUNDLED)

    assert len((await read_settings(session, SetupSettings)).qbittorrent.steps) == len(
        QbittorrentStep
    )


@pytest.mark.asyncio
async def test_switching_prowlarr_forgets_the_login_it_set_on_the_other_one(
    session: AsyncSession,
) -> None:
    await own(session)
    factory = FakeClientFactory()
    await choose(session, factory, ServiceKind.PROWLARR, ServiceOrigin.BUNDLED)
    setup = await read_settings(session, SetupSettings)
    setup.indexer.web_ui_username = "deck"
    setup.indexer.steps = [SetupStep(key="nyaasi", status=StepStatus.OK)]
    await write_settings(session, setup)

    await choose(
        session,
        factory,
        ServiceKind.PROWLARR,
        ServiceOrigin.EXISTING,
        ServiceConnection(base_url="http://nas:9696", api_key="theirs"),
    )

    setup = await read_settings(session, SetupSettings)
    assert setup.indexer.web_ui_username == ""
    assert [row.key for row in setup.indexer.steps] == ["prowlarr"]


@pytest.mark.asyncio
async def test_the_jellyfin_source_is_locked_once_there_is_an_owner(
    session: AsyncSession,
) -> None:
    """擁有者是那一台上的帳號，換一台 Jellyfin 等於換擁有者（shape 時使用者拍板）。"""
    factory = FakeClientFactory()
    await choose(session, factory, ServiceKind.JELLYFIN, ServiceOrigin.BUNDLED)
    await own(session)

    with pytest.raises(ChoiceLockedError):
        await choose(
            session,
            factory,
            ServiceKind.JELLYFIN,
            ServiceOrigin.EXISTING,
            ServiceConnection(base_url="http://nas:8096"),
        )

    assert (await read_settings(session, SetupSettings)).origin_of(
        ServiceKind.JELLYFIN
    ) is ServiceOrigin.BUNDLED


async def owned_existing_jellyfin(
    session: AsyncSession, factory: FakeClientFactory, *, api_key: str = "key-berth-0"
) -> None:
    """既有 Jellyfin 在 `http://nas:8096`、擁有者在它上面、Berth 的 key 是它發的，頁 1 做完了。"""
    factory.jellyfin_.api_keys_.append(JellyfinApiKey(app_name="Berth", access_token=api_key))
    await choose(
        session,
        factory,
        ServiceKind.JELLYFIN,
        ServiceOrigin.EXISTING,
        ServiceConnection(base_url="http://nas:8096"),
    )
    await own(session)
    jellyfin = await read_settings(session, JellyfinSettings)
    jellyfin.api_key = api_key
    await write_settings(session, jellyfin)
    setup = await read_settings(session, SetupSettings)
    setup.jellyfin.steps = [SetupStep(key="api_key", status=StepStatus.OK)]
    await write_settings(session, setup)


def jellyfin_at(setup: SetupSettings, jellyfin: JellyfinSettings) -> tuple[str, str]:
    return setup.choices[ServiceKind.JELLYFIN].base_url, jellyfin.base_url


@pytest.mark.asyncio
async def test_after_the_owner_jellyfin_moves_only_to_the_same_server(
    session: AsyncSession,
) -> None:
    """同一台換了網址（ServerId 相同，brief §20.15）：存下、重驗 Berth 的 key，這一頁不重做。"""
    factory = FakeClientFactory(jellyfin=FakeJellyfinClient(startup_wizard_completed=True))
    await owned_existing_jellyfin(session, factory)
    factory.jellyfin_.use_token("")

    status = await choose(
        session,
        factory,
        ServiceKind.JELLYFIN,
        ServiceOrigin.EXISTING,
        ServiceConnection(base_url="http://nas2:8096"),
    )

    setup = await read_settings(session, SetupSettings)
    jellyfin = await read_settings(session, JellyfinSettings)
    assert jellyfin_at(setup, jellyfin) == ("http://nas2:8096", "http://nas2:8096")
    assert [row.key for row in setup.jellyfin.steps] == ["api_key"]
    moved = view(status, ServiceKind.JELLYFIN)
    assert (moved.state, moved.reason) == (ConnectionState.OK, ConnectionReason.SETUP_COMPLETED)
    # 重驗的是存下來的那一把。
    assert factory.jellyfin_.token == "key-berth-0"


@pytest.mark.asyncio
async def test_after_the_owner_another_server_is_refused_and_nothing_is_saved(
    session: AsyncSession,
) -> None:
    """另一台 Jellyfin（ServerId 不同）：擁有者、key、媒體庫都在原本那一台，換過去就是換擁有者。"""
    other = FakeJellyfinClient(
        startup_wizard_completed=True, server_id="9fda94c0187f455fb00c8593d35ef9d1"
    )
    factory = FakeClientFactory(
        jellyfin=FakeJellyfinClient(startup_wizard_completed=True),
        elsewhere={"http://other:8096": other},
    )
    await owned_existing_jellyfin(session, factory)
    before = await read_settings(session, SetupSettings)

    with pytest.raises(ChoiceLockedError) as refused:
        await choose(
            session,
            factory,
            ServiceKind.JELLYFIN,
            ServiceOrigin.EXISTING,
            ServiceConnection(base_url="http://other:8096"),
        )

    assert refused.value.reason is ChoiceRefusal.OTHER_SERVER
    setup = await read_settings(session, SetupSettings)
    jellyfin = await read_settings(session, JellyfinSettings)
    assert jellyfin_at(setup, jellyfin) == ("http://nas:8096", "http://nas:8096")
    assert setup.choices == before.choices
    assert jellyfin.api_key == "key-berth-0"


@pytest.mark.asyncio
async def test_after_the_owner_an_address_that_does_not_answer_is_not_saved(
    session: AsyncSession,
) -> None:
    """連不上就認不出是不是同一台：不存。存下去的話每個人的登入都會打到一個不回答的位址。"""
    factory = FakeClientFactory(
        jellyfin=FakeJellyfinClient(startup_wizard_completed=True),
        elsewhere={
            "http://gone:8096": FakeJellyfinClient(error=ServiceUnavailableError("refused"))
        },
    )
    await owned_existing_jellyfin(session, factory)

    with pytest.raises(ConnectionFailedError) as refused:
        await choose(
            session,
            factory,
            ServiceKind.JELLYFIN,
            ServiceOrigin.EXISTING,
            ServiceConnection(base_url="http://gone:8096"),
        )

    # 連不上是位址的錯，與擁有者之前同一條、標在位址欄（M4 票 45）；原本是頁面層級的 `unverified`。
    assert refused.value.attempt.reason is ConnectionReason.UNREACHABLE
    setup = await read_settings(session, SetupSettings)
    assert setup.choices[ServiceKind.JELLYFIN].base_url == "http://nas:8096"


@pytest.mark.asyncio
async def test_a_revoked_key_on_the_same_server_asks_the_owner_to_sign_in_again(
    session: AsyncSession,
) -> None:
    """同一台、但 Berth 那一把在 Jellyfin 被撤了：位址照樣存下，測試紅在「要求帳密」。"""
    factory = FakeClientFactory(jellyfin=FakeJellyfinClient(startup_wizard_completed=True))
    await owned_existing_jellyfin(session, factory)
    factory.jellyfin_.revoke_api_key("Berth")

    status = await choose(
        session,
        factory,
        ServiceKind.JELLYFIN,
        ServiceOrigin.EXISTING,
        ServiceConnection(base_url="http://nas2:8096"),
    )

    moved = view(status, ServiceKind.JELLYFIN)
    assert (moved.base_url, moved.state, moved.reason) == (
        "http://nas2:8096",
        ConnectionState.FAILED,
        ConnectionReason.AUTH_REQUIRED,
    )


@pytest.mark.asyncio
async def test_retesting_finds_another_server_behind_the_saved_address(
    session: AsyncSession,
) -> None:
    """同一個位址後面換成了另一台（別的容器佔了那個 port）：重新測試就說出來，不是綠燈。"""
    factory = FakeClientFactory(jellyfin=FakeJellyfinClient(startup_wizard_completed=True))
    await owned_existing_jellyfin(session, factory)
    factory.jellyfin_.server_id = "9fda94c0187f455fb00c8593d35ef9d1"

    status = await retest_service(session, factory, BUNDLED, ServiceKind.JELLYFIN, now=NOW)

    retested = view(status, ServiceKind.JELLYFIN)
    assert (retested.state, retested.reason) == (
        ConnectionState.FAILED,
        ConnectionReason.OTHER_SERVER,
    )


@pytest.mark.asyncio
async def test_an_owner_from_before_the_server_id_adopts_the_one_it_answers_with(
    session: AsyncSession,
) -> None:
    """票 18 之前成立的擁有者沒記 ServerId：下一次測到的那一台就是它（之後照樣擋另一台）。"""
    factory = FakeClientFactory(jellyfin=FakeJellyfinClient(startup_wizard_completed=True))
    await owned_existing_jellyfin(session, factory)
    await own(session, server_id="")

    await retest_service(session, factory, BUNDLED, ServiceKind.JELLYFIN, now=NOW)

    assert (await read_settings(session, SetupSettings)).owner.jellyfin_server_id == SERVER_ID


@pytest.mark.asyncio
async def test_an_owner_from_before_the_server_id_cannot_move_to_another_server_either(
    session: AsyncSession,
) -> None:
    """沒記 ServerId 的擁有者第一次換位址：先問原本那一台是誰，另一台照樣擋（spec review）。"""
    other = FakeJellyfinClient(
        startup_wizard_completed=True, server_id="9fda94c0187f455fb00c8593d35ef9d1"
    )
    factory = FakeClientFactory(
        jellyfin=FakeJellyfinClient(startup_wizard_completed=True),
        elsewhere={"http://other:8096": other},
    )
    await owned_existing_jellyfin(session, factory)
    await own(session, server_id="")

    with pytest.raises(ChoiceLockedError) as refused:
        await choose(
            session,
            factory,
            ServiceKind.JELLYFIN,
            ServiceOrigin.EXISTING,
            ServiceConnection(base_url="http://other:8096"),
        )

    assert refused.value.reason is ChoiceRefusal.OTHER_SERVER
    setup = await read_settings(session, SetupSettings)
    assert setup.choices[ServiceKind.JELLYFIN].base_url == "http://nas:8096"


@pytest.mark.asyncio
async def test_an_owner_from_before_the_server_id_whose_old_address_is_gone_cannot_move(
    session: AsyncSession,
) -> None:
    """原本那一台也不回答：認不出新位址是不是它，不存。"""
    factory = FakeClientFactory(
        jellyfin=FakeJellyfinClient(startup_wizard_completed=True),
        elsewhere={"http://nas2:8096": FakeJellyfinClient(startup_wizard_completed=True)},
    )
    await owned_existing_jellyfin(session, factory)
    await own(session, server_id="")
    factory.jellyfin_.error = ServiceUnavailableError("refused")

    with pytest.raises(ChoiceLockedError) as refused:
        await choose(
            session,
            factory,
            ServiceKind.JELLYFIN,
            ServiceOrigin.EXISTING,
            ServiceConnection(base_url="http://nas2:8096"),
        )

    assert refused.value.reason is ChoiceRefusal.UNVERIFIED


@pytest.mark.parametrize(
    ("version", "state", "reason"),
    [
        ("10.10.7", ConnectionState.FAILED, ConnectionReason.VERSION_UNSUPPORTED),
        ("11.9.9", ConnectionState.FAILED, ConnectionReason.VERSION_UNSUPPORTED),
        ("12.0.0", ConnectionState.OK, ConnectionReason.SETUP_COMPLETED),
    ],
)
@pytest.mark.asyncio
async def test_the_jellyfin_version_floor_is_checked_when_testing(
    session: AsyncSession, version: str, state: ConnectionState, reason: ConnectionReason
) -> None:
    """版本在測連線時就擋，不等到登入（M4 票 18）：頁 1 的擁有者表單因此不會出現。太舊的不存
    （M4 票 45），那一次的結論跟著拒絕回去。"""
    factory = FakeClientFactory(
        jellyfin=FakeJellyfinClient(startup_wizard_completed=True, version=version)
    )
    nas = ServiceConnection(base_url="http://nas:8096")

    if state is ConnectionState.OK:
        status = await choose(session, factory, ServiceKind.JELLYFIN, ServiceOrigin.EXISTING, nas)
        tested = view(status, ServiceKind.JELLYFIN)
    else:
        with pytest.raises(ConnectionFailedError) as refused:
            await choose(session, factory, ServiceKind.JELLYFIN, ServiceOrigin.EXISTING, nas)
        tested = refused.value.attempt
    assert (tested.state, tested.reason, tested.detail) == (state, reason, version)


@pytest.mark.asyncio
async def test_an_outdated_bundled_jellyfin_is_red_at_once(session: AsyncSession) -> None:
    """套件內那一台太舊也當場紅：等不會好（與 Prowlarr 同，M4 票 17）。"""
    factory = FakeClientFactory(jellyfin=FakeJellyfinClient(version="10.10.7"))

    status = await choose(session, factory, ServiceKind.JELLYFIN, ServiceOrigin.BUNDLED)

    tested = view(status, ServiceKind.JELLYFIN)
    assert (tested.state, tested.reason) == (
        ConnectionState.FAILED,
        ConnectionReason.VERSION_UNSUPPORTED,
    )


@pytest.mark.asyncio
async def test_before_the_owner_jellyfin_can_still_be_switched(session: AsyncSession) -> None:
    factory = FakeClientFactory()
    await choose(session, factory, ServiceKind.JELLYFIN, ServiceOrigin.BUNDLED)

    status = await choose(
        session,
        factory,
        ServiceKind.JELLYFIN,
        ServiceOrigin.EXISTING,
        ServiceConnection(base_url="http://nas:8096"),
    )

    assert view(status, ServiceKind.JELLYFIN).origin is ServiceOrigin.EXISTING
