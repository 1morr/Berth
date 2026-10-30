"""換一台 qBittorrent / Prowlarr 之前，列出 Berth 在現在這一台留下的東西（M4 票 47，ADR-0013）。

換台的確認框問的是「現在存著的那一台」：按下確認之前它還是 Berth 在用的那一台，按下之後就成了舊的。
所以這裡讀的是存下的連線，不收位址。

**只列 Berth 擁有的物件**（brief §16.4，D1）：`berth-*` 分類（各有幾個 torrent）、Berth 加進
Prowlarr 的站、Berth 設的介面登入。使用者自己的分類與站不出現。那一台連不到時列 Berth 記得的：
分類是 Route 的、站是加站時記下的（`SetupIndexer.added_sites`），torrent 數說不出來。

**還在下載的 Job 也列出**（M4 票 102）：它們的 torrent 留在原本那一台，換台之後新那一台上
找不到，poller 照 plan §3.1 把它們變成 `client_removed`——那件 Issue 的「重新送單」送到的
就是新那一台。換台框照實說，換台本身不改它們的狀態。

**能移除的只有空的 `berth-*` 分類**：站與登入只列出——站可能有人在用、登入拿掉就沒人登得進去，
而 Berth 分不出來；空的分類刪掉不影響任何 torrent。移除是換台框裡的勾選，**跟著確認換台一起做**
（`setup.choose_service`，M4 票 65，審計 P2-9）：原本按下就刪，之後取消換台，分類已經沒了。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceError
from berth.adapters.qbittorrent import QbittorrentClient
from berth.domain import ServiceKind, StepFailure
from berth.models import IndexerSettings, Job, QbittorrentSettings, SetupSettings
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, Flag, command
from berth.services.jobs import IN_CLIENT_STATES
from berth.services.qbittorrent import route_categories, try_sign_in
from berth.services.routes import CATEGORY_PREFIX
from berth.services.settings import read_settings
from berth.services.steps import failure_of, message


class CategoriesNotRemovedError(Exception):
    """移除時連不到、或 qBittorrent 沒收下：什麼都沒刪（或不知道刪了沒），訊息是原文。"""


@dataclass(frozen=True, slots=True)
class LeftoverCategory:
    name: str
    #: 裡面有幾個 torrent。那一台連不到時是 `None`：列的是 Berth 記得的，數不出來。
    torrents: int | None


@dataclass(frozen=True, slots=True)
class LeftoverJob:
    """還在原本那一台下載的一筆 Job（`Leftovers.in_flight`）。"""

    hash: str
    name: str


@dataclass(frozen=True, slots=True)
class Leftovers:
    kind: ServiceKind
    base_url: str
    #: 連得到那一台：清單是它現在的樣子。連不到時是 Berth 記得建過的，沒辦法確認現況。
    reachable: bool
    #: qBittorrent 的 `berth-*` 分類，依名字排序；Prowlarr 是空的。
    categories: tuple[LeftoverCategory, ...]
    #: Berth 加進 Prowlarr 的站名；qBittorrent 是空的。
    sites: tuple[str, ...]
    #: Berth 在那一台設的介面帳號；沒設過（或是那一台自己設的）是空字串。
    login: str
    #: 連不到時為什麼（M4 票 21 的代碼與原文）；連得到是 `None` 與空字串。
    failure: StepFailure | None = None
    error: str = ""
    #: 還在下載的 Job（qBittorrent 才有）：torrent 留在原本那一台，新那一台上找不到時
    #: poller 會把它們變成 `client_removed`（M4 票 102）。讀的是 Berth 自己的 Job，
    #: 連不到那一台也列得出。
    in_flight: tuple[LeftoverJob, ...] = ()


@command(Effect.READ)
async def read_leftovers(
    session: AsyncSession, factory: ServiceClientFactory, kind: ServiceKind
) -> Leftovers:
    """換台確認框的清單。只給 qBittorrent 與 Prowlarr：Jellyfin 在擁有者成立之後換不了來源。"""
    if kind is ServiceKind.QBITTORRENT:
        return await _qbittorrent_leftovers(session, factory)
    if kind is ServiceKind.PROWLARR:
        return await _prowlarr_leftovers(session, factory)
    raise ValueError(f"{kind}: only qbittorrent and prowlarr list leftovers")


# 回不去：刪掉之前 Berth 沒記它的路徑，不是 Route 的那幾個（審計 S2 舊 QA 留下的那種）
# Berth 建不回來。
@command(Effect.IRREVERSIBLE, flags={Flag.INTERNAL, Flag.SETTINGS})
async def remove_empty_categories(
    session: AsyncSession, factory: ServiceClientFactory
) -> tuple[str, ...]:
    """移除現在存著的這一台 qBittorrent 上空的 `berth-*` 分類，回傳移除了哪幾個。換台時在存下
    新那一台之前呼叫（`setup.choose_service`）。

    **確認時重數**：清單畫出來之後可能有 torrent 進了某個分類，刪掉它會讓那個 torrent 變成沒有分類。
    連不到或刪不掉是 `CategoriesNotRemovedError`：勾了移除要說得出沒有移除，不能看起來像刪完了。
    """
    settings = await read_settings(session, QbittorrentSettings)
    client = factory.qbittorrent(settings.base_url)
    try:
        counted = await _count_categories(client, settings)
        empty = [name for name, torrents in counted.items() if torrents == 0]
        if empty:
            await client.remove_categories(empty)
    except ServiceError as exc:
        raise CategoriesNotRemovedError(message(exc)) from exc
    finally:
        await client.aclose()
    return tuple(empty)


async def _qbittorrent_leftovers(session: AsyncSession, factory: ServiceClientFactory) -> Leftovers:
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, QbittorrentSettings)
    login = setup.qbittorrent.web_ui_username if setup.qbittorrent.web_ui_password_hash else ""
    in_flight = await _in_flight(session)
    client = factory.qbittorrent(settings.base_url)
    try:
        counted = await _count_categories(client, settings)
    except ServiceError as exc:
        remembered = sorted(await route_categories(session))
        return _unreachable(
            ServiceKind.QBITTORRENT,
            settings.base_url,
            exc,
            categories=tuple(LeftoverCategory(name, None) for name in remembered),
            login=login,
            in_flight=in_flight,
        )
    finally:
        await client.aclose()
    return Leftovers(
        kind=ServiceKind.QBITTORRENT,
        base_url=settings.base_url,
        reachable=True,
        categories=tuple(LeftoverCategory(name, counted[name]) for name in sorted(counted)),
        sites=(),
        login=login,
        in_flight=in_flight,
    )


async def _in_flight(session: AsyncSession) -> tuple[LeftoverJob, ...]:
    """poller 每一輪到 qBittorrent 裡找的那幾筆（`IN_CLIENT_STATES`）。已經是待處理、
    送單失敗的不算：它們本來就不在清單上等著。"""
    rows = await session.execute(
        select(Job.hash, Job.name).where(Job.state.in_(IN_CLIENT_STATES)).order_by(Job.name)
    )
    return tuple(LeftoverJob(hash=row.hash, name=row.name) for row in rows)


async def _count_categories(
    client: QbittorrentClient, settings: QbittorrentSettings
) -> dict[str, int]:
    """那一台上每個 `berth-*` 分類裡有幾個 torrent。`sync` 在新的 client 上就是全量。"""
    failed = await try_sign_in(client, settings)
    if failed is not None:
        raise failed
    names = [row.name for row in await client.categories() if row.name.startswith(CATEGORY_PREFIX)]
    inside = Counter(row.category for row in await client.sync())
    return {name: inside[name] for name in names}


async def _prowlarr_leftovers(session: AsyncSession, factory: ServiceClientFactory) -> Leftovers:
    setup = await read_settings(session, SetupSettings)
    settings = await read_settings(session, IndexerSettings)
    added = setup.indexer.added_sites
    login = setup.indexer.web_ui_username if setup.indexer.web_ui_password_hash else ""
    client = factory.prowlarr(settings.base_url, settings.api_key)
    try:
        present = await client.indexers()
    except ServiceError as exc:
        return _unreachable(
            ServiceKind.PROWLARR,
            settings.base_url,
            exc,
            sites=tuple(added.values()),
            login=login,
        )
    finally:
        await client.aclose()
    return Leftovers(
        kind=ServiceKind.PROWLARR,
        base_url=settings.base_url,
        reachable=True,
        categories=(),
        sites=tuple(row.name for row in present if row.definition_name in added),
        login=login,
    )


def _unreachable(
    kind: ServiceKind,
    base_url: str,
    exc: ServiceError,
    *,
    categories: tuple[LeftoverCategory, ...] = (),
    sites: tuple[str, ...] = (),
    login: str,
    in_flight: tuple[LeftoverJob, ...] = (),
) -> Leftovers:
    failure, _ = failure_of(exc)
    return Leftovers(
        kind=kind,
        base_url=base_url,
        reachable=False,
        categories=categories,
        sites=sites,
        login=login,
        failure=failure,
        error=message(exc),
        in_flight=in_flight,
    )
