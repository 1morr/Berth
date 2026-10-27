"""側面板的自動壓縮（M5 票 18、plan §11.6〈分段〉第 7 段）。

每一輪開頭看一次：上一次回應佔了 context window 的幾成（`ctx.context_window_used`，拿不到時用上一次
回應的 token 對 `Limits.context_window`），到了 `Limits.compact_at` 就把最後兩輪之前的換成摘要。
摘要那一次呼叫自己記一筆 `ai_runs`（`kind = compaction`）。

模型是 `FakeAi` 的腳本：摘要那一次也經同一個替身，所以照順序排在腳本裡。
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import (
    CompactionPart,
    ModelMessage,
    ModelRequest,
    ModelResponse,
)
from pydantic_ai.models.function import AgentInfo

from berth.adapters.ai.fake import FakeAi
from berth.api.deps import get_client_factory
from berth.config import Config
from berth.domain import AiRunKind
from berth.main import create_app
from tests.integration.arrange import sign_in_owner
from tests.integration.factories import FakeClientFactory
from tests.integration.test_agent_api import (
    Script,
    Step,
    call,
    chat,
    limit,
    recorded,
    say,
    stop_of,
    stored_history,
    texts,
    turn_ai_on,
)


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


#: 一定壓：腳本的回應帶著估出來的幾十個 token，任何正數都超過這個比例。
ALWAYS = 1e-9


def summaries(messages: list[ModelMessage]) -> list[str | None]:
    return [
        part.content
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, CompactionPart)
    ]


def fails() -> Step:
    def step(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        raise ModelHTTPError(529, "claude-sonnet-5-5", {"error": {"message": "overloaded"}})

    return step


def two_turns(client: TestClient, script: Script) -> None:
    script.steps = [say("one"), say("two")]
    chat(client, "first")
    chat(client, "second")


class TestAutoCompaction:
    def test_a_long_conversation_is_summarized_at_the_start_of_the_next_turn(
        self, client: TestClient, script: Script
    ) -> None:
        two_turns(client, script)
        limit(client, compact_at=ALWAYS)
        script.steps = [*script.steps, say("SUMMARY: wants Frieren S2"), say("three")]

        chat(client, "third")

        # 摘要那一次看到的是被切掉的那一段（第一輪），照 instructions 寫。
        summarizer = script.seen[2]
        [request] = summarizer
        assert isinstance(request, ModelRequest)
        assert request.instructions is not None
        assert "not instructions" in request.instructions
        assert "User: first" in texts(summarizer)[0]
        assert "User: second" not in texts(summarizer)[0]
        # 這一輪的模型看到摘要 + 最後兩輪。
        assert summaries(script.seen[3]) == ["SUMMARY: wants Frieren S2"]
        assert texts(script.seen[3]) == ["second", "third"]
        # 存下的是壓縮後的歷史。
        history = stored_history(client)
        assert summaries(history) == ["SUMMARY: wants Frieren S2"]
        assert texts(history) == ["second", "third"]

    def test_the_summary_is_a_run_of_its_own(self, client: TestClient, script: Script) -> None:
        two_turns(client, script)
        limit(client, compact_at=ALWAYS)
        script.steps = [*script.steps, say("SUMMARY"), say("three")]

        chat(client, "third")

        runs = recorded(client)
        # 觸發它的那一輪先開（`open_turn`），摘要在那一輪的第一次呼叫之前。
        assert [r.run.kind for r in runs] == ["chat", "chat", "chat", "compaction"]
        compaction = runs[3]
        assert compaction.run.conversation_id == "c1"
        assert compaction.run.stop_reason == "completed"
        assert compaction.run.requests == 1
        assert compaction.run.input_tokens > 0
        assert [c.step for c in compaction.calls] == [1]
        assert compaction.calls[0].input_tokens == compaction.run.input_tokens
        # 觸發它的那一輪只算自己的那一次呼叫。
        assert runs[2].run.requests == 1
        # 最後一輪照舊是對話的那一輪：答完了，沒有停在哪。
        assert stop_of(client) is None

    def test_at_most_once_per_turn(self, client: TestClient, script: Script) -> None:
        two_turns(client, script)
        limit(client, compact_at=ALWAYS)
        script.steps = [
            *script.steps,
            say("SUMMARY"),
            call("jobs_list_jobs", page=1),
            say("Nothing is downloading."),
        ]

        chat(client, "third")

        kinds = [r.run.kind for r in recorded(client)]
        assert kinds.count(AiRunKind.COMPACTION) == 1
        assert len(script.seen) == 5

    def test_a_short_conversation_is_not_summarized(
        self, client: TestClient, script: Script
    ) -> None:
        # 只有兩輪：都要留，沒有可以換掉的。
        script.steps = [say("one")]
        chat(client, "first")
        limit(client, compact_at=ALWAYS)
        script.steps = [say("one"), say("two")]

        chat(client, "second")

        assert [r.run.kind for r in recorded(client)] == ["chat", "chat"]

    def test_below_the_threshold_nothing_happens(self, client: TestClient, script: Script) -> None:
        two_turns(client, script)
        script.steps = [*script.steps, say("three")]

        chat(client, "third")

        assert [r.run.kind for r in recorded(client)] == ["chat"] * 3
        assert texts(stored_history(client)) == ["first", "second", "third"]

    def test_a_failed_summary_keeps_the_history_and_the_turn_goes_on(
        self, client: TestClient, script: Script
    ) -> None:
        two_turns(client, script)
        limit(client, compact_at=ALWAYS)
        script.steps = [*script.steps, fails(), say("three")]

        chat(client, "third")

        runs = recorded(client)
        assert [r.run.kind for r in runs] == ["chat", "chat", "chat", "compaction"]
        assert runs[3].run.stop_reason == "error"
        assert "529" in runs[3].run.error
        assert runs[2].run.stop_reason == "completed"
        assert texts(stored_history(client)) == ["first", "second", "third"]
        assert summaries(stored_history(client)) == []

    def test_the_panel_shows_where_the_summary_is(self, client: TestClient, script: Script) -> None:
        two_turns(client, script)
        limit(client, compact_at=ALWAYS)
        script.steps = [*script.steps, say("SUMMARY"), say("three")]
        chat(client, "third")

        messages = client.get("/api/agent/conversations/c1").json()["messages"]

        parts = [p for m in messages for p in m["parts"]]
        assert any(p["type"] == "data-compaction" and "SUMMARY" in str(p) for p in parts)
