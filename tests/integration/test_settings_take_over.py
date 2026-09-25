"""精靈跑完之後，設定頁經 `setup/*` 改東西（票 06i）。

設定的索引站 / TMDB / qBittorrent 那幾頁送的是精靈的同一批命令與端點（plan §6）。這裡驗的是
那個決定真的成立：精靈跑完之後管理員照樣打得動、命令照樣做事、而且**不會把精靈拉回未完成**
——移除最後一站會讓精靈的步驟退回第 6 步，但 `completed` 是另一個位元，不跟著退。
一般使用者一律 403，規則在門禁（`api/gate.py`），整張表在 `test_auth_api.py`。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from berth.adapters.indexer import IndexerResult
from berth.adapters.indexer.fake import FakeIndexerSearch
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.adapters.tmdb import TmdbConfiguration
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.api.deps import get_client_factory
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.domain import DetectionReason, ServiceKind, ServiceOrigin
from berth.main import create_app
from berth.models import (
    IndexerSettings,
    JellyfinSettings,
    QbittorrentSettings,
    ServiceProbe,
    SetupSettings,
    TmdbSettings,
)
from berth.services.settings import read_settings, write_settings
from tests.conftest import TMDB_API_KEY
from tests.integration.factories import FakeClientFactory

BROWSER = {CSRF_HEADER: "XMLHttpRequest"}
ADMIN = {"username": "skipper", "password": "harbour"}
DECKHAND = {"username": "deckhand", "password": "rope"}
NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)


@pytest.fixture
def factory() -> FakeClientFactory:
    release = IndexerResult(title="[SubsPlease] Frieren - 28 (1080p)", indexer="Nyaa.si")
    return FakeClientFactory(
        jellyfin=FakeJellyfinClient(
            startup_wizard_completed=True,
            admin=(ADMIN["username"], ADMIN["password"]),
            users={DECKHAND["username"]: DECKHAND["password"]},
        ),
        qbittorrent=FakeQbittorrentClient(base_url="http://nas:8080"),
        tmdb=FakeTmdbClient(
            configuration=TmdbConfiguration(image_base_url="https://image.tmdb.org/t/p/")
        ),
        indexer_search=FakeIndexerSearch(results=(release,)),
    )


@pytest.fixture
def client(config: Config, tmp_path: Path, factory: FakeClientFactory) -> Iterator[TestClient]:
    """精靈跑完的一台：套件內的 Prowlarr、使用者自己的 qBittorrent。"""
    app = create_app(replace(config, web_root=tmp_path / "never-built"))
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app) as running:
        _finished_wizard(running)
        yield running


def post(client: TestClient, path: str, body: object = None) -> httpx.Response:
    response: httpx.Response = client.post(path, json=body, headers=BROWSER)
    return response


def sign_in(client: TestClient, credentials: dict[str, str]) -> None:
    assert post(client, "/api/auth/login", credentials).status_code == 200


def still_complete(client: TestClient) -> bool:
    completed: bool = client.get("/api/health").json()["setup_completed"]
    return completed


def test_an_administrator_adds_a_site_tries_it_and_removes_it(client: TestClient) -> None:
    sign_in(client, ADMIN)

    added = post(client, "/api/setup/indexers/apply", {"indexers": ["nyaasi", "mikan"]})
    assert added.status_code == 200
    present = {row["definition_name"]: row["indexer_id"] for row in added.json()["options"]}
    assert present["nyaasi"] is not None
    assert present["mikan"] is not None

    trial = client.get("/api/setup/indexers/search", params={"query": ""})
    assert trial.status_code == 200
    assert {row["definition_name"] for row in trial.json()["sites"]} == {"nyaasi", "mikan"}

    removed = client.delete(f"/api/setup/indexers/{present['mikan']}", headers=BROWSER)
    assert removed.status_code == 200
    assert [row["definition_name"] for row in removed.json()["options"] if row["present"]] == [
        "nyaasi"
    ]
    assert still_complete(client)


def test_removing_every_site_does_not_reopen_the_wizard(client: TestClient) -> None:
    """精靈的步驟由狀態導出、會退回第 6 步；完成與否是另一個位元，設定頁的修改不碰它。"""
    sign_in(client, ADMIN)
    added = post(client, "/api/setup/indexers/apply", {"indexers": ["nyaasi"]}).json()
    (only,) = [row["indexer_id"] for row in added["options"] if row["present"]]

    assert client.delete(f"/api/setup/indexers/{only}", headers=BROWSER).status_code == 200

    assert still_complete(client)
    assert client.get("/api/setup/status").json()["completed"] is True


def test_an_administrator_swaps_the_tmdb_key(
    client: TestClient, factory: FakeClientFactory
) -> None:
    sign_in(client, ADMIN)

    response = post(client, "/api/setup/tmdb/test", {"api_key": TMDB_API_KEY})

    assert response.status_code == 200
    assert response.json()["verified"] is True
    assert factory.tmdb_.credential == TMDB_API_KEY
    assert still_complete(client)


def test_an_administrator_changes_the_qbittorrent_credentials(
    client: TestClient, factory: FakeClientFactory
) -> None:
    sign_in(client, ADMIN)

    response = post(
        client,
        "/api/setup/services/qbittorrent",
        {"base_url": "http://nas:8080", "username": "admin", "password": "new-secret"},
    )

    assert response.status_code == 200
    (qbittorrent,) = [row for row in response.json()["services"] if row["kind"] == "qbittorrent"]
    assert (qbittorrent["origin"], qbittorrent["reason"]) == ("existing", "connected")
    assert factory.qbittorrent_.logins[-1] == ("admin", "new-secret")
    stored = asyncio.run(_read_qbittorrent(client))
    assert (stored.username, stored.password) == ("admin", "new-secret")
    assert still_complete(client)


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/api/setup/indexers/apply", {"indexers": ["nyaasi"]}),
        ("GET", "/api/setup/indexers/search?query=", None),
        ("DELETE", "/api/setup/indexers/1", None),
        ("POST", "/api/setup/tmdb/test", {"api_key": TMDB_API_KEY}),
        ("POST", "/api/setup/services/qbittorrent", {"base_url": "http://nas:8080"}),
    ],
)
def test_an_ordinary_user_cannot_change_any_of_it(
    client: TestClient, method: str, path: str, body: object
) -> None:
    sign_in(client, DECKHAND)

    response = client.request(method, path, json=body, headers=BROWSER)

    assert response.status_code == 403


async def _read_qbittorrent(client: TestClient) -> QbittorrentSettings:
    # `TestClient.app` 是 Starlette 的 `ASGIApp`，型別上沒有 `state`（實際是 FastAPI）。
    async with client.app.state.session_factory() as session:  # type: ignore[attr-defined]
        return await read_settings(session, QbittorrentSettings)


def _finished_wizard(client: TestClient) -> None:
    """把 DB 推到「精靈跑完」：套件內 Prowlarr（讀得到 key）、既有 qBittorrent、TMDB 驗過。"""

    async def arrange() -> None:
        # 同上：`TestClient.app` 型別上沒有 `state`。
        factory = client.app.state.session_factory  # type: ignore[attr-defined]
        async with factory() as session:
            setup = await read_settings(session, SetupSettings)
            setup.completed = True
            setup.services = {
                ServiceKind.JELLYFIN: ServiceProbe(
                    origin=ServiceOrigin.EXISTING,
                    reason=DetectionReason.CONNECTED,
                    base_url="http://jellyfin:8096",
                    checked_at=NOW,
                    configured=True,
                ),
                ServiceKind.QBITTORRENT: ServiceProbe(
                    origin=ServiceOrigin.EXISTING,
                    reason=DetectionReason.CONNECTED,
                    base_url="http://nas:8080",
                    checked_at=NOW,
                    configured=True,
                ),
                ServiceKind.PROWLARR: ServiceProbe(
                    origin=ServiceOrigin.BUNDLED,
                    reason=DetectionReason.NO_INDEXERS,
                    base_url="http://prowlarr:9696",
                    checked_at=NOW,
                ),
            }
            await write_settings(session, setup)
            await write_settings(
                session, JellyfinSettings(base_url="http://jellyfin:8096", api_key="the-key")
            )
            await write_settings(
                session,
                QbittorrentSettings(base_url="http://nas:8080", username="admin", password="old"),
            )
            await write_settings(session, IndexerSettings(api_key="0" * 31 + "1"))
            await write_settings(session, TmdbSettings(api_key="old-key"))
            await session.commit()

    asyncio.run(arrange())
