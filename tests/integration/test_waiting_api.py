"""頁首的件數（M5.5 票 07）：`GET /waiting` 照來源數，只有管理員。

怎麼算「等著」是 `waiting.waiting_now` 的事（`test_notify_waiting.py`）；這裡只驗端點的形狀與門禁。
三格加起來等於 Discord 那個 N 的等式也在 `test_notify_waiting.py`。
"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from berth.models import RssSeries
from tests.integration.test_issues_api import CREW, client, factory, open_issue, sign_in

__all__ = ["client", "factory"]


def unbound(client: TestClient, key: str) -> None:
    async def run() -> None:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            session.add(RssSeries(key=key, title_raw="[ANi] Frieren - 29", reasons_json=[]))
            await session.commit()

    asyncio.run(run())


class TestTheWaitingCounts:
    def test_nothing_waiting_is_three_zeros(self, client: TestClient) -> None:
        sign_in(client)

        assert client.get("/api/waiting").json() == {"review": 0, "issue": 0, "rss": 0}

    def test_each_list_is_counted_on_its_own(self, client: TestClient) -> None:
        open_issue(client)
        unbound(client, "mikan:1:2")
        unbound(client, "mikan:1:3")
        sign_in(client)

        assert client.get("/api/waiting").json() == {"review": 0, "issue": 1, "rss": 2}

    def test_an_ordinary_user_is_refused(self, client: TestClient) -> None:
        sign_in(client, CREW)

        assert client.get("/api/waiting").status_code == 403
