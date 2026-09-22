"""送單與 Job 的讀取端（plan §3.1、§3.3、§6 jobs 群組、brief §5.1、票 09）。

**這是產品第一次真的動到 Berth 以外的東西。** 在它之前每個命令都只讀；從這裡開始 Berth 會
在使用者的 qBittorrent 上放一個 torrent，並且把一串字寫死進 `media.folder_name`——那是整個
系統唯一一個定了就改不掉的東西（brief §4.5）。所以這一支的形狀主要是關於**什麼時候不做事**。

一次送單的順序不能換：

1. **驗前提**（作品、Route、Route 的健康）。不成立就一個 Job 都不建——紅的 Route 送單一定
   失敗（brief §4.4），而一列註定失敗的 Job 只是下載列表上要人去清掉的垃圾。
2. **拿到 torrent 本身**（`adapters/torrent.py`）。`jobs.hash` 是主鍵，所以在知道是哪一個
   torrent 之前沒有 Job 可建。索引站報得出 hash 時先查一次重複，那一步連請求都不必發。
3. **建 Job（`requested`）+ event**。從這裡開始失敗都記在 Job 上，因為現在有地方記了。
4. **ensure_category → `torrents/add`**。成功是 `submitted`，失敗是 `submit_failed` 加原文，
   而 `submit_failed` 可以手動重試回 `requested`（plan §3.1）。
5. **成功之後才凍結資料夾名、寫下「上次用的 Route」**。順序是刻意的：磁碟上沒發生任何事的
   那一次不該讓那串字定下來。**送單這一步不刷新快照**（plan §8.3 的六小時規則留給票 11 的
   planning）：凍下去的必須就是使用者剛剛在確認畫面上看到的那一串字，而刷新會在他按下去
   與那串字落地之間把它換掉（brief §4.5「有人在場、有一次明確確認」）。

log 的每一行帶 job id（brief §16.2、plan T1.9）：`job_context` 一包住，這一段裡任何模組
發出的任何一行都帶著它，不必逐個呼叫端記得傳。
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter
from collections.abc import AsyncIterator, Coroutine, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from berth.adapters.http import ServiceError
from berth.adapters.qbittorrent import TorrentAdd, ensure_category
from berth.adapters.torrent import TorrentSource
from berth.domain import (
    EventType,
    HealthStatus,
    JobState,
    JobTrigger,
    collection_type_for,
)
from berth.logs import job_context
from berth.models import (
    Event,
    Job,
    Media,
    PathSettings,
    Plan,
    PlanItem,
    QbittorrentSettings,
    Route,
    User,
)
from berth.models.types import utcnow
from berth.services.clients import ServiceClientFactory
from berth.services.qbittorrent import sign_in
from berth.services.routes import save_path_of
from berth.services.settings import read_settings
from berth.services.steps import message

logger = logging.getLogger(__name__)

#: 重試得了的兩個狀態（plan §3.1）：送單失敗回 `requested` 再送一次，入庫失敗回 `importing`
#: 從沒做完的那幾個接著做。已經在下載的 torrent 再送一次只是多一次無謂的請求，而 `imported`
#: 再來一次是另一件事（M2 的重新入庫）。
RETRYABLE = frozenset({JobState.SUBMIT_FAILED, JobState.IMPORT_FAILED})

#: 手動重跑得了 Plan 的狀態（票 11）。`review` 也在裡面：plan §3.1 的「使用者拒絕 →
#: `completed`」就是為了讓它重新 planning，而 M1 沒有審核 UI，重跑是唯一按得到的那一步。
#: `importing` 不在裡面——那一份計劃已經被採信，而 importer 正照著它動檔案（票 12）。
#:
#: **與 `RETRYABLE` 放在一起**：兩個都在回答「這一筆現在按得了什麼」，而畫面上那兩顆按鈕
#: 就在同一塊展開區裡。規則分兩個模組寫的話，其中一份遲早會漏掉一個狀態。
REPLANNABLE = frozenset({JobState.COMPLETED, JobState.PLANNING, JobState.REVIEW})


class _JobLocks:
    """一個 job 一把程序內的鎖（plan §3.1、brief §5.3「同一時間一個 Job 只有一個 worker」）。

    compare-and-set 保證的是「不會寫壞」，鎖保證的是「不會做兩次」：poller 正在為某一筆
    建 `job_files` 時，使用者按下的重試如果同時跑，兩邊會各打一次 qBittorrent。

    **用完就丟**：長期執行的 Berth 會經手幾千筆 Job，一個永遠長大的字典是個慢性漏洞。
    等待中的呼叫端自己記在 `_waiting` 上，歸零才把鎖拿掉——查 `asyncio.Lock` 的私有
    `_waiters` 也做得到，但那是別人的內部欄位。
    """

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._waiting: Counter[str] = Counter()

    @property
    def held(self) -> int:
        """現在字典裡有幾把。「用完就丟」沒有別的觀測點。"""
        return len(self._locks)

    @asynccontextmanager
    async def hold(self, job_hash: str) -> AsyncIterator[None]:
        self._waiting[job_hash] += 1
        lock = self._locks.setdefault(job_hash, asyncio.Lock())
        try:
            async with lock:
                yield
        finally:
            self._waiting[job_hash] -= 1
            if not self._waiting[job_hash]:
                del self._waiting[job_hash]
                self._locks.pop(job_hash, None)


_locks = _JobLocks()


def job_lock(job_hash: str) -> AbstractAsyncContextManager[None]:
    """握住這一筆 Job 的鎖。**不可重入**，所以只掛在對外的入口上，不掛在內部步驟裡。"""
    return _locks.hold(job_hash)


def held_locks() -> int:
    """現在還留著幾把鎖。**只給測試**——「用完就丟」沒有別的觀測點，而那是這個字典
    不會無限長大的唯一保證。"""
    return _locks.held


@dataclass(frozen=True, slots=True)
class JobSource:
    """結果表的一列帶過來的東西：要下載哪一個 torrent。

    `info_hash` 是**索引站說的**，可能沒有（實測 ACG.RIP 不報，brief §20.7）。有的話它值得
    一次短路：同一筆重複送單時連 torrent 都不必去要，而 Prowlarr 的每一次代理下載都是它
    再去連一次追蹤站。沒有的話由 `adapters/torrent.py` 從那份 torrent 自己算出來。
    """

    url: str
    #: 發佈名。`jobs.name`——使用者在下載列表上認得出這一列的東西。
    title: str
    info_hash: str = ""


class JobRejectedError(Exception):
    """這一次送單在建 Job 之前就停下來了。

    `reason` 是封閉集合（UI 逐種說一句話、給一條下一步），`detail` 是服務回的原文或
    Berth 自己算出來的實測值——與精靈的纜繩同一個規矩：理由翻譯，原文不翻譯。
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True, slots=True)
class JobView:
    """下載列表與 Job 詳情上的一筆。

    `media_title` 與 `route_name` 是**攤平進來的**而不是巢狀物件：這一列上要顯示的就是
    那兩個字串，而列表一次畫幾十筆——巢狀會讓前端為了一個名字帶著整份 Media。
    """

    hash: str
    name: str
    state: JobState
    trigger: JobTrigger
    trigger_ref: str
    error: str
    media_id: str | None
    #: 作品名的兩輪（brief §7.5）：`zh-Hant` 介面用 `media_title`（`zh-TW` 那一輪，缺就是英文），
    #: `en` 介面用 `media_title_en`。沒有作品時兩個都是空字串。
    media_title: str
    media_title_en: str
    route_id: int | None
    route_name: str
    route_slug: str
    user_id: int | None
    user_name: str
    save_path: str
    content_path: str
    total_size: int
    progress: float
    client_state: str
    added_at: datetime
    completed_at: datetime | None
    imported_at: datetime | None
    #: 這一筆現在按得了「重試」嗎（plan §3.1 的 `submit_failed` → `requested`）。
    #: 規則在後端算好：前端重算一份的話，票 10 加進來的其他可重試狀態會漏掉一邊。
    retryable: bool
    #: 這一筆現在按得了「重新規劃」嗎（票 11）。與 `retryable` 同一個道理：規則在後端算。
    replannable: bool
    #: 這一筆現在那一份 Import Plan 的 id（票 11），沒算過就是 `None`。
    #:
    #: **是 id 而不是整份 Plan**：下載列表一次畫幾十列，而逐檔的決定只有展開那一列時才要
    #: （`GET /api/plans/{id}`）。有沒有值本身就是畫面要的答案——要不要畫那一區。
    plan_id: int | None
    #: 那一份計劃裡 medium 自動入庫、掛著 audit 的檔案數（brief §6.5）。列上要說得出
    #: 「N 個待確認」：Job 的狀態是綠色的「已入庫」，而原則 3 說的是那幾個還要人看一眼（票 15）。
    audits: int


@dataclass(frozen=True, slots=True)
class JobEventView:
    """時間線上的一筆（brief §5.2）。"""

    id: int
    type: str
    actor: str
    payload: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AddDownloadOutcome:
    """一次送單的結果。

    `created` 分得出「送出去了」與「這一個本來就在了」（plan §3.3）。兩者都是成功——
    使用者按第二次時要看到的是那一筆既有的 Job，不是一則錯誤。
    """

    job: JobView
    created: bool


async def add_download(
    session: AsyncSession,
    factory: ServiceClientFactory,
    *,
    source: JobSource,
    media_id: str,
    route_id: int,
    user_id: int | None,
    trigger: JobTrigger = JobTrigger.MANUAL,
    trigger_ref: str = "",
) -> AddDownloadOutcome:
    """把一個 torrent 送進 qBittorrent，並替它建一筆 Job（plan §3.1）。"""
    media, route = await _preconditions(session, media_id, route_id)

    if source.info_hash:
        existing = await session.get(Job, source.info_hash)
        if existing is not None:
            return AddDownloadOutcome(job=await _view_one(session, existing), created=False)

    torrent = await _resolve(factory, source.url)
    existing = await session.get(Job, torrent.info_hash)
    if existing is not None:
        return AddDownloadOutcome(job=await _view_one(session, existing), created=False)

    with job_context(torrent.info_hash):
        job = Job(
            hash=torrent.info_hash,
            name=source.title,
            source_url=source.url,
            trigger=trigger,
            trigger_ref=trigger_ref,
            user_id=user_id,
            media_id=media.id,
            route_id=route.id,
            state=JobState.REQUESTED,
        )
        # **打 qBittorrent 之前就 commit**（與精靈每一步「做之前先寫 `running`」同一個道理，
        # plan §2.1）：在那之後任何一個沒接住的例外或斷線都會 rollback，而 torrent 可能
        # 已經進了下載器——那就成了一個沒有 Job 的孤兒（plan §3.2 的 `unknown_torrent`）。
        #
        # `try` 從 `add` 就開始：約束在 flush 當下就丟（`record_event` 會 flush），等不到 commit。
        try:
            session.add(job)
            await record_event(
                session,
                job,
                EventType.CREATED,
                actor=actor_of(user_id),
                payload={
                    "trigger": trigger.value,
                    "media": media.id,
                    "route": route.slug,
                    "name": source.title,
                },
            )
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            # 兩個分頁同時送同一筆：主鍵擋下第二個。回既有的那一列，不是 500（plan §3.3）。
            duplicate = await session.get(Job, torrent.info_hash)
            if duplicate is not None:
                return AddDownloadOutcome(job=await _view_one(session, duplicate), created=False)
            # 前提查過之後 Route 在 Route 設定頁被刪掉了：外鍵擋下這一列（票 14a）。
            # 用參數的 id 而不是 `route.id`——rollback 之後那個物件已經過期，讀它要再打一次資料庫。
            if await session.get(Route, route_id) is None:
                raise JobRejectedError("route_missing", str(route_id)) from exc
            raise
        logger.info("job created", extra={"state": job.state.value, "route": route.slug})
        # 從這裡開始 poller 也看得到這一列（它已經 commit 了），所以送單與迴圈要排隊。
        async with job_lock(job.hash):
            await _finish(session, factory, job, route, torrent, media, actor=actor_of(user_id))
        return AddDownloadOutcome(job=await _view_one(session, job), created=True)


async def retry_job(session: AsyncSession, factory: ServiceClientFactory, job_hash: str) -> JobView:
    """`submit_failed` → `requested` → 再送一次（plan §3.1）。

    重試走**存下來的下載連結**：畫面上那一輪搜尋早就不在了，而 Prowlarr 的代理連結每次
    搜尋都不一樣（brief §20.7），重新搜一次不會給出同一條。
    """
    job = await session.get(Job, job_hash)
    if job is None:
        raise JobRejectedError("job_missing", job_hash)
    if job.state not in RETRYABLE:
        raise JobRejectedError("not_retryable", job.state.value)
    if job.state is JobState.IMPORT_FAILED:
        with job_context(job.hash):
            async with job_lock(job.hash):
                return await _resume_import(session, job)
    route = await session.get(Route, job.route_id) if job.route_id is not None else None
    if route is None:
        raise JobRejectedError("route_missing", str(job.route_id))
    # **與第一次送單同一組前提**：那條 Route 可能在中間被停用、被改成收別種作品，或紅了。
    # 只檢查健康的話「第一次送不出去、重試卻送得出去」——同一個決定兩種答案。
    subject = await session.get(Media, job.media_id) if job.media_id is not None else None
    _check_route(route, subject)

    with job_context(job.hash):
        # poller 也會寫這一列（票 10），所以重試與迴圈排隊——CAS 保證不寫壞，鎖保證不做兩次。
        async with job_lock(job.hash):
            return await _resubmit(session, factory, job, route, subject)


async def _resubmit(
    session: AsyncSession,
    factory: ServiceClientFactory,
    job: Job,
    route: Route,
    subject: Media | None,
) -> JobView:
    """重試的那幾步。抽出來是為了讓 `job_lock` 包得住整段而不必再縮排一層。"""
    if not await transition(session, job, JobState.REQUESTED, expected=JobState.SUBMIT_FAILED):
        # 有別人（或另一個分頁）先動過它。放棄本次操作，不覆寫他的結果（plan §3.1）。
        raise JobRejectedError("not_retryable", job.state.value)
    await record_event(session, job, EventType.RETRIED, actor="user", payload={})
    logger.info("job retried", extra={"state": job.state.value})
    try:
        torrent = await _resolve(factory, job.source_url)
    except JobRejectedError as failure:
        await _fail(session, job, failure.detail or failure.reason, actor="user")
        await session.commit()
        return await _view_one(session, job)
    await _finish(session, factory, job, route, torrent, subject, actor="user")
    return await _view_one(session, job)


async def _resume_import(session: AsyncSession, job: Job) -> JobView:
    """`import_failed` → `importing`（plan §3.1）。

    這一支只把那一列放回去：importer 下一輪從 `applied_at` 還空著的那幾個接著做，已經鏈接好的
    跳過（`services/importer.py`）。事件的 `state` 讓時間線分得出這是哪一種重試——送單的重試
    說的是「再送一次」，這一個說的是「再入庫一次」。
    """
    if not await transition(session, job, JobState.IMPORTING, expected=JobState.IMPORT_FAILED):
        raise JobRejectedError("not_retryable", job.state.value)
    await record_event(
        session, job, EventType.RETRIED, actor="user", payload={"state": JobState.IMPORTING.value}
    )
    await session.commit()
    logger.info("job import retried", extra={"state": job.state.value})
    return await _view_one(session, job)


async def guarded[T](
    session: AsyncSession, job_hash: str, work: Coroutine[Any, Any, T], *, fallback: T
) -> T:
    """一筆 Job 的一輪（planner 與 importer 共用）。**它爆掉不會拖累同一輪的其他人。**

    迴圈那一層已經接了例外（`pipeline/`），但那個接法會讓這一輪剩下的 job 全部跳過——而掃描
    是照 `added_at` 排的，所以一筆壞掉的 Job 會在每一輪都排在最前面，後面那幾筆因此永遠
    輪不到。鎖與 log 上下文也在這裡包好：一輪裡的每一行 log 都帶那一筆的 job id。
    """
    with job_context(job_hash):
        async with job_lock(job_hash):
            try:
                return await work
            except Exception:
                await session.rollback()
                logger.exception("this job's round failed; the rest of the round goes on")
                return fallback


async def list_jobs(session: AsyncSession) -> tuple[JobView, ...]:
    """下載列表頁的一整份，最新的在前面（brief §13）。"""
    rows = tuple(await session.scalars(select(Job).order_by(Job.added_at.desc(), Job.hash)))
    related = await _related(session, rows)
    return tuple(_view(row, related) for row in rows)


async def read_job(session: AsyncSession, job_hash: str) -> JobView | None:
    job = await session.get(Job, job_hash)
    return None if job is None else await _view_one(session, job)


async def read_job_events(session: AsyncSession, job_hash: str) -> tuple[JobEventView, ...]:
    """時間線，最舊的在前面——它是一份紀錄，讀的方向是事情發生的方向（brief §5.2）。"""
    rows = await session.scalars(
        select(Event).where(Event.job_hash == job_hash).order_by(Event.created_at, Event.id)
    )
    return tuple(
        JobEventView(
            id=row.id,
            type=row.type,
            actor=row.actor,
            payload=row.payload_json or {},
            created_at=row.created_at,
        )
        for row in rows
    )


# --- 送單 ---------------------------------------------------------------


async def _preconditions(
    session: AsyncSession, media_id: str, route_id: int
) -> tuple[Media, Route]:
    """四個前提，逐個各有自己的理由——「送不出去」是一句沒有下一步的話。"""
    media = await session.get(Media, media_id)
    if media is None:
        raise JobRejectedError("media_missing", media_id)
    route = await session.get(Route, route_id)
    if route is None:
        raise JobRejectedError("route_missing", str(route_id))
    _check_route(route, media)
    return media, route


def _check_route(route: Route, media: Media | None) -> None:
    """這條 Route 現在收得下這一次送單嗎。**第一次送單與重試走同一支。**

    紅的 Route 送單一定失敗（brief §4.4）——硬鏈接或路徑有一條斷了，檔案下載完也進不了庫。
    `unknown` 放行：那是「還沒檢查」而不是「壞了」（`HealthStatus` 的三個值）。健康迴圈
    五分鐘才跑一輪（plan §3.2），拿它擋人等於精靈剛跑完的那五分鐘裡誰都送不了單。
    """
    if not route.enabled:
        raise JobRejectedError("route_disabled", route.slug)
    if media is not None and route.collection_type is not collection_type_for(media.kind):
        raise JobRejectedError(
            "route_kind_mismatch", f"{route.slug} holds {route.collection_type.value}"
        )
    if route.health_status is HealthStatus.FAILED:
        raise JobRejectedError("route_unhealthy", route.slug)


async def _resolve(factory: ServiceClientFactory, url: str) -> TorrentSource:
    """索引站的下載連結 → info hash + 要交出去的那一份。

    失敗**不建 Job**：`jobs.hash` 是主鍵，而 Job 記的正是「一個 torrent 的生命週期」
    （`CONTEXT.md`）——連是哪一個 torrent 都還不知道時，沒有東西可以記。
    """
    fetcher = factory.torrent()
    try:
        return await fetcher.fetch(url)
    except ServiceError as exc:
        raise JobRejectedError("source_unavailable", message(exc)) from exc
    finally:
        await fetcher.aclose()


async def _finish(
    session: AsyncSession,
    factory: ServiceClientFactory,
    job: Job,
    route: Route,
    torrent: TorrentSource,
    media: Media | None,
    *,
    actor: str,
) -> None:
    """送出去，然後照結果收尾。**第一次送單與重試走同一支**——兩邊的收尾差一步就會分岔。

    凍結在成功之後（plan §2.2、brief §4.5）：磁碟上什麼都沒發生的那一次不該讓那串字定下來。
    """
    await _submit(session, factory, job, route, torrent, actor=actor)
    if job.state is JobState.SUBMITTED and media is not None:
        _freeze(media, route)
    await session.commit()


async def _submit(
    session: AsyncSession,
    factory: ServiceClientFactory,
    job: Job,
    route: Route,
    torrent: TorrentSource,
    *,
    actor: str,
) -> None:
    """`requested` → `submitted` / `submit_failed`（plan §3.1）。

    先 `ensure_category`：category 決定 save path（`autoTMM=true`），所以它就是「這個
    torrent 會下載到哪裡」。同名但指向別處的 category **不覆寫**——那會搬走使用者
    自己那一整個分類的 torrent（brief §20.2）。
    """
    settings = await read_settings(session, QbittorrentSettings)
    paths = await read_settings(session, PathSettings)
    save_path = save_path_of(paths.complete_root, route.slug)
    client = factory.qbittorrent(settings.base_url)
    try:
        await sign_in(client, settings)
        outcome = await ensure_category(client, route.category, save_path)
        if outcome.conflict:
            await _fail(
                session,
                job,
                f"category {outcome.name!r} already points at {outcome.save_path!r}; "
                f"Berth wants {save_path!r} and will not move an existing category",
                actor=actor,
            )
            return
        await client.add_torrent(
            TorrentAdd(
                category=route.category,
                magnet=torrent.magnet,
                content=torrent.content,
                filename=torrent.filename,
            )
        )
    except ServiceError as exc:
        await _fail(session, job, message(exc), actor=actor)
        return
    finally:
        await client.aclose()

    if not await transition(session, job, JobState.SUBMITTED, expected=JobState.REQUESTED):
        # 有別人先動過它（票 10 起的迴圈也會寫同一列）。放棄本次操作，不覆寫他的結果。
        logger.warning("job moved on before it could be marked submitted")
        return
    await record_event(
        session,
        job,
        EventType.SUBMITTED,
        actor=actor,
        payload={
            "client": settings.base_url,
            "category": route.category,
            "save_path": save_path,
        },
    )
    logger.info(
        "job submitted",
        extra={"state": job.state.value, "category": route.category, "save_path": save_path},
    )


async def _fail(session: AsyncSession, job: Job, detail: str, *, actor: str) -> None:
    if not await transition(
        session, job, JobState.SUBMIT_FAILED, expected=JobState.REQUESTED, error=detail
    ):
        logger.warning("job moved on before it could be marked failed", extra={"error": detail})
        return
    await record_event(
        session, job, EventType.SUBMIT_FAILED, actor=actor, payload={"error": detail}
    )
    logger.warning("job submission failed", extra={"state": job.state.value, "error": detail})


def _freeze(media: Media, route: Route) -> None:
    """送單成功那一刻：資料夾名定死，Route 成為「上次用的」（plan §2.2、brief §4.5）。

    **已經凍結過的不重凍**：第二次送單時 TMDB 可能已經改了標題，而磁碟上的資料夾還是
    第一次那一個。`folder_name` 本身這時候不重算——`services/media` 在凍結之後也不再動它。
    """
    media.folder_frozen = True
    media.default_route_id = route.id


async def transition(
    session: AsyncSession,
    job: Job,
    state: JobState,
    *,
    expected: JobState,
    error: str = "",
) -> bool:
    """compare-and-set（plan §3.1：**轉換一律** compare-and-set）：影響 0 列就放棄本次操作。

    寫同一列的不只一個人：使用者有兩個分頁，而票 10 起的背景迴圈也會動這一列。
    `error` 與狀態同一句 UPDATE——分兩次寫的話，中間那一瞬間的狀態與理由對不起來。
    """
    result = await session.execute(
        update(Job)
        .where(Job.hash == job.hash, Job.state == expected)
        .values(state=state, error=error)
        .execution_options(synchronize_session="fetch")
    )
    # `CursorResult` 才有 `rowcount`；`execute(update(...))` 的靜態型別是 `Result`。
    changed = getattr(result, "rowcount", 0) == 1
    await session.refresh(job)
    return changed


async def record_event(
    session: AsyncSession,
    job: Job,
    event: EventType,
    *,
    actor: str,
    payload: dict[str, Any],
) -> None:
    """一筆事件（brief §5.2）。`flush` 而不是 `commit`：整次送單是一個工作單元。

    **同一件事一分鐘內只寫一次**（plan §3.3）：`(job_hash, type, payload)` 相同就跳過。
    理由是重啟——迴圈的一輪可能在寫完事件之後、在下一步落地之前被關掉，而重啟後的第一輪
    會把同一件事再做一次；時間線上同一件事出現兩次，讀起來就是發生了兩次。比的是 payload
    的**內容**（鍵排序後的 JSON），不是 dict 恰好的鍵順序。

    **使用者按下的重試是界線**：它是一次新的嘗試，之後發生的事就算與之前一模一樣，也是真的
    又發生了一次。不設界線的話，重試之後又同樣失敗的那一筆會被吞掉，時間線停在「重試」而
    狀態是失敗（code-review 抓到）。
    """
    now = utcnow()
    fingerprint = _fingerprint(payload)
    last_retry = await session.scalar(
        select(func.max(Event.id)).where(
            Event.job_hash == job.hash, Event.type == EventType.RETRIED.value
        )
    )
    recent = await session.scalars(
        select(Event.payload_json).where(
            Event.job_hash == job.hash,
            Event.type == event.value,
            Event.created_at >= now - EVENT_DEDUP_WINDOW,
            Event.id > (last_retry or 0),
        )
    )
    if any(_fingerprint(row or {}) == fingerprint for row in recent):
        logger.debug("duplicate event dropped", extra={"event": event.value})
        return
    session.add(
        Event(
            job_hash=job.hash,
            media_id=job.media_id,
            type=event.value,
            actor=actor,
            payload_json=payload,
            created_at=now,
        )
    )
    await session.flush()


#: 事件去重的窗口（plan §3.3）。
EVENT_DEDUP_WINDOW = timedelta(minutes=1)


def _fingerprint(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)


def actor_of(user_id: int | None) -> str:
    """`events.actor`：user id、`system`、`rss:<rule>` 或 `ai`（plan §2.3）。"""
    return str(user_id) if user_id is not None else "system"


# --- 攤平 ---------------------------------------------------------------


async def _view_one(session: AsyncSession, job: Job) -> JobView:
    """單獨一筆的 view。清單走 `_related` 一次問完，這裡是它的單數形。"""
    return _view(job, await _related(session, (job,)))


@dataclass(frozen=True, slots=True)
class _Related:
    """一份 Job 清單身上掛的每一種關聯，四次查詢問完（票 01）。

    逐列問的話一百筆下載就是四百次往返，而下載列每次重新整理都走這一支。
    """

    routes: dict[int, Route]
    media: dict[str, Media]
    users: dict[int, User]
    #: job hash → 現在那一份計劃的 id 與它掛著 audit 的檔案數。
    plans: dict[str, tuple[int, int]]


async def _related(session: AsyncSession, jobs: Sequence[Job]) -> _Related:
    """`_view` 要用到的每一種關聯。空的那一種不問。"""
    return _Related(
        routes=await _by_id(session, Route, Route.id, {j.route_id for j in jobs}),
        media=await _by_id(session, Media, Media.id, {j.media_id for j in jobs}),
        users=await _by_id(session, User, User.id, {j.user_id for j in jobs}),
        plans=await _plans_of(session, [job.hash for job in jobs]),
    )


async def _by_id[K, T](
    session: AsyncSession, model: type[T], key: InstrumentedAttribute[K], ids: set[K | None]
) -> dict[K, T]:
    wanted = {value for value in ids if value is not None}
    if not wanted:
        return {}
    rows = await session.scalars(select(model).where(key.in_(wanted)))
    return {getattr(row, key.key): row for row in rows}


async def _plans_of(session: AsyncSession, job_hashes: Sequence[str]) -> dict[str, tuple[int, int]]:
    """每一筆 Job 現在那一份計劃的 id 與掛著 audit 的檔案數。

    `services/plan.plan_id_of` 問的是前一半；**這裡不呼叫它**：`services/plan` 已經 import
     這一支（`transition`、`job_lock`），反過來就是循環。
    """
    if not job_hashes:
        return {}
    rows = await session.execute(
        select(Plan.job_hash, Plan.id, func.count(PlanItem.id).filter(PlanItem.audit))
        .outerjoin(PlanItem, PlanItem.plan_id == Plan.id)
        .where(Plan.job_hash.in_(list(job_hashes)))
        .group_by(Plan.job_hash, Plan.id)
    )
    return {job_hash: (plan_id, audits) for job_hash, plan_id, audits in rows if job_hash}


def _view(job: Job, related: _Related) -> JobView:
    route = related.routes.get(job.route_id) if job.route_id is not None else None
    media = related.media.get(job.media_id) if job.media_id is not None else None
    user = related.users.get(job.user_id) if job.user_id is not None else None
    plan_id, audits = related.plans.get(job.hash, (None, 0))
    return JobView(
        hash=job.hash,
        name=job.name,
        state=job.state,
        trigger=job.trigger,
        trigger_ref=job.trigger_ref,
        error=job.error,
        media_id=job.media_id,
        media_title=media.snapshot().title if media is not None else "",
        media_title_en=media.title_en if media is not None else "",
        route_id=job.route_id,
        route_name=route.name if route is not None else "",
        route_slug=route.slug if route is not None else "",
        user_id=job.user_id,
        user_name=user.name if user is not None else "",
        save_path=job.save_path,
        content_path=job.content_path,
        total_size=job.total_size,
        progress=job.progress,
        client_state=job.client_state,
        added_at=job.added_at,
        completed_at=job.completed_at,
        imported_at=job.imported_at,
        retryable=job.state in RETRYABLE,
        replannable=job.state in REPLANNABLE,
        plan_id=plan_id,
        audits=audits,
    )
