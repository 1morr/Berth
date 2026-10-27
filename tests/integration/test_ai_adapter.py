"""AI provider adapter（M5 票 09、brief §20.24 provider）：依設定組出模型、打一次最小呼叫。

不打網路：SDK 的 http client 換成 httpx2 的 `MockTransport`，斷言請求打到哪一條路徑、帶哪一把 key，
以及服務回什麼時 `probe` 怎麼分類。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

import httpx2
import pytest
from pydantic_ai.models import Model

from berth.adapters.ai import AiEndpoint, build_model, normalize_base_url, probe
from berth.domain import AiProbeFailure, AiProvider
from berth.logs import json_line

KEY = "sk-test-do-not-leak"

ANTHROPIC_OK = {
    "id": "msg_1",
    "type": "message",
    "role": "assistant",
    "model": "claude-sonnet-5-5",
    "content": [{"type": "text", "text": "OK"}],
    "stop_reason": "end_turn",
    "stop_sequence": None,
    "usage": {"input_tokens": 9, "output_tokens": 1},
}
OPENAI_OK = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "created": 0,
    "model": "deepseek-flash",
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}
    ],
    "usage": {"prompt_tokens": 9, "completion_tokens": 1, "total_tokens": 10},
}


class Recorder:
    """收下每一個請求，照 `answer` 回。"""

    def __init__(self, answer: Callable[[httpx2.Request], httpx2.Response]) -> None:
        self.requests: list[httpx2.Request] = []
        self._answer = answer

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return self._answer(request)

    def client(self) -> httpx2.AsyncClient:
        return httpx2.AsyncClient(transport=httpx2.MockTransport(self))


def answers(status: int, body: object) -> Recorder:
    return Recorder(lambda _: httpx2.Response(status, json=body))


def wired(endpoint: AiEndpoint, seen: Recorder) -> Model:
    return build_model(endpoint, http_client=seen.client())


def anthropic(base_url: str = "", model: str = "claude-sonnet-5-5") -> AiEndpoint:
    return AiEndpoint(AiProvider.ANTHROPIC, base_url=base_url, api_key=KEY, model=model)


def openai(base_url: str = "", model: str = "deepseek-flash") -> AiEndpoint:
    return AiEndpoint(AiProvider.OPENAI, base_url=base_url, api_key=KEY, model=model)


class TestBaseUrl:
    pytestmark = pytest.mark.asyncio

    async def test_anthropic_official_endpoint_when_left_blank(self) -> None:
        seen = answers(200, ANTHROPIC_OK)
        await probe(wired(anthropic(), seen))
        assert str(seen.requests[0].url) == "https://api.anthropic.com/v1/messages"
        # anthropic 2.x 把 `api_key` 放在 `Authorization: Bearer`，不是舊版的 `x-api-key`。
        assert seen.requests[0].headers["authorization"] == f"Bearer {KEY}"

    async def test_anthropic_gateway_gets_v1_messages_appended(self) -> None:
        seen = answers(200, ANTHROPIC_OK)
        endpoint = anthropic("https://api.deepseek.com/anthropic")
        await probe(wired(endpoint, seen))
        assert str(seen.requests[0].url) == "https://api.deepseek.com/anthropic/v1/messages"

    async def test_openai_official_endpoint_when_left_blank(self) -> None:
        seen = answers(200, OPENAI_OK)
        await probe(wired(openai(), seen))
        assert str(seen.requests[0].url) == "https://api.openai.com/v1/chat/completions"
        assert seen.requests[0].headers["authorization"] == f"Bearer {KEY}"

    async def test_openai_compatible_base_url_is_used_as_given(self) -> None:
        seen = answers(200, OPENAI_OK)
        await probe(wired(openai("https://api.deepseek.com"), seen))
        assert str(seen.requests[0].url) == "https://api.deepseek.com/chat/completions"
        assert json.loads(seen.requests[0].content)["model"] == "deepseek-flash"


class TestNormalize:
    @pytest.mark.parametrize(
        ("typed", "kept"),
        [
            ("https://api.anthropic.com/v1", "https://api.anthropic.com"),
            ("https://gw.example/anthropic/v1/", "https://gw.example/anthropic"),
            ("https://api.anthropic.com/", "https://api.anthropic.com"),
            ("  ", ""),
        ],
    )
    def test_anthropic_drops_a_trailing_v1(self, typed: str, kept: str) -> None:
        assert normalize_base_url(AiProvider.ANTHROPIC, typed) == kept

    def test_openai_keeps_its_v1(self) -> None:
        typed = "https://openrouter.ai/api/v1/"
        assert normalize_base_url(AiProvider.OPENAI, typed) == "https://openrouter.ai/api/v1"


class TestProbe:
    pytestmark = pytest.mark.asyncio

    async def test_it_tries_once(self) -> None:
        """測試連線要的是第一個回應怎麼說，SDK 的重試只會讓人多等。"""
        seen = answers(500, {"error": {"message": "down", "type": "server_error"}})
        await probe(wired(openai(), seen))
        assert len(seen.requests) == 1

    async def test_a_reply_is_success_with_the_model_that_answered(self) -> None:
        result = await probe(wired(anthropic(), answers(200, ANTHROPIC_OK)))
        assert result.failure is None
        assert result.model == "claude-sonnet-5-5"

    async def test_a_refused_key_is_said_with_the_service_text(self) -> None:
        body = {
            "type": "error",
            "error": {"type": "authentication_error", "message": "invalid x-api-key"},
        }
        result = await probe(wired(anthropic(), answers(401, body)))
        assert result.failure is AiProbeFailure.KEY_REJECTED
        assert result.status == 401
        assert "invalid x-api-key" in result.detail

    async def test_an_unknown_model_is_said_with_the_service_text(self) -> None:
        body = {
            "error": {"message": "Model Not Exist", "type": "invalid_request_error", "code": None}
        }
        result = await probe(wired(openai(model="nope"), answers(404, body)))
        assert result.failure is AiProbeFailure.NOT_FOUND
        assert "Model Not Exist" in result.detail

    async def test_a_server_error_is_said_with_its_status(self) -> None:
        body = {"error": {"message": "upstream exploded", "type": "server_error"}}
        result = await probe(wired(openai(), answers(500, body)))
        assert result.failure is AiProbeFailure.SERVICE_ERROR
        assert result.status == 500
        assert "upstream exploded" in result.detail

    async def test_no_connection_is_unreachable(self) -> None:
        def refuse(request: httpx2.Request) -> httpx2.Response:
            raise httpx2.ConnectError("connection refused", request=request)

        result = await probe(wired(anthropic(), Recorder(refuse)))
        assert result.failure is AiProbeFailure.UNREACHABLE
        assert result.status is None
        assert result.detail != ""

    async def test_a_page_that_is_not_the_api_is_a_bad_response(self) -> None:
        """base URL 指到一個網頁：200 但不是 API 的形狀。"""
        page = Recorder(lambda _: httpx2.Response(200, text="<html>hello</html>"))
        result = await probe(wired(openai("https://example.com"), page))
        assert result.failure is AiProbeFailure.BAD_RESPONSE
        assert result.detail != ""


class TestNoKeyInLogs:
    pytestmark = pytest.mark.asyncio

    async def test_the_sdks_debug_lines_do_not_carry_the_key(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """R13：兩家 SDK 與 httpx2 在 DEBUG 印請求與回應，key 不在其中。"""
        caplog.set_level(logging.DEBUG)
        await probe(wired(anthropic(), answers(401, {"error": {"message": "no"}})))
        await probe(wired(openai(), answers(200, OPENAI_OK)))
        assert caplog.records, "DEBUG 什麼都沒抓到：這條測試量不到洩漏"
        assert [json_line(r) for r in caplog.records if KEY in json_line(r)] == []
