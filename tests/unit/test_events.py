"""SSE 的廣播與輪詢間隔的純規則（plan §3.2、§6 events 群組、票 10）。

兩者都不碰資料庫也不碰網路，所以它們的規則在這裡逐條釘：訂閱者落後時該丟哪一筆、
連續失敗時下一次多久再試。
"""

from __future__ import annotations

from berth.domain import JobState
from berth.services.downloads import BACKOFF_CEILING, IDLE_INTERVAL, backoff
from berth.services.events import EventHub, JobSignal


def signal(hash_: str) -> JobSignal:
    return JobSignal(hash=hash_, state=JobState.DOWNLOADING, progress=0.0)


def test_a_slow_subscriber_loses_the_oldest_not_the_newest() -> None:
    """事件是「去重問」的提示，最新的那一筆永遠比舊的有價值。

    丟最新的（`QueueFull` 就放棄）會讓一個睡著的分頁醒來之後停在一個過期的狀態上，
    而那正是這條推播要解決的問題。
    """
    hub = EventHub(capacity=2)

    with hub.subscribe() as queue:
        for index in range(5):
            hub.publish(signal(str(index)))

        assert [queue.get_nowait().hash for _ in range(2)] == ["3", "4"]


def test_publishing_with_nobody_listening_is_fine() -> None:
    """發佈端是背景迴圈：它不能因為沒有人開著分頁就出事。"""
    EventHub().publish(signal("a"))


def test_leaving_the_context_takes_the_subscription_with_it() -> None:
    """斷線的分頁不能留下一條永遠沒人讀的佇列。"""
    hub = EventHub()

    with hub.subscribe():
        assert hub.subscribers == 1

    assert hub.subscribers == 0


def test_everyone_listening_gets_the_same_signal() -> None:
    hub = EventHub()

    with hub.subscribe() as first, hub.subscribe() as second:
        hub.publish(signal("abc"))

        assert first.get_nowait().hash == "abc"
        assert second.get_nowait().hash == "abc"


def test_consecutive_failures_back_off_to_five_minutes() -> None:
    """plan §3.2：連續失敗退避到 5 分鐘。

    第一次失敗仍然等一個完整的閒置間隔——qBittorrent 重啟一次要幾秒，立刻重試只會再
    失敗一次，而每一次失敗都會在健康頁上多記一筆。
    """
    assert backoff(0) == IDLE_INTERVAL
    assert backoff(1) == IDLE_INTERVAL
    assert backoff(2) == IDLE_INTERVAL * 2
    assert backoff(9) == BACKOFF_CEILING
    assert backoff(50) == BACKOFF_CEILING
