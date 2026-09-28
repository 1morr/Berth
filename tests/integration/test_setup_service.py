"""精靈第 2 步的 services 命令：偵測服務（plan §9.3、票 05）。

第 1 步（擁有者）在 `test_setup_owner.py`。這裡的每一條都從「擁有者已經成立」開始
（`owner_first`）：擁有者成立之前偵測只探 Jellyfin（M4 票 06）。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
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
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.domain import DetectionReason, ServiceKind, ServiceOrigin
from berth.models import IndexerSettings, SetupSettings
from berth.services.clients import SetupProbes
from berth.services.settings import read_settings, write_settings
from berth.services.setup import (
    DETECT_WINDOW,
    SetupStatus,
    claim_owner,
    detect_services,
    read_status,
)
from tests.integration.arrange import own
from tests.integration.factories import FakeClientFactory
from tests.integration.test_setup_jellyfin import seed as dock_jellyfin

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def probes(
    *,
    jellyfin: FakeJellyfinClient | None = None,
    qbittorrent: FakeQbittorrentClient | None = None,
    prowlarr: FakeProwlarrClient | None = None,
    prowlarr_api_key: str = "the-key",
) -> SetupProbes:
    return SetupProbes(
        jellyfin=jellyfin or FakeJellyfinClient(),
        qbittorrent=qbittorrent or FakeQbittorrentClient(),
        prowlarr=prowlarr or FakeProwlarrClient(),
        prowlarr_api_key=prowlarr_api_key,
    )


def verdict(status: SetupStatus, kind: ServiceKind) -> tuple[ServiceOrigin, DetectionReason]:
    detection = next(row for row in status.services if row.kind is kind)
    return detection.origin, detection.reason


def detail(status: SetupStatus, kind: ServiceKind) -> str:
    return next(row for row in status.services if row.kind is kind).detail


@pytest_asyncio.fixture(autouse=True)
async def owner_first(session: AsyncSession) -> None:
    await own(session)
    await session.commit()


# --- 第 2 步：偵測服務 ---


@pytest.mark.asyncio
async def test_all_three_bundled_on_a_clean_compose(session: AsyncSession) -> None:
    status = await detect_services(session, probes(), now=NOW)

    assert verdict(status, ServiceKind.JELLYFIN) == (
        ServiceOrigin.BUNDLED,
        DetectionReason.SETUP_PENDING,
    )
    assert verdict(status, ServiceKind.QBITTORRENT) == (
        ServiceOrigin.BUNDLED,
        DetectionReason.ANONYMOUS_OK,
    )
    assert verdict(status, ServiceKind.PROWLARR) == (
        ServiceOrigin.BUNDLED,
        DetectionReason.NO_INDEXERS,
    )
    assert status.current_step == 3


@pytest.mark.asyncio
async def test_measured_values_are_carried_to_the_ui(session: AsyncSession) -> None:
    status = await detect_services(session, probes(), now=NOW)

    assert detail(status, ServiceKind.JELLYFIN) == "12.1.0"
    assert "v5.2.3" in detail(status, ServiceKind.QBITTORRENT)
    assert "2.15.1" in detail(status, ServiceKind.QBITTORRENT)
    jellyfin = next(row for row in status.services if row.kind is ServiceKind.JELLYFIN)
    assert jellyfin.base_url == "http://jellyfin:8096"


@pytest.mark.asyncio
async def test_jellyfin_that_finished_its_own_wizard_is_existing(session: AsyncSession) -> None:
    configured = FakeJellyfinClient(
        server_name="nas", version="12.0.0", startup_wizard_completed=True
    )

    status = await detect_services(session, probes(jellyfin=configured), now=NOW)

    assert verdict(status, ServiceKind.JELLYFIN) == (
        ServiceOrigin.EXISTING,
        DetectionReason.SETUP_COMPLETED,
    )


@pytest.mark.asyncio
async def test_qbittorrent_asking_for_credentials_is_existing(session: AsyncSession) -> None:
    guarded = FakeQbittorrentClient(error=AuthFailedError("403"))

    status = await detect_services(session, probes(qbittorrent=guarded), now=NOW)

    assert verdict(status, ServiceKind.QBITTORRENT) == (
        ServiceOrigin.EXISTING,
        DetectionReason.AUTH_REQUIRED,
    )


@pytest.mark.asyncio
async def test_prowlarr_with_indexers_is_existing(session: AsyncSession) -> None:
    in_use = FakeProwlarrClient(indexers=[ProwlarrIndexer(id=1, name="Nyaa.si", enabled=True)])

    status = await detect_services(session, probes(prowlarr=in_use), now=NOW)

    assert verdict(status, ServiceKind.PROWLARR) == (
        ServiceOrigin.EXISTING,
        DetectionReason.HAS_INDEXERS,
    )
    assert detail(status, ServiceKind.PROWLARR) == "1"


@pytest.mark.asyncio
async def test_prowlarr_without_an_api_key_falls_back_to_the_form(session: AsyncSession) -> None:
    status = await detect_services(session, probes(prowlarr_api_key=""), now=NOW)

    assert verdict(status, ServiceKind.PROWLARR) == (
        ServiceOrigin.EXISTING,
        DetectionReason.API_KEY_MISSING,
    )


@pytest.mark.asyncio
async def test_prowlarr_rejecting_the_api_key_is_existing(session: AsyncSession) -> None:
    rejected = FakeProwlarrClient(indexers_error=AuthFailedError("401"))

    status = await detect_services(session, probes(prowlarr=rejected), now=NOW)

    assert verdict(status, ServiceKind.PROWLARR) == (
        ServiceOrigin.EXISTING,
        DetectionReason.AUTH_REQUIRED,
    )


@pytest.mark.asyncio
async def test_a_service_removed_from_compose_profiles_is_existing(session: AsyncSession) -> None:
    """主機名解不到就不必等：立刻顯示既有服務的表單（票 05 驗收）。"""
    absent = FakeJellyfinClient(error=ServiceNotDeployedError("no such host"))

    status = await detect_services(session, probes(jellyfin=absent), now=NOW)

    assert verdict(status, ServiceKind.JELLYFIN) == (
        ServiceOrigin.EXISTING,
        DetectionReason.NOT_DEPLOYED,
    )
    assert verdict(status, ServiceKind.QBITTORRENT)[0] is ServiceOrigin.BUNDLED
    assert verdict(status, ServiceKind.PROWLARR)[0] is ServiceOrigin.BUNDLED
    # 有結論不等於可以往下走：Berth 還不知道那台 Jellyfin 在哪裡，所以精靈留在第 2 步，
    # 使用者才填得到位址（票 06 修正）。
    assert (
        next(row for row in status.services if row.kind is ServiceKind.JELLYFIN).resolved is False
    )
    assert status.current_step == 2


@pytest.mark.asyncio
async def test_a_container_still_starting_stays_pending(session: AsyncSession) -> None:
    starting = FakeQbittorrentClient(error=ServiceUnavailableError("connection refused"))

    status = await detect_services(session, probes(qbittorrent=starting), now=NOW)

    assert verdict(status, ServiceKind.QBITTORRENT) == (
        ServiceOrigin.PENDING,
        DetectionReason.UNREACHABLE,
    )
    assert status.waited_seconds == 0
    assert status.window_seconds == int(DETECT_WINDOW.total_seconds())
    assert status.current_step == 2


@pytest.mark.asyncio
async def test_pending_becomes_timeout_after_the_polling_window(session: AsyncSession) -> None:
    starting = FakeQbittorrentClient(error=ServiceUnavailableError("connection refused"))
    later = NOW + DETECT_WINDOW + timedelta(seconds=1)

    await detect_services(session, probes(qbittorrent=starting), now=NOW)
    status = await detect_services(session, probes(qbittorrent=starting), now=later)

    assert verdict(status, ServiceKind.QBITTORRENT) == (
        ServiceOrigin.TIMEOUT,
        DetectionReason.UNREACHABLE,
    )
    assert status.waited_seconds == int((DETECT_WINDOW + timedelta(seconds=1)).total_seconds())


@pytest.mark.asyncio
async def test_retry_restarts_the_polling_window(session: AsyncSession) -> None:
    starting = FakeQbittorrentClient(error=ServiceUnavailableError("connection refused"))
    later = NOW + DETECT_WINDOW + timedelta(seconds=1)

    await detect_services(session, probes(qbittorrent=starting), now=NOW)
    status = await detect_services(session, probes(qbittorrent=starting), now=later, restart=True)

    assert verdict(status, ServiceKind.QBITTORRENT) == (
        ServiceOrigin.PENDING,
        DetectionReason.UNREACHABLE,
    )
    assert status.waited_seconds == 0


@pytest.mark.asyncio
async def test_jellyfin_still_loading_is_pending_not_an_error(session: AsyncSession) -> None:
    """Jellyfin 啟動中每一支端點都回 503（票 06g）：那是「還在啟動」，不是 500、也不是既有。"""
    loading = FakeJellyfinClient(error=ServiceBusyError("503 still loading"))

    status = await detect_services(session, probes(jellyfin=loading), now=NOW)

    assert verdict(status, ServiceKind.JELLYFIN) == (
        ServiceOrigin.PENDING,
        DetectionReason.STARTING,
    )
    assert status.current_step == 2


@pytest.mark.asyncio
async def test_still_loading_becomes_timeout_after_the_polling_window(
    session: AsyncSession,
) -> None:
    loading = FakeJellyfinClient(error=ServiceBusyError("503 still loading"))
    later = NOW + DETECT_WINDOW + timedelta(seconds=1)

    await detect_services(session, probes(jellyfin=loading), now=NOW)
    status = await detect_services(session, probes(jellyfin=loading), now=later)

    assert verdict(status, ServiceKind.JELLYFIN) == (
        ServiceOrigin.TIMEOUT,
        DetectionReason.STARTING,
    )


def answering_with_something_else(kind: ServiceKind) -> SetupProbes:
    wrong = ProtocolMismatchError("not the expected service")
    if kind is ServiceKind.JELLYFIN:
        return probes(jellyfin=FakeJellyfinClient(error=wrong))
    if kind is ServiceKind.QBITTORRENT:
        return probes(qbittorrent=FakeQbittorrentClient(error=wrong))
    return probes(prowlarr=FakeProwlarrClient(ping_error=wrong))


@pytest.mark.parametrize("kind", list(ServiceKind))
@pytest.mark.asyncio
async def test_something_else_answering_inside_the_window_is_still_pending(
    session: AsyncSession, kind: ServiceKind
) -> None:
    """啟動途中的服務會回不像它自己的東西（票 06g 量到 Jellyfin 11 秒時這樣）：視窗內先等。"""
    wrong = answering_with_something_else(kind)

    await detect_services(session, wrong, now=NOW)
    status = await detect_services(session, wrong, now=NOW + DETECT_WINDOW)

    assert verdict(status, kind) == (ServiceOrigin.PENDING, DetectionReason.PROTOCOL_MISMATCH)


@pytest.mark.parametrize("kind", list(ServiceKind))
@pytest.mark.asyncio
async def test_something_else_answering_past_the_window_is_existing(
    session: AsyncSession, kind: ServiceKind
) -> None:
    """過了視窗還是別的東西：主機名上真的不是它，展開既有服務的表單（不是逾時）。"""
    wrong = answering_with_something_else(kind)

    await detect_services(session, wrong, now=NOW)
    status = await detect_services(session, wrong, now=NOW + DETECT_WINDOW + timedelta(seconds=1))

    assert verdict(status, kind) == (ServiceOrigin.EXISTING, DetectionReason.PROTOCOL_MISMATCH)


@pytest.mark.asyncio
async def test_detection_results_survive_a_reload(session: AsyncSession) -> None:
    """關掉瀏覽器再回來要回到原本那一步（shape brief 的續行）。"""
    await detect_services(session, probes(), now=NOW)

    status = await read_status(session)

    assert verdict(status, ServiceKind.JELLYFIN)[0] is ServiceOrigin.BUNDLED
    assert status.current_step == 3


@pytest.mark.asyncio
async def test_detection_is_rerunnable_and_can_change_its_mind(session: AsyncSession) -> None:
    starting = FakeQbittorrentClient(error=ServiceUnavailableError("connection refused"))

    await detect_services(session, probes(qbittorrent=starting), now=NOW)
    status = await detect_services(session, probes(), now=NOW + timedelta(seconds=5))

    assert verdict(status, ServiceKind.QBITTORRENT)[0] is ServiceOrigin.BUNDLED
    assert len(status.services) == 3


@pytest.mark.asyncio
async def test_redetecting_one_service_leaves_the_others_as_they_were(
    session: AsyncSession,
) -> None:
    """「重新偵測這個服務」只探那一個（票 06d）：其他服務的判定原封不動，連探都不探。"""
    starting = FakeQbittorrentClient(error=ServiceUnavailableError("connection refused"))
    later = NOW + DETECT_WINDOW + timedelta(seconds=1)
    await detect_services(session, probes(qbittorrent=starting), now=NOW)
    await detect_services(session, probes(qbittorrent=starting), now=later)
    # 其他兩個這時候已經探不到了——只探 qBittorrent 的話，它們的判定不會跟著變。
    gone = probes(
        jellyfin=FakeJellyfinClient(error=ServiceNotDeployedError("jellyfin")),
        prowlarr=FakeProwlarrClient(ping_error=ServiceNotDeployedError("prowlarr")),
    )

    status = await detect_services(
        session, gone, now=later, restart=True, kind=ServiceKind.QBITTORRENT
    )

    assert verdict(status, ServiceKind.QBITTORRENT) == (
        ServiceOrigin.BUNDLED,
        DetectionReason.ANONYMOUS_OK,
    )
    assert verdict(status, ServiceKind.JELLYFIN)[0] is ServiceOrigin.BUNDLED
    assert verdict(status, ServiceKind.PROWLARR)[0] is ServiceOrigin.BUNDLED


@pytest.mark.asyncio
async def test_redetecting_a_pinned_service_does_not_probe_it_again(
    session: AsyncSession,
) -> None:
    """釘住的服務（Berth 自己設過密碼、加過站）指名重探也不探：判定規則看的正是 Berth 做掉的事。"""
    await detect_services(session, probes(), now=NOW)
    setup = await read_settings(session, SetupSettings)
    setup.services[ServiceKind.QBITTORRENT].configured = True
    await write_settings(session, setup)
    locked = FakeQbittorrentClient(error=AuthFailedError("403"))

    status = await detect_services(
        session, probes(qbittorrent=locked), now=NOW, restart=True, kind=ServiceKind.QBITTORRENT
    )

    assert verdict(status, ServiceKind.QBITTORRENT)[0] is ServiceOrigin.BUNDLED


@pytest.mark.asyncio
async def test_a_docked_bundled_jellyfin_stays_bundled_after_a_restart(
    session: AsyncSession, tmp_path: Path
) -> None:
    """第 1 步幫套件內 Jellyfin 跑完它自己的精靈之後，`StartupWizardCompleted` 會變 true——
    重新偵測不能因此把它誤判成使用者自己開的那一台（跟 qBittorrent 設完密碼、Prowlarr
    加完索引站同一個道理，票 06b 追蹤）。
    """
    await dock_jellyfin(session, library_root=str(tmp_path / "library"), owner=False)
    await claim_owner(
        session, FakeClientFactory(jellyfin=FakeJellyfinClient()), username="s", password="p"
    )
    reprobed = FakeJellyfinClient(startup_wizard_completed=True)

    status = await detect_services(
        session, probes(jellyfin=reprobed), now=NOW, restart=True, kind=ServiceKind.JELLYFIN
    )

    assert verdict(status, ServiceKind.JELLYFIN)[0] is ServiceOrigin.BUNDLED


@pytest.mark.asyncio
async def test_the_bundled_prowlarr_api_key_is_remembered_for_the_later_steps(
    session: AsyncSession,
) -> None:
    """套件內 Prowlarr 的 key 只有探測讀得到（唯讀掛載），第 6 步與 M1 都要用它。"""
    await detect_services(session, probes(prowlarr_api_key="0" * 31 + "1"))

    indexer = await read_settings(session, IndexerSettings)
    assert indexer.api_key == "0" * 31 + "1"
    assert indexer.base_url == "http://prowlarr:9696"


@pytest.mark.asyncio
async def test_a_key_the_user_pasted_is_not_overwritten_by_the_mount(
    session: AsyncSession,
) -> None:
    settings = await read_settings(session, IndexerSettings)
    settings.api_key = "the-users-key"
    await write_settings(session, settings)

    await detect_services(session, probes(prowlarr_api_key="0" * 31 + "1"))

    assert (await read_settings(session, IndexerSettings)).api_key == "the-users-key"
