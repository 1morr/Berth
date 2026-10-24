"""OpenAI 相容格式（Chat Completions）的 adapter 對假端點（respx）的契約（M5 票 07b、brief
§20.24）。

假端點回的 SSE 照研究底稿 `docs/research/ai-providers/openai-compatible.md` §1.4、§3.1、§6 組：
每個 chunk 一行 `data: <JSON>`，`choices[0].delta` 帶文字或 `tool_calls` 片段，最後一個
`finish_reason`，開了 `include_usage` 時 `[DONE]` 前多一個只有 `usage` 的 chunk。
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from berth.adapters.ai import (
    AiProviderError,
    ChatRequest,
    Endpoint,
    ModelTurn,
    OpaquePart,
    StopReason,
    TextDelta,
    TextPart,
    ToolCall,
    ToolCallStarted,
    ToolResult,
    ToolSpec,
    TurnEnded,
    Usage,
    UserTurn,
)
from berth.adapters.ai.openai import OpenAiProvider
from berth.domain import AiFailure, ApiFormat

pytestmark = pytest.mark.asyncio

KEY = "sk-or-test-0123456789"
OPENROUTER = "https://openrouter.ai/api/v1"
COMPLETIONS = f"{OPENROUTER}/chat/completions"
MODEL = "qwen/qwen3-coder"
HELLO = ChatRequest(
    model=MODEL,
    system="",
    tools=(),
    turns=(UserTurn((TextPart("Say ok"),)),),
    max_output_tokens=64,
)


def provider(base_url: str = OPENROUTER, api_key: str = KEY) -> OpenAiProvider:
    return OpenAiProvider(Endpoint(format=ApiFormat.OPENAI, base_url=base_url, api_key=api_key))


def sse(*chunks: dict[str, Any] | str, done: bool = True) -> httpx.Response:
    """一段 SSE。字串原樣放進去（註解行、壞掉的尾巴），其餘是一個 chunk 的 JSON。"""
    lines = [
        chunk if isinstance(chunk, str) else f"data: {json.dumps(chunk)}\n\n" for chunk in chunks
    ]
    if done:
        lines.append("data: [DONE]\n\n")
    return httpx.Response(
        200, headers={"content-type": "text/event-stream"}, content="".join(lines).encode()
    )


def chunk(delta: dict[str, Any] | None = None, finish: str | None = None) -> dict[str, Any]:
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion.chunk",
        "model": MODEL,
        "choices": [{"index": 0, "delta": delta or {}, "finish_reason": finish}],
    }


def usage_chunk(**usage: Any) -> dict[str, Any]:
    """`include_usage` 的最後一個 chunk：`choices` 是空的（OpenAI 的樣子）。"""
    body = {"prompt_tokens": 30, "completion_tokens": 4, "total_tokens": 34, **usage}
    return {"id": "chatcmpl-1", "object": "chat.completion.chunk", "choices": [], "usage": body}


async def drain(stream: Any) -> list[Any]:
    return [event async for event in stream]


@respx.mock
async def test_a_text_reply_streams_and_ends_with_the_whole_turn() -> None:
    route = respx.post(COMPLETIONS).mock(
        return_value=sse(
            ": OPENROUTER PROCESSING\n\n",
            chunk({"role": "assistant", "content": ""}),
            chunk({"content": "o"}),
            chunk({"content": "k"}),
            chunk({}, finish="stop"),
            usage_chunk(),
        )
    )

    events = await drain(provider().stream(HELLO))

    assert [e for e in events if isinstance(e, TextDelta)] == [TextDelta("o"), TextDelta("k")]
    ended = events[-1]
    assert isinstance(ended, TurnEnded)
    assert ended.stop is StopReason.END
    assert ended.stop_raw == "stop"
    assert ended.reply.text == "ok"
    assert ended.usage == Usage(input_tokens=30, output_tokens=4)

    sent = route.calls.last.request
    assert sent.headers["authorization"] == f"Bearer {KEY}"
    body = json.loads(sent.content)
    assert body["model"] == MODEL
    assert body["stream"] is True
    assert body["stream_options"] == {"include_usage": True}
    assert body["messages"] == [{"role": "user", "content": "Say ok"}]
    assert body["max_tokens"] == 64
    # 只能聊天的請求不帶 `tools`（vLLM 對空陣列回 400），也不強制呼叫。
    assert "tools" not in body
    assert "tool_choice" not in body


def text_reply(text: str = "ok", **usage: Any) -> httpx.Response:
    return sse(chunk({"content": text}), chunk({}, finish="stop"), usage_chunk(**usage))


@respx.mock
async def test_the_official_endpoint_is_used_when_no_base_url_is_given() -> None:
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(return_value=text_reply())

    ended = (await drain(provider(base_url="").stream(HELLO)))[-1]

    assert ended.reply.text == "ok"
    assert provider(base_url="").host == "api.openai.com"
    body = json.loads(route.calls.last.request.content)
    # 官方的推理模型不收 `max_tokens`；第三方（Ollama）只認得 `max_tokens`。
    assert body["max_completion_tokens"] == 64
    assert "max_tokens" not in body


@respx.mock
async def test_without_a_key_no_credential_header_is_sent() -> None:
    route = respx.post("http://ollama:11434/v1/chat/completions").mock(return_value=text_reply())

    await drain(provider(base_url="http://ollama:11434/v1/", api_key="").stream(HELLO))

    assert "authorization" not in route.calls.last.request.headers
    assert provider(base_url="http://ollama:11434/v1").host == "ollama:11434"


@respx.mock
async def test_the_system_text_goes_first_as_a_system_message() -> None:
    route = respx.post(COMPLETIONS).mock(return_value=text_reply())
    request = ChatRequest(
        model=MODEL,
        system="You are Berth.",
        tools=(),
        turns=HELLO.turns,
        max_output_tokens=64,
    )

    await drain(provider().stream(request))

    body = json.loads(route.calls.last.request.content)
    assert body["messages"][0] == {"role": "system", "content": "You are Berth."}


# ---- usage ---------------------------------------------------------------------------------------


@respx.mock
async def test_cache_fields_the_endpoint_does_not_return_are_unknown_not_zero() -> None:
    # Ollama、沒開 `--enable-prompt-tokens-details` 的 vLLM：只有輸入與輸出。
    respx.post(COMPLETIONS).mock(return_value=text_reply())

    ended = (await drain(provider().stream(HELLO)))[-1]

    assert ended.usage == Usage(
        input_tokens=30, output_tokens=4, cache_write_tokens=None, cache_read_tokens=None
    )


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        # OpenAI、OpenRouter：讀取與寫入都在 `prompt_tokens_details`。
        (
            {"prompt_tokens_details": {"cached_tokens": 20, "cache_write_tokens": 8}},
            Usage(input_tokens=30, output_tokens=4, cache_write_tokens=8, cache_read_tokens=20),
        ),
        # 回了 0 就是 0。
        (
            {"prompt_tokens_details": {"cached_tokens": 0}},
            Usage(input_tokens=30, output_tokens=4, cache_write_tokens=None, cache_read_tokens=0),
        ),
        # DeepSeek：頂層的 `prompt_cache_hit_tokens`，沒有寫入。
        (
            {"prompt_cache_hit_tokens": 12, "prompt_cache_miss_tokens": 18},
            Usage(input_tokens=30, output_tokens=4, cache_write_tokens=None, cache_read_tokens=12),
        ),
        # vLLM：寫入叫 `created_cache_tokens`。
        (
            {"prompt_tokens_details": {"cached_tokens": 16, "created_cache_tokens": 14}},
            Usage(input_tokens=30, output_tokens=4, cache_write_tokens=14, cache_read_tokens=16),
        ),
        # `prompt_tokens_details` 是 null（有的端點這樣回）。
        (
            {"prompt_tokens_details": None},
            Usage(input_tokens=30, output_tokens=4),
        ),
    ],
)
@respx.mock
async def test_cache_fields_map_from_each_endpoint_shape(
    usage: dict[str, Any], expected: Usage
) -> None:
    respx.post(COMPLETIONS).mock(return_value=text_reply(**usage))

    ended = (await drain(provider().stream(HELLO)))[-1]

    assert ended.usage == expected


@respx.mock
async def test_a_cache_read_larger_than_the_input_is_not_believed() -> None:
    # 研究最後一節第 7 條：`prompt_tokens` 含不含快取讀取沒有逐字說明；不含的話命中率會超過 100%。
    respx.post(COMPLETIONS).mock(
        return_value=text_reply(prompt_tokens_details={"cached_tokens": 64})
    )

    ended = (await drain(provider().stream(HELLO)))[-1]

    assert ended.usage.input_tokens == 30
    assert ended.usage.cache_read_tokens is None


@respx.mock
async def test_usage_on_a_chunk_that_still_has_choices_is_taken() -> None:
    # OpenRouter：最後一個 chunk 的 `choices` 不是空的（「Unlike OpenAI's spec」）。
    last = {**chunk({"content": ""}, finish="stop"), "usage": usage_chunk()["usage"]}
    respx.post(COMPLETIONS).mock(
        return_value=sse(chunk({"content": "ok"}), {**chunk({}), "usage": None}, last)
    )

    ended = (await drain(provider().stream(HELLO)))[-1]

    assert ended.usage == Usage(input_tokens=30, output_tokens=4)
    assert ended.stop is StopReason.END


# ---- 工具呼叫 ------------------------------------------------------------------------------------

ECHO = ToolSpec(
    name="berth_echo",
    description="Echo a nonce back.",
    input_schema={"type": "object", "properties": {"nonce": {"type": "string"}}},
)
ALPHA = ToolSpec(name="alpha", description="First by name.", input_schema={"type": "object"})


def call_piece(
    index: int, arguments: str, *, call_id: str | None = None, name: str | None = None
) -> dict[str, Any]:
    piece: dict[str, Any] = {"index": index, "function": {"arguments": arguments}}
    if call_id is not None:
        piece |= {"id": call_id, "type": "function"}
    if name is not None:
        piece["function"]["name"] = name
    return chunk({"tool_calls": [piece]})


def asking(*tools: ToolSpec) -> ChatRequest:
    return ChatRequest(
        model=MODEL,
        system="",
        tools=tools,
        turns=(UserTurn((TextPart('Call berth_echo with nonce "n1"'),)),),
        max_output_tokens=64,
    )


@respx.mock
async def test_tool_calls_are_pieced_together_from_their_fragments() -> None:
    route = respx.post(COMPLETIONS).mock(
        return_value=sse(
            chunk({"role": "assistant", "content": None}),
            call_piece(0, "", call_id="call_a", name="berth_echo"),
            call_piece(0, '{"non'),
            call_piece(0, 'ce": "n1"}'),
            # 平行的第二個呼叫。
            call_piece(1, '{"nonce": "n2"}', call_id="call_b", name="berth_echo"),
            chunk({}, finish="tool_calls"),
            usage_chunk(),
        )
    )

    events = await drain(provider().stream(asking(ECHO, ALPHA)))

    assert [e for e in events if isinstance(e, ToolCallStarted)] == [
        ToolCallStarted(id="call_a", name="berth_echo"),
        ToolCallStarted(id="call_b", name="berth_echo"),
    ]
    ended = events[-1]
    assert ended.stop is StopReason.TOOL_CALLS
    assert ended.reply.tool_calls == (
        ToolCall(id="call_a", name="berth_echo", arguments='{"nonce": "n1"}'),
        ToolCall(id="call_b", name="berth_echo", arguments='{"nonce": "n2"}'),
    )
    body = json.loads(route.calls.last.request.content)
    # 工具依名稱排序（快取吃前綴）；不送 `tool_choice`（Ollama 不支援，研究結論 4）。
    assert body["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "alpha",
                "description": "First by name.",
                "parameters": {"type": "object"},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "berth_echo",
                "description": "Echo a nonce back.",
                "parameters": {"type": "object", "properties": {"nonce": {"type": "string"}}},
            },
        },
    ]
    assert "tool_choice" not in body


@respx.mock
async def test_a_call_that_comes_whole_in_one_chunk_without_an_id_still_counts() -> None:
    # Ollama 一次給完整的參數；有的端點不給 id，`finish_reason` 也照樣寫 `stop`。
    respx.post(COMPLETIONS).mock(
        return_value=sse(
            chunk(
                {
                    "tool_calls": [
                        {
                            "index": 0,
                            "function": {"name": "berth_echo", "arguments": '{"nonce":"n1"}'},
                        }
                    ]
                }
            ),
            chunk({}, finish="stop"),
        )
    )

    ended = (await drain(provider().stream(asking(ECHO))))[-1]

    assert ended.reply.tool_calls == (
        ToolCall(id="call_0", name="berth_echo", arguments='{"nonce":"n1"}'),
    )
    assert ended.stop is StopReason.TOOL_CALLS
    assert ended.stop_raw == "stop"


@respx.mock
async def test_tool_results_go_back_as_one_tool_message_each() -> None:
    route = respx.post(COMPLETIONS).mock(return_value=text_reply("Got it."))
    called = ModelTurn(
        (
            TextPart("Calling."),
            ToolCall(id="call_a", name="berth_echo", arguments='{"nonce": "n1"}'),
            ToolCall(id="call_b", name="berth_echo", arguments=""),
        )
    )
    results = UserTurn(
        (
            ToolResult("call_a", '{"nonce": "n1"}'),
            ToolResult("call_b", '{"error": "bad arguments"}', is_error=True),
            TextPart("Now answer."),
        )
    )
    request = ChatRequest(
        model=MODEL,
        system="",
        tools=(ECHO,),
        turns=(*asking(ECHO).turns, called, results),
        max_output_tokens=64,
    )

    await drain(provider().stream(request))

    messages = json.loads(route.calls.last.request.content)["messages"]
    assert messages[1:] == [
        {
            "role": "assistant",
            "content": "Calling.",
            "tool_calls": [
                {
                    "id": "call_a",
                    "type": "function",
                    "function": {"name": "berth_echo", "arguments": '{"nonce": "n1"}'},
                },
                # 沒給參數送 `{}`：有的端點不收空字串。
                {
                    "id": "call_b",
                    "type": "function",
                    "function": {"name": "berth_echo", "arguments": "{}"},
                },
            ],
        },
        {"role": "tool", "tool_call_id": "call_a", "content": '{"nonce": "n1"}'},
        # 這個格式沒有 is_error：錯誤本來就寫在 content 裡。
        {"role": "tool", "tool_call_id": "call_b", "content": '{"error": "bad arguments"}'},
        {"role": "user", "content": "Now answer."},
    ]


@respx.mock
async def test_a_turn_with_only_calls_sends_no_text_content() -> None:
    route = respx.post(COMPLETIONS).mock(return_value=text_reply())
    called = ModelTurn((ToolCall(id="call_a", name="berth_echo", arguments="{}"),))
    request = ChatRequest(
        model=MODEL,
        system="",
        tools=(ECHO,),
        turns=(*asking(ECHO).turns, called, UserTurn((ToolResult("call_a", "{}"),))),
        max_output_tokens=64,
    )

    await drain(provider().stream(request))

    messages = json.loads(route.calls.last.request.content)["messages"]
    assert messages[1]["content"] is None


@respx.mock
async def test_reasoning_content_comes_back_and_goes_out_with_the_turn() -> None:
    # DeepSeek 思考模式帶工具：前幾輪的 `reasoning_content` 要送回去（研究底稿 §3.4）。
    route = respx.post(COMPLETIONS).mock(
        side_effect=[
            sse(
                chunk({"reasoning_content": "Need to "}),
                chunk({"reasoning_content": "call it."}),
                call_piece(0, '{"nonce": "n1"}', call_id="call_a", name="berth_echo"),
                chunk({}, finish="tool_calls"),
            ),
            text_reply("Done."),
        ]
    )

    first = (await drain(provider().stream(asking(ECHO))))[-1]
    assert first.reply.text == ""
    assert (
        OpaquePart(format=ApiFormat.OPENAI, raw={"reasoning_content": "Need to call it."})
        in first.reply.parts
    )

    follow = ChatRequest(
        model=MODEL,
        system="",
        tools=(ECHO,),
        turns=(*asking(ECHO).turns, first.reply, UserTurn((ToolResult("call_a", "{}"),))),
        max_output_tokens=64,
    )
    await drain(provider().stream(follow))

    assistant = json.loads(route.calls.last.request.content)["messages"][1]
    assert assistant["reasoning_content"] == "Need to call it."
    assert assistant["tool_calls"][0]["id"] == "call_a"


@respx.mock
async def test_opaque_parts_of_another_format_are_not_sent() -> None:
    route = respx.post(COMPLETIONS).mock(return_value=text_reply())
    thinking = OpaquePart(format=ApiFormat.ANTHROPIC, raw={"type": "thinking", "thinking": "x"})
    request = ChatRequest(
        model=MODEL,
        system="",
        tools=(),
        turns=(*HELLO.turns, ModelTurn((thinking, TextPart("ok"))), *HELLO.turns),
        max_output_tokens=64,
    )

    await drain(provider().stream(request))

    assistant = json.loads(route.calls.last.request.content)["messages"][1]
    assert assistant == {"role": "assistant", "content": "ok"}


# ---- 錯誤 ----------------------------------------------------------------------------------------


def error(status: int, body: object, **headers: str) -> httpx.Response:
    content = body if isinstance(body, str) else json.dumps(body)
    kind = "text/html" if isinstance(body, str) else "application/json"
    return httpx.Response(
        status, headers={"content-type": kind, **headers}, content=content.encode()
    )


async def failure_of(response: httpx.Response) -> AiProviderError:
    respx.post(COMPLETIONS).mock(return_value=response)
    with pytest.raises(AiProviderError) as caught:
        await drain(provider().stream(HELLO))
    return caught.value


@pytest.mark.parametrize(
    ("response", "failure"),
    [
        (
            error(
                429,
                {
                    "error": {
                        "message": "Rate limit reached",
                        "type": "requests",
                        "code": "rate_limit_exceeded",
                    }
                },
            ),
            AiFailure.RATE_LIMITED,
        ),
        (
            error(
                429,
                {
                    "error": {
                        "message": "slow down",
                        "type": "rate_limit_error",
                        "code": "slow_down",
                    }
                },
            ),
            AiFailure.RATE_LIMITED,
        ),
        # OpenAI 的額度與支出上限也是 429，看 `error.code` / `error.type`（研究結論 8）。
        (
            error(
                429,
                {
                    "error": {
                        "message": "no credit",
                        "type": "insufficient_quota",
                        "code": "credit_balance_exhausted",
                    }
                },
            ),
            AiFailure.QUOTA_EXHAUSTED,
        ),
        (
            error(429, {"error": {"message": "cap", "type": "insufficient_quota", "code": None}}),
            AiFailure.QUOTA_EXHAUSTED,
        ),
        (
            error(
                429,
                {"error": {"message": "cap", "type": "x", "code": "project_spend_limit_exceeded"}},
            ),
            AiFailure.QUOTA_EXHAUSTED,
        ),
        (
            error(
                429,
                {
                    "error": {
                        "message": "cap",
                        "type": "x",
                        "code": "organization_usage_limit_exceeded",
                    }
                },
            ),
            AiFailure.QUOTA_EXHAUSTED,
        ),
        # OpenRouter、DeepSeek 的 402；OpenRouter 的 `error.code` 是整數。
        (
            error(402, {"error": {"code": 402, "message": "Insufficient credits"}}),
            AiFailure.QUOTA_EXHAUSTED,
        ),
        (
            error(
                401,
                {
                    "error": {
                        "message": "Incorrect API key provided",
                        "type": "invalid_request_error",
                        "code": "invalid_api_key",
                    }
                },
            ),
            AiFailure.AUTH_FAILED,
        ),
        (error(403, {"error": {"code": 403, "message": "Key limit"}}), AiFailure.AUTH_FAILED),
        # 三家「模型不存在」的樣子：OpenAI、Ollama、vLLM。
        (
            error(
                404,
                {
                    "error": {
                        "message": "The model `gpt-x` does not exist",
                        "type": "invalid_request_error",
                        "code": "model_not_found",
                    }
                },
            ),
            AiFailure.MODEL_NOT_FOUND,
        ),
        (
            error(
                404,
                {
                    "error": {
                        "message": 'model "qwen9" not found, try pulling it first',
                        "type": "not_found_error",
                        "param": None,
                        "code": None,
                    }
                },
            ),
            AiFailure.MODEL_NOT_FOUND,
        ),
        (
            error(
                404,
                {
                    "error": {
                        "message": "The model `qwen9` does not exist.",
                        "type": "NotFoundError",
                        "param": None,
                        "code": 404,
                    }
                },
            ),
            AiFailure.MODEL_NOT_FOUND,
        ),
        (
            error(
                503,
                {
                    "error": {
                        "message": "overloaded",
                        "type": "service_unavailable_error",
                        "code": "server_is_overloaded",
                    }
                },
            ),
            AiFailure.PROVIDER_DOWN,
        ),
        (
            error(502, {"error": {"code": 502, "message": "Provider returned error"}}),
            AiFailure.PROVIDER_DOWN,
        ),
        (
            error(
                400,
                {
                    "error": {
                        "message": '"auto" tool choice requires --enable-auto-tool-choice'
                        " and --tool-call-parser to be set",
                        "type": "BadRequestError",
                        "code": 400,
                    }
                },
            ),
            AiFailure.REJECTED,
        ),
        (
            error(422, {"error": {"code": "invalid_parameters", "message": "bad"}}),
            AiFailure.REJECTED,
        ),
    ],
)
@respx.mock
async def test_each_error_answer_maps_to_its_reason(
    response: httpx.Response, failure: AiFailure
) -> None:
    caught = await failure_of(response)

    assert caught.failure is failure
    assert caught.usage == Usage()


@respx.mock
async def test_a_rate_limit_says_when_to_come_back() -> None:
    caught = await failure_of(
        error(
            429,
            {"error": {"message": "slow", "code": "rate_limit_exceeded"}},
            **{"retry-after": "7"},
        )
    )

    assert caught.retry_after == 7.0
    assert "429" in caught.detail
    assert "slow" in caught.detail


@pytest.mark.parametrize(
    ("response", "failure", "said"),
    [
        # 反向代理的 404 頁：多半是 base URL 少了 `/v1`，不是模型不存在。
        (
            error(404, "<html><body>404 page not found</body></html>"),
            AiFailure.REJECTED,
            "404 page not found",
        ),
        (error(404, {"detail": "Not Found"}), AiFailure.REJECTED, "Not Found"),
        # OpenAI 自己的「網址不對」也是 404，但說的不是模型。
        (
            error(
                404,
                {
                    "error": {
                        "message": "Invalid URL (POST /v1/chat/completion)",
                        "type": "invalid_request_error",
                        "code": None,
                    }
                },
            ),
            AiFailure.REJECTED,
            "Invalid URL",
        ),
        # Ollama 原生端點的形狀：`error` 是字串。
        (error(400, {"error": "json: cannot unmarshal"}), AiFailure.REJECTED, "cannot unmarshal"),
        (error(500, "Internal Server Error"), AiFailure.PROVIDER_DOWN, "Internal Server Error"),
        (error(418, ""), AiFailure.REJECTED, "418"),
    ],
)
@respx.mock
async def test_an_error_body_berth_cannot_read_falls_back_safely_with_the_raw_text(
    response: httpx.Response, failure: AiFailure, said: str
) -> None:
    caught = await failure_of(response)

    assert caught.failure is failure
    assert said in caught.detail


@respx.mock
async def test_an_error_body_in_a_200_is_still_an_error() -> None:
    # OpenRouter 非串流時可能回 200 加只有 `error` 的 JSON（「Check the body for an `error` field
    # even on a `200`」）。
    caught = await failure_of(error(200, {"error": {"code": 502, "message": "upstream died"}}))

    assert caught.failure is AiFailure.PROVIDER_DOWN
    assert "upstream died" in caught.detail


@respx.mock
async def test_a_200_that_is_not_an_event_stream_is_not_understood() -> None:
    caught = await failure_of(error(200, "<html>captive portal</html>"))

    assert caught.failure is AiFailure.REJECTED
    assert "captive portal" in caught.detail


@respx.mock
async def test_an_error_chunk_after_200_is_the_provider_going_down() -> None:
    # OpenRouter：先送了內容，再送一個帶 `error` 與 `finish_reason: "error"` 的 chunk。
    broken = {
        **chunk({"content": ""}, finish="error"),
        "error": {
            "code": 502,
            "message": "Provider disconnected",
            "metadata": {"error_type": "provider_unavailable"},
        },
    }
    respx.post(COMPLETIONS).mock(return_value=sse(chunk({"content": "Hal"}), broken))

    with pytest.raises(AiProviderError) as caught:
        await drain(provider().stream(HELLO))

    assert caught.value.failure is AiFailure.PROVIDER_DOWN
    assert "Provider disconnected" in caught.value.detail


@respx.mock
async def test_a_rate_limit_inside_the_stream_is_a_rate_limit() -> None:
    broken = {
        "error": {
            "code": 429,
            "message": "upstream rate limited",
            "metadata": {"error_type": "rate_limit_exceeded"},
        }
    }
    respx.post(COMPLETIONS).mock(return_value=sse(broken))

    with pytest.raises(AiProviderError) as caught:
        await drain(provider().stream(HELLO))

    assert caught.value.failure is AiFailure.RATE_LIMITED


@pytest.mark.parametrize(
    "error_body",
    [
        # OpenAI 形狀：`code` 是字串。
        {"message": "Rate limit reached", "type": "requests", "code": "rate_limit_exceeded"},
        {"message": "slow down", "type": "rate_limit_error", "code": None},
    ],
)
@respx.mock
async def test_a_rate_limit_named_by_its_code_inside_the_stream_is_a_rate_limit(
    error_body: dict[str, Any],
) -> None:
    respx.post(COMPLETIONS).mock(return_value=sse({"error": error_body}))

    with pytest.raises(AiProviderError) as caught:
        await drain(provider().stream(HELLO))

    assert caught.value.failure is AiFailure.RATE_LIMITED


@respx.mock
async def test_a_finish_reason_of_error_without_an_error_object_is_still_down() -> None:
    respx.post(COMPLETIONS).mock(
        return_value=sse(chunk({"content": "x"}), chunk({}, finish="error"))
    )

    with pytest.raises(AiProviderError) as caught:
        await drain(provider().stream(HELLO))

    assert caught.value.failure is AiFailure.PROVIDER_DOWN


@respx.mock
async def test_a_chunk_that_is_not_json_is_not_understood() -> None:
    respx.post(COMPLETIONS).mock(return_value=sse(chunk({"content": "x"}), "data: {oops\n\n"))

    with pytest.raises(AiProviderError) as caught:
        await drain(provider().stream(HELLO))

    assert caught.value.failure is AiFailure.REJECTED
    assert "{oops" in caught.value.detail


@respx.mock
async def test_a_stream_that_stops_before_the_model_finished_is_an_error() -> None:
    respx.post(COMPLETIONS).mock(return_value=sse(chunk({"content": "Hal"}), done=False))

    with pytest.raises(AiProviderError) as caught:
        await drain(provider().stream(HELLO))

    assert caught.value.failure is AiFailure.PROVIDER_DOWN
    # usage 只在最後一個 chunk：斷掉時四格都不知道（研究結論 7）。
    assert caught.value.usage == Usage()


@respx.mock
async def test_a_finished_turn_whose_stream_closes_without_done_still_counts() -> None:
    # 模型已經說完（有 `finish_reason`），只是端點沒送 `[DONE]` 就關了連線。
    respx.post(COMPLETIONS).mock(
        return_value=sse(
            chunk({"content": "ok"}), chunk({}, finish="stop"), usage_chunk(), done=False
        )
    )

    ended = (await drain(provider().stream(HELLO)))[-1]

    assert isinstance(ended, TurnEnded)
    assert ended.reply.text == "ok"
    assert ended.usage.input_tokens == 30


@respx.mock
async def test_a_refused_connection_is_unreachable() -> None:
    respx.post(COMPLETIONS).mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(AiProviderError) as caught:
        await drain(provider().stream(HELLO))

    assert caught.value.failure is AiFailure.UNREACHABLE


@respx.mock
async def test_the_key_never_shows_up_in_an_error() -> None:
    caught = await failure_of(
        error(401, {"error": {"message": "bad key", "code": "invalid_api_key"}})
    )

    assert KEY not in caught.detail
    assert KEY not in str(caught)


# ---- 模型清單 ------------------------------------------------------------------------------------


@respx.mock
async def test_models_are_listed_from_the_endpoint() -> None:
    route = respx.get(f"{OPENROUTER}/models").mock(
        return_value=httpx.Response(
            200,
            json={
                "object": "list",
                "data": [
                    {"id": "qwen/qwen3-coder", "object": "model"},
                    {"id": "deepseek/deepseek-v4"},
                    {"object": "model"},
                ],
            },
        )
    )

    assert await provider().list_models() == ["qwen/qwen3-coder", "deepseek/deepseek-v4"]
    assert route.calls.last.request.headers["authorization"] == f"Bearer {KEY}"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(404, json={"detail": "Not Found"}),
        httpx.Response(405, text="Method Not Allowed"),
        httpx.Response(200, text="<html>not json</html>"),
        httpx.Response(200, json={"models": ["a"]}),
    ],
)
@respx.mock
async def test_an_endpoint_without_a_model_list_falls_back_to_typing(
    response: httpx.Response,
) -> None:
    respx.get(f"{OPENROUTER}/models").mock(return_value=response)

    assert await provider().list_models() is None


@respx.mock
async def test_listing_models_with_a_bad_key_says_so() -> None:
    respx.get(f"{OPENROUTER}/models").mock(
        return_value=httpx.Response(
            401, json={"error": {"message": "No auth credentials found", "code": 401}}
        )
    )

    with pytest.raises(AiProviderError) as caught:
        await provider().list_models()

    assert caught.value.failure is AiFailure.AUTH_FAILED


@respx.mock
async def test_listing_models_on_a_dead_host_is_unreachable() -> None:
    respx.get(f"{OPENROUTER}/models").mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(AiProviderError) as caught:
        await provider().list_models()

    assert caught.value.failure is AiFailure.UNREACHABLE
