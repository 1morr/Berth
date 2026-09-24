"""`health_checker` 量出來的兩種 Issue（M2 票 09c）：媒體庫掛了 TVDB、磁碟剩的空間低於門檻。

M0 起這兩件事只是畫面上的一行字（Route 設定頁的 TVDB 提示、`hardlink` 纜繩上的 `free=`），
沒有人會在出事的那一刻看到。變成 Issue 之後它們進 `/issues` 與 Review Queue，與其餘十一種
同一個載體、同一個冪等鍵（`record_issue`）。

兩條規則是這兩種獨有的：

- **條件解除時由系統收掉**（`resolved_by = system`）。它們沒有 Berth 按得了的修法——使用者在
  Jellyfin 或磁碟上修好之後，Issue 不該還開著等人按「忽略」。
- **忽略在條件持續期間有效**（2026-09-23 使用者拍板）。其餘幾種的「忽略」是「這一次不處理」，
  下一次偵測到就開新的一筆；對 5 分鐘量一次的東西那等於忽略無效，而故意掛 TVDB 的使用者
  會被每 5 分鐘問一次。所以最後一筆是 `ignored` 的就不重開；條件解除過一次（在那一筆的
  `detail_json.cleared_at` 記下來），之後再發生才重開。

**問不到就不判**（brief §16.2）：Jellyfin 問不到時 TVDB 那一種整種不動，某個根目錄量不到時
那一條不動——「問不到」不是「好了」。
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import fs
from berth.adapters.http import ServiceError
from berth.adapters.jellyfin import JellyfinLibrary
from berth.domain import IssueStatus, IssueType
from berth.models import DiskSettings, Issue, JellyfinSettings, PathSettings, Route
from berth.models.types import utcnow
from berth.services.clients import ServiceClientFactory
from berth.services.issues import record_issue
from berth.services.jellyfin import tvdb_fetchers
from berth.services.settings import read_settings, write_settings

logger = logging.getLogger(__name__)

#: 條件解除時收掉那一件的人（plan §2.4 的 `resolved_by`，與 poller 的事件同一個字）。
SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class Finding:
    """這一輪量完的結果：哪幾個 subject 有問題、哪幾個這一輪量不到。

    其餘的（量到了、沒問題）就是「條件解除」——包括已經不存在的那幾個（Route 被刪了、
    根目錄改了），它們的 Issue 說的事也不再是現況。
    """

    flagged: Mapping[str, dict[str, Any]]
    unknown: frozenset[str] = frozenset()


async def watch_conditions(
    session: AsyncSession, factory: ServiceClientFactory, *, now: datetime | None = None
) -> None:
    """兩種各量一次、寫下或收掉（`health_checker` 每一輪的最後一步）。**會 commit**。"""
    moment = now or utcnow()
    tvdb = await _tvdb(session, factory)
    if tvdb is not None:
        await _settle(session, IssueType.LIBRARY_USES_TVDB, tvdb, moment)
    await _settle(session, IssueType.LOW_DISK_SPACE, await _disk(session), moment)
    await session.commit()


async def set_min_free(
    session: AsyncSession, gigabytes: int, *, now: datetime | None = None
) -> int:
    """改門檻，並**立刻重量一次**：量磁碟不連任何服務，使用者改完不必等下一輪 5 分鐘。"""
    settings = await read_settings(session, DiskSettings)
    settings.min_free_gb = gigabytes
    await write_settings(session, settings)
    await _settle(session, IssueType.LOW_DISK_SPACE, await _disk(session), now or utcnow())
    await session.commit()
    return settings.min_free_gb


async def read_min_free(session: AsyncSession) -> int:
    return (await read_settings(session, DiskSettings)).min_free_gb


# --- 兩種量法 -------------------------------------------------------------


async def _tvdb(session: AsyncSession, factory: ServiceClientFactory) -> Finding | None:
    """每一條 Route 的媒體庫掛不掛 TVDB。**Jellyfin 問不到就回 `None`**：整種不動。

    媒體庫以 `ItemId` 認，沒有才用名字（`services/routes._is_library` 的同一條規則）。
    Jellyfin 上已經找不到那個媒體庫的 Route 不算有問題——那是 Route 的纜繩要報的事。
    """
    settings = await read_settings(session, JellyfinSettings)
    if not settings.base_url:
        return None
    client = factory.jellyfin(settings.base_url, token=settings.api_key)
    try:
        libraries = await client.libraries()
    except ServiceError as exc:
        logger.info("skipping the TVDB check: Jellyfin did not answer", extra={"error": str(exc)})
        return None
    finally:
        await client.aclose()

    flagged: dict[str, dict[str, Any]] = {}
    for route in await session.scalars(select(Route)):
        library = next((row for row in libraries if _is_library(row, route)), None)
        fetchers = tvdb_fetchers(library) if library is not None else ()
        if library is not None and fetchers:
            flagged[route.target_path] = {
                "route": route.name,
                "library": library.name,
                "fetchers": list(fetchers),
            }
    return Finding(flagged=flagged)


def _is_library(library: JellyfinLibrary, route: Route) -> bool:
    if route.jellyfin_library_id:
        return library.item_id == route.jellyfin_library_id
    return library.name == route.jellyfin_library_name


async def _disk(session: AsyncSession) -> Finding:
    """incomplete 與 complete 兩個根目錄各剩多少。

    **同一個檔案系統只量一次**，complete 先：兩者多半在同一個掛載上（硬鏈接的硬規則把 complete
    與媒體庫綁在一起，incomplete 通常也在同一棵），同一件事開兩筆只是雜訊。incomplete 單獨
    在另一顆磁碟上時它自己一件——正在長大的是那一顆。

    Route 的目標不另外量：它與 complete 在同一個檔案系統上（`hardlink` 纜繩就在驗這件事）。
    """
    threshold = (await read_settings(session, DiskSettings)).min_free_bytes
    paths = await read_settings(session, PathSettings)
    flagged: dict[str, dict[str, Any]] = {}
    unknown: set[str] = set()
    devices: set[int] = set()
    for root in dict.fromkeys((paths.complete_root, paths.incomplete_root)):
        if not root:
            continue
        try:
            device = fs.stat(Path(root)).device
            free = fs.free_space(Path(root))
        except OSError:
            # 沒掛上或看不到：`download_path` 纜繩在報這件事，這裡不把它說成「空間夠」。
            unknown.add(root)
            continue
        if device in devices:
            continue
        devices.add(device)
        if threshold > 0 and free < threshold:
            flagged[root] = {"free": free, "min_free": threshold}
    return Finding(flagged=flagged, unknown=frozenset(unknown))


# --- 寫下與收掉 -----------------------------------------------------------


async def _settle(session: AsyncSession, kind: IssueType, finding: Finding, now: datetime) -> None:
    """有問題的寫下（忽略過的除外），其餘開著的收掉、忽略過的記下「解除過了」。"""
    for subject, detail in finding.flagged.items():
        if await _still_ignored(session, kind, subject):
            continue
        await record_issue(session, kind, path=subject, detail=detail, now=now)

    rows = await session.scalars(
        select(Issue).where(
            Issue.type == kind, Issue.status.in_((IssueStatus.OPEN, IssueStatus.IGNORED))
        )
    )
    for row in rows:
        if row.subject in finding.flagged or row.subject in finding.unknown:
            continue
        if row.status is IssueStatus.OPEN:
            row.status = IssueStatus.RESOLVED
            row.resolved_at = now
            row.resolved_by = SYSTEM
            logger.info("issue cleared", extra={"issue": kind.value, "subject": row.subject})
        elif "cleared_at" not in (row.detail_json or {}):
            row.detail_json = {**(row.detail_json or {}), "cleared_at": now.isoformat()}
    await session.flush()


async def _still_ignored(session: AsyncSession, kind: IssueType, subject: str) -> bool:
    """這件事最後一次是被忽略的，而且從那之後條件一直沒解除過。"""
    last = await session.scalar(
        select(Issue)
        .where(Issue.type == kind, Issue.subject == subject)
        .order_by(Issue.id.desc())
        .limit(1)
    )
    return (
        last is not None
        and last.status is IssueStatus.IGNORED
        and "cleared_at" not in (last.detail_json or {})
    )
