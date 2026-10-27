"""用量頁與步驟頁的數字（M5 票 21）。

全部從 `ai_calls`、`ai_tool_calls`、`ai_runs` 算，逐日加總等於 `ai_calls`。
"""

from __future__ import annotations

import itertools
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
import time_machine
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import AiProvider, AiRunKind, AiRunRefusal, AiStopReason, AiToolOutcome, Role
from berth.domain.spend import SpendAlertKind
from berth.models import AiCall, AiConversation, AiRun, AiToolCall, User
from berth.services.usage import (
    RunRejectedError,
    read_run,
    read_usage,
    set_spend_alert,
    spend_check,
)

pytestmark = pytest.mark.asyncio

TAIPEI = ZoneInfo("Asia/Taipei")
#: 台北 2026-10-27 10:00（UTC 02:00）。
NOW = datetime(2026, 10, 27, 10, 0, tzinfo=TAIPEI)
_ids = itertools.count(1)


async def _user(session: AsyncSession, name: str = "roxy", role: Role = Role.ADMIN) -> User:
    user = User(jellyfin_user_id=f"jf-{name}", name=name, role=role)
    session.add(user)
    await session.flush()
    return user


async def _run(
    session: AsyncSession,
    user: User,
    at: datetime,
    *,
    stop: AiStopReason | None = AiStopReason.COMPLETED,
) -> AiRun:
    conversation = AiConversation(id=f"c{next(_ids)}", user_id=user.id)
    run = AiRun(
        id=f"r{next(_ids)}",
        conversation_id=conversation.id,
        user_id=user.id,
        provider=AiProvider.ANTHROPIC,
        model="claude-sonnet-5-5",
        started_at=at,
        stop_reason=stop,
    )
    session.add_all([conversation, run])
    await session.flush()
    return run


def _call(
    run: AiRun,
    at: datetime,
    *,
    step: int = 1,
    input_tokens: int = 1000,
    output: int = 100,
    read: int | None = 0,
    write: int | None = 0,
    cost: float | None = 0.01,
    searches: int = 0,
    error: str = "",
) -> AiCall:
    return AiCall(
        run_id=run.id,
        step=step,
        model="claude-sonnet-5-5",
        input_tokens=input_tokens,
        output_tokens=output,
        cache_read_tokens=read,
        cache_write_tokens=write,
        cost_usd=cost,
        web_searches=searches,
        web_search_cost_usd=None,
        error=error,
        created_at=at,
    )


def _tool(
    run: AiRun, at: datetime, outcome: AiToolOutcome, command: str = "why_not.explain", **kw: bool
) -> AiToolCall:
    return AiToolCall(run_id=run.id, step=1, command=command, outcome=outcome, created_at=at, **kw)


def _utc(local: datetime) -> datetime:
    return local.astimezone(UTC)


class TestDays:
    async def test_the_days_add_up_to_ai_calls(self, session: AsyncSession) -> None:
        user = await _user(session)
        today = NOW - timedelta(hours=1)
        yesterday = NOW - timedelta(days=1)
        run = await _run(session, user, _utc(today))
        old = await _run(session, user, _utc(yesterday))
        session.add_all(
            [
                _call(
                    run, _utc(today), input_tokens=5000, output=300, read=4000, write=500, cost=0.02
                ),
                _call(
                    run,
                    _utc(today),
                    step=2,
                    input_tokens=6000,
                    output=200,
                    read=5500,
                    write=0,
                    cost=0.01,
                ),
                _call(
                    old,
                    _utc(yesterday),
                    input_tokens=2000,
                    output=50,
                    read=0,
                    write=1500,
                    cost=0.005,
                ),
            ]
        )
        await session.flush()

        usage = await read_usage(session, now=NOW)

        total_input, total_output = (
            await session.execute(
                select(func.sum(AiCall.input_tokens), func.sum(AiCall.output_tokens))
            )
        ).one()
        assert sum(d.input_tokens for d in usage.days) == total_input == 13000
        assert sum(d.output_tokens for d in usage.days) == total_output == 550
        assert usage.totals.input_tokens == 13000
        assert usage.totals.cost.known == pytest.approx(0.035)
        by_day = {d.day: d for d in usage.days}
        assert by_day[date(2026, 10, 27)].calls == 2
        assert by_day[date(2026, 10, 27)].cache_read.known == 9500
        assert by_day[date(2026, 10, 27)].cache_write.known == 500
        # 新的 input 是扣掉快取讀寫的那部分。
        assert by_day[date(2026, 10, 27)].new_input == 11000 - 9500 - 500
        assert by_day[date(2026, 10, 27)].hit_rate == pytest.approx(9500 / 11000)
        assert by_day[date(2026, 10, 26)].cache_write.known == 1500

    async def test_days_split_on_the_local_clock(self, session: AsyncSession) -> None:
        # 台北 10-27 00:30 是 UTC 10-26 16:30：算在台北的 27 號。
        user = await _user(session)
        just_after_midnight = datetime(2026, 10, 27, 0, 30, tzinfo=TAIPEI)
        run = await _run(session, user, _utc(just_after_midnight))
        session.add(_call(run, _utc(just_after_midnight)))
        await session.flush()

        usage = await read_usage(session, now=NOW)

        assert [d.day for d in usage.days if d.calls] == [date(2026, 10, 27)]

    async def test_newest_first_and_today_is_always_there(self, session: AsyncSession) -> None:
        user = await _user(session)
        at = NOW - timedelta(days=3)
        run = await _run(session, user, _utc(at))
        session.add(_call(run, _utc(at)))
        await session.flush()

        usage = await read_usage(session, now=NOW)

        assert [d.day for d in usage.days] == [date(2026, 10, 27), date(2026, 10, 24)]
        assert usage.days[0].calls == 0
        assert usage.days[0].hit_rate is None

    async def test_older_than_thirty_days_is_left_out(self, session: AsyncSession) -> None:
        user = await _user(session)
        at = NOW - timedelta(days=30)
        run = await _run(session, user, _utc(at))
        session.add(_call(run, _utc(at)))
        await session.flush()

        usage = await read_usage(session, now=NOW)

        assert usage.totals.calls == 0


class TestUnknowns:
    async def test_unknown_is_counted_not_summed_as_zero(self, session: AsyncSession) -> None:
        user = await _user(session)
        at = NOW - timedelta(hours=1)
        run = await _run(session, user, _utc(at))
        session.add_all(
            [
                _call(run, _utc(at), cost=0.02, write=100),
                # 價目表上沒有的模型；Chat Completions 不報快取寫。
                _call(run, _utc(at), step=2, cost=None, write=None),
                # 出錯、沒有回應：沒有花費可算，不是不知道（協調者 2026-10-27）。
                _call(
                    run,
                    _utc(at),
                    step=3,
                    input_tokens=0,
                    output=0,
                    read=None,
                    write=None,
                    cost=None,
                    error="boom",
                ),
            ]
        )
        await session.flush()

        today = (await read_usage(session, now=NOW)).days[0]

        assert today.cost.known == pytest.approx(0.02)
        # 只有價目查不到的那一次；出錯的那一次不數。
        assert today.cost.unknown == 1
        assert today.cache_write.known == 100
        # 出錯那一次沒有 token，不算「快取寫不知道」。
        assert today.cache_write.unknown == 1

    async def test_web_searches_count_both_kinds(self, session: AsyncSession) -> None:
        user = await _user(session)
        at = NOW - timedelta(hours=1)
        run = await _run(session, user, _utc(at))
        session.add_all(
            [
                _call(run, _utc(at), searches=3),
                _tool(run, _utc(at), AiToolOutcome.OK, "web.tavily_search"),
                _tool(run, _utc(at), AiToolOutcome.WARNED, "web.tavily_search"),
                # 被擋下的沒有搜。
                _tool(run, _utc(at), AiToolOutcome.BLOCKED, "web.tavily_search"),
            ]
        )
        await session.flush()

        today = (await read_usage(session, now=NOW)).days[0]

        assert (today.web_searches, today.tavily_searches) == (3, 2)


class TestGuards:
    async def test_stops_and_tool_outcomes_are_counted(self, session: AsyncSession) -> None:
        user = await _user(session)
        at = _utc(NOW - timedelta(hours=1))
        stopped = await _run(session, user, at, stop=AiStopReason.REPEATED_CALL)
        await _run(session, user, at, stop=AiStopReason.REPEATED_CALL)
        await _run(session, user, at, stop=AiStopReason.NO_PROGRESS)
        await _run(session, user, at, stop=None)  # 還在跑
        session.add_all(
            [
                _tool(stopped, at, AiToolOutcome.BLOCKED),
                _tool(stopped, at, AiToolOutcome.ABORTED),
                _tool(stopped, at, AiToolOutcome.REFUSED),
                _tool(stopped, at, AiToolOutcome.OK, truncated=True),
            ]
        )
        await session.flush()

        guards = (await read_usage(session, now=NOW)).guards

        assert guards.stops[AiStopReason.REPEATED_CALL] == 2
        assert guards.stops[AiStopReason.NO_PROGRESS] == 1
        assert guards.stops[AiStopReason.PING_PONG] == 0
        assert AiStopReason.COMPLETED not in guards.stops
        # 停在確認卡等人按（票 13）是正常的停法，不是防護。
        assert AiStopReason.AWAITING_CONFIRMATION not in guards.stops
        assert (guards.blocked, guards.refused, guards.failed, guards.truncated) == (2, 1, 0, 1)


class TestRecentRuns:
    async def test_newest_first_with_who_and_numbers(self, session: AsyncSession) -> None:
        roxy = await _user(session)
        kid = await _user(session, "kid", Role.USER)
        first = await _run(session, roxy, _utc(NOW - timedelta(hours=2)))
        second = await _run(
            session, kid, _utc(NOW - timedelta(hours=1)), stop=AiStopReason.TOKEN_LIMIT
        )
        second.requests, second.input_tokens, second.cost_usd = 4, 9000, None
        await session.flush()

        runs = (await read_usage(session, now=NOW)).runs

        assert [(r.id, r.user_name) for r in runs] == [(second.id, "kid"), (first.id, "roxy")]
        assert (runs[0].requests, runs[0].input_tokens, runs[0].cost_usd) == (4, 9000, None)
        assert runs[0].stop_reason is AiStopReason.TOKEN_LIMIT


class TestPrices:
    async def test_models_used_are_listed_with_their_price_or_unknown(
        self, session: AsyncSession
    ) -> None:
        user = await _user(session)
        at = _utc(NOW - timedelta(hours=1))
        run = await _run(session, user, at)
        unknown = _call(run, at, step=2, cost=None)
        unknown.model = "my-local-llm"
        session.add_all([_call(run, at), unknown])
        await session.flush()

        prices = {p.model: p.price for p in (await read_usage(session, now=NOW)).prices}

        assert prices["my-local-llm"] is None
        sonnet = prices["claude-sonnet-5-5"]
        assert sonnet is not None
        assert sonnet.verified == date(2026, 10, 27)


class TestAlerts:
    async def _spend(self, session: AsyncSession, user: User, days_ago: int, cost: float) -> None:
        at = _utc(NOW - timedelta(days=days_ago, hours=1))
        run = await _run(session, user, at)
        session.add(_call(run, at, cost=cost))
        await session.flush()

    async def test_the_daily_threshold_alerts(self, session: AsyncSession) -> None:
        user = await _user(session)
        await set_spend_alert(session, 0.5)
        await self._spend(session, user, 0, 0.6)

        usage = await read_usage(session, now=NOW)

        assert usage.daily_alert_usd == 0.5
        assert [a.kind for a in usage.spend.alerts] == [SpendAlertKind.THRESHOLD]

    async def test_an_anomaly_alerts_against_the_days_with_usage(
        self, session: AsyncSession
    ) -> None:
        user = await _user(session)
        for days_ago in (2, 5, 9):
            await self._spend(session, user, days_ago, 0.02)
        await self._spend(session, user, 0, 0.10)

        alerts = (await read_usage(session, now=NOW)).spend.alerts

        assert [(a.kind, a.against) for a in alerts] == [(SpendAlertKind.ANOMALY, Decimal("0.02"))]

    async def test_clearing_the_threshold_stops_alerting(self, session: AsyncSession) -> None:
        user = await _user(session)
        await set_spend_alert(session, 0.5)
        await set_spend_alert(session, None)
        await self._spend(session, user, 0, 0.6)

        usage = await read_usage(session, now=NOW)

        assert usage.daily_alert_usd is None
        assert usage.spend.alerts == []


class TestARun:
    async def test_steps_in_order_with_their_tool_calls(self, session: AsyncSession) -> None:
        user = await _user(session)
        at = _utc(NOW - timedelta(hours=1))
        run = await _run(session, user, at, stop=AiStopReason.REPEATED_CALL)
        run.requests, run.tool_calls, run.input_tokens = 2, 3, 11000
        session.add_all(
            [
                _call(run, at + timedelta(seconds=5), step=2, input_tokens=6000),
                _call(run, at, step=1, input_tokens=5000),
                _tool(run, at, AiToolOutcome.OK),
                AiToolCall(
                    run_id=run.id,
                    step=2,
                    command="why_not.explain",
                    outcome=AiToolOutcome.BLOCKED,
                    detail="same call a third time",
                    created_at=at,
                ),
                AiToolCall(
                    run_id=run.id,
                    step=2,
                    command="why_not.explain",
                    outcome=AiToolOutcome.ABORTED,
                    created_at=at + timedelta(seconds=1),
                ),
            ]
        )
        await session.flush()

        found = await read_run(session, run.id, user_id=user.id, role=Role.USER)

        assert found.stop_reason is AiStopReason.REPEATED_CALL
        assert (found.requests, found.tool_calls, found.input_tokens) == (2, 3, 11000)
        assert [s.step for s in found.steps] == [1, 2]
        assert [s.call.input_tokens for s in found.steps if s.call] == [5000, 6000]
        assert [t.outcome for t in found.steps[1].tools] == [
            AiToolOutcome.BLOCKED,
            AiToolOutcome.ABORTED,
        ]
        assert found.steps[1].tools[0].detail == "same call a third time"

    async def test_a_run_cut_off_mid_call_still_has_its_numbers(
        self, session: AsyncSession
    ) -> None:
        user = await _user(session)
        at = _utc(NOW - timedelta(hours=1))
        run = await _run(session, user, at, stop=AiStopReason.ERROR)
        session.add(
            _call(run, at, input_tokens=0, output=0, read=None, write=None, cost=None, error="429")
        )
        await session.flush()

        found = await read_run(session, run.id, user_id=user.id, role=Role.USER)

        assert found.steps[0].call is not None
        assert found.steps[0].call.error == "429"

    async def test_someone_elses_run_is_missing_for_a_user(self, session: AsyncSession) -> None:
        owner = await _user(session)
        other = await _user(session, "kid", Role.USER)
        run = await _run(session, owner, _utc(NOW))

        with pytest.raises(RunRejectedError) as caught:
            await read_run(session, run.id, user_id=other.id, role=Role.USER)
        assert caught.value.reason is AiRunRefusal.RUN_MISSING

    async def test_an_admin_sees_anyones_run(self, session: AsyncSession) -> None:
        owner = await _user(session, "kid", Role.USER)
        admin = await _user(session)
        run = await _run(session, owner, _utc(NOW))

        found = await read_run(session, run.id, user_id=admin.id, role=Role.ADMIN)

        assert found.user_name == "kid"

    async def test_an_unknown_run_is_missing(self, session: AsyncSession) -> None:
        admin = await _user(session)
        with pytest.raises(RunRejectedError):
            await read_run(session, "nope", user_id=admin.id, role=Role.ADMIN)


class TestReviewFixes:
    """code-review（票 21）：不知道的不當 0，0 也不當不知道；分日跟著夏令時走。"""

    async def test_a_known_zero_is_still_known(self, session: AsyncSession) -> None:
        user = await _user(session)
        at = _utc(NOW - timedelta(hours=1))
        run = await _run(session, user, at)
        session.add_all([_call(run, at, write=0), _call(run, at, step=2, write=None)])
        await session.flush()

        today = (await read_usage(session, now=NOW)).days[0]

        # 一次報了 0、一次沒報：知道的是 1 次，畫面寫「0 +未知」而不是「未知」。
        assert (today.cache_write.known, today.cache_write.counted, today.cache_write.unknown) == (
            0,
            1,
            1,
        )

    async def test_the_hit_rate_leaves_out_calls_whose_reads_are_unknown(
        self, session: AsyncSession
    ) -> None:
        user = await _user(session)
        at = _utc(NOW - timedelta(hours=1))
        run = await _run(session, user, at)
        session.add_all(
            [
                _call(run, at, input_tokens=1000, read=800),
                _call(run, at, step=2, input_tokens=9000, read=None),
            ]
        )
        await session.flush()

        today = (await read_usage(session, now=NOW)).days[0]

        assert today.hit_rate == pytest.approx(0.8)

    async def test_no_known_reads_is_no_rate_not_zero(self, session: AsyncSession) -> None:
        user = await _user(session)
        at = _utc(NOW - timedelta(hours=1))
        run = await _run(session, user, at)
        session.add(_call(run, at, read=None))
        await session.flush()

        assert (await read_usage(session, now=NOW)).days[0].hit_rate is None

    async def test_days_follow_daylight_saving_on_the_server_clock(
        self, session: AsyncSession
    ) -> None:
        # 紐約 2026-11-01 結束夏令時。10-31 00:30 EDT 是 UTC 04:30；拿今天（EST，-5）的固定偏移換算
        # 會變成 10-30 23:30，算錯一天。time-machine 照目的地的 `ZoneInfo` 換掉程序的 `TZ`。
        user = await _user(session)
        at = datetime(2026, 10, 31, 4, 30, tzinfo=UTC)
        run = await _run(session, user, at)
        session.add(_call(run, at))
        await session.flush()

        new_york = ZoneInfo("America/New_York")
        with time_machine.travel(datetime(2026, 11, 5, 12, 0, tzinfo=new_york), tick=False):
            usage = await read_usage(session)

        assert [d.day for d in usage.days if d.calls] == [date(2026, 10, 31)]

    async def test_the_panel_alerts_match_the_page(self, session: AsyncSession) -> None:
        user = await _user(session)
        await set_spend_alert(session, 0.5)
        at = _utc(NOW - timedelta(hours=1))
        run = await _run(session, user, at)
        session.add(_call(run, at, cost=0.6))
        await session.flush()

        assert (await spend_check(session, now=NOW)).alerts == (
            await read_usage(session, now=NOW)
        ).spend.alerts


class TestUnknownCostsInTheReminders:
    """協調者 2026-10-27：提醒只算有價目的那部分。

    費用未知的呼叫要說出來，不讓「沒有提醒」看起來像沒事。
    """

    async def _spend(
        self, session: AsyncSession, user: User, days_ago: int, cost: float | None
    ) -> None:
        at = _utc(NOW - timedelta(days=days_ago, hours=1))
        run = await _run(session, user, at)
        session.add(_call(run, at, cost=cost))
        await session.flush()

    async def test_unknown_costs_today_and_before_are_counted(self, session: AsyncSession) -> None:
        user = await _user(session)
        await set_spend_alert(session, 0.5)
        await self._spend(session, user, 0, None)
        await self._spend(session, user, 0, None)
        await self._spend(session, user, 0, 0.01)
        await self._spend(session, user, 3, None)
        # 第 15 天之前的不在基準期間裡。
        await self._spend(session, user, 20, None)

        spend = (await read_usage(session, now=NOW)).spend

        assert spend.alerts == []
        assert (spend.unknown_today, spend.unknown_before) == (2, 1)

    async def test_the_panel_sees_the_same_unknowns(self, session: AsyncSession) -> None:
        user = await _user(session)
        await self._spend(session, user, 0, None)
        await self._spend(session, user, 6, None)

        assert await spend_check(session, now=NOW) == (await read_usage(session, now=NOW)).spend

    async def test_all_known_costs_leave_nothing_unsaid(self, session: AsyncSession) -> None:
        user = await _user(session)
        await self._spend(session, user, 0, 0.01)

        spend = await spend_check(session, now=NOW)

        assert (spend.unknown_today, spend.unknown_before) == (0, 0)


class TestCompactionRuns:
    """票 18 交接：`ai_runs` 有 `chat` 與 `compaction` 兩種。

    「輪」只數對話，費用與 token 含壓縮的摘要（`ai_calls` 本來就有它那一次呼叫）。
    """

    async def test_a_summary_counts_in_the_money_but_not_as_a_turn(
        self, session: AsyncSession
    ) -> None:
        user = await _user(session)
        at = _utc(NOW - timedelta(hours=1))
        chat = await _run(session, user, at)
        summary = await _run(session, user, at + timedelta(seconds=5))
        summary.kind = AiRunKind.COMPACTION
        session.add_all([_call(chat, at, cost=0.01), _call(summary, at, cost=0.02)])
        await session.flush()

        usage = await read_usage(session, now=NOW)

        assert usage.runs_count == 1
        assert [run.id for run in usage.runs] == [chat.id]
        assert usage.totals.calls == 2
        assert usage.totals.cost.known == pytest.approx(0.03)


class TestFailedCallsAreNotUnknownCosts:
    """協調者 2026-10-27：出錯、沒拿到回應的呼叫沒有 token，也就沒有花費可算。

    費用未知只數「有回應、有 token，但價目查不到」的；不然一次出錯就讓有價目的模型連掛兩週
    「提醒沒算進」。
    """

    async def test_a_failed_call_on_a_priced_model_leaves_nothing_unknown(
        self, session: AsyncSession
    ) -> None:
        user = await _user(session)
        at = _utc(NOW - timedelta(hours=1))
        run = await _run(session, user, at)
        session.add_all(
            [
                _call(run, at, cost=0.01),
                _call(
                    run,
                    at,
                    step=2,
                    input_tokens=0,
                    output=0,
                    read=None,
                    write=None,
                    cost=None,
                    error="status_code: 529, overloaded",
                ),
            ]
        )
        await session.flush()

        usage = await read_usage(session, now=NOW)
        panel = await spend_check(session, now=NOW)

        assert (panel.unknown_today, panel.unknown_before) == (0, 0)
        assert usage.spend == panel
        assert usage.days[0].cost.unknown == 0
        assert usage.days[0].cost.known == pytest.approx(0.01)
