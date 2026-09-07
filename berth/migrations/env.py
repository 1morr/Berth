"""Alembic 環境。

放在 `migrations/` 而不是 `db/`：它要 import `models` 取 metadata，留在 `db/` 會違反
import-linter 的層級契約（plan §1.3）。

兩種呼叫方式：
- 應用啟動時 `berth.db.upgrade_to_head` 把既有 connection 放進 `config.attributes`；
- `uv run alembic …` 時沒有 connection，這裡自己依 `berth.config` 開一個 engine。
"""

from __future__ import annotations

import asyncio
from typing import Any, Literal

from alembic import context
from alembic.autogenerate.api import AutogenContext
from sqlalchemy import Connection

from berth.config import load_config
from berth.db.engine import create_engine, database_url
from berth.models import Base
from berth.models.types import JsonText, UtcDateTime

target_metadata = Base.metadata

#: 自訂型別在 DDL 上就是 TEXT。這樣產出的 migration 不 import 應用程式碼，
#: 日後改動或搬移 `models/` 也不會讓歷史 migration 失效。
_TEXT_DECORATORS = (JsonText, UtcDateTime)


def render_item(type_: str, obj: Any, autogen_context: AutogenContext) -> str | Literal[False]:
    if type_ == "type" and isinstance(obj, _TEXT_DECORATORS):
        return "sa.Text()"
    return False


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # SQLite 沒有完整的 ALTER TABLE，改欄位一律走「建新表再搬」。
        render_as_batch=True,
        compare_type=True,
        render_item=render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    """產生 SQL 而不連資料庫（`alembic upgrade --sql`）。"""
    context.configure(
        url=database_url(load_config()).render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        render_item=render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_engine(load_config())
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


def run_migrations_online() -> None:
    connection = context.config.attributes.get("connection")
    if connection is not None:
        do_run_migrations(connection)
    else:
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
