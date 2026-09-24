"""`GET /api/events/stream`（plan §6 events 群組、票 10 驗收）。

三件事：**誰進得來**（門禁沒有為它開洞）、**推出去的形狀**（前端據此讓 query 失效），
以及**關掉之後訂閱要收乾淨**（斷線的分頁不能留下一條永遠沒人讀的佇列）。

讀的是真的位元組而不是產生器：`EventSourceResponse` 自己組 `event:` / `data:` 那兩行，
而那正是瀏覽器的 `EventSource` 讀的東西——繞過它的測試會在換掉 SSE 實作時仍然綠著。

**串流不能走 `TestClient`**：它把整個回應收完才回來，而 SSE 的回應永遠不會結束
（實測對這支端點直接卡住）。所以這裡自己驅動 ASGI：`TestClient` 只用來跑 lifespan
與登入拿 cookie，串流由一組最小的 `receive` / `send` 拉到第一筆事件為止。
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator, MutableMapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from berth.api.deps import get_client_factory
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.domain import JobState
from berth.main import create_app
from berth.models import TmdbSettings
from berth.services.events import JOB_EVENT, EventHub, JobSignal
from berth.services.routes import build_routes
from berth.services.settings import write_settings
from berth.services.setup import complete_setup
from tests.conftest import TMDB_API_KEY
from tests.integration.arrange import arrange, bundled_libraries, factory_for, fake_jellyfin
from tests.integration.factories import FakeClientFactory

BROWSER = {CSRF_HEADER: "XMLHttpRequest"}
ADMIN = {"username": "skipper", "password": "harbour"}

STREAM = "/api/events/stream"


@pytest.fixture
def client(config: Config, tmp_path: Path, roots: dict[str, Path]) -> Iterator[TestClient]:
    factory = factory_for(
        roots,
        jellyfin=fake_jellyfin(
            bundled_libraries(roots["library"]), admin=(ADMIN["username"], ADMIN["password"])
        ),
    )
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app) as running:
        _seed(running, roots, factory)
        yield running


def _seed(client: TestClient, roots: dict[str, Path], factory: FakeClientFactory) -> None:
    async def run() -> None:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            await arrange(session, roots)
            await write_settings(
                session,
                TmdbSettings(api_key=TMDB_API_KEY, image_base_url="https://image.tmdb.org/t/p/"),
            )
            await session.commit()
            await build_routes(session, factory, ())
            await complete_setup(session)

    asyncio.run(run())


def hub_of(client: TestClient) -> EventHub:
    events: EventHub = client.app.state.events  # type: ignore[attr-defined]
    return events


def test_anonymous_visitors_do_not_get_a_stream(client: TestClient) -> None:
    """`/api/events` 不在門禁的白名單上，所以什麼都不必做它就在門後（`api/gate.py`）。"""
    assert client.get(STREAM).status_code == 401


def test_a_signed_in_page_reads_the_job_signals(client: TestClient) -> None:
    """推出去的是**提示不是真相**：身分加上一眼看得到的兩格，前端據此重問一次。"""
    client.post("/api/auth/login", json=ADMIN, headers=BROWSER)
    hub = hub_of(client)

    status, headers, body = asyncio.run(
        _stream_once(client, hub, JobSignal(hash="abc", state=JobState.DOWNLOADING, progress=0.25))
    )

    assert status == 200
    assert headers[b"content-type"].startswith(b"text/event-stream")
    lines = [row for row in body.decode().splitlines() if row and not row.startswith(":")]
    assert f"event: {JOB_EVENT}" in lines
    data = next(row for row in lines if row.startswith("data:"))[len("data:") :]
    assert json.loads(data) == {"hash": "abc", "state": "downloading", "progress": 0.25}


def test_the_stream_is_never_compressed(client: TestClient) -> None:
    """gzip 會把事件收在壓縮器的緩衝裡，前端要等到湊滿一塊才看得到（M3 票 06 加壓縮時）。

    Starlette 的 `GZipMiddleware` 預設就跳過 `text/event-stream`；這一條守的是換掉它或改參數的
    那一天。
    """
    client.post("/api/auth/login", json=ADMIN, headers=BROWSER)
    hub = hub_of(client)

    _, headers, body = asyncio.run(
        _stream_once(
            client,
            hub,
            JobSignal(hash="abc", state=JobState.DOWNLOADING, progress=0.25),
            accept_encoding="gzip",
        )
    )

    assert b"content-encoding" not in headers
    assert f"event: {JOB_EVENT}".encode() in body


def test_closing_the_page_takes_the_subscription_with_it(client: TestClient) -> None:
    """一條沒人讀的佇列會在每一輪輪詢時被寫進去，永遠不會有人清掉它。"""
    client.post("/api/auth/login", json=ADMIN, headers=BROWSER)
    hub = hub_of(client)

    asyncio.run(
        _stream_once(client, hub, JobSignal(hash="abc", state=JobState.DOWNLOADING, progress=0.0))
    )

    assert hub.subscribers == 0


async def _stream_once(
    client: TestClient, hub: EventHub, signal: JobSignal, *, accept_encoding: str = ""
) -> tuple[int, dict[bytes, bytes], bytes]:
    """把 SSE 端點拉到第一筆事件為止，然後掛斷。

    `send` 收到第一段 body 就讓 `receive` 交出 `http.disconnect`，端點因此走的是正常
    斷線那條路徑——「訂閱有沒有收乾淨」測的就是它。
    """
    scope: dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": STREAM,
        "raw_path": STREAM.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"cookie", _cookie(client).encode()),
            (b"host", b"testserver"),
            *([(b"accept-encoding", accept_encoding.encode())] if accept_encoding else []),
        ],
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
    }
    disconnected = asyncio.Event()
    collected: list[dict[str, Any]] = []

    async def receive() -> MutableMapping[str, Any]:
        await disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(message: MutableMapping[str, Any]) -> None:
        collected.append(dict(message))
        if message["type"] == "http.response.body" and message.get("body"):
            disconnected.set()

    # **訂閱之後才發佈**：hub 沒有補送，所以在連線建立之前丟出去的那一筆誰都收不到——
    # 這正是「推播是提示不是真相」的另一面，前端每次連上都會重問一次。
    async def drive() -> None:
        await client.app(scope, receive, send)

    request = asyncio.create_task(drive())
    while hub.subscribers == 0:
        await asyncio.sleep(0.01)
    hub.publish(signal)
    await asyncio.wait_for(request, timeout=10)

    start = next(row for row in collected if row["type"] == "http.response.start")
    body = b"".join(row.get("body", b"") for row in collected)
    return int(start["status"]), dict(start["headers"]), body


def _cookie(client: TestClient) -> str:
    return "; ".join(f"{name}={value}" for name, value in client.cookies.items())
