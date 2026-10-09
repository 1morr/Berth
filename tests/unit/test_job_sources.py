"""送單來源暫存在伺服器上（M4 票 79）。

搜尋結果與一次性連結的每一筆在這裡換成一個不透明的 id，送單只收那個 id。時鐘是注入的，所以
這裡量的是它怎麼判斷過期，不是等了多久。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from berth.domain import JobRefusal
from berth.services.jobs import JobRejectedError, JobSource
from berth.services.sources import SOURCE_TTL_SECONDS, SourceCache

PROXY = "http://prowlarr:9696/2/download?apikey=prowlarr-secret&link=abc"
SOURCE = JobSource(
    url=PROXY,
    title="[ANi] SPY x FAMILY - 26 [1080P][CHT]",
    info_hash="a" * 40,
    published_at=datetime(2026, 9, 24, 13, 1, tzinfo=UTC),
    size=524288000,
)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def cache() -> tuple[SourceCache, Clock]:
    clock = Clock()
    return SourceCache(clock=clock), clock


def test_an_id_hands_back_the_source_it_stands_for() -> None:
    sources, _ = cache()

    assert sources.recall(sources.remember(SOURCE)) == SOURCE


def test_the_id_says_nothing_about_the_link() -> None:
    """瀏覽器拿到的只有 id：連結、key、發佈名都不在裡面。"""
    sources, _ = cache()

    source_id = sources.remember(SOURCE)

    assert "prowlarr" not in source_id
    assert "apikey" not in source_id
    assert "SPY" not in source_id


def test_every_row_gets_its_own_id_even_for_the_same_release() -> None:
    """兩輪搜尋到同一個發佈是兩條不同的代理連結（brief §20.7），各自記。"""
    sources, _ = cache()

    assert sources.remember(SOURCE) != sources.remember(SOURCE)


def test_an_id_still_works_just_before_it_expires() -> None:
    sources, clock = cache()
    source_id = sources.remember(SOURCE)

    clock.now += SOURCE_TTL_SECONDS - 1

    assert sources.recall(source_id) == SOURCE


def test_an_expired_id_is_refused_with_a_reason() -> None:
    sources, clock = cache()
    source_id = sources.remember(SOURCE)

    clock.now += SOURCE_TTL_SECONDS

    with pytest.raises(JobRejectedError) as refused:
        sources.recall(source_id)
    assert refused.value.reason is JobRefusal.SOURCE_EXPIRED


def test_an_id_it_never_handed_out_is_refused_the_same_way() -> None:
    """重啟之後、手打的、別台的：Berth 分不出來，下一步都是再搜一次。"""
    sources, _ = cache()

    with pytest.raises(JobRejectedError) as refused:
        sources.recall("not-an-id")
    assert refused.value.reason is JobRefusal.SOURCE_EXPIRED
    # `detail` 是原文，畫面原樣印出來：不回聲送來的字串。
    assert refused.value.detail == ""


def test_expired_entries_do_not_pile_up() -> None:
    """記的時候順手清掉過期的：一個程序開幾個月，記憶體只有最近這段時間的搜尋。"""
    sources, clock = cache()
    for _ in range(50):
        sources.remember(SOURCE)

    clock.now += SOURCE_TTL_SECONDS
    sources.remember(SOURCE)

    assert len(sources) == 1
