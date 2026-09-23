"""`jellyfin_resolver` 的排程（plan §3.2）：寫下一筆帳本的人要知道它第一次什麼時候被反查。

**自己一個模組**是因為寫帳本的有三處（importer、rematch 走的那一步、`claims.claim_file`），而
`services/resolver` 本身要 import `services/issues`（反查用完寫 `jellyfin_item_unresolved`）——
`issues` 又要呼叫 `claims`（認領類的按鈕，票 10）。排程放在 `resolver` 裡就是一個環。
"""

from __future__ import annotations

from datetime import datetime, timedelta

#: 第 n 次反查之前要等多久（plan §3.2）。長度就是總次數：6 次。
RESOLVE_DELAYS: tuple[timedelta, ...] = (
    timedelta(seconds=30),
    timedelta(minutes=2),
    timedelta(minutes=10),
    timedelta(hours=1),
    timedelta(hours=1),
    timedelta(hours=1),
)


def first_resolve_at(now: datetime) -> datetime:
    """一筆剛寫下的帳本第一次反查的時間。"""
    return now + RESOLVE_DELAYS[0]
