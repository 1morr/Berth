"""既有服務不被改動（M4 票 05、brief §19 2026-09-26；M4 票 15 起改讀使用者的選擇）。

`berth-lab` 實測：使用者自己的 Prowlarr 還沒加索引站就被判成套件內，第 6 步以第 1 步的帳密
`PUT config/host` 把它的登入覆寫掉；免密可進的舊 qBittorrent 走同一條路。票 05 的修法是收緊判定；
2026-09-29 起根本不判定——**使用者選了既有，Berth 就不寫它的帳密、不改它的全域偏好、不替它加站**，
「沒有索引站」「免密可進」這種跡象一概不看（brief §16.3）。雙向：選了套件內的照舊寫。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.domain import (
    HealthStatus,
    MediaKind,
    RouteCheck,
    ServiceKind,
    ServiceOrigin,
)
from berth.models import Media, QbittorrentSettings, SetupSettings
from berth.services.clients import BundledServices
from berth.services.indexer import apply_default_indexers, set_interface_login
from berth.services.jobs import JobSource, add_download
from berth.services.qbittorrent import (
    WEB_UI_PASSWORD_KEY,
    apply_qbittorrent,
    read_qbittorrent,
)
from berth.services.routes import build_routes, incomplete_path_of, save_path_of
from berth.services.settings import read_settings, write_settings
from berth.services.setup import (
    STEP_ROUTES,
    ServiceConnection,
    choose_service,
    read_status,
)
from berth.services.steps import InterfaceLogin
from tests.integration.arrange import arrange, chosen, factory_for, own
from tests.integration.factories import COMPOSE, FakeClientFactory

BUNDLED = BundledServices(targets=COMPOSE, prowlarr_api_key="mounted-key")
LOGIN = InterfaceLogin(username="labgate", password="Lab-gate-1")


async def owner(session: AsyncSession) -> None:
    await own(session, "labgate")
    await session.commit()


@pytest.mark.asyncio
async def test_an_existing_prowlarr_without_indexers_keeps_its_login(
    session: AsyncSession,
) -> None:
    """05 的 repro：一個站都沒有的既有 Prowlarr。選了既有，就不設登入、不自動加站（使用者按了
    「加入」才加勾的那幾站，M4 票 20，`test_setup_existing_prowlarr.py`）。"""
    await owner(session)
    prowlarr = FakeProwlarrClient(host_config={"username": "homeprowlarr"})
    factory = FakeClientFactory(prowlarr=prowlarr)

    await choose_service(
        session,
        factory,
        BUNDLED,
        ServiceKind.PROWLARR,
        ServiceOrigin.EXISTING,
        ServiceConnection(base_url="http://home-prowlarr:9696", api_key="theirs"),
    )

    with pytest.raises(ValueError, match="existing service"):
        await set_interface_login(session, factory, LOGIN)
    assert prowlarr.restarts == 0
    assert await prowlarr.indexers() == []
    assert (await prowlarr.host_config())["username"] == "homeprowlarr"


@pytest.mark.asyncio
async def test_an_existing_password_free_qbittorrent_gets_no_password(
    session: AsyncSession,
) -> None:
    """05 的 repro：免密可進的既有 qBittorrent。選了既有，就沒有登入那一格、不寫全域偏好。"""
    await owner(session)
    qbittorrent = FakeQbittorrentClient(base_url="http://home-qbittorrent:8080")
    factory = FakeClientFactory(qbittorrent=qbittorrent)

    await choose_service(
        session,
        factory,
        BUNDLED,
        ServiceKind.QBITTORRENT,
        ServiceOrigin.EXISTING,
        ServiceConnection(base_url="http://home-qbittorrent:8080"),
    )

    with pytest.raises(ValueError, match="existing service"):
        await apply_qbittorrent(session, factory, login=LOGIN)
    await apply_qbittorrent(session, factory)
    assert qbittorrent.writes == []


@pytest.mark.asyncio
async def test_a_bundled_choice_is_still_written(session: AsyncSession) -> None:
    """雙向：選了套件內的一樣是一個站都沒有、一樣免密可進——那兩台照舊由 Berth 設登入。"""
    await owner(session)
    qbittorrent = FakeQbittorrentClient()
    prowlarr = FakeProwlarrClient()
    factory = FakeClientFactory(qbittorrent=qbittorrent, prowlarr=prowlarr)
    for kind in (ServiceKind.QBITTORRENT, ServiceKind.PROWLARR):
        await choose_service(session, factory, BUNDLED, kind, ServiceOrigin.BUNDLED)

    await apply_qbittorrent(session, factory, login=LOGIN)
    await apply_default_indexers(session, factory, ["nyaasi"], sleep=_no_wait)
    await set_interface_login(session, factory, LOGIN, sleep=_no_wait)

    assert any(WEB_UI_PASSWORD_KEY in write for write in qbittorrent.writes)
    # 全域偏好一個都不寫，套件內也一樣（票 32）：閘門在 `test_qbittorrent_login_only.py`。
    assert all("save_path" not in write for write in qbittorrent.writes)
    assert prowlarr.restarts == 1
    assert prowlarr.signs_in("labgate", "Lab-gate-1")


@pytest.mark.parametrize("kind", [ServiceKind.QBITTORRENT, ServiceKind.PROWLARR])
@pytest.mark.asyncio
async def test_nothing_is_written_before_a_choice(session: AsyncSession, kind: ServiceKind) -> None:
    """還沒選的服務，寫入命令一律拒絕（票 05 的「沒有判定時預設套件內」一併消失）。"""
    await owner(session)
    qbittorrent = FakeQbittorrentClient()
    prowlarr = FakeProwlarrClient()
    factory = FakeClientFactory(qbittorrent=qbittorrent, prowlarr=prowlarr)
    await write_settings(session, QbittorrentSettings(base_url=COMPOSE[ServiceKind.QBITTORRENT]))

    with pytest.raises(ValueError):
        if kind is ServiceKind.QBITTORRENT:
            await apply_qbittorrent(session, factory, login=LOGIN)
        else:
            await apply_default_indexers(session, factory, ["nyaasi"])

    assert qbittorrent.writes == []
    assert prowlarr.restarts == 0


async def _no_wait(_: float) -> None:
    return None


MAGNET = "magnet:?xt=urn:btih:4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b&dn=Show"

#: 使用者自己那台 qBittorrent 的全域偏好：預設下載路徑是他的 `/downloads`，Berth 看不到；沒開
#: 「Keep incomplete torrents in」（票 22 的回報就是這一台）。
THEIR_PREFERENCES = {
    "save_path": "/downloads",
    "temp_path": "/downloads/incomplete",
    "temp_path_enabled": False,
    "auto_tmm_enabled": False,
    "category_changed_tmm_enabled": False,
}


async def at_step_four_with_existing_qbittorrent(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    """其他頁都接好（`arrange`），qBittorrent 選了使用者的那一台、頁 2 還沒按。"""
    await arrange(session, roots)
    setup = await read_settings(session, SetupSettings)
    setup.qbittorrent.steps = []
    setup.choices = {
        **setup.choices,
        ServiceKind.QBITTORRENT: chosen(ServiceOrigin.EXISTING, "http://home-qbittorrent:8080"),
    }
    await write_settings(session, setup)
    await write_settings(session, QbittorrentSettings(base_url="http://home-qbittorrent:8080"))
    await session.commit()


@pytest.mark.asyncio
async def test_an_existing_qbittorrent_keeps_its_global_paths_through_pages_two_and_three(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    await at_step_four_with_existing_qbittorrent(session, roots)
    qbittorrent = FakeQbittorrentClient(
        base_url="http://home-qbittorrent:8080", preferences=THEIR_PREFERENCES
    )
    factory = factory_for(roots, qbittorrent=qbittorrent)

    read = await read_qbittorrent(session, factory)
    # 沒有登入那一格：它的全域偏好與登入都是使用者的（票 07、22、32）。
    assert read.web_ui_login is False
    assert qbittorrent.writes == []
    # 連線測試通過就做完頁 2（M4 票 38）：沒有要按的確認鍵。
    assert (await read_status(session)).current_step == STEP_ROUTES

    routes = await build_routes(session, factory, ())
    # 第 2 條只看分類回報的路徑：使用者的全域 `/downloads` Berth 看不到也不是 Berth 的事。
    assert [row.health for row in routes.routes] == [HealthStatus.OK] * 3
    anime = next(row for row in routes.routes if row.slug == "anime")
    download_path = next(row for row in anime.checks if row.step == RouteCheck.DOWNLOAD_PATH.value)
    assert download_path.detail == (
        f"{save_path_of(str(roots['complete']), 'anime')}"
        f" · {incomplete_path_of(str(roots['incomplete']), 'anime')}"
    )

    media = Media(
        id="tv:1",
        tmdb_id=1,
        kind=MediaKind.TV,
        title_en="Show",
        title_original="Show",
        year=2024,
        folder_name="Show (2024)",
    )
    session.add(media)
    await session.commit()
    anime_route = next(row.id for row in routes.routes if row.slug == "anime")
    await add_download(
        session,
        factory,
        source=JobSource(url=MAGNET, title="[Group] Show - 01 [1080p]"),
        media_id=media.id,
        route_id=anime_route,
        user_id=None,
    )

    # 送單落在 Berth 的分類，分類的路徑是 Berth 的 complete 根目錄底下那一條；下載中落在分類自己的
    # 未完成目錄（票 22）——這一台全域的「Keep incomplete torrents in」關著也一樣。
    assert [row.category for row in qbittorrent.added] == ["berth-anime"]
    categories = {row.name: row for row in await qbittorrent.categories()}
    assert categories["berth-anime"].save_path == save_path_of(str(roots["complete"]), "anime")
    assert categories["berth-anime"].download_path == incomplete_path_of(
        str(roots["incomplete"]), "anime"
    )
    # 全域偏好從頭到尾沒被寫過。
    preferences = await qbittorrent.preferences()
    assert {key: preferences[key] for key in THEIR_PREFERENCES} == THEIR_PREFERENCES
    assert qbittorrent.writes == []
