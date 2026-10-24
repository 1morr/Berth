"""用量頁的彙總（M5 票 13、plan §11.6〈用量記錄〉）：依日期、出處、格式與模型、人、失敗類型。

命中率 = Σ 快取讀取 ÷ Σ 輸入（輸入含快取寫入與讀取），**只加輸入與快取讀取兩格都知道的呼叫**；
`NULL` 是「不知道」，不當 0。期望值是手算的數字，不是照實作再算一次。
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import AiCallOrigin, AiFailure, ApiFormat, Role
from berth.models import AiCall, User
from berth.services.ai_usage import UsageTally, read_usage

pytestmark = pytest.mark.asyncio

TAIPEI = ZoneInfo("Asia/Taipei")
TODAY = date(2026, 10, 24)
#: 台北的 10-24 中午。
NOON = datetime(2026, 10, 24, 4, 0, tzinfo=UTC)


def call(
    *,
    at: datetime = NOON,
    input: int | None = 1000,
    output: int | None = 100,
    write: int | None = 0,
    read: int | None = 0,
    model: str = "claude-opus-5-5",
    host: str = "api.anthropic.com",
    origin: AiCallOrigin = AiCallOrigin.TEST,
    user: User | None = None,
    failure: AiFailure | None = None,
) -> AiCall:
    return AiCall(
        created_at=at,
        format=ApiFormat.ANTHROPIC,
        host=host,
        model=model,
        input_tokens=input,
        output_tokens=output,
        cache_write_tokens=write,
        cache_read_tokens=read,
        duration_ms=1200,
        origin=origin,
        user_id=user.id if user else None,
        failure=failure,
    )


async def stored(session: AsyncSession, *calls: AiCall) -> None:
    session.add_all(calls)
    await session.commit()


async def person(session: AsyncSession, name: str) -> User:
    user = User(jellyfin_user_id=f"jf-{name}", name=name, role=Role.ADMIN)
    session.add(user)
    await session.commit()
    return user


class TestTheHitRate:
    async def test_cache_reads_over_all_input_including_cache_writes(
        self, session: AsyncSession
    ) -> None:
        await stored(
            session,
            call(input=1000, write=600, read=0, output=50),
            call(input=1000, write=0, read=900, output=70),
        )

        report = await read_usage(session, days=7, today=TODAY, zone=TAIPEI)

        assert report.totals == UsageTally(
            calls=2,
            failed=0,
            input_tokens=2000,
            output_tokens=120,
            cache_write_tokens=600,
            cache_read_tokens=900,
            hit_rate=0.45,
            cache_unreported=0,
        )

    async def test_calls_whose_cache_read_is_unknown_stay_out_of_it_and_are_counted(
        self, session: AsyncSession
    ) -> None:
        await stored(
            session,
            call(input=1000, write=None, read=500),
            # 端點不回快取欄位：輸入照加，命中率不算它。
            call(input=3000, write=None, read=None, output=200),
            # 被限流：什麼都不知道。沒有輸入可算，也不算「沒回報快取」。
            call(input=None, output=None, write=None, read=None, failure=AiFailure.RATE_LIMITED),
        )

        totals = (await read_usage(session, days=7, today=TODAY, zone=TAIPEI)).totals

        assert totals == UsageTally(
            calls=3,
            failed=1,
            input_tokens=4000,
            output_tokens=300,
            cache_write_tokens=0,
            cache_read_tokens=500,
            hit_rate=0.5,
            cache_unreported=1,
        )

    async def test_nothing_to_divide_by_is_no_rate_rather_than_zero(
        self, session: AsyncSession
    ) -> None:
        await stored(session, call(input=3000, read=None), call(input=0, read=0, output=0))

        totals = (await read_usage(session, days=7, today=TODAY, zone=TAIPEI)).totals

        assert totals.hit_rate is None
        assert totals.cache_unreported == 1

    async def test_no_calls_at_all_is_an_empty_tally(self, session: AsyncSession) -> None:
        report = await read_usage(session, days=7, today=TODAY, zone=TAIPEI)

        assert report.totals == UsageTally(
            calls=0,
            failed=0,
            input_tokens=0,
            output_tokens=0,
            cache_write_tokens=0,
            cache_read_tokens=0,
            hit_rate=None,
            cache_unreported=0,
        )
        assert report.has_any is False


class TestThePeriod:
    async def test_days_are_cut_on_the_wall_clock_and_every_day_is_listed(
        self, session: AsyncSession
    ) -> None:
        await stored(
            session,
            # 台北 10-17 23:30：七天前那一天的最後半小時，不在期間裡。
            call(at=datetime(2026, 10, 17, 15, 30, tzinfo=UTC), input=9999),
            # 台北 10-18 00:30：期間的第一天（UTC 還是 10-17）。
            call(at=datetime(2026, 10, 17, 16, 30, tzinfo=UTC), input=100, read=0),
            call(at=NOON, input=200, read=50),
            call(at=NOON, input=200, read=150),
        )

        report = await read_usage(session, days=7, today=TODAY, zone=TAIPEI)

        assert (report.since, report.until) == (date(2026, 10, 18), TODAY)
        assert [day.date for day in report.days] == [date(2026, 10, d) for d in range(18, 25)]
        assert [day.tally.calls for day in report.days] == [1, 0, 0, 0, 0, 0, 2]
        assert report.days[-1].tally.input_tokens == 400
        assert report.days[-1].tally.hit_rate == 0.5
        assert report.days[1].tally.hit_rate is None
        assert report.totals.input_tokens == 500

    async def test_older_calls_still_say_there_has_been_usage(self, session: AsyncSession) -> None:
        await stored(session, call(at=datetime(2026, 1, 1, tzinfo=UTC)))

        report = await read_usage(session, days=7, today=TODAY, zone=TAIPEI)

        assert report.has_any is True
        assert report.totals.calls == 0


class TestTheBreakdowns:
    async def test_the_same_model_on_two_hosts_is_two_lines(self, session: AsyncSession) -> None:
        await stored(
            session,
            call(model="claude-opus-5-5", input=1000, read=800),
            call(model="claude-opus-5-5", input=1000, read=200),
            call(model="claude-opus-5-5", host="openrouter.ai", input=500, read=None),
            call(model="claude-haiku-5-5", input=300, read=0),
        )

        lines = (await read_usage(session, days=7, today=TODAY, zone=TAIPEI)).by_model

        # 用得多的在前（輸入 tokens），同量照名字。
        assert [(line.format, line.host, line.model) for line in lines] == [
            (ApiFormat.ANTHROPIC, "api.anthropic.com", "claude-opus-5-5"),
            (ApiFormat.ANTHROPIC, "openrouter.ai", "claude-opus-5-5"),
            (ApiFormat.ANTHROPIC, "api.anthropic.com", "claude-haiku-5-5"),
        ]
        assert [line.tally.hit_rate for line in lines] == [0.5, None, 0.0]
        assert lines[1].tally.cache_unreported == 1

    async def test_each_person_and_nobody(self, session: AsyncSession) -> None:
        skipper = await person(session, "skipper")
        deckhand = await person(session, "deckhand")
        await stored(
            session,
            call(user=deckhand, input=100),
            call(user=skipper, input=5000),
            call(user=skipper, input=5000),
            call(user=None, input=10),
        )

        lines = (await read_usage(session, days=7, today=TODAY, zone=TAIPEI)).by_user

        assert [(line.user_id, line.name, line.tally.calls) for line in lines] == [
            (skipper.id, "skipper", 2),
            (deckhand.id, "deckhand", 1),
            (None, None, 1),
        ]

    async def test_origins_and_failures(self, session: AsyncSession) -> None:
        await stored(
            session,
            call(),
            call(input=None, output=None, read=None, write=None, failure=AiFailure.RATE_LIMITED),
            call(input=None, output=None, read=None, write=None, failure=AiFailure.RATE_LIMITED),
            call(input=800, output=None, failure=AiFailure.PROVIDER_DOWN),
        )

        report = await read_usage(session, days=7, today=TODAY, zone=TAIPEI)

        assert [(line.origin, line.tally.calls) for line in report.by_origin] == [
            (AiCallOrigin.TEST, 4)
        ]
        # 多的在前。
        assert [(line.failure, line.calls) for line in report.failures] == [
            (AiFailure.RATE_LIMITED, 2),
            (AiFailure.PROVIDER_DOWN, 1),
        ]
        assert report.totals.failed == 3
