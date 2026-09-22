"""精靈第 7 步：媒體庫 → Library Route 與跨服務檢查（plan §9.3 第 7 步、§9.5、brief §4）。

一個 Route 是「一個 Jellyfin 媒體庫 + 一條寫入目標路徑 + 一個 qBittorrent category」
（CONTEXT.md）。這一步做兩件事：

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

import errno
from collections import Counter
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from berth.adapters.fs import (
    PathEscapeError,
    ensure_directory,
    free_space,
    is_within,
    link_test,
    probe_file,
    stat,
)
from berth.adapters.http import ServiceError
from berth.adapters.jellyfin import JellyfinClient, JellyfinLibrary
from berth.adapters.qbittorrent import QbittorrentClient, ensure_category
from berth.domain import (
    CollectionType,
    HealthStatus,
    RouteCheck,
    RouteRefusal,
    ServiceKind,
    ServiceOrigin,
    StepStatus,
)
from berth.models import (
    JellyfinSettings,
    Job,
    LedgerEntry,
    PathSettings,
    QbittorrentSettings,
    Route,
    RouteHealth,
    SetupLibrary,
    SetupSettings,
    SetupStep,
)
from berth.models.types import utcnow
from berth.services.clients import BUNDLED_QBITTORRENT_URL, ServiceClientFactory
from berth.services.jellyfin import BUNDLED_LIBRARIES, TVDB_MARKER, berth_path, library_slug
from berth.services.qbittorrent import sign_in
from berth.services.settings import read_settings
from berth.services.steps import StepView, message, step_views

#: category 名稱的前綴（brief §4.1）。Berth 只碰自己這些分類，其他的 torrent 一律忽略。
CATEGORY_PREFIX = "berth-"

#: 可以當 Route 目的地的媒體庫類型。音樂、書、mixed 沒有 Berth 認得的命名規則（plan §5）。
SUPPORTED_TYPES = {kind.value: kind for kind in CollectionType}


class RouteRejectedError(Exception):
    """Route 設定頁的一個命令做不下去（票 14）。

    `reason` 是給畫面挑句子的封閉集合，`detail` 是原文——與送單的 `JobRejectedError` 同形，
    前端認的是同一種錯誤（PRODUCT 原則 4：說得出原因與下一步）。
    """

    def __init__(self, reason: RouteRefusal, detail: str) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


class RouteInUseError(RouteRejectedError):
    """刪除被拒：還有東西指著這條 Route（`route_in_use`，票 14a）。

    數字帶在 `usage` 上而不只是原文：畫面要說「N 筆下載、M 個入庫檔案」，不該去解析 `detail`。
    """

    def __init__(self, usage: RouteUsage) -> None:
        super().__init__(
            RouteRefusal.ROUTE_IN_USE,
            f"jobs={usage.jobs} · ledger_entries={usage.ledger_entries}",
        )
        self.usage = usage


@dataclass(frozen=True, slots=True)
class RouteSelection:
    """使用者為一個媒體庫做的選擇（既有 Jellyfin）。套件內不用它，三個 Route 是導出的。"""

    library: str
    #: 寫入目標。必須是這個媒體庫回報的路徑之一（brief §4.1、§4.3）。
    target_path: str


@dataclass(frozen=True, slots=True)
class RouteView:
    """一個 Route 攤給 UI 的樣子。"""

    #: 設定頁的 `PUT` / `DELETE /routes/{id}` 認它。slug 是網址與 category 用的名字。
    id: int
    slug: str
    name: str
    #: Jellyfin 媒體庫的名字。Route 名之後可以改，這個跟著 Jellyfin。
    library: str
    collection_type: CollectionType
    target_path: str
    category: str
    #: 這個 category 的 save path，也就是硬鏈接的來源目錄（brief §4.1）。
    save_path: str
    enabled: bool
    health: HealthStatus
    checks: tuple[StepView, ...]
    #: 硬鏈接回 `EXDEV`：兩個目錄在 Berth 內是不同掛載（brief §4.4）。
    cross_device: bool
    checked_at: datetime | None
    #: 最後一次全綠的時間（brief §16.2）。
    last_ok_at: datetime | None


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
    #: 已經有 Route 了：精靈只新增，這個媒體庫在勾選表上鎖住（票 14）。
    has_route: bool
    target_path: str


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
    by_library = {
        _library_key(route.jellyfin_library_id, route.jellyfin_library_name): route
        for route in routes.values()
    }
    return RouteSetupStatus(
        origin=_jellyfin_origin(setup),
        library_root=paths.library_root,
        complete_root=paths.complete_root,
        libraries=tuple(
            _library_choice(
                library,
                paths.library_root,
                by_library.get(_library_key(library.item_id, library.name)),
            )
            for library in setup.jellyfin.libraries
        ),
        routes=views,
        ready=_ready([route.health for route in views if route.enabled]),
        completed=setup.completed,
    )


async def routes_health(session: AsyncSession) -> HealthStatus:
    """健康頁四項裡的第四項：**啟用中**的 Route 的總結（票 10、票 14）。

    一條都沒有是 `unknown` 而不是紅燈——那是「還沒建」，不是「壞了」。停用的 Route 照樣
    檢查、照樣逐條顯示，但不算進總結：停用是「被引用、刪不得」時的出路（票 14），而一條
    沒有人會送單過去的 Route 紅著，不該讓整台 Berth 永遠是 degraded。
    """
    routes = await _existing_routes(session)
    health = [route.health_status for route in routes.values() if route.enabled]
    if not health:
        return HealthStatus.UNKNOWN
    if any(status is HealthStatus.FAILED for status in health):
        return HealthStatus.FAILED
    if all(status is HealthStatus.OK for status in health):
        return HealthStatus.OK
    # 有 Route 但還沒被檢查過（剛建好、Berth 才剛啟動）。
    return HealthStatus.UNKNOWN


async def routes_ready(session: AsyncSession) -> bool:
    """第 7 步做完了沒：至少一條啟用中的 Route，而且每一條啟用中的都通過了檢查。

    **不是「至少一個綠的」**：紅的那個 Route 送單會失敗（brief §4.4），把精靈放行等於讓
    使用者帶著一個已知壞掉的目的地開始用。停用的 Route 不是目的地，所以不算（票 14）。
    """
    routes = await _existing_routes(session)
    return _ready(tuple(route.health_status for route in routes.values() if route.enabled))


async def build_routes(
    session: AsyncSession,
    factory: ServiceClientFactory,
    selections: Sequence[RouteSelection],
) -> RouteSetupStatus:
    """替還沒有 Route 的媒體庫建 Route，然後重跑**每一條** Route 的檢查（plan §9.3 第 7 步）。

    **只新增、不改不刪**（票 14，使用者拍板）。票 09 之後 Job 引用 `route_id`、帳本以
    `target_path` 認 Route，所以重跑時取消勾選就刪掉、換個目標就覆寫，都會讓已經發生的事
    對不上它的 Route。已經有 Route 的媒體庫的選擇因此略過；刪除與停用是 Route 設定頁上
    明確的動作（`delete_route`、`update_route`）。重跑這一步的意思就剩「補上新勾的，全部重驗」。

    新建的 Route 啟不啟用分兩個時期：精靈跑完之前直接啟用——它紅著就擋完成（票 09）。跑完之後
    重跑已經沒有完成條件擋著，所以**先停用建立、檢查綠了才啟用**（票 14a）：先啟用再把紅的關掉的話，
    檢查跑完之前的那幾秒裡，送單選得到一條還沒驗過的 Route。
    """
    async with _write_lock(session):
        # 鎖內重讀：另一個分頁可能剛在設定頁建了一條，`_plan` 要看到它的 slug 與目標。
        setup = await read_settings(session, SetupSettings)
        paths = await read_settings(session, PathSettings)
        existing = tuple((await _existing_routes(session)).values())
        planned = _plan(setup, paths, selections, existing)
        for plan_row in planned:
            session.add(
                _new_route(plan_row, name=plan_row.library_name, enabled=not setup.completed)
            )

    await check_routes(session, factory)
    if setup.completed and planned:
        fresh = {plan_row.slug for plan_row in planned}
        for route in (await _existing_routes(session)).values():
            if route.slug in fresh and route.health_status is HealthStatus.OK:
                route.enabled = True
        await session.commit()
    return await read_route_status(session)


async def check_routes(
    session: AsyncSession, factory: ServiceClientFactory
) -> tuple[RouteView, ...]:
    """重跑每個既有 Route 的五項檢查（票 10 的第四項健康檢查）。

    與精靈第 7 步跑的是**同一組檢查、寫的是同一個欄位**（plan §9.5）：起點不同而已——那裡
    的起點是使用者的勾選，這裡是 `routes` 表現有的列。所以「精靈當時是綠的、現在紅了」
    在畫面上是同一種東西。
    """
    routes = list((await _existing_routes(session)).values())
    if not routes:
        return ()
    paths = await read_settings(session, PathSettings)
    planned = tuple(_planned_from(route, paths) for route in routes)

    await _run_checks(session, factory, planned, routes)
    return (await read_route_status(session)).routes


async def create_route(
    session: AsyncSession,
    factory: ServiceClientFactory,
    *,
    library_id: str,
    target_path: str,
    name: str,
) -> RouteView:
    """Route 設定頁的「新增 Route」（plan §6 routes 群組、brief §4.3、票 14）。

    同一個 Jellyfin 媒體庫可以有好幾條 Route（兩顆碟各一條），所以認媒體庫用 `ItemId`、
    slug 與整張表比。媒體庫與它的路徑**向 Jellyfin 現查**，不讀第 3 步的快照：第二條路徑
    多半是使用者之後才在 Jellyfin 那邊加的。

    建立時先停用、檢查全綠才啟用（使用者拍板）：紅的 Route 送單一定失敗（brief §4.4），
    而留著這一列，修好掛載之後按一次「重新檢查」再啟用就好，不必重填一次。

    順序是鎖的規矩（`_write_lock`）：問 Jellyfin 在鎖外，看目標有沒有人佔、算 slug、寫入在鎖內，
    五條纜繩又回到鎖外。兩個分頁同時建同一個目標時，後到的那一個重讀之後說 `target_taken`。
    """
    library = await _live_library(session, factory, library_id)
    collection_type = SUPPORTED_TYPES.get(library.collection_type)
    if collection_type is None:
        raise RouteRejectedError(
            RouteRefusal.LIBRARY_UNSUPPORTED,
            f"{library.name!r} is a {library.collection_type or 'mixed'} library",
        )
    if target_path not in library.locations:
        # 路徑一律從 Jellyfin 讀，使用者只做選擇（brief §4.1）。
        raise RouteRejectedError(
            RouteRefusal.TARGET_NOT_IN_LIBRARY,
            f"{target_path!r} is not a path of {library.name!r} "
            f"(it has {', '.join(library.locations) or 'none'})",
        )
    paths = await read_settings(session, PathSettings)
    try:
        async with _write_lock(session):
            existing = tuple((await _existing_routes(session)).values())
            _refuse_taken(target_path, existing)
            slug = _unique_slug(library.name, {route.slug for route in existing})
            plan_row = _Planned(
                slug=slug,
                library_name=library.name,
                library_item_id=library.item_id,
                collection_type=collection_type,
                target_path=target_path,
                category=f"{CATEGORY_PREFIX}{slug}",
                save_path=save_path_of(paths.complete_root, slug),
            )
            route = _new_route(plan_row, name=name, enabled=False)
            session.add(route)
    except IntegrityError as exc:
        # 建立點都在鎖內看過了；還是撞上唯一索引代表有鎖外的寫入。重讀之後照實說，不是 500。
        _refuse_taken(target_path, tuple((await _existing_routes(session)).values()))
        raise RouteRejectedError(RouteRefusal.ROUTE_CONFLICT, str(exc.orig)) from exc

    async with _stale_write_as_missing(session, route.id):
        await _run_checks(session, factory, (plan_row,), (route,))
        route.enabled = route.health_status is HealthStatus.OK
        await session.commit()
    return _route_view(route, paths.complete_root)


async def update_route(
    session: AsyncSession,
    factory: ServiceClientFactory,
    route_id: int,
    *,
    name: str,
    enabled: bool,
) -> RouteView:
    """Route 設定頁的「修改」：名稱與啟用（使用者拍板）。

    slug 與目標路徑不在這裡：category 與 complete 子目錄由 slug 導出，帳本以目標路徑認 Route，
    改了就是另一條 Route——要換就新增一條、刪掉舊的（Sonarr 的 root folder 同樣不能改路徑）。

    每一次修改都重跑五條纜繩（票 14 驗收）。**從停用到啟用**要那一輪全綠，否則拒絕並留在停用；
    名稱照樣存下。已經啟用的 Route 這一輪變紅不會被停掉——它的紅燈本來就擋得住
    送單（`jobs._check_route`），默默替人停用反而是另一種隱式的改動。
    """
    route = await _find_route(session, route_id)
    paths = await read_settings(session, PathSettings)
    async with _stale_write_as_missing(session, route_id):
        route.name = name
        await session.commit()

        await _run_checks(session, factory, (_planned_from(route, paths),), (route,))
        if enabled and not route.enabled and route.health_status is not HealthStatus.OK:
            raise RouteRejectedError(RouteRefusal.ROUTE_UNHEALTHY, route.slug)
        route.enabled = enabled
        await session.commit()
    return _route_view(route, paths.complete_root)


async def check_route(
    session: AsyncSession, factory: ServiceClientFactory, route_id: int
) -> RouteView:
    """「重新檢查」一條 Route：與健康迴圈同一組檢查、寫同一個欄位（plan §9.5）。

    只是診斷，不動 `enabled`——管理員可能是故意停用它的。修好之後要用它，就明確地啟用一次
    （`update_route` 會再驗一輪）。
    """
    route = await _find_route(session, route_id)
    paths = await read_settings(session, PathSettings)
    await _run_checks(session, factory, (_planned_from(route, paths),), (route,))
    return _route_view(route, paths.complete_root)


@dataclass(frozen=True, slots=True)
class RouteUsage:
    """有多少東西指著這條 Route。任一個不是 0 就刪不得（票 14）。"""

    #: `jobs.route_id` 是它的下載。入庫時要靠它知道去哪裡。
    jobs: int
    #: 目標落在它底下的帳本（`owning_route`）。帳本不記 Route，Job 不在了檔案也還在。
    ledger_entries: int

    @property
    def in_use(self) -> bool:
        return self.jobs > 0 or self.ledger_entries > 0


@dataclass(frozen=True, slots=True)
class ManagedRoute:
    """Route 設定頁上的一列：Route 本身，加上有多少東西指著它。"""

    route: RouteView
    usage: RouteUsage


@dataclass(frozen=True, slots=True)
class LibraryPath:
    """媒體庫回報的一條路徑，與已經寫在那裡的 Route。"""

    path: str
    #: 佔用它的那條 Route 的名字，沒有就是 `None`。同一個目標不會有第二條（`target_taken`）。
    route_name: str | None


@dataclass(frozen=True, slots=True)
class LibraryOption:
    """新增 Route 時可選的一個 Jellyfin 媒體庫（現查）。"""

    item_id: str
    name: str
    collection_type: str
    #: Jellyfin 回報的順序。被佔用的帶著 Route 名，畫面不必再拿清單反查（票 14a）。
    paths: tuple[LibraryPath, ...]
    supported: bool
    uses_tvdb: bool


async def list_routes(session: AsyncSession) -> tuple[ManagedRoute, ...]:
    """Route 設定頁的清單（`GET /routes`）。不連線；引用數一次算完，不逐條查。"""
    paths = await read_settings(session, PathSettings)
    routes = tuple((await _existing_routes(session)).values())
    usages = await _usages(session, routes)
    return tuple(
        ManagedRoute(route=_route_view(route, paths.complete_root), usage=usages[route.id])
        for route in routes
    )


async def list_libraries(
    session: AsyncSession, factory: ServiceClientFactory
) -> tuple[LibraryOption, ...]:
    """新增 Route 可選的媒體庫，**向 Jellyfin 現查**（`GET /jellyfin/libraries`）。

    不讀第 3 步的快照：「一個媒體庫多條 Route」的第二條路徑，多半是使用者之後才在
    Jellyfin 那邊加的。
    """
    libraries = await _live_libraries(session, factory)
    holders = {
        route.target_path: route.name for route in (await _existing_routes(session)).values()
    }
    return tuple(
        LibraryOption(
            item_id=library.item_id,
            name=library.name,
            collection_type=library.collection_type,
            paths=tuple(
                LibraryPath(path=path, route_name=holders.get(path)) for path in library.locations
            ),
            supported=library.collection_type in SUPPORTED_TYPES,
            uses_tvdb=any(
                TVDB_MARKER in fetcher.lower()
                for option in library.type_options
                for fetcher in option.metadata_fetchers
            ),
        )
        for library in libraries
    )


async def _usages(session: AsyncSession, routes: Sequence[Route]) -> dict[int, RouteUsage]:
    """每條 Route 被多少 Job 與帳本指著。帳本不記 Route，所以逐筆問 `owning_route`。"""
    counted = await session.execute(
        select(Job.route_id, func.count()).where(Job.route_id.is_not(None)).group_by(Job.route_id)
    )
    jobs = dict(counted.tuples().all())
    owned = Counter(
        owner.id
        for target in await session.scalars(select(LedgerEntry.target_path))
        if (owner := owning_route(target, routes)) is not None
    )
    return {
        route.id: RouteUsage(jobs=jobs.get(route.id, 0), ledger_entries=owned[route.id])
        for route in routes
    }


async def _usage_of(session: AsyncSession, route: Route, routes: Sequence[Route]) -> RouteUsage:
    """一條 Route 的引用數。刪除只問這一條，不必把整張帳本讀進來（清單才需要 `_usages`）。

    前綴粗篩（`target_prefix`）再用 `owning_route` 精判，與媒體庫頁同一條規則；前綴不正規化的話
    目標寫法不正規的 Route 會少算、被引用了還刪得掉。
    """
    jobs = await session.scalar(
        select(func.count()).select_from(Job).where(Job.route_id == route.id)
    )
    candidates = await session.scalars(
        select(LedgerEntry.target_path).where(
            LedgerEntry.target_path.startswith(target_prefix(route), autoescape=True)
        )
    )
    owned = sum(1 for target in candidates if owning_route(target, routes) is route)
    return RouteUsage(jobs=jobs or 0, ledger_entries=owned)


async def delete_route(session: AsyncSession, route_id: int) -> None:
    """Route 設定頁的「刪除」：一個明確、要二次確認的動作（票 14）。

    **被引用就拒絕**，理由是 `route_in_use`，出路是停用（`update_route`）：停用擋得住新的送單，
    又不讓已經發生的下載與入庫失去它們的 Route。qBittorrent 的 category 與 complete 子目錄
    不跟著刪——刪得了就代表沒有東西在用它們，而同一個 slug 之後重建時 category 檢查會認得它。

    算引用數與刪除在同一把寫鎖裡（票 14a）：否則算完的那一刻另一個請求送了一筆單，刪除接著把它的
    `route_id` 設成 NULL，留下一筆不知道要入庫到哪裡的下載。有鎖時那一筆等到這裡 commit，
    然後在外鍵上撞牆（`add_download` 回 `route_missing`）。
    """
    async with _write_lock(session):
        route = await _find_route(session, route_id)
        routes = tuple((await _existing_routes(session)).values())
        usage = await _usage_of(session, route, routes)
        if usage.in_use:
            raise RouteInUseError(usage)
        await session.delete(route)


async def _find_route(session: AsyncSession, route_id: int) -> Route:
    """設定頁的命令認的那一條。不在了是一個理由（`route_missing` → 404），不是 500。

    `populate_existing`：identity map 裡的那一份可能是另一條連線刪掉或改掉之前讀的。
    """
    route = await session.get(Route, route_id, populate_existing=True)
    if route is None:
        raise RouteRejectedError(RouteRefusal.ROUTE_MISSING, str(route_id))
    return route


def _refuse_taken(target_path: str, routes: Sequence[Route]) -> None:
    """帳本以目標路徑認 Route（`owning_route`）：兩條同一個目標就分不出檔案是誰的。"""
    holder = next((route for route in routes if route.target_path == target_path), None)
    if holder is not None:
        raise RouteRejectedError(
            RouteRefusal.TARGET_TAKEN, f"{target_path!r} is already {holder.slug!r}"
        )


#: 一句改不到任何一列的 UPDATE。用途見 `_write_lock`。
_TAKE_WRITE_LOCK = text("UPDATE routes SET id = id WHERE id = -1")


@asynccontextmanager
async def _write_lock(session: AsyncSession) -> AsyncIterator[None]:
    """在 SQLite 的寫鎖裡做完一段「先讀、再寫」；正常離開時 commit，丟例外就 rollback（票 14a）。

    刪除要先算引用數、建立要先看目標有沒有人佔：兩步之間另一條連線插一筆進來，檢查就白做了。
    SQLite 一個資料庫只有一把寫鎖，借它就不必自己做鎖，而且跨連線、跨 worker 都算數。

    做法：先 commit 收掉前一個交易，再下一句 0 列的 UPDATE。驅動在 legacy 交易模式下只為 DML
    發 `BEGIN`、SELECT 不發（SQLAlchemy 的 sqlite 方言文件），而 UPDATE 一開始執行就要寫鎖，
    不管改到幾列——`test_routes.py` 的 `TestRaces` 實證這一點。別的連線在 `busy_timeout` 內等它。

    規矩：取鎖之後一律重讀（鎖外讀到的可能已經不是現在的樣子）；鎖內不打網路（別的寫入都在等）。
    """
    await session.commit()
    try:
        # 等不到鎖（`busy_timeout` 到期）也要 rollback，別把半開的交易留給呼叫端。
        await session.execute(_TAKE_WRITE_LOCK)
        yield
        await session.commit()
    except BaseException:
        await session.rollback()
        raise


@asynccontextmanager
async def _stale_write_as_missing(session: AsyncSession, route_id: int) -> AsyncIterator[None]:
    """在鎖外打網路的那幾秒裡，這條 Route 可能在另一個分頁被刪掉了（票 14a）。

    寫回時 0 列被改到（`StaleDataError`）：與一開始就找不到它是同一個理由，
    `route_missing`，不是 500。
    """
    try:
        yield
    except StaleDataError as exc:
        await session.rollback()
        raise RouteRejectedError(RouteRefusal.ROUTE_MISSING, str(route_id)) from exc


async def _live_libraries(
    session: AsyncSession, factory: ServiceClientFactory
) -> tuple[JellyfinLibrary, ...]:
    """Jellyfin 現在報的媒體庫。問不到是一個理由（`jellyfin_unreachable`）而不是 500。"""
    settings = await read_settings(session, JellyfinSettings)
    jellyfin = factory.jellyfin(settings.base_url, token=settings.api_key)
    try:
        return await jellyfin.libraries()
    except ServiceError as exc:
        raise RouteRejectedError(RouteRefusal.JELLYFIN_UNREACHABLE, message(exc)) from exc
    finally:
        await jellyfin.aclose()


async def _live_library(
    session: AsyncSession, factory: ServiceClientFactory, library_id: str
) -> JellyfinLibrary:
    """Jellyfin 現在報的這個媒體庫。它已經不在了是一個理由而不是 500。"""
    libraries = await _live_libraries(session, factory)
    library = next((row for row in libraries if row.item_id == library_id), None)
    if library is None:
        raise RouteRejectedError(
            RouteRefusal.LIBRARY_MISSING, f"Jellyfin has no library with id {library_id!r}"
        )
    return library


def _planned_from(route: Route, paths: PathSettings) -> _Planned:
    """已經存在的 Route → 檢查要用的計劃。save path 照 `save_path_of` 算，不另存一份。"""
    return _Planned(
        slug=route.slug,
        library_name=route.jellyfin_library_name,
        library_item_id=route.jellyfin_library_id,
        collection_type=route.collection_type,
        target_path=route.target_path,
        category=route.category,
        save_path=save_path_of(paths.complete_root, route.slug),
    )


async def _run_checks(
    session: AsyncSession,
    factory: ServiceClientFactory,
    planned: Sequence[_Planned],
    routes: Sequence[Route],
) -> None:
    """逐個 Route 跑檢查並把結果寫回那一列。呼叫端負責它們的順序一致。"""
    moment = utcnow()
    qbittorrent_settings = await read_settings(session, QbittorrentSettings)
    jellyfin_settings = await read_settings(session, JellyfinSettings)
    qbittorrent = factory.qbittorrent(qbittorrent_settings.base_url or BUNDLED_QBITTORRENT_URL)
    jellyfin = factory.jellyfin(jellyfin_settings.base_url, token=jellyfin_settings.api_key)
    try:
        await sign_in(qbittorrent, qbittorrent_settings)
        for plan_row, route in zip(planned, routes, strict=True):
            previous = RouteHealth.model_validate(route.health_detail_json or {})
            health = await _check(plan_row, route, qbittorrent, jellyfin)
            passed = all(row.status is not StepStatus.FAILED for row in health.checks)
            health.checked_at = moment
            # 沒過就留住上一次成功的時間，別讓它看起來從來沒通過（brief §16.2）。
            health.last_ok_at = moment if passed else previous.last_ok_at
            # 逐個 commit：三個 Route 裡的第二個中途被刪掉時，第一個的結果仍然留得下來
            # （那一條的拒絕會結束這一輪，後面的留到下一輪重新檢查）。
            async with _stale_write_as_missing(session, route.id):
                route.health_detail_json = health.model_dump(mode="json")
                route.health_status = HealthStatus.OK if passed else HealthStatus.FAILED
                await session.commit()
    finally:
        await qbittorrent.aclose()
        await jellyfin.aclose()


# --- 選擇 → 計劃 -------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Planned:
    """一個要建立（或要重新檢查）的 Route。

    帶的是媒體庫的名字與 id 而不是整份 `SetupLibrary`：健康頁重跑檢查時起點是 `routes`
    那一列，它記的就是這兩個欄位（票 10）。
    """

    slug: str
    library_name: str
    library_item_id: str
    collection_type: CollectionType
    target_path: str
    category: str
    save_path: str


def _plan(
    setup: SetupSettings,
    paths: PathSettings,
    selections: Sequence[RouteSelection],
    existing: Sequence[Route],
) -> tuple[_Planned, ...]:
    """套件內導出三個 Route；既有用使用者的勾選。無效的選擇丟 `ValueError`（→ 422）。

    已經有 Route 的媒體庫略過（精靈只新增，見 `build_routes`）；slug 與整張表比，不只與
    這一批比——Route 設定頁建的第二條（`tv-2`）也佔著名字。

    **目標已經被佔用的選擇也略過，不回 422**（票 14a，使用者拍板）。佔用者可以是既有的 Route，
    也可以是這一批前面的選擇。帳本以目標路徑認 Route，同一個目標兩條就分不出檔案是誰的；而這與
    「已經有 Route 的媒體庫略過」是同一條只新增規則——套件內三個媒體庫自動全勾，舊 Route 的 key
    一旦對不上（沒有 `ItemId`、媒體庫又改了名），回 422 的話重跑就永遠卡在這一步。
    """
    libraries = {library.name: library for library in setup.jellyfin.libraries}
    chosen = (
        _bundled_selections(libraries)
        if _jellyfin_origin(setup) is ServiceOrigin.BUNDLED
        else selections
    )

    planned: list[_Planned] = []
    taken = {route.slug for route in existing}
    targets = {route.target_path for route in existing}
    routed = {
        _library_key(route.jellyfin_library_id, route.jellyfin_library_name) for route in existing
    }
    for selection in chosen:
        library = libraries.get(selection.library)
        if library is None:
            raise ValueError(f"no library named {selection.library!r} on this Jellyfin")
        key = _library_key(library.item_id, library.name)
        if key in routed:
            continue
        routed.add(key)
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
        if selection.target_path in targets:
            continue
        targets.add(selection.target_path)
        slug = _unique_slug(library.name, taken)
        taken.add(slug)
        planned.append(
            _Planned(
                slug=slug,
                library_name=library.name,
                library_item_id=library.item_id,
                collection_type=collection_type,
                target_path=selection.target_path,
                category=f"{CATEGORY_PREFIX}{slug}",
                save_path=save_path_of(paths.complete_root, slug),
            )
        )
    return tuple(planned)


def _bundled_selections(libraries: Mapping[str, SetupLibrary]) -> tuple[RouteSelection, ...]:
    """套件內：三個媒體庫各一個 Route（plan §9.3 第 7 步）。

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
        chosen.append(RouteSelection(library=bundled.name, target_path=library.locations[0]))
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


def _new_route(plan_row: _Planned, *, name: str, enabled: bool) -> Route:
    """計劃 → 一列還沒檢查過的 `routes`。"""
    return Route(
        slug=plan_row.slug,
        name=name,
        jellyfin_library_id=plan_row.library_item_id,
        jellyfin_library_name=plan_row.library_name,
        collection_type=plan_row.collection_type,
        target_path=plan_row.target_path,
        category=plan_row.category,
        enabled=enabled,
        health_status=HealthStatus.UNKNOWN,
    )


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
        # 送給 qBittorrent 的是**計劃裡那一串字**，不是 `Path` 走一趟回來的樣子：
        # 容器路徑一律是 POSIX，而 `str(Path(...))` 在 Windows 上會換成反斜線。送單
        # （票 09）比對的是同一支 `save_path_of` 的輸出，兩邊差一種分隔符就會判成衝突。
        outcome = await ensure_category(
            self._qbittorrent, self._plan.category, self._plan.save_path
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
        library = next((row for row in libraries if _is_library(row, self._plan)), None)
        if library is None:
            raise _CheckFailedError(
                f"Jellyfin no longer has a library named {self._plan.library_name!r}"
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


def _library_key(item_id: str, name: str) -> str:
    """認一個 Jellyfin 媒體庫：`ItemId`，沒有才用名字（票 09 之前存下的設定沒有 id）。

    一庫多條之後名字認不準（票 14 code-review）：在 Jellyfin 改個名不是換了一個媒體庫，
    同名的兩個也是兩個。
    """
    return item_id or name


def _is_library(library: JellyfinLibrary, plan_row: _Planned) -> bool:
    """Jellyfin 現在報的這一個，是不是這條 Route 的媒體庫。"""
    if plan_row.library_item_id:
        return library.item_id == plan_row.library_item_id
    return library.name == plan_row.library_name


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


# --- 攤平 ---------------------------------------------------------------


def _jellyfin_origin(setup: SetupSettings) -> ServiceOrigin:
    probe = setup.services.get(ServiceKind.JELLYFIN)
    return probe.origin if probe is not None else ServiceOrigin.EXISTING


def _route_view(route: Route, complete_root: str) -> RouteView:
    health = RouteHealth.model_validate(route.health_detail_json or {})
    return RouteView(
        id=route.id,
        slug=route.slug,
        name=route.name,
        library=route.jellyfin_library_name,
        collection_type=route.collection_type,
        target_path=route.target_path,
        category=route.category,
        save_path=save_path_of(complete_root, route.slug),
        enabled=route.enabled,
        health=route.health_status,
        checks=step_views(health.checks),
        cross_device=health.cross_device,
        checked_at=health.checked_at,
        last_ok_at=health.last_ok_at,
    )


def save_path_of(complete_root: str, slug: str) -> str:
    """Route 的 complete 子目錄（brief §4.1）。**一個地方算，到處用**——精靈的檢查、
    健康頁、畫面上那一行，以及票 09 的送單（category 的 save path 就是它）。"""
    return f"{complete_root.rstrip('/')}/{slug}"


def target_prefix(route: Route) -> str:
    """帳本目標路徑以這條 Route 開頭的樣子，給 SQL 的 `startswith` 粗篩用。

    帳本的目標是 importer 以 `PurePosixPath(route.target_path) / …` 組出來的，所以前綴照同一個
    正規化（`//`、結尾斜線）；照字面比的話，目標打成 `…//tv/` 的 Route 會少算（票 14a、15）。
    粗篩之後仍要 `owning_route` 精判：`…/tv/anime` 可能是另一條更深的 Route。
    """
    return str(PurePosixPath(route.target_path)).rstrip("/") + "/"


def owning_route(target_path: str, routes: Sequence[Route]) -> Route | None:
    """媒體庫裡這個檔案屬於哪一條 Route。

    帳本只記目標路徑、不記 Route，所以它屬於**目標在它底下**的那一條——有好幾條時是最深的
    那一條（`/data/library/tv` 與 `/data/library/tv/anime` 可以同時是 Route，brief §4.3）。
    反查（票 12）與媒體庫（票 13）問的是同一件事。
    """
    target = Path(target_path)
    owners = [route for route in routes if is_within(target, Path(route.target_path))]
    return max(owners, key=lambda route: len(route.target_path), default=None)


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
        has_route=route is not None,
        target_path=route.target_path if route is not None else _default_target(library),
    )


def _default_target(library: SetupLibrary) -> str:
    """還沒選過的媒體庫預選哪一條：只有一條就是它（brief §4.3「自動選定」）。"""
    return library.locations[0] if len(library.locations) == 1 else ""


def _ready(health: Sequence[HealthStatus]) -> bool:
    return bool(health) and all(status is HealthStatus.OK for status in health)


def _gigabytes(size: int) -> str:
    """可用空間。與 `dev=` / `inode=` 一樣是 key=value 的實測值，不是英文散文。"""
    return f"{size / 1_000_000_000:.1f} GB"
