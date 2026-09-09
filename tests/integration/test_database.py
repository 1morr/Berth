"""啟動時的資料庫行為：建檔、套 migration、WAL、可重複執行（票 02 驗收）。

M1 的表由後續的 migration 增量加上去（progress.md 偏差與決定），所以「升得上去」與
「降得回來」兩個方向都要驗——降不回來的 migration 等於沒有退路。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.engine import Connection

from berth.config import Config
from berth.db import create_engine
from berth.db.migrate import alembic_config
from tests.conftest import migrate

pytestmark = pytest.mark.asyncio

M0_TABLES = {"users", "sessions", "settings", "routes", "events"}
#: 票 03 加的兩張（plan §2.2）。
M1_TABLES = {"media", "tmdb_cache"}
EXPECTED_TABLES = M0_TABLES | M1_TABLES


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


async def test_the_planned_tables_are_created(config: Config) -> None:
    await migrate(config)

    assert _names_of(config.database_path, "table") >= EXPECTED_TABLES


async def test_every_migration_downgrades_off_an_empty_database(config: Config) -> None:
    """`alembic downgrade base`：一路降回去，只留 alembic 自己那張表。"""
    await migrate(config)

    engine = create_engine(config)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(_downgrade)
    finally:
        await engine.dispose()

    assert _names_of(config.database_path, "table") == {"alembic_version"}


async def test_downgrading_then_upgrading_lands_on_the_same_schema(config: Config) -> None:
    """降回去再升上來要是同一份 schema——單向能跑不代表 migration 是對的。"""
    await migrate(config)
    before = _schema_of(config.database_path)

    engine = create_engine(config)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(_downgrade)
    finally:
        await engine.dispose()
    await migrate(config)

    assert _schema_of(config.database_path) == before


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


def _downgrade(connection: Connection) -> None:
    config = alembic_config()
    config.attributes["connection"] = connection
    command.downgrade(config, "base")


def _schema_of(database_path: Path) -> set[str]:
    """`sqlite_master.sql`：表、索引與約束的 DDL 原文。"""
    with _sqlite(database_path) as connection:
        rows = connection.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name != 'alembic_version'"
        )
        return {sql for (sql,) in rows}
