"""測試共用：列出一個 app 上的每一條 API 路由。

`tests/unit/test_openapi_contract.py`（每一條都宣告了它會拒絕什麼）與
`tests/integration/test_auth_api.py`（每一條都有人管）都要走一遍同一份清單。放在這裡而不是其中一個
測試模組裡：從測試模組 import 會把那一個模組的頂層副作用一起帶進來（M2 票 16 code-review）。
"""

from __future__ import annotations

from typing import NamedTuple

from fastapi import FastAPI
from fastapi.routing import APIRoute, iter_route_contexts


class Endpoint(NamedTuple):
    """一條 API 路由，連它掛進 app 之後的完整路徑。"""

    path: str
    methods: frozenset[str]
    route: APIRoute


def api_endpoints(app: FastAPI) -> list[Endpoint]:
    """這個 app 上的每一條 API 路由。

    走 `iter_route_contexts`（FastAPI 自己產 OpenAPI 時攤平路由用的那一支）而不是讀
    `app.routes`：`include_router` 的結果從 0.141 起包在 `_IncludedRouter` 裡，直接讀
    `app.routes` 一條 `APIRoute` 都拿不到——而**空的 `parametrize` 是會通過的**（票 02a
    第一版就是這樣「綠燈」的）。`test_it_walks_every_operation_in_the_document` 釘著這件事。
    """
    found: list[Endpoint] = []
    for context in iter_route_contexts(app.routes):
        route = context.route
        if not isinstance(route, APIRoute):
            continue
        # `APIRoute` 一定有路徑與方法；`RouteContext` 的型別替 Mount 那種留了 `None`。
        assert context.path is not None
        found.append(Endpoint(context.path, frozenset(context.methods or ()), route))
    return found
