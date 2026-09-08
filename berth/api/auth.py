"""登入、登出與「我是誰」（plan §6 auth 群組、票 07）。

密碼只在這三支端點之間經過一次，不進 log、不回到回應裡；session token 只走 httpOnly
cookie，前端 JavaScript 讀不到它。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from berth.api.deps import ClientFactoryDep, SessionDep
from berth.api.gate import SESSION_COOKIE, current_user
from berth.domain import Role
from berth.services.auth import (
    SESSION_TTL,
    InvalidCredentialsError,
    JellyfinUnavailableError,
    sign_in,
    sign_out,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    """帳密**不加約束、也不設必填**：少一個欄位就會是 422，而 422 與 401 分得出來就是一個
    可以拿來試探的差別。空的與錯的一律交給 services 拒絕，回同一個 401。

    422 的回應本身不帶收到的值——那是 `api/errors.py` 的事。
    """

    username: str = ""
    password: str = ""


class MeOut(BaseModel):
    """使用者可見的身分。id 與 Jellyfin user id 都不外流——UI 用不到。"""

    name: str
    role: Role


@router.post("/login")
async def post_login(
    session: SessionDep, factory: ClientFactoryDep, body: LoginIn, response: Response
) -> MeOut:
    try:
        signed = await sign_in(session, factory, username=body.username, password=body.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    except JellyfinUnavailableError as exc:
        # 密碼沒有錯，是身分來源不在。UI 要說得出這兩件事的差別（brief §11）。
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    response.set_cookie(
        SESSION_COOKIE,
        signed.token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        samesite="strict",
        path="/",
        # 刻意不設 `secure`：自架幾乎都是區網的純 HTTP 位址，設了 cookie 根本存不下來。
        # 防線是 httpOnly + SameSite=Strict + CSRF 標頭（plan §6）；HTTPS 交給前置代理。
    )
    return MeOut(name=signed.user.name, role=signed.user.role)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def post_logout(session: SessionDep, request: Request, response: Response) -> None:
    """一律成功。session 早就過期的人也該把瀏覽器裡那張 cookie 清掉。"""
    await sign_out(session, request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="strict")


@router.get("/me")
async def get_me(request: Request) -> MeOut:
    """門禁已經擋掉沒有 session 的請求，所以走到這裡一定有人。"""
    user = current_user(request)
    if user is None:  # pragma: no cover - 門禁保證不會發生
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sign in to use this API")
    return MeOut(name=user.name, role=user.role)
