"""AI 設定的端點（M5 票 09）：兩種接口各自的 base URL、key、模型，開關，與「測試連線」。

**key 只進不出**：每一個回應、以及 DEBUG 等級下這期間的每一行 log 都不可以帶著它（R13：
aiosqlite 在 DEBUG 會印出 SQL 參數，那就是整份 `settings.ai` 的 JSON）。
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import httpx2
import pytest
from fastapi.testclient import TestClient

from berth.adapters.ai.fake import FakeAi
from berth.api.deps import get_client_factory
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.domain import AiProvider
from berth.logs import json_line
from berth.main import create_app
from tests.integration.arrange import sign_in_owner
from tests.integration.factories import FakeClientFactory

BROWSER = {CSRF_HEADER: "XMLHttpRequest"}
BASE = "/api/settings/ai"
KEY = "sk-ant-api03-secret-part-do-not-leak"
OTHER_KEY = "sk-openai-another-secret-do-not-leak"
TAVILY = "tvly-secret-do-not-leak"


@pytest.fixture
def factory() -> FakeClientFactory:
    return FakeClientFactory(ai=FakeAi(rejected_keys=frozenset({"wrong-key"})))


@pytest.fixture
def client(config: Config, tmp_path: Path, factory: FakeClientFactory) -> Iterator[TestClient]:
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app) as running:
        sign_in_owner(running)
        yield running


def save(client: TestClient, **fields: object) -> httpx2.Response:
    body: dict[str, object] = {
        "enabled": False,
        "provider": "anthropic",
        "base_url": "",
        "model": "claude-sonnet-5-5",
    }
    response: httpx2.Response = client.put(BASE, json=body | fields, headers=BROWSER)
    return response


def press_test(client: TestClient, **fields: object) -> httpx2.Response:
    body: dict[str, object] = {
        "provider": "anthropic",
        "base_url": "",
        "model": "claude-sonnet-5-5",
    }
    response: httpx2.Response = client.post(f"{BASE}/test", json=body | fields, headers=BROWSER)
    return response


class TestSaving:
    def test_nothing_is_set_up_at_first_and_ai_is_off(self, client: TestClient) -> None:
        got = client.get(BASE).json()
        assert got["enabled"] is False
        anthropic = got["anthropic"]
        assert (anthropic["base_url"], anthropic["model"], anthropic["has_key"]) == ("", "", False)
        assert anthropic["price"] is None
        assert got["has_tavily_key"] is False

    def test_a_saved_key_comes_back_only_as_has_key(self, client: TestClient) -> None:
        got = save(client, api_key=KEY, enabled=True)
        assert got.status_code == 200, got.text
        assert got.json()["enabled"] is True
        assert got.json()["anthropic"]["has_key"] is True
        assert KEY not in got.text
        assert KEY not in client.get(BASE).text

    def test_leaving_the_key_out_keeps_the_saved_one(self, client: TestClient) -> None:
        save(client, api_key=KEY)
        assert save(client, model="claude-haiku-5-5").json()["anthropic"]["has_key"] is True

    def test_a_blank_key_keeps_the_saved_one(self, client: TestClient) -> None:
        """空欄就是沒動（同測試連線）；清掉 key 是另一個命令。"""
        save(client, api_key=KEY)
        assert save(client, api_key="  ").json()["anthropic"]["has_key"] is True

    def test_each_provider_keeps_its_own_settings(self, client: TestClient) -> None:
        save(client, api_key=KEY, base_url="https://gw.example/anthropic")
        got = save(
            client,
            provider="openai",
            api_key=OTHER_KEY,
            base_url="https://api.deepseek.com",
            model="deepseek-flash",
        ).json()
        assert got["provider"] == "openai"
        assert got["openai"]["base_url"] == "https://api.deepseek.com"
        assert got["anthropic"] == {
            "base_url": "https://gw.example/anthropic",
            "model": "claude-sonnet-5-5",
            "has_key": True,
            "price": got["anthropic"]["price"],
            "known_models": got["anthropic"]["known_models"],
        }

    def test_anthropic_loses_a_pasted_v1(self, client: TestClient) -> None:
        got = save(client, base_url="https://api.anthropic.com/v1/")
        assert got.json()["anthropic"]["base_url"] == "https://api.anthropic.com"

    def test_an_address_that_is_not_http_is_refused_and_not_kept(self, client: TestClient) -> None:
        got = save(client, base_url="api.deepseek.com")
        assert got.status_code == 422
        assert got.json()["detail"]["reason"] == "base_url_invalid"
        assert client.get(BASE).json()["anthropic"]["model"] == ""

    def test_turning_on_without_a_key_is_refused(self, client: TestClient) -> None:
        got = save(client, enabled=True)
        assert got.status_code == 422
        assert got.json()["detail"]["reason"] == "key_missing"
        assert client.get(BASE).json()["enabled"] is False

    def test_turning_on_without_a_model_is_refused(self, client: TestClient) -> None:
        got = save(client, enabled=True, api_key=KEY, model=" ")
        assert got.status_code == 422
        assert got.json()["detail"]["reason"] == "model_missing"

    def test_turning_off_needs_nothing(self, client: TestClient) -> None:
        save(client, enabled=True, api_key=KEY)
        assert save(client, enabled=False, model="").json()["enabled"] is False

    def test_a_known_model_shows_its_price_and_an_unknown_one_has_none(
        self, client: TestClient
    ) -> None:
        price = save(client).json()["anthropic"]["price"]
        assert price["input"] == "2"
        assert price["output"] == "10"
        assert price["source"] == {
            "table": "genai_prices",
            "version": "0.1.13",
            "provider": "Anthropic",
            "verified": None,
        }
        unknown = save(client, provider="openai", model="some-local-model").json()
        assert unknown["openai"]["price"] is None

    def test_the_price_follows_the_base_url(self, client: TestClient) -> None:
        # Anthropic 接口打 DeepSeek 的相容端點：照 DeepSeek 的價（M5 票 21b）。
        got = save(client, base_url="https://api.deepseek.com/anthropic", model="deepseek-flash")
        price = got.json()["anthropic"]["price"]
        assert price["source"]["provider"] == "Deepseek"

    def test_the_models_with_a_price_are_offered_as_suggestions(self, client: TestClient) -> None:
        save(client, provider="openai", base_url="https://api.deepseek.com", model="deepseek-flash")
        got = client.get(BASE).json()
        anthropic, openai = got["anthropic"]["known_models"], got["openai"]["known_models"]
        assert "claude-sonnet-5-5" in anthropic
        assert anthropic == sorted(anthropic)
        # 端點是 DeepSeek：建議的是 DeepSeek 的模型，不是 OpenAI 的。
        assert "deepseek-flash" in openai
        assert "gpt-5.5" not in openai

    def test_the_tavily_key_is_write_only_too(self, client: TestClient) -> None:
        got = save(client, tavily_api_key=TAVILY)
        assert got.json()["has_tavily_key"] is True
        assert TAVILY not in got.text
        assert save(client, tavily_api_key="").json()["has_tavily_key"] is True

    def test_it_is_behind_the_admin_gate(self, config: Config, tmp_path: Path) -> None:
        app = create_app(replace(config, web_root=tmp_path / "never-built"))
        with TestClient(app) as anonymous:
            assert anonymous.get(BASE).status_code == 401


def forget(client: TestClient, which: str) -> httpx2.Response:
    response: httpx2.Response = client.delete(f"{BASE}/keys/{which}", headers=BROWSER)
    return response


class TestForgettingAKey:
    def test_a_provider_key_is_forgotten_and_the_rest_stays(self, client: TestClient) -> None:
        save(client, api_key=KEY, base_url="https://gw.example/anthropic")
        got = forget(client, "anthropic")
        assert got.status_code == 200, got.text
        assert got.json()["anthropic"]["has_key"] is False
        assert got.json()["anthropic"]["base_url"] == "https://gw.example/anthropic"

    def test_forgetting_the_key_in_use_turns_ai_off(self, client: TestClient) -> None:
        save(client, api_key=KEY, enabled=True)
        assert forget(client, "anthropic").json()["enabled"] is False

    def test_forgetting_the_other_providers_key_leaves_ai_on(self, client: TestClient) -> None:
        save(client, provider="openai", api_key=OTHER_KEY, model="deepseek-flash")
        save(client, api_key=KEY, enabled=True)
        got = forget(client, "openai").json()
        assert got["enabled"] is True
        assert got["provider"] == "anthropic"
        assert got["openai"]["has_key"] is False

    def test_the_tavily_key_is_forgotten(self, client: TestClient) -> None:
        save(client, tavily_api_key=TAVILY)
        assert forget(client, "tavily").json()["has_tavily_key"] is False

    def test_something_else_is_not_a_key(self, client: TestClient) -> None:
        assert forget(client, "jellyfin").status_code == 422


class TestConnectionTest:
    def test_success_says_which_model_answered(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        got = press_test(client, api_key=KEY, base_url="https://gw.example/anthropic/v1")
        assert got.status_code == 200, got.text
        assert got.json() == {
            "ok": True,
            "failure": None,
            "status": None,
            "detail": "",
            "model": "claude-sonnet-5-5",
        }
        endpoint = factory.ai_.endpoints[-1]
        assert endpoint.provider is AiProvider.ANTHROPIC
        assert endpoint.base_url == "https://gw.example/anthropic"

    def test_a_refused_key_is_said_with_the_service_text(self, client: TestClient) -> None:
        got = press_test(client, api_key="wrong-key").json()
        assert got["ok"] is False
        assert got["failure"] == "key_rejected"
        assert got["status"] == 401
        assert "invalid x-api-key" in got["detail"]

    def test_the_form_is_tested_without_saving_it(self, client: TestClient) -> None:
        press_test(client, api_key=KEY, model="claude-opus-5-5")
        assert client.get(BASE).json()["anthropic"]["has_key"] is False

    def test_a_blank_key_uses_the_saved_one_for_that_provider(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        save(client, api_key=KEY)
        save(client, provider="openai", api_key=OTHER_KEY, model="deepseek-flash")
        assert press_test(client).json()["ok"] is True
        assert factory.ai_.endpoints[-1].api_key == KEY

    def test_without_any_key_there_is_nothing_to_test_with(self, client: TestClient) -> None:
        got = press_test(client)
        assert got.status_code == 422
        assert got.json()["detail"]["reason"] == "key_missing"

    def test_without_a_model_there_is_nothing_to_ask(self, client: TestClient) -> None:
        got = press_test(client, api_key=KEY, model="")
        assert got.json()["detail"]["reason"] == "model_missing"

    def test_a_service_echoing_the_key_does_not_carry_it_back(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        """有的服務在錯誤訊息裡原樣回貼 key。原文要給人看，但 key 那一段要遮掉。"""
        factory.ai_.rejected_keys = frozenset({KEY})
        factory.ai_.echo_key = True
        got = press_test(client, api_key=KEY)
        assert got.json()["failure"] == "key_rejected"
        assert KEY not in got.text


class TestNoKeyInLogs:
    def test_keys_are_in_no_response_and_no_debug_log(
        self, client: TestClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG)
        responses = [
            save(client, api_key=KEY, enabled=True, tavily_api_key=TAVILY),
            save(client, provider="openai", api_key=OTHER_KEY, model="deepseek-flash"),
            client.get(BASE),
            press_test(client),
            press_test(client, api_key="wrong-key"),
        ]
        assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
        assert caplog.records, "DEBUG 什麼都沒抓到：這條測試量不到洩漏"
        for secret in (KEY, OTHER_KEY, TAVILY):
            assert [r.text for r in responses if secret in r.text] == []
            assert [json_line(r) for r in caplog.records if secret in json_line(r)] == []
