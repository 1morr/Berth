"""`/api/auth/*` 與整個 API 的門禁（plan §6、票 07 驗收）。

門禁是**預設拒絕**：`/api` 底下除了白名單那幾條，沒有 session 就是 401；非 GET 少了
`X-Requested-With` 就是 403。判定規則本身在 `test_auth_service.py`。
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.api import gate
from berth.api.deps import get_client_factory
from berth.api.gate import CSRF_HEADER, SESSION_COOKIE, Access, access_of
from berth.config import Config
from berth.main import create_app
from berth.models import JellyfinSettings, SetupSettings
from berth.services.settings import read_settings, write_settings
from tests.endpoints import api_endpoints

JELLYFIN_URL = "http://jellyfin:8096"
BROWSER = {CSRF_HEADER: "XMLHttpRequest"}
ADMIN = {"username": "skipper", "password": "harbour"}
DECKHAND = {"username": "deckhand", "password": "rope"}
#: 形狀對的 info hash。這一台上沒有這筆 Job——門禁跑在 router 之前，所以它照樣測得了。
HASH = "4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b"


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


class TestDeletingIsAdminOnlyWhileTheRestOfJobsIsNot:
    """門禁認得**方法**（M2 票 04）。

    `/jobs` 整組不能是 admin——一般使用者要送得了單、看得到自己的 job（brief §11）。而
    刪除是 admin 的事（plan §6，2026-09-22 拍板）。所以這是第一條「同一條路徑、不同方法、
    不同門禁」的規則，而它仍然只住在門禁一處。

    兩邊都斷言：把規則改回純前綴的話，不是 `/jobs` 整組變成 admin（下面那三條紅），就是
    刪除對誰都開著（上面那條紅）。
    """

    def test_an_ordinary_user_cannot_delete_a_job(self, client: TestClient) -> None:
        sign_in(client, DECKHAND)

        assert delete(client, f"/api/jobs/{HASH}").status_code == 403

    def test_an_administrator_gets_past_the_gate(self, client: TestClient) -> None:
        """門禁放行之後才輪到 router：這一台上沒有這筆 Job，所以 404 就是「進得來」。"""
        sign_in(client, ADMIN)

        assert delete(client, f"/api/jobs/{HASH}").status_code == 404

    def test_an_ordinary_user_still_reads_and_submits(self, client: TestClient) -> None:
        sign_in(client, DECKHAND)

        assert client.get("/api/jobs").status_code == 200
        assert client.get(f"/api/jobs/{HASH}/events").status_code == 200
        # 送單的 body 是空的，所以這是 422——重點是它**不是** 403：門禁放行了。
        assert post(client, "/api/jobs", {}).status_code == 422

    def test_signing_out_still_beats_the_method_rule(self, client: TestClient) -> None:
        """未登入是 401 而不是 403：前端據此導向 `/login`，不是說「你不是管理員」。"""
        assert delete(client, f"/api/jobs/{HASH}").status_code == 401


#: **每一條 API 路由是誰的**，照 `access_of` 的四種分（路徑相對 `/api`，路徑參數一律寫 `*`）。
#:
#: 故意寫死整張而不是只列 admin 那幾條：新增一個端點時，這張表逼人當場決定它是誰的——
#: 忘了把一支修正類的端點放進 `ADMIN_PREFIXES` / `ADMIN_ROUTES`，只列 admin 的表不會知道
#: 它漏了，這張會因為「沒被分類」先紅，分類成 admin 之後再因為門禁放行而紅。
ACCESS: dict[tuple[str, str], Access] = {
    ("POST", "/auth/login"): Access.ANONYMOUS,
    ("POST", "/auth/logout"): Access.ANONYMOUS,
    ("GET", "/health"): Access.ANONYMOUS,
    # 精靈：跑完之前匿名、之後只有管理員（`TestSettingsAreAdminOnly`）。
    ("POST", "/setup/admin"): Access.SETUP,
    ("POST", "/setup/complete"): Access.SETUP,
    ("POST", "/setup/detect"): Access.SETUP,
    ("GET", "/setup/indexers"): Access.SETUP,
    ("POST", "/setup/indexers/apply"): Access.SETUP,
    ("POST", "/setup/indexers/connect"): Access.SETUP,
    ("POST", "/setup/indexers/skip"): Access.SETUP,
    ("GET", "/setup/indexers/search"): Access.SETUP,
    ("DELETE", "/setup/indexers/*"): Access.SETUP,
    ("GET", "/setup/jellyfin"): Access.SETUP,
    ("POST", "/setup/jellyfin/bootstrap"): Access.SETUP,
    ("PUT", "/setup/jellyfin/bundled"): Access.SETUP,
    ("POST", "/setup/jellyfin/connect"): Access.SETUP,
    ("POST", "/setup/jellyfin/libraries/paths"): Access.SETUP,
    ("POST", "/setup/qbittorrent/apply"): Access.SETUP,
    ("GET", "/setup/qbittorrent/diff"): Access.SETUP,
    ("GET", "/setup/routes"): Access.SETUP,
    ("POST", "/setup/routes"): Access.SETUP,
    ("DELETE", "/setup/routes/*"): Access.SETUP,
    ("POST", "/setup/services/*"): Access.SETUP,
    ("GET", "/setup/status"): Access.SETUP,
    ("GET", "/setup/tmdb"): Access.SETUP,
    ("POST", "/setup/tmdb/test"): Access.SETUP,
    # M2 驗收第四條點名的六組（plan §11.3、票 16）：審核、Issue、rematch、對帳、刪除、重新入庫。
    ("GET", "/review"): Access.ADMIN,
    ("POST", "/review/audit/*/confirm"): Access.ADMIN,
    ("POST", "/review/audit/confirm"): Access.ADMIN,
    ("POST", "/review/series/*/confirm"): Access.ADMIN,
    ("POST", "/review/audit/*/undo"): Access.ADMIN,
    ("POST", "/review/duplicate/*/*"): Access.ADMIN,
    ("GET", "/issues"): Access.ADMIN,
    ("POST", "/issues/*/ignore"): Access.ADMIN,
    ("POST", "/issues/*/resolve"): Access.ADMIN,
    ("POST", "/files/rematch"): Access.ADMIN,
    ("GET", "/reconcile"): Access.ADMIN,
    ("POST", "/reconcile"): Access.ADMIN,
    ("DELETE", "/jobs/*"): Access.ADMIN,
    ("POST", "/jobs/*/reimport"): Access.ADMIN,
    # 其餘管理員的：刪除前的估算、Plan 的審核、設定、Route、Jellyfin 媒體庫清單。
    ("GET", "/jobs/*/deletion"): Access.ADMIN,
    ("POST", "/plans/*/approve"): Access.ADMIN,
    ("PUT", "/plans/*/items"): Access.ADMIN,
    ("POST", "/plans/*/reject"): Access.ADMIN,
    ("GET", "/settings/disk"): Access.ADMIN,
    ("POST", "/settings/disk"): Access.ADMIN,
    ("GET", "/settings/jellyfin"): Access.ADMIN,
    ("POST", "/settings/jellyfin"): Access.ADMIN,
    ("POST", "/settings/qbittorrent/apply"): Access.ADMIN,
    ("GET", "/settings/qbittorrent/diff"): Access.ADMIN,
    ("GET", "/settings/services"): Access.ADMIN,
    ("POST", "/settings/services/*/test"): Access.ADMIN,
    ("GET", "/routes"): Access.ADMIN,
    ("POST", "/routes"): Access.ADMIN,
    ("DELETE", "/routes/*"): Access.ADMIN,
    ("PUT", "/routes/*"): Access.ADMIN,
    ("POST", "/routes/*/check"): Access.ADMIN,
    ("GET", "/jellyfin/libraries"): Access.ADMIN,
    # RSS（M3 票 08）：整組 admin——聚合 feed 的網址帶 token，綁定會替整個家送單。
    ("GET", "/rss/feeds"): Access.ADMIN,
    ("POST", "/rss/feeds"): Access.ADMIN,
    ("DELETE", "/rss/feeds/*"): Access.ADMIN,
    ("POST", "/rss/feeds/*/poll"): Access.ADMIN,
    ("GET", "/rss/feeds/*/preview"): Access.ADMIN,
    ("POST", "/rss/feeds/*/prime"): Access.ADMIN,
    ("GET", "/rss/series"): Access.ADMIN,
    ("PUT", "/rss/series/*/binding"): Access.ADMIN,
    ("DELETE", "/rss/series/*/binding"): Access.ADMIN,
    ("GET", "/rss/items"): Access.ADMIN,
    ("POST", "/rss/oneshot"): Access.ADMIN,
    # 排除條件（票 10）：三層都是 admin，同一組的理由。
    ("GET", "/rss/exclusions"): Access.ADMIN,
    ("PUT", "/rss/exclusions"): Access.ADMIN,
    ("PUT", "/rss/feeds/*/exclusions"): Access.ADMIN,
    ("PUT", "/rss/series/*/exclusions"): Access.ADMIN,
    # 一般使用者：探索、送單、看自己的 Job、瀏覽媒體庫（brief §11）。重試與重新規劃是送單的
    # 人自己按得到的——它們只讓這一筆往前走，不拆也不改媒體庫裡已經有的東西。**例外是停在
    # review 的那一筆的重新規劃**（M3 票 04）：它會丟掉 admin 審過的那一份，所以只有 admin。
    # 門禁只看方法與路徑，這一條要看狀態，所以守在命令裡（403 `review_needs_admin`，
    # `test_plans_api.py` 的 `TestReplanInReviewIsAdmins`）；這張表上它仍然是 SIGNED_IN。
    ("GET", "/auth/me"): Access.SIGNED_IN,
    ("GET", "/discover/popular"): Access.SIGNED_IN,
    ("GET", "/discover/search"): Access.SIGNED_IN,
    ("GET", "/discover/trending"): Access.SIGNED_IN,
    ("GET", "/events/stream"): Access.SIGNED_IN,
    ("POST", "/health/check"): Access.SIGNED_IN,
    ("GET", "/health/detail"): Access.SIGNED_IN,
    ("GET", "/inventory"): Access.SIGNED_IN,
    ("GET", "/inventory/*"): Access.SIGNED_IN,
    ("GET", "/inventory/*/filters"): Access.SIGNED_IN,
    ("GET", "/inventory/*/watching"): Access.SIGNED_IN,
    ("GET", "/jellyfin/items/*/images/*"): Access.SIGNED_IN,
    ("DELETE", "/jellyfin/items/*/played"): Access.SIGNED_IN,
    ("POST", "/jellyfin/items/*/played"): Access.SIGNED_IN,
    ("GET", "/jellyfin/shows/*/episodes"): Access.SIGNED_IN,
    ("GET", "/jobs"): Access.SIGNED_IN,
    ("POST", "/jobs"): Access.SIGNED_IN,
    ("GET", "/jobs/*"): Access.SIGNED_IN,
    ("GET", "/jobs/*/events"): Access.SIGNED_IN,
    ("POST", "/jobs/*/replan"): Access.SIGNED_IN,
    ("POST", "/jobs/*/retry"): Access.SIGNED_IN,
    ("GET", "/media/*"): Access.SIGNED_IN,
    ("POST", "/media/*/refresh"): Access.SIGNED_IN,
    ("GET", "/media/*/watch"): Access.SIGNED_IN,
    ("GET", "/plans/*"): Access.SIGNED_IN,
    ("GET", "/search"): Access.SIGNED_IN,
    ("GET", "/search/queries"): Access.SIGNED_IN,
}

#: M2 驗收第四條點名的六組，照票 16 的寫法：整塊是 admin 的四個前綴，加上 `/jobs` 上的兩個動詞。
M2_NAMED_PREFIXES = ("/review", "/issues", "/files", "/reconcile")
M2_NAMED_ROUTES = (("DELETE", "/jobs/*"), ("POST", "/jobs/*/reimport"))

_PARAMETER = re.compile(r"\{[^/]+\}")


def routes_of(app: FastAPI) -> set[tuple[str, str]]:
    """app 上每一條 `(方法, 路徑)`，路徑相對 `/api`、參數寫成 `*`——參數叫什麼不影響它是誰的。"""
    return {
        (method, _PARAMETER.sub("*", endpoint.path.removeprefix("/api")))
        for endpoint in api_endpoints(app)
        for method in endpoint.methods
    }


def misclassified(table: dict[tuple[str, str], Access]) -> dict[tuple[str, str], Access]:
    """門禁的判定與表上寫的不同的那幾條：路由 → 門禁**實際**給的那一種。"""
    found = {route: access_of(route[0], concrete(route[1])) for route in table}
    return {route: actual for route, actual in found.items() if actual is not table[route]}


def concrete(template: str) -> str:
    """`/jobs/*/reimport` → `/jobs/1/reimport`。門禁在路由之前，參數長什麼樣它不看。"""
    return template.replace("*", "1")


def named_by_m2(route: tuple[str, str]) -> bool:
    path = route[1]
    return route in M2_NAMED_ROUTES or any(
        path == prefix or path.startswith(prefix + "/") for prefix in M2_NAMED_PREFIXES
    )


APP_ROUTES = routes_of(create_app())


class TestWhoEachEndpointIsFor:
    """M2 驗收第四條的後端那一半（票 16）：以 `user` 登入時**按不到**審核、修正與刪除。

    三層：表涵蓋 app 上的每一條路由（新增端點沒分類就紅）；門禁對每一條的判定與表一致（分成
    admin 卻沒進門禁就紅，反過來把一般使用者的端點誤關進去也紅）；最後真的以 `deckhand`
    打每一條 admin 的，拿到的是 403。
    """

    def test_every_route_on_the_app_is_classified(self) -> None:
        assert set(ACCESS) - APP_ROUTES == set(), "the table lists routes the app no longer has"
        assert APP_ROUTES - set(ACCESS) == set(), "classify these new routes in ACCESS"

    def test_the_gate_agrees_with_the_table(self) -> None:
        assert misclassified(ACCESS) == {}

    def test_the_six_the_m2_acceptance_names_are_admin_only(self) -> None:
        """從 app 上的路由算，不從表上抄：`/review` 底下新掛一支，它也在這一組裡。"""
        named = {route for route in APP_ROUTES if named_by_m2(route)}

        # review 6（M3 票 13 加 RSS Series 的整組確認）+ issues 3 + files 1 + reconcile 2
        # + jobs 上的 2。新掛一支就是 15，有人得看一眼。
        assert len(named) == 14, sorted(named)
        assert {route: ACCESS[route] for route in named} == dict.fromkeys(named, Access.ADMIN)

    @pytest.mark.parametrize(
        "route",
        sorted(route for route, access in ACCESS.items() if access is Access.ADMIN),
        ids=" ".join,
    )
    def test_an_ordinary_user_is_refused(self, client: TestClient, route: tuple[str, str]) -> None:
        """門禁在 router 之前擋下來，所以參數是不是真的有那一筆、body 對不對都無所謂。"""
        method, template = route
        sign_in(client, DECKHAND)

        response = client.request(method, f"/api{concrete(template)}", headers=BROWSER)

        assert response.status_code == 403, response.text


class TestTheSurfaceCheckItself:
    """上面那組的雙向變異：該紅的時候紅、不該紅的時候不紅（全域 CLAUDE.md「規則要有閘門」）。"""

    def test_a_new_route_nobody_classified_shows_up(self) -> None:
        app = create_app()

        @app.post("/api/jobs/{job_hash}/purge")
        async def purge(job_hash: str) -> None:
            """一支新的修正類端點，沒寫進表、也沒寫進門禁。"""

        assert routes_of(app) - set(ACCESS) == {("POST", "/jobs/*/purge")}

    def test_renaming_a_path_parameter_changes_nothing(self) -> None:
        app = create_app()

        @app.get("/api/jobs/{info_hash}/events")
        async def events(info_hash: str) -> None:
            """同一條路徑、參數換個名字：它仍然是表上那一條。"""

        assert routes_of(app) == APP_ROUTES

    def test_dropping_a_prefix_from_the_gate_is_caught(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        kept = tuple(prefix for prefix in gate.ADMIN_PREFIXES if prefix != "/files")
        monkeypatch.setattr(gate, "ADMIN_PREFIXES", kept)

        assert misclassified(ACCESS) == {("POST", "/files/rematch"): Access.SIGNED_IN}

    def test_reordering_the_gate_changes_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(gate, "ADMIN_PREFIXES", tuple(reversed(gate.ADMIN_PREFIXES)))
        monkeypatch.setattr(gate, "ADMIN_ROUTES", tuple(reversed(gate.ADMIN_ROUTES)))

        assert misclassified(ACCESS) == {}

    def test_a_signed_in_route_closed_by_mistake_is_caught(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gate, "ADMIN_ROUTES", (*gate.ADMIN_ROUTES, ("POST", "/jobs/*/retry")))

        assert misclassified(ACCESS) == {("POST", "/jobs/*/retry"): Access.ADMIN}


def delete(client: TestClient, path: str) -> httpx.Response:
    response: httpx.Response = client.delete(path, headers=BROWSER)
    return response


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
