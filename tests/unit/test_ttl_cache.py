"""`TtlCache`：過期、滿了丟最舊的、覆寫算新的（M5 票 16）。時鐘是注入的。"""

from __future__ import annotations

from berth.adapters.ttl import TtlCache


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_an_entry_is_served_until_its_ttl_is_up() -> None:
    clock = Clock()
    cache: TtlCache[str] = TtlCache(ttl=10, size=4, clock=clock)
    cache.put("a", "x")

    clock.now += 9.9
    assert cache.get("a") == "x"

    clock.now += 0.1  # 剛好滿 ttl：過期
    assert cache.get("a") is None


def test_a_missing_key_is_none() -> None:
    assert TtlCache[str](ttl=10, size=4).get("nope") is None


def test_putting_clears_the_expired_entries_from_the_front() -> None:
    clock = Clock()
    cache: TtlCache[str] = TtlCache(ttl=10, size=4, clock=clock)
    cache.put("a", "1")
    clock.now += 5
    cache.put("b", "2")
    clock.now += 6  # a 過期、b 還沒

    cache.put("c", "3")

    assert len(cache) == 2
    assert cache.get("a") is None
    assert cache.get("b") == "2"
    assert cache.get("c") == "3"


def test_a_full_cache_drops_the_oldest_entry() -> None:
    cache: TtlCache[int] = TtlCache(ttl=10, size=3, clock=Clock())
    for i, key in enumerate("abc"):
        cache.put(key, i)

    cache.put("d", 3)

    assert len(cache) == 3
    assert cache.get("a") is None
    assert [cache.get(k) for k in "bcd"] == [1, 2, 3]


def test_overwriting_a_key_makes_it_the_newest() -> None:
    cache: TtlCache[int] = TtlCache(ttl=10, size=3, clock=Clock())
    for i, key in enumerate("abc"):
        cache.put(key, i)

    cache.put("a", 10)  # a 變成最新的
    cache.put("d", 3)  # 該被丟的是 b，不是 a

    assert cache.get("a") == 10
    assert cache.get("b") is None
    assert [cache.get(k) for k in "cd"] == [2, 3]


def test_overwriting_in_a_full_cache_does_not_evict_another_entry() -> None:
    cache: TtlCache[int] = TtlCache(ttl=10, size=3, clock=Clock())
    for i, key in enumerate("abc"):
        cache.put(key, i)

    cache.put("b", 11)  # 筆數沒有增加，不該有人被丟

    assert len(cache) == 3
    assert [cache.get(k) for k in "abc"] == [0, 11, 2]


def test_overwriting_restarts_the_ttl() -> None:
    clock = Clock()
    cache: TtlCache[str] = TtlCache(ttl=10, size=3, clock=clock)
    cache.put("a", "old")
    clock.now += 8

    cache.put("a", "new")
    clock.now += 8

    assert cache.get("a") == "new"
