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
            "vendor": "Anthropic",
            "verified": None,
        }
        unknown = save(client, provider="openai", model="some-local-model").json()
        assert unknown["openai"]["price"] is None

    def test_the_price_follows_the_base_url(self, client: TestClient) -> None:
        # Anthropic 接口打 DeepSeek 的相容端點：照 DeepSeek 的價（M5 票 21b）。
        got = save(client, base_url="https://api.deepseek.com/anthropic", model="deepseek-flash")
        price = got.json()["anthropic"]["price"]
        assert price["source"]["vendor"] == "Deepseek"

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


class TestSavedKeyStaysOnItsEndpoint:
    """key 欄空著代表沿用存著的那把，但只在存它的那個網址上（M5.5 票 01）。

    打到一半的網址不該收到 key：改了 base URL 又沒貼新 key，測試與儲存都是 `key_missing`。
    """

    def test_testing_a_changed_address_sends_no_key(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        save(client, api_key=KEY, base_url="https://gw.example/anthropic")
        got = press_test(client, base_url="https://evil.example/anthropic")
        assert got.status_code == 422
        assert got.json()["detail"]["reason"] == "key_missing"
        assert factory.ai_.endpoints == []

    @pytest.mark.parametrize(
        ("saved_at", "tested_at"),
        [
            ("https://gw.example/anthropic", "https://gw.example/anthropic/v1/"),
            ("", "https://api.anthropic.com"),
            ("https://api.anthropic.com/v1", ""),
        ],
    )
    def test_testing_the_same_address_uses_the_saved_key(
        self, client: TestClient, factory: FakeClientFactory, saved_at: str, tested_at: str
    ) -> None:
        save(client, api_key=KEY, base_url=saved_at)
        assert press_test(client, base_url=tested_at).json()["ok"] is True
        assert factory.ai_.endpoints[-1].api_key == KEY

    @pytest.mark.parametrize("enabled", [True, False])
    def test_saving_a_changed_address_without_a_key_keeps_nothing(
        self, client: TestClient, enabled: bool
    ) -> None:
        """只守測試的話，先存再按就繞過去了：存的時候一樣拒絕，關著 AI 也一樣。"""
        save(client, api_key=KEY, base_url="https://gw.example/anthropic", enabled=True)
        before = client.get(BASE).json()
        got = save(
            client, base_url="https://evil.example/anthropic", model="other", enabled=enabled
        )
        assert got.status_code == 422
        assert got.json()["detail"]["reason"] == "key_missing"
        assert client.get(BASE).json() == before

    def test_saving_the_same_address_without_a_key_keeps_the_saved_one(
        self, client: TestClient
    ) -> None:
        save(client, api_key=KEY)
        got = save(client, base_url="https://api.anthropic.com/v1", enabled=True)
        assert got.status_code == 200, got.text
        assert got.json()["anthropic"]["has_key"] is True

    def test_a_new_address_with_a_new_key_is_saved(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        save(client, api_key=KEY, base_url="https://gw.example/anthropic")
        got = save(client, api_key=OTHER_KEY, base_url="https://api.deepseek.com/anthropic")
        assert got.status_code == 200, got.text
        press_test(client, base_url="https://api.deepseek.com/anthropic")
        assert factory.ai_.endpoints[-1].api_key == OTHER_KEY

    def test_a_new_address_is_fine_when_no_key_was_saved(self, client: TestClient) -> None:
        save(client, base_url="https://gw.example/anthropic")
        got = save(client, base_url="https://api.deepseek.com/anthropic")
        assert got.status_code == 200, got.text
        assert got.json()["anthropic"]["base_url"] == "https://api.deepseek.com/anthropic"


def suggest(client: TestClient, provider: str, base_url: str) -> httpx2.Response:
    response: httpx2.Response = client.get(
        f"{BASE}/models", params={"provider": provider, "base_url": base_url}
    )
    return response


def fetch_models(client: TestClient, **fields: object) -> httpx2.Response:
    body: dict[str, object] = {"provider": "anthropic", "base_url": ""}
    response: httpx2.Response = client.post(f"{BASE}/models", json=body | fields, headers=BROWSER)
    return response


class TestSuggestedModels:
    """沒按「取得模型」之前的建議（M5.5 票 02）：本機價目表照表單上的網址查，不帶 key、不連外。"""

    def test_the_suggestions_follow_the_typed_address_before_it_is_saved(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        save(client, provider="openai", api_key=OTHER_KEY, model="gpt-5.5")
        got = suggest(client, "openai", "https://api.deepseek.com")
        assert got.status_code == 200, got.text
        body = got.json()
        assert body["source"] == "prices"
        assert body["failure"] is None
        # 網址是 DeepSeek：建議的是 DeepSeek 的模型，不是 OpenAI 的，雖然存著的還是 OpenAI 官方。
        assert "deepseek-flash" in body["models"]
        assert "gpt-5.5" not in body["models"]
        assert factory.ai_.endpoints == []

    def test_the_official_address_suggests_that_providers_models(self, client: TestClient) -> None:
        models = suggest(client, "anthropic", "").json()["models"]
        assert "claude-sonnet-5-5" in models
        assert models == sorted(models)

    def test_a_half_typed_address_is_not_an_error(self, client: TestClient) -> None:
        """打到一半的網址只是認不出是哪一家，照接口種類建議；不連外，所以不用先驗。"""
        got = suggest(client, "anthropic", "https://api.deeps")
        assert got.status_code == 200, got.text
        assert "claude-sonnet-5-5" in got.json()["models"]


class TestFetchingModels:
    """按了「取得模型」才向表單上的端點問（M5.5 票 02、brief §20.26）。"""

    def test_the_models_come_from_the_endpoint_on_the_form(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        factory.ai_.listed = ("deepseek-flash", "deepseek-pro")
        got = fetch_models(
            client, provider="openai", base_url="https://api.deepseek.com", api_key=OTHER_KEY
        )
        assert got.status_code == 200, got.text
        assert got.json() == {
            "models": ["deepseek-flash", "deepseek-pro"],
            "source": "endpoint",
            "failure": None,
            "status": None,
            "detail": "",
        }
        endpoint = factory.ai_.endpoints[-1]
        assert endpoint.provider is AiProvider.OPENAI
        assert (endpoint.base_url, endpoint.api_key) == ("https://api.deepseek.com", OTHER_KEY)

    def test_nothing_is_saved(self, client: TestClient) -> None:
        fetch_models(client, base_url="https://gw.example/anthropic", api_key=KEY)
        assert client.get(BASE).json()["anthropic"] == {
            "base_url": "",
            "model": "",
            "has_key": False,
            "price": None,
        }

    def test_anthropic_loses_a_pasted_v1(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        fetch_models(client, base_url="https://api.deepseek.com/anthropic/v1/", api_key=KEY)
        assert factory.ai_.endpoints[-1].base_url == "https://api.deepseek.com/anthropic"

    def test_a_failure_falls_back_to_the_price_table_and_says_why(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        """問不到不是請求錯：200，照本機表建議，並帶服務回的原因。"""
        got = fetch_models(
            client, provider="openai", base_url="https://api.deepseek.com", api_key="wrong-key"
        )
        assert got.status_code == 200, got.text
        body = got.json()
        assert body["source"] == "prices"
        assert body["failure"] == "key_rejected"
        assert body["status"] == 401
        assert "invalid" in body["detail"]
        assert "deepseek-flash" in body["models"]

    def test_an_endpoint_that_lists_nothing_falls_back_without_a_failure(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        factory.ai_.listed = ()
        body = fetch_models(client, api_key=KEY).json()
        assert (body["source"], body["failure"]) == ("prices", None)
        assert "claude-sonnet-5-5" in body["models"]

    def test_a_service_echoing_the_key_does_not_carry_it_back(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        factory.ai_.rejected_keys = frozenset({KEY})
        factory.ai_.echo_key = True
        got = fetch_models(client, api_key=KEY)
        assert got.json()["failure"] == "key_rejected"
        assert KEY not in got.text

    def test_a_blank_key_uses_the_saved_one_on_the_same_address(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        save(client, api_key=KEY, base_url="https://gw.example/anthropic")
        got = fetch_models(client, base_url="https://gw.example/anthropic/v1")
        assert got.json()["source"] == "endpoint"
        assert factory.ai_.endpoints[-1].api_key == KEY

    def test_a_changed_address_with_a_blank_key_sends_no_key(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        """存著 key、改了 base URL、key 欄空著：`key_missing`，替身記不到帶舊 key 的請求。"""
        save(client, api_key=KEY, base_url="https://gw.example/anthropic")
        got = fetch_models(client, base_url="https://evil.example/anthropic", api_key="  ")
        assert got.status_code == 422
        assert got.json()["detail"]["reason"] == "key_missing"
        assert factory.ai_.endpoints == []

    def test_an_address_that_is_not_http_is_refused(self, client: TestClient) -> None:
        got = fetch_models(client, base_url="api.deepseek.com", api_key=KEY)
        assert got.status_code == 422
        assert got.json()["detail"]["reason"] == "base_url_invalid"


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
            fetch_models(client),
            suggest(client, "anthropic", ""),
        ]
        assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
        assert caplog.records, "DEBUG 什麼都沒抓到：這條測試量不到洩漏"
        for secret in (KEY, OTHER_KEY, TAVILY):
            assert [r.text for r in responses if secret in r.text] == []
            assert [json_line(r) for r in caplog.records if secret in json_line(r)] == []
