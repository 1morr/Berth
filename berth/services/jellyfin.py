"""精靈第 3 步：Jellyfin（plan §9.3 第 3 步、§9.4、§9.5）。

兩條路徑共用同一份狀態形狀（`SetupJellyfin`）：

- **套件內**：`bootstrap_jellyfin` 跑完 plan §9.4 的九步。每一步都冪等——媒體庫先看再建、
  API key 先列再建、插件先看裝了沒。重按只會把已經對的那幾步標成 `skipped`。
- **既有**：`connect_jellyfin` 以管理員帳密登入並建立 API key、列出媒體庫；`add_berth_path`
  為選定的媒體庫**加**一條路徑；`install_merge_versions` 是那顆要二次確認的按鈕。

既有 Jellyfin 的紅線（brief §16.4）：本檔絕不自動建立媒體庫、不改既有 `LibraryOptions`、
不刪除任何東西——adapter 的介面上根本沒有那些方法。

每一步在做之前先把自己標成 `running` 並 commit，所以前端輪詢 `GET /api/setup/jellyfin`
就看得到序列走到哪裡，不必為了進度另外開一條通道。
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.fs import ensure_directory
from berth.adapters.http import ServiceBusyError, ServiceError, ServiceUnavailableError
from berth.adapters.jellyfin import (
    JellyfinClient,
    JellyfinLibrary,
    JellyfinRepository,
    NewLibrary,
    TypeOption,
)
from berth.domain import CollectionType, JellyfinStep, ServiceKind, ServiceOrigin, StepStatus
from berth.models import (
    ANIME_SLUG,
    MOVIES_SLUG,
    TV_SLUG,
    JellyfinSettings,
    PathSettings,
    SetupAdmin,
    SetupLibrary,
    SetupSettings,
    SetupStep,
)
from berth.services.clients import ServiceClientFactory
from berth.services.settings import read_settings, write_settings

#: `POST /Auth/Keys?app=` 用的名字。也是重按時辨認「這把是我建的」的依據。
API_KEY_APP = "Berth"

#: plan §9.4 第 2 步。「精靈可改」是之後的事，M0 用固定值。
UI_CULTURE = "zh-TW"
METADATA_LANGUAGE = "zh-TW"
METADATA_COUNTRY = "TW"

#: brief §10 的決定：第一階段只用 TMDB。設定裡沒寫的媒體庫落回這個。
DEFAULT_METADATA_FETCHER = "TheMovieDb"

MERGE_VERSIONS_REPOSITORY = JellyfinRepository(
    name="danieladov",
    url="https://raw.githubusercontent.com/danieladov/JellyfinPluginManifest/master/manifest.json",
    enabled=True,
)
MERGE_VERSIONS_PACKAGE = "Merge Versions"
MERGE_VERSIONS_GUID = "f21bbed8-3a97-4d8b-88b2-48aaa65427cb"
MERGE_MOVIES_TASK_KEY = "MergeMoviesTask"
MERGE_EPISODES_TASK_KEY = "MergeEpisodesTask"

#: 媒體庫掛了 TVDB 的 metadata fetcher 就警告（brief §16.4）。比對小寫子字串，因為名字由
#: 插件自己決定（官方插件是 `TheTVDB`）。
TVDB_MARKER = "tvdb"

#: 插件庫要多久才出現這個套件、下載安裝重試幾次、重啟後等多久（brief §20.7）。
PACKAGE_ATTEMPTS = 30
INSTALL_ATTEMPTS = 3
RESTART_ATTEMPTS = 100
POLL_SECONDS = 4.0

Sleeper = Callable[[float], Awaitable[None]]


class StepFailedError(Exception):
    """這一步做不下去，而且原因不是外部服務丟出來的例外。"""


@dataclass(frozen=True, slots=True)
class BundledLibrary:
    """套件內固定建立的媒體庫（plan §9.4 第 4 步、brief §16.3）。"""

    slug: str
    name: str
    collection_type: CollectionType


BUNDLED_LIBRARIES: tuple[BundledLibrary, ...] = (
    BundledLibrary(MOVIES_SLUG, "Movies", CollectionType.MOVIES),
    BundledLibrary(TV_SLUG, "TV", CollectionType.TVSHOWS),
    BundledLibrary(ANIME_SLUG, "Anime", CollectionType.TVSHOWS),
)


@dataclass(frozen=True, slots=True)
class StepView:
    step: str
    status: StepStatus
    detail: str
    error: str


@dataclass(frozen=True, slots=True)
class LibraryView:
    name: str
    collection_type: str
    locations: tuple[str, ...]
    metadata_fetchers: tuple[str, ...]
    #: 這個媒體庫掛了 TVDB 的 metadata fetcher（brief §16.4 的警告，不阻擋）。
    uses_tvdb: bool
    #: 「加入 Berth 路徑」會加的那一條。按之前就顯示它（剖面即預覽）。
    berth_path: str
    has_berth_path: bool


@dataclass(frozen=True, slots=True)
class JellyfinSetupStatus:
    """`GET /api/setup/jellyfin` 的整份形狀。兩條路徑共用。"""

    origin: ServiceOrigin
    base_url: str
    api_key_present: bool
    steps: tuple[StepView, ...]
    libraries: tuple[LibraryView, ...]
    merge_versions_installed: bool
    merge_movies_task_id: str
    merge_episodes_task_id: str


async def read_jellyfin_status(session: AsyncSession) -> JellyfinSetupStatus:
    """不連線，只把存下來的狀態攤成 UI 的形狀。輪詢進度也走這一支。"""
    setup = await read_settings(session, SetupSettings)
    jellyfin = await read_settings(session, JellyfinSettings)
    paths = await read_settings(session, PathSettings)
    origin, base_url = _target(setup, jellyfin)
    return JellyfinSetupStatus(
        origin=origin,
        base_url=base_url,
        api_key_present=bool(jellyfin.api_key),
        steps=tuple(
            StepView(step=row.key, status=row.status, detail=row.detail, error=row.error)
            for row in setup.jellyfin.steps
        ),
        libraries=tuple(_library_view(row, paths.library_root) for row in setup.jellyfin.libraries),
        merge_versions_installed=setup.jellyfin.merge_versions_installed,
        merge_movies_task_id=jellyfin.merge_movies_task_id,
        merge_episodes_task_id=jellyfin.merge_episodes_task_id,
    )


async def bootstrap_jellyfin(
    session: AsyncSession, factory: ServiceClientFactory, *, sleep: Sleeper = asyncio.sleep
) -> JellyfinSetupStatus:
    """套件內路徑：跑完 plan §9.4 的九步。重按只補做還沒做的那幾步。"""
    return await _run(session, factory, tuple(JellyfinStep), sleep=sleep)


async def install_merge_versions(
    session: AsyncSession, factory: ServiceClientFactory, *, sleep: Sleeper = asyncio.sleep
) -> JellyfinSetupStatus:
    """既有路徑的「安裝 MergeVersions」按鈕：只跑第 8、9 步（plan §9.5）。

    與套件內走的是同一段程式碼，所以「會重啟 Jellyfin」這件事在兩條路徑上完全一樣。
    """
    return await _run(session, factory, (JellyfinStep.PLUGIN, JellyfinStep.TASKS), sleep=sleep)


async def connect_jellyfin(
    session: AsyncSession, factory: ServiceClientFactory, *, username: str, password: str
) -> JellyfinSetupStatus:
    """既有路徑：以**那台 Jellyfin 的**管理員帳密登入、建 API key、列出媒體庫（plan §9.5）。

    帳密不存下來：Berth 只需要 API key，而那台伺服器的管理員密碼不是 Berth 的東西。
    """
    return await _run(
        session,
        factory,
        (JellyfinStep.PUBLIC_INFO, JellyfinStep.API_KEY),
        sleep=asyncio.sleep,
        credentials=(username, password),
    )


async def add_berth_path(
    session: AsyncSession, factory: ServiceClientFactory, *, library_name: str
) -> JellyfinSetupStatus:
    """既有路徑的「加入 Berth 路徑」按鈕（plan §9.5、brief §16.4）。

    **舊路徑原地不動**：`POST /Library/VirtualFolders/Paths` 是加一條而不是換一條。
    目錄要先存在（不存在 Jellyfin 回 404），同一條路徑加兩次會出現重複的 location，
    所以兩件事都先擋掉（實測，brief §20.7）。

    失敗與序列裡的步驟走同一條路：記成 `libraries` 這一步的 `failed`，畫面就有原文與手動
    步驟可看。「目錄建不出來」正是 brief §16.4 那句「哪個容器少了哪個掛載」最典型的失敗，
    把它變成 500 等於把唯一有用的訊息丟掉。
    """
    setup = await read_settings(session, SetupSettings)
    jellyfin = await read_settings(session, JellyfinSettings)
    paths = await read_settings(session, PathSettings)
    _, base_url = _target(setup, jellyfin)

    client = factory.jellyfin(base_url, token=jellyfin.api_key)
    libraries: tuple[JellyfinLibrary, ...] | None = None
    await _record(session, _step(JellyfinStep.LIBRARIES, StepStatus.RUNNING))
    try:
        libraries = await client.libraries()
        library = next((row for row in libraries if row.name == library_name), None)
        if library is None:
            raise StepFailedError(f"no library named {library_name!r} on this Jellyfin")
        path = _berth_path(library_name, paths.library_root)
        if path not in library.locations:
            ensure_directory(Path(path))
            await client.add_library_path(library_name, path)
            libraries = await client.libraries()
    except (ServiceError, StepFailedError, OSError) as exc:
        await _record(
            session,
            SetupStep(
                key=JellyfinStep.LIBRARIES.value,
                status=StepStatus.FAILED,
                detail=library_name,
                error=_message(exc),
            ),
        )
    else:
        await _record(
            session,
            SetupStep(
                key=JellyfinStep.LIBRARIES.value,
                status=StepStatus.OK,
                detail=f"{library_name} · {path}",
            ),
        )
    finally:
        await client.aclose()

    await _remember(session, libraries=libraries)
    await session.commit()
    return await read_jellyfin_status(session)


# --- 序列 ---------------------------------------------------------------


async def _run(
    session: AsyncSession,
    factory: ServiceClientFactory,
    steps: tuple[JellyfinStep, ...],
    *,
    sleep: Sleeper,
    credentials: tuple[str, str] | None = None,
) -> JellyfinSetupStatus:
    setup = await read_settings(session, SetupSettings)
    jellyfin = await read_settings(session, JellyfinSettings)
    paths = await read_settings(session, PathSettings)
    _, base_url = _target(setup, jellyfin)

    client = factory.jellyfin(base_url, token=jellyfin.api_key)
    runner = _Runner(client, setup.admin, jellyfin, paths, sleep=sleep)
    if credentials is not None:
        runner.sign_in_as(*credentials)
    try:
        # 這一輪要跑的步驟先全部歸零，畫面才不會把上一輪的結果當成這一輪的進度。
        await _record(session, *(_step(step, StepStatus.PENDING) for step in steps))
        for step in steps:
            await _record(session, _step(step, StepStatus.RUNNING))
            result = await runner.run(step)
            await _record(session, result)
            if result.status is StepStatus.FAILED:
                break
        await runner.refresh_libraries()
    finally:
        await client.aclose()

    await _remember(
        session, libraries=runner.libraries, merge_installed=runner.merge_versions_installed
    )
    jellyfin.base_url = base_url
    jellyfin.api_key = runner.api_key or jellyfin.api_key
    jellyfin.merge_movies_task_id = runner.merge_movies_task_id or jellyfin.merge_movies_task_id
    jellyfin.merge_episodes_task_id = (
        runner.merge_episodes_task_id or jellyfin.merge_episodes_task_id
    )
    await write_settings(session, jellyfin)
    await session.commit()
    return await read_jellyfin_status(session)


async def _record(session: AsyncSession, *steps: SetupStep) -> None:
    """把步驟的最新狀態寫進設定並 commit。

    每一步各自 commit，前端輪詢才看得到序列走到哪裡；中途失敗時已完成的步驟也留得下來，
    重按時才跳得過它們。
    """
    setup = await read_settings(session, SetupSettings)
    by_key = {row.key: row for row in setup.jellyfin.steps}
    for step in steps:
        by_key[step.key] = step
    setup.jellyfin.steps = [by_key[key] for key in _ordered(by_key)]
    await write_settings(session, setup)
    await session.commit()


async def _remember(
    session: AsyncSession,
    *,
    libraries: tuple[JellyfinLibrary, ...] | None = None,
    merge_installed: bool = False,
) -> None:
    setup = await read_settings(session, SetupSettings)
    if libraries is not None:
        setup.jellyfin.libraries = [
            SetupLibrary(
                name=library.name,
                collection_type=library.collection_type,
                locations=list(library.locations),
                metadata_fetchers=sorted(
                    {name for option in library.type_options for name in option.metadata_fetchers}
                ),
            )
            for library in libraries
        ]
    if merge_installed:
        setup.jellyfin.merge_versions_installed = True
    await write_settings(session, setup)


def _ordered(by_key: dict[str, SetupStep]) -> list[str]:
    """照 plan §9.4 的順序排；認不得的鍵（舊資料）排在後面而不是被丟掉。"""
    known = [step.value for step in JellyfinStep if step.value in by_key]
    seen = set(known)
    return known + [key for key in by_key if key not in seen]


class _Runner:
    """一次序列執行。步驟之間共享的東西（憑證、媒體庫）住在這裡，不透過參數傳。"""

    def __init__(
        self,
        client: JellyfinClient,
        admin: SetupAdmin,
        jellyfin: JellyfinSettings,
        paths: PathSettings,
        *,
        sleep: Sleeper = asyncio.sleep,
    ) -> None:
        self._client = client
        self._jellyfin = jellyfin
        self._paths = paths
        self._sleep = sleep
        self._credentials = (admin.username, admin.password)
        self._token = jellyfin.api_key
        self._fresh = False
        self.api_key = jellyfin.api_key
        #: `None` 代表這一輪沒讀到媒體庫；不要拿它覆寫存下來的清單。
        self.libraries: tuple[JellyfinLibrary, ...] | None = None
        self.merge_versions_installed = False
        self.merge_movies_task_id = ""
        self.merge_episodes_task_id = ""

    def sign_in_as(self, username: str, password: str) -> None:
        """既有 Jellyfin 的管理員帳密，與 Berth 自己的那一組無關。"""
        self._credentials = (username, password)
        self._token = ""

    async def run(self, step: JellyfinStep) -> SetupStep:
        try:
            status, detail = await _ACTIONS[step](self)
        except (ServiceError, StepFailedError, OSError) as exc:
            return SetupStep(key=step.value, status=StepStatus.FAILED, error=_message(exc))
        return SetupStep(key=step.value, status=status, detail=detail)

    async def refresh_libraries(self) -> None:
        """收尾時再讀一次媒體庫。讀不到就維持 `None`，讓存下來的清單原封不動。"""
        try:
            self.libraries = await self._client.libraries()
        except ServiceError:
            return

    # --- 九個步驟 ---

    async def _public_info(self) -> tuple[StepStatus, str]:
        info = await self._client.public_info()
        self._fresh = not info.startup_wizard_completed
        return StepStatus.OK, info.version

    async def _configuration(self) -> tuple[StepStatus, str]:
        detail = f"{UI_CULTURE} · {METADATA_COUNTRY}"
        if not self._fresh:
            return StepStatus.SKIPPED, detail
        await self._client.start_configuration(
            ui_culture=UI_CULTURE,
            metadata_country_code=METADATA_COUNTRY,
            preferred_metadata_language=METADATA_LANGUAGE,
        )
        return StepStatus.OK, detail

    async def _admin_user(self) -> tuple[StepStatus, str]:
        username, password = self._credentials
        if not username or not password:
            raise StepFailedError("no Berth administrator yet; finish step 1 of the wizard first")
        if not self._fresh:
            return StepStatus.SKIPPED, username
        # GET 不是多餘的讀取：它會建立預設使用者，少了它 POST 回 500（brief §20.7）。
        await self._client.ensure_default_user()
        await self._client.create_startup_user(username, password)
        return StepStatus.OK, username

    async def _libraries(self) -> tuple[StepStatus, str]:
        if not self._fresh:
            # 初始精靈跑完之後，`/Library/VirtualFolders` 就要管理員憑證了。
            await self._authenticate()
        existing = {library.name for library in await self._client.libraries()}
        created: list[str] = []
        for bundled in BUNDLED_LIBRARIES:
            # 與既有媒體庫的 Berth 路徑同一支函式：兩套算法遲早會分岔，而分岔的症狀是
            # `has_berth_path` 對 Berth 自己建的路徑報 false（`test_bundled_paths_...` 釘住）。
            path = _berth_path(bundled.name, self._paths.library_root)
            # 媒體庫目錄由 Berth 建（plan §9.1）；兩邊掛同一個宿主目錄，所以建完 Jellyfin
            # 立刻看得到。
            ensure_directory(Path(path))
            if bundled.name in existing:
                # 同名不會被拒，會長出 `Movies2` 指向同一個路徑（實測，brief §20.7）。
                continue
            await self._client.create_library(await self._new_library(bundled, path))
            created.append(bundled.name)
        self.libraries = await self._client.libraries()
        if created:
            return StepStatus.OK, " · ".join(created)
        return StepStatus.SKIPPED, " · ".join(
            bundled.name for bundled in BUNDLED_LIBRARIES if bundled.name in existing
        )

    async def _remote_access(self) -> tuple[StepStatus, str]:
        if not self._fresh:
            return StepStatus.SKIPPED, ""
        await self._client.set_remote_access(enabled=True)
        return StepStatus.OK, ""

    async def _complete(self) -> tuple[StepStatus, str]:
        if not self._fresh:
            return StepStatus.SKIPPED, ""
        await self._client.complete_startup()
        return StepStatus.OK, ""

    async def _api_key(self) -> tuple[StepStatus, str]:
        await self._authenticate()
        existing = await self._find_api_key()
        if existing is not None:
            self._use(existing)
            return StepStatus.SKIPPED, API_KEY_APP
        # `POST /Auth/Keys` 不回傳 key 也不檢查重複，所以先找再建、建完再列（brief §20.7）。
        await self._client.create_api_key(API_KEY_APP)
        created = await self._find_api_key()
        if created is None:
            raise StepFailedError("Jellyfin accepted POST /Auth/Keys but the key is not listed")
        self._use(created)
        return StepStatus.OK, API_KEY_APP

    async def _plugin(self) -> tuple[StepStatus, str]:
        await self._authenticate()
        version = await self._installed_merge_versions()
        if version is not None:
            self.merge_versions_installed = True
            return StepStatus.SKIPPED, version
        repositories = await self._client.repositories()
        if not any(repo.url == MERGE_VERSIONS_REPOSITORY.url for repo in repositories):
            # `POST /Repositories` 是整份覆寫，所以先讀再合併。
            await self._client.set_repositories((*repositories, MERGE_VERSIONS_REPOSITORY))
        await self._wait_for_package()
        await self._install_package()
        await self._restart()
        await self._wait_for_admin_api()
        version = await self._installed_merge_versions()
        if version is None:
            raise StepFailedError("MergeVersions is not listed after the restart")
        self.merge_versions_installed = True
        return StepStatus.OK, version

    async def _tasks(self) -> tuple[StepStatus, str]:
        await self._authenticate()
        tasks = {task.key: task.id for task in await self._client.scheduled_tasks()}
        movies = tasks.get(MERGE_MOVIES_TASK_KEY, "")
        episodes = tasks.get(MERGE_EPISODES_TASK_KEY, "")
        if not movies or not episodes:
            raise StepFailedError(
                f"{MERGE_MOVIES_TASK_KEY} / {MERGE_EPISODES_TASK_KEY} are not in /ScheduledTasks"
            )
        # 存的是 `Id` 不是 `Key`：觸發要用 Id（brief §20.7）。
        self.merge_movies_task_id = movies
        self.merge_episodes_task_id = episodes
        unchanged = (
            movies == self._jellyfin.merge_movies_task_id
            and episodes == self._jellyfin.merge_episodes_task_id
        )
        return (StepStatus.SKIPPED if unchanged else StepStatus.OK), f"{movies} · {episodes}"

    # --- 步驟共用 ---

    async def _authenticate(self) -> None:
        """有 token 就用它；沒有就以管理員帳密換一個。API key 與登入 token 同一個形狀。"""
        if self._token:
            self._client.use_token(self._token)
            return
        username, password = self._credentials
        if not username or not password:
            raise StepFailedError("no administrator credentials for this Jellyfin")
        auth = await self._client.authenticate(username, password)
        if not auth.is_administrator:
            raise StepFailedError(f"{username} is not a Jellyfin administrator")
        self._token = auth.token
        self._client.use_token(auth.token)

    def _use(self, api_key: str) -> None:
        """之後改用 API key 而不是登入 token——它是 Berth 長期要用的那一把。"""
        self.api_key = api_key
        self._token = api_key
        self._client.use_token(api_key)

    async def _find_api_key(self) -> str | None:
        for key in await self._client.api_keys():
            if key.app_name == API_KEY_APP:
                return key.access_token
        return None

    async def _new_library(self, bundled: BundledLibrary, path: str) -> NewLibrary:
        available = await self._client.available_type_options(bundled.collection_type)
        fetchers = self._jellyfin.metadata_fetchers.get(bundled.slug) or [DEFAULT_METADATA_FETCHER]
        return NewLibrary(
            name=bundled.name,
            collection_type=bundled.collection_type,
            path=path,
            # metadata fetcher 是設定值（brief §10 的 TVDB【研究】就改這裡）；圖片 fetcher
            # 跟著這台伺服器自己的可用清單走——寫死會讓沒對到 TMDB 的作品連縮圖都沒有
            # （省略 `ImageFetchers` 會被存成空陣列，實測，brief §20.7）。
            type_options=tuple(
                TypeOption(
                    type=option.type,
                    metadata_fetchers=tuple(fetchers),
                    image_fetchers=option.image_fetchers,
                )
                for option in available
            ),
            preferred_metadata_language=METADATA_LANGUAGE,
            metadata_country_code=METADATA_COUNTRY,
        )

    async def _installed_merge_versions(self) -> str | None:
        wanted = MERGE_VERSIONS_GUID.replace("-", "").lower()
        for plugin in await self._client.plugins():
            if plugin.id == wanted:
                return plugin.version
        return None

    async def _wait_for_package(self) -> None:
        """加完 repository 之後 Jellyfin 要自己去抓 manifest，套件才會出現在插件庫。"""
        for _ in range(PACKAGE_ATTEMPTS):
            if await self._client.package_versions(MERGE_VERSIONS_PACKAGE):
                return
            await self._sleep(POLL_SECONDS)
        raise StepFailedError(
            f"{MERGE_VERSIONS_PACKAGE} did not appear in the plugin catalogue; "
            "Jellyfin could not reach the manifest"
        )

    async def _install_package(self) -> None:
        """下載由 Jellyfin 自己連 GitHub，實測會偶發 TLS 中斷回 500，所以重試（brief §20.7）。"""
        last = ""
        for _ in range(INSTALL_ATTEMPTS):
            try:
                await self._client.install_package(
                    MERGE_VERSIONS_PACKAGE, assembly_guid=MERGE_VERSIONS_GUID
                )
            except ServiceError as exc:
                last = _message(exc)
            await self._sleep(POLL_SECONDS)
            if await self._installed_merge_versions() is not None:
                return
        raise StepFailedError(
            f"MergeVersions did not install after {INSTALL_ATTEMPTS} tries: {last}"
        )

    async def _restart(self) -> None:
        """`POST /System/Restart` 有時候在回應送出去之前就把連線切了（brief §20.7）。

        那是重啟開始了的樣子，不是失敗——重啟到底有沒有成功，由接下來的輪詢決定。
        """
        try:
            await self._client.restart()
        except ServiceUnavailableError:
            return

    async def _wait_for_admin_api(self) -> None:
        """輪詢**真正要用的**管理員端點回 200，不是 `/System/Info/Public`。

        後者在伺服器還在載入時就回 200 了，這時 `/ScheduledTasks` 回 503（brief §20.7）。
        重啟瞬間連線會直接被切斷，所以「連不上」也算還沒好。
        """
        for _ in range(RESTART_ATTEMPTS):
            await self._sleep(POLL_SECONDS)
            try:
                await self._client.scheduled_tasks()
            except (ServiceBusyError, ServiceUnavailableError):
                continue
            return
        raise StepFailedError(
            "Jellyfin did not answer /ScheduledTasks within "
            f"{int(RESTART_ATTEMPTS * POLL_SECONDS)}s after the restart"
        )


_ACTIONS: dict[JellyfinStep, Callable[[_Runner], Awaitable[tuple[StepStatus, str]]]] = {
    JellyfinStep.PUBLIC_INFO: _Runner._public_info,
    JellyfinStep.CONFIGURATION: _Runner._configuration,
    JellyfinStep.ADMIN_USER: _Runner._admin_user,
    JellyfinStep.LIBRARIES: _Runner._libraries,
    JellyfinStep.REMOTE_ACCESS: _Runner._remote_access,
    JellyfinStep.COMPLETE: _Runner._complete,
    JellyfinStep.API_KEY: _Runner._api_key,
    JellyfinStep.PLUGIN: _Runner._plugin,
    JellyfinStep.TASKS: _Runner._tasks,
}

#: 少一步就在 import 時炸，而不是等使用者按下去才 `KeyError`。
assert set(_ACTIONS) == set(JellyfinStep), "every JellyfinStep needs an action"


# --- 小工具 -------------------------------------------------------------


def _target(setup: SetupSettings, jellyfin: JellyfinSettings) -> tuple[ServiceOrigin, str]:
    """第 3 步要連哪一台、它是套件內還是既有——兩者都由第 2 步的判定決定。"""
    probe = setup.services.get(ServiceKind.JELLYFIN)
    if probe is None:
        return ServiceOrigin.EXISTING, jellyfin.base_url
    return probe.origin, probe.base_url or jellyfin.base_url


def _step(step: JellyfinStep, status: StepStatus) -> SetupStep:
    return SetupStep(key=step.value, status=status)


#: 路徑上不能出現的字元（Windows 最嚴，brief §4.5）。中日文照留，它們在兩種檔案系統都合法。
_UNSAFE_IN_PATH = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def _berth_path(library_name: str, library_root: str) -> str:
    slug = _UNSAFE_IN_PATH.sub("-", library_name).strip(" .-").lower() or "berth"
    return f"{library_root.rstrip('/')}/{slug}"


def _library_view(library: SetupLibrary, library_root: str) -> LibraryView:
    path = _berth_path(library.name, library_root)
    return LibraryView(
        name=library.name,
        collection_type=library.collection_type,
        locations=tuple(library.locations),
        metadata_fetchers=tuple(library.metadata_fetchers),
        uses_tvdb=any(TVDB_MARKER in name.lower() for name in library.metadata_fetchers),
        berth_path=path,
        has_berth_path=path in library.locations,
    )


def _message(exc: BaseException) -> str:
    return str(exc) or type(exc).__name__
