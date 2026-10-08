"""重裝之後在畫面上把帳本找回來（M4 票 60、`.scratch/m4/ledger-rebuild-shape.md`）。

`rebuild_ledger` 本身在 `test_claims.py`；這裡驗的是畫面那一顆要的兩件事：

- **偵測**（`read_ledger_gap`）：Route 的寫入目標底下、帳本不認得、而且還沒被重建或認領判過的檔案。
  判過的不算——重建之後配不上的檔案仍然不在帳本上，照字面算的話那顆按鈕永遠不會消失。
- **端點**：`GET /issues/rebuild-ledger` 數一數、`POST` 跑一次與 CLI 同一個命令；重建之後
  作品頁的檔案列回來，再按一次不重複。

起點與 `test_claims` 一樣是真的走完一輪入庫（`test_deletion.imported`），再把帳本拿掉、磁碟留著
——重裝或 DB 遺失時就是這樣。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from berth.api.deps import get_client_factory
from berth.config import Config
from berth.domain import ClaimMiss, IssueType
from berth.main import create_app
from berth.services.issues import ignore_issue, record_issue
from berth.services.ledger_rebuild import read_ledger_gap, rebuild_ledger
from berth.services.reconcile import reconcile_once
from berth.services.setup import complete_setup
from tests.integration.factories import FakeClientFactory
from tests.integration.test_claims import ACTOR, forget_everything, hand_placed
from tests.integration.test_deletion import LINKS, imported
from tests.integration.test_issue_repairs import LATER
from tests.integration.test_issues_api import _pinned_as_running
from tests.integration.test_plan import NOW
from tests.integration.test_reconcile_checks import open_of
from tests.integration.test_review_api import ADMIN, BROWSER, CREW, sign_in

# 同一個 fixture（假 Jellyfin 認得 skipper 與 deckhand）；`as` 讓 import 本身說出它是要再匯出的。
from tests.integration.test_review_api import factory as factory

#: 一個不是 Berth 寫的檔案：帶著 `[tmdbid-…]` 的資料夾，但沒有來源（使用者自己複製進來的）。
STRANGER = "Hand Placed (2020) [tmdbid-1]/Hand Placed (2020) [tmdbid-1].mkv"


@pytest.mark.asyncio
class TestWhatCountsAsAGap:
    async def test_a_lost_ledger_is_every_link_in_the_library(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await imported(session, roots)
        await forget_everything(session)

        assert await read_ledger_gap(session) == LINKS

    async def test_a_full_ledger_is_no_gap(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await imported(session, roots)

        assert await read_ledger_gap(session) == 0

    async def test_after_a_rebuild_the_gap_is_closed_even_where_nothing_matched(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """配不上的那一個仍然不在帳本上，但重建判過它了：按鈕不該為它一直留著。"""
        _, route, factory = await imported(session, roots)
        hand_placed(route, STRANGER)
        await forget_everything(session)
        assert await read_ledger_gap(session) == LINKS + 1

        await rebuild_ledger(session, factory, now=NOW)

        assert await read_ledger_gap(session) == 0

    async def test_the_nightly_reconcile_does_not_reopen_the_gap(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """04:00 那一輪對同一件 Issue 再記一次時，重建寫上的理由要留著——它就是「判過了」的記號，
        也是待處理頁上「沒配上的理由」那一行。"""
        _, route, factory = await imported(session, roots)
        hand_placed(route, STRANGER)
        await rebuild_ledger(session, factory, now=NOW)

        await reconcile_once(session, factory, now=LATER)

        (issue,) = await open_of(session, IssueType.UNMANAGED_LIBRARY_FILE)
        assert (issue.detail_json or {}).get("reason") == ClaimMiss.NO_SOURCE.value
        assert await read_ledger_gap(session) == 0

    async def test_what_only_the_reconcile_saw_still_counts(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """對帳開的那幾件沒有理由：還沒有人試過重建，仍然是要給那顆按鈕的。"""
        _, _, factory = await imported(session, roots)
        await forget_everything(session)

        await reconcile_once(session, factory, now=LATER)

        assert len(await open_of(session, IssueType.UNMANAGED_LIBRARY_FILE)) == LINKS
        assert await read_ledger_gap(session) == LINKS

    async def test_an_ignored_judgement_stays_judged(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        _, route, factory = await imported(session, roots)
        hand_placed(route, STRANGER)
        await rebuild_ledger(session, factory, now=NOW)
        (issue,) = await open_of(session, IssueType.UNMANAGED_LIBRARY_FILE)

        await ignore_issue(session, issue.id, actor=ACTOR)

        assert await read_ledger_gap(session) == 0

    async def test_an_ignored_issue_the_reconcile_opened_is_not_a_judgement(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """沒有理由的那一件被忽略過，只代表「這一次不想處理」：重建沒有看過它。"""
        _, route, _ = await imported(session, roots)
        stranger = hand_placed(route, STRANGER)
        recorded = await record_issue(
            session, IssueType.UNMANAGED_LIBRARY_FILE, path=str(stranger), now=NOW
        )
        await session.commit()

        await ignore_issue(session, recorded.issue.id, actor=ACTOR)

        assert await read_ledger_gap(session) == 1

    async def test_a_route_whose_folder_is_gone_counts_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """掛不上的那一條說不出有什麼：不算缺口，也不炸（那是健康頁與對帳要說的）。"""
        _, route, _ = await imported(session, roots)
        await forget_everything(session)
        route.target_path = str(roots["library"] / "not-mounted")
        await session.commit()

        assert await read_ledger_gap(session) == 0


# --- 端點 -------------------------------------------------------------------


@pytest.fixture
def client(
    config: Config, tmp_path: Path, roots: dict[str, Path], factory: FakeClientFactory
) -> Iterator[TestClient]:
    app = create_app(replace(config, web_root=tmp_path / "never-built"), clients=factory)
    app.dependency_overrides[get_client_factory] = lambda: factory
    with TestClient(app) as running:
        yield running


def seed_lost_ledger(client: TestClient, roots: dict[str, Path], *, stranger: bool = False) -> str:
    """入庫完一筆、再把帳本拿掉。回那部作品的 id。"""

    async def run() -> str:
        # `app.state` 是 Starlette 的動態屬性，型別上看不到 lifespan 掛上去的 session factory。
        sessions = client.app.state.session_factory  # type: ignore[attr-defined]
        async with sessions() as session:
            job, route, _ = await imported(session, roots)
            if stranger:
                hand_placed(route, STRANGER)
            await complete_setup(session)
            await session.commit()
            await forget_everything(session)
            assert job.media_id is not None
            return job.media_id

    return asyncio.run(run())


class TestTheEndpoints:
    def test_only_an_admin_gets_in(self, client: TestClient, roots: dict[str, Path]) -> None:
        seed_lost_ledger(client, roots)
        sign_in(client, CREW)

        assert client.get("/api/issues/rebuild-ledger").status_code == 403
        assert client.post("/api/issues/rebuild-ledger", headers=BROWSER).status_code == 403

    def test_the_count_the_rebuild_and_the_title_page(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        media_id = seed_lost_ledger(client, roots, stranger=True)
        sign_in(client, ADMIN)
        assert client.get(f"/api/media/{media_id}").json()["files"] == []

        before = client.get("/api/issues/rebuild-ledger")
        rebuilt = client.post("/api/issues/rebuild-ledger", headers=BROWSER)

        assert before.json() == {"unknown": LINKS + 1}
        assert rebuilt.status_code == 200
        assert rebuilt.json() == {
            "known": 0,
            "claimed": LINKS,
            "unmatched": {ClaimMiss.NO_SOURCE.value: 1},
            "skipped": [],
            "unread_complete": [],
            "undecided": 0,
        }
        assert len(client.get(f"/api/media/{media_id}").json()["files"]) == LINKS
        assert client.get("/api/issues/rebuild-ledger").json() == {"unknown": 0}

    def test_pressing_it_again_adds_nothing(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        media_id = seed_lost_ledger(client, roots, stranger=True)
        sign_in(client, ADMIN)
        client.post("/api/issues/rebuild-ledger", headers=BROWSER)
        files = client.get(f"/api/media/{media_id}").json()["files"]
        issues = client.get("/api/issues").json()

        again = client.post("/api/issues/rebuild-ledger", headers=BROWSER).json()

        assert (again["known"], again["claimed"]) == (LINKS, 0)
        assert again["unmatched"] == {ClaimMiss.NO_SOURCE.value: 1}
        assert client.get(f"/api/media/{media_id}").json()["files"] == files
        assert [row["id"] for row in client.get("/api/issues").json()] == [
            row["id"] for row in issues
        ]

    def test_a_running_reconcile_refuses_it_and_writes_nothing(
        self, client: TestClient, roots: dict[str, Path]
    ) -> None:
        """兩邊都會替同一個檔案記一件 `unmanaged_library_file`：對帳正在跑時不重建（409）。"""
        media_id = seed_lost_ledger(client, roots)
        sign_in(client, ADMIN)
        runner = client.app.state.reconciler  # type: ignore[attr-defined]

        with _pinned_as_running(runner):
            response = client.post("/api/issues/rebuild-ledger", headers=BROWSER)

        assert response.status_code == 409
        assert response.json()["detail"]["reason"] == "reconcile_running"
        assert client.get(f"/api/media/{media_id}").json()["files"] == []
        assert client.get("/api/issues/rebuild-ledger").json() == {"unknown": LINKS}
