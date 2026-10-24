"""`/api` 的門禁：CSRF 標頭與登入檢查（plan §6、票 07）。

放在 middleware 而不是逐個 router 的相依，是為了**預設拒絕**：新增端點時什麼都不做
就已經在門後，忘記掛相依不會變成一個沒人守的洞。整份規則就一句話——

    `/api` 底下每個請求都要有 session，除了白名單那三條；精靈在擁有者成立之前開放找
    Jellyfin 與成立擁有者那幾支，因為那時候還沒有人登入得了（M4 票 06）。

兩道檢查各防一件事：

- `X-Requested-With`：跨站表單送得出 POST，但送不出自訂標頭。cookie 是 `SameSite=Strict`
  已經擋掉絕大部分，這是第二層（plan §6）。
- session cookie：沒有就是 401，前端據此導向 `/login`。

**不用 `BaseHTTPMiddleware`**：它會把回應整個收進記憶體再送出去，plan §6 的
`GET /events/stream`（SSE）在它底下就不是串流了。純 ASGI 沒有這個問題。

**哪一條路徑要哪一種人**寫在 `services/access.py`（M5 票 05 搬過去）：命令登錄表給一個人哪些
工具也照同一張表，這裡只負責 CSRF、讀 session 與精靈的擁有者那一關。
"""

from __future__ import annotations

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from berth.services.access import Access, access_of, admits
from berth.services.auth import AuthenticatedUser, read_session
from berth.services.jobs import actor_of
from berth.services.setup import is_owner_established

#: 不改狀態的方法不必帶 CSRF 標頭。
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

CSRF_HEADER = "X-Requested-With"
SESSION_COOKIE = "berth_session"

#: `/api` 底下的每一個回應都帶它。
#:
#: **這不是最佳化，是正確性**（票 10 實跑當場抓到）：Berth 一個 header 都不送，於是瀏覽器
#: 對 `200` 套用它自己的啟發式快取——SSE 推來「這一筆完成了」之後前端重問一次，拿回來的
#: 卻是幾秒前那份說「已送出」的快取，畫面因此永遠停在錯的狀態。這裡的每一支回的都是
#: 「現在的狀態」，沒有一支的答案在下一秒還算數。
#:
#: 放在門禁而不是逐個端點：新增端點什麼都不做就已經帶著它，與「預設拒絕」同一個道理。
NO_STORE = "no-store"


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
            case Access.SETUP_OPENING | Access.SETUP as access:
                return await _setup_verdict(request, user, access)
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


async def _setup_verdict(
    request: Request, user: AuthenticatedUser | None, access: Access
) -> JSONResponse | None:
    """擁有者成立之前只開精靈的開場（`SETUP_OPENING_PATHS`）；成立之後整組只有管理員進得來。

    精靈是唯一能在沒有任何帳號時就跑的東西，但沒有帳號時它只做得了一件事：找到 Jellyfin、
    讓第一個 Jellyfin 管理員成為擁有者（誰先到誰建立，與 Jellyfin 自己的啟動精靈、Seerr 相同，
    plan §9.3 第 1 步）。成立之後角色跟著 Jellyfin 的 `Policy.IsAdministrator`（brief §11）。

    跑完之後這一組是**設定頁的寫入端點**（票 06i）：設定的 Jellyfin / qBittorrent / 索引站 / TMDB
    那幾頁呼叫的就是精靈的同一批命令，不另開 `settings/*` 的一份。
    """
    async with _sessions(request)() as session:
        established = await is_owner_established(session)

    if not established:
        if access is Access.SETUP_OPENING:
            return None
        return _refuse(status.HTTP_403_FORBIDDEN, "finish step 1 of the setup wizard first")
    if user is None:
        return _refuse(status.HTTP_401_UNAUTHORIZED, "sign in to continue the setup wizard")
    if not admits(access, user.role):
        return _refuse(status.HTTP_403_FORBIDDEN, "administrators only")
    return None


def _admin_verdict(user: AuthenticatedUser | None) -> JSONResponse | None:
    """改設定是管理員的事；一般使用者看得到健康頁，但按不了那幾顆按鈕（brief §11）。"""
    if user is None:
        return _refuse(status.HTTP_401_UNAUTHORIZED, "sign in to use this API")
    if not admits(Access.ADMIN, user.role):
        return _refuse(status.HTTP_403_FORBIDDEN, "administrators only")
    return None


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


def current_actor(request: Request) -> str:
    """寫進 `events.actor` 的那個人：登入的 user id，沒有人就是 `system`（plan §2.3）。"""
    user = current_user(request)
    return actor_of(user.id if user is not None else None)


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
