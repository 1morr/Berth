"""啟動時的資料庫行為：建檔、套 migration、WAL、可重複執行（票 02 驗收）。

M1 的表由後續的 migration 增量加上去（progress.md 偏差與決定），所以「升得上去」與
「降得回來」兩個方向都要驗——降不回來的 migration 等於沒有退路。
"""

from __future__ import annotations

import json
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
#: 票 03 加的兩張（plan §2.2）、票 09 加的兩張、票 11 加的兩張與票 12 的帳本（plan §2.3）。
M1_TABLES = {"media", "tmdb_cache", "jobs", "job_files", "plans", "plan_items", "ledger"}
#: M2 票 05 加的一張（plan §2.4）。
M2_TABLES = {"issues"}
#: M3 票 08 加的三張（plan §2.4）。
M3_TABLES = {"rss_feeds", "rss_series", "rss_items"}
EXPECTED_TABLES = M0_TABLES | M1_TABLES | M2_TABLES | M3_TABLES


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
            await connection.run_sync(_downgrade_to, "base")
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
            await connection.run_sync(_downgrade_to, "base")
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
            await connection.run_sync(_downgrade_to, "-1")
        rolled_back = _columns_of(config.database_path)
        async with engine.begin() as connection:
            await connection.run_sync(_downgrade_to, "base")
            await connection.run_sync(_upgrade_to_previous)
    finally:
        await engine.dispose()

    assert _columns_of(config.database_path) == rolled_back


#: 票 14e 刪 `routes.profile` 的那一版，與它的前一版。
PROFILE_DROPPED = "9d4f1b6e2a70"
BEFORE_PROFILE_DROPPED = "3f6c0a7d94e2"


async def test_dropping_the_route_profile_keeps_what_points_at_the_route(config: Config) -> None:
    """票 14e：升版刪掉 `routes.profile`，降版補回 `standard`，**指向 Route 的列兩個方向都不動**。

    `jobs.route_id` 與 `media.default_route_id` 都是 `ON DELETE SET NULL`，而外鍵在 migration 時
    開著：用 batch 重建 `routes` 的話 `DROP TABLE` 那一步會把它們全部清空（2026-09-17 實測）。
    schema 比對的測試抓不到這件事——它們跑在空的資料庫上。
    """
    config.config_root.mkdir(parents=True, exist_ok=True)
    engine = create_engine(config)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(_upgrade_to, BEFORE_PROFILE_DROPPED)
        with _sqlite(config.database_path) as db:
            _arrange_a_routed_job(db)
            db.commit()

        async with engine.begin() as connection:
            await connection.run_sync(_upgrade_to, PROFILE_DROPPED)
        assert "profile" not in _columns_of(config.database_path)["routes"]
        assert _pointers_at_route(config.database_path) == (1, 1)

        async with engine.begin() as connection:
            await connection.run_sync(_downgrade_to, BEFORE_PROFILE_DROPPED)
        with _sqlite(config.database_path) as db:
            profiles = [profile for (profile,) in db.execute("SELECT profile FROM routes")]
        assert profiles == ["standard"]
        assert _pointers_at_route(config.database_path) == (1, 1)
    finally:
        await engine.dispose()


def _arrange_a_routed_job(db: sqlite3.Connection) -> None:
    """一條 anime Route，一部把它當預選的作品，一個送到它的 Job。"""
    db.execute(
        "INSERT INTO routes (id, slug, name, jellyfin_library_id, jellyfin_library_name,"
        " collection_type, target_path, category, profile, medium_auto_import, enabled,"
        " health_status, created_at)"
        " VALUES (1, 'anime', 'Anime', 'lib', 'Anime', 'tvshows', '/data/library/anime',"
        " 'berth-anime', 'anime', 1, 1, 'ok', '2026-09-17T00:00:00.000000+00:00')"
    )
    db.execute(
        "INSERT INTO media (id, tmdb_id, kind, title_en, title_original, folder_name,"
        " folder_frozen, default_route_id)"
        " VALUES ('tv:1', 1, 'tv', 'Show', 'Show', 'Show (2020) [tmdbid-1]', 1, 1)"
    )
    db.execute(
        "INSERT INTO jobs (hash, name, source_url, trigger, trigger_ref, media_id, route_id, state,"
        " error, save_path, content_path, total_size, progress, client_state, added_at)"
        " VALUES ('a', 'Show - 01', '', 'manual', '', 'tv:1', 1, 'downloading', '', '', '', 0,"
        " 0.0, '', '2026-09-17T00:00:00.000000+00:00')"
    )


def _pointers_at_route(database_path: Path) -> tuple[int | None, int | None]:
    with _sqlite(database_path) as db:
        (job,) = db.execute("SELECT route_id FROM jobs").fetchone()
        (media,) = db.execute("SELECT default_route_id FROM media").fetchone()
    return job, media


#: 票 07 把 `plan_items.reasons_json` 從英文句子改成 `{code, params}` 的那一版，與它的前一版。
REASON_CODES = "b58e3d1f7a20"
BEFORE_REASON_CODES = "a71c4e08b5d2"


async def test_old_reason_sentences_are_cleared_and_coded_ones_are_kept(config: Config) -> None:
    """票 07：舊格式的英文句子清成空清單（使用者拍板不轉換），新格式與空值不動。"""
    config.config_root.mkdir(parents=True, exist_ok=True)
    engine = create_engine(config)
    coded = '[{"code": "single_season", "params": {}}]'
    try:
        async with engine.begin() as connection:
            await connection.run_sync(_upgrade_to, BEFORE_REASON_CODES)
        with _sqlite(config.database_path) as db:
            db.execute(
                "INSERT INTO plans (id, source_path, engine, engine_version, status, created_at,"
                " decided_by) VALUES (1, '/x', 'rules', '', 'pending_review',"
                " '2026-09-23T00:00:00.000000+00:00', '')"
            )
            for item, reasons in ((1, '["the job names the season"]'), (2, coded), (3, None)):
                db.execute(
                    "INSERT INTO plan_items (id, plan_id, rel_path, action, target_path,"
                    " confidence, reasons_json, audit, error)"
                    " VALUES (?, 1, 'a.mkv', 'review', '', 'low', ?, 0, '')",
                    (item, reasons),
                )
            db.commit()

        async with engine.begin() as connection:
            await connection.run_sync(_upgrade_to, REASON_CODES)
        with _sqlite(config.database_path) as db:
            rows = dict(db.execute("SELECT id, reasons_json FROM plan_items").fetchall())
    finally:
        await engine.dispose()

    assert rows == {1: "[]", 2: coded, 3: None}


#: 票 06c 把第 1 步的帳密拆成帳號與介面兩組的那一版，與它的前一版。
INTERFACE_PAIR = "c3d8a6f1b240"
BEFORE_INTERFACE_PAIR = "f2a7c91d4e38"


async def test_the_interface_pair_starts_as_the_account_pair(config: Config) -> None:
    """票 06c：舊的 `setup` 列只有一組帳密，那一組就是介面那一組（兩組在交給 Jellyfin 前本來相同）。

    沒有這一步，精靈跑到一半的舊資料重跑第 4、5 步會讀到空的介面帳密，悄悄不設密碼。
    """
    config.config_root.mkdir(parents=True, exist_ok=True)
    engine = create_engine(config)
    admin = '{"admin": {"username": "skipper", "password": "harbour", "apply_to_services": true}}'
    try:
        async with engine.begin() as connection:
            await connection.run_sync(_upgrade_to, BEFORE_INTERFACE_PAIR)
        with _sqlite(config.database_path) as db:
            for key, value in (("setup", admin), ("paths", '{"library_root": "/data/library"}')):
                db.execute(
                    "INSERT INTO settings (key, value_json, updated_at)"
                    " VALUES (?, ?, '2026-09-25T00:00:00.000000+00:00')",
                    (key, value),
                )
            db.commit()

        async with engine.begin() as connection:
            await connection.run_sync(_upgrade_to, INTERFACE_PAIR)
        with _sqlite(config.database_path) as db:
            upgraded = dict(db.execute("SELECT key, value_json FROM settings").fetchall())

        async with engine.begin() as connection:
            await connection.run_sync(_downgrade_to, BEFORE_INTERFACE_PAIR)
        with _sqlite(config.database_path) as db:
            downgraded = dict(db.execute("SELECT key, value_json FROM settings").fetchall())
    finally:
        await engine.dispose()

    assert json.loads(upgraded["setup"])["admin"] == {
        "username": "skipper",
        "password": "harbour",
        "apply_to_services": True,
        "interface_username": "skipper",
        "interface_password": "harbour",
    }
    assert upgraded["paths"] == '{"library_root": "/data/library"}'
    assert json.loads(downgraded["setup"]) == json.loads(admin)


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
    assert "ix_ledger_job_hash" in indexes
    assert "ix_ledger_resolve_after" in indexes
    assert "ix_issues_status_detected_at" in indexes


async def test_one_open_issue_per_subject(config: Config) -> None:
    """冪等鍵 `(type, subject)` 由**資料庫**守著，而且只蓋 `open`（plan §2.4、M2 票 05）。

    兩件事一起驗，因為它們互相制衡：少了 unique，兩個迴圈同時偵測到同一件事會寫出兩筆
    `open`（服務那一層先查再寫中間那條縫關不掉）；少了 `WHERE status = 'open'`，一條路徑
    一輩子只能出一次問題——決定過的那一筆會永遠擋住下一次。
    """
    await migrate(config)
    rows = [
        ("library_link_missing", "/data/library/Show/S01E01.mkv", "open"),
        # 同一個 subject 的第二筆：決定過的那一筆不受索引管。
        ("library_link_missing", "/data/library/Show/S01E01.mkv", "resolved"),
        ("library_link_missing", "/data/library/Show/S01E01.mkv", "ignored"),
        # 同一條路徑、不同型別：不是同一件事。
        ("inode_mismatch", "/data/library/Show/S01E01.mkv", "open"),
    ]

    with _sqlite(config.database_path) as connection:
        for kind, subject, status in rows:
            connection.execute(
                "INSERT INTO issues (type, subject, path, status, detected_at, resolved_by) "
                "VALUES (?, ?, ?, ?, '2026-09-22T00:00:00+00:00', '')",
                (kind, subject, subject, status),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO issues (type, subject, path, status, detected_at, resolved_by) "
                "VALUES (?, ?, ?, 'open', '2026-09-22T00:00:00+00:00', '')",
                (rows[0][0], rows[0][1], rows[0][1]),
            )


async def test_a_library_path_has_at_most_one_ledger_entry(config: Config) -> None:
    """`ledger.target_path` 是 unique（plan §2.3、§3.3）：同一個目標寫第二筆就是冪等出了錯，
    要在資料庫這一層就擋下來，而不是靠 importer 記得先查。"""
    await migrate(config)

    with _sqlite(config.database_path) as connection:
        unique = {
            name: bool(is_unique)
            for _, name, is_unique, *_ in connection.execute("PRAGMA index_list('ledger')")
        }

    assert unique["ix_ledger_target_path"] is True


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


def _upgrade_to(connection: Connection, revision: str) -> None:
    config = alembic_config()
    config.attributes["connection"] = connection
    command.upgrade(config, revision)


def _downgrade_to(connection: Connection, revision: str) -> None:
    config = alembic_config()
    config.attributes["connection"] = connection
    command.downgrade(config, revision)


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
