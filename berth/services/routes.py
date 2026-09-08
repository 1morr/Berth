"""精靈第 7 步：媒體庫 → Library Route 與跨服務檢查（plan §9.3 第 7 步、§9.5、brief §4）。

一個 Route 是「一個 Jellyfin 媒體庫 + 一條寫入目標路徑 + 一個 qBittorrent category +
一個 profile」（CONTEXT.md）。這一步做兩件事：

- **建 Route**。套件內由 Berth 自己建的三個媒體庫自動長出三個 Route；既有 Jellyfin 由使用者
  勾選媒體庫，並從**那個媒體庫自己回報的路徑**裡選一條當寫入目標——路徑一律用選的，不用打的
  （brief §4.1），所以這裡也拒絕不在 `locations` 裡的目標。
- **檢查**。每個 Route 立刻在 qBittorrent 建 category，然後跑 plan §9.5 的三項檢查。它們回答
  的是同一個問題：**Berth、qBittorrent、Jellyfin 三個容器看到的是不是同一個檔案系統**。
  只比 `st_dev` 不夠，所以最後一項真的鏈接一次（brief §4.4）。

一條纜繩斷了就停在那裡：後面的檢查測的會是錯的路徑，讓它們一起變紅只會蓋掉真正的原因。

**檢查失敗不是例外**：它是這一步的結果，逐項寫進 `routes.health_detail_json`，畫面照著
顯示原文與「哪個容器少了哪個掛載」。會丟例外的只有使用者送了無效的選擇（ValueError → 422）。
"""

from __future__ import annotations

import contextlib
import errno
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.fs import (
    PathEscapeError,
    ensure_directory,
    free_space,
    link_test,
    probe_file,
    stat,
)
from berth.adapters.http import ServiceError
from berth.adapters.jellyfin import JellyfinClient
from berth.adapters.qbittorrent import QbittorrentClient, ensure_category
from berth.domain import (
    CollectionType,
    HealthStatus,
    Profile,
    RouteCheck,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.models import (
    JellyfinSettings,
    PathSettings,
    QbittorrentSettings,
    Route,
    RouteHealth,
    SetupLibrary,
    SetupSettings,
    SetupStep,
)
from berth.services.clients import BUNDLED_QBITTORRENT_URL, ServiceClientFactory
from berth.services.jellyfin import BUNDLED_LIBRARIES, TVDB_MARKER, berth_path, library_slug
from berth.services.settings import read_settings
from berth.services.steps import StepView, message, step_views

#: category 名稱的前綴（brief §4.1）。Berth 只碰自己這些分類，其他的 torrent 一律忽略。
CATEGORY_PREFIX = "berth-"

#: 可以當 Route 目的地的媒體庫類型。音樂、書、mixed 沒有 Berth 認得的命名規則（plan §5）。
SUPPORTED_TYPES = {kind.value: kind for kind in CollectionType}


@dataclass(frozen=True, slots=True)
class RouteSelection:
    """使用者為一個媒體庫做的選擇（既有 Jellyfin）。套件內不用它，三個 Route 是導出的。"""

    library: str
    #: 寫入目標。必須是這個媒體庫回報的路徑之一（brief §4.1、§4.3）。
    target_path: str
    profile: Profile = Profile.STANDARD


@dataclass(frozen=True, slots=True)
class RouteView:
    """一個 Route 攤給 UI 的樣子。"""

    slug: str
    name: str
    #: Jellyfin 媒體庫的名字。Route 名之後可以改，這個跟著 Jellyfin。
    library: str
    collection_type: CollectionType
    target_path: str
    category: str
    #: 這個 category 的 save path，也就是硬鏈接的來源目錄（brief §4.1）。
    save_path: str
    profile: Profile
    enabled: bool
    health: HealthStatus
    checks: tuple[StepView, ...]
    #: 硬鏈接回 `EXDEV`：兩個目錄在 Berth 內是不同掛載（brief §4.4）。
    cross_device: bool


@dataclass(frozen=True, slots=True)
class LibraryChoice:
    """第 7 步的一列：一個 Jellyfin 媒體庫，以及它現在被選成什麼。"""

    name: str
    collection_type: str
    locations: tuple[str, ...]
    #: 「加入 Berth 路徑」會加的那一條（第 3 步的按鈕，plan §9.5）。
    berth_path: str
    has_berth_path: bool
    uses_tvdb: bool
    #: Berth 建得了 Route 的類型（movies / tvshows）。
    supported: bool
    #: 已經有 Route 了。關掉瀏覽器再回來要回到原本的選擇（plan §9.3 續行）。
    selected: bool
    target_path: str
    profile: Profile


@dataclass(frozen=True, slots=True)
class RouteSetupStatus:
    """`GET /api/setup/routes` 與 `POST .../routes` 的整份形狀。"""

    origin: ServiceOrigin
    library_root: str
    complete_root: str
    libraries: tuple[LibraryChoice, ...]
    routes: tuple[RouteView, ...]
    #: 至少一個 Route，而且每個都綠燈。第 8 步（完成）的前提。
    ready: bool
    completed: bool


async def read_route_status(session: AsyncSession) -> RouteSetupStatus:
    """不連線，只把媒體庫與已建的 Route 攤成 UI 的形狀。"""
    setup = await read_settings(session, SetupSettings)
    paths = await read_settings(session, PathSettings)
    routes = await _existing_routes(session)
    views = tuple(_route_view(route, paths.complete_root) for route in routes.values())
    by_library = {route.jellyfin_library_name: route for route in routes.values()}
    return RouteSetupStatus(
        origin=_jellyfin_origin(setup),
        library_root=paths.library_root,
        complete_root=paths.complete_root,
        libraries=tuple(
            _library_choice(library, paths.library_root, by_library.get(library.name))
            for library in setup.jellyfin.libraries
        ),
        routes=views,
        ready=_ready([route.health for route in views]),
        completed=setup.completed,
    )


async def routes_ready(session: AsyncSession) -> bool:
    """第 7 步做完了沒：至少一個 Route，而且每個都通過了檢查。

    **不是「至少一個綠的」**：紅的那個 Route 送單會失敗（brief §4.4），把精靈放行等於讓
    使用者帶著一個已知壞掉的目的地開始用。
    """
    routes = await _existing_routes(session)
    return _ready(tuple(route.health_status for route in routes.values()))


async def build_routes(
    session: AsyncSession,
    factory: ServiceClientFactory,
    selections: Sequence[RouteSelection],
) -> RouteSetupStatus:
    """建立（或更新）Route 並逐個跑檢查（plan §9.3 第 7 步）。

    重跑是覆寫同一組列：slug 相同就是同一個 Route，沒被選到的就刪掉——精靈裡的勾選就是
    「我要哪幾個 Route」，留著一個使用者剛取消勾選的 Route 只會讓畫面說謊。
    """
    setup = await read_settings(session, SetupSettings)
    paths = await read_settings(session, PathSettings)
    planned = _plan(setup, paths, selections)

    routes = await _sync(session, planned)
    await session.commit()

    qbittorrent_settings = await read_settings(session, QbittorrentSettings)
    jellyfin_settings = await read_settings(session, JellyfinSettings)
    qbittorrent = factory.qbittorrent(qbittorrent_settings.base_url or BUNDLED_QBITTORRENT_URL)
    jellyfin = factory.jellyfin(jellyfin_settings.base_url, token=jellyfin_settings.api_key)
    try:
        await _sign_in(qbittorrent, qbittorrent_settings)
        for plan_row, route in zip(planned, routes, strict=True):
            health = await _check(plan_row, route, qbittorrent, jellyfin)
            route.health_detail_json = health.model_dump(mode="json")
            route.health_status = (
                HealthStatus.OK
                if all(row.status is not StepStatus.FAILED for row in health.checks)
                else HealthStatus.FAILED
            )
            # 逐個 commit：三個 Route 裡的第二個炸了，第一個的結果仍然留得下來。
            await session.commit()
    finally:
        await qbittorrent.aclose()
        await jellyfin.aclose()

    return await read_route_status(session)


# --- 選擇 → 計劃 -------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Planned:
    """一個要建立的 Route，以及檢查要用到的那個媒體庫。"""

    slug: str
    library: SetupLibrary
    collection_type: CollectionType
    target_path: str
    category: str
    save_path: str
    profile: Profile


def _plan(
    setup: SetupSettings, paths: PathSettings, selections: Sequence[RouteSelection]
) -> tuple[_Planned, ...]:
    """套件內導出三個 Route；既有用使用者的勾選。無效的選擇丟 `ValueError`（→ 422）。"""
    libraries = {library.name: library for library in setup.jellyfin.libraries}
    chosen = (
        _bundled_selections(libraries)
        if _jellyfin_origin(setup) is ServiceOrigin.BUNDLED
        else selections
    )

    planned: list[_Planned] = []
    taken: set[str] = set()
    for selection in chosen:
        library = libraries.get(selection.library)
        if library is None:
            raise ValueError(f"no library named {selection.library!r} on this Jellyfin")
        collection_type = SUPPORTED_TYPES.get(library.collection_type)
        if collection_type is None:
            raise ValueError(
                f"{library.name!r} is a {library.collection_type or 'mixed'} library; "
                "Berth routes are movies or tvshows"
            )
        if selection.target_path not in library.locations:
            # 路徑一律從 Jellyfin 讀，使用者只做選擇（brief §4.1）。自己打的路徑會讓
            # 「Jellyfin 看得到 Berth 寫的檔案」這個前提悄悄不成立。
            raise ValueError(
                f"{selection.target_path!r} is not a path of {library.name!r} "
                f"(it has {', '.join(library.locations) or 'none'})"
            )
        slug = _unique_slug(library.name, taken)
        taken.add(slug)
        planned.append(
            _Planned(
                slug=slug,
                library=library,
                collection_type=collection_type,
                target_path=selection.target_path,
                category=f"{CATEGORY_PREFIX}{slug}",
                save_path=_save_path(paths.complete_root, slug),
                profile=selection.profile,
            )
        )
    return tuple(planned)


def _bundled_selections(libraries: Mapping[str, SetupLibrary]) -> tuple[RouteSelection, ...]:
    """套件內：三個媒體庫各一個 Route，anime 用 `anime` profile（plan §9.3 第 7 步）。

    目標路徑取自 **Jellyfin 回報的** `locations`，不是自己算一遍——第 3 步建立時的路徑與
    這裡算出來的路徑一旦分岔，錯的那個要到入庫時才會被發現。
    """
    chosen: list[RouteSelection] = []
    for bundled in BUNDLED_LIBRARIES:
        library = libraries.get(bundled.name)
        if library is None or not library.locations:
            raise ValueError(
                f"Jellyfin does not report a library named {bundled.name!r} with a path; "
                "rerun step 3 before building routes"
            )
        chosen.append(
            RouteSelection(
                library=bundled.name,
                target_path=library.locations[0],
                profile=Profile.ANIME if bundled.slug == "anime" else Profile.STANDARD,
            )
        )
    return tuple(chosen)


def _unique_slug(library_name: str, taken: set[str]) -> str:
    """同名（或 slug 撞在一起）的第二個媒體庫接 `-2`，否則兩個 Route 會互相覆寫。"""
    base = library_slug(library_name)
    if base not in taken:
        return base
    suffix = 2
    while f"{base}-{suffix}" in taken:
        suffix += 1
    return f"{base}-{suffix}"


# --- 計劃 → 資料表 -----------------------------------------------------


async def _sync(session: AsyncSession, planned: Sequence[_Planned]) -> list[Route]:
    """把計劃寫成 `routes` 的列。slug 是同一性：重跑不長出重複列（票 09 驗收）。"""
    existing = await _existing_routes(session)
    wanted = {row.slug for row in planned}
    for slug, dropped in existing.items():
        if slug not in wanted:
            await session.delete(dropped)

    rows: list[Route] = []
    for plan_row in planned:
        route = existing.get(plan_row.slug)
        if route is None:
            route = Route(slug=plan_row.slug)
            session.add(route)
        route.name = plan_row.library.name
        route.jellyfin_library_id = plan_row.library.item_id
        route.jellyfin_library_name = plan_row.library.name
        route.collection_type = plan_row.collection_type
        route.target_path = plan_row.target_path
        route.category = plan_row.category
        route.profile = plan_row.profile
        route.enabled = True
        route.health_status = HealthStatus.UNKNOWN
        route.health_detail_json = None
        rows.append(route)
    await session.flush()
    return rows


async def _existing_routes(session: AsyncSession) -> dict[str, Route]:
    rows = (await session.scalars(select(Route).order_by(Route.id))).all()
    return {row.slug: row for row in rows}


# --- 檢查 ---------------------------------------------------------------


async def _check(
    plan_row: _Planned,
    route: Route,
    qbittorrent: QbittorrentClient,
    jellyfin: JellyfinClient,
) -> RouteHealth:
    """跑完一個 Route 的檢查序列。第一條斷掉之後的檢查一律 `pending`。"""
    checker = _Checker(plan_row, qbittorrent, jellyfin)
    checks: list[SetupStep] = []
    stopped = False
    for check in RouteCheck:
        if stopped:
            checks.append(SetupStep(key=check.value, status=StepStatus.PENDING))
            continue
        result = await checker.run(check)
        checks.append(result)
        stopped = result.status is StepStatus.FAILED
    return RouteHealth(checks=checks, cross_device=checker.cross_device)


class _Checker:
    """一個 Route 的一輪檢查。檢查之間共用的東西住在這裡，不透過參數傳。"""

    def __init__(
        self,
        plan_row: _Planned,
        qbittorrent: QbittorrentClient,
        jellyfin: JellyfinClient,
    ) -> None:
        self._plan = plan_row
        self._qbittorrent = qbittorrent
        self._jellyfin = jellyfin
        self._target = Path(plan_row.target_path)
        self._save_path = Path(plan_row.save_path)
        #: qBittorrent 自己報的 category save path。檢查一 `stat` 的是**它**，不是 Berth 算出來
        #: 的那個字串——後者是我們剛建好的目錄，拿它去 stat 一定會過，等於沒檢查。
        self._reported_save_path = ""
        #: 硬鏈接回 `EXDEV`。訊息要多說一句「兩個目錄在 Berth 內是不同掛載」。
        self.cross_device = False

    async def run(self, check: RouteCheck) -> SetupStep:
        try:
            status, detail = await _CHECKS[check](self)
        except (ServiceError, OSError, PathEscapeError) as exc:
            return SetupStep(key=check.value, status=StepStatus.FAILED, error=message(exc))
        return SetupStep(key=check.value, status=status, detail=detail)

    async def _category(self) -> tuple[StepStatus, str]:
        """category 不存在才建；存在但 save path 不同就回報衝突且**不覆寫**（plan §8.1）。"""
        # 硬鏈接的來源目錄。qBittorrent 完成時才會自己建，但檢查現在就要用到它。
        ensure_directory(self._save_path)
        outcome = await ensure_category(
            self._qbittorrent, self._plan.category, str(self._save_path)
        )
        self._reported_save_path = outcome.save_path
        detail = f"{outcome.name} → {outcome.save_path}"
        if outcome.conflict:
            raise _CheckFailedError(
                f"category {outcome.name!r} already points at {outcome.save_path!r}; "
                f"Berth wants {self._plan.save_path!r} and will not move an existing category"
            )
        return (StepStatus.OK if outcome.created else StepStatus.SKIPPED), detail

    async def _download_path(self) -> tuple[StepStatus, str]:
        """檢查一：**qBittorrent 報的**兩條路徑，Berth 這個容器看得到（plan §9.5）。

        兩條都現查那台服務：全域 `save_path` 讀 `app/preferences`，category 的那條用上一步
        `torrents/categories` 回報的值。讀不到偏好也是這一條的紅燈——把它吞掉會讓這一步在
        「其實什麼都沒驗到」的情況下變綠。
        """
        preferences = await self._qbittorrent.preferences()
        global_path = str(preferences.get("save_path", "") or "")
        if not global_path:
            raise _CheckFailedError("qBittorrent did not report a global save_path")
        _visible(global_path)
        _visible(self._reported_save_path or str(self._save_path))
        return StepStatus.OK, f"{global_path} · {self._reported_save_path or self._save_path}"

    async def _library_path(self) -> tuple[StepStatus, str]:
        """檢查二：**向 Jellyfin 現查**媒體庫路徑，逐一確認 Berth 看得到（plan §9.5）。

        不吃第 3 步存下來的快照：使用者可能在那之後於 Jellyfin 改了路徑或刪了媒體庫，而這一步
        要證明的正是「現在這台 Jellyfin 說的路徑，Berth 看得到」。
        """
        libraries = await self._jellyfin.libraries()
        library = next((row for row in libraries if row.name == self._plan.library.name), None)
        if library is None:
            raise _CheckFailedError(
                f"Jellyfin no longer has a library named {self._plan.library.name!r}"
            )
        if not library.locations:
            raise _CheckFailedError(f"{library.name!r} has no path on Jellyfin")
        for location in library.locations:
            _visible(location)
        return StepStatus.OK, " · ".join(library.locations)

    async def _probe_visible(self) -> tuple[StepStatus, str]:
        """檢查三前半：Berth 寫進 Route 目標的檔案，Jellyfin 那台也看得到（brief §16.4）。

        Jellyfin 在別台機器、或少掛了這個目錄，都會在這裡現形。
        """
        with probe_file(self._target, roots=[self._target]) as probe:
            seen = await self._jellyfin.validate_path(str(probe))
        if not seen:
            raise _CheckFailedError(
                f"Jellyfin cannot see {self._target}; "
                "POST /Environment/ValidatePath answered 404 for a file Berth had just written"
            )
        return StepStatus.OK, str(self._target)

    async def _hardlink(self) -> tuple[StepStatus, str]:
        """檢查三後半：complete 目錄與 Route 目標之間真的鏈接得起來（brief §4.4）。

        只比 `st_dev` 不夠——同一個檔案系統掛兩次、btrfs 子卷、ZFS dataset、mergerfs 都會
        `EXDEV`，所以真的鏈接一次再比 inode。
        """
        try:
            facts = link_test(self._save_path, self._target, roots=[self._target])
        except OSError as exc:
            self.cross_device = exc.errno == errno.EXDEV
            raise
        free = _gigabytes(free_space(self._target))
        return StepStatus.OK, f"dev={facts.device} · inode={facts.inode} · free={free}"


def _visible(path: str) -> None:
    """這條路徑在 Berth 這個容器裡看得到嗎。

    訊息帶的是**服務自己報的那個字串**：它就是「哪個容器少了哪個掛載」的答案，重寫成
    正規化過的樣子會讓使用者對不上他在 qBittorrent 或 Jellyfin 畫面上看到的值。各平台的
    errno 文字帶不帶檔名也不一致（Windows 的 `WinError 3` 就不帶），所以自己補。
    """
    try:
        stat(Path(path))
    except OSError as exc:
        raise _CheckFailedError(
            f"{path} is not visible from the Berth container ({message(exc)})"
        ) from exc


class _CheckFailedError(OSError):
    """這一項檢查沒過，而原因是 Berth 自己判斷出來的（不是誰丟出來的例外）。

    繼承 `OSError` 是為了與 `stat` / `link` 的失敗走同一條處理路徑——對畫面來說它們是
    同一件事：這條纜繩沒繫上，這是原文。
    """


_CHECKS: dict[RouteCheck, Callable[[_Checker], Awaitable[tuple[StepStatus, str]]]] = {
    RouteCheck.CATEGORY: _Checker._category,
    RouteCheck.DOWNLOAD_PATH: _Checker._download_path,
    RouteCheck.LIBRARY_PATH: _Checker._library_path,
    RouteCheck.PROBE_VISIBLE: _Checker._probe_visible,
    RouteCheck.HARDLINK: _Checker._hardlink,
}

#: 少一項就在 import 時炸，而不是等使用者按下去才 `KeyError`。
assert set(_CHECKS) == set(RouteCheck), "every RouteCheck needs a check"


# --- 服務 ---------------------------------------------------------------


async def _sign_in(client: QbittorrentClient, settings: QbittorrentSettings) -> None:
    """既有服務要先登入；套件內的那一台在免密白名單上（plan §9.2）。

    **登入失敗不在這裡爆掉**：帳密不對要變成每個 Route 的 `category` 那一條紅燈（接下來的
    呼叫會丟同一個 `AuthFailedError`，原文就落在那一行），而不是一個把整頁換成 500、
    連哪個 Route 卡住都看不出來的例外。
    """
    if not settings.username:
        return
    with contextlib.suppress(ServiceError):
        await client.login(settings.username, settings.password)


# --- 攤平 ---------------------------------------------------------------


def _jellyfin_origin(setup: SetupSettings) -> ServiceOrigin:
    probe = setup.services.get(ServiceKind.JELLYFIN)
    return probe.origin if probe is not None else ServiceOrigin.EXISTING


def _route_view(route: Route, complete_root: str) -> RouteView:
    health = RouteHealth.model_validate(route.health_detail_json or {})
    return RouteView(
        slug=route.slug,
        name=route.name,
        library=route.jellyfin_library_name,
        collection_type=route.collection_type,
        target_path=route.target_path,
        category=route.category,
        save_path=_save_path(complete_root, route.slug),
        profile=route.profile,
        enabled=route.enabled,
        health=route.health_status,
        checks=step_views(health.checks),
        cross_device=health.cross_device,
    )


def _save_path(complete_root: str, slug: str) -> str:
    """Route 的 complete 子目錄（brief §4.1）。**一個地方算，兩個地方用**——計劃與畫面。"""
    return f"{complete_root.rstrip('/')}/{slug}"


def _library_choice(library: SetupLibrary, library_root: str, route: Route | None) -> LibraryChoice:
    #: 「加入 Berth 路徑」加的是哪一條由第 3 步決定，這裡呼叫的是同一支函式（不重算 slug）。
    path = berth_path(library.name, library_root)
    return LibraryChoice(
        name=library.name,
        collection_type=library.collection_type,
        locations=tuple(library.locations),
        berth_path=path,
        has_berth_path=path in library.locations,
        uses_tvdb=any(TVDB_MARKER in name.lower() for name in library.metadata_fetchers),
        supported=library.collection_type in SUPPORTED_TYPES,
        selected=route is not None,
        target_path=route.target_path if route is not None else _default_target(library),
        profile=route.profile if route is not None else Profile.STANDARD,
    )


def _default_target(library: SetupLibrary) -> str:
    """還沒選過的媒體庫預選哪一條：只有一條就是它（brief §4.3「自動選定」）。"""
    return library.locations[0] if len(library.locations) == 1 else ""


def _ready(health: Sequence[HealthStatus]) -> bool:
    return bool(health) and all(status is HealthStatus.OK for status in health)


def _gigabytes(size: int) -> str:
    """可用空間。與 `dev=` / `inode=` 一樣是 key=value 的實測值，不是英文散文。"""
    return f"{size / 1_000_000_000:.1f} GB"
