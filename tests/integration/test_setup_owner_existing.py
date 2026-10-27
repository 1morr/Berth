"""頁 1 既有 Jellyfin：位址與管理員帳密一次送出（M4 票 67，審計 C1）。

照 Seerr（伺服器位址與管理員帳密同一頁、一顆 Sign In）：`POST /setup/owner/existing` 先測位址、
測過才存（M4 票 45），那一台已經有管理員就接著登入、成為擁有者、發 session。錯誤照票 45 分到
欄位：位址那一段是 400 `connection_failed` 帶那一次測試（`attempt.reason` 決定標哪一格），帳密是
401，其餘（不是管理員、Jellyfin 那一段失敗）在表單層級。還沒初始化的那一台照原本的分支：存下選擇、
不建任何東西，頁 1 換成建立管理員的表單。
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.jellyfin.fake import SERVER_ID, FakeJellyfinClient
from berth.api.deps import get_bundled_services, get_client_factory
from berth.api.gate import CSRF_HEADER, SESSION_COOKIE
from berth.config import Config
from berth.main import create_app
from berth.services.clients import BundledServices
from tests.integration.factories import COMPOSE, FakeClientFactory

BROWSER = {CSRF_HEADER: "XMLHttpRequest"}
ADDRESS = "http://media.lan:8096"
PASSWORD = "harbour-lights"


def _app(config: Config, tmp_path: Path, jellyfin: FakeJellyfinClient) -> Iterator[TestClient]:
    app = create_app(replace(config, web_root=tmp_path / "never-built"))
    factory = FakeClientFactory(jellyfin=jellyfin)
    app.dependency_overrides[get_bundled_services] = lambda: BundledServices(
        targets=COMPOSE, prowlarr_api_key=""
    )
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app, headers=BROWSER) as running:
        yield running


@pytest.fixture
def jellyfin() -> FakeJellyfinClient:
    """使用者自己的那一台：跑過初始精靈，有一個管理員與一個一般使用者。"""
    return FakeJellyfinClient(
        startup_wizard_completed=True,
        admin=("captain", PASSWORD),
        users={"deckhand": PASSWORD},
    )


@pytest.fixture
def fresh(config: Config, tmp_path: Path, jellyfin: FakeJellyfinClient) -> Iterator[TestClient]:
    yield from _app(config, tmp_path, jellyfin)


def _sign_in(client: TestClient, **body: str) -> Response:
    response: Response = client.post(
        "/api/setup/owner/existing",
        json={"base_url": ADDRESS, "username": "captain", "password": PASSWORD, **body},
    )
    return response


def test_one_call_connects_and_signs_the_owner_in(fresh: TestClient) -> None:
    response = _sign_in(fresh)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["owner"] == "captain"
    assert body["current_step"] == 2
    [row] = body["services"]
    assert (row["kind"], row["origin"], row["base_url"], row["state"]) == (
        "jellyfin",
        "existing",
        ADDRESS,
        "ok",
    )
    # 同一個回應就發了 session：下一支精靈端點不必再登入。
    assert fresh.get("/api/setup/jellyfin").status_code == 200


def test_the_address_stays_trimmed_like_the_choice_form(fresh: TestClient) -> None:
    response = _sign_in(fresh, base_url=f"  {ADDRESS}/ ")

    assert response.status_code == 200, response.text
    assert response.json()["services"][0]["base_url"] == ADDRESS


def test_an_unreachable_address_is_the_address_fields_and_nothing_is_kept(
    config: Config, tmp_path: Path
) -> None:
    down = FakeJellyfinClient(error=ServiceUnavailableError("connection refused"))
    for client in _app(config, tmp_path, down):
        response = _sign_in(client)

        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["reason"] == "connection_failed"
        # `unreachable` 是位址那一格的（前端 `connectionField`）。
        assert detail["attempt"]["reason"] == "unreachable"
        assert detail["attempt"]["base_url"] == ADDRESS
        status = client.get("/api/setup/status").json()
        assert (status["owner"], status["services"]) == ("", [])


def test_a_jellyfin_too_old_is_a_form_level_connection_failure(
    config: Config, tmp_path: Path
) -> None:
    old = FakeJellyfinClient(
        version="10.10.7", startup_wizard_completed=True, admin=("captain", PASSWORD)
    )
    for client in _app(config, tmp_path, old):
        response = _sign_in(client)

        assert response.status_code == 400
        attempt = response.json()["detail"]["attempt"]
        assert (attempt["reason"], attempt["detail"]) == ("version_unsupported", "10.10.7")
        assert old.admin == ("captain", PASSWORD)


def test_a_wrong_password_is_the_credential_fields(fresh: TestClient) -> None:
    response = _sign_in(fresh, password="wrong")

    assert response.status_code == 401
    assert response.json()["detail"] == {"reason": "invalid_credentials", "detail": ""}
    assert fresh.get("/api/setup/status").json()["owner"] == ""


def test_blank_credentials_never_reach_jellyfin(
    fresh: TestClient, jellyfin: FakeJellyfinClient
) -> None:
    response = _sign_in(fresh, password="")

    assert response.status_code == 401
    assert response.json()["detail"]["reason"] == "invalid_credentials"
    assert jellyfin.api_keys_ == []


def test_a_user_who_is_not_an_administrator_is_refused_at_the_form(fresh: TestClient) -> None:
    response = _sign_in(fresh, username="deckhand")

    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "not_administrator"
    assert fresh.get("/api/setup/status").json()["owner"] == ""


def test_a_wrong_password_then_the_right_one_signs_in(fresh: TestClient) -> None:
    """改一格再按：第一次存下的位址不擋第二次。"""
    assert _sign_in(fresh, password="wrong").status_code == 401

    response = _sign_in(fresh)

    assert response.status_code == 200, response.text
    assert response.json()["owner"] == "captain"


def test_a_jellyfin_not_yet_set_up_keeps_the_choice_and_asks_for_the_create_form(
    config: Config, tmp_path: Path
) -> None:
    """還沒初始化的那一台照原本的分支：只存下選擇，建管理員由下一張表單（帶語言與遠端存取）做。"""
    blank = FakeJellyfinClient(startup_wizard_completed=False)
    for client in _app(config, tmp_path, blank):
        response = _sign_in(client)

        assert response.status_code == 200, response.text
        body = response.json()
        assert (body["owner"], body["owner_signs_in"]) == ("", False)
        [row] = body["services"]
        assert (row["origin"], row["state"], row["reason"], row["server_id"]) == (
            "existing",
            "ok",
            "setup_pending",
            SERVER_ID,
        )
        assert blank.admin is None
        assert blank.startup_wizard_completed is False
        # 沒有擁有者，也就沒有 session。
        assert SESSION_COOKIE not in client.cookies


def test_once_there_is_an_owner_it_does_not_make_another(fresh: TestClient) -> None:
    assert _sign_in(fresh).status_code == 200

    response = _sign_in(fresh)

    assert response.status_code == 409
    assert response.json()["detail"]["reason"] == "owner_exists"
