"""測試與前端演練用的 Jellyfin 替身。

這不是「回固定值」的 stub，而是一台**會記得自己被做過什麼**的假 Jellyfin：初始精靈的
狀態、媒體庫、API key、插件、重啟。實測到的難搞行為刻意複製進來，因為 services 的冪等
就是靠它們才測得出來（全部見 brief §20.7）：

- 同名媒體庫不會被拒，會長出 `Movies2` 指向同一個路徑。
- 同一條路徑加兩次，媒體庫就有兩個一樣的 location。
- `POST /Auth/Keys` 不檢查重複，同一個 `AppName` 會有第二把。
- `POST /Startup/User` 之前沒有 `GET /Startup/User` 會失敗。
- 第一個使用者已經有密碼時，`POST /Startup/User` 回 403——精靈第 3 步的重試靠它才測得出來
  （12.0 起，brief §20.9、票 14b）。
- 初始精靈完成之後，管理員端點沒有 token 就是 401。
- `GET /Items` 沒有路徑篩選：`parentId=<library>&recursive=true` 回的是那個媒體庫路徑底下的全部。
- **API key 帶 `parentId` 替使用者查時不套媒體庫權限**（12.1.0 實測，研究 library-browsing.md §2）：
  `library_page` / `library_index` 對他沒有權限的媒體庫照樣回內容。權限只在 `user_views` 上成立——
  「Berth 自己擋」的測試要靠這台替身不替它擋，才證明得了是 Berth 擋的。
- **停用的帳號照樣代讀得到**：`user_views` 不看停用，只有 `user_policy` 說得出來（同上）。
- **圖片匿名可取、`tag` 不驗證**（研究 §6）：`image` 不要 token，錯的 tag 一樣回圖。
- **標記已看 / 未看由 Jellyfin 自己查可見性**（研究 §5）：這位使用者看不到的 item 回 404、沒有寫入。
  對 Series 標記遞迴到底下每一集，Series 自己的紀錄由它的集算出來（`PlayedPercentage`、
  `UnplayedItemCount`）；標記會把看到一半的位置歸零。停用的帳號照樣寫得進去（研究 §2）。
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import replace

from berth.adapters.http import AuthFailedError, NotFoundError, ProtocolMismatchError
from berth.adapters.jellyfin import (
    ITEM_SERIES,
    JellyfinApiKey,
    JellyfinAuth,
    JellyfinImage,
    JellyfinItem,
    JellyfinLibrary,
    JellyfinPage,
    JellyfinPolicy,
    JellyfinPublicInfo,
    JellyfinTask,
    JellyfinUserData,
    JellyfinView,
    NewLibrary,
    TypeOption,
)
from berth.domain import CollectionType

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

#: 內建的「重新掃描媒體庫」（實測 12.0.0 的 id 與 key，brief §20.1）。
LIBRARY_SCAN_TASK = JellyfinTask(
    id="7738148ffcd07979c7ceb148e06b3aed", key="RefreshLibrary", name="Scan Media Library"
)


class FakeJellyfinClient:
    def __init__(
        self,
        *,
        base_url: str = "http://jellyfin:8096",
        #: 預設是支援下限之上的那一條線（`deploy/` 釘的 12.1，brief §19）。低於 12.0 的值
        #: 讓精靈與健康檢查的版本閘門測得出來。
        version: str = "12.1.0",
        server_name: str = "jellyfin",
        startup_wizard_completed: bool = False,
        #: 已存在的管理員帳密。`authenticate` 給它 `IsAdministrator=true`。
        admin: tuple[str, str] | None = None,
        #: 其餘使用者（帳號 → 密碼），一律非管理員。票 07 的角色判定靠它才測得出來。
        users: dict[str, str] | None = None,
        #: 帳號 → 他看得到的媒體庫 `item_id`。沒列的帳號看得到全部（`EnableAllFolders`）。
        folders: dict[str, tuple[str, ...]] | None = None,
        libraries: tuple[JellyfinLibrary, ...] = (),
        api_keys: tuple[JellyfinApiKey, ...] = (),
        tasks: tuple[JellyfinTask, ...] = (),
        #: 每一次呼叫都丟這個例外。用來演練「服務不在」「連不上」這類判定。
        error: Exception | None = None,
        #: 這台 Jellyfin 掛得到的路徑前綴。`None` = 與 Berth 看到的一樣（正常部署）。
        visible_roots: tuple[str, ...] | None = None,
        #: 掃描過的媒體樹（`GET /Items`）。測試擺出「Jellyfin 已經掃到了什麼」。
        items: tuple[JellyfinItem, ...] = (),
        #: 只有 `POST /Library/Media/Updated` 丟這個例外。「通知失敗不擋入庫」要它才測得出來。
        notify_error: Exception | None = None,
        #: `(item id, 圖片類型)` → 那張圖。沒列的是 404。
        images: dict[tuple[str, str], JellyfinImage] | None = None,
        #: 帳號 → 他看過的集與電影的 item id。Series 的紀錄由它的集算出來，不在這裡。
        played: dict[str, set[str]] | None = None,
        #: 帳號 → 看到一半的集與電影 → 看到幾 %。
        positions: dict[str, dict[str, float]] | None = None,
    ) -> None:
        self.base_url = base_url
        self.version = version
        self.server_name = server_name
        self.startup_wizard_completed = startup_wizard_completed
        self.admin = admin
        self.users = dict(users or {})
        self.folders = dict(folders or {})
        #: 在 Jellyfin 被停用的帳號名。測試在登入之後才加進來，演「帳號被停用」。
        self.disabled: set[str] = set()
        self.libraries_ = list(libraries)
        self.api_keys_ = list(api_keys)
        self.tasks_ = list(tasks)
        self.error = error
        self.visible_roots = visible_roots
        self.items_ = list(items)
        self.notify_error = notify_error
        self.images = dict(images or {})
        self.played = {name: set(ids) for name, ids in (played or {}).items()}
        self.positions = {name: dict(rows) for name, rows in (positions or {}).items()}

        #: 每一次 `notify_paths` 收到的路徑，攤平。
        self.notified: list[str] = []
        #: 每一次 `items` 問的是哪個媒體庫、哪幾種型別。「還沒到時間就不問」靠它斷言。
        self.item_queries: list[tuple[str, tuple[str, ...]]] = []
        #: 每一次 `run_task` 觸發的任務 id。
        self.tasks_run: list[str] = []
        #: 每一次 `user_views` / `user_policy` 問的是誰。快取有沒有擋下重複的問題靠它斷言。
        self.view_queries: list[str] = []
        self.policy_queries: list[str] = []
        #: 每一次帶 `parentId` 替使用者查的 `(user_id, library_id)`（`library_page` 與
        #: `library_index` 都算）。「沒有轉發給 Jellyfin」就是這裡記不到那一次。
        self.browse_queries: list[tuple[str, str]] = []
        #: 每一次 `image` 收到的整組參數：`(item_id, image_type, tag, fill_width, fill_height,
        #: quality)`。尺寸白名單翻成了哪幾個數字靠它斷言。
        self.image_queries: list[tuple[str, str, str, int, int, int]] = []
        #: 每一次 `mark_played` 收到的 `(user_id, item_id, played)`，被 404 擋下的也記。
        self.played_queries: list[tuple[str, str, bool]] = []
        self.token = ""
        self.culture: tuple[str, str, str] | None = None
        self.remote_access: bool | None = None
        #: 每一次 `create_library` 收到的整份請求，測試用來斷言寫進去的選項。
        self.created: list[NewLibrary] = []
        self._default_user_read = False

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

    async def create_startup_user(self, name: str, password: str) -> bool:
        self._checkpoint()
        if not self._default_user_read:
            # 真的 Jellyfin 在這裡回 500「Sequence contains no elements」（brief §20.7）。
            raise ProtocolMismatchError("POST /Startup/User: 500 Sequence contains no elements")
        if self.admin is not None and self.admin[1]:
            # 12.0 起：第一個使用者已經有密碼就回 403，密碼不動（brief §20.9）。
            return False
        self.admin = (name, password)
        return True

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

    async def validate_path(self, path: str, *, is_file: bool = True) -> bool:
        """`visible_roots` 是這台 Jellyfin 掛得到的容器路徑。

        `None` 代表「與 Berth 掛同一個宿主目錄在同一個容器路徑」，也就是 brief §16.4 那條
        硬規則成立的樣子；給了清單就是少了掛載的那一台，用來演練檢查三的失敗。
        """
        self._checkpoint()
        if self.visible_roots is None:
            return True
        return any(path.startswith(root) for root in self.visible_roots)

    # --- 排程任務 ---

    async def scheduled_tasks(self) -> tuple[JellyfinTask, ...]:
        self._checkpoint(always=True)
        return tuple(self.tasks_)

    async def run_task(self, task_id: str) -> None:
        self._checkpoint(always=True)
        if task_id not in {task.id for task in self.tasks_}:
            raise ProtocolMismatchError(f"POST /ScheduledTasks/Running/{task_id}: 404")
        self.tasks_run.append(task_id)

    # --- 入庫之後 ---

    async def notify_paths(self, paths: Sequence[str]) -> None:
        self._checkpoint(always=True)
        if self.notify_error is not None:
            raise self.notify_error
        self.notified.extend(paths)

    async def items(self, library_id: str, item_types: Sequence[str]) -> tuple[JellyfinItem, ...]:
        """照媒體庫的路徑篩——`parentId=<library>&recursive=true` 在真的 Jellyfin 就是這個意思。"""
        self._checkpoint()
        self.item_queries.append((library_id, tuple(item_types)))
        library = next((row for row in self.libraries_ if row.item_id == library_id), None)
        if library is None:
            return ()
        return tuple(
            item
            for item in self.items_
            if item.type in item_types
            and any(item.path.startswith(f"{location}/") for location in library.locations)
        )

    # --- 替某一位使用者瀏覽 ---

    async def user_views(self, user_id: str) -> tuple[JellyfinView, ...]:
        self._checkpoint(always=True)
        self.view_queries.append(user_id)
        return tuple(
            JellyfinView(id=row.item_id, name=row.name, collection_type=row.collection_type)
            for row in self._folders_of(self._username(user_id))
        )

    async def user_policy(self, user_id: str) -> JellyfinPolicy:
        self._checkpoint(always=True)
        self.policy_queries.append(user_id)
        return JellyfinPolicy(is_disabled=self._username(user_id) in self.disabled)

    async def library_page(
        self, *, user_id: str, library_id: str, item_type: str, start: int, limit: int
    ) -> JellyfinPage:
        titles = self._browse(user_id, library_id, item_type)
        # 牆的查詢一向不驗 id（媒體庫測試用一個替身不認得的觀看者）：不認得的人就是什麼都沒看過。
        name = self._account(user_id) or ""
        return JellyfinPage(
            items=tuple(
                replace(item, user_data=self._user_data(name, item))
                for item in titles[start : start + limit]
            ),
            total=len(titles),
        )

    async def library_index(
        self, *, user_id: str, library_id: str, item_type: str
    ) -> tuple[JellyfinItem, ...]:
        return self._browse(user_id, library_id, item_type)

    def _browse(self, user_id: str, library_id: str, item_type: str) -> tuple[JellyfinItem, ...]:
        """**不看 `user_id` 的權限**：真的 Jellyfin 在 API key 帶 `parentId` 時也不看
        （研究 §2）。"""
        self._checkpoint(always=True)
        self.browse_queries.append((user_id, library_id))
        library = next((row for row in self.libraries_ if row.item_id == library_id), None)
        if library is None:
            return ()
        titles = [item for item in self.items_ if item.type == item_type and _under(item, library)]
        # `SortName` 是小寫化的名稱（研究 §3.1）；替身不去掉冠詞。
        return tuple(sorted(titles, key=lambda item: (item.name.casefold(), item.id)))

    async def mark_played(self, *, user_id: str, item_id: str, played: bool) -> JellyfinUserData:
        self._checkpoint(always=True)
        self.played_queries.append((user_id, item_id, played))
        name = self._username(user_id)
        item = next((row for row in self.items_ if row.id == item_id), None)
        if item is None or not self._visible(name, item):
            method = "POST" if played else "DELETE"
            raise NotFoundError(f"{method} /UserPlayedItems/{item_id}: 404")
        episodes = self._episodes(item)
        seen = self.played.setdefault(name, set())
        positions = self.positions.setdefault(name, {})
        for target in episodes or (item,):
            if played:
                seen.add(target.id)
            else:
                seen.discard(target.id)
            positions.pop(target.id, None)
        return self._user_data(name, item)

    def _folders_of(self, name: str) -> list[JellyfinLibrary]:
        """這個帳號看得到的媒體庫（沒列在 `folders` 的看得到全部）。"""
        allowed = self.folders.get(name)
        return [row for row in self.libraries_ if allowed is None or row.item_id in allowed]

    def _visible(self, name: str, item: JellyfinItem) -> bool:
        return any(_under(item, library) for library in self._folders_of(name))

    def _episodes(self, item: JellyfinItem) -> tuple[JellyfinItem, ...]:
        if item.type != ITEM_SERIES:
            return ()
        return tuple(row for row in self.items_ if row.series_id == item.id)

    def _user_data(self, name: str, item: JellyfinItem) -> JellyfinUserData:
        """劇集的紀錄由底下的集算：看過的比例與沒看的集數（12.1.0 錄的 `UserData`，研究 §5）。"""
        seen = self.played.get(name, set())
        if item.type != ITEM_SERIES:
            return JellyfinUserData(
                played=item.id in seen,
                played_percentage=self.positions.get(name, {}).get(item.id, 0.0),
                unplayed_item_count=None,
            )
        episodes = self._episodes(item)
        if not episodes:
            return JellyfinUserData(
                played=item.id in seen, played_percentage=0.0, unplayed_item_count=0
            )
        unplayed = sum(episode.id not in seen for episode in episodes)
        return JellyfinUserData(
            played=unplayed == 0,
            played_percentage=100 * (len(episodes) - unplayed) / len(episodes),
            unplayed_item_count=unplayed,
        )

    # --- 圖片 ---

    async def image(
        self,
        item_id: str,
        image_type: str,
        *,
        tag: str,
        fill_width: int,
        fill_height: int,
        quality: int,
    ) -> JellyfinImage:
        """匿名可取：不看 token（研究 §6）。`tag` 錯了一樣回圖。"""
        self._checkpoint(elevated=False)
        self.image_queries.append((item_id, image_type, tag, fill_width, fill_height, quality))
        found = self.images.get((item_id, image_type))
        if found is None:
            raise NotFoundError(f"GET /Items/{item_id}/Images/{image_type}: no such image")
        return found

    def _account(self, user_id: str) -> str | None:
        accounts = [*self.users, *([self.admin[0]] if self.admin else [])]
        return next((name for name in accounts if _user_id(name) == user_id), None)

    def _username(self, user_id: str) -> str:
        """id 反查帳號名。不認得的 id 在真的 Jellyfin 是 4xx，client 翻成協定不符。"""
        name = self._account(user_id)
        if name is None:
            raise ProtocolMismatchError(f"GET /Users/{user_id}: 404")
        return name

    async def aclose(self) -> None:
        return None

    def _checkpoint(self, *, elevated: bool = True, always: bool = False) -> None:
        """每一支端點的共同前置：注入的錯誤，以及要不要 token。

        `elevated=True` 的端點在初始精靈跑完之前匿名可用（`FirstTimeSetupOrElevated`），
        跑完之後就要 token；`always=True` 的（`RequiresElevation`）永遠要。
        """
        if self.error is not None:
            raise self.error
        if elevated and (always or self.startup_wizard_completed) and not self.token:
            raise AuthFailedError("401 requires elevation")


def _auth(username: str, *, is_administrator: bool) -> JellyfinAuth:
    """每個帳號一個穩定的假 id，兩個人登入才會是 `users` 表的兩列。"""
    return JellyfinAuth(
        token=f"token-for-{username}",
        user_id=_user_id(username),
        name=username,
        server_id="4e71f8d8bc324291b6e6c5a4f3fa8825",
        is_administrator=is_administrator,
    )


def _under(item: JellyfinItem, library: JellyfinLibrary) -> bool:
    """item 在不在這個媒體庫的某一條路徑底下（`parentId=<library>&recursive=true` 的意思）。"""
    return any(item.path.startswith(f"{location}/") for location in library.locations)


def _user_id(username: str) -> str:
    return hashlib.sha256(username.encode()).hexdigest()[:32]
