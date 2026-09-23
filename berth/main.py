"""FastAPI app 的組裝：lifespan、API、前端靜態檔（plan §1.1、§1.2）。"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path, PurePath

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Lifespan, Scope

from berth.api import router as api_router
from berth.api.errors import validation_error
from berth.api.gate import ApiGate
from berth.config import VERSION, Config, load_config
from berth.db import create_engine, create_session_factory, upgrade_to_head
from berth.logs import configure_logging
from berth.pipeline import (
    HealthChecker,
    Importer,
    JellyfinResolver,
    PlannerRunner,
    QbitPoller,
    Reconciler,
)
from berth.services.clients import HttpServiceClientFactory, ServiceClientFactory
from berth.services.events import EventHub
from berth.services.hints import JobHints
from berth.services.jellyfin_access import AccessCache
from berth.services.reconcile import ReconcileRunner

logger = logging.getLogger(__name__)

API_PREFIX = "/api"

#: 背景 task 的名字。關機時要找得到它，測試也靠它斷言「沒有留下 pending task」。
HEALTH_CHECKER_TASK = "health_checker"
QBIT_POLLER_TASK = "qbit_poller"
PLANNER_RUNNER_TASK = "planner_runner"
IMPORTER_TASK = "importer"
JELLYFIN_RESOLVER_TASK = "jellyfin_resolver"
RECONCILER_TASK = "reconciler"

#: mount 掛在 `/`，所以 StaticFiles 收到的 path 沒有開頭的斜線。
_API_SEGMENT = API_PREFIX.lstrip("/")


class SpaFiles(StaticFiles):
    """前端是 SPA：找不到的路徑交回 `index.html`，由前端 router 決定顯示什麼。

    `/api` 底下不套用這個規則，否則前端 fetch 會拿到 HTML 而不是 JSON 錯誤。
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or _is_api(path):
                raise
            return await super().get_response("index.html", scope)


def _is_api(path: str) -> bool:
    """比對第一個路徑段，否則 `/apiary` 這種前端路由會被誤判成 API。

    StaticFiles 交來的 path 已經過 `os.path.normpath`，Windows 上的分隔符是反斜線，
    所以用 `PurePath` 拆而不是比對字串前綴。
    """
    parts = PurePath(path).parts
    return bool(parts) and parts[0] == _API_SEGMENT


def create_app(
    config: Config | None = None, *, clients: ServiceClientFactory | None = None
) -> FastAPI:
    """`clients` 只給演練與測試用（`scripts/fake_setup_server.py`）。

    背景迴圈不經過 FastAPI 的相依，所以 `dependency_overrides` 換不掉它要用的 client——
    要換就得在這裡換。
    """
    resolved = load_config() if config is None else config
    # 一行一筆 JSON，job 上下文裡的每一行帶 job id（brief §16.2、plan T1.9）。冪等，
    # 而且要在任何 logger 拿到第一筆之前——record factory 只蓋得到它裝好之後的那些。
    configure_logging()

    app = FastAPI(title="Berth", version=VERSION, lifespan=_lifespan(resolved))
    app.state.config = resolved
    app.state.clients = clients or HttpServiceClientFactory()
    # 一個程序一個 hub：發佈的是背景迴圈，訂閱的是這個程序裡開著的 SSE 連線（票 10）。
    app.state.events = EventHub()
    # 替使用者讀 Jellyfin 時的允許清單與帳號狀態，一個程序一份（M1.5 票 03）。
    app.state.jellyfin_access = AccessCache()
    # 門禁包住整個 `/api`，所以它要在路由之外（票 07）。
    app.add_middleware(ApiGate, prefix=API_PREFIX)
    app.add_exception_handler(RequestValidationError, validation_error)
    app.include_router(api_router, prefix=API_PREFIX)
    _mount_frontend(app, resolved.web_root)
    return app


def _lifespan(config: Config) -> Lifespan[FastAPI]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        config.config_root.mkdir(parents=True, exist_ok=True)
        engine = create_engine(config)
        await upgrade_to_head(engine)
        # 相依（api/deps.py）從 app.state 取，這樣 router 不必知道 engine 是怎麼建的。
        app.state.session_factory = create_session_factory(engine)
        # 迴圈之間的提示（票 11）：poller 動了什麼就叫醒 `planner_runner`。**在這裡建而不是
        # 在 `create_app`**：它裡面是一個 `asyncio.Event`，而 Event 認第一次 await 它的那個
        # 事件迴圈——同一個 app 起兩次（測試就是這樣跑的）會拿到「bound to a different
        # event loop」。迴圈與它同生同滅，所以它本來就屬於這一段。
        #
        # **一個接收者一份**：poller 叫醒 planner、planner 叫醒 importer。共用一份的話，
        # 正在忙的那一個清掉訊號時，另一個就漏掉了它（`asyncio.Event` 是大家一起清的）。
        plans = JobHints()
        imports = JobHints()
        # 入庫重試與核准的端點也要叫醒 importer，拒絕要叫醒規劃器（`api/deps.py`）。
        app.state.import_hints = imports
        app.state.plan_hints = plans
        sessions = app.state.session_factory
        clients = app.state.clients
        checker = HealthChecker(sessions, clients)
        poller = QbitPoller(sessions, clients, app.state.events, plans)
        planner = PlannerRunner(sessions, clients, app.state.events, plans, import_hints=imports)
        importer = Importer(sessions, clients, app.state.events, imports)
        resolver = JellyfinResolver(sessions, clients)
        # 對帳那一輪的擁有者。**端點也要拿得到它**（`POST /reconcile` 開一輪、`GET /reconcile`
        # 讀進度），所以它掛在 `app.state`；每日 04:00 的排程按的是同一個物件，於是
        # 「一次只有一輪」只有一個地方判斷得出來（plan §3.2）。
        runner = ReconcileRunner(sessions, clients)
        app.state.reconciler = runner
        reconciler = Reconciler(sessions, runner)
        # 背景迴圈（plan §3.2）。每一個都先睡一個間隔，所以啟動本身不會慢。
        tasks = [
            asyncio.create_task(checker.run(), name=HEALTH_CHECKER_TASK),
            asyncio.create_task(poller.run(), name=QBIT_POLLER_TASK),
            asyncio.create_task(planner.run(), name=PLANNER_RUNNER_TASK),
            asyncio.create_task(importer.run(), name=IMPORTER_TASK),
            asyncio.create_task(resolver.run(), name=JELLYFIN_RESOLVER_TASK),
            asyncio.create_task(reconciler.run(), name=RECONCILER_TASK),
        ]
        try:
            yield
        finally:
            # 先收 task 再收 engine：反過來的話迴圈會拿著一個已經關掉的 engine 醒來。
            for task in tasks:
                task.cancel()
            for task in tasks:
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            # poller 握著一條 qBittorrent 連線（rid 綁在它的 session 上），cancel 之後
            # 要自己還回去——沒還的話關機會留下一個沒關的 httpx client。
            await poller.aclose()
            # 對帳跑在自己的 task 上（202 之後那個請求早就回完了），所以 cancel 迴圈
            # 收不到它。跑到一半被收掉的那一輪不留半筆：`reconcile_once` 只在最後 commit。
            await runner.aclose()
            await engine.dispose()

    return lifespan


def _mount_frontend(app: FastAPI, web_root: Path) -> None:
    if not web_root.is_dir():
        # 只跑後端測試或還沒 `pnpm -C web build` 的開發者；API 照常運作。
        logger.warning("frontend build not found at %s; serving API only", web_root)
        return

    # 掛在最後：先前註冊的 /api 路由優先比對。
    app.mount("/", SpaFiles(directory=web_root), name="web")
