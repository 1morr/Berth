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
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.adapters.prowlarr import ProwlarrIndexer
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.adapters.qbittorrent import IpBannedError
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.domain import (
    ConnectionReason,
    ConnectionState,
    HealthStatus,
    IndexerKind,
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
from berth.services.jellyfin import add_berth_path, connect_jellyfin
from berth.services.qbittorrent import read_qbittorrent_diff
from berth.services.routes import build_routes, read_route_status, routes_ready
from berth.services.settings import read_settings, write_settings
from berth.services.setup import (
    STEP_JELLYFIN,
    STEP_QBITTORRENT,
    TEST_WINDOW,
    ChoiceLockedError,
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
        await retest_service(session, factory, ServiceKind.QBITTORRENT)

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

    status = await read_qbittorrent_diff(session, factory)

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
        await add_berth_path(session, factory, library_name="TV")
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
    assert (indexer.kind, indexer.base_url, indexer.api_key) == (
        IndexerKind.PROWLARR.value,
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
    # 沒有 key 就不去敲它。
    assert factory.api_keys == []

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
    status = await retest_service(session, factory, ServiceKind.JELLYFIN, now=NOW + TEST_WINDOW)

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
    status = await retest_service(session, factory, ServiceKind.JELLYFIN, now=later)

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
    status = await retest_service(session, factory, ServiceKind.JELLYFIN, restart=True, now=later)

    row = view(status, ServiceKind.JELLYFIN)
    assert (row.state, row.waited_seconds) == (ConnectionState.WAITING, 0)


@pytest.mark.asyncio
async def test_a_container_that_came_up_turns_green(session: AsyncSession) -> None:
    jellyfin = FakeJellyfinClient(error=ServiceUnavailableError("refused"))
    factory = FakeClientFactory(jellyfin=jellyfin)

    await choose(session, factory, ServiceKind.JELLYFIN, ServiceOrigin.BUNDLED, now=NOW)
    jellyfin.error = None
    status = await retest_service(session, factory, ServiceKind.JELLYFIN, now=NOW)

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
    """使用者自己填的位址不給倒數：一個永遠不會好的倒數比紅燈更糟（票 06g）。"""
    await own(session)
    factory = FakeClientFactory(qbittorrent=FakeQbittorrentClient(login_error=error))

    status = await choose(
        session,
        factory,
        ServiceKind.QBITTORRENT,
        ServiceOrigin.EXISTING,
        ServiceConnection(base_url="http://nas:8080", username="home", password="wrong"),
    )

    row = view(status, ServiceKind.QBITTORRENT)
    assert (row.state, row.reason) == (ConnectionState.FAILED, reason)


@pytest.mark.asyncio
async def test_existing_qbittorrent_credentials_are_verified_and_kept(
    session: AsyncSession,
) -> None:
    """既有那一台的帳密是 Berth 的連線憑證（brief §16.2）：存下、拿它登入。測不過也存。"""
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
    assert all(
        route.health is HealthStatus.UNKNOWN for route in (await read_route_status(session)).routes
    )
    assert status.current_step == STEP_QBITTORRENT


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


@pytest.mark.asyncio
async def test_an_existing_jellyfin_can_move_to_a_new_address_after_the_owner(
    session: AsyncSession,
) -> None:
    """同一個來源換位址可以：設定頁的連線區就是做這件事。Jellyfin 頁的結果不重做。"""
    factory = FakeClientFactory(jellyfin=FakeJellyfinClient(startup_wizard_completed=True))
    await choose(
        session,
        factory,
        ServiceKind.JELLYFIN,
        ServiceOrigin.EXISTING,
        ServiceConnection(base_url="http://nas:8096"),
    )
    await own(session)
    setup = await read_settings(session, SetupSettings)
    setup.jellyfin.steps = [SetupStep(key="api_key", status=StepStatus.OK)]
    await write_settings(session, setup)

    await choose(
        session,
        factory,
        ServiceKind.JELLYFIN,
        ServiceOrigin.EXISTING,
        ServiceConnection(base_url="http://nas2:8096"),
    )

    setup = await read_settings(session, SetupSettings)
    assert setup.choices[ServiceKind.JELLYFIN].base_url == "http://nas2:8096"
    assert [row.key for row in setup.jellyfin.steps] == ["api_key"]
    assert (await read_settings(session, JellyfinSettings)).base_url == "http://nas2:8096"


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
