"""位址的協定寫錯不是「連不上」（M4 票 25，實測 E2-06～09）。

https 填到只講 http 的 port 有兩種樣子（berth image 對 berth-existing 實測，brief §20.14）：
Jellyfin、Prowlarr 回一個 HTTP 400，TLS 握手讀到它而 `WRONG_VERSION_NUMBER`；qBittorrent 的 WebUI
不回、等著 HTTP 請求，握手逾時（鏈上是 `SSLWantReadError`）。位址沒寫 `http://`，httpx 當場丟
`UnsupportedProtocol`。原本三者都歸成 `unreachable`、畫面叫人確認 port。這裡用正式的 HTTP adapter
（`HttpServiceClientFactory`）對本機幾台假伺服器，走精靈選既有服務的那一條路；逾時那一種直接開
`HttpSession`，不必等滿 5 秒。
"""

from __future__ import annotations

import asyncio
import socket
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import HttpSession, SchemeMismatchError, ServiceUnavailableError
from berth.domain import ConnectionReason, ConnectionState, ServiceKind, ServiceOrigin
from berth.services.clients import BundledServices, HttpServiceClientFactory
from berth.services.setup import ServiceConnection, choose_service
from tests.integration.arrange import own
from tests.integration.factories import COMPOSE

BUNDLED = BundledServices(targets=COMPOSE, prowlarr_api_key="")


async def _answer(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """只講 http 的那一台：讀到什麼都回一個 200（TLS 的 ClientHello 也是，那正是錯配的樣子）。"""
    await reader.read(4096)
    writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 6\r\nConnection: close\r\n\r\nv5.2.3")
    await writer.drain()
    writer.close()


async def _wait_for_a_request(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """qBittorrent 的 WebUI 對 ClientHello 的樣子：讀了，等一個 HTTP 請求，什麼都不回。"""
    await reader.read(4096)
    await asyncio.sleep(2)
    writer.close()


@pytest_asyncio.fixture
async def plain_http() -> AsyncIterator[int]:
    server = await asyncio.start_server(_answer, "127.0.0.1", 0)
    port: int = server.sockets[0].getsockname()[1]
    async with server:
        yield port


@pytest_asyncio.fixture
async def silent_http() -> AsyncIterator[int]:
    server = await asyncio.start_server(_wait_for_a_request, "127.0.0.1", 0)
    port: int = server.sockets[0].getsockname()[1]
    async with server:
        yield port


def _closed_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


async def _test(session: AsyncSession, base_url: str) -> tuple[ConnectionState, ConnectionReason]:
    await own(session)
    status = await choose_service(
        session,
        HttpServiceClientFactory(),
        BUNDLED,
        ServiceKind.QBITTORRENT,
        ServiceOrigin.EXISTING,
        ServiceConnection(base_url=base_url),
    )
    row = next(row for row in status.services if row.kind is ServiceKind.QBITTORRENT)
    assert row.state is not None
    assert row.reason is not None
    return row.state, row.reason


@pytest.mark.asyncio
async def test_https_to_a_port_that_speaks_http(session: AsyncSession, plain_http: int) -> None:
    assert await _test(session, f"https://127.0.0.1:{plain_http}") == (
        ConnectionState.FAILED,
        ConnectionReason.SCHEME_MISMATCH,
    )


@pytest.mark.asyncio
async def test_https_to_a_port_that_waits_for_an_http_request(silent_http: int) -> None:
    async with HttpSession(f"https://127.0.0.1:{silent_http}", timeout=0.5) as session:
        with pytest.raises(SchemeMismatchError):
            await session.get("/api/v2/app/version")


@pytest.mark.asyncio
async def test_plain_http_that_does_not_answer_in_time_is_still_unreachable(
    silent_http: int,
) -> None:
    """逾時本身不是協定錯配：`http://` 打過去、對方不回，照舊是連不上（讀逾時，不在握手裡）。"""
    async with HttpSession(f"http://127.0.0.1:{silent_http}", timeout=0.5) as session:
        with pytest.raises(ServiceUnavailableError):
            await session.get("/api/v2/app/version")


@pytest.mark.parametrize("written", ["127.0.0.1:{port}", "localhost:{port}"])
@pytest.mark.asyncio
async def test_an_address_without_a_scheme(
    session: AsyncSession, plain_http: int, written: str
) -> None:
    assert await _test(session, written.format(port=plain_http)) == (
        ConnectionState.FAILED,
        ConnectionReason.SCHEME_MISSING,
    )


@pytest.mark.asyncio
async def test_a_port_nobody_listens_on_is_still_unreachable(session: AsyncSession) -> None:
    assert await _test(session, f"http://127.0.0.1:{_closed_port()}") == (
        ConnectionState.FAILED,
        ConnectionReason.UNREACHABLE,
    )
