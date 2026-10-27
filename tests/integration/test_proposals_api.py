"""`GET /proposals`、`POST /proposals/{id}/decide`（M5 票 08）：誰看得到、誰按得到、拒絕的形狀。

狀態機本身在 `test_proposals.py`。這裡驗 API 那一層：決定的 body 只有核准與勾選，**不收參數**；
別人的卡片看不到也按不到；連按兩次的第二次是 409。
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import Actor, CollectionType, JobState, JobTrigger, Role
from berth.models import Job, Route, User
from berth.services import proposals
from berth.services.events import EventHub
from tests.integration.test_media import SPY_ID
from tests.integration.test_media_api import ADMIN, BROWSER, CREW, client, factory, sign_in
from tests.integration.test_why_not_api import in_session

__all__ = ["client", "factory"]  # pytest 的 fixture 要在這個模組的命名空間裡

ADMINS_JOB = "a" * 40
CREWS_JOB = "c" * 40
#: Prowlarr 的代理下載連結長這樣：帶著它的 API key（brief §20.7、M4 票 79）。
PROWLARR_KEY = "0123456789abcdef0123456789abcdef"
PROXY_LINK = f"http://prowlarr:9696/1/download?apikey={PROWLARR_KEY}&link=abc&file=Spy"


def cards(client: TestClient, *, in_chat: bool = False) -> dict[str, int]:
    """管理員與一般使用者各有一筆入庫失敗的 Job，AI 各替他們提出了一張「重試」的卡片。

    `in_chat` 時卡片在各自的對話裡（核准只記決定）；否則按下去就執行。
    """
    sign_in(client, CREW)
    sign_in(client, ADMIN)

    async def arrange(session: AsyncSession) -> dict[str, int]:
        users = {row.name: row for row in await session.scalars(select(User))}
        made: dict[str, int] = {}
        for job_hash, who, chat in ((ADMINS_JOB, ADMIN, "c-admin"), (CREWS_JOB, CREW, "c-crew")):
            user = users[who["username"]]
            session.add(
                Job(
                    hash=job_hash,
                    name=job_hash,
                    trigger=JobTrigger.MANUAL,
                    user_id=user.id,
                    state=JobState.IMPORT_FAILED,
                )
            )
            await session.commit()
            card = await proposals.propose(
                session,
                EventHub(),
                "jobs.retry_job",
                [{"job_hash": job_hash}],
                actor=Actor.ai(user.id, Role(user.role)),
                conversation_id=chat if in_chat else None,
            )
            made[who["username"]] = card.id
        return made

    return in_session(client, arrange)


def decide(client: TestClient, card: int, body: dict[str, Any]) -> Any:
    return client.post(f"/api/proposals/{card}/decide", json=body, headers=BROWSER)


async def job_state(session: AsyncSession, job_hash: str) -> JobState:
    job = await session.get(Job, job_hash)
    assert job is not None
    return job.state


class TestWhoSeesWhat:
    def test_it_needs_a_session(self, client: TestClient) -> None:
        assert client.get("/api/proposals").status_code == 401

    def test_an_ordinary_user_lists_only_their_own(self, client: TestClient) -> None:
        made = cards(client)
        sign_in(client, CREW)

        response = client.get("/api/proposals")

        assert response.status_code == 200, response.text
        [card] = response.json()
        assert card["id"] == made[CREW["username"]]
        assert card["command"] == "jobs.retry_job"
        assert card["arguments"] == [{"job_hash": CREWS_JOB}]
        assert card["proposer"] == "ai"
        assert card["status"] == "pending"
        assert card["preview"]["effect"] == "reversible"
        assert card["preview"]["flags"] == ["downloads"]
        assert card["results"] is None

    def test_one_conversation_at_a_time(self, client: TestClient) -> None:
        made = cards(client, in_chat=True)

        everyone = client.get("/api/proposals").json()
        in_chat = client.get("/api/proposals", params={"conversation_id": "c-crew"}).json()

        assert [card["id"] for card in everyone] == [
            made[ADMIN["username"]],
            made[CREW["username"]],
        ]
        assert [card["id"] for card in in_chat] == [made[CREW["username"]]]


class TestDecide:
    def test_approving_runs_it_and_answers_with_each_rows_result(self, client: TestClient) -> None:
        made = cards(client)
        sign_in(client, CREW)

        response = decide(client, made[CREW["username"]], {"approve": True})

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "executed"
        [row] = body["results"]
        assert (row["outcome"], row["reason"]) == ("done", "")
        assert row["result"]["state"] == "importing"
        assert in_session(client, lambda s: job_state(s, CREWS_JOB)) is JobState.IMPORTING

    def test_the_body_takes_no_arguments(self, client: TestClient) -> None:
        """執行用存下的那一份：送參數來是請求本身說不通，卡片也還在等。"""
        made = cards(client)
        sign_in(client, CREW)
        card = made[CREW["username"]]

        response = decide(client, card, {"approve": True, "arguments": [{"job_hash": ADMINS_JOB}]})

        assert response.status_code == 422
        assert client.get("/api/proposals").json()[0]["status"] == "pending"
        assert in_session(client, lambda s: job_state(s, ADMINS_JOB)) is JobState.IMPORT_FAILED

    def test_someone_elses_card_is_missing(self, client: TestClient) -> None:
        made = cards(client)
        sign_in(client, CREW)

        response = decide(client, made[ADMIN["username"]], {"approve": True})

        assert response.status_code == 404
        assert response.json()["detail"]["reason"] == "proposal_missing"
        assert in_session(client, lambda s: job_state(s, ADMINS_JOB)) is JobState.IMPORT_FAILED

    def test_an_admin_may_decide_anyones(self, client: TestClient) -> None:
        made = cards(client)

        response = decide(client, made[CREW["username"]], {"approve": False})

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "rejected"

    def test_the_second_press_is_a_conflict(self, client: TestClient) -> None:
        made = cards(client)
        card = made[ADMIN["username"]]
        assert decide(client, card, {"approve": True}).status_code == 200

        response = decide(client, card, {"approve": True})

        assert response.status_code == 409
        assert response.json()["detail"] == {"reason": "proposal_decided", "detail": "executed"}

    def test_a_selection_that_does_not_fit_is_unprocessable(self, client: TestClient) -> None:
        made = cards(client)

        response = decide(client, made[ADMIN["username"]], {"approve": True, "selection": [3]})

        assert response.status_code == 422
        assert response.json()["detail"]["reason"] == "selection_invalid"


class TestSubmitCards:
    def test_a_submit_card_never_hands_the_download_link_to_the_browser(
        self, client: TestClient
    ) -> None:
        """M4 票 79 的規矩：下載連結記在伺服器上，瀏覽器只拿 id。確認卡也一樣。"""
        sign_in(client, CREW)
        sign_in(client, ADMIN)
        # 作品頁打開過，Berth 才有這部作品（快照從 TMDB 替身來）。
        assert client.get(f"/api/media/{SPY_ID}").status_code == 200

        async def arrange(session: AsyncSession) -> None:
            crew = await session.scalar(select(User).where(User.name == CREW["username"]))
            route = await session.scalar(
                select(Route).where(Route.collection_type == CollectionType.TVSHOWS)
            )
            assert crew is not None
            assert route is not None
            await proposals.propose(
                session,
                EventHub(),
                "downloading.add_manual_download",
                [
                    {
                        "source": {"url": PROXY_LINK, "title": "[Sub] SPY x FAMILY - 01 [1080p]"},
                        "media_id": SPY_ID,
                        "route_id": route.id,
                    }
                ],
                actor=Actor.ai(crew.id, Role(crew.role)),
            )

        in_session(client, arrange)
        sign_in(client, CREW)

        response = client.get("/api/proposals")

        assert response.status_code == 200, response.text
        assert len(response.json()) == 1
        assert PROWLARR_KEY not in response.text
