"""經命令執行器的 API 路由：門禁與命令的 `audience` 要一致（M5 票 07）。

門禁（`api/gate.py`）只看方法與路徑，執行器只看命令的 `audience`。兩邊對不上時，一種是一般使用者過了
門禁卻被執行器擋下（行為變了），另一種是門禁只給管理員、執行器卻讓 AI 替一般使用者做（AI 繞過了
API 的門）。這裡逐條比：路由掛的 `Command` 相依說它叫哪個命令，`access_of` 說門禁怎麼看。

`ROUTED` 釘住哪幾條走執行器：會登錄成 AI 工具、或能被確認卡執行的命令（plan §6〈命令執行器〉）。
少一條或多一條都要有人看到。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI
from fastapi.dependencies.models import Dependant

from berth.api.commands import Command, Run
from berth.api.gate import Access, access_of
from berth.domain import Role
from berth.main import create_app
from berth.services.registry import commands
from tests.endpoints import api_endpoints

API_PREFIX = "/api"

#: 走執行器的路由 → 它叫的命令。
ROUTED = {
    ("GET", "/media/{media_id}/why-not"): "why_not.explain",
    ("POST", "/jobs"): "downloading.add_manual_download",
    ("POST", "/jobs/{job_hash}/retry"): "jobs.retry_job",
    ("POST", "/jobs/{job_hash}/replan"): "plan.replan_job",
    ("GET", "/search"): "search.search_torrents",
    ("GET", "/rss/mikan/search"): "bangumi.search_bangumi",
    ("GET", "/rss/mikan/bangumi/{bangumi_id}"): "bangumi.read_bangumi",
    ("POST", "/rss/subscriptions/mikan"): "rss.subscribe_mikan",
    ("POST", "/rss/subscriptions/search"): "rss.subscribe_search",
    ("GET", "/rss/search/subgroups"): "rss.search_subgroups",
    ("POST", "/rss/feeds"): "rss.add_feed",
    ("GET", "/routes"): "routes.list_routes",
}

#: 門禁的哪一道對上哪一種 `audience`。其餘幾道（匿名、精靈）不該有路由走執行器。
GATE_FOR = {Role.ADMIN: Access.ADMIN, Role.USER: Access.SIGNED_IN}


def routed(app: FastAPI) -> dict[tuple[str, str], str]:
    """每一條掛了 `Command` 相依的路由 → 它叫的命令。路徑相對於 `/api`。"""
    found: dict[tuple[str, str], str] = {}
    for endpoint in api_endpoints(app):
        names = _commands_in(endpoint.route.dependant)
        assert len(names) <= 1, f"{endpoint.path} runs {names}"
        for method in endpoint.methods:
            for name in names:
                found[(method, endpoint.path.removeprefix(API_PREFIX))] = name
    return found


def _commands_in(dependant: Dependant) -> list[str]:
    found = [dependant.call.name] if isinstance(dependant.call, Command) else []
    for child in dependant.dependencies:
        found.extend(_commands_in(child))
    return found


def mismatches(app: FastAPI) -> list[str]:
    """門禁與 `audience` 對不上的每一條，一行一條。"""
    registry = commands()
    wrong: list[str] = []
    for (method, path), name in sorted(routed(app).items()):
        audience = registry[name].audience
        gate = access_of(method, _concrete(path))
        if gate is not GATE_FOR[audience]:
            wrong.append(f"{method} {path}: the gate is {gate}, {name} is for {audience}")
    return wrong


def _concrete(path: str) -> str:
    """`/jobs/{job_hash}/retry` → `/jobs/x/retry`：門禁比的是實際的路徑，`*` 配一段。"""
    return "/".join("x" if part.startswith("{") else part for part in path.split("/"))


class TestTheRealApp:
    def test_these_routes_go_through_the_executor(self) -> None:
        assert routed(create_app()) == ROUTED

    def test_the_gate_agrees_with_each_commands_audience(self) -> None:
        assert mismatches(create_app()) == []


# --- 雙向變異：比對本身抓得到錯、也不被無關的改名騙到 -----------------------------------


def _app(*routes: tuple[str, str, str]) -> FastAPI:
    """幾條假路由：`(方法, 路徑, 命令)`。handler 不會被呼叫，讀的是它們的相依（掛在路由上的
    `dependencies=` 也算，與參數上的同一個走法）。"""
    router = APIRouter()
    for method, path, name in routes:

        async def handler() -> None:
            pass

        router.add_api_route(path, handler, methods=[method], dependencies=[Depends(Command(name))])
    app = FastAPI()
    app.include_router(router, prefix=API_PREFIX)
    return app


class TestTheComparisonItself:
    def test_a_signed_in_route_running_an_admin_command_is_caught(self) -> None:
        app = _app(("GET", "/media/{media_id}/routes", "routes.list_routes"))

        assert mismatches(app) == [
            "GET /media/{media_id}/routes: the gate is signed_in, routes.list_routes is for admin"
        ]

    def test_an_admin_route_running_a_user_command_is_caught(self) -> None:
        app = _app(("POST", "/rss/retry/{job_hash}", "jobs.retry_job"))

        assert mismatches(app) == [
            "POST /rss/retry/{job_hash}: the gate is admin, jobs.retry_job is for user"
        ]

    def test_a_per_verb_admin_route_counts_as_admin(self) -> None:
        """`ADMIN_ROUTES` 那種只有一個動詞是 admin 的：路徑參數換成實際的一段才配得上。"""
        app = _app(("POST", "/plans/{plan_id}/approve", "routes.list_routes"))

        assert mismatches(app) == []

    def test_renamed_handlers_and_parameters_read_the_same(self) -> None:
        router = APIRouter()

        async def a_differently_named_handler(
            some_other_name: Annotated[Run, Depends(Command("jobs.retry_job"))],
        ) -> None:
            del some_other_name

        router.add_api_route(
            "/jobs/{hash_of_it}/retry", a_differently_named_handler, methods=["POST"]
        )
        app = FastAPI()
        app.include_router(router, prefix=API_PREFIX)

        assert routed(app) == {("POST", "/jobs/{hash_of_it}/retry"): "jobs.retry_job"}
        assert mismatches(app) == []
