"""完成 → Import Plan（plan §3.1 的 planning 段、§3.2 的 `planner_runner`、§4、票 11）。

**這是沒有人在場時做的最大決定**：哪個檔案會被寫到媒體庫的哪一條路徑，以及要不要先問一句。
送單那一步有人按按鈕（票 09），下載那一段只是把 qBittorrent 說的話抄下來（票 10），而這一支
要自己回答「這一包是什麼」。所以它的形狀主要是關於**憑什麼相信自己**：

- **算之前先把事實補齊**。快照超過 6 小時就重抓（plan §8.3：新播的集數會變），下載完成的
  檔案逐個問一次 mediainfo（brief §5.1：此時的信心明顯高於只看檔名）。兩件事失敗都不阻擋
  ——存下來的季集仍然是真的季集，而少一個訊號的 Plan 仍然入得了庫。
- **算完之後先寫下來，再走下一步**。`plans` 與 `plan_items` 是這一輪的產出，Job 的狀態只是
  它的結論（plan §3.1「planning 的產出是 Plan，不是副作用」）。
- **一個 Job 一份「現在的計劃」**（`models/plan.py`）：重跑改寫同一列，所以重入不會長出
  第二份決定，而 `GET /api/plans/{id}` 不必回答「哪一個 id 才是現在那一份」。

pre-plan 是同一支邏輯的一半（brief §5.1）：檔案清單一到手就先算一次，不量 mediainfo、
不動 Job 的狀態，只回答「還來得及取消嗎」。
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import fs, mediainfo
from berth.config import VERSION
from berth.domain import (
    Confidence,
    EventType,
    FileEntry,
    FileKind,
    JobState,
    MediaSnapshot,
    ParseContext,
    PlanAction,
    PlanEngine,
    PlanStatus,
    PlanSummary,
    ReviewReason,
    Tags,
)
from berth.domain import PlanItem as PlannedFile
from berth.logs import job_context
from berth.models import Job, JobFile, LedgerEntry, Media, Plan, PlanItem, Route
from berth.models.types import utcnow
from berth.parser import SPAN_CLASH_CONSEQUENCE, classify, episode_span
from berth.parser import plan as decide
from berth.services.clients import ServiceClientFactory
from berth.services.events import EventHub, JobSignal
from berth.services.jobs import (
    REPLANNABLE,
    JobRejectedError,
    actor_of,
    guarded,
    job_lock,
    record_event,
    transition,
)
from berth.services.media import snapshot_for_planning

logger = logging.getLogger(__name__)

#: 這幾種處置真的會在媒體庫裡多一個檔案（plan §4.2 的 `target_path`）。
WRITTEN: frozenset[PlanAction] = frozenset(
    {PlanAction.IMPORT, PlanAction.EXTRA, PlanAction.SUBTITLE}
)

#: 該算一份正式 Plan 的狀態。`planning` 也在裡面——Berth 在算到一半時被關掉的話，那一列會
#: 停在那裡，而只掃 `completed` 就再也沒有人會碰它（plan §3.3 的重入）。
PLANNABLE: frozenset[JobState] = frozenset({JobState.COMPLETED, JobState.PLANNING})

#: 該先給一份預估的狀態（brief §5.1）：檔案清單已經到手，而檔案還在下載。
ESTIMABLE: frozenset[JobState] = frozenset(
    {JobState.METADATA_READY, JobState.DOWNLOADING, JobState.STALLED}
)


@dataclass(frozen=True, slots=True)
class Contents:
    """一包 torrent 的檔案清單，加上它的**內容根那一層**。

    兩件事總是一起旅行，所以它們是一個型別：qBittorrent 報的路徑相對 save path 且含根目錄
    （brief §20.7），而解析器要的是相對內容根（plan §4.6）。三個呼叫端（算 entries、問
    mediainfo、寫 plan items）各自算一次 prefix 的話，其中一個遲早會與另外兩個不一樣——
    而不一樣的後果是靜靜地查不到那一列 `job_files`（mediainfo 跳過、`job_file_id` 變 `None`）。

    **`root` 從整包算**，不是從「要下載的那些」算：內容根是那個 torrent 自己的形狀，
    與使用者在 qBittorrent 上取消勾選了哪幾個檔案無關。
    """

    rows: list[JobFile]
    root: str

    def entries(self) -> tuple[FileEntry, ...]:
        """解析器的輸入。**不下載的檔案不進 Plan**（`priority == 0`，brief §5.1）。"""
        return tuple(
            FileEntry(rel_path=row.rel_path[len(self.root) :], size=row.size, priority=row.priority)
            for row in self.rows
            if row.priority != 0
        )

    def find(self, rel_path: str) -> JobFile | None:
        """解析器口中的那條路徑 → `job_files` 的那一列。"""
        wanted = f"{self.root}{rel_path}"
        return next((row for row in self.rows if row.rel_path == wanted), None)


@dataclass(frozen=True, slots=True)
class PlanOutcome:
    """一輪的結果。log 與測試看它。"""

    planned: int
    preplanned: int


@dataclass(frozen=True, slots=True)
class PlanItemView:
    """Plan 表格上的一列（brief §6.5：決定、信心與理由）。"""

    id: int
    rel_path: str
    action: PlanAction
    media_id: str | None
    season: int | None
    episode_start: int | None
    episode_end: int | None
    #: 相對於 Route 目標的位置。`review` 與 `unmatched` 多半是空的。
    target_path: str
    confidence: Confidence
    reasons: tuple[str, ...]
    #: medium 自動入庫掛的旗標（CONTEXT.md 的 Audit）。
    audit: bool
    error: str


@dataclass(frozen=True, slots=True)
class PlanView:
    """一份 Plan 的一整份（`GET /api/plans/{id}`）。"""

    id: int
    job_hash: str | None
    status: PlanStatus
    engine: PlanEngine
    engine_version: str
    created_at: datetime
    summary: PlanSummary
    items: tuple[PlanItemView, ...]


async def sweep_plans(
    session: AsyncSession,
    factory: ServiceClientFactory,
    hub: EventHub,
    *,
    now: datetime | None = None,
) -> PlanOutcome:
    """一輪：把該算的都算一遍（plan §3.2 的 `planner_runner`）。

    **DB 狀態才是真相**：迴圈醒來的理由（提示或 60 秒到了）不決定要處理哪幾筆，這兩句
    查詢才決定。程序重啟之後不必補送任何提示，而重複的提示也只是讓同一輪早一點發生。
    """
    moment = now or utcnow()
    planned = 0
    for job_hash in await _plannable(session):
        # 一筆解析不了的 torrent 會停在 `planning`，而它排在最前面——`guarded` 讓它不擋後面的人。
        planned += await guarded(
            session, job_hash, _plan(session, factory, hub, job_hash, moment), fallback=0
        )
    preplanned = 0
    for job_hash in await _estimable(session):
        preplanned += await guarded(
            session, job_hash, _preplan(session, hub, job_hash, moment), fallback=0
        )
    return PlanOutcome(planned=planned, preplanned=preplanned)


async def replan_job(
    session: AsyncSession, factory: ServiceClientFactory, hub: EventHub, job_hash: str
) -> PlanView:
    """手動重跑一次（`POST /api/jobs/{hash}/replan`、plan §6 jobs 群組）。

    使用者按它的時刻是：Plan 停在 review 而他改了 Route 的設定、或 TMDB 那邊剛補上正確的
    季集。`review` 先退回 `completed` 再算——那正是 plan §3.1 的「使用者拒絕」那一條。
    """
    job = await session.get(Job, job_hash)
    if job is None:
        raise JobRejectedError("job_missing", job_hash)
    if job.state not in REPLANNABLE:
        raise JobRejectedError("not_replannable", job.state.value)
    with job_context(job_hash):
        async with job_lock(job_hash):
            if job.state is JobState.REVIEW and not await transition(
                session, job, JobState.COMPLETED, expected=JobState.REVIEW
            ):
                raise JobRejectedError("not_replannable", job.state.value)
            await _plan(session, factory, hub, job_hash, utcnow())
    plan_id = await plan_id_of(session, job_hash)
    view = None if plan_id is None else await read_plan(session, plan_id)
    if view is None:
        raise JobRejectedError("not_replannable", job.state.value)
    return view


async def read_plan(session: AsyncSession, plan_id: int) -> PlanView | None:
    row = await session.get(Plan, plan_id)
    if row is None:
        return None
    items = await session.scalars(
        select(PlanItem).where(PlanItem.plan_id == row.id).order_by(PlanItem.id)
    )
    return PlanView(
        id=row.id,
        job_hash=row.job_hash,
        status=row.status,
        engine=row.engine,
        engine_version=row.engine_version,
        created_at=row.created_at,
        summary=PlanSummary.model_validate(row.summary_json or {}),
        items=tuple(
            PlanItemView(
                id=item.id,
                rel_path=item.rel_path,
                action=item.action,
                media_id=item.media_id,
                season=item.season,
                episode_start=item.episode_start,
                episode_end=item.episode_end,
                target_path=item.target_path,
                confidence=item.confidence,
                reasons=tuple(item.reasons_json or ()),
                audit=item.audit,
                error=item.error,
            )
            for item in items
        ),
    )


async def plan_id_of(session: AsyncSession, job_hash: str) -> int | None:
    """這個 Job 現在那一份計劃的 id。沒算過就是 `None`（下載列表照它決定畫不畫那一區）。"""
    found: int | None = await session.scalar(select(Plan.id).where(Plan.job_hash == job_hash))
    return found


# --- 一輪要處理誰 -------------------------------------------------------


async def _plannable(session: AsyncSession) -> list[str]:
    rows = await session.scalars(
        select(Job.hash).where(Job.state.in_(PLANNABLE)).order_by(Job.added_at, Job.hash)
    )
    return list(rows)


async def _estimable(session: AsyncSession) -> list[str]:
    """還在下載、有檔案清單、而且還沒有任何一份 Plan 的那幾筆。

    「還沒有任何一份」就是 pre-plan 的冪等鍵：這個迴圈每分鐘醒一次，而預估只值得算一次
    （檔案清單在下載期間不會變）。
    """
    has_plan = select(Plan.id).where(Plan.job_hash == Job.hash).exists()
    has_files = select(JobFile.id).where(JobFile.job_hash == Job.hash).exists()
    rows = await session.scalars(
        select(Job.hash)
        .where(Job.state.in_(ESTIMABLE), ~has_plan, has_files)
        .order_by(Job.added_at, Job.hash)
    )
    return list(rows)


# --- 正式的那一份 -------------------------------------------------------


async def _plan(
    session: AsyncSession,
    factory: ServiceClientFactory,
    hub: EventHub,
    job_hash: str,
    now: datetime,
) -> int:
    """`completed` → `planning` → `importing` / `review`（plan §3.1）。"""
    job = await session.get(Job, job_hash)
    if job is None or job.state not in PLANNABLE:
        return 0
    if job.state is JobState.COMPLETED:
        if not await transition(session, job, JobState.PLANNING, expected=JobState.COMPLETED):
            # 有別人先動過它（使用者按了刪除，或另一個分頁按了重跑）。放棄本次操作。
            return 0
        # **先 commit 再開始算**（與精靈每一步「做之前先寫 running」同一個道理，plan §2.1）：
        # 讀 TMDB 與逐檔問 mediainfo 要幾秒鐘，而那幾秒鐘畫面上要說得出它正在做什麼。
        # 中途爆掉的話那一列停在 `planning`，下一輪掃到它會從頭再算一次。
        await session.commit()

    route = await session.get(Route, job.route_id) if job.route_id is not None else None
    snapshot = await _snapshot(session, factory, job)
    contents = await _contents(session, job)
    entries = await _measure(session, job, contents)
    items = await _against_ledger(
        session,
        job,
        route,
        _apply_policy(decide(job.name, entries, _context(route, snapshot)), route),
    )
    status, reason = _verdict(items, route)
    row = await _store(session, job, contents, items, status=status, reason=reason, now=now)

    landed = JobState.IMPORTING if status is PlanStatus.AUTO else JobState.REVIEW
    if not await transition(session, job, landed, expected=JobState.PLANNING):
        logger.warning("job moved on before its plan could land")
        await session.rollback()
        return 0
    await _announce(session, job, row, status, reason)
    await session.commit()
    # 推播在 commit 之後（票 10 實跑抓到的那一條）：反過來的話前端收到提示就立刻重問，
    # 而那一次讀到的是還沒 commit 的舊狀態。
    hub.publish(JobSignal(hash=job.hash, state=job.state.value, progress=job.progress))
    logger.info(
        "job planned",
        extra={"state": job.state.value, "plan": row.id, "status": status.value},
    )
    return 1


async def _preplan(session: AsyncSession, hub: EventHub, job_hash: str, now: datetime) -> int:
    """`metadata_ready` 的另一半：一份預估（brief §5.1、plan §3.1）。

    **不碰網路也不碰磁碟**：快照就用存下來的那一份（送單那一刻才抓的，這時候頂多幾分鐘大），
    mediainfo 一個都不問（檔案還在下載，量到的一定是半份）。它回答的是「這一包對不對」，
    而那個答案在檔案清單裡就有了。
    """
    job = await session.get(Job, job_hash)
    if job is None or job.state not in ESTIMABLE:
        return 0
    route = await session.get(Route, job.route_id) if job.route_id is not None else None
    contents = await _contents(session, job)
    entries = contents.entries()
    if not entries:
        return 0
    items = await _against_ledger(
        session,
        job,
        route,
        _apply_policy(
            decide(job.name, entries, _context(route, await _stored(session, job))), route
        ),
    )
    _, reason = _verdict(items, route)
    row = await _store(
        session, job, contents, items, status=PlanStatus.PREPLAN, reason=reason, now=now
    )
    await record_event(
        session,
        job,
        EventType.PREPLAN,
        actor=actor_of(None),
        payload=plan_counts(row) | {"plan": row.id},
    )
    await session.commit()
    hub.publish(JobSignal(hash=job.hash, state=job.state.value, progress=job.progress))
    logger.info("job pre-planned", extra={"plan": row.id})
    return 1


async def _announce(
    session: AsyncSession,
    job: Job,
    row: Plan,
    status: PlanStatus,
    reason: ReviewReason | None,
) -> None:
    """一個轉換一筆事件（plan §3.1 的副作用欄）。

    `review` 那一條**不另外寫 `plan_generated`**：兩筆說的是同一件事，而時間線上一件事
    只該有一行。停下來的那一筆自己帶著同樣的計數，加上一個說得出下一步的理由。
    """
    counts = plan_counts(row) | {"plan": row.id}
    if status is PlanStatus.AUTO:
        await record_event(
            session,
            job,
            EventType.PLAN_GENERATED,
            actor=actor_of(None),
            payload=counts | {"engine": row.engine.value},
        )
        return
    await record_event(
        session,
        job,
        EventType.REVIEW_REQUIRED,
        actor=actor_of(None),
        payload=counts | {"reason": (reason or ReviewReason.LOW_CONFIDENCE).value},
    )


def plan_counts(row: Plan) -> dict[str, object]:
    """計劃那幾筆事件共用的計數。importer 停下來時寫的 `review_required` 也帶同一組。"""
    summary = PlanSummary.model_validate(row.summary_json or {})
    return {
        "files": summary.files,
        "high": summary.high,
        "medium": summary.medium,
        "low": summary.low,
    }


# --- 事實 ---------------------------------------------------------------


async def _snapshot(
    session: AsyncSession, factory: ServiceClientFactory, job: Job
) -> MediaSnapshot | None:
    if job.media_id is None:
        return None
    return await snapshot_for_planning(session, factory, job.media_id)


async def _stored(session: AsyncSession, job: Job) -> MediaSnapshot | None:
    """存下來的那一份，不刷新。pre-plan 用它——預估不該讓 TMDB 壞掉時整個停下來。"""
    if job.media_id is None:
        return None
    row = await session.get(Media, job.media_id)
    return row.stored_snapshot() if row is not None else None


def _context(route: Route | None, snapshot: MediaSnapshot | None) -> ParseContext:
    """解析器看得到的東西（plan §4.3）。

    `season_hint` 與 `episode_offset` 留空：那兩個是 RSS Rule 帶進來的（M3），
    手動送單的 Job 沒有它們。
    """
    return ParseContext(
        media=snapshot,
        route_collection_type=route.collection_type if route is not None else None,
    )


async def _contents(session: AsyncSession, job: Job) -> Contents:
    """這一包 torrent 現在有哪些檔案（`job_files`），以及它的內容根那一層。

    **一輪查一次**：算 entries、問 mediainfo、寫 plan items 三步用的是同一份，
    所以它們對「哪一段是根目錄」的答案不會分岔（`Contents`）。
    """
    rows = list(
        await session.scalars(
            select(JobFile).where(JobFile.job_hash == job.hash).order_by(JobFile.id)
        )
    )
    return Contents(rows=rows, root=_content_root([row.rel_path for row in rows]))


def _content_root(paths: Sequence[str]) -> str:
    """torrent 內容根那一層（含尾斜線），沒有就是空字串。

    多檔 torrent 一律有一個以發佈名命名的根目錄；單檔 torrent 沒有。「全部檔案共用同一個
    第一段」就是那件事的定義——共用不了的時候不動它，寧可多一層提示也不要砍掉真的資料夾。
    """
    if not paths or any("/" not in path for path in paths):
        return ""
    firsts = {path.split("/", 1)[0] for path in paths}
    return f"{firsts.pop()}/" if len(firsts) == 1 else ""


async def _measure(session: AsyncSession, job: Job, contents: Contents) -> tuple[FileEntry, ...]:
    """逐個影片問一次 mediainfo，把答案寫回 `job_files`（plan §3.1 的副作用）。

    **只問影片、只在下載完成之後問**：mediainfo 打開的是真的檔案，而其餘分類（字型、字幕、
    海報）沒有一個訊號是 Plan 用得上的。

    Berth 看不到那條 save path 時一個都不問：那不是這一筆 torrent 的問題，而是掛載對不上
    （Route 的 `download_path` 纜繩在回答它，plan §9.5）——逐檔問一次只會在 log 裡留下
    24 行一樣的警告。
    """
    entries = contents.entries()
    root = job.save_path
    if not root or not Path(root).is_absolute() or not Path(root).is_dir():
        logger.debug("mediainfo skipped: berth cannot see the save path", extra={"path": root})
        return entries

    measured: dict[str, int] = {}
    for entry in classify(entries):
        if entry.kind is not FileKind.VIDEO:
            continue
        row = contents.find(entry.rel_path)
        if row is None:
            continue
        # libmediainfo 是 C 函式庫，呼叫它的那一刻整條執行緒都在等——而這個迴圈同時是
        # SSE 的來源（`asyncio.to_thread`，`adapters/mediainfo.py`）。
        summary = await asyncio.to_thread(mediainfo.probe, fs.under(root, row.rel_path))
        if summary is None:
            continue
        row.mediainfo_json = summary.model_dump(mode="json")
        row.updated_at = utcnow()
        measured[entry.rel_path] = summary.duration_s
    await session.flush()
    return tuple(
        entry.model_copy(update={"duration_s": measured.get(entry.rel_path)}) for entry in entries
    )


# --- 決定 ---------------------------------------------------------------


def _apply_policy(items: Sequence[PlannedFile], route: Route | None) -> tuple[PlannedFile, ...]:
    """Route 的政策：`medium_auto_import = false` 時 medium 進 review（brief §6.5）。

    **改的是 `action` 而不是只記一個旗標**：importer 逐列看的就是 action（票 12），
    政策留在 Route 上的話「這一列會不會被寫出去」要兩個地方一起看才答得出來。

    `target_path` **留著**：那一格回答的是「它會去哪裡」，而這條政策說的是「先問一句」，
    不是「不知道」。畫面上那一列因此仍然說得出使用者真正想確認的那件事（plan §4.2 的
    「只有會被寫出去的檔案有值」在這裡讓步，票 11）。
    """
    if route is None or route.medium_auto_import:
        return tuple(items)
    return tuple(
        item.model_copy(
            update={
                "action": PlanAction.REVIEW,
                "reasons": (
                    *item.reasons,
                    "this route does not import medium confidence by itself",
                ),
            }
        )
        if item.action in WRITTEN and item.confidence is Confidence.MEDIUM
        else item
        for item in items
    )


async def _against_ledger(
    session: AsyncSession,
    job: Job,
    route: Route | None,
    items: Sequence[PlannedFile],
) -> tuple[PlannedFile, ...]:
    """媒體庫裡已經有、起始集相同而結束集不同的正片 → 這一列送 review（brief §7.8、§20.9）。

    解析器只看得見這一包裡的檔案，同一條規則在 `parser/planner.py`（純函式，benchmark 量它）；
    上一批入庫的那一集在帳本裡，而帳本要 session 才讀得到，所以這一半住在 services。

    比的是**同一個資料夾裡**、同一季、同一個起始集——那正是 Jellyfin 12 的版本分組鍵（同一個
    季資料夾、同一個 `S/E`，它不看結束集）。`S01E03-E04` 與 `S01E03` 於是被併成同一集的兩個
    版本，第 4 集從集列表上消失。**資料夾是判準的一部分**：同一部作品可以有兩條 Route（兩個
    Jellyfin 媒體庫、兩個資料夾），那是兩個條目，跨資料夾不會被併（`inventory._versions`
    的版本分組同一個道理）。
    """
    if job.media_id is None or route is None:
        return tuple(items)
    root = PurePosixPath(route.target_path)
    ends: dict[tuple[str, int, int], set[int]] = {}
    for entry in await session.scalars(
        select(LedgerEntry).where(
            LedgerEntry.media_id == job.media_id, LedgerEntry.action == PlanAction.IMPORT
        )
    ):
        if entry.season is None or entry.episode_start is None:
            continue
        folder = str(PurePosixPath(entry.target_path).parent)
        ends.setdefault((folder, entry.season, entry.episode_start), set()).add(
            entry.episode_end or entry.episode_start
        )
    return tuple(_against(item, root, ends) for item in items)


def _against(
    item: PlannedFile, root: PurePosixPath, ends: dict[tuple[str, int, int], set[int]]
) -> PlannedFile:
    """判準與同一包裡那一半共用（`parser.episode_span`）：分岔了就會有兩個答案。"""
    span = episode_span(item)
    if span is None or not item.target_path:
        return item
    season, start, end = span
    folder = str((root / item.target_path).parent)
    others = ends.get((folder, season, start), set()) - {end}
    if not others:
        return item
    return item.model_copy(
        update={
            "action": PlanAction.REVIEW,
            "confidence": Confidence.LOW,
            "reasons": (*item.reasons, _span_clash(season, start, others)),
        }
    )


def _span_clash(season: int, start: int, others: set[int]) -> str:
    """開頭說得出媒體庫裡已經有哪一段，後果接解析器那一句（同一個後果只有一份字）。"""
    known = ", ".join(
        f"S{season:02d}E{start:02d}" + (f"-E{end:02d}" if end != start else "")
        for end in sorted(others)
    )
    return (
        f"the library already has {known}, which starts at the same episode but covers a "
        f"different range; {SPAN_CLASH_CONSEQUENCE}"
    )


def _verdict(
    items: Sequence[PlannedFile], route: Route | None
) -> tuple[PlanStatus, ReviewReason | None]:
    """全 high / medium 且 Route 允許 → `auto`，否則 `pending_review`（plan §3.1）。

    三種理由的下一步不一樣，所以停下來的時候要說得出是哪一種（brief §5.2 的
    `review_required(reason)`）。

    **`unmatched` 不擋自動入庫**（票 11 的偏差，plan §3.1 已回寫）。照字面「全 high/medium」
    的話它會擋——unmatched 一律是 low。但那不是低信心，而是一個**已經做完的決定**：
    「這是一個節目，但它不是 TMDB 上的任何一集」（brief §7.6），檔案留在 complete 原位，
    人在 Unmatched 清單裡指派它（M2 的 `GET /review`）。動漫批次幾乎每一包都夾著一兩個
    這種 SP，擋下去等於「三種類型各一部不經人工入庫」（plan §11.2 T1.6）永遠達不到。
    它仍然被數進 `summary.low`，所以畫面上看得見。
    """
    held = [item for item in items if item.action is PlanAction.REVIEW]
    if any(item.confidence is not Confidence.MEDIUM for item in held):
        return PlanStatus.PENDING_REVIEW, ReviewReason.LOW_CONFIDENCE
    if held:
        # 只剩下被 Route 擋下的那幾個 medium——它們的季集是算得出來的，只差一句話。
        return PlanStatus.PENDING_REVIEW, ReviewReason.MEDIUM_NOT_ALLOWED
    if not any(item.action in WRITTEN for item in items):
        # 整包都是「不用管」的檔案。那不是低信心，是送錯了 torrent（brief §5.1）。
        return PlanStatus.PENDING_REVIEW, ReviewReason.NOTHING_TO_IMPORT
    return PlanStatus.AUTO, None


def _summarise(items: Sequence[PlannedFile], reason: ReviewReason | None) -> PlanSummary:
    """一份 Plan 的一句話（`plans.summary_json`）。

    信心只數**不是 skip 的那些**：字型與海報雙方都同意可以忽略，把它們算進 high 會讓
    「這一包有多可信」被一堆沒有人在意的檔案稀釋（`berth bench` 分桶的同一個道理）。
    """
    counted = [item for item in items if item.action is not PlanAction.SKIP]
    levels = Counter(item.confidence for item in counted)
    return PlanSummary(
        files=sum(1 for item in items if item.action in WRITTEN),
        high=levels[Confidence.HIGH],
        medium=levels[Confidence.MEDIUM],
        low=levels[Confidence.LOW],
        actions={
            action.value: count for action, count in Counter(item.action for item in items).items()
        },
        review_reason=reason,
    )


async def _store(
    session: AsyncSession,
    job: Job,
    contents: Contents,
    items: Sequence[PlannedFile],
    *,
    status: PlanStatus,
    reason: ReviewReason | None,
    now: datetime,
) -> Plan:
    """把這一輪的決定寫下來，**整份換掉**上一輪的（`models/plan.py`）。

    順手把分類寫回 `job_files`：那一欄與 `plan_items.action` 是同一次計算的兩半，
    而分類是 mediainfo 修正過的那一份（brief §6.2），第一次建列時還不知道。
    """
    row = await session.scalar(select(Plan).where(Plan.job_hash == job.hash))
    if row is None:
        row = Plan(job_hash=job.hash, status=status)
        session.add(row)
        await session.flush()
    else:
        await session.execute(delete(PlanItem).where(PlanItem.plan_id == row.id))
    row.status = status
    row.engine = PlanEngine.RULES
    row.engine_version = VERSION
    row.summary_json = _summarise(items, reason).model_dump(mode="json")
    # 這一列永遠是「現在的計劃」，所以它的時間就是**算出它**的時間；上一份留在時間線上。
    row.created_at = now

    for item in items:
        source = contents.find(item.rel_path)
        if source is not None:
            source.kind = item.kind
        session.add(
            PlanItem(
                plan_id=row.id,
                job_file_id=source.id if source is not None else None,
                rel_path=item.rel_path,
                action=item.action,
                media_id=job.media_id,
                season=item.season,
                episode_start=item.episode_start,
                episode_end=item.episode_end,
                tags_json=_tags(item.tags),
                target_path=item.target_path,
                confidence=item.confidence,
                reasons_json=list(item.reasons),
                audit=_audit(item, status),
            )
        )
    await session.flush()
    return row


def _audit(item: PlannedFile, status: PlanStatus) -> bool:
    """medium **而且真的自動入庫了**才掛 audit（brief §6.5、CONTEXT.md）。

    停在 review 的那一份誰都還沒動過，那時候掛旗標會讓 Review Queue 把「已入庫待確認」
    與「還沒入庫」混成同一列。
    """
    return (
        status is PlanStatus.AUTO
        and item.confidence is Confidence.MEDIUM
        and item.action in WRITTEN
    )


def _tags(tags: Tags) -> dict[str, object] | None:
    """空的 tag 不佔一格 JSON：分類就決定得了處置的那些檔案本來就沒有版本可言。"""
    dumped: dict[str, object] = tags.model_dump(mode="json")
    return dumped if tags.render() else None
