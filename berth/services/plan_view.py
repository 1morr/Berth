"""Import Plan 的讀取端：表格上的每一列，以及「核准的話它會落在哪裡」。

plan §6 plans 群組、票 11、M2 票 07。

M1 這一份是唯讀的答案；M2 票 07 起停在 review 的 Plan 逐列改得動（`services/plan_review.py`），
而這一支多回答兩件事：

- **每一列改得成哪幾種處置**（`EDITABLE_ACTIONS`，依分類）。前端照它畫選單，不自己判斷。
- **核准的話它會寫到哪裡**：`pending_review` 的 Plan，每一列的 `target_path` 是「照提案入庫」
  之後的那一條（`landing`，2026-09-23 使用者拍板），與核准時真的寫進 `plan_items` 的是**同一次
  計算**——畫面上看到的就是 importer 待會兒鏈接的那一條。

讀寫的形狀（資料庫的列 ↔ 解析器的 `PlanItem`）也在這裡，因為編輯與核准要的是同一份。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import (
    EDITABLE_ACTIONS,
    Confidence,
    FileKind,
    ItemReason,
    MediaKind,
    MediaSnapshot,
    PlanAction,
    PlanEngine,
    PlanStatus,
    PlanSummary,
    Tags,
)
from berth.domain import PlanItem as PlannedFile
from berth.models import Job, JobFile, Media, Plan, PlanItem
from berth.parser import promote, revise


@dataclass(frozen=True, slots=True)
class PlanItemView:
    """Plan 表格上的一列（brief §6.5：決定、信心與理由）。"""

    id: int
    rel_path: str
    kind: FileKind
    action: PlanAction
    media_id: str | None
    season: int | None
    episode_start: int | None
    episode_end: int | None
    #: 相對於 Route 目標的位置。`pending_review` 時是**核准的話**它會落在哪裡（`landing`）。
    target_path: str
    confidence: Confidence
    reasons: tuple[ItemReason, ...]
    #: medium 自動入庫掛的旗標（CONTEXT.md 的 Audit）。
    audit: bool
    #: 已經鏈接進媒體庫了。這一列在這裡改不動——那是 rematch 的事（票 08）。
    applied: bool
    #: 這一列改得成哪幾種處置，第一個是它的分類最常見的那一種。改不動時是空的。
    actions: tuple[PlanAction, ...]
    error: str


@dataclass(frozen=True, slots=True)
class PlanSeries:
    """算一份 Plan 時交給解析器的 RSS Series 與它當時的值（`plans.rss_series_id` 那三格）。"""

    id: int
    season: int | None
    episode_offset: int | None


@dataclass(frozen=True, slots=True)
class PlanView:
    """一份 Plan 的一整份（`GET /api/plans/{id}`）。"""

    id: int
    job_hash: str | None
    status: PlanStatus
    engine: PlanEngine
    engine_version: str
    created_at: datetime
    #: 劇集或電影。電影的列沒有季集可改，畫面照它決定要不要畫那三格。
    media_kind: MediaKind | None
    summary: PlanSummary
    items: tuple[PlanItemView, ...]
    #: 算這一份時交給解析器的 RSS Series 與它的值（M3 票 13）。不是 RSS 送的是 `None`。
    series: PlanSeries | None = None


@dataclass(frozen=True, slots=True)
class LoadedPlan:
    """一份 Plan 的列，攤成解析器的形狀（`rows` 與 `items` 同一個順序）。"""

    plan: Plan
    rows: list[PlanItem]
    items: tuple[PlannedFile, ...]
    media: MediaSnapshot | None
    #: 已經鏈接進媒體庫的那幾列（rel_path）。它們的路徑是磁碟上的事實（`parser.revise`）。
    settled: frozenset[str]


async def read_plan(session: AsyncSession, plan_id: int) -> PlanView | None:
    loaded = await load_plan(session, plan_id)
    if loaded is None:
        return None
    row = loaded.plan
    editable = row.status is PlanStatus.PENDING_REVIEW
    shown = landing(loaded) if editable else loaded.items
    return PlanView(
        id=row.id,
        job_hash=row.job_hash,
        status=row.status,
        engine=row.engine,
        engine_version=row.engine_version,
        created_at=row.created_at,
        media_kind=loaded.media.kind if loaded.media is not None else None,
        summary=PlanSummary.model_validate(row.summary_json or {}),
        series=None
        if row.rss_series_id is None
        else PlanSeries(
            id=row.rss_series_id, season=row.season_hint, episode_offset=row.episode_offset
        ),
        items=tuple(
            PlanItemView(
                id=stored.id,
                rel_path=stored.rel_path,
                kind=item.kind,
                action=stored.action,
                media_id=stored.media_id,
                season=stored.season,
                episode_start=stored.episode_start,
                episode_end=stored.episode_end,
                target_path=landed.target_path,
                confidence=stored.confidence,
                reasons=item.reasons,
                audit=stored.audit,
                applied=stored.applied_at is not None,
                actions=(
                    EDITABLE_ACTIONS[item.kind] if editable and stored.applied_at is None else ()
                ),
                error=stored.error,
            )
            for stored, item, landed in zip(loaded.rows, loaded.items, shown, strict=True)
        ),
    )


def landing(loaded: LoadedPlan) -> tuple[PlannedFile, ...]:
    """核准的話每一列會變成什麼（`parser.promote` + `parser.revise`）。核准寫下的就是這一份。"""
    return revise(promote(loaded.items, loaded.media), loaded.media, settled=loaded.settled)


async def load_plan(session: AsyncSession, plan_id: int) -> LoadedPlan | None:
    """一份 Plan 與它的列、分類、作品快照。**不打網路**：快照用存下來的那一份。"""
    plan = await session.get(Plan, plan_id, populate_existing=True)
    if plan is None:
        return None
    rows = list(
        await session.scalars(
            select(PlanItem)
            .where(PlanItem.plan_id == plan.id)
            .order_by(PlanItem.id)
            .execution_options(populate_existing=True)
        )
    )
    kinds = await _kinds(session, rows)
    return LoadedPlan(
        plan=plan,
        rows=rows,
        items=tuple(planned(row, kinds.get(row.job_file_id)) for row in rows),
        media=await _media(session, plan, rows),
        settled=frozenset(row.rel_path for row in rows if row.applied_at is not None),
    )


def planned(row: PlanItem, kind: FileKind | None) -> PlannedFile:
    """資料庫的一列 → 解析器的形狀。

    分類存在 `job_files` 上（規劃時寫回去的，`services/plan._store`）。沒有那一列時——重新入庫
    建的 Plan 沒有 Job（票 10）——當作 `other`：它只改得成「略過」，寧可少一個選項也不要讓一個
    不知道是什麼的檔案被當成一集。
    """
    return PlannedFile(
        rel_path=row.rel_path,
        kind=kind or FileKind.OTHER,
        action=row.action,
        season=row.season,
        episode_start=row.episode_start,
        episode_end=row.episode_end,
        tags=Tags.model_validate(row.tags_json or {}),
        confidence=row.confidence,
        target_path=row.target_path,
        reasons=reasons_of(row),
    )


def reasons_of(item: PlanItem) -> tuple[ItemReason, ...]:
    """`plan_items.reasons_json` → 型別化的理由。讀的地方（Plan 表格、audit 列）都走這裡。"""
    return tuple(ItemReason.model_validate(reason) for reason in item.reasons_json or ())


def dump_reasons(reasons: Sequence[ItemReason]) -> list[dict[str, object]]:
    return [reason.model_dump(mode="json") for reason in reasons]


def dump_tags(tags: Tags) -> dict[str, object] | None:
    """`plan_items.tags_json`。空的 tag 不佔一格 JSON：分類就決定得了處置的那些檔案本來就沒有
    版本可言。"""
    dumped: dict[str, object] = tags.model_dump(mode="json")
    return dumped if tags.render() else None


async def _kinds(session: AsyncSession, rows: Sequence[PlanItem]) -> dict[int | None, FileKind]:
    ids = [row.job_file_id for row in rows if row.job_file_id is not None]
    if not ids:
        return {}
    found = await session.execute(select(JobFile.id, JobFile.kind).where(JobFile.id.in_(ids)))
    return {file_id: kind for file_id, kind in found.tuples() if kind is not None}


async def _media(
    session: AsyncSession, plan: Plan, rows: Sequence[PlanItem]
) -> MediaSnapshot | None:
    """這份 Plan 屬於哪一部作品的快照。Job 帶著它；沒有 Job 時看列上的 `media_id`。"""
    media_id = None
    if plan.job_hash is not None:
        job = await session.get(Job, plan.job_hash)
        media_id = job.media_id if job is not None else None
    if media_id is None:
        media_id = next((row.media_id for row in rows if row.media_id is not None), None)
    if media_id is None:
        return None
    media = await session.get(Media, media_id)
    return media.stored_snapshot() if media is not None else None
