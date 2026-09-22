"""登入與 session（plan §11.1 T0.5、brief §11）。

Berth 沒有密碼系統：憑證交給 Jellyfin 驗，`Policy.IsAdministrator` 決定角色，`users`
只是本地鏡射。驗過之後 Berth 發自己的 session，之後每個請求都只認那張 cookie——
不必為了每次呼叫再問一次 Jellyfin。

取捨照 brief §11：Jellyfin 掛掉時沒有人登得進來（Seerr 同樣如此），所以「連不上」與
「密碼錯誤」在這裡是兩種例外，UI 才說得出差別。
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import AuthFailedError, ServiceError
from berth.adapters.jellyfin import JellyfinAuth
from berth.domain import Role
from berth.models import JellyfinSettings, User, UserSession
from berth.services.clients import ServiceClientFactory
from berth.services.settings import read_settings

#: session 的絕對壽命。不滑動續期：到期就是到期，重登一次即可（票 07 驗收）。
SESSION_TTL = timedelta(days=30)

#: token 的亂數位元組數。`token_urlsafe` 出來是 43 個字元。
TOKEN_BYTES = 32


class InvalidCredentialsError(Exception):
    """帳密不對。**刻意不分辨是哪一個**——分辨得出來就是在幫人列舉帳號。"""


class JellyfinUnavailableError(Exception):
    """問不到 Jellyfin：位址還沒設定，或那台伺服器連不上。

    這不是使用者打錯了，訊息與處置都該不一樣（brief §11 的取捨）。
    """


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """一個已登入的使用者。API 與門禁只看得到這個形狀，看不到 ORM。"""

    id: int
    name: str
    role: Role
    #: 替這個人向 Jellyfin 讀東西時帶的 `userId`（`services/jellyfin_access.py`）。**只從 session
    #: 來**：API key 帶誰的 id 就是誰，所以前端送來的 id 一個都不收（plan §11.2b）。
    jellyfin_user_id: str


@dataclass(frozen=True, slots=True)
class SignedIn:
    """一次成功的登入。`token` 只在這裡出現一次，之後只存得下它的雜湊。"""

    user: AuthenticatedUser
    token: str


async def sign_in(
    session: AsyncSession,
    factory: ServiceClientFactory,
    *,
    username: str,
    password: str,
) -> SignedIn:
    """以 Jellyfin 帳密換一張 Berth session。呼叫端不必再 commit。"""
    if not username.strip() or not password:
        # 空白憑證不必打擾 Jellyfin，但回的仍是同一種拒絕。
        raise InvalidCredentialsError(_REFUSAL)

    auth = await _authenticate(session, factory, username, password)
    user = await _mirror_user(session, auth)
    token = secrets.token_urlsafe(TOKEN_BYTES)
    session.add(
        UserSession(
            user_id=user.id, token_hash=token_digest(token), expires_at=_utcnow() + SESSION_TTL
        )
    )
    await session.commit()
    return SignedIn(user=user, token=token)


async def read_session(session: AsyncSession, token: str | None) -> AuthenticatedUser | None:
    """token 背後的使用者，沒有或已過期就是 `None`。

    過期的列就地刪掉，所以「自動失效」不必等背景工作。呼叫端負責 commit。
    """
    if not token:
        return None

    row = await session.scalar(
        select(UserSession).where(UserSession.token_hash == token_digest(token))
    )
    if row is None:
        return None
    if row.expires_at <= _utcnow():
        await session.delete(row)
        return None

    user = await session.get(User, row.user_id)
    return None if user is None else _view(user)


async def sign_out(session: AsyncSession, token: str | None) -> None:
    """使這一張 session 失效。其他裝置上的 session 不動。"""
    if not token:
        return
    await session.execute(delete(UserSession).where(UserSession.token_hash == token_digest(token)))
    await session.commit()


async def end_sessions(session: AsyncSession, user_id: int) -> None:
    """這個人在每一台裝置上的 session 全部失效，並當場 commit。

    Jellyfin 停用了他的帳號時呼叫（`services/jellyfin_access.py`）。**自己 commit**：呼叫端接著會丟
    例外，而請求的工作單元遇到例外是 rollback（`api/deps.get_session`）。
    """
    await session.execute(delete(UserSession).where(UserSession.user_id == user_id))
    await session.commit()


def token_digest(token: str) -> str:
    """存進 `sessions.token_hash` 的值。

    資料庫被看到時 cookie 不該還能用，所以存雜湊而不是 token 本身。不加 salt 也不用
    KDF：token 是 256 bit 的亂數，沒有字典可以查，慢雜湊只會讓每個請求變慢。
    """
    return hashlib.sha256(token.encode()).hexdigest()


async def _authenticate(
    session: AsyncSession,
    factory: ServiceClientFactory,
    username: str,
    password: str,
) -> JellyfinAuth:
    """把憑證交給 Jellyfin。這是整個系統唯一驗證密碼的地方。"""
    jellyfin = await read_settings(session, JellyfinSettings)
    if not jellyfin.base_url:
        raise JellyfinUnavailableError("jellyfin address is not configured yet")

    client = factory.jellyfin(jellyfin.base_url)
    try:
        auth = await client.authenticate(username, password)
    except AuthFailedError as exc:
        # 例外訊息會進 log，所以只留「被拒絕了」，不留憑證。
        raise InvalidCredentialsError(_REFUSAL) from exc
    except ServiceError as exc:
        raise JellyfinUnavailableError(f"jellyfin at {jellyfin.base_url} did not answer") from exc
    finally:
        await client.aclose()
    return auth


async def _mirror_user(session: AsyncSession, auth: JellyfinAuth) -> AuthenticatedUser:
    """`users` 是鏡射，不是真相：名字與角色每次登入都照 Jellyfin 重寫。

    同一個新使用者的兩次登入同時進來時，兩邊都在對方 commit 之前讀過 `users`，所以兩邊都
    以為自己是第一個，後到的那一個撞上 `users.jellyfin_user_id` 的唯一索引。那不是使用者
    做錯了什麼，是兩個分頁同時按下登入——重讀之後照樣發 session（票 01）。
    """
    role = Role.ADMIN if auth.is_administrator else Role.USER
    row = await _find_mirror(session, auth.user_id) or await _insert_mirror(session, auth, role)
    row.name = auth.name
    row.role = role
    row.last_login_at = _utcnow()
    # id 要在建 session 之前拿得到。
    await session.flush()
    return _view(row)


async def _insert_mirror(session: AsyncSession, auth: JellyfinAuth, role: Role) -> User:
    """建這個人的那一列，或者在另一個分頁搶先建好時拿它建的那一列。

    回滾掉的只有這一次 insert：`sign_in` 走到這裡為止只讀過東西，session 沒有別的待寫。
    """
    row = User(jellyfin_user_id=auth.user_id, name=auth.name, role=role)
    session.add(row)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        theirs = await _find_mirror(session, auth.user_id)
        if theirs is None:
            # 撞的不是這個人那一列，那就沒有第二種解釋了。
            raise
        return theirs
    return row


async def _find_mirror(session: AsyncSession, jellyfin_user_id: str) -> User | None:
    row: User | None = await session.scalar(
        select(User).where(User.jellyfin_user_id == jellyfin_user_id)
    )
    return row


def _view(user: User) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user.id, name=user.name, role=user.role, jellyfin_user_id=user.jellyfin_user_id
    )


def _utcnow() -> datetime:
    return datetime.now(UTC)


#: 唯一的拒絕訊息。「帳號不存在」與「密碼錯誤」用同一句（票 07 驗收）。
_REFUSAL = "invalid username or password"
