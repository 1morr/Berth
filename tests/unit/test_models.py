"""欄位型別與 metadata。時間一律 UTC ISO 8601、JSON 以 TEXT 存（plan §2）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy import Text
from sqlalchemy.dialects import sqlite

from berth.domain import Role
from berth.models import SETTINGS_GROUPS, Base, PathSettings
from berth.models.types import JsonText, UtcDateTime, enum_column

#: 這兩個 TypeDecorator 都不看 dialect，但簽章要求一個，所以給真的而不是 None。
DIALECT = sqlite.dialect()


def _bind(value: Any) -> Any:
    return UtcDateTime().process_bind_param(value, DIALECT)


def _load(value: Any) -> Any:
    return UtcDateTime().process_result_value(value, DIALECT)


class TestUtcDateTime:
    def test_stores_iso_8601_in_utc(self) -> None:
        assert _bind(datetime(2026, 9, 7, 12, 30, tzinfo=UTC)) == "2026-09-07T12:30:00.000000+00:00"

    def test_converts_other_offsets_to_utc_before_storing(self) -> None:
        taipei = datetime(2026, 9, 7, 20, 30, tzinfo=timezone(timedelta(hours=8)))

        assert _bind(taipei) == "2026-09-07T12:30:00.000000+00:00"

    def test_rejects_naive_datetimes_rather_than_guessing_a_zone(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            _bind(datetime(2026, 9, 7, 12, 30))

    def test_reads_back_as_an_aware_datetime(self) -> None:
        loaded = _load("2026-09-07T12:30:00.000000+00:00")

        assert loaded == datetime(2026, 9, 7, 12, 30, tzinfo=UTC)
        assert loaded.tzinfo is not None

    def test_none_round_trips(self) -> None:
        assert _bind(None) is None
        assert _load(None) is None

    def test_fixed_width_output_keeps_text_sort_chronological(self) -> None:
        """事件時間線靠 `ORDER BY created_at`，所以字串排序必須等於時間排序。"""
        earlier = _bind(datetime(2026, 9, 7, 12, 30, 0, 1, tzinfo=UTC))
        later = _bind(datetime(2026, 9, 7, 12, 30, 1, tzinfo=UTC))

        assert earlier < later

    def test_is_stored_as_text(self) -> None:
        assert UtcDateTime.impl is Text


class TestJsonText:
    def test_round_trips_a_mapping(self) -> None:
        payload = {"reason": "hardlink_failed", "path": "/data/library/movies"}

        stored = JsonText().process_bind_param(payload, DIALECT)

        assert isinstance(stored, str)
        assert JsonText().process_result_value(stored, DIALECT) == payload

    def test_keeps_cjk_readable_in_the_database(self) -> None:
        stored = JsonText().process_bind_param({"name": "動畫"}, DIALECT)

        assert stored is not None
        assert "動畫" in stored

    def test_none_round_trips(self) -> None:
        assert JsonText().process_bind_param(None, DIALECT) is None
        assert JsonText().process_result_value(None, DIALECT) is None


def test_metadata_holds_exactly_the_m0_tables() -> None:
    """M0 只建這五張表；其餘在需要它們的里程碑用 Alembic 增量加（progress.md 偏差）。"""
    assert set(Base.metadata.tables) == {"users", "sessions", "settings", "routes", "events"}


def test_constraints_are_named_so_sqlite_batch_migrations_can_drop_them() -> None:
    assert set(Base.metadata.naming_convention) == {"ix", "uq", "ck", "fk", "pk"}


def test_enum_columns_store_the_value_not_the_python_name() -> None:
    """SQLAlchemy 預設存 `ADMIN`；plan §2.1 要的是 `admin`。"""
    column = enum_column(Role)

    assert sorted(column.enums) == ["admin", "user"]
    assert column.native_enum is False


def test_every_settings_group_has_a_distinct_key() -> None:
    keys = [group.KEY for group in SETTINGS_GROUPS]

    assert sorted(keys) == [
        "paths",
        "services.indexer",
        "services.jellyfin",
        "services.qbittorrent",
        "services.tmdb",
        "setup",
    ]


def test_settings_groups_are_fully_defaulted_so_an_empty_database_still_reads() -> None:
    for group in SETTINGS_GROUPS:
        assert group() is not None


def test_settings_groups_ignore_keys_written_by_older_versions() -> None:
    stored = {"complete_root": "/x", "removed_in_a_later_version": 1}

    assert PathSettings.model_validate(stored).complete_root == "/x"
