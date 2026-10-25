"""Anthropic Messages 格式的 adapter 對假端點（respx）的契約（M5 票 08、brief §20.24）。

假端點回的 SSE 照官方的事件形狀組（研究底稿 `docs/research/ai-providers/anthropic.md` §3.5、§6）：
`message_start` → 每個 block 的 `content_block_start` / `_delta` / `_stop` → `message_delta` →
`message_stop`，中間可夾 `ping`。
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

import httpx
import pytest
import respx

from berth.adapters.ai import (
    AiProviderError,
    ChatRequest,
    Endpoint,
    ModelInfo,
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
    UsageReported,
    UserTurn,
)
from berth.adapters.ai.anthropic import AnthropicProvider
from berth.domain import AiFailure, ApiFormat

pytestmark = pytest.mark.asyncio

KEY = "sk-ant-test-0123456789"
OFFICIAL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-opus-5-5"
HELLO = ChatRequest(
    model=MODEL,
    system="",
    tools=(),
    turns=(UserTurn((TextPart("Say ok"),)),),
    max_output_tokens=64,
)
ECHO = ToolSpec(
    name="berth_echo",
    description="Echo a nonce back.",
    input_schema={"type": "object", "properties": {"nonce": {"type": "string"}}},
)


def sse(*events: tuple[str, dict[str, Any]] | str) -> httpx.Response:
    """一段 SSE。字串原樣放進去（註解行、壞掉的尾巴），其餘是 `(event, data)`。"""
    chunks: list[str] = []
    for event in events:
        if isinstance(event, str):
            chunks.append(event)
        else:
            name, data = event
            chunks.append(f"event: {name}\ndata: {json.dumps(data)}\n\n")
    return httpx.Response(
        200, headers={"content-type": "text/event-stream"}, content="".join(chunks).encode()
    )


def message_start(**usage: int) -> tuple[str, dict[str, Any]]:
    body = {"input_tokens": 12, "output_tokens": 1, **usage}
    return (
        "message_start",
        {
            "type": "message_start",
            "message": {
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "content": [],
                "model": MODEL,
                "stop_reason": None,
                "usage": body,
            },
        },
    )


def text_block(index: int, *pieces: str) -> list[tuple[str, dict[str, Any]]]:
    return [
        (
            "content_block_start",
            {
                "type": "content_block_start",
                "index": index,
                "content_block": {"type": "text", "text": ""},
            },
        ),
        *[
            (
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": index,
                    "delta": {"type": "text_delta", "text": piece},
                },
            )
            for piece in pieces
        ],
        ("content_block_stop", {"type": "content_block_stop", "index": index}),
    ]


def tool_block(
    index: int, call_id: str, name: str, *json_pieces: str
) -> list[tuple[str, dict[str, Any]]]:
    return [
        (
            "content_block_start",
            {
                "type": "content_block_start",
                "index": index,
                "content_block": {"type": "tool_use", "id": call_id, "name": name, "input": {}},
            },
        ),
        *[
            (
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": index,
                    "delta": {"type": "input_json_delta", "partial_json": piece},
                },
            )
            for piece in json_pieces
        ],
        ("content_block_stop", {"type": "content_block_stop", "index": index}),
    ]


def message_end(stop: str = "end_turn", **usage: int) -> list[tuple[str, dict[str, Any]]]:
    return [
        (
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": stop},
                "usage": {"output_tokens": 5, **usage},
            },
        ),
        ("message_stop", {"type": "message_stop"}),
    ]


async def collect(provider: AnthropicProvider, request: ChatRequest = HELLO) -> list[Any]:
    return [event async for event in provider.stream(request)]


def official(key: str = KEY) -> AnthropicProvider:
    return AnthropicProvider(Endpoint(format=ApiFormat.ANTHROPIC, base_url="", api_key=key))


def body_of(route: respx.Route) -> dict[str, Any]:
    content: dict[str, Any] = json.loads(route.calls.last.request.content)
    return content


def flat(groups: Iterable[list[tuple[str, dict[str, Any]]]]) -> list[tuple[str, dict[str, Any]]]:
    return [event for group in groups for event in group]


@respx.mock
async def test_a_text_reply_streams_and_ends_with_the_whole_turn() -> None:
    route = respx.post(OFFICIAL).mock(
        return_value=sse(
            message_start(cache_creation_input_tokens=0, cache_read_input_tokens=0),
            ("ping", {"type": "ping"}),
            *text_block(0, "o", "k"),
            *message_end(),
        )
    )

    events = await collect(official())

    # 輸入在 `message_start` 就知道了；輸出要等講完。
    assert events[0] == UsageReported(
        Usage(input_tokens=12, output_tokens=None, cache_write_tokens=0, cache_read_tokens=0)
    )
    assert [event for event in events if isinstance(event, TextDelta)] == [
        TextDelta("o"),
        TextDelta("k"),
    ]
    assert events[-1] == TurnEnded(
        stop=StopReason.END,
        stop_raw="end_turn",
        reply=ModelTurn((TextPart("ok"),)),
        usage=Usage(input_tokens=12, output_tokens=5, cache_write_tokens=0, cache_read_tokens=0),
    )
    request = route.calls.last.request
    # 只送 `x-api-key`：官方仍收、DeepSeek 只列它（brief §20.24）。
    assert request.headers["x-api-key"] == KEY
    assert "authorization" not in request.headers
    assert request.headers["anthropic-version"] == "2026-10-21"
    body = body_of(route)
    assert body["model"] == MODEL
    assert body["stream"] is True
    assert body["max_tokens"] == 64
    assert body["messages"] == [{"role": "user", "content": [{"type": "text", "text": "Say ok"}]}]
    # 空的 system 與空的工具清單不送；沒有 temperature 這幾個（`2026-10-21` 送了回 400）。
    assert "system" not in body
    assert "tools" not in body
    assert not {"temperature", "top_p", "top_k"} & body.keys()


@pytest.mark.parametrize(
    ("raw", "stop"),
    [
        ("end_turn", StopReason.END),
        ("stop_sequence", StopReason.END),
        ("max_tokens", StopReason.MAX_TOKENS),
        ("model_context_window_exceeded", StopReason.CONTEXT_FULL),
        ("refusal", StopReason.REFUSED),
        ("pause_turn", StopReason.OTHER),
    ],
)
@respx.mock
async def test_each_stop_reason_maps_and_keeps_its_raw_value(raw: str, stop: StopReason) -> None:
    respx.post(OFFICIAL).mock(
        return_value=sse(message_start(), *text_block(0, "ok"), *message_end(raw))
    )

    ended = (await collect(official()))[-1]

    assert (ended.stop, ended.stop_raw) == (stop, raw)


def custom(base_url: str, key: str = "") -> AnthropicProvider:
    return AnthropicProvider(Endpoint(format=ApiFormat.ANTHROPIC, base_url=base_url, api_key=key))


@respx.mock
async def test_a_custom_base_url_is_where_the_request_goes() -> None:
    """base URL 照 `ANTHROPIC_BASE_URL` 的慣例不含 `/v1`（brief §20.24）；結尾的 `/` 不影響。"""
    route = respx.post("https://openrouter.ai/api/v1/messages").mock(
        return_value=sse(message_start(), *text_block(0, "ok"), *message_end())
    )
    provider = custom("https://openrouter.ai/api/", key=KEY)

    await collect(provider)

    assert route.called
    assert provider.host == "openrouter.ai"


@respx.mock
async def test_without_a_key_no_credential_header_is_sent() -> None:
    """自架的 Ollama 不驗 key：沒填就兩個認證標頭都不送，不是送空的。"""
    route = respx.post("http://ollama.lan:11434/v1/messages").mock(
        return_value=sse(message_start(), *text_block(0, "ok"), *message_end())
    )
    provider = custom("http://ollama.lan:11434")

    await collect(provider)

    request = route.calls.last.request
    assert "authorization" not in request.headers
    assert "x-api-key" not in request.headers
    assert provider.host == "ollama.lan:11434"


@respx.mock
async def test_cache_fields_the_endpoint_does_not_return_are_unknown_not_zero() -> None:
    respx.post(OFFICIAL).mock(
        return_value=sse(message_start(), *text_block(0, "ok"), *message_end())
    )

    events = await collect(official())

    assert events[-1].usage == Usage(
        input_tokens=12, output_tokens=5, cache_write_tokens=None, cache_read_tokens=None
    )


@respx.mock
async def test_total_input_counts_cache_writes_and_reads() -> None:
    """`input_tokens` 只算最後一個 breakpoint 之後的；全部輸入要加上兩個快取欄位（A §6）。
    `message_delta` 的 usage 是累計值，有給的欄位覆寫 `message_start` 的。"""
    respx.post(OFFICIAL).mock(
        return_value=sse(
            message_start(cache_creation_input_tokens=1000, cache_read_input_tokens=0),
            *text_block(0, "ok"),
            *message_end(output_tokens=9, cache_read_input_tokens=200),
        )
    )

    events = await collect(official())

    assert events[-1].usage == Usage(
        input_tokens=12 + 1000 + 200,
        output_tokens=9,
        cache_write_tokens=1000,
        cache_read_tokens=200,
    )


@respx.mock
async def test_tool_calls_are_pieced_together_from_their_json_fragments() -> None:
    route = respx.post(OFFICIAL).mock(
        return_value=sse(
            *flat(
                [
                    [message_start()],
                    text_block(0, "Calling."),
                    tool_block(1, "toolu_1", "berth_echo", '{"non', 'ce": "a1"}'),
                    tool_block(2, "toolu_2", "berth_echo"),
                    message_end("tool_use"),
                ]
            )
        )
    )
    request = ChatRequest(
        model=MODEL,
        system="You are Berth.",
        tools=(ToolSpec("zz_last", "z", {"type": "object"}), ECHO),
        turns=HELLO.turns,
        max_output_tokens=256,
    )

    events = await collect(official(), request)

    assert ToolCallStarted(id="toolu_1", name="berth_echo") in events
    ended = events[-1]
    assert ended.stop is StopReason.TOOL_CALLS
    assert ended.reply.tool_calls == (
        ToolCall(id="toolu_1", name="berth_echo", arguments='{"nonce": "a1"}'),
        ToolCall(id="toolu_2", name="berth_echo", arguments=""),
    )
    body = body_of(route)
    # 工具依名稱排序、system 帶顯式 breakpoint、頂層是自動快取（研究結論 6）。
    assert [tool["name"] for tool in body["tools"]] == ["berth_echo", "zz_last"]
    assert body["system"] == [
        {"type": "text", "text": "You are Berth.", "cache_control": {"type": "ephemeral"}}
    ]
    assert body["cache_control"] == {"type": "ephemeral"}
    assert "tool_choice" not in body


@respx.mock
async def test_tool_results_go_back_first_in_the_next_user_message() -> None:
    route = respx.post(OFFICIAL).mock(
        return_value=sse(message_start(), *text_block(0, "done"), *message_end())
    )
    thinking = OpaquePart(
        format=ApiFormat.ANTHROPIC,
        raw={"type": "thinking", "thinking": "hmm", "signature": "sig"},
    )
    request = ChatRequest(
        model=MODEL,
        system="",
        tools=(ECHO,),
        turns=(
            *HELLO.turns,
            ModelTurn(
                (thinking, ToolCall(id="toolu_1", name="berth_echo", arguments='{"nonce":"a1"}'))
            ),
            UserTurn((TextPart("Now answer."), ToolResult("toolu_1", '{"nonce": "a1"}'))),
        ),
        max_output_tokens=256,
    )

    await collect(official(), request)

    messages = body_of(route)["messages"]
    assert messages[1] == {
        "role": "assistant",
        "content": [
            {"type": "thinking", "thinking": "hmm", "signature": "sig"},
            {"type": "tool_use", "id": "toolu_1", "name": "berth_echo", "input": {"nonce": "a1"}},
        ],
    }
    assert messages[2] == {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_1",
                "content": '{"nonce": "a1"}',
                "is_error": False,
            },
            {"type": "text", "text": "Now answer."},
        ],
    }


@respx.mock
async def test_thinking_blocks_come_back_as_opaque_parts() -> None:
    """thinking 要原樣帶回下一輪（研究最後一節第 3 條）：Berth 不讀，但拼得回完整的 block。"""
    respx.post(OFFICIAL).mock(
        return_value=sse(
            message_start(),
            (
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "thinking", "thinking": ""},
                },
            ),
            (
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "thinking_delta", "thinking": "let me"},
                },
            ),
            (
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "signature_delta", "signature": "sig=="},
                },
            ),
            ("content_block_stop", {"type": "content_block_stop", "index": 0}),
            *text_block(1, "ok"),
            *message_end(),
        )
    )

    events = await collect(official())

    assert events[-1].reply == ModelTurn(
        (
            OpaquePart(
                format=ApiFormat.ANTHROPIC,
                raw={"type": "thinking", "thinking": "let me", "signature": "sig=="},
            ),
            TextPart("ok"),
        )
    )


def error_body(kind: str, message: str) -> dict[str, Any]:
    return {"type": "error", "error": {"type": kind, "message": message}, "request_id": "req_1"}


@pytest.mark.parametrize(
    ("status", "body", "headers", "failure"),
    [
        (
            429,
            error_body("rate_limit_error", "slow down"),
            {"retry-after": "7"},
            AiFailure.RATE_LIMITED,
        ),
        (401, error_body("authentication_error", "invalid x-api-key"), {}, AiFailure.AUTH_FAILED),
        (403, error_body("permission_error", "no access"), {}, AiFailure.AUTH_FAILED),
        (404, error_body("not_found_error", "model: claude-nope"), {}, AiFailure.MODEL_NOT_FOUND),
        (402, error_body("billing_error", "credit balance too low"), {}, AiFailure.QUOTA_EXHAUSTED),
        (529, error_body("overloaded_error", "Overloaded"), {}, AiFailure.PROVIDER_DOWN),
        (500, error_body("api_error", "oops"), {}, AiFailure.PROVIDER_DOWN),
        (400, error_body("invalid_request_error", "tools: bad"), {}, AiFailure.REJECTED),
    ],
)
@respx.mock
async def test_each_error_answer_maps_to_its_reason(
    status: int, body: dict[str, Any], headers: dict[str, str], failure: AiFailure
) -> None:
    respx.post(OFFICIAL).mock(return_value=httpx.Response(status, json=body, headers=headers))

    with pytest.raises(AiProviderError) as caught:
        await collect(official())

    assert caught.value.failure is failure
    assert body["error"]["message"] in caught.value.detail
    assert caught.value.retry_after == (7.0 if headers else None)
    assert KEY not in caught.value.detail


@respx.mock
async def test_a_404_that_is_not_an_anthropic_answer_is_not_a_missing_model() -> None:
    """base URL 多寫了 `/v1`：`/v1/v1/messages` 的 404 是網址錯，不能叫人去換模型。"""
    respx.post("https://proxy.example/v1/v1/messages").mock(
        return_value=httpx.Response(404, text="404 page not found")
    )

    with pytest.raises(AiProviderError) as caught:
        await collect(custom("https://proxy.example/v1", key=KEY))

    assert caught.value.failure is AiFailure.REJECTED
    assert "404 page not found" in caught.value.detail


@respx.mock
async def test_a_refused_connection_is_unreachable() -> None:
    respx.post(OFFICIAL).mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(AiProviderError) as caught:
        await collect(official())

    assert caught.value.failure is AiFailure.UNREACHABLE


@respx.mock
async def test_an_error_event_after_200_is_the_provider_going_down() -> None:
    """200 之後的 SSE `event: error`（A §3.7）：已經收到的 usage 照樣帶著，輸出還不知道。"""
    respx.post(OFFICIAL).mock(
        return_value=sse(
            message_start(cache_read_input_tokens=0),
            *text_block(0, "o"),
            ("error", error_body("overloaded_error", "Overloaded")),
        )
    )

    with pytest.raises(AiProviderError) as caught:
        await collect(official())

    assert caught.value.failure is AiFailure.PROVIDER_DOWN
    assert caught.value.usage == Usage(
        input_tokens=12, output_tokens=None, cache_write_tokens=None, cache_read_tokens=0
    )


@respx.mock
async def test_a_stream_that_stops_before_message_stop_is_an_error() -> None:
    respx.post(OFFICIAL).mock(return_value=sse(message_start(), *text_block(0, "o")))

    with pytest.raises(AiProviderError) as caught:
        await collect(official())

    assert caught.value.failure is AiFailure.PROVIDER_DOWN
    assert caught.value.usage.input_tokens == 12


@respx.mock
async def test_models_are_listed_from_the_endpoint() -> None:
    route = respx.get("https://api.anthropic.com/v1/models").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"id": "claude-opus-5-5", "type": "model", "max_input_tokens": 1_000_000},
                    {"id": "claude-haiku-5-5"},
                ],
                "has_more": False,
            },
        )
    )

    # 沒說 context window 的是不知道（壓縮時用設定或保守預設，plan §11.6〈上下文管理〉）。
    assert await official().list_models() == [
        ModelInfo("claude-opus-5-5", context_window=1_000_000),
        ModelInfo("claude-haiku-5-5", context_window=None),
    ]
    assert route.calls.last.request.url.params["limit"] == "1000"


@pytest.mark.parametrize(
    "answer",
    [
        httpx.Response(404, text="nope"),
        httpx.Response(200, text="<html>"),
        httpx.Response(200, json={}),
    ],
)
@respx.mock
async def test_an_endpoint_without_a_model_list_falls_back_to_typing(
    answer: httpx.Response,
) -> None:
    respx.get("http://ollama.lan:11434/v1/models").mock(return_value=answer)

    assert await custom("http://ollama.lan:11434").list_models() is None


@respx.mock
async def test_listing_models_with_a_bad_key_says_so() -> None:
    respx.get("https://api.anthropic.com/v1/models").mock(
        return_value=httpx.Response(401, json=error_body("authentication_error", "invalid"))
    )

    with pytest.raises(AiProviderError) as caught:
        await official().list_models()

    assert caught.value.failure is AiFailure.AUTH_FAILED
