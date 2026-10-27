"""AI 用量頁的數字與花費提醒（M5 票 21、研究 C5、brief §6.10）。

數字**全從觀測的三張表算**：逐日 token、快取、費用、網搜加總自 `ai_calls`（Tavily 是
`ai_tool_calls` 的 `web.tavily_search`），停止原因數自 `ai_runs`。逐日表的加總就是 `ai_calls` 的加總
（`tests/integration/test_usage.py`）。

- **分日照伺服器的時區**（`now` 的時區；正式跑是 `datetime.now().astimezone()`），近 30 天含今天。
- **不知道的不當 0**（研究 C5）：快取讀寫、費用各自記「知道的加總」與「幾次呼叫不知道」。
  出錯、沒有回應的那一次沒有 token，也就沒有花費可算：快取與費用都不數它，**不是**不知道（協調者
  2026-10-27：否則一次出錯就讓有價目的模型連掛兩週「提醒沒算進」）。`ai_runs.cost_usd` 的合計
  （`services.agent` 的記帳）仍照「有一次算不出來就是 `NULL`」。
- **花費提醒只提醒、不停用**（`domain.spend`）：用知道的那部分費用比。提醒值存在 `settings.ai`。
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from decimal import Decimal

from pydantic import NonNegativeFloat
from sqlalchemy import ColumnElement, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.adapters.ai.prices import ModelPrice, price_of
from berth.domain import AiProvider, AiRunKind, AiRunRefusal, AiStopReason, AiToolOutcome, Role
from berth.domain.spend import ANOMALY_WINDOW_DAYS, SpendAlert, spend_alerts
from berth.models import AiCall, AiRun, AiSettings, AiToolCall, User
from berth.services.agent_tools import TAVILY_TOOL
from berth.services.commands import Effect, Flag, command
from berth.services.settings import read_settings, update_settings

#: 用量頁看近幾天（含今天）。
WINDOW_DAYS = 30
#: 「最近的輪」列幾輪。
RECENT_RUNS = 20
#: Tavily 真的搜了的那幾種結果：照做了的與警告後照做的（被擋下、失敗的沒有搜）。
_SEARCHED = frozenset({AiToolOutcome.OK, AiToolOutcome.WARNED})


def tavily_searched(tool: AiToolCall) -> bool:
    """這一次工具呼叫是不是真的用掉一次 Tavily。

    用量頁、步驟頁與 `/usage`（`services.slash`）共用這一條規則。
    """
    return tool.command == TAVILY_TOOL and tool.outcome in _SEARCHED


def tavily_searched_sql() -> ColumnElement[bool]:
    """`tavily_searched` 的 SQL 寫法：在資料庫裡數的那一處（`/usage`）用它。"""
    return and_(AiToolCall.command == TAVILY_TOOL, AiToolCall.outcome.in_(_SEARCHED))


#: 防護與出錯：用量頁數這幾種停止原因。答完與停在確認卡等人按（票 13）是正常的停法，不數。
GUARD_STOPS: tuple[AiStopReason, ...] = tuple(
    reason
    for reason in AiStopReason
    if reason not in {AiStopReason.COMPLETED, AiStopReason.AWAITING_CONFIRMATION}
)


@dataclass(slots=True)
class Tally[N: (int, float)]:
    """知道的加總、幾次呼叫知道、幾次不知道。**0 也是知道**：知道的加總是 0 不等於全部不知道
    （`counted` 分得出來）。"""

    known: N
    counted: int = 0
    unknown: int = 0

    def add(self, value: N | None) -> None:
        if value is None:
            self.unknown += 1
        else:
            self.known += value
            self.counted += 1

    def merge(self, other: Tally[N]) -> None:
        self.known += other.known
        self.counted += other.counted
        self.unknown += other.unknown


@dataclass(slots=True)
class DayUsage:
    day: date
    calls: int = 0
    #: 全部的 input，含快取讀寫（`adapters/ai/usage.py`）。
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read: Tally[int] = field(default_factory=lambda: Tally(0))
    cache_write: Tally[int] = field(default_factory=lambda: Tally(0))
    #: 估計費用（美元）。
    cost: Tally[float] = field(default_factory=lambda: Tally(0.0))
    #: 伺服器端網搜（Anthropic 的 `web_search`）。
    web_searches: int = 0
    #: Tavily（使用者自己的 Tavily credit，不在估計費用裡）。
    tavily_searches: int = 0
    #: 快取讀知道的那幾次呼叫的 input：命中率的分母（不知道的那幾次不算進去，也不當 0）。
    read_input: int = 0

    @property
    def new_input(self) -> int:
        """沒命中、也沒寫進快取的 input。"""
        return max(self.input_tokens - self.cache_read.known - self.cache_write.known, 0)

    @property
    def hit_rate(self) -> float | None:
        """快取讀 ÷ 那幾次呼叫的 input；沒有一次知道快取讀（或沒有 input）是 `None`。"""
        return self.cache_read.known / self.read_input if self.read_input else None

    def add_call(self, call: AiCall) -> None:
        self.calls += 1
        self.input_tokens += call.input_tokens
        self.output_tokens += call.output_tokens
        self.web_searches += call.web_searches
        # 出錯、沒拿到回應的那一次沒有 token，也就沒有花費可算：快取與費用都不數它（不是不知道）。
        if call.error:
            return
        self.cache_read.add(call.cache_read_tokens)
        self.cache_write.add(call.cache_write_tokens)
        if call.cache_read_tokens is not None:
            self.read_input += call.input_tokens
        self.cost.add(call.cost_usd)

    def merge(self, other: DayUsage) -> None:
        self.calls += other.calls
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read.merge(other.cache_read)
        self.cache_write.merge(other.cache_write)
        self.cost.merge(other.cost)
        self.read_input += other.read_input
        self.web_searches += other.web_searches
        self.tavily_searches += other.tavily_searches


@dataclass(frozen=True, slots=True)
class GuardCounts:
    #: 每一種停止原因（完成的除外）各幾輪；0 的也在。
    stops: dict[AiStopReason, int]
    #: 被擋下的工具呼叫（第 3 次擋下與第 4 次中止）。
    blocked: int
    #: 命令以宣告的理由拒絕。
    refused: int
    #: 參數錯或命令出錯。
    failed: int
    #: 結果太長、交給模型的是截過的。
    truncated: int


@dataclass(frozen=True, slots=True)
class RunRow:
    id: str
    started_at: datetime
    user_name: str
    stop_reason: AiStopReason | None
    requests: int
    tool_calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float | None


@dataclass(frozen=True, slots=True)
class ModelPriceRow:
    model: str
    #: 價目表上沒有是 `None`（畫面寫「未知」）。
    price: ModelPrice | None


@dataclass(frozen=True, slots=True)
class UsageView:
    today: date
    #: 有用量的日子加上今天，新的在前。
    days: list[DayUsage]
    totals: DayUsage
    runs_count: int
    guards: GuardCounts
    runs: list[RunRow]
    prices: list[ModelPriceRow]
    daily_alert_usd: float | None
    spend: SpendCheck


@dataclass(frozen=True, slots=True)
class SpendCheck:
    """今天的花費提醒，與它**沒算進去的**。

    提醒只用知道的費用比，有回應、有 token 而價目表上沒有這個模型的那幾次不在裡面。管理員要看得出
    「沒有提醒」是沒事，還是有一部分根本沒算（brief §6.10：未知不當 0）。
    """

    alerts: list[SpendAlert]
    #: 今天幾次呼叫的費用不知道（每日提醒值與異常都比今天）。
    unknown_today: int
    #: 前 14 天（異常的基準）幾次呼叫的費用不知道。
    unknown_before: int


def _local_day(at: datetime, zone: tzinfo | None) -> date:
    """伺服器時區的日期。`zone` 是 `None` 時照系統時區**逐一換算**：`datetime.now().astimezone()`
    給的是今天的固定偏移，30 天裡跨過夏令時的那幾天會差一小時、分錯日。"""
    aware = at.replace(tzinfo=at.tzinfo or UTC)
    return (aware.astimezone(zone) if zone is not None else aware.astimezone()).date()


def _day_start(day: date, zone: tzinfo | None) -> datetime:
    """那一天 00:00（伺服器時區）換成 UTC。"""
    if zone is not None:
        return datetime.combine(day, time.min, zone).astimezone(UTC)
    return datetime.combine(day, time.min).astimezone().astimezone(UTC)


# 用量頁：只讀三張觀測表與設定。
@command(Effect.READ)
async def read_usage(session: AsyncSession, *, now: datetime | None = None) -> UsageView:
    """近 30 天的用量、防護次數、最近的輪、用到的模型的價目與今天的花費提醒。"""
    zone = now.tzinfo if now is not None else None
    today = (now or datetime.now().astimezone()).date()
    start = _day_start(today - timedelta(days=WINDOW_DAYS - 1), zone)

    calls = (await session.scalars(select(AiCall).where(AiCall.created_at >= start))).all()
    tools = (await session.scalars(select(AiToolCall).where(AiToolCall.created_at >= start))).all()
    runs = (
        await session.execute(
            select(AiRun, User.name)
            .join(User, User.id == AiRun.user_id)
            # 「輪」只數對話；壓縮的摘要（票 18）不是一輪，它的費用與 token 照樣在 `ai_calls` 裡。
            .where(AiRun.started_at >= start, AiRun.kind == AiRunKind.CHAT)
            .order_by(AiRun.started_at.desc())
        )
    ).all()

    by_day: dict[date, DayUsage] = {today: DayUsage(today)}
    for call in calls:
        day = _local_day(call.created_at, zone)
        by_day.setdefault(day, DayUsage(day)).add_call(call)
    for tool in tools:
        if tavily_searched(tool):
            day = _local_day(tool.created_at, zone)
            by_day.setdefault(day, DayUsage(day)).tavily_searches += 1
    days = sorted(by_day.values(), key=lambda d: d.day, reverse=True)
    totals = DayUsage(today)
    for day_usage in days:
        totals.merge(day_usage)

    threshold = (await read_settings(session, AiSettings)).daily_alert_usd
    spend = _check(
        {day: (usage.cost.known, usage.cost.unknown) for day, usage in by_day.items()},
        today,
        threshold,
    )
    models = sorted({call.model for call in calls})
    return UsageView(
        today=today,
        days=days,
        totals=totals,
        runs_count=len(runs),
        guards=_guards([run for run, _ in runs], tools),
        runs=[_run_row(run, name) for run, name in runs[:RECENT_RUNS]],
        prices=[ModelPriceRow(model, price_of(model)) for model in models],
        daily_alert_usd=threshold,
        spend=spend,
    )


# 側面板（管理員）的花費提醒：與用量頁同一份規則，只讀近 15 天的費用。`agent.read_status` 叫，
# 不當工具。
@command(Effect.READ, flags={Flag.INTERNAL})
async def spend_check(session: AsyncSession, *, now: datetime | None = None) -> SpendCheck:
    """今天的花費提醒與沒算進去的呼叫數（同用量頁的那一份）。"""
    zone = now.tzinfo if now is not None else None
    today = (now or datetime.now().astimezone()).date()
    start = _day_start(today - timedelta(days=ANOMALY_WINDOW_DAYS), zone)
    rows = await session.execute(
        select(AiCall.created_at, AiCall.cost_usd).where(
            AiCall.created_at >= start,
            # 同 `DayUsage.add_call`：出錯、沒有回應的那一次沒有花費可算，不是費用未知。
            AiCall.error == "",
        )
    )
    costs: dict[date, tuple[float, int]] = {}
    for created_at, cost in rows:
        day = _local_day(created_at, zone)
        known, unknown = costs.get(day, (0.0, 0))
        costs[day] = (known + cost, unknown) if cost is not None else (known, unknown + 1)
    threshold = (await read_settings(session, AiSettings)).daily_alert_usd
    return _check(costs, today, threshold)


def _check(
    costs: dict[date, tuple[float, int]], today: date, threshold: float | None
) -> SpendCheck:
    """逐日的（已知費用, 費用未知的呼叫數）→ 今天的提醒（`domain.spend`）與沒算進去的次數。
    近 14 天沒用量的日子補 0。"""
    before = [today - timedelta(days=n) for n in range(ANOMALY_WINDOW_DAYS, 0, -1)]
    known_today, unknown_today = costs.get(today, (0.0, 0))
    alerts = spend_alerts(
        _dollars(known_today),
        threshold=_dollars(threshold) if threshold is not None else None,
        previous=[_dollars(costs.get(day, (0.0, 0))[0]) for day in before],
    )
    return SpendCheck(
        alerts=alerts,
        unknown_today=unknown_today,
        unknown_before=sum(costs.get(day, (0.0, 0))[1] for day in before),
    )


def _dollars(value: float) -> Decimal:
    # 費用以 float 存；比較用 Decimal，先照記帳的精度收掉 float 的尾數。
    return Decimal(str(round(value, 9)))


def _guards(runs: Sequence[AiRun], tools: Sequence[AiToolCall]) -> GuardCounts:
    stops = Counter(run.stop_reason for run in runs)
    outcomes = Counter(tool.outcome for tool in tools)
    return GuardCounts(
        stops={reason: stops[reason] for reason in GUARD_STOPS},
        blocked=outcomes[AiToolOutcome.BLOCKED] + outcomes[AiToolOutcome.ABORTED],
        refused=outcomes[AiToolOutcome.REFUSED],
        failed=outcomes[AiToolOutcome.FAILED],
        truncated=sum(1 for tool in tools if tool.truncated),
    )


def _run_row(run: AiRun, user_name: str) -> RunRow:
    return RunRow(
        id=run.id,
        started_at=run.started_at,
        user_name=user_name,
        stop_reason=run.stop_reason,
        requests=run.requests,
        tool_calls=run.tool_calls,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        cost_usd=run.cost_usd,
    )


# 改設定（每日提醒值）；用原值再存一次就回去。只提醒，不擋任何東西。
@command(Effect.REVERSIBLE, inverse="usage.set_spend_alert", flags={Flag.SETTINGS})
async def set_spend_alert(
    session: AsyncSession, daily_usd: NonNegativeFloat | None
) -> float | None:
    """存每日提醒值（美元）；`None` 是不提醒。回存下去的值。"""

    def change(settings: AiSettings) -> None:
        settings.daily_alert_usd = daily_usd

    return (await update_settings(session, AiSettings, change)).daily_alert_usd


class RunRejectedError(Exception):
    def __init__(self, reason: AiRunRefusal, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True, slots=True)
class StepCall:
    model: str
    input_tokens: int
    output_tokens: int
    #: `None` 是接口沒報（研究 C5）。
    cache_read_tokens: int | None
    cache_write_tokens: int | None
    cost_usd: float | None
    web_searches: int
    #: 模型說它為什麼停（原樣）；出錯是空字串。
    finish_reason: str
    duration_ms: int
    #: 出錯的原文（key 已遮掉）；成功是空字串。
    error: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class StepTool:
    command: str
    args_json: str
    outcome: AiToolOutcome
    #: 拒絕的理由、錯誤的原文；成功是空字串。
    detail: str
    truncated: bool
    duration_ms: int


@dataclass(frozen=True, slots=True)
class RunStep:
    #: 第幾次模型呼叫（`ai_calls.step`）。
    step: int
    #: 這一次模型呼叫；記帳之前就斷掉的那一次是 `None`（只剩它叫的工具）。
    call: StepCall | None
    #: 這一次模型呼叫叫的工具，照時間。
    tools: list[StepTool]


@dataclass(frozen=True, slots=True)
class RunView:
    id: str
    user_name: str
    provider: AiProvider
    model: str
    started_at: datetime
    #: 還在跑是 `None`。
    ended_at: datetime | None
    #: 還在跑是 `None`。
    stop_reason: AiStopReason | None
    error: str
    #: 這一輪是對哪一輪按的「繼續」。
    continues: str | None
    requests: int
    tool_calls: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int | None
    cache_write_tokens: int | None
    cost_usd: float | None
    web_searches: int
    tavily_searches: int
    steps: list[RunStep]

    @property
    def hit_rate(self) -> float | None:
        """快取讀 ÷ input；有一次不知道快取讀（合計是 `None`）或沒有 input 是 `None`。"""
        if self.cache_read_tokens is None or not self.input_tokens:
            return None
        return self.cache_read_tokens / self.input_tokens


# 一輪的步驟：只讀三張觀測表。一般使用者看得到自己的（側面板每一則回覆連過來），管理員看得到全部。
@command(Effect.READ, refusals=(AiRunRefusal,), audience=Role.USER)
async def read_run(session: AsyncSession, run_id: str, *, user_id: int, role: Role) -> RunView:
    """一輪裡每一次模型呼叫與它叫的工具，各自的 token、耗時、結果，以及停止原因。"""
    found = (
        await session.execute(
            select(AiRun, User.name).join(User, User.id == AiRun.user_id).where(AiRun.id == run_id)
        )
    ).one_or_none()
    if found is None or (role is not Role.ADMIN and found[0].user_id != user_id):
        raise RunRejectedError(AiRunRefusal.RUN_MISSING, run_id)
    run, user_name = found
    calls = (
        await session.scalars(select(AiCall).where(AiCall.run_id == run_id).order_by(AiCall.step))
    ).all()
    tools = (
        await session.scalars(
            select(AiToolCall)
            .where(AiToolCall.run_id == run_id)
            .order_by(AiToolCall.created_at, AiToolCall.id)
        )
    ).all()
    by_step: dict[int, list[StepTool]] = {}
    for tool in tools:
        by_step.setdefault(tool.step, []).append(_step_tool(tool))
    call_of = {call.step: _step_call(call) for call in calls}
    return RunView(
        id=run.id,
        user_name=user_name,
        provider=run.provider,
        model=run.model,
        started_at=run.started_at,
        ended_at=run.ended_at,
        stop_reason=run.stop_reason,
        error=run.error,
        continues=run.continues,
        requests=run.requests,
        tool_calls=run.tool_calls,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        cache_read_tokens=run.cache_read_tokens,
        cache_write_tokens=run.cache_write_tokens,
        cost_usd=run.cost_usd,
        web_searches=run.web_searches,
        tavily_searches=sum(1 for tool in tools if tavily_searched(tool)),
        steps=[
            RunStep(step, call_of.get(step), by_step.get(step, []))
            for step in sorted(call_of.keys() | by_step.keys())
        ],
    )


def _step_call(call: AiCall) -> StepCall:
    return StepCall(
        model=call.model,
        input_tokens=call.input_tokens,
        output_tokens=call.output_tokens,
        cache_read_tokens=call.cache_read_tokens,
        cache_write_tokens=call.cache_write_tokens,
        cost_usd=call.cost_usd,
        web_searches=call.web_searches,
        finish_reason=call.finish_reason,
        duration_ms=call.duration_ms,
        error=call.error,
        created_at=call.created_at,
    )


def _step_tool(tool: AiToolCall) -> StepTool:
    return StepTool(
        command=tool.command,
        args_json=tool.args_json,
        outcome=tool.outcome,
        detail=tool.detail,
        truncated=tool.truncated,
        duration_ms=tool.duration_ms,
    )
