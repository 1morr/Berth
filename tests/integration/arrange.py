"""把資料庫與假服務推到「精靈某一步剛做完」的狀態（票 09、票 10 共用）。

第 5 步的檢查與健康頁的 Route 檢查是同一組（plan §9.5），兩邊的測試因此需要同一個
起點：三層路徑真的存在、Jellyfin 真的報得出媒體庫、qBittorrent 報的 save path 就是
Berth 的 complete root。安排寫兩份的話，一邊改了另一邊會悄悄測到別的東西。
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from berth.adapters.indexer.fake import FakeIndexerSearch
from berth.adapters.jellyfin import JellyfinLibrary
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.adapters.qbittorrent import QbittorrentCategory
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.adapters.tmdb.fake import FakeTmdbClient
from berth.domain import (
    DetectionReason,
    JellyfinStep,
    QbittorrentStep,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.models import (
    IndexerSettings,
    JellyfinSettings,
    PathSettings,
    QbittorrentSettings,
    ServiceProbe,
    SetupLibrary,
    SetupSettings,
    SetupStep,
)
from berth.services.jellyfin import BUNDLED_LIBRARIES
from berth.services.routes import delete_route
from berth.services.settings import read_settings, write_settings
from berth.services.setup import create_admin
from tests.integration.factories import FakeClientFactory

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)

#: 套件內 Jellyfin 建好的三個媒體庫。名字與類型跟著 services 那一份走，不另抄一遍。
BUNDLED = tuple((row.name, row.collection_type.value) for row in BUNDLED_LIBRARIES)


async def arrange(
    session: AsyncSession,
    roots: dict[str, Path],
    *,
    origin: ServiceOrigin = ServiceOrigin.BUNDLED,
    libraries: tuple[SetupLibrary, ...] | None = None,
) -> None:
    """把資料庫推到「前三個泊位都接好、輪到媒體庫路徑」的狀態。"""
    await create_admin(session, username="skipper", password="harbour", apply_to_services=True)
    setup = await read_settings(session, SetupSettings)
    setup.jellyfin.steps = [
        SetupStep(key=step.value, status=StepStatus.OK) for step in JellyfinStep
    ]
    setup.qbittorrent.steps = [
        SetupStep(key=step.value, status=StepStatus.OK)
        for step in QbittorrentStep
        if step is not QbittorrentStep.PASSWORD
    ]
    setup.indexer.steps = [SetupStep(key="nyaasi", status=StepStatus.OK)]
    setup.tmdb.steps = [SetupStep(key="configuration", status=StepStatus.OK)]
    setup.jellyfin.libraries = list(libraries or bundled_libraries(roots["library"]))
    setup.services = {
        ServiceKind.JELLYFIN: ServiceProbe(
            origin=origin,
            reason=(
                DetectionReason.SETUP_PENDING
                if origin is ServiceOrigin.BUNDLED
                else DetectionReason.SETUP_COMPLETED
            ),
            base_url="http://jellyfin:8096",
            checked_at=NOW,
        ),
        ServiceKind.QBITTORRENT: ServiceProbe(
            origin=ServiceOrigin.BUNDLED,
            reason=DetectionReason.ANONYMOUS_OK,
            base_url="http://qbittorrent:8080",
            checked_at=NOW,
        ),
        ServiceKind.PROWLARR: ServiceProbe(
            origin=ServiceOrigin.BUNDLED,
            reason=DetectionReason.NO_INDEXERS,
            base_url="http://prowlarr:9696",
            checked_at=NOW,
        ),
    }
    await write_settings(session, setup)
    await write_settings(
        session,
        JellyfinSettings(base_url="http://jellyfin:8096", api_key="key-berth-0"),
    )
    await write_settings(session, QbittorrentSettings(base_url="http://qbittorrent:8080"))
    await write_settings(
        session,
        IndexerSettings(kind="prowlarr", base_url="http://prowlarr:9696", api_key="key-prowlarr-0"),
    )
    await write_settings(
        session,
        PathSettings(
            incomplete_root=str(roots["incomplete"]),
            complete_root=str(roots["complete"]),
            library_root=str(roots["library"]),
        ),
    )
    await session.commit()


def bundled_libraries(library_root: Path) -> tuple[SetupLibrary, ...]:
    """Jellyfin 回報的三個媒體庫。目錄由第 3 步的 Berth 建好（plan §9.4 第 4 步），所以這裡
    也真的建出來——第 5 步的檢查問的就是「這條路徑在 Berth 內看得到嗎」。
    """
    rows = []
    for index, (name, collection_type) in enumerate(BUNDLED):
        path = library_root / name.lower()
        path.mkdir(parents=True, exist_ok=True)
        rows.append(
            SetupLibrary(
                name=name,
                item_id=f"item-{index}",
                collection_type=collection_type,
                locations=[str(path)],
                metadata_fetchers=["TheMovieDb"],
            )
        )
    return tuple(rows)


def with_second_disk(roots: dict[str, Path]) -> tuple[tuple[SetupLibrary, ...], Path]:
    """TV 媒體庫在 Jellyfin 上多掛了一條路徑（brief §4.3 的「兩顆碟各一個 Route」，票 14）。

    第二條 Route 的前提：同一個媒體庫、不同的寫入目標。目錄真的建出來，檢查才問得到它。
    """
    disk = roots["library"] / "tv-disk2"
    disk.mkdir(exist_ok=True)
    libraries = tuple(
        row.model_copy(update={"locations": [*row.locations, str(disk)]})
        if row.name == "TV"
        else row
        for row in bundled_libraries(roots["library"])
    )
    return libraries, disk


def berth_path(roots: dict[str, Path], name: str) -> str:
    """「加入 Berth 路徑」會加的那一條：`<library root>/<slug>`（CONTEXT.md）。

    容器路徑一律以 `/` 相接，所以這裡也照著組——`Path` 在 Windows 上會換成反斜線，
    而正式部署裡兩邊看到的都是 Linux 路徑。
    """
    return f"{roots['library']}/{name}"


def existing_library(*locations: Path | str) -> SetupLibrary:
    """使用者自己那台 Jellyfin 的一個媒體庫，可能有好幾條路徑（brief §4.3）。"""
    return SetupLibrary(
        name="影集",
        item_id="a1",
        collection_type="tvshows",
        locations=[str(path) for path in locations],
        metadata_fetchers=["TheMovieDb"],
    )


def applied_qbittorrent(roots: dict[str, Path], **overrides: object) -> FakeQbittorrentClient:
    """第 4 步套用過建議偏好之後的那一台：全域 save path 就是 Berth 的 complete root。

    第 5 步的檢查一問的是「qBittorrent 報的路徑 Berth 看得到嗎」，所以它報什麼很重要。
    """
    preferences = {
        "save_path": str(roots["complete"]),
        "temp_path": str(roots["incomplete"]),
        "temp_path_enabled": True,
        "auto_tmm_enabled": True,
        "category_changed_tmm_enabled": True,
    }
    return FakeQbittorrentClient(preferences=preferences, **overrides)  # type: ignore[arg-type]


def fake_jellyfin(libraries: tuple[SetupLibrary, ...], **overrides: object) -> FakeJellyfinClient:
    """一台跑完初始精靈、而且**真的報得出這幾個媒體庫**的 Jellyfin。

    檢查二是向 Jellyfin 現查路徑（不是讀第 3 步的快照），所以假服務也得真的有它們。
    """
    defaults: dict[str, object] = {
        "startup_wizard_completed": True,
        "libraries": tuple(
            JellyfinLibrary(
                name=row.name,
                item_id=row.item_id,
                collection_type=row.collection_type,
                locations=tuple(row.locations),
                type_options=(),
            )
            for row in libraries
        ),
    }
    return FakeJellyfinClient(**{**defaults, **overrides})  # type: ignore[arg-type]


def factory_for(
    roots: dict[str, Path],
    *,
    libraries: tuple[SetupLibrary, ...] | None = None,
    qbittorrent: FakeQbittorrentClient | None = None,
    jellyfin: FakeJellyfinClient | None = None,
    tmdb: FakeTmdbClient | None = None,
    indexer_search: FakeIndexerSearch | None = None,
) -> FakeClientFactory:
    return FakeClientFactory(
        jellyfin=jellyfin or fake_jellyfin(libraries or bundled_libraries(roots["library"])),
        qbittorrent=qbittorrent or applied_qbittorrent(roots),
        tmdb=tmdb or FakeTmdbClient(),
        indexer_search=indexer_search or FakeIndexerSearch(),
    )


def delete_once_during_checks(
    qbittorrent: FakeQbittorrentClient,
    sessions: async_sessionmaker[AsyncSession],
    route_id: int,
) -> None:
    """下一輪檢查問 qBittorrent 的那一刻，另一個 session 把這條 Route 刪掉（票 14a、票 01）。

    五條纜繩在鎖外打網路，那幾秒就是另一個分頁按下刪除的空窗。**只刪一次**：整組重跑會
    逐條問，刪第二次拿到的是刪除自己的拒絕，不是這裡要造的那個競爭。
    """
    categories = qbittorrent.categories
    deleted = False

    async def deleted_meanwhile() -> tuple[QbittorrentCategory, ...]:
        nonlocal deleted
        if not deleted:
            deleted = True
            async with sessions() as other:
                await delete_route(other, route_id)
        return await categories()

    # 替身的方法是實例屬性，指派回去就是「這一輪改問這個」。
    qbittorrent.categories = deleted_meanwhile  # type: ignore[method-assign]
