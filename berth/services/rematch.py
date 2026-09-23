"""改一個檔案的處置：rematch（brief §7.4、§9.4、plan §6 files 群組、M2 票 08）。

一個已經在 complete 裡的檔案——對不到的（Unmatched），或已經鏈接進媒體庫的——事後改成
「指派為某一集」「標記為 extra」「忽略」。**一律經過 Plan**（brief §9.4，plan §11.3 決定 8）：
內部建一份 `job_hash = NULL`、`engine = user` 的 Plan 並立刻套用，所以修正也留得下紀錄；對外是
一支命令，畫面不必看到一份只有一列的 Plan。重複版本的「取代舊版」「保留兩者」走同一步
（`services/duplicates.py`）。

**順序是 importer 的那一條**（`services/importer.py`）：建新鏈接 → 拆舊鏈接 → 改帳本 → 通知掃描。

- **磁碟先、紀錄後**：新的鏈接建不起來、舊的拆不掉，都在寫任何一筆紀錄之前丟出來
  （`RematchRefusal`）。拆不掉時剛建的那一條收回，所以拒絕的意思永遠是「什麼都沒變」。
- **帳本那一列改寫，不是刪了再建**：`ledger.id` 是 Review Queue 與畫面指向它的東西，而同一條
  路徑換來源時（取代舊版）刪了再建會在同一次 flush 裡撞上 `target_path` 的唯一索引。
- **字幕跟著影片走**（brief §6.7）：已入庫的正片改到另一集，旁邊那幾個字幕改名跟過去；改成
  extra 或忽略時一起拆掉——特典旁邊不掛字幕（`parser.planner._FOLLOWS`）。字幕搬不成只記在
  它那一列上，不擋影片（importer 的 `SKIPPABLE` 同一個道理）。
- **Job 的那一份 Plan 跟著改**：那一列 Plan Item 說的是「這個檔案現在怎麼處置」，Media 詳情的
  Unmatched 區、佇列與下載列表都讀它。單列 Plan 是這一次修正的紀錄，Job 的那一份是現況。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters import fs
from berth.config import VERSION
from berth.domain import (
    REMATCH_ACTIONS,
    SETTLED_PLANS,
    Confidence,
    EventType,
    FileKind,
    MediaKind,
    MediaSnapshot,
    PlanAction,
    PlanEngine,
    PlanStatus,
    RematchRefusal,
    Tags,
    why,
)
from berth.domain import PlanItem as PlannedFile
from berth.domain import ReasonCode as Code
from berth.logs import job_context
from berth.models import Job, JobFile, LedgerEntry, Media, Plan, PlanItem, Route
from berth.models.types import utcnow
from berth.parser import revise
from berth.services.clients import ServiceClientFactory
from berth.services.deletion import remove_one, route_targets
from berth.services.importer import (
    TargetTakenError,
    link_into,
    notify_jellyfin,
    record_link,
    restate_versions,
)
from berth.services.jobs import job_lock, record_event
from berth.services.plan import WRITTEN, summarise
from berth.services.plan_view import dump_reasons, dump_tags, load_plan, reasons_of
from berth.services.steps import message

logger = logging.getLogger(__name__)


class RematchRejectedError(Exception):
    """改不下去，而且**什麼都沒變**（`domain.RematchRefusal`）。"""

    def __init__(self, reason: RematchRefusal, detail: str) -> None:
        super().__init__(f"{reason.value}: {detail}")
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True, slots=True)
class Assignment:
    """要改成什麼。季集只屬於劇集的入庫，其餘處置三格都是 `None`。"""

    action: PlanAction
    season: int | None = None
    episode_start: int | None = None
    episode_end: int | None = None


@dataclass(frozen=True, slots=True)
class RematchOutcome:
    """改完的樣子。"""

    #: 記下這一次修正的那一份單列 Plan。
    plan_id: int
    #: 這個檔案現在在媒體庫的哪裡（容器裡的完整路徑）；不在媒體庫裡是空字串。
    target_path: str


@dataclass(slots=True)
class Move:
    """一個檔案要變成什麼：來源、決定好的樣子（`target_path` 相對 Route 目標），以及它原本在
    媒體庫裡的那一列帳本（沒有就是 `None`）。"""

    source: Path
    #: 與 `job_files.rel_path` / `ledger.source_rel_path` 同形。
    source_rel: str
    job_hash: str | None
    job_file_id: int | None
    planned: PlannedFile
    old: LedgerEntry | None
    #: Job 那一份 Plan 裡說這個檔案的那一列。跟著改，因為它說的是現況。
    mirror: PlanItem | None
    #: 被這一步取代的**另一筆** Job 的那一列（取代舊版，`services/duplicates.py`）：那一集已經不是
    #: 它的了，它的 Plan 要改成沒有落點。rematch 自己搬的都是同一筆 Job 的檔案，沒有這一格。
    displaced: PlanItem | None = None
    #: 碰了磁碟之後的結果：鏈接完量到的兩邊，或這一步為什麼沒成（只有字幕會走到這裡）。
    facts: tuple[fs.PathFacts, fs.PathFacts] | None = None
    error: str = ""
    #: 這一步拆掉的舊路徑（通知 Jellyfin 用）。
    removed: str = ""


@dataclass(slots=True)
class Landing:
    """一次修正要做的事：同一筆 Job、同一部作品、同一條 Route 底下的幾個檔案，第一個是主角。"""

    job: Job | None
    media: MediaSnapshot | None
    media_id: str | None
    #: Route 的目標路徑；不寫進媒體庫的修正（忽略）不需要它。
    root: str | None
    moves: list[Move] = field(default_factory=list)


async def rematch_file(
    session: AsyncSession,
    factory: ServiceClientFactory,
    *,
    ledger_id: int | None = None,
    job_file_id: int | None = None,
    to: Assignment,
    actor: str,
) -> RematchOutcome:
    """`POST /files/rematch`：已入庫的帶 `ledger_id`，對不到的帶 `job_file_id`（二選一）。"""
    job_hash = await _job_hash_of(session, ledger_id=ledger_id, job_file_id=job_file_id)
    async with locked(job_hash):
        if ledger_id is not None:
            landing, kind, before = await _linked(session, ledger_id)
        else:
            assert job_file_id is not None  # 二選一由呼叫端（API 的 model）保證
            landing, kind, before = await _unmatched(session, job_file_id)
        main = landing.moves[0]
        main.planned = _decided(main.planned, kind, to, landing)
        landing.moves.extend(await _sidecars(session, landing, main))
        plan = await land(session, landing, actor=actor)
        if landing.job is not None:
            await record_event(
                session,
                landing.job,
                EventType.REMATCHED,
                actor=actor,
                payload={
                    "plan": plan.id,
                    "file": main.source_rel,
                    "from": before,
                    "to": _state(main.planned, full_path(landing.root, main.planned)),
                },
            )
        await session.commit()
    await announce(session, factory, landing)
    logger.info("file rematched", extra={"plan": plan.id, "action": to.action.value})
    return RematchOutcome(plan_id=plan.id, target_path=full_path(landing.root, main.planned))


# --- 主角是誰 -------------------------------------------------------------


async def _job_hash_of(
    session: AsyncSession, *, ledger_id: int | None, job_file_id: int | None
) -> str | None:
    """鎖外那一次讀，只為了知道要鎖哪一筆 Job。鎖裡那一次（`populate_existing`）才算數。"""
    if ledger_id is not None:
        entry = await session.get(LedgerEntry, ledger_id)
        if entry is None:
            raise RematchRejectedError(RematchRefusal.LEDGER_MISSING, str(ledger_id))
        return entry.job_hash
    row = await session.get(JobFile, job_file_id)
    if row is None:
        raise RematchRejectedError(RematchRefusal.FILE_MISSING, str(job_file_id))
    return row.job_hash


@asynccontextmanager
async def locked(*job_hashes: str | None) -> AsyncIterator[None]:
    """鎖住這幾筆 Job：importer 的重試、audit 的兩顆、Plan 編輯、刪除都寫同一份 Plan 與帳本。

    **取代舊版要兩把**（code-review 抓到）：它拆的是另一筆 Job 的鏈接、改的是那一筆的帳本，只鎖
    新的那一筆的話，舊的那一筆上同時按下的撤銷會拆到剛換上去的新鏈接。多把時照 hash 排序依序拿，
    兩個方向同時取代的兩個分頁才不會互等。重新入庫建出來的帳本沒有 Job（`models/ledger.py`），
    那一份沒有鎖可拿。例外離開時由呼叫端的 session 收拾：拒絕都在寫入之前丟出來。
    """
    wanted = sorted({job_hash for job_hash in job_hashes if job_hash is not None})
    async with AsyncExitStack() as stack:
        if wanted:
            stack.enter_context(job_context(wanted[0]))
        for job_hash in wanted:
            await stack.enter_async_context(job_lock(job_hash))
        yield


async def _linked(
    session: AsyncSession, ledger_id: int
) -> tuple[Landing, FileKind, dict[str, object]]:
    """一個已經在媒體庫裡的檔案（帳本那一列）。"""
    entry = await session.get(LedgerEntry, ledger_id, populate_existing=True)
    if entry is None:
        raise RematchRejectedError(RematchRefusal.LEDGER_MISSING, str(ledger_id))
    job = await session.get(Job, entry.job_hash) if entry.job_hash is not None else None
    row = await _job_file(session, entry.job_hash, entry.source_rel_path)
    kind = (row.kind if row is not None else None) or (
        FileKind.SUBTITLE if entry.action is PlanAction.SUBTITLE else FileKind.VIDEO
    )
    landing = Landing(
        job=job,
        media=await _snapshot(session, entry.media_id),
        media_id=entry.media_id,
        root=await _root(session, job, entry.target_path),
    )
    landing.moves.append(
        Move(
            source=Path(entry.source_abs_path),
            source_rel=entry.source_rel_path,
            job_hash=entry.job_hash,
            job_file_id=row.id if row is not None else None,
            planned=_planned(
                entry.source_rel_path, kind, Tags.model_validate(entry.tags_json or {})
            ),
            old=entry,
            mirror=await _mirror_of(session, job, row),
        )
    )
    before: dict[str, object] = {
        "action": entry.action.value,
        "season": entry.season,
        "episode_start": entry.episode_start,
        "episode_end": entry.episode_end,
        "target": entry.target_path,
    }
    # 字幕跟著它的影片走，自己不另外改（`REMATCH_ACTIONS` 對字幕只給忽略）。
    return landing, kind, before


async def _unmatched(
    session: AsyncSession, job_file_id: int
) -> tuple[Landing, FileKind, dict[str, object]]:
    """一個對不到、留在 complete 原位的檔案（brief §7.4）。"""
    row = await session.get(JobFile, job_file_id, populate_existing=True)
    if row is None:
        raise RematchRejectedError(RematchRefusal.FILE_MISSING, str(job_file_id))
    job = await session.get(Job, row.job_hash, populate_existing=True)
    plan = await session.scalar(select(Plan).where(Plan.job_hash == row.job_hash))
    mirror = await _mirror_of(session, job, row)
    if job is None or plan is None or mirror is None or mirror.action is not PlanAction.UNMATCHED:
        raise RematchRejectedError(RematchRefusal.NOT_UNMATCHED, row.rel_path)
    if plan.status not in SETTLED_PLANS:
        # 預估（檔案還在下載）、等審核（那時候改它是 Plan 編輯的事）、被拒絕（正要整份重算）。
        raise RematchRejectedError(RematchRefusal.PLAN_PENDING, plan.status.value)
    landing = Landing(
        job=job,
        media=await _snapshot(session, job.media_id),
        media_id=job.media_id,
        root=await _root(session, job, None),
    )
    landing.moves.append(
        Move(
            source=fs.under(job.save_path, row.rel_path),
            source_rel=row.rel_path,
            job_hash=job.hash,
            job_file_id=row.id,
            planned=_planned(
                row.rel_path,
                row.kind or FileKind.OTHER,
                Tags.model_validate(mirror.tags_json or {}),
            ),
            old=None,
            mirror=mirror,
        )
    )
    before: dict[str, object] = {
        "action": PlanAction.UNMATCHED.value,
        "season": None,
        "episode_start": None,
        "episode_end": None,
        "target": "",
    }
    return landing, row.kind or FileKind.OTHER, before


async def _job_file(session: AsyncSession, job_hash: str | None, rel_path: str) -> JobFile | None:
    if job_hash is None:
        return None
    found: JobFile | None = await session.scalar(
        select(JobFile).where(JobFile.job_hash == job_hash, JobFile.rel_path == rel_path)
    )
    return found


async def claimant(session: AsyncSession, entry: LedgerEntry) -> PlanItem | None:
    """帳本這一列的來源在它那一筆 Job 的 Plan 裡是哪一列（取代舊版時要改成沒有落點的那一列）。"""
    job = await session.get(Job, entry.job_hash) if entry.job_hash is not None else None
    return await _mirror_of(
        session, job, await _job_file(session, entry.job_hash, entry.source_rel_path)
    )


async def _mirror_of(
    session: AsyncSession, job: Job | None, row: JobFile | None
) -> PlanItem | None:
    """Job 那一份 Plan 裡說這個檔案的那一列（以 `job_file_id` 找，不以帳本的 `plan_item_id`：
    那一格可能指向上一次修正的單列 Plan，而歷史不該被改寫）。"""
    if job is None or row is None:
        return None
    found: PlanItem | None = await session.scalar(
        select(PlanItem)
        .join(Plan, Plan.id == PlanItem.plan_id)
        .where(Plan.job_hash == job.hash, PlanItem.job_file_id == row.id)
        .execution_options(populate_existing=True)
    )
    return found


async def _snapshot(session: AsyncSession, media_id: str | None) -> MediaSnapshot | None:
    if media_id is None:
        return None
    media = await session.get(Media, media_id)
    return media.stored_snapshot() if media is not None else None


async def _root(session: AsyncSession, job: Job | None, target: str | None) -> str | None:
    """收這個檔案的 Route 的目標。Job 記著它；沒有 Job 時看舊的那條路徑落在哪一條底下。"""
    if job is not None and job.route_id is not None:
        route = await session.get(Route, job.route_id)
        if route is not None:
            return route.target_path
    if target is None:
        return None
    try:
        return str(fs.root_of(Path(target), await route_targets(session)))
    except fs.PathEscapeError:
        return None


def _planned(rel_path: str, kind: FileKind, tags: Tags) -> PlannedFile:
    """還沒決定的樣子：只有身分與 Tags。`_decided` 填上處置與路徑。"""
    return PlannedFile(
        rel_path=rel_path,
        kind=kind,
        action=PlanAction.SKIP,
        tags=tags,
        confidence=Confidence.HIGH,
        reasons=(why(Code.SET_BY_USER),),
    )


# --- 決定 -----------------------------------------------------------------


def _decided(planned: PlannedFile, kind: FileKind, to: Assignment, landing: Landing) -> PlannedFile:
    """人說的處置，合不合法（矛盾的拒絕，不是默默修正），以及它會落在哪裡。

    **人親手指定的一列信心是 high**：信心說的是「這個答案有多可信」，而這一個是人給的。路徑由
    `parser.revise` 算，與規劃、Plan 編輯同一份命名規則。
    """
    name = planned.name
    media = landing.media
    if to.action not in REMATCH_ACTIONS[kind]:
        raise RematchRejectedError(RematchRefusal.ACTION_NOT_ALLOWED, name)
    if to.action in WRITTEN and media is None:
        raise RematchRejectedError(RematchRefusal.MEDIA_MISSING, name)
    if to.action in WRITTEN and landing.root is None:
        raise RematchRejectedError(RematchRefusal.ROUTE_MISSING, name)
    numbered = to.action is PlanAction.IMPORT and media is not None and media.kind is MediaKind.TV
    given = (to.season, to.episode_start, to.episode_end)
    if not numbered:
        if any(value is not None for value in given):
            raise RematchRejectedError(RematchRefusal.EPISODE_NOT_ALLOWED, name)
    else:
        if to.season is None or to.episode_start is None:
            raise RematchRejectedError(RematchRefusal.EPISODE_REQUIRED, name)
        if to.episode_end is not None and to.episode_end < to.episode_start:
            raise RematchRejectedError(RematchRefusal.EPISODE_RANGE_REVERSED, name)
    # 結束集等於起始集時存成 `None`：`S01E05-E05` 不是一種檔名（同 `plan_review._edited`）。
    end = None if to.episode_end == to.episode_start else to.episode_end
    decided = planned.model_copy(
        update={
            "action": to.action,
            "season": to.season,
            "episode_start": to.episode_start,
            "episode_end": end,
        }
    )
    (landed,) = revise((decided,), media)
    return landed


async def _sidecars(session: AsyncSession, landing: Landing, main: Move) -> list[Move]:
    """已入庫的正片旁邊那幾個字幕，跟著它走（brief §6.7）。

    旁邊的定義是命名規則的那一條（`naming.subtitle_target`）：同一個資料夾、檔名以影片的主幹
    加一個點開頭。路徑沒變時什麼都不做。
    """
    old = main.old
    if old is None or old.action is not PlanAction.IMPORT:
        return []
    new_target = full_path(landing.root, main.planned)
    if new_target == old.target_path:
        return []
    stem = str(PurePosixPath(old.target_path).with_suffix(""))
    moves = []
    following = main.planned.action is PlanAction.IMPORT
    new_stem = str(PurePosixPath(main.planned.target_path).with_suffix("")) if following else ""
    for entry in await sidecars_of(session, old):
        tail = entry.target_path[len(stem) :]
        reasons = (why(Code.SUBTITLE_FOLLOWS, video=main.source_rel), why(Code.SET_BY_USER))
        planned = PlannedFile(
            rel_path=entry.source_rel_path,
            kind=FileKind.SUBTITLE,
            action=PlanAction.SUBTITLE if following else PlanAction.SKIP,
            season=main.planned.season if following else None,
            episode_start=main.planned.episode_start if following else None,
            episode_end=main.planned.episode_end if following else None,
            tags=Tags.model_validate(entry.tags_json or {}),
            confidence=Confidence.HIGH,
            target_path=f"{new_stem}{tail}" if following else "",
            reasons=reasons
            if following
            else (*reasons, why(Code.VIDEO_NOT_IMPORTED, action=main.planned.action.value)),
        )
        job = await session.get(Job, entry.job_hash) if entry.job_hash is not None else None
        row = await _job_file(session, entry.job_hash, entry.source_rel_path)
        moves.append(
            Move(
                source=Path(entry.source_abs_path),
                source_rel=entry.source_rel_path,
                job_hash=entry.job_hash,
                job_file_id=row.id if row is not None else None,
                planned=planned,
                old=entry,
                mirror=await _mirror_of(session, job, row),
            )
        )
    return moves


async def sidecars_of(session: AsyncSession, video: LedgerEntry) -> list[LedgerEntry]:
    """帳本上掛在這個影片旁邊的字幕。旁邊的定義是命名規則的那一條（`naming.subtitle_target`）：
    同一個資料夾、檔名以影片的主幹加一個點開頭。rematch 與取代舊版共用這一份。"""
    stem = str(PurePosixPath(video.target_path).with_suffix(""))
    return list(
        await session.scalars(
            select(LedgerEntry)
            .where(
                LedgerEntry.action == PlanAction.SUBTITLE,
                LedgerEntry.target_path.startswith(f"{stem}.", autoescape=True),
                LedgerEntry.id != video.id,
            )
            .order_by(LedgerEntry.id)
        )
    )


# --- 套用 -----------------------------------------------------------------


async def land(session: AsyncSession, landing: Landing, *, actor: str) -> Plan:
    """磁碟 → 紀錄。第一個檔案做不成就整個拒絕（還沒寫任何東西）；其餘的只記在自己那一列。

    回記下這一次修正的單列 Plan（尚未 commit）。
    """
    now = utcnow()
    roots = await route_targets(session)
    for index, move in enumerate(landing.moves):
        try:
            await _carry_out(session, landing, move, roots)
        except RematchRejectedError as refusal:
            if index == 0:
                raise
            move.error = refusal.detail or refusal.reason.value
            logger.warning("a follower did not move", extra={"file": move.source_rel})
    return await _record(session, landing, actor=actor, now=now)


async def _carry_out(
    session: AsyncSession, landing: Landing, move: Move, roots: Sequence[Path]
) -> None:
    """一個檔案在磁碟上：鏈到新的地方，再拆舊的。**拆不掉就把新的收回**，然後拒絕。"""
    new = full_path(landing.root, move.planned) if move.planned.action in WRITTEN else ""
    old = move.old.target_path if move.old is not None else ""
    if new:
        taken = await session.scalar(
            select(LedgerEntry.id).where(
                LedgerEntry.target_path == new,
                LedgerEntry.id != (move.old.id if move.old is not None else -1),
            )
        )
        if taken is not None:
            raise RematchRejectedError(RematchRefusal.TARGET_TAKEN, new)
    created = False
    try:
        if new and new == old and move.old is not None:
            if move.old.source_abs_path != str(move.source):
                # 同一條路徑換另一個來源（取代舊版）：一步換過去，中間沒有一刻是空的。
                fs.replace_link(move.source, Path(new), roots=roots)
            move.facts = link_into(move.source, Path(new), roots=roots)
        elif new:
            created = not Path(new).exists()
            move.facts = link_into(move.source, Path(new), roots=roots)
    except TargetTakenError as exc:
        raise RematchRejectedError(RematchRefusal.TARGET_TAKEN, new) from exc
    except (OSError, fs.PathEscapeError) as exc:
        raise RematchRejectedError(RematchRefusal.LINK_FAILED, message(exc)) from exc
    if old and old != new:
        try:
            remove_one(Path(old), roots=roots)
        except (OSError, fs.PathEscapeError) as exc:
            if created:
                _take_back(Path(new), roots)
            raise RematchRejectedError(RematchRefusal.UNLINK_FAILED, message(exc)) from exc
        move.removed = old


def _take_back(path: Path, roots: Sequence[Path]) -> None:
    """拆舊的失敗時收回剛建的那一條。收不回只留一行 log：它與來源同一個 inode，下一輪對帳看得到。"""
    try:
        remove_one(path, roots=roots)
    except (OSError, fs.PathEscapeError):
        logger.warning("a new link could not be taken back", extra={"target": str(path)})


async def _record(session: AsyncSession, landing: Landing, *, actor: str, now: datetime) -> Plan:
    """磁碟上的事做完了，紀錄跟上：單列 Plan、帳本、Job 那一份 Plan 的那幾列。"""
    main = landing.moves[0]
    plan = Plan(
        job_hash=None,
        source_path=str(main.source),
        engine=PlanEngine.USER,
        engine_version=VERSION,
        status=PlanStatus.APPLIED,
        summary_json=summarise([move.planned for move in landing.moves], None).model_dump(
            mode="json"
        ),
        created_at=now,
        decided_by=actor,
        decided_at=now,
    )
    session.add(plan)
    await session.flush()
    mirrored: set[int] = set()
    for move in landing.moves:
        planned = move.planned
        done = not move.error
        written = done and planned.action in WRITTEN and move.facts is not None
        item = PlanItem(
            plan_id=plan.id,
            job_file_id=move.job_file_id,
            rel_path=move.source_rel,
            action=planned.action,
            media_id=landing.media_id,
            season=planned.season,
            episode_start=planned.episode_start,
            episode_end=planned.episode_end,
            tags_json=dump_tags(planned.tags),
            target_path=planned.target_path,
            confidence=planned.confidence,
            reasons_json=dump_reasons(planned.reasons),
            applied_at=now if written else None,
            error=move.error,
        )
        session.add(item)
        await session.flush()
        if not done:
            continue
        target = full_path(landing.root, planned)
        if written and move.facts is not None:
            entry = move.old if move.old is not None else LedgerEntry()
            record_link(
                entry,
                job_hash=move.job_hash,
                source_rel_path=move.source_rel,
                source=move.source,
                target=target,
                facts=move.facts,
                item=item,
                now=now,
            )
            if move.old is None:
                session.add(entry)
            await restate_versions(session, item, target, now)
        elif move.old is not None:
            await session.delete(move.old)
        if move.mirror is not None:
            _mirror(move.mirror, item)
            mirrored.add(move.mirror.plan_id)
        if move.displaced is not None:
            _displace(move.displaced)
            mirrored.add(move.displaced.plan_id)
    await session.flush()
    for plan_id in mirrored:
        await _resummarise(session, plan_id)
    return plan


def _mirror(row: PlanItem, landed: PlanItem) -> None:
    """Job 那一份 Plan 的那一列改成現況。人說了算，所以理由多一條 `set_by_user`、清掉錯誤與旗標。"""
    row.action = landed.action
    row.season = landed.season
    row.episode_start = landed.episode_start
    row.episode_end = landed.episode_end
    row.target_path = landed.target_path
    row.confidence = landed.confidence
    row.applied_at = landed.applied_at
    row.error = ""
    row.audit = False
    row.duplicate_of = None
    marked = why(Code.SET_BY_USER)
    reasons = reasons_of(row)
    row.reasons_json = dump_reasons(reasons if marked in reasons else (*reasons, marked))


def _displace(row: PlanItem) -> None:
    """被取代的那一方：它的檔案還在 complete 裡，但媒體庫裡那一集已經是別人的了。"""
    row.action = PlanAction.SKIP
    row.target_path = ""
    row.applied_at = None
    row.audit = False
    marked = why(Code.SET_BY_USER)
    reasons = reasons_of(row)
    row.reasons_json = dump_reasons(reasons if marked in reasons else (*reasons, marked))


async def _resummarise(session: AsyncSession, plan_id: int) -> None:
    """Job 那一份 Plan 的摘要重算：下載列表那一列的「要入庫 N 個」數的是它。"""
    loaded = await load_plan(session, plan_id)
    if loaded is None:
        return
    reason = (loaded.plan.summary_json or {}).get("review_reason")
    summary = summarise(loaded.items, None).model_dump(mode="json")
    loaded.plan.summary_json = summary | {"review_reason": reason}


async def announce(session: AsyncSession, factory: ServiceClientFactory, landing: Landing) -> None:
    """通知 Jellyfin：新鏈接的路徑與拆掉的路徑（brief §20.1：它對每一條都重讀那個資料夾）。

    在紀錄 commit 之後（plan §3.3）：通知失敗只記事件，檔案已經在媒體庫裡了。
    """
    paths = [
        path
        for move in landing.moves
        if not move.error
        for path in (
            full_path(landing.root, move.planned) if move.facts is not None else "",
            move.removed,
        )
        if path
    ]
    await notify_jellyfin(session, factory, landing.job, list(dict.fromkeys(paths)))
    await session.commit()


def full_path(root: str | None, planned: PlannedFile) -> str:
    """容器裡的完整路徑（Jellyfin 回報 `Path` 的形狀）。不寫進媒體庫的是空字串。"""
    if root is None or planned.action not in WRITTEN or not planned.target_path:
        return ""
    return str(PurePosixPath(root) / planned.target_path)


def _state(planned: PlannedFile, target: str) -> dict[str, object]:
    """時間線上「從什麼改成什麼」的一半。"""
    return {
        "action": planned.action.value,
        "season": planned.season,
        "episode_start": planned.episode_start,
        "episode_end": planned.episode_end,
        "target": target,
    }
