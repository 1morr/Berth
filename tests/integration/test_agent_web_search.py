"""側面板的網路搜尋（M5 票 17、plan §11.6〈外部資料〉）。

- 接口是 Anthropic Messages 時掛伺服器端的 `web_search`（限次數、限網域）；Chat Completions 沒有。
- 設了 Tavily key 時兩種接口都多一個 Tavily 工具，經登錄表與執行器。
- 次數進 `ai_calls` / `ai_runs`；Anthropic 官方端點每次 $0.01，其他端點的價不知道就不計。

模型是 `FakeAi` 的腳本（`test_agent_api.Script`）：「模型看得到什麼」從它記下的 `AgentInfo` 斷言。
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from time_machine import TimeMachineFixture

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
from berth.services.agent import load_history
from berth.services.agent_origins import external_texts
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
from tests.integration.test_agent_slash import in_portal

TAVILY_KEY = "tvly-dev-agent-test-key"
#: DeepSeek 的尖峰是平日 UTC 01–04、06–10（brief §20.24），價錢是離峰的兩倍。2026-10-28 是週三。
PEAK = datetime(2026, 10, 28, 2, 42, tzinfo=UTC)
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
        # 伺服器端的網頁只多送一次（票 23d），所以叫模型搜完就寫下來；Tavily 的結果一直在。
        assert ("write down what you need" in script.instructions[0]) is native


def search_status(client: TestClient) -> dict[str, bool]:
    response = client.post(
        "/api/agent/conversations/c1/commands", json={"text": "/status"}, headers=BROWSER
    )
    assert response.status_code == 200, response.text
    body = response.json()
    return {"web_search": body["web_search"], "tavily": body["tavily"]}


def sent_tools(client: TestClient) -> list[list[str] | None]:
    """最後一輪每次模型呼叫送出的工具名，從步驟頁的端點讀。"""
    run_id = recorded(client)[-1].run.id
    steps = client.get(f"/api/agent/runs/{run_id}").json()["steps"]
    return [step["call"]["tools"] for step in steps]


class TestTheSearchToolsRightNow:
    """M5.5 票 15：正式環境的模型在 Tavily key 存回之後仍說沒有搜尋工具。`/status` 由程式直接說
    這一刻搜得到什麼；每次模型呼叫記下送出的工具名，事後查得到。"""

    def test_clearing_and_refilling_the_tavily_key_shows_at_once(
        self, client: TestClient, script: Seen
    ) -> None:
        turn_ai_on(client, "openai", tavily=True)
        assert search_status(client) == {"web_search": False, "tavily": True}

        forgotten = client.delete("/api/settings/ai/keys/tavily", headers=BROWSER)
        assert forgotten.status_code == 200, forgotten.text
        assert search_status(client) == {"web_search": False, "tavily": False}
        script.steps = [say("No search tools.")]
        chat(client, "Can you search the web?")
        [without] = sent_tools(client)
        assert without is not None and "web_tavily_search" not in without

        turn_ai_on(client, "openai", tavily=True)
        assert search_status(client) == {"web_search": False, "tavily": True}
        chat(client, "Now?")
        [with_key] = sent_tools(client)
        assert with_key is not None and "web_tavily_search" in with_key
        # 送出的就是模型看得到的那一份。
        assert sorted(with_key) == script.tools[-1]

    def test_the_server_side_search_is_listed_on_the_anthropic_interface(
        self, client: TestClient, script: Seen
    ) -> None:
        turn_ai_on(client, "anthropic")
        assert search_status(client) == {"web_search": True, "tavily": False}
        script.steps = [say("Here you go.")]

        chat(client, "Is Frieren season 2 any good?")

        [tools] = sent_tools(client)
        assert tools is not None and "web_search" in tools
        assert "web_tavily_search" not in tools

    def test_the_instructions_say_the_tools_can_change_between_messages(
        self, client: TestClient, script: Seen
    ) -> None:
        turn_ai_on(client, "openai")
        script.steps = [say("Hi.")]

        chat(client, "Hello?")

        assert "only the tools you have now" in script.instructions[0]

    def test_calls_from_before_ticket_15_say_nothing_was_recorded(
        self, client: TestClient, script: Seen
    ) -> None:
        turn_ai_on(client, "openai")
        script.steps = [say("Hi.")]
        chat(client, "Hello?")

        async def forget(session: AsyncSession) -> None:
            for row in (await session.scalars(select(AiCall))).all():
                row.tools_json = None
            await session.commit()

        in_portal(client, forget)

        assert sent_tools(client) == [None]


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
                [
                    {
                        "type": "web_search_result",
                        "title": "Frieren",
                        "url": FRIEREN_URL,
                        "page_age": "October 3, 2026",
                        "encrypted_content": SEALED,
                    }
                ],
                tool_call_id="srv-1",
            ),
            last,
        ]
    )


FRIEREN_URL = "https://en.wikipedia.org/wiki/Frieren"
#: Anthropic 每筆結果帶的不透明內容（給服務端重播用，實際一筆數千字）。
SEALED = "EqgfCioIBhgCIiQ3YTk2LWZmMmUtNDQ0ZC05ZTQ4LTI2ZDYzYzUwYTQ3MQ"


def history(client: TestClient, conversation: str = "c1") -> list[ModelMessage]:
    async def read() -> list[ModelMessage]:
        sessions: async_sessionmaker[AsyncSession] = client.app.state.session_factory  # type: ignore[attr-defined]  # Starlette 的 app 型別是 ASGIApp
        async with sessions() as session:
            row = await session.get_one(AiConversation, conversation)
            return load_history(row.history_json)

    assert client.portal is not None
    found: list[ModelMessage] = client.portal.call(read)
    return found


def turn_deepseek_on(client: TestClient) -> None:
    """Anthropic 接口打 DeepSeek 的相容端點：價錢分尖峰離峰。"""
    turn_ai_on(
        client, "anthropic", base_url="https://api.deepseek.com/anthropic", model="deepseek-flash"
    )


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
        self, client: TestClient, script: Seen, time_machine: TimeMachineFixture
    ) -> None:
        # `priced` 照記帳那一刻重算、記帳照回應那一刻：DeepSeek 分時段，跨過邊界兩邊會不一樣。
        time_machine.move_to(PEAK)
        turn_deepseek_on(client)
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
        self, client: TestClient, script: Seen, time_machine: TimeMachineFixture
    ) -> None:
        # Anthropic 接口打 DeepSeek 的相容端點（M5 票 21b）：記下端點，照 DeepSeek 在回應時的價。
        # 串流回應的時間是收到的那一刻，腳本控制不了，所以釘時鐘（票 21c）。
        time_machine.move_to(OFF_PEAK)
        turn_deepseek_on(client)
        script.steps = [say("Hello.")]

        chat(client, "Hi")

        [turn] = recorded(client)
        [call_row] = turn.calls
        assert call_row.base_url == "https://api.deepseek.com/anthropic"
        # DeepSeek 離峰：輸入 $0.15、輸出 $0.6（每百萬）。
        expected = (call_row.input_tokens * 0.15 + call_row.output_tokens * 0.6) / 1_000_000
        assert call_row.cost_usd == pytest.approx(expected)

    @pytest.mark.parametrize(
        ("now", "input_usd", "output_usd"),
        [pytest.param(PEAK, 0.3, 1.2, id="peak"), pytest.param(OFF_PEAK, 0.15, 0.6, id="off-peak")],
    )
    def test_a_call_is_priced_at_the_hour_it_was_answered(
        self,
        client: TestClient,
        script: Seen,
        time_machine: TimeMachineFixture,
        now: datetime,
        input_usd: float,
        output_usd: float,
    ) -> None:
        # 時段照回應的時間，也就是收到的那一刻（pydantic-ai 的串流回應一律用本機時鐘，票 21c）。
        time_machine.move_to(now)
        turn_deepseek_on(client)
        script.steps = [say("Hello.")]

        chat(client, "Hi")

        [turn] = recorded(client)
        [call_row] = turn.calls
        expected = (
            call_row.input_tokens * input_usd + call_row.output_tokens * output_usd
        ) / 1_000_000
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
        # 記下的工具名跟著同一份（M5.5 票 15）：額度用完那幾次沒有 `web_search`。
        assert [("web_search" in (tools or [])) for tools in sent_tools(client)] == [
            True,
            True,
            False,
            False,
        ]
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


def native_parts(messages: list[ModelMessage]) -> list[object]:
    return [
        part
        for message in messages
        for part in message.parts
        if isinstance(part, NativeToolCallPart | NativeToolReturnPart)
    ]


class TestEarlierSearchesLeaveTheContext:
    """票 23d：伺服器端 `web_search` 的結果（Anthropic 回的是整頁加密內容）每次呼叫都重送，長系列
    在找種子那一輪撞過每輪 input 上限。下一輪起送給模型的歷史拿掉它，存著的歷史不動。"""

    def test_the_next_reply_does_not_resend_earlier_search_results(
        self, client: TestClient, script: Seen
    ) -> None:
        turn_ai_on(client, "anthropic")
        script.steps = [
            searched("Re:Zero list of episodes", then=ToolCallPart("jobs_list_jobs", {})),
            say("Season 1 is 25 episodes."),
            call("jobs_list_jobs"),
            say("Nothing is downloading."),
        ]
        chat(client, "How do the seasons of Re:Zero line up?")
        chat(client, "What is downloading?")

        _, later_in_it, next_reply, later_in_next = script.seen
        # 同一輪裡照留：模型還在讀那幾頁。
        assert native_parts(later_in_it)
        # 下一輪起不送；那一輪寫下的結論還在。
        for seen in (next_reply, later_in_next):
            assert not native_parts(seen)
            assert any(
                isinstance(part, TextPart) and "25 episodes" in part.content
                for message in seen
                for part in message.parts
            )
        # 存著的歷史不動：「出自外部來源」照樣認得那一輪讀過的網頁。
        assert native_parts(history(client))
        assert any(FRIEREN_URL in text for text in external_texts(history(client)))

    def test_within_a_reply_the_pages_are_sent_once_more_and_then_dropped(
        self, client: TestClient, script: Seen
    ) -> None:
        """2026-10-28 實跑：Re:Zero 列清單那一輪搜了兩次（約 21 萬 token），之後每次呼叫都重送，
        一輪 457K。搜完的下一次呼叫照送（模型接著寫清單），再下一次起不送。"""
        turn_ai_on(client, "anthropic")
        script.steps = [
            searched("Re:Zero list of episodes", then=ToolCallPart("jobs_list_jobs", {})),
            call("jobs_list_jobs", limit=5),
            call("jobs_list_jobs", limit=6),
            say("Season 1 is 25 episodes."),
        ]
        chat(client, "How do the seasons of Re:Zero line up?")

        _, right_after, then, last = script.seen
        assert native_parts(right_after)
        assert not native_parts(then)
        assert not native_parts(last)
        assert native_parts(history(client))


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


class TestTheBrowserGetsNoSealedContent:
    """M5.5 票 03：`encrypted_content` 只給服務端重播，不送到瀏覽器；標題、網址、日期照給。"""

    def test_the_stream_leaves_it_out(self, client: TestClient, script: Seen) -> None:
        turn_ai_on(client, "anthropic")
        script.steps = [searched("Frieren season 2 reception")]

        response = chat(client, "Is Frieren season 2 any good?")

        assert response.status_code == 200, response.text
        assert SEALED not in response.text
        assert "encrypted_content" not in response.text
        [output] = [
            event["output"]
            for event in stream_events(response.text)
            if event.get("type") == "tool-output-available"
        ]
        assert output == [
            {
                "type": "web_search_result",
                "title": "Frieren",
                "url": FRIEREN_URL,
                "page_age": "October 3, 2026",
            }
        ]

    def test_a_reconnected_stream_leaves_it_out(self, client: TestClient, script: Seen) -> None:
        """重連（`resumeStream`）重播的是 `_relay` 送出的同一串片段。"""
        turn_ai_on(client, "anthropic")
        script.steps = [searched("Frieren season 2 reception")]
        chat(client, "Is Frieren season 2 any good?")
        [turn] = recorded(client)

        followed = client.get(f"/api/agent/conversations/c1/stream?turn={turn.run.id}")

        assert followed.status_code == 200, followed.text
        assert FRIEREN_URL in followed.text
        assert SEALED not in followed.text

    def test_the_reloaded_conversation_leaves_it_out(
        self, client: TestClient, script: Seen
    ) -> None:
        turn_ai_on(client, "anthropic")
        script.steps = [searched("Frieren season 2 reception")]
        chat(client, "Is Frieren season 2 any good?")

        got = client.get("/api/agent/conversations/c1")

        assert got.status_code == 200, got.text
        assert SEALED not in got.text
        [search] = [
            part
            for message in got.json()["messages"]
            for part in message["parts"]
            if part["type"] == "tool-web_search"
        ]
        assert search["output"] == [
            {
                "type": "web_search_result",
                "title": "Frieren",
                "url": FRIEREN_URL,
                "page_age": "October 3, 2026",
            }
        ]

    def test_the_model_still_gets_it_back(self, client: TestClient, script: Seen) -> None:
        """模型重播靠伺服器存的歷史：存著的照留，搜完的下一次呼叫照送（之後的送不送是票 23d）。"""
        turn_ai_on(client, "anthropic")
        script.steps = [
            searched("Frieren season 2 reception", then=ToolCallPart("jobs_list_jobs", {})),
            say("Reviews are warm."),
        ]

        chat(client, "Is Frieren season 2 any good?")

        _, right_after = script.seen
        for messages in (right_after, history(client)):
            [returned] = [p for p in native_parts(messages) if isinstance(p, NativeToolReturnPart)]
            assert [
                result["encrypted_content"] for result in cast(list[Any], returned.content)
            ] == [SEALED]


def stream_events(body: str) -> list[dict[str, Any]]:
    """UI message stream（SSE）的每一個 JSON 事件。"""
    return [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: {")
    ]


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
