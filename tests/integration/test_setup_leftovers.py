"""換一台 qBittorrent / Prowlarr 時列出 Berth 在舊那台留下的東西（M4 票 47，brief §19 D6）。

- 清單只含 **Berth 擁有的物件**（brief §16.4，D1）：`berth-*` 分類與裡面幾個 torrent、Berth
  加進去的站、Berth 設的介面登入。使用者自己的分類、自己在 Prowlarr 加的站不出現。
- 舊那台連不到時列「Berth 記得建過的」：分類來自 Route、站來自加站時記下的那一份，torrent 數
  說不出來。
- 移除只刪 **`berth-*` 而且裡面沒有 torrent** 的分類（雙向）；站與登入只列出。
- 移除是換台框裡的勾選，**跟著確認換台一起做**（M4 票 65）：打開換台框、取消、換不成都不動任何
  分類；勾了而原本那一台沒答上來，整個換台不做。
"""

from __future__ import annotations

from collections.abc import Awaitable, Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.prowlarr import ProwlarrIndexer
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.adapters.qbittorrent import QbittorrentCategory, TorrentStatus
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.api.deps import get_bundled_services, get_client_factory
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.domain import IssueType, JobState, JobTrigger, ServiceKind, ServiceOrigin
from berth.main import create_app
from berth.models import Issue, Job, SetupSettings
from berth.services.clients import BundledServices
from berth.services.downloads import poll_downloads
from berth.services.events import EventHub
from berth.services.hints import JobHints
from berth.services.indexer import apply_default_indexers, remove_indexer
from berth.services.leftovers import CategoriesNotRemovedError, LeftoverJob, read_leftovers
from berth.services.qbittorrent import route_categories
from berth.services.routes import build_routes
from berth.services.settings import read_settings, write_settings
from berth.services.setup import (
    ConnectionFailedError,
    ServiceConnection,
    SetupStatus,
    choose_service,
)
from tests.integration.arrange import arrange, factory_for, sign_in_owner
from tests.integration.factories import COMPOSE, FakeClientFactory

BUNDLED = BundledServices(targets=COMPOSE, prowlarr_api_key="")
HOME = "http://host.docker.internal:48080"
QBT = ServiceKind.QBITTORRENT


def category(name: str) -> QbittorrentCategory:
    return QbittorrentCategory(
        name=name, save_path=f"/data/torrent/complete/{name}", download_path=""
    )


def torrent(info_hash: str, in_category: str) -> TorrentStatus:
    return TorrentStatus(
        hash=info_hash,
        name=f"release-{info_hash}",
        state="uploading",
        category=in_category,
        tags=(),
        progress=1.0,
        completion_on=1,
        last_activity=1,
        added_on=1,
        save_path="/data/torrent/complete",
        content_path=f"/data/torrent/complete/release-{info_hash}",
        total_size=1,
    )


def old_qbittorrent() -> FakeQbittorrentClient:
    """Berth 在上面建了兩個分類（一個空的、一個有兩個 torrent），使用者自己有兩個（一個空的）。"""
    return FakeQbittorrentClient(
        categories=(
            category("berth-shows"),
            category("berth-movies"),
            category("mine"),
            category("mine-empty"),
        ),
        torrents=(torrent("a", "berth-movies"), torrent("b", "berth-movies"), torrent("c", "mine")),
    )


def users_site(indexer_id: int, definition_name: str) -> ProwlarrIndexer:
    return ProwlarrIndexer(
        id=indexer_id,
        name=f"Their {definition_name}",
        enabled=True,
        definition_name=definition_name,
        privacy="private",
        protocol="torrent",
    )


async def ready(
    session: AsyncSession, roots: dict[str, Path], qbittorrent: FakeQbittorrentClient
) -> FakeClientFactory:
    """三台都是套件內、Route 建好；Berth 替 qBittorrent 設過介面登入。"""
    await arrange(session, roots)
    factory = factory_for(roots, qbittorrent=qbittorrent)
    await build_routes(session, factory, ())
    setup = await read_settings(session, SetupSettings)
    setup.qbittorrent.web_ui_username = "skipper"
    setup.qbittorrent.web_ui_password_hash = "salted"
    await write_settings(session, setup)
    await session.commit()
    return factory


@pytest.mark.asyncio
class TestQbittorrentList:
    async def test_lists_only_berth_categories_with_their_torrent_counts(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots, old_qbittorrent())

        leftovers = await read_leftovers(session, factory, ServiceKind.QBITTORRENT)

        assert leftovers.reachable
        counts = {row.name: row.torrents for row in leftovers.categories}
        assert counts["berth-shows"] == 0
        assert counts["berth-movies"] == 2
        assert not {"mine", "mine-empty"} & counts.keys()
        assert leftovers.login == "skipper"
        assert leftovers.sites == ()

    async def test_a_login_the_instance_set_itself_is_not_berths(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """帳號在、雜湊空的是那一台自己就設過的（M4 票 38）：不是 Berth 設的，不列。"""
        factory = await ready(session, roots, old_qbittorrent())
        setup = await read_settings(session, SetupSettings)
        setup.qbittorrent.web_ui_password_hash = ""
        await write_settings(session, setup)

        leftovers = await read_leftovers(session, factory, ServiceKind.QBITTORRENT)

        assert leftovers.login == ""

    async def test_an_unreachable_qbittorrent_lists_what_berth_remembers(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots, old_qbittorrent())
        remembered = sorted(await route_categories(session))
        assert remembered
        factory.qbittorrent_.error = ServiceUnavailableError("qbittorrent: connection refused")

        leftovers = await read_leftovers(session, factory, ServiceKind.QBITTORRENT)

        assert not leftovers.reachable
        assert leftovers.error
        # 舊那台上的 `berth-shows` 不是 Route 建的，Berth 不記得它：只列 Route 的分類。
        assert [row.name for row in leftovers.categories] == remembered
        assert all(row.torrents is None for row in leftovers.categories)
        assert leftovers.login == "skipper"


def switch_to_existing(
    session: AsyncSession, factory: FakeClientFactory, *, remove_empty_categories: bool
) -> Awaitable[SetupStatus]:
    """確認換台：換到 `HOME` 那一台既有的 qBittorrent（測過才存）。"""
    return choose_service(
        session,
        factory,
        BUNDLED,
        ServiceKind.QBITTORRENT,
        ServiceOrigin.EXISTING,
        ServiceConnection(base_url=HOME, username="admin", password="adminadmin"),
        remove_empty_categories=remove_empty_categories,
    )


async def chosen_qbittorrent(session: AsyncSession) -> tuple[ServiceOrigin, str]:
    choice = (await read_settings(session, SetupSettings)).choices[ServiceKind.QBITTORRENT]
    return choice.origin, choice.base_url


@pytest.mark.asyncio
class TestRemoveEmptyCategoriesOnSwitch:
    """「移除空分類」跟著確認換台一起做（M4 票 65，審計 P2-9）：打開換台框、取消、換不成都不動。"""

    async def test_confirming_the_switch_removes_the_old_ones_empty_berth_categories(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        old = old_qbittorrent()
        factory = await ready(session, roots, old)
        new = FakeQbittorrentClient()
        factory.qbittorrent_elsewhere[HOME] = new
        # Route 檢查建的那幾個也都是空的 `berth-*`：一起移除。
        created = {row.name for row in old.created_categories}

        await switch_to_existing(session, factory, remove_empty_categories=True)

        assert set(old.removed_categories) == {"berth-shows"} | created
        names = {row.name for row in await old.categories()}
        # 有 torrent 的 `berth-*`、使用者自己的（空的也一樣）都留著。
        assert {"berth-movies", "mine", "mine-empty"} <= names
        assert new.removed_categories == []
        assert await chosen_qbittorrent(session) == (ServiceOrigin.EXISTING, HOME)

    async def test_changing_the_address_from_one_existing_to_another_is_a_switch_too(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """設定頁的「改位址」（M4 票 102）：既有換到另一台既有一樣是換台，勾了移除就移除
        原本那一台的。"""
        old = old_qbittorrent()
        factory = await ready(session, roots, old)
        # 沒列在 `qbittorrent_elsewhere` 的位址都是 `old` 那一台：先把它改成以既有的位址連。
        await choose_service(
            session,
            factory,
            BUNDLED,
            QBT,
            ServiceOrigin.EXISTING,
            ServiceConnection(base_url="http://nas:8080", username="admin", password="adminadmin"),
        )
        new = FakeQbittorrentClient()
        factory.qbittorrent_elsewhere[HOME] = new

        await switch_to_existing(session, factory, remove_empty_categories=True)

        assert "berth-shows" in old.removed_categories
        assert "berth-movies" not in old.removed_categories
        assert new.removed_categories == []
        assert await chosen_qbittorrent(session) == (ServiceOrigin.EXISTING, HOME)

    async def test_switching_without_the_box_ticked_removes_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        old = old_qbittorrent()
        factory = await ready(session, roots, old)
        factory.qbittorrent_elsewhere[HOME] = FakeQbittorrentClient()

        await switch_to_existing(session, factory, remove_empty_categories=False)

        assert old.removed_categories == []
        assert await chosen_qbittorrent(session) == (ServiceOrigin.EXISTING, HOME)

    async def test_opening_the_switch_box_and_cancelling_removes_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """取消換台不送任何請求：打開換台框時讀的那一份清單是唯一碰到原本那一台的。"""
        old = old_qbittorrent()
        factory = await ready(session, roots, old)

        await read_leftovers(session, factory, ServiceKind.QBITTORRENT)

        assert old.removed_categories == []
        assert await chosen_qbittorrent(session) == (ServiceOrigin.BUNDLED, COMPOSE[QBT])

    async def test_a_switch_the_new_one_fails_removes_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """新那一台測不過就沒有換台（測過才存，M4 票 45）：勾了也不移除。"""
        old = old_qbittorrent()
        factory = await ready(session, roots, old)
        failing = FakeQbittorrentClient()
        failing.error = ServiceUnavailableError("qbittorrent: connection refused")
        factory.qbittorrent_elsewhere[HOME] = failing

        with pytest.raises(ConnectionFailedError):
            await switch_to_existing(session, factory, remove_empty_categories=True)

        assert old.removed_categories == []
        assert await chosen_qbittorrent(session) == (ServiceOrigin.BUNDLED, COMPOSE[QBT])

    async def test_staying_on_the_same_one_removes_nothing(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """沒有換台（再點一次同一格）就沒有「原本那一台」：勾選不作數，現在這一台的分類不碰。"""
        old = old_qbittorrent()
        factory = await ready(session, roots, old)

        await choose_service(
            session,
            factory,
            BUNDLED,
            ServiceKind.QBITTORRENT,
            ServiceOrigin.BUNDLED,
            remove_empty_categories=True,
        )

        assert old.removed_categories == []

    async def test_a_torrent_added_before_the_press_keeps_its_category(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """換台框畫出來之後才有 torrent 進來：按下確認時重數，那一個不刪。"""
        old = old_qbittorrent()
        factory = await ready(session, roots, old)
        factory.qbittorrent_elsewhere[HOME] = FakeQbittorrentClient()
        old.torrents = (*old.torrents, torrent("d", "berth-shows"))

        await switch_to_existing(session, factory, remove_empty_categories=True)

        assert "berth-shows" not in old.removed_categories

    async def test_an_old_one_that_stopped_answering_refuses_the_whole_switch(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """勾了移除、原本那一台卻沒答上來：沒有移除，也不換台——一起做的就一起不做，畫面說得出
        取消勾選再換一次。"""
        old = old_qbittorrent()
        factory = await ready(session, roots, old)
        factory.qbittorrent_elsewhere[HOME] = FakeQbittorrentClient()
        old.error = ServiceUnavailableError("qbittorrent: connection refused")

        with pytest.raises(CategoriesNotRemovedError, match="connection refused"):
            await switch_to_existing(session, factory, remove_empty_categories=True)

        assert old.removed_categories == []
        assert await chosen_qbittorrent(session) == (ServiceOrigin.BUNDLED, COMPOSE[QBT])


def job(info_hash: str, state: JobState) -> Job:
    return Job(
        hash=info_hash,
        name=f"release-{info_hash}",
        source_url=f"magnet:?xt=urn:btih:{info_hash}",
        trigger=JobTrigger.MANUAL,
        state=state,
    )


@pytest.mark.asyncio
class TestDownloadsStillOnTheOldOne:
    """換台之後還在下載的那幾筆（M4 票 102，票 65 留下的）：torrent 留在原本那一台，新那一台上
    找不到，poller 照 plan §3.1 把它們變成 `client_removed`。換台框照實說出是哪幾筆。"""

    async def test_after_the_switch_the_poller_opens_client_removed_for_them(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """重現：原本那一台上下到一半的那一筆，換台後的第一輪就成了待處理。"""
        old = old_qbittorrent()
        old.torrents = (*old.torrents, replace(torrent("d", "berth-shows"), state="downloading"))
        factory = await ready(session, roots, old)
        session.add(job("d", JobState.DOWNLOADING))
        await session.commit()
        factory.qbittorrent_elsewhere[HOME] = FakeQbittorrentClient()

        await switch_to_existing(session, factory, remove_empty_categories=False)
        await poll_downloads(session, factory.qbittorrent(HOME), EventHub(), JobHints())

        found = await session.get(Job, "d")
        assert found is not None and found.state is JobState.CLIENT_REMOVED
        issue = await session.scalar(select(Issue).where(Issue.job_hash == "d"))
        assert issue is not None and issue.type is IssueType.CLIENT_REMOVED

    async def test_the_list_names_the_ones_that_will_become_issues(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """poller 盯著的那幾種狀態才算：入庫了的、已經是待處理的、送單失敗的都不在
        qBittorrent 的清單上等著。"""
        factory = await ready(session, roots, old_qbittorrent())
        for info_hash, state in [
            ("d", JobState.DOWNLOADING),
            ("e", JobState.STALLED),
            ("f", JobState.SUBMITTED),
            ("g", JobState.IMPORTED),
            ("h", JobState.CLIENT_REMOVED),
            ("i", JobState.SUBMIT_FAILED),
        ]:
            session.add(job(info_hash, state))
        await session.commit()

        leftovers = await read_leftovers(session, factory, ServiceKind.QBITTORRENT)

        assert leftovers.in_flight == (
            LeftoverJob(hash="d", name="release-d"),
            LeftoverJob(hash="e", name="release-e"),
            LeftoverJob(hash="f", name="release-f"),
        )

    async def test_an_unreachable_old_one_still_names_them(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """清單讀的是 Berth 自己的 Job，連不到原本那一台照樣說得出。"""
        factory = await ready(session, roots, old_qbittorrent())
        session.add(job("d", JobState.DOWNLOADING))
        await session.commit()
        factory.qbittorrent_.error = ServiceUnavailableError("qbittorrent: connection refused")

        leftovers = await read_leftovers(session, factory, ServiceKind.QBITTORRENT)

        assert not leftovers.reachable
        assert leftovers.in_flight == (LeftoverJob(hash="d", name="release-d"),)

    async def test_prowlarr_has_none(self, session: AsyncSession, roots: dict[str, Path]) -> None:
        factory = await ready(session, roots, FakeQbittorrentClient())
        session.add(job("d", JobState.DOWNLOADING))
        await session.commit()

        leftovers = await read_leftovers(session, factory, ServiceKind.PROWLARR)

        assert leftovers.in_flight == ()


@pytest.mark.asyncio
class TestProwlarrList:
    async def test_lists_the_sites_berth_added_and_not_the_users_own(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots, FakeQbittorrentClient())
        factory.prowlarr_ = FakeProwlarrClient(indexers=[users_site(1, "animebytes")])
        await apply_default_indexers(session, factory, ["nyaasi"], sleep=_no_sleep)

        leftovers = await read_leftovers(session, factory, ServiceKind.PROWLARR)

        assert leftovers.reachable
        assert leftovers.sites == ("Nyaa.si",)
        assert leftovers.categories == ()

    async def test_a_site_removed_in_berth_is_no_longer_listed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots, FakeQbittorrentClient())
        await apply_default_indexers(session, factory, ["nyaasi"], sleep=_no_sleep)
        (added,) = await factory.prowlarr_.indexers()
        await remove_indexer(session, factory, added.id)
        factory.prowlarr_.ping_error = ServiceUnavailableError("prowlarr: connection refused")
        factory.prowlarr_.indexers_error = factory.prowlarr_.ping_error

        leftovers = await read_leftovers(session, factory, ServiceKind.PROWLARR)

        assert leftovers.sites == ()

    async def test_an_unreachable_prowlarr_lists_what_berth_remembers(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        factory = await ready(session, roots, FakeQbittorrentClient())
        await apply_default_indexers(session, factory, ["nyaasi"], sleep=_no_sleep)
        setup = await read_settings(session, SetupSettings)
        setup.indexer.web_ui_username = "skipper"
        setup.indexer.web_ui_password_hash = "salted"
        await write_settings(session, setup)
        factory.prowlarr_.indexers_error = ServiceUnavailableError("prowlarr: connection refused")

        leftovers = await read_leftovers(session, factory, ServiceKind.PROWLARR)

        assert not leftovers.reachable
        assert leftovers.sites == ("Nyaa.si",)
        assert leftovers.login == "skipper"

    async def test_switching_prowlarr_forgets_the_old_ones_sites(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """換了之後清單說的是新那一台：舊那台的站不再算 Berth 在「現在這一台」上加的。"""
        factory = await ready(session, roots, FakeQbittorrentClient())
        await apply_default_indexers(session, factory, ["nyaasi"], sleep=_no_sleep)

        await choose_service(
            session,
            factory,
            BUNDLED,
            ServiceKind.PROWLARR,
            ServiceOrigin.EXISTING,
            ServiceConnection(base_url="http://host.docker.internal:49696", api_key="theirs"),
        )

        assert (await read_settings(session, SetupSettings)).indexer.added_sites == {}


async def _no_sleep(_: float) -> None:
    return None


class TestApi:
    @pytest.fixture
    def qbittorrent(self) -> FakeQbittorrentClient:
        return old_qbittorrent()

    @pytest.fixture
    def client(
        self, config: Config, tmp_path: Path, qbittorrent: FakeQbittorrentClient
    ) -> Iterator[TestClient]:
        app = create_app(replace(config, web_root=tmp_path / "never-built"))
        factory = FakeClientFactory(
            qbittorrent=qbittorrent, qbittorrent_elsewhere={HOME: FakeQbittorrentClient()}
        )
        app.dependency_overrides[get_bundled_services] = lambda: BUNDLED
        app.dependency_overrides[get_client_factory] = lambda: factory
        with TestClient(app, headers={CSRF_HEADER: "XMLHttpRequest"}) as running:
            sign_in_owner(running)
            assert (
                running.post("/api/setup/services/qbittorrent", json={"origin": "bundled"})
            ).status_code == 200
            yield running

    def test_lists_then_removes_on_the_switch_through_the_api(
        self, client: TestClient, qbittorrent: FakeQbittorrentClient
    ) -> None:
        listed = client.get("/api/setup/services/qbittorrent/leftovers")
        assert listed.status_code == 200, listed.text
        body = listed.json()
        assert body["reachable"] is True
        assert {row["name"]: row["torrents"] for row in body["categories"]} == {
            "berth-shows": 0,
            "berth-movies": 2,
        }
        assert qbittorrent.removed_categories == []

        switched = client.post(
            "/api/setup/services/qbittorrent",
            json={
                "origin": "existing",
                "base_url": HOME,
                "username": "admin",
                "password": "adminadmin",
                "remove_empty_categories": True,
            },
        )

        assert switched.status_code == 200, switched.text
        assert qbittorrent.removed_categories == ["berth-shows"]

    def test_an_old_one_that_stopped_answering_is_a_502_refusal(
        self, client: TestClient, qbittorrent: FakeQbittorrentClient
    ) -> None:
        qbittorrent.error = ServiceUnavailableError("qbittorrent: connection refused")

        refused = client.post(
            "/api/setup/services/qbittorrent",
            json={"origin": "existing", "base_url": HOME, "remove_empty_categories": True},
        )

        assert refused.status_code == 502, refused.text
        detail = refused.json()["detail"]
        assert detail["reason"] == "categories_not_removed"
        assert "connection refused" in detail["detail"]
        assert qbittorrent.removed_categories == []

    def test_only_qbittorrent_takes_the_box(self, client: TestClient) -> None:
        refused = client.post(
            "/api/setup/services/prowlarr",
            json={"origin": "bundled", "remove_empty_categories": True},
        )

        assert refused.status_code == 422, refused.text

    def test_jellyfin_has_no_leftovers_list(self, client: TestClient) -> None:
        assert client.get("/api/setup/services/jellyfin/leftovers").status_code == 422
