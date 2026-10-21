"""Discord bot 私訊 adapter 對錄製回應的契約（M4 票 123；回應是票 121 對 API v10 錄的）。

`tests/fixtures/http/discord/` 的每一份是 `{status, headers, body}`。替身伺服器照原樣回它們，
斷言 adapter 把每一種分到對的 `DeliveryFailure`。
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from berth.adapters.http import AuthFailedError
from berth.adapters.notify import Message
from berth.adapters.notify.discord import HttpDiscordBot, invite_url
from berth.config import DEFAULT_DISCORD_API_URL as DEFAULT_API_URL
from berth.domain import DeliveryFailure
from tests.conftest import read_fixture

pytestmark = pytest.mark.asyncio

TOKEN = "bot-token-0123456789"
RECIPIENT = "000000000000000001"
CHANNEL = "000000000000000002"
OPEN = f"{DEFAULT_API_URL}/users/@me/channels"
SEND = f"{DEFAULT_API_URL}/channels/{CHANNEL}/messages"
MESSAGE = Message(
    title="可以看了：葬送的芙莉蓮", description="S02E05", fields=(("Route", "Anime"),)
)

#: 錄下來的這幾個標頭描述的是那一次的傳輸，交給替身會與它自己算的長度打架。
_TRANSPORT = {"content-length", "transfer-encoding", "connection"}


def recorded(name: str) -> httpx.Response:
    record: dict[str, Any] = json.loads(read_fixture(f"http/discord/{name}.json"))
    headers = {k: v for k, v in record["headers"].items() if k.lower() not in _TRANSPORT}
    return httpx.Response(record["status"], json=record["body"], headers=headers)


def bot() -> HttpDiscordBot:
    return HttpDiscordBot(TOKEN)


@respx.mock
async def test_a_message_reaches_the_recipient_in_two_steps() -> None:
    opened = respx.post(OPEN).mock(return_value=recorded("users-me-channels.created"))
    sent = respx.post(SEND).mock(return_value=recorded("channels-messages.embed"))

    delivery = await bot().send(RECIPIENT, MESSAGE)

    assert delivery.delivered
    assert json.loads(opened.calls.last.request.content) == {"recipient_id": RECIPIENT}
    request = sent.calls.last.request
    assert request.headers["Authorization"] == f"Bot {TOKEN}"
    assert request.headers["User-Agent"].startswith("DiscordBot (")
    payload = json.loads(request.content)
    # 作品名是別人寫的字：一個 mention 都不解析。
    assert payload["allowed_mentions"] == {"parse": []}
    (embed,) = payload["embeds"]
    assert embed["title"] == MESSAGE.title
    assert embed["description"] == "S02E05"
    assert embed["fields"] == [{"name": "Route", "value": "Anime", "inline": True}]


@respx.mock
async def test_a_plain_text_answer_is_also_delivered() -> None:
    """純文字訊息那一份回應（`content`、沒有 embed）的形狀一樣算送到。"""
    respx.post(OPEN).mock(return_value=recorded("users-me-channels.created"))
    respx.post(SEND).mock(return_value=recorded("channels-messages.created"))

    assert (await bot().send(RECIPIENT, MESSAGE)).delivered


@pytest.mark.parametrize(
    "fixture", ["channels-messages.no-mutual-guild", "channels-messages.dm-closed"]
)
@respx.mock
async def test_no_mutual_guild_and_closed_dms_are_the_same_unreachable_recipient(
    fixture: str,
) -> None:
    """開 DM channel 是 200，擋下來的是送訊息那一步；兩種情況 Discord 回的是同一個 `50278`。"""
    respx.post(OPEN).mock(return_value=recorded("users-me-channels.created"))
    respx.post(SEND).mock(return_value=recorded(fixture))

    delivery = await bot().send(RECIPIENT, MESSAGE)

    assert delivery.failure is DeliveryFailure.RECIPIENT_UNREACHABLE
    assert "50278" in delivery.detail


@respx.mock
async def test_a_wrong_token_is_unauthorized_at_the_first_step() -> None:
    respx.post(OPEN).mock(return_value=recorded("users-me-channels.unauthorized"))
    sent = respx.post(SEND)

    delivery = await bot().send(RECIPIENT, MESSAGE)

    assert delivery.failure is DeliveryFailure.UNAUTHORIZED
    assert not sent.called


@respx.mock
async def test_rate_limiting_says_when_to_come_back() -> None:
    """body 的 `retry_after` 是下一個空位（浮點秒），header 的 `Retry-After` 是整個 bucket。"""
    respx.post(OPEN).mock(return_value=recorded("users-me-channels.created"))
    respx.post(SEND).mock(return_value=recorded("channels-messages.rate-limited"))

    delivery = await bot().send(RECIPIENT, MESSAGE)

    assert delivery.failure is DeliveryFailure.RATE_LIMITED
    assert delivery.retry_after == pytest.approx(0.3)
    assert not delivery.whole_channel


@respx.mock
async def test_a_global_rate_limit_is_said_to_hold_the_whole_channel() -> None:
    """`global: true`（Discord 文件 Rate Limits；票 121 沒量到，從錄的那一份翻 `global`）。"""
    respx.post(OPEN).mock(return_value=recorded("users-me-channels.created"))
    limited = recorded("channels-messages.rate-limited")
    body = {**json.loads(limited.content), "global": True}
    headers = {k: v for k, v in limited.headers.items() if k.lower() not in _TRANSPORT}
    respx.post(SEND).mock(return_value=httpx.Response(429, json=body, headers=headers))

    delivery = await bot().send(RECIPIENT, MESSAGE)

    assert delivery.failure is DeliveryFailure.RATE_LIMITED
    assert delivery.whole_channel


@pytest.mark.parametrize(
    "fixture", ["channels-messages.content-too-long", "channels-messages.embeds-too-long"]
)
@respx.mock
async def test_an_oversized_message_is_rejected(fixture: str) -> None:
    respx.post(OPEN).mock(return_value=recorded("users-me-channels.created"))
    respx.post(SEND).mock(return_value=recorded(fixture))

    delivery = await bot().send(RECIPIENT, MESSAGE)

    assert delivery.failure is DeliveryFailure.REJECTED
    assert "50035" in delivery.detail


@pytest.mark.parametrize("status", [500, 502, 503])
@respx.mock
async def test_a_discord_outage_is_unavailable(status: int) -> None:
    respx.post(OPEN).mock(return_value=recorded("users-me-channels.created"))
    respx.post(SEND).mock(return_value=httpx.Response(status))

    delivery = await bot().send(RECIPIENT, MESSAGE)

    assert delivery.failure is DeliveryFailure.UNAVAILABLE


@respx.mock
async def test_a_refused_connection_is_unavailable_not_an_exception() -> None:
    respx.post(OPEN).mock(side_effect=httpx.ConnectError("refused"))

    delivery = await bot().send(RECIPIENT, MESSAGE)

    assert delivery.failure is DeliveryFailure.UNAVAILABLE


@respx.mock
async def test_an_answer_without_a_channel_is_unavailable_not_an_exception() -> None:
    """`send` 不丟例外：開 channel 回了 200 卻不像 Discord（沒有 `id`）也是一個 `Delivery`。"""
    respx.post(OPEN).mock(return_value=httpx.Response(200, json={"message": "hello"}))

    delivery = await bot().send(RECIPIENT, MESSAGE)

    assert delivery.failure is DeliveryFailure.UNAVAILABLE


@respx.mock
async def test_identify_reads_the_application_behind_the_token() -> None:
    """`GET /applications/@me` 沒有錄製回應（回應裡有 application 擁有者的帳號，票 121 不存）；
    這裡只用文件上的兩格（Application Object 的 `id`、`name`，brief §20.23）。"""
    route = respx.get(f"{DEFAULT_API_URL}/applications/@me").mock(
        return_value=httpx.Response(200, json={"id": "000000000000000004", "name": "berth-bot"})
    )

    identity = await bot().identify()

    assert (identity.application_id, identity.name) == ("000000000000000004", "berth-bot")
    assert route.calls.last.request.headers["Authorization"] == f"Bot {TOKEN}"


@respx.mock
async def test_identify_with_a_wrong_token_is_auth_failed() -> None:
    respx.get(f"{DEFAULT_API_URL}/applications/@me").mock(
        return_value=recorded("users-me-channels.unauthorized")
    )

    with pytest.raises(AuthFailedError):
        await bot().identify()


@respx.mock
async def test_the_base_url_can_point_elsewhere() -> None:
    """票 133 的 e2e 把它指到假的 Discord（`DISCORD_API_URL`）。"""
    elsewhere = "http://fake-discord:9000/api/v10"
    route = respx.post(f"{elsewhere}/users/@me/channels").mock(
        return_value=recorded("users-me-channels.created")
    )
    respx.post(f"{elsewhere}/channels/{CHANNEL}/messages").mock(
        return_value=recorded("channels-messages.created")
    )

    assert (await HttpDiscordBot(TOKEN, base_url=elsewhere).send(RECIPIENT, MESSAGE)).delivered
    assert route.called


async def test_the_invite_asks_for_the_bot_scope_and_no_permissions() -> None:
    assert invite_url("42") == (
        "https://discord.com/oauth2/authorize?client_id=42&scope=bot&permissions=0"
    )
