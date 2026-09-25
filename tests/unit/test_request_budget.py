"""一個站一份請求預算（M3 票 20、plan §3.2）。

形狀照 Prowlarr 索引站的 Query Limit：一個站在一段**滾動**視窗裡最多幾個請求，用完的那一個
被拒絕（不是排隊等），並說得出何時放得下。時鐘是注入的，所以這裡量的是它怎麼判斷，不是等了多久。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from berth.adapters.budget import BudgetExhaustedError, RequestBudget, site_of
from berth.domain import BudgetUse

START = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
HOUR = timedelta(hours=1)


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now


def budget(limit: int = 3) -> tuple[RequestBudget, Clock]:
    clock = Clock()
    return RequestBudget(limit=limit, window=HOUR, now=clock), clock


def test_requests_within_the_limit_go_through() -> None:
    requests, _ = budget(limit=3)

    for _ in range(3):
        requests.take(("mikanani.me",), 1, BudgetUse.POLL)

    (usage,) = requests.usage()
    assert usage.site == "mikanani.me"
    assert usage.used == 3


def test_one_past_the_limit_is_refused_with_the_time_it_fits_again() -> None:
    """被拒的那一個不排隊：它說得出何時放得下——最早那一個滑出視窗的時刻。"""
    requests, clock = budget(limit=2)
    requests.take(("mikanani.me",), 1, BudgetUse.POLL)
    clock.now = START + timedelta(minutes=10)
    requests.take(("mikanani.me",), 1, BudgetUse.BACKFILL)

    with pytest.raises(BudgetExhaustedError) as refused:
        requests.take(("mikanani.me",), 1, BudgetUse.SEARCH)

    assert refused.value.site == "mikanani.me"
    assert refused.value.until == START + HOUR


def test_the_window_rolls() -> None:
    """滾動視窗，不是整點歸零：一小時前的那一個滑出去，就空出一格。"""
    requests, clock = budget(limit=1)
    requests.take(("nyaa.si",), 1, BudgetUse.POLL)

    clock.now = START + HOUR
    requests.take(("nyaa.si",), 1, BudgetUse.POLL)

    (usage,) = requests.usage()
    assert usage.used == 1


def test_each_site_has_its_own_budget() -> None:
    requests, _ = budget(limit=1)

    requests.take(("mikanani.me",), 1, BudgetUse.POLL)
    requests.take(("nyaa.si",), 1, BudgetUse.POLL)

    assert {usage.site: usage.used for usage in requests.usage()} == {
        "mikanani.me": 1,
        "nyaa.si": 1,
    }


def test_a_batch_takes_all_of_its_requests_on_every_site_or_none() -> None:
    """一批搜尋是五個查詢、每一個都打到每一個站：有一站放不下就整批不問，也不佔任何一站。"""
    requests, _ = budget(limit=5)
    requests.take(("nyaa.si",), 1, BudgetUse.POLL)

    with pytest.raises(BudgetExhaustedError) as refused:
        requests.take(("mikanani.me", "nyaa.si"), 5, BudgetUse.SEARCH)

    assert refused.value.site == "nyaa.si"
    assert {usage.site: usage.used for usage in requests.usage()} == {"nyaa.si": 1}


def test_ready_at_says_when_a_batch_fits() -> None:
    requests, clock = budget(limit=5)
    requests.take(("mikanani.me",), 3, BudgetUse.SEARCH)
    clock.now = START + timedelta(minutes=20)
    requests.take(("mikanani.me",), 2, BudgetUse.SEARCH)

    assert requests.ready_at(("mikanani.me",), 3) == START + HOUR
    assert requests.ready_at(("mikanani.me",), 0) == clock.now
    assert requests.ready_at(("nyaa.si",), 5) == clock.now


def test_a_batch_larger_than_the_limit_never_fits() -> None:
    """放不下的批次不說一個永遠不會到的時間。"""
    requests, _ = budget(limit=3)

    with pytest.raises(BudgetExhaustedError) as refused:
        requests.take(("mikanani.me",), 4, BudgetUse.SEARCH)

    assert refused.value.until is None
    assert requests.ready_at(("mikanani.me",), 4) is None


def test_usage_splits_the_count_by_who_asked() -> None:
    """健康頁要說得出這一小時是誰用掉的：輪詢、補漏、搜尋共用一份。"""
    requests, _ = budget(limit=10)
    requests.take(("mikanani.me",), 1, BudgetUse.POLL)
    requests.take(("mikanani.me",), 1, BudgetUse.POLL)
    requests.take(("mikanani.me",), 1, BudgetUse.BACKFILL)
    requests.take(("mikanani.me",), 5, BudgetUse.SEARCH)

    (usage,) = requests.usage()
    assert dict(usage.by_use) == {
        BudgetUse.POLL: 2,
        BudgetUse.BACKFILL: 1,
        BudgetUse.SEARCH: 5,
    }


def test_refused_work_is_listed_until_it_goes_through() -> None:
    """用完時被延後的工作要說得出來（票 20 驗收第三條）：誰被擋、擋了幾次、何時放得下；
    同一種工作之後過得去就不再列。"""
    requests, clock = budget(limit=1)
    requests.take(("mikanani.me",), 1, BudgetUse.POLL)
    for _ in range(2):
        with pytest.raises(BudgetExhaustedError):
            requests.take(("mikanani.me",), 1, BudgetUse.BACKFILL)

    (usage,) = requests.usage()
    (deferral,) = usage.deferred
    assert deferral.use is BudgetUse.BACKFILL
    assert deferral.refused == 2
    assert deferral.since == START
    assert deferral.until == START + HOUR

    clock.now = START + HOUR
    requests.take(("mikanani.me",), 1, BudgetUse.BACKFILL)

    (usage,) = requests.usage()
    assert usage.deferred == ()


def test_a_site_is_its_host_without_www() -> None:
    assert site_of("https://mikanani.me/RSS/MyBangumi?token=x") == "mikanani.me"
    assert site_of("https://www.Nyaa.si/?page=rss") == "nyaa.si"
    assert site_of("https://acg.rip/1.xml?term=x") == "acg.rip"


def test_a_deferral_stops_being_listed_once_it_fits_again() -> None:
    """搜尋與人按的讀取被擋之後沒有東西自己重試：放得下的時刻一過就不再算「延後」，
    否則健康頁會一直說它在等（code review 抓到）。"""
    requests, clock = budget(limit=1)
    requests.take(("mikanani.me",), 1, BudgetUse.POLL)
    with pytest.raises(BudgetExhaustedError):
        requests.take(("mikanani.me",), 1, BudgetUse.SEARCH)

    clock.now = START + HOUR

    assert requests.usage() == ()


def test_a_request_too_big_to_ever_fit_is_listed_for_one_window() -> None:
    """永遠放不下的那一種沒有「放得下的時刻」：列一個窗長就收起來。"""
    requests, clock = budget(limit=1)
    with pytest.raises(BudgetExhaustedError):
        requests.take(("mikanani.me",), 5, BudgetUse.SEARCH)

    clock.now = START + timedelta(minutes=59)
    assert [row.deferred for row in requests.usage()] != [()]
    clock.now = START + HOUR
    assert requests.usage() == ()
