"""FastAPI app 的組裝：lifespan、API、前端靜態檔（plan §1.1、§1.2）。"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path, PurePath

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Lifespan, Scope

from berth.api import router as api_router
from berth.config import VERSION, Config, load_config
from berth.db import create_engine, upgrade_to_head

logger = logging.getLogger(__name__)

API_PREFIX = "/api"

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


def create_app(config: Config | None = None) -> FastAPI:
    resolved = load_config() if config is None else config

    app = FastAPI(title="Berth", version=VERSION, lifespan=_lifespan(resolved))
    app.include_router(api_router, prefix=API_PREFIX)
    _mount_frontend(app, resolved.web_root)
    return app


def _lifespan(config: Config) -> Lifespan[FastAPI]:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        config.config_root.mkdir(parents=True, exist_ok=True)
        engine = create_engine(config)
        await upgrade_to_head(engine)
        try:
            yield
        finally:
            await engine.dispose()

    return lifespan


def _mount_frontend(app: FastAPI, web_root: Path) -> None:
    if not web_root.is_dir():
        # 只跑後端測試或還沒 `pnpm -C web build` 的開發者；API 照常運作。
        logger.warning("frontend build not found at %s; serving API only", web_root)
        return

    # 掛在最後：先前註冊的 /api 路由優先比對。
    app.mount("/", SpaFiles(directory=web_root), name="web")
