"""啟動時的資料庫行為：建檔、套 migration、WAL、可重複執行（票 02 驗收）。

M1 的表由後續的 migration 增量加上去（progress.md 偏差與決定），所以「升得上去」與
「降得回來」兩個方向都要驗——降不回來的 migration 等於沒有退路。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sqlite3
import threading
from collections.abc import Iterator, Mapping
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import Connection

from berth.config import Config
from berth.db import create_engine
from berth.db.migrate import alembic_config
from berth.services.steps import password_matches
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


#: M4 票 06 拿掉第 1 步那組帳密的那一版，與它的前一版。
OWNER_ONLY = "e8a1c4d7b293"
BEFORE_OWNER_ONLY = "d5c8e2a7f391"


async def test_the_old_setup_pair_is_dropped_and_not_kept_anywhere(config: Config) -> None:
    """M4 票 06：擁有者的帳密只交給 Jellyfin，資料庫裡不留。舊列的兩組帳密與 Berth 寫進 Prowlarr
    的那一份（就是同一個密碼）一起拿掉；其餘的鍵原封不動。
    """
    config.config_root.mkdir(parents=True, exist_ok=True)
    engine = create_engine(config)
    old = {
        "completed": True,
        "admin": {
            "username": "skipper",
            "password": "harbour",
            "interface_username": "skipper",
            "interface_password": "harbour",
            "apply_to_services": True,
        },
        "indexer": {"steps": [], "skipped": False, "login_password": "harbour"},
        "tmdb": {"steps": []},
    }
    try:
        async with engine.begin() as connection:
            await connection.run_sync(_upgrade_to, BEFORE_OWNER_ONLY)
        with _sqlite(config.database_path) as db:
            db.execute(
                "INSERT INTO settings (key, value_json, updated_at)"
                " VALUES ('setup', ?, '2026-09-28T00:00:00.000000+00:00')",
                (json.dumps(old),),
            )
            db.commit()

        async with engine.begin() as connection:
            await connection.run_sync(_upgrade_to, OWNER_ONLY)
        with _sqlite(config.database_path) as db:
            upgraded = db.execute("SELECT value_json FROM settings WHERE key = 'setup'").fetchone()[
                0
            ]

        async with engine.begin() as connection:
            await connection.run_sync(_downgrade_to, BEFORE_OWNER_ONLY)
    finally:
        await engine.dispose()

    assert "harbour" not in upgraded
    assert json.loads(upgraded) == {
        "completed": True,
        "indexer": {"steps": [], "skipped": False},
        "tmdb": {"steps": []},
    }


#: M4 票 15 把偵測判定換成選擇的那一版，與它的前一版。
SETUP_CHOICES = "f3c9a1d6b2e8"


async def _migrate_rows(
    config: Config, rows: Mapping[str, object], *, before: str, after: str
) -> tuple[dict[str, object], dict[str, object]]:
    """在 `before` 寫下這幾列設定，升到 `after`、再降回 `before`，回兩次讀到的設定。"""
    config.config_root.mkdir(parents=True, exist_ok=True)
    engine = create_engine(config)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(_upgrade_to, before)
        with _sqlite(config.database_path) as db:
            for key, value in rows.items():
                db.execute(
                    "INSERT INTO settings (key, value_json, updated_at)"
                    " VALUES (?, ?, '2026-09-29T00:00:00.000000+00:00')",
                    (key, json.dumps(value)),
                )
            db.commit()
        async with engine.begin() as connection:
            await connection.run_sync(_upgrade_to, after)
        with _sqlite(config.database_path) as db:
            upgraded = {
                key: json.loads(value)
                for key, value in db.execute("SELECT key, value_json FROM settings")
            }
        async with engine.begin() as connection:
            await connection.run_sync(_downgrade_to, before)
        with _sqlite(config.database_path) as db:
            downgraded = {
                key: json.loads(value)
                for key, value in db.execute("SELECT key, value_json FROM settings")
            }
    finally:
        await engine.dispose()
    return upgraded, downgraded


def _probe(origin: str, reason: str, base_url: str, **extra: object) -> dict[str, object]:
    return {
        "origin": origin,
        "reason": reason,
        "detail": "",
        "base_url": base_url,
        "checked_at": "2026-09-28T00:00:00+00:00",
        **extra,
    }


async def test_a_finished_wizard_keeps_its_sources_as_choices(config: Config) -> None:
    """M4 票 15：精靈跑完的舊資料庫，每個服務的判定就是那時候的來源。

    套件內 qBittorrent 的 WebUI 登入（票 07 存在連線帳密裡的明文）換成帳號加雜湊，連線帳密清空
    ——Berth 連套件內那一台靠免密白名單；Prowlarr 的介面密碼同樣換成雜湊。資料庫裡不剩明文。
    """
    rows = {
        "setup": {
            "completed": True,
            "owner": {"jellyfin_user_id": "u1", "name": "skipper"},
            "services": {
                "jellyfin": _probe("existing", "setup_completed", "http://nas:8096"),
                "qbittorrent": _probe(
                    "bundled", "connected", "http://qbittorrent:8080", configured=True
                ),
                "prowlarr": _probe("bundled", "connected", "http://prowlarr:9696"),
            },
            "probe_started_at": None,
            "qbittorrent": {"steps": []},
            "indexer": {"steps": [], "web_ui_username": "deck", "web_ui_password": "Deck-pass-1"},
        },
        "services.qbittorrent": {
            "base_url": "http://qbittorrent:8080",
            "username": "skipper",
            "password": "Webui-pass-1",
        },
    }

    upgraded, downgraded = await _migrate_rows(config, rows, before=OWNER_ONLY, after=SETUP_CHOICES)

    setup = upgraded["setup"]
    assert isinstance(setup, dict)
    assert "services" not in setup and "probe_started_at" not in setup
    assert {kind: row["origin"] for kind, row in setup["choices"].items()} == {
        "jellyfin": "existing",
        "qbittorrent": "bundled",
        "prowlarr": "bundled",
    }
    assert setup["choices"]["jellyfin"]["base_url"] == "http://nas:8096"
    assert setup["choices"]["jellyfin"]["test"]["reason"] == "setup_completed"
    assert all(row["test"]["state"] == "ok" for row in setup["choices"].values())
    assert setup["qbittorrent"]["web_ui_username"] == "skipper"
    assert password_matches("Webui-pass-1", setup["qbittorrent"]["web_ui_password_hash"])
    assert password_matches("Deck-pass-1", setup["indexer"]["web_ui_password_hash"])
    assert upgraded["services.qbittorrent"] == {
        "base_url": "http://qbittorrent:8080",
        "username": "",
        "password": "",
    }
    text = json.dumps(upgraded)
    assert "Webui-pass-1" not in text and "Deck-pass-1" not in text

    old = downgraded["setup"]
    assert isinstance(old, dict)
    assert {kind: row["origin"] for kind, row in old["services"].items()} == {
        "jellyfin": "existing",
        "qbittorrent": "bundled",
        "prowlarr": "bundled",
    }


async def test_a_half_run_wizard_drops_the_guesses_it_never_confirmed(config: Config) -> None:
    """M4 票 15：跑到一半的舊資料庫，還在探測、逾時、以及偵測猜成既有卻從沒被使用者填過的，都不是
    使用者的選擇，那一頁回到二選一。使用者填過而連不上的既有服務留著，測試是紅的。既有 qBittorrent
    的連線帳密是 Berth 的連線憑證，照舊。"""
    rows = {
        "setup": {
            "completed": False,
            "owner": {"jellyfin_user_id": "u1", "name": "skipper"},
            "services": {
                "jellyfin": _probe("bundled", "connected", "http://jellyfin:8096", configured=True),
                "qbittorrent": _probe(
                    "existing", "auth_required", "http://nas:8080", configured=True
                ),
                "prowlarr": _probe("existing", "not_deployed", "http://prowlarr:9696"),
            },
            "probe_started_at": "2026-09-28T00:00:00+00:00",
        },
        "services.qbittorrent": {
            "base_url": "http://nas:8080",
            "username": "home",
            "password": "Home-pass-1",
        },
    }

    upgraded, _ = await _migrate_rows(config, rows, before=OWNER_ONLY, after=SETUP_CHOICES)

    setup = upgraded["setup"]
    assert isinstance(setup, dict)
    assert set(setup["choices"]) == {"jellyfin", "qbittorrent"}
    assert setup["choices"]["qbittorrent"]["origin"] == "existing"
    assert setup["choices"]["qbittorrent"]["test"]["state"] == "failed"
    assert setup["choices"]["qbittorrent"]["test"]["reason"] == "auth_required"
    connection = upgraded["services.qbittorrent"]
    assert isinstance(connection, dict)
    assert connection["password"] == "Home-pass-1"


async def test_pending_probes_are_not_choices(config: Config) -> None:
    rows = {
        "setup": {
            "services": {
                "jellyfin": _probe("pending", "unreachable", "http://jellyfin:8096"),
                "qbittorrent": _probe("timeout", "unreachable", "http://qbittorrent:8080"),
            }
        }
    }

    upgraded, _ = await _migrate_rows(config, rows, before=OWNER_ONLY, after=SETUP_CHOICES)

    assert upgraded["setup"] == {"choices": {}, "qbittorrent": {}, "indexer": {}}


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


@pytest.mark.parametrize("stuck", ["connect", "pragma"])
async def test_a_connection_cancelled_while_opening_is_still_closed(
    config: Config, monkeypatch: pytest.MonkeyPatch, stuck: str
) -> None:
    """關機時 lifespan cancel 背景迴圈，打在它正在開新連線的那一刻（qbit poller 每 5 秒醒一次）。

    兩個地方會把連線丟著不關：aiosqlite 的 connect 被 cancel（`connect`），以及連上之後設
    pragma 時被 cancel（`pragma`，`journal_mode=WAL` 要等寫鎖，最容易被打中）。thread 之後把
    結果交回已經關掉的 loop，pytest 把 `Event loop is closed` 與 `unclosed database` 算在下一個
    測試頭上——`test_setup_api.py` 單獨跑三次兩次紅。
    """
    await migrate(config)
    entered, release = threading.Event(), threading.Event()
    opened: list[sqlite3.Connection] = []
    real_connect = sqlite3.connect

    def hold() -> int:
        entered.set()
        release.wait(timeout=10)
        return 0

    def slow_connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        if stuck == "connect":
            hold()
        connection: sqlite3.Connection = real_connect(*args, **kwargs)
        if stuck == "pragma":
            # 第一條敘述（設 pragma）執行途中卡住；放行之後拿掉，之後的敘述照常。
            def once() -> int:
                connection.set_progress_handler(None, 1)
                return hold()

            connection.set_progress_handler(once, 1)
        opened.append(connection)
        return connection

    # aiosqlite 的 worker thread 以 `sqlite3.connect` 開連線、在同一條 thread 上執行敘述。
    monkeypatch.setattr("aiosqlite.core.sqlite3.connect", slow_connect)
    engine = create_engine(config)

    async def use() -> None:
        async with engine.connect() as connection:
            await connection.scalar(text("SELECT 1"))

    task = asyncio.create_task(use())
    while not entered.is_set():
        await asyncio.sleep(0.01)
    task.cancel()
    release.set()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    await engine.dispose()
    # 修好之前沒有人等那條 thread：它開完的時候，這裡早就走過去了。
    for _ in range(500):
        if opened:
            break
        await asyncio.sleep(0.01)

    assert len(opened) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        opened[0].execute("SELECT 1")


BACKFILL = "e8a3d6c1f59b"
BEFORE_BACKFILL = "c3e9a7f1b204"


async def test_series_bound_before_backfill_do_not_fetch_a_whole_season(config: Config) -> None:
    """票 12：升級之前就綁好的 Mikan RSS Series 從沒被問過要不要補舊集，升級那一刻不替它們送出
    整季——`passed_before` 補成它長出來的那一刻。待綁定的與不是 Mikan 的不動。"""
    config.config_root.mkdir(parents=True, exist_ok=True)
    engine = create_engine(config)
    born = "2026-09-20T00:00:00.000000+00:00"
    try:
        async with engine.begin() as connection:
            await connection.run_sync(_upgrade_to, BEFORE_BACKFILL)
        with _sqlite(config.database_path) as db:
            for key, media, bangumi in (
                ("mikan:1:1", "tv:1", 1),
                ("mikan:2:1", None, 2),
                ("title:kimi:lolihouse", "tv:1", None),
            ):
                db.execute(
                    "INSERT INTO rss_series (key, title_raw, media_id, mikan_bangumi_id,"
                    " mikan_subgroup_id, bound_by, created_at) VALUES (?, '', ?, ?, ?, '', ?)",
                    (key, media, bangumi, bangumi and 1, born),
                )
            db.commit()

        async with engine.begin() as connection:
            await connection.run_sync(_upgrade_to, BACKFILL)
        with _sqlite(config.database_path) as db:
            rows = dict(db.execute("SELECT key, passed_before FROM rss_series").fetchall())
    finally:
        await engine.dispose()

    assert rows == {"mikan:1:1": born, "mikan:2:1": None, "title:kimi:lolihouse": None}


NO_PASSING = "d71e4b9a3c58"
BEFORE_NO_PASSING = "b4ca280eaeca"


async def test_dropping_passed_before_puts_back_what_it_passed(config: Config) -> None:
    """M4 票 78：補舊集不再有開關。因為 `passed_before` 而略過的舊集放回去——綁著的回到 `matched`
    （下一輪輪詢送出），解綁了的回到 `unbound`；其他理由的 `passed`（「只追之後的」）不動。降版只把
    欄位加回來、不還原狀態。"""
    config.config_root.mkdir(parents=True, exist_ok=True)
    engine = create_engine(config)
    born, before, after = (
        "2026-09-20T00:00:00.000000+00:00",
        "2026-09-10T00:00:00.000000+00:00",
        "2026-09-25T00:00:00.000000+00:00",
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(_upgrade_to, BEFORE_NO_PASSING)
        with _sqlite(config.database_path) as db:
            for feed, kind in ((1, "mikan"), (2, "acgrip")):
                db.execute(
                    "INSERT INTO rss_feeds (id, name, url, kind, interval_sec, last_error,"
                    " exclude_json, created_at) VALUES (?, '', ?, ?, 1800, '', '[]', ?)",
                    (feed, f"u{feed}", kind, born),
                )
            for series, key, media, bangumi, passed_before in (
                (1, "mikan:1:1", "tv:1", 1, born),
                (2, "mikan:2:1", None, 2, born),
                (3, "mikan:3:1", "tv:3", 3, None),
                (4, "title:rezero:lolihouse", "tv:4", None, None),
            ):
                db.execute(
                    "INSERT INTO rss_series (id, key, title_raw, media_id, mikan_bangumi_id,"
                    " mikan_subgroup_id, bound_by, exclude_json, passed_before, created_at)"
                    " VALUES (?, ?, '', ?, ?, ?, '', '[]', ?, ?)",
                    (series, key, media, bangumi, bangumi and 1, passed_before, born),
                )
            for guid, feed, series, published, status in (
                ("bound-old", 1, 1, before, "passed"),
                ("bound-new", 1, 1, after, "matched"),
                ("bound-excluded", 1, 1, before, "excluded"),
                ("unbound-old", 1, 2, before, "passed"),
                ("never-unchecked", 1, 3, before, "passed"),
                ("primed-later", 2, 4, before, "passed"),
                # 條件都對得上，只差不在 Mikan Feed 上：只有 Mikan Feed 上的才是它略過的。
                ("other-feed", 2, 1, before, "passed"),
            ):
                db.execute(
                    "INSERT INTO rss_items (feed_id, guid, title, link, torrent_url, info_hash,"
                    " published_at, seen_at, series_id, job_hash, status, error)"
                    " VALUES (?, ?, '', '', '', '', ?, ?, ?, '', ?, '')",
                    (feed, guid, published, born, series, status),
                )
            db.commit()

        async with engine.begin() as connection:
            await connection.run_sync(_upgrade_to, NO_PASSING)
        with _sqlite(config.database_path) as db:
            statuses = dict(db.execute("SELECT guid, status FROM rss_items").fetchall())
        upgraded = _columns_of(config.database_path)["rss_series"]

        async with engine.begin() as connection:
            await connection.run_sync(_downgrade_to, BEFORE_NO_PASSING)
        with _sqlite(config.database_path) as db:
            restored = dict(db.execute("SELECT key, passed_before FROM rss_series").fetchall())
            back = dict(db.execute("SELECT guid, status FROM rss_items").fetchall())
    finally:
        await engine.dispose()

    assert statuses == {
        "bound-old": "matched",
        "bound-new": "matched",
        "bound-excluded": "excluded",
        "unbound-old": "unbound",
        # 從沒取消勾選的 Series 底下不會有它略過的；這一筆是別的理由，不動。
        "never-unchecked": "passed",
        "primed-later": "passed",
        "other-feed": "passed",
    }
    assert "passed_before" not in upgraded
    assert set(restored.values()) == {None}
    assert back == statuses


PUBLISHED = "c8d2f5a1e734"


async def test_rss_jobs_take_their_published_time_from_the_feed_item(config: Config) -> None:
    """票 14：升級之前送出的 RSS Job 從 `rss_items` 補上發佈時間（最早帶到它的那一筆），還沒入庫的
    重新規劃時才比得到播出日。手動送單的沒有來源可以補，留空。"""
    config.config_root.mkdir(parents=True, exist_ok=True)
    engine = create_engine(config)
    early, late = "2026-09-20T13:01:00.000000+00:00", "2026-09-21T02:00:00.000000+00:00"
    try:
        async with engine.begin() as connection:
            await connection.run_sync(_upgrade_to, BEFORE_PUBLISHED)
        with _sqlite(config.database_path) as db:
            for job_hash, trigger in (("a" * 40, "rss"), ("b" * 40, "manual")):
                db.execute(
                    "INSERT INTO jobs (hash, name, source_url, trigger, trigger_ref, state, error,"
                    " save_path, content_path, total_size, progress, client_state, added_at)"
                    " VALUES (?, '', '', ?, '', 'submitted', '', '', '', 0, 0, '', ?)",
                    (job_hash, trigger, early),
                )
            db.execute(
                "INSERT INTO rss_feeds (id, name, url, kind, interval_sec, last_error, created_at)"
                " VALUES (1, '', 'u', 'mikan', 1800, '', ?)",
                (early,),
            )
            for guid, published, job_hash in (
                ("1", late, "a" * 40),
                ("2", early, "a" * 40),
                ("3", early, "b" * 40),
            ):
                db.execute(
                    "INSERT INTO rss_items (feed_id, guid, title, link, torrent_url, info_hash,"
                    " published_at, seen_at, job_hash, status, error)"
                    " VALUES (1, ?, '', '', '', '', ?, ?, ?, 'sent', '')",
                    (guid, published, early, job_hash),
                )
            db.commit()

        async with engine.begin() as connection:
            await connection.run_sync(_upgrade_to, PUBLISHED)
        with _sqlite(config.database_path) as db:
            rows = dict(db.execute("SELECT hash, published_at FROM jobs").fetchall())
    finally:
        await engine.dispose()

    assert rows == {"a" * 40: early, "b" * 40: None}


BEFORE_PUBLISHED = "a4f7c2e9d168"


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
