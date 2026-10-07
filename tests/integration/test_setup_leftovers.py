"""換一台 qBittorrent / Prowlarr 時列出 Berth 在舊那台留下的東西（M4 票 47，brief §19 D6）。

- 清單只含 **Berth 擁有的物件**（brief §16.4，D1）：`berth-*` 分類與裡面幾個 torrent、Berth
  加進去的站、Berth 設的介面登入。使用者自己的分類、自己在 Prowlarr 加的站不出現。
- 舊那台連不到時列「Berth 記得建過的」：分類來自 Route、站來自加站時記下的那一份，torrent 數
  說不出來。
- 一鍵移除只刪 **`berth-*` 而且裡面沒有 torrent** 的分類（雙向）；站與登入只列出。
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.prowlarr import ProwlarrIndexer
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.adapters.qbittorrent import QbittorrentCategory, TorrentStatus
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.api.deps import get_bundled_services, get_client_factory
from berth.api.gate import CSRF_HEADER
from berth.config import Config
from berth.domain import ServiceKind, ServiceOrigin
from berth.main import create_app
from berth.models import SetupSettings
from berth.services.clients import BundledServices
from berth.services.indexer import apply_default_indexers, remove_indexer
from berth.services.leftovers import (
    CategoriesNotRemovedError,
    read_leftovers,
    remove_empty_categories,
)
from berth.services.qbittorrent import route_categories
from berth.services.routes import build_routes
from berth.services.settings import read_settings, write_settings
from berth.services.setup import ServiceConnection, choose_service
from tests.integration.arrange import arrange, factory_for, sign_in_owner
from tests.integration.factories import COMPOSE, FakeClientFactory

BUNDLED = BundledServices(targets=COMPOSE, prowlarr_api_key="")
HOME = "http://host.docker.internal:48080"


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


@pytest.mark.asyncio
class TestRemoveEmptyCategories:
    async def test_removes_only_empty_berth_categories(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        qbittorrent = old_qbittorrent()
        factory = await ready(session, roots, qbittorrent)
        # Route 檢查建的那幾個也都是空的 `berth-*`：一起移除。
        created = {row.name for row in qbittorrent.created_categories}

        leftovers = await remove_empty_categories(session, factory)

        assert set(qbittorrent.removed_categories) == {"berth-shows"} | created
        names = {row.name for row in await qbittorrent.categories()}
        # 有 torrent 的 `berth-*`、使用者自己的（空的也一樣）都留著。
        assert {"berth-movies", "mine", "mine-empty"} <= names
        assert "berth-shows" not in names
        assert [(row.name, row.torrents) for row in leftovers.categories] == [("berth-movies", 2)]

    async def test_a_torrent_added_before_the_press_keeps_its_category(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """清單畫出來之後才有 torrent 進來：按下時重數，那一個不刪。"""
        qbittorrent = old_qbittorrent()
        factory = await ready(session, roots, qbittorrent)
        qbittorrent.torrents = (*qbittorrent.torrents, torrent("d", "berth-shows"))

        await remove_empty_categories(session, factory)

        assert "berth-shows" not in qbittorrent.removed_categories

    async def test_an_unreachable_qbittorrent_removes_nothing_and_says_so(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        qbittorrent = old_qbittorrent()
        factory = await ready(session, roots, qbittorrent)
        qbittorrent.error = ServiceUnavailableError("qbittorrent: connection refused")

        with pytest.raises(CategoriesNotRemovedError, match="connection refused"):
            await remove_empty_categories(session, factory)

        assert qbittorrent.removed_categories == []


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
        factory = FakeClientFactory(qbittorrent=qbittorrent)
        app.dependency_overrides[get_bundled_services] = lambda: BUNDLED
        app.dependency_overrides[get_client_factory] = lambda: factory
        with TestClient(app, headers={CSRF_HEADER: "XMLHttpRequest"}) as running:
            sign_in_owner(running)
            assert (
                running.post("/api/setup/services/qbittorrent", json={"origin": "bundled"})
            ).status_code == 200
            yield running

    def test_lists_and_removes_through_the_api(
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

        removed = client.delete("/api/setup/services/qbittorrent/leftovers/categories")

        assert removed.status_code == 200, removed.text
        assert qbittorrent.removed_categories == ["berth-shows"]
        assert [row["name"] for row in removed.json()["categories"]] == ["berth-movies"]

    def test_jellyfin_has_no_leftovers_list(self, client: TestClient) -> None:
        assert client.get("/api/setup/services/jellyfin/leftovers").status_code == 422
