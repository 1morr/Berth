"""BTH 4 只接 Prowlarr（M4 票 37、brief §19 D3）：存著 Torznab 端點的安裝升上來之後怎麼樣。

設定是 JSON，多出來的 `kind` 讀得進來（`SettingsGroup` 忽略多餘的鍵）；但那條位址是 Jackett 之類的
Torznab 網址，當成 Prowlarr 去連只會在頁 4 與搜尋上紅得莫名其妙。migration 把它清掉，頁 4 回到
待處理，搜尋說「還沒接」。
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import AsyncIterator, Iterator
from contextlib import closing, contextmanager
from dataclasses import replace
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from berth.api.deps import get_client_factory
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.db import create_engine, create_session_factory
from berth.db.migrate import alembic_config
from berth.domain import (
    PROWLARR_LOGIN_STEP,
    ConnectionReason,
    IndexerProblem,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.main import create_app
from berth.models import IndexerSettings, SetupSettings, SetupStep, TmdbSettings
from berth.services.indexer import read_indexer_status
from berth.services.routes import build_routes
from berth.services.search import search_torrents
from berth.services.settings import read_settings, write_settings
from berth.services.setup import STEP_COMPLETE, STEP_INDEXER, complete_setup, read_status
from tests.conftest import TMDB_API_KEY
from tests.integration.arrange import (
    arrange,
    bundled_libraries,
    chosen,
    factory_for,
    fake_jellyfin,
)
from tests.integration.factories import FakeClientFactory

pytestmark = pytest.mark.asyncio

#: 拿掉 Torznab 之前的最後一版。
BEFORE = "f3c9a1d6b2e8"
JACKETT = "http://jackett:9117/api/v2.0/indexers/all/results/torznab/api"


@pytest_asyncio.fixture
async def before(config: Config) -> AsyncIterator[AsyncEngine]:
    """停在 `BEFORE` 的資料庫。"""
    config.config_root.mkdir(parents=True, exist_ok=True)
    engine = create_engine(config)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(_upgrade_to, BEFORE)
        yield engine
    finally:
        await engine.dispose()


async def _finished_wizard(
    engine: AsyncEngine, roots: dict[str, Path], factory: FakeClientFactory
) -> None:
    """精靈跑完、頁 4 接的是套件內 Prowlarr（`arrange` 的那一份）。"""
    async with create_session_factory(engine)() as session:
        await arrange(session, roots)
        await write_settings(session, TmdbSettings(api_key=TMDB_API_KEY))
        await session.commit()
        await build_routes(session, factory, ())
        status = await complete_setup(session)
        assert status.current_step == STEP_COMPLETE


async def _point_at_jackett(engine: AsyncEngine) -> None:
    """頁 4 改接 Jackett：舊程式的既有表單選了 Torznab 測過之後留下的樣子。"""
    async with create_session_factory(engine)() as session:
        setup = await read_settings(session, SetupSettings)
        setup.choices = {
            **setup.choices,
            ServiceKind.PROWLARR: chosen(ServiceOrigin.EXISTING, JACKETT),
        }
        setup.indexer.steps = [SetupStep(key="torznab", status=StepStatus.OK, detail="Jackett")]
        setup.indexer.web_ui_username = ""
        setup.indexer.web_ui_password_hash = ""
        await write_settings(session, setup)
        await session.commit()
    _write_raw(
        engine, "services.indexer", {"kind": "torznab", "base_url": JACKETT, "api_key": "theirs"}
    )


async def test_a_torznab_endpoint_is_cleared_and_page_4_waits(
    before: AsyncEngine, config: Config, tmp_path: Path, roots: dict[str, Path]
) -> None:
    factory = factory_for(
        roots,
        jellyfin=fake_jellyfin(bundled_libraries(roots["library"]), admin=("skipper", "harbour")),
    )
    await _finished_wizard(before, roots, factory)
    await _point_at_jackett(before)

    async with before.begin() as connection:
        await connection.run_sync(_upgrade_to, "head")

    async with create_session_factory(before)() as session:
        status = await read_status(session)
        indexer = await read_indexer_status(session, factory)
        searched = await search_torrents(session, factory, media_id="tv:120089")
        settings = await read_settings(session, IndexerSettings)

    assert status.current_step == STEP_INDEXER
    assert ServiceKind.PROWLARR not in {view.kind for view in status.services}
    assert (indexer.origin, indexer.steps, indexer.skipped) == (None, (), False)
    assert searched.problem is IndexerProblem.NOT_CONFIGURED
    assert (settings.base_url, settings.api_key) == ("", "")
    assert "jackett" not in json.dumps(_read_raw(before))

    # 經過 HTTP 也一樣：搜尋是 200 加「還沒接」，不是 500。
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app, headers={CSRF_HEADER: "XMLHttpRequest"}) as client:
        signed = client.post("/api/auth/login", json={"username": "skipper", "password": "harbour"})
        assert signed.status_code == 200
        response = client.get("/api/search?media=tv:120089")
    assert response.status_code == 200
    assert response.json()["problem"] == "not_configured"


async def test_a_prowlarr_install_only_loses_the_kind_key(
    before: AsyncEngine, roots: dict[str, Path]
) -> None:
    """接 Prowlarr 的安裝一個字都不變，只少了已經沒有意義的 `kind`。"""
    factory = factory_for(roots)
    await _finished_wizard(before, roots, factory)
    # 舊程式寫下的樣子：`kind` 一律存著。
    _write_raw(
        before,
        "services.indexer",
        {"kind": "prowlarr", "base_url": "http://prowlarr:9696", "api_key": "key-prowlarr-0"},
    )
    rows = _read_raw(before)

    async with before.begin() as connection:
        await connection.run_sync(_upgrade_to, "head")

    upgraded = _read_raw(before)
    assert upgraded["services.indexer"] == {
        "base_url": "http://prowlarr:9696",
        "api_key": "key-prowlarr-0",
    }
    assert upgraded["setup"] == rows["setup"]
    async with create_session_factory(before)() as session:
        setup = await read_settings(session, SetupSettings)
        assert (await read_status(session)).current_step == STEP_COMPLETE
    assert {row.key for row in setup.indexer.steps} == {"nyaasi", PROWLARR_LOGIN_STEP}
    test = setup.choices[ServiceKind.PROWLARR].test
    assert test is not None
    assert test.reason is ConnectionReason.CONNECTED


def _upgrade_to(connection: Connection, revision: str) -> None:
    config = alembic_config()
    config.attributes["connection"] = connection
    command.upgrade(config, revision)


@contextmanager
def _sqlite(engine: AsyncEngine) -> Iterator[sqlite3.Connection]:
    path = engine.url.database
    assert path is not None
    with closing(sqlite3.connect(path)) as db:
        yield db


def _read_raw(engine: AsyncEngine) -> dict[str, dict[str, object]]:
    with _sqlite(engine) as db:
        rows = db.execute("SELECT key, value_json FROM settings")
        return {key: json.loads(value) for key, value in rows}


def _write_raw(engine: AsyncEngine, key: str, value: dict[str, object]) -> None:
    with _sqlite(engine) as db:
        db.execute("UPDATE settings SET value_json = ? WHERE key = ?", (json.dumps(value), key))
        db.commit()
