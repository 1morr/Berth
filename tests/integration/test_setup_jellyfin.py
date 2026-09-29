"""精靈第 3 步的 services 命令（plan §9.4、§9.5、票 06）。

驗的是票 06 的驗收條件本身：七步跑完之後 Jellyfin 上真的有那些東西、metadata fetcher 是
設定值、重按不會建第二份、失敗的那一步可以單獨重來、既有路徑不碰舊資料。版本閘門與 403
的重試是票 14b 加的。M4 票 06 起七步分兩半：前六步在第 1 步成立擁有者時跑（`claim_jellyfin`，
擁有者本身在 `test_setup_owner.py`），這裡的 `dock` 把兩半接起來。
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import AuthFailedError, ServiceUnavailableError
from berth.adapters.jellyfin import JellyfinApiKey, JellyfinLibrary, TypeOption
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.domain import (
    BundledLibraryRefusal,
    CollectionType,
    ConnectionReason,
    HealthStatus,
    JellyfinStep,
    QbittorrentStep,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.models import (
    BundledLibrary,
    JellyfinSettings,
    PathSettings,
    Route,
    SetupSettings,
    SetupStep,
)
from berth.services.jellyfin import (
    BundledLibraryRejectedError,
    JellyfinSetupStatus,
    add_berth_path,
    bootstrap_jellyfin,
    claim_jellyfin,
    connect_jellyfin,
    save_bundled_libraries,
)
from berth.services.routes import read_route_status
from berth.services.settings import read_settings, write_settings
from berth.services.setup import STEP_INDEXER, STEP_ROUTES, read_status
from tests.integration.arrange import chosen, own
from tests.integration.factories import FakeClientFactory

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)

#: 低於支援下限的那一台（brief §16.4、§20.9）。10.11.x 是最後一個舊版號系列。
TOO_OLD = "10.11.11"


async def seed(
    session: AsyncSession,
    *,
    origin: ServiceOrigin = ServiceOrigin.BUNDLED,
    base_url: str = "http://jellyfin:8096",
    library_root: str = "/data/library",
    owner: bool = True,
) -> None:
    """把頁 1 的產物放好：擁有者與三個服務的選擇（M4 票 15）。"""
    if owner:
        await own(session)
    setup = await read_settings(session, SetupSettings)
    setup.choices = {
        ServiceKind.JELLYFIN: chosen(
            origin,
            base_url,
            ConnectionReason.SETUP_PENDING
            if origin is ServiceOrigin.BUNDLED
            else ConnectionReason.SETUP_COMPLETED,
            detail="12.1.0",
        ),
        ServiceKind.QBITTORRENT: chosen(ServiceOrigin.BUNDLED, "http://qbittorrent:8080"),
        ServiceKind.PROWLARR: chosen(ServiceOrigin.BUNDLED, "http://prowlarr:9696"),
    }
    await write_settings(session, setup)
    paths = await read_settings(session, PathSettings)
    paths.library_root = library_root
    await write_settings(session, paths)
    await session.commit()


async def dock(session: AsyncSession, factory: FakeClientFactory) -> JellyfinSetupStatus:
    """套件內的整段序列：第 1 步那一半（建管理員、跑完初始設定、換 key），再加泊位 1 建媒體庫。"""
    await claim_jellyfin(session, factory, username="skipper", password="harbour")
    return await bootstrap_jellyfin(session, factory)


def step(status: JellyfinSetupStatus, which: JellyfinStep) -> StepStatus:
    return next(row.status for row in status.steps if row.step == which.value)


def detail(status: JellyfinSetupStatus, which: JellyfinStep) -> str:
    return next(row.detail for row in status.steps if row.step == which.value)


# --- 套件內：plan §9.4 的七步 ---


@pytest.mark.asyncio
async def test_bootstrap_runs_the_whole_sequence(session: AsyncSession, tmp_path: Path) -> None:
    await seed(session, library_root=str(tmp_path / "library"))
    jellyfin = FakeJellyfinClient()
    factory = FakeClientFactory(jellyfin=jellyfin)

    status = await dock(session, factory)

    assert [row.status for row in status.steps] == [StepStatus.OK] * len(JellyfinStep)
    # Jellyfin 上真的有 Berth 管理員與三個媒體庫。
    assert jellyfin.admin == ("skipper", "harbour")
    assert jellyfin.startup_wizard_completed is True
    assert jellyfin.remote_access is True
    assert [(row.name, row.collection_type) for row in jellyfin.libraries_] == [
        ("Movies", "movies"),
        ("TV", "tvshows"),
        ("Anime", "tvshows"),
    ]
    root = tmp_path / "library"
    assert [row.locations[0] for row in jellyfin.libraries_] == [
        f"{root}/movies",
        f"{root}/tv",
        f"{root}/anime",
    ]
    # 目錄由 Berth 先建好，Jellyfin 才看得到（plan §9.1）。
    assert sorted(p.name for p in root.iterdir()) == ["anime", "movies", "tv"]


@pytest.mark.asyncio
async def test_bootstrap_writes_the_library_options_the_plan_asks_for(
    session: AsyncSession, tmp_path: Path
) -> None:
    await seed(session, library_root=str(tmp_path / "library"))
    jellyfin = FakeJellyfinClient()

    await dock(session, FakeClientFactory(jellyfin=jellyfin))

    for created in jellyfin.created:
        assert created.preferred_metadata_language == "zh-TW"
        assert created.metadata_country_code == "TW"
    assert jellyfin.culture == ("zh-TW", "TW", "zh-TW")


@pytest.mark.asyncio
async def test_metadata_fetchers_come_from_settings_not_from_the_code(
    session: AsyncSession, tmp_path: Path
) -> None:
    """brief §10 的 TVDB【研究】定案時要改的是設定，不是程式（票 06 驗收）。"""
    await seed(session, library_root=str(tmp_path / "library"))
    jellyfin_settings = await read_settings(session, JellyfinSettings)
    jellyfin_settings.metadata_fetchers["anime"] = ["TheTVDB", "TheMovieDb"]
    await write_settings(session, jellyfin_settings)
    await session.commit()
    jellyfin = FakeJellyfinClient()

    await dock(session, FakeClientFactory(jellyfin=jellyfin))

    by_name = {created.name: created for created in jellyfin.created}
    assert [option.metadata_fetchers for option in by_name["Anime"].type_options] == [
        ("TheTVDB", "TheMovieDb")
    ] * 3
    assert [option.metadata_fetchers for option in by_name["TV"].type_options] == [
        ("TheMovieDb",)
    ] * 3
    # 圖片 fetcher 不是設定值：跟著伺服器自己的可用清單，寫死會讓沒對到 TMDB 的作品沒縮圖。
    assert by_name["Movies"].type_options[0].image_fetchers == (
        "TheMovieDb",
        "The Open Movie Database",
        "Embedded Image Extractor",
        "Screen Grabber",
    )


@pytest.mark.asyncio
async def test_bootstrap_stores_the_api_key(session: AsyncSession, tmp_path: Path) -> None:
    await seed(session, library_root=str(tmp_path / "library"))
    jellyfin = FakeJellyfinClient()

    status = await dock(session, FakeClientFactory(jellyfin=jellyfin))

    stored = await read_settings(session, JellyfinSettings)
    assert stored.api_key == jellyfin.api_keys_[0].access_token
    assert stored.base_url == "http://jellyfin:8096"
    assert status.api_key_present is True
    assert (status.version, status.version_supported) == ("12.1.0", True)


@pytest.mark.asyncio
async def test_pressing_bootstrap_twice_changes_nothing(
    session: AsyncSession, tmp_path: Path
) -> None:
    """票 06 驗收：重按不會重複建立媒體庫或重複建 API key。"""
    await seed(session, library_root=str(tmp_path / "library"))
    jellyfin = FakeJellyfinClient()
    factory = FakeClientFactory(jellyfin=jellyfin)
    await dock(session, factory)

    status = await bootstrap_jellyfin(session, factory)

    assert len(jellyfin.libraries_) == 3
    assert len(jellyfin.api_keys_) == 1
    # 第一步永遠真的問一次；媒體庫是「已經是想要的樣子」。
    assert step(status, JellyfinStep.PUBLIC_INFO) is StepStatus.OK
    assert step(status, JellyfinStep.LIBRARIES) is StepStatus.SKIPPED


@pytest.mark.asyncio
async def test_the_second_run_still_reaches_the_libraries_after_the_wizard_closed(
    session: AsyncSession, tmp_path: Path
) -> None:
    """初始精靈跑完之後 `/Library/VirtualFolders` 就要憑證，所以第二輪要先登入。"""
    await seed(session, library_root=str(tmp_path / "library"))
    jellyfin = FakeJellyfinClient()
    factory = FakeClientFactory(jellyfin=jellyfin)
    await dock(session, factory)
    jellyfin.use_token("")

    status = await bootstrap_jellyfin(session, factory)

    assert step(status, JellyfinStep.LIBRARIES) is StepStatus.SKIPPED
    assert detail(status, JellyfinStep.LIBRARIES) == "Movies · TV · Anime"


@pytest.mark.asyncio
async def test_the_bundled_paths_match_what_the_berth_path_rule_computes(
    session: AsyncSession, tmp_path: Path
) -> None:
    """套件內建的路徑與既有媒體庫的「Berth 路徑」必須是同一支函式算出來的。

    兩套算法一分岔，`has_berth_path` 就會對 Berth 自己建的媒體庫報 false。
    """
    root = str(tmp_path / "library")
    await seed(session, library_root=root)
    jellyfin = FakeJellyfinClient()

    status = await dock(session, FakeClientFactory(jellyfin=jellyfin))

    assert [row.has_berth_path for row in status.libraries] == [True, True, True]
    assert [row.berth_path for row in status.libraries] == [
        f"{root}/movies",
        f"{root}/tv",
        f"{root}/anime",
    ]


# --- 使用者列的媒體庫（票 06f）---

#: 票 06f 的 playwright 情境：改一個名稱、加一個第四列、刪掉 Anime。
EDITED = [
    BundledLibrary(name="電影", collection_type=CollectionType.MOVIES, folder="films"),
    BundledLibrary(name="TV", collection_type=CollectionType.TVSHOWS, folder="tv"),
    BundledLibrary(name="電視劇（華語）", collection_type=CollectionType.TVSHOWS, folder="tv-zh"),
]


@pytest.mark.asyncio
async def test_bootstrap_builds_the_libraries_on_the_list(
    session: AsyncSession, tmp_path: Path
) -> None:
    """票 06f 驗收：依清單建，名稱、類型、資料夾都照使用者列的，不是照常數。"""
    root = tmp_path / "library"
    await seed(session, library_root=str(root))
    await save_bundled_libraries(session, EDITED)
    jellyfin = FakeJellyfinClient()

    status = await dock(session, FakeClientFactory(jellyfin=jellyfin))

    assert [(row.name, row.collection_type, row.locations) for row in jellyfin.libraries_] == [
        ("電影", "movies", (f"{root}/films",)),
        ("TV", "tvshows", (f"{root}/tv",)),
        ("電視劇（華語）", "tvshows", (f"{root}/tv-zh",)),
    ]
    assert sorted(p.name for p in root.iterdir()) == ["films", "tv", "tv-zh"]
    assert detail(status, JellyfinStep.LIBRARIES) == "電影 · TV · 電視劇（華語）"
    assert [row.built for row in status.bundled] == [True, True, True]


@pytest.mark.asyncio
async def test_new_libraries_get_the_fetchers_of_their_type_unless_their_folder_has_a_row(
    session: AsyncSession, tmp_path: Path
) -> None:
    """`metadata_fetchers` 的鍵是資料夾（媒體庫 slug）；沒寫的依內容類型給預設（票 06f）。"""
    await seed(session, library_root=str(tmp_path / "library"))
    await save_bundled_libraries(session, EDITED)
    settings = await read_settings(session, JellyfinSettings)
    settings.metadata_fetchers = {"tv-zh": ["TheTVDB", "TheMovieDb"]}
    await write_settings(session, settings)
    await session.commit()
    jellyfin = FakeJellyfinClient()

    await dock(session, FakeClientFactory(jellyfin=jellyfin))

    fetchers = {
        created.name: {option.metadata_fetchers for option in created.type_options}
        for created in jellyfin.created
    }
    assert fetchers == {
        "電影": {("TheMovieDb",)},
        "TV": {("TheMovieDb",)},
        "電視劇（華語）": {("TheTVDB", "TheMovieDb")},
    }
    # 類型照列上寫的：`AvailableOptions` 問的是那一種的型別清單。
    assert [created.collection_type for created in jellyfin.created] == [
        CollectionType.MOVIES,
        CollectionType.TVSHOWS,
        CollectionType.TVSHOWS,
    ]


@pytest.mark.asyncio
async def test_a_row_added_after_docking_is_the_only_one_built_on_the_rerun(
    session: AsyncSession, tmp_path: Path
) -> None:
    """冪等（票 06f 驗收）：同名的已經在就標「已經是這樣」，只建清單上新加的那一列。"""
    await seed(session, library_root=str(tmp_path / "library"))
    jellyfin = FakeJellyfinClient()
    factory = FakeClientFactory(jellyfin=jellyfin)
    first = await dock(session, factory)
    documentaries = BundledLibrary(
        name="紀錄片", collection_type=CollectionType.MOVIES, folder="docs"
    )
    await save_bundled_libraries(
        session,
        [
            BundledLibrary(name=row.name, collection_type=row.collection_type, folder=row.folder)
            for row in first.bundled
        ]
        + [documentaries],
    )

    status = await bootstrap_jellyfin(session, factory)

    assert [row.name for row in jellyfin.libraries_] == ["Movies", "TV", "Anime", "紀錄片"]
    assert [created.name for created in jellyfin.created] == ["Movies", "TV", "Anime", "紀錄片"]
    assert step(status, JellyfinStep.LIBRARIES) is StepStatus.OK
    assert detail(status, JellyfinStep.LIBRARIES) == "紀錄片"

    again = await bootstrap_jellyfin(session, factory)

    assert step(again, JellyfinStep.LIBRARIES) is StepStatus.SKIPPED
    assert len(jellyfin.libraries_) == 4


@pytest.mark.asyncio
async def test_a_built_library_is_locked_on_the_list(session: AsyncSession, tmp_path: Path) -> None:
    """建好的那一列改名要去 Jellyfin：同名認得的規則下，這裡改了名重跑就是第二個媒體庫。"""
    await seed(session, library_root=str(tmp_path / "library"))
    await dock(session, FakeClientFactory(jellyfin=FakeJellyfinClient()))

    with pytest.raises(BundledLibraryRejectedError) as caught:
        await save_bundled_libraries(session, EDITED)

    assert caught.value.reason is BundledLibraryRefusal.BUILT_CHANGED
    stored = await read_settings(session, SetupSettings)
    assert [row.name for row in stored.jellyfin.bundled] == ["Movies", "TV", "Anime"]


@pytest.mark.asyncio
async def test_a_library_renamed_in_jellyfin_is_not_built_again(
    session: AsyncSession, tmp_path: Path
) -> None:
    """code review 抓到：照畫面說的去 Jellyfin 改名之後，只比名稱就認不出它。

    改名後重跑會再建一個 `Movies` 指向同一個資料夾——正是鎖住那一列要擋的重複。所以「已經在
    Jellyfin 上」也認路徑：那個資料夾已經是某個媒體庫的路徑，那一列就是建好了。
    """
    root = tmp_path / "library"
    await seed(session, library_root=str(root))
    jellyfin = FakeJellyfinClient()
    factory = FakeClientFactory(jellyfin=jellyfin)
    await dock(session, factory)
    jellyfin.libraries_[0] = replace(jellyfin.libraries_[0], name="Films")

    status = await bootstrap_jellyfin(session, factory)

    assert [row.name for row in jellyfin.libraries_] == ["Films", "TV", "Anime"]
    assert step(status, JellyfinStep.LIBRARIES) is StepStatus.SKIPPED
    # 那一列照樣鎖著：它在 Jellyfin 上，只是換了名字。
    assert [row.built for row in status.bundled] == [True, True, True]


# --- 版本閘門（brief §16.4、§19、§20.9）---


@pytest.mark.asyncio
async def test_a_jellyfin_below_twelve_stops_at_the_first_step(
    session: AsyncSession, tmp_path: Path
) -> None:
    """只支援 Jellyfin 12 以上：低於它就紅燈、不往下做（使用者拍板，brief §19）。"""
    await seed(session, library_root=str(tmp_path / "library"))
    jellyfin = FakeJellyfinClient(version=TOO_OLD)

    claim = await claim_jellyfin(
        session, FakeClientFactory(jellyfin=jellyfin), username="skipper", password="harbour"
    )
    status = claim.status

    failure = next(row for row in status.steps if row.step == JellyfinStep.PUBLIC_INFO.value)
    assert failure.status is StepStatus.FAILED
    # 訊息說得出「它是哪一版」與「要哪一版」，兩者都在畫面上。
    assert failure.detail == TOO_OLD
    assert TOO_OLD in failure.error
    assert "12.0" in failure.error
    assert (status.version, status.version_supported) == (TOO_OLD, False)
    # 一步都沒做：沒有建管理員，也沒有動它的媒體庫。
    assert {row.status for row in status.steps[1:]} == {StepStatus.PENDING}
    assert jellyfin.admin is None
    assert jellyfin.libraries_ == []


@pytest.mark.asyncio
async def test_an_existing_jellyfin_below_twelve_is_refused_too(
    session: AsyncSession, tmp_path: Path
) -> None:
    """既有路徑走同一個閘門：它也是從 `public_info` 開始（plan §9.5）。"""
    await seed(
        session,
        origin=ServiceOrigin.EXISTING,
        base_url="http://nas:8096",
        library_root=str(tmp_path / "library"),
    )
    jellyfin = nas_jellyfin(version=TOO_OLD)

    status = await connect_jellyfin(
        session, FakeClientFactory(jellyfin=jellyfin), username="owner", password="s3cret"
    )

    assert step(status, JellyfinStep.PUBLIC_INFO) is StepStatus.FAILED
    assert status.version_supported is False
    assert status.api_key_present is False
    assert jellyfin.api_keys_ == []


# --- 失敗與重試 ---


@pytest.mark.asyncio
async def test_a_failing_step_stops_the_sequence_and_keeps_what_worked(
    session: AsyncSession, tmp_path: Path
) -> None:
    """媒體庫目錄建不出來（掛載對不上，brief §16.4）是泊位 1 最真實的失敗。"""
    blocked = tmp_path / "library"
    blocked.write_text("not a directory", encoding="utf-8")
    await seed(session, library_root=str(blocked))
    jellyfin = FakeJellyfinClient()
    factory = FakeClientFactory(jellyfin=jellyfin)

    status = await dock(session, factory)

    assert step(status, JellyfinStep.LIBRARIES) is StepStatus.FAILED
    # 第 1 步做過的事都留著：管理員、初始設定、API key。
    assert {row.status for row in status.steps if row.step != JellyfinStep.LIBRARIES.value} == {
        StepStatus.OK
    }
    assert jellyfin.admin == ("skipper", "harbour")
    assert jellyfin.libraries_ == []


@pytest.mark.asyncio
async def test_retrying_after_a_failure_walks_the_rest_of_the_sequence(
    session: AsyncSession, tmp_path: Path
) -> None:
    """媒體庫失敗之後重按，只補建媒體庫。管理員那一步的 403 重試在第 1 步
    （`test_setup_owner.py::test_a_second_claim_on_a_bundled_jellyfin_is_a_sign_in`）。
    """
    blocked = tmp_path / "library"
    blocked.write_text("not a directory", encoding="utf-8")
    await seed(session, library_root=str(blocked))
    jellyfin = FakeJellyfinClient()
    factory = FakeClientFactory(jellyfin=jellyfin)
    await dock(session, factory)
    blocked.unlink()

    status = await bootstrap_jellyfin(session, factory)

    assert [row.status for row in status.steps] != [StepStatus.FAILED]
    assert {row.status for row in status.steps} <= {StepStatus.OK, StepStatus.SKIPPED}
    assert jellyfin.admin == ("skipper", "harbour")
    assert len(jellyfin.libraries_) == 3


@pytest.mark.asyncio
async def test_bootstrap_without_an_owner_says_so(session: AsyncSession, tmp_path: Path) -> None:
    """沒有第 1 步的 API key 就不建媒體庫——即使那台 Jellyfin 還沒跑過初始精靈、匿名也建得了。"""
    await seed(session, library_root=str(tmp_path / "library"), owner=False)
    jellyfin = FakeJellyfinClient()

    status = await bootstrap_jellyfin(session, FakeClientFactory(jellyfin=jellyfin))

    failure = next(row for row in status.steps if row.step == JellyfinStep.LIBRARIES.value)
    assert failure.status is StepStatus.FAILED
    assert "step 1" in failure.error
    assert jellyfin.libraries_ == []


@pytest.mark.asyncio
async def test_a_jellyfin_that_is_not_reachable_fails_on_the_first_step(
    session: AsyncSession, tmp_path: Path
) -> None:
    await seed(session, library_root=str(tmp_path / "library"))
    jellyfin = FakeJellyfinClient(error=ServiceUnavailableError("connection refused"))

    status = await dock(session, FakeClientFactory(jellyfin=jellyfin))

    assert step(status, JellyfinStep.PUBLIC_INFO) is StepStatus.FAILED
    assert {row.status for row in status.steps[1:]} == {StepStatus.PENDING}


# --- 精靈的步數 ---


@pytest.mark.asyncio
async def test_the_libraries_page_waits_for_the_bundled_libraries(
    session: AsyncSession, tmp_path: Path
) -> None:
    """頁 3 的前半是套件內 Jellyfin 的媒體庫（票 06f，M4 票 15 把它從 Jellyfin 頁搬過來）：
    有一條綠的 Route 也不算，清單建完才走得過去。"""
    await seed(session, library_root=str(tmp_path / "library"))
    setup = await read_settings(session, SetupSettings)
    setup.qbittorrent.steps = [
        SetupStep(key=step.value, status=StepStatus.OK) for step in QbittorrentStep
    ]
    await write_settings(session, setup)
    session.add(
        Route(
            slug="tv",
            name="TV",
            jellyfin_library_id="item-tv",
            jellyfin_library_name="TV",
            collection_type=CollectionType.TVSHOWS,
            target_path=f"{tmp_path}/library/tv",
            category="berth-tv",
            health_status=HealthStatus.OK,
        )
    )
    await session.commit()
    assert (await read_status(session)).current_step == STEP_ROUTES

    await dock(session, FakeClientFactory(jellyfin=FakeJellyfinClient()))

    assert (await read_status(session)).current_step == STEP_INDEXER


@pytest.mark.asyncio
async def test_libraries_are_never_created_on_an_existing_jellyfin(
    session: AsyncSession, tmp_path: Path
) -> None:
    """brief §16.4 的紅線：選了既有就不建媒體庫——畫面沒有那顆鍵，直接打 API 也一樣。"""
    await seed(session, origin=ServiceOrigin.EXISTING, library_root=str(tmp_path / "library"))
    jellyfin = FakeJellyfinClient()

    with pytest.raises(ValueError, match="existing service"):
        await dock(session, FakeClientFactory(jellyfin=jellyfin))

    assert jellyfin.created == []


# --- 既有 Jellyfin（plan §9.5）---


def nas_jellyfin(**overrides: object) -> FakeJellyfinClient:
    """一台使用者自己的 Jellyfin：跑過自己的精靈、有兩個媒體庫，其中一個掛了 TVDB。"""
    defaults: dict[str, object] = {
        "base_url": "http://nas:8096",
        "server_name": "nas",
        "version": "12.0.0",
        "startup_wizard_completed": True,
        "admin": ("owner", "s3cret"),
        "libraries": (
            JellyfinLibrary(
                name="電影",
                item_id="a1",
                collection_type="movies",
                locations=("/volume1/media/movies",),
                type_options=(
                    TypeOption(
                        type="Movie",
                        metadata_fetchers=("TheMovieDb",),
                        image_fetchers=("TheMovieDb",),
                    ),
                ),
            ),
            JellyfinLibrary(
                name="Anime",
                item_id="a2",
                collection_type="tvshows",
                locations=("/volume1/media/anime",),
                type_options=(
                    TypeOption(
                        type="Series",
                        metadata_fetchers=("TheTVDB", "TheMovieDb"),
                        image_fetchers=("TheTVDB",),
                    ),
                ),
            ),
        ),
    }
    return FakeJellyfinClient(**{**defaults, **overrides})  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_connecting_to_an_existing_jellyfin_lists_its_libraries(
    session: AsyncSession, tmp_path: Path
) -> None:
    await seed(
        session,
        origin=ServiceOrigin.EXISTING,
        base_url="http://nas:8096",
        library_root=str(tmp_path / "library"),
    )
    jellyfin = nas_jellyfin()

    status = await connect_jellyfin(
        session, FakeClientFactory(jellyfin=jellyfin), username="owner", password="s3cret"
    )

    assert status.origin is ServiceOrigin.EXISTING
    assert status.api_key_present is True
    assert [(row.name, row.locations) for row in status.libraries] == [
        ("電影", ("/volume1/media/movies",)),
        ("Anime", ("/volume1/media/anime",)),
    ]
    # 掛 TVDB 插件的媒體庫要顯示警告（brief §16.4）。
    assert [row.uses_tvdb for row in status.libraries] == [False, True]
    # 絕不自動建立媒體庫。
    assert jellyfin.created == []


@pytest.mark.asyncio
async def test_the_wrong_password_fails_the_api_key_step(
    session: AsyncSession, tmp_path: Path
) -> None:
    await seed(
        session,
        origin=ServiceOrigin.EXISTING,
        base_url="http://nas:8096",
        library_root=str(tmp_path / "library"),
    )

    status = await connect_jellyfin(
        session, FakeClientFactory(jellyfin=nas_jellyfin()), username="owner", password="wrong"
    )

    failure = next(row for row in status.steps if row.step == JellyfinStep.API_KEY.value)
    assert failure.status is StepStatus.FAILED
    assert status.api_key_present is False


@pytest.mark.asyncio
async def test_a_non_administrator_cannot_be_used(session: AsyncSession, tmp_path: Path) -> None:
    await seed(
        session,
        origin=ServiceOrigin.EXISTING,
        base_url="http://nas:8096",
        library_root=str(tmp_path / "library"),
    )
    jellyfin = nas_jellyfin(api_keys=(JellyfinApiKey(app_name="Kodi", access_token="other"),))

    status = await connect_jellyfin(
        session, FakeClientFactory(jellyfin=jellyfin), username="owner", password="s3cret"
    )

    # 名字不是 Berth 的那把不會被拿來用。
    stored = await read_settings(session, JellyfinSettings)
    assert stored.api_key not in {"", "other"}
    assert status.api_key_present is True


@pytest.mark.asyncio
async def test_adding_a_berth_path_leaves_the_old_paths_alone(
    session: AsyncSession, tmp_path: Path
) -> None:
    library_root = str(tmp_path / "library")
    await seed(
        session,
        origin=ServiceOrigin.EXISTING,
        base_url="http://nas:8096",
        library_root=library_root,
    )
    jellyfin = nas_jellyfin()
    factory = FakeClientFactory(jellyfin=jellyfin)
    await connect_jellyfin(session, factory, username="owner", password="s3cret")

    status = await add_berth_path(session, factory, library_name="電影")

    movies = next(row for row in status.libraries if row.name == "電影")
    assert movies.locations == ("/volume1/media/movies", f"{library_root}/電影")
    assert movies.has_berth_path is True
    assert (tmp_path / "library" / "電影").is_dir()


@pytest.mark.asyncio
async def test_a_berth_path_added_under_the_spaced_slug_still_counts(
    session: AsyncSession, tmp_path: Path
) -> None:
    """票 08 之前加的 Berth 路徑帶空白（`…/tv shows`）：它仍是這個媒體庫的 Berth 路徑，
    不再加一條 `…/tv-shows`（已經加上的路徑與 Route、分類一樣不改名）。"""
    library_root = str(tmp_path / "library")
    legacy = f"{library_root}/tv shows"
    Path(legacy).mkdir(parents=True)
    await seed(
        session,
        origin=ServiceOrigin.EXISTING,
        base_url="http://nas:8096",
        library_root=library_root,
    )
    shows = JellyfinLibrary(
        name="TV Shows",
        item_id="a3",
        collection_type="tvshows",
        locations=("/volume1/media/tv", legacy),
        type_options=(),
    )
    factory = FakeClientFactory(jellyfin=nas_jellyfin(libraries=(shows,)))
    await connect_jellyfin(session, factory, username="owner", password="s3cret")

    status = await add_berth_path(session, factory, library_name="TV Shows")

    [view] = status.libraries
    assert view.locations == ("/volume1/media/tv", legacy)
    assert (view.berth_path, view.has_berth_path) == (legacy, True)
    assert not (tmp_path / "library" / "tv-shows").exists()
    [choice] = (await read_route_status(session)).libraries
    assert (choice.berth_path, choice.has_berth_path, choice.target_path) == (legacy, True, legacy)


@pytest.mark.asyncio
async def test_a_new_library_with_spaces_gets_the_hyphenated_berth_path(
    session: AsyncSession, tmp_path: Path
) -> None:
    """反向：還沒有 Berth 路徑的媒體庫照新規則加 `…/tv-shows`。"""
    library_root = str(tmp_path / "library")
    await seed(
        session,
        origin=ServiceOrigin.EXISTING,
        base_url="http://nas:8096",
        library_root=library_root,
    )
    shows = JellyfinLibrary(
        name="TV Shows",
        item_id="a3",
        collection_type="tvshows",
        locations=("/volume1/media/tv",),
        type_options=(),
    )
    factory = FakeClientFactory(jellyfin=nas_jellyfin(libraries=(shows,)))
    await connect_jellyfin(session, factory, username="owner", password="s3cret")

    status = await add_berth_path(session, factory, library_name="TV Shows")

    [view] = status.libraries
    assert view.locations == ("/volume1/media/tv", f"{library_root}/tv-shows")
    assert view.has_berth_path is True


@pytest.mark.asyncio
async def test_adding_the_same_berth_path_twice_does_not_duplicate_it(
    session: AsyncSession, tmp_path: Path
) -> None:
    """同一條路徑送兩次，Jellyfin 會讓 location 出現兩次（實測，brief §20.7）。"""
    await seed(
        session,
        origin=ServiceOrigin.EXISTING,
        base_url="http://nas:8096",
        library_root=str(tmp_path / "library"),
    )
    jellyfin = nas_jellyfin()
    factory = FakeClientFactory(jellyfin=jellyfin)
    await connect_jellyfin(session, factory, username="owner", password="s3cret")
    await add_berth_path(session, factory, library_name="電影")

    status = await add_berth_path(session, factory, library_name="電影")

    movies = next(row for row in status.libraries if row.name == "電影")
    assert len(movies.locations) == 2


@pytest.mark.asyncio
async def test_adding_a_path_that_fails_becomes_a_step_not_an_exception(
    session: AsyncSession, tmp_path: Path
) -> None:
    """失敗要看得到：畫面靠這一條步驟顯示原文與手動步驟（票 06 驗收最後一條）。"""
    await seed(
        session,
        origin=ServiceOrigin.EXISTING,
        base_url="http://nas:8096",
        library_root=str(tmp_path / "library"),
    )
    jellyfin = nas_jellyfin()
    factory = FakeClientFactory(jellyfin=jellyfin)
    await connect_jellyfin(session, factory, username="owner", password="s3cret")

    status = await add_berth_path(session, factory, library_name="Nope")

    assert step(status, JellyfinStep.LIBRARIES) is StepStatus.FAILED
    failure = next(row for row in status.steps if row.step == JellyfinStep.LIBRARIES.value)
    assert "Nope" in failure.error
    # 既有的媒體庫清單沒有被這次失敗清掉。
    assert [row.name for row in status.libraries] == ["電影", "Anime"]


@pytest.mark.asyncio
async def test_a_jellyfin_that_stops_answering_while_adding_a_path_is_a_failed_step(
    session: AsyncSession, tmp_path: Path
) -> None:
    await seed(
        session,
        origin=ServiceOrigin.EXISTING,
        base_url="http://nas:8096",
        library_root=str(tmp_path / "library"),
    )
    jellyfin = nas_jellyfin()
    factory = FakeClientFactory(jellyfin=jellyfin)
    await connect_jellyfin(session, factory, username="owner", password="s3cret")
    jellyfin.error = ServiceUnavailableError("connection refused")

    status = await add_berth_path(session, factory, library_name="電影")

    failure = next(row for row in status.steps if row.step == JellyfinStep.LIBRARIES.value)
    assert failure.status is StepStatus.FAILED
    assert "connection refused" in failure.error


@pytest.mark.asyncio
async def test_an_expired_api_key_surfaces_as_a_failed_step(
    session: AsyncSession, tmp_path: Path
) -> None:
    """既有路徑上「那把 key 不管用了」要看得見原文，不是 500（plan §9.5）。"""
    await seed(
        session,
        origin=ServiceOrigin.EXISTING,
        base_url="http://nas:8096",
        library_root=str(tmp_path / "library"),
    )
    jellyfin = nas_jellyfin()
    factory = FakeClientFactory(jellyfin=jellyfin)
    await connect_jellyfin(session, factory, username="owner", password="s3cret")
    jellyfin.error = AuthFailedError("401")

    status = await add_berth_path(session, factory, library_name="電影")

    failure = next(row for row in status.steps if row.step == JellyfinStep.LIBRARIES.value)
    assert failure.status is StepStatus.FAILED
    assert "401" in failure.error
