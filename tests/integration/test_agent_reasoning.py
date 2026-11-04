"""側面板的推理片段（M5.5 票 16，brief §20.26）。

模型回的推理文字（`ThinkingPart`；`deepseek-flash` 不送 `thinking` 也會回）在串流裡是 `reasoning-*`
片段，重新載入時 `GET /agent/conversations/{id}` 也帶出 `reasoning` 那一格，面板兩條路畫同一個形狀。
模型是 `FakeAi` 的腳本（`test_agent_api.Script`），串流照真的服務把推理拆成片段送。
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.messages import ModelResponse, TextPart, ThinkingPart, ToolCallPart

from berth.adapters.ai.fake import FakeAi
from berth.api.deps import get_client_factory
from berth.config import Config
from berth.main import create_app
from tests.integration.arrange import sign_in_owner
from tests.integration.factories import FakeClientFactory
from tests.integration.test_agent_api import Script, Step, chat, say, turn_ai_on
from tests.integration.test_agent_web_search import stream_events


@pytest.fixture
def script() -> Script:
    return Script()


@pytest.fixture
def factory(script: Script) -> FakeClientFactory:
    return FakeClientFactory(ai=FakeAi(script=script))


@pytest.fixture
def client(config: Config, tmp_path: Path, factory: FakeClientFactory) -> Iterator[TestClient]:
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app) as running:
        sign_in_owner(running)
        turn_ai_on(running)
        yield running


THOUGHT = "The user asks why. I should check the job list first."


def thought(then: TextPart | ToolCallPart) -> Step:
    return lambda _messages, _info: ModelResponse(parts=[ThinkingPart(THOUGHT), then])


def reasoning_streamed(body: str) -> str:
    return "".join(
        event["delta"] for event in stream_events(body) if event.get("type") == "reasoning-delta"
    )


def reloaded_parts(client: TestClient) -> list[dict[str, Any]]:
    got = client.get("/api/agent/conversations/c1")
    assert got.status_code == 200, got.text
    return [
        part
        for message in got.json()["messages"]
        if message["role"] == "assistant"
        for part in message["parts"]
    ]


class TestReasoningReachesThePanel:
    def test_the_stream_carries_the_reasoning_before_the_answer(
        self, client: TestClient, script: Script
    ) -> None:
        script.steps = [thought(TextPart("Nothing is stuck."))]

        response = chat(client, "Why is nothing downloading?")

        assert response.status_code == 200, response.text
        assert reasoning_streamed(response.text) == THOUGHT
        kinds = [event["type"] for event in stream_events(response.text)]
        assert kinds.index("reasoning-start") < kinds.index("text-start")

    def test_the_reloaded_conversation_keeps_it(self, client: TestClient, script: Script) -> None:
        script.steps = [thought(TextPart("Nothing is stuck."))]
        chat(client, "Why is nothing downloading?")

        parts = reloaded_parts(client)

        assert [(p["type"], p.get("text")) for p in parts] == [
            ("reasoning", THOUGHT),
            ("text", "Nothing is stuck."),
        ]

    def test_reasoning_before_a_tool_call_is_kept_with_that_step(
        self, client: TestClient, script: Script
    ) -> None:
        script.steps = [thought(ToolCallPart("jobs_list_jobs", {})), say("Nothing is stuck.")]
        chat(client, "Why is nothing downloading?")

        kinds = [p["type"] for p in reloaded_parts(client)]

        assert kinds[0] == "reasoning"
        assert kinds.index("reasoning") < kinds.index("tool-jobs_list_jobs")
        assert kinds[-1] == "text"
