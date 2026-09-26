"""RSS Series 的第一批：證據夠強時系統替人確認，不夠時說一句在問什麼（M4 票 11、brief §15）。

兩件事，都只看**還沒確認**的 Series：

- **系統確認**（`vouch` → `confirm_by_batch`）：規劃器算出一份自動入庫的計劃時問一次。**第一批是
  整個 Series 到確認為止送來的每一筆**，所以擔保要看整批：這一份每一列都照字面、剛播、播出日對得上
  （`parser.vouch_first_batch`），同一個 Series 的其他 Job 都已經落地（入庫中或已入庫；還在下載、
  停在 review、失敗的都算「整批還沒到齊」），而且它們還掛著 audit 的每一份也都擔保得了——才把 Series
  標成確認過、清掉那幾份的 audit，每一筆的時間線記一筆 `series_confirmed` 說出依據。有一列不符合，
  就照舊整批待確認。補舊集一次送十幾筆，前面幾筆先掛著 audit，最後一筆落地時整批一起看。規劃器在
  寫計劃之前問（擔保了的那一份不掛 audit，`plan._audit`），寫完之後才確認：時間線上先是計劃、再是
  它促成的確認。
- **在問什麼**（`asks`）：還在等人的第一批——掛著 audit 的已入庫正片，與停在 review 的計劃——蓋到
  哪幾集、季集是怎麼讀出來的（`FirstBatchBasis`）。審核頁那一組與作品頁的「第一批待確認」都說這一句。
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from sqlalchemy import and_, cast, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import Integer

from berth.domain import (
    EventType,
    FirstBatchBasis,
    ItemReason,
    JobState,
    JobTrigger,
    MediaSnapshot,
    PlanAction,
    PlanStatus,
    episode_label,
)
from berth.domain import PlanItem as PlannedFile
from berth.domain import ReasonCode as Code
from berth.models import Job, LedgerEntry, Plan, PlanItem, RssSeries
from berth.parser import vouch_first_batch
from berth.services.commands import Effect, command
from berth.services.jobs import actor_of, record_event
from berth.services.plan_view import planned, reasons_of

#: 同一個 Series 的其他 Job 落在這幾個狀態才算「到齊」：計劃自動入庫、寫進（或正在寫進）媒體庫。
_LANDED: frozenset[JobState] = frozenset({JobState.IMPORTING, JobState.IMPORTED})

#: 自動入庫的計劃：還在入庫（`auto`）或已經套用完（`applied`）。人核准過的那一份套用完也是
#: `applied`，但它的列不掛 audit（`plan_review`），`_waiting` 看旗標就分得開。
_AUTOMATIC: frozenset[PlanStatus] = frozenset({PlanStatus.AUTO, PlanStatus.APPLIED})

#: 季集是從 Series 上的值讀的。
_FROM_SERIES: frozenset[Code] = frozenset({Code.SEASON_FROM_JOB, Code.SERIES_CORRECTED})
#: 絕對編號換算。
_ABSOLUTE: frozenset[Code] = frozenset({Code.ABSOLUTE_GROUP, Code.ABSOLUTE_CUMULATIVE})
#: 依播出的輪次換算：虛擬季、cour 標記。第一輪以後的重數推測另外看（`_basis`）。
_RUNS: frozenset[Code] = frozenset({Code.AIR_DATE_RUN, Code.COUR_OFFSET})
#: 季號由篇章名或「最終季」讀出。
_ARC: frozenset[Code] = frozenset({Code.SEASON_FROM_ARC, Code.FINAL_SEASON})


@dataclass(frozen=True, slots=True)
class Span:
    """同一季裡連續的幾集。"""

    season: int
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class FirstBatchAsk:
    """一個還沒確認的 RSS Series 在問人什麼：蓋到的集數，以及它們的季集是怎麼讀出來的。"""

    spans: tuple[Span, ...]
    basis: FirstBatchBasis


@dataclass(frozen=True, slots=True)
class Vouched:
    """擔保了的整批：蓋到的集數（`S01E03`），與還掛著 audit、要一起清掉的其他 Job。"""

    episodes: tuple[str, ...]
    others: tuple[str, ...]


@command(Effect.READ)
async def vouch(
    session: AsyncSession,
    job: Job,
    series: RssSeries,
    items: Sequence[PlannedFile],
    media: MediaSnapshot | None,
) -> Vouched | None:
    """這一份加上同一個 Series 還在等人的每一份，證據都夠強就回整批；不夠、或 Series 已經確認過是
    `None`。只讀。"""
    if series.confirmed:
        return None
    mine = vouch_first_batch(
        job.name,
        items,
        media,
        job.published_at,
        season_hint=series.season,
        episode_offset=series.episode_offset,
    )
    if mine is None:
        return None
    spans = list(mine)
    others: list[str] = []
    siblings = await session.scalars(
        select(Job).where(
            Job.trigger == JobTrigger.RSS,
            Job.trigger_ref == str(series.id),
            Job.hash != job.hash,
            Job.state != JobState.REMOVED,
        )
    )
    for other in siblings:
        if other.state not in _LANDED:
            return None
        waiting = await _waiting(session, other)
        if waiting is None:
            continue
        plan, stored = waiting
        theirs = vouch_first_batch(
            other.name,
            stored,
            media,
            other.published_at,
            season_hint=plan.season_hint,
            episode_offset=plan.episode_offset,
        )
        if theirs is None:
            return None
        spans.extend(theirs)
        others.append(other.hash)
    return Vouched(
        episodes=tuple(episode_label(season, start, end) for season, start, end in sorted(spans)),
        others=tuple(others),
    )


async def _waiting(session: AsyncSession, job: Job) -> tuple[Plan, tuple[PlannedFile, ...]] | None:
    """這一筆自動入庫的計劃還有列掛著 audit 的話，回計劃與它的每一列；都看過了（人逐列確認過）是
    `None`——人看過的就不必再擔保。"""
    plan = await session.scalar(
        select(Plan).where(Plan.job_hash == job.hash, Plan.status.in_(_AUTOMATIC))
    )
    if plan is None:
        return None
    rows = list(await session.scalars(select(PlanItem).where(PlanItem.plan_id == plan.id)))
    if not any(row.audit for row in rows):
        return None
    # 分類不影響擔保（看的是處置、季集與理由），所以不必讀回 `job_files`。
    return plan, tuple(planned(row, None) for row in rows)


@command(Effect.REVERSIBLE)
async def confirm_by_batch(
    session: AsyncSession, job: Job, series: RssSeries, vouched: Vouched
) -> None:
    """把 Series 標成確認過，清掉整批其他 Job 掛著的 audit（Plan Item 與帳本兩邊，同人按「確認」），
    每一筆的時間線記下依據。不 commit：與計劃同一個交易。

    沒有反向命令：確認不動任何檔案，只決定之後的集數照一般信心走；確認錯了由播出日比對、片長驗證與
    回驗接住（同 `series_review.confirm_series`）。
    """
    series.confirmed = True
    if vouched.others:
        plans = select(Plan.id).where(Plan.job_hash.in_(vouched.others))
        await session.execute(
            update(PlanItem).where(PlanItem.plan_id.in_(plans)).values(audit=False)
        )
        await session.execute(
            update(LedgerEntry).where(LedgerEntry.job_hash.in_(vouched.others)).values(audit=False)
        )
    payload = {"series": series.id, "name": series.title_raw, "episodes": list(vouched.episodes)}
    for one in (job, *await _jobs(session, vouched.others)):
        await record_event(
            session, one, EventType.SERIES_CONFIRMED, actor=actor_of(None), payload=payload
        )


async def _jobs(session: AsyncSession, hashes: Sequence[str]) -> list[Job]:
    if not hashes:
        return []
    return list(await session.scalars(select(Job).where(Job.hash.in_(hashes))))


@command(Effect.READ)
async def asks(session: AsyncSession, series_ids: Iterable[int]) -> dict[int, FirstBatchAsk]:
    """每一個還沒確認、有集數在等人的 Series 在問什麼：掛著 audit 的已入庫正片，加上停在 review 的
    計劃裡有季集的列（連載中的 split-cour 被播出日比對整批擋在那裡，一集都沒入庫）。沒有在等的不在
    結果裡。"""
    wanted = sorted(set(series_ids))
    if not wanted:
        return {}
    series = {
        row.id: row
        for row in await session.scalars(
            select(RssSeries).where(RssSeries.id.in_(wanted), RssSeries.confirmed.is_(False))
        )
    }
    if not series:
        return {}
    sent = and_(Job.trigger == JobTrigger.RSS, cast(Job.trigger_ref, Integer) == RssSeries.id)
    audited = await session.execute(
        select(
            RssSeries.id,
            LedgerEntry.season,
            LedgerEntry.episode_start,
            LedgerEntry.episode_end,
            PlanItem,
        )
        .join(Job, sent)
        .join(LedgerEntry, LedgerEntry.job_hash == Job.hash)
        .outerjoin(PlanItem, PlanItem.id == LedgerEntry.plan_item_id)
        .where(RssSeries.id.in_(series), LedgerEntry.audit, LedgerEntry.action == PlanAction.IMPORT)
    )
    held = await session.execute(
        select(
            RssSeries.id, PlanItem.season, PlanItem.episode_start, PlanItem.episode_end, PlanItem
        )
        .join(Job, sent)
        .join(Plan, Plan.job_hash == Job.hash)
        .join(PlanItem, PlanItem.plan_id == Plan.id)
        .where(
            RssSeries.id.in_(series),
            Plan.status == PlanStatus.PENDING_REVIEW,
            Job.state == JobState.REVIEW,
            PlanItem.action.in_([PlanAction.IMPORT, PlanAction.REVIEW]),
        )
    )
    rows: dict[int, list[tuple[int | None, int | None, int | None, PlanItem | None]]] = defaultdict(
        list
    )
    for key, *row in (*audited.tuples(), *held.tuples()):
        rows[key].append((row[0], row[1], row[2], row[3]))
    return {
        key: ask for key, found in rows.items() if (ask := _ask(series[key], found)) is not None
    }


def _ask(
    series: RssSeries, rows: Sequence[tuple[int | None, int | None, int | None, PlanItem | None]]
) -> FirstBatchAsk | None:
    episodes = sorted(
        {
            (season, number)
            for season, start, end, _ in rows
            if season is not None and start is not None
            for number in range(start, (end or start) + 1)
        }
    )
    if not episodes:
        return None
    kinds = {
        basis_of(
            series.season,
            series.episode_offset,
            reasons_of(item) if item is not None else None,
        )
        for season, start, _, item in rows
        if season is not None and start is not None
    }
    return FirstBatchAsk(
        spans=spans_of(episodes),
        basis=kinds.pop() if len(kinds) == 1 else FirstBatchBasis.MIXED,
    )


def spans_of(episodes: Sequence[tuple[int, int]]) -> tuple[Span, ...]:
    """排好序的（季, 集）收成同一季裡連續的幾段。"""
    spans: list[Span] = []
    for season, number in episodes:
        last = spans[-1] if spans else None
        if last is not None and last.season == season and last.end + 1 == number:
            spans[-1] = Span(season, last.start, number)
        else:
            spans.append(Span(season, number, number))
    return tuple(spans)


def basis_of(
    season_hint: int | None,
    episode_offset: int | None,
    reasons: Sequence[ItemReason] | None,
) -> FirstBatchBasis:
    """這一集的季集是怎麼讀出來的，照它那一列 Plan Item 的理由。純函式。

    **先看 Series 的值**：設了季號或 offset 的話，解析器讀的就是它們。帳本那一列的 Plan Item 被重新
    規劃換掉（`plan_item_id` 被 `SET NULL`）時看不出來（`reasons` 是 `None`），算不只一種。
    """
    if season_hint is not None or episode_offset is not None:
        return FirstBatchBasis.SERIES
    if reasons is None:
        return FirstBatchBasis.MIXED
    codes = {reason.code for reason in reasons}
    if codes & _FROM_SERIES:
        return FirstBatchBasis.SERIES
    if codes & _ABSOLUTE:
        return FirstBatchBasis.ABSOLUTE
    if codes & _ARC:
        return FirstBatchBasis.ARC
    restarted = any(
        reason.code is Code.PUBLISHED_IN_RUN and reason.params.get("run") != 1 for reason in reasons
    )
    if restarted or codes & _RUNS:
        return FirstBatchBasis.RUNS
    return FirstBatchBasis.LITERAL
