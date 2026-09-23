"""issues 與 reconcile 端點（plan §6 issues 群組、M2 票 05 驗收）。

命令本身在 `test_issues.py` / `test_issue_actions.py` / `test_reconcile.py`；這裡驗的是
**形狀、狀態碼與「誰進得來」**：

- `issues/*` 與 `reconcile` 整組只有 `admin`（plan §6，2026-09-22 拍板）。票上那一條驗收。
- `POST /reconcile` 回 **202** 並給這一輪的 id；跑的時候再按是 **409** `reconcile_running`
  （plan §3.2）。**不排隊**——排隊的那一輪看到的會是同一份磁碟。
- `GET /reconcile` 在還沒跑過的時候兩格都是 `null`，而那兩個 `null` 意思不同。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient

from berth.adapters.http import ServiceUnavailableError
from berth.api.deps import get_client_factory
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.domain import IssueType, JobState, JobTrigger
from berth.main import create_app
from berth.models import Job
from berth.services.issues import record_issue
from berth.services.reconcile import ReconcileRunner
from berth.services.routes import build_routes
from berth.services.setup import complete_setup
from tests.integration.arrange import arrange, bundled_libraries, factory_for, fake_jellyfin
from tests.integration.factories import FakeClientFactory

BROWSER = {CSRF_HEADER: "XMLHttpRequest"}
ADMIN = {"username": "skipper", "password": "harbour"}
CREW = {"username": "deckhand", "password": "rope"}

TARGET = "/data/library/tv/Show (2020)/Season 01/Show - S01E01.mkv"
HASH = "4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b"


@pytest.fixture
def factory(roots: dict[str, Path]) -> FakeClientFactory:
    return factory_for(
        roots,
        jellyfin=fake_jellyfin(
            bundled_libraries(roots["library"]),
            admin=(ADMIN["username"], ADMIN["password"]),
            users={CREW["username"]: CREW["password"]},
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
            await build_routes(session, factory, ())
            await complete_setup(session)
            await session.commit()

    asyncio.run(run())


def open_issue(client: TestClient) -> int:
    """直接寫一筆 `open`：這一份驗的是端點，偵測那一段在 `test_reconcile.py`。"""

    async def run() -> int:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            recorded = await record_issue(session, IssueType.LIBRARY_LINK_MISSING, path=TARGET)
            await session.commit()
            return int(recorded.issue.id)

    return asyncio.run(run())


def sign_in(client: TestClient, who: dict[str, str] = ADMIN) -> None:
    assert client.post("/api/auth/login", json=who, headers=BROWSER).status_code == 200


class TestWhoGetsIn:
    """票上那一條驗收：`user` 登入時 `/issues/*` 與 `/reconcile` 全是 403。"""

    def test_an_ordinary_user_is_refused_everywhere(self, client: TestClient) -> None:
        issue_id = open_issue(client)
        sign_in(client, CREW)

        assert client.get("/api/issues").status_code == 403
        assert (
            client.post(
                f"/api/issues/{issue_id}/resolve", json={"action": "relink"}, headers=BROWSER
            ).status_code
            == 403
        )
        assert client.post(f"/api/issues/{issue_id}/ignore", headers=BROWSER).status_code == 403
        assert client.post("/api/reconcile", headers=BROWSER).status_code == 403
        assert client.get("/api/reconcile").status_code == 403

    def test_anonymous_is_401_not_403(self, client: TestClient) -> None:
        """沒登入是 401（前端據此導向 `/login`），登入了但不是 admin 才是 403。"""
        assert client.get("/api/issues").status_code == 401
        assert client.get("/api/reconcile").status_code == 401

    def test_an_administrator_gets_in(self, client: TestClient) -> None:
        sign_in(client)

        assert client.get("/api/issues").status_code == 200


class TestTheList:
    def test_it_carries_the_buttons_the_backend_worked_out(self, client: TestClient) -> None:
        """**`actions` 由後端算**：前端照這一格畫按鈕，不自己重算一份規則。

        這一筆沒有帳本也沒有 Job，所以三顆一顆都按不了——只剩「忽略」。
        """
        open_issue(client)
        sign_in(client)

        (row,) = client.get("/api/issues").json()

        assert row["type"] == "library_link_missing"
        assert row["path"] == TARGET
        assert row["status"] == "open"
        assert row["actions"] == []

    def test_it_is_empty_when_nothing_needs_deciding(self, client: TestClient) -> None:
        sign_in(client)

        assert client.get("/api/issues").json() == []


class TestPressingAButton:
    def test_ignoring_takes_it_off_the_list(self, client: TestClient) -> None:
        issue_id = open_issue(client)
        sign_in(client)

        response = client.post(f"/api/issues/{issue_id}/ignore", headers=BROWSER)

        assert response.status_code == 200
        assert response.json()["status"] == "ignored"
        assert client.get("/api/issues").json() == []

    def test_ignoring_it_twice_is_409(self, client: TestClient) -> None:
        """多半是另一個分頁先按了。請求本身沒問題，所以不是 422。"""
        issue_id = open_issue(client)
        sign_in(client)
        client.post(f"/api/issues/{issue_id}/ignore", headers=BROWSER)

        response = client.post(f"/api/issues/{issue_id}/ignore", headers=BROWSER)

        assert response.status_code == 409
        assert response.json()["detail"]["reason"] == "issue_not_open"

    def test_an_issue_that_is_not_there_is_404(self, client: TestClient) -> None:
        sign_in(client)

        response = client.post("/api/issues/404/ignore", headers=BROWSER)

        assert response.status_code == 404
        assert response.json()["detail"]["reason"] == "issue_missing"

    def test_a_button_this_issue_cannot_offer_is_422(self, client: TestClient) -> None:
        """那一顆對這一筆根本按不了（它指不到帳本），重送幾次都一樣——所以是 422 不是 409。"""
        issue_id = open_issue(client)
        sign_in(client)

        response = client.post(
            f"/api/issues/{issue_id}/resolve", json={"action": "relink"}, headers=BROWSER
        )

        assert response.status_code == 422
        assert response.json()["detail"]["reason"] == "action_not_available"

    def test_an_action_outside_the_closed_set_never_reaches_the_service(
        self, client: TestClient
    ) -> None:
        """`action` 是封閉集合（brief §9.1 那一欄），所以 pydantic 先擋下來。"""
        issue_id = open_issue(client)
        sign_in(client)

        response = client.post(
            f"/api/issues/{issue_id}/resolve", json={"action": "burn-it-all"}, headers=BROWSER
        )

        assert response.status_code == 422


class TestReconciling:
    def test_pressing_it_is_202_with_the_id_of_this_run(self, client: TestClient) -> None:
        """**202 不是 200**：那一輪在背景跑，回的是「收下了，這一輪是第幾號」。"""
        sign_in(client)

        response = client.post("/api/reconcile", headers=BROWSER)

        assert response.status_code == 202
        assert response.json()["id"] == 1

    def test_the_finished_run_says_what_each_side_found(self, client: TestClient) -> None:
        """`GET /reconcile` 的「哪一方比到哪、幾筆」（plan §3.2）。五方都要在（票 09）。"""
        sign_in(client)
        client.post("/api/reconcile", headers=BROWSER)

        last = client.get("/api/reconcile").json()["last"]

        assert last is not None
        assert last["finished_at"] is not None
        assert [row["side"] for row in last["sides"]] == [
            "ledger",
            "client",
            "complete",
            "library",
            "jellyfin",
        ]

    def test_nothing_has_run_yet_is_two_nulls(self, client: TestClient) -> None:
        """兩格都是 `null`，而意思不同：沒有在跑 / 這個程序起來之後還沒跑過。"""
        sign_in(client)

        assert client.get("/api/reconcile").json() == {"current": None, "last": None}

    def test_pressing_it_while_one_is_going_is_409(self, client: TestClient) -> None:
        """**不排隊**：排隊的那一輪看到的會是同一份磁碟（plan §3.2）。

        「正在跑的時候再按」那條規則本身在 `test_reconcile.py` 驗（那裡拿得到事件迴圈，
        不必跟一個背景 task 賽跑）。這裡驗的是它到了 HTTP 這一層是 409 與哪一個 `reason`。
        """
        sign_in(client)
        runner = client.app.state.reconciler  # type: ignore[attr-defined]

        with _pinned_as_running(runner):
            response = client.post("/api/reconcile", headers=BROWSER)

        assert response.status_code == 409
        assert response.json()["detail"]["reason"] == "reconcile_running"


@contextmanager
def _pinned_as_running(runner: ReconcileRunner) -> Iterator[None]:
    """把 runner 釘在「正在跑」，不必真的開一輪。

    `running` 問的是「有沒有一個還沒完成的 task」，所以一個永遠回 `False` 的 `done()`
    就夠了——真的去跑一輪再搶在它之前送第二個請求，測到的會是誰跑得快。
    """
    before = runner._task
    runner._task = cast("asyncio.Task[None]", _NeverDone())
    try:
        yield
    finally:
        runner._task = before


class _NeverDone:
    """`asyncio.Task` 在這一條規則裡唯一被問到的那個方法。"""

    def done(self) -> bool:
        return False


class TestTheDiskThreshold:
    """磁碟空間門檻在設定裡（M2 票 09c），改了立刻重量一次。"""

    def test_it_starts_at_ten_gigabytes(self, client: TestClient) -> None:
        sign_in(client)

        assert client.get("/api/settings/disk").json() == {"min_free_gb": 10}

    def test_raising_it_past_the_free_space_opens_an_issue_right_away(
        self, client: TestClient
    ) -> None:
        sign_in(client)

        saved = client.post("/api/settings/disk", json={"min_free_gb": 1_000_000}, headers=BROWSER)

        assert saved.json() == {"min_free_gb": 1_000_000}
        assert [row["type"] for row in client.get("/api/issues").json()] == ["low_disk_space"]

    def test_a_negative_threshold_is_refused(self, client: TestClient) -> None:
        sign_in(client)

        assert (
            client.post("/api/settings/disk", json={"min_free_gb": -1}, headers=BROWSER).status_code
            == 422
        )

    def test_an_ordinary_user_cannot_change_it(self, client: TestClient) -> None:
        sign_in(client, CREW)

        assert (
            client.post("/api/settings/disk", json={"min_free_gb": 0}, headers=BROWSER).status_code
            == 403
        )


class TestAPipelineButtonThatCannotReachTheClient:
    """驗收：問不到 qBittorrent 時按鈕說得出為什麼（502 `client_unreachable`），Issue 留著。"""

    def test_it_is_a_502_with_the_reason_and_the_issue_stays(
        self, client: TestClient, factory: FakeClientFactory
    ) -> None:
        async def run() -> int:
            sessions = client.app.state.session_factory  # type: ignore[attr-defined]  # app.state 是 Starlette 的動態屬性
            async with sessions() as session:
                session.add(
                    Job(
                        hash=HASH,
                        name="broken",
                        trigger=JobTrigger.MANUAL,
                        state=JobState.CLIENT_ERROR,
                    )
                )
                recorded = await record_issue(session, IssueType.CLIENT_ERROR, job_hash=HASH)
                await session.commit()
                return int(recorded.issue.id)

        issue_id = asyncio.run(run())
        factory.qbittorrent_.error = ServiceUnavailableError("connection refused")
        sign_in(client)

        pressed = client.post(
            f"/api/issues/{issue_id}/resolve", json={"action": "retry"}, headers=BROWSER
        )

        assert pressed.status_code == 502
        assert pressed.json()["detail"]["reason"] == "client_unreachable"
        assert [row["id"] for row in client.get("/api/issues").json()] == [issue_id]
