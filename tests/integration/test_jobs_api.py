"""jobs 端點（plan §6 jobs 群組、票 09 驗收）。

命令本身在 `test_jobs.py`；這裡驗的是形狀、狀態碼與「誰進得來」——`/api/jobs` 沒有在門禁的
白名單上，所以匿名一律 401，而**送單不是管理動作**（brief §11：那本來就是一般使用者做的事）。

拒絕的狀態碼分成三種，因為修法不同：422 是「你送錯東西了」，409 是「請求沒問題，現在做不了」
（紅的 Route 修好之後同一個請求就會成功），502 是「索引站那邊給不出這份 torrent」。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.adapters.torrent import NotATorrentError
from berth.api.deps import get_client_factory
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.domain import HealthStatus
from berth.main import create_app
from berth.models import Route, TmdbSettings
from berth.services.routes import build_routes
from berth.services.settings import write_settings
from berth.services.setup import complete_setup
from tests.conftest import TMDB_API_KEY
from tests.integration.arrange import arrange, bundled_libraries, factory_for, fake_jellyfin
from tests.integration.factories import FakeClientFactory
from tests.integration.test_media import ORDERING, SEASONS, SPY, SPY_ID

BROWSER = {CSRF_HEADER: "XMLHttpRequest"}
ADMIN = {"username": "skipper", "password": "harbour"}
CREW = {"username": "deckhand", "password": "rope"}

MAGNET = "magnet:?xt=urn:btih:4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b&dn=Spy.x.Family"
MAGNET_HASH = "4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b"
RELEASE = "[ANi] SPY×FAMILY - 13 [1080P][WEB-DL][AAC AVC][CHT]"


@pytest.fixture
def factory(roots: dict[str, Path]) -> FakeClientFactory:
    return factory_for(
        roots,
        jellyfin=fake_jellyfin(
            bundled_libraries(roots["library"]),
            admin=(ADMIN["username"], ADMIN["password"]),
            users={CREW["username"]: CREW["password"]},
        ),
        tmdb=FakeTmdbClient(
            details=[SPY],
            seasons=SEASONS,
            ordering=ORDERING,
            translations={120089: "SPY×FAMILY 間諜家家酒"},
        ),
    )


@pytest.fixture
def client(
    config: Config, tmp_path: Path, roots: dict[str, Path], factory: FakeClientFactory
) -> Iterator[TestClient]:
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app) as running:
        _seed(running, roots, factory)
        yield running


def _seed(client: TestClient, roots: dict[str, Path], factory: FakeClientFactory) -> None:
    async def run() -> None:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            await arrange(session, roots)
            await write_settings(
                session,
                TmdbSettings(api_key=TMDB_API_KEY, image_base_url="https://image.tmdb.org/t/p/"),
            )
            await session.commit()
            await build_routes(session, factory, ())
            await complete_setup(session)

    asyncio.run(run())


def sign_in(client: TestClient, who: dict[str, str] = ADMIN) -> httpx.Response:
    response: httpx.Response = client.post("/api/auth/login", json=who, headers=BROWSER)
    return response


def route_id(client: TestClient, slug: str = "tv") -> int:
    async def run() -> int:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            from sqlalchemy import select

            row = await session.scalar(select(Route).where(Route.slug == slug))
            assert row is not None
            return int(row.id)

    return asyncio.run(run())


def make_route_red(client: TestClient, slug: str = "tv") -> None:
    async def run() -> None:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            from sqlalchemy import select

            row = await session.scalar(select(Route).where(Route.slug == slug))
            assert row is not None
            row.health_status = HealthStatus.FAILED
            await session.commit()

    asyncio.run(run())


def body(client: TestClient, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "source": {"url": MAGNET, "title": RELEASE, "info_hash": ""},
        "media": SPY_ID,
        "route": route_id(client),
    }
    return payload | overrides


def submit(client: TestClient, **overrides: object) -> httpx.Response:
    # 詳情頁先開過一次，`media` 那一列才存在（快照要有地方放，plan §2.2）。
    client.get(f"/api/media/{SPY_ID}")
    response: httpx.Response = client.post(
        "/api/jobs", json=body(client, **overrides), headers=BROWSER
    )
    return response


class TestGate:
    def test_submitting_needs_a_session(self, client: TestClient) -> None:
        assert client.post("/api/jobs", json={}, headers=BROWSER).status_code == 401

    def test_reading_the_list_needs_a_session(self, client: TestClient) -> None:
        assert client.get("/api/jobs").status_code == 401

    def test_an_ordinary_user_may_submit(self, client: TestClient) -> None:
        """送單本來就是一般使用者做的事（brief §11）——只有設定才要 admin。"""
        sign_in(client, CREW)

        assert submit(client).status_code == 200

    def test_a_cross_site_form_post_is_refused(self, client: TestClient) -> None:
        sign_in(client)
        client.get(f"/api/media/{SPY_ID}")

        assert client.post("/api/jobs", json=body(client)).status_code == 403


class TestSubmitting:
    def test_a_submitted_job_comes_back_with_its_route_and_media(self, client: TestClient) -> None:
        sign_in(client)

        payload = submit(client).json()

        assert payload["created"] is True
        job = payload["job"]
        assert job["hash"] == MAGNET_HASH
        assert job["error"] == ""
        assert job["state"] == "submitted"
        assert job["trigger"] == "manual"
        assert job["route_slug"] == "tv"
        assert job["media_id"] == SPY_ID
        assert (job["media_title"], job["media_title_en"]) == (
            "SPY×FAMILY 間諜家家酒",
            "SPY x FAMILY",
        )
        assert job["user_name"] == "skipper"
        assert job["retryable"] is False

    def test_the_same_torrent_twice_returns_the_same_job(self, client: TestClient) -> None:
        sign_in(client)
        submit(client)

        payload = submit(client).json()

        assert payload["created"] is False
        assert payload["job"]["hash"] == MAGNET_HASH
        assert len(client.get("/api/jobs").json()) == 1

    def test_the_timeline_reads_oldest_first(self, client: TestClient) -> None:
        sign_in(client)
        submit(client)

        events = client.get(f"/api/jobs/{MAGNET_HASH}/events").json()

        assert [row["type"] for row in events] == ["created", "submitted"]
        assert events[1]["payload"]["category"] == "berth-tv"

    def test_the_media_page_now_says_it_is_tracked_and_frozen(self, client: TestClient) -> None:
        """兩件事在同一刻發生：Berth 為這部作品做過事了，而那串資料夾名定死了。"""
        sign_in(client)
        before = client.get(f"/api/media/{SPY_ID}").json()
        assert (before["tracked"], before["folder_frozen"]) == (False, False)

        submit(client)

        after = client.get(f"/api/media/{SPY_ID}").json()
        assert (after["tracked"], after["folder_frozen"]) == (True, True)
        assert after["default_route_id"] == route_id(client)

    def test_the_discover_wall_reads_the_same_derivation(self, client: TestClient) -> None:
        sign_in(client)
        submit(client)

        items = client.get("/api/discover/trending").json()["items"]

        assert all("tracked" in item for item in items)


class TestRefusals:
    def test_a_red_route_is_a_conflict_with_a_reason(self, client: TestClient) -> None:
        """紅的 Route 送單一定失敗（brief §4.4）。409 而不是 422：請求本身沒問題，
        修好那條 Route 之後同一個請求就會成功。"""
        sign_in(client)
        make_route_red(client)

        response = submit(client)

        assert response.status_code == 409
        assert response.json()["detail"]["reason"] == "route_unhealthy"
        assert client.get("/api/jobs").json() == []

    def test_a_route_that_cannot_hold_this_kind_is_unprocessable(self, client: TestClient) -> None:
        sign_in(client)

        response = submit(client, route=route_id(client, "movies"))

        assert response.status_code == 422
        assert response.json()["detail"]["reason"] == "route_kind_mismatch"

    def test_an_unknown_media_is_unprocessable(self, client: TestClient) -> None:
        sign_in(client)

        response = submit(client, media="tv:999999")

        assert response.status_code == 422
        assert response.json()["detail"]["reason"] == "media_missing"

    def test_an_indexer_that_cannot_give_the_torrent_is_a_bad_gateway(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        """502：問題在 Berth 與索引站之間，而使用者送的東西沒有錯。"""
        sign_in(client)
        factory.torrent_.error = NotATorrentError("indexer.invalid: 200 text/html")

        response = submit(client)

        assert response.status_code == 502
        assert response.json()["detail"]["reason"] == "source_unavailable"
        assert "text/html" in response.json()["detail"]["detail"]

    def test_a_missing_job_is_a_404(self, client: TestClient) -> None:
        sign_in(client)

        assert client.get("/api/jobs/0000000000").status_code == 404

    def test_retrying_a_job_that_is_not_failed_is_a_conflict(self, client: TestClient) -> None:
        sign_in(client)
        submit(client)

        response = client.post(f"/api/jobs/{MAGNET_HASH}/retry", headers=BROWSER)

        assert response.status_code == 409
        assert response.json()["detail"]["reason"] == "not_retryable"


class TestSubmitFailed:
    def test_qbittorrent_refusing_still_answers_200_with_the_failed_job(
        self, client: TestClient, factory: FakeClientFactory, roots: dict[str, Path]
    ) -> None:
        """**不是 HTTP 錯誤**：Job 已經建好了，畫面要顯示的是那一列加上一顆重試。"""
        from berth.adapters.http import ServiceUnavailableError

        sign_in(client)
        factory.qbittorrent_.add_error = ServiceUnavailableError("connection refused")

        payload = submit(client).json()

        assert payload["created"] is True
        assert payload["job"]["state"] == "submit_failed"
        assert "refused" in payload["job"]["error"]
        assert payload["job"]["retryable"] is True

    def test_retrying_after_the_service_comes_back_succeeds(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        from berth.adapters.http import ServiceUnavailableError

        sign_in(client)
        factory.qbittorrent_.add_error = ServiceUnavailableError("connection refused")
        submit(client)
        factory.qbittorrent_.add_error = None

        job = client.post(f"/api/jobs/{MAGNET_HASH}/retry", headers=BROWSER).json()

        assert job["state"] == "submitted"
        assert job["error"] == ""


class TestDeleteScope:
    """`DELETE /jobs/{hash}` 的四個旗標與估算那一支（brief §9.2、M2 票 04）。

    命令本身的行為在 `test_deletion.py` 貼著磁碟驗；這裡驗的是 HTTP 那一層——預設值、
    拒絕的狀態碼與理由，以及「真的做了什麼」有沒有原樣回到畫面上。
    """

    def test_the_four_flags_default_to_off(self, client: TestClient) -> None:
        """一個參數都不帶時什麼都不刪（brief §9.2）：預設在後端也成立，不只在對話框上。"""
        sign_in(client)
        submit(client)

        response = client.delete(f"/api/jobs/{MAGNET_HASH}", headers=BROWSER)

        assert response.status_code == 200
        assert response.json() == {
            "links": 0,
            "sources": 0,
            "torrent": False,
            "purged": False,
            "freed": 0,
        }

    def test_deleting_files_without_removing_the_torrent_is_422_with_a_reason(
        self, client: TestClient
    ) -> None:
        sign_in(client)
        submit(client)

        response = client.delete(f"/api/jobs/{MAGNET_HASH}?delete_files=true", headers=BROWSER)

        assert response.status_code == 422
        assert response.json()["detail"]["reason"] == "delete_files_requires_remove_torrent"

    def test_a_job_that_is_not_there_is_404_with_a_reason(self, client: TestClient) -> None:
        sign_in(client)

        response = client.delete(f"/api/jobs/{MAGNET_HASH}", headers=BROWSER)

        assert response.status_code == 404
        assert response.json()["detail"]["reason"] == "job_missing"

    def test_removing_the_torrent_says_so_in_the_answer(self, client: TestClient) -> None:
        sign_in(client)
        submit(client)

        response = client.delete(f"/api/jobs/{MAGNET_HASH}?remove_torrent=true", headers=BROWSER)

        assert response.status_code == 200
        assert response.json()["torrent"] is True

    def test_purging_takes_the_job_off_the_list(self, client: TestClient) -> None:
        sign_in(client)
        submit(client)

        client.delete(f"/api/jobs/{MAGNET_HASH}?purge=true", headers=BROWSER)

        assert client.get("/api/jobs").json() == []

    def test_without_purge_it_stays_on_the_list_as_removed(self, client: TestClient) -> None:
        sign_in(client)
        submit(client)

        client.delete(f"/api/jobs/{MAGNET_HASH}", headers=BROWSER)

        assert [row["state"] for row in client.get("/api/jobs").json()] == ["removed"]

    def test_the_estimate_answers_before_anything_is_deleted(self, client: TestClient) -> None:
        """送單當下還沒有檔案，所以每一格都是 0——**而且那一筆 Job 一點都沒有變**。"""
        sign_in(client)
        submit(client)

        response = client.get(f"/api/jobs/{MAGNET_HASH}/deletion")

        assert response.status_code == 200
        assert response.json()["reclaimable"] == 0
        assert [row["state"] for row in client.get("/api/jobs").json()] == ["submitted"]

    def test_the_estimate_of_a_job_that_is_not_there_is_404(self, client: TestClient) -> None:
        sign_in(client)

        response = client.get(f"/api/jobs/{MAGNET_HASH}/deletion")

        assert response.status_code == 404
        assert response.json()["detail"]["reason"] == "job_missing"

    def test_an_ordinary_user_can_neither_delete_nor_estimate(self, client: TestClient) -> None:
        """刪除與它的估算都是 admin（plan §6）。送單與清單照常——那一條在
        `test_auth_api.py` 的門禁那一組。"""
        sign_in(client, ADMIN)
        submit(client)
        client.post("/api/auth/logout", headers=BROWSER)
        sign_in(client, CREW)

        assert client.delete(f"/api/jobs/{MAGNET_HASH}", headers=BROWSER).status_code == 403
        assert client.get(f"/api/jobs/{MAGNET_HASH}/deletion").status_code == 403
        assert client.get("/api/jobs").status_code == 200


class TestReimport:
    """`POST /jobs/{hash}/reimport`（M2 票 10）。流程本身在 `test_reimport.py`，
    這裡只看門與形狀。"""

    def test_an_ordinary_user_cannot_reimport_but_still_reads_the_list(
        self, client: TestClient
    ) -> None:
        """驗收：`user` 登入時是 403，而 `GET /jobs` 照常（plan §6、brief §11）。"""
        sign_in(client, ADMIN)
        submit(client)
        client.post("/api/auth/logout", headers=BROWSER)
        sign_in(client, CREW)

        assert client.post(f"/api/jobs/{MAGNET_HASH}/reimport", headers=BROWSER).status_code == 403
        assert client.get("/api/jobs").status_code == 200

    def test_a_job_still_in_the_client_is_not_reimportable(self, client: TestClient) -> None:
        """剛送出去的那一筆還在下載：409，而且列上的旗標事先就說了不行。"""
        sign_in(client)
        submit(client)

        response = client.post(f"/api/jobs/{MAGNET_HASH}/reimport", headers=BROWSER)

        assert response.status_code == 409
        assert response.json()["detail"]["reason"] == "not_reimportable"
        assert [row["reimportable"] for row in client.get("/api/jobs").json()] == [False]

    def test_a_job_that_is_not_there_is_404(self, client: TestClient) -> None:
        sign_in(client)

        response = client.post(f"/api/jobs/{MAGNET_HASH}/reimport", headers=BROWSER)

        assert response.status_code == 404
        assert response.json()["detail"]["reason"] == "job_missing"
