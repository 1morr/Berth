"""助理對話的端點（M5 票 08）：POST 回 SSE、重讀還在、別人的看不到、AI 沒設好的拒絕。

迴圈本身（工具、輪數上限、provider 失敗）是 `test_assistant.py` 的事；這裡驗門禁與線上的形狀。
"""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta

from fastapi.testclient import TestClient

from berth.adapters.ai import ModelTurn, StopReason, TextPart, TurnEnded, Usage
from berth.models.types import utcnow
from tests.integration.factories import FakeClientFactory
from tests.integration.test_ai_settings_api import BROWSER
from tests.integration.test_assistant import calls
from tests.integration.test_issues_api import CREW, client, factory, sign_in
from tests.integration.test_weekly import FRIEREN, imported, works

__all__ = ["client", "factory"]


def says(text: str) -> TurnEnded:
    return TurnEnded(
        stop=StopReason.END, stop_raw="end_turn", reply=ModelTurn((TextPart(text),)), usage=Usage()
    )


def ai_ready(client: TestClient) -> None:
    """管理員存好 AI 設定（官方端點加 key）。之後登入的人照呼叫端的意思。"""
    sign_in(client)
    saved = client.put(
        "/api/settings/ai",
        json={"format": "anthropic", "base_url": "", "model": "", "api_key": "sk-test"},
        headers=BROWSER,
    )
    assert saved.status_code == 200


def chunks(body: str) -> list[dict[str, object]]:
    """SSE 的每一行 `data:`。"""
    return [
        json.loads(line.removeprefix("data:").strip())
        for line in body.splitlines()
        if line.startswith("data:")
    ]


def send(client: TestClient, text: str, conversation: int | None = None) -> list[dict[str, object]]:
    url = (
        "/api/conversations"
        if conversation is None
        else f"/api/conversations/{conversation}/messages"
    )
    response = client.post(url, json={"text": text, "language": "en"}, headers=BROWSER)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    return chunks(response.text)


class TestSendingAMessage:
    def test_the_reply_streams_back_and_is_there_on_reload(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        ai_ready(client)
        factory.ai_.replies = [says("Hello there.")]

        streamed = send(client, "hi")

        cid = streamed[0]["conversation_id"]
        assert streamed == [
            {"type": "start", "conversation_id": cid},
            {"type": "text-delta", "delta": "Hello there."},
            {"type": "finish"},
        ]
        body = client.get(f"/api/conversations/{cid}").json()
        assert body["replying"] is False
        assert [(m["kind"], m["parts"]) for m in body["messages"]] == [
            ("user", [{"type": "user_text", "text": "hi"}]),
            ("model", [{"type": "model_text", "text": "Hello there."}]),
        ]
        assert client.get("/api/conversations").json()[0]["title"] == "hi"

    def test_a_second_message_goes_into_the_same_conversation(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        ai_ready(client)
        factory.ai_.replies = [says("One."), says("Two.")]

        cid = send(client, "first")[0]["conversation_id"]
        assert isinstance(cid, int)
        again = send(client, "second", cid)

        assert again[0] == {"type": "start", "conversation_id": cid}
        assert len(client.get(f"/api/conversations/{cid}").json()["messages"]) == 4

    def test_a_blank_message_is_a_422(self, client: TestClient) -> None:
        ai_ready(client)

        response = client.post(
            "/api/conversations", json={"text": "   ", "language": "en"}, headers=BROWSER
        )

        assert response.status_code == 422
        assert response.json()["detail"]["reason"] == "empty_message"


class TestResultCards:
    """結果卡從工具結果畫（M5 票 09）：串流時那一個 chunk 帶著結果型別與結果，
    重讀時也在存下的那一則裡。"""

    def test_what_came_in_this_week_comes_back_as_a_recent_imports_result(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        ai_ready(client)
        this_week(client)
        factory.ai_.replies = [calls("recent_imports"), says("Frieren got two episodes.")]

        streamed = send(client, "What came in this week?")

        [output] = [chunk for chunk in streamed if chunk["type"] == "tool-output-available"]
        assert (output["tool_name"], output["outcome"], output["result_type"]) == (
            "recent_imports",
            "done",
            "RecentImports",
        )
        assert isinstance(output["result"], dict)
        [work] = output["result"]["works"]
        assert (work["media"], work["episodes"], work["presence"]) == (
            FRIEREN,
            [[1, 1, 2]],
            "lost",
        )
        cid = streamed[0]["conversation_id"]
        body = client.get(f"/api/conversations/{cid}").json()
        stored = [
            part
            for message in body["messages"]
            for part in message["parts"]
            if part["type"] == "tool_result"
        ]
        assert [(part["result_type"], part["result"]) for part in stored] == [
            ("RecentImports", output["result"])
        ]


def this_week(client: TestClient) -> None:
    """芙莉蓮昨天入庫了兩集（反查沒排上，所以 Jellyfin 找不到）。"""

    async def run() -> None:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]  # app.state 是 Starlette 的動態屬性
        async with sessions() as session:
            await works(session)
            for episode in (1, 2):
                await imported(session, FRIEREN, episode, at=utcnow() - timedelta(days=1))

    asyncio.run(run())


class TestNotSetUp:
    def test_nothing_is_sent_and_the_status_says_why(self, client: TestClient) -> None:
        sign_in(client, CREW)

        assert client.get("/api/assistant").json() == {"ready": False, "chat_only": False}
        response = client.post(
            "/api/conversations", json={"text": "hi", "language": "en"}, headers=BROWSER
        )
        assert response.status_code == 409
        assert response.json()["detail"]["reason"] == "not_ready"

    def test_an_ordinary_user_sees_the_status_too(self, client: TestClient) -> None:
        ai_ready(client)
        sign_in(client, CREW)

        assert client.get("/api/assistant").json()["ready"] is True


class TestEachPersonsOwn:
    def test_someone_elses_conversation_is_not_listed_read_or_streamed(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        ai_ready(client)
        factory.ai_.replies = [says("Noted."), says("Hi.")]
        mine = send(client, "admin only")[0]["conversation_id"]

        sign_in(client, CREW)
        theirs = send(client, "hello")[0]["conversation_id"]

        listed = client.get("/api/conversations").json()
        assert [row["id"] for row in listed] == [theirs]
        assert client.get(f"/api/conversations/{mine}").status_code == 404
        refused = client.post(
            f"/api/conversations/{mine}/messages",
            json={"text": "me too", "language": "en"},
            headers=BROWSER,
        )
        assert refused.status_code == 404
        assert refused.json()["detail"]["reason"] == "conversation_missing"

    def test_signed_out_gets_nothing(self, client: TestClient) -> None:
        assert client.get("/api/conversations").status_code == 401
        assert client.get("/api/assistant").status_code == 401
