"""精靈第 3 步的 services 命令（plan §9.4、§9.5、票 06）。

驗的是票 06 的驗收條件本身：七步跑完之後 Jellyfin 上真的有那些東西、metadata fetcher 是
設定值、重按不會建第二份、失敗的那一步可以單獨重來、既有路徑不碰舊資料。版本閘門與 403
的重試是票 14b 加的。
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
    DetectionReason,
    JellyfinStep,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.models import (
    BundledLibrary,
    JellyfinSettings,
    PathSettings,
    ServiceProbe,
    SetupSettings,
)
from berth.services.jellyfin import (
    BundledLibraryRejectedError,
    JellyfinSetupStatus,
    add_berth_path,
    bootstrap_jellyfin,
    connect_jellyfin,
    save_bundled_libraries,
)
from berth.services.settings import read_settings, write_settings
from berth.services.setup import STEP_QBITTORRENT, create_admin, read_status
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
    admin: tuple[str, str] | None = ("skipper", "harbour"),
) -> None:
    """把第 1–2 步的產物放好：管理員與 Jellyfin 的判定。"""
    if admin is not None:
        await create_admin(session, username=admin[0], password=admin[1], apply_to_services=True)
    setup = await read_settings(session, SetupSettings)
    setup.services = {
        ServiceKind.JELLYFIN: ServiceProbe(
            origin=origin,
            reason=(
                DetectionReason.SETUP_PENDING
                if origin is ServiceOrigin.BUNDLED
                else DetectionReason.SETUP_COMPLETED
            ),
            detail="12.1.0",
            base_url=base_url,
            checked_at=NOW,
        ),
        # 另外兩個服務也要有結論，否則精靈還在第 2 步（plan §9.3）。
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
    paths = await read_settings(session, PathSettings)
    paths.library_root = library_root
    await write_settings(session, paths)
    await session.commit()


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

    status = await bootstrap_jellyfin(session, factory)

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

    await bootstrap_jellyfin(session, FakeClientFactory(jellyfin=jellyfin))

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

    await bootstrap_jellyfin(session, FakeClientFactory(jellyfin=jellyfin))

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

    status = await bootstrap_jellyfin(session, FakeClientFactory(jellyfin=jellyfin))

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
    await bootstrap_jellyfin(session, factory)

    status = await bootstrap_jellyfin(session, factory)

    assert len(jellyfin.libraries_) == 3
    assert len(jellyfin.api_keys_) == 1
    # 第一步永遠真的問一次；其餘的都是「已經是想要的樣子」。
    assert step(status, JellyfinStep.PUBLIC_INFO) is StepStatus.OK
    assert {row.status for row in status.steps[1:]} == {StepStatus.SKIPPED}


@pytest.mark.asyncio
async def test_the_second_run_still_reaches_the_libraries_after_the_wizard_closed(
    session: AsyncSession, tmp_path: Path
) -> None:
    """初始精靈跑完之後 `/Library/VirtualFolders` 就要憑證，所以第二輪要先登入。"""
    await seed(session, library_root=str(tmp_path / "library"))
    jellyfin = FakeJellyfinClient()
    factory = FakeClientFactory(jellyfin=jellyfin)
    await bootstrap_jellyfin(session, factory)
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

    status = await bootstrap_jellyfin(session, FakeClientFactory(jellyfin=jellyfin))

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

    status = await bootstrap_jellyfin(session, FakeClientFactory(jellyfin=jellyfin))

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

    await bootstrap_jellyfin(session, FakeClientFactory(jellyfin=jellyfin))

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
    first = await bootstrap_jellyfin(session, factory)
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
    await bootstrap_jellyfin(session, FakeClientFactory(jellyfin=FakeJellyfinClient()))

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
    await bootstrap_jellyfin(session, factory)
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

    status = await bootstrap_jellyfin(session, FakeClientFactory(jellyfin=jellyfin))

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
    """媒體庫目錄建不出來（掛載對不上，brief §16.4）是第 4 步最真實的失敗。"""
    blocked = tmp_path / "library"
    blocked.write_text("not a directory", encoding="utf-8")
    await seed(session, library_root=str(blocked))
    jellyfin = FakeJellyfinClient()
    factory = FakeClientFactory(jellyfin=jellyfin)

    status = await bootstrap_jellyfin(session, factory)

    assert step(status, JellyfinStep.LIBRARIES) is StepStatus.FAILED
    assert step(status, JellyfinStep.COMPLETE) is StepStatus.PENDING
    # 前三步做過的事都留著，重按時才跳得過去。
    assert {row.status for row in status.steps[:3]} == {StepStatus.OK}
    assert jellyfin.admin == ("skipper", "harbour")
    assert jellyfin.startup_wizard_completed is False


@pytest.mark.asyncio
async def test_retrying_after_a_failure_walks_the_rest_of_the_sequence(
    session: AsyncSession, tmp_path: Path
) -> None:
    """票 06 的「可重試」在 12.x 只有這一條路走得通（brief §20.9、票 14b）。

    第 3 步已經替 Jellyfin 建好了管理員，而 12.0 起第一個使用者有密碼之後
    `POST /Startup/User` 回 **403**。把它當成失敗的話，第 4 步失敗之後的重試會永遠卡在第 3 步。
    """
    blocked = tmp_path / "library"
    blocked.write_text("not a directory", encoding="utf-8")
    await seed(session, library_root=str(blocked))
    jellyfin = FakeJellyfinClient()
    factory = FakeClientFactory(jellyfin=jellyfin)
    await bootstrap_jellyfin(session, factory)
    blocked.unlink()

    status = await bootstrap_jellyfin(session, factory)

    assert [row.status for row in status.steps] != [StepStatus.FAILED]
    assert {row.status for row in status.steps} <= {StepStatus.OK, StepStatus.SKIPPED}
    # 密碼沒有被改掉——403 是「已經設過了」，不是「再設一次」。
    assert jellyfin.admin == ("skipper", "harbour")
    assert step(status, JellyfinStep.ADMIN_USER) is StepStatus.SKIPPED
    assert len(jellyfin.libraries_) == 3


@pytest.mark.asyncio
async def test_changing_step_one_after_jellyfin_took_the_account_keeps_step_three_working(
    session: AsyncSession, tmp_path: Path
) -> None:
    """管理員建好之後那組帳號屬於 Jellyfin（票 06c，Seerr 的慣例）。

    Berth 寫不進 Jellyfin 的密碼（初始精靈跑過之後 `_admin_user` 一律略過），所以第 1 步再改
    帳密只能改 qBittorrent 與 Prowlarr 那一組；否則重跑第 3 步會拿新密碼去登入而被 401。
    **序列要停在拿到 API key 之前**才測得出來：有了 key，`_authenticate` 用它而不用密碼。
    同一組錯的帳密之後也擋在「用 Jellyfin 帳號登入 Berth」那一關，那一關沒有 key 可以墊。
    """
    blocked = tmp_path / "library"
    blocked.write_text("not a directory", encoding="utf-8")
    await seed(session, library_root=str(blocked))
    jellyfin = FakeJellyfinClient()
    factory = FakeClientFactory(jellyfin=jellyfin)
    await bootstrap_jellyfin(session, factory)
    await create_admin(session, username="deckhand", password="changed", apply_to_services=True)
    await session.commit()
    blocked.unlink()

    status = await bootstrap_jellyfin(session, factory)

    assert {row.status for row in status.steps} <= {StepStatus.OK, StepStatus.SKIPPED}
    assert jellyfin.admin == ("skipper", "harbour")
    admin = (await read_settings(session, SetupSettings)).admin
    assert (admin.username, admin.password) == ("skipper", "harbour")
    assert (admin.interface_username, admin.interface_password) == ("deckhand", "changed")


@pytest.mark.asyncio
async def test_bootstrap_without_an_administrator_says_so(
    session: AsyncSession, tmp_path: Path
) -> None:
    await seed(session, library_root=str(tmp_path / "library"), admin=None)
    jellyfin = FakeJellyfinClient()

    status = await bootstrap_jellyfin(session, FakeClientFactory(jellyfin=jellyfin))

    failure = next(row for row in status.steps if row.step == JellyfinStep.ADMIN_USER.value)
    assert failure.status is StepStatus.FAILED
    assert "step 1" in failure.error
    assert jellyfin.admin is None


@pytest.mark.asyncio
async def test_a_jellyfin_that_is_not_reachable_fails_on_the_first_step(
    session: AsyncSession, tmp_path: Path
) -> None:
    await seed(session, library_root=str(tmp_path / "library"))
    jellyfin = FakeJellyfinClient(error=ServiceUnavailableError("connection refused"))

    status = await bootstrap_jellyfin(session, FakeClientFactory(jellyfin=jellyfin))

    assert step(status, JellyfinStep.PUBLIC_INFO) is StepStatus.FAILED
    assert {row.status for row in status.steps[1:]} == {StepStatus.PENDING}


# --- 精靈的步數 ---


@pytest.mark.asyncio
async def test_the_wizard_moves_past_jellyfin_once_the_sequence_is_done(
    session: AsyncSession, tmp_path: Path
) -> None:
    await seed(session, library_root=str(tmp_path / "library"))
    assert (await read_status(session)).current_step == 3

    await bootstrap_jellyfin(session, FakeClientFactory(jellyfin=FakeJellyfinClient()))

    assert (await read_status(session)).current_step == STEP_QBITTORRENT


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
