"""通知設定的端點（M4 票 123、125）：管理員存 token；每個人填自己的 Discord ID、勾種類、按測試。

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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.jellyfin import JellyfinAuth
from berth.api.deps import get_client_factory
from berth.api.gate import CSRF_HEADER, SESSION_COOKIE
from berth.config import Config
from berth.logs import configure_logging, json_line
from berth.main import create_app
from berth.services.auth import open_session
from tests.integration.arrange import sign_in_owner
from tests.integration.factories import FakeClientFactory

BROWSER = {CSRF_HEADER: "XMLHttpRequest"}
TOKEN = "MTAwMDAwMDAwMDAwMDAwMDAx.secret-part.do-not-leak"
DISCORD_ID = "100000000000000001"
BASE = "/api/settings/notifications"
MINE = "/api/me/notifications"
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
    client: TestClient,
    discord_id: str = DISCORD_ID,
    language: str = "zh-Hant",
    kinds: tuple[str, ...] = ("ready",),
) -> httpx.Response:
    response: httpx.Response = client.put(
        MINE,
        json={"discord_user_id": discord_id, "language": language, "kinds": list(kinds)},
        headers=BROWSER,
    )
    return response


def sign_in_crew(client: TestClient, name: str = "deckhand") -> None:
    """換成一位 `user` 角色的人登入（擁有者已經在 `client` fixture 成立）。"""

    async def seat() -> str:
        sessions: async_sessionmaker[AsyncSession] = client.app.state.session_factory  # type: ignore[attr-defined]  # Starlette 的 app 型別是 ASGIApp
        async with sessions() as session:
            auth = JellyfinAuth(
                token="", user_id=f"id-{name}", name=name, server_id="", is_administrator=False
            )
            return (await open_session(session, auth)).token

    assert client.portal is not None
    client.cookies.set(SESSION_COOKIE, client.portal.call(seat))


def save_berth_url(client: TestClient, url: str) -> httpx.Response:
    response: httpx.Response = client.put(
        f"{BASE}/berth-url", json={"berth_url": url}, headers=BROWSER
    )
    return response


def press_test(client: TestClient) -> httpx.Response:
    response: httpx.Response = client.post(f"{MINE}/test", headers=BROWSER)
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
            "berth_url": "",
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
        responses = [
            save_token(client),
            client.get(BASE),
            save_id(client),
            client.get(MINE),
            press_test(client),
        ]
        factory.discord_.unreachable.add(DISCORD_ID)
        responses.append(press_test(client))
        factory.discord_.rejected_tokens.add(TOKEN)
        responses += [press_test(client), save_token(client)]

        assert all(r.status_code < 500 for r in responses)
        assert leaks(TOKEN, responses, caplog.records) == []


class TestMine:
    def test_an_id_is_kept_with_the_language_it_was_saved_in(self, client: TestClient) -> None:
        saved = save_id(client, language="en")

        assert saved.status_code == 200
        assert (saved.json()["discord_user_id"], saved.json()["language"]) == (DISCORD_ID, "en")
        assert client.get(MINE).json()["discord_user_id"] == DISCORD_ID

    @pytest.mark.parametrize("wrong", ["skipper#0001", "12345", "1" * 21])
    def test_something_that_is_not_a_snowflake_is_refused(
        self, client: TestClient, wrong: str
    ) -> None:
        refused = save_id(client, wrong)

        assert refused.status_code == 422
        assert refused.json()["detail"]["reason"] == "discord_id_invalid"

    def test_ready_is_subscribed_before_anything_is_saved(self, client: TestClient) -> None:
        """填了 Discord ID 就收得到最主要的那一種；「正在下載」要自己勾。管理員多「等你處理」
        （M4 票 127）。"""
        assert client.get(MINE).json()["kinds"] == ["ready", "waiting"]

    def test_an_admin_can_turn_waiting_off(self, client: TestClient) -> None:
        assert save_id(client, kinds=("ready",)).json()["kinds"] == ["ready"]
        assert save_id(client, kinds=("waiting",)).json()["kinds"] == ["waiting"]

    def test_the_chosen_kinds_are_kept(self, client: TestClient) -> None:
        save_id(client, kinds=("downloading", "ready"))
        assert client.get(MINE).json()["kinds"] == ["ready", "downloading"]

        save_id(client, kinds=())
        assert client.get(MINE).json()["kinds"] == []

    def test_a_kind_that_does_not_exist_is_refused(self, client: TestClient) -> None:
        assert save_id(client, kinds=("weekly-gossip",)).status_code == 422


class TestCrew:
    """一般使用者（`user` 角色）：自己的那一半看得到、改得了、測得了；bot 那一半一個字都碰不到
    （M4 票 125）。"""

    def test_a_crew_member_sets_up_their_own_discord(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        save_token(client)
        sign_in_crew(client)

        page = client.get(MINE)
        assert page.status_code == 200
        assert page.json()["bot_configured"] is True
        assert page.json()["discord_user_id"] == ""
        assert "invite_url" not in page.json()

        assert save_id(client, "100000000000000009", kinds=("ready", "downloading")).json()[
            "kinds"
        ] == ["ready", "downloading"]
        assert press_test(client).json()["delivered"] is True
        assert [recipient for recipient, _ in factory.discord_.sent] == ["100000000000000009"]

    def test_a_crew_member_starts_with_ready_and_cannot_add_waiting(
        self, client: TestClient
    ) -> None:
        """「等你處理」只給管理員（M4 票 127）：送來了也不存。"""
        sign_in_crew(client)

        assert client.get(MINE).json()["kinds"] == ["ready"]
        saved = save_id(client, "100000000000000009", kinds=("ready", "waiting"))
        assert saved.json()["kinds"] == ["ready"]

    def test_the_bot_half_stays_behind_the_admin_gate(self, client: TestClient) -> None:
        save_token(client)
        sign_in_crew(client)

        assert client.get(BASE).status_code == 403
        assert save_token(client, "crew-token").status_code == 403
        assert save_berth_url(client, "https://evil.example.com").status_code == 403

    def test_each_person_reads_and_writes_only_their_own(self, client: TestClient) -> None:
        save_id(client)
        sign_in_crew(client)

        assert client.get(MINE).json()["discord_user_id"] == ""
        save_id(client, "100000000000000009")

        sign_in_crew(client, "lookout")
        assert client.get(MINE).json()["discord_user_id"] == ""


class TestBerthUrl:
    """Berth 從外面看的網址：通知裡的連結照它組（M4 票 124）。"""

    def test_a_saved_address_comes_back_without_the_trailing_slash(
        self, client: TestClient
    ) -> None:
        saved = save_berth_url(client, " https://berth.example.com/ ")

        assert saved.status_code == 200
        assert saved.json()["berth_url"] == "https://berth.example.com"
        assert client.get(BASE).json()["berth_url"] == "https://berth.example.com"

    @pytest.mark.parametrize(
        "wrong",
        [
            "berth.example.com",
            "ftp://berth.example.com",
            "/media",
            "https://",
            # 連結是接著路徑組的：`?x=1/media/...` 開不到作品頁。
            "https://berth.example.com?x=1",
            "https://berth.example.com/#top",
        ],
    )
    def test_something_that_is_not_an_http_address_is_refused_and_not_kept(
        self, client: TestClient, wrong: str
    ) -> None:
        save_berth_url(client, "http://192.168.1.10:8000")

        refused = save_berth_url(client, wrong)

        assert refused.status_code == 422
        assert refused.json()["detail"]["reason"] == "berth_url_invalid"
        assert wrong in refused.json()["detail"]["detail"]
        assert client.get(BASE).json()["berth_url"] == "http://192.168.1.10:8000"

    def test_an_empty_address_clears_it(self, client: TestClient) -> None:
        save_berth_url(client, "https://berth.example.com")

        cleared = save_berth_url(client, "")

        assert cleared.status_code == 200
        assert cleared.json()["berth_url"] == ""


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

        page = client.get(MINE).json()
        assert page["unreachable_at"] is not None
        assert "50278" in page["unreachable_detail"]

        factory.discord_.unreachable.clear()
        press_test(client)
        assert client.get(MINE).json()["unreachable_at"] is None

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
