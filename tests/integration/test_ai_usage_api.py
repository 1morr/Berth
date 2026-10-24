"""用量頁的端點（M5 票 13）：只有管理員、期間只收 7 / 30 / 90。

數字怎麼算是 `test_ai_usage.py` 的事；這裡只驗門禁、參數與形狀。
"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from berth.domain import AiCallOrigin, ApiFormat
from berth.models import AiCall
from berth.models.types import utcnow
from tests.integration.test_issues_api import CREW, client, factory, sign_in

__all__ = ["client", "factory"]

URL = "/api/settings/ai/usage"


def one_call(client: TestClient) -> None:
    async def run() -> None:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]  # Starlette 的 app 型別是 ASGIApp
        async with sessions() as session:
            session.add(
                AiCall(
                    created_at=utcnow(),
                    format=ApiFormat.ANTHROPIC,
                    host="api.anthropic.com",
                    model="claude-opus-5-5",
                    input_tokens=1000,
                    output_tokens=50,
                    cache_write_tokens=0,
                    cache_read_tokens=None,
                    duration_ms=900,
                    origin=AiCallOrigin.TEST,
                )
            )
            await session.commit()

    asyncio.run(run())


class TestTheUsageEndpoint:
    def test_today_is_the_last_day_of_the_default_thirty(self, client: TestClient) -> None:
        one_call(client)
        sign_in(client)

        body = client.get(URL).json()

        assert body["has_any"] is True
        assert len(body["days"]) == 30
        assert body["days"][-1]["date"] == body["until"]
        assert body["days"][-1]["tally"]["calls"] == 1
        assert body["totals"]["hit_rate"] is None
        assert body["totals"]["cache_unreported"] == 1
        assert body["by_model"] == [
            {
                "format": "anthropic",
                "host": "api.anthropic.com",
                "model": "claude-opus-5-5",
                "tally": body["totals"],
            }
        ]
        assert body["by_user"][0]["user_id"] is None
        assert body["failures"] == []

    def test_only_the_three_periods(self, client: TestClient) -> None:
        sign_in(client)

        assert len(client.get(URL, params={"days": 7}).json()["days"]) == 7
        assert len(client.get(URL, params={"days": 90}).json()["days"]) == 90
        assert client.get(URL, params={"days": 365}).status_code == 422

    def test_an_ordinary_user_is_refused(self, client: TestClient) -> None:
        sign_in(client, CREW)

        assert client.get(URL).status_code == 403
