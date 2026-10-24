"""用量頁的彙總（M5 票 13、plan §11.6〈用量記錄〉、`.scratch/m5/usage-page-shape.md`）。

只讀 `ai_calls`。不設預算（brief §6.10），所以這裡只有加總，沒有門檻。

- **`NULL` 是「不知道」**：每一格只加知道的那些，不當 0，也不讓整格變成不知道。
- **快取命中率** = Σ 快取讀取 ÷ Σ 輸入（輸入含快取寫入與讀取），只加**輸入與快取讀取兩格都
  知道**的呼叫；分母是 0 時是 `None`。快取讀取不知道的另外數（`cache_unreported`），頁面說得出
  命中率少算了幾次（連輸入都不知道的不算在這裡：它們本來就沒有東西可算）。
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import AiCallOrigin, AiFailure, ApiFormat
from berth.models import AiCall, User
from berth.services.commands import Effect, command


@dataclass(frozen=True)
class UsageTally:
    calls: int
    #: 沒成的（`failure` 不是空的）；它們也在 `calls` 裡。
    failed: int
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    #: 0–1；分母是 0（沒有一筆兩格都知道、或輸入全是 0）時是 `None`。
    hit_rate: float | None
    #: 知道輸入、快取讀取卻是 `NULL` 的呼叫數：它們花了輸入卻不在命中率裡。連輸入都不知道的
    #: （送出就被限流）不算——它們對命中率本來就沒有東西可算。
    cache_unreported: int


@dataclass(frozen=True)
class DayUsage:
    date: date
    tally: UsageTally


@dataclass(frozen=True)
class OriginUsage:
    origin: AiCallOrigin
    tally: UsageTally


@dataclass(frozen=True)
class ModelUsage:
    """一個端點上的一個模型：同一個模型 id 經兩台主機是兩列（快取各算各的）。"""

    format: ApiFormat
    host: str
    model: str
    tally: UsageTally


@dataclass(frozen=True)
class UserUsage:
    #: `None` 是沒有人：背景任務（M6），或人刪了（`SET NULL`）。
    user_id: int | None
    name: str | None
    tally: UsageTally


@dataclass(frozen=True)
class FailureCount:
    failure: AiFailure
    calls: int


@dataclass(frozen=True)
class UsageReport:
    #: 有史以來有沒有任何一列：分得出「第一次來」與「這段期間沒有」。
    has_any: bool
    #: 期間的第一天與最後一天（含），`zone` 的牆上日期。
    since: date
    until: date
    totals: UsageTally
    #: 期間裡的每一天，沒有呼叫的也在（一格空的），由舊到新。
    days: tuple[DayUsage, ...]
    #: 以下各串都是用得多的在前（輸入 tokens，再來是呼叫數）。
    by_origin: tuple[OriginUsage, ...]
    by_model: tuple[ModelUsage, ...]
    by_user: tuple[UserUsage, ...]
    #: 沒成的分類與次數，多的在前；全都成了是空的。
    failures: tuple[FailureCount, ...]


def tally(calls: Iterable[AiCall]) -> UsageTally:
    rows = list(calls)
    known = [
        (row.input_tokens, row.cache_read_tokens)
        for row in rows
        if row.input_tokens is not None and row.cache_read_tokens is not None
    ]
    denominator = sum(spent for spent, _ in known)
    numerator = sum(read for _, read in known)
    return UsageTally(
        calls=len(rows),
        failed=sum(1 for row in rows if row.failure is not None),
        input_tokens=sum(row.input_tokens or 0 for row in rows),
        output_tokens=sum(row.output_tokens or 0 for row in rows),
        cache_write_tokens=sum(row.cache_write_tokens or 0 for row in rows),
        cache_read_tokens=sum(row.cache_read_tokens or 0 for row in rows),
        hit_rate=numerator / denominator if denominator else None,
        cache_unreported=sum(
            1 for row in rows if row.input_tokens is not None and row.cache_read_tokens is None
        ),
    )


@command(Effect.READ)
async def read_usage(
    session: AsyncSession, *, days: int, today: date, zone: tzinfo | None = None
) -> UsageReport:
    """`today` 往前 `days` 天（含今天）的用量。日期以 `zone` 的牆上時間切；`None` 是容器時區。"""
    since = today - timedelta(days=days - 1)
    found = (
        await session.execute(
            select(AiCall, User.name)
            .outerjoin(User, User.id == AiCall.user_id)
            .where(AiCall.created_at >= _midnight(since, zone))
            .where(AiCall.created_at < _midnight(today + timedelta(days=1), zone))
        )
    ).all()
    rows = [row for row, _ in found]
    names = {row.user_id: name for row, name in found}
    by_day: dict[date, list[AiCall]] = {since + timedelta(days=n): [] for n in range(days)}
    for row in rows:
        by_day[row.created_at.astimezone(zone).date()].append(row)
    has_any = await session.scalar(select(AiCall.id).limit(1)) is not None
    return UsageReport(
        has_any=has_any,
        since=since,
        until=today,
        totals=tally(rows),
        days=tuple(DayUsage(date=day, tally=tally(calls)) for day, calls in by_day.items()),
        by_origin=tuple(
            OriginUsage(origin=origin, tally=counted)
            for origin, counted in _grouped(rows, lambda row: row.origin)
        ),
        by_model=tuple(
            ModelUsage(format=format, host=host, model=model, tally=counted)
            for (format, host, model), counted in _grouped(
                rows, lambda row: (row.format, row.host, row.model)
            )
        ),
        by_user=tuple(
            UserUsage(user_id=user_id, name=names[user_id], tally=counted)
            for user_id, counted in _grouped(rows, lambda row: row.user_id)
        ),
        failures=tuple(
            FailureCount(failure=failure, calls=calls)
            for failure, calls in sorted(
                Counter(row.failure for row in rows if row.failure is not None).items(),
                key=lambda pair: (-pair[1], pair[0].value),
            )
        ),
    )


def _grouped[K: Hashable](
    rows: list[AiCall], key: Callable[[AiCall], K]
) -> list[tuple[K, UsageTally]]:
    groups: defaultdict[K, list[AiCall]] = defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    counted = [(group, tally(calls)) for group, calls in groups.items()]
    # 同量時照鍵的字面排，畫面每次重整才不會換位置。
    return sorted(counted, key=lambda pair: (-pair[1].input_tokens, -pair[1].calls, str(pair[0])))


def _midnight(day: date, zone: tzinfo | None) -> datetime:
    """那一天在 `zone` 的 00:00。`None` 是容器時區：naive 的 `astimezone()` 照當地的夏令時間換。"""
    if zone is None:
        return datetime.combine(day, time.min).astimezone()
    return datetime.combine(day, time.min, tzinfo=zone)
