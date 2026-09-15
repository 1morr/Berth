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

import errno
from collections import Counter
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
    Profile,
    RouteCheck,
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

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


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
    profile: Profile
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

    新建的 Route 啟不啟用分兩個時期：精靈跑完之前直接啟用——它紅著就擋完成（票 09）；跑完之後
    重跑已經沒有完成條件擋著，所以與設定頁同一條規則，紅燈就維持停用（票 14 code-review）。
    """
    setup = await read_settings(session, SetupSettings)
    paths = await read_settings(session, PathSettings)
    existing = tuple((await _existing_routes(session)).values())
    planned = _plan(setup, paths, selections, existing)
    for plan_row in planned:
        session.add(_new_route(plan_row, name=plan_row.library_name, enabled=True))
    await session.commit()

    await check_routes(session, factory)
    if setup.completed:
        fresh = {plan_row.slug for plan_row in planned}
        for route in (await _existing_routes(session)).values():
            if route.slug in fresh and route.health_status is not HealthStatus.OK:
                route.enabled = False
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
    profile: Profile,
) -> RouteView:
    """Route 設定頁的「新增 Route」（plan §6 routes 群組、brief §4.3、票 14）。

    同一個 Jellyfin 媒體庫可以有好幾條 Route（兩顆碟各一條），所以認媒體庫用 `ItemId`、
    slug 與整張表比。媒體庫與它的路徑**向 Jellyfin 現查**，不讀第 3 步的快照：第二條路徑
    多半是使用者之後才在 Jellyfin 那邊加的。

    建立時先停用、檢查全綠才啟用（使用者拍板）：紅的 Route 送單一定失敗（brief §4.4），
    而留著這一列，修好掛載之後按一次「重新檢查」再啟用就好，不必重填一次。
    """
    library = await _live_library(session, factory, library_id)
    collection_type = SUPPORTED_TYPES.get(library.collection_type)
    if collection_type is None:
        raise RouteRejectedError(
            "library_unsupported",
            f"{library.name!r} is a {library.collection_type or 'mixed'} library",
        )
    _check_profile(collection_type, profile)
    if target_path not in library.locations:
        # 路徑一律從 Jellyfin 讀，使用者只做選擇（brief §4.1）。
        raise RouteRejectedError(
            "target_not_in_library",
            f"{target_path!r} is not a path of {library.name!r} "
            f"(it has {', '.join(library.locations) or 'none'})",
        )
    paths = await read_settings(session, PathSettings)
    existing = tuple((await _existing_routes(session)).values())
    holder = next((route for route in existing if route.target_path == target_path), None)
    if holder is not None:
        # 帳本以目標路徑認 Route（`owning_route`）：兩條同一個目標就分不出檔案是誰的。
        raise RouteRejectedError("target_taken", f"{target_path!r} is already {holder.slug!r}")
    slug = _unique_slug(library.name, {route.slug for route in existing})
    plan_row = _Planned(
        slug=slug,
        library_name=library.name,
        library_item_id=library.item_id,
        collection_type=collection_type,
        target_path=target_path,
        category=f"{CATEGORY_PREFIX}{slug}",
        save_path=save_path_of(paths.complete_root, slug),
        profile=profile,
    )
    route = _new_route(plan_row, name=name, enabled=False)
    session.add(route)
    await session.commit()

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
    profile: Profile,
    enabled: bool,
) -> RouteView:
    """Route 設定頁的「修改」：名稱、profile、啟用（使用者拍板）。

    slug 與目標路徑不在這裡：category 與 complete 子目錄由 slug 導出，帳本以目標路徑認 Route，
    改了就是另一條 Route——要換就新增一條、刪掉舊的（Sonarr 的 root folder 同樣不能改路徑）。

    每一次修改都重跑五條纜繩（票 14 驗收）。**從停用到啟用**要那一輪全綠，否則拒絕並留在停用；
    名稱與 profile 照樣存下。已經啟用的 Route 這一輪變紅不會被停掉——它的紅燈本來就擋得住
    送單（`jobs._check_route`），默默替人停用反而是另一種隱式的改動。
    """
    route = await _find_route(session, route_id)
    _check_profile(route.collection_type, profile)
    route.name = name
    route.profile = profile
    await session.commit()

    paths = await read_settings(session, PathSettings)
    await _run_checks(session, factory, (_planned_from(route, paths),), (route,))
    if enabled and not route.enabled and route.health_status is not HealthStatus.OK:
        raise RouteRejectedError("route_unhealthy", route.slug)
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
class LibraryOption:
    """新增 Route 時可選的一個 Jellyfin 媒體庫（現查）。"""

    item_id: str
    name: str
    collection_type: str
    locations: tuple[str, ...]
    #: 已經有 Route 寫在那裡的路徑。
    taken: tuple[str, ...]
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
    targets = {route.target_path for route in (await _existing_routes(session)).values()}
    return tuple(
        LibraryOption(
            item_id=library.item_id,
            name=library.name,
            collection_type=library.collection_type,
            locations=library.locations,
            taken=tuple(path for path in library.locations if path in targets),
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


async def delete_route(session: AsyncSession, route_id: int) -> None:
    """Route 設定頁的「刪除」：一個明確、要二次確認的動作（票 14）。

    **被引用就拒絕**，理由是 `route_in_use`，出路是停用（`update_route`）：停用擋得住新的送單，
    又不讓已經發生的下載與入庫失去它們的 Route。qBittorrent 的 category 與 complete 子目錄
    不跟著刪——刪得了就代表沒有東西在用它們，而同一個 slug 之後重建時 category 檢查會認得它。
    """
    route = await _find_route(session, route_id)
    routes = tuple((await _existing_routes(session)).values())
    usage = (await _usages(session, routes))[route.id]
    if usage.in_use:
        raise RouteRejectedError(
            "route_in_use", f"jobs={usage.jobs} · ledger_entries={usage.ledger_entries}"
        )
    await session.delete(route)
    await session.commit()


async def _find_route(session: AsyncSession, route_id: int) -> Route:
    """設定頁的命令認的那一條。不在了是一個理由（`route_missing` → 404），不是 500。"""
    route = await session.get(Route, route_id)
    if route is None:
        raise RouteRejectedError("route_missing", str(route_id))
    return route


def _check_profile(collection_type: CollectionType, profile: Profile) -> None:
    """anime 是劇集的季集與命名規則（CONTEXT.md 的 Profile）；電影沒有這條路徑（票 14）。"""
    if profile is Profile.ANIME and collection_type is CollectionType.MOVIES:
        raise RouteRejectedError(
            "profile_unsupported", f"a {collection_type.value} route cannot use {profile.value}"
        )


async def _live_libraries(
    session: AsyncSession, factory: ServiceClientFactory
) -> tuple[JellyfinLibrary, ...]:
    """Jellyfin 現在報的媒體庫。問不到是一個理由（`jellyfin_unreachable`）而不是 500。"""
    settings = await read_settings(session, JellyfinSettings)
    jellyfin = factory.jellyfin(settings.base_url, token=settings.api_key)
    try:
        return await jellyfin.libraries()
    except ServiceError as exc:
        raise RouteRejectedError("jellyfin_unreachable", message(exc)) from exc
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
            "library_missing", f"Jellyfin has no library with id {library_id!r}"
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
        profile=route.profile,
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
            route.health_detail_json = health.model_dump(mode="json")
            route.health_status = HealthStatus.OK if passed else HealthStatus.FAILED
            # 逐個 commit：三個 Route 裡的第二個炸了，第一個的結果仍然留得下來。
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
    profile: Profile


def _plan(
    setup: SetupSettings,
    paths: PathSettings,
    selections: Sequence[RouteSelection],
    existing: Sequence[Route],
) -> tuple[_Planned, ...]:
    """套件內導出三個 Route；既有用使用者的勾選。無效的選擇丟 `ValueError`（→ 422）。

    已經有 Route 的媒體庫略過（精靈只新增，見 `build_routes`）；slug 與整張表比，不只與
    這一批比——Route 設定頁建的第二條（`tv-2`）也佔著名字。
    """
    libraries = {library.name: library for library in setup.jellyfin.libraries}
    chosen = (
        _bundled_selections(libraries)
        if _jellyfin_origin(setup) is ServiceOrigin.BUNDLED
        else selections
    )

    planned: list[_Planned] = []
    taken = {route.slug for route in existing}
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
        profile=plan_row.profile,
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
        profile=route.profile,
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
