"""套件內 qBittorrent 換了 WebUI port 之後（票 06b）。

`QBITTORRENT_WEBUI_PORT` 內外兩側一起換（Host 檢查連 port 都比對，plan §9.2），所以 compose
內網上那一台也不在 8080 了。選了套件內，測試要照 Berth 的設定去敲，之後的步驟連的也是那一台
（M4 票 15 起位址在選的時候記下）。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import respx
from sqlalchemy.ext.asyncio import AsyncSession

from berth.config import load_config
from berth.domain import ConnectionState, ServiceKind, ServiceOrigin
from berth.models import SetupSettings
from berth.services.clients import HttpServiceClientFactory, bundled_services
from berth.services.qbittorrent import read_qbittorrent_diff
from berth.services.routes import build_routes
from berth.services.settings import read_settings
from berth.services.setup import choose_service
from tests.conftest import read_fixture
from tests.integration.arrange import arrange, factory_for, own

MOVED = "http://qbittorrent:18080"


@respx.mock
@pytest.mark.asyncio
async def test_choosing_bundled_knocks_on_the_port_berth_was_given(
    session: AsyncSession, tmp_path: Path
) -> None:
    respx.get(f"{MOVED}/api/v2/app/version").respond(
        200, text=read_fixture("http/qbittorrent/app-version.5.2.3.txt")
    )
    respx.get(f"{MOVED}/api/v2/app/webapiVersion").respond(
        200, text=read_fixture("http/qbittorrent/app-webapiversion.5.2.3.txt")
    )
    config = load_config({"EXT_ROOT": str(tmp_path), "QBITTORRENT_WEBUI_PORT": "18080"})
    await own(session)

    await choose_service(
        session,
        HttpServiceClientFactory(),
        bundled_services(config, {}),
        ServiceKind.QBITTORRENT,
        ServiceOrigin.BUNDLED,
    )

    choice = (await read_settings(session, SetupSettings)).choices[ServiceKind.QBITTORRENT]
    assert choice.base_url == MOVED
    assert choice.test is not None and choice.test.state is ConnectionState.OK


async def chosen_at(session: AsyncSession, roots: dict[str, Path], base_url: str) -> None:
    """選了套件內，而那一台在 `base_url`。"""
    config = load_config(
        {"EXT_ROOT": str(roots["library"].parent), "QBITTORRENT_WEBUI_PORT": "18080"}
    )
    await arrange(session, roots)
    factory = factory_for(roots)
    await choose_service(
        session,
        factory,
        bundled_services(config, {}),
        ServiceKind.QBITTORRENT,
        ServiceOrigin.BUNDLED,
    )
    await session.commit()
    assert (await read_settings(session, SetupSettings)).choices[
        ServiceKind.QBITTORRENT
    ].base_url == base_url


@pytest.mark.asyncio
async def test_the_qbittorrent_page_connects_to_the_chosen_one(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    await chosen_at(session, roots, MOVED)
    factory = factory_for(roots)

    status = await read_qbittorrent_diff(session, factory)

    assert (status.base_url, factory.qbittorrent_.base_url) == (MOVED, MOVED)


@pytest.mark.asyncio
async def test_route_checks_connect_to_the_chosen_one(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    await chosen_at(session, roots, MOVED)
    factory = factory_for(roots)

    await build_routes(session, factory, ())

    assert factory.qbittorrent_.base_url == MOVED
