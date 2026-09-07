"""自訂欄位型別。序列化集中在 `models/`（plan §2）。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Dialect, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.types import TypeDecorator


class UtcDateTime(TypeDecorator[datetime]):
    """以 UTC ISO 8601 存進 TEXT，讀回帶時區的 datetime。

    SQLAlchemy 內建的 SQLite `DateTime` 會回 naive datetime，跨時區比較必出錯，
    所以自己來。固定寫到微秒，讓字串排序等於時間排序。
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(f"datetime must be timezone-aware, got {value!r}")
        return value.astimezone(UTC).isoformat(timespec="microseconds")

    def process_result_value(self, value: str | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return datetime.fromisoformat(value)


class JsonText(TypeDecorator[Any]):
    """`*_json` 欄位：JSON 以 TEXT 存（plan §2），CJK 不轉義以便直接讀。"""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def process_result_value(self, value: str | None, dialect: Dialect) -> Any:
        if value is None:
            return None
        return json.loads(value)


def utcnow() -> datetime:
    """`created_at` 這類欄位的預設值。"""
    return datetime.now(UTC)


def enum_column(enum_type: type[StrEnum]) -> SAEnum:
    """把 `StrEnum` 存成它的 value。

    SQLAlchemy 的 `Enum` 預設存 enum 的 *name*（`ADMIN`），plan §2 要的是 value（`admin`），
    所以每個 enum 欄位都得走這裡。`native_enum=False` 讓 DDL 是 VARCHAR。
    """
    return SAEnum(
        enum_type,
        native_enum=False,
        values_callable=lambda enum: [member.value for member in enum],
    )
