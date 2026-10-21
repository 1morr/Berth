"""Discord bot 私訊（brief §20.23；M4 票 121 實測，回應錄在 `tests/fixtures/http/discord/`）。

私訊是兩步：`POST /users/@me/channels`（`recipient_id`）開 DM channel，再
`POST /channels/{id}/messages`。純 REST、不必連 gateway、不需要 intent。**開 channel 什麼情況都回
`200`**，擋下來的是送訊息那一步（沒有共同伺服器、收件人關了私訊、bot 被踢出都是 `403` / `50278`）。

**token 只走 `Authorization` 標頭**：Berth 不記標頭，httpx 的 log 只有方法與網址，所以 token 不會經
網址或錯誤訊息進日誌（`Delivery.detail` 只抄回應 body 的代碼與訊息）。

base URL 可以換（`DISCORD_API_URL`，票 133 的 e2e 指到假伺服器），預設是 API v10。
"""

from __future__ import annotations

from typing import Any

import httpx

from berth.adapters.http import HttpSession, ProtocolMismatchError, ServiceError, json_body
from berth.adapters.notify import BotIdentity, Delivery, Message
from berth.config import DEFAULT_DISCORD_API_URL, VERSION
from berth.domain import DeliveryFailure

#: Discord 要求 bot 的 User-Agent 是 `DiscordBot ($url, $versionNumber)` 這個形狀。
USER_AGENT = f"DiscordBot (https://github.com/1morr/Berth, {VERSION})"

#: 只私訊的邀請：`bot` scope 讓 bot 進伺服器（共同伺服器），私訊不需要任何伺服器權限。
INVITE_URL = (
    "https://discord.com/oauth2/authorize?client_id={application_id}&scope=bot&permissions=0"
)

#: 收件人到不了：沒有共同伺服器或關了私訊（實測，分不出來）、不能傳訊息給這位使用者（文件）。
_UNREACHABLE_CODES = frozenset({50278, 50007})

#: Discord 會用 4xx 講一件有內容的事，這幾個原樣拿回來自己分類。
_ANSWERS = (400, 401, 403, 404, 429)

#: embed 各欄的上限（Discord 的 Embed Limits）。組字的那一層照理不會超過；超過就截，
#: 總比整則被拒好。
_TITLE_MAX = 256
_DESCRIPTION_MAX = 4096
_FIELD_NAME_MAX = 256
_FIELD_VALUE_MAX = 1024
_FOOTER = "Berth"
#: 內文與連結之間空一行。
_PARAGRAPH = "\n\n"


def invite_url(application_id: str) -> str:
    """邀請這個 bot 進伺服器的連結（brief §20.23）。"""
    return INVITE_URL.format(application_id=application_id)


class HttpDiscordBot:
    def __init__(self, token: str, *, base_url: str = DEFAULT_DISCORD_API_URL) -> None:
        self._base_url = base_url
        self._token = token

    def _session(self) -> HttpSession:
        return HttpSession(
            self._base_url,
            headers={"Authorization": f"Bot {self._token}", "User-Agent": USER_AGENT},
        )

    async def identify(self) -> BotIdentity:
        async with self._session() as http:
            body = json_body(await http.get("/applications/@me"))
        return BotIdentity(application_id=str(body["id"]), name=str(body.get("name", "")))

    async def send(self, recipient: str, message: Message) -> Delivery:
        try:
            async with self._session() as http:
                opened = await http.request(
                    "POST",
                    "/users/@me/channels",
                    json={"recipient_id": recipient},
                    tolerate=_ANSWERS,
                )
                if opened.status_code != 200:
                    return _failed(opened)
                channel = _channel_id(json_body(opened))
                sent = await http.request(
                    "POST",
                    f"/channels/{channel}/messages",
                    json=_payload(message),
                    tolerate=_ANSWERS,
                )
                if sent.status_code != 200:
                    return _failed(sent)
        except ServiceError as exc:
            # 連不上、逾時、5xx（`HttpSession` 已經分好類），與回的不是 Discord。
            return Delivery(failure=DeliveryFailure.UNAVAILABLE, detail=str(exc))
        return Delivery()


def _payload(message: Message) -> dict[str, Any]:
    embed: dict[str, Any] = {"title": message.title[:_TITLE_MAX], "footer": {"text": _FOOTER}}
    if description := _description(message):
        embed["description"] = description
    if message.fields:
        embed["fields"] = [
            {"name": name[:_FIELD_NAME_MAX], "value": value[:_FIELD_VALUE_MAX], "inline": True}
            for name, value in message.fields
        ]
    # 內容裡有作品名這種別人寫的字：一個 mention 都不解析。
    return {"embeds": [embed], "allowed_mentions": {"parse": []}}


def _description(message: Message) -> str:
    """內文，連結接在最後一行。**連結不放 embed 的 `url`**：沒有點的主機名（`http://berth:8000`）
    在那一格是整則 `400` `URL_TYPE_INVALID_URL`，寫成 Markdown 連結就收（M4 票 124 實測，
    brief §20.23）。截的是內文，連結整條留著。"""
    if message.link is None:
        return message.description[:_DESCRIPTION_MAX]
    link = f"[{message.link.label}]({message.link.url})"
    if not message.description:
        return link
    room = _DESCRIPTION_MAX - len(link) - len(_PARAGRAPH)
    return f"{message.description[:room]}{_PARAGRAPH}{link}"


def _channel_id(body: Any) -> str:
    """開 DM channel 的回應裡的 channel id。沒有就是回的不是 Discord：`send` 不丟例外，所以翻成
    `ServiceError` 讓上面那一層接成 `unavailable`。"""
    channel = body.get("id") if isinstance(body, dict) else None
    if not isinstance(channel, str) or not channel:
        raise ProtocolMismatchError("POST /users/@me/channels: no channel id in the answer")
    return channel


def _failed(response: httpx.Response) -> Delivery:
    body = _body(response)
    code = body.get("code")
    detail = f"{response.status_code} code={code} {body.get('message', '')}".rstrip()
    status = response.status_code
    if status == 401:
        return Delivery(failure=DeliveryFailure.UNAUTHORIZED, detail=detail)
    if status == 429:
        retry = body.get("retry_after")
        return Delivery(
            failure=DeliveryFailure.RATE_LIMITED,
            detail=detail,
            retry_after=float(retry) if isinstance(retry, int | float) else None,
            whole_channel=body.get("global") is True,
        )
    if status == 403 and code in _UNREACHABLE_CODES:
        return Delivery(failure=DeliveryFailure.RECIPIENT_UNREACHABLE, detail=detail)
    return Delivery(failure=DeliveryFailure.REJECTED, detail=detail)


def _body(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}
