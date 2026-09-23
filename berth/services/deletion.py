"""刪除範圍：四個可組合的旗標與空間估算（brief §9.2、plan §3.1 的 `delete_job`、M2 票 04）。

**這是 M2 的第一個原語**：票 06 的 audit 撤銷、票 08 的 rematch、票 05 Issue 的「連 complete
一起刪」都走它，所以它自己那一層要說得準。

四個旗標各自只做一件事，順序不能換：

1. **從 qBittorrent 移除 torrent**。排第一是因為它是唯一可能失敗的一步——問不到那一台時
   整次刪除不做，而不是刪到一半才發現。
2. **移除 library 硬鏈接**。
3. **刪除 complete 檔案**。要求先移除 torrent（否則拒絕）：qBittorrent 還握著那個 torrent
   時把檔案抽走，它會報 `missingFiles` 然後在重新檢查時把整包再抓一遍。
4. **清除帳本與 Job 紀錄**。不勾的話那一筆留著當歷史，狀態是 `removed`。

**檔案由 Berth 自己逐檔刪，不交給 `torrents/delete?deleteFiles=true`**。兩個理由：那一筆
torrent 可能早就不在客戶端了（`client_removed`），而 Berth 仍然要刪得掉磁碟上的東西；而且
時間線要說得出刪了幾個、空出多少位元組，交出去就只剩「送出了一個請求」。

**空間估算逐一 `stat`**（慢而準，brief §9.2）。硬鏈接底下「檔案大小的總和」不是答案——
一份資料有幾個名字就有幾條路徑指著它，只有**最後一個**名字消失時那些位元組才回到檔案
系統。所以這裡先把要刪的路徑按 `(device, inode)` 分組，一組的路徑數等於它的 `st_nlink`
時才算進「真的會釋放」，少一個就是有別人（Jellyfin 外的第二條 Route、使用者自己的鏈接）
還握著它。
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import fs
from berth.adapters.http import ServiceError
from berth.domain import EventType, JobRefusal, JobState, LedgerStatus
from berth.logs import job_context
from berth.models import Event, Job, JobFile, LedgerEntry, PathSettings, QbittorrentSettings, Route
from berth.services.clients import ServiceClientFactory
from berth.services.jobs import JobRejectedError, job_lock, record_event, transition
from berth.services.qbittorrent import sign_in
from berth.services.settings import read_settings
from berth.services.steps import message

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DeleteScope:
    """要刪掉哪幾樣（brief §9.2）。**四個預設全不勾**（2026-09-22 定）。

    Sonarr 的對話框預設勾「同時刪除檔案」，但這裡的刪除以 Job 為單位而不是作品，預設刪檔
    會誤刪還在做種的東西。預設值寫在這裡而不只寫在 UI 上：對話框以外的呼叫端（Issue 的
    修復動作、票 06 的 audit 撤銷）拿到的預設要是同一組。
    """

    #: 移除 library 硬鏈接。Jellyfin 會在下次掃描少掉它。
    unlink: bool = False
    #: 從 qBittorrent 移除 torrent，不刪檔。
    remove_torrent: bool = False
    #: 刪除 complete 檔案。要求 `remove_torrent`。
    delete_files: bool = False
    #: 清除帳本與 Job 紀錄。不勾的話留為歷史。
    purge: bool = False


@dataclass(frozen=True, slots=True)
class DeletionEstimate:
    """對話框打開時算的那一份（brief §9.2）。每一個數字都是剛剛 `stat` 出來的。

    `reclaimable` 與 `held` 加起來才是「Berth 手上這些檔案有多大」：前者是**來源與所有
    鏈接都刪掉時**真的空出來的，後者是有別人也握著、刪了也不會空出來的。畫面要說清楚這
    件事，不然使用者會以為勾一個就能拿回一份。
    """

    #: 帳本上、磁碟上還在的媒體庫鏈接數。
    links: int
    #: 帳本上有、磁碟上已經不在的（有人在 Jellyfin 或檔案總管裡刪掉了）。
    links_missing: int
    #: 那幾個鏈接的大小合計。**不是可釋放的量**：它們與來源是同一份資料。
    link_bytes: int
    #: complete 底下還在的來源檔數。
    sources: int
    sources_missing: int
    source_bytes: int
    #: 來源與所有鏈接都刪掉時真的會空出來的位元組。
    reclaimable: int
    #: Berth 不知道的第三個名字握著、刪了也不會空出來的位元組。
    held: int


@dataclass(frozen=True, slots=True)
class DeleteOutcome:
    """**真的發生了什麼**，不是「勾了哪幾個」。

    兩者不一樣：勾了「移除鏈接」而那幾個檔案早就被人刪掉時，這裡的 `links` 是 0。時間線
    與畫面說的都是這一份。
    """

    links: int
    sources: int
    torrent: bool
    purged: bool
    freed: int


async def estimate_deletion(session: AsyncSession, job_hash: str) -> DeletionEstimate:
    """這一筆刪下去會空出多少（brief §9.2）。**只讀，不改任何東西。**

    慢是刻意的：逐一 `stat` 每一個來源與目標，不用 qBittorrent 報的 `total_size` 去猜——
    那是 torrent 的大小，而磁碟上可能只下載了一部分、可能有人手動刪過幾個檔案。
    """
    job = await _job(session, job_hash)
    paths = await _scope_paths(session, job)
    facts = _measure(paths.links + paths.sources)
    links = _measure(paths.links)
    sources = _measure(paths.sources)
    return DeletionEstimate(
        links=len(links.found),
        links_missing=len(paths.links) - len(links.found),
        link_bytes=links.bytes,
        sources=len(sources.found),
        sources_missing=len(paths.sources) - len(sources.found),
        source_bytes=sources.bytes,
        reclaimable=facts.reclaimable,
        held=facts.bytes - facts.reclaimable,
    )


async def delete_job(
    session: AsyncSession,
    factory: ServiceClientFactory,
    job_hash: str,
    scope: DeleteScope,
    *,
    actor: str,
) -> DeleteOutcome:
    """照 `scope` 刪掉這一筆的東西，Job 進 `removed`（plan §3.1 的最後一列）。

    **拒絕都在前面**：做不了的那兩種（沒有這個 Job、勾錯組合）在碰任何東西之前就停下來，
    向 qBittorrent 移除那一步也排在動磁碟之前——刪到一半才失敗是最難收拾的結果。
    """
    job = await _job(session, job_hash)
    if scope.delete_files and not scope.remove_torrent:
        raise JobRejectedError(
            JobRefusal.DELETE_FILES_REQUIRES_REMOVE_TORRENT,
            "qBittorrent would fetch the files again on its next recheck",
        )

    with job_context(job.hash):
        # poller 與 importer 也寫這一列，而這一支會把它們腳下的檔案抽走。
        async with job_lock(job.hash):
            return await _apply(session, factory, job, scope, actor=actor)


async def _apply(
    session: AsyncSession,
    factory: ServiceClientFactory,
    job: Job,
    scope: DeleteScope,
    *,
    actor: str,
) -> DeleteOutcome:
    """鎖裡面的那一段。抽出來是為了讓 `job_lock` 包得住整段而不必再縮排一層。"""
    paths = await _scope_paths(session, job)
    # **先量再刪**：`st_nlink` 在刪掉第一個名字之後就變了，事後算不出「這一次空出多少」。
    before = _measure(
        (paths.links if scope.unlink else []) + (paths.sources if scope.delete_files else [])
    )

    if scope.remove_torrent:
        await _remove_torrent(session, factory, job)

    links = _remove_all(paths.links, roots=paths.route_targets) if scope.unlink else 0
    sources = _remove_all(paths.sources, roots=[paths.complete_root]) if scope.delete_files else 0
    await _restate_ledger(session, job, scope)

    outcome = DeleteOutcome(
        links=links,
        sources=sources,
        torrent=scope.remove_torrent,
        purged=scope.purge,
        freed=before.reclaimable,
    )
    await _record(session, job, outcome, actor=actor)
    if scope.purge:
        await _purge(session, job)
    await session.commit()
    logger.info(
        "job deleted",
        extra={"links": links, "sources": sources, "purged": scope.purge, "freed": outcome.freed},
    )
    return outcome


async def _remove_torrent(session: AsyncSession, factory: ServiceClientFactory, job: Job) -> None:
    """從 qBittorrent 移除，**不刪檔**（brief §9.2 的第二個旗標）。

    它沒有這個 hash 時也是成功（brief §20.2 實測原始碼），所以不先問一次它還在不在——
    多一次往返只會讓「剛好在這中間被刪掉」變成一個要處理的競態。
    """
    settings = await read_settings(session, QbittorrentSettings)
    client = factory.qbittorrent(settings.base_url)
    try:
        await sign_in(client, settings)
        await client.delete_torrent(job.hash, delete_files=False)
    except ServiceError as exc:
        raise JobRejectedError(JobRefusal.CLIENT_UNREACHABLE, message(exc)) from exc
    finally:
        await client.aclose()


@dataclass(frozen=True, slots=True)
class _ScopePaths:
    """這一筆在磁碟上佔著的每一條路徑，加上刪除守衛用的兩組根。"""

    links: list[Path]
    sources: list[Path]
    route_targets: list[Path]
    complete_root: Path


async def _scope_paths(session: AsyncSession, job: Job) -> _ScopePaths:
    """媒體庫那一側讀帳本，complete 那一側讀 `job_files` 與帳本的來源。

    兩邊都讀是因為它們各自會少一半：`job_files` 是 qBittorrent 報的完整內容（包含沒有進
    Plan 的那幾個，例如 readme 與被跳過的樣本檔），而帳本的 `source_abs_path` 認得重新入庫
    那種沒有 `job_files` 的 Job（brief §9.3）。去重靠正規化後的字串。
    """
    entries = list(
        await session.scalars(select(LedgerEntry).where(LedgerEntry.job_hash == job.hash))
    )
    files = list(await session.scalars(select(JobFile).where(JobFile.job_hash == job.hash)))
    paths = await read_settings(session, PathSettings)
    return _ScopePaths(
        links=_unique(Path(row.target_path) for row in entries),
        sources=_unique(
            [Path(row.source_abs_path) for row in entries]
            + [fs.under(job.save_path, row.rel_path) for row in files if job.save_path]
        ),
        route_targets=await route_targets(session),
        complete_root=Path(paths.complete_root),
    )


@dataclass(frozen=True, slots=True)
class _Measured:
    """一組路徑量出來的事實。"""

    #: 磁碟上真的看得到的那幾條。
    found: list[Path]
    #: 它們佔的位元組，一份資料只算一次（同一個 inode 的兩條路徑不是兩份）。
    bytes: int
    #: 這幾條**全部**刪掉時真的會空出來的位元組。
    reclaimable: int


def _measure(paths: Sequence[Path]) -> _Measured:
    """逐一 `stat`，再按 `(device, inode)` 分組。

    分組是整段估算的關鍵：同一份資料的來源與鏈接會落在同一組，所以它的大小只算一次；而
    一組裡的**名字數**等於 `links` 時，刪掉這一組就是刪掉這份資料的最後一個名字。

    一組裡收的是**正規化後的路徑集合**而不是計數器：同一個檔案被兩條寫法不同的路徑指到時
    （帳本記的來源與 `job_files` 組出來的，qBittorrent 搬過家之後就會分岔）它仍然只是一個
    名字。當成兩個算的話，只刪來源看起來就像連最後一個名字都刪掉了——畫面於是報出一個根本
    不會發生的釋放量，而媒體庫那一半明明還在。
    """
    names: dict[tuple[int, int], set[str]] = defaultdict(set)
    facts: dict[tuple[int, int], fs.PathFacts] = {}
    found: list[Path] = []
    for path in paths:
        try:
            info = fs.stat(path)
        except OSError:
            # 不在了就是沒有東西要刪，也沒有位元組要算。差幾條由呼叫端報成 `*_missing`。
            continue
        key = (info.device, info.inode)
        names[key].add(os.path.normcase(os.path.normpath(path)))
        facts[key] = info
        found.append(path)
    return _Measured(
        found=found,
        bytes=sum(info.size for info in facts.values()),
        reclaimable=sum(info.size for key, info in facts.items() if len(names[key]) >= info.links),
    )


def _remove_all(paths: Sequence[Path], *, roots: Sequence[Path]) -> int:
    """逐條刪，回傳真的刪掉幾個。空掉的目錄跟著收。

    **一條失敗不讓整次刪除停住**：帳本被改壞、指到媒體庫外面的那一條（`PathEscapeError`）
    或權限不足的那一條，記一行 log 之後換下一條——其餘四條照樣要刪得完，而剩下的那一條
    由對帳（brief §9.1）當成 Issue 處理。
    """
    removed = 0
    for path in paths:
        try:
            gone = remove_one(path, roots=roots)
        except (OSError, fs.PathEscapeError) as exc:
            logger.warning("this path was left alone", extra={"path": str(path), "error": str(exc)})
            continue
        if gone:
            removed += 1
    return removed


def remove_one(path: Path, *, roots: Sequence[Path]) -> bool:
    """刪一條路徑，空掉的目錄跟著收。回傳它原本在不在。

    **一條一條的那一步**，`_remove_all` 與 audit 撤銷（`services/review.py`，M2 票 06）都走它：
    撤銷只拆一個檔案，而且拆不掉時要停下來、什麼紀錄都不改——所以失敗照樣丟出去
    （`OSError` / `fs.PathEscapeError`），吞不吞由呼叫端決定。
    """
    root = fs.root_of(path, roots)
    gone = fs.remove(path, roots=roots)
    fs.prune_empty_parents(path, root=root)
    return gone


async def route_targets(session: AsyncSession) -> list[Path]:
    """刪除守衛認得的那幾個根：每一條 Route 的目標路徑。媒體庫裡只刪得到它們底下的東西。"""
    return [Path(row.target_path) for row in await session.scalars(select(Route))]


async def _restate_ledger(session: AsyncSession, job: Job, scope: DeleteScope) -> None:
    """帳本那幾列說得出現況（brief §9.1 的 `ledger.status`）。

    **不跟著刪掉**：清除帳本是另一個旗標，而留下來的那幾列正是「這個媒體庫檔案原本來自
    哪個 torrent」的唯一答案。來源與目標都被刪掉時記的是 `target_missing`——那一列上更要人
    知道的是媒體庫裡少了什麼。
    """
    if not (scope.unlink or scope.delete_files) or scope.purge:
        return
    status = LedgerStatus.TARGET_MISSING if scope.unlink else LedgerStatus.SOURCE_MISSING
    for entry in await session.scalars(select(LedgerEntry).where(LedgerEntry.job_hash == job.hash)):
        entry.status = status


async def _record(session: AsyncSession, job: Job, outcome: DeleteOutcome, *, actor: str) -> None:
    """`removed` + 一筆 `deleted`（plan §3.1 的最後一列）。

    CAS 的 `expected` 是讀進來的那個狀態：磁碟上的事已經做完了，所以輸掉的那一次只記一行
    log——覆寫別人剛寫下的狀態比停在這裡更糟。`job_lock` 已經把迴圈擋在外面，走到這裡的
    多半是使用者的第二個分頁。
    """
    if not await transition(session, job, JobState.REMOVED, expected=job.state):
        logger.warning("job moved on before it could be marked removed")
    await record_event(
        session,
        job,
        EventType.DELETED,
        actor=actor,
        payload={
            "links": outcome.links,
            "sources": outcome.sources,
            "torrent": outcome.torrent,
            "purged": outcome.purged,
            "freed": outcome.freed,
        },
    )


async def _purge(session: AsyncSession, job: Job) -> None:
    """帳本、事件與 Job 一起消失（brief §9.2 的第四個旗標）。

    `job_files` 與 `plans` 跟著 Job 的外鍵 `CASCADE` 走；帳本與事件是**弱引用**
    （`models/ledger.py`、`models/event.py`），刻意沒有外鍵，所以由這裡明寫。
    """
    await session.execute(sql_delete(LedgerEntry).where(LedgerEntry.job_hash == job.hash))
    await session.execute(sql_delete(Event).where(Event.job_hash == job.hash))
    await session.delete(job)


async def _job(session: AsyncSession, job_hash: str) -> Job:
    job = await session.get(Job, job_hash)
    if job is None:
        raise JobRejectedError(JobRefusal.JOB_MISSING, job_hash)
    return job


def _unique(paths: Iterable[Path]) -> list[Path]:
    """同一條路徑只留一次，順序照第一次出現。帳本與 `job_files` 多半指著同一批檔案。"""
    seen: dict[str, Path] = {}
    for path in paths:
        seen.setdefault(str(path), path)
    return list(seen.values())
