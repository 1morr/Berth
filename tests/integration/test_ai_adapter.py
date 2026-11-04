"""AI provider adapter（M5 票 09、brief §20.24 provider）：依設定組出模型、打一次最小呼叫。

不打網路：SDK 的 http client 換成 httpx2 的 `MockTransport`，斷言請求打到哪一條路徑、帶哪一把 key，
以及服務回什麼時 `probe` 怎麼分類。
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import replace

import httpx2
import pytest
from pydantic_ai import ModelRequest
from pydantic_ai.direct import model_request
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models import Model

from berth.adapters.ai import (
    AiEndpoint,
    build_model,
    chat_settings,
    normalize_base_url,
    probe,
    reasoning_support,
    rejects_reasoning,
)
from berth.domain import AiProbeFailure, AiProvider, AiReasoning
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


def sent(endpoint: AiEndpoint, ok: object) -> dict[str, object]:
    """照側面板的設定打一次，回錄下的請求本體（M5.5 票 17：以錄下的請求為準）。"""
    seen = answers(200, ok)
    model = wired(endpoint, seen)

    async def call() -> None:
        await model_request(
            model,
            [ModelRequest.user_text_prompt("hi")],
            model_settings=chat_settings(endpoint, model, 4096),
        )

    asyncio.run(call())
    body: dict[str, object] = json.loads(seen.requests[0].content)
    return body


def reasoning_of(body: dict[str, object]) -> dict[str, object]:
    return {
        key: body[key] for key in ("thinking", "output_config", "reasoning_effort") if key in body
    }


class TestReasoning:
    """推理程度變成請求參數（M5.5 票 17、brief §20.26）。統一的 `thinking` 不夠：DeepSeek 的
    Anthropic 接口忽略 `budget_tokens`，要明寫 effort 與關。"""

    @pytest.mark.parametrize("level", [AiReasoning.LOW, AiReasoning.MEDIUM, AiReasoning.HIGH])
    def test_deepseek_on_anthropic_gets_the_effort_spelled_out(self, level: AiReasoning) -> None:
        endpoint = replace(
            anthropic("https://api.deepseek.com/anthropic", "deepseek-flash"), reasoning=level
        )
        assert reasoning_of(sent(endpoint, ANTHROPIC_OK)) == {
            "output_config": {"effort": level.value}
        }

    def test_deepseek_on_anthropic_is_turned_off_explicitly(self) -> None:
        """不送 `thinking` 的話 DeepSeek 照樣思考（brief §20.26 實測）。"""
        endpoint = replace(
            anthropic("https://api.deepseek.com/anthropic", "deepseek-flash"),
            reasoning=AiReasoning.OFF,
        )
        assert reasoning_of(sent(endpoint, ANTHROPIC_OK)) == {"thinking": {"type": "disabled"}}

    def test_an_unknown_gateway_gets_nothing_when_off(self) -> None:
        """認不得 `thinking` / `output_config` 的相容閘道會 400，設定頁又沒有「不送」一級：
        「關」就是不送（M5.5 票 17b，使用者定）。"""
        endpoint = replace(
            anthropic("https://llm.example.net/anthropic", "glm-4.6"), reasoning=AiReasoning.OFF
        )
        assert reasoning_of(sent(endpoint, ANTHROPIC_OK)) == {}

    @pytest.mark.parametrize("level", [AiReasoning.LOW, AiReasoning.MEDIUM, AiReasoning.HIGH])
    def test_an_unknown_gateway_still_gets_the_effort(self, level: AiReasoning) -> None:
        endpoint = replace(
            anthropic("https://llm.example.net/anthropic", "glm-4.6"), reasoning=level
        )
        assert reasoning_of(sent(endpoint, ANTHROPIC_OK)) == {
            "output_config": {"effort": level.value}
        }

    def test_deepseek_behind_another_host_is_an_unknown_gateway(self) -> None:
        """收不收參數是端點的事，不是模型名的事：轉送 DeepSeek 模型的閘道照樣認不得。"""
        endpoint = replace(
            anthropic("https://llm.example.net/anthropic", "deepseek-flash"),
            reasoning=AiReasoning.OFF,
        )
        assert reasoning_of(sent(endpoint, ANTHROPIC_OK)) == {}

    def test_claude_uses_the_unified_setting(self) -> None:
        endpoint = replace(anthropic(model="claude-sonnet-5-5"), reasoning=AiReasoning.HIGH)
        assert reasoning_of(sent(endpoint, ANTHROPIC_OK)) == {
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": "high"},
        }

    def test_claude_off_thinks_only_between_tools(self) -> None:
        """Sonnet 5.5 關不掉思考，pydantic-ai 換成它最少的一種。"""
        endpoint = replace(anthropic(model="claude-sonnet-5-5"), reasoning=AiReasoning.OFF)
        assert reasoning_of(sent(endpoint, ANTHROPIC_OK)) == {"thinking": {"type": "between_tools"}}

    @pytest.mark.parametrize("level", list(AiReasoning))
    @pytest.mark.parametrize("name", ["claude-haiku-4-5", "claude-opus-4-1"])
    def test_a_claude_without_effort_gets_nothing(self, name: str, level: AiReasoning) -> None:
        """官方不收 `output_config.effort`，統一設定的 `budget_tokens` 又大過每次的 `max_tokens`：
        不送，與升級前一樣（code-review 追加）。"""
        endpoint = replace(anthropic(model=name), reasoning=level)
        assert reasoning_of(sent(endpoint, ANTHROPIC_OK)) == {}
        assert reasoning_support(AiProvider.ANTHROPIC, "", name).applies is False

    def test_sonnet_4_5_has_no_effort_either(self) -> None:
        """不錄請求：SDK 對這個模型發棄用警告。"""
        assert reasoning_support(AiProvider.ANTHROPIC, "", "claude-sonnet-4-5").applies is False

    def test_a_compatible_endpoint_always_gets_it(self) -> None:
        assert reasoning_support(AiProvider.ANTHROPIC, "", "deepseek-flash").applies is True
        assert reasoning_support(AiProvider.ANTHROPIC, "", "glm-4.6").applies is True
        assert reasoning_support(AiProvider.ANTHROPIC, "", "claude-sonnet-5-5").applies is True

    @pytest.mark.parametrize(
        ("base_url", "model", "off_sends_nothing"),
        [
            ("https://llm.example.net/anthropic", "glm-4.6", True),
            ("https://llm.example.net/anthropic", "deepseek-flash", True),
            ("https://api.deepseek.com/anthropic", "deepseek-flash", False),
            ("", "claude-sonnet-5-5", False),
            ("", "claude-haiku-4-5", False),
        ],
    )
    def test_off_sends_nothing_only_on_an_unknown_gateway(
        self, base_url: str, model: str, off_sends_nothing: bool
    ) -> None:
        """設定頁與停下的說明照它說「選關就不送」（M5.5 票 17b）。"""
        support = reasoning_support(AiProvider.ANTHROPIC, base_url, model)
        assert support.off_sends_nothing is off_sends_nothing

    def test_off_sends_nothing_is_never_said_on_openai(self) -> None:
        assert reasoning_support(AiProvider.OPENAI, "", "gpt-5.5").off_sends_nothing is False
        assert reasoning_support(AiProvider.OPENAI, "", "glm-4.6").off_sends_nothing is False

    @pytest.mark.parametrize("level", list(AiReasoning))
    @pytest.mark.parametrize("name", ["deepseek-flash", "gpt-4o-mini", "some-local-model"])
    def test_an_openai_model_it_does_not_know_gets_nothing(
        self, name: str, level: AiReasoning
    ) -> None:
        endpoint = replace(openai("https://api.deepseek.com", name), reasoning=level)
        assert reasoning_of(sent(endpoint, OPENAI_OK)) == {}
        assert reasoning_support(AiProvider.OPENAI, "", name).applies is False

    @pytest.mark.parametrize(
        ("level", "effort"),
        [
            (AiReasoning.OFF, "none"),
            (AiReasoning.LOW, "low"),
            (AiReasoning.MEDIUM, "medium"),
            (AiReasoning.HIGH, "high"),
        ],
    )
    def test_an_openai_reasoning_model_gets_its_effort(
        self, level: AiReasoning, effort: str
    ) -> None:
        endpoint = replace(openai(model="gpt-5.5"), reasoning=level)
        assert reasoning_of(sent(endpoint, OPENAI_OK)) == {"reasoning_effort": effort}
        assert reasoning_support(AiProvider.OPENAI, "", "gpt-5.5").applies is True

    def test_the_level_is_medium_unless_set(self) -> None:
        assert anthropic().reasoning is AiReasoning.MEDIUM


class TestRejectsReasoning:
    """服務拒絕推理參數的判斷（M5.5 票 17）：只看 400 的 body。"""

    def test_a_400_about_the_effort_is_a_rejection(self) -> None:
        body = {"error": {"message": "output_config.effort: Extra inputs are not permitted"}}
        assert rejects_reasoning(str(ModelHTTPError(400, "claude-3-5-haiku-latest", body)))

    def test_the_model_name_alone_does_not_count(self) -> None:
        body = {"error": {"message": "prompt is too long"}}
        assert not rejects_reasoning(str(ModelHTTPError(400, "deepseek-reasoner", body)))

    @pytest.mark.parametrize(
        "message",
        [
            "messages.1.content.0.thinking: Invalid `signature` in `thinking` block",
            "The `reasoning_content` in the thinking mode must be passed back to the API.",
        ],
    )
    def test_a_400_about_replayed_thinking_is_not(self, message: str) -> None:
        """重播推理內容的 400 改程度沒有用。"""
        body = {"error": {"message": message}}
        assert not rejects_reasoning(str(ModelHTTPError(400, "deepseek-flash", body)))

    @pytest.mark.parametrize(
        "message",
        [
            "thinking.type: Input tag 'disabled' does not match any of the expected tags",
            "Unsupported parameter: 'reasoning_effort' is not supported with this model.",
            "thinking.budget_tokens: must be less than max_tokens",
        ],
    )
    def test_a_400_about_the_parameters_is(self, message: str) -> None:
        body = {"error": {"message": message}}
        assert rejects_reasoning(str(ModelHTTPError(400, "some-model", body)))

    def test_only_a_400_counts(self) -> None:
        body = {"error": {"message": "reasoning backend overloaded"}}
        assert not rejects_reasoning(str(ModelHTTPError(529, "deepseek-flash", body)))
