"""Berth 對 qBittorrent 的全域偏好只寫 WebUI 登入（M4 票 32，brief §19 D2）。

審計 S5：套件內那一台被寫了三個全域鍵（`save_path`、`auto_tmm_enabled`、
`category_changed_tmm_enabled`），Route 檢查又回頭現查全域 `save_path`，使用者一改它送單就被擋。
Berth 送單逐個 torrent 帶分類與 `autoTMM=true`，那三個鍵本來就不影響它，所以兩種來源都不寫。

閘門：精靈走完（頁 2 套用與重按、設定頁換登入、頁 3 建 Route、送一筆單），Fake qBittorrent 收到的
`setPreferences` 只有登入的兩個鍵。鍵名照 Web API 的字面寫在這裡，不從 `services` import——被守的
程式改了常數，閘門不能跟著改口。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.domain import HealthStatus, MediaKind, ServiceKind, ServiceOrigin
from berth.models import Media, QbittorrentSettings, SetupSettings
from berth.services import qbittorrent as qbittorrent_service
from berth.services.jobs import JobSource, add_download
from berth.services.qbittorrent import apply_qbittorrent, set_interface_login
from berth.services.routes import build_routes
from berth.services.settings import read_settings, write_settings
from berth.services.steps import InterfaceLogin
from tests.integration.arrange import arrange, chosen, factory_for

#: `app/setPreferences` 裡 Berth 唯一可以送的兩個鍵（brief §20.2）。
LOGIN_KEYS = frozenset({"web_ui_username", "web_ui_password"})

MAGNET = "magnet:?xt=urn:btih:4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b&dn=Show"


def foreign_keys(writes: Iterable[Mapping[str, Any]]) -> set[str]:
    """送進 `setPreferences` 的鍵裡，不是 WebUI 登入的那幾個。閘門要它是空的。"""
    return {key for write in writes for key in write} - LOGIN_KEYS


async def walk_the_wizard(
    session: AsyncSession, roots: dict[str, Path], origin: ServiceOrigin, login: InterfaceLogin
) -> FakeQbittorrentClient:
    """頁 2 套用、回頭重按，套件內再從設定頁換一次登入；頁 3 建 Route；送一筆單。"""
    await arrange(session, roots)
    base_url = (
        "http://qbittorrent:8080"
        if origin is ServiceOrigin.BUNDLED
        else "http://home-qbittorrent:8080"
    )
    setup = await read_settings(session, SetupSettings)
    setup.qbittorrent.steps = []
    setup.choices = {**setup.choices, ServiceKind.QBITTORRENT: chosen(origin, base_url)}
    await write_settings(session, setup)
    await write_settings(session, QbittorrentSettings(base_url=base_url))
    await session.commit()
    # 全域偏好是乾淨實例的樣子：每一個都與舊的「建議值」不同，寫了就看得到。
    qbittorrent = FakeQbittorrentClient(base_url=base_url)
    factory = factory_for(roots, qbittorrent=qbittorrent)

    if origin is ServiceOrigin.BUNDLED:
        await apply_qbittorrent(session, factory, login=login)
        await apply_qbittorrent(session, factory)
        await set_interface_login(
            session, factory, InterfaceLogin(username=login.username, password="Second-pass-2")
        )
    else:
        await apply_qbittorrent(session, factory)
        await apply_qbittorrent(session, factory)

    routes = await build_routes(session, factory, ())
    assert [row.health for row in routes.routes] == [HealthStatus.OK] * 3
    media = Media(
        id="tv:1",
        tmdb_id=1,
        kind=MediaKind.TV,
        title_en="Show",
        title_original="Show",
        year=2024,
        folder_name="Show (2024)",
    )
    session.add(media)
    await session.commit()
    await add_download(
        session,
        factory,
        source=JobSource(url=MAGNET, title="[Group] Show - 01 [1080p]"),
        media_id=media.id,
        route_id=next(row.id for row in routes.routes if row.slug == "anime"),
        user_id=None,
    )
    assert [row.category for row in qbittorrent.added] == ["berth-anime"]
    return qbittorrent


LOGIN = InterfaceLogin(username="labgate", password="Lab-gate-1")


@pytest.mark.parametrize("origin", [ServiceOrigin.BUNDLED, ServiceOrigin.EXISTING])
@pytest.mark.asyncio
async def test_the_wizard_writes_only_the_login_keys(
    session: AsyncSession, roots: dict[str, Path], origin: ServiceOrigin
) -> None:
    qbittorrent = await walk_the_wizard(session, roots, origin, LOGIN)

    assert foreign_keys(qbittorrent.writes) == set()
    if origin is ServiceOrigin.BUNDLED:
        assert {key for write in qbittorrent.writes for key in write} == LOGIN_KEYS
    else:
        assert qbittorrent.writes == []


@pytest.mark.asyncio
async def test_the_gate_turns_red_when_berth_writes_save_path(
    session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """變異：讓精靈把帳號那一筆送到 `save_path`，閘門要抓得到。"""
    monkeypatch.setattr(qbittorrent_service, "WEB_UI_USERNAME_KEY", "save_path")

    qbittorrent = await walk_the_wizard(session, roots, ServiceOrigin.BUNDLED, LOGIN)

    assert foreign_keys(qbittorrent.writes) == {"save_path"}


@pytest.mark.asyncio
async def test_the_gate_ignores_an_unrelated_rename(
    session: AsyncSession, roots: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """變異的另一面：換帳號、換 qBittorrent 預設帳號的名字，送的還是那兩個鍵，閘門不紅。"""
    monkeypatch.setattr(qbittorrent_service, "DEFAULT_WEB_UI_USERNAME", "root")

    qbittorrent = await walk_the_wizard(
        session,
        roots,
        ServiceOrigin.BUNDLED,
        InterfaceLogin(username="renamed-owner", password="Lab-gate-1"),
    )

    assert foreign_keys(qbittorrent.writes) == set()
