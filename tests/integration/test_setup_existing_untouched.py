"""既有服務不被改動（M4 票 05、brief §19 2026-09-26）。

`berth-lab` 實測：使用者自己的 Prowlarr 還沒加索引站就被判成套件內，第 6 步以第 1 步的帳密
`PUT config/host` 把它的登入覆寫掉；免密可進的舊 qBittorrent 走同一條路。規則是**只有 compose
主機名上探到的才可能是套件內**，使用者填的位址一律既有——Jellyfin 例外（plan §9.3 第 2 步）。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.adapters.prowlarr.fake import FakeProwlarrClient
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.domain import (
    DetectionReason,
    HealthStatus,
    IndexerKind,
    MediaKind,
    RouteCheck,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.models import Media, QbittorrentSettings, SetupSettings
from berth.services.health import check_health
from berth.services.indexer import apply_default_indexers, connect_indexer
from berth.services.jobs import JobSource, add_download
from berth.services.qbittorrent import (
    WEB_UI_PASSWORD_KEY,
    apply_qbittorrent,
    read_qbittorrent_diff,
)
from berth.services.routes import build_routes, save_path_of
from berth.services.settings import read_settings, write_settings
from berth.services.setup import (
    STEP_QBITTORRENT,
    STEP_ROUTES,
    ServiceConnection,
    SetupStatus,
    connect_service,
    create_admin,
    read_status,
)
from tests.integration.arrange import NOW, arrange, factory_for
from tests.integration.factories import COMPOSE, FakeClientFactory


def verdict(status: SetupStatus, kind: ServiceKind) -> tuple[ServiceOrigin, DetectionReason]:
    row = next(r for r in status.services if r.kind is kind)
    return row.origin, row.reason


async def owner(session: AsyncSession) -> None:
    """第 1 步勾了「同一組帳密」：套件內的那兩台會被設成這一組。"""
    await create_admin(session, username="labgate", password="harbour", apply_to_services=True)
    await session.commit()


@pytest.mark.asyncio
async def test_a_typed_prowlarr_without_indexers_is_existing_and_keeps_its_login(
    session: AsyncSession,
) -> None:
    await owner(session)
    prowlarr = FakeProwlarrClient(host_config={"username": "homeprowlarr"})
    factory = FakeClientFactory(prowlarr=prowlarr)

    status = await connect_service(
        session,
        ServiceKind.PROWLARR,
        ServiceConnection(base_url="http://home-prowlarr:9696", api_key="theirs"),
        factory,
        compose_hosts=COMPOSE,
    )

    assert verdict(status, ServiceKind.PROWLARR)[0] is ServiceOrigin.EXISTING
    # 第 6 步對既有 Prowlarr 不加站、不設登入：`config/host` 一次都沒寫。
    with pytest.raises(ValueError, match="existing service"):
        await apply_default_indexers(session, factory, ["nyaasi"])
    assert prowlarr.restarts == 0
    assert (await prowlarr.host_config())["username"] == "homeprowlarr"


@pytest.mark.asyncio
async def test_a_prowlarr_typed_at_the_indexer_berth_is_existing_and_keeps_its_login(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    """第 6 步的另一扇門：套件內 Prowlarr 連不上時，泊位照樣給連線表單（`IndexerStep`）。

    使用者在那裡填自己的 Prowlarr，判定也要跟著變成既有；只存位址的話，第 2 步留下的
    「套件內」會讓預設站清單與 `config/host` 對著他那一台跑。
    """
    await arrange(session, roots)
    prowlarr = FakeProwlarrClient(host_config={"username": "homeprowlarr"})
    factory = FakeClientFactory(prowlarr=prowlarr)

    status = await connect_indexer(
        session,
        factory,
        kind=IndexerKind.PROWLARR,
        base_url="http://home-prowlarr:9696",
        api_key="theirs",
    )

    assert status.origin is ServiceOrigin.EXISTING
    with pytest.raises(ValueError, match="existing service"):
        await apply_default_indexers(session, factory, ["nyaasi"])
    assert prowlarr.restarts == 0
    assert (await prowlarr.host_config())["username"] == "homeprowlarr"


@pytest.mark.asyncio
async def test_a_typed_password_free_qbittorrent_is_existing_and_gets_no_password(
    session: AsyncSession,
) -> None:
    await owner(session)
    qbittorrent = FakeQbittorrentClient(base_url="http://home-qbittorrent:8080")
    factory = FakeClientFactory(qbittorrent=qbittorrent)

    status = await connect_service(
        session,
        ServiceKind.QBITTORRENT,
        ServiceConnection(base_url="http://home-qbittorrent:8080"),
        factory,
        compose_hosts=COMPOSE,
    )

    assert verdict(status, ServiceKind.QBITTORRENT) == (
        ServiceOrigin.EXISTING,
        DetectionReason.CONNECTED,
    )
    await apply_qbittorrent(session, factory)
    assert all(WEB_UI_PASSWORD_KEY not in write for write in qbittorrent.writes)


@pytest.mark.asyncio
async def test_the_compose_hostnames_are_still_bundled_when_typed(session: AsyncSession) -> None:
    """雙向：compose 主機名上的空 Prowlarr 與免密 qBittorrent，手動填了仍然是套件內。

    讀不到唯讀掛載的套件內 Prowlarr，使用者貼了 key 之後照樣要跑預設索引站（票 08）。
    """
    factory = FakeClientFactory()

    await connect_service(
        session,
        ServiceKind.QBITTORRENT,
        ServiceConnection(base_url="http://qbittorrent:8080"),
        factory,
        compose_hosts=COMPOSE,
    )
    status = await connect_service(
        session,
        ServiceKind.PROWLARR,
        ServiceConnection(base_url="http://prowlarr:9696/", api_key="pasted"),
        factory,
        compose_hosts=COMPOSE,
    )

    assert verdict(status, ServiceKind.QBITTORRENT) == (
        ServiceOrigin.BUNDLED,
        DetectionReason.ANONYMOUS_OK,
    )
    assert verdict(status, ServiceKind.PROWLARR) == (
        ServiceOrigin.BUNDLED,
        DetectionReason.NO_INDEXERS,
    )


@pytest.mark.asyncio
async def test_a_typed_jellyfin_that_never_ran_its_wizard_is_still_bundled(
    session: AsyncSession,
) -> None:
    """Jellyfin 是例外：沒跑過初始精靈的那一台上沒有任何人的帳號可以蓋掉（plan §9.3 第 2 步）。"""
    factory = FakeClientFactory(
        jellyfin=FakeJellyfinClient(base_url="http://nas:8096", startup_wizard_completed=False)
    )

    status = await connect_service(
        session,
        ServiceKind.JELLYFIN,
        ServiceConnection(base_url="http://nas:8096"),
        factory,
        compose_hosts=COMPOSE,
    )

    assert verdict(status, ServiceKind.JELLYFIN) == (
        ServiceOrigin.BUNDLED,
        DetectionReason.SETUP_PENDING,
    )


MAGNET = "magnet:?xt=urn:btih:4bd0f6ef1d3b1e3cbb1e1b6b6c2a9c7d8e5f0a1b&dn=Show"

#: 使用者自己那台 qBittorrent 的全域偏好：預設下載路徑是他的 `/downloads`，Berth 看不到。
THEIR_PREFERENCES = {
    "save_path": "/downloads",
    "temp_path": "/downloads/incomplete",
    "temp_path_enabled": True,
    "auto_tmm_enabled": False,
    "category_changed_tmm_enabled": False,
}


async def at_step_four_with_existing_qbittorrent(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    """其他泊位都接好（`arrange`），qBittorrent 換成使用者的、第 4 步還沒按。"""
    await arrange(session, roots)
    setup = await read_settings(session, SetupSettings)
    setup.qbittorrent.steps = []
    setup.services = {
        **setup.services,
        ServiceKind.QBITTORRENT: setup.services[ServiceKind.QBITTORRENT].model_copy(
            update={
                "origin": ServiceOrigin.EXISTING,
                "reason": DetectionReason.CONNECTED,
                "base_url": "http://home-qbittorrent:8080",
                "configured": True,
                "checked_at": NOW,
            }
        ),
    }
    await write_settings(session, setup)
    await write_settings(session, QbittorrentSettings(base_url="http://home-qbittorrent:8080"))
    await session.commit()


@pytest.mark.asyncio
async def test_an_existing_qbittorrent_keeps_its_global_paths_through_steps_four_and_five(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    await at_step_four_with_existing_qbittorrent(session, roots)
    qbittorrent = FakeQbittorrentClient(
        base_url="http://home-qbittorrent:8080", preferences=THEIR_PREFERENCES
    )
    factory = factory_for(roots, qbittorrent=qbittorrent)
    assert (await read_status(session)).current_step == STEP_QBITTORRENT

    diff = await read_qbittorrent_diff(session, factory)
    # 建議值照樣列出來給人看，只是不寫。
    assert diff.writes_preferences is False
    assert any(row.differs for row in diff.diffs)

    applied = await apply_qbittorrent(session, factory)
    assert qbittorrent.writes == []
    # 五條纜繩都繫上：Berth 看過、沒動它，細節是它自己的現值。
    assert [(row.step, row.status, row.detail) for row in applied.steps][:5] == [
        ("temp_path_enabled", StepStatus.SKIPPED, "true"),
        ("temp_path", StepStatus.SKIPPED, "/downloads/incomplete"),
        ("save_path", StepStatus.SKIPPED, "/downloads"),
        ("auto_tmm_enabled", StepStatus.SKIPPED, "false"),
        ("category_changed_tmm_enabled", StepStatus.SKIPPED, "false"),
    ]
    assert (await read_status(session)).current_step == STEP_ROUTES

    routes = await build_routes(session, factory, ())
    # 第 2 條只看分類回報的路徑：使用者的全域 `/downloads` Berth 看不到也不是 Berth 的事。
    assert [row.health for row in routes.routes] == [HealthStatus.OK] * 3
    anime = next(row for row in routes.routes if row.slug == "anime")
    download_path = next(row for row in anime.checks if row.step == RouteCheck.DOWNLOAD_PATH.value)
    assert download_path.detail == save_path_of(str(roots["complete"]), "anime")

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

    # 送單落在 Berth 的分類，分類的路徑是 Berth 的 complete 根目錄底下那一條。
    assert [row.category for row in qbittorrent.added] == ["berth-anime"]
    categories = {row.name: row.save_path for row in await qbittorrent.categories()}
    assert categories["berth-anime"] == save_path_of(str(roots["complete"]), "anime")
    # 全域偏好從頭到尾沒被寫過。
    preferences = await qbittorrent.preferences()
    assert {key: preferences[key] for key in THEIR_PREFERENCES} == THEIR_PREFERENCES
    assert qbittorrent.writes == []


@pytest.mark.asyncio
async def test_an_existing_qbittorrent_reports_no_drift(
    session: AsyncSession, roots: dict[str, Path]
) -> None:
    """它的全域偏好本來就是使用者的：與建議值不同不是漂移，健康頁不給「還原建議設定」。"""
    await at_step_four_with_existing_qbittorrent(session, roots)
    qbittorrent = FakeQbittorrentClient(
        base_url="http://home-qbittorrent:8080", preferences=THEIR_PREFERENCES
    )

    report = await check_health(session, factory_for(roots, qbittorrent=qbittorrent), now=NOW)

    row = next(row for row in report.services if row.kind is ServiceKind.QBITTORRENT)
    assert (row.status, row.drift) == (HealthStatus.OK, ())
