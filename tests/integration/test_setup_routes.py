"""精靈頁 3（媒體庫與路徑）與完成頁的 services 命令（plan §9.3、§9.5、brief §4、§16.4、票 09）。

驗的是票 09 的驗收條件：套件內自動建三個 Route、既有由使用者勾選、每個 Route 建 category
並跑每一項檢查、失敗說得出是哪個容器少了哪個掛載、重跑不長出重複列、全綠才寫得下
`settings.setup.completed`。

檔案系統是**真的**：`tmp_path` 底下真的建目錄、真的 `link()`、真的比 inode。硬鏈接檢查的
價值就在這裡，用假的檔案系統測等於什麼都沒測。
"""

from __future__ import annotations

import errno
import os
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from berth.adapters.fs import ensure_directory, is_within
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
    JellyfinStep,
    RouteCheck,
    RouteRefusal,
    ServiceOrigin,
    StepFailure,
    StepStatus,
)
from berth.models import (
    BundledLibrary,
    QbittorrentSettings,
    Route,
    SetupLibrary,
    SetupSettings,
)
from berth.services import routes as routes_module
from berth.services.routes import (
    RouteRejectedError,
    RouteSelection,
    RouteSetupStatus,
    build_routes,
    check_routes,
    delete_route,
    incomplete_path_of,
    read_route_status,
    reread_libraries,
    routes_ready,
    save_path_of,
)
from berth.services.settings import read_settings, write_settings
from berth.services.setup import (
    STEP_COMPLETE,
    STEP_INDEXER,
    STEP_ROUTES,
    complete_setup,
    read_status,
)
from berth.services.steps import StepView
from tests.integration.arrange import (
    BUNDLED,
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

        assert [(row.slug, row.name, row.collection_type) for row in status.routes] == [
            ("movies", "Movies", CollectionType.MOVIES),
            ("tv", "TV", CollectionType.TVSHOWS),
            ("anime", "Anime", CollectionType.TVSHOWS),
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
    async def test_builds_one_route_per_library_the_user_listed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """票 06f 驗收：清單不是預設三列時也是每一個建出來的媒體庫一條 Route。

        Movies 改名成「電影」、多一個「電視劇（華語）」、Anime 刪掉；使用者在 Jellyfin 自己加的
        音樂庫 Berth 寫不了，略過而不是讓整步 422。
        """
        libraries = []
        for index, (name, collection_type, folder) in enumerate(
            [
                ("電影", "movies", "films"),
                ("TV", "tvshows", "tv"),
                ("電視劇（華語）", "tvshows", "tv-zh"),
                ("Music", "music", "music"),
            ]
        ):
            path = roots["library"] / folder
            path.mkdir(parents=True)
            libraries.append(
                SetupLibrary(
                    name=name,
                    item_id=f"item-{index}",
                    collection_type=collection_type,
                    locations=[str(path)],
                )
            )
        await arrange(session, roots, libraries=tuple(libraries))
        await listed(session, [row for row in libraries if row.collection_type != "music"])

        status = await build_routes(session, factory_for(roots, libraries=tuple(libraries)), ())

        assert [(row.name, row.target_path, row.health) for row in status.routes] == [
            ("電影", str(roots["library"] / "films"), HealthStatus.OK),
            ("TV", str(roots["library"] / "tv"), HealthStatus.OK),
            ("電視劇（華語）", str(roots["library"] / "tv-zh"), HealthStatus.OK),
        ]
        assert status.ready is True

    @pytest.mark.asyncio
    async def test_category_and_complete_folder_take_the_folder_the_user_typed(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """套件內的分類與 complete 子目錄照使用者在清單上填的資料夾名（M4 票 31，實測 #44）。

        媒體庫叫「電影」、資料夾填 films，原本分類是 `berth-電影`、下載落在
        `complete/電影`，與媒體庫資料夾對不上。
        """
        path = roots["library"] / "films"
        path.mkdir(parents=True)
        library = SetupLibrary(
            name="電影", item_id="item-0", collection_type="movies", locations=[str(path)]
        )
        await arrange(session, roots, libraries=(library,))
        await listed(session, [library])

        status = await build_routes(session, factory_for(roots, libraries=(library,)), ())

        assert [(row.name, row.slug, row.category) for row in status.routes] == [
            ("電影", "films", "berth-films")
        ]
        assert status.routes[0].save_path == save_path_of(str(roots["complete"]), "films")

    @pytest.mark.asyncio
    async def test_routes_follow_the_order_of_the_users_list(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Route 照使用者清單的順序建（M4 票 31，實測 #46）：Jellyfin 照字母回報媒體庫，原本 Route
        跟著變成 Anime、Movies、TV，與頁 3 清單上的順序對不起來。"""
        libraries = []
        for index, (name, folder) in enumerate(
            [("Movies", "movies"), ("TV", "tv"), ("Anime", "anime")]
        ):
            path = roots["library"] / folder
            path.mkdir(parents=True)
            libraries.append(
                SetupLibrary(
                    name=name,
                    item_id=f"item-{index}",
                    collection_type="movies" if name == "Movies" else "tvshows",
                    locations=[str(path)],
                )
            )
        alphabetical = tuple(sorted(libraries, key=lambda row: row.name))
        await arrange(session, roots, libraries=alphabetical)
        await listed(session, libraries)

        status = await build_routes(session, factory_for(roots, libraries=alphabetical), ())

        assert [row.name for row in status.routes] == ["Movies", "TV", "Anime"]

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
            RouteCheck.DOWNLOAD_VISIBLE.value: StepStatus.OK,
            RouteCheck.LIBRARY_PATH.value: StepStatus.OK,
            RouteCheck.PROBE_VISIBLE.value: StepStatus.OK,
            RouteCheck.HARDLINK.value: StepStatus.OK,
        }

    @pytest.mark.asyncio
    async def test_creates_one_category_per_route_under_the_complete_root(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        qbittorrent = FakeQbittorrentClient()
        await arrange(session, roots)

        await build_routes(session, factory_for(roots, qbittorrent=qbittorrent), ())

        # 送給 qBittorrent 的是 `save_path_of` 算出來的那一串字（容器路徑一律 POSIX），
        # 不是 `Path` 在這台機器上的寫法——票 09 的送單比對的是同一支函式的輸出。每個分類帶自己的
        # 未完成目錄（票 22），Berth 先把它建好。
        complete, incomplete = str(roots["complete"]), str(roots["incomplete"])
        assert [
            (row.name, row.save_path, row.download_path) for row in qbittorrent.created_categories
        ] == [
            (f"berth-{slug}", save_path_of(complete, slug), incomplete_path_of(incomplete, slug))
            for slug in ("movies", "tv", "anime")
        ]
        assert all(Path(row.download_path).is_dir() for row in qbittorrent.created_categories)

    @pytest.mark.asyncio
    async def test_rerunning_neither_duplicates_rows_nor_categories(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """精靈全程可重跑（票 09 驗收）。"""
        qbittorrent = FakeQbittorrentClient()
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


class TestBundledPageThree:
    """M4 票 24：套件內頁 3 的前進條件與 Route 的範圍都照清單與 Jellyfin 現在報的媒體庫算。"""

    @pytest.mark.asyncio
    async def test_a_reinstall_whose_jellyfin_has_every_listed_library_moves_on(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """保留 Jellyfin、只清 Berth 重跑（實測 R-07）：清單全部已建立，前端不呼叫建媒體庫。"""
        await arrange(session, roots)
        setup = await read_settings(session, SetupSettings)
        # 重裝的 Berth 只跑過頁 1：`libraries` 那一步從來沒有結果。
        setup.jellyfin.steps = [
            row for row in setup.jellyfin.steps if row.key != JellyfinStep.LIBRARIES.value
        ]
        setup.indexer.steps = []
        await write_settings(session, setup)

        await build_routes(session, factory_for(roots), ())

        assert (await read_status(session)).current_step == STEP_INDEXER

    @pytest.mark.asyncio
    async def test_a_listed_library_jellyfin_does_not_have_yet_holds_page_three(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """雙向：清單上有 Jellyfin 還沒有的，就算上一次建媒體庫是綠的也要先建它。"""
        await arrange(session, roots)
        await listed(session, [*bundled_libraries(roots["library"]), docs(roots)])

        await build_routes(session, factory_for(roots), ())

        assert (await read_route_status(session)).ready is True
        assert (await read_status(session)).current_step == STEP_ROUTES

    @pytest.mark.asyncio
    async def test_a_library_that_is_not_on_the_list_gets_no_route(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """使用者自己在 Jellyfin 加的、路徑不在 `/data` 的媒體庫不自動建 Route（實測 R-04）。"""
        libraries = (*bundled_libraries(roots["library"]), elsewhere())
        await arrange(session, roots, libraries=libraries)

        status = await build_routes(session, factory_for(roots, libraries=libraries), ())

        assert [row.library for row in status.routes] == ["Movies", "TV", "Anime"]
        assert status.ready is True
        assert [(row.name, row.listed) for row in status.libraries] == [
            ("Movies", True),
            ("TV", True),
            ("Anime", True),
            ("Old", False),
        ]

    @pytest.mark.asyncio
    async def test_a_deleted_red_route_is_not_built_again(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """刪掉那一條紅的之後，下一次「建立並檢查」不讓它長回來（實測 R-05、R-06）。"""
        libraries = (*bundled_libraries(roots["library"]), elsewhere())
        await arrange(session, roots, libraries=libraries)
        # 票 24 之前的精靈替它建了一條，紅在 `library_path`。
        red = Route(
            slug="old",
            name="Old",
            jellyfin_library_id="item-old",
            jellyfin_library_name="Old",
            collection_type=CollectionType.MOVIES,
            target_path="/mnt/old",
            category="berth-old",
            enabled=True,
            health_status=HealthStatus.FAILED,
        )
        session.add(red)
        await session.commit()
        await delete_route(session, red.id)
        await session.commit()

        status = await build_routes(session, factory_for(roots, libraries=libraries), ())

        assert "Old" not in [row.library for row in status.routes]
        assert (await read_status(session)).current_step == STEP_COMPLETE

    @pytest.mark.asyncio
    async def test_a_library_deleted_in_jellyfin_is_gone_after_the_reread(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """套件內進頁也重讀：在 Jellyfin 刪掉的媒體庫不再列入，清單上那一列回到「還沒建」。"""
        await arrange(session, roots)
        await build_routes(session, factory_for(roots), ())
        remaining = tuple(row for row in bundled_libraries(roots["library"]) if row.name != "Anime")

        status = await reread_libraries(session, factory_for(roots, libraries=remaining))

        assert [row.name for row in status.libraries] == ["Movies", "TV"]
        assert (await read_status(session)).current_step == STEP_ROUTES


async def listed(session: AsyncSession, libraries: Sequence[SetupLibrary]) -> None:
    """使用者在頁 3 列的清單：每個媒體庫照它的名字與資料夾各一列。"""
    setup = await read_settings(session, SetupSettings)
    setup.jellyfin.bundled = [
        BundledLibrary(
            name=row.name,
            collection_type=CollectionType(row.collection_type),
            folder=Path(row.locations[0]).name,
        )
        for row in libraries
    ]
    await write_settings(session, setup)
    await session.commit()


def docs(roots: dict[str, Path]) -> SetupLibrary:
    """清單上多出來、Jellyfin 還沒有的一列。"""
    return SetupLibrary(
        name="Docs",
        item_id="item-docs",
        collection_type="movies",
        locations=[str(roots["library"] / "docs")],
    )


def elsewhere() -> SetupLibrary:
    """使用者自己在套件內 Jellyfin 加的媒體庫，路徑不在 Berth 的掛載裡。"""
    return SetupLibrary(
        name="Old", item_id="item-old", collection_type="movies", locations=["/mnt/old"]
    )


class TestExisting:
    @pytest.mark.asyncio
    async def test_the_berth_path_is_the_preselected_target_once_it_is_added(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """票 06h：泊位 1 加了 Berth 路徑之後，泊位 3 反而什麼都沒預選。

        那條路徑正是為 Berth 加的；其餘路徑是使用者自己的。
        """
        old = roots["library"] / "old-tv"
        berth = berth_path(roots, "影集")
        await arrange(
            session, roots, origin=ServiceOrigin.EXISTING, libraries=(existing_library(old, berth),)
        )

        status = await read_route_status(session)

        assert [row.target_path for row in status.libraries] == [berth]

    @pytest.mark.asyncio
    async def test_the_new_berth_path_is_preselected_even_when_the_library_has_one_path(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """票 19：預設是還沒加的 Berth 路徑，不是使用者自己那一條（推翻 brief §4.3「自動選定」）。

        旁邊的說明寫的是「不想讓它寫進你既有的資料夾」，預設選既有的就與它方向相反；要寫進既有的，
        使用者自己選。
        """
        old = roots["library"] / "old-tv"
        await arrange(
            session, roots, origin=ServiceOrigin.EXISTING, libraries=(existing_library(old),)
        )

        status = await read_route_status(session)

        assert [row.target_path for row in status.libraries] == [berth_path(roots, "影集")]

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
            (RouteSelection(library="影集", target_path=berth),),
        )

        assert [(row.library, row.target_path) for row in status.routes] == [("影集", berth)]
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
        """重跑第 5 步**不再隱式刪掉**沒勾的 Route（票 14）：Job 與帳本從票 09 起就引用它。
        刪除是 Route 設定頁上一個明確、要二次確認的動作。"""
        await arrange(session, roots, origin=ServiceOrigin.EXISTING)
        factory = factory_for(roots)
        picked = tuple(
            RouteSelection(library=name, target_path=str(roots["library"] / folder))
            for name, _, folder in BUNDLED
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
            (RouteSelection(library="影集", target_path=str(old)),),
        )

        assert [row.target_path for row in status.routes] == [berth]

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
    async def test_a_library_name_with_spaces_gets_a_hyphenated_slug(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """票 08：空白換成 `-`，分類名與 complete 子目錄不帶空白。"""
        target = roots["library"] / "shows"
        target.mkdir()
        libraries = (existing_library(target).model_copy(update={"name": "TV Shows"}),)
        await arrange(session, roots, origin=ServiceOrigin.EXISTING, libraries=libraries)
        qbittorrent = FakeQbittorrentClient()

        status = await build_routes(
            session,
            factory_for(roots, libraries=libraries, qbittorrent=qbittorrent),
            (RouteSelection(library="TV Shows", target_path=str(target)),),
        )

        [route] = status.routes
        assert (route.slug, route.category) == ("tv-shows", "berth-tv-shows")
        assert route.save_path.endswith("/tv-shows")
        assert [row.name for row in qbittorrent.created_categories] == ["berth-tv-shows"]

    @pytest.mark.asyncio
    async def test_a_route_built_with_a_spaced_slug_keeps_it_on_a_rerun(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """票 08：已經存在的 Route 與分類不改名——改分類的 save path 會搬走它底下的 torrent
        （brief §20.2）。重跑照存下來的 slug 與分類檢查，不另建一個 `berth-tv-shows`。"""
        target = roots["library"] / "shows"
        target.mkdir()
        libraries = (existing_library(target).model_copy(update={"name": "TV Shows"}),)
        await arrange(session, roots, origin=ServiceOrigin.EXISTING, libraries=libraries)
        selection = (RouteSelection(library="TV Shows", target_path=str(target)),)
        await build_routes(session, factory_for(roots, libraries=libraries), selection)
        route = (await session.scalars(select(Route))).one()
        route.slug, route.category = "tv shows", "berth-tv shows"
        await session.commit()
        qbittorrent = FakeQbittorrentClient()

        status = await build_routes(
            session, factory_for(roots, libraries=libraries, qbittorrent=qbittorrent), selection
        )

        [kept] = status.routes
        assert (kept.slug, kept.category) == ("tv shows", "berth-tv shows")
        assert kept.save_path.endswith("/tv shows")
        assert [row.name for row in qbittorrent.created_categories] == ["berth-tv shows"]

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
        """寫入目標只能從 Jellyfin 回報的路徑裡**選**，不能自己打（brief §4.1）。

        拒絕帶理由（M4 票 31）：原本是裸的 `ValueError` → 422，畫面一律說「畫面過時了，重新整理」。
        """
        await arrange(session, roots, origin=ServiceOrigin.EXISTING)

        with pytest.raises(RouteRejectedError) as refused:
            await build_routes(
                session,
                factory_for(roots),
                (RouteSelection(library="TV", target_path=str(roots["library"] / "elsewhere")),),
            )
        assert refused.value.reason is RouteRefusal.TARGET_NOT_IN_LIBRARY

    @pytest.mark.asyncio
    async def test_refuses_a_library_this_jellyfin_does_not_have(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots, origin=ServiceOrigin.EXISTING)

        with pytest.raises(RouteRejectedError) as refused:
            await build_routes(
                session,
                factory_for(roots),
                (RouteSelection(library="Ghost", target_path=str(roots["library"] / "ghost")),),
            )
        assert refused.value.reason is RouteRefusal.LIBRARY_MISSING

    @pytest.mark.asyncio
    async def test_a_listed_library_jellyfin_reports_without_a_folder_says_so(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """套件內清單上的媒體庫在 Jellyfin 上沒有任何資料夾（M4 票 31，實測 #50）：重新整理不會好，
        所以不是「畫面過時」——說出是哪一個媒體庫少了資料夾。"""
        library = SetupLibrary(
            name="Movies", item_id="item-0", collection_type="movies", locations=[]
        )
        await arrange(session, roots, libraries=(library,))
        await listed(
            session,
            [
                SetupLibrary(
                    name="Movies",
                    item_id="item-0",
                    collection_type="movies",
                    locations=[str(roots["library"] / "movies")],
                )
            ],
        )

        with pytest.raises(RouteRejectedError) as refused:
            await build_routes(session, factory_for(roots, libraries=(library,)), ())
        assert refused.value.reason is RouteRefusal.LIBRARY_WITHOUT_PATH
        assert "Movies" in refused.value.detail


class TestChecks:
    @pytest.mark.asyncio
    async def test_a_category_pointing_somewhere_else_is_a_conflict(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """已存在但 save path 不同：回報衝突且**不覆寫**（票 09 驗收）。"""
        qbittorrent = FakeQbittorrentClient(
            categories=(QbittorrentCategory(name="berth-tv", save_path="/mnt/old/tv"),)
        )
        await arrange(session, roots)

        status = await build_routes(session, factory_for(roots, qbittorrent=qbittorrent), ())

        category = checks(status, "tv")[RouteCheck.CATEGORY.value]
        assert category.status is StepStatus.FAILED
        assert "/mnt/old/tv" in category.error
        # 畫面照代碼說人話，路徑是參數（M4 票 21）。
        assert category.failure is StepFailure.CATEGORY_CONFLICT
        assert category.params["path"] == "/mnt/old/tv"
        # 其他兩個 Route 的 category 照建；不覆寫的只有撞上的那一個。
        assert [row.name for row in qbittorrent.created_categories] == [
            "berth-movies",
            "berth-anime",
        ]
        assert next(row for row in status.routes if row.slug == "tv").health is HealthStatus.FAILED

    @pytest.mark.asyncio
    async def test_a_category_downloading_somewhere_else_is_a_conflict(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """save path 一樣、未完成目錄不同：同一條衝突規則，不覆寫（票 22）。"""
        tv = QbittorrentCategory(
            name="berth-tv",
            save_path=save_path_of(str(roots["complete"]), "tv"),
            download_path="/mnt/temp/tv",
        )
        qbittorrent = FakeQbittorrentClient(categories=(tv,))
        await arrange(session, roots)

        status = await build_routes(session, factory_for(roots, qbittorrent=qbittorrent), ())

        category = checks(status, "tv")[RouteCheck.CATEGORY.value]
        assert category.status is StepStatus.FAILED
        assert "/mnt/temp/tv" in category.error
        assert category.failure is StepFailure.CATEGORY_CONFLICT
        # 兩邊並排；路徑以 repr 印（Windows 上的暫存路徑有反斜線）。
        assert repr(incomplete_path_of(str(roots["incomplete"]), "tv")) in category.error
        assert await qbittorrent.categories() == (tv, *qbittorrent.created_categories)

    @pytest.mark.asyncio
    async def test_a_category_from_before_ticket_22_is_kept_and_says_so(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """票 22 之前建的 Berth 分類沒有自己的未完成目錄：不紅、不改，那一行說出下載跟著全域
        設定。"""
        tv = QbittorrentCategory(
            name="berth-tv", save_path=save_path_of(str(roots["complete"]), "tv")
        )
        qbittorrent = FakeQbittorrentClient(categories=(tv,))
        await arrange(session, roots)

        status = await build_routes(session, factory_for(roots, qbittorrent=qbittorrent), ())

        category = checks(status, "tv")[RouteCheck.CATEGORY.value]
        assert category.status is StepStatus.SKIPPED
        assert "no download path of its own" in category.detail
        assert next(row for row in status.routes if row.slug == "tv").health is HealthStatus.OK
        assert (await qbittorrent.categories())[0] == tv

    @pytest.mark.asyncio
    async def test_a_global_save_path_berth_cannot_see_does_not_matter(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """票 32（審計 S5 的 repro）：使用者把套件內那一台的全域 `save_path` 改成一個不存在的目錄。
        Berth 送單逐個 torrent 帶分類與 `autoTMM=true`，不落在那裡，所以三條 Route 照舊是綠的。"""
        await arrange(session, roots)
        qbittorrent = FakeQbittorrentClient(preferences={"save_path": "/data/my-downloads"})

        status = await build_routes(session, factory_for(roots, qbittorrent=qbittorrent), ())

        assert [row.health for row in status.routes] == [HealthStatus.OK] * 3
        row = checks(status, "tv")[RouteCheck.DOWNLOAD_PATH.value]
        assert "/data/my-downloads" not in row.detail
        assert save_path_of(str(roots["complete"]), "tv") in row.detail

    @pytest.mark.parametrize("side", ["complete", "incomplete"])
    @pytest.mark.asyncio
    async def test_a_category_path_berth_cannot_see_fails_check_one(
        self,
        session: AsyncSession,
        roots: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
        side: str,
    ) -> None:
        """另一面：分類自己的路徑（complete 與 incomplete）看不到才紅，錯誤說的就是那一條。

        Berth 每一輪先建分類的兩個目錄，所以造「看不到」要讓那一步建不出來（目錄在檢查之間被刪）。
        """
        await arrange(session, roots)
        build = ensure_directory
        monkeypatch.setattr(
            routes_module,
            "ensure_directory",
            lambda path: False if is_within(path, roots[side]) else build(path),
        )

        status = await build_routes(session, factory_for(roots), ())

        missing = (save_path_of if side == "complete" else incomplete_path_of)(
            str(roots[side]), "tv"
        )
        row = checks(status, "tv")[RouteCheck.DOWNLOAD_PATH.value]
        assert row.status is StepStatus.FAILED
        assert (row.failure, row.params) == (StepFailure.DIRECTORY_MISSING, {"path": missing})

    @pytest.mark.asyncio
    async def test_a_qbittorrent_that_cannot_see_the_category_path_fails_the_route(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """票 19：分類路徑 Berth 看得到（那是它自己建的），qBittorrent 那一台卻只掛了 `/downloads`。

        它讀不到 Berth 寫進分類路徑的探測檔：紅在這一條、理由指名 qBittorrent 與那條路徑，後面不跑。
        """
        await arrange(session, roots)
        qbittorrent = FakeQbittorrentClient(visible_roots=("/downloads",))

        status = await build_routes(session, factory_for(roots, qbittorrent=qbittorrent), ())

        tv = checks(status, "tv")
        assert tv[RouteCheck.DOWNLOAD_PATH.value].status is StepStatus.OK
        row = tv[RouteCheck.DOWNLOAD_VISIBLE.value]
        assert row.status is StepStatus.FAILED
        assert "qBittorrent" in row.error
        assert row.failure is StepFailure.PROBE_UNSEEN
        assert save_path_of(str(roots["complete"]), "tv") in row.error
        assert tv[RouteCheck.LIBRARY_PATH.value].status is StepStatus.PENDING
        assert next(route for route in status.routes if route.slug == "tv").health is (
            HealthStatus.FAILED
        )

    @pytest.mark.asyncio
    async def test_a_qbittorrent_that_reads_the_probe_passes_and_nothing_is_left_behind(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """看得到的那一面：探針校驗完整就綠；探針 torrent 移除時不刪檔，探測檔由 Berth 自己刪。"""
        await arrange(session, roots)
        qbittorrent = FakeQbittorrentClient()

        status = await build_routes(session, factory_for(roots, qbittorrent=qbittorrent), ())

        row = checks(status, "tv")[RouteCheck.DOWNLOAD_VISIBLE.value]
        assert row.status is StepStatus.OK
        assert row.detail == save_path_of(str(roots["complete"]), "tv")
        assert len(qbittorrent.probed) == 3
        assert qbittorrent.open_probes == {}
        assert list(roots["complete"].rglob(".berth-probe-*")) == []

    @pytest.mark.asyncio
    async def test_a_library_path_berth_cannot_see_fails_the_route(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """檢查二：Jellyfin 報的媒體庫路徑在 Berth 內 `stat` 不到——它在 Berth 的共用根目錄外面（它
        自己掛的 `/media/tv`）。**上一層存在也一樣是沒掛**（M4 票 25 code-review）：image 本來就有
        `/media`、`/mnt` 這種空目錄，看「上面幾層在不在」會把它說成目錄被刪。"""
        media = roots["library"].parents[1] / "media"  # 與共用根 `data` 並排，而且存在
        media.mkdir()
        missing = media / "tv"
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
        assert (row.failure, row.params) == (StepFailure.PATH_NOT_VISIBLE, {"path": str(missing)})

    @pytest.mark.asyncio
    async def test_a_deleted_write_target_is_a_missing_directory_not_a_mount(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """寫入目標被刪掉：它上面的媒體庫根目錄還在，掛載是好的（M4 票 25，實測 E12）。原本與少了
        掛載同一個代碼，畫面因此說「不在 /data 底下」，照做修不好。"""
        deleted = roots["library"] / "tv"
        libraries = (existing_library(deleted),)
        await arrange(session, roots, origin=ServiceOrigin.EXISTING, libraries=libraries)

        status = await build_routes(
            session,
            factory_for(roots, libraries=libraries),
            (RouteSelection(library="影集", target_path=str(deleted)),),
        )

        row = checks(status, status.routes[0].slug)[RouteCheck.LIBRARY_PATH.value]
        assert (row.failure, row.params) == (StepFailure.DIRECTORY_MISSING, {"path": str(deleted)})

    @pytest.mark.asyncio
    async def test_only_the_write_target_has_to_be_visible_to_berth(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """票 19：舊路徑不動、加一條 Berth 路徑（brief §16.4）時，舊的 `/movies` 看不到也是綠的。

        Berth 只在寫入目標底下讀寫檔案；舊路徑的作品經 Jellyfin 的 API 讀（`services/inventory.py`、
        `services/reconcile.py` 都只走 Route 的目標）。
        """
        berth = berth_path(roots, "影集")
        Path(berth).mkdir()
        libraries = (existing_library("/movies", berth),)
        await arrange(session, roots, origin=ServiceOrigin.EXISTING, libraries=libraries)

        status = await build_routes(
            session,
            factory_for(roots, libraries=libraries),
            (RouteSelection(library="影集", target_path=berth),),
        )

        row = checks(status, status.routes[0].slug)[RouteCheck.LIBRARY_PATH.value]
        assert row.status is StepStatus.OK
        assert row.detail == berth
        assert status.routes[0].health is HealthStatus.OK

    @pytest.mark.asyncio
    async def test_a_target_jellyfin_no_longer_lists_fails_check_library_path(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """只驗寫入目標，但它仍要是媒體庫現在報的路徑之一：使用者在 Jellyfin 拿掉它之後就紅。"""
        berth = berth_path(roots, "影集")
        Path(berth).mkdir()
        libraries = (existing_library(berth),)
        await arrange(session, roots, origin=ServiceOrigin.EXISTING, libraries=libraries)
        factory = factory_for(roots, libraries=libraries)
        await build_routes(session, factory, (RouteSelection(library="影集", target_path=berth),))

        moved = factory_for(roots, libraries=(existing_library(roots["library"] / "tv"),))
        routes = await check_routes(session, moved)

        row = next(step for step in routes[0].checks if step.step == RouteCheck.LIBRARY_PATH.value)
        assert row.status is StepStatus.FAILED
        assert berth in row.error
        assert (row.failure, row.params) == (
            StepFailure.LIBRARY_PATH_GONE,
            {"library": "影集", "path": berth},
        )

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
        assert row.failure is StepFailure.JELLYFIN_CANNOT_SEE

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
        qbittorrent = FakeQbittorrentClient(error=ServiceUnavailableError("connection refused"))

        status = await build_routes(session, factory_for(roots, qbittorrent=qbittorrent), ())

        assert [row.health for row in status.routes] == [HealthStatus.FAILED] * 3
        category = checks(status, "tv")[RouteCheck.CATEGORY.value]
        assert "connection refused" in category.error
        assert category.failure is StepFailure.UNREACHABLE

    @pytest.mark.asyncio
    async def test_wrong_qbittorrent_credentials_land_on_the_category_line(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """既有 qBittorrent 的帳密不對是**那一條纜繩**的紅燈，不是整頁 500；而且說的是登入那一次
        （M4 票 21）：原本登入的失敗被吞掉，紅燈是建分類時的 403，補法給成「分類衝突」。"""
        await arrange(session, roots)
        await write_settings(
            session,
            QbittorrentSettings(base_url="http://nas:8080", username="admin", password="wrong"),
        )
        await session.commit()
        qbittorrent = FakeQbittorrentClient(
            login_error=AuthFailedError("auth/login: rejected"),
            error=AuthFailedError("GET /api/v2/torrents/categories: 403"),
        )

        status = await build_routes(session, factory_for(roots, qbittorrent=qbittorrent), ())

        assert [row.health for row in status.routes] == [HealthStatus.FAILED] * 3
        category = checks(status, "tv")[RouteCheck.CATEGORY.value]
        assert (category.failure, category.error) == (
            StepFailure.AUTH_REJECTED,
            "auth/login: rejected",
        )

    @pytest.mark.asyncio
    async def test_a_failed_check_leaves_the_rest_pending(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """一條纜繩斷了就停在那裡：後面的檢查測的會是錯的路徑。"""
        await arrange(session, roots)
        qbittorrent = FakeQbittorrentClient(
            visible_roots=("/downloads",)
        )  # 分類路徑沒掛進 qBittorrent

        status = await build_routes(session, factory_for(roots, qbittorrent=qbittorrent), ())

        assert checks(status, "tv")[RouteCheck.DOWNLOAD_VISIBLE.value].status is StepStatus.FAILED
        assert checks(status, "tv")[RouteCheck.LIBRARY_PATH.value].status is StepStatus.PENDING
        assert checks(status, "tv")[RouteCheck.HARDLINK.value].status is StepStatus.PENDING


class TestCompletion:
    @pytest.mark.asyncio
    async def test_the_wizard_stays_on_step_five_until_a_route_is_green(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(session, roots, origin=ServiceOrigin.EXISTING)

        assert (await read_status(session)).current_step == STEP_ROUTES
        assert await routes_ready(session) is False

    @pytest.mark.asyncio
    async def test_routes_come_right_after_qbittorrent(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        """Route 只依賴 Jellyfin 與 qBittorrent，所以排在索引站與 TMDB 之前（票 06d）：
        掛載設錯的人在頁 3 就知道，不必先去申請一把 TMDB key。"""
        await arrange(session, roots)
        setup = await read_settings(session, SetupSettings)
        setup.indexer.steps = []
        setup.tmdb.steps = []
        await write_settings(session, setup)

        assert (await read_status(session)).current_step == STEP_ROUTES == 3

        await build_routes(session, factory_for(roots), ())

        assert (await read_status(session)).current_step == STEP_INDEXER == 4

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
        """精靈跑完之後重跑第 5 步，已經沒有完成條件擋著，所以與設定頁同一條規則：紅的不給啟用。

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
            client: QbittorrentClient, name: str, save_path: str, download_path: str
        ) -> CategoryOutcome:
            """每條 Route 的第一條纜繩：這時新建的那兩條已經 commit，另一個 session 讀得到。"""
            async with sessions() as other:
                fresh = select(Route.enabled).where(Route.slug.in_(("tv", "anime")))
                seen.extend((await other.scalars(fresh)).all())
            return await ensure_category(client, name, save_path, download_path)

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
        """第 5 步不可跳（plan §9.3）。"""
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


class TestReread:
    """票 19：頁 3 進頁時重讀 Jellyfin，不再只靠頁 1 的快照。"""

    @pytest.mark.asyncio
    async def test_a_path_changed_in_jellyfin_after_page_one_shows_up(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        await arrange(
            session,
            roots,
            origin=ServiceOrigin.EXISTING,
            libraries=(existing_library("/movies"),),
        )
        moved = (existing_library("/data/media/tv"),)

        status = await reread_libraries(session, factory_for(roots, libraries=moved))

        assert [row.locations for row in status.libraries] == [("/data/media/tv",)]
        assert [row.locations for row in (await read_route_status(session)).libraries] == [
            ("/data/media/tv",)
        ]

    @pytest.mark.asyncio
    async def test_a_jellyfin_that_does_not_answer_keeps_the_snapshot(
        self, session: AsyncSession, roots: dict[str, Path]
    ) -> None:
        libraries = (existing_library("/movies"),)
        await arrange(session, roots, origin=ServiceOrigin.EXISTING, libraries=libraries)
        down = fake_jellyfin(libraries, error=ServiceUnavailableError("connection refused"))

        with pytest.raises(RouteRejectedError) as refused:
            await reread_libraries(session, factory_for(roots, jellyfin=down))

        assert refused.value.reason is RouteRefusal.JELLYFIN_UNREACHABLE
        assert [row.locations for row in (await read_route_status(session)).libraries] == [
            ("/movies",)
        ]


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
        qbittorrent = FakeQbittorrentClient(
            categories=(QbittorrentCategory(name="berth-tv", save_path=reported),)
        )

        status = await build_routes(session, factory_for(roots, qbittorrent=qbittorrent), ())

        # 尾斜線不算衝突，所以 category 那一條是綠的；但那條路徑本身不存在。
        assert checks(status, "tv")[RouteCheck.CATEGORY.value].status is StepStatus.SKIPPED
        download = checks(status, "tv")[RouteCheck.DOWNLOAD_PATH.value]
        assert download.status is StepStatus.OK
        assert reported.rstrip("/") in download.detail

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
        assert (row.failure, row.params) == (StepFailure.LIBRARY_GONE, {"library": "TV"})
        assert next(row for row in status.routes if row.slug == "movies").health is HealthStatus.OK
