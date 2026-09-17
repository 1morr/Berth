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
    ServiceClientFactory,
    SetupProbes,
    build_setup_probes,
    close_setup_probes,
)
from berth.services.events import EventHub
from berth.services.hints import JobHints
from berth.services.jellyfin_access import AccessCache


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


def get_event_hub(request: Request) -> EventHub:
    """SSE 端點與背景迴圈用同一個 hub（`create_app` 放進 `app.state`）。

    一個程序一個：訂閱者是這個程序裡的連線，而發佈者是這個程序裡的迴圈。
    """
    hub: EventHub = request.app.state.events
    return hub


def get_import_hints(request: Request) -> JobHints:
    """importer 的喚醒訊號（`main.py` 的 lifespan 放進 `app.state`）。入庫重試按下去就叫醒它。"""
    hints: JobHints = request.app.state.import_hints
    return hints


def get_access_cache(request: Request) -> AccessCache:
    """允許清單與 `Policy` 的快取（`create_app` 放進 `app.state`）：一個程序一份，每個請求共用。"""
    cache: AccessCache = request.app.state.jellyfin_access
    return cache


def get_client_factory(request: Request) -> ServiceClientFactory:
    """端點與背景迴圈用同一份（`create_app` 放進 `app.state`）。"""
    factory: ServiceClientFactory = request.app.state.clients
    return factory


#: `scope="function"`：commit 在回應送出**之前**。FastAPI 的預設是回應送出之後才跑 `yield`
#: 之後的收尾——客戶端拿到 200 時寫入還沒落地，緊接著的下一個請求讀到舊狀態，commit 失敗時
#: 他手上也已經是一個成功（票 15 的 e2e 抓到，`test_app.py::TestUnitOfWork`）。
SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]
ClientFactoryDep = Annotated[ServiceClientFactory, Depends(get_client_factory)]
AccessCacheDep = Annotated[AccessCache, Depends(get_access_cache)]
EventHubDep = Annotated[EventHub, Depends(get_event_hub)]
ImportHintsDep = Annotated[JobHints, Depends(get_import_hints)]
ConfigDep = Annotated[Config, Depends(get_config)]
SetupProbesDep = Annotated[SetupProbes, Depends(get_setup_probes)]
