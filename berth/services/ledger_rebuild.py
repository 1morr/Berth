"""`berth rebuild-ledger`：帳本從磁碟上長回來（plan §11.3 決定 9、M2 票 10）。

逐 Route 走完媒體庫，帳本不認得的每一個檔案交給 `claims.claim_file`：配得上的長回完整一列
（季、集、Tags 從目標路徑反解），**配不到的一律建 `unmanaged_library_file` Issue，不猜**，理由
寫在 `detail_json.reason`（`ClaimMiss`）。只加不減：一個位元組都不刪。

與「認領進帳本」那一顆同一個原語（`claim_file`），差在範圍：這一支走整個媒體庫，那一顆只做一個
檔案。住在 `claims` 外面是因為它要寫 Issue，而 `services/issues` 反過來要呼叫 `claims`。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import fs
from berth.domain import ClaimMiss, IssueType
from berth.models import LedgerEntry, Route
from berth.models.types import utcnow
from berth.services.claims import (
    UnclaimedError,
    claim_file,
    source_index,
)
from berth.services.clients import ServiceClientFactory
from berth.services.issues import record_issue

logger = logging.getLogger(__name__)

#: 帳本長回來、那一件 Issue 跟著收掉時寫的是誰：CLI 沒有登入的人。
SYSTEM = "system"


@dataclass(slots=True)
class RebuildReport:
    """一次 `rebuild-ledger` 做了什麼。CLI 把它印出來。"""

    #: 本來就在帳本上、不必動的檔案數。
    known: int = 0
    #: 長回帳本的檔案數。
    claimed: int = 0
    #: 配不上、變成（或仍是）一件 `unmanaged_library_file` 的檔案數，逐種理由。
    unmatched: dict[ClaimMiss, int] = field(default_factory=dict)
    #: 目標目錄讀不到而整條跳過的 Route（原文）。
    skipped: list[str] = field(default_factory=list)
    #: 讀不到的 complete 子目錄（原文）。有它的時候配不到來源的檔案不開 Issue，只數在 `undecided`。
    unread_complete: list[str] = field(default_factory=list)
    #: 配不到來源、但 complete 沒讀全所以說不出它是不是真的沒有來源的檔案數。
    undecided: int = 0


async def rebuild_ledger(
    session: AsyncSession, factory: ServiceClientFactory, *, now: datetime | None = None
) -> RebuildReport:
    """逐 Route 走完媒體庫：帳本不認得的每一個檔案，配得上的長回一列，配不上的開一件 Issue。

    **只加不減**：帳本上已經有、磁碟上卻不在的那幾列不在這裡收——那是對帳的 `library_link_missing`，
    要人決定。complete 的 inode 索引整輪只建一次（一個檔案問一次的話，一千個檔案就是走一千次
    complete）。讀不到的那一條 Route 整條跳過並說出來，與對帳同一個規矩（brief §16.2）；complete
    有子目錄讀不到時，配不到來源的那幾個檔案也不開 Issue——問不到不算不見了。
    """
    moment = now or utcnow()
    report = RebuildReport()
    known = {fs.path_key(row) for row in await session.scalars(select(LedgerEntry.target_path))}
    index = await source_index(session)
    report.unread_complete = list(index.unread)
    for route in list(await session.scalars(select(Route).order_by(Route.id))):
        try:
            files = fs.files_under(Path(route.target_path))
        except OSError as exc:
            report.skipped.append(f"{route.name} ({route.target_path}): {exc}")
            continue
        for path in files:
            if fs.path_key(path) in known:
                report.known += 1
                continue
            try:
                entry = await claim_file(
                    session, factory, path, index=index, now=moment, actor=SYSTEM
                )
            except UnclaimedError as miss:
                if miss.reason is ClaimMiss.NO_SOURCE and index.unread:
                    report.undecided += 1
                    continue
                report.unmatched[miss.reason] = report.unmatched.get(miss.reason, 0) + 1
                await record_issue(
                    session,
                    IssueType.UNMANAGED_LIBRARY_FILE,
                    path=str(path),
                    detail={"reason": miss.reason.value},
                    now=moment,
                )
                continue
            known.add(fs.path_key(entry.target_path))
            report.claimed += 1
    await session.commit()
    logger.info(
        "ledger rebuilt",
        extra={
            "claimed": report.claimed,
            "unmatched": sum(report.unmatched.values()),
            "skipped": len(report.skipped),
            "undecided": report.undecided,
        },
    )
    return report
