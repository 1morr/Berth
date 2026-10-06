"""精靈頁 2 的 services 命令（plan §9.3、§8.1、票 08）。

套件內那一台設泊位上填的登入（M4 票 07）、既有服務什麼都不寫、Web API 低於 2.8.4 拒絕接入、
重按結果一致。全域偏好一個都不寫（M4 票 32）：閘門在 `test_qbittorrent_login_only.py`。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import AuthFailedError, ServiceNotDeployedError, ServiceUnavailableError
from berth.adapters.qbittorrent import QbittorrentVersion
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.domain import (
    ConnectionReason,
    JellyfinStep,
    QbittorrentStep,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.models import QbittorrentSettings, SetupSettings, SetupStep
from berth.services.clients import BundledServices
from berth.services.commands import CommandMark, Effect, mark_of
from berth.services.qbittorrent import (
    WEB_UI_PASSWORD_KEY,
    apply_qbittorrent,
    read_qbittorrent,
    set_interface_login,
)
from berth.services.settings import read_settings, write_settings
from berth.services.setup import STEP_QBITTORRENT, STEP_ROUTES, read_status, retest_service
from berth.services.steps import InterfaceLogin, password_matches
from tests.integration.arrange import chosen, own
from tests.integration.factories import COMPOSE, FakeClientFactory

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
BUNDLED = BundledServices(targets=COMPOSE, prowlarr_api_key="")

#: 泊位上填的 WebUI 登入（M4 票 07）。
SKIPPER = InterfaceLogin(username="skipper", password="harbour")


async def arrange(
    session: AsyncSession,
    *,
    origin: ServiceOrigin = ServiceOrigin.BUNDLED,
    username: str = "",
    password: str = "",
) -> None:
    """把資料庫推到「第 3 步做完、輪到 qBittorrent」的狀態。"""
    await own(session)
    setup = await read_settings(session, SetupSettings)
    # 前兩個泊位已經接好了：步驟由狀態導出，所以頁 2 要成為「當前」就得先把它們填齊。
    setup.jellyfin.steps = [SetupStep(key=JellyfinStep.API_KEY.value, status=StepStatus.OK)]
    setup.choices = {
        ServiceKind.JELLYFIN: chosen(
            ServiceOrigin.EXISTING, "http://nas:8096", ConnectionReason.SETUP_COMPLETED
        ),
        ServiceKind.PROWLARR: chosen(ServiceOrigin.BUNDLED, "http://prowlarr:9696"),
        ServiceKind.QBITTORRENT: chosen(
            origin,
            "http://qbittorrent:8080" if origin is ServiceOrigin.BUNDLED else "http://nas:8080",
        ),
    }
    await write_settings(session, setup)
    if origin is not ServiceOrigin.BUNDLED:
        settings = await read_settings(session, QbittorrentSettings)
        settings.base_url = "http://nas:8080"
        settings.username = username
        settings.password = password
        await write_settings(session, settings)
    await session.commit()


@pytest.mark.asyncio
async def test_reading_connects_and_writes_nothing(session: AsyncSession) -> None:
    await arrange(session)
    client = FakeQbittorrentClient()
    factory = FakeClientFactory(qbittorrent=client)

    status = await read_qbittorrent(session, factory)

    assert (status.supported, status.blocked, status.reachable) == (True, False, True)
    assert (status.web_ui_login, status.web_ui_username) == (True, "")
    assert status.steps == ()
    assert client.writes == []


@pytest.mark.asyncio
async def test_apply_sets_the_web_ui_login_typed_on_the_berth(session: AsyncSession) -> None:
    """套件內那一台的 WebUI 登入跟著「套用」送進來（M4 票 07），設完之後拿它登得進去。"""
    await arrange(session)
    client = FakeQbittorrentClient()
    factory = FakeClientFactory(qbittorrent=client)

    status = await apply_qbittorrent(session, factory, login=SKIPPER)

    # 密碼先、帳號後，各一次（M4 票 26：5.2 帳號先寫、密碼後驗）。全域偏好一個都不寫（M4 票 32）。
    assert client.writes == [{"web_ui_password": "harbour"}, {"web_ui_username": "skipper"}]
    assert [row.status for row in status.steps if row.step == QbittorrentStep.PASSWORD.value] == [
        StepStatus.OK
    ]
    assert (status.web_ui_login, status.web_ui_username) == (True, "skipper")
    await client.login("skipper", "harbour")
    with pytest.raises(AuthFailedError):
        await client.login("admin", "adminadmin")
    # Berth 只記帳號與雜湊（M4 票 15）；它連這一台靠免密白名單，連線帳密是空的。
    setup = await read_settings(session, SetupSettings)
    assert setup.qbittorrent.web_ui_username == "skipper"
    assert password_matches("harbour", setup.qbittorrent.web_ui_password_hash)
    settings = await read_settings(session, QbittorrentSettings)
    assert (settings.username, settings.password) == ("", "")


@pytest.mark.asyncio
async def test_a_changed_login_replaces_the_old_one(session: AsyncSession) -> None:
    """設定頁改登入（M4 票 07）：舊的那一組失效、新的有效。"""
    await arrange(session)
    client = FakeQbittorrentClient()
    factory = FakeClientFactory(qbittorrent=client)
    await apply_qbittorrent(session, factory, login=SKIPPER)
    written = len(client.writes)

    status = await set_interface_login(
        session, factory, InterfaceLogin(username="deckhand", password="changed")
    )

    assert client.writes[written:] == [
        {"web_ui_password": "changed"},
        {"web_ui_username": "deckhand"},
    ]
    await client.login("deckhand", "changed")
    with pytest.raises(AuthFailedError):
        await client.login("skipper", "harbour")
    assert status.web_ui_username == "deckhand"
    setup = await read_settings(session, SetupSettings)
    assert password_matches("changed", setup.qbittorrent.web_ui_password_hash)
    # 密碼那一條換成這一次的結果。
    assert [(row.step, row.status) for row in status.steps] == [
        (QbittorrentStep.PASSWORD.value, StepStatus.OK)
    ]
    assert mark_of(set_interface_login) == CommandMark(Effect.REVERSIBLE)


@pytest.mark.asyncio
async def test_reapplying_without_a_login_keeps_the_one_already_set(
    session: AsyncSession,
) -> None:
    """回頭重按不帶登入：已經設過的那一組照舊，不重寫。"""
    await arrange(session)
    client = FakeQbittorrentClient()
    factory = FakeClientFactory(qbittorrent=client)
    await apply_qbittorrent(session, factory, login=SKIPPER)
    written = len(client.writes)

    status = await apply_qbittorrent(session, factory)

    assert client.writes[written:] == []
    password = [row for row in status.steps if row.step == QbittorrentStep.PASSWORD.value]
    assert [(row.status, row.detail) for row in password] == [(StepStatus.SKIPPED, "skipper")]
    assert (await read_status(session)).current_step == STEP_ROUTES


@pytest.mark.asyncio
async def test_a_bundled_qbittorrent_without_a_login_holds_the_wizard(
    session: AsyncSession,
) -> None:
    """兩格都必填（M4 票 07 shape）：沒設過登入的套件內那一台，密碼那一條沒跑到，精靈不往下走。"""
    await arrange(session)
    client = FakeQbittorrentClient()
    factory = FakeClientFactory(qbittorrent=client)

    status = await apply_qbittorrent(session, factory)

    assert all(WEB_UI_PASSWORD_KEY not in write for write in client.writes)
    assert [row.status for row in status.steps if row.step == QbittorrentStep.PASSWORD.value] == [
        StepStatus.PENDING
    ]
    assert (status.web_ui_login, status.web_ui_username) == (True, "")
    assert (await read_status(session)).current_step == STEP_QBITTORRENT


@pytest.mark.asyncio
async def test_existing_service_never_gets_a_password_from_berth(session: AsyncSession) -> None:
    """既有 qBittorrent 是使用者自己的，Berth 不改他的密碼（brief §16.4、M4 票 07）。

    泊位上沒有那一格（`web_ui_login` 是 false）；直接打 API 帶了登入也一個字都不送。
    """
    await arrange(session, origin=ServiceOrigin.EXISTING, username="owner", password="s3cret")
    client = FakeQbittorrentClient(base_url="http://nas:8080")
    factory = FakeClientFactory(qbittorrent=client)

    status = await apply_qbittorrent(session, factory)
    with pytest.raises(ValueError, match="existing service"):
        await apply_qbittorrent(session, factory, login=SKIPPER)
    with pytest.raises(ValueError, match="existing service"):
        await set_interface_login(session, factory, SKIPPER)

    assert all(WEB_UI_PASSWORD_KEY not in write for write in client.writes)
    assert (status.web_ui_login, status.web_ui_username) == (False, "")
    # 既有服務要先登入才讀得了偏好；Berth 連它用的那一組不是「WebUI 登入」。
    assert client.logins == [("owner", "s3cret")]
    settings = await read_settings(session, QbittorrentSettings)
    assert (settings.username, settings.password) == ("owner", "s3cret")
    # 它的判定不因為這一步被釘成套件內，也不算要設登入：精靈照樣往下走。
    assert (await read_status(session)).current_step == STEP_ROUTES


@pytest.mark.asyncio
async def test_an_existing_service_lists_no_global_preferences(session: AsyncSession) -> None:
    """它沒開未完成目錄也不警告、不擋（M4 票 22）：Berth 的分類各自帶 `downloadPath`，它的全域
    設定沒有一個影響 Berth。"""
    await arrange(session, origin=ServiceOrigin.EXISTING)
    client = FakeQbittorrentClient(base_url="http://nas:8080")  # 全域 temp_path_enabled 是 false
    factory = FakeClientFactory(qbittorrent=client)

    status = await read_qbittorrent(session, factory)

    assert status.supported is True
    assert status.blocked is False


@pytest.mark.asyncio
async def test_a_web_api_below_2_8_4_is_refused(session: AsyncSession) -> None:
    """版本低於 4.4（Web API 2.8.4）拒絕接入並提示升級（brief §16.4）。"""
    await arrange(session, origin=ServiceOrigin.EXISTING)
    client = FakeQbittorrentClient(
        base_url="http://nas:8080", version=QbittorrentVersion(app="v4.3.9", webapi="2.8.2")
    )
    factory = FakeClientFactory(qbittorrent=client)

    status = await read_qbittorrent(session, factory)
    assert (status.supported, status.blocked) == (False, True)

    applied = await apply_qbittorrent(session, factory)
    assert applied.blocked is True
    assert client.writes == []


@pytest.mark.asyncio
async def test_pressing_apply_twice_changes_nothing_the_second_time(
    session: AsyncSession,
) -> None:
    await arrange(session)
    client = FakeQbittorrentClient()
    factory = FakeClientFactory(qbittorrent=client)

    first = await apply_qbittorrent(session, factory, login=SKIPPER)
    second = await apply_qbittorrent(session, factory, login=SKIPPER)

    assert len(client.writes) == 2  # 第一輪的密碼、帳號；第二輪一個都不寫。
    assert [row.status for row in second.steps] == [StepStatus.SKIPPED]
    assert [row.step for row in second.steps] == [row.step for row in first.steps]


@pytest.mark.asyncio
async def test_the_wizard_moves_on_once_the_login_is_set(
    session: AsyncSession,
) -> None:
    await arrange(session)
    assert (await read_status(session)).current_step == STEP_QBITTORRENT

    factory = FakeClientFactory(qbittorrent=FakeQbittorrentClient())
    await apply_qbittorrent(session, factory, login=SKIPPER)

    # 下一步是媒體庫路徑（票 06d 移到 qBittorrent 之後）。
    assert (await read_status(session)).current_step == STEP_ROUTES


@pytest.mark.asyncio
async def test_a_qbittorrent_that_stopped_after_applying_holds_page_2_again(
    session: AsyncSession,
) -> None:
    """套用過之後 qBittorrent 停了：重新測試是紅的，頁 2 就不算做完（M4 票 25，實測 B9-04～07）。

    原本連線卡是綠的、底下紅的、前進鍵照樣在。頁 2 做完＝這一台**現在**連得上，而且按過套用；容器
    回來、重新測試綠了，套用過的結果照舊算數，不必再按一次。
    """
    await arrange(session)
    client = FakeQbittorrentClient()
    factory = FakeClientFactory(qbittorrent=client)
    await apply_qbittorrent(session, factory, login=SKIPPER)

    client.error = ServiceNotDeployedError("GET /api/v2/app/version: host does not resolve")
    stopped = await retest_service(session, factory, BUNDLED, ServiceKind.QBITTORRENT, now=NOW)
    assert stopped.current_step == STEP_QBITTORRENT

    client.error = None
    back = await retest_service(session, factory, BUNDLED, ServiceKind.QBITTORRENT, now=NOW)
    assert back.current_step == STEP_ROUTES


@pytest.mark.asyncio
async def test_a_service_that_rejects_the_credentials_fails_the_step_not_the_request(
    session: AsyncSession,
) -> None:
    """失敗要變成一條紅色的纜繩，不是 500——畫面靠它顯示原文與手動步驟。"""
    await arrange(session, origin=ServiceOrigin.EXISTING, username="owner", password="wrong")
    client = FakeQbittorrentClient(
        base_url="http://nas:8080", login_error=AuthFailedError("auth/login: rejected")
    )
    factory = FakeClientFactory(qbittorrent=client)

    status = await apply_qbittorrent(session, factory)

    assert status.error == "auth/login: rejected"
    assert status.reachable is False
    assert client.writes == []


@pytest.mark.asyncio
async def test_a_password_that_will_not_write_fails_its_step_not_the_request(
    session: AsyncSession,
) -> None:
    """登入寫不進去是那一條纜繩紅，不是 500；Berth 也不記下那一組。"""
    await arrange(session)
    client = FakeQbittorrentClient()
    factory = FakeClientFactory(qbittorrent=client)

    async def refuse(values: Mapping[str, Any]) -> None:
        raise ServiceUnavailableError("connection refused")

    client.set_preferences = refuse  # type: ignore[method-assign]  # 只換這一支，讀偏好照常

    status = await apply_qbittorrent(session, factory, login=SKIPPER)

    by_step = {row.step: row.status for row in status.steps}
    assert by_step == {QbittorrentStep.PASSWORD.value: StepStatus.FAILED}
    assert status.reachable is True
    setup = await read_settings(session, SetupSettings)
    assert (setup.qbittorrent.web_ui_username, setup.qbittorrent.web_ui_password_hash) == ("", "")
    assert (await read_status(session)).current_step == STEP_QBITTORRENT
