"""通知設定的端點（M4 票 123）：存 token、填 Discord ID、按測試。

**bot token 只進不出**：這一份裡的每一個回應與這期間的每一行 log 都不可以帶著它
（`assert_no_token`，檔尾自己驗它真的抓得到洩漏）。
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from berth.adapters.http import ServiceUnavailableError
from berth.api.deps import get_client_factory
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.logs import configure_logging, json_line
from berth.main import create_app
from tests.integration.arrange import sign_in_owner
from tests.integration.factories import FakeClientFactory

BROWSER = {CSRF_HEADER: "XMLHttpRequest"}
TOKEN = "MTAwMDAwMDAwMDAwMDAwMDAx.secret-part.do-not-leak"
DISCORD_ID = "100000000000000001"
BASE = "/api/settings/notifications"
#: Berth 寫出去的等級：`configure_logging` 的預設值，讀它而不是抄一份。
LOGGED: int = inspect.signature(configure_logging).parameters["level"].default


@pytest.fixture
def factory() -> FakeClientFactory:
    return FakeClientFactory()


@pytest.fixture
def client(config: Config, tmp_path: Path, factory: FakeClientFactory) -> Iterator[TestClient]:
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app) as running:
        sign_in_owner(running)
        yield running


def leaks(
    token: str, responses: list[httpx.Response], records: list[logging.LogRecord]
) -> list[str]:
    """回應原文與 log（照 Berth 寫出去的 JSON 那一行，含 `extra`）裡帶著 token 的那幾處。"""
    found = [f"{r.request.method} {r.request.url.path}" for r in responses if token in r.text]
    found += [json_line(record) for record in records if token in json_line(record)]
    return found


def save_token(client: TestClient, token: str = TOKEN) -> httpx.Response:
    response: httpx.Response = client.put(f"{BASE}/bot", json={"token": token}, headers=BROWSER)
    return response


def save_id(
    client: TestClient, discord_id: str = DISCORD_ID, language: str = "zh-Hant"
) -> httpx.Response:
    response: httpx.Response = client.put(
        f"{BASE}/me", json={"discord_user_id": discord_id, "language": language}, headers=BROWSER
    )
    return response


def press_test(client: TestClient) -> httpx.Response:
    response: httpx.Response = client.post(f"{BASE}/test", headers=BROWSER)
    return response


class TestBotToken:
    def test_a_saved_token_comes_back_only_as_configured(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        saved = save_token(client)

        assert saved.status_code == 200
        assert saved.json() == {
            "bot_configured": True,
            "bot_name": "berth",
            "invite_url": (
                "https://discord.com/oauth2/authorize"
                "?client_id=1000000000000000001&scope=bot&permissions=0"
            ),
            "token_rejected": False,
            "discord_user_id": "",
            "language": "zh-Hant",
            "unreachable_at": None,
            "unreachable_detail": "",
        }
        assert factory.discord_.token == TOKEN
        assert client.get(BASE).json()["bot_configured"] is True

    def test_a_token_discord_refuses_is_not_kept(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        factory.discord_.rejected_tokens.add(TOKEN)

        refused = save_token(client)

        assert refused.status_code == 422
        assert refused.json()["detail"]["reason"] == "token_rejected"
        assert client.get(BASE).json()["bot_configured"] is False

    def test_discord_out_of_reach_is_said_and_nothing_is_kept(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        factory.discord_.identify_error = ServiceUnavailableError(
            "GET /applications/@me: connection refused"
        )

        refused = save_token(client)

        assert refused.status_code == 502
        assert refused.json()["detail"] == {
            "reason": "discord_unreachable",
            "detail": "GET /applications/@me: connection refused",
        }
        assert client.get(BASE).json()["bot_configured"] is False

    def test_an_empty_token_clears_the_bot(self, client: TestClient) -> None:
        save_token(client)

        cleared = save_token(client, "")

        assert cleared.json()["bot_configured"] is False
        assert cleared.json()["invite_url"] is None

    def test_the_token_is_in_no_response_and_no_log(
        self, client: TestClient, factory: FakeClientFactory, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Berth 寫出去的等級（`configure_logging` 的 root 是 INFO，沒有開關調低）。DEBUG 底下
        # aiosqlite 會印出 SQL 參數——整份設定的 JSON，每一種憑證都在裡面——那一行從來不寫出去。
        caplog.set_level(LOGGED)
        responses = [save_token(client), client.get(BASE), save_id(client), press_test(client)]
        factory.discord_.unreachable.add(DISCORD_ID)
        responses.append(press_test(client))
        factory.discord_.rejected_tokens.add(TOKEN)
        responses += [press_test(client), save_token(client)]

        assert all(r.status_code < 500 for r in responses)
        assert leaks(TOKEN, responses, caplog.records) == []


class TestDiscordId:
    def test_an_id_is_kept_with_the_language_it_was_saved_in(self, client: TestClient) -> None:
        saved = save_id(client, language="en")

        assert saved.status_code == 200
        assert (saved.json()["discord_user_id"], saved.json()["language"]) == (DISCORD_ID, "en")
        assert client.get(BASE).json()["discord_user_id"] == DISCORD_ID

    @pytest.mark.parametrize("wrong", ["skipper#0001", "12345", "1" * 21])
    def test_something_that_is_not_a_snowflake_is_refused(
        self, client: TestClient, wrong: str
    ) -> None:
        refused = save_id(client, wrong)

        assert refused.status_code == 422
        assert refused.json()["detail"]["reason"] == "discord_id_invalid"


class TestTestButton:
    def test_without_a_bot_there_is_nothing_to_send_with(self, client: TestClient) -> None:
        save_id(client)

        refused = press_test(client)

        assert refused.status_code == 409
        assert refused.json()["detail"]["reason"] == "bot_missing"

    def test_without_an_id_there_is_no_one_to_send_to(self, client: TestClient) -> None:
        save_token(client)

        refused = press_test(client)

        assert refused.status_code == 409
        assert refused.json()["detail"]["reason"] == "discord_id_missing"

    def test_a_test_message_reaches_whoever_pressed_it_in_their_language(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        save_token(client)
        save_id(client, language="en")

        result = press_test(client)

        assert result.json() == {
            "delivered": True,
            "failure": None,
            "detail": "",
            "retry_after": None,
        }
        ((recipient, message),) = factory.discord_.sent
        assert recipient == DISCORD_ID
        assert message.title == "Berth test message"

    def test_an_unreachable_recipient_is_said_on_the_spot(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        save_token(client)
        save_id(client)
        factory.discord_.unreachable.add(DISCORD_ID)

        result = press_test(client)

        assert result.status_code == 200
        assert result.json()["delivered"] is False
        assert result.json()["failure"] == "recipient_unreachable"
        assert "50278" in result.json()["detail"]

    def test_an_unreachable_recipient_stays_said_on_the_page_until_a_delivery(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        """M4 票 128：重新整理之後照樣說得出來，補好之後按一次測試就收掉。"""
        save_token(client)
        save_id(client)
        factory.discord_.unreachable.add(DISCORD_ID)
        press_test(client)

        page = client.get(BASE).json()
        assert page["unreachable_at"] is not None
        assert "50278" in page["unreachable_detail"]

        factory.discord_.unreachable.clear()
        press_test(client)
        assert client.get(BASE).json()["unreachable_at"] is None

    def test_a_token_reset_in_discord_is_said_after_the_test(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        save_token(client)
        save_id(client)
        assert client.get(BASE).json()["token_rejected"] is False
        factory.discord_.rejected_tokens.add(TOKEN)

        press_test(client)

        assert client.get(BASE).json()["token_rejected"] is True
        assert client.get("/api/health/detail").json()["notify"]["token_rejected"] is True


class TestTheLeakCheckItself:
    """`leaks` 自己的雙向變異：沒有這一段，上面那條可能只是在讀一個永遠是空的東西。"""

    def test_a_token_logged_once_is_caught(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(LOGGED)
        logging.getLogger("berth.services.notify").info("saved", extra={"token": TOKEN})

        assert leaks(TOKEN, [], caplog.records) != []

    def test_a_token_in_a_response_is_caught(self) -> None:
        request = httpx.Request("GET", f"http://berth{BASE}")
        response = httpx.Response(200, json={"token": TOKEN}, request=request)

        assert leaks(TOKEN, [response], []) == [f"GET {BASE}"]

    def test_unrelated_lines_are_not_caught(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(LOGGED)
        logging.getLogger("berth.services.notify").info("saved", extra={"bot": "berth"})
        request = httpx.Request("GET", f"http://berth{BASE}")
        response = httpx.Response(200, json={"bot_configured": True}, request=request)

        assert leaks(TOKEN, [response], caplog.records) == []
