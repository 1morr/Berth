"""全域令牌桶（plan §8.3：TMDB 40 req/s）。

時鐘與 sleep 都是注入的，所以這裡量的是「它決定等多久」，不是「測試跑了多久」——
靠真的時間測速率上限只會得到一個慢而且會偶爾紅的測試。
"""

from __future__ import annotations

import pytest

from berth.adapters.rate import TokenBucket


class FakeClock:
    """單調時鐘 + 記錄下來的 sleep。`sleep` 會把時鐘往前推，就像真的睡過去一樣。"""

    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def time(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


@pytest.mark.asyncio
async def test_a_full_bucket_lets_the_whole_burst_through() -> None:
    clock = FakeClock()
    bucket = TokenBucket(rate=40.0, capacity=40, clock=clock.time, sleep=clock.sleep)

    for _ in range(40):
        await bucket.acquire()

    assert clock.slept == []


@pytest.mark.asyncio
async def test_the_request_after_the_burst_waits_one_slot() -> None:
    clock = FakeClock()
    bucket = TokenBucket(rate=40.0, capacity=40, clock=clock.time, sleep=clock.sleep)
    for _ in range(40):
        await bucket.acquire()

    await bucket.acquire()

    assert clock.slept == [pytest.approx(1 / 40)]


@pytest.mark.asyncio
async def test_a_sustained_run_settles_on_the_configured_rate() -> None:
    """突發用完之後，每一次都剛好等一格：100 次呼叫花掉 60 格 = 1.5 秒。"""
    clock = FakeClock()
    bucket = TokenBucket(rate=40.0, capacity=40, clock=clock.time, sleep=clock.sleep)

    for _ in range(100):
        await bucket.acquire()

    assert sum(clock.slept) == pytest.approx(60 / 40)


@pytest.mark.asyncio
async def test_idle_time_refills_the_bucket() -> None:
    clock = FakeClock()
    bucket = TokenBucket(rate=40.0, capacity=40, clock=clock.time, sleep=clock.sleep)
    for _ in range(40):
        await bucket.acquire()

    clock.now += 10.0
    for _ in range(40):
        await bucket.acquire()

    assert clock.slept == []


@pytest.mark.asyncio
async def test_the_bucket_never_banks_more_than_its_capacity() -> None:
    """閒置一整天不代表接下來可以一次送三千個請求。"""
    clock = FakeClock()
    bucket = TokenBucket(rate=40.0, capacity=40, clock=clock.time, sleep=clock.sleep)

    clock.now += 86_400.0
    for _ in range(41):
        await bucket.acquire()

    assert clock.slept == [pytest.approx(1 / 40)]
