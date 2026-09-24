"""plans 端點與手動重跑（plan §6 plans / jobs 群組、票 11 驗收）。

命令本身在 `test_plan.py`；這裡驗的是形狀、狀態碼與「誰進得來」——`/api/plans` 沒有在門禁的
白名單上，所以匿名一律 401，而**看一份計劃不是管理動作**（brief §11：入庫是一般使用者
做的事）。

M1 的 plans 群組**只有讀**：逐列編輯與核准是 M2 的 Review Queue（plan §11.3）。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.api.deps import get_client_factory
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.domain import JobState, JobTrigger, MediaKind
from berth.main import create_app
from berth.models import Job, JobFile, Media, Route, TmdbSettings
from berth.services.routes import build_routes
from berth.services.settings import write_settings
from berth.services.setup import complete_setup
from tests.conftest import TMDB_API_KEY
from tests.integration.arrange import arrange, bundled_libraries, factory_for, fake_jellyfin
from tests.integration.factories import FakeClientFactory
from tests.integration.test_media import SPY_ID
from tests.integration.test_plan import BATCH, BATCH_FILES, HASH, STRAY, STRAY_FILES, _snapshot

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
        _seed(running, roots, factory)
        yield running


def _seed(client: TestClient, roots: dict[str, Path], factory: FakeClientFactory) -> None:
    """精靈跑完、作品在手、一筆下載完成的 Job 躺在那裡等人算（票 10 留下來的狀態）。"""

    async def run() -> None:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            await arrange(session, roots)
            await write_settings(session, TmdbSettings(api_key=TMDB_API_KEY))
            await session.commit()
            await build_routes(session, factory, ())
            await complete_setup(session)
            await _media(session)
            await _job(session, roots)

    asyncio.run(run())


async def _media(session: AsyncSession) -> None:
    session.add(
        Media(
            id=SPY_ID,
            tmdb_id=120089,
            kind=MediaKind.TV,
            title_en="SPY x FAMILY",
            title_original="SPY×FAMILY",
            year=2022,
            folder_name="SPY x FAMILY (2022)",
            folder_frozen=True,
            tmdb_snapshot_json=_snapshot().model_dump(mode="json"),
        )
    )
    await session.commit()


async def _job(
    session: AsyncSession,
    roots: dict[str, Path],
    *,
    name: str = BATCH,
    files: tuple[tuple[str, int], ...] = BATCH_FILES,
) -> None:
    route = await session.scalar(select(Route).where(Route.slug == "anime"))
    assert route is not None
    save_path = str(roots["complete"] / "anime")
    session.add(
        Job(
            hash=HASH,
            name=name,
            trigger=JobTrigger.MANUAL,
            media_id=SPY_ID,
            route_id=route.id,
            state=JobState.COMPLETED,
            save_path=save_path,
            content_path=f"{save_path}/{name}",
            progress=1.0,
        )
    )
    session.add_all(
        [
            JobFile(job_hash=HASH, rel_path=rel_path, size=size, priority=1)
            for rel_path, size in files
        ]
    )
    await session.commit()


def sign_in(client: TestClient, who: dict[str, str] = ADMIN) -> httpx.Response:
    response: httpx.Response = client.post("/api/auth/login", json=who, headers=BROWSER)
    return response


def replan(client: TestClient, job_hash: str = HASH) -> httpx.Response:
    response: httpx.Response = client.post(f"/api/jobs/{job_hash}/replan", headers=BROWSER)
    return response


class TestGate:
    def test_reading_a_plan_needs_a_session(self, client: TestClient) -> None:
        assert client.get("/api/plans/1").status_code == 401

    def test_replanning_needs_a_session(self, client: TestClient) -> None:
        assert client.post(f"/api/jobs/{HASH}/replan", headers=BROWSER).status_code == 401

    def test_an_ordinary_user_may_read_a_plan(self, client: TestClient) -> None:
        """入庫本來就是一般使用者做的事（brief §11）——只有設定才要 admin。"""
        sign_in(client, CREW)
        job = replan(client).json()

        assert client.get(f"/api/plans/{job['plan_id']}").status_code == 200

    def test_a_cross_site_form_post_is_refused(self, client: TestClient) -> None:
        sign_in(client)

        assert client.post(f"/api/jobs/{HASH}/replan").status_code == 403


class TestReplan:
    def test_it_answers_with_the_job_and_its_new_plan(self, client: TestClient) -> None:
        sign_in(client)

        job = replan(client).json()

        assert job["state"] == "importing"
        assert job["plan_id"] is not None

    def test_the_download_list_carries_the_plan_id(self, client: TestClient) -> None:
        """有沒有那一格就是畫面要的答案：要不要去要那一份逐檔的決定。"""
        sign_in(client)
        before = client.get("/api/jobs").json()[0]
        assert before["plan_id"] is None

        replan(client)

        assert client.get("/api/jobs").json()[0]["plan_id"] is not None

    def test_a_missing_job_is_a_404(self, client: TestClient) -> None:
        sign_in(client)

        response = replan(client, "0" * 40)

        assert response.status_code == 404
        assert response.json()["detail"]["reason"] == "job_missing"

    def test_a_job_that_is_already_importing_is_a_conflict(self, client: TestClient) -> None:
        """409 而不是 422：請求本身沒問題，是**現在**做不了。"""
        sign_in(client)
        replan(client)

        response = replan(client)

        assert response.status_code == 409
        assert response.json()["detail"]["reason"] == "not_replannable"


def _stray(client: TestClient, roots: dict[str, Path]) -> None:
    """換成一包規劃器認不出來的：重算一次就停在 review。"""

    async def run() -> None:
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            job = await session.get(Job, HASH)
            assert job is not None
            await session.delete(job)
            await session.commit()
            await _job(session, roots, name=STRAY, files=STRAY_FILES)

    asyncio.run(run())


class TestReplanInReviewIsAdmins:
    """`review` 狀態的重算只有 admin（M3 票 04）。

    在 `review` 重算會丟掉那一份——連同 admin 逐列改過的、撤銷之後退回來的——而審核本來就是
    admin 的事（plan §6）。門禁只看方法與路徑，這一條要看狀態，所以守在命令裡（鎖內讀到的
    狀態）；其他狀態的重算照舊是送單的人自己按得到的。
    """

    def test_an_ordinary_user_is_refused_while_it_waits_for_review(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        _stray(client, roots)
        sign_in(client)
        assert replan(client).json()["state"] == "review"
        client.post("/api/auth/logout", headers=BROWSER)
        sign_in(client, CREW)

        response = replan(client)

        assert response.status_code == 403
        assert response.json()["detail"]["reason"] == "review_needs_admin"
        job = client.get(f"/api/jobs/{HASH}").json()
        assert job["state"] == "review"
        # 按鈕與命令問的是同一份規則：對這個人，這一筆沒有那一顆。
        assert job["replannable"] is False

    def test_an_administrator_still_replans_it(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        _stray(client, roots)
        sign_in(client)
        replan(client)

        assert client.get(f"/api/jobs/{HASH}").json()["replannable"] is True

        response = replan(client)

        assert response.status_code == 200
        assert response.json()["state"] == "review"

    def test_an_ordinary_user_still_replans_a_completed_job(self, client: TestClient) -> None:
        sign_in(client, CREW)
        assert client.get("/api/jobs").json()[0]["replannable"] is True

        response = replan(client)

        assert response.status_code == 200
        assert response.json()["state"] == "importing"


class TestReading:
    def test_a_plan_reads_as_the_decision_the_confidence_and_the_reasons(
        self, client: TestClient
    ) -> None:
        sign_in(client)
        job = replan(client).json()

        plan = client.get(f"/api/plans/{job['plan_id']}").json()

        assert plan["job_hash"] == HASH
        assert plan["status"] == "auto"
        assert plan["engine"] == "rules"
        assert plan["summary"]["files"] == 5
        assert plan["summary"]["high"] == 5
        assert len(plan["items"]) == len(BATCH_FILES)
        episode = plan["items"][0]
        assert episode["action"] == "import"
        assert episode["confidence"] == "high"
        assert (episode["season"], episode["episode_start"]) == (1, 1)
        assert episode["target_path"].startswith("SPY x FAMILY (2022)")
        assert episode["reasons"]
        assert episode["audit"] is False

    def test_an_unknown_plan_is_a_404(self, client: TestClient) -> None:
        sign_in(client)

        assert client.get("/api/plans/404").status_code == 404

    def test_a_plan_that_stopped_says_why(self, client: TestClient, roots: dict[str, Path]) -> None:
        """M1 沒有審核 UI，所以這一份唯讀的答案就是使用者看得到的全部（票 11）。"""
        sign_in(client)

        async def stray() -> None:
            sessions = client.app.state.session_factory  # type: ignore[attr-defined]
            async with sessions() as session:
                job = await session.get(Job, HASH)
                assert job is not None
                await session.delete(job)
                await session.commit()
                await _job(session, roots, name=STRAY, files=STRAY_FILES)

        asyncio.run(stray())

        job = replan(client).json()
        plan = client.get(f"/api/plans/{job['plan_id']}").json()

        assert job["state"] == "review"
        assert plan["status"] == "pending_review"
        assert plan["summary"]["review_reason"] == "low_confidence"
        assert plan["items"][0]["reasons"]
