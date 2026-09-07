"""三個 adapter 對 `tests/fixtures/http/` 錄製回應的契約測試（plan §1.3、票 05）。

錄製來源與日期見 `tests/fixtures/http/README.md`。這裡驗的是「真服務回這個，adapter 解成那個」，
所以斷言貼著錄下來的值，不重寫一份假的 payload。
"""

from __future__ import annotations

import socket

import httpx
import pytest
import respx

from berth.adapters.http import (
    AuthFailedError,
    ProtocolMismatchError,
    ServiceNotDeployedError,
    ServiceUnavailableError,
)
from berth.adapters.jellyfin.client import HttpJellyfinClient
from berth.adapters.prowlarr.client import HttpProwlarrClient
from berth.adapters.qbittorrent.client import HttpQbittorrentClient
from tests.conftest import read_fixture

JELLYFIN_URL = "http://jellyfin:8096"
QBITTORRENT_URL = "http://qbittorrent:8080"
PROWLARR_URL = "http://prowlarr:9696"


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_public_info_before_startup_wizard() -> None:
    respx.get(f"{JELLYFIN_URL}/System/Info/Public").respond(
        200, text=read_fixture("http/jellyfin/system-info-public.setup-pending.json")
    )

    client = HttpJellyfinClient(JELLYFIN_URL)
    try:
        info = await client.public_info()
    finally:
        await client.aclose()

    assert info.startup_wizard_completed is False
    assert info.version == "10.11.11"


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_public_info_after_startup_wizard() -> None:
    respx.get(f"{JELLYFIN_URL}/System/Info/Public").respond(
        200, text=read_fixture("http/jellyfin/system-info-public.configured.json")
    )

    client = HttpJellyfinClient(JELLYFIN_URL)
    try:
        info = await client.public_info()
    finally:
        await client.aclose()

    assert info.startup_wizard_completed is True


@respx.mock
@pytest.mark.asyncio
async def test_jellyfin_rejects_a_payload_from_something_else() -> None:
    respx.get(f"{JELLYFIN_URL}/System/Info/Public").respond(200, json={"hello": "world"})

    client = HttpJellyfinClient(JELLYFIN_URL)
    with pytest.raises(ProtocolMismatchError):
        await client.public_info()
    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_version_without_credentials() -> None:
    respx.get(f"{QBITTORRENT_URL}/api/v2/app/version").respond(
        200, text=read_fixture("http/qbittorrent/app-version.txt")
    )
    respx.get(f"{QBITTORRENT_URL}/api/v2/app/webapiVersion").respond(
        200, text=read_fixture("http/qbittorrent/app-webapiversion.txt")
    )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        version = await client.version()
    finally:
        await client.aclose()

    assert version.app == "v5.2.3"
    assert version.webapi == "2.15.1"


@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_forbidden_maps_to_auth_failed() -> None:
    respx.get(f"{QBITTORRENT_URL}/api/v2/app/version").respond(
        403, text=read_fixture("http/qbittorrent/app-version.forbidden.txt")
    )

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    with pytest.raises(AuthFailedError):
        await client.version()
    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_qbittorrent_sends_referer_matching_the_base_url() -> None:
    """CSRF：送了 `Referer` 就必須與 Host 一致，不一致回 401（brief §20.7）。"""
    route = respx.get(f"{QBITTORRENT_URL}/api/v2/app/version").respond(200, text="v5.2.3")
    respx.get(f"{QBITTORRENT_URL}/api/v2/app/webapiVersion").respond(200, text="2.15.1")

    client = HttpQbittorrentClient(QBITTORRENT_URL)
    try:
        await client.version()
    finally:
        await client.aclose()

    assert route.calls.last.request.headers["Referer"] == QBITTORRENT_URL


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_ping_is_anonymous() -> None:
    respx.get(f"{PROWLARR_URL}/ping").respond(200, text=read_fixture("http/prowlarr/ping.json"))

    client = HttpProwlarrClient(PROWLARR_URL)
    try:
        await client.ping()
    finally:
        await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_indexers_empty_on_a_fresh_install() -> None:
    respx.get(f"{PROWLARR_URL}/api/v1/indexer").respond(
        200, text=read_fixture("http/prowlarr/indexer.empty.json")
    )

    client = HttpProwlarrClient(PROWLARR_URL, "key")
    try:
        assert await client.indexers() == []
    finally:
        await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_indexers_parsed_from_a_configured_install() -> None:
    route = respx.get(f"{PROWLARR_URL}/api/v1/indexer").respond(
        200, text=read_fixture("http/prowlarr/indexer.configured.json")
    )

    client = HttpProwlarrClient(PROWLARR_URL, "the-key")
    try:
        indexers = await client.indexers()
    finally:
        await client.aclose()

    assert [(row.id, row.name, row.enabled) for row in indexers] == [(1, "Nyaa.si", True)]
    assert route.calls.last.request.headers["X-Api-Key"] == "the-key"


@respx.mock
@pytest.mark.asyncio
async def test_prowlarr_without_api_key_maps_to_auth_failed() -> None:
    respx.get(f"{PROWLARR_URL}/api/v1/indexer").respond(401)

    client = HttpProwlarrClient(PROWLARR_URL)
    with pytest.raises(AuthFailedError):
        await client.indexers()
    await client.aclose()


@pytest.mark.asyncio
async def test_unresolvable_host_is_not_deployed(monkeypatch: pytest.MonkeyPatch) -> None:
    """主機名解不到 = 服務不在 compose 裡，不是「還沒起來」（plan §9.3 第 2 步）。

    這條不走 respx：它會把 side effect 例外的 `__cause__` 換成自己的 Route 物件，
    而分類靠的正是 `__cause__` 鏈。真實鏈是 httpx.ConnectError → httpcore → socket.gaierror。
    """
    chained = httpx.ConnectError("nodename nor servname provided")
    chained.__cause__ = socket.gaierror(-2, "Name or service not known")

    async def raise_dns_failure(*_args: object, **_kwargs: object) -> httpx.Response:
        raise chained

    monkeypatch.setattr(httpx.AsyncClient, "request", raise_dns_failure)

    client = HttpJellyfinClient(JELLYFIN_URL)
    with pytest.raises(ServiceNotDeployedError):
        await client.public_info()
    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_connection_refused_is_unavailable() -> None:
    respx.get(f"{JELLYFIN_URL}/System/Info/Public").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    client = HttpJellyfinClient(JELLYFIN_URL)
    with pytest.raises(ServiceUnavailableError):
        await client.public_info()
    await client.aclose()


@respx.mock
@pytest.mark.asyncio
async def test_timeout_is_unavailable() -> None:
    respx.get(f"{JELLYFIN_URL}/System/Info/Public").mock(
        side_effect=httpx.ConnectTimeout("timed out")
    )

    client = HttpJellyfinClient(JELLYFIN_URL)
    with pytest.raises(ServiceUnavailableError):
        await client.public_info()
    await client.aclose()
