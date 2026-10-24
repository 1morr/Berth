"""用量頁的端點（M5 票 13）：只有管理員、期間只收 7 / 30 / 90。

數字怎麼算是 `test_ai_usage.py` 的事；這裡驗門禁、參數與形狀，以及側面板的對話叫了模型之後，
用量頁看得到那幾次的 tokens 與快取命中率（plan §11.6 驗收，M5 票 16）。
"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from berth.adapters.ai import ModelTurn, StopReason, TextPart, TurnEnded, Usage
from berth.domain import AiCallOrigin, ApiFormat
from berth.models import AiCall
from berth.models.types import utcnow
from tests.integration.factories import FakeClientFactory
from tests.integration.test_conversations_api import ai_ready, send
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


def says(text: str, usage: Usage) -> TurnEnded:
    return TurnEnded(
        stop=StopReason.END, stop_raw="end_turn", reply=ModelTurn((TextPart(text),)), usage=usage
    )


class TestAConversationShowsUp:
    def test_each_reply_counts_its_tokens_and_the_cache_it_hit(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        ai_ready(client)
        factory.ai_.replies = [
            # 第一句寫進快取，第二句讀到它。
            says(
                "Hi.",
                Usage(
                    input_tokens=1000, output_tokens=20, cache_write_tokens=900, cache_read_tokens=0
                ),
            ),
            says(
                "Sure.",
                Usage(
                    input_tokens=1100, output_tokens=30, cache_write_tokens=0, cache_read_tokens=900
                ),
            ),
        ]

        cid = send(client, "hi")[0]["conversation_id"]
        send(client, "and again", int(str(cid)))
        body = client.get(URL, params={"days": 7}).json()

        conversation = {
            "calls": 2,
            "failed": 0,
            "input_tokens": 2100,
            "output_tokens": 50,
            "cache_write_tokens": 900,
            "cache_read_tokens": 900,
            "hit_rate": 900 / 2100,
            "cache_unreported": 0,
        }
        assert body["by_origin"] == [{"origin": "conversation", "tally": conversation}]
        assert body["totals"] == conversation
        assert body["days"][-1]["tally"] == conversation
        assert [row["tally"] for row in body["by_user"]] == [conversation]
