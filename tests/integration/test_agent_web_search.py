"""側面板的網路搜尋（M5 票 17、plan §11.6〈外部資料〉）。

- 接口是 Anthropic Messages 時掛伺服器端的 `web_search`（限次數、限網域）；Chat Completions 沒有。
- 設了 Tavily key 時兩種接口都多一個 Tavily 工具，經登錄表與執行器。
- 次數進 `ai_calls` / `ai_runs`；Anthropic 官方端點每次 $0.01，其他端點的價不知道就不計。

模型是 `FakeAi` 的腳本（`test_agent_api.Script`）：「模型看得到什麼」從它記下的 `AgentInfo` 斷言。
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    NativeToolCallPart,
    NativeToolReturnPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import AgentInfo
from pydantic_ai.native_tools import WebSearchTool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.adapters.ai.fake import FakeAi
from berth.adapters.ai.prices import cost_of
from berth.adapters.ai.usage import TokenUsage
from berth.adapters.http import AuthFailedError
from berth.adapters.websearch import WebPage
from berth.api.deps import get_client_factory
from berth.config import Config
from berth.domain import AiProvider
from berth.main import create_app
from berth.models import AiCall, AiConversation
from berth.services.agent import external_texts, load_history
from berth.services.web import SEARCH_DOMAINS
from tests.integration.arrange import sign_in_owner
from tests.integration.factories import FakeClientFactory
from tests.integration.test_agent_api import (
    BROWSER,
    KEY,
    Script,
    Step,
    call,
    chat,
    limit,
    recorded,
    say,
)

TAVILY_KEY = "tvly-dev-agent-test-key"
#: DeepSeek 的離峰（尖峰是 UTC 01–04、06–10）。
OFF_PEAK = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


class Seen(Script):
    """另外記下每次呼叫看得到的伺服器端工具。"""

    def __init__(self) -> None:
        super().__init__()
        self.native: list[list[WebSearchTool]] = []
        self.instructions: list[str] = []

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        self.native.append(
            [t for t in info.model_request_parameters.native_tools if isinstance(t, WebSearchTool)]
        )
        self.instructions.append(info.instructions or "")
        return super().__call__(messages, info)


@pytest.fixture
def script() -> Seen:
    return Seen()


@pytest.fixture
def factory(script: Seen) -> FakeClientFactory:
    return FakeClientFactory(ai=FakeAi(script=script))


@pytest.fixture
def client(config: Config, tmp_path: Path, factory: FakeClientFactory) -> Iterator[TestClient]:
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app) as running:
        sign_in_owner(running)
        yield running


def turn_ai_on(
    client: TestClient,
    provider: str,
    *,
    base_url: str = "",
    tavily: bool = False,
    model: str | None = None,
) -> None:
    body: dict[str, Any] = {
        "enabled": True,
        "provider": provider,
        "base_url": base_url,
        "model": model or ("claude-sonnet-5-5" if provider == "anthropic" else "deepseek-flash"),
        "api_key": KEY,
    }
    if tavily:
        body["tavily_api_key"] = TAVILY_KEY
    response = client.put("/api/settings/ai", json=body, headers=BROWSER)
    assert response.status_code == 200, response.text


class TestWhichSearchToolsTheModelSees:
    @pytest.mark.parametrize(
        ("provider", "tavily", "native", "function"),
        [
            ("anthropic", False, True, False),
            ("anthropic", True, True, True),
            ("openai", False, False, False),
            ("openai", True, False, True),
        ],
    )
    def test_each_provider_gets_its_search_tools(
        self,
        client: TestClient,
        script: Seen,
        provider: str,
        tavily: bool,
        native: bool,
        function: bool,
    ) -> None:
        turn_ai_on(client, provider, tavily=tavily)
        script.steps = [say("Here you go.")]

        response = chat(client, "Is Frieren season 2 any good?")

        assert response.status_code == 200, response.text
        [seen] = script.native
        assert bool(seen) is native
        assert ("web_tavily_search" in script.tools[0]) is function
        if native:
            [tool] = seen
            assert tool.allowed_domains == list(SEARCH_DOMAINS)
            assert tool.max_uses is not None and tool.max_uses > 0
        # 搜得到網頁的那幾種才叫模型附網址。
        assert ("URL" in script.instructions[0]) is (native or function)


def searched(query: str, *, then: ToolCallPart | None = None) -> Step:
    """伺服器端搜了一次（Anthropic 回的 `server_tool_use` 與 `web_search_tool_result`）。

    之後答完（這一輪結束），或接著叫 `then` 這個工具（這一輪繼續）。
    """
    last: ToolCallPart | TextPart = then or TextPart(f"Reviews are warm ({FRIEREN_URL}).")
    return lambda _messages, _info: ModelResponse(
        parts=[
            NativeToolCallPart("web_search", {"query": query}, tool_call_id="srv-1"),
            NativeToolReturnPart(
                "web_search",
                [{"type": "web_search_result", "title": "Frieren", "url": FRIEREN_URL}],
                tool_call_id="srv-1",
            ),
            last,
        ]
    )


FRIEREN_URL = "https://en.wikipedia.org/wiki/Frieren"


def history(client: TestClient, conversation: str = "c1") -> list[ModelMessage]:
    async def read() -> list[ModelMessage]:
        sessions: async_sessionmaker[AsyncSession] = client.app.state.session_factory  # type: ignore[attr-defined]  # Starlette 的 app 型別是 ASGIApp
        async with sessions() as session:
            row = await session.get_one(AiConversation, conversation)
            return load_history(row.history_json)

    assert client.portal is not None
    found: list[ModelMessage] = client.portal.call(read)
    return found


class TestTheBooks:
    def test_server_side_searches_on_the_official_endpoint_are_counted_and_priced(
        self, client: TestClient, script: Seen
    ) -> None:
        turn_ai_on(client, "anthropic")
        script.steps = [searched("Frieren season 2 reception")]

        chat(client, "Is Frieren season 2 any good?")

        [turn] = recorded(client)
        [call_row] = turn.calls
        assert call_row.web_searches == 1
        assert call_row.web_search_cost_usd == pytest.approx(0.01)
        tokens_only = float(priced(call_row) or 0)
        assert call_row.cost_usd == pytest.approx(tokens_only + 0.01)
        assert turn.run.web_searches == 1
        assert turn.run.cost_usd == pytest.approx(call_row.cost_usd)

    def test_other_endpoints_count_searches_but_leave_their_price_out(
        self, client: TestClient, script: Seen
    ) -> None:
        turn_ai_on(
            client,
            "anthropic",
            base_url="https://api.deepseek.com/anthropic",
            model="deepseek-flash",
        )
        script.steps = [searched("Frieren season 2 reception")]

        chat(client, "Is Frieren season 2 any good?")

        [turn] = recorded(client)
        [call_row] = turn.calls
        assert call_row.web_searches == 1
        # 價錢不知道：這一格是 NULL，估計費用只有 token（不讓整筆變成不知道）。
        assert call_row.web_search_cost_usd is None
        tokens_only = priced(call_row)
        assert tokens_only is not None
        assert call_row.cost_usd == pytest.approx(float(tokens_only))
        assert turn.run.web_searches == 1

    def test_a_call_is_priced_by_the_endpoint_it_went_to(
        self, client: TestClient, script: Seen
    ) -> None:
        # Anthropic 接口打 DeepSeek 的相容端點（M5 票 21b）：記下端點，照 DeepSeek 在回應時的價。
        turn_ai_on(
            client,
            "anthropic",
            base_url="https://api.deepseek.com/anthropic",
            model="deepseek-flash",
        )
        script.steps = [
            lambda _m, _i: ModelResponse(parts=[TextPart("Hello.")], timestamp=OFF_PEAK)
        ]

        chat(client, "Hi")

        [turn] = recorded(client)
        [call_row] = turn.calls
        assert call_row.base_url == "https://api.deepseek.com/anthropic"
        # DeepSeek 離峰：輸入 $0.15、輸出 $0.6（每百萬）。
        expected = (call_row.input_tokens * 0.15 + call_row.output_tokens * 0.6) / 1_000_000
        assert call_row.cost_usd == pytest.approx(expected)

    def test_an_empty_base_url_records_the_official_one(
        self, client: TestClient, script: Seen
    ) -> None:
        turn_ai_on(client, "anthropic")
        script.steps = [say("Hello.")]

        chat(client, "Hi")

        [turn] = recorded(client)
        assert [c.base_url for c in turn.calls] == ["https://api.anthropic.com"]

    def test_a_reply_without_searches_records_zero(self, client: TestClient, script: Seen) -> None:
        turn_ai_on(client, "anthropic")
        script.steps = [say("Hello.")]

        chat(client, "Hi")

        [turn] = recorded(client)
        assert [c.web_searches for c in turn.calls] == [0]
        assert [c.web_search_cost_usd for c in turn.calls] == [0]
        assert turn.run.web_searches == 0


class TestTavily:
    def test_the_tool_searches_the_listed_sites_with_the_stored_key(
        self, client: TestClient, script: Seen, factory: FakeClientFactory
    ) -> None:
        turn_ai_on(client, "openai", tavily=True)
        factory.web_search_.pages = [
            WebPage("Frieren - Wikipedia", FRIEREN_URL, "A fantasy anime. " * 200)
        ]
        script.steps = [
            call("web_tavily_search", query="Frieren season 2 reception"),
            say(f"Reviews are warm ({FRIEREN_URL})."),
        ]

        response = chat(client, "Is Frieren season 2 any good?")

        assert response.status_code == 200, response.text
        [search] = factory.web_search_.searched
        assert search.query == "Frieren season 2 reception"
        assert search.domains == SEARCH_DOMAINS
        assert search.api_key == TAVILY_KEY
        [returned] = tool_returns(script.seen[1])
        result = returned.model_response_object()
        [page] = result["pages"]
        assert page["url"] == FRIEREN_URL
        assert len(page["content"]) <= 1000
        assert "external content" in result["external_content"]
        [turn] = recorded(client)
        assert [(t.command, t.outcome) for t in turn.tools] == [("web.tavily_search", "ok")]

    def test_a_rejected_key_goes_back_to_the_model_without_ending_the_reply(
        self, client: TestClient, script: Seen, factory: FakeClientFactory
    ) -> None:
        turn_ai_on(client, "openai", tavily=True)
        factory.web_search_.error = AuthFailedError(
            "POST /search: 401 Unauthorized: missing or invalid API key."
        )
        script.steps = [call("web_tavily_search", query="Frieren"), say("Search is down.")]

        chat(client, "Is Frieren season 2 any good?")

        [returned] = tool_returns(script.seen[1])
        assert "invalid API key" in str(returned.model_response_object())
        [turn] = recorded(client)
        assert [t.outcome for t in turn.tools] == ["failed"]
        assert turn.run.stop_reason == "completed"


class TestTheSearchLimit:
    def test_tavily_and_server_side_searches_share_one_limit_per_reply(
        self, client: TestClient, script: Seen
    ) -> None:
        turn_ai_on(client, "anthropic", tavily=True)
        limit(client, web_searches=2)
        script.steps = [
            searched("Frieren reception", then=ToolCallPart("jobs_list_jobs", {})),
            call("web_tavily_search", query="Frieren season 2"),
            call("web_tavily_search", query="Frieren season 2 ratings"),
            say("Done."),
        ]

        chat(client, "Is Frieren season 2 any good?")

        # 伺服器端搜 1 次、Tavily 1 次，額度用完：之後的呼叫不掛 `web_search`。`max_uses` 每次一樣
        # （改工具定義會讓整段快取失效）。
        assert [[t.max_uses for t in seen] for seen in script.native] == [[2], [2], [], []]
        [turn] = recorded(client)
        assert [t.outcome for t in turn.tools] == ["ok", "ok", "blocked"]
        blocked = tool_returns(script.seen[3])[-1]
        assert "limit" in str(blocked.model_response_object())


class TestExternalContent:
    def test_what_searches_returned_is_marked_as_external(
        self, client: TestClient, script: Seen
    ) -> None:
        turn_ai_on(client, "anthropic", tavily=True)
        script.steps = [
            searched("Frieren reception", then=ToolCallPart("web_tavily_search", {"query": "x"})),
            say("Done."),
        ]
        chat(client, "Is Frieren season 2 any good?")
        script.steps = [call("jobs_list_jobs"), say("Nothing.")]
        chat(client, "What is downloading?")

        texts = external_texts(history(client))

        # 伺服器端那一份與 Tavily 那一份；`jobs_list_jobs` 的結果不算。
        assert len(texts) == 2
        assert FRIEREN_URL in texts[0]
        assert "external content" in texts[1]


def tool_returns(messages: list[ModelMessage]) -> list[ToolReturnPart]:
    return [
        part
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    ]


def priced(row: AiCall) -> Decimal | None:
    """這一列的 token 照它記下的端點、在它記帳的那一刻算出來的費用（網搜另計）。"""
    usage = TokenUsage(
        row.input_tokens, row.output_tokens, row.cache_read_tokens, row.cache_write_tokens
    )
    return cost_of(
        row.model,
        usage,
        base_url=row.base_url,
        provider=AiProvider.ANTHROPIC,
        at=row.created_at,
    )


def test_a_conversation_with_a_server_side_search_still_reloads(
    client: TestClient, script: Seen
) -> None:
    turn_ai_on(client, "anthropic")
    script.steps = [searched("Frieren season 2 reception")]
    chat(client, "Is Frieren season 2 any good?")

    got = client.get("/api/agent/conversations/c1")

    assert got.status_code == 200, got.text
    parts = [p for m in got.json()["messages"] for p in m["parts"]]
    assert any(FRIEREN_URL in p.get("text", "") for p in parts)


def test_parallel_tavily_calls_cannot_overrun_the_limit(client: TestClient, script: Seen) -> None:
    """同一則回應裡的工具呼叫是並行跑的：額度要在檢查的那一刻就扣，不是等結果回來。"""
    turn_ai_on(client, "openai", tavily=True)
    limit(client, web_searches=1)
    script.steps = [
        lambda _messages, _info: ModelResponse(
            parts=[
                ToolCallPart("web_tavily_search", {"query": "a"}),
                ToolCallPart("web_tavily_search", {"query": "b"}),
            ]
        ),
        say("Done."),
    ]

    chat(client, "Is Frieren season 2 any good?")

    [turn] = recorded(client)
    assert sorted(t.outcome for t in turn.tools) == ["blocked", "ok"]
