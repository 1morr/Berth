"""FastAPI 相依：資料庫 session、設定、adapter client（plan §1.3）。

`api` 只 import `services`，所以 client 由 `services.clients` 組出來；測試與前端演練
用 `app.dependency_overrides` 換成 Fake。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.config import Config
from berth.services.clients import (
    HttpServiceClientFactory,
    build_setup_probes,
    close_setup_probes,
)
from berth.services.setup import ServiceClientFactory, SetupProbes


def get_config(request: Request) -> Config:
    config: Config = request.app.state.config
    return config


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """一次請求一個工作單元：正常回傳就 commit，丟例外就 rollback（plan §1.3）。"""
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        await session.commit()


async def get_setup_probes(
    config: Annotated[Config, Depends(get_config)],
) -> AsyncIterator[SetupProbes]:
    probes = build_setup_probes(config)
    try:
        yield probes
    finally:
        await close_setup_probes(probes)


def get_client_factory() -> ServiceClientFactory:
    return HttpServiceClientFactory()


SessionDep = Annotated[AsyncSession, Depends(get_session)]
ClientFactoryDep = Annotated[ServiceClientFactory, Depends(get_client_factory)]
ConfigDep = Annotated[Config, Depends(get_config)]
SetupProbesDep = Annotated[SetupProbes, Depends(get_setup_probes)]
