"""套件內 qBittorrent 換了 WebUI port 之後（票 06b）。

`QBITTORRENT_WEBUI_PORT` 內外兩側一起換（Host 檢查連 port 都比對，plan §9.2），所以 compose
內網上那一台也不在 8080 了。偵測要照 Berth 的設定去敲，之後的步驟連的是偵測記下的那一台。
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
import respx
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.config import load_config
from berth.domain import DetectionReason, ServiceKind, ServiceOrigin
from berth.models import QbittorrentSettings, SetupSettings
from berth.services.clients import build_setup_probes, close_setup_probes
from berth.services.qbittorrent import read_qbittorrent_diff
from berth.services.routes import build_routes
from berth.services.settings import read_settings, write_settings
from berth.services.setup import detect_services
from tests.conftest import read_fixture
from tests.integration.arrange import arrange, factory_for

MOVED = "http://qbittorrent:18080"


@respx.mock
@pytest.mark.asyncio
async def test_detection_knocks_on_the_port_berth_was_given(
    session: AsyncSession, tmp_path: Path
) -> None:
    respx.get(f"{MOVED}/api/v2/app/version").respond(
        200, text=read_fixture("http/qbittorrent/app-version.5.2.3.txt")
    )
    respx.get(f"{MOVED}/api/v2/app/webapiVersion").respond(
        200, text=read_fixture("http/qbittorrent/app-webapiversion.5.2.3.txt")
    )
    config = load_config({"EXT_ROOT": str(tmp_path), "QBITTORRENT_WEBUI_PORT": "18080"})
    real = build_setup_probes(config, {})
    probes = dataclasses.replace(real, jellyfin=FakeJellyfinClient(), prowlarr=FakeProwlarrClient())
    try:
        await detect_services(session, probes)
    finally:
        await close_setup_probes(real)

    probe = (await read_settings(session, SetupSettings)).services[ServiceKind.QBITTORRENT]
    assert (probe.origin, probe.reason, probe.base_url) == (
        ServiceOrigin.BUNDLED,
        DetectionReason.ANONYMOUS_OK,
        MOVED,
    )


async def detected_at(session: AsyncSession, roots: dict[str, Path], base_url: str) -> None:
    """偵測判成套件內、記下 `base_url`，而第 4 步還沒把位址寫進 `QbittorrentSettings`。"""
    await arrange(session, roots)
    setup = await read_settings(session, SetupSettings)
    probe = setup.services[ServiceKind.QBITTORRENT]
    setup.services = {
        **setup.services,
        ServiceKind.QBITTORRENT: probe.model_copy(update={"base_url": base_url}),
    }
    await write_settings(session, setup)
    await write_settings(session, QbittorrentSettings())
    await session.commit()


@pytest.mark.asyncio
async def test_the_qbittorrent_step_connects_to_the_one_detection_found(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    await detected_at(session, roots, MOVED)
    factory = factory_for(roots)

    status = await read_qbittorrent_diff(session, factory)

    assert (status.base_url, factory.qbittorrent_.base_url) == (MOVED, MOVED)


@pytest.mark.asyncio
async def test_route_checks_connect_to_the_one_detection_found(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    await detected_at(session, roots, MOVED)
    factory = factory_for(roots)

    await build_routes(session, factory, ())

    assert factory.qbittorrent_.base_url == MOVED
