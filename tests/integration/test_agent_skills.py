"""側面板的 skills（M5 票 19）：instructions 只帶名稱與描述，模型叫 `skills_load_skill` 拿全文。

模型是 `FakeAi` 的腳本（`test_agent_api.Script`）：模型看到什麼，從它記下的 instructions 與工具結果
斷言。
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolReturnPart
from pydantic_ai.models.function import AgentInfo

from berth.adapters.ai.fake import FakeAi
from berth.api.deps import get_client_factory
from berth.config import Config
from berth.main import create_app
from berth.services.skills import catalog
from tests.integration.arrange import sign_in_crew, sign_in_owner
from tests.integration.factories import FakeClientFactory
from tests.integration.test_agent_api import Script, call, chat, recorded, say, turn_ai_on


class Seen(Script):
    """另外記下每次呼叫的 instructions。"""

    def __init__(self) -> None:
        super().__init__()
        self.instructions: list[str] = []

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.instructions.append(info.instructions or "")
        return super().__call__(messages, info)


@pytest.fixture
def script() -> Seen:
    return Seen()


@pytest.fixture
def client(config: Config, tmp_path: Path, script: Seen) -> Iterator[TestClient]:
    factory = FakeClientFactory(ai=FakeAi(script=script))
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app) as running:
        sign_in_owner(running)
        turn_ai_on(running)
        yield running


def body_of(name: str) -> str:
    return next(skill.body for skill in catalog() if skill.name == name)


def returned(script: Seen, tool: str) -> list[ToolReturnPart]:
    return [
        part
        for messages in script.seen
        for message in messages
        for part in message.parts
        if isinstance(part, ToolReturnPart) and part.tool_name == tool
    ]


class TestProgressiveDisclosure:
    def test_the_instructions_list_names_and_descriptions_but_not_the_steps(
        self, client: TestClient, script: Seen
    ) -> None:
        script.steps = [say("Hi.")]

        chat(client, "Hello")

        [instructions] = script.instructions
        why_not = next(skill for skill in catalog() if skill.name == "why-not-imported")
        assert f"- why-not-imported: {why_not.description}" in instructions
        assert why_not.body not in instructions
        assert "skills_load_skill" in instructions
        # 流程要的工具還沒進側面板（票 13 / 14 / 16）：不列。
        assert "series-mapping" not in instructions

    def test_the_model_loads_a_skill_and_gets_its_whole_body(
        self, client: TestClient, script: Seen
    ) -> None:
        script.steps = [
            call("skills_load_skill", name="why-not-imported"),
            say("Following the steps."),
        ]

        response = chat(client, "Why is Frieren not in my library?")

        assert response.status_code == 200, response.text
        [loaded] = returned(script, "skills_load_skill")
        assert loaded.model_response_object() == {
            "name": "why-not-imported",
            "instructions": body_of("why-not-imported"),
        }
        [turn] = recorded(client)
        assert [(tool.command, tool.outcome) for tool in turn.tools] == [
            ("skills.load_skill", "ok")
        ]

    def test_a_skill_that_is_not_offered_cannot_be_loaded(
        self, client: TestClient, script: Seen
    ) -> None:
        script.steps = [call("skills_load_skill", name="series-mapping"), say("No such skill.")]

        chat(client, "Map all of Re:Zero.")

        [refused] = returned(script, "skills_load_skill")
        assert refused.model_response_object() == {
            "refused": "skill_missing",
            "detail": "series-mapping",
        }
        [turn] = recorded(client)
        assert [(tool.command, tool.outcome) for tool in turn.tools] == [
            ("skills.load_skill", "refused")
        ]

    def test_a_user_gets_the_skills_their_tools_cover(
        self, client: TestClient, script: Seen
    ) -> None:
        sign_in_crew(client)
        script.steps = [call("skills_load_skill", name="why-not-imported"), say("OK.")]

        chat(client, "Why is episode 3 missing?")

        assert "- why-not-imported:" in script.instructions[0]
        assert "skills_load_skill" in script.tools[0]
        [loaded] = returned(script, "skills_load_skill")
        assert loaded.model_response_object()["name"] == "why-not-imported"
