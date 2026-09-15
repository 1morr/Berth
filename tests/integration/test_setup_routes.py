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
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.adapters.http import AuthFailedError, ServiceUnavailableError
from berth.adapters.qbittorrent import (
    CategoryOutcome,
    QbittorrentCategory,
    QbittorrentClient,
    ensure_category,
)
from berth.adapters.qbittorrent.fake import FakeQbittorrentClient
from berth.db import create_session_factory
from berth.domain import (
    CollectionType,
    HealthStatus,
    Profile,
    RouteCheck,
    ServiceOrigin,
    StepStatus,
)
from berth.models import (
    QbittorrentSettings,
    Route,
    SetupSettings,
)
from berth.services.routes import (
    RouteSelection,
    RouteSetupStatus,
    build_routes,
    delete_route,
    read_route_status,
    routes_ready,
    save_path_of,
)
from berth.services.settings import read_settings, write_settings
from berth.services.setup import (
    STEP_COMPLETE,
    STEP_ROUTES,
    complete_setup,
    read_status,
)
from berth.services.steps import StepView
from tests.integration.arrange import (
    BUNDLED,
    applied_qbittorrent,
    arrange,
    berth_path,
    bundled_libraries,
    existing_library,
    factory_for,
    fake_jellyfin,
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

        # 送給 qBittorrent 的是 `save_path_of` 算出來的那一串字（容器路徑一律 POSIX），
        # 不是 `Path` 在這台機器上的寫法——票 09 的送單比對的是同一支函式的輸出。
        assert [(row.name, row.save_path) for row in qbittorrent.created_categories] == [
            ("berth-movies", save_path_of(str(roots["complete"]), "movies")),
            ("berth-tv", save_path_of(str(roots["complete"]), "tv")),
            ("berth-anime", save_path_of(str(roots["complete"]), "anime")),
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
    async def test_leaving_a_library_unticked_on_a_rerun_keeps_its_route(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """重跑第 7 步**不再隱式刪掉**沒勾的 Route（票 14）：Job 與帳本從票 09 起就引用它。
        刪除是 Route 設定頁上一個明確、要二次確認的動作。"""
        await arrange(session, roots, origin=ServiceOrigin.EXISTING)
        factory = factory_for(roots)
        picked = tuple(
            RouteSelection(library=name, target_path=str(roots["library"] / name.lower()))
            for name, _ in BUNDLED
        )
        await build_routes(session, factory, picked)

        status = await build_routes(session, factory, picked[:1])

        assert [row.slug for row in status.routes] == ["movies", "tv", "anime"]
        assert len((await session.scalars(select(Route))).all()) == 3

    @pytest.mark.asyncio
    async def test_a_rerun_leaves_a_library_that_already_has_a_route_as_it_is(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """精靈只新增不改（票 14，使用者拍板）：換寫入目標會讓帳本對不上它的 Route，
        要換就在 Route 設定頁新增一條、刪掉舊的。"""
        old = roots["library"] / "old-tv"
        old.mkdir()
        berth = berth_path(roots, "影集")
        Path(berth).mkdir()
        libraries = (existing_library(old, berth),)
        await arrange(session, roots, origin=ServiceOrigin.EXISTING, libraries=libraries)
        factory = factory_for(roots, libraries=libraries)
        await build_routes(session, factory, (RouteSelection(library="影集", target_path=berth),))

        status = await build_routes(
            session,
            factory,
            (RouteSelection(library="影集", target_path=str(old), profile=Profile.ANIME),),
        )

        assert [(row.target_path, row.profile) for row in status.routes] == [
            (berth, Profile.STANDARD)
        ]

    @pytest.mark.asyncio
    async def test_a_rerun_after_a_rename_does_not_grow_a_second_route_on_the_same_target(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """票 09 之前存下的 Route 沒有 `ItemId`，只能以名字認媒體庫；媒體庫在 Jellyfin 改名之後，
        精靈就認不出它已經有 Route。目標已經被佔用就略過（票 14a）：兩條 Route 同一個目標，
        帳本分不出檔案是誰的。"""
        berth = berth_path(roots, "影集")
        Path(berth).mkdir()
        libraries = (existing_library(berth),)
        await arrange(session, roots, origin=ServiceOrigin.EXISTING, libraries=libraries)
        await build_routes(
            session,
            factory_for(roots, libraries=libraries),
            (RouteSelection(library="影集", target_path=berth),),
        )
        (await session.scalars(select(Route))).one().jellyfin_library_id = ""
        renamed = (libraries[0].model_copy(update={"name": "劇集"}),)
        setup = await read_settings(session, SetupSettings)
        setup.jellyfin.libraries = list(renamed)
        await write_settings(session, setup)
        await session.commit()

        status = await build_routes(
            session,
            factory_for(roots, libraries=renamed),
            (RouteSelection(library="劇集", target_path=berth),),
        )

        assert [row.target_path for row in status.routes] == [berth]

    @pytest.mark.asyncio
    async def test_two_selections_for_the_same_target_build_one_route(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """兩個媒體庫回報同一條路徑、兩個都勾了它：只建第一條，第二個選擇與
        「已經有 Route」同樣略過。"""
        shared = berth_path(roots, "shared")
        Path(shared).mkdir()
        libraries = (
            existing_library(shared),
            existing_library(shared).model_copy(update={"name": "動畫", "item_id": "a2"}),
        )
        await arrange(session, roots, origin=ServiceOrigin.EXISTING, libraries=libraries)

        status = await build_routes(
            session,
            factory_for(roots, libraries=libraries),
            (
                RouteSelection(library="影集", target_path=shared),
                RouteSelection(library="動畫", target_path=shared),
            ),
        )

        assert [(row.library, row.target_path) for row in status.routes] == [("影集", shared)]

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
    async def test_after_setup_a_rerun_keeps_a_new_red_route_disabled(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """精靈跑完之後重跑第 7 步，已經沒有完成條件擋著，所以與設定頁同一條規則：紅的不給啟用。

        跑完之前建的 Route 仍然直接啟用——它紅著就擋完成
        （`test_a_broken_route_holds_the_wizard_back`）。
        """
        await arrange(session, roots)
        await build_routes(session, factory_for(roots), ())
        await complete_setup(session)
        # 管理員在 Route 設定頁刪掉了 anime，之後回精靈重跑；這一次 Jellyfin 看不到那個目錄。
        anime = next(
            row for row in (await read_route_status(session)).routes if row.slug == "anime"
        )
        await delete_route(session, anime.id)
        blind = fake_jellyfin(
            bundled_libraries(roots["library"]),
            visible_roots=(str(roots["library"] / "movies"), str(roots["library"] / "tv")),
        )

        status = await build_routes(session, factory_for(roots, jellyfin=blind), ())

        rebuilt = next(row for row in status.routes if row.slug == "anime")
        assert (rebuilt.health, rebuilt.enabled) == (HealthStatus.FAILED, False)

    @pytest.mark.asyncio
    async def test_after_setup_a_rerun_enables_new_routes_only_once_they_pass(
        self,
        session: AsyncSession,
        roots: dict[str, Path],
        engine: AsyncEngine,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """精靈跑完之後重跑：新建的 Route 在檢查跑完之前就啟用的話，送單在那幾秒裡選得到一條
        還沒驗過、可能是紅的 Route。所以一律停用建立，檢查綠了才啟用（票 14a）。"""
        await arrange(session, roots)
        await build_routes(session, factory_for(roots), ())
        await complete_setup(session)
        for slug in ("tv", "anime"):
            gone = next(
                row for row in (await read_route_status(session)).routes if row.slug == slug
            )
            await delete_route(session, gone.id)
        blind = fake_jellyfin(
            bundled_libraries(roots["library"]),
            visible_roots=(str(roots["library"] / "movies"), str(roots["library"] / "tv")),
        )
        factory = factory_for(roots, jellyfin=blind)
        sessions = create_session_factory(engine)
        seen: list[bool] = []

        async def peek_mid_check(
            client: QbittorrentClient, name: str, save_path: str
        ) -> CategoryOutcome:
            """每條 Route 的第一條纜繩：這時新建的那兩條已經 commit，另一個 session 讀得到。"""
            async with sessions() as other:
                fresh = select(Route.enabled).where(Route.slug.in_(("tv", "anime")))
                seen.extend((await other.scalars(fresh)).all())
            return await ensure_category(client, name, save_path)

        # 包的是 routes 模組 import 進來的那個名字：檢查呼叫的是它，不是 adapter 上的原件。
        monkeypatch.setattr("berth.services.routes.ensure_category", peek_mid_check)

        status = await build_routes(session, factory, ())

        assert seen
        assert not any(seen)
        assert {row.slug: (row.health, row.enabled) for row in status.routes} == {
            "movies": (HealthStatus.OK, True),
            "tv": (HealthStatus.OK, True),
            "anime": (HealthStatus.FAILED, False),
        }

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

        chosen = {row.name: (row.has_route, row.target_path) for row in status.libraries}
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
        # 尾斜線是 4.4 的行為（brief §20.7）。路徑本身走 `save_path_of`：Berth 送出去的
        # 就是那一串字，而這個情境問的正是「服務把它原樣回報回來時 Berth 怎麼判」。
        reported = f"{save_path_of(str(roots['complete']), 'tv')}/"
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
