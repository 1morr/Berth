"""RSS Series 的第一批審核：確認整個 Series、改正一集並套用到整個 Series（brief §15，M3 票 13）。

季號與 offset 放在 RSS Series 上、規劃時讀（`plan.parse_context`）。大部分時候不必設——解析器的
季名、篇章名、cour 標記與絕對編號換算先處理——但 TMDB 把 split-cour 併成一季而字幕組每個 cour
從 01 重數時，第一集錯就整季一起錯。所以新 Series 的第一批進審核（`plan._audit`：確認之前 high 也
掛 audit），這裡是那一組的兩顆：

- **全部確認**（`confirm_series`）：畫面上那一組的每一列各按一次確認（`review.confirm_audits`，
  逐列語意與跳過規則相同），再把 Series 標成確認過。之後它的 medium 入庫不再進 audit 清單。
- **改正並套用到這個 RSS Series**（`correct_series`）：人改的那一集照常 rematch；由那一集檔名
  寫的集號算出 offset，寫回 Series，**重算它底下還沒確認的集數**——已入庫、還掛著 audit 的那幾集
  問規劃器現在該在哪一集（`plan.proposal`）再走 rematch 搬過去，停在 review 的那幾筆走重新規劃
  （`plan.replan_job`）。不另寫一條入庫的路：搬鏈接、字幕跟著走、帳本改寫、通知掃描都是 rematch 的。

**跟著重算的那幾集留在第一批裡**（仍掛 audit）：還沒有人看過它們，改正之後的那一組正是要人按
「全部確認」的東西；人親手改的那一集是人決定的，旗標清掉。已經確認過的集數不動——那是人說對的。

**搬家的順序**：offset 小於這一批的集數時，人要的那一格正被同一批的另一集佔著（01–12 放錯、
正解 07–18，第 1 集要去的 E07 上是還沒搬的第 7 集）。所以動手之前先問人那一格上是誰
（`rematch.destination`）：空的、或是同一批也要搬走的那一集才動手，否則當場拒絕、什麼都不動；
搬的時候被佔著的等別人先走再試（`_carry`）。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import (
    JobState,
    JobTrigger,
    PlanAction,
    PlanEngine,
    RematchRefusal,
    Role,
    why,
)
from berth.domain import PlanItem as PlannedFile
from berth.domain import ReasonCode as Code
from berth.models import Job, LedgerEntry, Plan, RssSeries
from berth.parser import written_episode
from berth.services.clients import ServiceClientFactory
from berth.services.commands import Effect, command
from berth.services.events import EventHub
from berth.services.jobs import JobRejectedError
from berth.services.plan import proposal, replan_job, series_of
from berth.services.rematch import (
    Assignment,
    RematchOutcome,
    RematchRejectedError,
    destination,
    rematch_file,
)
from berth.services.review import AuditsConfirmed, confirm_audits

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SeriesCorrected:
    """改正並套用之後：Series 現在的值，以及它底下還沒確認的集數怎麼了。"""

    #: 人改的那一集（`POST /files/rematch` 平常回的那一份）。擋路的那一集自己搬不走時（一圈換位、
    #: 或它的磁碟那一步失敗）是 `None`：Series 照樣寫回、其餘照樣搬，這一集數進 `left`。
    rematched: RematchOutcome | None
    season: int
    #: `None` 是不用偏移（人說的集號就是檔名寫的集號）。
    episode_offset: int | None
    #: 已入庫的集數裡跟著搬到新路徑的（不含人改的那一集）。
    moved: int
    #: 停在 review、照新的值重新規劃的 Job。
    replanned: int
    #: 照新的值落不到任何一集、或搬不過去的已入庫集數：留在原地、仍在第一批裡等人。
    left: int


@command(Effect.REVERSIBLE)
async def confirm_series(
    session: AsyncSession, series_id: int, ledger_ids: Sequence[int], *, actor: str
) -> AuditsConfirmed:
    """「全部確認」一個 RSS Series 的那一組：逐列確認送來的 id，再標 `confirmed = true`。

    範圍同票 05 的整段確認：送來的是畫面上列出的那幾個 id，按下之後才進來的不會被順手確認掉。
    Series 不在了（另一個分頁刪了）時照樣確認那幾列——按下去的人說的是「這幾集對」。

    沒有單一的反向命令：確認的每一列逐列撤銷得回來（`review.undo_audit`），而 `confirmed` 只決定
    之後的入庫要不要再問一次（M5 做登錄表時再決定要不要另立「取消確認」，同票 05 的 Comments）。
    """
    outcome = await confirm_audits(session, ledger_ids, actor=actor)
    if not outcome.confirmed:
        # 送來的每一列都已經被別處確認或撤銷：這一次沒有人看過任何一集，不算確認了這個 Series。
        return outcome
    series = await session.get(RssSeries, series_id)
    if series is not None and not series.confirmed:
        series.confirmed = True
        await session.commit()
        logger.info("rss series confirmed", extra={"series": series_id})
    return outcome


@command(Effect.REVERSIBLE)
async def correct_series(
    session: AsyncSession,
    factory: ServiceClientFactory,
    hub: EventHub,
    ledger_id: int,
    *,
    to: Assignment,
    actor: str,
) -> SeriesCorrected:
    """改正一集並「套用到這個 RSS Series」。

    沒有單一的反向命令：每一集的搬家逐列改得回來（rematch、audit 撤銷），但 Series 原本的值可能是
    「沒設」，這一支寫不回 `None`，連帶搬走的那幾集也不會自己回去——同一支帶回原本那一集不等於撤銷。

    **拒絕都在動任何東西之前**：不是 RSS Series 送的（`not_from_series`）、檔名讀不出集號
    （`no_episode_number`，算不出 offset）、人要的那一格被一個不會搬走的檔案佔著（`target_taken`），
    以及 rematch 自己的那幾種。之後 Series 寫回，人的那一集與其餘各集同一輪搬，各自成敗。
    """
    entry = await session.get(LedgerEntry, ledger_id)
    if entry is None:
        raise RematchRejectedError(RematchRefusal.LEDGER_MISSING, str(ledger_id))
    job = await session.get(Job, entry.job_hash) if entry.job_hash is not None else None
    series = await series_of(session, job) if job is not None else None
    if job is None or series is None:
        raise RematchRejectedError(RematchRefusal.NOT_FROM_SERIES, entry.source_rel_path)
    if to.action is not PlanAction.IMPORT:
        raise RematchRejectedError(RematchRefusal.ACTION_NOT_ALLOWED, entry.source_rel_path)
    if to.season is None or to.episode_start is None:
        raise RematchRejectedError(RematchRefusal.EPISODE_REQUIRED, entry.source_rel_path)
    written = written_episode(job.name, entry.source_rel_path)
    if written is None:
        raise RematchRejectedError(RematchRefusal.NO_EPISODE_NUMBER, entry.source_rel_path)

    series_id = series.id
    season, offset = to.season, (to.episode_start - written) or None
    # 先放進 session、還沒 commit：`plan.proposal` 經 `series_of` 讀到的是 identity map 裡這同一個
    # 物件，所以其餘各集照新的值算。人要的那一格被佔著而佔的人不會搬時，rollback 就回到原樣。
    series.season, series.episode_offset = season, offset
    followers, unplaceable = await _followers(session, series_id, season, offset, ledger_id)
    moves = [(ledger_id, to), *followers]
    target = await destination(session, ledger_id, to)
    holder = await session.scalar(
        select(LedgerEntry.id).where(LedgerEntry.target_path == target, LedgerEntry.id != ledger_id)
    )
    if holder is not None and holder not in {moved for moved, _ in moves}:
        await session.rollback()
        raise RematchRejectedError(RematchRefusal.TARGET_TAKEN, target)
    await session.commit()
    logger.info(
        "rss series corrected", extra={"series": series_id, "season": season, "offset": offset}
    )

    done = await _carry(session, factory, moves, actor=actor)
    replanned = await _replan_held(session, factory, hub, series_id)
    return SeriesCorrected(
        rematched=done.get(ledger_id),
        season=season,
        episode_offset=offset,
        moved=len(done) - (ledger_id in done),
        replanned=replanned,
        left=unplaceable + len(moves) - len(done),
    )


async def _followers(
    session: AsyncSession, series_id: int, season: int, offset: int | None, edited: int
) -> tuple[list[tuple[int, Assignment]], int]:
    """已入庫、還沒確認的其餘各集照新的值該去哪一集（`plan.proposal`）。回（要搬的, 落不到任何
    一集的幾個）——後者是新的值在 TMDB 上沒有那一集，留在原地給人。已經在那裡的不動。"""
    because = why(Code.SERIES_CORRECTED, season=season, offset=f"{offset or 0:+d}")
    entries = list(
        await session.scalars(
            select(LedgerEntry)
            .where(
                LedgerEntry.audit,
                LedgerEntry.action == PlanAction.IMPORT,
                LedgerEntry.job_hash.in_(_hashes_of(series_id)),
                LedgerEntry.id != edited,
            )
            .order_by(LedgerEntry.id)
        )
    )
    proposals: dict[str, dict[str, PlannedFile]] = {}
    moves: list[tuple[int, Assignment]] = []
    unplaceable = 0
    for entry in entries:
        assert entry.job_hash is not None  # 以 job_hash 查出來的
        if entry.job_hash not in proposals:
            job = await session.get(Job, entry.job_hash)
            proposals[entry.job_hash] = await proposal(session, job) if job is not None else {}
        planned = proposals[entry.job_hash].get(entry.source_rel_path)
        if planned is None or planned.action is not PlanAction.IMPORT:
            unplaceable += 1
            continue
        if (planned.season, planned.episode_start, planned.episode_end) != (
            entry.season,
            entry.episode_start,
            entry.episode_end,
        ):
            moves.append(
                (
                    entry.id,
                    Assignment(
                        action=PlanAction.IMPORT,
                        season=planned.season,
                        episode_start=planned.episode_start,
                        episode_end=planned.episode_end,
                        because=because,
                        audit=True,
                    ),
                )
            )
    return moves, unplaceable


async def _carry(
    session: AsyncSession,
    factory: ServiceClientFactory,
    moves: Sequence[tuple[int, Assignment]],
    *,
    actor: str,
) -> dict[int, RematchOutcome]:
    """逐一走 rematch，回搬成的那幾個（帳本 id → 結果）。

    **被佔著的等別人先走再試**（`target_taken`）：佔著的多半是同一批還沒搬的那一集。一圈沒有任何
    進展就停（剩下的是一圈換位，或佔著的那一個自己搬不走），留給人。其餘的拒絕只算這一集沒搬成。
    拒絕都在寫入之前丟出來，rollback 只是把 session 收乾淨——之後不再碰這裡之前讀進來的物件。
    """
    done: dict[int, RematchOutcome] = {}
    pending = list(moves)
    while pending:
        waiting: list[tuple[int, Assignment]] = []
        for ledger_id, to in pending:
            try:
                done[ledger_id] = await rematch_file(
                    session, factory, ledger_id=ledger_id, to=to, actor=actor
                )
            except RematchRejectedError as refused:
                await session.rollback()
                if refused.reason is RematchRefusal.TARGET_TAKEN:
                    waiting.append((ledger_id, to))
                    continue
                logger.warning(
                    "an episode did not follow its series",
                    extra={"ledger": ledger_id, "reason": refused.reason.value},
                )
        if len(waiting) == len(pending):
            break
        pending = waiting
    return done


async def _replan_held(
    session: AsyncSession, factory: ServiceClientFactory, hub: EventHub, series_id: int
) -> int:
    """停在 review 的那幾筆照新的值重新規劃（與 Job 頁的「重新規劃」同一支）。回重算了幾筆。

    **管理員逐列改過的那一份不動**（`engine = user`，`plan_review.edit_items`）：重新規劃是整份
    換掉，那是人的決定，不是「還沒確認的集數」。
    """
    held = list(
        await session.scalars(
            select(Job.hash)
            .join(Plan, Plan.job_hash == Job.hash)
            .where(
                Job.hash.in_(_hashes_of(series_id)),
                Job.state == JobState.REVIEW,
                Plan.engine != PlanEngine.USER,
            )
            .order_by(Job.added_at, Job.hash)
        )
    )
    replanned = 0
    for job_hash in held:
        try:
            await replan_job(session, factory, hub, job_hash, role=Role.ADMIN)
        except JobRejectedError as refused:
            # 按下去之後它被別處動過了（另一個分頁核准了、刪了）：那一筆已經不在等人。
            logger.info("a held job moved on", extra={"job": job_hash, "reason": str(refused)})
            continue
        replanned += 1
    return replanned


def _hashes_of(series_id: int) -> Select[tuple[str]]:
    """這個 RSS Series 送出的 Job（`trigger_ref` 是它的 id，`plan.series_of` 的反方向）。"""
    return select(Job.hash).where(Job.trigger == JobTrigger.RSS, Job.trigger_ref == str(series_id))
