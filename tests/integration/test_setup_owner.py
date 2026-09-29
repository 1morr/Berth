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
from berth.domain import (
    ConnectionReason,
    ConnectionState,
    JellyfinStep,
    OwnerRefusal,
    Role,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.models import JellyfinSettings, Setting, SetupSettings
from berth.services.auth import read_session, sign_in
from berth.services.settings import read_settings, write_settings
from berth.services.setup import (
    STEP_JELLYFIN,
    STEP_QBITTORRENT,
    OwnerRejectedError,
    claim_owner,
    read_status,
)
from tests.integration.arrange import chosen
from tests.integration.factories import FakeClientFactory

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
PASSWORD = "harbour-lights"


async def found(
    session: AsyncSession,
    *,
    origin: ServiceOrigin = ServiceOrigin.BUNDLED,
    reason: ConnectionReason = ConnectionReason.SETUP_PENDING,
    state: ConnectionState = ConnectionState.OK,
) -> None:
    """頁 1 前半：使用者選了來源、測試是 `state`（M4 票 15）。"""
    setup = await read_settings(session, SetupSettings)
    setup.choices = {
        ServiceKind.JELLYFIN: chosen(origin, "http://jellyfin:8096", reason, state=state)
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

    assert (status.completed, status.current_step, status.owner) == (False, STEP_JELLYFIN, "")
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
async def test_the_owner_moves_the_wizard_to_qbittorrent(session: AsyncSession) -> None:
    await found(session)
    assert (await read_status(session)).current_step == STEP_JELLYFIN

    await claim_owner(session, bundled(), username="skipper", password=PASSWORD)

    status = await read_status(session)
    assert status.owner == "skipper"
    assert status.current_step == STEP_QBITTORRENT


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
    await found(session, origin=ServiceOrigin.EXISTING, reason=ConnectionReason.SETUP_COMPLETED)

    with pytest.raises(OwnerRejectedError) as refused:
        await claim_owner(session, existing(), username="deckhand", password=PASSWORD)

    assert (refused.value.reason, refused.value.detail) == (OwnerRefusal.NOT_ADMINISTRATOR, "")
    status = await read_status(session)
    assert (status.owner, status.current_step) == ("", STEP_JELLYFIN)
    assert (await read_settings(session, JellyfinSettings)).api_key == ""


@pytest.mark.asyncio
async def test_existing_admin_becomes_the_owner(session: AsyncSession) -> None:
    await found(session, origin=ServiceOrigin.EXISTING, reason=ConnectionReason.SETUP_COMPLETED)
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
    await found(session, origin=ServiceOrigin.EXISTING, reason=ConnectionReason.SETUP_COMPLETED)

    with pytest.raises(OwnerRejectedError) as refused:
        await claim_owner(session, existing(), username="captain", password="nope")

    assert refused.value.reason is OwnerRefusal.INVALID_CREDENTIALS


@pytest.mark.asyncio
async def test_an_old_jellyfin_is_refused_with_its_version(session: AsyncSession) -> None:
    await found(session, origin=ServiceOrigin.EXISTING, reason=ConnectionReason.SETUP_COMPLETED)
    factory = existing()
    factory.jellyfin_.version = "10.11.11"

    with pytest.raises(OwnerRejectedError) as refused:
        await claim_owner(session, factory, username="captain", password=PASSWORD)

    assert refused.value.reason is OwnerRefusal.JELLYFIN_FAILED
    assert "10.11.11" in refused.value.detail


# --- 選擇與測試 ---


@pytest.mark.parametrize("state", [ConnectionState.WAITING, ConnectionState.FAILED])
@pytest.mark.asyncio
async def test_no_claim_until_the_chosen_jellyfin_answers(
    session: AsyncSession, state: ConnectionState
) -> None:
    await found(session, reason=ConnectionReason.UNREACHABLE, state=state)

    with pytest.raises(OwnerRejectedError) as refused:
        await claim_owner(session, bundled(), username="skipper", password=PASSWORD)

    assert refused.value.reason is OwnerRefusal.JELLYFIN_UNRESOLVED


@pytest.mark.asyncio
async def test_no_claim_before_jellyfin_is_chosen(session: AsyncSession) -> None:
    factory = bundled()

    with pytest.raises(OwnerRejectedError) as refused:
        await claim_owner(session, factory, username="skipper", password=PASSWORD)

    assert refused.value.reason is OwnerRefusal.JELLYFIN_UNRESOLVED
    assert factory.jellyfin_.admin is None


@pytest.mark.asyncio
async def test_an_existing_jellyfin_that_never_ran_its_wizard_gets_its_admin_created(
    session: AsyncSession,
) -> None:
    """表單跟著那一台的狀態走（brief §16.3）：選既有而它還沒初始化，擁有者建立它的管理員。"""
    await found(session, origin=ServiceOrigin.EXISTING, reason=ConnectionReason.SETUP_PENDING)
    factory = bundled()

    claimed = await claim_owner(session, factory, username="skipper", password=PASSWORD)

    assert factory.jellyfin_.admin == ("skipper", PASSWORD)
    assert claimed.signed_in.user.role is Role.ADMIN


@pytest.mark.asyncio
async def test_a_bundled_jellyfin_kept_from_a_reinstall_is_a_sign_in(
    session: AsyncSession,
) -> None:
    """套件內但已經初始化過（重裝保留 config）：同一組管理員帳密登入，一個設定都不動。"""
    await found(session, reason=ConnectionReason.SETUP_COMPLETED)
    factory = existing()

    claimed = await claim_owner(session, factory, username="captain", password=PASSWORD)

    assert claimed.signed_in.user.role is Role.ADMIN
    assert factory.jellyfin_.culture is None
    assert factory.jellyfin_.remote_access is None
