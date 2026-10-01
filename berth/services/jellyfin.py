"""精靈的 Jellyfin（plan §9.3 頁 1 與頁 3、§9.4、§9.5）。

兩條路徑共用同一份狀態形狀（`SetupJellyfin`）。plan §9.4 的七步分兩半跑（M4 票 06）：

- **擁有者**（精靈頁 1，`claim_jellyfin`）：帳密只在這裡出現。還沒跑過初始精靈的那一台建立
  管理員、跑完它自己的初始設定、換 API key；已經有管理員的以它的管理員登入、換 API key。
  之後的一切都用那把 key。
- **媒體庫與路徑頁**：套件內 `bootstrap_jellyfin` 建使用者列的媒體庫；既有 `add_berth_path` 為選定的
  媒體庫**加**一條路徑。設定頁換位址或 key 走 `connect_jellyfin`。

每一步都冪等——媒體庫先看再建、API key 先列再建。重按只會把已經對的那幾步標成 `skipped`。

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
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.fs import (
    ensure_directory,
    missing_directories,
    probe_file,
    remove_empty_directories,
)
from berth.adapters.http import AuthFailedError, ServiceError
from berth.adapters.jellyfin import (
    JellyfinAuth,
    JellyfinClient,
    JellyfinLibrary,
    NewLibrary,
    TypeOption,
    unsupported_message,
    version_supported,
)
from berth.domain import (
    BerthPathFailure,
    BundledLibraryRefusal,
    CollectionType,
    InterfaceLoginRefusal,
    JellyfinStep,
    OwnerRefusal,
    ServiceKind,
    ServiceOrigin,
    StepFailure,
    StepStatus,
)
from berth.models import (
    BerthPathResult,
    BundledLibrary,
    JellyfinSettings,
    PathSettings,
    SetupLibrary,
    SetupSettings,
    SetupStep,
)
from berth.services.clients import ServiceClientFactory
from berth.services.settings import read_settings, update_settings
from berth.services.steps import (
    InterfaceLogin,
    StepFailedError,
    StepView,
    failed_step,
    step_views,
)

#: `POST /Auth/Keys?app=` 用的名字。也是重按時辨認「這把是我建的」的依據。
API_KEY_APP = "Berth"

#: 套件內媒體庫的 metadata 語言與國家（plan §9.4 第 4 步）。Jellyfin 自己的初始設定（第 2 步）
#: 不用它，走 `JellyfinStartup`。
METADATA_LANGUAGE = "zh-TW"
METADATA_COUNTRY = "TW"


@dataclass(frozen=True, slots=True)
class JellyfinStartup:
    """替還沒初始化的 Jellyfin 跑它自己的初始精靈時寫進去的（plan §9.4 第 2、5 步）。

    **在畫面上問**（M4 票 18，使用者 2026-09-30 拍板）：既有那一台問語言與地區、遠端存取；套件內
    那一台不問，前端帶 UI 語言、不開遠端存取——Berth 從同一台主機的容器連進來，用不到它。
    已經初始化過的那一台不寫，這一份用不到。
    """

    #: `UICulture` 與 `PreferredMetadataLanguage`（Jellyfin 的語言代碼：`zh-TW`、`en`）。
    ui_culture: str = "zh-TW"
    metadata_language: str = "zh-TW"
    #: `MetadataCountryCode`（ISO 3166 兩碼）。
    metadata_country: str = "TW"
    remote_access: bool = False


DEFAULT_STARTUP = JellyfinStartup()

#: 設定裡沒寫的媒體庫依內容類型落回這裡（票 06f）。brief §10 的決定：第一階段只用 TMDB，
#: 所以兩種現在一樣；分開寫是因為切換點是按類型與按媒體庫，不是全域的。
DEFAULT_METADATA_FETCHERS: dict[CollectionType, tuple[str, ...]] = {
    CollectionType.MOVIES: ("TheMovieDb",),
    CollectionType.TVSHOWS: ("TheMovieDb",),
}

#: 媒體庫掛了 TVDB 的 metadata fetcher 就警告（brief §16.4）。比對小寫子字串，因為名字由
#: 插件自己決定（官方插件是 `TheTVDB`）。
TVDB_MARKER = "tvdb"


def tvdb_fetchers(library: JellyfinLibrary) -> tuple[str, ...]:
    """這個媒體庫掛著的 TVDB metadata fetcher（逐型別攤平、去重，順序照 Jellyfin 回報的）。

    空的就是沒掛。Route 設定頁的那一行字與 `health_checker` 的 Issue 問的是同一件事（票 09c）。
    """
    found = (
        fetcher
        for option in library.type_options
        for fetcher in option.metadata_fetchers
        if TVDB_MARKER in fetcher.lower()
    )
    return tuple(dict.fromkeys(found))


class BundledLibraryRejectedError(Exception):
    """媒體庫清單存不下來（票 06f）。`row` 是新清單裡的第幾列；說不出是哪一列時是 `None`。"""

    def __init__(self, reason: BundledLibraryRefusal, detail: str, *, row: int | None) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail
        self.row = row


class LibraryDraft(Protocol):
    """送來存的一列，`PUT /setup/jellyfin/bundled` 的 body 就長這樣。存下來時才變成
    `BundledLibrary`。

    api 不 import models（import-linter），所以這裡收一個形狀而不是那個 model。
    """

    @property
    def name(self) -> str: ...
    @property
    def collection_type(self) -> CollectionType: ...
    @property
    def folder(self) -> str: ...


@dataclass(frozen=True, slots=True)
class BundledLibraryView:
    """剖面上的一列：使用者列的一個媒體庫，以及它是不是已經在 Jellyfin 建好了。"""

    name: str
    collection_type: CollectionType
    folder: str
    #: 建好的那一列在精靈裡鎖住，要改去 Jellyfin（票 06f）。
    built: bool


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
    #: 套件內路徑要建的媒體庫（票 06f）。既有路徑照樣帶著，只是畫面不讀它。
    bundled: tuple[BundledLibraryView, ...]
    #: 媒體庫資料夾的父目錄。剖面上每一列的完整路徑是 `<library_root>/<folder>`。
    library_root: str
    #: 上一次「加入 Berth 路徑」逐個媒體庫的結果（M4 票 19）。
    berth_paths: tuple[BerthPathResult, ...]


async def read_jellyfin_status(session: AsyncSession) -> JellyfinSetupStatus:
    """不連線，只把存下來的狀態攤成 UI 的形狀。輪詢進度也走這一支。"""
    setup = await read_settings(session, SetupSettings)
    jellyfin = await read_settings(session, JellyfinSettings)
    paths = await read_settings(session, PathSettings)
    origin, base_url = _target(setup, jellyfin)
    version = _measured_version(setup)
    built = _on_jellyfin(setup, paths.library_root)
    return JellyfinSetupStatus(
        origin=origin,
        base_url=base_url,
        api_key_present=bool(jellyfin.api_key),
        steps=step_views(setup.jellyfin.steps),
        libraries=tuple(_library_view(row, paths.library_root) for row in setup.jellyfin.libraries),
        version=version,
        version_supported=not version or version_supported(version),
        bundled=tuple(
            BundledLibraryView(
                name=row.name,
                collection_type=row.collection_type,
                folder=row.folder,
                built=row in built,
            )
            for row in setup.jellyfin.bundled
        ),
        library_root=paths.library_root,
        berth_paths=tuple(setup.jellyfin.berth_paths),
    )


async def save_bundled_libraries(
    session: AsyncSession, rows: Sequence[LibraryDraft]
) -> JellyfinSetupStatus:
    """存下套件內要建的媒體庫（票 06f）。按「開始靠泊」之前剖面每改一次就存一次。

    規則見 `check_bundled_libraries`。**已經在 Jellyfin 建好的列改不得**：在這裡改了名，重跑
    會多建一個指向同一個資料夾的；刪了 Berth 也不會去刪 Jellyfin 的（brief §16.4 的紅線對自己
    建的也一樣）。改名與刪除要去 Jellyfin。
    """
    paths = await read_settings(session, PathSettings)

    def record(latest: SetupSettings) -> None:
        built = _on_jellyfin(latest, paths.library_root)
        latest.jellyfin.bundled = list(check_bundled_libraries(rows, built=built))

    await update_settings(session, SetupSettings, record)
    return await read_jellyfin_status(session)


def check_bundled_libraries(
    rows: Sequence[LibraryDraft], *, built: Sequence[BundledLibrary]
) -> tuple[BundledLibrary, ...]:
    """媒體庫清單的規則（票 06f）。回修掉前後空白的清單；不成立就丟 `BundledLibraryRejectedError`。

    精靈的剖面在送出之前用同一組規則擋（`web/src/setup/libraryRules.ts`）。名稱與資料夾
    都不分大小寫比重複：Windows 與 macOS 的檔案系統不分，Jellyfin 的名稱比對也不可知。
    `built` 是已經在 Jellyfin 建好的那幾列，它們要原樣留在清單裡。
    """
    if not rows:
        raise BundledLibraryRejectedError(BundledLibraryRefusal.EMPTY, "no libraries", row=None)
    cleaned = tuple(
        BundledLibrary(
            name=row.name.strip(), collection_type=row.collection_type, folder=row.folder.strip()
        )
        for row in rows
    )
    names: set[str] = set()
    folders: set[str] = set()
    for index, row in enumerate(cleaned):
        reason = _row_problem(row, names, folders)
        if reason is not None:
            raise BundledLibraryRejectedError(reason, f"{row.name!r} → {row.folder!r}", row=index)
        names.add(row.name.casefold())
        folders.add(row.folder.casefold())
    for kept in built:
        if kept not in cleaned:
            raise BundledLibraryRejectedError(
                BundledLibraryRefusal.BUILT_CHANGED,
                f"{kept.name!r} already exists on Jellyfin; rename or delete it there",
                row=None,
            )
    return cleaned


#: 資料夾要是 `library_root` 底下的一層（票 06f）：有分隔符號、或整個是 `.` / `..`，就跳出去
#: 或往下鑽了。往下鑽也擋：`tv` 與 `tv/anime` 兩個媒體庫會重複掃到同一批檔案。
_OUTSIDE_ROOT = re.compile(r"[/\\]|^\.{1,2}$")


def _row_problem(
    row: BundledLibrary, names: set[str], folders: set[str]
) -> BundledLibraryRefusal | None:
    if not row.name:
        return BundledLibraryRefusal.NAME_MISSING
    if not row.folder:
        return BundledLibraryRefusal.FOLDER_MISSING
    if _OUTSIDE_ROOT.search(row.folder):
        return BundledLibraryRefusal.FOLDER_OUTSIDE_ROOT
    if _UNSAFE_IN_PATH.search(row.folder):
        return BundledLibraryRefusal.FOLDER_CHARACTERS
    if row.name.casefold() in names:
        return BundledLibraryRefusal.NAME_TAKEN
    if row.folder.casefold() in folders:
        return BundledLibraryRefusal.FOLDER_TAKEN
    return None


def _on_jellyfin(setup: SetupSettings, library_root: str) -> tuple[BundledLibrary, ...]:
    """清單裡已經在 Jellyfin 建好的那幾列，對著第 3 步最後一次讀到的媒體庫（`_already_built`）。"""
    names = {library.name for library in setup.jellyfin.libraries}
    locations = {path for library in setup.jellyfin.libraries for path in library.locations}
    return tuple(
        row
        for row in setup.jellyfin.bundled
        if _already_built(row, library_root, names=names, locations=locations)
    )


def libraries_built(setup: SetupSettings, library_root: str) -> bool:
    """套件內清單的每一列都在 Jellyfin 上了：頁 3 的前半（M4 票 24）。既有的那一台不建媒體庫。

    **看快照，不看「建媒體庫那一步有沒有跑過」**：保留 Jellyfin、只清 Berth 重跑時清單全部已建立，
    前端照剖面的「已建立」（`_on_jellyfin`，同一條）不呼叫 bootstrap，那一步就永遠沒有結果。
    """
    if setup.origin_of(ServiceKind.JELLYFIN) is not ServiceOrigin.BUNDLED:
        return True
    return len(_on_jellyfin(setup, library_root)) == len(setup.jellyfin.bundled)


def is_listed(library: SetupLibrary, bundled: Sequence[BundledLibrary], library_root: str) -> bool:
    """這個媒體庫是清單上的某一列（`_already_built` 反過來問）。套件內只替這幾個建 Route
    （M4 票 24）：使用者自己在 Jellyfin 加的媒體庫不是 Berth 的，路徑多半也不在它的掛載裡。"""
    names = {library.name}
    locations = set(library.locations)
    return any(
        _already_built(row, library_root, names=names, locations=locations) for row in bundled
    )


def _already_built(
    row: BundledLibrary, library_root: str, *, names: set[str], locations: set[str]
) -> bool:
    """這一列在 Jellyfin 上了嗎：同名的媒體庫在，或它的資料夾已經是某個媒體庫的路徑。

    **兩個都認**：同名不會被拒，會長出 `Movies2`（實測，brief §20.7）；而使用者照畫面說的去
    Jellyfin 改了名之後名稱就對不上了，只比名稱的話重跑會在同一個資料夾上再建一個（code review）。
    bootstrap 與剖面的鎖讀的是同一條。
    """
    return row.name in names or bundled_path(row.folder, library_root) in locations


#: 擁有者那一半（精靈頁 1）。還沒跑過初始精靈的那一台要先有管理員、跑完它自己的初始設定，才換
#: API key——初始設定跑完之後再登入、建 key 是實測過的順序（brief §20.7）。已經有管理員的那一台
#: 在 `public_info` 就知道了，中間四步都是 `skipped`（`_Runner._fresh`）。**選套件內或既有不影響
#: 這一條**（M4 票 15）：選既有而那一台還沒初始化，它上面沒有任何人的帳號可以蓋掉。
OWNER_STEPS: tuple[JellyfinStep, ...] = (
    JellyfinStep.PUBLIC_INFO,
    JellyfinStep.CONFIGURATION,
    JellyfinStep.ADMIN_USER,
    JellyfinStep.REMOTE_ACCESS,
    JellyfinStep.COMPLETE,
    JellyfinStep.API_KEY,
)

#: 設定頁換位址或 key：只登入、換 key，不動那一台的任何設定。
SIGN_IN_STEPS: tuple[JellyfinStep, ...] = (JellyfinStep.PUBLIC_INFO, JellyfinStep.API_KEY)

#: 媒體庫與路徑頁的那一半（套件內）：版本再看一次，然後建媒體庫。用的是頁 1 存下的 API key。
BERTH_STEPS = (JellyfinStep.PUBLIC_INFO, JellyfinStep.LIBRARIES)


@dataclass(frozen=True, slots=True)
class JellyfinClaim:
    """第 1 步那一半的結果。`auth` 有值就是這個人是這台 Jellyfin 的管理員、key 也拿到了。"""

    status: JellyfinSetupStatus
    auth: JellyfinAuth | None
    #: 沒成立時的理由；`detail` 是失敗那一步的原文（版本太舊時帶著版本號）。
    refusal: OwnerRefusal | None
    detail: str
    #: 這一台的 ServerId（brief §20.15）。擁有者記下它，之後換位址只接受同一台（M4 票 18）。
    server_id: str = ""


async def claim_jellyfin(
    session: AsyncSession,
    factory: ServiceClientFactory,
    *,
    username: str,
    password: str,
    startup: JellyfinStartup = DEFAULT_STARTUP,
) -> JellyfinClaim:
    """精靈第 1 步的 Jellyfin 那一半：套件內建管理員並跑完初始設定，既有的登入；都換 API key。

    **帳密一律交給 Jellyfin 驗**，即使已經有一把 key：第 1 步要證明的是「這個人是它的管理員」，
    不是「Berth 連得上它」。帳密不存下來（brief §11）。

    套件內那一台的管理員已經在（上一次在某一步失敗，或 session 過期之後重來）時，建立那一步是
    `skipped`（12.0 起回 403，brief §20.9），驗證落在換 key 那一步——所以同一組照樣成立，
    別的密碼蓋不掉它。
    """
    status, runner = await _run(
        session, factory, OWNER_STEPS, credentials=(username, password), startup=startup
    )
    failed = next((row for row in status.steps if row.status is StepStatus.FAILED), None)
    if runner.refusal is not None:
        # 帳密那兩種的理由本身就是完整的一句話；Jellyfin 的原文只給「那一段沒做完」。
        return JellyfinClaim(status=status, auth=None, refusal=runner.refusal, detail="")
    if failed is not None or runner.auth is None:
        return JellyfinClaim(
            status=status,
            auth=None,
            refusal=OwnerRefusal.JELLYFIN_FAILED,
            detail=failed.error if failed is not None else "",
        )
    return JellyfinClaim(
        status=status, auth=runner.auth, refusal=None, detail="", server_id=runner.server_id
    )


async def bootstrap_jellyfin(
    session: AsyncSession, factory: ServiceClientFactory
) -> JellyfinSetupStatus:
    """套件內路徑的媒體庫與路徑頁：建使用者列的媒體庫。重按只補建還沒建的那幾個。

    **只對選了套件內的那一台**（`ValueError`）：既有 Jellyfin 絕不自動建媒體庫（brief §16.4）。
    """
    setup = await read_settings(session, SetupSettings)
    if setup.origin_of(ServiceKind.JELLYFIN) is not ServiceOrigin.BUNDLED:
        raise ValueError(
            "this Jellyfin is an existing service; Berth does not create libraries on it"
        )
    status, _ = await _run(session, factory, BERTH_STEPS)
    return status


async def connect_jellyfin(
    session: AsyncSession, factory: ServiceClientFactory, *, username: str, password: str
) -> JellyfinSetupStatus:
    """設定頁：以**那台 Jellyfin 的**管理員帳密登入、建 API key、列出媒體庫（plan §9.5）。

    精靈裡同一件事在頁 1（`claim_jellyfin`）；這一支是精靈跑完之後換位址、換 key 用的。
    帳密不存下來：Berth 只需要 API key，而那台伺服器的管理員密碼不是 Berth 的東西。
    還沒選來源是 `ValueError`（M4 票 15）。
    """
    _require_choice(await read_settings(session, SetupSettings))
    status, _ = await _run(session, factory, SIGN_IN_STEPS, credentials=(username, password))
    return status


async def add_berth_paths(
    session: AsyncSession, factory: ServiceClientFactory, *, library_names: Sequence[str]
) -> JellyfinSetupStatus:
    """既有 Jellyfin 的「加入 Berth 路徑」：**每一個媒體庫都試、各自回報**（M4 票 19）。

    plan §9.5、brief §16.4。

    **舊路徑原地不動**：`POST /Library/VirtualFolders/Paths` 是加一條而不是換一條。同一條路徑
    加兩次會出現重複的 location，所以已經在的跳過（實測，brief §20.7）。

    **先問 Jellyfin 看不看得到，再送那一支**：目錄不存在時它回 404 + `Error processing request.`，
    連「媒體庫不存在」也是同一句（2026-09-30 對 12.1 實測），原因只在它自己的 log。所以 Berth 先建
    目錄、寫探測檔、以 `Environment/ValidatePath` 問它——看不到就是它沒掛同一個父目錄，說得出
    哪一台、哪條路徑。加不上的那一個，剛建的目錄一層一層收回去，不留空殼。

    結果逐個記在 `berth_paths`；有一個沒加上，`libraries` 那一步就是紅的——精靈停在這裡，
    不建 Route。回 422（`ValueError`）的只有還沒選來源。
    """
    setup = await read_settings(session, SetupSettings)
    _require_choice(setup)
    jellyfin = await read_settings(session, JellyfinSettings)
    paths = await read_settings(session, PathSettings)
    _, base_url = _target(setup, jellyfin)

    client = factory.jellyfin(base_url, token=jellyfin.api_key)
    libraries: tuple[JellyfinLibrary, ...] | None = None
    results: list[BerthPathResult] = []
    await _record(session, _step(JellyfinStep.LIBRARIES, StepStatus.RUNNING))
    try:
        libraries = await client.libraries()
        for name in library_names:
            results.append(await _add_berth_path(client, libraries, name, paths.library_root))
        libraries = await client.libraries()
    except ServiceError as exc:
        # 一開始就問不到媒體庫：沒試到的每一個都記成同一個原因，畫面照樣逐個說。
        tried = {row.library for row in results}
        results += [
            BerthPathResult(
                library=name,
                path="",
                status=StepStatus.FAILED,
                reason=BerthPathFailure.JELLYFIN,
                error=_message(exc),
            )
            for name in library_names
            if name not in tried
        ]
    finally:
        await client.aclose()

    failed = [row for row in results if row.status is StepStatus.FAILED]
    await _record(
        session,
        SetupStep(
            key=JellyfinStep.LIBRARIES.value,
            status=StepStatus.FAILED if failed else StepStatus.OK,
            detail=" · ".join(f"{row.library} · {row.path}" for row in results if row.path),
            error="; ".join(f"{row.library}: {row.error}" for row in failed),
        ),
    )

    def record(latest: SetupSettings) -> None:
        latest.jellyfin.berth_paths = results

    await update_settings(session, SetupSettings, record)
    await _remember(session, libraries=libraries)
    return await read_jellyfin_status(session)


async def _add_berth_path(
    client: JellyfinClient,
    libraries: Sequence[JellyfinLibrary],
    library_name: str,
    library_root: str,
) -> BerthPathResult:
    """一個媒體庫：找到它、算出 Berth 路徑、建目錄、問 Jellyfin 看不看得到、加上去。"""
    library = next((row for row in libraries if row.name == library_name), None)
    if library is None:
        return BerthPathResult(
            library=library_name,
            path="",
            status=StepStatus.FAILED,
            reason=BerthPathFailure.LIBRARY_MISSING,
            error=f"no library named {library_name!r} on this Jellyfin",
        )
    path = berth_path(library_name, library_root, library.locations)
    if path in library.locations:
        return BerthPathResult(library=library_name, path=path, status=StepStatus.OK)

    def failed(reason: BerthPathFailure, error: str) -> BerthPathResult:
        return BerthPathResult(
            library=library_name, path=path, status=StepStatus.FAILED, reason=reason, error=error
        )

    directory = Path(path)
    created = missing_directories(directory)
    try:
        ensure_directory(directory)
    except OSError as exc:
        remove_empty_directories(created)
        return failed(BerthPathFailure.DIRECTORY, _message(exc))
    try:
        with probe_file(directory, roots=[directory]) as probe:
            # 容器路徑一律以 `/` 相接：`str(Path)` 在 Windows 上會換成反斜線。
            seen = await client.validate_path(f"{path}/{probe.name}")
        if seen:
            await client.add_library_path(library_name, path)
    except OSError as exc:
        # 探測檔寫不進去是 Berth 自己這一邊的事，不是 Jellyfin 的（code-review）。
        remove_empty_directories(created)
        return failed(BerthPathFailure.DIRECTORY, _message(exc))
    except ServiceError as exc:
        remove_empty_directories(created)
        return failed(BerthPathFailure.JELLYFIN, _message(exc))
    if not seen:
        remove_empty_directories(created)
        return failed(
            BerthPathFailure.JELLYFIN_CANNOT_SEE,
            f"Jellyfin cannot see {path}: POST /Environment/ValidatePath answered 404 "
            "for a file Berth had just written there",
        )
    return BerthPathResult(library=library_name, path=path, status=StepStatus.OK)


class InterfaceLoginRejectedError(Exception):
    """勾了「沿用 Jellyfin 帳密」而 Jellyfin 那一關沒過（`InterfaceLoginRefusal`）。"""

    def __init__(self, reason: InterfaceLoginRefusal, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else str(reason))
        self.reason = reason
        self.detail = detail


async def resolve_interface_login(
    session: AsyncSession, factory: ServiceClientFactory, login: InterfaceLogin
) -> InterfaceLogin:
    """「沿用 Jellyfin 帳密」（brief §16.3，M4 票 15）：帳號換成擁有者，密碼先向 Jellyfin 驗過。

    沒勾就原樣回。驗不過就拒絕（`InterfaceLoginRejectedError`），呼叫端在寫任何東西之前呼叫它，
    所以密碼打錯時兩台都不會被寫。Berth 仍然不存擁有者的密碼（票 06）：寫進那兩台之後只記雜湊。
    """
    if not login.reuse_owner:
        return login
    setup = await read_settings(session, SetupSettings)
    jellyfin = await read_settings(session, JellyfinSettings)
    if not setup.owner.name:
        raise ValueError("there is no owner yet; finish page 1 of the wizard first")
    client = factory.jellyfin(jellyfin.base_url)
    try:
        auth = await client.authenticate(setup.owner.name, login.password)
    except AuthFailedError as exc:
        raise InterfaceLoginRejectedError(InterfaceLoginRefusal.OWNER_PASSWORD) from exc
    except ServiceError as exc:
        raise InterfaceLoginRejectedError(
            InterfaceLoginRefusal.JELLYFIN_UNREACHABLE, _message(exc)
        ) from exc
    finally:
        await client.aclose()
    return InterfaceLogin(username=auth.name or setup.owner.name, password=login.password)


# --- 序列 ---------------------------------------------------------------


async def _run(
    session: AsyncSession,
    factory: ServiceClientFactory,
    steps: tuple[JellyfinStep, ...],
    *,
    credentials: tuple[str, str] | None = None,
    startup: JellyfinStartup = DEFAULT_STARTUP,
) -> tuple[JellyfinSetupStatus, _Runner]:
    setup = await read_settings(session, SetupSettings)
    jellyfin = await read_settings(session, JellyfinSettings)
    paths = await read_settings(session, PathSettings)
    _, base_url = _target(setup, jellyfin)

    client = factory.jellyfin(base_url, token=jellyfin.api_key)
    runner = _Runner(
        client, jellyfin, paths, setup.jellyfin.bundled, credentials=credentials, startup=startup
    )
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

    def remember(latest: JellyfinSettings) -> None:
        latest.base_url = base_url
        latest.api_key = runner.api_key or latest.api_key

    # 九步要一分鐘上下，開頭讀到的那一份不拿來整組寫回（M4 票 23）。
    await update_settings(session, JellyfinSettings, remember)
    return await read_jellyfin_status(session), runner


async def _record(session: AsyncSession, *steps: SetupStep) -> None:
    """把步驟的最新狀態寫進設定並 commit。

    每一步各自 commit，前端輪詢才看得到序列走到哪裡；中途失敗時已完成的步驟也留得下來，
    重按時才跳得過它們。
    """

    def record(latest: SetupSettings) -> None:
        by_key = {row.key: row for row in latest.jellyfin.steps}
        for step in steps:
            by_key[step.key] = step
        latest.jellyfin.steps = [by_key[key] for key in _ordered(by_key)]

    await update_settings(session, SetupSettings, record)


async def _remember(
    session: AsyncSession, *, libraries: tuple[JellyfinLibrary, ...] | None = None
) -> None:
    if libraries is not None:
        await remember_libraries(session, libraries)


async def remember_libraries(session: AsyncSession, libraries: Sequence[JellyfinLibrary]) -> None:
    """把 Jellyfin 現在報的媒體庫存成精靈的快照（頁 3 讀它），commit。"""
    snapshot = [
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

    def record(latest: SetupSettings) -> None:
        latest.jellyfin.libraries = snapshot

    await update_settings(session, SetupSettings, record)


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
        jellyfin: JellyfinSettings,
        paths: PathSettings,
        bundled: Sequence[BundledLibrary],
        *,
        credentials: tuple[str, str] | None,
        startup: JellyfinStartup,
    ) -> None:
        self._client = client
        self._startup = startup
        self._jellyfin = jellyfin
        self._paths = paths
        self._bundled = tuple(bundled)
        self._credentials = credentials
        # 給了帳密就一定拿它登入，不拿存下來的 key 抄捷徑：要證明的是這個人是管理員。
        self._token = "" if credentials is not None else jellyfin.api_key
        self._fresh = False
        self.api_key = jellyfin.api_key
        #: `None` 代表這一輪沒讀到媒體庫；不要拿它覆寫存下來的清單。
        self.libraries: tuple[JellyfinLibrary, ...] | None = None
        #: 拿帳密登入成功的那一次（`claim_jellyfin` 拿它發 Berth session）。
        self.auth: JellyfinAuth | None = None
        #: 帳密這一關沒過的理由。其他失敗照樣是那一步的 `failed`。
        self.refusal: OwnerRefusal | None = None
        #: 第 1 步讀到的 ServerId（brief §20.15）。
        self.server_id = ""

    async def run(self, step: JellyfinStep) -> SetupStep:
        try:
            status, detail = await _ACTIONS[step](self)
        except (ServiceError, OSError) as exc:
            # 量得到的實測值照樣帶著：版本太舊那一行要同時說出「它是 10.11.11」與「要 12 以上」。
            version = exc.params.get("version", "") if isinstance(exc, StepFailedError) else ""
            return failed_step(step.value, exc, detail=version)
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
            raise StepFailedError(
                StepFailure.VERSION_UNSUPPORTED,
                unsupported_message(info.version),
                version=info.version,
            )
        self._fresh = not info.startup_wizard_completed
        self.server_id = info.server_id
        return StepStatus.OK, info.version

    async def _configuration(self) -> tuple[StepStatus, str]:
        startup = self._startup
        detail = f"{startup.ui_culture} · {startup.metadata_country}"
        if not self._fresh:
            return StepStatus.SKIPPED, detail
        await self._client.start_configuration(
            ui_culture=startup.ui_culture,
            metadata_country_code=startup.metadata_country,
            preferred_metadata_language=startup.metadata_language,
        )
        return StepStatus.OK, detail

    async def _admin_user(self) -> tuple[StepStatus, str]:
        if self._credentials is None:
            raise StepFailedError(
                StepFailure.UNEXPECTED, "no owner yet; finish step 1 of the wizard first"
            )
        username, password = self._credentials
        if not self._fresh:
            return StepStatus.SKIPPED, username
        # GET 不是多餘的讀取：它會建立預設使用者，少了它 POST 回 500（brief §20.7）。
        await self._client.ensure_default_user()
        # 12.0 起「第一個使用者已經有密碼」回 403，而那是**已經設過了**不是失敗：第 3 步成功、
        # 之後某一步失敗、Jellyfin 沒重啟時按重試就走到這裡（brief §20.9、票 14b）。密碼對不對
        # 由換 API key 那一步的登入驗證——那一步本來就要拿同一組帳密登入。
        created = await self._client.create_startup_user(username, password)
        return (StepStatus.OK if created else StepStatus.SKIPPED), username

    async def _libraries(self) -> tuple[StepStatus, str]:
        # 一律要第 1 步的 API key：初始精靈跑完之後 `/Library/VirtualFolders` 本來就要管理員憑證，
        # 而還沒跑完的那一台匿名也建得了——那正是擁有者成立之前不該有人做得到的事（M4 票 06）。
        await self._authenticate()
        libraries = await self._client.libraries()
        names = {library.name for library in libraries}
        locations = {path for library in libraries for path in library.locations}
        root = self._paths.library_root
        created: list[str] = []
        present: list[str] = []
        for bundled in self._bundled:
            path = bundled_path(bundled.folder, root)
            # 媒體庫目錄由 Berth 建（plan §9.1）；兩邊掛同一個宿主目錄，所以建完 Jellyfin
            # 立刻看得到。
            ensure_directory(Path(path))
            if _already_built(bundled, root, names=names, locations=locations):
                present.append(bundled.name)
                continue
            await self._client.create_library(await self._new_library(bundled, path))
            created.append(bundled.name)
        self.libraries = await self._client.libraries()
        if created:
            return StepStatus.OK, " · ".join(created)
        return StepStatus.SKIPPED, " · ".join(present)

    async def _remote_access(self) -> tuple[StepStatus, str]:
        if not self._fresh:
            return StepStatus.SKIPPED, ""
        await self._client.set_remote_access(enabled=self._startup.remote_access)
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
            raise StepFailedError(
                StepFailure.UNEXPECTED,
                "Jellyfin accepted POST /Auth/Keys but the key is not listed",
            )
        self._use(created)
        return StepStatus.OK, API_KEY_APP

    # --- 步驟共用 ---

    async def _authenticate(self) -> None:
        """有 token 就用它；沒有就以管理員帳密換一個。API key 與登入 token 同一個形狀。"""
        if self._token:
            self._client.use_token(self._token)
            return
        if self._credentials is None:
            raise StepFailedError(
                StepFailure.UNEXPECTED,
                "no API key for this Jellyfin yet; finish step 1 of the wizard",
            )
        username, password = self._credentials
        try:
            auth = await self._client.authenticate(username, password)
        except AuthFailedError:
            self.refusal = OwnerRefusal.INVALID_CREDENTIALS
            raise
        if not auth.is_administrator:
            self.refusal = OwnerRefusal.NOT_ADMINISTRATOR
            raise StepFailedError(
                StepFailure.AUTH_REJECTED, f"{username} is not a Jellyfin administrator"
            )
        self.auth = auth
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
        fetchers = self._jellyfin.metadata_fetchers.get(
            bundled.folder
        ) or DEFAULT_METADATA_FETCHERS.get(bundled.collection_type, ())
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
    """要連哪一台、它是套件內還是既有——使用者在頁 1 選的（M4 票 15）。還沒選就當既有：
    建媒體庫的那一條另外擋（`bootstrap_jellyfin`）。"""
    choice = setup.choices.get(ServiceKind.JELLYFIN)
    return (
        choice.origin if choice is not None else ServiceOrigin.EXISTING,
        jellyfin.base_url or (choice.base_url if choice is not None else ""),
    )


def _require_choice(setup: SetupSettings) -> None:
    """還沒選的服務，寫入它的命令一律拒絕（M4 票 15）。"""
    if setup.origin_of(ServiceKind.JELLYFIN) is None:
        raise ValueError("choose where Jellyfin comes from first")


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
#: 一段空白連同貼著它的 `-`：「TV Shows」「Anime / Old」都只剩一個 `-`（票 08）。
_SPACE_RUN = re.compile(r"[\s-]*\s[\s-]*")


def library_slug(library_name: str) -> str:
    """媒體庫名 → 路徑與 category 用的 slug。中日文照留（brief §4.5），空白換成 `-`（票 08）。

    第 5 步的 Route 用同一支：Route 的 complete 子目錄、qBittorrent category 與這個媒體庫的
    Berth 路徑要對得起來，兩套算法遲早會分岔。**只影響新建的**：已經存在的 Route 存著自己的
    slug 與分類，不重算——改分類的 save path 會搬走它底下的 torrent（brief §20.2）。前端
    `libraryRules.folderFor` 照同一條規則推套件內清單的資料夾。
    """
    unsafe = _UNSAFE_IN_PATH.sub("-", library_name)
    return _SPACE_RUN.sub("-", unsafe).strip(" .-").lower() or "berth"


def bundled_path(folder: str, library_root: str) -> str:
    """套件內媒體庫的路徑：`<library root>/<folder>`（票 06f）。

    預設三列的資料夾就是 `library_slug(名稱)`，所以它們與 `berth_path` 算出來的一樣；使用者
    自己取的資料夾不必。`has_berth_path` 只在既有路徑的畫面上讀（加路徑、勾選寫入目標）。
    """
    return f"{library_root.rstrip('/')}/{folder}"


def berth_path(library_name: str, library_root: str, locations: Sequence[str] = ()) -> str:
    """「加入 Berth 路徑」加的那一條：`<library root>/<slug>`（CONTEXT.md）。

    第 5 步的 Route 也用這一支決定「這個媒體庫的 Berth 路徑是哪一條」，兩邊算出來的字串
    必須一模一樣，否則畫面會對 Berth 自己建的路徑說「還沒有 Berth 路徑」。

    **已經加上去的那一條不改名**（票 08）：票 08 之前的 slug 留著空白（`…/tv shows`），媒體庫的
    `locations` 裡有它就是它——否則畫面會再給一條 `…/tv-shows`，按下去 Jellyfin 就多一條路徑。
    """
    root = library_root.rstrip("/")
    spaced = _UNSAFE_IN_PATH.sub("-", library_name).strip(" .-").lower() or "berth"
    if f"{root}/{spaced}" in locations:
        return f"{root}/{spaced}"
    return f"{root}/{library_slug(library_name)}"


def _library_view(library: SetupLibrary, library_root: str) -> LibraryView:
    path = berth_path(library.name, library_root, library.locations)
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
