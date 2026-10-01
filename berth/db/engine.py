"""Async engine 與 session factory（plan §1.1、§1.2）。

SQLite 走 WAL：單程序內 API 與背景迴圈同時讀寫，WAL 讓讀不擋寫。
"""

from __future__ import annotations

import asyncio
import contextlib

import aiosqlite
from sqlalchemy import URL
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
    path = str(config.database_path)
    return create_async_engine(database_url(config), async_creator=lambda: _connect(path))


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


#: 每條連線開好就設。journal_mode 會寫進檔案本身，之後每次開啟都是 WAL；重設無害。
PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA foreign_keys=ON",
    f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}",
)


async def _connect(path: str) -> aiosqlite.Connection:
    """開一條連線、設好 pragma；做到一半被 cancel 時，先做完、關掉，再讓 cancel 往上走。

    關機時 lifespan cancel 背景迴圈，會打在迴圈正在開新連線的時候（qbit poller 每 5 秒醒一次）。
    兩個地方都會把連線丟著不關：aiosqlite 的 connect 被 cancel 時丟掉 worker thread 剛開好的
    sqlite3 連線（0.22.1 與上游 main 都是）；SQLAlchemy 的 `connect` 事件裡被 cancel 時丟掉整條
    連線——而 `journal_mode=WAL` 要等寫鎖，最容易被打中。thread 之後還把結果交回已經關掉的
    事件迴圈。所以 pragma 不放在 `connect` 事件，與 connect 一起包在 `shield` 裡做完。

    參數照 SQLAlchemy 的 aiosqlite 方言預設的那一份（`check_same_thread=False`、thread 設成
    daemon）：`async_creator` 接手之後這兩件事要自己做。
    """
    connection = aiosqlite.connect(path, check_same_thread=False)
    # 私有屬性：0.22 起 thread 包在 Connection 裡，SQLAlchemy 的方言也是這樣設的。
    connection._thread.daemon = True
    opening = asyncio.ensure_future(_opened(connection))
    try:
        return await asyncio.shield(opening)
    except asyncio.CancelledError:
        with contextlib.suppress(Exception):
            await (await opening).close()
        raise


async def _opened(connection: aiosqlite.Connection) -> aiosqlite.Connection:
    await connection
    for pragma in PRAGMAS:
        async with connection.execute(pragma):
            pass
    return connection
