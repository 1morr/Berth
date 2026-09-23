"""plans 的寫入端點與佇列上的 `plan` 那一類（plan §6 plans / review 群組、M2 票 07 驗收）。

命令本身在 `test_plan_review.py`；這裡驗的是**形狀、狀態碼與「誰進得來」**，以及核准之後
背景的 importer 真的被叫醒、檔案真的進了媒體庫——那一段只有整個 app 跑起來才看得到。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from berth.api.deps import get_client_factory
from berth.config import Config
from berth.domain import IssueType
from berth.main import create_app
from berth.services.issues import record_issue
from berth.services.setup import complete_setup
from tests.integration.arrange import bundled_libraries, factory_for, fake_jellyfin
from tests.integration.factories import FakeClientFactory
from tests.integration.test_plan import HASH
from tests.integration.test_plan_review import held
from tests.integration.test_review_api import ADMIN, BROWSER, CREW, sign_in


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


def seed_held(client: TestClient, roots: dict[str, Path], *, with_issue: bool = False) -> int:
    """一份停在 review 的低信心 Plan（`test_plan_review.held`），回 Plan 的 id。"""

    async def run() -> int:
        # `app.state` 是 Starlette 的動態屬性，型別上看不到 lifespan 掛上去的 session factory。
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            if with_issue:
                await record_issue(
                    session, IssueType.LIBRARY_LINK_MISSING, path="/data/library/tv/a.mkv"
                )
            _, _, _, plan_id = await held(session, roots)
            await complete_setup(session)
            await session.commit()
            return plan_id

    return asyncio.run(run())


def items_of(client: TestClient, plan_id: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = client.get(f"/api/plans/{plan_id}").json()["items"]
    return rows


def video_of(client: TestClient, plan_id: int) -> dict[str, Any]:
    return next(row for row in items_of(client, plan_id) if row["rel_path"].endswith(".mkv"))


def state_of(client: TestClient) -> str:
    state: str = client.get(f"/api/jobs/{HASH}").json()["state"]
    return state


def events_of(client: TestClient) -> list[str]:
    return [row["type"] for row in client.get(f"/api/jobs/{HASH}/events").json()]


def settle(done: Callable[[], bool]) -> None:
    """等背景迴圈把這一輪做完。

    **不只是為了斷言**：測試結束時 TestClient 會取消還在跑的迴圈，取消在一個查詢的半途時那一條
    aiosqlite 連線沒有人關，GC 到下一個測試模組才炸（`ResourceWarning`，第一次全量跑時抓到）。
    所以每一條叫醒迴圈的測試都要等到那一輪的**最後一步**。
    """
    deadline = time.monotonic() + 10
    while not done() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert done()


class TestWhoGetsIn:
    """票上那一條驗收：`user` 登入時 `/plans/{id}/items`、`approve`、`reject` 全是 403。"""

    def test_an_ordinary_user_reads_the_plan_but_cannot_decide_it(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        plan_id = seed_held(client, roots)
        sign_in(client, CREW)
        video = video_of(client, plan_id)

        edit = {"items": [{"id": video["id"], "action": "skip"}]}
        assert (
            client.put(f"/api/plans/{plan_id}/items", json=edit, headers=BROWSER).status_code == 403
        )
        for decision in ("approve", "reject"):
            response = client.post(f"/api/plans/{plan_id}/{decision}", headers=BROWSER)
            assert response.status_code == 403
        # 讀得到：停下來的是他自己送的那一筆，他看得到為什麼（`GET /plans/*` 不在 admin 名單上）。
        assert video["actions"] != []
        assert state_of(client) == "review"


class TestTheQueue:
    def test_a_held_plan_comes_first_and_carries_a_code(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        """票 06 定的排序：`plan` 在「要你決定」那一組，排在 Issue 前面——即使 Issue 比較舊。"""
        plan_id = seed_held(client, roots, with_issue=True)
        sign_in(client)

        rows = client.get("/api/review").json()["rows"]

        assert [row["kind"] for row in rows] == ["plan", "issue"]
        plan = rows[0]
        assert plan["ref"] == plan_id
        assert plan["reason"] == {
            "code": "low_confidence",
            "params": {"files": 0, "low": 2, "medium": 0},
        }
        assert plan["actions"] == ["approve", "reject"]
        assert (plan["job_hash"], plan["title_en"]) == (HASH, "SPY x FAMILY")


class TestEditing:
    def test_an_edit_comes_back_with_the_new_target(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        plan_id = seed_held(client, roots)
        sign_in(client)
        video = video_of(client, plan_id)

        response = client.put(
            f"/api/plans/{plan_id}/items",
            json={
                "items": [{"id": video["id"], "action": "import", "season": 2, "episode_start": 5}]
            },
            headers=BROWSER,
        )

        assert response.status_code == 200
        moved = next(row for row in response.json()["items"] if row["id"] == video["id"])
        assert " - S02E05" in moved["target_path"]
        assert {"code": "set_by_user", "params": {}} in moved["reasons"]

    def test_a_reversed_range_is_a_422_with_its_reason(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        plan_id = seed_held(client, roots)
        sign_in(client)
        video = video_of(client, plan_id)

        response = client.put(
            f"/api/plans/{plan_id}/items",
            json={
                "items": [
                    {
                        "id": video["id"],
                        "action": "import",
                        "season": 1,
                        "episode_start": 6,
                        "episode_end": 5,
                    }
                ]
            },
            headers=BROWSER,
        )

        assert response.status_code == 422
        assert response.json()["detail"]["reason"] == "episode_range_reversed"

    def test_the_same_row_twice_in_one_request_is_refused(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        """整批成立或整批拒絕：同一列出現兩次時說不出哪一個算數，所以不是「後者蓋前者」。"""
        plan_id = seed_held(client, roots)
        sign_in(client)
        video = video_of(client, plan_id)
        twice = [{"id": video["id"], "action": "skip"}, {"id": video["id"], "action": "extra"}]

        response = client.put(f"/api/plans/{plan_id}/items", json={"items": twice}, headers=BROWSER)

        assert response.status_code == 422
        assert video_of(client, plan_id)["action"] == "review"


class TestDeciding:
    def test_approving_wakes_the_importer_and_the_files_land(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        """核准 → `importing` → 背景的 importer 被叫醒 → 媒體庫裡真的有那兩個檔案。"""
        plan_id = seed_held(client, roots)
        sign_in(client)
        shown = [row["target_path"] for row in items_of(client, plan_id)]

        response = client.post(f"/api/plans/{plan_id}/approve", headers=BROWSER)

        assert response.status_code == 200
        assert response.json()["status"] == "approved"
        # 入庫那一輪的最後一步是通知 Jellyfin（狀態落地之後才通知，plan §3.3）。
        settle(lambda: "jellyfin_scan_requested" in events_of(client))
        assert state_of(client) == "imported"
        library = roots["library"] / "anime"
        assert all((library / target).exists() for target in shown)

    def test_rejecting_is_204_and_says_so_on_the_timeline(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        plan_id = seed_held(client, roots)
        sign_in(client)

        assert client.post(f"/api/plans/{plan_id}/reject", headers=BROWSER).status_code == 204

        events = client.get(f"/api/jobs/{HASH}/events").json()
        decided = [row for row in events if row["type"] == "review_decided"]
        assert [row["payload"]["decision"] for row in decided] == ["rejected"]
        # 規劃器被叫醒、整份重算，又停回 review（plan §3.1）——不必等 60 秒那一輪。
        settle(lambda: events_of(client).count("review_required") == 2)
        assert state_of(client) == "review"

    def test_deciding_twice_is_409(self, client: TestClient, roots: dict[str, Path]) -> None:
        plan_id = seed_held(client, roots)
        sign_in(client)
        client.post(f"/api/plans/{plan_id}/approve", headers=BROWSER)

        response = client.post(f"/api/plans/{plan_id}/reject", headers=BROWSER)

        assert response.status_code == 409
        assert response.json()["detail"]["reason"] == "not_pending"
        # 核准叫醒了 importer：等它那一輪做完再離開（`settle` 的理由）。
        settle(lambda: "jellyfin_scan_requested" in events_of(client))
