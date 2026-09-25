"""`/api` 的門禁：CSRF 標頭與登入檢查（plan §6、票 07）。

放在 middleware 而不是逐個 router 的相依，是為了**預設拒絕**：新增端點時什麼都不做
就已經在門後，忘記掛相依不會變成一個沒人守的洞。整份規則就一句話——

    `/api` 底下每個請求都要有 session，除了白名單那三條；`setup/*` 在精靈跑完之前
    也開放，因為那時候還沒有人登入得了。

兩道檢查各防一件事：

- `X-Requested-With`：跨站表單送得出 POST，但送不出自訂標頭。cookie 是 `SameSite=Strict`
  已經擋掉絕大部分，這是第二層（plan §6）。
- session cookie：沒有就是 401，前端據此導向 `/login`。

**不用 `BaseHTTPMiddleware`**：它會把回應整個收進記憶體再送出去，plan §6 的
`GET /events/stream`（SSE）在它底下就不是串流了。純 ASGI 沒有這個問題。
"""

from __future__ import annotations

from enum import StrEnum

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from berth.domain import Role
from berth.services.auth import AuthenticatedUser, read_session
from berth.services.setup import is_setup_complete

#: 不改狀態的方法不必帶 CSRF 標頭。
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

CSRF_HEADER = "X-Requested-With"
SESSION_COOKIE = "berth_session"

#: 匿名可達的端點，路徑相對於 `/api`（plan §6）。
ANONYMOUS_PATHS = frozenset(
    {
        #: 監控與 compose 的健康檢查要打得到，而且只回 ok / degraded 與精靈跑完了沒。
        "/health",
        "/auth/login",
        #: 登出永遠成功：session 已經過期的人也該把 cookie 清掉。
        "/auth/logout",
    }
)

#: 設定精靈。它自己有一條隨時間關上的規則，見 `_setup_verdict`。
SETUP_PREFIX = "/setup"

#: 只有管理員進得來的路徑（brief §11）。規則放在門禁而不是 router 的相依，理由與 `setup/*`
#: 一樣：底下新掛的端點什麼都不做就已經在同一道門後面。
#:
#: Route 管理（票 14）也在這裡，**精靈跑完之前也不匿名開放**（票 14a）：否則那一刻匿名的人可以
#: 把紅燈 Route 停用、再按完成。精靈第 5 步只需要刪除，它走 `DELETE /setup/routes/{id}`。
#: `/jellyfin` 只收媒體庫清單那一支：之後掛在它底下的端點照預設規則（登入即可）另外決定。
#:
#: `issues` 與 `reconcile` 從 M2 票 05 起也在這裡：修正與對帳是管理員的事（plan §6、brief §11）。
#: `files`（rematch，M2 票 08）同一個理由：改一個檔案的處置會拆掉或建起媒體庫裡的鏈接。
#: `/reconcile` 沒有子路徑，前綴比對對它就是完全比對——`_under_any` 的第一個條件。
ADMIN_PREFIXES = (
    "/settings",
    "/routes",
    "/jellyfin/libraries",
    "/issues",
    "/reconcile",
    "/review",
    "/files",
)

#: 只有管理員做得了的**單一方法**（M2 票 04）。`(方法, 路徑樣式)`，樣式裡的 `*` 配一段。
#:
#: 上面那一份說的是「這整塊是 admin」，這一份說的是「**這一個動詞**在這條路徑上是 admin，
#: 它的兄弟不是」。`/jobs` 整組不可以是 admin——一般使用者要送得了單、看得到自己的 job
#: （brief §11）——而刪除是 admin 的事（plan §6，2026-09-22 拍板）。兩件事在同一條路徑上，
#: 所以前綴分不開它們。
#:
#: 估算與刪除一起：對話框打開時算的那一份逐一 `stat` 每一個檔案（brief §9.2），按不到
#: 刪除的人不必替他算。
ADMIN_ROUTES: tuple[tuple[str, str], ...] = (
    ("DELETE", "/jobs/*"),
    ("GET", "/jobs/*/deletion"),
    # 重新入庫會動媒體庫（M2 票 10）；`POST /jobs` 與重試不是——`user` 送單之後要按得到重試。
    ("POST", "/jobs/*/reimport"),
    # 審核是 admin 的事（M2 票 07）；`GET /plans/*` 不是——`user` 看得到自己那筆為什麼停下來。
    ("PUT", "/plans/*/items"),
    ("POST", "/plans/*/approve"),
    ("POST", "/plans/*/reject"),
)

#: `/api` 底下的每一個回應都帶它。
#:
#: **這不是最佳化，是正確性**（票 10 實跑當場抓到）：Berth 一個 header 都不送，於是瀏覽器
#: 對 `200` 套用它自己的啟發式快取——SSE 推來「這一筆完成了」之後前端重問一次，拿回來的
#: 卻是幾秒前那份說「已送出」的快取，畫面因此永遠停在錯的狀態。這裡的每一支回的都是
#: 「現在的狀態」，沒有一支的答案在下一秒還算數。
#:
#: 放在門禁而不是逐個端點：新增端點什麼都不做就已經帶著它，與「預設拒絕」同一個道理。
NO_STORE = "no-store"


class Access(StrEnum):
    """一個請求要過哪一道門。規則只寫在 `access_of` 一處，門禁照它放行或擋下。"""

    #: 不必登入（`ANONYMOUS_PATHS`）。
    ANONYMOUS = "anonymous"
    #: 精靈：跑完之前匿名開放，之後只有管理員（`_setup_verdict`）。
    SETUP = "setup"
    #: 只有管理員（`ADMIN_PREFIXES`、`ADMIN_ROUTES`）。
    ADMIN = "admin"
    #: 登入就可以。沒被上面三種認領的路徑都落在這裡——預設拒絕的那一半是「要登入」。
    SIGNED_IN = "signed_in"


def access_of(method: str, path: str) -> Access:
    """`path` 相對於 `/api`。只看方法與路徑，不看是誰——那是 `_verdict` 的事。

    `tests/integration/test_auth_api.py` 的 `TestWhoEachEndpointIsFor` 拿它對 app 上的每一條路由
    逐條比對一份寫死的分類表，新增端點而沒決定它是誰的，紅的是那一支。
    """
    if path in ANONYMOUS_PATHS:
        return Access.ANONYMOUS
    if _under_any(path, (SETUP_PREFIX,)):
        return Access.SETUP
    if _under_any(path, ADMIN_PREFIXES) or _is_admin_route(method, path):
        return Access.ADMIN
    return Access.SIGNED_IN


class ApiGate:
    """`/api` 底下的每個請求都先過這裡。前端靜態檔不受影響。"""

    def __init__(self, app: ASGIApp, *, prefix: str) -> None:
        self._app = app
        self._prefix = prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request = Request(scope, receive)
        path = _under(request.url.path, self._prefix)
        if path is None:
            await self._app(scope, receive, send)
            return

        # 擋下來的那一個也要 `no-store`：401 被快取的話，登入之後那一頁還是進不去。
        fresh = _no_store(send)
        refusal = await self._verdict(request, path)
        if refusal is not None:
            await refusal(scope, receive, fresh)
            return

        await self._app(scope, receive, fresh)

    async def _verdict(self, request: Request, path: str) -> JSONResponse | None:
        """放行回 `None`，擋下來回一個回應。"""
        if request.method not in SAFE_METHODS and CSRF_HEADER not in request.headers:
            return _refuse(status.HTTP_403_FORBIDDEN, f"{CSRF_HEADER} header is required")

        user = await self._resolve(request)
        # 端點透過 `current_user()` 讀它。純 ASGI 下這寫進 `scope["state"]`，
        # 下游用同一份 scope 造出來的 Request 讀得到同一個字典。
        request.state.user = user

        match access_of(request.method, path):
            case Access.ANONYMOUS:
                return None
            case Access.SETUP:
                return await _setup_verdict(request, user)
            case Access.ADMIN:
                return _admin_verdict(user)
            case Access.SIGNED_IN:
                if user is None:
                    # 未知路徑也走這裡：401 早於 404，才不會讓人靠回應碼列舉端點。
                    return _refuse(status.HTTP_401_UNAUTHORIZED, "sign in to use this API")
                return None

    async def _resolve(self, request: Request) -> AuthenticatedUser | None:
        token = request.cookies.get(SESSION_COOKIE)
        if not token:
            # 沒有 cookie 就沒得查。compose 的健康檢查每 30 秒打一次 `/health`，
            # 不該為它開資料庫。
            return None

        async with _sessions(request)() as session:
            user = await read_session(session, token)
            # `read_session` 會刪掉過期的列，所以這裡要收尾。
            await session.commit()
        return user


async def _setup_verdict(request: Request, user: AuthenticatedUser | None) -> JSONResponse | None:
    """精靈跑完之前整組匿名開放；跑完之後它就是設定入口，只有管理員進得來。

    精靈是唯一能在沒有任何帳號時就跑的東西——它跑完之前根本還沒有人登入得了
    （plan §6）。跑完之後角色跟著 Jellyfin 的 `Policy.IsAdministrator`（brief §11）。
    """
    async with _sessions(request)() as session:
        if not await is_setup_complete(session):
            return None

    if user is None:
        return _refuse(
            status.HTTP_401_UNAUTHORIZED,
            "setup is complete; sign in to change these settings",
        )
    if user.role is not Role.ADMIN:
        return _refuse(status.HTTP_403_FORBIDDEN, "administrators only")
    return None


def _admin_verdict(user: AuthenticatedUser | None) -> JSONResponse | None:
    """改設定是管理員的事；一般使用者看得到健康頁，但按不了那幾顆按鈕（brief §11）。"""
    if user is None:
        return _refuse(status.HTTP_401_UNAUTHORIZED, "sign in to use this API")
    if user.role is not Role.ADMIN:
        return _refuse(status.HTTP_403_FORBIDDEN, "administrators only")
    return None


def _under_any(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes)


def _is_admin_route(method: str, path: str) -> bool:
    """`ADMIN_ROUTES` 上有沒有哪一條同時配上這個方法與這條路徑。

    **逐段比，不是前綴比**：樣式裡的 `*` 配掉一段（job hash 就落在那裡），所以
    `DELETE /jobs/<hash>` 配得上而 `POST /jobs` 配不上——後者正是一般使用者要按的那一顆。
    """
    segments = path.split("/")
    return any(
        method == wanted and _segments_match(pattern.split("/"), segments)
        for wanted, pattern in ADMIN_ROUTES
    )


def _segments_match(pattern: list[str], segments: list[str]) -> bool:
    return len(pattern) == len(segments) and all(
        wanted in ("*", actual) for wanted, actual in zip(pattern, segments, strict=True)
    )


def _sessions(request: Request) -> async_sessionmaker[AsyncSession]:
    """門禁在路由之前，拿不到端點的相依，只能自己開 session。

    每次都從 app 拿：middleware 只有一份，把它存成實例屬性會在並行請求之間互相踩到。
    """
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    return factory


def current_user(request: Request) -> AuthenticatedUser | None:
    """這個請求背後的使用者。門禁跑過之後才有值。"""
    user: AuthenticatedUser | None = getattr(request.state, "user", None)
    return user


def _no_store(send: Send) -> Send:
    """包一層 `send`，替回應補上 `Cache-Control: no-store`。

    端點自己設過就不動它（SSE 那一支有自己的值）。純 ASGI 的包法，不用
    `BaseHTTPMiddleware`——它會把回應整個收進記憶體，`GET /events/stream` 在它底下
    就不是串流了。
    """

    async def wrapped(message: Message) -> None:
        if message["type"] == "http.response.start":
            headers = MutableHeaders(raw=message["headers"])
            headers.setdefault("cache-control", NO_STORE)
        await send(message)

    return wrapped


def _under(path: str, prefix: str) -> str | None:
    """`/api/auth/me` → `/auth/me`；不在 `/api` 底下就回 `None`。"""
    if path == prefix:
        return "/"
    return path[len(prefix) :] if path.startswith(prefix + "/") else None


def _refuse(code: int, detail: str) -> JSONResponse:
    """形狀與 FastAPI 的 `HTTPException` 一致，前端只需要認一種錯誤。"""
    return JSONResponse({"detail": detail}, status_code=code)
