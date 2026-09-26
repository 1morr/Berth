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

**媒體庫那一側只拆 Berth 放下去的那一個**（M3 票 01）：使用者可能把硬鏈接換成了自己的檔案
（一份複製品、一個重新壓制的版本），那時候那條路徑上的是 Unmanaged（CONTEXT.md），永不刪。
會拆媒體庫鏈接的每一條路——這裡的「移除鏈接」、audit 撤銷、rematch 拆舊鏈接——都走
`remove_one`，判斷只有 `Placed.holds` 一份。
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
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
    #: 沒有拆的媒體庫路徑：那裡的檔案已經不是 Berth 放的那一個（`Placed`）。
    unmanaged: tuple[str, ...] = ()


async def estimate_deletion(session: AsyncSession, job_hash: str) -> DeletionEstimate:
    """這一筆刪下去會空出多少（brief §9.2）。**只讀，不改任何東西。**

    慢是刻意的：逐一 `stat` 每一個來源與目標，不用 qBittorrent 報的 `total_size` 去猜——
    那是 torrent 的大小，而磁碟上可能只下載了一部分、可能有人手動刪過幾個檔案。
    媒體庫那一側不是 Berth 放的那幾個不會被刪，也就不算。
    """
    job = await _job(session, job_hash)
    paths = await _scope_paths(session, job)
    placed = _ours(paths.links)
    facts = _measure(placed + paths.sources)
    links = _measure(placed)
    sources = _measure(paths.sources)
    return DeletionEstimate(
        links=len(links.found),
        links_missing=len(placed) - len(links.found),
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

    **拒絕都在前面**：做不了的那幾種（沒有這個 Job、勾錯組合、按下去之後它被別處改過了）在碰
    任何東西之前就停下來，向 qBittorrent 移除那一步也排在動磁碟之前——刪到一半才失敗是最難
    收拾的結果。

    **鎖裡第一件事是比對狀態**（M3 票 01）：`expected` 是這個請求進來時讀到的狀態，也就是使用者
    按下去時看到的那一個。兩個分頁同時刪同一筆時，後拿到鎖的那一個看到它已經不是那個狀態、得到
    `moved_on`，而不是對著剛刪過的 Job 再刪一次、回報「刪好了」。先到的那一個勾了清除紀錄的話
    這一列已經不在了，後到的那一個是 `job_missing`。

    **轉換（CAS）排在向 qBittorrent 移除之後**（plan §3.3，M4 票 01）：轉換一寫下去就握著 SQLite
    的寫鎖，先轉再打 qBittorrent 的話，它慢的那幾秒每一個寫者都在等。鎖裡的比對擋得住兩個分頁。
    CAS 照舊在，但它輸掉時 torrent 已經移除了、回的是 `moved_on`——只有沒拿鎖就改狀態的寫者造得出
    這種半套，而改 Job 狀態的每一條路都拿著這把鎖（`transition` 的呼叫端）。
    """
    seen = (await _job(session, job_hash)).state
    if scope.delete_files and not scope.remove_torrent:
        raise JobRejectedError(
            JobRefusal.DELETE_FILES_REQUIRES_REMOVE_TORRENT,
            "qBittorrent would fetch the files again on its next recheck",
        )

    with job_context(job_hash):
        # poller 與 importer 也寫這一列，而這一支會把它們腳下的檔案抽走。
        async with job_lock(job_hash):
            # 鎖外那一次讀只為了知道使用者看到了什麼；鎖裡這一次（`populate_existing`）才算數。
            job = await session.get(Job, job_hash, populate_existing=True)
            if job is None:
                raise JobRejectedError(JobRefusal.JOB_MISSING, job_hash)
            if job.state is not seen:
                raise JobRejectedError(JobRefusal.MOVED_ON, job.state.value)
            return await _apply(session, factory, job, scope, seen=seen, actor=actor)


async def _apply(
    session: AsyncSession,
    factory: ServiceClientFactory,
    job: Job,
    scope: DeleteScope,
    *,
    seen: JobState,
    actor: str,
) -> DeleteOutcome:
    """鎖裡面、比對過狀態之後的那一段。抽出來是為了讓 `job_lock` 包得住整段而不必再縮排一層。"""
    paths = await _scope_paths(session, job)
    # **先量再刪**：`st_nlink` 在刪掉第一個名字之後就變了，事後算不出「這一次空出多少」。
    before = _measure(
        (_ours(paths.links) if scope.unlink else []) + (paths.sources if scope.delete_files else [])
    )

    if scope.remove_torrent:
        await _remove_torrent(session, factory, job)
    if not await transition(session, job, JobState.REMOVED, expected=seen):
        raise JobRejectedError(JobRefusal.MOVED_ON, job.state.value)

    unlinked = _unlink_all(paths.links, roots=paths.route_targets) if scope.unlink else {}
    sources = _remove_all(paths.sources, roots=[paths.complete_root]) if scope.delete_files else 0
    await _restate_ledger(session, job, scope, unlinked)

    outcome = DeleteOutcome(
        links=sum(result is Unlink.REMOVED for result in unlinked.values()),
        sources=sources,
        torrent=scope.remove_torrent,
        purged=scope.purge,
        freed=before.reclaimable,
        unmanaged=tuple(path for path, result in unlinked.items() if result is Unlink.UNMANAGED),
    )
    await _record(session, job, outcome, actor=actor)
    if scope.purge:
        await _purge(session, job)
    await session.commit()
    logger.info(
        "job deleted",
        extra={
            "links": outcome.links,
            "sources": sources,
            "purged": scope.purge,
            "freed": outcome.freed,
            "unmanaged": len(outcome.unmanaged),
        },
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
    """這一筆在磁碟上佔著的每一條路徑，加上刪除守衛用的兩組根。

    媒體庫那一側以帳本的 `target_path` 為鍵、帶著「Berth 放的是誰」：那條路徑上現在的檔案
    不一定還是它。
    """

    links: dict[str, Placed]
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
        links={row.target_path: Placed.of(row) for row in entries},
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


class Unlink(StrEnum):
    """拆一條媒體庫鏈接的結果（`remove_one`）。"""

    #: 拆掉了。
    REMOVED = "removed"
    #: 本來就不在（有人在 Jellyfin 或檔案總管裡先刪了）。要做的事已經成立。
    GONE = "gone"
    #: 那條路徑上的已經不是 Berth 放的那一個，沒有碰（CONTEXT.md 的 Unmanaged）。
    UNMANAGED = "unmanaged"


@dataclass(frozen=True, slots=True)
class Placed:
    """Berth 在一條媒體庫路徑上放下去的是誰（M3 票 01）。**會拆媒體庫鏈接的每一條路共用這一份。**

    兩個認法，對上一個就是：

    - **帳本記的** `(device, inode)`：鏈接當下量的那一個（`importer.record_link`）。來源後來被
      qBittorrent 重新下載、換了 inode 時，媒體庫那一份仍然是 Berth 當時放的。
    - **來源現在的**：與來源同一份資料的那個名字，刪了也不會少掉任何資料；importer 收掉換了
      落點的舊鏈接時手上也只有來源。

    兩者都對不上，那個檔案就是使用者自己的（換成了一份複製品、一個重新壓制的版本）。
    device 與 inode 以字串比（`models/ledger.py`：Windows 的 `st_dev` 超過 SQLite INTEGER）。
    """

    recorded: tuple[str, str] | None
    source: Path | None

    @classmethod
    def of(cls, entry: LedgerEntry) -> Placed:
        """帳本那一列：它記的目標，與它的來源。"""
        return cls(
            recorded=(entry.source_dev, entry.target_inode), source=Path(entry.source_abs_path)
        )

    @classmethod
    def linked(cls, facts: fs.PathFacts) -> Placed:
        """剛剛鏈接出來、量過的那一個（rematch 收回自己剛建的鏈接）。"""
        return cls(recorded=_identity(facts), source=None)

    @classmethod
    def sharing(cls, source: Path) -> Placed:
        """與這個來源同一份資料的那一個（importer 收掉換了落點的舊鏈接）。"""
        return cls(recorded=None, source=source)

    def holds(self, facts: fs.PathFacts) -> bool:
        """`facts` 說的那個檔案是不是 Berth 放的那一個。"""
        if self.recorded == _identity(facts):
            return True
        if self.source is None:
            return False
        try:
            return _identity(fs.stat(self.source)) == _identity(facts)
        except OSError:
            return False


def _identity(facts: fs.PathFacts) -> tuple[str, str]:
    return str(facts.device), str(facts.inode)


def _ours(links: dict[str, Placed]) -> list[Path]:
    """會被拆的那幾條：Berth 放的，或已經不在的。估算與「空出多少」只算它們。"""
    kept = []
    for text, placed in links.items():
        path = Path(text)
        try:
            facts = fs.stat(path)
        except OSError:
            kept.append(path)
            continue
        if placed.holds(facts):
            kept.append(path)
    return kept


def _unlink_all(links: dict[str, Placed], *, roots: Sequence[Path]) -> dict[str, Unlink]:
    """媒體庫那一側逐條拆，回每一條的結果（鍵是帳本的 `target_path`）。

    **一條失敗不讓整次刪除停住**：帳本被改壞、指到媒體庫外面的那一條（`PathEscapeError`）
    或權限不足的那一條，記一行 log 之後換下一條——其餘照樣要拆得完。它沒有結果，帳本那一列
    也就不改，由對帳（brief §9.1）當成 Issue 處理。
    """
    results: dict[str, Unlink] = {}
    for text, placed in links.items():
        try:
            results[text] = remove_one(Path(text), roots=roots, placed=placed)
        except (OSError, fs.PathEscapeError) as exc:
            logger.warning("this path was left alone", extra={"path": text, "error": str(exc)})
    return results


def _remove_all(paths: Sequence[Path], *, roots: Sequence[Path]) -> int:
    """complete 那一側逐條刪，回傳真的刪掉幾個。空掉的目錄跟著收。失敗的那一條同 `_unlink_all`。

    這一側不認人：complete 是 Berth 的下載目錄，不是使用者會換檔案的地方（brief §5.3）。
    """
    removed = 0
    for path in paths:
        try:
            root = fs.root_of(path, roots)
            gone = fs.remove(path, roots=roots)
            fs.prune_empty_parents(path, root=root)
        except (OSError, fs.PathEscapeError) as exc:
            logger.warning("this path was left alone", extra={"path": str(path), "error": str(exc)})
            continue
        if gone:
            removed += 1
    return removed


def remove_one(path: Path, *, roots: Sequence[Path], placed: Placed) -> Unlink:
    """拆一條媒體庫鏈接，空掉的目錄跟著收——**只拆 Berth 放下去的那一個**（`Placed`）。

    **一條一條的那一步**，會拆媒體庫鏈接的每一條路都走它：刪除範圍的「移除鏈接」、audit 撤銷
    （`services/review.py`）、rematch 拆舊鏈接與收回剛建的鏈接（`services/rematch.py`）、importer
    收掉換了落點的舊鏈接。撤銷只拆一個檔案，而且拆不掉時要停下來、什麼紀錄都不改——所以失敗
    照樣丟出去（`OSError` / `fs.PathEscapeError`），吞不吞由呼叫端決定。

    守衛在認人之前：指到媒體庫外面的那一條連 `stat` 都不做。認完到刪之間有一條縫（使用者剛好在
    這一瞬間換掉檔案）；`unlink` 沒有「inode 還是它才刪」的原子版本。
    """
    root = fs.root_of(path, roots)
    try:
        facts = fs.stat(path)
    except FileNotFoundError:
        fs.prune_empty_parents(path, root=root)
        return Unlink.GONE
    if not placed.holds(facts):
        return Unlink.UNMANAGED
    gone = fs.remove(path, roots=roots)
    fs.prune_empty_parents(path, root=root)
    return Unlink.REMOVED if gone else Unlink.GONE


async def route_targets(session: AsyncSession) -> list[Path]:
    """刪除守衛認得的那幾個根：每一條 Route 的目標路徑。媒體庫裡只刪得到它們底下的東西。"""
    return [Path(row.target_path) for row in await session.scalars(select(Route))]


async def _restate_ledger(
    session: AsyncSession, job: Job, scope: DeleteScope, unlinked: dict[str, Unlink]
) -> None:
    """帳本那幾列說得出現況（brief §9.1 的 `ledger.status`）。

    **不跟著刪掉**：清除帳本是另一個旗標，而留下來的那幾列正是「這個媒體庫檔案原本來自
    哪個 torrent」的唯一答案。

    寫下的兩種都是**使用者決定過的現況**，對帳看到就不再為那一列開 Issue（`source_missing` 的
    先例，plan §2.4）：拆掉了的是 `unlinked`，只刪了來源的是 `source_missing`。來源與目標都刪掉
    時記 `unlinked`——那一列上更要人知道的是媒體庫裡少了什麼。沒拆的那幾條（不是 Berth 放的、
    拆不掉的）目標還在，只在刪了來源時改；其餘的現況交給下一輪對帳。
    """
    if not (scope.unlink or scope.delete_files) or scope.purge:
        return
    for entry in await session.scalars(select(LedgerEntry).where(LedgerEntry.job_hash == job.hash)):
        if unlinked.get(entry.target_path) in (Unlink.REMOVED, Unlink.GONE):
            entry.status = LedgerStatus.UNLINKED
        elif scope.delete_files:
            entry.status = LedgerStatus.SOURCE_MISSING


async def _record(session: AsyncSession, job: Job, outcome: DeleteOutcome, *, actor: str) -> None:
    """一筆 `deleted`（plan §3.1 的最後一列）。`removed` 是鎖裡的第一件事（`delete_job`）。"""
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
            "unmanaged": list(outcome.unmanaged),
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
