"""花費提醒的規則（M5 票 21、研究 C3〈花費可見性〉）：只提醒、不停用。"""

from __future__ import annotations

from decimal import Decimal

from berth.domain.spend import SpendAlert, SpendAlertKind, spend_alerts


def _d(*values: str) -> list[Decimal]:
    return [Decimal(v) for v in values]


class TestDailyThreshold:
    def test_at_or_over_the_threshold_alerts(self) -> None:
        alerts = spend_alerts(Decimal("1.00"), threshold=Decimal("1.00"), previous=[])
        assert alerts == [SpendAlert(SpendAlertKind.THRESHOLD, Decimal("1.00"), Decimal("1.00"))]

    def test_under_the_threshold_is_quiet(self) -> None:
        assert spend_alerts(Decimal("0.99"), threshold=Decimal("1.00"), previous=[]) == []

    def test_no_threshold_set_is_quiet(self) -> None:
        assert spend_alerts(Decimal("50"), threshold=None, previous=[]) == []


class TestAnomaly:
    def test_five_times_the_median_of_days_with_usage_alerts(self) -> None:
        # 有用量的日子：0.01、0.02、0.03 → 中位數 0.02，5 倍是 0.10；沒用的日子（0）不算進去。
        previous = _d("0", "0.01", "0", "0.02", "0.03", "0")
        alerts = spend_alerts(Decimal("0.10"), threshold=None, previous=previous)
        assert alerts == [SpendAlert(SpendAlertKind.ANOMALY, Decimal("0.10"), Decimal("0.02"))]

    def test_just_under_five_times_is_quiet(self) -> None:
        previous = _d("0.01", "0.02", "0.03")
        assert spend_alerts(Decimal("0.0999"), threshold=None, previous=previous) == []

    def test_fewer_than_three_days_with_usage_is_quiet(self) -> None:
        previous = _d("0", "0.01", "0", "0.01", "0")
        assert spend_alerts(Decimal("5"), threshold=None, previous=previous) == []

    def test_even_count_takes_the_middle_two(self) -> None:
        previous = _d("0.01", "0.02", "0.04", "0.10")
        # 中位數 (0.02 + 0.04) / 2 = 0.03，5 倍 0.15。
        assert spend_alerts(Decimal("0.14"), threshold=None, previous=previous) == []
        assert spend_alerts(Decimal("0.15"), threshold=None, previous=previous) == [
            SpendAlert(SpendAlertKind.ANOMALY, Decimal("0.15"), Decimal("0.03"))
        ]

    def test_only_the_last_fourteen_days_count(self) -> None:
        # 最舊的三天很便宜；只看最後 14 天的話中位數是 1，今天的 2 不算異常。
        previous = _d("0.001", "0.001", "0.001", *(["1"] * 14))
        assert spend_alerts(Decimal("2"), threshold=None, previous=previous) == []


def test_both_alerts_can_fire_together() -> None:
    previous = _d("0.01", "0.01", "0.01")
    kinds = [
        a.kind for a in spend_alerts(Decimal("1"), threshold=Decimal("0.5"), previous=previous)
    ]
    assert kinds == [SpendAlertKind.THRESHOLD, SpendAlertKind.ANOMALY]


def test_nothing_spent_today_is_quiet() -> None:
    previous = _d("0.01", "0.01", "0.01")
    assert spend_alerts(Decimal("0"), threshold=Decimal("0"), previous=previous) == []
