"""通知設定的端點（plan §11.5〈通知〉、M4 票 123、125）。兩半，各在自己的門後：

- `/settings/notifications`：bot token 與 Berth 的網址。掛在 `/settings` 底下，所以只有管理員進得來
  （`api/gate.py`）。
- `/me/notifications`：每一位登入的人自己的 Discord ID、要收的種類、測試（M4 票 125）。不在任何
  管理員前綴底下，照預設規則登入就行；收件人永遠是 session 上的那一個人，沒有收 user id 的參數。

**bot token 只進不出**：管理員那一半回的是 `NotifyBotOut`，它只說「設定了沒」與 bot 的名字；
「我的」那一半連邀請連結都沒有。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from berth.api.deps import ClientFactoryDep, SessionDep
from berth.api.errors import refusal_responses
from berth.api.gate import current_user
from berth.domain import DeliveryFailure, Language, NotificationKind, NotifyRefusal
from berth.services.notify import (
    NotifyRefusedError,
    read_bot,
    read_mine,
    send_test,
    set_berth_url,
    set_bot_token,
    set_mine,
)

router = APIRouter(prefix="/settings/notifications", tags=["settings"])
#: 每一位登入的人自己的那一半（M4 票 125）。`api/__init__.py` 一起掛上。
me_router = APIRouter(prefix="/me/notifications", tags=["notifications"])

_STATUS: dict[NotifyRefusal, int] = {
    NotifyRefusal.TOKEN_REJECTED: status.HTTP_422_UNPROCESSABLE_CONTENT,
    NotifyRefusal.DISCORD_UNREACHABLE: status.HTTP_502_BAD_GATEWAY,
    NotifyRefusal.DISCORD_ID_INVALID: status.HTTP_422_UNPROCESSABLE_CONTENT,
    NotifyRefusal.BERTH_URL_INVALID: status.HTTP_422_UNPROCESSABLE_CONTENT,
    #: 測試的前提還沒齊：先設 token、先填 ID。
    NotifyRefusal.BOT_MISSING: status.HTTP_409_CONFLICT,
    NotifyRefusal.DISCORD_ID_MISSING: status.HTTP_409_CONFLICT,
}


class NotifyRefusalOut(BaseModel):
    """與其他群組的拒絕同形：`reason` 挑句子，`detail` 是 Discord 的原文（沒有就是空字串）。"""

    reason: NotifyRefusal
    detail: str


def _responses(*reasons: NotifyRefusal) -> dict[int | str, dict[str, Any]]:
    return refusal_responses(NotifyRefusalOut, {reason: _STATUS[reason] for reason in reasons})


def notify_refusal(refusal: NotifyRefusedError) -> HTTPException:
    body = NotifyRefusalOut(reason=refusal.reason, detail=refusal.detail)
    return HTTPException(status_code=_STATUS[refusal.reason], detail=body.model_dump(mode="json"))


class NotifyBotOut(BaseModel):
    """管理員那一半。"""

    model_config = ConfigDict(from_attributes=True)

    #: 存過 bot token 沒有。token 本身永遠不回來。
    bot_configured: bool
    #: Discord 上那個 application 的名字；沒設定是空字串。
    bot_name: str
    #: 邀請 bot 進伺服器的連結（`scope=bot&permissions=0`）；沒設定是 `null`。
    invite_url: str | None
    #: Discord 不再接受存著的那一把 token（之後被重設了）：通知暫停到換一把（M4 票 128）。
    token_rejected: bool
    #: Berth 從外面看的網址，通知裡的連結照它組；沒存過是空字串（不附連結）。
    berth_url: str


class MyNotifyOut(BaseModel):
    """「我的通知」：登入的這個人自己的那一份（M4 票 125）。"""

    model_config = ConfigDict(from_attributes=True)

    #: 管理員設好 bot 沒有：沒有的話測試按不了。
    bot_configured: bool
    #: 私訊會從哪一個 bot 來；沒設定是空字串。
    bot_name: str
    #: 這個人的 Discord user ID；沒填是空字串。
    discord_user_id: str
    #: 通知用哪個語言寫給這個人。
    language: Language
    #: 訂閱的種類，照 `NotificationKind` 的順序。
    kinds: list[NotificationKind]
    #: 上一次送給這個人時 Discord 說他到不了（`403` / `50278`）；`null` 是沒有。
    #: 送到一則或換 ID 就清掉。
    unreachable_at: datetime | None
    #: 那一次 Discord 的原文，給「技術細節」。
    unreachable_detail: str


class BotTokenIn(BaseModel):
    #: 空字串是清掉。
    token: str


class MyNotifyIn(BaseModel):
    #: 空字串是不收。
    discord_user_id: str
    #: 送出這一刻的介面語言：通知用它寫。
    language: Language
    #: 要收的種類；空的是什麼都不收（ID 留著，測試照樣按得了）。
    kinds: list[NotificationKind]


class BerthUrlIn(BaseModel):
    #: `https://berth.example.com`。空字串是清掉。
    berth_url: str


class NotifyTestOut(BaseModel):
    """`adapters.notify.Delivery` 的線上形狀。"""

    model_config = ConfigDict(from_attributes=True)

    delivered: bool
    #: 沒送到時的分類；送到是 `null`。
    failure: DeliveryFailure | None
    #: Discord 的原文（狀態碼、錯誤代碼、訊息），給「技術細節」。
    detail: str
    #: 限速時 Discord 說的「幾秒後再來」。
    retry_after: float | None


def _user_id(request: Request) -> int:
    user = current_user(request)
    # 兩組都在要登入的門後面，門禁跑過之後一定有人。
    assert user is not None
    return user.id


@router.get("")
async def get_notifications(session: SessionDep) -> NotifyBotOut:
    return NotifyBotOut.model_validate(await read_bot(session))


@router.put(
    "/bot",
    responses=_responses(NotifyRefusal.TOKEN_REJECTED, NotifyRefusal.DISCORD_UNREACHABLE),
)
async def put_bot(session: SessionDep, factory: ClientFactoryDep, body: BotTokenIn) -> NotifyBotOut:
    """存 bot token：先問 Discord 它是哪一個 bot，問得到才存。"""
    try:
        view = await set_bot_token(session, factory, body.token)
    except NotifyRefusedError as exc:
        raise notify_refusal(exc) from exc
    return NotifyBotOut.model_validate(view)


@router.put("/berth-url", responses=_responses(NotifyRefusal.BERTH_URL_INVALID))
async def put_berth_url(session: SessionDep, body: BerthUrlIn) -> NotifyBotOut:
    """存 Berth 從外面看的網址：不是 http(s) 的絕對網址回 422 `berth_url_invalid`（M4 票 124）。"""
    try:
        view = await set_berth_url(session, body.berth_url)
    except NotifyRefusedError as exc:
        raise notify_refusal(exc) from exc
    return NotifyBotOut.model_validate(view)


@me_router.get("")
async def get_mine(session: SessionDep, request: Request) -> MyNotifyOut:
    return MyNotifyOut.model_validate(await read_mine(session, _user_id(request)))


@me_router.put("", responses=_responses(NotifyRefusal.DISCORD_ID_INVALID))
async def put_mine(session: SessionDep, request: Request, body: MyNotifyIn) -> MyNotifyOut:
    try:
        view = await set_mine(
            session, _user_id(request), body.discord_user_id, body.language, body.kinds
        )
    except NotifyRefusedError as exc:
        raise notify_refusal(exc) from exc
    return MyNotifyOut.model_validate(view)


@me_router.post(
    "/test",
    responses=_responses(NotifyRefusal.BOT_MISSING, NotifyRefusal.DISCORD_ID_MISSING),
)
async def post_test(
    session: SessionDep, factory: ClientFactoryDep, request: Request
) -> NotifyTestOut:
    """送一則測試訊息給按的人。Discord 拒絕也是 200：那是「測試的結果」，不是請求錯了。"""
    try:
        delivery = await send_test(session, factory, _user_id(request))
    except NotifyRefusedError as exc:
        raise notify_refusal(exc) from exc
    return NotifyTestOut.model_validate(delivery)
