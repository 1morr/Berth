"""既有 Jellyfin 的頁 3：勾了才新建的媒體庫、撞名、預設勾選（M4 票 64，審計 E1、C2、P2-15）。

新建的媒體庫是獨立物件，屬於「Berth 擁有的物件」（brief §16.4）；與套件內建媒體庫走同一條路徑
（`_Runner._libraries`），所以同名的不重複建。路徑是 `<library root>/<slug>`，同一個資料夾不給第二個
媒體庫——新建與加 Berth 路徑都是。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceUnavailableError
from berth.adapters.jellyfin import JellyfinLibrary
from berth.domain import (
    BerthPathFailure,
    BundledLibraryRefusal,
    CollectionType,
    JellyfinStep,
    ServiceOrigin,
    StepStatus,
)
from berth.services.jellyfin import (
    BundledLibraryRejectedError,
    LibraryRequest,
    add_berth_paths,
    connect_jellyfin,
    create_libraries,
)
from tests.integration.factories import FakeClientFactory
from tests.integration.test_setup_jellyfin import choices, nas_jellyfin, seed, step

MOVIES = CollectionType.MOVIES
SHOWS = CollectionType.TVSHOWS


async def existing(
    session: AsyncSession, tmp_path: Path, libraries: tuple[JellyfinLibrary, ...] | None = None
) -> tuple[FakeClientFactory, str]:
    """頁 1 選了既有、成為擁有者之後的樣子。回替身的工廠與 library root。"""
    library_root = str(tmp_path / "library")
    await seed(
        session,
        origin=ServiceOrigin.EXISTING,
        base_url="http://nas:8096",
        library_root=library_root,
    )
    jellyfin = nas_jellyfin() if libraries is None else nas_jellyfin(libraries=libraries)
    factory = FakeClientFactory(jellyfin=jellyfin)
    await connect_jellyfin(session, factory, username="owner", password="s3cret")
    return factory, library_root


def shows_only(tmp_path: Path) -> tuple[JellyfinLibrary, ...]:
    """只有劇集媒體庫的那一台（票 64 的情境）。"""
    return (
        JellyfinLibrary(
            name="劇集",
            item_id="s1",
            collection_type="tvshows",
            locations=(str(tmp_path / "volume1" / "tv"),),
            type_options=(),
        ),
    )


@pytest.mark.asyncio
async def test_a_ticked_library_is_created_under_the_library_root(
    session: AsyncSession, tmp_path: Path
) -> None:
    factory, library_root = await existing(session, tmp_path, shows_only(tmp_path))

    status = await create_libraries(session, factory, libraries=[LibraryRequest("電影", MOVIES)])

    [made] = factory.jellyfin_.created
    assert (made.name, made.collection_type, made.path) == ("電影", MOVIES, f"{library_root}/電影")
    # 與套件內同一條：圖片 fetcher 照這台伺服器的可用清單、metadata 照 Jellyfin 自己的設定。
    assert made.type_options
    assert (tmp_path / "library" / "電影").is_dir()
    assert step(status, JellyfinStep.LIBRARIES) is StepStatus.OK
    # 存下的快照立刻有它：頁 3 的清單與建 Route 都讀那一份。
    movies = next(row for row in await choices(session) if row.name == "電影")
    assert movies.locations == (f"{library_root}/電影",)
    assert (movies.has_berth_path, movies.target_path) == (True, f"{library_root}/電影")


@pytest.mark.asyncio
async def test_nothing_is_created_unless_it_is_ticked(
    session: AsyncSession, tmp_path: Path
) -> None:
    """勾了才建：只加 Berth 路徑的那一輪不建任何媒體庫；要求一個就只建那一個。"""
    factory, _ = await existing(session, tmp_path, shows_only(tmp_path))

    await add_berth_paths(session, factory, library_names=["劇集"])
    assert factory.jellyfin_.created == []

    await create_libraries(session, factory, libraries=[LibraryRequest("Movies", MOVIES)])
    assert [row.name for row in factory.jellyfin_.created] == ["Movies"]


@pytest.mark.asyncio
async def test_pressing_again_does_not_build_a_second_library(
    session: AsyncSession, tmp_path: Path
) -> None:
    """同名不重複建：重按（Route 檢查紅了再按）不會長出「電影2」。

    Jellyfin 不拒同名（brief §20.7），所以要 Berth 自己略過。
    """
    factory, _ = await existing(session, tmp_path, shows_only(tmp_path))
    request = [LibraryRequest("電影", MOVIES)]
    await create_libraries(session, factory, libraries=request)

    status = await create_libraries(session, factory, libraries=request)

    assert len(factory.jellyfin_.created) == 1
    assert [row.name for row in factory.jellyfin_.libraries_] == ["劇集", "電影"]
    assert step(status, JellyfinStep.LIBRARIES) is StepStatus.SKIPPED


@pytest.mark.asyncio
async def test_a_name_that_differs_only_in_case_is_refused(
    session: AsyncSession, tmp_path: Path
) -> None:
    """「anime」與那台的「Anime」：Jellyfin 會建出兩個看起來一樣的媒體庫，所以擋下。"""
    factory, _ = await existing(session, tmp_path)

    with pytest.raises(BundledLibraryRejectedError) as refused:
        await create_libraries(session, factory, libraries=[LibraryRequest("anime", SHOWS)])

    assert (refused.value.reason, refused.value.row) == (BundledLibraryRefusal.NAME_TAKEN, 0)
    assert factory.jellyfin_.created == []


@pytest.mark.asyncio
async def test_a_folder_another_library_already_uses_is_refused(
    session: AsyncSession, tmp_path: Path
) -> None:
    """「Movies?」的資料夾是 `…/movies`，那台的「Films」已經在用：兩個媒體庫會掃同一批檔案。"""
    library_root = tmp_path / "library"
    films = JellyfinLibrary(
        name="Films",
        item_id="f1",
        collection_type="movies",
        locations=(f"{library_root}/movies",),
        type_options=(),
    )
    factory, _ = await existing(session, tmp_path, (films,))

    with pytest.raises(BundledLibraryRejectedError) as refused:
        await create_libraries(session, factory, libraries=[LibraryRequest("Movies?", MOVIES)])

    assert refused.value.reason is BundledLibraryRefusal.FOLDER_TAKEN
    assert factory.jellyfin_.created == []


@pytest.mark.asyncio
async def test_a_blank_name_is_refused(session: AsyncSession, tmp_path: Path) -> None:
    factory, _ = await existing(session, tmp_path, shows_only(tmp_path))

    with pytest.raises(BundledLibraryRejectedError) as refused:
        await create_libraries(session, factory, libraries=[LibraryRequest("  ", MOVIES)])

    assert refused.value.reason is BundledLibraryRefusal.NAME_MISSING


@pytest.mark.asyncio
async def test_a_bundled_jellyfin_builds_its_list_instead(
    session: AsyncSession, tmp_path: Path
) -> None:
    """套件內那一台照它的清單建（`bootstrap_jellyfin`），這一支只給既有。"""
    await seed(session, library_root=str(tmp_path / "library"))
    factory = FakeClientFactory()

    with pytest.raises(ValueError, match="bundled"):
        await create_libraries(session, factory, libraries=[LibraryRequest("Movies", MOVIES)])


@pytest.mark.asyncio
async def test_a_jellyfin_that_refuses_is_a_failed_step(
    session: AsyncSession, tmp_path: Path
) -> None:
    factory, _ = await existing(session, tmp_path, shows_only(tmp_path))
    factory.jellyfin_.error = ServiceUnavailableError("connection refused")

    status = await create_libraries(session, factory, libraries=[LibraryRequest("電影", MOVIES)])

    failure = next(row for row in status.steps if row.step == JellyfinStep.LIBRARIES.value)
    assert failure.status is StepStatus.FAILED
    assert "connection refused" in failure.error


# --- 預設勾選（審計 C2）---


@pytest.mark.asyncio
async def test_movies_and_shows_libraries_are_preselected(
    session: AsyncSession, tmp_path: Path
) -> None:
    """類型對得上 Route 用途的預設勾；音樂、混合不勾（也勾不了）。"""
    music = JellyfinLibrary(
        name="Music", item_id="m1", collection_type="music", locations=("/m",), type_options=()
    )
    mixed = JellyfinLibrary(
        name="Home", item_id="h1", collection_type="", locations=("/h",), type_options=()
    )
    shows = shows_only(tmp_path)[0]
    await existing(session, tmp_path, (shows, music, mixed))

    assert {row.name: row.preselected for row in await choices(session)} == {
        "劇集": True,
        "Music": False,
        "Home": False,
    }


# --- 同一個資料夾不給第二個媒體庫：加 Berth 路徑 ---


def twin_shows(library_root: Path, *, one_has_it: bool) -> tuple[JellyfinLibrary, ...]:
    """「TV Shows」與「TV-Shows」：slug 都是 `tv-shows`。"""
    return (
        JellyfinLibrary(
            name="TV Shows",
            item_id="t1",
            collection_type="tvshows",
            locations=("/volume1/tv",),
            type_options=(),
        ),
        JellyfinLibrary(
            name="TV-Shows",
            item_id="t2",
            collection_type="tvshows",
            locations=(
                ("/volume1/tv2", f"{library_root}/tv-shows") if one_has_it else ("/volume1/tv2",)
            ),
            type_options=(),
        ),
    )


@pytest.mark.asyncio
async def test_a_berth_path_another_library_already_has_is_not_added(
    session: AsyncSession, tmp_path: Path
) -> None:
    library_root = tmp_path / "library"
    factory, _ = await existing(session, tmp_path, twin_shows(library_root, one_has_it=True))

    status = await add_berth_paths(session, factory, library_names=["TV Shows"])

    [result] = status.berth_paths
    assert (result.status, result.reason) == (StepStatus.FAILED, BerthPathFailure.PATH_TAKEN)
    assert "TV-Shows" in result.error
    shows = next(row for row in factory.jellyfin_.libraries_ if row.name == "TV Shows")
    assert shows.locations == ("/volume1/tv",)


@pytest.mark.asyncio
async def test_two_libraries_with_the_same_slug_do_not_share_a_berth_path(
    session: AsyncSession, tmp_path: Path
) -> None:
    """同一輪兩個都要加：第一個加上，第二個說被第一個用掉了。"""
    library_root = tmp_path / "library"
    factory, _ = await existing(session, tmp_path, twin_shows(library_root, one_has_it=False))

    status = await add_berth_paths(session, factory, library_names=["TV Shows", "TV-Shows"])

    assert [(row.library, row.status, row.reason) for row in status.berth_paths] == [
        ("TV Shows", StepStatus.OK, None),
        ("TV-Shows", StepStatus.FAILED, BerthPathFailure.PATH_TAKEN),
    ]
    holders = [
        row.name
        for row in factory.jellyfin_.libraries_
        if f"{library_root}/tv-shows" in row.locations
    ]
    assert holders == ["TV Shows"]
