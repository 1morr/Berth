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
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import Connection

from berth.config import Config
from berth.db import create_engine
from berth.db.migrate import alembic_config
from tests.conftest import migrate

pytestmark = pytest.mark.asyncio

M0_TABLES = {"users", "sessions", "settings", "routes", "events"}
#: 票 03 加的兩張（plan §2.2）、票 09 加的兩張與票 11 加的兩張（plan §2.3）。
M1_TABLES = {"media", "tmdb_cache", "jobs", "job_files", "plans", "plan_items"}
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


async def test_downgrading_the_last_revision_lands_on_the_previous_schema(
    config: Config,
) -> None:
    """**降一版**要回到那一版原本的 schema，不是一個長得像它的東西。

    降到 base 那條測不出這件事：整張表都沒了，欄位差在哪就看不出來；升回 head 也測不出來，
    降版時多出來的東西會被下一次升版蓋掉。實際踩過的坑是 SQLite 補一個 NOT NULL 欄位得先給
    `server_default` 填舊列，填完沒拿掉的話降版後那一欄就多了一個當初沒有的預設值（票 04b）。
    """
    await migrate(config)

    engine = create_engine(config)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(_downgrade_one)
        rolled_back = _columns_of(config.database_path)
        async with engine.begin() as connection:
            await connection.run_sync(_downgrade)
            await connection.run_sync(_upgrade_to_previous)
    finally:
        await engine.dispose()

    assert _columns_of(config.database_path) == rolled_back


async def test_alembic_records_the_head_revision(config: Config) -> None:
    await migrate(config)

    with _sqlite(config.database_path) as connection:
        applied = {row[0] for row in connection.execute("SELECT version_num FROM alembic_version")}

    assert len(applied) == 1


async def test_indexes_from_the_plan_are_present(config: Config) -> None:
    await migrate(config)

    indexes = _names_of(config.database_path, "index")

    assert "ix_events_job_hash_created_at" in indexes
    assert "ix_job_files_job_hash" in indexes
    assert "ix_plan_items_plan_id" in indexes
    # 一個 Job 一份「現在的計劃」：unique 而不只是 index（`models/plan.py`）。
    assert "ix_plans_job_hash" in indexes


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


def _downgrade_one(connection: Connection) -> None:
    config = alembic_config()
    config.attributes["connection"] = connection
    command.downgrade(config, "-1")


def _upgrade_to_previous(connection: Connection) -> None:
    """從空的資料庫升到**倒數第二版**：head 的 `down_revision`，不寫死任何 id。"""
    config = alembic_config()
    config.attributes["connection"] = connection
    scripts = ScriptDirectory.from_config(config)
    head = scripts.get_current_head()
    assert head is not None
    previous = scripts.get_revision(head).down_revision
    assert isinstance(previous, str)
    command.upgrade(config, previous)


def _columns_of(database_path: Path) -> dict[str, dict[str, tuple[str, int, str | None]]]:
    """每張表的欄位：名字 → (型別, NOT NULL, 預設值)。

    比 `sqlite_master.sql` 原文適合比較兩條不同路徑走出來的同一份 schema：SQLite 的 batch
    migration 是「建新表再搬」，走過它的表名會多一組引號、欄位順序也會變——那兩件事不是差異，
    而預設值是。
    """
    with _sqlite(database_path) as connection:
        tables = {
            name
            for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        return {
            table: {
                row[1]: (row[2], row[3], row[4])
                for row in connection.execute(f'PRAGMA table_info("{table}")')
            }
            for table in tables
        }


def _schema_of(database_path: Path) -> set[str]:
    """`sqlite_master.sql`：表、索引與約束的 DDL 原文。"""
    with _sqlite(database_path) as connection:
        rows = connection.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name != 'alembic_version'"
        )
        return {sql for (sql,) in rows}
