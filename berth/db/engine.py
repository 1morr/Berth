"""Async engine 與 session factory（plan §1.1、§1.2）。

SQLite 走 WAL：單程序內 API 與背景迴圈同時讀寫，WAL 讓讀不擋寫。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import URL, event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from berth.config import Config

#: 等鎖的上限。WAL 下寫入互斥，背景迴圈與請求撞在一起時寧可等一下也不要直接 SQLITE_BUSY。
BUSY_TIMEOUT_MS = 5_000


def database_url(config: Config) -> URL:
    """用 `URL.create` 而不是字串拼接：Windows 的碟符與反斜線不必特別處理。"""
    return URL.create("sqlite+aiosqlite", database=str(config.database_path))


def create_engine(config: Config) -> AsyncEngine:
    engine = create_async_engine(database_url(config))

    # Any：DBAPI connection 由驅動決定，aiosqlite 包過一層後沒有可標註的公開型別。
    @event.listens_for(engine.sync_engine, "connect")
    def _apply_pragmas(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        try:
            # journal_mode 會寫進檔案本身，之後每次開啟都是 WAL；重設無害。
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        finally:
            cursor.close()

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
