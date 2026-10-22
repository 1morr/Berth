"""週報的端點（M4 票 131）：清單與某一週，只有管理員；沒有這一週是 404。

內容怎麼算是 `test_weekly.py` 的事；這裡只驗端點：門禁、形狀、順序。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from berth.services.weekly import compose_weekly
from tests.integration.test_issues_api import CREW, client, factory, sign_in

__all__ = ["client", "factory"]

#: 2026-10-26 是週一。
MONDAY = datetime(2026, 10, 26, 5, 0, tzinfo=UTC)


def composed(client: TestClient, ends_at: datetime) -> int:
    async def run() -> int:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            made = await compose_weekly(session, ends_at=ends_at)
            assert made is not None
            return made.id

    return asyncio.run(run())


class TestTheWeeklyEndpoints:
    def test_the_list_is_newest_first_and_each_week_opens(self, client: TestClient) -> None:
        older = composed(client, MONDAY - timedelta(days=7))
        newer = composed(client, MONDAY)
        sign_in(client)

        lines = client.get("/api/weekly").json()

        assert [(line["id"], line["first_day"], line["last_day"]) for line in lines] == [
            (newer, "2026-10-19", "2026-10-25"),
            (older, "2026-10-12", "2026-10-18"),
        ]
        report = client.get(f"/api/weekly/{newer}").json()
        assert report["first_day"] == "2026-10-19"
        assert set(report) == {
            "id",
            "first_day",
            "last_day",
            "created_at",
            "imported",
            "fixed",
            "waiting",
        }
        assert set(report["waiting"]) == {"review", "issues", "rss", "swept"}

    def test_a_week_that_is_not_there_is_404(self, client: TestClient) -> None:
        sign_in(client)

        assert client.get("/api/weekly/999").status_code == 404

    def test_an_ordinary_user_is_refused(self, client: TestClient) -> None:
        report = composed(client, MONDAY)
        sign_in(client, CREW)

        assert client.get("/api/weekly").status_code == 403
        assert client.get(f"/api/weekly/{report}").status_code == 403
