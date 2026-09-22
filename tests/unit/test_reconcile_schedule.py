"""對帳排程的邊界（`pipeline/reconciling.previous`、plan §3.2、M2 票 05）。

純函式，所以住在 unit：排程的判斷是「有沒有跨過某一個 04:00」，而跨過的定義是最近那一個
04:00 比上次跑的那一個新。算錯的話迴圈會整天不停地跑，或者永遠不跑——兩種都是靜的。
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from berth.pipeline.reconciling import RECONCILE_AT, previous

#: 03:30，也就是**還沒**跨過今天的 04:00。
BEFORE = datetime(2026, 9, 22, 3, 30, tzinfo=UTC)
AFTER = datetime(2026, 9, 22, 4, 30, tzinfo=UTC)


class TestTheBoundary:
    """`previous()`：`now` 之前最近的那一個 04:00。"""

    def test_before_the_hour_it_is_yesterdays(self) -> None:
        assert previous(BEFORE, RECONCILE_AT) == BEFORE.replace(hour=4, minute=0) - timedelta(
            days=1
        )

    def test_after_the_hour_it_is_todays(self) -> None:
        assert previous(AFTER, RECONCILE_AT) == AFTER.replace(hour=4, minute=0)

    def test_exactly_on_the_hour_counts_as_crossed(self) -> None:
        on_it = AFTER.replace(hour=4, minute=0, second=0, microsecond=0)

        assert previous(on_it, RECONCILE_AT) == on_it

    def test_a_different_hour_moves_the_boundary(self) -> None:
        """這一條釘住「`at` 真的有被讀」：寫死 04:00 的實作在這裡才會紅。"""
        assert previous(AFTER, time(5, 0)) == AFTER.replace(hour=5, minute=0) - timedelta(days=1)
