"""精靈第 4 步的 services 命令（plan §9.3 第 4 步、§8.1、票 08）。

驗的是票 08 的驗收條件本身：差異列得出來、套用只寫有差異的鍵、套件內那一台設泊位上填的登入
（M4 票 07）、既有服務的 temp path 未啟用只警告、Web API 低於 2.8.4 拒絕接入、重按結果一致。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import AuthFailedError, ServiceUnavailableError
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
from berth.models import PathSettings, QbittorrentSettings, SetupSettings, SetupStep
from berth.services.commands import CommandMark, Effect, mark_of
from berth.services.qbittorrent import (
    WEB_UI_PASSWORD_KEY,
    apply_qbittorrent,
    read_qbittorrent_diff,
    set_interface_login,
)
from berth.services.settings import read_settings, write_settings
from berth.services.setup import STEP_QBITTORRENT, STEP_ROUTES, read_status
from berth.services.steps import InterfaceLogin, password_matches
from tests.integration.arrange import chosen, own
from tests.integration.factories import FakeClientFactory

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)

#: 泊位上填的 WebUI 登入（M4 票 07）。
SKIPPER = InterfaceLogin(username="skipper", password="harbour")

#: 精靈建議的五個鍵（plan §8.1）。順序即畫面上纜繩的順序。
RECOMMENDED_KEYS = [
    QbittorrentStep.TEMP_PATH_ENABLED,
    QbittorrentStep.TEMP_PATH,
    QbittorrentStep.SAVE_PATH,
    QbittorrentStep.AUTO_TMM_ENABLED,
    QbittorrentStep.CATEGORY_CHANGED_TMM_ENABLED,
]


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
    # 前兩個泊位已經接好了：步驟由狀態導出，所以第 4 步要成為「當前」就得先把它們填齊。
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
async def test_diff_lists_the_five_recommended_keys(session: AsyncSession) -> None:
    await arrange(session)
    factory = FakeClientFactory(qbittorrent=FakeQbittorrentClient())

    status = await read_qbittorrent_diff(session, factory)

    paths = await read_settings(session, PathSettings)
    assert [row.key for row in status.diffs] == [step.value for step in RECOMMENDED_KEYS]
    assert [row.recommended for row in status.diffs] == [
        "true",
        paths.incomplete_root,
        paths.complete_root,
        "true",
        "true",
    ]
    # 乾淨實例的現值（錄製回應，brief §20.7）：五個鍵全部與建議值不同。
    assert [row.current for row in status.diffs] == [
        "false",
        "/downloads/incomplete",
        "/downloads",
        "false",
        "false",
    ]
    assert all(row.differs for row in status.diffs)
    assert status.supported is True


@pytest.mark.asyncio
async def test_apply_writes_only_the_keys_that_differ(session: AsyncSession) -> None:
    await arrange(session)
    paths = await read_settings(session, PathSettings)
    client = FakeQbittorrentClient(
        preferences={"auto_tmm_enabled": True, "save_path": paths.complete_root}
    )
    factory = FakeClientFactory(qbittorrent=client)

    status = await apply_qbittorrent(session, factory)

    assert client.writes == [
        {
            "temp_path_enabled": True,
            "temp_path": paths.incomplete_root,
            "category_changed_tmm_enabled": True,
        }
    ]
    written = {row.step: row.status for row in status.steps}
    assert written[QbittorrentStep.TEMP_PATH.value] is StepStatus.OK
    # 已經是建議值的鍵不重寫，但仍然是一條繫上的纜繩。
    assert written[QbittorrentStep.SAVE_PATH.value] is StepStatus.SKIPPED
    assert written[QbittorrentStep.AUTO_TMM_ENABLED.value] is StepStatus.SKIPPED


@pytest.mark.asyncio
async def test_apply_sets_the_web_ui_login_typed_on_the_berth(session: AsyncSession) -> None:
    """套件內那一台的 WebUI 登入跟著「套用」送進來（M4 票 07），設完之後拿它登得進去。"""
    await arrange(session)
    client = FakeQbittorrentClient()
    factory = FakeClientFactory(qbittorrent=client)

    status = await apply_qbittorrent(session, factory, login=SKIPPER)

    assert client.writes[-1] == {"web_ui_username": "skipper", "web_ui_password": "harbour"}
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
    """設定頁改登入（M4 票 07）：舊的那一組失效、新的有效，偏好不跟著重寫。"""
    await arrange(session)
    client = FakeQbittorrentClient()
    factory = FakeClientFactory(qbittorrent=client)
    await apply_qbittorrent(session, factory, login=SKIPPER)
    written = len(client.writes)

    status = await set_interface_login(
        session, factory, InterfaceLogin(username="deckhand", password="changed")
    )

    assert client.writes[written:] == [
        {"web_ui_username": "deckhand", "web_ui_password": "changed"}
    ]
    await client.login("deckhand", "changed")
    with pytest.raises(AuthFailedError):
        await client.login("skipper", "harbour")
    assert status.web_ui_username == "deckhand"
    setup = await read_settings(session, SetupSettings)
    assert password_matches("changed", setup.qbittorrent.web_ui_password_hash)
    # 密碼那一條換成這一次的結果，五個鍵的纜繩留著。
    by_step = {row.step: row.status for row in status.steps}
    assert by_step[QbittorrentStep.PASSWORD.value] is StepStatus.OK
    assert by_step[QbittorrentStep.SAVE_PATH.value] is StepStatus.OK
    assert mark_of(set_interface_login) == CommandMark(Effect.REVERSIBLE)


@pytest.mark.asyncio
async def test_reapplying_without_a_login_keeps_the_one_already_set(
    session: AsyncSession,
) -> None:
    """回頭重按、設定頁的「還原建議設定」都不帶登入：已經設過的那一組照舊，不重寫。"""
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
async def test_existing_service_with_temp_path_off_is_a_warning_not_a_blocker(
    session: AsyncSession,
) -> None:
    await arrange(session, origin=ServiceOrigin.EXISTING)
    client = FakeQbittorrentClient(base_url="http://nas:8080")
    factory = FakeClientFactory(qbittorrent=client)

    status = await read_qbittorrent_diff(session, factory)

    assert status.temp_path_warning is True
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

    status = await read_qbittorrent_diff(session, factory)
    assert (status.supported, status.blocked) == (False, True)
    assert status.diffs == ()

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

    assert len(client.writes) == 2  # 第一輪的五個鍵 + 密碼；第二輪一個都不寫。
    assert [row.status for row in second.steps] == [
        StepStatus.SKIPPED,
        StepStatus.SKIPPED,
        StepStatus.SKIPPED,
        StepStatus.SKIPPED,
        StepStatus.SKIPPED,
        StepStatus.SKIPPED,
    ]
    assert [row.step for row in second.steps] == [row.step for row in first.steps]


@pytest.mark.asyncio
async def test_the_wizard_moves_on_once_the_preferences_are_applied(
    session: AsyncSession,
) -> None:
    await arrange(session)
    assert (await read_status(session)).current_step == STEP_QBITTORRENT

    factory = FakeClientFactory(qbittorrent=FakeQbittorrentClient())
    await apply_qbittorrent(session, factory, login=SKIPPER)

    # 下一步是媒體庫路徑（票 06d 移到 qBittorrent 之後）。
    assert (await read_status(session)).current_step == STEP_ROUTES


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
async def test_a_trailing_slash_is_not_a_difference(session: AsyncSession) -> None:
    """4.4.5 把設進去的路徑讀回來時**帶尾斜線**（brief §20.7）。

    照字面比對的話那兩個鍵在 4.4 上永遠「不同」，每次重按都重寫一次同樣的值——
    也就破壞了「重按結果一致」。
    """
    await arrange(session)
    paths = await read_settings(session, PathSettings)
    client = FakeQbittorrentClient(
        version=QbittorrentVersion(app="v4.4.5", webapi="2.8.5"),
        preferences={
            "temp_path_enabled": True,
            "temp_path": f"{paths.incomplete_root}/",
            "save_path": f"{paths.complete_root}/",
            "auto_tmm_enabled": True,
            "category_changed_tmm_enabled": True,
        },
    )
    factory = FakeClientFactory(qbittorrent=client)

    status = await apply_qbittorrent(session, factory)

    assert client.writes == []
    assert [row.differs for row in status.diffs] == [False] * 5


@pytest.mark.asyncio
async def test_a_password_that_will_not_write_keeps_the_five_keys(
    session: AsyncSession,
) -> None:
    """密碼是另一次呼叫。它失敗時前面五個鍵已經寫進去了，畫面必須說得出來。"""
    await arrange(session)
    client = FakeQbittorrentClient()
    factory = FakeClientFactory(qbittorrent=client)
    #: 前五個鍵寫得進去，密碼那一次才失敗。
    original = client.set_preferences

    async def fail_on_password(values: Mapping[str, Any]) -> None:
        if WEB_UI_PASSWORD_KEY in values:
            raise ServiceUnavailableError("connection refused")
        await original(values)

    client.set_preferences = fail_on_password  # type: ignore[method-assign]

    status = await apply_qbittorrent(session, factory, login=SKIPPER)

    by_step = {row.step: row.status for row in status.steps}
    assert by_step[QbittorrentStep.SAVE_PATH.value] is StepStatus.OK
    assert by_step[QbittorrentStep.PASSWORD.value] is StepStatus.FAILED
    assert status.reachable is True
    # 帳密沒設成功就不能記下來，否則下一次會拿它去登入。
    assert (await read_settings(session, QbittorrentSettings)).password == ""
