"""設定頁的 AI 一格（M5 票 07）：存 base URL、key 與模型，按測試打一次假端點（respx）。

測試走真的 Anthropic adapter：`AiFactory` 只把 `ai()` 換回正式的那一份，其餘服務照舊是替身
（背景迴圈不會去連網路）。

**key 只進不出**：每一個回應與這期間的每一行 log 都不可以帶著它（同 `test_notify_api.py`）。
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.adapters.ai import ChatProvider, Endpoint
from berth.api.deps import get_client_factory
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.logs import configure_logging, json_line
from berth.main import create_app
from berth.models import AiCall
from berth.services.clients import HttpServiceClientFactory
from tests.integration.arrange import sign_in_owner
from tests.integration.factories import FakeClientFactory

BROWSER = {CSRF_HEADER: "XMLHttpRequest"}
BASE = "/api/settings/ai"
KEY = "sk-ant-api03-do-not-leak-0123456789"
OFFICIAL = "https://api.anthropic.com/v1/messages"
#: Berth 寫出去的等級：`configure_logging` 的預設值，讀它而不是抄一份。
LOGGED: int = inspect.signature(configure_logging).parameters["level"].default


class AiFactory(FakeClientFactory):
    def ai(self, endpoint: Endpoint) -> ChatProvider:
        return HttpServiceClientFactory().ai(endpoint)


@pytest.fixture
def client(config: Config, tmp_path: Path) -> Iterator[TestClient]:
    factory = AiFactory()
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app) as running:
        sign_in_owner(running)
        yield running


def calls_in(client: TestClient) -> list[AiCall]:
    async def read() -> list[AiCall]:
        sessions: async_sessionmaker[AsyncSession] = client.app.state.session_factory  # type: ignore[attr-defined]  # Starlette 的 app 型別是 ASGIApp
        async with sessions() as session:
            return list((await session.scalars(select(AiCall).order_by(AiCall.id))).all())

    assert client.portal is not None
    rows: list[AiCall] = client.portal.call(read)
    return rows


def save(client: TestClient, **fields: Any) -> httpx.Response:
    body = {"format": "anthropic", "base_url": "", "model": "", "api_key": KEY, **fields}
    response: httpx.Response = client.put(BASE, json=body, headers=BROWSER)
    return response


def run_test(client: TestClient) -> httpx.Response:
    response: httpx.Response = client.post(f"{BASE}/test", headers=BROWSER)
    return response


# ---- 假端點 -------------------------------------------------------------------------------------


def sse(*events: dict[str, Any]) -> httpx.Response:
    text = "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events)
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=text.encode())


def start(**usage: int) -> dict[str, Any]:
    return {
        "type": "message_start",
        "message": {
            "id": "msg",
            "role": "assistant",
            "content": [],
            "usage": {"input_tokens": 20, "output_tokens": 1, **usage},
        },
    }


def text_reply(text: str, **usage: int) -> httpx.Response:
    return sse(
        start(**usage),
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}},
        {"type": "content_block_stop", "index": 0},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn"},
            "usage": {"output_tokens": 3},
        },
        {"type": "message_stop"},
    )


def tool_reply(name: str, arguments: str) -> httpx.Response:
    return sse(
        start(),
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "tool_use", "id": "toolu_1", "name": name, "input": {}},
        },
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "input_json_delta", "partial_json": arguments},
        },
        {"type": "content_block_stop", "index": 0},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "tool_use"},
            "usage": {"output_tokens": 8},
        },
        {"type": "message_stop"},
    )


def nonce_of(request: httpx.Request) -> str:
    """探針第二次的使用者訊息裡那個 nonce（引號裡的那一段）。"""
    text: str = json.loads(request.content)["messages"][0]["content"][0]["text"]
    return text.split('"')[1]


Step = Callable[[httpx.Request], httpx.Response]


def endpoint(hello: Step, call: Step, after: Step) -> Callable[[httpx.Request], httpx.Response]:
    """依請求的形狀分派：不帶工具的是第一次，帶工具、最後一則是工具結果的是第三次。"""

    def answer(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if "tools" not in body:
            return hello(request)
        last = body["messages"][-1]["content"][0]
        if last["type"] == "tool_result":
            return after(request)
        return call(request)

    return answer


def calls_echo(request: httpx.Request) -> httpx.Response:
    return tool_reply("berth_echo", json.dumps({"nonce": nonce_of(request)}))


def says(text: str) -> Step:
    return lambda _: text_reply(text)


WORKS = endpoint(says("ok"), calls_echo, says("Got it."))


# ---- 測試 ---------------------------------------------------------------------------------------


def test_nothing_is_set_up_by_default(client: TestClient) -> None:
    """沒設 key 時 AI 就是沒設定：官方端點有預設模型，但沒有 key 還是不算好。"""
    view = client.get(BASE).json()

    assert view["ready"] is False
    assert view["api_key_present"] is False
    assert view["default_model"] == "claude-opus-5-5"
    assert view["tool_test"] is None


def test_saving_keeps_the_key_out_of_every_answer(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(LOGGED)

    saved = save(client)
    read = client.get(BASE)

    assert saved.status_code == 200
    assert read.json()["api_key_present"] is True
    assert read.json()["ready"] is True
    assert KEY not in saved.text + read.text
    assert not [line for line in map(json_line, caplog.records) if KEY in line]


def test_leaving_the_key_out_keeps_it_and_an_empty_one_clears_it(client: TestClient) -> None:
    save(client)

    kept = client.put(
        BASE, json={"format": "anthropic", "base_url": "", "model": ""}, headers=BROWSER
    ).json()
    cleared = save(client, api_key="").json()

    assert kept["api_key_present"] is True
    assert cleared["api_key_present"] is False


def test_a_self_hosted_endpoint_without_a_key_is_ready_once_a_model_is_named(
    client: TestClient,
) -> None:
    """自架的 Ollama / vLLM 不需要 key（研究最後一節第 6 條），但第三方沒有預設模型。"""
    no_model = save(client, base_url="http://ollama.lan:11434", api_key="").json()
    named = save(client, base_url="http://ollama.lan:11434", api_key="", model="qwen3").json()

    assert no_model["ready"] is False
    assert no_model["default_model"] is None
    assert named["ready"] is True


def test_a_base_url_that_is_not_http_is_refused(client: TestClient) -> None:
    response = save(client, base_url="api.anthropic.com")

    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "base_url_invalid"


def test_testing_before_anything_is_set_is_refused(client: TestClient) -> None:
    response = run_test(client)

    assert response.status_code == 409
    assert response.json()["detail"]["reason"] == "not_ready"


@respx.mock
def test_a_working_endpoint_answers_calls_the_tool_and_logs_every_call(
    client: TestClient,
) -> None:
    respx.post(OFFICIAL).mock(side_effect=WORKS)
    save(client)

    result = run_test(client).json()

    assert result["failure"] is None
    assert result["reply"] == "ok"
    assert result["tools"]["supported"] is True
    assert [call["step"] for call in result["calls"]] == ["hello", "tool_call", "tool_result"]
    assert result["calls"][0]["usage"] == {
        "input_tokens": 20,
        "output_tokens": 3,
        "cache_write_tokens": None,
        "cache_read_tokens": None,
    }
    assert client.get(BASE).json()["tool_test"]["supported"] is True

    rows = calls_in(client)
    assert len(rows) == 3
    first = rows[0]
    assert (first.format, first.host, first.model) == (
        "anthropic",
        "api.anthropic.com",
        "claude-opus-5-5",
    )
    assert (first.input_tokens, first.output_tokens) == (20, 3)
    # 假端點沒回快取欄位：那是「不知道」，不是 0。
    assert (first.cache_write_tokens, first.cache_read_tokens) == (None, None)
    assert first.origin == "test"
    assert first.user_id is not None
    assert first.duration_ms >= 0
    assert first.failure is None


@respx.mock
def test_cache_fields_the_endpoint_returns_are_recorded(client: TestClient) -> None:
    respx.post(OFFICIAL).mock(
        side_effect=endpoint(
            lambda _: text_reply("ok", cache_creation_input_tokens=0, cache_read_input_tokens=5),
            calls_echo,
            says("done"),
        )
    )
    save(client)

    run_test(client)

    first = calls_in(client)[0]
    assert (first.input_tokens, first.cache_write_tokens, first.cache_read_tokens) == (25, 0, 5)


@respx.mock
def test_the_request_goes_to_the_base_url_that_was_saved(client: TestClient) -> None:
    custom = respx.post("https://openrouter.ai/api/v1/messages").mock(side_effect=WORKS)
    save(client, base_url="https://openrouter.ai/api", model="anthropic/claude-opus-5.5")

    result = run_test(client).json()

    assert result["failure"] is None
    assert custom.call_count == 3
    # 官方端點沒掛 route：真的打過去的話 respx 會直接報錯。
    assert json.loads(custom.calls[0].request.content)["model"] == "anthropic/claude-opus-5.5"
    assert {row.host for row in calls_in(client)} == {"openrouter.ai"}


@pytest.mark.parametrize(
    ("call", "gap"),
    [
        (says("Sure, I would call it now."), "tools_ignored"),
        (
            lambda r: text_reply(f'<tool_call>berth_echo {{"nonce": "{nonce_of(r)}"}}</tool_call>'),
            "written_as_text",
        ),
        (lambda _: tool_reply("berth_echo", '{"nonce": "wrong"}'), "wrong_call"),
        (
            lambda _: httpx.Response(
                400,
                json={
                    "type": "error",
                    "error": {
                        "type": "invalid_request_error",
                        "message": "model does not support tools",
                    },
                },
            ),
            "tools_rejected",
        ),
    ],
)
@respx.mock
def test_an_endpoint_that_does_not_call_the_tool_is_chat_only(
    client: TestClient, call: Step, gap: str
) -> None:
    respx.post(OFFICIAL).mock(side_effect=endpoint(says("ok"), call, says("done")))
    save(client)

    result = run_test(client).json()

    assert result["failure"] is None
    assert result["tools"]["supported"] is False
    assert result["tools"]["gap"] == gap
    stored = client.get(BASE).json()["tool_test"]
    assert stored["supported"] is False
    assert stored["gap"] == gap


@respx.mock
def test_a_tool_result_the_endpoint_rejects_is_chat_only(client: TestClient) -> None:
    rejected = httpx.Response(
        400,
        json={
            "type": "error",
            "error": {"type": "invalid_request_error", "message": "bad tool_result"},
        },
    )
    respx.post(OFFICIAL).mock(side_effect=endpoint(says("ok"), calls_echo, lambda _: rejected))
    save(client)

    result = run_test(client).json()

    assert result["tools"] == {
        "supported": False,
        "gap": "result_rejected",
        "detail": "400 invalid_request_error: bad tool_result",
        "tested_at": result["tools"]["tested_at"],
    }


@respx.mock
def test_changing_the_model_or_the_address_needs_a_new_test(client: TestClient) -> None:
    respx.post(OFFICIAL).mock(side_effect=endpoint(says("ok"), says("no tools here"), says("-")))
    save(client)
    run_test(client)

    same = save(client).json()
    other_model = save(client, model="claude-haiku-5-5").json()
    run_test(client)
    other_address = save(client, model="claude-haiku-5-5", base_url="https://proxy.example").json()

    assert same["tool_test"]["supported"] is False
    assert other_model["tool_test"] is None
    assert other_address["tool_test"] is None


@respx.mock
def test_a_rate_limited_tool_check_is_not_a_conclusion(client: TestClient) -> None:
    """限流、provider 掛掉、連不上是「這次沒測成」：不存，也不說不支援。"""
    limited = httpx.Response(
        429, json={"type": "error", "error": {"type": "rate_limit_error", "message": "slow"}}
    )
    respx.post(OFFICIAL).mock(side_effect=endpoint(says("ok"), lambda _: limited, says("-")))
    save(client)

    result = run_test(client).json()

    assert result["failure"] is None
    assert result["tools"] is None
    assert result["tools_failure"] == "rate_limited"
    assert client.get(BASE).json()["tool_test"] is None
    assert [row.failure for row in calls_in(client)] == [None, "rate_limited"]


def anthropic_error(status: int, kind: str, message: str, **headers: str) -> httpx.Response:
    return httpx.Response(
        status, json={"type": "error", "error": {"type": kind, "message": message}}, headers=headers
    )


@pytest.mark.parametrize(
    ("answer", "failure"),
    [
        (
            anthropic_error(429, "rate_limit_error", "Rate limited", **{"retry-after": "12"}),
            "rate_limited",
        ),
        (anthropic_error(401, "authentication_error", "invalid x-api-key"), "auth_failed"),
        (anthropic_error(404, "not_found_error", "model: claude-nope"), "model_not_found"),
        (httpx.ConnectError("connection refused"), "unreachable"),
    ],
)
@respx.mock
def test_each_failure_comes_back_with_its_reason(
    client: TestClient, answer: httpx.Response | Exception, failure: str
) -> None:
    route = respx.post(OFFICIAL)
    if isinstance(answer, Exception):
        route.mock(side_effect=answer)
    else:
        route.mock(return_value=answer)
    save(client, model="claude-nope")

    response = run_test(client)
    result = response.json()

    assert response.status_code == 200
    assert result["failure"] == failure
    assert result["tools"] is None
    assert result["retry_after"] == (12.0 if failure == "rate_limited" else None)
    # 第一次沒過就不往下測。
    assert route.call_count == 1
    assert KEY not in response.text
    assert [row.failure for row in calls_in(client)] == [failure]


@respx.mock
def test_models_come_from_the_endpoint(client: TestClient) -> None:
    respx.get("https://api.anthropic.com/v1/models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "claude-opus-5-5"}]})
    )
    save(client)

    listed = client.get(f"{BASE}/models").json()

    assert listed == {"models": ["claude-opus-5-5"], "failure": None, "detail": ""}


@respx.mock
def test_an_endpoint_without_a_model_list_falls_back_to_typing(client: TestClient) -> None:
    respx.get("http://ollama.lan:11434/v1/models").mock(return_value=httpx.Response(404))
    save(client, base_url="http://ollama.lan:11434", api_key="", model="qwen3")

    listed = client.get(f"{BASE}/models").json()

    assert listed == {"models": None, "failure": None, "detail": ""}
