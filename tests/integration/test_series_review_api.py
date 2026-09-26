"""RSS Series 的第一批審核走 API（M3 票 13、14b）：佇列上的 Series、整組確認、改正並套用（從已入庫
的與從停在審核的）、Plan 上的值。

命令本身在 `test_series_review.py`；這裡驗的是形狀、狀態碼與「誰進得來」（`review/*`、`files/*`
只有 admin）。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from berth.domain import MediaSnapshot
from berth.models import LedgerEntry, Plan, PlanItem
from berth.services.setup import complete_setup
from tests.integration.test_air_date_check import airing_split_cour
from tests.integration.test_plan_review_api import settle
from tests.integration.test_review_api import BROWSER, CREW, client, factory, sign_in
from tests.integration.test_series_review import delivered, split_cour

__all__ = ["client", "factory"]  # pytest fixture，從 review API 的測試借來


def seed(
    client: TestClient, roots: dict[str, Path], snapshot: MediaSnapshot | None = None
) -> tuple[int, list[int], list[int]]:
    """split-cour 的第一批入庫完：回 Series id、帳本 id（照集號）、兩份 Plan 的 id（照集號）。

    `snapshot` 換成連載中的那一份時，兩集都被播出日比對擋在審核、帳本是空的（票 14b）。
    """

    async def run() -> tuple[int, list[int], list[int]]:
        # `app.state` 是 Starlette 的動態屬性，型別上看不到 lifespan 掛上去的 session factory。
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            series, _ = await delivered(session, roots, snapshot=snapshot or split_cour())
            await complete_setup(session)
            await session.commit()
            entries = await session.scalars(
                select(LedgerEntry.id).order_by(LedgerEntry.source_rel_path)
            )
            plans = await session.scalars(
                select(Plan.id)
                .join(PlanItem, PlanItem.plan_id == Plan.id)
                .where(Plan.job_hash.is_not(None), PlanItem.rel_path.endswith(".mkv"))
                .order_by(PlanItem.rel_path)
            )
            return series.id, list(entries), list(plans)

    return asyncio.run(run())


def test_audit_rows_carry_their_series(client: TestClient, roots: dict[str, Path]) -> None:
    series_id, _, _ = seed(client, roots)
    sign_in(client)

    rows = client.get("/api/review").json()["rows"]

    assert {row["reason"]["code"] for row in rows} == {"first_batch"}
    assert {row["series"]["id"] for row in rows} == {series_id}
    assert {row["series"]["confirmed"] for row in rows} == {False}


def test_the_plan_says_which_values_it_used(client: TestClient, roots: dict[str, Path]) -> None:
    series_id, _, plans = seed(client, roots)
    sign_in(client)

    body = client.get(f"/api/plans/{plans[0]}").json()

    assert body["series"] == {"id": series_id, "season": None, "episode_offset": None}


def test_confirming_a_series_empties_its_group(client: TestClient, roots: dict[str, Path]) -> None:
    series_id, entries, _ = seed(client, roots)
    sign_in(client)

    response = client.post(
        f"/api/review/series/{series_id}/confirm", json={"ledger_ids": entries}, headers=BROWSER
    )

    assert response.status_code == 200
    assert response.json() == {"confirmed": 2, "skipped": 0}
    assert client.get("/api/review").json()["rows"] == []


def test_a_correction_applied_to_the_series_says_what_followed(
    client: TestClient, roots: dict[str, Path]
) -> None:
    series_id, (eleven, _), _ = seed(client, roots)
    sign_in(client)

    response = client.post(
        "/api/files/rematch",
        json={
            "ledger_id": eleven,
            "action": "import",
            "season": 1,
            "episode_start": 23,
            "apply_to_series": True,
        },
        headers=BROWSER,
    )

    assert response.status_code == 200, response.text
    assert response.json()["series"] == {
        "season": 1,
        "episode_offset": 12,
        "moved": 1,
        "replanned": 0,
        "left": 0,
    }
    rows = client.get("/api/review").json()["rows"]
    assert [(row["season"], row["episode_start"]) for row in rows] == [(1, 24)]
    assert rows[0]["series"] == {
        "id": series_id,
        "name": rows[0]["series"]["name"],
        "group": "喵萌奶茶屋&LoliHouse",
        "confirmed": False,
        "season": 1,
        "episode_offset": 12,
        # 還在等人的那一集照 Series 上的值讀（M4 票 11 的「在問什麼」）。
        "ask": {"spans": [{"season": 1, "start": 24, "end": 24}], "basis": "series"},
    }
    assert [reason["code"] for reason in rows[0]["reasons"]] == ["series_corrected"]


def test_applying_to_a_series_needs_a_file_in_the_library(
    client: TestClient, roots: dict[str, Path]
) -> None:
    seed(client, roots)
    sign_in(client)

    response = client.post(
        "/api/files/rematch",
        json={
            "job_file_id": 1,
            "action": "import",
            "season": 1,
            "episode_start": 1,
            "apply_to_series": True,
        },
        headers=BROWSER,
    )

    assert response.status_code == 422


def test_an_ordinary_user_cannot_confirm_a_series(
    client: TestClient, roots: dict[str, Path]
) -> None:
    series_id, entries, _ = seed(client, roots)
    sign_in(client, CREW)

    response = client.post(
        f"/api/review/series/{series_id}/confirm", json={"ledger_ids": entries}, headers=BROWSER
    )

    assert response.status_code == 403


def held_video(client: TestClient, plan_id: int) -> int:
    body = client.get(f"/api/plans/{plan_id}").json()
    found: int = next(item["id"] for item in body["items"] if item["rel_path"].endswith(".mkv"))
    return found


def test_a_correction_in_review_applied_to_the_series_says_what_followed(
    client: TestClient, roots: dict[str, Path]
) -> None:
    """連載中的 split-cour：兩集都停在審核。改第 11 集並套用，另一集重新規劃、通過比對入庫。"""
    series_id, entries, (eleven, twelve) = seed(client, roots, airing_split_cour())
    assert entries == []
    sign_in(client)
    row = held_video(client, eleven)

    response = client.put(
        f"/api/plans/{eleven}/items",
        json={
            "items": [{"id": row, "action": "import", "season": 1, "episode_start": 23}],
            "apply_to_series": True,
        },
        headers=BROWSER,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["corrected"] == {
        "season": 1,
        "episode_offset": 12,
        "moved": 0,
        "replanned": 1,
        "left": 0,
    }
    assert body["status"] == "pending_review"
    assert body["series"] == {"id": series_id, "season": 1, "episode_offset": 12}
    edited = next(item for item in body["items"] if item["id"] == row)
    assert (edited["season"], edited["episode_start"]) == (1, 23)
    other = client.get(f"/api/plans/{twelve}").json()
    assert other["status"] == "auto"
    # 重新規劃通過了比對，importer 被叫醒、把它入庫（也是 `settle` 說的：等那一輪做完）。
    settle(lambda: client.get(f"/api/jobs/{other['job_hash']}").json()["state"] == "imported")


def test_a_plain_edit_says_nothing_about_a_series(
    client: TestClient, roots: dict[str, Path]
) -> None:
    _, _, (eleven, _) = seed(client, roots, airing_split_cour())
    sign_in(client)
    row = held_video(client, eleven)

    response = client.put(
        f"/api/plans/{eleven}/items",
        json={"items": [{"id": row, "action": "import", "season": 1, "episode_start": 23}]},
        headers=BROWSER,
    )

    assert response.status_code == 200, response.text
    assert response.json()["corrected"] is None
    assert response.json()["series"]["episode_offset"] is None


def test_applying_to_a_series_takes_exactly_one_row(
    client: TestClient, roots: dict[str, Path]
) -> None:
    """兩列說的可能是兩個 offset：請求本身就不成立，還沒讀到資料庫就 422。"""
    _, _, (eleven, _) = seed(client, roots, airing_split_cour())
    sign_in(client)
    row = held_video(client, eleven)

    response = client.put(
        f"/api/plans/{eleven}/items",
        json={
            "items": [
                {"id": row, "action": "import", "season": 1, "episode_start": 23},
                {"id": row + 1, "action": "import", "season": 1, "episode_start": 24},
            ],
            "apply_to_series": True,
        },
        headers=BROWSER,
    )

    assert response.status_code == 422
