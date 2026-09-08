"""精靈第 1–2 步的 services 命令（plan §9.3、票 05）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import (
    AuthFailedError,
    ProtocolMismatchError,
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
    create_admin,
    detect_services,
    read_status,
)

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


# --- 第 1 步：建立管理員 ---


@pytest.mark.asyncio
async def test_status_on_a_clean_install_starts_at_step_one(session: AsyncSession) -> None:
    status = await read_status(session)

    assert status.completed is False
    assert status.current_step == 1
    assert status.admin_created is False
    assert status.services == ()


@pytest.mark.asyncio
async def test_create_admin_records_the_account_and_the_checkbox(session: AsyncSession) -> None:
    await create_admin(session, username="skipper", password="harbour", apply_to_services=False)

    status = await read_status(session)
    assert status.admin_created is True
    assert status.admin_username == "skipper"
    assert status.apply_to_services is False
    assert status.current_step == 2


@pytest.mark.asyncio
async def test_apply_to_services_defaults_to_checked(session: AsyncSession) -> None:
    await create_admin(session, username="skipper", password="harbour", apply_to_services=True)

    assert (await read_status(session)).apply_to_services is True


@pytest.mark.asyncio
async def test_create_admin_is_rerunnable_without_duplicating(session: AsyncSession) -> None:
    await create_admin(session, username="first", password="one", apply_to_services=True)
    await create_admin(session, username="second", password="two", apply_to_services=False)

    status = await read_status(session)
    assert status.admin_username == "second"
    assert status.apply_to_services is False


@pytest.mark.asyncio
async def test_create_admin_rejects_blank_credentials(session: AsyncSession) -> None:
    with pytest.raises(ValueError):
        await create_admin(session, username="  ", password="harbour", apply_to_services=True)
    with pytest.raises(ValueError):
        await create_admin(session, username="skipper", password="", apply_to_services=True)


@pytest.mark.asyncio
async def test_admin_password_is_kept_for_the_service_steps(session: AsyncSession) -> None:
    """票 06 / 08 要拿這組帳密去建 Jellyfin 管理員與設 qBittorrent 密碼，所以存明文。"""
    await create_admin(session, username="skipper", password="harbour", apply_to_services=True)

    assert (await read_settings(session, SetupSettings)).admin.password == "harbour"


# --- 第 2 步：偵測服務 ---


@pytest.mark.asyncio
async def test_all_three_bundled_on_a_clean_compose(session: AsyncSession) -> None:
    await create_admin(session, username="skipper", password="harbour", apply_to_services=True)
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

    assert detail(status, ServiceKind.JELLYFIN) == "10.11.11"
    assert "v5.2.3" in detail(status, ServiceKind.QBITTORRENT)
    assert "2.15.1" in detail(status, ServiceKind.QBITTORRENT)
    jellyfin = next(row for row in status.services if row.kind is ServiceKind.JELLYFIN)
    assert jellyfin.base_url == "http://jellyfin:8096"


@pytest.mark.asyncio
async def test_jellyfin_that_finished_its_own_wizard_is_existing(session: AsyncSession) -> None:
    configured = FakeJellyfinClient(
        server_name="nas", version="10.10.7", startup_wizard_completed=True
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
    await create_admin(session, username="skipper", password="harbour", apply_to_services=True)
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
    await create_admin(session, username="skipper", password="harbour", apply_to_services=True)
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
async def test_a_service_answering_with_something_else_is_existing(session: AsyncSession) -> None:
    wrong = FakeJellyfinClient(error=ProtocolMismatchError("not jellyfin"))

    status = await detect_services(session, probes(jellyfin=wrong), now=NOW)

    assert verdict(status, ServiceKind.JELLYFIN) == (
        ServiceOrigin.EXISTING,
        DetectionReason.PROTOCOL_MISMATCH,
    )


@pytest.mark.asyncio
async def test_detection_results_survive_a_reload(session: AsyncSession) -> None:
    """關掉瀏覽器再回來要回到原本那一步（shape brief 的續行）。"""
    await create_admin(session, username="skipper", password="harbour", apply_to_services=True)
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
async def test_the_bundled_prowlarr_api_key_is_remembered_for_the_later_steps(
    session: AsyncSession,
) -> None:
    """套件內 Prowlarr 的 key 只有探測讀得到（唯讀掛載），第 5 步與 M1 都要用它。"""
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
