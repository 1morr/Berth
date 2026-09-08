"""精靈第 3 步的 services 命令（plan §9.4、§9.5、票 06）。

驗的是票 06 的驗收條件本身：九步跑完之後 Jellyfin 上真的有那些東西、metadata fetcher 是
設定值、任務存的是 `Id`、重按不會建第二份、失敗的那一步可以單獨重來、既有路徑不碰舊資料。
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import AuthFailedError, ServiceUnavailableError
from berth.adapters.jellyfin import (
    JellyfinApiKey,
    JellyfinLibrary,
    JellyfinPlugin,
    JellyfinTask,
    TypeOption,
)
from berth.adapters.jellyfin.fake import FakeJellyfinClient
from berth.domain import (
    DetectionReason,
    JellyfinStep,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.models import JellyfinSettings, PathSettings, ServiceProbe, SetupSettings
from berth.services.jellyfin import (
    MERGE_VERSIONS_GUID,
    JellyfinSetupStatus,
    add_berth_path,
    bootstrap_jellyfin,
    connect_jellyfin,
    install_merge_versions,
)
from berth.services.settings import read_settings, write_settings
from berth.services.setup import STEP_QBITTORRENT, create_admin, read_status
from tests.integration.factories import FakeClientFactory

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


async def never_sleep(_seconds: float) -> None:
    return None


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
            detail="10.11.11",
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


# --- 套件內：plan §9.4 的九步 ---


@pytest.mark.asyncio
async def test_bootstrap_runs_the_whole_sequence(session: AsyncSession, tmp_path: Path) -> None:
    await seed(session, library_root=str(tmp_path / "library"))
    jellyfin = FakeJellyfinClient()
    factory = FakeClientFactory(jellyfin=jellyfin)

    status = await bootstrap_jellyfin(session, factory, sleep=never_sleep)

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
    # MergeVersions 裝好並重啟過一次。
    assert [plugin.id for plugin in jellyfin.plugins_] == [MERGE_VERSIONS_GUID.replace("-", "")]
    assert jellyfin.restarts == 1


@pytest.mark.asyncio
async def test_bootstrap_writes_the_library_options_the_plan_asks_for(
    session: AsyncSession, tmp_path: Path
) -> None:
    await seed(session, library_root=str(tmp_path / "library"))
    jellyfin = FakeJellyfinClient()

    await bootstrap_jellyfin(session, FakeClientFactory(jellyfin=jellyfin), sleep=never_sleep)

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

    await bootstrap_jellyfin(session, FakeClientFactory(jellyfin=jellyfin), sleep=never_sleep)

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
async def test_bootstrap_stores_the_api_key_and_the_task_ids(
    session: AsyncSession, tmp_path: Path
) -> None:
    await seed(session, library_root=str(tmp_path / "library"))
    jellyfin = FakeJellyfinClient()

    status = await bootstrap_jellyfin(
        session, FakeClientFactory(jellyfin=jellyfin), sleep=never_sleep
    )

    stored = await read_settings(session, JellyfinSettings)
    assert stored.api_key == jellyfin.api_keys_[0].access_token
    assert stored.base_url == "http://jellyfin:8096"
    # 存的是 `Id` 不是 `Key`（brief §20.7）。
    assert stored.merge_movies_task_id == "fd957c84b0cfc2380becf2893e4b76fc"
    assert stored.merge_episodes_task_id == "dcaf151dd1af25aefe775c58e214477e"
    assert status.api_key_present is True
    assert detail(status, JellyfinStep.TASKS) == (
        "fd957c84b0cfc2380becf2893e4b76fc · dcaf151dd1af25aefe775c58e214477e"
    )


@pytest.mark.asyncio
async def test_pressing_bootstrap_twice_changes_nothing(
    session: AsyncSession, tmp_path: Path
) -> None:
    """票 06 驗收：重按不會重複建立媒體庫或重複安裝插件。"""
    await seed(session, library_root=str(tmp_path / "library"))
    jellyfin = FakeJellyfinClient()
    factory = FakeClientFactory(jellyfin=jellyfin)
    await bootstrap_jellyfin(session, factory, sleep=never_sleep)

    status = await bootstrap_jellyfin(session, factory, sleep=never_sleep)

    assert len(jellyfin.libraries_) == 3
    assert len(jellyfin.api_keys_) == 1
    assert len(jellyfin.plugins_) == 1
    assert jellyfin.restarts == 1
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
    await bootstrap_jellyfin(session, factory, sleep=never_sleep)
    jellyfin.use_token("")

    status = await bootstrap_jellyfin(session, factory, sleep=never_sleep)

    assert step(status, JellyfinStep.LIBRARIES) is StepStatus.SKIPPED
    assert detail(status, JellyfinStep.LIBRARIES) == "Movies · TV · Anime"


@pytest.mark.asyncio
async def test_bootstrap_waits_for_jellyfin_to_finish_loading_after_the_restart(
    session: AsyncSession, tmp_path: Path
) -> None:
    """`/System/Info/Public` 早就回 200 了，管理員 API 還在 503（brief §20.7）。"""
    await seed(session, library_root=str(tmp_path / "library"))
    jellyfin = FakeJellyfinClient(busy_after_restart=3)

    status = await bootstrap_jellyfin(
        session, FakeClientFactory(jellyfin=jellyfin), sleep=never_sleep
    )

    assert step(status, JellyfinStep.PLUGIN) is StepStatus.OK
    assert step(status, JellyfinStep.TASKS) is StepStatus.OK


@pytest.mark.asyncio
async def test_a_restart_that_drops_the_connection_is_not_a_failure(
    session: AsyncSession, tmp_path: Path
) -> None:
    """`POST /System/Restart` 有時候在回應送出去之前就把連線切了（brief §20.7）。"""
    await seed(session, library_root=str(tmp_path / "library"))
    jellyfin = FakeJellyfinClient(drop_on_restart=True, busy_after_restart=2)

    status = await bootstrap_jellyfin(
        session, FakeClientFactory(jellyfin=jellyfin), sleep=never_sleep
    )

    assert step(status, JellyfinStep.PLUGIN) is StepStatus.OK
    assert step(status, JellyfinStep.TASKS) is StepStatus.OK
    assert jellyfin.restarts == 1


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

    status = await bootstrap_jellyfin(
        session, FakeClientFactory(jellyfin=jellyfin), sleep=never_sleep
    )

    assert [row.has_berth_path for row in status.libraries] == [True, True, True]
    assert [row.berth_path for row in status.libraries] == [
        f"{root}/movies",
        f"{root}/tv",
        f"{root}/anime",
    ]


@pytest.mark.asyncio
async def test_bootstrap_retries_a_plugin_download_that_drops(
    session: AsyncSession, tmp_path: Path
) -> None:
    """下載是 Jellyfin 自己連 GitHub，實測會偶發 TLS 中斷回 500（brief §20.7）。"""
    await seed(session, library_root=str(tmp_path / "library"))
    jellyfin = FakeJellyfinClient(install_failures=2)

    status = await bootstrap_jellyfin(
        session, FakeClientFactory(jellyfin=jellyfin), sleep=never_sleep
    )

    assert step(status, JellyfinStep.PLUGIN) is StepStatus.OK
    assert len(jellyfin.installs) == 3


# --- 失敗與重試 ---


@pytest.mark.asyncio
async def test_a_failing_step_stops_the_sequence_and_keeps_what_worked(
    session: AsyncSession, tmp_path: Path
) -> None:
    await seed(session, library_root=str(tmp_path / "library"))
    jellyfin = FakeJellyfinClient(install_failures=99)
    factory = FakeClientFactory(jellyfin=jellyfin)

    status = await bootstrap_jellyfin(session, factory, sleep=never_sleep)

    assert step(status, JellyfinStep.PLUGIN) is StepStatus.FAILED
    assert step(status, JellyfinStep.TASKS) is StepStatus.PENDING
    failure = next(row for row in status.steps if row.step == JellyfinStep.PLUGIN.value)
    assert "MergeVersions did not install" in failure.error
    # 前面七步做過的事都留著，重按時才跳得過去。
    assert {row.status for row in status.steps[:7]} == {StepStatus.OK}
    assert jellyfin.startup_wizard_completed is True


@pytest.mark.asyncio
async def test_retrying_after_a_failure_only_redoes_the_failed_step(
    session: AsyncSession, tmp_path: Path
) -> None:
    """票 06 驗收：任一步失敗時該步可單獨重試。"""
    await seed(session, library_root=str(tmp_path / "library"))
    jellyfin = FakeJellyfinClient(install_failures=99)
    factory = FakeClientFactory(jellyfin=jellyfin)
    await bootstrap_jellyfin(session, factory, sleep=never_sleep)
    jellyfin.install_failures = 0

    status = await bootstrap_jellyfin(session, factory, sleep=never_sleep)

    assert step(status, JellyfinStep.PLUGIN) is StepStatus.OK
    assert step(status, JellyfinStep.TASKS) is StepStatus.OK
    # 媒體庫沒有被再建一次。
    assert len(jellyfin.libraries_) == 3


@pytest.mark.asyncio
async def test_bootstrap_without_an_administrator_says_so(
    session: AsyncSession, tmp_path: Path
) -> None:
    await seed(session, library_root=str(tmp_path / "library"), admin=None)
    jellyfin = FakeJellyfinClient()

    status = await bootstrap_jellyfin(
        session, FakeClientFactory(jellyfin=jellyfin), sleep=never_sleep
    )

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

    status = await bootstrap_jellyfin(
        session, FakeClientFactory(jellyfin=jellyfin), sleep=never_sleep
    )

    assert step(status, JellyfinStep.PUBLIC_INFO) is StepStatus.FAILED
    assert {row.status for row in status.steps[1:]} == {StepStatus.PENDING}


# --- 精靈的步數 ---


@pytest.mark.asyncio
async def test_the_wizard_moves_past_jellyfin_once_the_sequence_is_done(
    session: AsyncSession, tmp_path: Path
) -> None:
    await seed(session, library_root=str(tmp_path / "library"))
    assert (await read_status(session)).current_step == 3

    await bootstrap_jellyfin(
        session, FakeClientFactory(jellyfin=FakeJellyfinClient()), sleep=never_sleep
    )

    assert (await read_status(session)).current_step == STEP_QBITTORRENT


# --- 既有 Jellyfin（plan §9.5）---


def nas_jellyfin(**overrides: object) -> FakeJellyfinClient:
    """一台使用者自己的 Jellyfin：跑過自己的精靈、有兩個媒體庫，其中一個掛了 TVDB。"""
    defaults: dict[str, object] = {
        "base_url": "http://nas:8096",
        "server_name": "nas",
        "version": "10.10.7",
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
async def test_installing_merge_versions_on_an_existing_jellyfin(
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

    status = await install_merge_versions(session, factory, sleep=never_sleep)

    assert status.merge_versions_installed is True
    assert jellyfin.restarts == 1
    assert status.merge_movies_task_id == "fd957c84b0cfc2380becf2893e4b76fc"
    # 只跑第 8、9 步：媒體庫一個都沒被建。
    assert jellyfin.created == []
    assert step(status, JellyfinStep.PLUGIN) is StepStatus.OK


@pytest.mark.asyncio
async def test_installing_merge_versions_twice_does_not_restart_again(
    session: AsyncSession, tmp_path: Path
) -> None:
    await seed(
        session,
        origin=ServiceOrigin.EXISTING,
        base_url="http://nas:8096",
        library_root=str(tmp_path / "library"),
    )
    jellyfin = nas_jellyfin(
        plugins=(
            JellyfinPlugin(
                id=MERGE_VERSIONS_GUID.replace("-", ""), name="Merge Versions", version="10.10.0.5"
            ),
        ),
        tasks=(
            JellyfinTask(id="m1", key="MergeMoviesTask", name="Merge All Movies"),
            JellyfinTask(id="e1", key="MergeEpisodesTask", name="Merge All Episodes"),
        ),
    )
    factory = FakeClientFactory(jellyfin=jellyfin)
    await connect_jellyfin(session, factory, username="owner", password="s3cret")

    status = await install_merge_versions(session, factory, sleep=never_sleep)

    assert jellyfin.restarts == 0
    assert step(status, JellyfinStep.PLUGIN) is StepStatus.SKIPPED
    assert detail(status, JellyfinStep.PLUGIN) == "10.10.0.5"
    assert status.merge_movies_task_id == "m1"


@pytest.mark.asyncio
async def test_installing_without_credentials_fails_instead_of_guessing(
    session: AsyncSession, tmp_path: Path
) -> None:
    await seed(
        session,
        origin=ServiceOrigin.EXISTING,
        base_url="http://nas:8096",
        library_root=str(tmp_path / "library"),
        admin=None,
    )

    status = await install_merge_versions(
        session, FakeClientFactory(jellyfin=nas_jellyfin()), sleep=never_sleep
    )

    failure = next(row for row in status.steps if row.step == JellyfinStep.PLUGIN.value)
    assert failure.status is StepStatus.FAILED
    assert "credentials" in failure.error


@pytest.mark.asyncio
async def test_an_expired_api_key_surfaces_as_a_failed_step(
    session: AsyncSession, tmp_path: Path
) -> None:
    await seed(
        session,
        origin=ServiceOrigin.EXISTING,
        base_url="http://nas:8096",
        library_root=str(tmp_path / "library"),
    )
    jellyfin = nas_jellyfin(error=AuthFailedError("401"))

    status = await install_merge_versions(
        session, FakeClientFactory(jellyfin=jellyfin), sleep=never_sleep
    )

    failure = next(row for row in status.steps if row.step == JellyfinStep.PLUGIN.value)
    assert failure.status is StepStatus.FAILED
    assert "401" in failure.error
