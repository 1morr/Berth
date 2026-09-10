"""AI fallback 解析器的介面（plan §4.5、brief §6.10）。

**介面在 M1 就定好，實作在 M4。**先定的理由是它約束的是規則層：`propose` 收規則層算出來的
Plan、回同一個型別的 Plan，所以 AI 只能提出一份「這幾個檔案應該這樣放」的提案，
不能發明一種規則層表達不出來的處置，也碰不到檔案（brief §6.10「AI 是 fallback 解析器與
助理，不是執行者」）。

與 provider 無關的那幾件事（輸入壓縮、schema 驗證、快取鍵、預算檢查）住在 `services/plan.py`，
不在這裡——換一家 provider 不該讓預算檢查跟著搬家。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from berth.domain import FileEntry, ParseContext, PlanItem

#: 一份 Plan 就是逐檔的決定（plan §4.1）。取一個名字是因為它同時是 `propose` 的輸入與輸出。
Plan = tuple[PlanItem, ...]


class AiPlanner(Protocol):
    """規則層說不出話時的第二意見（brief §6.10）。"""

    async def propose(
        self, context: ParseContext, files: Sequence[FileEntry], rules_plan: Plan
    ) -> Plan | None:
        """提一份 Plan，或什麼都不提。

        `rules_plan` 是規則層已經算出來的那一份：AI 看得到規則層的部分解析，才不會
        從頭猜一遍（brief §6.10 的輸入清單）。

        回 `None` 表示**沒有意見**，呼叫端退回 review；回一份空的 Plan 是另一件事
        （「這一包什麼都不用做」），所以兩者不能混用。
        """
        ...


class NullAiPlanner:
    """M1 的實作：永遠沒有意見。

    不是佔位符——它是「使用者沒有開啟 AI 解析」時的正式行為（brief §6.10 的觸發條件）。
    所以它住在 `adapters/` 而不是測試裡。
    """

    async def propose(
        self, context: ParseContext, files: Sequence[FileEntry], rules_plan: Plan
    ) -> Plan | None:
        return None
