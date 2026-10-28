"""Proposal：等人確認的命令（plan §2.6、§11.6〈分段〉第 3 段，M5 票 08）。

確認卡要能隔很久才按、在別的地方按、重啟之後按（brief §14〈對話裡的確認卡〉），所以它是
`proposals` 的一列（`models/proposal.py`），生命週期也獨立於提出它的那一輪對話（brief §20.24）。
不需要 AI：人也能提出。

**五個動作**：

1. **提出**（`propose`）：查登錄表、照命令的 `audience` 擋角色、每一列過輸入模型並跑 `validate`
   （乾跑）。有一列不通過就不建，丟 `InvalidProposalError` 說哪一列、什麼理由——prototype 實測的
   `route_required` 是按了確認才被擋，只好再出一張卡。
2. **決定**（`decide`）：只有提出者本人或管理員按得到，別人的是 `proposal_missing`（看不到就是
   沒有）。
   **先搶狀態**：compare-and-set 從讀到的那個等待狀態改成核准或拒絕，搶輸的是 `proposal_decided`，
   所以連按兩次只算一次。核准時可以帶逐列選擇。
   **Route 是唯一能在這裡給的參數**（票 23b，放寬票 08 的「存下後不可改」）：作品放得進的 Route
   不只一條時，提出時把那一列的可選清單存進預覽（`RouteAsk`），核准時勾著的每一列都要選一條、
   只收清單裡的（`route_required` / `route_not_offered`）。只有一條的列不收。
   **字幕組也是**（M5 票 26）：訂閱的字幕組可選的不只一個時，提出的一方把選項存進預覽
   （`SubgroupAsk`，模型給的只當預選），核准時勾著的每一列都要選、只收清單裡的
   （`subgroup_required` / `subgroup_not_offered`）。關鍵字訂閱的**第一輪**同理（`first_batch`：
   「下載這些並追之後的」或「只追之後的」，同 RSS 頁第一輪），不給就照存下的（預設前者）。
3. **執行**（`execute`）：同樣先搶（核准 → 執行中），再逐列經命令執行器：先重驗（乾跑）、再執行。
   **參數只用存下的那一份**（例外只有卡片上選的 Route 與字幕組），而且先重算雜湊比對卡片上那一份。
   每做完一列就把那一列的結果與它的改動一起 commit：做到一半的總覽卡，做過的那幾列有結果、
   不會再做一次。
   做的人是提出者（AI 提出的記 `ai:<user id>`），角色照他**現在**的角色重讀。
4. **脫離對話**（`detach`）：使用者沒按就繼續說話時，那段對話裡還在等的卡片標成脫離（票 13 叫它）。
5. **過期清掃**（`expire_due`）：`sweeper` 每分鐘醒來時叫它。決定時也會當場看期限。

**什麼時候執行**：**核准就當場執行**，不論卡片在不在對話裡（票 13 改了票 08 的「還在對話裡的只記
決定、由對話恢復時執行」）。對話恢復那一輪只把逐列結果交給模型（`services.agent`）：按下確認的那一刻
就做，AI 之後被關掉、恢復那一輪送不出去、或使用者直接關掉頁面，都不會留下一張「核准了卻沒做」的卡。
這段對話的卡片以 `tool_call_id` 找回來（`card_of_call`）；脫離過的記下 `detached_at`
（`detached_cards`），之後每一輪的 instructions 帶上它們的近況。

**給外面看的參數去掉 `Private` 的格子**（`ProposalView.arguments`，登錄表的 `public_arguments`）：
送單來源的下載連結帶著 Prowlarr 的 API key。執行讀的是存著的完整那一份。

**每一次狀態變更都推一則 `ProposalSignal`**（只有 id 與狀態，`services/events.py`）。

決定、執行、脫離、過期都標 `internal`：它們不進命令登錄表，所以 AI 的工具裡永遠不會有「核准」。
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic_core import to_jsonable_python
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import (
    WAITING_PROPOSALS,
    Actor,
    ActorKind,
    FeedKind,
    PrimeMode,
    ProposalRefusal,
    ProposalRowOutcome,
    ProposalStatus,
    Role,
)
from berth.models import Proposal, User
from berth.services.commands import Effect, Flag, command
from berth.services.events import EventHub, ProposalSignal
from berth.services.executor import CommandRefusal, CommandRefusedError, Executor
from berth.services.media import route_offer
from berth.services.registry import CommandSpec, Verdict, commands, dry_run, public_arguments
from berth.services.rss import SubscriptionRef

logger = logging.getLogger(__name__)

#: 沒人按多久之後過期。確認卡要能隔很久才按（隔天早上），但不該永遠掛著：參數裡的作品、Route、
#: 來源都會變，太舊的卡片重驗多半也過不了。
PROPOSAL_TTL = timedelta(hours=24)

#: 雜湊對不上時那幾列的 `reason`：存下的參數在卡片出現之後被改過，一列都不做。
ARGUMENTS_CHANGED = "arguments_changed"


class ProposalRejectedError(Exception):
    def __init__(self, reason: ProposalRefusal, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else str(reason))
        self.reason = reason
        self.detail = detail


class InvalidProposalError(CommandRefusedError):
    """提出時有一列過不了命令的驗證：哪一列（0 起算）、命令自己的理由。"""

    def __init__(self, command: str, row: int, reason: StrEnum, detail: str = "") -> None:
        super().__init__(command, reason, detail)
        self.row = row


@dataclass(frozen=True, slots=True)
class RouteOption:
    id: int
    #: 提出那一刻的名字：卡片照它畫，之後改名不影響這張卡。
    name: str


@dataclass(frozen=True, slots=True)
class RouteAsk:
    """一列要人在卡片上選的 Route（票 23b）：這部作品放得進的不只一條（`media.route_choices`）。

    模型給的那一條不算數（票 23 實測它不問就挑），**預選的是這部作品上次送單用的那一條**
    （`default_route_id`，在清單裡才算）；沒用過就不預選。
    """

    options: tuple[RouteOption, ...]
    preselected: int | None


@dataclass(frozen=True, slots=True)
class SubgroupOption:
    """訂閱可選的一個字幕組（M5 票 26）：卡片照它畫，選了它就用 `arguments` 蓋過存下的參數。"""

    #: 這一個的身分（決定的 body 送它）：Mikan 是字幕組 id 的字串，關鍵字訂閱是字幕組名。
    key: str
    name: str
    releases: int
    updated: date | None
    #: 最新一筆的發佈名（看得出語言與解析度，同 Media 頁的字幕組那一顆鍵）。
    latest: str
    #: 關鍵字訂閱的第一批：按下確認就送出的發佈名，新的在前。Mikan 是空的（整季，筆數是
    #: `releases`）。
    titles: tuple[str, ...]
    #: 選了這一個時蓋過存下參數的那幾格（Mikan：`subgroup_id` 與 `subgroup_name`；
    #: 關鍵字：`subgroup`）。
    # `Any`：格子的型別隨命令（字幕組 id 是 int、名字是 str）。
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SubgroupAsk:
    """一列訂閱的字幕組（M5 票 26）。`preselected` 是模型給的那一個（在選項裡才算）。

    `required`：要人選——選項不只一個，或模型給的不在選項裡。只有一個、而且就是模型給的那一個時
    只列出來（關鍵字訂閱的第一批照樣列），不必選。
    """

    options: tuple[SubgroupOption, ...]
    preselected: str | None
    required: bool


@dataclass(frozen=True, slots=True)
class ProposalPreview:
    """提出那一刻伺服器算的：命令的效果與旗標（卡片照它說「不可逆」「會送出 torrent」），與逐列
    有沒有乾跑過（命令沒有驗證函式的是 `False`：預覽只看得到參數）。"""

    effect: Effect
    flags: tuple[Flag, ...]
    checked: tuple[bool, ...]
    #: 逐列：出自外部內容的自由文字格子（M5 票 14，`agent_origins`）。卡片只在這幾格標警示；
    #: 人提出的、或 AI 沒讀過外部內容的，每一列都是空的。
    external_fields: tuple[tuple[str, ...], ...] = ()
    #: 這一次呼叫裡超過一張卡上限、沒放上這一張的列數（送單的數量閘，M5 票 14）。
    held_back: int = 0
    #: 逐列：按下去會送出幾個 torrent（送單一列一個，訂閱 Mikan 是單一 feed 上整季的筆數）；
    #: `None` 是提出時不知道，要送出時才知道。不送 torrent 的命令是空的。
    torrents: tuple[int | None, ...] = ()
    #: 逐列：要人選 Route 的列是 `RouteAsk`，其餘（只有一條、命令沒有 Route）是 `None`。命令的輸入
    #: 沒有 `media_id` 與 `route_id` 的、票 23b 之前存的卡是空的。
    routes: tuple[RouteAsk | None, ...] = ()
    #: 逐列：訂閱的字幕組選項（`SubgroupAsk`），其餘是 `None`。不是訂閱的命令、票 26 之前存的卡
    #: 是空的。
    subgroups: tuple[SubgroupAsk | None, ...] = ()
    #: 逐列：這部作品提出那一刻已經有的訂閱（M5 票 26）。卡片說出來，由人決定要不要再訂一份。
    #: 不是訂閱的命令、票 26 之前存的卡是空的。
    existing: tuple[tuple[SubscriptionRef, ...], ...] = ()
    #: 逐列：卡片上能不能選第一輪（命令輸入有 `first_batch` 的：關鍵字訂閱，M5 票 26）。
    #: 都不能是空的。
    first_batch: tuple[bool, ...] = ()


@dataclass(frozen=True, slots=True)
class RowResult:
    """一列的結果。`reason` 是拒絕理由的值或例外的型別名，`detail` 是原文；`result` 是命令回傳值的
    JSON 形狀（做成的那一列才有）。"""

    outcome: ProposalRowOutcome
    reason: str = ""
    detail: str = ""
    result: Any = None


@dataclass(frozen=True, slots=True)
class ProposalView:
    id: int
    command: str
    # `Any`：每一格的型別隨命令，形狀由登錄表的輸入模型決定（已過驗證、`mode="json"`）。
    arguments: list[dict[str, Any]]
    arguments_hash: str
    preview: ProposalPreview
    user_id: int
    proposer: ActorKind
    conversation_id: str | None
    #: AI 提出的那一次 tool call；人提出的是 `None`。
    tool_call_id: str | None
    status: ProposalStatus
    created_at: datetime
    expires_at: datetime
    decided_by: int | None
    decided_at: datetime | None
    selection: list[int] | None
    results: list[RowResult] | None
    #: 脫離提出它的那一輪的時刻；沒脫離過是 `None`。
    detached_at: datetime | None = None
    #: 核准時逐列在卡片上選的 Route（`preview.routes` 有 `RouteAsk` 的列才有值）；沒選過是 `None`。
    routes: list[int | None] | None = None
    #: 核准時逐列在卡片上選的字幕組（選項的 `key`）；沒選過是 `None`。
    subgroups: list[str | None] | None = None
    #: 核准時逐列選的第一輪；沒選過是 `None`。
    first_batch: list[PrimeMode | None] | None = None


def arguments_hash(name: str, arguments: Sequence[Mapping[str, object]]) -> str:
    blob = json.dumps(
        {"command": name, "arguments": list(arguments)},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode()).hexdigest()


# 寫一列等人確認的卡片；拒絕或過期就是它的反向，沒有單一反向命令。
@command(Effect.REVERSIBLE, flags={Flag.INTERNAL})
async def propose(
    session: AsyncSession,
    hub: EventHub,
    name: str,
    rows: Sequence[Mapping[str, object]],
    *,
    actor: Actor,
    conversation_id: str | None = None,
    tool_call_id: str | None = None,
    external_fields: Sequence[Sequence[str]] = (),
    held_back: int = 0,
    torrents: Sequence[int | None] = (),
    subgroups: Sequence[SubgroupAsk | None] = (),
    existing: Sequence[Sequence[SubscriptionRef]] = (),
    now: datetime | None = None,
) -> ProposalView:
    """建一張卡片（模組 docstring 第 1 點）。輸入格式不對是 pydantic 的 `ValidationError`。

    AI 提出的帶 `tool_call_id`（提出它的那一次工具呼叫），恢復那一輪時靠它找回卡片；
    `external_fields`、`held_back`、`torrents`、`subgroups` 與 `existing` 照實記進預覽
    （`ProposalPreview`），由提出它的那一方算（`services.agent`：字幕組要讀番組頁或搜尋）。
    """
    if external_fields and len(external_fields) != len(rows):
        raise ValueError("external_fields names the fields of every row")
    if actor.user_id is None or actor.kind is ActorKind.SYSTEM:
        raise ValueError("a proposal is made by a person, or by the AI for a person")
    if not rows:
        raise ValueError("a proposal has at least one row")
    spec = commands().get(name)
    if spec is None:
        raise CommandRefusedError(name, CommandRefusal.UNKNOWN_COMMAND)
    if spec.audience is Role.ADMIN and actor.role is not Role.ADMIN:
        raise CommandRefusedError(name, CommandRefusal.ADMIN_ONLY)
    arguments = [spec.input.model_validate(row).model_dump(mode="json") for row in rows]
    checked: list[bool] = []
    for index, row in enumerate(arguments):
        verdict = await dry_run(spec, session, row)
        if verdict.refusal is not None:
            raise InvalidProposalError(name, index, verdict.refusal, verdict.detail)
        checked.append(verdict.checked)
    moment = now or datetime.now(UTC)
    preview = ProposalPreview(
        effect=spec.effect,
        flags=tuple(sorted(spec.flags)),
        checked=tuple(checked),
        external_fields=tuple(tuple(fields) for fields in external_fields)
        or tuple(() for _ in rows),
        held_back=held_back,
        torrents=tuple(torrents),
        routes=await _route_asks(session, spec, arguments),
        subgroups=tuple(subgroups),
        existing=tuple(tuple(found) for found in existing),
        first_batch=(
            tuple(True for _ in arguments) if "first_batch" in spec.input.model_fields else ()
        ),
    )
    proposal = Proposal(
        command=name,
        arguments_json=arguments,
        arguments_hash=arguments_hash(name, arguments),
        preview_json=to_jsonable_python(asdict(preview)),
        user_id=actor.user_id,
        proposer=actor.kind,
        conversation_id=conversation_id,
        tool_call_id=tool_call_id,
        status=ProposalStatus.PENDING,
        created_at=moment,
        expires_at=moment + PROPOSAL_TTL,
    )
    session.add(proposal)
    await session.commit()
    hub.publish(ProposalSignal(id=proposal.id, status=proposal.status))
    return _view(proposal)


# 按下核准或拒絕。核准會執行命令，而命令可能不可逆。
@command(Effect.IRREVERSIBLE, flags={Flag.INTERNAL})
async def decide(
    session: AsyncSession,
    executor: Executor,
    proposal_id: int,
    *,
    approve: bool,
    selection: Sequence[int] | None = None,
    routes: Sequence[int | None] | None = None,
    subgroups: Sequence[str | None] | None = None,
    first_batch: Sequence[PrimeMode | None] | None = None,
    user_id: int,
    role: Role,
    now: datetime | None = None,
) -> ProposalView:
    """人按下卡片（模組 docstring 第 2 點）。只收人：AI 沒有這條路。

    `routes` 與 `subgroups` 逐列對齊，只有存了選項的列（`preview.routes`、`preview.subgroups`）
    能給值；拒絕時不看它們。
    """
    moment = now or datetime.now(UTC)
    proposal = await session.get(Proposal, proposal_id, populate_existing=True)
    if proposal is None or (role is not Role.ADMIN and proposal.user_id != user_id):
        raise ProposalRejectedError(ProposalRefusal.PROPOSAL_MISSING, str(proposal_id))
    seen = proposal.status
    if seen not in WAITING_PROPOSALS:
        raise ProposalRejectedError(ProposalRefusal.PROPOSAL_DECIDED, seen.value)
    if moment >= proposal.expires_at:
        if await _move(session, proposal_id, seen, ProposalStatus.EXPIRED):
            await session.commit()
            executor.hub.publish(ProposalSignal(id=proposal_id, status=ProposalStatus.EXPIRED))
            raise ProposalRejectedError(ProposalRefusal.PROPOSAL_EXPIRED)
        raise await _decided(session, proposal_id)
    rows = len(proposal.arguments_json)
    chosen = _selection(selection, rows) if approve else None
    preview = _view(proposal).preview
    picked = _routes(routes, preview.routes, rows, chosen) if approve else None
    groups = _subgroups(subgroups, preview.subgroups, rows, chosen) if approve else None
    rounds = _first_batches(first_batch, preview.first_batch, rows, chosen) if approve else None
    status = ProposalStatus.APPROVED if approve else ProposalStatus.REJECTED
    moved = await _move(
        session,
        proposal_id,
        seen,
        status,
        decided_by=user_id,
        decided_at=moment,
        selection_json=chosen,
        routes_json=picked,
        subgroups_json=groups,
        first_batch_json=rounds,
    )
    if not moved:
        raise await _decided(session, proposal_id)
    await session.commit()
    executor.hub.publish(ProposalSignal(id=proposal_id, status=status))
    if approve:
        try:
            return await execute(session, executor, proposal_id)
        except ProposalRejectedError:
            # 核准已經記下了；別處（另一個分頁的同一下）先開始執行，按的人看到的是它現在的樣子，
            # 不是 409。
            pass
    return await _read(session, proposal_id)


# 照存下的參數執行核准過的卡片；命令可能不可逆。
@command(Effect.IRREVERSIBLE, flags={Flag.INTERNAL})
async def execute(session: AsyncSession, executor: Executor, proposal_id: int) -> ProposalView:
    """執行一張核准過的卡片（模組 docstring 第 3 點）。不收參數：用的是存下的那一份。"""
    if not await _move(session, proposal_id, ProposalStatus.APPROVED, ProposalStatus.EXECUTING):
        raise await _decided(session, proposal_id)
    await session.commit()
    executor.hub.publish(ProposalSignal(id=proposal_id, status=ProposalStatus.EXECUTING))
    proposal = await _row(session, proposal_id)
    name = proposal.command
    rows = proposal.arguments_json
    selection = proposal.selection_json
    picked = proposal.routes_json or [None] * len(rows)
    asks = _view(proposal).preview.subgroups
    groups = proposal.subgroups_json or [None] * len(rows)
    rounds = proposal.first_batch_json or [None] * len(rows)
    intact = arguments_hash(name, rows) == proposal.arguments_hash
    actor = await _actor(session, proposal)
    results: list[RowResult] = []
    for index, row in enumerate(rows):
        if selection is not None and index not in selection:
            outcome = RowResult(ProposalRowOutcome.SKIPPED)
        elif not intact:
            outcome = RowResult(ProposalRowOutcome.FAILED, reason=ARGUMENTS_CHANGED)
        else:
            route = picked[index]
            given = row if route is None else {**row, "route_id": route}
            ask = asks[index] if index < len(asks) else None
            if ask is not None:
                given = {**given, **_option(ask, groups[index]).arguments}
            if rounds[index] is not None:
                given = {**given, "first_batch": rounds[index]}
            outcome = await _run_row(session, executor, name, given, actor)
        results.append(outcome)
        # 這一列的結果與它的改動同一筆 commit。
        await session.execute(
            update(Proposal)
            .where(Proposal.id == proposal_id)
            .values(results_json=[_dump(result) for result in results])
        )
        await session.commit()
    status = _settled(results)
    await _move(session, proposal_id, ProposalStatus.EXECUTING, status)
    await session.commit()
    executor.hub.publish(ProposalSignal(id=proposal_id, status=status))
    return await _read(session, proposal_id)


# 對話往下走了，還在等的卡片脫離那一輪；之後照樣按得下去。
@command(Effect.REVERSIBLE, flags={Flag.INTERNAL})
async def detach(
    session: AsyncSession, hub: EventHub, conversation_id: str, *, now: datetime | None = None
) -> list[int]:
    """這段對話裡還在等的卡片標成脫離（模組 docstring 第 4 點），記下時刻，回傳是哪幾張。"""
    detached = list(
        await session.scalars(
            update(Proposal)
            .where(
                Proposal.conversation_id == conversation_id,
                Proposal.status == ProposalStatus.PENDING,
            )
            .values(status=ProposalStatus.DETACHED, detached_at=now or datetime.now(UTC))
            .returning(Proposal.id)
            .execution_options(synchronize_session=False)
        )
    )
    await session.commit()
    for proposal_id in detached:
        hub.publish(ProposalSignal(id=proposal_id, status=ProposalStatus.DETACHED))
    return detached


# 背景迴圈（`sweeper`）的入口；過期的卡片不會回來。
@command(Effect.IRREVERSIBLE, flags={Flag.INTERNAL})
async def expire_due(
    session: AsyncSession, hub: EventHub, *, now: datetime | None = None
) -> list[int]:
    """還在等、過了期限的卡片標成過期，回傳是哪幾張。核准過還沒執行的不動：那是對話的事。"""
    moment = now or datetime.now(UTC)
    expired = list(
        await session.scalars(
            update(Proposal)
            .where(Proposal.status.in_(WAITING_PROPOSALS), Proposal.expires_at <= moment)
            .values(status=ProposalStatus.EXPIRED)
            .returning(Proposal.id)
            .execution_options(synchronize_session=False)
        )
    )
    await session.commit()
    for proposal_id in expired:
        hub.publish(ProposalSignal(id=proposal_id, status=ProposalStatus.EXPIRED))
    return expired


@command(
    Effect.READ,
    about=(
        "List the confirmation cards (proposals) the user can decide, oldest first, optionally "
        "only those of one conversation, with their status and per-row results."
    ),
    audience=Role.USER,
)
async def list_proposals(
    session: AsyncSession,
    conversation_id: str | None = None,
    *,
    user_id: int | None,
    role: Role,
) -> list[ProposalView]:
    """按的人決定得了的卡片：管理員是每一張，其他人是自己的。舊的在前（對話裡的順序）。"""
    query = select(Proposal).order_by(Proposal.id)
    if role is not Role.ADMIN:
        query = query.where(Proposal.user_id == user_id)
    if conversation_id is not None:
        query = query.where(Proposal.conversation_id == conversation_id)
    found = await session.scalars(query.execution_options(populate_existing=True))
    return [_view(proposal) for proposal in found]


# 對話恢復那一輪找卡片：只讀。
@command(Effect.READ, flags={Flag.INTERNAL})
async def card_of_call(
    session: AsyncSession, conversation_id: str, tool_call_id: str
) -> ProposalView | None:
    """這段對話裡這一次 tool call 提出的卡片；沒有（沒出卡、或卡片跟著人一起刪了）是 `None`。

    **取最新的一張**：`tool_call_id` 不保證唯一（有的 OpenAI 相容閘道每一輪都從 `call_0` 編起），
    而要找的永遠是最後一則模型回應裡的那一次。
    """
    found = await session.scalar(
        select(Proposal)
        .where(Proposal.conversation_id == conversation_id, Proposal.tool_call_id == tool_call_id)
        .order_by(Proposal.id.desc())
        .limit(1)
        .execution_options(populate_existing=True)
    )
    return None if found is None else _view(found)


# 每一輪開頭讀：脫離過的卡片現在怎麼了。只讀。
@command(Effect.READ, flags={Flag.INTERNAL})
async def detached_cards(
    session: AsyncSession, conversation_id: str, *, limit: int = 5
) -> list[ProposalView]:
    """這段對話裡脫離過那一輪的卡片，最近的 `limit` 張，舊的在前。"""
    found = await session.scalars(
        select(Proposal)
        .where(Proposal.conversation_id == conversation_id, Proposal.detached_at.is_not(None))
        .order_by(Proposal.id.desc())
        .limit(limit)
        .execution_options(populate_existing=True)
    )
    return [_view(proposal) for proposal in reversed(list(found))]


async def _run_row(
    session: AsyncSession,
    executor: Executor,
    name: str,
    row: Mapping[str, object],
    actor: Actor,
) -> RowResult:
    """一列：重驗、經執行器執行。失敗的那一列 rollback 它自己沒 commit 的改動，不影響別列。"""
    try:
        spec = commands().get(name)
        verdict = await dry_run(spec, session, row) if spec is not None else Verdict(checked=False)
        if verdict.refusal is not None:
            return RowResult(
                ProposalRowOutcome.REFUSED, reason=verdict.refusal.value, detail=verdict.detail
            )
        result = await executor.execute(session, name, row, actor)
    except CommandRefusedError as refused:
        await session.rollback()
        return RowResult(
            ProposalRowOutcome.REFUSED, reason=refused.reason.value, detail=refused.detail
        )
    except Exception as exc:  # 一列壞了不擋別列；原文留在結果裡，堆疊進 log
        logger.exception("proposal row failed", extra={"command": name})
        await session.rollback()
        return RowResult(ProposalRowOutcome.FAILED, reason=type(exc).__name__, detail=str(exc))
    return RowResult(ProposalRowOutcome.DONE, result=to_jsonable_python(result, fallback=str))


def _settled(results: Sequence[RowResult]) -> ProposalStatus:
    chosen = [result for result in results if result.outcome is not ProposalRowOutcome.SKIPPED]
    done = sum(result.outcome is ProposalRowOutcome.DONE for result in chosen)
    if done == len(chosen):
        return ProposalStatus.EXECUTED
    return ProposalStatus.FAILED if done == 0 else ProposalStatus.PARTIAL


def sends_into_a_route(spec: CommandSpec) -> bool:
    """命令把一部作品送進一條 Route（輸入有 `media_id` 與 `route_id`：送單、訂閱 Mikan、
    關鍵字訂閱）。這幾支在作品放得進的 Route 不只一條時要人選（票 23b）。"""
    return {"media_id", "route_id"} <= set(spec.input.model_fields)


async def _route_asks(
    session: AsyncSession, spec: CommandSpec, arguments: Sequence[Mapping[str, object]]
) -> tuple[RouteAsk | None, ...]:
    """逐列：作品放得進的 Route 不只一條就要人選（票 23b，`sends_into_a_route` 的命令才看）。"""
    if not sends_into_a_route(spec):
        return ()
    asks: list[RouteAsk | None] = []
    for row in arguments:
        offer = await route_offer(session, str(row["media_id"]))
        asks.append(
            RouteAsk(
                options=tuple(RouteOption(id=c.id, name=c.name) for c in offer.choices),
                preselected=offer.last_used,
            )
            if len(offer.choices) > 1
            else None
        )
    return tuple(asks)


def _routes(
    routes: Sequence[int | None] | None,
    asks: Sequence[RouteAsk | None],
    rows: int,
    chosen: Sequence[int] | None,
) -> list[int | None] | None:
    """核准時的逐列 Route（模組 docstring 第 2 點）。勾著而沒選的是 `route_required`（`detail` 是
    列號）；不在清單裡、那一列沒得選、或長度對不上的是 `route_not_offered`。"""
    picks: list[int | None] = list(routes) if routes is not None else [None] * rows
    if len(picks) != rows:
        raise ProposalRejectedError(ProposalRefusal.ROUTE_NOT_OFFERED, json.dumps(picks))
    for index, pick in enumerate(picks):
        ask = asks[index] if index < len(asks) else None
        if ask is None:
            if pick is not None:
                raise ProposalRejectedError(ProposalRefusal.ROUTE_NOT_OFFERED, f"{index}:{pick}")
        elif chosen is not None and index not in chosen:
            # 沒勾的列不做，帶來的 Route 不記（清單外的照樣拒絕，上一個分支之外）。
            if pick is not None and pick not in {option.id for option in ask.options}:
                raise ProposalRejectedError(ProposalRefusal.ROUTE_NOT_OFFERED, f"{index}:{pick}")
            picks[index] = None
        elif pick is None:
            raise ProposalRejectedError(ProposalRefusal.ROUTE_REQUIRED, str(index))
        elif pick not in {option.id for option in ask.options}:
            raise ProposalRejectedError(ProposalRefusal.ROUTE_NOT_OFFERED, f"{index}:{pick}")
    return picks if any(pick is not None for pick in picks) else None


def _subgroups(
    subgroups: Sequence[str | None] | None,
    asks: Sequence[SubgroupAsk | None],
    rows: int,
    chosen: Sequence[int] | None,
) -> list[str | None] | None:
    """核准時的逐列字幕組（模組 docstring 第 2 點，同 `_routes`）。勾著而要選卻沒選的是
    `subgroup_required`（`detail` 是列號）；不在清單裡、那一列沒得選、或長度對不上的是
    `subgroup_not_offered`。不必選的列（`required` 是假）沒給就用預選的那一個。"""
    picks: list[str | None] = list(subgroups) if subgroups is not None else [None] * rows
    if len(picks) != rows:
        raise ProposalRejectedError(ProposalRefusal.SUBGROUP_NOT_OFFERED, json.dumps(picks))
    for index, pick in enumerate(picks):
        ask = asks[index] if index < len(asks) else None
        offered = {option.key for option in ask.options} if ask is not None else set()
        if pick is not None and pick not in offered:
            raise ProposalRejectedError(ProposalRefusal.SUBGROUP_NOT_OFFERED, f"{index}:{pick}")
        if chosen is not None and index not in chosen:
            # 沒勾的列不做，帶來的字幕組不記。
            picks[index] = None
        elif ask is not None and ask.required and pick is None:
            raise ProposalRejectedError(ProposalRefusal.SUBGROUP_REQUIRED, str(index))
    return picks if any(pick is not None for pick in picks) else None


def _first_batches(
    picks: Sequence[PrimeMode | None] | None,
    offers: Sequence[bool],
    rows: int,
    chosen: Sequence[int] | None,
) -> list[str | None] | None:
    """核准時的逐列第一輪（模組 docstring 第 2 點）。沒得選的列帶了值、或長度對不上是
    `first_batch_not_offered`；沒勾的列不記；沒給的照存下的。"""
    if picks is None:
        return None
    given = list(picks)
    if len(given) != rows:
        raise ProposalRejectedError(ProposalRefusal.FIRST_BATCH_NOT_OFFERED, json.dumps(given))
    kept: list[str | None] = []
    for index, pick in enumerate(given):
        offered = index < len(offers) and offers[index]
        if pick is not None and not offered:
            raise ProposalRejectedError(ProposalRefusal.FIRST_BATCH_NOT_OFFERED, str(index))
        ticked = chosen is None or index in chosen
        kept.append(PrimeMode(pick).value if pick is not None and ticked else None)
    return kept if any(pick is not None for pick in kept) else None


def _option(ask: SubgroupAsk, pick: str | None) -> SubgroupOption:
    """執行這一列用的字幕組：人選的那一個，沒選（不必選的列）是預選的那一個。`decide` 擋過了，
    所以一定找得到。"""
    key = pick if pick is not None else ask.preselected
    return next(option for option in ask.options if option.key == key)


def _selection(selection: Sequence[int] | None, rows: int) -> list[int] | None:
    if selection is None:
        return None
    chosen = list(selection)
    if not chosen or len(set(chosen)) != len(chosen) or not all(0 <= i < rows for i in chosen):
        raise ProposalRejectedError(ProposalRefusal.SELECTION_INVALID, json.dumps(chosen))
    return sorted(chosen)


async def _move(
    session: AsyncSession,
    proposal_id: int,
    expected: ProposalStatus,
    status: ProposalStatus,
    **values: object,
) -> bool:
    """compare-and-set：還是 `expected` 才改成 `status`。影響 0 列就是有人先動了它。"""
    result = await session.execute(
        update(Proposal)
        .where(Proposal.id == proposal_id, Proposal.status == expected)
        .values(status=status, **values)
        .execution_options(synchronize_session=False)
    )
    # `CursorResult` 才有 `rowcount`；`execute(update(...))` 的靜態型別是 `Result`。
    return getattr(result, "rowcount", 0) == 1


async def _decided(session: AsyncSession, proposal_id: int) -> ProposalRejectedError:
    """搶輸了：它現在在哪個狀態（不見了就是沒有）。"""
    found = await session.get(Proposal, proposal_id, populate_existing=True)
    if found is None:
        return ProposalRejectedError(ProposalRefusal.PROPOSAL_MISSING, str(proposal_id))
    return ProposalRejectedError(ProposalRefusal.PROPOSAL_DECIDED, found.status.value)


async def _row(session: AsyncSession, proposal_id: int) -> Proposal:
    found = await session.get(Proposal, proposal_id, populate_existing=True)
    if found is None:
        raise ProposalRejectedError(ProposalRefusal.PROPOSAL_MISSING, str(proposal_id))
    return found


async def _read(session: AsyncSession, proposal_id: int) -> ProposalView:
    return _view(await _row(session, proposal_id))


async def _actor(session: AsyncSession, proposal: Proposal) -> Actor:
    """做的人是提出者，角色照他現在的（外鍵是 `CASCADE`，所以他一定還在）。"""
    user = await session.get(User, proposal.user_id, populate_existing=True)
    assert user is not None
    if proposal.proposer is ActorKind.AI:
        return Actor.ai(user.id, user.role)
    return Actor.person(user.id, user.role)


# `Any`：`result` 是命令回傳值的 JSON 形狀，隨命令。
def _dump(result: RowResult) -> dict[str, Any]:
    return {
        "outcome": result.outcome.value,
        "reason": result.reason,
        "detail": result.detail,
        "result": result.result,
    }


def _view(proposal: Proposal) -> ProposalView:
    preview = proposal.preview_json
    spec = commands().get(proposal.command)
    return ProposalView(
        id=proposal.id,
        command=proposal.command,
        # 給瀏覽器與模型的那一份：標了 `Private` 的格子（下載連結）不出伺服器。
        arguments=(
            [public_arguments(spec, row) for row in proposal.arguments_json]
            if spec is not None
            else proposal.arguments_json
        ),
        arguments_hash=proposal.arguments_hash,
        preview=ProposalPreview(
            effect=Effect(preview["effect"]),
            flags=tuple(Flag(flag) for flag in preview["flags"]),
            checked=tuple(preview["checked"]),
            # 票 14 之前存的卡沒有這兩格。
            external_fields=tuple(
                tuple(fields)
                for fields in preview.get("external_fields") or [[] for _ in preview["checked"]]
            ),
            held_back=preview.get("held_back", 0),
            torrents=tuple(preview.get("torrents") or ()),
            # 票 23b 之前存的卡沒有這一格。
            routes=tuple(
                None
                if ask is None
                else RouteAsk(
                    options=tuple(RouteOption(**option) for option in ask["options"]),
                    preselected=ask["preselected"],
                )
                for ask in preview.get("routes") or ()
            ),
            # 票 26 之前存的卡沒有這三格。
            subgroups=tuple(_subgroup_ask(ask) for ask in preview.get("subgroups") or ()),
            existing=tuple(
                tuple(
                    SubscriptionRef(
                        feed_id=ref["feed_id"],
                        name=ref["name"],
                        kind=FeedKind(ref["kind"]),
                        subgroup=ref["subgroup"],
                    )
                    for ref in refs
                )
                for refs in preview.get("existing") or ()
            ),
            first_batch=tuple(preview.get("first_batch") or ()),
        ),
        user_id=proposal.user_id,
        proposer=proposal.proposer,
        conversation_id=proposal.conversation_id,
        tool_call_id=proposal.tool_call_id,
        status=proposal.status,
        created_at=proposal.created_at,
        expires_at=proposal.expires_at,
        decided_by=proposal.decided_by,
        decided_at=proposal.decided_at,
        selection=proposal.selection_json,
        results=(
            None
            if proposal.results_json is None
            else [
                RowResult(
                    outcome=ProposalRowOutcome(result["outcome"]),
                    reason=result["reason"],
                    detail=result["detail"],
                    result=result["result"],
                )
                for result in proposal.results_json
            ]
        ),
        detached_at=proposal.detached_at,
        routes=proposal.routes_json,
        subgroups=proposal.subgroups_json,
        first_batch=(
            None
            if proposal.first_batch_json is None
            else [None if pick is None else PrimeMode(pick) for pick in proposal.first_batch_json]
        ),
    )


# `Any`：存在 `preview_json` 裡的 JSON 形狀。
def _subgroup_ask(ask: dict[str, Any] | None) -> SubgroupAsk | None:
    if ask is None:
        return None
    return SubgroupAsk(
        options=tuple(
            SubgroupOption(
                key=option["key"],
                name=option["name"],
                releases=option["releases"],
                updated=date.fromisoformat(option["updated"]) if option["updated"] else None,
                latest=option["latest"],
                titles=tuple(option["titles"]),
                arguments=option["arguments"],
            )
            for option in ask["options"]
        ),
        preselected=ask["preselected"],
        required=ask["required"],
    )
