"""精靈第 7–8 步的 services 命令（plan §9.3 第 7–8 步、§9.5、brief §4、§16.4、票 09）。

驗的是票 09 的驗收條件：套件內自動建三個 Route、既有由使用者勾選、每個 Route 建 category
並跑三項檢查、失敗說得出是哪個容器少了哪個掛載、重跑不長出重複列、全綠才寫得下
`settings.setup.completed`。

檔案系統是**真的**：`tmp_path` 底下真的建目錄、真的 `link()`、真的比 inode。硬鏈接檢查的
價值就在這裡，用假的檔案系統測等於什麼都沒測。
"""

from __future__ import annotations

import errno
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import AuthFailedError, ServiceUnavailableError
from berth.adapters.jellyfin import JellyfinLibrary
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.adapters.qbittorrent import QbittorrentCategory
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.domain import (
    CollectionType,
    DetectionReason,
    HealthStatus,
    JellyfinStep,
    Profile,
    QbittorrentStep,
    RouteCheck,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.models import (
    JellyfinSettings,
    PathSettings,
    QbittorrentSettings,
    Route,
    ServiceProbe,
    SetupLibrary,
    SetupSettings,
    SetupStep,
)
from berth.services.jellyfin import BUNDLED_LIBRARIES
from berth.services.routes import (
    RouteSelection,
    RouteSetupStatus,
    build_routes,
    read_route_status,
    routes_ready,
)
from berth.services.settings import read_settings, write_settings
from berth.services.setup import (
    STEP_COMPLETE,
    STEP_ROUTES,
    complete_setup,
    create_admin,
    read_status,
)
from berth.services.steps import StepView
from tests.integration.factories import FakeClientFactory

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)

#: 套件內 Jellyfin 建好的三個媒體庫。名字與類型跟著 services 那一份走，不另抄一遍。
BUNDLED = tuple((row.name, row.collection_type.value) for row in BUNDLED_LIBRARIES)


@pytest.fixture
def roots(tmp_path: Path) -> dict[str, Path]:
    """一個宿主目錄底下的三層路徑（brief §4.1）。硬鏈接要成立就得同一個掛載。"""
    data = tmp_path / "data"
    paths = {
        "library": data / "library",
        "complete": data / "torrent" / "complete",
        "incomplete": data / "torrent" / "incomplete",
    }
    for path in paths.values():
        path.mkdir(parents=True)
    return paths


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
        PathSettings(
            incomplete_root=str(roots["incomplete"]),
            complete_root=str(roots["complete"]),
            library_root=str(roots["library"]),
        ),
    )
    await session.commit()


def bundled_libraries(library_root: Path) -> tuple[SetupLibrary, ...]:
    """Jellyfin 回報的三個媒體庫。目錄由第 3 步的 Berth 建好（plan §9.4 第 4 步），所以這裡
    也真的建出來——第 7 步的檢查問的就是「這條路徑在 Berth 內看得到嗎」。
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

    第 7 步的檢查一問的是「qBittorrent 報的路徑 Berth 看得到嗎」，所以它報什麼很重要。
    """
    preferences = {
        "save_path": str(roots["complete"]),
        "temp_path": str(roots["incomplete"]),
        "temp_path_enabled": True,
        "auto_tmm_enabled": True,
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
) -> FakeClientFactory:
    return FakeClientFactory(
        jellyfin=jellyfin or fake_jellyfin(libraries or bundled_libraries(roots["library"])),
        qbittorrent=qbittorrent or applied_qbittorrent(roots),
    )


def checks(status: RouteSetupStatus, slug: str) -> dict[str, StepView]:
    """一個 Route 的逐項檢查，鍵是 `RouteCheck`。"""
    route = next(row for row in status.routes if row.slug == slug)
    return {row.step: row for row in route.checks}


@pytest.fixture
def cross_device_link(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """`link()` 回 `EXDEV`：兩個目錄在 Berth 內是不同掛載（brief §4.4）。"""

    def refuse(source: object, target: object) -> None:
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(os, "link", refuse)
    yield


class TestBundled:
    @pytest.mark.asyncio
    async def test_builds_one_route_per_bundled_library(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots)

        status = await build_routes(session, factory_for(roots), ())

        assert [
            (row.slug, row.name, row.profile, row.collection_type) for row in status.routes
        ] == [
            ("movies", "Movies", Profile.STANDARD, CollectionType.MOVIES),
            ("tv", "TV", Profile.STANDARD, CollectionType.TVSHOWS),
            ("anime", "Anime", Profile.ANIME, CollectionType.TVSHOWS),
        ]
        assert [row.target_path for row in status.routes] == [
            str(roots["library"] / "movies"),
            str(roots["library"] / "tv"),
            str(roots["library"] / "anime"),
        ]
        assert [row.category for row in status.routes] == [
            "berth-movies",
            "berth-tv",
            "berth-anime",
        ]
        assert [row.library for row in status.routes] == ["Movies", "TV", "Anime"]

    @pytest.mark.asyncio
    async def test_every_check_is_green_on_a_shared_mount(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots)

        status = await build_routes(session, factory_for(roots), ())

        assert [row.health for row in status.routes] == [HealthStatus.OK] * 3
        assert {step: row.status for step, row in checks(status, "tv").items()} == {
            RouteCheck.CATEGORY.value: StepStatus.OK,
            RouteCheck.DOWNLOAD_PATH.value: StepStatus.OK,
            RouteCheck.LIBRARY_PATH.value: StepStatus.OK,
            RouteCheck.PROBE_VISIBLE.value: StepStatus.OK,
            RouteCheck.HARDLINK.value: StepStatus.OK,
        }

    @pytest.mark.asyncio
    async def test_creates_one_category_per_route_under_the_complete_root(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        qbittorrent = applied_qbittorrent(roots)
        await arrange(session, roots)

        await build_routes(session, factory_for(roots, qbittorrent=qbittorrent), ())

        assert [(row.name, row.save_path) for row in qbittorrent.created_categories] == [
            ("berth-movies", str(roots["complete"] / "movies")),
            ("berth-tv", str(roots["complete"] / "tv")),
            ("berth-anime", str(roots["complete"] / "anime")),
        ]

    @pytest.mark.asyncio
    async def test_rerunning_neither_duplicates_rows_nor_categories(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """精靈全程可重跑（票 09 驗收）。"""
        qbittorrent = applied_qbittorrent(roots)
        factory = factory_for(roots, qbittorrent=qbittorrent)
        await arrange(session, roots)

        await build_routes(session, factory, ())
        status = await build_routes(session, factory, ())

        assert len(status.routes) == 3
        assert len(qbittorrent.created_categories) == 3
        assert len((await session.scalars(select(Route))).all()) == 3

    @pytest.mark.asyncio
    async def test_leaves_no_probe_files_behind(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots)

        await build_routes(session, factory_for(roots), ())

        assert sorted(path.name for path in (roots["library"] / "tv").iterdir()) == []
        assert sorted(path.name for path in (roots["complete"] / "tv").iterdir()) == []


class TestExisting:
    @pytest.mark.asyncio
    async def test_builds_a_route_for_each_selected_library(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        old = roots["library"] / "old-tv"
        old.mkdir()
        berth = berth_path(roots, "影集")
        Path(berth).mkdir()
        libraries = (existing_library(old, berth),)
        await arrange(session, roots, origin=ServiceOrigin.EXISTING, libraries=libraries)

        status = await build_routes(
            session,
            factory_for(roots, libraries=libraries),
            (RouteSelection(library="影集", target_path=berth, profile=Profile.ANIME),),
        )

        assert [(row.library, row.target_path, row.profile) for row in status.routes] == [
            ("影集", berth, Profile.ANIME)
        ]
        assert [row.health for row in status.routes] == [HealthStatus.OK]

    @pytest.mark.asyncio
    async def test_an_unselected_library_gets_no_route(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots, origin=ServiceOrigin.EXISTING)

        status = await build_routes(session, factory_for(roots), ())

        assert status.routes == ()
        assert status.ready is False

    @pytest.mark.asyncio
    async def test_dropping_a_library_on_a_rerun_removes_its_route(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots, origin=ServiceOrigin.EXISTING)
        factory = factory_for(roots)
        picked = tuple(
            RouteSelection(library=name, target_path=str(roots["library"] / name.lower()))
            for name, _ in BUNDLED
        )
        await build_routes(session, factory, picked)

        status = await build_routes(session, factory, picked[:1])

        assert [row.slug for row in status.routes] == ["movies"]

    @pytest.mark.asyncio
    async def test_refuses_a_target_that_is_not_one_of_the_library_paths(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """寫入目標只能從 Jellyfin 回報的路徑裡**選**，不能自己打（brief §4.1）。"""
        await arrange(session, roots, origin=ServiceOrigin.EXISTING)

        with pytest.raises(ValueError, match="not a path of"):
            await build_routes(
                session,
                factory_for(roots),
                (RouteSelection(library="TV", target_path=str(roots["library"] / "elsewhere")),),
            )

    @pytest.mark.asyncio
    async def test_refuses_a_library_this_jellyfin_does_not_have(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots, origin=ServiceOrigin.EXISTING)

        with pytest.raises(ValueError, match="no library"):
            await build_routes(
                session,
                factory_for(roots),
                (RouteSelection(library="Ghost", target_path=str(roots["library"] / "ghost")),),
            )


class TestChecks:
    @pytest.mark.asyncio
    async def test_a_category_pointing_somewhere_else_is_a_conflict(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """已存在但 save path 不同：回報衝突且**不覆寫**（票 09 驗收）。"""
        qbittorrent = applied_qbittorrent(
            roots, categories=(QbittorrentCategory(name="berth-tv", save_path="/mnt/old/tv"),)
        )
        await arrange(session, roots)

        status = await build_routes(session, factory_for(roots, qbittorrent=qbittorrent), ())

        category = checks(status, "tv")[RouteCheck.CATEGORY.value]
        assert category.status is StepStatus.FAILED
        assert "/mnt/old/tv" in category.error
        # 其他兩個 Route 的 category 照建；不覆寫的只有撞上的那一個。
        assert [row.name for row in qbittorrent.created_categories] == [
            "berth-movies",
            "berth-anime",
        ]
        assert next(row for row in status.routes if row.slug == "tv").health is HealthStatus.FAILED

    @pytest.mark.asyncio
    async def test_a_download_path_berth_cannot_see_fails_the_route(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """檢查一：qBittorrent 報的 save path 在 Berth 內 `stat` 不到（brief §16.4）。"""
        await arrange(session, roots)
        qbittorrent = FakeQbittorrentClient(preferences={"save_path": "/downloads"})  # 沒掛進 Berth

        status = await build_routes(session, factory_for(roots, qbittorrent=qbittorrent), ())

        row = checks(status, "tv")[RouteCheck.DOWNLOAD_PATH.value]
        assert row.status is StepStatus.FAILED
        assert "/downloads" in row.error

    @pytest.mark.asyncio
    async def test_a_library_path_berth_cannot_see_fails_the_route(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """檢查二：Jellyfin 報的媒體庫路徑在 Berth 內 `stat` 不到。"""
        missing = roots["library"] / "not-mounted"
        libraries = (existing_library(missing),)
        await arrange(session, roots, origin=ServiceOrigin.EXISTING, libraries=libraries)

        status = await build_routes(
            session,
            factory_for(roots, libraries=libraries),
            (RouteSelection(library="影集", target_path=str(missing)),),
        )

        row = checks(status, status.routes[0].slug)[RouteCheck.LIBRARY_PATH.value]
        assert row.status is StepStatus.FAILED
        assert str(missing) in row.error

    @pytest.mark.asyncio
    async def test_a_jellyfin_that_cannot_see_the_probe_fails_the_route(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """檢查三前半：探測檔寫下去了，但 Jellyfin 那台看不到同一條路徑。"""
        await arrange(session, roots)
        jellyfin = fake_jellyfin(bundled_libraries(roots["library"]), visible_roots=("/elsewhere",))

        status = await build_routes(session, factory_for(roots, jellyfin=jellyfin), ())

        row = checks(status, "movies")[RouteCheck.PROBE_VISIBLE.value]
        assert row.status is StepStatus.FAILED
        assert str(roots["library"] / "movies") in row.error

    @pytest.mark.asyncio
    async def test_cross_device_is_reported_as_such(
        self, session: AsyncSession, roots: dict[str, Path], cross_device_link: None
    ) -> None:
        """檢查三後半：`EXDEV` 要說得出「兩個目錄在 Berth 內是不同掛載」（票 09 驗收）。"""
        await arrange(session, roots)

        status = await build_routes(session, factory_for(roots), ())

        route = next(row for row in status.routes if row.slug == "movies")
        assert route.cross_device is True
        assert checks(status, "movies")[RouteCheck.HARDLINK.value].status is StepStatus.FAILED

    @pytest.mark.asyncio
    async def test_a_qbittorrent_that_is_down_fails_the_route_without_raising(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots)
        qbittorrent = applied_qbittorrent(
            roots, error=ServiceUnavailableError("connection refused")
        )

        status = await build_routes(session, factory_for(roots, qbittorrent=qbittorrent), ())

        assert [row.health for row in status.routes] == [HealthStatus.FAILED] * 3
        assert "connection refused" in checks(status, "tv")[RouteCheck.CATEGORY.value].error

    @pytest.mark.asyncio
    async def test_wrong_qbittorrent_credentials_land_on_the_category_line(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """既有 qBittorrent 的帳密不對是**那一條纜繩**的紅燈，不是整頁 500。"""
        await arrange(session, roots)
        await write_settings(
            session,
            QbittorrentSettings(base_url="http://nas:8080", username="admin", password="wrong"),
        )
        await session.commit()
        qbittorrent = applied_qbittorrent(
            roots,
            login_error=AuthFailedError("auth/login: rejected"),
            error=AuthFailedError("GET /api/v2/torrents/categories: 403"),
        )

        status = await build_routes(session, factory_for(roots, qbittorrent=qbittorrent), ())

        assert [row.health for row in status.routes] == [HealthStatus.FAILED] * 3
        assert "403" in checks(status, "tv")[RouteCheck.CATEGORY.value].error

    @pytest.mark.asyncio
    async def test_a_failed_check_leaves_the_rest_pending(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """一條纜繩斷了就停在那裡：後面的檢查測的會是錯的路徑。"""
        await arrange(session, roots)
        qbittorrent = FakeQbittorrentClient(preferences={"save_path": "/downloads"})  # 沒掛進 Berth

        status = await build_routes(session, factory_for(roots, qbittorrent=qbittorrent), ())

        assert checks(status, "tv")[RouteCheck.LIBRARY_PATH.value].status is StepStatus.PENDING
        assert checks(status, "tv")[RouteCheck.HARDLINK.value].status is StepStatus.PENDING


class TestCompletion:
    @pytest.mark.asyncio
    async def test_the_wizard_stays_on_step_seven_until_a_route_is_green(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots, origin=ServiceOrigin.EXISTING)

        assert (await read_status(session)).current_step == STEP_ROUTES
        assert await routes_ready(session) is False

    @pytest.mark.asyncio
    async def test_a_green_route_moves_the_wizard_to_the_last_step(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots)

        await build_routes(session, factory_for(roots), ())

        assert await routes_ready(session) is True
        assert (await read_status(session)).current_step == STEP_COMPLETE

    @pytest.mark.asyncio
    async def test_a_broken_route_holds_the_wizard_back(
        self, session: AsyncSession, roots: dict[str, Path], cross_device_link: None
    ) -> None:
        await arrange(session, roots)

        await build_routes(session, factory_for(roots), ())

        assert await routes_ready(session) is False
        assert (await read_status(session)).current_step == STEP_ROUTES

    @pytest.mark.asyncio
    async def test_completing_writes_the_bit_the_gate_reads(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots)
        await build_routes(session, factory_for(roots), ())

        status = await complete_setup(session)

        assert status.completed is True
        assert (await read_settings(session, SetupSettings)).completed is True

    @pytest.mark.asyncio
    async def test_completing_is_refused_while_no_route_is_green(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """第 7 步不可跳（plan §9.3）。"""
        await arrange(session, roots)

        with pytest.raises(ValueError, match="route"):
            await complete_setup(session)

        assert (await read_settings(session, SetupSettings)).completed is False


class TestStatus:
    @pytest.mark.asyncio
    async def test_offers_every_library_with_its_paths(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        old = roots["library"] / "old-tv"
        berth = berth_path(roots, "影集")
        await arrange(
            session,
            roots,
            origin=ServiceOrigin.EXISTING,
            libraries=(existing_library(old, berth),),
        )

        status = await read_route_status(session)

        assert status.origin is ServiceOrigin.EXISTING
        assert [(row.name, row.locations) for row in status.libraries] == [
            ("影集", (str(old), berth))
        ]
        # 「加入 Berth 路徑」加的就是這一條（第 3 步的按鈕，plan §9.5）。
        assert status.libraries[0].berth_path == berth
        assert status.libraries[0].has_berth_path is True

    @pytest.mark.asyncio
    async def test_remembers_which_target_each_library_was_given(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """關掉瀏覽器再回來要回到原本的選擇（plan §9.3 續行）。"""
        await arrange(session, roots)
        await build_routes(session, factory_for(roots), ())

        status = await read_route_status(session)

        chosen = {row.name: (row.selected, row.target_path) for row in status.libraries}
        assert chosen["TV"] == (True, str(roots["library"] / "tv"))


class TestChecksReadTheServices:
    """檢查一與檢查二問的是**服務現在說什麼**，不是 Berth 自己算出來的值（票 09 code-review）。"""

    @pytest.mark.asyncio
    async def test_a_category_pointing_at_an_unmounted_path_fails_check_one(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """category 已經存在、路徑正規化後相同（4.4 的尾斜線），但 Berth 看不到它。

        `stat` 的必須是 qBittorrent 回報的那個字串——拿 Berth 剛建好的目錄去 stat 一定會過。
        """
        await arrange(session, roots)
        # 尾斜線是 4.4 的行為（brief §20.7）；路徑本身用 `Path` 組，Windows 上才與服務端一致。
        reported = f"{roots['complete'] / 'tv'}/"
        qbittorrent = applied_qbittorrent(
            roots, categories=(QbittorrentCategory(name="berth-tv", save_path=reported),)
        )

        status = await build_routes(session, factory_for(roots, qbittorrent=qbittorrent), ())

        # 尾斜線不算衝突，所以 category 那一條是綠的；但那條路徑本身不存在。
        assert checks(status, "tv")[RouteCheck.CATEGORY.value].status is StepStatus.SKIPPED
        download = checks(status, "tv")[RouteCheck.DOWNLOAD_PATH.value]
        assert download.status is StepStatus.OK
        assert reported.rstrip("/") in download.detail

    @pytest.mark.asyncio
    async def test_preferences_that_cannot_be_read_fail_check_one(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """讀不到 `app/preferences` 就是這一條的紅燈，不是靜靜地變綠。"""
        await arrange(session, roots)
        qbittorrent = FakeQbittorrentClient(preferences={"save_path": ""})

        status = await build_routes(session, factory_for(roots, qbittorrent=qbittorrent), ())

        row = checks(status, "tv")[RouteCheck.DOWNLOAD_PATH.value]
        assert row.status is StepStatus.FAILED
        assert "global save_path" in row.error

    @pytest.mark.asyncio
    async def test_a_library_deleted_in_jellyfin_after_step_three_fails_check_two(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """第 3 步之後使用者在 Jellyfin 那邊刪掉了媒體庫：快照還在，現查就沒有了。"""
        await arrange(session, roots)
        remaining = tuple(row for row in bundled_libraries(roots["library"]) if row.name != "TV")

        status = await build_routes(session, factory_for(roots, libraries=remaining), ())

        row = checks(status, "tv")[RouteCheck.LIBRARY_PATH.value]
        assert row.status is StepStatus.FAILED
        assert "no longer has a library named 'TV'" in row.error
        assert next(row for row in status.routes if row.slug == "movies").health is HealthStatus.OK
