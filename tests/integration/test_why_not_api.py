"""`GET /media/{id}/why-not`（M5 票 10）：誰進得來、誰看得到什麼、拒絕的形狀。

結論本身在 `test_why_not.py`。這裡驗 brief §19「M5 的方向」⑦：一般使用者只讀得到**自己的**
送單，Issue 與 RSS 那一側（管理員的頁面）對他是 `null`。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import Confidence, JobState, JobTrigger, PlanAction, PlanStatus
from berth.models import Job, Plan, PlanItem, User
from tests.integration.test_media import SPY_ID
from tests.integration.test_media_api import ADMIN, CREW, client, factory, sign_in

__all__ = ["client", "factory"]  # pytest 的 fixture 要在這個模組的命名空間裡

ADMINS_JOB = "a" * 40
CREWS_JOB = "c" * 40


def in_session[T](client: TestClient, work: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def run() -> T:
        # `TestClient.app` 是 Starlette 的 `ASGIApp`，型別上沒有 `state`（實際是 FastAPI）。
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            return await work(session)

    return asyncio.run(run())


def two_downloads(client: TestClient) -> None:
    """管理員與一般使用者各送了一筆，兩筆都蓋到 S01E01、都還在下載。"""
    sign_in(client, CREW)
    sign_in(client, ADMIN)
    # 作品頁打開過，Berth 才有這部作品（快照從 TMDB 替身來）。
    assert client.get(f"/api/media/{SPY_ID}").status_code == 200

    async def arrange(session: AsyncSession) -> None:
        users = {row.name: row.id for row in await session.scalars(select(User))}
        for job_hash, who in ((ADMINS_JOB, ADMIN), (CREWS_JOB, CREW)):
            session.add(
                Job(
                    hash=job_hash,
                    name=f"SPY x FAMILY - 01 ({who['username']})",
                    trigger=JobTrigger.MANUAL,
                    media_id=SPY_ID,
                    user_id=users[who["username"]],
                    state=JobState.DOWNLOADING,
                )
            )
            plan = Plan(job_hash=job_hash, status=PlanStatus.PREPLAN)
            session.add(plan)
            await session.flush()
            session.add(
                PlanItem(
                    plan_id=plan.id,
                    rel_path="episode.mkv",
                    action=PlanAction.IMPORT,
                    media_id=SPY_ID,
                    season=1,
                    episode_start=1,
                    confidence=Confidence.HIGH,
                )
            )
        await session.commit()

    in_session(client, arrange)


def episode_one(client: TestClient) -> dict[str, Any]:
    response = client.get(f"/api/media/{SPY_ID}/why-not", params={"season": 1, "episode": 1})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


class TestWhoSeesWhat:
    def test_it_needs_a_session(self, client: TestClient) -> None:
        assert client.get(f"/api/media/{SPY_ID}/why-not").status_code == 401

    def test_an_ordinary_user_sees_only_their_own_jobs(self, client: TestClient) -> None:
        two_downloads(client)
        sign_in(client, CREW)

        body = episode_one(client)

        assert body["conclusion"] == "downloading"
        assert [row["hash"] for row in body["jobs"]] == [CREWS_JOB]
        assert body["episodes"][0]["jobs"] == [CREWS_JOB]
        assert (body["issues"], body["rss"]) == (None, None)

    def test_an_admin_sees_everyones(self, client: TestClient) -> None:
        two_downloads(client)

        body = episode_one(client)

        assert sorted(row["hash"] for row in body["jobs"]) == [ADMINS_JOB, CREWS_JOB]
        assert body["issues"] == []
        assert body["rss"] == {"series": [], "items": []}


class TestRefusals:
    def test_season_without_episode(self, client: TestClient) -> None:
        sign_in(client)

        response = client.get(f"/api/media/{SPY_ID}/why-not", params={"season": 1})

        assert response.status_code == 422
        assert response.json()["detail"]["reason"] == "episode_incomplete"

    def test_a_title_berth_has_never_seen(self, client: TestClient) -> None:
        sign_in(client)

        response = client.get("/api/media/tv:999999/why-not")

        assert response.status_code == 404
        assert response.json()["detail"]["reason"] == "media_missing"
