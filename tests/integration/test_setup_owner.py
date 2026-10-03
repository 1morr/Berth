"""精靈第 1 步：擁有者（M4 票 06、brief §11、§19 2026-09-26「精靈改為 Jellyfin 優先」）。

照 Seerr：先連 Jellyfin，它的管理員就是 Berth 的擁有者。套件內的那一台由 Berth 代建管理員，
既有的那一台以它自己的管理員登入；成功的那一刻發 Berth session。帳密只交給 Jellyfin，不存下來。
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.adapters.jellyfin import JellyfinAuth
from berth.adapters.jellyfin.fake import SERVER_ID, FakeJellyfinClient
from berth.db import create_session_factory
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
from berth.services.clients import BundledServices
from berth.services.jellyfin import JellyfinStartup, JellyfinTarget
from berth.services.settings import read_settings, write_settings
from berth.services.setup import (
    STEP_JELLYFIN,
    STEP_QBITTORRENT,
    OwnerRejectedError,
    ServiceConnection,
    choose_service,
    claim_owner,
    read_status,
)
from tests.integration.arrange import chosen
from tests.integration.factories import COMPOSE, FakeClientFactory

NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
PASSWORD = "harbour-lights"
JELLYFIN_URL = "http://jellyfin:8096"
#: 頁 1 畫面上測過的那一台：表單送出時帶著它（M4 票 28）。
SEEN = JellyfinTarget(base_url=JELLYFIN_URL, server_id=SERVER_ID)


async def found(
    session: AsyncSession,
    *,
    origin: ServiceOrigin = ServiceOrigin.BUNDLED,
    reason: ConnectionReason = ConnectionReason.SETUP_PENDING,
    state: ConnectionState = ConnectionState.OK,
    server_id: str = SERVER_ID,
) -> None:
    """頁 1 前半：使用者選了來源、測試是 `state`，那一台答的 ServerId 是 `server_id`
    （M4 票 15、28）。"""
    setup = await read_settings(session, SetupSettings)
    setup.choices = {
        ServiceKind.JELLYFIN: chosen(origin, JELLYFIN_URL, reason, state=state, server_id=server_id)
    }
    await write_settings(session, setup)
    await write_settings(session, JellyfinSettings(base_url=JELLYFIN_URL))
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

    claimed = await claim_owner(
        session, factory, target=SEEN, username="skipper", password=PASSWORD
    )

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

    await claim_owner(session, factory, target=SEEN, username="skipper", password=PASSWORD)

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

    await claim_owner(session, bundled(), target=SEEN, username="skipper", password=PASSWORD)

    assert PASSWORD not in await stored_setup(session)
    assert PASSWORD not in json.dumps(
        (await read_settings(session, JellyfinSettings)).model_dump(mode="json")
    )


@pytest.mark.asyncio
async def test_the_owner_moves_the_wizard_to_qbittorrent(session: AsyncSession) -> None:
    await found(session)
    assert (await read_status(session)).current_step == STEP_JELLYFIN

    await claim_owner(session, bundled(), target=SEEN, username="skipper", password=PASSWORD)

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
        await claim_owner(session, factory, target=SEEN, username="skipper", password="another")
    assert refused.value.reason is OwnerRefusal.INVALID_CREDENTIALS
    assert factory.jellyfin_.admin == ("skipper", PASSWORD)

    claimed = await claim_owner(
        session, factory, target=SEEN, username="skipper", password=PASSWORD
    )
    assert claimed.signed_in.user.role is Role.ADMIN


# --- 既有 ---


@pytest.mark.asyncio
async def test_existing_refuses_a_user_who_is_not_an_administrator(session: AsyncSession) -> None:
    await found(session, origin=ServiceOrigin.EXISTING, reason=ConnectionReason.SETUP_COMPLETED)

    with pytest.raises(OwnerRejectedError) as refused:
        await claim_owner(session, existing(), target=SEEN, username="deckhand", password=PASSWORD)

    assert (refused.value.reason, refused.value.detail) == (OwnerRefusal.NOT_ADMINISTRATOR, "")
    status = await read_status(session)
    assert (status.owner, status.current_step) == ("", STEP_JELLYFIN)
    assert (await read_settings(session, JellyfinSettings)).api_key == ""


@pytest.mark.asyncio
async def test_existing_admin_becomes_the_owner(session: AsyncSession) -> None:
    await found(session, origin=ServiceOrigin.EXISTING, reason=ConnectionReason.SETUP_COMPLETED)
    factory = existing()

    claimed = await claim_owner(
        session, factory, target=SEEN, username="captain", password=PASSWORD
    )

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
        await claim_owner(session, existing(), target=SEEN, username="captain", password="nope")

    assert refused.value.reason is OwnerRefusal.INVALID_CREDENTIALS


@pytest.mark.asyncio
async def test_an_old_jellyfin_is_refused_with_its_version(session: AsyncSession) -> None:
    await found(session, origin=ServiceOrigin.EXISTING, reason=ConnectionReason.SETUP_COMPLETED)
    factory = existing()
    factory.jellyfin_.version = "10.11.11"

    with pytest.raises(OwnerRejectedError) as refused:
        await claim_owner(session, factory, target=SEEN, username="captain", password=PASSWORD)

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
        await claim_owner(session, bundled(), target=SEEN, username="skipper", password=PASSWORD)

    assert refused.value.reason is OwnerRefusal.JELLYFIN_UNRESOLVED


@pytest.mark.asyncio
async def test_no_claim_before_jellyfin_is_chosen(session: AsyncSession) -> None:
    factory = bundled()

    with pytest.raises(OwnerRejectedError) as refused:
        await claim_owner(session, factory, target=SEEN, username="skipper", password=PASSWORD)

    assert refused.value.reason is OwnerRefusal.JELLYFIN_UNRESOLVED
    assert factory.jellyfin_.admin is None


@pytest.mark.asyncio
async def test_an_existing_jellyfin_that_never_ran_its_wizard_gets_its_admin_created(
    session: AsyncSession,
) -> None:
    """表單跟著那一台的狀態走（brief §16.3）：選既有而它還沒初始化，擁有者建立它的管理員。"""
    await found(session, origin=ServiceOrigin.EXISTING, reason=ConnectionReason.SETUP_PENDING)
    factory = bundled()

    claimed = await claim_owner(
        session, factory, target=SEEN, username="skipper", password=PASSWORD
    )

    assert factory.jellyfin_.admin == ("skipper", PASSWORD)
    assert claimed.signed_in.user.role is Role.ADMIN


@pytest.mark.asyncio
async def test_the_language_and_remote_access_asked_on_screen_are_what_jellyfin_gets(
    session: AsyncSession,
) -> None:
    """既有而還沒初始化的那一台：語言與地區、遠端存取在畫面上問（M4 票 18，使用者拍板），
    送出的值就是寫進 `/Startup/Configuration` 與 `/Startup/RemoteAccess` 的。"""
    await found(session, origin=ServiceOrigin.EXISTING, reason=ConnectionReason.SETUP_PENDING)
    factory = bundled()

    await claim_owner(
        session,
        factory,
        target=SEEN,
        username="skipper",
        password=PASSWORD,
        startup=JellyfinStartup(
            ui_culture="en-GB", metadata_language="en", metadata_country="GB", remote_access=True
        ),
    )

    assert factory.jellyfin_.culture == ("en-GB", "GB", "en")
    assert factory.jellyfin_.remote_access is True


@pytest.mark.asyncio
async def test_remote_access_stays_off_unless_asked_for(session: AsyncSession) -> None:
    await found(session, origin=ServiceOrigin.EXISTING, reason=ConnectionReason.SETUP_PENDING)
    factory = bundled()

    await claim_owner(
        session,
        factory,
        target=SEEN,
        username="skipper",
        password=PASSWORD,
        startup=JellyfinStartup(
            ui_culture="zh-TW", metadata_language="zh-TW", metadata_country="TW"
        ),
    )

    assert factory.jellyfin_.culture == ("zh-TW", "TW", "zh-TW")
    assert factory.jellyfin_.remote_access is False


# --- 畫面上測過的那一台（M4 票 28，實測 E12）---


@pytest.mark.parametrize(
    "seen",
    [
        JellyfinTarget(base_url="http://localhost:58097", server_id=SERVER_ID),
        JellyfinTarget(base_url=JELLYFIN_URL, server_id="548d38d28268441f8d4bd0b0b7a6c1e2"),
    ],
    ids=["address", "server"],
)
@pytest.mark.asyncio
async def test_a_target_swapped_while_the_form_was_open_is_refused_before_jellyfin_is_asked(
    session: AsyncSession, seen: JellyfinTarget
) -> None:
    """擁有者成立前頁 1 是匿名的：別人在你填表時把位址改掉，帳密不能跟著送到新位址。"""
    await found(session, origin=ServiceOrigin.EXISTING, reason=ConnectionReason.SETUP_COMPLETED)
    factory = existing()
    factory.jellyfin_.error = AssertionError("Jellyfin must not be asked")
    before = await stored_setup(session)

    with pytest.raises(OwnerRejectedError) as refused:
        await claim_owner(session, factory, target=seen, username="captain", password=PASSWORD)

    assert refused.value.reason is OwnerRefusal.TARGET_CHANGED
    assert await stored_setup(session) == before


@pytest.mark.asyncio
async def test_a_test_that_never_learned_the_server_id_is_not_a_match(
    session: AsyncSession,
) -> None:
    """票 28 之前測過的那一列沒有 ServerId：兩邊都是空字串不算「同一台」，重新測試再送。"""
    await found(
        session,
        origin=ServiceOrigin.EXISTING,
        reason=ConnectionReason.SETUP_COMPLETED,
        server_id="",
    )
    factory = existing()
    factory.jellyfin_.error = AssertionError("Jellyfin must not be asked")

    with pytest.raises(OwnerRejectedError) as refused:
        await claim_owner(
            session,
            factory,
            target=JellyfinTarget(base_url=JELLYFIN_URL, server_id=""),
            username="captain",
            password=PASSWORD,
        )

    assert refused.value.reason is OwnerRefusal.TARGET_CHANGED


@pytest.mark.asyncio
async def test_the_claim_goes_to_the_address_that_was_tested(session: AsyncSession) -> None:
    """位址在比對之後才被換掉（兩次讀之間）：帳密照樣只送到畫面上的那一個位址。"""
    await found(session, origin=ServiceOrigin.EXISTING, reason=ConnectionReason.SETUP_COMPLETED)
    await write_settings(session, JellyfinSettings(base_url="http://elsewhere:8096"))
    await session.commit()
    factory = existing()
    factory.elsewhere["http://elsewhere:8096"] = FakeJellyfinClient(
        error=AssertionError("the swapped address must not be asked")
    )

    claimed = await claim_owner(
        session, factory, target=SEEN, username="captain", password=PASSWORD
    )

    assert claimed.signed_in.user.name == "captain"


@pytest.mark.asyncio
async def test_another_server_behind_the_same_address_never_sees_the_password(
    session: AsyncSession,
) -> None:
    """測過之後同一個位址後面換了一台：序列的第一步就認出來，帳密那一步不跑。"""
    await found(session)
    factory = bundled()
    factory.jellyfin_.server_id = "548d38d28268441f8d4bd0b0b7a6c1e2"

    with pytest.raises(OwnerRejectedError) as refused:
        await claim_owner(session, factory, target=SEEN, username="skipper", password=PASSWORD)

    assert refused.value.reason is OwnerRefusal.TARGET_CHANGED
    assert factory.jellyfin_.admin is None
    assert (await read_status(session)).owner == ""


@pytest.mark.asyncio
async def test_a_target_swapped_while_the_sequence_runs_leaves_no_owner(
    session: AsyncSession, engine: AsyncEngine
) -> None:
    """帳密已經送到畫面上那一台，但這一分鐘裡另一邊匿名改選了別台：擁有者不落在頁 1 已經不選的
    那一台，畫面上那一台換來的 key 也不留給新選的位址——連線設定跟著選擇走，重測與下一次登入問的
    都是它。"""
    await found(session, origin=ServiceOrigin.EXISTING, reason=ConnectionReason.SETUP_COMPLETED)
    paused = _PausedAtSignIn(admin=("captain", PASSWORD))
    factory = FakeClientFactory(jellyfin=paused)
    elsewhere = "http://elsewhere:8096"
    meanwhile = FakeClientFactory(
        jellyfin=FakeJellyfinClient(startup_wizard_completed=True, server_id="another-server")
    )

    async def swap() -> None:
        await paused.signing_in.wait()
        async with create_session_factory(engine)() as other:
            await choose_service(
                other,
                meanwhile,
                BundledServices(targets=COMPOSE, prowlarr_api_key=""),
                ServiceKind.JELLYFIN,
                ServiceOrigin.EXISTING,
                ServiceConnection(base_url=elsewhere),
            )
        paused.go.set()

    swapping = asyncio.create_task(swap())
    with pytest.raises(OwnerRejectedError) as refused:
        await claim_owner(session, factory, target=SEEN, username="captain", password=PASSWORD)
    await swapping

    assert refused.value.reason is OwnerRefusal.TARGET_CHANGED
    assert (await read_status(session)).owner == ""
    jellyfin = await read_settings(session, JellyfinSettings)
    assert (jellyfin.base_url, jellyfin.api_key) == (elsewhere, "")


@pytest.mark.asyncio
async def test_two_owners_at_once_leave_exactly_one(
    session: AsyncSession, engine: AsyncEngine
) -> None:
    """兩個人同時送頁 1（M4 票 28）：先檢查、打網路、最後寫，後寫的那一個在寫鎖裡被擋下。"""
    await found(session, origin=ServiceOrigin.EXISTING, reason=ConnectionReason.SETUP_COMPLETED)
    paused = _PausedAtSignIn(admin=("captain", PASSWORD))
    first = FakeClientFactory(jellyfin=paused)
    second = FakeClientFactory(
        jellyfin=FakeJellyfinClient(startup_wizard_completed=True, admin=("first-mate", PASSWORD))
    )

    async def claim(factory: FakeClientFactory, username: str) -> str:
        async with create_session_factory(engine)() as own_session:
            try:
                claimed = await claim_owner(
                    own_session, factory, target=SEEN, username=username, password=PASSWORD
                )
            except OwnerRejectedError as refused:
                return refused.reason.value
            return claimed.signed_in.user.name

    slow = asyncio.create_task(claim(first, "captain"))
    await paused.signing_in.wait()
    fast = await claim(second, "first-mate")
    paused.go.set()

    assert (fast, await slow) == ("first-mate", OwnerRefusal.OWNER_EXISTS.value)
    assert (await read_status(session)).owner == "first-mate"


class _PausedAtSignIn(FakeJellyfinClient):
    """登入那一刻停住，讓另一個請求整個跑完。"""

    def __init__(self, admin: tuple[str, str]) -> None:
        super().__init__(startup_wizard_completed=True, admin=admin)
        self.signing_in = asyncio.Event()
        self.go = asyncio.Event()

    async def authenticate(self, username: str, password: str) -> JellyfinAuth:
        self.signing_in.set()
        await self.go.wait()
        return await super().authenticate(username, password)


# --- 擁有者成立之後 ---


@pytest.mark.asyncio
async def test_the_owner_remembers_which_jellyfin_it_lives_on(session: AsyncSession) -> None:
    """ServerId 記下來，之後換位址只接受同一台（brief §20.15、M4 票 18）。"""
    other = "9fda94c0187f455fb00c8593d35ef9d1"
    await found(
        session,
        origin=ServiceOrigin.EXISTING,
        reason=ConnectionReason.SETUP_COMPLETED,
        server_id=other,
    )
    factory = existing()
    factory.jellyfin_.server_id = other

    await claim_owner(
        session,
        factory,
        target=JellyfinTarget(base_url=JELLYFIN_URL, server_id=other),
        username="captain",
        password=PASSWORD,
    )

    owner = (await read_settings(session, SetupSettings)).owner
    assert owner.jellyfin_server_id == "9fda94c0187f455fb00c8593d35ef9d1"


@pytest.mark.asyncio
async def test_an_established_owner_is_not_replaced(session: AsyncSession) -> None:
    """成立之後任何一位管理員再打這一支都不換擁有者（M4 票 18）；連 Jellyfin 都不問。"""
    await found(session, origin=ServiceOrigin.EXISTING, reason=ConnectionReason.SETUP_COMPLETED)
    factory = existing()
    factory.jellyfin_.admin = ("captain", PASSWORD)
    await claim_owner(session, factory, target=SEEN, username="captain", password=PASSWORD)
    factory.jellyfin_.users = {}
    factory.jellyfin_.admin = ("first-mate", PASSWORD)
    factory.jellyfin_.error = AssertionError("Jellyfin must not be asked")

    with pytest.raises(OwnerRejectedError) as refused:
        await claim_owner(session, factory, target=SEEN, username="first-mate", password=PASSWORD)

    assert refused.value.reason is OwnerRefusal.OWNER_EXISTS
    assert (await read_status(session)).owner == "captain"


@pytest.mark.asyncio
async def test_a_bundled_jellyfin_kept_from_a_reinstall_is_a_sign_in(
    session: AsyncSession,
) -> None:
    """套件內但已經初始化過（重裝保留 config）：同一組管理員帳密登入，一個設定都不動。"""
    await found(session, reason=ConnectionReason.SETUP_COMPLETED)
    factory = existing()

    claimed = await claim_owner(
        session, factory, target=SEEN, username="captain", password=PASSWORD
    )

    assert claimed.signed_in.user.role is Role.ADMIN
    assert factory.jellyfin_.culture is None
    assert factory.jellyfin_.remote_access is None
