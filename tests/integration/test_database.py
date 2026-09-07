"""啟動時的資料庫行為：建檔、套 migration、WAL、可重複執行（票 02 驗收）。"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

import pytest
from sqlalchemy import text

from berth.config import Config
from berth.db import create_engine
from tests.conftest import migrate

pytestmark = pytest.mark.asyncio

EXPECTED_TABLES = {"users", "sessions", "settings", "routes", "events"}


@contextmanager
def _sqlite(database_path: Path) -> Iterator[sqlite3.Connection]:
    """`sqlite3.connect` 當 context manager 只管交易，不關連線，所以自己 close。"""
    with closing(sqlite3.connect(database_path)) as connection:
        yield connection


def _names_of(database_path: Path, kind: str) -> set[str]:
    with _sqlite(database_path) as connection:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type = ?", (kind,))
        return {name for (name,) in rows}


async def test_migrating_an_empty_config_root_creates_the_database(config: Config) -> None:
    assert not config.database_path.exists()

    await migrate(config)

    assert config.database_path.exists()


async def test_the_m0_tables_are_created(config: Config) -> None:
    await migrate(config)

    assert _names_of(config.database_path, "table") >= EXPECTED_TABLES


async def test_alembic_records_the_head_revision(config: Config) -> None:
    await migrate(config)

    with _sqlite(config.database_path) as connection:
        applied = {row[0] for row in connection.execute("SELECT version_num FROM alembic_version")}

    assert len(applied) == 1


async def test_indexes_from_the_plan_are_present(config: Config) -> None:
    await migrate(config)

    assert "ix_events_job_hash_created_at" in _names_of(config.database_path, "index")


async def test_migrating_twice_is_a_no_op(config: Config) -> None:
    await migrate(config)
    before = config.database_path.read_bytes()

    await migrate(config)

    assert _names_of(config.database_path, "table") >= EXPECTED_TABLES
    assert config.database_path.read_bytes() == before


async def test_the_database_runs_in_wal_mode(config: Config) -> None:
    await migrate(config)

    engine = create_engine(config)
    try:
        async with engine.connect() as connection:
            mode = await connection.scalar(text("PRAGMA journal_mode"))
    finally:
        await engine.dispose()

    assert mode == "wal"


async def test_foreign_keys_are_enforced(config: Config) -> None:
    """`sessions.user_id` 的 CASCADE 只有在 pragma 開著時才有意義。"""
    await migrate(config)

    engine = create_engine(config)
    try:
        async with engine.connect() as connection:
            enabled = await connection.scalar(text("PRAGMA foreign_keys"))
    finally:
        await engine.dispose()

    assert enabled == 1
