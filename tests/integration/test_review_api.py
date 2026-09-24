"""review 端點（plan §6 review 群組、M2 票 06 驗收）。

命令本身在 `test_review.py`；這裡驗的是**形狀、狀態碼與「誰進得來」**：

- `review/*` 整組只有 `admin`（plan §6、brief §11）。票上那一條驗收。
- 每一列的理由是**封閉集合的 code + 參數**，不是後端拼好的句子（前端翻譯）。
- 確認與撤銷走完整條：佇列上看得到 → 按下去 → 從佇列消失，時間線寫得出來。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from berth.api.deps import get_client_factory
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.domain import IssueType
from berth.main import create_app
from berth.services.issues import record_issue
from berth.services.setup import complete_setup
from tests.integration.arrange import bundled_libraries, factory_for, fake_jellyfin
from tests.integration.factories import FakeClientFactory
from tests.integration.test_plan import HASH
from tests.integration.test_review import audited

BROWSER = {CSRF_HEADER: "XMLHttpRequest"}
ADMIN = {"username": "skipper", "password": "harbour"}
CREW = {"username": "deckhand", "password": "rope"}


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
        yield running


def seed_audit(client: TestClient, roots: dict[str, Path]) -> tuple[int, str]:
    """一筆真的 medium 自動入庫（`test_review.audited`），回帳本那一列的 id 與目標路徑。"""

    async def run() -> tuple[int, str]:
        # `app.state` 是 Starlette 的動態屬性，型別上看不到 lifespan 掛上去的 session factory。
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            _, entry = await audited(session, roots)
            await complete_setup(session)
            await session.commit()
            return entry.id, entry.target_path

    return asyncio.run(run())


def seed_issue(client: TestClient) -> int:
    async def run() -> int:
        # `app.state` 是 Starlette 的動態屬性，型別上看不到 lifespan 掛上去的 session factory。
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            recorded = await record_issue(
                session, IssueType.LIBRARY_LINK_MISSING, path="/data/library/tv/a.mkv"
            )
            await session.commit()
            return int(recorded.issue.id)

    return asyncio.run(run())


def sign_in(client: TestClient, who: dict[str, str] = ADMIN) -> None:
    assert client.post("/api/auth/login", json=who, headers=BROWSER).status_code == 200


class TestWhoGetsIn:
    """票上那一條驗收：`user` 登入時 `/review/*` 全是 403。"""

    def test_an_ordinary_user_is_refused_everywhere(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        ledger_id, _ = seed_audit(client, roots)
        sign_in(client, CREW)

        assert client.get("/api/review").status_code == 403
        for action in ("confirm", "undo"):
            response = client.post(f"/api/review/audit/{ledger_id}/{action}", headers=BROWSER)
            assert response.status_code == 403
        many = client.post(
            "/api/review/audit/confirm", json={"ledger_ids": [ledger_id]}, headers=BROWSER
        )
        assert many.status_code == 403

    def test_anonymous_is_401_not_403(self, client: TestClient, roots: dict[str, Path]) -> None:
        seed_audit(client, roots)
        assert client.get("/api/review").status_code == 401

    def test_an_administrator_gets_in(self, client: TestClient, roots: dict[str, Path]) -> None:
        seed_audit(client, roots)
        sign_in(client)
        assert client.get("/api/review").status_code == 200


class TestTheQueue:
    def test_an_audit_row_carries_a_code_not_a_sentence(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        """acceptance：理由是封閉集合的 code + 參數，句子由前端照 code 挑。"""
        ledger_id, target = seed_audit(client, roots)
        sign_in(client)

        body = client.get("/api/review").json()

        assert body["total"] == 1
        (row,) = body["rows"]
        assert row["kind"] == "audit"
        assert row["ref"] == ledger_id
        assert row["reason"] == {"code": "medium_auto_imported", "params": {}}
        assert row["actions"] == ["confirm", "undo"]
        assert (row["path"], row["job_hash"]) == (target, HASH)

    def test_issues_are_not_rows_only_a_count(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        """acceptance：`/review` 沒有 Issue 列，原位那一行「另有 N 件待處理」要的是 `issues_open`。
        它不算在 `total` 裡——Issue 只在 `/issues`（brief §19，2026-09-24）。"""
        seed_audit(client, roots)
        seed_issue(client)
        sign_in(client)

        body = client.get("/api/review").json()

        assert [row["kind"] for row in body["rows"]] == ["audit"]
        assert (body["total"], body["queue_total"], body["issues_open"]) == (1, 1, 1)

    def test_an_issue_acted_on_leaves_the_count(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        seed_audit(client, roots)
        issue_id = seed_issue(client)
        sign_in(client)

        assert client.post(f"/api/issues/{issue_id}/ignore", headers=BROWSER).status_code == 200

        assert client.get("/api/review").json()["issues_open"] == 0


class TestConfirmMany:
    """「全部確認」（M3 票 05）：同一個 Job 一組、audit 段整段，都打這一支。"""

    def test_every_row_sent_leaves_the_queue(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        ledger_id, _ = seed_audit(client, roots)
        sign_in(client)

        response = client.post(
            "/api/review/audit/confirm", json={"ledger_ids": [ledger_id]}, headers=BROWSER
        )

        assert response.status_code == 200
        assert response.json() == {"confirmed": 1, "skipped": 0}
        assert client.get("/api/review").json()["rows"] == []
        events = [row["type"] for row in client.get(f"/api/jobs/{HASH}/events").json()]
        assert "audit_confirmed" in events

    def test_a_row_already_decided_is_skipped_not_a_conflict(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        """另一個分頁先撤銷了其中一列：照樣 200，說出跳過了幾列。"""
        ledger_id, _ = seed_audit(client, roots)
        sign_in(client)
        client.post(f"/api/review/audit/{ledger_id}/undo", headers=BROWSER)

        response = client.post(
            "/api/review/audit/confirm", json={"ledger_ids": [ledger_id, 404]}, headers=BROWSER
        )

        assert response.status_code == 200
        assert response.json() == {"confirmed": 0, "skipped": 2}


class TestConfirm:
    def test_it_is_204_and_the_row_leaves_the_queue(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        """acceptance：佇列上看得到 → 按確認 → 從佇列消失、時間線有 `audit_confirmed`。"""
        ledger_id, _ = seed_audit(client, roots)
        sign_in(client)

        response = client.post(f"/api/review/audit/{ledger_id}/confirm", headers=BROWSER)

        assert response.status_code == 204
        assert client.get("/api/review").json() == {
            "rows": [],
            "total": 0,
            "queue_total": 0,
            "issues_open": 0,
        }
        events = [row["type"] for row in client.get(f"/api/jobs/{HASH}/events").json()]
        assert "audit_confirmed" in events

    def test_confirming_twice_is_409(self, client: TestClient, roots: dict[str, Path]) -> None:
        ledger_id, _ = seed_audit(client, roots)
        sign_in(client)
        client.post(f"/api/review/audit/{ledger_id}/confirm", headers=BROWSER)

        response = client.post(f"/api/review/audit/{ledger_id}/confirm", headers=BROWSER)

        assert response.status_code == 409
        assert response.json()["detail"]["reason"] == "not_audited"

    def test_a_row_that_is_not_there_is_404(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        seed_audit(client, roots)
        sign_in(client)

        response = client.post("/api/review/audit/404/confirm", headers=BROWSER)

        assert response.status_code == 404
        assert response.json()["detail"]["reason"] == "ledger_missing"


class TestUndo:
    def test_the_whole_way_through(self, client: TestClient, roots: dict[str, Path]) -> None:
        """acceptance：硬鏈接沒了、帳本那一列沒了、Job 回 `review` 且 `review_reason =
        audit_undone`、時間線寫得出來——整條走 HTTP。"""
        ledger_id, target = seed_audit(client, roots)
        sign_in(client)

        response = client.post(f"/api/review/audit/{ledger_id}/undo", headers=BROWSER)

        assert response.status_code == 200
        assert response.json() == {"unlinked": True, "unmanaged": False}
        assert not Path(target).exists()
        # audit 那一列走了；回到 review 的那份 Plan 換成 `plan` 那一類等人（票 07）。
        rows = client.get("/api/review").json()["rows"]
        job = client.get(f"/api/jobs/{HASH}").json()
        assert [(row["kind"], row["ref"]) for row in rows] == [("plan", job["plan_id"])]
        assert job["state"] == "review"
        plan = client.get(f"/api/plans/{job['plan_id']}").json()
        assert plan["status"] == "pending_review"
        assert plan["summary"]["review_reason"] == "audit_undone"
        events = [row["type"] for row in client.get(f"/api/jobs/{HASH}/events").json()]
        assert events[-1] == "audit_undone"

    def test_undoing_twice_is_404(self, client: TestClient, roots: dict[str, Path]) -> None:
        """第一次已經把帳本那一列刪掉了，第二次找不到它。"""
        ledger_id, _ = seed_audit(client, roots)
        sign_in(client)
        client.post(f"/api/review/audit/{ledger_id}/undo", headers=BROWSER)

        response = client.post(f"/api/review/audit/{ledger_id}/undo", headers=BROWSER)

        assert response.status_code == 404
        assert response.json()["detail"]["reason"] == "ledger_missing"


class TestOneLibrary:
    """媒體庫頁的「待審 / 對不到」（M2 票 14）：`?library=` 只回那個媒體庫的 plan 與 unmatched，
    `queue_total` 仍是整份佇列——清單底下那一句「審核佇列裡還有 N 件」要的是它。"""

    def test_only_this_librarys_decisions_come_back(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        ledger_id, _ = seed_audit(client, roots)
        seed_issue(client)
        sign_in(client)
        # 撤銷之後那一筆回到 review：`plan` 那一類，在 anime Route 指向的 `item-2` 上。
        client.post(f"/api/review/audit/{ledger_id}/undo", headers=BROWSER)

        body = client.get("/api/review", params={"library": "item-2"}).json()

        assert [row["kind"] for row in body["rows"]] == ["plan"]
        # 整份佇列只剩那一份 Plan：Issue 不在佇列上（M3 票 05），它是另一個數字。
        assert (body["total"], body["queue_total"], body["issues_open"]) == (1, 1, 1)
        elsewhere = client.get("/api/review", params={"library": "item-9"}).json()
        assert (elsewhere["rows"], elsewhere["total"], elsewhere["queue_total"]) == ([], 0, 1)

    def test_without_it_the_two_totals_are_the_same(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        seed_audit(client, roots)
        seed_issue(client)
        sign_in(client)

        body = client.get("/api/review").json()

        assert (body["total"], body["queue_total"]) == (1, 1)

    def test_an_ordinary_user_is_still_refused(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        seed_audit(client, roots)
        sign_in(client, CREW)

        assert client.get("/api/review", params={"library": "item-2"}).status_code == 403
