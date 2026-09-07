"""在程序內套用 Alembic migration（plan §1.1：啟動時自動 migrate）。

不讀 repo 根目錄的 `alembic.ini`：那個檔只服務 `uv run alembic …` 的人工操作，
安裝成 wheel 之後並不存在。設定在這裡組出來，兩條路徑共用同一個 `env.py`。
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def alembic_config() -> AlembicConfig:
    config = AlembicConfig()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    return config


async def upgrade_to_head(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(_upgrade)


def _upgrade(connection: Connection) -> None:
    config = alembic_config()
    # `env.py` 看到這個 connection 就沿用，不會另外開 engine。
    config.attributes["connection"] = connection
    command.upgrade(config, "head")
