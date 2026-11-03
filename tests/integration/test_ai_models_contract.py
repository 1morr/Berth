"""「取得模型」adapter 對模型清單端點的契約（M5.5 票 02、brief §20.26）。

`tests/fixtures/http/ai_models/` 的每一份是 `{status, headers, body}`，來源在
`tests/fixtures/http/README.md`：`deepseek*` 是 `scripts/experiments/ai_models.py` 2026-11-04 帶 key
錄的；`anthropic.page-*`、`openai.ok` 照官方文件的範例（**未實測**，沒有那兩家的 key）。
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from berth.adapters.ai.catalog import ANTHROPIC_VERSION, HttpModelCatalog, ModelListing
from berth.domain import AiProbeFailure, AiProvider
from tests.conftest import read_fixture

pytestmark = pytest.mark.asyncio

KEY = "sk-contract-test-key"
DEEPSEEK = "https://api.deepseek.com"
DEEPSEEK_ANTHROPIC = "https://api.deepseek.com/anthropic"


def recorded(name: str) -> httpx.Response:
    record: dict[str, Any] = json.loads(read_fixture(f"http/ai_models/{name}.json"))
    body = record["body"]
    if body is None:
        return httpx.Response(record["status"], content=b"", headers=record["headers"])
    if isinstance(body, str):
        return httpx.Response(record["status"], text=body, headers=record["headers"])
    return httpx.Response(record["status"], json=body, headers=record["headers"])


async def listing(provider: AiProvider, base_url: str) -> ModelListing:
    return await HttpModelCatalog(provider, base_url, KEY).list_models()


@respx.mock
async def test_anthropic_collects_every_page() -> None:
    route = respx.get(f"{DEEPSEEK_ANTHROPIC}/v1/models").mock(
        side_effect=[recorded("anthropic.page-1"), recorded("anthropic.page-2")]
    )

    got = await listing(AiProvider.ANTHROPIC, DEEPSEEK_ANTHROPIC)

    assert got == ModelListing(
        ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"), None, None, ""
    )
    first, second = (call.request for call in route.calls)
    assert first.headers["x-api-key"] == KEY
    assert first.headers["anthropic-version"] == ANTHROPIC_VERSION
    assert "authorization" not in first.headers
    assert dict(first.url.params) == {"limit": "1000"}
    assert dict(second.url.params) == {"limit": "1000", "after_id": "claude-sonnet-5-5"}


@respx.mock
async def test_anthropic_stops_when_the_service_keeps_saying_there_is_more() -> None:
    """服務不理 `after_id`、一直回 `has_more: true`：問到上限就停，不無限問下去。"""
    route = respx.get(f"{DEEPSEEK_ANTHROPIC}/v1/models").mock(
        side_effect=lambda _: recorded("anthropic.page-1")
    )

    got = await listing(AiProvider.ANTHROPIC, DEEPSEEK_ANTHROPIC)

    assert got.models == ("claude-opus-5-5", "claude-sonnet-5-5")
    assert route.call_count == 10


@respx.mock
async def test_openai_compatible_asks_models_with_a_bearer_key() -> None:
    route = respx.get(f"{DEEPSEEK}/models").mock(return_value=recorded("deepseek.ok"))

    got = await listing(AiProvider.OPENAI, DEEPSEEK)

    assert got == ModelListing(("deepseek-flash", "deepseek-v4-pro"), None, None, "")
    assert route.calls.last.request.headers["Authorization"] == f"Bearer {KEY}"


@pytest.mark.parametrize(
    ("provider", "url", "fixture"),
    [
        (AiProvider.ANTHROPIC, "https://api.anthropic.com/v1/models", "anthropic.page-2"),
        (AiProvider.OPENAI, "https://api.openai.com/v1/models", "openai.ok"),
    ],
)
@respx.mock
async def test_a_blank_address_asks_the_official_endpoint(
    provider: AiProvider, url: str, fixture: str
) -> None:
    respx.get(url).mock(return_value=recorded(fixture))

    got = await listing(provider, "")

    assert got.failure is None
    assert got.models


@respx.mock
async def test_a_rejected_key_says_so_with_the_services_words() -> None:
    respx.get(f"{DEEPSEEK_ANTHROPIC}/v1/models").mock(
        return_value=recorded("anthropic.unauthorized")
    )

    got = await listing(AiProvider.ANTHROPIC, DEEPSEEK_ANTHROPIC)

    assert (got.models, got.failure, got.status) == ((), AiProbeFailure.KEY_REJECTED, 401)
    assert "invalid x-api-key" in got.detail


@pytest.mark.parametrize("fixture", ["deepseek-anthropic.x-api-key", "deepseek-anthropic.bearer"])
@respx.mock
async def test_deepseeks_anthropic_endpoint_has_no_model_list(fixture: str) -> None:
    """DeepSeek 的 Anthropic 相容端點帶對的 key 也是 404（兩種標頭都一樣，brief §20.26）：
    說的是「這個端點不提供模型清單」，不是 key 被拒。"""
    respx.get(f"{DEEPSEEK_ANTHROPIC}/v1/models").mock(return_value=recorded(fixture))

    got = await listing(AiProvider.ANTHROPIC, DEEPSEEK_ANTHROPIC)

    assert (got.models, got.failure, got.status) == ((), AiProbeFailure.NOT_FOUND, 404)


@pytest.mark.parametrize(
    ("provider", "base_url", "path", "fixture"),
    [
        (AiProvider.ANTHROPIC, DEEPSEEK_ANTHROPIC, "/v1/models", "deepseek-anthropic.unauthorized"),
        (AiProvider.OPENAI, DEEPSEEK, "/models", "deepseek.unauthorized"),
    ],
)
@respx.mock
async def test_deepseek_says_a_wrong_key_is_rejected(
    provider: AiProvider, base_url: str, path: str, fixture: str
) -> None:
    """key 錯時兩支都先回 401：認證在找路由之前。"""
    respx.get(f"{base_url}{path}").mock(return_value=recorded(fixture))

    got = await listing(provider, base_url)

    assert (got.failure, got.status) == (AiProbeFailure.KEY_REJECTED, 401)
    assert "Authentication Fails" in got.detail


@respx.mock
async def test_a_plain_text_refusal_is_kept_as_it_was_said() -> None:
    """DeepSeek 的 `/models` 不帶 key 時回純文字，不是 JSON（2026-11-03 不帶 key 探到的）。"""
    respx.get(f"{DEEPSEEK}/models").mock(
        return_value=httpx.Response(401, text="Authentication Fails (governor)")
    )

    got = await listing(AiProvider.OPENAI, DEEPSEEK)

    assert (got.failure, got.detail) == (
        AiProbeFailure.KEY_REJECTED,
        "Authentication Fails (governor)",
    )


@pytest.mark.parametrize(
    ("response", "failure"),
    [
        (httpx.Response(404, text="404 page not found"), AiProbeFailure.NOT_FOUND),
        (httpx.Response(405, text="Method Not Allowed"), AiProbeFailure.NOT_FOUND),
        (httpx.Response(501, text="Not Implemented"), AiProbeFailure.NOT_FOUND),
        (httpx.Response(403, json={"error": "forbidden"}), AiProbeFailure.KEY_REJECTED),
        (httpx.Response(429, json={"error": "rate limited"}), AiProbeFailure.SERVICE_ERROR),
        (httpx.Response(200, text="<html>gateway</html>"), AiProbeFailure.BAD_RESPONSE),
        (httpx.Response(200, json={"models": ["x"]}), AiProbeFailure.BAD_RESPONSE),
    ],
    ids=["404", "405", "501", "403", "429", "html", "other-json"],
)
@respx.mock
async def test_each_failure_is_classified(
    response: httpx.Response, failure: AiProbeFailure
) -> None:
    respx.get(f"{DEEPSEEK}/models").mock(return_value=response)

    got = await listing(AiProvider.OPENAI, DEEPSEEK)

    assert (got.models, got.failure) == ((), failure)


@respx.mock
async def test_an_unreachable_endpoint_is_said_to_be_unreachable() -> None:
    respx.get(f"{DEEPSEEK}/models").mock(side_effect=httpx.ConnectError("refused"))

    got = await listing(AiProvider.OPENAI, DEEPSEEK)

    assert (got.failure, got.status) == (AiProbeFailure.UNREACHABLE, None)


@respx.mock
async def test_a_redirect_is_not_followed_with_the_key() -> None:
    """`x-api-key` 是自訂標頭，httpx 轉到別的主機時照樣帶著：不跟，key 只送到填的那個端點。"""
    respx.get(f"{DEEPSEEK_ANTHROPIC}/v1/models").mock(
        return_value=httpx.Response(302, headers={"Location": "https://evil.example/v1/models"})
    )
    elsewhere = respx.get("https://evil.example/v1/models").mock(
        return_value=recorded("anthropic.page-2")
    )

    got = await listing(AiProvider.ANTHROPIC, DEEPSEEK_ANTHROPIC)

    assert not elsewhere.called
    assert (got.failure, got.status) == (AiProbeFailure.BAD_RESPONSE, 302)
