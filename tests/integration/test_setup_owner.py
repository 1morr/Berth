"""精靈第 1 步：擁有者（M4 票 06、brief §11、§19 2026-09-26「精靈改為 Jellyfin 優先」）。

照 Seerr：先連 Jellyfin，它的管理員就是 Berth 的擁有者。套件內的那一台由 Berth 代建管理員，
既有的那一台以它自己的管理員登入；成功的那一刻發 Berth session。帳密只交給 Jellyfin，不存下來。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.domain import (
    DetectionReason,
    JellyfinStep,
    OwnerRefusal,
    Role,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.models import JellyfinSettings, ServiceProbe, Setting, SetupSettings
from berth.services.auth import read_session, sign_in
from berth.services.clients import SetupProbes
from berth.services.settings import read_settings, write_settings
from berth.services.setup import (
    STEP_DETECT,
    STEP_OWNER,
    OwnerRejectedError,
    claim_owner,
    detect_services,
    read_status,
)
from tests.integration.factories import FakeClientFactory

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
PASSWORD = "harbour-lights"


async def found(
    session: AsyncSession,
    *,
    origin: ServiceOrigin = ServiceOrigin.BUNDLED,
    reason: DetectionReason = DetectionReason.SETUP_PENDING,
) -> None:
    """第 1 步前半：Jellyfin 已經找到了（探測的結果）。"""
    setup = await read_settings(session, SetupSettings)
    setup.services = {
        ServiceKind.JELLYFIN: ServiceProbe(
            origin=origin,
            reason=reason,
            detail="12.1.0",
            base_url="http://jellyfin:8096",
            checked_at=NOW,
        )
    }
    await write_settings(session, setup)
    await write_settings(session, JellyfinSettings(base_url="http://jellyfin:8096"))
    await session.commit()


def bundled() -> FakeClientFactory:
    return FakeClientFactory(jellyfin=FakeJellyfinClient(startup_wizard_completed=False))


def existing() -> FakeClientFactory:
    return FakeClientFactory(
        jellyfin=FakeJellyfinClient(
            startup_wizard_completed=True,
            admin=("captain", PASSWORD),
            users={"deckhand": PASSWORD},
        )
    )


async def stored_setup(session: AsyncSession) -> str:
    row = await session.scalar(select(Setting).where(Setting.key == SetupSettings.KEY))
    return json.dumps(row.value_json if row else {})


@pytest.mark.asyncio
async def test_a_clean_install_starts_at_the_owner(session: AsyncSession) -> None:
    status = await read_status(session)

    assert (status.completed, status.current_step, status.owner) == (False, STEP_OWNER, "")
    assert status.services == ()


# --- 套件內 ---


@pytest.mark.asyncio
async def test_bundled_creates_the_jellyfin_admin_and_that_pair_signs_in_as_admin(
    session: AsyncSession,
) -> None:
    await found(session)
    factory = bundled()

    claimed = await claim_owner(session, factory, username="skipper", password=PASSWORD)

    assert factory.jellyfin_.admin == ("skipper", PASSWORD)
    assert claimed.signed_in.user.role is Role.ADMIN
    assert await read_session(session, claimed.signed_in.token) == claimed.signed_in.user
    # 同一組帳密之後就是登入 Berth 的那一組（`/login` 走的也是 Jellyfin）。
    again = await sign_in(session, factory, username="skipper", password=PASSWORD)
    assert again.user.role is Role.ADMIN
    assert again.user.id == claimed.signed_in.user.id


@pytest.mark.asyncio
async def test_bundled_leaves_jellyfin_ready_for_its_berth(session: AsyncSession) -> None:
    """初始設定跑完、Berth 的 API key 存好；建媒體庫留給泊位 1。"""
    await found(session)
    factory = bundled()

    await claim_owner(session, factory, username="skipper", password=PASSWORD)

    jellyfin = factory.jellyfin_
    assert jellyfin.startup_wizard_completed is True
    assert jellyfin.created == []
    assert (await read_settings(session, JellyfinSettings)).api_key == "key-berth-0"
    steps = {
        row.key: row.status for row in (await read_settings(session, SetupSettings)).jellyfin.steps
    }
    assert JellyfinStep.LIBRARIES.value not in steps
    assert steps[JellyfinStep.ADMIN_USER.value] is StepStatus.OK
    assert steps[JellyfinStep.API_KEY.value] is StepStatus.OK


@pytest.mark.asyncio
async def test_the_owners_password_is_not_stored(session: AsyncSession) -> None:
    await found(session)

    await claim_owner(session, bundled(), username="skipper", password=PASSWORD)

    assert PASSWORD not in await stored_setup(session)
    assert PASSWORD not in json.dumps(
        (await read_settings(session, JellyfinSettings)).model_dump(mode="json")
    )


@pytest.mark.asyncio
async def test_the_owner_moves_the_wizard_to_detection(session: AsyncSession) -> None:
    await found(session)
    assert (await read_status(session)).current_step == STEP_OWNER

    await claim_owner(session, bundled(), username="skipper", password=PASSWORD)

    status = await read_status(session)
    assert status.owner == "skipper"
    assert status.current_step == STEP_DETECT


@pytest.mark.asyncio
async def test_a_second_claim_on_a_bundled_jellyfin_is_a_sign_in(session: AsyncSession) -> None:
    """管理員已經建好（上一次在某一步失敗、或 session 過期後重來）：同一組帳密照樣成立，
    別的密碼不會蓋掉它——Jellyfin 12 對第二次建立回 403（brief §20.9）。
    """
    await found(session)
    factory = bundled()
    factory.jellyfin_.admin = ("skipper", PASSWORD)

    with pytest.raises(OwnerRejectedError) as refused:
        await claim_owner(session, factory, username="skipper", password="another")
    assert refused.value.reason is OwnerRefusal.INVALID_CREDENTIALS
    assert factory.jellyfin_.admin == ("skipper", PASSWORD)

    claimed = await claim_owner(session, factory, username="skipper", password=PASSWORD)
    assert claimed.signed_in.user.role is Role.ADMIN


# --- 既有 ---


@pytest.mark.asyncio
async def test_existing_refuses_a_user_who_is_not_an_administrator(session: AsyncSession) -> None:
    await found(session, origin=ServiceOrigin.EXISTING, reason=DetectionReason.SETUP_COMPLETED)

    with pytest.raises(OwnerRejectedError) as refused:
        await claim_owner(session, existing(), username="deckhand", password=PASSWORD)

    assert (refused.value.reason, refused.value.detail) == (OwnerRefusal.NOT_ADMINISTRATOR, "")
    status = await read_status(session)
    assert (status.owner, status.current_step) == ("", STEP_OWNER)
    assert (await read_settings(session, JellyfinSettings)).api_key == ""


@pytest.mark.asyncio
async def test_existing_admin_becomes_the_owner(session: AsyncSession) -> None:
    await found(session, origin=ServiceOrigin.EXISTING, reason=DetectionReason.SETUP_COMPLETED)
    factory = existing()

    claimed = await claim_owner(session, factory, username="captain", password=PASSWORD)

    assert claimed.signed_in.user.role is Role.ADMIN
    assert (await read_status(session)).owner == "captain"
    assert (await read_settings(session, JellyfinSettings)).api_key == "key-berth-0"
    # 既有的那一台：一個設定都不動（brief §16.4）。
    assert factory.jellyfin_.culture is None
    assert factory.jellyfin_.remote_access is None
    assert PASSWORD not in await stored_setup(session)


@pytest.mark.asyncio
async def test_a_wrong_password_is_refused_as_invalid_credentials(session: AsyncSession) -> None:
    await found(session, origin=ServiceOrigin.EXISTING, reason=DetectionReason.SETUP_COMPLETED)

    with pytest.raises(OwnerRejectedError) as refused:
        await claim_owner(session, existing(), username="captain", password="nope")

    assert refused.value.reason is OwnerRefusal.INVALID_CREDENTIALS


@pytest.mark.asyncio
async def test_an_old_jellyfin_is_refused_with_its_version(session: AsyncSession) -> None:
    await found(session, origin=ServiceOrigin.EXISTING, reason=DetectionReason.SETUP_COMPLETED)
    factory = existing()
    factory.jellyfin_.version = "10.11.11"

    with pytest.raises(OwnerRejectedError) as refused:
        await claim_owner(session, factory, username="captain", password=PASSWORD)

    assert refused.value.reason is OwnerRefusal.JELLYFIN_FAILED
    assert "10.11.11" in refused.value.detail


# --- 偵測 ---


@pytest.mark.asyncio
async def test_no_claim_before_jellyfin_is_found(session: AsyncSession) -> None:
    await found(session, origin=ServiceOrigin.PENDING, reason=DetectionReason.UNREACHABLE)

    with pytest.raises(OwnerRejectedError) as refused:
        await claim_owner(session, bundled(), username="skipper", password=PASSWORD)

    assert refused.value.reason is OwnerRefusal.JELLYFIN_UNRESOLVED


def probes(jellyfin: FakeJellyfinClient) -> SetupProbes:
    return SetupProbes(
        jellyfin=jellyfin,
        qbittorrent=FakeQbittorrentClient(),
        prowlarr=FakeProwlarrClient(),
        prowlarr_api_key="key-prowlarr",
    )


@pytest.mark.asyncio
async def test_before_the_owner_detection_only_looks_for_jellyfin(session: AsyncSession) -> None:
    """其他服務的偵測在擁有者之後（票 06）：那時候寫入的東西都已經在門後。"""
    status = await detect_services(session, probes(FakeJellyfinClient()), now=NOW)

    assert [row.kind for row in status.services] == [ServiceKind.JELLYFIN]
    assert status.current_step == STEP_OWNER


@pytest.mark.asyncio
async def test_after_the_owner_jellyfin_is_not_probed_again(session: AsyncSession) -> None:
    """套件內的那一台剛被 Berth 跑完初始精靈，重探會把它判成既有（`_pin_jellyfin` 的道理）。"""
    await found(session)
    await claim_owner(session, bundled(), username="skipper", password=PASSWORD)

    status = await detect_services(
        session, probes(FakeJellyfinClient(startup_wizard_completed=True)), now=NOW
    )

    by_kind = {row.kind: row for row in status.services}
    assert by_kind[ServiceKind.JELLYFIN].origin is ServiceOrigin.BUNDLED
    assert set(by_kind) == set(ServiceKind)


@pytest.mark.asyncio
async def test_detection_before_the_owner_leaves_the_other_verdicts_alone(
    session: AsyncSession,
) -> None:
    """擁有者之前只探 Jellyfin，但**不丟掉**另外兩列：舊資料庫的精靈跑到一半時（migration 之後
    回到第 1 步），Prowlarr 已經被 Berth 加過站、判定釘住了（`configured`）。丟掉的話擁有者之後
    重探會看到它有索引站而判成既有——plan §9.3「釘住不再重探」的那一條（code-review 抓到）。
    """
    pinned = ServiceProbe(
        origin=ServiceOrigin.BUNDLED,
        reason=DetectionReason.NO_INDEXERS,
        base_url="http://prowlarr:9696",
        checked_at=NOW,
        configured=True,
    )
    setup = await read_settings(session, SetupSettings)
    setup.services = {ServiceKind.PROWLARR: pinned}
    await write_settings(session, setup)
    await session.commit()

    await detect_services(session, probes(FakeJellyfinClient()), now=NOW)

    assert (await read_settings(session, SetupSettings)).services[ServiceKind.PROWLARR] == pinned
