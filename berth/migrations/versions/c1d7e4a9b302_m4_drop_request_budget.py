"""被請求預算擋下的 RSS Series 改成下一輪就重認（M4 票 107）。

票 107 刪掉一個站一份的請求預算，`lookup_deferred` 那一種理由跟著不在了。還帶著它的 Series 不轉換的
話永遠不會再被重認（`_due_lookups` 只看 `lookup_retry` 的 `at`），一直卡在待綁定。

**升版**：`lookup_deferred` 換成 `at` 是升版那一刻的 `lookup_retry`，`attempt` 是 0——被預算擋下
不是查不到，不算進重認的上限（`attempt` 是已經算的失敗次數，下一次失敗才記成第 1 次）。原本就排著
一次重認的（被擋之前已經失敗過）留那一條、`attempt` 照舊，只把 `at` 提前到升版那一刻。

**降版**：`attempt` 是 0 的 `lookup_retry` 只會是這一版寫的，換回 `lookup_deferred`；提前了 `at`
的那一種分不出來，留著（舊版本照 `at` 一樣會重認它）。

Revision ID: c1d7e4a9b302
Revises: bec5947663f5
Create Date: 2026-10-19 12:00:00.000000
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "c1d7e4a9b302"
down_revision: str | None = "bec5947663f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEFERRED = "lookup_deferred"
_RETRY = "lookup_retry"
#: 換上去的 `lookup_retry` 的 `detail`（原文是英文，同其他理由）。
_DETAIL = "deferred by the request budget, which was removed"

Reasons = list[dict[str, Any]]


def upgrade() -> None:
    moment = datetime.now(UTC).isoformat()
    _rewrite(_DEFERRED, lambda reasons: _due_now(reasons, moment))


def downgrade() -> None:
    _rewrite(_RETRY, _deferred_again)


def _due_now(reasons: Reasons, moment: str) -> Reasons:
    deferred = next(one for one in reasons if one.get("code") == _DEFERRED)
    retrying = next((one for one in reasons if one.get("code") == _RETRY), None)
    if retrying is None:
        retrying = {
            "code": _RETRY,
            "params": {
                "site": deferred.get("params", {}).get("site", ""),
                "attempt": 0,
                "at": moment,
                "detail": _DETAIL,
            },
        }
    else:
        retrying = {**retrying, "params": {**retrying.get("params", {}), "at": moment}}
    kept = [one for one in reasons if one.get("code") not in (_DEFERRED, _RETRY)]
    return [retrying, *kept]


def _deferred_again(reasons: Reasons) -> Reasons:
    return [
        {"code": _DEFERRED, "params": {"site": one["params"].get("site", "")}}
        if one.get("code") == _RETRY and one.get("params", {}).get("attempt") == 0
        else one
        for one in reasons
    ]


def _rewrite(code: str, change: Callable[[Reasons], Reasons]) -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, reasons_json FROM rss_series WHERE reasons_json LIKE :pattern"),
        {"pattern": f'%"{code}"%'},
    ).fetchall()
    for series_id, raw in rows:
        reasons = json.loads(raw)
        if not any(one.get("code") == code for one in reasons):
            continue
        bind.execute(
            sa.text("UPDATE rss_series SET reasons_json = :reasons WHERE id = :id"),
            {
                "reasons": json.dumps(change(reasons), ensure_ascii=False, sort_keys=True),
                "id": series_id,
            },
        )
