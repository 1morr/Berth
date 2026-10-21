"""`DiscordBot` 的替身（plan §1.3）：整合測試與演練伺服器用它取代 Discord。

送出的每一則記在 `sent`。`failures` 依序決定接下來幾則的結果（用完就是送到），讓「這一輪 5xx、
下一輪送到」寫得出來；`rejected_tokens` 與 `unreachable` 是兩種固定的拒絕，演練伺服器靠它們
在畫面上演出失敗。
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from berth.adapters.http import AuthFailedError, ServiceError
from berth.adapters.notify import BotIdentity, Delivery, Message
from berth.domain import DeliveryFailure

#: 票 121 錄到的原文（`tests/fixtures/http/discord/channels-messages.no-mutual-guild.json`）。
_NO_MUTUAL_GUILDS = "Cannot send messages to this user due to having no mutual guilds"


class FakeDiscordBot:
    def __init__(
        self,
        *,
        identity: BotIdentity | None = None,
        failures: Iterable[Delivery] = (),
        rejected_tokens: Iterable[str] = (),
        unreachable: Iterable[str] = (),
    ) -> None:
        self.identity = identity or BotIdentity(application_id="1000000000000000001", name="berth")
        self.failures: deque[Delivery] = deque(failures)
        #: Discord 不接受的 token（`401`）。
        self.rejected_tokens = set(rejected_tokens)
        #: 到不了的收件人（`403` / `50278`）。
        self.unreachable = set(unreachable)
        #: `identify()` 要丟的錯；`None` 是答得出來。
        self.identify_error: ServiceError | None = None
        #: 工廠造它時給的那一把（`FakeClientFactory.discord`）。
        self.token = ""
        self.sent: list[tuple[str, Message]] = []

    async def identify(self) -> BotIdentity:
        if self.identify_error is not None:
            raise self.identify_error
        if self.token in self.rejected_tokens:
            raise AuthFailedError("GET /applications/@me: 401")
        return self.identity

    async def send(self, recipient: str, message: Message) -> Delivery:
        if self.token in self.rejected_tokens:
            return Delivery(
                failure=DeliveryFailure.UNAUTHORIZED, detail="401 code=0 401: Unauthorized"
            )
        if recipient in self.unreachable:
            return Delivery(
                failure=DeliveryFailure.RECIPIENT_UNREACHABLE,
                detail=f"403 code=50278 {_NO_MUTUAL_GUILDS}",
            )
        if self.failures:
            return self.failures.popleft()
        self.sent.append((recipient, message))
        return Delivery()
