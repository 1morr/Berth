"""精靈第 3 步：Jellyfin（plan §9.3 第 3 步、§9.4、§9.5）。

兩條路徑共用同一份狀態形狀（`SetupJellyfin`）：

- **套件內**：`bootstrap_jellyfin` 跑完 plan §9.4 的七步。每一步都冪等——媒體庫先看再建、
  API key 先列再建。重按只會把已經對的那幾步標成 `skipped`。
- **既有**：`connect_jellyfin` 以管理員帳密登入並建立 API key、列出媒體庫；`add_berth_path`
  為選定的媒體庫**加**一條路徑。

**第一步是版本閘門**（brief §16.4、§19、§20.9）：低於 Jellyfin 12.0 就停在那裡，不往下做。
10.x 上同一集的兩個版本是兩個重複的條目，要靠 MergeVersions 插件；12.0 起原生合併，所以
Berth 只支援 12 以上，序列裡也不再有「裝插件」與「重啟」那兩步（票 14b）。

既有 Jellyfin 的紅線（brief §16.4）：本檔絕不自動建立媒體庫、不改既有 `LibraryOptions`、
不刪除任何東西——adapter 的介面上根本沒有那些方法。

每一步在做之前先把自己標成 `running` 並 commit，所以前端輪詢 `GET /api/setup/jellyfin`
就看得到序列走到哪裡，不必為了進度另外開一條通道。
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.fs import ensure_directory
from berth.adapters.http import ServiceError
from berth.adapters.jellyfin import (
    JellyfinClient,
    JellyfinLibrary,
    NewLibrary,
    TypeOption,
    unsupported_message,
    version_supported,
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
from berth.services.steps import StepView, step_views

#: `POST /Auth/Keys?app=` 用的名字。也是重按時辨認「這把是我建的」的依據。
API_KEY_APP = "Berth"

#: plan §9.4 第 2 步。「精靈可改」是之後的事，M0 用固定值。
UI_CULTURE = "zh-TW"
METADATA_LANGUAGE = "zh-TW"
METADATA_COUNTRY = "TW"

#: brief §10 的決定：第一階段只用 TMDB。設定裡沒寫的媒體庫落回這個。
DEFAULT_METADATA_FETCHER = "TheMovieDb"

#: 媒體庫掛了 TVDB 的 metadata fetcher 就警告（brief §16.4）。比對小寫子字串，因為名字由
#: 插件自己決定（官方插件是 `TheTVDB`）。
TVDB_MARKER = "tvdb"


class StepFailedError(Exception):
    """這一步做不下去，而且原因不是外部服務丟出來的例外。

    `detail` 是失敗那一刻仍然量得到的實測值（版本太舊時就是它的版本號）：那一行要同時說得出
    「這台是什麼」與「為什麼不行」。
    """

    def __init__(self, message: str, *, detail: str = "") -> None:
        super().__init__(message)
        self.detail = detail


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
    #: 這台 Jellyfin 上一次報的版本號（`public_info` 那一步的實測值）。還沒問過就是空字串。
    version: str
    #: 版本夠不夠新（brief §16.4）。**還沒問過時是 `True`**：那一格是「尚未取得」而不是紅燈。
    version_supported: bool


async def read_jellyfin_status(session: AsyncSession) -> JellyfinSetupStatus:
    """不連線，只把存下來的狀態攤成 UI 的形狀。輪詢進度也走這一支。"""
    setup = await read_settings(session, SetupSettings)
    jellyfin = await read_settings(session, JellyfinSettings)
    paths = await read_settings(session, PathSettings)
    origin, base_url = _target(setup, jellyfin)
    version = _measured_version(setup)
    return JellyfinSetupStatus(
        origin=origin,
        base_url=base_url,
        api_key_present=bool(jellyfin.api_key),
        steps=step_views(setup.jellyfin.steps),
        libraries=tuple(_library_view(row, paths.library_root) for row in setup.jellyfin.libraries),
        version=version,
        version_supported=not version or version_supported(version),
    )


async def bootstrap_jellyfin(
    session: AsyncSession, factory: ServiceClientFactory
) -> JellyfinSetupStatus:
    """套件內路徑：跑完 plan §9.4 的七步。重按只補做還沒做的那幾步。"""
    return await _run(session, factory, tuple(JellyfinStep))


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
        path = berth_path(library_name, paths.library_root)
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
    credentials: tuple[str, str] | None = None,
) -> JellyfinSetupStatus:
    setup = await read_settings(session, SetupSettings)
    jellyfin = await read_settings(session, JellyfinSettings)
    paths = await read_settings(session, PathSettings)
    _, base_url = _target(setup, jellyfin)

    client = factory.jellyfin(base_url, token=jellyfin.api_key)
    runner = _Runner(client, setup.admin, jellyfin, paths)
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

    await _remember(session, libraries=runner.libraries)
    jellyfin.base_url = base_url
    jellyfin.api_key = runner.api_key or jellyfin.api_key
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
    session: AsyncSession, *, libraries: tuple[JellyfinLibrary, ...] | None = None
) -> None:
    setup = await read_settings(session, SetupSettings)
    if libraries is not None:
        setup.jellyfin.libraries = [
            SetupLibrary(
                name=library.name,
                item_id=library.item_id,
                collection_type=library.collection_type,
                locations=list(library.locations),
                metadata_fetchers=sorted(
                    {name for option in library.type_options for name in option.metadata_fetchers}
                ),
            )
            for library in libraries
        ]
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
    ) -> None:
        self._client = client
        self._jellyfin = jellyfin
        self._paths = paths
        self._credentials = (admin.username, admin.password)
        self._token = jellyfin.api_key
        self._fresh = False
        self.api_key = jellyfin.api_key
        #: `None` 代表這一輪沒讀到媒體庫；不要拿它覆寫存下來的清單。
        self.libraries: tuple[JellyfinLibrary, ...] | None = None

    def sign_in_as(self, username: str, password: str) -> None:
        """既有 Jellyfin 的管理員帳密，與 Berth 自己的那一組無關。"""
        self._credentials = (username, password)
        self._token = ""

    async def run(self, step: JellyfinStep) -> SetupStep:
        try:
            status, detail = await _ACTIONS[step](self)
        except StepFailedError as exc:
            # 量得到的實測值照樣帶著：版本太舊那一行要同時說出「它是 10.11.11」與「要 12 以上」。
            return SetupStep(
                key=step.value, status=StepStatus.FAILED, detail=exc.detail, error=_message(exc)
            )
        except (ServiceError, OSError) as exc:
            return SetupStep(key=step.value, status=StepStatus.FAILED, error=_message(exc))
        return SetupStep(key=step.value, status=status, detail=detail)

    async def refresh_libraries(self) -> None:
        """收尾時再讀一次媒體庫。讀不到就維持 `None`，讓存下來的清單原封不動。"""
        try:
            self.libraries = await self._client.libraries()
        except ServiceError:
            return

    # --- 七個步驟 ---

    async def _public_info(self) -> tuple[StepStatus, str]:
        info = await self._client.public_info()
        if not info.supported:
            # 版本閘門就在第一步，後面的步驟因此一步都不會跑（brief §16.4、§19）。
            raise StepFailedError(unsupported_message(info.version), detail=info.version)
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
        # 12.0 起「第一個使用者已經有密碼」回 403，而那是**已經設過了**不是失敗：第 3 步成功、
        # 之後某一步失敗、Jellyfin 沒重啟時按重試就走到這裡（brief §20.9、票 14b）。密碼對不對
        # 由第 7 步的登入驗證——那一步本來就要拿同一組帳密換 API key。
        created = await self._client.create_startup_user(username, password)
        return (StepStatus.OK if created else StepStatus.SKIPPED), username

    async def _libraries(self) -> tuple[StepStatus, str]:
        if not self._fresh:
            # 初始精靈跑完之後，`/Library/VirtualFolders` 就要管理員憑證了。
            await self._authenticate()
        existing = {library.name for library in await self._client.libraries()}
        created: list[str] = []
        for bundled in BUNDLED_LIBRARIES:
            # 與既有媒體庫的 Berth 路徑同一支函式：兩套算法遲早會分岔，而分岔的症狀是
            # `has_berth_path` 對 Berth 自己建的路徑報 false（`test_bundled_paths_...` 釘住）。
            path = berth_path(bundled.name, self._paths.library_root)
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


_ACTIONS: dict[JellyfinStep, Callable[[_Runner], Awaitable[tuple[StepStatus, str]]]] = {
    JellyfinStep.PUBLIC_INFO: _Runner._public_info,
    JellyfinStep.CONFIGURATION: _Runner._configuration,
    JellyfinStep.ADMIN_USER: _Runner._admin_user,
    JellyfinStep.LIBRARIES: _Runner._libraries,
    JellyfinStep.REMOTE_ACCESS: _Runner._remote_access,
    JellyfinStep.COMPLETE: _Runner._complete,
    JellyfinStep.API_KEY: _Runner._api_key,
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


def _measured_version(setup: SetupSettings) -> str:
    """上一輪 `public_info` 量到的版本號。**失敗的那一輪也算**：版本太舊時這一格就是理由。"""
    return next(
        (
            row.detail
            for row in setup.jellyfin.steps
            if row.key == JellyfinStep.PUBLIC_INFO.value and row.detail
        ),
        "",
    )


#: 路徑上不能出現的字元（Windows 最嚴，brief §4.5）。中日文照留，它們在兩種檔案系統都合法。
_UNSAFE_IN_PATH = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def library_slug(library_name: str) -> str:
    """媒體庫名 → 路徑與 category 用的 slug。中日文照留（brief §4.5）。

    第 7 步的 Route 用同一支：Route 的 complete 子目錄、qBittorrent category 與這個媒體庫的
    Berth 路徑要對得起來，兩套算法遲早會分岔。
    """
    return _UNSAFE_IN_PATH.sub("-", library_name).strip(" .-").lower() or "berth"


def berth_path(library_name: str, library_root: str) -> str:
    """「加入 Berth 路徑」加的那一條：`<library root>/<slug>`（CONTEXT.md）。

    第 7 步的 Route 也用這一支決定「這個媒體庫的 Berth 路徑是哪一條」，兩邊算出來的字串
    必須一模一樣，否則畫面會對 Berth 自己建的路徑說「還沒有 Berth 路徑」。
    """
    return f"{library_root.rstrip('/')}/{library_slug(library_name)}"


def _library_view(library: SetupLibrary, library_root: str) -> LibraryView:
    path = berth_path(library.name, library_root)
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
