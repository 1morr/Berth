"""精靈的命令不再互相蓋掉（M4 票 23）。

精靈的命令都是「讀、打網路、寫回」，網路那幾秒最多 5 秒，而套件內那一台還在啟動時前端每 3 秒
重測一次。拿開頭讀到的整份 `settings.setup` 跨過網路再整列寫回，別人在那幾秒裡寫進去的就被蓋回
舊值（2026-10-01 實測 L-P2-1：頁 2 做完了，12 秒後 qBittorrent 又變回上一次的失敗）。

交錯是真的：替身在網路請求的中途開第二個 session、跑完另一支命令，再回到原本那一支。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.adapters.http import AuthFailedError, ServiceBusyError
from berth.adapters.jellyfin import JellyfinPublicInfo
from berth.adapters.jellyfin.fake import SERVER_ID, FakeJellyfinClient
from berth.adapters.qbittorrent import QbittorrentVersion
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.db import create_session_factory
from berth.domain import (
    ConnectionReason,
    ConnectionState,
    JellyfinStep,
    OwnerRefusal,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.models import (
    IndexerSettings,
    JellyfinSettings,
    QbittorrentSettings,
    ServiceChoice,
    ServiceTest,
    SetupSettings,
    SetupStep,
)
from berth.services.clients import BundledServices
from berth.services.jellyfin import JellyfinTarget
from berth.services.qbittorrent import apply_qbittorrent, set_interface_login
from berth.services.settings import read_settings, write_settings
from berth.services.setup import (
    STEP_ROUTES,
    OwnerRejectedError,
    ServiceConnection,
    SetupStatus,
    choose_service,
    claim_owner,
    read_status,
    retest_service,
)
from berth.services.steps import InterfaceLogin
from tests.integration.arrange import chosen, own
from tests.integration.factories import COMPOSE, FakeClientFactory

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
BUNDLED = BundledServices(targets=COMPOSE, prowlarr_api_key="mounted-key")
NAS_QBITTORRENT = "http://nas:8080"
OTHER_QBITTORRENT = "http://nas:18080"
MATE = InterfaceLogin(username="mate", password="harbour-2")


def state_of(status: SetupStatus, kind: ServiceKind) -> ConnectionState | None:
    return next(row.state for row in status.services if row.kind is kind)


async def arrange(session: AsyncSession) -> None:
    """L-P2-1 的樣子：頁 1 做完了，套件內 Jellyfin 又進了啟動中；頁 2 的既有 qBittorrent 上一次
    沒測過；套件內 Prowlarr 也還在啟動。"""
    await own(session)
    setup = await read_settings(session, SetupSettings)
    setup.jellyfin.steps = [SetupStep(key=JellyfinStep.API_KEY.value, status=StepStatus.OK)]
    starting = ServiceTest(
        state=ConnectionState.WAITING,
        reason=ConnectionReason.STARTING,
        checked_at=NOW,
        waiting_since=NOW,
    )
    setup.choices = {
        ServiceKind.JELLYFIN: ServiceChoice(
            origin=ServiceOrigin.BUNDLED, base_url=COMPOSE[ServiceKind.JELLYFIN], test=starting
        ),
        ServiceKind.QBITTORRENT: chosen(
            ServiceOrigin.EXISTING,
            NAS_QBITTORRENT,
            ConnectionReason.UNREACHABLE,
            state=ConnectionState.FAILED,
        ),
        ServiceKind.PROWLARR: ServiceChoice(
            origin=ServiceOrigin.BUNDLED, base_url=COMPOSE[ServiceKind.PROWLARR], test=starting
        ),
    }
    await write_settings(session, setup)
    await write_settings(session, QbittorrentSettings(base_url=NAS_QBITTORRENT))
    await write_settings(
        session,
        IndexerSettings(base_url=COMPOSE[ServiceKind.PROWLARR], api_key="k"),
    )
    await session.commit()


class _StillStarting(FakeJellyfinClient):
    """還在啟動的 Jellyfin：每一次都答 503。第一次答之前，`meanwhile` 在另一個 session 裡跑完。"""

    def __init__(self, engine: AsyncEngine, meanwhile: str) -> None:
        super().__init__()
        self._engine = engine
        self._meanwhile = meanwhile
        self._done = False

    async def public_info(self) -> JellyfinPublicInfo:
        if not self._done:
            self._done = True
            async with create_session_factory(self._engine)() as other:
                if self._meanwhile == "page 2":
                    factory = FakeClientFactory(qbittorrent=FakeQbittorrentClient())
                    await choose_service(
                        other,
                        factory,
                        BUNDLED,
                        ServiceKind.QBITTORRENT,
                        ServiceOrigin.EXISTING,
                        ServiceConnection(base_url=NAS_QBITTORRENT),
                        now=NOW,
                    )
                    await apply_qbittorrent(other, factory)
                else:
                    await retest_service(
                        other, FakeClientFactory(), BUNDLED, ServiceKind.PROWLARR, now=NOW
                    )
        raise ServiceBusyError("GET /System/Info/Public: 503 Service Unavailable")


class _JellyfinUpMeanwhile(FakeQbittorrentClient):
    """頁 2 的套用讀偏好的那一刻（每一次套用都讀，票 32 起不一定寫），Jellyfin 的輪詢先寫完了：
    它已經起來了。"""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__()
        self._engine = engine
        self._done = False

    async def preferences(self) -> Mapping[str, Any]:
        if not self._done:
            self._done = True
            async with create_session_factory(self._engine)() as other:
                await retest_service(
                    other, FakeClientFactory(), BUNDLED, ServiceKind.JELLYFIN, now=NOW
                )
        return await super().preferences()


@pytest.mark.asyncio
async def test_a_poll_in_flight_does_not_undo_page_2(
    session: AsyncSession, engine: AsyncEngine
) -> None:
    """L-P2-1：Jellyfin 啟動中的輪詢還在路上時，頁 2 測過、按了確認。輪詢寫完之後頁 2 仍是完成。"""
    await arrange(session)
    factory = FakeClientFactory(jellyfin=_StillStarting(engine, "page 2"))

    polled = await retest_service(session, factory, BUNDLED, ServiceKind.JELLYFIN, now=NOW)

    assert state_of(polled, ServiceKind.JELLYFIN) is ConnectionState.WAITING
    status = await read_status(session)
    assert state_of(status, ServiceKind.QBITTORRENT) is ConnectionState.OK
    assert status.current_step == STEP_ROUTES


@pytest.mark.asyncio
async def test_two_services_polled_at_once_both_keep_their_results(
    session: AsyncSession, engine: AsyncEngine
) -> None:
    """兩個服務的測試交錯寫入：Prowlarr 在 Jellyfin 的那一次中途起來了，兩邊的結果都在。"""
    await arrange(session)
    factory = FakeClientFactory(jellyfin=_StillStarting(engine, "prowlarr"))

    await retest_service(session, factory, BUNDLED, ServiceKind.JELLYFIN, now=NOW)

    status = await read_status(session)
    assert state_of(status, ServiceKind.PROWLARR) is ConnectionState.OK
    assert state_of(status, ServiceKind.JELLYFIN) is ConnectionState.WAITING


@pytest.mark.asyncio
async def test_applying_page_2_does_not_undo_a_poll_that_landed_meanwhile(
    session: AsyncSession, engine: AsyncEngine
) -> None:
    """反過來：頁 2 的套用還在路上時，Jellyfin 的輪詢先寫完了。套用寫完之後 Jellyfin 仍是綠的。"""
    await arrange(session)
    setup = await read_settings(session, SetupSettings)
    setup.choices = {
        **setup.choices,
        ServiceKind.QBITTORRENT: chosen(ServiceOrigin.BUNDLED, COMPOSE[ServiceKind.QBITTORRENT]),
    }
    await write_settings(session, setup)
    await write_settings(session, QbittorrentSettings(base_url=COMPOSE[ServiceKind.QBITTORRENT]))
    await session.commit()
    factory = FakeClientFactory(qbittorrent=_JellyfinUpMeanwhile(engine))

    await apply_qbittorrent(session, factory)

    status = await read_status(session)
    assert state_of(status, ServiceKind.JELLYFIN) is ConnectionState.OK
    steps = (await read_settings(session, SetupSettings)).qbittorrent.steps
    assert steps, "頁 2 的纜繩要記下來"


class _SwitchedMeanwhile(FakeQbittorrentClient):
    """頁 2 的測試還在路上時，另一個分頁把 qBittorrent 換成了另一台（它測過了）。這一次答的是
    原本那一台：帳密不對。"""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__()
        self._engine = engine
        self._done = False

    async def version(self) -> QbittorrentVersion:
        if not self._done:
            self._done = True
            async with create_session_factory(self._engine)() as other:
                await choose_service(
                    other,
                    FakeClientFactory(),
                    BUNDLED,
                    ServiceKind.QBITTORRENT,
                    ServiceOrigin.EXISTING,
                    ServiceConnection(base_url=OTHER_QBITTORRENT),
                    now=NOW,
                )
        raise AuthFailedError("auth/login: Fails.")


@pytest.mark.asyncio
async def test_a_result_about_the_previous_address_is_not_recorded_on_the_new_one(
    session: AsyncSession, engine: AsyncEngine
) -> None:
    await arrange(session)
    factory = FakeClientFactory(qbittorrent=_SwitchedMeanwhile(engine))

    await retest_service(session, factory, BUNDLED, ServiceKind.QBITTORRENT, now=NOW)

    choice = (await read_settings(session, SetupSettings)).choices[ServiceKind.QBITTORRENT]
    assert choice.base_url == OTHER_QBITTORRENT
    assert choice.test is not None
    assert choice.test.state is ConnectionState.OK


class _RivalClaims(FakeJellyfinClient):
    """頁 1 送出去、Jellyfin 還在建管理員時，另一個人先成了擁有者。"""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(startup_wizard_completed=False)
        self._engine = engine
        self._done = False

    async def complete_startup(self) -> None:
        if not self._done:
            self._done = True
            async with create_session_factory(self._engine)() as other:
                await own(other, "rival")
                await other.commit()
        await super().complete_startup()


@pytest.mark.asyncio
async def test_a_second_owner_does_not_replace_the_first(
    session: AsyncSession, engine: AsyncEngine
) -> None:
    setup = await read_settings(session, SetupSettings)
    setup.choices = {
        ServiceKind.JELLYFIN: chosen(
            ServiceOrigin.BUNDLED,
            COMPOSE[ServiceKind.JELLYFIN],
            ConnectionReason.SETUP_PENDING,
            server_id=SERVER_ID,
        )
    }
    await write_settings(session, setup)
    await write_settings(session, JellyfinSettings(base_url=COMPOSE[ServiceKind.JELLYFIN]))
    await session.commit()
    factory = FakeClientFactory(jellyfin=_RivalClaims(engine))

    with pytest.raises(OwnerRejectedError) as refused:
        await claim_owner(
            session,
            factory,
            target=JellyfinTarget(base_url=COMPOSE[ServiceKind.JELLYFIN], server_id=SERVER_ID),
            username="skipper",
            password="harbour-lights",
        )

    assert refused.value.reason is OwnerRefusal.OWNER_EXISTS
    assert (await read_status(session)).owner == "rival"


class _Page2Meanwhile(FakeQbittorrentClient):
    """頁 2 的套用讀偏好的那一刻，另一個分頁先寫完了 `meanwhile`。"""

    def __init__(self, engine: AsyncEngine, meanwhile: str) -> None:
        super().__init__()
        self._engine = engine
        self._meanwhile = meanwhile
        self._done = False

    async def preferences(self) -> Mapping[str, Any]:
        if not self._done:
            self._done = True
            async with create_session_factory(self._engine)() as other:
                if self._meanwhile == "login":
                    await set_interface_login(other, FakeClientFactory(), MATE)
                else:
                    await choose_service(
                        other,
                        FakeClientFactory(),
                        BUNDLED,
                        ServiceKind.QBITTORRENT,
                        ServiceOrigin.EXISTING,
                        ServiceConnection(base_url=NAS_QBITTORRENT),
                        now=NOW,
                    )
        return await super().preferences()


async def bundled_qbittorrent(session: AsyncSession) -> None:
    """頁 2 選了套件內、登入設過了（帳號 skipper）。"""
    await arrange(session)
    setup = await read_settings(session, SetupSettings)
    setup.choices = {
        **setup.choices,
        ServiceKind.QBITTORRENT: chosen(ServiceOrigin.BUNDLED, COMPOSE[ServiceKind.QBITTORRENT]),
    }
    setup.qbittorrent.web_ui_username = "skipper"
    await write_settings(session, setup)
    await write_settings(session, QbittorrentSettings(base_url=COMPOSE[ServiceKind.QBITTORRENT]))
    await session.commit()


@pytest.mark.asyncio
async def test_reapplying_page_2_keeps_a_login_set_meanwhile(
    session: AsyncSession, engine: AsyncEngine
) -> None:
    """不帶登入的重按（登入照舊）不把開頭讀到的那一組寫回去：設定頁剛換的登入留著。"""
    await bundled_qbittorrent(session)
    factory = FakeClientFactory(qbittorrent=_Page2Meanwhile(engine, "login"))

    await apply_qbittorrent(session, factory)

    assert (await read_settings(session, SetupSettings)).qbittorrent.web_ui_username == "mate"


@pytest.mark.asyncio
async def test_applying_page_2_records_nothing_once_another_qbittorrent_is_chosen(
    session: AsyncSession, engine: AsyncEngine
) -> None:
    """套用的那幾秒裡另一個分頁換了一台：結果說的是原本那一台，不記在新的那一台上。"""
    await bundled_qbittorrent(session)
    factory = FakeClientFactory(qbittorrent=_Page2Meanwhile(engine, "switch"))

    await apply_qbittorrent(session, factory)

    assert (await read_settings(session, SetupSettings)).qbittorrent.steps == []
    assert (await read_settings(session, QbittorrentSettings)).base_url == NAS_QBITTORRENT
