"""`jellyfin_resolver`：入庫的檔案在 Jellyfin 裡是哪一個 item（plan §3.2、brief §20.1、票 12）。

`POST /Library/Media/Updated` 只是「去看看」：Jellyfin 收下之後自己排程去掃，掃完才有 item。
所以反查是**延遲的、會重試的**——第一次在入庫 30 秒後，之後隔 2 分、10 分、1 小時、1 小時、
1 小時，共 6 次（plan §3.2）。排程存在帳本那一列上（`resolve_after`），重啟不會把它忘掉。

**兩段查詢，都以媒體庫為 parent**（brief §20.1）：`GET /Items` 沒有路徑篩選，而
`parentId=<seriesId>` 在 10.11 第一次掃描後會回 0。第一段看作品資料夾是不是已經是一個 Series
（還不是的話，那一批集數連問都不必問）；第二段列媒體庫底下的集數，照路徑對到帳本的那一條。
電影一段就夠：電影的檔案就是 item 自己。

**比路徑，也比 `MediaSources`**：同一集或同一部電影的第二個版本，在多版本合併之後不是 item
自己的 `Path`，只是它底下的一個來源（brief §7.7）。

**沒找到的那幾條再通知一次**（plan §3.3「resolver 之後會再嘗試」）：入庫當下那一次通知可能沒
送到，或 Berth 在狀態落地與通知之間被關掉——那兩種情況下 Jellyfin 根本不知道要去掃。路徑級的
通知是冪等的，多送一次的代價只是一個請求。

**找到的那一刻順手記下版本名**（brief §7.7）：12.0 起劇集也原生合併，而版本選單上的名字是
Jellyfin 自己算的（去掉各版本檔名的共同前綴，算法連 12.0 與 12.1 都不一樣）。存進帳本之後，
詳情頁不必為了一行字再問一次 Jellyfin，也不必追著三種算法跑。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.http import ServiceError
from berth.adapters.jellyfin import (
    ITEM_EPISODE,
    ITEM_MOVIE,
    ITEM_SERIES,
    JellyfinClient,
    JellyfinItem,
    scan_libraries,
)
from berth.domain import CollectionType, EventType, IssueType
from berth.models import JellyfinSettings, Job, LedgerEntry, Media, Route
from berth.models.types import utcnow
from berth.services.clients import ServiceClientFactory
from berth.services.issues import record_issue
from berth.services.jobs import actor_of, record_event
from berth.services.routes import owning_route
from berth.services.settings import read_settings
from berth.services.steps import message

logger = logging.getLogger(__name__)

#: 第 n 次反查之前要等多久（plan §3.2）。長度就是總次數：6 次。
RESOLVE_DELAYS: tuple[timedelta, ...] = (
    timedelta(seconds=30),
    timedelta(minutes=2),
    timedelta(minutes=10),
    timedelta(hours=1),
    timedelta(hours=1),
    timedelta(hours=1),
)

#: 沒找到幾次之後改請 Jellyfin 掃描媒體庫（brief §20.1）。第一次沒找到多半只是路徑通知的 60 秒延遲
#: 還沒過；第二次還沒有，就是通知沒起作用——從來沒掃到過內容的媒體庫，通知往上找不到任何 item，
#: 靜靜地什麼都不做（2026-09-15 對 12.0.0 實測、查核 `FileRefresher.GetAffectedBaseItem`）。
SCAN_AFTER_MISSES = 2

#: 請 Jellyfin 掃描之後，下一次最晚多久再看。原本的間隔到後面是一小時，那是在等它自己的排程；
#: 已經開口請它掃了，就不必等那麼久。
SCAN_SETTLE = timedelta(minutes=10)


def first_resolve_at(now: datetime) -> datetime:
    """一筆剛寫下的帳本第一次反查的時間。importer 寫帳本時用它。"""
    return now + RESOLVE_DELAYS[0]


@dataclass(frozen=True, slots=True)
class ResolveOutcome:
    """一輪的結果。log 與測試看它。"""

    resolved: int
    retried: int
    exhausted: int


async def sweep_resolutions(
    session: AsyncSession, factory: ServiceClientFactory, *, now: datetime | None = None
) -> ResolveOutcome:
    """一輪：到時間的帳本逐條問 Jellyfin（plan §3.2 的 `jellyfin_resolver`）。

    **沒有到時間的就一個請求都不發**：這個迴圈醒得比最短的間隔頻繁，而大部分醒來的時候
    沒有東西要問。
    """
    moment = now or utcnow()
    due = list(
        await session.scalars(
            select(LedgerEntry)
            .where(LedgerEntry.resolve_after.is_not(None), LedgerEntry.resolve_after <= moment)
            .order_by(LedgerEntry.id)
        )
    )
    if not due:
        return ResolveOutcome(resolved=0, retried=0, exhausted=0)

    routes = list(await session.scalars(select(Route)))
    settings = await read_settings(session, JellyfinSettings)
    client = factory.jellyfin(settings.base_url, token=settings.api_key)
    found: list[LedgerEntry] = []
    waiting: list[LedgerEntry] = []
    given_up: list[LedgerEntry] = []
    try:
        for route, entries in _by_route(due, routes):
            items = await _look_up(session, client, route, entries)
            for entry in entries:
                item = locate(entry.target_path, items)
                if item is not None:
                    _remember(entry, item)
                    entry.resolve_after = None
                    found.append(entry)
                elif _reschedule(entry, moment):
                    given_up.append(entry)
                else:
                    waiting.append(entry)
        if await _remind(client, waiting):
            for entry in waiting:
                if entry.resolve_after is not None:
                    entry.resolve_after = min(entry.resolve_after, moment + SCAN_SETTLE)
        await _announce(session, found, given_up)
    finally:
        await client.aclose()
    await session.commit()
    return ResolveOutcome(resolved=len(found), retried=len(waiting), exhausted=len(given_up))


async def refresh_resolved(
    session: AsyncSession, client: JellyfinClient, entries: Sequence[LedgerEntry]
) -> int:
    """反查過的那幾條，照 Jellyfin **現在**的樣子重對一次。回傳改了幾條（M2 票 09）。

    兩件事都是「當時對的、現在不對了」，所以同一支：

    - **票 13 之前反查完的劇集沒有 Series id**：那一欄是票 13 才加的，媒體庫的卡片因此一直說
      「還在掃描」。migration 裡問不了 Jellyfin，所以由這裡補。
    - **Jellyfin 12 合併版本之後，反查到的那一個可能不再是主條目**（brief §20.9）：次要版本
      帶 `PrimaryVersionId`，一般查詢濾掉它，帳本那個檔案變成主條目底下的一個來源。`locate`
      本來就比 `MediaSources`，所以重對一次就會對到主條目。

    **找不到的那幾條不動**：「Jellyfin 現在沒列出它」可能是還在重掃、可能是它被刪了，而檔案
    在不在是媒體庫那一方的事。這一支只把找得到的換新，不清掉任何東西。

    Jellyfin 問不到時 `ServiceError` 往上丟：呼叫端（對帳的那一方）要說出「問不到」，而不是
    把「一條都沒改」當成「都對得上」。
    """
    routes = list(await session.scalars(select(Route)))
    changed = 0
    for route, group in _by_route(entries, routes):
        if route is None:
            continue
        items = await _items_for(session, client, route, group)
        for entry in group:
            item = locate(entry.target_path, items)
            if item is None:
                continue
            before = (
                entry.jellyfin_item_id,
                entry.jellyfin_series_id,
                entry.jellyfin_version_name,
            )
            _remember(entry, item)
            if before != (
                entry.jellyfin_item_id,
                entry.jellyfin_series_id,
                entry.jellyfin_version_name,
            ):
                changed += 1
    return changed


def _remember(entry: LedgerEntry, item: JellyfinItem) -> None:
    """找到了：item、它所屬的 Series、Jellyfin 替這個檔案算的版本名（brief §7.7）。"""
    entry.jellyfin_item_id = item.id
    entry.jellyfin_series_id = item.series_id
    entry.jellyfin_version_name = item.version_name(entry.target_path)


def locate(target_path: str, items: Sequence[JellyfinItem]) -> JellyfinItem | None:
    """帳本那一條路徑在 Jellyfin 裡是哪一個 item。

    也比 `source_paths`：多版本合併之後，第二個版本的檔案只是那個 item 底下的一個來源
    （brief §7.7）。
    """
    wanted = target_path.rstrip("/")
    for item in items:
        if item.path.rstrip("/") == wanted or wanted in item.source_paths:
            return item
    return None


def _reschedule(entry: LedgerEntry, now: datetime) -> bool:
    """這一次沒找到：排下一次，或者放棄。回傳「是不是放棄了」。"""
    entry.resolve_attempts += 1
    if entry.resolve_attempts >= len(RESOLVE_DELAYS):
        entry.resolve_after = None
        return True
    entry.resolve_after = now + RESOLVE_DELAYS[entry.resolve_attempts]
    return False


def _by_route(
    entries: Sequence[LedgerEntry], routes: Sequence[Route]
) -> list[tuple[Route | None, list[LedgerEntry]]]:
    """一條 Route 一個媒體庫、一次查詢。找不到 Route 的那幾筆（Route 被刪了）照樣算一次沒找到。"""
    groups: dict[int | None, tuple[Route | None, list[LedgerEntry]]] = {}
    for entry in entries:
        route = owning_route(entry.target_path, routes)
        key = route.id if route is not None else None
        groups.setdefault(key, (route, []))[1].append(entry)
    return list(groups.values())


async def _look_up(
    session: AsyncSession,
    client: JellyfinClient,
    route: Route | None,
    entries: Sequence[LedgerEntry],
) -> tuple[JellyfinItem, ...]:
    """這一批帳本可能對得到的那些 item（brief §20.1 的兩段查詢）。

    Jellyfin 連不上時回空的：那一次照樣算一次沒找到。服務掛了一小時的話 6 次會用掉幾次，
    而那正是「多次失敗記為 Issue」要讓人看見的事。
    """
    if route is None:
        return ()
    try:
        return await _items_for(session, client, route, entries)
    except ServiceError as exc:
        logger.warning(
            "jellyfin lookup failed; it counts as one try",
            extra={"route": route.slug, "error": message(exc)},
        )
        return ()


async def _items_for(
    session: AsyncSession,
    client: JellyfinClient,
    route: Route,
    entries: Sequence[LedgerEntry],
) -> tuple[JellyfinItem, ...]:
    """brief §20.1 的兩段查詢本身。問不到就丟 `ServiceError`，要不要吞掉是呼叫端的事。"""
    if route.collection_type is CollectionType.MOVIES:
        return await client.items(route.jellyfin_library_id, (ITEM_MOVIE,))
    series = await client.items(route.jellyfin_library_id, (ITEM_SERIES,))
    folders = await _scanned_folders(session, route, entries, series)
    if not folders:
        return ()
    episodes = await client.items(route.jellyfin_library_id, (ITEM_EPISODE,))
    return tuple(
        item for item in episodes if any(item.path.startswith(f"{folder}/") for folder in folders)
    )


async def _scanned_folders(
    session: AsyncSession,
    route: Route,
    entries: Sequence[LedgerEntry],
    series: Sequence[JellyfinItem],
) -> set[str]:
    """已經是一個 Series 的作品資料夾：路徑對得上，或 `ProviderIds.Tmdb` 對得上（brief §5.1）。"""
    root = PurePosixPath(route.target_path)
    ours: set[str] = set()
    for entry in entries:
        try:
            ours.add(str(root / PurePosixPath(entry.target_path).relative_to(root).parts[0]))
        except ValueError:
            # `_route_of` 比的是正規化之後的路徑（大小寫、`..`），這裡是逐字的。對不上的那一筆
            # 只剩 tmdb id 認得出來——而不能讓它丟出去：整輪回滾的話，這一批永遠用不完那 6 次。
            continue
    media_ids = {entry.media_id for entry in entries if entry.media_id is not None}
    tmdb_ids = {
        str(row.tmdb_id)
        for row in await session.scalars(select(Media).where(Media.id.in_(media_ids)))
    }
    return {
        item.path.rstrip("/")
        for item in series
        if item.path.rstrip("/") in ours or (item.tmdb_id and item.tmdb_id in tmdb_ids)
    }


async def _remind(client: JellyfinClient, entries: Sequence[LedgerEntry]) -> bool:
    """還沒找到的那幾條再通知一次；沒找到兩次以上就請 Jellyfin 掃描媒體庫。回傳「請它掃了沒」。

    **失敗只記 log**：這一次反查已經算過一次了。
    """
    if not entries:
        return False
    try:
        await client.notify_paths([entry.target_path for entry in entries])
        if all(entry.resolve_attempts < SCAN_AFTER_MISSES for entry in entries):
            return False
        if not await scan_libraries(client):
            logger.warning("jellyfin has no library scan task")
            return False
        logger.info("asked jellyfin to scan its libraries")
        return True
    except ServiceError as exc:
        logger.warning("jellyfin could not be reminded", extra={"error": message(exc)})
        return False


async def _announce(
    session: AsyncSession, found: Sequence[LedgerEntry], given_up: Sequence[LedgerEntry]
) -> None:
    """一筆 Job 一行，不是一個檔案一行：一季 24 集的時間線不該被 24 行「找到了」淹沒。"""
    for job, entries in await _by_job(session, found):
        await record_event(
            session,
            job,
            EventType.JELLYFIN_ITEM_RESOLVED,
            actor=actor_of(None),
            payload={"count": len(entries)},
        )
    for job, entries in await _by_job(session, given_up):
        # 事件是**一筆 Job 一行**（時間線不該被 24 集淹沒），Issue 是**一列帳本一件**
        # ——它的冪等鍵是 `ledger_id`（plan §2.4）：同一筆 Job 的兩集各自反查、各自放棄，
        # 而使用者是逐集去 Jellyfin 看它把那個檔案認成了什麼。
        await record_event(
            session,
            job,
            EventType.ISSUE_DETECTED,
            actor=actor_of(None),
            payload={
                "type": IssueType.JELLYFIN_ITEM_UNRESOLVED.value,
                "count": len(entries),
                "paths": [entry.target_path for entry in entries],
            },
        )
        logger.warning("jellyfin never showed these files", extra={"count": len(entries)})

    for entry in given_up:
        await record_issue(
            session,
            IssueType.JELLYFIN_ITEM_UNRESOLVED,
            path=entry.target_path,
            job_hash=entry.job_hash,
            ledger_id=entry.id,
            detail={
                "type": IssueType.JELLYFIN_ITEM_UNRESOLVED.value,
                "attempts": entry.resolve_attempts,
                "media": entry.media_id,
            },
        )


async def _by_job(
    session: AsyncSession, entries: Sequence[LedgerEntry]
) -> list[tuple[Job, list[LedgerEntry]]]:
    """帳本的 `job_hash` 是弱引用：Job 已經刪掉的那幾筆沒有時間線可寫。"""
    grouped: dict[str, list[LedgerEntry]] = {}
    for entry in entries:
        if entry.job_hash is not None:
            grouped.setdefault(entry.job_hash, []).append(entry)
    rows = []
    for job_hash, group in grouped.items():
        job = await session.get(Job, job_hash)
        if job is not None:
            rows.append((job, group))
    return rows
