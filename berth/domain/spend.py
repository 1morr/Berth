"""花費提醒的規則（M5 票 21、研究 C3〈花費可見性〉、brief §6.10）。

**只提醒、不停用**：這裡只算要不要說一句，沒有任何東西照它擋下 AI。費用是估計值，只用知道的那部分
（查不到價目的呼叫不算進來）。

- **每日提醒值**：今天的估計費用到了使用者設的值。
- **異常**：今天是近 14 天（不含今天）日中位數的 5 倍以上。中位數**只算有用量的日子**、至少 3 天
  （使用者 2026-10-27 選定）：家用多半幾天才問一次，把沒用的日子當 0 算，中位數常是 0，
  每一次使用都會變成「異常」。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from statistics import median

#: 異常比的是近幾天。
ANOMALY_WINDOW_DAYS = 14
#: 今天是中位數的幾倍以上算異常。
ANOMALY_FACTOR = 5
#: 有用量的日子少於這幾天就不比。
ANOMALY_MIN_DAYS = 3


class SpendAlertKind(StrEnum):
    #: 到了使用者設的每日提醒值。
    THRESHOLD = "threshold"
    #: 近 14 天日中位數的 5 倍以上。
    ANOMALY = "anomaly"


@dataclass(frozen=True, slots=True)
class SpendAlert:
    kind: SpendAlertKind
    #: 今天的估計費用（美元）。
    today: Decimal
    #: 比的那個數：提醒值，或中位數。
    against: Decimal


def spend_alerts(
    today: Decimal, *, threshold: Decimal | None, previous: Sequence[Decimal]
) -> list[SpendAlert]:
    """今天該說的提醒。`previous` 是今天之前**每一個日曆日**的費用，舊的在前，沒用量的日子是 0
    （近 14 天照項數取，漏掉沒用的日子會把更早的日子算進來）。
    """
    if today <= 0:
        return []
    alerts: list[SpendAlert] = []
    if threshold is not None and today >= threshold:
        alerts.append(SpendAlert(SpendAlertKind.THRESHOLD, today, threshold))
    used = [cost for cost in previous[-ANOMALY_WINDOW_DAYS:] if cost > 0]
    if len(used) >= ANOMALY_MIN_DAYS:
        middle = median(used)
        if today >= middle * ANOMALY_FACTOR:
            alerts.append(SpendAlert(SpendAlertKind.ANOMALY, today, middle))
    return alerts
