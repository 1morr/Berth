"""測試與前端演練用的 Jellyfin 替身。

這不是「回固定值」的 stub，而是一台**會記得自己被做過什麼**的假 Jellyfin：初始精靈的
狀態、媒體庫、API key、插件、重啟。實測到的難搞行為刻意複製進來，因為 services 的冪等
就是靠它們才測得出來（全部見 brief §20.7）：

- 同名媒體庫不會被拒，會長出 `Movies2` 指向同一個路徑。
- 同一條路徑加兩次，媒體庫就有兩個一樣的 location。
- `POST /Auth/Keys` 不檢查重複，同一個 `AppName` 會有第二把。
- `POST /Startup/User` 之前沒有 `GET /Startup/User` 會失敗。
- 初始精靈完成之後，管理員端點沒有 token 就是 401。
- 重啟後有一段時間所有端點回 503。
"""

from __future__ import annotations

import hashlib
from dataclasses import replace

from berth.adapters.http import (
    AuthFailedError,
    ProtocolMismatchError,
    ServiceBusyError,
    ServiceUnavailableError,
)
from berth.adapters.jellyfin import (
    JellyfinApiKey,
    JellyfinAuth,
    JellyfinLibrary,
    JellyfinPlugin,
    JellyfinPublicInfo,
    JellyfinRepository,
    JellyfinTask,
    NewLibrary,
    TypeOption,
)
from berth.domain import CollectionType

#: `GET /Repositories` 在乾淨安裝上的內容（實測 10.11.11）。
JELLYFIN_STABLE_REPOSITORY = JellyfinRepository(
    name="Jellyfin Stable",
    url="https://repo.jellyfin.org/files/plugin/manifest.json",
    enabled=True,
)

#: 這台伺服器裝了哪些 fetcher（`GET /Libraries/AvailableOptions`，實測 10.11.11）。
AVAILABLE_TYPE_OPTIONS: dict[CollectionType, tuple[TypeOption, ...]] = {
    CollectionType.MOVIES: (
        TypeOption(
            type="Movie",
            metadata_fetchers=("TheMovieDb", "The Open Movie Database"),
            image_fetchers=(
                "TheMovieDb",
                "The Open Movie Database",
                "Embedded Image Extractor",
                "Screen Grabber",
            ),
        ),
    ),
    CollectionType.TVSHOWS: (
        TypeOption(
            type="Series",
            metadata_fetchers=("TheMovieDb", "The Open Movie Database"),
            image_fetchers=("TheMovieDb",),
        ),
        TypeOption(
            type="Season", metadata_fetchers=("TheMovieDb",), image_fetchers=("TheMovieDb",)
        ),
        TypeOption(
            type="Episode",
            metadata_fetchers=("TheMovieDb", "The Open Movie Database"),
            image_fetchers=(
                "TheMovieDb",
                "The Open Movie Database",
                "Embedded Image Extractor",
                "Screen Grabber",
            ),
        ),
    ),
}

#: MergeVersions 裝好並重啟後出現的兩個排程任務（實測 id，brief §20.7）。
MERGE_VERSIONS_TASKS = (
    JellyfinTask(
        id="dcaf151dd1af25aefe775c58e214477e", key="MergeEpisodesTask", name="Merge All Episodes"
    ),
    JellyfinTask(
        id="fd957c84b0cfc2380becf2893e4b76fc", key="MergeMoviesTask", name="Merge All Movies"
    ),
)


class FakeJellyfinClient:
    def __init__(
        self,
        *,
        base_url: str = "http://jellyfin:8096",
        version: str = "10.11.11",
        server_name: str = "jellyfin",
        startup_wizard_completed: bool = False,
        #: 已存在的管理員帳密。`authenticate` 給它 `IsAdministrator=true`。
        admin: tuple[str, str] | None = None,
        #: 其餘使用者（帳號 → 密碼），一律非管理員。票 07 的角色判定靠它才測得出來。
        users: dict[str, str] | None = None,
        libraries: tuple[JellyfinLibrary, ...] = (),
        api_keys: tuple[JellyfinApiKey, ...] = (),
        plugins: tuple[JellyfinPlugin, ...] = (),
        tasks: tuple[JellyfinTask, ...] = (),
        #: 每一次呼叫都丟這個例外。用來演練「服務不在」「連不上」這類判定。
        error: Exception | None = None,
        #: `install_package` 前幾次失敗（實測會遇到 TLS 中斷回 500）。
        install_failures: int = 0,
        #: 重啟後有幾次呼叫回 503。0 代表重啟瞬間就好了。
        busy_after_restart: int = 0,
        #: `restart()` 在回應送出去之前就把連線切了（實測遇得到，brief §20.7）。
        drop_on_restart: bool = False,
    ) -> None:
        self.base_url = base_url
        self.version = version
        self.server_name = server_name
        self.startup_wizard_completed = startup_wizard_completed
        self.admin = admin
        self.users = dict(users or {})
        self.libraries_ = list(libraries)
        self.api_keys_ = list(api_keys)
        self.plugins_ = list(plugins)
        self.tasks_ = list(tasks)
        self.error = error
        self.install_failures = install_failures
        self.busy_after_restart = busy_after_restart
        self.drop_on_restart = drop_on_restart

        self.repositories_ = [JELLYFIN_STABLE_REPOSITORY]
        #: 插件庫裡看得到的套件。加了 repository 才長出來。
        self.packages_: dict[str, tuple[str, ...]] = {}
        self.token = ""
        self.restarts = 0
        self.culture: tuple[str, str, str] | None = None
        self.remote_access: bool | None = None
        self.installs: list[str] = []
        #: 每一次 `create_library` 收到的整份請求，測試用來斷言寫進去的選項。
        self.created: list[NewLibrary] = []
        self._busy = 0
        self._default_user_read = False
        self._tasks_after_restart: list[JellyfinTask] = []

    def use_token(self, token: str) -> None:
        self.token = token

    async def public_info(self) -> JellyfinPublicInfo:
        self._checkpoint(elevated=False)
        return JellyfinPublicInfo(
            server_name=self.server_name,
            version=self.version,
            startup_wizard_completed=self.startup_wizard_completed,
        )

    # --- 初始精靈 ---

    async def start_configuration(
        self, *, ui_culture: str, metadata_country_code: str, preferred_metadata_language: str
    ) -> None:
        self._checkpoint()
        self.culture = (ui_culture, metadata_country_code, preferred_metadata_language)

    async def ensure_default_user(self) -> str:
        self._checkpoint()
        self._default_user_read = True
        return "root"

    async def create_startup_user(self, name: str, password: str) -> None:
        self._checkpoint()
        if not self._default_user_read:
            # 真的 Jellyfin 在這裡回 500「Sequence contains no elements」（brief §20.7）。
            raise ProtocolMismatchError("POST /Startup/User: 500 Sequence contains no elements")
        self.admin = (name, password)

    async def set_remote_access(self, *, enabled: bool) -> None:
        self._checkpoint()
        self.remote_access = enabled

    async def complete_startup(self) -> None:
        self._checkpoint()
        self.startup_wizard_completed = True

    # --- 憑證 ---

    async def authenticate(self, username: str, password: str) -> JellyfinAuth:
        self._checkpoint(elevated=False)
        if self.admin is not None and (username, password) == self.admin:
            return _auth(username, is_administrator=True)
        if self.users.get(username) == password and password != "":
            return _auth(username, is_administrator=False)
        # 帳號不存在與密碼錯誤在真的 Jellyfin 也是同一個 401。
        raise AuthFailedError("POST /Users/AuthenticateByName: 401")

    async def api_keys(self) -> tuple[JellyfinApiKey, ...]:
        self._checkpoint(always=True)
        return tuple(self.api_keys_)

    async def create_api_key(self, app: str) -> None:
        self._checkpoint(always=True)
        # 不檢查重複：同一個 AppName 按兩次就有兩把（實測）。
        self.api_keys_.append(
            JellyfinApiKey(app_name=app, access_token=f"key-{app.lower()}-{len(self.api_keys_)}")
        )

    # --- 媒體庫 ---

    async def libraries(self) -> tuple[JellyfinLibrary, ...]:
        self._checkpoint()
        return tuple(self.libraries_)

    async def available_type_options(
        self, collection_type: CollectionType
    ) -> tuple[TypeOption, ...]:
        self._checkpoint()
        return AVAILABLE_TYPE_OPTIONS[collection_type]

    async def create_library(self, library: NewLibrary) -> None:
        self._checkpoint()
        self.created.append(library)
        # 同名不會被拒，Jellyfin 自己改名（實測回 204 並建出 `Movies2`）。
        taken = {existing.name for existing in self.libraries_}
        name = library.name
        suffix = 2
        while name in taken:
            name = f"{library.name}{suffix}"
            suffix += 1
        self.libraries_.append(
            JellyfinLibrary(
                name=name,
                item_id=f"item-{len(self.libraries_)}",
                collection_type=library.collection_type.value,
                locations=(library.path,),
                type_options=library.type_options,
            )
        )

    async def add_library_path(self, library_name: str, path: str) -> None:
        self._checkpoint()
        for index, existing in enumerate(self.libraries_):
            if existing.name == library_name:
                # 重複的路徑不會被去掉，location 就這樣出現兩次（實測）。
                self.libraries_[index] = replace(existing, locations=(*existing.locations, path))
                return
        raise ProtocolMismatchError(f"POST /Library/VirtualFolders/Paths: 404 {library_name}")

    # --- 插件與排程任務 ---

    async def repositories(self) -> tuple[JellyfinRepository, ...]:
        self._checkpoint(always=True)
        return tuple(self.repositories_)

    async def set_repositories(self, repositories: tuple[JellyfinRepository, ...]) -> None:
        self._checkpoint(always=True)
        self.repositories_ = list(repositories)
        # 加了 repository，套件才在插件庫裡看得到。
        self.packages_.setdefault("Merge Versions", ("10.11.0.1",))

    async def package_versions(self, name: str) -> tuple[str, ...]:
        self._checkpoint(always=True)
        return self.packages_.get(name, ())

    async def install_package(self, name: str, *, assembly_guid: str) -> None:
        self._checkpoint(always=True)
        self.installs.append(name)
        if self.install_failures > 0:
            self.install_failures -= 1
            raise ProtocolMismatchError(f"POST /Packages/Installed/{name}: 500")
        self.plugins_.append(
            JellyfinPlugin(
                id=assembly_guid.replace("-", "").lower(), name=name, version="10.11.0.1"
            )
        )
        # 排程任務要重啟之後才出現。
        self._tasks_after_restart = list(MERGE_VERSIONS_TASKS)

    async def plugins(self) -> tuple[JellyfinPlugin, ...]:
        self._checkpoint(always=True)
        return tuple(self.plugins_)

    async def restart(self) -> None:
        self._checkpoint(always=True)
        self.restarts += 1
        self._busy = self.busy_after_restart
        self.tasks_.extend(self._tasks_after_restart)
        self._tasks_after_restart = []
        if self.drop_on_restart:
            # 伺服器已經在重啟了，只是回應沒送到。
            raise ServiceUnavailableError("POST /System/Restart: connection dropped")

    async def scheduled_tasks(self) -> tuple[JellyfinTask, ...]:
        self._checkpoint(always=True)
        return tuple(self.tasks_)

    async def aclose(self) -> None:
        return None

    def _checkpoint(self, *, elevated: bool = True, always: bool = False) -> None:
        """每一支端點的共同前置：注入的錯誤、重啟後的 503、以及要不要 token。

        `elevated=True` 的端點在初始精靈跑完之前匿名可用（`FirstTimeSetupOrElevated`），
        跑完之後就要 token；`always=True` 的（`RequiresElevation`）永遠要。
        """
        if self.error is not None:
            raise self.error
        if self._busy > 0:
            self._busy -= 1
            raise ServiceBusyError("503 still loading")
        if elevated and (always or self.startup_wizard_completed) and not self.token:
            raise AuthFailedError("401 requires elevation")


def _auth(username: str, *, is_administrator: bool) -> JellyfinAuth:
    """每個帳號一個穩定的假 id，兩個人登入才會是 `users` 表的兩列。"""
    user_id = hashlib.sha256(username.encode()).hexdigest()[:32]
    return JellyfinAuth(
        token=f"token-for-{username}",
        user_id=user_id,
        name=username,
        server_id="4e71f8d8bc324291b6e6c5a4f3fa8825",
        is_administrator=is_administrator,
    )
