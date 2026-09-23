"""`POST /files/rematch` 與重複版本的三顆（plan §6 files / review 群組、M2 票 08 驗收）。

命令本身在 `test_rematch.py` 與 `test_duplicates.py`；這裡驗的是**形狀、狀態碼與「誰進得來」**：

- `files/*` 與 `review/*` 只有 `admin`（plan §6、brief §11）。票上那一條驗收。
- 佇列上的 `unmatched` 列指向的 `ref` 就是 `POST /files/rematch` 的 `job_file_id`：`/review` 與
  Media 詳情打的是同一支（票上「不是兩套邏輯」那一條，Media 詳情那一半在 `test_media_api.py`）。
- 拒絕是 `{reason, detail}`，理由是封閉集合。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from berth.api.deps import get_client_factory
from berth.config import Config
from berth.main import create_app
from berth.services.setup import complete_setup
from tests.integration.factories import FakeClientFactory
from tests.integration.test_duplicates import SAME, SAME_FILES, first_batch, second_download
from tests.integration.test_media import SPY_ID
from tests.integration.test_rematch import OVA, imported, ova
from tests.integration.test_review_api import ADMIN, BROWSER, CREW, sign_in

# 同一個 fixture（假 Jellyfin 認得 skipper 與 deckhand）；`as` 讓 import 本身說出它是要再匯出的。
from tests.integration.test_review_api import factory as factory


@pytest.fixture
def client(
    config: Config, tmp_path: Path, roots: dict[str, Path], factory: FakeClientFactory
) -> Iterator[TestClient]:
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app) as running:
        yield running


def seed_unmatched(client: TestClient, roots: dict[str, Path]) -> int:
    """一筆入庫完、夾著一個對不到的 OVA 的批次（`test_rematch.imported`）。

    回 OVA 的 job file id。
    """

    async def run() -> int:
        # `app.state` 是 Starlette 的動態屬性，型別上看不到 lifespan 掛上去的 session factory。
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            await imported(session, roots)
            await complete_setup(session)
            await session.commit()
            return (await ova(session)).id

    return asyncio.run(run())


def seed_duplicate(client: TestClient, roots: dict[str, Path]) -> None:
    async def run() -> None:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            media, route, factory = await first_batch(session, roots)
            await second_download(
                session, roots, media, route, factory, name=SAME, files=SAME_FILES
            )
            await complete_setup(session)
            await session.commit()

    asyncio.run(run())


class TestWhoGetsIn:
    def test_an_ordinary_user_is_refused(self, client: TestClient, roots: dict[str, Path]) -> None:
        """acceptance：`user` 登入時 `/files/*` 是 403，重複版本的三顆也是。"""
        file_id = seed_unmatched(client, roots)
        sign_in(client, CREW)

        rematch = client.post(
            "/api/files/rematch",
            json={"job_file_id": file_id, "action": "skip"},
            headers=BROWSER,
        )
        decide = client.post("/api/review/duplicate/1/skip", headers=BROWSER)

        assert rematch.status_code == 403
        assert decide.status_code == 403

    def test_anonymous_is_401(self, client: TestClient, roots: dict[str, Path]) -> None:
        file_id = seed_unmatched(client, roots)
        response = client.post(
            "/api/files/rematch", json={"job_file_id": file_id, "action": "skip"}, headers=BROWSER
        )
        assert response.status_code == 401


class TestRematch:
    def test_the_queue_row_points_at_what_rematch_takes(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        """`/review` 的 `unmatched` 列的 `ref` 送進 `POST /files/rematch` 就是那一個檔案。"""
        file_id = seed_unmatched(client, roots)
        sign_in(client, ADMIN)

        (row,) = [
            row for row in client.get("/api/review").json()["rows"] if row["kind"] == "unmatched"
        ]
        response = client.post(
            "/api/files/rematch",
            json={"job_file_id": row["ref"], "action": "import", "season": 0, "episode_start": 3},
            headers=BROWSER,
        )

        assert row["ref"] == file_id
        assert row["reason"] == {"code": "left_in_place", "params": {}}
        assert row["actions"] == ["import", "extra", "skip"]
        assert row["media_kind"] == "tv"
        assert row["path"].endswith(OVA.rsplit("/", 1)[1])
        assert response.status_code == 200
        body = response.json()
        assert "S00E03" in body["target_path"]
        assert isinstance(body["plan_id"], int)
        rows = client.get("/api/review").json()["rows"]
        assert [row["kind"] for row in rows if row["kind"] == "unmatched"] == []

    def test_exactly_one_of_the_two_ids(self, client: TestClient, roots: dict[str, Path]) -> None:
        seed_unmatched(client, roots)
        sign_in(client, ADMIN)

        neither = client.post("/api/files/rematch", json={"action": "skip"}, headers=BROWSER)
        both = client.post(
            "/api/files/rematch",
            json={"ledger_id": 1, "job_file_id": 1, "action": "skip"},
            headers=BROWSER,
        )

        assert neither.status_code == 422
        assert both.status_code == 422

    @pytest.mark.parametrize(
        ("body", "status", "reason"),
        [
            ({"job_file_id": 999, "action": "skip"}, 404, "file_missing"),
            ({"ledger_id": 999, "action": "skip"}, 404, "ledger_missing"),
            ({"action": "import"}, 422, "episode_required"),
            ({"action": "subtitle"}, 422, "action_not_allowed"),
        ],
    )
    def test_a_refusal_is_a_reason_and_a_detail(
        self,
        client: TestClient,
        roots: dict[str, Path],
        body: dict[str, object],
        status: int,
        reason: str,
    ) -> None:
        file_id = seed_unmatched(client, roots)
        sign_in(client, ADMIN)
        sent = (
            body
            if "ledger_id" in body or "job_file_id" in body
            else {**body, "job_file_id": file_id}
        )

        response = client.post("/api/files/rematch", json=sent, headers=BROWSER)

        assert response.status_code == status
        assert response.json()["detail"]["reason"] == reason


class TestDuplicates:
    def test_a_duplicate_row_and_its_three_buttons(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        seed_duplicate(client, roots)
        sign_in(client, ADMIN)

        (row,) = [
            row for row in client.get("/api/review").json()["rows"] if row["kind"] == "duplicate"
        ]

        assert row["reason"] == {"code": "same_version", "params": {}}
        assert row["actions"] == ["replace", "keep_both", "skip"]
        assert (row["season"], row["episode_start"]) == (1, 2)
        assert row["known_path"].endswith("S01E02 [1080p][CHT][Group].mkv")

    def test_deciding_takes_it_off_the_queue(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        seed_duplicate(client, roots)
        sign_in(client, ADMIN)
        (row,) = [
            row for row in client.get("/api/review").json()["rows"] if row["kind"] == "duplicate"
        ]

        response = client.post(f"/api/review/duplicate/{row['ref']}/keep_both", headers=BROWSER)

        assert response.status_code == 200
        assert response.json()["target_path"].endswith("[2].mkv")
        again = client.post(f"/api/review/duplicate/{row['ref']}/skip", headers=BROWSER)
        assert again.status_code == 409
        assert again.json()["detail"]["reason"] == "not_duplicate"

    def test_skipping_answers_with_nothing_landed(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        seed_duplicate(client, roots)
        sign_in(client, ADMIN)
        (row,) = [
            row for row in client.get("/api/review").json()["rows"] if row["kind"] == "duplicate"
        ]

        response = client.post(f"/api/review/duplicate/{row['ref']}/skip", headers=BROWSER)

        assert response.status_code == 200
        assert response.json() == {"plan_id": None, "target_path": ""}

    def test_an_unknown_decision_is_422(self, client: TestClient, roots: dict[str, Path]) -> None:
        seed_duplicate(client, roots)
        sign_in(client, ADMIN)
        assert client.post("/api/review/duplicate/1/delete", headers=BROWSER).status_code == 422


class TestTheMediaPage:
    """Media 詳情的修正入口打的是同一支（票上「不是兩套邏輯」那一條）。"""

    def test_its_unmatched_row_is_the_queues_row(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        file_id = seed_unmatched(client, roots)
        sign_in(client, ADMIN)

        media = client.get(f"/api/media/{SPY_ID}").json()
        (row,) = [r for r in client.get("/api/review").json()["rows"] if r["kind"] == "unmatched"]

        (unmatched,) = media["unmatched"]
        assert unmatched["job_file_id"] == row["ref"] == file_id
        assert unmatched["actions"] == row["actions"] == ["import", "extra", "skip"]

    def test_a_linked_file_offers_the_same_three_and_a_subtitle_none(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        seed_unmatched(client, roots)
        sign_in(client, ADMIN)

        files = client.get(f"/api/media/{SPY_ID}").json()["files"]

        actions = {file["action"]: file["actions"] for file in files}
        assert actions["import"] == ["import", "extra", "skip"]
        assert actions["extra"] == ["import", "extra", "skip"]
        assert actions["subtitle"] == []

    def test_fixing_a_linked_file_from_the_media_page(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        """檔案清單那一列的 `id` 就是 `ledger_id`：改到 S01E05 之後清單上它說的是 S01E05。"""
        seed_unmatched(client, roots)
        sign_in(client, ADMIN)
        files = client.get(f"/api/media/{SPY_ID}").json()["files"]
        third = next(f for f in files if f["action"] == "import" and f["episode_start"] == 3)

        response = client.post(
            "/api/files/rematch",
            json={"ledger_id": third["id"], "action": "import", "season": 1, "episode_start": 5},
            headers=BROWSER,
        )

        assert response.status_code == 200
        after = {f["id"]: f for f in client.get(f"/api/media/{SPY_ID}").json()["files"]}
        assert after[third["id"]]["episode_start"] == 5
        assert after[third["id"]]["target_path"] == response.json()["target_path"]
