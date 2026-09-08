"""`/api/auth/*` 與整個 API 的門禁（plan §6、票 07 驗收）。

門禁是**預設拒絕**：`/api` 底下除了白名單那幾條，沒有 session 就是 401；非 GET 少了
`X-Requested-With` 就是 403。判定規則本身在 `test_auth_service.py`。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.api.deps import get_client_factory
from berth.api.gate import CSRF_HEADER, SESSION_COOKIE
from berth.config import Config
from berth.main import create_app
from berth.models import JellyfinSettings, SetupSettings
from berth.services.settings import read_settings, write_settings

JELLYFIN_URL = "http://jellyfin:8096"
BROWSER = {CSRF_HEADER: "XMLHttpRequest"}
ADMIN = {"username": "skipper", "password": "harbour"}
DECKHAND = {"username": "deckhand", "password": "rope"}


class OneJellyfin:
    def __init__(self, jellyfin: FakeJellyfinClient) -> None:
        self._jellyfin = jellyfin

    def jellyfin(self, base_url: str, token: str = "") -> FakeJellyfinClient:
        return self._jellyfin

    def qbittorrent(self, base_url: str) -> FakeQbittorrentClient:
        return FakeQbittorrentClient(base_url=base_url)

    def prowlarr(self, base_url: str, api_key: str) -> FakeProwlarrClient:
        return FakeProwlarrClient(base_url=base_url)


@pytest.fixture
def jellyfin() -> FakeJellyfinClient:
    return FakeJellyfinClient(
        startup_wizard_completed=True,
        admin=(ADMIN["username"], ADMIN["password"]),
        users={DECKHAND["username"]: DECKHAND["password"]},
    )


@pytest.fixture
def client(config: Config, tmp_path: Path, jellyfin: FakeJellyfinClient) -> Iterator[TestClient]:
    """精靈已經跑完的一台 Berth：`/setup` 從此要管理員，其餘 API 都要登入。"""
    app = create_app(replace(config, web_root=tmp_path / "never-built"))
    app.dependency_overrides[get_client_factory] = lambda: OneJellyfin(jellyfin)
    with TestClient(app) as running:
        _finish_setup(running)
        yield running


def post(client: TestClient, path: str, body: object = None) -> httpx.Response:
    """前端一律帶 CSRF 標頭（`api/client.ts`）；沒帶的情形另外測。"""
    response: httpx.Response = client.post(path, json=body, headers=BROWSER)
    return response


def sign_in(client: TestClient, credentials: dict[str, str]) -> httpx.Response:
    return post(client, "/api/auth/login", credentials)


class TestLogin:
    def test_an_administrator_signs_in(self, client: TestClient) -> None:
        response = sign_in(client, ADMIN)

        assert response.status_code == 200
        assert response.json() == {"name": "skipper", "role": "admin"}

    def test_the_session_arrives_as_an_httponly_strict_cookie(self, client: TestClient) -> None:
        response = sign_in(client, ADMIN)

        cookie = response.headers["set-cookie"].lower()
        assert f"{SESSION_COOKIE}=".lower() in cookie
        assert "httponly" in cookie
        assert "samesite=strict" in cookie
        assert "path=/" in cookie

    def test_the_token_never_appears_in_the_body(self, client: TestClient) -> None:
        """cookie 是 httpOnly 的意義就在這裡：token 不該有第二個出口。"""
        body = sign_in(client, ADMIN).json()

        assert set(body) == {"name", "role"}

    def test_a_wrong_password_is_401(self, client: TestClient) -> None:
        response = sign_in(client, {"username": "skipper", "password": "wrong"})

        assert response.status_code == 401
        assert SESSION_COOKIE not in response.cookies

    def test_an_unknown_account_answers_exactly_the_same(self, client: TestClient) -> None:
        wrong = sign_in(client, {"username": "skipper", "password": "wrong"})
        unknown = sign_in(client, {"username": "nobody", "password": "harbour"})

        assert wrong.status_code == unknown.status_code
        assert wrong.json() == unknown.json()

    def test_blank_credentials_are_refused_the_same_way(self, client: TestClient) -> None:
        blank = sign_in(client, {"username": "", "password": ""})
        wrong = sign_in(client, {"username": "skipper", "password": "wrong"})

        assert blank.status_code == 401
        assert blank.json() == wrong.json()

    def test_the_refusal_never_echoes_the_password(self, client: TestClient) -> None:
        response = sign_in(client, {"username": "skipper", "password": "hunter2"})

        assert "hunter2" not in response.text

    def test_a_missing_field_is_refused_like_a_wrong_password(self, client: TestClient) -> None:
        """422 與 401 分得出來就是一個可以拿來試探的差別。"""
        response = post(client, "/api/auth/login", {"password": "harbour"})

        assert response.status_code == 401

    def test_a_rejected_body_never_comes_back_with_what_was_sent(self, client: TestClient) -> None:
        """FastAPI 預設把收到的值放進 422 裡——那會把密碼原樣送回去（`api/errors.py`）。"""
        response = post(client, "/api/auth/login", {"username": "skipper", "password": 1234567})

        assert response.status_code == 422
        assert "1234567" not in response.text
        # 「哪個欄位、為什麼」留著，值不留。
        assert response.json()["detail"][0]["loc"] == ["body", "password"]

    def test_an_unreachable_jellyfin_is_503_not_401(
        self, client: TestClient, jellyfin: FakeJellyfinClient
    ) -> None:
        """密碼沒有錯，是身分來源不在。UI 要說得出這兩件事的差別（brief §11）。"""
        jellyfin.error = ServiceUnavailableError("connection refused")

        assert sign_in(client, ADMIN).status_code == 503


class TestMe:
    def test_me_reports_the_signed_in_user(self, client: TestClient) -> None:
        sign_in(client, ADMIN)

        response = client.get("/api/auth/me")

        assert response.status_code == 200
        assert response.json() == {"name": "skipper", "role": "admin"}

    def test_an_ordinary_user_is_reported_as_such(self, client: TestClient) -> None:
        sign_in(client, DECKHAND)

        assert client.get("/api/auth/me").json()["role"] == "user"

    def test_me_without_a_session_is_401(self, client: TestClient) -> None:
        assert client.get("/api/auth/me").status_code == 401

    def test_a_forged_cookie_is_401(self, client: TestClient) -> None:
        client.cookies.set(SESSION_COOKIE, "made-up")

        assert client.get("/api/auth/me").status_code == 401


class TestLogout:
    def test_logging_out_invalidates_the_session(self, client: TestClient) -> None:
        sign_in(client, ADMIN)

        assert post(client, "/api/auth/logout").status_code == 204

        client.cookies.clear()
        assert client.get("/api/auth/me").status_code == 401

    def test_logging_out_clears_the_cookie(self, client: TestClient) -> None:
        sign_in(client, ADMIN)

        post(client, "/api/auth/logout")

        assert client.cookies.get(SESSION_COOKIE) in (None, "")

    def test_the_old_token_stops_working_even_if_the_browser_keeps_it(
        self, client: TestClient
    ) -> None:
        sign_in(client, ADMIN)
        token = client.cookies[SESSION_COOKIE]

        post(client, "/api/auth/logout")
        client.cookies.set(SESSION_COOKIE, token)

        assert client.get("/api/auth/me").status_code == 401

    def test_logging_out_without_a_session_is_still_fine(self, client: TestClient) -> None:
        assert post(client, "/api/auth/logout").status_code == 204


class TestGate:
    def test_any_api_needs_a_session(self, client: TestClient) -> None:
        assert client.get("/api/auth/me").status_code == 401
        assert client.get("/api/setup/status").status_code == 401

    def test_health_stays_anonymous(self, client: TestClient) -> None:
        response = client.get("/api/health")

        assert response.status_code == 200
        # 沒登入也讀得到「精靈跑完了沒」——前端靠它決定要畫精靈還是登入頁。
        assert response.json()["setup_completed"] is True

    def test_an_unknown_api_path_is_refused_before_it_is_looked_up(
        self, client: TestClient
    ) -> None:
        """404 會洩漏「哪些端點存在」，門禁在路由之前就擋下來。"""
        response = client.get("/api/nope")

        assert response.status_code == 401
        assert response.json()["detail"]

    def test_a_signed_in_caller_gets_a_normal_404(self, client: TestClient) -> None:
        sign_in(client, ADMIN)

        response = client.get("/api/nope")

        assert response.status_code == 404
        assert response.json()["detail"]

    def test_the_gate_only_covers_the_api(self, client: TestClient) -> None:
        """`/login` 要拿得到前端，否則沒有人登得進來。"""
        assert client.get("/login").status_code != 401


class TestCsrf:
    def test_a_post_without_the_header_is_403(self, client: TestClient) -> None:
        response = client.post("/api/auth/login", json=ADMIN)

        assert response.status_code == 403

    def test_the_header_check_happens_before_the_credentials_are_read(
        self, client: TestClient
    ) -> None:
        """沒有標頭就不該有人拿得到「帳密對不對」這個資訊。"""
        response = client.post("/api/auth/login", json={"username": "skipper", "password": "x"})

        assert response.status_code == 403

    def test_a_signed_in_post_still_needs_the_header(self, client: TestClient) -> None:
        sign_in(client, ADMIN)

        assert client.post("/api/auth/logout").status_code == 403

    def test_get_requests_do_not_need_the_header(self, client: TestClient) -> None:
        sign_in(client, ADMIN)

        assert client.get("/api/auth/me").status_code == 200

    def test_the_header_value_does_not_matter(self, client: TestClient) -> None:
        """防的是跨站表單送出——它根本加不了自訂標頭，值是什麼無關緊要。"""
        response = client.post("/api/auth/login", json=ADMIN, headers={CSRF_HEADER: "berth"})

        assert response.status_code == 200


class TestSettingsAreAdminOnly:
    def test_an_administrator_can_still_reach_setup(self, client: TestClient) -> None:
        sign_in(client, ADMIN)

        assert client.get("/api/setup/status").status_code == 200

    def test_an_ordinary_user_is_refused(self, client: TestClient) -> None:
        """非 admin 直接打設定 API 也回 403（票 07 驗收）。"""
        sign_in(client, DECKHAND)

        assert client.get("/api/setup/status").status_code == 403
        assert post(client, "/api/setup/detect", {}).status_code == 403

    def test_an_ordinary_user_cannot_rerun_the_jellyfin_sequence(self, client: TestClient) -> None:
        sign_in(client, DECKHAND)

        assert post(client, "/api/setup/jellyfin/bootstrap").status_code == 403

    def test_the_rule_holds_for_setup_paths_that_no_router_claims(self, client: TestClient) -> None:
        """規則在門禁上，不在 router 的相依上——所以之後新掛的 setup 端點預設就在門後。"""
        sign_in(client, DECKHAND)

        assert client.get("/api/setup/not-built-yet").status_code == 403


def _finish_setup(client: TestClient) -> None:
    """把 DB 推到「精靈跑完」的狀態。票 09 的 `POST /setup/complete` 還沒有。"""

    async def mark() -> None:
        factory = client.app.state.session_factory  # type: ignore[attr-defined]
        async with factory() as session:
            setup = await read_settings(session, SetupSettings)
            setup.completed = True
            await write_settings(session, setup)
            await write_settings(
                session, JellyfinSettings(base_url=JELLYFIN_URL, api_key="the-key")
            )
            await session.commit()

    asyncio.run(mark())
