"""通知管道的 adapter 介面（plan §11.5〈通知〉、M4 票 123）。

一個管道做一件事：**送一則給一位收件人，回成功或分類過的失敗**。失敗不丟例外而是回值：送出迴圈
要逐則記下原因、一則失敗不拖累下一則，「測試」要當場說出是哪一種——每一個呼叫端都要接住它，
用回值才不會有人漏接。

M4 唯一的實作是 Discord bot 私訊（`discord.py`）；訊息的形狀（`Message`）不認 Discord，
組字在 `services.notify`。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from berth.domain import DeliveryFailure


@dataclass(frozen=True, slots=True)
class Link:
    """點了開到哪：Berth 的那一頁（`deeplink.berth_link`）。`label` 照收件人的語言組好。"""

    label: str
    url: str


@dataclass(frozen=True, slots=True)
class Message:
    """一則通知：標題、一段內文、幾格「名稱 → 值」。句子已經照收件人的語言組好。"""

    title: str
    description: str = ""
    fields: tuple[tuple[str, str], ...] = ()
    #: 空的是沒有連結（Berth 的網址沒存）。「有 N 件等你處理」一波跨好幾種時每一種一條
    #: （M4 票 127）。怎麼放是管道的事。
    links: tuple[Link, ...] = ()


@dataclass(frozen=True, slots=True)
class Delivery:
    """送一則的結果。`failure` 是 `None` 就是送到了。"""

    failure: DeliveryFailure | None = None
    #: 管道回的原文（狀態碼、錯誤代碼與訊息），給「技術細節」與 `notifications.error`。不含憑證。
    detail: str = ""
    #: 限速時管道說的「幾秒後再來」。送出迴圈照它延後（M4 票 128）。
    retry_after: float | None = None
    #: 限速是整個管道的（Discord 的 `global`），不是這一則的 bucket：等的是後面每一則。
    whole_channel: bool = False

    @property
    def delivered(self) -> bool:
        return self.failure is None


@dataclass(frozen=True, slots=True)
class BotIdentity:
    """bot token 背後的那一個 application（Discord 的 `GET /applications/@me`）。"""

    application_id: str
    name: str


class NotifyChannel(Protocol):
    async def send(self, recipient: str, message: Message) -> Delivery:
        """送一則給 `recipient`（Discord 是 user ID）。**不丟例外**：連不上也是一個 `Delivery`。"""
        ...


class DiscordBot(NotifyChannel, Protocol):
    async def identify(self) -> BotIdentity:
        """這個 token 是哪一個 bot。被拒是 `AuthFailedError`，問不到是其餘的 `ServiceError`。"""
        ...


__all__ = ["BotIdentity", "Delivery", "DiscordBot", "Link", "Message", "NotifyChannel"]
