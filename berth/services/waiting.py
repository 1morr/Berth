"""等你處理：現在有哪幾件要管理員動手（M4 票 127，plan §11.5〈通知〉）。

三份清單，各自照它們的頁面怎麼算：審核佇列（`review.queue_keys`，`/review`）、開著的 Issue
（`issues.open_issues`，`/issues`）、待綁定的 RSS Series（`rss.unbound_series`，`/rss` 的
待綁定段）。
這裡只說「有誰」，不說內容：「有 N 件等你處理」的看守（`notify.watch_waiting`）拿它與上一輪比，
送出時再拿一次重算還剩哪幾件。

**看清單，不在寫入點各掛一個**：進審核的路有規劃、入庫、撤銷、重新規劃；RSS Series 變待綁定有
長出來、解除綁定，還有作品被刪時資料庫的 `SET NULL`——最後那一條根本沒有程式碼可掛。清單上有的
就是頁面上看得到的，新增與總數永遠和頁面對得上。

每一件的鍵是 `<來源>:<id>`（審核多一段種類：`review:audit:12`），錨點是那一列在頁面上的 `id`
（`#audit-12`、`#issue-5`、`#series-7`，形狀是 `deeplink` 的 `*_ROW`），前端照同一個形狀給列
加 `id`。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from berth.domain import IssueType
from berth.services.commands import Effect, command
from berth.services.deeplink import (
    ISSUE_ROW,
    ISSUES_PAGE,
    REVIEW_PAGE,
    REVIEW_ROW,
    RSS_PAGE,
    SERIES_ROW,
)
from berth.services.issues import open_issues
from berth.services.review import queue_keys
from berth.services.rss import unbound_series


class WaitingSource(StrEnum):
    """一件在哪一份清單上。順序就是訊息裡說的順序。"""

    REVIEW = "review"
    ISSUE = "issue"
    RSS = "rss"


#: 每一份清單的頁面。
LIST_PAGE: dict[WaitingSource, str] = {
    WaitingSource.REVIEW: REVIEW_PAGE,
    WaitingSource.ISSUE: ISSUES_PAGE,
    WaitingSource.RSS: RSS_PAGE,
}


@dataclass(frozen=True, slots=True)
class Waiting:
    """等著的一件。"""

    source: WaitingSource
    #: 它在那一份清單上的 id（Issue id、RSS Series id、審核那一類的 id）。
    ref: int
    #: 只有這一件時連到哪：清單頁加那一列的錨點。
    path: str
    #: Issue 的型別（訊息說「1 個 Issue（檔案遺失）」）；其他來源是 `None`。
    issue_type: IssueType | None = None


@command(Effect.READ)
async def waiting_now(session: AsyncSession) -> dict[str, Waiting]:
    """現在等著的每一件，鍵 → 那一件。順序：審核、Issue、RSS，各自照清單的順序。"""
    found: dict[str, Waiting] = {}
    for kind, id_ in await queue_keys(session):
        found[f"review:{kind.value}:{id_}"] = Waiting(
            WaitingSource.REVIEW,
            id_,
            f"{REVIEW_PAGE}#{REVIEW_ROW.format(kind=kind.value, ref=id_)}",
        )
    for id_, issue_type in await open_issues(session):
        found[f"issue:{id_}"] = Waiting(
            WaitingSource.ISSUE,
            id_,
            f"{ISSUES_PAGE}#{ISSUE_ROW.format(ref=id_)}",
            issue_type=issue_type,
        )
    for id_ in await unbound_series(session):
        found[f"rss:{id_}"] = Waiting(
            WaitingSource.RSS, id_, f"{RSS_PAGE}#{SERIES_ROW.format(ref=id_)}"
        )
    return found
