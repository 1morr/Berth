"""設定頁的 AI 一格切到 OpenAI 相容（M5 票 07b）：測試的三次請求走真的 adapter 打假端點（respx）。

Anthropic 格式的同一組在 `test_ai_settings_api.py`；這裡驗格式換了之後：請求打到 Chat Completions、
三種「不支援工具呼叫」的樣子（400、忽略 `tools`、把呼叫寫成文字）都判得出來、列不出模型與
看不懂的錯誤不會壞。
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from berth.api.deps import get_client_factory
from berth.config import Config
from berth.main import create_app
from tests.integration.arrange import sign_in_owner
from tests.integration.test_ai_settings_api import BASE, BROWSER, AiFactory, calls_in, run_test

KEY = "sk-or-v1-do-not-leak-0123456789"
OPENROUTER = "https://openrouter.ai/api/v1"
COMPLETIONS = f"{OPENROUTER}/chat/completions"
MODEL = "qwen/qwen3-coder"


@pytest.fixture
def client(config: Config, tmp_path: Path) -> Iterator[TestClient]:
    factory = AiFactory()
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app) as running:
        sign_in_owner(running)
        yield running


def save(client: TestClient, **fields: Any) -> httpx.Response:
    body = {"format": "openai", "base_url": OPENROUTER, "model": MODEL, "api_key": KEY, **fields}
    response: httpx.Response = client.put(BASE, json=body, headers=BROWSER)
    return response


# ---- 假端點 -------------------------------------------------------------------------------------


def sse(*chunks: dict[str, Any]) -> httpx.Response:
    text = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n"
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=text.encode())


def delta(content: dict[str, Any], finish: str | None = None) -> dict[str, Any]:
    return {"choices": [{"index": 0, "delta": content, "finish_reason": finish}]}


def usage(**fields: Any) -> dict[str, Any]:
    return {"choices": [], "usage": {"prompt_tokens": 40, "completion_tokens": 2, **fields}}


def text_reply(text: str, **fields: Any) -> httpx.Response:
    return sse(delta({"content": text}), delta({}, "stop"), usage(**fields))


def tool_reply(name: str, arguments: str) -> httpx.Response:
    call = {"index": 0, "id": "call_1", "type": "function", "function": {"name": name}}
    return sse(
        delta({"tool_calls": [call]}),
        delta({"tool_calls": [{"index": 0, "function": {"arguments": arguments}}]}),
        delta({}, "tool_calls"),
        usage(),
    )


def nonce_of(request: httpx.Request) -> str:
    """探針第二次的使用者訊息裡那個 nonce（引號裡的那一段）。"""
    text: str = json.loads(request.content)["messages"][0]["content"]
    return text.split('"')[1]


Step = Callable[[httpx.Request], httpx.Response]


def endpoint(hello: Step, call: Step, after: Step) -> Step:
    """依請求的形狀分派：不帶工具的是第一次，最後一則是 `role: tool` 的是第三次。"""

    def answer(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if "tools" not in body:
            return hello(request)
        if body["messages"][-1]["role"] == "tool":
            return after(request)
        return call(request)

    return answer


def calls_echo(request: httpx.Request) -> httpx.Response:
    return tool_reply("berth_echo", json.dumps({"nonce": nonce_of(request)}))


def says(text: str) -> Step:
    return lambda _: text_reply(text)


WORKS = endpoint(says("ok"), calls_echo, says("Got it."))


# ---- 測試 ---------------------------------------------------------------------------------------


def test_the_official_openai_endpoint_has_no_default_model(client: TestClient) -> None:
    """預設模型只在官方 Anthropic 端點時給（研究結論 5）：OpenAI 官方也要選或填。"""
    view = save(client, base_url="", model="").json()

    assert view["ready"] is False
    assert view["official_models"] == {"anthropic": "claude-opus-5-5", "openai": None}


@respx.mock
def test_a_working_endpoint_answers_calls_the_tool_and_logs_every_call(
    client: TestClient,
) -> None:
    route = respx.post(COMPLETIONS).mock(side_effect=WORKS)
    assert save(client).json()["ready"] is True

    result = run_test(client).json()

    assert result["failure"] is None
    assert result["reply"] == "ok"
    assert result["tools"]["supported"] is True
    assert [call["step"] for call in result["calls"]] == ["hello", "tool_call", "tool_result"]
    # 第三次送回去的：帶 `tool_calls` 的 assistant，再一則 `role: tool`。
    sent = json.loads(route.calls.last.request.content)["messages"]
    assert [message["role"] for message in sent] == ["user", "assistant", "tool"]
    assert sent[1]["tool_calls"][0]["id"] == sent[2]["tool_call_id"] == "call_1"
    assert route.calls.last.request.headers["authorization"] == f"Bearer {KEY}"

    rows = calls_in(client)
    assert len(rows) == 3
    first = rows[0]
    assert (first.format, first.host, first.model) == ("openai", "openrouter.ai", MODEL)
    assert (first.input_tokens, first.output_tokens) == (40, 2)
    # 假端點沒回快取欄位：那是「不知道」，不是 0。
    assert (first.cache_write_tokens, first.cache_read_tokens) == (None, None)


@respx.mock
def test_cache_reads_the_endpoint_returns_are_recorded(client: TestClient) -> None:
    respx.post(COMPLETIONS).mock(
        side_effect=endpoint(
            lambda _: text_reply("ok", prompt_tokens_details={"cached_tokens": 32}),
            calls_echo,
            says("done"),
        )
    )
    save(client)

    run_test(client)

    first = calls_in(client)[0]
    assert (first.input_tokens, first.cache_write_tokens, first.cache_read_tokens) == (40, None, 32)


def rejects_tools(_: httpx.Request) -> httpx.Response:
    # vLLM 沒開 `--enable-auto-tool-choice`、Ollama 不支援工具的模型。
    return httpx.Response(
        400,
        json={
            "error": {
                "message": "qwen2:0.5b does not support tools",
                "type": "invalid_request_error",
            }
        },
    )


def writes_the_call_as_text(request: httpx.Request) -> httpx.Response:
    # vLLM 沒開 `--tool-call-parser`：模型輸出的呼叫原樣成了文字。
    nonce = nonce_of(request)
    return text_reply(
        f'<tool_call>{{"name": "berth_echo", "arguments": {{"nonce": "{nonce}"}}}}</tool_call>'
    )


@respx.mock
def test_calling_the_tool_again_after_the_result_still_counts_as_supported(
    client: TestClient,
) -> None:
    """實跑 DeepSeek（2026-10-24，兩種格式都是）：同一組設定連測 20 次有 14 次在第三步又呼叫一次
    `berth_echo`（名字與 nonce 都對），被判成「只能聊天」。工具結果的來回已經走通，那一次呼叫就是
    支援的證據；這個假端點輪流回呼叫與一句話，連測四次都要是支援（M5 票 16）。"""
    afters = iter([calls_echo, says("Got it."), calls_echo, says("Got it.")])
    respx.post(COMPLETIONS).mock(
        side_effect=endpoint(says("ok"), calls_echo, lambda request: next(afters)(request))
    )
    save(client)

    verdicts = [run_test(client).json()["tools"] for _ in range(4)]

    assert [tools["supported"] for tools in verdicts] == [True, True, True, True]


@pytest.mark.parametrize(
    ("call", "gap"),
    [
        (rejects_tools, "tools_rejected"),
        # OpenRouter 在上游都不支援時忽略 `tools`、照樣回 200。
        (says("Sure, done!"), "tools_ignored"),
        (writes_the_call_as_text, "written_as_text"),
    ],
)
@respx.mock
def test_each_way_of_not_supporting_tools_is_chat_only(
    client: TestClient, call: Step, gap: str
) -> None:
    respx.post(COMPLETIONS).mock(side_effect=endpoint(says("ok"), call, says("unused")))
    save(client)

    result = run_test(client).json()

    assert result["failure"] is None
    assert result["tools"]["supported"] is False
    assert result["tools"]["gap"] == gap
    assert client.get(BASE).json()["tool_test"]["supported"] is False


@respx.mock
def test_switching_the_format_needs_a_new_test(client: TestClient) -> None:
    respx.post(COMPLETIONS).mock(side_effect=WORKS)
    save(client)
    run_test(client)

    switched = save(client, format="anthropic", base_url="https://openrouter.ai/api").json()

    assert switched["tool_test"] is None


@respx.mock
def test_an_error_page_berth_cannot_read_still_comes_back_with_the_raw_text(
    client: TestClient,
) -> None:
    respx.post(COMPLETIONS).mock(
        return_value=httpx.Response(
            502, headers={"content-type": "text/html"}, text="<h1>Bad Gateway</h1>"
        )
    )
    save(client)

    response = run_test(client)
    result = response.json()

    assert result["failure"] == "provider_down"
    assert "Bad Gateway" in result["detail"]
    assert KEY not in response.text


@respx.mock
def test_a_404_that_is_not_about_the_model_says_the_address_is_wrong(client: TestClient) -> None:
    # 少了 `/v1`：反向代理回自己的 404 頁，不是「模型不存在」。
    respx.post("https://openrouter.ai/api/chat/completions").mock(
        return_value=httpx.Response(404, text="404 page not found")
    )
    save(client, base_url="https://openrouter.ai/api")

    result = run_test(client).json()

    assert result["failure"] == "rejected"
    assert "404 page not found" in result["detail"]


@respx.mock
def test_models_come_from_the_endpoint(client: TestClient) -> None:
    respx.get(f"{OPENROUTER}/models").mock(
        return_value=httpx.Response(
            200, json={"data": [{"id": MODEL}, {"id": "deepseek/deepseek-v4"}]}
        )
    )
    save(client)

    listed = client.get(f"{BASE}/models").json()

    assert listed == {"models": [MODEL, "deepseek/deepseek-v4"], "failure": None, "detail": ""}


@respx.mock
def test_an_endpoint_without_a_model_list_falls_back_to_typing(client: TestClient) -> None:
    respx.get("http://vllm.lan:8000/v1/models").mock(return_value=httpx.Response(404))
    save(client, base_url="http://vllm.lan:8000/v1", api_key="")

    listed = client.get(f"{BASE}/models").json()

    assert listed == {"models": None, "failure": None, "detail": ""}
